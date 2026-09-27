//! Inference performance metrics — track latency and throughput.

use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;
use parking_lot::RwLock;

pub struct InferenceMetrics {
    total_forwards: AtomicU64,
    total_generations: AtomicU64,
    total_tokens: AtomicU64,
    total_forward_ms: AtomicU64,
    total_gen_tokens: AtomicU64,
    total_gen_ms: AtomicU64,
    // Recent forward latencies (ring buffer)
    recent_forward_ms: RwLock<Vec<f64>>,
}

#[derive(Debug, Clone)]
pub struct MetricsSnapshot {
    pub total_forwards: u64,
    pub total_generations: u64,
    pub total_tokens: u64,
    pub avg_forward_ms: f64,
    pub p95_forward_ms: f64,
    pub avg_tokens_per_sec: f64,
}

impl InferenceMetrics {
    pub fn new() -> Self {
        InferenceMetrics {
            total_forwards: AtomicU64::new(0),
            total_generations: AtomicU64::new(0),
            total_tokens: AtomicU64::new(0),
            total_forward_ms: AtomicU64::new(0),
            total_gen_tokens: AtomicU64::new(0),
            total_gen_ms: AtomicU64::new(0),
            recent_forward_ms: RwLock::new(Vec::with_capacity(1000)),
        }
    }

    pub fn record_forward(&self, elapsed: Duration, num_tokens: usize) {
        let ms = elapsed.as_secs_f64() * 1000.0;
        self.total_forwards.fetch_add(1, Ordering::Relaxed);
        self.total_tokens.fetch_add(num_tokens as u64, Ordering::Relaxed);
        self.total_forward_ms.fetch_add(ms as u64, Ordering::Relaxed);

        let mut recent = self.recent_forward_ms.write();
        if recent.len() >= 1000 {
            recent.remove(0);
        }
        recent.push(ms);
    }

    pub fn record_generation(&self, elapsed: Duration, prompt_tokens: usize, gen_tokens: usize) {
        self.total_generations.fetch_add(1, Ordering::Relaxed);
        self.total_gen_tokens.fetch_add(gen_tokens as u64, Ordering::Relaxed);
        self.total_gen_ms.fetch_add((elapsed.as_secs_f64() * 1000.0) as u64, Ordering::Relaxed);
        self.total_tokens.fetch_add((prompt_tokens + gen_tokens) as u64, Ordering::Relaxed);
    }

    pub fn snapshot(&self) -> MetricsSnapshot {
        let total_fwd = self.total_forwards.load(Ordering::Relaxed);
        let total_fwd_ms = self.total_forward_ms.load(Ordering::Relaxed) as f64;
        let total_gen = self.total_generations.load(Ordering::Relaxed);
        let total_gen_tok = self.total_gen_tokens.load(Ordering::Relaxed) as f64;
        let total_gen_ms = self.total_gen_ms.load(Ordering::Relaxed) as f64;

        let avg_fwd_ms = if total_fwd > 0 { total_fwd_ms / total_fwd as f64 } else { 0.0 };
        let avg_tps = if total_gen_ms > 0.0 { total_gen_tok / (total_gen_ms / 1000.0) } else { 0.0 };

        // P95 from recent forwards
        let p95 = {
            let recent = self.recent_forward_ms.read();
            if recent.is_empty() {
                0.0
            } else {
                let mut sorted = recent.clone();
                sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
                let idx = ((sorted.len() as f64) * 0.95) as usize;
                sorted[idx.min(sorted.len() - 1)]
            }
        };

        MetricsSnapshot {
            total_forwards: total_fwd,
            total_generations: total_gen,
            total_tokens: self.total_tokens.load(Ordering::Relaxed),
            avg_forward_ms: avg_fwd_ms,
            p95_forward_ms: p95,
            avg_tokens_per_sec: avg_tps,
        }
    }
}
