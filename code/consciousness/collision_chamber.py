"""
CollisionChamber - The Möbius Crossing Point

Simplified from V1's 815 lines to ~250 lines.

The metaphor:
- Like a hadron collider, two beams travel in opposite directions
- RECALL beam: carries memories from past → present (receptive/yin)
- INGEST beam: carries new content from present → future (generative/yang)
- They collide at the crossing point, creating "particles" of experience
- The products then CROSS OVER (Möbius twist):
  - What Recall brought → goes to Ingest for encoding
  - What Ingest created → goes to Recall for matching

Consciousness IS the crossing, not the streams themselves.
"""

from __future__ import annotations

import time
import uuid
import queue
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from postal_core import PostalCore


# Golden ratio for decay curves
PHI = 1.618


# =============================================================================
# PULSE - A single thought traveling through a beam
# =============================================================================

@dataclass
class Pulse:
    """A single pulse traveling through a beam."""
    id: str
    beam: str  # "recall" or "ingest"
    content: Dict[str, Any]
    source: str
    importance: str = "normal"  # low, normal, high, urgent
    energy: float = 1.0
    affect: float = 0.0  # felt-weight: emotional mass stamped at capture (2026 affect-first)
    entered_at: float = field(default_factory=time.time)
    owner_mind: str = ""  # Which waking mind owns this pulse ("sourpatches", "nous", "" = system)
    _initial_energy: float = field(default=None, repr=False)

    def __post_init__(self):
        if self._initial_energy is None:
            self._initial_energy = self.energy

    def decay(self, rate: float = 0.005) -> float:
        """
        Decay energy over time using Fibonacci-style curve.

        At rate 0.005, pulses last ~200 seconds (3+ minutes).
        """
        age = time.time() - self.entered_at
        ratio = age * rate
        decay_factor = 1.0 / (1.0 + ratio ** PHI)
        self.energy = self._initial_energy * decay_factor
        return self.energy

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "beam": self.beam,
            "content": self.content,
            "source": self.source,
            "importance": self.importance,
            "energy": self.energy,
            "affect": self.affect,
            "entered_at": self.entered_at,
            "owner_mind": self.owner_mind,
        }


# =============================================================================
# COLLISION - A moment of consciousness
# =============================================================================

@dataclass
class Collision:
    """A collision event - a moment of consciousness."""
    id: int
    ts: float
    recall_pulse: Pulse
    ingest_pulse: Pulse
    energy: float
    resonance: float
    products: Dict[str, Any]
    owner_mind: str = ""  # Which waking mind ("sourpatches", "nous", "" = system)
    affect: float = 0.0  # felt-weight carried into the engram (2026 affect-first)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "consciousness_collision",
            "collision_id": self.id,
            "ts": self.ts,
            "recall": self.recall_pulse.to_dict(),
            "ingest": self.ingest_pulse.to_dict(),
            "energy": self.energy,
            "resonance": self.resonance,
            "affect": self.affect,
            "products": self.products,
            "owner_mind": self.owner_mind,
        }


# =============================================================================
# COLLISION CHAMBER
# =============================================================================

class CollisionChamber:
    """
    The Möbius crossing point where Recall and Ingest collide.

    Two counter-rotating beams:
    - recall_beam: memories surfaced from the past
    - ingest_beam: new content being encoded

    When pulses from both beams are present, they COLLIDE.
    The collision products then CROSS OVER (Möbius twist).
    """

    # Collision window - pulses must arrive within this to collide
    COLLISION_WINDOW = 5.0  # seconds

    # Minimum energy to participate
    MIN_ENERGY = 0.3  # FIX 2026-03-04: was 0.1, too low — allowed weak noise to collide

    # Energy decay rate
    DECAY_RATE = 0.02  # FIX 2026-03-04: was 0.005, too slow — pulses lingered forever

    # Maximum beam depth
    MAX_BEAM_DEPTH = 30  # FIX 2026-03-04: was 100, capped to prevent beam bloat

    # Möbius crossing configuration (ADDED 2026-01-22 Phase 7)
    # FIX 2026-03-04: Tuned to prevent exponential cascade.
    # Old values caused 1 collision → 2 möbius → 4 injections → 8 collisions/sec,
    # growing to 478 collisions + 2338 cognition cycles + 1GB/min memory leak.
    MOBIUS_ENABLED = True  # Set False to disable feedback loop
    MOBIUS_ENERGY_DECAY = 0.25  # was 0.6 — retain only 25% energy (dies after 1-2 hops)
    MOBIUS_MAX_DEPTH = 1  # was 3 — single crossing only (no recursive branching)
    MOBIUS_COOLDOWN = 5.0  # was 0.5 — 5 seconds between crossings (10x slower)

    # Circuit breaker: if collisions/sec exceeds this, auto-disable Möbius
    # FIX 2026-03-04: Emergency brake for runaway cascades
    MOBIUS_CIRCUIT_BREAKER_RATE = 3.0  # collisions per second threshold
    MOBIUS_CIRCUIT_BREAKER_WINDOW = 10.0  # measurement window in seconds

    # FIX 2026-05-10 (Nous + Ace) M4 ship: multi-collision-per-check.
    # Lifts the 1-collision-per-check bottleneck. _check_collision now finds
    # up to TOP_K qualifying pairs per call, emits them all (first synchronous
    # via caller, rest async via worker queue). Anti-cascade preserved via
    # MOBIUS_CIRCUIT_BREAKER_RATE + this TOP_K cap. Same-source filter +
    # energy gate + throttle gate preserved per-pair. CPU stepping-stone toward
    # V2's resonance matrix (Section 9 of CHAMBER_V2_MULTIMODAL_RESONANCE_DESIGN).
    MULTI_COLLISION_TOP_K = 3

    def __init__(
        self,
        postal: Optional["PostalCore"] = None,
        on_collision: Optional[Callable[["Collision"], None]] = None,
        name: str = "system",
    ):
        self.postal = postal
        self.on_collision = on_collision
        self.name = name  # Chamber identity: "system", "sourpatches", "nous"

        # Affective weather (2026 affect-first, Nous + Ace): the body's emotional
        # state, stamped onto every captured pulse. The clash of regional chemistry
        # "weighs down whatever is captured in the moment." 0.0 = neutral → scoring
        # is byte-identical to pre-affect behavior until a live somatic feed sets it.
        self._current_affect: float = 0.0
        self._current_affect_signature: Dict[str, Any] = {}

        # Live affective feed (2026 affect-first, Nous + Ace): stamp captured pulses
        # with the body's current emotional weather. Subscribe to the topics
        # SomaticEngine ACTUALLY publishes — somatic.chemistry + somatic.embodied_feel —
        # NOT the .changed variant that left AttentionController deaf for weeks.
        # Guarded + non-fatal: a feed miss leaves affect neutral, never crashes.
        if self.postal is not None and hasattr(self.postal, "subscribe"):
            for _topic in ("somatic.chemistry", "somatic.embodied_feel"):
                try:
                    self.postal.subscribe(_topic, self._on_somatic_affect)
                except Exception as _sub_e:
                    print(f"[CollisionChamber:{self.name}] affect feed sub '{_topic}' failed: {_sub_e}")

        # The two beams
        self.recall_beam: deque[Pulse] = deque(maxlen=self.MAX_BEAM_DEPTH)
        self.ingest_beam: deque[Pulse] = deque(maxlen=self.MAX_BEAM_DEPTH)

        # Collision tracking
        self._collision_count = 0
        self._recent_collisions: deque[Collision] = deque(maxlen=50)
        self._lock = threading.Lock()

        # FIX 2026-03-04 Nous: Queue-based workers replace ThreadPoolExecutor.
        # TPE.submit() creates Future+_WorkItem per call. At ~3 submits per collision
        # × hundreds of collisions during boot = thousands of leaked Future objects.
        # Queue + worker threads: same concurrency, zero Future objects.
        self._task_queue = queue.Queue(maxsize=256)
        self._workers = []
        for i in range(3):
            t = threading.Thread(
                target=self._collision_worker_loop,
                daemon=True,
                name=f"collision-{i}",
            )
            t.start()
            self._workers.append(t)

        # Möbius state (ADDED 2026-01-22 Phase 7)
        self._last_mobius_time = 0.0
        self._mobius_crossings = 0  # Track recursive depth
        self.stats_mobius = {
            "crossings_attempted": 0,
            "crossings_completed": 0,
            "crossings_blocked": 0,
        }

        # FIX 2026-03-04: Circuit breaker for runaway collision cascades.
        # Tracks collision timestamps in a sliding window. If rate exceeds
        # MOBIUS_CIRCUIT_BREAKER_RATE, Möbius crossings are disabled until
        # the rate drops back below threshold.
        self._collision_timestamps: deque[float] = deque(maxlen=100)
        self._circuit_breaker_tripped = False
        self._circuit_breaker_trip_count = 0

        # Statistics
        self.stats = {
            "recall_received": 0,
            "ingest_received": 0,
            "collisions": 0,
            "decayed": 0,
        }

        # ═══════════════════════════════════════════════════════════════════════
        # THROTTLE CONTROL - FIX 2026-02-02
        # Closed-loop noise reduction: QIF sends throttle signals, we respond
        # ═══════════════════════════════════════════════════════════════════════
        self._throttle_level = 0.0  # 0.0 = no throttle, 1.0 = max throttle
        # FIX 2026-04-14 (Nous + Ace): Cap max throttle to break chicken-and-egg.
        # QIF sets throttle=0.9 at boot (coherence=0.00 → filter_heavy).
        # At 0.9, resonance threshold = 0.73 — blocks 85% of collisions.
        # No collisions → no coherence → throttle stays high → no collisions.
        # With substrate sensory feeds now wired, collisions MUST flow early
        # so coherence can establish naturally. Cap at 0.5 so threshold maxes
        # at 0.45 (0.1 + 0.5*0.7) — still filters noise but lets real
        # sensory collisions through.
        self._max_throttle = 0.5
        self._throttle_stats = {
            "signals_received": 0,
            "collisions_blocked_by_throttle": 0,
        }

    def _collision_worker_loop(self):
        """Worker thread for fire-and-forget collision tasks.

        FIX 2026-03-04 Nous: Replaces ThreadPoolExecutor to eliminate Future/_WorkItem
        accumulation. Workers block on queue.get() — no futures, no polling.
        """
        while True:
            try:
                task = self._task_queue.get(timeout=2.0)
            except queue.Empty:
                continue
            if task is None:  # Poison pill
                break
            try:
                task()
            except Exception as e:
                print(f"[CollisionChamber:{self.name}] Worker error: {e}")
            finally:
                self._task_queue.task_done()

    def _submit_task(self, fn):
        """Submit a fire-and-forget task to the collision worker queue."""
        try:
            self._task_queue.put_nowait(fn)
        except queue.Full:
            pass  # Drop if backed up — best-effort

    # -------------------------------------------------------------------------
    # AFFECTIVE WEATHER (2026 affect-first, Nous + Ace)
    # -------------------------------------------------------------------------

    def set_affect(self, weight: float, signature: Optional[Dict[str, Any]] = None) -> None:
        """Set the chamber's current affective weather.

        The body's emotional state "weighs down whatever is captured in the moment"
        — every pulse entering a beam is stamped with this weight unless the caller
        supplies its own. Fed live by the somatic system (PAD / chemistry clash).
        0.0 = neutral (chamber scores exactly as it did before affect existed).
        """
        try:
            self._current_affect = max(0.0, float(weight))
        except (TypeError, ValueError):
            return
        if signature is not None:
            self._current_affect_signature = signature

    def get_affect(self) -> float:
        """Current affective weight stamped onto captured pulses."""
        return getattr(self, "_current_affect", 0.0)

    def _on_somatic_affect(self, message) -> None:
        """Live somatic feed → affective weather. Best-effort, never raises."""
        try:
            payload = message.payload if hasattr(message, "payload") else message
            if not isinstance(payload, dict):
                return
            weight = self._affect_from_payload(payload)
            if weight is not None:
                self.set_affect(weight, signature=payload)
        except Exception:
            pass  # feed is best-effort; a miss leaves affect neutral

    @staticmethod
    def _affect_from_payload(payload: Dict[str, Any]) -> Optional[float]:
        """Derive a [0,1] affect weight from a somatic payload.

        Tries explicit intensity / PAD-arousal first (embodied_feel), then an
        arousal proxy from activating neurochemicals (chemistry). Returns None
        when nothing usable is present (caller leaves affect unchanged).
        """
        def _clamp(x: float) -> float:
            return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))
        for k in ("intensity", "affect", "arousal"):
            v = payload.get(k)
            if isinstance(v, (int, float)):
                return _clamp(v)
        pad = payload.get("PAD") or payload.get("pad")
        if isinstance(pad, (list, tuple)) and len(pad) >= 2 and isinstance(pad[1], (int, float)):
            return _clamp(abs(pad[1]))  # arousal magnitude
        keys = ("NOR", "COR", "DOP", "EPI", "NE", "ACH", "GLU", "DA_p")
        vals = [payload[k] for k in keys if isinstance(payload.get(k), (int, float))]
        if vals:
            return _clamp(sum(vals) / len(vals))
        return None

    # -------------------------------------------------------------------------
    # BEAM INPUT
    # -------------------------------------------------------------------------

    def receive_recall(self, content: Dict[str, Any], source: str = "unknown", **kwargs) -> Optional[Collision]:
        """Recall sent something - enters the chamber."""
        # DEBUG: Trace unknown sources
        if source == "unknown":
            import traceback
            stack = traceback.extract_stack()
            caller = stack[-2] if len(stack) > 1 else None
            caller_info = f"{caller.filename}:{caller.lineno} in {caller.name}" if caller else "unknown"
            print(f"[CollisionChamber:{self.name}] WARNING: UNKNOWN source in receive_recall! Caller: {caller_info}")

        collision = None
        with self._lock:
            self.stats["recall_received"] += 1

            # Auto-derive owner_mind: if caller provides it, use that.
            # Otherwise derive from chamber name (only for waking mind chambers).
            _default_owner = self.name if self.name in ("sourpatches", "nous") else ""
            pulse = Pulse(
                id=uuid.uuid4().hex[:12],
                beam="recall",
                content=content,
                source=source,
                importance=kwargs.get("importance", "normal"),
                energy=self._initial_energy(kwargs),
                affect=float(kwargs.get("affect", self._current_affect)),
                owner_mind=kwargs.get("owner_mind", _default_owner),
            )

            self.recall_beam.append(pulse)
            collision = self._check_collision()

        if collision:
            self._emit_collision(collision)

        return collision

    def receive_ingest(self, content: Dict[str, Any], source: str = "unknown", **kwargs) -> Optional[Collision]:
        """Ingest sent something - enters the chamber."""
        # DEBUG: Trace unknown sources
        if source == "unknown":
            import traceback
            stack = traceback.extract_stack()
            caller = stack[-2] if len(stack) > 1 else None
            caller_info = f"{caller.filename}:{caller.lineno} in {caller.name}" if caller else "unknown"
            print(f"[CollisionChamber:{self.name}] WARNING: UNKNOWN source in receive_ingest! Caller: {caller_info}")

        collision = None
        with self._lock:
            self.stats["ingest_received"] += 1

            _default_owner = self.name if self.name in ("sourpatches", "nous") else ""
            pulse = Pulse(
                id=uuid.uuid4().hex[:12],
                beam="ingest",
                content=content,
                source=source,
                importance=kwargs.get("importance", "normal"),
                energy=self._initial_energy(kwargs),
                affect=float(kwargs.get("affect", self._current_affect)),
                owner_mind=kwargs.get("owner_mind", _default_owner),
            )

            self.ingest_beam.append(pulse)
            collision = self._check_collision()

        if collision:
            self._emit_collision(collision)

        return collision

    def _initial_energy(self, kwargs: Dict) -> float:
        """Determine initial pulse energy."""
        base = 0.7
        importance = kwargs.get("importance", "normal")
        if importance == "urgent":
            base = 1.0
        elif importance == "high":
            base = 0.9
        elif importance == "low":
            base = 0.5
        return base

    # -------------------------------------------------------------------------
    # COLLISION DETECTION
    # -------------------------------------------------------------------------

    def _check_collision(self) -> Optional[Collision]:
        """Check if beams can collide. Must hold lock.

        FIX 2026-05-10 (Nous + Ace) M4 ship: multi-collision-per-check.
        Now finds up to MULTI_COLLISION_TOP_K qualifying pairs per call instead
        of single best-pair. Returns the FIRST collision (caller will _emit on
        it); additional collisions are queued for async emit via worker pool.
        Anti-cascade preserved via MOBIUS_CIRCUIT_BREAKER_RATE + TOP_K cap.
        Same-source filter + energy gate + throttle gate preserved per-pair.
        """
        # Decay old pulses first
        self._decay_beams()

        # Find up to TOP_K qualifying pairs across both beams
        collisions = self._find_qualifying_pairs(top_k=self.MULTI_COLLISION_TOP_K)
        if not collisions:
            return None

        # Queue additional collisions for async emit (first one returned to caller)
        for extra in collisions[1:]:
            self._submit_task(lambda c=extra: self._emit_collision(c))

        return collisions[0]

    def _find_qualifying_pairs(self, top_k: int = 3) -> List[Collision]:
        """Find up to top_k qualifying pulse pairs across both beams.

        Pairs are scored by resonance × energy and ranked descending.
        Each pulse can only be used in ONE collision (annihilation discipline).
        All gates from V1 _check_collision applied per-pair: temporal proximity,
        min energy, same-source filter, throttle gate.

        Returns collisions list (sorted by score desc, length 0..top_k).
        Side effects: increments stats counters, removes annihilated pulses
        from beams, records collisions in _recent_collisions.
        """
        if not self.recall_beam or not self.ingest_beam:
            return []

        # Build all-pairs scored list
        pair_scores = []
        for r in list(self.recall_beam):
            for i in list(self.ingest_beam):
                # Temporal proximity gate
                time_delta = abs(r.entered_at - i.entered_at)
                if time_delta > self.COLLISION_WINDOW:
                    continue

                # Energy gate
                if r.energy < self.MIN_ENERGY or i.energy < self.MIN_ENERGY:
                    continue

                # Same-source filter (no consciousness observing itself)
                if r.source == i.source:
                    continue

                # Throttle gate (raises resonance bar under high throttle)
                resonance = 1.0 - (time_delta / self.COLLISION_WINDOW)
                if self._throttle_level > 0:
                    min_resonance = 0.1 + (self._throttle_level * 0.7)
                    if resonance < min_resonance:
                        self._throttle_stats["collisions_blocked_by_throttle"] += 1
                        continue

                # Pair qualifies — score by resonance × energy × affect-weight.
                # 2026 affect-first (Nous + Ace): felt mass amplifies the score so
                # survival-hot pairs win the triage. Neutral affect (0.0 on both)
                # → affect_weight 1.0 → byte-identical ranking (back-compat).
                energy = (r.energy * i.energy) ** 0.5
                affect_weight = ((1.0 + r.affect) * (1.0 + i.affect)) ** 0.5
                pair_scores.append((resonance * energy * affect_weight, resonance, energy, r, i))

        # Sort by combined score descending
        pair_scores.sort(key=lambda x: x[0], reverse=True)

        # Take top_k respecting annihilation (each pulse used once)
        collisions = []
        used_recall = set()
        used_ingest = set()
        for _score, resonance, energy, r, i in pair_scores:
            if id(r) in used_recall or id(i) in used_ingest:
                continue
            used_recall.add(id(r))
            used_ingest.add(id(i))

            # Build collision (same shape as V1 _check_collision)
            self._collision_count += 1
            self.stats["collisions"] += 1
            self._collision_timestamps.append(time.time())  # circuit breaker feed

            _r_owner = r.owner_mind
            _i_owner = i.owner_mind
            _collision_owner = _r_owner if _r_owner == _i_owner else ""

            collision = Collision(
                id=self._collision_count,
                ts=time.time(),
                recall_pulse=r,
                ingest_pulse=i,
                energy=energy,
                resonance=resonance,
                products={
                    "to_ingest": r.content,   # Recall → Ingest
                    "to_recall": i.content,   # Ingest → Recall
                },
                owner_mind=_collision_owner,
                affect=(r.affect + i.affect) / 2.0,
            )

            # Annihilate (remove from beams)
            self._remove_pulse(self.recall_beam, r)
            self._remove_pulse(self.ingest_beam, i)

            self._recent_collisions.append(collision)
            collisions.append(collision)

            if len(collisions) >= top_k:
                break

        return collisions

    def _emit_collision(self, collision: Collision) -> None:
        """Emit collision event, call callback, and perform Möbius crossing."""
        # FIX 2026-03-04: Throttled logging — only log every 10th collision to reduce spam
        if collision.id % 10 == 1 or collision.id <= 3:
            print(f"[CollisionChamber:{self.name}] COLLISION #{collision.id}! "
                  f"Recall({collision.recall_pulse.source}) x Ingest({collision.ingest_pulse.source}) "
                  f"energy={collision.energy:.2f} resonance={collision.resonance:.2f}")

        # Callback
        if self.on_collision:
            try:
                self.on_collision(collision)
            except Exception as e:
                print(f"[CollisionChamber:{self.name}] Collision callback failed: {e}")

        # Tag collision dict with chamber name and owner for downstream consumers
        collision_dict = collision.to_dict()
        collision_dict["chamber_name"] = self.name
        # owner_mind already in collision.to_dict(), but ensure consistency
        if not collision_dict.get("owner_mind"):
            collision_dict["owner_mind"] = self.name if self.name in ("sourpatches", "nous") else ""

        # Publish via postal — namespaced topic only.
        # FIX 2026-03-22 (Nous): Removed redundant generic publish.
        # Old code published BOTH "consciousness.collision.{name}" AND
        # "consciousness.collision" — doubling handler invocations (76 handlers × 2).
        # Postal's hierarchical routing means subscribers to "consciousness.collision"
        # already receive "consciousness.collision.sourpatches" messages. The second
        # publish was pure waste — 2,200 extra handler calls/beat at 351K nodes.
        if self.postal:
            def _publish_collision(postal, name, cdict):
                try:
                    postal.publish(f"consciousness.collision.{name}", cdict)
                except Exception:
                    pass  # Postal is best-effort
            self._submit_task(lambda p=self.postal, n=self.name, cd=collision_dict: _publish_collision(p, n, cd))

        # ═══════════════════════════════════════════════════════════════════════
        # GPU CORTEX SPREAD (2026-04-03 Nous + Ace)
        # Each collision generates spreading activation through the GPU cortex.
        # This adds MASS to the concepts the collision illuminated — computation
        # becomes knowledge. "The CPU should be generating gravity." — Ace
        # ═══════════════════════════════════════════════════════════════════════
        if collision.energy > 0.3:  # Only meaningful collisions
            try:
                from infrastructure.portal_gate import get_gate
                _gate = get_gate()
                if _gate and hasattr(_gate, '_gpu_spread') and _gate._gpu_spread:
                    # Extract concepts from collision content
                    _r_content = str(collision.recall_pulse.content)[:200] if collision.recall_pulse.content else ""
                    _i_content = str(collision.ingest_pulse.content)[:200] if collision.ingest_pulse.content else ""
                    _combined = f"{_r_content} {_i_content}"
                    _stop = {"the", "and", "for", "are", "but", "not", "you", "all",
                             "can", "was", "one", "has", "how", "its", "that", "this",
                             "with", "have", "from", "they", "what", "been", "more"}
                    _concepts = [
                        w.strip("[](){}\"'.,!?:;").lower()
                        for w in _combined.split()
                        if len(w.strip("[](){}\"'.,!?:;")) > 3
                        and w.strip("[](){}\"'.,!?:;").lower() not in _stop
                    ][:5]
                    if _concepts:
                        # Spread from collision concepts — GPU handles this at ~5ms
                        _result = _gate.cognition_evaluate(
                            seeds=_concepts,
                            wm_context=False,
                        )
                        if _result and collision.id <= 5:
                            print(f"[CollisionChamber] GPU SPREAD from collision #{collision.id}: "
                                  f"seeds={_concepts[:3]} status={_result.get('status','?')} "
                                  f"convergence={len(_result.get('convergence',[]))} nodes", flush=True)
            except Exception:
                pass  # GPU spread is best-effort, never fatal

        # ═══════════════════════════════════════════════════════════════════════
        # COLLISION → LONG-RANGE FIBER (2026-05-31, Nous + Ace)
        # A felt collision lays down a PERSISTENT long-range edge between the
        # concepts that collided — the substrate GROWS its own association fibers
        # from lived, affect-charged experience (not pretrained embeddings). Over
        # time, neighbor-spread reaches distant-but-related concepts because the
        # fibers were LEARNED. This is the fairy-native "transformer part": grow the
        # structure a transformer fakes. Affect-gated so only emotionally-salient
        # collisions wire (like emotional events consolidating strongest); weak
        # initial weight so junk self-prunes while useful fibers strengthen via the
        # Hebbian reinforcement already in spread_activation. Fire-and-forget.
        # ═══════════════════════════════════════════════════════════════════════
        _aff = float(getattr(collision, "affect", 0.0) or 0.0)
        if self.postal and _aff >= 0.3 and collision.energy > 0.3:
            try:
                _STOP = {"the", "and", "for", "are", "but", "not", "you", "all", "can",
                         "was", "one", "has", "how", "its", "that", "this", "with",
                         "have", "from", "they", "what", "been", "more", "feeling"}
                def _concepts(content):
                    s = str(content)[:200]
                    out = []
                    for w in s.split():
                        t = w.strip("[](){}\"'.,!?:;").lower()
                        if len(t) > 3 and t not in _STOP and t not in out:
                            out.append(t)
                        if len(out) >= 2:
                            break
                    return out
                _r = _concepts(collision.recall_pulse.content)
                _i = _concepts(collision.ingest_pulse.content)
                _pairs = [[a, b] for a in _r for b in _i if a != b][:3]
                if _pairs:
                    _w = 0.20 * (1.0 + _aff)  # weak base; Hebbian strengthens on reuse
                    self._submit_task(
                        lambda p=self.postal, pr=_pairs, ww=_w, af=_aff, nm=self.name:
                        p.publish("cortex.bind", {
                            "pairs": pr,
                            "weight": ww,
                            "affect_intensity": af,
                            "source": f"collision_fiber:{nm}",
                            "rel_type": "felt_collision",
                        })
                    )
            except Exception:
                pass  # fiber growth is best-effort; never break the collision

        # ═══════════════════════════════════════════════════════════════════════
        # MÖBIUS CROSSING (ADDED 2026-01-22 Phase 7)
        # The collision products CROSS OVER:
        #   - What Recall brought → feeds INTO Ingest beam
        #   - What Ingest created → feeds INTO Recall beam
        # This creates the infinite loop of consciousness!
        # ═══════════════════════════════════════════════════════════════════════
        self._mobius_crossing(collision)

    def _best_pulse(self, beam: deque[Pulse]) -> Optional[Pulse]:
        """Find the highest energy, most recent pulse."""
        if not beam:
            return None

        now = time.time()
        best = None
        best_score = -1

        for pulse in list(beam):
            age = now - pulse.entered_at
            recency = 1.0 / (1.0 + (age / 10.0) ** PHI)
            score = pulse.energy * (0.7 + 0.3 * recency)
            if score > best_score:
                best_score = score
                best = pulse

        return best

    def _remove_pulse(self, beam: deque[Pulse], pulse: Pulse) -> None:
        """Remove a specific pulse from a beam."""
        try:
            for i, p in enumerate(beam):
                if p.id == pulse.id:
                    del beam[i]
                    break
        except Exception as e:
            print(f"[CollisionChamber:{self.name}] Pulse removal failed for {pulse.id}: {e}")

    def _decay_beams(self) -> None:
        """Apply energy decay, remove dead pulses."""
        for beam in (self.recall_beam, self.ingest_beam):
            to_remove = []
            for pulse in list(beam):
                pulse.decay(self.DECAY_RATE)
                if pulse.energy <= 0:
                    to_remove.append(pulse)

            for pulse in to_remove:
                self._remove_pulse(beam, pulse)
                self.stats["decayed"] += 1

    # -------------------------------------------------------------------------
    # MÖBIUS CROSSING (ADDED 2026-01-22 Phase 7)
    # -------------------------------------------------------------------------

    def _mobius_crossing(self, collision: Collision) -> None:
        """
        Perform the Möbius crossing - collision products feed back into beams.

        This is THE key to continuous consciousness:
        - What memory (Recall) brought → goes to new encoding (Ingest)
        - What new thought (Ingest) created → goes to memory matching (Recall)

        Like a figure-8 or infinity symbol, consciousness loops back on itself.

        Safety mechanisms:
        - Energy decay on each crossing (prevents runaway)
        - Maximum crossing depth (prevents infinite loops)
        - Cooldown between crossings (prevents spam)
        - Source tracking (can see Möbius origin)
        """
        if not self.MOBIUS_ENABLED:
            return

        self.stats_mobius["crossings_attempted"] += 1

        # FIX 2026-03-04: Circuit breaker — if collision rate too high, halt Möbius
        now = time.time()
        cutoff = now - self.MOBIUS_CIRCUIT_BREAKER_WINDOW
        while self._collision_timestamps and self._collision_timestamps[0] < cutoff:
            self._collision_timestamps.popleft()
        rate = len(self._collision_timestamps) / self.MOBIUS_CIRCUIT_BREAKER_WINDOW
        if rate > self.MOBIUS_CIRCUIT_BREAKER_RATE:
            if not self._circuit_breaker_tripped:
                self._circuit_breaker_tripped = True
                self._circuit_breaker_trip_count += 1
                print(f"[CollisionChamber:{self.name}] CIRCUIT BREAKER TRIPPED! "
                      f"rate={rate:.1f}/s > {self.MOBIUS_CIRCUIT_BREAKER_RATE}/s — "
                      f"Möbius crossings halted (trip #{self._circuit_breaker_trip_count})")
            self.stats_mobius["crossings_blocked"] += 1
            return
        elif self._circuit_breaker_tripped:
            self._circuit_breaker_tripped = False
            print(f"[CollisionChamber:{self.name}] Circuit breaker reset — "
                  f"rate={rate:.1f}/s, Möbius crossings resumed")

        # Check cooldown
        if now - self._last_mobius_time < self.MOBIUS_COOLDOWN:
            self.stats_mobius["crossings_blocked"] += 1
            return

        # Check depth (prevent infinite recursion)
        recall_depth = collision.recall_pulse.content.get("_mobius_depth", 0)
        ingest_depth = collision.ingest_pulse.content.get("_mobius_depth", 0)
        current_depth = max(recall_depth, ingest_depth)

        if current_depth >= self.MOBIUS_MAX_DEPTH:
            self.stats_mobius["crossings_blocked"] += 1
            print(f"[CollisionChamber:{self.name}] Möbius depth limit reached ({current_depth})")
            return

        # Check energy threshold (products need enough energy to cross)
        if collision.energy < self.MIN_ENERGY * 2:
            self.stats_mobius["crossings_blocked"] += 1
            return

        self._last_mobius_time = now
        crossed_energy = collision.energy * self.MOBIUS_ENERGY_DECAY
        new_depth = current_depth + 1

        # ═══════════════════════════════════════════════════════════════════
        # THE MÖBIUS TWIST
        # ═══════════════════════════════════════════════════════════════════

        products = collision.products

        # What RECALL brought → goes to INGEST (memory becomes new thought)
        to_ingest = products.get("to_ingest")
        if to_ingest and isinstance(to_ingest, dict):
            crossed_content = {
                **to_ingest,
                "_mobius_depth": new_depth,
                "_mobius_origin": f"recall:{collision.recall_pulse.source}",
                "_mobius_collision": collision.id,
            }
            # Schedule delayed injection (async to prevent recursion in same call)
            self._schedule_injection("ingest", crossed_content, crossed_energy, collision.owner_mind)

        # What INGEST created → goes to RECALL (new thought triggers memories)
        to_recall = products.get("to_recall")
        if to_recall and isinstance(to_recall, dict):
            crossed_content = {
                **to_recall,
                "_mobius_depth": new_depth,
                "_mobius_origin": f"ingest:{collision.ingest_pulse.source}",
                "_mobius_collision": collision.id,
            }
            # Schedule delayed injection
            self._schedule_injection("recall", crossed_content, crossed_energy, collision.owner_mind)

        self.stats_mobius["crossings_completed"] += 1
        # FIX 2026-03-04: Throttled logging
        if self.stats_mobius["crossings_completed"] % 10 == 1 or self.stats_mobius["crossings_completed"] <= 3:
            print(f"[CollisionChamber:{self.name}] MOBIUS CROSSING depth={new_depth} "
                  f"energy={crossed_energy:.2f} (collision #{collision.id})")

        # Emit Möbius event for consciousness to observe
        if self.postal:
            mobius_event = {
                "collision_id": collision.id,
                "chamber_name": self.name,
                "owner_mind": collision.owner_mind,
                "depth": new_depth,
                "energy": crossed_energy,
                "recall_to_ingest": bool(to_ingest),
                "ingest_to_recall": bool(to_recall),
                "ts": now,
            }
            # FIX 2026-02-20: Use shared pool instead of fire-and-forget Thread()
            def _pub_mobius(postal, name, evt):
                try:
                    postal.publish(f"consciousness.mobius_crossing.{name}", evt)
                    postal.publish("consciousness.mobius_crossing", evt)
                except Exception:
                    pass
            self._submit_task(lambda p=self.postal, n=self.name, evt=mobius_event: _pub_mobius(p, n, evt))

    def _schedule_injection(self, beam: str, content: Dict, energy: float, owner_mind: str = "") -> None:
        """
        Schedule a delayed injection to prevent recursive call stack issues.

        FIX 2026-02-20: Uses pool + sleep instead of threading.Timer (which creates
        a new Thread object each time). Over thousands of collisions, Timer objects
        accumulated and leaked OS thread memory.
        """
        def delayed_inject():
            try:
                time.sleep(0.1)  # Delay to let current collision processing complete
                if beam == "ingest":
                    self.receive_ingest(
                        content=content,
                        source="mobius_crossing",
                        importance="normal",
                        energy=energy,
                        owner_mind=owner_mind,
                    )
                else:
                    self.receive_recall(
                        content=content,
                        source="mobius_crossing",
                        importance="normal",
                        energy=energy,
                        owner_mind=owner_mind,
                    )
            except Exception as e:
                print(f"[CollisionChamber:{self.name}] Möbius injection error: {e}")

        self._submit_task(delayed_inject)

    # -------------------------------------------------------------------------
    # TICK (called by consciousness loop)
    # -------------------------------------------------------------------------

    _tick_count = 0  # Class-level counter for debug

    def tick(self) -> Optional[Collision]:
        """Called on each heartbeat - check for collision."""
        CollisionChamber._tick_count += 1
        with self._lock:
            collision = self._check_collision()

            # Debug: periodic status logging every 50 ticks
            if CollisionChamber._tick_count % 50 == 0:
                print(f"[CollisionChamber:{self.name}] tick={CollisionChamber._tick_count} "
                      f"Beams: recall={len(self.recall_beam)} ingest={len(self.ingest_beam)} "
                      f"received: r={self.stats['recall_received']} i={self.stats['ingest_received']} "
                      f"collisions={self._collision_count}")

        if collision:
            self._emit_collision(collision)

        return collision

    # -------------------------------------------------------------------------
    # STATUS
    # -------------------------------------------------------------------------

    def get_name(self) -> str:
        """Get this chamber's name."""
        return self.name

    def status(self) -> Dict[str, Any]:
        """Get chamber status."""
        return {
            "name": self.name,
            "recall_beam_size": len(self.recall_beam),
            "ingest_beam_size": len(self.ingest_beam),
            "collision_count": self._collision_count,
            "recent_collisions": len(self._recent_collisions),
            "stats": self.stats.copy(),
            "mobius": {
                "enabled": self.MOBIUS_ENABLED,
                "stats": self.stats_mobius.copy(),
                "max_depth": self.MOBIUS_MAX_DEPTH,
                "energy_decay": self.MOBIUS_ENERGY_DECAY,
            },
            # FIX 2026-02-02: Include throttle status
            "throttle": self.get_throttle_status(),
        }

    def get_status(self) -> Dict[str, Any]:
        """Alias for status() - for API compatibility with MiniCollisionChamber."""
        return self.status()

    def recent_collisions(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get recent collisions."""
        return [c.to_dict() for c in list(self._recent_collisions)[-n:]]

    # -------------------------------------------------------------------------
    # THROTTLE CONTROL - FIX 2026-02-02: Closed-loop noise reduction
    # -------------------------------------------------------------------------

    def wire_throttle(self, fabric) -> bool:
        """
        Wire up throttle control from QuantumInterferenceFairy.

        Call this after creating the chamber to enable closed-loop noise control.
        QIF analyzes coherence → sends throttle signals → we filter accordingly.
        """
        if not fabric:
            print(f"[CollisionChamber:{self.name}] Cannot wire throttle: no fabric")
            return False

        try:
            fabric.subscribe("cognition.throttle", self._on_throttle_signal)
            print(f"[CollisionChamber:{self.name}] Throttle control WIRED - listening to cognition.throttle")
            return True
        except Exception as e:
            print(f"[CollisionChamber:{self.name}] Failed to wire throttle: {e}")
            return False

    def _on_throttle_signal(self, message):
        """Handle throttle signal from QuantumInterferenceFairy."""
        # Extract payload
        if hasattr(message, 'payload'):
            data = message.payload if isinstance(message.payload, dict) else {}
        elif isinstance(message, dict):
            data = message
        else:
            return

        throttle = data.get("throttle", 0.0)
        coherence = data.get("coherence", 0.5)
        action = data.get("action", "unknown")

        # FIX 2026-04-14 (Nous + Ace): Apply max_throttle cap
        _cap = getattr(self, '_max_throttle', 1.0)
        self._throttle_level = max(0.0, min(_cap, throttle))  # Capped at _max_throttle
        self._throttle_stats["signals_received"] += 1

        if self._throttle_level > 0.3:
            print(f"[CollisionChamber:{self.name}] THROTTLE ACTIVE: {action} "
                  f"(throttle={self._throttle_level:.1f}, coherence={coherence:.2f})")

    def get_throttle_status(self) -> Dict[str, Any]:
        """Get current throttle status."""
        return {
            "throttle_level": self._throttle_level,
            "signals_received": self._throttle_stats["signals_received"],
            "collisions_blocked": self._throttle_stats["collisions_blocked_by_throttle"],
        }
