# Adversarial review: nous/sanctuary-scout (Her Room, first slice)

Scope: `git diff origin/main...origin/nous/sanctuary-scout -- code/` (`src/sanctuary/room.rs` new, `src/sanctuary/main.rs` edited).
Only cargo check/test ran. No binary, server or launcher was run. One CARGO_TARGET_DIR.

**Verdict: PASS, with MINOR notes.** I found no blockers.

| # | claim / attack | result | evidence | severity |
|---|---|---|---|---|
| 1 | Branch tests pass | 3/3 `room::` tests pass | `cargo test --features sanctuary --bin sanctuary room::` | OK |
| 2 | Builds headless | `cargo check --features sanctuary --bin sanctuary` Finished, 0 errors | command | OK |
| 3 | CONTROL fails on main | main's `main.rs` with `room.rs` absent: the room tests **do not exist** (the full bin run lists only the 3 gltf_avatar tests) | `git show origin/main:.../main.rs`, then `cargo test --features sanctuary --bin sanctuary` | OK |
| 4 | Pre-existing failures not introduced | `gltf_avatar::tests::test_emotion_derivation` panics at gltf_avatar.rs:688 identically on main and on the branch. `core::chemistry::tests::test_decay_toward_baseline` fails in `cargo test --lib`; the lib does not compile any changed file (sanctuary is bin-only, Cargo.toml:57-60), so the outcome is the same by construction. I did not rebuild the somatic_sim default-feature errors; its inputs are untouched by the diff | runs + Cargo.toml | OK |
| 5 | Switch default OFF | `room_enabled()` is true only for exactly `"1"`. Unset becomes "0", so false; `""` false; `"0"` false; `"true"` false | room.rs:27-29 | OK |
| 6 | RoomPlugin added elsewhere? | Only main.rs:117-118, behind the switch | grep `RoomPlugin\|room_enabled\|SANCTUARY_ROOM` | OK |
| 7 | Switch OFF builds the same App | Same builder chain, split into `let mut app` plus `app.run()`; the only addition is one env read. The lib (`--lib`, `--features python --lib`, `test --lib`) is untouched: the diff has no lib files | main.rs:69-121 | OK |
| 8 | Switch ON: two active cameras | `Ace Camera` (camera.rs:61, order 0) stays active and her eyes (order 1) also render to the primary window. Hers draws on top, so Ace's view is gone and its render pass is wasted work. egui may attach to either camera | camera.rs:59-66, room.rs:272-279 | MINOR (ON only) |
| 9 | Switch ON: WASD and mouse bound twice | WASD moves both the Ace camera (camera.rs:90-102) and her body (room.rs move_her_body). Her gaze turns on any mouse motion, and Ace also turns on right-drag | camera.rs:70-140, room.rs move_her_body | MINOR (ON only) |
| 10 | Feed-swap robustness | `TestPattern::next_frame` indexes `out` without a length check. A `MonitorFeed` replaced after Startup with a different `size()` would panic. Nothing does that today; the image is sized from the feed at spawn | room.rs next_frame / update_monitor | MINOR |
| 11 | Switch test is weak | Covers only unset, not `"0"` or `"true"`. `remove_var` mutates the process env while tests run in parallel; harmless today | room.rs tests | MINOR |
| 12 | Window is a pane, not an opening | An emissive translucent cuboid in front of the north wall. Acceptable as a "primitive" | room.rs spawn_room | OK |
| M1 | Mutant: the monitor writes the same frame (drop `frame += 1`) | CAUGHT (`assert_ne!(a, b)`) | mutant run | OK |
| M2 | Mutant: 3 walls (east wall becomes Desk) | CAUGHT (wall count == 4) | mutant run | OK |
| M3 | Mutant: eyes not parented to the body | CAUGHT (2 tests fail) | mutant run | OK |
| M4 | Mutant: switch defaults ON | CAUGHT (`switch_is_off_when_unset`) | mutant run | OK |

Suggested follow-ups (not blocking): when the room is ON, set `is_active = false` on `SanctuaryCamera` and gate `camera_movement` and `camera_look`. Add a length guard in `update_monitor` (skip when `img.data.len() != w*h*4`).
