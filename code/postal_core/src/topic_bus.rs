//! TopicBus - The central pub/sub coordinator.
//!
//! Ported from Whisper's parallel_fabric.py TopicBus:
//! - Per-topic worker pools
//! - Three priority lanes per topic
//! - Autoscaling based on load and system pressure
//! - Subscriber management with batching/coalescing options

use dashmap::DashMap;
use parking_lot::RwLock;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::Duration;

use crate::backpressure::BackpressurePolicy;
use crate::envelope::Envelope;
use crate::metrics::{MetricsSnapshot, PostalMetrics};
use crate::priority::Priority;
use crate::return_office::{
    ReturnOffice, RETURN_GLOBAL_DEFAULT, RETURN_GLOBAL_FLOOR, RETURN_POOL, RETURN_RATE_DEFAULT, RETURN_RATE_FLOOR,
    RETURN_RING_DEFAULT,
};
use crate::worker::{cpu_pressure, WorkerPool, WorkerPoolConfig};

/// Configuration for the TopicBus.
#[derive(Debug, Clone)]
pub struct TopicBusConfig {
    /// Default max queue size per topic.
    pub default_max_queue: usize,
    /// Default max workers per topic.
    pub default_max_workers: usize,
    /// Default min workers per topic.
    pub default_min_workers: usize,
    /// Default target P95 latency in ms.
    pub default_target_p95_ms: u64,
    /// Default backpressure policy.
    pub backpressure: BackpressurePolicy,
    /// Autoscale check interval in ms.
    pub autoscale_interval_ms: u64,
    /// W2 return to sender. Default: AKASHIC_RETURN_TO_SENDER == "1" (OFF when unset).
    pub return_to_sender: bool,
    /// Ring of the last N returns. Default: AKASHIC_RETURN_RING or 256.
    pub return_ring: usize,
    /// Returned letters re-published per intent per second (floor 1). Default: AKASHIC_RETURN_RATE or 10.
    pub return_rate_per_intent: u32,
    /// Returned letters re-published per second in total (floor 10). Default: AKASHIC_RETURN_GLOBAL_RATE or 100.
    pub return_global_rate: u32,
}

fn env_flag(name: &str) -> bool {
    std::env::var(name).map(|v| v == "1").unwrap_or(false)
}

fn env_num<T: std::str::FromStr>(name: &str, default: T) -> T {
    std::env::var(name).ok().and_then(|v| v.parse().ok()).unwrap_or(default)
}

impl Default for TopicBusConfig {
    fn default() -> Self {
        Self {
            // FIX 2026-03-27 (Nous): Scaled BACK from 131K. With 836+ unique intents
            // each creating a pool, 131K × 836 × 3 channels = 20GB RAM overnight.
            // _BaseTopicPostal now collapses to ~20 base topics for Rust,
            // so each pool handles MORE traffic but fewer pools exist.
            // 65536 per pool → normal channel = 32768. ~20 pools × 65K × ~100B = ~130MB.
            default_max_queue: 65536,
            default_max_workers: 16,
            default_min_workers: 1,
            default_target_p95_ms: 150,
            backpressure: BackpressurePolicy::DropOldestLow,
            autoscale_interval_ms: 250,
            return_to_sender: env_flag("AKASHIC_RETURN_TO_SENDER"),
            return_ring: env_num("AKASHIC_RETURN_RING", RETURN_RING_DEFAULT),
            return_rate_per_intent: env_num("AKASHIC_RETURN_RATE", RETURN_RATE_DEFAULT).max(RETURN_RATE_FLOOR),
            return_global_rate: env_num("AKASHIC_RETURN_GLOBAL_RATE", RETURN_GLOBAL_DEFAULT).max(RETURN_GLOBAL_FLOOR),
        }
    }
}

/// Per-topic configuration overrides.
#[derive(Debug, Clone, Default)]
pub struct TopicConfig {
    pub max_queue: Option<usize>,
    pub max_workers: Option<usize>,
    pub min_workers: Option<usize>,
    pub target_p95_ms: Option<u64>,
}

/// A subscriber registration.
struct Subscriber {
    handler_id: usize,
    #[allow(dead_code)]
    name: String,
    coalesce_ms: u64,
    max_batch: usize,
    /// Full intent this subscriber actually asked for, e.g.
    /// "fairy.heartbeat.routed.MemoryEngineFairy". The POOL is keyed on the base
    /// topic ("fairy") so we keep ~20 pools instead of hundreds, but without this
    /// field publish() had no way to tell subscribers apart and enqueued to ALL of
    /// them -- 262 enqueues per heartbeat, 261 of which _pool_dispatch threw away.
    /// None = wildcard (base-topic subscriber), which is the pre-2026-08-28 behaviour.
    intent_filter: Option<String>,
}

impl Subscriber {
    /// Mirrors _pool_dispatch's Python filter EXACTLY:
    ///     original_intent == intent or original_intent.startswith(intent + '.')
    /// so a subscriber on "fairy.heartbeat" still receives "fairy.heartbeat.routed.X".
    fn wants(&self, intent: &str) -> bool {
        match &self.intent_filter {
            None => true,
            Some(f) => intent == f.as_str() || intent.starts_with(&format!("{}.", f)),
        }
    }
}

/// Per-topic state.
struct TopicState {
    pool: Arc<WorkerPool>,
    subscribers: Vec<Subscriber>,
}

/// The central message bus.
///
/// Manages per-topic worker pools and routes messages to subscribers.
pub struct TopicBus {
    /// Global configuration.
    config: RwLock<TopicBusConfig>,

    /// Per-topic overrides.
    topic_configs: DashMap<String, TopicConfig>,

    /// Per-topic state (pool + subscribers).
    topics: Arc<DashMap<String, TopicState>>,

    /// Global metrics.
    metrics: Arc<PostalMetrics>,

    /// Autoscaler thread.
    autoscaler: RwLock<Option<JoinHandle<()>>>,

    /// Stop flag.
    stop_flag: Arc<AtomicBool>,

    /// W2 return to sender. None = switch off = publish_routed exactly as before.
    returns: Option<Arc<ReturnOffice>>,
}

impl TopicBus {
    /// Create a new TopicBus with default configuration.
    pub fn new() -> Self {
        Self::with_config(TopicBusConfig::default())
    }

    /// Create a new TopicBus with custom configuration.
    pub fn with_config(config: TopicBusConfig) -> Self {
        let returns = if config.return_to_sender {
            Some(Arc::new(ReturnOffice::new(
                config.return_ring,
                config.return_rate_per_intent,
                config.return_global_rate,
            )))
        } else {
            None
        };
        let bus = Self {
            config: RwLock::new(config),
            topic_configs: DashMap::new(),
            topics: Arc::new(DashMap::new()),
            metrics: Arc::new(PostalMetrics::new()),
            autoscaler: RwLock::new(None),
            stop_flag: Arc::new(AtomicBool::new(false)),
            returns,
        };
        bus.start_autoscaler();
        bus
    }

    /// Subscribe to a topic.
    ///
    /// Returns a subscription ID that can be used to unsubscribe.
    pub fn subscribe<F>(
        &self,
        topic: impl Into<String>,
        handler: F,
        name: impl Into<String>,
        coalesce_ms: u64,
        max_batch: usize,
    ) -> usize
    where
        F: Fn(Envelope) + Send + Sync + 'static,
    {
        self.subscribe_filtered(topic, handler, name, coalesce_ms, max_batch, None)
    }

    /// subscribe(), but recording WHICH intent this subscriber wants so publish_routed
    /// can skip the ones that did not ask. intent_filter=None reproduces subscribe().
    pub fn subscribe_filtered<F>(
        &self,
        topic: impl Into<String>,
        handler: F,
        name: impl Into<String>,
        coalesce_ms: u64,
        max_batch: usize,
        intent_filter: Option<String>,
    ) -> usize
    where
        F: Fn(Envelope) + Send + Sync + 'static,
    {
        let topic = topic.into();
        let name = name.into();

        // Ensure topic exists
        self.ensure_topic(&topic);

        // Register handler with the pool
        let mut entry = self.topics.get_mut(&topic).unwrap();
        let state = entry.value_mut();

        let handler_id = state.pool.register_handler(handler);

        state.subscribers.push(Subscriber {
            handler_id,
            name,
            coalesce_ms,
            max_batch,
            intent_filter,
        });

        handler_id
    }

    /// Unsubscribe from a topic by handler ID.
    pub fn unsubscribe(&self, topic: &str, handler_id: usize) {
        if let Some(mut entry) = self.topics.get_mut(topic) {
            entry.value_mut().subscribers.retain(|s| s.handler_id != handler_id);
        }
    }

    /// Publish a message to a topic.
    ///
    /// The message is fanned out to all subscribers of the topic.
    pub fn publish(&self, envelope: Envelope) {
        let topic = envelope.topic().to_string();
        self.publish_routed(&topic, envelope);
    }

    /// Publish into POOL `pool_topic` while keeping the envelope's REAL intent for
    /// subscriber matching. Rust previously conflated the two -- Envelope::topic() just
    /// returns &self.intent -- so Python had to publish the BASE topic to avoid creating
    /// a pool per intent, which erased the information needed to route. Separating them
    /// keeps ~20 pools AND stops the 262-way fan-out.
    pub fn publish_routed(&self, pool_topic: &str, mut envelope: Envelope) {
        if self.stop_flag.load(Ordering::Relaxed) {
            return;
        }

        // Ensure envelope has required fields (Whisper's envelope enforcement)
        if envelope.intent.is_empty() {
            return;
        }

        let topic = pool_topic.to_string();

        // Ensure topic exists
        self.ensure_topic(&topic);

        // Get subscribers and enqueue for each
        let mut wanted = 0usize;
        if let Some(entry) = self.topics.get(&topic) {
            let state = entry.value();

            for subscriber in &state.subscribers {
                // 2026-08-28: only enqueue to subscribers that asked for THIS intent.
                // Previously every subscriber on the pool got a copy and _pool_dispatch
                // discarded the mismatches -- 261 of every 262 on the `fairy` topic.
                if !subscriber.wants(&envelope.intent) {
                    continue;
                }
                // TODO: Implement batching/coalescing for subscribers that want it
                // For now, direct enqueue
                state.pool.enqueue(envelope.clone(), subscriber.handler_id);
                wanted += 1;
            }
        }

        // W2 RETURN TO SENDER: nobody wanted it. Counted as returned, NOT as published. Runs after the
        // DashMap guard above is dropped: the return publish may ensure_topic(RETURN_POOL).
        if wanted == 0 {
            if let Some(office) = &self.returns {
                if let Some(back) = office.process(&envelope) {
                    self.publish_routed(RETURN_POOL, back);
                }
                return;
            }
        }

        self.metrics.inc_published();
    }

    /// W2: return-to-sender counters and ring. {"enabled": false} when the switch is off.
    pub fn returns_snapshot(&self) -> serde_json::Value {
        match &self.returns {
            Some(office) => office.snapshot(),
            None => serde_json::json!({"enabled": false}),
        }
    }

    /// Publish with a specific priority override.
    pub fn publish_priority(&self, mut envelope: Envelope, priority: Priority) {
        envelope.priority = priority;
        self.publish(envelope);
    }

    /// Configure a specific topic.
    pub fn configure_topic(&self, topic: impl Into<String>, config: TopicConfig) {
        let topic = topic.into();
        self.topic_configs.insert(topic.clone(), config.clone());

        // If topic already exists, update its pool config
        if let Some(mut entry) = self.topics.get_mut(&topic) {
            let state = entry.value_mut();
            // Apply new config to existing pool (limited - mainly for new subscribers)
            // Full reconfiguration would require restarting the pool
            let _ = state;
        }
    }

    /// Get global metrics snapshot.
    pub fn metrics(&self) -> MetricsSnapshot {
        // Aggregate depth AND the per-topic delivered/dropped counters. 2026-08-28:
        // inc_delivered()/inc_dropped() had no production call site, so both read 0
        // forever and throughput was structurally 0.0. Counting per-pool and summing
        // here keeps 375 worker threads off a single shared atomic.
        let mut total_depth: u64 = 0;
        let mut delivered: u64 = 0;
        let mut dropped: u64 = 0;
        for e in self.topics.iter() {
            let pool = &e.value().pool;
            total_depth += pool.queue_depth() as u64;
            delivered += pool.metrics.delivered.load(Ordering::Relaxed);
            dropped += pool.metrics.dropped.load(Ordering::Relaxed);
        }
        self.metrics.set_queue_depth(total_depth);
        self.metrics.set_delivered(delivered);
        self.metrics.set_dropped(dropped);

        self.metrics.snapshot()
    }

    /// Get per-topic stats.
    pub fn topic_stats(&self) -> Vec<TopicStats> {
        self.topics
            .iter()
            .map(|e| {
                let topic = e.key().clone();
                let state = e.value();
                TopicStats {
                    topic,
                    workers: state.pool.workers(),
                    queue_depth: state.pool.queue_depth(),
                    subscribers: state.subscribers.len(),
                    p95_ms: state.pool.metrics.p95_ms(),
                    // TRUE end-to-end wait, per topic -- this is what p95_ms was never
                    // measuring. Expect minutes-to-hours on a ceilinged topic.
                    queue_wait_p50_ms: state.pool.metrics.queue_wait_p50_ms(),
                    queue_wait_p95_ms: state.pool.metrics.queue_wait_p95_ms(),
                    queue_wait_max_ms: state.pool.metrics.queue_wait_max_ms(),
                    delivered: state.pool.metrics.delivered.load(Ordering::Relaxed),
                    dropped: state.pool.metrics.dropped.load(Ordering::Relaxed),
                }
            })
            .collect()
    }

    /// Shutdown the bus gracefully.
    pub fn shutdown(&self) {
        self.stop_flag.store(true, Ordering::SeqCst);

        // Stop autoscaler
        if let Some(thread) = self.autoscaler.write().take() {
            let _ = thread.join();
        }

        // Stop all topic pools
        for entry in self.topics.iter() {
            entry.value().pool.stop();
        }
    }

    /// Update global configuration.
    pub fn configure(&self, config: TopicBusConfig) {
        *self.config.write() = config;
    }

    // ---- Internal ----

    /// Ensure a topic exists, creating it if necessary.
    fn ensure_topic(&self, topic: &str) {
        if self.topics.contains_key(topic) {
            return;
        }

        let config = self.config.read();
        let topic_config = self.topic_configs.get(topic);

        let pool_config = WorkerPoolConfig {
            min_workers: topic_config
                .as_ref()
                .and_then(|c| c.min_workers)
                .unwrap_or(config.default_min_workers),
            max_workers: topic_config
                .as_ref()
                .and_then(|c| c.max_workers)
                .unwrap_or(config.default_max_workers),
            target_p95_ms: topic_config
                .as_ref()
                .and_then(|c| c.target_p95_ms)
                .unwrap_or(config.default_target_p95_ms),
            queue_capacity: topic_config
                .as_ref()
                .and_then(|c| c.max_queue)
                .unwrap_or(config.default_max_queue),
            autoscale_interval_ms: config.autoscale_interval_ms,
            ..Default::default()
        };

        let pool = Arc::new(WorkerPool::new(topic.to_string(), pool_config));
        pool.start();

        self.topics.insert(
            topic.to_string(),
            TopicState {
                pool,
                subscribers: Vec::new(),
            },
        );
    }

    /// Start the autoscaler background thread.
    fn start_autoscaler(&self) {
        let stop_flag = Arc::clone(&self.stop_flag);
        let topics = Arc::clone(&self.topics);
        let interval_ms = self.config.read().autoscale_interval_ms;

        let handle = thread::Builder::new()
            .name("postal-autoscaler".into())
            .spawn(move || {
                while !stop_flag.load(Ordering::Relaxed) {
                    let pressure = cpu_pressure();

                    for entry in topics.iter() {
                        entry.value().pool.autoscale(pressure);
                    }

                    thread::sleep(Duration::from_millis(interval_ms));
                }
            })
            .expect("Failed to spawn autoscaler");

        *self.autoscaler.write() = Some(handle);
    }
}

impl Default for TopicBus {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for TopicBus {
    fn drop(&mut self) {
        self.shutdown();
    }
}

/// Statistics for a single topic.
#[derive(Debug, Clone, serde::Serialize)]
pub struct TopicStats {
    pub topic: String,
    pub workers: usize,
    pub queue_depth: usize,
    pub subscribers: usize,
    /// HANDLER execution p95 (what this always was, despite the name).
    pub p95_ms: f64,
    /// TRUE queue wait, from enqueue to handler start (2026-08-28).
    pub queue_wait_p50_ms: f64,
    pub queue_wait_p95_ms: f64,
    pub queue_wait_max_ms: f64,
    pub delivered: u64,
    pub dropped: u64,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::AtomicUsize;

    #[test]
    fn test_topic_bus_basic() {
        let bus = TopicBus::new();

        let counter = Arc::new(AtomicUsize::new(0));
        let counter_clone = Arc::clone(&counter);

        bus.subscribe(
            "test",
            move |_| {
                counter_clone.fetch_add(1, Ordering::Relaxed);
            },
            "test-handler",
            0,
            1,
        );

        // Give the worker pool time to start
        thread::sleep(Duration::from_millis(50));

        // Publish some messages
        for i in 0..10 {
            let env = Envelope::new(format!("test.action.{}", i), serde_json::json!({}));
            bus.publish(env);
        }

        // Wait for processing (longer for CI environments)
        thread::sleep(Duration::from_millis(500));

        let count = counter.load(Ordering::Relaxed);
        assert!(count > 0, "Expected messages to be processed, got {}", count);

        bus.shutdown();
    }

    #[test]
    fn test_topic_stats() {
        let bus = TopicBus::new();

        bus.subscribe("fairy", |_| {}, "fairy-handler", 0, 1);
        bus.subscribe("memory", |_| {}, "memory-handler", 0, 1);

        let stats = bus.topic_stats();
        assert_eq!(stats.len(), 2);

        bus.shutdown();
    }

    // ── W2 return to sender ────────────────────────────────────────────────────────────
    fn bus_with_returns(on: bool) -> TopicBus {
        let mut cfg = TopicBusConfig::default();
        cfg.return_to_sender = on;
        cfg.return_ring = 16;
        cfg.return_rate_per_intent = 10;
        TopicBus::with_config(cfg)
    }

    fn letter(intent: &str, sender: &str) -> Envelope {
        Envelope::new(intent, serde_json::json!({"source": sender, "x": 1}))
    }

    #[test]
    fn w2_switch_default_is_off_and_only_exact_1_is_on() {
        // REVIEW_W2 F3: the default must be OFF when the variable is unset. Uses its own variable names
        // for the parsing cases so it cannot race other tests; only this test touches the real one.
        std::env::remove_var("AKASHIC_RETURN_TO_SENDER");
        assert!(!TopicBusConfig::default().return_to_sender);
        for (i, v) in ["", "0", " 1", "1 ", "true", "TRUE", "yes", "on"].iter().enumerate() {
            let name = format!("W2_TEST_FLAG_{}", i);
            std::env::set_var(&name, v);
            assert!(!env_flag(&name), "{:?} must be OFF", v);
            std::env::remove_var(&name);
        }
        std::env::set_var("W2_TEST_FLAG_ON", "1");
        assert!(env_flag("W2_TEST_FLAG_ON"));
        std::env::remove_var("W2_TEST_FLAG_ON");
        assert!(!env_flag("W2_TEST_FLAG_UNSET_NEVER_SET"));
    }

    #[test]
    fn w2_off_is_todays_behaviour() {
        let bus = bus_with_returns(false);
        bus.publish_routed("delta", letter("delta.two", "S"));
        assert_eq!(bus.metrics().messages_published, 1); // counted published, dropped: today
        assert_eq!(bus.returns_snapshot(), serde_json::json!({"enabled": false}));
        bus.shutdown();
    }

    #[test]
    fn w2_on_returns_to_sender_mailbox() {
        let bus = bus_with_returns(true);
        let got = Arc::new(AtomicUsize::new(0));
        let g = Arc::clone(&got);
        bus.subscribe_filtered(
            "postal",
            move |env| {
                if env.payload["intent"] == "delta.two" && env.payload["_returned"] == true {
                    g.fetch_add(1, Ordering::Relaxed);
                }
            },
            "mailbox-S",
            0,
            1,
            Some("postal.returned.S".to_string()),
        );
        thread::sleep(Duration::from_millis(50));
        bus.publish_routed("delta", letter("delta.two", "S"));
        for _ in 0..100 {
            if got.load(Ordering::Relaxed) == 1 {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        assert_eq!(got.load(Ordering::Relaxed), 1);
        let r = bus.returns_snapshot();
        assert_eq!(r["messages_returned"], 1);
        assert_eq!(r["returns_delivered"], 1);
        assert_eq!(r["return_undeliverable"], 0);
        assert_eq!(bus.metrics().messages_published, 1); // the delivered return, not the letter
        bus.shutdown();
    }

    #[test]
    fn w2_on_undeliverable_return_is_counted_not_looped() {
        let bus = bus_with_returns(true);
        bus.publish_routed("delta", letter("delta.two", "S"));
        let r = bus.returns_snapshot();
        assert_eq!(r["messages_returned"], 1);
        assert_eq!(r["return_undeliverable"], 1);
        assert_eq!(r["ring"].as_array().unwrap().len(), 2);
        assert_eq!(bus.metrics().messages_published, 0);
        bus.shutdown();
    }

    #[test]
    fn w2_on_no_sender_counted_not_sent() {
        let bus = bus_with_returns(true);
        bus.publish_routed("void", Envelope::new("void.x", serde_json::json!({})));
        let r = bus.returns_snapshot();
        assert_eq!(r["returns_no_sender"], 1);
        assert_eq!(r["returns_delivered"], 0);
        bus.shutdown();
    }

    /// Per-publish cost, no subscriber. cargo test --release -- --ignored --nocapture w2_cost
    #[test]
    #[ignore]
    fn w2_cost() {
        for on in [false, true] {
            let mut cfg = TopicBusConfig::default();
            cfg.return_to_sender = on;
            cfg.return_rate_per_intent = 1; // most returns suppressed: measures the office, not pools
            let bus = TopicBus::with_config(cfg);
            let n = 200_000u32;
            let env = letter("cost.none", "S");
            bus.publish_routed("cost", env.clone()); // create the pool outside the timing
            let t0 = std::time::Instant::now();
            for _ in 0..n {
                bus.publish_routed("cost", env.clone());
            }
            let ns = t0.elapsed().as_nanos() as f64 / n as f64;
            println!("W2 rust no-subscriber publish, return_to_sender={}: {:.0} ns/publish", on, ns);
            bus.shutdown();
        }
    }

    // ── W14 parity table (shared with python/tests_nous/test_w14_no_double.py) ─────────────
    /// For every row of w14_parity_table.json: make the TopicBus calls that lib.rs PyPostalCore.subscribe/publish
    /// forward to when _BaseTopicPostal runs with USING_RUST (pool = base topic, filter = full intent; lib.rs itself
    /// is not exercised here), publish the row's letter
    /// routed into its base pool, count REAL handler invocations per subscription, and assert the table's
    /// "rust" column. Runs with return_to_sender off and on. Prints the measured table:
    ///     cargo test w14_parity_table -- --nocapture
    #[test]
    fn w14_parity_table() {
        let table: serde_json::Value =
            serde_json::from_str(include_str!("../python/tests_nous/w14_parity_table.json")).unwrap();
        let rows = table["rows"].as_array().unwrap();
        let base = |s: &str| s.split('.').next().unwrap().to_string();
        for rts in [false, true] {
            let bus = bus_with_returns(rts);
            let mut counters: Vec<Vec<Arc<AtomicUsize>>> = Vec::new();
            let mut want_total = 0usize;
            for row in rows {
                let mut cs = Vec::new();
                for (i, sub) in row["subs"].as_array().unwrap().iter().enumerate() {
                    let sub = sub.as_str().unwrap();
                    let c = Arc::new(AtomicUsize::new(0));
                    let c2 = Arc::clone(&c);
                    bus.subscribe_filtered(
                        base(sub),
                        move |_| {
                            c2.fetch_add(1, Ordering::Relaxed);
                        },
                        format!("w14-{}-{}", row["id"].as_str().unwrap(), i),
                        0,
                        1,
                        Some(sub.to_string()),
                    );
                    cs.push(c);
                }
                for n in row["rust"].as_array().unwrap() {
                    want_total += n.as_u64().unwrap() as usize;
                }
                counters.push(cs);
            }
            thread::sleep(Duration::from_millis(50));
            for row in rows {
                let p = row["pub"].as_str().unwrap();
                bus.publish_routed(&base(p), Envelope::new(p, serde_json::json!({"row": row["id"]})));
            }
            let total = || counters.iter().flatten().map(|c| c.load(Ordering::Relaxed)).sum::<usize>();
            for _ in 0..300 {
                if total() >= want_total {
                    break;
                }
                thread::sleep(Duration::from_millis(10));
            }
            thread::sleep(Duration::from_millis(300)); // extra copies, if any, land here
            for (row, cs) in rows.iter().zip(&counters) {
                let got: Vec<u64> = cs.iter().map(|c| c.load(Ordering::Relaxed) as u64).collect();
                let want: Vec<u64> = row["rust"].as_array().unwrap().iter().map(|n| n.as_u64().unwrap()).collect();
                println!(
                    "W14 rust rts={} {} {:?} -> {} : {:?}",
                    rts as u8,
                    row["id"].as_str().unwrap(),
                    row["subs"],
                    row["pub"].as_str().unwrap(),
                    got
                );
                assert_eq!(got, want, "row {} rts={}", row["id"], rts);
            }
            bus.shutdown();
        }
    }
}
