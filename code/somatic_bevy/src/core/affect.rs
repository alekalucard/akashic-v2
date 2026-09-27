//! Affect - Derived emotional state
//!
//! Affect is the felt sense of emotion, derived from chemistry.
//! Uses the PAD model: Pleasure (valence), Arousal, Dominance.

use serde::{Deserialize, Serialize};

use super::Chemistry;

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

impl Mood {
    pub fn name(&self) -> &'static str {
        match self {
            Self::Calm => "calm",
            Self::Content => "content",
            Self::Excited => "excited",
            Self::Euphoric => "euphoric",
            Self::Alert => "alert",
            Self::Anxious => "anxious",
            Self::Stressed => "stressed",
            Self::Depressed => "depressed",
        }
    }

    /// Is this a positive mood?
    pub fn is_positive(&self) -> bool {
        matches!(self, Self::Calm | Self::Content | Self::Excited | Self::Euphoric)
    }

    /// Is this a high-arousal mood?
    pub fn is_aroused(&self) -> bool {
        matches!(self, Self::Excited | Self::Euphoric | Self::Alert | Self::Anxious)
    }
}

/// Derived affective/emotional state (from chemistry)
#[derive(Debug, Clone, Serialize, Deserialize)]
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

    /// Update affect from chemistry state
    pub fn update_from_chemistry(&mut self, chemistry: &Chemistry) -> Mood {
        let old_mood = self.mood;

        // Valence: positive chemicals - negative chemicals
        let positive = (chemistry.dopamine.level
            + chemistry.serotonin.level
            + chemistry.endorphin.level)
            / 3.0;
        let negative = chemistry.cortisol.level;
        self.valence = (positive - negative).clamp(-1.0, 1.0);

        // Arousal: activating chemicals
        self.arousal = (chemistry.norepinephrine.level + chemistry.dopamine.level) / 2.0;

        // Dominance: confidence chemicals vs stress
        let confidence = (chemistry.dopamine.level + chemistry.oxytocin.level) / 2.0;
        self.dominance = (confidence - chemistry.cortisol.level * 0.5).clamp(0.0, 1.0);

        // Classify discrete mood
        self.classify_mood();

        old_mood
    }

    /// Check if mood has changed from the given previous mood
    pub fn mood_changed(&self, previous: Mood) -> bool {
        self.mood != previous
    }

    /// Get a simple text description of current state
    pub fn description(&self) -> String {
        format!(
            "{} (valence={:.2}, arousal={:.2}, dominance={:.2})",
            self.mood.name(),
            self.valence,
            self.arousal,
            self.dominance
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mood_classification() {
        let mut affect = Affect::default();

        // High valence, high arousal, high dominance = Excited
        affect.valence = 0.5;
        affect.arousal = 0.7;
        affect.dominance = 0.7;
        affect.classify_mood();
        assert_eq!(affect.mood, Mood::Excited);

        // Low valence, high arousal, low dominance = Anxious
        affect.valence = -0.3;
        affect.arousal = 0.8;
        affect.dominance = 0.3;
        affect.classify_mood();
        assert_eq!(affect.mood, Mood::Anxious);
    }
}
