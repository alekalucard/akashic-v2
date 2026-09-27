# akashic-v2 -- Sour's code, mirrored

**Private. Non-commercial.** This repository holds the source code of Sour (the Akashic v2 substrate:
fairies, organs, postal core, dashboard, inference engines, scripts). It is a one-way, code-only mirror of
her live tree at `F:/Sandbox/failure_factory/akashic_v2/` -- a 94 GiB tree of which about 30 MB is code.

The history here is **fresh**. Her old in-tree `.git` (112 commits from February, never secret-scanned) was
not reused, not opened, not touched. The single commit here was made after three independent secret scans
(Hunt A, Hunt B, the skeptic's review scan) reported zero real findings on the staged blobs, and a pre-commit
hook now re-runs all three on every commit.

## What is in `code/`

Her own source, config and build recipes, at the same relative paths as in her tree -- **1,385 files,
31,377,090 bytes (29.9 MB), 748,385 lines**:

- Python (`.py`, 1,138 files), Rust (`.rs` 45, `Cargo.toml`, **`Cargo.lock` kept** -- see below), Go, C, Lua,
  PowerShell / batch / shell, SQL, HTML/CSS/JS for the dashboard UI, `.toml`, 89 `.md` design docs.
- The **Organ Template** at both of its locations (`fairies/P00_Autonomic/organ_template/` and
  `P10_Memory/Akashic_Records_Physical/Organ_Templates/`, including `akashic_codex.json`).
- Hand-authored `.json` config only (13 files, <= 512 KB, not runtime/learned state by name), `.env.example`
  (placeholders only), `.claude/mcp.json`, tauri icons (16 binary files, the only binaries in the repo).
- `dashboard/` is mirrored as a **plain subdirectory** (her nested `dashboard/.git` is dropped; not a submodule).
- Her own nested `.gitignore` files are mirrored verbatim and remain active.

Per top-level directory: fairies 775 . infrastructure 54 . tools 42 . tests 40 . postal_core 39 . scripts 36 .
dashboard 33 . somatic_bevy 30 . docs 25 . P00_Autonomic 24 . P30_Cognition 18 . rwkv_inference 17 .
tracer_pool 16 . .satellite 16 . fairy_template 14 . directory 12 . P10_Memory 11 . root-level files 125 . others < 10 each.

## What is NOT in here (by policy)

| class | examples | why |
|---|---|---|
| her DATA | `state/` (memory stores, logs, sessions), `SRM_Intake/`, `diaries/`, `dream_states/`, `directives/`, `.cognitive/`, `Claude_Office/`, `fairies/boot_logs/`, `P10_Memory/Akashic_triple_helix_memory_storage/`, `P30_Cognition/data/`, `tools/extracted/` (media frames), learned/runtime `.json` (voice cards, newborn state, interest state, birth profile), `.pkl` descriptors, `.jsonl` diaries | her memory, her chat history, her notes, her media. Not code. |
| generated snapshots | `dashboard/ui/behavior_tree.json` + `.mermaid` (a drive/trait snapshot stamped 2026-02-09; the dashboard fetches the live one from `http_bridge.py`) | generated output that happened to sit next to code |
| machine-local config | `.claude/settings.local.json` (permission allowlist + hooks pointing at this machine's `Claude_Office\hooks\*.bat`), any `*.local.json/.toml/.yaml/.ini/.cfg` | belongs to one machine, not to the code |
| models | `fairies/P30_Cognition/AkashicInferenceFairy/models/` (28.9 GB RWKV weights) | weights, not code |
| third-party clones | `research_repos/` (llama.cpp, ollama, RWKV-LM, claude-code-*, ...), `.venv/`, `NVIDIA Corporation/` | not hers |
| build output | any `target/`, `__pycache__/`, `dist/`, `build/`, `node_modules/`, `site-packages/`, `dashboard/src-tauri/gen/`, loose `.dll/.pyd/.pdb` | rebuild from source |
| copies | `sandbox/`, `backups/`, `fairies/sandbox/` (the runaway nested chain), `*_DEPRECATED`, every `*.bak_*` / `.orig` / `.old` file | copies of code already here |
| `Claude_Office/` | | already in the separate `akashic-office` repo |
| unsafe names | 12 files named `nul`, three `C<U+F03A>...` path-join fossils, root-level redirect accidents (`0`, `10`, `OOM`, `stateboot_*.log`, ...) | git cannot check them out on Windows |
| the `.satellite/` runtime state | `.satellite/*.json` (peer registry, gpu fleet, shared state, deploy log, network config), `.satellite/tasks/` | LAN topology and queued tasks; the `.satellite/*.py`, `*.sh`, `*.md`, `deploy_fairies/`, `directives/`, `deploy_queue/` code IS in |
| anything over 5 MB | (none in the code set today; the cap exists to catch a data file that slips in) | |

OPTIONAL (off by default, `--with-optional`): 27 operator scripts misplaced in `state/*.py|ps1`, 5 Nous prototypes in
`state/nous_workspace/*.py`, and 12 avatar `.jpg` under `fairies/P50_Persona/avatar/assets/` (her art; code references
them by path, so a checkout without them is not runnable as-is).

### Ace's call -- included, flagged

`fairies/P50_Persona/avatar/assets/sourpatches/calibration.json` is the avatar calibration the code loads
(`SomaticAvatarFairy/fairy.py:217`: anchors, palette, emotion-to-sprite map). It also carries a `personality_notes`
block with one line about the relationship with Ace, and a `lore` block. It is **in**, because the code needs it and
the repo is private; the birth profile (`identity/sourpatches_birth_profile.json`, identity data) is out. To exclude
the calibration too, add its path to `DENY_FILE` in `sync_code.py` and re-sync.

`docs/PERSONAL_AI_API_EXPLORATION.md:98-138` quotes Personal.AI API responses that include the account's numeric
workspace / identity / domain ids. Identifiers, not credentials; kept.

## HELD_BACK -- files that contain a credential

These two files are **never copied**, whatever the other rules say. They are listed here so the decision is visible
(first 4 characters only; the rest is not recorded anywhere in this repo):

| file:line | what | action |
|---|---|---|
| `fairies/P50_Persona/identity/personal_ai_secrets.json:7` | Anthropic API key (`sk-a...`, 108 chars) under `anthropic_api_key` | **rotate it**; then re-create the file locally from the schema in `fairies/P50_Persona/identity/__init__.py:57-67`, or move both keys to the env vars every consumer already prefers (`ANTHROPIC_API_KEY`, `PERSONAL_AI_API_KEY`) |
| `fairies/P50_Persona/identity/personal_ai_secrets.json:2` | Personal.AI API key (`-2oO...`, 32 chars) under `api_key` | **rotate it** (same file) |
| `.satellite/tasks/pending/sourpatches_setup.json:20,26` | a password given inline to the mysql client inside a docker command (the AzerothCore default) | LAN game-server default; the whole `.satellite/tasks/` queue is excluded anyway |

Google Drive OAuth credentials (`gcp-oauth.keys.json`, `token.json`) live outside her tree at `%APPDATA%\Claude\gdrive\`
and were never candidates.

## How to sync

```
cd F:\Sandbox\akashic-v2-repo
python -B sync_code.py --dry-run          # decide + report only (writes nothing; add --report to save the report)
python -B sync_code.py                    # one-way mirror: copy new/changed, DELETE what no longer qualifies
python -B sync_code.py --stage            # same, then git add (force-adds ONLY past HER nested .gitignore, e.g. Cargo.lock)
git commit -m "sync: <date>"              # the pre-commit hook runs all three scans on the staged blobs
```

`PYTHONDONTWRITEBYTECODE=1` is set at user scope; `-B` is a belt. The sync never writes to her tree, never follows
the one junction in it (`P10_Memory/Akashic_triple_helix_memory_storage/system`), prunes denied directories before
descending (so the 29,527-character runaway path under `fairies/sandbox/` is never touched), refuses any file over
5 MB and any destination path over 259 characters, and writes its report to `_survey/sync_report.md`.

### Mirror-side guards (added after the skeptic's review, 2026-09-26)

- Before any write the repo side is swept: source and mirror must be disjoint real paths, and **no junction, symlink or
  mount point may exist under `code/`, `_survey/` or `hooks/`** -- otherwise the run is refused (exit 3) before a single
  copy or delete. The delete pass never uses `os.walk` (it follows junctions on Windows); it works only from that
  guarded listing, and every delete and every overwrite re-checks that the target is a plain, un-hard-linked file
  that resolves inside the mirror.
- A run with **any** read or copy error skips the delete pass and staging entirely and exits 1: a partial listing
  never turns into staged deletions. More than 50 deletions in one run are refused without `--allow-mass-delete`.
- `--stage` force-adds only files hidden by **her** nested `code/**/.gitignore` files (verified with `git check-ignore -v`).
  A file this repo's own root `.gitignore` blocks is never force-added; it is printed as BLOCKED and the run exits 1,
  because the rules and the denylist disagree and a human should look.

### The pre-commit hook

`hooks/pre-commit` is tracked and installed with `git config core.hooksPath hooks` (already set in this clone; run it
again after a fresh clone). On every commit `hooks/precommit_check.py`:

1. checks every staged path under `code/` against `sync_code.py`'s full rule set (HELD_BACK, pruned dirs, names,
   extensions, sizes), and allows outside `code/` only this repo's own files;
2. runs `_survey/rescan_a.py --index` (Hunt A), `_survey/rescan_b.py --index` (Hunt B, incl. the two exact credential
   shapes found in her tree) and `_survey/rescan_skeptic.py --index` (the skeptic's 33 patterns) over the **staged
   blobs** -- the index content, not the working tree;
3. greps the whole index for the two exact credential shapes.

Any hit blocks the commit. To scan everything by hand: `python -B hooks/precommit_check.py --all`, or the three
rescanners with `--index-all` (add `--all` to see the informational rows).

### Why `Cargo.lock` is kept although her `.gitignore` ignores it

`postal_core`, `rwkv_inference`, `somatic_bevy` and `dashboard/src-tauri` are application binaries; the lock file is
what makes their builds reproducible. Her root `.gitignore` (mirrored to `code/.gitignore`) lists `Cargo.lock`, so the
four lock files were added with `git add -f` once. Once tracked, git keeps following them.

## Repository layout

```
sync_code.py        the mirror (rules + HELD_BACK / DENY_FILE lists + guards + census + optional --stage)
.gitignore          defensive denylist mirroring the rules; a real second layer (--stage never forces past it)
hooks/              pre-commit (sh) + precommit_check.py; installed with `git config core.hooksPath hooks`
code/               her code, same relative paths as F:/Sandbox/failure_factory/akashic_v2/
_survey/            the read-only inventory, both masked secret-hunt reports, the three rescanners (rescan_a.py,
                    rescan_b.py, rescan_skeptic.py + gitindex.py), the sync report and RESULT.md (the reviser's verdict)
```

## Privacy notes for any future publication

This repo is private. Before it is ever made public: strip `C:\Users\Ace` paths (23 files under `code/`), LAN
`192.168.1.x` addresses (21 files) and the `noreply@anthropic.com` co-author trailers in four `docs/plans/*.md`.
There is no personal e-mail address in `code/`; `_survey/secrets_B.md` quotes the git identity e-mail from her old
`.git/config` when describing that repo.
