# RESULT -- reviser's verdict on the akashic-v2 code mirror (2026-09-26)

**Verdict: SAFE-TO-PUSH.** One commit on `main`, fresh history, **no remote configured, nothing pushed** -- the push
is Ace's decision. Her tree `F:/Sandbox/failure_factory/akashic_v2/` was only ever read (no write call targets it,
her old `.git` was never opened, she was not started). No bytecode caches were written (`python -B`,
`PYTHONDONTWRITEBYTECODE=1`).

This file records what the repo contains, what was excluded and why, the credentials that were held back, what the
skeptic found and how each item was fixed, and the scan results on the final index.

## 1. What the repo contains

| | |
|---|---|
| `code/` (her code, same relative paths) | **1,385 files, 31,377,090 B (29.9 MB), 748,385 lines** |
| whole index (code/ + this repo's own files) | 1,410 files, ~32.1 MB (`.git` about 14 MB) |
| by extension (code/) | py 1,138 . md 89 . rs 45 . bat 18 . ps1 14 . png 14 . json 13 . lua 12 . toml 8 . go 6 . lock 4 . cmd 4 . gitignore 3 . txt 2 . sql 2 . html 2 . one each: vbs sum sh mod js ico icns h example |
| by top dir (code/) | fairies 775 . root-level files 125 . infrastructure 54 . tools 42 . tests 40 . postal_core 39 . scripts 36 . dashboard 33 . somatic_bevy 30 . docs 25 . P00_Autonomic 24 . P30_Cognition 18 . rwkv_inference 17 . tracer_pool 16 . .satellite 16 . fairy_template 14 . directory 12 . P10_Memory 11 . others < 10 |
| binaries | 16 files, all default Tauri icons (png / ico / icns) |
| largest | `fairies/P30_Cognition/cognition/working_memory_hub_fairy.py` 665 KB . `fairies/P50_Persona/Waking Minds/Sourpatches/sourpatches_fairy.py` 644 KB . `fairies/P30_Cognition/AssociationCortexFairy/fairy.py` 539 KB . `server.py` 503 KB . Organ Template 313 KB (both locations) |

Repo-own files: `sync_code.py` (the mirror), `.gitignore` (second-layer denylist), `README.md`, `hooks/pre-commit` +
`hooks/precommit_check.py`, `_survey/` (inventory, the two masked hunt reports, `rescan_a.py`, `rescan_b.py`,
`rescan_skeptic.py`, `gitindex.py`, `sync_report.md`, this file).

## 2. What was excluded and why

| class | what | why |
|---|---|---|
| DATA (~111 k files, ~64 GB) | `state/` 22.1 GB, RWKV weights 28.9 GB, `tools/extracted/` 9.7 GB media frames, `P10_Memory/Akashic_triple_helix_memory_storage/` 1.6 GB (holds the junction), `SRM_Intake/`, `diaries/`, `dream_states/`, `directives/`, `.cognitive/`, `akashic_records/`, `fairies/boot_logs/`, `Claude_Office/` (own repo), learned/runtime `.json` (voice cards, newborn state, interest state, birth profile), `.pkl`, `.jsonl`, `.satellite/*.json` + `.satellite/tasks/` | her memory, logs, chat, notes, media, models -- not code |
| generated snapshots (new this pass) | `dashboard/ui/behavior_tree.json`, `dashboard/ui/behavior_tree.mermaid` (drive/trait snapshot stamped 2026-02-09; the live one is served by `http_bridge.py`) | generated output beside code |
| machine-local config (new this pass) | `.claude/settings.local.json` (permission allowlist + hooks to this machine's `Claude_Office\hooks\*.bat`); rule `*.local.{json,toml,yaml,yml,ini,cfg}` | one machine's settings |
| BUILD (~32 k files, 22.3 GB) | `target/`, `__pycache__/`, `dist/`, `.pytest_cache`, `dashboard/src-tauri/gen/`, loose `.dll/.pyd/.pdb` | rebuild from source |
| THIRD-PARTY (~30 k files, 5.1 GB) | `.venv/`, `research_repos/` (llama.cpp, ollama, RWKV-LM, ...), `NVIDIA Corporation/` | not hers |
| COPIES (~2.6 k files, 2.6 GB) | `sandbox/`, `backups/`, `*_DEPRECATED`, 309 backup-suffixed files, the runaway `fairies/sandbox/...` chain (never walked) | duplicates |
| GIT | her root `.git` (never opened) and `dashboard/.git` (dashboard mirrored as a plain subdir) | fresh history by requirement |
| unsafe names | 12 `nul` files, `C<U+F03A>...` path-join fossils, root redirect accidents (`0`, `10`, `OOM`, `stateboot_*.log`) | not checkout-able on Windows |
| OPTIONAL (off) | 27 `state/*.py\|ps1`, 5 `state/nous_workspace/*.py`, 12 avatar `.jpg` | `--with-optional` if wanted |

Ace's call, **included and flagged**: `fairies/P50_Persona/avatar/assets/sourpatches/calibration.json` (avatar
anchors/palette the code loads at `SomaticAvatarFairy/fairy.py:217`; also holds a `personality_notes` block with one
line about the relationship with Ace, and `lore`). `docs/PERSONAL_AI_API_EXPLORATION.md:98-138` quotes Personal.AI
account ids (numeric workspace/identity/domain ids) from API responses -- identifiers, not credentials.

## 3. HELD_BACK -- Ace decides / rotates (first 4 characters only)

| file:line | kind | first 4 | action |
|---|---|---|---|
| `fairies/P50_Persona/identity/personal_ai_secrets.json:7` | Anthropic API key, 108 chars, under `anthropic_api_key` | `sk-a` | **ROTATE.** Then re-create the file locally from `identity/__init__.py:57-67` or use `ANTHROPIC_API_KEY` (every consumer prefers the env var) |
| `fairies/P50_Persona/identity/personal_ai_secrets.json:2` | Personal.AI API key, 32 chars, under `api_key` | `-2oO` | **ROTATE.** Same file; env var `PERSONAL_AI_API_KEY` |
| `.satellite/tasks/pending/sourpatches_setup.json:20,26` | password given inline to the mysql client inside a docker command (AzerothCore default, 8 chars) | `pass` | LOW; the whole `.satellite/tasks/` queue is excluded anyway |

Both files are skipped whole by `sync_code.py` (`HELD_BACK`), and the hook refuses their paths. The two live key values
occur in exactly one file tree-wide (skeptic, 2,288 files read) and in **no** object of this repo (section 5).

## 4. The skeptic's findings and what was done

| # | sev | finding | fix (all in `F:/Sandbox/akashic-v2-repo/`) | verified by |
|---|---|---|---|---|
| 1 | MED | delete pass used `os.walk`, which follows a junction out of the mirror and deletes there; copy side trusted the destination blindly | `guard_repo()` sweeps `code/`, `_survey/`, `hooks/` with scandir before any write and **refuses the run (exit 3)** on any reparse point or source/mirror overlap; delete pass works only from that listing; `check_dest_file()` requires plain file, `st_nlink == 1`, `realpath` inside the mirror on every overwrite and every delete | regression A1-A5, E1-E4, F1 (scratch, the skeptic's own junction layout) |
| 2 | MED | `--stage` force-added past the root `.gitignore` | `stage()` separates root-ignored (`--exclude-from=.gitignore`) from nested-ignored; force-adds only files whose `git check-ignore -v` source is a `code/**/.gitignore`; root-blocked files are printed BLOCKED and exit 1 | regression B1-B3 (skeptic's stagedemo case) |
| 3 | MED | a partial scan still ran the delete pass and staged mass deletions | any read/copy error -> delete pass and staging skipped, exit 1; > 50 deletions refused without `--allow-mass-delete` | regression C1-C4, D1-D2 |
| 4 | LOW-MED | nothing enforced a scan before commit; rescans covered `code/` only; HELD_BACK is path-exact | tracked `hooks/pre-commit` (`core.hooksPath hooks`) runs `hooks/precommit_check.py`: path rules on every staged path (via `sync_code.path_allowed`), Hunt A + Hunt B + skeptic scan over the **staged blobs** (`--index`, via `_survey/gitindex.py`), exact grep of the two key shapes over the whole index | `precommit_check.py --all` OK; hook exercised by the amend itself and by a blocked fake-key commit in a scratch clone |
| 5 | LOW | `dashboard/ui/behavior_tree.json` + `.mermaid` are runtime snapshots | `DENY_FILE` rule + `.gitignore`; removed from the mirror | sync report: 3 deleted |
| 6 | LOW | `calibration.json` has personal notes | kept (code loads it; private repo); flagged in README and here with the one-line way to exclude | -- |
| 7 | LOW | `.claude/settings.local.json` is machine-local | `LOCAL_NAME_RX` rule + `.gitignore`; removed | sync report |
| 8 | LOW | Personal.AI account ids in a doc | kept; flagged (identifiers, not credentials) | -- |
| 9 | INFO | HELD_BACK list correct; README's "email in tauri.conf.json" was a false positive (`128x128@2x.png`) | README privacy note corrected: no personal e-mail in `code/`; the only e-mail shapes are `noreply@anthropic.com` co-author trailers (4 `docs/plans/*.md`) and `128x128@2x.png` | skeptic scan e-mail section |
| 10 | INFO | 3 unreachable blobs | `git reflog expire --expire=now --all && git gc --prune=now` after the amend | `git fsck --unreachable --no-reflogs` |
| 11 | INFO | commit trailer names Fable 5.1 | kept -- that is the model that did the work (harness attribution rule) | -- |
| 12 | INFO | her MCP servers write `state/` while she is down | nothing to do; `state/` is excluded and never read by the sync | -- |

Also done: the skeptic's verbatim pattern scan is now in the repo as `_survey/rescan_skeptic.py` (index-reading, one
triaged doc example keyed by file/line/first4); `rescan_a.py` learned `--index/--index-all/--stdin0` and treats the
hunts' own `xxxx..[len]` masking stubs as placeholders; four pattern *descriptions* in `secrets_A.md` / `secrets_B.md`
(the URL-with-embedded-credentials shape and the inline mysql-password shape) were reworded so a scanner reading the
reports no longer matches the description of a pattern as an instance of it -- no finding in either report changed.
(The first attempt to amend was itself blocked by the hook because this file quoted those two descriptions literally;
that is the hook working as intended, and the wording here is the result.)

## 5. Scan results on the final index (1,409 paths before this file: 1,393 text blobs + 16 binary)

| scan | result |
|---|---|
| Hunt A `rescan_a.py --index-all` | **0 REAL**. 17 pattern rows: 15 placeholder-hinted (`.env.example:25/28/31` `your...`, `tests/personal_ai_benchmark.py:11,897` `your...`, `postal_core/akp_protocol.md:608` truncated `eyJh...`, 9 masked `xxxx..[N]` stubs in `secrets_A.md` tables) + 2 triaged (`akp_protocol.md:182` `optional-bearer-token`; `secrets_A.md:28` type name `torch.Tensor`). Credential-named files: `.env.example` + the survey's own `secrets_*` reports. exit 0 |
| Hunt B `rescan_b.py --index-all` | **0 hard** (23 formats + both exact key shapes + unfiltered context literals); 224 soft rows, all filter-dropped. exit 0 |
| Skeptic `rescan_skeptic.py --index-all` (33 patterns, verbatim) | **0 REAL** hard hits; 1 raw = `akp_protocol.md:608` truncated doc example (triaged). base64 credential blobs 0. INFO: 24 credential-named literal assignments (type names / ids / placeholders), 136 high-entropy literals (paths, identifiers), 14 ip:port pairs (LAN + 8.8.8.8), 3 e-mail shapes (see #9). exit 0 |
| Skeptic's original `scan.py` (scratch, unmodified) | HARD 1 (the same doc example) -- down from 8 at `8ba060b`; the other 7 were pattern descriptions in README / sync_code / sync_report / the two hunt reports, now reworded |
| Skeptic's `known.py` (exact + every 16-char window of both live keys, over all 1,409 index blobs, every git object, the working tree) | **0** hits for either key; hits only for the 8-letter mysql default word and the public `api_base_url` string |
| Skeptic's `lcs.py` (longest substring shared with a key, min 6) | Anthropic key: 7 chars = the public `sk-ant-` prefix (5 blobs). Personal.AI key: none |
| Skeptic's `bare.py` / `embedded.py` | 32 bare high-entropy tokens = paths/identifiers; long hex = Cargo.lock checksums and HF snapshot hashes; no chat-like lines, no timestamp clusters, largest string literal 8.4 KB |
| `hooks/precommit_check.py --all` | path rules 1,409 paths / 0 problems; all three scanners exit 0; exact known-shape grep 0 files. **OK** |
| `git grep --cached -E 'sk-ant-[A-Za-z0-9_-]{20,}\|-2oO[A-Za-z0-9_-]{28}'` | 0 files |
| index integrity | every entry mode 100644 except `hooks/pre-commit` 100755; no gitlinks, no `.gitmodules`, no nested `.git`; one root commit, `main` only, no remote |

## 6. How to keep it this way

```
python -B sync_code.py --dry-run        # preview
python -B sync_code.py --stage          # mirror + git add (refuses on junctions, errors, mass deletes, root-ignored files)
git commit -m "sync: <date>"            # hooks/pre-commit re-runs Hunt A, Hunt B, the skeptic scan and the path rules
```
After a fresh clone: `git config core.hooksPath hooks`. A new credential in a code file: add its path to `HELD_BACK`
in `sync_code.py`, re-sync (the delete pass removes it), rotate it.
