# TASK SANCTUARY: summary

Branch: nous/sanctuary-scout. Full detail, with file:line for every row, is in GAP_MAP.md. Tags: [C] read in code, [M] measured here, [I] inference.

## T1-T6

| T | Status | Effort | Smallest first step |
|---|---|---|---|
| T1 room to walk in | main MISSING (island plus a solid box cabin, world.rs:166-218). Branch: PARTIAL (room.rs `spawn_room`) | S (done) / M | Colliders and a doorway |
| T2 her body and first-person eyes | main MISSING (camera.rs:59-66 is a free observer camera). Branch: PARTIAL (room.rs:251-287, gaze at 326-337) | M | Use `spawn_her_body` at the room.rs:251 seam. Raycast the gaze |
| T3 second body (Nous) and talk | PARTIAL (avatar.rs:125-133 wisp, chat panel, chat messages) | M | Nous body in the room, plus speech bubbles (chat_panel.rs:436, never called) |
| T4 terminal and webcam monitors | main MISSING. Branch: PARTIAL (`FrameSource` trait room.rs:100, synthetic feed) | M / L | MJPEG `FrameSource`; egui-to-texture terminal |
| T5 her system drives the body and gets her eyes | MISSING. Inbound file only; spawn/mood are TODO (postal_bridge.rs:250-258); likely path mismatch [I] | L | move/gaze messages, render-to-texture eyes, an outbox file |
| T6 light follows her circadian clock | PARTIAL. Sky follows `time_of_day` (world.rs:333), but that is a synthetic 10-minute day (mood.rs:80-87) | S | Subscribe to `circadian.state` `virtual_hour` (circadian_pacemaker_fairy.py:659) and call `send_mood` (sanctuary_bridge.py:206). Implement the Mood arm |

## Findings

- The postal bridge uses no postal topics. It is a file, `state/sanctuary_inbox.json`, read relative to the working directory, and nothing goes out [C postal_bridge.rs:56].
- The only launcher is the dashboard's `open_sanctuary`, which runs with working directory `<root>\somatic_bevy` (code/dashboard/src-tauri/src/lib.rs:1077-1090). Python writes `<root>\state\...` (sanctuary_wiring.py:31-34). The two paths probably differ, so the inbox is probably a dead letter [I].
- Chemistry only reaches glTF avatars [C gltf_avatar.rs:450-456], and no .glb exists. All 3 model paths are missing, 2 of them game-ripped [M].
- Build: `cargo check --features sanctuary --bin sanctuary` gives 0 errors and 73 warnings on Bevy 0.15.3 [M]. Pre-existing breakage, in files untouched here [M]:
  - the default-feature `somatic_sim` bin does not compile (14 errors);
  - core/chemistry.rs:227 and gltf_avatar.rs:688 tests fail.
- Upgrading to current Bevy is about M (get_single x9, `EventWriter` x18, `.send(` x19, `Parent` x3, egui x35) [M counts, I effort].
- Runtime needs [I]: a GPU with Vulkan 1.1, DX12 or Metal (integrated is fine at 720p), 0.5-1 GB VRAM, 2+ cores, about 1 GB RAM. It needed libasound2-dev and libudev-dev to build.

## The slice

New file room.rs plus 10 lines in main.rs. The switch is env `SANCTUARY_ROOM`, OFF when unset (room.rs:29-36), and the code compiles only with the `sanctuary` feature. When ON, the scene has:

- floor, 4 walls, a window, a desk and a light;
- a glowing wisp body;
- a Camera3d "Her Eyes" as a child of the body, with a gaze focus point;
- one wall monitor fed through the `FrameSource` trait by a moving colour-bar `TestPattern`;
- the island camera switched off.

Original primitives only, no third-party assets.

## Tests [M]

Run with `cargo test --features sanctuary --bin sanctuary room::`, headless (MinimalPlugins and AssetPlugin).

| Run | Result |
|---|---|
| Branch | 5/5 pass |
| CONTROL A: main's main.rs | The room tests do not exist (0 run). |
| CONTROL B: plugin with no systems, as on main | 4/5 FAIL |

Mutants. All 6 are caught.

| Mutant | Result |
|---|---|
| M1 frame never advances | 1 FAIL |
| M2 eyes not parented to the body | 2 FAIL |
| M3 switch default ON | 1 FAIL |
| M4 gaze on the wrong axis | 1 FAIL |
| M5 island camera left on | 1 FAIL |
| M6 no frame length guard | 1 FAIL (panics) |

Off-switch path [M]: the diff touches only src/sanctuary/ (bin-only; Cargo.toml:52-55). `cargo check --lib` and `--features python --lib` pass. The `cargo test --lib` result and the pre-existing failures are the same as on main; the reviewer confirmed this.

## Could NOT verify

- Rendering: no window and no GPU here; nothing was drawn.
- Whether her live tree bridges the two inbox paths.
- Real webcam input.
- Actual frame time, VRAM or RAM.

## CHECK THESE 3

1. Inbox path mismatch: code/dashboard/src-tauri/src/lib.rs:1077 + 1090 vs code/fairies/P40_Sensory/mcp/sanctuary_wiring.py:31-34 vs postal_bridge.rs:56.
2. The switch is OFF when unset, and the app with it OFF is identical: room.rs:29-36 and main.rs:116-119.
3. The monitor texture really changes per frame through the trait: room.rs:100-154 (TestPattern, `wrapping_add` at 152) and `update_monitor`.

## REVIEW

The reviewer was a fresh remote session that only saw the diff and the task. Its full table is on branch nous/sanctuary-review in docs/nous/SANCTUARY/REVIEW.md. Verdict: **PASS, with MINOR notes, no blockers**. It ran 1 round plus 1 re-check, the re-check at 645f5bf.

| # | Finding | Status |
|---|---|---|
| 1-3 | Tests pass, headless build OK, control absent on main | OK |
| 4 | Pre-existing failures are identical on main (gltf_avatar.rs:688, chemistry.rs:227) | OK |
| 5-7 | Switch is OFF for unset, "", "0" and "true"; RoomPlugin is added only at main.rs:117-118; the OFF app is the same | OK |
| 8 | Two active cameras when ON | FIXED in 645f5bf (`hand_view_to_her_eyes`, test plus mutant M5); confirmed by the re-check |
| 9 | WASD also moves the island camera (now inactive) when ON | OPEN: harmless, ON-only. The fix would need to gate camera.rs, which was left untouched |
| 10 | Monitor writes frames without a length check | FIXED after the re-check (room.rs:359-362, `warn_once` + skip; test plus mutant M6). Not re-reviewed |
| 11 | Switch test covered only "unset" | FIXED after the re-check (`switch_on` covers unset, "", "0", "true" and "1"). Not re-reviewed |
| M1-M4 | Reviewer's own mutants (same frame, 3 walls, eyes unparented, default ON) | All CAUGHT |
