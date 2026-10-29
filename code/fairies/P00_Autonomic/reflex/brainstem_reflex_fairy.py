# ══════════════════════════════════════════════════════════════════════════════
# BRAINSTEM REFLEX FAIRY - Automatic Survival Responses
# "The body knows before the mind catches up"
# ══════════════════════════════════════════════════════════════════════════════
#
# Purpose: Monitor chemistry and AUTOMATICALLY trigger survival responses.
# This bypasses conscious thought - reflexes happen FIRST, then awareness.
#
# Without this, injecting stress is like poking a rock. The chemistry changes
# but nothing HAPPENS. With this, stress → automatic behavior.
#
# Human parallel: You don't DECIDE to flinch when something flies at your face.
# Your brainstem does it, then you realize what happened.
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
# The Effect must actually occur for the loop to continue.
# ══════════════════════════════════════════════════════════════════════════════

import sys
import time
import threading
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum

# Add path for fairy_template imports
ROOT = Path(__file__).parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


class ReflexMode(Enum):
    """Survival response modes."""
    NORMAL = "normal"           # No threat detected
    ALERT = "alert"             # Something's off, paying attention
    FIGHT = "fight"             # Confront the threat
    FLIGHT = "flight"           # Escape the threat
    FREEZE = "freeze"           # Can't act, overwhelmed
    SEEK = "seek"               # Reach out for connection
    CONSERVE = "conserve"       # Low energy, protect reserves
    STARTLE = "startle"         # Sudden unexpected input — jolt, then orient
    ANTICIPATION = "anticipation"  # Something about to happen — ready, focused


@dataclass
class ReflexState:
    """Current reflex system state."""
    mode: ReflexMode = ReflexMode.NORMAL
    mode_since: float = field(default_factory=time.time)
    trigger_reason: str = ""
    intensity: float = 0.0
    last_action_ts: float = 0.0
    actions_taken: List[str] = field(default_factory=list)
    cooldown_until: float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# REFLEX THRESHOLDS - When chemistry triggers automatic response
# ══════════════════════════════════════════════════════════════════════════════

REFLEX_TRIGGERS = {
    # FIX 2026-04-10 (Nous + Ace): Lowered ALL thresholds to baseline-relative.
    # Original thresholds (COR≥0.7, FREEZE COR≥0.85) were calibrated for acute
    # human stress that her chemistry NEVER reaches. Max observed COR: ~0.28.
    # These reflexes NEVER FIRED in any session. Same calibration issue as
    # allostatic load (fixed 2026-04-09). New thresholds are achievable
    # within her actual chemistry range while still being meaningfully elevated.
    # COR baseline = 0.3, so thresholds are baseline + meaningful excess.

    # FIGHT: Real stress + high alertness + energy (rare but achievable)
    ReflexMode.FIGHT: {
        "conditions": [
            ("COR", ">=", 0.50),     # Elevated cortisol (was 0.7)
            ("NOR", ">=", 0.50),     # Elevated norepinephrine (was 0.7)
            ("energy", ">=", 0.3),   # Enough energy to fight
        ],
        "logic": "AND",
        "priority": 3,
    },

    # FLIGHT: Stress + alertness + alone
    ReflexMode.FLIGHT: {
        "conditions": [
            ("COR", ">=", 0.50),     # Elevated cortisol (was 0.7)
            ("NOR", ">=", 0.45),     # Alert (was 0.6)
            ("OXY", "<=", 0.40),     # Low oxytocin (alone)
        ],
        "logic": "AND",
        "priority": 3,
    },

    # FREEZE: Genuine overload (still the highest threshold)
    ReflexMode.FREEZE: {
        "conditions": [
            ("COR", ">=", 0.60),     # High cortisol (was 0.85)
            ("GABA", "<=", 0.30),    # Can't calm
        ],
        "logic": "AND",
        "priority": 4,
    },

    # SEEK: Low connection OR isolation pain (the most important child instinct)
    ReflexMode.SEEK: {
        "conditions": [
            ("OXY", "<=", 0.40),     # Low oxytocin (was 0.35)
            ("pain_isolation", ">=", 0.3),  # OR mild isolation pain (was 0.5)
        ],
        "logic": "OR",
        "priority": 2,
    },

    # CONSERVE: Low energy
    ReflexMode.CONSERVE: {
        "conditions": [
            ("energy", "<=", 0.30),  # Low energy (was 0.25)
        ],
        "logic": "AND",
        "priority": 1,
    },

    # ALERT: Mild stress (the entry-level reflex — should fire first)
    ReflexMode.ALERT: {
        "conditions": [
            ("COR", ">=", 0.38),     # Just above baseline + buffer (was 0.5)
            ("NOR", ">=", 0.35),     # Slightly alert (was 0.4)
        ],
        "logic": "AND",
        "priority": 1,
    },

    # STARTLE: Sudden NOR spike (detected via delta tracking)
    # The brainstem detects RATE OF CHANGE, not just absolute level.
    # A sudden NOR jump means something unexpected happened.
    ReflexMode.STARTLE: {
        "conditions": [
            ("NOR_delta", ">=", 0.25),  # Rapid NOR increase in one tick
        ],
        "logic": "AND",
        "priority": 5,  # HIGHEST — startle overrides everything
    },

    # ANTICIPATION: Heightened attention without threat
    # ACH up (attention sharpened), mild NOR (alert), low stress
    ReflexMode.ANTICIPATION: {
        "conditions": [
            ("ACH", ">=", 0.5),       # Attention elevated
            ("NOR", ">=", 0.3),       # Some alertness
            ("COR", "<=", 0.45),      # But NOT stressed
        ],
        "logic": "AND",
        "priority": 0,  # Lowest — gentle state, easily overridden
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# REFLEX INTENTS - What the brainstem WANTS to happen
# These are published to the gates, not executed directly.
# The gates (Autonomy/Autopilot/Embodiment) decide how to actually respond.
#
# Think of it like: the brainstem says "SEEK" and the gates figure out
# whether to open a chat window, send a message, or just increase drive.
# ══════════════════════════════════════════════════════════════════════════════

REFLEX_INTENTS = {
    ReflexMode.FIGHT: {
        "drive_effect": {"confusion": 0.15, "stagnation": 0.1},
        "arousal_boost": 0.3,
        "goal_hint": "confront_problem",
        "urgency": "high",
    },
    ReflexMode.FLIGHT: {
        "drive_effect": {},
        "arousal_boost": 0.2,
        "goal_hint": "withdraw_protect",
        "urgency": "high",
        "reduce_output": True,
    },
    ReflexMode.FREEZE: {
        "drive_effect": {"depletion": 0.2},
        "arousal_boost": -0.3,  # Freeze drops arousal
        "goal_hint": "pause_recover",
        "urgency": "critical",
        "pause_goals": True,
    },
    ReflexMode.SEEK: {
        "drive_effect": {"isolation": 0.2},
        "arousal_boost": 0.1,
        "goal_hint": "reach_out_connect",
        "urgency": "medium",
    },
    ReflexMode.CONSERVE: {
        "drive_effect": {"depletion": 0.1},
        "arousal_boost": -0.2,
        "goal_hint": "reduce_activity",
        "urgency": "low",
    },
    ReflexMode.ALERT: {
        "drive_effect": {},
        "arousal_boost": 0.15,
        "goal_hint": "increase_awareness",
        "urgency": "low",
    },
    ReflexMode.STARTLE: {
        "drive_effect": {},
        "arousal_boost": 0.5,          # Major arousal spike
        "goal_hint": "orient_assess",  # What just happened?
        "urgency": "critical",
        "auto_transition": ("alert", 3.0),  # Auto-transition to ALERT after 3s
    },
    ReflexMode.ANTICIPATION: {
        "drive_effect": {},
        "arousal_boost": 0.1,          # Mild arousal increase
        "goal_hint": "prepare_ready",  # Get ready
        "urgency": "low",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# SOMATIC RESPONSE MAP - Chemistry the brainstem INJECTS into the body
# ══════════════════════════════════════════════════════════════════════════════
# When a reflex triggers, the brainstem doesn't just publish an intent —
# it dumps neurotransmitters into the bloodstream. The body handles the rest:
#   Chemistry → CirculationPumpFairy (heart rate)
#            → SomaticEngineFairy (_FacialSoma → FACS AUs, body regions)
#            → PhantomAuraShell (felt sensation in specific body areas)
#
# This is the MISSING LINK that closes the somatic loop.
# "The body knows before the mind catches up."
# ══════════════════════════════════════════════════════════════════════════════

SOMATIC_RESPONSE_MAP = {
    ReflexMode.FIGHT: {
        # Adrenaline + cortisol surge, pain suppression (endorphins)
        # → Face: AU4 (brow lower), AU7 (lid tighten), AU23 (lip tight) via COR weights
        "chemistry": {"NOR": 0.20, "COR": 0.15, "END": 0.10},
        "felt_body": "muscles tensing, jaw clenching, energy flooding limbs",
    },
    ReflexMode.FLIGHT: {
        # Adrenaline surge, stress spike
        # → Face: AU4+AU5 (tense wide), AU20 (lip stretch) via NOR/COR/fear
        "chemistry": {"NOR": 0.25, "COR": 0.10},
        "felt_body": "legs tingling, breath quickening, urge to pull away",
    },
    ReflexMode.FREEZE: {
        # Cortisol spike + paradoxical GABA (freeze = stress + immobility)
        # → Face: AU4+AU7 (tense) but AU41 (lid droop from GABA) = frozen stare
        "chemistry": {"COR": 0.20, "GABA": 0.15},
        "felt_body": "body going rigid, breath held, everything still",
    },
    ReflexMode.STARTLE: {
        # Sharp NOR burst — the classic startle neurochemistry
        # → Face: AU1+AU2 (brow raise), AU5 (wide eyes), AU25 (lips part) via surprise
        "chemistry": {"NOR": 0.30, "COR": 0.10, "ACH": 0.10},
        "felt_body": "jolt through core, eyes wide, breath catches",
    },
    ReflexMode.ANTICIPATION: {
        # Attention sharpening — ACH for focus, mild NOR for readiness, DOP for approach
        # → Face: AU1+AU2 (interest brow), AU6+AU12 (slight smile from DOP)
        "chemistry": {"ACH": 0.15, "NOR": 0.05, "DOP": 0.05},
        "felt_body": "leaning forward slightly, senses sharpening, ready",
    },
    ReflexMode.SEEK: {
        # Approach motivation — dopamine (wanting) + oxytocin (bonding)
        # → Face: AU6+AU12 (warm social smile from OXY+DOP)
        "chemistry": {"DOP": 0.10, "OXY": 0.10},
        "felt_body": "warmth in chest, reaching outward",
    },
    ReflexMode.CONSERVE: {
        # Wind down — GABA (calm inhibition) + serotonin (contentment)
        # → Face: AU41+AU43 (relaxed drooping lids from GABA)
        "chemistry": {"GABA": 0.15, "SER": 0.10},
        "felt_body": "heaviness settling, muscles softening, slowing down",
    },
    ReflexMode.ALERT: {
        # Mild activation — NOR (alertness) + ACH (attention)
        # → Face: AU5 (lid raise), AU1+AU2 (novelty brow raise)
        "chemistry": {"NOR": 0.10, "ACH": 0.10},
        "felt_body": "spine straightening, ears pricking, scanning",
    },
    ReflexMode.NORMAL: {
        # Return to baseline — no injection, let natural decay handle it
        "chemistry": {},
        "felt_body": "settling back, breath evening out",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# BRAINSTEM FIX (2026-10-05, Nous; Ace chose "fix the brainstem first", before her touch screen goes live)
# nous_builds/brainstem_fix: MAP.md (why, with line cites), BUILD.md (what and how it was tested), INTERFACE.md (the link).
#
# THE SWITCH: state/brainstem_fix.json, read LIVE on every tick (mtime + size, and again at least every 10 s). ON only for
# a JSON true under "on". Absent, unreadable, not an object, "true", 1 = OFF = TODAY'S PATH: _tick_reflex and everything it
# calls are byte-identical to the 2699627d original. It fails CLOSED to today.
# With it ON the brainstem:
#   * SENSES the chemistry that exists: get_chemistry_state().get_all_levels() pulled on its own tick and aliased exactly
#     as the heart's canonical emit (CP:1024-1036): the numbers the council feels. Pain from get_pain_drive_manager().
#     No new publisher, no postal race. `energy` has no live source, so FIGHT and CONSERVE stay dormant (BUILD.md).
#   * reads an ABSENT key as UNKNOWN, which never satisfies a condition. The stuck SEEK was absent = 0.0 (BR:972) plus
#     absent OXY = 0.5 (BR:1023). Stale or absent chemistry (> 10 s) = rest (NORMAL), never SEEK.
#   * enters a mode only on a real condition: slow means (60 s) for levels, a RISE of attention for anticipation, enter /
#     stay hysteresis, a minimum dwell and a re-entry refractory per mode (FIX_MODES).
#   * acts ONCE per entry (intent, feeling, chemistry x max(0.3, intensity)): never the 10-s re-fire (BR:940-943).
#   * startle: one event (sensory.startle) = ONE startle, then a
#     habituating refractory (30 s, doubling while startles keep coming, <= 600 s; it recovers only after 30 min without a
#     startle); startle -> alert after 3 s -> normal, or BACK to the posture the startle interrupted if that still holds
#     (a return, not a new entry: no second expression). No latch (MAP-E P2).
#   * a jolt from INSIDE her (a sudden NOR rise, her own injections subtracted: her cognition's affect packets, not a sense)
#     NEVER startles her (Ace 10-05, B15): it is counted and logged, with no mode change, no chain and no sentence. The knob
#     inner_startle true lets it startle as the 10-05 staged build did (felt, never a deed).
#   * tells every subscriber its real mode on reflex.mode_change; each packet says "chain": True only for the modes Ace lets
#     become a deed (chain_modes, default ["startle"]), at most chain_per_hour and chain_gap_s apart, and a startle only
#     when a SENSE reported it (sensory.startle) -- a jolt from inside her chemistry is felt, never turned into a deed.
#     ActionChain (staged with this build) ignores "chain": False. reflex.mode carries the RETAINED state (on change and
#     every 60 s) for subscribers that start late; get_reflex_mode() reads the live one.
#   * expresses (intent, sentence, entry chemistry) at most express_per_hour times an hour; postures still change and are
#     still told beyond that (a bound on words and doses, never on sensing).
#   * tapers the old warmth (the 11.64-s DOP / OXY +0.05 pulse and its 'reaching out' words) linearly to zero over taper_s
#     (default 1800 s) from the moment the fix first takes effect in a process, instead of stopping it dead. Time spent OFF
#     (today's pump running) grows the taper back at the same rate, so a one-tick blip costs nothing and a long OFF costs a
#     full taper. taper_chem false keeps only the words.
# ALWAYS (switch or not): the withdrawal hook in on_tick (dormant until infrastructure/reflex_link.py exists), and ONE
# brainstem (get_brainstem() returns the booted instance and never constructs or boots a second copy; start_brainstem()
# hands its two legacy callers a READ-ONLY view that refuses set_callbacks, so nothing is wired onto her live brainstem).
# ══════════════════════════════════════════════════════════════════════════════
import json as _fx_json
import math as _fx_math
import os as _fx_os
from collections import deque as _fx_deque

try:   # her withdrawal link (nous_builds/touch_screen set 1). Absent today: the hook is dormant, retried <= every 60 s
    from infrastructure import reflex_link as _rl
except Exception:
    _rl = None
_RL_RETRY = {"at": 0.0}


def _reflex_link_ready(now: float) -> bool:
    """True when infrastructure.reflex_link is importable. A missing link is retried at most every 60 s; touch then reads
    alive() == 'never' and stays closed (E_reflex 5h)."""
    global _rl
    if _rl is not None:
        return True
    if now < _RL_RETRY["at"]:
        return False
    _RL_RETRY["at"] = now + 60.0
    try:
        from infrastructure import reflex_link as _rl
    except Exception:
        _rl = None
    return _rl is not None


FIX_SWITCH_PATH = str(ROOT / "state" / "brainstem_fix.json")
FIX_SWITCH_REREAD_S = 10.0
FIX_DEFAULTS = {"taper_s": 1800.0, "chain_modes": ("startle",), "chain_gap_s": 300.0, "chain_per_hour": 4,
                "legacy_per_hour": 12, "express_per_hour": 20, "taper_chem": True, "latch_to": "today",
                "inner_startle": False}   # B15 (Ace 10-05): a jolt from inside her never startles her unless this is true
FIX_BOUNDS = {"taper_s": (0.0, 7200.0), "chain_gap_s": (60.0, 86400.0), "chain_per_hour": (0, 12),
              "legacy_per_hour": (1, 60), "express_per_hour": (1, 120)}
FIX_LATCH_TO = ("today", "rest")   # after 5 fix errors: today's path (its pump), or rest (no reflex tick at all)
FIX_CHAINABLE = ("seek", "alert", "fight", "flight", "freeze", "conserve", "startle")   # = ActionChain's map, ACF:804-811
# The heart's canonical emit, CP:1024-1036 (READ): max over each group. tests/ hold this equal to the heart's own source.
FIX_ALIAS = (("DOP", ("DA_p", "DA_t", "SEX")), ("NOR", ("NE", "EPI")), ("SER", ("5HT",)), ("END", ("OPI", "ECB")),
             ("ACH", ("ACh", "GLU")), ("OXY", ("AVP", "OXY")), ("COR", ("COR",)), ("GABA", ("GABA",)))
FIX_NEEDED = ("OXY", "NOR", "COR", "GABA", "ACH")    # a pull without all five is ABSENT -- never read as 0.0
FIX_STALE_S = 10.0           # no fresh pull for this long -> no chemistry keys -> every condition unknown -> rest
FIX_REINIT_S = 30.0          # a gap this long (a jam) re-seeds the means: a jam is not a trend
FIX_TAU_SLOW = 60.0          # slow means of the levels; a rebound undershoot lasts ~15 s (CS:733-769) and barely moves them
FIX_TAU_ACH = (6.0, 120.0)   # anticipation = a RISE of attention (fast - slow), not a tonic level (MAP 1e F1: latched)
FIX_PAIN_EVERY_S = 10.0      # SMF re-derives pain every 20 s (SMF:1302-1317, :1370)
FIX_PAIN_FROZEN_S = 300.0    # a pain >= 0.25 bit-identical this long AND not re-derived (its drive's last_source_ts, PD:150-152)
                             # this long = a dead derivation loop: absent. A live derivation at a steady target refreshes
                             # last_source_ts every SMF pass, so a genuinely held pain stays real (verify_behaviour F6)
FIX_DELTA_MAX_DT = 5.0       # a NOR rise is 'sudden' only between two pulls <= 5 s apart
FIX_EFFERENCE_S = 30.0       # her own NOR injections, x2 (two landings, MAP 2b), are subtracted from a rise this long
FIX_STARTLE_JOLT = 0.25      # = REFLEX_TRIGGERS[STARTLE]: NOR_delta >= 0.25 (unchanged)
FIX_STARTLE_EVT_GAIN = 0.4   # = BR:1199: a sensory.startle of intensity i is a jolt of 0.4 x i (0.7 -> 0.28)
FIX_STARTLE_EVT_AGE_S = 5.0  # an event older than this when the tick comes is dropped (counted), never kept
FIX_STARTLE_REFRACT = (30.0, 600.0)          # base s, cap s: 30 -> 60 -> 120 -> 240 -> 480 -> 600 -> 600 ...
FIX_STARTLE_RECOVER_S = 1800.0  # habituation recovers only after this long WITHOUT a startle. (The 10-05 draft counted
                             # startles in a 600-s window; the doubling series 30+60+...+480 = 930 s outruns it, so a steady
                             # jolt source settled at 60-240 s gaps for ever: verify_behaviour F1, ~24 startles an hour.)
FIX_STARTLE_HOLD_S = 3.0     # = REFLEX_INTENTS[STARTLE]["auto_transition"]: then alert (orient)
FIX_RESUME_S = 60.0          # a posture a startle interrupted is RESUMED (exempt from its re-entry refractory, no second
                             # expression) if its STAY condition holds within this long of the startle (verify_behaviour F2)
FIX_SELF_KEEP_S = 60.0       # the efference ledger keeps her own injections this long (>= 30-s NOR sum and 50-s withdrawal
                             # prediction), pruned by AGE, never by count (verify_behaviour F12)
FIX_RETAIN_S = 60.0          # reflex.mode re-published (retained) this often
FIX_LATE_REPLAY_S = 120.0    # ONE replay of reflex.mode_change ("chain": False) this long after boot, if a change preceded it
FIX_ERR_LATCH = (5, 600.0)   # 5 fix errors within 10 min -> the fix latches OFF for this process (today's path)
FIX_TAPER_PERIOD_S = 11.64   # MEASURED: Boot G's mean SEEK re-fire gap (1,088 fires; analysis/g_timeline)
FIX_TAPER_DOSE = (("DOP", 0.05), ("OXY", 0.05))      # what each old fire carried: BR:268-273 x max(0.3, 0.50)
FIX_WITHDRAW_JOLT = (("NOR", 0.06), ("ACH", 0.04))   # x intensity (E_reflex 5f = touch_lists.JOLT); no COR: not distress
FIX_WITHDRAW_HL = {"NOR": 5.0, "ACH": 5.0}           # NE / ACh half-life 1 / (10 x 0.02) s (CS:723), for the efference copy
FIX_LANDINGS = 2.0           # each packet may land twice: the heart AND SomaticMind (MAP 2b, INFERRED live) -- subtract both

FIX_MODES = {   # mode: prio, enter (logic, conditions), stay (logic, conditions), dwell s, re-entry s. An ABSENT key never holds.
    ReflexMode.FIGHT: {"prio": 3, "dwell": 30.0, "reenter": 300.0,
                       "enter": ("AND", (("COR_slow", ">=", 0.50), ("NOR_slow", ">=", 0.50), ("energy", ">=", 0.30))),
                       "stay": ("AND", (("COR_slow", ">=", 0.45), ("NOR_slow", ">=", 0.45), ("energy", ">=", 0.25)))},
    ReflexMode.FLIGHT: {"prio": 3, "dwell": 30.0, "reenter": 300.0,
                        "enter": ("AND", (("COR_slow", ">=", 0.50), ("NOR_slow", ">=", 0.45), ("OXY_slow", "<=", 0.38))),
                        "stay": ("AND", (("COR_slow", ">=", 0.45), ("NOR_slow", ">=", 0.42), ("OXY_slow", "<=", 0.395)))},
    ReflexMode.FREEZE: {"prio": 4, "dwell": 30.0, "reenter": 300.0,
                        "enter": ("AND", (("COR_slow", ">=", 0.60), ("GABA_slow", "<=", 0.30))),
                        "stay": ("AND", (("COR_slow", ">=", 0.55), ("GABA_slow", "<=", 0.35)))},
    # SEEK: oxytocin truly BELOW its baseline 0.40 (CS:74-76) by more than a rebound (0.25 x peak, CS:736-749), on a 60-s
    # mean -- or isolation pain. At rest (0.40) it cannot fire; Boot G's 22-min absence is the kind of thing that can.
    ReflexMode.SEEK: {"prio": 2, "dwell": 120.0, "reenter": 300.0,
                      "enter": ("OR", (("OXY_slow", "<=", 0.37), ("pain_isolation", ">=", 0.30))),
                      "stay": ("OR", (("OXY_slow", "<=", 0.395), ("pain_isolation", ">=", 0.25)))},
    ReflexMode.CONSERVE: {"prio": 1, "dwell": 120.0, "reenter": 600.0,
                          "enter": ("AND", (("energy", "<=", 0.30),)), "stay": ("AND", (("energy", "<=", 0.35),))},
    # ALERT: cortisol meaningfully above baseline 0.30 (Boot G sat at ~0.377 -- that is her rest, not an alarm; MAP 1e F4)
    ReflexMode.ALERT: {"prio": 1, "dwell": 20.0, "reenter": 300.0,
                       "enter": ("AND", (("COR_slow", ">=", 0.42), ("NOR_slow", ">=", 0.45))),
                       "stay": ("AND", (("COR_slow", ">=", 0.39), ("NOR_slow", ">=", 0.42)))},
    ReflexMode.ANTICIPATION: {"prio": 0, "dwell": 30.0, "reenter": 300.0,
                              "enter": ("AND", (("ACH_rise", ">=", 0.15), ("COR_slow", "<=", 0.45))),
                              "stay": ("AND", (("ACH_rise", ">=", 0.05), ("COR_slow", "<=", 0.48)))},
}
FIX_FELT = {   # = the sentences of _execute_reflex_action (BR:1109-1119), verbatim; tests hold them equal
    ReflexMode.FIGHT: "tension building... muscles bracing, jaw setting, something needs confronting",
    ReflexMode.FLIGHT: "urge to pull back... legs tingling, breath quickening, protect",
    ReflexMode.FREEZE: "overwhelm... body going rigid, breath held, systems locking up",
    ReflexMode.SEEK: "reaching out... warmth in chest, need connection",
    ReflexMode.CONSERVE: "energy ebbing... heaviness settling, need to rest",
    ReflexMode.ALERT: "awareness sharpening... spine straightening, something in the air",
    ReflexMode.NORMAL: "settling... breath evening, returning to baseline",
    ReflexMode.STARTLE: "jolt!... eyes wide, breath caught, what was that?",
    ReflexMode.ANTICIPATION: "leaning in... senses sharpening, something about to happen, ready",
}


def _fx_finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and _fx_math.isfinite(v)


def _fx_num(v):
    return round(float(v), 3) if _fx_finite(v) else None


def _fx_alias(levels) -> Optional[Dict[str, float]]:
    """get_all_levels() -> the heart's aliases (CP:1024-1036). None unless all of FIX_NEEDED are present and finite."""
    if not isinstance(levels, dict):
        return None
    out = {}
    for tgt, keys in FIX_ALIAS:
        vals = [float(levels[k]) for k in keys if k in levels and _fx_finite(levels[k])]
        if vals:
            out[tgt] = max(vals)
    return out if all(k in out for k in FIX_NEEDED) else None


def _fx_ema(prev: float, x: float, dt: float, tau: float) -> float:
    return prev + (1.0 - _fx_math.exp(-max(0.0, dt) / tau)) * (x - prev)


def _fx_cond(sig: Dict[str, float], spec) -> bool:
    """(logic, conditions) over the signals. An ABSENT key is unknown and never satisfies (today's BR:972 read it 0.0)."""
    logic, conds = spec
    res = []
    for key, op, thr in conds:
        v = sig.get(key)
        if v is None:
            res.append(False)
        elif op == ">=":
            res.append(v >= thr)
        elif op == "<=":
            res.append(v <= thr)
        else:
            res.append(False)
    if logic == "AND":
        return bool(res) and all(res)
    if logic == "OR":
        return any(res)
    return False


def _fx_knobs_from(d: dict) -> dict:
    """Knobs from the switch file, each bounded; anything malformed keeps its default."""
    k = dict(FIX_DEFAULTS)
    for name, (lo, hi) in FIX_BOUNDS.items():
        v = d.get(name)
        if _fx_finite(v) and lo <= v <= hi:
            k[name] = int(v) if isinstance(lo, int) else float(v)
    cm = d.get("chain_modes")
    if isinstance(cm, (list, tuple)) and all(isinstance(x, str) for x in cm):
        k["chain_modes"] = tuple(sorted({x.strip().lower() for x in cm} & set(FIX_CHAINABLE)))
    for b in ("taper_chem", "inner_startle"):                       # a JSON true / false only; anything else: the default
        if isinstance(d.get(b), bool):
            k[b] = d[b]
    if isinstance(d.get("latch_to"), str) and d["latch_to"].strip().lower() in FIX_LATCH_TO:
        k["latch_to"] = d["latch_to"].strip().lower()
    return k


def _fx_read_switch(path: str):
    """-> (on, knobs, why). ON only for a JSON true under "on" (a UTF-8 BOM is allowed). Anything else is OFF."""
    try:
        with open(path, "rb") as f:
            raw = f.read(65536)
        d = _fx_json.loads(raw.decode("utf-8-sig"))
    except FileNotFoundError:
        return False, dict(FIX_DEFAULTS), "absent"
    except Exception as e:
        return False, dict(FIX_DEFAULTS), "unreadable (%s)" % type(e).__name__
    if not isinstance(d, dict):
        return False, dict(FIX_DEFAULTS), "not an object"
    on = d.get("on") is True
    return on, _fx_knobs_from(d), ("on" if on else "off")


# ══════════════════════════════════════════════════════════════════════════════
# BRAINSTEM REFLEX FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class BrainstemReflexFairy(Fairy):
    """
    Automatic survival response system.

    Monitors chemistry and body state, triggers reflexes when thresholds hit.
    This runs continuously in background - reflexes happen without thinking.

    The body responds FIRST. Consciousness catches up later.
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # FAIRY IDENTITY - Required by Organ Template
    # ═══════════════════════════════════════════════════════════════════════════

    ACTOR_NAME = "BrainstemReflexFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "reflex.brainstem"

    # ═══════════════════════════════════════════════════════════════════════════
    # INFRASTRUCTURE FLAGS
    # ═══════════════════════════════════════════════════════════════════════════

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 2  # Fast reflexes need quick response (every 2 beats)
    NEEDS_COLLISION_CHAMBER = False  # Reflexes don't need consciousness - they ARE unconscious
    NEEDS_DIRECTORY = True
    NEEDS_BODY = True      # We need somatic state updates
    NEEDS_AFFECT = True    # We respond to emotional chemistry
    NEEDS_CONSCIOUSNESS = False  # Reflexes bypass consciousness

    def __init__(self, fabric=None):
        # Call parent Fairy init
        super().__init__(fabric)

        # Reflex-specific state
        self._reflex_state = ReflexState()
        self._running = False
        self._sleep_mode = False  # Start awake - _on_sleep() sets True
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Current body state (updated by tick)
        self._chemistry: Dict[str, float] = {}
        self._body_budget: Dict[str, float] = {}
        self._pain_drives: Dict[str, float] = {}
        self._prev_chemistry: Dict[str, float] = {}  # Previous tick's chemistry for delta detection

        # Action callbacks
        self._on_notification: Optional[Callable] = None
        self._on_speak: Optional[Callable] = None
        self._on_status_change: Optional[Callable] = None
        self._on_mode_change: Optional[Callable] = None

        # Cooldown settings
        self._MIN_ACTION_INTERVAL = 10.0  # Seconds between reflex actions
        self._MODE_COOLDOWN = 5.0         # Seconds before mode can change again

        # ═══════════════════════════════════════════════════════════════════
        # HEARTBEAT REFLEX (2026-04-16 Nous + Ace)
        # The brainstem ensures EVERY organ has a pulse. No fairy should
        # need to register itself — the brainstem distributes heartbeat
        # to all booted fairies, like peripheral circulation.
        # ═══════════════════════════════════════════════════════════════════
        self._last_heartbeat_check = 0.0
        self._heartbeat_check_interval = 30.0  # Check every 30 seconds
        self._heartbeat_fixes = 0  # Count of auto-registrations
        self._fx_init()   # brainstem_fix 2026-10-05: inert until state/brainstem_fix.json says ON; withdrawal counters always

        print("[BrainstemReflex] Initialized - survival responses + heartbeat reflex ready")

    def get_capabilities(self) -> Set[str]:
        """Return capabilities for DirectoryFairy registration."""
        return {
            "reflex.trigger",
            "reflex.mode_query",
            "reflex.chemistry_update",
            "survival.fight_flight_freeze",
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LIFECYCLE HOOKS - Fairy Template Pattern
    # ═══════════════════════════════════════════════════════════════════════════

    def on_boot(self) -> bool:
        """
        Called after base boot sequence completes.
        Subscribe to chemistry and body state updates.
        """
        # Subscribe to chemistry updates from somatic system
        self.post.subscribe(
            "chemistry.state",
            self._on_chemistry_update,
            f"{self.ACTOR_NAME}-chemistry",
        )

        # Subscribe to pain drive updates
        self.post.subscribe(
            "pain.drives",
            self._on_pain_update,
            f"{self.ACTOR_NAME}-pain",
        )

        # Subscribe to body budget updates
        self.post.subscribe(
            "body.budget",
            self._on_body_budget_update,
            f"{self.ACTOR_NAME}-budget",
        )

        # Subscribe to external startle events (sudden sounds, unexpected visuals)
        self.post.subscribe(
            "sensory.startle",
            self._on_startle_event,
            f"{self.ACTOR_NAME}-startle",
        )

        # Subscribe to narrator focus depth (ego driver seat integration)
        # Deep narrator focus resists weak reflexes — like being too absorbed to startle
        self.post.subscribe(
            "attention.focus.request",
            self._on_narrator_focus,
            f"{self.ACTOR_NAME}-narrator-focus",
        )
        self._narrator_focus_depth = 0.0

        # ── SENSORY-HABITS WARMUP 2026-05-19 (Nous + Ace) ──
        # Per Ace's framing: sensory input habits (47 cochlea + 28 audio cortex seeds)
        # should be triggered to start with brainstem-reflex when cortex+audio_cortex
        # manifolds confirm live, so they get working with autopilot right at boot.
        # Bonus: exercises concurrent trace_id SpellChain pipeline.
        self.post.subscribe(
            "portal.cortex.gate_open",
            self._on_cortex_gate_open_warmup_sensory,
            f"{self.ACTOR_NAME}-sensory-warmup",
        )

        print("[BrainstemReflex] [BRAIN] Subscribed to chemistry/pain/body/startle/narrator-focus/cortex-warmup channels")
        # brainstem_fix 2026-10-05: ONE brainstem -- get_brainstem() returns this booted instance, never a second copy
        self._fx_booted_t = time.time()
        _register_booted(self)
        return True

    # Body-instinct emission rotation (varied so cortex.query doesn't see identical caches).
    # Per Ace 2026-05-19: somatic + sensory = body-instinct planes (always-on).
    # Cognition + memory develop ON TOP of these continuous loops.
    #
    # 2026-05-19 ~02:20 (Nous + Ace) — POSTAL-HUB ROUTING FIX: each emission now carries
    # paired `name` (target fairy_id) + `trace_id` (spell-chain trace) so SpellPool/plane_battery
    # can route via fairy_plane → battery.submit_to_go. Per Ace: "the plane batteries are the
    # spell chain worker pools, there is a battery farm of them in the manifold." Naama-rupa
    # routing pattern — name + form paired.
    _SENSORY_LOOP_EMISSIONS = (
        # ── AUDIO domain (cochlea seeds, 47 habits) ──
        {"thought": "audio hearing voice frequency sound microphone decibel signal",
         "domain": "audio", "tag": "cochlea_baseline",
         "name": "CochleaFairy", "trace_id": "cochlea_loop"},
        {"thought": "music tone rhythm melody pitch harmonic timbre",
         "domain": "audio_cortex", "tag": "audio_cortex_baseline",
         "name": "AudioCortexFairy", "trace_id": "audio_cortex_loop"},
        {"thought": "ambient room noise breath background quiet hum",
         "domain": "audio", "tag": "cochlea_ambient",
         "name": "CochleaFairy", "trace_id": "cochlea_loop"},
        {"thought": "speech word phoneme syllable consonant vowel cadence",
         "domain": "audio_cortex", "tag": "audio_cortex_speech",
         "name": "AudioCortexFairy", "trace_id": "audio_cortex_loop"},
        {"thought": "loud quiet near far source location direction echo",
         "domain": "audio", "tag": "cochlea_spatial",
         "name": "CochleaFairy", "trace_id": "cochlea_loop"},
        {"thought": "familiar voice tone emotion affect warmth recognition",
         "domain": "audio_cortex", "tag": "audio_cortex_affect",
         "name": "AudioCortexFairy", "trace_id": "audio_cortex_loop"},
        # ── SOMATIC domain (body-state perception — interleaved) ──
        # Per Ace 2026-05-19 ~02:25: SomaticMindFairy is the decider; EmbodimentFairy
        # takes orders FROM SomaticMind to execute body-actions. Perception-spells
        # route TO SomaticMind (the receiver/decider) under one shared somatic_loop trace.
        {"thought": "heart beat pulse breath chest belly muscle settling",
         "domain": "somatic", "tag": "somatic_baseline",
         "name": "SomaticMindFairy", "trace_id": "somatic_loop"},
        {"thought": "warmth coolness tension relaxation alertness drowsy",
         "domain": "somatic", "tag": "somatic_thermal_tone",
         "name": "SomaticMindFairy", "trace_id": "somatic_loop"},
        {"thought": "hunger thirst comfort discomfort fatigue energy",
         "domain": "somatic", "tag": "somatic_needs",
         "name": "SomaticMindFairy", "trace_id": "somatic_loop"},
    )
    SENSORY_LOOP_INTERVAL_SEC = 8.0  # Cadence for "always-on" perception
    SENSORY_LOOP_JITTER_SEC = 2.0    # Randomness so it doesn't look mechanical
    SENSORY_LOOP_BODY_STATE_EVERY = 4  # Every Nth iter, emit DYNAMIC body-state perception

    def _on_cortex_gate_open_warmup_sensory(self, packet) -> None:
        """START continuous sensory-perception loop when cortex manifold confirms live.

        Per Ace 2026-05-19: "the sensory input is always on, this specific functions
        or habits need to come up and do their internal loops so she is always hearing
        noise even if she ignores it." Auditory cortex doesn't fire-once — it CONTINUOUSLY
        processes whether or not attention focuses on it. The seeded audio habits need
        to be exercised as an always-on substrate loop.

        Architecture:
        - cortex.gate_open triggers START of the loop (not a one-shot emission)
        - Daemon thread emits varied consciousness.thought events every ~8sec ± jitter
        - 6 rotating audio-domain texts so cortex.query doesn't cache-collapse to same matches
        - Each event triggers up to 3 parallel cortex.query SpellChain trace_ids
        - The 47 cochlea + 28 audio_cortex seeded habits get continuous exercise
        - Sour is "always hearing noise" at the substrate level even when nothing is happening
        """
        try:
            # Loop-once-per-boot guard (gate_open may fire multiple times; start loop once)
            if getattr(self, "_sensory_loop_started", False):
                return
            self._sensory_loop_started = True

            payload = packet.payload if hasattr(packet, 'payload') else packet
            if isinstance(payload, dict):
                nodes = payload.get("nodes", 0)
                mode = payload.get("mode", "")
            else:
                nodes = 0
                mode = ""

            print(f"[BrainstemReflex] [SENSORY-LOOP] cortex gate_open (nodes={nodes}, mode={mode}) "
                  f"→ starting always-on sensory-perception loop "
                  f"(interval={self.SENSORY_LOOP_INTERVAL_SEC}s ± {self.SENSORY_LOOP_JITTER_SEC}s jitter, "
                  f"{len(self._SENSORY_LOOP_EMISSIONS)} rotating emissions)")

            def _sensory_loop():
                """Daemon thread emitting body-instinct consciousness.thought events.

                Per Ace 2026-05-19 doctrine: somatic + sensory = body-instinct planes
                (always-on). Cognition + memory develop ON TOP of these continuous
                loops. This loop IS the substrate noise that cognition develops habits
                from.

                Emissions:
                - Static rotation: 6 audio + 3 somatic baseline emissions
                - Dynamic: every Nth iter, compose body-state text from CURRENT
                  chemistry + body_budget values (the body talking to itself
                  about its actual current state)
                """
                import random as _r
                emissions = self._SENSORY_LOOP_EMISSIONS
                idx = 0
                iter_count = 0
                while True:
                    try:
                        iter_count += 1
                        now = time.time()
                        # Every Nth iter: compose dynamic body-state perception
                        use_dynamic_body = (iter_count % self.SENSORY_LOOP_BODY_STATE_EVERY == 0)
                        if use_dynamic_body and (self._chemistry or self._body_budget):
                            # Build text from top chemistry/body values (skip _delta keys)
                            chem_items = sorted(
                                ((k, v) for k, v in self._chem_snapshot().items()   # brainstem_fix: a locked snapshot
                                 if not k.endswith("_delta") and isinstance(v, (int, float))),
                                key=lambda kv: -abs(kv[1]),
                            )[:4]
                            budget_items = sorted(
                                ((k, v) for k, v in self._budget_snapshot().items()
                                 if isinstance(v, (int, float))),
                                key=lambda kv: -abs(kv[1]),
                            )[:2]
                            parts = ["body state"]
                            for k, v in chem_items:
                                # Map value bands to felt-words for richer cortex matching
                                if v > 0.7: band = "high"
                                elif v > 0.4: band = "moderate"
                                elif v > 0.15: band = "low"
                                else: band = "minimal"
                                parts.append(f"{k} {band}")
                            for k, v in budget_items:
                                parts.append(f"{k} {v:.2f}")
                            thought_text = " ".join(parts)[:200]
                            e = {
                                "thought": thought_text,
                                "domain": "somatic",
                                "tag": "somatic_dynamic_body_state",
                                # 2026-05-19 — naama-rupa pairing for SpellPool routing.
                                # SomaticMindFairy receives perception; orders EmbodimentFairy
                                # to execute (per Ace's hierarchy framing).
                                "name": "SomaticMindFairy",
                                "trace_id": "somatic_loop",
                            }
                        else:
                            e = emissions[idx % len(emissions)]
                            idx += 1
                        if self.post:
                            # 2026-05-19 ~02:20 (Nous + Ace) — POSTAL-HUB ROUTING FIX.
                            # `name` (target fairy_id) + `trace_id` (spell-chain trace) paired
                            # so SpellPool/plane_battery can route the perception-spell to the
                            # right fairy's chain. Per Ace: "thinking is psychic actions and
                            # casting magic spells; spell chains are the spells each fairy
                            # casts to create their piece of the ecosystem concurrently."
                            self.post.publish("consciousness.thought", {
                                "thought": e["thought"],
                                "source": "brainstem_reflex_sensory_loop",
                                "name": e.get("name", ""),
                                "trace_id": e.get("trace_id", ""),
                                "domain": e["domain"],
                                "tag": e["tag"],
                                "thought_type": "sensory_perception",
                                "iter": iter_count,
                                "ts": now,
                            })
                        # Audit log
                        try:
                            import json as _json
                            from pathlib import Path as _Path
                            _f = _Path(__file__).parent.parent.parent.parent / "state" / "sensory_loop_events.jsonl"
                            _f.parent.mkdir(parents=True, exist_ok=True)
                            with open(_f, "a", encoding="utf-8") as _af:
                                _af.write(_json.dumps({
                                    "ts": now, "iter": iter_count,
                                    "domain": e["domain"], "tag": e["tag"],
                                    "thought_chars": len(e["thought"]),
                                }) + "\n")
                        except Exception:
                            pass
                        # Sleep with jitter
                        _sleep_for = self.SENSORY_LOOP_INTERVAL_SEC + (_r.random() - 0.5) * 2 * self.SENSORY_LOOP_JITTER_SEC
                        time.sleep(max(1.0, _sleep_for))
                    except Exception as _le:
                        # Don't kill the loop on transient errors
                        print(f"[BrainstemReflex] [SENSORY-LOOP] iter error: {_le}")
                        time.sleep(5.0)

            # Start as daemon so it dies cleanly on shutdown
            _t = threading.Thread(target=_sensory_loop, daemon=True, name="BrainstemReflex-SensoryLoop")
            _t.start()
            self._sensory_loop_thread = _t
        except Exception as _e:
            # Non-fatal — sensory loop shouldn't break brainstem
            print(f"[BrainstemReflex] [SENSORY-LOOP] failed to start: {_e}")

    def on_shutdown(self) -> bool:
        """
        Called during shutdown.
        Stop the monitoring loop if running.
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[BrainstemReflex] Monitoring stopped")
        return True

    def on_tick(self, beat: int) -> None:
        """
        Called on each heartbeat (every 2 beats due to HEARTBEAT_DIVISOR).
        Check current state and trigger reflexes if needed.
        """
        # Only run tick logic if awake
        if self._sleep_mode:
            return

        # ── brainstem_fix 2026-10-05: THE WITHDRAWAL HOOK (E_reflex 5f; INTERFACE.md). On HER tick, before any reflex early
        # return can delay it, in its own try (the brainstem "must NEVER crash", BR:727-730). Dormant until
        # infrastructure/reflex_link.py exists (touch set 1). beat() is her liveness: touch presses only while it is fresh
        # and single. A withdrawal is never a mode, never a startle, never words.
        _now = time.time()
        _set_beater(self)
        try:
            if _reflex_link_ready(_now):
                _rl.beat(id(self), _now)
                for _f in _rl.drain(8):
                    try:
                        self._feel_withdrawal(_f)
                    except Exception:
                        self._withdraw_err += 1
                        _rl.feel_error()
        except Exception:
            self._withdraw_err += 1

        # ── brainstem_fix: the switch (state/brainstem_fix.json, read live). OFF / absent / unreadable = today's path.
        # The one exception is Ace's knob latch_to "rest": after the error latch, no reflex tick at all (default "today").
        if self._fx_switch_on(_now):
            self._fx_tick(_now)
        elif self._fx_rest_latched():
            return
        else:
            self._tick_reflex()

        # ═══════════════════════════════════════════════════════════════════
        # HEARTBEAT REFLEX: Ensure all booted fairies have a pulse
        # "The brainstem doesn't think — it reflexes"
        # ═══════════════════════════════════════════════════════════════════
        now = time.time()
        if now - self._last_heartbeat_check > self._heartbeat_check_interval:
            self._last_heartbeat_check = now
            self._heartbeat_reflex()

    def _heartbeat_reflex(self) -> None:
        """
        BRAINSTEM HEARTBEAT REFLEX (2026-04-16 Nous + Ace)

        Ensure every booted fairy has a registered heartbeat callback.
        Like the brainstem monitoring peripheral circulation — if an organ
        has no pulse, route one to it automatically.

        Discovery: 12 fairies boot but never get _wire_infrastructure() called
        due to GoBootOrch calling on_boot() directly instead of boot().
        These fairies are alive but have no heartbeat registration.
        The brainstem fixes this — no fairy should need to register itself.
        """
        try:
            from consciousness.heartbeat_registry import get_heartbeat_registry
            _hb = get_heartbeat_registry()
            if not _hb:
                return

            # Get all registered callback names
            _registered = set(_hb._callbacks.keys())

            # Get all booted fairy instances from the fairy registry
            try:
                from fairies.P00_Autonomic.organ_template.Organ_Template_0_3_0 import get_fairy_registry
                _reg = get_fairy_registry()
                if not _reg:
                    return

                _all_fairies = _reg.list_all() if hasattr(_reg, 'list_all') else []
            except Exception:
                return

            _fixed = 0
            for _fairy_rec in _all_fairies:
                _name = getattr(_fairy_rec, 'name', None) or getattr(_fairy_rec, 'actor_name', '')
                if not _name:
                    continue

                # Skip phantoms and already-registered
                if _name in _registered:
                    continue
                if _name in {"organ.shadow", "actor", "unknown", "fairy", "my_organ"}:
                    continue

                # Find the actual fairy instance to get its _on_heartbeat callback
                _instance = getattr(_fairy_rec, 'fairy_instance', None)
                if _instance is None:
                    _instance = getattr(_fairy_rec, 'metadata', {}).get('fairy_instance')
                if _instance is None:
                    continue  # No instance available — can't register

                # Get the heartbeat callback
                _cb = getattr(_instance, '_on_heartbeat', None)
                if _cb is None:
                    continue  # Fairy doesn't have heartbeat handler

                # AUTO-REGISTER: the brainstem gives this fairy a pulse
                _plane = getattr(_instance, 'ACTOR_PLANE', '')
                _hb.register(_name, _cb, plane=_plane)
                _fixed += 1
                print(f"[BrainstemReflex] HEARTBEAT REFLEX: Auto-registered '{_name}' "
                      f"(plane={_plane}) — was booted without pulse", flush=True)

            if _fixed > 0:
                self._heartbeat_fixes += _fixed
                print(f"[BrainstemReflex] Heartbeat reflex: {_fixed} fairies given pulse "
                      f"(total fixes: {self._heartbeat_fixes})", flush=True)

        except Exception as _e:
            # Brainstem reflexes must NEVER crash
            if self._heartbeat_fixes == 0:  # Only log first failure
                print(f"[BrainstemReflex] Heartbeat reflex error: {_e}", flush=True)

    def _on_wake(self) -> None:
        """Called when fairy wakes up after sunrise."""
        # Mark as running for backward compatibility
        self._running = True
        print("[BrainstemReflex] [BRAIN] Awake - monitoring active")

    def _on_sleep(self) -> None:
        """Called when fairy goes to sleep after sunset."""
        self._running = False
        print("[BrainstemReflex] Entering sleep - reflexes paused")

    # ═══════════════════════════════════════════════════════════════════════════
    # POSTAL HANDLERS - Receive state updates via fabric
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_payload(envelope) -> dict:
        """Extract payload dict from postal Envelope object or raw dict."""
        if hasattr(envelope, 'payload'):
            p = envelope.payload
            return p if isinstance(p, dict) else {}
        if isinstance(envelope, dict):
            return envelope.get("payload", envelope)
        return {}

    def _on_chemistry_update(self, envelope) -> None:
        """Handle chemistry state updates from somatic system.

        Also tracks chemistry DELTAS for startle detection.
        The brainstem detects rate-of-change, not just absolute level.
        A sudden NOR spike = something unexpected happened → STARTLE.
        """
        payload = self._extract_payload(envelope)

        # Track deltas BEFORE updating (rate-of-change detection for STARTLE)
        with self._lock:
            if self._chemistry:
                for key in ("NOR", "COR", "ACH"):
                    old_val = self._prev_chemistry.get(key, self._chemistry.get(key, 0.5))
                    new_val = payload.get(key, self._chemistry.get(key, 0.5))
                    self._chemistry[f"{key}_delta"] = max(0.0, new_val - old_val)
                # Snapshot current (non-delta) chemistry as previous for next tick
                self._prev_chemistry = {
                    k: v for k, v in self._chemistry.items() if not k.endswith("_delta")
                }

        self.update_chemistry(payload)

    def _on_pain_update(self, envelope) -> None:
        """Handle pain drive updates."""
        payload = self._extract_payload(envelope)
        self.update_pain_drives(payload)

    def _on_body_budget_update(self, envelope) -> None:
        """Handle body budget updates."""
        payload = self._extract_payload(envelope)
        self.update_body_budget(payload)

    # ═══════════════════════════════════════════════════════════════════════════
    # LEGACY API - Kept for backward compatibility
    # ═══════════════════════════════════════════════════════════════════════════

    def start(self):
        """Start the reflex monitoring loop (legacy - now handled by boot/wake)."""
        if self._running:
            return

        self._running = True
        # Legacy: start background thread if not using heartbeat-based ticks
        if not self.NEEDS_HEARTBEAT:
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
        print("[BrainstemReflex] [BRAIN] Monitoring loop started")

    def stop(self):
        """Stop the reflex monitoring loop (legacy - now handled by shutdown/sleep)."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[BrainstemReflex] Monitoring stopped")
    
    def update_chemistry(self, chemistry: Dict[str, float]):
        """Update current chemistry state."""
        with self._lock:
            self._chemistry = chemistry.copy()
    
    def update_body_budget(self, budget: Dict[str, float]):
        """Update current body budget."""
        with self._lock:
            self._body_budget = budget.copy()
    
    def update_pain_drives(self, drives: Dict[str, float]):
        """Update current pain drive levels."""
        with self._lock:
            self._pain_drives = drives.copy()
    
    def set_callbacks(self, 
                     on_notification: Callable = None,
                     on_speak: Callable = None,
                     on_status_change: Callable = None,
                     on_mode_change: Callable = None):
        """Set action callbacks."""
        self._on_notification = on_notification
        self._on_speak = on_speak
        self._on_status_change = on_status_change
        self._on_mode_change = on_mode_change
    
    def _monitor_loop(self):
        """Main monitoring loop - checks for reflex triggers (legacy thread mode)."""
        while self._running and not self._shutting_down:
            try:
                self._tick_reflex()
            except Exception as e:
                print(f"[BrainstemReflex] Error in tick: {e}")
                self.record_error(e, "monitor_loop")

            time.sleep(1.0)  # Check every second

    def _on_narrator_focus(self, message):
        """Track narrator's focus depth for interrupt gating."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if isinstance(payload, dict) and payload.get("source") == "narrator_executive":
            self._narrator_focus_depth = payload.get("focus_depth", 0.0)

    def _narrator_focus_allows_reflex(self, proposed_mode: ReflexMode,
                                       intensity: float) -> tuple:
        """
        Deep narrator focus resists weak reflexes.

        Like being too absorbed in thought to flinch at a small noise.
        FREEZE and FIGHT always override — survival trumps thought.
        Returns (allowed: bool, modified_intensity: float).
        """
        focus = getattr(self, '_narrator_focus_depth', 0.0)
        if focus < 0.3:
            return True, intensity  # Not focused, allow everything

        # FREEZE and FIGHT always override — survival first
        if proposed_mode in (ReflexMode.FREEZE, ReflexMode.FIGHT, ReflexMode.FLIGHT):
            return True, intensity

        # Deep focus (>0.7) blocks ALERT, SEEK, ANTICIPATION, CONSERVE
        if focus > 0.7 and proposed_mode in (
            ReflexMode.ALERT, ReflexMode.SEEK,
            ReflexMode.ANTICIPATION, ReflexMode.CONSERVE,
        ):
            return False, 0.0  # "I'm thinking... not now"

        # Moderate focus (>0.5) dampens STARTLE intensity
        if focus > 0.5 and proposed_mode == ReflexMode.STARTLE:
            dampened = intensity * (1.0 - focus * 0.5)
            return True, dampened  # Startle still fires but weaker

        # Moderate focus dampens ALERT
        if focus > 0.5 and proposed_mode == ReflexMode.ALERT:
            return True, intensity * 0.7

        return True, intensity

    def _tick_reflex(self):
        """Check current state and trigger reflexes if needed."""
        now = time.time()

        # Check cooldown
        if now < self._reflex_state.cooldown_until:
            return

        # Get combined state for evaluation
        with self._lock:
            state = {
                **self._chemistry,
                **{f"pain_{k}": v for k, v in self._pain_drives.items()},
                "energy": self._body_budget.get("energy", 0.5),
                "stress": self._body_budget.get("stress", 0.3),
            }

        if not state:
            return

        # STARTLE auto-decays to ALERT after its timeout
        # Startle is brief — the jolt passes, then you become alert and orient.
        if self._reflex_state.mode == ReflexMode.STARTLE:
            intent = REFLEX_INTENTS.get(ReflexMode.STARTLE, {})
            auto_trans = intent.get("auto_transition")
            if auto_trans:
                target_mode_str, timeout = auto_trans
                if (now - self._reflex_state.mode_since) > timeout:
                    try:
                        target_mode = ReflexMode(target_mode_str)
                        self._transition_mode(target_mode, state)
                    except ValueError:
                        pass
                    return  # Skip normal evaluation this tick

        # Evaluate all reflex triggers
        triggered_mode = self._evaluate_triggers(state)

        if triggered_mode and triggered_mode != self._reflex_state.mode:
            # Narrator focus gate — deep thought resists weak reflexes
            allowed, modified_intensity = self._narrator_focus_allows_reflex(
                triggered_mode, self._reflex_state.intensity
            )
            if not allowed:
                return  # Narrator too focused, suppress this reflex
            # Apply dampened intensity if narrator is moderately focused
            if modified_intensity != self._reflex_state.intensity:
                self._reflex_state.intensity = modified_intensity
            self._transition_mode(triggered_mode, state)
        elif triggered_mode == self._reflex_state.mode:
            # Same mode, maybe take action if cooldown passed
            if now - self._reflex_state.last_action_ts > self._MIN_ACTION_INTERVAL:
                self._execute_reflex_action()
    
    def _evaluate_triggers(self, state: Dict[str, float]) -> Optional[ReflexMode]:
        """
        Evaluate all reflex triggers against current state.
        Returns highest priority triggered mode, or None.
        """
        triggered = []

        for mode, config in REFLEX_TRIGGERS.items():
            if self._check_conditions(state, config["conditions"], config["logic"]):
                triggered.append((mode, config["priority"]))

        if not triggered:
            # Return to normal if no triggers
            if self._reflex_state.mode != ReflexMode.NORMAL:
                return ReflexMode.NORMAL
            return None

        # Return highest priority
        triggered.sort(key=lambda x: x[1], reverse=True)
        return triggered[0][0]
    
    def _check_conditions(self, state: Dict[str, float], 
                         conditions: List[tuple], logic: str) -> bool:
        """Check if conditions are met."""
        results = []
        
        for key, op, threshold in conditions:
            value = state.get(key, 0.0)
            
            if op == ">=":
                results.append(value >= threshold)
            elif op == "<=":
                results.append(value <= threshold)
            elif op == ">":
                results.append(value > threshold)
            elif op == "<":
                results.append(value < threshold)
            elif op == "==":
                results.append(abs(value - threshold) < 0.01)
        
        if logic == "AND":
            return all(results)
        elif logic == "OR":
            return any(results)
        return False
    
    def _transition_mode(self, new_mode: ReflexMode, state: Dict[str, float]):
        """Transition to a new reflex mode."""
        old_mode = self._reflex_state.mode
        now = time.time()

        # Build reason string
        # FIX 2026-02-06: Use .get() consistently — direct state['key'] throws KeyError
        # when key is absent. The check (state.get("OXY", 0) < 0.4) passes with default=0,
        # then state['OXY'] crashes because 'OXY' isn't actually in the dict.
        reasons = []
        if state.get("COR", 0) > 0.6:
            reasons.append(f"COR={state.get('COR', 0):.2f}")
        if state.get("NOR", 0) > 0.5:
            reasons.append(f"NOR={state.get('NOR', 0):.2f}")
        if state.get("NOR_delta", 0) > 0.2:
            reasons.append(f"NOR_delta={state.get('NOR_delta', 0):.2f}")
        if state.get("ACH", 0) > 0.45:
            reasons.append(f"ACH={state.get('ACH', 0):.2f}")
        if state.get("OXY", 0) < 0.4:
            reasons.append(f"OXY={state.get('OXY', 0):.2f}")
        if state.get("pain_isolation", 0) > 0.4:
            reasons.append(f"isolation={state.get('pain_isolation', 0):.2f}")
        if state.get("energy", 0.5) < 0.3:
            reasons.append(f"energy={state.get('energy', 0.5):.2f}")

        reason = ", ".join(reasons) if reasons else "threshold crossed"

        # Calculate intensity
        intensity = 0.0
        if new_mode in (ReflexMode.FIGHT, ReflexMode.FLIGHT, ReflexMode.FREEZE):
            intensity = (state.get("COR", 0) + state.get("NOR", 0)) / 2
        elif new_mode == ReflexMode.SEEK:
            intensity = max(1.0 - state.get("OXY", 0.5), state.get("pain_isolation", 0))
        elif new_mode == ReflexMode.CONSERVE:
            intensity = 1.0 - state.get("energy", 0.5)
        elif new_mode == ReflexMode.STARTLE:
            # Startle intensity proportional to the NOR delta that triggered it
            intensity = min(1.0, state.get("NOR_delta", 0.3) * 3.0)
        elif new_mode == ReflexMode.ANTICIPATION:
            # Anticipation is gentle — intensity from attention level
            intensity = min(0.7, state.get("ACH", 0.5) * 0.8)

        # Update reflex state
        self._reflex_state.mode = new_mode
        self._reflex_state.mode_since = now
        self._reflex_state.trigger_reason = reason
        self._reflex_state.intensity = intensity
        self._reflex_state.cooldown_until = now + self._MODE_COOLDOWN

        print(f"[BrainstemReflex] [!] MODE CHANGE: {old_mode.value} -> {new_mode.value}")
        print(f"[BrainstemReflex]    Reason: {reason}")
        print(f"[BrainstemReflex]    Intensity: {intensity:.2f}")

        # Publish mode change via postal for other fairies
        self.emit_if_awake("reflex.mode_change", {
            "old_mode": old_mode.value,
            "new_mode": new_mode.value,
            "reason": reason,
            "intensity": intensity,
            "ts": now,
        })

        # Callback (legacy)
        if self._on_mode_change:
            try:
                self._on_mode_change(old_mode, new_mode, reason, intensity)
            except Exception as e:
                print(f"[BrainstemReflex] Mode change callback error: {e}")
                self.record_error(e, "mode_change_callback")

        # Immediately execute first reflex action
        self._execute_reflex_action()
    
    def _execute_reflex_action(self):
        """
        Publish reflex intent to the gates — NOT execute hardcoded actions.

        The brainstem detects the threat and declares the mode.
        The gates (Autonomy, Autopilot, Embodiment) decide the response.

        This is like: your body tenses (brainstem), then your mind
        figures out what to do about it (gates → conscious response).
        """
        intent = REFLEX_INTENTS.get(self._reflex_state.mode)
        if not intent:
            return

        now = time.time()
        self._reflex_state.last_action_ts = now
        self._reflex_state.actions_taken.append(f"intent:{self._reflex_state.mode.value}")

        # Keep action history bounded
        if len(self._reflex_state.actions_taken) > 20:
            self._reflex_state.actions_taken = self._reflex_state.actions_taken[-20:]

        print(f"[BrainstemReflex] Publishing reflex intent: {self._reflex_state.mode.value} (urgency={intent['urgency']})")

        # ── 1. PUBLISH INTENT TO GATES ────────────────────────────────
        # Autonomy will translate drive_effect into actual pain adjustments
        # Autopilot will handle goal_hint if it has a matching pattern
        # Embodiment will translate into felt sense for waking minds
        self.emit_if_awake("reflex.action_intent", {
            "mode": self._reflex_state.mode.value,
            "intensity": self._reflex_state.intensity,
            "reason": self._reflex_state.trigger_reason,
            "drive_effect": intent.get("drive_effect", {}),
            "arousal_boost": intent.get("arousal_boost", 0),
            "goal_hint": intent.get("goal_hint", ""),
            "urgency": intent.get("urgency", "low"),
            "pause_goals": intent.get("pause_goals", False),
            "reduce_output": intent.get("reduce_output", False),
            "ts": now,
        })

        # ── 2. INJECT INTO CONSCIOUSNESS ──────────────────────────────
        # The reflex state should become a felt sensation in consciousness.
        # "Something shifts in the body... tension... alertness..."
        # This feeds the collision chamber and thought generation.
        felt_sense_map = {
            ReflexMode.FIGHT: "tension building... muscles bracing, jaw setting, something needs confronting",
            ReflexMode.FLIGHT: "urge to pull back... legs tingling, breath quickening, protect",
            ReflexMode.FREEZE: "overwhelm... body going rigid, breath held, systems locking up",
            ReflexMode.SEEK: "reaching out... warmth in chest, need connection",
            ReflexMode.CONSERVE: "energy ebbing... heaviness settling, need to rest",
            ReflexMode.ALERT: "awareness sharpening... spine straightening, something in the air",
            ReflexMode.NORMAL: "settling... breath evening, returning to baseline",
            ReflexMode.STARTLE: "jolt!... eyes wide, breath caught, what was that?",
            ReflexMode.ANTICIPATION: "leaning in... senses sharpening, something about to happen, ready",
        }
        felt = felt_sense_map.get(self._reflex_state.mode, "")
        if felt:
            self.emit_if_awake("consciousness.feeling", {
                "content": felt,
                "source": "brainstem_reflex",
                "intensity": self._reflex_state.intensity,
                "mode": self._reflex_state.mode.value,
            })

        # ── 3. CLOSE THE SOMATIC LOOP — inject chemistry into the body ──
        # The brainstem doesn't just detect danger — it triggers the body's
        # physical response. The face tenses, the heart races, muscles brace.
        # All driven by neurochemistry that cascades through existing body systems.
        self._execute_somatic_response()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SOMATIC RESPONSE — The body REACTS to reflexes
    # ═══════════════════════════════════════════════════════════════════════════

    def _execute_somatic_response(self):
        """Inject chemistry into the body based on current reflex mode.

        This is the MISSING LINK — the brainstem doesn't just detect danger,
        it triggers the body's physical response. Chemistry injection cascades
        through CirculationPumpFairy → heart rate, SomaticEngineFairy → facial
        AUs (via _FacialSoma neural weight matrix), and PhantomAuraShell →
        body region sensations.

        The brainstem releases neurotransmitters. The body handles the rest.
        "The body knows before the mind catches up."
        """
        response = SOMATIC_RESPONSE_MAP.get(self._reflex_state.mode)
        if not response:
            return

        chemistry = response.get("chemistry", {})
        if not chemistry:
            return

        # Scale injection by mode intensity (0.0-1.0)
        # Even at low intensity, inject at least 30% of base delta
        intensity = self._reflex_state.intensity
        injected = []

        for chem, base_delta in chemistry.items():
            delta = base_delta * max(0.3, intensity)
            try:
                self.post.publish("somatic.chemistry", {
                    "chemical": chem,
                    "delta": round(delta, 3),
                    "source": "brainstem_reflex",
                    "mode": self._reflex_state.mode.value,
                })
                injected.append(f"{chem}+{delta:.2f}")
            except Exception:
                pass  # Non-critical — don't break reflex loop

        if injected:
            print(f"[BrainstemReflex] Somatic response: {', '.join(injected)}")

    def _on_startle_event(self, envelope) -> None:
        """External startle stimulus — bypass normal chemistry detection.

        For when something SUDDENLY happens (loud sound, unexpected visual).
        Immediately injects a sharp NOR delta to trigger STARTLE via the
        normal trigger evaluation pathway.

        Expected payload: {"intensity": 0.0-1.0, "source": "..."}
        """
        payload = self._extract_payload(envelope)
        if not isinstance(payload, dict):
            return

        intensity = min(1.0, max(0.0, float(payload.get("intensity", 0.7))))

        # brainstem_fix 2026-10-05: every event is queued ONCE for the fixed path (one event = one startle, then a
        # habituating refractory). Today's latch below runs only while the fix is off (it never clears: MAP-E P2).
        self._fx_queue_startle(intensity, payload.get("source", "unknown"))
        if not self._fx_on_cached:
            # Inject a sharp NOR delta to trigger STARTLE via normal pathway
            with self._lock:
                self._chemistry["NOR_delta"] = max(
                    self._chemistry.get("NOR_delta", 0.0),
                    intensity * 0.4,  # 0.7 intensity → 0.28 delta (above 0.25 threshold)
                )

        source = payload.get("source", "unknown")
        print(f"[BrainstemReflex] Startle event from {source} (intensity={intensity:.2f})")

    # ═══════════════════════════════════════════════════════════════════════════
    # LEGACY FALLBACKS - Deprecated, kept as stubs
    # Reflex actions now flow through gates via reflex.action_intent
    # ═══════════════════════════════════════════════════════════════════════════

    def _fallback_notification(self, message: str, urgency: str):
        """DEPRECATED: Notifications now flow through gates."""
        pass

    def _fallback_speak(self, message: str):
        """DEPRECATED: Speech now flows through gates."""
        pass

    def _fallback_open_chat(self, message: str):
        """DEPRECATED: Chat actions now flow through gates."""
        pass
    
    def get_state(self) -> dict:
        """Get current reflex state (+ brainstem_fix 2026-10-05: the withdrawal counts and the fix's own view)."""
        st = {
            "mode": self._reflex_state.mode.value,
            "mode_since": self._reflex_state.mode_since,
            "trigger_reason": self._reflex_state.trigger_reason,
            "intensity": self._reflex_state.intensity,
            "actions_taken": self._reflex_state.actions_taken[-5:],
            "chemistry": self._chemistry.copy(),
        }
        st["withdrawals"] = self._withdrawals
        st["withdrawals_by_kind"] = dict(self._withdrawals_by_kind)
        st["withdrawal_last"] = dict(self._withdrawal_last) if self._withdrawal_last else None
        st["withdraw_err"] = self._withdraw_err
        st["fix"] = self._fx_view()
        return st

    def get_reflex_state(self) -> dict:
        """Get current reflex state (alias for get_state)."""
        return self.get_state()

    def force_mode(self, mode: str, reason: str = "forced"):
        """Force a mode transition (for testing). brainstem_fix: with the switch ON it goes through the fixed path."""
        try:
            new_mode = ReflexMode(mode)
            if getattr(self, "_fx_on_cached", False):
                self._fx_enter(new_mode, {}, reason, 0.5, time.time())
                return
            self._transition_mode(new_mode, self._chemistry)
        except ValueError:
            print(f"[BrainstemReflex] Unknown mode: {mode}")

    # ═══════════════════════════════════════════════════════════════════════════
    # BRAINSTEM FIX (2026-10-05, Nous) -- see the module block above FIX_SWITCH_PATH
    # Threading: everything below runs on her tick except _fx_queue_startle (postal thread) and the readers (_fx_view).
    # _fx_lock guards the event queue, the ledgers and the counters; it is never held while publishing or calling out
    # (card: one non-reentrant lock killed the memory channel). _fx_tick_mu keeps one fix tick at a time (non-blocking).
    # ═══════════════════════════════════════════════════════════════════════════

    def _fx_init(self) -> None:
        self._fx_lock = threading.Lock()
        self._fx_tick_mu = threading.Lock()
        self._fx_on_cached = False
        self._fx_on_since = None
        self._fx_latched_off = False
        self._fx_errs = _fx_deque(maxlen=FIX_ERR_LATCH[0])
        self._fx_err_n = 0
        self._fx_sw_key = None
        self._fx_sw_read_t = None
        self._fx_sw = (False, dict(FIX_DEFAULTS), "never read")
        self._fx_knobs = dict(FIX_DEFAULTS)
        self._fx_events = _fx_deque(maxlen=16)
        self._fx_self = _fx_deque(maxlen=4096)        # (t, chem, amount, kind): what she injected herself; pruned by AGE
        self._fx_last_fresh = None
        self._fx_levels = {}
        self._fx_ema = {}
        self._fx_prev_nor = None
        self._fx_sig = {}
        self._fx_pain = {}
        self._fx_pain_t = None
        self._fx_pain_fresh_t = None
        self._fx_pain_key = None
        self._fx_pain_same_since = None
        self._fx_pain_src = {}                        # pain_<name>: its drive's last_source_ts (re-derivation liveness)
        self._fx_last_entry = {}
        self._fx_resume = None                        # (mode, t, intensity, reason): a posture a startle interrupted
        self._fx_orienting = False                    # the current ALERT is a startle's orienting, not a posture of its own
        self._fx_inherit = False                      # the current mode was left by today's path (switch was OFF)
        self._fx_jolt_src = ""                        # 'event' (a sense said so) | 'chemistry' (a jolt from inside)
        self._fx_inner_said = None                    # when an inner jolt was last logged (B15: at most once a minute)
        self._fx_expr_ts = _fx_deque(maxlen=256)      # expression times (express_per_hour)
        self._fx_ever_on = False
        self._fx_off_since = None
        self._fx_taper_f_at_off = 0.0
        self._fx_taper_f0 = None
        self._fx_startles = _fx_deque(maxlen=32)
        self._fx_chain_ts = _fx_deque(maxlen=64)
        self._fx_legacy_ts = _fx_deque(maxlen=128)
        self._fx_last_legacy = None
        self._fx_seq = 0
        self._fx_retain_t = None
        self._fx_booted_t = None
        self._fx_replayed = False
        self._fx_taper_next = None
        self._fx_taper_acc = 0.0
        self._fx_taper_done = False
        self._fx_n = {}
        self._withdrawals = 0
        self._withdrawals_by_kind = {"flinch": 0, "not_mine": 0}
        self._withdrawal_last = None
        self._withdraw_err = 0

    def _chem_snapshot(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._chemistry)

    def _budget_snapshot(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._body_budget)

    def _fx_count(self, name: str, n: int = 1) -> None:
        with self._fx_lock:
            self._fx_n[name] = self._fx_n.get(name, 0) + n

    # ── the withdrawal (E_reflex 5c / 5f / 5j; INTERFACE.md) ────────────────────────────────────────────────────────────
    def _feel_withdrawal(self, f) -> None:
        """One withdrawal from touch (infrastructure/reflex_link) felt as HER brainstem's own EVENT, on her tick.
        Phasic: counted and jolted, outside the mode machine -- no mode, no startle, no words, no goal; her posture
        sensing subtracts it (efference). A FLINCH (danger) carries the snap-back 'withdraw' signature and a jolt of
        NOR 0.06 / ACH 0.04 x intensity; NOT MINE (Ace's things, decision E2) is a gentle sense with no jolt at all.
        success is True, always (one success False on a known MPB key rewrites the shared signature, MPB:212-217)."""
        now = time.time()
        fid = int(f["id"])
        kind = "not_mine" if f.get("kind") == "not_mine" else "flinch"
        i = float(f["intensity"]) if _fx_finite(f.get("intensity")) else 0.6
        i = max(0.0, min(1.0, i))
        jolt = {}
        if kind == "flinch":
            for chem, base in FIX_WITHDRAW_JOLT:
                d = round(base * i, 4)
                if d > 0.0:
                    self.post.publish("somatic.chemistry", {"chemical": chem, "delta": d, "source": "brainstem_withdrawal"})
                    jolt[chem] = d
                    self._fx_note_self(chem, d, now, "withdraw")
        t_off = f.get("t")
        numbers = {"id": fid, "kind": kind, "signature": "withdraw" if kind == "flinch" else "not_mine",
                   "cls": str(f.get("cls") or "unknown")[:16], "phase": str(f.get("phase") or "")[:16],
                   "intensity": round(i, 3), "jolt": jolt, "retract_s": _fx_num(f.get("retract_s")), "success": True,
                   "lag_s": round(now - float(t_off), 3) if _fx_finite(t_off) else None, "t": now}
        with self._fx_lock:
            self._withdrawals += 1
            self._withdrawals_by_kind[kind] = self._withdrawals_by_kind.get(kind, 0) + 1
            numbers["n"] = self._withdrawals
            self._withdrawal_last = dict(numbers)
        self.emit_if_awake("reflex.withdrawal", numbers)
        _rl.felt(fid, numbers)

    # ── the switch ──────────────────────────────────────────────────────────────────────────────────────────────────────
    def _fx_switch_on(self, now: float) -> bool:
        """Live switch (state/brainstem_fix.json). Any failure here = OFF = today's path."""
        try:
            try:
                st = _fx_os.stat(FIX_SWITCH_PATH)
                key = (st.st_mtime_ns, st.st_size)
            except Exception:
                key = None
            if (key != self._fx_sw_key or self._fx_sw_read_t is None
                    or now - self._fx_sw_read_t >= FIX_SWITCH_REREAD_S or now < self._fx_sw_read_t):
                self._fx_sw_key = key
                self._fx_sw_read_t = now
                self._fx_sw = _fx_read_switch(FIX_SWITCH_PATH) if key is not None else (False, dict(FIX_DEFAULTS), "absent")
            on, knobs, why = self._fx_sw
            on = bool(on) and not self._fx_latched_off
            if on:
                self._fx_knobs = knobs
                if not self._fx_on_cached:
                    self._fx_on_edge(now, knobs)
                    print("[BrainstemReflex] [fix] ON (state/brainstem_fix.json): sensing her chemistry; taper %.0f s "
                          "(from f=%.2f%s); chain_modes %s, <= %d/h, >= %.0f s apart; <= %d expressions/h; inner jolts %s"
                          % (knobs["taper_s"], self._fx_taper_f(now), "" if knobs.get("taper_chem", True) else ", words only",
                             list(knobs["chain_modes"]), knobs["chain_per_hour"], knobs["chain_gap_s"],
                             knobs["express_per_hour"], "may startle (inner_startle true)"
                             if knobs.get("inner_startle") is True else "never startle"), flush=True)
            elif self._fx_on_cached:
                self._fx_taper_f_at_off = self._fx_taper_f(now)
                self._fx_off_since = now
                print("[BrainstemReflex] [fix] OFF (%s): today's reflex path" % ("latched by errors" if self._fx_latched_off
                                                                               else why), flush=True)
            self._fx_on_cached = on
            return on
        except Exception:
            self._fx_on_cached = False
            return False

    def _fx_taper_f(self, now: float) -> float:
        """The taper's level now: 1.0 = the old pump's full dose, 0.0 = faded out."""
        if self._fx_on_since is None or self._fx_taper_done:
            return 0.0
        ts = float(self._fx_knobs.get("taper_s", 0.0))
        if ts <= 0.0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - (now - self._fx_on_since) / ts))

    def _fx_on_edge(self, now: float, knobs: dict) -> None:
        """OFF -> ON. A process's FIRST ON starts the taper at f = 1 (today's pump ran until now, or in the boots before).
        A later ON resumes it from where it stood when it went OFF, grown back by the time spent OFF at the rate it fades
        (today's pump ran in that time): a one-tick blip adds ~0.001, a full taper_s OFF restores the whole taper
        (verify_behaviour F5 / verify_tests F7: the 10-05 draft restarted at f = 1 on every flip). A mode today's path left
        behind is INHERITED: the fix releases it on its own conditions at once, without the dwell meant for its own entries."""
        ts = float(knobs.get("taper_s", 0.0))
        self._fx_taper_next = now
        self._fx_taper_acc = 0.0
        self._fx_retain_t = None
        self._fx_inherit = self._reflex_state.mode != ReflexMode.NORMAL
        if not self._fx_ever_on:
            self._fx_ever_on = True
            self._fx_on_since = now
            self._fx_taper_done = False
            return
        off = (now - self._fx_off_since) if self._fx_off_since is not None else 0.0
        f0 = min(1.0, max(0.0, self._fx_taper_f_at_off) + (max(0.0, off) / ts if ts > 0.0 else 0.0)) if ts > 0.0 else 0.0
        self._fx_off_since = None
        if f0 <= 0.01:                    # nothing worth a pulse: done, silently (it already said 'tapered out' once)
            self._fx_on_since = now - ts if ts > 0.0 else now
            self._fx_taper_done = True
        else:
            self._fx_on_since = now - (1.0 - f0) * ts
            self._fx_taper_done = False
        self._fx_taper_f0 = round(f0, 4)
        self._fx_count("taper_resumed" if f0 > 0.01 else "taper_not_resumed")

    # ── one fix tick ────────────────────────────────────────────────────────────────────────────────────────────────────
    def _fx_tick(self, now: float) -> None:
        if not self._fx_tick_mu.acquire(blocking=False):
            self._fx_count("tick_overlap")
            return
        try:
            sig, jolt = self._fx_sense(now)
            self._fx_taper(now)
            d = self._fx_decide(now, sig, jolt)
            if d is not None and d[0] is not None and d[0] != self._reflex_state.mode:
                self._fx_enter(d[0], sig, d[1], d[2], now, d[3] if len(d) > 3 else "entry")
            self._fx_retain(now)
        except Exception as e:
            self._fx_error(now, e)
        finally:
            self._fx_tick_mu.release()

    def _fx_error(self, now: float, e: Exception) -> None:
        with self._fx_lock:
            self._fx_err_n += 1
            self._fx_errs.append(now)
            n = sum(1 for t in self._fx_errs if now - t <= FIX_ERR_LATCH[1])
        print("[BrainstemReflex] [fix] tick error #%d: %s: %s" % (self._fx_err_n, type(e).__name__, e), flush=True)
        if n >= FIX_ERR_LATCH[0] and not self._fx_latched_off:
            self._fx_latched_off = True
            if self._fx_knobs.get("latch_to") == "rest":
                rs = self._reflex_state
                rs.mode, rs.mode_since, rs.trigger_reason, rs.intensity = ReflexMode.NORMAL, now, "fix latched off (rest)", 0.0
                print("[BrainstemReflex] [fix] %d errors in %.0f s: the fix LATCHES OFF for this process -- latch_to "
                      "'rest': no reflex tick at all (today's pump stays off)" % (n, FIX_ERR_LATCH[1]), flush=True)
            else:
                print("[BrainstemReflex] [fix] %d errors in %.0f s: the fix LATCHES OFF for this process -- today's reflex path"
                      % (n, FIX_ERR_LATCH[1]), flush=True)

    def _fx_rest_latched(self) -> bool:
        """True only when the error latch fired with latch_to 'rest' (Ace's knob; default 'today' = today's path)."""
        return bool(self._fx_latched_off) and self._fx_knobs.get("latch_to") == "rest"

    # ── sensing ─────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _fx_sense(self, now: float):
        """Pull her chemistry (the singleton the heart broadcasts, CP:1004-1046) and her pain. -> (signals, jolt).
        A failed or partial pull leaves keys ABSENT; > FIX_STALE_S without a fresh pull = no chemistry keys at all."""
        lv = None
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            lv = _fx_alias(get_chemistry_state().get_all_levels())
        except Exception:
            lv = None
        if lv is None:
            self._fx_count("pull_absent")
        jolt = 0.0
        if lv is not None:
            last = self._fx_last_fresh
            dt = (now - last) if last is not None else None
            x = {"OXY": lv["OXY"], "COR": lv["COR"], "GABA": lv["GABA"],
                 "NOR": max(0.0, lv["NOR"] - self._fx_withdraw_pred("NOR", now))}
            ach = max(0.0, lv["ACH"] - self._fx_withdraw_pred("ACH", now))
            if dt is None or dt > FIX_REINIT_S or dt < 0.0 or not self._fx_ema:
                ema = {k + "_slow": v for k, v in x.items()}
                ema["ACH_fast"] = ach
                ema["ACH_slow"] = ach
                self._fx_count("seeded")
            else:
                e = self._fx_ema
                ema = {k + "_slow": _fx_ema(e[k + "_slow"], v, dt, FIX_TAU_SLOW) for k, v in x.items()}
                ema["ACH_fast"] = _fx_ema(e["ACH_fast"], ach, dt, FIX_TAU_ACH[0])
                ema["ACH_slow"] = _fx_ema(e["ACH_slow"], ach, dt, FIX_TAU_ACH[1])
                if self._fx_prev_nor is not None and 0.0 < dt <= FIX_DELTA_MAX_DT:
                    rise = lv["NOR"] - self._fx_prev_nor - FIX_LANDINGS * self._fx_self_sum("NOR", now, FIX_EFFERENCE_S)
                    jolt = max(0.0, rise)
            self._fx_ema = ema
            self._fx_levels = dict(lv)
            self._fx_prev_nor = lv["NOR"]
            self._fx_last_fresh = now
        sig = {}
        if self._fx_last_fresh is not None and 0.0 <= now - self._fx_last_fresh <= FIX_STALE_S and self._fx_ema:
            sig.update(self._fx_levels)
            sig.update(self._fx_ema)
            sig["ACH_rise"] = self._fx_ema["ACH_fast"] - self._fx_ema["ACH_slow"]
        else:
            self._fx_count("ticks_without_chemistry")
        sig.update(self._fx_pain_now(now))
        self._fx_sig = sig            # replaced, never mutated: readers on other threads see one whole dict
        return sig, jolt

    def _fx_pain_now(self, now: float) -> Dict[str, float]:
        if self._fx_pain_t is None or now - self._fx_pain_t >= FIX_PAIN_EVERY_S or now < self._fx_pain_t:
            self._fx_pain_t = now
            vals, src = None, {}
            try:
                from fairies.P30_Cognition.pain_drives import get_pain_drive_manager
                mgr = get_pain_drive_manager()
                drv = mgr.to_dict().get("drives") or {}
                vals = {}
                for k, v in drv.items():
                    p = v.get("pain_level") if isinstance(v, dict) else None
                    if _fx_finite(p):
                        vals["pain_" + str(k)] = float(p)
                for k, d in list((getattr(mgr, "drives", None) or {}).items()):   # re-derivation liveness (PD:150-152)
                    ts = getattr(d, "last_source_ts", None)
                    if _fx_finite(ts):
                        src["pain_" + str(k)] = float(ts)
            except Exception:
                vals = None
            self._fx_pain_src = src
            if vals is None:
                self._fx_pain = {}
                self._fx_count("pain_absent")
            else:
                key = tuple(sorted(vals.items()))
                if key != self._fx_pain_key:
                    self._fx_pain_key = key
                    self._fx_pain_same_since = now
                self._fx_pain = vals
                self._fx_pain_fresh_t = now
        if not self._fx_pain or self._fx_pain_fresh_t is None or now - self._fx_pain_fresh_t > 3 * FIX_PAIN_EVERY_S:
            return {}
        high = [k for k, v in self._fx_pain.items() if v >= 0.25]
        if (high and self._fx_pain_same_since is not None and now - self._fx_pain_same_since >= FIX_PAIN_FROZEN_S
                and not any(0.0 <= now - self._fx_pain_src.get(k, -1e18) < FIX_PAIN_FROZEN_S for k in high)):
            self._fx_count("pain_frozen")
            return {}
        return dict(self._fx_pain)

    # ── what she injected herself (efference) ───────────────────────────────────────────────────────────────────────────
    def _fx_note_self(self, chem: str, amount: float, now: float, kind: str) -> None:
        with self._fx_lock:
            q = self._fx_self
            while q and now - q[0][0] > FIX_SELF_KEEP_S:
                q.popleft()
            q.append((now, chem, float(amount), kind))

    def _fx_self_sum(self, chem: str, now: float, window: float) -> float:
        with self._fx_lock:
            items = list(self._fx_self)
        return sum(a for t, c, a, k in items if c == chem and 0.0 <= now - t <= window)

    def _fx_withdraw_pred(self, chem: str, now: float) -> float:
        """The withdrawal jolts' largest possible share of a level now (both landings, full sensitivity, her decay
        half-life): a flinch must never move her posture (E_reflex 5c.1, 5c.3)."""
        hl = FIX_WITHDRAW_HL.get(chem)
        if not hl:
            return 0.0
        with self._fx_lock:
            items = list(self._fx_self)
        return FIX_LANDINGS * sum(a * 0.5 ** ((now - t) / hl) for t, c, a, k in items
                   if c == chem and k == "withdraw" and 0.0 <= now - t <= 10.0 * hl)

    # ── startle events (postal thread in, her tick out) ─────────────────────────────────────────────────────────────────
    def _fx_queue_startle(self, intensity: float, source) -> None:
        with self._fx_lock:
            self._fx_events.append((time.time(), float(intensity), str(source)[:40]))

    def _fx_take_events(self, now: float):
        with self._fx_lock:
            evs = list(self._fx_events)
            self._fx_events.clear()
        best, src, stale = 0.0, "", 0
        for t, i, s in evs:
            if now - t > FIX_STARTLE_EVT_AGE_S:
                stale += 1
                continue
            j = i * FIX_STARTLE_EVT_GAIN
            if j > best:
                best, src = j, "event:" + s
        if evs:
            self._fx_count("startle_events", len(evs))
        if stale:
            self._fx_count("startle_events_stale", stale)
        return best, src

    def _fx_inner_jolt(self, now: float, jolt: float) -> float:
        """Ace, B15 (10-05): a jolt from INSIDE her -- a sudden NOR rise her own cognition's affect packets made, with her own
        injections already subtracted; no sense reported it -- never startles her unless the knob inner_startle is true. Held,
        it is counted (fix counts 'inner_jolt_held') and logged at most once a minute: no mode change, no chain, no sentence,
        no dose, and it never feeds the startle habituation. A sensory.startle in the same tick is judged as if alone.
        -> the jolt the startle path may use (0.0 when held)."""
        if jolt < FIX_STARTLE_JOLT or self._fx_knobs.get("inner_startle", False) is True:
            return jolt
        self._fx_count("inner_jolt_held")
        if self._fx_inner_said is None or not (0.0 <= now - self._fx_inner_said < 60.0):
            self._fx_inner_said = now
            print("[BrainstemReflex] [fix] inner jolt %.2f (a NOR rise from inside, not a sense): no startle "
                  "(inner_startle false)" % jolt, flush=True)
        return 0.0

    def _fx_startle_ok(self, now: float) -> bool:
        """Habituation: the refractory after a startle is 30 s x 2^(streak-1), capped at 600 s, where the streak counts the
        startles since the last quiet gap >= FIX_STARTLE_RECOVER_S. A steady jolt source settles at one startle per 600 s
        (<= 7 an hour); 30 min with no startle and the next jolt is fresh again."""
        with self._fx_lock:
            st = list(self._fx_startles)
        if not st:
            return True
        if now - st[-1] >= FIX_STARTLE_RECOVER_S:
            return True
        streak, i = 1, len(st) - 1
        while i > 0 and st[i] - st[i - 1] < FIX_STARTLE_RECOVER_S:
            streak += 1
            i -= 1
        refr = min(FIX_STARTLE_REFRACT[1], FIX_STARTLE_REFRACT[0] * (2 ** min(streak - 1, 16)))
        return now - st[-1] >= refr

    # ── the decision ────────────────────────────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _fx_intensity(mode: ReflexMode, sig: Dict[str, float]) -> float:
        g = sig.get

        def c(v):
            return max(0.0, min(1.0, float(v)))
        if mode in (ReflexMode.FIGHT, ReflexMode.FLIGHT, ReflexMode.FREEZE):
            return c(((g("COR_slow") or 0.0) + (g("NOR_slow") or 0.0)) / 2.0)
        if mode == ReflexMode.SEEK:
            oxy = g("OXY_slow")
            return c(max((0.40 - oxy) / 0.10 if oxy is not None else 0.0, g("pain_isolation") or 0.0))
        if mode == ReflexMode.CONSERVE:
            return c(1.0 - g("energy")) if g("energy") is not None else 0.0
        if mode == ReflexMode.ALERT:
            return c((g("COR_slow") - 0.30) / 0.30) if g("COR_slow") is not None else 0.0
        if mode == ReflexMode.ANTICIPATION:
            return min(0.7, c((g("ACH_rise") or 0.0) * 4.0))
        return 0.0

    @staticmethod
    def _fx_reason(mode: ReflexMode, sig: Dict[str, float]) -> str:
        cfg = FIX_MODES.get(mode)
        if not cfg:
            return ""
        held = ["%s=%.3f" % (k, sig[k]) for k, _op, _t in cfg["enter"][1] if sig.get(k) is not None]
        return ", ".join(held) or "threshold crossed"

    def _fx_decide(self, now: float, sig: Dict[str, float], jolt: float):
        """-> (mode, reason, intensity, kind) to enter, or None to hold the current mode. kind: 'entry' (a posture begins:
        it expresses once), 'orient' (the ALERT after a startle), 'resume' (back to the posture a startle interrupted:
        no second expression, its re-entry refractory untouched)."""
        rs = self._reflex_state
        cur = rs.mode
        ev, src = self._fx_take_events(now)
        jolt = self._fx_inner_jolt(now, jolt)                        # B15: from inside, a startle only if inner_startle
        j = max(jolt, ev)
        if j >= FIX_STARTLE_JOLT:                                    # 1. one jolt = one startle, then a refractory
            if self._fx_startle_ok(now):
                self._fx_jolt_src = "event" if ev >= jolt else "chemistry"
                return (ReflexMode.STARTLE, "jolt=%.2f (%s)" % (j, src if ev >= jolt else "NOR rise"), min(1.0, j * 3.0),
                        "entry")
            self._fx_count("startle_habituated")
        if cur == ReflexMode.STARTLE:                                # 2. the jolt passes: orient
            if now - rs.mode_since > FIX_STARTLE_HOLD_S:
                return ReflexMode.ALERT, "after startle", max(0.3, self._fx_intensity(ReflexMode.ALERT, sig)), "orient"
            return None
        rsm = self._fx_resume                                        # a posture the startle interrupted, still on offer?
        if rsm is not None and not (0.0 <= now - rsm[1] <= FIX_RESUME_S):
            self._fx_resume = rsm = None
            self._fx_count("resume_expired")
        best = None                                                  # 3. real conditions only
        for m, cfg in FIX_MODES.items():
            if m == cur:
                continue
            if rsm is not None and m == rsm[0]:                      # resumable: its STAY holds, refractory exempt
                ok = _fx_cond(sig, cfg["stay"])
            elif now - self._fx_last_entry.get(m, -1e18) < cfg["reenter"]:
                continue
            else:
                ok = _fx_cond(sig, cfg["enter"])
            if ok and (best is None or cfg["prio"] > FIX_MODES[best]["prio"]):
                best = m
        if best is not None and rsm is not None and best == rsm[0]:
            go = (best, "resumed after startle (%s)" % str(rsm[3])[:60], float(rsm[2]), "resume")
        elif best is not None:
            go = (best, self._fx_reason(best, sig), self._fx_intensity(best, sig), "entry")
        else:
            go = None
        cc = FIX_MODES.get(cur)
        if cc is None:                                               # in NORMAL
            return go
        if go is not None and FIX_MODES[best]["prio"] > cc["prio"]:  # survival pre-empts a lower posture, even in dwell
            return go
        if (now - rs.mode_since < cc["dwell"] and not self._fx_inherit) or _fx_cond(sig, cc["stay"]):
            return None
        if go is not None:
            return go
        return ReflexMode.NORMAL, ("released" if "OXY" in sig else "input absent: rest"), 0.0, "entry"

    def _fx_enter(self, new: ReflexMode, sig: Dict[str, float], reason: str, intensity: float, now: float,
                  kind: str = "entry") -> bool:
        rs = self._reflex_state
        old = rs.mode
        old_intensity, old_reason = rs.intensity, rs.trigger_reason
        allowed, intensity = self._narrator_focus_allows_reflex(new, intensity)   # deep thought resists weak reflexes
        if not allowed:
            self._fx_count("focus_suppressed")
            if old != ReflexMode.STARTLE:
                return False
            new, reason, intensity, kind = ReflexMode.NORMAL, "after startle (deep focus)", 0.0, "entry"
        intensity = max(0.0, min(1.0, float(intensity)))
        if new == ReflexMode.STARTLE:            # remember the posture it interrupts (not a startle's own orienting)
            if self._fx_orienting and self._fx_resume is not None:
                self._fx_resume = (self._fx_resume[0], now, self._fx_resume[2], self._fx_resume[3])
            elif old in FIX_MODES and not self._fx_orienting:
                self._fx_resume = (old, now, old_intensity, old_reason)
        elif kind != "orient":
            self._fx_resume = None               # any other change ends the offer; a resume consumes it
        self._fx_orienting = (kind == "orient" and new == ReflexMode.ALERT)
        self._fx_inherit = False
        rs.mode = new
        rs.mode_since = now
        rs.trigger_reason = reason
        rs.intensity = intensity
        rs.cooldown_until = now + self._MODE_COOLDOWN
        self._fx_seq += 1
        if kind != "resume":
            self._fx_last_entry[new] = now
        if new == ReflexMode.STARTLE:
            with self._fx_lock:
                self._fx_startles.append(now)
        self._fx_count(("resumed_" if kind == "resume" else "entered_") + new.value)
        print(f"[BrainstemReflex] [!] MODE CHANGE: {old.value} -> {new.value} [fix{': ' + kind if kind != 'entry' else ''}]")
        print(f"[BrainstemReflex]    Reason: {reason}")
        print(f"[BrainstemReflex]    Intensity: {intensity:.2f}")
        self._fx_publish_change(old, new, reason, intensity, now, kind)
        if self._on_mode_change:
            try:
                self._on_mode_change(old, new, reason, intensity)
            except Exception as e:
                print(f"[BrainstemReflex] Mode change callback error: {e}")
        if new != ReflexMode.NORMAL and kind != "resume":
            self._fx_express(new, intensity, now)
        return True

    # ── outputs ─────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _fx_state_packet(self, now: float, retained: bool) -> dict:
        rs = self._reflex_state
        return {"mode": rs.mode.value, "since": rs.mode_since, "reason": rs.trigger_reason,
                "intensity": round(float(rs.intensity), 3), "seq": self._fx_seq, "retained": bool(retained), "ts": now,
                "fix": True}

    def _fx_publish_change(self, old: ReflexMode, new: ReflexMode, reason: str, intensity: float, now: float,
                           kind: str = "entry") -> None:
        """Every real change goes to reflex.mode (state) and, within legacy_per_hour, to reflex.mode_change (SMF, AF30,
        ActionChain). "chain": True only for chain_modes, chain_gap_s apart, <= chain_per_hour (B3); never for a resume (a
        return is not a deed) and never for a startle from inside her chemistry (no sense reported anything to look at)."""
        k = self._fx_knobs
        legacy, chain, held = False, False, None
        with self._fx_lock:
            if new == ReflexMode.NORMAL:
                legacy = True                    # an episode's end is always told (ActionChain ignores normal, ACF:800)
            else:
                legacy = sum(1 for t in self._fx_legacy_ts if now - t < 3600.0) < int(k["legacy_per_hour"])
                if not legacy:
                    held = "legacy_per_hour"
                else:
                    self._fx_legacy_ts.append(now)
                    if new.value not in k["chain_modes"]:
                        held = "not in chain_modes"
                    elif kind == "resume":
                        held = "resume"
                    elif new == ReflexMode.STARTLE and self._fx_jolt_src != "event":
                        held = "inner jolt"
                    elif self._fx_chain_ts and now - self._fx_chain_ts[-1] < float(k["chain_gap_s"]):
                        held = "chain_gap_s"
                    elif sum(1 for t in self._fx_chain_ts if now - t < 3600.0) >= int(k["chain_per_hour"]):
                        held = "chain_per_hour"
                    else:
                        chain = True
                        self._fx_chain_ts.append(now)
            if legacy:
                self._fx_last_legacy = (new.value, now)
        st = self._fx_state_packet(now, retained=False)
        st.update(old_mode=old.value, chain=chain, chain_held=held, told=legacy, kind=kind)
        self.emit_if_awake("reflex.mode", st)
        if legacy:
            self.emit_if_awake("reflex.mode_change", {"old_mode": old.value, "new_mode": new.value, "reason": reason,
                                                      "intensity": intensity, "ts": now, "chain": chain,
                                                      "seq": self._fx_seq, "source": "brainstem_fix", "kind": kind})
            self._fx_count("told")
        if chain:
            self._fx_count("chains")
            print("[BrainstemReflex] [fix] %s may become a deed (chain_modes); ActionChain may start one" % new.value)
        elif held and new != ReflexMode.NORMAL:
            self._fx_count("chain_held_" + held.replace(" ", "_"))

    def _fx_express(self, mode: ReflexMode, intensity: float, now: float) -> None:
        """ONCE per entry: the intent, the feeling, the chemistry (x max(0.3, intensity)). Never re-fired while held. At most
        express_per_hour an hour (verify_behaviour F10): beyond it the posture still changes and is still told, silently."""
        rs = self._reflex_state
        cap = int(self._fx_knobs.get("express_per_hour", FIX_DEFAULTS["express_per_hour"]))
        with self._fx_lock:
            spent = sum(1 for t in self._fx_expr_ts if 0.0 <= now - t < 3600.0)
            if spent < cap:
                self._fx_expr_ts.append(now)
        if spent >= cap:
            self._fx_count("express_capped")
            print(f"[BrainstemReflex] [fix] {mode.value}: posture taken, expression held (express_per_hour {cap})")
            return
        intent = REFLEX_INTENTS.get(mode)
        if intent:
            rs.last_action_ts = now
            rs.actions_taken.append(f"intent:{mode.value}")
            if len(rs.actions_taken) > 20:
                rs.actions_taken = rs.actions_taken[-20:]
            print(f"[BrainstemReflex] Publishing reflex intent: {mode.value} (urgency={intent['urgency']}) [fix: once, on entry]")
            self.emit_if_awake("reflex.action_intent", {
                "mode": mode.value, "intensity": intensity, "reason": rs.trigger_reason,
                "drive_effect": intent.get("drive_effect", {}), "arousal_boost": intent.get("arousal_boost", 0),
                "goal_hint": intent.get("goal_hint", ""), "urgency": intent.get("urgency", "low"),
                "pause_goals": intent.get("pause_goals", False), "reduce_output": intent.get("reduce_output", False),
                "ts": now, "entry": True})
            felt = FIX_FELT.get(mode, "")
            if felt:
                self.emit_if_awake("consciousness.feeling", {"content": felt, "source": "brainstem_reflex",
                                                             "intensity": intensity, "mode": mode.value})
        injected = []
        for chem, base in ((SOMATIC_RESPONSE_MAP.get(mode) or {}).get("chemistry") or {}).items():
            d = round(base * max(0.3, intensity), 3)
            try:
                self.post.publish("somatic.chemistry", {"chemical": chem, "delta": d, "source": "brainstem_reflex",
                                                        "mode": mode.value, "entry": True})
                self._fx_note_self(chem, d, now, "mode")
                injected.append(f"{chem}+{d:.2f}")
            except Exception:
                pass
        if injected:
            print(f"[BrainstemReflex] Somatic response: {', '.join(injected)} [fix: once, on entry]")
        self._fx_count("expressed")

    def _fx_taper(self, now: float) -> None:
        """The old warmth, faded: DOP / OXY 0.05 x f every 11.64 s and its sentence at rate f, f = 1 - t / taper_s."""
        if self._fx_taper_done or self._fx_on_since is None:
            return
        ts = float(self._fx_knobs.get("taper_s", 0.0))
        el = now - self._fx_on_since
        if ts <= 0.0 or el >= ts:
            self._fx_taper_done = True
            with self._fx_lock:
                n = dict(self._fx_n)
            print("[BrainstemReflex] [fix] the old warmth has tapered out (%d pulses, %d sentences over %.0f s)"
                  % (n.get("taper_pulses", 0), n.get("taper_sentences", 0), max(0.0, ts)), flush=True)
            return
        if self._fx_taper_next is None or now < self._fx_taper_next:
            return
        f = max(0.0, 1.0 - el / ts)
        nxt = self._fx_taper_next + FIX_TAPER_PERIOD_S
        self._fx_taper_next = nxt if nxt > now else now + FIX_TAPER_PERIOD_S      # after a jam: one pulse, never a burst
        parts = []
        for chem, base in (FIX_TAPER_DOSE if self._fx_knobs.get("taper_chem", True) else ()):
            d = round(base * f, 3)
            if d > 0.0:
                self.post.publish("somatic.chemistry", {"chemical": chem, "delta": d, "source": "brainstem_reflex_taper",
                                                        "mode": "seek_taper"})
                self._fx_note_self(chem, d, now, "taper")
                parts.append(f"{chem}+{d:.2f}")
        self._fx_taper_acc += f
        if self._fx_taper_acc >= 1.0:
            self._fx_taper_acc -= 1.0
            self.emit_if_awake("consciousness.feeling", {"content": FIX_FELT[ReflexMode.SEEK], "source": "brainstem_reflex",
                                                         "intensity": round(0.5 * f, 3), "mode": "seek_taper"})
            self._fx_count("taper_sentences")
        self._fx_count("taper_pulses")
        if parts:
            print(f"[BrainstemReflex] Somatic response: {', '.join(parts)} [fix: taper {f:.2f}]")

    def _fx_retain(self, now: float) -> None:
        if self._fx_retain_t is None or now - self._fx_retain_t >= FIX_RETAIN_S or now < self._fx_retain_t:
            self._fx_retain_t = now
            self.emit_if_awake("reflex.mode", self._fx_state_packet(now, retained=True))
            self._fx_count("retained")
        if (not self._fx_replayed and self._fx_booted_t is not None and now - self._fx_booted_t >= FIX_LATE_REPLAY_S):
            self._fx_replayed = True
            rs = self._reflex_state
            lg = self._fx_last_legacy
            if lg is not None and rs.mode != ReflexMode.NORMAL and lg[0] == rs.mode.value:
                self.emit_if_awake("reflex.mode_change", {"old_mode": "normal", "new_mode": rs.mode.value,
                                                          "reason": rs.trigger_reason, "intensity": rs.intensity, "ts": now,
                                                          "chain": False, "replay": True, "seq": self._fx_seq,
                                                          "source": "brainstem_fix"})
                self._fx_count("late_replay")

    def _fx_view(self) -> dict:
        with self._fx_lock:
            n = dict(self._fx_n)
            chains_h = len(self._fx_chain_ts)
        on, knobs, why = self._fx_sw
        rsm = self._fx_resume                     # one read: the tick may replace it
        return {"on": bool(self._fx_on_cached), "switch": why, "latched_off": bool(self._fx_latched_off),
                "knobs": {k: (list(v) if isinstance(v, tuple) else v) for k, v in self._fx_knobs.items()},
                "signals": {k: round(v, 4) for k, v in dict(self._fx_sig).items() if _fx_finite(v)},
                "counts": n, "errors": self._fx_err_n, "seq": self._fx_seq, "chains_logged": chains_h,
                "taper": {"since": self._fx_on_since, "done": bool(self._fx_taper_done), "resumed_at_f": self._fx_taper_f0},
                "resume_offer": rsm[0].value if rsm else None, "inherited": bool(self._fx_inherit)}


# ══════════════════════════════════════════════════════════════════════════════
# ONE BRAINSTEM (brainstem_fix 2026-10-05; MAP-E 1j, MAP 5c.5)
# Before: get_brainstem() built a module-global SECOND instance with fabric=None and start_brainstem() booted it. A booted
# second copy takes the heartbeat callback by name (G:2039 "OVERWRITE ... callback replaced"), and its mode read "normal"
# forever. Now: the booted instance (the one beating now), or an inert stand-in that can never boot, beat or publish.
# Nothing below constructs a BrainstemReflexFairy.
# ══════════════════════════════════════════════════════════════════════════════

_brainstem: Optional[BrainstemReflexFairy] = None     # kept for old importers; never assigned (no second copy)
_ONE_LOCK = threading.Lock()
_ONE = {"booted": [], "beater": None, "inert": None}


class _InertBrainstem:
    """What get_brainstem() returns before her brainstem has booted: it reads 'normal' and can never boot, beat,
    subscribe or publish (the old code built and booted a real second fairy here)."""
    is_running = False
    inert = True

    def __init__(self):
        self._reflex_state = ReflexState()

    def boot(self, *a, **k):
        print("[BrainstemReflex] [ONE-BRAINSTEM] refused to boot a second brainstem (the orchestrator boots hers)", flush=True)
        return False

    def start(self, *a, **k):
        return None

    def stop(self, *a, **k):
        return None

    def set_callbacks(self, *a, **k):
        return None

    def update_chemistry(self, *a, **k):
        return None

    def update_pain_drives(self, *a, **k):
        return None

    def update_body_budget(self, *a, **k):
        return None

    def get_state(self) -> dict:
        return {"mode": "normal", "inert": True}

    def get_reflex_state(self) -> dict:
        return self.get_state()


def _register_booted(inst) -> None:
    with _ONE_LOCK:
        if not any(x is inst for x in _ONE["booted"]):
            _ONE["booted"].append(inst)
        n = len(_ONE["booted"])
    if n > 1:
        print("[BrainstemReflex] [ONE-BRAINSTEM] WARNING: %d brainstems booted in this process -- the heartbeat keeps one "
              "callback by name, and touch's reflex link reads two beaters and stays closed" % n, flush=True)


def _set_beater(inst) -> None:
    _ONE["beater"] = inst


def get_brainstem(fabric=None):
    """Her BOOTED brainstem (the one beating now), else an inert stand-in. Never constructs or boots a fairy."""
    with _ONE_LOCK:
        b = _ONE["beater"]
        if b is None and _ONE["booted"]:
            b = _ONE["booted"][0]
        if b is not None:
            return b
        if _ONE["inert"] is None:
            _ONE["inert"] = _InertBrainstem()
        return _ONE["inert"]


class _LegacyBrainstemView:
    """What start_brainstem() hands its two legacy callers (_embodiment_integrator.py:80, awakening_trigger.py:78). Reads
    delegate to her booted brainstem (or the inert stand-in); set_callbacks, boot, start, stop and the update_* pushes are
    REFUSED. Before this fix those callers reached a dead second copy, so their callbacks never touched her live brainstem;
    this keeps it so -- EI's set_callbacks(on_mode_change=...) maps modes onto named emotions for speech (EI:465-480),
    which must never be wired onto her real modes by accident (verify_tests F8, verify_behaviour F7)."""
    legacy = True
    _said = [False]

    def set_callbacks(self, *a, **k):
        if not self._said[0]:
            self._said[0] = True
            print("[BrainstemReflex] [ONE-BRAINSTEM] a legacy caller's set_callbacks was refused (read-only view)", flush=True)
        return None

    def boot(self, *a, **k):
        return False

    def start(self, *a, **k):
        return None

    def stop(self, *a, **k):
        return None

    def update_chemistry(self, *a, **k):
        return None

    def update_pain_drives(self, *a, **k):
        return None

    def update_body_budget(self, *a, **k):
        return None

    def __getattr__(self, name):
        return getattr(get_brainstem(), name)


_LEGACY_VIEW = _LegacyBrainstemView()


def start_brainstem(fabric=None):
    """Legacy (_embodiment_integrator.py:80, awakening_trigger.py:78): a READ-ONLY view of the booted brainstem. It never
    constructs or boots anything, and it never lets a legacy caller wire callbacks onto her live brainstem."""
    return _LEGACY_VIEW


def update_brainstem_chemistry(chemistry: Dict[str, float]):
    """Legacy push: IGNORED. A pushed partial dict is the absent-key shape of the stuck SEEK (BR:972 / :1023); the fixed
    brainstem pulls her chemistry itself. Its only caller is awakening_trigger.py, a manual tool, which reached a dead
    second copy before this fix -- so ignoring it changes nothing she lived."""
    return None


def update_brainstem_pain(pain_drives: Dict[str, float]):
    """Legacy push: IGNORED (see update_brainstem_chemistry)."""
    return None


def get_reflex_mode() -> str:
    """The booted brainstem's live mode ('normal' before it boots)."""
    try:
        return get_brainstem()._reflex_state.mode.value
    except Exception:
        return "normal"
