# akashic-v2 code mirror -- INVENTORY (survey, 2026-09-26)

Source tree: `F:/Sandbox/failure_factory/akashic_v2/` (READ-ONLY; nothing in it was modified,
its `.git` was not opened by git, no remote added, nothing pushed; she is OFFLINE).
Mirror target: `F:/Sandbox/akashic-v2-repo/` (fresh history; nothing copied yet -- this is the plan).
Method: one long-path-safe `os.scandir` walk (never follows reparse points, never descends the
root `.git`), stat only; then a pure-path/size classifier; then a bounded read-only text scan of
the proposed mirror set for secret patterns (masked output, first 4 chars only).
Python: `python -B` with `PYTHONDONTWRITEBYTECODE=1`, UTF-8 stdout (the cp1252 console broke
the first name-safety run -- the diagnostic must never be the failure).

## 1. Headline numbers

| measure | value |
|---|---|
| files walked | 178,736 (+ 6,011 files inside the old root `.git`, not walked) = ~184.7k -> matches the "~184k" du figure |
| directories | 12,167 (1,639 of them are the empty runaway chain under `fairies/sandbox/`) |
| bytes | 100,987,706,317 = 94.05 GiB (+ 41 MB root `.git`); du's "~92 GB" is consistent (allocation vs apparent size) |
| reparse points (junction/symlink) | 1 |
| walk errors | 0 |
| max directory depth | 1,641 (runaway chain); max FILE depth 14 |
| longest path | 29,527 chars (runaway chain, directories only); longest real file relpath 208 chars (in Claude_Office, excluded) |
| CODE files over 5 MB | **0** (largest CODE file is 0.6 MB) |
| proposed mirror | **1,390 files, 29.9 MB** (+44 optional files, 4.2 MB) |

## 2. Class totals (whole tree)

| class | files | bytes | share of bytes | share of files |
|---|---:|---:|---:|---:|
| CODE (her own source) | 1,402 | 0.03 GiB (34 MB) | 0.0% | 0.8% |
| DATA (stores, logs, media, models, state, diaries, notes) | 111,785 | 54.88 GiB | 58.3% | 62.5% |
| THIRD-PARTY (.venv, research_repos clones) | 30,160 | 5.05 GiB | 5.4% | 16.9% |
| BUILD OUTPUT (target/, dist/, __pycache__, compiled artifacts) | 32,330 | 22.27 GiB | 23.7% | 18.1% |
| COPIES (sandbox copies, backups/, *.bak_* files, _DEPRECATED) | 3,059 | 11.81 GiB | 12.6% | 1.7% |
| **total** | **178,736** | **94.05 GiB** | | |

Where the bytes actually are (top 12 leaves):
`.gguf` 13.95 GB (21 files) . `.portal` 12.75 GB (3) . `.rlib` 9.68 GB (2,475) . `.wav` 9.60 GB (1,802) .
`.manifold` 6.45 GB (39) . `.rmeta` 4.44 GB . `.pdb` 4.35 GB . `.dll` 4.28 GB . `.log` 3.65 GB (135) .
`.embeddings` 2.93 GB (2) . `.pth` 2.93 GB (13) . `.lib` 2.67 GB . `.bak_precore_0624` 2.59 GB (4).
The 103,725 `.json` files (1.05 GB) are almost all SRM_Intake / state / dream_states records.

## 3. Every top-level entry, classified

(dominant class; size and file count; per-class split. Empty dirs listed at the end.)

| entry | class | size | files | split |
|---|---|---:|---:|---|
| fairies | DATA (code inside) | 30.97 GB | 10,240 | DATA 30,920 MB/9,175 (models 28.9 GB, boot_logs 1.33 GB) . CODE 23.6 MB/787 . COPIES 25.5 MB/278 |
| state | DATA | 22.59 GB | 12,735 | DATA 14,147 MB/12,568 . COPIES 8,440 MB/166 (_probe_copy, _restore_probe, *.bak_*) |
| somatic_bevy | BUILD (Rust) | 10.58 GB | 11,703 | BUILD 10,583 MB/11,673 (target/) . CODE 0.3 MB/30 |
| tools | DATA (code inside) | 9.92 GB | 3,731 | DATA 9,909 MB/3,688 (tools/extracted media frames + wav) . CODE 0.5 MB/42 |
| dashboard | BUILD (nested git) | 9.32 GB | 14,217 | BUILD 9,320 MB/14,125 (src-tauri/target, gen/schemas) . CODE 1.0 MB/35 . DATA/.git 0.4 MB/57 . COPIES 2 |
| .venv | THIRD-PARTY | 4.86 GB | 20,807 | all third-party |
| backups | COPIES | 2.48 GB | 11 | pre_xp_reset_20260602 cortex.manifold(.csr/.embeddings/.keys) + json |
| postal_core | BUILD (Rust) | 2.18 GB | 4,507 | BUILD 2,176 MB/4,444 (target/) . CODE 0.7 MB/39 . COPIES 4.3 MB/23 |
| P10_Memory | COPIES/DATA | 1.68 GB | 162 | Akashic_triple_helix_memory_storage 1,679 MB/149 (stores + .bak) . CODE 0.6 MB/11 (Organ_Templates) |
| rwkv_inference | BUILD (Rust) | 0.72 GB | 2,096 | BUILD 720 MB/2,079 (target/, dist/) . CODE 0.2 MB/17 |
| research_repos | THIRD-PARTY | 0.47 GB | 9,584 | llama.cpp, ollama, RWKV-LM, claude-code-*, openai-agents-python, mamba, grok-1 (8 nested .git) |
| sandbox | COPIES | 188 MB | 2,429 | 30+ sandbox copies (cortex_slim 75 MB, cortex_coherence_shape 48 MB, modality_gate_visual 36 MB/2,016 files) |
| SRM_Intake | DATA | 108 MB | 81,866 | per-day json records (the file-count hog: 46% of all files) |
| diaries | DATA | 78 MB | 97 | |
| P30_Cognition | CODE + data | 60 MB | 26 | CODE 0.2 MB/18 (cognition/, integration/) . data/ 59 MB (COPIES/DATA) |
| Claude_Office | DATA (excluded -- separate akashic-office repo) | 33 MB | 834 | |
| `<root files>` | mixed | 29 MB | 209 | CODE 1.6 MB/125 . COPIES 11.9 MB/41 (25x server.py.bak_*) . DATA 15.5 MB/42 (boot logs, junk names) . BUILD 1 (battery_matvec_fused.dll) |
| directives | DATA | 25 MB | 128 | generated *.directive (7.6 MB each) |
| tracer_pool | CODE (+dll) | 9.6 MB | 19 | CODE 0.2 MB/16 (Go + Python) . BUILD 9.4 MB/2 (tracer_pool.dll x2) . `nul` |
| infrastructure | CODE | 4.7 MB | 93 | CODE 1.5 MB/54 . COPIES 3.2 MB/39 (*.bak_*) |
| .cognitive | DATA | 1.6 MB | 1,360 | agent_logs |
| dream_states | DATA | 0.9 MB | 1,594 | |
| _old_unconscious_mind_DEPRECATED | COPIES | 0.7 MB | 35 | |
| tests | CODE | 0.7 MB | 40 | |
| docs | CODE | 0.6 MB | 25 | docs/plans/*.md |
| scripts | CODE | 0.5 MB | 36 | |
| fairy_template | CODE | 0.3 MB | 14 | |
| directory | CODE | 0.3 MB | 14 | 12 CODE + 2 COPIES |
| consciousness | CODE | 0.3 MB | 7 | 6 + 1 copy |
| P00_Autonomic | CODE | 0.2 MB | 24 | nervous_system/ |
| memory | CODE | 0.2 MB | 8 | helix/ + tensor fabric |
| .satellite | CODE + state | 0.1 MB | 26 | CODE 18 (py/lua/sh/md/json configs) . DATA 6 (runtime json) . COPIES 2 |
| wow_scripts | CODE | 0.1 MB | 8 | lua |
| hardware | CODE | 0.1 MB | 7 | 6 + 1 copy |
| akashic_records | DATA | 0.1 MB | 8 | |
| waking_minds | CODE | 0.1 MB | 2 | nous_fairy.py |
| core | CODE | 0.1 MB | 7 | |
| spellchain | CODE | 0.1 MB | 7 | |
| .pytest_cache | BUILD | 0.1 MB | 5 | |
| gui, integration, utils | CODE | tiny | 2 each | |
| foundations, P20_Somatic, P60_Executive, .claude | CODE | tiny | 1-3 each | |
| .git | (old root repo, 112 Feb commits, NOT reused) | 41 MB | 6,011 | HEAD -> master, no remote configured |
| empty top-level dirs (git cannot track): `config`, `functions`, `nous_workshop`, `postal`, `scrape_checkpoints`, `session_forensics`, `unconscious_mind`, `NVIDIA Corporation`, `C<U+F03A>temp` | -- | 0 | 0 | |

### Large subfolders (>= 20 MB or >= 500 files), depth 2

| subfolder | size | files | class |
|---|---:|---:|---|
| fairies/P30_Cognition | 29,583 MB | 334 | DATA 29,565 MB/10 (AkashicInferenceFairy/models: 8 RWKV weights .gguf/.portal/.pth) . CODE 6.0 MB/166 . COPIES 12.4 MB/158 |
| state/akashic | 14,149 MB | 61 | DATA 7,970 MB/37 (cortex.manifold + sidecars) . COPIES 6,179 MB/24 (.bak_precore, .bak_prechain, .run1, .over_pruned ...) |
| somatic_bevy/target | 10,583 MB | 11,673 | BUILD |
| tools/extracted | 9,922 MB | 3,689 | DATA: plex_media 9,276 MB/265, austin_powers 484 MB/2,496 frames, american_dad 119 MB/915, sourpatches_art 43 MB/12 |
| dashboard/src-tauri | 9,320 MB | 14,150 | BUILD 9,319.5 MB/14,125 . CODE 0.4 MB/23 |
| .venv/Lib | 4,858 MB | 20,771 | THIRD-PARTY |
| backups/pre_xp_reset_20260602_174328 | 2,477 MB | 11 | COPIES |
| postal_core/target | 2,174 MB | 4,442 | BUILD |
| P10_Memory/Akashic_triple_helix_memory_storage | 1,679 MB | 149 | COPIES 884 MB/10 . DATA 795 MB/139 (contains the junction, see 6) |
| state/logs | 1,566 MB | 5 | DATA |
| fairies/boot_logs | 1,328 MB | 7,468 | DATA |
| state/_restore_probe | 1,123 MB | 3 | COPIES |
| state/_probe_copy | 1,012 MB | 62 | COPIES |
| rwkv_inference/target | 719 MB | 2,077 | BUILD |
| state/dream_seeds | 309 MB | 3,589 | DATA |
| research_repos/llama.cpp . ollama . RWKV-LM . claude-code-nirholas . claude-code-source . openai-agents-python | 175 . 130 . 57 . 47 . 41 . 10 MB | 2,505 . 1,743 . 207 . 2,199 . 1,933 . 824 | THIRD-PARTY |
| sandbox/cortex_slim . cortex_coherence_shape . modality_gate_visual | 75 . 48 . 36 MB | 15 . 5 . 2,016 | COPIES |
| state/autopilot 72 MB . diaries/Fairies 68 MB . state/consciousness 61 MB . P30_Cognition/data 59 MB . state/telemetry 46 MB . state/rwkv_state 33 MB . Claude_Office/from_ace 23 MB . state/cognition_guild 23 MB | | | DATA/COPIES |
| state/sessions 2,927 files . state/weave_inbox_nous_held 5,382 files . .cognitive/agent_logs 1,349 . fairies/SRM_Intake 1,340 . SRM_Intake/<75 day dirs> 500-1,900 files each | small | | DATA |

## 4. CODE class in detail

### Extensions in CODE (count, size)

| ext | n | size | | ext | n | size |
|---|---:|---:|---|---|---:|---:|
| .py | 1,138 | 26.8 MB | | .cmd | 4 | 0.0 |
| .md | 89 | 1.1 MB | | .lock | 4 | 0.3 MB (Cargo.lock x4) |
| .rs | 45 | 0.4 MB | | .gitignore | 3 | 0.0 |
| .bat | 18 | 0.0 | | .txt | 2 | 0.0 (requirements.txt + 1) |
| .json | 17 | 0.1 MB | | .sql | 2 | 0.1 MB |
| .ps1 | 14 | 0.0 | | .html | 2 | 0.2 MB |
| .png | 14 | 0.2 MB (tauri icons) | | .example .c .vbs .mod .sum .h .js .mermaid .css .icns .ico .sh | 1 each | |
| .lua | 12 | 0.2 MB | | | | |
| .jpg | 12 | 4.1 MB (avatar art -> OPTIONAL) | | | | |
| .toml | 8 | 0.0 | | | | |
| .go | 6 | 0.1 MB | | | | |

`.py` accounting across the whole tree (13,771 total): THIRD-PARTY 10,083 (.venv 9,397, research_repos 686) .
COPIES 2,505 (sandbox 2,305, state 87, fairies 78, _old_..._DEPRECATED 35) . CODE 1,138 . DATA 45
(state 21, Claude_Office 16, tools/extracted 2, sandbox 2, P30_Cognition/data 2, P10_Memory stores 2).

### Largest CODE files (none over 1 MB; none over 5 MB)

| size | file |
|---:|---|
| 0.6 MB | fairies/P30_Cognition/cognition/working_memory_hub_fairy.py |
| 0.6 MB | fairies/P50_Persona/Waking Minds/Sourpatches/sourpatches_fairy.py |
| 0.5 MB | fairies/P30_Cognition/AssociationCortexFairy/fairy.py |
| 0.5 MB | server.py |
| 0.4 MB | fairies/P20_Somatic/SomaticMindFairy/fairy.py |
| 0.4 MB | fairies/P30_Cognition/cognition/unconscious_mind_fairy.py |
| 0.3 MB | fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py |
| 0.3 MB | P10_Memory/Akashic_Records_Physical/Organ_Templates/Organ_Template_0.3.0.py |
| 0.3 MB | dashboard/src-tauri/icons/icon.icns |
| 0.2 MB | fairies/P40_Sensory/mcp/akashic_mcp_server.py . infrastructure/portal_interior.py . dashboard/ui/index.html . fairies/P50_Persona/SpeechCenterFairy/fairy.py . fairies/P40_Sensory/web/akashic_foundation.py . fairies/P50_Persona/Waking Minds/Sourpatches/newborn_core.py . fairies/P00_Autonomic/AutopilotFairy/fairy.py . infrastructure/manifold_memory.py . fairies/P30_Cognition/goal_scheduler/goal_scheduler_fairy.py . fairies/P30_Cognition/integration/cortex_reasoner.py |
| (jpg) 0.2-0.5 MB | 12 avatar images under fairies/P50_Persona/avatar/assets/ -- OPTIONAL |

The Organ Template is present in two places and both are CODE/INCLUDE:
`fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py` and
`P10_Memory/Akashic_Records_Physical/Organ_Templates/{Organ_Template_0.1.0.py, Organ_Template_0_1_2.py, Organ_Template_0.3.0.py, fairy_status_sheet.py, akashic_codex.json (76 KB)}`.

### Where her CODE lives (mirror INCLUDE set by directory)

fairies/P30_Cognition 166 . fairies/P40_Sensory 160 . fairies/P00_Autonomic 158 . fairies/P10_Memory 117 .
fairies/P20_Somatic 96 . fairies/P50_Persona 60 (+12 optional jpg) . fairies/P60_Executive 16 . fairies/embodiment_wiring 1 .
`<root>` 125 . infrastructure 54 . tools 42 . tests 40 . postal_core 39 . scripts 36 . dashboard 35 . somatic_bevy 30 .
docs 25 . P00_Autonomic 24 . P30_Cognition 18 . .satellite 18 . rwkv_inference 17 . tracer_pool 16 . fairy_template 14 .
directory 12 . P10_Memory 11 . wow_scripts 8 . memory 8 . spellchain 7 . core 7 . hardware 6 . consciousness 6 .
P60_Executive 3 . P20_Somatic 3 . waking_minds 2 . utils 2 . integration 2 . gui 2 . .claude 2 . foundations 1.

### Review items inside CODE-shaped areas (routing decisions the rule made)

| decision | files | note |
|---|---|---|
| `.json` routed to DATA by name/size while sitting in a code dir | 10 | `fairies/P40_Sensory/cortex/canary_cards/cards.json` 0.7 MB, `luxtts_cards/cards.json` 0.5 MB, `voice_profiles/profiles.json`, `fairies/P10_Memory/visual_memory/visual_index.json`, `.../Sourpatches/newborn_state/{thought_chain_templates,learned_patterns}.json`, `fairies/P30_Cognition/cognition/interest_state.json`, `fairies/P50_Persona/identity/sourpatches_birth_profile.json`, `fairies/P10_Memory/SRM_Clusters/media/media_index.json`, `fairies/P40_Sensory/cortex/portal_state/audio_portal_state.json` -- these are her learned/runtime state, not config. Ace may pull any back in. |
| `.json` kept as CODE although > 64 KB | 1 | `P10_Memory/Akashic_Records_Physical/Organ_Templates/akashic_codex.json` (76 KB) -- part of the Organ Template set |
| `.txt` routed to DATA in a code dir | 1 | `fairies/@AutomationLog.txt` |
| `.satellite/*.json` split | 4 CODE / 6 DATA | configs (network_config, directives/*, tasks/*) in; runtime (peer_registry, gpu_fleet, shared_state, deploy_log, cardinal_network_log, deploy_queue/manifest) out. All contain only LAN 192.168.x addresses. |
| her own compiled artifacts outside build dirs (excluded; rebuild from source) | 7 | tracer_pool/tracer_pool.dll + _SAVED.dll (4.7 MB each), rwkv_inference/python/rwkv_inference/_native.cp312-win_amd64.pyd 1.4 MB, postal_core/python/postal_core/postal_core.cp314t-win_amd64.pyd 0.6 MB + .pdb 1.0 MB, battery_matvec_fused.dll 54 KB (source battery_matvec_fused.c IS included) |
| code living inside DATA dirs (OPTIONAL extras) | 32 | 27 `state/*.py|*.ps1` operator scripts + 5 `state/nous_workspace/*.py` (coupling_operator_proto/v2/v3, node_compare, shadow_promoter) -- Nous's prototypes. Not code-in-`.satellite`-deploy_queue (already in). Also `P30_Cognition/data/symbology.py`, `P10_Memory/.../relational_clusters/Sourpatches/{personality_extractor,ask_sour}.py`, `tools/extracted/sourpatches_art/{_feature_extract_worker,_register_ace_voice}.py` -- left out (live inside stores). |
| root-level PDF | 1 | `SOURPATCHES_CORE DIRECTIVE Akashic_Foundation Example.pdf` 105 KB -- authored document, classed DATA by extension; Ace's call whether it is design documentation. |
| root junk names | ~20 | `0`, `0.20`, `10`, `50`, `OOM`, `per-region`, `nul`, `test_output.txt` (0 B), `Ctempstatus.json`, `Sandboxtemp_status.json`, `FSandboxfailure_factoryakashic_v2stateboot_live.log`, `stateboot_*.log`, `stateserver_*.log`, `temp_stat.json`, `test_capture.png` 4 MB -- path-join accidents and log fossils; excluded. |

## 5. Backup / copy census

363 backup-suffixed files, 6,280 MB total (dominated by `state/akashic/cortex.manifold.bak_*`).
Suffix shapes seen: `.bak_<tag><mmdd>` 69 . `.bak_<date>_empty` 14 . `.bak_<tag><date>` 13 . `.bak_<tag>` 9 .
`.bak_<date>` 6 . `.bak_<date>_<word>` ~90 across 40 words . `.deprecated` 5 . `.keys.bak_*` 4 . `.NUKED` 2 . `.disabled` 2 .
`.csr.bak_*` 2 . `.bak` 3 . plus `.run1`, `.over_pruned`, `.pre_merge_<date>`, `.bak_prechaintype`, `.bak_<date>_presnippetclear`
(each 824 MB manifold copies). Root alone has 25 `server.py.bak_*` (~12 MB), 3 `rwkv_gpu_engine.py.bak_*`,
4 `sour_graceful_shutdown.py.bak_*`, 6 `start_HQ_LEAN*.bat.bak_*`, 2 `start_nous.bat.bak_*`.
`infrastructure/` has 39 (13 of `manifold_memory.py`, 6 `portal_gate.py`, 6 `graph_weaver.py`, 5 `gpu_inference_portal.py`).
Copy DIRECTORIES: `sandbox/` (2,429 files), `fairies/sandbox/` (dirs only), `backups/`, `state/_probe_copy/`, `state/_restore_probe/`,
`state/_rust_test/`, `state/_sandbox_council/`, `state/_preserved_*/`, `state/nous_workspace/_shadow_stage/`,
`fairies/P30_Cognition/AkashicInferenceFairy/_old_rwkv_DEPRECATED/`, `_old_unconscious_mind_DEPRECATED/`.

## 6. Git-relevant hazards

### Nested .git directories (10) and .gitmodules (2)
| path | what | mirror action |
|---|---|---|
| `.git` (root) | old repo, 112 Feb commits, 41 MB, 6,011 files, HEAD -> master, **no remote** | never opened; new repo starts fresh |
| `dashboard/.git` | HER nested repo (53 files, 0.1 MB) | drop the `.git`; mirror `dashboard/` as a plain subdirectory (NOT a submodule/gitlink) |
| `research_repos/{RWKV-LM, openai-agents-python, ollama, mamba, llama.cpp, grok-1, claude-code-source, claude-code-nirholas}/.git` | third-party clones | whole `research_repos/` excluded |
| `research_repos/{mamba,llama.cpp}/.gitmodules` | third-party | excluded |

### Symlinks / junctions (1)
`P10_Memory/Akashic_triple_helix_memory_storage/system` -> junction (tag 0xA0000003) to
`F:\Sandbox\failure_factory\ebook_copy\P10_Memory\Akashic_triple_helix_memory_storage\system` -- points OUTSIDE her tree,
sits in a DATA store that is excluded anyway. Never follow it.

### Windows-reserved basenames (12) -- git cannot check these out on Windows
`nul` at: root, `tracer_pool/`, `state/`, `postal_core/`, `fairies/`, `fairies/P10_Memory/`,
`fairies/P50_Persona/Waking Minds/Sourpatches/`, `fairies/P30_Cognition/AkashicInferenceFairy/models/`,
`dashboard/`, `dashboard/src-tauri/`, `P10_Memory/Akashic_triple_helix_memory_storage/`, `research_repos/llama.cpp/`.
All 0-260 bytes (stdout redirect accidents). Excluded by rule.

### Path-join fossils with U+F03A (private-use "colon") -- 3
`C<U+F03A>tempstatus.json`, `F<U+F03A>Sandboxfailure_factoryakashic_v2stateboot_live.log` (files, root) and `C<U+F03A>temp/` (empty dir).
Excluded ("unsafe name").

### Paths too long for git on Windows
* The runaway chain `fairies/sandbox/consciousness_wiring_phase1/sandbox/consciousness_wiring_phase1/...` repeats ~600 times:
  **1,639 directories, 0 files, longest 29,527 chars.** Git never sees it (empty dirs are not tracked) but any copy tool
  that recurses will die with "Filename too long" -- the copy must be manifest-driven or prune `fairies/sandbox/` (`robocopy /XD`).
* Outside the chain: 0 relpaths >= 240 chars; 1 relpath >= 200 (208, a `Claude_Office/from_ace/*.md`, excluded);
  0 mirror paths exceed 259 chars under `F:\Sandbox\akashic-v2-repo\`. `core.longpaths=true` is still recommended as a belt.
* Illegal characters (`<>:"|?*`, control): 0. Trailing space/dot names: 0. Case-only collisions in one directory: 0.
* Non-ASCII paths: 7 (the 3 PUA fossils + 4 `Claude_Office/from_ace/` titles) -- none in the mirror set.
* Empty directories: 670 (excl. chain); git cannot track them; nothing needed.
* Spaces in paths that ARE mirrored: `fairies/P50_Persona/Waking Minds/...` -- fine for git, quote in scripts.

## 7. Secrets / privacy scan (read-only; masked)

Targets: the 1,390 INCLUDE + 44 OPTIONAL files, plus every code-in-data candidate, every `.satellite/` and `.claude/` file,
`.mcp.json`, `.env.example`, `claude_desktop_config_NEW.json`, and every file whose name matches secret/credential/token/
password/.env/.pem/.key (1,507 targets, 1,458 scanned as text, 49 skipped binary/oversize).

| result | detail |
|---|---|
| **live key pattern: 1 hit** | `fairies/P50_Persona/identity/personal_ai_secrets.json:7` -- Anthropic-style key, starts `sk-a`, length 108. File is 351 bytes, classed DATA / SECRET-NAMED and **excluded by the rule**. Recommend Ace rotates it regardless (it is a plaintext file in her tree). |
| other key formats (OpenAI, GitHub, AWS, Slack, Google, HF, JWT, Discord, private-key blocks, URL credentials, `password=` literals) | 0 hits in the mirror set |
| `.env.example` | template only: `ANTHROPIC_API_KEY`/`ELEVENLABS_API_KEY`/`OPENAI_API_KEY` values start `your`; rest are paths/ports/`cuda`/`INFO`. Safe to include. |
| `.mcp.json`, `.claude/mcp.json`, `claude_desktop_config_NEW.json`, `.claude/settings.local.json` | localhost URLs, absolute `F:\Sandbox\...` paths, MCP tool allowlist. No secrets. Include. |
| privacy-grade (fine for a PRIVATE repo, note for any future publication) | `C:\Users\Ace` paths: 47 lines / 30 files (Nous.cmd, boot_312.bat, boot_ram_profiler.py, dashboard lib.rs, .satellite lua ...). LAN IPs 192.168.1.x: 43 lines / 28 files (.satellite/*, P00_Autonomic/nervous_system/resource_pools.py ...). Emails: 26 lines / 5 files (tauri.conf.json, 4 docs/plans/*.md). One `ssh user@host` in .satellite/satellite_daemon.py. |
| secret-NAMED files in the tree (besides the hit) | none real: `TokenBucketFairy*` (a fairy name), `test_timemix_multi_token.py`, `tokenizer.py`, third-party `*api_key*` tests inside sandbox copies of research_repos. |

## 8. PROPOSED RULES for the code-only mirror

Order of evaluation per file: (1) hard denylist -> (2) directory allowlist -> (3) extension allowlist (+ json/txt guards) -> (4) size cap.
A file is copied only if it passes all four. Directories are never copied as units; the manifest is the unit.

### 8a. Hard DENYLIST (anything matching is never copied)

Top-level entries (whole subtree):
```
.git  .venv  research_repos  "NVIDIA Corporation"  Claude_Office  state  diaries  dream_states  SRM_Intake
sandbox  backups  directives  _old_unconscious_mind_DEPRECATED  .cognitive  .pytest_cache  akashic_records
session_forensics  scrape_checkpoints  config  functions  nous_workshop  postal  unconscious_mind  "C<U+F03A>temp"
```
Path prefixes (relative to her root):
```
fairies/sandbox/                fairies/boot_logs/            fairies/state/               fairies/diaries/
fairies/akashic_records/        fairies/.cognitive/           fairies/.satellite/          fairies/SRM_Intake/
fairies/Claude_Office/          "fairies/NVIDIA Corporation/"
fairies/P30_Cognition/AkashicInferenceFairy/models/
fairies/P30_Cognition/AkashicInferenceFairy/_old_rwkv_DEPRECATED/
fairies/P10_Memory/Akashic_triple_helix_memory_storage/
P10_Memory/Akashic_triple_helix_memory_storage/           P30_Cognition/data/
tools/extracted/                memory/.scrape_checkpoints/   dashboard/.git/              dashboard/src-tauri/gen/
state/_probe_copy/  state/_restore_probe/  state/_rust_test/  state/_sandbox_council/  state/_preserved_*/  state/akashic/backups/
state/nous_workspace/_shadow_stage/
```
Directory components anywhere in the path:
```
target  __pycache__  dist  build  node_modules  site-packages  .git  _shadow_stage  .pytest_cache  .mypy_cache  .ruff_cache
```
Basename patterns (regex, case-insensitive):
```
backup suffixes : \.bak(_|\.|\d|$) | \.backup(_|\.|$) | \.orig$ | \.old$ | ~$ | _SAVED\. | \.deprecated$ | \.disabled$ | \.nuked$
                  | \.corrupted\d*$ | \.crash_backup$ | \.stale_ | \.inuse_ | \.nul_\d+$ | _DEPRECATED | _MERGED_for74
                  | \.pre[a-z]+_\d{8} | \.run\d+$ | \.over_pruned$ | \.pre_merge_
secret names    : ^\.env(?!\.example$)(\..*)?$ | secret | credential | api_?key | \.pem$ | \.pfx$ | \.p12$ | ^id_rsa | ^id_ed25519
                  | \.netrc$ | \.npmrc$ | \.pypirc$ | \.git-credentials$ | known_hosts$ | \.kdbx$   (TokenBucketFairy* is allowed: it is a fairy name)
reserved names  : ^(nul|con|prn|aux|com[1-9]|lpt[1-9])(\..*)?$
unsafe chars    : any of  < > : " | ? *  or control chars or U+F03A
root junk       : ^(\d+(\.\d+)?|nul|OOM|per-region|test_output\.txt|boot_test_out5\.txt|boot_test_output\.txt|stateboot_.*|stateserver_.*
                  |FSandbox.*|Ctemp.*|.*status\.json|temp_stat\.json|test_capture\.png|guild_test_err\.log|clean_boot.*|boot_.*\.(log|txt)
                  |boot_test_err.*|SESSION_2026_01_14\.md)$        (root level only)
```
Extensions always denied (data / media / models / compiled):
```
log jsonl pkl pickle pt pth npz npy gguf portal manifold csr keys ring embeddings state index bloat dat db sqlite sqlite3
wav mp3 ogg flac aac m4a mp4 mkv avi webm srt  jpg jpeg jfif gif webp bmp tiff psd (jpg/png allowed ONLY under */icons/ or */assets/)
pdf docx doc xlsx pptx zip 7z tar gz rar tmp dict directive model bpe arrow parquet h5 hdf5 onnx safetensors ckpt cache mat idx pack rev sample nfo
pyc pyo pyd dll so exe lib pdb o obj rlib rmeta d whl egg timestamp ilk exp a bin
```
Size cap: any single file > 5 MB is refused and reported (currently none would trip it; largest is 0.6 MB).

### 8b. Directory ALLOWLIST (subject to 8a and 8c)

```
<root files>        .claude/        .satellite/        P00_Autonomic/     P10_Memory/        P20_Somatic/      P30_Cognition/
P60_Executive/      consciousness/  core/              dashboard/         directory/         docs/             fairies/
fairy_template/     foundations/    gui/               hardware/          infrastructure/    integration/      memory/
postal_core/        rwkv_inference/ scripts/           somatic_bevy/      spellchain/        tests/            tools/
tracer_pool/        utils/          waking_minds/      wow_scripts/
```
OPTIONAL (Ace decides; copied to the same relative paths if chosen):
```
state/*.py  state/*.ps1                      27 misplaced operator scripts (0.2 MB)
state/nous_workspace/*.py  (top level only)   5 Nous prototypes (17 KB)
fairies/P50_Persona/avatar/assets/**/*.jpg   12 avatar images (4.1 MB) -- her art, not code; calibration.json beside them IS included
```

### 8c. Extension ALLOWLIST (within allowed dirs)

```
py pyi pyx rs toml md bat cmd ps1 psm1 psd1 vbs sh lua go mod sum c h cpp hpp cu cuh sql html htm css js mjs ts tsx
yaml yml ini cfg conf lock gitignore gitattributes editorconfig mermaid mmd svg wgsl glsl ron pest proto patch diff
json  -- only if size <= 512 KB AND basename does NOT match
        (status|stat\b|state|report|log|history|cache|snapshot|checkpoint|seed|session|telemetry|registry|profile|stats|metrics
         |memory|record|result|deaths|audit|census|backup|habits|learn|skills|goals|satisfaction|awareness|world|circulation
         |deploy|peer|fleet|shared|scan_results|_bp74|promoter|heartbeat|diagnostic|evolution|graph|index|manifest|outcome
         |timing|weights|embedding|vector|knowledge|tracker|inbox|queue|ledger|cards?\b|dream|reflection|thought|chat
         |conversation|transcript|crash|error)
txt   -- only if size <= 256 KB AND basename does NOT match (log|_err|stderr|stdout|_out\b|output|trace|dump|census|report|@Automation)
png ico icns  -- only under a path containing /icons/ or /assets/ (tauri icons, avatar calibration)
example       -- .env.example only
extensionless -- only: Makefile Dockerfile LICENSE README* CHANGELOG NOTICE AUTHORS CONTRIBUTING Cargo.lock Procfile justfile
```

### 8d. Deviations from HER root `.gitignore` (read, not modified)
Her `.gitignore` ignores `__pycache__/ *.py[cod] *.so .venv/ dist/ build/ target/ Cargo.lock .idea .vscode *.log *.bin .env *.pem *.key credentials.json`
and four `state/*.json`. The rules above agree on everything except **`Cargo.lock`: KEEP it** (4 files, 0.3 MB) --
postal_core, rwkv_inference, somatic_bevy and dashboard/src-tauri are application binaries, and a lock file is what makes
their builds reproducible. `dashboard/src-tauri/.gitignore` ignores `/target/` and `/gen/schemas` -- the rules agree
(`gen/schemas` are tauri-generated, 0.3 MB, excluded).

## 9. Mirror estimate

| set | files | working-tree bytes |
|---|---:|---:|
| INCLUDE | 1,390 | 29.9 MB |
| + OPTIONAL scripts (state/*.py|ps1, nous_workspace) | +32 | +0.2 MB |
| + OPTIONAL avatar jpg | +12 | +4.1 MB |
| max | 1,434 | 34.2 MB |

Git object store for 30-34 MB of mostly-Python text compresses to roughly 8-12 MB; expect the whole `.git` + checkout
to stay **under 50 MB** -- against a 94 GiB source. Per top-level: fairies 775 files / 19.6 MB, root 125 / 1.6 MB,
infrastructure 54 / 1.5 MB, dashboard 35 / 1.0 MB, tests 40 / 0.7 MB, postal_core 39 / 0.7 MB, docs 25 / 0.6 MB,
P10_Memory 11 / 0.6 MB, tools 42 / 0.5 MB, scripts 36 / 0.5 MB, everything else < 0.4 MB each.

What the rules exclude, by reason (file counts): SRM_Intake 81,866 . build components 32,318 . .venv 20,807 .
data prefixes 12,927 . state 12,702 . research_repos 9,352 . sandbox 2,427 . dream_states 1,594 . .cognitive 1,360 .
Claude_Office 834 . COPIES-class files in allowed dirs 308 . nested .git 284 . DATA-class files in allowed dirs 216 .
directives 128 . diaries 97 . _old_unconscious_mind_DEPRECATED 35 . unsafe names 14 . backups 11 . akashic_records 8 .
BUILD-class loose artifacts 6 . .pytest_cache 5 . secret-named 3.

## 10. Judgment calls for Ace (the rule picked one side; both readings are defensible)

1. `fairies/P40_Sensory/cortex/{canary_cards,luxtts_cards}/cards.json` (1.2 MB together) and `voice_profiles/profiles.json` --
   excluded as learned voice data. If they are hand-authored fixtures, add them back.
2. `fairies/P50_Persona/identity/sourpatches_birth_profile.json` (7.9 KB) -- excluded as her identity DATA; `personal_ai_personas.json`
   (12.7 KB, no secrets found) is INCLUDED as config. Swap either way.
3. `fairies/P50_Persona/Waking Minds/Sourpatches/newborn_state/*.json` -- excluded (her learned state).
4. Avatar art (12 jpg, 4.1 MB) -- OPTIONAL. Code references them by path, so the checkout is not runnable without them.
5. The root PDF `SOURPATCHES_CORE DIRECTIVE Akashic_Foundation Example.pdf` -- excluded as a document; include if it is design doc.
6. `docs/plans/*.md` carry an email address on some lines; `.satellite/*.json` and several .py/.lua carry LAN IPs and `C:\Users\Ace` paths.
   Fine for a private repo; strip before any publication.
7. `Cargo.lock` kept against her .gitignore (see 8d).
8. **Rotate the key in `fairies/P50_Persona/identity/personal_ai_secrets.json`** -- not mirrored, but it is plaintext on disk.

## 11. Supporting files

In this directory (`F:/Sandbox/akashic-v2-repo/_survey/`):
`mirror_manifest.tsv` (relpath, size, INCLUDE|OPTIONAL, reason) . `code_files.tsv` (all 1,402 CODE-class files) .
`gitdirs.tsv` . `reparse.tsv` . `walk_summary.json` . `report.txt` (full classifier report) . `name_safety.txt` . `secrets_scan.txt` (masked) .
`checks.txt` (py accounting, backup census, empty dirs, secret-named files).
Large intermediates stayed in the session scratchpad (`.../scratchpad/survey/`): `files.tsv` 12.8 MB, `dirs.tsv` 24.9 MB,
`classified.tsv` 16 MB (every file with class + reason); scripts `walk_tree.py`, `classify.py`, `name_safety.py`, `checks.py`, `secrets_scan.py`.
Decide whether `_survey/` itself belongs in the repo before the first commit (it is safe: no secret values, only masked prefixes).
