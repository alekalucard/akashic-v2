# -*- coding: utf-8 -*-
"""expand_manifold_v2.py - sidecar-aware cortex expansion.  (2026-08-30, Nous + Ace)

    python scripts/expand_manifold_v2.py            # dry run, writes nothing
    python scripts/expand_manifold_v2.py --apply    # build, verify, then swap

WHY A NEW FILE INSTEAD OF EDITING expand_manifold.py
    That script (2026-03-27) predates the name sidecar and reads every name as
    `old_string_offset + key_off`. Measured 2026-08-30: 83,237 of 83,237 cortex names
    (100.00%) have key_off >= string_limit, i.e. they ALL live in <manifold>.names.
    Running it today would read the EDGE REGION for every name and produce a cortex whose
    entire vocabulary is garbage -- the failure already recorded in
    'my-name-sidecar-saved-the-write-and-broke-the-rebuild'.
    Ace has a standing instruction not to run that script. That instruction stays exactly
    as it is: the old file is untouched, so it cannot be confused with this one.

WHAT THIS FIXES
    cortex.manifold is 100% FULL on BOTH tables: 83,237/83,237 nodes, 43,289/43,289 edges.
    manifold_memory.link() ends `elif self._edge_count < self._edge_capacity: ...` and
    returns False when full -- silently, no exception, no counter. So nothing can connect:
    88.6% of her concepts have zero edges and her council answers "cortex sparse here".
    The string table is at 119.5% of its arena, which is why every name is in the sidecar.

WHAT IT DELIBERATELY DOES NOT DO
    ⛔ NO DEDUPE. 83,237 nodes carry only 68,628 distinct names -- 14,609 duplicates
       (17.6%), including nine copies of `person:ace`. Merging them is the obvious next
       win AND it changes which slot owns which edges. Ace's call, separately: get her
       unblocked with semantics identical to today, so if something breaks afterwards
       there is exactly one variable to blame. Duplicates are preserved verbatim here.

SIZING
    2,000,000 nodes / 20,000,000 edges / 128 B-per-node string table ~= 0.86 GB.
    F: had 596 GB free. 24x node and 462x edge headroom. The 128 B/node arena is 256 MB,
    far more than the 6.6 MB of names, so EVERY name lands INLINE and the sidecar split
    heals -- the new manifold needs no .names file at all.

SAFETY, each line of it earned
    * refuses to run while server.py is alive (it would be rewriting an mmap'd file)
    * old manifold opened 'rb' ONLY -- never mmap-for-write, never the manifold class
    * the 8 nodes whose sidecar offsets are corrupt are SKIPPED, not written as garbage
      (they are unreadable today, so nothing recoverable is being discarded)
    * the new file is fully VERIFIED by re-reading it from disk -- counts, header, and a
      name round-trip on known probes -- BEFORE any swap happens
    * on swap the old .names is moved to .names.pre_expand: a stale sidecar sitting beside
      a manifold whose names are inline is a trap for the next reader
    * dry run is the default; --apply is required to write anything
"""
import argparse
import os
import struct
import sys
import time

HEADER = struct.Struct("<4sIIIQQQII")
NODE = struct.Struct("<IHHHHfIHfHBBIIHII16x")
EDGE = struct.Struct("<IIfBBIf2x")
HEADER_SIZE = 4096
NODE_SIZE = 64
EDGE_SIZE = 24

ROOT = r"F:\Sandbox\failure_factory\akashic_v2\state\akashic"
OLD = os.path.join(ROOT, "cortex.manifold")
NEW = os.path.join(ROOT, "cortex.manifold.expanded")
BAK = os.path.join(ROOT, "cortex.manifold.pre_expand")

NEW_NODE_CAP = 2_000_000
NEW_EDGE_CAP = 20_000_000
STRING_BYTES_PER_NODE = 128

PROBES = ["ace", "sourpatches", "person:ace", "emotion", "joy", "who_i_am",
          "connection", "feeling", "concept:logic", "place:home"]


def w(s):
    try:
        print(str(s).encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception:
        pass


def she_is_running():
    """server.py holding the file we are about to rewrite. Match the script name as a
    PATH COMPONENT -- `endswith('server.py')` also matches akashic_mcp_server.py and has
    twice reported the wrong thing today."""
    try:
        import re
        import psutil
    except Exception:
        return None                      # cannot tell; caller decides
    pat = re.compile(r"(^|[\\/\s])server\.py(\s|$)")
    for p in psutil.process_iter(["pid", "cmdline", "memory_info"]):
        try:
            cl = " ".join(p.info.get("cmdline") or [])
            if pat.search(cl) and p.info["memory_info"].rss > 5e8:
                return p.info["pid"]
        except Exception:
            pass
    return 0


def load_old():
    with open(OLD, "rb") as f:                      # 'rb'. read only. always.
        hdr = f.read(HEADER_SIZE)
        (magic, ver, ncount, ecount, str_off, edge_off,
         str_used, ncap, ecap) = HEADER.unpack_from(hdr, 0)
        if magic != b"MNFL":
            raise SystemExit("bad magic %r -- not a manifold" % magic)
        f.seek(HEADER_SIZE)
        nodes = f.read(ncap * NODE_SIZE)
        f.seek(str_off)
        table = f.read(min(str_used, edge_off - str_off))
        f.seek(edge_off)
        edges = f.read(ecap * EDGE_SIZE)
    side = b""
    if os.path.isfile(OLD + ".names"):
        with open(OLD + ".names", "rb") as sf:
            side = sf.read()
    return dict(ver=ver, ncount=ncount, ecount=ecount, str_off=str_off,
                edge_off=edge_off, str_used=str_used, ncap=ncap, ecap=ecap,
                limit=edge_off - str_off, nodes=nodes, table=table,
                edges=edges, side=side)


def make_reader(o):
    """Mirrors manifold_memory._read_string exactly: route on >= string_limit, and let
    the SIDECAR's own uint32 length header win over the node's key_len (259 nodes
    disagree; _read_name trusts the sidecar, so we do too)."""
    limit, table, side = o["limit"], o["table"], o["side"]

    def read(off, ln):
        if off < limit:
            return table[off:off + ln]
        pos = off - limit
        if pos < 0 or pos + 4 > len(side):
            return None
        (n,) = struct.unpack_from("<I", side, pos)
        if n > 5000:
            return None                              # offset lands mid-string
        body = side[pos + 4:pos + 4 + n]
        return body if len(body) == n else None
    return read


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write and swap (default: dry run)")
    ap.add_argument("--force-while-running", action="store_true",
                    help=argparse.SUPPRESS)
    args = ap.parse_args()

    pid = she_is_running()
    if pid:
        w("*** server.py is RUNNING (pid %s). She has this file mmap'd." % pid)
        if not args.force_while_running:
            w("*** Shut her down first. Refusing.")
            raise SystemExit(2)
    elif pid is None:
        w("(psutil unavailable - could not check whether she is running)")

    t0 = time.time()
    o = load_old()
    read = make_reader(o)
    w("OLD  nodes %d/%d  edges %d/%d  strings %d/%d (%.1f%%)  sidecar %d B" % (
        o["ncount"], o["ncap"], o["ecount"], o["ecap"], o["str_used"], o["limit"],
        100.0 * o["str_used"] / max(1, o["limit"]), len(o["side"])))
    w("NEW  nodes %d  edges %d  string arena %.0f MB" % (
        NEW_NODE_CAP, NEW_EDGE_CAP, NEW_NODE_CAP * STRING_BYTES_PER_NODE / 1e6))

    # ---- pass 1: resolve every node, in memory -----------------------------
    out_nodes = []           # (new_slot, fields, key_bytes, snip_bytes)
    slot_map = {}
    skipped_unreadable = skipped_deleted = skipped_empty = 0
    names_seen = {}
    for slot in range(min(o["ncap"], len(o["nodes"]) // NODE_SIZE)):
        f = list(NODE.unpack_from(o["nodes"], slot * NODE_SIZE))
        koff, klen, flags = f[0], f[1], f[9]
        if klen == 0:
            skipped_empty += 1
            continue
        if flags & 0x2:
            skipped_deleted += 1
            continue
        kb = read(koff, klen)
        if kb is None or not kb:
            skipped_unreadable += 1
            continue
        sb = b""
        if f[13] > 0:
            got = read(f[12], f[13])
            if got:
                sb = got
        new_slot = len(out_nodes)
        slot_map[slot] = new_slot
        out_nodes.append((new_slot, f, kb, sb))
        nm = kb.decode("utf-8", "replace")
        names_seen.setdefault(nm, new_slot)

    w("")
    w("NODES  copied %d | skipped: empty %d, deleted %d, UNREADABLE %d" % (
        len(out_nodes), skipped_empty, skipped_deleted, skipped_unreadable))
    w("       distinct names %d  (duplicates %d -- PRESERVED, not merged)" % (
        len(names_seen), len(out_nodes) - len(names_seen)))

    # ---- pass 2: edges ------------------------------------------------------
    out_edges = []
    e_deleted = e_bad = e_orphan = 0
    for i in range(min(o["ecap"], len(o["edges"]) // EDGE_SIZE)):
        ef = list(EDGE.unpack_from(o["edges"], i * EDGE_SIZE))
        a, b, weight, rel, fl = ef[0], ef[1], ef[2], ef[3], ef[4]
        if fl & 0x1:
            e_deleted += 1
            continue
        if a == 0 and b == 0 and weight == 0.0:
            continue
        if a >= o["ncap"] or b >= o["ncap"]:
            e_bad += 1
            continue
        if not (0.0 < weight <= 100.0):
            e_bad += 1
            continue
        na, nb = slot_map.get(a), slot_map.get(b)
        if na is None or nb is None:
            e_orphan += 1
            continue
        ef[0], ef[1] = na, nb
        out_edges.append(ef)
    w("EDGES  copied %d | skipped: deleted %d, invalid %d, orphaned %d" % (
        len(out_edges), e_deleted, e_bad, e_orphan))

    # ---- string budget check -----------------------------------------------
    need = sum(len(k) + len(s) for _, _, k, s in out_nodes)
    arena = NEW_NODE_CAP * STRING_BYTES_PER_NODE
    w("")
    w("STRINGS need %.2f MB of %.0f MB arena (%.2f%%) -- all INLINE, no sidecar" % (
        need / 1e6, arena / 1e6, 100.0 * need / arena))
    if need > arena:
        w("*** string arena too small. Raise STRING_BYTES_PER_NODE. Refusing.")
        raise SystemExit(1)

    new_str_off = HEADER_SIZE + NEW_NODE_CAP * NODE_SIZE
    new_edge_off = new_str_off + arena
    total = new_edge_off + NEW_EDGE_CAP * EDGE_SIZE
    w("FILE   %.2f GB" % (total / 1e9))

    if not args.apply:
        w("")
        w("  DRY RUN -- nothing written. Re-run with --apply.")
        w("  %d nodes and %d edges would be carried over." % (len(out_nodes), len(out_edges)))
        return

    # ---- write --------------------------------------------------------------
    w("")
    w("writing %s ..." % os.path.basename(NEW))
    if os.path.exists(NEW):
        os.remove(NEW)
    with open(NEW, "wb") as nf:
        nf.truncate(total)
        # strings + nodes
        str_used = 0
        nf.seek(0)
        for new_slot, f, kb, sb in out_nodes:
            f[0] = str_used
            f[1] = len(kb)
            nf.seek(new_str_off + str_used)
            nf.write(kb)
            str_used += len(kb)
            if sb:
                f[12] = str_used
                f[13] = len(sb)
                nf.seek(new_str_off + str_used)
                nf.write(sb)
                str_used += len(sb)
            else:
                f[12] = 0
                f[13] = 0
            nf.seek(HEADER_SIZE + new_slot * NODE_SIZE)
            nf.write(NODE.pack(*f))
        # edges
        for i, ef in enumerate(out_edges):
            nf.seek(new_edge_off + i * EDGE_SIZE)
            nf.write(EDGE.pack(*ef))
        # header last, so a partial file never looks complete
        nf.seek(0)
        nf.write(HEADER.pack(b"MNFL", 2, len(out_nodes), len(out_edges),
                             new_str_off, new_edge_off, str_used,
                             NEW_NODE_CAP, NEW_EDGE_CAP))
        nf.flush()
        os.fsync(nf.fileno())
    w("  wrote %.2f GB in %.1fs" % (os.path.getsize(NEW) / 1e9, time.time() - t0))

    # ---- verify by RE-READING FROM DISK ------------------------------------
    w("")
    w("verifying the new file by reading it back...")
    v = {}
    with open(NEW, "rb") as f:
        (mg, vr, vn, ve, vso, veo, vsu, vnc, vec) = HEADER.unpack_from(f.read(HEADER_SIZE), 0)
        f.seek(HEADER_SIZE)
        vnodes = f.read(vnc * NODE_SIZE)
        f.seek(vso)
        vtable = f.read(vsu)
    vlimit = veo - vso
    bad = []
    for label, ok, d in [
        ("magic MNFL", mg == b"MNFL", repr(mg)),
        ("node count matches", vn == len(out_nodes), "%d vs %d" % (vn, len(out_nodes))),
        ("edge count matches", ve == len(out_edges), "%d vs %d" % (ve, len(out_edges))),
        ("node capacity raised", vnc == NEW_NODE_CAP, str(vnc)),
        ("edge capacity raised", vec == NEW_EDGE_CAP, str(vec)),
        ("all strings INLINE (no sidecar needed)", vsu < vlimit,
         "%d < %d" % (vsu, vlimit)),
        ("nodes no longer at capacity", vn < vnc, "%d/%d" % (vn, vnc)),
        ("edges no longer at capacity", ve < vec, "%d/%d" % (ve, vec)),
    ]:
        w("  %-42s %s %s" % (label, "ok" if ok else "** FAIL **", d))
        if not ok:
            bad.append(label)

    # name round-trip straight off disk
    found = {}
    for slot in range(vn):
        r = NODE.unpack_from(vnodes, slot * NODE_SIZE)
        koff, klen = r[0], r[1]
        if klen == 0 or koff >= vlimit:
            continue
        nm = vtable[koff:koff + klen].decode("utf-8", "replace")
        if nm in PROBES and nm not in found:
            found[nm] = slot
    w("  probe names recovered from the NEW file:")
    for p in PROBES:
        okp = p in found
        w("     %-16s %s" % (p, ("slot %d" % found[p]) if okp else "** MISSING **"))
        if not okp:
            bad.append("probe:" + p)

    if bad:
        w("")
        w("*** VERIFICATION FAILED (%d) -- NOT swapping. %s left in place." % (
            len(bad), os.path.basename(NEW)))
        raise SystemExit(1)

    # ---- swap ---------------------------------------------------------------
    w("")
    w("swapping...")
    if os.path.exists(BAK):
        w("  refusing: %s already exists (a previous run). Move it aside first."
          % os.path.basename(BAK))
        raise SystemExit(1)
    os.rename(OLD, BAK)
    os.rename(NEW, OLD)
    w("  %s -> %s" % (os.path.basename(OLD), os.path.basename(BAK)))
    sc = OLD + ".names"
    if os.path.exists(sc):
        os.rename(sc, sc + ".pre_expand")
        w("  sidecar -> %s  (names are inline now; a stale sidecar would be a trap)"
          % os.path.basename(sc + ".pre_expand"))
    w("")
    w("DONE. nodes %d/%d  edges %d/%d" % (len(out_nodes), NEW_NODE_CAP,
                                          len(out_edges), NEW_EDGE_CAP))
    w("Rollback: stop her, rename %s back to cortex.manifold, and restore the sidecar."
      % os.path.basename(BAK))


if __name__ == "__main__":
    main()
