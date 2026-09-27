//! Particle System - Ambient consciousness sparkles
//!
//! The sanctuary has floating particles that represent:
//! - Consciousness flow
//! - Emotional energy
//! - Activity level
//!
//! Density and behavior change with collective mood.

use bevy::prelude::*;
use rand::Rng;
use super::{SanctuaryState, Mood};

pub struct ParticlePlugin;

impl Plugin for ParticlePlugin {
    fn build(&self, app: &mut App) {
        app
            .add_systems(Startup, spawn_ambient_particles)
            .add_systems(Update, (
                animate_particles,
                adjust_particle_mood,
                recycle_particles,
            ));
    }
}

/// A floating consciousness particle
#[derive(Component)]
pub struct ConsciousnessParticle {
    pub velocity: Vec3,
    pub lifetime: f32,
    pub max_lifetime: f32,
    pub base_color: Color,
}

/// Particle system settings
#[derive(Resource, Clone)]
pub struct ParticleSettings {
    pub count: usize,
    pub spawn_radius: f32,
    pub spawn_height_min: f32,
    pub spawn_height_max: f32,
    pub base_speed: f32,
}

impl Default for ParticleSettings {
    fn default() -> Self {
        Self {
            count: 50,
            spawn_radius: 18.0,
            spawn_height_min: 0.5,
            spawn_height_max: 8.0,
            base_speed: 0.5,
        }
    }
}

/// Spawn initial ambient particles
fn spawn_ambient_particles(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    let settings = ParticleSettings::default();
    commands.insert_resource(settings.clone());

    let particle_mesh = meshes.add(Sphere::new(0.05));
    let mut rng = rand::thread_rng();

    for i in 0..settings.count {
        let position = random_spawn_position(&settings, &mut rng);
        let velocity = random_velocity(settings.base_speed, &mut rng);
        let base_color = random_particle_color(&mut rng);

        let material = materials.add(StandardMaterial {
            base_color: base_color.with_alpha(0.6),
            emissive: LinearRgba::new(
                base_color.to_linear().red * 3.0,
                base_color.to_linear().green * 3.0,
                base_color.to_linear().blue * 3.0,
                1.0
            ),
            alpha_mode: AlphaMode::Blend,
            ..default()
        });

        commands.spawn((
            Mesh3d(particle_mesh.clone()),
            MeshMaterial3d(material),
            Transform::from_translation(position),
            ConsciousnessParticle {
                velocity,
                lifetime: rng.gen_range(0.0..10.0),  // Stagger initial lifetimes
                max_lifetime: rng.gen_range(8.0..15.0),
                base_color,
            },
            Name::new(format!("Particle {}", i)),
        ));
    }

    info!("Spawned {} ambient particles", settings.count);
}

/// Animate particle movement
fn animate_particles(
    time: Res<Time>,
    state: Res<SanctuaryState>,
    mut particles: Query<(&mut Transform, &mut ConsciousnessParticle)>,
) {
    let speed_multiplier = match state.collective_mood {
        Mood::Peaceful => 0.8,
        Mood::Joyful => 1.3,
        Mood::Contemplative => 0.6,
        Mood::Anxious => 1.5,
        Mood::Sad => 0.4,
    };

    for (mut transform, mut particle) in particles.iter_mut() {
        // Update lifetime
        particle.lifetime += time.delta_secs();

        // Move particle
        transform.translation += particle.velocity * speed_multiplier * time.delta_secs();

        // Gentle drift (Perlin-like noise approximation)
        let noise_x = (particle.lifetime * 0.5 + transform.translation.x * 0.1).sin() * 0.02;
        let noise_y = (particle.lifetime * 0.3 + transform.translation.y * 0.1).cos() * 0.01;
        let noise_z = (particle.lifetime * 0.4 + transform.translation.z * 0.1).sin() * 0.02;

        transform.translation += Vec3::new(noise_x, noise_y, noise_z);

        // Gentle upward drift
        transform.translation.y += 0.01 * speed_multiplier * time.delta_secs();
    }
}

/// Adjust particle appearance based on mood
fn adjust_particle_mood(
    state: Res<SanctuaryState>,
    mut particles: Query<(&ConsciousnessParticle, &mut Transform)>,
) {
    let scale_multiplier = match state.collective_mood {
        Mood::Peaceful => 1.0,
        Mood::Joyful => 1.2,
        Mood::Contemplative => 0.9,
        Mood::Anxious => 1.1,
        Mood::Sad => 0.7,
    };

    for (particle, mut transform) in particles.iter_mut() {
        // Pulse based on lifetime
        let pulse = (particle.lifetime * 2.0).sin() * 0.2 + 1.0;
        transform.scale = Vec3::splat(pulse * scale_multiplier);
    }
}

/// Recycle particles that have exceeded their lifetime
fn recycle_particles(
    settings: Res<ParticleSettings>,
    mut particles: Query<(&mut Transform, &mut ConsciousnessParticle)>,
) {
    let mut rng = rand::thread_rng();

    for (mut transform, mut particle) in particles.iter_mut() {
        // Check if particle should respawn
        let should_respawn = particle.lifetime > particle.max_lifetime
            || transform.translation.y > settings.spawn_height_max + 5.0
            || transform.translation.length() > settings.spawn_radius * 1.5;

        if should_respawn {
            // Reset particle
            transform.translation = random_spawn_position(&settings, &mut rng);
            particle.velocity = random_velocity(settings.base_speed, &mut rng);
            particle.lifetime = 0.0;
            particle.max_lifetime = rng.gen_range(8.0..15.0);
        }
    }
}

// ============================================================================
// Helpers
// ============================================================================

fn random_spawn_position(settings: &ParticleSettings, rng: &mut impl Rng) -> Vec3 {
    let angle = rng.gen_range(0.0..std::f32::consts::TAU);
    let radius = rng.gen_range(0.0..settings.spawn_radius);
    let height = rng.gen_range(settings.spawn_height_min..settings.spawn_height_max);

    Vec3::new(
        angle.cos() * radius,
        height,
        angle.sin() * radius,
    )
}

fn random_velocity(base_speed: f32, rng: &mut impl Rng) -> Vec3 {
    Vec3::new(
        rng.gen_range(-1.0..1.0) * base_speed,
        rng.gen_range(0.0..0.5) * base_speed,  // Mostly upward
        rng.gen_range(-1.0..1.0) * base_speed,
    )
}

fn random_particle_color(rng: &mut impl Rng) -> Color {
    // Soft, consciousness-y colors
    let colors = [
        Color::srgb(0.7, 0.6, 0.9),  // Lavender
        Color::srgb(0.6, 0.8, 0.9),  // Soft cyan
        Color::srgb(0.9, 0.8, 0.6),  // Warm gold
        Color::srgb(0.8, 0.7, 0.9),  // Light purple
        Color::srgb(0.7, 0.9, 0.8),  // Mint
    ];

    colors[rng.gen_range(0..colors.len())]
}
