//! Worker pool for processing messages.
//!
//! Based on Whisper's per-topic worker pools with autoscaling.
//! Workers pull from priority queues and execute subscriber handlers.

use crossbeam::channel::{bounded, Receiver, Sender};
use parking_lot::RwLock;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};
use sysinfo::System;

use crate::envelope::Envelope;
use crate::metrics::TopicMetrics;
use crate::priority::Priority;

/// Configuration for a worker pool.
#[derive(Debug, Clone)]
pub struct WorkerPoolConfig {
    /// Minimum number of workers.
    pub min_workers: usize,
    /// Maximum number of workers.
    pub max_workers: usize,
    /// Target P95 latency in milliseconds.
    pub target_p95_ms: u64,
    /// Queue capacity per priority lane.
    pub queue_capacity: usize,
    /// How often to check for autoscaling (ms).
    pub autoscale_interval_ms: u64,
    /// CPU pressure threshold to avoid scaling up.
    pub cpu_hot_threshold: f32,
    /// CPU pressure threshold to consider scaling down.
    pub cpu_cool_threshold: f32,
}

impl Default for WorkerPoolConfig {
    fn default() -> Self {
        Self {
            min_workers: 1,
            max_workers: 16,
            target_p95_ms: 150,
            // FIX 2026-03-27 (Nous): Scaled back from 131K but up from 16K.
            // Base-topic collapsing means ~20 pools, each handling more traffic.
            // 65K → normal channel = 32K items. Handles burst fan-out.
            queue_capacity: 65536,
            autoscale_interval_ms: 250,
            cpu_hot_threshold: 0.85,
            cpu_cool_threshold: 0.55,
        }
    }
}

/// A task for a worker to execute.
pub struct WorkerTask {
    pub envelope: Envelope,
    pub handler_id: usize,
    pub queued_at: Instant,
}

/// A pool of workers for a specific topic.
pub struct WorkerPool {
    /// Topic name.
    pub topic: String,

    /// Configuration.
    config: WorkerPoolConfig,

    /// Three priority lanes (HIGH, NORMAL, LOW).
    tx_high: Sender<WorkerTask>,
    rx_high: Receiver<WorkerTask>,
    tx_normal: Sender<WorkerTask>,
    rx_normal: Receiver<WorkerTask>,
    tx_low: Sender<WorkerTask>,
    rx_low: Receiver<WorkerTask>,

    /// Worker thread handles.
    workers: RwLock<Vec<WorkerHandle>>,

    /// Stop signal.
    stop_flag: Arc<AtomicBool>,

    /// Current worker count.
    worker_count: AtomicUsize,

    /// Metrics for this pool.
    pub metrics: Arc<TopicMetrics>,

    /// Handler registry (handler_id -> handler function).
    /// Wrapped in Arc so workers can share access to dynamically added handlers.
    handlers: Arc<RwLock<Vec<Arc<dyn Fn(Envelope) + Send + Sync>>>>,

    /// Last autoscale check time.
    last_autoscale: RwLock<Instant>,
}

struct WorkerHandle {
    thread: Option<JoinHandle<()>>,
    stop_flag: Arc<AtomicBool>,
}

impl WorkerPool {
    /// Create a new worker pool for a topic.
    pub fn new(topic: impl Into<String>, config: WorkerPoolConfig) -> Self {
        let topic = topic.into();
        let cap = config.queue_capacity;

        let (tx_high, rx_high) = bounded(cap / 8);
        let (tx_normal, rx_normal) = bounded(cap / 2);
        let (tx_low, rx_low) = bounded(cap);

        Self {
            metrics: Arc::new(TopicMetrics::new(topic.clone())),
            topic,
            config,
            tx_high,
            rx_high,
            tx_normal,
            rx_normal,
            tx_low,
            rx_low,
            workers: RwLock::new(Vec::new()),
            stop_flag: Arc::new(AtomicBool::new(false)),
            worker_count: AtomicUsize::new(0),
            handlers: Arc::new(RwLock::new(Vec::new())),
            last_autoscale: RwLock::new(Instant::now()),
        }
    }

    /// Start the worker pool with minimum workers.
    pub fn start(&self) {
        self.scale_to(self.config.min_workers);
    }

    /// Stop all workers.
    pub fn stop(&self) {
        self.stop_flag.store(true, Ordering::SeqCst);
        let mut workers = self.workers.write();
        for handle in workers.drain(..) {
            if let Some(thread) = handle.thread {
                handle.stop_flag.store(true, Ordering::SeqCst);
                let _ = thread.join();
            }
        }
        self.worker_count.store(0, Ordering::Relaxed);
    }

    /// Register a handler and return its ID.
    pub fn register_handler<F>(&self, handler: F) -> usize
    where
        F: Fn(Envelope) + Send + Sync + 'static,
    {
        let mut handlers = self.handlers.write();
        let id = handlers.len();
        handlers.push(Arc::new(handler));
        id
    }

    /// Enqueue a task for a specific handler.
    pub fn enqueue(&self, envelope: Envelope, handler_id: usize) -> bool {
        let task = WorkerTask {
            envelope: envelope.clone(),
            handler_id,
            queued_at: Instant::now(),
        };

        let channel = match envelope.priority {
            Priority::High => &self.tx_high,
            Priority::Normal => &self.tx_normal,
            Priority::Low => &self.tx_low,
        };

        match channel.try_send(task) {
            Ok(_) => {
                self.update_queue_depth();
                true
            }
            Err(_) => {
                // Apply backpressure: try to drop from low queue.
                // 2026-08-28: every branch here discarded a message with NOTHING counted --
                // inc_dropped() had no production call site, so drop_rate_percent read 0.0
                // while four topics sat pinned at the 32,768 ceiling shedding traffic.
                if let Ok(_) = self.rx_low.try_recv() {
                    // Evicting a low-priority message IS a drop. Count the evicted one.
                    self.metrics.dropped.fetch_add(1, Ordering::Relaxed);
                    let retry_task = WorkerTask {
                        envelope,
                        handler_id,
                        queued_at: Instant::now(),
                    };
                    let accepted = channel.try_send(retry_task).is_ok();
                    if !accepted {
                        // retry lost too -- a second message gone
                        self.metrics.dropped.fetch_add(1, Ordering::Relaxed);
                    }
                    accepted
                } else {
                    // nothing evictable: this message is discarded outright
                    self.metrics.dropped.fetch_add(1, Ordering::Relaxed);
                    false
                }
            }
        }
    }

    /// Get current queue depth across all lanes.
    pub fn queue_depth(&self) -> usize {
        self.rx_high.len() + self.rx_normal.len() + self.rx_low.len()
    }

    /// Get current worker count.
    pub fn workers(&self) -> usize {
        self.worker_count.load(Ordering::Relaxed)
    }

    /// Check and apply autoscaling (called periodically).
    pub fn autoscale(&self, cpu_pressure: f32) {
        let mut last = self.last_autoscale.write();
        if last.elapsed().as_millis() < self.config.autoscale_interval_ms as u128 {
            return;
        }
        *last = Instant::now();
        drop(last);

        let queue_depth = self.queue_depth();
        let current = self.workers();
        let p95 = self.metrics.p95_ms();

        let is_hot = cpu_pressure > self.config.cpu_hot_threshold;
        let is_cool = cpu_pressure < self.config.cpu_cool_threshold;

        // Scale up if: queue is backing up OR latency is high, AND system isn't hot
        let should_scale_up = (queue_depth > current * 8 || p95 > self.config.target_p95_ms as f64)
            && !is_hot
            && current < self.config.max_workers;

        // Scale down if: queue is low AND latency is well under target, AND system is cool
        let should_scale_down = queue_depth < 2
            && p95 < (self.config.target_p95_ms as f64 / 2.0)
            && is_cool
            && current > self.config.min_workers;

        if should_scale_up {
            self.scale_to(current + 1);
        } else if should_scale_down {
            self.scale_to(current - 1);
        }
    }

    /// Scale to a specific number of workers.
    fn scale_to(&self, target: usize) {
        let target = target.clamp(self.config.min_workers, self.config.max_workers);
        let current = self.workers();

        if target > current {
            // Spawn more workers
            let mut workers = self.workers.write();
            for i in current..target {
                let stop = Arc::new(AtomicBool::new(false));
                let worker = self.spawn_worker(i, Arc::clone(&stop));
                workers.push(WorkerHandle {
                    thread: Some(worker),
                    stop_flag: stop,
                });
            }
            self.worker_count.store(target, Ordering::Relaxed);
        } else if target < current {
            // Signal workers to stop (they'll exit after current task)
            let mut workers = self.workers.write();
            for i in target..current {
                if let Some(handle) = workers.get(i) {
                    handle.stop_flag.store(true, Ordering::SeqCst);
                }
            }
            // Remove stopped workers
            workers.truncate(target);
            self.worker_count.store(target, Ordering::Relaxed);
        }
    }

    /// Spawn a single worker thread.
    fn spawn_worker(&self, idx: usize, stop_flag: Arc<AtomicBool>) -> JoinHandle<()> {
        let topic = self.topic.clone();
        let rx_high = self.rx_high.clone();
        let rx_normal = self.rx_normal.clone();
        let rx_low = self.rx_low.clone();
        let handlers = Arc::clone(&self.handlers);  // Share the Arc, not clone the Vec
        let metrics = Arc::clone(&self.metrics);

        thread::Builder::new()
            .name(format!("postal[{}]#{}", topic, idx))
            .spawn(move || {
                while !stop_flag.load(Ordering::Relaxed) {
                    // Priority order: HIGH -> NORMAL -> LOW
                    let task = rx_high
                        .try_recv()
                        .or_else(|_| rx_normal.try_recv())
                        .or_else(|_| rx_low.recv_timeout(Duration::from_millis(20)));

                    let task = match task {
                        Ok(t) => t,
                        Err(_) => continue,
                    };

                    // Execute the handler - read lock to get handler
                    let handler_opt = {
                        let guard = handlers.read();
                        guard.get(task.handler_id).cloned()
                    };

                    if let Some(handler) = handler_opt {
                        // TRUE queue wait. queued_at was captured at enqueue and, until
                        // 2026-08-28, never read anywhere in the crate -- so p95_ms below
                        // measured handler execution and excluded the wait entirely
                        // (memory topic: 30 ms reported, ~5.4 h actual).
                        metrics.record_queue_wait(task.queued_at.elapsed());

                        let start = Instant::now();
                        handler(task.envelope);
                        let latency = start.elapsed();

                        // Record HANDLER latency (unchanged -- the autoscaler reads this,
                        // and feeding it the true wait would pin every pool at max_workers)
                        {
                            let mut hist = metrics.latency_us.write();
                            let _ = hist.record(latency.as_micros() as u64);
                        }
                        metrics.delivered.fetch_add(1, Ordering::Relaxed);
                    }

                    metrics.messages.fetch_add(1, Ordering::Relaxed);
                }
            })
            .expect("Failed to spawn worker thread")
    }

    /// Update queue depth metric.
    fn update_queue_depth(&self) {
        let depth = self.queue_depth() as u64;
        self.metrics.queue_depth.store(depth, Ordering::Relaxed);
    }
}

impl Drop for WorkerPool {
    fn drop(&mut self) {
        self.stop();
    }
}

/// Get current CPU pressure (0.0 to 1.0).
pub fn cpu_pressure() -> f32 {
    let mut sys = System::new_all();
    sys.refresh_all();

    // Average load across all CPUs
    let cpus = sys.cpus();
    if cpus.is_empty() {
        return 0.0;
    }

    let total: f32 = cpus.iter().map(|c| c.cpu_usage()).sum();
    (total / cpus.len() as f32) / 100.0
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::AtomicUsize;

    #[test]
    fn test_worker_pool_basic() {
        let config = WorkerPoolConfig {
            min_workers: 2,
            max_workers: 4,
            ..Default::default()
        };
        let pool = WorkerPool::new("test", config);
        pool.start();

        assert_eq!(pool.workers(), 2);

        pool.stop();
        assert_eq!(pool.workers(), 0);
    }

    #[test]
    fn test_worker_pool_handler() {
        let pool = WorkerPool::new("test", WorkerPoolConfig::default());
        let counter = Arc::new(AtomicUsize::new(0));
        let counter_clone = Arc::clone(&counter);

        let handler_id = pool.register_handler(move |_env| {
            counter_clone.fetch_add(1, Ordering::Relaxed);
        });

        pool.start();

        // Send some messages
        for _ in 0..10 {
            let env = Envelope::new("test.action", serde_json::json!({}));
            pool.enqueue(env, handler_id);
        }

        // Wait for processing
        thread::sleep(Duration::from_millis(100));

        assert!(counter.load(Ordering::Relaxed) > 0);
        pool.stop();
    }
}
