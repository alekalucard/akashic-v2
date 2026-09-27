# SECRET HUNT B -- hard-coded values by CONTEXT + ENTROPY

_Written 2026-09-26 18:56 by the survey:secrets-B agent. Independent of Hunt A. Tree read-only; nothing in her tree was modified; her old `.git` was not touched (one byte-grep of `.git/index` to test whether a path was ever tracked). No secret value is reproduced beyond its first 4 characters._

## 0. Verdict in one paragraph

Exactly **one file** in Sour's tree holds real credentials: `fairies/P50_Persona/identity/personal_ai_secrets.json` (351 B, dated 2025-12-26) -- an **Anthropic API key** (`sk-a…`, 108 chars) and a **Personal.AI API key** (`-2oO…`, 32 chars). Both keys occur **nowhere else** (a shape-regex search over every text-like file including `state/`, `backups/`, `sandbox/`, `Claude_Office/`, `.bak` copies and `.jsonl`/`.log` returned that single file), and her old repo's index never tracked the file. A code-only mirror that copies `*.json` under `fairies/` **would include it** unless it is held back by path. Everything else this hunt surfaced is either a placeholder (`.env.example`), a default game-server DB password in a satellite task file, a public SSH key, LAN topology, or a false positive (Python `key=` kwargs, module paths, GGUF tensor names, folder names). The gdrive OAuth client secret + refresh token live **outside** the tree at `%APPDATA%\Claude\gdrive\`.

Scale: 301,057 files walked, 204,988 text files content-scanned (3,693 full code passes + 201,295 light data passes, 1.54 GiB read, 1129 s), 23,069 raw detector rows, 110 credential-name hits; after hand triage the only rows that are real are the two keys above (section 5b).

**Builder must:** hold back `fairies/P50_Persona/identity/personal_ai_secrets.json` whole; add `personal_ai_secrets.json`, `*_secrets.json`, `token.json`, `gcp-oauth*.json` to `.gitignore` (her current `.gitignore` covers `.env`, `*.pem`, `*.key`, `credentials*.json` only). **Ace should:** rotate both keys regardless (plaintext for 9 months on a machine with satellites and MCP servers reading the file), then re-create the file locally from the shape documented in `fairies/P50_Persona/identity/__init__.py:57-67`.

## 1. Hand-verified findings

| # | file:line | kind | first 4 | INCLUDED by a code-only mirror? | severity | notes |
|---|-----------|------|---------|----------------------------------|----------|-------|
| 1 | `fairies/P50_Persona/identity/personal_ai_secrets.json:7` | Anthropic API key (`sk-ant-…`, 108 chars, H=5.51) under JSON key `anthropic_api_key` | `sk-a` | YES by extension (.json under fairies/). The inventory's proposed manifest already drops it as SECRET-NAMED; the builder must make that an explicit path rule, not a name heuristic | **CRITICAL** | Live-format key. Consumed via `identity.load_secrets()['anthropic_api_key']` by fairies/P30_Cognition/cognition/system_chat_responder.py:281, drift_aware_responder.py:214 (env var ANTHROPIC_API_KEY takes priority). Appears in exactly ONE file tree-wide (shape search over *.py/json/md/txt/log/jsonl/bak incl. state/, backups/, sandbox/, Claude_Office/). NOT tracked by her old .git (index has 0 mentions). HOLD BACK the whole file; recommend ROTATE anyway (file dated 2025-12-26, has sat in a plaintext JSON for 9 months). |
| 2 | `fairies/P50_Persona/identity/personal_ai_secrets.json:2` | Personal.AI API key (32 chars, H=4.73) under JSON key `api_key` | `-2oO` | YES by extension unless held back | **HIGH** | Sent as `x-api-key` header by fairies/P50_Persona/memory/personal_ai_bridge.py:564, tests/personal_ai_benchmark.py:186, fairies/P30_Cognition/cognition/cognition_router.py:907 (fallback env PERSONAL_AI_API_KEY). Exactly ONE copy tree-wide. Same file as above -> one HOLD BACK covers both. |
| 3 | `.satellite/tasks/pending/sourpatches_setup.json:20 and :26` | password embedded in a CLI command (`mysql -u root` with the password passed via the `-p` flag, then `acore_world`, inside `docker exec`) | `pass` | YES -- the inventory's proposed manifest marks this file INCLUDE (json config) | **LOW** | The password is the AzerothCore docker default (the literal word). Real but not sensitive beyond the LAN game server; still a hard-coded credential in a task file. Suggest exclude .satellite/tasks/ and .satellite/*.json state files (they are runtime state, not code). |
| 4 | `.satellite/shared_state.json:8` | SSH PUBLIC key (`ssh-ed25519 AAAA…`, 68 chars, comment `Ace@DESK…`) inside a queued shell command that appends it to ~/.ssh/authorized_keys | `AAAA` | NO in the inventory's manifest (routed to DATA by name/size); YES if `.satellite/*.json` were taken wholesale | **INFO** | Public half only -- not a secret. It does identify Ace's desktop hostname and grants nothing. Exclude as runtime state anyway. |
| 5 | `.satellite/network_config.json:6-17 (+ .bak_satack_0625), peer_registry.json, gpu_fleet.json, ALIENWARE_SETUP.md:7, setup_satellite.sh:21-22` | LAN topology: hostnames, LAN IPs (192.168.1.6/.24/.74), `ssh_user` name, CIFS mount user | `n/a` | MIXED: manifest INCLUDES network_config.json, ALIENWARE_SETUP.md, setup_satellite.sh (18 .satellite files total); peer_registry.json, gpu_fleet.json, shared_state.json, *.bak are routed to DATA | **INFO (privacy, not secret)** | No passwords or keys. Private repo -> acceptable, but the *.json here are live state files, not code; recommend the mirror takes .satellite/*.py, *.sh, *.md, deploy_fairies/, directives/ and skips the *.json/.bak state. |
| 6 | `fairies/P40_Sensory/mcp/akashic_mcp_server.py:821` | absolute credential path with Windows username: `C:\Users\Ace\AppData\Roaming\Claude\gdrive` (token.json, gcp-oauth.keys.json) | `C:\U` | YES (core code file) | **INFO** | Path only; the files themselves are OUT of her tree (verified: %APPDATA%\Claude\gdrive\gcp-oauth.keys.json 404 B, token.json 735 B exist there, and nowhere inside akashic_v2). tools/train_gdrive.py:43-45 and scripts/retrain_gdrive_to_cortex.py:68-70 use %APPDATA% instead (portable). Cosmetic: switch the MCP server to os.environ['APPDATA'] too. |
| 7 | `.env.example:25,28,31,74` | API key placeholders (ANTHROPIC_API_KEY / ELEVENLABS_API_KEY / OPENAI_API_KEY / QDRANT_API_KEY) | `your` | YES | **NONE (verified placeholder)** | All four values start `your-…` (val_len 27/24/20/20). Lines 15,18 hold local absolute paths (F:/S…). Safe to include. |
| 8 | `tests/personal_ai_benchmark.py:82` | hard-coded absolute path to the secrets file (F:\Sandbox\failure_factory\akashic_v2\fairies\P50_Persona\identity\personal_ai_secrets.json) | `F:\S` | YES | **INFO** | Path, not value; :914 prints only the key's last 4 chars and :964 strips it from saved results. Fine to include; it documents where the held-back file must be restored. |
| 9 | `hardware/drivers/orbi.py:106,606 + fairies/P40_Sensory/mcp/akashic_mcp_server.py:4638` | router admin password parameter (`password: str = ""`), Basic-auth header built from it | `""` | YES | **NONE** | Default is empty; the password is supplied at call time. No literal anywhere in the tree (grep for `password\s*=\s*["'][^"']{3,}` over all code dirs -> only these parameter defaults). |
| 10 | `fairies/P30_Cognition/cognition/thought_chain_sequencer_fairy.py:120` | `ANTHROPIC_API_KEY = ""` (empty literal, LLM disabled) | `""` | YES | **NONE** | Empty; documented as 'LOCAL ONLY'. |

Inclusion rule used above and in the appendix: a file is INCLUDED when it sits in one of her own source folders with a code/config extension and is not under `state/ .venv/ research_repos/ backups/ sandbox/ diaries/ Claude_Office/ SRM_Intake/ dream_states/ .cognitive/ directives/ tracer_pool/ memory/ P10_Memory/Akashic_* stores`, any `models/`, `target/`, `node_modules/`, `tools/extracted/`, and is not a `.bak*`/`.log`/data-extension file. `.satellite/` is marked conditional because the inventory classed it DATA-dominant.

## 2. Where each service's credentials actually live (config map)

| service | code site(s) | credential location | in tree? | status |
|---------|--------------|---------------------|----------|--------|
| Google Drive (gdrive_* MCP tools) | `fairies/P40_Sensory/mcp/akashic_mcp_server.py:820-823, 1645-1669` (hard-coded `C:\Users\Ace\AppData\Roaming\Claude\gdrive`); `tools/train_gdrive.py:43-46`; `scripts/retrain_gdrive_to_cortex.py:68-71` (both `%APPDATA%\Claude\gdrive`) | `gcp-oauth.keys.json` (OAuth client, 404 B, 2025-12-29) + `token.json` (refresh/access token, 735 B, 2026-06-16) | **NO** -- verified present out-of-tree, absent in-tree by name and by content shape (`GOCSPX-`, `1//0`, `ya29.`, `.apps.googleusercontent.com`) | OK. `state/gdrive_*.{log,json}` are progress logs (excluded with state/) |
| Personal.AI (Sourpatches twin) | `fairies/P50_Persona/identity/__init__.py:31,53-81` (`load_secrets`), `fairies/P50_Persona/memory/personal_ai_bridge.py:886-891`, `fairies/P30_Cognition/cognition/cognition_router.py:905-907`, `tests/personal_ai_benchmark.py:72-90` | `fairies/P50_Persona/identity/personal_ai_secrets.json` key `api_key`; env `PERSONAL_AI_API_KEY` | **YES -- finding #2** | HOLD BACK + rotate |
| Anthropic | 13 code sites read `os.getenv('ANTHROPIC_API_KEY')` (unconscious_mind_fairy.py:153, prompt_aware_mixin.py:49, fairy_world_foundation.py:275, dynamic_goal_generator.py:217, intent_to_goal_fairy.py:75, visual_memory_system.py:387/530, image_memory_builder.py:388, generate_encyclopedia_entries.py:496, …); 3 fall back to the secrets file: system_chat_responder.py:275-282, drift_aware_responder.py:208-215, identity/__init__.py:80 | env var (not in tree) **and** `personal_ai_secrets.json` key `anthropic_api_key` | **YES -- finding #1** | HOLD BACK + rotate. `akashic_mcp_server.py:2135` has the vision call disabled (`api_key = None`), `thought_chain_sequencer_fairy.py:120` is `""` |
| OpenAI | only `.env.example:31` placeholder; no `sk-`/`sk-proj-` shaped literal anywhere in code | none in tree | -- | nothing to do |
| Ollama | `infrastructure/farm_ollama_adapter.py:37` `OLLAMA_HOST_URL` env, default `http://localhost…` | none (unauthenticated local API) | -- | nothing to do |
| ElevenLabs / Qdrant | `.env.example:28,74` placeholders only | none in tree | -- | nothing to do |
| Steam / Discord / Slack / Telegram / GitHub / AWS / HuggingFace | 'steam' occurs only as a window-title keyword (`infrastructure/vision_ground.py:833`, `fairies/P40_Sensory/WindowSenseFairy/fairy.py:732`); no token-shaped literal of any of these formats in scanned files | none | -- | nothing to do |
| Netgear Orbi router | `hardware/drivers/orbi.py:106` (`password=""` default), MCP tool `orbi_status(router_ip, password)` :4638 | supplied at call time | -- | no literal in tree |
| Satellite SSH (alienware .24, laptop .74) | `.satellite/setup_satellite.sh:21-22,41-51` (ssh-copy-id, key-based), `.satellite/shared_state.json:8` (public key push) | `~/.ssh/id_rsa` on the desktop (out of tree) | public key only in tree | INFO |
| AzerothCore MySQL (WoW sandbox on alienware) | `.satellite/tasks/pending/sourpatches_setup.json:20,26` | inline `-p<pw>` = docker default | **conditional (finding #3)** | exclude .satellite state files |
| Git identity | `.git/config:9`, `dashboard/.git/config:9` `user.email = ace@akashic.foundation`; **no remote configured in either** (so no token-in-remote-URL leak) | -- | not mirrored (.git dirs) | fine |

## 3. Credential-named FILES anywhere in the tree (name match; content NOT scanned for data dirs)

Patterns: `credentials*.json token*.json client_secret*.json service_account*.json gcp-oauth* *.pem *.key id_rsa* id_ed25519* .env .env.* .netrc _netrc *.p12 *.pfx *.ppk authorized_keys .git-credentials .npmrc .pypirc *secret* *credential* *passw*` (case-insensitive), via `find` over the whole tree plus the scanner's own name pass.

### 3a. Outside .venv / research_repos

| path | size | assessment |
|------|------|------------|
| `.env.example` | 5,879 B | template; verified all key values are `your-…` placeholders -> SAFE |
| `fairies/P50_Persona/identity/personal_ai_secrets.json` | 351 B | REAL SECRETS (Anthropic + Personal.AI keys) -> HOLD BACK, ROTATE |
| `state/shadow_snapshots/TokenBucketFairy.json` | 322 B | name-match only (TokenBucketFairy = rate-limiter fairy); in state/ (excluded) |

### 3b. Inside third-party / build / data dirs (.venv, research_repos, dashboard, somatic_bevy, postal_core, rwkv_inference, state, tools/extracted, backups, sandbox, models)

| path | size | assessment |
|------|------|------------|
| `.venv/Lib/site-packages/certifi/cacert.pem` | 270,954 B | public CA bundle (third-party) |
| `.venv/Lib/site-packages/mcp/client/auth/extensions/client_credentials.py` | 20,897 B | third-party library source (name match on secret/password/credential) |
| `.venv/Lib/site-packages/pip/_vendor/certifi/cacert.pem` | 291,366 B | public CA bundle (third-party) |
| `.venv/Lib/site-packages/pydantic_settings/sources/providers/nested_secrets.py` | 6,622 B | third-party library source (name match on secret/password/credential) |
| `.venv/Lib/site-packages/pydantic_settings/sources/providers/secrets.py` | 4,303 B | third-party library source (name match on secret/password/credential) |
| `.venv/Lib/site-packages/win32/Demos/NetValidatePasswordPolicy.py` | 3,635 B | third-party library source (name match on secret/password/credential) |
| `.venv/Lib/site-packages/win32/Demos/security/sspi/validate_password.py` | 1,164 B | third-party library source (name match on secret/password/credential) |
| `research_repos/MAMBA_CUDA_OPTIMIZATION_SECRETS.md` | 7,350 B | third-party clone (name match) |
| `research_repos/claude-code-nirholas/.env.example` | 12,415 B | third-party template |
| `research_repos/claude-code-nirholas/src/bridge/workSecret.ts` | 4,803 B | third-party clone (name match) |
| `research_repos/claude-code-nirholas/src/commands/install-github-app/CheckExistingSecretStep.tsx` | 18,328 B | third-party clone (name match) |
| `research_repos/claude-code-nirholas/src/services/teamMemorySync/secretScanner.ts` | 9,784 B | third-party clone (name match) |
| `research_repos/claude-code-nirholas/src/services/teamMemorySync/teamMemSecretGuard.ts` | 1,598 B | third-party clone (name match) |
| `research_repos/claude-code-nirholas/web/.env.example` | 103 B | third-party template |
| `research_repos/claude-code-source/bridge/workSecret.ts` | 4,799 B | third-party clone (name match) |
| `research_repos/claude-code-source/commands/install-github-app/CheckExistingSecretStep.tsx` | 18,324 B | third-party clone (name match) |
| `research_repos/claude-code-source/services/teamMemorySync/secretScanner.ts` | 9,782 B | third-party clone (name match) |
| `research_repos/claude-code-source/services/teamMemorySync/teamMemSecretGuard.ts` | 1,596 B | third-party clone (name match) |
| `research_repos/llama.cpp/docs/development/llama-star/idea-arch.key` | 488,591 B | Apple Keynote document, not a key (third-party) |
| `research_repos/llama.cpp/tools/server/webui/.npmrc` | 20 B | 20 B npm config, third-party clone |
| `research_repos/ollama/docs/images/n8n-credential-creation.png` | 43,948 B | third-party clone (name match) |

### 3c. Scanner's own name pass (hunt_b.py, all dirs incl. data dirs) -- cross-check

110 distinct name hits: 74 are scraped ebook/article JSON sections whose TITLE contains secret/password/credential (P10_Memory store, e.g. 'Show_And_Hide_Password_Using_JavaScript', 'The_lifecycle_of_a_secret'), 31 are third-party library/clone sources (.venv certifi `cacert.pem`, pywin32 password demos, claude-code `ApiKeyStep.tsx`, llama.cpp `idea-arch.key` Keynote file, `.npmrc`), 3 are tokenizer/token-bucket name collisions. None of those three groups is a credential file. The rest:

| path | pattern | size | in content-skipped dir? | assessment |
|------|---------|------|--------------------------|------------|
| `.env.example` | .env* | 5,879 B | no | template; verified all key values are `your-…` placeholders -> SAFE |
| `fairies\P50_Persona\identity\personal_ai_secrets.json` | name contains 'secret' | 351 B | no | REAL SECRETS (Anthropic + Personal.AI keys) -> HOLD BACK, ROTATE |

## 4. Blast-radius checks (are the real keys anywhere else?)

- Shape search `sk-ant-[A-Za-z0-9_-]{20,}` and `-2oO[A-Za-z0-9_-]{28}` (the exact 32-char shape of the Personal.AI key) across the WHOLE tree, glob `*.py *.json *.md *.txt *.bat *.ps1 *.toml *.yaml *.yml *.ini *.cfg *.env* *.jsonl *.log *.js *.ts *.rs *.lua *.sh *.html *.csv *.directive *.bak*` (this includes `state/` 22 GB, `backups/`, `sandbox/` copies, `Claude_Office/`, SRM_Intake, dream_states, diaries): **1 file** -> `fairies/P50_Persona/identity/personal_ai_secrets.json`.
- Name search for `personal_ai_secrets*` across the whole tree: **1 file** (no sandbox/backup copy).
- `.git/index` (her old repo, last written 2026-03-16): 0 occurrences of `personal_ai_secrets.json` -> never staged in the old history. (Also 0 for `.env.example`, `.satellite/shared_state.json`, `sourpatches_setup.json`.)
- `.gitignore` (root) lists `.env`, `*.pem`, `*.key`, `credentials*.json` -- **does not** cover `personal_ai_secrets.json`.
- Google formats (`GOCSPX-`, `1//0…`, `ya29.`, `AIza…`, `*.apps.googleusercontent.com`), GitHub (`ghp_/gho_/github_pat_`), AWS (`AKIA`), Slack (`xox*`), Discord token shape, HuggingFace (`hf_`), JWT (`eyJ…`), `-----BEGIN … PRIVATE KEY`, `Bearer <token>`, URLs carrying `user:password@host`: **0 hits** in every content-scanned file (see appendix stats).

## 5. Appendix -- automated context + entropy scan (hunt_b.py)

Scanner stats: binary_skipped=9,690, binary_sniffed=64, bytes_scanned=1,652,278,831, credfile_hits=110, deep_skipped_dirs=1,593, elapsed_s=1129.0, files_content_skipped=86,041, files_full=3,693, files_light=201,295, files_scanned=204,988, files_seen=301,057, light_oversize_skipped=214, oversize_skipped=11, reserved_skipped=9; walk/read errors=2

Method: every text file outside the skip dirs was read; (a) 22 known token formats; (b) quoted assignments on lines carrying a context word (key, token, secret, password, passwd, pwd, auth, credential, bearer, cookie, session, client_id, client_secret, refresh, webhook, access_key, private_key, passphrase, salt); (c) `KEY=value` env/ini/bat lines with a context word; (d) email + password within +-3 lines; (e) quoted string literals of length >= 20 and Shannon entropy > 4.0 (code files only; uuids and http/data URIs dropped). Data stores (SRM_Intake, P10_Memory stores, diaries, dream_states, .cognitive, backups, boot logs, Claude_Office, tracer_pool, waking_minds) got a light pass (a-d only, <= 1 MB). Values are masked at emit time; the findings file itself never held more than 4 characters of any value.

Raw rows by kind: context assignment=21074, high-entropy literal=1902, context env/ini assignment=90, JWT=2, Anthropic key=1

### 5a. False-positive classes (hand-checked on samples, rule-applied to the rest)

| class | rows | files | example (masked) |
|-------|------|-------|------------------|
| telemetry diary .jsonl field (`kind`/`session`) in diaries/ (data, excluded) | 12237 | 71 | `diaries\Shadow Fairies\organ_template_seed\2026-02-05.jsonl:3` sess…(len=19, H=3.43, mixed-punct) |
| boot-observation log field (`name`/`tname` = thread name) in fairies/boot_logs/*.jsonl | 8698 | 1980 | `fairies\boot_logs\20260128_212231_boot_observation.jsonl:102` post…(len=15, H=3.64, mixed-punct) |
| dotted/pathlike identifier (module path, filename, CLI flag, tensor name) | 1421 | 440 | `battery_accel.py:40` Brec…(len=70, H=4.85, mixed-punct) |
| CamelCase class / actor / shadow name (SHADOW_NAME, ACTOR_NAME, fairy registry lists) | 330 | 212 | `server.py:4706` Akas…(len=35, H=4.00, urlsafe-b64/alnum) |
| identifier / dict-key literal on a context-word line (`key="postal_…"`, `kind="…"`, css class, example doc) | 88 | 43 | `tests\test_helix_concept_migration.py:398` test…(len=16, H=3.28, urlsafe-b64/alnum) |
| runtime-state JSON content under fairies/ (association pattern keys, interest topics, avatar asset filenames) | 81 | 8 | `fairies\P50_Persona\Waking Minds\Sourpatches\newborn_state\learned_patterns.backup.json:122` asso…(len=80, H=4.29, mixed-punct) |
| python kwarg `key=` (sort/dict key function) | 78 | 43 | `tools\expand_manifold.py:177` node…(len=12, H=3.25, mixed-punct) |
| snake_case identifier / topic / domain / source / opcode name (`sourpatches_…`, `visual_experience_…`, `acknowledge_…`) | 40 | 22 | `sandbox\nous_manifold\proto_nous_memory.py:79` proj…(len=53, H=4.10, urlsafe-b64/alnum) |
| short lowercase identifier (postal example memory key `greeting`, achievement category, rel_name, icon) | 25 | 23 | `sandbox\pocket_dimension\fairies\P30_Cognition\AssociationCortexFairy\fairy.py:1244` Conc…(len=11, H=3.10, base64) |
| Claude_Office document text (excluded dir; already mirrored in the akashic-office repo) | 18 | 9 | `Claude_Office\CONTEXT_LIVE_SOUR.md:24` obse…(len=9, H=3.17, base64) |
| variable pass-through / identifier on the right-hand side (`api_key=personal_ai_key`, `client_id=client_id`, `token = tokens[i]`) | 12 | 10 | `tests\personal_ai_benchmark.py:902` api_…(len=8, H=3.00, mixed-punct) |
| known identifier (folder/class/amendment-id/model name) | 10 | 4 | `tools\recompile_codex_2026-04-20.py:34` 2026…(len=38, H=4.27, urlsafe-b64/alnum) |
| diary/log data line (.jsonl/.log inside a code folder) | 8 | 1 | `fairies\P50_Persona\Waking Minds\Sourpatches\diary\2026-08-31_diary.jsonl:25` wm_l…(len=43, H=4.13, urlsafe-b64/alnum) |
| SRM data text (TensorEnvelope payload / session note) | 7 | 2 | `SRM_Intake\2026-06-08\sourpatchesfairy.reflection-a6709333.json:4` sess…(len=7, H=2.13, base64) |
| SQL literal (WoW backport generator) | 4 | 2 | `sandbox\modality_gate_visual\fairies\P60_Executive\CardinalFairy\wow_backport\backport_generator.py:151` Equi…(len=24, H=4.05, base64) |
| hex-digit alphabet string used as a character set | 4 | 4 | `sandbox\modality_gate_visual\fairies\P30_Cognition\cognition\thought_chain_engine.py:208` 0123…(len=22, H=4.46, hex22) |
| alphabet string for random.choice | 2 | 2 | `sandbox\modality_gate_visual\fairies\P50_Persona\Waking Minds\Sourpatches\motor_practice.py:232` abcd…(len=26, H=4.70, base64) |
| tutorial sample JWT inside the P10_Memory ebook store (GeeksforGeeks article) | 2 | 2 | `P10_Memory\Akashic_triple_helix_memory_storage\system\programming\geeksforgeeks\51022deb_What_is_JSON_Web_Token_JWT\section_001_Main.json:5` eyJh…(len=177, H=5.52, mixed-punct) |

### 5b. Residual rows after FP rules (each hand-reviewed; verdict in last column)

| file:line | kind | masked value | included? | context (masked) | verdict |
|-----------|------|--------------|-----------|------------------|---------|
| `fairies\P50_Persona\identity\personal_ai_secrets.json:2` | context assignment | -2oO…(len=32, H=4.73, urlsafe-b64/alnum) | INCLUDED | `"api_key": "«-2oO…»",` | **REAL -- see finding #1/#2** |
| `fairies\P50_Persona\identity\personal_ai_secrets.json:7` | Anthropic key | sk-a…(len=108, H=5.51, urlsafe-b64/alnum) | INCLUDED | `"anthropic_api_key": "«sk-a…»"` | **REAL -- see finding #1/#2** |

### 5c. Skip policy of the content scan

Content-skipped (names still listed in section 3): `state/`, `.venv/`, `research_repos/`, `tools/extracted/`, any `models/`, `target/`, `node_modules/`, `__pycache__/`, `site-packages/`, `.git/` (root and nested `dashboard/.git`), `.pytest_cache/`.

Oversize (> 4 MB) text files NOT content-scanned: `P30_Cognition\data\concept_graph.backup_20260223_165359.json` (9,395,449 B); `P30_Cognition\data\concept_graph.json` (6,746,692 B) -- both are concept-graph data dumps (DATA class), so they need no hold-back but should not be mirrored either.

`deep_skipped_dirs=1,593`: directories deeper than 60 levels or with a path > 900 chars were not descended -- this is the runaway `sandbox/…/fairies/sandbox/consciousness_wiring_phase1/sandbox/…` copy chain named in the brief ('Filename too long'); it is a COPIES-class tree and is excluded from the mirror by class.

Known limits of this hunt: (a) the 4 MB / 1 MB size caps above; (b) light-pass files (data stores) were not entropy-scanned, only format/context/email-password scanned; (c) `\\?\`-prefixed reads were used, so long paths were readable, but the 60-level depth guard means the deepest sandbox copies were not opened -- they are duplicates of tree content by construction; (d) binary files (9,690 by extension + 64 by NUL sniff) were not decoded -- a secret inside a `.db`/`.pkl`/`.mmap` would not be seen by this hunt (nor mirrored, since they are data).

## 6. Recommendations for the BUILDER (this hunt's HELD_BACK list)

1. **HOLD BACK whole file:** `fairies/P50_Persona/identity/personal_ai_secrets.json` (finding #1 + #2). Nothing else in the tree needs holding back for secret content.
2. **Exclude as runtime state, not code:** `.satellite/*.json`, `.satellite/*.json.bak_*`, `.satellite/tasks/`, `.satellite/deploy_log.json`, `.satellite/cardinal_network_log.json` (findings #3-#5). Keep `.satellite/*.py`, `*.sh`, `*.md`, `deploy_fairies/`, `directives/`, `deploy_queue/README.md`.
3. **.gitignore additions** (defensive, beyond her current 4 lines): `personal_ai_secrets.json`, `*_secrets.json`, `*secrets*.json`, `token.json`, `gcp-oauth*.json`, `client_secret*.json`, `.env`, `.env.*`, `!.env.example`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `.satellite/*.json`.
4. **Post-stage re-scan** must include the two shape regexes from section 4 and the 22 known formats; expected result 0.
5. **Ace:** rotate the Anthropic key and the Personal.AI key; re-create `personal_ai_secrets.json` locally (schema in `fairies/P50_Persona/identity/__init__.py:57-67`), or move both to env vars (`ANTHROPIC_API_KEY`, `PERSONAL_AI_API_KEY`) which every consumer already prefers.

_Scanner and helpers: scratchpad `hunt_b.py`, `triage.py`, `mpeek.py` (masked viewer), `write_secrets_b.py` (this report). Findings JSONL is masked at source._
