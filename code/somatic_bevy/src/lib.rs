//! Somatic Body Simulation
//!
//! A multi-target library for embodied consciousness simulation:
//! - `core` - Pure Rust simulation logic (always available)
//! - `bevy` - Bevy ECS integration (feature: bevy, default)
//! - `python` - PyO3 bindings (feature: python)
//!
//! "The body is the unconscious mind." - Candace Pert
//!
//! # Architecture
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                     Python (via PyO3)                            │
//! │   SomaticSimulation, Chemistry, Heartbeat, Affect               │
//! └─────────────────────────────────────────────────────────────────┘
//!                               │
//!                     PyO3 Bindings (--features python)
//!                               │
//!                               ▼
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                     Core Layer (always)                          │
//! │   Heartbeat, Chemistry, Affect, BodyMap, SomaticSimulation      │
//! └─────────────────────────────────────────────────────────────────┘
//!                               │
//!                     Component wrappers (--features bevy)
//!                               │
//!                               ▼
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                     Bevy Layer                                   │
//! │   HeartbeatComponent, SomaticPlugin, Systems                    │
//! └─────────────────────────────────────────────────────────────────┘
//! ```

// Core module - pure Rust, no dependencies
pub mod core;

// Bevy ECS integration (feature-gated)
#[cfg(feature = "bevy")]
pub mod components;
#[cfg(feature = "bevy")]
pub mod resources;
#[cfg(feature = "bevy")]
pub mod events;
#[cfg(feature = "bevy")]
pub mod systems;
#[cfg(feature = "bevy")]
pub mod plugin;

// Her fairy body (procedural, parametric). Only with the `sanctuary` feature (needs bevy_pbr);
// without it nothing below exists and the crate is unchanged.
#[cfg(feature = "sanctuary")]
pub mod fairy_body;
#[cfg(all(test, feature = "sanctuary"))]
mod fairy_body_tests;

// Python bindings (feature-gated)
#[cfg(feature = "python")]
mod python;

// Re-export core types at crate root
pub use core::*;

// Re-export Bevy types when available
#[cfg(feature = "bevy")]
pub use components::*;
#[cfg(feature = "bevy")]
pub use resources::*;
#[cfg(feature = "bevy")]
pub use events::*;
#[cfg(feature = "bevy")]
pub use plugin::SomaticPlugin;

/// Prelude for convenient imports (Bevy mode)
#[cfg(feature = "bevy")]
pub mod prelude {
    pub use crate::core::*;
    pub use crate::components::*;
    pub use crate::resources::*;
    pub use crate::events::*;
    pub use crate::systems::*;
    pub use crate::plugin::SomaticPlugin;
    pub use bevy::prelude::*;
}
