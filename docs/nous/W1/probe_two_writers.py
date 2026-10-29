"""W1 probe: what two read-write ManifoldMemory handles on ONE file do to new keys.

Synthetic only: builds a 1,000-slot manifold in a temp dir. Never opens a real *.manifold.
Imports code/infrastructure/manifold_memory.py (stdlib-only top level, no threads at import).

CONTROL:  one RW handle mints a key stream -> 0 duplicate records.
CONTROL2: two RW handles, no key learned by both -> 0 duplicates (the shared allocator
          at manifold_memory.py:657-697 keeps their SLOTS apart).
CASE:    two RW handles (the live layout: main-process region + portal_interior) mint the
         same key stream -> every shared key gets a second record; a fresh open indexes
         only the LAST slot, so the first record is orphaned (still active, not findable).

    python3 docs/nous/W1/probe_two_writers.py
"""
import os
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "code"))
from infrastructure.manifold_memory import ManifoldMemory, FLAG_DELETED  # noqa: E402


def records_by_key(path):
    m = ManifoldMemory(path, readonly=True)
    seen = Counter()
    for slot in range(m._node_capacity):          # same walk as _rebuild_indices (:782-797)
        rec = m._read_node(slot)
        if rec[1] == 0 or rec[9] == FLAG_DELETED:  # empty or deleted
            continue
        key = m._read_string(rec[0], rec[1])
        seen[key] += 1
    indexed = len(m._key_index)
    m.close()
    return seen, indexed


def run(n_handles, keys, shared_fraction):
    d = tempfile.mkdtemp(prefix="w1_probe_")
    path = os.path.join(d, "cortex.manifold")
    ManifoldMemory(path, node_capacity=1000, edge_capacity=4000).close()
    hs = [ManifoldMemory(path) for _ in range(n_handles)]
    n_shared = int(len(keys) * shared_fraction)
    for i, k in enumerate(keys):
        if i < n_shared:
            for h in hs:                       # a concept both writers learn
                h.upsert_node(k, activation=0.5)
        else:
            hs[i % n_handles].upsert_node(k, activation=0.5)   # a concept only one learns
    for h in hs:
        h.flush()
        h.close()
    seen, indexed = records_by_key(path)
    dup_keys = sum(1 for c in seen.values() if c > 1)
    return dict(handles=n_handles, keys=len(keys), records=sum(seen.values()),
                distinct=len(seen), dup_keys=dup_keys, indexed_on_reopen=indexed,
                orphaned=sum(seen.values()) - indexed)


if __name__ == "__main__":
    keys = ["concept_%03d" % i for i in range(180)]
    ctrl = run(1, keys, shared_fraction=1 / 9)
    ctrl2 = run(2, keys, shared_fraction=0.0)
    case = run(2, keys, shared_fraction=1 / 9)
    print("CONTROL (1 writer): ", ctrl)
    print("CONTROL2 (2 writers, no key learned by both):", ctrl2)
    print("CASE    (2 writers):", case)
    ok = ctrl["dup_keys"] == 0 and ctrl2["dup_keys"] == 0 and case["dup_keys"] == int(len(keys) / 9)
    print("RESULT:", "as predicted (shared keys minted twice only with 2 writers)" if ok else "NOT as predicted")
    sys.exit(0 if ok else 1)
