//! Somatic Simulation - Complete tick-based body simulation
//!
//! This is the main entry point for non-Bevy usage (Python, standalone).
//! It bundles Heartbeat, Chemistry, BodyMap, and Affect into a single
//! tick-driven simulation.

use serde::{Deserialize, Serialize};

use super::{Affect, BodyMap, Chemistry, ChemicalType, Heartbeat, Mood};

/// Configuration for the simulation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimulationConfig {
    /// Global multiplier for chemistry decay rates
    pub decay_multiplier: f32,
    /// Maximum injection amount per event
    pub injection_cap: f32,
    /// Body region decay rate
    pub region_decay_rate: f32,
}

impl Default for SimulationConfig {
    fn default() -> Self {
        Self {
            decay_multiplier: 1.0,
            injection_cap: 0.3,
            region_decay_rate: 0.2,
        }
    }
}

/// A complete somatic body simulation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SomaticSimulation {
    /// The body's clock
    pub heartbeat: Heartbeat,
    /// Chemical state
    pub chemistry: Chemistry,
    /// Physical body sensations
    pub body_map: BodyMap,
    /// Derived emotional state
    pub affect: Affect,
    /// Configuration
    pub config: SimulationConfig,
    /// Total elapsed simulation time
    pub elapsed: f32,
}

impl Default for SomaticSimulation {
    fn default() -> Self {
        Self::new(72.0)
    }
}

impl SomaticSimulation {
    /// Create a new simulation with the given heart rate
    pub fn new(bpm: f32) -> Self {
        Self {
            heartbeat: Heartbeat::new(bpm),
            chemistry: Chemistry::balanced(),
            body_map: BodyMap::relaxed(),
            affect: Affect::default(),
            config: SimulationConfig::default(),
            elapsed: 0.0,
        }
    }

    /// Create with custom configuration
    pub fn with_config(bpm: f32, config: SimulationConfig) -> Self {
        Self {
            config,
            ..Self::new(bpm)
        }
    }

    /// Advance the simulation by dt seconds
    /// Returns a TickResult with events that occurred
    pub fn tick(&mut self, dt: f32) -> TickResult {
        self.elapsed += dt;

        // Tick heartbeat
        let beats = self.heartbeat.tick(dt);

        // Decay chemistry toward baseline
        self.chemistry.decay_all(dt, self.config.decay_multiplier);

        // Apply chemistry to body regions
        self.body_map.apply_chemistry(&self.chemistry, dt);

        // Decay body regions toward neutral
        self.body_map.decay_all(dt, self.config.region_decay_rate);

        // Update affect from chemistry
        let old_mood = self.affect.update_from_chemistry(&self.chemistry);
        let mood_changed = self.affect.mood != old_mood;

        TickResult {
            beats,
            mood_changed,
            old_mood: if mood_changed { Some(old_mood) } else { None },
            new_mood: self.affect.mood,
        }
    }

    /// Inject a chemical by type
    pub fn inject(&mut self, chemical: ChemicalType, amount: f32) {
        let capped = amount.min(self.config.injection_cap);
        self.chemistry.get_mut(chemical).inject(capped);
    }

    /// Inject a chemical by name (string)
    pub fn inject_by_name(&mut self, name: &str, amount: f32) -> Result<(), String> {
        let capped = amount.min(self.config.injection_cap);
        self.chemistry.inject_by_name(name, capped)
    }

    /// Set heart rate
    pub fn set_bpm(&mut self, bpm: f32) {
        self.heartbeat.set_bpm(bpm);
    }

    /// Get current mood as string
    pub fn mood(&self) -> &'static str {
        self.affect.mood.name()
    }

    /// Get current state as a serializable snapshot
    pub fn snapshot(&self) -> SimulationSnapshot {
        SimulationSnapshot {
            elapsed: self.elapsed,
            bpm: self.heartbeat.bpm,
            beat_counter: self.heartbeat.beat_counter,
            chemistry: self.chemistry.levels().into_iter().map(|(k, v)| (k.to_string(), v)).collect(),
            valence: self.affect.valence,
            arousal: self.affect.arousal,
            dominance: self.affect.dominance,
            mood: self.affect.mood.name().to_string(),
            chest_temp: self.body_map.chest.temperature,
            chest_tension: self.body_map.chest.tension,
            chest_activation: self.body_map.chest.activation,
        }
    }
}

/// Result of a simulation tick
#[derive(Debug, Clone)]
pub struct TickResult {
    /// Number of heartbeats that occurred
    pub beats: u64,
    /// Whether mood changed this tick
    pub mood_changed: bool,
    /// Previous mood (if changed)
    pub old_mood: Option<Mood>,
    /// Current mood
    pub new_mood: Mood,
}

/// A serializable snapshot of simulation state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimulationSnapshot {
    pub elapsed: f32,
    pub bpm: f32,
    pub beat_counter: u64,
    pub chemistry: Vec<(String, f32)>,
    pub valence: f32,
    pub arousal: f32,
    pub dominance: f32,
    pub mood: String,
    pub chest_temp: f32,
    pub chest_tension: f32,
    pub chest_activation: f32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simulation_tick() {
        let mut sim = SomaticSimulation::new(60.0);

        // Tick for 1 second - should get 1 beat
        let result = sim.tick(1.0);
        assert_eq!(result.beats, 1);
        assert_eq!(sim.heartbeat.beat_counter, 1);
    }

    #[test]
    fn test_injection_affects_mood() {
        let mut sim = SomaticSimulation::new(72.0);

        // Inject a lot of cortisol (stress)
        sim.inject(ChemicalType::Cortisol, 0.5);

        // Tick to process
        sim.tick(0.1);

        // Should have negative valence
        assert!(sim.affect.valence < 0.0);
    }
}
