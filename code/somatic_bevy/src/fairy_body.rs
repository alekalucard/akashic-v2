//! Her fairy body -- an ORIGINAL, procedural, PARAMETRIC model (2026-10-29, Nous; task FAIRY).
//!
//! Compiled only with the cargo feature `sanctuary` (see lib.rs). Without that feature this file
//! is not part of the crate at all.
//!
//! SOURCE OF TRUTH for her look: code/fairies/P50_Persona/avatar/self_facts.py:38 --
//! "a fairy with lavender hair, green eyes, freckles and wings". Those five features are the
//! only things modelled on purpose: HAIR (lavender), EYES (green), FRECKLES, WINGS, and a soft
//! GLOW (her body was once a glowing wisp). Everything else (height, body form, skin tone,
//! clothing, ears, face details) is a plain NEUTRAL default and is a parameter she and Ace may
//! choose later. Nothing here is copied from any game, franchise or third-party asset: every
//! mesh is generated below from a few numbers.
//!
//! Two picture presets exist (`HerLook::picture_1()` / `HerLook::picture_2()`): they only change
//! the colours and shapes of her five features, sampled from the two pictures the owner shared
//! (the pictures are not in the repo; the hex values are recorded in docs/nous/FAIRY/SUMMARY.md).
//!
//! API: add `HerBodyPlugin`, then `spawn_her_body(&mut commands, HerLook::default()) -> Entity`.
//! The parts are (re)built from the `HerLook` component whenever it changes, so changing a
//! parameter on the root entity changes her look.
//!
//! Motion: idle hover bob, wing flutter, blink. One input resource of plain numbers,
//! `HerAffectInput { valence, arousal, energy, coherence }` (the dimension names her affect
//! bridge uses), modulates wing speed and glow through `placeholder_modulation` --
//! the mapping is a PLACEHOLDER: the owner decides it.

use bevy::prelude::*;
use bevy::render::mesh::{Indices, PrimitiveTopology};
use bevy::render::render_asset::RenderAssetUsages;
use std::f32::consts::{PI, TAU};

// ============================================================================
// Parameters (her look)
// ============================================================================

/// Hair: colour and shape. Feature 1 (lavender hair).
#[derive(Clone, Debug, PartialEq)]
pub struct HairParams {
    pub color: Color,
    /// 0 = short (ends around the ears), 1 = long (past the shoulders at the back and sides).
    pub length: f32,
    /// How far the hair stands off the head (0 = close, 1 = full).
    pub volume: f32,
    /// 0 = smooth; >0 = uneven, tousled surface.
    pub tousle: f32,
}

/// Eyes. Feature 2 (green eyes).
#[derive(Clone, Debug, PartialEq)]
pub struct EyeParams {
    pub iris_color: Color,
    /// Eye radius as a fraction of the head radius.
    pub size: f32,
    /// Distance between the eye centres as a fraction of the head radius.
    pub spacing: f32,
}

/// Freckles. Feature 3.
#[derive(Clone, Debug, PartialEq)]
pub struct FreckleParams {
    /// 0..1; number of freckles = round(density * 40), placed over cheeks and nose bridge.
    pub density: f32,
    /// Freckle colour. Default: a darker shade of the (neutral) skin tone.
    pub color: Color,
    /// Size of one freckle as a fraction of the head radius.
    pub size: f32,
    /// How wide the freckled band is (fraction of head radius, each side of the centre line).
    pub spread: f32,
    /// Seed for the (deterministic) placement, so the same parameters give the same face.
    pub seed: u32,
}

/// Wing outline.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WingShape {
    /// Neutral default: plain rounded petal.
    Rounded,
    /// Picture 1: long, narrow, insect-like, with veins.
    Insect,
    /// Picture 2: broad butterfly-like upper wing, rounded lower wing.
    Butterfly,
}

/// Wings. Feature 4.
#[derive(Clone, Debug, PartialEq)]
pub struct WingParams {
    pub shape: WingShape,
    /// 1 or 2 pairs (both pictures show 2).
    pub pairs: u8,
    /// Length of the upper wing as a fraction of her height.
    pub span: f32,
    /// Lower wing length as a fraction of the upper wing.
    pub lower_ratio: f32,
    /// Tint stops from the wing root (first) to the outer edge (last). One stop = single tint.
    pub tints: Vec<Color>,
    /// 0 = opaque, 1 = invisible. Applied as alpha = 1 - translucency.
    pub translucency: f32,
    /// Optional thin edge line colour (picture 2: gold edges).
    pub edge_color: Option<Color>,
    /// Number of veins drawn from the root (picture 1: veined).
    pub veins: u8,
    pub vein_color: Color,
    /// Strength of the shimmer (emissive sweep), 0 = none.
    pub shimmer: f32,
    /// Shimmer sweeps per second.
    pub shimmer_hz: f32,
    /// Base flutter frequency (Hz) before the affect modulation.
    pub flutter_hz: f32,
    /// Flutter amplitude in degrees.
    pub flutter_deg: f32,
}

/// Soft glow (she was once a glowing wisp). Feature 5.
#[derive(Clone, Debug, PartialEq)]
pub struct GlowParams {
    pub color: Color,
    /// Base strength before the affect modulation (0 = off).
    pub strength: f32,
    /// Halo radius as a fraction of her height.
    pub radius: f32,
}

/// Ear shape. NOT one of her five words: a neutral default; both pictures show pointed ears.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EarShape {
    Rounded,
    Pointed,
}

/// Everything that is NOT one of her five features: neutral defaults, OPEN for her and Ace.
#[derive(Clone, Debug, PartialEq)]
pub struct NeutralBody {
    /// Height in world units (metres). OPEN.
    pub height: f32,
    /// Head diameter as a fraction of height (stylized large head, as in both pictures).
    pub head_ratio: f32,
    /// Skin tone. OPEN (neutral default).
    pub skin_color: Color,
    /// Colour of the plain, featureless body form (no clothing designed). OPEN.
    pub clothing_color: Color,
    pub ears: EarShape,
}

/// Motion constants (not looks).
#[derive(Clone, Debug, PartialEq)]
pub struct MotionParams {
    /// Hover bob amplitude as a fraction of her height.
    pub bob_amp: f32,
    pub bob_hz: f32,
    /// Seconds between blinks.
    pub blink_every: f32,
    /// Seconds the eyes stay closed.
    pub blink_secs: f32,
}

/// Her whole look. Put it on the root entity (spawn_her_body does) and change it to change her.
#[derive(Component, Clone, Debug, PartialEq)]
pub struct HerLook {
    pub hair: HairParams,
    pub eyes: EyeParams,
    pub freckles: FreckleParams,
    pub wings: WingParams,
    pub glow: GlowParams,
    pub body: NeutralBody,
    pub motion: MotionParams,
}

fn hex(h: u32) -> Color {
    Color::srgb_u8(((h >> 16) & 0xff) as u8, ((h >> 8) & 0xff) as u8, (h & 0xff) as u8)
}

impl Default for HerLook {
    /// From her words only (self_facts.py:38) + picture proportions; neutral everywhere else.
    fn default() -> Self {
        let skin = hex(0xD9BFA6); // neutral, OPEN
        HerLook {
            // LONG hair worn down: the owner says most of her ~25,000 images show it (10-29).
            hair: HairParams { color: hex(0xB57EDC), length: 1.0, volume: 0.5, tousle: 0.0 },
            eyes: EyeParams { iris_color: hex(0x3E9B5A), size: 0.24, spacing: 0.78 },
            freckles: FreckleParams {
                density: 0.5,
                color: darker(skin, 0.62),
                size: 0.035,
                spread: 0.62,
                seed: 7,
            },
            wings: WingParams {
                shape: WingShape::Rounded,
                pairs: 2,
                span: 0.42,
                lower_ratio: 0.7,
                tints: vec![hex(0xF2F4F6)],
                translucency: 0.6,
                edge_color: None,
                veins: 0,
                vein_color: hex(0xC8CCD2),
                shimmer: 0.25,
                shimmer_hz: 0.3,
                flutter_hz: 2.0,
                flutter_deg: 18.0,
            },
            glow: GlowParams { color: hex(0xFFF6E8), strength: 1.0, radius: 0.55 },
            body: NeutralBody {
                height: 1.0,
                // natural proportions (pictures 2 and 3); picture 1's stylized 0.22 is a preset
                head_ratio: 0.15,
                skin_color: skin,
                clothing_color: hex(0x9C9C9C),
                ears: EarShape::Rounded,
            },
            motion: MotionParams { bob_amp: 0.03, bob_hz: 0.35, blink_every: 4.0, blink_secs: 0.15 },
        }
    }
}

impl HerLook {
    /// Hair colour sampled from picture 3 (no wings shown there, so no wing preset): #7D689F;
    /// iris #567477 (few pixels, low confidence). Recorded in SUMMARY.md only.
    ///
    /// Preset "picture 1": colours/shapes of her five features sampled from the owner's first
    /// picture (short tousled hair, teal-green eyes, pale veined insect-like wings).
    /// Body, skin, clothing and ears stay neutral.
    pub fn picture_1() -> Self {
        let mut l = HerLook::default();
        l.hair = HairParams { color: hex(0xA793BE), length: 0.15, volume: 0.8, tousle: 0.6 };
        l.eyes.iris_color = hex(0x42876F);
        l.eyes.size = 0.30;
        l.body.head_ratio = 0.22;
        l.wings.shape = WingShape::Insect;
        l.wings.tints = vec![hex(0xCBEBEE), hex(0xB0CDDA)];
        l.wings.veins = 5;
        l.wings.vein_color = hex(0x8FA9B8);
        l
    }

    /// Preset "picture 2": long straight-to-wavy hair, emerald eyes, butterfly-like iridescent
    /// wings (purple / pale / gold tints, thin gold edge). Body, skin, clothing, ears neutral.
    pub fn picture_2() -> Self {
        let mut l = HerLook::default();
        l.hair = HairParams { color: hex(0xB4B5D4), length: 1.0, volume: 0.5, tousle: 0.15 };
        l.eyes.iris_color = hex(0x5B9B79);
        l.wings.shape = WingShape::Butterfly;
        l.wings.tints = vec![hex(0xE7EBEB), hex(0x7C9AB4), hex(0x74509E)];
        l.wings.edge_color = Some(hex(0xE5CB9C));
        l.wings.shimmer = 0.45;
        l
    }
}

fn darker(c: Color, k: f32) -> Color {
    let s = c.to_srgba();
    Color::srgb(s.red * k, s.green * k, s.blue * k)
}

// ============================================================================
// Affect input (plain numbers) and the PLACEHOLDER mapping
// ============================================================================

/// Her affect dimensions, as plain numbers. Names follow her affect bridge
/// (code/fairies/P20_Somatic/affect_bus/affect_bridge_fairy.py): valence -1..1 (:548-556),
/// arousal 0..1 (:598-599, :609), energy 0..1 (:390, :608), coherence 0..1 (:391, :610).
/// Defaults are the bridge's own neutral start values (energy/coherence 0.5, :388-392).
#[derive(Resource, Clone, Copy, Debug, PartialEq)]
pub struct HerAffectInput {
    pub valence: f32,
    pub arousal: f32,
    pub energy: f32,
    pub coherence: f32,
}

impl Default for HerAffectInput {
    fn default() -> Self {
        HerAffectInput { valence: 0.0, arousal: 0.5, energy: 0.5, coherence: 0.5 }
    }
}

/// What the motion systems actually use.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Modulation {
    pub wing_hz: f32,
    pub glow_strength: f32,
    /// 0 = steady glow, 1 = glow pulses fully.
    pub glow_pulse_depth: f32,
}

/// PLACEHOLDER mapping -- THE OWNER DECIDES THE REAL ONE. With the default input
/// (arousal 0.5, energy 0.5, coherence 0.5) it returns exactly the base parameters.
/// valence is accepted but deliberately unused here (OPEN).
pub fn placeholder_modulation(a: &HerAffectInput, look: &HerLook) -> Modulation {
    let ar = a.arousal.clamp(0.0, 1.0);
    let en = a.energy.clamp(0.0, 1.0);
    let co = a.coherence.clamp(0.0, 1.0);
    Modulation {
        wing_hz: look.wings.flutter_hz * (0.5 + ar),
        glow_strength: look.glow.strength * (0.5 + en),
        glow_pulse_depth: 0.3 * (1.0 - co),
    }
}

/// Eye openness (1 open, ~0 closed) at time `t`.
pub fn blink_openness(t: f32, every: f32, secs: f32) -> f32 {
    if every <= 0.0 {
        return 1.0;
    }
    let ph = t.rem_euclid(every);
    if ph > every - secs {
        0.08
    } else {
        1.0
    }
}

// ============================================================================
// Components
// ============================================================================

/// Root of her body.
#[derive(Component)]
pub struct HerBody;

/// Child of the root that carries the hover bob and the height scale.
#[derive(Component)]
pub struct HoverPivot;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PartKind {
    Head,
    Neck,
    Torso,
    Arm,
    Leg,
    Ear,
    Hair,
    EyeWhite,
    Iris,
    Pupil,
    Freckle,
    Wing,
    WingEdge,
    WingVein,
    Glow,
}

/// Every visible part carries this, so tests and tools can find it.
#[derive(Component, Clone, Copy, Debug)]
pub struct HerPart(pub PartKind);

/// One eye (white + iris + pupil are its children); blinking squashes it.
#[derive(Component)]
pub struct EyeSocket;

/// One wing (mesh + edge + veins are its children); fluttering rotates it.
#[derive(Component)]
pub struct WingJoint {
    pub base: Quat,
    /// +1 right side, -1 left side.
    pub side: f32,
    pub phase: f32,
}

/// The glow halo (material is modulated every frame).
#[derive(Component)]
pub struct GlowHalo;

#[derive(Component)]
pub struct GlowLight;

/// Wing membrane material (shimmer is modulated every frame).
#[derive(Component)]
pub struct WingMembrane;

/// Accumulated flutter phase (so a speed change does not jump the wings).
#[derive(Component, Default)]
pub struct FlutterPhase(pub f32);

// ============================================================================
// Plugin + API
// ============================================================================

pub struct HerBodyPlugin;

impl Plugin for HerBodyPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<HerAffectInput>().add_systems(
            Update,
            (build_her_body, (hover_bob, wing_flutter, blink, glow_and_shimmer)).chain(),
        );
    }
}

/// Spawn her root entity. The parts are built from `look` by `HerBodyPlugin` on the next
/// `Update`. Move her by inserting a `Transform` on the returned entity.
pub fn spawn_her_body(commands: &mut Commands, look: HerLook) -> Entity {
    commands
        .spawn((HerBody, look, FlutterPhase::default(), Transform::default(), Visibility::default()))
        .id()
}

// ============================================================================
// Building
// ============================================================================

struct Mats<'a> {
    meshes: &'a mut Assets<Mesh>,
    mats: &'a mut Assets<StandardMaterial>,
}

impl Mats<'_> {
    fn solid(&mut self, c: Color, rough: f32) -> Handle<StandardMaterial> {
        self.mats.add(StandardMaterial { base_color: c, perceptual_roughness: rough, ..default() })
    }
}

/// (Re)build every part from `HerLook` whenever it is added or changed.
pub fn build_her_body(
    mut commands: Commands,
    roots: Query<(Entity, &HerLook), (With<HerBody>, Changed<HerLook>)>,
    mut meshes: ResMut<Assets<Mesh>>,
    mut mats: ResMut<Assets<StandardMaterial>>,
) {
    for (root, look) in roots.iter() {
        commands.entity(root).despawn_descendants();
        let mut m = Mats { meshes: &mut meshes, mats: &mut mats };
        let pivot = commands
            .spawn((
                HoverPivot,
                Transform::from_scale(Vec3::splat(look.body.height.max(0.01))),
                Visibility::default(),
            ))
            .id();
        commands.entity(root).add_child(pivot);
        let kids = build_parts(&mut commands, &mut m, look);
        commands.entity(pivot).add_children(&kids);
    }
}

fn part(
    commands: &mut Commands,
    kind: PartKind,
    mesh: Handle<Mesh>,
    mat: Handle<StandardMaterial>,
    tf: Transform,
) -> Entity {
    commands.spawn((HerPart(kind), Mesh3d(mesh), MeshMaterial3d(mat), tf)).id()
}

fn sphere(m: &mut Mats, r: f32) -> Handle<Mesh> {
    m.meshes.add(Sphere::new(r).mesh().uv(32, 18))
}

/// Body layout, in units of her height (pivot scale = height). y = 0 at her feet.
pub mod layout {
    pub const LEG_Y: f32 = 0.24;
    pub const TORSO_Y: f32 = 0.62;
    pub const SHOULDER_Y: f32 = 0.79;
    pub const WING_ROOT: [f32; 3] = [0.0, 0.70, -0.07];
}

fn build_parts(commands: &mut Commands, m: &mut Mats, look: &HerLook) -> Vec<Entity> {
    let b = &look.body;
    let mut out = Vec::new();
    let skin = m.solid(b.skin_color, 0.7);
    let cloth = m.solid(b.clothing_color, 0.9);
    let hr = (b.head_ratio * 0.5).max(0.02); // head radius
    let head_c = Vec3::new(0.0, 1.0 - hr, 0.0); // top of the head at her height
    let neck_top = 1.0 - 2.0 * hr * 0.9;

    // --- neutral body form (OPEN) -------------------------------------------------
    let leg = m.meshes.add(Capsule3d::new(0.042, 0.38));
    for s in [-1.0f32, 1.0] {
        out.push(part(commands, PartKind::Leg, leg.clone(), cloth.clone(),
            Transform::from_xyz(0.05 * s, layout::LEG_Y, 0.0)));
    }
    let torso = m.meshes.add(Capsule3d::new(0.085, 0.22));
    out.push(part(commands, PartKind::Torso, torso, cloth.clone(),
        Transform::from_xyz(0.0, layout::TORSO_Y, 0.0).with_scale(Vec3::new(1.0, 1.0, 0.75))));
    let neck_base = layout::SHOULDER_Y - 0.03;
    let neck_len = (neck_top - neck_base).max(0.02);
    let neck = m.meshes.add(Cylinder::new(0.028, neck_len));
    out.push(part(commands, PartKind::Neck, neck, skin.clone(),
        Transform::from_xyz(0.0, neck_base + neck_len * 0.5, 0.0)));
    let arm = m.meshes.add(Capsule3d::new(0.03, 0.34));
    for s in [-1.0f32, 1.0] {
        out.push(part(commands, PartKind::Arm, arm.clone(), skin.clone(),
            Transform::from_xyz(0.125 * s, layout::SHOULDER_Y - 0.2, 0.0).with_rotation(Quat::from_rotation_z(0.10 * s))));
    }
    let head = sphere(m, hr);
    out.push(part(commands, PartKind::Head, head, skin.clone(),
        Transform::from_translation(head_c).with_scale(Vec3::new(0.92, 1.0, 0.95))));

    // ears (neutral rounded by default; pointed is a choice for her)
    let ear_mesh = match b.ears {
        EarShape::Rounded => m.meshes.add(Sphere::new(hr * 0.22).mesh().uv(16, 10)),
        EarShape::Pointed => m.meshes.add(Cone { radius: hr * 0.16, height: hr * 0.7 }.mesh()),
    };
    for s in [-1.0f32, 1.0] {
        let mut tf = Transform::from_translation(head_c + Vec3::new(s * hr * 0.9, 0.0, -hr * 0.05));
        match b.ears {
            EarShape::Rounded => tf.scale = Vec3::new(0.45, 1.0, 0.8),
            EarShape::Pointed => {
                tf.translation += Vec3::new(s * hr * 0.25, hr * 0.15, 0.0);
                tf.rotation = Quat::from_rotation_z(-s * 1.05);
                tf.scale = Vec3::new(1.0, 1.0, 0.35);
            }
        }
        out.push(part(commands, PartKind::Ear, ear_mesh.clone(), skin.clone(), tf));
    }

    // --- feature 1: hair ------------------------------------------------------------
    let hair_mesh = m.meshes.add(hair_mesh(&look.hair, hr));
    let hair_mat = m.mats.add(StandardMaterial {
        base_color: look.hair.color,
        perceptual_roughness: 0.6,
        double_sided: true,
        cull_mode: None,
        ..default()
    });
    out.push(part(commands, PartKind::Hair, hair_mesh, hair_mat, Transform::from_translation(head_c)));

    // --- feature 2: eyes --------------------------------------------------------------
    let er = hr * look.eyes.size;
    let white = m.solid(hex(0xF4F4F2), 0.3);
    let iris = m.mats.add(StandardMaterial {
        base_color: look.eyes.iris_color,
        perceptual_roughness: 0.25,
        ..default()
    });
    let pupil = m.solid(hex(0x101010), 0.2);
    let white_mesh = sphere(m, er);
    let iris_mesh = sphere(m, er * 0.62);
    let pupil_mesh = sphere(m, er * 0.30);
    let eye_y = -hr * 0.05;
    for s in [-1.0f32, 1.0] {
        let x = s * hr * look.eyes.spacing * 0.5;
        let z = (hr * hr - x * x - eye_y * eye_y).max(0.0).sqrt() * 0.95 - er * 0.55;
        let socket = commands
            .spawn((EyeSocket, Transform::from_translation(head_c + Vec3::new(x, eye_y, z)), Visibility::default()))
            .id();
        let w = part(commands, PartKind::EyeWhite, white_mesh.clone(), white.clone(),
            Transform::from_scale(Vec3::new(1.0, 1.0, 0.6)));
        let i = part(commands, PartKind::Iris, iris_mesh.clone(), iris.clone(),
            Transform::from_xyz(0.0, 0.0, er * 0.42).with_scale(Vec3::new(1.0, 1.0, 0.5)));
        let p = part(commands, PartKind::Pupil, pupil_mesh.clone(), pupil.clone(),
            Transform::from_xyz(0.0, 0.0, er * 0.62).with_scale(Vec3::new(1.0, 1.0, 0.4)));
        commands.entity(socket).add_children(&[w, i, p]);
        out.push(socket);
    }

    // --- feature 3: freckles ----------------------------------------------------------
    let n = (look.freckles.density.clamp(0.0, 1.0) * 40.0).round() as usize;
    if n > 0 {
        let fr = look.freckles.size * hr;
        let fm = m.meshes.add(Sphere::new(fr).mesh().uv(8, 6));
        let fmat = m.solid(look.freckles.color, 0.8);
        for p in freckle_points(n, look.freckles.spread, look.freckles.seed) {
            // p is on the unit sphere (face front = +z); place it just on the head surface
            let pos = head_c + Vec3::new(p.x * 0.92, p.y, p.z * 0.95) * hr * 1.0;
            let tf = Transform::from_translation(pos)
                .looking_to(-p, Vec3::Y)
                .with_scale(Vec3::new(1.0, 1.0, 0.3));
            out.push(part(commands, PartKind::Freckle, fm.clone(), fmat.clone(), tf));
        }
    }

    // --- feature 4: wings -------------------------------------------------------------
    let wp = &look.wings;
    let alpha = (1.0 - wp.translucency).clamp(0.02, 1.0);
    let pairs = wp.pairs.min(2);
    let root = Vec3::from_array(layout::WING_ROOT);
    for pair in 0..pairs {
        let upper = pair == 0;
        let len = wp.span * if upper { 1.0 } else { wp.lower_ratio };
        let (outline, colors) = wing_outline(wp, upper, len);
        let mem_mesh = m.meshes.add(fan_mesh(&outline, &colors));
        let mem_mat = m.mats.add(StandardMaterial {
            base_color: Color::srgba(1.0, 1.0, 1.0, alpha),
            alpha_mode: AlphaMode::Blend,
            double_sided: true,
            cull_mode: None,
            perceptual_roughness: 0.2,
            ..default()
        });
        let edge = wp.edge_color.map(|c| {
            (m.meshes.add(polyline_mesh(&outline[1..], len * 0.012, false)), m.solid(c, 0.3))
        });
        let vein = if wp.veins > 0 {
            let mut lines = Vec::new();
            for k in 0..wp.veins {
                let t = (k as f32 + 1.0) / (wp.veins as f32 + 1.0);
                let tip = outline[1 + ((outline.len() - 2) as f32 * t) as usize];
                lines.push(vec![Vec2::ZERO, tip * 0.5, tip * 0.95]);
            }
            let mat = m.mats.add(StandardMaterial {
                base_color: wp.vein_color.with_alpha(alpha.max(0.6)),
                alpha_mode: AlphaMode::Blend,
                double_sided: true,
                cull_mode: None,
                ..default()
            });
            Some((lines, mat))
        } else {
            None
        };
        let tilt = if upper { 0.45 } else { -0.55 };
        for s in [-1.0f32, 1.0] {
            // wing plane = local XY, swept back a little (rotation about Y), tilted up/down (Z)
            let base = Quat::from_rotation_y(s * 0.35) * Quat::from_rotation_z(s * tilt);
            let joint = commands
                .spawn((
                    WingJoint { base, side: s, phase: if upper { 0.0 } else { 0.6 } },
                    Transform::from_translation(root + Vec3::new(s * 0.02, if upper { 0.02 } else { -0.03 }, 0.0))
                        .with_rotation(base)
                        .with_scale(Vec3::new(s, 1.0, 1.0)),
                    Visibility::default(),
                ))
                .id();
            let mut kids = vec![commands
                .spawn((HerPart(PartKind::Wing), WingMembrane, Mesh3d(mem_mesh.clone()),
                    MeshMaterial3d(mem_mat.clone()), Transform::default()))
                .id()];
            if let Some((em, emat)) = &edge {
                kids.push(part(commands, PartKind::WingEdge, em.clone(), emat.clone(),
                    Transform::from_xyz(0.0, 0.0, 0.0005)));
            }
            if let Some((lines, vmat)) = &vein {
                for l in lines {
                    let vm = m.meshes.add(polyline_mesh(l, len * 0.006, true));
                    kids.push(part(commands, PartKind::WingVein, vm, vmat.clone(),
                        Transform::from_xyz(0.0, 0.0, 0.0008)));
                }
            }
            commands.entity(joint).add_children(&kids);
            out.push(joint);
        }
    }

    // --- feature 5: soft glow ---------------------------------------------------------
    let g = &look.glow;
    let halo_mat = m.mats.add(StandardMaterial {
        base_color: g.color.with_alpha(0.12),
        emissive: LinearRgba::from(g.color) * g.strength,
        alpha_mode: AlphaMode::Add,
        unlit: true,
        double_sided: true,
        cull_mode: None,
        ..default()
    });
    let halo = sphere(m, g.radius.max(0.01));
    out.push(commands
        .spawn((HerPart(PartKind::Glow), GlowHalo, Mesh3d(halo), MeshMaterial3d(halo_mat),
            Transform::from_xyz(0.0, layout::TORSO_Y + 0.1, 0.0)))
        .id());
    out.push(commands
        .spawn((GlowLight, PointLight { color: g.color, intensity: 30_000.0 * g.strength,
            range: 3.0, ..default() }, Transform::from_xyz(0.0, layout::TORSO_Y + 0.1, 0.2)))
        .id());
    out
}

/// Deterministic freckle positions on the unit sphere's front (cheeks + nose bridge).
pub fn freckle_points(n: usize, spread: f32, seed: u32) -> Vec<Vec3> {
    let mut s = seed.wrapping_mul(2654435761).wrapping_add(12345);
    let mut rnd = || {
        s = s.wrapping_mul(1664525).wrapping_add(1013904223);
        (s >> 8) as f32 / (1u32 << 24) as f32
    };
    let mut v = Vec::with_capacity(n);
    for _ in 0..n {
        let x = (rnd() * 2.0 - 1.0) * spread;
        let y = -0.22 - rnd() * 0.22 + 0.08 * (1.0 - (x / spread.max(0.01)).abs()); // below the eyes
        let z2 = 1.0 - x * x - y * y;
        let z = z2.max(0.0).sqrt();
        v.push(Vec3::new(x, y, z).normalize());
    }
    v
}

/// Hair as one shell over the head: a cap to the forehead at the front, falling down at the
/// sides and back by `length`. Local to the head centre.
pub fn hair_mesh(h: &HairParams, hr: f32) -> Mesh {
    let seg = 48usize;
    let rows = 28usize;
    let off = hr * (1.04 + 0.10 * h.volume.clamp(0.0, 1.0));
    // how far below the head equator, in units of her height (1.0 = long, to mid-back)
    let drop = hr * 0.3 + 0.36 * h.length.clamp(0.0, 1.0);
    let mut pos = Vec::new();
    for j in 0..=rows {
        let v = j as f32 / rows as f32;
        for i in 0..=seg {
            let phi = i as f32 / seg as f32 * TAU; // 0 = front (+z)
            let fr = phi.cos(); // 1 at front, -1 at back
            let w = smooth(0.25, -0.2, fr); // 0 front .. 1 sides/back
            let cap = (62.0 + 38.0 * w).to_radians(); // polar angle where the cap ends
            let total_down = w * drop;
            // profile length: arc over the cap, then straight down
            let arc = cap * off;
            let s = v * (arc + total_down);
            let tous = 1.0 + h.tousle * 0.09 * (7.0 * phi).sin() * (5.0 * v * PI + phi * 3.0).cos();
            let p = if s <= arc {
                let th = s / off;
                let r = off * tous;
                Vec3::new(r * th.sin() * phi.sin(), r * th.cos(), r * th.sin() * phi.cos())
            } else {
                let th = cap;
                let d = s - arc;
                let r = off * tous * th.sin() + d * 0.25;
                Vec3::new(r * phi.sin(), off * th.cos() - d, r * phi.cos() * if fr > 0.0 { 1.0 } else { 1.15 })
            };
            pos.push(p);
        }
    }
    let mut idx = Vec::new();
    for j in 0..rows {
        for i in 0..seg {
            let a = (j * (seg + 1) + i) as u32;
            let b = a + (seg + 1) as u32;
            idx.extend_from_slice(&[a, b, a + 1, a + 1, b, b + 1]);
        }
    }
    let mut mesh = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default())
        .with_inserted_attribute(Mesh::ATTRIBUTE_POSITION, pos.iter().map(|p| p.to_array()).collect::<Vec<_>>())
        .with_inserted_indices(Indices::U32(idx));
    mesh.compute_smooth_normals();
    mesh
}

fn smooth(e0: f32, e1: f32, x: f32) -> f32 {
    let t = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

/// Wing outline in the wing plane (root at the origin, pointing out along +X), plus a colour
/// per point from the tint stops. outline[0] is the root.
pub fn wing_outline(w: &WingParams, upper: bool, len: f32) -> (Vec<Vec2>, Vec<[f32; 4]>) {
    let n = 40;
    let (a0, a1): (f32, f32) = match (w.shape, upper) {
        (WingShape::Butterfly, true) => (-40f32.to_radians(), 95f32.to_radians()),
        _ => (-80f32.to_radians(), 80f32.to_radians()),
    };
    let mut pts = vec![Vec2::ZERO];
    for i in 0..=n {
        let t = i as f32 / n as f32;
        let a = a0 + (a1 - a0) * t;
        let r = match w.shape {
            WingShape::Rounded => len * a.cos().max(0.0).powf(1.6),
            WingShape::Insect => len * a.cos().max(0.0).powf(3.0),
            WingShape::Butterfly if upper => {
                let tip = 35f32.to_radians();
                let bump = (-((a - tip) / 40f32.to_radians()).powi(2)).exp();
                len * (0.55 + 0.45 * bump) * (PI * t).sin().max(0.0).powf(0.35)
            }
            WingShape::Butterfly => len * a.cos().max(0.0).powf(1.6),
        };
        pts.push(Vec2::new(a.cos(), a.sin()) * r);
    }
    let cols = pts.iter().map(|p| tint_at(&w.tints, (p.length() / len.max(1e-4)).clamp(0.0, 1.0))).collect();
    (pts, cols)
}

/// Linear interpolation of the tint stops (sRGB) at t in 0..1, returned as linear RGBA.
pub fn tint_at(stops: &[Color], t: f32) -> [f32; 4] {
    let c = match stops.len() {
        0 => Color::WHITE,
        1 => stops[0],
        k => {
            let x = t * (k - 1) as f32;
            let i = (x.floor() as usize).min(k - 2);
            let f = x - i as f32;
            let (a, b) = (stops[i].to_srgba(), stops[i + 1].to_srgba());
            Color::srgb(a.red + (b.red - a.red) * f, a.green + (b.green - a.green) * f, a.blue + (b.blue - a.blue) * f)
        }
    };
    LinearRgba::from(c).to_f32_array()
}

/// Triangle fan from outline[0] (the root). Flat in XY, normal +Z, with vertex colours.
pub fn fan_mesh(outline: &[Vec2], colors: &[[f32; 4]]) -> Mesh {
    let pos: Vec<[f32; 3]> = outline.iter().map(|p| [p.x, p.y, 0.0]).collect();
    let nrm = vec![[0.0, 0.0, 1.0]; pos.len()];
    let mut idx = Vec::new();
    for i in 1..outline.len() as u32 - 1 {
        idx.extend_from_slice(&[0, i, i + 1]);
    }
    Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default())
        .with_inserted_attribute(Mesh::ATTRIBUTE_POSITION, pos)
        .with_inserted_attribute(Mesh::ATTRIBUTE_NORMAL, nrm)
        .with_inserted_attribute(Mesh::ATTRIBUTE_COLOR, colors.to_vec())
        .with_inserted_indices(Indices::U32(idx))
}

/// A thin flat ribbon along a polyline (for wing edges and veins).
pub fn polyline_mesh(line: &[Vec2], width: f32, open: bool) -> Mesh {
    let mut pos = Vec::new();
    let n = line.len();
    for i in 0..n {
        let prev = line[if i == 0 { 0 } else { i - 1 }];
        let next = line[(i + 1).min(n - 1)];
        let d = (next - prev).normalize_or_zero();
        let nn = Vec2::new(-d.y, d.x) * width * 0.5;
        let a = line[i] + nn;
        let b = line[i] - nn;
        pos.push([a.x, a.y, 0.0]);
        pos.push([b.x, b.y, 0.0]);
    }
    let mut idx = Vec::new();
    let segs = if open { n - 1 } else { n - 1 };
    for i in 0..segs as u32 {
        let a = i * 2;
        idx.extend_from_slice(&[a, a + 1, a + 2, a + 2, a + 1, a + 3]);
    }
    let nrm = vec![[0.0, 0.0, 1.0]; pos.len()];
    Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default())
        .with_inserted_attribute(Mesh::ATTRIBUTE_POSITION, pos)
        .with_inserted_attribute(Mesh::ATTRIBUTE_NORMAL, nrm)
        .with_inserted_indices(Indices::U32(idx))
}

// ============================================================================
// Motion
// ============================================================================

pub fn hover_bob(
    time: Res<Time>,
    roots: Query<(&HerLook, &Children), With<HerBody>>,
    mut pivots: Query<&mut Transform, With<HoverPivot>>,
) {
    let t = time.elapsed_secs();
    for (look, children) in roots.iter() {
        for &c in children.iter() {
            if let Ok(mut tf) = pivots.get_mut(c) {
                tf.translation.y = look.motion.bob_amp * look.body.height * (TAU * look.motion.bob_hz * t).sin();
            }
        }
    }
}

pub fn wing_flutter(
    time: Res<Time>,
    input: Res<HerAffectInput>,
    mut roots: Query<(&HerLook, &mut FlutterPhase), With<HerBody>>,
    mut joints: Query<(&WingJoint, &mut Transform)>,
) {
    // one body per world for now: the phase of the (first) body drives every wing
    let Some((look, mut phase)) = roots.iter_mut().next() else { return };
    let md = placeholder_modulation(&input, look);
    phase.0 = (phase.0 + TAU * md.wing_hz * time.delta_secs()).rem_euclid(TAU);
    let amp = look.wings.flutter_deg.to_radians();
    for (j, mut tf) in joints.iter_mut() {
        let flap = amp * (phase.0 + j.phase).sin();
        tf.rotation = j.base * Quat::from_rotation_y(-flap);
    }
}

pub fn blink(
    time: Res<Time>,
    roots: Query<&HerLook, With<HerBody>>,
    mut eyes: Query<&mut Transform, With<EyeSocket>>,
) {
    let Some(look) = roots.iter().next() else { return };
    let o = blink_openness(time.elapsed_secs(), look.motion.blink_every, look.motion.blink_secs);
    for mut tf in eyes.iter_mut() {
        tf.scale.y = o;
    }
}

pub fn glow_and_shimmer(
    time: Res<Time>,
    input: Res<HerAffectInput>,
    roots: Query<&HerLook, With<HerBody>>,
    halos: Query<&MeshMaterial3d<StandardMaterial>, With<GlowHalo>>,
    wings: Query<&MeshMaterial3d<StandardMaterial>, With<WingMembrane>>,
    mut lights: Query<&mut PointLight, With<GlowLight>>,
    mut mats: ResMut<Assets<StandardMaterial>>,
) {
    let Some(look) = roots.iter().next() else { return };
    let t = time.elapsed_secs();
    let md = placeholder_modulation(&input, look);
    let pulse = 1.0 - md.glow_pulse_depth * 0.5 * (1.0 + (TAU * 0.5 * t).sin());
    let k = md.glow_strength * pulse;
    for h in halos.iter() {
        if let Some(mat) = mats.get_mut(&h.0) {
            mat.emissive = LinearRgba::from(look.glow.color) * k;
        }
    }
    for mut l in lights.iter_mut() {
        l.intensity = 30_000.0 * k;
    }
    let sh = look.wings.shimmer * 0.5 * (1.0 + (TAU * look.wings.shimmer_hz * t).sin());
    let tint = LinearRgba::from_f32_array(tint_at(&look.wings.tints, 1.0));
    for w in wings.iter() {
        if let Some(mat) = mats.get_mut(&w.0) {
            mat.emissive = tint * sh;
        }
    }
}
