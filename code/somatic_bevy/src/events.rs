//! ECS Events - Decoupled communication between systems
//!
//! Events allow systems to communicate without tight coupling.
//! This is how external systems will interact with the body.

use bevy::prelude::*;
use serde::{Deserialize, Serialize};

use crate::components::{ChemicalType, Mood, RegionType};

/// Event: A heartbeat occurred
#[derive(Event, Debug, Clone, Serialize, Deserialize)]
pub struct HeartbeatEvent {
    /// Which beat number this is
    pub beat_number: u64,
    /// The entity that had the heartbeat
    pub entity: Entity,
    /// Current BPM at time of beat
    pub bpm: f32,
}

/// Event: Request to inject a chemical
#[derive(Event, Debug, Clone, Serialize, Deserialize)]
pub struct InjectionEvent {
    /// Target body entity
    pub target: Entity,
    /// Which chemical to inject
    pub chemical: ChemicalType,
    /// Amount to inject (will be clamped)
    pub amount: f32,
    /// Source of the injection (for logging)
    pub source: String,
}

impl InjectionEvent {
    pub fn new(target: Entity, chemical: ChemicalType, amount: f32) -> Self {
        Self {
            target,
            chemical,
            amount,
            source: "unknown".to_string(),
        }
    }

    pub fn with_source(mut self, source: impl Into<String>) -> Self {
        self.source = source.into();
        self
    }
}

/// Event: Affect state changed significantly
#[derive(Event, Debug, Clone, Serialize, Deserialize)]
pub struct AffectChangeEvent {
    /// Which body entity
    pub entity: Entity,
    /// Previous mood
    pub old_mood: Mood,
    /// New mood
    pub new_mood: Mood,
    /// Current valence
    pub valence: f32,
    /// Current arousal
    pub arousal: f32,
}

/// Event: Body region state changed
#[derive(Event, Debug, Clone, Serialize, Deserialize)]
pub struct RegionChangeEvent {
    /// Which body entity
    pub entity: Entity,
    /// Which region changed
    pub region: RegionType,
    /// Temperature change
    pub temperature_delta: f32,
    /// Tension change
    pub tension_delta: f32,
    /// Activation change
    pub activation_delta: f32,
}

/// Event: Request full body state snapshot (for export)
#[derive(Event, Debug, Clone)]
pub struct StateSnapshotRequest {
    /// Optional: specific entity, or None for all
    pub entity: Option<Entity>,
}

/// Event: Response with body state snapshot
#[derive(Event, Debug, Clone, Serialize, Deserialize)]
pub struct StateSnapshotResponse {
    pub entity: Entity,
    pub beat_count: u64,
    pub bpm: f32,
    pub chemistry: std::collections::HashMap<String, f32>,
    pub mood: Mood,
    pub valence: f32,
    pub arousal: f32,
}
