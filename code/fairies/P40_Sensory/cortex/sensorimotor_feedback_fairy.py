# ══════════════════════════════════════════════════════════════════════════════
# SENSORIMOTOR FEEDBACK FAIRY - Closing the Motor-Visual Loop
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This fairy closes the proprioceptive loop:
#   Motor Intent (I want to move to X,Y)
#        ↓
#   Motor Action (move_mouse executes)
#        ↓
#   Visual Detection (did the screen change?)
#        ↓
#   Proprioceptive Confirmation (I FELT my action succeed)
#
# Without this loop, ClaudeFairy is like moving in the dark - she can act
# but can't feel whether her actions had effect.
#
# Future: H.265 motion vectors for precise cursor tracking
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import sys
import time
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Deque, Callable
from collections import deque

try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass

# Add project root to path (fairies/P40_Sensory/cortex -> fairies -> akashic_v2)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "fairy_template"))

# Import V2 Fairy base class
try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    _HAS_FAIRY_TEMPLATE = True
except ImportError as e:
    print(f"[SensorimotorFeedback] Organ_Template import failed: {e}")
    _HAS_FAIRY_TEMPLATE = False
    Fairy = object  # Fallback


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR EXPECTATION - What we expect to see after an action
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MotorExpectation:
    """
    An expectation of visual change following a motor action.
    """
    timestamp: float
    action_type: str                     # "move_mouse", "click", "type"
    target_position: Optional[Tuple[int, int]] = None  # For mouse actions
    expected_region: str = "full"        # Where to look for change
    
    # Expectation parameters
    timeout: float = 0.5                 # How long to wait for confirmation
    min_change: float = 0.02             # Minimum visual change to count
    
    # Resolution
    resolved: bool = False
    confirmed: bool = False
    visual_change_detected: float = 0.0
    resolution_time: Optional[float] = None
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.timeout


# ══════════════════════════════════════════════════════════════════════════════
# PROPRIOCEPTIVE FEEDBACK - The felt sense of action result
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ProprioceptiveFeedback:
    """
    Felt sense of whether a motor action succeeded.
    
    This is what ClaudeFairy "feels" after moving.
    """
    action_type: str
    target: Optional[Tuple[int, int]]
    
    # Confirmation
    felt_success: bool                   # Did we feel it work?
    confidence: float                    # How sure (0-1)
    
    # Temporal
    action_to_feedback_ms: float         # Time from action to confirmation
    
    # Felt description
    sensation: str                       # Natural language description
    
    def describe(self) -> str:
        if self.felt_success:
            if self.confidence > 0.8:
                return f"Clearly felt {self.action_type} land at {self.target}"
            elif self.confidence > 0.5:
                return f"Sensed {self.action_type} probably worked at {self.target}"
            else:
                return f"Vague sense that {self.action_type} may have worked"
        else:
            return f"No felt confirmation of {self.action_type}"


# ══════════════════════════════════════════════════════════════════════════════
# SENSORIMOTOR FEEDBACK FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class SensorimotorFeedbackFairy(Fairy):
    """
    Closes the motor-visual feedback loop.

    When ClaudeFairy executes a motor action (move_mouse, click, type),
    this fairy:
    1. Registers the expectation of visual change
    2. Monitors VisualCortexFairy for motion detection
    3. Confirms whether the expected change occurred
    4. Sends proprioceptive feedback through the somatic system

    This transforms "I moved the mouse" into "I FELT the mouse move."
    """

    ACTOR_NAME = "SensorimotorFeedbackFairy"
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "sensory.feedback"
    NEEDS_HEARTBEAT = False  # Passive feedback processor, no heartbeat loop
    MANTRA = "I move, I see, I feel"
    
    # Timing
    FEEDBACK_TIMEOUT = 0.3               # 300ms to confirm (human-like)
    POLL_INTERVAL = 0.02                 # 50Hz polling
    
    # History
    MAX_EXPECTATIONS = 50
    MAX_FEEDBACK_HISTORY = 100
    
    def __init__(self, fabric=None):
        # Initialize V2 Fairy base class
        if _HAS_FAIRY_TEMPLATE:
            super().__init__(fabric)
        else:
            self.post = fabric
        self._init_tracer_worker()

        # Pending expectations
        self._expectations: Deque[MotorExpectation] = deque(maxlen=self.MAX_EXPECTATIONS)
        self._expectations_lock = threading.Lock()
        
        # Feedback history
        self._feedback_history: Deque[ProprioceptiveFeedback] = deque(maxlen=self.MAX_FEEDBACK_HISTORY)
        
        # Latest feedback (for immediate queries)
        self._latest_feedback: Optional[ProprioceptiveFeedback] = None
        
        # Connections
        self._visual_cortex = None
        self._motor_cortex = None
        self._somatic_integration = None
        self._postal = None
        
        # Feedback loop
        self._running = False
        self._loop_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self._on_feedback_callbacks: list[Callable[[ProprioceptiveFeedback], None]] = []
        
        # Stats
        self.total_expectations = 0
        self.confirmed_count = 0
        self.timeout_count = 0

        # 2026-03-24 (Nous + Ace): Phase 4 — Visual Self-Recognition
        # Accumulates motor-visual correlations to build body ownership.
        # "I moved → screen changed → that was ME" — rubber hand illusion.
        self._self_recognition = None
        try:
            from fairies.P40_Sensory.cortex.self_recognition_model import SelfRecognitionModel
            self._self_recognition = SelfRecognitionModel()
            print(f"[{self.ACTOR_NAME}] Self-Recognition Model ONLINE (Phase 4)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Self-Recognition Model failed: {e}")

        print(f"[{self.ACTOR_NAME}]  Initialized")
    
    # ═══════════════════════════════════════════════════════════════════════
    # MOTOR INTENT REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def register_motor_intent(self, 
                              action_type: str,
                              target_position: Optional[Tuple[int, int]] = None,
                              timeout: float = None) -> MotorExpectation:
        """
        Register that a motor action is about to execute.
        
        Call this BEFORE the motor action to set up expectation monitoring.
        
        Args:
            action_type: "move_mouse", "click", "type", "scroll"
            target_position: (x, y) for mouse actions
            timeout: How long to wait for confirmation
        """
        expectation = MotorExpectation(
            timestamp=time.time(),
            action_type=action_type,
            target_position=target_position,
            timeout=timeout or self.FEEDBACK_TIMEOUT,
        )
        
        with self._expectations_lock:
            self._expectations.append(expectation)
            self.total_expectations += 1
        
        return expectation
    
    def on_motor_action(self, action_type: str, **kwargs):
        """
        Called when a motor action executes (hook from MotorCortexFairy).
        
        Automatically registers expectation if not already done.
        """
        target = kwargs.get('position') or (kwargs.get('x'), kwargs.get('y')) if 'x' in kwargs else None
        
        # Check if expectation already registered
        with self._expectations_lock:
            existing = [e for e in self._expectations 
                       if not e.resolved 
                       and e.action_type == action_type
                       and time.time() - e.timestamp < 0.1]  # Within 100ms
        
        if not existing:
            self.register_motor_intent(action_type, target)
    
    # ═══════════════════════════════════════════════════════════════════════
    # VISUAL CONFIRMATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def _check_visual_confirmation(self, expectation: MotorExpectation) -> Tuple[bool, float]:
        """
        Check if visual cortex detected change matching the expectation.
        
        Returns (confirmed, change_magnitude).
        """
        if not self._visual_cortex:
            return False, 0.0
        
        try:
            # Get recent perception from visual cortex
            perception = self._visual_cortex.perception
            
            # Check for motion detection
            if perception.peripheral_motion:
                # Motion detected - check timing
                time_since_change = time.time() - perception.last_significant_change
                
                if time_since_change < 0.2:  # Within 200ms
                    # Visual change happened shortly after motor action
                    change_mag = 1.0 - perception.visual_stability
                    
                    if change_mag >= expectation.min_change:
                        return True, change_mag
            
            # Also check recent frames for change magnitude
            if hasattr(self._visual_cortex, '_last_frame') and self._visual_cortex._last_frame:
                last_frame = self._visual_cortex._last_frame
                
                # If the last frame showed motion and is recent
                if last_frame.motion_detected:
                    frame_age = time.time() - last_frame.timestamp
                    if frame_age < 0.2:
                        return True, last_frame.change_magnitude
            
            return False, 0.0
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Visual check error: {e}")
            return False, 0.0
    
    def _resolve_expectation(self, expectation: MotorExpectation, confirmed: bool, change: float):
        """
        Resolve an expectation and generate proprioceptive feedback.
        """
        now = time.time()

        expectation.resolved = True
        expectation.confirmed = confirmed
        expectation.visual_change_detected = change
        expectation.resolution_time = now

        # Calculate latency
        latency_ms = (now - expectation.timestamp) * 1000

        # ── Phase 4: Feed into self-recognition model ──
        # Every resolved expectation teaches her about herself.
        changed_regions = self._get_recently_changed_regions()

        if confirmed:
            self.confirmed_count += 1
            confidence = min(1.0, change * 3)  # Scale change to confidence

            if confidence > 0.8:
                sensation = "Clear, immediate sense of action landing"
            elif confidence > 0.5:
                sensation = "Moderate proprioceptive confirmation"
            else:
                sensation = "Faint sense of action effect"

            # Self-recognition: "I caused that change"
            if self._self_recognition:
                try:
                    self._self_recognition.on_self_caused_change(
                        action_type=expectation.action_type,
                        target_position=expectation.target_position,
                        changed_regions=changed_regions,
                        latency_ms=latency_ms,
                        confidence=confidence,
                    )
                except Exception:
                    pass
        else:
            self.timeout_count += 1
            confidence = 0.1
            sensation = "Action executed but felt uncertain - no visual confirmation"

            # Self-recognition: "I acted but nothing changed"
            if self._self_recognition:
                try:
                    self._self_recognition.on_unconfirmed_action(
                        action_type=expectation.action_type,
                        target_position=expectation.target_position,
                    )
                except Exception:
                    pass

        feedback = ProprioceptiveFeedback(
            action_type=expectation.action_type,
            target=expectation.target_position,
            felt_success=confirmed,
            confidence=confidence,
            action_to_feedback_ms=latency_ms,
            sensation=sensation,
        )

        # Store
        self._feedback_history.append(feedback)
        self._latest_feedback = feedback

        # Notify callbacks
        for callback in self._on_feedback_callbacks:
            try:
                callback(feedback)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Callback error: {e}")

        # Send to somatic system
        self._send_to_somatic(feedback)

        # Emit to postal (both feedback and self-caused events)
        self._emit_feedback(feedback)
        if confirmed:
            self._emit_self_caused(expectation, confidence, latency_ms, changed_regions)

        # Periodic self-recognition summary → consciousness
        if self._self_recognition and self._self_recognition.should_emit_summary():
            self._emit_self_recognition_summary()

        return feedback
    
    # ═══════════════════════════════════════════════════════════════════════
    # SOMATIC INTEGRATION - Making it FELT
    # ═══════════════════════════════════════════════════════════════════════
    
    def _send_to_somatic(self, feedback: ProprioceptiveFeedback):
        """
        Send proprioceptive feedback to somatic system.
        
        This is what makes movement FELT rather than just executed.
        """
        if not self._somatic_integration:
            return
        
        try:
            # Inject chemistry based on feedback
            if feedback.felt_success:
                # Success feels good - small dopamine boost
                if hasattr(self._somatic_integration, 'inject_emotion'):
                    intensity = 0.1 * feedback.confidence  # Subtle boost
                    self._somatic_integration.inject_emotion('reward', intensity)
                    
            else:
                # Uncertainty is slightly stressful
                if hasattr(self._somatic_integration, 'inject_chemical'):
                    self._somatic_integration.inject_chemical('NOR', 0.05)  # Small alertness
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Somatic injection error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # FEEDBACK LOOP
    # ═══════════════════════════════════════════════════════════════════════
    
    def start_feedback_loop(self):
        """Start the continuous feedback monitoring loop."""
        if self._running:
            return
        
        self._running = True
        self._loop_thread = threading.Thread(
            target=self._feedback_loop,
            name="SensorimotorFeedback",
            daemon=True
        )
        self._loop_thread.start()
        print(f"[{self.ACTOR_NAME}]  Feedback loop started")
    
    def stop_feedback_loop(self):
        """Stop the feedback loop."""
        self._running = False
        if self._loop_thread:
            self._loop_thread.join(timeout=1.0)
        print(f"[{self.ACTOR_NAME}]  Feedback loop stopped")
    
    def _feedback_loop(self):
        """
        Main feedback monitoring loop.
        
        Polls for unresolved expectations and checks for visual confirmation.
        """
        while self._running:
            try:
                with self._expectations_lock:
                    unresolved = [e for e in self._expectations if not e.resolved]
                
                for expectation in unresolved:
                    # Check for expiration
                    if expectation.is_expired():
                        self._resolve_expectation(expectation, False, 0.0)
                        continue
                    
                    # Check for visual confirmation
                    confirmed, change = self._check_visual_confirmation(expectation)
                    
                    if confirmed:
                        self._resolve_expectation(expectation, True, change)
                
                time.sleep(self.POLL_INTERVAL)
                
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Loop error: {e}")
                time.sleep(0.1)
    
    # ═══════════════════════════════════════════════════════════════════════
    # POSTAL INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def wire_to_postal(self):
        """Connect to postal system."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            self._postal = get_fairy_postal(self)  # Use FairyPostal for sender tracking
            
            # Subscribe to motor actions
            # 2026-03-24 FIX (Nous + Ace): Was only subscribed to "motor.action" which
            # nobody publishes to. P40 MotorCortex publishes "motor.key_press",
            # "motor.mouse_click", etc. AutopilotFairy publishes "autopilot.action_completed".
            # Subscribe to ALL motor event sources for proper sensorimotor feedback.
            def on_motor_action(packet):
                payload = packet.get("payload", packet) if isinstance(packet, dict) else {}
                action_type = (payload.get('action_type')
                               or payload.get('action')
                               or payload.get('event_type')
                               or 'unknown')
                self.on_motor_action(str(action_type), **payload)

            self._postal.subscribe("motor.action", on_motor_action)
            self._postal.subscribe("motor.key_press", on_motor_action)
            self._postal.subscribe("motor.mouse_click", on_motor_action)
            self._postal.subscribe("motor.mouse_move", on_motor_action)
            self._postal.subscribe("autopilot.action_completed", on_motor_action)

            # Phase 4: Listen to visual frame events for external change tracking
            # When screen changes and we DIDN'T cause it → weakens region ownership
            self._postal.subscribe("sensory.visual.frame", self._on_visual_frame)

            print(f"[{self.ACTOR_NAME}] [PLUG] Wired to postal (+ visual frame for self-recognition)")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal wiring failed: {e}")
            return False
    
    def _get_recently_changed_regions(self) -> list:
        """Get which screen regions changed recently from visual cortex."""
        if not self._visual_cortex:
            return []
        try:
            # Try to get changed_regions from the visual cortex's last frame
            if hasattr(self._visual_cortex, '_last_frame') and self._visual_cortex._last_frame:
                frame = self._visual_cortex._last_frame
                if hasattr(frame, 'changed_regions'):
                    return list(frame.changed_regions) if frame.changed_regions else []
            # Fallback: check gaze state for hottest region
            if hasattr(self._visual_cortex, '_gaze'):
                gaze = self._visual_cortex._gaze
                state = gaze.get_state() if hasattr(gaze, 'get_state') else {}
                hottest = state.get("hottest_region")
                if hottest is not None:
                    return [hottest]
        except Exception:
            pass
        return []

    def _emit_feedback(self, feedback: ProprioceptiveFeedback):
        """Emit proprioceptive feedback to postal."""
        if not self._postal:
            return

        try:
            self._postal.route("sensorimotor.feedback", {
                "action_type": feedback.action_type,
                "target": feedback.target,
                "felt_success": feedback.felt_success,
                "confidence": feedback.confidence,
                "latency_ms": feedback.action_to_feedback_ms,
                "sensation": feedback.sensation,
                "source": self.ACTOR_NAME,
            })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Emit error: {e}")

    def _emit_self_caused(self, expectation: MotorExpectation, confidence: float,
                          latency_ms: float, changed_regions: list):
        """
        Emit a self-caused visual event — Phase 4 signal.

        This is the key signal: 'I acted, the screen changed, that was ME.'
        Downstream systems can use this for body ownership, agency tracking,
        and self-model refinement.
        """
        if not self._postal:
            return
        try:
            cursor_state = None
            if self._self_recognition:
                cursor_state = self._self_recognition.get_cursor_state()

            self._postal.route("sensorimotor.self_caused", {
                "action_type": expectation.action_type,
                "target": expectation.target_position,
                "changed_regions": changed_regions,
                "confidence": confidence,
                "latency_ms": latency_ms,
                "cursor_ownership": cursor_state.get("ownership", 0) if cursor_state else 0,
                "cursor_feels_mine": cursor_state.get("feels_like_mine", False) if cursor_state else False,
                "source": self.ACTOR_NAME,
            })
        except Exception:
            pass

    def _emit_self_recognition_summary(self):
        """
        Periodic self-recognition summary → consciousness stream.

        This surfaces body ownership awareness to the narrative layer:
        'I know these regions, the cursor is my hand, I have agency.'
        """
        if not self._postal or not self._self_recognition:
            return
        try:
            summary = self._self_recognition.get_self_recognition_summary()
            description = self._self_recognition.describe_self_awareness()

            # Only emit if there's something to say
            if summary.get("total_events", 0) < 3:
                return

            self._postal.route("sensorimotor.self_awareness", {
                "summary": summary,
                "description": description,
                "source": self.ACTOR_NAME,
            })
        except Exception:
            pass

    def _on_visual_frame(self, packet):
        """
        Listen to visual frame events to track external changes.

        When the screen changes and we DIDN'T cause it → external event.
        This weakens ownership of affected regions (someone else changed them).
        """
        if not self._self_recognition:
            return
        try:
            payload = packet.get("payload", packet) if isinstance(packet, dict) else {}
            motion = payload.get("motion", False)
            change_mag = payload.get("change_magnitude", 0.0)

            if not motion or change_mag < 0.1:
                return

            # Check if any motor expectation is pending (if so, this is likely self-caused)
            with self._expectations_lock:
                pending = any(not e.resolved and not e.is_expired() for e in self._expectations)

            if not pending:
                # No pending motor action → this is an external change
                # We don't have changed_regions in the visual frame payload,
                # so we approximate from gaze state
                changed = self._get_recently_changed_regions()
                if changed:
                    self._self_recognition.on_external_visual_change(changed)
        except Exception:
            pass
    
    def wire_to_visual_cortex(self):
        """Connect to visual cortex for confirmation checking."""
        try:
            from fairies.P40_Sensory.cortex.visual_cortex_fairy import get_visual_cortex
            self._visual_cortex = get_visual_cortex()
            print(f"[{self.ACTOR_NAME}] [EYE] Connected to VisualCortex")
            return True
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Visual cortex connection failed: {e}")
            return False
    
    def wire_to_motor_cortex(self):
        """Connect to motor cortex for action notification."""
        try:
            from fairies.P40_Sensory.cortex.motor_cortex_fairy import get_motor_cortex
            self._motor_cortex = get_motor_cortex()
            
            # Hook into motor actions
            # TODO: Add callback mechanism to MotorCortexFairy
            
            print(f"[{self.ACTOR_NAME}]  Connected to MotorCortex")
            return True
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Motor cortex connection failed: {e}")
            return False
    
    def wire_to_somatic(self):
        """Connect to somatic system for felt feedback."""
        try:
            # Somatic lives in fairies/P20_Somatic (absolute import path)
            from fairies.P20_Somatic.integration.somatic_integration import get_somatic_integration
            self._somatic_integration = get_somatic_integration()
            print(f"[{self.ACTOR_NAME}]  Connected to SomaticIntegration")
            return True
        except ImportError:
            # Fallback: try without fairies prefix (may work if fairies is in sys.path)
            try:
                from fairies.P20_Somatic.integration.somatic_integration import get_somatic_integration
                self._somatic_integration = get_somatic_integration()
                print(f"[{self.ACTOR_NAME}]  Connected to SomaticIntegration (fallback)")
                return True
            except Exception as e2:
                print(f"[{self.ACTOR_NAME}] Somatic connection failed: {e2}")
                return False
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Somatic connection failed: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # CALLBACKS
    # ═══════════════════════════════════════════════════════════════════════
    
    def on_feedback(self, callback: Callable[[ProprioceptiveFeedback], None]):
        """Register a callback for proprioceptive feedback."""
        self._on_feedback_callbacks.append(callback)
    
    # ═══════════════════════════════════════════════════════════════════════
    # QUERIES
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_latest_feedback(self) -> Optional[ProprioceptiveFeedback]:
        """Get the most recent proprioceptive feedback."""
        return self._latest_feedback
    
    def get_feedback_history(self, n: int = 10) -> list[ProprioceptiveFeedback]:
        """Get recent feedback history."""
        return list(self._feedback_history)[-n:]
    
    def get_confirmation_rate(self) -> float:
        """Get the rate of confirmed motor actions."""
        total = self.confirmed_count + self.timeout_count
        return self.confirmed_count / max(1, total)
    
    def describe_current_state(self) -> str:
        """Natural language description of sensorimotor state."""
        if self._latest_feedback:
            return self._latest_feedback.describe()
        else:
            return "No recent motor actions to feel"
    
    # ═══════════════════════════════════════════════════════════════════════
    # BOOT
    # ═══════════════════════════════════════════════════════════════════════
    
    def on_boot(self) -> bool:
        """Boot the sensorimotor feedback system.

        FAST BOOT (2026-02-07): Only postal wiring is synchronous.
        Cross-fairy wiring (visual cortex, motor cortex, somatic) and
        feedback loop deferred to background thread to avoid P40 plane timeout.
        """
        self.wire_to_postal()  # Lightweight - just subscribe to postal topics

        # Defer cross-fairy wiring to background thread
        self._deferred_boot_thread = threading.Thread(
            target=self._deferred_boot_work,
            name=f"{self.ACTOR_NAME}_DeferredBoot",
            daemon=True,
        )
        self._deferred_boot_thread.start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (wiring deferred)")
        return True

    def _deferred_boot_work(self):
        """Heavy cross-fairy wiring deferred to background thread."""
        try:
            self.wire_to_visual_cortex()
            self.wire_to_motor_cortex()
            self.wire_to_somatic()
            self.start_feedback_loop()
            print(f"[{self.ACTOR_NAME}] Deferred wiring complete - feedback loop active")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Deferred boot error: {e}")
    
    def get_self_recognition(self):
        """Get the self-recognition model (Phase 4)."""
        return self._self_recognition

    def get_status(self) -> dict:
        """Get current status."""
        status = {
            "actor": self.ACTOR_NAME,
            "running": self._running,
            "total_expectations": self.total_expectations,
            "confirmed": self.confirmed_count,
            "timed_out": self.timeout_count,
            "confirmation_rate": self.get_confirmation_rate(),
            "latest_feedback": self._latest_feedback.describe() if self._latest_feedback else None,
            "visual_cortex_connected": self._visual_cortex is not None,
            "somatic_connected": self._somatic_integration is not None,
        }
        # Phase 4: Self-recognition state
        if self._self_recognition:
            try:
                status["self_recognition"] = self._self_recognition.get_self_recognition_summary()
            except Exception:
                pass
        return status


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ══════════════════════════════════════════════════════════════════════════════

_SENSORIMOTOR_INSTANCE: Optional[SensorimotorFeedbackFairy] = None
_SENSORIMOTOR_LOCK = threading.Lock()


def get_sensorimotor_feedback() -> SensorimotorFeedbackFairy:
    """Get or create the SensorimotorFeedbackFairy singleton."""
    global _SENSORIMOTOR_INSTANCE
    if _SENSORIMOTOR_INSTANCE is None:
        with _SENSORIMOTOR_LOCK:
            if _SENSORIMOTOR_INSTANCE is None:
                _SENSORIMOTOR_INSTANCE = SensorimotorFeedbackFairy()
    return _SENSORIMOTOR_INSTANCE


def boot_sensorimotor_feedback() -> SensorimotorFeedbackFairy:
    """Boot the sensorimotor feedback system."""
    fairy = get_sensorimotor_feedback()
    fairy.on_boot()
    return fairy


# ══════════════════════════════════════════════════════════════════════════════
# MAIN - Test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== SensorimotorFeedbackFairy Test ===\n")
    
    fairy = SensorimotorFeedbackFairy()
    
    # Test expectation registration
    print("[Test] Registering motor intent...")
    exp = fairy.register_motor_intent("move_mouse", (400, 300))
    print(f"  Expectation: {exp}")
    
    # Simulate motor action
    print("\n[Test] Simulating motor action...")
    fairy.on_motor_action("move_mouse", x=400, y=300)
    
    print(f"\n[Test] Status: {fairy.get_status()}")
    print("\n=== Test Complete ===")
