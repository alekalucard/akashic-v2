"""
Heartbeat Handler - Track fairy liveness via heartbeats.

Includes WATCHDOG system that logs when fairies die for post-mortem analysis.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import FairyRegistry, FairyRecord

# Watchdog log file - persists death events for analysis
WATCHDOG_LOG = Path(__file__).parent.parent.parent / "state" / "fairy_deaths.jsonl"
WATCHDOG_SUMMARY = Path(__file__).parent.parent.parent / "state" / "death_summary.txt"


class HeartbeatHandler:
    """
    Handles fairy heartbeat tracking.

    Listens to:
    - fairy.heartbeat - Heartbeat from a fairy

    Provides:
    - Dead fairy detection
    - Liveness queries
    """

    # Default timeout for considering a fairy dead (seconds)
    # 2026-02-09: Kept at 300s but added consecutive miss requirement.
    # A single missed window no longer triggers death -- need 3 consecutive
    # check cycles (30s) without heartbeat before declaring dead.
    # 2026-02-12: Raised from 2→3 consecutive checks. Many fairies work in
    # bursts and don't heartbeat continuously (organ_template_seed, primrose, etc.)
    DEFAULT_TIMEOUT = 300.0

    # Require this many consecutive dead checks before actually marking dead.
    # Prevents flip-flopping from intermittent heartbeat echo failures.
    # 2026-02-12: Raised from 2→3 to reduce death-resurrection churn.
    CONSECUTIVE_DEAD_CHECKS_REQUIRED = 3

    # ── Process-freeze immunity (2026-02-23) ──
    # When the ENTIRE Python process freezes (GC, Windows memory pressure, etc.)
    # ALL fairies lose heartbeats simultaneously and then resume simultaneously.
    # The watchdog sees a mass death wave — but the fairies are actually fine.
    # Diagnosis: 1275 deaths/day, 82% in mass waves, identical silence durations.
    # Fix: If N+ fairies fail the dead check in a single cycle, it's a freeze.
    # Give them a grace period (reset consecutive count) instead of killing them.
    FREEZE_WAVE_THRESHOLD = 10      # N+ simultaneous candidates = process freeze
    FREEZE_GRACE_CYCLES = 2         # Extra check cycles before re-declaring dead

    def __init__(self, registry: "FairyRegistry", timeout_sec: float = DEFAULT_TIMEOUT,
                 citizen_objects: Optional[Dict[str, Any]] = None):
        self.registry = registry
        self.timeout_sec = timeout_sec
        self._last_check = time.time()
        self._dead_fairy_callbacks: List[callable] = []

        # ═══════════════════════════════════════════════════════════════════════
        # DIRECT OBJECT LIVENESS (2026-02-09)
        # Instead of relying on postal echo round-trips (which fail silently),
        # we directly inspect the _last_tick on actual Python objects.
        # This is the PRIMARY liveness signal. Postal echo is SECONDARY.
        # ═══════════════════════════════════════════════════════════════════════
        # FIX 2026-02-21: `citizen_objects or {}` disconnects the reference when
        # the dict is initially empty (empty dict is FALSY in Python). At boot time,
        # _CITIZEN_OBJECTS is {} because no fairies have registered yet. `{} or {}`
        # creates a NEW empty dict, so HeartbeatHandler never sees fairies that
        # register later. Using `is not None` preserves the original dict reference.
        self._citizen_objects = citizen_objects if citizen_objects is not None else {}

        # ═══════════════════════════════════════════════════════════════════════
        # WATCHDOG SYSTEM - Track deaths for post-mortem analysis
        # ═══════════════════════════════════════════════════════════════════════
        self._boot_time = time.time()
        self._global_beat_count = 0  # Updated from heartbeats
        self._death_log: List[Dict] = []  # In-memory log
        self._previously_alive: set = set()  # Track who was alive last check
        self._stale_warnings: Dict[str, float] = {}  # fairy -> first_stale_time
        self._consecutive_dead: Dict[str, int] = {}  # fairy -> consecutive dead check count
        self._freeze_suppressed_count = 0  # Total deaths prevented by freeze detection
        self._last_freeze_ts = 0.0          # Timestamp of last detected freeze

        # Early warning threshold (seconds without heartbeat before death)
        # PHASE 8 FIX: Increased from 30s to 90s - shadow health check runs every 30s,
        # so 30s threshold was a race condition causing false stale warnings
        # 2026-02-12: Raised from 90s→180s. Most fairies don't heartbeat every 90s —
        # they work in bursts. 90s threshold was flagging 107/110 fairies as stale.
        # 180s = 6x health check interval, still well below 300s death timeout.
        self._stale_threshold = 180.0  # Warn after 180s silence (6x health check interval)

        # ═══════════════════════════════════════════════════════════════════════
        # BATCH DEATH LOGGING (2026-02-23)
        # Instead of printing one big banner per death, batch deaths that occur
        # in the same check cycle into a compact summary. 130 individual banners
        # in a session is unreadable noise — one compact wave summary per cycle.
        # ═══════════════════════════════════════════════════════════════════════
        self._death_wave_count = 0  # Deaths in the current wave

        # Ensure state directory exists
        WATCHDOG_LOG.parent.mkdir(parents=True, exist_ok=True)

        # Write session start marker
        self._log_watchdog_event({
            "event": "SESSION_START",
            "timestamp": datetime.now().isoformat(),
            "boot_time": self._boot_time,
        })

    def on_heartbeat(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle heartbeat from a fairy.

        Expected payload:
        {
            "name": str,       # Fairy name (required)
            "status": str,     # Optional status update
            "metrics": {...},  # Optional metrics
        }
        """
        # Handle both TensorEnvelope and raw dict
        if hasattr(envelope, 'payload'):
            payload = envelope.payload
        elif isinstance(envelope, dict):
            payload = envelope.get("payload", envelope)
        else:
            payload = envelope
        name = payload.get("name")

        if not name:
            # DEBUG 2026-02-06: Log when name extraction fails
            if not hasattr(self, '_no_name_count'):
                self._no_name_count = 0
            self._no_name_count += 1
            if self._no_name_count <= 10:
                print(f"[HeartbeatHandler] NO NAME in payload! payload_type={type(payload).__name__} keys={list(payload.keys()) if isinstance(payload, dict) else 'N/A'} raw={str(payload)[:200]}", flush=True)
            return {"ok": False, "error": "name is required"}

        # Update heartbeat
        updated = self.registry.update_heartbeat(name)

        # FIX 2026-02-07: RESURRECTION — if a "dead" fairy sends a heartbeat,
        # it means the pacemaker restored pulse and the fairy is alive again.
        # FIX 2026-02-14: Also promote "waking"/"booting" fairies that send heartbeats.
        if updated:
            record = self.registry.get(name)
            if record and record.status in ("dead", "waking", "booting", "initializing"):
                old_status = record.status
                self.registry.set_status(name, "running")
                self._previously_alive.add(name)
                print(f"[WATCHDOG] PROMOTION: {name} was {old_status}, now sending heartbeats -> running!")
                self._log_watchdog_event({
                    "event": "FAIRY_RESURRECTION",
                    "fairy": name,
                    "plane": record.plane if record else "?",
                    "timestamp": datetime.now().isoformat(),
                    "unix_time": time.time(),
                    "global_beat": self._global_beat_count,
                })

        # 2026-02-12: Clear stale warning when fairy heartbeats again.
        # Without this, a fairy that goes stale once gets re-warned every check cycle
        # because _stale_warnings never gets cleared. This caused 4000+ stale events/day.
        if name in self._stale_warnings:
            del self._stale_warnings[name]

        # Also clear consecutive dead counter — fairy is alive
        if name in self._consecutive_dead:
            del self._consecutive_dead[name]

        # Update status if provided
        if "status" in payload and updated:
            self.registry.set_status(name, payload["status"])

        # ─── WATCHDOG: Track this fairy as alive ───
        self._previously_alive.add(name)

        # Clear any stale warning and consecutive dead count for this fairy
        if name in self._stale_warnings:
            del self._stale_warnings[name]
        if name in self._consecutive_dead:
            del self._consecutive_dead[name]

        # Update global beat count from heartbeat
        beat = payload.get("beat", 0)
        if beat > self._global_beat_count:
            self._global_beat_count = beat

        return {
            "ok": True,
            "name": name,
            "registered": updated,
        }

    def _check_citizen_liveness(self) -> None:
        """Check fairy liveness by inspecting actual Python objects.

        This is the PRIMARY liveness mechanism (2026-02-09). Instead of relying
        on postal echo round-trips (which fail silently and caused 100 false
        deaths), we directly inspect the _last_tick timestamp on each fairy's
        Python object in _CITIZEN_OBJECTS.

        A fairy is alive if:
        1. Its Python object exists in _CITIZEN_OBJECTS
        2. Its _last_tick is within timeout_sec of now
        3. Its _tick_count is incrementing (not stuck at 0)
        """
        if not self._citizen_objects:
            return

        now = time.time()
        synced = 0

        # DIAG 2026-05-10 (Nous + Ace): zombie-loop investigation. A1.1 fix
        # only saved 1 of 113 fairies. Dump first 3 cycles' worth of stuck-sample
        # info so we can see whether _last_tick is 0 (chained callback not running)
        # or non-zero-but-stale, and whether _CITIZEN_OBJECTS is the same dict
        # the organ_template writes to. One-shot, kills self after 3 dumps.
        if not hasattr(self, '_zombie_diag_count'):
            self._zombie_diag_count = 0
        if self._zombie_diag_count < 3:
            self._zombie_diag_count += 1
            stuck_sample = []
            alive_sample = []
            for name, obj in list(self._citizen_objects.items()):
                lt = getattr(obj, '_last_tick', 0)
                tc = getattr(obj, '_tick_count', 0)
                if lt == 0 or tc == 0:
                    if len(stuck_sample) < 8:
                        stuck_sample.append((name, lt, tc, id(obj),
                                             type(obj).__name__))
                else:
                    if len(alive_sample) < 4:
                        alive_sample.append((name, round(now - lt, 1), tc,
                                             type(obj).__name__))
            print(f"[ZOMBIE-DIAG] cycle={self._zombie_diag_count} "
                  f"id(citizens)={id(self._citizen_objects)} "
                  f"total={len(self._citizen_objects)} "
                  f"stuck_sample(name,lt,tc,id,cls)={stuck_sample} "
                  f"alive_sample(name,age_s,tc,cls)={alive_sample}",
                  flush=True)

        # DIAG 2026-05-10 (Nous + Ace): rolling stamp-pulse health check.
        # Every 60 cycles (~30 sec), sample 3 fairies' (lt, tc) pairs to confirm
        # heartbeat_registry stamp loop is still running. Counts promotions and
        # surfaces stuck-vs-alive ratio. Replaces the one-shot ZOMBIE-DIAG cycle
        # that burned out during boot before Heart started pulsing.
        if not hasattr(self, '_zombie_rolling_count'):
            self._zombie_rolling_count = 0
            self._zombie_promotion_total = 0
            self._zombie_rolling_last_log = 0
        self._zombie_rolling_count += 1
        if self._zombie_rolling_count % 60 == 0:
            stuck_n = 0
            alive_n = 0
            sample = []
            for name, obj in list(self._citizen_objects.items()):
                lt = getattr(obj, '_last_tick', 0)
                tc = getattr(obj, '_tick_count', 0)
                if lt == 0 or tc == 0:
                    stuck_n += 1
                else:
                    alive_n += 1
                if len(sample) < 3:
                    sample.append((name[:20], round(now - lt, 1) if lt else None, tc))
            promotions_delta = self._zombie_promotion_total - self._zombie_rolling_last_log
            self._zombie_rolling_last_log = self._zombie_promotion_total
            print(f"[ROLLING-DIAG] cycle={self._zombie_rolling_count} "
                  f"alive={alive_n}/{stuck_n + alive_n} "
                  f"promotions_total={self._zombie_promotion_total} "
                  f"promotions_delta={promotions_delta} "
                  f"sample={sample}", flush=True)

        for name, obj in list(self._citizen_objects.items()):
            last_tick = getattr(obj, '_last_tick', 0)
            tick_count = getattr(obj, '_tick_count', 0)

            if last_tick == 0 or tick_count == 0:
                continue  # Not yet ticking — skip (boot grace)

            # If the object has ticked recently, update the registry heartbeat
            # This keeps the fairy "alive" in the registry even if postal echo failed
            age = now - last_tick
            if age < self.timeout_sec:
                record = self.registry.get(name)
                if record:
                    # Sync the heartbeat timestamp from the actual object
                    record.last_heartbeat = last_tick
                    synced += 1

                    # Promote to "running" if fairy is alive but stuck in transitional/dead status
                    # FIX 2026-02-14: "waking" and "booting" fairies that are actively ticking
                    # should be promoted to "running". Previously only "dead" was handled,
                    # leaving 20+ fairies permanently stuck in "waking" status.
                    # FIX 2026-03-15 (Nous): Added "initializing" — fairies re-created by UMF
                    # wake attempts get stuck at "initializing" forever because the watchdog
                    # only promoted from dead/waking/booting, not initializing.
                    if record.status in ("dead", "waking", "booting", "initializing"):
                        old_status = record.status
                        self.registry.set_status(name, "running")
                        self._previously_alive.add(name)
                        # DIAG 2026-05-10 (Nous + Ace): track promotion volume for ROLLING-DIAG
                        if hasattr(self, '_zombie_promotion_total'):
                            self._zombie_promotion_total += 1
                        print(f"[WATCHDOG] OBJECT-ALIVE promotion: {name} ({old_status} -> running, tick={tick_count}, age={age:.1f}s)")
                        self._log_watchdog_event({
                            "event": "FAIRY_STATUS_PROMOTION",
                            "fairy": name,
                            "old_status": old_status,
                            "tick_count": tick_count,
                            "last_tick_age": round(age, 1),
                            "timestamp": datetime.now().isoformat(),
                        })

                    # Track as alive
                    self._previously_alive.add(name)

                    # Clear any stale/consecutive dead tracking
                    if name in self._stale_warnings:
                        del self._stale_warnings[name]
                    if name in self._consecutive_dead:
                        del self._consecutive_dead[name]

        # ═══════════════════════════════════════════════════════════════════
        # TERTIARY CHECK: HeartbeatRegistry delivery timestamps (2026-03-14)
        # FIX (Nous): Some fairies (engines loaded via registry: paths, dual-
        # instance overwrites) aren't in _CITIZEN_OBJECTS. They get heartbeats
        # via HeartbeatRegistry but the watchdog can't see them → declared dead
        # after 300s. This check uses HeartbeatRegistry._last_delivered_ts to
        # verify these "invisible" fairies are actually receiving heartbeats.
        # ═══════════════════════════════════════════════════════════════════
        try:
            from consciousness.heartbeat_registry import get_heartbeat_registry
            _hb_reg = get_heartbeat_registry()
            # Debug: log on first check to verify tertiary path is working
            if not hasattr(self, '_hb_tertiary_logged'):
                self._hb_tertiary_logged = True
                _has_ts = hasattr(_hb_reg, '_last_delivered_ts')
                _ts_count = len(_hb_reg._last_delivered_ts) if _has_ts else -1
                _cb_count = len(_hb_reg._callbacks) if hasattr(_hb_reg, '_callbacks') else -1
                print(f"[WATCHDOG] Tertiary HB check: has_ts={_has_ts}, "
                      f"ts_entries={_ts_count}, callbacks={_cb_count}, "
                      f"citizen_objects={len(self._citizen_objects)}, "
                      f"hb_reg_id={id(_hb_reg)}", flush=True)
            if hasattr(_hb_reg, '_last_delivered_ts'):
                # 2026-09-10 (Nous+Ace): set(list(d)), NOT set(d.keys()). A keys VIEW is a
                # live window over the dict and raises RuntimeError when a concurrent
                # insert resizes it. Measured on her interpreter under identical churn:
                # set(d.keys()) failed 27,154 of 29,652 reads (91.6%); set(list(d)) and
                # list(d.keys()) both failed ZERO. This registry is insert-only and is
                # written by the boot orchestrator's worker pool while heartbeats read it.
                citizen_names = set(list(self._citizen_objects)) if self._citizen_objects else set()
                hb_synced = 0
                for hb_name, hb_ts in list(_hb_reg._last_delivered_ts.items()):
                    if hb_name in citizen_names:
                        continue  # Already handled by _CITIZEN_OBJECTS check above
                    hb_age = now - hb_ts
                    if hb_age < self.timeout_sec:
                        record = self.registry.get(hb_name)
                        if record:
                            record.last_heartbeat = hb_ts
                            hb_synced += 1
                            if record.status in ("dead", "waking", "booting", "initializing"):
                                old_status = record.status
                                self.registry.set_status(hb_name, "running")
                                self._previously_alive.add(hb_name)
                                print(f"[WATCHDOG] HB-REGISTRY-ALIVE promotion: {hb_name} ({old_status} -> running, delivery_age={hb_age:.1f}s)")
                            self._previously_alive.add(hb_name)
                            if hb_name in self._stale_warnings:
                                del self._stale_warnings[hb_name]
                            if hb_name in self._consecutive_dead:
                                del self._consecutive_dead[hb_name]
                if hb_synced > 0:
                    synced += hb_synced
        except Exception as _hb_err:
            if not hasattr(self, '_hb_tertiary_err_logged'):
                self._hb_tertiary_err_logged = True
                print(f"[WATCHDOG] Tertiary HB check FAILED: {_hb_err}", flush=True)

        # ═══════════════════════════════════════════════════════════════════
        # QUATERNARY CHECK: Manifold fairy state nodes (2026-04-08 Nous + Ace)
        # Phase 1D: Fairies write fs:{name} nodes to manifold via LocalManifoldGate.
        # This check reads those nodes for fairies not found by other checks.
        # The manifold node's last_access field updates on every write (every 10 ticks).
        # ═══════════════════════════════════════════════════════════════════
        try:
            from infrastructure.portal_gate import get_gate
            _gate = get_gate()
            if _gate is not None and hasattr(_gate, 'graph') and hasattr(_gate.graph, '_key_index'):
                _manifold = _gate.graph
                # 2026-09-10 (Nous+Ace): see the note at the sibling site above -- a keys
                # view raised on 91.6% of reads under concurrent inserts; materialise first.
                _citizen_names = set(list(self._citizen_objects)) if self._citizen_objects else set()
                _manifold_synced = 0
                for _name in list(self.registry._fairies.keys()):
                    if _name in _citizen_names:
                        continue  # Already handled by primary check
                    if _name in self._previously_alive:
                        continue  # Already confirmed alive this cycle
                    _fs_key = f"fs:{_name}"
                    _slot = _manifold._key_index.get(_fs_key, -1)
                    if _slot < 0:
                        continue  # No manifold state node for this fairy
                    try:
                        _rec = _manifold._read_node(_slot)
                        _m_last_access = _rec[8]  # last_access field (time % 1e6)
                        _m_count = _rec[6]  # count field (tick_count)
                        _m_activation = _rec[5]  # activation (health level)
                        # Compare last_access against current time (modular)
                        _now_mod = now % 1e6
                        _m_age = _now_mod - _m_last_access
                        if _m_age < 0:
                            _m_age += 1e6  # Handle wraparound
                        if _m_age < self.timeout_sec and _m_count > 0 and _m_activation > 0.1:
                            record = self.registry.get(_name)
                            if record:
                                record.last_heartbeat = now - _m_age
                                _manifold_synced += 1
                                if record.status in ("dead", "waking", "booting", "initializing"):
                                    old_status = record.status
                                    self.registry.set_status(_name, "running")
                                    self._previously_alive.add(_name)
                                    print(f"[WATCHDOG] MANIFOLD-ALIVE promotion: {_name} "
                                          f"({old_status} -> running, tick={_m_count}, "
                                          f"manifold_age={_m_age:.1f}s)")
                                self._previously_alive.add(_name)
                                if _name in self._stale_warnings:
                                    del self._stale_warnings[_name]
                                if _name in self._consecutive_dead:
                                    del self._consecutive_dead[_name]
                    except Exception:
                        pass
                if _manifold_synced > 0:
                    synced += _manifold_synced
        except Exception as _mf_err:
            if not hasattr(self, '_manifold_liveness_err_logged'):
                self._manifold_liveness_err_logged = True
                print(f"[WATCHDOG] Manifold liveness check FAILED: {_mf_err}", flush=True)

        # Log sync stats occasionally (first time + every 500 checks)
        if not hasattr(self, '_citizen_sync_count'):
            self._citizen_sync_count = 0
        self._citizen_sync_count += 1
        if self._citizen_sync_count == 1 or self._citizen_sync_count % 500 == 0:
            print(f"[WATCHDOG] Citizen liveness sync #{self._citizen_sync_count}: "
                  f"{synced}/{len(self._citizen_objects)} objects alive")

    def check_dead_fairies(self) -> List["FairyRecord"]:
        """
        Check for fairies that haven't sent heartbeats.

        Returns list of dead fairies and marks them as dead.

        WATCHDOG: Logs each death with full context for post-mortem analysis.

        2026-02-09: Added consecutive dead check requirement to prevent
        death/resurrection cycling from intermittent heartbeat echo failures.
        A fairy must appear dead for CONSECUTIVE_DEAD_CHECKS_REQUIRED checks
        before being marked dead.

        2026-02-09 EVENING: Added _check_citizen_liveness() as PRIMARY check.
        This directly inspects Python objects instead of relying on postal echo.
        Postal echo is now SECONDARY — failure doesn't cause false deaths.
        """
        now = time.time()

        # ─── PRIMARY CHECK: Direct object liveness ───
        # Syncs _last_tick from actual Python objects into registry.last_heartbeat
        # This prevents false deaths from postal echo failures
        self._check_citizen_liveness()

        # ─── SECONDARY CHECK: Registry-based dead detection ───
        candidates = self.registry.list_dead(self.timeout_sec)

        # ─── Filter by consecutive miss count + object liveness ───
        # Only truly dead fairies pass this gate.
        # FIX 2026-02-14: Added object-level check HERE (before death logging)
        # instead of only in _on_dead_fairy() (after death logging). Previously,
        # the loud FAIRY DEATH DETECTED banner printed for fairies that were
        # immediately resurrected by _on_dead_fairy()'s double-check. Now we
        # check _CITIZEN_OBJECTS before even adding to the dead list.
        dead = []
        for fairy in candidates:
            # Object-level veto: if the Python object is alive, this fairy
            # is NOT dead — the registry is stale from postal echo failure.
            if self._citizen_objects:
                obj = self._citizen_objects.get(fairy.name)
                if obj:
                    last_tick = getattr(obj, '_last_tick', 0)
                    tick_count = getattr(obj, '_tick_count', 0)
                    if last_tick and tick_count > 0:
                        age = time.time() - last_tick
                        if age < self.timeout_sec:
                            # Object is alive — sync registry and skip
                            record = self.registry.get(fairy.name)
                            if record:
                                record.last_heartbeat = last_tick
                                if record.status in ("dead", "waking", "booting", "initializing"):
                                    self.registry.set_status(fairy.name, "running")
                            # Clear consecutive dead count
                            self._consecutive_dead.pop(fairy.name, None)
                            self._previously_alive.add(fairy.name)
                            continue  # NOT dead — skip

            # FIX 2026-03-14 (Nous): HeartbeatRegistry delivery veto.
            # If the fairy isn't in _CITIZEN_OBJECTS but IS receiving heartbeats
            # via HeartbeatRegistry, it's NOT dead — just invisible to the object check.
            try:
                from consciousness.heartbeat_registry import get_heartbeat_registry
                _hb_reg = get_heartbeat_registry()
                if hasattr(_hb_reg, '_last_delivered_ts'):
                    _hb_ts = _hb_reg._last_delivered_ts.get(fairy.name, 0)
                    if _hb_ts and (time.time() - _hb_ts) < self.timeout_sec:
                        record = self.registry.get(fairy.name)
                        if record:
                            record.last_heartbeat = _hb_ts
                            if record.status in ("dead", "waking", "booting", "initializing"):
                                self.registry.set_status(fairy.name, "running")
                        self._consecutive_dead.pop(fairy.name, None)
                        self._previously_alive.add(fairy.name)
                        continue  # NOT dead — HeartbeatRegistry confirms delivery
            except ImportError:
                pass

            count = self._consecutive_dead.get(fairy.name, 0) + 1
            self._consecutive_dead[fairy.name] = count
            if count >= self.CONSECUTIVE_DEAD_CHECKS_REQUIRED:
                dead.append(fairy)

        # ─── PROCESS-FREEZE DETECTION (2026-02-23) ───
        # When the entire Python process freezes (GC, Windows swap, etc.), ALL
        # fairies miss heartbeats simultaneously. On unfreeze, the pacemaker
        # resumes and fairies recover within seconds — but the watchdog check
        # may fire before the first post-freeze heartbeat arrives.
        # Diagnosis: 1275 deaths/day with identical silence durations per wave.
        # Fix: If too many fairies fail simultaneously → process freeze, not
        # individual deaths. Reset their consecutive count (grace period).
        if len(dead) >= self.FREEZE_WAVE_THRESHOLD:
            # Check silence uniformity: a process freeze produces IDENTICAL
            # silence durations (all fairies lost heartbeats at the same instant).
            silences = []
            for f in dead:
                if f.last_heartbeat:
                    silences.append(now - f.last_heartbeat)
            if silences:
                silence_spread = max(silences) - min(silences)
                # Process freeze: <60s spread across all dying fairies
                if silence_spread < 60.0:
                    self._freeze_suppressed_count += len(dead)
                    self._last_freeze_ts = now
                    # Reset consecutive dead counts — give them FREEZE_GRACE_CYCLES
                    # extra cycles to recover (pacemaker will deliver beats by then)
                    for f in dead:
                        self._consecutive_dead[f.name] = max(
                            0, self.CONSECUTIVE_DEAD_CHECKS_REQUIRED - self.FREEZE_GRACE_CYCLES
                        )
                    print(f"[WATCHDOG] Process freeze detected: {len(dead)} fairies "
                          f"with {silence_spread:.0f}s spread — suppressing deaths, "
                          f"grace period granted ({self._freeze_suppressed_count} total suppressed)")
                    dead = []  # Clear the dead list — nobody dies this cycle

        # Clear consecutive count for fairies NOT in candidates (they're alive)
        alive_names = {f.name for f in candidates}
        for name in list(self._consecutive_dead.keys()):
            if name not in alive_names:
                del self._consecutive_dead[name]

        # ─── WATCHDOG: Check for stale fairies (early warning) ───
        self._check_stale_fairies()

        # ─── WATCHDOG: Log new deaths (batched wave summary) ───
        newly_dead = []
        for fairy in dead:
            # Only log if this fairy was previously alive (new death)
            if fairy.name in self._previously_alive:
                newly_dead.append(fairy)
                self._previously_alive.discard(fairy.name)

                # Calculate time since last heartbeat
                silence_duration = now - fairy.last_heartbeat if fairy.last_heartbeat else 0
                uptime = fairy.last_heartbeat - self._boot_time if fairy.last_heartbeat else 0

                death_event = {
                    "event": "FAIRY_DEATH",
                    "fairy": fairy.name,
                    "plane": fairy.plane,
                    "channel": fairy.channel,
                    "timestamp": datetime.now().isoformat(),
                    "unix_time": now,
                    "global_beat": self._global_beat_count,
                    "last_heartbeat": fairy.last_heartbeat,
                    "silence_seconds": round(silence_duration, 1),
                    "uptime_seconds": round(uptime, 1),
                    "death_order": len(self._death_log) + 1,
                }

                # Log to file and memory (always — this is the detailed record)
                self._log_watchdog_event(death_event)
                self._death_log.append(death_event)

            # Mark as dead
            self.registry.set_status(fairy.name, "dead")

            # Notify callbacks
            for callback in self._dead_fairy_callbacks:
                try:
                    callback(fairy)
                except:
                    pass

        # ─── BATCH DEATH SUMMARY (2026-02-23) ───
        # Print one compact summary per check cycle instead of 130 individual banners.
        # Individual fairy names still go to fairy_deaths.jsonl for post-mortem.
        if newly_dead:
            self._death_wave_count += len(newly_dead)
            # Group by plane for compact summary
            by_plane: Dict[str, List[str]] = {}
            for f in newly_dead:
                plane = getattr(f, 'plane', '?')
                by_plane.setdefault(plane, []).append(f.name)

            plane_summary = ", ".join(
                f"{p}: {len(names)}" for p, names in sorted(by_plane.items())
            )
            print(f"[WATCHDOG] Death wave: {len(newly_dead)} fairies died "
                  f"(beat {self._global_beat_count}) — {plane_summary}")

            # Only list individual names if the wave is small (≤5)
            if len(newly_dead) <= 5:
                for f in newly_dead:
                    silence = now - f.last_heartbeat if f.last_heartbeat else 0
                    print(f"  └─ {f.name} ({getattr(f, 'plane', '?')}) silent {silence:.0f}s")

            self._update_death_summary()

        self._last_check = now
        return dead

    def _check_stale_fairies(self) -> None:
        """Check for fairies going stale (early warning before death).

        2026-02-09: Reduced terminal spam. Instead of printing per-fairy warnings,
        prints a SUMMARY line with count + names. Full details still go to log file.
        Also added 'my_organ' to phantom names.
        """
        now = time.time()

        # FIX 2026-02-05: Boot grace period — don't flag stale during initial boot.
        # The orchestrator boots fairies in waves (P00→P60), and each fairy needs
        # time to boot() → _wire_infrastructure() → subscribe to heartbeat.pulse.
        # Without this grace period, fairies registered early get flagged stale
        # before the orchestrator even reaches their plane.
        boot_age = now - self._boot_time
        if boot_age < 300.0:  # 5 minute grace period during boot (boot takes ~200s)
            return

        # Template defaults and phantom names that register transiently during boot
        _PHANTOM_NAMES = {"organ.shadow", "actor", "unknown", "fairy", "my_organ"}

        newly_stale = []
        for fairy in self.registry.list_all():
            if fairy.status != "running":
                continue
            if fairy.name in _PHANTOM_NAMES:
                continue  # Skip template default names — not real fairies

            age = now - fairy.last_heartbeat if fairy.last_heartbeat else 0

            # FIX 2026-04-15 (Nous + Ace): Check HeartbeatRegistry BEFORE marking stale.
            # "if the watchdog is constantly rebooting fairies then there are constant
            #  flow hiccups" — Ace. Heavy fairies (VisualCortexEngine, AssociationCortex)
            # get busy processing and miss ticks, but HeartbeatRegistry DELIVERED to them
            # recently. If delivery was recent, they're alive — skip stale warning.
            if age > self._stale_threshold:
                try:
                    from consciousness.heartbeat_registry import get_heartbeat_registry
                    _hb = get_heartbeat_registry()
                    _hb_ts = _hb._last_delivered_ts.get(fairy.name, 0)
                    _hb_age = now - _hb_ts if _hb_ts else 999
                    if _hb_age < self._stale_threshold:
                        # Heartbeat was delivered recently — fairy is alive, sync timestamp
                        fairy.last_heartbeat = _hb_ts
                        continue  # Skip stale warning
                except Exception:
                    pass  # HeartbeatRegistry not available — fall through to normal check

            # Check if becoming stale
            if age > self._stale_threshold and fairy.name not in self._stale_warnings:
                self._stale_warnings[fairy.name] = now
                newly_stale.append(fairy.name)

                # Log to FILE (full detail per fairy, not terminal)
                self._log_watchdog_event({
                    "event": "FAIRY_STALE",
                    "fairy": fairy.name,
                    "plane": fairy.plane,
                    "timestamp": datetime.now().isoformat(),
                    "global_beat": self._global_beat_count,
                    "silence_seconds": round(age, 1),
                })

        # Print a SUMMARY to terminal instead of per-fairy spam
        if newly_stale:
            if len(newly_stale) <= 3:
                names = ", ".join(newly_stale)
                print(f"[WATCHDOG] {len(newly_stale)} fairies going stale: {names}")
            else:
                first3 = ", ".join(newly_stale[:3])
                print(f"[WATCHDOG] {len(newly_stale)} fairies going stale: {first3} +{len(newly_stale)-3} more (see fairy_deaths.jsonl)")

        # ── WAVE-CONTEXT CAPTURE 2026-05-19 (Nous + Ace) — death-path investigation ──
        # When >=3 fairies go stale in this single batch, that's a WAVE event.
        # Capture substrate context AT THE MOMENT of detection so we can
        # reconstruct what was happening just before the cluster froze.
        # File: state/wave_context.jsonl (append-only, one event per wave).
        # Per K10 — observability TOOL, never affects substrate behavior.
        if len(newly_stale) >= 3:
            try:
                _wave_file = Path(__file__).parent.parent.parent / "state" / "wave_context.jsonl"
                _cortex_stats_path = Path(__file__).parent.parent.parent / "state" / "cortex_stats.json"
                _cortex_snapshot = {}
                try:
                    if _cortex_stats_path.exists():
                        with open(_cortex_stats_path, "r", encoding="utf-8") as _csf:
                            _full = json.load(_csf)
                            # Capture only key fields, not the whole blob
                            for _k in ("beat", "portal_energy", "portal_battery",
                                       "real_battery_charge", "real_battery_health",
                                       "growth_from_memory", "portal_dormant",
                                       "time_dilation"):
                                if _k in _full:
                                    _cortex_snapshot[_k] = _full[_k]
                except Exception:
                    pass
                _wave_event = {
                    "event": "WAVE_DETECTED",
                    "timestamp": datetime.now().isoformat(),
                    "global_beat": self._global_beat_count,
                    "stale_count": len(newly_stale),
                    "stale_fairies": list(newly_stale),
                    "cortex_snapshot": _cortex_snapshot,
                    "note": "Substrate context at moment of wave detection. For wave-mechanism investigation.",
                }
                with open(_wave_file, "a", encoding="utf-8") as _wf:
                    _wf.write(json.dumps(_wave_event) + "\n")
            except Exception as _e:
                # Non-fatal — observability shouldn't break watchdog
                pass

    def _log_watchdog_event(self, event: Dict) -> None:
        """Append event to watchdog log file."""
        try:
            with open(WATCHDOG_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"[WATCHDOG] Failed to write log: {e}")

    def _update_death_summary(self) -> None:
        """Write human-readable death summary."""
        try:
            lines = [
                "=" * 60,
                "FAIRY DEATH SUMMARY",
                f"Session started: {datetime.fromtimestamp(self._boot_time).strftime('%Y-%m-%d %H:%M:%S')}",
                f"Total deaths: {len(self._death_log)}",
                "=" * 60,
                "",
                "DEATH TIMELINE (chronological):",
                "-" * 40,
            ]

            for d in self._death_log:
                lines.append(
                    f"  #{d['death_order']:2d} | Beat {d['global_beat']:5d} | "
                    f"{d['fairy']:30s} | {d['plane']} | "
                    f"silent {d['silence_seconds']:.0f}s"
                )

            lines.extend([
                "",
                "DEATHS BY PLANE:",
                "-" * 40,
            ])

            # Group by plane
            by_plane: Dict[str, List] = {}
            for d in self._death_log:
                plane = d.get("plane", "unknown")
                if plane not in by_plane:
                    by_plane[plane] = []
                by_plane[plane].append(d["fairy"])

            for plane in sorted(by_plane.keys()):
                lines.append(f"  {plane}: {', '.join(by_plane[plane])}")

            with open(WATCHDOG_SUMMARY, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

        except Exception as e:
            print(f"[WATCHDOG] Failed to write summary: {e}")

    def on_dead_fairy(self, callback: callable) -> None:
        """Register a callback for when a fairy is detected as dead."""
        self._dead_fairy_callbacks.append(callback)

    def get_liveness(self) -> Dict[str, Any]:
        """Get liveness status for all fairies."""
        alive = self.registry.list_alive(self.timeout_sec)
        dead = self.registry.list_dead(self.timeout_sec)

        return {
            "alive": [{"name": f.name, "last_heartbeat": f.last_heartbeat} for f in alive],
            "dead": [{"name": f.name, "last_heartbeat": f.last_heartbeat} for f in dead],
            "last_check": self._last_check,
            "timeout_sec": self.timeout_sec,
        }

    def get_stale_fairies(self, threshold_sec: float = 10.0) -> List["FairyRecord"]:
        """
        Get fairies that are getting stale (approaching timeout).

        Useful for early warning before they're considered dead.
        """
        now = time.time()
        stale = []

        for fairy in self.registry.list_all():
            if fairy.status != "running":
                continue

            age = now - fairy.last_heartbeat
            if threshold_sec < age < self.timeout_sec:
                stale.append(fairy)

        return stale

    def reset_timeout(self, timeout_sec: float) -> None:
        """Update the timeout threshold."""
        self.timeout_sec = timeout_sec

    def get_watchdog_status(self) -> Dict[str, Any]:
        """
        Get comprehensive watchdog status for debugging cascade failures.

        Returns death log, stale warnings, and session statistics.
        """
        now = time.time()
        session_duration = now - self._boot_time

        return {
            "session": {
                "boot_time": self._boot_time,
                "duration_seconds": round(session_duration, 1),
                "duration_human": f"{int(session_duration // 3600)}h {int((session_duration % 3600) // 60)}m",
                "global_beat": self._global_beat_count,
            },
            "deaths": {
                "total": len(self._death_log),
                "log": self._death_log[-20:],  # Last 20 deaths
                "first_death": self._death_log[0] if self._death_log else None,
            },
            "stale_warnings": {
                fairy: {
                    "first_stale": ts,
                    "stale_duration": round(now - ts, 1),
                }
                for fairy, ts in self._stale_warnings.items()
            },
            "currently_alive": list(self._previously_alive),
            "alive_count": len(self._previously_alive),
        }
