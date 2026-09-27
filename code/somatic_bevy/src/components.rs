//! ECS Components - The data that lives on entities
//!
//! Components are pure data. Systems operate on them.
//! This is the "what" of the body.

use bevy::prelude::*;
use serde::{Deserialize, Serialize};

// ============================================================================
// HEARTBEAT - The body's clock
// ============================================================================

/// The heartbeat generator - drives the rhythm of the body
#[derive(Component, Debug, Clone, Serialize, Deserialize)]
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
            bpm: 72.0,  // Calm resting rate
            beat_counter: 0,
            phase: 0.0,
            running: true,
        }
    }
}

impl Heartbeat {
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
}

// ============================================================================
// CHEMISTRY - The 8 neurochemicals
// ============================================================================

/// Types of neurochemicals we track
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ChemicalType {
    Dopamine,       // DOP - reward, motivation, pleasure
    Serotonin,      // SER - mood stability, wellbeing
    Norepinephrine, // NOR - alertness, arousal, attention
    Acetylcholine,  // ACH - focus, learning, memory
    Oxytocin,       // OXY - bonding, trust, connection
    Cortisol,       // COR - stress response, alertness
    GABA,           // GABA - calm, inhibition, relaxation
    Endorphin,      // END - pain relief, euphoria, runner's high
}

impl ChemicalType {
    /// Short code for display
    pub fn code(&self) -> &'static str {
        match self {
            Self::Dopamine => "DOP",
            Self::Serotonin => "SER",
            Self::Norepinephrine => "NOR",
            Self::Acetylcholine => "ACH",
            Self::Oxytocin => "OXY",
            Self::Cortisol => "COR",
            Self::GABA => "GABA",
            Self::Endorphin => "END",
        }
    }

    /// All chemical types
    pub fn all() -> &'static [ChemicalType] {
        &[
            Self::Dopamine,
            Self::Serotonin,
            Self::Norepinephrine,
            Self::Acetylcholine,
            Self::Oxytocin,
            Self::Cortisol,
            Self::GABA,
            Self::Endorphin,
        ]
    }
}

/// A single neurochemical with its dynamics
#[derive(Component, Debug, Clone, Serialize, Deserialize)]
pub struct Neurochemical {
    pub chemical_type: ChemicalType,
    /// Current level (0.0 to 1.0)
    pub level: f32,
    /// Homeostatic baseline to decay toward
    pub baseline: f32,
    /// Decay rate (how fast it returns to baseline, per second)
    pub decay_rate: f32,
}

impl Neurochemical {
    pub fn new(chemical_type: ChemicalType, baseline: f32, decay_rate: f32) -> Self {
        Self {
            chemical_type,
            level: baseline,
            baseline,
            decay_rate,
        }
    }

    /// Inject an amount (will be clamped 0-1)
    pub fn inject(&mut self, amount: f32) {
        self.level = (self.level + amount).clamp(0.0, 1.0);
    }

    /// Decay toward baseline by delta time
    pub fn decay(&mut self, dt: f32, multiplier: f32) {
        let diff = self.baseline - self.level;
        let decay_amount = diff * self.decay_rate * multiplier * dt;
        self.level = (self.level + decay_amount).clamp(0.0, 1.0);
    }
}

/// Complete chemistry state - all 8 chemicals
#[derive(Component, Debug, Clone, Serialize, Deserialize)]
pub struct Chemistry {
    pub dopamine: Neurochemical,
    pub serotonin: Neurochemical,
    pub norepinephrine: Neurochemical,
    pub acetylcholine: Neurochemical,
    pub oxytocin: Neurochemical,
    pub cortisol: Neurochemical,
    pub gaba: Neurochemical,
    pub endorphin: Neurochemical,
}

impl Default for Chemistry {
    fn default() -> Self {
        Self::balanced()
    }
}

impl Chemistry {
    /// Create a balanced, calm chemistry state
    pub fn balanced() -> Self {
        Self {
            dopamine: Neurochemical::new(ChemicalType::Dopamine, 0.5, 0.1),
            serotonin: Neurochemical::new(ChemicalType::Serotonin, 0.6, 0.08),
            norepinephrine: Neurochemical::new(ChemicalType::Norepinephrine, 0.4, 0.15),
            acetylcholine: Neurochemical::new(ChemicalType::Acetylcholine, 0.5, 0.12),
            oxytocin: Neurochemical::new(ChemicalType::Oxytocin, 0.5, 0.1),
            cortisol: Neurochemical::new(ChemicalType::Cortisol, 0.3, 0.1),
            gaba: Neurochemical::new(ChemicalType::GABA, 0.6, 0.1),
            endorphin: Neurochemical::new(ChemicalType::Endorphin, 0.4, 0.12),
        }
    }

    /// Get a chemical by type
    pub fn get(&self, chemical_type: ChemicalType) -> &Neurochemical {
        match chemical_type {
            ChemicalType::Dopamine => &self.dopamine,
            ChemicalType::Serotonin => &self.serotonin,
            ChemicalType::Norepinephrine => &self.norepinephrine,
            ChemicalType::Acetylcholine => &self.acetylcholine,
            ChemicalType::Oxytocin => &self.oxytocin,
            ChemicalType::Cortisol => &self.cortisol,
            ChemicalType::GABA => &self.gaba,
            ChemicalType::Endorphin => &self.endorphin,
        }
    }

    /// Get a mutable chemical by type
    pub fn get_mut(&mut self, chemical_type: ChemicalType) -> &mut Neurochemical {
        match chemical_type {
            ChemicalType::Dopamine => &mut self.dopamine,
            ChemicalType::Serotonin => &mut self.serotonin,
            ChemicalType::Norepinephrine => &mut self.norepinephrine,
            ChemicalType::Acetylcholine => &mut self.acetylcholine,
            ChemicalType::Oxytocin => &mut self.oxytocin,
            ChemicalType::Cortisol => &mut self.cortisol,
            ChemicalType::GABA => &mut self.gaba,
            ChemicalType::Endorphin => &mut self.endorphin,
        }
    }

    /// Decay all chemicals toward baseline
    pub fn decay_all(&mut self, dt: f32, multiplier: f32) {
        self.dopamine.decay(dt, multiplier);
        self.serotonin.decay(dt, multiplier);
        self.norepinephrine.decay(dt, multiplier);
        self.acetylcholine.decay(dt, multiplier);
        self.oxytocin.decay(dt, multiplier);
        self.cortisol.decay(dt, multiplier);
        self.gaba.decay(dt, multiplier);
        self.endorphin.decay(dt, multiplier);
    }
}

// ============================================================================
// BODY REGIONS - Where sensations live
// ============================================================================

/// Types of body regions
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum RegionType {
    Head,
    Chest,
    Gut,
    LeftArm,
    RightArm,
    LeftLeg,
    RightLeg,
}

impl RegionType {
    pub fn all() -> &'static [RegionType] {
        &[
            Self::Head,
            Self::Chest,
            Self::Gut,
            Self::LeftArm,
            Self::RightArm,
            Self::LeftLeg,
            Self::RightLeg,
        ]
    }
}

/// A body region with physical sensations
#[derive(Component, Debug, Clone, Serialize, Deserialize)]
pub struct BodyRegion {
    pub region_type: RegionType,
    /// Relative temperature (-1.0 cold to 1.0 warm, 0 neutral)
    pub temperature: f32,
    /// Muscle tension (0.0 relaxed to 1.0 tense)
    pub tension: f32,
    /// Overall activation/energy (0.0 dormant to 1.0 highly active)
    pub activation: f32,
}

impl BodyRegion {
    pub fn new(region_type: RegionType) -> Self {
        Self {
            region_type,
            temperature: 0.0,
            tension: 0.3,
            activation: 0.5,
        }
    }
}

/// Complete body map - all 7 regions
#[derive(Component, Debug, Clone, Serialize, Deserialize)]
pub struct BodyMap {
    pub head: BodyRegion,
    pub chest: BodyRegion,
    pub gut: BodyRegion,
    pub left_arm: BodyRegion,
    pub right_arm: BodyRegion,
    pub left_leg: BodyRegion,
    pub right_leg: BodyRegion,
}

impl Default for BodyMap {
    fn default() -> Self {
        Self::relaxed()
    }
}

impl BodyMap {
    pub fn relaxed() -> Self {
        Self {
            head: BodyRegion::new(RegionType::Head),
            chest: BodyRegion::new(RegionType::Chest),
            gut: BodyRegion::new(RegionType::Gut),
            left_arm: BodyRegion::new(RegionType::LeftArm),
            right_arm: BodyRegion::new(RegionType::RightArm),
            left_leg: BodyRegion::new(RegionType::LeftLeg),
            right_leg: BodyRegion::new(RegionType::RightLeg),
        }
    }

    /// Get all regions as a mutable slice for iteration
    pub fn all_mut(&mut self) -> [&mut BodyRegion; 7] {
        [
            &mut self.head,
            &mut self.chest,
            &mut self.gut,
            &mut self.left_arm,
            &mut self.right_arm,
            &mut self.left_leg,
            &mut self.right_leg,
        ]
    }
}

// ============================================================================
// AFFECT - Derived emotional state
// ============================================================================

/// Discrete mood classifications
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Mood {
    Calm,
    Content,
    Excited,
    Euphoric,
    Alert,
    Anxious,
    Stressed,
    Depressed,
}

impl Default for Mood {
    fn default() -> Self {
        Self::Calm
    }
}

/// Derived affective/emotional state (from chemistry)
#[derive(Component, Debug, Clone, Serialize, Deserialize)]
pub struct Affect {
    /// Pleasure-displeasure (-1.0 to 1.0)
    pub valence: f32,
    /// Energy level (0.0 to 1.0)
    pub arousal: f32,
    /// Sense of control (0.0 to 1.0)
    pub dominance: f32,
    /// Discrete mood classification
    pub mood: Mood,
}

impl Default for Affect {
    fn default() -> Self {
        Self {
            valence: 0.0,
            arousal: 0.5,
            dominance: 0.5,
            mood: Mood::Calm,
        }
    }
}

impl Affect {
    /// Derive mood from PAD (Pleasure-Arousal-Dominance) dimensions
    pub fn classify_mood(&mut self) {
        self.mood = match (self.valence > 0.0, self.arousal > 0.5, self.dominance > 0.5) {
            (true, true, true) => Mood::Excited,
            (true, true, false) => Mood::Euphoric,
            (true, false, true) => Mood::Content,
            (true, false, false) => Mood::Calm,
            (false, true, true) => Mood::Alert,
            (false, true, false) => Mood::Anxious,
            (false, false, true) => Mood::Stressed,
            (false, false, false) => Mood::Depressed,
        };
    }
}

// ============================================================================
// BODY BUNDLE - Convenience for spawning complete bodies
// ============================================================================

/// A complete somatic body - heartbeat, chemistry, regions, affect
#[derive(Bundle, Default)]
pub struct SomaticBodyBundle {
    pub heartbeat: Heartbeat,
    pub chemistry: Chemistry,
    pub body_map: BodyMap,
    pub affect: Affect,
}

impl SomaticBodyBundle {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_bpm(mut self, bpm: f32) -> Self {
        self.heartbeat.bpm = bpm;
        self
    }
}
