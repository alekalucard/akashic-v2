#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_code.py -- one-way CODE-ONLY mirror of Sour's tree into this repo.

    source  F:/Sandbox/failure_factory/akashic_v2/      (READ-ONLY: never written, its .git never opened)
    target  F:/Sandbox/akashic-v2-repo/code/            (this repo's working tree)

    python -B sync_code.py [--dry-run] [--with-optional] [--no-census] [--stage] [--allow-mass-delete]

Rules (inventory.md section 8 + both secret hunts), evaluated per file in this order:
    HELD_BACK (explicit paths both hunts flagged as carrying a secret -> skipped whole, listed)
    -> DENY_FILE (explicit paths: generated snapshots) and machine-local config (*.local.json)
    -> hard denylist (top dirs, path prefixes, dir components, backup/secret/reserved/unsafe names,
       root junk, data/media/model/compiled extensions)
    -> directory allowlist (31 top-level entries + root files)
    -> extension allowlist (json <= 512 KB + name guard, txt <= 256 KB + name guard,
       png/ico/icns only under icons/ or assets/, .env.example, a few extensionless names)
    -> size cap 5 MB
    -> destination path length (Windows MAX_PATH; nothing may exceed 259 chars)
A file is copied only if it passes everything. Denied directories are PRUNED before descent (this is
what keeps the runaway fairies/sandbox/... chain and the 22 GB state/ store from ever being touched).
Reparse points (junctions / symlinks) are never followed, not even for the census.
Files in the mirror that no longer qualify at the source are DELETED (one-way mirror).

Mirror-side safety (skeptic review 2026-09-26, problems 1-3):
    * before ANY write the repo side is swept: source and mirror must be disjoint real paths, and no reparse
      point (junction / symlink / mount point) may exist anywhere under code/, _survey/ or hooks/. If one does,
      the run is REFUSED before copying or deleting a single file.
    * every copy checks that the destination directory resolves inside the mirror and that an existing
      destination is a plain, un-hard-linked file (st_nlink == 1); every delete re-checks the same on the file.
    * the delete pass never uses os.walk (which follows junctions); it deletes only from the guarded listing.
    * a run with ANY read/copy error skips the delete pass and staging entirely and exits 1 -- a partial
      listing must never turn into staged deletions.
    * more than MASS_DELETE_LIMIT deletions in one run are refused unless --allow-mass-delete is given.
    * --stage force-adds ONLY files hidden by HER nested .gitignore files under code/ (e.g. Cargo.lock). Files
      this repo's own root .gitignore blocks are never force-added; they are reported and the run exits 1.

Nothing here prints or stores more than the first 4 characters of any secret value.
"""
import os
import re
import sys
import stat
import time
import shutil
import argparse
import subprocess

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = r"F:\Sandbox\failure_factory\akashic_v2"
REPO = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(REPO, "code")
REPORT = os.path.join(REPO, "_survey", "sync_report.md")
MANIFEST = os.path.join(REPO, "_survey", "mirror_manifest.tsv")

SIZE_CAP = 5 * 1024 * 1024
JSON_CAP = 512 * 1024
TXT_CAP = 256 * 1024
MAX_DEST_PATH = 259          # Windows MAX_PATH minus NUL; git for Windows checkout limit without core.longpaths
MAX_DEPTH = 40               # belt: no real file in her tree is deeper than 14
CENSUS_MAX_DEPTH = 48
MASS_DELETE_LIMIT = 50       # more deletions than this in one run need --allow-mass-delete
GUARDED_DIRS = ("code", "_survey", "hooks")   # repo dirs swept for reparse points before any write
FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

# --------------------------------------------------------------------------------------- HELD_BACK
# Files BOTH secret hunts flagged as carrying a live credential in their CONTENT. Skipped whole, always,
# regardless of any other rule. (relpath -> [(line, description)]).  First 4 chars only, ever.
HELD_BACK = {
    "fairies/P50_Persona/identity/personal_ai_secrets.json": [
        (7, "Anthropic API key under `anthropic_api_key` (first4 `sk-a`, len 108) -- Hunt A #1 / Hunt B #1, CRITICAL"),
        (2, "Personal.AI API key under `api_key` (first4 `-2oO`, len 32) -- Hunt A #2 / Hunt B #2, HIGH"),
    ],
    ".satellite/tasks/pending/sourpatches_setup.json": [
        (20, "password given inline to the mysql client (its password option) inside a docker command (AzerothCore default) -- Hunt B #3, LOW"),
        (26, "same password, second occurrence -- Hunt B #3, LOW"),
    ],
}
# Explicit single files denied for what they ARE (generated output), whatever their extension says.
DENY_FILE = {
    "dashboard/ui/behavior_tree.json": "DATA (generated runtime snapshot of drives/traits, timestamp 2026-02-09; "
                                       "the dashboard fetches the live one from http_bridge /behavior_tree)",
    "dashboard/ui/behavior_tree.mermaid": "DATA (generated runtime snapshot, 'Generated: 2026-02-09 15:10:26')",
}
# NOTE 2026-09-29: fairies/P50_Persona/avatar/assets/sourpatches/calibration.json (personality notes + lore) was
# briefly denied, then Ace chose to INCLUDE it: the repo is private and serves cloud sessions, and
# SomaticAvatarFairy/fairy.py:217 loads it.
LOCAL_NAME_RX = re.compile(r"\.local\.(json|toml|ya?ml|ini|cfg)$", re.I)   # .claude/settings.local.json etc.

# ---------------------------------------------------------------------------------- directory rules
ALLOW_TOP = {
    ".claude", ".satellite", "P00_Autonomic", "P10_Memory", "P20_Somatic", "P30_Cognition", "P60_Executive",
    "consciousness", "core", "dashboard", "directory", "docs", "fairies", "fairy_template", "foundations",
    "gui", "hardware", "infrastructure", "integration", "memory", "postal_core", "rwkv_inference", "scripts",
    "somatic_bevy", "spellchain", "tests", "tools", "tracer_pool", "utils", "waking_minds", "wow_scripts",
}
# top-level entries that are denied, with the class they belong to (for the census report)
DENY_TOP = {
    ".git": "GIT (old root repo, never opened)", ".venv": "THIRD-PARTY", "research_repos": "THIRD-PARTY",
    "NVIDIA Corporation": "THIRD-PARTY", "Claude_Office": "DATA (separate akashic-office repo)",
    "state": "DATA (memory stores, logs, runtime state)", "diaries": "DATA", "dream_states": "DATA",
    "SRM_Intake": "DATA", "directives": "DATA", ".cognitive": "DATA", "akashic_records": "DATA",
    "sandbox": "COPIES", "backups": "COPIES", "_old_unconscious_mind_DEPRECATED": "COPIES",
    ".pytest_cache": "BUILD", "session_forensics": "EMPTY", "scrape_checkpoints": "EMPTY", "config": "EMPTY",
    "functions": "EMPTY", "nous_workshop": "EMPTY", "postal": "EMPTY", "unconscious_mind": "EMPTY",
    "C\uf03atemp": "UNSAFE NAME (path-join fossil)",
}
DENY_PREFIX = {   # relpath prefixes (with trailing /), class
    "fairies/sandbox/": "COPIES (runaway nested chain, never walked)",
    "fairies/boot_logs/": "DATA", "fairies/state/": "DATA", "fairies/diaries/": "DATA",
    "fairies/akashic_records/": "DATA", "fairies/.cognitive/": "DATA", "fairies/.satellite/": "DATA",
    "fairies/SRM_Intake/": "DATA", "fairies/Claude_Office/": "DATA", "fairies/NVIDIA Corporation/": "THIRD-PARTY",
    "fairies/P30_Cognition/AkashicInferenceFairy/models/": "DATA (RWKV model weights)",
    "fairies/P30_Cognition/AkashicInferenceFairy/_old_rwkv_DEPRECATED/": "COPIES",
    "fairies/P10_Memory/Akashic_triple_helix_memory_storage/": "DATA (memory store)",
    "P10_Memory/Akashic_triple_helix_memory_storage/": "DATA (memory store; contains the junction)",
    "P30_Cognition/data/": "DATA",
    "tools/extracted/": "DATA (media frames)",
    "memory/.scrape_checkpoints/": "DATA",
    "dashboard/.git/": "GIT (her nested repo; mirrored as plain subdir)",
    "dashboard/src-tauri/gen/": "BUILD (tauri generated)",
    ".satellite/tasks/": "DATA (runtime task queue; Hunt B)",
    "state/_probe_copy/": "COPIES", "state/_restore_probe/": "COPIES", "state/_rust_test/": "COPIES",
    "state/_sandbox_council/": "COPIES", "state/akashic/backups/": "COPIES", "state/nous_workspace/_shadow_stage/": "COPIES",
}
DENY_PREFIX_RX = re.compile(r"^state/_preserved_[^/]*/")
DENY_COMPONENT = {
    "target": "BUILD", "__pycache__": "BUILD", "dist": "BUILD", "build": "BUILD", "node_modules": "THIRD-PARTY",
    "site-packages": "THIRD-PARTY", ".git": "GIT", "_shadow_stage": "COPIES", ".pytest_cache": "BUILD",
    ".mypy_cache": "BUILD", ".ruff_cache": "BUILD",
}
# OPTIONAL set (inventory 8b): copied only with --with-optional
OPTIONAL_RX = [
    (re.compile(r"^state/[^/]+\.(py|ps1)$", re.I), "misplaced state/*.py|ps1 operator script"),
    (re.compile(r"^state/nous_workspace/[^/]+\.py$", re.I), "nous_workspace prototype"),
    (re.compile(r"^fairies/P50_Persona/avatar/assets/.+\.jpe?g$", re.I), "avatar jpg asset"),
]

# --------------------------------------------------------------------------------------- name rules
BACKUP_RX = re.compile(
    r"\.bak(_|\.|\d|$)|\.backup(_|\.|$)|\.orig$|\.old$|~$|_SAVED\.|\.deprecated$|\.disabled$|\.nuked$"
    r"|\.corrupted\d*$|\.crash_backup$|\.stale_|\.inuse_|\.nul_\d+$|_DEPRECATED|_MERGED_for74"
    r"|\.pre[a-z]+_\d{8}|\.run\d+$|\.over_pruned$|\.pre_merge_", re.I)
SECRET_NAME_RX = re.compile(
    r"^\.env(?!\.example$)(\..*)?$|secret|credential|api_?key|\.pem$|\.pfx$|\.p12$|\.ppk$|\.kdbx$|\.p8$|\.jks$|\.keystore$"
    r"|^id_rsa|^id_ed25519|^id_ecdsa|^id_dsa|^\.?_?netrc$|\.npmrc$|\.pypirc$|\.git-credentials$|known_hosts$|authorized_keys$"
    r"|^token.*\.json$|\.token$|access_token|refresh_token|^gcp-oauth.*\.json$|^service_account.*\.json$|\.htpasswd$", re.I)
SECRET_NAME_ALLOW_RX = re.compile(r"^TokenBucket", re.I)   # a fairy's name, not a credential file
RESERVED_RX = re.compile(r"^(nul|con|prn|aux|com[1-9]|lpt[1-9])(\..*)?$", re.I)
UNSAFE_RX = re.compile(r'[<>:"|?*\x00-\x1f\uf000-\uf0ff]')
ROOT_JUNK_RX = re.compile(
    r"^(\d+(\.\d+)?|nul|OOM|per-region|test_output\.txt|boot_test_out5\.txt|boot_test_output\.txt|stateboot_.*|stateserver_.*"
    r"|FSandbox.*|Ctemp.*|.*status\.json|temp_stat\.json|test_capture\.png|guild_test_err\.log|clean_boot.*|boot_.*\.(log|txt)"
    r"|boot_test_err.*|SESSION_2026_01_14\.md)$", re.I)

DENY_EXT = set("""
log jsonl pkl pickle pt pth npz npy gguf portal manifold csr keys ring embeddings state index bloat dat db sqlite sqlite3
wav mp3 ogg flac aac m4a mp4 mkv avi webm srt jpg jpeg jfif gif webp bmp tiff psd
pdf docx doc xlsx pptx zip 7z tar gz rar tmp dict directive model bpe arrow parquet h5 hdf5 onnx safetensors ckpt cache mat idx pack rev sample nfo
pyc pyo pyd dll so exe lib pdb o obj rlib rmeta d whl egg timestamp ilk exp a bin
""".split())
ALLOW_EXT = set("""
py pyi pyx rs toml md bat cmd ps1 psm1 psd1 vbs sh lua go mod sum c h cpp hpp cu cuh sql html htm css js mjs ts tsx
yaml yml ini cfg conf lock gitignore gitattributes editorconfig mermaid mmd svg wgsl glsl ron pest proto patch diff
""".split())
IMAGE_EXT = {"png", "ico", "icns"}
IMAGE_DIR_RX = re.compile(r"/(icons|assets)/", re.I)
JSON_GUARD_RX = re.compile(
    r"(status|stat\b|state|report|log|history|cache|snapshot|checkpoint|seed|session|telemetry|registry|profile|stats|metrics"
    r"|memory|record|result|deaths|audit|census|backup|habits|learn|skills|goals|satisfaction|awareness|world|circulation"
    r"|deploy|peer|fleet|shared|scan_results|_bp74|promoter|heartbeat|diagnostic|evolution|graph|index|manifest|outcome"
    r"|timing|weights|embedding|vector|knowledge|tracker|inbox|queue|ledger|cards?\b|dream|reflection|thought|chat"
    r"|conversation|transcript|crash|error)", re.I)
TXT_GUARD_RX = re.compile(r"(log|_err|stderr|stdout|_out\b|output|trace|dump|census|report|@Automation)", re.I)
NOEXT_ALLOW = {"Makefile", "Dockerfile", "LICENSE", "CHANGELOG", "NOTICE", "AUTHORS", "CONTRIBUTING", "Procfile", "justfile"}


# ------------------------------------------------------------------------------------------ helpers
def lp(path):
    """Long-path form for Windows so a deep or long source path can never raise 'Filename too long'."""
    path = os.path.normpath(path)
    if os.name == "nt" and not path.startswith("\\\\?\\"):
        return "\\\\?\\" + path
    return path


def is_reparse(entry):
    try:
        if entry.is_symlink():
            return True
        st = entry.stat(follow_symlinks=False)
        return bool(getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return True   # cannot stat it -> do not touch it


def ext_of(name):
    root, ext = os.path.splitext(name)
    ext = ext.lstrip(".").lower()
    if not ext and name.startswith("."):
        ext = name[1:].lower()   # ".gitignore" -> "gitignore"
    return ext


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0


class Census:
    """Counts of files/bytes we rejected, by reason. Pruned directories are counted by a separate
    listing pass (names + cached stat only, never follows reparse points, never enters .git)."""
    def __init__(self):
        self.rej = {}          # reason -> [files, bytes]
        self.pruned = {}       # class -> [dirs, files, bytes]
        self.examples = {}     # reason -> up to 5 relpaths

    def reject(self, reason, size, rel):
        r = self.rej.setdefault(reason, [0, 0])
        r[0] += 1
        r[1] += size
        ex = self.examples.setdefault(reason, [])
        if len(ex) < 5:
            ex.append(rel)

    def prune(self, klass, files, size):
        p = self.pruned.setdefault(klass, [0, 0, 0])
        p[0] += 1
        p[1] += files
        p[2] += size


def count_tree(path_lp, depth=0):
    """List-only census of a pruned directory. Never follows reparse points, never enters .git,
    stops at CENSUS_MAX_DEPTH. Returns (files, bytes)."""
    files = size = 0
    if depth > CENSUS_MAX_DEPTH:
        return files, size
    try:
        with os.scandir(path_lp) as it:
            for e in it:
                if is_reparse(e):
                    continue
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name == ".git":
                            continue
                        f, s = count_tree(e.path, depth + 1)
                        files += f
                        size += s
                    else:
                        files += 1
                        size += e.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
    except OSError:
        pass
    return files, size


# --------------------------------------------------------------------------------------- decisions
def dir_decision(rel, name, depth, opts):
    """Return (descend: bool, prune_class or None)."""
    if depth == 0:
        if name in DENY_TOP:
            if name == "state" and opts.with_optional:
                return True, None
            return False, DENY_TOP[name]
        if name not in ALLOW_TOP:
            return False, "NOT ALLOWLISTED (top-level)"
    if rel.startswith("state/"):
        # only the optional set lives here: state/*.py|ps1 and state/nous_workspace/*.py
        if rel != "state/nous_workspace":
            return False, "DATA (state/ subtree; only nous_workspace top level is optional)"
    if rel.startswith("state/nous_workspace/"):
        return False, "DATA (below state/nous_workspace)"
    relslash = rel + "/"
    for pfx, klass in DENY_PREFIX.items():
        if relslash.startswith(pfx):
            return False, klass
    if DENY_PREFIX_RX.match(relslash):
        return False, "COPIES"
    if name in DENY_COMPONENT:
        return False, DENY_COMPONENT[name]
    if BACKUP_RX.search(name):
        return False, "COPIES (backup-suffixed directory)"
    if RESERVED_RX.match(name) or UNSAFE_RX.search(name):
        return False, "UNSAFE NAME"
    if depth >= MAX_DEPTH:
        return False, "DEPTH CAP (runaway path)"
    return True, None


def file_decision(rel, name, size, depth, opts):
    """Return (action, reason). action in {'copy', 'held', 'skip', 'optional-skip'}."""
    if rel in HELD_BACK:
        return "held", "HELD_BACK (secret content flagged by both hunts)"
    if rel in DENY_FILE:
        return "skip", DENY_FILE[rel]
    if LOCAL_NAME_RX.search(name):
        return "skip", "machine-local config (*.local.json: permission allowlist / hooks pointing at this machine)"
    if RESERVED_RX.match(name):
        return "skip", "reserved Windows name"
    if UNSAFE_RX.search(name):
        return "skip", "unsafe characters in name"
    if BACKUP_RX.search(name):
        return "skip", "backup / copy suffix"
    if SECRET_NAME_RX.search(name) and not SECRET_NAME_ALLOW_RX.match(name):
        return "skip", "credential-shaped file name"
    if depth == 0 and ROOT_JUNK_RX.match(name):
        return "skip", "root junk (path-join fossil / log / redirect accident)"
    ext = ext_of(name)
    for rx, label in OPTIONAL_RX:
        if rx.match(rel):
            if opts.with_optional:
                return "copy", "OPTIONAL: " + label
            return "optional-skip", "OPTIONAL (not selected): " + label
    if ext in DENY_EXT:
        return "skip", f"data/media/model/compiled extension (.{ext})"
    top = rel.split("/", 1)[0] if "/" in rel else None
    if top is not None and top not in ALLOW_TOP:
        return "skip", "directory not allowlisted"
    if rel.startswith(".satellite/") and depth == 1 and ext == "json":
        return "skip", ".satellite runtime-state json (LAN topology / peers / deploy log; Hunt B)"
    if ext in ALLOW_EXT:
        pass
    elif ext == "json":
        if size > JSON_CAP:
            return "skip", "json over 512 KB (learned/runtime data)"
        if JSON_GUARD_RX.search(name):
            return "skip", "json name guard (runtime / learned state)"
    elif ext == "txt":
        if size > TXT_CAP:
            return "skip", "txt over 256 KB"
        if TXT_GUARD_RX.search(name):
            return "skip", "txt name guard (log / output / dump)"
    elif ext in IMAGE_EXT:
        if not IMAGE_DIR_RX.search("/" + rel):
            return "skip", "image outside icons/ or assets/"
    elif ext == "example":
        if name != ".env.example":
            return "skip", "extension not allowlisted (.example other than .env.example)"
    elif ext == "":
        if not (name in NOEXT_ALLOW or name.startswith("README")):
            return "skip", "extensionless file not in the allow set"
    else:
        return "skip", f"extension not allowlisted (.{ext})"
    if size > SIZE_CAP:
        return "skip", "OVER 5 MB size cap"
    return "copy", "code"


def path_allowed(rel, size, opts):
    """Full rule check for ONE relpath (used by hooks/precommit_check.py on every staged path under code/):
    every ancestor directory must be descendable and the file itself must decide 'copy'. Returns (ok, reason)."""
    parts = rel.split("/")
    for i in range(len(parts) - 1):
        drel = "/".join(parts[:i + 1])
        descend, klass = dir_decision(drel, parts[i], i, opts)
        if not descend:
            return False, f"directory `{drel}`: {klass}"
    action, reason = file_decision(rel, parts[-1], size, len(parts) - 1, opts)
    if action != "copy":
        return False, reason
    if len(os.path.join(DST, rel.replace("/", os.sep))) > MAX_DEST_PATH:
        return False, "destination path over 259 chars"
    return True, reason


# ------------------------------------------------------------------------------------ mirror guard
class MirrorUnsafe(Exception):
    """Raised BEFORE any write when the mirror side is not a plain directory tree this repo owns."""


def has_reparse_attr(st):
    return bool(getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)


def inside(path_real, root_real):
    root_real = root_real.rstrip(os.sep)
    return path_real == root_real or path_real.startswith(root_real + os.sep)


def list_repo_dir(root):
    """scandir listing of an existing repo directory -> ({abs_file: lstat}, [abs_dirs]). Raises MirrorUnsafe on the
    first reparse point (junction / symlink / mount point) or unreadable entry: the mirror must be a plain tree we
    own, or nothing gets deleted or written. Never uses os.walk (which follows junctions on Windows)."""
    files, dirs = {}, []
    if not os.path.isdir(root):
        return files, dirs
    if has_reparse_attr(os.lstat(root)):
        raise MirrorUnsafe(f"{root} is itself a reparse point")
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError as e:
            raise MirrorUnsafe(f"cannot list {d}: {e}")
        for e in entries:
            if is_reparse(e):
                raise MirrorUnsafe(f"reparse point (junction/symlink) inside the repo: {e.path}")
            try:
                if e.is_dir(follow_symlinks=False):
                    dirs.append(e.path)
                    stack.append(e.path)
                else:
                    files[e.path] = e.stat(follow_symlinks=False)
            except OSError as err:
                raise MirrorUnsafe(f"cannot stat {e.path}: {err}")
    return files, dirs


def guard_repo(src_real, dst_real):
    """Refuse to run unless source and mirror are disjoint real paths, the mirror lives inside this repo, and no
    reparse point exists anywhere under the guarded repo dirs. Returns the pre-write listing of code/."""
    if inside(dst_real, src_real) or inside(src_real, dst_real):
        raise MirrorUnsafe(f"source and mirror overlap: {src_real} <-> {dst_real}")
    repo_real = os.path.realpath(REPO)
    if not inside(dst_real, repo_real):
        raise MirrorUnsafe(f"mirror {dst_real} is not inside the repo {repo_real}")
    if has_reparse_attr(os.lstat(REPO)):
        raise MirrorUnsafe(f"repo root {REPO} is a reparse point")
    listing = {}
    for name in GUARDED_DIRS:
        listing[name] = list_repo_dir(os.path.join(REPO, name))
    return listing["code"]


def check_dest_file(dst, dst_real):
    """An existing destination must be a plain file with one link that resolves inside the mirror."""
    lst = os.lstat(dst)
    if has_reparse_attr(lst):
        raise MirrorUnsafe(f"destination is a reparse point: {dst}")
    if lst.st_nlink > 1:
        raise MirrorUnsafe(f"destination is hard-linked ({lst.st_nlink} links): {dst}")
    if not inside(os.path.realpath(dst), dst_real):
        raise MirrorUnsafe(f"destination resolves outside the mirror: {dst}")
    return lst


# --------------------------------------------------------------------------------------------- sync
def run(opts):
    t0 = time.time()
    src_lp = lp(SRC)
    census = Census()
    kept = {}          # rel -> (size, reason)
    copied = updated = unchanged = 0
    held = []          # (rel, size)
    oversize = []      # (rel, size)
    longpath = []      # (rel, len)
    reparse = []       # rel
    errors = []        # (rel, err)
    optional_skipped = []

    src_real = os.path.realpath(SRC)
    dst_real = os.path.realpath(DST)             # realpath also resolves a not-yet-existing mirror dir
    mirror_files, mirror_dirs = guard_repo(src_real, dst_real)     # raises MirrorUnsafe -> nothing written

    if not opts.dry_run:
        os.makedirs(DST, exist_ok=True)
        if not inside(os.path.realpath(DST), dst_real):
            raise MirrorUnsafe(f"mirror dir changed identity during the run: {DST}")

    stack = [(src_lp, "", 0)]
    while stack:
        dpath, drel, depth = stack.pop()
        try:
            entries = list(os.scandir(dpath))
        except OSError as e:
            errors.append((drel or ".", f"scandir: {e}"))
            continue
        for e in sorted(entries, key=lambda x: x.name):
            rel = f"{drel}/{e.name}" if drel else e.name
            if is_reparse(e):
                reparse.append(rel)
                continue
            try:
                is_dir = e.is_dir(follow_symlinks=False)
            except OSError as err:
                errors.append((rel, str(err)))
                continue
            if is_dir:
                descend, klass = dir_decision(rel, e.name, depth, opts)
                if descend:
                    stack.append((e.path, rel, depth + 1))
                else:
                    if opts.no_census or klass.startswith("GIT") or rel == "fairies/sandbox":
                        census.prune(klass, 0, 0)
                    else:
                        f, s = count_tree(e.path)
                        census.prune(klass, f, s)
                continue
            try:
                st = e.stat(follow_symlinks=False)
            except OSError as err:
                errors.append((rel, str(err)))
                continue
            size = st.st_size
            action, reason = file_decision(rel, e.name, size, depth, opts)
            if action == "held":
                held.append((rel, size))
                continue
            if action == "optional-skip":
                optional_skipped.append(rel)
                census.reject(reason, size, rel)
                continue
            if action == "skip":
                if reason.startswith("OVER 5 MB"):
                    oversize.append((rel, size))
                census.reject(reason, size, rel)
                continue
            # copy path
            dst = os.path.join(DST, rel.replace("/", os.sep))
            if len(dst) > MAX_DEST_PATH:
                longpath.append((rel, len(dst)))
                census.reject("destination path over 259 chars", size, rel)
                continue
            kept[rel] = (size, reason)
            try:
                dst_st = os.stat(dst)
                same = (dst_st.st_size == size and dst_st.st_mtime_ns == st.st_mtime_ns)
            except FileNotFoundError:
                dst_st = None
                same = False
            if same:
                unchanged += 1
                continue
            if not opts.dry_run:
                ddir = os.path.dirname(dst)
                try:
                    os.makedirs(ddir, exist_ok=True)
                    if not inside(os.path.realpath(ddir), dst_real):
                        raise MirrorUnsafe(f"destination dir resolves outside the mirror: {ddir}")
                    if dst_st is not None:
                        check_dest_file(dst, dst_real)
                    shutil.copy2(e.path, dst)
                except MirrorUnsafe as err:
                    errors.append((rel, f"copy REFUSED: {err}"))
                    kept.pop(rel, None)
                    continue
                except OSError as err:
                    errors.append((rel, f"copy: {err}"))
                    kept.pop(rel, None)
                    continue
            if dst_st is None:
                copied += 1
            else:
                updated += 1

    # ---- delete pass: anything in the mirror that is no longer produced by the rules.
    # Works ONLY from the guarded pre-write listing (no os.walk), compares case-insensitively (NTFS), and is
    # skipped whole when this run had any error or would delete more than MASS_DELETE_LIMIT files.
    deleted = []
    delete_note = None
    kept_norm = {os.path.normcase(os.path.join(DST, r.replace("/", os.sep))) for r in kept}
    candidates = sorted(p for p in mirror_files if os.path.normcase(p) not in kept_norm)
    if errors:
        delete_note = (f"delete pass SKIPPED: {len(errors)} read/copy error(s) this run -- a partial listing must "
                       f"not drive deletions ({len(candidates)} candidate(s) left in place)")
    elif len(candidates) > MASS_DELETE_LIMIT and not opts.allow_mass_delete:
        delete_note = (f"delete pass REFUSED: {len(candidates)} files would be deleted (> {MASS_DELETE_LIMIT}); "
                       f"re-run with --allow-mass-delete only if that is intended")
        errors.append(("delete-pass", delete_note))
    else:
        for p in candidates:
            rel = os.path.relpath(p, DST).replace(os.sep, "/")
            deleted.append(rel)
            if opts.dry_run:
                continue
            try:
                check_dest_file(p, dst_real)
                os.remove(p)
            except (OSError, MirrorUnsafe) as err:
                errors.append((rel, f"delete refused: {err}"))
        if not opts.dry_run:
            for d in sorted(mirror_dirs, key=len, reverse=True):      # deepest first
                try:
                    if not has_reparse_attr(os.lstat(d)) and inside(os.path.realpath(d), dst_real) and not os.listdir(d):
                        os.rmdir(d)
                except OSError:
                    pass

    # ---- manifest cross-check (inventory's proposed set)
    manifest_diff = None
    if os.path.isfile(MANIFEST):
        inc, opt = set(), set()
        with open(MANIFEST, encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 3:
                    (inc if parts[2] == "INCLUDE" else opt).add(parts[0])
        expected = inc | (opt if opts.with_optional else set())
        manifest_diff = (sorted(set(kept) - expected), sorted(expected - set(kept)))

    total_bytes = sum(s for s, _ in kept.values())
    largest = sorted(kept.items(), key=lambda kv: -kv[1][0])[:15]
    elapsed = time.time() - t0

    # ---- report
    L = []
    w = L.append
    w(f"# sync_code.py report -- {time.strftime('%Y-%m-%d %H:%M:%S')}  ({'DRY RUN' if opts.dry_run else 'LIVE'})")
    w("")
    w(f"source `{SRC}` -> mirror `{DST}`  .  optional set: {'ON' if opts.with_optional else 'off'}  .  {elapsed:.1f}s")
    w("")
    w("## Result")
    w("")
    w(f"| mirrored files | {len(kept):,} |\n|---|---:|")
    w(f"| total bytes | {total_bytes:,} ({human(total_bytes)}) |")
    w(f"| new | {copied:,} |\n| updated | {updated:,} |\n| unchanged | {unchanged:,} |\n| deleted from mirror | {len(deleted):,} |")
    w(f"| HELD_BACK (secret content) | {len(held)} |\n| over 5 MB cap | {len(oversize)} |\n| destination path too long | {len(longpath)} |")
    w(f"| reparse points skipped | {len(reparse)} |\n| errors | {len(errors)} |")
    w("")
    w(f"mirror guard: source `{src_real}` and mirror `{dst_real}` are disjoint; {len(mirror_files):,} files / "
      f"{len(mirror_dirs):,} dirs listed under code/ before any write; 0 reparse points under {', '.join(GUARDED_DIRS)}.")
    if delete_note:
        w("")
        w(f"**{delete_note}**")
    w("")
    w("## HELD_BACK -- skipped whole; Ace decides (file:line, first 4 chars only)")
    w("")
    # checked directly at the source, so a held-back file inside a PRUNED directory is still reported
    for rel in HELD_BACK:
        try:
            size = os.stat(lp(os.path.join(SRC, rel.replace("/", os.sep)))).st_size
            where = f"present at source, {size} B" + ("" if rel in {r for r, _ in held} else "; inside a pruned directory")
        except OSError:
            where = "NOT present at source this run"
        for ln, desc in HELD_BACK[rel]:
            w(f"- `{rel}:{ln}` -- {desc}  ({where})")
    w("")
    w("## Largest mirrored files")
    w("")
    for rel, (size, _) in largest:
        w(f"- {human(size):>9}  `{rel}`")
    w("")
    if oversize:
        w("## Files over the 5 MB cap (refused)")
        w("")
        for rel, size in oversize:
            w(f"- {human(size)}  `{rel}`")
        w("")
    if longpath:
        w("## Destination paths over 259 chars (refused)")
        w("")
        for rel, n in longpath:
            w(f"- {n} chars  `{rel}`")
        w("")
    if reparse:
        w("## Reparse points (junction/symlink) -- never followed")
        w("")
        for rel in reparse:
            w(f"- `{rel}`")
        w("")
    w("## Excluded: pruned directories (never descended for copying; census is a name listing only)")
    w("")
    w("| class | dirs | files | bytes |\n|---|---:|---:|---:|")
    for klass, (d, f, s) in sorted(census.pruned.items(), key=lambda kv: -kv[1][2]):
        w(f"| {klass} | {d} | {f:,} | {human(s)} |")
    w("")
    w("## Excluded: files seen inside allowed directories and rejected, by reason")
    w("")
    w("| reason | files | bytes | examples |\n|---|---:|---:|---|")
    for reason, (f, s) in sorted(census.rej.items(), key=lambda kv: -kv[1][0]):
        ex = ", ".join(f"`{x}`" for x in census.examples.get(reason, [])[:3])
        w(f"| {reason} | {f:,} | {human(s)} | {ex} |")
    w("")
    if deleted:
        w("## Deleted from mirror (gone or no longer qualifying at source)")
        w("")
        for rel in deleted[:200]:
            w(f"- `{rel}`")
        if len(deleted) > 200:
            w(f"- ... {len(deleted) - 200} more")
        w("")
    if manifest_diff is not None:
        extra, missing = manifest_diff
        w(f"## Cross-check against `_survey/mirror_manifest.tsv` (inventory's proposed set)")
        w("")
        w(f"- in mirror but not in manifest: {len(extra)}")
        for rel in extra[:100]:
            w(f"  - `{rel}`")
        w(f"- in manifest but not in mirror: {len(missing)}")
        for rel in missing[:100]:
            w(f"  - `{rel}`")
        w("")
    if errors:
        w("## Errors")
        w("")
        for rel, err in errors:
            w(f"- `{rel}`: {err}")
        w("")

    text = "\n".join(L) + "\n"
    if not opts.dry_run or opts.report:
        os.makedirs(os.path.dirname(REPORT), exist_ok=True)
        data = text.encode("utf-8")           # build the bytes first, then open for writing
        tmp = REPORT + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, REPORT)
    print(text)
    return kept, held, errors


def stage(kept):
    """git add the mirror + repo files. Her nested .gitignore files under code/ are mirrored verbatim and would hide
    files the rules keep (her root one ignores Cargo.lock), so files hidden by THOSE -- and only those -- are
    force-added, each verified with `git check-ignore -v` to come from a code/**/.gitignore. Anything this repo's own
    root .gitignore blocks is never force-added: it is reported as BLOCKED (the rules and the denylist disagree, so
    a human looks) and the caller exits 1. Returns (staged_count, forced, blocked)."""
    def git(*args, check=True):
        return subprocess.run(["git", "-C", REPO, *args], check=check, capture_output=True, text=True, encoding="utf-8")

    def zlist(out):
        return [p for p in out.split("\0") if p]

    git("add", "-A", "--", "code", ".gitignore", "README.md", "sync_code.py", "_survey", "hooks")
    ignored_any = set(zlist(git("ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--", "code").stdout))
    ignored_root = set(zlist(git("ls-files", "--others", "--ignored", "--exclude-from=.gitignore", "-z", "--", "code").stdout))
    forced, blocked = [], []
    for p in sorted(ignored_any):
        rel = p[len("code/"):] if p.startswith("code/") else p
        if rel not in kept:
            continue                                   # not a file the rules keep: nothing to add
        if p in ignored_root:
            blocked.append((p, "this repo's root .gitignore"))
            continue
        src = git("check-ignore", "-v", "--no-index", "--", p, check=False).stdout.split(":", 1)[0].strip()
        if not src.startswith("code/") or not src.endswith(".gitignore"):
            blocked.append((p, f"ignore source {src!r} is not one of her nested code/**/.gitignore files"))
            continue
        git("add", "-f", "--", p)
        forced.append((p, src))
    n = len(zlist(git("ls-files", "-z", "--", "code").stdout))
    print(f"staged: {n} files under code/ ; force-added past HER nested .gitignore: {len(forced)} ; "
          f"BLOCKED by this repo's root .gitignore: {len(blocked)}")
    for p, src in forced:
        print(f"  forced: {p}   (hidden by {src})")
    for p, why in blocked:
        print(f"  BLOCKED: {p}   ({why}) -- rules kept it, the denylist refuses it; decide, do not force")
    if n != len(kept):
        print(f"WARNING: staged count {n} != mirrored count {len(kept)}")
    return n, forced, blocked


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="decide and report, copy/delete nothing")
    ap.add_argument("--with-optional", action="store_true", help="also mirror the OPTIONAL set (state scripts, avatar jpg)")
    ap.add_argument("--no-census", action="store_true", help="skip the listing census of pruned directories (faster)")
    ap.add_argument("--report", action="store_true", help="write the report file even on --dry-run")
    ap.add_argument("--stage", action="store_true", help="after a clean live sync, git add everything (force-add only past HER nested .gitignore)")
    ap.add_argument("--allow-mass-delete", action="store_true", help=f"permit more than {MASS_DELETE_LIMIT} deletions in one run")
    opts = ap.parse_args()
    if not os.path.isdir(SRC):
        print(f"source missing: {SRC}")
        sys.exit(2)
    try:
        kept, held, errors = run(opts)
    except MirrorUnsafe as e:
        print(f"REFUSED before any write (mirror guard): {e}")
        sys.exit(3)
    if opts.stage and not opts.dry_run:
        if errors:
            print(f"staging SKIPPED: {len(errors)} error(s) this run -- see the report; nothing was git-added")
        else:
            n, forced, blocked = stage(kept)
            if blocked:
                errors.append(("stage", f"{len(blocked)} rule-kept file(s) blocked by the root .gitignore"))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
