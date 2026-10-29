# -*- coding: utf-8 -*-
"""grow_cortex.py -- OFFLINE, slot-preserving capacity growth for a v2 .manifold.

    python tools/grow_cortex.py --manifold <path> --nodes 4000000            # dry run
    AKASHIC_CORTEX_GROW=1 python tools/grow_cortex.py --manifold <path> --nodes 4000000 --apply

W6 (2026-10-29). Owner's direction: grow the space instead of deleting from it.

WHAT IT DOES
    Old layout:  HEADER(4096) | NODES old_cap*64 | STRINGS arena | EDGES old_ecap*24
    New layout:  HEADER(4096) | NODES new_cap*64 | STRINGS arena | EDGES new_ecap*24
    * every node record is copied BYTE-FOR-BYTE to the SAME slot (incl. the 16 reserved
      bytes: affect_coupling / paradox_residue). No slot is renumbered, so edges, the
      .embeddings file (slot-indexed) and any slot held elsewhere stay valid.
    * the string arena is copied verbatim with the SAME size. Key/snippet offsets are
      relative to string_offset, and the .names sidecar tag is `offset >= arena size`,
      so neither needs rewriting. (Growing the arena would require re-tagging every
      sidecar name; deliberately not done.)
    * edge records are copied verbatim (they hold slot ids, which did not change).
    * header: bytes 48..4095 (region stats, future fields) copied verbatim; only
      string_offset, edge_offset, node_capacity, edge_capacity change. Counts unchanged.
    No memory is edited, merged, deduplicated or dropped.

CRASH SAFETY
    1. write <path>.grow.tmp in the same directory; its magic stays zero until the very
       last write, so a partial temp never looks like a manifold
    2. fsync, then VERIFY by re-reading both files from disk
    3. hard-link (or copy) the old file to <path>.pre_grow.<ts>   (rollback copy)
    4. move the DERIVED companions .csr and .keys aside (they encode node_capacity and
       ManifoldMemory's freshness check does not compare it -- a stale .csr would load
       with the old N and GPUSpread's (N,N) tensor would not match). They rebuild on the
       next open. Done BEFORE the swap: if we crash here the old manifold simply rebuilds
       them, which is harmless.
    5. fsync the directory (backup link + companion renames durable), then a FINAL
       CHECK right before the swap: full SHA-256 of the source == the one taken before
       the copy, a second in-use scan, and (size, mtime, inode) unchanged. Any hit:
       refuse, put the companions back, drop the backup link, delete the temp.
       os.replace(tmp, path)  -- atomic on POSIX and NTFS; then fsync the directory
    6. extend <path>.embeddings with zeros to new_cap*768 (ManifoldMemory would do this
       itself on a read-write open, manifold_memory.py _ensure_embedding_file)
    A crash before 5 leaves the live file byte-identical. A crash after 5 leaves the
    verified new file live and the old bytes in the .pre_grow copy.

REFUSES TO RUN WHEN THE FILE LOOKS IN USE (best effort, see in_use_report)
    * Linux: every readable /proc/<pid>/fd and /proc/<pid>/maps is checked for the
      manifold's or a companion's (st_dev, st_ino) -- catches open handles AND mmaps
    * Windows: CreateFileW with share mode 0 fails with a sharing violation while any
      handle (an mmap holds one) is open
    * psutil, if installed: any process whose cmdline has server.py as a path component
    * quiescence: size/mtime of the manifold must not change over a short window
    * a <path>.grow.lock created O_EXCL stops two growers at once
    * if no detection method works on this OS, refuses unless --assume-down is given
    * FAIL CLOSED (fix round): if ANY process could not be inspected (unreadable
      /proc/<pid>/fd AND maps: another user, hidepid), refuses unless --assume-down
    And re-checks the source's (size, mtime, inode) after verify, then runs the FINAL
    CHECK above immediately before os.replace.

SWITCH: --apply additionally requires AKASHIC_CORTEX_GROW=1 in the environment.
There is no runtime path: nothing in her code imports or calls this.
"""
import argparse
import os
import shutil
import struct
import sys
import time

HEADER_STRUCT = struct.Struct("<4sIIIQQQII")   # == manifold_memory.HEADER_STRUCT (48 B)
HEADER_SIZE = 4096
NODE_SIZE = 64                                 # == manifold_memory.NODE_RECORD_SIZE
EDGE_SIZE = 24                                 # == manifold_memory.EDGE_RECORD_SIZE
EMB_BYTES = 384 * 2                            # == ManifoldMemory.EMBEDDING_BYTES_PER_NODE
MAGIC = b"MNFL"
CHUNK = 16 * 1024 * 1024
DERIVED_COMPANIONS = (".csr", ".keys")         # encode node_capacity, rebuilt on open
ALL_COMPANIONS = (".csr", ".keys", ".embeddings", ".names")

# Steps in order. Tests set _FAULT to one of these to simulate a crash there.
STEPS = ("lock", "in_use", "read_old", "tmp_create", "copy_nodes", "zero_new_nodes",
         "copy_strings", "copy_edges", "zero_new_edges", "write_header", "fsync_tmp",
         "verify", "recheck_source", "backup", "move_companions", "final_check", "replace",
         "dirsync", "extend_embeddings", "unlock")
_FAULT = None
_FAULT_MODE = "raise"      # "exit" = os._exit(9): a hard kill, no finally blocks run


class InjectedCrash(Exception):
    pass


class GrowRefused(Exception):
    pass


def _step(name):
    if _FAULT == name:
        if _FAULT_MODE == "exit":
            os._exit(9)
        raise InjectedCrash(name)


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- in-use detection

def _ids(paths):
    out = {}
    for p in paths:
        try:
            st = os.stat(p)
            out[(st.st_dev, st.st_ino)] = p
        except OSError:
            pass
    return out


def _proc_scan(paths):
    """Linux /proc scan. Returns (hits, uninspectable_pids) or None when /proc is absent."""
    if not os.path.isdir("/proc/self/fd"):
        return None
    ids = _ids(paths)
    real = {os.path.realpath(p): p for p in ids.values()}
    me = os.getpid()
    hits, blind = [], 0
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == me:
            continue
        seen_any = False
        try:
            for fd in os.listdir("/proc/%s/fd" % pid):
                try:
                    st = os.stat("/proc/%s/fd/%s" % (pid, fd))
                except OSError:
                    continue
                k = (st.st_dev, st.st_ino)
                if k in ids:
                    hits.append("pid %s has %s open (fd %s)" % (pid, ids[k], fd))
            seen_any = True
        except (PermissionError, FileNotFoundError, ProcessLookupError):
            pass
        try:
            with open("/proc/%s/maps" % pid, "r") as f:
                for line in f:
                    parts = line.split(None, 5)
                    if len(parts) < 6:
                        continue
                    try:
                        ino = int(parts[4])
                        maj, mnr = (int(x, 16) for x in parts[3].split(":"))
                    except ValueError:
                        continue
                    mpath = parts[5].strip()
                    for (dev, i), p in ids.items():
                        # dev in maps can differ from stat's on overlay filesystems, so a
                        # path match with the same inode also counts
                        if ino == i and ((os.major(dev), os.minor(dev)) == (maj, mnr)
                                         or real.get(mpath) == p):
                            hits.append("pid %s has %s mmap'd" % (pid, p))
                            break
            seen_any = True
        except (PermissionError, FileNotFoundError, ProcessLookupError, OSError):
            pass
        if not seen_any and os.path.exists("/proc/%s" % pid):
            blind += 1                          # (a pid that exited mid-scan is not blind)
    return hits, blind


def _proc_hidden():
    """True when /proc HIDES other users' pids from us (hidepid=2/invisible or 4/ptraceable)
    and we are not root: those pids are not listed at all, so _proc_scan cannot count them."""
    if os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() == 0:
        return False
    try:
        with open("/proc/self/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[1] == "/proc":
                    return bool({"hidepid=2", "hidepid=invisible", "hidepid=4",
                                 "hidepid=ptraceable"} & set(parts[3].split(",")))
    except OSError:
        pass
    return False


def _win_exclusive(paths):
    """Windows: an exclusive open fails while any other handle exists. None off-Windows."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    INVALID = wintypes.HANDLE(-1).value
    hits = []
    for p in paths:
        if not os.path.exists(p):
            continue
        h = k32.CreateFileW(p, 0x80000000, 0, None, 3, 0x80, None)   # GENERIC_READ, share 0, OPEN_EXISTING
        if h == INVALID or h is None:
            err = ctypes.get_last_error()
            hits.append("%s cannot be opened exclusively (winerror %d: in use)" % (p, err))
        else:
            k32.CloseHandle(h)
    return hits


def _psutil_scan():
    try:
        import re
        import psutil
    except Exception:
        return None
    pat = re.compile(r"(^|[\\/\s])server\.py(\s|$)")
    hits = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            cl = " ".join(p.info.get("cmdline") or [])
            if pat.search(cl) and p.info["pid"] != os.getpid():
                hits.append("pid %s is running server.py" % p.info["pid"])
        except Exception:
            pass
    return hits


def in_use_report(path, quiet_s=1.5):
    """Best-effort: (hits, methods_used, notes, blind). Any hit means: do not touch the file.
    blind = number of processes /proc would not let us inspect (0 off-Linux)."""
    paths = [path] + [path + s for s in ALL_COMPANIONS]
    hits, methods, notes, blind = [], [], [], 0
    r = _proc_scan(paths)
    if r is not None:
        methods.append("proc")
        hits += r[0]
        blind = r[1]
        if r[1]:
            notes.append("%d processes could not be inspected (permissions)" % r[1])
        if _proc_hidden():
            blind += 1
            notes.append("/proc is mounted hidepid=2/4: other users' processes are invisible")
    r = _win_exclusive(paths)
    if r is not None:
        methods.append("win-exclusive-open")
        hits += r
    r = _psutil_scan()
    if r is not None:
        methods.append("psutil")
        hits += r
    if quiet_s > 0:
        s0 = os.stat(path)
        time.sleep(quiet_s)
        s1 = os.stat(path)
        methods.append("quiescence")
        if (s0.st_size, s0.st_mtime_ns) != (s1.st_size, s1.st_mtime_ns):
            hits.append("%s changed during a %.1fs quiet window" % (path, quiet_s))
    return list(dict.fromkeys(hits)), methods, notes, blind


def detection_gate(methods, blind, assume_down):
    """None when the in-use scan can be trusted; else the refusal text (fail CLOSED)."""
    if assume_down:
        return None
    if not (set(methods) - {"quiescence"}):
        return ("no in-use detection method works here (%s); pass --assume-down "
                "only if you KNOW she is down" % ",".join(methods))
    if blind:
        return ("%d processes could not be inspected (unreadable /proc/<pid>/fd and maps, "
                "or hidden by /proc hidepid; counted as 1), so she could be running as one of "
                "them. Refusing. "
                "--assume-down is ONLY for when she is KNOWN to be down." % blind)
    return None


# ---------------------------------------------------------------- layout

def read_layout(path):
    with open(path, "rb") as f:
        hdr = f.read(HEADER_SIZE)
    if len(hdr) < HEADER_SIZE:
        raise GrowRefused("file shorter than a header")
    (magic, ver, ncount, ecount, soff, eoff, sused, ncap, ecap) = HEADER_STRUCT.unpack_from(hdr, 0)
    if magic != MAGIC:
        raise GrowRefused("bad magic %r" % magic)
    if ver != 2:
        raise GrowRefused("version %d; only v2 (64-byte nodes, 24-byte edges) is supported" % ver)
    if soff != HEADER_SIZE + ncap * NODE_SIZE:
        raise GrowRefused("string_offset %d != 4096 + node_capacity*64 (%d): unknown layout"
                          % (soff, HEADER_SIZE + ncap * NODE_SIZE))
    if eoff < soff:
        raise GrowRefused("edge_offset < string_offset")
    size = os.path.getsize(path)
    if size != eoff + ecap * EDGE_SIZE:
        raise GrowRefused("file size %d != edge_offset + edge_capacity*24 (%d): unknown layout"
                          % (size, eoff + ecap * EDGE_SIZE))
    if ncount > ncap or ecount > ecap:
        raise GrowRefused("counts exceed capacities")
    return dict(hdr=hdr, ver=ver, ncount=ncount, ecount=ecount, soff=soff, eoff=eoff,
                sused=sused, ncap=ncap, ecap=ecap, arena=eoff - soff, size=size)


def plan(old, new_ncap, new_ecap):
    nsoff = HEADER_SIZE + new_ncap * NODE_SIZE
    neoff = nsoff + old["arena"]
    return dict(ncap=new_ncap, ecap=new_ecap, soff=nsoff, eoff=neoff,
                size=neoff + new_ecap * EDGE_SIZE)


def _copy(src, dst, src_off, dst_off, n):
    src.seek(src_off)
    dst.seek(dst_off)
    left = n
    while left:
        b = src.read(min(CHUNK, left))
        if not b:
            raise IOError("short read at %d" % (src_off + n - left))
        dst.write(b)
        left -= len(b)


def _zero(dst, off, n):
    dst.seek(off)
    z = b"\x00" * min(CHUNK, max(1, n))
    left = n
    while left:
        k = min(len(z), left)
        dst.write(z[:k])
        left -= k


def _same(fa, fb, off_a, off_b, n):
    fa.seek(off_a)
    fb.seek(off_b)
    left = n
    while left:
        k = min(CHUNK, left)
        if fa.read(k) != fb.read(k):
            return False
        left -= k
    return True


def _is_zero(f, off, n):
    f.seek(off)
    left = n
    while left:
        k = min(CHUNK, left)
        b = f.read(k)
        if len(b) != k or b.count(0) != k:
            return False
        left -= k
    return True


def new_header(old, new):
    h = bytearray(old["hdr"])
    HEADER_STRUCT.pack_into(h, 0, MAGIC, old["ver"], old["ncount"], old["ecount"],
                            new["soff"], new["eoff"], old["sused"], new["ncap"], new["ecap"])
    return bytes(h)


def verify(path, tmp, old, new):
    """Re-read both files from disk. Returns a list of failures (empty = good)."""
    bad = []
    if os.path.getsize(tmp) != new["size"]:
        bad.append("tmp size %d != %d" % (os.path.getsize(tmp), new["size"]))
        return bad
    with open(path, "rb") as fo, open(tmp, "rb") as fn:
        if fn.read(HEADER_SIZE) != new_header(old, new):
            bad.append("header")
        nodes = old["ncap"] * NODE_SIZE
        if not _same(fo, fn, HEADER_SIZE, HEADER_SIZE, nodes):
            bad.append("node records not byte-identical")
        if not _is_zero(fn, HEADER_SIZE + nodes, (new["ncap"] - old["ncap"]) * NODE_SIZE):
            bad.append("new node slots not zero")
        if not _same(fo, fn, old["soff"], new["soff"], old["arena"]):
            bad.append("string arena not byte-identical")
        edges = old["ecap"] * EDGE_SIZE
        if not _same(fo, fn, old["eoff"], new["eoff"], edges):
            bad.append("edge records not byte-identical")
        if not _is_zero(fn, new["eoff"] + edges, (new["ecap"] - old["ecap"]) * EDGE_SIZE):
            bad.append("new edge slots not zero")
    return bad


def _src_ident(path):
    st = os.stat(path)
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)


def _sha256(path):
    """Full-file SHA-256. Full, not sampled: her writes are scattered single-record updates
    a sample would miss, and the tool already reads the whole file twice (copy + verify)."""
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def final_check(path, ident0, sha0, assume_down):
    """Run IMMEDIATELY before os.replace. None = safe to swap; else the refusal text.
    Slowest first, cheapest last, so the stat is the closest thing to the swap."""
    if _sha256(path) != sha0:
        return "source content changed since the copy (full SHA-256 differs)."
    hits, methods, _notes, blind = in_use_report(path, quiet_s=0)
    if hits:
        return "file looks IN USE right before the swap:\n  " + "\n  ".join(hits)
    gate = detection_gate(methods, blind, assume_down)
    if gate:
        return gate
    if _src_ident(path) != ident0:
        return "source (size, mtime or inode) changed right before the swap."
    return None


def _fsync_dir(d):
    if os.name == "nt":
        return
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def grow(path, new_ncap, new_ecap=None, apply=False, assume_down=False, quiet_s=1.5,
         stamp=None):
    """Grow `path` to new_ncap node slots (and new_ecap edge slots, default unchanged).

    Returns a dict report. Raises GrowRefused when it will not proceed.
    """
    path = os.path.abspath(path)
    if apply and os.environ.get("AKASHIC_CORTEX_GROW", "0") != "1":
        raise GrowRefused("--apply needs AKASHIC_CORTEX_GROW=1 in the environment")
    old = read_layout(path)
    new_ecap = old["ecap"] if new_ecap is None else int(new_ecap)
    new_ncap = int(new_ncap)
    if new_ncap <= old["ncap"]:
        raise GrowRefused("new node capacity %d must exceed current %d" % (new_ncap, old["ncap"]))
    if new_ecap < old["ecap"]:
        raise GrowRefused("edge capacity can only grow (%d < %d)" % (new_ecap, old["ecap"]))
    if new_ncap > 0xFFFFFFFF or new_ecap > 0xFFFFFFFF:
        raise GrowRefused("capacity does not fit the header's uint32")
    new = plan(old, new_ncap, new_ecap)
    report = dict(old=dict((k, old[k]) for k in ("ncount", "ncap", "ecount", "ecap", "arena", "size")),
                  new=new, applied=False)
    if not apply:
        return report

    d = os.path.dirname(path)
    free = shutil.disk_usage(d).free
    need = new["size"] + old["size"] + max(0, new["ncap"] - old["ncap"]) * EMB_BYTES + (64 << 20)
    if free < need:
        raise GrowRefused("not enough disk: need ~%d bytes, %d free" % (need, free))

    lock = path + ".grow.lock"
    tmp = path + ".grow.tmp"
    stamp = stamp or time.strftime("%Y%m%d_%H%M%S")
    _step("lock")
    try:
        lfd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise GrowRefused("%s exists: another grow is running or one crashed. "
                          "Inspect, then delete it." % lock)
    os.write(lfd, str(os.getpid()).encode())
    os.close(lfd)
    swapped = False
    try:
        _step("in_use")
        hits, methods, notes, blind = in_use_report(path, quiet_s=quiet_s)
        report["in_use_methods"] = methods
        report["in_use_notes"] = notes
        if hits:
            raise GrowRefused("file looks IN USE -- shut her down first:\n  " + "\n  ".join(hits))
        gate = detection_gate(methods, blind, assume_down)
        if gate:
            raise GrowRefused(gate)
        _step("read_old")
        ident0 = _src_ident(path)
        sha0 = _sha256(path)
        old2 = read_layout(path)
        if old2["hdr"] != old["hdr"]:
            raise GrowRefused("header changed since planning")
        _step("tmp_create")
        if os.path.exists(tmp):
            os.remove(tmp)                      # a leftover from a crashed run; never live data
        with open(path, "rb") as fo, open(tmp, "wb") as fn:
            fn.write(b"\x00" * HEADER_SIZE)     # magic stays zero until write_header
            _step("copy_nodes")
            _copy(fo, fn, HEADER_SIZE, HEADER_SIZE, old["ncap"] * NODE_SIZE)
            _step("zero_new_nodes")
            _zero(fn, HEADER_SIZE + old["ncap"] * NODE_SIZE, (new["ncap"] - old["ncap"]) * NODE_SIZE)
            _step("copy_strings")
            _copy(fo, fn, old["soff"], new["soff"], old["arena"])
            _step("copy_edges")
            _copy(fo, fn, old["eoff"], new["eoff"], old["ecap"] * EDGE_SIZE)
            _step("zero_new_edges")
            _zero(fn, new["eoff"] + old["ecap"] * EDGE_SIZE, (new["ecap"] - old["ecap"]) * EDGE_SIZE)
            fn.flush()
            os.fsync(fn.fileno())
            _step("write_header")
            fn.seek(0)
            fn.write(new_header(old, new))
            fn.flush()
            _step("fsync_tmp")
            os.fsync(fn.fileno())
        _step("verify")
        bad = verify(path, tmp, old, new)
        if bad:
            raise GrowRefused("verification FAILED, nothing swapped: " + "; ".join(bad))
        _step("recheck_source")
        if _src_ident(path) != ident0:
            raise GrowRefused("source changed while copying -- someone has it open. Nothing swapped.")
        _step("backup")
        bak = "%s.pre_grow.%s" % (path, stamp)
        if os.path.exists(bak):
            raise GrowRefused("%s already exists" % bak)
        try:
            os.link(path, bak)
        except OSError:
            shutil.copy2(path, bak)
            with open(bak, "rb+") as bf:
                os.fsync(bf.fileno())
        report["backup"] = bak
        _step("move_companions")
        moved = []
        for suf in DERIVED_COMPANIONS:
            c = path + suf
            if os.path.exists(c):
                os.replace(c, "%s.pre_grow.%s" % (c, stamp))
                moved.append(c)
        report["companions_moved_aside"] = moved
        _fsync_dir(d)                           # backup link + companion renames durable
        _step("final_check")
        why = final_check(path, ident0, sha0, assume_down)
        if why:
            for c in moved:                     # undo: companions back where they were
                aside = "%s.pre_grow.%s" % (c, stamp)
                if not os.path.exists(c) and os.path.exists(aside):
                    os.replace(aside, c)
            try:
                if os.path.samefile(bak, path):
                    os.remove(bak)              # only a hard-link alias; a real copy is kept
            except OSError:
                pass
            raise GrowRefused(why + " Nothing swapped; the live file is untouched.")
        _step("replace")
        os.replace(tmp, path)
        swapped = True
        report["applied"] = True
        _step("dirsync")
        _fsync_dir(d)
        _step("extend_embeddings")
        emb = path + ".embeddings"
        if os.path.exists(emb):
            want = new["ncap"] * EMB_BYTES
            if os.path.getsize(emb) < want:
                with open(emb, "r+b") as ef:
                    ef.truncate(want)           # zero tail; existing vectors untouched
                    os.fsync(ef.fileno())
        _step("unlock")
    finally:
        if not swapped and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        try:
            os.remove(lock)
        except OSError:
            pass
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Offline, slot-preserving cortex growth (W6).")
    ap.add_argument("--manifold", required=True)
    ap.add_argument("--nodes", type=int, required=True, help="new node capacity")
    ap.add_argument("--edges", type=int, default=None, help="new edge capacity (default unchanged)")
    ap.add_argument("--apply", action="store_true", help="write (also needs AKASHIC_CORTEX_GROW=1)")
    ap.add_argument("--assume-down", action="store_true",
                    help="proceed even if in-use detection is unavailable or some processes "
                         "could not be inspected. ONLY when she is KNOWN to be down")
    a = ap.parse_args(argv)
    try:
        r = grow(a.manifold, a.nodes, a.edges, apply=a.apply, assume_down=a.assume_down)
    except GrowRefused as e:
        _log("REFUSED: %s" % e)
        return 2
    o, n = r["old"], r["new"]
    _log("old: nodes %d/%d edges %d/%d arena %d B file %d B" % (
        o["ncount"], o["ncap"], o["ecount"], o["ecap"], o["arena"], o["size"]))
    _log("new: nodes %d/%d edges %d/%d file %d B (+%d B; +%d B .embeddings)" % (
        o["ncount"], n["ncap"], o["ecount"], n["ecap"], n["size"], n["size"] - o["size"],
        (n["ncap"] - o["ncap"]) * EMB_BYTES))
    _log("APPLIED. backup: %s  companions moved aside: %s" % (r.get("backup"), r.get(
        "companions_moved_aside")) if r["applied"] else "DRY RUN -- nothing written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
