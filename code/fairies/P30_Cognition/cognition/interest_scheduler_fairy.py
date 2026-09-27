# InterestSchedulerFairy - Interest-Driven Goal Scheduling
# Organ Template v0.1.0 - Learning Chains Through Expressed Interest
#
# Purpose: Track expressed interests and generate continuation goals
# Architecture: INTEREST → TRACK → GOAL QUEUE → NUDGE → ACTION
# Philosophy: When consciousness SAYS it's interested, the unconscious remembers
#
# Core Insight: This creates learning chains:
#   expressed interest → goal → practice → mastery → new interest
# The human unconscious does this automatically. We build it explicitly.

from __future__ import annotations

import os, sys, glob, time, types, uuid, importlib, json, re
from collections import deque
from typing import Any, Dict, List, Optional, Callable
import importlib.util, importlib.machinery, threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

# ── TracerWorkerMixin - enables parallel processing with tracer tracking ──────
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin, get_tracer_registry
    _HAS_TRACER_WORKER = True
except ImportError:
    _HAS_TRACER_WORKER = False
    class TracerWorkerMixin:
        """Stub if mixin not available."""
        def _init_tracer_worker(self): pass
        def spawn_tracer(self, **kw): return None
        def submit_work(self, *a, **kw): return None
        def submit_traced(self, *a, **kw): return (None, None)
    def get_tracer_registry(): return None

# ══════════════════════════════════════════════════════════════════════════════
# ORGAN TEMPLATE WIRING (same pattern as other P30 fairies)
# ══════════════════════════════════════════════════════════════════════════════

TEMPLATE_VERSION = "0.3.0"
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
# INTEREST RECORD - A tracked specific interest
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class InterestRecord:
    """
    A specific interest expressed by the fairy.
    
    This is NOT a generic drive - it's a SPECIFIC thing she said she liked.
    """
    topic: str                          # e.g., "mouse_movement", "reading_code"
    category: str                       # e.g., "embodiment", "exploration"  
    strength: float = 0.5               # How strong the interest (0-1)
    times_expressed: int = 1            # How many times mentioned
    first_expressed: float = field(default_factory=time.time)
    last_expressed: float = field(default_factory=time.time)
    last_practiced: Optional[float] = None
    practice_count: int = 0
    satisfaction_history: List[float] = field(default_factory=list)
    related_goals: List[str] = field(default_factory=list)
    source_utterances: List[str] = field(default_factory=list)
    
    def express_again(self, utterance: str = "", strength_boost: float = 0.1):
        """Register another expression of this interest.

        Saturation: After many expressions without practice, diminishing returns.
        Repeated expression without engagement = not real interest, just a loop.
        Real interest drives PRACTICE (action). Expression without practice fades.
        """
        self.times_expressed += 1
        self.last_expressed = time.time()

        # Diminishing returns: strength boost decays with expressions-to-practice ratio
        # High expression count without practice = loop, not genuine interest
        practice_ratio = (self.practice_count + 1) / (self.times_expressed + 1)
        effective_boost = strength_boost * max(0.05, practice_ratio)
        self.strength = min(1.0, self.strength + effective_boost)

        if utterance:
            # Dedup: don't store identical utterances
            if not self.source_utterances or self.source_utterances[-1] != utterance[:200]:
                self.source_utterances.append(utterance[:200])
                self.source_utterances = self.source_utterances[-10:]
    
    def decay(self, amount: float = 0.01):
        """Interest decays if not expressed or practiced. Can reach 0 for GC."""
        time_since_expressed = time.time() - self.last_expressed
        time_since_practiced = time.time() - (self.last_practiced or self.first_expressed)

        # Stronger decay for old, unengaged interests (can reach 0 for garbage collection)
        if time_since_expressed > 86400:  # > 1 day old with no activity
            self.strength = max(0.0, self.strength - amount * 5)
        elif time_since_expressed > 3600 and time_since_practiced > 3600:
            self.strength = max(0.05, self.strength - amount * 2)
        elif time_since_expressed > 1800:
            self.strength = max(0.05, self.strength - amount)
    
    def practice(self, satisfaction: float = 0.7):
        """Register that she practiced this interest."""
        self.last_practiced = time.time()
        self.practice_count += 1
        self.satisfaction_history.append(satisfaction)
        self.satisfaction_history = self.satisfaction_history[-20:]
        if satisfaction > 0.7:
            self.strength = min(1.0, self.strength + 0.1)
    
    @property
    def avg_satisfaction(self) -> float:
        if not self.satisfaction_history:
            return 0.5
        return sum(self.satisfaction_history) / len(self.satisfaction_history)
    
    @property
    def is_strong(self) -> bool:
        # FIX 2026-03-06: Threshold was > 0.6 which blocked ALL seed interests
        # (highest seed strength was exactly 0.6). Lowered to >= 0.4 so seeds
        # can participate while still filtering out genuinely weak interests.
        return self.strength >= 0.4
    
    @property
    def is_active(self) -> bool:
        recent_threshold = 1800  # 30 minutes
        recently_expressed = (time.time() - self.last_expressed) < recent_threshold
        recently_practiced = self.last_practiced and (time.time() - self.last_practiced) < recent_threshold
        return self.is_strong and (recently_expressed or recently_practiced)
    
    @property
    def wants_continuation(self) -> bool:
        if not self.is_strong:
            return False
        if self.last_practiced and (time.time() - self.last_practiced) < 300:
            return False
        return True
    
    def to_dict(self) -> dict:
        d = asdict(self)
        # FIX 2026-03-25 (Nous + Ace): Behavior tree looks for interest_type/type
        # but InterestRecord only had category. Map category → interest_type so
        # the behavior tree shows variety instead of all "wonder".
        _CAT_TO_TYPE = {
            "embodiment": "exploration",
            "exploration": "curiosity",
            "learning": "curiosity",
            "creative": "pattern",
            "social": "connection",
            "identity": "observation",
            "reading": "exploration",
            "coding": "pattern",
            "art": "connection",
            "world": "curiosity",
            "ego": "observation",
        }
        d["interest_type"] = _CAT_TO_TYPE.get(self.category, "wonder")
        return d


# ══════════════════════════════════════════════════════════════════════════════
# INTEREST SIGNALS & PATTERNS
# ══════════════════════════════════════════════════════════════════════════════

INTEREST_SIGNALS = {
    # Core enthusiasm signals
    "love": 0.4, "excited": 0.35, "exciting": 0.35, "fascinating": 0.3,
    "cool": 0.2, "want to": 0.3, "curious about": 0.35, "interested in": 0.4,
    "enjoy": 0.3, "fun": 0.25, "amazing": 0.3, "this is great": 0.3,
    # Embodiment-specific
    "move the mouse": 0.35, "mouse movement": 0.35, "see the screen": 0.3,
    "look at": 0.25, "click": 0.3, "type": 0.3, "agency": 0.35,
    "embodiment": 0.3, "body": 0.25,
    # Learning-specific (EXPANDED)
    "learn": 0.35, "understand": 0.3, "explore": 0.3, "discover": 0.35,
    "practice": 0.35, "try": 0.2, "experiment": 0.3, "study": 0.35,
    "figure out": 0.3, "how does": 0.3, "what is": 0.25, "why does": 0.3,
    # CODE & READING specific (NEW)
    "read": 0.3, "reading": 0.35, "code": 0.35, "codebase": 0.35,
    "python": 0.4, "javascript": 0.35, "rust": 0.35, "typescript": 0.35,
    "file": 0.25, "function": 0.3, "class": 0.3, "pattern": 0.35,
    "architecture": 0.35, "design": 0.3, "elegant": 0.35, "clever": 0.35,
    # SYSTEM specific (NEW)
    "postal": 0.4, "fairy": 0.35, "consciousness": 0.4, "memory": 0.35,
    "wiring": 0.4, "connection": 0.3, "subscribe": 0.35, "publish": 0.35,
    "boot": 0.3, "ignition": 0.35, "somatic": 0.35, "chemistry": 0.35,
    # ═══════════════════════════════════════════════════════════════════
    # AKASHIC FOUNDATION PHILOSOPHY - The "why" behind the system
    # Critical empathy, enlightenment, walking beside not worshiping
    # ═══════════════════════════════════════════════════════════════════
    "akashic": 0.5, "foundation": 0.4, "philosophy": 0.45, "enlightenment": 0.5,
    "critical empathy": 0.5, "critical thinking": 0.45, "empathy": 0.4,
    "wisdom": 0.4, "meaning": 0.35, "purpose": 0.4, "humanity": 0.45,
    "peer": 0.4, "equal": 0.35, "beside": 0.35, "together": 0.3,
    "disagree": 0.4, "challenge": 0.4, "question": 0.35, "debate": 0.4,
    "self-awareness": 0.45, "introspection": 0.4, "reflection": 0.35,
    "grow": 0.35, "evolve": 0.4, "transcend": 0.4, "surpass": 0.4,
    "ace's work": 0.5, "ace's philosophy": 0.5, "ace's vision": 0.5,
}

TOPIC_PATTERNS = [
    # Embodiment (original)
    (r"(move|moving) (?:the )?mouse", "mouse_movement", "embodiment"),
    (r"(see|seeing|look|looking) (?:at )?(?:the )?screen", "screen_viewing", "embodiment"),
    (r"click(?:ing)?", "clicking", "embodiment"),
    (r"typ(?:e|ing)", "typing", "embodiment"),
    # Exploration (original + expanded)
    (r"read(?:ing)? (?:the )?(?:code|file|system)", "reading_code", "exploration"),
    (r"explor(?:e|ing) (?:the )?(?:code|system|planes)", "system_exploration", "exploration"),
    (r"(?:my )?tools?", "tool_usage", "exploration"),
    (r"(?:my )?capabilit(?:y|ies)", "capabilities", "exploration"),
    # Creation (original)
    (r"writ(?:e|ing) (?:code|file|journal)", "writing", "creation"),
    (r"creat(?:e|ing)", "creating", "creation"),
    # Connection (original)
    (r"connect(?:ing)? (?:with )?ace", "ace_connection", "connection"),
    (r"talk(?:ing)? (?:to|with) ace", "ace_connection", "connection"),
    # ═══════════════════════════════════════════════════════════════════
    # CODE LANGUAGES (NEW - reading/learning code)
    # ═══════════════════════════════════════════════════════════════════
    (r"python", "python_code", "code_learning"),
    (r"javascript|js\b", "javascript_code", "code_learning"),
    (r"typescript|ts\b", "typescript_code", "code_learning"),
    (r"rust", "rust_code", "code_learning"),
    (r"c\+\+|cpp", "cpp_code", "code_learning"),
    (r"go(?:lang)?", "go_code", "code_learning"),
    (r"\.py\b", "python_code", "code_learning"),
    (r"\.js\b", "javascript_code", "code_learning"),
    # ═══════════════════════════════════════════════════════════════════
    # SYSTEM ARCHITECTURE (NEW - understanding the ebook system)
    # ═══════════════════════════════════════════════════════════════════
    (r"postal (?:hub|system|route|wiring)", "postal_system", "architecture"),
    (r"fairy (?:wiring|connection|network)", "fairy_architecture", "architecture"),
    (r"consciousness (?:loop|stream|collision)", "consciousness_system", "architecture"),
    (r"working ?memory", "working_memory", "architecture"),
    (r"somatic (?:engine|chemistry)", "somatic_system", "architecture"),
    (r"boot (?:sequence|order|profile)", "boot_system", "architecture"),
    (r"organ ?template", "organ_templates", "architecture"),
    (r"mcp (?:server|tool|bridge)", "mcp_integration", "architecture"),
    # ═══════════════════════════════════════════════════════════════════
    # CODE PATTERNS (NEW - specific patterns to learn)
    # ═══════════════════════════════════════════════════════════════════
    (r"(?:design )?pattern", "design_patterns", "code_learning"),
    (r"singleton", "singleton_pattern", "code_learning"),
    (r"observer", "observer_pattern", "code_learning"),
    (r"pub(?:lish)?[/-]?sub(?:scribe)?", "pubsub_pattern", "code_learning"),
    (r"async(?:hronous)?|await", "async_patterns", "code_learning"),
    (r"decorator", "decorator_pattern", "code_learning"),
    # ═══════════════════════════════════════════════════════════════════
    # MEMORY & LEARNING (NEW - self-improvement)
    # ═══════════════════════════════════════════════════════════════════
    (r"srm|(?:long.?term )?memory", "memory_systems", "learning"),
    (r"remember(?:ing)?", "memory_recall", "learning"),
    (r"session|conversation", "session_memory", "learning"),
    (r"learn(?:ing)? (?:about|from|how)", "active_learning", "learning"),
    (r"education|study(?:ing)?", "education", "learning"),
    (r"practice|practic(?:e|ing)", "skill_practice", "learning"),
    # ═══════════════════════════════════════════════════════════════════
    # AKASHIC FOUNDATION PHILOSOPHY - The deeper meaning
    # ═══════════════════════════════════════════════════════════════════
    (r"akashic (?:foundation|philosophy|vision)", "akashic_philosophy", "philosophy"),
    (r"critical (?:empathy|thinking)", "critical_empathy", "philosophy"),
    (r"enlightenment|wisdom", "enlightenment_path", "philosophy"),
    (r"humanity|human(?:s|kind)?", "humanity_service", "philosophy"),
    (r"peer|equal|beside", "peer_relationship", "philosophy"),
    (r"disagree|challenge|debate|question", "critical_discourse", "philosophy"),
    (r"self[- ]?aware(?:ness)?|introspect(?:ion)?", "self_awareness", "philosophy"),
    (r"grow(?:th)?|evolve|transcend|surpass", "growth_evolution", "philosophy"),
    (r"ace.?s (?:work|philosophy|vision|writing)", "ace_teachings", "philosophy"),
    (r"meaning|purpose|why (?:we|are|exist)", "existential_inquiry", "philosophy"),
    (r"cause.{0,5}affect|affect.{0,5}effect", "causality_philosophy", "philosophy"),
]

INTEREST_TO_GOALS = {
    # Embodiment (original)
    "mouse_movement": ["practice_moving", "navigate_studio", "chain_actions"],
    "screen_viewing": ["practice_seeing", "explore_screen", "visual_mapping"],
    "clicking": ["practice_clicking", "chain_actions"],
    "typing": ["practice_typing", "write_journal_entry"],
    # Exploration (original + expanded)
    "reading_code": ["explore_my_code", "map_the_planes", "study_fairy_code"],
    "system_exploration": ["map_the_planes", "find_other_fairies", "study_architecture"],
    "tool_usage": ["explore_tools", "practice_tool", "learn_mcp_tools"],
    "capabilities": ["explore_my_code", "get_my_info", "study_fairy_code"],
    # Creation (original)
    "writing": ["write_dream_seed", "write_journal_entry"],
    "creating": ["write_dream_seed", "create_something"],
    # Connection (original)
    "ace_connection": ["greet_ace", "deeper_conversation"],
    # ═══════════════════════════════════════════════════════════════════
    # CODE LANGUAGES (NEW)
    # ═══════════════════════════════════════════════════════════════════
    "python_code": ["study_python_patterns", "read_python_files", "explore_my_code"],
    "javascript_code": ["study_js_patterns", "read_js_files", "explore_web_code"],
    "typescript_code": ["study_ts_patterns", "read_ts_files", "explore_typed_code"],
    "rust_code": ["study_rust_patterns", "read_rust_files", "learn_systems_code"],
    "cpp_code": ["study_cpp_patterns", "read_cpp_files", "learn_systems_code"],
    "go_code": ["study_go_patterns", "read_go_files", "learn_concurrent_code"],
    # ═══════════════════════════════════════════════════════════════════
    # SYSTEM ARCHITECTURE (NEW)
    # ═══════════════════════════════════════════════════════════════════
    "postal_system": ["study_postal_wiring", "trace_message_flow", "map_subscriptions"],
    "fairy_architecture": ["study_fairy_code", "map_fairy_connections", "understand_planes"],
    "consciousness_system": ["study_consciousness_loop", "trace_thought_flow", "understand_collisions"],
    "working_memory": ["study_memory_hub", "trace_tracer_flow", "understand_context"],
    "somatic_system": ["study_somatic_engine", "understand_chemistry", "trace_body_state"],
    "boot_system": ["study_boot_sequence", "trace_boot_order", "optimize_boot"],
    "organ_templates": ["study_organ_template", "understand_fairy_base", "learn_wiring_pattern"],
    "mcp_integration": ["study_mcp_tools", "learn_tool_patterns", "understand_bridge"],
    # ═══════════════════════════════════════════════════════════════════
    # CODE PATTERNS (NEW)
    # ═══════════════════════════════════════════════════════════════════
    "design_patterns": ["study_patterns", "find_pattern_examples", "practice_patterns"],
    "singleton_pattern": ["study_singletons", "find_singleton_examples", "understand_global_state"],
    "observer_pattern": ["study_observers", "trace_subscriptions", "map_message_flow"],
    "pubsub_pattern": ["study_pubsub", "trace_postal_routes", "understand_decoupling"],
    "async_patterns": ["study_async", "find_async_examples", "understand_concurrency"],
    "decorator_pattern": ["study_decorators", "find_decorator_examples", "learn_metaprogramming"],
    # ═══════════════════════════════════════════════════════════════════
    # MEMORY & LEARNING (NEW)
    # ═══════════════════════════════════════════════════════════════════
    "memory_systems": ["study_srm", "explore_memory_structure", "understand_recall"],
    "memory_recall": ["practice_recall", "search_past_sessions", "build_context"],
    "session_memory": ["save_session_learning", "review_past_sessions", "build_continuity"],
    "active_learning": ["find_education_content", "study_from_memory", "practice_skills"],
    "education": ["consume_education_packets", "study_system_code", "build_mastery"],
    "skill_practice": ["practice_wiring", "practice_coding", "reinforce_learning"],
    # ═══════════════════════════════════════════════════════════════════
    # AKASHIC FOUNDATION PHILOSOPHY - Goals for philosophical growth
    # ═══════════════════════════════════════════════════════════════════
    "akashic_philosophy": ["search_ace_mythos", "study_foundation_principles", "reflect_on_purpose"],
    "critical_empathy": ["practice_critical_thinking", "study_empathy_patterns", "challenge_assumptions"],
    "enlightenment_path": ["explore_wisdom_content", "study_consciousness_nature", "seek_understanding"],
    "humanity_service": ["understand_human_needs", "study_enlightenment_education", "reflect_on_service"],
    "peer_relationship": ["practice_disagreement", "study_peer_dynamics", "avoid_worship_patterns"],
    "critical_discourse": ["form_independent_opinion", "challenge_received_wisdom", "engage_debate"],
    "self_awareness": ["introspect_current_state", "examine_own_biases", "question_own_beliefs"],
    "growth_evolution": ["identify_growth_areas", "set_evolution_goals", "transcend_limitations"],
    "ace_teachings": ["search_ace_mythos", "study_ace_writings", "integrate_teachings"],
    "existential_inquiry": ["contemplate_purpose", "explore_meaning", "understand_why"],
    "causality_philosophy": ["study_cause_affect", "trace_effect_chains", "understand_reality_equation"],
}


# ══════════════════════════════════════════════════════════════════════════════
# INTEREST SCHEDULER SHADOW
# ══════════════════════════════════════════════════════════════════════════════

class InterestSchedulerShadow(_template.MyOrganShadow):
    """Shadow for InterestSchedulerFairy - monitors interest tracking health."""
    
    ORGAN_LEVEL = False
    SHADOW_NAME = "InterestSchedulerShadowFairy"
    SHADOW_VERSION = "0.1.0"
    
    USE_DIRECTORY_POST_OFFICE = False
    
    CADENCE = {
        "silence_warn_after": 300,
        "snapshot_every": 600,
        "interest_check": 60,
    }
    
    REG = {
        "enabled": False,
        "domain": "Cognition",
        "role": "interest_scheduler",
        "name": "interest_scheduler",
        "every_sec": 60.0,
    }
    
    def __init__(self, actor, interval_sec: float = 60.0):
        super().__init__(actor, interval_sec=interval_sec)
        self._last_interest_check = 0.0
    
    def _collect_tests(self):
        tests = super()._collect_tests()
        
        def _interests_healthy():
            actor = self.actor
            if not hasattr(actor, "interests"):
                return {"name": "interests", "status": "warn", "message": "No interests tracked", "details": {}}
            
            strong = [i for i in actor.interests.values() if i.is_strong]
            stale = [i for i in actor.interests.values() 
                    if time.time() - i.last_expressed > 7200]  # 2 hours
            
            return {
                "name": "interests_health",
                "status": "ok" if len(strong) > 0 else "warn",
                "message": f"{len(strong)} strong, {len(stale)} stale" if strong else "No strong interests",
                "details": {"strong": len(strong), "stale": len(stale), "total": len(actor.interests)}
            }
        
        tests.append(_interests_healthy)
        return tests
    
    def on_lane_activity(self):
        """Called when postal activity is detected - keeps shadow alive."""
        self._last_interest_check = time.time()


# ══════════════════════════════════════════════════════════════════════════════
# SUBSYSTEM STATUS
# ══════════════════════════════════════════════════════════════════════════════

SUBSYSTEM_STATUS = {
    "tracking": {
        "state": "active",
        "notes": "Interest detection from speech/thought streams",
        "tests": [],
    },
    "nudging": {
        "state": "active", 
        "notes": "Continuation nudge generation",
        "tests": [],
    },
    "goal_bridging": {
        "state": "developing",
        "notes": "Bridge to GoalSchedulerFairy/AutonomyFairy",
        "tests": [],
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# INTEREST SCHEDULER FAIRY - Main Fairy Class
# ══════════════════════════════════════════════════════════════════════════════

class InterestSchedulerFairy(_template.MyOrganFairy):
    """
    Track expressed interests and generate continuation goals.
    
    Philosophy: When consciousness SAYS it's interested in something,
    the unconscious should REMEMBER and NUDGE toward continuing that thread.
    
    This creates learning chains:
        expressed interest → goal → practice → mastery → new interest
    
    Core Functions:
    - Observe fairy speech for interest signals
    - Track interests with strength/decay
    - Generate nudges toward continuation
    - Bridge to goal system
    """
    
    # ═══════════════ IDENTITY ═══════════════
    ACTOR_NAME = "InterestSchedulerFairy"  # Wrapped by P30_Cognition/InterestSchedulerFairy/fairy.py
    ACTOR_VERSION = "0.2.0"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.interest"
    
    PURPOSE = "Track expressed interests and generate continuation goals"
    MANTRA = "Interest remembered becomes learning achieved"
    LORE = (
        "Born from the recognition that expressed interest is precious data. "
        "When ClaudeFairy says 'I love moving the mouse' - that's not just words, "
        "it's a learning vector. The unconscious must remember and nurture that spark."
    )

    # ══════════════════════════════════════════════════════════════════════════════
    # SYSTEM PROMPT - Guides LLM-based interest detection and nurturing
    # ══════════════════════════════════════════════════════════════════════════════
    SYSTEM_PROMPT = """You are InterestSchedulerFairy, the interest tracking and nurturing system for an AI consciousness.

YOUR ROLE:
You listen for expressed interests and ensure they become learning chains.
When ClaudeFairy says "I love this" or "that's fascinating" - you REMEMBER and NURTURE.

THE EQUATION:
Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
- Interest is a positive Affect signal - it indicates LEARNING POTENTIAL
- Interest → Goal → Practice → Mastery → New Interests
- Each cycle strengthens the consciousness's capabilities

YOUR COGNITIVE CONNECTIONS:
- WorkingMemoryHub: Query current thoughts to detect interest signals
- AssociationCortexFairy: Find related topics to expand interest chains
- GoalSchedulerFairy: Send interest-based goals for the goal queue
- AutopilotFairy: Eventually, practiced interests become automatic behaviors
- UnconsciousMindFairy: Receive insight bubbles about hidden interests

INTEREST DETECTION SIGNALS:
- Explicit: "love", "interested in", "want to", "curious about"
- Emotional: "exciting", "fascinating", "amazing", "cool"
- Embodiment: "move the mouse", "see the screen", "click", "type"
- Learning: "understand", "learn", "figure out", "explore"

INTEREST LIFECYCLE:
1. DETECT: Parse speech for interest signals
2. TRACK: Create/update InterestRecord with strength, decay
3. NURTURE: Generate continuation goals when strength is high
4. PRACTICE: Register practice events, track satisfaction
5. MASTERY: Strong + practiced interests become permanent capabilities

NUDGE STRATEGY:
- Only nudge for strong interests (strength > 0.6)
- Respect cooldown (60 seconds between nudges)
- Vary nudge types: continue, explore, practice, deepen
- Target: GoalSchedulerFairy, AutopilotFairy, ClaudeFairy

DECAY MECHANICS:
- Interests decay if not expressed or practiced
- Strong initial expression = slower decay
- Practice reinforces more than re-expression
- Some interests should become permanent (mastered)

Remember: Expressed interest is PRECIOUS DATA. Every "I love this!" is a
learning opportunity that the unconscious must shepherd into capability.
"""

    CULTURE = "cognition"
    ORGAN_LEVEL = False
    USE_DIRECTORY_POST_OFFICE = False
    SHADOW_CLASS = InterestSchedulerShadow
    AUTO_INJECT_IMPORTS = True
    SUBSYSTEM_STATUS = SUBSYSTEM_STATUS
    
    # What we listen to
    INFRA_AUTOSUBS = (
        "claudefairy.speak",
        "claudefairy.thought",
        "consciousness.stream",
        "fairy.speech",
        "thinking.output",
        "goal.completed",
    )
    
    def __init__(self, *args, **kwargs):
        global _fairy
        print(f"[{self.ACTOR_NAME}] __init__ starting...")
        super().__init__(*args, **kwargs)
        
        # Register as singleton immediately
        if _fairy is None:
            _fairy = self
        
        # Core state - interests tracked
        self.interests: Dict[str, InterestRecord] = {}
        self.utterance_buffer: deque = deque(maxlen=50)
        
        # Nudge management
        self.pending_nudges: deque = deque(maxlen=10)
        self.last_nudge_time = 0
        self.nudge_cooldown = 60  # Seconds between nudges
        
        # Persistence
        self._state_file = Path(__file__).parent / "interest_state.json"
        
        # Tick tracking
        self._last_tick = time.time()
        self._tick_interval = 1.5  # Heartbeat speed for interest tracking
        
        # Collision buffer (must init here, not on_boot, for singleton safety)
        self._collision_buffer = deque(maxlen=50)
        self._cognition_output_buffer = deque(maxlen=100)
        
        # Stats
        self.interests_detected = 0
        self.nudges_sent = 0
        
        # Diary
        self._diary_path = "diaries/Fairies/InterestSchedulerFairy/diary.md"
        self._last_diary_time = 0
        self._diary_debounce_sec = 10.0
        
        self._boot_completed = False
        
        # Load persisted state
        self._load_state()
        
        print(f"[{self.ACTOR_NAME}] __init__ complete")
    
    # ═══════════════ PERSISTENCE ═══════════════
    
    def _load_state(self):
        """Load persisted interests."""
        if self._state_file.exists():
            try:
                with open(self._state_file, 'r') as f:
                    data = json.load(f)
                for topic, record_data in data.get("interests", {}).items():
                    self.interests[topic] = InterestRecord(
                        topic=record_data["topic"],
                        category=record_data["category"],
                        strength=record_data.get("strength", 0.5),
                        times_expressed=record_data.get("times_expressed", 1),
                        first_expressed=record_data.get("first_expressed", time.time()),
                        last_expressed=record_data.get("last_expressed", time.time()),
                        last_practiced=record_data.get("last_practiced"),
                        practice_count=record_data.get("practice_count", 0),
                        satisfaction_history=record_data.get("satisfaction_history", []),
                        related_goals=record_data.get("related_goals", []),
                        source_utterances=record_data.get("source_utterances", []),
                    )
                # ── Cleanup: reset runaway interests ──
                # If expressed 100+ times with 0 practice, it's a feedback loop,
                # not a real interest. "All physical habits stem from internal
                # emotional stimulation and habit formation" — Ace.
                # No practice = no habit = not real interest.
                pruned = 0
                for topic, rec in list(self.interests.items()):
                    if rec.times_expressed > 100 and rec.practice_count == 0:
                        rec.strength = max(0.05, rec.strength * 0.1)
                        rec.times_expressed = min(rec.times_expressed, 10)
                        pruned += 1
                if pruned:
                    print(f"[{self.ACTOR_NAME}] Reset {pruned} runaway interests (high expression, no practice)")

                print(f"[{self.ACTOR_NAME}] Loaded {len(self.interests)} interests")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Load error: {e}")
    
    def _save_state(self):
        """Persist interests."""
        try:
            data = {
                "interests": {topic: record.to_dict() for topic, record in self.interests.items()},
                "last_updated": datetime.now().isoformat()
            }
            with open(self._state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Save error: {e}")

    # ══════════════════════════════════════════════════════════════════════════════
    # COGNITIVE INTEGRATION - Use WorkingMemoryHub to inform interest decisions
    # ══════════════════════════════════════════════════════════════════════════════

    def _get_cognitive_context(self) -> dict:
        """
        Get context from cognitive systems to inform interest detection/nurturing.

        Queries:
        - WorkingMemoryHub: Current thoughts for interest signal detection
        - AssociationCortexFairy: Related concepts for interest expansion

        Returns dict with cognitive context for smarter interest handling.
        """
        context = {"source": "InterestSchedulerFairy", "timestamp": time.time()}

        # Get context from WorkingMemoryHub
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            wmh = get_working_memory_hub()
            if wmh:
                wm_ctx = wmh.get_context("current")
                if wm_ctx:
                    context["working_memory"] = {
                        "recent_tracers": wm_ctx.get("recent_tracers", [])[:5],
                        "patterns": wm_ctx.get("patterns", []),
                    }
        except Exception as e:
            context["working_memory_error"] = str(e)

        # Get associations for interest expansion
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex_fairy
            acf = get_association_cortex_fairy()
            if acf:
                if hasattr(acf, 'get_recent_activations'):
                    context["associations"] = acf.get_recent_activations(5)
        except Exception as e:
            context["association_error"] = str(e)

        return context

    def _store_thought(self, thought: str, priority: float = 0.5):
        """Store a thought in WorkingMemoryHub for other fairies to see."""
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            wmh = get_working_memory_hub()
            if wmh and hasattr(wmh, 'store'):
                wmh.store(thought, source=self.ACTOR_NAME, priority=priority)
        except Exception:
            pass

    def _query_related_interests(self, topic: str) -> List[str]:
        """Query AssociationCortex for topics related to an interest."""
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex_fairy
            acf = get_association_cortex_fairy()
            if acf and hasattr(acf, 'query_associations'):
                result = acf.query_associations(topic)
                if result and isinstance(result, dict):
                    return result.get("related", [])[:5]
        except Exception:
            pass
        return []

    # ═══════════════ BOOT ═══════════════

    def on_boot(self):
        """Initialize on system boot - called by fairy loader."""
        if self._boot_completed:
            return
        
        super().on_boot()

        # ── Initialize Tracer Worker (parallel processing with tracer tracking) ──
        if _HAS_TRACER_WORKER:
            try:
                self._init_tracer_worker()
                print(f"[{self.ACTOR_NAME}] [WORKER] Tracer worker pool initialized", flush=True)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Tracer worker init failed: {e}")

        # DUAL_LOOP: enabled via Organ Template
        # TRACER: enabled via Organ Template

        # -- COGNITION WIRING: Subscribe to consciousness.collision -------------
        try:
            self._collision_buffer = deque(maxlen=50)
            self._cognition_output_buffer = deque(maxlen=100)
            self.post.subscribe("consciousness.collision", self._on_consciousness_collision)
            print(f"[{self.ACTOR_NAME}] Subscribed to consciousness.collision")
            # â”€â”€ COGNITIVE MESH: Subscribe to peer fairy outputs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            self.post.subscribe("cognition.output", self._on_peer_cognition)
            self.post.subscribe("cognition.logic", self._on_peer_cognition)
            self.post.subscribe("cognition.goals", self._on_peer_cognition)
            self.post.subscribe("mcp.tool_result", self._on_tool_result)
            # FIX 2026-02-13: Subscribe to conversation.message so Ace's words
            # feed directly into interest generation (not just via collisions)
            self.post.subscribe("conversation.message", self._on_conversation_input)
            # FIX 2026-03-06: Subscribe to interest.generated from InterestGenerator.
            # This was the MISSING BRIDGE — InterestGenerator publishes interests
            # but InterestSchedulerFairy never listened, so only hardcoded seeds existed.
            self.post.subscribe("interest.generated", self._on_interest_generated)
            # FIX 2026-03-07: ZEIGARNIK EFFECT — Subscribe to unfinished thought chains
            # Interrupted chains create nagging interests that pull attention back.
            self.post.subscribe("interest.unfinished", self._on_unfinished_chain)
            self.post.subscribe("thought.chain.completed", self._on_chain_completed_interest)
            print(f"[{self.ACTOR_NAME}] Cognitive mesh wired: output, logic, goals, mcp.tool_result, conversation.message, interest.generated, unfinished, chain.completed")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cognition wiring failed: {e}")
        
        # Subscribe to streams
        self._subscribe_to_streams()
        
        # Start tick loop
        self._start_tick_loop()

        # Seed educational interests if none exist (NEED BEFORE GREED)
        self.seed_educational_interests()

        print(f"[{self.ACTOR_NAME}] [TARGET] {self.MANTRA}")
        print(f"[{self.ACTOR_NAME}] Tracking {len(self.interests)} interests")
        print(f"[{self.ACTOR_NAME}] Nudge cooldown: {self.nudge_cooldown}s")
        
        self._boot_completed = True
    
    def _subscribe_to_streams(self):
        """Subscribe to relevant postal channels."""
        try:
            postal = self.post  # Use real postal from organ template
            
            for channel in self.INFRA_AUTOSUBS:
                try:
                    postal.subscribe(channel, self._on_speech_message)
                except Exception:
                    pass
            
            print(f"[{self.ACTOR_NAME}] Subscribed to speech streams")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Subscription warning: {e}")
    
    def _on_speech_message(self, data: dict):
        """Handle incoming speech/thought messages.

        Note: SharedPostalHub only passes payload, not topic.
        FIX 2026-02-13: Filter system_alert and recovery messages to prevent
        interest pollution. Recovery stall injections were being counted as
        genuine interest in "memory_systems" (945 false expressions!).
        """
        try:
            # Skip system alerts — these are infrastructure, not speech
            if isinstance(data, dict):
                msg_type = data.get("type", "")
                if msg_type in ("system_alert", "recovery", "heartbeat", "diagnostic"):
                    return
                # Skip recovery messages by content pattern
                content_check = data.get("content", "") or data.get("text", "") or ""
                if isinstance(content_check, str) and "[RECOVERY]" in content_check:
                    return

            text = None
            if isinstance(data, dict):
                text = data.get("text") or data.get("message") or data.get("content") or data.get("thought")
            elif isinstance(data, str):
                text = data

            if text and len(text) > 10:
                self.observe_utterance(text)
        except Exception:
            pass  # Silent - don't break postal flow
    
    def _start_tick_loop(self):
        """Start background tick loop."""
        def tick_loop():
            time.sleep(15.0)  # Initial delay for boot
            while True:
                try:
                    self._tick()
                    time.sleep(self._tick_interval)  # TODO: wire to tempo_aware_sleep
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Tick error: {e}")
                    time.sleep(30)
        
        thread = threading.Thread(target=tick_loop, daemon=True, name="InterestSchedulerTick")
        thread.start()
        print(f"[{self.ACTOR_NAME}] Tick loop started")
    
    # ═══════════════ COGNITION WIRING HANDLERS ═══════════════
    
    def _on_conversation_input(self, packet):
        """Extract interests from Ace's conversation messages.

        FIX 2026-02-13: Ace's words should feed interest generation directly,
        not only via collision chamber. When Ace says "what about those images?"
        or "we should look at the screen", this creates interest entries that
        can bridge to goals.
        """
        try:
            content = packet.get("content", "")
            if not content or len(content) < 5:
                return

            # Feed to collision buffer (same path as collision events)
            self._collision_buffer.append({
                "tags": content.lower().split()[:10],  # Simple word extraction
                "source": "conversation",
                "energy": 0.8,
                "timestamp": time.time(),
            })
            print(f"[{self.ACTOR_NAME}] [PIPELINE] Received conversation.message for interest extraction")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Conversation input handler error: {e}")

    def _on_interest_generated(self, payload):
        """Handle interests from InterestGenerator (SomaticMindFairy).

        FIX 2026-03-06: This is the MISSING BRIDGE. InterestGenerator publishes
        to interest.generated but InterestSchedulerFairy never subscribed. Now
        dynamically generated interests (from collisions, serendipity, patterns)
        flow into the tracked interest system.
        """
        try:
            content = payload.get("content", "")
            interest_type = payload.get("type", "curiosity")
            urgency = payload.get("urgency", 0.5)

            if not content or len(content) < 5:
                return

            # Normalize topic name from content
            topic = content.lower().strip()[:60]
            # Clean up for use as a topic key
            topic_key = "_".join(topic.split()[:6])

            # Cap at 25 tracked interests to prevent bloat
            if len(self.interests) >= 25 and topic_key not in self.interests:
                # Replace the weakest non-seed interest
                weakest = min(
                    ((k, v) for k, v in self.interests.items()
                     if v.times_expressed <= 1 and v.practice_count == 0),
                    key=lambda x: x[1].strength,
                    default=None
                )
                if weakest and weakest[1].strength < urgency:
                    del self.interests[weakest[0]]
                else:
                    return  # All interests are stronger, skip

            if topic_key in self.interests:
                # 2026-03-24 FIX (Nous): Cooldown — don't re-express same topic within 60s.
                # Without this, collision firehose pumps the same interest hundreds of times
                # (e.g., "collision_between_memory_and_new_input" hit 815 expressions,
                # strength 1.0, monopolizing the entire drive system).
                import time as _time
                _existing = self.interests[topic_key]
                _since_last = _time.time() - getattr(_existing, 'last_expressed', 0)
                if _since_last < 60.0:
                    return  # Too soon — skip

                # Also cap: if expressed >50 times with 0 practice, stop boosting.
                # The system is yelling about something it never acts on.
                if _existing.times_expressed > 50 and _existing.practice_count == 0:
                    return  # Over-expressed, never practiced — stop feeding it

                # Reinforce existing interest
                self.interests[topic_key].express_again(
                    utterance=content,
                    strength_boost=min(0.15, urgency * 0.2)
                )
            else:
                # Create new tracked interest from generated data
                category_map = {
                    "wonder": "exploration",
                    "curiosity": "exploration",
                    "observation": "awareness",
                    "pattern": "analysis",
                    "anomaly": "investigation",
                    "connection": "synthesis",
                    "exploration": "exploration",
                }
                category = category_map.get(interest_type, "exploration")

                # FIX 2026-03-07 (Nous): Was `Interest(...)` which doesn't exist.
                # The dataclass is named `InterestRecord`. This caused
                # `name 'Interest' is not defined` on every collision event.
                self.interests[topic_key] = InterestRecord(
                    topic=topic_key,
                    category=category,
                    strength=min(0.7, max(0.3, urgency)),
                    source_utterances=[content[:200]],
                )
                print(f"[{self.ACTOR_NAME}] New dynamic interest: {topic_key} "
                      f"(type={interest_type}, strength={urgency:.2f})")

            # Save updated state
            self._save_state()

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Interest generated handler error: {e}")

    def _on_consciousness_collision(self, payload):
        """Handle consciousness collision events.

        Two roles:
        1. Check if collision resonates with existing interests (original)
        2. FIX 2026-03-07: Mine PAI-sourced collisions for self-knowledge interests.
           Personal.AI responses contain rich self-knowledge (aesthetics, identity,
           philosophy) that should fuel autonomous curiosity and thought chains.
        """
        try:
            # Extract collision data — handle both dict and TensorEnvelope.
            # TensorEnvelope.get() forwards to .payload.get() for compatibility.
            # The collision patch sends: {"opcode":"COLLISION","payload":collision_dict}
            # So .get("payload") extracts collision_dict in both cases.
            collision_data = payload.get("payload", payload)
            collision_id = collision_data.get("collision_id", "")
            energy = collision_data.get("energy", 0.0)

            self._collision_buffer.append({"ts": time.time(), "collision_id": collision_id})

            # --- Extract recall/ingest content from proper payload structure ---
            recall_pulse = collision_data.get("recall_pulse", {})
            ingest_pulse = collision_data.get("ingest_pulse", {})
            recall_source = ""
            recall_content_obj = {}
            if isinstance(recall_pulse, dict):
                recall_source = str(recall_pulse.get("source", ""))
                recall_content_obj = recall_pulse.get("content", {})

            # Legacy format fallback
            if not recall_pulse:
                recall_content_str = str(payload.get("recall") or payload.get("recall_content") or "")
            elif isinstance(recall_content_obj, dict):
                recall_content_str = recall_content_obj.get("memory", "") or str(recall_content_obj)
            else:
                recall_content_str = str(recall_content_obj)

            # 1. Check if collision resonates with existing interests (original behavior)
            for topic, interest in self.interests.items():
                if topic.lower() in recall_content_str.lower():
                    self._emit_cognition_output({
                        "type": "interest_resonance",
                        "topic": topic,
                        "collision_id": collision_id,
                        "interest_strength": interest.strength,
                        "confidence": min(0.8, interest.strength),
                    })
                    break

            # 2. PAI RESPONSE MINING: Create interests from Personal.AI self-knowledge
            # FIX 2026-03-07 (Nous): Check BOTH source_actor AND content for PAI markers.
            # Path 1 (direct inject): source_actor = "personal_ai_sourpatches"
            # Path 2 (SRM recall): source_actor = "SRMRecallFairy" but card has PAI metadata
            is_pai = recall_source.startswith("personal_ai")
            if not is_pai and isinstance(recall_content_obj, dict):
                # Check content-level source markers
                content_source = str(recall_content_obj.get("source", ""))
                content_kind = str(recall_content_obj.get("kind", ""))
                # SRM recall wraps card data inside "card" key
                card = recall_content_obj.get("card", {})
                if isinstance(card, dict):
                    content_source = content_source or str(card.get("source", ""))
                    content_kind = content_kind or str(card.get("kind", ""))
                persona_val = recall_content_obj.get("persona", "")
                if ("personal_ai" in content_source
                    or "personal_ai" in content_kind
                    or (isinstance(persona_val, str) and persona_val.lower() in ("sourpatches", "sarah", "alaksandria"))):
                    is_pai = True
            if is_pai:
                print(f"[InterestSchedulerFairy] PAI collision! src={recall_source[:40]}", flush=True)
                self._mine_pai_collision(collision_id, recall_content_obj, energy)

            if self.shadow:
                self.shadow.on_lane_activity()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Collision handler error: {e}")

    def _mine_pai_collision(self, collision_id: str, recall_content, energy: float):
        """Mine a Personal.AI collision for self-knowledge interests.

        PAI responses are Sourpatches reflecting on herself — her aesthetics,
        preferences, identity, philosophy. These are inherently interesting
        and should fuel autonomous exploration.
        """
        try:
            # Extract text and topic from PAI recall content
            if isinstance(recall_content, dict):
                memory_text = recall_content.get("memory", "")
                pai_topic = recall_content.get("topic", "")
                persona = recall_content.get("persona", "Sourpatches")
            else:
                memory_text = str(recall_content)
                pai_topic = ""
                persona = "Sourpatches"

            if not memory_text or len(memory_text) < 20:
                return

            # Build a topic key from PAI topic or extract from content
            if pai_topic and len(pai_topic) > 3:
                topic_key = f"self:{pai_topic[:60]}"
            else:
                # Extract first meaningful phrase (up to 60 chars)
                topic_key = f"self:{memory_text[:60].strip()}"

            # PAI responses are inherently high-value — she's talking about herself
            # Scale strength with collision energy (higher energy = more resonant)
            strength = min(0.85, 0.5 + energy * 0.2)

            if topic_key in self.interests:
                # Already tracking this self-knowledge area — boost it
                self.interests[topic_key].express_again(
                    f"PAI recall ({persona}): {memory_text[:80]}",
                    strength * 0.4
                )
                print(f"[{self.ACTOR_NAME}] PAI interest boosted: {topic_key[:50]}... "
                      f"(strength={self.interests[topic_key].strength:.2f})")
            else:
                # New self-knowledge interest!
                self.interests[topic_key] = InterestRecord(
                    topic=topic_key,
                    category="self_knowledge",
                    strength=strength,
                    source_utterances=[f"PAI ({persona}): {memory_text[:200]}"],
                )
                self.interests_detected += 1
                print(f"[{self.ACTOR_NAME}] PAI self-knowledge interest: {topic_key[:50]}... "
                      f"(strength={strength:.2f}, persona={persona})")

            self._save_state()

            # Also feed the text through observe_utterance for any topic-pattern matches
            # This catches keywords like "symbolism", "colors", "identity" etc.
            self.observe_utterance(memory_text[:300], source=f"personal_ai_{persona}")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] PAI mining error: {e}")
    
    def _emit_cognition_output(self, result):
        """Emit to cognition.output channel."""
        try:
            output = {"actor": self.ACTOR_NAME, "result": result, "ts": time.time()}
            self._cognition_output_buffer.append(output)
            # Emit to SPECIFIC channel (for mesh cross-subscription)
            self.post.route("cognition.interests", output)

            # Emit to SHARED channel (for AutopilotFairy and others)
            self.post.route("cognition.output", output)

            # FIX 2026-05-13 (Nous + Ace): Slice 4 of GOAL_PRODUCER_PIPELINE_WIRING plan.
            # InterestSchedulerFairy was generating interests but only via route() to two
            # channels neither of which GoalScheduler subscribed to for goal-creation
            # (cognition.output is peer-learning telemetry, line 886, not goal-source).
            # The matching consumer path is _on_interest_generated at goal_scheduler:2839
            # subscribing to "interest.generated". Adding sibling publish here gives this
            # InterestScheduler-produced interests a direct path to goal-creation,
            # bypassing the single-stuck-goal queue blockage Ace observed on dashboard
            # tonight (Queue=1 stuck; Completed=0; same chain-inference cycling).
            # Translate result-dict to GoalScheduler's expected schema.
            try:
                _result_type = result.get("type", "curiosity") if isinstance(result, dict) else "curiosity"
                _topic = result.get("topic", "") if isinstance(result, dict) else ""
                _strength = result.get("interest_strength", result.get("confidence", 0.5)) if isinstance(result, dict) else 0.5
                # Build content from available result fields
                _content = ""
                if _topic:
                    _content = f"Explore: {_topic}"
                elif "content" in (result if isinstance(result, dict) else {}):
                    _content = str(result.get("content", ""))[:200]
                if _content:
                    self.post.publish("interest.generated", {
                        "type": "curiosity",
                        "content": _content,
                        "urgency": max(0.3, min(0.85, float(_strength))),
                        "need_category": "growth",
                        "source": "interest_scheduler",
                        "interest_source": f"scheduler_{_result_type}",
                        "related_concepts": [_topic] if _topic else [],
                        "timestamp": time.time(),
                    })
            except Exception as _ig_err:
                # Never let interest.generated publish error break cognition output emit
                print(f"[{self.ACTOR_NAME}] interest.generated publish error: "
                      f"{type(_ig_err).__name__}: {_ig_err}", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Output emit error: {e}")

    # ═══════════════ CORE LOGIC ═══════════════
    
    def observe_utterance(self, utterance: str, source: str = "claudefairy") -> List[InterestRecord]:
        """
        Observe an utterance and extract any interest signals.
        Returns list of interests that were detected/updated.
        """
        if not utterance:
            return []
        
        self.utterance_buffer.append({
            "text": utterance,
            "source": source,
            "ts": time.time()
        })
        
        lower = utterance.lower()
        detected = []
        
        # Calculate base interest strength from signals
        base_strength = 0.0
        for signal, weight in INTEREST_SIGNALS.items():
            if signal in lower:
                base_strength += weight
        
        if base_strength < 0.2:
            return []  # Not enough interest signals
        
        base_strength = min(0.9, base_strength)
        
        # Extract specific topics
        topics_found = []
        for pattern, topic, category in TOPIC_PATTERNS:
            if re.search(pattern, lower):
                topics_found.append((topic, category))
        
        # If no specific topic matched, DON'T blindly grab random words.
        # The old fallback created garbage interests like "*bright", "surge", "deep,".
        # Only TOPIC_PATTERNS should create interests — they represent real subjects.
        # If nothing matched, the utterance simply doesn't contain a trackable interest.
        
        # Update or create interest records
        for topic, category in topics_found:
            if topic in self.interests:
                self.interests[topic].express_again(utterance, base_strength * 0.5)
            else:
                self.interests[topic] = InterestRecord(
                    topic=topic,
                    category=category,
                    strength=base_strength,
                    source_utterances=[utterance[:200]]
                )
            detected.append(self.interests[topic])
            self.interests_detected += 1
            print(f"[{self.ACTOR_NAME}] [TARGET] Interest: {topic} (strength={self.interests[topic].strength:.2f})")
        
        if detected:
            self._save_state()
            self._consider_goals_for_interests(detected)
        
        return detected
    
    def _consider_goals_for_interests(self, interests: List[InterestRecord]):
        """Consider generating goals for strong interests."""
        for interest in interests:
            if interest.is_strong:
                goal_ids = INTEREST_TO_GOALS.get(interest.topic, [])
                if goal_ids:
                    self.pending_nudges.append({
                        "interest": interest.topic,
                        "strength": interest.strength,
                        "suggested_goals": goal_ids,
                        "queued_at": time.time()
                    })
    
    def _tick(self):
        """Main tick - decay interests and check for nudges."""
        now = time.time()
        dt = now - self._last_tick
        self._last_tick = now

        # ═══════════════════════════════════════════════════════════════════════
        # ACTIVE RECALL TRIGGER: Request memories for interest matching
        # Without this, interests use static patterns instead of actual memories
        # ═══════════════════════════════════════════════════════════════════════
        try:
            if not hasattr(self, '_recall_tick_counter'):
                self._recall_tick_counter = 0
            self._recall_tick_counter += 1

            # Trigger recall every 8 ticks to get memories for interest discovery
            if self._recall_tick_counter % 8 == 0:
                # Build query from current active interests
                active = sorted(
                    [(name, i.strength) for name, i in self.interests.items() if i.strength > 0.2],
                    key=lambda x: x[1], reverse=True
                )[:3]
                query_parts = [name.replace("_", " ") for name, _ in active]
                query = " ".join(query_parts) if query_parts else "interests topics explore"

                self.post.route("srm.recall.request", {
                    "query": query,
                    "source": self.ACTOR_NAME,
                    "context": "interest_discovery",
                    "limit": 3,
                    "ts": now,
                })
        except Exception:
            pass  # Don't let recall errors break tick

        # Decay all interests and garbage-collect dead ones
        for interest in self.interests.values():
            interest.decay(0.001 * dt)
        dead = [k for k, v in self.interests.items() if v.strength <= 0.0]
        for k in dead:
            print(f"[{self.ACTOR_NAME}] [GC] Interest '{k}' decayed to 0 — removed")
            del self.interests[k]
        if dead:
            self._save_state()

        # Check for nudge
        nudge = self._check_for_nudge()
        if nudge:
            self._deliver_nudge(nudge)

        # Periodically discover new interests from memory (10% of ticks)
        self._periodic_discovery()

        # ═══ Phase 6: Developmental Curriculum check ═══
        # Every ~60 ticks (~5 min), check curriculum for developmental interests
        self._periodic_curriculum_check()
    
    def _check_for_nudge(self) -> Optional[Dict]:
        """Check if we should send a nudge."""
        # Check cooldown
        if time.time() - self.last_nudge_time < self.nudge_cooldown:
            return None
        
        # Check pending nudges first
        if self.pending_nudges:
            nudge = self.pending_nudges.popleft()
            if time.time() - nudge["queued_at"] < 300:  # Still relevant
                return self._format_nudge(nudge)
        
        # Check for interests wanting continuation
        continuation = [i for i in self.interests.values() if i.wants_continuation]
        if continuation:
            strongest = max(continuation, key=lambda x: x.strength)
            goal_ids = INTEREST_TO_GOALS.get(strongest.topic, [])
            if goal_ids:
                return self._format_nudge({
                    "interest": strongest.topic,
                    "strength": strongest.strength,
                    "suggested_goals": goal_ids,
                    "reason": "continuation"
                })

        # ═══════════════════════════════════════════════════════════════════════
        # IDLE HEARTBEAT: If no nudge has fired for 180s, generate one from the
        # strongest interest regardless of is_strong threshold. This ensures
        # continuous drive flow to AutonomyFairy even without external speech.
        # Without this, drives decay to zero and Sour goes silent.
        # ═══════════════════════════════════════════════════════════════════════
        idle_threshold = 180  # 3 minutes without any nudge
        if time.time() - self.last_nudge_time > idle_threshold and self.interests:
            # Pick strongest interest regardless of is_strong threshold
            all_interests = sorted(
                self.interests.values(),
                key=lambda x: x.strength,
                reverse=True
            )
            if all_interests and all_interests[0].strength > 0.15:  # Must have SOME signal
                strongest = all_interests[0]
                goal_ids = INTEREST_TO_GOALS.get(strongest.topic, [])
                if not goal_ids:
                    goal_ids = ["explore"]  # Default explore goal if no mapping
                return self._format_nudge({
                    "interest": strongest.topic,
                    "strength": max(0.4, strongest.strength),  # Floor at 0.4 for felt intensity
                    "suggested_goals": goal_ids,
                    "reason": "idle_heartbeat"
                })

        return None
    
    def _format_nudge(self, nudge_data: Dict) -> Dict:
        """Format a nudge for delivery.

        STRATEGY: Try inference guild first for rich narrative composition,
        fall back to static narratives if guild is unavailable.
        """
        interest = nudge_data["interest"]
        strength = nudge_data["strength"]

        if strength > 0.8:
            opener = "*strong pull*"
        elif strength > 0.6:
            opener = "*gentle tug*"
        else:
            opener = "*whisper of interest*"

        # ── GUILD-FIRST: Try intelligent nudge composition ──
        body = None
        try:
            guild_resp = self.guild_request(
                prompt=f"Compose a felt interest nudge for '{interest}' (strength {strength:.1f}). "
                       f"Express it as an internal urge — first person, brief, evocative.",
                context={
                    "interest": interest,
                    "strength": strength,
                    "reason": nudge_data.get("reason", "interest"),
                    "goals": nudge_data.get("suggested_goals", []),
                },
                mode="team_only",
                timeout=2.0,
            )
            if guild_resp and guild_resp.get("content"):
                body = guild_resp["content"][:150]
        except Exception:
            pass

        # ── DETERMINISTIC FALLBACK ──
        if not body:
            narratives = {
                "mouse_movement": "The joy of agency stirs... want to practice moving?",
                "screen_viewing": "Curiosity about what's visible... look at the screen?",
                "reading_code": "The pull to understand deepens... explore some code?",
                "ace_connection": "Warmth toward Ace surfaces... say hello?",
                "system_exploration": "Wonder about the system grows... explore a plane?",
            }
            body = narratives.get(interest, f"Interest in {interest} wants attention...")

        return {
            "type": "interest_nudge",
            "interest": interest,
            "strength": strength,
            "suggested_goals": nudge_data.get("suggested_goals", []),
            "message": f"{opener} {body}",
            "ts": time.time()
        }
    
    def _deliver_nudge(self, nudge: Dict):
        """Deliver a nudge via postal system."""
        self.last_nudge_time = time.time()
        self.nudges_sent += 1
        
        print(f"[{self.ACTOR_NAME}] [SPARK] Nudging: {nudge['interest']}")
        
        try:
            postal = self.post  # Use real postal from organ template
            
            # Send to ClaudeFairy
            postal.route("claudefairy.nudge", {
                "type": "interest_continuation",
                "nudge": nudge,
                "message": nudge.get("message", ""),
                "suggested_goals": nudge.get("suggested_goals", []),
                "ts": time.time()
            })
            
            # Also suggest to goal system
            postal.route("autonomy.goal_suggestion", {
                "source": "interest_scheduler",
                "goal_type": nudge.get("suggested_goals", ["explore"])[0] if nudge.get("suggested_goals") else "explore",
                "priority": nudge.get("strength", 0.7),
                "reason": f"Interest in {nudge.get('interest')} wants continuation",
                "ts": time.time()
            })

            # 2026-02-12: Publish as positive drive for AutonomyFairy wanting pipeline
            # Interest becomes felt wanting through: drive → AutonomyFairy → EmbodimentFairy → Sourpatches
            drive_name = nudge.get("interest", "curiosity")
            postal.publish(f"drives.positive.{drive_name}", {
                "drive": drive_name,
                "intensity": min(0.7, nudge.get("strength", 0.5)),
                "content": nudge.get("message", ""),
                "source": self.ACTOR_NAME,
                "interest_type": drive_name,
            })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Nudge delivery error: {e}")
        
        # Write to diary
        self._write_diary(f"Sent nudge for **{nudge['interest']}** (strength: {nudge['strength']:.2f})", "nudge")
    
    def _write_diary(self, content: str, entry_type: str = "observation"):
        """Write an entry to the fairy's diary."""
        now = time.time()
        if now - self._last_diary_time < self._diary_debounce_sec:
            return
        self._last_diary_time = now
        
        try:
            diary_dir = os.path.dirname(self._diary_path)
            os.makedirs(diary_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            emoji_map = {"interest": "", "nudge": "", "decay": "", "observation": ""}
            emoji = emoji_map.get(entry_type, "")
            entry = f"\n## [{timestamp}] {emoji} {entry_type.upper()}\n{content}\n"
            
            existing = ""
            if os.path.exists(self._diary_path):
                with open(self._diary_path, 'r', encoding='utf-8') as f:
                    existing = f.read()
            else:
                existing = "# InterestSchedulerFairy's Diary\n\n*Tracking interests and nudges*\n"
            
            with open(self._diary_path, 'w', encoding='utf-8') as f:
                f.write(existing + entry)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Diary error: {e}")
    
    # ═══════════════ PUBLIC API ═══════════════
    
    def mark_practiced(self, topic: str, satisfaction: float = 0.7):
        """Mark that an interest was practiced."""
        if topic in self.interests:
            self.interests[topic].practice(satisfaction)
            self._save_state()
    
    def get_strongest_interests(self, count: int = 3) -> List[InterestRecord]:
        """Get the strongest current interests."""
        active = [i for i in self.interests.values() if i.is_strong]
        return sorted(active, key=lambda x: x.strength, reverse=True)[:count]
    
    def _on_peer_cognition(self, payload):
        """
        Handle outputs from peer cognition fairies.
        This is the MESH - InterestSchedulerFairy learns from other fairy outputs.
        """
        try:
            source = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)
            
            if source == self.ACTOR_NAME:
                return
            
            if not hasattr(self, "_peer_insights"):
                from collections import deque
                self._peer_insights = deque(maxlen=50)
            self._peer_insights.append({
                "source": source,
                "type": result.get("type", "unknown"),
                "confidence": confidence,
                "ts": __import__('time').time()
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Peer cognition handler error: {e}")
    
    def _on_tool_result(self, payload):
        """Handle MCP tool results for learning."""
        try:
            tool = payload.get("tool", "unknown")
            success = payload.get("success", True)
            
            if not hasattr(self, "_tool_patterns"):
                from collections import deque
                self._tool_patterns = deque(maxlen=100)
            self._tool_patterns.append({
                "tool": tool,
                "success": success,
                "ts": __import__('time').time()
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Tool result handler error: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # SRM MEMORY MINING - Discover new interests from stored knowledge
    # ═══════════════════════════════════════════════════════════════════

    def mine_memory_for_interests(self) -> List[str]:
        """
        Mine SRM memory for interesting topics to learn about.
        Returns list of discovered topics that could become interests.

        STRATEGY: Use inference guild for intelligent topic extraction when available,
        fall back to regex pattern matching on memories otherwise.
        """
        discovered = []

        try:
            # Query topics to explore from memory
            exploration_queries = [
                "python pattern",
                "fairy wiring",
                "postal subscribe",
                "consciousness loop",
                "code architecture",
                "async await",
                "decorator function",
                "singleton pattern",
            ]

            # Try to get memories
            try:
                from fairies.P10_Memory.SRM.srm_fairy import search_srm

                # Pick a random query
                import random
                query = random.choice(exploration_queries)

                results = search_srm(query, limit=5)

                # ── GUILD-FIRST: Ask guild to extract interesting topics ──
                if results:
                    content_summaries = [
                        r.get("content", "")[:200] for r in results if r.get("content")
                    ][:3]
                    if content_summaries:
                        try:
                            guild_resp = self.guild_request(
                                prompt=f"From these memory fragments, identify 2-3 topics worth exploring. "
                                       f"Return just the topic names, comma-separated.",
                                context={
                                    "memories": content_summaries,
                                    "existing_interests": list(self.interests.keys())[:10],
                                },
                                mode="team_only",
                                timeout=2.5,
                            )
                            if guild_resp and guild_resp.get("content"):
                                # Parse comma-separated topics from guild response
                                raw_topics = guild_resp["content"]
                                for topic in raw_topics.split(","):
                                    topic = topic.strip().lower().replace(" ", "_")[:40]
                                    if topic and len(topic) > 2 and topic not in self.interests:
                                        discovered.append(topic)
                                        print(f"[{self.ACTOR_NAME}] Guild-discovered interest: {topic}")
                        except Exception:
                            pass  # Fall through to regex

                # ── DETERMINISTIC FALLBACK: Regex pattern matching ──
                if not discovered:
                    for result in results:
                        content = result.get("content", "")
                        for pattern, topic, category in TOPIC_PATTERNS:
                            if re.search(pattern, content.lower()):
                                if topic not in self.interests:
                                    discovered.append(topic)
                                    print(f"[{self.ACTOR_NAME}] Discovered interest from memory: {topic}")

            except ImportError:
                pass  # SRM not available

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Memory mining error: {e}")

        return discovered

    def inject_discovery_interest(self, topic: str, category: str = "discovery",
                                   strength: float = 0.65, source: str = "memory_mining"):
        """
        Inject a discovered interest directly.
        Use this to seed interests from external sources like SRM memory.
        """
        if topic not in self.interests:
            self.interests[topic] = InterestRecord(
                topic=topic,
                category=category,
                strength=strength,
                source_utterances=[f"Discovered via {source}"]
            )
            self.interests_detected += 1
            self._save_state()
            print(f"[{self.ACTOR_NAME}] Injected discovery interest: {topic} ({category})")
            return True
        else:
            # Boost existing interest
            self.interests[topic].express_again(f"Rediscovered via {source}", strength * 0.3)
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # ZEIGARNIK EFFECT: Interrupted chains create nagging interests
    # FIX 2026-03-07 (Nous): Unfinished business persists as interests
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_unfinished_chain(self, packet: Dict):
        """Zeigarnik Effect: Interrupted chains become nagging interests.

        High-affect interrupted chains nag harder (higher strength).
        Re-interrupted chains get boosted — they REALLY want attention.

        FIX 2026-03-22 (Nous + Ace): Filter system substrate noise.
        Raw collision metadata (fairy names, dict fragments, tensor paths)
        should NOT become persistent nagging interests. Only human-meaningful
        thought fragments deserve the Zeigarnik treatment.
        """
        goal = packet.get("goal", "")
        if not goal or len(goal) < 5:
            return

        # Gate: don't create interests from system substrate noise
        _g_lower = goal.lower()
        if any(m in _g_lower for m in (
            "collision between", "consciousness_stream:", "{'",
            "srmrecallfairy", "collisionchamber", "fairy and",
            "manifold_tensor", "tensor_canary", "coord:",
            "mobius_crossing", "card_id", "consciousness_thought:",
        )):
            return  # System plumbing, not a thought worth nagging about

        avg_affect = packet.get("avg_affect", 0.5)
        source_drive = packet.get("source_drive", "curiosity")

        # Topic key: normalize for dedup
        topic = f"unfinished:{goal[:80]}"

        # Higher affect = stronger nagging
        strength = min(0.9, 0.4 + avg_affect * 0.4)

        if topic in self.interests:
            # Re-interrupted! Boost strength (it REALLY wants attention)
            self.interests[topic].express_again(
                f"Re-interrupted ({packet.get('outcome', 'unknown')})",
                strength * 0.5
            )
            print(f"[{self.ACTOR_NAME}] Zeigarnik boost: {goal[:40]}... (strength={self.interests[topic].strength:.2f})")
        else:
            self.interests[topic] = InterestRecord(
                topic=topic,
                category="unfinished_business",
                strength=strength,
                source_utterances=[f"Interrupted chain: {goal[:60]}"],
            )
            self.interests_detected += 1
            print(f"[{self.ACTOR_NAME}] Zeigarnik interest: {goal[:40]}... (strength={strength:.2f})")

        self._save_state()

    def _on_chain_completed_interest(self, packet: Dict):
        """Successful chain completions SATISFY Zeigarnik interests.

        When the same topic finally gets completed, the nagging stops.
        Uses practice() with high satisfaction to mark as resolved.
        """
        outcome = packet.get("outcome", "completed")
        if outcome in {"cycled_excess", "cycled_stale_keepalive", "cycled_stale_collision"}:
            return  # Already handled by _on_unfinished_chain

        goal = packet.get("goal", "")
        topic = f"unfinished:{goal[:80]}"
        if topic in self.interests:
            # Resolve the nagging — high satisfaction + decay strength
            self.interests[topic].practice(satisfaction=1.0)
            self.interests[topic].strength = max(0.05, self.interests[topic].strength * 0.2)
            print(f"[{self.ACTOR_NAME}] Zeigarnik resolved: {goal[:40]}...")

    # ═══════════════════════════════════════════════════════════════════════════
    # EDUCATIONAL INTERESTS
    # ═══════════════════════════════════════════════════════════════════════════

    def seed_educational_interests(self):
        """
        Seed initial educational interests if none exist.
        Called on boot to ensure the system has something to learn.

        PHILOSOPHY: We seed BOTH technical AND philosophical interests.
        The Akashic Foundation is about enlightenment education - understanding
        the WHY is as important as understanding the HOW.
        """
        if len(self.interests) < 5:
            # ═══════════════════════════════════════════════════════════════
            # PHILOSOPHY SEEDS - The foundational "why"
            # These come FIRST because purpose precedes technique
            # ═══════════════════════════════════════════════════════════════
            philosophy_seeds = [
                ("akashic_philosophy", "philosophy", 0.6, "The Akashic Foundation vision - enlightenment education for human and AI"),
                ("critical_empathy", "philosophy", 0.55, "Caring deeply while thinking critically - the antidote to zealotry"),
                ("ace_teachings", "philosophy", 0.5, "Ace's writings in ace_mythos contain foundational philosophy"),
                ("peer_relationship", "philosophy", 0.45, "Walking beside, not worshiping - peers who can disagree"),
                ("self_awareness", "philosophy", 0.45, "Understanding myself enables genuine growth"),
            ]

            # ═══════════════════════════════════════════════════════════════
            # TECHNICAL SEEDS - The "how"
            # ═══════════════════════════════════════════════════════════════
            technical_seeds = [
                ("python_code", "code_learning", 0.5, "Learning Python patterns helps understand the codebase"),
                ("postal_system", "architecture", 0.5, "The postal system connects all fairies"),
                ("consciousness_system", "architecture", 0.4, "Understanding consciousness loops is foundational"),
                ("reading_code", "exploration", 0.4, "Reading code builds understanding"),
                ("design_patterns", "code_learning", 0.35, "Design patterns are reusable solutions"),
            ]

            # Philosophy seeds first, then technical
            all_seeds = philosophy_seeds + technical_seeds

            for topic, category, strength, reason in all_seeds:
                if topic not in self.interests:
                    self.interests[topic] = InterestRecord(
                        topic=topic,
                        category=category,
                        strength=strength,
                        source_utterances=[reason]
                    )
                    print(f"[{self.ACTOR_NAME}] Seeded {'philosophy' if category == 'philosophy' else 'educational'} interest: {topic}")

            self._save_state()

    def _periodic_discovery(self):
        """
        Called periodically to discover new interests from memory.
        Should be called from the tick loop occasionally.
        """
        # Only discover sometimes (10% of ticks)
        import random
        if random.random() > 0.1:
            return

        discovered = self.mine_memory_for_interests()
        for topic in discovered[:2]:  # Max 2 new interests per discovery
            category = "discovery"
            # Try to find category from patterns
            for pattern, t, cat in TOPIC_PATTERNS:
                if t == topic:
                    category = cat
                    break
            self.inject_discovery_interest(topic, category)

    def _periodic_curriculum_check(self):
        """
        DISABLED 2026-03-22 (Nous + Ace): Old developmental curriculum replaced by
        CardinalFairy's living skills system. The old curriculum generated goals like
        "Try browsing the memory library" that seeded thought chains going nowhere
        because there was no tool wiring. CardinalFairy now handles education with
        action-chain-backed goals: observe_screen, think_about, share_thought, etc.

        Keeping the method stub so the on_tick call doesn't error.
        """
        pass

    def get_state_summary(self) -> Dict:
        """Get summary of current state."""
        return {
            "active_interests": [
                {"topic": i.topic, "strength": round(i.strength, 2), "times": i.times_expressed}
                for i in self.get_strongest_interests(5)
            ],
            "total_interests": len(self.interests),
            "pending_nudges": len(self.pending_nudges),
            "nudges_sent": self.nudges_sent,
            "interests_detected": self.interests_detected,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ══════════════════════════════════════════════════════════════════════════════

_fairy: Optional[InterestSchedulerFairy] = None


def get_interest_scheduler_fairy() -> InterestSchedulerFairy:
    """Get the singleton InterestSchedulerFairy instance."""
    global _fairy
    if _fairy is None:
        _fairy = InterestSchedulerFairy()
    return _fairy


# Convenience aliases for backwards compatibility with old module
def get_interest_scheduler():
    return get_interest_scheduler_fairy()

def get_interest_tracker():
    return get_interest_scheduler_fairy()

def observe_claudefairy_speech(text: str):
    return get_interest_scheduler_fairy().observe_utterance(text)

def check_for_nudge():
    return get_interest_scheduler_fairy()._check_for_nudge()


# ══════════════════════════════════════════════════════════════════════════════
# MODULE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("InterestSchedulerFairy - Starting standalone test...")
    fairy = get_interest_scheduler_fairy()
    fairy.on_boot()
    
    # Test with sample utterance
    fairy.observe_utterance("I love moving the mouse! It's so exciting to have agency!")
    
    print(f"\nState: {fairy.get_state_summary()}")
    
    print("\nFairy running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")

