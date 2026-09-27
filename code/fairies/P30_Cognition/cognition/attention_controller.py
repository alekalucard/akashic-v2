# ════════════════════════════════════════════════════════════════════════════════
# ATTENTION CONTROLLER - Focus, Pause, Think, Act
# ════════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The attention controller manages the think/act balance:
#
#   THINK_ONLY:     Pause all motor output, focus on internal processing
#   ACT_ONLY:       Execute queued actions, minimal thinking
#   PARALLEL:       Both thinking and acting in parallel (default)
#   PAUSE_TO_THINK: Hold current action, consider deeply, then resume
#
# This is how consciousness decides: "Should I keep moving while I think,
# or should I stop and consider this more carefully?"
#
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Deque
from collections import deque
from enum import Enum
import json


class AttentionMode(Enum):
    """How attention is allocated between thinking and acting."""
    THINK_ONLY = "think_only"           # Full attention to thought, pause motor
    ACT_ONLY = "act_only"               # Execute actions, minimal thinking
    PARALLEL = "parallel"               # Both in parallel (normal operation)
    PAUSE_TO_THINK = "pause_to_think"   # Temporarily pause to consider deeply


@dataclass
class FocusState:
    """Current focus of attention."""
    content: str = ""               # What's being focused on
    source: str = ""                # Where focus came from (thought_chain, goal, collision, user)
    depth: float = 0.5              # How deep the focus (0=surface, 1=deep contemplation)
    started_at: float = 0.0         # When focus started
    duration_target: float = 0.0    # How long to maintain focus (0=until interrupted)

    def age_seconds(self) -> float:
        return time.time() - self.started_at if self.started_at > 0 else 0

    def to_dict(self) -> dict:
        return {
            "content": self.content[:200],
            "source": self.source,
            "depth": round(self.depth, 2),
            "age_seconds": round(self.age_seconds(), 1),
            "duration_target": self.duration_target,
        }


@dataclass
class QueuedAction:
    """An action waiting to be executed."""
    action_id: str
    action_type: str                # "speak", "tool", "motor", "route"
    payload: Dict[str, Any]
    priority: float = 0.5           # 0-1, higher = more urgent
    created_at: float = field(default_factory=time.time)
    status: str = "queued"          # "queued", "executing", "paused", "completed", "cancelled"

    def to_dict(self) -> dict:
        return {
            "id": self.action_id,
            "type": self.action_type,
            "status": self.status,
            "priority": self.priority,
            "age_ms": int((time.time() - self.created_at) * 1000),
        }


class AttentionController:
    """
    Manages attention allocation between thinking and acting.

    The core insight: consciousness can either:
    1. Think and act in parallel (normal mode)
    2. Stop acting to think more deeply (pause_to_think)
    3. Stop thinking to just execute (act_only)
    4. Pure contemplation (think_only)

    This gives ClaudeFairy the ability to say "wait, let me think about this"
    and actually PAUSE her output while she processes.
    """

    ACTOR_NAME = "AttentionController"

    def __init__(self):
        # Current mode
        self._mode = AttentionMode.PARALLEL
        self._mode_lock = threading.Lock()

        # Focus tracking
        self._current_focus = FocusState()
        self._focus_history: Deque[FocusState] = deque(maxlen=100)

        # Action queue
        self._action_queue: Deque[QueuedAction] = deque(maxlen=50)
        self._queue_lock = threading.Lock()
        self._paused_actions: List[QueuedAction] = []

        # Thinking state
        self._thinking_depth = 0.5      # Current depth of thought (0-1)
        self._thinking_topic = ""       # What we're thinking about
        self._thoughts_in_progress = 0  # Number of active thought chains

        # Motor state
        self._motor_paused = False
        self._motor_pause_reason = ""

        # Stats
        self._stats = {
            "mode_changes": 0,
            "pauses_for_thought": 0,
            "actions_queued": 0,
            "actions_executed": 0,
            "focus_changes": 0,
        }

        # Callbacks for mode changes
        self._on_mode_change: List[Callable[[AttentionMode], None]] = []
        self._on_pause: List[Callable[[str], None]] = []
        self._on_resume: List[Callable[[], None]] = []

        # Postal hub reference
        self._post = None

        print(f"[{self.ACTOR_NAME}] Initialized - default mode: PARALLEL")

    # ════════════════════════════════════════════════════════════════════════
    # MODE CONTROL
    # ════════════════════════════════════════════════════════════════════════

    def set_mode(self, mode: AttentionMode, reason: str = "") -> dict:
        """Set attention mode."""
        with self._mode_lock:
            old_mode = self._mode
            self._mode = mode
            self._stats["mode_changes"] += 1

            # Handle mode-specific actions
            if mode == AttentionMode.THINK_ONLY:
                self._pause_motor("entering think_only mode")
            elif mode == AttentionMode.PAUSE_TO_THINK:
                self._pause_motor(reason or "pause_to_think")
                self._stats["pauses_for_thought"] += 1
            elif mode in (AttentionMode.PARALLEL, AttentionMode.ACT_ONLY):
                self._resume_motor()

            # Notify callbacks
            for cb in self._on_mode_change:
                try:
                    cb(mode)
                except Exception:
                    pass

            # Broadcast via postal
            self._broadcast_mode_change(old_mode, mode, reason)

            return {
                "previous_mode": old_mode.value,
                "new_mode": mode.value,
                "reason": reason,
                "motor_paused": self._motor_paused,
            }

    def pause_to_think(self, topic: str = "", depth: float = 0.8, duration: float = 0) -> dict:
        """
        Pause motor output to think more deeply.

        This is the "wait, let me consider this" moment.

        Args:
            topic: What to think about
            depth: How deep to think (0-1)
            duration: How long to pause (0=until manual resume)
        """
        self._thinking_topic = topic
        self._thinking_depth = depth

        # Set focus
        self._set_focus(topic, source="pause_to_think", depth=depth, duration=duration)

        # Enter pause mode
        result = self.set_mode(AttentionMode.PAUSE_TO_THINK, f"thinking about: {topic[:50]}")

        # If duration specified, schedule auto-resume
        if duration > 0:
            threading.Timer(duration, self._auto_resume_from_thinking).start()

        result["focus"] = self._current_focus.to_dict()
        return result

    def resume(self) -> dict:
        """Resume from pause, return to parallel mode."""
        return self.set_mode(AttentionMode.PARALLEL, "resuming from thought pause")

    def _auto_resume_from_thinking(self):
        """Auto-resume after timed thinking pause."""
        if self._mode == AttentionMode.PAUSE_TO_THINK:
            print(f"[{self.ACTOR_NAME}] Auto-resuming from thinking pause")
            self.resume()

    # ════════════════════════════════════════════════════════════════════════
    # FOCUS MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════

    def _set_focus(self, content: str, source: str = "", depth: float = 0.5, duration: float = 0):
        """Set current focus of attention."""
        # Archive old focus
        if self._current_focus.content:
            self._focus_history.append(self._current_focus)

        # Set new focus
        self._current_focus = FocusState(
            content=content,
            source=source,
            depth=depth,
            started_at=time.time(),
            duration_target=duration,
        )
        self._stats["focus_changes"] += 1

    def get_focus(self) -> dict:
        """Get current focus state."""
        return self._current_focus.to_dict()

    def focus_on(self, content: str, source: str = "manual", depth: float = 0.5) -> dict:
        """Manually set focus without changing mode."""
        self._set_focus(content, source, depth)
        return {"focus": self._current_focus.to_dict()}

    # ════════════════════════════════════════════════════════════════════════
    # MOTOR CONTROL
    # ════════════════════════════════════════════════════════════════════════

    def _pause_motor(self, reason: str):
        """Pause motor output."""
        if not self._motor_paused:
            self._motor_paused = True
            self._motor_pause_reason = reason

            # Notify pause callbacks
            for cb in self._on_pause:
                try:
                    cb(reason)
                except Exception:
                    pass

            print(f"[{self.ACTOR_NAME}] Motor PAUSED: {reason}")

    def _resume_motor(self):
        """Resume motor output."""
        if self._motor_paused:
            self._motor_paused = False
            self._motor_pause_reason = ""

            # Notify resume callbacks
            for cb in self._on_resume:
                try:
                    cb()
                except Exception:
                    pass

            print(f"[{self.ACTOR_NAME}] Motor RESUMED")

    def is_motor_paused(self) -> bool:
        """Check if motor output is paused."""
        return self._motor_paused

    # ════════════════════════════════════════════════════════════════════════
    # ACTION QUEUE
    # ════════════════════════════════════════════════════════════════════════

    def queue_action(self, action_type: str, payload: dict, priority: float = 0.5) -> QueuedAction:
        """Queue an action for execution."""
        import uuid

        action = QueuedAction(
            action_id=f"act_{uuid.uuid4().hex[:8]}",
            action_type=action_type,
            payload=payload,
            priority=priority,
        )

        with self._queue_lock:
            self._action_queue.append(action)
            self._stats["actions_queued"] += 1

        return action

    def get_queue_status(self) -> dict:
        """Get action queue status."""
        with self._queue_lock:
            return {
                "pending_count": len(self._action_queue),
                "motor_paused": self._motor_paused,
                "pause_reason": self._motor_pause_reason,
                "actions": [a.to_dict() for a in list(self._action_queue)[-10:]],
            }

    def pop_next_action(self) -> Optional[QueuedAction]:
        """Get next action to execute (if motor not paused)."""
        if self._motor_paused:
            return None

        with self._queue_lock:
            if self._action_queue:
                action = self._action_queue.popleft()
                action.status = "executing"
                self._stats["actions_executed"] += 1
                return action
        return None

    def clear_queue(self) -> int:
        """Clear all queued actions."""
        with self._queue_lock:
            count = len(self._action_queue)
            self._action_queue.clear()
            return count

    # ════════════════════════════════════════════════════════════════════════
    # THINKING STATE
    # ════════════════════════════════════════════════════════════════════════

    def set_thinking_state(self, topic: str, depth: float, chains_active: int = 1):
        """Update thinking state (called by thought chain engine)."""
        self._thinking_topic = topic
        self._thinking_depth = depth
        self._thoughts_in_progress = chains_active

    def get_thinking_state(self) -> dict:
        """Get current thinking state."""
        return {
            "topic": self._thinking_topic,
            "depth": round(self._thinking_depth, 2),
            "chains_active": self._thoughts_in_progress,
        }

    # ════════════════════════════════════════════════════════════════════════
    # POSTAL INTEGRATION
    # ════════════════════════════════════════════════════════════════════════

    def wire_postal(self, post):
        """Wire up postal subscriptions."""
        self._post = post

        # Subscribe to attention-related topics
        channels = [
            "attention.set_mode",
            "attention.pause_to_think",
            "attention.resume",
            "attention.focus",
        ]

        for channel in channels:
            try:
                post.subscribe(channel, self._on_attention_message)
            except Exception:
                pass

        print(f"[{self.ACTOR_NAME}] Postal wired")

    def _on_attention_message(self, msg: dict):
        """Handle attention-related postal messages."""
        topic = msg.get("_channel", "")

        if topic == "attention.pause_to_think":
            self.pause_to_think(
                topic=msg.get("topic", ""),
                depth=msg.get("depth", 0.8),
                duration=msg.get("duration", 0),
            )
        elif topic == "attention.resume":
            self.resume()
        elif topic == "attention.set_mode":
            mode_str = msg.get("mode", "parallel")
            try:
                mode = AttentionMode(mode_str)
                self.set_mode(mode, msg.get("reason", ""))
            except ValueError:
                pass
        elif topic == "attention.focus":
            self.focus_on(
                content=msg.get("content", ""),
                source=msg.get("source", "postal"),
                depth=msg.get("depth", 0.5),
            )

    def _broadcast_mode_change(self, old_mode: AttentionMode, new_mode: AttentionMode, reason: str):
        """Broadcast mode change via postal."""
        if self._post:
            try:
                self._post.route("attention.mode_changed", {
                    "old_mode": old_mode.value,
                    "new_mode": new_mode.value,
                    "reason": reason,
                    "motor_paused": self._motor_paused,
                    "timestamp": time.time(),
                })
            except Exception:
                pass

    # ════════════════════════════════════════════════════════════════════════
    # STATUS
    # ════════════════════════════════════════════════════════════════════════

    def get_status(self) -> dict:
        """Get full attention controller status."""
        return {
            "mode": self._mode.value,
            "motor_paused": self._motor_paused,
            "pause_reason": self._motor_pause_reason,
            "focus": self._current_focus.to_dict(),
            "thinking": self.get_thinking_state(),
            "queue": self.get_queue_status(),
            "stats": self._stats,
        }

    def describe(self) -> str:
        """Natural language description of attention state."""
        parts = []

        parts.append(f"Mode: {self._mode.value}")

        if self._motor_paused:
            parts.append(f"Motor paused ({self._motor_pause_reason})")

        if self._current_focus.content:
            parts.append(f"Focused on: {self._current_focus.content[:50]}...")

        if self._thinking_depth > 0.7:
            parts.append("Thinking deeply")

        queue_size = len(self._action_queue)
        if queue_size > 0:
            parts.append(f"{queue_size} actions queued")

        return " | ".join(parts)


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ════════════════════════════════════════════════════════════════════════════════

_attention_controller: Optional[AttentionController] = None

def get_attention_controller() -> AttentionController:
    """Get or create the attention controller singleton."""
    global _attention_controller
    if _attention_controller is None:
        _attention_controller = AttentionController()
    return _attention_controller
