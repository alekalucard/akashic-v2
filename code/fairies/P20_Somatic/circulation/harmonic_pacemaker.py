"""HarmonicPacemaker — the heart + circadian as two coupled CLOCK-DERIVED oscillators.
2026-07-08 (Nous + Ace) — north-star first production cell. Drop-in beat source for CirculationPump.

Design (HARMONIC_HEARTBEAT_CIRCADIAN_PROPOSAL.md):
  * heart & circadian phase are PURE FUNCTIONS OF WALL-CLOCK — no loop, no thread, no shared
    mutable state on the read path → they CANNOT freeze or deadlock (proven test_harmonic_heartbeat).
  * circadian phase modulates heart frequency (SCN-over-heart: slow at night, fast midday).
  * beat_count is a DERIVED read (accumulated turns), not a mutated counter with a writer thread.
  * TRUTH (phase) is decoupled from BROADCAST: the optional bridge re-emits legacy
    heartbeat.pulse / circadian.phase_change via a NON-BLOCKING publish, so a jammed postal
    can only lag the compat emit — it can never stop the clock.
Consumers migrate off `subscribe(heartbeat.pulse)` → `pacemaker.phase()` reads / coupling-op entrain.
"""
from __future__ import annotations
import math, threading

# ── process-shared read-point (2026-07-08) ──────────────────────────────────
# Because the pacemaker is a PURE FUNCTION OF WALL-CLOCK, any beat-consumer can read the
# heart's rate/phase WITHOUT a subscription and WITHOUT the pump's instance — it just reads
# the shared pacemaker and gets a value that agrees by construction (no message-passing, no
# deadlock). CirculationPump registers ITS pacemaker as the shared one at boot (exact parity);
# get_shared() lazily makes a default if a consumer reads before the pump boots (safety net).
_SHARED = None
_SHARED_LOCK = threading.Lock()

def set_shared(pm) -> None:
    global _SHARED
    with _SHARED_LOCK:
        _SHARED = pm

def get_shared():
    global _SHARED
    if _SHARED is None:
        with _SHARED_LOCK:
            if _SHARED is None:
                _SHARED = HarmonicPacemaker()
    return _SHARED

# circadian phase-name bands (fraction of day [0,1)), matching the existing pacemaker's vocabulary
_PHASE_BANDS = [
    (0.00, "deep_night"), (0.21, "dawn"), (0.29, "morning"), (0.46, "midday"),
    (0.58, "afternoon"), (0.71, "evening"), (0.83, "night"), (0.92, "sleep"), (1.00, "deep_night"),
]

# Fixed GLOBAL phase epoch (unix time 0) — the SAME on every machine, so phase() is coherent
# network-wide (given NTP-synced clocks + identical base/depth/tz). The distributed-clock anchor.
EPOCH = 0.0

class HarmonicPacemaker:
    def __init__(self, clock=None, base_hz: float = 1.2, circ_depth: float = 0.25,
                 tz_offset_s: float = 0.0, day_len_s: float = 86400.0):
        import time as _t
        self._clock = clock or _t.time      # inject for tests; wall-clock in prod
        self.base_hz = base_hz              # heart resting frequency
        self.circ_depth = circ_depth        # how much the day modulates rate (0.25 = ±25%)
        self.tz_offset_s = tz_offset_s      # local-time offset (replaces the buggy tz-lookup)
        self.day_len_s = day_len_s
        self._boot_t = self._clock()        # LOCAL boot anchor — beat() counts from here (small climbing int)
        self._extra_rate = 1.0              # allostatic/sleep multiplier (set by chemistry; 1.0 = neutral)

    # ---- circadian (slow oscillator) — pure fn of time-of-day ----
    def circadian_phase(self, now=None) -> float:
        now = self._clock() if now is None else now
        return ((now + self.tz_offset_s) / self.day_len_s) % 1.0

    def circadian_name(self, now=None) -> str:
        p = self.circadian_phase(now)
        name = _PHASE_BANDS[0][1]
        for frac, nm in _PHASE_BANDS:
            if p >= frac:
                name = nm
        return name

    # ---- heart (fast oscillator), circadian-coupled ----
    def f_heart(self, now=None) -> float:
        cp = self.circadian_phase(now)
        circ = 1.0 + self.circ_depth * (-math.cos(2 * math.pi * cp))  # slow at midnight, fast at noon
        return self.base_hz * circ * self._extra_rate

    def set_rate_multiplier(self, m: float):   # chemistry hook (allostatic load / _sleep_mode)
        self._extra_rate = max(0.05, float(m))

    # ---- EPOCH-ANCHORED turn integral (2026-07-08): CLOSED-FORM ∫ carrier-rate dt, a PURE fn of
    # absolute wall-clock. base*(1 - depth*cos(2π(t+tz)/DAY)) integrates to the expression below.
    # Anchoring the turn count to a FIXED GLOBAL EPOCH makes phase() identical on every machine
    # (cross-machine coherence, given synced clocks + same base/depth/tz). No per-instance checkpoint,
    # no trapezoid drift, no lock. (Carrier is the PURE rate — _extra_rate stays a LOCAL pacing knob.)
    def _antideriv(self, t: float) -> float:
        b = self.base_hz
        return b * t - b * self.circ_depth * (self.day_len_s / (2 * math.pi)) * \
            math.sin(2 * math.pi * (t + self.tz_offset_s) / self.day_len_s)

    def _turns_since(self, anchor: float, now: float) -> float:
        return self._antideriv(now) - self._antideriv(anchor)

    def beat(self, now=None) -> int:
        # LOCAL count from boot — stays a small climbing integer (displays/liveness), not an epoch count.
        now = self._clock() if now is None else now
        return int(self._turns_since(self._boot_t, now))

    def phase(self, now=None) -> float:   # the SHARED CARRIER phase [0, 2π) — GLOBAL epoch-anchored → coherent
        now = self._clock() if now is None else now
        return (self._turns_since(EPOCH, now) % 1.0) * 2 * math.pi

    def heart_rate_bps(self, now=None) -> float:
        return self.f_heart(now)

    # ---- compat BRIDGE: emit legacy events from the phase, NON-BLOCKING (can't re-clot) ----
    def make_bridge(self, publish_fn):
        """Returns a step() to call from a light driver (or another fairy's tick). Emits
        heartbeat.pulse on each new beat + circadian.phase_change on band transitions. publish_fn
        MUST be non-blocking (enqueue+return / drop-on-full) — then a jammed postal only lags the
        compat emit; direct phase readers are unaffected."""
        state = {"last_beat": self.beat(), "last_phase": self.circadian_name()}
        def step(now=None):
            b = self.beat(now)
            if b != state["last_beat"]:
                state["last_beat"] = b
                try: publish_fn("heartbeat.pulse", {"beat": b, "hz": self.heart_rate_bps(now)})
                except Exception: pass  # bridge lag is fine; the phase is still true
            pn = self.circadian_name(now)
            if pn != state["last_phase"]:
                prev = state["last_phase"]; state["last_phase"] = pn
                try: publish_fn("circadian.phase_change", {"old_phase": prev, "new_phase": pn})
                except Exception: pass
        return step
