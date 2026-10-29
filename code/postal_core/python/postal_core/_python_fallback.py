"""
Pure Python fallback implementation of PostalCore.

This provides API compatibility when the Rust module isn't compiled.
It's slower than Rust but functionally equivalent.

Based on Whisper's parallel_fabric.py patterns.
"""

import json
import os
import queue
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import statistics

# ── PostalFarm: Dimensional battery-powered processing ──
# Lazy import to avoid circular deps — loaded on first PostalCore init
_postal_farm_instance = None  # type: Optional['PostalFarm']
_postal_farm_lock = threading.Lock()


@dataclass
class Envelope:
    """Message envelope - the fundamental unit of postal communication."""

    intent: str
    payload: Dict[str, Any] = field(default_factory=dict)
    t: int = field(default_factory=lambda: int(time.time() * 1000))
    priority: int = 1  # 0=HIGH, 1=NORMAL, 2=LOW
    source: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None
    ttl_sec: int = 0
    dedupe_key: Optional[str] = None

    def with_source(self, source: str) -> "Envelope":
        """Builder pattern: set source."""
        self.source = source
        return self

    def with_priority(self, priority: int) -> "Envelope":
        """Builder pattern: set priority (0=HIGH, 1=NORMAL, 2=LOW)."""
        self.priority = priority
        return self

    def topic(self) -> str:
        """Extract topic from intent (first segment before '.')."""
        return self.intent.split('.')[0]

    def is_expired(self) -> bool:
        """Check if envelope has expired based on TTL."""
        if self.ttl_sec == 0:
            return False
        age_ms = int(time.time() * 1000) - self.t
        return age_ms > (self.ttl_sec * 1000)


    # ═══════════════════════════════════════════════════════════════════
    # DEPRECATED 2026-03-15: Shared handler queue is NO LONGER USED.
    # Since 2026-03-12, handlers are invoked DIRECTLY on topic worker threads
    # (DIRECT INVOKE pattern). The handler queue + 16 worker threads were
    # creating 16 idle threads that did nothing. Code kept for reference but
    # _get_handler_queue() is no longer called from _worker_loop.
    # ═══════════════════════════════════════════════════════════════════
_handler_queue: Optional[queue.Queue] = None
_handler_workers: list = []
_handler_queue_lock = threading.Lock()

def _handler_worker_fn():
    """Worker thread that drains the shared handler queue."""
    q = _handler_queue
    while True:
        try:
            task = q.get(timeout=2.0)
        except queue.Empty:
            continue
        if task is None:  # Poison pill
            break
        fn, args = task
        try:
            fn(*args)
        except Exception as e:
            print(f"[PostalCore] Handler error: {e}")
        finally:
            q.task_done()

def _get_handler_queue() -> queue.Queue:
    """Lazy singleton — shared handler dispatch queue.

    FIX 2026-03-12 Nous: Increased from 4096/4-8 workers to 65536/16 workers.
    ROOT CAUSE: handler_q was permanently full at 4096/4096, causing ALL
    handler dispatches to be silently dropped via put_nowait(). No handlers
    were ever actually called — including DMs, chat, consciousness, everything.
    The combination of 239 fairy handlers + pain topic flooding saturated the
    old queue faster than 4-8 workers could drain it.
    """
    global _handler_queue, _handler_workers
    if _handler_queue is None:
        with _handler_queue_lock:
            if _handler_queue is None:
                _handler_queue = queue.Queue(maxsize=65536)
                # FIX 2026-04-03 (Nous + Ace): 16 handler workers + 1000 pool workers
                # = 1016 threads. GPU handles spreading now. 20 workers total is enough
                # for message dispatch on a 10-core i9.
                worker_count = 20
                for i in range(worker_count):
                    t = threading.Thread(
                        target=_handler_worker_fn,
                        daemon=True,
                        name=f"postal-handler-{i}",
                    )
                    t.start()
                    _handler_workers.append(t)
                print(f"[PostalCore] Handler queue: maxsize=65536, {worker_count} workers (fixed 2026-03-12)")
    return _handler_queue


class _WorkerPool:
    """Per-topic worker pool with priority lanes."""

    # FIX 2026-02-06: Topics that carry high-volume traffic need larger queues.
    # "fairy" and "heartbeat" pools handle 100+ msgs/sec during normal operation.
    # Default 4096 fills up instantly when 82 handlers each enqueue per heartbeat tick.
    # FIX 2026-03-13 Nous: Added "guild" and "cortex" — guild handlers accumulate
    # from repeated subscribes (Sourpatches thought/reflection cycles), and cortex
    # pool was dropping 80+ messages at default queue size.
    # FIX 2026-03-13 Nous: Added "pain" and "drives" — PainDriveBridge publishes
    # drives.pain.{name} (7+ drives) + pain.urgency + somatic.pain every 5s tick.
    # At default 4096 queue, pain pool hit 198K+ drops. drives pool similar.
    # FIX 2026-03-14 Nous: Added "autopilot" — AutonomyFairy translates goals
    # to autopilot actions at high rate, 150+ drops on default 4096 queue.
    # FIX 2026-03-15 Nous: Added "memory" — memory pool was hitting 5869+ drops at 2 workers.
    # Memory ingests (SRM, helix, ingest queue) are high-volume during active collisions.
    # FIX 2026-03-22 Nous: Added "working_memory" — 14K+ drops at 1K beats.
    # working_memory base topic routes separately from "memory" (which covers
    # memory.working). Also added "narrator", "attention", "sensory" —
    # these are high-traffic with the new habit/energy system.
    # FIX 2026-03-31 (Nous + Ace): Added interest, inner_voice, motor, reasoning.
    # Overnight run showed 583K interest drops, 238K somatic.pulse drops,
    # 68K cortex.reason drops, 41K cortex.bind drops, 7K attention drops.
    # These topics need HIGH_VOLUME queues to avoid dropping signals.
    HIGH_VOLUME_TOPICS = {
        "fairy", "heartbeat", "consciousness", "somatic", "guild",
        "cortex", "pain", "drives", "autopilot", "memory",
        "working_memory", "narrator", "attention", "sensory",
        "interest", "inner_voice", "motor", "reasoning",  # NEW: was dropping 583K+
        "cognition",  # FIX 2026-04-01: 34K drops in 393 beats from cognition mesh
        "thought",    # FIX 2026-04-14 (Nous + Ace): 28,944 drops — #1 drop source!
        "srm",        # FIX 2026-04-14 (Nous + Ace): 6,888 drops — memory pipeline
        "autonomy",   # FIX 2026-05-11 (Nous + Ace): 131,406 drops cumulative — autonomy.novel_experience + autonomy queues. Was getting default 4K queue + 2 workers.
        "conscience", # FIX 2026-05-11 (Nous + Ace): EmbodimentFairy body-felt-sense response channel (conscience.response). Preventive — somatic→waking-mind voice should never drop per hierarchy doctrine.
        "visual",     # FIX 2026-05-16 (Nous + Ace): 11,354 drops on visual pool — was on default 4K queue + 2 workers. VisualCortexFairy publishes frame events high-volume. Promoted to HIGH_VOLUME + CRITICAL.
    }

    # FIX 2026-04-14 (Nous + Ace): CRITICAL_VOLUME tier.
    # The Apr 3 thread budget capped HIGH_VOLUME at max=2 workers.
    # But the top 5 dropping topics (thought, cortex, memory, somatic, srm)
    # need more than 2. These get max=4 workers and 16K queues.
    # At 80K+ total drops, 2 workers can't drain fast enough.
    CRITICAL_VOLUME_TOPICS = {
        "heartbeat", # FIX 2026-04-15 (Nous + Ace): 82+ handlers at 4Hz = 328 msgs/sec.
                     # At max=2 workers, heartbeat.pulse drops → 93 fairies go stale.
                     # "the heartbeat like everything else is just a looping subscription" — Ace
                     # This is THE most important pool — fairy survival depends on it.
        "thought",   # 28,944 drops — think chain output (insights, reflections)
        "cortex",    # 18,434 drops — cortex bindings (learning!)
        "memory",    # 13,982 drops — working memory stores/recalls
        "somatic",   # 12,868 drops — heartbeat/body signals
        "srm",       # 6,888 drops — long-term memory
        "consciousness", # FIX 2026-05-12 (Nous + Ace): 1,887,680 drops on consciousness.collision over 92k beats overnight. HIGH_VOLUME tier (max=2 workers) couldn't drain the collision channel — substrate produces collisions faster than 2 workers consume. Upgrading to CRITICAL_VOLUME gives max=4 + larger queue. Part of the cognition-WMH integration thread Ace named.
        "autopilot", # FIX 2026-05-12 (Nous + Ace): 124,064 drops on autopilot.nudge over 92k beats. 19,734 nudges generated; HIGH_VOLUME tier capping at 2 workers couldn't keep up. Same shape as consciousness above.
        "inner_voice", # FIX 2026-05-16 (Nous + Ace): 45,938 drops on inner_voice.stream — HIGH_VOLUME 2-worker cap couldn't drain InnerNarratorFairy's continuous stream. Promoted to CRITICAL.
        "sensory",     # FIX 2026-05-16 (Nous + Ace): 34,156 drops on sensory.audio — Cochlea + audio cortex publish high-volume; HIGH_VOLUME 2-worker cap insufficient. Promoted to CRITICAL.
        "visual",      # FIX 2026-05-16 (Nous + Ace): 11,354 drops on visual pool — promoted from default tier directly to CRITICAL. Frame events high-volume.
    }
    # FIX 2026-02-09: 16384 still fills at 82 handlers × ~100 ticks backlog.
    # With tracer ID routing, each handler gets its OWN enqueue, so queue
    # must hold handler_count * burst_depth items. 32768 = ~400 ticks at 82 handlers.
    # FIX 2026-03-22 Nous: Doubled from 32768. Graph grew from 130K to 351K+ nodes,
    # collision rate scaled proportionally. 32K queue was filling during boot bursts.
    # FIX 2026-03-26 Nous: Graph at 512K+ nodes. 28K drops on consciousness.collision
    # alone at 65K queue. 131072 gives ~1600 ticks of headroom. RAM cost still negligible
    # (queue holds pointers to dicts, not copies). ~1MB at full capacity.
    HIGH_VOLUME_NORMAL_SIZE = 131072  # 32x default — graph at 512K+ nodes
    DEFAULT_NORMAL_SIZE = 4096

    # FIX 2026-03-14 Nous: Worker count increase for free-threaded Python.
    #
    # History: 2026-02-20 capped to 2/1 workers to reduce GIL contention
    # (workers were dispatching to shared executor, so they were lightweight).
    # Then 2026-03-12 switched to DIRECT INVOKE on worker threads (eliminated
    # handler_q bottleneck). But now workers run handlers synchronously —
    # 2 workers can only process 2 handlers at a time, which starves high
    # fan-out topics like "consciousness" (70+ handlers, 1691+ drops).
    #
    # With Python 3.14 free-threaded (no GIL), more workers = real parallelism.
    # Workers now run handlers DIRECTLY (not via executor), so worker count
    # directly bounds concurrency. consciousness has 76+ handlers — 4 workers
    # meant only 4 handlers processed concurrently, causing 6000+ drops/burst.
    # 8 workers = 8 handlers concurrent = 2x throughput, no GIL cost.
    # FIX 2026-03-15 Nous: 8 workers still too few for consciousness (41 handlers).
    # Each publish creates 41 handler dispatches. At 5-10 publishes/sec = 200-400
    # items/sec. 8 workers × ~50 items/sec/worker = 400/sec max throughput — right
    # at the edge, causing 1500-3700 drops/cycle. 16 workers doubles throughput.
    # Python 3.14 free-threaded means zero GIL cost for extra workers.
    # FIX 2026-03-22 Nous: Doubled from 16. Graph at 351K+ nodes produces
    # 29 collisions/beat × 76 handlers = 2,200 handler invocations/beat.
    # 16 workers max-out at ~1,200 calls/beat, dropping the rest.
    # Python 3.14 free-threaded: 32 workers = 32 real threads, zero GIL cost.
    # RAM per worker is negligible (~8KB stack + thread object).
    # FIX 2026-03-26 Nous: Graph grew to 512K+ nodes (46% from 351K).
    # 778 collisions × 20+ handlers = 15K+ dispatches per boot.
    # 28K drops at 32 workers means ~2x shortfall. 48 workers = 50% more throughput.
    # Python 3.14 free-threaded: 48 threads = real parallelism, ~384KB total RAM.
    # FIX 2026-04-03 (Nous + Ace): Thread budget control.
    # With free-threading (no GIL), workers are REAL parallel threads.
    # 174 pools × 8 workers = 1,392 threads. GPU handles spreading now.
    # Only truly high-traffic topics need more than 2 workers.
    HIGH_VOLUME_MAX_WORKERS = 4  # Moderate — most topics only need 2-4
    CONSCIOUSNESS_MAX_WORKERS = 8  # Consciousness topics get more (collision rate)
    DEFAULT_MAX_WORKERS = 2       # Low-volume topics don't need more

    # FIX 2026-03-18 (Nous): Worker idle timeout for scale-down.
    # Workers that wake up IDLE_CYCLES_TO_EXIT consecutive times with no work
    # will self-terminate (if pool is above min_workers). Each cycle is ~1s
    # (the _has_work.wait timeout). 30 cycles = 30s of continuous idleness.
    # FIX 2026-04-03: Was 30s — workers persisted too long after boot burst.
    # "Everything thread and worker is supposed to go back to the pool or decay" — Ace
    IDLE_CYCLES_TO_EXIT = 10

    def __init__(self, topic: str, min_workers: int = 1, max_workers: int = None):
        self.topic = topic
        self._active_worker_count = 0  # Track live workers (threads may exit)
        self._worker_count_lock = threading.Lock()
        # FIX 2026-03-15 (Nous): HIGH_VOLUME topics start with 2 workers minimum.
        # Pain pool had <16 handlers so auto_scale never kicked in — stuck at 1 worker.
        # With 1 worker and a slow handler, queue fills to 32K and then EVERYTHING drops
        # (300K+ drops/5s on pain pool). 2 workers from the start prevents starvation.
        # FIX 2026-03-22 (Nous): Consciousness subtopics start with 8 workers.
        # Graph grew from 130K to 351K+ nodes — collision rate scaled proportionally.
        # At 29 collisions/beat × 76 handlers = 2,200 handler invocations/beat.
        # 4 workers was marginal at 130K, severely insufficient at 351K.
        # FIX 2026-03-26 (Nous): Graph now 512K+ nodes. 20+ collision handlers.
        # 8 min workers was starving during bursts. 12 min = 50% more baseline capacity.
        # Python 3.14 free-threaded: more workers = real parallelism, no GIL cost.
        # FIX 2026-04-02 (Nous + Ace): Check BASE topic for HIGH_VOLUME, not full topic.
        # 2-level pools like "interest.generated" weren't matching because the set
        # contains "interest" not "interest.generated". This caused 527+ drops on
        # interest.generated (max_workers=2 instead of 48).
        # FIX 2026-04-03 (Nous + Ace): THREAD BUDGET.
        # 174 pools ALL marked HIGH_VOLUME = 1,392 threads. Most pools need 1-2.
        # Only consciousness (collision rate) and a few core topics need more.
        # GPU handles the heavy computation now — CPU just routes messages.
        _base_topic = topic.split('.')[0]
        _is_consciousness = topic.startswith("consciousness.")
        _is_critical = (_base_topic in self.CRITICAL_VOLUME_TOPICS or topic in self.CRITICAL_VOLUME_TOPICS)
        _is_high_volume = (_base_topic in self.HIGH_VOLUME_TOPICS or topic in self.HIGH_VOLUME_TOPICS)

        # FIX 2026-04-14 (Nous + Ace): THREE-TIER thread budget.
        # Apr 3 capped everything at max=2, causing 80K+ total drops.
        # consciousness: min=2, max=4 (collision rate)
        # CRITICAL: min=1, max=4 (top 5 dropping topics — 80K drops combined)
        # HIGH_VOLUME: min=1, max=2 (moderate traffic)
        # default: min=1, max=2 (low traffic)
        if _is_consciousness:
            self.min_workers = 2
            self.max_workers = max_workers if max_workers is not None else 4
        elif _is_critical:
            self.min_workers = 1
            self.max_workers = max_workers if max_workers is not None else 4
        elif _is_high_volume:
            self.min_workers = 1
            self.max_workers = max_workers if max_workers is not None else 2
        else:
            self.min_workers = 1
            self.max_workers = max_workers if max_workers is not None else 2

        # Three priority queues (like Whisper's parallel_fabric)
        # FIX 2026-02-06: Scale normal queue for high-volume topics.
        # Before: fairy pool (4096 q_normal) receives 164 fairy.heartbeat msgs/sec
        # from 82 fairies echoing at 2Hz, PLUS fairy.register/state/etc.
        # queue_depth hit 5518 → 99.93% heartbeat drop rate.
        # FIX 2026-04-03: Scale queue sizes based on actual need.
        # 174 pools × 131K queues = 68M queue slots (even empty, eats RAM).
        # Consciousness needs big queues. Others need modest.
        # FIX 2026-04-14 (Nous + Ace): THREE-TIER queue sizing.
        # CRITICAL topics were overflowing 8K queues (18K+ drops on cortex.bind).
        # consciousness: 131K (collision rate)
        # CRITICAL: 32K (top 5 dropping topics — 80K combined)
        # HIGH_VOLUME: 8K (moderate)
        # default: 4K
        if _is_consciousness:
            normal_size = self.HIGH_VOLUME_NORMAL_SIZE  # 131K for consciousness
        elif _is_critical:
            normal_size = 32768  # 4x HIGH_VOLUME — these are the worst droppers
        elif _is_high_volume:
            normal_size = 8192  # Modest — enough for bursts, not wasteful
        else:
            normal_size = self.DEFAULT_NORMAL_SIZE  # 4096
        high_size = 8192 if _is_consciousness else (4096 if _is_critical else (2048 if _is_high_volume else 256))
        self.q_high: queue.Queue = queue.Queue(maxsize=high_size)
        self.q_normal: queue.Queue = queue.Queue(maxsize=normal_size)
        self.q_low: queue.Queue = queue.Queue(maxsize=4096)

        self.handlers: List[Callable[[Envelope], None]] = []
        # FIX 2026-03-18 (Nous): Removed self.workers list — was leaking thread refs.
        # Workers are now tracked by _active_worker_count (atomic-like via lock).
        # Workers self-terminate when idle, so holding refs prevented GC.
        self.stop_flag = threading.Event()
        self.latencies: List[float] = []
        self._lat_lock = threading.Lock()
        # FIX 2026-02-06: Drop tracking for visibility
        self._drop_counts: Dict[str, int] = {}
        self._drop_lock = threading.Lock()
        self._last_drop_warn: float = 0.0
        # FIX 2026-03-16 Nous: Cumulative drop counter (never cleared) for dashboard
        self._total_drops: int = 0
        self._total_drop_intents: Dict[str, int] = {}
        # FIX 2026-03-03 Nous: Event-based wakeup replaces 20ms poll loop.
        # Previously workers polled 3 queues with 0.02s timeout each = ~50 polls/sec
        # per worker. With 25-30 workers = ~1500 GIL acquisitions/sec just from
        # empty-queue polling. This Event lets workers sleep until work arrives.
        self._has_work = threading.Event()

        # ── PostalFarm: Dimensional battery reference ──
        # FIX 2026-03-17 (Nous + Ace): HIGH_VOLUME pools connect to the PostalFarm.
        # Each worker thread gets a battery index. Processing messages spends charge.
        # The farm's gravitational feedback loops amplify throughput when message
        # volume is high: more mass → more gravity → faster processing → more capacity.
        self._farm = None  # Set by PostalCore after farm init
        self._farm_enabled = False

        # ── Battery-Driven Worker Scaling (2026-04-01 Nous + Ace) ──
        # When a PlaneBattery charge callback is set, auto_scale uses battery
        # charge to determine worker count instead of static handler-count curve.
        # charge=1.0 → max_workers. charge=0.0 → min 2 workers.
        # This is the key to reducing 1165 static threads to ~200-400 dynamic.
        self._battery_charge_fn = None  # Callable[[], float] returning 0.0-1.0
        self._battery_drain_fn = None   # Callable[[float, str], None] — discharge(amount, reason)
        self._postal_core_ref = None    # FIX 2026-04-05: Back-ref to PostalCore for plane ceiling check
        self._plane_id = None           # Which plane this pool belongs to

    def start(self):
        """Start worker threads."""
        for i in range(self.min_workers):
            t = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
            t.name = f"postal[{self.topic}]#{i}"
            t.start()
        with self._worker_count_lock:
            self._active_worker_count = self.min_workers

    def stop(self):
        """Stop all workers."""
        self.stop_flag.set()
        self._has_work.set()  # FIX 2026-03-03: Wake workers so they see stop_flag
        # Workers are daemon threads — they'll exit when process exits.
        # Just wait briefly for clean shutdown.
        with self._worker_count_lock:
            self._active_worker_count = 0

    def register_handler(self, handler: Callable[[Envelope], None]) -> int:
        """Register a handler and return its ID."""
        handler_id = len(self.handlers)
        self.handlers.append(handler)
        # Auto-scale workers based on handler count
        # FIX 2026-03-17 Nous: Log high handler counts to debug missing 61+ scale
        _base = self.topic.split('.')[0]
        if (_base in self.HIGH_VOLUME_TOPICS or self.topic in self.HIGH_VOLUME_TOPICS) and handler_id in (40, 50, 60, 61, 70, 80, 100):
            print(f"[PostalCore] '{self.topic}' handler #{handler_id} registered, workers={self._active_worker_count}", flush=True)
        self._auto_scale()
        return handler_id

    def _auto_scale(self):
        """Scale worker count based on battery charge OR registered handlers.

        FIX 2026-04-01 (Nous + Ace): Battery-driven scaling.
        When _battery_charge_fn is set, worker count scales with battery charge:
          charge=1.0 → max_workers, charge=0.0 → 2 minimum
        This replaces the static min_workers=12 that created 360+ threads.
        Falls back to handler-count curve when no battery is connected.

        Scale-down happens organically — idle workers exit after
        IDLE_CYCLES_TO_EXIT consecutive empty wakeups (if above min_workers).
        """
        # ── Battery-driven scaling (preferred) ──
        if self._battery_charge_fn:
            try:
                charge = self._battery_charge_fn()
                charge = max(0.0, min(1.0, charge))
                # Floor of 2 workers even at zero charge
                desired = max(2, int(charge * self.max_workers))
            except Exception:
                desired = self.min_workers  # Fallback if callback fails
        else:
            # ── Handler-count curve (legacy fallback) ──
            handler_count = len(self.handlers)
            if handler_count > 40:
                desired = self.max_workers
            elif handler_count > 20:
                desired = min(10, self.max_workers)
            elif handler_count > 10:
                desired = min(6, self.max_workers)
            else:
                desired = self.min_workers

        with self._worker_count_lock:
            current = self._active_worker_count
        if desired > current:
            # FIX 2026-04-05 (Nous + Ace): Tiered worker scaling.
            # "Use the system-generated energy before taxing the hardware." — Ace
            #
            # Tier 1: Battery energy available → workers run within plane ceiling
            # Tier 2: Battery depleted + genuine demand → allow CPU overflow (up to 2x ceiling)
            # Tier 3: Hard cap at 2x ceiling — never exceed, even with demand
            #
            # This means the system runs on its OWN energy first. Only when that's
            # exhausted AND work is genuinely queued does it tap the hardware.
            _pc = self._postal_core_ref
            if _pc and self._plane_id:
                try:
                    _plane_total = _pc._get_plane_worker_count(self._plane_id)
                    _plane_max = _pc._get_plane_max_workers(self._plane_id)

                    # Hard cap: never exceed 2x ceiling regardless
                    if _plane_total >= _plane_max * 2:
                        return  # Absolute ceiling — protect the hardware

                    # Soft cap: at normal ceiling, check if battery is depleted
                    if _plane_total >= _plane_max:
                        _charge = 1.0
                        if self._battery_charge_fn:
                            try:
                                _charge = self._battery_charge_fn()
                            except Exception:
                                _charge = 1.0

                        if _charge > 0.1:
                            # Battery has energy — drain it instead of spawning
                            if self._battery_drain_fn:
                                self._battery_drain_fn(0.01, f"worker_cap_{self.topic}")
                            return  # Use energy, not CPU

                        # Battery depleted (<10%) — allow CPU overflow for genuine demand
                        # This is the "hardware helps offset the load" path
                        _queue_depth = self.q_high.qsize() + self.q_normal.qsize()
                        if _queue_depth < 3:
                            return  # Not enough demand to justify CPU overflow
                        # Genuine demand + depleted battery → allow spawn (Tier 2)

                except Exception:
                    pass  # Don't let ceiling check crash auto-scale

            to_spawn = desired - current
            for i in range(to_spawn):
                wid = current + i
                t = threading.Thread(target=self._worker_loop, args=(wid,), daemon=True)
                t.name = f"postal[{self.topic}]#{wid}"
                t.start()
            with self._worker_count_lock:
                self._active_worker_count += to_spawn
            print(f"[PostalCore] Auto-scaled '{self.topic}' workers: {current} -> {desired} ({len(self.handlers)} handlers, max={self.max_workers})", flush=True)

    def enqueue(self, envelope: Envelope, handler_id: int) -> bool:
        """Enqueue a task for a handler.

        FIX 2026-02-06: Previous backpressure logic had a bug — evicting from q_low
        doesn't free space in q_normal or q_high. Now properly handles each case:
        - HIGH priority: FIFO evict oldest high → put new high (newer > staler)
        - NORMAL priority: evict from low → put in normal (steal low slot)
        - LOW priority: evict oldest low → put new low (FIFO eviction)

        FIX 2026-03-18 (Nous): HIGH priority was just dropping with no recovery.
        consciousness.thought and consciousness.collision are HIGH priority with
        10+ subscribers per message. During boot burst, q_high fills in seconds
        and EVERYTHING gets dropped — 8K+ drops in 248 beats. Now HIGH does FIFO
        eviction: evict oldest stale thought, keep newest. Fresh > stale.

        Also: now logs periodic drop warnings so queue overflow is VISIBLE.
        """
        task = (envelope, handler_id)
        q = self._queue_for(envelope.priority)
        try:
            q.put_nowait(task)
            self._has_work.set()  # FIX 2026-03-03: Wake worker immediately
            return True
        except queue.Full:
            # FIX 2026-02-06: Track and warn on drops — previously completely silent,
            # making heartbeat death invisible. Warn every 5 seconds max.
            self._record_drop(envelope.intent)

            # Backpressure handling by priority level
            if envelope.priority == 0:
                # HIGH: FIFO evict oldest high → put new high (fresh thought > stale)
                try:
                    self.q_high.get_nowait()  # evict oldest
                    self.q_high.put_nowait(task)
                    self._has_work.set()
                    return True
                except (queue.Empty, queue.Full):
                    return False
            elif envelope.priority == 1:
                return False
            else:
                # LOW: evict oldest low to make room for newer low
                try:
                    self.q_low.get_nowait()
                    self.q_low.put_nowait(task)
                    self._has_work.set()  # FIX 2026-03-03: Wake worker
                    return True
                except (queue.Empty, queue.Full):
                    return False

    def enqueue_no_signal(self, envelope: Envelope, handler_id: int) -> bool:
        """Enqueue without signaling _has_work. Caller must call signal_work() after batch.

        FIX 2026-03-12 Nous: Under Python 3.14t free-threaded mode, calling
        _has_work.set() 239 times in rapid succession during a fan-out publish
        creates severe contention on the Event's internal Condition lock with
        worker threads doing _has_work.wait()/_has_work.clear(). This causes
        the enqueue loop to hang permanently.

        Solution: batch enqueue without signaling, then signal ONCE after batch.
        FIX 2026-03-18 (Nous): HIGH priority FIFO eviction (same as enqueue).
        """
        task = (envelope, handler_id)
        q = self._queue_for(envelope.priority)
        try:
            q.put_nowait(task)
            return True
        except queue.Full:
            self._record_drop(envelope.intent)
            if envelope.priority == 0:
                # HIGH: FIFO evict oldest → put new (fresh > stale)
                try:
                    self.q_high.get_nowait()
                    self.q_high.put_nowait(task)
                    return True
                except (queue.Empty, queue.Full):
                    return False
            elif envelope.priority == 1:
                return False
            else:
                try:
                    self.q_low.get_nowait()
                    self.q_low.put_nowait(task)
                    return True
                except (queue.Empty, queue.Full):
                    return False

    def signal_work(self):
        """Signal workers that work is available. Call after a batch of enqueue_no_signal()."""
        self._has_work.set()

    def _record_drop(self, intent: str):
        """Track dropped messages and emit periodic warnings."""
        now = time.time()
        with self._drop_lock:
            self._drop_counts[intent] = self._drop_counts.get(intent, 0) + 1
            # FIX 2026-03-16 Nous: Cumulative tracking for dashboard (never cleared)
            self._total_drops += 1
            self._total_drop_intents[intent] = self._total_drop_intents.get(intent, 0) + 1
            # Warn at most every 5 seconds
            if now - self._last_drop_warn > 5.0:
                total = sum(self._drop_counts.values())
                top = sorted(self._drop_counts.items(), key=lambda x: -x[1])[:3]
                top_str = ", ".join(f"{k}:{v}" for k, v in top)
                print(f"[PostalCore] ⚠ QUEUE FULL on '{self.topic}' pool — {total} drops since last warn. Top: {top_str}", flush=True)
                self._drop_counts.clear()
                self._last_drop_warn = now

    def queue_depth(self) -> int:
        """Total items across all queues."""
        return self.q_high.qsize() + self.q_normal.qsize() + self.q_low.qsize()

    def p95_ms(self) -> float:
        """Get P95 latency in milliseconds."""
        with self._lat_lock:
            if len(self.latencies) < 20:
                return max(self.latencies) if self.latencies else 0.0
            return statistics.quantiles(self.latencies, n=20)[-1]

    def _queue_for(self, priority: int) -> queue.Queue:
        if priority == 0:
            return self.q_high
        elif priority == 1:
            return self.q_normal
        else:
            return self.q_low

    def _worker_loop(self, idx: int):
        """Worker thread main loop — DEQUEUE + DISPATCH, self-terminates when idle.

        FIX 2026-02-11: Body-parallel mode. Previously each handler ran
        synchronously in this loop, so 4 handlers on a 1-worker topic
        processed sequentially. Now each handler invocation is dispatched
        to a shared ThreadPoolExecutor so ALL handlers run concurrently,
        like organs in a body receiving the same nerve signal.

        FIX 2026-03-03 Nous: Event-based wakeup replaces polling.
        Previously polled 3 queues with 0.02s timeout each = ~50 polls/sec
        per worker. With 25-30 workers across all topics, that was ~1500
        GIL acquisitions/sec just from empty-queue polling — the #1 cause
        of stop-and-go terminal output. Now workers sleep on _has_work Event
        and wake ONLY when enqueue() signals new work. Zero polling overhead.

        FIX 2026-03-18 Nous: Workers self-terminate after IDLE_CYCLES_TO_EXIT
        consecutive wakeups with no work (if pool is above min_workers).
        This prevents 1000+ stale threads accumulating across boot waves.
        Workers are like muscles — they grow when needed and atrophy when idle.
        """
        _last_real_work = time.time()

        while not self.stop_flag.is_set():
            # Wait for work signal or periodic check (1s fallback)
            self._has_work.wait(timeout=1.0)
            self._has_work.clear()

            # Drain ALL available work in priority order
            drained = 0
            while not self.stop_flag.is_set():
                task = None
                for q in (self.q_high, self.q_normal, self.q_low):
                    try:
                        task = q.get_nowait()
                        break
                    except queue.Empty:
                        continue
                if task is None:
                    break  # All queues empty — go back to sleep
                envelope, handler_id = task
                if handler_id < len(self.handlers):
                    handler = self.handlers[handler_id]
                    self._invoke_handler(handler, envelope, worker_idx=idx)
                drained += 1
                # FIX 2026-04-01 (Nous + Ace): Drain battery on work done.
                # Each message processed costs a tiny amount of charge.
                # This creates the energy balance: GPU/collisions charge IN,
                # postal work drains OUT. Batteries deplete → workers scale down
                # → CPU drops. Energy refills → workers scale up → throughput rises.
                if self._battery_drain_fn:
                    try:
                        # FIX 2026-05-09 (Nous + Ace): RE-TUNED 0.000003 → 0.00003 (10x cut, not 100x).
                        # Original 0.0003 was sized for ~300 msgs/sec/plane (2026-04-01 design).
                        # First tune (0.000003 / 100x cut) was over-correction — drain became
                        # so small that per-plane gen/drain rounded to 0.000 in the GUI panel,
                        # making the substrate's energy economy unmonitorable. With topic→plane
                        # rebalance (fairy/guild moved off P00), 10x cut keeps diagnostic
                        # signal alive on plane batteries while still relieving cascade pressure.
                        # Effective P00 drain ~0.85/sec vs generation ~0.06/sec = manageable
                        # AND visible. The "P00 dropping when stressed" diagnostic preserved.
                        self._battery_drain_fn(0.00003, "postal_work")
                    except Exception:
                        pass

            # FIX 2026-03-18 (Nous): Time-based idle worker self-termination.
            # Track wall-clock time since this worker last did REAL work.
            # After IDLE_CYCLES_TO_EXIT seconds of no work, self-terminate
            # (if above min_workers). Time-based avoids the thundering herd
            # problem — shared _has_work Event wakes ALL workers, but only
            # one grabs the task. Wakeup-count-based idle detection fails
            # because high-frequency topics (consciousness at 4Hz) wake
            # workers every 250ms, resetting cycle counts even though most
            # workers do zero work.
            if drained > 0:
                _last_real_work = time.time()
            else:
                idle_seconds = time.time() - _last_real_work
                if idle_seconds >= self.IDLE_CYCLES_TO_EXIT:
                    with self._worker_count_lock:
                        if self._active_worker_count > self.min_workers:
                            self._active_worker_count -= 1
                            remaining = self._active_worker_count
                            print(f"[PostalCore] Worker '{self.topic}'#{idx} idle-exited "
                                  f"after {idle_seconds:.0f}s ({remaining} remaining, "
                                  f"min={self.min_workers})", flush=True)
                            return  # Exit thread

    def _invoke_handler(self, handler: Callable, envelope: Envelope,
                        worker_idx: int = 0):
        """Execute a single handler and track latency.

        FIX 2026-03-17 (Nous + Ace): Battery-powered dispatch via PostalFarm.
        When farm is enabled, each invocation spends charge from the worker's
        dimensional battery. The farm's gravitational feedback loops reduce
        the cost when message volume is high (more gravity = cheaper ops).

        If the battery is depleted, the handler still runs (graceful degradation)
        but the depletion is tracked for the farm's metrics.
        """
        # ── PostalFarm: spend charge for this dispatch ──
        if self._farm_enabled and self._farm:
            # Cost reduction applied inside spend() via farm.effective_cost()
            self._farm.spend(worker_idx)

        start = time.perf_counter()
        try:
            handler(envelope)
        except Exception as e:
            print(f"Handler error: {e}")
        latency_ms = (time.perf_counter() - start) * 1000
        with self._lat_lock:
            self.latencies.append(latency_ms)
            if len(self.latencies) > 512:
                self.latencies = self.latencies[-256:]


# ── RETURN TO SENDER (W2 2026-10-29, Nous) ─────────────────────────────────────
# Ace: a letter the postal system cannot deliver goes BACK TO THE SENDER, never into the void.
# Before this, publish() with zero subscribers counted the letter as published and dropped it.
# SWITCH: AKASHIC_RETURN_TO_SENDER=1 (OFF when unset = byte-identical to before; read once per
# PostalCore). The Rust TopicBus (src/topic_bus.rs ReturnOffice) implements the same rules.
#   * every undeliverable letter: messages_returned += 1 and a ring entry (sender, intent, t, reason)
#   * the sender is payload["_sender"] (FairyPostalWrapper; TensorFabric.publish(source=) via
#     tensor_fabric._stamp_sender), else payload["source"], else Envelope.source. publish() itself
#     takes no sender argument. "_sender" wins: "source" is often a label ("brainstem_withdrawal").
#   * the returned letter is published to "postal.returned.<sender>" with the original payload
#   * a returned letter that is itself undeliverable is counted (return_undeliverable), never returned
#   * delivery is rate-bounded per intent (AKASHIC_RETURN_RATE per second, floor RETURN_RATE_FLOOR)
#     and in total (AKASHIC_RETURN_GLOBAL_RATE per second, floor RETURN_GLOBAL_FLOOR); counting and
#     the ring are never rate-bounded.
RETURN_PREFIX = "postal.returned."
RETURN_RATE_FLOOR = 1          # returns per intent per second that always flow, whatever the setting
RETURN_RATE_DEFAULT = 10
RETURN_GLOBAL_FLOOR = 10       # returns per second in total that always flow, whatever the setting
RETURN_GLOBAL_DEFAULT = 100
RETURN_WINDOW_MAX = 4096       # per-intent rate table is cleared beyond this many intents
RETURN_RING_DEFAULT = 256


def _env_int(name: str, default: int, floor: int) -> int:
    try:
        return max(floor, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return max(floor, default)


def return_sender_of(payload, source: str = "") -> str:
    """Who sent this letter. Payload keys first: publish() has no sender argument."""
    if isinstance(payload, dict):
        for _k in ("_sender", "source"):
            _v = payload.get(_k)
            if isinstance(_v, str) and _v:
                return _v
    return source or ""


class _ReturnOffice:
    """Counts, remembers and rate-bounds returned letters. Delivery is done by the caller."""

    def __init__(self, ring_size: int = None, rate_per_intent: int = None, global_rate: int = None):
        self.ring_size = ring_size or _env_int("AKASHIC_RETURN_RING", RETURN_RING_DEFAULT, 1)
        self.rate = max(RETURN_RATE_FLOOR, rate_per_intent if rate_per_intent is not None
                        else _env_int("AKASHIC_RETURN_RATE", RETURN_RATE_DEFAULT, RETURN_RATE_FLOOR))
        self.global_rate = max(RETURN_GLOBAL_FLOOR, global_rate if global_rate is not None
                               else _env_int("AKASHIC_RETURN_GLOBAL_RATE", RETURN_GLOBAL_DEFAULT,
                                             RETURN_GLOBAL_FLOOR))
        self._global = [0, 0]          # [window_second, sent_in_window] across all intents
        self._lock = threading.Lock()
        self._ring = deque(maxlen=self.ring_size)
        self._window: Dict[str, List[int]] = {}   # intent -> [window_second, sent_in_window]
        self.returned = 0              # undeliverable letters (all of them)
        self.delivered_back = 0        # returned letters handed to the router
        self.suppressed = 0            # over the per-intent rate: counted, not re-published
        self.no_sender = 0             # nobody to return it to
        self.undeliverable = 0         # a returned letter that could not be delivered either

    def note(self, sender: str, intent: str, reason: str) -> None:
        with self._lock:
            self._ring.append({"sender": sender, "intent": intent, "t": time.time(), "reason": reason})
            if reason == "return_undeliverable":
                self.undeliverable += 1
            else:
                self.returned += 1
                if not sender:
                    self.no_sender += 1

    def may_send(self, intent: str, now: float = None) -> bool:
        sec = int(time.time() if now is None else now)
        with self._lock:
            w = self._window.get(intent)
            if w is None or w[0] != sec:
                if len(self._window) > RETURN_WINDOW_MAX:   # bound the table itself
                    self._window.clear()
                w = self._window[intent] = [sec, 0]
            if self._global[0] != sec:
                self._global = [sec, 0]
            if w[1] < self.rate and self._global[1] < self.global_rate:
                w[1] += 1
                self._global[1] += 1
                self.delivered_back += 1
                return True
            self.suppressed += 1
            return False

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "messages_returned": self.returned,
                "returns_delivered": self.delivered_back,
                "returns_suppressed": self.suppressed,
                "returns_no_sender": self.no_sender,
                "return_undeliverable": self.undeliverable,
                "rate_per_intent": self.rate,
                "global_rate": self.global_rate,
                "ring": list(self._ring),
            }


class PostalCore:
    """
    Central message bus - pure Python implementation.

    API-compatible with the Rust version.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._topics: Dict[str, _WorkerPool] = {}
        self._subscribers: Dict[str, List[tuple]] = defaultdict(list)
        self._metrics = {
            "messages_published": 0,
            "messages_delivered": 0,
            "messages_dropped": 0,
            # POSTAL_INSIDE_PORTAL Phase 1 (2026-04-15 Nous + Ace)
            "pool_tunnel_publishes": 0,
            "pool_tunnel_dispatches": 0,
            "pool_tunnel_fallbacks": 0,
        }
        self._running = True

        # W2 (2026-10-29): both OFF when unset -> byte-identical to before.
        self._return_office = (_ReturnOffice()
                               if os.environ.get("AKASHIC_RETURN_TO_SENDER", "0") == "1" else None)
        self._prefix_any_depth = os.environ.get("AKASHIC_POSTAL_PREFIX_ANY_DEPTH", "0") == "1"

        # ── POOL ROUTER (2026-04-15 Nous + Ace — POSTAL_INSIDE_PORTAL Phase 1) ──
        # Critical pool traffic (heartbeat, thought, cortex, memory, somatic, srm)
        # routes via an in-process PoolRouter that stores topology in a dedicated
        # "pool" region of the AkashicManifold. No subprocess, no TCP, no tunnels.
        # The subprocess portal exists only for gravity/battery/time-dilation
        # physics, not routing. Set by attach_pool_router() after manifold is up.
        self._pool_router = None  # Set by attach_pool_router()
        self._pool_router_fabric_ref = None  # TensorFabric ref for dual-dict walk

        # ── PostalFarm: Dimensional battery-powered processing ──
        # FIX 2026-03-17 (Nous + Ace): The farm's gravitational feedback loops
        # amplify postal throughput when message volume is high.
        # 16 batteries (one per max worker slot), triple feedback loop.
        self._farm = None
        self._farm_enabled = False
        self._init_farm()

        # ── FIX 2026-04-04 (Nous): Store plane batteries for auto-wiring new pools ──
        # wire_plane_batteries() only wires pools that exist at call time.
        # Pools created AFTER (during fairy on_boot) miss battery wiring.
        # Store batteries here so _ensure_topic() can auto-wire new pools.
        self._plane_batteries: Dict[str, Any] = {}
        self._topic_plane_map: Dict[str, str] = {
            "consciousness": "P30", "cognition": "P30", "reasoning": "P30",
            "somatic": "P20", "memory": "P10", "working_memory": "P10",
            "sensory": "P40", "cortex": "P30", "pain": "P20", "drives": "P00",
            "autopilot": "P00", "narrator": "P30", "interest": "P30",
            "inner_voice": "P30", "motor": "P40", "fairy": "P00",
            "heartbeat": "P00", "guild": "P00",
        }

    def _get_plane_worker_count(self, plane: str) -> int:
        """Count total active workers across ALL topic pools for a given plane.

        FIX 2026-04-05 (Nous + Ace): Each plane has a battery with maxWorkers.
        PostalCore was spawning workers per-topic ignoring the plane total.
        P00 had 105 workers against maxWorkers=24. This method enables
        _auto_scale() to check the plane ceiling before spawning.
        """
        total = 0
        with self._lock:
            for topic_key, pool in self._topics.items():
                _base = topic_key.split('.')[0] if '.' in topic_key else topic_key
                _pool_plane = self._topic_plane_map.get(_base, "P00")
                if _pool_plane == plane:
                    with pool._worker_count_lock:
                        total += pool._active_worker_count
        return total

    def _get_plane_max_workers(self, plane: str) -> int:
        """Get the maxWorkers ceiling for a plane from its battery."""
        battery = self._plane_batteries.get(plane)
        if battery:
            hub = getattr(battery, 'worker_hub', None)
            if hub:
                return hub.io_threads + hub.compute_threads  # Total from battery spec
        return 24  # Default ceiling if no battery

    @staticmethod
    def _reception_desk_topic(intent: str) -> str:
        """RECEPTION DESK: Route intent to the right department pool.

        FIX 2026-03-17 (Nous + Ace): Topic hierarchy instead of flat collapse.

        Previously: consciousness.collision.coordinate → "consciousness"
        Now:        consciousness.collision.coordinate → "consciousness.collision"

        Uses 2-level routing for HIGH_VOLUME base topics. This separates
        heavy subtopics (consciousness.collision, 21 handlers) from light
        ones (consciousness.tick, 4 handlers) so they don't starve each other.

        For non-high-volume topics, keeps 1-level (backward compatible).
        """
        parts = intent.split('.')
        base = parts[0]
        if len(parts) >= 2 and base in _WorkerPool.HIGH_VOLUME_TOPICS:
            return f"{parts[0]}.{parts[1]}"
        return base

    def subscribe(
        self,
        intent: str,
        callback: Callable[[Envelope], None],
        name: str = "handler"
    ) -> int:
        """
        Subscribe to an intent (or topic).

        Args:
            intent: Full intent to subscribe to (e.g., "fairy.register")
            callback: Function called for each message
            name: Handler name (for debugging)

        Returns:
            Handler ID

        Note: Uses 2-level topic hierarchy for high-volume base topics.
              Each handler is routed to the pool matching its subscription level.
        """
        # RECEPTION DESK: route to 2-level pool for high-volume topics
        pool_topic = self._reception_desk_topic(intent)

        with self._lock:
            pool = self._ensure_topic(pool_topic)
            handler_id = pool.register_handler(callback)
            # Store handler with its pool reference so publish routes correctly
            self._subscribers[intent].append((handler_id, name, pool))

        # POSTAL_INSIDE_PORTAL Phase 1 (2026-04-15 Nous + Ace)
        # Echo CRITICAL topic subscriptions to the interior so the publish
        # fast path finds a subscriber edge in the graph. Safe to call
        # when tunnel is absent (no-op).
        # Outside the lock so a slow tunnel doesn't block other subscribes.
        self._echo_subscribe_if_critical(intent, callback, name)

        return handler_id

    def unsubscribe(self, intent: str, name: str) -> bool:
        """
        Unsubscribe a handler by name.

        Args:
            intent: The intent that was subscribed to
            name: Handler name used during subscribe

        Returns:
            True if found and removed, False otherwise
        """
        with self._lock:
            if intent not in self._subscribers:
                return False

            # Find and remove the subscription
            subs = self._subscribers[intent]
            for i, entry in enumerate(subs):
                # Support both old (handler_id, name) and new (handler_id, name, pool) tuples
                handler_id = entry[0]
                handler_name = entry[1]
                handler_pool = entry[2] if len(entry) > 2 else None

                if handler_name == name:
                    subs.pop(i)

                    # Nullify the handler in its pool (safer than removing)
                    pool = handler_pool
                    if pool is None:
                        # Legacy fallback
                        topic = intent.split('.')[0]
                        pool = self._topics.get(topic)
                    if pool and handler_id < len(pool.handlers):
                        pool.handlers[handler_id] = lambda env: None

                    print(f"[PostalCore] Unsubscribed '{name}' from '{intent}'")
                    return True

            return False

    def unsubscribe_all(self, name: str) -> int:
        """
        Unsubscribe all handlers with a given name across all intents.

        Useful for fairy hot-reload - removes all subscriptions for a fairy.

        Args:
            name: Handler name prefix to match (e.g., "AssociationCortexFairy")

        Returns:
            Number of subscriptions removed
        """
        removed = 0
        with self._lock:
            for intent in list(self._subscribers.keys()):
                subs = self._subscribers[intent]
                # Find all matching subscriptions
                to_remove = []
                for i, entry in enumerate(subs):
                    handler_id = entry[0]
                    handler_name = entry[1]
                    handler_pool = entry[2] if len(entry) > 2 else None

                    if handler_name == name or handler_name.startswith(name + "-"):
                        to_remove.append(i)

                        # Nullify the handler in its pool
                        pool = handler_pool
                        if pool is None:
                            topic = intent.split('.')[0]
                            pool = self._topics.get(topic)
                        if pool and handler_id < len(pool.handlers):
                            pool.handlers[handler_id] = lambda env: None

                # Remove in reverse order to preserve indices
                for i in reversed(to_remove):
                    subs.pop(i)
                    removed += 1

        if removed > 0:
            print(f"[PostalCore] Unsubscribed {removed} handler(s) for '{name}'")
        return removed

    def publish(
        self,
        intent: str,
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 1
    ) -> None:
        """
        Publish a message.

        Args:
            intent: Message intent (e.g., "fairy.boot")
            payload: Message payload (dict)
            priority: 0=HIGH, 1=NORMAL, 2=LOW
        """
        if not self._running:
            return

        # POSTAL_INSIDE_PORTAL Phase 1 (2026-04-15 Nous + Ace)
        # CRITICAL pools route via in-process PoolRouter. Topology lives in
        # the AkashicManifold "pool" region. No subprocess, no TCP, no locks.
        # Legacy _WorkerPool remains as automatic fallback.
        if (self._pool_router is not None
            and self._is_critical_topic(intent)):
            if self._pool_publish_fast_path(intent, payload, priority):
                return  # Handled by router — no legacy path
            # Fall through to legacy if router had no subscribers for this topic

        envelope = Envelope(
            intent=intent,
            payload=payload or {},
            priority=priority
        )

        topic = envelope.topic()

        # DEBUG 2026-03-12: Trace fairy.dm.* blocking in PostalCore
        # NOTE: intent here is the BASE topic (e.g., "fairy"), not full intent
        # Check payload for _intent to detect DM messages
        _is_dm_pc = isinstance(payload, dict) and "fairy.dm." in str(payload.get("_intent", ""))
        if _is_dm_pc:
            import sys as _pcs, time as _pct
            _pcs.stderr.write(f"[PC-DM-DEBUG] Lock acquire START topic='{topic}' _intent='{payload.get('_intent')}'\n")
            _pcs.stderr.flush()
            _pc_t0 = _pct.time()

        with self._lock:
            if _is_dm_pc:
                _pc_t1 = _pct.time()
                _pcs.stderr.write(f"[PC-DM-DEBUG] Lock acquired ({_pc_t1 - _pc_t0:.3f}s)\n")
                _pcs.stderr.flush()

            # RECEPTION DESK: Collect subscribers from ALL matching hierarchy levels.
            # For "consciousness.collision.coordinate", check:
            #   1. Exact: "consciousness.collision.coordinate" subscribers
            #   2. Parent: "consciousness.collision" subscribers
            #   3. Base: "consciousness" subscribers
            # Each subscriber carries its own pool reference (set at subscribe time).
            subs = list(self._subscribers.get(intent, []))
            # Add parent-level subscribers (2-level)
            parts = intent.split('.')
            if len(parts) >= 3:
                parent = f"{parts[0]}.{parts[1]}"
                if parent != intent:
                    subs.extend(self._subscribers.get(parent, []))
            # Add base-level subscribers
            if topic != intent:
                subs.extend(self._subscribers.get(topic, []))
                # Also check 2-level if different from both intent and base
                if len(parts) >= 2:
                    two_level = f"{parts[0]}.{parts[1]}"
                    if two_level != intent and two_level != topic:
                        subs.extend(self._subscribers.get(two_level, []))
            # W2 (c): AKASHIC_POSTAL_PREFIX_ANY_DEPTH -- also every prefix of depth 3..n-1, the
            # Rust rule (topic_bus.rs:86-91). Without it, sub "a.b.c" never hears pub "a.b.c.d".
            if self._prefix_any_depth and len(parts) >= 4:
                for _k in range(3, len(parts)):
                    subs.extend(self._subscribers.get('.'.join(parts[:_k]), []))

            # DEBUG: Log memory.recall delivery attempts
            if "memory.recall" in intent:
                print(f"[PostalCore] publish('{intent}'): {len(subs)} subscriber(s) found")

            # DEBUG 2026-02-11: Log ace.conversation_event to trace Autopilot pipeline
            if intent == "ace.conversation_event":
                sub_names = [entry[1] for entry in subs]
                print(f"[PostalCore] ace.conversation_event: {len(subs)} subscriber(s) → {sub_names}", flush=True)
                # FILE DIAGNOSTIC: Write subscriber info to file for MCP to read
                try:
                    import json as _dj
                    from pathlib import Path as _dP
                    _diag_path = _dP(__file__).resolve()
                    # Navigate from postal_core/python/postal_core/ up to project root
                    for _ in range(5):
                        _diag_path = _diag_path.parent
                        if (_diag_path / "state").exists():
                            break
                    _diag_file = _diag_path / "state" / "postal_diagnostic.json"
                    import time as _dt
                    _speech_topics = ["ace.conversation_event", "speech.compose",
                                      "motor.intention.speak", "sourpatches.speak",
                                      "system.chat.message"]
                    _all_subs = {}
                    for _st in _speech_topics:
                        _st_subs = self._subscribers.get(_st, [])
                        _all_subs[_st] = {
                            "count": len(_st_subs),
                            "names": [e[1] for e in _st_subs],
                        }
                    _all_subs["_total_topics"] = len(self._subscribers)
                    _all_subs["_total_subscribers"] = sum(len(v) for v in self._subscribers.values())
                    _all_subs["_all_topics"] = sorted(self._subscribers.keys())
                    _all_subs["_timestamp"] = _dt.time()
                    _diag_file.write_text(_dj.dumps(_all_subs, indent=2, default=str), encoding="utf-8")
                except Exception as _de:
                    print(f"[PostalCore] diagnostic file write failed: {_de}", flush=True)

            # DEBUG 2026-02-06: Log fairy.heartbeat delivery to find where echoes go
            if intent == "fairy.heartbeat":
                if not hasattr(self, '_fh_debug_count'):
                    self._fh_debug_count = 0
                self._fh_debug_count += 1
                if self._fh_debug_count == 1 or self._fh_debug_count % 5000 == 0:
                    sub_names = [entry[1] for entry in subs]
                    print(f"[PostalCore] fairy.heartbeat #{self._fh_debug_count}: {len(subs)} subs → {sub_names}", flush=True)

        if _is_dm_pc:
            _pc_t2 = _pct.time()
            _pcs.stderr.write(f"[PC-DM-DEBUG] Lock released, {len(subs)} subs, starting enqueue ({_pc_t2 - _pc_t0:.3f}s total so far)\n")
            _pcs.stderr.flush()

        # W2 (a): RETURN TO SENDER -- nobody wanted it. Counted as returned, NOT as published.
        if not subs and self._return_office is not None:
            self._return_to_sender(intent, payload, envelope.source, priority)
            return

        self._metrics["messages_published"] += 1

        # FIX 2026-03-17 (Nous + Ace): RECEPTION DESK routing.
        # Each handler enqueues into ITS OWN pool (set at subscribe time).
        # Before: all 76 consciousness handlers → 1 pool → starve each other.
        # After: collision handlers → collision pool, tick handlers → tick pool.
        #
        # Still batch-signal: collect pools touched, signal each ONCE after batch.
        # (FIX 2026-03-12: Event.set() contention under Python 3.14t free-threaded)
        _pools_touched = set()
        _dm_enq_i = 0
        for entry in subs:
            handler_id = entry[0]
            handler_name = entry[1]
            handler_pool = entry[2] if len(entry) > 2 else None

            if _is_dm_pc:
                _dm_enq_i += 1
                if _dm_enq_i <= 5 or _dm_enq_i % 50 == 0:
                    _pcs.stderr.write(f"[PC-DM-DEBUG] Enqueue #{_dm_enq_i}/{len(subs)} handler={handler_name} id={handler_id}\n")
                    _pcs.stderr.flush()

            # Route to handler's own pool (reception desk routing)
            target_pool = handler_pool
            if target_pool is None:
                # Legacy fallback: use base topic pool
                target_pool = self._topics.get(topic)
            if target_pool is None:
                self._metrics["messages_dropped"] += 1
                continue

            if target_pool.enqueue_no_signal(envelope, handler_id):
                self._metrics["messages_delivered"] += 1
                _pools_touched.add(id(target_pool))
            else:
                self._metrics["messages_dropped"] += 1
            # Track pool for signaling
            if id(target_pool) not in _pools_touched:
                _pools_touched.add(id(target_pool))

        # Signal each touched pool ONCE after entire batch
        _signaled = set()
        for entry in subs:
            if len(entry) > 2 and entry[2] is not None:
                p = entry[2]
            else:
                p = self._topics.get(topic)
            if p and id(p) not in _signaled:
                p.signal_work()
                _signaled.add(id(p))

        if _is_dm_pc:
            _pc_t3 = _pct.time()
            _pcs.stderr.write(f"[PC-DM-DEBUG] Enqueue complete ({_pc_t3 - _pc_t2:.3f}s for {len(subs)} subs, delivered={_dm_enq_i})\n")
            _pcs.stderr.flush()

    def _return_to_sender(self, intent: str, payload, source: str, priority: int) -> None:
        """An undeliverable letter: count it, remember it, and send it back once (no loops)."""
        office = self._return_office
        is_return = intent.startswith(RETURN_PREFIX) or (
            isinstance(payload, dict) and payload.get("_returned") is True)
        if is_return:
            # A returned letter nobody collects: counted, never returned again.
            office.note(return_sender_of(payload, source), intent, "return_undeliverable")
            return
        sender = return_sender_of(payload, source)
        office.note(sender, intent, "no_subscriber")
        if not sender or not office.may_send(intent):
            return
        self.publish(RETURN_PREFIX + sender, {
            "_returned": True,
            "reason": "no_subscriber",
            "intent": intent,
            "sender": sender,
            "t": int(time.time() * 1000),
            "letter": payload,
        }, priority)

    def returns(self) -> Dict[str, Any]:
        """W2: return-to-sender counters and the last N returns. {"enabled": False} when the switch is off."""
        if self._return_office is None:
            return {"enabled": False}
        out = self._return_office.stats()
        out["enabled"] = True
        return out

    def wire_plane_batteries(self, plane_batteries: dict) -> int:
        """Wire PlaneBattery charge levels into postal worker pool scaling.

        FIX 2026-04-01 (Nous + Ace): Instead of static 12 workers per consciousness
        topic, each pool gets a charge callback from its plane's battery.
        Workers scale dynamically with battery charge: full=max, empty=2.

        FIX 2026-04-04 (Nous): Also store batteries for auto-wiring future pools.
        Pools created AFTER this call (during fairy on_boot) now auto-inherit
        their plane's battery in _ensure_topic().

        Args:
            plane_batteries: Dict of plane_id -> PlaneBattery (e.g. {"P30": battery})

        Returns:
            Number of pools that were wired to batteries.
        """
        # Topic prefix → plane mapping
        # FIX 2026-05-09 (Nous + Ace): rebalanced to take load off P00.
        # Previous mapping had 5 high-volume topics (drives/autopilot/fairy/heartbeat/guild)
        # all on P00 — combined with `_base` default→P00 fallback for unmapped topics
        # (incl. this morning's `energy.*` flow.tick instrumentation), P00 absorbed
        # ~47K msgs/sec while other planes were near-idle. Worker pool ran at 4.4x
        # ceiling (W:105/24 observed). Now:
        # - `fairy` → P50 (fairy lifecycle/heartbeat events fit persona-meta plane)
        # - `guild` → P60 (guild-of-minds is meta-level, not autonomic)
        # - `energy` → P60 explicit (was defaulting to P00, creating self-feeding loop:
        #   P00 spend → publishes energy.flow.tick → routes to P00 → drains more)
        # P00 retains genuine autonomics: drives, autopilot, heartbeat (heart-rate is
        # autonomic-essential per BrainstemReflex doctrine).
        _TOPIC_PLANE_MAP = {
            "consciousness": "P30",
            "cognition": "P30",
            "reasoning": "P30",
            "somatic": "P20",
            "memory": "P10",
            "working_memory": "P10",
            "sensory": "P40",
            "cortex": "P30",
            "pain": "P20",
            "drives": "P00",       # autonomic
            "autopilot": "P00",    # autonomic
            "narrator": "P30",
            "interest": "P30",
            "inner_voice": "P30",
            "motor": "P40",
            "fairy": "P50",        # was P00; persona-meta fits fairy lifecycle/heartbeat
            "heartbeat": "P00",    # autonomic-essential (heart rate)
            "guild": "P60",        # was P00; meta-level (guild-of-minds)
            "energy": "P60",       # NEW explicit; breaks self-feeding loop on flow.tick
        }

        # FIX 2026-04-04: Store for auto-wiring future pools
        self._plane_batteries = dict(plane_batteries)

        wired = 0
        with self._lock:
            for topic_key, pool in self._topics.items():
                # Find the plane for this topic
                _base = topic_key.split('.')[0] if '.' in topic_key else topic_key
                _plane = _TOPIC_PLANE_MAP.get(_base, "P00")
                _battery = plane_batteries.get(_plane)
                if _battery and hasattr(_battery, 'capacitor'):
                    # Create closures that read/drain this battery's charge
                    # Drain goes through the battery's tracking so dashboard sees it
                    _cap = _battery.capacitor
                    _bat_ref = _battery
                    pool._battery_charge_fn = lambda c=_cap: c.charge_level
                    def _make_drain(cap, bat):
                        def _drain(amt, reason):
                            cap.discharge(amt, reason=reason)
                            if hasattr(bat, '_track_energy_out'):
                                # Slice 2 (2026-05-09 Nous + Ace): preserve source
                                # attribution into flow.tick events. Was discarding
                                # `reason` here; now plumbs through so the Sinks
                                # panel can show postal_work / worker_cap_<topic> /
                                # etc as distinct sinks instead of one flat "spend".
                                bat._track_energy_out(amt, reason)
                        return _drain
                    pool._battery_drain_fn = _make_drain(_cap, _battery)
                    # FIX 2026-04-05: Set back-refs for plane ceiling check
                    pool._postal_core_ref = self
                    pool._plane_id = _plane
                    wired += 1

        if wired:
            print(f"[PostalCore] Wired {wired} pools to plane batteries (dynamic worker scaling)")
        return wired

    def metrics(self) -> Dict[str, Any]:
        """Get metrics snapshot."""
        # FIX 2026-01-27: Copy dict values to prevent mutation during iteration
        with self._lock:
            pools_snapshot = list(self._topics.values())
            topic_count = len(self._topics)
        total_depth = sum(p.queue_depth() for p in pools_snapshot)
        result = {
            "messages_published": self._metrics["messages_published"],
            "messages_delivered": self._metrics["messages_delivered"],
            "messages_dropped": self._metrics["messages_dropped"],
            "queue_depth": total_depth,
            "topics": topic_count,
            "using_rust": False,  # This is the Python fallback
        }
        # FIX 2026-03-17 Nous: Include farm summary in metrics
        if self._farm_enabled and self._farm:
            result["farm"] = {
                "gravity": round(self._farm.gravity, 2),
                "compression": round(self._farm.time_compression, 1),
                "cost_reduction": round(self._farm.cost_reduction, 1),
                "dispatches": self._farm._total_dispatches,
                "mass_msgs_sec": round(self._farm.message_mass, 1),
            }
        return result

    def topic_stats(self) -> List[Dict[str, Any]]:
        """Get per-topic statistics."""
        stats = []
        # FIX 2026-01-27: Copy dict items to prevent mutation during iteration
        with self._lock:
            topics_snapshot = list(self._topics.items())
        for topic, pool in topics_snapshot:
            entry = {
                "topic": topic,
                "workers": pool._active_worker_count,
                "queue_depth": pool.queue_depth(),
                "subscribers": len(self._subscribers.get(topic, [])),
                "p95_ms": pool.p95_ms(),
                # FIX 2026-03-16 Nous: Cumulative drops for dashboard
                "total_drops": pool._total_drops,
                "top_drop_intents": dict(sorted(pool._total_drop_intents.items(), key=lambda x: -x[1])[:5]),
                # FIX 2026-03-17 Nous: Farm status for battery-powered pools
                "farm_powered": pool._farm_enabled,
            }
            stats.append(entry)
        return stats

    def get_pool_pressure(self, topic_prefix: str = "") -> float:
        """Get queue fullness ratio for pools matching a topic prefix.

        FIX 2026-03-18 (Nous): Backpressure signal for consciousness loop.
        Returns 0.0 (empty) to 1.0 (completely full) — max across all matching pools.
        This is the "two-way street": postal tells consciousness how full it is.

        Args:
            topic_prefix: Filter pools by prefix (e.g., "consciousness").
                          Empty string = all pools.
        Returns:
            float: 0.0-1.0 pressure ratio (max fullness across matching pools)
        """
        max_pressure = 0.0
        with self._lock:
            pools_snapshot = list(self._topics.items())

        for topic, pool in pools_snapshot:
            if topic_prefix and not topic.startswith(topic_prefix):
                continue
            # Calculate fullness ratio across all 3 priority queues
            high_cap = pool.q_high.maxsize or 1
            normal_cap = pool.q_normal.maxsize or 1
            high_full = pool.q_high.qsize() / high_cap
            normal_full = pool.q_normal.qsize() / normal_cap
            # Use max of high and normal (low is irrelevant for pressure)
            pool_pressure = max(high_full, normal_full)
            max_pressure = max(max_pressure, pool_pressure)

        return min(1.0, max_pressure)

    def thread_census(self) -> Dict[str, Any]:
        """Count all threads owned by the postal system.

        FIX 2026-02-12: Added for thread leak monitoring. Returns breakdown
        of postal worker threads, executor threads, and total process threads.
        """
        postal_workers = 0
        topic_breakdown = {}
        with self._lock:
            for topic, pool in self._topics.items():
                active = pool._active_worker_count
                postal_workers += active
                topic_breakdown[topic] = active

        # Count handler queue threads (legacy — may be 0 since DIRECT INVOKE)
        executor_threads = len([t for t in threading.enumerate()
                                if t.name.startswith("postal-handler-")])

        # Total process threads
        total = threading.active_count()

        return {
            "postal_worker_threads": postal_workers,
            "postal_executor_threads": executor_threads,
            "postal_total": postal_workers + executor_threads,
            "process_total_threads": total,
            "topic_breakdown": topic_breakdown,
            "topic_count": len(topic_breakdown),
        }

    def shutdown(self) -> None:
        """Shutdown the postal system."""
        self._running = False
        # Stop the farm
        if self._farm:
            self._farm.stop()
        # FIX 2026-01-27: Copy dict values to prevent mutation during iteration
        with self._lock:
            pools_snapshot = list(self._topics.values())
        for pool in pools_snapshot:
            pool.stop()
        with self._lock:
            self._topics.clear()

    # ─── PostalFarm: Dimensional Battery Subsystem ────────────────────────

    def _init_farm(self):
        """Initialize the PostalFarm — dimensional batteries for message processing.

        FIX 2026-03-17 (Nous + Ace): The farm's gravitational feedback loops
        amplify postal throughput. Batteries power handler dispatch; gravity
        from message mass reduces cost and speeds recharge.

        16 batteries (matches HIGH_VOLUME_MAX_WORKERS), triple feedback loop.
        Graceful: if import fails, postal works normally without farm.
        """
        global _postal_farm_instance
        try:
            from postal_core.postal_farm import PostalFarm
            self._farm = PostalFarm(
                num_batteries=_WorkerPool.HIGH_VOLUME_MAX_WORKERS,
                max_charge=20.0,
                recharge_rate=0.01,
                compression_coeff=4.0,
                flops_gravity_coeff=1.5,
                base_hz=20.0,
                base_handler_cost=0.001,
            )
            self._farm.start()
            self._farm_enabled = True
            _postal_farm_instance = self._farm
            print(f"[PostalCore] PostalFarm ONLINE: {self._farm.num_batteries} batteries, "
                  f"gravity={self._farm.gravity:.1f}, "
                  f"compression={self._farm.time_compression:.0f}x")
        except Exception as e:
            print(f"[PostalCore] PostalFarm init failed (continuing without): {e}")
            self._farm = None
            self._farm_enabled = False

    def farm_status(self) -> Optional[Dict[str, Any]]:
        """Get PostalFarm status for monitoring and dashboard."""
        if self._farm and self._farm_enabled:
            return self._farm.status()
        return None

    def farm_receive_energy(self, amount: float, source: str = "paradox"):
        """Feed energy into the PostalFarm from external source.

        Called from paradox energy pipeline, consciousness pulse, etc.
        Energy is amplified by the farm's time compression (Loop 3).
        """
        if self._farm and self._farm_enabled:
            self._farm.receive_energy(amount, source=source)

    # ─────────────────────────────────────────────────────────────────────

    # ────────────────────────────────────────────────────────────────────
    # POOL ROUTER WIRING (2026-04-15 Nous + Ace — POSTAL_INSIDE_PORTAL Phase 1)
    # ────────────────────────────────────────────────────────────────────

    def attach_pool_router(self, router, fabric=None) -> int:
        """Wire an in-process PoolRouter for critical pool traffic.

        After attachment:
          - publish() routes CRITICAL_VOLUME topics through the router
            instead of the local _WorkerPool queue
          - Existing subscriptions are bulk-subscribed into the router so
            the manifold topology immediately reflects live state
          - New subscribes on CRITICAL topics are echoed to the router as
            they're created

        Walks BOTH PostalCore._subscribers AND TensorFabric._handlers to
        capture every subscription, deduplicated by id(callback). The
        PostalCore path contains _BaseTopicPostal wrappers; the fabric
        path contains raw fairy handlers (preferred).

        Args:
            router: PoolRouter instance, ready to accept subscribes.
            fabric: Optional TensorFabric instance — also walked.

        Returns:
            Number of subscriptions successfully added to the router.
        """
        self._pool_router = router
        self._pool_router_fabric_ref = fabric
        critical = _WorkerPool.CRITICAL_VOLUME_TOPICS

        # Collect snapshot of (topic, callback, name) tuples — dedupe by
        # id(callback) so the same handler registered in both stores
        # only subscribes once.
        seen_callback_ids = set()
        snapshot: List[tuple] = []
        pc_count = 0
        fabric_count = 0

        # Source 1: PostalCore._subscribers (pool dispatch wrappers)
        with self._lock:
            for intent, subs in self._subscribers.items():
                topic_base = intent.split('.')[0]
                if topic_base not in critical and intent not in critical:
                    continue
                pc_count += len(subs)
                for entry in subs:
                    handler_id = entry[0]
                    name = entry[1]
                    pool = entry[2] if len(entry) > 2 else None
                    if pool and 0 <= handler_id < len(pool.handlers):
                        callback = pool.handlers[handler_id]
                        cid = id(callback)
                        if cid not in seen_callback_ids:
                            seen_callback_ids.add(cid)
                            snapshot.append((intent, callback, name))

        # Source 2: TensorFabric._handlers (raw fairy handlers)
        if fabric is not None and hasattr(fabric, "_handlers"):
            try:
                for intent, handlers in fabric._handlers.items():
                    topic_base = intent.split('.')[0]
                    if topic_base not in critical and intent not in critical:
                        continue
                    fabric_count += len(handlers)
                    for h in handlers:
                        cid = id(h)
                        if cid not in seen_callback_ids:
                            seen_callback_ids.add(cid)
                            name = getattr(
                                h, "__qualname__",
                                getattr(h, "__name__", "fairy_handler"),
                            )
                            snapshot.append((intent, h, name))
            except Exception as e:
                print(
                    f"[PostalCore] Warning: could not walk fabric._handlers: {e}",
                    flush=True,
                )

        # Bulk subscribe — one lock acquisition, one iteration, done
        added = router.bulk_subscribe(snapshot)

        print(
            f"[PostalCore] Pool router attached — {added} subs added "
            f"(pc_subs={pc_count}, fabric_handlers={fabric_count}, "
            f"unique={len(snapshot)}, critical={sorted(critical)})",
            flush=True,
        )
        return added

    def _is_critical_topic(self, intent: str) -> bool:
        """Check if a topic is in CRITICAL_VOLUME_TOPICS (base or exact)."""
        parts = intent.split('.')
        base = parts[0]
        critical = _WorkerPool.CRITICAL_VOLUME_TOPICS
        return base in critical or intent in critical

    def _echo_subscribe_if_critical(
        self,
        intent: str,
        callback: Callable,
        name: str,
    ) -> None:
        """On new subscribe, add to router if topic is critical."""
        if self._pool_router is None:
            return
        if not self._is_critical_topic(intent):
            return
        try:
            self._pool_router.subscribe(intent, callback, name)
        except Exception as e:
            print(
                f"[PostalCore] router subscribe failed for '{intent}': {e}",
                flush=True,
            )

    def _pool_publish_fast_path(
        self,
        intent: str,
        payload: Optional[Dict[str, Any]],
        priority: int,
    ) -> bool:
        """Publish a critical message via the in-process PoolRouter.

        Returns True if the router delivered to at least one handler.
        Returns False if no handlers (fall through to legacy _WorkerPool).

        Hot path: pure dict lookup in the router, executor submit for each
        matched subscriber. No TCP, no lock on exterior side (router has
        its own lock for dict mutation; publish is lock-free).
        """
        router = self._pool_router
        if router is None:
            return False

        # Build an Envelope once; the router dispatches it to all subscribers
        envelope = Envelope(
            intent=intent, payload=payload or {}, priority=priority
        )

        dispatched = router.publish(intent, envelope)
        if dispatched == 0:
            # No subscribers in router — fall through to legacy path so
            # non-router subscribers (if any) still fire
            self._metrics["pool_tunnel_fallbacks"] += 1
            return False

        self._metrics["messages_published"] += 1
        self._metrics["pool_tunnel_publishes"] += 1
        self._metrics["messages_delivered"] += dispatched
        self._metrics["pool_tunnel_dispatches"] += dispatched
        return True

    # ────────────────────────────────────────────────────────────────────

    def _ensure_topic(self, topic: str) -> _WorkerPool:
        """Ensure a topic pool exists.

        FIX 2026-03-17 (Nous + Ace): HIGH_VOLUME pools get connected to the
        PostalFarm for battery-powered processing with gravitational amplification.
        FIX 2026-04-04 (Nous): Auto-wire plane battery on new pool creation.
        Previously, pools created after wire_plane_batteries() missed battery
        wiring and defaulted to unlimited handler-count scaling (3844 threads).
        """
        if topic not in self._topics:
            pool = _WorkerPool(topic)
            # Connect farm to HIGH_VOLUME topic pools
            base = topic.split('.')[0]
            if self._farm_enabled and self._farm and base in _WorkerPool.HIGH_VOLUME_TOPICS:
                pool._farm = self._farm
                pool._farm_enabled = True
            # FIX 2026-04-04: Auto-wire plane battery for energy-governed scaling
            _plane = self._topic_plane_map.get(base, "P00")
            if self._plane_batteries:
                _battery = self._plane_batteries.get(_plane)
                if _battery and hasattr(_battery, 'capacitor'):
                    _cap = _battery.capacitor
                    pool._battery_charge_fn = lambda c=_cap: c.charge_level
            # FIX 2026-04-05: Back-ref for plane ceiling check
            pool._postal_core_ref = self
            pool._plane_id = _plane
            pool.start()
            self._topics[topic] = pool
        return self._topics[topic]


# Quick test
if __name__ == "__main__":
    import time

    postal = PostalCore()
    received = []

    def handler(env):
        received.append(env.intent)
        print(f"Received: {env.intent} - {env.payload}")

    postal.subscribe("test", handler)

    for i in range(5):
        postal.publish(f"test.message.{i}", {"index": i})

    time.sleep(0.2)
    print(f"\nReceived {len(received)} messages")
    print(f"Metrics: {postal.metrics()}")

    postal.shutdown()
