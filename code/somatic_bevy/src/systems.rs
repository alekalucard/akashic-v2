//! ECS Systems - The logic that operates on components
//!
//! Systems are functions. They query components and mutate state.
//! This is the "how" of the body simulation.

use bevy::prelude::*;

use crate::components::*;
use crate::resources::*;
use crate::events::*;

// ============================================================================
// HEARTBEAT SYSTEM - The body's clock
// ============================================================================

/// Update heartbeat phase and emit beat events
pub fn heartbeat_system(
    time: Res<Time>,
    mut somatic_time: ResMut<SomaticTime>,
    mut query: Query<(Entity, &mut Heartbeat)>,
    mut beat_events: EventWriter<HeartbeatEvent>,
) {
    let delta = time.delta_secs();
    somatic_time.elapsed_seconds += delta;

    for (entity, mut heartbeat) in query.iter_mut() {
        if !heartbeat.running {
            continue;
        }

        // Update phase based on BPM
        let phase_increment = heartbeat.bps() * delta;
        heartbeat.phase += phase_increment;

        // Check if we crossed a beat threshold
        while heartbeat.phase >= 1.0 {
            heartbeat.phase -= 1.0;
            heartbeat.beat_counter += 1;
            somatic_time.total_beats += 1;

            beat_events.send(HeartbeatEvent {
                beat_number: heartbeat.beat_counter,
                entity,
                bpm: heartbeat.bpm,
            });

            // Console visibility every 10 beats
            if heartbeat.beat_counter % 10 == 0 {
                println!(
                    "[Somatic] <3 Beat #{} | BPM: {:.0} | Total: {}",
                    heartbeat.beat_counter,
                    heartbeat.bpm,
                    somatic_time.total_beats
                );
            }
        }
    }
}

// ============================================================================
// CHEMISTRY SYSTEMS - Injection and decay
// ============================================================================

/// Process injection events
pub fn injection_system(
    mut injection_events: EventReader<InjectionEvent>,
    mut query: Query<&mut Chemistry>,
    config: Res<ChemistryConfig>,
    mut stats: ResMut<SomaticStats>,
) {
    for event in injection_events.read() {
        if let Ok(mut chemistry) = query.get_mut(event.target) {
            let clamped_amount = event.amount.min(config.injection_cap);
            let chemical = chemistry.get_mut(event.chemical);
            chemical.inject(clamped_amount);

            stats.injections_processed += 1;

            println!(
                "[Somatic] +{:.2} {} (now {:.2}) via {}",
                clamped_amount,
                event.chemical.code(),
                chemical.level,
                event.source
            );
        }
    }
}

/// Decay all chemicals toward baseline
pub fn chemistry_decay_system(
    time: Res<Time>,
    config: Res<ChemistryConfig>,
    mut query: Query<&mut Chemistry>,
) {
    let delta = time.delta_secs();

    for mut chemistry in query.iter_mut() {
        chemistry.decay_all(delta, config.decay_multiplier);
    }
}

// ============================================================================
// REGION SYSTEM - Body influenced by chemistry
// ============================================================================

/// Update body regions based on chemistry state
pub fn region_influence_system(
    time: Res<Time>,
    config: Res<RegionInfluenceConfig>,
    mut query: Query<(&Chemistry, &mut BodyMap)>,
) {
    let delta = time.delta_secs();

    for (chemistry, mut body) in query.iter_mut() {
        // Stress chemicals affect chest
        let stress_level = (chemistry.norepinephrine.level + chemistry.cortisol.level) / 2.0;
        body.chest.activation += (stress_level - 0.5) * config.stress_chest_factor * delta;
        body.chest.activation = body.chest.activation.clamp(0.0, 1.0);

        // Calming chemicals reduce tension globally
        let calm_level = (chemistry.serotonin.level + chemistry.gaba.level) / 2.0;
        let tension_reduction = calm_level * config.calm_tension_factor * delta;

        for region in body.all_mut() {
            region.tension = (region.tension - tension_reduction).max(0.1);
        }

        // Reward chemicals increase warmth in chest/gut
        let reward_level = (chemistry.dopamine.level + chemistry.endorphin.level) / 2.0;
        let warmth_delta = (reward_level - 0.5) * config.reward_warmth_factor * delta;

        body.chest.temperature += warmth_delta;
        body.gut.temperature += warmth_delta * 0.5;

        body.chest.temperature = body.chest.temperature.clamp(-1.0, 1.0);
        body.gut.temperature = body.gut.temperature.clamp(-1.0, 1.0);
    }
}

// ============================================================================
// AFFECT SYSTEM - Derive emotional state from chemistry
// ============================================================================

/// Derive affect state from chemistry
pub fn affect_derivation_system(
    mut query: Query<(Entity, &Chemistry, &mut Affect)>,
    mut change_events: EventWriter<AffectChangeEvent>,
    mut stats: ResMut<SomaticStats>,
) {
    for (entity, chemistry, mut affect) in query.iter_mut() {
        let old_mood = affect.mood;

        // Calculate PAD dimensions from chemistry
        // Valence: positive chemicals - negative chemicals
        let positive = (chemistry.dopamine.level + chemistry.serotonin.level + chemistry.endorphin.level) / 3.0;
        let negative = chemistry.cortisol.level;
        affect.valence = (positive - negative).clamp(-1.0, 1.0);

        // Arousal: activating chemicals
        affect.arousal = (chemistry.norepinephrine.level + chemistry.dopamine.level) / 2.0;

        // Dominance: confidence chemicals vs stress
        let confidence = (chemistry.dopamine.level + chemistry.oxytocin.level) / 2.0;
        affect.dominance = (confidence - chemistry.cortisol.level * 0.5).clamp(0.0, 1.0);

        // Classify mood from PAD space
        affect.classify_mood();

        // Emit change event if mood shifted
        if affect.mood != old_mood {
            stats.affect_changes += 1;

            println!(
                "[Somatic] Mood shift: {:?} -> {:?} (v={:.2}, a={:.2})",
                old_mood, affect.mood, affect.valence, affect.arousal
            );

            change_events.send(AffectChangeEvent {
                entity,
                old_mood,
                new_mood: affect.mood,
                valence: affect.valence,
                arousal: affect.arousal,
            });
        }
    }
}

// ============================================================================
// SNAPSHOT SYSTEM - Export state for external consumption
// ============================================================================

/// Handle state snapshot requests
pub fn snapshot_system(
    mut requests: EventReader<StateSnapshotRequest>,
    mut responses: EventWriter<StateSnapshotResponse>,
    query: Query<(Entity, &Heartbeat, &Chemistry, &Affect)>,
) {
    for request in requests.read() {
        for (entity, heartbeat, chemistry, affect) in query.iter() {
            // If specific entity requested, filter
            if let Some(target) = request.entity {
                if entity != target {
                    continue;
                }
            }

            let mut chem_map = std::collections::HashMap::new();
            chem_map.insert("DOP".to_string(), chemistry.dopamine.level);
            chem_map.insert("SER".to_string(), chemistry.serotonin.level);
            chem_map.insert("NOR".to_string(), chemistry.norepinephrine.level);
            chem_map.insert("ACH".to_string(), chemistry.acetylcholine.level);
            chem_map.insert("OXY".to_string(), chemistry.oxytocin.level);
            chem_map.insert("COR".to_string(), chemistry.cortisol.level);
            chem_map.insert("GABA".to_string(), chemistry.gaba.level);
            chem_map.insert("END".to_string(), chemistry.endorphin.level);

            responses.send(StateSnapshotResponse {
                entity,
                beat_count: heartbeat.beat_counter,
                bpm: heartbeat.bpm,
                chemistry: chem_map,
                mood: affect.mood,
                valence: affect.valence,
                arousal: affect.arousal,
            });
        }
    }
}

// ============================================================================
// LOGGING/DEBUG SYSTEM - Periodic state output
// ============================================================================

/// Log body state periodically (every ~60 beats)
pub fn periodic_logging_system(
    mut beat_events: EventReader<HeartbeatEvent>,
    query: Query<(&Heartbeat, &Chemistry, &Affect, &BodyMap)>,
) {
    for event in beat_events.read() {
        // Log every 60 beats (~1 minute at 60bpm)
        if event.beat_number % 60 != 0 {
            continue;
        }

        if let Ok((heartbeat, chem, affect, body)) = query.get(event.entity) {
            println!("\n[Somatic] === Minute {} Status ===", event.beat_number / 60);
            println!(
                "  Heart: {} beats @ {:.0} BPM",
                heartbeat.beat_counter, heartbeat.bpm
            );
            println!(
                "  Chemistry: DOP={:.2} SER={:.2} NOR={:.2} COR={:.2}",
                chem.dopamine.level,
                chem.serotonin.level,
                chem.norepinephrine.level,
                chem.cortisol.level
            );
            println!(
                "  Affect: {:?} (v={:.2}, a={:.2}, d={:.2})",
                affect.mood, affect.valence, affect.arousal, affect.dominance
            );
            println!(
                "  Chest: temp={:.2}, tension={:.2}, activation={:.2}",
                body.chest.temperature, body.chest.tension, body.chest.activation
            );
            println!();
        }
    }
}
