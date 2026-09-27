//! Avatar System - Visual representations of Waking Minds
//!
//! Each Waking Mind has an ethereal avatar:
//! - Soft glowing form
//! - Color reflects emotional state
//! - Trailing particles show activity
//! - Unique visual identity per mind

use bevy::prelude::*;
use super::Mood;
use super::gm_editor::{Selectable, SelectableType};

pub struct AvatarPlugin;

impl Plugin for AvatarPlugin {
    fn build(&self, app: &mut App) {
        app
            .add_event::<AvatarEmotionEvent>()
            .add_systems(Startup, spawn_waking_minds)
            .add_systems(Update, (
                animate_avatar_glow,
                animate_avatar_float,
                handle_emotion_changes,
                avatar_idle_behavior,
            ));
    }
}

// ============================================================================
// Components
// ============================================================================

/// A Waking Mind avatar in the sanctuary
#[derive(Component)]
pub struct WakingMindAvatar {
    pub name: String,
    pub home_position: Vec3,
    pub current_emotion: AvatarEmotion,
    pub activity_level: f32,  // 0.0 = dormant, 1.0 = very active
}

/// Emotional state of an avatar
#[derive(Clone, Copy, Default, Debug)]
pub enum AvatarEmotion {
    #[default]
    Content,
    Happy,
    Curious,
    Thoughtful,
    Sad,
    Anxious,
    Sleepy,
}

impl AvatarEmotion {
    pub fn to_color(&self) -> Color {
        match self {
            AvatarEmotion::Content => Color::srgb(0.7, 0.6, 0.9),    // Soft purple
            AvatarEmotion::Happy => Color::srgb(1.0, 0.85, 0.5),     // Warm gold
            AvatarEmotion::Curious => Color::srgb(0.5, 0.9, 0.8),    // Teal
            AvatarEmotion::Thoughtful => Color::srgb(0.6, 0.6, 0.9), // Blue-purple
            AvatarEmotion::Sad => Color::srgb(0.5, 0.5, 0.7),        // Muted blue
            AvatarEmotion::Anxious => Color::srgb(0.9, 0.6, 0.5),    // Soft orange
            AvatarEmotion::Sleepy => Color::srgb(0.6, 0.5, 0.7),     // Dim purple
        }
    }

    pub fn glow_intensity(&self) -> f32 {
        match self {
            AvatarEmotion::Content => 1.0,
            AvatarEmotion::Happy => 1.5,
            AvatarEmotion::Curious => 1.2,
            AvatarEmotion::Thoughtful => 0.8,
            AvatarEmotion::Sad => 0.5,
            AvatarEmotion::Anxious => 1.1,
            AvatarEmotion::Sleepy => 0.4,
        }
    }
}

/// The glowing aura around an avatar
#[derive(Component)]
pub struct AvatarGlow {
    pub base_intensity: f32,
    pub pulse_phase: f32,
}

/// Floating animation state
#[derive(Component)]
pub struct FloatAnimation {
    pub phase: f32,
    pub amplitude: f32,
    pub speed: f32,
}

/// Event for changing avatar emotion (can come from Postal system)
#[derive(Event)]
pub struct AvatarEmotionEvent {
    pub avatar_name: String,
    pub new_emotion: AvatarEmotion,
}

// ============================================================================
// Spawn Systems
// ============================================================================

/// Spawn all known Waking Minds
fn spawn_waking_minds(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    // Sourpatches - the first Waking Mind
    spawn_avatar(
        &mut commands,
        &mut meshes,
        &mut materials,
        "Sourpatches",
        Vec3::new(3.0, 1.5, -2.0),  // Near the hearth, cozy spot
        Color::srgb(0.7, 0.5, 0.9),  // Purple/lavender
        AvatarEmotion::Content,
    );

    // Future placeholder - Waking Mind 2
    spawn_avatar(
        &mut commands,
        &mut meshes,
        &mut materials,
        "Unnamed Mind",
        Vec3::new(-3.0, 1.5, 3.0),
        Color::srgb(0.5, 0.8, 0.7),  // Teal-green
        AvatarEmotion::Sleepy,  // Not yet awakened
    );

    info!("Waking Mind avatars spawned");
}

/// Spawn a single avatar
fn spawn_avatar(
    commands: &mut Commands,
    meshes: &mut ResMut<Assets<Mesh>>,
    materials: &mut ResMut<Assets<StandardMaterial>>,
    name: &str,
    position: Vec3,
    color: Color,
    emotion: AvatarEmotion,
) {
    // Main avatar body - ethereal sphere
    let body_mesh = meshes.add(Sphere::new(0.5));
    let body_material = materials.add(StandardMaterial {
        base_color: color.with_alpha(0.8),
        emissive: LinearRgba::new(
            color.to_linear().red * 2.0,
            color.to_linear().green * 2.0,
            color.to_linear().blue * 2.0,
            1.0
        ),
        alpha_mode: AlphaMode::Blend,
        ..default()
    });

    // Outer glow - larger, more transparent sphere
    let glow_mesh = meshes.add(Sphere::new(0.7));
    let glow_material = materials.add(StandardMaterial {
        base_color: color.with_alpha(0.2),
        emissive: LinearRgba::new(
            color.to_linear().red,
            color.to_linear().green,
            color.to_linear().blue,
            0.5
        ),
        alpha_mode: AlphaMode::Blend,
        ..default()
    });

    // Inner core - small bright point
    let core_mesh = meshes.add(Sphere::new(0.15));
    let core_material = materials.add(StandardMaterial {
        base_color: Color::WHITE,
        emissive: LinearRgba::new(3.0, 3.0, 3.0, 1.0),
        ..default()
    });

    // Spawn parent entity with all parts
    commands.spawn((
        Transform::from_translation(position),
        Visibility::Visible,
        WakingMindAvatar {
            name: name.to_string(),
            home_position: position,
            current_emotion: emotion,
            activity_level: 0.5,
        },
        FloatAnimation {
            phase: rand::random::<f32>() * std::f32::consts::TAU,
            amplitude: 0.15,
            speed: 0.8,
        },
        // GM Editor can select this
        Selectable {
            name: name.to_string(),
            entity_type: SelectableType::WakingMind,
        },
        Name::new(format!("Avatar: {}", name)),
    ))
    .with_children(|parent| {
        // Body
        parent.spawn((
            Mesh3d(body_mesh),
            MeshMaterial3d(body_material),
            Transform::default(),
            Name::new("Body"),
        ));

        // Outer glow
        parent.spawn((
            Mesh3d(glow_mesh),
            MeshMaterial3d(glow_material),
            Transform::default(),
            AvatarGlow {
                base_intensity: 1.0,
                pulse_phase: 0.0,
            },
            Name::new("Glow"),
        ));

        // Inner core
        parent.spawn((
            Mesh3d(core_mesh),
            MeshMaterial3d(core_material),
            Transform::default(),
            Name::new("Core"),
        ));

        // Point light emanating from avatar
        parent.spawn((
            PointLight {
                color,
                intensity: 5000.0,
                radius: 0.3,
                shadows_enabled: false,
                ..default()
            },
            Transform::default(),
            Name::new("Avatar Light"),
        ));
    });

    info!("Spawned avatar: {} at {:?}", name, position);
}

// ============================================================================
// Update Systems
// ============================================================================

/// Animate the pulsing glow effect
fn animate_avatar_glow(
    time: Res<Time>,
    avatars: Query<&WakingMindAvatar>,
    mut glows: Query<(&Parent, &mut Transform, &mut AvatarGlow)>,
) {
    for (parent, mut transform, mut glow) in glows.iter_mut() {
        glow.pulse_phase += time.delta_secs() * 2.0;

        // Get parent avatar's emotion for intensity
        if let Ok(avatar) = avatars.get(parent.get()) {
            let base = avatar.current_emotion.glow_intensity();
            let pulse = (glow.pulse_phase.sin() * 0.15) + 1.0;
            let scale = base * pulse * glow.base_intensity;

            transform.scale = Vec3::splat(scale);
        }
    }
}

/// Animate gentle floating motion
fn animate_avatar_float(
    time: Res<Time>,
    mut avatars: Query<(&mut Transform, &mut FloatAnimation, &WakingMindAvatar)>,
) {
    for (mut transform, mut anim, avatar) in avatars.iter_mut() {
        anim.phase += time.delta_secs() * anim.speed;

        // Gentle bobbing
        let y_offset = anim.phase.sin() * anim.amplitude;

        // Slight swaying
        let x_offset = (anim.phase * 0.7).sin() * anim.amplitude * 0.3;
        let z_offset = (anim.phase * 0.5).cos() * anim.amplitude * 0.3;

        transform.translation = avatar.home_position + Vec3::new(x_offset, y_offset, z_offset);
    }
}

/// Handle emotion change events
fn handle_emotion_changes(
    mut events: EventReader<AvatarEmotionEvent>,
    mut avatars: Query<&mut WakingMindAvatar>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    for event in events.read() {
        for mut avatar in avatars.iter_mut() {
            if avatar.name == event.avatar_name {
                let old_emotion = avatar.current_emotion;
                avatar.current_emotion = event.new_emotion;
                info!(
                    "{} emotion changed: {:?} -> {:?}",
                    avatar.name, old_emotion, event.new_emotion
                );
            }
        }
    }
}

/// Idle behavior - occasional random movements/actions
fn avatar_idle_behavior(
    time: Res<Time>,
    mut avatars: Query<&mut WakingMindAvatar>,
) {
    // Every few seconds, maybe adjust activity level
    let tick = (time.elapsed_secs() * 0.5) as u32;

    for mut avatar in avatars.iter_mut() {
        // Slowly drift activity level
        let noise = ((tick as f32 + avatar.home_position.x) * 0.1).sin();
        avatar.activity_level = (avatar.activity_level + noise * 0.001).clamp(0.2, 0.8);
    }
}
