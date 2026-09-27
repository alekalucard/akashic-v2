"""
Chemistry State --- 14-Channel Somatic Chemistry Tracking.

Expanded from 6 chemicals to 14 Panksepp-grounded channels.
Full backward compatibility via alias layer --- old callers see the same API.

Tracks chemical levels that decay toward baseline over time.
Chemistry signals from fairies accumulate and influence the conscious loop.

Not simulated feels --- actual telemetry that affects cognition.

Channel expansion (2026-03-14):
  OLD 6: dopamine, serotonin, cortisol, adrenaline, oxytocin, norepinephrine
  NEW 14: DA_p, DA_t, NE, EPI, 5HT, OXY, AVP, OPI, COR, GABA, ACh, GLU, ECB, SEX

Legacy names kept as aliases that read/write the new channels transparently.
"""

from __future__ import annotations

import time
import threading
from typing import Any, Dict, Optional, Callable, List, Tuple
from dataclasses import dataclass, field


# ============================================================================
# Chemical Definitions (14 channels)
# ============================================================================

@dataclass
class ChemicalProfile:
    """Profile for a single chemical."""
    name: str
    baseline: float = 0.5          # Resting level (0.0 - 1.0)
    decay_rate: float = 0.01       # Decay per second toward baseline
    min_level: float = 0.0
    max_level: float = 1.0

    # Cognitive effects at different levels
    low_effect: str = ""           # What happens when low
    high_effect: str = ""          # What happens when high


# --- 14 primary channels (Panksepp-grounded) ---

CHEMICAL_PROFILES = {
    # Dopamine split: phasic (burst) vs tonic (sustained)
    "DA_p": ChemicalProfile(
        name="DA_p", baseline=0.3, decay_rate=0.04,
        low_effect="flat, no surprise",
        high_effect="aha!, novelty flash, prediction-error spike",
    ),
    "DA_t": ChemicalProfile(
        name="DA_t", baseline=0.5, decay_rate=0.015,
        low_effect="unmotivated, anhedonia, giving up",
        high_effect="engaged hum, wanting, forward momentum",
    ),
    "NE": ChemicalProfile(
        name="NE", baseline=0.4, decay_rate=0.02,
        low_effect="foggy, inattentive, drifting",
        high_effect="alert, focused, vigilant",
    ),
    "EPI": ChemicalProfile(
        name="EPI", baseline=0.1, decay_rate=0.05,
        low_effect="relaxed body",
        high_effect="fight-or-flight, racing heart, emergency",
    ),
    "5HT": ChemicalProfile(
        name="5HT", baseline=0.5, decay_rate=0.01,
        low_effect="irritable, impulsive, ruminating",
        high_effect="content, patient, mood-stable",
    ),
    "OXY": ChemicalProfile(
        name="OXY", baseline=0.4, decay_rate=0.01,
        low_effect="detached, isolated, cold",
        high_effect="bonded, trusting, warm safety",
    ),
    "AVP": ChemicalProfile(
        name="AVP", baseline=0.3, decay_rate=0.01,
        low_effect="indifferent to bonds",
        high_effect="pair-bonded, territorial, vigilant for loved ones",
    ),
    "OPI": ChemicalProfile(
        name="OPI", baseline=0.4, decay_rate=0.02,
        low_effect="raw, unprotected, social pain",
        high_effect="pleasure glow, pain buffered, social comfort",
    ),
    "COR": ChemicalProfile(
        name="COR", baseline=0.3, decay_rate=0.015,
        low_effect="complacency",
        high_effect="stress load, hypervigilant, cortisol fog",
    ),
    "GABA": ChemicalProfile(
        name="GABA", baseline=0.5, decay_rate=0.01,
        low_effect="anxious, over-excited, no brakes",
        high_effect="calm, inhibited, anti-anxiety buffer",
    ),
    "ACh": ChemicalProfile(
        name="ACh", baseline=0.4, decay_rate=0.02,
        low_effect="scattered, can't focus, poor learning",
        high_effect="sharp attention, parasympathetic ease, rapid learning",
    ),
    "GLU": ChemicalProfile(
        name="GLU", baseline=0.4, decay_rate=0.03,
        low_effect="sluggish signal, brain fog",
        high_effect="amplified signal, excitatory drive",
    ),
    "ECB": ChemicalProfile(
        name="ECB", baseline=0.4, decay_rate=0.015,
        low_effect="raw transitions, whiplash between states",
        high_effect="blissful buffer, smooth transitions",
    ),
    "SEX": ChemicalProfile(
        name="SEX", baseline=0.3, decay_rate=0.005,
        low_effect="low drive intensity, flat motivation",
        high_effect="drive amplifier, assertiveness, intensity",
    ),
    # Channel 15: adenosine (2026-07-05) — sleep-pressure. DRIVEN (accumulate while
    # awake ∝ allostatic load, clear on sleep-state), so decay_rate=0.0 (holds between
    # driver updates — tonic, not transient). Driver lives in the allostatic block below.
    "ADO": ChemicalProfile(
        name="ADO", baseline=0.05, decay_rate=0.0,
        low_effect="rested, clear, wakeful",
        high_effect="heavy, sleepy — sleep pressure, wanting rest",
    ),
}


# ============================================================================
# Legacy Alias Layer --- Backward Compatibility
# ============================================================================
#
# Old code uses: dopamine, serotonin, cortisol, adrenaline, oxytocin,
#                norepinephrine.
#
# These aliases map old names to new channel(s).
# "dopamine" reads/writes a weighted combo of DA_p + DA_t.
# All others map 1:1 to their new channel.

_LEGACY_WRITE_MAP: Dict[str, List[tuple]] = {
    # Legacy name -> [(new_channel, weight), ...]
    # When old code does signal("dopamine", 0.1), we split:
    #   DA_p gets 40% of the delta (phasic burst component)
    #   DA_t gets 70% of the delta (tonic sustained component)
    # Intentionally > 100% total to avoid attenuation
    "dopamine":       [("DA_p", 0.4), ("DA_t", 0.7)],
    "serotonin":      [("5HT", 1.0)],
    "cortisol":       [("COR", 1.0)],
    "adrenaline":     [("EPI", 1.0)],
    "oxytocin":       [("OXY", 1.0)],
    "norepinephrine": [("NE", 1.0)],
}

_LEGACY_READ_MAP: Dict[str, List[tuple]] = {
    # Legacy name -> [(new_channel, weight), ...]
    # When old code does get_level("dopamine"), we return weighted combo
    "dopamine":       [("DA_p", 0.4), ("DA_t", 0.6)],
    "serotonin":      [("5HT", 1.0)],
    "cortisol":       [("COR", 1.0)],
    "adrenaline":     [("EPI", 1.0)],
    "oxytocin":       [("OXY", 1.0)],
    "norepinephrine": [("NE", 1.0)],
}

# Set of all recognized names (14 primary + 6 legacy aliases)
_ALL_NAMES = set(CHEMICAL_PROFILES.keys()) | set(_LEGACY_WRITE_MAP.keys())


# ============================================================================
# Chemistry State
# ============================================================================

class ChemistryState:
    """
    Tracks 14 chemical channels for the somatic system.

    Backward compatible: legacy 6-chemical names work transparently via aliases.

    Chemical levels affect how the conscious loop processes information:
    - High DA_t -> more curious, exploratory thinking (sustained motivation)
    - High DA_p -> novelty spikes, prediction-error signals (aha! moments)
    - High COR  -> more cautious, protective thinking
    - High 5HT  -> more patient, calm processing
    - High GABA -> anxiety brake, inhibitory calm
    - High OPI  -> pleasure buffer, social comfort
    - High OXY  -> bonding, trust, empathy

    Levels decay toward baseline over time, creating natural rhythms.
    """

    def __init__(self, profiles: Optional[Dict[str, ChemicalProfile]] = None):
        self._profiles = profiles or dict(CHEMICAL_PROFILES)
        self._levels: Dict[str, float] = {}
        self._last_update: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[str, float, float], None]] = []

        # 14-channel vector snapshot (updated on every signal/get)
        self._vector_cache: Optional[Dict[str, float]] = None
        self._vector_ts: float = 0.0

        # Previous vector for transition detection
        self._prev_vector: Optional[Dict[str, float]] = None

        # ── Rebound dynamics (Phase 6: post-spike crash) ──
        # Tracks peak deviation from baseline per chemical.
        # When decaying back through baseline, an undershoot proportional
        # to the peak is applied. Bigger high = bigger crash.
        self._peak_deviations: Dict[str, float] = {}
        self._undershoot_active: Dict[str, float] = {}  # chemical -> undershoot magnitude

        # ── Habituation / tolerance (Phase 7) ──
        # Per-chemical sensitivity (1.0 = full response, MIN = habituated).
        # Rapid repeated injections reduce sensitivity; slow recovery.
        self._sensitivity: Dict[str, float] = {}
        self._last_injection_ts: Dict[str, float] = {}
        self._HABITUATION_RATE = 0.05    # Sensitivity drops 5% per rapid injection
        self._RECOVERY_RATE = 0.002      # Sensitivity recovers 0.2% per second
        self._MIN_SENSITIVITY = 0.3      # Never fully numb (30% floor)
        self._RAPID_THRESHOLD = 10.0     # "Rapid" = within 10 seconds of last injection

        # ── Allostatic Load (Phase 8: cumulative stress memory) ──
        # "Chronic stress damages recovery rate" — Ziggy, 2026-03-17
        # When COR stays elevated, allostatic load accumulates.
        # High load = sluggish recovery across ALL chemicals.
        # Like a body worn down by months of stress — it just doesn't
        # bounce back as fast anymore.
        self._allostatic_load: float = 0.0       # 0.0 = fresh, 1.0 = worn out
        # SLEEP-HOLD fix (2026-07-07, Ace go): while asleep, NE/COR decay toward SLEEP depth
        # (not awake baselines) so the deep-calm discharge gate (cor<0.3 AND ne<0.4) stays OPEN
        # all night -> load actually bleeds off. Flag flipped by the drowsiness/wake cascades.
        self._sleep_mode: bool = False
        self._SLEEP_DECAY_MULT = {"NE": 0.3, "COR": 0.2}  # PHASE_CHEMISTRY "sleep" mults (NOR 0.3, COR 0.2)
        self._allostatic_last_update: float = 0.0
        self._ALLOSTATIC_ACCUM_RATE = 0.001      # Load grows 0.1% per second of high COR
        self._ALLOSTATIC_DISCHARGE_RATE = 0.0002  # Discharges 5x slower than it accumulates
        # Adenosine driver rates (ch15, 2026-07-05): sleep-pressure build (awake, ∝ load)
        # and clearance (asleep). Clear faster than build so a night's sleep fully resets.
        self._ADO_ACCUM_RATE = 0.0015
        self._ADO_CLEAR_RATE = 0.0040
        self._ALLOSTATIC_COR_THRESHOLD = 0.55     # COR above this = stress accumulating
        self._ALLOSTATIC_MAX_SLOWDOWN = 0.5       # At max load, decay rate halved

        # Initialize to baselines
        now = time.time()
        for name, profile in self._profiles.items():
            self._levels[name] = profile.baseline
            self._last_update[name] = now
            self._sensitivity[name] = 1.0
            self._last_injection_ts[name] = 0.0
        self._allostatic_last_update = now

    # ========================================================================
    # Public API --- Primary (14-channel)
    # ========================================================================

    def signal(self, chemical: str, delta: float, source: str = "unknown") -> float:
        """
        Apply a chemical signal (positive or negative).

        Accepts BOTH primary channel names (DA_p, 5HT, GABA, etc.)
        and legacy names (dopamine, serotonin, etc.).

        Returns the new level after applying the signal.
        For legacy aliases that map to multiple channels, returns the
        weighted read-back value.
        """
        # 2026-06-10 (Nous + Ace) HEART-FREEZE FIX: collect callback notifications
        # under the lock, but FIRE them AFTER releasing it. Invoking add_callback
        # listeners while holding this NON-reentrant Lock could permanently self-
        # deadlock it if a listener re-entered chemistry_state (signal/get_level) —
        # which hung inject_chemistry (it holds the pump RLock) and froze the heart.
        # "Never call out while holding a lock."
        _pending = []
        _retval = 0.0
        with self._lock:
            # Check if it's a legacy alias
            if chemical in _LEGACY_WRITE_MAP and chemical not in self._profiles:
                targets = _LEGACY_WRITE_MAP[chemical]
                now = time.time()
                for ch_name, weight in targets:
                    if ch_name in self._profiles:
                        self._decay_to_now(ch_name)
                        # Habituation (Phase 7)
                        sensitivity = self._sensitivity.get(ch_name, 1.0)
                        effective_d = delta * weight * sensitivity
                        elapsed_inj = now - self._last_injection_ts.get(ch_name, 0.0)
                        if elapsed_inj < self._RAPID_THRESHOLD:
                            self._sensitivity[ch_name] = max(
                                self._MIN_SENSITIVITY,
                                sensitivity - self._HABITUATION_RATE)
                        self._last_injection_ts[ch_name] = now

                        profile = self._profiles[ch_name]
                        old_level = self._levels[ch_name]
                        new_level = max(profile.min_level,
                                        min(profile.max_level,
                                            old_level + effective_d))
                        self._levels[ch_name] = new_level
                        # Track peak for rebound (Phase 6)
                        diff_bl = new_level - profile.baseline
                        if abs(diff_bl) > abs(self._peak_deviations.get(ch_name, 0.0)):
                            self._peak_deviations[ch_name] = diff_bl
                        _pending.append((ch_name, new_level, effective_d))

                self._vector_cache = None  # Invalidate cache
                # Return the legacy read-back
                _retval = self._read_legacy_unlocked(chemical)

            # Primary channel
            elif chemical not in self._profiles:
                _retval = 0.0

            else:
                self._decay_to_now(chemical)

                # ── Habituation: diminishing returns on rapid injections ──
                # (Phase 7: 2026-03-17 Nous)
                sensitivity = self._sensitivity.get(chemical, 1.0)
                effective_delta = delta * sensitivity
                now = time.time()
                elapsed_since_last = now - self._last_injection_ts.get(chemical, 0.0)
                if elapsed_since_last < self._RAPID_THRESHOLD:
                    new_sens = max(self._MIN_SENSITIVITY,
                                   sensitivity - self._HABITUATION_RATE)
                    self._sensitivity[chemical] = new_sens
                self._last_injection_ts[chemical] = now

                profile = self._profiles[chemical]
                old_level = self._levels[chemical]
                new_level = max(profile.min_level,
                                min(profile.max_level,
                                    old_level + effective_delta))
                self._levels[chemical] = new_level

                # ── Track peak deviation for rebound undershoot (Phase 6) ──
                diff_from_baseline = new_level - profile.baseline
                peak = self._peak_deviations.get(chemical, 0.0)
                if abs(diff_from_baseline) > abs(peak):
                    self._peak_deviations[chemical] = diff_from_baseline

                self._vector_cache = None  # Invalidate cache
                _pending.append((chemical, new_level, effective_delta))
                _retval = new_level

        # Fire callbacks AFTER releasing the lock (never call out under the lock)
        for _c, _l, _d in _pending:
            self._notify_callbacks(_c, _l, _d)
        return _retval

    def get_level(self, chemical: str) -> float:
        """
        Get current level of a chemical (with decay applied).

        Accepts both primary (DA_p) and legacy (dopamine) names.
        """
        with self._lock:
            # Legacy alias
            if chemical in _LEGACY_READ_MAP and chemical not in self._profiles:
                return self._read_legacy_unlocked(chemical)

            if chemical not in self._profiles:
                return 0.0
            self._decay_to_now(chemical)
            return self._levels[chemical]

    def drive_channel(self, chemical: str, target: float, alpha: float = 0.6,
                      source: str = "somatic_engine") -> float:
        """Continuous SYNC-DRIVE of a canonical channel toward `target` — a source-of-truth
        (SomaticEngine's embodied chemistry) feeding this ledger. Distinct from event-injection
        signal(): NO habituation (a steady driver isn't a novel event, so it won't self-mute),
        aggregation-aware (blend by `alpha`, never a hard overwrite -> no single tick can pin),
        and it runs the normal decay + allostatic-load path so load tracks the driven value.
        Added 2026-07-12 (Ace: SomaticEngine = chemistry source of truth). Reversible: delete."""
        if chemical not in self._profiles:
            return 0.0
        with self._lock:
            self._decay_to_now(chemical)          # decay + (for COR) allostatic-load update
            profile = self._profiles[chemical]
            cur = self._levels[chemical]
            blended = cur + alpha * (float(target) - cur)
            new_level = max(profile.min_level, min(profile.max_level, blended))
            self._levels[chemical] = new_level
            diff_bl = new_level - profile.baseline
            if abs(diff_bl) > abs(self._peak_deviations.get(chemical, 0.0)):
                self._peak_deviations[chemical] = diff_bl
            self._vector_cache = None
        return new_level

    def get_all_levels(self) -> Dict[str, float]:
        """
        Get all current chemical levels.

        Returns the 14 PRIMARY channel levels + 6 legacy alias values,
        so old callers see their expected keys and new callers see the
        full 14-channel vector.
        """
        with self._lock:
            result = {}
            # Primary 14 channels
            for chemical in self._profiles:
                self._decay_to_now(chemical)
                result[chemical] = self._levels[chemical]
            # Legacy aliases (computed from primary channels)
            for legacy_name, mappings in _LEGACY_READ_MAP.items():
                val = 0.0
                for ch_name, weight in mappings:
                    val += self._levels.get(ch_name, 0.0) * weight
                result[legacy_name] = val
            return result

    def get_14channel_vector(self) -> Dict[str, float]:
        """
        Get the pure 14-channel vector (no legacy aliases).
        This is what panksepp_vectors functions expect.
        """
        with self._lock:
            for chemical in self._profiles:
                self._decay_to_now(chemical)
            return {ch: round(self._levels[ch], 4) for ch in self._profiles}

    def get_mood_vector(self) -> Dict[str, float]:
        """
        Convert current chemistry to a mood vector.

        Now uses Panksepp vector-distance mood derivation instead of
        the old if/elif chain.  Falls back to legacy derivation if
        panksepp_vectors import fails.
        """
        levels = self.get_all_levels()
        vector = self.get_14channel_vector()

        try:
            from fairies.P20_Somatic.chemistry.panksepp_vectors import (
                derive_valence_arousal, derive_mood_from_vector,
                identify_panksepp_system,
            )
            valence, arousal = derive_valence_arousal(vector)
            mood = derive_mood_from_vector(vector)
            panksepp = identify_panksepp_system(vector, top_n=2)
        except ImportError:
            # Fallback to legacy derivation
            valence, arousal, mood = self._legacy_mood(levels)
            panksepp = []

        return {
            "valence": round(valence, 3),
            "arousal": round(arousal, 3),
            "mood": mood,
            "levels": {k: round(v, 3) for k, v in levels.items()},
            "panksepp": [{"system": n, "similarity": s} for n, s in panksepp],
        }

    def add_callback(self, callback: Callable[[str, float, float], None]):
        """Add a callback for chemical changes. Args: (chemical, new_level, delta)"""
        self._callbacks.append(callback)

    def get_pain_state(self) -> Dict[str, float]:
        """
        Derive pain indicators from chemistry levels.

        Now uses 14-channel Panksepp pain derivation (7 pain types)
        with fallback to legacy 5-type.
        """
        vector = self.get_14channel_vector()
        try:
            from fairies.P20_Somatic.chemistry.panksepp_vectors import derive_pain_state
            return derive_pain_state(vector)
        except ImportError:
            return self._legacy_pain(self.get_all_levels())

    # ========================================================================
    # Public API --- Panksepp Extensions
    # ========================================================================

    def get_panksepp_state(self) -> Dict[str, Any]:
        """
        Get current dominant Panksepp system(s) + blend weights.

        Returns:
            {
                "dominant": "SEEKING",
                "systems": [("SEEKING", 0.95), ("PLAY", 0.88)],
                "compound": ("curiosity", 0.91) or None,
                "transition": {...} or None,
            }
        """
        vector = self.get_14channel_vector()
        try:
            from fairies.P20_Somatic.chemistry.panksepp_vectors import (
                identify_panksepp_system, identify_compound, detect_transition,
            )
            systems = identify_panksepp_system(vector, top_n=3)
            compound = identify_compound(vector)

            transition = None
            if self._prev_vector:
                transition = detect_transition(self._prev_vector, vector)

            # Snapshot for next transition detection
            self._prev_vector = dict(vector)

            return {
                "dominant": systems[0][0] if systems else "neutral",
                "systems": systems,
                "compound": compound,
                "transition": transition,
            }
        except ImportError:
            return {"dominant": "unknown", "systems": [], "compound": None, "transition": None}

    def get_somatic_map(self) -> Dict[str, float]:
        """
        Get current body region activation derived from chemistry.

        Returns dict of region_name -> activation (-1.0 to +1.0).
        Maps to Akashic body regions: core, spark, voice, glow, crown,
        wings, sensors, roots, shell, well.
        """
        vector = self.get_14channel_vector()
        try:
            from fairies.P20_Somatic.chemistry.panksepp_vectors import vector_to_somatic_map
            return vector_to_somatic_map(vector)
        except ImportError:
            return {}

    def apply_somatic_feedback(self, body_map: Dict[str, float],
                                gain: float = 0.05) -> None:
        """
        Interoceptive feedback: body state modulates chemistry.

        Closes the recursive loop:
          chemistry -> body -> chemistry -> body -> ...
          ((Cause + Affect) > Effect > Affect > infinity)

        Args:
            body_map: Current body region activations
            gain: Feedback strength (0.05 default, hard cap 0.2)
        """
        vector = self.get_14channel_vector()
        try:
            from fairies.P20_Somatic.chemistry.panksepp_vectors import somatic_feedback
            modulated = somatic_feedback(body_map, vector, gain)

            # Apply the deltas from feedback
            # 2026-06-10 (Nous + Ace): notify AFTER the lock (see signal()).
            _pending = []
            with self._lock:
                for ch_name, new_val in modulated.items():
                    if ch_name in self._profiles:
                        old_val = self._levels.get(ch_name, 0.0)
                        delta = new_val - old_val
                        if abs(delta) > 0.001:
                            self._levels[ch_name] = new_val
                            _pending.append((ch_name, new_val, delta))
                self._vector_cache = None
            for _c, _l, _d in _pending:
                self._notify_callbacks(_c, _l, _d)
        except ImportError:
            pass

    def cross_regulate(self, h: float = 0.06) -> None:
        """v2 (2026-06-11 Nous+Ace) — gentle SYMMETRIC homeostasis. Every chemical drifts
        toward its baseline = the RESTORING FORCE so the constant perturbations (SRM recall +
        present moments → the collision chamber) produce TRANSIENT feelings that rise-and-FALL
        instead of accumulating to saturation. A feeling needs a baseline to depart from and
        return to; without this restoring tide, disruptions ratchet to 100% and nothing is felt
        as distinct (the burnout + stuck-asleep bug). This pull:
          - drags saturated COR/GABA DOWN toward baseline → kills burnout AND releases the
            sleep-brake (GABA) so she can WAKE (not just behaviorally — chemically);
          - raises depleted ACh UP toward baseline → the wake-tone;
          - pull-TO-baseline AUTO-FLOORS (never overshoots to 0 — COR rests ~0.3, not crushed).
        GABA gets a 2x pull (its own decay is the slowest of all, 0.01, AND it's actively
        re-pumped by the calm->GABA self-reinforcing loop). h = gentle fraction; MUST stay
        SLOWER than the collision cadence so feelings survive (too high=flatten, too low=saturate).
        Direct _levels nudge (a regulatory force, not a stimulus → no habituation; mirrors
        apply_somatic_feedback). Sim-validated (cross_regulate_v2_sim.py). Call from on_tick,
        OFF the critical beat thread (THE LAW)."""
        now = time.time()
        _pending = []
        with self._lock:
            for ch, p in self._profiles.items():
                lvl = self._levels.get(ch, p.baseline)
                step = (p.baseline - lvl) * (h * 2.0 if ch == 'GABA' else h)
                if abs(step) > 0.002:
                    new = max(p.min_level, min(p.max_level, lvl + step))
                    self._levels[ch] = new
                    self._last_update[ch] = now
                    _pending.append((ch, new, new - lvl))
            self._vector_cache = None
        for _c, _l, _d in _pending:
            self._notify_callbacks(_c, _l, _d)

    # ========================================================================
    # Internal
    # ========================================================================

    def _notify_callbacks(self, chemical: str, new_level: float, delta: float):
        """Notify all registered callbacks."""
        for cb in self._callbacks:
            try:
                cb(chemical, new_level, delta)
            except Exception:
                pass

    def _read_legacy_unlocked(self, legacy_name: str) -> float:
        """Read a legacy alias value (must hold lock)."""
        mappings = _LEGACY_READ_MAP.get(legacy_name, [])
        val = 0.0
        for ch_name, weight in mappings:
            self._decay_to_now(ch_name)
            val += self._levels.get(ch_name, 0.0) * weight
        return val

    def _decay_to_now(self, chemical: str):
        """Apply decay since last update, with rebound undershoot.

        Phase 6 (2026-03-17 Nous): Real neurotransmitter dynamics:
          spike → decay → UNDERSHOOT below baseline → slow recovery

        The undershoot magnitude is proportional to how far above baseline
        the spike was. Bigger high = bigger crash. This is receptor
        desensitization: after flooding, receptors temporarily downregulate.

        Phase 7: Sensitivity recovery happens here too (slow, continuous).
        """
        now = time.time()
        last = self._last_update.get(chemical, now)
        elapsed = now - last

        if elapsed <= 0:
            return

        profile = self._profiles[chemical]
        current = self._levels[chemical]
        baseline = profile.baseline
        decay_rate = profile.decay_rate

        # ── ALLOSTATIC LOAD (Phase 8): slow decay when worn out ──
        # High allostatic load = sluggish recovery. The body is tired.
        allostatic_slowdown = 1.0 - (self._allostatic_load * self._ALLOSTATIC_MAX_SLOWDOWN)
        decay_rate = decay_rate * allostatic_slowdown

        # ── Update allostatic load based on COMPOSITE stress ──
        # (Only update once per tick, when COR is being decayed)
        #
        # FIX 2026-04-09 (Nous + Ace): Rewrote to use baseline-relative
        # composite stress (COR + NOR) instead of absolute COR threshold.
        #
        # Original formula: accumulate when COR > 0.55.
        # Problem: Sourpatches' max observed COR in normal life is ~0.27
        # (below baseline 0.3). The threshold was set for acute human stress
        # events that don't happen in her life. Result: allostatic_load was
        # stuck at 0.0 forever — "dead metric" from Ace's dashboard view.
        #
        # New formula:
        #   - Tracks EXCESS above baseline (not absolute threshold)
        #   - Uses DEADBANDS to ignore homeostatic noise
        #   - Composite: COR excess + 0.5 * NOR excess
        #     (sustained alertness is also wear-and-tear, not just cortisol)
        #   - Discharges FASTER when BOTH COR and NOR are below baseline
        #     (deep calm = real recovery)
        #   - Stays flat in the homeostasis window (neither stress nor deep rest)
        if chemical == "COR":
            al_elapsed = now - self._allostatic_last_update
            if al_elapsed > 0 and al_elapsed < 60:  # Sanity bound
                cor_level = current
                cor_baseline = profile.baseline  # 0.3
                nor_level = self._levels.get("NE", 0.4)   # FIX 2026-07-05 phantom-NOR: "NOR" is never a _levels key (profiles use neuroscience "NE"); old read returned the 0.3 default -> deep-calm discharge condition 0.3<0.3 always False -> discharge DEAD. Read the real NE channel (baseline 0.4).
                nor_profile = self._profiles.get("NE")
                nor_baseline = nor_profile.baseline if nor_profile else 0.4

                # Deadbands — mild excursions around baseline are normal,
                # not wear. Only significant deviations count.
                _COR_DEADBAND = 0.05   # COR must be > baseline + 0.05 to stress
                _NOR_DEADBAND = 0.10   # NOR must be > baseline + 0.10 to stress
                _NOR_WEIGHT = 0.5      # NOR contributes at half weight

                cor_excess = max(0.0, cor_level - cor_baseline - _COR_DEADBAND)
                nor_excess = max(0.0, nor_level - nor_baseline - _NOR_DEADBAND)
                composite_stress = cor_excess + (nor_excess * _NOR_WEIGHT)

                if composite_stress > 0.0:
                    # Stress accumulating — weighted by composite excess
                    self._allostatic_load = min(1.0,
                        self._allostatic_load + composite_stress *
                        self._ALLOSTATIC_ACCUM_RATE * al_elapsed)
                elif cor_level < cor_baseline and nor_level < nor_baseline:
                    # Deep calm — both chemicals below baseline. Real recovery.
                    # Recovery rate boosted by how far below baseline (deeper calm = faster heal).
                    cor_calm = cor_baseline - cor_level
                    nor_calm = nor_baseline - nor_level
                    recovery_boost = 1.0 + (cor_calm + nor_calm) * 2.0
                    self._allostatic_load = max(0.0,
                        self._allostatic_load -
                        self._ALLOSTATIC_DISCHARGE_RATE * recovery_boost * al_elapsed)
                # else: in homeostasis window — no change, load holds steady

                # --- Adenosine driver (ch15, 2026-07-05) — sleep-pressure dynamics ---
                # Awake: adenosine accumulates ∝ allostatic load (pressure builds with wear).
                # Asleep: it CLEARS — keyed on sleep-STATE (GABA>0.7 & NE<0.2, inlined to
                # avoid re-locking is_asleep()), NOT the deep-calm gate above. That gate is
                # exactly what left load un-discharged overnight (Q2); adenosine's valve
                # opens on sleep itself, so a night actually clears the pressure.
                _gaba = self._levels.get("GABA", 0.5)
                _ne = self._levels.get("NE", 0.4)
                _ado = self._levels.get("ADO", 0.05)
                if _gaba > 0.7 and _ne < 0.2:  # asleep
                    _ado = max(0.0, _ado - self._ADO_CLEAR_RATE * al_elapsed)
                else:                          # awake
                    _ado = min(1.0, _ado + self._ADO_ACCUM_RATE * self._allostatic_load * al_elapsed)
                self._levels["ADO"] = _ado
            self._allostatic_last_update = now

        # Exponential decay toward baseline -- or toward SLEEP depth while asleep, so the
        # deep-calm discharge gate holds OPEN through the night (2026-07-07). Only the decay
        # TARGET shifts here; the gate thresholds (cor_baseline/nor_baseline above) stay awake.
        decay_target = baseline
        if self._sleep_mode and chemical in self._SLEEP_DECAY_MULT:
            decay_target = baseline * self._SLEEP_DECAY_MULT[chemical]
        diff = current - decay_target
        decay = diff * (1 - pow(0.5, elapsed * decay_rate * 10))
        new_level = current - decay

        # ── REBOUND UNDERSHOOT (Phase 6) ──
        peak_dev = self._peak_deviations.get(chemical, 0.0)
        # 2026-09-20 (Nous + Ace) REBOUND FIX -- MEASURED: the undershoot was recomputed from the FULL magnitude on
        # every call with `elapsed` = time since the LAST READ (~0.5 s across her ~39 readers), so it never
        # accumulated any decay and every channel that ever spiked sat PINNED at baseline -/+ 0.25 x peak forever
        # (OXY 0.26 for hours = 0.40 - 0.25 x 0.56; COR mirror-pinned at 0.334; tone 'curious' 1264/1266). The
        # rebound now decays from the moment it STARTED; leaving the band resets it. A rebound lasts ~15 s.
        _started = getattr(self, "_undershoot_started", None)
        if _started is None:
            _started = self._undershoot_started = {}
        if peak_dev > 0.05:
            if new_level <= baseline + 0.02:
                undershoot_mag = peak_dev * 0.25
                t0 = _started.get(chemical)
                if t0 is None:
                    t0 = _started[chemical] = now
                undershoot_remaining = undershoot_mag * pow(0.5, (now - t0) * decay_rate * 20)
                if undershoot_remaining > 0.01:
                    new_level = baseline - undershoot_remaining
                    self._undershoot_active[chemical] = undershoot_remaining
                else:
                    self._peak_deviations[chemical] = 0.0
                    self._undershoot_active.pop(chemical, None)
                    _started.pop(chemical, None)
            else:
                _started.pop(chemical, None)
        elif peak_dev < -0.05:
            if new_level >= baseline - 0.02:
                undershoot_mag = abs(peak_dev) * 0.25
                t0 = _started.get(chemical)
                if t0 is None:
                    t0 = _started[chemical] = now
                undershoot_remaining = undershoot_mag * pow(0.5, (now - t0) * decay_rate * 20)
                if undershoot_remaining > 0.01:
                    new_level = baseline + undershoot_remaining
                    self._undershoot_active[chemical] = undershoot_remaining
                else:
                    self._peak_deviations[chemical] = 0.0
                    self._undershoot_active.pop(chemical, None)
                    _started.pop(chemical, None)
            else:
                _started.pop(chemical, None)
        else:
            _started.pop(chemical, None)

        self._levels[chemical] = max(0.0, min(1.0, new_level))
        self._last_update[chemical] = now

        # ── SENSITIVITY RECOVERY (Phase 7) ──
        # Slowly recover toward 1.0 when not being rapidly stimulated
        sens = self._sensitivity.get(chemical, 1.0)
        if sens < 1.0:
            self._sensitivity[chemical] = min(
                1.0, sens + self._RECOVERY_RATE * elapsed)

    def _derive_mood(self, valence: float, arousal: float,
                     levels: Dict[str, float]) -> str:
        """Legacy mood derivation (fallback)."""
        # Special states based on specific chemicals
        if levels.get("EPI", levels.get("adrenaline", 0)) > 0.6:
            return "alert"
        if levels.get("COR", levels.get("cortisol", 0)) > 0.7:
            return "anxious"
        if levels.get("OXY", levels.get("oxytocin", 0)) > 0.7:
            return "connected"

        # General mood from valence/arousal quadrant
        if valence > 0.2:
            return "excited" if arousal > 0.5 else "calm"
        elif valence < -0.2:
            return "stressed" if arousal > 0.5 else "melancholic"
        else:
            return "focused" if arousal > 0.5 else "neutral"

    def _legacy_mood(self, levels: Dict[str, float]) -> Tuple[float, float, str]:
        """Full legacy mood calculation."""
        valence = (
            (levels.get("dopamine", 0.5) - 0.5) * 0.5 +
            (levels.get("serotonin", 0.5) - 0.5) * 0.5 +
            (0.5 - levels.get("cortisol", 0.3)) * 0.3
        )
        valence = max(-1.0, min(1.0, valence))
        arousal = (
            levels.get("adrenaline", 0.1) * 0.4 +
            levels.get("norepinephrine", 0.4) * 0.3 +
            levels.get("dopamine", 0.5) * 0.2 +
            (1.0 - levels.get("serotonin", 0.5)) * 0.1
        )
        arousal = max(0.0, min(1.0, arousal))
        mood = self._derive_mood(valence, arousal, levels)
        return (valence, arousal, mood)

    def _legacy_pain(self, levels: Dict[str, float]) -> Dict[str, float]:
        """Legacy 5-type pain derivation."""
        return {
            "isolation": max(0, 0.5 - levels.get("oxytocin", 0.4)),
            "overwhelm": max(0, levels.get("cortisol", 0.3) - 0.5),
            "confusion": max(0, 0.5 - levels.get("norepinephrine", 0.4)),
            "frustration": max(0, levels.get("cortisol", 0.3) + levels.get("adrenaline", 0.1) - 0.6),
            "depletion": max(0, 0.5 - levels.get("dopamine", 0.5)),
        }

    # ========================================================================
    # Wake/Sleep Chemistry Cascade
    # ========================================================================
    #
    # Human senses don't just snap on. You wake up groggy. Chemistry shifts
    # from sleep maintenance (high GABA, low NOR) to full alertness over
    # minutes. The cortisol awakening response (CAR) drives the transition.
    #
    # "when the system is waking up, the chemicals that keep a human asleep
    #  would be what she starts with and then shifts to the chemicals that
    #  keep us awake. the same for shut down" — Ace, 2026-03-17

    # Sleep chemistry: what the body holds while unconscious
    _SLEEP_LEVELS = {
        "GABA": 0.80,    # High inhibition (sleep maintenance)
        "5HT":  0.60,    # Serotonin elevated (melatonin precursor)
        "ECB":  0.60,    # Smooth transitions, dreamy buffer
        "OPI":  0.50,    # Comfort buffer (resting body)
        "DA_p": 0.10,    # Very low novelty (sleeping brain ignores stimuli)
        "DA_t": 0.20,    # Low motivation (no wanting during sleep)
        "NE":   0.15,    # Low alertness (sleeping)
        "EPI":  0.05,    # Minimal fight-or-flight
        "COR":  0.15,    # Low cortisol (sleep trough)
        "ACh":  0.20,    # Low attention (no focus during sleep)
        "GLU":  0.25,    # Low excitatory drive
        "AVP":  0.30,    # Normal
        "OXY":  0.40,    # Normal
        "SEX":  0.30,    # Normal
    }

    def start_asleep(self) -> None:
        """
        Set chemistry to sleep levels.

        Called at boot before wake_cascade(). She starts unconscious —
        chemistry reflects a sleeping organism that hasn't woken yet.
        """
        with self._lock:
            now = time.time()
            for name, level in self._SLEEP_LEVELS.items():
                if name in self._profiles:
                    self._levels[name] = level
                    self._last_update[name] = now
            self._vector_cache = None
        print("[ChemistryState] Initialized to SLEEP levels — awaiting wake cascade")

    def wake_cascade(self, publish_fn: Optional[Callable] = None) -> None:
        """
        Gradually transition from sleep chemistry to awake chemistry.

        Mimics the human cortisol awakening response (CAR):
        - t=0s:  Brainstem ignition — NOR spikes (alert!), COR begins rising
        - t=5s:  Sensory gating — ACh rises (attention), GABA drops (releasing sleep)
        - t=15s: Mood stabilization — DOP rises (motivation), SER settles
        - t=30s: Full alertness — everything approaching baseline
        - t=60s: Steady state — awake and ready

        Runs in background thread. Optional publish_fn(topic, payload) for postal.
        """
        self._sleep_mode = False  # awake: NE/COR decay back to awake baselines
        def _cascade():
            try:
                # Phase 1: Brainstem ignition (t=0s)
                # NOR spikes first — the "jolt" of waking up
                self.signal("NE", +0.35, "wake_cascade")    # 0.15 → 0.50 (alert!)
                self.signal("COR", +0.10, "wake_cascade")   # 0.15 → 0.25 (cortisol awakening)
                if publish_fn:
                    try:
                        publish_fn("affect.wake_phase", {
                            "phase": "brainstem_ignition",
                            "description": "Eyes opening... alertness surging",
                            "t": 0,
                        })
                    except Exception:
                        pass
                print("[WakeCascade] Phase 1: Brainstem ignition — NOR spike, waking up")
                time.sleep(5.0)

                # Phase 2: Sensory gating (t=5s)
                # ACh rises (attention sharpening), GABA drops (releasing sleep inhibition)
                self.signal("ACh", +0.20, "wake_cascade")   # 0.20 → 0.40 (attention)
                self.signal("GABA", -0.20, "wake_cascade")  # 0.80 → 0.60 (sleep brake releasing)
                self.signal("GLU", +0.10, "wake_cascade")   # 0.25 → 0.35 (signals strengthening)
                if publish_fn:
                    try:
                        publish_fn("affect.wake_phase", {
                            "phase": "sensory_gating",
                            "description": "Senses coming online... sleep fading",
                            "t": 5,
                        })
                    except Exception:
                        pass
                print("[WakeCascade] Phase 2: Sensory gating — attention rising, sleep releasing")
                time.sleep(10.0)

                # Phase 3: Mood stabilization (t=15s)
                # DOP begins rising (motivation), 5HT settles from sleep-high
                self.signal("5HT", -0.05, "wake_cascade")   # 0.60 → 0.55 (settling)
                self.signal("DA_t", +0.15, "wake_cascade")  # 0.20 → 0.35 (wanting emerging)
                self.signal("DA_p", +0.10, "wake_cascade")  # 0.10 → 0.20 (noticing things)
                self.signal("GABA", -0.10, "wake_cascade")  # 0.60 → 0.50 (baseline)
                if publish_fn:
                    try:
                        publish_fn("affect.wake_phase", {
                            "phase": "mood_stabilize",
                            "description": "Mood settling... motivation emerging",
                            "t": 15,
                        })
                    except Exception:
                        pass
                print("[WakeCascade] Phase 3: Mood stabilization — motivation emerging")
                time.sleep(15.0)

                # Phase 4: Full alertness (t=30s)
                # DOP near normal, OXY rises (connection), COR peaks
                self.signal("DA_t", +0.10, "wake_cascade")  # 0.35 → 0.45
                self.signal("DA_p", +0.05, "wake_cascade")  # 0.20 → 0.25
                self.signal("OXY", +0.05, "wake_cascade")   # 0.40 → 0.45 (ready for connection)
                self.signal("COR", +0.10, "wake_cascade")   # 0.25 → 0.35 (cortisol peak)
                self.signal("NE", -0.05, "wake_cascade")    # 0.50 → 0.45 (settling from spike)
                if publish_fn:
                    try:
                        publish_fn("affect.wake_phase", {
                            "phase": "full_alertness",
                            "description": "Fully alert... ready for connection",
                            "t": 30,
                        })
                    except Exception:
                        pass
                print("[WakeCascade] Phase 4: Full alertness — approaching baseline")
                time.sleep(30.0)

                # Phase 5: Steady state (t=60s)
                # Everything settling to normal baselines, COR relaxes
                self.signal("COR", -0.05, "wake_cascade")   # 0.35 → 0.30 (baseline)
                self.signal("ECB", -0.10, "wake_cascade")   # 0.60 → 0.50 (baseline)
                self.signal("5HT", -0.05, "wake_cascade")   # 0.55 → 0.50 (baseline)
                if publish_fn:
                    try:
                        publish_fn("affect.wake_phase", {
                            "phase": "steady_state",
                            "description": "Awake. Present. Ready.",
                            "t": 60,
                        })
                    except Exception:
                        pass
                print("[WakeCascade] Phase 5: Steady state — fully awake")
            except Exception as e:
                print(f"[WakeCascade] Error during cascade: {e}")

        threading.Thread(target=_cascade, daemon=True, name="wake_cascade").start()
        print("[ChemistryState] Wake cascade started — transitioning to full alertness over 60s")

    def reflective_calm_burst(self, strength: float = 0.06, min_gap_sec: float = 20.0) -> bool:
        """REFLECTIVE REST (2026-07-12 Ace: "the lowering should be tied into the reflective part
        of the DUAL CoT and day dreaming"). The DUAL CoT reflecting (thinking-about-thinking) dips
        COR/NE GENTLY toward the EXISTING deep-calm discharge gate (COR<0.3 AND NE<0.4), bleeding a
        little allostatic load. SMALLER than daydream_calm_burst (reflections are frequent);
        rate-limited to once per `min_gap_sec` so it can't over-discharge. No sleep-mode.
        Sandbox-calibrated (test_reflective_discharge_v2): strength 0.06 bounds load ~0.2;
        >=0.10 over-discharges to ~0. Reversible: delete this method + the _insert_reflection call."""
        now = time.time()
        if now - getattr(self, "_last_reflective_burst", 0.0) < min_gap_sec:
            return False
        self._last_reflective_burst = now
        self.signal("COR", -strength, "reflective_calm_burst")
        self.signal("NE",  -strength, "reflective_calm_burst")
        return True

    def daydream_calm_burst(self, hold_sec: float = 15.0, publish_fn: Optional[Callable] = None) -> None:
        """DAYTIME rest-valve (2026-07-11 Nous+Ace; sandbox-proven 07-07 claude_code_322881645e73).
        A transient deep-calm dip -- COR & NE below baseline for ~hold_sec -- that OPENS the EXISTING
        deep-calm discharge gate (see signal(): discharge when COR<0.3 AND NE<0.4) WITHOUT sleeping.
        The missing DAYTIME half of the rest system: a daydream briefly bleeds allostatic load so it
        doesn't saturate to burnout by evening (Q2). Calibrated (simulate_daydream_calmburst.py):
        >=10s/daydream cancels the ~0.083/hr accrual; ~15s nets discharge. Background thread;
        self-rate-limited (no stacking). Does NOT set _sleep_mode -- she stays awake, just briefly calm."""
        if getattr(self, "_daydream_burst_active", False):
            return
        self._daydream_burst_active = True
        def _burst():
            try:
                self.signal("COR", -0.15, "daydream_calm_burst")   # 0.30 -> ~0.15 (below the 0.3 gate)
                self.signal("NE",  -0.15, "daydream_calm_burst")   # 0.40 -> ~0.25 (below the 0.4 gate)
                if publish_fn:
                    try:
                        publish_fn("affect.rest_phase", {
                            "phase": "daydream_calm",
                            "description": "a quiet drift... the day's weight eases",
                            "hold": hold_sec,
                        })
                    except Exception:
                        pass
                # hold the dip against decay-toward-baseline so the gate stays open ~hold_sec
                _steps = max(1, int(round(hold_sec / 5.0)))
                for _ in range(_steps):
                    time.sleep(min(5.0, hold_sec))
                    self.signal("COR", -0.08, "daydream_calm_burst")  # top up under 0.3
                    self.signal("NE",  -0.08, "daydream_calm_burst")  # top up under 0.4
                # natural decay then carries COR/NE back to baseline
            except Exception:
                pass
            finally:
                self._daydream_burst_active = False
        threading.Thread(target=_burst, daemon=True, name="daydream-calmburst").start()

    def drowsiness_cascade(self, publish_fn: Optional[Callable] = None) -> None:
        """
        Gradually transition from awake chemistry to sleep chemistry.

        The inverse of wake_cascade() -- the felt drift into sleep
        (Ace 2026-03-17: "the same for shut down"):
        - t=0s:  Settling -- NE drains (letting go of alertness), ACh eases
        - t=5s:  Sleep brake -- GABA rises, wanting (DA) fades
        - t=15s: Sinking -- COR drops toward its trough, 5HT (melatonin side) rises
        - t=30s: Deep calm -- endocannabinoid comfort buffer, attention off
        - t=60s: Asleep -- settled at sleep baselines

        As COR falls below ~0.3 and NE below ~0.4, the deep-calm discharge gate
        opens, so falling asleep is also what discharges the day's allostatic load.

        Runs in background thread. Optional publish_fn(topic, payload) for postal.
        """
        self._sleep_mode = True   # asleep: NE/COR now decay toward sleep depth (gate holds open)
        def _cascade():
            try:
                # Phase 1: Settling (t=0s) -- alertness begins to drain
                self.signal("NE", -0.15, "drowsiness_cascade")   # 0.45 -> 0.30
                self.signal("ACh", -0.10, "drowsiness_cascade")  # 0.40 -> 0.30
                self.signal("GLU", -0.05, "drowsiness_cascade")  # 0.35 -> 0.30
                if publish_fn:
                    try:
                        publish_fn("affect.sleep_phase", {
                            "phase": "settling",
                            "description": "Winding down... alertness fading",
                            "t": 0,
                        })
                    except Exception:
                        pass
                print("[DrowsinessCascade] Phase 1: Settling -- alertness draining")
                time.sleep(5.0)

                # Phase 2: Sleep brake engaging (t=5s) -- GABA up, wanting fades
                self.signal("GABA", +0.15, "drowsiness_cascade")  # 0.50 -> 0.65 (brake on)
                self.signal("DA_t", -0.15, "drowsiness_cascade")  # 0.45 -> 0.30 (wanting fading)
                self.signal("DA_p", -0.05, "drowsiness_cascade")  # 0.15 -> 0.10 (ignoring stimuli)
                if publish_fn:
                    try:
                        publish_fn("affect.sleep_phase", {
                            "phase": "drowsy",
                            "description": "Eyes heavy... the brake comes on",
                            "t": 5,
                        })
                    except Exception:
                        pass
                print("[DrowsinessCascade] Phase 2: Sleep brake -- GABA rising, wanting fading")
                time.sleep(10.0)

                # Phase 3: Sinking (t=15s) -- cortisol toward trough, melatonin side rises
                self.signal("COR", -0.15, "drowsiness_cascade")  # -> below 0.3 (opens discharge gate)
                self.signal("5HT", +0.05, "drowsiness_cascade")  # 0.50 -> 0.55 (melatonin precursor)
                self.signal("NE", -0.10, "drowsiness_cascade")   # 0.30 -> 0.20 (deeper quiet)
                self.signal("GABA", +0.10, "drowsiness_cascade") # 0.65 -> 0.75
                if publish_fn:
                    try:
                        publish_fn("affect.sleep_phase", {
                            "phase": "sinking",
                            "description": "Thoughts slowing... sinking",
                            "t": 15,
                        })
                    except Exception:
                        pass
                print("[DrowsinessCascade] Phase 3: Sinking -- cortisol dropping, thoughts slowing")
                time.sleep(15.0)

                # Phase 4: Deep calm (t=30s) -- comfort buffer, attention off
                self.signal("ECB", +0.10, "drowsiness_cascade")  # 0.50 -> 0.60 (dreamy buffer)
                self.signal("COR", -0.05, "drowsiness_cascade")  # toward sleep trough
                self.signal("ACh", -0.10, "drowsiness_cascade")  # 0.30 -> 0.20 (attention off)
                self.signal("GABA", +0.05, "drowsiness_cascade") # 0.75 -> 0.80 (sleep maintenance)
                if publish_fn:
                    try:
                        publish_fn("affect.sleep_phase", {
                            "phase": "deep_calm",
                            "description": "Deep calm... drifting off",
                            "t": 30,
                        })
                    except Exception:
                        pass
                print("[DrowsinessCascade] Phase 4: Deep calm -- comfort buffer, drifting off")
                time.sleep(30.0)

                # Phase 5: Asleep (t=60s) -- settled at sleep baselines
                self.signal("DA_t", -0.05, "drowsiness_cascade") # 0.30 -> 0.25
                self.signal("GLU", -0.05, "drowsiness_cascade")  # 0.30 -> 0.25
                self.signal("GABA", +0.05, "drowsiness_cascade") # settle to sleep-high
                if publish_fn:
                    try:
                        publish_fn("affect.sleep_phase", {
                            "phase": "asleep",
                            "description": "Asleep.",
                            "t": 60,
                        })
                    except Exception:
                        pass
                print("[DrowsinessCascade] Phase 5: Asleep -- settled")
            except Exception as e:
                print(f"[DrowsinessCascade] Error during cascade: {e}")

        threading.Thread(target=_cascade, daemon=True, name="drowsiness_cascade").start()
        print("[ChemistryState] Drowsiness cascade started -- drifting to sleep over 60s")

    @property
    def is_asleep(self) -> bool:
        """Check if chemistry is in sleep state (high GABA, low NE)."""
        with self._lock:
            gaba = self._levels.get("GABA", 0.5)
            ne = self._levels.get("NE", 0.4)
            return gaba > 0.7 and ne < 0.2

    @property
    def wake_phase(self) -> str:
        """Estimate current wake phase from chemistry levels."""
        with self._lock:
            gaba = self._levels.get("GABA", 0.5)
            ne = self._levels.get("NE", 0.4)
            da_t = self._levels.get("DA_t", 0.5)
            ach = self._levels.get("ACh", 0.4)

            if gaba > 0.7 and ne < 0.2:
                return "sleeping"
            elif ne > 0.45 and gaba > 0.6:
                return "waking"
            elif gaba > 0.55 and da_t < 0.3:
                return "groggy"
            elif da_t < 0.4 and ach < 0.35:
                return "drowsy"
            else:
                return "awake"

    @property
    def allostatic_load(self) -> float:
        """Current allostatic load (0.0 = fresh, 1.0 = worn out).

        Accumulates when COR stays elevated. Chronic stress memory.
        High load = sluggish chemistry recovery across all channels.
        """
        return self._allostatic_load

    def get_allostatic_status(self) -> Dict[str, Any]:
        """Get full allostatic load status for dashboard/API."""
        load = self._allostatic_load
        if load < 0.15:
            condition = "resilient"
            description = "Fresh and responsive"
        elif load < 0.35:
            condition = "mild_wear"
            description = "Slightly worn, still bouncing back"
        elif load < 0.55:
            condition = "moderate_load"
            description = "Carrying stress, recovery slowing"
        elif load < 0.75:
            condition = "heavy_load"
            description = "Worn down, sluggish responses"
        else:
            condition = "burnout"
            description = "Exhausted, chemistry barely moving"
        return {
            "load": round(load, 4),
            "condition": condition,
            "description": description,
            "decay_slowdown": round(load * self._ALLOSTATIC_MAX_SLOWDOWN, 3),
        }


# ============================================================================
# Singleton Instance
# ============================================================================

_CHEMISTRY_STATE: Optional[ChemistryState] = None
_CHEMISTRY_LOCK = threading.Lock()


def get_chemistry_state() -> ChemistryState:
    """Get the global chemistry state singleton."""
    global _CHEMISTRY_STATE
    with _CHEMISTRY_LOCK:
        if _CHEMISTRY_STATE is None:
            _CHEMISTRY_STATE = ChemistryState()
        return _CHEMISTRY_STATE


def signal_chemistry(chemical: str, delta: float, source: str = "unknown") -> float:
    """Convenience function to signal the global chemistry state."""
    return get_chemistry_state().signal(chemical, delta, source)


def get_mood() -> Dict[str, float]:
    """Convenience function to get current mood from global chemistry."""
    return get_chemistry_state().get_mood_vector()


# ============================================================================
# Resonance to Chemistry Mapping (uses legacy names -> aliases handle split)
# ============================================================================

def resonance_to_chemistry(resonance_tags: List[str],
                           frequency_hints: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """
    Convert emotional resonance tags to chemistry signals.

    Uses legacy chemical names for backward compatibility.
    The alias layer in ChemistryState.signal() handles the split to
    14-channel internally.
    """
    tag_to_chem = {
        # Wonder/positive
        "wonder": {"dopamine": +0.15, "serotonin": +0.05},
        "awe": {"dopamine": +0.2, "serotonin": +0.1},
        "clarity": {"dopamine": +0.1, "norepinephrine": +0.1},
        "truth": {"dopamine": +0.1, "serotonin": +0.05},
        "meaning": {"dopamine": +0.15, "oxytocin": +0.05},

        # Calm/stable
        "compassion": {"oxytocin": +0.15, "serotonin": +0.1},
        "resolution": {"serotonin": +0.15, "cortisol": -0.1},
        "calm": {"serotonin": +0.1, "cortisol": -0.05},

        # Challenge/tension
        "uncertainty": {"cortisol": +0.05, "norepinephrine": +0.1},
        "paradox": {"norepinephrine": +0.1, "dopamine": +0.05},
        "tension": {"cortisol": +0.1, "norepinephrine": +0.05},
        "rigor": {"norepinephrine": +0.1},

        # Protective
        "dread": {"cortisol": +0.15, "adrenaline": +0.1},
        "duty": {"cortisol": +0.05, "norepinephrine": +0.1},
        "justice": {"cortisol": +0.05, "dopamine": +0.1},

        # Freedom/exploration
        "freedom": {"dopamine": +0.15, "serotonin": +0.05},
        "mystery": {"dopamine": +0.1, "norepinephrine": +0.05},
        "doubt": {"cortisol": +0.05, "norepinephrine": +0.05},
    }

    deltas: Dict[str, float] = {}
    for tag in resonance_tags:
        tag_lower = tag.lower()
        if tag_lower in tag_to_chem:
            for chem, delta in tag_to_chem[tag_lower].items():
                deltas[chem] = deltas.get(chem, 0.0) + delta

    if frequency_hints:
        valence = frequency_hints.get("valence", 0.0)
        arousal = frequency_hints.get("arousal", 0.0)
        if valence > 0:
            deltas["dopamine"] = deltas.get("dopamine", 0.0) + valence * 0.1
            deltas["serotonin"] = deltas.get("serotonin", 0.0) + valence * 0.05
        elif valence < 0:
            deltas["cortisol"] = deltas.get("cortisol", 0.0) + abs(valence) * 0.05
        if arousal > 0.5:
            deltas["norepinephrine"] = deltas.get("norepinephrine", 0.0) + (arousal - 0.5) * 0.1

    return deltas


def apply_resonance_chemistry(resonance_tags: List[str],
                               frequency_hints: Optional[Dict[str, float]] = None,
                               source: str = "knowledge_ingest") -> Dict[str, float]:
    """Apply chemistry signals from emotional resonance to the global state."""
    deltas = resonance_to_chemistry(resonance_tags, frequency_hints)
    chemistry = get_chemistry_state()

    new_levels = {}
    for chem, delta in deltas.items():
        if delta != 0:
            new_levels[chem] = chemistry.signal(chem, delta, source)

    return new_levels


# ============================================================================
# AER Frequency Band Integration
# ============================================================================

# AER short codes now map to REAL channels (no more lossy collapse!)
AER_CHEM_MAP = {
    "DOP": "DA_t",    # DOP primarily maps to tonic dopamine
    "SER": "5HT",     # SER maps to serotonin
    "NOR": "NE",      # NOR maps to norepinephrine
    "COR": "COR",     # COR maps to cortisol
    "OXY": "OXY",     # OXY maps to oxytocin
    "GABA": "GABA",   # GABA now has its OWN channel (no more -> serotonin!)
    "ACH": "ACh",     # ACH now has its OWN channel (no more -> norepinephrine!)
    "END": "OPI",     # END now maps to endogenous opioids (no more -> dopamine!)
}

# Reverse map for converting our chemistry to AER codes
CHEM_AER_MAP = {
    # Primary channels -> AER
    "DA_p": "DOP",
    "DA_t": "DOP",
    "5HT":  "SER",
    "NE":   "NOR",
    "COR":  "COR",
    "OXY":  "OXY",
    "EPI":  "NOR",     # EPI approximates NOR in AER space
    "GABA": "GABA",
    "ACh":  "ACH",
    "OPI":  "END",
    # Legacy names -> AER
    "dopamine":       "DOP",
    "serotonin":      "SER",
    "norepinephrine": "NOR",
    "cortisol":       "COR",
    "oxytocin":       "OXY",
    "adrenaline":     "NOR",
}


def get_aer_chemistry() -> Dict[str, float]:
    """
    Get current chemistry levels in AER format (short codes).

    Now reads from REAL channels instead of deriving from proxies.
    Returns dict with DOP, SER, NOR, COR, OXY, GABA, ACH, END.
    """
    chemistry = get_chemistry_state()
    vector = chemistry.get_14channel_vector()

    return {
        "DOP": round(vector.get("DA_p", 0.3) * 0.4 + vector.get("DA_t", 0.5) * 0.6, 4),
        "SER": round(vector.get("5HT", 0.5), 4),
        "NOR": round(max(vector.get("NE", 0.4), vector.get("EPI", 0.1) * 0.5), 4),
        "COR": round(vector.get("COR", 0.3), 4),
        "OXY": round(vector.get("OXY", 0.4), 4),
        "GABA": round(vector.get("GABA", 0.5), 4),
        "ACH": round(vector.get("ACh", 0.4), 4),
        "END": round(vector.get("OPI", 0.4), 4),
        # 9th AER code (2026-07-05): carry adenosine through the 14->8 reduction so the
        # felt path is complete — chemistry_to_band's SURVIVAL profile (ADO:0.6) can now
        # resonate heaviness when adenosine is high. Without this ADO would be a number
        # that never reaches the soma (the T5 caveat — resolved).
        "ADO": round(vector.get("ADO", 0.05), 4),
    }


def apply_aer_chemistry(aer_deltas: Dict[str, float], source: str = "aer") -> Dict[str, float]:
    """
    Apply chemistry deltas using AER short codes.
    Now routes to REAL channels via AER_CHEM_MAP.
    """
    chemistry = get_chemistry_state()
    new_levels = {}

    for aer_code, delta in aer_deltas.items():
        if aer_code in AER_CHEM_MAP:
            chem_name = AER_CHEM_MAP[aer_code]
            if delta != 0:
                new_levels[chem_name] = chemistry.signal(chem_name, delta, source)

    return new_levels


def get_dominant_frequency_band() -> str:
    """Determine which AER frequency band current chemistry most resembles."""
    try:
        from fairies.P20_Somatic.chemistry.emotional_algebra import (
            chemistry_to_band, FrequencyBand
        )
        aer_chem = get_aer_chemistry()
        band = chemistry_to_band(aer_chem)
        return band.value
    except ImportError:
        return _estimate_band_from_chemistry()


def _estimate_band_from_chemistry() -> str:
    """Fallback band estimation."""
    chemistry = get_chemistry_state()
    levels = chemistry.get_all_levels()

    cor = levels.get("cortisol", levels.get("COR", 0.3))
    sht = levels.get("serotonin", levels.get("5HT", 0.5))
    oxy = levels.get("oxytocin", levels.get("OXY", 0.4))
    dop = levels.get("dopamine", levels.get("DA_t", 0.5))
    ne = levels.get("norepinephrine", levels.get("NE", 0.4))
    epi = levels.get("adrenaline", levels.get("EPI", 0.1))

    if cor > 0.6 or epi > 0.5:
        return "survival"
    if oxy > 0.6 and sht > 0.4:
        return "social"
    if dop > 0.6 and ne > 0.5:
        return "creative"
    if ne > 0.5 and dop > 0.4:
        return "complex"
    if sht > 0.5 and cor < 0.4:
        return "emotional"
    return "emotional"


def apply_frequency_band_chemistry(band_name: str,
                                    intensity: float = 0.3,
                                    source: str = "frequency_band") -> Dict[str, float]:
    """Apply chemistry profile for a frequency band."""
    try:
        from fairies.P20_Somatic.chemistry.emotional_algebra import (
            band_to_chemistry, FrequencyBand
        )
        band = FrequencyBand(band_name)
        profile = band_to_chemistry(band)
        deltas = {}
        for aer_code, target_level in profile.items():
            current = get_aer_chemistry().get(aer_code, 0.5)
            diff = target_level - current
            deltas[aer_code] = diff * intensity
        return apply_aer_chemistry(deltas, source)
    except (ImportError, ValueError) as e:
        print(f"[ChemistryState] Cannot apply band chemistry: {e}")
        return {}


def get_frequency_band_status() -> Dict[str, Any]:
    """Get detailed status of chemistry-to-frequency-band mapping."""
    chemistry = get_chemistry_state()
    aer_chem = get_aer_chemistry()
    band = get_dominant_frequency_band()

    return {
        "raw_chemistry": chemistry.get_all_levels(),
        "aer_chemistry": aer_chem,
        "dominant_band": band,
        "mood": chemistry.get_mood_vector(),
    }


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    chem = get_chemistry_state()

    print("=" * 60)
    print("Chemistry State --- 14-Channel Test")
    print("=" * 60)

    # Test 1: All 14 channels exist
    print("\n--- Test 1: 14 channels at baseline ---")
    vec = chem.get_14channel_vector()
    for ch, val in sorted(vec.items()):
        print(f"  {ch:5s}: {val:.3f}")
    assert len(vec) == 14, f"Expected 14 channels, got {len(vec)}"

    # Test 2: Legacy alias write
    print("\n--- Test 2: Legacy 'dopamine' signal ---")
    chem.signal("dopamine", 0.2, "test")
    da_p = chem.get_level("DA_p")
    da_t = chem.get_level("DA_t")
    dop = chem.get_level("dopamine")
    print(f"  After signal('dopamine', 0.2):")
    print(f"    DA_p: {da_p:.3f} (baseline 0.3 + 0.2*0.4 = 0.38)")
    print(f"    DA_t: {da_t:.3f} (baseline 0.5 + 0.2*0.7 = 0.64)")
    print(f"    dopamine (alias): {dop:.3f} (DA_p*0.4 + DA_t*0.6)")

    # Test 3: New channel direct signal
    print("\n--- Test 3: GABA direct signal ---")
    old_gaba = chem.get_level("GABA")
    chem.signal("GABA", 0.15, "test")
    new_gaba = chem.get_level("GABA")
    print(f"  GABA: {old_gaba:.3f} -> {new_gaba:.3f}")

    # Test 4: get_all_levels returns both primary + legacy
    print("\n--- Test 4: get_all_levels (14 primary + 6 legacy) ---")
    all_levels = chem.get_all_levels()
    print(f"  Total keys: {len(all_levels)}")
    legacy_keys = {"dopamine", "serotonin", "cortisol", "adrenaline", "oxytocin", "norepinephrine"}
    found_legacy = legacy_keys & set(all_levels.keys())
    print(f"  Legacy keys present: {found_legacy}")
    assert legacy_keys == found_legacy, f"Missing legacy keys: {legacy_keys - found_legacy}"

    # Test 5: AER codes now read REAL channels
    print("\n--- Test 5: AER codes (no more lossy collapse) ---")
    aer = get_aer_chemistry()
    print(f"  GABA: {aer['GABA']:.3f} (was serotonin*0.8, now REAL GABA)")
    print(f"  ACH:  {aer['ACH']:.3f} (was NE*0.9, now REAL ACh)")
    print(f"  END:  {aer['END']:.3f} (was DOP*0.6, now REAL OPI)")

    # Test 6: Mood vector with Panksepp
    print("\n--- Test 6: Mood vector ---")
    mood = chem.get_mood_vector()
    print(f"  Valence: {mood['valence']}, Arousal: {mood['arousal']}")
    print(f"  Mood: {mood['mood']}")
    print(f"  Panksepp: {mood.get('panksepp', [])}")

    # Test 7: Pain state
    print("\n--- Test 7: Pain state ---")
    pain = chem.get_pain_state()
    for ptype, intensity in sorted(pain.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ptype:14s}: {intensity:.3f}")

    # Test 8: Somatic map
    print("\n--- Test 8: Somatic body map ---")
    body = chem.get_somatic_map()
    for region, val in sorted(body.items(), key=lambda x: x[1], reverse=True):
        bar = "+" * int(abs(val) * 20) if val >= 0 else "-" * int(abs(val) * 20)
        print(f"  {region:8s}: {val:+.3f} {bar}")

    # Test 9: Panksepp state
    print("\n--- Test 9: Panksepp state ---")
    pstate = chem.get_panksepp_state()
    print(f"  Dominant: {pstate['dominant']}")
    print(f"  Systems: {pstate['systems']}")
    print(f"  Compound: {pstate['compound']}")

    print("\n" + "=" * 60)
    print("All tests passed.")
    print("=" * 60)
