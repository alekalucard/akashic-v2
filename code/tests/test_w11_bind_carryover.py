"""W11 bind carryover + bind timing -- unit tests. SYNTHETIC DATA IN A TEMP DIR ONLY: no real manifold, no server, no fairy.

Run:  python3 -I code/tests/test_w11_bind_carryover.py                (tests the tree this file sits in)
      W11_TREE=<dir> python3 -I code/tests/test_w11_bind_carryover.py (tests another tree: <dir>/infrastructure/*.py, <dir>/server.py)
code/tests/w11_mutation_run.py runs this file against main, this branch and the mutants.

What is imported: infrastructure.tardis_fix / tardis_backlog / tardis_timing / manifold_memory. Their top level only defines
constants, locks and functions (no threads, sockets or file writes). server.py is NEVER imported: one function is lifted out of
its source with ast and run against a stub.
"""
import ast
import json
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
import unittest

TREE = os.environ.get("W11_TREE") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TREE)

from infrastructure import tardis_fix as TF          # noqa: E402
from infrastructure import tardis_backlog as TB      # noqa: E402
from infrastructure import tardis_timing as TT       # noqa: E402
from infrastructure import manifold_memory as MM     # noqa: E402

ENV = ("AKASHIC_BIND_CARRYOVER", "AKASHIC_BIND_TIMING")

# Every path the modules write to points into ONE process-wide temp root for the whole run and is never restored to the
# tree's own state/ (B's sweeper thread outlives a test by design; it must never find a real directory).
import atexit                                         # noqa: E402
_ROOT_TMP = tempfile.mkdtemp(prefix="w11_root_")
atexit.register(shutil.rmtree, _ROOT_TMP, True)
TF.FILE = os.path.join(_ROOT_TMP, "absent", "tardis_fix.json")
TB.DIR = os.path.join(_ROOT_TMP, "unused_backlog")


class _Region:
    """Stands in for the manifold region: B reads only filepath / node_count / edge_count from it."""
    def __init__(self, path):
        self.filepath = path
        self.node_count = 10
        self.edge_count = 20


class _Cx:
    def __init__(self, region, q):
        self._akashic_cortex_region = region
        self._tardis_bind_queue = q


def _items(n):
    """Synthetic queue items in the exact shape fairy.py:_on_postal_bind builds (fairy.py:4986-4996), with features."""
    out = []
    for i in range(n):
        it = {
            "concept_key": "audiocortexfairy_exp_%d" % (1700000000 + i),
            "features": {"lex": ["word%d" % i, "other%d" % i], "affect": ["warm"], "audio": ["audio_level:0.%d" % (i % 10)]},
            "concepts_to_bind": ["audiocortexfairy_exp_%d" % (1700000000 + i), "word%d" % i, "other%d" % i, "affect_warm"],
            "feeling": "warm",
            "from_fairy": "AudioCortexFairy",
            "origin_plane": "P40",
            "origin_channel": "experience",
        }
        if i % 3 == 0:
            it["concept_metadata"] = {"word%d" % i: {"snippet": "s%d" % i, "node_type": 0}}
        out.append(it)
    return out


def _pairs_of(items):
    """The pair list _tardis_process_batch derives from a batch (fairy.py:6381-6411, one tracer bucket): order kept."""
    seen, out = set(), []
    for it in items:
        c = it.get("concepts_to_bind", [])
        for i in range(len(c)):
            for j in range(i + 1, len(c)):
                k = (min(c[i], c[j]), max(c[i], c[j]))
                if k not in seen:
                    seen.add(k)
                    out.append((c[i], c[j]))
    return out


def _read_file(path):
    recs = []
    with open(path, "rb") as f:
        for line in f:
            r, why = TB._dec(line)
            assert r is not None, why
            recs.append(r)
    return recs


class Base(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.pop(k, None) for k in ENV}
        self.tmp = tempfile.mkdtemp(prefix="w11_test_", dir=_ROOT_TMP)
        TF.FILE = os.path.join(self.tmp, "tardis_fix.json")      # absent: every key OFF from the file
        TF.reset_cache()
        TB.DIR = os.path.join(self.tmp, "tardis_backlog")
        self.saved_cfg = dict(TB.CFG)
        TB._reset_for_tests()

    def tearDown(self):
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        TF.FILE = os.path.join(_ROOT_TMP, "absent", "tardis_fix.json")
        TF.reset_cache()
        TB.CFG.clear()
        TB.CFG.update(self.saved_cfg)
        TB._reset_for_tests()

    def backlog(self, q=None):
        q = q if q is not None else queue.Queue(maxsize=4096)
        region = _Region(os.path.join(self.tmp, "synthetic.manifold"))
        return TB.Backlog(_Cx(region, q), region, q), q


# ---------------------------------------------------------------- the switches
class Switch(Base):
    def test_off_when_unset(self):
        """OFF equivalence: env unset and file absent -> every key OFF (same as main)."""
        for k in ("b_persist", "l0_timing", "a1_fastlink"):
            self.assertFalse(TF.on(k), k)
            self.assertFalse(TF.on(k, fresh=True), k)
        self.assertFalse(TB._sw("b_persist", fresh=True))

    def test_off_for_non_one_values(self):
        for v in ("0", "", "true", "yes", "on", " 1", "1 ", "01", "TRUE"):
            os.environ["AKASHIC_BIND_CARRYOVER"] = v
            os.environ["AKASHIC_BIND_TIMING"] = v
            self.assertFalse(TF.on("b_persist", fresh=True), repr(v))
            self.assertFalse(TF.on("l0_timing", fresh=True), repr(v))

    def test_control_env_turns_layer_on(self):
        """CONTROL (fails on main: main has no environment switch)."""
        os.environ["AKASHIC_BIND_CARRYOVER"] = "1"
        self.assertTrue(TF.on("b_persist"))
        self.assertTrue(TF.on("b_persist", fresh=True))
        self.assertFalse(TF.on("l0_timing", fresh=True))
        self.assertFalse(TF.on("a1_fastlink", fresh=True))       # no alias for A1
        os.environ.pop("AKASHIC_BIND_CARRYOVER")
        os.environ["AKASHIC_BIND_TIMING"] = "1"
        self.assertTrue(TF.on("l0_timing", fresh=True))
        self.assertFalse(TF.on("b_persist", fresh=True))

    def test_file_on_still_on_with_env_unset(self):
        with open(TF.FILE, "w") as f:
            json.dump({"b_persist": True}, f)
        TF.reset_cache()
        self.assertTrue(TF.on("b_persist", fresh=True))
        self.assertFalse(TF.on("l0_timing", fresh=True))


# ---------------------------------------------------------------- persist: fields, order, pairs
class Persist(Base):
    def test_control_persist_keeps_every_field_in_order(self):
        """CONTROL (fails on main: main writes a subset of fields, `features` is dropped)."""
        os.environ["AKASHIC_BIND_CARRYOVER"] = "1"
        b, q = self.backlog()
        src = _items(300)
        for it in src:
            q.put_nowait(dict(it))
        b.persist_now("test")
        self.assertEqual(q.qsize(), 0)
        recs = _read_file(b.path)
        self.assertEqual(recs[0]["kind"], TB.KIND)
        body = recs[1:]
        self.assertEqual(len(body), len(src))
        self.assertEqual([r["seq"] for r in body], list(range(1, len(src) + 1)))       # order within the file
        for r, it in zip(body, src):
            self.assertEqual(r["t"], "item")
            self.assertEqual(r["i"], it)                                                # same fields, same values
            self.assertEqual(list(r["i"].keys()), list(it.keys()))                      # same key order
        self.assertEqual(_pairs_of([r["i"] for r in body]), _pairs_of(src))

    def test_off_persist_writes_todays_subset(self):
        """OFF equivalence: b_persist ON from the FILE, env unset -> the record is today's subset (no features)."""
        with open(TF.FILE, "w") as f:
            json.dump({"b_persist": True}, f)
        TF.reset_cache()
        b, q = self.backlog()
        src = _items(5)
        for it in src:
            q.put_nowait(dict(it))
        b.persist_now("test")
        body = _read_file(b.path)[1:]
        self.assertEqual(len(body), 5)
        for r, it in zip(body, src):
            self.assertNotIn("features", r["i"])
            self.assertEqual(r["i"]["concepts_to_bind"], it["concepts_to_bind"])
        self.assertEqual(_pairs_of([r["i"] for r in body]), _pairs_of(src))

    def test_unrepresentable_item_falls_back_to_todays_record(self):
        """A tuple does not survive JSON exactly: the item is written as today's record, its pairs unchanged."""
        os.environ["AKASHIC_BIND_CARRYOVER"] = "1"
        b, q = self.backlog()
        it = _items(1)[0]
        it["features"] = {"lex": ("a", "b")}
        rec = b.item_record(it, "queue")
        self.assertNotIn("features", rec["i"])
        self.assertEqual(rec["i"]["concepts_to_bind"], it["concepts_to_bind"])
        it2 = _items(1)[0]
        it2["concepts_to_bind"] = it2["concepts_to_bind"] + ["x" * 300]                  # manifold would reject it anyway
        rec2 = b.item_record(it2, "queue")
        self.assertNotIn("features", rec2["i"])
        self.assertEqual(rec2["i"]["concepts_to_bind"], it2["concepts_to_bind"][:-1])
        self.assertTrue(TB.validate(rec) and TB.validate(rec2))

    def test_replay_bookkeeping_key_not_carried(self):
        os.environ["AKASHIC_BIND_CARRYOVER"] = "1"
        b, q = self.backlog()
        it = dict(_items(1)[0])
        it["_tf_replay"] = "abc"
        rec = b.item_record(it, "queue")
        self.assertNotIn("_tf_replay", rec["i"])
        self.assertIn("features", rec["i"])

    def test_control_persist_then_replay_roundtrip(self):
        """CONTROL: persist at shutdown, replay at the next boot into a fresh queue -> the same items, same order; file moved aside."""
        os.environ["AKASHIC_BIND_CARRYOVER"] = "1"
        b, q = self.backlog()
        src = _items(150)
        for it in src:
            q.put_nowait(dict(it))
        b.persist_now("test")
        name = os.path.basename(b.path)
        b._fh.close()
        TB._reset_for_tests()
        TB.CFG.update(max_rate=200, headroom=2048, trickle_s=0.0)
        b2, q2 = self.backlog()
        self.assertTrue(b2._replay_file(name))
        got = []
        while True:
            try:
                got.append(q2.get_nowait())
            except queue.Empty:
                break
        self.assertEqual(len(got), len(src))
        for g, it in zip(got, src):
            g = dict(g)
            self.assertEqual(g.pop("_tf_replay"), _read_file(os.path.join(TB.DIR, "done-" + name[len("pending-"):]))[0]["uuid"])
            self.assertEqual(g, it)
        left = sorted(os.listdir(TB.DIR))
        self.assertIn("done-" + name[len("pending-"):], left)                           # moved aside, not deleted
        self.assertNotIn(name, left)
        # the same file can never be replayed twice: put it back by hand -> rejected (ledger), nothing fed
        os.replace(os.path.join(TB.DIR, "done-" + name[len("pending-"):]), os.path.join(TB.DIR, name))
        self.assertTrue(b2._replay_file(name))
        self.assertEqual(q2.qsize(), 0)

    def test_torn_tail_leaves_earlier_records_and_previous_file_intact(self):
        """A crash mid-append: the torn last line is skipped, every complete record before it replays; an earlier boot's file
        is never opened for writing (each boot writes a NEW pending-* name, opened 'xb'). A property of main's B, kept: B is
        switched ON here through the FILE so this test also runs (and passes) on main."""
        with open(TF.FILE, "w") as f:
            json.dump({"b_persist": True}, f)
        TF.reset_cache()
        old =os.path.join(TB.DIR, "pending-20260101-000000-1-deadbeef.jsonl")
        os.makedirs(TB.DIR, exist_ok=True)
        with open(old, "wb") as f:
            f.write(b"previous boot bytes\n")
        before = open(old, "rb").read()
        b, q = self.backlog()
        for it in _items(10):
            q.put_nowait(dict(it))
        b.persist_now("test")
        b._fh.close()
        self.assertEqual(open(old, "rb").read(), before)
        data = open(b.path, "rb").read()
        with open(b.path, "wb") as f:
            f.write(data[:-7])                                    # tear the last record
        name = os.path.basename(b.path)
        TB._reset_for_tests()
        TB.CFG.update(max_rate=200, headroom=2048, trickle_s=0.0)
        b2, q2 = self.backlog()
        b2._replay_file(name)
        self.assertEqual(q2.qsize(), 9)
        self.assertEqual(b2.counters["torn"], 1)


# ---------------------------------------------------------------- never delete
class NeverDelete(Base):
    def _finish(self):
        os.makedirs(TB.DIR, exist_ok=True)
        for i in range(20):
            open(os.path.join(TB.DIR, "done-old%02d.jsonl" % i), "wb").close()
        claim = "replaying-new.jsonl"
        open(os.path.join(TB.DIR, claim), "wb").close()
        b, q = self.backlog()
        b._cur = {"fh": open(os.path.join(TB.DIR, claim), "rb"), "claim": claim, "name": "pending-new.jsonl", "uuid": "u", "left": 0}
        b._finish_current("done")
        return sorted(n for n in os.listdir(TB.DIR) if n.startswith("done-"))

    def test_control_never_deletes_done_files(self):
        """CONTROL (fails on main: main prunes done-* to the newest 16)."""
        os.environ["AKASHIC_BIND_CARRYOVER"] = "1"
        self.assertEqual(len(self._finish()), 21)

    def test_off_prunes_like_today(self):
        """OFF equivalence: env unset -> today's pruning (done_keep = 16)."""
        self.assertEqual(len(self._finish()), TB.cfg("done_keep"))

    def _ledger(self, n):
        os.makedirs(TB.DIR, exist_ok=True)
        for i in range(n):
            TB._ledger_add("u%04d" % i)
        return TB._ledger_read()

    def test_control_ledger_keeps_every_uuid(self):
        """CONTROL (fails on main: the ledger keeps 256 uuids, so a kept done-* file older than that could replay twice)."""
        os.environ["AKASHIC_BIND_CARRYOVER"] = "1"
        got = self._ledger(TB.cfg("ledger_keep") + 10)
        self.assertEqual(len(got), TB.cfg("ledger_keep") + 10)
        self.assertEqual(got[0], "u0000")

    def test_off_ledger_trims_like_today(self):
        got = self._ledger(TB.cfg("ledger_keep") + 10)
        self.assertEqual(len(got), TB.cfg("ledger_keep"))


# ---------------------------------------------------------------- persist_owner + server.py hook
class Owner(Base):
    def test_persist_owner_off_does_nothing(self):
        with open(TF.FILE, "w") as f:
            json.dump({"b_persist": True}, f)
        TF.reset_cache()
        b, q = self.backlog()
        TB._OWNER["b"] = b
        for it in _items(3):
            q.put_nowait(it)
        f = getattr(TB, "persist_owner", None)
        if f is not None:
            self.assertFalse(f("reboot"))
        self.assertEqual(q.qsize(), 3)
        self.assertIsNone(b.path)

    def test_control_persist_owner_on(self):
        """CONTROL (fails on main: no persist_owner; the reboot / Ctrl+C routes persist nothing)."""
        os.environ["AKASHIC_BIND_CARRYOVER"] = "1"
        b, q = self.backlog()
        TB._OWNER["b"] = b
        for it in _items(3):
            q.put_nowait(it)
        self.assertTrue(TB.persist_owner("reboot"))
        self.assertEqual(q.qsize(), 0)
        self.assertEqual(len(_read_file(b.path)), 4)
        self.assertTrue(TB.persist_owner("ctrl_c"))                # idempotent
        self.assertEqual(len(_read_file(b.path)), 4)


def _server_fn():
    """Lift _w11_bind_carryover out of server.py's SOURCE (server.py is never imported) and its two call sites."""
    src = open(os.path.join(TREE, "server.py"), "rb").read().decode("utf-8")
    tree = ast.parse(src)
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_w11_bind_carryover"]
    calls = [n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_w11_bind_carryover"]
    return (ast.get_source_segment(src, fn[0]) if fn else None), calls


def _calls_in(node, name, attr=None):
    """Calls of `name(...)` (or `attr`.`name`(...)) inside node, NOT descending into nested function definitions."""
    out, todo = [], [node]
    while todo:
        n = todo.pop()
        for c in ast.iter_child_nodes(n):
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(c, ast.Call):
                f = c.func
                if (attr is None and getattr(f, "id", None) == name) or \
                        (attr is not None and isinstance(f, ast.Attribute) and f.attr == name and getattr(f.value, "id", None) == attr):
                    out.append(c)
            todo.append(c)
    return out


def _hook_placement():
    """For each hook call: is it a plain statement whose LATER siblings run shutdown_system(), with no os._exit before it?"""
    src = open(os.path.join(TREE, "server.py"), "rb").read().decode("utf-8")
    tree = ast.parse(src)
    res = {}
    for parent in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            stmts = getattr(parent, field, None)
            if not isinstance(stmts, list):
                continue
            for i, st in enumerate(stmts):
                if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and \
                        getattr(st.value.func, "id", "") == "_w11_bind_carryover":
                    reason = st.value.args[0].value
                    later = any(_calls_in(ast.Module(body=[x], type_ignores=[]), "shutdown_system") for x in stmts[i + 1:])
                    earlier_exit = any(_calls_in(ast.Module(body=[x], type_ignores=[]), "_exit", "os") for x in stmts[:i])
                    res[reason] = later and not earlier_exit
    return res


class ServerHook(Base):
    def _run(self):
        code, calls = _server_fn()
        self.assertIsNotNone(code, "server.py has no _w11_bind_carryover")
        self.assertEqual(sorted(calls), ["ctrl_c", "reboot"])
        seen = []
        stub = type(sys)("infrastructure.tardis_backlog")
        stub.persist_owner = lambda r: seen.append(r)
        real = sys.modules.get("infrastructure.tardis_backlog")
        sys.modules["infrastructure.tardis_backlog"] = stub
        import infrastructure as _pkg
        real_attr = getattr(_pkg, "tardis_backlog", None)
        _pkg.tardis_backlog = stub
        try:
            ns = {"os": os}
            exec(compile(code, "server.py:_w11_bind_carryover", "exec"), ns)
            ns["_w11_bind_carryover"]("reboot")
        finally:
            sys.modules["infrastructure.tardis_backlog"] = real
            _pkg.tardis_backlog = real_attr
        return seen

    def test_control_server_hook_on(self):
        """CONTROL (fails on main: server.py has no hook)."""
        os.environ["AKASHIC_BIND_CARRYOVER"] = "1"
        self.assertEqual(self._run(), ["reboot"])

    def test_control_hooks_run_before_shutdown_system(self):
        """CONTROL (fails on main: no hooks). Each hook is a plain statement that runs BEFORE shutdown_system() on its route."""
        self.assertEqual(_hook_placement(), {"reboot": True, "ctrl_c": True})

    def test_server_hook_off_when_unset(self):
        code, _ = _server_fn()
        if code is None:
            return                                                # main: nothing to call -> trivially OFF
        self.assertEqual(self._run(), [])


# ---------------------------------------------------------------- timing laps
class Timing(Base):
    def _mm(self, ncap, ecap):
        m = MM.ManifoldMemory(os.path.join(self.tmp, "synthetic.manifold"), node_capacity=ncap, edge_capacity=ecap)
        self.addCleanup(m.close)
        return m

    def _armed(self, fn):
        w = TT.Window(owner=None, out=lambda s: None)
        MM._TF_L0_TL.acc = w.acc
        try:
            fn()
        finally:
            MM._TF_L0_TL.acc = None
        return w.acc

    def _edge_full(self):
        m = self._mm(64, 8)
        for i in range(10):
            m.upsert_node("n%d" % i)
        for i in range(8):
            self.assertTrue(m.link("n0", "n%d" % (i + 1)))
        self.assertEqual(m._edge_count, 8)
        return self._armed(lambda: self.assertTrue(m.link("n2", "n3")))

    def _node_full(self):
        m = self._mm(4, 16)
        for i in range(4):
            m.upsert_node("n%d" % i)
        return self._armed(lambda: self.assertGreaterEqual(m.upsert_node("fresh"), 0))

    def test_control_eviction_laps_on(self):
        """CONTROL (fails on main: the eviction scan is hidden inside l.new / u.new)."""
        os.environ["AKASHIC_BIND_TIMING"] = "1"
        a = self._edge_full()
        self.assertIn("l.evict", a.w)
        self.assertIn("l.new", a.w)
        a2 = self._node_full()
        self.assertIn("u.evict", a2.w)
        self.assertIn("u.new", a2.w)
        w = TT.Window(owner=None, out=lambda s: None)
        w.acc = a
        self.assertIn("l.evict", w.stats()["deep_l_ms"])

    def test_off_no_new_laps(self):
        """OFF equivalence: env unset -> the laps main takes, nothing more."""
        a = self._edge_full()
        self.assertNotIn("l.evict", a.w)
        self.assertEqual(a.n.get("l.new"), 1)
        a2 = self._node_full()
        self.assertNotIn("u.evict", a2.w)
        self.assertEqual(a2.n.get("u.new"), 1)

    def test_unarmed_thread_measures_nothing(self):
        os.environ["AKASHIC_BIND_TIMING"] = "1"
        m = self._mm(4, 16)
        for i in range(5):
            m.upsert_node("n%d" % i)                              # the 5th evicts, with no accumulator armed
        self.assertIsNone(getattr(MM._TF_L0_TL, "acc", None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
