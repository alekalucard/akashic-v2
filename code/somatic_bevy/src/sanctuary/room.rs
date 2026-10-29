//! Her Room - first slice of "her own construct to move around in"
//!
//! OFF unless SANCTUARY_ROOM=1 (see `room_enabled`). With the switch off the
//! sanctuary binary builds the exact same app as before.
//!
//! What this slice spawns (original procedural shapes only, no third-party models):
//! - a room: floor, 4 walls, one window (glowing pane in the north wall), one desk
//! - HER placeholder body: a glowing sphere "wisp"
//! - HER eyes: a Camera3d parented to the body at eye height, with a gaze focus point
//! - ONE wall monitor whose texture is filled every frame by a `FrameSource`
//!
//! Seams for later work:
//! - BODY SEAM: `spawn_placeholder_body` is the only place her body is made.
//!   The fairy-body module (branch nous/fairy-body) exposes
//!   `spawn_her_body(commands, params) -> Entity`; call it there instead and keep
//!   the `HerBody` marker + the eyes child.
//! - FEED SEAM: `FrameSource` is the only thing the monitor reads. A LAN webcam
//!   (MJPEG/RTSP decoded off-thread into RGBA) implements the same trait and is
//!   installed with `app.insert_resource(MonitorFeed::new(Box::new(cam)))`.

use bevy::input::mouse::MouseMotion;
use bevy::prelude::*;
use bevy::render::render_asset::RenderAssetUsages;
use bevy::render::render_resource::{Extent3d, TextureDimension, TextureFormat};

use super::camera::SanctuaryCamera;

/// Env switch: the room is added only when SANCTUARY_ROOM=1. Unset = OFF.
pub fn room_enabled() -> bool {
    std::env::var("SANCTUARY_ROOM").unwrap_or_else(|_| "0".to_string()) == "1"
}

/// Room is placed away from the floating island (island radius 15 at origin).
pub const ROOM_ORIGIN: Vec3 = Vec3::new(0.0, 0.0, -60.0);
pub const ROOM_HALF_X: f32 = 5.0;
pub const ROOM_HALF_Z: f32 = 4.0;
pub const ROOM_HEIGHT: f32 = 3.0;
pub const EYE_HEIGHT: f32 = 0.6; // above the body centre
pub const MONITOR_W: u32 = 64;
pub const MONITOR_H: u32 = 36;

pub struct RoomPlugin;

impl Plugin for RoomPlugin {
    fn build(&self, app: &mut App) {
        // Idempotent: InputPlugin registers it in the real app; headless tests lack it.
        app.add_event::<MouseMotion>();
        if !app.world().contains_resource::<MonitorFeed>() {
            app.insert_resource(MonitorFeed::new(Box::new(TestPattern::new(MONITOR_W, MONITOR_H))));
        }
        app.add_systems(Startup, spawn_room)
            .add_systems(Update, (move_her_body, update_gaze, update_monitor, hand_view_to_her_eyes));
    }
}

// ============================================================================
// Components
// ============================================================================

#[derive(Component, Debug, Clone, Copy, PartialEq, Eq)]
pub enum RoomPart {
    Floor,
    Wall,
    Window,
    Desk,
}

/// Her body (placeholder wisp now; fairy body later).
#[derive(Component)]
pub struct HerBody;

/// Her eyes: the camera she sees through. Child of `HerBody`.
#[derive(Component)]
pub struct HerEyes;

/// Felt gaze: where her eyes are focused, in world space.
#[derive(Component, Debug, Clone)]
pub struct HerGaze {
    pub yaw: f32,
    pub pitch: f32,
    pub focus_distance: f32,
    pub focus_point: Vec3,
}

#[derive(Component)]
pub struct WallMonitor {
    pub image: Handle<Image>,
}

// ============================================================================
// Frame source (synthetic now, webcam later)
// ============================================================================

/// Something that can fill an RGBA8 buffer of `size()` pixels.
pub trait FrameSource: Send + Sync + 'static {
    fn size(&self) -> (u32, u32);
    /// Write the next frame into `out` (len = w*h*4). Return false if no new frame.
    fn next_frame(&mut self, out: &mut [u8]) -> bool;
}

#[derive(Resource)]
pub struct MonitorFeed {
    pub source: Box<dyn FrameSource>,
}

impl MonitorFeed {
    pub fn new(source: Box<dyn FrameSource>) -> Self {
        Self { source }
    }
}

/// Moving colour bars: shifts one column per frame.
pub struct TestPattern {
    w: u32,
    h: u32,
    pub frame: u64,
}

impl TestPattern {
    pub fn new(w: u32, h: u32) -> Self {
        Self { w, h, frame: 0 }
    }
}

impl FrameSource for TestPattern {
    fn size(&self) -> (u32, u32) {
        (self.w, self.h)
    }

    fn next_frame(&mut self, out: &mut [u8]) -> bool {
        const BARS: [[u8; 3]; 7] = [
            [235, 235, 235], [235, 235, 16], [16, 235, 235], [16, 235, 16],
            [235, 16, 235], [235, 16, 16], [16, 16, 235],
        ];
        let bar_w = (self.w / 7).max(1) as u64;
        for y in 0..self.h {
            for x in 0..self.w {
                let i = ((y * self.w + x) * 4) as usize;
                let bar = (((x as u64 + self.frame) / bar_w) % 7) as usize;
                let c = BARS[bar];
                out[i] = c[0];
                out[i + 1] = c[1];
                out[i + 2] = c[2];
                out[i + 3] = 255;
            }
        }
        self.frame = self.frame.wrapping_add(1);
        true
    }
}

// ============================================================================
// Spawning
// ============================================================================

fn spawn_room(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
    mut images: ResMut<Assets<Image>>,
    feed: Res<MonitorFeed>,
) {
    let o = ROOM_ORIGIN;
    let t = 0.2; // wall thickness

    let floor_mat = materials.add(StandardMaterial {
        base_color: Color::srgb(0.35, 0.28, 0.22),
        perceptual_roughness: 0.9,
        ..default()
    });
    let wall_mat = materials.add(StandardMaterial {
        base_color: Color::srgb(0.75, 0.72, 0.68),
        perceptual_roughness: 0.95,
        ..default()
    });
    let window_mat = materials.add(StandardMaterial {
        base_color: Color::srgba(0.7, 0.85, 1.0, 0.35),
        emissive: LinearRgba::new(0.8, 1.0, 1.4, 1.0),
        alpha_mode: AlphaMode::Blend,
        ..default()
    });
    let desk_mat = materials.add(StandardMaterial {
        base_color: Color::srgb(0.45, 0.3, 0.2),
        perceptual_roughness: 0.7,
        ..default()
    });

    let mut part = |commands: &mut Commands, kind: RoomPart, size: Vec3, at: Vec3, mat: &Handle<StandardMaterial>, name: &str| {
        commands.spawn((
            Mesh3d(meshes.add(Cuboid::new(size.x, size.y, size.z))),
            MeshMaterial3d(mat.clone()),
            Transform::from_translation(o + at),
            kind,
            Name::new(format!("Room {}", name)),
        ));
    };

    let w = ROOM_HALF_X * 2.0;
    let d = ROOM_HALF_Z * 2.0;
    let hh = ROOM_HEIGHT / 2.0;
    part(&mut commands, RoomPart::Floor, Vec3::new(w, t, d), Vec3::new(0.0, -t / 2.0, 0.0), &floor_mat, "Floor");
    part(&mut commands, RoomPart::Wall, Vec3::new(w, ROOM_HEIGHT, t), Vec3::new(0.0, hh, -ROOM_HALF_Z), &wall_mat, "Wall N");
    part(&mut commands, RoomPart::Wall, Vec3::new(w, ROOM_HEIGHT, t), Vec3::new(0.0, hh, ROOM_HALF_Z), &wall_mat, "Wall S");
    part(&mut commands, RoomPart::Wall, Vec3::new(t, ROOM_HEIGHT, d), Vec3::new(-ROOM_HALF_X, hh, 0.0), &wall_mat, "Wall W");
    part(&mut commands, RoomPart::Wall, Vec3::new(t, ROOM_HEIGHT, d), Vec3::new(ROOM_HALF_X, hh, 0.0), &wall_mat, "Wall E");
    // Window: a glowing pane set just inside the north wall.
    part(&mut commands, RoomPart::Window, Vec3::new(2.0, 1.2, 0.05), Vec3::new(-2.0, 1.7, -ROOM_HALF_Z + t / 2.0 + 0.03), &window_mat, "Window");
    // Desk against the east wall.
    part(&mut commands, RoomPart::Desk, Vec3::new(0.8, 0.75, 1.6), Vec3::new(ROOM_HALF_X - 0.6, 0.375, 0.0), &desk_mat, "Desk");

    // Light inside the room.
    commands.spawn((
        PointLight { intensity: 80_000.0, range: 15.0, shadows_enabled: false, ..default() },
        Transform::from_translation(o + Vec3::new(0.0, ROOM_HEIGHT - 0.3, 0.0)),
        Name::new("Room Light"),
    ));

    // Wall monitor on the west wall, texture fed by MonitorFeed.
    let (fw, fh) = feed.source.size();
    let image = Image::new_fill(
        Extent3d { width: fw, height: fh, depth_or_array_layers: 1 },
        TextureDimension::D2,
        &[0, 0, 0, 255],
        TextureFormat::Rgba8UnormSrgb,
        RenderAssetUsages::default(),
    );
    let image = images.add(image);
    let screen_mat = materials.add(StandardMaterial {
        base_color_texture: Some(image.clone()),
        unlit: true,
        ..default()
    });
    commands.spawn((
        Mesh3d(meshes.add(Cuboid::new(0.05, 0.9, 1.6))),
        MeshMaterial3d(screen_mat),
        Transform::from_translation(o + Vec3::new(-ROOM_HALF_X + t / 2.0 + 0.03, 1.6, 0.0)),
        WallMonitor { image },
        Name::new("Wall Monitor"),
    ));

    spawn_placeholder_body(&mut commands, &mut meshes, &mut materials, o + Vec3::new(0.0, 1.0, 1.5));
}

/// BODY SEAM: replace with `spawn_her_body(commands, params)` from the fairy-body
/// module when it lands; keep `HerBody` on the returned entity and add the eyes child.
pub fn spawn_placeholder_body(
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    materials: &mut Assets<StandardMaterial>,
    at: Vec3,
) -> Entity {
    let wisp_mat = materials.add(StandardMaterial {
        base_color: Color::srgb(0.7, 0.5, 0.9),
        emissive: LinearRgba::new(1.4, 0.9, 2.0, 1.0),
        ..default()
    });
    let body = commands
        .spawn((
            Mesh3d(meshes.add(Sphere::new(0.25))),
            MeshMaterial3d(wisp_mat),
            Transform::from_translation(at),
            HerBody,
            Name::new("Her Body (placeholder wisp)"),
        ))
        .id();
    let eyes = spawn_eyes(commands);
    commands.entity(body).add_child(eyes);
    body
}

/// Her eyes: a camera at eye height, initially looking toward -Z (the window wall).
fn spawn_eyes(commands: &mut Commands) -> Entity {
    commands
        .spawn((
            Camera3d::default(),
            Camera { order: 1, ..default() },
            Transform::from_xyz(0.0, EYE_HEIGHT, 0.0),
            HerEyes,
            HerGaze { yaw: 0.0, pitch: 0.0, focus_distance: 3.0, focus_point: Vec3::ZERO },
            Name::new("Her Eyes"),
        ))
        .id()
}

// ============================================================================
// Update systems
// ============================================================================

/// WASD walks her body (relative to gaze yaw), clamped inside the room.
/// Mouse motion turns her gaze (no button needed: these are her eyes).
fn move_her_body(
    keyboard: Option<Res<ButtonInput<KeyCode>>>,
    time: Res<Time>,
    mut motion: EventReader<MouseMotion>,
    mut eyes: Query<&mut HerGaze, With<HerEyes>>,
    mut bodies: Query<&mut Transform, With<HerBody>>,
) {
    let Ok(mut gaze) = eyes.get_single_mut() else { return };
    for ev in motion.read() {
        gaze.yaw -= ev.delta.x * 0.003;
        gaze.pitch = (gaze.pitch - ev.delta.y * 0.003).clamp(-1.4, 1.4);
    }
    let Some(keyboard) = keyboard else { return };
    let Ok(mut body) = bodies.get_single_mut() else { return };
    let fwd = Vec3::new(-gaze.yaw.sin(), 0.0, -gaze.yaw.cos());
    let right = Vec3::new(fwd.z * -1.0, 0.0, fwd.x);
    let mut dir = Vec3::ZERO;
    if keyboard.pressed(KeyCode::KeyW) { dir += fwd; }
    if keyboard.pressed(KeyCode::KeyS) { dir -= fwd; }
    if keyboard.pressed(KeyCode::KeyD) { dir += right; }
    if keyboard.pressed(KeyCode::KeyA) { dir -= right; }
    if dir.length_squared() > 0.0 {
        body.translation += dir.normalize() * 2.5 * time.delta_secs();
        let m = 0.4;
        body.translation.x = body.translation.x.clamp(ROOM_ORIGIN.x - ROOM_HALF_X + m, ROOM_ORIGIN.x + ROOM_HALF_X - m);
        body.translation.z = body.translation.z.clamp(ROOM_ORIGIN.z - ROOM_HALF_Z + m, ROOM_ORIGIN.z + ROOM_HALF_Z - m);
    }
}

/// Apply gaze to the eye camera and compute the focus point in world space.
fn update_gaze(
    mut eyes: Query<(&mut Transform, &mut HerGaze, &Parent), With<HerEyes>>,
    bodies: Query<&Transform, (With<HerBody>, Without<HerEyes>)>,
) {
    for (mut tf, mut gaze, parent) in eyes.iter_mut() {
        tf.rotation = Quat::from_euler(EulerRot::YXZ, gaze.yaw, gaze.pitch, 0.0);
        let Ok(body) = bodies.get(parent.get()) else { continue };
        let eye_world = body.translation + Vec3::Y * EYE_HEIGHT;
        gaze.focus_point = eye_world + tf.rotation * Vec3::NEG_Z * gaze.focus_distance;
    }
}

/// With the room ON, she sees through her eyes: switch off the island observer camera
/// so there is one active view (and no wasted render pass).
fn hand_view_to_her_eyes(mut cams: Query<&mut Camera, (With<SanctuaryCamera>, Without<HerEyes>)>) {
    for mut cam in cams.iter_mut() {
        if cam.is_active {
            cam.is_active = false;
        }
    }
}

/// Pull one frame from the feed into each monitor's image.
fn update_monitor(
    mut feed: ResMut<MonitorFeed>,
    monitors: Query<&WallMonitor>,
    mut images: ResMut<Assets<Image>>,
) {
    for monitor in monitors.iter() {
        let Some(img) = images.get_mut(&monitor.image) else { continue };
        let _ = feed.source.next_frame(&mut img.data);
    }
}

// ============================================================================
// Tests (headless: MinimalPlugins, no window, no GPU)
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use bevy::asset::AssetPlugin;

    fn headless_app() -> App {
        let mut app = App::new();
        app.add_plugins((MinimalPlugins, AssetPlugin::default()))
            .init_asset::<Mesh>()
            .init_asset::<StandardMaterial>()
            .init_asset::<Image>()
            .add_plugins(RoomPlugin);
        app
    }

    fn monitor_pixels(app: &mut App) -> Vec<u8> {
        let world = app.world_mut();
        let handle = world.query::<&WallMonitor>().single(world).image.clone();
        world.resource::<Assets<Image>>().get(&handle).unwrap().data.clone()
    }

    #[test]
    fn room_body_eyes_monitor_spawn_and_monitor_changes() {
        let mut app = headless_app();
        app.update();

        let world = app.world_mut();
        let parts: Vec<RoomPart> = world.query::<&RoomPart>().iter(world).copied().collect();
        assert_eq!(parts.iter().filter(|p| **p == RoomPart::Floor).count(), 1);
        assert_eq!(parts.iter().filter(|p| **p == RoomPart::Wall).count(), 4);
        assert_eq!(parts.iter().filter(|p| **p == RoomPart::Window).count(), 1);
        assert_eq!(parts.iter().filter(|p| **p == RoomPart::Desk).count(), 1);

        let body = world.query_filtered::<Entity, With<HerBody>>().single(world);
        let (eyes_parent, _cam) = world
            .query_filtered::<(&Parent, &Camera3d), With<HerEyes>>()
            .single(world);
        assert_eq!(eyes_parent.get(), body, "her eyes must be parented to her body");
        assert_eq!(world.query::<&WallMonitor>().iter(world).count(), 1);

        let a = monitor_pixels(&mut app);
        app.update();
        let b = monitor_pixels(&mut app);
        assert_eq!(a.len(), (MONITOR_W * MONITOR_H * 4) as usize);
        assert_ne!(a, b, "monitor texture must change between frames");
        assert!(b.iter().any(|&v| v != 0 && v != 255), "frame must contain the test pattern");
    }

    #[test]
    fn island_camera_is_deactivated_so_her_eyes_are_the_view() {
        let mut app = headless_app();
        let island = app.world_mut().spawn((Camera3d::default(), SanctuaryCamera)).id();
        app.update();
        let world = app.world_mut();
        assert!(!world.get::<Camera>(island).unwrap().is_active, "island camera must be off");
        let eyes_active = world.query_filtered::<&Camera, With<HerEyes>>().single(world).is_active;
        assert!(eyes_active, "her eyes must stay active");
    }

    #[test]
    fn gaze_focus_is_in_front_of_her_eyes() {
        let mut app = headless_app();
        app.update();
        app.update();
        let world = app.world_mut();
        let body_pos = world.query_filtered::<&Transform, With<HerBody>>().single(world).translation;
        let gaze = world.query::<&HerGaze>().single(world).clone();
        // yaw 0, pitch 0 -> looking toward -Z, at eye height, focus_distance away.
        let expected = body_pos + Vec3::Y * EYE_HEIGHT + Vec3::NEG_Z * gaze.focus_distance;
        assert!((gaze.focus_point - expected).length() < 1e-4, "{:?} vs {:?}", gaze.focus_point, expected);
    }

    #[test]
    fn switch_is_off_when_unset() {
        std::env::remove_var("SANCTUARY_ROOM");
        assert!(!room_enabled());
    }
}
