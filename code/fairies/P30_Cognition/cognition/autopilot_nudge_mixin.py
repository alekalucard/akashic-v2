# autopilot_nudge_mixin.py - Nudge handling for AutopilotFairy
# Wires GoalSchedulerFairy nudges into AutopilotFairy
# 
# This creates the: GOAL → NUDGE → URGE → ACTION pathway
# The missing link that causes agent drift!
#
# Usage in autopilot_fairy.py:
#   from fairies.P30_Cognition.cognition.autopilot_nudge_mixin import AutopilotNudgeMixin
#   class AutopilotFairy(AutopilotNudgeMixin, _template.MyOrganFairy):
#       ...
#
# And call in on_boot():
#   self._subscribe_to_nudges()

import time
from typing import Dict, List, Optional, Any


class AutopilotNudgeMixin:
    """
    Mixin that adds nudge handling to AutopilotFairy.
    
    The GoalSchedulerFairy extracts goals from conversation and sends
    nudges to create "urge to act". This mixin receives those nudges
    and creates the internal pressure that drives action.
    
    Without this: Goals exist but nothing compels action.
    With this: Goals create urges → urges create action → action creates new thinking.
    
    This is the equation in action:
    CAUSE (goal) → AFFECT (nudge/urge) → EFFECT (action) → AFFECT (new thinking) → ∞
    """
    
    def _init_nudge_system(self):
        """Initialize nudge tracking structures."""
        self.pending_nudges: Dict[str, dict] = {}
        self.action_queue: List[dict] = []
        self.nudges_received = 0
        self.urges_created = 0
        # 2026-03-24 FIX (Nous + Ace): Was 0.3, drives never reached it.
        # 0 goals nudged, 0 loop closures, 0 skill XP for months.
        self.nudge_threshold = 0.15  # Lowered: let weak drives create urges
    
    def _subscribe_to_nudges(self):
        """Subscribe to GoalScheduler nudge channel."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            postal.subscribe("autopilot.nudge", self._on_nudge)
            postal.subscribe("goal_scheduler.nudge", self._on_nudge)
            print(f"[{getattr(self, 'ACTOR_NAME', 'AutopilotFairy')}] [OK] Subscribed to GoalScheduler nudges")
        except Exception as e:
            print(f"[{getattr(self, 'ACTOR_NAME', 'AutopilotFairy')}] Failed to subscribe to nudges: {e}")
    
    def _on_nudge(self, packet: dict):
        """
        Handle nudge from GoalSchedulerFairy.
        
        This is the bridge: GOAL → URGE → ACTION
        
        Nudges create an internal "pressure" to act on goals,
        similar to how biological systems create drive states.
        """
        if not isinstance(packet, dict):
            return
        
        goal_id = packet.get("goal_id", "")
        goal_name = packet.get("goal_name", "")
        description = packet.get("description", "")
        nudge_strength = packet.get("nudge_strength", 0.5)
        suggested_action = packet.get("suggested_action", "")
        
        # Initialize if needed
        if not hasattr(self, "pending_nudges"):
            self._init_nudge_system()
        
        # Track nudge
        self.nudges_received += 1
        
        # Store in pending nudges (create internal pressure)
        self.pending_nudges[goal_id] = {
            "name": goal_name,
            "description": description,
            "strength": nudge_strength,
            "suggested_action": suggested_action,
            "received_at": time.time(),
            "acted_on": False,
        }
        
        # If strong enough nudge, create immediate action urge
        threshold = getattr(self, "nudge_threshold", 0.3)
        if nudge_strength > threshold:
            self._create_action_urge(goal_name, description, suggested_action, nudge_strength)
        
        # Log the nudge
        print(f"[{getattr(self, 'ACTOR_NAME', 'AutopilotFairy')}] [!] Nudge: {goal_name} (strength={nudge_strength:.2f})")
    
    def _create_action_urge(self, goal_name: str, description: str, 
                            suggested_action: str, strength: float):
        """
        Create the internal URGE to act.
        
        This is what turns passive goals into active intention.
        The urge broadcasts to consciousness, creating the subjective
        experience of "wanting to do something".
        """
        if not hasattr(self, "action_queue"):
            self.action_queue = []
        if not hasattr(self, "urges_created"):
            self.urges_created = 0
            
        urge = {
            "type": "action_urge",
            "goal": goal_name,
            "description": description,
            "suggested_action": suggested_action,
            "urge_strength": strength,
            "source": "goal_scheduler_nudge",
            "ts": time.time(),
        }
        
        self.urges_created += 1
        
        # Broadcast urge to consciousness stream
        try:
            post = getattr(self, "post", None)
            if post:
                post.route("consciousness.urge", urge)
                post.route("autopilot.action_urge", urge)
        except Exception as e:
            print(f"[{getattr(self, 'ACTOR_NAME', 'AutopilotFairy')}] Failed to broadcast urge: {e}")
        
        # Also add to internal action queue
        self.action_queue.append(urge)
        
        # Trim queue
        if len(self.action_queue) > 20:
            self.action_queue = self.action_queue[-20:]
    
    def get_pending_nudges(self) -> List[dict]:
        """Get current pending nudges that haven't been acted on."""
        if not hasattr(self, "pending_nudges"):
            return []
        
        now = time.time()
        pending = []
        for goal_id, nudge in self.pending_nudges.items():
            if not nudge.get("acted_on", False):
                age = now - nudge.get("received_at", now)
                # Nudges decay over time (5 minute halflife)
                effective_strength = nudge["strength"] * max(0.1, 1 - (age / 300))
                pending.append({
                    "goal_id": goal_id,
                    "name": nudge["name"],
                    "strength": effective_strength,
                    "suggested_action": nudge.get("suggested_action", ""),
                    "age_seconds": age,
                })
        
        # Sort by strength
        pending.sort(key=lambda x: x["strength"], reverse=True)
        return pending
    
    def get_action_urges(self) -> List[dict]:
        """Get current action urges (recent, sorted by strength)."""
        if not hasattr(self, "action_queue"):
            return []
        
        now = time.time()
        # Only return urges from last 5 minutes
        recent = [u for u in self.action_queue if now - u.get("ts", 0) < 300]
        recent.sort(key=lambda x: x.get("urge_strength", 0), reverse=True)
        return recent
    
    def mark_goal_acted_on(self, goal_id: str):
        """Mark a goal as acted upon (reduces nudge pressure)."""
        if hasattr(self, "pending_nudges") and goal_id in self.pending_nudges:
            self.pending_nudges[goal_id]["acted_on"] = True
    
    def get_nudge_stats(self) -> dict:
        """Get nudge system statistics."""
        return {
            "nudges_received": getattr(self, "nudges_received", 0),
            "urges_created": getattr(self, "urges_created", 0),
            "pending_count": len(self.get_pending_nudges()),
            "active_urges": len(self.get_action_urges()),
            "threshold": getattr(self, "nudge_threshold", 0.3),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
#
# Add to autopilot_fairy.py:
#
# 1. Import at top:
#    from fairies.P30_Cognition.cognition.autopilot_nudge_mixin import AutopilotNudgeMixin
#
# 2. Add to class inheritance:
#    class AutopilotFairy(AutopilotNudgeMixin, _template.MyOrganFairy):
#
# 3. In on_boot() method, add:
#    self._init_nudge_system()
#    self._subscribe_to_nudges()
#
# That's it! The mixin provides all nudge handling.
# ═══════════════════════════════════════════════════════════════════════════════
