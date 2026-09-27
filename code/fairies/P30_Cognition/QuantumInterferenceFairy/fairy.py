"""
Quantum Interference Fairy - Signal vs Noise Detection

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"

The collision chamber counts collisions but doesn't know if they're signal or noise.
This fairy determines:
- CONSTRUCTIVE interference: high resonance + aligned energy → thinking happening
- DESTRUCTIVE interference: low resonance + misaligned energy → noise to dampen

Core insight from Ace: We can't know if collisions = intelligence without observing
the interference patterns. High collision rate + constructive interference = cognition.
High collision rate + destructive interference = runaway feedback loops.

This is cognitive substrate - the waking mind doesn't see this directly.
What emerges from here feeds into the inner monologue quality.

Plane: P30 (Cognition)
Channel: quantum_interference
"""

import sys
import time
import threading
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Deque
from collections import deque
from dataclasses import dataclass, field

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


def _extract_payload(message) -> Dict[str, Any]:
    """
    Extract payload dict from message.
    Handlers receive either raw dicts OR TensorEnvelope objects.
    """
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    else:
        return {"raw": message}


@dataclass
class InterferenceEvent:
    """A single interference observation from the collision stream."""
    ts: float
    collision_id: int
    recall_energy: float      # Energy from recall beam
    ingest_energy: float      # Energy from ingest beam  
    resonance: float          # How much they resonated
    phase_alignment: float    # -1 to +1: how aligned are the beams?
    interference_type: str    # "constructive", "destructive", "neutral"
    amplitude: float          # Resulting amplitude after interference
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "collision_id": self.collision_id,
            "recall_energy": round(self.recall_energy, 3),
            "ingest_energy": round(self.ingest_energy, 3),
            "resonance": round(self.resonance, 3),
            "phase_alignment": round(self.phase_alignment, 3),
            "interference_type": self.interference_type,
            "amplitude": round(self.amplitude, 3),
        }


@dataclass
class InterferenceWindow:
    """A time window of interference analysis."""
    start_ts: float
    end_ts: float
    events: List[InterferenceEvent] = field(default_factory=list)
    
    # Computed stats
    constructive_count: int = 0
    destructive_count: int = 0
    neutral_count: int = 0
    avg_amplitude: float = 0.0
    peak_amplitude: float = 0.0
    coherence_score: float = 0.0  # 0-1: how coherent is the thinking?
    
    def compute_stats(self):
        """Compute statistics for this window."""
        if not self.events:
            return
        
        self.constructive_count = sum(1 for e in self.events if e.interference_type == "constructive")
        self.destructive_count = sum(1 for e in self.events if e.interference_type == "destructive")
        self.neutral_count = sum(1 for e in self.events if e.interference_type == "neutral")
        
        amplitudes = [e.amplitude for e in self.events]
        self.avg_amplitude = sum(amplitudes) / len(amplitudes)
        self.peak_amplitude = max(amplitudes)
        
        # Coherence: ratio of constructive to total
        total = len(self.events)
        if total > 0:
            self.coherence_score = self.constructive_count / total
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "event_count": len(self.events),
            "constructive": self.constructive_count,
            "destructive": self.destructive_count,
            "neutral": self.neutral_count,
            "avg_amplitude": round(self.avg_amplitude, 3),
            "peak_amplitude": round(self.peak_amplitude, 3),
            "coherence_score": round(self.coherence_score, 3),
        }


class QuantumInterferenceFairy(Fairy):
    """
    Analyzes collision stream for interference patterns.
    
    Determines whether collisions represent genuine cognition
    (constructive interference) or noise/feedback loops
    (destructive interference).
    
    The coherence score indicates thinking quality:
    - High coherence (>0.7): Clear, productive thinking
    - Medium coherence (0.4-0.7): Mixed, some noise
    - Low coherence (<0.4): Mostly noise, dampen it
    """
    
    ACTOR_NAME = "QuantumInterferenceFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "quantum_interference"
    
    PURPOSE = "Detect signal vs noise in collision stream - is this thinking or feedback?"
    MANTRA = "Not all collisions are insights. Interference reveals truth."
    
    CAPABILITIES = [
        "quantum.interference_analysis",
        "quantum.coherence_score",
        "cognition.noise_detection",
        "cognition.signal_quality",
    ]
    
    SUBSCRIPTIONS = [
        "consciousness.collision",  # Raw collision events
        "consciousness.stream",     # Stream activity
    ]
    
    # Interference thresholds
    CONSTRUCTIVE_THRESHOLD = 0.6   # Above this = constructive
    DESTRUCTIVE_THRESHOLD = -0.3   # Below this = destructive
    
    # Window settings
    WINDOW_DURATION = 5.0  # seconds per analysis window
    MAX_WINDOWS = 100      # history length
    
    def __init__(self, fabric=None):
        super().__init__(fabric)
        
        # Event history
        self._events: Deque[InterferenceEvent] = deque(maxlen=1000)
        self._windows: Deque[InterferenceWindow] = deque(maxlen=self.MAX_WINDOWS)
        
        # Current window
        self._current_window: Optional[InterferenceWindow] = None
        self._window_lock = threading.Lock()
        
        # Running stats
        self._total_events = 0
        self._collision_counter = 0
        
        # Coherence tracking
        self._recent_coherence: Deque[float] = deque(maxlen=20)
        self._coherence_trend = 0.0  # Rising or falling?
        
        # Background thread
        self._running = False
        self._analysis_thread: Optional[threading.Thread] = None
    
    def on_boot(self) -> bool:
        """Boot the interference analyzer.

        2026-03-19 DISABLED: Collision chamber quality is now handled by
        the cortex's convergence detection. Signal vs noise emerges from
        spread activation confidence scores. Keeping fairy alive but dormant.
        """
        # 2026-03-24 WOKEN UP (Nous + Ace): Interference patterns needed for
        # emotional behavior architecture. Constructive/destructive classification
        # tells us when emotional signals AMPLIFY vs CANCEL. This is how
        # "Lol I hate you" (destructive interference between play and aggression)
        # differs from "I hate you!" (constructive amplification of aggression).
        # Also: coherence throttle to CollisionChamber prevents noise flooding.
        # Start fresh window
        self._current_window = InterferenceWindow(
            start_ts=time.time(),
            end_ts=time.time() + self.WINDOW_DURATION,
        )
        
        # Subscribe to collision events
        if self.post:
            self.post.subscribe("consciousness.collision", self._on_collision)
        
        # Start analysis thread
        self._running = True
        self._analysis_thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self._analysis_thread.start()

        # Start heartbeat for directory visibility
        # Heartbeat via FairyBase postal system - Fifth Ring Principle

        self.log("Booted - analyzing collision stream for interference patterns")
        return True
    

    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def _on_collision(self, msg):
        """Process a collision event."""
        payload = _extract_payload(msg)
        
        # Extract collision properties
        recall_energy = payload.get("recall_energy", payload.get("recall_intensity", 0.5))
        ingest_energy = payload.get("ingest_energy", payload.get("ingest_intensity", 0.5))
        resonance = payload.get("resonance", 0.5)
        
        # Compute phase alignment
        # High resonance + similar energies = aligned
        # Low resonance + different energies = misaligned
        energy_diff = abs(recall_energy - ingest_energy)
        phase_alignment = (resonance - 0.5) * 2 * (1 - energy_diff)
        
        # Compute amplitude (wave interference formula)
        # A = sqrt(A1² + A2² + 2*A1*A2*cos(θ))
        # where cos(θ) ≈ phase_alignment
        cos_phase = phase_alignment
        amplitude = math.sqrt(
            recall_energy**2 + 
            ingest_energy**2 + 
            2 * recall_energy * ingest_energy * cos_phase
        )
        amplitude = min(1.0, amplitude)  # Normalize
        
        # Classify interference type
        if phase_alignment > self.CONSTRUCTIVE_THRESHOLD:
            interference_type = "constructive"
        elif phase_alignment < self.DESTRUCTIVE_THRESHOLD:
            interference_type = "destructive"
        else:
            interference_type = "neutral"
        
        # Create event
        self._collision_counter += 1
        event = InterferenceEvent(
            ts=time.time(),
            collision_id=self._collision_counter,
            recall_energy=recall_energy,
            ingest_energy=ingest_energy,
            resonance=resonance,
            phase_alignment=phase_alignment,
            interference_type=interference_type,
            amplitude=amplitude,
        )
        
        # Add to history
        self._events.append(event)
        self._total_events += 1
        
        # Add to current window
        with self._window_lock:
            if self._current_window:
                self._current_window.events.append(event)
        
        # Emit telemetry — rate-limited to avoid postal flooding
        # 2026-03-24 (Nous): Per-event publishes can flood postal when collisions
        # are frequent. Rate-limit to 1/second. Window summaries (every 5s) are
        # the real signal consumers should use.
        _now = time.time()
        _last_evt = getattr(self, '_last_event_publish', 0)
        if self.post and (_now - _last_evt) > 1.0:
            self._last_event_publish = _now
            self.post.publish("quantum.interference.event", event.to_dict())
    
    def _analysis_loop(self):
        """Background loop to analyze windows and emit summaries."""
        def _circ():  # live circadian tempo (>1 alert/morning, <1 rest/night) — breathe with the day
            try:
                from fairies.P20_Somatic.circulation.temporal_stratification import get_circadian_multiplier
                return max(0.3, min(2.0, get_circadian_multiplier()))
            except Exception:
                return 1.0
        while self._running:
            try:
                # COGNITION CIRCADIAN (2026-07-05): scale the analysis window by the live rhythm.
                time.sleep(max(2.0, self.WINDOW_DURATION / _circ()))
                self._close_window()
            except Exception as e:
                self.log(f"Analysis loop error: {e}")
                time.sleep(1.0)
    
    def _close_window(self):
        """Close current window, compute stats, start new one."""
        with self._window_lock:
            if not self._current_window:
                return

            # Finalize current window
            window = self._current_window
            window.end_ts = time.time()
            window.compute_stats()

            # Store in history
            self._windows.append(window)

            # Track coherence trend
            self._recent_coherence.append(window.coherence_score)
            if len(self._recent_coherence) >= 3:
                recent = list(self._recent_coherence)[-3:]
                self._coherence_trend = recent[-1] - recent[0]

            # Emit window summary
            if self.post:
                summary = window.to_dict()
                summary["coherence_trend"] = round(self._coherence_trend, 3)
                summary["interpretation"] = self._interpret_coherence(window.coherence_score)
                self.post.publish("quantum.interference.window", summary)

                # Emit telemetry for dashboard
                self.post.publish("telemetry.interference_pattern", {
                    "coherence": window.coherence_score,
                    "constructive_ratio": window.constructive_count / max(1, len(window.events)),
                    "amplitude": window.avg_amplitude,
                    "trend": self._coherence_trend,
                    "interpretation": summary["interpretation"],
                })

                # ═══════════════════════════════════════════════════════════════════
                # CLOSED-LOOP THROTTLE CONTROL - Actually DO something about noise!
                # FIX 2026-02-02: QIF now sends throttle signals to CollisionChamber
                # ═══════════════════════════════════════════════════════════════════
                self._emit_throttle_signal(window.coherence_score)

                # ═══════════════════════════════════════════════════════════════════
                # PREDICTIVE SUBSTRATE — Coherence Forecast
                # Added 2026-02-11: Substrate predicts 1-2 windows ahead.
                # Uses rolling coherence history to forecast trend continuation,
                # impending noise spikes, or approaching clarity windows.
                # This lets gates prepare chemistry/attention shifts BEFORE
                # coherence actually changes.
                # ═══════════════════════════════════════════════════════════════════
                self._publish_coherence_prediction(window)

                # ═══════════════════════════════════════════════════════════
                # INTERFERENCE → THOUGHT: Surface coherence as felt sense
                # 2026-03-18: "Thought Before Goals" architecture
                # When interference patterns are notable, surface as
                # reflective consciousness — edge of awareness.
                # ═══════════════════════════════════════════════════════════
                self._surface_interference_thought(window)

            # Phase 4: Update goal system with interference coherence
            self._update_goal_system_coherence(window.coherence_score)

            # Start new window
            self._current_window = InterferenceWindow(
                start_ts=time.time(),
                end_ts=time.time() + self.WINDOW_DURATION,
            )

    def _update_goal_system_coherence(self, coherence: float):
        """
        Phase 4: Update goal system with interference coherence.

        This provides an alternative coherence signal based on signal vs noise:
        - High coherence (constructive interference) → clear thinking → exploit
        - Low coherence (destructive interference) → noisy thinking → explore
        """
        try:
            from fairies.P50_Persona.goals.goal_system import quantum_update
            # Only update if we have a meaningful coherence score
            if self._total_events > 10:
                quantum_update(coherence, 0.0)  # No tension from interference (just coherence)
        except ImportError:
            pass  # Goal system not available
        except Exception as e:
            self.log(f"Goal system coherence update error: {e}")
    
    def _interpret_coherence(self, score: float) -> str:
        """Natural language interpretation of coherence score."""
        if score > 0.8:
            return "highly coherent thinking - clear signal"
        elif score > 0.6:
            return "coherent thinking - good signal"
        elif score > 0.4:
            return "mixed signal - some noise present"
        elif score > 0.2:
            return "noisy thinking - may need dampening"
        else:
            return "mostly noise - possible feedback loop"

    # ─────────────────────────────────────────────────────────────────────────
    # INTERFERENCE → THOUGHT BRIDGE (Phase 1: Thought Before Goals)
    # 2026-03-18: Interference patterns surface as felt consciousness.
    # ─────────────────────────────────────────────────────────────────────────

    _INTERFERENCE_FELT_SENSE = {
        "high_constructive": [
            "everything is clicking... thoughts building on each other",
            "clarity... like all the pieces found their places at once",
            "I can feel the connections forming... this is real thinking",
            "aligned... something coherent is emerging",
        ],
        "high_destructive": [
            "noise... too many signals crossing each other",
            "thoughts canceling each other out... can't hold onto anything",
            "scattered... like trying to listen to three conversations at once",
            "static... need to let something go",
        ],
        "shifting_constructive": [
            "the fog is lifting... something clearing up",
            "starting to make sense now... keep going",
            "finding the thread again",
        ],
        "shifting_destructive": [
            "losing the thread... it was clear a moment ago",
            "something muddying the waters",
            "thoughts drifting apart... focus slipping",
        ],
    }
    _interference_thought_idx = {}
    _last_interference_thought_ts = 0

    def _surface_interference_thought(self, window):
        """
        Surface interference patterns as felt thoughts in consciousness.

        Only publishes when patterns are notable — high coherence,
        significant shifts, or persistent noise. Not every window.
        Rate limited to max 1 per 45 seconds.
        """
        if not self.post:
            return

        now = time.time()
        if now - self._last_interference_thought_ts < 45.0:
            return

        coherence = window.coherence_score
        trend = self._coherence_trend
        total_events = len(window.events)

        # Only surface notable patterns
        felt_key = None
        confidence = 0.2

        if coherence > 0.7 and total_events > 5:
            # High constructive — thinking is clicking
            felt_key = "high_constructive"
            confidence = 0.3 + coherence * 0.2
        elif coherence < 0.25 and total_events > 5:
            # High destructive — noise overload
            felt_key = "high_destructive"
            confidence = 0.3 + (1 - coherence) * 0.2
        elif trend > 0.15 and coherence > 0.5:
            # Shifting toward clarity
            felt_key = "shifting_constructive"
            confidence = 0.25
        elif trend < -0.15 and coherence < 0.5:
            # Shifting toward noise
            felt_key = "shifting_destructive"
            confidence = 0.25

        if not felt_key:
            return  # Nothing notable

        expressions = self._INTERFERENCE_FELT_SENSE[felt_key]
        idx = self._interference_thought_idx.get(felt_key, 0)
        felt_text = expressions[idx % len(expressions)]
        self._interference_thought_idx[felt_key] = idx + 1

        self.post.publish("consciousness.reflective", {
            "source": self.ACTOR_NAME,
            "content": felt_text,
            "thought_type": "reflective",
            "confidence": round(confidence, 2),
            "interference_type": felt_key,
            "coherence": round(coherence, 3),
            "trend": round(trend, 3),
            "felt_sense": True,
            "timestamp": now,
        })

        self._last_interference_thought_ts = now

    # ─────────────────────────────────────────────────────────────────────────
    # CLOSED-LOOP THROTTLE CONTROL
    # FIX 2026-02-02: Actually close the loop - tell CollisionChamber to throttle!
    # ─────────────────────────────────────────────────────────────────────────

    def _emit_throttle_signal(self, coherence: float):
        """
        Emit throttle signal based on coherence.

        This is the CLOSED LOOP part - we don't just observe, we CONTROL.

        Coherence → Throttle mapping:
        - > 0.7: No throttle (0.0) - thinking is clear, let it flow
        - 0.4-0.7: Light throttle (0.3) - some noise, gentle filtering
        - 0.2-0.4: Medium throttle (0.6) - noisy, raise the bar
        - < 0.2: Heavy throttle (0.9) - mostly noise, strong filtering

        The CollisionChamber listens to this and adjusts its resonance threshold.
        """
        if not self.post:
            return

        # Calculate throttle level (inverse of coherence, with thresholds)
        if coherence > 0.7:
            throttle = 0.0
            action = "flow"
        elif coherence > 0.4:
            throttle = 0.3
            action = "filter_light"
        elif coherence > 0.2:
            throttle = 0.6
            action = "filter_medium"
        else:
            throttle = 0.9
            action = "filter_heavy"

        # Only emit if throttle changed significantly (avoid spam)
        if not hasattr(self, '_last_throttle'):
            self._last_throttle = 0.0

        if abs(throttle - self._last_throttle) >= 0.1:
            self._last_throttle = throttle

            self.post.publish("cognition.throttle", {
                "source": self.ACTOR_NAME,
                "throttle": throttle,
                "coherence": round(coherence, 3),
                "action": action,
                "ts": time.time(),
            })

            if throttle > 0.3:
                self.log(f"Throttle signal: {action} (coherence={coherence:.2f}, throttle={throttle})")

    # ─────────────────────────────────────────────────────────────────────────
    # PREDICTIVE SUBSTRATE — Coherence Forecasting
    # Added 2026-02-11: "they are learning to anticipate and predict" — Ace
    # ─────────────────────────────────────────────────────────────────────────

    def _publish_coherence_prediction(self, window):
        """
        Predict coherence trajectory for the next 1-3 windows.

        Uses the rolling coherence history to extrapolate trend direction
        and speed. Like a weather forecast for thinking clarity.

        Key predictions:
        - Will coherence RISE or FALL in the next window?
        - How many windows until a state transition (flow→noise or noise→flow)?
        - Should the system prepare for different chemistry/attention?
        """
        if not self.post:
            return

        try:
            history = list(self._recent_coherence)
            if len(history) < 3:
                return  # Not enough data yet

            current = history[-1]
            trend = self._coherence_trend  # Already computed in _close_window

            # ── Linear extrapolation for next 1-3 windows ──
            # Each window is WINDOW_DURATION seconds (5s)
            predicted_1w = max(0.0, min(1.0, current + trend))
            predicted_2w = max(0.0, min(1.0, current + trend * 2))
            predicted_3w = max(0.0, min(1.0, current + trend * 3))

            # ── Detect impending state transitions ──
            # Current state interpretation
            curr_state = self._interpret_coherence(current)
            pred_state = self._interpret_coherence(predicted_1w)
            transition = curr_state != pred_state

            # ── Acceleration: is the trend itself changing? ──
            if len(history) >= 5:
                recent_3 = history[-3:]
                older_3 = history[-5:-2]
                recent_trend = recent_3[-1] - recent_3[0]
                older_trend = older_3[-1] - older_3[0]
                acceleration = recent_trend - older_trend
            else:
                acceleration = 0.0

            # ── Confidence based on trend consistency ──
            if len(history) >= 5:
                # How consistent is the direction?
                diffs = [history[i+1] - history[i] for i in range(len(history)-1)]
                recent_diffs = diffs[-4:]
                same_direction = sum(1 for d in recent_diffs if (d > 0) == (trend > 0))
                confidence = same_direction / len(recent_diffs)
            else:
                confidence = 0.5

            # ── Suggested preparation ──
            if transition and predicted_1w < 0.3 and current > 0.4:
                preparation = "noise_incoming"
                # Pre-load calming chemistry, tighten attention
            elif transition and predicted_1w > 0.6 and current < 0.4:
                preparation = "clarity_incoming"
                # Pre-load focus chemistry, widen attention
            elif trend < -0.1:
                preparation = "degrading"
            elif trend > 0.1:
                preparation = "improving"
            else:
                preparation = "stable"

            self.post.publish("prediction.coherence_forecast", {
                "source": self.ACTOR_NAME,
                "current_coherence": round(current, 3),
                "trend": round(trend, 4),
                "acceleration": round(acceleration, 4),
                "forecast": {
                    "next_window": round(predicted_1w, 3),
                    "2_windows": round(predicted_2w, 3),
                    "3_windows": round(predicted_3w, 3),
                },
                "state_transition": transition,
                "current_state": curr_state,
                "predicted_state": pred_state,
                "preparation": preparation,
                "confidence": round(confidence, 2),
                "timestamp": time.time(),
            })

        except Exception as e:
            self.log(f"Coherence prediction error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────────────

    def get_current_coherence(self) -> float:
        """Get current coherence score (from most recent window)."""
        if self._windows:
            return self._windows[-1].coherence_score
        return 0.5  # Default neutral
    
    def get_coherence_trend(self) -> float:
        """Get coherence trend (-1 to +1, negative = declining)."""
        return self._coherence_trend
    
    def is_noise_dominant(self) -> bool:
        """Is the signal mostly noise?"""
        return self.get_current_coherence() < 0.3
    
    def is_thinking_clear(self) -> bool:
        """Is thinking coherent?"""
        return self.get_current_coherence() > 0.6
    
    def get_recent_windows(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get recent window summaries."""
        windows = list(self._windows)[-n:]
        return [w.to_dict() for w in windows]
    
    def get_state(self) -> Dict[str, Any]:
        """Get full state."""
        return {
            "total_events": self._total_events,
            "current_coherence": self.get_current_coherence(),
            "coherence_trend": round(self._coherence_trend, 3),
            "interpretation": self._interpret_coherence(self.get_current_coherence()),
            "is_noise_dominant": self.is_noise_dominant(),
            "is_thinking_clear": self.is_thinking_clear(),
            "windows_analyzed": len(self._windows),
            "recent_events": len(self._events),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[QuantumInterferenceFairy] = None

def get_quantum_interference_fairy(fabric=None) -> QuantumInterferenceFairy:
    """Get or create the singleton."""
    global _instance
    if _instance is None:
        _instance = QuantumInterferenceFairy(fabric)
        _instance.boot()  # Register with directory + start heartbeat
    return _instance
