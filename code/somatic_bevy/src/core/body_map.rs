//! Body Map - Where sensations live
//!
//! The body is mapped into 7 regions, each with temperature, tension, and activation.
//! This represents the felt sense of the body - where emotions are physically experienced.

use serde::{Deserialize, Serialize};

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

    pub fn name(&self) -> &'static str {
        match self {
            Self::Head => "head",
            Self::Chest => "chest",
            Self::Gut => "gut",
            Self::LeftArm => "left_arm",
            Self::RightArm => "right_arm",
            Self::LeftLeg => "left_leg",
            Self::RightLeg => "right_leg",
        }
    }
}

/// A body region with physical sensations
#[derive(Debug, Clone, Serialize, Deserialize)]
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

    /// Clamp all values to valid ranges
    pub fn clamp(&mut self) {
        self.temperature = self.temperature.clamp(-1.0, 1.0);
        self.tension = self.tension.clamp(0.0, 1.0);
        self.activation = self.activation.clamp(0.0, 1.0);
    }

    /// Decay toward neutral state
    pub fn decay(&mut self, dt: f32, rate: f32) {
        // Temperature decays toward 0
        self.temperature -= self.temperature * rate * dt;
        // Tension decays toward 0.3 (slight resting tension)
        self.tension += (0.3 - self.tension) * rate * dt;
        // Activation decays toward 0.5
        self.activation += (0.5 - self.activation) * rate * dt;
        self.clamp();
    }
}

/// Complete body map - all 7 regions
#[derive(Debug, Clone, Serialize, Deserialize)]
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

    /// Get a region by type
    pub fn get(&self, region_type: RegionType) -> &BodyRegion {
        match region_type {
            RegionType::Head => &self.head,
            RegionType::Chest => &self.chest,
            RegionType::Gut => &self.gut,
            RegionType::LeftArm => &self.left_arm,
            RegionType::RightArm => &self.right_arm,
            RegionType::LeftLeg => &self.left_leg,
            RegionType::RightLeg => &self.right_leg,
        }
    }

    /// Get a mutable region by type
    pub fn get_mut(&mut self, region_type: RegionType) -> &mut BodyRegion {
        match region_type {
            RegionType::Head => &mut self.head,
            RegionType::Chest => &mut self.chest,
            RegionType::Gut => &mut self.gut,
            RegionType::LeftArm => &mut self.left_arm,
            RegionType::RightArm => &mut self.right_arm,
            RegionType::LeftLeg => &mut self.left_leg,
            RegionType::RightLeg => &mut self.right_leg,
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

    /// Get all regions as immutable references
    pub fn all(&self) -> [&BodyRegion; 7] {
        [
            &self.head,
            &self.chest,
            &self.gut,
            &self.left_arm,
            &self.right_arm,
            &self.left_leg,
            &self.right_leg,
        ]
    }

    /// Decay all regions toward neutral
    pub fn decay_all(&mut self, dt: f32, rate: f32) {
        for region in self.all_mut() {
            region.decay(dt, rate);
        }
    }

    /// Apply chemistry influences to body regions
    pub fn apply_chemistry(&mut self, chemistry: &super::Chemistry, dt: f32) {
        // Stress chemicals affect chest
        let stress_level =
            (chemistry.norepinephrine.level + chemistry.cortisol.level) / 2.0;
        self.chest.activation += (stress_level - 0.5) * 0.5 * dt;

        // Calming chemicals reduce tension globally
        let calm_level = (chemistry.serotonin.level + chemistry.gaba.level) / 2.0;
        let tension_reduction = calm_level * 0.3 * dt;

        for region in self.all_mut() {
            region.tension = (region.tension - tension_reduction).max(0.1);
        }

        // Reward chemicals increase warmth in chest/gut
        let reward_level = (chemistry.dopamine.level + chemistry.endorphin.level) / 2.0;
        let warmth_delta = (reward_level - 0.5) * 0.4 * dt;

        self.chest.temperature += warmth_delta;
        self.gut.temperature += warmth_delta * 0.5;

        // Clamp everything
        for region in self.all_mut() {
            region.clamp();
        }
    }
}
