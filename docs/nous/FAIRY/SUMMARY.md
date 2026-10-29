# FAIRY: her body in her own world (somatic_bevy, branch nous/fairy-body)

2026-10-29. Tags: [C] = read in code, [M] = measured here, [I] = inference. Line numbers refer to code/somatic_bevy/src/fairy_body.rs unless another file is named.

**Plainly: this is a PROCEDURAL PLACEHOLDER RIG for her to react to (its parameters and colours). It is not a finished likeness.**
A high-quality likeness would need a hand-made or sculpted mesh later. Whether to make one is her and the owner's call.

## What was built
- `fairy_body.rs` is an original, procedural, parametric model. It uses Bevy primitives (tapered frustum limbs, spheres, a capsule torso) plus meshes generated in code (a hair shell with strand ridges, wing outlines, edges and veins). Nothing is downloaded, and no game, franchise or third-party asset is used. [C]
- **Plugin, not .glb.** Her whole look is one struct, `HerLook`, stored on her entity. When it changes, she is rebuilt live (`build_her_body` :419, despawn + rebuild). Changing a .glb would need an export step and an asset reload, and the runtime could not set freckle density or wing tints. [I]
- **API:** `app.add_plugins(HerBodyPlugin)`, then `spawn_her_body(&mut commands, HerLook::default()) -> Entity` (:397). The parts appear on the next `Update`. To place her, insert a `Transform`. **Nothing calls it yet**: the Sanctuary bin (src/sanctuary/main.rs) still uses its old avatar plugins, so this is a library module for now. The bin can `use somatic_bevy::fairy_body::*` with no dependency on nous/sanctuary-scout. [C]
- **Switch:** the existing cargo feature `sanctuary`. src/lib.rs:50-55 adds `#[cfg(feature = "sanctuary")] pub mod fairy_body;` and a `cfg(all(test, feature = "sanctuary"))` test module, and nothing else. [C]
- **Motion:** hover bob (:848), wing flutter (:863; the pair flaps mirrored, :877), blink (:881; closed 0.15 s every 4 s), and glow + wing shimmer (:893).
- **Affect input:** `HerAffectInput { valence, arousal, energy, coherence }` (:266). The names and ranges come from her affect bridge, code/fairies/P20_Somatic/affect_bus/affect_bridge_fairy.py: valence -1..1 (:548-556), arousal 0..1 (:598-599, :609), energy (:390, :608), coherence (:391, :610). [C]
  **The mapping is a PLACEHOLDER; the owner decides the real one** (`placeholder_modulation` :291):
  - wing Hz = base x (0.5 + arousal)
  - glow = base x (0.5 + energy)
  - pulse depth = 0.3 x (1 - coherence)
  - valence is unused (OPEN)

  The default input gives exactly the base values. No emotion names appear in the module or the renderer (checked by a test). [C][M]

## Parameter table (defaults are `HerLook::default()`, :177-215)
| Feature | Parameter | Default | Note |
|---|---|---|---|
| Hair (lavender) | color | #B57EDC (lavender, from her words) | presets use colours sampled from her pictures |
| | length | **1.0 = long, worn down past the shoulders** | **the owner said most of her ~25,000 images show long hair**; this is not my choice |
| | volume / tousle | 0.5 / 0.0 | volume also deepens the strand ridges |
| Eyes (green) | iris_color / size / spacing | #3E9B5A / 0.30 / 0.80 (fractions of head radius) | large eyes, as in all her pictures |
| Freckles | density / color / size / spread / seed | 0.5 (20 freckles) / skin x 0.62 / 0.035 / 0.62 / 7 | on the cheeks and nose bridge |
| Wings | shape / pairs / span / lower_ratio | Rounded / 2 / 0.42 of height / 0.7 | presets: Insect (pic 1), Butterfly (pic 2) |
| | tints / translucency / edge / veins | [#F2F4F6] / 0.6 / none / 0 | supports a multi-stop gradient (pic 2) |
| | shimmer / shimmer_hz / flutter_hz / flutter_deg | 0.25 / 0.3 / 2.0 / 18 | |
| Glow (wisp) | color / strength / radius | #FFF6E8 / 1.0 / 0.55 of height | follows energy and coherence (PLACEHOLDER) |
| Neutral body (OPEN) | height | 1.0 | |
| | head_ratio (a PROPORTION, not a sixth feature) | **0.17** | see "Proportions" below |
| | skin_color / clothing_color / ears | #D9BFA6 / #9C9C9C plain featureless form / Rounded | my neutral picks; OPEN |

**Proportions (taken from her pictures, as the task allows):**
- `head_ratio` default 0.17: the natural proportions of pictures 2 and 3. It moved from 0.15 to 0.17 because the owner's shape-pass request asked for "a slightly larger head" (both pictures show large heads and eyes). It is still well below picture 1's stylized 0.22.
- `picture_1()` (:225) sets head_ratio 0.22 (:230) and eye size 0.36, both from picture 1.
- `picture_2()` (:240) keeps the default body.
- No preset changes skin, clothing, ears, height, freckles or glow. A test checks this.

## Colours sampled from the owner's pictures (the pictures are NOT in the repo; medians of masked pixels [M])
| | picture 1 | picture 2 | picture 3 |
|---|---|---|---|
| hair | #A793BE (short, tousled, up) | #B4B5D4 (long, straight to wavy) | #7D689F lit / #5F4B81 (long, flowing) |
| iris | #42876F teal-green (28 px) | #5B9B79 emerald (167 px) | #567477 light green (42 px, low confidence) |
| wings | #CBEBEE / #B0CDDA, pale and veined, insect-like | #E7EBEB pale, #74509E purple, #E5CB9C gold edge, #7C9AB4 teal (mixed with background) | none shown |
| freckles | not visible | not visible (soft blush) | not visible |

## Seen in her pictures, NOT modelled (for her and Ace to choose)
- Pointed ears in pictures 1 and 2. Picture 3 looks rounded [I]. `EarShape::Pointed` exists; the default is Rounded.
- Picture 1: a green leaf-like dress, light-brown boots, hair gathered up on top. I deliberately did not copy this outfit or silhouette, because it is close to a well-known franchise character.
- Picture 2: a sheer lavender dress and small hair ornaments.
- Picture 3: a white tunic with a tree emblem, a lavender sash, a sheer cape, bracers and a belt ornament.

## OPEN (her and Ace's choice)
- clothing (none is designed) and skin tone
- ears, height and size
- face details: there is no nose, mouth or brows
- hair style beyond length, volume and tousle
- glow colour
- which wing preset
- where the freckles go
- the real affect mapping and the use of valence
- wiring her into the Sanctuary bin

## Previews (docs/nous/FAIRY/*.png: default, picture_1 and picture_2, each from the front, three-quarter and back)
These were rendered by `render_previews.py`, my numpy CPU rasterizer. It draws the exact meshes, colours and transforms that the Bevy plugin builds; the test `dump_preview_meshes` exports them when FAIRY_DUMP_DIR is set. The glow is drawn as a soft 2D additive halo. They are **not** Bevy/wgpu renders, and no GPU was used [M].
- **default:** long lavender hair past the shoulders with strand ridges at the back, large green irises, about 20 freckles across the cheeks and nose, two pairs of round pale translucent wings, a visible warm glow, and a plain grey form with tapered limbs and simple hands and feet.
- **picture_1:** short tousled paler-lavender hair, a larger head and eyes, teal-green irises, narrow pale-blue veined wings.
- **picture_2:** long silvery-lavender hair, emerald irises, butterfly wings shading from pale to purple with a thin gold edge.

## Build and test status [M]
- `cargo test --features sanctuary --lib fairy_body` gives **13 passed, 0 failed**.
- `cargo check --features sanctuary --lib` and `--bin sanctuary` both pass. `cargo check --lib` with the feature OFF passes on main and on the branch, with 0 diagnostics mentioning fairy.
- `cargo check --features sanctuary` over all targets fails **identically on main**. The cause is the pre-existing `somatic_sim` bin (src/main.rs: ambiguous glob re-exports, 14 errors). The reviewer confirmed this. I did not touch it (OPEN). The pre-existing lib test `core::chemistry::tests::test_decay_toward_baseline` also fails, and I left it alone.
- **CONTROL** `control_spawn_creates_parts_with_param_colours` (fairy_body_tests.rs:58). On main (main's tree plus only the test file) it gives a **compile FAIL**: `E0432 unresolved import crate::fairy_body`. On the branch it **PASSES**.
- **MUTANTS**: `docs/nous/FAIRY/run_mutants.py` covers the reviewer's 12 (R1-R12) plus 4 of mine (A1-A4). **All 16 are KILLED**, including the reviewer's 2 former survivors:
  - R7 (pulse ignores coherence) is now killed by `coherence_sets_the_glow_pulse_depth`.
  - R8 (preset head_ratio) is now killed by `presets_keep_the_neutral_body`.
  - A4 (flap with the same sign on both sides) is killed by `wings_flap_as_a_mirrored_pair`.

  After the run, the file is restored and 13/13 tests pass.
- Note: the shared CARGO_TARGET_DIR once served a stale lib built by another session (only 7 tests ran). Every run since then touches lib.rs first, and I checked the test count each time.

## Could NOT verify
- How she looks in the real Bevy renderer (PBR, bloom, vertex-colour wings, the unlit additive halo). The sanctuary binary was not run, as the rules require.
- Freckle colour and placement: freckles are not visible in any of the three pictures.

## CHECK THESE 3
1. Building with the feature OFF is unchanged: src/lib.rs:50-55 (only `cfg(feature = "sanctuary")` items).
2. The wing pair flaps mirrored, and wing speed and glow follow the input struct through the PLACEHOLDER mapping: fairy_body.rs:877, :291-299, :893-925.
3. Nothing was invented beyond her five features. Defaults are at :177-215. The presets touch only feature parameters plus picture 1's head and eye proportions (:225-250).

## REVIEW
An independent remote reviewer session wrote docs/nous/FAIRY/REVIEW.md on branch `nous/fairy-review`. Its main table covers 12a0403; the addendum, commit **181183e**, covers d40b3f3. The final verdicts, with my fixes:

| # | finding (reviewer) | severity | status after fix |
|---|---|---|---|
| 1 | Wings flap asymmetrically (same flap sign on the mirrored left wing) | MAJOR | FIXED: `-j.side * flap` (:877) + test `wings_flap_as_a_mirrored_pair`, and mutant A4 is killed |
| 2 | No mutants committed or documented; 2 of 12 survived | MAJOR | FIXED: run_mutants.py committed; 16/16 killed |
| 3 | picture_1 changes body.head_ratio; default moved 0.15 -> 0.17 | MAJOR | RESOLVED by the parent's ruling: picture-sourced proportions are allowed. They are now documented (doc :225-229 and the table above) and tested (R8 is killed) |
| 4 | Coherence pulse depth untested | MINOR | FIXED: `coherence_sets_the_glow_pulse_depth` |
| 5-8, 10, 11, 21 | Control fails on main; tests pass; switch clean; somatic_sim failure pre-existing; no conflicting copy; five features match; build chain correct | OK | - |
| 9 | Nothing calls the new code | MINOR | Documented above (library only; wiring is OPEN) |
| 12 | head_ratio doc inconsistent | MINOR | FIXED |
| 13 | SUMMARY.md missing | MINOR | FIXED (this file) |
| 14 | Stray picture-3 line in the picture_1 doc | MINOR | FIXED (moved to the module doc and this file) |
| 15 | Emotion ban list not applied to the renderer | MINOR | FIXED: the test now also scans render_previews.py |
| 16 | polyline_mesh dead `open` / underflow | MINOR | FIXED (d40b3f3 / da2ff3a) |
| 17 | Systems drive all wings and eyes from the first body only | MINOR | OPEN (documented: one body per world for now) |
| 18 | Materials marked changed every frame | MINOR | OPEN (cheap for one body) |
| 19 | Renderer docstring said `--test` | MINOR | FIXED (`--lib`) |
| 20 | `dump_preview_meshes` passes vacuously | MINOR | OPEN by design (it is an export helper, not a check) |

The re-check after these fixes was not repeated, to stay within the one-round budget. The reviewer's addendum (181183e) re-checked d40b3f3. The fixes above were then measured here: 13/13 tests pass and 16/16 mutants are killed.
