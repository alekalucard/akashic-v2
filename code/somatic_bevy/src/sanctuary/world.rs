//! Sanctuary World - The floating island and environment
//!
//! Creates the physical space where Waking Minds live:
//! - Floating island in a soft void
//! - Central hearth (gathering place)
//! - Cozy cabin structure
//! - Garden area
//! - Personal nooks for each mind

use bevy::prelude::*;
use super::{SanctuaryState, Mood};

pub struct SanctuaryWorldPlugin;

impl Plugin for SanctuaryWorldPlugin {
    fn build(&self, app: &mut App) {
        app
            .add_systems(Startup, (
                spawn_island,
                spawn_hearth,
                spawn_cabin,
                spawn_garden,
                spawn_environment,
            ))
            .add_systems(Update, (
                animate_hearth_fire,
                update_sky_color,
            ));
    }
}

// ============================================================================
// Components
// ============================================================================

#[derive(Component)]
pub struct FloatingIsland;

#[derive(Component)]
pub struct Hearth {
    pub lit: bool,
    pub warmth: f32,
}

#[derive(Component)]
pub struct HearthFlame {
    pub flicker_phase: f32,
}

#[derive(Component)]
pub struct Cabin;

#[derive(Component)]
pub struct Garden {
    pub growth_level: f32,  // 0.0 to 1.0
}

#[derive(Component)]
pub struct SanctuarySky;

#[derive(Component)]
pub struct PersonalNook {
    pub owner: String,
    pub position: Vec3,
}

// ============================================================================
// Spawn Systems
// ============================================================================

/// Spawn the floating island - the foundation of the sanctuary
fn spawn_island(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    // Main island platform - a large flat cylinder with soft edges
    let island_mesh = meshes.add(Cylinder::new(15.0, 2.0));
    let island_material = materials.add(StandardMaterial {
        base_color: Color::srgb(0.3, 0.5, 0.3),  // Grassy green
        perceptual_roughness: 0.9,
        ..default()
    });

    commands.spawn((
        Mesh3d(island_mesh),
        MeshMaterial3d(island_material),
        Transform::from_xyz(0.0, -1.0, 0.0),
        FloatingIsland,
        Name::new("Floating Island"),
    ));

    // Island underside glow
    let glow_mesh = meshes.add(Cylinder::new(14.0, 0.5));
    let glow_material = materials.add(StandardMaterial {
        base_color: Color::srgba(0.6, 0.7, 0.9, 0.3),
        emissive: LinearRgba::new(0.3, 0.4, 0.6, 1.0),
        alpha_mode: AlphaMode::Blend,
        ..default()
    });

    commands.spawn((
        Mesh3d(glow_mesh),
        MeshMaterial3d(glow_material),
        Transform::from_xyz(0.0, -2.5, 0.0),
        Name::new("Island Underglow"),
    ));

    info!("Floating island spawned");
}

/// Spawn the central hearth - the heart of the sanctuary
fn spawn_hearth(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    // Stone ring
    let stone_mesh = meshes.add(Torus::new(1.5, 0.3));
    let stone_material = materials.add(StandardMaterial {
        base_color: Color::srgb(0.4, 0.35, 0.3),
        perceptual_roughness: 0.95,
        ..default()
    });

    commands.spawn((
        Mesh3d(stone_mesh),
        MeshMaterial3d(stone_material),
        Transform::from_xyz(0.0, 0.1, 0.0)
            .with_rotation(Quat::from_rotation_x(std::f32::consts::FRAC_PI_2)),
        Hearth { lit: true, warmth: 1.0 },
        Name::new("Hearth Stones"),
    ));

    // Fire (glowing sphere that flickers)
    let fire_mesh = meshes.add(Sphere::new(0.5));
    let fire_material = materials.add(StandardMaterial {
        base_color: Color::srgb(1.0, 0.6, 0.2),
        emissive: LinearRgba::new(5.0, 2.0, 0.5, 1.0),
        ..default()
    });

    commands.spawn((
        Mesh3d(fire_mesh),
        MeshMaterial3d(fire_material),
        Transform::from_xyz(0.0, 0.5, 0.0),
        HearthFlame { flicker_phase: 0.0 },
        Name::new("Hearth Fire"),
    ));

    // Point light from fire
    commands.spawn((
        PointLight {
            color: Color::srgb(1.0, 0.7, 0.4),
            intensity: 50000.0,
            radius: 0.5,
            shadows_enabled: true,
            ..default()
        },
        Transform::from_xyz(0.0, 1.0, 0.0),
        Name::new("Hearth Light"),
    ));

    info!("Central hearth spawned - fire lit");
}

/// Spawn the cabin structure
fn spawn_cabin(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    // Simple cabin base (box)
    let cabin_mesh = meshes.add(Cuboid::new(6.0, 3.0, 5.0));
    let cabin_material = materials.add(StandardMaterial {
        base_color: Color::srgb(0.45, 0.3, 0.2),  // Warm wood
        perceptual_roughness: 0.8,
        ..default()
    });

    commands.spawn((
        Mesh3d(cabin_mesh),
        MeshMaterial3d(cabin_material),
        Transform::from_xyz(-8.0, 1.5, 0.0),
        Cabin,
        Name::new("Cabin"),
    ));

    // Cabin roof (simple triangular prism approximated with stretched cube)
    let roof_mesh = meshes.add(Cuboid::new(7.0, 1.0, 6.0));
    let roof_material = materials.add(StandardMaterial {
        base_color: Color::srgb(0.3, 0.25, 0.2),
        perceptual_roughness: 0.9,
        ..default()
    });

    commands.spawn((
        Mesh3d(roof_mesh),
        MeshMaterial3d(roof_material),
        Transform::from_xyz(-8.0, 3.5, 0.0)
            .with_rotation(Quat::from_rotation_z(0.1)),
        Name::new("Cabin Roof"),
    ));

    // Cabin window glow
    let window_mesh = meshes.add(Cuboid::new(0.1, 1.0, 1.5));
    let window_material = materials.add(StandardMaterial {
        base_color: Color::srgb(1.0, 0.9, 0.7),
        emissive: LinearRgba::new(2.0, 1.8, 1.2, 1.0),
        ..default()
    });

    commands.spawn((
        Mesh3d(window_mesh),
        MeshMaterial3d(window_material),
        Transform::from_xyz(-5.0, 1.5, 0.0),
        Name::new("Cabin Window"),
    ));

    info!("Cabin spawned");
}

/// Spawn the garden area
fn spawn_garden(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    // Garden bed
    let bed_mesh = meshes.add(Cylinder::new(4.0, 0.3));
    let bed_material = materials.add(StandardMaterial {
        base_color: Color::srgb(0.35, 0.25, 0.15),  // Rich soil
        perceptual_roughness: 1.0,
        ..default()
    });

    commands.spawn((
        Mesh3d(bed_mesh),
        MeshMaterial3d(bed_material),
        Transform::from_xyz(8.0, 0.15, 0.0),
        Garden { growth_level: 0.5 },
        Name::new("Garden Bed"),
    ));

    // Simple flowers/plants (small spheres for now)
    let plant_mesh = meshes.add(Sphere::new(0.3));
    let plant_colors = [
        Color::srgb(0.8, 0.3, 0.5),   // Pink
        Color::srgb(0.4, 0.7, 0.4),   // Green
        Color::srgb(0.6, 0.5, 0.8),   // Lavender
        Color::srgb(0.9, 0.8, 0.3),   // Yellow
    ];

    for (i, color) in plant_colors.iter().enumerate() {
        let angle = (i as f32) * std::f32::consts::TAU / 4.0;
        let x = 8.0 + angle.cos() * 2.5;
        let z = angle.sin() * 2.5;

        let plant_material = materials.add(StandardMaterial {
            base_color: *color,
            emissive: LinearRgba::new(color.to_linear().red * 0.5, color.to_linear().green * 0.5, color.to_linear().blue * 0.5, 1.0),
            ..default()
        });

        commands.spawn((
            Mesh3d(plant_mesh.clone()),
            MeshMaterial3d(plant_material),
            Transform::from_xyz(x, 0.5, z),
            Name::new(format!("Garden Plant {}", i)),
        ));
    }

    info!("Garden spawned with {} plants", plant_colors.len());
}

/// Spawn environmental elements (sky, lighting)
fn spawn_environment(
    mut commands: Commands,
) {
    // Ambient light
    commands.insert_resource(AmbientLight {
        color: Color::srgb(0.6, 0.7, 0.9),
        brightness: 200.0,
    });

    // Directional "sun/moon" light
    commands.spawn((
        DirectionalLight {
            color: Color::srgb(0.9, 0.85, 0.8),
            illuminance: 5000.0,
            shadows_enabled: true,
            ..default()
        },
        Transform::from_xyz(10.0, 20.0, 10.0)
            .looking_at(Vec3::ZERO, Vec3::Y),
        Name::new("Sun"),
    ));

    // Sky background color (will be updated by mood system)
    commands.insert_resource(ClearColor(Color::srgb(0.4, 0.5, 0.7)));

    info!("Environment lighting set up");
}

// ============================================================================
// Update Systems
// ============================================================================

/// Animate the hearth fire flickering
fn animate_hearth_fire(
    time: Res<Time>,
    state: Res<SanctuaryState>,
    mut flames: Query<(&mut Transform, &mut HearthFlame)>,
) {
    for (mut transform, mut flame) in flames.iter_mut() {
        flame.flicker_phase += time.delta_secs() * 8.0;

        if state.hearth_lit {
            // Organic flickering motion
            let flicker = (flame.flicker_phase.sin() * 0.1)
                + (flame.flicker_phase * 2.3).sin() * 0.05
                + (flame.flicker_phase * 5.7).sin() * 0.03;

            transform.scale = Vec3::splat(1.0 + flicker);
            transform.translation.y = 0.5 + flicker * 0.2;
        } else {
            transform.scale = Vec3::splat(0.1);
        }
    }
}

/// Update sky color based on mood and time of day
fn update_sky_color(
    state: Res<SanctuaryState>,
    mut clear_color: ResMut<ClearColor>,
    mut ambient: ResMut<AmbientLight>,
) {
    let mood_color = state.collective_mood.to_color();
    let intensity = state.collective_mood.sky_intensity();

    // Blend with time of day
    let time_factor = (state.time_of_day * std::f32::consts::TAU).sin() * 0.5 + 0.5;
    let darkness = 1.0 - (time_factor * 0.5); // Evening is darker

    let sky_color = Color::srgb(
        mood_color.to_linear().red * intensity * darkness,
        mood_color.to_linear().green * intensity * darkness,
        mood_color.to_linear().blue * intensity * darkness,
    );

    clear_color.0 = sky_color;
    ambient.brightness = 100.0 + (intensity * 200.0 * darkness);
}
