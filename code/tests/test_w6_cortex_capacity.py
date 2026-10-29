# -*- coding: utf-8 -*-
"""W6 tests: offline cortex growth + PROTECT_EGO eviction guard.

SYNTHETIC manifolds only (1,000 slots), in a temp dir. Never opens a real *.manifold.

Which code is under test is chosen by environment, so the same suite runs against the
original tree (CONTROL), the fix, and each MUTANT (see w6_mutants.py):
    W6_MM_PATH      path to the manifold_memory.py to load (default: this tree's)
    W6_GROW_PATH    path to grow_cortex.py (default: this tree's tools/grow_cortex.py)
    W6_GROWER       "new" (grow_cortex.grow, default) or "legacy_v2"
                    (scripts/expand_manifold_v2.py, the existing tool, re-pointed at temp paths)
"""
import hashlib
import importlib.util
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
MM_PATH = os.environ.get("W6_MM_PATH", os.path.join(CODE, "infrastructure", "manifold_memory.py"))
GROW_PATH = os.environ.get("W6_GROW_PATH", os.path.join(CODE, "tools", "grow_cortex.py"))
LEGACY_V2 = os.path.join(CODE, "scripts", "expand_manifold_v2.py")
GROWER = os.environ.get("W6_GROWER", "new")

CAP = 1000
ECAP = 3000
NEW_CAP = 1500


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MM = _load("w6_manifold_memory", MM_PATH)
try:
    G = _load("w6_grow_cortex", GROW_PATH)
except Exception:                       # original tree: the tool does not exist
    G = None


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


PROBES = ["ace", "sourpatches", "person:ace", "emotion", "joy", "who_i_am",
          "connection", "feeling", "concept:logic", "place:home"]   # legacy_v2 verifies these


def build(d, full=True, name="cortex.manifold"):
    """A synthetic, FULL cortex with every feature the format has: inline names, sidecar
    names (arena overflow), snippets, all regions/tracers, reserved bytes, a frozen node,
    edges, .csr/.keys companions and an .embeddings file."""
    p = os.path.join(d, name)
    m = MM.ManifoldMemory(p, node_capacity=CAP, edge_capacity=ECAP)
    rnd = random.Random(6)
    keys = PROBES + ["w6_concept_%04d" % i for i in range(CAP - len(PROBES))]
    if not full:
        keys = keys[:CAP // 2]
    for i, k in enumerate(keys):
        snip = ("snippet %d " % i) * 60 if i < 90 else ""          # fills the 64 KB arena
        m.upsert_node(k, activation=0.5 + (i % 17) * 0.1, count=i % 5 + 1,
                      coord_str="%03d.%03d.%03d" % (i % 9, i % 7, i % 5), snippet=snip,
                      node_type=i % 6, region=[1, 0, 2, 3, 4][i % 5],
                      tracer_id=[0, 1, 2, 3, 6, 7, 8, 12][i % 8], parent_slot=i // 3)
    for s in range(0, len(keys), 7):
        m.write_reserved_bytes(s, struct.pack("<4f", s * 0.5, 1.25, -2.0, 3.0))
    rec = list(m._read_node(5))
    rec[9] = MM.FLAG_FROZEN
    m._write_node(5, *rec, preserve_reserved=True)
    for _ in range(2000):
        a, b = rnd.sample(keys, 2)
        m.link(a, b, weight=rnd.random() * 0.9 + 0.05, rel_type=rnd.randrange(28),
               tracer_id=rnd.choice([1, 2, 7]))
    for s in range(0, 40):
        m.write_embedding(s, bytes([s % 251]) * MM.ManifoldMemory.EMBEDDING_BYTES_PER_NODE)
    m.close()
    m = MM.ManifoldMemory(p)          # re-open so .csr/.keys are built from disk
    m.close()
    return p, keys


def snapshot(p, keys):
    m = MM.ManifoldMemory(p)
    try:
        out = dict(
            index=dict(m._key_index),
            nodes={k: m.get_node(k) for k in keys},
            nb={k: sorted(m.get_neighbors(k, limit=10000)) for k in keys},
            res={s: m.read_reserved_bytes(s) for s in range(CAP) if m._read_node(s)[1]},
            raw={s: bytes(m._mm[m._node_offset(s):m._node_offset(s) + 64]) for s in range(CAP)},
            sidecar=sum(1 for s in range(CAP)
                        if m._read_node(s)[1] and m._read_node(s)[0] >= m._string_limit()),
            nc=m._node_count, ec=m._edge_count, cap=m._node_capacity, ecap=m._edge_capacity,
            emb={s: m.read_embedding(s) is not None for s in range(0, 40)},
        )
    finally:
        m.close()
    return out


def run_grow(p, new_cap=NEW_CAP, **kw):
    if GROWER == "legacy_v2":
        L = _load("w6_legacy_v2_%d" % time.time_ns(), LEGACY_V2)
        L.OLD, L.NEW, L.BAK = p, p + ".expanded", p + ".pre_expand"
        L.NEW_NODE_CAP, L.NEW_EDGE_CAP = new_cap, ECAP
        L.STRING_BYTES_PER_NODE = 4096       # its default (128) refuses on this data; give it room
        argv = sys.argv
        sys.argv = ["expand_manifold_v2.py", "--apply"]
        try:
            L.main()
        finally:
            sys.argv = argv
        return {"applied": True}
    if G is None:
        raise AssertionError("tools/grow_cortex.py does not exist in this tree")
    os.environ["AKASHIC_CORTEX_GROW"] = "1"
    try:
        return G.grow(p, new_cap, apply=True, quiet_s=0.05, **kw)
    finally:
        os.environ.pop("AKASHIC_CORTEX_GROW", None)


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="w6_")
        os.environ.pop("AKASHIC_PROTECT_EGO", None)
        if G is not None:
            G._FAULT = None
            G._FAULT_MODE = "raise"

    def tearDown(self):
        os.environ.pop("AKASHIC_PROTECT_EGO", None)
        shutil.rmtree(self.d, ignore_errors=True)


class TestGrow(Base):
    def test_grow_preserves_every_node_and_index(self):
        p, keys = build(self.d)
        before = snapshot(p, keys)
        self.assertEqual(before["nc"], CAP)
        self.assertGreater(before["sidecar"], 100, "synthetic data must exercise the .names sidecar")
        run_grow(p)
        after = snapshot(p, keys)
        self.assertEqual(after["cap"], NEW_CAP)
        self.assertEqual(after["ecap"], ECAP)
        self.assertEqual((after["nc"], after["ec"]), (before["nc"], before["ec"]))
        self.assertEqual(after["raw"], before["raw"], "node records not byte-for-byte")
        self.assertEqual(after["index"], before["index"], "key lookup moved")
        self.assertEqual(after["nodes"], before["nodes"], "a node's fields/snippet changed")
        self.assertEqual(after["nb"], before["nb"], "neighbours changed")
        self.assertEqual(after["res"], before["res"], "reserved (affect) bytes changed")
        self.assertEqual(after["sidecar"], before["sidecar"], "sidecar names not resolving")
        self.assertEqual(after["emb"], before["emb"])

    def test_after_grow_new_node_evicts_nothing(self):
        p, keys = build(self.d)
        run_grow(p)
        m = MM.ManifoldMemory(p)
        try:
            for i in range(50):
                s = m.upsert_node("w6_new_%d" % i, activation=0.1)
                self.assertGreaterEqual(s, CAP)
            for k in keys:
                self.assertIn(k, m._key_index, "an old memory was evicted")
            self.assertEqual(m._node_count, CAP + 50)
        finally:
            m.close()

    def test_companions_rebuilt_for_new_capacity(self):
        p, keys = build(self.d)
        run_grow(p)
        MM.ManifoldMemory(p).close()
        for suf, magic in ((".csr", b"CSRA"), (".keys", b"KEYS")):
            with open(p + suf, "rb") as f:
                h = struct.unpack("<4sIIII", f.read(20))
            self.assertEqual(h[0], magic)
            self.assertEqual(h[1], NEW_CAP, "%s still encodes the old capacity" % suf)
        self.assertGreaterEqual(os.path.getsize(p + ".embeddings"),
                                NEW_CAP * MM.ManifoldMemory.EMBEDDING_BYTES_PER_NODE)

    def test_refuses_without_switch_and_when_shrinking(self):
        self.assertIsNotNone(G, "tools/grow_cortex.py missing")
        p, keys = build(self.d)
        h0 = sha(p)
        os.environ.pop("AKASHIC_CORTEX_GROW", None)
        with self.assertRaises(G.GrowRefused):
            G.grow(p, NEW_CAP, apply=True, quiet_s=0)
        os.environ["AKASHIC_CORTEX_GROW"] = "1"
        try:
            with self.assertRaises(G.GrowRefused):
                G.grow(p, CAP, apply=True, quiet_s=0)
        finally:
            os.environ.pop("AKASHIC_CORTEX_GROW", None)
        r = G.grow(p, NEW_CAP, apply=False)          # dry run writes nothing
        self.assertFalse(r["applied"])
        self.assertEqual(sha(p), h0)

    def test_refuses_while_another_process_has_it_mapped(self):
        self.assertIsNotNone(G, "tools/grow_cortex.py missing")
        if not os.path.isdir("/proc/self/fd") and os.name != "nt":
            self.skipTest("no in-use detection on this OS")
        p, keys = build(self.d)
        h0 = sha(p)
        reached, step0 = [], G._step
        holder = subprocess.Popen(
            [sys.executable, "-I", "-c",
             "import mmap,sys,time\nf=open(sys.argv[1],'rb')\n"
             "m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)\nf.close()\n"
             "print('ready',flush=True)\ntime.sleep(60)", p],
            stdout=subprocess.PIPE)
        try:
            self.assertEqual(holder.stdout.readline().strip(), b"ready")
            os.environ["AKASHIC_CORTEX_GROW"] = "1"
            G._step = lambda name: (reached.append(name), step0(name))
            with self.assertRaises(G.GrowRefused) as cm:
                G.grow(p, NEW_CAP, apply=True, quiet_s=0)
            self.assertIn("IN USE", str(cm.exception))
            # refused at the FIRST scan, before anything is copied (not only by the pre-swap backstop)
            self.assertIn("shut her down first", str(cm.exception))
            self.assertNotIn("tmp_create", reached)
        finally:
            G._step = step0
            os.environ.pop("AKASHIC_CORTEX_GROW", None)
            holder.kill()
            holder.wait()
        self.assertEqual(sha(p), h0)
        self.assertFalse(os.path.exists(p + ".grow.lock"))


class TestCrash(Base):
    """Raise (and, separately, hard-exit the process) at every step of the grow."""

    def _files(self, p):
        return {s: sha(p + s) for s in ("", ".csr", ".keys", ".embeddings", ".names")
                if os.path.exists(p + s)}

    def _check(self, p, keys, h0, step, killed):
        steps = G.STEPS
        swapped = steps.index(step) > steps.index("replace")
        if not swapped:
            self.assertEqual(sha(p), h0[""], "live file changed after crash at %s" % step)
        else:
            baks = [f for f in os.listdir(self.d) if f.startswith("cortex.manifold.pre_grow.")]
            self.assertEqual(len(baks), 1, step)
            self.assertEqual(sha(os.path.join(self.d, baks[0])), h0[""],
                             "backup is not the old bytes (crash at %s)" % step)
        self.assertEqual(sha(p + ".names"), h0[".names"])
        if not killed:
            self.assertFalse(os.path.exists(p + ".grow.tmp"), step)
            self.assertFalse(os.path.exists(p + ".grow.lock"), step)
        m = MM.ManifoldMemory(p)                         # whatever is live must open intact
        try:
            self.assertEqual(m._node_capacity, NEW_CAP if swapped else CAP, step)
            for k in keys:
                self.assertIn(k, m._key_index, "%s lost after crash at %s" % (k, step))
        finally:
            m.close()

    def _one(self, step, mode):
        sub = os.path.join(self.d, "%s_%s" % (step, mode))
        os.mkdir(sub)
        self.d, outer = sub, self.d
        try:
            p, keys = build(sub)
            h0 = self._files(p)
            if mode == "raise":
                G._FAULT = step
                with self.assertRaises(G.InjectedCrash):
                    run_grow(p)
                G._FAULT = None
            else:
                code = ("import importlib.util,os,sys\n"
                        "s=importlib.util.spec_from_file_location('g',sys.argv[1]);g=importlib.util.module_from_spec(s);s.loader.exec_module(g)\n"
                        "g._FAULT=sys.argv[3];g._FAULT_MODE='exit'\n"
                        "os.environ['AKASHIC_CORTEX_GROW']='1'\n"
                        "g.grow(sys.argv[2],%d,apply=True,quiet_s=0.05)\n"
                        "sys.exit(0)\n" % NEW_CAP)
                rc = subprocess.call([sys.executable, "-I", "-c", code, GROW_PATH, p, step])
                self.assertEqual(rc, 9, "child did not die at %s" % step)
            self._check(p, keys, h0, step, killed=(mode == "exit"))
        finally:
            self.d = outer

    def test_crash_at_every_step_raise(self):
        self.assertIsNotNone(G, "tools/grow_cortex.py missing")
        for step in G.STEPS:
            with self.subTest(step=step):
                self._one(step, "raise")

    def test_crash_at_every_step_hard_exit(self):
        self.assertIsNotNone(G, "tools/grow_cortex.py missing")
        for step in G.STEPS:
            with self.subTest(step=step):
                self._one(step, "exit")


HOLDER_PY_MMAP = ("import mmap,sys,time\nf=open(sys.argv[1],'rb')\n"
                  "m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)\nf.close()\n"
                  "print('ready',flush=True)\ntime.sleep(60)")
# A mapping with NO open fd: CPython's mmap keeps a dup'd fd, so map through libc and
# close the fd; only /proc/<pid>/maps can see this holder.
HOLDER_MAPS_ONLY = ("import ctypes,os,sys,time\nlibc=ctypes.CDLL(None,use_errno=True)\n"
                    "libc.mmap.restype=ctypes.c_void_p\n"
                    "libc.mmap.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_long]\n"
                    "fd=os.open(sys.argv[1],os.O_RDONLY)\na=libc.mmap(None,4096,1,1,fd,0)\n"
                    "assert a not in (None,ctypes.c_void_p(-1).value)\nos.close(fd)\n"
                    "print('ready',flush=True)\ntime.sleep(60)")


class TestSafetyChecks(Base):
    """Fix round after REVIEW_W6 (F1, F2, F3): each test kills a mutant that survived."""

    def setUp(self):
        super().setUp()
        self.assertIsNotNone(G, "tools/grow_cortex.py missing")
        self._saved = {n: getattr(G, n) for n in ("_step", "_proc_scan", "_win_exclusive",
                                                  "_psutil_scan", "_proc_hidden")
                       if hasattr(G, n)}
        self._holders = []

    def tearDown(self):
        for n, v in self._saved.items():
            setattr(G, n, v)
        for h in self._holders:
            h.kill()
            h.wait()
        os.environ.pop("AKASHIC_CORTEX_GROW", None)
        super().tearDown()

    def _hook(self, at, fn):
        orig = self._saved["_step"]

        def step(name):
            if name == at:
                fn()
            orig(name)
        G._step = step

    def _holder(self, code, p):
        h = subprocess.Popen([sys.executable, "-I", "-c", code, p], stdout=subprocess.PIPE)
        self._holders.append(h)
        self.assertEqual(h.stdout.readline().strip(), b"ready")
        return h

    def _poke(self, p, keep_mtime=False):
        """Change one byte inside a node record (same size)."""
        st = os.stat(p)
        with open(p, "r+b") as f:
            f.seek(G.HEADER_SIZE + 64 * 3 + 8)
            b = f.read(1)
            f.seek(G.HEADER_SIZE + 64 * 3 + 8)
            f.write(bytes([b[0] ^ 0xFF]))
        if keep_mtime:
            os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))

    def _untouched_tree(self, p, h_live, h_csr):
        self.assertEqual(sha(p), h_live, "live file changed")
        self.assertEqual(sha(p + ".csr"), h_csr, ".csr not back in place")
        self.assertFalse(os.path.exists(p + ".grow.tmp"), "temp left behind")
        self.assertFalse(os.path.exists(p + ".grow.lock"), "lock left behind")
        left = [f for f in os.listdir(self.d) if ".pre_grow." in f]
        self.assertEqual(left, [], "backup link / moved companions left behind: %s" % left)
        with open(p, "rb") as f:
            self.assertEqual(G.HEADER_STRUCT.unpack(f.read(48))[7], CAP)   # node_capacity

    def test_verify_failure_refuses(self):                       # kills R2
        p, keys = build(self.d)
        h0 = sha(p)

        def corrupt():
            with open(p + ".grow.tmp", "r+b") as f:
                f.seek(G.HEADER_SIZE + 64 * 10 + 4)
                f.write(b"\xEE")
        self._hook("verify", corrupt)
        with self.assertRaises(G.GrowRefused) as cm:
            run_grow(p)
        self.assertIn("verification FAILED", str(cm.exception))
        self.assertEqual(sha(p), h0)
        self.assertFalse(os.path.exists(p + ".grow.tmp"))

    def test_source_changed_after_verify_refuses_before_touching_companions(self):  # kills R6
        p, keys = build(self.d)
        h_csr = sha(p + ".csr")
        self._hook("recheck_source", lambda: self._poke(p))
        with self.assertRaises(G.GrowRefused) as cm:
            run_grow(p)
        self.assertIn("source changed while copying", str(cm.exception))
        h_live = sha(p)                                         # our poke, not a swap
        self._untouched_tree(p, h_live, h_csr)

    def test_content_change_with_same_mtime_refused_right_before_swap(self):  # F2: hash
        p, keys = build(self.d)
        h_csr = sha(p + ".csr")
        self._hook("move_companions", lambda: self._poke(p, keep_mtime=True))
        with self.assertRaises(G.GrowRefused) as cm:
            run_grow(p)
        self.assertIn("SHA-256", str(cm.exception))
        self._untouched_tree(p, sha(p), h_csr)

    def test_holder_that_maps_after_first_scan_refused_before_swap(self):  # F2: rescan
        if not os.path.isdir("/proc/self/fd") and os.name != "nt":
            self.skipTest("no in-use detection on this OS")
        p, keys = build(self.d)
        h0, h_csr = sha(p), sha(p + ".csr")
        self._hook("move_companions", lambda: self._holder(HOLDER_PY_MMAP, p))
        with self.assertRaises(G.GrowRefused) as cm:
            run_grow(p)
        self.assertIn("IN USE right before the swap", str(cm.exception))
        self._untouched_tree(p, h0, h_csr)

    def test_maps_only_holder_detected(self):                    # kills R10
        if not os.path.isdir("/proc/self/fd"):
            self.skipTest("Linux /proc only")
        p, keys = build(self.d)
        h0 = sha(p)
        h = self._holder(HOLDER_MAPS_ONLY, p)
        ino = os.stat(p).st_ino
        fds = os.listdir("/proc/%d/fd" % h.pid)
        self.assertFalse(any(os.stat("/proc/%d/fd/%s" % (h.pid, x)).st_ino == ino for x in fds
                             if os.path.exists("/proc/%d/fd/%s" % (h.pid, x))),
                         "holder still has an fd: the test would not exercise the maps scan")
        with self.assertRaises(G.GrowRefused) as cm:
            run_grow(p)
        self.assertIn("mmap'd", str(cm.exception))
        self.assertEqual(sha(p), h0)

    def test_blind_proc_fails_closed_unless_assume_down(self):  # F1
        G._psutil_scan = lambda: None
        G._win_exclusive = lambda paths: None
        for label, scans in (("blind at first scan", [([], 42)]),
                             ("blind only at the pre-swap scan", [([], 0), ([], 42)])):
            with self.subTest(label):
                sub = os.path.join(self.d, label.replace(" ", "_"))
                os.mkdir(sub)
                p, keys = build(sub)
                h0 = sha(p)
                seq = list(scans)
                G._proc_scan = lambda paths: seq.pop(0) if len(seq) > 1 else seq[0]
                with self.assertRaises(G.GrowRefused) as cm:
                    run_grow(p)
                msg = str(cm.exception)
                self.assertIn("42 processes could not be inspected", msg)
                self.assertIn("KNOWN to be down", msg)
                self.assertEqual(sha(p), h0)
                self.assertEqual([f for f in os.listdir(sub) if ".pre_grow." in f], [])
                seq[:] = list(scans)
                self.assertTrue(run_grow(p, assume_down=True)["applied"])

    def test_hidepid_hidden_processes_fail_closed(self):          # F1: invisible pids
        G._psutil_scan = lambda: None
        G._win_exclusive = lambda paths: None
        G._proc_scan = lambda paths: ([], 0)
        G._proc_hidden = lambda: True
        p, keys = build(self.d)
        h0 = sha(p)
        with self.assertRaises(G.GrowRefused) as cm:
            run_grow(p)
        self.assertIn("hidepid", str(cm.exception))
        self.assertEqual(sha(p), h0)

    def test_no_detection_method_refuses_unless_assume_down(self):  # kills R18
        G._proc_scan = lambda paths: None
        G._win_exclusive = lambda paths: None
        G._psutil_scan = lambda: None
        p, keys = build(self.d)
        h0 = sha(p)
        with self.assertRaises(G.GrowRefused) as cm:
            run_grow(p)
        self.assertIn("no in-use detection method", str(cm.exception))
        self.assertEqual(sha(p), h0)
        self.assertTrue(run_grow(p, assume_down=True)["applied"])

    def test_second_grower_refused_by_lock(self):                # kills R13
        p, keys = build(self.d)
        h0 = sha(p)
        with open(p + ".grow.lock", "wb") as f:
            f.write(b"99999")
        with self.assertRaises(G.GrowRefused) as cm:
            run_grow(p)
        self.assertIn(".grow.lock", str(cm.exception))
        self.assertEqual(sha(p), h0)
        with open(p + ".grow.lock", "rb") as f:
            self.assertEqual(f.read(), b"99999", "another grower's lock was taken over")

    def test_fsync_tmp_and_dir_before_replace(self):            # kills R1
        import stat as _stat
        p, keys = build(self.d)
        tmp = p + ".grow.tmp"
        dino = os.stat(self.d).st_ino
        ev = []
        real_fsync, real_replace = os.fsync, os.replace

        def fsync(fd):
            st = os.fstat(fd)
            if _stat.S_ISDIR(st.st_mode) and st.st_ino == dino:
                ev.append("fsync_dir")
            elif os.path.exists(tmp) and os.stat(tmp).st_ino == st.st_ino:
                with open(tmp, "rb") as f:
                    ev.append("fsync_tmp_final" if f.read(4) == G.MAGIC else "fsync_tmp")
            return real_fsync(fd)

        def replace(a, b):
            if os.path.abspath(a) == os.path.abspath(tmp):
                ev.append("replace")
            return real_replace(a, b)
        os.fsync, os.replace = fsync, replace
        try:
            run_grow(p)
        finally:
            os.fsync, os.replace = real_fsync, real_replace
        self.assertIn("replace", ev)
        before, after = ev[:ev.index("replace")], ev[ev.index("replace") + 1:]
        self.assertIn("fsync_tmp_final", before, "temp (with its header) not fsynced before the swap: %s" % ev)
        self.assertIn("fsync_dir", before, "directory not fsynced before the swap: %s" % ev)
        self.assertIn("fsync_dir", after, "directory not fsynced after the swap: %s" % ev)

    def test_header_tail_copied_verbatim(self):                   # kills R11
        p, keys = build(self.d)
        with open(p, "rb") as f:
            tail0 = f.read(G.HEADER_SIZE)[48:]
        self.assertTrue(any(tail0), "synthetic header tail is all zero: test would be blind")
        run_grow(p)
        with open(p, "rb") as f:
            self.assertEqual(f.read(G.HEADER_SIZE)[48:], tail0)


class TestProtectEgo(Base):
    def _full(self, regions_tracers, coldest):
        """Full 1000-slot cortex; slot `coldest` has the lowest activation."""
        p = os.path.join(self.d, "ego.manifold")
        m = MM.ManifoldMemory(p, node_capacity=CAP, edge_capacity=ECAP)
        for i in range(CAP):
            reg, tr = regions_tracers(i)
            m.upsert_node("k%04d" % i, activation=(0.01 if i == coldest else 1.0 + i * 0.001),
                          region=reg, tracer_id=tr)
        return m

    def test_off_by_default_matches_original(self):
        m = self._full(lambda i: (MM.REGION_EGO if i == 3 else 1, 0), coldest=3)
        try:
            s = m.upsert_node("newcomer")
            self.assertEqual(s, 3)                       # unchanged behaviour: coldest goes
            self.assertNotIn("k0003", m._key_index)
        finally:
            m.close()

    def test_ego_region_node_survives(self):
        os.environ["AKASHIC_PROTECT_EGO"] = "1"
        m = self._full(lambda i: (MM.REGION_EGO if i == 3 else 1, 0), coldest=3)
        try:
            s = m.upsert_node("newcomer")
            self.assertIn("k0003", m._key_index, "ego node was deleted")
            self.assertNotEqual(s, 3)
            self.assertEqual(s, 0)                       # next coldest, non-ego
        finally:
            m.close()

    def test_personal_and_seeded_tracer_survive(self):
        os.environ["AKASHIC_PROTECT_EGO"] = "1"
        for tr in (MM.TRACE_PERSONAL, MM.TRACE_SEEDED):
            with self.subTest(tracer=tr):
                m = self._full(lambda i: (1, tr if i == 3 else 2), coldest=3)
                try:
                    m.upsert_node("newcomer")
                    self.assertIn("k0003", m._key_index)
                finally:
                    m.close()
                os.remove(os.path.join(self.d, "ego.manifold"))

    def test_all_protected_deletes_nothing_and_refuses(self):
        os.environ["AKASHIC_PROTECT_EGO"] = "1"
        m = self._full(lambda i: (MM.REGION_EGO, MM.TRACE_PERSONAL), coldest=3)
        try:
            before = dict(m._key_index)
            s = m.upsert_node("newcomer")
            self.assertEqual(s, -1, "new node must be refused, not placed over a memory")
            self.assertEqual(m._key_index, before)
            self.assertNotIn("newcomer", m._key_index)
            for slot in range(CAP):
                self.assertNotEqual(m._read_node(slot)[9], MM.FLAG_DELETED)
            self.assertEqual(getattr(m, "_ego_refusals", 0), 1, "refusal not counted")
        finally:
            m.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
