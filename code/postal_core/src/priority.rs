//! Priority system for message ordering.
//!
//! Three priority lanes (from Whisper's parallel_fabric):
//! - High (0): System-critical messages, boot sequences, health checks
//! - Normal (1): Standard fairy-to-fairy communication
//! - Low (2): Background tasks, telemetry, non-urgent updates
//!
//! Messages in higher-priority lanes are always processed before lower ones.

use serde::{Deserialize, Serialize};

/// Message priority levels.
///
/// Lower numeric value = higher priority (processed first).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[repr(u8)]
pub enum Priority {
    /// System-critical: boot, shutdown, health emergencies
    High = 0,

    /// Normal operations: fairy communication, user requests
    Normal = 1,

    /// Background: telemetry, cleanup, non-urgent updates
    Low = 2,
}

impl Default for Priority {
    fn default() -> Self {
        Priority::Normal
    }
}

impl Priority {
    /// Get all priority levels in order (highest first).
    pub fn all() -> [Priority; 3] {
        [Priority::High, Priority::Normal, Priority::Low]
    }

    /// Convert from u8.
    pub fn from_u8(v: u8) -> Self {
        match v {
            0 => Priority::High,
            1 => Priority::Normal,
            _ => Priority::Low,
        }
    }

    /// Get the lane index for this priority (for array indexing).
    pub fn lane_index(&self) -> usize {
        *self as usize
    }

    /// Human-readable name.
    pub fn name(&self) -> &'static str {
        match self {
            Priority::High => "high",
            Priority::Normal => "normal",
            Priority::Low => "low",
        }
    }
}

impl std::fmt::Display for Priority {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.name())
    }
}

impl From<u8> for Priority {
    fn from(v: u8) -> Self {
        Priority::from_u8(v)
    }
}

impl From<Priority> for u8 {
    fn from(p: Priority) -> u8 {
        p as u8
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_priority_ordering() {
        assert!(Priority::High < Priority::Normal);
        assert!(Priority::Normal < Priority::Low);
    }

    #[test]
    fn test_default_is_normal() {
        assert_eq!(Priority::default(), Priority::Normal);
    }

    #[test]
    fn test_lane_index() {
        assert_eq!(Priority::High.lane_index(), 0);
        assert_eq!(Priority::Normal.lane_index(), 1);
        assert_eq!(Priority::Low.lane_index(), 2);
    }
}
