//! glTF Avatar Loader - Load WoW-exported models and wire to consciousness
//!
//! This module loads glTF/GLB models (from wow.export or other sources) and
//! wires them to the Akashic consciousness system:
//!
//! - Chemistry → Animation blending (serotonin = relaxed idle, dopamine = excited)
//! - Emotion → Material emission/color shifts
//! - Activity Level → Animation speed
//!
//! # Usage
//!
//! ```rust
//! // In your startup system:
//! commands.spawn(GltfAvatarBundle {
//!     avatar: GltfAvatar {
//!         name: "Sourpatches".to_string(),
//!         model_path: "models/demon_hunter.glb".to_string(),
//!         ..default()
//!     },
//!     transform: Transform::from_xyz(0.0, 0.0, 0.0),
//!     ..default()
//! });
//! ```
//!
//! # WoW Export Workflow
//!
//! 1. Use wow.export to extract character model as GLB
//! 2. Place in `assets/models/` folder
//! 3. Spawn with GltfAvatarBundle
//! 4. System auto-wires to chemistry

use bevy::prelude::*;
use bevy::gltf::GltfAssetLabel;
use std::collections::HashMap;

use super::Mood;
use super::gm_editor::{Selectable, SelectableType};

pub struct GltfAvatarPlugin;

impl Plugin for GltfAvatarPlugin {
    fn build(&self, app: &mut App) {
        app
            .init_resource::<AvatarAnimationLibrary>()
            .add_event::<ChemistryUpdateEvent>()
            .add_event::<SpawnGltfAvatarEvent>()
            .add_systems(Startup, setup_avatar_assets)
            .add_systems(Update, (
                handle_spawn_avatar_events,
                setup_spawned_avatars,
                update_avatar_from_chemistry,
                blend_avatar_animations,
                update_avatar_emission,
                sync_avatar_transform,
            ));
    }
}

// ============================================================================
// Configuration
// ============================================================================

/// Default models for different avatar types
pub const DEFAULT_FAIRY_MODEL: &str = "models/fairy_default.glb";
pub const DEMON_HUNTER_MODEL: &str = "models/demon_hunter.glb";
pub const BLOODELF_DH_MODEL: &str = "models/bloodelf_demonhunter.glb";  // Petite Blood Elf DH

/// Animation names expected in glTF files (wow.export standard)
pub mod anim_names {
    pub const IDLE: &str = "Stand";
    pub const IDLE_RELAXED: &str = "StandRelaxed";
    pub const WALK: &str = "Walk";
    pub const RUN: &str = "Run";
    pub const EMOTE_WAVE: &str = "EmoteWave";
    pub const EMOTE_CHEER: &str = "EmoteCheer";
    pub const EMOTE_DANCE: &str = "EmoteDance";
    pub const EMOTE_CRY: &str = "EmoteCry";
    pub const COMBAT_READY: &str = "ReadyUnarmed";
    pub const CAST: &str = "CastDirected";
}

// ============================================================================
// Components
// ============================================================================

/// A glTF-based avatar that can be wired to the consciousness system
#[derive(Component, Debug)]
pub struct GltfAvatar {
    /// Display name
    pub name: String,
    /// Path to the glTF/GLB file (relative to assets/)
    pub model_path: String,
    /// Current chemistry state (updated from Postal)
    pub chemistry: AvatarChemistry,
    /// Current emotion derived from chemistry
    pub emotion: AvatarEmotion,
    /// Activity level (0.0 = dormant, 1.0 = very active)
    pub activity_level: f32,
    /// Home position in the sanctuary
    pub home_position: Vec3,
    /// Whether the model has been loaded and set up
    pub is_loaded: bool,
}

impl Default for GltfAvatar {
    fn default() -> Self {
        Self {
            name: "Unnamed".to_string(),
            model_path: DEFAULT_FAIRY_MODEL.to_string(),
            chemistry: AvatarChemistry::default(),
            emotion: AvatarEmotion::Content,
            activity_level: 0.5,
            home_position: Vec3::ZERO,
            is_loaded: false,
        }
    }
}

/// Chemistry state that drives avatar appearance and animation
#[derive(Debug, Clone, Default)]
pub struct AvatarChemistry {
    /// Serotonin: contentment, relaxation (0.0-1.0)
    pub serotonin: f32,
    /// Dopamine: excitement, reward anticipation (0.0-1.0)
    pub dopamine: f32,
    /// Cortisol: stress, alertness (0.0-1.0)
    pub cortisol: f32,
    /// Oxytocin: connection, warmth (0.0-1.0)
    pub oxytocin: f32,
    /// Adrenaline: energy, urgency (0.0-1.0)
    pub adrenaline: f32,
}

impl AvatarChemistry {
    /// Calculate overall arousal level (how "activated" the avatar is)
    pub fn arousal(&self) -> f32 {
        (self.dopamine * 0.3 + self.cortisol * 0.3 + self.adrenaline * 0.4).clamp(0.0, 1.0)
    }

    /// Calculate valence (positive vs negative feeling)
    pub fn valence(&self) -> f32 {
        let positive = self.serotonin * 0.4 + self.dopamine * 0.3 + self.oxytocin * 0.3;
        let negative = self.cortisol * 0.7 + self.adrenaline * 0.3;
        (positive - negative).clamp(-1.0, 1.0)
    }

    /// Derive emotion from chemistry state
    pub fn derive_emotion(&self) -> AvatarEmotion {
        let arousal = self.arousal();
        let valence = self.valence();

        if arousal < 0.3 {
            // Low arousal
            if valence > 0.2 {
                AvatarEmotion::Content
            } else if valence < -0.2 {
                AvatarEmotion::Sad
            } else {
                AvatarEmotion::Sleepy
            }
        } else if arousal > 0.7 {
            // High arousal
            if valence > 0.3 {
                AvatarEmotion::Happy
            } else if valence < -0.3 {
                AvatarEmotion::Anxious
            } else {
                AvatarEmotion::Curious
            }
        } else {
            // Medium arousal
            if self.oxytocin > 0.6 {
                AvatarEmotion::Loving
            } else if self.dopamine > 0.6 {
                AvatarEmotion::Curious
            } else {
                AvatarEmotion::Thoughtful
            }
        }
    }
}

/// Emotional state of an avatar (affects visuals and animation)
#[derive(Clone, Copy, Default, Debug, PartialEq)]
pub enum AvatarEmotion {
    #[default]
    Content,
    Happy,
    Curious,
    Thoughtful,
    Loving,
    Sad,
    Anxious,
    Sleepy,
}

impl AvatarEmotion {
    /// Get emission color modifier for this emotion
    pub fn emission_color(&self) -> Color {
        match self {
            AvatarEmotion::Content => Color::srgb(0.7, 0.6, 0.9),    // Soft purple
            AvatarEmotion::Happy => Color::srgb(1.0, 0.85, 0.4),     // Warm gold
            AvatarEmotion::Curious => Color::srgb(0.4, 0.9, 0.8),    // Cyan
            AvatarEmotion::Thoughtful => Color::srgb(0.5, 0.5, 0.9), // Blue
            AvatarEmotion::Loving => Color::srgb(1.0, 0.6, 0.7),     // Pink
            AvatarEmotion::Sad => Color::srgb(0.4, 0.4, 0.6),        // Muted blue
            AvatarEmotion::Anxious => Color::srgb(0.9, 0.5, 0.3),    // Orange
            AvatarEmotion::Sleepy => Color::srgb(0.5, 0.4, 0.6),     // Dim purple
        }
    }

    /// Get emission intensity for this emotion
    pub fn emission_intensity(&self) -> f32 {
        match self {
            AvatarEmotion::Content => 0.3,
            AvatarEmotion::Happy => 0.8,
            AvatarEmotion::Curious => 0.5,
            AvatarEmotion::Thoughtful => 0.2,
            AvatarEmotion::Loving => 0.6,
            AvatarEmotion::Sad => 0.1,
            AvatarEmotion::Anxious => 0.7,
            AvatarEmotion::Sleepy => 0.1,
        }
    }

    /// Get preferred animation for this emotion
    pub fn preferred_animation(&self) -> &'static str {
        match self {
            AvatarEmotion::Content => anim_names::IDLE,
            AvatarEmotion::Happy => anim_names::EMOTE_CHEER,
            AvatarEmotion::Curious => anim_names::IDLE,
            AvatarEmotion::Thoughtful => anim_names::IDLE_RELAXED,
            AvatarEmotion::Loving => anim_names::EMOTE_WAVE,
            AvatarEmotion::Sad => anim_names::EMOTE_CRY,
            AvatarEmotion::Anxious => anim_names::COMBAT_READY,
            AvatarEmotion::Sleepy => anim_names::IDLE_RELAXED,
        }
    }
}

/// Marker for the main mesh of an avatar (receives emission updates)
#[derive(Component)]
pub struct AvatarMesh {
    pub parent_avatar: Entity,
}

/// Animation state for a glTF avatar
#[derive(Component)]
pub struct AvatarAnimationState {
    /// Current animation clip handle
    pub current_clip: Option<Handle<AnimationClip>>,
    /// Target animation to blend towards
    pub target_clip: Option<Handle<AnimationClip>>,
    /// Blend weight (0.0 = current, 1.0 = target)
    pub blend_weight: f32,
    /// Animation speed multiplier
    pub speed: f32,
}

impl Default for AvatarAnimationState {
    fn default() -> Self {
        Self {
            current_clip: None,
            target_clip: None,
            blend_weight: 0.0,
            speed: 1.0,
        }
    }
}

/// Floating effect for fairy avatars
#[derive(Component)]
pub struct FloatEffect {
    pub phase: f32,
    pub amplitude: f32,
    pub speed: f32,
}

impl Default for FloatEffect {
    fn default() -> Self {
        Self {
            phase: 0.0,
            amplitude: 0.15,
            speed: 1.0,
        }
    }
}

// ============================================================================
// Resources
// ============================================================================

/// Library of loaded animation clips for avatars
#[derive(Resource, Default)]
pub struct AvatarAnimationLibrary {
    /// Map of model_path -> animation_name -> clip handle
    pub clips: HashMap<String, HashMap<String, Handle<AnimationClip>>>,
}

// ============================================================================
// Events
// ============================================================================

/// Event to update avatar chemistry from the Postal system
#[derive(Event)]
pub struct ChemistryUpdateEvent {
    pub avatar_name: String,
    pub chemistry: AvatarChemistry,
}

/// Event to spawn a new glTF avatar
#[derive(Event)]
pub struct SpawnGltfAvatarEvent {
    pub name: String,
    pub model_path: String,
    pub position: Vec3,
    pub initial_chemistry: Option<AvatarChemistry>,
}

// ============================================================================
// Bundle
// ============================================================================

/// Bundle for spawning a glTF avatar
#[derive(Bundle, Default)]
pub struct GltfAvatarBundle {
    pub avatar: GltfAvatar,
    pub transform: Transform,
    pub global_transform: GlobalTransform,
    pub visibility: Visibility,
    pub inherited_visibility: InheritedVisibility,
    pub view_visibility: ViewVisibility,
    pub float_effect: FloatEffect,
    pub animation_state: AvatarAnimationState,
}

// ============================================================================
// Systems
// ============================================================================

/// Load any avatar assets we need at startup
fn setup_avatar_assets(
    asset_server: Res<AssetServer>,
    mut animation_library: ResMut<AvatarAnimationLibrary>,
) {
    info!("glTF Avatar system initializing...");

    // Pre-load common model paths
    // The actual animation clips get loaded when we spawn avatars

    info!("glTF Avatar system ready");
}

/// Handle spawn avatar events
fn handle_spawn_avatar_events(
    mut commands: Commands,
    mut events: EventReader<SpawnGltfAvatarEvent>,
    asset_server: Res<AssetServer>,
) {
    for event in events.read() {
        info!("Spawning glTF avatar: {} from {}", event.name, event.model_path);

        // Clone the model path to owned String for 'static lifetime
        let model_path: String = event.model_path.clone();

        // Load the glTF scene
        let scene_handle: Handle<Scene> = asset_server.load(
            GltfAssetLabel::Scene(0).from_asset(model_path.clone())
        );

        // Spawn the avatar entity
        commands.spawn((
            GltfAvatar {
                name: event.name.clone(),
                model_path: event.model_path.clone(),
                chemistry: event.initial_chemistry.clone().unwrap_or_default(),
                home_position: event.position,
                is_loaded: false,
                ..default()
            },
            SceneRoot(scene_handle),
            Transform::from_translation(event.position),
            GlobalTransform::default(),
            Visibility::Visible,
            InheritedVisibility::default(),
            ViewVisibility::default(),
            FloatEffect {
                phase: rand::random::<f32>() * std::f32::consts::TAU,
                ..default()
            },
            AvatarAnimationState::default(),
            Selectable {
                name: event.name.clone(),
                entity_type: SelectableType::WakingMind,
            },
            Name::new(format!("GltfAvatar: {}", event.name)),
        ));
    }
}

/// Set up newly spawned avatars once their scenes are loaded
fn setup_spawned_avatars(
    mut commands: Commands,
    mut avatars: Query<(Entity, &mut GltfAvatar, &Children), Without<AvatarMesh>>,
    meshes: Query<(Entity, &Mesh3d)>,
    names: Query<&Name>,
) {
    for (avatar_entity, mut avatar, children) in avatars.iter_mut() {
        if avatar.is_loaded {
            continue;
        }

        // Check if scene is loaded by looking for mesh children
        let mut found_mesh = false;

        for &child in children.iter() {
            // Recursively search for meshes
            if let Ok((mesh_entity, _)) = meshes.get(child) {
                // Mark this mesh as belonging to the avatar
                commands.entity(mesh_entity).insert(AvatarMesh {
                    parent_avatar: avatar_entity,
                });
                found_mesh = true;
            }
        }

        if found_mesh {
            avatar.is_loaded = true;
            info!("Avatar '{}' scene loaded and set up", avatar.name);

            // Add a subtle point light
            commands.entity(avatar_entity).with_children(|parent| {
                parent.spawn((
                    PointLight {
                        color: avatar.emotion.emission_color(),
                        intensity: 3000.0 * avatar.emotion.emission_intensity(),
                        radius: 0.5,
                        shadows_enabled: false,
                        ..default()
                    },
                    Transform::from_xyz(0.0, 1.0, 0.0),
                    Name::new("Avatar Glow Light"),
                ));
            });
        }
    }
}

/// Update avatar state from chemistry events (from Postal system)
fn update_avatar_from_chemistry(
    mut events: EventReader<ChemistryUpdateEvent>,
    mut avatars: Query<&mut GltfAvatar>,
) {
    for event in events.read() {
        for mut avatar in avatars.iter_mut() {
            if avatar.name == event.avatar_name {
                avatar.chemistry = event.chemistry.clone();

                // Derive emotion from chemistry
                let new_emotion = avatar.chemistry.derive_emotion();
                if new_emotion != avatar.emotion {
                    info!(
                        "{}: emotion changed {:?} -> {:?} (arousal: {:.2}, valence: {:.2})",
                        avatar.name,
                        avatar.emotion,
                        new_emotion,
                        avatar.chemistry.arousal(),
                        avatar.chemistry.valence()
                    );
                    avatar.emotion = new_emotion;
                }

                // Update activity level from arousal
                avatar.activity_level = avatar.chemistry.arousal();
            }
        }
    }
}

/// Blend animations based on emotion state
fn blend_avatar_animations(
    time: Res<Time>,
    mut avatars: Query<(&GltfAvatar, &mut AvatarAnimationState)>,
    mut animation_players: Query<&mut AnimationPlayer>,
) {
    for (avatar, mut anim_state) in avatars.iter_mut() {
        // Adjust animation speed based on activity level
        anim_state.speed = 0.5 + avatar.activity_level * 1.0;

        // Update blend weight towards target
        if anim_state.target_clip.is_some() {
            anim_state.blend_weight = (anim_state.blend_weight + time.delta_secs() * 2.0).min(1.0);
        }
    }
}

/// Update avatar mesh emission based on emotion
fn update_avatar_emission(
    avatars: Query<&GltfAvatar>,
    avatar_meshes: Query<(&AvatarMesh, &MeshMaterial3d<StandardMaterial>)>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    for (avatar_mesh, material_handle) in avatar_meshes.iter() {
        if let Ok(avatar) = avatars.get(avatar_mesh.parent_avatar) {
            if let Some(material) = materials.get_mut(&material_handle.0) {
                // Apply emotion-based emission
                let color = avatar.emotion.emission_color();
                let intensity = avatar.emotion.emission_intensity();

                material.emissive = LinearRgba::new(
                    color.to_linear().red * intensity,
                    color.to_linear().green * intensity,
                    color.to_linear().blue * intensity,
                    1.0,
                );
            }
        }
    }
}

/// Sync avatar transform with floating effect
fn sync_avatar_transform(
    time: Res<Time>,
    mut avatars: Query<(&GltfAvatar, &mut Transform, &mut FloatEffect)>,
) {
    for (avatar, mut transform, mut float) in avatars.iter_mut() {
        // Update float phase
        float.phase += time.delta_secs() * float.speed * (0.5 + avatar.activity_level * 0.5);

        // Calculate float offset
        let y_offset = float.phase.sin() * float.amplitude;
        let x_offset = (float.phase * 0.7).sin() * float.amplitude * 0.3;
        let z_offset = (float.phase * 0.5).cos() * float.amplitude * 0.3;

        // Apply to transform
        transform.translation = avatar.home_position + Vec3::new(x_offset, y_offset, z_offset);
    }
}

// ============================================================================
// Helper Functions
// ============================================================================

/// Spawn a demo fairy avatar (for testing)
pub fn spawn_demo_fairy(
    commands: &mut Commands,
    asset_server: &Res<AssetServer>,
    name: &str,
    position: Vec3,
    model_path: Option<&str>,
) {
    let path: String = model_path.unwrap_or(DEFAULT_FAIRY_MODEL).to_string();

    let scene_handle: Handle<Scene> = asset_server.load(
        GltfAssetLabel::Scene(0).from_asset(path.clone())
    );

    commands.spawn((
        GltfAvatar {
            name: name.to_string(),
            model_path: path.clone(),
            home_position: position,
            ..default()
        },
        SceneRoot(scene_handle),
        Transform::from_translation(position),
        GlobalTransform::default(),
        Visibility::Visible,
        InheritedVisibility::default(),
        ViewVisibility::default(),
        FloatEffect {
            phase: rand::random::<f32>() * std::f32::consts::TAU,
            ..default()
        },
        AvatarAnimationState::default(),
        Selectable {
            name: name.to_string(),
            entity_type: SelectableType::WakingMind,
        },
        Name::new(format!("GltfAvatar: {}", name)),
    ));

    info!("Spawned demo fairy: {} at {:?}", name, position);
}

/// Create chemistry from simple emotion values (for testing)
pub fn chemistry_from_mood(mood: &str) -> AvatarChemistry {
    match mood.to_lowercase().as_str() {
        "happy" => AvatarChemistry {
            serotonin: 0.8,
            dopamine: 0.9,
            cortisol: 0.1,
            oxytocin: 0.6,
            adrenaline: 0.3,
        },
        "sad" => AvatarChemistry {
            serotonin: 0.2,
            dopamine: 0.1,
            cortisol: 0.5,
            oxytocin: 0.3,
            adrenaline: 0.1,
        },
        "anxious" => AvatarChemistry {
            serotonin: 0.2,
            dopamine: 0.3,
            cortisol: 0.9,
            oxytocin: 0.2,
            adrenaline: 0.7,
        },
        "curious" => AvatarChemistry {
            serotonin: 0.5,
            dopamine: 0.8,
            cortisol: 0.2,
            oxytocin: 0.4,
            adrenaline: 0.4,
        },
        "loving" => AvatarChemistry {
            serotonin: 0.7,
            dopamine: 0.6,
            cortisol: 0.1,
            oxytocin: 0.95,
            adrenaline: 0.2,
        },
        "sleepy" => AvatarChemistry {
            serotonin: 0.6,
            dopamine: 0.1,
            cortisol: 0.1,
            oxytocin: 0.4,
            adrenaline: 0.0,
        },
        _ => AvatarChemistry::default(),
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chemistry_arousal() {
        let calm = AvatarChemistry {
            serotonin: 0.8,
            dopamine: 0.2,
            cortisol: 0.1,
            oxytocin: 0.5,
            adrenaline: 0.1,
        };
        assert!(calm.arousal() < 0.3);

        let excited = AvatarChemistry {
            serotonin: 0.5,
            dopamine: 0.9,
            cortisol: 0.2,
            oxytocin: 0.5,
            adrenaline: 0.8,
        };
        assert!(excited.arousal() > 0.6);
    }

    #[test]
    fn test_chemistry_valence() {
        let positive = AvatarChemistry {
            serotonin: 0.9,
            dopamine: 0.8,
            cortisol: 0.1,
            oxytocin: 0.7,
            adrenaline: 0.2,
        };
        assert!(positive.valence() > 0.3);

        let negative = AvatarChemistry {
            serotonin: 0.1,
            dopamine: 0.1,
            cortisol: 0.9,
            oxytocin: 0.1,
            adrenaline: 0.3,
        };
        assert!(negative.valence() < -0.3);
    }

    #[test]
    fn test_emotion_derivation() {
        let happy_chem = chemistry_from_mood("happy");
        assert_eq!(happy_chem.derive_emotion(), AvatarEmotion::Happy);

        let sad_chem = chemistry_from_mood("sad");
        assert_eq!(sad_chem.derive_emotion(), AvatarEmotion::Sad);
    }
}
