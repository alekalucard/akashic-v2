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


if __name__ == "__main__":
    unittest.main(verbosity=2)
