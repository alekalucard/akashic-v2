"""gitindex.py -- read blobs straight from the git INDEX (what a commit would actually contain), not the
working tree. Used by rescan_a.py / rescan_b.py / rescan_skeptic.py (`--index`, `--index-all`) and by
hooks/precommit_check.py. Read-only: it only runs `git ls-files`, `git diff --cached` and `git cat-file`.

    staged_paths(repo)                 paths added/copied/modified/renamed in the index vs HEAD (ACMR)
    staged_paths(repo, all_tracked=1)  every path in the index
    index_blobs(repo, paths)           yields (path, mode, data-or-None) from stage-0 index entries
"""
import os
import subprocess


def repo_root(start=None):
    return subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start or os.getcwd(),
                          capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()


def _z(out):
    return [p for p in out.split(b"\0") if p]


def staged_paths(repo, all_tracked=False):
    if all_tracked:
        out = subprocess.run(["git", "-C", repo, "ls-files", "-z"], capture_output=True, check=True).stdout
    else:
        out = subprocess.run(["git", "-C", repo, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"],
                             capture_output=True, check=True).stdout
    return [p.decode("utf-8", "replace") for p in _z(out)]


def index_entries(repo):
    """path -> (mode, sha) for every stage-0 entry."""
    out = subprocess.run(["git", "-C", repo, "ls-files", "-s", "-z"], capture_output=True, check=True).stdout
    ents = {}
    for rec in _z(out):
        meta, path = rec.split(b"\t", 1)
        mode, sha, stage = meta.split()
        if stage == b"0":
            ents[path.decode("utf-8", "replace")] = (mode.decode(), sha.decode())
    return ents


def index_blobs(repo, paths):
    """Yield (path, mode, data) for each requested path. data is None when the path is not a blob in the index
    (missing, or a gitlink / submodule entry) -- callers must treat None as a finding, never as 'clean'."""
    ents = index_entries(repo)
    want = [(p, ents.get(p)) for p in paths]
    p = subprocess.Popen(["git", "-C", repo, "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for path, ent in want:
            if ent is None or not ent[0].startswith("100"):
                yield path, (ent[0] if ent else None), None
                continue
            mode, sha = ent
            p.stdin.write((sha + "\n").encode("ascii"))
            p.stdin.flush()
            hdr = p.stdout.readline().split()
            if len(hdr) < 3 or hdr[1] != b"blob":
                yield path, mode, None
                continue
            n = int(hdr[2])
            data = p.stdout.read(n)
            p.stdout.read(1)
            yield path, mode, data
    finally:
        p.stdin.close()
        p.wait()
