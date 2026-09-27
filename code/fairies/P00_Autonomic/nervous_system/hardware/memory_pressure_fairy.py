from __future__ import annotations

"""
Memory Pressure Fairy (v0.3.0)

ACTIVE memory management with agent spawning.
Now a proper Fairy that extends fairy_template for postal/directory integration.

ARCHITECTURE:
  - Target: Keep RAM under 50% if possible
  - Lower thresholds with escalating responses
  - If GC doesn't free enough, spawn helper agents
  - Helper agents attack specific memory hogs

ESCALATION LEVELS:
  Level 0 (0-40%):   Comfortable - just monitor
  Level 1 (40-50%):  Warning - light GC
  Level 2 (50-60%):  Elevated - full GC + cache flush requests
  Level 3 (60-70%):  High - spawn MailboxPruner + DequePatrol
  Level 4 (>70%):    Critical - spawn LeakHunter + emergency measures

HELPER AGENTS (spawn when GC isn't enough):
  - CacheFlushAgent: Broadcasts cache flush to all fairies
  - MailboxPrunerAgent: Trims postal mailboxes
  - DequePatrolAgent: Finds and trims unbounded deques
  - LeakHunterAgent: Profiles memory to find biggest hogs
"""

import sys
import gc
import time
import threading
from typing import Any, Dict, Optional, List, Set
from collections import deque
import weakref

# MCP-SAFE: redirect prints to stderr
_builtin_print = print
def print(*args, **kwargs):
    kwargs['file'] = sys.stderr
    _builtin_print(*args, **kwargs)

# Import Fairy base class
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# ---- Soft imports ----
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER AGENTS - These get spawned to attack specific memory problems
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryAgent:
    """Base class for memory relief agents."""

    def __init__(self, parent: 'MemoryPressureFairy'):
        self.parent = weakref.ref(parent)
        self.spawn_time = time.time()
        self.actions_taken = 0
        self.bytes_freed = 0

    def run(self) -> Dict[str, Any]:
        """Execute the agent's task. Override in subclass."""
        raise NotImplementedError

    def report(self) -> Dict[str, Any]:
        return {
            "agent": self.__class__.__name__,
            "spawn_time": self.spawn_time,
            "actions": self.actions_taken,
            "bytes_freed": self.bytes_freed,
            "age_sec": time.time() - self.spawn_time,
        }


class CacheFlushAgent(MemoryAgent):
    """
    Broadcasts cache flush requests to all fairies.
    Many fairies keep caches that can be cleared under pressure.
    """

    def run(self) -> Dict[str, Any]:
        parent = self.parent()
        if not parent or not parent.fabric:
            return {"success": False, "reason": "no_fabric"}

        # Broadcast flush request to multiple channels
        request = {
            "opcode": "FLUSH_CACHES_URGENT",
            "payload": {
                "reason": "memory_pressure",
                "level": parent._last_level,
                "ram_pct": parent._get_memory_percent(),
                "ts": time.time(),
            }
        }

        channels = [
            "memory.stream",
            "telemetry",
            "system.command",
            "fairy.command",
        ]

        sent = 0
        for ch in channels:
            try:
                parent.fabric.publish(ch, request)
                sent += 1
            except Exception:
                pass

        self.actions_taken = sent
        print(f"[CacheFlushAgent] Broadcast flush request to {sent} channels")
        return {"success": True, "channels_notified": sent}


class MailboxPrunerAgent(MemoryAgent):
    """
    Trims postal mailboxes that may have accumulated old messages.
    Postal mailboxes can grow unbounded if nobody consumes them.
    """

    MAX_MAILBOX_SIZE = 100  # Keep only latest N messages per topic

    def run(self) -> Dict[str, Any]:
        parent = self.parent()
        if not parent:
            return {"success": False, "reason": "no_parent"}

        pruned_count = 0
        bytes_before = self._estimate_postal_size()

        try:
            # Try to access the shared postal hub directly
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()

            if postal and hasattr(postal, '_mailboxes'):
                mailboxes = postal._mailboxes
                for topic, box in mailboxes.items():
                    if hasattr(box, '__len__') and len(box) > self.MAX_MAILBOX_SIZE:
                        old_len = len(box)
                        # If it's a deque, we can truncate by reassigning
                        if isinstance(box, deque):
                            # Keep only the latest messages
                            while len(box) > self.MAX_MAILBOX_SIZE:
                                box.popleft()
                                pruned_count += 1
                        # If it's a list
                        elif isinstance(box, list):
                            del box[:-self.MAX_MAILBOX_SIZE]
                            pruned_count += old_len - len(box)

            # Also check subscriber lists
            if postal and hasattr(postal, '_subscribers'):
                # Can't prune subscribers but can report
                sub_count = sum(len(subs) for subs in postal._subscribers.values())
                print(f"[MailboxPrunerAgent] {sub_count} active subscribers")

        except Exception as e:
            print(f"[MailboxPrunerAgent] Error pruning: {e}")

        bytes_after = self._estimate_postal_size()
        self.bytes_freed = bytes_before - bytes_after
        self.actions_taken = pruned_count

        if pruned_count > 0:
            print(f"[MailboxPrunerAgent] Pruned {pruned_count} old messages")

        return {
            "success": True,
            "messages_pruned": pruned_count,
            "bytes_freed_est": self.bytes_freed,
        }

    def _estimate_postal_size(self) -> int:
        """Rough estimate of postal memory usage."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            if postal and hasattr(postal, '_mailboxes'):
                # Very rough estimate: 1KB per message average
                total_msgs = sum(
                    len(box) for box in postal._mailboxes.values()
                    if hasattr(box, '__len__')
                )
                return total_msgs * 1024
        except Exception:
            pass
        return 0


class DequePatrolAgent(MemoryAgent):
    """
    Finds and reports unbounded deques across the system.
    Unbounded deques (maxlen=None) can grow forever and leak memory.
    """

    def run(self) -> Dict[str, Any]:
        parent = self.parent()
        if not parent:
            return {"success": False, "reason": "no_parent"}

        findings = []
        trimmed = 0

        # Scan imported modules for deque attributes
        for name, module in list(sys.modules.items()):
            if module is None:
                continue
            if not name.startswith(('P00_', 'P10_', 'P20_', 'P30_', 'P40_', 'P50_', 'P60_')):
                continue

            try:
                for attr_name in dir(module):
                    try:
                        attr = getattr(module, attr_name, None)
                        if isinstance(attr, deque):
                            # Check if unbounded and large
                            if attr.maxlen is None and len(attr) > 1000:
                                findings.append({
                                    "module": name,
                                    "attr": attr_name,
                                    "size": len(attr),
                                    "maxlen": attr.maxlen,
                                })
                                # Trim to 1000 items
                                while len(attr) > 1000:
                                    attr.popleft()
                                    trimmed += 1
                    except Exception:
                        pass
            except Exception:
                pass

        self.actions_taken = len(findings)

        if findings:
            print(f"[DequePatrolAgent] Found {len(findings)} large unbounded deques:")
            for f in findings[:5]:  # Show first 5
                print(f"  - {f['module']}.{f['attr']}: {f['size']} items")
            if trimmed > 0:
                print(f"[DequePatrolAgent] Trimmed {trimmed} items total")

        return {
            "success": True,
            "unbounded_deques": len(findings),
            "items_trimmed": trimmed,
            "findings": findings[:10],  # First 10
        }


class LeakHunterAgent(MemoryAgent):
    """
    Profiles memory to identify the biggest consumers.
    This is the heavy artillery - only spawn when really needed.

    Uses MemoryLeakTracer for detailed tracemalloc-based diagnostics
    to identify WHERE allocations are coming from.
    """

    def run(self) -> Dict[str, Any]:
        parent = self.parent()
        if not parent:
            return {"success": False, "reason": "no_parent"}

        report = {
            "success": True,
            "timestamp": time.time(),
            "findings": [],
        }

        # Use MemoryLeakTracer for detailed diagnostics
        try:
            from fairies.P00_Autonomic.utils.memory_leak_tracer import get_memory_tracer
            tracer = get_memory_tracer()

            # Take a snapshot if tracer is running
            if hasattr(tracer, '_running') and tracer._running:
                snap_name = f"leak_hunt_{int(time.time())}"
                tracer.snapshot(snap_name)

                # Get top memory consumers with source locations
                top_consumers = tracer.get_top_consumers(10)
                report["tracemalloc_top_consumers"] = top_consumers

                # Get comparison from start if available
                if "start" in getattr(tracer, '_snapshots', {}):
                    comparison = tracer.compare("start", snap_name)
                    report["growth_since_start"] = {
                        "memory_growth_mb": comparison.get("memory_growth_mb", 0),
                        "growth_rate_mb_per_hour": comparison.get("memory_growth_rate_mb_per_hour", 0),
                        "top_growing_types": dict(list(comparison.get("top_growing_types", {}).items())[:5]),
                    }
                    print(f"[LeakHunterAgent] Growth rate: {comparison.get('memory_growth_rate_mb_per_hour', 0):.1f} MB/hour")
        except Exception as e:
            print(f"[LeakHunterAgent] MemoryLeakTracer not available: {e}")

        # Get process memory breakdown
        if HAS_PSUTIL:
            try:
                proc = psutil.Process()
                mem_info = proc.memory_info()
                report["process"] = {
                    "rss_mb": mem_info.rss / (1024**2),
                    "vms_mb": mem_info.vms / (1024**2),
                }

                # FIX 2026-03-03 (Nous): SINGLE-PASS gc scan.
                # OLD: 3 separate gc.get_objects() passes (count, then lists, then dicts).
                # Each pass iterates EVERY Python object (~millions), holding the GIL
                # the entire time. With multiple LeakHunterAgents, this consumed 200%+ CPU
                # and caused stop-and-go terminal output.
                # NEW: One pass collects all metrics. Yields GIL every 50K objects.
                gc.collect()

                type_counts = {}
                type_sizes = {}
                large_lists = 0
                large_dicts = 0
                scan_count = 0
                # -- REFERRER ANALYSIS 2026-09-05 (Nous + Ace) ------------------
                # This agent reported WHAT was accumulating and never WHO held it.
                # Measured: 1,622,793 sets / 786,451 dicts / 523,761 lists and
                # "51 lists with >10K items", against 13.78 GB of ANONYMOUS heap
                # vs a 3.46 GB mmap cortex that can no longer stay resident
                # (248,650 page faults/sec; edge throughput fell 105x in one boot).
                # Ownership is the one missing fact. Collect the oversized
                # containers HERE -- the scan already identifies them, so this
                # costs nothing extra -- then resolve holders in ONE pass below.
                _big = []
                _TRACK_MAX = 12
                _REF_BUDGET_S = 20.0

                for obj in gc.get_objects():
                    scan_count += 1

                    # Yield GIL every 50K objects to prevent starvation
                    if scan_count % 50000 == 0:
                        time.sleep(0)  # GIL yield point

                    try:
                        t = type(obj).__name__
                        type_counts[t] = type_counts.get(t, 0) + 1
                        type_sizes[t] = type_sizes.get(t, 0) + sys.getsizeof(obj)

                        # Pattern detection in same pass
                        if isinstance(obj, list) and len(obj) > 10000:
                            large_lists += 1
                            if len(_big) < _TRACK_MAX:
                                _big.append(obj)
                        elif isinstance(obj, dict) and len(obj) > 10000:
                            large_dicts += 1
                            if len(_big) < _TRACK_MAX:
                                _big.append(obj)
                        elif isinstance(obj, set) and len(obj) > 10000:
                            if len(_big) < _TRACK_MAX:
                                _big.append(obj)
                    except Exception:
                        pass

                # Top 10 by count
                top_count = sorted(type_counts.items(), key=lambda x: -x[1])[:10]
                report["top_by_count"] = top_count

                # Top 10 by size
                top_size = sorted(type_sizes.items(), key=lambda x: -x[1])[:10]
                report["top_by_size"] = [
                    (t, s / (1024**2)) for t, s in top_size
                ]

                # Patterns from single pass
                patterns = []
                if large_lists > 0:
                    patterns.append(f"Found {large_lists} lists with >10K items")
                if large_dicts > 0:
                    patterns.append(f"Found {large_dicts} dicts with >10K items")
                report["patterns"] = patterns

                # -- REFERRER ANALYSIS 2026-09-05 (Nous + Ace) ------------------
                # ONE gc.get_referrers() call over ALL tracked containers.
                # get_referrers walks the WHOLE heap per call, so calling it per
                # object would be ~12 full passes over 3.6M objects inside a mind
                # already thrashing. One call, hard time budget, GIL yields.
                # A diagnostic must never become the outage it is diagnosing.
                _owners = []
                try:
                    if _big:
                        _t_ref = time.time()
                        _ids = {id(o): i for i, o in enumerate(_big)}
                        _seen = 0
                        for _r in gc.get_referrers(*_big):
                            _seen += 1
                            if _seen % 50000 == 0:
                                time.sleep(0)  # GIL yield, same as the scan above
                            if time.time() - _t_ref > _REF_BUDGET_S:
                                _owners.append("(referrer scan hit %.0fs budget)"
                                               % _REF_BUDGET_S)
                                break
                            try:
                                _rt = type(_r).__name__
                                # ★ On Python 3.11+ (and 3.14t here) instances use
                                # MANAGED DICTS: get_referrers returns the OBJECT,
                                # not its __dict__. Verified on this interpreter --
                                # the naive "scan the referrer as a dict" approach
                                # finds NOTHING and would have reported "no owners".
                                # So read vars() to name the attribute directly.
                                _rd = getattr(_r, "__dict__", None)
                                if isinstance(_rd, dict):
                                    for _k, _v in list(_rd.items())[:4000]:
                                        if id(_v) in _ids and isinstance(_k, str):
                                            _t = _big[_ids[id(_v)]]
                                            _owners.append("%s.%s -> %s(%d)"
                                                           % (_rt[:40], _k[:40],
                                                              type(_t).__name__, len(_t)))
                                elif isinstance(_r, dict):
                                    # module globals / a plain cache dict
                                    for _k, _v in list(_r.items())[:4000]:
                                        if id(_v) in _ids and isinstance(_k, str):
                                            _t = _big[_ids[id(_v)]]
                                            _owners.append("dict['%s'] -> %s(%d)"
                                                           % (_k[:40], type(_t).__name__,
                                                              len(_t)))
                                elif _rt not in ("list", "tuple", "frame"):
                                    _owners.append("%s holds a big container" % _rt[:48])
                            except Exception:
                                pass
                        # de-dup, keep it short enough for a cp1252 console
                        _uniq = []
                        for _o in _owners:
                            if _o not in _uniq:
                                _uniq.append(_o)
                        _owners = _uniq[:12]
                        report["big_container_owners"] = _owners
                except Exception as _re:
                    print("[LeakHunterAgent] referrer analysis failed: %s" % str(_re)[:120])
                finally:
                    # Drop the strong refs immediately -- a leak hunter must not
                    # become a leak.
                    try:
                        _big = []
                        del _ids
                    except Exception:
                        pass

                self.actions_taken = 1

                print(f"[LeakHunterAgent] Memory analysis complete ({scan_count:,} objects scanned):")
                print(f"  Process RSS: {report['process']['rss_mb']:.1f} MB")
                print(f"  Top types: {report['top_by_count'][:5]}")
                if patterns:
                    for p in patterns:
                        print(f"  [WARN] {p}")
                if report.get("big_container_owners"):
                    print("  [OWNERS] who holds the oversized containers:")
                    for _o in report["big_container_owners"]:
                        print(f"    {_o}")

            except Exception as e:
                report["error"] = str(e)
                print(f"[LeakHunterAgent] Analysis error: {e}")
        else:
            report["error"] = "psutil not available"

        return report


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryPressureFairy(Fairy):
    """
    Active memory pressure manager with agent spawning.

    Now a proper Fairy that integrates with the postal system and Directory.

    THRESHOLDS (target: keep under 50%):
      - Level 0 (0-40%):   Comfortable - just monitor
      - Level 1 (40-50%):  Warning - light GC
      - Level 2 (50-60%):  Elevated - full GC + cache flush
      - Level 3 (60-70%):  High - spawn pruning agents
      - Level 4 (>70%):    Critical - spawn leak hunter + emergency
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # FAIRY IDENTITY
    # ═══════════════════════════════════════════════════════════════════════════

    ACTOR_NAME = "MemoryPressureFairy"
    ACTOR_VERSION = "0.3.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "hardware.memory"

    # ═══════════════════════════════════════════════════════════════════════════
    # FAIRY CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════════

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 1  # Check every heartbeat (we manage our own cadence)

    # Disable infrastructure we don't need (lightweight fairy)
    NEEDS_CIRCADIAN = False
    NEEDS_BODY = False
    NEEDS_AFFECT = False
    NEEDS_MEMORY = False
    NEEDS_GOALS = False
    NEEDS_CONSCIOUSNESS = False
    NEEDS_CORTEX = False
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_LEARNING = False

    # ═══════════════════════════════════════════════════════════════════════════
    # THRESHOLDS AND CADENCE
    # ═══════════════════════════════════════════════════════════════════════════

    # Lower thresholds - target is to stay under 50%
    THRESHOLD_WARNING = 40.0     # Start paying attention
    THRESHOLD_ELEVATED = 50.0    # Target ceiling
    THRESHOLD_HIGH = 60.0        # Getting concerning
    THRESHOLD_CRITICAL = 70.0    # Need aggressive action

    # FREE-RAM FLOOR (2026-06-25, Nous): system-% is only a PROXY for "running low" — the real
    # signal is ABSOLUTE free RAM. A large-but-LIVE footprint (e.g. a ~12GB mmap cortex on a 32GB
    # box → ~70% system RAM with ~9GB free) is NOT an emergency, and gc.collect() can't shrink it
    # anyway. Without this floor the % ladder pins such a system in permanent "critical" → endless
    # CRIT alerts + futile agent spawns (incl the heavy LeakHunter, since GC can never look
    # "effective" against a live mmap). So escalation past "comfortable" now requires free RAM to
    # be genuinely low. Tune to taste (Ace's dial); 3GB suits the 32GB box.
    MIN_FREE_GB = 3.0            # >= this much AVAILABLE RAM ⇒ no pressure, just monitor

    # Cadence (seconds between checks at each level)
    CADENCE_COMFORTABLE = 30.0
    CADENCE_WARNING = 20.0
    CADENCE_ELEVATED = 15.0     # was 10 — too aggressive for 9GB process
    CADENCE_HIGH = 10.0         # was 5  — GC alone takes several seconds
    CADENCE_CRITICAL = 5.0      # was 3  — need breathing room between GCs

    # FIX 2026-03-03 (Nous): Minimum seconds between GC runs.
    # gc.collect(2) on a 9GB process holds the GIL for seconds, blocking ALL
    # other threads (print, consciousness, speech). Running it every 5s caused
    # permanent stop-and-go. Now we enforce at least 60s between full GCs.
    MIN_GC_INTERVAL = 60.0

    # GC effectiveness threshold - if we free less than this %, escalate
    GC_EFFECTIVENESS_THRESHOLD = 2.0  # If GC frees <2%, it's not helping

    # ═══════════════════════════════════════════════════════════════════════════
    # GC-CONTROLLER + GROWTH-RATE GUARD (2026-07-16 Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════════
    # WHY: two failure modes, one root (millions of gc-tracked objects):
    #  1) FREEZE (07-13) — a full gc.collect(2) is STOP-THE-WORLD: it froze EVERY
    #     thread for seconds. The "SLOW: X callback took 111s" lines were 2-LINE
    #     liveness callbacks frozen mid-run, not slow fairies. Sandbox: thread-freeze
    #     2213ms default -> 12ms with gc.disable() (~180x). gen0=146ms vs gen2=836ms.
    #  2) CRASH (07-13 OOM) — _get_level's FREE-RAM FLOOR keeps us "comfortable"
    #     (cadence 30s, NO action) until ~29GB, so an 11->32GB runaway in <30s
    #     balloons BETWEEN checks and we NEVER react. We reacted AT 100% = too late.
    # SO: this fairy now OWNS gc (automatic collection disabled at boot) and does
    # cheap gen-0 OFTEN on a level-INDEPENDENT fast poll, full gen-2 RARELY in a
    # window. gen-0 must ride the FAST poll (not the level ladder) — gc.disable()
    # plus sparse ladder-collection would let RAM climb unchecked to the floor and
    # CAUSE the very OOM we're fixing.
    POLL_FAST_SEC = 5.0             # cheap RSS poll + gen-0 (level-INDEPENDENT)
    RATE_LIMIT_MB_PER_MIN = 4096.0  # >4GB/min climb = runaway -> EMERGENCY (bypasses free-RAM floor)
    EMERGENCY_COOLDOWN_SEC = 60.0
    FULL_GC_WINDOW_SEC = 300.0      # deep gen-2 reclaim, off the hot path
    # FIX 2026-07-16b (caught by the LIVE loop, not the sim): BOOT legitimately
    # allocates ~0->10GB in the first minute (manifold/cortex load) = ~16GB/min,
    # which tripped the rate guard on the very first boot ("RUNAWAY rss=9021MB
    # climbing 16.5GB/min") and spuriously fired a full gen-2 + cache flush.
    # A runaway only MATTERS if it's heading for the 32GB wall, so require BOTH
    # a high rate AND an already-high RSS, plus a grace window past boot.
    # (The 07-13 runaway went 11GB->32GB, so it crosses 16GB early and still gets
    #  ~16GB / ~30s of headroom — vs the old logic's "never fires".)
    RUNAWAY_MIN_RSS_MB = 16384.0    # don't alarm below ~half the box (boot's ~10GB is normal)
    BOOT_GRACE_SEC = 180.0          # don't arm the rate guard until the load settles

    # ── ZERO-COLLECT TEST (2026-07-16, Ace's call — the LIVE arbiter) ──
    # The gc-controller did NOT collapse the SLOW callbacks (10 before, 10 after;
    # worst 47.7s). Sandbox says the worst GC pause reproducible is ~0.9-2.2s, i.e.
    # 20-50x too small to BE her 47s freeze — but the sandbox measures the MECHANISM,
    # only her loop measures the SYSTEM. So: run with gc.disable() and ZERO scheduled
    # collects for one boot and read the SLOW list.
    #   SLOW vanishes  -> GC IS the freeze after all -> collect far less / only in sleep.
    #   SLOW persists  -> GC is NOT the cause -> hunt elsewhere (status-gather lock is
    #                     the prime suspect: fairies: 132,123ms, 0.1ms at beat 40).
    # SAFETY: the level ladder (_monitor_tick) still collects under real pressure, and
    # the runaway guard still emergency-collects >16GB. RAM WILL grow this run — expected.
    # REVERT: set back to True (or restore .bak_gcctl_0716).
    SCHEDULED_COLLECTS_ENABLED = False

    # ═══════════════════════════════════════════════════════════════════════════
    # INITIALIZATION
    # ═══════════════════════════════════════════════════════════════════════════

    def __init__(self, fabric=None):
        """Initialize the Memory Pressure Fairy."""
        super().__init__(fabric)

        self._last_gc_time = 0.0
        self._gc_count = 0
        self._last_level = "comfortable"
        self._pressure_history: deque = deque(maxlen=120)
        self._last_alert_time = 0.0
        self._alert_cooldown = 30.0

        # GC effectiveness tracking
        self._gc_results: deque = deque(maxlen=10)
        self._ineffective_gc_streak = 0

        # Agent tracking
        self._active_agents: List[MemoryAgent] = []
        self._agent_cooldowns: Dict[str, float] = {}  # agent_class -> last_spawn_time
        # FIX 2026-03-03 (Nous): 60s was far too short — LeakHunterAgent takes
        # minutes to scan millions of objects, so new agents piled up every 60s.
        self._agent_cooldown_sec = 300.0  # 5 min between same agent type

        # Cadence management (track last check time for dynamic cadence)
        self._last_check_time = 0.0
        self._monitor_tick_count = 0

        # GC-CONTROLLER + GROWTH-RATE GUARD state (2026-07-16)
        self._last_rss_mb = 0.0
        self._last_rss_time = 0.0
        self._last_fast_poll = 0.0
        self._emergency_fired_at = 0.0
        self._last_full_gc = 0.0
        self._boot_time = 0.0  # set in on_boot; gates the rate guard past boot load

    # ═══════════════════════════════════════════════════════════════════════════
    # FAIRY LIFECYCLE HOOKS
    # ═══════════════════════════════════════════════════════════════════════════

    def get_capabilities(self) -> Set[str]:
        """Return capabilities for Directory registration."""
        return {
            "hardware.memory.monitor",
            "hardware.memory.gc",
            "hardware.memory.pressure",
        }

    def on_boot(self) -> bool:
        """Called when fairy boots. Initialize monitoring state."""
        self._last_check_time = time.time()
        self._boot_time = time.time()  # rate guard arms only after BOOT_GRACE_SEC
        # GC-CONTROLLER (2026-07-16): disable AUTOMATIC stop-the-world collection.
        # A collect over ~millions of gc-tracked objects freezes EVERY thread for
        # seconds (the 07-13 "121s SLOW callback" freeze). We schedule it ourselves:
        # cheap gen-0 on the fast poll, full gen-2 only in a window / under pressure.
        # Reversible: gc.enable() restores stock behaviour.
        try:
            gc.disable()
            if self.SCHEDULED_COLLECTS_ENABLED:
                print(f"[{self.ACTOR_NAME}] GC-CONTROLLER: automatic gc DISABLED "
                      f"(gen0 every {self.POLL_FAST_SEC:.0f}s, full gen2 every {self.FULL_GC_WINDOW_SEC:.0f}s/pressure)")
            else:
                print(f"[{self.ACTOR_NAME}] *** ZERO-COLLECT TEST *** automatic gc DISABLED + NO scheduled "
                      f"collects (ladder/runaway-guard only). RAM will grow — reading the SLOW list to "
                      f"decide: is GC the freeze, or not?")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] gc.disable failed (non-fatal, stock gc stays on): {e}")
        print(f"[{self.ACTOR_NAME}] [OK] Started v{self.ACTOR_VERSION} (target: <{self.THRESHOLD_ELEVATED}% RAM)")
        return True

    def on_shutdown(self) -> bool:
        """Called during shutdown. Clean up agents."""
        self._active_agents.clear()
        print(f"[{self.ACTOR_NAME}] Stopped")
        return True

    def on_tick(self, beat: int) -> None:
        """
        Called on each heartbeat. Check if it's time to monitor based on cadence.

        The cadence is dynamic based on pressure level - we check more frequently
        under higher pressure. The heartbeat provides the clock, but we only
        act when enough time has passed based on current cadence.
        """
        now = time.time()

        # ── FAST PATH (2026-07-16): level-INDEPENDENT, every POLL_FAST_SEC ──
        # A bare psutil rss read is microseconds. The free-RAM floor keeps us
        # "comfortable" to ~29GB, so the level ladder below is BLIND to a fast
        # runaway (the 07-13 OOM) — this poll is what actually catches it. It also
        # does the cheap gen-0 that keeps garbage from aging into the costly gen-2.
        if now - self._last_fast_poll >= self.POLL_FAST_SEC:
            self._last_fast_poll = now
            try:
                self._fast_poll(now)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] fast_poll error (non-fatal): {e}")

        cadence = self._get_cadence(self._last_level)

        # Only check if enough time has passed (respects dynamic cadence)
        if now - self._last_check_time < cadence:
            return

        self._last_check_time = now
        self._monitor_tick()

    # ═══════════════════════════════════════════════════════════════════════════
    # GC-CONTROLLER + GROWTH-RATE GUARD (2026-07-16 Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════════

    def _fast_poll(self, now: float) -> None:
        """Cheap + level-independent: growth-rate guard, then young-gen collect."""
        rss = self._get_python_memory_mb()

        # ── GROWTH-RATE GUARD: escalate on dRSS/dt, BYPASSING the free-RAM floor.
        # The floor assumes gradual change; a runaway is not gradual.
        # Gated by RUNAWAY_MIN_RSS_MB + BOOT_GRACE_SEC so boot's own legitimate
        # manifold load (~16GB/min to ~10GB) doesn't trip it (fix 2026-07-16b).
        armed = (rss > self.RUNAWAY_MIN_RSS_MB and
                 self._boot_time > 0.0 and
                 now - self._boot_time > self.BOOT_GRACE_SEC)
        if armed and self._last_rss_time and rss > 0 and self._last_rss_mb > 0:
            dt = now - self._last_rss_time
            if dt > 0:
                rate = (rss - self._last_rss_mb) / dt * 60.0  # MB/min
                if (rate > self.RATE_LIMIT_MB_PER_MIN and
                        now - self._emergency_fired_at > self.EMERGENCY_COOLDOWN_SEC):
                    self._emergency_fired_at = now
                    self._on_runaway(rss, rate)
        self._last_rss_mb = rss
        self._last_rss_time = now

        # ── ZERO-COLLECT TEST gate: when False we do NO scheduled collection at all
        # (gc is disabled at boot), so the SLOW list answers "is GC the freeze?".
        if not self.SCHEDULED_COLLECTS_ENABLED:
            return

        # ── cheap gen-0: young cyclic garbage only (~146ms@1M .. ~277ms@5M, sub-linear).
        # Frequent gen-0 keeps garbage from aging, so the rare gen-2 has less to do.
        gc.collect(0)

        # ── deep gen-2 ONLY in a maintenance window, off the hot path.
        if now - self._last_full_gc > self.FULL_GC_WINDOW_SEC:
            self._last_full_gc = now
            gc.collect(2)

    def _on_runaway(self, rss_mb: float, rate_mb_min: float) -> None:
        """A runaway allocation is climbing fast. React NOW — the level ladder won't."""
        print(f"[{self.ACTOR_NAME}] *** RUNAWAY ALLOCATION *** rss={rss_mb:.0f}MB climbing "
              f"{rate_mb_min / 1024.0:.1f}GB/min -- emergency response", flush=True)
        # 1) Name the site if tracemalloc is live (heap_profiler level=2, deferred start).
        try:
            import tracemalloc
            if tracemalloc.is_tracing():
                snap = tracemalloc.take_snapshot()
                for s in snap.statistics("traceback")[:3]:
                    where = " | ".join(str(f) for f in s.traceback[:3])
                    print(f"[{self.ACTOR_NAME}] [RUNAWAY-SITE] {s.size / 1e6:.0f}MB @ {where}", flush=True)
        except Exception:
            pass  # never let diagnostics break the emergency path
        # 2) Shed: full reclaim + cache flush.
        try:
            gc.collect(2)
        except Exception:
            pass
        try:
            self._spawn_agent(CacheFlushAgent)
        except Exception:
            pass
        try:
            self._emit_alert("critical", 100.0 * rss_mb / (32.0 * 1024.0),
                             "RUNAWAY allocation - emergency shed")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # MONITORING LOGIC
    # ═══════════════════════════════════════════════════════════════════════════

    def _monitor_tick(self) -> None:
        """
        Perform one monitoring tick. Called from on_tick when cadence allows.
        This replaces the old _monitor_loop - no while/sleep, just one check.
        """
        try:
            pct = self._get_memory_percent()
            python_mb = self._get_python_memory_mb()
            level = self._get_level(pct)
            self._pressure_history.append((time.time(), pct, level, python_mb))
            self._monitor_tick_count += 1

            # Periodic status log
            if self._monitor_tick_count % 10 == 0:
                print(f"[{self.ACTOR_NAME}] tick #{self._monitor_tick_count} | RAM: {pct:.1f}% | Python: {python_mb:.0f}MB | level: {level}")

            # Level transition
            if level != self._last_level:
                print(f"[{self.ACTOR_NAME}] Level change: {self._last_level} -> {level} ({pct:.1f}%)")
                self._last_level = level

            # Actions based on level
            if level == "critical":
                # LEVEL 4: Everything
                self._do_gc("critical", generations=2)
                self._emit_alert(level, pct, "RAM critical - aggressive measures")

                # Spawn all agents
                self._spawn_agent(CacheFlushAgent)
                self._spawn_agent(MailboxPrunerAgent)
                self._spawn_agent(DequePatrolAgent)

                # Only spawn leak hunter if GC isn't working
                if self._ineffective_gc_streak >= 2:
                    self._spawn_agent(LeakHunterAgent)

            elif level == "high":
                # LEVEL 3: GC + pruning agents
                # 2026-07-16: gen2->gen1 on the hot ladder (gen2 = 836ms STW freeze;
                # the deep full collect now runs in _fast_poll's window / at critical).
                self._do_gc("high", generations=1)
                self._emit_alert(level, pct, "RAM high - spawning cleanup agents")

                self._spawn_agent(CacheFlushAgent)
                self._spawn_agent(MailboxPrunerAgent)

                # Spawn deque patrol if GC not working
                if self._ineffective_gc_streak >= 2:
                    self._spawn_agent(DequePatrolAgent)

            elif level == "elevated":
                # LEVEL 2: light GC + cache flush
                # 2026-07-16: gen2->gen0 (young-gen is ~5.7x less freezing).
                self._do_gc("elevated", generations=0)

                if self._ineffective_gc_streak >= 2:
                    self._spawn_agent(CacheFlushAgent)
                    self._emit_alert(level, pct, "GC ineffective - requesting cache flush")

            elif level == "warning":
                # LEVEL 1: Light GC (2026-07-16: gen1->gen0)
                self._do_gc("warning", generations=0)

            # else: Comfortable - just monitor

            # Clean up finished agents - ALWAYS do this regardless of level!
            old_count = len(self._active_agents)
            self._active_agents = [a for a in self._active_agents
                                   if (time.time() - a.spawn_time) < 300]  # 5 min max
            if old_count != len(self._active_agents):
                print(f"[{self.ACTOR_NAME}] [CLEANUP] Purged {old_count - len(self._active_agents)} expired agents")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [X] Monitor error: {e}")
            import traceback
            traceback.print_exc()

    def _get_memory_percent(self) -> float:
        if not HAS_PSUTIL:
            return 0.0
        try:
            return psutil.virtual_memory().percent
        except Exception:
            return 0.0

    def _get_python_memory_mb(self) -> float:
        """Get current Python process memory in MB."""
        if not HAS_PSUTIL:
            return 0.0
        try:
            return psutil.Process().memory_info().rss / (1024**2)
        except Exception:
            return 0.0

    def _get_free_gb(self) -> float:
        """Absolute AVAILABLE system RAM in GB (free + reclaimable — what a process can realistically get).
        The honest 'are we actually running low?' signal vs the % proxy. No psutil ⇒ 999 (never false-escalate)."""
        if not HAS_PSUTIL:
            return 999.0
        try:
            return psutil.virtual_memory().available / (1024**3)
        except Exception:
            return 999.0

    def _get_level(self, pct: float, free_gb: float = None) -> str:
        # FREE-RAM FLOOR (2026-06-25): when ample RAM is actually free, there's no pressure to act
        # on — regardless of how high the % looks. A big-but-live footprint isn't an emergency and
        # gc can't shrink it. Only once free RAM is genuinely low does the % ladder escalate (so a
        # real leak / sudden alloc that drives free RAM down is still caught + handled aggressively).
        if free_gb is None:
            free_gb = self._get_free_gb()
        if free_gb >= self.MIN_FREE_GB:
            return "comfortable"
        if pct >= self.THRESHOLD_CRITICAL:
            return "critical"
        elif pct >= self.THRESHOLD_HIGH:
            return "high"
        elif pct >= self.THRESHOLD_ELEVATED:
            return "elevated"
        elif pct >= self.THRESHOLD_WARNING:
            return "warning"
        return "comfortable"

    def _get_cadence(self, level: str) -> float:
        return {
            "comfortable": self.CADENCE_COMFORTABLE,
            "warning": self.CADENCE_WARNING,
            "elevated": self.CADENCE_ELEVATED,
            "high": self.CADENCE_HIGH,
            "critical": self.CADENCE_CRITICAL,
        }.get(level, self.CADENCE_COMFORTABLE)

    def _do_gc(self, reason: str, generations: int = 2) -> Optional[Dict[str, Any]]:
        # FIX 2026-03-03 (Nous): Enforce minimum interval between GC runs.
        # gc.collect(2) on a 9GB process holds the GIL for SECONDS, freezing
        # every thread (print, consciousness, speech). The old code ran it
        # every 5-10s → permanent stop-and-go terminal output.
        now = time.time()
        if (now - self._last_gc_time) < self.MIN_GC_INTERVAL:
            return None  # Too soon — skip this GC

        before = self._get_memory_percent()

        # FIX: gc.collect(N) collects generation N AND all younger ones.
        # So gc.collect(2) already does gen 0 + gen 1 + gen 2.
        # The old for-loop calling gc.collect(0), gc.collect(1), gc.collect(2)
        # did 3x the GIL-holding work for zero additional benefit.
        collected = gc.collect(generations)
        time.sleep(0)  # Explicit GIL yield after GC

        after = self._get_memory_percent()
        self._gc_count += 1
        self._last_gc_time = time.time()
        freed_pct = before - after

        result = {
            "reason": reason,
            "generations": generations,
            "objects_collected": collected,
            "before_pct": before,
            "after_pct": after,
            "freed_pct": freed_pct,
            "gc_count": self._gc_count,
            "ts": self._last_gc_time,
            "effective": freed_pct >= self.GC_EFFECTIVENESS_THRESHOLD,
        }

        self._gc_results.append(result)

        # Track effectiveness
        if result["effective"]:
            self._ineffective_gc_streak = 0
            print(f"[{self.ACTOR_NAME}] [OK] GC freed {freed_pct:.1f}% ({reason})")
        else:
            self._ineffective_gc_streak += 1
            if self._ineffective_gc_streak >= 3:
                print(f"[{self.ACTOR_NAME}] [WARN] GC ineffective {self._ineffective_gc_streak}x - need agents!")

        return result

    def _can_spawn_agent(self, agent_class: type) -> bool:
        """Check if we can spawn this agent type (cooldown + no duplicate)."""
        name = agent_class.__name__
        last_spawn = self._agent_cooldowns.get(name, 0)
        if (time.time() - last_spawn) <= self._agent_cooldown_sec:
            return False

        # FIX 2026-03-03 (Nous): Prevent duplicate agents.
        # Old code only checked cooldown, not whether the agent was still running.
        # LeakHunterAgent scans gc.get_objects() (millions of objects) under GIL —
        # with 6-8 concurrent instances this consumed 200%+ CPU and caused
        # stop-and-go terminal output by starving all other threads of GIL time.
        for existing in self._active_agents:
            if (type(existing).__name__ == name
                    and hasattr(existing, '_thread')
                    and existing._thread is not None
                    and existing._thread.is_alive()):
                return False

        return True

    def _spawn_agent(self, agent_class: type) -> Optional[MemoryAgent]:
        """Spawn a helper agent if not on cooldown and not already running."""
        if not self._can_spawn_agent(agent_class):
            return None

        # Clean up dead agents first
        self._active_agents = [
            a for a in self._active_agents
            if hasattr(a, '_thread') and a._thread is not None and a._thread.is_alive()
        ]

        agent = agent_class(self)
        self._active_agents.append(agent)
        self._agent_cooldowns[agent_class.__name__] = time.time()

        print(f"[{self.ACTOR_NAME}] [GO] Spawned {agent_class.__name__} "
              f"(active agents: {len(self._active_agents)})")

        # Run agent in thread to not block monitor
        def run_agent():
            try:
                result = agent.run()
                print(f"[{self.ACTOR_NAME}] Agent {agent_class.__name__} complete: {result.get('success')}")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Agent {agent_class.__name__} error: {e}")

        t = threading.Thread(target=run_agent, daemon=True, name=f"Agent-{agent_class.__name__}")
        agent._thread = t  # Track thread for duplicate detection
        t.start()

        return agent

    def _emit_alert(self, level: str, pct: float, message: str) -> None:
        now = time.time()
        if now - self._last_alert_time < self._alert_cooldown:
            return
        self._last_alert_time = now

        python_mb = self._get_python_memory_mb()

        alert = {
            "opcode": "MEMORY_PRESSURE_ALERT",
            "payload": {
                "level": level,
                "ram_percent": pct,
                "python_mb": python_mb,
                "message": message,
                "actor": self.ACTOR_NAME,
                "ineffective_gc_streak": self._ineffective_gc_streak,
                "agents_spawned": len(self._active_agents),
                "ts": now,
            }
        }

        level_icons = {"critical": "[CRIT]", "high": "[HIGH]", "elevated": "[WARN]", "warning": "[INFO]"}
        icon = level_icons.get(level, "")
        print(f"[{self.ACTOR_NAME}] {icon} {level.upper()}: {pct:.1f}% RAM, Python {python_mb:.0f}MB - {message}")

        # Publish via fabric (Fairy base provides self.post)
        try:
            self.post.publish("telemetry", alert)
            self.post.publish("tracer", alert)
            if level == "critical":
                self.post.publish("executive", alert)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════

    def force_gc(self, reason: str = "manual") -> Dict[str, Any]:
        # Bypass MIN_GC_INTERVAL for explicit manual requests
        self._last_gc_time = 0.0
        result = self._do_gc(reason, generations=2)
        return result or {"skipped": True, "reason": "unexpected"}

    def get_status(self) -> Dict[str, Any]:
        pct = self._get_memory_percent()
        python_mb = self._get_python_memory_mb()
        return {
            "running": self.is_running,
            "ram_percent": pct,
            "python_mb": python_mb,
            "level": self._get_level(pct),
            "gc_count": self._gc_count,
            "ineffective_gc_streak": self._ineffective_gc_streak,
            "active_agents": len(self._active_agents),
            "agent_names": [type(a).__name__ for a in self._active_agents],
            "last_gc_time": self._last_gc_time,
            "history_len": len(self._pressure_history),
        }

    def get_trend(self) -> Dict[str, Any]:
        if len(self._pressure_history) < 5:
            return {"trend": "insufficient_data"}

        recent = list(self._pressure_history)[-20:]
        values = [p[1] for p in recent]
        avg = sum(values) / len(values)

        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if second_avg > first_avg + 3:
            trend = "rising"
        elif second_avg < first_avg - 3:
            trend = "falling"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "current": values[-1] if values else 0,
            "average": avg,
            "min": min(values),
            "max": max(values),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON + BOOT
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[MemoryPressureFairy] = None


def get_memory_pressure_fairy(fabric=None) -> MemoryPressureFairy:
    """Get or create the singleton MemoryPressureFairy instance."""
    global _instance
    if _instance is None:
        _instance = MemoryPressureFairy(fabric=fabric)
    return _instance


def start_memory_pressure_monitor(fabric=None) -> MemoryPressureFairy:
    """Get the fairy and boot it."""
    fairy = get_memory_pressure_fairy(fabric)
    if not fairy.is_running:
        fairy.boot()
    return fairy


def force_gc(reason: str = "manual") -> Dict[str, Any]:
    """Force a garbage collection via the fairy."""
    fairy = get_memory_pressure_fairy()
    return fairy.force_gc(reason)


def on_boot(fabric=None) -> MemoryPressureFairy:
    """Boot function for orchestrator compatibility."""
    return start_memory_pressure_monitor(fabric)


if __name__ == "__main__":
    print("Testing MemoryPressureFairy v0.3.0...")
    fairy = MemoryPressureFairy()
    fairy.boot()
    print(f"Status: {fairy.get_status()}")
    result = fairy.force_gc("test")
    print(f"GC result: {result}")

    # Test agent spawning
    agent = CacheFlushAgent(fairy)
    print(f"Agent report: {agent.report()}")

    fairy.shutdown()
