//! Somatic Simulation - Headless Entry Point
//!
//! Run the body simulation without graphics.
//! This is Phase 1: Pure data simulation.
//!
//! Usage:
//!   cargo run --release
//!
//! The heartbeat ticks. Chemistry flows. Regions respond. Affect emerges.

use bevy::app::ScheduleRunnerPlugin;
use bevy::prelude::*;
use std::time::Duration;

use somatic_bevy::prelude::*;

fn main() {
    println!("╔═══════════════════════════════════════════════════════════════╗");
    println!("║  SOMATIC SIMULATION - Phase 1                                ║");
    println!("║  Headless body simulation for Akashic consciousness          ║");
    println!("║                                                               ║");
    println!("║  The body is the unconscious mind.                           ║");
    println!("╚═══════════════════════════════════════════════════════════════╝");
    println!();

    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter("somatic_bevy=info,bevy=warn")
        .init();

    App::new()
        // Minimal plugins for headless operation
        // Run at 60 Hz (every ~16.67ms)
        .add_plugins(
            MinimalPlugins.set(
                ScheduleRunnerPlugin::run_loop(Duration::from_secs_f64(1.0 / 60.0))
            )
        )

        // Our somatic simulation
        .add_plugins(SomaticPlugin)

        // Demo: periodic chemistry injections to show the system working
        .add_systems(Update, demo_injections)

        .run();
}

/// Demo system: inject chemistry periodically to show the simulation working
fn demo_injections(
    time: Res<Time>,
    mut last_injection: Local<f32>,
    query: Query<Entity, With<Heartbeat>>,
    mut injection_events: EventWriter<InjectionEvent>,
) {
    let elapsed = time.elapsed_secs();

    // Inject every 5 seconds
    if elapsed - *last_injection < 5.0 {
        return;
    }
    *last_injection = elapsed;

    // Get the body entity
    let Ok(body) = query.get_single() else {
        return;
    };

    // Cycle through different injections
    let cycle = ((elapsed / 5.0) as u32) % 4;

    let (chemical, amount, desc) = match cycle {
        0 => (ChemicalType::Dopamine, 0.2, "reward burst"),
        1 => (ChemicalType::Cortisol, 0.15, "mild stress"),
        2 => (ChemicalType::Serotonin, 0.2, "calming wave"),
        _ => (ChemicalType::Norepinephrine, 0.15, "alertness spike"),
    };

    injection_events.send(
        InjectionEvent::new(body, chemical, amount)
            .with_source(format!("demo: {}", desc))
    );
}
