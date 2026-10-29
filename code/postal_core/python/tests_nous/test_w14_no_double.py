"""W14 tests: AKASHIC_POSTAL_NO_DOUBLE (pure-Python PostalCore fallback) + the Python/Rust parity table.

Synthetic only: in-process PostalCore instances, no server, no fairy, no files written.
The module under test is loaded FROM A PATH so the suite runs against the original, the fix and mutants
(see run_w14_matrix.py):
    W14_FALLBACK=<path to _python_fallback.py>   (default: the file in this repo)
    W14_ORIGINAL=<path to the pre-W14 file>      (needed by the switch-OFF equivalence tests)
    W14_TENSOR_FABRIC=<path to tensor_fabric.py> (default: the file in this repo; only the class
                                                   _BaseTopicPostal is taken from it, with ast: importing
                                                   tensor_fabric starts a probe thread)
Table: w14_parity_table.json (shared with the Rust test topic_bus.rs w14_parity_table).
    python3 test_w14_no_double.py --table     prints measured Python counts next to Rust's, per switch combo.
"""
import ast
import importlib.util
import itertools
import json
import os
import sys
import threading
import time
import unittest
from collections import defaultdict
from typing import Callable, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = os.path.dirname(HERE)
DEFAULT_FALLBACK = os.path.join(PKG_ROOT, "postal_core", "_python_fallback.py")
DEFAULT_TF = os.path.join(PKG_ROOT, "postal_core", "tensor_fabric.py")
with open(os.path.join(HERE, "w14_parity_table.json"), encoding="utf-8") as _f:
    TABLE = json.load(_f)["rows"]
if PKG_ROOT not in sys.path:
    sys.path.insert(0, PKG_ROOT)                                   # for postal_core.postal_farm

SWITCHES = ("AKASHIC_RETURN_TO_SENDER", "AKASHIC_POSTAL_PREFIX_ANY_DEPTH", "AKASHIC_POSTAL_NO_DOUBLE",
            "AKASHIC_RETURN_RATE", "AKASHIC_RETURN_RING", "AKASHIC_RETURN_GLOBAL_RATE")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FB = load(os.environ.get("W14_FALLBACK", DEFAULT_FALLBACK), "w14_fallback_under_test")


class Env:
    """Set exactly these switches for the block; everything else in SWITCHES unset."""

    def __init__(self, **kv):
        self.kv = kv

    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in SWITCHES}
        for k in SWITCHES:
            os.environ.pop(k, None)
        os.environ.update(self.kv)

    def __exit__(self, *a):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def combo_env(rts, pad, nd):
    kv = {}
    if rts:
        kv["AKASHIC_RETURN_TO_SENDER"] = "1"
    if pad:
        kv["AKASHIC_POSTAL_PREFIX_ANY_DEPTH"] = "1"
    if nd:
        kv["AKASHIC_POSTAL_NO_DOUBLE"] = "1"
    return kv


COMBOS = list(itertools.product((0, 1), repeat=3))                 # (rts, pad, nd)


def bridge_class(path=None):
    """tensor_fabric._BaseTopicPostal, extracted with ast and run with USING_RUST=False (Python mode)."""
    with open(path or os.environ.get("W14_TENSOR_FABRIC", DEFAULT_TF), encoding="utf-8") as f:
        src = f.read()
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == "_BaseTopicPostal")

    class _Probe:
        def note_collision_publish(self, *a):
            pass

    ns = {"USING_RUST": False, "defaultdict": defaultdict, "Dict": Dict, "List": List, "Callable": Callable,
          "threading": threading, "_POSTAL_PROBE": _Probe()}
    exec(compile(ast.Module([node], []), "tensor_fabric_BaseTopicPostal", "exec"), ns)
    return ns["_BaseTopicPostal"]


def wait_for(pred, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.01)
    return pred()


def measure(mod, mode, rts, pad, nd, rows=TABLE):
    """Deliveries per subscription for every row, one PostalCore for the whole table (rows use distinct
    base topics, so they cannot hear each other). mode: 'core' or 'bridge'."""
    with Env(**combo_env(rts, pad, nd)):
        pc = mod.PostalCore()
    saved = sys.modules.get("postal_core._python_fallback")
    sys.modules["postal_core._python_fallback"] = mod            # the bridge imports Envelope from here
    target = bridge_class()(pc) if mode == "bridge" else pc
    got = {r["id"]: [0] * len(r["subs"]) for r in TABLE if r in rows}
    lock = threading.Lock()

    def handler(rid, i):
        def h(_env):
            with lock:
                got[rid][i] += 1
        return h

    try:
        for r in rows:
            for i, s in enumerate(r["subs"]):
                target.subscribe(s, handler(r["id"], i), "w14-%s-%d" % (r["id"], i))
        for r in rows:
            target.publish(r["pub"], {"row": r["id"]})
        want = sum(sum(r[mode]["%d%d" % (pad, nd)]) for r in rows)
        wait_for(lambda: sum(map(sum, got.values())) >= want)
        time.sleep(0.3)                                           # let stragglers (extra copies) land
        with lock:
            return {k: list(v) for k, v in got.items()}
    finally:
        if saved is None:
            sys.modules.pop("postal_core._python_fallback", None)
        else:
            sys.modules["postal_core._python_fallback"] = saved
        pc.shutdown()


def enqueue_log(mod, **env):
    """Every (publish index, pool, handler_id) enqueue for the table in core mode, in order."""
    seq = []
    cls = mod._WorkerPool
    real = cls.enqueue_no_signal
    cur = [None]

    def spy(self, envelope, handler_id):
        seq.append((cur[0], self.topic, handler_id))
        return real(self, envelope, handler_id)

    cls.enqueue_no_signal = spy
    with Env(**env):
        pc = mod.PostalCore()
    try:
        for r in TABLE:
            for i, s in enumerate(r["subs"]):
                pc.subscribe(s, lambda e: None, "w14-%s-%d" % (r["id"], i))
        for r in TABLE:
            cur[0] = r["id"]
            pc.publish(r["pub"], {"row": r["id"]})
    finally:
        cls.enqueue_no_signal = real
        pc.shutdown()
    return seq


class TestParityTable(unittest.TestCase):
    """Measured Python deliveries equal the table, for all 8 switch combinations, in both Python layers."""

    def _check(self, mode):
        for rts, pad, nd in COMBOS:
            got = measure(FB, mode, rts, pad, nd)
            for r in TABLE:
                self.assertEqual(got[r["id"]], r[mode]["%d%d" % (pad, nd)],
                                 "%s %s rts=%d pad=%d nd=%d" % (mode, r["id"], rts, pad, nd))

    def test_core_table(self):
        self._check("core")

    def test_bridge_table(self):
        self._check("bridge")

    def test_core_with_both_prefix_switches_equals_rust(self):
        """CONTROL: PostalCore with PREFIX_ANY_DEPTH=1 + NO_DOUBLE=1 delivers exactly Rust's counts, every row."""
        for rts in (0, 1):
            got = measure(FB, "core", rts, 1, 1)
            for r in TABLE:
                self.assertEqual(got[r["id"]], r["rust"], "%s rts=%d" % (r["id"], rts))

    def test_no_double_alone_fixes_every_double(self):
        """CONTROL: with NO_DOUBLE=1 no subscription anywhere in the table is delivered more than once."""
        for mode in ("core", "bridge"):
            got = measure(FB, mode, 0, 0, 1)
            for r in TABLE:
                self.assertLessEqual(max(got[r["id"]]), 1, (mode, r["id"]))


class TestSwitchOff(unittest.TestCase):
    """NO_DOUBLE unset: exactly the pre-W14 enqueue sequence (set, count and ORDER), with W2 switches 0/1."""

    def test_off_enqueue_sequence_matches_original(self):
        orig_path = os.environ.get("W14_ORIGINAL")
        if not orig_path:
            self.skipTest("W14_ORIGINAL not set (run via run_w14_matrix.py)")
        orig = load(orig_path, "w14_fallback_original")
        for rts, pad in itertools.product((0, 1), repeat=2):
            env = combo_env(rts, pad, 0)
            a, b = enqueue_log(orig, **env), enqueue_log(FB, **env)
            self.assertTrue(a)
            self.assertEqual(a, b, env)

    def test_on_removes_only_the_repeat(self):
        """NO_DOUBLE=1 = the OFF sequence with each repeated (pool, handler) of one publish dropped, order kept."""
        for pad in (0, 1):
            off = enqueue_log(FB, **combo_env(0, pad, 0))
            on = enqueue_log(FB, **combo_env(0, pad, 1))
            seen, expect = set(), []
            for e in off:
                if e not in seen:
                    seen.add(e)
                    expect.append(e)
            self.assertLess(len(expect), len(off))               # the table does contain doubles
            self.assertEqual(on, expect, "pad=%d" % pad)


class TestSwitchParsing(unittest.TestCase):
    def test_only_exact_1(self):
        for v in ("", "0", " 1", "1 ", "true", "TRUE", "yes", "on", "2"):
            with Env(AKASHIC_POSTAL_NO_DOUBLE=v):
                pc = FB.PostalCore()
            try:
                self.assertIs(pc._no_double, False, repr(v))
            finally:
                pc.shutdown()
        with Env():
            pc = FB.PostalCore()
        try:
            self.assertIs(pc._no_double, False, "unset")
        finally:
            pc.shutdown()
        with Env(AKASHIC_POSTAL_NO_DOUBLE="1"):
            pc = FB.PostalCore()
        try:
            self.assertIs(pc._no_double, True)
        finally:
            pc.shutdown()


def print_table():
    """Measured Python counts vs the table's Rust column; '!' marks a row that differs from Rust."""
    res = {(m, rts, pad, nd): measure(FB, m, rts, pad, nd) for m in ("core", "bridge") for rts, pad, nd in COMBOS}
    hdr = ["row", "subs -> pub", "rust"] + ["%s r%dp%dn%d" % (m, rts, pad, nd)
                                           for m in ("core", "bridge") for rts, pad, nd in COMBOS]
    print("\t".join(hdr))
    for r in TABLE:
        cells = []
        for m in ("core", "bridge"):
            for c in COMBOS:
                v = res[(m,) + c][r["id"]]
                cells.append(("" if v == r["rust"] else "!") + ",".join(map(str, v)))
        print("\t".join([r["id"], "%s -> %s" % ("+".join(r["subs"]), r["pub"]),
                         ",".join(map(str, r["rust"]))] + cells))


if __name__ == "__main__":
    if "--table" in sys.argv:
        print_table()
    else:
        unittest.main()
