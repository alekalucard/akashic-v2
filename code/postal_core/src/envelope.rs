//! Envelope - The fundamental message type in the postal system.
//!
//! Every message MUST have:
//! - intent: What action/topic this message represents
//! - t: Timestamp in milliseconds (when created)
//!
//! This follows the Whisper parallel_fabric envelope enforcement pattern.

use serde::{Deserialize, Serialize};
use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;

use crate::priority::Priority;

/// The core message type for all postal communication.
///
/// Envelopes are immutable once created. They flow through the system
/// via lock-free channels and are never modified in transit.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Envelope {
    /// REQUIRED: The intent/action this message represents.
    /// Examples: "fairy.boot", "memory.store", "wiring.scan"
    pub intent: String,

    /// REQUIRED: Creation timestamp in milliseconds since epoch.
    pub t: u64,

    /// The message payload (any JSON-serializable data).
    pub payload: serde_json::Value,

    /// Message priority for queue ordering.
    #[serde(default)]
    pub priority: Priority,

    /// Source identifier (fairy name, "mcp", "system", etc.)
    #[serde(default)]
    pub source: String,

    /// Optional reply-to topic for request/response patterns.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reply_to: Option<String>,

    /// Trace ID for distributed tracing.
    pub trace_id: String,

    /// Optional correlation ID for linking related messages.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub correlation_id: Option<String>,

    /// Time-to-live in seconds (0 = no expiry).
    #[serde(default)]
    pub ttl_sec: u32,

    /// Deduplication key for idempotent processing.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dedupe_key: Option<String>,
}

impl Envelope {
    /// Create a new envelope with required fields.
    pub fn new(intent: impl Into<String>, payload: serde_json::Value) -> Self {
        Self {
            intent: intent.into(),
            t: now_ms(),
            payload,
            priority: Priority::Normal,
            source: String::new(),
            reply_to: None,
            trace_id: Uuid::new_v4().to_string(),
            correlation_id: None,
            ttl_sec: 0,
            dedupe_key: None,
        }
    }

    /// Builder pattern: set priority
    pub fn with_priority(mut self, priority: Priority) -> Self {
        self.priority = priority;
        self
    }

    /// Builder pattern: set source
    pub fn with_source(mut self, source: impl Into<String>) -> Self {
        self.source = source.into();
        self
    }

    /// Builder pattern: set reply_to for request/response
    pub fn with_reply_to(mut self, reply_to: impl Into<String>) -> Self {
        self.reply_to = Some(reply_to.into());
        self
    }

    /// Builder pattern: set trace_id (usually auto-generated)
    pub fn with_trace_id(mut self, trace_id: impl Into<String>) -> Self {
        self.trace_id = trace_id.into();
        self
    }

    /// Builder pattern: set correlation_id
    pub fn with_correlation_id(mut self, correlation_id: impl Into<String>) -> Self {
        self.correlation_id = Some(correlation_id.into());
        self
    }

    /// Builder pattern: set TTL in seconds
    pub fn with_ttl(mut self, ttl_sec: u32) -> Self {
        self.ttl_sec = ttl_sec;
        self
    }

    /// Builder pattern: set dedupe key
    pub fn with_dedupe_key(mut self, key: impl Into<String>) -> Self {
        self.dedupe_key = Some(key.into());
        self
    }

    /// Check if this envelope has expired based on TTL.
    pub fn is_expired(&self) -> bool {
        if self.ttl_sec == 0 {
            return false;
        }
        let age_ms = now_ms().saturating_sub(self.t);
        let ttl_ms = (self.ttl_sec as u64) * 1000;
        age_ms > ttl_ms
    }

    /// Get the age of this envelope in milliseconds.
    pub fn age_ms(&self) -> u64 {
        now_ms().saturating_sub(self.t)
    }

    /// The full topic string (same as intent).
    /// Subscribe and publish must use the same key — no truncation.
    pub fn topic(&self) -> &str {
        &self.intent
    }
}

/// Get current time in milliseconds since Unix epoch.
pub fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_envelope_creation() {
        let env = Envelope::new("test.action", json!({"key": "value"}));
        assert_eq!(env.intent, "test.action");
        assert!(!env.trace_id.is_empty());
        assert!(env.t > 0);
    }

    #[test]
    fn test_envelope_builder() {
        let env = Envelope::new("fairy.boot", json!({}))
            .with_priority(Priority::High)
            .with_source("DirectoryFairy")
            .with_ttl(60);

        assert_eq!(env.priority, Priority::High);
        assert_eq!(env.source, "DirectoryFairy");
        assert_eq!(env.ttl_sec, 60);
    }

    #[test]
    fn test_topic_extraction() {
        let env = Envelope::new("fairy.boot.complete", json!({}));
        assert_eq!(env.topic(), "fairy");
    }

    #[test]
    fn test_expiry() {
        let mut env = Envelope::new("test", json!({}));
        env.ttl_sec = 0;
        assert!(!env.is_expired());

        // Can't easily test expiry without sleeping, but the logic is there
    }
}
