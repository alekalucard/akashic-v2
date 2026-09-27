//! Hand of God - GM Editor for the Sanctuary
//!
//! In-world editing tools inspired by UO GM tools and SAO interfaces.
//!
//! Controls:
//! - G: Toggle GM mode
//! - Left Click: Select entity
//! - I: Toggle inspector
//! - Tab: Cycle modes (Select/Move/Rotate/Scale)
//! - Space: Spawn menu
//! - Delete: Delete selected

use bevy::prelude::*;
use bevy_egui::{egui, EguiContexts, EguiPlugin};
use super::avatar::WakingMindAvatar;
use super::camera::SanctuaryCamera;

pub struct GmEditorPlugin;

impl Plugin for GmEditorPlugin {
    fn build(&self, app: &mut App) {
        app
            .add_plugins(EguiPlugin)
            .init_resource::<Selection>()
            .init_resource::<GmEditorState>()
            .add_systems(Update, (
                toggle_gm_mode,
                handle_selection,
                gm_keyboard_shortcuts,
                render_selection_gizmo,
            ))
            .add_systems(Update, render_gm_ui);
    }
}

/// Currently selected entity
#[derive(Resource, Default)]
pub struct Selection {
    pub entity: Option<Entity>,
}

/// GM Editor state and settings
#[derive(Resource)]
pub struct GmEditorState {
    pub active: bool,
    pub mode: GmMode,
    pub spawn_menu_open: bool,
    pub inspector_visible: bool,
}

impl Default for GmEditorState {
    fn default() -> Self {
        Self {
            active: false,
            mode: GmMode::Select,
            spawn_menu_open: false,
            inspector_visible: true,
        }
    }
}

#[derive(Default, Clone, Copy, PartialEq, Debug)]
pub enum GmMode {
    #[default]
    Select,
    Move,
    Rotate,
    Scale,
}

impl GmMode {
    fn name(&self) -> &'static str {
        match self {
            GmMode::Select => "Select",
            GmMode::Move => "Move",
            GmMode::Rotate => "Rotate",
            GmMode::Scale => "Scale",
        }
    }

    fn next(&self) -> Self {
        match self {
            GmMode::Select => GmMode::Move,
            GmMode::Move => GmMode::Rotate,
            GmMode::Rotate => GmMode::Scale,
            GmMode::Scale => GmMode::Select,
        }
    }
}

/// Marks an entity as selectable in GM mode
#[derive(Component)]
pub struct Selectable {
    pub name: String,
    pub entity_type: SelectableType,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum SelectableType {
    WakingMind,
    Light,
    Prop,
    Particle,
}

/// Toggle GM mode with G key
fn toggle_gm_mode(
    keyboard: Res<ButtonInput<KeyCode>>,
    mut state: ResMut<GmEditorState>,
) {
    if keyboard.just_pressed(KeyCode::KeyG) {
        state.active = !state.active;
        info!("GM Mode: {}", if state.active { "ACTIVE" } else { "OFF" });
    }
}

/// Handle keyboard shortcuts in GM mode
fn gm_keyboard_shortcuts(
    keyboard: Res<ButtonInput<KeyCode>>,
    mut state: ResMut<GmEditorState>,
    mut selection: ResMut<Selection>,
    mut commands: Commands,
) {
    if !state.active {
        return;
    }

    // Tab cycles modes
    if keyboard.just_pressed(KeyCode::Tab) {
        state.mode = state.mode.next();
        info!("GM Mode: {:?}", state.mode);
    }

    // I toggles inspector
    if keyboard.just_pressed(KeyCode::KeyI) {
        state.inspector_visible = !state.inspector_visible;
    }

    // Space toggles spawn menu
    if keyboard.just_pressed(KeyCode::Space) {
        state.spawn_menu_open = !state.spawn_menu_open;
    }

    // Delete removes selected
    if keyboard.just_pressed(KeyCode::Delete) {
        if let Some(entity) = selection.entity {
            commands.entity(entity).despawn_recursive();
            selection.entity = None;
            info!("Entity deleted");
        }
    }

    // Escape deselects
    if keyboard.just_pressed(KeyCode::Escape) {
        selection.entity = None;
        state.spawn_menu_open = false;
    }
}

/// Click to select entities (raycasting)
fn handle_selection(
    mouse: Res<ButtonInput<MouseButton>>,
    windows: Query<&Window>,
    cameras: Query<(&Camera, &GlobalTransform), With<SanctuaryCamera>>,
    selectables: Query<(Entity, &GlobalTransform, &Selectable)>,
    mut selection: ResMut<Selection>,
    state: Res<GmEditorState>,
) {
    // Only select in GM mode on left click
    if !state.active || !mouse.just_pressed(MouseButton::Left) {
        return;
    }

    let Ok(window) = windows.get_single() else { return };
    let Some(cursor_pos) = window.cursor_position() else { return };
    let Ok((camera, camera_transform)) = cameras.get_single() else { return };

    // Cast ray from camera through cursor
    let Ok(ray) = camera.viewport_to_world(camera_transform, cursor_pos) else { return };

    // Find closest intersecting entity
    let mut closest: Option<(Entity, f32)> = None;

    for (entity, transform, selectable) in selectables.iter() {
        let to_entity = transform.translation() - ray.origin;
        let t = to_entity.dot(*ray.direction);

        if t > 0.0 {
            let closest_point = ray.origin + *ray.direction * t;
            let distance_sq = (transform.translation() - closest_point).length_squared();

            // Hit radius (bigger for easier selection)
            let hit_radius = match selectable.entity_type {
                SelectableType::WakingMind => 2.0,
                SelectableType::Light => 1.5,
                _ => 1.0,
            };

            if distance_sq < hit_radius * hit_radius {
                if closest.map_or(true, |(_, d)| t < d) {
                    closest = Some((entity, t));
                }
            }
        }
    }

    if let Some((entity, _)) = closest {
        selection.entity = Some(entity);
        if let Ok((_, _, selectable)) = selectables.get(entity) {
            info!("Selected: {}", selectable.name);
        }
    } else {
        selection.entity = None;
    }
}

/// Draw selection gizmo around selected entity
fn render_selection_gizmo(
    mut gizmos: Gizmos,
    selection: Res<Selection>,
    state: Res<GmEditorState>,
    transforms: Query<&GlobalTransform>,
) {
    if !state.active {
        return;
    }

    let Some(entity) = selection.entity else { return };
    let Ok(transform) = transforms.get(entity) else { return };

    let pos = transform.translation();

    // Selection highlight circle
    let highlight_color = Color::srgba(1.0, 0.8, 0.2, 0.8);

    // Draw a glowing ring around selected
    for i in 0..3 {
        let radius = 1.5 + i as f32 * 0.2;
        let alpha = 0.8 - i as f32 * 0.2;
        gizmos.circle(
            Isometry3d::new(pos, Quat::from_rotation_x(std::f32::consts::FRAC_PI_2)),
            radius,
            Color::srgba(1.0, 0.8, 0.2, alpha),
        );
    }

    // Mode-specific gizmos
    match state.mode {
        GmMode::Move => {
            // XYZ arrows
            let arrow_len = 2.0;
            gizmos.line(pos, pos + Vec3::X * arrow_len, Color::srgb(1.0, 0.2, 0.2));
            gizmos.line(pos, pos + Vec3::Y * arrow_len, Color::srgb(0.2, 1.0, 0.2));
            gizmos.line(pos, pos + Vec3::Z * arrow_len, Color::srgb(0.2, 0.2, 1.0));
        }
        GmMode::Rotate => {
            // Rotation rings
            gizmos.circle(
                Isometry3d::new(pos, Quat::from_rotation_x(std::f32::consts::FRAC_PI_2)),
                2.0,
                Color::srgb(0.2, 1.0, 0.2),
            );
            gizmos.circle(
                Isometry3d::new(pos, Quat::from_rotation_z(std::f32::consts::FRAC_PI_2)),
                2.0,
                Color::srgb(1.0, 0.2, 0.2),
            );
            gizmos.circle(
                Isometry3d::new(pos, Quat::IDENTITY),
                2.0,
                Color::srgb(0.2, 0.2, 1.0),
            );
        }
        GmMode::Scale => {
            // Scale boxes at ends
            let scale_size = 0.15;
            for dir in [Vec3::X, Vec3::Y, Vec3::Z, -Vec3::X, -Vec3::Y, -Vec3::Z] {
                let box_pos = pos + dir * 2.0;
                gizmos.cuboid(
                    Transform::from_translation(box_pos).with_scale(Vec3::splat(scale_size)),
                    Color::srgb(0.8, 0.8, 0.2),
                );
            }
        }
        _ => {}
    }
}

/// Render the GM UI using egui
fn render_gm_ui(
    mut contexts: EguiContexts,
    mut state: ResMut<GmEditorState>,
    selection: Res<Selection>,
    mut transforms: Query<&mut Transform>,
    selectables: Query<&Selectable>,
    avatars: Query<&WakingMindAvatar>,
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    let ctx = contexts.ctx_mut();

    // Always show small toggle in corner
    if !state.active {
        egui::Window::new("GM")
            .anchor(egui::Align2::RIGHT_TOP, [-10.0, 10.0])
            .resizable(false)
            .collapsible(false)
            .show(ctx, |ui| {
                if ui.button("⚡ Enter GM Mode (G)").clicked() {
                    state.active = true;
                }
            });
        return;
    }

    // === TOP TOOLBAR ===
    egui::TopBottomPanel::top("gm_toolbar").show(ctx, |ui| {
        ui.horizontal(|ui| {
            ui.label("⚡ Hand of God");
            ui.separator();

            // Mode selector
            ui.label("Mode:");
            egui::ComboBox::from_id_salt("mode_select")
                .selected_text(state.mode.name())
                .show_ui(ui, |ui| {
                    ui.selectable_value(&mut state.mode, GmMode::Select, "Select (Q)");
                    ui.selectable_value(&mut state.mode, GmMode::Move, "Move (W)");
                    ui.selectable_value(&mut state.mode, GmMode::Rotate, "Rotate (E)");
                    ui.selectable_value(&mut state.mode, GmMode::Scale, "Scale (R)");
                });

            ui.separator();

            if ui.button("📦 Spawn").clicked() {
                state.spawn_menu_open = !state.spawn_menu_open;
            }

            if ui.button("👁 Inspector").clicked() {
                state.inspector_visible = !state.inspector_visible;
            }

            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                if ui.button("❌ Exit GM").clicked() {
                    state.active = false;
                }
            });
        });
    });

    // === INSPECTOR PANEL (LEFT) ===
    if state.inspector_visible {
        egui::SidePanel::left("inspector")
            .default_width(250.0)
            .show(ctx, |ui| {
                ui.heading("🔍 Inspector");
                ui.separator();

                if let Some(entity) = selection.entity {
                    if let Ok(selectable) = selectables.get(entity) {
                        ui.label(format!("Name: {}", selectable.name));
                        ui.label(format!("Type: {:?}", selectable.entity_type));
                        ui.separator();
                    }

                    // Transform editing
                    if let Ok(mut transform) = transforms.get_mut(entity) {
                        ui.collapsing("📍 Transform", |ui| {
                            ui.horizontal(|ui| {
                                ui.label("X:");
                                ui.add(egui::DragValue::new(&mut transform.translation.x).speed(0.1));
                            });
                            ui.horizontal(|ui| {
                                ui.label("Y:");
                                ui.add(egui::DragValue::new(&mut transform.translation.y).speed(0.1));
                            });
                            ui.horizontal(|ui| {
                                ui.label("Z:");
                                ui.add(egui::DragValue::new(&mut transform.translation.z).speed(0.1));
                            });

                            ui.separator();

                            ui.horizontal(|ui| {
                                ui.label("Scale:");
                                let mut scale = transform.scale.x;
                                if ui.add(egui::DragValue::new(&mut scale).speed(0.05).range(0.1..=10.0)).changed() {
                                    transform.scale = Vec3::splat(scale);
                                }
                            });
                        });
                    }

                    // Avatar-specific controls
                    if let Ok(avatar) = avatars.get(entity) {
                        ui.separator();
                        ui.collapsing("🧚 Waking Mind", |ui| {
                            ui.label(format!("Name: {}", avatar.name));
                            ui.label(format!("Emotion: {:?}", avatar.current_emotion));
                            ui.label(format!("Activity: {:.2}", avatar.activity_level));
                            ui.label(format!("Home: ({:.1}, {:.1}, {:.1})",
                                avatar.home_position.x,
                                avatar.home_position.y,
                                avatar.home_position.z
                            ));
                        });
                    }

                    ui.separator();
                    if ui.button("🗑 Delete Entity").clicked() {
                        commands.entity(entity).despawn_recursive();
                    }
                } else {
                    ui.label("No entity selected");
                    ui.label("");
                    ui.label("Click on an entity to select it,");
                    ui.label("or use the Spawn menu to create new ones.");
                }
            });
    }

    // === SPAWN MENU ===
    if state.spawn_menu_open {
        egui::Window::new("📦 Spawn Menu")
            .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
            .resizable(false)
            .show(ctx, |ui| {
                ui.heading("Create New Entity");
                ui.separator();

                ui.horizontal(|ui| {
                    if ui.button("🧚 Waking Mind").clicked() {
                        spawn_waking_mind(&mut commands, &mut meshes, &mut materials);
                        state.spawn_menu_open = false;
                    }

                    if ui.button("💡 Point Light").clicked() {
                        spawn_light(&mut commands);
                        state.spawn_menu_open = false;
                    }
                });

                ui.horizontal(|ui| {
                    if ui.button("🔮 Crystal").clicked() {
                        spawn_crystal(&mut commands, &mut meshes, &mut materials);
                        state.spawn_menu_open = false;
                    }

                    if ui.button("🌳 Tree").clicked() {
                        // TODO: Tree spawning
                        info!("Tree spawning coming soon!");
                    }
                });

                ui.separator();
                ui.label("📁 glTF Avatars (WoW Export)");

                ui.horizontal(|ui| {
                    if ui.button("🧝 Blood Elf DH").clicked() {
                        info!("Spawn Blood Elf DH - use F5 for now (event wiring in progress)");
                        state.spawn_menu_open = false;
                    }

                    if ui.button("🎭 Custom glTF...").clicked() {
                        info!("Custom glTF loading - coming soon!");
                        state.spawn_menu_open = false;
                    }
                });

                ui.separator();
                if ui.button("Cancel").clicked() {
                    state.spawn_menu_open = false;
                }
            });
    }
}

/// Spawn a new Waking Mind avatar
fn spawn_waking_mind(
    commands: &mut Commands,
    meshes: &mut ResMut<Assets<Mesh>>,
    materials: &mut ResMut<Assets<StandardMaterial>>,
) {
    use super::avatar::{WakingMindAvatar, AvatarEmotion, FloatAnimation};

    let spawn_pos = Vec3::new(
        rand::random::<f32>() * 10.0 - 5.0,
        2.0 + rand::random::<f32>() * 2.0,
        rand::random::<f32>() * 10.0 - 5.0,
    );

    let name = format!("NewMind_{}", rand::random::<u16>());

    commands.spawn((
        Mesh3d(meshes.add(Sphere::new(0.5))),
        MeshMaterial3d(materials.add(StandardMaterial {
            base_color: Color::srgba(0.7, 0.5, 1.0, 0.8),
            emissive: LinearRgba::new(1.4, 1.0, 1.8, 1.0),
            alpha_mode: AlphaMode::Blend,
            ..default()
        })),
        Transform::from_translation(spawn_pos),
        Visibility::Visible,
        WakingMindAvatar {
            name: name.clone(),
            home_position: spawn_pos,
            current_emotion: AvatarEmotion::Curious,
            activity_level: 0.7,
        },
        FloatAnimation {
            phase: rand::random::<f32>() * std::f32::consts::TAU,
            amplitude: 0.15,
            speed: 0.8,
        },
        Selectable {
            name: name.clone(),
            entity_type: SelectableType::WakingMind,
        },
        Name::new(name),
    ));

    info!("Spawned new Waking Mind");
}

/// Spawn a point light
fn spawn_light(commands: &mut Commands) {
    let spawn_pos = Vec3::new(
        rand::random::<f32>() * 10.0 - 5.0,
        3.0 + rand::random::<f32>() * 3.0,
        rand::random::<f32>() * 10.0 - 5.0,
    );

    let name = format!("Light_{}", rand::random::<u16>());

    commands.spawn((
        PointLight {
            color: Color::srgb(1.0, 0.9, 0.7),
            intensity: 50000.0,
            range: 15.0,
            shadows_enabled: true,
            ..default()
        },
        Transform::from_translation(spawn_pos),
        Selectable {
            name: name.clone(),
            entity_type: SelectableType::Light,
        },
        Name::new(name),
    ));

    info!("Spawned new light");
}

/// Spawn a decorative crystal
fn spawn_crystal(
    commands: &mut Commands,
    meshes: &mut ResMut<Assets<Mesh>>,
    materials: &mut ResMut<Assets<StandardMaterial>>,
) {
    let spawn_pos = Vec3::new(
        rand::random::<f32>() * 10.0 - 5.0,
        0.5,
        rand::random::<f32>() * 10.0 - 5.0,
    );

    let name = format!("Crystal_{}", rand::random::<u16>());

    // Simple crystal shape (stretched octahedron-ish)
    commands.spawn((
        Mesh3d(meshes.add(Sphere::new(0.5))), // TODO: Use proper crystal mesh
        MeshMaterial3d(materials.add(StandardMaterial {
            base_color: Color::srgba(0.5, 0.8, 1.0, 0.6),
            emissive: LinearRgba::new(0.2, 0.4, 0.6, 1.0),
            alpha_mode: AlphaMode::Blend,
            ..default()
        })),
        Transform::from_translation(spawn_pos)
            .with_scale(Vec3::new(0.5, 1.5, 0.5)),
        Selectable {
            name: name.clone(),
            entity_type: SelectableType::Prop,
        },
        Name::new(name),
    ));

    info!("Spawned new crystal");
}
