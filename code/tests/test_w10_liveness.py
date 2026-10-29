"""W10 tests: AKASHIC_LIVENESS_FROM_DELIVERY + break-room report.

Synthetic data only. No pool threads (POOL_SIZE=0 subclass), no files except
inside a TemporaryDirectory, fairy_template.citizen_registry is stubbed.

  W10_HBR_PATH  path of heartbeat_registry.py under test (default: this repo's)
  W10_REF_PATH  optional path of main's heartbeat_registry.py -> switch-OFF differential

Run:  python3 -m unittest code/tests/test_w10_liveness.py -v
"""
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
HBR_PATH = os.environ.get("W10_HBR_PATH") or os.path.join(CODE, "consciousness", "heartbeat_registry.py")
BR_PATH = os.path.join(CODE, "consciousness", "break_room.py")
FLAG = "AKASHIC_LIVENESS_FROM_DELIVERY"

# Stub the canonical citizen dict so no real fairy_template package is imported.
_CIT = {}
_pkg = types.ModuleType("fairy_template"); _pkg.__path__ = []
_mod = types.ModuleType("fairy_template.citizen_registry")
_mod._CITIZEN_OBJECTS = _CIT; _mod.CITIZEN_OBJECTS = _CIT
sys.modules["fairy_template"] = _pkg
sys.modules["fairy_template.citizen_registry"] = _mod


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


HBR = _load(HBR_PATH, "w10_hbr_under_test")
BR = _load(BR_PATH, "w10_break_room")


class Obj:
    def __init__(self, plane=""):
        self.ACTOR_PLANE = plane
        self._last_tick = 0
        self._tick_count = 0


def make(mod):
    class R(mod.HeartbeatRegistry):
        POOL_SIZE = 0  # no worker threads; tests drain the queue by hand
    return R()


def drain(r):
    while not r._delivery_queue.empty():
        name, cb, pd = r._delivery_queue.get_nowait()
        r._deliver_one(name, cb, pd)


def scenario(mod, beats=(1,)):
    """Napper: citizen, no callback.  Worker: citizen + callback.  Engine: P10 non-citizen.
    Hog: callback already in flight.  Broken: callback raises."""
    _CIT.clear()
    _CIT["Napper"] = Obj("P30"); _CIT["Worker"] = Obj("P40")
    r = make(mod)
    r.register("Worker", lambda pd: None, plane="P40")
    r.register("Engine", lambda pd: None, plane="P10")
    r.register("Hog", lambda pd: None, plane="P30")
    def boom(pd): raise RuntimeError("x")
    r.register("Broken", boom, plane="P20")
    r._in_flight.add("Hog")
    for b in beats:
        r.pulse({"beat": b})
        drain(r)
        r._in_flight.add("Hog")  # still busy
    return r


class Env:
    def __init__(self, val): self.val = val
    def __enter__(self):
        self.old = os.environ.get(FLAG)
        if self.val is None: os.environ.pop(FLAG, None)
        else: os.environ[FLAG] = self.val
    def __exit__(self, *a):
        if self.old is None: os.environ.pop(FLAG, None)
        else: os.environ[FLAG] = self.old


class SwitchOn(unittest.TestCase):
    def test_control_citizen_without_callback_not_stamped(self):
        with Env("1"):
            r = scenario(HBR)
        self.assertNotIn("Napper", r._last_delivered_ts)

    def test_gated_beat_not_stamped(self):
        with Env("1"):
            r = scenario(HBR, beats=(1,))  # 1 % 5 != 0 -> Engine (P10) gated
        self.assertNotIn("Engine", r._last_delivered_ts)

    def test_in_flight_skip_not_stamped(self):
        with Env("1"):
            r = scenario(HBR)
        self.assertNotIn("Hog", r._last_delivered_ts)

    def test_raising_callback_not_stamped(self):
        with Env("1"):
            r = scenario(HBR)
        self.assertNotIn("Broken", r._last_delivered_ts)

    def test_real_delivery_stamped_with_beat(self):
        with Env("1"):
            r = scenario(HBR, beats=(1, 5))
        self.assertIn("Worker", r._last_delivered_ts)
        self.assertEqual(r._last_delivered_beat.get("Worker"), 5)
        self.assertEqual(r._last_delivered_beat.get("Engine"), 5)  # 5 % 5 == 0 -> delivered

    def test_object_tick_stamps_unchanged(self):
        # Deliberate: _obj._last_tick/_tick_count feed the watchdog's primary check
        # (handlers/heartbeat.py:278-326, :490-507); W10 does not touch them.
        with Env("1"):
            r = scenario(HBR, beats=(1, 2, 3))
        self.assertEqual(_CIT["Napper"]._tick_count, 3)
        self.assertGreater(_CIT["Napper"]._last_tick, 0)

    def test_break_room_lists_nappers(self):
        _CIT.clear(); _CIT["Napper"] = Obj("P30")
        with Env("1"):
            r = make(HBR)
            r.register("Worker", lambda pd: None, plane="P40")
            r.register("Sleeper", lambda pd: None, plane="P20")
            for b in range(1, 16):
                r.pulse({"beat": b})
                while not r._delivery_queue.empty():
                    n, cb, pd = r._delivery_queue.get_nowait()
                    if n == "Sleeper" and b > 1:
                        r._in_flight.discard(n); continue  # simulate never reached again
                    r._deliver_one(n, cb, pd)
        rep = BR.break_room(r, n_beats=10, citizens=_CIT)
        names = {x["name"]: x for x in rep["napping"]}
        self.assertTrue(rep["switch_on"])
        self.assertIn("Napper", names); self.assertEqual(names["Napper"]["plane"], "P30")
        self.assertIn("Sleeper", names); self.assertEqual(names["Sleeper"]["beats_since"], 14)
        self.assertEqual(names["Sleeper"]["plane"], "P20")
        self.assertNotIn("Worker", names)
        # CLI over a snapshot file (temp dir only)
        with tempfile.TemporaryDirectory() as d:
            p = BR.dump_snapshot(r, os.path.join(d, "snap.json"), citizens=_CIT)
            with open(p, encoding="utf-8") as f:
                snap = json.load(f)
            rep2 = BR.break_room(snap, n_beats=10)
            self.assertEqual(rep, rep2)
            self.assertEqual(BR.main([p, "--beats", "10"]), 0)


class SwitchOff(unittest.TestCase):
    def _legacy(self, r):
        for n in ("Napper", "Worker", "Engine", "Hog"):
            self.assertIn(n, r._last_delivered_ts, n)
        self.assertNotIn("Broken", r._last_delivered_ts)
        self.assertEqual(getattr(r, "_last_delivered_beat", {}), {})

    def test_off_when_unset(self):
        with Env(None):
            self._legacy(scenario(HBR))

    def test_only_exact_1_is_on(self):
        for v in ("0", "", "true", "yes", "on", " 1", "2"):
            with Env(v):
                self._legacy(scenario(HBR))

    def test_break_room_off_lists_only_no_callback(self):
        with Env(None):
            r = scenario(HBR)
        rep = BR.break_room(r, n_beats=10, citizens=_CIT)
        self.assertFalse(rep["switch_on"]); self.assertTrue(rep["note"])
        self.assertEqual([x["name"] for x in rep["napping"]], ["Napper"])

    @unittest.skipUnless(os.environ.get("W10_REF_PATH"), "set W10_REF_PATH to main's file")
    def test_off_differential_vs_main(self):
        ref = _load(os.environ["W10_REF_PATH"], "w10_hbr_ref")
        def trace(mod):
            with Env(None):
                r = scenario(mod, beats=(1, 2, 5))
            return (sorted(r._last_delivered_ts), dict(r._error_counts),
                    {k: (v._tick_count, v._last_tick > 0) for k, v in _CIT.items()},
                    r._last_stats, sorted(r._in_flight), r._total_pulses)
        self.assertEqual(trace(ref), trace(HBR))


if __name__ == "__main__":
    unittest.main()
