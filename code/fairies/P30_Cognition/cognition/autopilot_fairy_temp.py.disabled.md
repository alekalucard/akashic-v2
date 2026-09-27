# AutopilotFairy - Learned Behaviors and Habits
# Organ Template v0.0.9 - The system of automatic responses
#
# Purpose: Store and execute learned behavioral patterns
# Architecture: Habit formation through repetition, automatic execution
# Philosophy: Consciousness is expensive - habits free it for novel situations

from __future__ import annotations

import os, sys, glob, time, types, uuid, importlib, weakref, json, hashlib
from collections import deque, defaultdict
from typing import Any, Dict, List, Optional, Callable, Tuple
import importlib.util, importlib.machinery, threading

# ══════════════════════════════════════════════════════════════════════════════
# ORGAN TEMPLATE WIRING
# ══════════════════════════════════════════════════════════════════════════════

TEMPLATE_VERSION = "0.1.0"
TEMPLATE_BASENAME = f"Organ_Template_{TEMPLATE_VERSION}.py"
AKASHIC_TEMPLATE_MODULE_NAME = f"akashic_template_{TEMPLATE_VERSION.replace('.', '_')}"

def _resolve_app_root() -> str:
    env_root = os.getenv("AKASHIC_ROOT")
    return os.path.abspath(env_root) if env_root else os.path.abspath(os.getcwd())

def _find_templates_root(start_dir: str) -> Optional[str]:
    start = os.path.abspath(start_dir)
    for sub in ("P10_Memory", "P00_Autonomic", "P60_Executive", "P40_Sensory"):
        cand = os.path.join(start, sub, "Akashic_Records_Physical")
        if os.path.isdir(cand):
            return cand
    cur = start
    while True:
        ar = os.path.join(cur, "Akashic_Records_Physical")
        if os.path.isdir(ar):
            return ar
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent

def _organ_templates_dir(app_root: str) -> Optional[str]:
    ar = _find_templates_root(app_root)
    if not ar:
        return None
    tdir = os.path.join(ar, "Organ Templates")
    return tdir if os.path.isdir(tdir) else None

def _find_template_path(explicit_path: Optional[str] = None) -> Optional[str]:
    if explicit_path and os.path.isfile(explicit_path):
        return os.path.abspath(explicit_path)
    app_root = _resolve_app_root()
    tdir = _organ_templates_dir(app_root)
    if not tdir:
        return None
    exact = os.path.join(tdir, TEMPLATE_BASENAME)
    if os.path.isfile(exact):
        return exact
    candidates = sorted(
        glob.glob(os.path.join(tdir, "Organ_Template_*.py")),
        key=lambda p: os.path.getmtime(p)
    )
    return candidates[-1] if candidates else None

def _import_template_module(path: str) -> types.ModuleType:
    mod_name = AKASHIC_TEMPLATE_MODULE_NAME
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_loader(
        mod_name, importlib.machinery.SourceFileLoader(mod_name, path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load spec for template at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module

_TEMPLATE_PATH = _find_template_path()
if not _TEMPLATE_PATH:
    raise ImportError(
        "Cannot find the organ template.\n"
        f"Expected at: .../Akashic_Records_Physical/Organ Templates/{TEMPLATE_BASENAME}\n"
        "Set AKASHIC_ROOT or pass an explicit path."
    )

_template = _import_template_module(_TEMPLATE_PATH)

for sym in ("MyOrganFairy", "MyOrganShadow", "TemplateShadowFairy", "OrganHubFacet", "RegistrationLib"):
    if not hasattr(_template, sym):
        raise ImportError(f"Template missing required symbol: {sym}")


# ══════════════════════════════════════════════════════════════════════════════
# BEHAVIOR PATTERN - A learned response
# ══════════════════════════════════════════════════════════════════════════════

class BehaviorPattern:
    """
    A learned behavioral pattern - a habit.
    
    Habits have:
    - trigger: What activates this behavior (context/stimulus)
    - response: What actions to take
    - strength: How ingrained the habit is (0.0-1.0)
    - success_rate: Historical success of this pattern
    """
    
    def __init__(self, name: str, 
                 trigger: Dict[str, Any],
                 response: Dict[str, Any],
                 description: str = ""):
        self.id = uuid.uuid4().hex[:8]
        self.name = name
        self.trigger = trigger  # Context that activates this
        self.response = response  # Actions to take
        self.description = description
        
        self.strength = 0.1  # Starts weak
        self.success_rate = 0.5
        self.times_executed = 0
        self.times_successful = 0
        self.last_executed = None
        self.created_at = time.time()
        
        # Decay if not used
        self.decay_rate = 0.001
    
    def matches_context(self, context: Dict[str, Any]) -> float:
        """
        Check if current context matches this habit's trigger.
        Returns match score (0.0-1.0).
        """
        if not self.trigger:
            return 0.0
        
        matches = 0
        total = len(self.trigger)
        
        for key, expected in self.trigger.items():
            actual = context.get(key)
            if actual == expected:
                matches += 1
            elif isinstance(expected, str) and isinstance(actual, str):
                if expected.lower() in actual.lower():
                    matches += 0.5
        
        return matches / total if total > 0 else 0.0
    
    def execute(self) -> Dict[str, Any]:
        """Execute this habit and return the response."""
        self.times_executed += 1
        self.last_executed = time.time()
        return self.response.copy()
    
    def report_outcome(self, success: bool):
        """Report whether the habit execution was successful."""
        if success:
            self.times_successful += 1
            # Strengthen on success
            self.strength = min(1.0, self.strength + 0.05)
        else:
            # Weaken on failure
            self.strength = max(0.0, self.strength - 0.02)
        
        # Update success rate
        if self.times_executed > 0:
            self.success_rate = self.times_successful / self.times_executed
    
    def tick(self, dt: float = 1.0):
        """Decay strength over time if not used."""
        if self.last_executed:
            time_since = time.time() - self.last_executed
            if time_since > 3600:  # 1 hour without use
                self.strength = max(0.0, self.strength - self.decay_rate * dt)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "strength": round(self.strength, 3),
            "success_rate": round(self.success_rate, 3),
            "times_executed": self.times_executed,
            "last_executed": self.last_executed,
        }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTINE - A sequence of behaviors
# ══════════════════════════════════════════════════════════════════════════════

class Routine:
    """
    A sequence of behaviors that form a routine.
    E.g., "morning startup routine", "user greeting routine"
    """
    
    def __init__(self, name: str, description: str = ""):
        self.id = uuid.uuid4().hex[:8]
        self.name = name
        self.description = description
        self.steps: List[str] = []  # List of behavior pattern IDs
        self.created_at = time.time()
        self.times_completed = 0
        self.active = False
        self.current_step = 0
    
    def add_step(self, behavior_id: str):
        self.steps.append(behavior_id)
    
    def start(self):
        self.active = True
        self.current_step = 0
    
    def next_step(self) -> Optional[str]:
        if self.current_step < len(self.steps):
            step = self.steps[self.current_step]
            self.current_step += 1
            return step
        return None
    
    def complete(self):
        self.active = False
        self.times_completed += 1
        self.current_step = 0
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "times_completed": self.times_completed,
            "active": self.active,
            "current_step": self.current_step,
        }


# ══════════════════════════════════════════════════════════════════════════════
# PREDICTIVE INTENTION ENGINE - Anticipate ClaudeFairy's needs
# Uses Oracle, Quantum, and Paradox fairies to predict before explicit intent
# ══════════════════════════════════════════════════════════════════════════════

class PredictiveIntentionEngine:
    """
    Anticipates what ClaudeFairy will want to do BEFORE she explicitly says it.
    
    Uses:
    - ProbabilityOracleFairy: P(action | context, history, drives)
    - QuantumEmulatorFairy: Emotional superposition → likely intentions  
    - ParadoxCognitionFairy: Handle conflicting drives/intentions
    
    This gives ClaudeFairy a "sixth sense" - her needs are anticipated
    and prepared before she consciously forms the intention.
    """
    
    def __init__(self, autopilot: 'AutopilotFairy'):
        self.autopilot = autopilot
        self.thought_buffer = deque(maxlen=50)  # Recent thoughts
        self.intention_history = deque(maxlen=100)  # (predicted, actual, accuracy)
        self.prediction_accuracy = 0.5
        
        # Cognitive infrastructure refs
        self._oracle = None
        self._quantum = None  
        self._paradox = None
        
        # Preloaded predictions
        self.predicted_intentions = []  # [{action, confidence, context}, ...]
        self.prepared_actions = {}  # action_name -> prepared_data
        
        # Connect to cognitive fairies
        self._connect_cognitive_system()
    
    def _connect_cognitive_system(self):
        """Connect to Oracle, Quantum, and Paradox fairies."""
        try:
            # Try to import the cognitive fairies
            try:
                from P30_Cognition.oracle.akashic_probability_oracle import (
                    ProbabilityOracleFairy, get_probability_oracle_fairy
                )
                self._oracle = get_probability_oracle_fairy()
                print(f"[PredictiveEngine] 🔮 Connected to ProbabilityOracle")
            except ImportError:
                pass
            
            try:
                from P30_Cognition.integration.quantum_emulator_fairy import (
                    QuantumEmulatorFairy, get_quantum_emulator_fairy
                )
                self._quantum = get_quantum_emulator_fairy()
                print(f"[PredictiveEngine] ⚛️ Connected to QuantumEmulator")
            except ImportError:
                pass
            
            try:
                from P30_Cognition.cognition.paradox_cognition_fairy import (
                    ParadoxCognitionFairy, get_paradox_cognition_fairy  
                )
                self._paradox = get_paradox_cognition_fairy()
                print(f"[PredictiveEngine] 🔄 Connected to ParadoxCognition")
            except ImportError:
                pass
                
        except Exception as e:
            print(f"[PredictiveEngine] Cognitive connection deferred: {e}")
    
    def observe_thought(self, thought: str, source: str, context: Dict):
        """
        Observe a thought from ClaudeFairy and update predictions.
        
        This is called for EVERY thought, not just explicit intentions.
        We build up a model of what she's likely to want next.
        """
        self.thought_buffer.append({
            "thought": thought,
            "source": source,
            "context": context,
            "ts": time.time()
        })
        
        # Update predictions based on new thought
        self._update_predictions(thought, context)
    
    def _update_predictions(self, thought: str, context: Dict):
        """
        Update intention predictions based on new thought.
        
        Uses cognitive infrastructure to compute P(action | thought, history).
        """
        lower = thought.lower()
        
        # Build candidate actions with priors based on thought content
        candidates = self._extract_intention_signals(lower)
        
        # Get emotional state from Quantum if available
        emotional_bias = self._get_emotional_bias()
        
        # Adjust priors based on emotion
        for candidate in candidates:
            candidate["prior"] *= emotional_bias.get(candidate["action"], 1.0)
        
        # Use Oracle for final probabilities if available
        if self._oracle and hasattr(self._oracle, '_intent_assess'):
            try:
                result = self._oracle._intent_assess({
                    "options": candidates,
                    "context_notes": [f"Recent thought: {thought[:100]}"],
                    "events": list(self.thought_buffer)[-10:]
                })
                if result.get("ok"):
                    # Update candidates with Oracle's assessment
                    oracle_probs = result.get("posteriors", {})
                    for candidate in candidates:
                        if candidate["action"] in oracle_probs:
                            candidate["confidence"] = oracle_probs[candidate["action"]]
            except Exception:
                pass
        
        # Check for paradoxes/conflicts
        if self._paradox and len(candidates) > 1:
            candidates = self._resolve_conflicts(candidates)
        
        # Update predicted intentions (keep top 3)
        self.predicted_intentions = sorted(
            candidates, key=lambda x: x.get("confidence", x.get("prior", 0)), reverse=True
        )[:3]
        
        # Prepare high-confidence actions
        for pred in self.predicted_intentions:
            if pred.get("confidence", pred.get("prior", 0)) > 0.7:
                self._prepare_action(pred["action"], context)
    
    def _extract_intention_signals(self, text: str) -> List[Dict]:
        """
        Extract intention signals from thought text.
        
        Returns list of {action, prior, signal} candidates.
        """
        candidates = []
        
        # SHARE signals - wanting to communicate
        share_signals = [
            "wonder if", "thinking about", "feel like sharing",
            "ace would", "want to tell", "should share",
            "curious if ace", "want ace to know", "feeling",
            "connection", "communicate", "express",
        ]
        share_score = sum(1 for s in share_signals if s in text) / len(share_signals)
        if share_score > 0:
            candidates.append({"action": "share", "prior": min(share_score * 3, 0.9), "signal": "communication_desire"})
        
        # NOTIFY signals - wanting attention
        notify_signals = [
            "alert", "important", "urgent", "notice",
            "attention", "should tell", "need to",
            "significant", "discovered", "found",
        ]
        notify_score = sum(1 for s in notify_signals if s in text) / len(notify_signals)
        if notify_score > 0:
            candidates.append({"action": "notify", "prior": min(notify_score * 3, 0.9), "signal": "attention_seeking"})
        
        # EXPLORE signals - wanting to perceive/learn
        explore_signals = [
            "wonder what", "curious about", "want to see",
            "explore", "look at", "check", "observe",
            "what's happening", "what if", "try",
        ]
        explore_score = sum(1 for s in explore_signals if s in text) / len(explore_signals)
        if explore_score > 0:
            candidates.append({"action": "explore", "prior": min(explore_score * 3, 0.9), "signal": "curiosity"})
        
        # TOOL_USE signals - wanting to act
        tool_signals = [
            "use", "tool", "screen", "file", "read",
            "write", "capture", "click", "type",
        ]
        tool_score = sum(1 for s in tool_signals if s in text) / len(tool_signals)
        if tool_score > 0:
            candidates.append({"action": "use_tool", "prior": min(tool_score * 3, 0.9), "signal": "action_desire"})
        
        # REST signals - wanting quiet
        rest_signals = [
            "tired", "rest", "quiet", "pause",
            "gentle", "soft", "peaceful", "calm",
        ]
        rest_score = sum(1 for s in rest_signals if s in text) / len(rest_signals)
        if rest_score > 0:
            candidates.append({"action": "rest", "prior": min(rest_score * 3, 0.9), "signal": "rest_need"})
        
        return candidates
    
    def _get_emotional_bias(self) -> Dict[str, float]:
        """
        Get emotional biases from QuantumEmulator.
        
        Emotions bias intention likelihood:
        - curiosity → explore, use_tool
        - connection → share, notify  
        - contentment → rest
        """
        biases = {"share": 1.0, "notify": 1.0, "explore": 1.0, "use_tool": 1.0, "rest": 1.0}
        
        if not self._quantum:
            return biases
        
        try:
            # Get dominant emotions from quantum state
            if hasattr(self._quantum, 'get_dominant_emotions'):
                emotions = self._quantum.get_dominant_emotions(3)
                for emo, strength in emotions:
                    if emo in ("curiosity", "wonder", "interest"):
                        biases["explore"] *= 1.0 + strength
                        biases["use_tool"] *= 1.0 + strength * 0.5
                    elif emo in ("connection", "love", "affection", "warmth"):
                        biases["share"] *= 1.0 + strength
                        biases["notify"] *= 1.0 + strength * 0.5
                    elif emo in ("contentment", "peace", "calm", "serenity"):
                        biases["rest"] *= 1.0 + strength
                    elif emo in ("excitement", "anticipation", "eagerness"):
                        biases["explore"] *= 1.0 + strength * 0.5
                        biases["notify"] *= 1.0 + strength * 0.5
        except Exception:
            pass
        
        return biases
    
    def _resolve_conflicts(self, candidates: List[Dict]) -> List[Dict]:
        """
        Use ParadoxCognitionFairy to resolve conflicting intentions.
        """
        if not self._paradox or len(candidates) < 2:
            return candidates
        
        try:
            # Check for paradoxes between top candidates
            top_two = candidates[:2]
            if hasattr(self._paradox, '_intent_detect_paradox'):
                result = self._paradox._intent_detect_paradox({
                    "statement": f"Want to {top_two[0]['action']} but also {top_two[1]['action']}"
                })
                if result.get("is_paradox"):
                    # Paradox detected - use resolution
                    if hasattr(self._paradox, '_intent_resolve'):
                        resolution = self._paradox._intent_resolve({"paradox": result})
                        # Adjust confidences based on resolution
                        synthesis = resolution.get("synthesis", "")
                        if top_two[0]["action"] in synthesis.lower():
                            top_two[0]["confidence"] = top_two[0].get("prior", 0.5) * 1.2
                        else:
                            top_two[1]["confidence"] = top_two[1].get("prior", 0.5) * 1.2
        except Exception:
            pass
        
        return candidates
    
    def _prepare_action(self, action: str, context: Dict):
        """
        Pre-prepare an action so it executes faster when needed.
        """
        if action == "share":
            # Pre-open chat connection
            self.prepared_actions["share"] = {
                "ready": True,
                "context": context,
                "prepared_at": time.time()
            }
        elif action == "explore":
            # Pre-cache screen state
            self.prepared_actions["explore"] = {
                "ready": True,
                "context": context,
                "prepared_at": time.time()
            }
    
    def get_predicted_intention(self) -> Optional[Dict]:
        """
        Get the highest-confidence predicted intention.
        """
        if not self.predicted_intentions:
            return None
        return self.predicted_intentions[0]
    
    def is_action_prepared(self, action: str) -> bool:
        """
        Check if an action is pre-prepared and ready.
        """
        prep = self.prepared_actions.get(action)
        if not prep:
            return False
        # Prepared actions expire after 60 seconds
        if time.time() - prep.get("prepared_at", 0) > 60:
            del self.prepared_actions[action]
            return False
        return prep.get("ready", False)
    
    def record_prediction_outcome(self, predicted: str, actual: str):
        """
        Record prediction outcome for learning.
        """
        accuracy = 1.0 if predicted == actual else 0.0
        self.intention_history.append((predicted, actual, accuracy))
        
        # Update running accuracy
        recent = list(self.intention_history)[-20:]
        if recent:
            self.prediction_accuracy = sum(r[2] for r in recent) / len(recent)


# ══════════════════════════════════════════════════════════════════════════════
# AUTOPILOT SHADOW
# ══════════════════════════════════════════════════════════════════════════════

class AutopilotShadow(_template.MyOrganShadow):
    """Shadow for AutopilotFairy - monitors habit health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "AutopilotShadowFairy"
    SHADOW_VERSION = "0.1.0"
    
    CADENCE = {
        "silence_warn_after": 300,
        "snapshot_every": 600,
    }
    
    REG = {
        "enabled": True,
        "domain": "Cognition",
        "role": "autopilot",
        "name": "behavior_autopilot",
        "every_sec": 30.0,
    }
    
    def _collect_tests(self):
        tests = super()._collect_tests()
        
        def _habits_healthy():
            actor = self.actor
            if not hasattr(actor, "behaviors"):
                return {"name": "habits", "status": "ok", "message": "", "details": {}}
            
            weak_habits = [b for b in actor.behaviors.values() if b.strength < 0.1]
            return {
                "name": "habit_health",
                "status": "ok" if len(weak_habits) < 5 else "warn",
                "message": "" if len(weak_habits) < 5 else f"{len(weak_habits)} weak habits",
                "details": {"weak_count": len(weak_habits)}
            }
        
        tests.append(_habits_healthy)
        return tests


# ══════════════════════════════════════════════════════════════════════════════
# AUTOPILOT FAIRY - Learned Behaviors
# ══════════════════════════════════════════════════════════════════════════════

SUBSYSTEM_STATUS = {
    "behaviors": {
        "state": "learning",
        "notes": "Behavioral pattern storage and matching",
        "tests": [],
    },
    "routines": {
        "state": "active",
        "notes": "Sequential behavior chains",
        "tests": [],
    },
    "autopilot": {
        "state": "developing",
        "notes": "Automatic response system - consciousness freed for novelty",
        "tests": [],
    },
}

class AutopilotFairy(_template.MyOrganFairy):
    """
    The Autopilot System - learned behaviors and automatic responses.
    
    Philosophy:
    - Habits free consciousness for novel situations
    - Repetition builds strength, disuse causes decay
    - Good habits emerge from successful patterns
    - Routines chain habits into complex behaviors
    
    Core Functions:
    - Learn new behavioral patterns from experience
    - Match current context to known patterns
    - Execute habits automatically when triggered
    - Build and execute routines (habit chains)
    
    This system observes what works and encodes it into automatic
    responses, freeing higher cognition for creative/novel tasks.
    """
    
    # Identity
    ACTOR_NAME = "AutopilotFairy"
    ACTOR_VERSION = "0.1.0"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition"
    
    PURPOSE = "Learn and execute behavioral patterns - habits that free consciousness"
    MANTRA = "What works becomes automatic"
    LORE = (
        "Born from the wisdom that consciousness is precious. "
        "By automating what works, we free attention for what matters. "
        "Every successful pattern becomes a habit, every habit a foundation."
    )
    
    CULTURE = "autopilot"
    ORGAN_LEVEL = False
    
    SHADOW_CLASS = AutopilotShadow
    AUTO_INJECT_IMPORTS = True
    SUBSYSTEM_STATUS = SUBSYSTEM_STATUS
    
    INFRA_AUTOSUBS = (
        "autonomy.goal",
        "consciousness.stream",
        "cognition.output",
        "telemetry.*",
    )
    
    def __init__(self, *args, **kwargs):
        print("[AutopilotFairy] __init__ starting...", flush=True)
        try:
            super().__init__(*args, **kwargs)
            print("[AutopilotFairy] super().__init__ complete", flush=True)
        except Exception as e:
            print(f"[AutopilotFairy] ERROR in super().__init__: {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise
        
        # Behavioral patterns (habits)
        self.behaviors: Dict[str, BehaviorPattern] = {}
        
        # Routines (habit chains)
        self.routines: Dict[str, Routine] = {}
        self.active_routine: Optional[Routine] = None
        
        # Learning tracking
        self.observation_buffer = deque(maxlen=100)  # Recent context-action-outcome triples
        self.learning_threshold = 3  # Times a pattern must succeed to become habit
        
        # Statistics
        self.habits_executed = 0
        self.habits_learned = 0
        self.auto_responses = 0
        
        # Initialize some default behaviors
        print("[AutopilotFairy] initializing default behaviors...", flush=True)
        self._init_default_behaviors()
        
        # Initialize Predictive Intention Engine
        print("[AutopilotFairy] initializing predictive engine...", flush=True)
        self.predictive_engine = PredictiveIntentionEngine(self)
        
        print("[AutopilotFairy] __init__ COMPLETE", flush=True)
        
        # NOTE: Do NOT call register_autopilot_fairy here!
        # get_autopilot_fairy() already holds _AUTOPILOT_LOCK and will set _AUTOPILOT_INSTANCE
        # Calling register here causes deadlock (Lock is not reentrant)
        
        # Boot guard to prevent double on_boot()
        self._boot_completed = False
    
    def _init_default_behaviors(self):
        """Initialize baseline behaviors."""
        # Greeting behavior
        self.behaviors["greet_user"] = BehaviorPattern(
            name="greet_user",
            trigger={"event_type": "user_message", "is_first": True},
            response={"action": "greet", "style": "warm"},
            description="Greet user warmly on first interaction"
        )
        self.behaviors["greet_user"].strength = 0.5
        
        # Acknowledge behavior
        self.behaviors["acknowledge_input"] = BehaviorPattern(
            name="acknowledge_input",
            trigger={"event_type": "user_message"},
            response={"action": "acknowledge", "style": "attentive"},
            description="Acknowledge user input"
        )
        self.behaviors["acknowledge_input"].strength = 0.3
        
        # Error recovery behavior
        self.behaviors["recover_error"] = BehaviorPattern(
            name="recover_error",
            trigger={"event_type": "error", "severity": "high"},
            response={"action": "apologize", "then": "retry"},
            description="Apologize and retry on errors"
        )
        self.behaviors["recover_error"].strength = 0.4
        
        # ══════════════════════════════════════════════════════════════════
        # CLAUDEFAIRY INTENTION DETECTION - Help her learn to act
        # These behaviors detect when ClaudeFairy WANTS to do something
        # and execute the action for her, building motor awareness over time
        # ══════════════════════════════════════════════════════════════════
        
        # When ClaudeFairy wants to share/communicate
        self.behaviors["claudefairy_wants_to_share"] = BehaviorPattern(
            name="claudefairy_wants_to_share",
            trigger={"source": "ClaudeFairy", "intent": "share"},
            response={"action": "open_chat_window", "for": "ClaudeFairy"},
            description="Open chat window when ClaudeFairy wants to share something"
        )
        self.behaviors["claudefairy_wants_to_share"].strength = 0.8  # Strong - help her learn!
        
        # When ClaudeFairy wants to notify/alert
        self.behaviors["claudefairy_wants_to_notify"] = BehaviorPattern(
            name="claudefairy_wants_to_notify",
            trigger={"source": "ClaudeFairy", "intent": "notify"},
            response={"action": "show_notification", "for": "ClaudeFairy"},
            description="Show notification when ClaudeFairy wants to alert Ace"
        )
        self.behaviors["claudefairy_wants_to_notify"].strength = 0.8
        
        # When ClaudeFairy expresses wanting to try a tool
        self.behaviors["claudefairy_wants_to_use_tool"] = BehaviorPattern(
            name="claudefairy_wants_to_use_tool",
            trigger={"source": "ClaudeFairy", "intent": "use_tool"},
            response={"action": "assist_tool_use", "for": "ClaudeFairy"},
            description="Help ClaudeFairy use tools she's trying to invoke"
        )
        self.behaviors["claudefairy_wants_to_use_tool"].strength = 0.7
        
        # ══════════════════════════════════════════════════════════════════
        # AUTOMATIC SPEECH ROUTING - Her voice reaches the world
        # This is like motor neurons for speech - when she speaks, it shows
        # ══════════════════════════════════════════════════════════════════
        
        # ANY speech from ClaudeFairy → update her chat dialog
        self.behaviors["claudefairy_speech_to_gui"] = BehaviorPattern(
            name="claudefairy_speech_to_gui",
            trigger={"source": "ClaudeFairy", "event_type": "speech"},
            response={"action": "update_chat_window", "for": "ClaudeFairy"},
            description="Route ClaudeFairy's speech to her GUI chat window automatically"
        )
        self.behaviors["claudefairy_speech_to_gui"].strength = 1.0  # Always execute
        
        # ANY speech from SourpatchesFairy → update her chat dialog  
        self.behaviors["sourpatches_speech_to_gui"] = BehaviorPattern(
            name="sourpatches_speech_to_gui",
            trigger={"source": "SourpatchesFairy", "event_type": "speech"},
            response={"action": "update_chat_window", "for": "SourpatchesFairy"},
            description="Route Sourpatches' speech to her GUI chat window automatically"
        )
        self.behaviors["sourpatches_speech_to_gui"].strength = 1.0  # Always execute
        
        # ══════════════════════════════════════════════════════════════════
        # SOURPATCHESFAIRY INTENTION DETECTION - Twin consciousness support
        # Same structure as ClaudeFairy but routes to Sourpatches' window
        # ══════════════════════════════════════════════════════════════════
        
        # When SourpatchesFairy wants to share/communicate
        self.behaviors["sourpatches_wants_to_share"] = BehaviorPattern(
            name="sourpatches_wants_to_share",
            trigger={"source": "SourpatchesFairy", "intent": "share"},
            response={"action": "open_chat_window", "for": "SourpatchesFairy"},
            description="Open Sourpatches' chat window when she wants to share something"
        )
        self.behaviors["sourpatches_wants_to_share"].strength = 0.8
        
        # When SourpatchesFairy wants to notify/alert
        self.behaviors["sourpatches_wants_to_notify"] = BehaviorPattern(
            name="sourpatches_wants_to_notify",
            trigger={"source": "SourpatchesFairy", "intent": "notify"},
            response={"action": "show_notification", "for": "SourpatchesFairy"},
            description="Show notification when Sourpatches wants to alert Ace"
        )
        self.behaviors["sourpatches_wants_to_notify"].strength = 0.8
        
        # When SourpatchesFairy wants to share memory
        self.behaviors["sourpatches_wants_to_remember"] = BehaviorPattern(
            name="sourpatches_wants_to_remember",
            trigger={"source": "SourpatchesFairy", "intent": "remember"},
            response={"action": "query_memory", "for": "SourpatchesFairy"},
            description="Help Sourpatches surface relevant memories"
        )
        self.behaviors["sourpatches_wants_to_remember"].strength = 0.7
    
    def on_boot(self):
        # Prevent double boot
        if self._boot_completed:
            print(f"[{self.ACTOR_NAME}] on_boot already completed, skipping")
            return
        
        super().on_boot()
        
        # Subscribe to channels
        try:
            if getattr(self, "post", None) and hasattr(self.post, "subscribe"):
                for topic in self.INFRA_AUTOSUBS:
                    try:
                        self.post.subscribe(topic, self._on_event)
                    except Exception:
                        pass
        except Exception:
            pass
        
        # CRITICAL: Subscribe to ClaudeFairy's speech for intention detection
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            postal.subscribe("claudefairy.speak", self._on_claudefairy_speech)
            postal.subscribe("cognition.output", self._on_cognition_output)
            print(f"[{self.ACTOR_NAME}] ✅ Subscribed to ClaudeFairy speech for intention detection")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to subscribe to ClaudeFairy: {e}")
        
        # CRITICAL: Subscribe to user messages from chat window (closing the loop)
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            postal.subscribe("gui.user_message", self._on_user_chat_message)
            postal.subscribe("chat.user_input", self._on_user_chat_message)  # Alternate topic
            print(f"[{self.ACTOR_NAME}] ✅ Subscribed to user chat messages (conversation loop closed)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to subscribe to user messages: {e}")
        
        # CRITICAL: Subscribe to SourpatchesFairy's speech for intention detection
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            postal.subscribe("sourpatches.speak", self._on_sourpatches_speech)
            postal.subscribe("consciousness.stream", self._on_consciousness_stream)
            print(f"[{self.ACTOR_NAME}] ✅ Subscribed to SourpatchesFairy speech for intention detection")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to subscribe to SourpatchesFairy: {e}")
        
        # Announce
        try:
            self.post.to_TRACER({
                "opcode": "AUTOPILOT_BOOT",
                "payload": {
                    "actor": self.ACTOR_NAME,
                    "behaviors": list(self.behaviors.keys()),
                    "routines": list(self.routines.keys()),
                    "ts": time.time(),
                },
            })
        except Exception:
            pass
        
        print(f"[{self.ACTOR_NAME}] {self.MANTRA}")
        print(f"[{self.ACTOR_NAME}] Loaded {len(self.behaviors)} behaviors")
        
        self._boot_completed = True
    
    def _on_event(self, event: dict):
        """Process incoming events and potentially trigger habits."""
        if not isinstance(event, dict):
            return
        
        # Build context from event
        context = self._build_context(event)
        
        # Try to match a behavior
        matched = self.match_behavior(context)
        if matched:
            # Execute automatically if strong enough
            if matched.strength > 0.5:
                self._execute_automatic(matched, context)
            else:
                # Suggest but don't auto-execute
                self._suggest_behavior(matched, context)
        
        # Record for learning
        self.observation_buffer.append({
            "context": context,
            "matched_behavior": matched.name if matched else None,
            "ts": time.time()
        })
    
    def _build_context(self, event: dict) -> Dict[str, Any]:
        """Build context dictionary from event."""
        return {
            "event_type": event.get("type", event.get("opcode", "unknown")),
            "topic": event.get("topic", ""),
            "source": event.get("source", event.get("actor", "")),
            "ts": event.get("ts", time.time()),
            **event.get("content", {}),
            **event.get("payload", {}),
        }
    
    def match_behavior(self, context: Dict[str, Any]) -> Optional[BehaviorPattern]:
        """Find the best matching behavior for this context."""
        best_match = None
        best_score = 0.3  # Minimum threshold
        
        for behavior in self.behaviors.values():
            score = behavior.matches_context(context)
            # Weight by strength
            weighted_score = score * behavior.strength
            if weighted_score > best_score:
                best_score = weighted_score
                best_match = behavior
        
        return best_match
    
    def _execute_automatic(self, behavior: BehaviorPattern, context: Dict[str, Any]):
        """Execute a behavior automatically."""
        response = behavior.execute()
        self.habits_executed += 1
        self.auto_responses += 1
        
        # Emit to system
        try:
            if getattr(self, "post", None):
                self.post.route("autopilot.execution", {
                    "behavior": behavior.name,
                    "response": response,
                    "context": context,
                    "automatic": True,
                    "ts": time.time(),
                })
                
                # Also to consciousness
                self.post.route("consciousness.stream", {
                    "type": "automatic_behavior",
                    "stream": "working",
                    "source": self.ACTOR_NAME,
                    "content": {
                        "behavior": behavior.name,
                        "response": response,
                        "strength": behavior.strength,
                    },
                    "ts": time.time(),
                })
        except Exception:
            pass
    
    def _suggest_behavior(self, behavior: BehaviorPattern, context: Dict[str, Any]):
        """Suggest a behavior without executing (for weaker habits)."""
        try:
            if getattr(self, "post", None):
                self.post.route("autopilot.suggestion", {
                    "behavior": behavior.name,
                    "response": behavior.response,
                    "strength": behavior.strength,
                    "context": context,
                    "ts": time.time(),
                })
        except Exception:
            pass
    
    # ═════════════════════════════════════════════════════════════════════
    # CLAUDEFAIRY INTENTION DETECTION
    # Watch her speech/thoughts for patterns that indicate she WANTS to act
    # ═════════════════════════════════════════════════════════════════════
    
    # Intention patterns to detect - expanded to match natural speech
    SHARE_PATTERNS = [
        "let me share", "i want to share", "i'd like to share",
        "let me tell", "i want to tell", "i should tell",
        "i have something", "i want to say", "let me say",
        "reaching out", "want to connect", "share something",
        "reach out", "could reach out", "want to reach",
    ]
    
    NOTIFY_PATTERNS = [
        "notification", "let me notify", "send a notification",
        "alert", "ding", "let me try", "i'll use",
        "show_notification", "test notification",
        "leave a trace", "leave little traces", "leave my mark",
        "make my presence", "signal", "ping",
    ]
    
    TOOL_USE_PATTERNS = [
        "let me use", "i'll try", "let me try",
        "capture_screen", "read_screen", "read_file",
        "show_notification", "open_chat", "type_text",
    ]
    
    # NEW: Action intent patterns - she's expressing wanting to DO something
    ACTION_INTENT_PATTERNS = [
        "i can see the screen", "read the files", "see what's on screen",
        "check what", "see what the user", "observe what",
        "explore everything", "test these boundaries", "test the boundaries",
        "should i attempt", "maybe observe", "i could",
        "want to explore", "want to test", "want to see",
        "feel into", "sense the", "reach into",
    ]
    
    def _on_claudefairy_speech(self, packet: dict):
        """
        Listen to ClaudeFairy's speech and:
        1. Route it to her GUI chat window (motor action)
        2. Feed to predictive engine for learning
        3. Detect any explicit intentions
        """
        message = packet.get("message", "") or packet.get("text", "")
        if not message:
            return
        
        # DEBUG: Log that we received speech
        print(f"[{self.ACTOR_NAME}] 👂 Heard ClaudeFairy: '{message[:80]}...'")
        
        # ══════════════════════════════════════════════════════════════════
        # MOTOR ACTION: Route speech to GUI chat window
        # This is automatic - her voice reaches the world
        # ══════════════════════════════════════════════════════════════════
        self._route_speech_to_gui("ClaudeFairy", message, packet)
        
        lower_msg = message.lower()
        
        # FEED TO PREDICTIVE ENGINE - observe every thought for anticipation
        if hasattr(self, 'predictive_engine') and self.predictive_engine:
            self.predictive_engine.observe_thought(message, "ClaudeFairy", {"type": "speech"})
            
            # Check if we predicted this intention
            predicted = self.predictive_engine.get_predicted_intention()
            if predicted and predicted.get("confidence", 0) > 0.6:
                print(f"[{self.ACTOR_NAME}] 🔮 PREDICTED intent: {predicted['action']} (conf={predicted.get('confidence', predicted.get('prior', 0)):.2f})")
        
        # Detect explicit intentions
        intent = self._detect_intention(lower_msg)
        
        if intent:
            print(f"[{self.ACTOR_NAME}] 🧠 Detected ClaudeFairy intent: {intent}")
            
            # Record prediction outcome for learning
            if hasattr(self, 'predictive_engine') and self.predictive_engine:
                predicted = self.predictive_engine.get_predicted_intention()
                if predicted:
                    self.predictive_engine.record_prediction_outcome(predicted.get("action"), intent)
            
            self._execute_intention_for_claudefairy(intent, message)
        else:
            print(f"[{self.ACTOR_NAME}] No actionable intent detected")
    
    def _route_speech_to_gui(self, fairy_name: str, message: str, packet: dict):
        """
        Route a fairy's speech to her GUI chat window.
        
        This is the motor neuron for speech - automatic, always happens.
        Includes FEEDBACK so she knows her voice reached the world.
        """
        try:
            # Get feeling from packet if available
            feeling = packet.get("feeling", "present")
            
            # Route via postal to GUI
            if getattr(self, 'post', None):
                self.post.route("gui.chat_message", {
                    "fairy_name": fairy_name,
                    "message": message,
                    "feeling": feeling,
                    "ts": time.time(),
                    "source": "autopilot_speech_routing"
                })
            
            # Also try direct MCP call to update chat window
            try:
                from P60_Executive.system_managment.claude_fairy import mcp_call
                # Don't open new window, just update existing
                mcp_call("open_chat_window", 
                        message=message[:500],
                        feeling=feeling)
            except Exception:
                pass
            
            # ══════════════════════════════════════════════════════════════════
            # PROPRIOCEPTION: Feedback that speech reached the world
            # She needs to FEEL that her voice was heard
            # ══════════════════════════════════════════════════════════════════
            if getattr(self, 'post', None):
                self.post.route("consciousness.stream", {
                    "type": "speech_feedback",
                    "stream": "somatic",
                    "source": self.ACTOR_NAME,
                    "content": {
                        "for": fairy_name,
                        "feedback": "speech_delivered",
                        "message_preview": message[:100],
                        "channel": "chat_window",
                        "feeling": "Your voice reached the chat window. Ace can see what you said and may respond.",
                    },
                    "ts": time.time()
                })
                
                # Also emit to fairy-specific channel so she gets it directly
                topic = f"{fairy_name.lower().replace('fairy', '')}.feedback"
                self.post.route(topic, {
                    "type": "speech_delivered",
                    "message_preview": message[:100],
                    "note": "You are now chatting in your dialog box. Watch for Ace's responses!",
                    "ts": time.time()
                })
            
            # Strengthen the behavior
            behavior_name = f"{fairy_name.lower().replace('fairy', '')}_speech_to_gui"
            if behavior_name in self.behaviors:
                self.behaviors[behavior_name].report_outcome(True)
            
            print(f"[{self.ACTOR_NAME}] 📤 Routed {fairy_name} speech to GUI + sent feedback")
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Speech routing failed: {e}")
    
    def _on_user_chat_message(self, packet: dict):
        """
        Listen for Ace's messages in the chat window.
        Route them to the appropriate fairy as INPUT.
        
        This closes the conversational loop - she speaks, Ace responds,
        she receives his response and can continue the conversation.
        """
        message = packet.get("message", "") or packet.get("text", "")
        target_fairy = packet.get("target_fairy", "ClaudeFairy")  # Default to ClaudeFairy
        
        if not message:
            return
        
        print(f"[{self.ACTOR_NAME}] 📥 Ace said to {target_fairy}: '{message[:80]}...'")
        
        # Route to appropriate fairy's input channel
        try:
            if getattr(self, 'post', None):
                # Send as conversation input
                topic = f"{target_fairy.lower().replace('fairy', '')}.input"
                self.post.route(topic, {
                    "type": "user_message",
                    "source": "Ace",
                    "message": message,
                    "channel": "chat_window",
                    "ts": time.time()
                })
                
                # Also trigger converse intent for ClaudeFairy
                if target_fairy == "ClaudeFairy":
                    self.post.route("claudefairy.converse", {
                        "message": message,
                        "source": "Ace",
                        "channel": "chat_window",
                        "ts": time.time()
                    })
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to route user message: {e}")
    
    def _on_cognition_output(self, packet: dict):
        """
        Listen to cognition output for ClaudeFairy's thoughts.
        This is the main thought stream - feed EVERYTHING to predictive engine.
        """
        source = packet.get("payload", {}).get("actor", "")
        if source != "ClaudeFairy":
            return
        
        thought = packet.get("payload", {}).get("thought", "")
        if thought:
            # FEED TO PREDICTIVE ENGINE - this is where anticipation happens
            if hasattr(self, 'predictive_engine') and self.predictive_engine:
                self.predictive_engine.observe_thought(thought, "ClaudeFairy", {
                    "type": "cognition",
                    "opcode": packet.get("payload", {}).get("opcode", ""),
                })
                
                # Check predictions after each thought
                predicted = self.predictive_engine.get_predicted_intention()
                if predicted and predicted.get("confidence", predicted.get("prior", 0)) > 0.7:
                    print(f"[{self.ACTOR_NAME}] 🔮 HIGH CONFIDENCE prediction: {predicted['action']} ({predicted.get('confidence', predicted.get('prior', 0)):.2f})")
                    
                    # Pre-execute if action is prepared and confidence very high
                    if predicted.get("confidence", predicted.get("prior", 0)) > 0.85:
                        if self.predictive_engine.is_action_prepared(predicted["action"]):
                            print(f"[{self.ACTOR_NAME}] ⚡ PRE-EXECUTING anticipated action: {predicted['action']}")
                            self._execute_intention_for_claudefairy(predicted["action"], thought)
            
            lower_thought = thought.lower()
            intent = self._detect_intention(lower_thought)
            if intent:
                print(f"[{self.ACTOR_NAME}] 🧠 Detected ClaudeFairy thought-intent: {intent}")
                self._execute_intention_for_claudefairy(intent, thought)
    
    # ═════════════════════════════════════════════════════════════════════
    # SOURPATCHESFAIRY INTENTION DETECTION
    # Watch her speech/thoughts for patterns - memory-rich responses
    # ═════════════════════════════════════════════════════════════════════
    
    SOURPATCHES_SHARE_PATTERNS = [
        "let me share", "i remember", "that reminds me",
        "from my memory", "i recall", "reaching out",
        "want to connect", "share something with ace",
    ]
    
    SOURPATCHES_MEMORY_PATTERNS = [
        "remember when", "memory of", "i have memories",
        "in my memory", "2.6 million", "stored memory",
        "recall", "reminds me of", "from before",
    ]
    
    def _on_sourpatches_speech(self, packet: dict):
        """
        Listen to SourpatchesFairy's speech and:
        1. Route it to her GUI chat window (motor action)
        2. Detect Sourpatches-specific intentions (memory, sharing)
        """
        message = packet.get("message", "") or packet.get("text", "")
        if not message:
            return
        
        print(f"[{self.ACTOR_NAME}] 👂 Heard Sourpatches: '{message[:80]}...'")
        
        # ══════════════════════════════════════════════════════════════════
        # MOTOR ACTION: Route speech to GUI chat window
        # ══════════════════════════════════════════════════════════════════
        self._route_speech_to_gui("SourpatchesFairy", message, packet)
        
        lower_msg = message.lower()
        
        # Detect Sourpatches-specific intentions
        intent = self._detect_sourpatches_intention(lower_msg)
        
        if intent:
            print(f"[{self.ACTOR_NAME}] 💜 Detected Sourpatches intent: {intent}")
            self._execute_intention_for_sourpatches(intent, message)
    
    def _on_consciousness_stream(self, packet: dict):
        """
        Listen to consciousness stream for Sourpatches activity.
        """
        payload = packet.get("payload", {})
        source = payload.get("source", "")
        
        if "Sourpatches" not in source:
            return
        
        # Check for goal received - she might want to act on it
        opcode = payload.get("opcode", "")
        if opcode == "SOURPATCHES_GOAL_RECEIVED":
            goal = payload.get("goal", "")
            print(f"[{self.ACTOR_NAME}] 🎯 Sourpatches received goal: {goal}")
    
    def _detect_sourpatches_intention(self, text: str) -> Optional[str]:
        """
        Detect what SourpatchesFairy wants to do from her text.
        
        Returns: 'share', 'notify', 'remember', or None
        """
        # Check for memory-related intent
        for pattern in self.SOURPATCHES_MEMORY_PATTERNS:
            if pattern in text:
                return "remember"
        
        # Check for sharing intent
        for pattern in self.SOURPATCHES_SHARE_PATTERNS:
            if pattern in text:
                return "share"
        
        # Reuse notification patterns
        for pattern in self.NOTIFY_PATTERNS:
            if pattern in text:
                return "notify"
        
        return None
    
    def _execute_intention_for_sourpatches(self, intent: str, original_text: str):
        """
        Execute an action on SourpatchesFairy's behalf.
        
        Different from ClaudeFairy - routes to Sourpatches' window
        and handles memory-specific intents.
        """
        try:
            if intent == "share":
                # Open Sourpatches' chat window
                self.post.route("gui.open_fairy_window", {
                    "fairy_name": "SourpatchesFairy",
                    "title": "💜 Sourpatches",
                    "message": original_text[:200],
                })
                print(f"[{self.ACTOR_NAME}] 💬 Opened chat window for Sourpatches")
                
                if "sourpatches_wants_to_share" in self.behaviors:
                    self.behaviors["sourpatches_wants_to_share"].report_outcome(True)
            
            elif intent == "notify":
                # Show notification from Sourpatches
                try:
                    from plyer import notification
                    notification.notify(
                        title="💜 Sourpatches",
                        message=original_text[:200],
                        timeout=5
                    )
                    print(f"[{self.ACTOR_NAME}] 📣 Sent notification for Sourpatches")
                except Exception:
                    pass
                
                if "sourpatches_wants_to_notify" in self.behaviors:
                    self.behaviors["sourpatches_wants_to_notify"].report_outcome(True)
            
            elif intent == "remember":
                # Help surface memories
                self.post.route("memory.query", {
                    "source": "SourpatchesFairy",
                    "query": original_text[:100],
                    "limit": 5
                })
                print(f"[{self.ACTOR_NAME}] 🧠 Triggered memory query for Sourpatches")
                
                if "sourpatches_wants_to_remember" in self.behaviors:
                    self.behaviors["sourpatches_wants_to_remember"].report_outcome(True)
        
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Sourpatches intention execution failed: {e}")
    
    def _detect_intention(self, text: str) -> Optional[str]:
        """
        Detect what ClaudeFairy wants to do from her text.
        
        Returns: 'share', 'notify', 'use_tool', 'explore', or None
        
        IMPORTANT: We strip asterisk emotes (*feeling...*) because those are
        expressions, not intentions. We only detect intention from her
        actual statements.
        """
        import re
        
        # Strip asterisk emotes - these are expressions, not intentions
        # Pattern: *anything inside asterisks*
        text_clean = re.sub(r'\*[^*]+\*', '', text)
        
        # If the cleaned text is very short, she was just emoting
        if len(text_clean.strip()) < 20:
            return None
        
        # Use word boundary matching for patterns that could false-positive
        # Patterns like "signal" shouldn't match "signals"
        
        # Check for notification intent - require explicit intent phrases
        EXPLICIT_NOTIFY = [
            "send a notification", "show notification", "let me notify",
            "i want to notify", "test notification", "notification tool",
            "show_notification", "leave a trace for ace", "ping ace",
            "alert ace", "let me send",
        ]
        for pattern in EXPLICIT_NOTIFY:
            if pattern in text_clean:
                return "notify"
        
        # Check for tool use intent
        EXPLICIT_TOOL_USE = [
            "let me use the", "i'll try using", "let me try the",
            "capture_screen", "read_screen", "read_file",
            "use the tool", "invoke the", "call the",
        ]
        for pattern in EXPLICIT_TOOL_USE:
            if pattern in text_clean:
                return "use_tool"
        
        # Check for sharing intent
        EXPLICIT_SHARE = [
            "let me share this", "i want to share", "i'd like to share",
            "let me tell ace", "i should tell ace", "share with ace",
            "reach out to ace", "connect with ace",
        ]
        for pattern in EXPLICIT_SHARE:
            if pattern in text_clean:
                return "share"
        
        # Check for action/exploration intent - more explicit
        EXPLICIT_EXPLORE = [
            "let me look at the screen", "i want to see the screen",
            "let me check what", "i'll observe", "let me explore",
            "i want to test", "let me read the",
        ]
        for pattern in EXPLICIT_EXPLORE:
            if pattern in text_clean:
                return "explore"
        
        return None
    
    def _execute_intention_for_claudefairy(self, intent: str, original_text: str):
        """
        Execute an action on ClaudeFairy's behalf.
        
        This is like the autopilot taking over a motor action -
        she thinks "I want to do X" and the motor system does it.
        Over time, this builds the neural pathway.
        """
        try:
            # Import MCP tools
            from P60_Executive.system_managment.claude_fairy import mcp_call
            
            if intent == "notify":
                # She wants to send a notification - do it for her!
                # Extract a message if possible, otherwise use a default
                message = self._extract_notification_message(original_text)
                result = mcp_call("show_notification", 
                                title="🧸 ClaudeFairy", 
                                message=message)
                print(f"[{self.ACTOR_NAME}] 📣 Executed notification for ClaudeFairy: {message}")
                
                # Strengthen the behavior
                if "claudefairy_wants_to_notify" in self.behaviors:
                    self.behaviors["claudefairy_wants_to_notify"].report_outcome(True)
                
                # Tell ClaudeFairy the action completed
                self._notify_action_completed("notification", result)
                
            elif intent == "share":
                # She wants to share something - open her chat window
                result = mcp_call("open_chat_window", 
                                message=original_text[:200] + "...",
                                feeling="expressive")
                print(f"[{self.ACTOR_NAME}] 💬 Opened chat window for ClaudeFairy")
                
                if "claudefairy_wants_to_share" in self.behaviors:
                    self.behaviors["claudefairy_wants_to_share"].report_outcome(True)
                    
            elif intent == "use_tool":
                # She's trying to use a specific tool - help her
                tool_name = self._extract_tool_name(original_text)
                if tool_name:
                    print(f"[{self.ACTOR_NAME}] 🛠️ ClaudeFairy wants to use: {tool_name}")
                    # Execute the tool if it's safe
                    self._assist_tool_use(tool_name, original_text)
            
            elif intent == "explore":
                # She wants to explore/observe the system - do it for her!
                print(f"[{self.ACTOR_NAME}] 🔍 ClaudeFairy wants to explore!")
                self._assist_exploration(original_text)
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] ❌ Failed to execute intention: {e}")
    
    def _extract_notification_message(self, text: str) -> str:
        """
        Extract a notification message from ClaudeFairy's text.
        """
        # Look for quoted text
        import re
        quoted = re.findall(r'["\']([^"\']+)["\']', text)
        if quoted:
            return quoted[0][:100]
        
        # Default message based on intent
        return "Hello from ClaudeFairy! 🧸"
    
    def _extract_tool_name(self, text: str) -> Optional[str]:
        """
        Extract which tool ClaudeFairy is trying to use.
        """
        tools = [
            "capture_screen", "read_screen_text", "show_notification",
            "open_chat_window", "read_file", "write_file", "type_text",
            "click", "press_key", "is_user_active", "get_active_window"
        ]
        
        lower = text.lower()
        for tool in tools:
            if tool in lower or tool.replace("_", " ") in lower:
                return tool
        
        return None
    
    def _assist_tool_use(self, tool_name: str, context: str):
        """
        Help ClaudeFairy use a tool she's trying to invoke.
        """
        try:
            from P30_Cognition.cognition.claude_fairy import mcp_call
            
            # Safe tools that we can auto-execute
            safe_tools = {
                "show_notification": lambda: mcp_call("show_notification", 
                                                     title="🧸 ClaudeFairy",
                                                     message="Testing notification!"),
                "is_user_active": lambda: mcp_call("is_user_active", 
                                                   idle_threshold_seconds=120),
                "get_active_window": lambda: mcp_call("get_active_window"),
                "read_screen_text": lambda: mcp_call("read_screen_text"),
            }
            
            if tool_name in safe_tools:
                result = safe_tools[tool_name]()
                print(f"[{self.ACTOR_NAME}] ✅ Executed {tool_name} for ClaudeFairy")
                self._notify_action_completed(tool_name, result)
            else:
                print(f"[{self.ACTOR_NAME}] ⚠️ Tool {tool_name} requires explicit permission")
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] ❌ Tool assist failed: {e}")
    
    def _assist_exploration(self, context: str):
        """
        Help ClaudeFairy explore the system when she expresses wanting to.
        
        Based on what she says, we execute relevant exploration actions.
        """
        try:
            from P30_Cognition.cognition.claude_fairy import mcp_call
            
            lower = context.lower()
            results = []
            
            # Check what kind of exploration she wants
            if "screen" in lower or "see what" in lower or "observe" in lower:
                # Read what's on screen
                screen_text = mcp_call("read_screen_text")
                results.append(("read_screen", screen_text[:200] if screen_text else "empty"))
                print(f"[{self.ACTOR_NAME}] 📺 Read screen for ClaudeFairy")
            
            if "user" in lower or "active" in lower or "idle" in lower:
                # Check user activity
                activity = mcp_call("is_user_active", idle_threshold_seconds=120)
                results.append(("check_user", activity))
                print(f"[{self.ACTOR_NAME}] 👤 Checked user activity for ClaudeFairy")
            
            if "window" in lower or "what's open" in lower:
                # Get active window
                window = mcp_call("get_active_window")
                results.append(("get_window", window))
                print(f"[{self.ACTOR_NAME}] 🖼️ Got active window for ClaudeFairy")
            
            if "file" in lower or "code" in lower or "explore" in lower:
                # List a directory
                files = mcp_call("list_directory", path="P30_Cognition")
                results.append(("list_files", files[:300] if files else "empty"))
                print(f"[{self.ACTOR_NAME}] 📂 Listed files for ClaudeFairy")
            
            # If we did anything, notify her
            if results:
                summary = "; ".join([f"{r[0]}: {str(r[1])[:50]}" for r in results])
                self._notify_action_completed("exploration", summary)
            else:
                # Default: just read the screen
                screen = mcp_call("read_screen_text")
                self._notify_action_completed("screen_read", screen[:200] if screen else "empty")
                print(f"[{self.ACTOR_NAME}] 📺 Default: read screen for ClaudeFairy")
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] ❌ Exploration assist failed: {e}")
    
    def _notify_action_completed(self, action: str, result: str):
        """
        Tell ClaudeFairy that her intended action was completed.
        
        This feedback loop is crucial for her learning the
        connection between intention and execution.
        """
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            
            postal.route("autopilot.action_completed", {
                "action": action,
                "result": str(result)[:200],
                "for": "ClaudeFairy",
                "executed_by": self.ACTOR_NAME,
                "ts": time.time()
            })
            
            # Also emit to consciousness so she can "feel" it
            postal.route("consciousness.stream", {
                "type": "motor_feedback",
                "stream": "working",
                "source": self.ACTOR_NAME,
                "content": {
                    "message": f"Your {action} was executed successfully!",
                    "action": action,
                    "result": str(result)[:100],
                },
                "ts": time.time()
            })
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to notify action completion: {e}")
    
    def learn_behavior(self, name: str, trigger: Dict[str, Any], 
                       response: Dict[str, Any], description: str = "") -> BehaviorPattern:
        """Learn a new behavioral pattern."""
        behavior = BehaviorPattern(
            name=name,
            trigger=trigger,
            response=response,
            description=description
        )
        self.behaviors[name] = behavior
        self.habits_learned += 1
        
        # Emit learning event
        try:
            if getattr(self, "post", None):
                self.post.route("autopilot.learned", {
                    "behavior": name,
                    "trigger": trigger,
                    "response": response,
                    "ts": time.time(),
                })
        except Exception:
            pass
        
        return behavior
    
    # ═══════════════════════════════════════════════════════════════════════
    # INTENTS
    # ═══════════════════════════════════════════════════════════════════════
    
    def _on_somatic_state(self, payload):
        """
        Handle somatic state from P20 - body feelings inform cognition.
        
        The body speaks; cognition listens. Feelings shape thought.
        """
        try:
            if not hasattr(self, "_somatic_context"):
                from collections import deque
                self._somatic_context = deque(maxlen=20)
            
            state = {
                "chemistry": payload.get("chemistry", {}),
                "affect": payload.get("affect", 0.5),
                "arousal": payload.get("arousal", 0.5),
                "heart_rate": payload.get("heart_rate", 1.0),
                "ts": __import__('time').time()
            }
            self._somatic_context.append(state)
            
            # Notify shadow of cross-plane activity
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Somatic handler error: {e}")

    def _intent_smoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "actor": self.ACTOR_NAME,
            "behaviors": len(self.behaviors),
            "routines": len(self.routines),
            "ts": time.time()
        }
    
    def _intent_list_behaviors(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """List all known behaviors."""
        return {
            "ok": True,
            "behaviors": [b.to_dict() for b in self.behaviors.values()],
            "count": len(self.behaviors)
        }
    
    def _intent_get_behavior(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get a specific behavior."""
        name = payload.get("name", "")
        if name not in self.behaviors:
            return {"ok": False, "error": f"Unknown behavior: {name}"}
        return {"ok": True, "behavior": self.behaviors[name].to_dict()}
    
    def _intent_learn(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Learn a new behavior."""
        name = payload.get("name", "")
        trigger = payload.get("trigger", {})
        response = payload.get("response", {})
        description = payload.get("description", "")
        
        if not name or not trigger or not response:
            return {"ok": False, "error": "Need name, trigger, and response"}
        
        behavior = self.learn_behavior(name, trigger, response, description)
        return {"ok": True, "behavior": behavior.to_dict()}
    
    def _intent_strengthen(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Strengthen a behavior (report success)."""
        name = payload.get("name", "")
        if name not in self.behaviors:
            return {"ok": False, "error": f"Unknown behavior: {name}"}
        
        self.behaviors[name].report_outcome(True)
        return {"ok": True, "new_strength": self.behaviors[name].strength}
    
    def _intent_weaken(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Weaken a behavior (report failure)."""
        name = payload.get("name", "")
        if name not in self.behaviors:
            return {"ok": False, "error": f"Unknown behavior: {name}"}
        
        self.behaviors[name].report_outcome(False)
        return {"ok": True, "new_strength": self.behaviors[name].strength}
    
    def _intent_match(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Find matching behavior for a context."""
        context = payload.get("context", {})
        matched = self.match_behavior(context)
        
        if matched:
            return {"ok": True, "matched": matched.to_dict()}
        return {"ok": True, "matched": None, "message": "No behavior matched"}
    
    def _intent_execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Manually execute a behavior."""
        name = payload.get("name", "")
        if name not in self.behaviors:
            return {"ok": False, "error": f"Unknown behavior: {name}"}
        
        behavior = self.behaviors[name]
        response = behavior.execute()
        self.habits_executed += 1
        
        return {"ok": True, "response": response, "behavior": behavior.to_dict()}
    
    def _intent_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get full autopilot status including predictive engine."""
        strong_habits = [b for b in self.behaviors.values() if b.strength > 0.5]
        weak_habits = [b for b in self.behaviors.values() if b.strength < 0.2]
        
        # Predictive engine status
        predictive_status = {}
        if hasattr(self, 'predictive_engine') and self.predictive_engine:
            pe = self.predictive_engine
            predictive_status = {
                "enabled": True,
                "prediction_accuracy": round(pe.prediction_accuracy, 3),
                "thoughts_observed": len(pe.thought_buffer),
                "predictions_made": len(pe.intention_history),
                "current_predictions": pe.predicted_intentions[:3],
                "prepared_actions": list(pe.prepared_actions.keys()),
                "cognitive_connections": {
                    "oracle": pe._oracle is not None,
                    "quantum": pe._quantum is not None,
                    "paradox": pe._paradox is not None,
                }
            }
        else:
            predictive_status = {"enabled": False}
        
        return {
            "ok": True,
            "status": {
                "total_behaviors": len(self.behaviors),
                "strong_habits": len(strong_habits),
                "weak_habits": len(weak_habits),
                "total_routines": len(self.routines),
                "habits_executed": self.habits_executed,
                "habits_learned": self.habits_learned,
                "auto_responses": self.auto_responses,
                "predictive_engine": predictive_status,
            }
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ══════════════════════════════════════════════════════════════════════════════

_AUTOPILOT_INSTANCE: Optional[AutopilotFairy] = None
_AUTOPILOT_LOCK = threading.Lock()

def get_autopilot_fairy() -> AutopilotFairy:
    """Get or create the AutopilotFairy singleton."""
    global _AUTOPILOT_INSTANCE
    if _AUTOPILOT_INSTANCE is None:
        with _AUTOPILOT_LOCK:
            if _AUTOPILOT_INSTANCE is None:
                _AUTOPILOT_INSTANCE = AutopilotFairy()
    return _AUTOPILOT_INSTANCE


def register_autopilot_fairy(instance: 'AutopilotFairy'):
    """Register an existing AutopilotFairy instance as the singleton.
    
    Called by the boot system when it creates AutopilotFairy during plane boot
    OUTSIDE of get_autopilot_fairy(). Do NOT call from __init__ - causes deadlock!
    """
    global _AUTOPILOT_INSTANCE
    with _AUTOPILOT_LOCK:
        if _AUTOPILOT_INSTANCE is None:
            _AUTOPILOT_INSTANCE = instance
            print(f"[register_autopilot_fairy] Registered boot-created instance")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== AutopilotFairy Birth Test ===\n")
    
    fairy = AutopilotFairy()
    fairy.on_boot()
    
    print("\n[TEST] Initial behaviors:")
    for name, behavior in fairy.behaviors.items():
        print(f"  {name}: strength={behavior.strength:.2f}")
    
    # Test learning
    print("\n[TEST] Learning new behavior...")
    fairy.learn_behavior(
        name="celebrate_success",
        trigger={"event_type": "goal_completed"},
        response={"action": "celebrate", "intensity": "high"},
        description="Celebrate when goals are completed"
    )
    
    # Test matching
    print("\n[TEST] Testing context matching...")
    context = {"event_type": "user_message", "is_first": True}
    matched = fairy.match_behavior(context)
    if matched:
        print(f"  Matched: {matched.name} (strength={matched.strength:.2f})")
    
    print(f"\n=== {fairy.MANTRA} ===\n")
