#!/usr/bin/env python3
"""Candidate near-miss pairs between dead letters (A) and deaf ears (B).

Stdlib only; reuses tools/dead_letters.py (static ast read, nothing under code/ runs).
Prints candidates; every pair still has to be confirmed by reading both ends.

    python3 -W ignore tools/dead_letter_pairs.py [--max-dist 2]

Kinds (strongest first):
  wildcard   B is a literal "x.*" (no router has wildcards) and A starts with "x."
  norm       equal after lower-casing, '_'/'-' -> '.', and dropping a plural 's' per segment
  swap       same segments, different order
  edit       Levenshtein distance <= --max-dist on the whole string (and not explained above)
  prefix     same tail (last 1 or 2 segments, tail length >= 8 chars), different head (renamed prefix)
  depth      one is the other plus or minus one segment
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dead_letters as dl  # noqa: E402


def lev(a: str, b: str, cap: int) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def norm(t: str) -> str:
    segs = t.lower().replace("-", ".").replace("_", ".").split(".")
    return ".".join(s[:-1] if len(s) > 3 and s.endswith("s") and not s.endswith("ss") else s for s in segs)


def candidates(dead, deaf, max_dist=2, renames=True):
    out = []
    # a tail word shared by many topics ("complete", "response") says nothing about identity
    tail_count = defaultdict(int)
    for t in set(dead) | set(deaf):
        tail_count[t.split(".")[-1]] += 1
    for b in deaf:
        bs = b.split(".")
        for a in dead:
            if dl.WILD in a or dl.WILD in b:
                continue
            as_ = a.split(".")
            kind = None
            if b.endswith(".*") and a.startswith(b[:-1]):
                kind = "wildcard"
            elif norm(a) == norm(b):
                kind = "norm"
            elif len(as_) == len(bs) and sorted(as_) == sorted(bs):
                kind = "swap"
            else:
                d = lev(a, b, max_dist)
                if d <= max_dist:
                    kind = f"edit{d}"
                else:
                    for k in ((2, 1) if renames else ()):
                        if len(as_) > k and len(bs) > k and as_[-k:] == bs[-k:] and \
                                len(".".join(as_[-k:])) >= 8 and as_[:-k] != bs[:-k] and \
                                (k == 2 or tail_count[as_[-1]] <= 2):
                            kind = f"prefix{k}"
                            break
                    if kind is None and renames and abs(len(as_) - len(bs)) == 1:
                        lo, hi = (as_, bs) if len(as_) < len(bs) else (bs, as_)
                        for i in range(len(hi)):
                            if hi[:i] + hi[i + 1:] == lo and len(lo) >= 2:
                                kind = "depth"
                                break
            if kind:
                out.append((kind, a, b))
    order = {"wildcard": 0, "norm": 1, "swap": 2, "edit1": 3, "edit2": 4, "prefix2": 5, "prefix1": 6, "depth": 7}
    out.sort(key=lambda x: (order.get(x[0], 9), x[1], x[2]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-dist", type=int, default=2)
    args = ap.parse_args()
    live, tests, shadowed, reached = dl.census()
    sites = dl.scan(live)
    pub, sub = defaultdict(list), defaultdict(list)
    for s in sites:
        for t in s.topics:
            if s.kind == "pub":
                pub[t].append(s.loc)
            elif s.kind == "sub":
                sub[t].append(s.loc)
    dead, deaf = dl.dead_and_deaf(sites)
    rows = candidates(sorted(dead), sorted(deaf), args.max_dist)
    print(f"## A x B   A={len(dead)} B={len(deaf)} candidates={len(rows)}")
    for kind, a, b in rows:
        print(f"{kind:8s} A {a:45s} {', '.join(pub[a][:2])}")
        print(f"{'':8s} B {b:45s} {', '.join(sub[b][:2])}")
    # A against ears that DO hear something: the letter may be a misspelling of a live channel.
    live_ears = sorted(set(sub) - set(deaf))
    rows = candidates(sorted(dead), live_ears, args.max_dist, renames=False)
    print(f"## A x live ears (subscribed and published elsewhere)   candidates={len(rows)}")
    for kind, a, b in rows:
        print(f"{kind:8s} A {a:45s} {', '.join(pub[a][:2])}")
        print(f"{'':8s} S {b:45s} {', '.join(sub[b][:2])}")


if __name__ == "__main__":
    main()
