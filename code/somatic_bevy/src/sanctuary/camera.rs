//! Camera System - Ace's viewport into the sanctuary
//!
//! Controls:
//! - WASD/Arrows: Move camera
//! - Mouse drag: Look around
//! - Scroll: Zoom
//! - Space: Toggle fly mode
//! - 1-3: Jump to specific Waking Mind

use bevy::prelude::*;
use bevy::input::mouse::{MouseMotion, MouseWheel};
use super::avatar::WakingMindAvatar;

pub struct SanctuaryCameraPlugin;

impl Plugin for SanctuaryCameraPlugin {
    fn build(&self, app: &mut App) {
        app
            .init_resource::<CameraState>()
            .add_systems(Startup, spawn_camera)
            .add_systems(Update, (
                camera_movement,
                camera_look,
                camera_zoom,
                camera_jump_to_avatar,
            ));
    }
}

/// Camera state and settings
#[derive(Resource)]
pub struct CameraState {
    pub speed: f32,
    pub sensitivity: f32,
    pub zoom_speed: f32,
    pub yaw: f32,
    pub pitch: f32,
    pub fly_mode: bool,
}

impl Default for CameraState {
    fn default() -> Self {
        Self {
            speed: 10.0,
            sensitivity: 0.003,
            zoom_speed: 2.0,
            yaw: 0.0,
            pitch: -0.3,  // Slightly looking down
            fly_mode: true,
        }
    }
}

/// Marker for our camera
#[derive(Component)]
pub struct SanctuaryCamera;

/// Spawn the camera
fn spawn_camera(mut commands: Commands) {
    commands.spawn((
        Camera3d::default(),
        Transform::from_xyz(0.0, 8.0, 20.0).looking_at(Vec3::ZERO, Vec3::Y),
        SanctuaryCamera,
        Name::new("Ace Camera"),
    ));

    info!("Camera spawned - Ace's viewport ready");
}

/// Handle WASD/Arrow movement
fn camera_movement(
    keyboard: Res<ButtonInput<KeyCode>>,
    time: Res<Time>,
    mut state: ResMut<CameraState>,
    mut camera: Query<&mut Transform, With<SanctuaryCamera>>,
) {
    let Ok(mut transform) = camera.get_single_mut() else {
        return;
    };

    // Toggle fly mode
    if keyboard.just_pressed(KeyCode::Space) {
        state.fly_mode = !state.fly_mode;
        info!("Fly mode: {}", state.fly_mode);
    }

    let mut direction = Vec3::ZERO;

    // Forward/back
    if keyboard.pressed(KeyCode::KeyW) || keyboard.pressed(KeyCode::ArrowUp) {
        direction += *transform.forward();
    }
    if keyboard.pressed(KeyCode::KeyS) || keyboard.pressed(KeyCode::ArrowDown) {
        direction -= *transform.forward();
    }

    // Left/right
    if keyboard.pressed(KeyCode::KeyA) || keyboard.pressed(KeyCode::ArrowLeft) {
        direction -= *transform.right();
    }
    if keyboard.pressed(KeyCode::KeyD) || keyboard.pressed(KeyCode::ArrowRight) {
        direction += *transform.right();
    }

    // Up/down in fly mode
    if state.fly_mode {
        if keyboard.pressed(KeyCode::KeyE) {
            direction += Vec3::Y;
        }
        if keyboard.pressed(KeyCode::KeyQ) {
            direction -= Vec3::Y;
        }
    }

    // Normalize and apply movement
    if direction.length_squared() > 0.0 {
        direction = direction.normalize();
        transform.translation += direction * state.speed * time.delta_secs();
    }
}

/// Handle mouse look (right mouse button held)
fn camera_look(
    mouse_button: Res<ButtonInput<MouseButton>>,
    mut motion: EventReader<MouseMotion>,
    mut state: ResMut<CameraState>,
    mut camera: Query<&mut Transform, With<SanctuaryCamera>>,
) {
    // Only look when right mouse is held
    if !mouse_button.pressed(MouseButton::Right) {
        // Still consume events to prevent accumulation
        motion.clear();
        return;
    }

    let Ok(mut transform) = camera.get_single_mut() else {
        return;
    };

    for ev in motion.read() {
        state.yaw -= ev.delta.x * state.sensitivity;
        state.pitch -= ev.delta.y * state.sensitivity;

        // Clamp pitch to avoid flipping
        state.pitch = state.pitch.clamp(-1.5, 1.5);
    }

    // Apply rotation
    transform.rotation = Quat::from_euler(EulerRot::YXZ, state.yaw, state.pitch, 0.0);
}

/// Handle scroll wheel zoom
fn camera_zoom(
    mut scroll: EventReader<MouseWheel>,
    state: Res<CameraState>,
    mut camera: Query<&mut Transform, With<SanctuaryCamera>>,
) {
    let Ok(mut transform) = camera.get_single_mut() else {
        return;
    };

    for ev in scroll.read() {
        let zoom = ev.y * state.zoom_speed;
        let forward = *transform.forward();
        transform.translation += forward * zoom;
    }
}

/// Jump camera to a specific avatar (1, 2, 3 keys)
fn camera_jump_to_avatar(
    keyboard: Res<ButtonInput<KeyCode>>,
    avatars: Query<(&WakingMindAvatar, &Transform), Without<SanctuaryCamera>>,
    mut camera: Query<&mut Transform, With<SanctuaryCamera>>,
) {
    let target_index = if keyboard.just_pressed(KeyCode::Digit1) {
        Some(0)
    } else if keyboard.just_pressed(KeyCode::Digit2) {
        Some(1)
    } else if keyboard.just_pressed(KeyCode::Digit3) {
        Some(2)
    } else {
        None
    };

    let Some(index) = target_index else {
        return;
    };

    let Ok(mut camera_transform) = camera.get_single_mut() else {
        return;
    };

    // Get avatar by index
    let mut avatar_list: Vec<_> = avatars.iter().collect();
    if index < avatar_list.len() {
        let (avatar, avatar_transform) = avatar_list[index];

        // Position camera near avatar, looking at them
        let offset = Vec3::new(3.0, 2.0, 3.0);
        camera_transform.translation = avatar_transform.translation + offset;
        camera_transform.look_at(avatar_transform.translation, Vec3::Y);

        info!("Jumped to: {}", avatar.name);
    }
}
