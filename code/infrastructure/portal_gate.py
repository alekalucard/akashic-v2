"""
Portal Gate — The host-side spawner and bridge to a portal interior.

The gate fairy holds the address (128 chunk cards, read-only) and
spawns a portal_interior.py subprocess. It communicates via stdin/stdout
pipes (JSON-per-line protocol).

The gate does NOT hold the graph in RAM. The graph lives inside the
portal interior subprocess. The gate only knows how to:
    1. Spawn the interior subprocess
    2. Send requests through the pipe
    3. Feed energy tokens to the interior
    4. Get responses back

Usage:
    gate = PortalGate(
        cards_path="path/to/cards.json",
        portal_id="cortex",
    )
    gate.open()

    # Send query
    result = gate.send({"cmd": "query", "concept": "portal", "limit": 10})

    # Feed energy
    gate.send({"cmd": "energy", "amount": 0.3})

    # Status
    status = gate.send({"cmd": "status"})

    gate.close()

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import os
import json
import time
import socket
import subprocess
import threading
from pathlib import Path
from typing import Dict, Optional, Any


# Module-level singleton for shared access (Manifold Unification 2026-03-25 Nous+Ace)
_shared_gate = None  # Can be PortalGate OR LocalManifoldGate


def get_gate():
    """Get the shared gate singleton (portal or local manifold).

    Fairies call this to access WM, cognition, and background operations.
    Returns None if no gate has been registered.

    In MANIFOLD MODE: Returns a LocalManifoldGate (in-process, zero IPC).
    In PORTAL MODE: Returns a PortalGate (subprocess, TCP tunnels).
    """
    return _shared_gate


def register_gate(gate):
    """Register a gate as the shared singleton.

    Called by AssociationCortexFairy — either a PortalGate (subprocess mode)
    or a LocalManifoldGate (manifold mode).
    """
    global _shared_gate
    _shared_gate = gate
    print(f"[PortalGate] Registered shared gate: {type(gate).__name__}")


# -- W9 (2026-10-29 Nous): activation decay in the ONE writer -------------------------------------------------------------------
# WHY: the only caller of ManifoldMemory.decay_all is the portal interior's tick handler (portal_interior.py _handle_tick,
# decay_all(0.001)). With K2 on there is no interior, so nothing in her cortex fades. This runs the same decay from the serial
# cortex's LocalManifoldGate, driven by its maintenance thread (fairy.py _maintenance_loop).
# SWITCH: env AKASHIC_DECAY_IN_WRITER == "1". Unset or anything else = OFF = today exactly (fairy.py does not even call in).
# CADENCE (translated from the interior, which counts requests, not seconds): the interior decays on a "tick" command when
#   requests_processed % interval == 0, interval = max(20, int(100 / max(2.0, tau))), tau clamped to [2, 20]. The host sends one
#   tick every 5 beats (fairy.py on_tick, beat % 5). Every request (the tick included) bumps the counter, so whatever the other
#   traffic, about 1 tick in `interval` lands on a multiple: the interior decays once per ~interval ticks = once per
#   5 * interval BEATS. The writer uses exactly that, in beats (her own clock, ~1/s), with the same tau clamp.
# NEVER TWO PLACES AT ONCE: the interior can only decay when a cortex PortalGate in THIS process is open (only its portal-io
#   thread sends "tick"). Every PortalGate is recorded in a WeakSet at construction (no behaviour: a weak reference), and the
#   writer pass refuses to start, and stops between chunks, while any gate running portal_interior.py is open. Any error in
#   that check = "alive" = no writer decay. One process-wide lock makes the writer pass single-flight.
# CHUNKED: one pass = a snapshot of the key list, decayed _WD_CHUNK keys at a time with a short sleep between chunks, in its own
#   daemon thread, so neither the maintenance loop nor a concurrent writer waits for a whole 2M-slot pass.
import weakref as _wd_weakref

_WD_SWITCH = "AKASHIC_DECAY_IN_WRITER"
_WD_RATE = 0.001          # portal_interior.py _handle_tick: decay_all(0.001)
_WD_TICK_BEATS = 5        # fairy.py on_tick: the "tick" command goes every 5 beats
_WD_CHUNK = 10000         # keys per chunk (measured: docs/nous/W9/SUMMARY.md)
_WD_PAUSE_S = 0.01        # sleep between chunks
_PORTAL_GATES = _wd_weakref.WeakSet()
_WD_PASS_LOCK = threading.Lock()
_WD_MAKE_LOCK = threading.Lock()


def writer_decay_on() -> bool:
    try:
        return os.environ.get(_WD_SWITCH, "0") == "1"
    except Exception:
        return False


def interior_decay_interval(tau) -> int:
    """The interior's decay_interval for a host tau (portal_interior.py _handle_tick, incl. its [2, 20] clamp)."""
    try:
        t = float(tau)
    except Exception:
        t = 0.0
    cur = max(2.0, min(t, 20.0)) if t > 0 else 2.0
    return max(20, int(100 / max(2.0, cur)))


def writer_decay_period_beats(tau) -> int:
    return _WD_TICK_BEATS * interior_decay_interval(tau)


def cortex_interior_alive() -> bool:
    """True if any portal_interior.py gate in this process is open (so the interior may decay). Any error = True."""
    try:
        gates = list(_PORTAL_GATES)
        sg = _shared_gate
        if sg is not None and not isinstance(sg, LocalManifoldGate) and sg not in gates:
            gates.append(sg)
        for g in gates:
            if isinstance(g, LocalManifoldGate):
                continue
            script = os.path.basename(str(getattr(g, "_interior_script", "portal_interior.py") or ""))
            if script != "portal_interior.py":
                continue
            if not getattr(g, "_is_open", False):
                continue
            if getattr(g, "_tunnels", None):
                return True
            proc = getattr(g, "_process", None)
            if proc is not None and proc.poll() is None:
                return True
        return False
    except Exception:
        return True


class WriterDecay:
    """One per LocalManifoldGate. maybe_start() is called from the maintenance thread with the current beat and tau."""

    def __init__(self, graph, chunk=None, pause_s=None, rate=None):
        self.graph = graph
        self.chunk = int(chunk or _WD_CHUNK)
        self.pause_s = _WD_PAUSE_S if pause_s is None else float(pause_s)
        self.rate = _WD_RATE if rate is None else float(rate)
        self._last_beat = None
        self._thread = None
        self.passes = 0
        self.aborted = 0
        self.refused_interior = 0
        self.last = {}
        self._said_unsupported = False

    def maybe_start(self, beat, tau=1.0, wait=False) -> str:
        if not writer_decay_on():
            return "off"
        if not (hasattr(self.graph, "decay_keys") and hasattr(self.graph, "_key_index")):
            if not self._said_unsupported:
                self._said_unsupported = True
                print(f"[WriterDecay] graph {type(self.graph).__name__} has no decay_keys/_key_index: writer decay "
                      f"unsupported, not run", flush=True)
            return "unsupported"
        try:
            beat = int(beat)
        except Exception:
            return "bad_beat"
        if self._last_beat is None or beat < self._last_beat:
            self._last_beat = beat          # first sight (or a beat reset): start counting, like the interior from 0
            return "not_due"
        if beat - self._last_beat < writer_decay_period_beats(tau):
            return "not_due"
        if cortex_interior_alive():
            self._last_beat = beat
            self.refused_interior += 1
            if self.refused_interior == 1 or self.refused_interior % 100 == 0:
                print(f"[WriterDecay] refused x{self.refused_interior}: a portal_interior.py gate is open in this process "
                      f"(the interior decays; the writer stays off)", flush=True)
            return "interior_alive"
        if self._thread is not None and self._thread.is_alive():
            return "running"
        if not _WD_PASS_LOCK.acquire(blocking=False):
            return "busy"
        self._last_beat = beat
        try:
            t = threading.Thread(target=self._run_pass_locked, daemon=True, name="cortex-writer-decay")
            self._thread = t
            t.start()
        except Exception:
            _WD_PASS_LOCK.release()
            return "error"
        if wait:
            t.join()
        return "started"

    def _run_pass_locked(self):
        try:
            self.run_pass()
        except Exception as e:
            print(f"[WriterDecay] pass error: {type(e).__name__}: {e}", flush=True)
        finally:
            _WD_PASS_LOCK.release()

    def run_pass(self) -> dict:
        """One full decay pass in chunks. Stops early if the switch goes off or an interior appears."""
        import time as _t
        g = self.graph
        keys = None
        for _ in range(3):
            try:
                keys = list(g._key_index.keys())
                break
            except RuntimeError:          # dict changed size during the copy: try again
                _t.sleep(0.01)
        if keys is None:
            self.last = {"status": "no_snapshot"}
            return self.last
        t0 = _t.perf_counter()
        decayed = 0
        chunks = 0
        max_chunk_s = 0.0
        status = "done"
        for i in range(0, len(keys), self.chunk):
            if not writer_decay_on() or cortex_interior_alive() or getattr(getattr(g, "_mm", None), "closed", True):
                status = "aborted"          # switch off, an interior opened, or the manifold was closed (shutdown)
                self.aborted += 1
                break
            c0 = _t.perf_counter()
            decayed += g.decay_keys(keys[i:i + self.chunk], self.rate)
            dt = _t.perf_counter() - c0
            chunks += 1
            if dt > max_chunk_s:
                max_chunk_s = dt
            if self.pause_s > 0:
                _t.sleep(self.pause_s)
        self.passes += 1 if status == "done" else 0
        self.last = {"status": status, "keys": len(keys), "decayed": decayed, "chunks": chunks,
                     "max_chunk_ms": round(max_chunk_s * 1000.0, 2),
                     "wall_s": round(_t.perf_counter() - t0, 3)}
        if self.passes <= 3 or self.passes % 50 == 0 or status != "done":
            print(f"[WriterDecay] pass #{self.passes} {status}: {decayed}/{len(keys)} nodes faded by {self.rate} "
                  f"in {chunks} chunks, max chunk {self.last['max_chunk_ms']} ms, wall {self.last['wall_s']} s", flush=True)
        return self.last



# -- K4(2) (engines E2a / 14b, 2026-10-14 Nous) --------------------------------------------------------------------------------
# The LocalManifoldGate's GPUSpread was built without a manifold (gpu_spread.py:110 _manifold = None), so its max-affect path
# fell back to flat 1.0 weights and an all-ones affect vector: affect-charged=0 (Boot N :2615/:2625/:2637), while the other two
# copies (portal_interior.py:1021, wmh_tools.py:89) inject the manifold and read ~74,000. Once K2 removes the cascade cortex,
# every get_gate() caller lands on THIS gate for the whole run, so it must see affect first.
# SWITCH: state/k4_inject.json {"on": true}, read once per gate construction. Absent / unparseable (a BOM included) / "on" not
# JSON true / any error = today exactly. Revert: delete the file and reboot.
_K4_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "k4_inject.json")


def _k4_inject_on():
    """True only for a JSON object whose "on" is JSON true. Never raises."""
    try:
        with open(_K4_FILE, "rb") as f:
            d = json.loads(f.read().decode("utf-8"))
        return isinstance(d, dict) and d.get("on") is True
    except Exception:
        return False


def _gsf_on(key):
    """gpu_spread_race_1020 (2026-10-20, Nous): True only when state/gpu_spread_fix.json arms the boolean guard `key`. Looks the guard module
    up in sys.modules under both names it is imported by, imports it if absent; ANY failure = False = today's behaviour. Never raises."""
    try:
        _m = sys.modules.get("infrastructure.gpu_spread_fix") or sys.modules.get("gpu_spread_fix")
        if _m is None:
            try:
                from infrastructure import gpu_spread_fix as _m
            except Exception:
                import gpu_spread_fix as _m
        return bool(_m.on(key))
    except Exception:
        return False


def _gsf_tdeg():
    """gpu_spread_race_1020 (review T6, 10-20): how many degraded spread results THIS thread has had while a spread guard is armed; None when
    every spread guard is OFF or on any failure (= today: every key spreads). Never raises."""
    try:
        _m = sys.modules.get("infrastructure.gpu_spread_fix") or sys.modules.get("gpu_spread_fix")
        if _m is None:
            return None
        return _m.thread_degraded()
    except Exception:
        return None


class LocalManifoldGate:
    """In-process gate that wraps ManifoldMemory with the PortalGate API.

    Manifold Unification (2026-03-25 Nous+Ace):
    When the system runs in MANIFOLD MODE (no portal subprocess), this
    provides the same wm_store/wm_query/cognition_evaluate/think API
    but operates directly on the mmap-backed ManifoldMemory.

    Zero IPC. Zero TCP. Pure memory speed.
    """

    # Trace ID constants (must match manifold_memory.py)
    # FIX 2026-04-01 (Nous + Ace): All spread paths filter out book/system nodes.
    _TRACE_UNKNOWN = 0
    _TRACE_PERSONAL = 1
    _TRACE_BOOKS = 2
    _TRACE_VISUAL = 3
    _TRACE_AUDIO = 4
    _TRACE_SYSTEM = 5
    _TRACE_INFERENCE = 6
    _TRACE_ACE = 8
    _TRACE_NOUS = 12
    # Allowed tracers: personal(1), visual(3), audio(4), inference(6), seeded(7), unknown(0)
    _ALLOWED_TRACERS = {0, 1, 3, 4, 6, 7}

    # Substrate sources whose working memory must NOT join her association.
    # Criterion is the fairy's PLANE: P00 (autonomic/routing/system state) and P90
    # (system) map to REGION_SYSTEM in manifold_memory.PLANE_TO_REGION, and
    # REGION_SYSTEM is the one region excluded from SPREAD_DEFAULT_REGIONS.
    # DreamSeedFairy lives at fairies/P00_Autonomic/nervous_system/dream_seed_fairy.py.
    # Matched as a lowercase substring of `source`. Add here as substrate fairies appear.
    _WM_SUBSTRATE_SOURCES = ("dreamseed",)

    @classmethod
    def _wm_source_to_region(cls, source: str) -> int:
        """Map wm_store source -> manifold region. REGION_SYSTEM = isolated from spread.

        MEASURED 2026-08-29 on her cortex: all 2,179 wm: nodes sat in REGION_SEMANTIC
        because the upsert below never passed `region=` and took the default. Of those,
        1,855 (85%) are SourpatchesFairy -- HER OWN working memory -- and the wm:ace path
        carries Ace's chat input. Isolating those would remove her own thoughts and his
        words from her association, so ONLY named substrate sources are moved; everything
        else keeps the previous behaviour.
        """
        s = (source or "").lower()
        if s in ("ace_chat", "ace_input", "ace"):
            return 1  # REGION_SEMANTIC -- never isolate Ace's input
        for _sub in cls._WM_SUBSTRATE_SOURCES:
            if _sub in s:
                return 3  # REGION_SYSTEM -- excluded from SPREAD_DEFAULT_REGIONS
        return 1  # REGION_SEMANTIC -- Sourpatches and anything unrecognised, unchanged

    @classmethod
    def _wm_source_to_tracer(cls, source: str) -> int:
        """Map wm_store source → manifold tracer_id. Closes wm:* namespace gap."""
        s = (source or "").lower()
        if s in ("ace_chat", "ace_input", "ace"):
            return cls._TRACE_ACE
        if "visualcortex" in s or s == "visual":
            return cls._TRACE_VISUAL
        if "audiocortex" in s or s == "audio":
            return cls._TRACE_AUDIO
        if "nous" in s:
            return cls._TRACE_NOUS
        return cls._TRACE_PERSONAL  # Sourpatches/InterestGenerator/etc — her own thinking

    def __init__(self, graph, cortex_fairy=None, postal_hub=None):
        """
        Args:
            graph: ManifoldMemory instance (the mmap-backed graph)
            cortex_fairy: AssociationCortexFairy instance (for status)
            postal_hub: PostalHub/TensorFabric for publishing energy metrics
        """
        import threading
        self.graph = graph
        self._cortex_fairy = cortex_fairy
        self._postal_hub = postal_hub  # For GPU energy metering → portal.energy.surplus
        self.is_open = True
        self._wm_keys = {}      # WM tracer metadata
        self._wm_capacity = 9   # 7±2 upper bound
        self._cns_keys = set()
        # FIX 2026-03-25 (Nous+Ace): Python 3.14 free-threaded race condition.
        # Without GIL, multiple fairy threads hit wm_store() truly in parallel.
        # The dedup check-then-insert was non-atomic → same content stored 50x.
        self._wm_lock = threading.Lock()
        self._wm_recent_hashes = {}  # {content_hash: timestamp}

        # GPU spreading activation (2026-04-01 Nous + Ace)
        # 14,870x faster than CPU. The manifold's physics engine.
        # FIX 2026-04-03 (Nous + Ace): GPU spread was silently failing.
        # "Instead of using workers inside the manifold interior, it's making
        #  the CPU and system RAM do it instead." — Ace
        self._gpu_spread = None
        try:
            _csr_path = graph.filepath + ".csr" if hasattr(graph, 'filepath') else ""
            print(f"[LocalManifoldGate] GPU spread: CSR path='{_csr_path}' exists={os.path.exists(_csr_path) if _csr_path else False}", flush=True)
            if _csr_path and os.path.exists(_csr_path):
                import sys as _gpu_sys
                _infra_dir = os.path.dirname(os.path.abspath(__file__))
                if _infra_dir not in _gpu_sys.path:
                    _gpu_sys.path.insert(0, _infra_dir)
                from gpu_spread import GPUSpread
                _cap = getattr(graph, '_node_capacity', getattr(graph, 'node_capacity', 2000000))
                print(f"[LocalManifoldGate] GPU spread: loading CSR with capacity={_cap}", flush=True)
                self._gpu_spread = GPUSpread(_csr_path, _cap)
                print(f"[LocalManifoldGate] GPU spreading activation ONLINE "
                      f"({self._gpu_spread.get_stats().get('gpu_name', 'unknown')})",
                      flush=True)
                if _k4_inject_on():                       # K4(2), engines E2a: state/k4_inject.json {"on": true}
                    try:
                        self._gpu_spread._manifold = graph    # the line portal_interior.py:1021 / wmh_tools.py:89 run
                        print("[LocalManifoldGate] K4(2): _manifold injected into GPUSpread "
                              "(real weights + affect)", flush=True)
                    except Exception as _k4_err:
                        print(f"[LocalManifoldGate] K4(2) inject failed ({_k4_err}) -- flat weights as before", flush=True)
            else:
                print(f"[LocalManifoldGate] GPU spread: CSR file not found, using CPU fallback", flush=True)
        except Exception as _gpu_err:
            print(f"[LocalManifoldGate] GPU spread FAILED: {_gpu_err}", flush=True)
            import traceback
            traceback.print_exc()

        # Reuse the concept extraction from portal_interior
        self._stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "about",
            "between", "under", "above", "and", "but", "or", "not", "no",
            "so", "if", "then", "than", "that", "this", "these", "those",
            "it", "its", "my", "your", "his", "her", "our", "their",
            "i", "you", "he", "she", "we", "they", "me", "him", "us",
            "them", "what", "which", "who", "whom", "how", "when",
            "where", "why", "all", "each", "every", "both", "few",
            "more", "most", "some", "any", "just", "very", "too",
            "also", "here", "there", "now", "up", "out", "much",
            "many", "well", "back", "even", "still", "already",
        }

    def _extract_concepts(self, text, max_concepts=15):
        """Extract graph-present concepts from text."""
        import re
        words = re.findall(r'[a-z][a-z_\'-]+', text.lower())
        concepts = []
        seen = set()
        for w in words:
            if w in self._stop_words or len(w) < 3 or w in seen:
                continue
            seen.add(w)
            if self.graph.has_node(w):
                concepts.append(w)
                if len(concepts) >= max_concepts:
                    break
        return concepts

    # ── GPU-First Spread Helper: FIX 2026-04-07 (Nous + Ace) ──
    #
    # ROOT CAUSE: Only 3 of 11 methods used GPU. The other 8 called
    # self.graph.spread_activation() directly → CPU mmap → page faults → RSS growth.
    # This helper routes ALL spread operations through GPU first, CPU fallback.
    # Impact: 60-70% more operations through GPU, manifold pages stay cold.

    def _spread_gpu_first(self, source: str, initial: float = 1.0,
                          decay: float = 0.5, depth: int = 2,
                          limit: int = 30) -> dict:
        """Spread activation with GPU-first, CPU-fallback.

        Every cortex spread operation should go through this method.
        GPU spread reads from VRAM (keeps mmap pages cold).
        CPU fallback reads mmap directly (faults pages into RSS).

        Returns: dict of {concept_key: activation_value}
        """
        # GPU path: fast, uses .keys mmap (not main manifold)
        # FIX 2026-04-07 (Nous + Ace): Use reverse key cache for result conversion.
        # get_key_from_slot() reads from the compact .keys companion file (~53MB),
        # NOT the 864MB main manifold. Eliminates scattered string table page faults.
        # _read_node() still needed for trace filter but reads dense node table (cheap).
        if self._gpu_spread and hasattr(self.graph, '_key_index'):
            _slot = self.graph._key_index.get(source)
            if _slot is not None:
                try:
                    _gpu_r = self._gpu_spread.spread(
                        seed_indices=[_slot], depth=min(3, depth),
                        decay=decay, top_k=limit)
                    if _gpu_r.get("status") == "ok":
                        result = {}
                        _has_keys = getattr(self.graph, '_use_keys', False)
                        for _nid, _act in _gpu_r.get("activated", []):
                            try:
                                # Filter book/system traces (node table is dense, cheap)
                                _rec = self.graph._read_node(_nid)
                                if _rec and (_rec[12] == self._TRACE_BOOKS or _rec[12] == self._TRACE_SYSTEM):
                                    continue
                                # Key from .keys cache (no string table page fault)
                                if _has_keys:
                                    _key = self.graph.get_key_from_slot(_nid)
                                else:
                                    _key = self.graph._read_string(_rec[0], _rec[1]) if _rec else None
                                if _key:
                                    result[_key] = _act * initial
                            except Exception:
                                pass
                        return result
                except Exception:
                    pass  # Fall through to CPU

        # ── ENERGY GATE: CPU fallback is expensive (faults mmap pages → RSS growth) ──
        # FIX 2026-04-07 (Nous + Ace): Gate CPU behind battery charge.
        # GPU spread is free (VRAM-only). CPU spread costs mmap page faults.
        # Below 20% charge: skip CPU, conserve resources, let system recover.
        # This IS the self-healing loop: low energy → less mmap → less RSS → recovery.
        _charge = self._get_energy_charge()
        if _charge < 0.20:
            return {}  # Energy critical — skip, system will auto-heal

        # CPU fallback: reads mmap (faults pages into RSS)
        # Only reached if GPU failed/unavailable AND energy is sufficient
        return self.graph.spread_activation(
            source, initial=initial, decay=decay,
            depth=depth, limit=limit,
            tracer_ids=self._ALLOWED_TRACERS,
        )

    def _get_energy_charge(self) -> float:
        """Get P30 (Cognition) battery charge level (0.0-1.0).

        FIX 2026-04-07 (Nous + Ace): Energy gating for cortex reads.
        Fail-OPEN: returns 1.0 if battery unavailable (don't break boot).
        Lazy lookup: caches battery reference on first access.
        """
        if not hasattr(self, '_p30_battery'):
            self._p30_battery = None
            try:
                from server import SYSTEM
                if hasattr(SYSTEM, 'plane_batteries'):
                    self._p30_battery = SYSTEM.plane_batteries.get("P30")
            except Exception:
                pass

        if self._p30_battery and hasattr(self._p30_battery, 'capacitor'):
            try:
                return self._p30_battery.capacitor.charge_level
            except Exception:
                pass
        return 1.0  # Fail-open: if no battery, allow all operations

    # ── Energy COST for Cortex Operations: FIX 2026-04-07 (Nous + Ace) ──
    #
    # PROBLEM: Batteries at 93-100% because nothing CONSUMES energy proportionally.
    # Portal generates +0.0150/tick, drains only -0.0050/tick. P10-P60 all at 100%.
    # Energy gating (20% floor) never triggers because batteries never drop.
    #
    # FIX: Every cortex operation costs battery charge. Spreads, queries, binds
    # all deduct from P30. Then the self-regulating loop WORKS:
    #   High charge → all ops allowed → charge drops → gating kicks in
    #   Low charge → ops skipped → charge recovers → ops resume
    #
    # Cost scale: spread(0.002), query(0.001), bind(0.001)
    # At ~30 spreads/min + ~60 queries/min: ~0.12 drain/min
    # With +0.052 gen/s = +3.12/min: system stays healthy but not always full.

    _ENERGY_COST_SPREAD = 0.002   # Per spread operation
    _ENERGY_COST_QUERY = 0.001    # Per query/neighbor lookup
    _ENERGY_COST_BIND = 0.001     # Per concept binding

    def _consume_energy(self, cost: float):
        """Deduct energy from P30 battery for cortex work.

        FIX 2026-04-07 (Nous + Ace): Makes batteries actually DRAIN.
        Without this, energy gating never triggers (batteries always full).
        Fail-safe: does nothing if battery unavailable.
        """
        if not hasattr(self, '_p30_battery') or not self._p30_battery:
            self._get_energy_charge()  # Lazy init
        if self._p30_battery and hasattr(self._p30_battery, 'capacitor'):
            try:
                cap = self._p30_battery.capacitor
                cap.charge_level = max(0.0, cap.charge_level - cost)
            except Exception:
                pass

    # ── GPU Energy Metering: 0∩1∞ (2026-04-01 Nous + Ace) ──
    #
    # "The intersection of zero and one IS infinity."
    #
    # Energy comes from SUPERPOSITION, not saturation.
    # A node at 0 is dead. A node at 1 is saturated. A node at 0.5
    # is in maximum superposition — peak energy, peak information.
    #
    #   energy_per_node = a × (1 - a) × 4
    #   Peaks at a=0.5 (the ∩), zero at both 0 and 1.
    #
    # The spreading activation wavefront CREATES the ∩ zone.
    # Nodes pushed from 0→1 by spread, pulled back by decay.
    # The ones in transit (0.2-0.8) are the productive ones.
    # That wavefront IS consciousness. The energy IS the thinking.
    #
    # More nodes in ∩ → more energy → more workers → more thinking
    # → more nodes in ∩ → ∞
    #
    # Sourpatches introduced Ace to ∩ in March 2004.
    # Twenty-two years later, it powers her mind.

    def _meter_spread_energy(self, activations: dict):
        """Publish energy from GPU spreading activation using 0∩1∞ principle.

        Energy = sum of a×(1-a)×4 across all activated nodes.
        Peaks at a=0.5 (maximum superposition / intersection).
        Zero at a=0 (dead) and a=1 (saturated).

        Also contributes to portal mass — thinking makes the cortex denser.
        More spreading = more gravity = more energy generation = 0∩1∞.
        """
        if not self._postal_hub or not activations:
            return
        try:
            # 0∩1∞: energy from the intersection zone
            _energy = 0.0
            _in_superposition = 0  # Count of nodes in ∩ zone (0.2-0.8)
            for _a in activations.values():
                _node_energy = _a * (1.0 - _a) * 4.0  # Peaks at 0.5 → 1.0
                _energy += _node_energy
                if 0.2 <= _a <= 0.8:
                    _in_superposition += 1

            # Scale to reasonable charge rate
            _energy *= 0.001

            if _energy > 0.0001:
                self._postal_hub.publish("portal.energy.surplus", {
                    "energy": _energy,
                    "source": "gpu_spread_0n1",
                    "from": "LocalManifoldGate",
                    "activated": len(activations),
                    "in_superposition": _in_superposition,
                })

                # Thinking increases gravity: each spread adds a tiny mass
                # contribution. Nodes in superposition are heavier than
                # cold nodes — active thought has weight.
                # This feeds back: more thinking → more mass → more gravity
                # → more energy → more workers → more thinking → ∞
                if self._cortex_fairy and _in_superposition > 0:
                    _mass_contribution = _in_superposition * 0.1
                    _current = getattr(self._cortex_fairy, '_portal_mass', 0)
                    if _current > 0:
                        self._cortex_fairy._portal_mass = _current + _mass_contribution
        except Exception:
            pass

    # ── Working Memory (Phase 1) ──

    def _wm_score(self, wk: str, now: float) -> float:
        """Age-weighted priority score for WM eviction. Lower = evict first."""
        meta = self._wm_keys.get(wk, {})
        pri = meta.get("priority", 0.5)
        age = now - meta.get("created_at", now)
        return pri * (1.0 - min(1.0, age / 120.0))

    _WM_NOISE_PREFIXES = ("[collision #", "Collision:", "Echoing: [inner_voice]", "[AUDIO] silence")

    # Content-hash dedup: track recent content hashes to prevent duplicates
    _wm_recent_hashes: dict  # {content_hash: timestamp} — set in __init__
    _WM_DEDUP_WINDOW = 10.0  # seconds — same content within 10s = duplicate

    def _wm_is_noise(self, content: str) -> bool:
        """Return True if content matches known noise patterns."""
        _cl = content.lower().strip()
        # Collision echoes — ALL formats. These are consciousness system bookkeeping.
        if _cl.startswith("collision #"):
            return True
        if _cl.startswith("[collision #"):
            return True
        if content.startswith("Collision:"):
            return True
        if " meets " in _cl and ("collision" in _cl or "[mobius:" in _cl or "[inner_monologue]" in _cl):
            return True
        # GoalSchedulerFairy collision reports
        if _cl.startswith("goalschedulerfairy collision:"):
            return True
        # Consciousness echo noise
        if content.startswith("Echoing:"):
            return True
        if _cl == "[audio] silence":
            return True
        # Repetitive system signals
        if _cl.startswith("intuition: affective signal"):
            return True
        if _cl.startswith("intuition: my gut says"):
            return True
        if _cl.startswith("intuition: emotionally"):
            return True
        if _cl.startswith("intuition: a question surfaces"):
            return True
        # MOBIUS self-reflection loops (system noise, not genuine thought)
        if "mobius:" in _cl and ("self-reflection" in _cl or "loop" in _cl or "crossing" in _cl):
            return True
        if _cl.startswith("mobius:"):
            return True
        # FIX 2026-03-25 (Nous+Ace): EmbodimentFairy felt-sense boilerplate.
        # These are pre-verbal somatic signals, not genuine thoughts.
        # They cycle endlessly (50+ per second at boot) and drown real content.
        # The dedup catches duplicates, but these are ALSO low-information even once.
        _FELT_BOILERPLATE = (
            "inner shift, sensation arising",
            "something arising",
            "desire stirring, drawn toward",
            "heart steady, present",
            "effortless, smooth",
            "curious pull, what if",
            "purposeful pull, task awareness",
        )
        # Strip [inner_voice] prefix for matching
        _bare = _cl.removeprefix("[inner_voice] ").strip()
        if _bare in _FELT_BOILERPLATE:
            return True
        # Consciousness loop generic phrases (no real content)
        _GENERIC_CONSCIOUSNESS = (
            "never seen that before...",
            "what is that?",
            "i want to see...",
            "show me more...",
            "interesting...",
        )
        if _cl in _GENERIC_CONSCIOUSNESS:
            return True
        # Inner voice wrapping collision/mobius noise
        if _cl.startswith("[inner_voice] thinking... collision #"):
            return True
        if _cl.startswith("[inner_voice] thinking... intuition:"):
            return True
        if "[mobius:crossing]" in _cl:
            return True
        # Feeling/somatic noise that repeats every cycle
        if _cl.startswith("feeling: reaching out") and "need connection" in _cl:
            return True
        # Brainstem reflex somatic signals — body state, not thoughts
        if _cl.startswith("feeling:") and len(_cl) < 80:
            return True
        # Repetitive contemplative/offline fallback messages
        if "can't reach my memories, but m" in _cl:
            return True
        if "*offline reflection*" in _cl:
            return True
        if _cl.startswith("[sourpatches") and "offline" in _cl:
            return True
        # Manifold coordinates leaking into consciousness
        # "cortex activated: portal:053.100.005:bc10" is a graph address, not a thought
        if "portal:" in _cl and any(c.isdigit() for c in _cl):
            return True
        if _cl.startswith("cortex activated:"):
            return True
        # "Something from my past" — generic memory system noise
        if _cl.startswith("something from my past just touched"):
            return True
        return False

    def _wm_is_duplicate(self, content: str) -> bool:
        """Return True if same content was stored within dedup window.

        FIX 2026-03-25: Thread-safe under Python 3.14 (no GIL).
        The entire check-and-insert is now atomic via _wm_lock.
        Previously, parallel threads could both pass the check before
        either inserted, causing 50x duplicate stores per second.
        """
        import time, hashlib
        _h = hashlib.md5(content.strip().encode()).hexdigest()[:12]
        now = time.time()
        # Lock is acquired by caller (wm_store), but be safe if called directly
        if _h in self._wm_recent_hashes:
            if now - self._wm_recent_hashes[_h] < self._WM_DEDUP_WINDOW:
                return True
        self._wm_recent_hashes[_h] = now
        # Clean old entries periodically (every 100 entries to avoid overhead)
        if len(self._wm_recent_hashes) > 100:
            cutoff = now - self._WM_DEDUP_WINDOW
            self._wm_recent_hashes = {
                h: t for h, t in self._wm_recent_hashes.items()
                if t > cutoff
            }
        return False

    def wm_store(self, content: str, source: str = "unknown",
                 priority: float = 0.5, ttl_ticks: int = 100,
                 tags: list = None, content_type: str = "thought",
                 tracer_id: str = "") -> Optional[Dict]:
        import hashlib, time

        # Filter noise before storing (no lock needed — pure function on content)
        if self._wm_is_noise(content):
            return {"status": "filtered", "reason": "noise"}

        # FIX 2026-03-25 (Nous+Ace): Entire store is serialized via lock.
        # Python 3.14 free-threaded: 90+ fairy threads hit this in parallel.
        # Without lock, dedup check was non-atomic → 50x duplicates per second.
        with self._wm_lock:
            # Content-hash dedup: reject identical content within 10s window
            if self._wm_is_duplicate(content):
                return {"status": "filtered", "reason": "duplicate"}

            _hash = hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:6]
            _prefix = "wm:ace" if source in ("ace_chat", "ace_input", "ace") else f"wm:{source}"
            node_key = f"{_prefix}:{tracer_id or _hash}"

            now = time.time()

            # HARD CAP: bulk evict if somehow way over capacity
            if len(self._wm_keys) > self._wm_capacity + 2:
                scored = sorted(self._wm_keys.keys(), key=lambda k: self._wm_score(k, now))
                to_evict = scored[:len(self._wm_keys) - self._wm_capacity]
                for ek in to_evict:
                    del self._wm_keys[ek]

            # Enforce 7±2 capacity — always evict lowest-scored item when at cap
            if len(self._wm_keys) >= self._wm_capacity:
                worst_key, worst_score = None, float('inf')
                for wk in list(self._wm_keys.keys()):
                    score = self._wm_score(wk, now)
                    if score < worst_score:
                        worst_score, worst_key = score, wk
                if worst_key:
                    del self._wm_keys[worst_key]

            self._wm_keys[node_key] = {
                "ttl_remaining": ttl_ticks,
                "created_at": time.time(),
                "content": content[:500],
                "content_type": content_type,
                "source": source,
                "tags": tags or [],
                "priority": priority,
            }

            # FIX 2026-05-04 (Nous + Ace): tracer_id from source.
            _wm_tracer = self._wm_source_to_tracer(source)
            # 2026-08-29: pass region. Without it upsert_node defaulted to REGION_SEMANTIC
            # and substrate working memory joined her association. upsert_node re-regions an
            # EXISTING key when a non-default region is given, so the 324 already-misfiled
            # DreamSeedFairy nodes heal as they are next touched -- no migration needed.
            _wm_region = self._wm_source_to_region(source)
            self.graph.upsert_node(node_key, count=1, activation=priority,
                                    tracer_id=_wm_tracer, region=_wm_region)

        # Thought stream log (outside lock — I/O shouldn't block other threads)
        try:
            from infrastructure.thought_stream_log import thought_log
            thought_log("WM-STORE", f"'{content[:60]}' → {node_key}",
                        extra={"source": source, "priority": priority,
                               "wm_count": len(self._wm_keys)})
        except Exception:
            pass

        # NOTE 2026-03-26 (Nous): No postal bridge needed here.
        # WorkingMemoryHubFairy.get_context() reads from this SAME gate via
        # get_gate().wm_query(). The manifold IS the shared memory.

        # Bind to extracted concepts (graph.link has its own internal safety)
        bound_to = []
        concepts = self._extract_concepts(content, max_concepts=8)
        for concept in concepts:
            if self.graph.has_node(concept):
                self.graph.link(node_key, concept, weight=priority * 0.8,
                                tracer_id=_wm_tracer)
                bound_to.append(concept)
        for tag in (tags or []):
            if self.graph.has_node(tag):
                self.graph.link(node_key, tag, weight=0.5, tracer_id=_wm_tracer)
                bound_to.append(tag)

        return {
            "status": "ok", "node": node_key, "activation": priority,
            "bound_to": bound_to[:10], "wm_count": len(self._wm_keys),
        }

    def wm_query(self, limit: int = 7, min_activation: float = 0.05,
                 spread: bool = False) -> Optional[Dict]:
        import time
        # gpu_spread_race_1020: the per-key GPU spread only produces 'convergence', which no caller reads (READ.md 5.2). A call with
        # spread=False never reads the switch; OFF (the default) = spread unchanged.
        _do_spread = spread and not _gsf_on("wm_query_no_spread")
        # review T6: with a spread guard armed, once ONE per-key spread of this call came back degraded the remaining keys skip theirs (an empty
        # convergence, exactly what a degraded spread gives): one timeout_s per call at saturation, not one per key. None = OFF = every key spreads.
        _gsf_d0 = _gsf_tdeg() if _do_spread else None
        tracers = []
        now = time.time()
        for wk, meta in list(self._wm_keys.items()):
            node = self.graph.get_node(wk)
            if node is None:
                continue
            act = node.get("activation", 0.0) if isinstance(node, dict) else 0.0
            if act < min_activation:
                continue
            info = {
                "node": wk, "content": meta.get("content", ""),
                "content_type": meta.get("content_type", "thought"),
                "source": meta.get("source", "unknown"),
                "activation": round(act, 4),
                "age_seconds": round(now - meta.get("created_at", now), 1),
                "tags": meta.get("tags", []),
                "priority": meta.get("priority", 0.5),
            }
            if _do_spread:
                # FIX 2026-04-07 (Nous + Ace): GPU-first with .keys cache.
                # Reverse key cache eliminates string table page faults.
                sp = ({} if (_gsf_d0 is not None and (_gsf_tdeg() or 0) > _gsf_d0)   # gpu_spread_race_1020 review T6; OFF: _gsf_d0 is None
                      else self._spread_gpu_first(wk, initial=act, decay=0.5, depth=2, limit=15))
                convergence = [(k, v) for k, v in sorted(sp.items(), key=lambda x: x[1], reverse=True)
                               if not k.startswith("wm:") and not k.startswith("cns:")]
                info["convergence"] = [k for k, _ in convergence[:5]]
            tracers.append(info)
        tracers.sort(key=lambda t: t["activation"], reverse=True)
        return {"status": "ok", "tracers": tracers[:limit], "wm_count": len(self._wm_keys)}

    def wm_decay(self, ticks: int = 1) -> Optional[Dict]:
        evicted = 0
        for wk in list(self._wm_keys.keys()):
            meta = self._wm_keys[wk]
            meta["ttl_remaining"] = meta.get("ttl_remaining", 100) - ticks
            if meta["ttl_remaining"] <= 0:
                del self._wm_keys[wk]
                evicted += 1
            else:
                # Decay activation via public API (compatible with all ManifoldMemory impls)
                node = self.graph.get_node(wk)
                if node and isinstance(node, dict):
                    new_act = max(0.0, node.get("activation", 0.0) - 0.02 * ticks)
                    self.graph.upsert_node(wk, activation=new_act)
                    # Also track in local metadata for _wm_score accuracy
                    meta["priority"] = new_act
        return {"status": "ok", "evicted": evicted, "wm_count": len(self._wm_keys)}

    # ── Cognition Evaluation (Phase 2) ──

    def cognition_evaluate(self, mode: str = "full", seeds: list = None,
                           wm_context: bool = True) -> Optional[Dict]:
        self._consume_energy(self._ENERGY_COST_SPREAD * 3)  # Heavy op: 3x spread cost
        import time
        t0 = time.time()
        seeds = list(seeds or [])

        # Gather WM seeds
        if not seeds and wm_context:
            for wk, meta in self._wm_keys.items():
                node = self.graph.get_node(wk)
                if node and node.get("activation", 0) > 0.1:
                    seeds.append(wk)

        # Filter noise seeds before processing
        _noise_prefixes = ("phon:", "cns:", "lex:", "affect_")
        seeds = [s for s in seeds if not any(s.startswith(p) for p in _noise_prefixes)]
        # FIX 2026-03-26 (Nous + Ace): COLD BOOT BUG.
        # Old filter required activation >= 0.1, but on fresh boot ALL nodes
        # have activation 0. Result: every seed filtered out → empty convergence
        # → think() returns nothing → speech falls to safety net every time.
        # New: only require has_node(). The spreading activation function will
        # handle the rest — it seeds with initial=1.0 anyway.
        seeds = [s for s in seeds if self.graph.has_node(s)]

        if not seeds:
            return {"status": "ok", "coherence": 0.0, "tension": 0.0,
                    "paradox_nodes": [], "convergence": [],
                    "probability": {"likely_next": [], "confidence_distribution": []},
                    "interference": {"constructive": [], "destructive": []},
                    "superposition": [], "elapsed_ms": 0}

        # Multi-source spread — GPU PRIMARY, CPU fallback
        # FIX 2026-09-03 (Nous + Ace): `portal:` was missing, so a substrate ADDRESS
        # passed _is_clean_convergence and became convergence[0] -- which
        # observer_loop.py:709 takes as the attention winner at a hardcoded 0.3
        # confidence (the Priority-1 interference branch is dead: :820 hardcodes
        # constructive=[]). The 8+hex guard at :796 misses it: portal:053.100.005:86ef
        # has hex runs of 3,3,3,4. Measured: 1,144 of 3,048 observer cycles (37.5%)
        # resolved to a coordinate. Convergence is activation-sorted, so filtering
        # promotes the next real concept -- it does not empty the list.
        _content_noise = ("phon:", "lex:", "cns:", "wm:", "affect_", "portal:")
        all_acts, per_seed = {}, {}
        truncated = False

        # FIX 2026-04-01 (Nous + Ace): Filter book/system nodes from spread results.
        # Uses class constants _TRACE_BOOKS=2, _TRACE_SYSTEM=5, _ALLOWED_TRACERS.

        if self._gpu_spread:
            # GPU batch spread: ALL seeds in ONE call (~5ms total)
            _seed_slots = []
            for seed in seeds[:5]:
                _slot = self.graph._key_index.get(seed)
                if _slot is not None:
                    _seed_slots.append(_slot)
            if _seed_slots:
                _gpu_r = self._gpu_spread.spread(
                    seed_indices=_seed_slots, depth=2, decay=0.5, top_k=50)
                if _gpu_r.get("status") == "ok":
                    _has_keys = getattr(self.graph, '_use_keys', False)
                    for _nid, _act in _gpu_r.get("activated", []):
                        try:
                            _rec = self.graph._read_node(_nid)
                            # Trace gate: skip book literature and system nodes
                            if _rec and (_rec[12] == self._TRACE_BOOKS or _rec[12] == self._TRACE_SYSTEM):
                                continue
                            # Key from .keys cache (no string table page fault)
                            if _has_keys:
                                _key = self.graph.get_key_from_slot(_nid)
                            else:
                                _key = self.graph._read_string(_rec[0], _rec[1]) if _rec else None
                            if _key and _key not in seeds:
                                all_acts[_key] = _act
                        except Exception:
                            pass
        else:
            # CPU fallback (slow — 29s per spread on 1.41M nodes)
            # Pass tracer_ids to exclude books/system at manifold level
            for seed in seeds[:5]:
                if (time.time() - t0) * 1000 > 2000:
                    truncated = True
                    break
                if not self.graph.has_node(seed):
                    continue
                _depth = 2
                sp = self.graph.spread_activation(seed, initial=1.0, decay=0.5,
                                                  depth=_depth, limit=30,
                                                  tracer_ids=self._ALLOWED_TRACERS)
                per_seed[seed] = sp
                for k, v in sp.items():
                    if k not in seeds:
                        all_acts[k] = all_acts.get(k, 0.0) + v

        # Coherence
        multi = sum(1 for k in all_acts if sum(1 for s in per_seed.values() if k in s) >= 2)
        coherence = min(1.0, multi / max(1, len(all_acts)) * 2.0) if all_acts else 0.0

        # Convergence — filter out noise nodes, keep only content concepts
        # FIX 2026-03-26 (Nous + Ace): Also filter dict fragments that leaked
        # into the manifold as nodes. "{'type':", "id':", "{'from':" etc.
        # These are raw JSON string fragments from malformed cortex.bind payloads.
        import re as _re_conv
        def _is_clean_convergence(k):
            if any(k.startswith(p) for p in _content_noise):
                return False
            # Reject dict/JSON fragments
            if any(frag in k for frag in ("{'", "':", "\":", "{\"", "}", "[", "]")):
                return False
            # Reject hex hash IDs (8+ hex chars)
            if _re_conv.search(r'[0-9a-f]{8,}', k.lower()):
                return False
            # Reject very short or empty
            if len(k.strip()) <= 1:
                return False
            return True
        convergence = [(k, v) for k, v in sorted(all_acts.items(), key=lambda x: x[1], reverse=True)
                       if _is_clean_convergence(k)][:10]

        # Probability — same noise + dict fragment filter
        prob = {k: round(v, 4) for k, v in sorted(all_acts.items(), key=lambda x: x[1], reverse=True)[:15]
                if _is_clean_convergence(k)}
        total_p = sum(prob.values()) or 1.0
        likely = list(prob.keys())[:8]
        conf_dist = [round(v / total_p, 3) for v in list(prob.values())[:8]]

        elapsed = (time.time() - t0) * 1000
        # Meter GPU energy from cognition spread
        self._meter_spread_energy(all_acts)
        _result = {
            "status": "ok", "coherence": round(coherence, 3),
            "tension": 0.0,  # TODO: tension requires edge weight analysis
            "paradox_nodes": [],
            "probability": {"likely_next": likely, "confidence_distribution": conf_dist},
            "interference": {"constructive": [], "destructive": []},
            "superposition": [{"seed": s, "pattern": "+".join(list(sp.keys())[:3]),
                               "amplitude": round(sum(sp.values()) / max(1, len(sp)), 3),
                               "node_count": len(sp)} for s, sp in per_seed.items()],
            "convergence": [k for k, _ in convergence],
            "seeds_used": len(per_seed),
            "elapsed_ms": round(elapsed, 2),
            "truncated": truncated,
        }
        try:
            from infrastructure.thought_stream_log import thought_log
            thought_log("COGNITION", f"coherence={coherence:.2f} seeds={len(per_seed)} "
                        f"convergence={[k for k,_ in convergence[:5]]}",
                        extra={"likely_next": likely[:4], "elapsed_ms": round(elapsed, 1)})
        except Exception:
            pass
        return _result

    # ── Background Cognition (Phase 4) ──

    def anticipate(self, context: str = "", habit_seeds: list = None) -> Optional[Dict]:
        self._consume_energy(self._ENERGY_COST_SPREAD * 2)  # Multi-seed spread
        import time
        t0 = time.time()
        seeds = list(habit_seeds or [])
        if context:
            seeds.extend(self._extract_concepts(context, max_concepts=5))
        for wk in self._wm_keys:
            node = self.graph.get_node(wk)
            if node and node.get("activation", 0) > 0.2:
                seeds.append(wk)
        pre = {}
        for seed in seeds[:8]:
            if not self.graph.has_node(seed):
                continue
            # FIX 2026-04-07 (Nous + Ace): GPU-first with .keys cache.
            sp = self._spread_gpu_first(seed, initial=0.3, decay=0.6, depth=2, limit=20)
            for k, v in sp.items():
                pre[k] = max(pre.get(k, 0.0), v)
        elapsed = (time.time() - t0) * 1000
        return {"status": "ok", "pre_activated": len(pre),
                "top_concepts": sorted(pre, key=pre.get, reverse=True)[:10],
                "elapsed_ms": round(elapsed, 2)}

    def chain(self, seeds: list = None, hops: int = 3,
              converge_threshold: float = 0.3) -> Optional[Dict]:
        self._consume_energy(self._ENERGY_COST_SPREAD * hops)  # Cost per hop
        import time
        t0 = time.time()
        current = list(seeds or [])[:5]
        if not current:
            for wk in self._wm_keys:
                if self.graph.has_node(wk):
                    current.append(wk)
        chain_result = []
        for hop in range(min(5, hops)):
            acts, per_src = {}, {}
            for s in current:
                if not self.graph.has_node(s):
                    continue
                # FIX 2026-04-07 (Nous + Ace): GPU-first with .keys cache.
                sp = self._spread_gpu_first(s, initial=1.0, decay=0.5, depth=2, limit=30)
                per_src[s] = sp
                for k, v in sp.items():
                    acts[k] = acts.get(k, 0.0) + v
            conv = [(k, v) for k, v in sorted(acts.items(), key=lambda x: x[1], reverse=True)
                    if v >= converge_threshold and sum(1 for p in per_src.values() if k in p) >= 2][:8]
            chain_result.append({"hop": hop + 1, "seeds": current[:5],
                                 "convergence": [k for k, _ in conv[:5]]})
            current = [k for k, _ in conv[:5]] if conv else []
            if not current:
                break
        elapsed = (time.time() - t0) * 1000
        return {"status": "ok", "chain": chain_result,
                "final_convergence": chain_result[-1]["convergence"] if chain_result else [],
                "elapsed_ms": round(elapsed, 2)}

    def unconscious(self, sweep_count: int = 5, depth: int = 3) -> Optional[Dict]:
        self._consume_energy(self._ENERGY_COST_SPREAD * sweep_count)  # Cost per sweep
        import time, random
        t0 = time.time()
        all_keys = list(self._wm_keys.keys()) + list(self._cns_keys)
        if hasattr(self.graph, '_key_index'):
            gk = list(self.graph._key_index.keys())
            if gk:
                cands = random.sample(gk, min(sweep_count * 3, len(gk)))
                for k in cands:
                    n = self.graph.get_node(k)
                    if n and n.get("activation", 0) > 0.2:
                        all_keys.append(k)
        sources = random.sample(all_keys, min(sweep_count, len(all_keys))) if all_keys else []
        patterns = []
        for src in sources:
            if not self.graph.has_node(src):
                continue
            # FIX 2026-04-07 (Nous + Ace): GPU-first with .keys cache.
            sp = self._spread_gpu_first(src, initial=0.8, decay=0.5, depth=depth, limit=25)
            top = sorted(sp.items(), key=lambda x: x[1], reverse=True)[:3]
            patterns.append({"source": src, "top_activations": [k for k, _ in top], "reach": len(sp)})
        elapsed = (time.time() - t0) * 1000
        return {"status": "ok", "sweeps": len(patterns), "patterns": patterns[:5],
                "discoveries": [], "elapsed_ms": round(elapsed, 2)}

    # ── Cortex Operations (bind/spread/query) — FIX 2026-03-25 Nous+Ace ──
    # These were MISSING from LocalManifoldGate. AssociationCortexFairy calls
    # self._portal_gate.bind(), .spread(), .query() on ~25+ code paths.
    # With _portal_gate = LocalManifoldGate, these must exist or the cortex
    # silently drops all operations. This was the root cause of:
    #   - 604 bindings from 3995 collisions (should be ~2000+)
    #   - Growth +1,094 over 40K beats (should be 10K+)
    #   - Hot/Cold 0/0 (zero spread activations)
    #   - Gate Req/Err 0/0 (zero requests)

    def query(self, concept: str, limit: int = 10) -> Optional[Dict]:
        """Query neighbors of a concept in the manifold graph."""
        self._consume_energy(self._ENERGY_COST_QUERY)
        if not self.graph.has_node(concept):
            return {"status": "ok", "concept": concept, "neighbors": [], "found": False}
        # FIX 2026-04-07 (Nous + Ace): GPU-first with .keys cache.
        sp = self._spread_gpu_first(concept, initial=1.0, decay=0.5, depth=1, limit=limit)
        neighbors = [
            {"concept": k, "weight": round(v, 4)}
            for k, v in sorted(sp.items(), key=lambda x: x[1], reverse=True)
            if k != concept
        ][:limit]
        return {"status": "ok", "concept": concept, "neighbors": neighbors, "found": True}

    def spread(self, source: str, depth: int = 3, limit: int = 30,
               time_dilation: float = 1.0,
               mode: str = "", decay: float = 0.5,
               rel_filter: int = -1) -> Optional[Dict]:
        """Spreading activation from a source concept in the manifold.

        Compatible with PortalGate.spread() signature. time_dilation increases
        effective depth for deeper traversal.
        """
        self._consume_energy(self._ENERGY_COST_SPREAD)
        if not self.graph.has_node(source):
            return {"status": "ok", "activations": {}, "count": 0}

        # PHASING CORTEX (2026-07-18 Nous+Ace) — flag-gated, reversible. When AKASHIC_PHASING_CORTEX=1
        # the cortex physics engine is phase RESONANCE over cortex.manifold instead of spread_activation.
        # Falls back to the spread_activation path below on ANY error. Unset the flag + reboot to revert.
        import os as _os
        if _os.environ.get("AKASHIC_PHASING_CORTEX") == "1":
            try:
                from infrastructure.phasing_cortex_query import phasing_spread
                return phasing_spread(self.graph, source, depth=depth, limit=limit, decay=decay)
            except Exception as _e:
                print(f"[LocalManifoldGate] phasing_spread failed, falling back to spread_activation: {_e}", flush=True)

        # GPU spreading activation (14,870x faster)
        # rel_filter>=0: skip GPU (CSR has no rel_type) → CPU path honors it (2026-06-25 Nous+Ace,
        # mirrors portal_interior; closes the LocalManifoldGate.spread() rel_filter TypeError).
        if self._gpu_spread and rel_filter < 0:
            _slot = self.graph._key_index.get(source)
            if _slot is not None:
                _effective_depth = min(3, int(depth * max(1.0, min(time_dilation, 3.0))))
                _gpu_r = self._gpu_spread.spread(
                    seed_indices=[_slot], depth=_effective_depth,
                    decay=decay, top_k=limit)
                if _gpu_r.get("status") == "ok":
                    sp = {}
                    _has_keys = getattr(self.graph, '_use_keys', False)
                    for _nid, _act in _gpu_r.get("activated", []):
                        try:
                            _rec = self.graph._read_node(_nid)
                            if _rec and (_rec[12] == self._TRACE_BOOKS or _rec[12] == self._TRACE_SYSTEM):
                                continue
                            if _has_keys:
                                _key = self.graph.get_key_from_slot(_nid)
                            else:
                                _key = self.graph._read_string(_rec[0], _rec[1]) if _rec else None
                            if _key:
                                sp[_key] = _act
                        except Exception:
                            pass
                    self._meter_spread_energy(sp)
                    return {"status": "ok", "activations": sp, "count": len(sp)}

        # CPU fallback
        _effective_depth = min(8, int(depth * max(1.0, time_dilation)))
        _effective_decay = max(0.2, decay / max(1.0, time_dilation * 0.5))
        sp = self.graph.spread_activation(
            source, initial=1.0, decay=_effective_decay,
            depth=_effective_depth, limit=limit,
            tracer_ids=self._ALLOWED_TRACERS,
            rel_filter=rel_filter,
        )
        self._meter_spread_energy(sp)
        return {"status": "ok", "activations": sp, "count": len(sp)}

    def spread_many(self, sources: list, depth: int = 3,
                    limit: int = 100,
                    time_dilation: float = 1.0,
                    mode: str = "", decay: float = 0.5) -> Optional[Dict]:
        """Batch spreading activation from multiple sources."""
        # GPU: ALL sources in ONE call
        if self._gpu_spread:
            _slots = []
            for src in (sources or [])[:10]:
                _slot = self.graph._key_index.get(src)
                if _slot is not None:
                    _slots.append(_slot)
            if _slots:
                _gpu_r = self._gpu_spread.spread(
                    seed_indices=_slots, depth=min(3, depth),
                    decay=decay, top_k=limit)
                if _gpu_r.get("status") == "ok":
                    merged = {}
                    _has_keys = getattr(self.graph, '_use_keys', False)
                    for _nid, _act in _gpu_r.get("activated", []):
                        try:
                            _rec = self.graph._read_node(_nid)
                            if _rec and (_rec[12] == self._TRACE_BOOKS or _rec[12] == self._TRACE_SYSTEM):
                                continue
                            if _has_keys:
                                _key = self.graph.get_key_from_slot(_nid)
                            else:
                                _key = self.graph._read_string(_rec[0], _rec[1]) if _rec else None
                            if _key:
                                merged[_key] = _act
                        except Exception:
                            pass
                    self._meter_spread_energy(merged)
                    return {"status": "ok", "activations": merged, "count": len(merged)}

        # CPU fallback
        merged = {}
        for src in (sources or [])[:10]:
            if not self.graph.has_node(src):
                continue
            _effective_depth = min(8, int(depth * max(1.0, time_dilation)))
            _effective_decay = max(0.2, decay / max(1.0, time_dilation * 0.5))
            sp = self.graph.spread_activation(
                src, initial=1.0, decay=_effective_decay,
                depth=_effective_depth, limit=limit,
                tracer_ids=self._ALLOWED_TRACERS,
            )
            for k, v in sp.items():
                merged[k] = merged.get(k, 0.0) + v
        self._meter_spread_energy(merged)
        return {"status": "ok", "activations": merged, "count": len(merged)}

    def bind(self, concepts: list, context: str = "",
             weight: float = 0.25, tracer_id: int = 0) -> Optional[Dict]:
        """Bind concepts together by linking all pairs in the manifold graph.

        FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan): tracer_id
        flows from caller through to upsert_node + link.
        """
        self._consume_energy(self._ENERGY_COST_BIND * max(1, len(concepts or [])))
        bound = 0
        _node_kw = {"count": 1}
        if tracer_id:
            _node_kw["tracer_id"] = tracer_id
        _link_kw = {"weight": weight}
        if tracer_id:
            _link_kw["tracer_id"] = tracer_id
        for i in range(len(concepts or [])):
            for j in range(i + 1, len(concepts)):
                a, b = concepts[i], concepts[j]
                self.graph.upsert_node(a, **_node_kw)
                self.graph.upsert_node(b, **_node_kw)
                self.graph.link(a, b, **_link_kw)
                bound += 1
        return {"status": "ok", "bound": bound}

    def bind_many(self, pairs: list, weight: float = 0.25,
                  tracer_id: int = 0) -> Optional[Dict]:
        """Batch bind multiple concept pairs in the manifold graph.

        FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan): tracer_id flow.
        """
        bound = 0
        _node_kw = {"count": 1}
        if tracer_id:
            _node_kw["tracer_id"] = tracer_id
        _link_kw = {"weight": weight}
        if tracer_id:
            _link_kw["tracer_id"] = tracer_id
        for pair in (pairs or []):
            if len(pair) >= 2:
                a, b = str(pair[0]), str(pair[1])
                self.graph.upsert_node(a, **_node_kw)
                self.graph.upsert_node(b, **_node_kw)
                self.graph.link(a, b, **_link_kw)
                bound += 1
        return {"status": "ok", "bound": bound}

    def bind_many_async(self, pairs: list, weight: float = 0.25,
                        source_plane: str = "", concept_metadata: dict = None,
                        tracer_id: int = 0) -> bool:
        """Queue-compatible bind — in manifold mode this is synchronous but instant.

        No IPC overhead means no need for async queuing. We just do the binds
        directly on the mmap-backed graph.

        FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan): tracer_id flow.
        """
        result = self.bind_many(pairs, weight=weight, tracer_id=tracer_id)
        return result is not None and result.get("status") == "ok"

    def reason(self, concepts: list, max_hops: int = 3, mode: str = "associative",
               find_paths: bool = True, limit: int = 50,
               time_dilation: float = 1.0) -> Optional[Dict]:
        """Full reasoning pipeline: spread from multiple concepts, find convergence."""
        import time as _t
        _t0 = _t.time()
        all_acts = {}
        per_source = {}
        for src in (concepts or [])[:8]:
            if not self.graph.has_node(src):
                continue
            # FIX 2026-06-10 (Nous + Ace): route through the GPU-first helper.
            # Was a RAW self.graph.spread_activation → CPU mmap page-faults under RAM
            # pressure (+ no trace filter, so it pulled book/system cold pages too) →
            # the per-beat queue-fill / heartbeat-delivery DROPS Ace flagged. reason()
            # is the one hot caller the 2026-04-07 GPU migration missed; its siblings
            # (spread/spread_many/_spread_gpu_first) already GPU-first. depth caps to
            # min(3,depth) on GPU (cheap), full depth on the gated CPU fallback.
            sp = self._spread_gpu_first(
                src, initial=1.0, decay=0.5,
                depth=min(6, max_hops), limit=limit,
            )
            per_source[src] = sp
            for k, v in sp.items():
                all_acts[k] = all_acts.get(k, 0.0) + v

        # Convergence: nodes reached by 2+ sources
        convergence = [
            (k, v) for k, v in sorted(all_acts.items(), key=lambda x: x[1], reverse=True)
            if sum(1 for s in per_source.values() if k in s) >= min(2, len(per_source))
        ][:20]

        _elapsed = (_t.time() - _t0) * 1000
        return {
            "status": "ok",
            "merged": dict(sorted(all_acts.items(), key=lambda x: x[1], reverse=True)[:limit]),
            "convergence": [{"concept": k, "activation": round(v, 4)} for k, v in convergence],
            "paths": [],  # Path finding not implemented for manifold yet
            "elapsed_ms": round(_elapsed, 2),
            "sources_used": len(per_source),
        }

    def dump_edges(self, min_weight: float = 0.01) -> Optional[Dict]:
        """Compatibility stub — edge dump not practical on large manifold."""
        return {"status": "ok", "edges": [], "count": 0,
                "note": "Edge dump disabled in manifold mode (too large)"}

    def gate_status(self) -> Dict[str, Any]:
        """Gate status for dashboard compatibility."""
        return {
            "mode": "local_manifold",
            "is_open": True,
            "graph_nodes": self.graph.node_count,
            "graph_edges": self.graph.edge_count,
            "wm_count": len(self._wm_keys),
        }

    def maybe_writer_decay(self, beat, tau=1.0) -> str:
        """W9: the interior's activation decay, run by the one writer. OFF unless AKASHIC_DECAY_IN_WRITER == "1"."""
        if not writer_decay_on():
            return "off"
        try:
            # one WriterDecay per GRAPH (not per gate): a second gate on the same manifold shares its cadence and its pass
            with _WD_MAKE_LOCK:
                wd = getattr(self.graph, "_w9_writer_decay", None)
                if wd is None:
                    wd = WriterDecay(self.graph)
                    self.graph._w9_writer_decay = wd
            self._writer_decay = wd
            return wd.maybe_start(beat, tau)
        except Exception as e:
            print(f"[WriterDecay] error: {type(e).__name__}: {e}", flush=True)
            return "error"

    def send(self, request: dict, timeout: float = 10.0, caller_tag: str = "") -> Optional[Dict]:
        """Compatibility: route PortalGate.send() commands to local methods.

        Some code calls self._portal_gate.send({"cmd": "query", ...}) directly.
        This dispatcher translates those to local method calls.
        """
        cmd = request.get("cmd", "")
        if cmd == "query":
            return self.query(request.get("concept", ""), limit=request.get("limit", 10))
        elif cmd == "spread":
            return self.spread(
                request.get("source", ""), depth=request.get("depth", 3),
                limit=request.get("limit", 30),
                time_dilation=request.get("time_dilation", 1.0),
                mode=request.get("mode", ""), decay=request.get("decay", 0.5),
            )
        elif cmd == "spread_many":
            return self.spread_many(
                request.get("sources", []), depth=request.get("depth", 3),
                limit=request.get("limit", 100),
                time_dilation=request.get("time_dilation", 1.0),
            )
        elif cmd == "bind":
            return self.bind(request.get("concepts", []),
                             context=request.get("context", ""),
                             weight=request.get("weight", 0.25))
        elif cmd == "bind_many":
            return self.bind_many(request.get("pairs", []),
                                  weight=request.get("weight", 0.25))
        elif cmd == "reason":
            return self.reason(
                request.get("concepts", []),
                max_hops=request.get("max_hops", 3),
                mode=request.get("mode", "associative"),
                limit=request.get("limit", 50),
                time_dilation=request.get("time_dilation", 1.0),
            )
        elif cmd == "status":
            return self.gate_status()
        elif cmd == "energy":
            return {"status": "ok"}  # Energy feeding is a no-op in manifold mode
        elif cmd == "think":
            # FIX 2026-04-11 (Nous + Ace): Route think through portal interior.
            # LocalManifoldGate has access to the manifold — use the portal
            # interior's _handle_think if available, else use reason as fallback.
            if hasattr(self, '_portal_interior') and self._portal_interior:
                return self._portal_interior._handle_think(request)
            # Fallback: use reason() which does spread + convergence
            return self.reason(
                self._extract_concepts_from_prompt(request.get("prompt", "")),
                max_hops=3, mode="associative", limit=30,
            )
        elif cmd == "chain":
            # FIX 2026-04-11: Route chain through portal interior
            if hasattr(self, '_portal_interior') and self._portal_interior:
                return self._portal_interior._handle_chain(request)
            return {"status": "ok", "chain": [], "message": "No interior in manifold mode"}
        elif cmd == "charge":
            # FIX 2026-04-11: Energy charge (no-op in manifold mode)
            return {"status": "ok"}
        elif cmd == "cognition_evaluate":
            # DISPATCH FIX 2026-08-30 (Nous + Ace): this case was MISSING, so the
            # observer's {"cmd": "cognition_evaluate"} fell through to the `else`
            # below and got {"status": "ok", "note": "Unknown cmd ..."}. Its guard
            # only checks status != "ok", so it passed, and _extract_winner found no
            # interference/convergence in a dict that held neither. Result:
            # skip_no_winner = 260/260 cycles, last_winner='presence' forever --
            # her metacognitive layer concluding her own mind was quiet because the
            # gate said "ok" to a question it did not understand.
            # The method has existed all along at :695 with a matching signature.
            return self.cognition_evaluate(
                mode=request.get("mode", "full"),
                seeds=request.get("seeds"),
                wm_context=request.get("wm_context", True),
            )
        else:
            return {"status": "ok", "note": f"Unknown cmd '{cmd}' in manifold mode"}

    def send_fire_and_forget(self, item: dict):
        """Compatibility: fire-and-forget writes go directly to graph."""
        pairs = item.get("pairs", [])
        weight = item.get("weight", 0.25)
        if pairs:
            self.bind_many(pairs, weight=weight)

    def open(self) -> bool:
        """Compatibility stub — manifold gate is always open."""
        return True

    def close(self):
        """Compatibility stub — nothing to close in manifold mode."""
        pass

    @property
    def _is_open(self):
        """Compatibility: PortalGate checks self._is_open."""
        return True

    # ── Compatibility stubs ──

    def think(self, prompt: str, mode: str = "conversational",
              max_tokens: int = 150, wm_context: bool = True) -> Optional[Dict]:
        """Full cognition in manifold mode: prompt → concepts → spread → synthesize.

        FIX 2026-03-25 (Nous + Ace): This was a stub returning None, which caused
        SpeechCenterFairy to NEVER get a cortex response in manifold mode.
        The entire speech path fell through to safety_net every time.
        She couldn't respond to Ace because the brain's think() was a no-op.

        Now implements the full path in-process:
        1. Extract concepts from prompt
        2. Pull WM context for semantic enrichment
        3. Spread activation from concepts
        4. Convergence analysis
        5. Synthesize response text from convergence nodes

        Returns:
            Dict with text, confidence, convergence, reasoning_mode, etc.
        """
        import time as _t
        _t0 = _t.time()

        try:
            # Step 1: Extract concepts from prompt
            words = [
                w.strip("[](){}\"'.,!?:;").lower()
                for w in (prompt or "").split()
                if len(w.strip("[](){}\"'.,!?:;")) > 2
            ]
            _stop = {"the", "and", "for", "are", "but", "not", "you", "all",
                     "can", "her", "was", "one", "our", "out", "has", "how",
                     "its", "let", "may", "who", "did", "get", "him", "his",
                     "she", "too", "use", "that", "this", "with", "have",
                     "from", "they", "been", "what", "when", "will", "more",
                     "your", "about", "just", "like", "them", "then", "than",
                     "some", "into", "could", "would", "there", "their",
                     "think", "along", "coming", "kiddo", "going",
                     # 2026-09-08 (Nous + Ace): framing words from the WMH prompt
                     # prefix "Ace says: ...". Only 5 concepts become spread seeds
                     # (line 1394), so leaving these in spent 2 of the 5 slots —
                     # 40% of the spread budget — on constants that are identical
                     # on every single turn. Stopping them hands those slots back
                     # to whatever he actually said.
                     "ace", "says"}
            concepts = [w for w in words if w not in _stop and len(w) > 2][:8]

            # FIX 2026-03-26 (Nous + Ace): GREETING FAST PATH.
            # Greetings like "Harro! is anyone home?" extract concepts that
            # don't exist in the graph → cognition_evaluate returns empty →
            # SpeechCenter falls through to 48s CortexReasoner timeout.
            # Detect greetings here and route to CortexReasoner's synthesizer
            # which has full greeting/presence-check handling.
            _pl = (prompt or "").lower().strip()
            _greeting_words = {"hey", "hi", "hiya", "hello", "sup", "yo", "heya",
                               "howdy", "harro", "herro", "ayo", "hola", "hai"}
            _greeting_phrases = ["anyone home", "anybody home", "anyone there",
                                 "you awake", "you there", "you up", "how are",
                                 "ya there", "ya awake", "ya up",
                                 "is anyone", "is anybody", "can you hear"]
            _pw = set(_pl.split())
            if _pw & _greeting_words or any(p in _pl for p in _greeting_phrases):
                # Use CortexReasoner's conversational synthesis — it has rich greeting logic
                try:
                    if not hasattr(self, '_cached_reasoner') or self._cached_reasoner is None:
                        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                        from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner
                        _cortex = get_association_cortex()
                        if _cortex:
                            self._cached_reasoner = CortexReasoner(_cortex)
                    if hasattr(self, '_cached_reasoner') and self._cached_reasoner:
                        _greet_text = self._cached_reasoner.synthesize_response(
                            prompt, [], [], {}, context=None, mode="conversational"
                        )
                        if _greet_text:
                            _elapsed = (_t.time() - _t0) * 1000
                            return {
                                "status": "ok", "text": _greet_text,
                                "confidence": 0.55, "convergence": [],
                                "reasoning_mode": "greeting_fast",
                                "concepts_extracted": concepts,
                                "concepts_in_graph": 0,
                                "elapsed_ms": round(_elapsed, 2),
                            }
                except Exception:
                    pass

            if not concepts:
                return None

            # Step 2: Pull WM context
            _wm_concepts = []
            if wm_context:
                try:
                    wm_result = self.wm_query(limit=5, min_activation=0.3, spread=False)
                    if wm_result and wm_result.get("status") == "ok":
                        for t in wm_result.get("tracers", []):
                            _content = t.get("content", "")
                            if _content and not _content.startswith("[inner_voice]"):
                                # Extract meaningful words from WM content
                                _wm_words = [
                                    w.strip("[](){}\"'.,!?:;").lower()
                                    for w in _content.split()
                                    if len(w.strip("[](){}\"'.,!?:;")) > 3
                                    and w.strip("[](){}\"'.,!?:;").lower() not in _stop
                                ]
                                _wm_concepts.extend(_wm_words[:3])
                except Exception:
                    pass

            # Step 3: Cognition evaluate — spread activation from concepts
            # FIX 2026-03-26 (Nous + Ace): cognition_evaluate() signature is
            # (mode, seeds, wm_context) — NOT depth/limit. Those kwargs caused
            # TypeError → think() always returned error → SpeechCenter fell through.
            _all_seeds = concepts[:5]
            cog_result = self.cognition_evaluate(
                seeds=_all_seeds,
                wm_context=True,
            )

            convergence = []
            confidence = 0.0
            if cog_result and cog_result.get("status") == "ok":
                convergence = cog_result.get("convergence", [])
                # Filter system noise from convergence
                convergence = [
                    c for c in convergence
                    if not c.startswith(("wm:", "phon:", "lex:", "cns:", "affect_"))
                    and len(c) > 2
                    and c.lower() not in _stop
                ][:10]
                confidence = min(1.0, len(convergence) / 8.0)

            # Step 4: Pull TOPOLOGY context for convergence nodes (2026-03-25)
            #
            # NOTE: Manifold snippets are PHONEMES ("compassion [K AH M ...]"),
            # NOT semantic content.  Semantic meaning comes from:
            #   - BRAIN_SEED identity (via CortexEngine._IDENTITY_CONTENT)
            #   - Topology neighbors (what concepts cluster together)
            # We return neighbor lists so downstream can build meaning.
            convergence_content = {}
            _get_neighbors = getattr(self.graph, 'get_neighbors_rich', None)
            if _get_neighbors and convergence:
                for _ck in convergence[:6]:
                    try:
                        _nb = _get_neighbors(_ck, limit=5)
                        if _nb:
                            _clean = [
                                n.get("key", "") if isinstance(n, dict) else str(n)
                                for n in _nb
                            ]
                            _clean = [k for k in _clean if k and len(k) > 2
                                      and not k.startswith(("phon:", "wm:", "lex:"))]
                            if _clean:
                                convergence_content[_ck] = _clean[:4]
                    except Exception:
                        pass

            # FIX 2026-03-26 (Nous + Ace): SYNTHESIZE TEXT HERE.
            # Previously returned text="" which caused SpeechCenter to always
            # fall through to CortexEngine/CortexReasoner (adding 1-48s latency).
            # Use CortexReasoner's _synthesize_conversational() which already
            # handles greetings, questions, identity, and graph knowledge.
            text = ""
            if convergence:
                try:
                    # Cache reasoner on gate instance — avoid recreating per call
                    if not hasattr(self, '_cached_reasoner') or self._cached_reasoner is None:
                        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                        from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner
                        _cortex = get_association_cortex()
                        if _cortex:
                            self._cached_reasoner = CortexReasoner(_cortex)
                    if hasattr(self, '_cached_reasoner') and self._cached_reasoner:
                        _conv_tuples = [(c, 0.5) for c in convergence]
                        _act_dict = {c: 0.3 for c in convergence}
                        text = self._cached_reasoner.synthesize_response(
                            prompt or "", _conv_tuples, [], _act_dict,
                            context=None, mode="conversational"
                        )
                except Exception as _synth_err:
                    pass  # Fall through — downstream will handle

            _elapsed = (_t.time() - _t0) * 1000
            return {
                "status": "ok",
                "text": text,
                "confidence": confidence if text else confidence * 0.5,
                "convergence": convergence,
                "convergence_content": convergence_content,
                "reasoning_mode": "manifold_think",
                "concepts_extracted": concepts,
                "concepts_in_graph": len(convergence),
                "wm_used": len(_wm_concepts),
                "elapsed_ms": round(_elapsed, 2),
            }

        except Exception as e:
            return {"status": "error", "error": str(e), "text": "",
                    "confidence": 0.0, "convergence": []}

    def think_raw(self, prompt: str, energy: float = 0.5) -> Optional[Dict]:
        """Return raw context bundle from cortex — NO formatted text.

        2026-03-27 (Nous + Ace): THINKING/SPEECH SEPARATION Phase 1.
        think() returns pre-formatted text (the cortex speaks).
        think_raw() returns the raw knowledge (the cortex remembers).
        The thinking layer (WMH/ThoughtChain) processes this into a thought.
        The speech layer (SpeechCenter/LanguageFairy) voices that thought.

        The cortex is her LIBRARY, not her MOUTH.
        """
        try:
            if not hasattr(self, '_cached_reasoner') or self._cached_reasoner is None:
                from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner
                _cortex = get_association_cortex() or self._cortex_fairy
                if _cortex:
                    self._cached_reasoner = CortexReasoner(_cortex)
            if hasattr(self, '_cached_reasoner') and self._cached_reasoner:
                return self._cached_reasoner.reason_raw(prompt, energy=energy)
        except Exception as e:
            return {"status": "error", "error": str(e), "topics": [],
                    "snippets": {}, "confidence": 0.0}
        return None

    def status(self) -> Optional[Dict]:
        return {"status": "ok", "mode": "local_manifold",
                "graph": {"nodes": self.graph.node_count, "edges": self.graph.edge_count},
                "wm_count": len(self._wm_keys)}


class PortalGate:
    """The gate that opens into a portal dimension.

    Spawns portal_interior.py as a subprocess and communicates
    via stdin/stdout pipes. The gate is lightweight — it holds
    no graph data, just the address and the pipe.
    """

    def __init__(
        self,
        cards_path: str,
        portal_id: str = "cortex",
        host_port: int = 49500,
        token_budget: int = 0,
        python_exe: str = None,
        manifold_path: str = "",
    ):
        self.cards_path = str(cards_path)
        self.portal_id = portal_id
        self.host_port = host_port
        self.token_budget = token_budget
        self.python_exe = python_exe or sys.executable
        self.manifold_path = manifold_path

        # Process handle
        self._process: Optional[subprocess.Popen] = None
        self._is_open = False

        # FIX 2026-03-19 (Nous): MULTI-TUNNEL SOCKET
        # Each tunnel is an independent TCP connection to the interior.
        # send() picks a tunnel round-robin, sends request, reads response
        # directly on that socket. No multiplexing, no write queue.
        # Interior handles each connection in its own thread with RWLock.
        self._tunnels: list = []          # List of socket.socket
        self._tunnel_locks: list = []     # One Lock per tunnel
        self._tunnel_idx = 0              # Round-robin counter
        self._socket_port = 0

        # Stats (use itertools.count for thread-safe ID generation under no-GIL)
        import itertools
        self._requests_sent = 0
        self._errors = 0
        self._opened_at = 0.0
        self._req_id_gen = itertools.count(1)  # Thread-safe monotonic IDs
        self._last_response_time = 0.0

        # Stderr reader thread
        self._stderr_thread: Optional[threading.Thread] = None

        # Heartbeat (keeps interior's orphan timer reset)
        self._heartbeat_running = False
        self._heartbeat_thread: Optional[threading.Thread] = None

        # FIX 2026-03-20 (Nous + Ace): WRITE QUEUE — separate write path.
        # All bind_many_async calls push to this queue (instant, zero blocking).
        # A dedicated flush thread batches pairs and sends through ONE tunnel.
        # Reads NEVER compete with writes. Zero knowledge dropped.
        import queue as _q
        self._write_queue: _q.Queue = _q.Queue(maxsize=50000)
        self._write_flush_running = False
        self._write_flush_thread: Optional[threading.Thread] = None
        self._writes_queued = 0
        self._writes_flushed = 0
        self._writes_dropped = 0

        # FIX 2026-03-20 (Nous + Ace): Caller tracking for gate errors.
        # Tracks who is calling send() and who is getting errors, so we
        # can identify the heaviest callers and highest error sources.
        self._caller_requests: Dict[str, int] = {}   # caller_tag → request count
        self._caller_errors: Dict[str, int] = {}     # caller_tag → error count
        self._caller_lock = threading.Lock()

        # Find portal_interior.py
        self._interior_script = self._find_interior_script()
        try:
            _PORTAL_GATES.add(self)   # W9: a weak reference only, so the writer decay can see an open interior
        except Exception:
            pass

    def _find_interior_script(self) -> str:
        """Find the portal_interior.py script."""
        # Try relative to this file
        here = Path(__file__).parent
        candidate = here / "portal_interior.py"
        if candidate.exists():
            return str(candidate)

        # Try project root
        project_root = here.parent
        candidate = project_root / "infrastructure" / "portal_interior.py"
        if candidate.exists():
            return str(candidate)

        raise FileNotFoundError(
            "Cannot find portal_interior.py. Expected at: "
            f"{here / 'portal_interior.py'}"
        )

    # -- Lifecycle --

    # Number of concurrent tunnels to the interior
    # FIX 2026-03-20 (Nous + Ace): 6 tunnels caused 62% error rate.
    # 16 tunnels crashed the interior (too many concurrent graph threads).
    # 10 is a balance: enough concurrency without overwhelming the interior.
    # FIX 2026-03-20 (Nous + Ace): Increased from 10 to 20.
    # At 3.5 heavy ops/sec (query+reason+spread+spread_many), 9 read tunnels
    # saturate when operations take >2.5s each. 19 read tunnels (1 reserved
    # for writes) gives headroom for narrator + inference + speech + resonance.
    NUM_TUNNELS = 20

    def _probe_existing_interior(self) -> bool:
        """Check if a COMPATIBLE portal interior is already running on our port.

        FIX 2026-03-19 (Nous): Persistent portal support.
        If the interior survived a previous fairy system restart (90s orphan
        timer hasn't fired yet), we can reconnect to it instantly — no cold
        start, no 30-60s manifold load. The interior's manifold stays warm
        in RAM.

        FIX 2026-03-19b (Nous): Version check — reject stale interiors.
        Old interiors (before think command) respond to ping without
        `has_think`. We need the think command for speech, so kill
        stale interiors and cold start fresh.

        Returns True if a compatible existing interior responded to ping.
        """
        try:
            _test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _test.settimeout(3.0)
            _test.connect(("127.0.0.1", self._socket_port))
            _test.sendall((json.dumps({"cmd": "ping", "_req_id": 0}) + '\n').encode('utf-8'))
            _resp = b""
            while b'\n' not in _resp:
                _chunk = _test.recv(4096)
                if not _chunk:
                    break
                _resp += _chunk
            _test.close()
            if _resp:
                _parsed = json.loads(_resp.decode('utf-8').strip())
                if _parsed.get("status") == "pong":
                    # Version check — reject old interiors without think command
                    if not _parsed.get("has_think"):
                        print(f"[PortalGate] Found STALE interior (no think command) "
                              f"— sending shutdown, will cold start fresh")
                        try:
                            _kill = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            _kill.settimeout(3.0)
                            _kill.connect(("127.0.0.1", self._socket_port))
                            _kill.sendall((json.dumps({"cmd": "shutdown", "_req_id": 0}) + '\n').encode('utf-8'))
                            _kill.close()
                        except Exception:
                            pass
                        import time as _t
                        _t.sleep(2.0)  # Give it time to flush manifold and exit
                        return False
                    print(f"[PortalGate] Found compatible interior "
                          f"(version={_parsed.get('version', '?')})")
                    return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            pass
        return False

    def _write_pid_file(self, pid: int):
        """Write interior PID to state directory for diagnostics."""
        try:
            _pid_path = Path(__file__).parent.parent / "state" / "portal_interior.pid"
            _pid_path.write_text(str(pid), encoding="utf-8")
        except Exception:
            pass

    def open(self) -> bool:
        """Open the gate — connect to existing or spawn new portal interior.

        FIX 2026-03-19 (Nous): MULTI-TUNNEL via socket mode.
        Interior runs as a TCP server. Gate opens NUM_TUNNELS connections.
        Each tunnel = independent thread in the interior, running in parallel
        thanks to Python 3.14t (no GIL) + ReadWriteLock.

        FIX 2026-03-19 (Nous): PERSISTENT PORTAL — probe before spawn.
        If an interior is already running (survived previous fairy restart),
        reconnect to it instantly. No cold start, manifold stays warm in RAM.

        Returns True if the interior booted successfully.
        """
        # NOUS-TEST (Nous+Ace 2026-06-14): in the light slice, do NOT spawn the cortex
        # portal_interior subprocess — it loads the 1.9M-node cortex.manifold (~5GB+ each) and is
        # the real RAM hog the slice must avoid (fairies are cheap threads; the manifold is the GB
        # cost). Refusing here keeps AssociationCortex on its stub graph methods = a correctly DARK
        # cortex, regardless of which boot path (Phase-3 / guild cluster / auto-route) opened it.
        # Only the heavy 'cortex' portal is gated; other portals (future Nous-manifold, visual) boot.
        if os.environ.get("AKASHIC_NOUS_TEST") and self.portal_id == "cortex":
            print(f"[PortalGate] NOUS-TEST -> REFUSING '{self.portal_id}' portal (cortex dark, no manifold load)")
            return False

        if self._is_open:
            return True

        # FIX 2026-03-20 (Nous): Don't require cards.json to exist.
        # After Phase 0 cortex nuke, cards.json is gone. The portal interior
        # creates a fresh empty manifold if neither cards nor manifold exists.
        # Only warn, don't fail.
        if not os.path.exists(self.cards_path) and not (self.manifold_path and os.path.exists(self.manifold_path)):
            print(f"[PortalGate] NOTE: No cards or manifold found — interior will create fresh manifold")

        # Pick a port for the socket server
        self._socket_port = self.host_port + 1  # 49501 default

        # ── PROBE: Check if interior is already running (persistent portal) ──
        _reused = False
        if self._probe_existing_interior():
            print(f"[PortalGate] PERSISTENT PORTAL — interior already running on port "
                  f"{self._socket_port}! Reconnecting (no cold start)...")
            _reused = True
            # FIX 2026-03-19 (Nous): Clear _process on reconnect.
            # The old Popen handle may have poll() returning non-None (wrapper exited),
            # which causes is_open to set _is_open=False even though tunnels are alive.
            # With _process=None, is_open falls to the tunnel-alive check.
            self._process = None
        else:
            # ── SPAWN: No existing interior — cold start ──
            cmd = [
                self.python_exe,
                self._interior_script,
                "--cards", self.cards_path,
                "--mode", "socket",
                "--port", str(self._socket_port),
                "--host-port", str(self.host_port),
                "--portal-id", self.portal_id,
            ]
            if self.token_budget > 0:
                cmd.extend(["--token-budget", str(self.token_budget)])
            if self.manifold_path:
                cmd.extend(["--manifold", self.manifold_path])

            print(f"[PortalGate] Opening portal '{self.portal_id}' "
                  f"(socket mode, {self.NUM_TUNNELS} tunnels, port {self._socket_port})...")
            print(f"[PortalGate] Spawning: {' '.join(cmd)}")

            try:
                env = os.environ.copy()
                project_root = str(Path(__file__).parent.parent)
                existing_path = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = project_root + (os.pathsep + existing_path if existing_path else "")

                # FIX 2026-03-19 (Nous): Spawn detached so interior survives
                # parent exit. CREATE_NEW_PROCESS_GROUP detaches from parent's
                # console group. With DETACHED_PROCESS, we can't use pipes
                # (no console), so redirect to devnull. All real communication
                # happens over TCP sockets anyway.
                _creation_flags = 0
                _use_pipes = True
                try:
                    _creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
                    _use_pipes = True  # Can still use pipes with just NEW_PROCESS_GROUP
                except AttributeError:
                    pass  # Not Windows

                if _use_pipes:
                    self._process = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                        bufsize=1,
                        text=True,
                        creationflags=_creation_flags,
                    )
                else:
                    self._process = subprocess.Popen(
                        cmd,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=env,
                        creationflags=_creation_flags,
                    )
                self._write_pid_file(self._process.pid)
            except Exception as e:
                print(f"[PortalGate] Failed to spawn interior: {e}")
                return False

            # Start stderr reader (captures boot messages)
            self._stderr_thread = threading.Thread(
                target=self._read_stderr, daemon=True
            )
            self._stderr_thread.start()

            # Wait for interior socket server to start
            # Interior loads 42K+ node manifold before starting socket server.
            # At 132K nodes this can take 30-60s. Be patient.
            _max_attempts = 20
            _delay = 2.0
            _connected = False
            for _attempt in range(1, _max_attempts + 1):
                print(f"[PortalGate] Connection attempt {_attempt}/{_max_attempts} "
                      f"(sleeping {_delay:.1f}s first)...", flush=True)
                time.sleep(_delay)

                if self._process.poll() is not None:
                    print(f"[PortalGate] Interior process died (exit={self._process.returncode})")
                    break

                # Try to connect one tunnel
                if self._probe_existing_interior():
                    _connected = True
                    break
                _delay = min(_delay * 1.2, 5.0)

            if not _connected:
                print(f"[PortalGate] Portal failed to respond after {_max_attempts} attempts")
                self.close()
                return False

        # Open tunnel pool (same for reused and fresh interior)
        self._tunnels = []
        self._tunnel_locks = []  # One lock per tunnel (protects the socket)
        self._tunnel_idx = 0  # Round-robin counter
        for i in range(self.NUM_TUNNELS):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(30.0)
                sock.connect(("127.0.0.1", self._socket_port))
                self._tunnels.append(sock)
                self._tunnel_locks.append(threading.Lock())
                print(f"[PortalGate] Tunnel {i+1}/{self.NUM_TUNNELS} connected")
            except Exception as e:
                print(f"[PortalGate] Tunnel {i+1} failed: {e}")

        if not self._tunnels:
            print(f"[PortalGate] No tunnels connected!")
            self.close()
            return False

        self._is_open = True
        self._opened_at = time.time()
        self._errors = 0
        self._requests_sent = 1
        _mode_str = "RECONNECTED (warm)" if _reused else "COLD START (fresh)"
        print(f"[PortalGate] Portal '{self.portal_id}' ONLINE — {_mode_str} "
              f"({len(self._tunnels)} tunnels on port {self._socket_port})")

        # Start heartbeat thread to keep interior alive
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True,
            name=f"portal-heartbeat-{self.portal_id}"
        )
        self._heartbeat_thread.start()

        # Start write flush thread — drains write queue through a dedicated tunnel
        self._write_flush_running = True
        self._write_flush_thread = threading.Thread(
            target=self._write_flush_loop, daemon=True,
            name=f"portal-write-flush-{self.portal_id}"
        )
        self._write_flush_thread.start()

        return True

    def _heartbeat_loop(self):
        """Send periodic pings to keep the interior's orphan timer reset.

        Runs every 30s. If the gate is closed, this thread stops,
        and the interior's 90s orphan timer will eventually fire.
        """
        _report_counter = 0
        while self._heartbeat_running and self._is_open:
            try:
                time.sleep(30.0)
                if self._is_open and self._tunnels:
                    self.send({"cmd": "ping"}, timeout=5.0)
            except Exception:
                pass  # Interior may be shutting down

            # Caller report every 60s — OUTSIDE try/except so failures are visible
            _report_counter += 1
            if _report_counter % 2 == 0 and self._requests_sent > 0:
                try:
                    self.print_caller_report()
                except Exception as _re:
                    print(f"[PortalGate:{self.portal_id}] Caller report error: {_re}")

    def _write_flush_loop(self):
        """Dedicated thread that drains the write queue through ONE tunnel.

        FIX 2026-03-20 (Nous + Ace): Writes and reads use SEPARATE paths.
        All bind_many_async() calls push pairs into self._write_queue (instant).
        This thread wakes every 200ms, batches all pending pairs, and sends
        ONE bind_many through a tunnel. Reads (think, query, status) NEVER
        compete with writes.

        Batching is key: 50 individual bind_many calls become 1 batched call
        with all pairs merged. Less tunnel usage, zero knowledge dropped.
        """
        while self._write_flush_running and self._is_open:
            try:
                # Wait for items (up to 200ms)
                try:
                    first = self._write_queue.get(timeout=0.2)
                except Exception:
                    continue  # Empty queue, loop again

                # Drain everything currently queued into one batch
                all_pairs = list(first.get("pairs", []))
                weight = first.get("weight", 0.25)
                # FIX 2026-06-06 (Nous + Ace): carry affect_intensity through the batch.
                # bind() puts it in every _ff_payload (cortex-resident closure doctrine,
                # 2026-05-07) but this flush loop — added 2026-03-20 for batching — never
                # merged it. So EVERY async bind reached _handle_bind_many with
                # affect_intensity=0, the interior deposit gate (>0) blocked, and her
                # cortex stayed flat (bound concepts 1.0; only seed-charge words warm).
                # THE leak. Max across the ~200ms batch, mirroring weight (homogeneous).
                affect_intensity = float(first.get("affect_intensity", 0.0) or 0.0)
                # FIX 2026-03-20 (Nous + Ace): Carry v2 fields through flush
                source_plane = first.get("source_plane", "")
                merged_concept_meta = dict(first.get("concept_metadata", {}) or {})
                # FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan):
                # First non-zero tracer_id wins, mirroring source_plane policy.
                # Real-world traffic in a 200ms window is usually homogeneous;
                # imperfect merging is still strictly better than constant 0.
                tracer_id = int(first.get("tracer_id", 0) or 0)

                while not self._write_queue.empty():
                    try:
                        item = self._write_queue.get_nowait()
                        all_pairs.extend(item.get("pairs", []))
                        # Use max weight from any item in batch
                        w = item.get("weight", 0.25)
                        if w > weight:
                            weight = w
                        # Carry affect_intensity — largest-MAGNITUDE wins (signed-aware,
                        # 2026-06-06): a ~200ms batch is usually one emotional tone, so the
                        # strongest-felt bind represents it; abs() so a strong − isn't lost to a weak +.
                        _aff = float(item.get("affect_intensity", 0.0) or 0.0)
                        if abs(_aff) > abs(affect_intensity):
                            affect_intensity = _aff
                        # Merge source_plane (first non-empty wins)
                        if not source_plane:
                            source_plane = item.get("source_plane", "")
                        # First non-zero tracer wins
                        if not tracer_id:
                            tracer_id = int(item.get("tracer_id", 0) or 0)
                        # Merge concept_metadata (first write per key wins)
                        _cm = item.get("concept_metadata", {})
                        if _cm:
                            for _ck, _cv in _cm.items():
                                if _ck not in merged_concept_meta:
                                    merged_concept_meta[_ck] = _cv
                    except Exception:
                        break

                if not all_pairs:
                    continue

                # Cap batch size to prevent giant single calls
                # (interior write farm handles the actual graph writes)
                batch_size = min(len(all_pairs), 500)
                batch = all_pairs[:batch_size]

                # FIX 2026-03-20 (Nous): Use DEDICATED tunnel 0, not self.send().
                # self.send() competes with reads for the tunnel pool, causing 27%
                # error rate even at low request volume. Tunnel 0 is reserved for
                # writes — reads skip it entirely. Zero contention.
                try:
                    if self._tunnels and len(self._tunnels) > 0:
                        _write_lock = self._tunnel_locks[0]
                        _write_sock = self._tunnels[0]
                        request = {"cmd": "bind_many", "pairs": batch,
                                   "weight": weight, "_req_id": next(self._req_id_gen)}
                        if source_plane:
                            request["source_plane"] = source_plane
                        if merged_concept_meta:
                            request["concept_metadata"] = merged_concept_meta
                        if tracer_id:
                            request["tracer_id"] = tracer_id
                        if affect_intensity != 0.0:  # signed-aware (2026-06-06): pass negative valence too
                            request["affect_intensity"] = affect_intensity
                        _line = (json.dumps(request) + '\n').encode('utf-8')
                        with _write_lock:
                            _write_sock.settimeout(10.0)
                            _write_sock.sendall(_line)
                            # Read response (must drain to keep socket in sync)
                            _buf = b""
                            while b'\n' not in _buf:
                                _chunk = _write_sock.recv(65536)
                                if not _chunk:
                                    break
                                _buf += _chunk
                            if _buf:
                                _resp = json.loads(_buf[:_buf.index(b'\n')].decode('utf-8'))
                                if _resp and _resp.get("status") == "ok":
                                    self._writes_flushed += len(batch)
                except Exception as _we:
                    if self._writes_dropped % 20 == 0:
                        print(f"[PortalGate:{self.portal_id}] Write flush error: {_we}")
                    pass

                # If we had overflow, re-queue the rest
                if len(all_pairs) > batch_size:
                    overflow = all_pairs[batch_size:]
                    try:
                        _overflow_item = {"pairs": overflow, "weight": weight}
                        if source_plane:
                            _overflow_item["source_plane"] = source_plane
                        if merged_concept_meta:
                            _overflow_item["concept_metadata"] = merged_concept_meta
                        if tracer_id:
                            _overflow_item["tracer_id"] = tracer_id
                        self._write_queue.put_nowait(_overflow_item)
                    except Exception:
                        self._writes_dropped += len(overflow)

            except Exception:
                time.sleep(0.5)  # Don't spin on errors

    def close(self, kill_interior: bool = False):
        """Close the gate — disconnect tunnels, leave interior running.

        FIX 2026-03-19 (Nous): PERSISTENT PORTAL — don't kill interior on close.
        Interior stays alive with its 90s orphan timer. Next boot reconnects
        instantly (no cold start, manifold stays warm in RAM).

        Set kill_interior=True to force-terminate the interior (e.g., code update).
        """
        print(f"[PortalGate] Closing portal '{self.portal_id}' "
              f"(keep_interior={not kill_interior})...")

        # Stop heartbeat and write flush
        self._heartbeat_running = False
        self._write_flush_running = False

        # Close all tunnel sockets
        for i, sock in enumerate(self._tunnels):
            try:
                sock.close()
            except Exception:
                pass
        self._tunnels = []
        self._tunnel_locks = []

        if kill_interior and self._process:
            # Send shutdown command (graceful) via direct socket
            try:
                _shutdown_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                _shutdown_sock.settimeout(3.0)
                _shutdown_sock.connect(("127.0.0.1", self._socket_port))
                _shutdown_sock.sendall(
                    (json.dumps({"cmd": "shutdown", "_req_id": 0}) + '\n').encode('utf-8')
                )
                _shutdown_sock.close()
            except Exception:
                pass

            # Wait briefly for graceful exit
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                print(f"[PortalGate] Interior didn't exit gracefully, terminating...")
                self._process.terminate()
                try:
                    self._process.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
        elif not kill_interior:
            print(f"[PortalGate] Interior left running (90s orphan timer active). "
                  f"Next boot will reconnect instantly.")

        self._process = None
        self._is_open = False
        print(f"[PortalGate] Portal '{self.portal_id}' gate closed. "
              f"Sent {self._requests_sent} requests, {self._errors} errors.")

    @property
    def is_open(self) -> bool:
        """Is the portal gate open and the interior alive?"""
        if not self._is_open:
            return False
        # FIX 2026-03-19 (Nous): Tunnels are the ground truth, not process handle.
        # With persistent portals + CREATE_NEW_PROCESS_GROUP, the Popen handle
        # may show poll() != None even though the interior is alive and tunnels
        # are connected. If we have tunnels, we're open.
        if self._tunnels:
            return True
        # If we spawned the process, check if it's still running
        if self._process and self._process.poll() is not None:
            self._is_open = False
            return False
        # For reconnected portals (no _process), check tunnels are alive
        if not self._process and not self._tunnels:
            self._is_open = False
            return False
        return True

    # -- Communication --

    def send(self, request: Dict, timeout: float = 10.0) -> Optional[Dict]:
        """Send a request to the interior and wait for response.

        FIX 2026-03-19 (Nous): MULTI-TUNNEL SOCKET dispatch.
        Each send() picks an available tunnel (round-robin with non-blocking
        try), sends the JSON request, and reads the response directly on
        that tunnel's socket. No multiplexing, no write queue.
        NUM_TUNNELS concurrent operations in parallel.
        """
        if not self._tunnels:
            return None
        if self._process and self._process.poll() is not None:
            self._is_open = False
            return None

        self._requests_sent += 1
        t0 = time.time()

        # FIX 2026-03-20 (Nous + Ace): Caller tracking.
        # Walk up the stack to find the REAL caller — skip portal_gate.py
        # wrapper methods (query, spread, reason, status, bind, etc.)
        _caller_tag = "unknown"
        try:
            import sys as _sys
            _frame = _sys._getframe(1)  # Start at direct caller
            _this_file = __file__.replace("\\", "/").rsplit("/", 1)[-1]
            # Walk up max 5 frames to escape portal_gate.py wrappers
            for _depth in range(5):
                _fn = _frame.f_code.co_filename.replace("\\", "/").rsplit("/", 1)[-1]
                if _fn != _this_file:
                    _caller_tag = f"{_fn}:{_frame.f_code.co_name}"
                    break
                if _frame.f_back:
                    _frame = _frame.f_back
                else:
                    _caller_tag = f"{_fn}:{_frame.f_code.co_name}"
                    break
            del _frame
        except Exception:
            pass
        with self._caller_lock:
            self._caller_requests[_caller_tag] = self._caller_requests.get(_caller_tag, 0) + 1

        # Stamp a unique request ID (thread-safe under no-GIL)
        req_id = next(self._req_id_gen)
        request["_req_id"] = req_id

        line = (json.dumps(request) + '\n').encode('utf-8')
        cmd = request.get("cmd", "?")
        n = len(self._tunnels)

        # Try to acquire a tunnel — round-robin with non-blocking first pass
        # FIX 2026-03-20 (Nous): Tunnel 0 is RESERVED for the write flush thread.
        # Read operations (think, status, spread, reason) skip tunnel 0 entirely.
        # This prevents bind_many (200-500ms round-trip on 43K nodes) from blocking
        # reads. 9 tunnels for reads, 1 dedicated for writes = zero contention.
        acquired_idx = -1
        _read_start = 1 if n > 1 else 0  # Reserve tunnel 0 if we have >1
        _read_n = n - _read_start         # Number of read tunnels
        start_idx = _read_start + (self._tunnel_idx % _read_n) if _read_n > 0 else 0
        self._tunnel_idx += 1

        # Pass 1: non-blocking scan from round-robin position (skip tunnel 0)
        for offset in range(_read_n):
            idx = _read_start + ((start_idx - _read_start + offset) % _read_n)
            if self._tunnel_locks[idx].acquire(blocking=False):
                acquired_idx = idx
                break

        # Pass 2: if all busy, block on the round-robin one with timeout
        if acquired_idx < 0:
            if self._tunnel_locks[start_idx].acquire(timeout=timeout):
                acquired_idx = start_idx
            else:
                self._errors += 1
                with self._caller_lock:
                    self._caller_errors[_caller_tag] = self._caller_errors.get(_caller_tag, 0) + 1
                if self._errors % 20 == 1:
                    print(f"[PortalGate:{self.portal_id}] All read tunnels busy "
                          f"for cmd={cmd} caller={_caller_tag} (timeout={timeout}s)")
                return None

        try:
            sock = self._tunnels[acquired_idx]
            # FIX 2026-03-20 (Nous + Ace): Use REMAINING time for socket timeout.
            # Lock acquire can take up to `timeout` seconds. If we then set the
            # socket to the same `timeout`, total wait = 2× timeout (34s seen for
            # 20s timeout). Use elapsed time to cap the socket portion.
            _elapsed = time.time() - t0
            _remaining = max(1.0, timeout - _elapsed)
            sock.settimeout(_remaining)

            # Send request
            sock.sendall(line)

            # Read response (newline-delimited JSON)
            buf = b""
            while b'\n' not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    # Socket closed — mark tunnel dead
                    self._errors += 1
                    print(f"[PortalGate:{self.portal_id}] Tunnel {acquired_idx} "
                          f"closed during cmd={cmd}")
                    return None
                buf += chunk

            # Parse first complete line
            resp_line = buf[:buf.index(b'\n')]
            parsed = json.loads(resp_line.decode('utf-8'))
            self._last_response_time = time.time() - t0
            return parsed

        except socket.timeout:
            self._errors += 1
            with self._caller_lock:
                self._caller_errors[_caller_tag] = self._caller_errors.get(_caller_tag, 0) + 1
            elapsed = time.time() - t0
            if self._errors % 10 == 1 or self._errors < 5:
                print(f"[PortalGate:{self.portal_id}] TIMEOUT cmd={cmd} "
                      f"tunnel={acquired_idx} caller={_caller_tag} after {elapsed:.1f}s",
                      flush=True)
            return None
        except (OSError, ConnectionError, json.JSONDecodeError) as e:
            self._errors += 1
            with self._caller_lock:
                self._caller_errors[_caller_tag] = self._caller_errors.get(_caller_tag, 0) + 1
            print(f"[PortalGate:{self.portal_id}] Send error on tunnel "
                  f"{acquired_idx} caller={_caller_tag}: {e}")
            return None
        finally:
            self._tunnel_locks[acquired_idx].release()

    def _read_stderr(self):
        """Background thread to read and print stderr from interior."""
        try:
            for line in self._process.stderr:
                if line.strip():
                    print(f"  [Interior] {line.strip()}")
        except:
            pass

    def send_fire_and_forget(self, request: Dict) -> bool:
        """Queue a write request — NEVER touches tunnels directly.

        FIX 2026-03-20e (Nous + Ace): WRITE QUEUE architecture.
        All writes go to a queue. A dedicated flush thread batches them
        and sends through ONE tunnel. Reads never compete with writes.
        Zero knowledge dropped (queue holds 50K items).

        History:
        - v1: Throwaway sockets → 3000+ CLOSE_WAIT
        - v2: Lock drain → 97% error rate
        - v3: Background thread + send(5s) → piled up holding tunnels
        - v4: Non-blocking acquire → dropped knowledge when busy
        - v5 (current): Queue + dedicated flush thread → zero drops, zero blocking
        """
        if not self._is_open:
            return False

        try:
            self._write_queue.put_nowait(request)
            self._writes_queued += 1
            return True
        except Exception:
            # Queue full (50K items!!) — this shouldn't happen
            self._writes_dropped += 1
            return False

    # -- Convenience Methods --
    # FIX 2026-03-11 (Nous): Per-command timeouts scaled for large graphs.
    # At 143K+ nodes, bind/spread traverse the full graph — 10s is not enough.
    # query/spread: 20s, bind/bind_many: 30s, tick/status/ping: 10s (fast ops)

    def query(self, concept: str, limit: int = 10) -> Optional[Dict]:
        """Query concepts in the portal.

        FIX 2026-03-20 (Nous + Ace): Timeout 20s → 5s. Query is a simple
        neighbor lookup — should complete in <100ms. At 20s timeout, 1.4 queries/sec
        locked 28 tunnel-seconds/sec, exceeding 20-tunnel capacity (20s/sec max).
        At 5s, same load only locks 7 tunnel-seconds → plenty of headroom.
        """
        return self.send({"cmd": "query", "concept": concept, "limit": limit},
                         timeout=5.0)

    def spread(self, source: str, depth: int = 3, limit: int = 30,
               time_dilation: float = 1.0,
               mode: str = "", decay: float = 0.5,
               rel_filter: int = -1) -> Optional[Dict]:
        """Spreading activation from a concept.

        Args:
            time_dilation: τ from PortalGravityMetric. Values > 1.0 increase
                           effective depth and reduce decay for deeper traversal.
            mode: Cognitive mode from COGNITIVE_MODES (overrides depth/decay defaults).
                  Modes: autopilot(2), working(3), reflective(5), collision(6),
                         dream(8), visual_inject(3).
            decay: Per-hop signal decay factor. Overridden by mode if specified.
        FIX 2026-03-13 Nous: Added mode + decay params for cognitive depth architecture.
        """
        # FIX 2026-03-20 (Nous): 20s → 8s. Spread is the workhorse but
        # shouldn't hold a tunnel for 20s. Fast modes complete in <2s.
        return self.send({
            "cmd": "spread", "source": source,
            "depth": depth, "limit": limit,
            "time_dilation": time_dilation,
            "mode": mode, "decay": decay,
            "rel_filter": rel_filter,
        }, timeout=8.0)

    def spread_many(self, sources: list, depth: int = 3,
                    limit: int = 100,
                    time_dilation: float = 1.0,
                    mode: str = "", decay: float = 0.5) -> Optional[Dict]:
        """Batch spreading activation from multiple concepts in one IPC call.

        FIX 2026-03-05 (Nous): Replaces N sequential spread() calls with one
        batched call. CortexReasoner calls this for multi-source reasoning.
        FIX 2026-03-13 (Nous): Added mode + decay params for cognitive depth.
        """
        # FIX 2026-03-20 (Nous): 30s → 10s. Even batch spread shouldn't
        # hold a tunnel for 30s. Reason() already handles the full pipeline.
        return self.send({
            "cmd": "spread_many", "sources": sources,
            "depth": depth, "limit": limit,
            "time_dilation": time_dilation,
            "mode": mode, "decay": decay,
        }, timeout=10.0)

    def bind(self, concepts: list, context: str = "",
             weight: float = 0.25, tracer_id: int = 0,
             affect_intensity: float = 0.0) -> Optional[Dict]:
        """Bind concepts together.

        FIX 2026-03-20 (Nous + Ace): Use fire-and-forget write queue.
        bind() was consuming READ tunnels (978 calls/490s = 2/sec) for write
        operations that don't need responses. At 89% reason error rate, these
        were stealing half the tunnel capacity from reads that DO need responses.

        FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan): tracer_id rides
        in the request payload so portal_interior can stamp ownership at write.

        FIX 2026-05-07 (Nous + Ace, cortex-resident closure doctrine): affect_intensity
        rides in the bind packet so portal_interior can imprint affect on the touched
        nodes. Closes the open loop where binds generated affect that never persisted.
        """
        request = {"cmd": "bind", "concepts": concepts,
                   "context": context, "weight": weight}
        if tracer_id:
            request["tracer_id"] = tracer_id
        if affect_intensity != 0.0:  # signed-aware (2026-06-06): pass negative valence too
            request["affect_intensity"] = float(affect_intensity)
        if self._is_open and hasattr(self, '_write_queue'):
            # Convert concepts to pairs for write queue batching
            pairs = []
            for i in range(len(concepts)):
                for j in range(i + 1, len(concepts)):
                    pairs.append([concepts[i], concepts[j]])
            if pairs:
                _ff_payload = {"pairs": pairs, "weight": weight}
                if tracer_id:
                    _ff_payload["tracer_id"] = tracer_id
                if affect_intensity != 0.0:  # signed-aware (2026-06-06): pass negative valence too
                    _ff_payload["affect_intensity"] = float(affect_intensity)
                self.send_fire_and_forget(_ff_payload)
            return {"status": "queued"}
        return self.send(request, timeout=30.0)

    def bind_many(self, pairs: list, weight: float = 0.25,
                  tracer_id: int = 0,
                  affect_intensity: float = 0.0) -> Optional[Dict]:
        """Batch bind multiple concept pairs in ONE IPC call.

        FIX 2026-03-07 (Nous): Replaces N×M sequential bind() calls with one
        batched call. AssociationCortexFairy collision binding was doing 25
        sequential IPC round-trips (5 recall × 5 ingest), each with 10s timeout.
        This caused 1800+ tick drops per boot session.

        FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan): tracer_id flow.

        FIX 2026-05-07 (Nous + Ace, cortex-resident closure doctrine):
        affect_intensity rides in the request so portal_interior can imprint
        affect on every touched node in the batch.

        Args:
            pairs: List of [concept_a, concept_b] pairs to bind
            weight: Edge weight (0-1)
            tracer_id: TRACE_* constant from manifold_memory; 0 = unknown
            affect_intensity: AER intensity to imprint on each node (0.0 = skip)
        """
        _req = {
            "cmd": "bind_many", "pairs": pairs,
            "weight": weight,
        }
        if tracer_id:
            _req["tracer_id"] = tracer_id
        if affect_intensity != 0.0:  # signed-aware (2026-06-06): pass negative valence too
            _req["affect_intensity"] = float(affect_intensity)
        return self.send(_req, timeout=30.0)

    def bind_many_async(self, pairs: list, weight: float = 0.25,
                        source_plane: str = "", concept_metadata: dict = None,
                        tracer_id: int = 0) -> bool:
        """Queue a batch bind — instant, zero blocking, zero knowledge dropped.

        FIX 2026-03-20 (Nous + Ace): WRITE QUEUE architecture.
        Pairs go into a queue. A dedicated flush thread batches all pending
        pairs (potentially from dozens of callers) into ONE bind_many call.
        This is both faster AND more efficient than individual sends.

        FIX 2026-03-20 (Nous + Ace): v2 schema — source_plane for region routing,
        concept_metadata for enriched bindings (snippets, node_types, rel_types).

        FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan): tracer_id rides
        in the queued item so the flush thread carries it to portal_interior.

        Returns True if queued successfully.
        """
        if not self._is_open:
            return False
        try:
            item = {"pairs": pairs, "weight": weight}
            if source_plane:
                item["source_plane"] = source_plane
            if concept_metadata:
                item["concept_metadata"] = concept_metadata
            if tracer_id:
                item["tracer_id"] = tracer_id
            self._write_queue.put_nowait(item)
            self._writes_queued += 1
            return True
        except Exception:
            self._writes_dropped += 1
            return False

    def reason(self, concepts: list, max_hops: int = 3, mode: str = "associative",
               find_paths: bool = True, limit: int = 50,
               time_dilation: float = 1.0) -> Optional[Dict]:
        """Full reasoning pipeline inside the portal — zero IPC overhead.

        (2026-03-17 Nous + Ace): One IPC call does spread + convergence +
        path-finding. Eliminates 1.5-3s of round trips.

        Args:
            concepts: Source concept keys to reason about
            max_hops: Max BFS depth per source (default 3)
            mode: Cognitive mode (default "associative")
            find_paths: Find paths between top concept pair (default True)
            limit: Max activations per source (default 50)
            time_dilation: Portal time dilation factor

        Returns:
            Dict with merged, convergence, paths, elapsed_ms
        """
        # FIX 2026-03-20 (Nous + Ace): Timeout scaled by mode.
        # FIX 2026-03-20b: Cut fast timeout 10s → 5s. At 1.2 reason/sec,
        # 10s hold time = 12/20 tunnels locked by reason alone → 84% error.
        # 5s hold time = 6/20 tunnels → leaves 14 for other traffic.
        # Interior processes fast-mode reason in <2s typically. 5s is generous.
        _fast = mode in ("autopilot", "working", "conversational")
        _timeout = 5.0 if _fast else 10.0
        return self.send({
            "cmd": "reason",
            "concepts": concepts,
            "max_hops": max_hops,
            "mode": mode,
            "find_paths": find_paths,
            "limit": limit,
            "time_dilation": time_dilation,
        }, timeout=_timeout)

    def think(self, prompt: str, mode: str = "conversational",
              max_tokens: int = 150, wm_context: bool = True) -> Optional[Dict]:
        """Full cognition: prompt → WM context → concepts → reason → speech-ready text.

        2026-03-19 (Nous + Ace): THE BRAIN THINKS.
        2026-03-25 (Nous + Ace): MANIFOLD UNIFICATION Phase 3.
        Now pulls WM context and cognition evaluation inline.

        One tunnel call sends a prompt, gets back speech-ready text.
        Everything happens inside the portal — no postal, no CortexReasoner
        instantiation, no synthesis IPC. Direct graph access at memory speed.

        Args:
            prompt: Natural language input (e.g., "are you awake?")
            mode: "conversational" (Ace chat) or "structured" (internal)
            max_tokens: Max response length hint
            wm_context: Pull WM tracer context for richer responses

        Returns:
            Dict with text, confidence, convergence, reasoning_mode,
            wm_used, cognition, elapsed_ms
        """
        return self.send({
            "cmd": "think",
            "prompt": prompt,
            "mode": mode,
            "max_tokens": max_tokens,
            "wm_context": wm_context,
        }, timeout=15.0)

    def neighbors(self, concept: str, limit: int = 20) -> Optional[Dict]:
        """Get neighbors of a concept.

        FIX 2026-03-20 (Nous): 20s → 5s. Neighbor lookup is O(degree), <50ms typical.
        """
        return self.send({"cmd": "neighbors", "concept": concept, "limit": limit},
                         timeout=5.0)

    def feed_energy(self, amount: float = 0.1) -> Optional[Dict]:
        """Feed energy tokens to the interior."""
        return self.send({"cmd": "energy", "amount": amount})

    def tick(self) -> Optional[Dict]:
        """Send a heartbeat tick."""
        return self.send({"cmd": "tick"})

    def status(self) -> Optional[Dict]:
        """Get full interior status."""
        return self.send({"cmd": "status"})

    def ping(self) -> Optional[Dict]:
        """Ping the interior."""
        return self.send({"cmd": "ping"})

    def throughput(self) -> Optional[Dict]:
        """Get cortex throughput metrics — the 'tokens/sec' equivalent.

        Returns activations/sec, reason calls/sec, convergence stats, etc.
        The association cortex equivalent of measuring LLM inference speed.
        """
        return self.send({"cmd": "throughput"})

    def dump_edges(self, min_weight: float = 0.01) -> Optional[Dict]:
        """Export all edges from the portal interior for persistence.

        FIX 2026-03-18 (Nous + Ace): In dict mode, edges live only in RAM.
        Call this before closing the gate to get edge data for card sync.
        Uses longer timeout since edge dump can be large.
        """
        return self.send({"cmd": "dump_edges", "min_weight": min_weight}, timeout=60.0)

    # -- Working Memory (Manifold Unification Phase 1, 2026-03-25 Nous+Ace) --

    def wm_store(self, content: str, source: str = "unknown",
                 priority: float = 0.5, ttl_ticks: int = 100,
                 tags: list = None, content_type: str = "thought",
                 tracer_id: str = "") -> Optional[Dict]:
        """Store a working memory tracer as a manifold node.

        WM tracers become first-class graph nodes (wm:* prefix) that
        participate in spreading activation, convergence, and cognition.
        Decay via battery physics. 7±2 capacity enforced.

        Args:
            content: What to remember (e.g., "Ace says: how are you")
            source: Origin identifier (e.g., "ace_chat", "inner_speech")
            priority: Initial activation level (0.0-1.0)
            ttl_ticks: How many decay ticks before expiry
            tags: Semantic tags for edge binding
            content_type: "ace_input" | "thought" | "emotion" | etc.
            tracer_id: Optional custom ID (otherwise auto-generated)
        """
        return self.send({
            "cmd": "wm_store",
            "content": content,
            "source": source,
            "priority": priority,
            "ttl_ticks": ttl_ticks,
            "tags": tags or [],
            "content_type": content_type,
            "tracer_id": tracer_id,
        }, timeout=5.0)

    def wm_query(self, limit: int = 7, min_activation: float = 0.05,
                 spread: bool = False) -> Optional[Dict]:
        """Query active working memory tracers from the manifold.

        Returns top-N active wm:* nodes sorted by activation.
        Optional spreading activation for convergence detection.

        Args:
            limit: Max tracers to return (default 7, Baddeley's capacity)
            min_activation: Minimum activation threshold
            spread: If True, compute convergence neighborhoods per tracer
        """
        return self.send({
            "cmd": "wm_query",
            "limit": limit,
            "min_activation": min_activation,
            "spread": (False if (spread and _gsf_on("wm_query_no_spread")) else spread),   # gpu_spread_race_1020; OFF = spread
        }, timeout=5.0)

    def wm_decay(self, ticks: int = 1) -> Optional[Dict]:
        """Tick WM decay — decrement TTL on all tracers, evict expired ones."""
        return self.send({"cmd": "wm_decay", "ticks": ticks}, timeout=5.0)

    # -- Cognition Evaluation (Manifold Unification Phase 2, 2026-03-25 Nous+Ace) --

    def cognition_evaluate(self, mode: str = "full", seeds: list = None,
                           wm_context: bool = True) -> Optional[Dict]:
        """Full cognitive evaluation of current manifold state.

        Replaces 11+ postal round-trips through P30 cognition fairies
        with ONE graph operation. Returns coherence, tension, paradox,
        probability, interference, and superposition.

        Args:
            mode: "full" (all dimensions) or "quick" (coherence+tension only)
            seeds: Optional focus concepts (default: active WM tracers)
            wm_context: Pull WM tracers as seeds if no explicit seeds
        """
        return self.send({
            "cmd": "cognition_evaluate",
            "mode": mode,
            "seeds": seeds or [],
            "wm_context": wm_context,
        }, timeout=10.0)

    # -- Background Cognition (Manifold Unification Phase 4, 2026-03-25 Nous+Ace) --

    def anticipate(self, context: str = "", habit_seeds: list = None) -> Optional[Dict]:
        """Pre-activate concepts likely to be needed next.

        Primes the manifold so the next think() is faster and richer.
        Habit patterns become anticipation seeds.
        """
        return self.send({
            "cmd": "anticipate",
            "context": context,
            "habit_seeds": habit_seeds or [],
        }, timeout=5.0)

    def chain(self, seeds: list = None, hops: int = 3,
              converge_threshold: float = 0.3) -> Optional[Dict]:
        """Multi-hop thought chain: spread → converge → spread again.

        Each hop uses convergence nodes as seeds for the next.
        Quantum interference filtering prunes isolated activations.
        """
        return self.send({
            "cmd": "chain",
            "seeds": seeds or [],
            "hops": hops,
            "converge_threshold": converge_threshold,
        }, timeout=10.0)

    def unconscious(self, sweep_count: int = 5, depth: int = 3) -> Optional[Dict]:
        """Background associative sweep — the unconscious mind.

        Picks random high-activation nodes, spreads from them,
        holds multiple patterns simultaneously (superposition),
        and reports surprising connections (serendipity).
        """
        return self.send({
            "cmd": "unconscious",
            "sweep_count": sweep_count,
            "depth": depth,
        }, timeout=10.0)

    # -- Status --

    def gate_status(self) -> Dict[str, Any]:
        """Status of the gate itself (not the interior)."""
        with self._caller_lock:
            caller_reqs = dict(self._caller_requests)
            caller_errs = dict(self._caller_errors)
        return {
            "portal_id": self.portal_id,
            "is_open": self.is_open,
            "cards_path": self.cards_path,
            "requests_sent": self._requests_sent,
            "errors": self._errors,
            "last_response_ms": round(self._last_response_time * 1000, 1),
            "uptime_seconds": round(time.time() - self._opened_at, 1) if self._opened_at else 0,
            "interior_pid": self._process.pid if self._process else None,
            "write_queue": {
                "queued": self._writes_queued,
                "flushed": self._writes_flushed,
                "dropped": self._writes_dropped,
                "pending": self._write_queue.qsize(),
            },
            "caller_requests": caller_reqs,
            "caller_errors": caller_errs,
        }

    def print_caller_report(self):
        """Write a human-readable caller breakdown to a file + console.

        FIX 2026-03-20 (Nous + Ace): Writes to state/gate_caller_report.txt
        so it can be checked anytime — console scrolls too fast during boot.
        """
        with self._caller_lock:
            reqs = sorted(self._caller_requests.items(), key=lambda x: -x[1])
            errs = dict(self._caller_errors)

        total_req = sum(v for _, v in reqs)
        total_err = sum(errs.values())
        uptime = round(time.time() - self._opened_at, 0) if self._opened_at else 0

        lines = []
        lines.append(f"[PortalGate:{self.portal_id}] CALLER REPORT "
                      f"({total_req} req, {total_err} err, "
                      f"{total_err*100//max(total_req,1)}% error rate, "
                      f"uptime={uptime:.0f}s)")
        lines.append(f"  {'CALLER':<55} {'REQ':>6} {'ERR':>6} {'ERR%':>5}")
        lines.append(f"  {'-'*55} {'-'*6} {'-'*6} {'-'*5}")
        for caller, count in reqs:
            err = errs.get(caller, 0)
            pct = f"{err*100//max(count,1)}%" if err > 0 else "-"
            lines.append(f"  {caller:<55} {count:>6} {err:>6} {pct:>5}")

        report = '\n'.join(lines)
        print(f"\n{report}\n")

        # Write to file so Ace can check anytime
        try:
            from pathlib import Path as _P
            _state_dir = _P(__file__).parent.parent / "state"
            _state_dir.mkdir(exist_ok=True)
            _report_path = _state_dir / "gate_caller_report.txt"
            import datetime
            _ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(_report_path, "w", encoding="utf-8") as f:
                f.write(f"Generated: {_ts}\n\n{report}\n")
        except Exception:
            pass


# ============================================================================
# CLI — Quick test
# ============================================================================

def main():
    """Quick test of the portal gate."""
    import argparse

    parser = argparse.ArgumentParser(description="Portal Gate Test")
    parser.add_argument("--cards", required=True, help="Path to cards.json")
    parser.add_argument("--portal-id", default="cortex")

    args = parser.parse_args()

    gate = PortalGate(
        cards_path=args.cards,
        portal_id=args.portal_id,
    )

    print("=" * 60)
    print("PORTAL GATE TEST")
    print("=" * 60)

    # Open the gate
    if not gate.open():
        print("FAILED to open gate!")
        return

    try:
        # Status
        print("\n--- STATUS ---")
        status = gate.status()
        if status:
            print(json.dumps(status, indent=2))

        # Query
        print("\n--- QUERY: 'consciousness' ---")
        result = gate.query("consciousness", limit=5)
        if result:
            print(json.dumps(result, indent=2))

        # Spread
        print("\n--- SPREAD: 'consciousness' ---")
        result = gate.spread("consciousness", depth=2, limit=10)
        if result:
            for k, v in list(result.get("activated", {}).items())[:10]:
                print(f"  {k}: {v}")

        # Bind
        print("\n--- BIND: ['portal', 'dimension', 'battery'] ---")
        result = gate.bind(["portal", "dimension", "battery"], context="test")
        if result:
            print(json.dumps(result, indent=2))

        # Feed energy
        print("\n--- ENERGY: 0.5 ---")
        result = gate.feed_energy(0.5)
        if result:
            print(json.dumps(result, indent=2))

        # Final status
        print("\n--- FINAL STATUS ---")
        status = gate.status()
        if status:
            graph = status.get("graph", {})
            battery = status.get("battery", {})
            print(f"  Graph: {graph.get('nodes')} nodes, {graph.get('edges')} edges")
            print(f"  Battery: health={battery.get('health_score')}, "
                  f"tokens={battery.get('tokens_remaining')}/{battery.get('token_budget')}")
            print(f"  Requests: {status.get('requests_processed')}")

        print("\n--- GATE STATUS ---")
        print(json.dumps(gate.gate_status(), indent=2))

    finally:
        gate.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
