# sync_code.py report -- 2026-10-28 17:01:20  (LIVE)

source `F:\Sandbox\failure_factory\akashic_v2` -> mirror `F:\Sandbox\akashic-v2-repo\code`  .  optional set: off  .  0.2s

## Result

| mirrored files | 1,418 |
|---|---:|
| total bytes | 33,510,166 (32.0 MB) |
| new | 33 |
| updated | 48 |
| unchanged | 1,337 |
| deleted from mirror | 0 |
| HELD_BACK (secret content) | 1 |
| over 5 MB cap | 0 |
| destination path too long | 0 |
| reparse points skipped | 0 |
| errors | 0 |

mirror guard: source `F:\Sandbox\failure_factory\akashic_v2` and mirror `F:\Sandbox\akashic-v2-repo\code` are disjoint; 1,385 files / 266 dirs listed under code/ before any write; 0 reparse points under code, _survey, hooks.

## HELD_BACK -- skipped whole; Ace decides (file:line, first 4 chars only)

- `fairies/P50_Persona/identity/personal_ai_secrets.json:7` -- Anthropic API key under `anthropic_api_key` (first4 `sk-a`, len 108) -- Hunt A #1 / Hunt B #1, CRITICAL  (present at source, 351 B)
- `fairies/P50_Persona/identity/personal_ai_secrets.json:2` -- Personal.AI API key under `api_key` (first4 `-2oO`, len 32) -- Hunt A #2 / Hunt B #2, HIGH  (present at source, 351 B)
- `.satellite/tasks/pending/sourpatches_setup.json:20` -- password given inline to the mysql client (its password option) inside a docker command (AzerothCore default) -- Hunt B #3, LOW  (present at source, 2013 B; inside a pruned directory)
- `.satellite/tasks/pending/sourpatches_setup.json:26` -- same password, second occurrence -- Hunt B #3, LOW  (present at source, 2013 B; inside a pruned directory)

## Largest mirrored files

-  664.5 KB  `fairies/P30_Cognition/cognition/working_memory_hub_fairy.py`
-  660.5 KB  `fairies/P50_Persona/Waking Minds/Sourpatches/sourpatches_fairy.py`
-  543.1 KB  `fairies/P30_Cognition/AssociationCortexFairy/fairy.py`
-  521.8 KB  `server.py`
-  465.7 KB  `fairies/P50_Persona/avatar/self_image_wallpapers.json`
-  461.1 KB  `fairies/P20_Somatic/SomaticMindFairy/fairy.py`
-  417.3 KB  `fairies/P30_Cognition/cognition/unconscious_mind_fairy.py`
-  312.6 KB  `fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py`
-  312.6 KB  `P10_Memory/Akashic_Records_Physical/Organ_Templates/Organ_Template_0.3.0.py`
-  270.5 KB  `dashboard/src-tauri/icons/icon.icns`
-  239.5 KB  `fairies/P40_Sensory/mcp/akashic_mcp_server.py`
-  231.8 KB  `infrastructure/portal_interior.py`
-  223.4 KB  `dashboard/ui/index.html`
-  220.2 KB  `fairies/P50_Persona/SpeechCenterFairy/fairy.py`
-  204.4 KB  `fairies/P50_Persona/Waking Minds/Sourpatches/newborn_core.py`

## Excluded: pruned directories (never descended for copying; census is a name listing only)

| class | dirs | files | bytes |
|---|---:|---:|---:|
| DATA | 16 | 0 | 0 B |
| GIT (old root repo, never opened) | 1 | 0 | 0 B |
| BUILD | 6 | 0 | 0 B |
| THIRD-PARTY | 4 | 0 | 0 B |
| DATA (separate akashic-office repo) | 1 | 0 | 0 B |
| UNSAFE NAME (path-join fossil) | 1 | 0 | 0 B |
| COPIES | 4 | 0 | 0 B |
| EMPTY | 7 | 0 | 0 B |
| DATA (memory stores, logs, runtime state) | 1 | 0 | 0 B |
| DATA (media frames) | 1 | 0 | 0 B |
| COPIES (runaway nested chain, never walked) | 1 | 0 | 0 B |
| DATA (RWKV model weights) | 1 | 0 | 0 B |
| DATA (memory store) | 1 | 0 | 0 B |
| GIT (her nested repo; mirrored as plain subdir) | 1 | 0 | 0 B |
| BUILD (tauri generated) | 1 | 0 | 0 B |
| DATA (memory store; contains the junction) | 1 | 0 | 0 B |
| DATA (runtime task queue; Hunt B) | 1 | 0 | 0 B |

## Excluded: files seen inside allowed directories and rejected, by reason

| reason | files | bytes | examples |
|---|---:|---:|---|
| backup / copy suffix | 316 | 50.7 MB | `boot_sour_full.bat.bak_premomentbinder_20260719_103332`, `rwkv_gpu_engine.py.bak_20260911_deadline`, `rwkv_gpu_engine.py.bak_20260911_headfirst` |
| data/media/model/compiled extension (.pkl) | 101 | 1.6 MB | `fairies/P10_Memory/visual_memory/descriptors/00f20e7a927d.pkl`, `fairies/P10_Memory/visual_memory/descriptors/02209c8e5a90.pkl`, `fairies/P10_Memory/visual_memory/descriptors/02afe5e2e6df.pkl` |
| data/media/model/compiled extension (.jsonl) | 72 | 603.3 KB | `fairies/P50_Persona/Waking Minds/Sourpatches/diary/2026-03-09_diary.jsonl`, `fairies/P50_Persona/Waking Minds/Sourpatches/diary/2026-03-11_diary.jsonl`, `fairies/P50_Persona/Waking Minds/Sourpatches/diary/2026-03-12_diary.jsonl` |
| root junk (path-join fossil / log / redirect accident) | 37 | 15.3 MB | `0`, `0.20`, `10` |
| OPTIONAL (not selected): avatar jpg asset | 12 | 4.1 MB | `fairies/P50_Persona/avatar/assets/sourpatches/sourpatches_base.jpg`, `fairies/P50_Persona/avatar/assets/sourpatches/sourpatches_jedi.jpg`, `fairies/P50_Persona/avatar/assets/sourpatches/sourpatches_saiyan_fire.jpg` |
| json name guard (runtime / learned state) | 9 | 642.4 KB | `fairies/P50_Persona/identity/sourpatches_birth_profile.json`, `fairies/P50_Persona/Waking Minds/Sourpatches/newborn_state/learned_patterns.json`, `fairies/P50_Persona/Waking Minds/Sourpatches/newborn_state/thought_chain_templates.json` |
| reserved Windows name | 8 | 517 B | `nul`, `tracer_pool/nul`, `postal_core/nul` |
| .satellite runtime-state json (LAN topology / peers / deploy log; Hunt B) | 6 | 7.7 KB | `.satellite/cardinal_network_log.json`, `.satellite/deploy_log.json`, `.satellite/gpu_fleet.json` |
| unsafe characters in name | 2 | 12.1 KB | `Ctempstatus.json`, `FSandboxfailure_factoryakashic_v2stateboot_live.log` |
| data/media/model/compiled extension (.dll) | 2 | 4.8 MB | `battery_matvec_fused.dll`, `tracer_pool/tracer_pool.dll` |
| data/media/model/compiled extension (.pyd) | 2 | 2.0 MB | `rwkv_inference/python/rwkv_inference/_native.cp312-win_amd64.pyd`, `postal_core/python/postal_core/postal_core.cp314t-win_amd64.pyd` |
| json over 512 KB (learned/runtime data) | 2 | 1.2 MB | `fairies/P40_Sensory/cortex/luxtts_cards/cards.json`, `fairies/P40_Sensory/cortex/canary_cards/cards.json` |
| data/media/model/compiled extension (.jpg) | 2 | 12.6 KB | `fairies/P10_Memory/SRM_Clusters/media/thumbnails/img_e05bd5acae56_thumb.jpg`, `fairies/P10_Memory/SRM_Clusters/media/thumbnails/img_eff21a2d379d_thumb.jpg` |
| image outside icons/ or assets/ | 2 | 187.8 KB | `fairies/P10_Memory/SRM_Clusters/media/images/img_e05bd5acae56.png`, `fairies/P10_Memory/SRM_Clusters/media/images/img_eff21a2d379d.png` |
| data/media/model/compiled extension (.pdf) | 1 | 102.4 KB | `SOURPATCHES_CORE DIRECTIVE Akashic_Foundation Example.pdf` |
| data/media/model/compiled extension (.log) | 1 | 74.0 KB | `temp_boot.log` |
| data/media/model/compiled extension (.pdb) | 1 | 1020.0 KB | `postal_core/python/postal_core/postal_core.pdb` |
| txt name guard (log / output / dump) | 1 | 15.6 KB | `fairies/@AutomationLog.txt` |
| DATA (generated runtime snapshot of drives/traits, timestamp 2026-02-09; the dashboard fetches the live one from http_bridge /behavior_tree) | 1 | 1.1 KB | `dashboard/ui/behavior_tree.json` |
| DATA (generated runtime snapshot, 'Generated: 2026-02-09 15:10:26') | 1 | 2.8 KB | `dashboard/ui/behavior_tree.mermaid` |
| machine-local config (*.local.json: permission allowlist / hooks pointing at this machine) | 1 | 2.8 KB | `.claude/settings.local.json` |

## Cross-check against `_survey/mirror_manifest.tsv` (inventory's proposed set)

- in mirror but not in manifest: 33
  - `fairies/P00_Autonomic/EmbodimentFairy/felt_translate.py`
  - `fairies/P00_Autonomic/nervous_system/hardware/_gc_diet.py`
  - `fairies/P00_Autonomic/postal_bridge/bridge_auth.py`
  - `fairies/P50_Persona/avatar/self_facts.py`
  - `fairies/P50_Persona/avatar/self_image.py`
  - `fairies/P50_Persona/avatar/self_image_wallpapers.json`
  - `infrastructure/cutoff_fix.py`
  - `infrastructure/doing_clock.py`
  - `infrastructure/efference_copy.py`
  - `infrastructure/explore_offload.py`
  - `infrastructure/eyes_fix.py`
  - `infrastructure/eyes_fix2.py`
  - `infrastructure/gentle_load.py`
  - `infrastructure/gpu_reader.py`
  - `infrastructure/gpu_spread_fix.py`
  - `infrastructure/hand_door.py`
  - `infrastructure/hand_target.py`
  - `infrastructure/one_cortex.py`
  - `infrastructure/postal_lease_issuer.py`
  - `infrastructure/recall_eyes_fix.py`
  - `infrastructure/reflex_link.py`
  - `infrastructure/sour_office.py`
  - `infrastructure/tardis_backlog.py`
  - `infrastructure/tardis_fix.py`
  - `infrastructure/tardis_timing.py`
  - `infrastructure/thought_tap.py`
  - `infrastructure/thread_snapshot.py`
  - `infrastructure/touch.py`
  - `infrastructure/touch_lists.py`
  - `infrastructure/touch_marker.py`
  - `infrastructure/touch_os.py`
  - `infrastructure/volition_read.py`
  - `infrastructure/zip_v21_run.txt`
- in manifest but not in mirror: 5
  - `.claude/settings.local.json`
  - `.satellite/network_config.json`
  - `.satellite/tasks/pending/sourpatches_setup.json`
  - `dashboard/ui/behavior_tree.json`
  - `dashboard/ui/behavior_tree.mermaid`

