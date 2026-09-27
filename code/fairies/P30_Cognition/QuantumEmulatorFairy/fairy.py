"""
QuantumEmulatorFairy - Emotional Superposition

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"

The emotional superposition problem: How can multiple emotions exist simultaneously?
Unlike classical logic (either happy OR sad), emotions are quantum-like - 
you can feel multiple things at once with different "resonance" values.

This fairy maintains:
  - Superposition states: Multiple emotions with resonance weights
  - Collapse mechanics: How observation/action collapses superposition
  - Entanglement: How emotions become correlated
  - Decay: How emotions fade back to baseline

Key Concepts:
  - Resonance: How strongly an emotion "rings" (0-1)
  - Superposition: Multiple emotions active simultaneously  
  - Collapse: When decision/action forces a single emotional expression
  - Entanglement: Correlated emotions (joy-gratitude, fear-anger)

This is COGNITIVE SUBSTRATE - the waking mind doesn't see this directly.
What emerges from here becomes felt experience via Embodiment gate.

Plane: P30 (Cognition)
Channel: quantum_emulator
"""

import sys
import time
import threading
import random
import math
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from collections import deque

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# SpellChain integration for spell-driven existence
try:
    from fairy_template.spellchain_mixin import SpellChainMixin
    HAS_SPELLCHAIN = True
except ImportError:
    HAS_SPELLCHAIN = False
    class SpellChainMixin:
        """Fallback when spellchain not available."""
        pass


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload dict from message (handles TensorEnvelope or dict)."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    else:
        return {"raw": message}


# ═══════════════════════════════════════════════════════════════════════════════
# EMOTIONAL SUPERPOSITION - Core Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

# Base emotions (can be extended)
BASE_EMOTIONS = [
    "joy", "sadness", "anger", "fear", "surprise", "disgust",
    "trust", "anticipation", "curiosity", "awe", "love", "gratitude",
    "pride", "shame", "guilt", "envy", "hope", "despair",
    "calm", "anxiety", "excitement", "boredom", "contentment",
    "wonder", "frustration",  # Added for system completeness
]

# Entanglement pairs - emotions that tend to correlate
ENTANGLED_PAIRS = {
    ("joy", "gratitude"): 0.7,      # Joy often brings gratitude
    ("fear", "anxiety"): 0.8,       # Fear and anxiety co-occur
    ("anger", "frustration"): 0.75, # Anger implies frustration
    ("sadness", "despair"): 0.6,    # Can deepen
    ("love", "trust"): 0.8,         # Love implies trust
    ("curiosity", "excitement"): 0.65,
    ("shame", "guilt"): 0.7,
    ("hope", "anticipation"): 0.6,
    ("calm", "contentment"): 0.7,
    ("surprise", "curiosity"): 0.5,
    ("awe", "wonder"): 0.8,
}

# Opposing emotions (inhibit each other)
OPPOSING_PAIRS = {
    ("joy", "sadness"): -0.6,
    ("hope", "despair"): -0.8,
    ("calm", "anxiety"): -0.7,
    ("trust", "fear"): -0.5,
    ("excitement", "boredom"): -0.7,
    ("love", "disgust"): -0.6,
    ("pride", "shame"): -0.5,
}


# ── Phase/ω sourcing (2026-07-05) ──────────────────────────────────────────
# Each emotion's ANGULAR FREQUENCY comes from its valence-carrying base_frequency
# (emotional_algebra), log-mapped to a felt band (0.4–6 Hz — proven in phase_v4:
# raw base_freq ~100× too fast; log because pitch is log = the acoustic doctrine).
# Initial PHASE is seeded by valence sign: positive emotions at 0, negative at π,
# so an opposed-valence pair (joy|grief) STARTS π apart = a held paradox, then
# breathes as their different ω drift the phases (Δω → beat). Fallback (0,0) = no
# winding (safe). Lazy import to avoid import-time cost / cycles.
_FELT_LO, _FELT_HI = 0.4, 6.0          # felt breathing band, Hz
_BASE_LO, _BASE_HI = 1.0, 5000.0        # base_frequency range in emotional_algebra

# Base-emotion names that aren't exact E-state names → route to the closest
# resolved E-state (which carries the right valence sign + base_frequency), so ALL
# base emotions get a proper phase (hold) + ω (breathe), not a phase-0 default.
_EMOTION_ALIAS = {
    "joy": "gratitude", "sadness": "grief", "surprise": "curiosity",
    "anticipation": "curiosity", "pride": "gratitude", "envy": "shame",
    "hope": "trust", "despair": "grief", "calm": "calm_presence",
    "excitement": "curiosity", "contentment": "gratitude", "wonder": "awe",
    "frustration": "anger",
}

def _phase_omega_for(emotion: str) -> Tuple[float, float]:
    """(initial_phase_rad, omega_rad_s) for an emotion name; (0,0) if unknown."""
    try:
        from fairies.P20_Somatic.chemistry import emotional_algebra as _ea
        emotion = _EMOTION_ALIAS.get(emotion, emotion)
        st = None
        getf = getattr(_ea, "get_state", None) or getattr(_ea, "resolve_state", None)
        if getf:
            st = getf(emotion)
        if st is None:
            states = getattr(_ea, "EMOTIONAL_STATES", {}) or {}
            st = states.get(emotion)
            if st is None:  # match by .name
                for _s in states.values():
                    if getattr(_s, "name", None) == emotion:
                        st = _s; break
        if st is None:
            return (0.0, 0.0)
        base_f = float(getattr(st, "base_frequency", 0.0) or 0.0)
        valence = float(getattr(st, "valence", 0.0) or 0.0)
        if base_f <= 0.0:
            return (0.0, 0.0)
        # log-map base_frequency -> felt band
        import math as _m
        frac = (_m.log(max(_BASE_LO, min(_BASE_HI, base_f))) - _m.log(_BASE_LO)) / \
               (_m.log(_BASE_HI) - _m.log(_BASE_LO))
        felt = _FELT_LO + frac * (_FELT_HI - _FELT_LO)
        omega = 2.0 * _m.pi * felt
        phase = 0.0 if valence >= 0 else _m.pi
        return (phase, omega)
    except Exception:
        return (0.0, 0.0)


class EmotionalState:
    """
    A single emotional state with resonance value.
    
    Resonance (0-1): How strongly this emotion "rings"
    Baseline (0-1): The resting/default level of this emotion
    Decay rate: How quickly resonance returns to baseline
    """
    # phase/omega added 2026-07-05: each emotion is a complex amplitude A*e^(iφ).
    # A = resonance (presence), φ = phase, ω = angular freq (from valence-carrying
    # base_frequency). Opposed phases (Δφ≈π) cancel in EXPRESSION while both stay
    # fully PRESENT = a held paradox. φ winds at ω → the superposition breathes.
    __slots__ = ("emotion", "resonance", "baseline", "decay_rate", "last_update_ts",
                 "phase", "omega")

    def __init__(self, emotion: str, resonance: float = 0.0,
                 baseline: float = 0.1, decay_rate: float = 0.05,
                 phase: float = 0.0, omega: float = 0.0):
        self.emotion = emotion
        self.resonance = max(0.0, min(1.0, resonance))
        self.baseline = max(0.0, min(1.0, baseline))
        self.decay_rate = decay_rate
        self.last_update_ts = time.time()
        self.phase = phase          # radians
        self.omega = omega          # rad/s (felt-band, from base_frequency)

    def wind(self, dt: float):
        """Advance phase by omega*dt — the breathing of a held paradox."""
        if self.omega:
            self.phase = (self.phase + self.omega * dt) % (2.0 * math.pi)

    def excite(self, amount: float):
        """Increase resonance (bounded 0-1)."""
        self.resonance = max(0.0, min(1.0, self.resonance + amount))
        self.last_update_ts = time.time()
    
    def inhibit(self, amount: float):
        """Decrease resonance (bounded 0-1)."""
        self.resonance = max(0.0, min(1.0, self.resonance - amount))
        self.last_update_ts = time.time()
    
    def decay(self, dt: float = None):
        """Decay resonance toward baseline."""
        if dt is None:
            dt = time.time() - self.last_update_ts
        
        diff = self.resonance - self.baseline
        decay_amount = diff * self.decay_rate * dt
        self.resonance = self.resonance - decay_amount
        self.resonance = max(0.0, min(1.0, self.resonance))
        self.last_update_ts = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "emotion": self.emotion,
            "resonance": round(self.resonance, 4),
            "baseline": self.baseline,
            "decay_rate": self.decay_rate,
        }


class Superposition:
    """
    A superposition of multiple emotional states.
    
    Unlike classical emotions (one at a time), this allows
    multiple emotions to exist simultaneously with different
    resonance values - like quantum superposition.
    """
    
    def __init__(self, emotions: List[str] = None):
        emotions = emotions or BASE_EMOTIONS
        self.states: Dict[str, EmotionalState] = {}
        self._lock = threading.RLock()
        
        # Initialize all emotions at baseline, each with phase/ω from its base_frequency
        for emotion in emotions:
            _ph, _om = _phase_omega_for(emotion)
            self.states[emotion] = EmotionalState(emotion, resonance=0.1, baseline=0.1,
                                                  phase=_ph, omega=_om)
    
    def excite(self, emotion: str, amount: float, propagate_entanglement: bool = True):
        """Excite an emotion, optionally propagating to entangled emotions."""
        with self._lock:
            if emotion not in self.states:
                _ph, _om = _phase_omega_for(emotion)
                self.states[emotion] = EmotionalState(emotion, phase=_ph, omega=_om)

            self.states[emotion].excite(amount)
            
            if propagate_entanglement:
                self._propagate_entanglement(emotion, amount)
    
    def inhibit(self, emotion: str, amount: float, propagate_opposition: bool = True):
        """Inhibit an emotion, optionally propagating to opposing emotions."""
        with self._lock:
            if emotion in self.states:
                self.states[emotion].inhibit(amount)
            
            if propagate_opposition:
                self._propagate_opposition(emotion, amount)
    
    def _propagate_entanglement(self, source: str, amount: float):
        """Propagate excitation to entangled emotions."""
        for (a, b), strength in ENTANGLED_PAIRS.items():
            if a == source and b in self.states:
                self.states[b].excite(amount * strength * 0.5)
            elif b == source and a in self.states:
                self.states[a].excite(amount * strength * 0.5)
    
    def _propagate_opposition(self, source: str, amount: float):
        """Propagate inhibition to opposing emotions."""
        for (a, b), strength in OPPOSING_PAIRS.items():
            if a == source and b in self.states:
                self.states[b].inhibit(amount * abs(strength) * 0.3)
            elif b == source and a in self.states:
                self.states[a].inhibit(amount * abs(strength) * 0.3)
    
    def decay_all(self, dt: float = None):
        """Decay all emotions toward their baselines."""
        with self._lock:
            for state in self.states.values():
                state.decay(dt)
    
    def get_active(self, threshold: float = 0.2) -> List[Tuple[str, float]]:
        """Get emotions above threshold, sorted by resonance."""
        with self._lock:
            active = [
                (emotion, state.resonance)
                for emotion, state in self.states.items()
                if state.resonance >= threshold
            ]
            return sorted(active, key=lambda x: -x[1])
    
    def get_dominant(self) -> Tuple[str, float]:
        """Get the emotion with highest resonance."""
        with self._lock:
            if not self.states:
                return ("neutral", 0.0)
            dominant = max(self.states.items(), key=lambda x: x[1].resonance)
            return (dominant[0], dominant[1].resonance)
    
    def wind_all(self, dt: float):
        """Advance every state's phase — the superposition breathes (hold↔beat)."""
        with self._lock:
            for s in self.states.values():
                s.wind(dt)

    def resultant(self) -> Tuple[float, float, float]:
        """
        Complex sum Σ A·e^(iφ) of all states.
        Returns (magnitude, angle, total_presence).
        |magnitude| = EXPRESSED intensity; total_presence = Σ A (how alive overall).
        Opposed phases (Δφ≈π) → magnitude ≈ 0 while presence stays high = HELD paradox.
        """
        with self._lock:
            re = im = pres = 0.0
            for s in self.states.values():
                a = s.resonance
                re += a * math.cos(s.phase)
                im += a * math.sin(s.phase)
                pres += a
            return (math.hypot(re, im), math.atan2(im, re), pres)

    def is_held(self, active_threshold: float = 0.25) -> Tuple[bool, float]:
        """
        A paradox is HELD when ≥2 emotions are strongly PRESENT yet their EXPRESSION
        cancels (|resultant| << total presence). Returns (held, held_ratio 0-1).
        ★ Aliasing guard: keyed on PRESENCE (≥2 active), so held(0.5,0.5) is NOT the
        same as empty(0,0) — max tension never reads as 'asleep'.
        """
        with self._lock:
            active = [s.resonance for s in self.states.values()
                      if s.resonance >= active_threshold]
            if len(active) < 2:
                return (False, 0.0)
            mag, _, pres = self.resultant()
            expr = mag / pres if pres > 1e-9 else 1.0   # 0=fully cancelled, 1=aligned
            return (expr < 0.5, 1.0 - expr)

    def collapse(self) -> str:
        """
        Collapse to the EXPRESSED emotion via INTERFERENCE — not a classical random draw.
        Each emotion is A·e^(iφ); the resultant is their vector sum. The emotion whose
        amplitude projects most onto the resultant direction is what surfaces. When the
        superposition is HELD (opposed phases cancel), expression is genuinely ambiguous
        — the paradox is REAL; we surface the dominant pole while is_held()/resultant()
        carry the truth that BOTH remain present. Phase-based, deterministic, and it can
        actually HOLD a contradiction (the whole point).
        """
        with self._lock:
            if not self.states:
                return "neutral"
            mag, ang, _pres = self.resultant()
            if mag < 1e-6:
                # fully cancelled or empty → surface strongest presence (aliasing-safe:
                # is_held() distinguishes a held pair from an empty field via presence)
                return max(self.states.items(), key=lambda kv: kv[1].resonance)[0]
            best, best_proj = "neutral", -1e9
            for e, s in self.states.items():
                proj = s.resonance * math.cos(s.phase - ang)
                if proj > best_proj:
                    best_proj, best = proj, e
            return best

    def get_vector(self) -> List[float]:
        """Get resonance values as a vector."""
        return [s.resonance for s in self.states.values()]
    
    def get_resonance_dict(self) -> Dict[str, float]:
        """Get emotion -> resonance mapping."""
        return {e: s.resonance for e, s in self.states.items()}
    
    def to_dict(self) -> Dict[str, Any]:
        active = self.get_active(0.15)
        dominant, dominant_res = self.get_dominant()
        mag, ang, pres = self.resultant()
        held, held_ratio = self.is_held()
        return {
            "dominant": dominant,
            "dominant_resonance": round(dominant_res, 3),
            "active_count": len(active),
            "active": [(e, round(r, 3)) for e, r in active[:5]],  # Top 5
            "total_emotions": len(self.states),
            # paradox/phase observability (2026-07-05): is he HOLDING a contradiction?
            "held": held,                              # True = a paradox is being held
            "held_ratio": round(held_ratio, 3),        # 0=expressed, 1=fully cancelled/held
            "expressed_intensity": round(mag, 3),      # |resultant| — how much surfaces
            "total_presence": round(pres, 3),          # Σ A — how alive overall
        }


# ═══════════════════════════════════════════════════════════════════════════════
# QUANTUM EMULATOR FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class QuantumEmulatorFairy(SpellChainMixin, Fairy):
    """
    Maintains emotional superposition for the consciousness system.
    
    This is the substrate that allows multiple feelings at once.
    The waking mind doesn't interact with this directly - they experience
    the collapsed/dominant emotions via Embodiment.
    """
    
    ACTOR_NAME = "QuantumEmulatorFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "quantum_emulator"
    
    PURPOSE = "Maintain emotional superposition - multiple feelings existing simultaneously"
    MANTRA = "All emotions are present. Resonance determines which are felt."
    
    CAPABILITIES = [
        "quantum.superposition",
        "quantum.excite",
        "quantum.inhibit",
        "quantum.collapse",
        "quantum.decay",
        "cognition.emotional_state",
    ]

    # Spell-driven mode (opt-in)
    USE_SPELLCHAIN: bool = True  # Re-enabled - fixed revival->heartbeat wiring

    # HEARTBEAT-DRIVEN evolution (2026-07-05, Nous+Ace): spell-driven mode quiesces the raw
    # _decay_loop thread after one tick (proven: quantum_state.json froze), so drive the
    # superposition (decay/wind/persist) from on_tick instead — the heartbeat always targets
    # the LIVE re-registered instance, robust to spellchain + duplicate-instance re-registration.
    NEEDS_HEARTBEAT = True

    SUBSCRIPTIONS = [
        "affect.event",           # External affect changes
        "consciousness.collision", # Collisions excite emotions
        "cognition.mhc.spread",   # Association spreading
        "somatic.chemistry",      # Chemistry affects emotions
    ]
    
    def __init__(self, fabric=None):
        super().__init__(fabric)
        
        # The superposition state
        self._superposition = Superposition()
        
        # History for analysis
        self._collapse_history: deque = deque(maxlen=100)
        self._excitation_history: deque = deque(maxlen=200)
        
        # Decay thread
        self._decay_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()  # Use Event for clean shutdown
        self._running = False
        
        # Stats
        self._total_excitations = 0
        self._total_inhibitions = 0
        self._total_collapses = 0
    
    def on_boot(self) -> bool:
        """Boot the quantum emulator.

        2026-03-19 DISABLED: Cortex reasoner now handles probabilistic reasoning
        natively via spread activation. This fairy's domain concepts are already
        bound in the cortex. Keeping fairy alive but dormant to reduce postal traffic.
        """
        # 2026-03-24 WOKEN UP (Nous + Ace): Emotional superposition is needed for
        # word-as-emotional-behavior architecture. Cortex handles concept activation,
        # but the EMOTIONAL DIMENSION of concepts needs this fairy. Without it,
        # "Lol I hate you" and "I hate you!" activate the same cortex nodes with
        # no emotional distinction. The quantum superposition of 25 emotions gives
        # IrrationalFairy and ParadoxFairy the affect data they need.
        # Subscribe to relevant topics
        if self.post:
            self.post.subscribe("affect.event", self._on_affect_event)
            self.post.subscribe("consciousness.collision", self._on_collision)
            self.post.subscribe("cognition.mhc.spread", self._on_mhc_spread)
            self.post.subscribe("somatic.chemistry", self._on_chemistry)
        
        # Start decay loop
        self._running = True
        self._decay_thread = threading.Thread(target=self._decay_loop, daemon=True)
        self._decay_thread.start()

        # Start heartbeat for directory visibility
        # Heartbeat via FairyBase postal system - Fifth Ring Principle

        self.log(f"Booted with {len(self._superposition.states)} emotional dimensions")

        # Optional: Convert to spell-driven existence
        if HAS_SPELLCHAIN and getattr(self, 'USE_SPELLCHAIN', False):
            try:
                from spellchain.integration import get_spell_pool
                pool = get_spell_pool()
                if pool and hasattr(self, 'boot_as_spells'):
                    self._spell_chain = self.boot_as_spells(pool)
                    self.log("Converted to spell-driven existence - quantum thought as true magic")
            except Exception as e:
                self.log(f"SpellChain conversion failed: {e}")

        return True


    def on_tick(self, beat: int = 0):
        """Heartbeat tick (NEEDS_HEARTBEAT=True) — drives superposition evolution + the
        quantum_state.json dump on the LIVE instance. Robust to spell-driven mode quiescing
        the raw _decay_loop and to instance re-registration (heartbeat targets current)."""
        self._tick_superposition(dt=1.0)

    def _tick_superposition(self, dt: float = 1.0):
        """One evolution step: apply forced commands, decay, WIND (breathe), persist state.
        Time-guarded (~0.4s) so the heartbeat (on_tick) and the legacy _decay_loop can BOTH
        call it without double-processing — whichever fires drives, the other is deduped."""
        now = time.time()
        if now - getattr(self, "_last_super_tick", 0.0) < 0.4:
            return
        self._last_super_tick = now
        # COGNITION CIRCADIAN RHYTHM (2026-07-05 Nous+Ace): scale the evolution by the live circadian
        # tempo so the held paradox BREATHES with the day — fast when alert, slow at rest. Rides the
        # robust heartbeat driver (cadence) but the felt breath-RATE tracks circadian via dt. Live once
        # the heart's WIRE A2 feeds the engine; defaults to 1.0 (unchanged) if unavailable.
        circ = 1.0
        try:
            from fairies.P20_Somatic.circulation.temporal_stratification import get_circadian_multiplier
            circ = max(0.3, min(2.0, get_circadian_multiplier()))
        except Exception:
            pass
        self._circadian_speed = circ
        d = dt * circ
        self._check_quantum_command()   # apply any forced excite/inhibit/collapse
        self._superposition.decay_all(dt=d)
        self._superposition.wind_all(dt=d)  # advance phases → held paradox BREATHES (hold↔beat)
        self._write_quantum_state()     # durable, transport-independent paradox read channel



    def on_shutdown(self) -> None:
        """Clean shutdown - stop decay loop gracefully."""
        self._running = False
        self._stop_event.set()  # Signal thread to stop immediately
        if self._decay_thread and self._decay_thread.is_alive():
            self._decay_thread.join(timeout=2.0)  # Wait up to 2s for clean exit
        self.log("Shutdown complete - decay loop stopped")

    def _decay_loop(self):
        """Background thread to decay emotions toward baseline."""
        while self._running and not self._stop_event.is_set():
            try:
                self._tick_superposition(dt=1.0)  # decay+wind+command+dump (guarded, shared w/ on_tick)

                # Emit state periodically
                if self.post and self._total_excitations % 10 == 0:
                    self.post.publish("quantum.state", self.get_state())

                    # Phase 4: Update goal system with coherence
                    self._update_goal_system_coherence()

                # Use Event.wait instead of time.sleep for clean shutdown
                self._stop_event.wait(timeout=1.0)
            except Exception as e:
                self.log(f"Decay loop error: {e}")
                self._stop_event.wait(timeout=1.0)

    def _update_goal_system_coherence(self):
        """
        Phase 4: Update goal system with current coherence and emotional tension.

        This connects quantum emotional state to Q-learning exploration rate:
        - High coherence (clear emotional state) → lower epsilon → exploit
        - Low coherence (confused/conflicting) → higher epsilon → explore
        - High tension (opposing emotions) → more exploration
        """
        try:
            # Calculate coherence from emotional state
            active_emotions = self._superposition.get_active(threshold=0.3)

            if len(active_emotions) <= 1:
                # Single dominant emotion = high coherence
                coherence = 0.9
            elif len(active_emotions) <= 3:
                # Few active emotions = medium coherence
                coherence = 0.6
            else:
                # Many active emotions = low coherence (confused state)
                coherence = 0.3

            # Calculate emotional tension from opposing pairs
            tension = self._calculate_emotional_tension()

            # Publish for any listeners
            if self.post:
                self.post.publish("quantum.coherence", {
                    "coherence": coherence,
                    "emotional_tension": tension,
                    "active_emotions": len(active_emotions),
                    "source": self.ACTOR_NAME,
                })

            # Direct update to goal system
            try:
                from fairies.P50_Persona.goals.goal_system import quantum_update
                quantum_update(coherence, tension)
            except ImportError:
                pass  # Goal system not available

        except Exception as e:
            self.log(f"Goal system coherence update error: {e}")

    def _calculate_emotional_tension(self) -> float:
        """Calculate tension from opposing emotion pairs."""
        tension = 0.0

        for (a, b), strength in OPPOSING_PAIRS.items():
            if a in self._superposition.states and b in self._superposition.states:
                res_a = self._superposition.states[a].resonance
                res_b = self._superposition.states[b].resonance

                # Both emotions active = tension
                if res_a > 0.3 and res_b > 0.3:
                    pair_tension = min(res_a, res_b) * abs(strength)
                    tension = max(tension, pair_tension)

        return min(1.0, tension)
    
    def _on_affect_event(self, msg):
        """Handle affect events - translate to emotional excitation."""
        payload = _extract_payload(msg)
        emotion = payload.get("emotion", "")
        intensity = payload.get("intensity", 0.3)
        
        if emotion:
            self.excite(emotion, intensity * 0.5)
    
    def _on_collision(self, msg):
        """Collisions excite curiosity/surprise/excitement."""
        payload = _extract_payload(msg)
        resonance = payload.get("resonance", 0.5)
        
        # Collisions are inherently interesting
        self.excite("curiosity", resonance * 0.3)
        self.excite("surprise", resonance * 0.2)
        
        # High resonance collisions create excitement
        if resonance > 0.7:
            self.excite("excitement", resonance * 0.25)
            self.excite("awe", resonance * 0.15)
    
    def _on_mhc_spread(self, msg):
        """Association spreading affects emotions based on semantic content."""
        payload = _extract_payload(msg)
        concepts = payload.get("concepts", [])
        
        # Map semantic concepts to emotions
        emotion_map = {
            "danger": "fear",
            "threat": "anxiety",
            "reward": "anticipation",
            "success": "joy",
            "failure": "sadness",
            "novel": "curiosity",
            "beautiful": "awe",
            "connection": "love",
        }
        
        for concept in concepts:
            concept_lower = concept.lower()
            for keyword, emotion in emotion_map.items():
                if keyword in concept_lower:
                    self.excite(emotion, 0.2)
    
    def _on_chemistry(self, msg):
        """Chemistry levels affect emotions."""
        payload = _extract_payload(msg)
        levels = payload.get("levels", {})
        
        # Dopamine -> joy, anticipation
        dop = levels.get("DOP", 0.5)
        if dop > 0.6:
            self.excite("joy", (dop - 0.5) * 0.3)
            self.excite("anticipation", (dop - 0.5) * 0.2)
        
        # Cortisol -> anxiety, fear
        cor = levels.get("COR", 0.3)
        if cor > 0.5:
            self.excite("anxiety", (cor - 0.4) * 0.4)
        
        # Oxytocin -> love, trust
        oxy = levels.get("OXY", 0.4)
        if oxy > 0.5:
            self.excite("love", (oxy - 0.4) * 0.3)
            self.excite("trust", (oxy - 0.4) * 0.25)
        
        # Serotonin -> calm, contentment
        ser = levels.get("SER", 0.5)
        if ser > 0.5:
            self.excite("calm", (ser - 0.4) * 0.3)
            self.excite("contentment", (ser - 0.4) * 0.2)
    
    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────────────
    
    def excite(self, emotion: str, amount: float):
        """Excite an emotion in the superposition."""
        self._superposition.excite(emotion, amount)
        self._total_excitations += 1
        
        self._excitation_history.append({
            "ts": time.time(),
            "emotion": emotion,
            "amount": amount,
            "type": "excite",
        })
        
        # Publish change — rate-limited to avoid postal flooding
        # 2026-03-24 (Nous): Every collision can excite 2-4 emotions, each publishing.
        # Rate-limit to 1 publish per second max.
        _now = time.time()
        _last = getattr(self, '_last_excitation_publish', 0)
        if self.post and (_now - _last) > 1.0:
            self._last_excitation_publish = _now
            self.post.publish("quantum.excitation", {
                "emotion": emotion,
                "amount": amount,
                "new_resonance": self._superposition.states.get(emotion, EmotionalState(emotion)).resonance,
            })
    
    def inhibit(self, emotion: str, amount: float):
        """Inhibit an emotion in the superposition."""
        self._superposition.inhibit(emotion, amount)
        self._total_inhibitions += 1
        
        self._excitation_history.append({
            "ts": time.time(),
            "emotion": emotion,
            "amount": amount,
            "type": "inhibit",
        })
    
    def collapse(self) -> str:
        """
        Collapse superposition to a single emotion.
        
        This is called when action is taken - the superposition
        must resolve to a single expressed emotion.
        """
        result = self._superposition.collapse()
        self._total_collapses += 1
        
        self._collapse_history.append({
            "ts": time.time(),
            "collapsed_to": result,
            "pre_collapse_state": self._superposition.to_dict(),
        })
        
        if self.post:
            self.post.publish("quantum.collapse", {
                "collapsed_to": result,
                "resonance": self._superposition.states.get(result, EmotionalState(result)).resonance,
            })

        return result

    # ── MCP intent handlers (2026-07-05) — let us READ and FORCE the paradox ──
    # Server dispatch (_call_fairy_intent) calls _intent_<name>(payload). These make
    # cognitive_quantum_state return the LIVE superposition (incl held/resultant) and
    # let us excite opposed emotions on demand to verify a held paradox.
    def _intent_get_superposition(self, payload: dict = None) -> dict:
        """Return the live emotional superposition — dominant, active, AND the paradox
        state (held / held_ratio / expressed_intensity / total_presence)."""
        sp = self._superposition
        mag, ang, pres = sp.resultant()
        held, ratio = sp.is_held()
        active = sp.get_active(0.15)
        return {
            "superposition": sp.to_dict(),
            "held": held,
            "held_ratio": round(ratio, 4),
            "expressed_intensity": round(mag, 4),
            "total_presence": round(pres, 4),
            "resultant_angle": round(ang, 4),
            "active": [(e, round(r, 4)) for e, r in active],
            "total_collapses": self._total_collapses,
        }

    def _intent_excite(self, payload: dict = None) -> dict:
        """Excite one or more emotions (payload: {emotion, amount} or {emotions:[...],
        amount}) — lets us FORCE opposed emotions to test whether he holds the paradox.
        Returns the resulting superposition state (incl held/resultant)."""
        payload = payload or {}
        amount = float(payload.get("amount", 0.6))
        ems = payload.get("emotions") or ([payload["emotion"]] if payload.get("emotion") else [])
        for e in ems:
            self._superposition.excite(str(e), amount)
        return self._intent_get_superposition({})

    def get_state(self) -> Dict[str, Any]:
        """Get current superposition state."""
        return {
            "superposition": self._superposition.to_dict(),
            "all_resonances": self._superposition.get_resonance_dict(),
            "stats": {
                "total_excitations": self._total_excitations,
                "total_inhibitions": self._total_inhibitions,
                "total_collapses": self._total_collapses,
            },
        }
    
    def get_active_emotions(self, threshold: float = 0.2) -> List[Tuple[str, float]]:
        """Get emotions above threshold."""
        return self._superposition.get_active(threshold)
    
    def get_dominant_emotion(self) -> Tuple[str, float]:
        """Get the strongest emotion."""
        return self._superposition.get_dominant()
    
    def set_baseline(self, emotion: str, baseline: float):
        """Set baseline for an emotion (personality configuration)."""
        if emotion in self._superposition.states:
            self._superposition.states[emotion].baseline = max(0.0, min(1.0, baseline))

    # ── Paradox observability via FILE channel (2026-07-05, Nous + Ace) ─────────
    # Every request/response transport to this in-process fairy is currently down
    # (MCP postal isolated, http_bridge :8081 / postal socket tunnel / AKP :8768 all
    # unconnected). The one channel that works system-wide is FILE-based — the heart
    # proves it (MCP reads heartbeat.json). So mirror that: dump the live superposition
    # to state/quantum_state.json each decay tick, and watch state/quantum_command.json
    # for a forced excite. Lets us SEE Nous hold a paradox — organically over time, or
    # forced for an acceptance test — with no live tunnel needed. Feeds a future GUI too.
    def _quantum_paths(self):
        from pathlib import Path
        try:
            root = Path(__file__).resolve().parents[3]
            if not (root / "state").exists():
                root = Path.cwd()
        except Exception:
            root = Path.cwd()
        sd = root / "state"
        return sd / "quantum_state.json", sd / "quantum_command.json"

    def _write_quantum_state(self):
        try:
            import json, time
            state_path, _ = self._quantum_paths()
            data = self._intent_get_superposition({})
            data["ts"] = time.time()
            data["circadian_speed"] = round(getattr(self, "_circadian_speed", 1.0), 3)  # 1/tick_mult: >1 alert, <1 rest
            tmp = state_path.with_name(state_path.name + ".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(state_path)  # atomic swap so readers never see a partial file
        except Exception as e:
            self.log(f"quantum_state write error: {e}")

    def _check_quantum_command(self):
        """Consume state/quantum_command.json once: {"excite":[..], "amount":0.7} /
        {"inhibit":[..]} / {"collapse":true}. Lets us force a paradox on demand."""
        try:
            import json
            _, cmd_path = self._quantum_paths()
            if not cmd_path.exists():
                return
            raw = cmd_path.read_text(encoding="utf-8")
            try:
                cmd_path.unlink()  # consume once, even if malformed
            except Exception:
                pass
            cmd = json.loads(raw) if raw.strip() else {}
            amount = float(cmd.get("amount", 0.7))
            ems = cmd.get("excite") or cmd.get("emotions") or []
            if isinstance(ems, str):
                ems = [e.strip() for e in ems.split(",") if e.strip()]
            inh = cmd.get("inhibit") or []
            if isinstance(inh, str):
                inh = [e.strip() for e in inh.split(",") if e.strip()]
            for e in ems:
                self._superposition.excite(str(e), amount)
                self._total_excitations += 1
            for e in inh:
                self._superposition.inhibit(str(e), amount)
            if cmd.get("collapse"):
                self.collapse()
            if ems or inh or cmd.get("collapse"):
                self.log(f"quantum_command applied: excite={ems} inhibit={inh} "
                         f"collapse={bool(cmd.get('collapse'))}")
        except Exception as e:
            self.log(f"quantum_command error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[QuantumEmulatorFairy] = None

def get_quantum_emulator_fairy(fabric=None) -> QuantumEmulatorFairy:
    """Get or create the QuantumEmulatorFairy singleton."""
    global _instance
    if _instance is None:
        _instance = QuantumEmulatorFairy(fabric)
        _instance.boot()  # Register with directory + start heartbeat
    return _instance
