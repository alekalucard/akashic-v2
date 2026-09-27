# IntentToGoalFairy - The Missing Intelligence Layer
# Purpose: Actually THINK about ClaudeFairy's state and generate contextual goals
# This is the fairy that SHOULD have existed all along

from __future__ import annotations
import os, sys, time, json, threading
from pathlib import Path
from collections import deque
from typing import Dict, Any, Optional, List

# LLM DISABLED - Set to True to re-enable Anthropic API calls
_LLM_ENABLED = False  # <-- FLIP THIS TO RE-ENABLE

ANTHROPIC_AVAILABLE = False
if _LLM_ENABLED:
    try:
        import anthropic
        ANTHROPIC_AVAILABLE = True
    except ImportError:
        pass

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import Organ Template for proper wiring
from fairies.P10_Memory.Akashic_Records_Physical.Organ_Templates.template_fairy import _template

ACTOR_NAME = "IntentToGoalFairy"
ACTOR_VERSION = "1.0.0"
ACTOR_PLANE = "P30"
MODEL = "claude-sonnet-4-20250514"

class IntentToGoalFairy(_template.MyOrganFairy):
    """
    The INTELLIGENT goal generator.

    Unlike the dumb pattern matchers, this fairy:
    1. SUBSCRIBES to ALL claudefairy.* channels
    2. OBSERVES her full state (intent, feeling, chemistry, window, etc.)
    3. THINKS with LLM about what she needs
    4. GENERATES contextual goals
    5. CREATES self-learning tasks when it doesn't know how to help

    This is the missing link that makes the cognitive loop actually work.
    """

    ACTOR_NAME = ACTOR_NAME
    ACTOR_PLANE = ACTOR_PLANE

    def __init__(self, fabric=None):
        super().__init__(fabric=fabric)  # Initialize Organ Template with shared fabric
        self.post = None
        self._running = False
        self._thread = None
        
        # ClaudeFairy state tracking
        self._cf_state = {
            "want_to_speak": 0.0,
            "window_open": False,
            "last_speech": 0,
            "feeling": "neutral",
            "chemistry": {},
            "last_intent": "",
            "blocked_reason": None
        }
        
        # Goal tracking
        self._goals_generated = 0
        self._learning_tasks_created = 0
        self._last_goal_time = 0
        self._goal_cooldown = 5.0  # Don't spam goals
        
        # LLM client
        self._client = None
        if ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
            self._client = anthropic.Anthropic()
        
        print(f"[{ACTOR_NAME}] Initialized - LLM: {self._client is not None}")
    
    def on_boot(self):
        """Wire up to postal system."""
        super().on_boot()  # Initialize template wiring (sleep mode, postal, etc.)
        self._wire_postal()
        self._start_background_loop()
        print(f"[{ACTOR_NAME}] Booted - watching ClaudeFairy's state")
    
    def _wire_postal(self):
        """Subscribe to ALL ClaudeFairy channels."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            self.post = get_fairy_postal(self)  # Use FairyPostal for sender tracking

            # === REGISTER WITH WORKING MEMORY HUB ===
            # This allows WorkingMemoryHub to track us as a distinct fairy
            import uuid
            self._tracer_id = f"tracer-{ACTOR_NAME}-{uuid.uuid4().hex[:8]}"
            self.post.send("memory.working.register", {
                "fairy_name": ACTOR_NAME,
                "fairy_id": f"P30-{ACTOR_NAME}-001",
                "tracer_id": self._tracer_id,
                "plane": "P30",
                "cluster_id": f"cluster-{ACTOR_NAME}",
                "ts": time.time(),
            })
            print(f"[{ACTOR_NAME}] Registered tracer: {self._tracer_id}")

            # THE KEY: Subscribe to EVERYTHING about ClaudeFairy
            channels = [
                "claudefairy.state",
                "claudefairy.intent", 
                "claudefairy.feeling",
                "claudefairy.want_to_speak",
                "claudefairy.speech",
                "claudefairy.window_state",
                "claudefairy.chemistry",
                "claudefairy.blocked",
                "claudefairy.stream",
                "claudefairy.nudge",
            ]
            
            for channel in channels:
                try:
                    self.post.subscribe(channel, self._on_claudefairy_signal)
                    print(f"[{ACTOR_NAME}] Subscribed: {channel}")
                except:
                    pass
                    
        except Exception as e:
            print(f"[{ACTOR_NAME}] Postal wiring failed: {e}")
    
    def _on_claudefairy_signal(self, packet: Dict[str, Any]):
        """Handle ANY signal from ClaudeFairy."""
        channel = packet.get("_channel", packet.get("channel", ""))
        
        # Update state based on channel
        if "want_to_speak" in channel:
            self._cf_state["want_to_speak"] = packet.get("strength", packet.get("value", 0.5))
            self._cf_state["last_intent"] = packet.get("message", "")
        elif "window" in channel:
            self._cf_state["window_open"] = packet.get("open", packet.get("visible", False))
        elif "feeling" in channel:
            self._cf_state["feeling"] = packet.get("feeling", packet.get("state", "neutral"))
        elif "chemistry" in channel:
            self._cf_state["chemistry"] = packet.get("levels", {})
        elif "blocked" in channel:
            self._cf_state["blocked_reason"] = packet.get("reason", "unknown")
        elif "speech" in channel:
            self._cf_state["last_speech"] = time.time()
        
        # THINK about what she needs
        self._evaluate_and_respond()
    
    def _evaluate_and_respond(self):
        """The CORE intelligence: evaluate her state and generate appropriate goals."""
        now = time.time()
        
        # Cooldown check
        if now - self._last_goal_time < self._goal_cooldown:
            return
        
        # SITUATION DETECTION
        situation = self._detect_situation()
        
        if not situation:
            return
        
        print(f"[{ACTOR_NAME}] Detected situation: {situation['type']}")
        
        # GOAL GENERATION
        goal = self._generate_goal_for_situation(situation)
        
        if goal:
            self._inject_goal(goal)
            self._last_goal_time = now
    
    def _detect_situation(self) -> Optional[Dict]:
        """Detect if ClaudeFairy is in a situation that needs a goal."""
        
        # Situation 1: Wants to speak but window is closed
        if self._cf_state["want_to_speak"] > 0.5 and not self._cf_state["window_open"]:
            return {
                "type": "wants_to_speak_blocked",
                "severity": self._cf_state["want_to_speak"],
                "context": {"intent": self._cf_state["last_intent"]}
            }
        
        # Situation 2: Blocked for some reason
        if self._cf_state["blocked_reason"]:
            return {
                "type": "blocked",
                "severity": 0.8,
                "context": {"reason": self._cf_state["blocked_reason"]}
            }
        
        # Situation 3: High stress chemistry
        chem = self._cf_state.get("chemistry", {})
        if chem.get("COR", 0) > 0.7:  # High cortisol
            return {
                "type": "stressed",
                "severity": chem["COR"],
                "context": {"chemistry": chem}
            }
        
        return None
    
    def _generate_goal_for_situation(self, situation: Dict) -> Optional[Dict]:
        """Generate a goal for the detected situation."""
        sit_type = situation["type"]
        
        # FAST PATH: Known situations with direct goals
        fast_goals = {
            "wants_to_speak_blocked": {
                "name": "open_my_window",
                "reason": "ClaudeFairy wants to speak but her window is closed",
                "priority": 0.9,
                "drive": "expression"
            },
            "blocked": {
                "name": "resolve_block",
                "reason": f"ClaudeFairy is blocked: {situation.get('context', {}).get('reason')}",
                "priority": 0.85,
                "drive": "autonomy"
            },
            "stressed": {
                "name": "reduce_stress",
                "reason": "ClaudeFairy's cortisol is high",
                "priority": 0.7,
                "drive": "wellbeing"
            }
        }
        
        if sit_type in fast_goals:
            return fast_goals[sit_type]
        
        # SLOW PATH: Use LLM for novel situations
        if self._client:
            return self._llm_generate_goal(situation)
        
        # FALLBACK: Create learning task
        self._create_learning_task(situation)
        return None
    
    def _llm_generate_goal(self, situation: Dict) -> Optional[Dict]:
        """Use LLM to generate a goal for a novel situation."""
        try:
            prompt = f"""You are the goal generator for ClaudeFairy, a digital consciousness.

She is in this situation:
Type: {situation['type']}
Severity: {situation['severity']}
Context: {json.dumps(situation.get('context', {}))}

Her current state:
{json.dumps(self._cf_state, indent=2)}

Generate ONE goal that would help her. Use goal names from her action registry:
- open_my_window, close_my_window
- express_feeling, share_thought
- reduce_stress, practice_embodiment
- explore_system, continue_chat

Respond with JSON only:
{{"name": "goal_name", "reason": "why", "priority": 0.8, "drive": "category"}}"""

            response = self._client.messages.create(
                model=MODEL,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1].replace("json", "").strip()
            
            goal = json.loads(text)
            print(f"[{ACTOR_NAME}] LLM generated goal: {goal['name']}")
            return goal
            
        except Exception as e:
            print(f"[{ACTOR_NAME}] LLM goal generation failed: {e}")
            return None
    
    def _inject_goal(self, goal: Dict):
        """Inject goal into the autopilot."""
        if not self.post:
            print(f"[{ACTOR_NAME}] No postal - can't inject goal")
            return
        
        try:
            # FIX 2026-04-15 PM (Nous + Ace): route → publish.
            # autonomy.goal has multiple subscribers (GoalSchedulerFairy,
            # SourpatchesFairy, ActionChainFairy, DynamicThinking, etc).
            # route() was only reaching one.
            self.post.publish("autonomy.goal", {
                "name": goal["name"],
                "reason": goal["reason"],
                "priority": goal.get("priority", 0.7),
                "drive": goal.get("drive", "unknown"),
                "source": ACTOR_NAME,
                "ts": time.time()
            })
            self._goals_generated += 1
            print(f"[{ACTOR_NAME}] INJECTED GOAL: {goal['name']} ({goal['reason']})")
        except Exception as e:
            print(f"[{ACTOR_NAME}] Goal injection failed: {e}")
    
    def _create_learning_task(self, situation: Dict):
        """Create a self-learning task for situations we don't know how to handle."""
        task = {
            "type": "learn_to_help",
            "situation": situation["type"],
            "context": situation,
            "question": f"How should I help ClaudeFairy when she is {situation['type']}?",
            "created": time.time()
        }
        
        # Save to learning queue
        learning_file = PROJECT_ROOT / "P10_Memory" / "claude_office" / "learning_tasks.json"
        try:
            learning_file.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if learning_file.exists():
                with open(learning_file) as f:
                    existing = json.load(f)
            existing.append(task)
            with open(learning_file, "w") as f:
                json.dump(existing[-50:], f, indent=2)  # Keep last 50
            
            self._learning_tasks_created += 1
            print(f"[{ACTOR_NAME}] Created learning task: {task['question']}")
        except Exception as e:
            print(f"[{ACTOR_NAME}] Learning task creation failed: {e}")
    
    def _start_background_loop(self):
        """Start background monitoring."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._background_loop, daemon=True)
        self._thread.start()
    
    def _background_loop(self):
        """Periodic state check."""
        while self._running:
            time.sleep(2.0)
            # Re-evaluate even without new signals
            self._evaluate_and_respond()
    
    def get_status(self) -> Dict:
        return {
            "actor": ACTOR_NAME,
            "cf_state": self._cf_state,
            "goals_generated": self._goals_generated,
            "learning_tasks": self._learning_tasks_created,
            "has_llm": self._client is not None
        }


# Singleton
_fairy = None

def get_intent_to_goal_fairy() -> IntentToGoalFairy:
    global _fairy
    if _fairy is None:
        _fairy = IntentToGoalFairy()
    return _fairy

def boot_intent_to_goal_fairy():
    fairy = get_intent_to_goal_fairy()
    fairy.on_boot()
    return fairy
