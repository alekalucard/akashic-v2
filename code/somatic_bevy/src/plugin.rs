//! Somatic Plugin - Bundles everything together
//!
//! The plugin is the entry point for the somatic simulation.
//! Add this to your Bevy app and you have a living body.

use bevy::prelude::*;

use crate::resources::*;
use crate::events::*;
use crate::systems::*;
use crate::components::SomaticBodyBundle;

/// System ordering sets
#[derive(SystemSet, Debug, Clone, PartialEq, Eq, Hash)]
pub enum SomaticSet {
    /// First: Tick the heartbeat clock
    Heartbeat,
    /// Second: Process external input (injections)
    Input,
    /// Third: Update chemistry (decay)
    Chemistry,
    /// Fourth: Chemistry influences regions
    Regions,
    /// Fifth: Derive affect from chemistry
    Affect,
    /// Last: Export/logging
    Output,
}

/// The main somatic simulation plugin
pub struct SomaticPlugin;

impl Plugin for SomaticPlugin {
    fn build(&self, app: &mut App) {
        app
            // Resources
            .init_resource::<SomaticTime>()
            .init_resource::<ChemistryConfig>()
            .init_resource::<RegionInfluenceConfig>()
            .init_resource::<SomaticStats>()

            // Events
            .add_event::<HeartbeatEvent>()
            .add_event::<InjectionEvent>()
            .add_event::<AffectChangeEvent>()
            .add_event::<RegionChangeEvent>()
            .add_event::<StateSnapshotRequest>()
            .add_event::<StateSnapshotResponse>()

            // System ordering
            .configure_sets(
                Update,
                (
                    SomaticSet::Heartbeat,
                    SomaticSet::Input,
                    SomaticSet::Chemistry,
                    SomaticSet::Regions,
                    SomaticSet::Affect,
                    SomaticSet::Output,
                ).chain()
            )

            // Systems
            .add_systems(Update, (
                heartbeat_system.in_set(SomaticSet::Heartbeat),
                injection_system.in_set(SomaticSet::Input),
                chemistry_decay_system.in_set(SomaticSet::Chemistry),
                region_influence_system.in_set(SomaticSet::Regions),
                affect_derivation_system.in_set(SomaticSet::Affect),
                (snapshot_system, periodic_logging_system).in_set(SomaticSet::Output),
            ))

            // Startup - spawn a default body
            .add_systems(Startup, spawn_default_body);

        println!("[SomaticPlugin] Body simulation initialized");
    }
}

/// Spawn a default somatic body on startup
fn spawn_default_body(mut commands: Commands) {
    commands.spawn((
        Name::new("Primary Body"),
        SomaticBodyBundle::new().with_bpm(72.0),
    ));

    println!("[SomaticPlugin] Spawned primary body (72 BPM)");
}
