"""W2 tests: return to sender + prefix-any-depth for the pure-Python PostalCore fallback.

Synthetic only: in-process PostalCore instances, no server, no fairy, no files outside a temp dir.
The module under test is loaded FROM A PATH so the same suite runs against the original file,
the fix, and mutants (see run_w2_matrix.py):
    W2_FALLBACK=<path to _python_fallback.py>   (default: the file in this repo)
    W2_ORIGINAL=<path to the pre-W2 file>        (needed by the byte-identical test)

Import check: _python_fallback.py's top level is stdlib imports + three module-level assignments
(no threads, sockets, files). Constructing PostalCore starts the PostalFarm tick thread and one worker
pool per topic; every test shuts its instances down.
"""
import importlib.util
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = os.path.dirname(HERE)                                   # code/postal_core/python
DEFAULT_FALLBACK = os.path.join(PKG_ROOT, "postal_core", "_python_fallback.py")
if PKG_ROOT not in sys.path:
    sys.path.insert(0, PKG_ROOT)                                   # for postal_core.postal_farm

SWITCHES = ("AKASHIC_RETURN_TO_SENDER", "AKASHIC_POSTAL_PREFIX_ANY_DEPTH",
            "AKASHIC_RETURN_RATE", "AKASHIC_RETURN_RING")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FB = load(os.environ.get("W2_FALLBACK", DEFAULT_FALLBACK), "w2_fallback_under_test")


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


def wait_for(pred, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.01)
    return pred()


def make(mod=FB, **env):
    with Env(**env):
        return mod.PostalCore()


SCENARIO_SUBS = ["alpha", "alpha.beta", "alpha.beta.gamma", "delta.one", "postal.returned.Sender"]
SCENARIO_PUBS = [
    ("alpha.x", {"source": "Sender"}),
    ("alpha.beta.y", {"source": "Sender"}),
    ("alpha.beta.gamma.z", {"source": "Sender"}),      # depth-4: Python-only miss today
    ("delta.one", {}),
    ("delta.two", {"source": "Sender"}),               # nobody listens
    ("nowhere.at.all", {"_sender": "Other"}),          # nobody listens
    ("nowhere", None),
]


def run_scenario(mod):
    """Fixed traffic; returns (metrics minus timing-dependent keys, sorted deliveries per handler)."""
    pc = make(mod)
    got = {s: [] for s in SCENARIO_SUBS}
    try:
        for s in SCENARIO_SUBS:
            pc.subscribe(s, (lambda env, _s=s: got[_s].append(env.intent)), name="h-" + s)
        for intent, payload in SCENARIO_PUBS:
            pc.publish(intent, payload)
        wait_for(lambda: sum(len(v) for v in got.values()) >= 8)
        time.sleep(0.3)                                   # let stragglers land
        m = pc.metrics()
        m.pop("queue_depth", None)
        m.pop("farm", None)
        return m, {k: sorted(v) for k, v in got.items()}
    finally:
        pc.shutdown()


class TestSwitchOffByteIdentical(unittest.TestCase):
    """(b) With both switches unset, the fix behaves exactly like the pre-W2 file."""

    def test_off_matches_original(self):
        orig_path = os.environ.get("W2_ORIGINAL")
        if not orig_path:
            self.skipTest("W2_ORIGINAL not set (run via run_w2_matrix.py)")
        orig = load(orig_path, "w2_fallback_original")
        with Env():
            self.assertEqual(run_scenario(orig), run_scenario(FB))

    def test_off_has_no_return_office(self):
        pc = make()
        try:
            self.assertEqual(pc.returns(), {"enabled": False})
            self.assertNotIn("messages_returned", pc.metrics())
        finally:
            pc.shutdown()


class TestReturnToSender(unittest.TestCase):
    """(a) AKASHIC_RETURN_TO_SENDER=1."""

    def test_unwanted_letter_goes_back_to_sender(self):
        pc = make(AKASHIC_RETURN_TO_SENDER="1")
        back = []
        try:
            pc.subscribe("postal.returned.Sender", back.append, name="sender-mailbox")
            pc.publish("delta.two", {"source": "Sender", "x": 1})
            self.assertTrue(wait_for(lambda: len(back) == 1))
            p = back[0].payload
            self.assertEqual((p["_returned"], p["intent"], p["sender"], p["reason"]),
                             (True, "delta.two", "Sender", "no_subscriber"))
            self.assertEqual(p["letter"]["x"], 1)
            r = pc.returns()
            self.assertEqual((r["messages_returned"], r["returns_delivered"]), (1, 1))
            self.assertEqual(r["ring"][-1]["intent"], "delta.two")
            # the letter is NOT counted as published; the delivered return is
            self.assertEqual(pc.metrics()["messages_published"], 1)
        finally:
            pc.shutdown()

    def test_sender_from_underscore_sender_key(self):
        pc = make(AKASHIC_RETURN_TO_SENDER="1")
        back = []
        try:
            pc.subscribe("postal.returned.Other", back.append, name="other-mailbox")
            pc.publish("nowhere.at.all", {"_sender": "Other"})
            self.assertTrue(wait_for(lambda: len(back) == 1))
        finally:
            pc.shutdown()

    def test_no_sender_is_counted_not_sent(self):
        pc = make(AKASHIC_RETURN_TO_SENDER="1")
        try:
            pc.publish("nowhere", None)
            r = pc.returns()
            self.assertEqual((r["messages_returned"], r["returns_no_sender"], r["returns_delivered"]), (1, 1, 0))
        finally:
            pc.shutdown()

    def test_undeliverable_return_is_counted_never_returned(self):
        pc = make(AKASHIC_RETURN_TO_SENDER="1")
        try:
            pc.publish("delta.two", {"source": "Sender"})      # nobody listens, nor to the return
            r = pc.returns()
            self.assertEqual(r["messages_returned"], 1)
            self.assertEqual(r["return_undeliverable"], 1)
            self.assertEqual(r["returns_delivered"], 1)
            self.assertEqual(len(r["ring"]), 2)               # the letter + its dead return, nothing more
        finally:
            pc.shutdown()

    def test_delivered_letters_unchanged(self):
        pc = make(AKASHIC_RETURN_TO_SENDER="1")
        got = []
        try:
            pc.subscribe("delta.one", got.append, name="d1")
            pc.publish("delta.one", {"source": "Sender"})
            self.assertTrue(wait_for(lambda: len(got) == 1))
            self.assertEqual(pc.returns()["messages_returned"], 0)
        finally:
            pc.shutdown()

    def test_ring_is_bounded(self):
        pc = make(AKASHIC_RETURN_TO_SENDER="1", AKASHIC_RETURN_RING="5")
        try:
            for i in range(20):
                pc.publish("void.%d" % i, None)
            r = pc.returns()
            self.assertEqual(len(r["ring"]), 5)
            self.assertEqual(r["messages_returned"], 20)
            self.assertEqual(r["ring"][-1]["intent"], "void.19")
        finally:
            pc.shutdown()


class TestRateFloor(unittest.TestCase):
    """Any rate bound has a floor: returns still flow under it."""

    def test_rate_zero_is_clamped_to_floor_and_still_flows(self):
        off = FB._ReturnOffice(ring_size=8, rate_per_intent=0)
        self.assertEqual(off.rate, FB.RETURN_RATE_FLOOR)
        self.assertTrue(off.may_send("a.b", now=100.0))
        self.assertFalse(off.may_send("a.b", now=100.5))
        self.assertTrue(off.may_send("c.d", now=100.5))      # a flood on a.b does not starve c.d
        self.assertTrue(off.may_send("a.b", now=101.0))      # next second flows again

    def test_flood_under_env_rate_zero(self):
        pc = make(AKASHIC_RETURN_TO_SENDER="1", AKASHIC_RETURN_RATE="0")
        back = []
        try:
            pc.subscribe("postal.returned.Sender", back.append, name="mb")
            for _ in range(200):
                pc.publish("flood.topic", {"source": "Sender"})
            pc.publish("quiet.topic", {"source": "Sender"})
            self.assertTrue(wait_for(lambda: any(e.payload["intent"] == "quiet.topic" for e in back)))
            r = pc.returns()
            self.assertEqual(r["messages_returned"], 201)              # every letter counted
            self.assertGreaterEqual(r["returns_delivered"], 2)         # floor: >=1 per intent
            self.assertLessEqual(r["returns_delivered"], 4)            # bounded (second boundary slack)
            self.assertEqual(r["returns_delivered"] + r["returns_suppressed"], 201)
        finally:
            pc.shutdown()


class TestPrefixAnyDepth(unittest.TestCase):
    """(c) AKASHIC_POSTAL_PREFIX_ANY_DEPTH: sub a.b.c hears pub a.b.c.d (the Rust rule)."""

    def _deliveries(self, **env):
        pc = make(**env)
        got = {"a.b.c": [], "a.b.c.d": [], "a.b.c.d.e": []}
        try:
            for s in got:
                pc.subscribe(s, (lambda e, _s=s: got[_s].append(e.intent)), name="h-" + s)
            pc.publish("a.b.c.d.e.f", {})
            pc.publish("a.b.c.d", {})
            wait_for(lambda: len(got["a.b.c"]) >= 2 and len(got["a.b.c.d"]) >= 2)
            time.sleep(0.3)
            return {k: sorted(v) for k, v in got.items()}
        finally:
            pc.shutdown()

    def test_off_misses_deep_prefix(self):
        d = self._deliveries()
        self.assertEqual(d["a.b.c"], [])
        self.assertEqual(d["a.b.c.d"], ["a.b.c.d"])

    def test_on_hears_every_prefix_exactly_once(self):
        d = self._deliveries(AKASHIC_POSTAL_PREFIX_ANY_DEPTH="1")
        self.assertEqual(d["a.b.c"], ["a.b.c.d", "a.b.c.d.e.f"])
        self.assertEqual(d["a.b.c.d"], ["a.b.c.d", "a.b.c.d.e.f"])
        self.assertEqual(d["a.b.c.d.e"], ["a.b.c.d.e.f"])


if __name__ == "__main__":
    unittest.main()
