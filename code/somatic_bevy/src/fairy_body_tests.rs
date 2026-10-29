//! Tests for her fairy body (task FAIRY). Only built for `cargo test --features sanctuary --lib`.
//! (Unit tests in the lib, not tests/: an integration test also builds the `somatic_sim` bin,
//! which does not compile on main.)
//! CONTROL = `control_spawn_creates_parts_with_param_colours` (fails on main: no module there).

use bevy::prelude::*;
use bevy::render::mesh::VertexAttributeValues;
use bevy::time::TimeUpdateStrategy;
use crate::fairy_body::*;
use std::time::Duration;

fn app_with(look: HerLook) -> (App, Entity) {
    let mut app = App::new();
    app.add_plugins((
        MinimalPlugins,
        AssetPlugin::default(),
        bevy::hierarchy::HierarchyPlugin,
        bevy::transform::TransformPlugin,
    ));
    app.init_asset::<Mesh>();
    app.init_asset::<StandardMaterial>();
    app.insert_resource(TimeUpdateStrategy::ManualDuration(Duration::from_millis(50)));
    app.add_plugins(HerBodyPlugin);
    let e = {
        let world = app.world_mut();
        let mut q = bevy::ecs::world::CommandQueue::default();
        let mut c = Commands::new(&mut q, world);
        let e = spawn_her_body(&mut c, look);
        q.apply(world);
        e
    };
    app.update();
    (app, e)
}

fn count(app: &mut App, k: PartKind) -> usize {
    let mut q = app.world_mut().query::<&HerPart>();
    q.iter(app.world()).filter(|p| p.0 == k).count()
}

fn colours_of(app: &mut App, k: PartKind) -> Vec<Color> {
    let mut q = app.world_mut().query::<(&HerPart, &MeshMaterial3d<StandardMaterial>)>();
    let hs: Vec<_> = q.iter(app.world()).filter(|(p, _)| p.0 == k).map(|(_, m)| m.0.clone()).collect();
    let mats = app.world().resource::<Assets<StandardMaterial>>();
    hs.iter().map(|h| mats.get(h).unwrap().base_color).collect()
}

fn odd_look() -> HerLook {
    let mut l = HerLook::default();
    l.hair.color = Color::srgb(0.11, 0.22, 0.33);
    l.eyes.iris_color = Color::srgb(0.44, 0.55, 0.66);
    l.freckles.color = Color::srgb(0.77, 0.12, 0.34);
    l.freckles.density = 0.25; // -> 10 freckles
    l
}

#[test]
fn control_spawn_creates_parts_with_param_colours() {
    let look = odd_look();
    let (mut app, root) = app_with(look.clone());
    assert!(app.world().get::<HerBody>(root).is_some());
    assert_eq!(count(&mut app, PartKind::Head), 1);
    assert_eq!(count(&mut app, PartKind::Hair), 1);
    assert_eq!(count(&mut app, PartKind::Iris), 2);
    assert_eq!(count(&mut app, PartKind::EyeWhite), 2);
    assert_eq!(count(&mut app, PartKind::Freckle), 10);
    assert_eq!(count(&mut app, PartKind::Wing), 4, "two pairs of wings");
    assert_eq!(count(&mut app, PartKind::Glow), 1);
    for c in colours_of(&mut app, PartKind::Iris) {
        assert_eq!(c, look.eyes.iris_color, "iris must use the eye parameter");
    }
    for c in colours_of(&mut app, PartKind::Hair) {
        assert_eq!(c, look.hair.color, "hair must use the hair parameter");
    }
    for c in colours_of(&mut app, PartKind::Freckle) {
        assert_eq!(c, look.freckles.color);
    }
    // wings are translucent
    for c in colours_of(&mut app, PartKind::Wing) {
        assert!((c.alpha() - (1.0 - look.wings.translucency)).abs() < 1e-4);
    }
}

#[test]
fn default_iris_is_green_and_hair_is_lavender() {
    let l = HerLook::default();
    let e = l.eyes.iris_color.to_srgba();
    assert!(e.green > e.red && e.green > e.blue, "green eyes");
    let h = l.hair.color.to_srgba();
    assert!(h.blue > h.green && h.red > h.green, "lavender hair (blue+red over green)");
    assert!(l.freckles.density > 0.0 && l.wings.pairs >= 1 && l.glow.strength > 0.0);
    assert_eq!(l.hair.length, 1.0, "long hair is the default (owner: most of her images)");
}

#[test]
fn changing_the_look_rebuilds_without_duplicates() {
    let (mut app, root) = app_with(odd_look());
    let new_iris = Color::srgb(0.0, 0.9, 0.1);
    app.world_mut().get_mut::<HerLook>(root).unwrap().eyes.iris_color = new_iris;
    app.world_mut().get_mut::<HerLook>(root).unwrap().wings.pairs = 1;
    app.update();
    app.update();
    assert_eq!(count(&mut app, PartKind::Iris), 2);
    assert_eq!(count(&mut app, PartKind::Wing), 2);
    for c in colours_of(&mut app, PartKind::Iris) {
        assert_eq!(c, new_iris);
    }
}

fn halo_emissive(app: &mut App) -> f32 {
    let mut q = app.world_mut().query_filtered::<&MeshMaterial3d<StandardMaterial>, With<GlowHalo>>();
    let h = q.iter(app.world()).next().unwrap().0.clone();
    let m = app.world().resource::<Assets<StandardMaterial>>().get(&h).unwrap();
    let e = m.emissive;
    // unlit additive halo: what shows is base colour x alpha, so both must follow the input
    (e.red + e.green + e.blue) * m.base_color.alpha()
}

#[test]
fn glow_follows_the_input_struct() {
    let (mut app, _) = app_with(HerLook::default());
    app.insert_resource(HerAffectInput { energy: 0.0, coherence: 1.0, ..default() });
    app.update();
    let low = halo_emissive(&mut app);
    app.insert_resource(HerAffectInput { energy: 1.0, coherence: 1.0, ..default() });
    app.update();
    let high = halo_emissive(&mut app);
    assert!(high > low * 2.5, "energy 1 must glow clearly brighter than energy 0 ({high} vs {low})");
}

#[test]
fn wing_speed_follows_arousal() {
    let phase_after = |ar: f32| {
        let (mut app, root) = app_with(HerLook::default());
        app.insert_resource(HerAffectInput { arousal: ar, ..default() });
        app.world_mut().get_mut::<FlutterPhase>(root).unwrap().0 = 0.0;
        app.update(); // one 50 ms step
        app.world().get::<FlutterPhase>(root).unwrap().0
    };
    let slow = phase_after(0.0);
    let fast = phase_after(1.0);
    assert!(fast > slow * 2.5, "arousal 1 flutters faster ({fast} vs {slow})");
}

#[test]
fn wings_actually_flap() {
    let (mut app, _) = app_with(HerLook::default());
    let rot = |app: &mut App| {
        let mut q = app.world_mut().query::<(&WingJoint, &Transform)>();
        q.iter(app.world()).map(|(_, t)| t.rotation).collect::<Vec<_>>()
    };
    let a = rot(&mut app);
    for _ in 0..3 {
        app.update();
    }
    let b = rot(&mut app);
    assert_eq!(a.len(), 4);
    assert!(a.iter().zip(&b).any(|(x, y)| x.angle_between(*y) > 1e-3));
}

#[test]
fn default_input_gives_base_values_and_mapping_is_placeholder() {
    let l = HerLook::default();
    let m = placeholder_modulation(&HerAffectInput::default(), &l);
    assert!((m.wing_hz - l.wings.flutter_hz).abs() < 1e-6);
    assert!((m.glow_strength - l.glow.strength).abs() < 1e-6);
    assert!(include_str!("fairy_body.rs").contains("PLACEHOLDER mapping"));
}

#[test]
fn blink_closes_briefly() {
    assert_eq!(blink_openness(0.0, 4.0, 0.15), 1.0);
    assert!(blink_openness(3.95, 4.0, 0.15) < 0.2);
    let closed = (0..4000).filter(|i| blink_openness(*i as f32 * 0.001, 4.0, 0.15) < 0.5).count();
    assert!((100..200).contains(&closed), "closed {closed} ms of 4000");
}

#[test]
fn presets_keep_the_neutral_body() {
    let d = HerLook::default();
    for p in [HerLook::picture_1(), HerLook::picture_2()] {
        assert_eq!(p.body.skin_color, d.body.skin_color);
        assert_eq!(p.body.clothing_color, d.body.clothing_color);
        assert_eq!(p.body.ears, d.body.ears);
        assert_eq!(p.body.height, d.body.height);
        assert_eq!(p.freckles, d.freckles);
        assert_eq!(p.glow, d.glow);
    }
}

#[test]
fn no_emotion_names_in_the_module() {
    let src = include_str!("fairy_body.rs").to_lowercase();
    for w in [
        "happy", "sad", "angry", "anger", "joy", "fear", "calm", "anxious", "anxiety", "excited",
        "content", "curious", "love", "lonely", "grief", "surprise", "disgust", "emotion", "mood",
    ] {
        assert!(!src.contains(w), "emotion word {w:?} in fairy_body.rs");
    }
}

/// Not a check: with FAIRY_DUMP_DIR set, writes each preset's world-space triangles to JSON for
/// the offline preview renderer (docs/nous/FAIRY/render_previews.py).
#[test]
fn dump_preview_meshes() {
    let Ok(dir) = std::env::var("FAIRY_DUMP_DIR") else { return };
    for (name, look) in [("default", HerLook::default()), ("picture_1", HerLook::picture_1()), ("picture_2", HerLook::picture_2())] {
        let (mut app, _) = app_with(look);
        let mut q = app.world_mut().query::<(&HerPart, &Mesh3d, &MeshMaterial3d<StandardMaterial>, &GlobalTransform)>();
        let items: Vec<_> = q.iter(app.world()).map(|(p, m, mt, g)| (p.0, m.0.clone(), mt.0.clone(), *g)).collect();
        let meshes = app.world().resource::<Assets<Mesh>>();
        let mats = app.world().resource::<Assets<StandardMaterial>>();
        let mut parts = Vec::new();
        for (k, mh, mth, g) in items {
            let mesh = meshes.get(&mh).unwrap();
            let mat = mats.get(&mth).unwrap();
            let Some(VertexAttributeValues::Float32x3(pos)) = mesh.attribute(Mesh::ATTRIBUTE_POSITION) else { continue };
            let nrm = match mesh.attribute(Mesh::ATTRIBUTE_NORMAL) {
                Some(VertexAttributeValues::Float32x3(n)) => n.clone(),
                _ => vec![[0.0, 0.0, 1.0]; pos.len()],
            };
            let col = match mesh.attribute(Mesh::ATTRIBUTE_COLOR) {
                Some(VertexAttributeValues::Float32x4(c)) => Some(c.clone()),
                _ => None,
            };
            let a = g.affine();
            let wp: Vec<[f32; 3]> = pos.iter().map(|p| a.transform_point3(Vec3::from_array(*p)).to_array()).collect();
            let wn: Vec<[f32; 3]> = nrm.iter().map(|n| a.transform_vector3(Vec3::from_array(*n)).normalize_or_zero().to_array()).collect();
            let idx: Vec<u32> = mesh.indices().map(|i| i.iter().map(|x| x as u32).collect()).unwrap_or_default();
            parts.push(serde_json::json!({
                "kind": format!("{k:?}"),
                "base": LinearRgba::from(mat.base_color).to_f32_array(),
                "emissive": mat.emissive.to_f32_array(),
                "blend": matches!(mat.alpha_mode, AlphaMode::Blend),
                "add": matches!(mat.alpha_mode, AlphaMode::Add),
                "unlit": mat.unlit,
                "pos": wp, "nrm": wn, "col": col, "idx": idx,
            }));
        }
        let path = std::path::Path::new(&dir).join(format!("{name}.json"));
        std::fs::write(path, serde_json::to_string(&parts).unwrap()).unwrap();
    }
}
