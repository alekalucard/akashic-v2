//! Chemistry - The 8 neurochemicals
//!
//! The body's chemical soup determines mood, motivation, and response to stimuli.
//! Each chemical has a baseline it decays toward, creating homeostasis.

use serde::{Deserialize, Serialize};

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

    /// Parse from string (case-insensitive)
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_uppercase().as_str() {
            "DOP" | "DOPAMINE" => Some(Self::Dopamine),
            "SER" | "SEROTONIN" => Some(Self::Serotonin),
            "NOR" | "NOREPINEPHRINE" => Some(Self::Norepinephrine),
            "ACH" | "ACETYLCHOLINE" => Some(Self::Acetylcholine),
            "OXY" | "OXYTOCIN" => Some(Self::Oxytocin),
            "COR" | "CORTISOL" => Some(Self::Cortisol),
            "GABA" => Some(Self::GABA),
            "END" | "ENDORPHIN" => Some(Self::Endorphin),
            _ => None,
        }
    }
}

/// A single neurochemical with its dynamics
#[derive(Debug, Clone, Serialize, Deserialize)]
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

    /// Distance from baseline (signed)
    pub fn deviation(&self) -> f32 {
        self.level - self.baseline
    }
}

/// Complete chemistry state - all 8 chemicals
#[derive(Debug, Clone, Serialize, Deserialize)]
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

    /// Inject a chemical by string name
    pub fn inject_by_name(&mut self, name: &str, amount: f32) -> Result<(), String> {
        match ChemicalType::from_str(name) {
            Some(chem_type) => {
                self.get_mut(chem_type).inject(amount);
                Ok(())
            }
            None => Err(format!("Unknown chemical: {}", name)),
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

    /// Get all levels as a vector of (code, level) pairs
    pub fn levels(&self) -> Vec<(&'static str, f32)> {
        vec![
            ("DOP", self.dopamine.level),
            ("SER", self.serotonin.level),
            ("NOR", self.norepinephrine.level),
            ("ACH", self.acetylcholine.level),
            ("OXY", self.oxytocin.level),
            ("COR", self.cortisol.level),
            ("GABA", self.gaba.level),
            ("END", self.endorphin.level),
        ]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_injection_clamping() {
        let mut chem = Neurochemical::new(ChemicalType::Dopamine, 0.5, 0.1);
        chem.inject(0.8); // Would be 1.3, should clamp to 1.0
        assert_eq!(chem.level, 1.0);
    }

    #[test]
    fn test_decay_toward_baseline() {
        let mut chem = Neurochemical::new(ChemicalType::Dopamine, 0.5, 1.0);
        chem.level = 1.0; // Above baseline

        // Decay for 1 second
        chem.decay(1.0, 1.0);

        // Should have moved toward 0.5
        assert!(chem.level < 1.0);
        assert!(chem.level > 0.5);
    }
}
