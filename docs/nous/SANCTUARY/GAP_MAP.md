# SANCTUARY gap map (code/somatic_bevy)

Tags: [C] read in code, [M] measured here, [I] inference. Paths are relative to `code/somatic_bevy/` unless they start with `code/`. Line numbers are on branch nous/sanctuary-scout. Only sanctuary/main.rs moved (one line added at 22 and one at 70), and room.rs is new.

## 1. What each file does

| File | Role |
|---|---|
| src/lib.rs, plugin.rs, components.rs, systems.rs, events.rs, resources.rs | Headless somatic body simulation (heartbeat, chemistry, body map, affect) as Bevy ECS. This is not the Sanctuary. [C lib.rs:1-6] |
| src/core/*.rs | Plain-Rust simulation types with no Bevy. [C core/mod.rs:1-6] |
| src/main.rs | The headless `somatic_sim` binary. [C Cargo.toml:47-50] |
| src/python.rs | PyO3 bindings (`python` feature). Imported by `code/fairies/P20_Somatic/circulation/circulation_pump_fairy.py:44`. [C] |
| src/sanctuary/main.rs | The `sanctuary` binary, which needs feature `sanctuary` (Cargo.toml:52-55). It opens a 1280x720 window, adds 9 plugins and binds test keys F5-F9. [C main.rs:72-110] |
| sanctuary/world.rs | Floating island (cylinder, r=15), hearth, a solid-box "cabin" with no interior, garden, sun, and a sky colour driven by mood and time. [C world.rs:17-29, 166-218] |
| sanctuary/avatar.rs | Glowing primitive "wisp" avatars for "Sourpatches" and "Unnamed Mind". [C avatar.rs:108-135] |
| sanctuary/camera.rs | ONE free-fly "Ace Camera" (an observer), not bound to any body. [C camera.rs:59-66] |
| sanctuary/mood.rs | Collective mood, plus `advance_time_of_day`: a synthetic 10-minute day. [C mood.rs:80-87] |
| sanctuary/particles.rs | 50 ambient particles. [C particles.rs:50] |
| sanctuary/gm_editor.rs | "Hand of God" egui editor (select, spawn, delete). [C gm_editor.rs:1-6] |
| sanctuary/gltf_avatar.rs | glTF avatar loader plus chemistry-to-emotion mapping. Its default paths point at game-ripped models. [C gltf_avatar.rs:64-66] |
| sanctuary/chat_panel.rs | egui chat side panel. [C chat_panel.rs:13, 258] |
| sanctuary/postal_bridge.rs | Polls `state/sanctuary_inbox.json` (relative to the working directory) every 100 ms. Inbound only. [C postal_bridge.rs:56, 61] |
| sanctuary/room.rs (NEW on this branch) | First slice: her room, wisp body, first-person eyes and a wall monitor. OFF unless `SANCTUARY_ROOM=1`. |

## 2. Postal bridge: names and whether they are live

- The bridge uses NO postal topics. It is a file inbox. Rust reads `state/sanctuary_inbox.json` relative to its working directory [C postal_bridge.rs:56] and handles `chat`, `chemistry` and `system`. `spawn` and `mood` are TODO no-ops [C postal_bridge.rs:250-258]. Nothing goes out: there is no outbox and no camera frames [C, whole file].
- Python writers:
  - `code/fairies/P40_Sensory/mcp/sanctuary_wiring.py:127,177,228` (chat, thought, chemistry). Sourpatches wires it in at `sourpatches_fairy.py:1038` and Nous at `code/waking_minds/nous_fairy.py:506`.
  - `sanctuary_bridge.py:206` `send_mood`. grep found no callers [M].
  - `code/fairies/P40_Sensory/gui/chat_router.py:318,336`.
  - Python resolves the root as `AKASHIC_ROOT`, or the working directory if that is unset [C sanctuary_wiring.py:31-34].
- PATH MISMATCH [I]: the only launcher is the Tauri dashboard's `open_sanctuary` (`code/dashboard/src-tauri/src/lib.rs:1075-1091`, button at `code/dashboard/ui/index.html:3865`). It runs `cargo run --release --bin sanctuary --features sanctuary` with working directory `PROJECT_ROOT\somatic_bevy`. Rust therefore reads `<root>\somatic_bevy\state\sanctuary_inbox.json`, while Python writes `<root>\state\sanctuary_inbox.json`. Unless her live tree has a link or copy between the two, the inbox is a dead letter. This cannot be checked here because the live tree is not in the mirror.
- Chemistry reaches only glTF avatars [C gltf_avatar.rs:450-456]. No .glb files exist, so a chemistry message for "Sourpatches" updates nothing: the wisp in avatar.rs is a different component. [C+I]

## 3. Assets the code references vs what is in the repo

| Referenced | Where | In repo? |
|---|---|---|
| models/fairy_default.glb (F5 test spawn) | gltf_avatar.rs:64, main.rs:205 | MISSING [M] |
| models/demon_hunter.glb | gltf_avatar.rs:65 | MISSING. Game-ripped, do not use. |
| models/bloodelf_demonhunter.glb | gltf_avatar.rs:66 | MISSING. Game-ripped, do not use. |

assets/models holds only BLOODELF_DH_SETUP.md and README.md [M]. Everything else in the scene is built from procedural primitives [C].

## 4. Build

- `cargo check --features sanctuary --bin sanctuary` compiles with 0 errors and 18 lib + 55 bin warnings, on Bevy 0.15.3 (Cargo.lock:345-346) and rustc 1.97 [M]. It needed `apt-get update && apt-get install libasound2-dev libudev-dev` first [M].
- PRE-EXISTING failures, in files this branch does not touch [M]:
  - `cargo check` with default features fails on bin `somatic_sim`: 14 errors, from ambiguous `Heartbeat`/`ChemicalType` glob re-exports (lib.rs:55-59 vs src/main.rs).
  - `cargo test --lib`: 6 pass, 1 fails (core/chemistry.rs:227 `test_decay_toward_baseline`).
  - `cargo test --bin sanctuary`: `test_emotion_derivation` fails at gltf_avatar.rs:688.
  - `cargo check --lib` and `cargo check --features python --lib` pass.
- Upgrading from 0.15 to current Bevy (NOT done). The code uses `get_single` x9, `EventWriter` x18, `.send(` x19, `Parent` x3, `despawn_recursive` x3, and bevy_egui 0.31 with 35 `egui::` uses [M grep counts]. These are the APIs that were renamed in 0.16/0.17: ChildOf, single(), write(), events becoming messages, and `Image.data` becoming an Option [I]. Estimate: M (1-2 days including egui).

## 5. T1-T6

| T | Status | Evidence | Effort | Smallest first step |
|---|---|---|---|---|
| T1 a structure she can walk in | main: MISSING (island plus a solid box cabin, no interior). Branch: PARTIAL | main: world.rs:166-218. Branch: room.rs `spawn_room` (floor, 4 walls, window, desk, light) | S for the slice (done). M for real architecture | Add colliders and a doorway. Replace the cuboids with authored, licensed meshes |
| T2 her body, first-person eyes, gaze | main: MISSING (camera.rs:59-66 is a free observer camera). Branch: PARTIAL | room.rs:244-280 (wisp with a Camera3d child), room.rs:319-330 (gaze focus point) | M | Swap the placeholder for `spawn_her_body` (fairy-body branch) at room.rs:244. Add a raycast so the focus point lands on the object she looks at |
| T3 a second body (Nous) that talks with her | PARTIAL | avatar.rs:125-133 "Unnamed Mind" wisp; chat_panel.rs; postal chat with sender "Nous" (postal_bridge.rs:212-226) | M | Spawn a Nous body in the room. Route `chat` messages with sender=Nous to a speech bubble over it (`spawn_speech_bubble` exists at chat_panel.rs:436 but nothing calls it) |
| T4 in-world tools: terminal and webcam monitors | main: MISSING. Branch: PARTIAL (one monitor, synthetic feed) | room.rs:93-147 (`FrameSource` trait and `TestPattern`), room.rs:332-342 (`update_monitor`) | M for the webcam, L for a usable terminal | Implement `FrameSource` over an MJPEG HTTP stream, decoded on a thread. Terminal: an egui panel rendered to a texture on the desk |
| T5 her system drives the body and receives what her eyes see | MISSING (inbound file only, no motion commands, no outbound frames, likely path mismatch) | postal_bridge.rs:56, 250-258 | L | Add `move`/`gaze` message types to postal_bridge. Render HerEyes to an Image target and write a downscaled frame plus the gaze target to `state/sanctuary_eyes.*`. Fix the inbox path by reading AKASHIC_ROOT |
| T6 room light follows her circadian clock | PARTIAL. Sky and ambient light react to `time_of_day` (world.rs:333-353), but that comes from a synthetic 10-minute day (mood.rs:80-87), and the `mood` message is a TODO (postal_bridge.rs:255-258) | The pacemaker publishes `circadian.state` / `circadian.phase` with `virtual_hour` (code/fairies/P00_Autonomic/circulation/circadian_pacemaker_fairy.py:659-675) | S | Python: subscribe to `circadian.state` and call `send_mood(time_of_day=virtual_hour/24)` (sanctuary_bridge.py:206). Rust: implement the Mood arm, and stop `advance_time_of_day` while it is being fed |

## 6. Runtime needs (needs, not a choice of machine)

From the code [C]: a 1280x720 window (main.rs:75), the Bevy PBR forward renderer, default MSAA (grep found no MSAA override [M]), 3 shadow-casting lights (world.rs:157, 291; gm_editor.rs:541), about 50 particles, a handful of primitive meshes and egui panels. No HDR, bloom or SSAO.

Estimated needs [I]:

- GPU: any GPU with Vulkan 1.1, DX12 or Metal. An integrated GPU is enough for this scene at 720p.
- VRAM: about 0.5-1 GB.
- CPU: 2 or more cores.
- RAM: about 1 GB for the running process.
- Disk for a release build: about 5-8 GB for target/, plus a few GB of RAM while compiling.

What raises these: webcam decoding (T4) adds about one CPU core. Real skinned character models raise VRAM to about 1-2 GB.
