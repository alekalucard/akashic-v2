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
                                ((k, v) for k, v in self._chemistry.items()
                                 if not k.endswith("_delta") and isinstance(v, (int, float))),
                                key=lambda kv: -abs(kv[1]),
                            )[:4]
                            budget_items = sorted(
                                ((k, v) for k, v in self._body_budget.items()
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
        """Get current reflex state."""
        return {
            "mode": self._reflex_state.mode.value,
            "mode_since": self._reflex_state.mode_since,
            "trigger_reason": self._reflex_state.trigger_reason,
            "intensity": self._reflex_state.intensity,
            "actions_taken": self._reflex_state.actions_taken[-5:],
            "chemistry": self._chemistry.copy(),
        }

    def get_reflex_state(self) -> dict:
        """Get current reflex state (alias for get_state)."""
        return self.get_state()

    def force_mode(self, mode: str, reason: str = "forced"):
        """Force a mode transition (for testing)."""
        try:
            new_mode = ReflexMode(mode)
            self._transition_mode(new_mode, self._chemistry)
        except ValueError:
            print(f"[BrainstemReflex] Unknown mode: {mode}")


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE (Legacy compatibility)
# ══════════════════════════════════════════════════════════════════════════════
# NOTE: For proper system integration, use the boot orchestrator to create
# BrainstemReflexFairy with a shared fabric. These functions exist for
# backward compatibility and testing.
# ══════════════════════════════════════════════════════════════════════════════

_brainstem: Optional[BrainstemReflexFairy] = None


def get_brainstem(fabric=None) -> BrainstemReflexFairy:
    """Get or create the global brainstem reflex system."""
    global _brainstem
    if _brainstem is None:
        _brainstem = BrainstemReflexFairy(fabric=fabric)
    return _brainstem


def start_brainstem(fabric=None):
    """Start the brainstem monitoring (boots the fairy)."""
    brainstem = get_brainstem(fabric)
    # Boot the fairy properly through the template
    if not brainstem.is_running:
        brainstem.boot()
    return brainstem


def update_brainstem_chemistry(chemistry: Dict[str, float]):
    """Update brainstem with current chemistry."""
    brainstem = get_brainstem()
    brainstem.update_chemistry(chemistry)


def update_brainstem_pain(pain_drives: Dict[str, float]):
    """Update brainstem with current pain drives."""
    brainstem = get_brainstem()
    brainstem.update_pain_drives(pain_drives)


def get_reflex_mode() -> str:
    """Get current reflex mode."""
    brainstem = get_brainstem()
    return brainstem._reflex_state.mode.value
