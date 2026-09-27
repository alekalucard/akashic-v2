# SECRET HUNT A -- known token/key formats + credential-named files

Tree: `F:/Sandbox/failure_factory/akashic_v2/` (read-only; her `.git` and the nested `dashboard/.git` were never opened).  
Scanner: `_survey/secret_hunt_a3.py` (patterns also in `_survey/hunt_a_patterns.py`; re-run on a staged tree with `_survey/rescan_a.py <dir>`), whole-buffer regex, 1 junction(s) skipped, run 292.1 s.  
Values are NEVER printed in full: `first4` = first 4 characters, `len` = length of the matched value; context lines have the value replaced by `xxxx..[len]`.

## VERDICT (hand-triaged) -- one real secret file, two live credentials; everything else is placeholder or doc example

### HELD_BACK -- files the Builder must NOT copy (skip whole file)

| # | file:line | kind | first4 | len | included by a code-only mirror? | severity | action |
|---|---|---|---|---|---|---|---|
| 1 | `fairies/P50_Persona/identity/personal_ai_secrets.json:7` | **Anthropic API key** (`sk-ant-...` format, Shannon 5.51) | `sk-a` | 108 | **YES by a naive rule** (.json inside a code dir; my heuristic said INCLUDED). The inventory sibling already routes it to DATA as "SECRET-NAMED (never mirror)" -- keep that rule. | **CRITICAL** | hold back the whole file; **ROTATE the key** (it has sat in plaintext on disk; the pre-Feb `.git` history is unscanned) |
| 2 | `fairies/P50_Persona/identity/personal_ai_secrets.json:2` | **Personal.AI API key** (`"api_key"`, 32 chars, Shannon 4.73, not a hash/uuid) | `-2oO` | 32 | same file as #1 | **CRITICAL** | same file -- held back; **ROTATE** |

That file is 351 bytes and also holds `api_base_url` (26 chars, `http...`), `document_endpoint`, `upload_endpoint`, `health_endpoint` -- URLs, not secrets. It is the ONLY copy in the whole tree (no duplicate under `sandbox/`, `backups/`, `state/`).

Who reads it (so the mirror still works without it): `fairies/P50_Persona/identity/__init__.py:53 load_secrets()` and direct readers in `fairies/P50_Persona/SpeechCenterFairy/fairy.py:2971`, `fairies/P50_Persona/Waking Minds/Sourpatches/sourpatches_fairy.py:11419-11431`, `.../Sourpatches/tool_bridge.py:1313-1321`, `fairies/P50_Persona/memory/personal_ai_bridge.py:886-891`, `.../memory/visual_memory_system.py:578`, `.../memory/image_memory_builder.py:406`, `fairies/P20_Somatic/SomaticMindFairy/mixins/personality_sifter.py:349-362`, `fairies/P30_Cognition/cognition/{cognition_router.py:905, drift_aware_responder.py:213, system_chat_responder.py:280}`, `tests/personal_ai_benchmark.py:81`. Every reader falls back to the env vars `PERSONAL_AI_API_KEY` / `ANTHROPIC_API_KEY` or degrades to "not configured" -- none has a hard-coded fallback value (checked, masked grep over all code dirs). The README can tell a fresh clone to create that file from a placeholder template or set the two env vars.

### Confirmed FALSE POSITIVES in mirror candidates (safe to include as-is)

| file:line | what it really is |
|---|---|
| `.env.example:25,28,31` | `ANTHROPIC_API_KEY` / `ELEVENLABS_API_KEY` / `OPENAI_API_KEY` = `your_..._here` placeholders (Shannon 3.4-3.7); all 11 assignments in that file were checked: ports, paths, `cuda`, `INFO`, placeholders only |
| `tests/personal_ai_benchmark.py:11, :897` | docstring / help text: `"your-key-here"` |
| `postal_core/akp_protocol.md:182` | protocol doc example `"auth_token": "opti..."` (a 21-char English placeholder in a JSON sample) |
| `postal_core/akp_protocol.md:608` | protocol doc example `"Bearer eyJh..."` -- 23 chars, truncated with `...`; a real JWT is 100+ chars with two dots |
| `fairies/P30_Cognition/AkashicInferenceFairy/_old_rwkv_DEPRECATED/rwkv_collision_adapter.py:201` | type annotation `token_importance: "torch.Tensor"` (deprecated copy; inventory excludes the dir anyway) |
| (excluded anyway) `Claude_Office/plans/POSTAL_INSIDE_PORTAL_PHASE1.md:302`, `sandbox/modality_gate_visual/...` x3 | design-doc pseudo-code `"token": "tok-..."` and sandbox copies of the two FPs above |

### NOT found in any mirror-candidate text file (0 matches after filters)

private-key blocks, real JWTs, GitHub / GitLab / AWS / Google (`AIza`, `ya29.`, `1//0`, `GOCSPX`) / Slack / Discord / Telegram / HuggingFace / npm / PyPI / SendGrid / Twilio / Stripe / OpenAI `sk-`/`sk-proj-` / OpenRouter / ElevenLabs / Steam keys, URLs carrying `user:password@host` credentials, email+password pairs, `Basic <b64>` headers, PowerShell `ConvertTo-SecureString -AsPlainText`, CLI inline passwords, Google service-account JSON, and high-entropy literals in key/token context.

### Google Drive OAuth (the `gdrive_*` MCP tools) -- credentials live OUTSIDE her tree

`fairies/P40_Sensory/mcp/akashic_mcp_server.py:820-823`, `postal_core/mcp.py:493-496` and `scripts/retrain_gdrive_to_cortex.py:68-70` read `%APPDATA%\Claude\gdrive\gcp-oauth.keys.json` (client secret) and `...\gdrive\token.json` (refresh token). Neither file exists anywhere under `akashic_v2/` (name scan of all 178k files: zero `oauth*`/`client_secret*`/`token.json` hits outside `.venv`/`research_repos`). The hard-coded `C:\Users\Ace\...` path string is a local-username disclosure only -- LOW for a private repo; the Builder may leave it.

### Credential-NAMED files -- her own tree (everything else is third-party or data)

| path | verdict |
|---|---|
| `fairies/P50_Persona/identity/personal_ai_secrets.json` | REAL -- see HELD_BACK |
| `.env.example` (5,879 B) | placeholders only -- safe; there is NO real `.env` anywhere in the tree |
| `state/shadow_snapshots/TokenBucketFairy.json` | false positive by name (rate-limiter fairy snapshot); `state/` is DATA and excluded regardless |

All 87 other name hits are third-party or build output: `.venv/.../certifi/cacert.pem` x2 (public CA bundle), `research_repos/llama.cpp/.../idea-arch.key` (Apple Keynote file), `research_repos/claude-code-*/**/*Secret*.ts|tsx`, `research_repos/**/.env.example`, `**/target/**/private.rs` (serde build output) and `lib-cookie.json`/`lib-match_token.json` cargo fingerprints, `RWKV-LM/**/20B_tokenizer.json`, `.cognitive/sessions/*.json`, `Claude_Office/sessions/*.json`, `SRM_Intake/.../SESSION_*.json`, `state/session_file_tracker.json` (all DATA dirs). Full list in section B.

### Denylist the Builder should carry (names, any depth) and the re-scan to run on STAGED files

`personal_ai_secrets.json`, `*secret*`, `*secrets*.json`, `.env` and `.env.*` except `*.example`, `credentials*.json`, `token*.json`, `client_secret*.json`, `service_account*.json`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.ppk`, `*.kdbx`, `id_rsa*`, `id_ed25519*`, `.netrc`, `_netrc`, `.git-credentials`, `*.token`, `*access_token*`, `*refresh_token*`. Then run `python -B _survey/rescan_a.py F:/Sandbox/akashic-v2-repo/code` -- expected result: exit 0, and with `--all` only the placeholder-hinted lines listed above (`.env.example`, `tests/personal_ai_benchmark.py`, `postal_core/akp_protocol.md`).

### Coverage caveats (honest edges of this hunt)

- Content scan skipped the known data/third-party/build dirs as instructed (`state/` except the 44 OPTIONAL `state/*.py|ps1` + `state/nous_workspace/*.py` from the inventory manifest, which WERE scanned: clean), `models`, `.venv`, `research_repos`, every `target/`, `tools/extracted`, and `fairies/boot_logs` (1.3 GB of boot JSONL; logs are excluded from the mirror). Everything else -- 90,381 text files, 296 MB, including all 1,390 INCLUDE + 44 OPTIONAL manifest files -- was scanned with the full pattern set.
- 7 files my crude heuristic would call "INCLUDED" were too large to scan (46-151 MB): `P10_Memory/Akashic_triple_helix_memory_storage/relational_clusters/AssociationCortexFairy/{concept_graph.backup_*.json, helix_cards/cards_backup_*.json, graph_backups/*.json}`. They are memory DATA (the inventory excludes them); the Builder's 5 MB cap and DATA rules must keep them out.
- One junction was found and NOT followed: `P10_Memory/Akashic_triple_helix_memory_storage/system` -> `F:\Sandbox\failure_factory\ebook_copy\...` (outside her tree). The sync script must not follow it either.
- Her `.git` and the nested `dashboard/.git` were never opened (the task forbids touching them), so whether the old history ever carried the two keys is unknown -- rotate regardless.
- This hunt is format- and name-based. Context/entropy hunting is HUNT B's job; the two hunts are independent by design.

## Coverage

- directories walked: 11,997; files seen: 178,452
- files content-scanned: 90,381 (295.9 MB)
- skipped for content because inside a data/third-party/build dir: 87,178 (`.git .venv venv node_modules __pycache__ target models research_repos state site-packages .pytest_cache boot_logs` and `tools/extracted`; these were still walked for credential-named FILES)
- skipped for size: 37 (cap 25 MB for files the mirror could include, 1 MB for files it would exclude); skipped as binary (NUL in first 8 KB): 5; errors: 0
- inventory manifest cross-reference rows: 1,434 (INCLUDE/OPTIONAL from `_survey/inventory.md` sibling)
- content patterns: Anthropic `sk-ant-`, OpenAI `sk-`/`sk-proj-`, OpenRouter, Stripe, GitHub `ghp_`/`github_pat_`/`gho_`..., GitLab, AWS `AKIA`+secret, Google `AIza`/`ya29.`/`1//0` refresh/`GOCSPX` client secret/client id, Slack `xox*`+webhooks, Discord bot tokens+webhooks, Telegram, HuggingFace, npm, PyPI, SendGrid, Twilio, ElevenLabs, Steam Web API key (assignment + URL), `-----BEGIN * PRIVATE KEY-----`, JWT `eyJ..eyJ..`, `Bearer <literal>`, `Basic <b64>`, URLs carrying `user:password@host`, password/secret literal assignments, ENV-style `X_KEY=...`, PowerShell `ConvertTo-SecureString ... -AsPlainText`, CLI inline passwords, email+password pairs, SSH private-key path refs, and a high-entropy (Shannon >= 4.3, len >= 32) literal in key/token context.

## A. Content findings

Total raw matches: **15** (CRITICAL 1, HIGH 14); in files a code-only mirror would include: **11**.

By kind:

- Password/secret literal assignment: 10 (in mirror candidates: 6)
- ENV-style secret assignment: 3 (in mirror candidates: 3)
- Bearer header with literal: 1 (in mirror candidates: 1)
- Anthropic API key: 1 (in mirror candidates: 1)

### A1. Matches in files a code-only mirror WOULD include (11)

| # | file:line | kind | first4 | len | included? | sev | placeholder? | context (masked) |
|---|---|---|---|---|---|---|---|---|
| 1 | `fairies/P50_Persona/identity/personal_ai_secrets.json:7` | Anthropic API key | `sk-a` | 108 | YES? (heuristic only; not in inventory manifest) | CRITICAL |  | `"anthropic_api_key": "sk-a..[108]"` |
| 2 | `.env.example:25` | ENV-style secret assignment | `your` | 27 | YES (both) | HIGH | hint | `ANTHROPIC_API_KEY=your..[27]` |
| 3 | `.env.example:28` | ENV-style secret assignment | `your` | 24 | YES (both) | HIGH | hint | `ELEVENLABS_API_KEY=your..[24]` |
| 4 | `.env.example:31` | ENV-style secret assignment | `your` | 20 | YES (both) | HIGH | hint | `OPENAI_API_KEY=your..[20]` |
| 5 | `fairies/P30_Cognition/AkashicInferenceFairy/_old_rwkv_DEPRECATED/rwkv_collision_adapter.py:201` | Password/secret literal assignment | `torc` | 12 | YES? (heuristic only; not in inventory manifest) | HIGH |  | `token_importance: "torc..[12]",` |
| 6 | `fairies/P50_Persona/identity/personal_ai_secrets.json:2` | Password/secret literal assignment | `-2oO` | 32 | YES? (heuristic only; not in inventory manifest) | HIGH |  | `"api_key": "-2oO..[32]",` |
| 7 | `fairies/P50_Persona/identity/personal_ai_secrets.json:7` | Password/secret literal assignment | `sk-a` | 108 | YES? (heuristic only; not in inventory manifest) | HIGH |  | `"anthropic_api_key": "sk-a..[108]"` |
| 8 | `postal_core/akp_protocol.md:182` | Password/secret literal assignment | `opti` | 21 | YES (both) | HIGH |  | `"auth_token": "opti..[21]",` |
| 9 | `postal_core/akp_protocol.md:608` | Bearer header with literal | `eyJh` | 23 | YES (both) | HIGH | hint | `"auth_token": "Bearer eyJh..[23]"` |
| 10 | `tests/personal_ai_benchmark.py:11` | Password/secret literal assignment | `your` | 13 | YES (both) | HIGH | hint | `export PERSONAL_AI_API_KEY="your..[13]"` |
| 11 | `tests/personal_ai_benchmark.py:897` | Password/secret literal assignment | `your` | 13 | YES (both) | HIGH | hint | `print('  {"api_key": "your..[13]"}')` |

### A2. CRITICAL/HIGH matches in files the mirror would EXCLUDE (data/copies/office) -- still worth knowing (4)

| # | file:line | kind | first4 | len | included? | sev | placeholder? | context (masked) |
|---|---|---|---|---|---|---|---|---|
| 1 | `Claude_Office/plans/POSTAL_INSIDE_PORTAL_PHASE1.md:302` | Password/secret literal assignment | `tok-` | 8 | no (dir:Claude_Office) | HIGH |  | `tunnel[3].send({"cmd": "subscribe", "token": "tok-..[8]",` |
| 2 | `sandbox/modality_gate_visual/fairies/P30_Cognition/AkashicInferenceFairy/_old_rwkv_DEPRECATED/rwkv_collision_adapter.py:201` | Password/secret literal assignment | `torc` | 12 | no (dir:sandbox) | HIGH |  | `token_importance: "torc..[12]",` |
| 3 | `sandbox/modality_gate_visual/tests/personal_ai_benchmark.py:11` | Password/secret literal assignment | `your` | 13 | no (dir:sandbox) | HIGH | hint | `export PERSONAL_AI_API_KEY="your..[13]"` |
| 4 | `sandbox/modality_gate_visual/tests/personal_ai_benchmark.py:897` | Password/secret literal assignment | `your` | 13 | no (dir:sandbox) | HIGH | hint | `print('  {"api_key": "your..[13]"}')` |

### A3. MEDIUM/LOW matches in excluded files (0), summarised per file


## B. Credential-NAMED files (anywhere in the tree, incl. data dirs)

STRONG name matches (the task's list: credentials*.json, token*.json, client_secret*.json, *.pem, *.key, id_rsa*, .env*, .netrc, *.p12, *.pfx, *secret*, plus .git-credentials, *.ppk, *.kdbx, service_account*.json, *.htpasswd, *.token, *access_token*, *refresh_token*, *.p8, *.jwk(s), *.keystore, *.jks): **19**.  
WEAK name matches (broadened: *password*, *passwd*, *apikey*, *api_key*, *session*.json, *cookie*, *private*, *.crt/.cer/.der/.asc/.gpg, oauth*.json, vault*, ...): **71**.

### B1. STRONG matches -- in files the mirror could include

- `.env.example` (5,879 B) glob `.env.*` -- heuristic INCLUDED (code/config/doc), inventory manifest: INCLUDE
- `fairies/P50_Persona/identity/personal_ai_secrets.json` (351 B) glob `*secret*` -- heuristic INCLUDED (code/config/doc), inventory manifest: -

### B2. STRONG matches -- in excluded locations, grouped by top-level dir

**research_repos/** -- 12 file(s)

  globs: `*secret*` x9, `.env.*` x2, `*.key` x1

  - `research_repos/llama.cpp/docs/development/llama-star/idea-arch.key` (488,591 B) `*.key`
  - `research_repos/MAMBA_CUDA_OPTIMIZATION_SECRETS.md` (7,350 B) `*secret*`
  - `research_repos/claude-code-nirholas/src/bridge/workSecret.ts` (4,803 B) `*secret*`
  - `research_repos/claude-code-nirholas/src/commands/install-github-app/CheckExistingSecretStep.tsx` (18,328 B) `*secret*`
  - `research_repos/claude-code-nirholas/src/services/teamMemorySync/secretScanner.ts` (9,784 B) `*secret*`
  - `research_repos/claude-code-nirholas/src/services/teamMemorySync/teamMemSecretGuard.ts` (1,598 B) `*secret*`
  - `research_repos/claude-code-source/bridge/workSecret.ts` (4,799 B) `*secret*`
  - `research_repos/claude-code-source/commands/install-github-app/CheckExistingSecretStep.tsx` (18,324 B) `*secret*`
  - `research_repos/claude-code-source/services/teamMemorySync/secretScanner.ts` (9,782 B) `*secret*`
  - `research_repos/claude-code-source/services/teamMemorySync/teamMemSecretGuard.ts` (1,596 B) `*secret*`
  - `research_repos/claude-code-nirholas/.env.example` (12,415 B) `.env.*`
  - `research_repos/claude-code-nirholas/web/.env.example` (103 B) `.env.*`

**.venv/** -- 4 file(s)

  globs: `*secret*` x2, `*.pem` x2

  - `.venv/Lib/site-packages/certifi/cacert.pem` (270,954 B) `*.pem`
  - `.venv/Lib/site-packages/pip/_vendor/certifi/cacert.pem` (291,366 B) `*.pem`
  - `.venv/Lib/site-packages/pydantic_settings/sources/providers/nested_secrets.py` (6,622 B) `*secret*`
  - `.venv/Lib/site-packages/pydantic_settings/sources/providers/secrets.py` (4,303 B) `*secret*`

**state/** -- 1 file(s)

  globs: `token*.json` x1

  - `state/shadow_snapshots/TokenBucketFairy.json` (322 B) `token*.json`

### B3. WEAK matches -- summary (glob x top-level dir), mirror candidates listed in full

Mirror candidates among WEAK matches: 0


| glob | top-level dir | count | sample |
|---|---|---|---|
| `*private*` | dashboard | 11 | `dashboard/src-tauri/target/release/build/thiserror-279f3ace2f42cd9b/out/private.rs`; `dashboard/src-tauri/target/release/build/thiserror-02a9a41a8de56ac1/out/private.rs`; `dashboard/src-tauri/target/release/build/serde_core-675b625e99c5bbe3/out/private.rs` |
| `*session*.json` | .cognitive | 10 | `.cognitive/sessions/session_20260122_115826.json`; `.cognitive/sessions/session_20260206_151635.json`; `.cognitive/sessions/session_20260212_192750.json` |
| `*apikey*` | research_repos | 7 | `research_repos/claude-code-source/hooks/useApiKeyVerification.ts`; `research_repos/claude-code-source/components/ApproveApiKey.tsx`; `research_repos/claude-code-source/commands/install-github-app/ApiKeyStep.tsx` |
| `*private*` | somatic_bevy | 6 | `somatic_bevy/target/release/build/serde_core-db46ee45286b7126/out/private.rs`; `somatic_bevy/target/release/build/serde-b59479b6347b2838/out/private.rs`; `somatic_bevy/target/debug/build/serde_core-ec66da306842655f/out/private.rs` |
| `*private*` | postal_core | 6 | `postal_core/target/release/build/serde_core-47e4e7fd7028a44e/out/private.rs`; `postal_core/target/release/build/serde-b59479b6347b2838/out/private.rs`; `postal_core/target/debug/build/serde_core-ec66da306842655f/out/private.rs` |
| `*private*` | rwkv_inference | 4 | `rwkv_inference/target/release/build/serde_core-ca7de5405d287ec9/out/private.rs`; `rwkv_inference/target/release/build/serde_core-01ee84361e9176a6/out/private.rs`; `rwkv_inference/target/release/build/serde-5c89248cb73b8df9/out/private.rs` |
| `*token*.json` | dashboard | 4 | `dashboard/src-tauri/target/release/.fingerprint/match_token-6c47552b439ff0ab/lib-match_token.json`; `dashboard/src-tauri/target/release/.fingerprint/match_token-452ae80360b67e1a/lib-match_token.json`; `dashboard/src-tauri/target/debug/.fingerprint/match_token-8910c53ed7525375/lib-match_token.json` |
| `*session*.json` | Claude_Office | 4 | `Claude_Office/sessions/session_20260104_001921.json`; `Claude_Office/sessions/session_20260104_002114_progress.json`; `Claude_Office/sessions/session_20260104_002206_complete.json` |
| `*private*` | .venv | 4 | `.venv/Lib/site-packages/torch/include/torch/csrc/profiler/standalone/privateuse1_observer.h`; `.venv/Lib/site-packages/torch/include/ATen/detail/PrivateUse1HooksInterface.h`; `.venv/Lib/site-packages/torch/include/ATen/core/GeneratorForPrivateuseone.h` |
| `*cookie*.json` | dashboard | 3 | `dashboard/src-tauri/target/release/.fingerprint/cookie-fa87a5ecf87465ba/lib-cookie.json`; `dashboard/src-tauri/target/debug/.fingerprint/cookie-9451ed34318d50a4/lib-cookie.json`; `dashboard/src-tauri/target/debug/.fingerprint/cookie-41c0b6844712ee92/lib-cookie.json` |
| `*api_key*` | sandbox | 2 | `sandbox/modality_gate_visual/research_repos/openai-agents-python/tests/tracing/test_processor_api_key.py`; `sandbox/modality_gate_visual/research_repos/openai-agents-python/tests/tracing/test_set_api_key_fix.py` |
| `*token*.json` | research_repos | 2 | `research_repos/RWKV-LM/RWKV-v4neo/20B_tokenizer.json`; `research_repos/RWKV-LM/RWKV-v4/20B_tokenizer.json` |
| `*api_key*` | research_repos | 2 | `research_repos/openai-agents-python/tests/tracing/test_processor_api_key.py`; `research_repos/openai-agents-python/tests/tracing/test_set_api_key_fix.py` |
| `*password*` | .venv | 2 | `.venv/Lib/site-packages/win32/Demos/NetValidatePasswordPolicy.py`; `.venv/Lib/site-packages/win32/Demos/security/sspi/validate_password.py` |
| `*session*.json` | state | 1 | `state/session_file_tracker.json` |
| `*session*.json` | SRM_Intake | 1 | `SRM_Intake/2026-01-28/SESSION_Fifth_Ring_Fairy_Organization.json` |
| `.npmrc` | research_repos | 1 | `research_repos/llama.cpp/tools/server/webui/.npmrc` |
| `*credentials*` | .venv | 1 | `.venv/Lib/site-packages/mcp/client/auth/extensions/client_credentials.py` |

## C. Not content-scanned because of size

- `P10_Memory/Akashic_triple_helix_memory_storage/relational_clusters/AssociationCortexFairy/helix_cards/cards_backup_1770369313.json` 151.5 MB -- heuristic INCLUDED, inventory -
- `sandbox/cortex_coherence_shape/boot2_err.log` 50.0 MB -- heuristic EXCLUDED, inventory -
- `P10_Memory/Akashic_triple_helix_memory_storage/relational_clusters/AssociationCortexFairy/graph_backups/concept_graph_pre_save_20260206_020213.json` 49.1 MB -- heuristic INCLUDED, inventory -
- `P10_Memory/Akashic_triple_helix_memory_storage/relational_clusters/AssociationCortexFairy/graph_backups/concept_graph_pre_save_20260206_020123.json` 49.0 MB -- heuristic INCLUDED, inventory -
- `P10_Memory/Akashic_triple_helix_memory_storage/relational_clusters/AssociationCortexFairy/graph_backups/concept_graph_pre_save_20260206_020012.json` 48.9 MB -- heuristic INCLUDED, inventory -
- `P10_Memory/Akashic_triple_helix_memory_storage/relational_clusters/AssociationCortexFairy/graph_backups/concept_graph_pre_save_20260206_015845.json` 48.9 MB -- heuristic INCLUDED, inventory -
- `P10_Memory/Akashic_triple_helix_memory_storage/relational_clusters/AssociationCortexFairy/graph_backups/concept_graph_pre_save_20260206_015800.json` 48.9 MB -- heuristic INCLUDED, inventory -
- `P10_Memory/Akashic_triple_helix_memory_storage/relational_clusters/AssociationCortexFairy/concept_graph.backup_20260223_165247.json` 46.0 MB -- heuristic INCLUDED, inventory -
- `diaries/Fairies/GoalSchedulerFairy/diary.md` 6.4 MB -- heuristic EXCLUDED, inventory -
- `stateboot_test2.log` 6.1 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ.clerk.primrose/2026-02-06.jsonl` 3.8 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ_template_seed/2026-02-06.jsonl` 3.5 MB -- heuristic EXCLUDED, inventory -
- `sandbox/satellite_ack/boot_err.log` 3.4 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ.clerk.primrose/2026-02-11.jsonl` 3.2 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ.clerk.primrose/2026-02-13.jsonl` 3.1 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ_template_seed/2026-02-11.jsonl` 3.0 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ_template_seed/2026-02-13.jsonl` 2.9 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ.clerk.primrose/2026-02-14.jsonl` 2.9 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ.clerk.primrose/2026-02-12.jsonl` 2.7 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ_template_seed/2026-02-14.jsonl` 2.7 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ.clerk.primrose/2026-02-10.jsonl` 2.6 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ_template_seed/2026-02-12.jsonl` 2.5 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ_template_seed/2026-02-10.jsonl` 2.5 MB -- heuristic EXCLUDED, inventory -
- `fairies/diaries/Fairies/InterestSchedulerFairy/diary.md` 2.3 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ.clerk.primrose/2026-02-07.jsonl` 2.1 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ_template_seed/2026-02-07.jsonl` 2.0 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ.clerk.primrose/2026-02-15.jsonl` 1.9 MB -- heuristic EXCLUDED, inventory -
- `boot_debug.log` 1.8 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ_template_seed/2026-02-15.jsonl` 1.8 MB -- heuristic EXCLUDED, inventory -
- `clean_boot2_err.log` 1.7 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ.clerk.primrose/2026-02-09.jsonl` 1.6 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ.clerk.primrose/2026-02-16.jsonl` 1.5 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ_template_seed/2026-02-09.jsonl` 1.5 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ.clerk.primrose/2026-02-08.jsonl` 1.4 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ_template_seed/2026-02-16.jsonl` 1.4 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/organ_template_seed/2026-02-08.jsonl` 1.3 MB -- heuristic EXCLUDED, inventory -
- `diaries/Fairies/my_organ/2026-02-16.jsonl` 1.2 MB -- heuristic EXCLUDED, inventory -

## D. Junctions / symlinks skipped (never followed)

- `P10_Memory/Akashic_triple_helix_memory_storage/system`

## E. Walk errors (0)

