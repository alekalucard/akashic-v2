"""W15 -- edge-slot double use at capacity (switch AKASHIC_EDGE_SLOT_FIX).

Synthetic manifolds in a temp dir only. Never touches a real *.manifold file.

The module under test is loaded from W15_MM_PATH (default: this repo's
code/infrastructure/manifold_memory.py). The reference ("main") copy for the
byte-identity test is loaded from W15_MAIN_PATH, or extracted with
`git show origin/main:code/infrastructure/manifold_memory.py`.

Run:  python -m unittest code/tests/test_w15_edge_slot.py -v
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time as _real_time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_MM = os.path.join(REPO, "code", "infrastructure", "manifold_memory.py")
SWITCH = "AKASHIC_EDGE_SLOT_FIX"

N_NODES = 64
CAP = 20          # edge capacity
K = 10            # new edges added once full


class _FakeTime:
    """Deterministic time.time(); everything else forwards to the real module."""
    def __init__(self):
        self._t = 1000.0

    def time(self):
        self._t += 0.5
        return self._t

    def __getattr__(self, name):
        return getattr(_real_time, name)


_MOD_CACHE = {}


def load_module(path, tag):
    key = (os.path.abspath(path), tag)
    if key in _MOD_CACHE:
        return _MOD_CACHE[key]
    name = "w15_mm_%s_%d" % (tag, len(_MOD_CACHE))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    mod._mlog = lambda *a, **k: None          # keep test output quiet
    _MOD_CACHE[key] = mod
    return mod


def main_module_path(tmp):
    p = os.environ.get("W15_MAIN_PATH")
    if p:
        return p
    out = subprocess.check_output(
        ["git", "-C", REPO, "show", "origin/main:code/infrastructure/manifold_memory.py"])
    p = os.path.join(tmp, "manifold_memory_main.py")
    with open(p, "wb") as f:
        f.write(out)
    return p


def key(i):
    return "n%03d" % i


FILL_PAIRS = [(i, i + 1) for i in range(CAP)]                 # 0-1, 1-2, ... 19-20
NEW_PAIRS = [(30 + i, 45 + i) for i in range(K)]              # disjoint from fill
FILL_W = [0.10 + 0.003 * ((7 * i) % CAP) for i in range(CAP)]  # distinct, all < 0.2
NEW_W = 0.9


def make_nodes(mm):
    for i in range(N_NODES):
        mm.upsert_node(key(i))


def fill(mm):
    for (x, y), w in zip(FILL_PAIRS, FILL_W):
        assert mm.link(key(x), key(y), weight=w)


def add_new(mm):
    for x, y in NEW_PAIRS:
        assert mm.link(key(x), key(y), weight=NEW_W)


def record_pairs(mm, mod):
    """Ground truth straight from the edge region: set of (a,b) active."""
    s = []
    for slot in range(mm._edge_count):
        r = mm._read_edge(slot)
        if r[4] & mod.FLAG_DELETED:
            continue
        s.append((min(r[0], r[1]), max(r[0], r[1])))
    return s


def findable(mm, mod, kx, ky):
    """Index lookup that does NOT trust a stale index entry: the entry must
    point at a slot whose record really is this pair."""
    a, b = mm._key_index[kx], mm._key_index[ky]
    lo, hi = min(a, b), max(a, b)
    nb = mm._csr_get_neighbors(a) if mm._use_csr else list(mm._adjacency.get(a, set()))
    for nid, es in nb:
        if nid != b:
            continue
        r = mm._read_edge(es)
        if not (r[4] & mod.FLAG_DELETED) and (min(r[0], r[1]), max(r[0], r[1])) == (lo, hi):
            return True
    return False


def survivors(mm, mod):
    truth = set(record_pairs(mm, mod))
    by_rec = sum(1 for x, y in NEW_PAIRS
                 if (min(mm._key_index[key(x)], mm._key_index[key(y)]),
                     max(mm._key_index[key(x)], mm._key_index[key(y)])) in truth)
    by_idx = sum(1 for x, y in NEW_PAIRS if findable(mm, mod, key(x), key(y)))
    by_gn = sum(1 for x, y in NEW_PAIRS
                if key(y) in [n for n, _w in mm.get_neighbors(key(x), limit=1000)])
    return by_rec, by_idx, by_gn


def scenario(mod, d, csr):
    """Fill to capacity; if csr, reopen so the CSR path is used; then add K new."""
    path = os.path.join(d, "t.manifold")
    mm = mod.ManifoldMemory(path, node_capacity=N_NODES, edge_capacity=CAP)
    make_nodes(mm)
    fill(mm)
    if csr:
        mm.close()
        mm = mod.ManifoldMemory(path)
        assert mm._use_csr, "expected the CSR path after reopen"
    add_new(mm)
    return mm, path


class _Base(unittest.TestCase):
    MM_PATH = os.environ.get("W15_MM_PATH", DEFAULT_MM)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="w15_")
        self._env = os.environ.get(SWITCH)
        self.mod = load_module(self.MM_PATH, "cand")
        self._saved_time = self.mod.time
        self.mod.time = _FakeTime()

    def tearDown(self):
        self.mod.time = self._saved_time
        if self._env is None:
            os.environ.pop(SWITCH, None)
        else:
            os.environ[SWITCH] = self._env
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sub(self, name):
        p = os.path.join(self.tmp, name)
        os.makedirs(p, exist_ok=True)
        return p


class TestFixOn(_Base):
    """CONTROL: these FAIL on main's file (it has no switch) and pass with the fix."""

    def _check(self, csr):
        os.environ[SWITCH] = "1"
        mm, path = scenario(self.mod, self.sub("on_%s" % csr), csr)
        by_rec, by_idx, by_gn = survivors(mm, self.mod)
        print("\n[W15] switch ON  csr=%s: K=%d survive by record=%d index=%d get_neighbors=%d"
              % (csr, K, by_rec, by_idx, by_gn))
        self.assertEqual(by_rec, K)
        self.assertEqual(by_idx, K)
        self.assertEqual(by_gn, K)
        self.assertEqual(mm._free_edge_slots, [])
        self.assertEqual(mm.edge_count, CAP)
        self.assertEqual(len(record_pairs(mm, self.mod)), CAP)
        mm.close()
        # (a) plain reopen. The .csr companion is reused when its ACTIVE edge count
        # matches (manifold_memory.py:852). At capacity that count never changes, so
        # a .csr built before the K new edges is loaded STALE -- a pre-existing
        # issue, the same on main (see SUMMARY "OPEN"). Records must still hold all K.
        mm2 = self.mod.ManifoldMemory(path)
        by_rec2, by_idx2, by_gn2 = survivors(mm2, self.mod)
        print("[W15] switch ON  csr=%s plain reopen: record=%d index=%d get_neighbors=%d"
              % (csr, by_rec2, by_idx2, by_gn2))
        self.assertEqual(by_rec2, K)
        mm2.close()
        # (b) reopen with the companion index rebuilt from the records.
        os.remove(path + ".csr")
        mm2 = self.mod.ManifoldMemory(path)
        by_rec2, by_idx2, by_gn2 = survivors(mm2, self.mod)
        print("[W15] switch ON  csr=%s reopen, .csr rebuilt: record=%d index=%d get_neighbors=%d"
              % (csr, by_rec2, by_idx2, by_gn2))
        self.assertEqual((by_rec2, by_idx2, by_gn2), (K, K, K))
        hdr = self.mod.HEADER_STRUCT.unpack(mm2._mm[0:self.mod.HEADER_STRUCT.size])
        self.assertEqual(hdr[3], CAP)          # header edge_count (high-water mark)
        self.assertEqual(mm2.edge_count, CAP)  # live count
        # which fill edges were evicted: exactly the K lightest (eviction choice unchanged)
        gone = set(range(CAP)) - set(
            i for i, (x, y) in enumerate(FILL_PAIRS)
            if (min(mm2._key_index[key(x)], mm2._key_index[key(y)]),
                max(mm2._key_index[key(x)], mm2._key_index[key(y)]))
            in set(record_pairs(mm2, self.mod)))
        lightest = set(sorted(range(CAP), key=lambda i: FILL_W[i])[:K])
        self.assertEqual(gone, lightest)
        mm2.close()

    def test_on_dict_path_keeps_all_K(self):
        self._check(csr=False)

    def test_on_csr_path_keeps_all_K(self):
        self._check(csr=True)

    def test_on_genuine_delete_still_frees_slot(self):
        """Deletion that is NOT evict-for-reuse (portal lottery / node eviction)
        must still put its slot on the free list."""
        os.environ[SWITCH] = "1"
        mm = self.mod.ManifoldMemory(os.path.join(self.sub("gd"), "t.manifold"),
                                     node_capacity=N_NODES, edge_capacity=CAP)
        make_nodes(mm)
        fill(mm)
        mm._delete_edge(3)
        self.assertEqual(mm._free_edge_slots, [3])
        self.assertEqual(mm.edge_count, CAP - 1)
        self.assertTrue(mm.link(key(40), key(41), weight=0.5))
        r = mm._read_edge(3)
        self.assertEqual((min(r[0], r[1]), max(r[0], r[1])),
                         (min(mm._key_index[key(40)], mm._key_index[key(41)]),
                          max(mm._key_index[key(40)], mm._key_index[key(41)])))
        self.assertEqual(mm._edge_count, CAP)
        mm.close()


class TestNodeEvictOn(_Base):
    """CONTROL: node eviction on the CSR path follows stale index entries. Both
    tests FAIL on main's file and pass with the switch on."""

    X = sorted(range(CAP), key=lambda i: FILL_W[i])[0]    # endpoint of the lightest fill edge

    def _open(self, d, cap):
        path = os.path.join(d, "t.manifold")
        mm = self.mod.ManifoldMemory(path, node_capacity=N_NODES, edge_capacity=cap)
        xs = FILL_PAIRS[self.X][0]
        for j in range(N_NODES):
            mm.upsert_node(key(j), activation=(0.0 if j == xs else 1.0))
        fill(mm)
        mm.close()
        mm = self.mod.ManifoldMemory(path)
        self.assertTrue(mm._use_csr)
        return mm, xs

    def test_on_node_evict_no_collateral(self):
        """At capacity: the evicted node's stale CSR entry names a slot that now
        holds one of the K new edges. That edge must not be deleted."""
        os.environ[SWITCH] = "1"
        mm, xs = self._open(self.sub("ne1"), CAP)
        add_new(mm)
        sx = mm._key_index[key(xs)]
        live_x = sum(1 for p in record_pairs(mm, self.mod) if sx in p)
        before = len(record_pairs(mm, self.mod))
        self.assertEqual(survivors(mm, self.mod)[0], K)
        self.assertEqual(mm._evict_coldest_node(), sx)
        after_rec = survivors(mm, self.mod)[0]
        print("\n[W15] node evict at capacity: K survive by record %d -> %d; active %d -> %d "
              "(node had %d live edges)" % (K, after_rec, before,
                                            len(record_pairs(mm, self.mod)), live_x))
        self.assertEqual(after_rec, K)
        self.assertEqual(len(record_pairs(mm, self.mod)), before - live_x)
        self.assertEqual(len(mm._free_edge_slots), len(set(mm._free_edge_slots)))
        mm.close()

    def test_on_node_evict_no_double_free(self):
        """Below capacity: delete an edge of node X (portal-lottery path), then
        evict X. Its stale CSR entry must not free the slot a second time."""
        os.environ[SWITCH] = "1"
        mm, xs = self._open(self.sub("ne2"), CAP * 2)
        sx = mm._key_index[key(xs)]
        slot = next(s for s in range(mm._edge_count)
                    if sx in mm._read_edge(s)[:2] and not (mm._read_edge(s)[4] & 1))
        mm._delete_edge(slot)
        self.assertEqual(mm._evict_coldest_node(), sx)
        dup = len(mm._free_edge_slots) - len(set(mm._free_edge_slots))
        # two new edges after this: each must survive
        p1, p2 = (50, 51), (52, 53)
        mm.link(key(p1[0]), key(p1[1]), weight=0.9)
        mm.link(key(p2[0]), key(p2[1]), weight=0.9)
        truth = set(record_pairs(mm, self.mod))
        ok = sum(1 for x, y in (p1, p2)
                 if (min(mm._key_index[key(x)], mm._key_index[key(y)]),
                     max(mm._key_index[key(x)], mm._key_index[key(y)])) in truth)
        print("\n[W15] node evict after a prior delete: duplicate free-list entries=%d, "
              "2 new edges survive=%d" % (dup, ok))
        self.assertEqual(dup, 0)
        self.assertEqual(ok, 2)
        mm.close()


class TestSwitchOffIdentical(_Base):
    """With the switch unset (and with "0"), file bytes equal main's after the same ops."""

    def _run(self, mod, d, csr):
        mod.time = _FakeTime()
        mm, path = scenario(mod, d, csr)
        res = survivors(mm, mod)
        # also drive the node-eviction path (evicts slot 0: all activations equal)
        mm._delete_edge(5)
        mm._evict_coldest_node()
        mm.link(key(50), key(51), weight=0.9)
        mm.link(key(52), key(53), weight=0.9)
        res = res + (len(mm._free_edge_slots), mm.edge_count)
        mm.close()
        out = {}
        for ext in ("", ".csr", ".keys"):
            if os.path.exists(path + ext):
                with open(path + ext, "rb") as f:
                    out[ext] = f.read()
        return out, res

    def _check(self, csr, env_value):
        if env_value is None:
            os.environ.pop(SWITCH, None)
        else:
            os.environ[SWITCH] = env_value
        main = load_module(main_module_path(self.tmp), "main")
        saved = main.time
        try:
            got_main, res_main = self._run(main, self.sub("main_%s" % csr), csr)
        finally:
            main.time = saved
        got_cand, res_cand = self._run(self.mod, self.sub("cand_%s" % csr), csr)
        print("\n[W15] switch %s csr=%s: main K-survivors (record,index,get_neighbors)=%s "
              "candidate=%s" % (env_value, csr, res_main, res_cand))
        self.assertEqual(sorted(got_main), sorted(got_cand))
        for ext in got_main:
            self.assertEqual(got_main[ext], got_cand[ext], "bytes differ in %r" % ext)
        self.assertEqual(res_main, res_cand)

    def test_off_unset_dict(self):
        self._check(False, None)

    def test_off_unset_csr(self):
        self._check(True, None)

    def test_off_zero_csr(self):
        self._check(True, "0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
