"""W12: MomentBinder HOLD -> dream seed at shutdown (switch AKASHIC_MOMENT_HOLD_SAVE, OFF unless "1").

Synthetic data in a temp dir only. Never imports server.py or any fairy: the helper module is loaded by file
path (stdlib-only, no side effects), server.py is read as text and parsed with ast.

  python code/tests/test_w12_moment_hold.py
Env overrides (used to run the same tests against main's files and against mutants):
  W12_MODULE  path of moment_hold_save.py to test   (default: code/infrastructure/moment_hold_save.py)
  W12_SERVER  path of server.py to check             (default: code/server.py)
"""
import ast
import importlib.util
import json
import os
import random
import shutil
import sys
import tempfile
import threading
import unittest
from collections import deque
from unittest import mock

sys.dont_write_bytecode = True   # no __pycache__ next to her code

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
MODULE_PATH = os.environ.get("W12_MODULE", os.path.join(CODE, "infrastructure", "moment_hold_save.py"))
SERVER_PATH = os.environ.get("W12_SERVER", os.path.join(CODE, "server.py"))
FAIRY_PATH = os.environ.get("W12_FAIRY", os.path.join(CODE, "fairies", "P30_Cognition", "MomentBinderFairy", "fairy.py"))
RSW = "AKASHIC_MOMENT_HOLD_RESTORE"
SW = "AKASHIC_MOMENT_HOLD_SAVE"


def load():
    spec = importlib.util.spec_from_file_location("w12_moment_hold_save_under_test", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)   # raises FileNotFoundError when the module does not exist (main)
    return mod


def moment(i, sig, rng):
    return {
        "ts": 1761700000.0 + i * 1.000123,
        "input_text": "thought %d · ünïcode — %s" % (i, "x" * rng.randint(0, 880)),
        "feeling": rng.choice(["neutral", "positive", "negative", "aroused"]),
        "channels": rng.randint(1, 7),
        "vision": ["scene:desk", "color:#%06x" % rng.randint(0, 0xFFFFFF)],
        "audio": [] if i % 2 else ["hum"],
        "significance": sig,
        "tracer": "%012x" % rng.getrandbits(48),
        "sources": [{"channel": "cognitive", "fairy": "InnerNarratorFairy"}],
    }


class FakeBinder:
    ACTOR_NAME = "MomentBinderFairy"

    def __init__(self, moments):
        self._moment_lock = threading.RLock()
        self._episodic_buffer = deque(moments, maxlen=60)
        self._consolidated_tracers = set()
        self._epi_persister = object()        # the episodic persister is up (on_boot initialised it)


class Rec:
    def __init__(self, inst):
        self.metadata = {"fairy_instance": inst}


class FakeDirectory:
    def __init__(self, inst):
        self.inst = inst
        self.instantiated = False

    def get_fairy(self, name):
        return Rec(self.inst) if name == "MomentBinderFairy" else None

    def list_fairies(self, plane=None, status=None):
        return [Rec(self.inst)]

    def get_fairy_instance(self, name):   # must never be used: it can CREATE a fairy
        self.instantiated = True
        return self.inst


class FakeSystem:
    def __init__(self, inst):
        self.directory = FakeDirectory(inst)


SEED = {
    "seed_id": "seed_1761700000", "captured_at": 1761700000.5, "captured_date": "2026-10-29 10:00:00",
    "mind_pools": {"WorkingMemoryHub": {"reflective_tracers": [{"content": "a", "priority": 0.5}]}},
    "chemistry_snapshot": {"dopamine": 0.5}, "last_thoughts": {"working_memory": "a"}, "pending_goals": [],
}


class Base(unittest.TestCase):
    def setUp(self):
        self.mod = load()
        self.tmp = tempfile.mkdtemp(prefix="w12_")
        self.seed_path = os.path.join(self.tmp, "dream_seed.json")
        with open(self.seed_path, "w", encoding="utf-8") as f:
            json.dump(SEED, f, indent=2)
        rng = random.Random(1225)
        self.moments = [moment(i, round(rng.random(), 3), rng) for i in range(60)]
        self.binder = FakeBinder([dict(m) for m in self.moments])
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop(SW, None)
        os.environ.pop(RSW, None)

    def tearDown(self):
        self._env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def seed_bytes(self):
        with open(self.seed_path, "rb") as f:
            return f.read()

    def seed(self):
        with open(self.seed_path, "r", encoding="utf-8") as f:
            return json.load(f)


class TestSwitchOff(Base):
    def test_off_when_unset(self):
        before = self.seed_bytes()
        self.assertEqual(self.mod.hand_off(self.binder, self.seed_path), "off")
        self.assertEqual(self.mod.shutdown_hand_off(FakeSystem(self.binder), self.seed_path), "off")
        self.assertEqual(self.seed_bytes(), before)
        self.assertEqual(os.listdir(self.tmp), ["dream_seed.json"])

    def test_off_for_every_value_but_1(self):
        before = self.seed_bytes()
        for v in ("0", "", "true", "True", "yes", "on", " 1", "1 ", "2"):
            os.environ[SW] = v
            self.assertEqual(self.mod.hand_off(self.binder, self.seed_path), "off", v)
        self.assertEqual(self.seed_bytes(), before)


class TestSwitchOn(Base):
    def setUp(self):
        super().setUp()
        os.environ[SW] = "1"

    def test_control_hold_carried_unchanged(self):
        """CONTROL: fails on main (module absent); passes here."""
        r = self.mod.shutdown_hand_off(FakeSystem(self.binder), self.seed_path)
        self.assertTrue(r.startswith("saved 60 of 60"), r)
        s = self.seed()
        mh = s["mind_pools"]["moment_hold"]
        self.assertEqual(mh["moments"], self.moments)          # every field, every moment, HOLD order
        self.assertEqual((mh["held"], mh["saved"], mh["dropped"]), (60, 60, 0))
        for k, v in SEED.items():                                # the seed's own content untouched
            if k != "mind_pools":
                self.assertEqual(s[k], v)
        self.assertEqual(s["mind_pools"]["WorkingMemoryHub"], SEED["mind_pools"]["WorkingMemoryHub"])
        self.assertEqual(list(self.binder._episodic_buffer), self.moments)   # HOLD not mutated
        self.assertEqual(os.listdir(self.tmp), ["dream_seed.json"])          # no temp left behind
        # boot readers iterate every mind_pools entry for these keys (unconscious_mind_fairy.py:4219-4227,
        # waking_sequence_fairy.py:615-629, sourpatches_farm.py:1184-1185): the entry must carry none of them
        for k in ("working_tracers", "reflective_tracers", "tracers", "goals"):
            self.assertNotIn(k, mh)

    def test_drop_by_significance_not_age(self):
        # oldest moments are the MOST significant: an age rule would drop them, the importance rule keeps them
        ms = [dict(m, significance=s) for m, s in zip(self.moments[:6], [0.9, 0.8, 0.7, 0.1, 0.2, 0.3])]
        b = FakeBinder(ms)
        r = self.mod.hand_off(b, self.seed_path, max_n=3)
        self.assertIn("dropped 3", r)
        kept = self.seed()["mind_pools"]["moment_hold"]["moments"]
        self.assertEqual([m["significance"] for m in kept], [0.9, 0.8, 0.7])
        self.assertEqual(kept, ms[:3])

    def test_byte_bound_drops_lowest_significance(self):
        ms = [dict(m) for m in self.moments[:10]]
        size = max(len(json.dumps(m)) for m in ms)
        r = self.mod.hand_off(FakeBinder(ms), self.seed_path, max_bytes=size * 4)
        kept = self.seed()["mind_pools"]["moment_hold"]["moments"]
        self.assertLessEqual(sum(len(json.dumps(m)) for m in kept), size * 4, r)
        dropped = [m for m in ms if m not in kept]
        self.assertTrue(dropped)
        self.assertLessEqual(max(m["significance"] for m in dropped), min(m["significance"] for m in kept))
        self.assertEqual(kept, [m for m in ms if m in kept])   # HOLD order kept

    def test_byte_bound_holds_on_disk(self):
        """The moments array as it sits in the written file stays within max_bytes (measured on the file)."""
        for cap in (3000, 6000, 12000, 40000):
            r = self.mod.hand_off(FakeBinder([dict(m) for m in self.moments]), self.seed_path, max_bytes=cap)
            with open(self.seed_path, "r", encoding="utf-8") as f:
                raw = f.read()
            s = json.loads(raw)
            empty = json.loads(raw)
            empty["mind_pools"]["moment_hold"]["moments"] = []
            on_disk = len(raw) - len(json.dumps(empty, indent=2))
            self.assertLessEqual(on_disk, cap, (cap, r))
            self.assertTrue(s["mind_pools"]["moment_hold"]["moments"], r)

    def test_non_dict_entry_refused_alone(self):
        ok = self.moments[:4]
        r = self.mod.hand_off(FakeBinder(["a string", 7] + [dict(m) for m in ok]), self.seed_path)
        self.assertIn("refused 2", r)
        mh = self.seed()["mind_pools"]["moment_hold"]
        self.assertEqual(mh["moments"], ok)
        self.assertEqual((mh["held"], mh["saved"], mh["refused"]), (6, 4, 2))

    def test_atomic_crash_mid_write_leaves_seed_intact(self):
        before = self.seed_bytes()
        real_dump = json.dump

        def crashing_dump(obj, fp, *a, **kw):
            fp.write('{"seed_id": "trunc')
            fp.flush()
            raise OSError("disk gone")

        with mock.patch.object(self.mod.json, "dump", crashing_dump):
            r = self.mod.hand_off(self.binder, self.seed_path)
        self.assertTrue(r.startswith("error"), r)
        self.assertEqual(self.seed_bytes(), before)
        self.assertEqual(os.listdir(self.tmp), ["dream_seed.json"])
        self.assertIs(json.dump, real_dump)

    def test_never_creates_a_seed(self):
        os.remove(self.seed_path)
        r = self.mod.hand_off(self.binder, self.seed_path)
        self.assertTrue(r.startswith("skipped"), r)
        self.assertEqual(os.listdir(self.tmp), [])

    def test_non_object_seed_left_as_is(self):
        with open(self.seed_path, "w") as f:
            f.write("[1, 2]")
        self.assertTrue(self.mod.hand_off(self.binder, self.seed_path).startswith("skipped"))
        with open(self.seed_path) as f:
            self.assertEqual(f.read(), "[1, 2]")

    def test_value_json_cannot_carry_is_refused_not_coerced(self):
        bad = dict(self.moments[0], vision=("scene:desk", "color:#000000"))   # tuple -> list would change it
        nan = dict(self.moments[1], significance=float("nan"))
        ok = self.moments[2:5]
        r = self.mod.hand_off(FakeBinder([bad, nan] + [dict(m) for m in ok]), self.seed_path)
        self.assertIn("refused 2", r)
        mh = self.seed()["mind_pools"]["moment_hold"]
        self.assertEqual(mh["moments"], ok)                    # the others carried exactly; nothing coerced
        self.assertEqual((mh["held"], mh["refused"]), (5, 2))
        self.assertEqual(mh["refused_tracers"], [bad["tracer"], nan["tracer"]])

    def test_find_binder_never_instantiates(self):
        sysm = FakeSystem(self.binder)
        self.assertIs(self.mod.find_binder(sysm), self.binder)
        self.assertFalse(sysm.directory.instantiated)
        self.assertTrue(self.mod.shutdown_hand_off(object(), self.seed_path).startswith("skipped"))

    def test_hand_off_never_raises(self):
        class Bad:
            @property
            def _episodic_buffer(self):
                raise KeyError("boom")
        self.assertTrue(self.mod.hand_off(Bad(), self.seed_path).startswith("error"))


class TestServerWiring(unittest.TestCase):
    """CONTROL (static, no import): shutdown_system() hands the HOLD off right after _capture_dream_seed(),
    gated on os.environ.get("AKASHIC_MOMENT_HOLD_SAVE", "0") == "1"."""

    def test_control_server_calls_hand_off_after_capture(self):
        with open(SERVER_PATH, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "shutdown_system")
        body = fn.body
        cap = next(i for i, n in enumerate(body) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                   and getattr(n.value.func, "id", "") == "_capture_dream_seed")
        nxt = body[cap + 1]
        self.assertIsInstance(nxt, ast.If, "no gated block right after _capture_dream_seed()")
        t = nxt.test
        self.assertIsInstance(t, ast.Compare)
        self.assertIsInstance(t.ops[0], ast.Eq)
        self.assertEqual(t.comparators[0].value, "1")
        call = t.left
        self.assertEqual(ast.unparse(call.func), "os.environ.get")
        self.assertEqual([a.value for a in call.args], [SW, "0"])
        src = ast.unparse(nxt)
        self.assertIn("infrastructure.moment_hold_save", src)
        self.assertIn("shutdown_hand_off", src)
        self.assertEqual(len(nxt.orelse), 0)


class TestRestore(Base):
    """W12b reader: dream_seed.json mind_pools['moment_hold'] -> an EMPTY hold, exactly as saved, once per set."""

    def setUp(self):
        super().setUp()
        self.marker = os.path.join(self.tmp, "moment_hold_restored.json")
        os.environ[SW] = "1"
        r = self.mod.hand_off(self.binder, self.seed_path)          # a real saved set, written by the saver
        self.assertTrue(r.startswith("saved 60"), r)
        os.environ.pop(SW)
        self.seed_before = self.seed_bytes()

    def fresh(self):
        return FakeBinder([])

    def test_restore_off_when_unset_or_not_1(self):
        for v in (None, "0", "", "true", " 1", "yes"):
            if v is None:
                os.environ.pop(RSW, None)
            else:
                os.environ[RSW] = v
            b = self.fresh()
            self.assertEqual(self.mod.restore_into(b, self.seed_path, self.marker), "off", v)
            self.assertEqual(len(b._episodic_buffer), 0)
        self.assertFalse(os.path.exists(self.marker))
        self.assertEqual(self.seed_bytes(), self.seed_before)

    def test_control_restore_exact_order_once(self):
        """CONTROL: fails on main (no reader); passes here."""
        os.environ[RSW] = "1"
        b = self.fresh()
        st0 = os.stat(self.seed_path)
        r = self.mod.restore_into(b, self.seed_path, self.marker)
        self.assertTrue(r.startswith("restored 60"), r)
        st1 = os.stat(self.seed_path)
        self.assertEqual((st1.st_ino, st1.st_mtime_ns), (st0.st_ino, st0.st_mtime_ns))   # seed not rewritten at all
        self.assertEqual(list(b._episodic_buffer), self.moments)      # every field, oldest-first, nothing merged/dropped
        self.assertEqual(b._episodic_buffer.maxlen, 60)                # same hold structure, same cap
        self.assertEqual(b._consolidated_tracers, {m["tracer"] for m in self.moments})   # rememberer skips them
        self.assertEqual(self.seed_bytes(), self.seed_before)          # the seed is never written
        # crash-restart: a second boot with a fresh, empty hold must NOT restore the same set again
        b2 = self.fresh()
        r2 = self.mod.restore_into(b2, self.seed_path, self.marker)
        self.assertIn("already restored", r2)
        self.assertEqual(len(b2._episodic_buffer), 0)

    def test_only_into_empty_hold(self):
        os.environ[RSW] = "1"
        live = dict(self.moments[0], tracer="live000000000")
        b = FakeBinder([live])
        r = self.mod.restore_into(b, self.seed_path, self.marker)
        self.assertIn("empty hold", r)
        self.assertEqual(list(b._episodic_buffer), [live])
        self.assertFalse(os.path.exists(self.marker))                  # not consumed: a later empty boot may restore it

    def test_never_exceeds_cap(self):
        os.environ[RSW] = "1"
        b = self.fresh()
        b._episodic_buffer = deque(maxlen=10)
        r = self.mod.restore_into(b, self.seed_path, self.marker)
        self.assertIn("hold cap", r)
        self.assertEqual(len(b._episodic_buffer), 0)
        self.assertFalse(os.path.exists(self.marker))

    def test_marker_write_fails_no_restore(self):
        """Mark BEFORE fill: if the consumed-mark cannot be written, the hold stays empty (never a double)."""
        os.environ[RSW] = "1"
        b = self.fresh()
        with mock.patch.object(self.mod, "_atomic_write_json", side_effect=OSError("disk gone")):
            r = self.mod.restore_into(b, self.seed_path, self.marker)
        self.assertTrue(r.startswith("error"), r)
        self.assertEqual(len(b._episodic_buffer), 0)

    def test_unreadable_marker_refuses(self):
        os.environ[RSW] = "1"
        with open(self.marker, "w") as f:
            f.write("{not json")
        b = self.fresh()
        self.assertTrue(self.mod.restore_into(b, self.seed_path, self.marker).startswith("error"))
        self.assertEqual(len(b._episodic_buffer), 0)
        with open(self.marker) as f:
            self.assertEqual(f.read(), "{not json")                      # never deleted or rewritten

    def test_new_saved_set_restores_again(self):
        os.environ[RSW] = "1"
        self.assertTrue(self.mod.restore_into(self.fresh(), self.seed_path, self.marker).startswith("restored"))
        os.environ[SW] = "1"                                            # next shutdown saves a different hold
        nb = FakeBinder([dict(m) for m in self.moments[:5]])
        self.mod.hand_off(nb, self.seed_path)
        b = self.fresh()
        self.assertTrue(self.mod.restore_into(b, self.seed_path, self.marker).startswith("restored 5"))
        self.assertEqual(list(b._episodic_buffer), self.moments[:5])
        with open(self.marker) as f:
            self.assertEqual(len(json.load(f)["consumed"]), 2)

    def test_nothing_saved_is_noop(self):
        os.environ[RSW] = "1"
        with open(self.seed_path, "w", encoding="utf-8") as f:
            json.dump(SEED, f)
        b = self.fresh()
        self.assertTrue(self.mod.restore_into(b, self.seed_path, self.marker).startswith("nothing"))
        self.assertFalse(os.path.exists(self.marker))


    def test_no_persister_no_restore(self):
        """R2-3: with no episodic persister a restored moment that rolls off would be dropped unpersisted
        (fairy.py append site): the restore must skip and leave the set unconsumed."""
        os.environ[RSW] = "1"
        b = self.fresh()
        b._epi_persister = None
        r = self.mod.restore_into(b, self.seed_path, self.marker)
        self.assertIn("no episodic persister", r)
        self.assertEqual(len(b._episodic_buffer), 0)
        self.assertFalse(os.path.exists(self.marker))
        b2 = self.fresh()                                               # a later boot with the persister up restores it
        self.assertTrue(self.mod.restore_into(b2, self.seed_path, self.marker).startswith("restored 60"))

    def test_one_saved_set_into_one_binder_only(self):
        """R2-6: many binders racing on one marker -> exactly one gets the set."""
        os.environ[RSW] = "1"
        binders = [self.fresh() for _ in range(8)]
        gate = threading.Barrier(len(binders))
        out = [None] * len(binders)

        def go(i):
            gate.wait()
            out[i] = self.mod.restore_into(binders[i], self.seed_path, self.marker)

        th = [threading.Thread(target=go, args=(i,)) for i in range(len(binders))]
        for x in th:
            x.start()
        for x in th:
            x.join()
        self.assertEqual(sum(1 for b in binders if len(b._episodic_buffer)), 1, out)
        self.assertEqual(sum(1 for r in out if r.startswith("restored")), 1, out)
        with open(self.marker) as f:
            self.assertEqual(len(json.load(f)["consumed"]), 1)


def _fairy_tree():
    with open(FAIRY_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MomentBinderFairy")
    return tree, {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}


class TestFairyWiring(unittest.TestCase):
    """CONTROL (static, no import): the switch is read once as _MH_RESTORE_ON = os.environ.get(RSW, "0") == "1";
    on_boot restores AFTER the episodic persister init; the hold's append and the reviewed-tracer prune take
    _moment_lock only when the switch is ON (OFF = the original lines)."""

    def test_switch_constant(self):
        tree, _ = _fairy_tree()
        a = [n for n in tree.body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "_MH_RESTORE_ON"]
        self.assertEqual(len(a), 1)
        v = a[0].value
        self.assertIsInstance(v.ops[0], ast.Eq)
        self.assertEqual(v.comparators[0].value, "1")
        self.assertTrue(ast.unparse(v.left.func).endswith("environ.get"))
        self.assertEqual([x.value for x in v.left.args], [RSW, "0"])

    def test_append_locked_only_when_on(self):
        _, fns = _fairy_tree()
        withs = [n for n in ast.walk(fns["_maybe_emit_moment"]) if isinstance(n, ast.With)
                 and "_episodic_buffer.append" in ast.unparse(n)]
        self.assertEqual(len(withs), 1)
        self.assertEqual(ast.unparse(withs[0].items[0].context_expr),
                         "self._moment_lock if _MH_RESTORE_ON else _MH_NO_LOCK()")
        self.assertIn("_evicted = self._episodic_buffer[0]", ast.unparse(withs[0]))

    def test_prune_under_lock_only_after_restore(self):
        with open(FAIRY_PATH, "r", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MomentBinderFairy")
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_consolidate_episodic")
        ifs = [n for n in fn.body if isinstance(n, ast.If) and ast.unparse(n.test) == "_MH_RESTORE_ON"]
        self.assertEqual(len(ifs), 1)
        on, off = ifs[0].body, ifs[0].orelse
        self.assertEqual([ast.unparse(x) for x in off], ["self._consolidated_tracers &= _live"])   # OFF: as on main
        self.assertIsInstance(on[0], ast.With)
        self.assertEqual(ast.unparse(on[0].items[0].context_expr), "self._moment_lock")
        self.assertIn("self._episodic_buffer", ast.unparse(on[0]))

    def test_control_on_boot_calls_restore(self):
        with open(FAIRY_PATH, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MomentBinderFairy")
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "on_boot")
        body = fn.body
        # the last step before `return True`, AFTER the episodic persister init (R2-3)
        self.assertIsInstance(body[-1], ast.Return)
        gate = body[-2]
        self.assertIsInstance(gate, ast.If, "no gated restore block before on_boot's return")
        self.assertIn("EpisodicPersister", ast.unparse(body[-3]))
        self.assertEqual(ast.unparse(gate.test), "_MH_RESTORE_ON")
        src = ast.unparse(gate)
        self.assertIn("infrastructure.moment_hold_save", src)
        self.assertIn("restore_into", src)
        self.assertNotIn("sleep_consolidate", ast.unparse(fn))
        self.assertEqual(len(gate.orelse), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
