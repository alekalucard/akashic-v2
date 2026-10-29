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
        holder = subprocess.Popen(
            [sys.executable, "-I", "-c",
             "import mmap,sys,time\nf=open(sys.argv[1],'rb')\n"
             "m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)\nf.close()\n"
             "print('ready',flush=True)\ntime.sleep(60)", p],
            stdout=subprocess.PIPE)
        try:
            self.assertEqual(holder.stdout.readline().strip(), b"ready")
            os.environ["AKASHIC_CORTEX_GROW"] = "1"
            with self.assertRaises(G.GrowRefused) as cm:
                G.grow(p, NEW_CAP, apply=True, quiet_s=0)
            self.assertIn("IN USE", str(cm.exception))
        finally:
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
