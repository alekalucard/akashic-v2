//! Metrics collection for the postal system.
//!
//! Tracks:
//! - Message latencies (P50, P95, P99)
//! - Queue depths
//! - Throughput
//! - Backpressure events
//!
//! Uses HDR Histogram for high-precision latency tracking (like Whisper's P95).

use hdrhistogram::Histogram;
use parking_lot::RwLock;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

/// Global metrics for the postal system.
pub struct PostalMetrics {
    /// Latency histogram (microseconds).
    latency_us: RwLock<Histogram<u64>>,

    /// Total messages published.
    pub messages_published: AtomicU64,

    /// Total messages delivered.
    pub messages_delivered: AtomicU64,

    /// Total messages dropped.
    pub messages_dropped: AtomicU64,

    /// Current queue depth across all lanes.
    pub queue_depth: AtomicU64,

    /// Peak queue depth observed.
    pub peak_queue_depth: AtomicU64,

    /// When metrics collection started.
    started_at: Instant,
}

impl PostalMetrics {
    /// Create a new metrics collector.
    pub fn new() -> Self {
        Self {
            // HDR Histogram: 1us to 10 seconds, 3 significant figures
            latency_us: RwLock::new(
                Histogram::new_with_bounds(1, 10_000_000, 3)
                    .expect("Failed to create histogram")
            ),
            messages_published: AtomicU64::new(0),
            messages_delivered: AtomicU64::new(0),
            messages_dropped: AtomicU64::new(0),
            queue_depth: AtomicU64::new(0),
            peak_queue_depth: AtomicU64::new(0),
            started_at: Instant::now(),
        }
    }

    /// Record a message latency (in microseconds).
    pub fn record_latency_us(&self, latency_us: u64) {
        let mut hist = self.latency_us.write();
        let _ = hist.record(latency_us);
    }

    /// Record a message latency from a duration.
    pub fn record_latency(&self, latency: std::time::Duration) {
        self.record_latency_us(latency.as_micros() as u64);
    }

    /// Get P50 latency in milliseconds.
    pub fn p50_ms(&self) -> f64 {
        let hist = self.latency_us.read();
        hist.value_at_quantile(0.50) as f64 / 1000.0
    }

    /// Get P95 latency in milliseconds (Whisper's key metric).
    pub fn p95_ms(&self) -> f64 {
        let hist = self.latency_us.read();
        hist.value_at_quantile(0.95) as f64 / 1000.0
    }

    /// Get P99 latency in milliseconds.
    pub fn p99_ms(&self) -> f64 {
        let hist = self.latency_us.read();
        hist.value_at_quantile(0.99) as f64 / 1000.0
    }

    /// Get mean latency in milliseconds.
    pub fn mean_ms(&self) -> f64 {
        let hist = self.latency_us.read();
        hist.mean() / 1000.0
    }

    /// Get max latency in milliseconds.
    pub fn max_ms(&self) -> f64 {
        let hist = self.latency_us.read();
        hist.max() as f64 / 1000.0
    }

    /// Increment published count.
    pub fn inc_published(&self) {
        self.messages_published.fetch_add(1, Ordering::Relaxed);
    }

    /// Increment delivered count.
    pub fn inc_delivered(&self) {
        self.messages_delivered.fetch_add(1, Ordering::Relaxed);
    }

    /// Increment dropped count.
    pub fn inc_dropped(&self) {
        self.messages_dropped.fetch_add(1, Ordering::Relaxed);
    }

    /// Set delivered/dropped absolutely. TopicBus aggregates per-topic counters here at
    /// snapshot time rather than having 375 worker threads contend on one global atomic.
    pub fn set_delivered(&self, n: u64) {
        self.messages_delivered.store(n, Ordering::Relaxed);
    }

    /// See set_delivered.
    pub fn set_dropped(&self, n: u64) {
        self.messages_dropped.store(n, Ordering::Relaxed);
    }

    /// Update queue depth.
    pub fn set_queue_depth(&self, depth: u64) {
        self.queue_depth.store(depth, Ordering::Relaxed);

        // Track peak
        let current_peak = self.peak_queue_depth.load(Ordering::Relaxed);
        if depth > current_peak {
            self.peak_queue_depth.store(depth, Ordering::Relaxed);
        }
    }

    /// Get uptime in seconds.
    pub fn uptime_secs(&self) -> f64 {
        self.started_at.elapsed().as_secs_f64()
    }

    /// Get messages per second (throughput).
    pub fn throughput(&self) -> f64 {
        let delivered = self.messages_delivered.load(Ordering::Relaxed) as f64;
        let uptime = self.uptime_secs();
        if uptime > 0.0 {
            delivered / uptime
        } else {
            0.0
        }
    }

    /// Get drop rate as percentage.
    pub fn drop_rate_percent(&self) -> f64 {
        let published = self.messages_published.load(Ordering::Relaxed);
        let dropped = self.messages_dropped.load(Ordering::Relaxed);
        if published == 0 {
            0.0
        } else {
            (dropped as f64 / published as f64) * 100.0
        }
    }

    /// Get a snapshot of all metrics.
    pub fn snapshot(&self) -> MetricsSnapshot {
        MetricsSnapshot {
            p50_ms: self.p50_ms(),
            p95_ms: self.p95_ms(),
            p99_ms: self.p99_ms(),
            mean_ms: self.mean_ms(),
            max_ms: self.max_ms(),
            messages_published: self.messages_published.load(Ordering::Relaxed),
            messages_delivered: self.messages_delivered.load(Ordering::Relaxed),
            messages_dropped: self.messages_dropped.load(Ordering::Relaxed),
            queue_depth: self.queue_depth.load(Ordering::Relaxed),
            peak_queue_depth: self.peak_queue_depth.load(Ordering::Relaxed),
            uptime_secs: self.uptime_secs(),
            throughput: self.throughput(),
            drop_rate_percent: self.drop_rate_percent(),
        }
    }

    /// Reset all metrics (for testing or after major events).
    pub fn reset(&self) {
        let mut hist = self.latency_us.write();
        hist.reset();
        self.messages_published.store(0, Ordering::Relaxed);
        self.messages_delivered.store(0, Ordering::Relaxed);
        self.messages_dropped.store(0, Ordering::Relaxed);
        self.queue_depth.store(0, Ordering::Relaxed);
        self.peak_queue_depth.store(0, Ordering::Relaxed);
    }
}

impl Default for PostalMetrics {
    fn default() -> Self {
        Self::new()
    }
}

/// A point-in-time snapshot of postal metrics.
#[derive(Debug, Clone, serde::Serialize)]
pub struct MetricsSnapshot {
    pub p50_ms: f64,
    pub p95_ms: f64,
    pub p99_ms: f64,
    pub mean_ms: f64,
    pub max_ms: f64,
    pub messages_published: u64,
    pub messages_delivered: u64,
    pub messages_dropped: u64,
    pub queue_depth: u64,
    pub peak_queue_depth: u64,
    pub uptime_secs: f64,
    pub throughput: f64,
    pub drop_rate_percent: f64,
}

/// Per-topic metrics.
pub struct TopicMetrics {
    pub topic: String,
    pub latency_us: RwLock<Histogram<u64>>,
    pub messages: AtomicU64,
    pub queue_depth: AtomicU64,
    /// Messages actually handed to a handler. 2026-08-28: inc_delivered() on
    /// PostalMetrics had no production call site, so delivered read 0 forever and
    /// throughput (= delivered/uptime) was structurally 0.0.
    pub delivered: AtomicU64,
    /// Messages discarded on a full channel -- including low-lane evictions.
    /// The overflow path returned `false` with nothing counted or logged.
    pub dropped: AtomicU64,
    /// TRUE end-to-end wait, from enqueue to handler start. `queued_at` was captured
    /// and never read; p95_ms times handler execution only. Measured error on the
    /// memory topic: 30 ms reported vs ~5.4 HOURS actual.
    /// NOTE THE BOUNDS: latency_us spans 10 s, which a real wait would saturate --
    /// this one spans 24 h so it cannot lie the same way.
    pub queue_wait_us: RwLock<Histogram<u64>>,
}

impl TopicMetrics {
    pub fn new(topic: String) -> Self {
        Self {
            topic,
            latency_us: RwLock::new(
                Histogram::new_with_bounds(1, 10_000_000, 3)
                    .expect("Failed to create histogram")
            ),
            messages: AtomicU64::new(0),
            queue_depth: AtomicU64::new(0),
            delivered: AtomicU64::new(0),
            dropped: AtomicU64::new(0),
            queue_wait_us: RwLock::new(
                Histogram::new_with_bounds(1, 86_400_000_000, 3)
                    .expect("Failed to create queue-wait histogram")
            ),
        }
    }

    pub fn p95_ms(&self) -> f64 {
        let hist = self.latency_us.read();
        hist.value_at_quantile(0.95) as f64 / 1000.0
    }

    /// Record the TRUE wait a message spent queued before a handler saw it.
    pub fn record_queue_wait(&self, waited: std::time::Duration) {
        let us = waited.as_micros().min(86_400_000_000u128) as u64;
        let mut hist = self.queue_wait_us.write();
        let _ = hist.record(us.max(1));
    }

    pub fn queue_wait_p50_ms(&self) -> f64 {
        let hist = self.queue_wait_us.read();
        hist.value_at_quantile(0.50) as f64 / 1000.0
    }

    pub fn queue_wait_p95_ms(&self) -> f64 {
        let hist = self.queue_wait_us.read();
        hist.value_at_quantile(0.95) as f64 / 1000.0
    }

    pub fn queue_wait_max_ms(&self) -> f64 {
        let hist = self.queue_wait_us.read();
        hist.max() as f64 / 1000.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metrics_basic() {
        let metrics = PostalMetrics::new();

        // Record some latencies
        metrics.record_latency_us(1000);  // 1ms
        metrics.record_latency_us(2000);  // 2ms
        metrics.record_latency_us(5000);  // 5ms

        assert!(metrics.p50_ms() > 0.0);
        assert!(metrics.mean_ms() > 0.0);
    }

    #[test]
    fn test_throughput() {
        let metrics = PostalMetrics::new();

        for _ in 0..100 {
            metrics.inc_published();
            metrics.inc_delivered();
        }

        assert_eq!(metrics.messages_published.load(Ordering::Relaxed), 100);
        assert_eq!(metrics.messages_delivered.load(Ordering::Relaxed), 100);
    }

    #[test]
    fn test_drop_rate() {
        let metrics = PostalMetrics::new();

        for _ in 0..90 {
            metrics.inc_published();
            metrics.inc_delivered();
        }
        for _ in 0..10 {
            metrics.inc_published();
            metrics.inc_dropped();
        }

        let rate = metrics.drop_rate_percent();
        assert!((rate - 10.0).abs() < 0.1);
    }
}
