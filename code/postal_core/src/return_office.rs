//! ReturnOffice - return to sender (W2, 2026-10-29, Nous).
//!
//! Ace: a letter the postal system cannot deliver goes BACK TO THE SENDER, never into the void.
//! Before this, publish_routed() with no subscriber that wanted the intent still called
//! inc_published() and dropped the letter.
//!
//! SWITCH: AKASHIC_RETURN_TO_SENDER=1, read once when the TopicBusConfig is built. OFF when unset:
//! TopicBus holds no ReturnOffice and publish_routed() runs exactly as before.
//! Same rules as the Python fallback (_python_fallback.py `_ReturnOffice`):
//!   * every undeliverable letter: messages_returned += 1 and a ring entry (sender, intent, t, reason)
//!   * sender = payload["source"], else payload["_sender"], else Envelope.source
//!   * the returned letter goes to "postal.returned.<sender>" carrying the original payload
//!   * a returned letter that is itself undeliverable is counted, never returned again
//!   * delivery is rate-bounded per intent (AKASHIC_RETURN_RATE per second, floor RETURN_RATE_FLOOR);
//!     counting and the ring are never rate-bounded.

use parking_lot::Mutex;
use serde::Serialize;
use std::collections::{HashMap, VecDeque};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::envelope::Envelope;

pub const RETURN_PREFIX: &str = "postal.returned.";
pub const RETURN_POOL: &str = "postal";
pub const RETURN_RATE_FLOOR: u32 = 1;
pub const RETURN_RATE_DEFAULT: u32 = 10;
pub const RETURN_RING_DEFAULT: usize = 256;

#[derive(Debug, Clone, Serialize)]
pub struct ReturnRecord {
    pub sender: String,
    pub intent: String,
    pub t: u64,
    pub reason: &'static str,
}

#[derive(Debug, Default)]
struct Counters {
    returned: u64,
    delivered_back: u64,
    suppressed: u64,
    no_sender: u64,
    undeliverable: u64,
}

pub struct ReturnOffice {
    ring_size: usize,
    rate: u32,
    ring: Mutex<VecDeque<ReturnRecord>>,
    window: Mutex<HashMap<String, (u64, u32)>>,
    counters: Mutex<Counters>,
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

/// Who sent this letter. Payload keys first: the pyo3 publish() has no sender argument.
pub fn sender_of(env: &Envelope) -> String {
    for key in ["source", "_sender"] {
        if let Some(s) = env.payload.get(key).and_then(|v| v.as_str()) {
            if !s.is_empty() {
                return s.to_string();
            }
        }
    }
    env.source.clone()
}

/// A letter that is itself a return (never returned again).
pub fn is_return(env: &Envelope) -> bool {
    env.intent.starts_with(RETURN_PREFIX)
        || env.payload.get("_returned").and_then(|v| v.as_bool()) == Some(true)
}

impl ReturnOffice {
    pub fn new(ring_size: usize, rate_per_intent: u32) -> Self {
        Self {
            ring_size: ring_size.max(1),
            rate: rate_per_intent.max(RETURN_RATE_FLOOR),
            ring: Mutex::new(VecDeque::new()),
            window: Mutex::new(HashMap::new()),
            counters: Mutex::new(Counters::default()),
        }
    }

    pub fn note(&self, sender: &str, intent: &str, reason: &'static str) {
        {
            let mut ring = self.ring.lock();
            if ring.len() >= self.ring_size {
                ring.pop_front();
            }
            ring.push_back(ReturnRecord {
                sender: sender.to_string(),
                intent: intent.to_string(),
                t: now_ms(),
                reason,
            });
        }
        let mut c = self.counters.lock();
        if reason == "return_undeliverable" {
            c.undeliverable += 1;
        } else {
            c.returned += 1;
            if sender.is_empty() {
                c.no_sender += 1;
            }
        }
    }

    /// Per-intent, per-second bound on re-published returns. `now_s` is injectable for tests.
    pub fn may_send(&self, intent: &str, now_s: u64) -> bool {
        let ok = {
            let mut w = self.window.lock();
            if w.len() > 4096 && !w.contains_key(intent) {
                w.clear(); // bound the table itself
            }
            let e = w.entry(intent.to_string()).or_insert((now_s, 0));
            if e.0 != now_s {
                *e = (now_s, 0);
            }
            if e.1 < self.rate {
                e.1 += 1;
                true
            } else {
                false
            }
        };
        let mut c = self.counters.lock();
        if ok {
            c.delivered_back += 1;
        } else {
            c.suppressed += 1;
        }
        ok
    }

    /// The returned letter for `env`, or None when it must not be sent (no sender / over rate).
    /// Always counts and records. Never builds a return for a return.
    pub fn process(&self, env: &Envelope) -> Option<Envelope> {
        let sender = sender_of(env);
        if is_return(env) {
            self.note(&sender, &env.intent, "return_undeliverable");
            return None;
        }
        self.note(&sender, &env.intent, "no_subscriber");
        if sender.is_empty() || !self.may_send(&env.intent, now_ms() / 1000) {
            return None;
        }
        let payload = serde_json::json!({
            "_returned": true,
            "reason": "no_subscriber",
            "intent": env.intent,
            "sender": sender,
            "t": now_ms(),
            "letter": env.payload,
        });
        let mut back = Envelope::new(format!("{}{}", RETURN_PREFIX, sender), payload);
        back.priority = env.priority;
        Some(back)
    }

    pub fn snapshot(&self) -> serde_json::Value {
        let c = self.counters.lock();
        let ring: Vec<ReturnRecord> = self.ring.lock().iter().cloned().collect();
        serde_json::json!({
            "enabled": true,
            "messages_returned": c.returned,
            "returns_delivered": c.delivered_back,
            "returns_suppressed": c.suppressed,
            "returns_no_sender": c.no_sender,
            "return_undeliverable": c.undeliverable,
            "rate_per_intent": self.rate,
            "ring": ring,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn rate_floor_still_flows() {
        // a configured rate of 0 is clamped to the floor: one return per intent per second flows
        let o = ReturnOffice::new(8, 0);
        assert!(o.may_send("a.b", 100));
        assert!(!o.may_send("a.b", 100));
        assert!(o.may_send("c.d", 100)); // another intent is not starved by a flood on a.b
        assert!(o.may_send("a.b", 101)); // next second flows again
    }

    #[test]
    fn return_of_a_return_is_counted_not_returned() {
        let o = ReturnOffice::new(8, 10);
        let env = Envelope::new("postal.returned.X", json!({"_returned": true, "sender": "X"}));
        assert!(o.process(&env).is_none());
        let s = o.snapshot();
        assert_eq!(s["return_undeliverable"], 1);
        assert_eq!(s["messages_returned"], 0);
    }

    #[test]
    fn ring_is_bounded() {
        let o = ReturnOffice::new(3, 10);
        for i in 0..10 {
            o.note("S", &format!("t.{}", i), "no_subscriber");
        }
        let s = o.snapshot();
        assert_eq!(s["ring"].as_array().unwrap().len(), 3);
        assert_eq!(s["messages_returned"], 10);
        assert_eq!(s["ring"][2]["intent"], "t.9");
    }
}
