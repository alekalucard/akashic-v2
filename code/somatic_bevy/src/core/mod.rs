//! Core somatic types - Pure Rust, no framework dependencies
//!
//! This module contains the fundamental data structures and logic
//! for the somatic body simulation. No Bevy, no PyO3 - just Rust.
//!
//! Both the Bevy ECS layer and Python bindings wrap these types.

mod heartbeat;
mod chemistry;
mod body_map;
mod affect;
mod simulation;

pub use heartbeat::*;
pub use chemistry::*;
pub use body_map::*;
pub use affect::*;
pub use simulation::*;
