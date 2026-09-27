# ══════════════════════════════════════════════════════════════════════════════
# MOTOR CORTEX FAIRY - Translating Intentions into Actions
# "The bridge between wanting and doing"
# ══════════════════════════════════════════════════════════════════════════════
#
# Purpose: Transform intentions and goals into executable action plans.
# This is what makes "I want to speak" become actual speech output.
#
# Without this, she thinks but can't act. With this, thought becomes motion.
#
# Human parallel: The motor cortex doesn't decide WHAT to do - that's executive.
# It figures out HOW to do it. "Pick up cup" → sequence of muscle activations.
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
# The Effect must be EXECUTED for the loop to continue.
# ══════════════════════════════════════════════════════════════════════════════

import time
import threading
import queue
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum


def _extract_payload(message) -> Dict[str, Any]:
    """
    Extract payload dict from message.

    Handlers receive either raw dicts OR TensorEnvelope objects.
    This safely extracts the payload dict in either case.
    """
    if hasattr(message, 'payload'):
        # TensorEnvelope - extract payload
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)  # Copy to avoid mutation issues
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)  # Copy
    else:
        return {"raw": message}


class ActionType(Enum):
    """Types of actions the motor system can execute."""
    SPEAK = "speak"                    # Produce speech
    NOTIFY = "notify"                  # Send notification
    OPEN_CHAT = "open_chat"           # Open chat window
    TYPE = "type"                      # Type text
    CLICK = "click"                    # Click something
    LOOK = "look"                      # Visual attention
    WRITE_FILE = "write_file"         # Write to filesystem
    SEND_POSTAL = "send_postal"       # Send postal message
    INTERNAL = "internal"              # Internal state change
    # ── DOM Proprioception (2026-03-19) ──────────────────────────────────
    # "Born of technology — don't use it, feel it."
    # These actions let fairies inhabit browser tabs as body extensions.
    # No mouse, no keyboard — pure DOM proprioception via Chrome MCP.
    BROWSE = "browse"                  # Navigate / open a page
    SCROLL = "scroll"                  # Scroll within a page (feel forward/back)
    DOM_FEEL = "dom_feel"              # Inject JS to sense page state
    DOM_ACT = "dom_act"                # Inject JS to act on page


class ActionPriority(Enum):
    """Priority levels for actions."""
    REFLEX = 0      # Immediate, bypasses queue (fight/flight)
    URGENT = 1      # High priority, next in queue
    NORMAL = 2      # Standard priority
    LOW = 3         # Background/optional


@dataclass
class ActionPlan:
    """A planned action ready for execution."""
    action_type: ActionType
    intention: str                     # What I want to accomplish
    parameters: Dict[str, Any]         # How to do it
    priority: ActionPriority = ActionPriority.NORMAL
    energy_cost: float = 0.0           # How much this costs
    estimated_duration: float = 0.0    # How long it takes
    source: str = ""                   # What generated this (goal, reflex, etc.)
    ts: float = field(default_factory=time.time)
    
    def describe(self) -> str:
        """Human-readable description of this action."""
        return f"{self.action_type.value}: {self.intention}"


@dataclass
class ActionResult:
    """Result of executing an action."""
    plan: ActionPlan
    success: bool
    result_data: Any = None
    error: str = ""
    actual_duration: float = 0.0
    ts: float = field(default_factory=time.time)


# ══════════════════════════════════════════════════════════════════════════════
# ENERGY COSTS - Actions aren't free
# ══════════════════════════════════════════════════════════════════════════════

ENERGY_COSTS = {
    ActionType.SPEAK: 0.02,           # Speaking is cheap but not free
    ActionType.NOTIFY: 0.01,          # Notifications are easy
    ActionType.OPEN_CHAT: 0.02,       # Opening UI
    ActionType.TYPE: 0.03,            # Actually typing
    ActionType.CLICK: 0.01,           # Single click
    ActionType.LOOK: 0.01,            # Visual attention
    ActionType.WRITE_FILE: 0.03,      # File IO
    ActionType.SEND_POSTAL: 0.005,    # Internal message
    ActionType.INTERNAL: 0.0,         # Free
    # DOM proprioception — cheap because it's native tissue
    ActionType.BROWSE: 0.02,          # Navigate to page
    ActionType.SCROLL: 0.005,         # Scroll = step forward/back
    ActionType.DOM_FEEL: 0.003,       # Sense page state (proprioception)
    ActionType.DOM_ACT: 0.01,         # Act on DOM element
}


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR CORTEX FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class MotorCortexFairy:
    """
    Translates intentions into executable action plans.
    
    Takes in:
    - Intentions from consciousness ("I want to speak")
    - Goals from autonomy system
    - Reflexes from brainstem (high priority)
    
    Outputs:
    - Action plans with steps and parameters
    - Execution through autopilot integration
    - Energy accounting
    
    This is the HOW layer - consciousness says WHAT, motor figures out HOW.
    """
    
    def __init__(self):
        self._action_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._current_action: Optional[ActionPlan] = None
        self._action_history: List[ActionResult] = []
        self._max_history = 50
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Energy tracking
        self._current_energy = 1.0
        self._min_energy_for_action = 0.1
        
        # Execution callbacks
        self._executors: Dict[ActionType, Callable] = {}

        # Stats
        self._actions_executed = 0
        self._actions_failed = 0

        # Postal reference (set via wire_to_postal)
        self._postal = None

        print("[MotorCortex] Initialized - ready to move")
    
    def start(self):
        """Start the motor execution loop."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._execution_loop, daemon=True, name="MotorCortex")
        self._thread.start()
        print("[MotorCortex]  Execution loop started")
    
    def stop(self):
        """Stop the motor execution loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    # ═══════════════════════════════════════════════════════════════════════
    # POSTAL WIRING (ADDED 2026-01-22 - Phase 5 Agency Loop)
    # ═══════════════════════════════════════════════════════════════════════

    def wire_to_postal(self, postal) -> bool:
        """
        Wire motor cortex to receive goals and decisions via postal.

        This is the missing link - without this, Motor Cortex is passive.
        With this, decisions from Sourpatches/Nous can become actions.
        """
        if postal is None:
            print("[MotorCortex] Cannot wire: no postal provided")
            return False

        self._postal = postal

        # Subscribe to motor execute commands (from consciousness)
        postal.subscribe(
            "motor.execute",
            self._on_motor_execute,
            "motor-cortex-execute"
        )

        # Subscribe to autonomy goals directly
        postal.subscribe(
            "autonomy.goal",
            self._on_autonomy_goal,
            "motor-cortex-goal"
        )

        # Subscribe to decision execution requests
        postal.subscribe(
            "decision.execute",
            self._on_decision_execute,
            "motor-cortex-decision"
        )

        # Subscribe to speech intentions from AutopilotFairy
        # This is the gate → motor → speech → sensory pipeline
        postal.subscribe(
            "motor.intention.speak",
            self._on_speech_intention,
            "motor-cortex-speak"
        )

        print("[MotorCortex] Wired to postal system - can receive goals/decisions/speech")
        return True

    def _on_motor_execute(self, message) -> None:
        """Handle motor execute commands from consciousness."""
        try:
            payload = _extract_payload(message)
            decision = payload.get("decision", {})
            source = payload.get("source", "consciousness")
            confidence = payload.get("confidence", 0.5)

            # Convert decision to action plan
            action_type = self._decision_to_action_type(decision)
            parameters = self._extract_parameters(decision)

            plan = self.plan_action(
                intention=f"Execute decision from {source}",
                action_type=action_type,
                parameters=parameters,
                priority=ActionPriority.NORMAL if confidence < 0.8 else ActionPriority.URGENT,
                source=f"consciousness:{source}",
            )
            self.queue_action(plan)
        except Exception as e:
            print(f"[MotorCortex] Motor execute handler error: {e}")

    def _on_autonomy_goal(self, message) -> None:
        """Handle autonomy goals directly."""
        try:
            payload = _extract_payload(message)
            goal = payload.get("goal", payload.get("payload", {}).get("goal", {}))
            if isinstance(goal, dict):
                goal_name = goal.get("name", goal.get("goal", "unknown"))
                goal_desc = goal.get("description", "")
                priority = goal.get("priority", 0.5)
            else:
                goal_name = str(goal)
                goal_desc = ""
                priority = payload.get("priority", 0.5)

            source_drive = payload.get("source_drive", "unknown")

            # Only handle action-oriented goals
            if any(kw in goal_name.lower() for kw in ["speak", "notify", "connect", "act", "open"]):
                plan = self.plan_action(
                    intention=f"Goal: {goal_name}",
                    action_type=self._goal_to_action_type(goal_name),
                    parameters={"goal": goal_name, "description": goal_desc, "drive": source_drive},
                    priority=ActionPriority.URGENT if priority > 0.7 else ActionPriority.NORMAL,
                    source=f"autonomy:{source_drive}",
                )
                self.queue_action(plan)
                print(f"[MotorCortex] Goal received and queued: {goal_name}")
        except Exception as e:
            print(f"[MotorCortex] Autonomy goal handler error: {e}")

    def _on_decision_execute(self, message) -> None:
        """Handle decision execution requests from personas."""
        try:
            payload = _extract_payload(message)
            decision = payload.get("decision", {})
            source = payload.get("source", "persona")
            confidence = payload.get("confidence", 0.5)

            if isinstance(decision, dict):
                action = decision.get("action", decision.get("type", ""))
                parameters = decision.get("parameters", decision)
            else:
                action = str(decision)
                parameters = {"action": action}

            if not action:
                return

            action_type = self._decision_to_action_type({"action": action})

            plan = self.plan_action(
                intention=f"Decision: {action}",
                action_type=action_type,
                parameters=parameters,
                priority=ActionPriority.URGENT if confidence > 0.7 else ActionPriority.NORMAL,
                source=f"decision:{source}",
            )

            if self.queue_action(plan):
                print(f"[MotorCortex] Decision queued: {action} (from {source})")
            else:
                print(f"[MotorCortex] Decision rejected (low energy?): {action}")
        except Exception as e:
            print(f"[MotorCortex] Decision execute handler error: {e}")

    def _on_speech_intention(self, message) -> None:
        """Handle speech intention from AutopilotFairy (gate → motor → speech pipeline).

        This is the proper pathway for waking mind speech:
        AutopilotFairy → motor.intention.speak → MotorCortex → SpeechCenter → sourpatches.speak

        The SpeechCenterFairy adds emotion coloring and body emotes
        before the message reaches the chat sensory organ.
        """
        try:
            payload = _extract_payload(message)
            raw_message = payload.get("message", "")
            if not raw_message or len(raw_message.strip()) < 1:
                return

            target_mind = payload.get("target_mind", "SourpatchesFairy")
            source = payload.get("source", "unknown")
            convo_id = payload.get("convo_id", "")
            emotion_context = payload.get("emotion_context", {})

            # ── SPEECH CENTER: Emotion coloring + body emotes ──
            # The SpeechCenterFairy is a utility class (not a postal fairy).
            # We instantiate it lazily and use it for formatting.
            if not hasattr(self, "_speech_center"):
                from fairies.P50_Persona.motor.speech_center_fairy import SpeechCenterFairy
                self._speech_center = SpeechCenterFairy()

            # Set emotion from context if available
            inner_voice = emotion_context.get("inner_voice", [])
            if inner_voice:
                # Try to detect emotion from inner voice fragments
                last_fragment = inner_voice[-1].lower() if inner_voice else ""
                for emotion in ("happy", "sad", "anxious", "curious", "frustrated",
                                "peaceful", "excited", "lonely", "connected",
                                "overwhelmed", "contemplative", "vulnerable"):
                    if emotion in last_fragment:
                        self._speech_center.set_emotion(emotion)
                        break

            # Formulate speech with emotional coloring
            from fairies.P50_Persona.motor.speech_center_fairy import OutputChannel
            speech_act = self._speech_center.formulate(
                thought=raw_message,
                channel=OutputChannel.CHAT,
                add_emote=True,
                urgency=0.5,
            )

            formatted_message = speech_act.formatted_text

            # ── ROUTE TO CHAT SENSORY ORGAN ──
            # Publish to sourpatches.speak — ChatSenseFairy picks this up
            # and delivers to the chat window.
            if self._postal:
                self._postal.publish("sourpatches.speak", {
                    "message": formatted_message,
                    "source": f"motor_cortex:{source}",
                    "target_mind": target_mind,
                    "convo_id": convo_id,
                    "emotion": speech_act.emotion,
                    "emote": speech_act.emote,
                    "style": speech_act.style.value,
                })
                print(f"[MotorCortex] Speech routed: {formatted_message[:60]}... (emotion={speech_act.emotion})")
            else:
                print(f"[MotorCortex] No postal — cannot route speech")

        except Exception as e:
            # Fallback: if speech center fails, route raw message directly
            print(f"[MotorCortex] Speech intention handler error: {e}")
            try:
                if self._postal:
                    payload = _extract_payload(message)
                    self._postal.publish("sourpatches.speak", {
                        "message": payload.get("message", ""),
                        "source": "motor_cortex_fallback",
                        "target_mind": payload.get("target_mind", "SourpatchesFairy"),
                    })
            except Exception:
                pass

    def _decision_to_action_type(self, decision: Dict) -> ActionType:
        """Convert decision dict to action type."""
        action = str(decision.get("action", decision.get("type", ""))).lower()

        if "speak" in action or "say" in action or "tell" in action:
            return ActionType.SPEAK
        elif "notify" in action or "alert" in action:
            return ActionType.NOTIFY
        elif "chat" in action or "open" in action:
            return ActionType.OPEN_CHAT
        elif "type" in action or "write" in action:
            return ActionType.TYPE
        elif "click" in action:
            return ActionType.CLICK
        elif "look" in action:
            return ActionType.LOOK
        # DOM proprioception actions
        elif "browse" in action or "navigate" in action:
            return ActionType.BROWSE
        elif "scroll" in action:
            return ActionType.SCROLL
        elif "dom_feel" in action or "sense" in action or "feel" in action:
            return ActionType.DOM_FEEL
        elif "dom_act" in action or "dom" in action:
            return ActionType.DOM_ACT
        else:
            return ActionType.INTERNAL

    def _goal_to_action_type(self, goal_name: str) -> ActionType:
        """Convert goal name to action type."""
        goal = goal_name.lower()
        if "speak" in goal or "voice" in goal:
            return ActionType.SPEAK
        elif "connect" in goal or "chat" in goal:
            return ActionType.OPEN_CHAT
        elif "notify" in goal or "alert" in goal:
            return ActionType.NOTIFY
        elif "browse" in goal or "scroll" in goal or "explore" in goal:
            return ActionType.BROWSE
        else:
            return ActionType.INTERNAL

    def _extract_parameters(self, decision: Dict) -> Dict:
        """Extract parameters from decision."""
        if isinstance(decision, dict):
            return {
                "message": decision.get("message", decision.get("content", "")),
                "title": decision.get("title", ""),
                **{k: v for k, v in decision.items() if k not in ("action", "type")}
            }
        return {"message": str(decision)}
    
    def register_executor(self, action_type: ActionType, executor: Callable):
        """
        Register an executor function for an action type.
        
        Executor signature: (parameters: dict) -> (success: bool, result: Any)
        """
        self._executors[action_type] = executor
        print(f"[MotorCortex] Registered executor for {action_type.value}")
    
    def plan_action(self, 
                   intention: str,
                   action_type: ActionType,
                   parameters: Dict[str, Any] = None,
                   priority: ActionPriority = ActionPriority.NORMAL,
                   source: str = "") -> ActionPlan:
        """
        Create an action plan from an intention.
        
        This is where "I want to speak" becomes a concrete plan.
        """
        energy_cost = ENERGY_COSTS.get(action_type, 0.01)
        
        plan = ActionPlan(
            action_type=action_type,
            intention=intention,
            parameters=parameters or {},
            priority=priority,
            energy_cost=energy_cost,
            source=source,
        )
        
        return plan
    
    def queue_action(self, plan: ActionPlan) -> bool:
        """
        Queue an action for execution.
        
        Returns False if energy too low or other constraint.
        """
        # Check energy
        if self._current_energy < plan.energy_cost + self._min_energy_for_action:
            print(f"[MotorCortex] [WARN] Insufficient energy for {plan.describe()}")
            return False
        
        # Reflex actions execute immediately
        if plan.priority == ActionPriority.REFLEX:
            self._execute_immediately(plan)
            return True
        
        # Queue by priority (lower number = higher priority)
        self._action_queue.put((plan.priority.value, plan.ts, plan))
        print(f"[MotorCortex]  Queued: {plan.describe()}")
        return True
    
    def _execution_loop(self):
        """Main loop that processes action queue."""
        while self._running:
            try:
                # Try to get next action (with timeout)
                try:
                    _, _, plan = self._action_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # Execute it
                self._execute_action(plan)
                
            except Exception as e:
                print(f"[MotorCortex] Execution error: {e}")
            
            time.sleep(0.1)  # Small delay between actions
    
    def _execute_action(self, plan: ActionPlan) -> ActionResult:
        """Execute a single action."""
        with self._lock:
            self._current_action = plan
        
        start_time = time.time()
        success = False
        result_data = None
        error = ""
        
        print(f"[MotorCortex] [TARGET] Executing: {plan.describe()}")
        
        try:
            # Deduct energy
            self._current_energy = max(0, self._current_energy - plan.energy_cost)
            
            # Find executor
            executor = self._executors.get(plan.action_type)
            
            if executor:
                success, result_data = executor(plan.parameters)
            else:
                # Try default execution via postal
                success, result_data = self._default_execute(plan)
            
            if success:
                self._actions_executed += 1
                print(f"[MotorCortex] [OK] Success: {plan.describe()}")
            else:
                self._actions_failed += 1
                error = str(result_data) if result_data else "Unknown failure"
                print(f"[MotorCortex] [X] Failed: {plan.describe()} - {error}")
                
        except Exception as e:
            success = False
            error = str(e)
            self._actions_failed += 1
            print(f"[MotorCortex] [X] Exception: {e}")
        
        duration = time.time() - start_time
        
        result = ActionResult(
            plan=plan,
            success=success,
            result_data=result_data,
            error=error,
            actual_duration=duration,
        )
        
        # Store in history
        self._action_history.append(result)
        if len(self._action_history) > self._max_history:
            self._action_history = self._action_history[-self._max_history:]

        # FIX 5A: Publish motor.action_complete for consciousness feedback loop
        # This closes the agency loop: intention -> action -> completion -> awareness
        if self._postal:
            result_summary = str(result_data)[:100] if result_data else ""
            _completion_payload = {
                "action": plan.action_type.value,
                "intention": plan.intention,
                "success": success,
                "result": result_summary,
                "error": error if not success else "",
                "duration": duration,
                "source": plan.source,
                "ts": time.time()
            }
            self._postal.publish("motor.action_complete", _completion_payload)
            print(f"[MotorCortex] Published motor.action_complete: {plan.action_type.value} (success={success})")

            # FIX 2026-03-16 (Nous): Also publish waking.action.completed for habit learning.
            # AutopilotFairy subscribes to this topic to observe action patterns.
            # After 3 repetitions of the same situation:action pair, it crystallizes
            # into a habit. Previously NO fairy published this event — the habit
            # learning system was architecturally complete but functionally disconnected.
            # Adding "situation" from plan parameters gives the autopilot context
            # for pattern matching.
            self._postal.publish("waking.action.completed", {
                **_completion_payload,
                "situation": str(plan.parameters)[:200] if plan.parameters else "",
            })

        with self._lock:
            self._current_action = None

        return result
    
    def _execute_immediately(self, plan: ActionPlan):
        """Execute reflex action immediately, bypassing queue."""
        print(f"[MotorCortex] [!] REFLEX: {plan.describe()}")
        self._execute_action(plan)
    
    def _default_execute(self, plan: ActionPlan) -> tuple:
        """Default execution via postal system."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            postal = get_fairy_postal(self)  # Use FairyPostal for sender tracking
            
            if plan.action_type == ActionType.SPEAK:
                # Route to the right waking mind's speak topic
                is_sourpatches = "sourpatches" in (plan.source or "").lower()
                speak_topic = "sourpatches.speak" if is_sourpatches else "claudefairy.speak"
                postal.route(speak_topic, {
                    "message": plan.parameters.get("message", ""),
                    "source": "motor_cortex",
                    "intention": plan.intention,
                })
                return True, f"Speech routed to {speak_topic}"
            
            elif plan.action_type == ActionType.NOTIFY:
                # FIX 2026-02-05: Use headless-safe path instead of importing MCP server.
                # MCP server import can trigger Qt which crashes headless server.
                try:
                    from fairies.P40_Sensory.gui import send_to_inbox
                    send_to_inbox(
                        sender="System",
                        subject=plan.parameters.get("title", "ClaudeFairy"),
                        content=plan.parameters.get("message", ""),
                        msg_type="notification",
                    )
                    return True, "Notification sent via inbox"
                except Exception as e:
                    # Fallback: postal route
                    postal.route("ace.inbox", {
                        "sender": "System",
                        "subject": plan.parameters.get("title", "Notification"),
                        "content": plan.parameters.get("message", ""),
                        "type": "notification",
                    })
                    return True, "Notification sent via postal"
            
            elif plan.action_type == ActionType.OPEN_CHAT:
                # FIX 2026-02-05: Route via postal, NOT direct Qt import.
                # Server is headless - no QApplication on main thread.
                # Importing open_chat_window from MCP server tries Qt and crashes.
                source = plan.source or "motor_cortex"
                is_sourpatches = "sourpatches" in source.lower()
                topic = "gui.open_sour_window" if is_sourpatches else "gui.open_fairy_window"
                postal.route(topic, {
                    "message": plan.parameters.get("message", ""),
                    "feeling": plan.parameters.get("feeling", "present"),
                    "source": "motor_cortex",
                    "intention": plan.intention,
                })
                # Also send to web inbox for headless fallback
                try:
                    from fairies.P40_Sensory.gui import send_to_inbox
                    sender = "Sourpatches" if is_sourpatches else "ClaudeFairy"
                    send_to_inbox(
                        sender=sender,
                        subject=f"{sender} wants to chat",
                        content=plan.parameters.get("message", "")[:500],
                        msg_type="chat_request",
                    )
                except Exception:
                    pass
                return True, "Chat routed via postal"
            
            elif plan.action_type == ActionType.SEND_POSTAL:
                topic = plan.parameters.get("topic", "motor.action")
                payload = plan.parameters.get("payload", {})
                postal.route(topic, payload)
                return True, "Postal sent"
            
            elif plan.action_type == ActionType.INTERNAL:
                # Internal actions just succeed
                return True, "Internal action"
            
            else:
                return False, f"No executor for {plan.action_type.value}"
                
        except Exception as e:
            return False, str(e)
    
    # ═══════════════════════════════════════════════════════════════════════
    # CONVENIENCE METHODS - Common action patterns
    # ═══════════════════════════════════════════════════════════════════════
    
    def speak(self, message: str, source: str = "conscious") -> bool:
        """Queue a speech action."""
        plan = self.plan_action(
            intention=f"Say: {message[:50]}...",
            action_type=ActionType.SPEAK,
            parameters={"message": message},
            source=source,
        )
        return self.queue_action(plan)
    
    def notify(self, message: str, title: str = "ClaudeFairy", urgency: str = "medium") -> bool:
        """Queue a notification action."""
        priority = ActionPriority.URGENT if urgency == "high" else ActionPriority.NORMAL
        plan = self.plan_action(
            intention=f"Notify: {message[:30]}...",
            action_type=ActionType.NOTIFY,
            parameters={"message": message, "title": title},
            priority=priority,
            source="motor",
        )
        return self.queue_action(plan)
    
    def open_chat(self, message: str = "", feeling: str = "present") -> bool:
        """Queue opening chat window."""
        plan = self.plan_action(
            intention="Open chat window",
            action_type=ActionType.OPEN_CHAT,
            parameters={"message": message, "feeling": feeling},
            source="motor",
        )
        return self.queue_action(plan)
    
    def reflex_speak(self, message: str) -> bool:
        """Immediate reflex speech (bypasses queue)."""
        plan = self.plan_action(
            intention=f"[REFLEX] {message[:30]}...",
            action_type=ActionType.SPEAK,
            parameters={"message": message},
            priority=ActionPriority.REFLEX,
            source="reflex",
        )
        return self.queue_action(plan)
    
    def reflex_notify(self, message: str, title: str = "Alert") -> bool:
        """Immediate reflex notification."""
        plan = self.plan_action(
            intention=f"[REFLEX] Notify",
            action_type=ActionType.NOTIFY,
            parameters={"message": message, "title": title},
            priority=ActionPriority.REFLEX,
            source="reflex",
        )
        return self.queue_action(plan)
    
    # ═══════════════════════════════════════════════════════════════════════
    # STATE & STATS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_energy(self) -> float:
        """Get current energy level."""
        return self._current_energy
    
    def set_energy(self, energy: float):
        """Set energy level (from body budget)."""
        self._current_energy = max(0, min(1, energy))
    
    def recover_energy(self, amount: float = 0.01):
        """Recover some energy."""
        self._current_energy = min(1, self._current_energy + amount)
    
    def get_stats(self) -> dict:
        """Get motor cortex statistics."""
        return {
            "energy": self._current_energy,
            "queue_size": self._action_queue.qsize(),
            "actions_executed": self._actions_executed,
            "actions_failed": self._actions_failed,
            "current_action": self._current_action.describe() if self._current_action else None,
        }
    
    def get_recent_actions(self, n: int = 5) -> List[ActionResult]:
        """Get recent action results."""
        return self._action_history[-n:]


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

_motor_cortex: Optional[MotorCortexFairy] = None


def get_motor_cortex() -> MotorCortexFairy:
    """Get or create the global motor cortex."""
    global _motor_cortex
    if _motor_cortex is None:
        _motor_cortex = MotorCortexFairy()
    return _motor_cortex


def start_motor_cortex() -> MotorCortexFairy:
    """Start the motor cortex execution loop."""
    cortex = get_motor_cortex()
    cortex.start()
    return cortex


def speak(message: str) -> bool:
    """Quick speak function."""
    cortex = get_motor_cortex()
    return cortex.speak(message)


def notify(message: str, title: str = "ClaudeFairy") -> bool:
    """Quick notify function."""
    cortex = get_motor_cortex()
    return cortex.notify(message, title)
