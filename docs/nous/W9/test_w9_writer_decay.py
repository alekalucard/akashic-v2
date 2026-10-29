"""W9 tests: activation decay run by the one writer (switch AKASHIC_DECAY_IN_WRITER, OFF when unset).

Synthetic manifolds in a temp dir only. Never opens a real *.manifold. Imports only manifold_memory and portal_gate, whose
top level has no threads, sockets or file writes (checked: only imports, constants, threading.local/Lock, WeakSet).

W9_CODE_ROOT (env) points at the code/ tree under test, so the same suite runs against main's files (controls must fail),
against this branch, and against mutant copies.

    python -m unittest -v docs/nous/W9/test_w9_writer_decay.py
"""
import os
import sys
import shutil
import tempfile
import threading
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.environ.get("W9_CODE_ROOT") or os.path.normpath(os.path.join(_HERE, "..", "..", "..", "code"))
sys.path.insert(0, CODE)

from infrastructure import manifold_memory as mmem      # noqa: E402
from infrastructure import portal_gate as pg            # noqa: E402

SW = "AKASHIC_DECAY_IN_WRITER"


def _mk(d, name="s.manifold", cap=2000):
    return mmem.ManifoldMemory(os.path.join(d, name), node_capacity=cap, edge_capacity=100)


def _act(m, key):
    return m._read_node(m._key_index[key])[5]


def _fill(m, n=300):
    tracers = [0, mmem.TRACE_PERSONAL, mmem.TRACE_BOOKS, mmem.TRACE_SEEDED, mmem.TRACE_INFERENCE]
    for i in range(n):
        m.upsert_node("k%d" % i, activation=[0.5, 0.005, 0.0105, 1.0, 0.0][i % 5], tracer_id=tracers[i % len(tracers)])
    for i in range(n):
        s = m._key_index["k%d" % i]
        if i % 3 == 0:
            m.write_affect_coupling(s, 1.8)
        if i % 4 == 0:
            m.write_paradox_residue(s, 0.4)


class _Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="w9_")
        self._old = os.environ.pop(SW, None)
        self.addCleanup(self._restore)

    def _restore(self):
        os.environ.pop(SW, None)
        if self._old is not None:
            os.environ[SW] = self._old
        pg._PORTAL_GATES.clear() if hasattr(pg, "_PORTAL_GATES") else None
        pg._shared_gate = None
        shutil.rmtree(self.d, ignore_errors=True)

    def gate(self, m):
        return pg.LocalManifoldGate(m)

    def fake_interior(self, open_=True):
        """A real PortalGate object (constructor only: no spawn, no socket), marked open with a tunnel, as B's is after
        PortalGate.open() succeeds."""
        g = pg.PortalGate(cards_path=os.path.join(self.d, "none.json"), portal_id="cortex")
        self._keep = getattr(self, "_keep", []) + [g]     # B holds its gate (self._portal_gate); the registry is weak
        if open_:
            g._is_open = True
            g._tunnels = [object()]
        return g


class TestW9(_Base):
    # ---- CONTROL: fails on main (nothing in the writer decays), passes here ----
    def test_control_writer_decays_when_on(self):
        m = _mk(self.d)
        m.upsert_node("habit", activation=0.5)
        g = self.gate(m)
        os.environ[SW] = "1"
        # on main the gate has no such method: the call is a no-op and the habit must still fade -> assertion fails
        call = getattr(g, "maybe_writer_decay", lambda beat, tau: "absent")
        for b in range(0, 1000, 10):                    # the maintenance loop, ~every 10 beats (~10 s apart in real life)
            if call(b, 1.0) == "started":
                g._writer_decay._thread.join(10)        # a real pass finishes long before the next 10 s cycle
        self.assertAlmostEqual(_act(m, "habit"), 0.5 - 0.001 * 3, places=5)   # 1000 beats / 250 = passes at 250,500,750

    # ---- switch default ----
    def test_off_when_unset(self):
        m = _mk(self.d)
        m.upsert_node("habit", activation=0.5)
        g = self.gate(m)
        self.assertFalse(pg.writer_decay_on())
        for b in range(0, 5000, 10):
            self.assertEqual(g.maybe_writer_decay(b, 1.0), "off")
        self.assertAlmostEqual(_act(m, "habit"), 0.5, places=6)
        self.assertIsNone(getattr(g, "_writer_decay", None))

    def test_off_for_other_values(self):
        m = _mk(self.d)
        m.upsert_node("habit", activation=0.5)
        g = self.gate(m)
        for v in ("0", "", "true", "yes", "on", " 1", "1 ", "2"):
            os.environ[SW] = v
            self.assertFalse(pg.writer_decay_on(), v)
            self.assertEqual(g.maybe_writer_decay(10 ** 6, 1.0), "off")
        self.assertAlmostEqual(_act(m, "habit"), 0.5, places=6)

    # ---- same decay as the interior, byte for byte, exemptions included ----
    def test_equivalent_to_decay_all_bytes(self):
        a, b = _mk(self.d, "a.manifold"), _mk(self.d, "b.manifold")
        os.environ[SW] = "1"
        old = mmem.ManifoldMemory._AFFECT_DECAY
        mmem.ManifoldMemory._AFFECT_DECAY = 0.1
        try:
            _fill(a)
            _fill(b)
            for _ in range(3):
                a.decay_all(0.001)
                wd = pg.WriterDecay(b, chunk=7, pause_s=0)
                self.assertEqual(wd.run_pass()["status"], "done")
        finally:
            mmem.ManifoldMemory._AFFECT_DECAY = old
        self.assertEqual(a._key_index, b._key_index)
        R = mmem.ManifoldMemory._RESERVED_OFFSET
        for k, s in a._key_index.items():
            ra, rb = list(a._read_node(s)), list(b._read_node(s))
            ra[8] = rb[8] = 0                     # last_access: upsert stamps wall time, the two files were filled apart
            self.assertEqual(ra, rb, k)
            o = mmem.HEADER_SIZE + s * mmem.NODE_RECORD_SIZE
            self.assertEqual(bytes(a._mm[o + R:o + mmem.NODE_RECORD_SIZE]), bytes(b._mm[o + R:o + mmem.NODE_RECORD_SIZE]), k)
        self.assertTrue(any(_act(b, "k%d" % i) not in (0.5, 0.005, 0.0105, 1.0, 0.0) for i in range(300)))

    def test_affect_exemptions_kept(self):
        m = _mk(self.d)
        os.environ[SW] = "1"
        old = mmem.ManifoldMemory._AFFECT_DECAY
        mmem.ManifoldMemory._AFFECT_DECAY = 0.5
        try:
            for k, t in (("me", mmem.TRACE_PERSONAL), ("seed", mmem.TRACE_SEEDED), ("book", mmem.TRACE_BOOKS)):
                m.upsert_node(k, activation=0.5, tracer_id=t)
                m.write_affect_coupling(m._key_index[k], 2.0)
            pg.WriterDecay(m, pause_s=0).run_pass()
        finally:
            mmem.ManifoldMemory._AFFECT_DECAY = old
        ac = {k: m.read_affect_coupling(m._key_index[k]) for k in ("me", "seed", "book")}
        self.assertAlmostEqual(ac["me"], 2.0, places=5)
        self.assertAlmostEqual(ac["seed"], 2.0, places=5)
        self.assertAlmostEqual(ac["book"], 1.5, places=5)

    def test_writes_only_activation_not_a_stale_record(self):
        """A concurrent upsert/link that changed count/degree/flags between decay's read and write must not be undone."""
        m = _mk(self.d)
        m.upsert_node("habit", activation=0.5, count=3)
        os.environ[SW] = "1"
        s = m._key_index["habit"]
        real_read = m._read_node

        def stale_read(slot):
            r = list(real_read(slot))
            r[6] = 999                      # a stale/other count value the decay must never write back
            r[9] = mmem.FLAG_DELETED        # and a flag it must never write back
            return tuple(r)
        m._read_node = stale_read
        try:
            self.assertEqual(m.decay_keys(["habit"], 0.001), 1)
        finally:
            m._read_node = real_read
        r = m._read_node(s)
        self.assertNotEqual(r[6], 999)
        self.assertEqual(r[9], mmem.FLAG_ACTIVE)
        self.assertAlmostEqual(r[5], 0.499, places=5)

    def test_unsupported_graph(self):
        os.environ[SW] = "1"

        class Store:
            __slots__ = ("filepath",)                    # refuses setattr, like a foreign store might
        st = Store()
        st.filepath = os.path.join(self.d, "x")
        g = pg.LocalManifoldGate(st)
        for b in (0, 250, 10 ** 6):
            self.assertEqual(g.maybe_writer_decay(b, 1.0), "unsupported")

    def test_closed_manifold_stops_pass(self):
        m = _mk(self.d)
        for i in range(50):
            m.upsert_node("k%d" % i, activation=0.5)
        os.environ[SW] = "1"
        wd = pg.WriterDecay(m, chunk=10, pause_s=0)
        real = m.decay_keys
        calls = []

        def spy(keys, rate):
            calls.append(1)
            n = real(keys, rate)
            if len(calls) == 1:
                m.close()                               # shutdown closes the manifold mid-pass
            return n
        m.decay_keys = spy
        out = wd.run_pass()
        self.assertEqual((out["status"], out["decayed"]), ("aborted", 10))

    # ---- fades only, never deletes ----
    def test_never_deletes(self):
        m = _mk(self.d)
        _fill(m, 200)
        os.environ[SW] = "1"
        before_keys = dict(m._key_index)
        before_flags = {k: m._read_node(s)[9] for k, s in before_keys.items()}
        wd = pg.WriterDecay(m, chunk=13, pause_s=0, rate=0.3)
        for _ in range(10):
            wd.run_pass()
        self.assertEqual(dict(m._key_index), before_keys)
        self.assertEqual(m.node_count, 200)
        for k, s in before_keys.items():
            r = m._read_node(s)
            self.assertEqual(r[9], before_flags[k])
            self.assertGreaterEqual(r[5], 0.0)
            self.assertLessEqual(r[5], 0.0105)          # every active node faded to the floor or below, none removed

    # ---- never in two places at once ----
    def test_refuses_while_interior_alive(self):
        m = _mk(self.d)
        m.upsert_node("habit", activation=0.5)
        g = self.gate(m)
        os.environ[SW] = "1"
        itr = self.fake_interior(open_=True)
        self.assertTrue(pg.cortex_interior_alive())
        g.maybe_writer_decay(0, 1.0)
        self.assertEqual(g.maybe_writer_decay(250, 1.0), "interior_alive")
        self.assertEqual(g.maybe_writer_decay(10 ** 6, 1.0), "interior_alive")
        self.assertAlmostEqual(_act(m, "habit"), 0.5, places=6)
        # the interior closes (gate.close() sets _is_open False, clears tunnels): the writer takes over
        itr._is_open = False
        itr._tunnels = []
        self.assertFalse(pg.cortex_interior_alive())
        self.assertEqual(g.maybe_writer_decay(10 ** 6 + 250, 1.0), "started")
        g._writer_decay._thread.join(10)
        self.assertAlmostEqual(_act(m, "habit"), 0.499, places=5)

    def test_shared_portal_gate_counts_as_interior(self):
        os.environ[SW] = "1"
        itr = self.fake_interior(open_=True)
        pg._PORTAL_GATES.discard(itr)
        pg._shared_gate = itr
        self.assertTrue(pg.cortex_interior_alive())

    def test_other_interiors_do_not_count(self):
        itr = self.fake_interior(open_=True)
        itr._interior_script = os.path.join(self.d, "kv_cache_interior.py")   # portal_worker sub-portal
        self.assertFalse(pg.cortex_interior_alive())

    def test_unopened_gate_does_not_count(self):
        self.fake_interior(open_=False)
        self.assertFalse(pg.cortex_interior_alive())

    def test_check_error_means_alive(self):
        class Bad:
            pass
        bad = Bad()
        pg._PORTAL_GATES.add(bad)
        type(bad)._is_open = property(lambda s: (_ for _ in ()).throw(RuntimeError("x")))
        self.assertTrue(pg.cortex_interior_alive())

    def test_pass_stops_when_interior_appears_mid_pass(self):
        m = _mk(self.d)
        for i in range(100):
            m.upsert_node("k%d" % i, activation=0.5)
        os.environ[SW] = "1"
        wd = pg.WriterDecay(m, chunk=10, pause_s=0)
        real = m.decay_keys
        calls = []

        def spy(keys, rate):
            calls.append(len(keys))
            n = real(keys, rate)
            if len(calls) == 2:
                self.fake_interior(open_=True)      # B opens its gate between chunk 2 and 3
            return n
        m.decay_keys = spy
        out = wd.run_pass()
        self.assertEqual(out["status"], "aborted")
        self.assertEqual(out["decayed"], 20)
        faded = sum(1 for i in range(100) if _act(m, "k%d" % i) < 0.5)
        self.assertEqual(faded, 20)

    def test_single_flight(self):
        m = _mk(self.d)
        m.upsert_node("habit", activation=0.5)
        os.environ[SW] = "1"
        w1, w2 = pg.WriterDecay(m), pg.WriterDecay(m)
        w1.maybe_start(0)
        w2.maybe_start(0)
        self.assertTrue(pg._WD_PASS_LOCK.acquire(blocking=False))     # someone else holds a pass
        try:
            self.assertEqual(w2.maybe_start(250), "busy")
        finally:
            pg._WD_PASS_LOCK.release()
        self.assertAlmostEqual(_act(m, "habit"), 0.5, places=6)

    def test_two_gates_one_graph_share_one_cadence(self):
        m = _mk(self.d)
        m.upsert_node("habit", activation=0.5)
        os.environ[SW] = "1"
        g1, g2 = self.gate(m), self.gate(m)
        g1.maybe_writer_decay(0, 1.0)
        g2.maybe_writer_decay(0, 1.0)
        self.assertEqual(g1.maybe_writer_decay(250, 1.0), "started")
        g1._writer_decay._thread.join(10)
        self.assertEqual(g2.maybe_writer_decay(250, 1.0), "not_due")      # same pass already ran for this graph
        self.assertIs(g1._writer_decay, g2._writer_decay)
        self.assertAlmostEqual(_act(m, "habit"), 0.499, places=5)

    # ---- cadence: the interior's, translated to beats ----
    def test_interval_matches_interior(self):
        self.assertEqual([pg.interior_decay_interval(t) for t in (0, -3, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 20.0, 99.0)],
                         [50, 50, 50, 50, 33, 25, 20, 20, 20, 20])
        self.assertEqual(pg.writer_decay_period_beats(1.0), 250)
        self.assertEqual(pg.writer_decay_period_beats(6.0), 100)

    def test_interior_model_rate_matches_period(self):
        """Simulate the interior's rule (portal_interior.py _handle_tick: tick every 5 beats, every request bumps the
        counter, decay when counter % interval == 0) with random other traffic; its decays per beat ~ 1 / period."""
        import random
        rnd = random.Random(7)
        for tau in (1.0, 3.0, 8.0):
            iv = pg.interior_decay_interval(tau)
            cnt = 0
            decays = 0
            beats = 400000
            for beat in range(1, beats + 1):
                cnt += rnd.choice((0, 0, 1, 3, 17))     # other requests this beat
                if beat % 5 == 0:
                    cnt += 1                            # the tick request itself
                    if cnt % iv == 0:
                        decays += 1
            expect = beats / pg.writer_decay_period_beats(tau)
            self.assertLess(abs(decays - expect) / expect, 0.08, (tau, decays, expect))

    def test_fairy_hook_is_switch_gated(self):
        with open(os.path.join(CODE, "fairies", "P30_Cognition", "AssociationCortexFairy", "fairy.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        i = src.index("W9 WRITER DECAY")
        block = src[i:i + 1200]
        self.assertIn('if os.environ.get("AKASHIC_DECAY_IN_WRITER", "0") == "1":', block)
        self.assertIn("is _wd_region", block)
        self.assertLess(block.index('os.environ.get("AKASHIC_DECAY_IN_WRITER"'), block.index("maybe_writer_decay"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
