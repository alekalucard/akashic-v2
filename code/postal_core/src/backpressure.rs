//! Backpressure policies for handling queue overflow.
//!
//! When queues are full, we need a strategy. From Whisper's parallel_fabric:
//! - DropOldestLow: Drop oldest low-priority message to make room
//! - DropNewLow: Drop the new message if it's low priority
//! - Block: Block the publisher until space is available (not recommended for hot paths)

use serde::{Deserialize, Serialize};

/// Policy for handling queue overflow.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum BackpressurePolicy {
    /// Drop the oldest low-priority message to make room.
    /// This is the default - it preserves newer, higher-priority work.
    DropOldestLow,

    /// Drop the new message if it's low priority.
    /// Preserves existing work at the cost of new low-priority items.
    DropNewLow,

    /// Block the publisher until space is available.
    /// WARNING: Can cause cascading delays. Only use for critical paths
    /// where message loss is unacceptable.
    Block,

    /// Drop the new message regardless of priority.
    /// Nuclear option - use when system is overwhelmed.
    DropNew,
}

impl Default for BackpressurePolicy {
    fn default() -> Self {
        BackpressurePolicy::DropOldestLow
    }
}

impl BackpressurePolicy {
    /// Human-readable description of the policy.
    pub fn description(&self) -> &'static str {
        match self {
            BackpressurePolicy::DropOldestLow => {
                "Drop oldest low-priority message when full"
            }
            BackpressurePolicy::DropNewLow => {
                "Drop new message if low priority when full"
            }
            BackpressurePolicy::Block => {
                "Block publisher until space available (use with caution)"
            }
            BackpressurePolicy::DropNew => {
                "Drop new message regardless of priority when full"
            }
        }
    }
}

/// Result of attempting to enqueue under backpressure.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EnqueueResult {
    /// Message was enqueued successfully.
    Success,

    /// Message was enqueued after dropping an older message.
    SuccessAfterDrop { dropped_count: usize },

    /// Message was dropped due to backpressure.
    Dropped,

    /// Publisher would block (only with Block policy).
    WouldBlock,
}

impl EnqueueResult {
    /// Did the message get enqueued?
    pub fn is_success(&self) -> bool {
        matches!(self, EnqueueResult::Success | EnqueueResult::SuccessAfterDrop { .. })
    }

    /// Was any message dropped?
    pub fn had_drops(&self) -> bool {
        matches!(
            self,
            EnqueueResult::SuccessAfterDrop { .. } | EnqueueResult::Dropped
        )
    }
}

/// Statistics about backpressure events.
#[derive(Debug, Clone, Default)]
pub struct BackpressureStats {
    /// Total messages dropped due to backpressure.
    pub dropped_count: u64,

    /// Times we had to drop oldest to make room.
    pub drop_oldest_events: u64,

    /// Times we blocked waiting for space.
    pub block_events: u64,

    /// Times we successfully enqueued without issues.
    pub clean_enqueues: u64,
}

impl BackpressureStats {
    /// Total enqueue attempts.
    pub fn total_attempts(&self) -> u64 {
        self.clean_enqueues + self.dropped_count + self.drop_oldest_events + self.block_events
    }

    /// Percentage of messages that were dropped.
    pub fn drop_rate(&self) -> f64 {
        let total = self.total_attempts();
        if total == 0 {
            0.0
        } else {
            (self.dropped_count as f64) / (total as f64) * 100.0
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_policy() {
        assert_eq!(BackpressurePolicy::default(), BackpressurePolicy::DropOldestLow);
    }

    #[test]
    fn test_enqueue_result() {
        assert!(EnqueueResult::Success.is_success());
        assert!(EnqueueResult::SuccessAfterDrop { dropped_count: 1 }.is_success());
        assert!(!EnqueueResult::Dropped.is_success());
    }

    #[test]
    fn test_stats_drop_rate() {
        let stats = BackpressureStats {
            dropped_count: 10,
            clean_enqueues: 90,
            ..Default::default()
        };
        assert!((stats.drop_rate() - 10.0).abs() < 0.01);
    }
}
