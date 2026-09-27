"""
Boot Timing Learner — Self-regulating boot/shutdown performance system.

Implements a closed learning loop:
  PRE-BOOT:  ProfileRecaller loads learned profiles from state/boot_profiles.json
             PriorityAdjuster uses profiles to re-weight fairy specs
  BOOT:      Go orchestrator boots fairies (timing captured in BootResult)
  POST-BOOT: BootResultTransformer maps BootResult -> profile deltas (EMA)
             ProfilePersister saves deltas to disk + SRM (async)
  SHUTDOWN:  ShutdownResultTransformer captures per-fairy shutdown timing
             ProfilePersister merges shutdown deltas into profiles

Baseline constraint: Profiles with boot_count < MIN_BASELINE_BOOTS are
observation-only — the PriorityAdjuster does NOT adjust their specs.
This prevents a bad early profile from poisoning adaptive timeouts.

Delta persistence: The persister does merge-on-write — only fields that
the transformer touched get updated. Shutdown fields are exclusively
owned by ShutdownResultTransformer. Knowledge accumulates, never resets.

Lives alongside boot_orchestrator.py — this is infrastructure, not a fairy.
Runs before fairies exist (pre-boot) and after they die (shutdown).

Architecture: Ace (2026-02-26)
Implementation: Nous
"""
import json
import os
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from tracer_pool.boot_orchestrator import BootResult, FairySpec


# ============================================================================
# Configuration
# ============================================================================

# Minimum boots before PriorityAdjuster trusts learned profiles.
# Boots 1..4 are observation-only (collecting baseline variance).
MIN_BASELINE_BOOTS = 5

# EMA learning rates (matches SatisfactionTracker convention)
TIMING_LEARNING_RATE = 0.2       # 20% weight to new timing observation
RELIABILITY_LEARNING_RATE = 0.15  # Slower for success_rate — one failure shouldn't tank trust

# Classification thresholds
HEAVY_THRESHOLD_MS = 5000.0   # > 5s total = heavy fairy
FAST_THRESHOLD_MS = 200.0     # < 200ms = fast fairy (priority bump)
FAILURE_DEPRIORITIZE = 3      # 3+ consecutive failures = low priority

# Timeout computation
TIMEOUT_HEADROOM = 1.5        # max_observed * 1.5 (p95-style upper bound)
MIN_TIMEOUT_MS = 10000        # Never less than 10s
MAX_TIMEOUT_MS = 120000       # Never more than 120s
DEFAULT_TIMEOUT_MS = 60000    # Default when insufficient data

# State file path
STATE_FILE = Path(__file__).parent.parent / "state" / "boot_profiles.json"


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class FairyBootProfile:
    """Learned boot performance profile for a single fairy.

    Fields are grouped by owner — boot transformer touches timing/reliability,
    shutdown transformer touches shutdown_* fields. Persister merges both.
    """
    name: str
    plane: str

    # --- Boot timing (EMA-smoothed, milliseconds) ---
    ema_init_ms: float = 0.0        # import + __init__()
    ema_boot_ms: float = 0.0        # on_boot()
    ema_total_ms: float = 0.0       # combined
    max_observed_ms: float = 0.0    # worst case seen (for p95 timeout)
    min_observed_ms: float = 0.0    # best case seen (0.0 = no observation yet)

    # --- Reliability ---
    success_rate: float = 1.0       # EMA of success (1.0 = always succeeds)
    consecutive_failures: int = 0
    last_error: str = ""

    # --- Classification (learned, not hardcoded) ---
    learned_priority: int = 1       # 0=high, 1=normal, 2=low
    learned_heavy: bool = False
    learned_timeout_ms: int = DEFAULT_TIMEOUT_MS

    # --- Shutdown timing ---
    ema_shutdown_ms: float = 0.0
    shutdown_success_rate: float = 1.0
    shutdown_order_hint: int = 0    # lower = safe to stop earlier
    shutdown_blocks_others: bool = False
    max_shutdown_ms: float = 0.0

    # --- Metadata ---
    boot_count: int = 0
    last_boot_ts: float = 0.0
    last_boot_ms: float = 0.0      # raw last observation
    first_seen_ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FairyBootProfile":
        """Migration-safe: ignore unknown keys, use defaults for missing."""
        valid_keys = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in valid_keys})


@dataclass
class BootTimingState:
    """Complete state for the boot timing learner."""
    version: int = 1
    profiles: Dict[str, FairyBootProfile] = field(default_factory=dict)
    global_stats: Dict[str, Any] = field(default_factory=lambda: {
        "total_boots": 0,
        "ema_total_boot_s": 0.0,
        "best_boot_s": float("inf"),
        "worst_boot_s": 0.0,
    })
    saved_at: float = 0.0


# ============================================================================
# EMA Helper
# ============================================================================

def _ema(current: float, new_value: float, rate: float = TIMING_LEARNING_RATE) -> float:
    """Exponential Moving Average, matching SatisfactionTracker pattern.

    First observation (current == 0.0) establishes baseline directly.
    """
    if current == 0.0:
        return new_value
    return current + rate * (new_value - current)


# ============================================================================
# 1. ProfileRecaller
# ============================================================================

class ProfileRecaller:
    """Loads boot profiles from local state file.

    Called ONCE at pre-boot, before GoBootOrchestrator creation.
    Must complete in < 10ms (just JSON file read, no SRM).
    """

    def __init__(self, state_file: Path = STATE_FILE):
        self._state_file = state_file

    def recall(self) -> BootTimingState:
        """Fast path: load from local JSON file."""
        try:
            if self._state_file.exists():
                with open(self._state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                state = self._deserialize(data)
                n = len(state.profiles)
                boot_num = state.global_stats.get("total_boots", 0) + 1
                print(f"[BootTiming] Recalled {n} profiles (boot #{boot_num})")
                return state
        except Exception as e:
            print(f"[BootTiming] Profile recall failed ({e}), using defaults")

        # First boot or corrupt file — empty state, all defaults
        return BootTimingState()

    def _deserialize(self, data: Dict) -> BootTimingState:
        state = BootTimingState()
        state.version = data.get("version", 1)
        state.global_stats = data.get("global_stats", state.global_stats)
        state.saved_at = data.get("saved_at", 0.0)
        for name, profile_data in data.get("profiles", {}).items():
            state.profiles[name] = FairyBootProfile.from_dict(profile_data)
        return state


# ============================================================================
# 2. PriorityAdjuster
# ============================================================================

class PriorityAdjuster:
    """Uses recalled boot profiles to dynamically adjust fairy boot specs.

    Baseline gate: profiles with boot_count < MIN_BASELINE_BOOTS are
    observation-only. No adjustments applied until we have enough signal.

    Infrastructure fairies (HIGH_PRIORITY_FAIRIES) NEVER get their priority
    changed, but DO get adaptive timeouts once past baseline.
    """

    def __init__(self, state: BootTimingState):
        self._state = state

    def adjust_specs(self, specs: List["FairySpec"]) -> List["FairySpec"]:
        """Adjust fairy specs using learned profiles. Mutates in place."""
        from tracer_pool.boot_orchestrator import HIGH_PRIORITY_FAIRIES

        adjusted = 0
        for spec in specs:
            profile = self._state.profiles.get(spec.name)
            if not profile:
                continue  # No history = use static defaults

            # Baseline gate: observation-only until enough data
            if profile.boot_count < MIN_BASELINE_BOOTS:
                continue

            # Infrastructure fairies: never change priority, but adjust timeout
            if spec.name in HIGH_PRIORITY_FAIRIES:
                timeout = self._compute_timeout(profile)
                spec.__dict__["learned_timeout_ms"] = timeout
                continue

            # --- Adjust priority based on learned performance ---

            if profile.consecutive_failures >= FAILURE_DEPRIORITIZE:
                spec.priority = 2  # Deprioritize chronic failures
            elif profile.ema_total_ms > HEAVY_THRESHOLD_MS:
                spec.priority = 2
                spec.heavy = True
            elif profile.ema_total_ms < FAST_THRESHOLD_MS:
                spec.priority = 0  # Fast fairy — boot early

            spec.__dict__["learned_timeout_ms"] = self._compute_timeout(profile)
            adjusted += 1

        if adjusted:
            print(f"[BootTiming] Adjusted {adjusted}/{len(specs)} fairy specs from profiles")

        return specs

    def _compute_timeout(self, profile: FairyBootProfile) -> int:
        """Compute adaptive timeout using max_observed (p95-style bound)."""
        if profile.boot_count < MIN_BASELINE_BOOTS:
            return DEFAULT_TIMEOUT_MS

        if profile.max_observed_ms <= 0:
            return DEFAULT_TIMEOUT_MS

        # Timeout = max observed * headroom, clamped to bounds
        padded = profile.max_observed_ms * TIMEOUT_HEADROOM
        return max(MIN_TIMEOUT_MS, min(MAX_TIMEOUT_MS, int(padded)))


# ============================================================================
# 3. BootResultTransformer
# ============================================================================

class BootResultTransformer:
    """Transforms BootResult into FairyBootProfile deltas.

    Called in _finalize_boot() after _process_results().
    Mutates ONLY boot timing/reliability fields. Never touches shutdown_* fields.
    """

    def __init__(self, state: BootTimingState):
        self._state = state

    def transform(
        self,
        result: "BootResult",
        init_timings: Optional[Dict[str, float]] = None,
    ) -> BootTimingState:
        """Process BootResult into profile updates.

        Args:
            result: BootResult from GoBootOrchestrator
            init_timings: Optional fairy_name -> init_duration_ms from Phase 1.
                          Allows splitting init vs boot time.
        """
        init_timings = init_timings or {}
        now = time.time()

        for fr in result.fairy_results:
            profile = self._state.profiles.get(fr.name)
            if not profile:
                # First time seeing this fairy — create profile
                profile = FairyBootProfile(
                    name=fr.name,
                    plane=fr.plane,
                    first_seen_ts=now,
                )
                self._state.profiles[fr.name] = profile

            # --- Update boot count and timestamp ---
            profile.boot_count += 1
            profile.last_boot_ts = now
            profile.last_boot_ms = fr.duration_ms

            # --- Split init vs boot if Phase 1 data available ---
            init_ms = init_timings.get(fr.name, 0.0)
            boot_ms = max(0.0, fr.duration_ms - init_ms) if init_ms else fr.duration_ms

            if fr.ok:
                # EMA timing updates
                profile.ema_init_ms = _ema(profile.ema_init_ms, init_ms)
                profile.ema_boot_ms = _ema(profile.ema_boot_ms, boot_ms)
                profile.ema_total_ms = _ema(profile.ema_total_ms, fr.duration_ms)

                # Variance tracking (min/max for p95 bounds)
                if fr.duration_ms > profile.max_observed_ms:
                    profile.max_observed_ms = fr.duration_ms
                if profile.min_observed_ms == 0.0 or fr.duration_ms < profile.min_observed_ms:
                    profile.min_observed_ms = fr.duration_ms

                # Reset failure streak
                profile.consecutive_failures = 0
                profile.last_error = ""
            else:
                profile.consecutive_failures += 1
                profile.last_error = fr.error or "unknown"

            # EMA reliability (slower learning rate)
            outcome = 1.0 if fr.ok else 0.0
            profile.success_rate = _ema(
                profile.success_rate, outcome, rate=RELIABILITY_LEARNING_RATE
            )

            # Reclassify heavy (only when past baseline)
            if profile.boot_count >= MIN_BASELINE_BOOTS:
                profile.learned_heavy = profile.ema_total_ms > HEAVY_THRESHOLD_MS

        # --- Update global stats ---
        gs = self._state.global_stats
        gs["total_boots"] = gs.get("total_boots", 0) + 1
        boot_s = result.total_ms / 1000.0
        gs["ema_total_boot_s"] = _ema(gs.get("ema_total_boot_s", 0.0), boot_s)
        gs["best_boot_s"] = min(gs.get("best_boot_s", float("inf")), boot_s)
        gs["worst_boot_s"] = max(gs.get("worst_boot_s", 0.0), boot_s)

        return self._state


# ============================================================================
# 4. ProfilePersister
# ============================================================================

class ProfilePersister:
    """Saves boot profiles: sync to disk, async to SRM.

    Delta merge: loads existing file, updates only changed fields,
    preserves everything else. Knowledge accumulates, never resets.
    """

    def __init__(self, state_file: Path = STATE_FILE):
        self._state_file = state_file

    def persist(self, state: BootTimingState, fabric=None):
        """Save profiles synchronously to disk, then async to SRM."""
        state.saved_at = time.time()

        # 1. Sync: atomic write to local JSON
        self._save_local(state)

        # 2. Async: SRM backup (best-effort, daemon thread)
        if fabric:
            threading.Thread(
                target=self._publish_to_srm,
                args=(state, fabric),
                name="boot-profile-srm-persist",
                daemon=True,
            ).start()

    def _save_local(self, state: BootTimingState):
        """Atomic write using .tmp + os.replace() (matches boot_skip_registry)."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)

            # --- Delta merge: load existing, update only changed profiles ---
            existing_data = {}
            if self._state_file.exists():
                try:
                    with open(self._state_file, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    existing_data = {}

            existing_profiles = existing_data.get("profiles", {})

            # Merge: new profiles overwrite matching keys, existing untouched keys stay
            for name, profile in state.profiles.items():
                if name in existing_profiles:
                    # Delta update: merge profile fields into existing
                    existing_profiles[name].update(profile.to_dict())
                else:
                    # New profile
                    existing_profiles[name] = profile.to_dict()

            data = {
                "version": state.version,
                "profiles": existing_profiles,
                "global_stats": state.global_stats,
                "saved_at": state.saved_at,
            }

            # Atomic write
            tmp = str(self._state_file) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp, str(self._state_file))

            print(f"[BootTiming] Saved {len(state.profiles)} profiles to {self._state_file.name}")

        except Exception as e:
            print(f"[BootTiming] Local save failed: {e}")

    def _publish_to_srm(self, state: BootTimingState, fabric):
        """Background: publish compact summary for SRM ingestion."""
        try:
            # Build compact summary (not the full profile dump)
            sorted_by_time = sorted(
                [(n, p.ema_total_ms) for n, p in state.profiles.items()
                 if p.boot_count > 0],
                key=lambda x: x[1], reverse=True,
            )
            failing = [
                (n, round(p.success_rate, 3), p.consecutive_failures)
                for n, p in state.profiles.items()
                if p.success_rate < 0.8
            ]

            fabric.publish("boot.profiles.learned", {
                "boot_number": state.global_stats.get("total_boots", 0),
                "total_boot_s": round(state.global_stats.get("ema_total_boot_s", 0), 1),
                "profile_count": len(state.profiles),
                "top_5_slowest": sorted_by_time[:5],
                "failing_fairies": failing[:10],
                "timestamp": time.time(),
            })
        except Exception as e:
            # SRM save is best-effort — don't crash
            print(f"[BootTiming] SRM publish failed (non-critical): {e}")


# ============================================================================
# 5. ShutdownResultTransformer
# ============================================================================

class ShutdownResultTransformer:
    """Captures per-fairy shutdown timing during server.py Phase 4.

    Uses the same FairyBootProfile (shutdown_* fields) so boot and shutdown
    learning live in one unified profile. Only touches shutdown fields.
    """

    def __init__(self, state: BootTimingState):
        self._state = state
        self._recordings: Dict[str, Dict[str, Any]] = {}

    def record_fairy_shutdown(
        self,
        name: str,
        duration_s: float,
        success: bool,
        timed_out: bool = False,
    ):
        """Record a single fairy's shutdown result. Called per-fairy in Phase 4."""
        self._recordings[name] = {
            "duration_ms": duration_s * 1000.0,
            "success": success,
            "timed_out": timed_out,
        }

    def finalize(self) -> BootTimingState:
        """Process all shutdown recordings into profile updates."""
        updated = 0

        for name, timing in self._recordings.items():
            profile = self._state.profiles.get(name)
            if not profile:
                continue  # No boot profile = skip (shouldn't happen)

            duration_ms = timing["duration_ms"]
            success = timing["success"]

            if success:
                # EMA shutdown timing
                profile.ema_shutdown_ms = _ema(profile.ema_shutdown_ms, duration_ms)
                # Track max for timeout computation
                if duration_ms > profile.max_shutdown_ms:
                    profile.max_shutdown_ms = duration_ms
            elif timing["timed_out"]:
                # Timed out: don't let raw timeout duration spike the EMA.
                # Instead cap at 2x current EMA to register "slow but bounded".
                if profile.ema_shutdown_ms > 0:
                    capped = min(duration_ms, profile.ema_shutdown_ms * 2.0)
                    profile.ema_shutdown_ms = _ema(profile.ema_shutdown_ms, capped)

            # EMA reliability
            outcome = 1.0 if success else 0.0
            profile.shutdown_success_rate = _ema(
                profile.shutdown_success_rate, outcome, rate=TIMING_LEARNING_RATE
            )

            # Shutdown order hint: faster = lower (safe to stop earlier)
            if profile.ema_shutdown_ms > 0:
                profile.shutdown_order_hint = int(profile.ema_shutdown_ms)

            # Detect blockers (fairies that time out = potential blockers)
            if timing["timed_out"]:
                profile.shutdown_blocks_others = True

            updated += 1

        if updated:
            print(f"[BootTiming] Shutdown profiles updated for {updated} fairies")

        return self._state
