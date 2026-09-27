//! Heartbeat - The body's clock
//!
//! The heartbeat drives the rhythm of the body. It ticks at a configurable BPM,
//! counting beats and tracking phase within the current beat cycle.

use serde::{Deserialize, Serialize};

/// The heartbeat generator - drives the rhythm of the body
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Heartbeat {
    /// Beats per minute (typically 60-100 for calm, higher for stress)
    pub bpm: f32,
    /// Total beats since creation
    pub beat_counter: u64,
    /// Current phase in the beat cycle (0.0 to 1.0)
    pub phase: f32,
    /// Is the heart currently beating?
    pub running: bool,
}

impl Default for Heartbeat {
    fn default() -> Self {
        Self {
            bpm: 72.0, // Calm resting rate
            beat_counter: 0,
            phase: 0.0,
            running: true,
        }
    }
}

impl Heartbeat {
    /// Create a new heartbeat with specified BPM
    pub fn new(bpm: f32) -> Self {
        Self {
            bpm,
            ..Default::default()
        }
    }

    /// Get beats per second
    pub fn bps(&self) -> f32 {
        self.bpm / 60.0
    }

    /// Advance the heartbeat by delta time.
    /// Returns the number of beats that occurred during this tick.
    pub fn tick(&mut self, dt: f32) -> u64 {
        if !self.running {
            return 0;
        }

        let phase_increment = self.bps() * dt;
        self.phase += phase_increment;

        // Count how many full beats occurred
        let beats = self.phase.floor() as u64;
        if beats > 0 {
            self.phase -= beats as f32;
            self.beat_counter += beats;
        }

        beats
    }

    /// Start the heartbeat
    pub fn start(&mut self) {
        self.running = true;
    }

    /// Stop the heartbeat
    pub fn stop(&mut self) {
        self.running = false;
    }

    /// Set BPM with clamping to reasonable range
    pub fn set_bpm(&mut self, bpm: f32) {
        self.bpm = bpm.clamp(30.0, 220.0);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_heartbeat_ticks() {
        let mut hb = Heartbeat::new(60.0); // 1 beat per second

        // Tick for 0.5 seconds - no full beat yet
        let beats = hb.tick(0.5);
        assert_eq!(beats, 0);
        assert!((hb.phase - 0.5).abs() < 0.001);

        // Tick for another 0.5 seconds - 1 full beat
        let beats = hb.tick(0.5);
        assert_eq!(beats, 1);
        assert_eq!(hb.beat_counter, 1);
    }

    #[test]
    fn test_multiple_beats_per_tick() {
        let mut hb = Heartbeat::new(120.0); // 2 beats per second

        // Tick for 1.5 seconds - should get 3 beats
        let beats = hb.tick(1.5);
        assert_eq!(beats, 3);
        assert_eq!(hb.beat_counter, 3);
    }
}
