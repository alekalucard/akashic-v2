# -*- coding: utf-8 -*-
"""merge_duplicate_nodes.py - collapse duplicate concept nodes, UNIONING their edges.
   (2026-08-30, Nous + Ace)

    python scripts/merge_duplicate_nodes.py            # dry run, writes nothing
    python scripts/merge_duplicate_nodes.py --apply    # merge, verify, keep a backup

WHY THIS IS NOT CLEANUP
    Measured on the live cortex: 3,448 names occupy 14,606 extra slots, and for 1,346 of
    those names MORE THAN ONE COPY HOLDS EDGES. Unioning them recovers 22,761 neighbour
    relationships she already earned but cannot reach -- half her knowledge about a thing
    sitting on a node the reasoner never looks at. Shrinking the file is the side effect;
    RECONNECTING her is the point.

WHY IT IS SAFE TO DO NOW (established before building this)
    Duplicates are HISTORICAL, not active. Sampled 4 minutes on the live manifold:
    she added 409 nodes and `distinct` rose by exactly 409 -- every new node unique --
    while dupExtra held at 14,606 (+0, +0, +0, +0). The write path dedups correctly today;
    these are debris from an older one. So this is a one-time pass, not a losing battle.
    ⇒ An earlier theory that two ManifoldMemory writers caused it was REFUTED: the second
      instance is the readonly `cortex:ro` handle (it logged `mode=dict (fallback)+no-keys`,
      which only a readonly open produces) and writes are blocked for it.

DESIGN: NO SLOT RENUMBERING
    Dead copies are FLAGGED deleted in place; every surviving slot keeps its number.
    Only the edge region is rewritten. That means .keys and .csr rebuild on next open
    exactly as they did after the expansion (keys reloads only when its stored key-count
    matches; CSR rebuilds when edge count changes -- both will differ). Renumbering was
    the dangerous part of the expansion and is simply not needed here.

SURVIVOR SELECTION -- her own precedence, not one I invented
    1. most edges          (the copy the graph actually uses)
    2. highest TRACE_PRIORITY  (upsert_node's own rule: ACE 12 > PERSONAL/NOUS 10 > SEEDED 9 ...)
    3. highest count, then highest activation
    4. lowest slot         (deterministic tie-break so runs are reproducible)

SKIPPED DELIBERATELY
    Names whose copies differ in REGION or NODE_TYPE (2 and 2 respectively). Those are not
    the same node; merging them would destroy provenance. Left exactly as they are.
"""
import argparse
import os
import shutil
import struct
import sys
import time
from collections import defaultdict

HEADER = struct.Struct("<4sIIIQQQII")
NODE = struct.Struct("<IHHHHfIHfHBBIIHII16x")
EDGE = struct.Struct("<IIfBBIf2x")
HEADER_SIZE = 4096
P = r"F:\Sandbox\failure_factory\akashic_v2\state\akashic\cortex.manifold"

TRACE_PRIORITY = {8: 12, 1: 10, 12: 10, 7: 9, 10: 8, 6: 7, 4: 5, 3: 4,
                  9: 3, 2: 3, 11: 2, 5: 2, 0: 1}
UINT32_MAX = 0xFFFFFFFF
UINT16_MAX = 0xFFFF


def w(s):
    try:
        print(str(s).encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception:
        pass


def she_is_running():
    try:
        import re
        import psutil
    except Exception:
        return None
    pat = re.compile(r"(^|[\\/\s])server\.py(\s|$)")
    for p in psutil.process_iter(["pid", "cmdline", "memory_info"]):
        try:
            cl = " ".join(p.info.get("cmdline") or [])
            if pat.search(cl) and p.info["memory_info"].rss > 5e8:
                return p.info["pid"]
        except Exception:
            pass
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--allow-live-dryrun", action="store_true",
                    help="permit the read-only dry run while she is up")
    args = ap.parse_args()

    pid = she_is_running()
    if pid and not (args.allow_live_dryrun and not args.apply):
        w("*** server.py is RUNNING (pid %s) -- she has this file mmap'd. Refusing." % pid)
        raise SystemExit(2)
    if pid:
        w("(she is live -- READ ONLY dry run)")

    t0 = time.time()
    with open(P, "rb") as f:                      # 'rb'. never a write handle here.
        (magic, ver, nc, ec, str_off, edge_off,
         str_used, ncap, ecap) = HEADER.unpack_from(f.read(HEADER_SIZE), 0)
        if magic != b"MNFL":
            raise SystemExit("bad magic")
        f.seek(HEADER_SIZE)
        nraw = bytearray(f.read(nc * NODE.size))
        f.seek(str_off)
        table = f.read(str_used)
        f.seek(edge_off)
        eraw = f.read(ec * EDGE.size)
    side = b""
    if os.path.isfile(P + ".names"):
        side = open(P + ".names", "rb").read()
    limit = edge_off - str_off

    def name_at(off, ln):
        if off < limit:
            return table[off:off + ln].decode("utf-8", "replace")
        pos = off - limit
        if pos + 4 > len(side):
            return ""
        (n,) = struct.unpack_from("<I", side, pos)
        if n > 5000:
            return ""
        return side[pos + 4:pos + 4 + n].decode("utf-8", "replace")

    w("cortex: %d nodes/%d cap, %d edges/%d cap" % (nc, ncap, ec, ecap))

    # ---- nodes -------------------------------------------------------------
    fields = {}
    by_name = defaultdict(list)
    for slot in range(nc):
        r = list(NODE.unpack_from(nraw, slot * NODE.size))
        if r[1] == 0 or (r[9] & 0x2):
            continue
        nm = name_at(r[0], r[1])
        if not nm:
            continue
        fields[slot] = r
        by_name[nm].append(slot)

    # ---- degrees + neighbours ---------------------------------------------
    deg = defaultdict(int)
    for i in range(ec):
        a, b, wt, rel, fl, tid, ca = EDGE.unpack_from(eraw, i * EDGE.size)
        if fl & 0x1 or (a == 0 and b == 0 and wt == 0.0):
            continue
        deg[a] += 1
        deg[b] += 1

    dups = {n: s for n, s in by_name.items() if len(s) > 1}
    w("  live named %d | distinct %d | duplicated names %d (extra slots %d)" % (
        len(fields), len(by_name), len(dups), sum(len(s) - 1 for s in dups.values())))

    # ---- choose survivors --------------------------------------------------
    remap = {}                     # dead slot -> survivor slot
    skipped_region = skipped_type = 0
    # EXPECTED RESIDUAL: extras left behind by names we deliberately skip. Computed
    # EXACTLY, not guessed. The first run of this script failed its own verify at 29
    # residual duplicates because the check allowed `skipped + 2` -- it assumed a skipped
    # name has ~2 copies. The two skipped names have 19 and 12 (fs:AffectBridgeFairy and
    # fs:ChemicalAlchemyFairy, each written under region 1 by old code and region 3 after
    # the region fix). 18 + 11 = 29, precisely. The merge was right; the assertion was
    # lazy. Replaced with exact equality, which is STRICTER than the threshold it replaces.
    expected_residual = 0
    merged_names = 0
    for nm, slots in dups.items():
        if len({fields[s][11] for s in slots}) > 1:
            skipped_region += 1
            expected_residual += len(slots) - 1
            continue
        if len({fields[s][10] for s in slots}) > 1:
            skipped_type += 1
            expected_residual += len(slots) - 1
            continue
        best = sorted(slots, key=lambda s: (
            -deg.get(s, 0),
            -TRACE_PRIORITY.get(fields[s][12], 0),
            -fields[s][6],
            -fields[s][5],
            s))[0]
        merged_names += 1
        surv = fields[best]
        for s in slots:
            if s == best:
                continue
            d = fields[s]
            surv[6] = min(UINT32_MAX, surv[6] + d[6])            # count: sum
            surv[15] = min(UINT32_MAX, surv[15] + d[15])         # frequency: sum
            surv[5] = max(surv[5], d[5])                         # activation: max
            if TRACE_PRIORITY.get(d[12], 0) > TRACE_PRIORITY.get(surv[12], 0):
                surv[12] = d[12]                                 # tracer: highest priority
            if surv[14] == 0 and d[14] > 0:                      # snippet: inherit if absent
                surv[13], surv[14] = d[13], d[14]
            remap[s] = best
    w("  merging %d names | skipped: region %d, node_type %d (leaves %d extras by design)" % (
        merged_names, skipped_region, skipped_type, expected_residual))
    w("  slots to retire: %d" % len(remap))

    # ---- rewrite edges -----------------------------------------------------
    seen = {}
    self_loops = 0
    collapsed = 0
    kept = 0
    out_edges = []
    for i in range(ec):
        e = list(EDGE.unpack_from(eraw, i * EDGE.size))
        a, b, wt, rel, fl = e[0], e[1], e[2], e[3], e[4]
        if fl & 0x1 or (a == 0 and b == 0 and wt == 0.0):
            continue
        na, nb = remap.get(a, a), remap.get(b, b)
        if na == nb:
            self_loops += 1
            continue
        key = (min(na, nb), max(na, nb), rel)
        if key in seen:
            j = seen[key]
            if wt > out_edges[j][2]:
                out_edges[j][2] = wt
            collapsed += 1
            continue
        e[0], e[1] = na, nb
        seen[key] = len(out_edges)
        out_edges.append(e)
        kept += 1
    w("  edges: %d -> %d  (self-loops dropped %d, duplicate pairs collapsed %d)" % (
        ec, len(out_edges), self_loops, collapsed))

    # ---- recompute degree hints + flag the dead ----------------------------
    newdeg = defaultdict(int)
    for e in out_edges:
        newdeg[e[0]] += 1
        newdeg[e[1]] += 1
    for slot, r in fields.items():
        if slot in remap:
            r[9] |= 0x2                                   # FLAG deleted, slot stays put
        else:
            r[7] = min(UINT16_MAX, newdeg.get(slot, 0))

    live_after = len(fields) - len(remap)
    w("")
    w("  RESULT  nodes %d -> %d live   edges %d -> %d" % (
        len(fields), live_after, ec, len(out_edges)))
    w("  file stays %.2f GB (no renumbering; dead slots flagged in place)"
      % (os.path.getsize(P) / 1e9))

    if not args.apply:
        w("")
        w("  DRY RUN -- nothing written. Re-run with --apply (she must be DOWN).")
        return

    # ---- write -------------------------------------------------------------
    BAK = P + ".pre_merge_20260830"
    if os.path.exists(BAK):
        w("  ABORT: %s exists" % os.path.basename(BAK))
        raise SystemExit(1)
    shutil.copy2(P, BAK)
    w("")
    w("  backup -> %s (%.2f GB)" % (os.path.basename(BAK), os.path.getsize(BAK) / 1e9))

    for slot, r in fields.items():
        NODE.pack_into(nraw, slot * NODE.size, *r)

    with open(P, "r+b") as f:
        f.seek(HEADER_SIZE)
        f.write(bytes(nraw))
        f.seek(edge_off)
        buf = bytearray(len(out_edges) * EDGE.size)
        for i, e in enumerate(out_edges):
            EDGE.pack_into(buf, i * EDGE.size, *e)
        f.write(bytes(buf))
        # zero the tail so stale edges cannot be read back
        f.write(b"\x00" * min((ec - len(out_edges)) * EDGE.size, 64 * 1024 * 1024))
        f.seek(0)
        f.write(HEADER.pack(magic, ver, nc, len(out_edges), str_off, edge_off,
                            str_used, ncap, ecap))
        f.flush()
        os.fsync(f.fileno())
    w("  written in %.1fs" % (time.time() - t0))

    # ---- verify by re-reading ---------------------------------------------
    w("")
    w("  verifying by reading the file back...")
    with open(P, "rb") as f:
        (m2, v2, n2, e2, so2, eo2, su2, nc2, ec2) = HEADER.unpack_from(f.read(HEADER_SIZE), 0)
        f.seek(HEADER_SIZE)
        vn = f.read(n2 * NODE.size)
    live = 0
    names2 = defaultdict(int)
    for slot in range(n2):
        r = NODE.unpack_from(vn, slot * NODE.size)
        if r[1] == 0 or (r[9] & 0x2):
            continue
        live += 1
        names2[name_at(r[0], r[1])] += 1
    extra = sum(v - 1 for v in names2.values() if v > 1)
    bad = []
    for label, ok, d in [
        ("magic intact", m2 == b"MNFL", repr(m2)),
        ("edge count updated", e2 == len(out_edges), "%d" % e2),
        ("live nodes match plan", live == live_after, "%d vs %d" % (live, live_after)),
        ("duplicate extras == expected residual", extra == expected_residual,
         "%d (expected %d from %d skipped names)" % (extra, expected_residual,
                                                     skipped_region + skipped_type)),
        ("capacities untouched", nc2 == ncap and ec2 == ecap, "%d/%d" % (nc2, ec2)),
        ("offsets untouched", so2 == str_off and eo2 == edge_off, "ok"),
    ]:
        w("    %-34s %s %s" % (label, "ok" if ok else "** FAIL **", d))
        if not ok:
            bad.append(label)
    if bad:
        w("")
        w("  *** VERIFY FAILED -- restoring from backup")
        shutil.copy2(BAK, P)
        raise SystemExit(1)
    w("")
    w("  DONE. live nodes %d, edges %d, duplicate extras %d" % (live, e2, extra))
    w("  Rollback: stop her, copy %s back over cortex.manifold." % os.path.basename(BAK))


if __name__ == "__main__":
    main()
