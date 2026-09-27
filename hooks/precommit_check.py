"""hooks/precommit_check.py -- nothing reaches a commit of this repo unscanned.
Run by hooks/pre-commit (installed with `git config core.hooksPath hooks`). Read-only. Exit 1 blocks the commit.
Never prints more than the first 4 characters of any value.

    1. PATH RULES  every staged path under code/ must pass sync_code.py's full rule set (HELD_BACK, DENY_FILE,
                   pruned dirs, name/extension/size rules) -- so a key pasted into a NEW file at a denied path,
                   or any held-back file, cannot be committed even by hand. Paths outside code/ must be one of
                   this repo's own files (.gitignore, README.md, sync_code.py, hooks/*, _survey/* text files).
    2. CONTENT     rescan_a --index (Hunt A), rescan_b --index (Hunt B, incl. the two exact credential shapes
                   found in her tree) and rescan_skeptic --index (the skeptic's 33 patterns) over the STAGED
                   BLOBS -- the index content, not the working tree.
    3. WHOLE INDEX `git grep --cached` for the two exact credential shapes over every tracked blob: must be 0.

    python -B hooks/precommit_check.py [--all]      (--all = scan the whole index, not just what is staged)
"""
import os
import re
import subprocess
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "_survey"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sync_code                                   # the rules themselves (import has no side effects)
from gitindex import staged_paths, index_entries

REPO_OWN_FILES = {".gitignore", "README.md", "sync_code.py"}
REPO_OWN_DIR_RX = re.compile(r"^(hooks|_survey)/[A-Za-z0-9_.\-]+\.(py|md|tsv|txt|json)$|^hooks/pre-commit$")
KNOWN_SHAPES = r"sk-ant-[A-Za-z0-9_-]{20,}|-2oO[A-Za-z0-9_-]{28}"


def git(*args, check=True, binary=False):
    r = subprocess.run(["git", "-C", REPO, *args], capture_output=True, check=check,
                       **({} if binary else {"text": True, "encoding": "utf-8"}))
    return r


def main():
    whole = "--all" in sys.argv
    problems = []
    paths = staged_paths(REPO, all_tracked=whole)
    if not paths:
        print("[pre-commit] nothing staged (ACMR) -- path rules skipped; content scans run on the index anyway")
    ents = index_entries(REPO)
    opts = types.SimpleNamespace(dry_run=True, with_optional=True, no_census=True, report=False, stage=False,
                                 allow_mass_delete=False)

    # 1. path rules ------------------------------------------------------------------------------------------
    for p in paths:
        mode, sha = ents.get(p, (None, None))
        if mode is None:
            problems.append(f"PATH  {p}: staged but not found as a stage-0 index entry")
            continue
        if not mode.startswith("100"):
            problems.append(f"PATH  {p}: mode {mode} is not a plain file (gitlink / symlink) -- refused")
            continue
        size = int(git("cat-file", "-s", sha).stdout.strip() or 0)
        if p.startswith("code/"):
            rel = p[len("code/"):]
            ok, reason = sync_code.path_allowed(rel, size, opts)
            if not ok:
                problems.append(f"PATH  {p}: {reason}")
        elif p in REPO_OWN_FILES or REPO_OWN_DIR_RX.match(p):
            pass
        else:
            problems.append(f"PATH  {p}: not under code/ and not one of this repo's own files")
    print(f"[pre-commit] path rules: {len(paths)} staged path(s) checked, {sum(1 for x in problems if x.startswith('PATH'))} problem(s)")

    # 2. content scans over the staged blobs -----------------------------------------------------------------
    mode_flag = "--index-all" if whole else "--index"
    for script in ("rescan_a.py", "rescan_b.py", "rescan_skeptic.py"):
        r = subprocess.run([sys.executable, "-B", os.path.join(REPO, "_survey", script), mode_flag],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        summary = [l for l in r.stdout.splitlines() if l.startswith("[")]
        for l in summary:
            print("[pre-commit] " + l)
        if r.returncode != 0:
            problems.append(f"SCAN  {script} exit {r.returncode}")
            detail = [l for l in r.stdout.splitlines() if not l.startswith("[")]
            for l in detail[:40]:
                print("    " + l)
            if r.stderr.strip():
                print("    stderr: " + r.stderr.strip()[-800:])

    # 3. the two exact shapes over the whole index ------------------------------------------------------------
    r = git("grep", "--cached", "-I", "-l", "-E", KNOWN_SHAPES, check=False)
    hits = [l for l in r.stdout.splitlines() if l]
    print(f"[pre-commit] exact known-shape grep over the whole index: {len(hits)} file(s)")
    for h in hits:
        problems.append(f"SHAPE {h}: carries one of the two credential shapes found in her tree")

    if problems:
        print(f"[pre-commit] BLOCKED -- {len(problems)} problem(s):")
        for x in problems:
            print("   " + x)
        return 1
    print("[pre-commit] OK -- path rules, Hunt A, Hunt B, skeptic scan and the exact-shape grep all clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
