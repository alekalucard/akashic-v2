"""W10 tests: AKASHIC_LIVENESS_FROM_DELIVERY (watch-only) + break-room report.

The switch gates ONLY two new dicts (_last_handled_ts/_last_handled_beat) read by
break_room.py. _last_delivered_ts (read by the watchdog) must equal main's, switch on or off.

Synthetic data only. No pool threads (POOL_SIZE=0 subclass), no files except
inside a TemporaryDirectory, fairy_template.citizen_registry is stubbed, and the
registry's clock is replaced by a fixed fake so timestamps compare exactly.

  W10_HBR_PATH  heartbeat_registry.py under test (default: this repo's)
  W10_BR_PATH   break_room.py under test (default: this repo's)
  W10_REF_PATH  main's heartbeat_registry.py -> exact differentials vs main (else skipped)

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
BR_PATH = os.environ.get("W10_BR_PATH") or os.path.join(CODE, "consciousness", "break_room.py")
REF_PATH = os.environ.get("W10_REF_PATH")
FLAG = "AKASHIC_LIVENESS_FROM_DELIVERY"

# Stub the canonical citizen dict so no real fairy_template package is imported.
_CIT = {}
_pkg = types.ModuleType("fairy_template"); _pkg.__path__ = []
_mod = types.ModuleType("fairy_template.citizen_registry")
_mod._CITIZEN_OBJECTS = _CIT; _mod.CITIZEN_OBJECTS = _CIT
sys.modules["fairy_template"] = _pkg
sys.modules["fairy_template.citizen_registry"] = _mod


class FakeClock:
    """Replaces the registry module's `time`: time() returns a fixed value per beat."""
    def __init__(self): self.now = 1000.0
    def time(self): return self.now
    def perf_counter(self): return 0.0


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.time = FakeClock()
    return m


HBR = _load(HBR_PATH, "w10_hbr_under_test")
BR = _load(BR_PATH, "w10_break_room")
REF = _load(REF_PATH, "w10_hbr_ref") if REF_PATH else None


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
        mod.time.now = 1000.0 + b
        r.pulse({"beat": b})
        drain(r)
        r._in_flight.add("Hog")  # still busy
    return r


def watchdog_view(mod, beats=(1, 2, 5)):
    """Everything handlers/heartbeat.py can read, after the scenario: exact values."""
    r = scenario(mod, beats)
    return (dict(r._last_delivered_ts), dict(r._error_counts),
            {k: (v._tick_count, v._last_tick) for k, v in _CIT.items()},
            dict(r._last_stats), sorted(r._in_flight), r._total_pulses, sorted(r._callbacks))


class Env:
    def __init__(self, val): self.val = val
    def __enter__(self):
        self.old = os.environ.get(FLAG)
        if self.val is None: os.environ.pop(FLAG, None)
        else: os.environ[FLAG] = self.val
    def __exit__(self, *a):
        if self.old is None: os.environ.pop(FLAG, None)
        else: os.environ[FLAG] = self.old


LEGACY = {"Napper", "Worker", "Engine", "Hog"}  # what main stamps in _last_delivered_ts at beat 1


class SwitchOn(unittest.TestCase):
    def test_control_handled_only_for_real_delivery(self):
        # CONTROL: main has no _last_handled_ts at all -> fails there.
        with Env("1"):
            r = scenario(HBR)
        self.assertEqual(set(r._last_handled_ts), {"Worker"})  # Napper/Engine(gated)/Hog/Broken absent

    def test_handled_beat_recorded(self):
        with Env("1"):
            r = scenario(HBR, beats=(1, 5))
        self.assertEqual(r._last_handled_beat.get("Worker"), 5)
        self.assertEqual(r._last_handled_beat.get("Engine"), 5)  # 5 % 5 == 0 -> delivered
        self.assertNotIn("Napper", r._last_handled_beat)
        self.assertNotIn("Broken", r._last_handled_beat)
        self.assertNotIn("Hog", r._last_handled_beat)

    def test_on_watchdog_stamp_still_legacy(self):
        # Watch-only: with the switch ON the watchdog's stamp is still blanket, as on main.
        with Env("1"):
            r = scenario(HBR)
        self.assertEqual(set(r._last_delivered_ts), LEGACY)

    @unittest.skipUnless(REF, "set W10_REF_PATH to main's file")
    def test_on_watchdog_view_identical_to_main(self):
        # Switch ON here vs main (which ignores the switch): every value the watchdog reads,
        # including exact _last_delivered_ts timestamps, must be identical.
        with Env("1"):
            a = watchdog_view(REF); b = watchdog_view(HBR)
        self.assertEqual(a, b)

    def test_object_tick_stamps_unchanged(self):
        with Env("1"):
            scenario(HBR, beats=(1, 2, 3))
        self.assertEqual(_CIT["Napper"]._tick_count, 3)
        self.assertEqual(_CIT["Napper"]._last_tick, 1003.0)

    def test_break_room_reads_handled_not_delivered(self):
        # _last_delivered_ts is fresh for everyone (as the watchdog sees it); only the new
        # field says Sleeper has not really run since beat 1. The report must follow the new field.
        _CIT.clear()
        with Env("1"):
            r = make(HBR)
            r.register("Worker", lambda pd: None, plane="P40")
            r.register("Sleeper", lambda pd: None, plane="P20")
            r.pulse({"beat": 15})
        r._last_delivered_ts.update({"Worker": 1015.0, "Sleeper": 1015.0})
        r._last_handled_beat.clear(); r._last_handled_beat.update({"Worker": 15, "Sleeper": 1})
        rep = BR.break_room(r, n_beats=10, citizens=_CIT)
        self.assertEqual([x["name"] for x in rep["napping"]], ["Sleeper"])
        self.assertEqual(rep["napping"][0]["beats_since"], 14)

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
        with tempfile.TemporaryDirectory() as d:  # CLI over a snapshot file (temp dir only)
            p = BR.dump_snapshot(r, os.path.join(d, "snap.json"), citizens=_CIT)
            with open(p, encoding="utf-8") as f:
                snap = json.load(f)
            self.assertEqual(BR.break_room(snap, n_beats=10), rep)
            self.assertEqual(BR.main([p, "--beats", "10"]), 0)


class SwitchOff(unittest.TestCase):
    def _legacy(self, r):
        self.assertEqual(set(r._last_delivered_ts), LEGACY)
        self.assertEqual(getattr(r, "_last_handled_ts", {}), {})
        self.assertEqual(getattr(r, "_last_handled_beat", {}), {})

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

    @unittest.skipUnless(REF, "set W10_REF_PATH to main's file")
    def test_off_watchdog_view_identical_to_main(self):
        with Env(None):
            a = watchdog_view(REF); b = watchdog_view(HBR)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
