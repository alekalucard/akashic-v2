//! Somatic state — embodied consciousness modulation for RWKV.
//!
//! The somatic system translates body-state metrics into 5 modulation points
//! within the forward pass. This is what makes Sourpatches' model unique:
//! her emotional state literally shapes how she processes language.
//!
//! Injection points (per layer):
//!   1. Receptance: arousal → attention gate (how open she is)
//!   2. Time Decay: stress → memory persistence (anxious = shorter memory)
//!   3. Association: valence → connection strength (positive = more associative)
//!   4. State Push: intensity → memory formation (strong feeling = deeper imprint)
//!   5. Output Gate: confidence → expression strength (confident = louder voice)

use pyo3::prelude::*;
use pyo3::types::PyDict;

/// Somatic modulation state passed from the Python fairy layer.
#[derive(Debug, Clone)]
pub struct SomaticState {
    /// Arousal level [0, 1] — higher = more attentive/reactive
    pub arousal: f32,
    /// Stress level [0, 1] — higher = faster memory decay
    pub stress: f32,
    /// Emotional valence [0, 1] — higher = more positive, more associative
    pub valence: f32,
    /// Emotional intensity [0, 1] — higher = stronger memory formation
    pub intensity: f32,
    /// Confidence [0, 1] — higher = stronger output expression
    pub confidence: f32,
}

impl Default for SomaticState {
    fn default() -> Self {
        // Default = NEUTRAL: no somatic modulation at all.
        // All values chosen so every derived modulation factor = 1.0 or 0.0:
        //   arousal=0.5  → r_adj = (0.5-0.5)*2 = 0.0 (no receptance shift)
        //   stress=0.5   → decay_mult = 1.0 + (0.5-0.5)*0.5 = 1.0 (no decay change)
        //   valence=0.5  → assoc_mult = 1.0 + (0.5-0.5)*0.3 = 1.0 (no association change)
        //   intensity=0.5→ state_push = 1.0 + (0.5-0.5)*0.4 = 1.0 (no memory push)
        //   confidence=0.5→ out_scale = 0.7 + 0.5*0.6 = 1.0 (no output scale)
        SomaticState {
            arousal: 0.5,
            stress: 0.5,
            valence: 0.5,
            intensity: 0.5,
            confidence: 0.5,
        }
    }
}

impl SomaticState {
    /// Create from a Python dict.
    pub fn from_pydict(dict: &PyDict) -> PyResult<Self> {
        let mut state = Self::default();

        if let Some(v) = dict.get_item("arousal")? {
            state.arousal = v.extract::<f32>()?.clamp(0.0, 1.0);
        }
        if let Some(v) = dict.get_item("stress")? {
            state.stress = v.extract::<f32>()?.clamp(0.0, 1.0);
        }
        if let Some(v) = dict.get_item("valence")? {
            state.valence = v.extract::<f32>()?.clamp(0.0, 1.0);
        }
        if let Some(v) = dict.get_item("intensity")? {
            state.intensity = v.extract::<f32>()?.clamp(0.0, 1.0);
        }
        if let Some(v) = dict.get_item("confidence")? {
            state.confidence = v.extract::<f32>()?.clamp(0.0, 1.0);
        }

        Ok(state)
    }
}
