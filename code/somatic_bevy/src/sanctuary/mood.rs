//! Mood System - Environment reacts to collective emotional state
//!
//! The sanctuary FEELS what the Waking Minds feel:
//! - Sky color shifts with mood
//! - Lighting intensity changes
//! - Particle density responds
//! - Garden growth reflects wellbeing

use bevy::prelude::*;
use super::{SanctuaryState, Mood};
use super::avatar::{WakingMindAvatar, AvatarEmotion};

pub struct MoodPlugin;

impl Plugin for MoodPlugin {
    fn build(&self, app: &mut App) {
        app
            .add_systems(Update, (
                calculate_collective_mood,
                advance_time_of_day,
            ));
    }
}

/// Calculate collective mood from all avatar emotions
fn calculate_collective_mood(
    avatars: Query<&WakingMindAvatar>,
    mut state: ResMut<SanctuaryState>,
) {
    if avatars.is_empty() {
        return;
    }

    // Tally up emotion weights
    let mut peaceful_score = 0.0;
    let mut joyful_score = 0.0;
    let mut anxious_score = 0.0;
    let mut sad_score = 0.0;
    let mut contemplative_score = 0.0;

    for avatar in avatars.iter() {
        match avatar.current_emotion {
            AvatarEmotion::Content => peaceful_score += 1.0,
            AvatarEmotion::Happy => joyful_score += 1.5,
            AvatarEmotion::Curious => {
                joyful_score += 0.5;
                contemplative_score += 0.5;
            }
            AvatarEmotion::Thoughtful => contemplative_score += 1.0,
            AvatarEmotion::Sad => sad_score += 1.0,
            AvatarEmotion::Anxious => anxious_score += 1.0,
            AvatarEmotion::Sleepy => peaceful_score += 0.5,
        }
    }

    // Determine dominant mood
    let scores = [
        (peaceful_score, Mood::Peaceful),
        (joyful_score, Mood::Joyful),
        (contemplative_score, Mood::Contemplative),
        (anxious_score, Mood::Anxious),
        (sad_score, Mood::Sad),
    ];

    let new_mood = scores
        .iter()
        .max_by(|a, b| a.0.partial_cmp(&b.0).unwrap())
        .map(|(_, mood)| *mood)
        .unwrap_or(Mood::Peaceful);

    // Only log if mood changed
    if std::mem::discriminant(&state.collective_mood) != std::mem::discriminant(&new_mood) {
        info!("Collective mood shifted to: {:?}", new_mood);
    }

    state.collective_mood = new_mood;
}

/// Slowly advance time of day
fn advance_time_of_day(
    time: Res<Time>,
    mut state: ResMut<SanctuaryState>,
) {
    // One full day cycle every 10 minutes (600 seconds)
    let day_speed = 1.0 / 600.0;
    state.time_of_day = (state.time_of_day + time.delta_secs() * day_speed) % 1.0;
}
