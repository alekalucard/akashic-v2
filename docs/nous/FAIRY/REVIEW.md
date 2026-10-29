# REVIEW: FAIRY body (commit 12a0403, `origin/main...origin/nous/fairy-body`)

Independent review, 2026-10-29. I tried to find reasons to reject the change. Tags: [C] = read in the code, [M] = measured by running it.
Nothing in the change was edited. Mutants and the probe were applied to a scratch worktree and then reverted.

**Verdict: the feature switch is clean and the tests are real, but there is one MAJOR motion bug (the wings flap asymmetrically) and two MAJOR scope issues. It is not ready to merge until #1 is fixed.**

| # | finding | severity | file:line | evidence |
|---|---------|----------|-----------|----------|
| 1 | **The wings flap asymmetrically.** `tf.rotation = j.base * Quat::from_rotation_y(-flap)` uses the same sign of `flap` for both sides, but the left wing is mirrored with scale.x = -1. So the right wing swings forward while the left swings back, like a rotor instead of a pair of wings. A probe after 3 frames gave upper-wing tips at z = -0.241 (left) and -0.076 (right), with \|x\| 0.232 vs 0.293. With amplitude 0 (mutant M3) the probe passes, so the rest pose is symmetric and the flap term is the cause. Fix: `Quat::from_rotation_y(-j.side * flap)` (and add a symmetry test). | MAJOR | code/somatic_bevy/src/fairy_body.rs:850 | [C][M] |
| 2 | **No mutants were committed or documented.** The task asks for MUTANTS that fail, but the test file has none, and neither the commit message nor the docs record a mutant run. I ran 12 (table below): 10 are killed and 2 survive (#3, #4). | MAJOR | code/somatic_bevy/src/fairy_body_tests.rs | [C][M] |
| 3 | **A preset changes a body value that is not one of her five features.** `picture_1()` sets `body.head_ratio = 0.22`, while its doc says "Body, skin, clothing and ears stay neutral". `presets_keep_the_neutral_body` does not check `head_ratio`: mutant M8 (head_ratio 0.40) survives. | MAJOR | fairy_body.rs:222,228; fairy_body_tests.rs:177-187 | [C][M] |
| 4 | Glow pulse depth (coherence) is untested: mutant M7 (`0.3*(1-co)` → `0.3`) survives. | MINOR | fairy_body.rs:296 | [M] |
| 5 | Control fails on main as required. Main + only the test file + the `mod fairy_body_tests` line gives `error: couldn't read src/fairy_body.rs` / `E0432 unresolved import crate::fairy_body` (exit 101). | OK | lib.rs:53-55 | [M] |
| 6 | All tests pass on the branch: `cargo test --features sanctuary --lib fairy_body` gives 11 passed, 0 failed. | OK | fairy_body_tests.rs | [M] |
| 7 | The switch is clean. The only non-doc change outside the new files is 2 `#[cfg]`-gated lines in lib.rs; Cargo.toml and Cargo.lock are untouched. `cargo check --lib` (default features) gives the same 18 "ambiguous glob re-exports" warnings on main and branch, and 0 diagnostics mention fairy. | OK | lib.rs:50-55 | [C][M] |
| 8 | Confirmed: `cargo check --features sanctuary` (all targets) fails identically on main and branch. It is the same error set in bin `somatic_sim` (src/main.rs): `ChemicalType` ×4 / `Heartbeat` ambiguous, E0277 ×2, E0308, E0599 ("14 previous errors"). The `sanctuary` bin itself checks OK on the branch. | OK | src/main.rs | [M] |
| 9 | **Nothing calls the new code.** No caller of `HerBodyPlugin` / `spawn_her_body` exists. The `sanctuary` bin (src/sanctuary/main.rs:80-87) still uses `AvatarPlugin` + `GltfAvatarPlugin`, so turning the feature on compiles her body but never shows her. That is acceptable if this is intended as a library only, but it should be stated. | MINOR | src/sanctuary/main.rs:80-87 | [C] |
| 10 | There is no conflicting copy to reuse. `sanctuary/avatar.rs` (a glowing wisp coloured by `Mood`) and `gltf_avatar.rs` (`spawn_demo_fairy`, a `.glb` loader, `derive_emotion`, `chemistry_from_mood`) are bin-private (`mod` in sanctuary/main.rs) and emotion-driven, so the lib could not use them, and they must not be used under the no-emotion rule. There are no shared components or type names. | OK | sanctuary/gltf_avatar.rs:148,545,587 | [C] |
| 11 | Her five features match self_facts.py:38: lavender hair B57EDC, green iris 3E9B5A, freckles (density 0.5), 2 pairs of wings, glow. Hair is long by default (`length: 1.0`). Neutral defaults: skin D9BFA6 "OPEN", grey featureless body 9C9C9C "no clothing designed", rounded ears, height 1.0, plain rounded white wings. All are documented as neutral/OPEN. | OK | fairy_body.rs:172-213 | [C] |
| 12 | Doc inconsistency: `head_ratio` says "stylized large head, as in both pictures" but the default is the "natural" 0.15. | MINOR | fairy_body.rs:135 vs 205-206 | [C] |
| 13 | **`docs/nous/FAIRY/SUMMARY.md` is referenced but missing.** The sampled hex values are said to be "recorded in SUMMARY.md only". The file is not in the commit, so where the preset colours came from cannot be audited. | MINOR | fairy_body.rs:16,218 | [C] |
| 14 | A stray doc line (picture 3 hair #7D689F / iris #567477) is merged into the doc comment of `picture_1()`. | MINOR | fairy_body.rs:217-218 | [C] |
| 15 | No emotion names appear in fairy_body.rs or render_previews.py (grep, 21 stems). The test file contains them only as the ban list in `no_emotion_names_in_the_module`, and that test only scans fairy_body.rs. Mutant M9 (adding "calm") is killed. | OK (MINOR: ban list not applied to tests/renderer) | fairy_body_tests.rs:190-197 | [C][M] |
| 16 | `polyline_mesh`: `let segs = if open { n - 1 } else { n - 1 }` has identical branches, so "closed" never closes and `open` is dead. It also underflows on n = 0 (no current caller does that). | MINOR | fairy_body.rs:806 | [C] |
| 17 | `blink`, `wing_flutter` and `glow_and_shimmer` take the FIRST `HerBody` only, then drive every EyeSocket, WingJoint and GlowHalo in the world. Two bodies would share one phase and one look. This is documented as "one body per world for now". | MINOR | fairy_body.rs:843-844,859,875 | [C] |
| 18 | `glow_and_shimmer` calls `mats.get_mut` on the halo and wing materials every frame, which marks them changed, so they are re-uploaded every frame. Cheap for 1 body. | MINOR | fairy_body.rs:881,891 | [C] |
| 19 | The renderer docstring gives a wrong command: `--test fairy_body` (there is no integration test; the dump is `--lib fairy_body dump_preview_meshes`). | MINOR | docs/nous/FAIRY/render_previews.py:4 | [C] |
| 20 | `dump_preview_meshes` is counted as a passing test but checks nothing (it returns early without FAIRY_DUMP_DIR). | MINOR | fairy_body_tests.rs:202-204 | [C] |
| 21 | The build-then-animate chain is correct: `(build, (bob, flutter, blink, glow)).chain()`. Auto apply_deferred makes the new children visible in the same frame. A rebuild despawns descendants first: mutant M5 is killed. | OK | fairy_body.rs:384-387,422 | [C][M] |

## Mutants (applied one at a time to fairy_body.rs, then reverted)

| mutant | change | killed by |
|---|---|---|
| M1 | wing_hz ignores arousal | wing_speed_follows_arousal |
| M2 | glow ignores energy | glow_follows_the_input_struct |
| M3 | flutter amplitude 0 | wings_actually_flap |
| M4 | iris uses the hair colour | control, changing_the_look_rebuilds |
| M5 | no despawn_descendants on rebuild | changing_the_look_rebuilds |
| M6 | eyes never close | blink_closes_briefly |
| M7 | pulse ignores coherence | **SURVIVES** |
| M8 | picture_1 head_ratio 0.40 | **SURVIVES** |
| M9 | "calm" in a doc comment | no_emotion_names_in_the_module |
| M10 | freckle count ×2 | control |
| M11 | wings opaque | control |
| M12 | `pairs` ignored | changing_the_look_rebuilds |

Commands: `CARGO_TARGET_DIR=/tmp/tgt cargo test --features sanctuary --lib fairy_body` (after `apt-get install libasound2-dev libudev-dev pkg-config`). Only synthetic data was used. No server, fairy, boot or launcher was run.

## Addendum: delta to branch HEAD d40b3f3 (12a0403..d40b3f3: da2ff3a, d40b3f3)

The table above reviews 12a0403. I re-checked the HEAD delta [C] and re-ran the tests on d40b3f3 [M]: the author's 11 tests pass. My wing-symmetry probe still FAILS with the same numbers as on 12a0403 (upper tips z = -0.241 left vs -0.076 right).

| # | status at d40b3f3 |
|---|---|
| 1 wings flap asymmetrically (fairy_body.rs:874 now) | **still open** (MAJOR) [M] |
| 2 no mutants committed | still open (MAJOR) [C] |
| 3 picture_1 sets body.head_ratio (fairy_body.rs:228) | still open (MAJOR) [C]. Also new: the DEFAULT head_ratio moved 0.15 → 0.17 ("larger head"). That is a non-feature body value, so it should be documented as an OPEN/neutral choice. |
| 13 SUMMARY.md missing | still open (MINOR) [C] |
| 16 polyline dead `open` branch / n=0 underflow | **fixed** (`n.saturating_sub(1)`) [C] |
| 19 renderer docstring `--test fairy_body` | still open (MINOR) [C] |
| new | Tapered limbs, hands and feet use the neutral cloth/skin materials and add no new look. The halo strength now also drives base_color alpha, and the test follows it. OK [C] |
