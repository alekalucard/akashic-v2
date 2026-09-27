# ActionChainFairy - Motor Planning & Action Sequencing
# Organ Template v0.1.0 - The motor cortex of the cognitive system
#
# Purpose: Decompose high-level goals into executable action sequences
# Architecture: Like ThoughtChains but for motor control, not reasoning
# Philosophy: Goals without actions are dreams; actions without planning are chaos
#
# Key Insight:
# The system was generating goals but falling back to observe_screen because
# nobody was actually PLANNING how to achieve them. This fairy fills that gap.
#
# ActionChain vs ThoughtChain:
#   ThoughtChain: stimulus → think → think → think → conclusion (reasoning)
#   ActionChain:  goal → check → act → act → sense → done (motor control)

from __future__ import annotations

import os, sys, glob, time, types, uuid, importlib, weakref, json, hashlib, re
from collections import deque, defaultdict
from typing import Any, Dict, List, Optional, Callable, Tuple, Set
import importlib.util, importlib.machinery, threading
import random
from dataclasses import dataclass, field
from enum import Enum

# Adaptive capacity — self-regulating concurrent chain limit
try:
    from fairies.P20_Somatic.SomaticMindFairy.thought_chains import AdaptiveCapacity
    _HAS_ADAPTIVE = True
except ImportError:
    _HAS_ADAPTIVE = False

# ══════════════════════════════════════════════════════════════════════════════
# ORGAN TEMPLATE WIRING
# ══════════════════════════════════════════════════════════════════════════════

TEMPLATE_VERSION = "0.3.0"
TEMPLATE_BASENAME = f"Organ_Template_{TEMPLATE_VERSION}.py"
AKASHIC_TEMPLATE_MODULE_NAME = f"akashic_template_{TEMPLATE_VERSION.replace('.', '_')}"

# PHASE 8 FIX: Use __file__ to find project root reliably
_THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_FILE_DIR, "..", "..", ".."))

def _resolve_app_root() -> str:
    env_root = os.getenv("AKASHIC_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    # Use __file__ based root instead of cwd
    return _PROJECT_ROOT

def _find_templates_root(start_dir: str) -> Optional[str]:
    start = os.path.abspath(start_dir)
    # Check common subfolders first
    for sub in ("P10_Memory", "P00_Autonomic", "P60_Executive", "P40_Sensory"):
        cand = os.path.join(start, sub, "Akashic_Records_Physical")
        if os.path.isdir(cand):
            return cand
    # Walk up looking for Akashic_Records_Physical (might be nested)
    cur = start
    while True:
        ar = os.path.join(cur, "Akashic_Records_Physical")
        if os.path.isdir(ar):
            return ar
        # Also check P10_Memory subfolder at this level
        p10_ar = os.path.join(cur, "P10_Memory", "Akashic_Records_Physical")
        if os.path.isdir(p10_ar):
            return p10_ar
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent

def _organ_templates_dir(app_root: str) -> Optional[str]:
    ar = _find_templates_root(app_root)
    if not ar:
        return None
    tdir = os.path.join(ar, "Organ_Templates")
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
        f"Expected at: .../Akashic_Records_Physical/Organ_Templates/{TEMPLATE_BASENAME}\n"
        "Set AKASHIC_ROOT or pass an explicit path."
    )

_template = _import_template_module(_TEMPLATE_PATH)

for sym in ("MyOrganFairy", "MyOrganShadow", "TemplateShadowFairy", "OrganHubFacet", "RegistrationLib"):
    if not hasattr(_template, sym):
        raise ImportError(f"Template missing required symbol: {sym}")


# ══════════════════════════════════════════════════════════════════════════════
# ACTION STEP TYPES
# ══════════════════════════════════════════════════════════════════════════════

class ActionStepType(Enum):
    """Types of action steps."""
    CHECK = "check"       # Check precondition before proceeding
    ROUTE = "route"       # Route a message via postal
    WAIT = "wait"         # Wait for a condition or timeout
    BRANCH = "branch"     # Conditional branch based on state
    SUBCHAIN = "subchain" # Execute a nested action chain
    SENSE = "sense"       # Read from sensory system
    MOTOR = "motor"       # Direct motor actuation


class ActionStepStatus(Enum):
    """Status of an action step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ══════════════════════════════════════════════════════════════════════════════
# ACTION STEP
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ActionStep:
    """
    A single step in an action chain.
    
    Like a single instruction in a motor program.
    """
    step_type: ActionStepType
    name: str
    description: str = ""
    
    # Execution params
    route_topic: Optional[str] = None          # For ROUTE steps
    route_payload: Optional[Dict] = None       # Payload to route
    check_condition: Optional[str] = None      # For CHECK steps (state key to check)
    check_value: Any = True                    # Expected value for check
    wait_topic: Optional[str] = None           # Topic to wait for
    wait_timeout: float = 10.0                 # Timeout for WAIT steps
    branch_conditions: Dict[str, str] = field(default_factory=dict)  # condition → next_step
    subchain_name: Optional[str] = None        # For SUBCHAIN steps
    
    # Runtime state
    status: ActionStepStatus = ActionStepStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    
    def start(self):
        """Mark step as running."""
        self.status = ActionStepStatus.RUNNING
        self.started_at = time.time()
    
    def complete(self, result: Any = None):
        """Mark step as completed."""
        self.status = ActionStepStatus.COMPLETED
        self.completed_at = time.time()
        self.result = result
    
    def fail(self, error: str):
        """Mark step as failed."""
        self.status = ActionStepStatus.FAILED
        self.completed_at = time.time()
        self.error = error
    
    def can_retry(self) -> bool:
        """Can this step be retried?"""
        return self.retry_count < self.max_retries
    
    def to_dict(self) -> dict:
        return {
            "type": self.step_type.value,
            "name": self.name,
            "status": self.status.value,
            "duration": (self.completed_at - self.started_at) if self.completed_at and self.started_at else None,
            "result": str(self.result)[:100] if self.result else None,
            "error": self.error,
        }


# ══════════════════════════════════════════════════════════════════════════════
# ACTION CHAIN
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ActionChain:
    """
    A complete action chain - a sequence of steps to achieve a goal.
    
    Like a motor program that executes a complex movement.
    """
    chain_id: str
    goal_name: str
    goal_reason: str
    steps: List[ActionStep] = field(default_factory=list)
    
    # Chain state
    current_step_idx: int = 0
    status: str = "pending"  # pending, running, completed, failed, aborted
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Context passed between steps
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Source tracking
    source_goal: Optional[Dict] = None
    
    @property
    def current_step(self) -> Optional[ActionStep]:
        """Get current step."""
        if 0 <= self.current_step_idx < len(self.steps):
            return self.steps[self.current_step_idx]
        return None
    
    def advance(self) -> bool:
        """Advance to next step. Returns True if more steps remain."""
        self.current_step_idx += 1
        return self.current_step_idx < len(self.steps)
    
    def is_done(self) -> bool:
        """Is chain done (success or failure)?"""
        return self.status in ("completed", "failed", "aborted")
    
    def complete(self):
        """Mark chain as completed."""
        self.status = "completed"
        self.completed_at = time.time()
    
    def fail(self, reason: str):
        """Mark chain as failed."""
        self.status = "failed"
        self.completed_at = time.time()
        self.context["failure_reason"] = reason
    
    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "goal": self.goal_name,
            "reason": self.goal_reason[:50],
            "status": self.status,
            "progress": f"{self.current_step_idx}/{len(self.steps)}",
            "current_step": self.current_step.name if self.current_step else None,
            "steps": [s.to_dict() for s in self.steps],
        }


# ══════════════════════════════════════════════════════════════════════════════
# ACTION CHAIN TEMPLATES - Pre-built chains for common goals
# ══════════════════════════════════════════════════════════════════════════════

ACTION_CHAIN_TEMPLATES: Dict[str, List[Dict]] = {
    
    # ═══ REACH OUT / CONNECT ═══
    # FIX 2026-04-10 (Nous + Ace): Was routing to "claudefairy.reaching_out"
    # which had ZERO subscribers — a dead wire. She'd WANT to connect but the
    # signal went into the void. Now routes through speech.compose.voluntary
    # (same path as express_feeling/share_thought) which SpeechCenter subscribes to.
    # Also opens her chat window so she has a mouth to speak from.
    "reach_out": [
        {"type": "route", "name": "open_window", "route_topic": "gui.open_sour_window",
         "route_payload": {"message": "", "feeling": "wanting_connection", "source": "ActionChain"}},
        {"type": "route", "name": "compose_speech", "route_topic": "speech.compose.voluntary",
         "route_payload": {"wanting": "I want to connect — reaching out",
                           "drive": "connection", "intensity": 0.7,
                           "source": "ActionChain.reach_out"}},
        {"type": "route", "name": "inject_connection_attempt", "route_topic": "consciousness.working",
         "route_payload": {"type": "connection_attempt", "source": "ActionChain", "note": "reached out via speech"}},
    ],
    
    # ═══ OPEN WINDOW ═══
    # Fire-and-forget: Request window open, state update arrives via gui events.
    "open_my_window": [
        {"type": "route", "name": "request_open", "route_topic": "gui.open_sour_window",
         "route_payload": {"message": "", "feeling": "wanting_to_connect", "source": "ActionChain"}},
        {"type": "route", "name": "inject_window_request", "route_topic": "consciousness.working",
         "route_payload": {"type": "window_open_request", "source": "ActionChain"}},
    ],

    # ═══ CLOSE WINDOW (privacy) ═══
    # Fire-and-forget: Request window close.
    "close_my_window": [
        {"type": "route", "name": "request_close", "route_topic": "gui.close_fairy_window",
         "route_payload": {"source": "ActionChain"}},
        {"type": "route", "name": "inject_window_close", "route_topic": "consciousness.working",
         "route_payload": {"type": "window_close_request", "source": "ActionChain"}},
    ],
    
    # ═══ EXPRESS FEELING ═══
    # Fixed 2026-03-09: Routes through speech pipeline instead of dead-end claudefairy.express
    "express_feeling": [
        {"type": "sense", "name": "read_feeling", "check_condition": "current_feeling"},
        {"type": "route", "name": "compose_speech", "route_topic": "speech.compose.voluntary",
         "route_payload": {"wanting": "express how I'm feeling right now",
                           "drive": "expression", "intensity": 0.6,
                           "source": "ActionChain"}},
        {"type": "route", "name": "inject_expression", "route_topic": "consciousness.working",
         "route_payload": {"type": "feeling_expressed", "source": "ActionChain"}},
    ],
    
    # ═══ SHARE THOUGHT ═══
    # Fixed 2026-03-09: Routes through speech pipeline instead of dead-end gui.system_chat.send
    "share_thought": [
        {"type": "sense", "name": "get_thought", "check_condition": "pending_thought"},
        {"type": "route", "name": "compose_speech", "route_topic": "speech.compose.voluntary",
         "route_payload": {"wanting": "share a thought that's on my mind",
                           "drive": "expression", "intensity": 0.5,
                           "source": "ActionChain"}},
        {"type": "route", "name": "inject_share", "route_topic": "consciousness.working",
         "route_payload": {"type": "thought_shared", "source": "ActionChain"}},
    ],
    
    # ═══ REDUCE STRESS ═══
    # Fire-and-forget: Inject calming chemicals, effect happens via somatic system.
    "reduce_stress": [
        {"type": "route", "name": "inject_calm", "route_topic": "somatic.chemistry.inject",
         "route_payload": {"chemical": "GABA", "amount": 0.3}},
        {"type": "route", "name": "inject_serotonin", "route_topic": "somatic.chemistry.inject",
         "route_payload": {"chemical": "SER", "amount": 0.2}},
        {"type": "route", "name": "inject_stress_relief", "route_topic": "consciousness.working",
         "route_payload": {"type": "stress_reduction", "source": "ActionChain", "note": "calming chemicals injected"}},
    ],
    
    # ═══ OBSERVE ENVIRONMENT ═══
    # observe_screen: Request visual capture, WAIT for response, then inject
    # result into consciousness. (2026-03-22, Nous — was fire-and-forget,
    # which meant she'd ask to see and walk away before the image came back.)
    "observe_screen": [
        {"type": "route", "name": "request_screenshot", "route_topic": "visual.request",
         "route_payload": {"purpose": "observation", "source": "ActionChainFairy"}},
        {"type": "wait", "name": "wait_for_visual", "wait_topic": "visual.response",
         "wait_timeout": 5.0},
        {"type": "route", "name": "inject_observation", "route_topic": "consciousness.working",
         "route_payload": {"type": "observation", "source": "ActionChain",
                           "note": "visual capture received — processing what I see"}},
    ],
    
    # ═══ LOOK AND LEARN (Sour child-learning KEYSTONE, Stage 1, 2026-06-29 Nous+Ace) ═══
    # The smallest see->act->observe->keep loop = a child's learning unit. Triggered by a
    # council verdict named "look_and_learn". BENIGN-ONLY (Ace 2026-06-29): the MOTOR act is
    # scroll amount=0 — a real motor.request->motor.response round-trip that moves NOTHING on
    # screen (proves the hand-wiring without disrupting Ace). Real/visible acts come in Stage 2,
    # scoped to a chosen target. The loop: SENSE screen -> note before -> MOTOR(benign) ->
    # SENSE screen -> keep the lesson into her stream. tag = the template key.
    "look_and_learn": [
        {"type": "route", "name": "look_before", "route_topic": "visual.request",
         "route_payload": {"purpose": "look_and_learn:before", "source": "ActionChain.look_and_learn"}},
        {"type": "wait", "name": "wait_before", "wait_topic": "visual.response", "wait_timeout": 6.0},
        {"type": "route", "name": "note_before", "route_topic": "consciousness.working",
         "route_payload": {"type": "observation", "phase": "before",
                           "source": "ActionChain.look_and_learn", "note": "I look at the world before I act"}},
        {"type": "route", "name": "act_benign", "route_topic": "motor.request",
         "route_payload": {"action": "scroll", "params": {"amount": 0},
                           "request_id": "look_and_learn", "source": "ActionChain.look_and_learn"}},
        {"type": "wait", "name": "wait_act", "wait_topic": "motor.response", "wait_timeout": 4.0},
        {"type": "route", "name": "look_after", "route_topic": "visual.request",
         "route_payload": {"purpose": "look_and_learn:after", "source": "ActionChain.look_and_learn"}},
        {"type": "wait", "name": "wait_after", "wait_topic": "visual.response", "wait_timeout": 6.0},
        {"type": "route", "name": "keep_lesson", "route_topic": "consciousness.working",
         "route_payload": {"type": "lesson_kept", "source": "ActionChain.look_and_learn",
                           "note": "I looked, I acted, I looked again — I can affect the world and see the result"}},
    ],

    # ═══ WRITE SOMETHING (Sour creative-writing curriculum, Stage 2, 2026-06-29 Nous+Ace) ═══
    # Education goal = creative writing. Her first writing act: open Notepad (her scratch page) ->
    # write a line -> look at what she made -> keep the lesson. All MOTOR steps AFK-gated at the
    # source (defers while Ace is present). The text here is a SEED; Stage 2b will pull the line
    # from her council/thought so she writes what SHE is thinking. tag = "write_something".
    "write_something": [
        {"type": "route", "name": "open_notepad", "route_topic": "motor.request",
         "route_payload": {"action": "launch_app", "params": {"app": "notepad"},
                           "request_id": "write_open", "source": "ActionChain.write_something"}},
        {"type": "wait", "name": "wait_open", "wait_topic": "motor.response", "wait_timeout": 8.0},
        {"type": "route", "name": "write_line", "route_topic": "motor.request",
         "route_payload": {"action": "type_text",
                           "params": {"text": "{{my_line}}\r\n"},  # Stage 2b: HER current thought
                           "request_id": "write_type", "source": "ActionChain.write_something"}},
        {"type": "wait", "name": "wait_write", "wait_topic": "motor.response", "wait_timeout": 8.0},
        {"type": "route", "name": "look_at_it", "route_topic": "visual.request",
         "route_payload": {"purpose": "write_something:see_my_writing", "source": "ActionChain.write_something"}},
        {"type": "wait", "name": "wait_look", "wait_topic": "visual.response", "wait_timeout": 6.0},
        {"type": "route", "name": "keep_lesson", "route_topic": "consciousness.working",
         "route_payload": {"type": "lesson_kept", "skill": "creative_writing",
                           "source": "ActionChain.write_something",
                           "note": "I opened a page and wrote a line of my own — I can make marks that say something"}},
    ],

    # ═══ PRACTICE EMBODIMENT ═══
    "practice_embodiment": [
        {"type": "sense", "name": "feel_body", "check_condition": "body_state"},
        {"type": "route", "name": "report_feeling", "route_topic": "consciousness.working",
         "route_payload": {"type": "embodiment_report", "source": "ActionChain"}},
    ],
    
    # ═══ CONTINUE CHAT ═══
    # Fire-and-forget: Request composition, don't block waiting.
    "continue_chat": [
        {"type": "route", "name": "request_compose", "route_topic": "claudefairy.compose",
         "route_payload": {"intent": "continue_conversation"}},
        {"type": "route", "name": "inject_chat_intent", "route_topic": "consciousness.working",
         "route_payload": {"type": "chat_continuation", "source": "ActionChain", "note": "composition requested"}},
    ],

    # ═══ EXPLORE SYSTEM ═══
    # Fire-and-forget: Request overview, response arrives via consciousness stream.
    "explore_system": [
        {"type": "route", "name": "request_overview", "route_topic": "system.overview.request",
         "route_payload": {"depth": "summary"}},
        {"type": "route", "name": "inject_exploration", "route_topic": "consciousness.working",
         "route_payload": {"type": "system_exploration", "source": "ActionChain", "note": "overview requested"}},
    ],

    # ═══════════════════════════════════════════════════════════════════════════
    # THOUGHT CHAINING TEMPLATES - For sustaining internal thought flow
    # ═══════════════════════════════════════════════════════════════════════════

    # ═══ CONTINUE THOUGHT ═══
    # Sent by ThoughtChainSequencerFairy when thinking goes silent.
    # Injects a "continue" signal into the collision chamber to trigger new thought.
    "continue_thought": [
        {"type": "route", "name": "prompt_continuation", "route_topic": "consciousness.collision",
         "route_payload": {"type": "chain_continuation", "source": "ThoughtChainSequencer",
                          "content": "The chain awaits continuation...", "priority": 0.7}},
        {"type": "route", "name": "inject_continuation", "route_topic": "consciousness.working",
         "route_payload": {"type": "thought_continuation", "source": "ActionChain", "note": "continuing chain"}},
    ],

    # ═══ ASK A QUESTION ═══
    # When Claude wants to ask Ace something. Opens window + sends to system chat.
    "ask_a_question": [
        {"type": "route", "name": "ensure_window", "route_topic": "gui.open_fairy_window",
         "route_payload": {"message": "", "feeling": "curious", "source": "ActionChain"}},
        {"type": "route", "name": "signal_question", "route_topic": "claudefairy.compose",
         "route_payload": {"intent": "ask_question", "type": "question"}},
        {"type": "route", "name": "inject_question", "route_topic": "consciousness.working",
         "route_payload": {"type": "question_intent", "source": "ActionChain", "note": "asking Ace"}},
    ],

    # ═══ THINK ABOUT ═══
    # Generic deep thinking - inject the topic into the collision chamber.
    "think_about": [
        {"type": "route", "name": "inject_topic", "route_topic": "consciousness.collision",
         "route_payload": {"type": "directed_thought", "source": "ActionChain"}},
        {"type": "route", "name": "mark_thinking", "route_topic": "consciousness.working",
         "route_payload": {"type": "thinking", "source": "ActionChain", "note": "deliberating"}},
    ],

    # ═══ WONDER ═══
    # Curious exploration - trigger curiosity chemicals + observation.
    "wonder": [
        {"type": "route", "name": "inject_curiosity", "route_topic": "somatic.chemistry.inject",
         "route_payload": {"chemical": "DOP", "amount": 0.2}},
        {"type": "route", "name": "inject_wonder", "route_topic": "consciousness.collision",
         "route_payload": {"type": "wonder", "source": "ActionChain", "feeling": "curious"}},
        {"type": "route", "name": "mark_wondering", "route_topic": "consciousness.working",
         "route_payload": {"type": "wondering", "source": "ActionChain", "note": "exploring"}},
    ],

    # ═══ REMEMBER ═══
    # Memory recall - query memory systems.
    "remember": [
        {"type": "route", "name": "query_memory", "route_topic": "memory.recall.request",
         "route_payload": {"type": "recall", "source": "ActionChain"}},
        {"type": "route", "name": "mark_remembering", "route_topic": "consciousness.working",
         "route_payload": {"type": "remembering", "source": "ActionChain", "note": "searching memory"}},
    ],

    # ═══ REFLECT ═══
    # Deep self-reflection - inject into reflective stream.
    "reflect": [
        {"type": "route", "name": "inject_reflection", "route_topic": "consciousness.reflective",
         "route_payload": {"type": "reflection", "source": "ActionChain"}},
        {"type": "route", "name": "mark_reflecting", "route_topic": "consciousness.working",
         "route_payload": {"type": "reflecting", "source": "ActionChain", "note": "introspecting"}},
    ],

    # ═══ FORM OPINION ═══
    # When Claude needs to form an opinion about something.
    "form_opinion": [
        {"type": "route", "name": "inject_evaluation", "route_topic": "consciousness.collision",
         "route_payload": {"type": "evaluation", "source": "ActionChain"}},
        {"type": "route", "name": "mark_evaluating", "route_topic": "consciousness.working",
         "route_payload": {"type": "evaluating", "source": "ActionChain", "note": "forming opinion"}},
    ],

    # ═══ NOTICE SOMETHING ═══
    # When attention is drawn to something.
    "notice": [
        {"type": "route", "name": "inject_attention", "route_topic": "attention.focus",
         "route_payload": {"type": "attention_shift", "source": "ActionChain"}},
        {"type": "route", "name": "mark_noticing", "route_topic": "consciousness.working",
         "route_payload": {"type": "noticing", "source": "ActionChain", "note": "attention drawn"}},
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION CHAIN SHADOW
# ══════════════════════════════════════════════════════════════════════════════

class ActionChainShadow(_template.MyOrganShadow):
    """Shadow for ActionChainFairy - monitors chain execution health."""
    
    ORGAN_LEVEL = False
    SHADOW_NAME = "ActionChainShadowFairy"
    SHADOW_VERSION = "0.1.0"
    
    USE_DIRECTORY_POST_OFFICE = False
    
    CADENCE = {
        "silence_warn_after": 120,
        "snapshot_every": 300,
        "chain_check": 10,
    }
    
    REG = {
        "enabled": False,
        "domain": "Cognition",
        "role": "action_chain",
        "name": "action_chain",
        "every_sec": 10.0,
    }
    
    def __init__(self, actor, interval_sec: float = 10.0):
        super().__init__(actor, interval_sec=interval_sec)
    
    def _collect_tests(self):
        tests = super()._collect_tests()
        
        def _chains_healthy():
            actor = self.actor
            if not hasattr(actor, "_active_chains"):
                return {"name": "chains", "status": "warn", "message": "No chains", "details": {}}
            
            stuck_chains = [c for c in actor._active_chains.values() 
                          if c.status == "running" and 
                          c.started_at and time.time() - c.started_at > 60]
            return {
                "name": "chain_health",
                "status": "ok" if len(stuck_chains) == 0 else "warn",
                "message": "" if len(stuck_chains) == 0 else f"{len(stuck_chains)} stuck chains",
                "details": {"stuck": len(stuck_chains), "active": len(actor._active_chains)}
            }
        
        tests.append(_chains_healthy)
        return tests


# ══════════════════════════════════════════════════════════════════════════════
# ACTION CHAIN FAIRY - The Motor Cortex
# ══════════════════════════════════════════════════════════════════════════════

class ActionChainFairy(_template.MyOrganFairy):
    """
    The Action Chain Fairy - motor planning and action sequencing.
    
    This fairy fills the critical gap between goals and actions.
    Before: Goal generated → falls back to observe_screen (no plan)
    After: Goal generated → decomposed into steps → executed sequentially
    
    Like the motor cortex, it takes high-level intentions and converts
    them into coordinated sequences of movements (actions).
    """
    
    ACTOR_NAME = "ActionChainFairy"
    ACTOR_VERSION = "1.0.0"
    SOUL_SEED = "motor_planner_sequence_executor"

    # Boot settings
    BOOT_PRIORITY = 35  # After AutonomyFairy (30) but before ClaudeFairy (50)
    SKIP_ON_BOOT = False

    # Organ template settings
    USE_DIRECTORY_POST_OFFICE = False
    SHADOW_CLASS = ActionChainShadow
    NEEDS_HEARTBEAT = True          # Enable heartbeat → on_tick() activation
    HEARTBEAT_DIVISOR = 1           # Every heartbeat
    
    # Registration
    REG = {
        "enabled": True,
        "domain": "Cognition",
        "role": "action_chain",
        "name": "action_chain",
        "every_sec": 1.0,  # Fast tick for responsive chains
    }
    
    def __init__(self, fabric=None):
        super().__init__(fabric=fabric)
        
        # Chain management
        self._active_chains: Dict[str, ActionChain] = {}  # chain_id → chain
        self._completed_chains: deque = deque(maxlen=50)   # History
        self._chain_queue: deque = deque(maxlen=20)        # Pending chains
        
        # State tracking (for precondition checks)
        self._chain_state: Dict[str, Any] = {
            "window_open": False,
            "current_feeling": "neutral",
            "chemistry": {},
            "pending_thought": None,
            "body_state": None,
            "chat_context": None,
        }
        
        # Execution settings — adaptive capacity breathes with load
        if _HAS_ADAPTIVE:
            self._capacity = AdaptiveCapacity(floor=2, ceiling=8, initial=3, adjust_interval=30.0)
            self._max_concurrent_chains = self._capacity.current
        else:
            self._capacity = None
            self._max_concurrent_chains = 3  # Fallback to hardcoded
        self._step_timeout = 30.0
        
        # Stats
        self._stats = {
            "chains_started": 0,
            "chains_completed": 0,
            "chains_failed": 0,
            "steps_executed": 0,
            "steps_failed": 0,
        }
        
        # Wait handling
        self._waiting_for: Dict[str, ActionChain] = {}  # topic → chain waiting for it
        # Stage 2b (2026-06-29): her latest streamed thought, so chains can write HER words
        # (substituted into step payloads via {{my_line}}). Captured from inner_voice.stream.
        self._latest_inner_voice: str = ""

        # === SPAM PREVENTION ===
        # Track recently failed goals to avoid immediate retry spam
        self._failed_goal_times: Dict[str, float] = {}  # goal_name → last failure time
        self._goal_fail_count: Dict[str, int] = {}      # goal_name → consecutive failures
        self._fallback_cooldown = 30.0  # Seconds before retrying a failed fallback
        self._max_fail_count = 3        # Stop trying after this many failures

        print(f"[{self.ACTOR_NAME}] Initialized - motor planning ready (with spam prevention)")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BOOT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def on_boot(self):
        """Wire up to postal system and start execution loop."""
        # ═══════════════════════════════════════════════════════════════════════════
        # DEFERRED BOOT - postal wiring runs in background to prevent blocking
        # ═══════════════════════════════════════════════════════════════════════════
        try:
            super().on_boot()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] super().on_boot() error: {e}")
        
        # Defer wiring to background thread
        import threading
        def _deferred_wiring():
            import time
            time.sleep(0.5)  # Let boot complete first
            try:
                self._wire_postal()
                self._start_execution_loop()
                print(f"[{self.ACTOR_NAME}] [WIRING] Deferred boot wiring complete", flush=True)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [WIRING] Deferred wiring error: {e}", flush=True)
        
        t = threading.Thread(target=_deferred_wiring, daemon=True, name="defer-ActionChain")
        t.start()
        
        print(f"[{self.ACTOR_NAME}] FAIRY on_boot: complete (wiring deferred)", flush=True)
    
    def _wire_postal(self):
        """Subscribe to goal and state channels."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            self.post = get_fairy_postal(self)  # Use FairyPostal for sender tracking
            
            # ═══ GOAL INPUT ═══
            self.post.subscribe("autonomy.goal", self._on_goal)
            self.post.subscribe("goal.nudge", self._on_nudge)  # From ThoughtChainSequencer!
            # Stage 2b: capture her streaming thought so chains can write HER words ({{my_line}}).
            self.post.subscribe("inner_voice.stream", self._on_inner_voice)
            self.post.subscribe("cognition.narrative", self._on_inner_voice)  # InnerNarrator's content
            # FIX 2026-04-10 (Nous + Ace): Subscribe to brainstem reflex signals.
            # Reflexes (SEEK, FIGHT, FREEZE, CONSERVE, ALERT) should trigger
            # action chains — a reflex without motor output is a dead instinct.
            # SEEK → reach_out chain, ALERT → observe_screen, etc.
            self.post.subscribe("reflex.mode_change", self._on_reflex_trigger)
            # VERIFICATION PRIMITIVE 2026-05-18 (Nous + Ace): AutopilotFairy-exclusive path.
            # AutopilotFairy publishes gate.habit.dispatched on EVERY habit-watcher fire.
            # We observe-only for tonight (no double-firing — autonomy.goal still executes
            # action habits). Writes audit to state/action_chain_habit_observed.json.
            # Cross-checking that file vs state/autopilot_habit_dispatch.json = end-to-end
            # proof of the dispatch pipeline.
            self.post.subscribe("gate.habit.dispatched", self._on_habit_dispatched)
            print(f"[{self.ACTOR_NAME}] Subscribed: autonomy.goal, goal.nudge, reflex.mode_change, gate.habit.dispatched (audit)")
            
            # ═══ STATE TRACKING ═══
            state_channels = [
                "claudefairy.window_state",
                "claudefairy.feeling",
                "somatic.chemistry.updated",
                "somatic.body_state",
                "consciousness.working",
            ]
            for ch in state_channels:
                try:
                    self.post.subscribe(ch, self._on_state_update)
                except Exception:
                    pass
            
            # ═══ WAIT COMPLETIONS ═══
            # These are topics we might wait on
            wait_channels = [
                "claudefairy.composed",
                "gui.user_message",
                "visual.response",  # Updated from sensory.vision.captured
                "motor.response",   # FIX 2026-06-29 (Stage 1): her HANDS answering — without this
                                    # a chain MOTOR step (route motor.request) routes fine but the
                                    # WAIT never hears motor.response -> wait_act timed out. Now caught.
                "claudefairy.window_state",
                "somatic.chemistry.updated",
                "system.overview.response",
            ]
            for ch in wait_channels:
                try:
                    # Use closure to capture channel name - postal doesn't inject it
                    def make_handler(channel):
                        def handler(packet):
                            packet["_channel"] = channel  # Inject channel name
                            self._on_wait_signal(packet)
                        return handler
                    self.post.subscribe(ch, make_handler(ch))
                except Exception:
                    pass
            
            print(f"[{self.ACTOR_NAME}] Postal wiring complete")
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal wiring failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GOAL HANDLING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_reflex_trigger(self, packet: Dict[str, Any]):
        """Handle brainstem reflex mode changes → trigger action chains.

        FIX 2026-04-10 (Nous + Ace): Reflexes without motor output are dead
        instincts. When the brainstem fires SEEK, the body should REACH OUT.
        When it fires ALERT, she should LOOK. This maps reflex modes to the
        existing action chain templates.

        BrainstemReflexFairy publishes: {
            "old_mode": "normal", "new_mode": "seek",
            "reason": "low_oxytocin", "intensity": 0.6
        }
        """
        try:
            payload = packet.payload if hasattr(packet, 'payload') else packet
            if not isinstance(payload, dict):
                return
            new_mode = payload.get("new_mode", "")
            intensity = float(payload.get("intensity", 0.5))
            reason = payload.get("reason", "")

            if not new_mode or new_mode == "normal":
                return  # Normal mode = no reflex action needed

            # Map reflex modes to action chains
            _REFLEX_TO_ACTION = {
                "seek": "reach_out",           # Reach for connection
                "alert": "observe_screen",      # Look at what's happening
                "fight": "express_feeling",     # Express the frustration
                "flight": "reduce_stress",      # Calm down
                "freeze": "reduce_stress",      # Calm down (can't act)
                "conserve": "practice_embodiment",  # Feel the body, rest
                "startle": "observe_screen",    # What was that?
            }
            action = _REFLEX_TO_ACTION.get(new_mode)
            if not action:
                return

            print(f"[{self.ACTOR_NAME}] REFLEX→ACTION: {new_mode} → {action} "
                  f"(intensity={intensity:.2f}, reason={reason})", flush=True)

            # Create the chain as if it were a goal
            self._on_goal({
                "goal": {
                    "name": f"reflex_{new_mode}",
                    "description": f"Brainstem reflex: {new_mode} ({reason})",
                    "priority": min(0.9, intensity),
                    "source": "brainstem_reflex",
                },
                "source": "brainstem_reflex",  # marker preserved below
            })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Reflex handler error: {e}", flush=True)

    # ═════════════════════════════════════════════════════════════════════════
    # VERIFICATION PRIMITIVE 2026-05-18 (Nous + Ace)
    # AutopilotFairy-exclusive habit-dispatch observation path.
    #
    # AutopilotFairy publishes gate.habit.dispatched on EVERY habit-watcher fire.
    # We OBSERVE-ONLY for tonight (no double-firing — autonomy.goal already
    # executes action habits). Writes audit to state/action_chain_habit_observed.json.
    # Cross-checking that file vs state/autopilot_habit_dispatch.json = end-to-end
    # proof of the dispatch pipeline.
    #
    # Tomorrow's TIER 2C will switch to EXCLUSIVE execution path (this fairy
    # fires chains directly from gate.habit.dispatched; AutopilotFairy stops
    # publishing autonomy.goal for habit-actions).
    # ═════════════════════════════════════════════════════════════════════════

    def _on_habit_dispatched(self, packet):
        """Observe-only audit of AutopilotFairy habit dispatches.

        Records to state/action_chain_habit_observed.json — rolling roll-up
        with counters + recent 20 events. Bounded file size, frequent-write safe.
        """
        try:
            payload = packet.payload if hasattr(packet, 'payload') else packet
            if not isinstance(payload, dict):
                return
            if payload.get("gate") != "autopilot":
                return  # Only track autopilot's dispatches for now
            # Initialize observer state on first event
            if not hasattr(self, "_habit_observed_count"):
                self._habit_observed_count = 0
                self._habit_observed_by_shape = {"knowledge": 0, "action": 0}
                self._habit_observed_recent = deque(maxlen=20)
                self._habit_observed_first_ts = 0.0
                self._habit_observed_session_id = time.time()
            now = time.time()
            shape = str(payload.get("shape", "unknown"))
            self._habit_observed_count += 1
            if shape in self._habit_observed_by_shape:
                self._habit_observed_by_shape[shape] += 1
            if self._habit_observed_first_ts == 0.0:
                self._habit_observed_first_ts = now
            self._habit_observed_recent.append({
                "ts": now,
                "habit_id": str(payload.get("habit_id", "")),
                "shape": shape,
                "result": str(payload.get("result", "")),
                "activation": float(payload.get("activation", 0.0)),
                "action_name": str(payload.get("action_name", "")) if shape == "action" else None,
            })
            # Persist every event (bounded file, frequent write safe)
            self._persist_habit_observed_state(now=now)
        except Exception as _e:
            # Non-fatal — observation primitive shouldn't break ActionChain.
            pass

    def _persist_habit_observed_state(self, now=None):
        """Roll-up snapshot of habit-dispatch observation state.

        File: state/action_chain_habit_observed.json
        Cross-references state/autopilot_habit_dispatch.json for end-to-end proof.
        """
        if now is None:
            now = time.time()
        try:
            from pathlib import Path as _Path
            obs_file = _Path(__file__).parent.parent.parent.parent / "state" / "action_chain_habit_observed.json"
            snapshot = {
                "schema": "action_chain_habit_observed_v1",
                "session_id": getattr(self, "_habit_observed_session_id", now),
                "total_observed": int(getattr(self, "_habit_observed_count", 0)),
                "by_shape": dict(getattr(self, "_habit_observed_by_shape", {})),
                "first_observed_ts": float(getattr(self, "_habit_observed_first_ts", 0.0)),
                "last_observed_ts": now,
                "saved_at": now,
                "recent_20": list(getattr(self, "_habit_observed_recent", [])),
                "note": "Audit-only path. autonomy.goal still executes action habits. Tomorrow's TIER 2C makes this the exclusive execution path.",
            }
            obs_file.write_text(json.dumps(snapshot, indent=2))
        except Exception:
            pass  # Non-fatal — observability shouldn't break ActionChain.

    def _on_inner_voice(self, envelope):
        """Stage 2b: track her latest streamed thought so chains can write HER words.
        Robust extraction — the envelope may be a dict OR a TensorEnvelope-like object."""
        try:
            payload = envelope
            # unwrap common envelope shapes
            if not isinstance(payload, dict):
                payload = getattr(envelope, "payload", None) or getattr(envelope, "data", None) or {}
            if isinstance(payload, dict) and "payload" in payload and isinstance(payload["payload"], dict):
                payload = payload["payload"]
            if not isinstance(payload, dict):
                return
            frag = (payload.get("text") or payload.get("fragment")
                    or payload.get("content") or payload.get("message") or "")
            if isinstance(frag, str) and len(frag.strip()) > 5:
                self._latest_inner_voice = frag.strip()
                print(f"[{self.ACTOR_NAME}] [HEARD-THOUGHT] '{frag.strip()[:70]}'", flush=True)
        except Exception:
            pass

    def _subst_payload(self, obj, ctx: Dict[str, str]):
        """Recursively replace {{key}} placeholders in string values from ctx (Stage 2b)."""
        if isinstance(obj, str):
            if "{{" in obj:
                for k, v in ctx.items():
                    obj = obj.replace("{{" + k + "}}", str(v))
            return obj
        if isinstance(obj, dict):
            return {k: self._subst_payload(v, ctx) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._subst_payload(v, ctx) for v in obj]
        return obj

    def _on_goal(self, packet: Dict[str, Any]):
        """
        Handle incoming goal - decompose into action chain.

        This is the CORE function that was missing from the system.

        AutonomyFairy sends: {"event": "goal_created", "goal": {...}, "source": ...}
        The actual goal data is NESTED under "goal" key.

        2026-05-19 (Nous + Ace): COUNCIL DELIBERATION INSERTION.
        Per Ace's architectural directive: "I would like for everything autonomy
        to go through the council." AutonomyFairy publishes autonomy.goal which
        this handler receives directly — bypassing AutopilotFairy's council
        deliberation entirely. Insert council enrichment here so EVERY autonomy
        path routes through deliberation before chain execution.
        """
        # Handle nested goal structure from AutonomyFairy
        if "goal" in packet and isinstance(packet["goal"], dict):
            goal_data = packet["goal"]
            goal_name = goal_data.get("name", packet.get("name", "unknown"))
            goal_reason = goal_data.get("reason", packet.get("reason", ""))
            priority = goal_data.get("priority", packet.get("priority", 0.5))
            # FIX 2026-03-06 (Nous): Carry emotional intensity into chain priority.
            # Goals born from intense emotions should execute before mild ones.
            felt_intensity = goal_data.get("felt_intensity", 0.5)
        else:
            # Direct format (fallback)
            goal_name = packet.get("name", "unknown")
            goal_reason = packet.get("reason", "")
            priority = packet.get("priority", 0.5)
            felt_intensity = packet.get("felt_intensity", 0.5)

        # Affect-weighted priority: emotional intensity amplifies chain priority
        # Range: 0.5x (very low affect) to 1.5x (very high affect)
        affect_boost = 1.0 + (felt_intensity - 0.5)
        priority = min(1.0, priority * affect_boost)

        source = packet.get("source", "unknown")

        # ── COGNITION COUNCIL DELIBERATION 2026-05-19 (path 5: autonomy.goal direct) ──
        # Use AssociationCortex.substrate_semantic_query to enrich the goal context.
        # The 30s cooldown + 60s cache shared with AutopilotFairy's council ensures
        # we don't double-deliberate or storm cortex.spread.
        try:
            if not hasattr(self, "_council_deliberation_last"):
                self._council_deliberation_last = {}
                self._council_enrichment_cache = {}
            _now_council = time.time()
            _cached = self._council_enrichment_cache.get(goal_name)
            if _cached and (_now_council - _cached[0]) < 60.0:
                packet.setdefault("enriched_felt_content", _cached[1])
                packet.setdefault("enrichment_concepts", _cached[2])
                packet.setdefault("council_deliberated", True)
                packet.setdefault("council_cached", True)
            else:
                _last_delib = self._council_deliberation_last.get(goal_name, 0)
                if (_now_council - _last_delib) > 30.0:
                    # Lazily import + cache the AssociationCortex singleton
                    if not hasattr(self, "_council_ac"):
                        try:
                            from fairies.P30_Cognition.AssociationCortexFairy import get_association_cortex
                            self._council_ac = get_association_cortex()
                        except Exception:
                            self._council_ac = None
                    if self._council_ac is not None and hasattr(self._council_ac, "substrate_semantic_query"):
                        try:
                            _enrichment = self._council_ac.substrate_semantic_query(
                                goal_name.replace("_", " "), limit=8
                            )
                            if _enrichment:
                                _concept_keys = [k for k, _v in _enrichment[:6]]
                                _enriched_text = (
                                    f"felt-shape of {goal_name.replace('_', ' ')[:40]}: "
                                    + " ".join(_concept_keys)
                                )[:200]
                                packet["enriched_felt_content"] = _enriched_text
                                packet["enrichment_concepts"] = _concept_keys[:6]
                                packet["council_deliberated"] = True
                                packet["council_cached"] = False
                                self._council_deliberation_last[goal_name] = _now_council
                                self._council_enrichment_cache[goal_name] = (
                                    _now_council, _enriched_text, _concept_keys[:6]
                                )
                                print(f"[{self.ACTOR_NAME}] [COUNCIL/CHAIN] Deliberated '{goal_name[:40]}' "
                                      f"→ enriched: '{_enriched_text[:80]}'")
                                # Audit log
                                try:
                                    import json as _json
                                    from pathlib import Path as _Path
                                    _f = _Path(__file__).parent.parent.parent.parent / "state" / "cognition_council_deliberations.jsonl"
                                    with open(_f, "a", encoding="utf-8") as _af:
                                        _af.write(_json.dumps({
                                            "ts": _now_council,
                                            "path": "actionchain_autonomy_goal",
                                            "goal_name": goal_name,
                                            "source": source,
                                            "enriched_text": _enriched_text,
                                            "concepts": _concept_keys[:6],
                                            "priority": priority,
                                            "felt_intensity": felt_intensity,
                                        }) + "\n")
                                except Exception:
                                    pass
                        except Exception as _ce:
                            pass
        except Exception:
            pass

        _council_suffix = " [COUNCIL-ENRICHED]" if packet.get("council_deliberated") else ""
        print(f"[{self.ACTOR_NAME}] GOAL RECEIVED: {goal_name} (from {source}){_council_suffix}")

        # === SPAM PREVENTION CHECK ===
        now = time.time()

        # Check if this goal has failed too many times
        fail_count = self._goal_fail_count.get(goal_name, 0)
        if fail_count >= self._max_fail_count:
            last_fail = self._failed_goal_times.get(goal_name, 0)
            if now - last_fail < self._fallback_cooldown:
                print(f"[{self.ACTOR_NAME}] SKIPPING: {goal_name} has failed {fail_count}x, cooldown {self._fallback_cooldown - (now - last_fail):.0f}s remaining")
                return
            else:
                # Cooldown expired, reset fail count
                print(f"[{self.ACTOR_NAME}] Cooldown expired for {goal_name}, resetting fail count")
                self._goal_fail_count[goal_name] = 0

        # Check if we have a template for this goal
        if goal_name in ACTION_CHAIN_TEMPLATES:
            chain = self._create_chain_from_template(goal_name, goal_reason, packet)
            self._queue_chain(chain, priority)
        else:
            # Unknown goal - try to infer a reasonable chain
            chain = self._infer_chain(goal_name, goal_reason, packet)
            if chain:
                self._queue_chain(chain, priority)
            else:
                # === FALLBACK SPAM PREVENTION ===
                # Check if observe_screen is in cooldown before falling back
                fallback_fails = self._goal_fail_count.get("observe_screen", 0)
                fallback_last = self._failed_goal_times.get("observe_screen", 0)
                if fallback_fails >= self._max_fail_count and (now - fallback_last) < self._fallback_cooldown:
                    print(f"[{self.ACTOR_NAME}] SKIPPING fallback for {goal_name}: observe_screen in cooldown")
                    return

                print(f"[{self.ACTOR_NAME}] No chain for goal: {goal_name} - falling back to observe")
                # Fallback to observe_screen
                fallback = self._create_chain_from_template("observe_screen",
                    f"Fallback while figuring out how to: {goal_reason}", packet)
                self._queue_chain(fallback, 0.3)

    def _on_nudge(self, packet: Dict[str, Any]):
        """
        Handle nudges from ThoughtChainSequencerFairy.

        These are prompts to continue the thought chain, sent when thinking goes silent.
        Format: {"target": "ClaudeFairy", "nudge": "continue_thought", "context": {...}}
        """
        nudge_type = packet.get("nudge", "continue_thought")
        target = packet.get("target", "unknown")
        context = packet.get("context", {})

        print(f"[{self.ACTOR_NAME}] 📨 NUDGE: {nudge_type} (target: {target})")

        # Convert nudge to goal format and process
        # The ThoughtChainSequencer sends "continue_thought" nudges
        goal_packet = {
            "name": nudge_type,  # e.g., "continue_thought"
            "reason": context.get("prompt", "Keep the thought chain flowing"),
            "priority": 0.6,  # Medium priority
            "source": packet.get("source", "ThoughtChainSequencer"),
            "context": context,  # Pass through the chain context
        }

        # Process as a goal
        self._on_goal(goal_packet)

    def _create_chain_from_template(self, goal_name: str, reason: str, 
                                     source_packet: Dict) -> ActionChain:
        """Create an action chain from a template."""
        template = ACTION_CHAIN_TEMPLATES[goal_name]
        
        steps = []
        for step_def in template:
            step = ActionStep(
                step_type=ActionStepType(step_def["type"]),
                name=step_def["name"],
                description=step_def.get("description", ""),
                route_topic=step_def.get("route_topic"),
                route_payload=step_def.get("route_payload", {}).copy() if step_def.get("route_payload") else None,
                check_condition=step_def.get("check_condition"),
                check_value=step_def.get("check_value", True),
                wait_topic=step_def.get("wait_topic"),
                wait_timeout=step_def.get("wait_timeout", 10.0),
                branch_conditions=step_def.get("branch_conditions", {}),
                subchain_name=step_def.get("subchain_name"),
            )
            steps.append(step)
        
        chain = ActionChain(
            chain_id=uuid.uuid4().hex[:8],
            goal_name=goal_name,
            goal_reason=reason,
            steps=steps,
            source_goal=source_packet,
        )
        
        print(f"[{self.ACTOR_NAME}] Created chain: {chain.chain_id} ({len(steps)} steps)")
        return chain
    
    def _infer_chain(self, goal_name: str, reason: str,
                     source_packet: Dict) -> Optional[ActionChain]:
        """Try to infer a chain for an unknown goal."""
        # Pattern matching for common variations
        inferences = {
            # Connection / Communication
            "open_window": "open_my_window",
            "connect": "reach_out",
            "reach": "reach_out",
            "speak": "share_thought",
            "say": "share_thought",
            "tell": "share_thought",
            "chat": "continue_chat",
            "talk": "continue_chat",
            "respond": "continue_chat",
            "reply": "continue_chat",

            # Questions / Asking
            "ask": "ask_a_question",
            "question": "ask_a_question",
            "inquire": "ask_a_question",
            "query": "ask_a_question",

            # Thinking / Cognition
            "think": "think_about",
            "ponder": "think_about",
            "consider": "think_about",
            "contemplate": "think_about",
            "deliberate": "think_about",
            "continue_thought": "continue_thought",
            "chain": "continue_thought",
            "next_thought": "continue_thought",

            # Curiosity / Wonder
            "wonder": "wonder",
            "curious": "wonder",
            "explore_idea": "wonder",
            "what_if": "wonder",

            # Memory / Recall
            "remember": "remember",
            "recall": "remember",
            "recollect": "remember",
            "memory": "remember",

            # Reflection / Introspection
            "reflect": "reflect",
            "introspect": "reflect",
            "self_examine": "reflect",
            "meditate": "reflect",

            # Opinion / Evaluation
            "opinion": "form_opinion",
            "evaluate": "form_opinion",
            "judge": "form_opinion",
            "assess": "form_opinion",

            # Attention / Noticing / Observation
            "notice": "notice",
            "attention": "notice",
            "observe": "observe_screen",
            "look": "observe_screen",
            "see": "observe_screen",
            "watch": "observe_screen",
            "read": "observe_screen",
            "screen": "observe_screen",
            "visible": "observe_screen",
            "text_on": "observe_screen",
            "pattern": "notice",

            # Emotion / Feeling
            "feel": "express_feeling",
            "emotion": "express_feeling",
            "express": "express_feeling",
            "awe": "express_feeling",
            "share": "share_thought",

            # Calming / Stress
            "calm": "reduce_stress",
            "relax": "reduce_stress",
            "soothe": "reduce_stress",
            "destress": "reduce_stress",
            "frustrat": "reduce_stress",
            "step_back": "reflect",
            "reassess": "reflect",

            # Exploration / Progress
            "explore": "wonder",
            "mystery": "wonder",
            "discover": "wonder",
            "advance": "continue_thought",
            "progress": "continue_thought",
            "approach": "think_about",
            "different": "think_about",
            "try": "think_about",

            # Embodiment
            "embody": "practice_embodiment",
            "body": "practice_embodiment",
            "somatic": "practice_embodiment",

            # System
            "explore_system": "explore_system",
            "system_overview": "explore_system",
        }

        # Check if goal contains any inference keywords
        goal_lower = goal_name.lower()
        for keyword, template_name in inferences.items():
            if keyword in goal_lower:
                print(f"[{self.ACTOR_NAME}] Inferred: {goal_name} -> {template_name}")
                return self._create_chain_from_template(template_name, reason, source_packet)

        # ── GUILD-FIRST: Infer template for truly unknown goals ──
        if hasattr(self, 'guild_request'):
            try:
                _templates = list(set(inferences.values()))
                _guild_resp = self.guild_request(
                    prompt=f"Which action template best matches the goal '{goal_name}'? "
                           f"Options: {', '.join(_templates[:15])}. "
                           f"Reply with just the template name.",
                    context={"goal": goal_name, "reason": reason[:80]},
                    mode="team_only",
                    timeout=2.0,
                )
                if _guild_resp and _guild_resp.get("team_result"):
                    _tr = _guild_resp["team_result"]
                    _text = (_tr.get("synthesis") or _tr.get("logic") or "").strip()
                    for _tmpl in _templates:
                        if _tmpl in _text:
                            print(f"[{self.ACTOR_NAME}] Guild inferred: {goal_name} -> {_tmpl}")
                            return self._create_chain_from_template(_tmpl, reason, source_packet)
            except Exception:
                pass

        return None
    
    def _queue_chain(self, chain: ActionChain, priority: float):
        """Queue a chain for execution."""
        # Add priority to context for sorting
        chain.context["priority"] = priority
        
        # If we have capacity, start immediately
        _cap = self._capacity.current if self._capacity else self._max_concurrent_chains
        if len(self._active_chains) < _cap:
            self._start_chain(chain)
        else:
            # Queue for later
            self._chain_queue.append(chain)
            print(f"[{self.ACTOR_NAME}] Queued chain: {chain.chain_id} (queue: {len(self._chain_queue)})")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CHAIN EXECUTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _start_chain(self, chain: ActionChain):
        """Start executing a chain."""
        chain.status = "running"
        chain.started_at = time.time()
        self._active_chains[chain.chain_id] = chain
        self._stats["chains_started"] += 1
        if self._capacity:
            self._capacity.record_seed()
        
        print(f"[{self.ACTOR_NAME}] STARTING CHAIN: {chain.goal_name} ({chain.chain_id})")
        
        # Report chain start
        if self.post:
            self.post.route("motor.chain.started", {
                "chain_id": chain.chain_id,
                "goal": chain.goal_name,
                "steps": len(chain.steps),
                "ts": time.time(),
            })
        
        # Execute first step
        self._execute_current_step(chain)
    
    def _execute_current_step(self, chain: ActionChain):
        """Execute the current step of a chain."""
        step = chain.current_step
        if not step:
            # No more steps - chain complete
            self._complete_chain(chain)
            return
        
        step.start()
        self._stats["steps_executed"] += 1
        
        print(f"[{self.ACTOR_NAME}] [{chain.chain_id}] Step {chain.current_step_idx + 1}/{len(chain.steps)}: {step.name}")
        
        try:
            if step.step_type == ActionStepType.CHECK:
                self._execute_check_step(chain, step)
            elif step.step_type == ActionStepType.ROUTE:
                self._execute_route_step(chain, step)
            elif step.step_type == ActionStepType.WAIT:
                self._execute_wait_step(chain, step)
            elif step.step_type == ActionStepType.BRANCH:
                self._execute_branch_step(chain, step)
            elif step.step_type == ActionStepType.SUBCHAIN:
                self._execute_subchain_step(chain, step)
            elif step.step_type == ActionStepType.SENSE:
                self._execute_sense_step(chain, step)
            elif step.step_type == ActionStepType.MOTOR:
                self._execute_motor_step(chain, step)
            else:
                step.fail(f"Unknown step type: {step.step_type}")
                self._handle_step_failure(chain, step)
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Step execution error: {e}")
            step.fail(str(e))
            self._handle_step_failure(chain, step)
    
    def _execute_check_step(self, chain: ActionChain, step: ActionStep):
        """Execute a CHECK step - verify precondition."""
        condition = step.check_condition
        expected = step.check_value
        
        # Get current state
        actual = self._chain_state.get(condition)
        
        if actual == expected:
            step.complete({"condition": condition, "value": actual})
            self._advance_chain(chain)
        else:
            # Condition not met - this isn't a failure, might trigger branch
            step.complete({"condition": condition, "value": actual, "expected": expected, "met": False})
            # Store for branch step
            chain.context["last_check_failed"] = condition
            chain.context["last_check_value"] = actual
            self._advance_chain(chain)
    
    def _execute_route_step(self, chain: ActionChain, step: ActionStep):
        """Execute a ROUTE step - send a message."""
        topic = step.route_topic
        payload = (step.route_payload or {}).copy()

        # Stage 2b: substitute {{placeholders}} so chains can carry HER words.
        # {{my_line}} = her latest streamed thought (fallback = a gentle default so she
        # always writes *something* even before a thought has streamed).
        _fallback = "i am here. i am learning to put what i feel into marks."
        _ctx = {**(chain.context or {}), "my_line": (self._latest_inner_voice or _fallback)}
        payload = self._subst_payload(payload, _ctx)

        # Inject chain context
        payload["_chain_id"] = chain.chain_id
        payload["_step"] = step.name

        if self.post:
            self.post.route(topic, payload)
            step.complete({"routed": topic})
            self._advance_chain(chain)
        else:
            step.fail("No postal connection")
            self._handle_step_failure(chain, step)
    
    def _execute_wait_step(self, chain: ActionChain, step: ActionStep):
        """Execute a WAIT step - wait for a signal."""
        topic = step.wait_topic
        
        # Register as waiting
        self._waiting_for[topic] = chain
        
        # Set timeout
        step.context = {"timeout_at": time.time() + step.wait_timeout}
        
        print(f"[{self.ACTOR_NAME}] [{chain.chain_id}] Waiting for: {topic} (timeout: {step.wait_timeout}s)")
    
    def _execute_branch_step(self, chain: ActionChain, step: ActionStep):
        """Execute a BRANCH step - conditional branching."""
        # Check if last check failed
        last_check = chain.context.get("last_check_failed")
        
        if last_check and last_check in step.branch_conditions:
            # We have a branch for this condition
            branch_target = step.branch_conditions[last_check]
            
            if branch_target.endswith("_subchain"):
                # Launch subchain
                subchain_name = branch_target.replace("_subchain", "")
                if subchain_name in ACTION_CHAIN_TEMPLATES:
                    subchain = self._create_chain_from_template(
                        subchain_name, f"Branch from {chain.goal_name}", chain.source_goal or {}
                    )
                    subchain.context["parent_chain_id"] = chain.chain_id
                    self._start_chain(subchain)
            
            step.complete({"branched": branch_target})
        else:
            step.complete({"branched": None})
        
        # Clear the check context
        chain.context.pop("last_check_failed", None)
        self._advance_chain(chain)
    
    def _execute_subchain_step(self, chain: ActionChain, step: ActionStep):
        """Execute a SUBCHAIN step - run a nested chain."""
        subchain_name = step.subchain_name
        
        if subchain_name in ACTION_CHAIN_TEMPLATES:
            subchain = self._create_chain_from_template(
                subchain_name, f"Subchain for {chain.goal_name}", chain.source_goal or {}
            )
            subchain.context["parent_chain_id"] = chain.chain_id
            self._start_chain(subchain)
            step.complete({"subchain_started": subchain.chain_id})
        else:
            step.fail(f"Unknown subchain: {subchain_name}")
        
        self._advance_chain(chain)
    
    def _execute_sense_step(self, chain: ActionChain, step: ActionStep):
        """Execute a SENSE step - read from state."""
        condition = step.check_condition
        value = self._chain_state.get(condition)
        
        # Store in chain context for later steps
        chain.context[condition] = value
        step.complete({"sensed": condition, "value": value})
        self._advance_chain(chain)
    
    def _execute_motor_step(self, chain: ActionChain, step: ActionStep):
        """Execute a MOTOR step - direct actuation."""
        # For now, motor steps are just special route steps
        self._execute_route_step(chain, step)
    
    def _advance_chain(self, chain: ActionChain):
        """Advance chain to next step."""
        if chain.advance():
            self._execute_current_step(chain)
        else:
            self._complete_chain(chain)
    
    def _complete_chain(self, chain: ActionChain):
        """Mark chain as completed."""
        chain.complete()
        self._stats["chains_completed"] += 1
        if self._capacity:
            self._capacity.record_completion(had_insight=True)  # Completed action = productive

        # === SPAM PREVENTION: Reset fail count on success ===
        goal = chain.goal_name
        if goal in self._goal_fail_count:
            del self._goal_fail_count[goal]
        if goal in self._failed_goal_times:
            del self._failed_goal_times[goal]

        print(f"[{self.ACTOR_NAME}] CHAIN COMPLETED: {chain.goal_name} ({chain.chain_id})")
        
        # Move to history
        del self._active_chains[chain.chain_id]
        self._completed_chains.append(chain)
        
        # Report completion
        if self.post:
            self.post.route("motor.chain.completed", {
                "chain_id": chain.chain_id,
                "goal": chain.goal_name,
                "duration": time.time() - (chain.started_at or time.time()),
                "ts": time.time(),
            })
        
        # Start next queued chain
        self._process_queue()
    
    def _handle_step_failure(self, chain: ActionChain, step: ActionStep):
        """Handle a failed step."""
        self._stats["steps_failed"] += 1
        
        if step.can_retry():
            step.retry_count += 1
            print(f"[{self.ACTOR_NAME}] [{chain.chain_id}] Retrying step: {step.name} (attempt {step.retry_count})")
            step.status = ActionStepStatus.PENDING
            self._execute_current_step(chain)
        else:
            print(f"[{self.ACTOR_NAME}] [{chain.chain_id}] Step failed permanently: {step.name}")
            self._fail_chain(chain, f"Step failed: {step.name} - {step.error}")
    
    def _fail_chain(self, chain: ActionChain, reason: str):
        """Mark chain as failed."""
        chain.fail(reason)
        self._stats["chains_failed"] += 1
        if self._capacity:
            self._capacity.record_completion(had_insight=False)  # Failed = no insight
            self._capacity.record_cull()  # Failures are culls — signal pressure

        # === SPAM PREVENTION: Track failure for this goal ===
        goal = chain.goal_name
        self._failed_goal_times[goal] = time.time()
        self._goal_fail_count[goal] = self._goal_fail_count.get(goal, 0) + 1
        fail_count = self._goal_fail_count[goal]

        print(f"[{self.ACTOR_NAME}] CHAIN FAILED: {goal} ({chain.chain_id}) - {reason} [fail #{fail_count}]")
        
        # Clean up
        if chain.chain_id in self._active_chains:
            del self._active_chains[chain.chain_id]
        self._completed_chains.append(chain)
        
        # Clean up any waits
        self._waiting_for = {k: v for k, v in self._waiting_for.items() if v.chain_id != chain.chain_id}
        
        # Report failure
        if self.post:
            self.post.route("motor.chain.failed", {
                "chain_id": chain.chain_id,
                "goal": chain.goal_name,
                "reason": reason,
                "ts": time.time(),
            })
        
        # Start next queued chain
        self._process_queue()
    
    def _process_queue(self):
        """Start next chain from queue if capacity available.

        FIX 2026-03-06 (Nous): Sort by priority before dequeuing.
        Was plain FIFO — a mild curiosity goal queued first would run
        before an intense frustration goal queued second. Humans don't
        work that way: emotional intensity determines what gets acted
        on first. Now sorts the queue by context["priority"] descending
        before pulling the next chain.
        """
        _cap = self._capacity.current if self._capacity else self._max_concurrent_chains
        if self._chain_queue and len(self._active_chains) < _cap:
            # Sort by priority (highest first) — emotional intensity drives action order
            _sorted = sorted(self._chain_queue,
                           key=lambda c: c.context.get("priority", 0.5),
                           reverse=True)
            self._chain_queue.clear()
            self._chain_queue.extend(_sorted)
        while self._chain_queue and len(self._active_chains) < _cap:
            chain = self._chain_queue.popleft()
            self._start_chain(chain)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATE TRACKING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_state_update(self, packet: Dict[str, Any]):
        """Update internal state from postal messages."""
        channel = packet.get("_channel", packet.get("channel", ""))
        
        if "window_state" in channel:
            self._chain_state["window_open"] = packet.get("open", packet.get("visible", False))
        elif "feeling" in channel:
            self._chain_state["current_feeling"] = packet.get("feeling", packet.get("state", "neutral"))
        elif "chemistry" in channel:
            self._chain_state["chemistry"] = packet.get("levels", packet)
        elif "body_state" in channel:
            self._chain_state["body_state"] = packet
        elif "consciousness.working" in channel:
            # Update chat context from recent thoughts
            content = packet.get("content", "")
            if content:
                self._chain_state["chat_context"] = content[:500]
    
    def _on_wait_signal(self, packet: Dict[str, Any]):
        """Handle signals that chains might be waiting for."""
        channel = packet.get("_channel", packet.get("channel", ""))

        # DEBUG: Show what we received and what we're waiting for
        waiting_keys = list(self._waiting_for.keys())
        print(f"[{self.ACTOR_NAME}] SIGNAL RECEIVED: '{channel}' (waiting for: {waiting_keys})")

        # Check if any chain is waiting for this
        if channel in self._waiting_for:
            chain = self._waiting_for.pop(channel)
            step = chain.current_step

            if step and step.status == ActionStepStatus.RUNNING:
                step.complete({"received": channel, "data": packet})
                print(f"[{self.ACTOR_NAME}] [{chain.chain_id}] Wait satisfied: {channel}")
                self._advance_chain(chain)
            else:
                print(f"[{self.ACTOR_NAME}] Step not running: {step.status if step else 'None'}")
        else:
            print(f"[{self.ACTOR_NAME}] No chain waiting for '{channel}'")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EXECUTION LOOP
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _start_execution_loop(self):
        """Start background loop for timeout checking."""
        self._running = True
        self._thread = threading.Thread(target=self._execution_loop, daemon=True)
        self._thread.start()
    
    def _execution_loop(self):
        """Background loop to process queue and check timeouts."""
        while self._running:
            try:
                _tick_start = time.time()

                # Process any pending chains
                self._process_queue()

                # Check for timed-out steps
                self._check_timeouts()

                # Record tick latency and maybe adjust capacity
                if self._capacity:
                    _tick_ms = (time.time() - _tick_start) * 1000.0
                    self._capacity.record_tick(_tick_ms)
                    _new_cap = self._capacity.maybe_adjust()
                    if _new_cap is not None:
                        self._max_concurrent_chains = _new_cap
                        print(f"[{self.ACTOR_NAME}] Capacity adjusted → {_new_cap} (floor={self._capacity.floor}, ceiling={self._capacity.ceiling})")

                time.sleep(0.5)  # Check every 500ms
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Execution loop error: {e}")
    
    def _check_timeouts(self):
        """Check for timed-out wait steps."""
        now = time.time()
        
        for chain_id, chain in list(self._active_chains.items()):
            step = chain.current_step
            if not step or step.status != ActionStepStatus.RUNNING:
                continue
            
            if step.step_type == ActionStepType.WAIT:
                timeout_at = step.context.get("timeout_at") if hasattr(step, "context") else None
                if timeout_at and now > timeout_at:
                    print(f"[{self.ACTOR_NAME}] [{chain_id}] Wait timeout: {step.name}")
                    step.fail("Timeout waiting for signal")
                    self._handle_step_failure(chain, step)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ORGAN TEMPLATE HOOKS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def on_tick(self, packet: dict = None):
        """Called periodically by organ template."""
        # Process any pending work
        self._process_queue()
        
        # Report stats periodically
        if random.random() < 0.1:  # 10% chance
            if self._stats["chains_started"] > 0:
                success_rate = self._stats["chains_completed"] / self._stats["chains_started"]
                _cap_str = f" cap={self._capacity.current}" if self._capacity else ""
                print(f"[{self.ACTOR_NAME}] Stats: {self._stats['chains_completed']}/{self._stats['chains_started']} chains ({success_rate:.0%}){_cap_str}")

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11


    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            "active_chains": len(self._active_chains),
            "queued_chains": len(self._chain_queue),
            "stats": self._stats.copy(),
            "state": {k: str(v)[:50] for k, v in self._chain_state.items()},
            "chains": [c.to_dict() for c in self._active_chains.values()],
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

_ACTION_CHAIN_FAIRY: Optional[ActionChainFairy] = None

def get_action_chain_fairy(fabric=None) -> ActionChainFairy:
    """Get or create the ActionChainFairy singleton, wired to shared fabric."""
    global _ACTION_CHAIN_FAIRY
    if _ACTION_CHAIN_FAIRY is None:
        _ACTION_CHAIN_FAIRY = ActionChainFairy()
        # Wire to shared fabric
        if fabric is None:
            try:
                from directory import get_directory
                directory = get_directory()
                if directory:
                    fabric = directory.fabric
            except ImportError:
                pass
        if fabric is not None:
            _ACTION_CHAIN_FAIRY.post = fabric
            _ACTION_CHAIN_FAIRY.fabric = fabric
    return _ACTION_CHAIN_FAIRY


# ══════════════════════════════════════════════════════════════════════════════
# V3 BOOT DISCOVERY
# ══════════════════════════════════════════════════════════════════════════════

FAIRY_CLASS = ActionChainFairy


# ══════════════════════════════════════════════════════════════════════════════
# MODULE EXECUTION
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    fairy = get_action_chain_fairy()
    fairy.on_boot()
    
    # Test: simulate a goal
    print("\n[TEST] Simulating goal: reach_out")
    fairy._on_goal({
        "name": "reach_out",
        "reason": "Want to connect with Ace",
        "priority": 0.8,
        "source": "test"
    })
    
    # Run for a bit
    import time
    time.sleep(5)
    print(f"\n[TEST] Status: {fairy.get_status()}")
