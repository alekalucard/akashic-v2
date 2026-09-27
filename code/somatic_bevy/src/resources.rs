//! ECS Resources - Global state accessible by all systems
//!
//! Resources are singletons. One per app.
//! This is the "configuration" and "tracking" of the body simulation.

use bevy::prelude::*;
use serde::{Deserialize, Serialize};

/// Global somatic time - tracks total beats and elapsed time
#[derive(Resource, Debug, Default, Serialize, Deserialize)]
pub struct SomaticTime {
    /// Total heartbeats across all bodies
    pub total_beats: u64,
    /// Total elapsed simulation seconds
    pub elapsed_seconds: f32,
}

/// Configuration for chemistry dynamics
#[derive(Resource, Debug, Clone, Serialize, Deserialize)]
pub struct ChemistryConfig {
    /// Global multiplier for all decay rates
    pub decay_multiplier: f32,
    /// Maximum amount from a single injection
    pub injection_cap: f32,
    /// Floor for all chemical levels
    pub min_level: f32,
    /// Ceiling for all chemical levels
    pub max_level: f32,
}

impl Default for ChemistryConfig {
    fn default() -> Self {
        Self {
            decay_multiplier: 1.0,
            injection_cap: 0.3,
            min_level: 0.0,
            max_level: 1.0,
        }
    }
}

/// Configuration for how chemistry influences body regions
#[derive(Resource, Debug, Clone, Serialize, Deserialize)]
pub struct RegionInfluenceConfig {
    /// How much stress chemicals (NOR/COR) affect chest activation
    pub stress_chest_factor: f32,
    /// How much calming chemicals (SER/GABA) reduce tension
    pub calm_tension_factor: f32,
    /// How much reward chemicals (DOP/END) increase warmth
    pub reward_warmth_factor: f32,
}

impl Default for RegionInfluenceConfig {
    fn default() -> Self {
        Self {
            stress_chest_factor: 0.5,
            calm_tension_factor: 0.3,
            reward_warmth_factor: 0.4,
        }
    }
}

/// Runtime statistics for monitoring
#[derive(Resource, Debug, Default, Serialize, Deserialize)]
pub struct SomaticStats {
    /// Number of injection events processed
    pub injections_processed: u64,
    /// Number of affect changes detected
    pub affect_changes: u64,
    /// Current tick rate (updates per second)
    pub tick_rate: f32,
    /// Last tick timestamp
    pub last_tick: f32,
}
