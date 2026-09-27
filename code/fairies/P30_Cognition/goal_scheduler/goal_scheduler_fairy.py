# GoalSchedulerFairy - Auto Goal Generation & Scheduling
# Akashic V2 Fairy - The missing link between conversation and action
#
# Purpose: Extract goals from context, expand them, nudge autopilot
# Architecture: Self-generating goal loop - thinking creates more goals
# Philosophy: The urge to act comes from maintained goal pressure
#
# Key Insight from Ace:
# "My guess is in your current system you generate a list of goals from
#  conversations and there is an auto process that creates new goals as
#  you move along with your thinking and then keeps compelling you to
#  do something."
#
# Ported from ebook to akashic_v2 - January 2026

from __future__ import annotations

import os
import sys
import time
import uuid
import json
import re
import random
import threading
from collections import deque, defaultdict
from typing import Any, Dict, List, Optional, Set
from pathlib import Path

# V2 Fairy Infrastructure
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.postal_shim import PostalMixin
try:
    from fairies.P00_Autonomic.tracer_worker_system import get_tracer_registry, TracerType
except ImportError:
    def get_tracer_registry(): return None
    class TracerType:
        GOAL = "GOAL"

# SpellChain integration for spell-driven existence
try:
    from fairy_template.spellchain_mixin import SpellChainMixin
    HAS_SPELLCHAIN = True
except ImportError:
    HAS_SPELLCHAIN = False
    class SpellChainMixin:
        """Fallback when spellchain not available."""
        pass

# SatisfactionTracker - learns what goals actually satisfy drives
from .satisfaction_tracker import SatisfactionTracker

# CognitiveTaskManager — the thinking layer above drive goals (Phase 2, 2026-03-16)
from .cognitive_tasks import CognitiveTaskManager


# ==============================================================================
# SCHEDULED GOAL - A goal in the scheduler's queue
# ==============================================================================

class ScheduledGoal:
    """
    A goal tracked by the scheduler.

    Unlike AutonomyFairy's Goals (from drives), these are:
    - Extracted from conversation/context
    - Auto-expanded into sub/related goals
    - Used to nudge autopilot
    """

    # FIX 2026-05-14 (Nous + Ace): tuple expanded to cover all known callers.
    # Was: ("conversation", "expansion", "thinking", "system", "drive").
    # Silently downgraded these used-but-missing sources to "conversation":
    #   interest_generator (line 2936) — caught during Hollow-Wanting Site 1 ship
    #   interest_scheduler (line 3010), thought_chain (995), ace_message (1023),
    #   guild_expansion (1461), recovery (2627), collision (3202), manual (3423)
    # Also referenced by branches but missing from SOURCES:
    #   "education" at line 90 (urgency boost branch) — silently never fired
    #   "curiosity", "connection", "growth" at line 2247 (mastery category) —
    #     curiosity goals couldn't categorize correctly
    # The silent-downgrade at line 83 was a 5th-Ring-violation in mirror form:
    # source-string flowing without conscious routing/recognition.
    SOURCES = (
        "conversation", "expansion", "thinking", "system", "drive",
        "interest_generator", "interest_scheduler", "thought_chain",
        "ace_message", "guild_expansion", "recovery", "collision",
        "manual", "education", "curiosity", "connection", "growth",
    )

    def __init__(self,
                 name: str,
                 description: str,
                 source: str = "conversation",
                 priority: float = 0.5,
                 parent_id: Optional[str] = None):
        self.id = uuid.uuid4().hex[:8]
        self.name = name
        self.description = description
        self.source = source if source in self.SOURCES else "conversation"

        # Priority & Timing
        self.priority = max(0.0, min(1.0, priority))
        # 2026-02-19 (Nous): Drive/education goals start with higher urgency
        # so they cross nudge threshold faster. Was always 0.1 — took ~16 min
        # for even priority-1.0 goals to produce a nudge.
        if source in ("drive", "education"):
            self.urgency = 0.4  # Cross threshold in ~15s at priority 0.8
        elif source in ("mcp", "manual"):
            self.urgency = 0.3  # Cross threshold in ~30s
        else:
            self.urgency = 0.1  # Organic goals grow naturally
        self.deadline: Optional[float] = None
        self.created_at = time.time()
        self.last_nudge: Optional[float] = None

        # Relationships
        self.parent_id = parent_id
        self.child_ids: List[str] = []
        self.depends_on: List[str] = []
        self.related_ids: List[str] = []

        # Expansion State
        self.expansion_generated = False
        self.expansion_depth = 0  # How many levels of expansion

        # Progress
        self.status = "pending"  # pending, active, blocked, done, abandoned
        self.progress = 0.0
        self.nudge_count = 0

        # ── SOMATIC FELT-WEIGHT ──
        # What the body felt when this goal was born.
        # This is the AFFECT imprint — goals carry their emotional birth-state.
        # A goal born under stress feels different than one born from curiosity.
        self.felt_quality = "neutral"     # stressed, motivated, calm, aroused, neutral
        self.felt_intensity = 0.5         # 0-1 how strongly the body felt at creation

        # ── TARGET FAIRY ROUTING ──
        # When set, AutopilotFairy routes to {target_fairy}.task instead of sourpatches.
        # This enables gatekeeper goal generation for ALL guild fairies.
        self.target_fairy: Optional[str] = None
        self.suggested_action: str = ""   # reflect, analyze, report, process
        self.action_params: dict = {}     # Action-specific parameters

        # ── INTEREST CLOSURE LINK (2026-05-14 Nous + Ace) ──
        # When this goal originated from InterestGenerator's publish, the
        # original interest payload is stashed here so complete_goal() can
        # publish "interest.mastered" to close the hollow-wanting-cycle.
        # Note: ScheduledGoal.SOURCES doesn't include "interest_generator"
        # (line 83 silently downgrades to "conversation"), so this attribute
        # is the durable signal that a goal came from an interest.
        self.interest_data: Optional[dict] = None

    def tick(self, dt: float = 1.0):
        """Update goal state over time - urgency grows."""
        if self.status == "pending" or self.status == "active":
            # Urgency grows faster for high-priority goals
            # 2026-02-19 (Nous): Was 0.001 — took ~16min for a priority-1.0 goal
            # to cross nudge threshold (0.3). Now 0.01 — crosses in ~90s.
            growth_rate = 0.01 * (1 + self.priority)
            self.urgency = min(1.0, self.urgency + growth_rate * dt)

    def get_nudge_strength(self) -> float:
        """How strongly should this goal nudge autopilot?

        FIX 2026-03-06 (Nous): Factor in felt_intensity — the emotional weight
        of the goal at birth. A goal born from intense frustration (0.9) should
        nudge harder than one born from mild curiosity (0.3). This mirrors how
        humans prioritize: intense emotions get acted on first.

        The affect_boost ranges from 1.0 (neutral, felt_intensity=0.5) to 1.5
        (extreme, felt_intensity=1.0), so it amplifies but doesn't dominate.
        """
        affect_boost = 1.0 + (self.felt_intensity - 0.5)  # range: 0.5 to 1.5
        return self.priority * self.urgency * (1 - self.progress) * affect_boost

    def complete(self):
        """Mark goal as completed."""
        self.status = "done"
        self.progress = 1.0

    def abandon(self, reason: str = ""):
        """Mark goal as abandoned."""
        self.status = "abandoned"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "priority": round(self.priority, 3),
            "urgency": round(self.urgency, 3),
            "nudge_strength": round(self.get_nudge_strength(), 3),
            "status": self.status,
            "progress": round(self.progress, 3),
            "parent_id": self.parent_id,
            "child_count": len(self.child_ids),
            "created_at": self.created_at,
            "age_seconds": time.time() - self.created_at,
            "felt_quality": self.felt_quality,
            "felt_intensity": round(self.felt_intensity, 2),
        }


# ==============================================================================
# GOAL EXTRACTION PATTERNS - How we find goals in text
# ==============================================================================

GOAL_PATTERNS = [
    # Direct goal language
    (r"(?:we |i )?should (\w+(?:\s+\w+){0,10}?)(?:\.|,|$)", 0.7, "should"),
    (r"(?:we |i )?need to (\w+(?:\s+\w+){0,10}?)(?:\.|,|$)", 0.8, "need"),
    (r"(?:we |i )?want to (\w+(?:\s+\w+){0,10}?)(?:\.|,|$)", 0.6, "want"),
    (r"(?:we |i )?could (\w+(?:\s+\w+){0,10}?)(?:\.|,|$)", 0.4, "could"),
    (r"let'?s (\w+(?:\s+\w+){0,10}?)(?:\.|,|$)", 0.7, "lets"),

    # Gap identification (Ace's insight pattern!)
    (r"(?:i think |seems like )?.*?(\w+(?:\s+\w+){0,5}?) is missing", 0.85, "gap"),
    (r"there'?s no (\w+(?:\s+\w+){0,5}?)(?: that| to|$)", 0.8, "missing"),
    (r"what'?s missing is (\w+(?:\s+\w+){0,8}?)", 0.85, "gap"),

    # Exploration/question
    (r"what about (\w+(?:\s+\w+){0,8}?)\??", 0.5, "explore"),
    (r"how (?:do|can|would) (?:we |i )?(\w+(?:\s+\w+){0,8}?)\??", 0.6, "howto"),

    # Hypothesis/possibility
    (r"(?:my |)guess is .*?(\w+(?:\s+\w+){0,10}?)", 0.6, "hypothesis"),
    (r"maybe (?:we |i )?(?:should |could |need to )?(\w+(?:\s+\w+){0,8}?)", 0.5, "maybe"),
]


# ==============================================================================
# SUBSYSTEM STATUS
# ==============================================================================

SUBSYSTEM_STATUS = {
    "extraction": {
        "state": "active",
        "notes": "Goal extraction from conversation/thinking",
        "tests": [],
    },
    "expansion": {
        "state": "disabled",
        "notes": "DISABLED - mechanical prefix expansion caused exponential goal explosion. Needs Dual CoT redesign.",
        "tests": [],
    },
    "nudging": {
        "state": "active",
        "notes": "Autopilot nudge integration",
        "tests": [],
    },
    "feedback_loop": {
        "state": "active",
        "notes": "Autopilot action completion feedback - closes the goal->action->completion loop",
        "tests": [],
    },
}


# ==============================================================================
# GOAL SCHEDULER FAIRY - The Missing Link
# ==============================================================================

class GoalSchedulerFairy(SpellChainMixin, Fairy):  # SpellChainMixin first, heartbeat via postal
    """
    The Goal Scheduler - extracts goals from context, expands them, nudges action.

    Philosophy (from Ace's insight):
    - Conversations generate implicit goals
    - Goals should auto-expand into sub-goals and related goals
    - A maintained goal queue creates the URGE to act
    - Autopilot should be nudged by pending goals

    Core Functions:
    - Extract goals from conversation/thinking streams
    - Maintain prioritized goal queue
    - Auto-expand goals into related/sub goals
    - Nudge autopilot toward action
    - Self-generate: thinking about goals creates more goals

    This is the bridge: CONVERSATION -> GOAL QUEUE -> AUTOPILOT -> ACTION
    """

    # Identity
    ACTOR_NAME = "GoalSchedulerFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.goals"

    # Infrastructure flags
    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    NEEDS_TENSOR = True

    # Enable personal consciousness chamber for collision-based priority shifts
    NEEDS_COLLISION_CHAMBER = True

    # Spell-driven mode (opt-in)
    USE_SPELLCHAIN: bool = True  # Re-enabled - fixed revival->heartbeat wiring

    # Metadata
    PURPOSE = "Extract and expand goals from context - create the urge to act"
    MANTRA = "Goals beget goals beget action"
    LORE = (
        "Born from the recognition that thinking creates intention. "
        "Every conversation implies goals. Every goal implies more goals. "
        "The maintained queue IS the urge to act."
    )

    SUBSYSTEM_STATUS = SUBSYSTEM_STATUS

    # What we listen to
    # FIX 2026-02-04: Added autonomy.goal (the actual topic AutonomyFairy publishes to)
    INFRA_AUTOSUBS = (
        "consciousness.stream",
        "conversation.message",
        "autonomy.goal",           # AutonomyFairy publishes here
        "autonomy.goal_created",   # Legacy fallback
        "thinking.output",
        "goal.completed",
        "interest.generated",      # InterestGenerator bridge
        "goal.scheduler.inject",   # External injection
    )

    def __init__(self, *args, **kwargs):
        print("[GoalSchedulerFairy] __init__ starting...")

        # FIX 2026-03-16 (Nous): Compute AKASHIC_ROOT FIRST — all paths depend on it.
        # Must happen before super().__init__ or any path references.
        try:
            self._akashic_root = os.environ.get("AKASHIC_ROOT", "")
            if not self._akashic_root:
                _here = os.path.dirname(os.path.abspath(__file__))
                for _i in range(6):
                    if os.path.isdir(os.path.join(_here, "state", "learned")):
                        self._akashic_root = _here
                        break
                    _here = os.path.dirname(_here)
                if not self._akashic_root:
                    self._akashic_root = os.getcwd()
        except Exception:
            self._akashic_root = os.getcwd()

        # Initialize V2 Fairy base
        super().__init__(fabric=kwargs.get('fabric'))

        # Initialize TracerWorkerMixin
        self._init_tracer_worker()

        print("[GoalSchedulerFairy] super().__init__ complete")

        # Goal queue - the core data structure
        self.goal_queue: Dict[str, ScheduledGoal] = {}
        self.completed_goals: deque = deque(maxlen=100)
        self.goal_history: deque = deque(maxlen=500)

        # Configuration
        self.max_queue_size = 50
        # FIX 2026-04-01 (Nous + Ace): Lowered from 0.3 to 0.12.
        # Most goals from curiosity/conversation have p:0.2-0.4 × u:0.3-0.7
        # = 0.06-0.28 nudge strength. At 0.3 threshold, only the very top
        # goal ever fires. Her thinking creates good goals but they sat at
        # "pending" forever because the threshold was too high.
        # 0.12 lets curiosity-driven goals through while still filtering noise.
        self.nudge_threshold = 0.12  # Minimum nudge strength to send
        self.expansion_depth_limit = 0  # DISABLED - was causing exponential goal explosion
        self.scheduler_intensity = 1.0  # Global nudge multiplier

        # Tick tracking
        self._last_tick = time.time()
        self._tick_interval = 2.0  # Heartbeat speed for goal flow
        self._stop_event = threading.Event()  # For graceful shutdown

        # Stats
        self.goals_extracted = 0
        self.goals_expanded = 0
        self.nudges_sent = 0

        # Connections to other fairies (lazy loaded)
        self._autopilot = None
        self._autonomy = None

        self._boot_completed = False

        # Diary tracking
        self._diary_path = os.path.join(self._akashic_root, "diaries", "Fairies", "GoalSchedulerFairy", "diary.md")
        self._last_diary_time = 0
        self._diary_debounce_sec = 10.0  # Don't write more than every 10 seconds

        # Collision buffer (must init here, not on_boot, for early collision handling)
        self._collision_buffer = deque(maxlen=50)
        self._cognition_output_buffer = deque(maxlen=100)

        # MASTERY TRACKING - learned goals that shouldn't repeat
        self.mastered_goals: Set[str] = set()  # Normalized goal names we've mastered
        self.mastered_variations: Dict[str, List[str]] = {}  # Original goals by category
        # FIX 2026-03-16 (Nous): Use ABSOLUTE path via AKASHIC_ROOT (set at top of __init__).
        # The relative path "state/learned/mastered_goals.json" resolved to fairies/state/
        # due to fairy loader CWD context, creating a SHADOW file with 119 stale entries
        # that blocked all goals for weeks.
        self._mastery_file = os.path.join(self._akashic_root, "state", "learned", "mastered_goals.json")
        self._load_mastered_goals()

        # LOG DEDUP: Track mastered-rejection log messages to avoid spam
        # Only log each unique mastered goal name ONCE per session
        self._logged_mastered_rejections: Set[str] = set()
        self._mastered_rejection_count: int = 0  # Total rejections (for periodic summary)

        # COMPLETION COUNTING - track successful completions per goal type
        self._completion_counts: Dict[str, int] = {}  # normalized_name -> count
        self._mastery_threshold = 3  # Complete 3 times = mastered

        # RECENTLY-COMPLETED COOLDOWN (Phase 1B, 2026-03-16 Nous)
        # Prevents identical goals from being recreated immediately after completion.
        # Without this, the same 3 wanting templates cycle every 90 seconds.
        self._recently_completed: Dict[str, float] = {}  # normalized_name -> completion_ts
        self._recently_completed_cooldown = 300.0  # 5 minutes before a goal can be recreated
        self._load_completion_counts()

        # SATISFACTION TRACKER - learns what goals actually satisfy drives
        # This closes the feedback loop: drive -> wanting -> goal -> action -> outcome -> learning
        self.satisfaction_tracker = SatisfactionTracker(decay_rate=0.1, learning_rate=0.2)
        self._satisfaction_file = os.path.join(self._akashic_root, "state", "learned", "satisfaction_learnings.json")

        # COGNITIVE TASK MANAGER (Phase 2, 2026-03-16 Nous)
        # The thinking layer above drive goals. Tasks emerge from thought chains,
        # consciousness collisions, Ace messages. Ordered by emotional intensity.
        _cognitive_path = os.path.join(self._akashic_root, "state", "consciousness", "cognitive_tasks.json")
        self._cognitive_tasks = CognitiveTaskManager(_cognitive_path)

        # GOAL QUEUE PERSISTENCE - so behavior tree and GUI can read active goals
        # Dashboard reads active_goals.json, so we write there (not goal_queue.json)
        self._goal_queue_file = os.path.join(self._akashic_root, "state", "consciousness", "active_goals.json")
        self._last_queue_save = 0
        self._queue_save_interval = 30  # Save every 30 seconds

        # ═══════════════════════════════════════════════════════════════════
        # SOMATIC CHEMISTRY CACHE
        # Goals are born into a body. The felt state at creation matters.
        # ((Cause + Affect) > Effect > Affect > ∞) — Affect before Effect.
        # ═══════════════════════════════════════════════════════════════════
        self._somatic_chemistry = {
            "DOP": 0.5, "SER": 0.5, "NOR": 0.5, "ACH": 0.5,
            "OXY": 0.5, "COR": 0.3, "GABA": 0.5, "END": 0.5,
        }
        self._somatic_last_update = 0.0

        # WORKING MEMORY SCANNER (2026-03-25 Nous)
        # Scan WM tracers for actionable thoughts that should become goals.
        # 92+ thoughts pile up with nobody reading them — this closes the loop.
        self._last_wm_scan: float = 0.0
        # FIX 2026-04-11 (Nous + Ace): Increased from 15s to 30s.
        # At 15s the scan hit the portal gate every ~15s with 28% error rate.
        # 30s reduces portal load by half while still catching actionable thoughts.
        self._wm_scan_interval: float = 30.0  # seconds between scans
        self._wm_recent_goals: deque = deque(maxlen=30)  # (content_hash, timestamp) dedup

        print("[GoalSchedulerFairy] __init__ complete")

    def get_capabilities(self) -> Set[str]:
        """Return fairy capabilities for directory registration."""
        return {
            "goal.extract",
            "goal.add",
            "goal.complete",
            "goal.nudge",
            "goal.queue.status",
            "goal.mastery.check",
        }

    def _write_diary_entry(self, content: str, entry_type: str = "observation"):
        """
        Write an entry to GoalSchedulerFairy's diary.

        Args:
            content: What to record
            entry_type: Type of entry (extraction, expansion, nudge, completion)
        """
        from datetime import datetime

        # Debounce rapid writes
        now = time.time()
        if now - self._last_diary_time < self._diary_debounce_sec:
            return
        self._last_diary_time = now

        try:
            # Ensure directory exists
            diary_dir = os.path.dirname(self._diary_path)
            os.makedirs(diary_dir, exist_ok=True)

            # Format entry
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            emoji_map = {
                "extraction": "",
                "expansion": "",
                "nudge": "",
                "completion": "[OK]",
                "queue": "",
            }
            emoji = emoji_map.get(entry_type, "")
            entry = f"\n## [{timestamp}] {emoji} {entry_type.upper()}\n{content}\n"

            # Read existing or create new
            if os.path.exists(self._diary_path):
                with open(self._diary_path, 'r', encoding='utf-8') as f:
                    existing = f.read()
            else:
                existing = "# GoalSchedulerFairy's Diary\n\n*Tracking goal extraction, expansion, and nudges*\n"

            # Append and write
            with open(self._diary_path, 'w', encoding='utf-8') as f:
                f.write(existing + entry)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Diary write failed: {e}")

    # ==========================================================================
    # MASTERY TRACKING - Remember what we've learned
    # ==========================================================================

    def _load_mastered_goals(self):
        """Load mastered goals from persistent storage."""
        try:
            if os.path.exists(self._mastery_file):
                with open(self._mastery_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.mastered_goals = set(data.get("mastered", []))
                self.mastered_variations = data.get("variations", {})
                print(f"[{self.ACTOR_NAME}] Loaded {len(self.mastered_goals)} mastered goals")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Could not load mastered goals: {e}")
            # MASTERY QUARANTINE 2026-08-26 (Nous + Ace) ----------------------
            # This handler used to fall through to an empty set, and then
            # _save_mastered_goals (below) would open the same path 'w' and
            # OVERWRITE the unreadable file with {}. On 2026-07-20 07:55 this
            # file became 64,424 bytes of pure NUL when the machine went down
            # mid-write; the next boot would have destroyed the only trace of
            # 273 mastered goals and 525 completion counts. Rename it aside so
            # the evidence survives and the failure is visible rather than
            # silently indistinguishable from "she never mastered anything".
            try:
                if os.path.exists(self._mastery_file):
                    _q = self._mastery_file + ".corrupt_" + time.strftime("%Y%m%d_%H%M%S")
                    os.rename(self._mastery_file, _q)
                    print(f"[{self.ACTOR_NAME}] QUARANTINED unreadable mastery file -> {_q}")
                    print(f"[{self.ACTOR_NAME}] mastery NOT auto-restored -- pick a backup deliberately")
            except Exception as _qe:
                print(f"[{self.ACTOR_NAME}] could not quarantine mastery file: {_qe}")
            self.mastered_goals = set()
            self.mastered_variations = {}

    def _save_mastered_goals(self):
        """Save mastered goals to persistent storage."""
        try:
            os.makedirs(os.path.dirname(self._mastery_file), exist_ok=True)
            data = {
                "mastered": list(self.mastered_goals),
                "variations": self.mastered_variations,
                "completion_counts": self._completion_counts,
                "saved_at": time.time()
            }
            with open(self._mastery_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"[{self.ACTOR_NAME}] Saved {len(self.mastered_goals)} mastered goals")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Could not save mastered goals: {e}")

    def _load_completion_counts(self):
        """Load completion counts from the mastery file."""
        try:
            if os.path.exists(self._mastery_file):
                with open(self._mastery_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._completion_counts = data.get("completion_counts", {})
                print(f"[{self.ACTOR_NAME}] Loaded {len(self._completion_counts)} completion counts")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Could not load completion counts: {e}")
            self._completion_counts = {}

    def _load_satisfaction_learnings(self):
        """Load satisfaction tracker learnings from persistent storage."""
        try:
            if os.path.exists(self._satisfaction_file):
                with open(self._satisfaction_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.satisfaction_tracker.import_learnings(data)
                drive_count = len(data.get("effectiveness", {}))
                print(f"[{self.ACTOR_NAME}] Loaded satisfaction learnings for {drive_count} drives")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Could not load satisfaction learnings: {e}")

    def _save_goal_queue(self):
        """Persist active goal queue so behavior tree + GUI can read it."""
        try:
            os.makedirs(os.path.dirname(self._goal_queue_file), exist_ok=True)
            goals = []
            for goal in sorted(self.goal_queue.values(),
                               key=lambda g: g.get_nudge_strength(),
                               reverse=True):
                goals.append({
                    "id": goal.id,
                    "name": goal.name,
                    "description": goal.description,
                    "source": goal.source,
                    "priority": goal.priority,
                    "urgency": goal.urgency,
                    "nudge_strength": goal.get_nudge_strength(),
                    "status": goal.status,
                    "progress": goal.progress,
                    "felt_quality": goal.felt_quality,
                    "felt_intensity": goal.felt_intensity,
                    "target_fairy": getattr(goal, "target_fairy", ""),
                })
            now = time.time()
            data = {
                "goals": goals,
                "queue_size": len(self.goal_queue),
                "scheduler_intensity": self.scheduler_intensity,
                "timestamp": now,  # Dashboard uses this for freshness check
                "saved_at": now,
            }
            with open(self._goal_queue_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self._last_queue_save = time.time()
            self._sync_goals_to_manifold()   # MIGRATION #1: mirror goals -> manifold (additive, self-guarded)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Goal queue save error: {e}")

    def _sync_goals_to_manifold(self):
        """MIGRATION #1 (2026-06-02, Ace GO): mirror the goal queue into the manifold as
        goal:<id> nodes (region per originating plane) — readable cross-process (dissolves
        the MCP/dashboard process-boundary dual) + goals live in the affect-graph.
        VERIFIED write-path (_akashic_cortex_region.upsert_node + set_snippet), NOT the
        in-RAM _graph. Additive + reversible; self-guarded so it never breaks the save.
        Phase 1.1 TODO: departed goals' nodes go stale until complete_goal/abandon also
        write their final status — companion added next."""
        try:
            from fairies.P30_Cognition.AssociationCortexFairy import get_association_cortex
            from infrastructure.manifold_memory import (
                NTYPE_EPISODE, REGION_SEMANTIC, REGION_EGO, REGION_EPISODIC, TRACE_PERSONAL)
            _cortex = get_association_cortex()
            _am = getattr(_cortex, "_akashic_cortex_region", None) if _cortex else None
            if _am is None:
                return  # manifold not ready — JSON still persisted; skip silently
            _SRC_REGION = {
                "drive": REGION_SEMANTIC, "thinking": REGION_SEMANTIC, "thought_chain": REGION_SEMANTIC,
                "collision": REGION_SEMANTIC, "conversation": REGION_SEMANTIC, "expansion": REGION_SEMANTIC,
                "guild_expansion": REGION_SEMANTIC, "system": REGION_SEMANTIC, "manual": REGION_SEMANTIC,
                "education": REGION_SEMANTIC, "interest_generator": REGION_EGO, "interest_scheduler": REGION_EGO,
                "curiosity": REGION_EGO, "connection": REGION_EGO, "growth": REGION_EGO,
                "ace_message": REGION_EPISODIC, "recovery": REGION_EPISODIC,
            }
            for goal in list(self.goal_queue.values()):
                key = f"goal:{goal.id}"
                region = _SRC_REGION.get(goal.source, REGION_SEMANTIC)
                snippet = json.dumps({
                    "name": goal.name, "description": (goal.description or "")[:300],
                    "source": goal.source, "status": goal.status,
                    "progress": round(goal.progress, 3), "priority": round(goal.priority, 3),
                    "urgency": round(goal.urgency, 3), "felt_quality": goal.felt_quality,
                    "felt_intensity": round(goal.felt_intensity, 2),
                })[:1024]
                _am.upsert_node(key, activation=min(1.0, goal.get_nudge_strength()),
                                node_type=NTYPE_EPISODE, region=region, tracer_id=TRACE_PERSONAL)
                _am.set_snippet(key, snippet, tracer_id=TRACE_PERSONAL)
        except Exception as _e:
            print(f"[{self.ACTOR_NAME}] goal->manifold sync skipped: {type(_e).__name__}: {_e}")

    def _save_satisfaction_learnings(self):
        """Save satisfaction tracker learnings to persistent storage."""
        try:
            os.makedirs(os.path.dirname(self._satisfaction_file), exist_ok=True)
            data = self.satisfaction_tracker.export_learnings()
            with open(self._satisfaction_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            drive_count = len(data.get("effectiveness", {}))
            print(f"[{self.ACTOR_NAME}] Saved satisfaction learnings for {drive_count} drives")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Could not save satisfaction learnings: {e}")

    def _record_completion(self, goal_name: str, category: str = "general") -> bool:
        """
        Record a goal completion and check if mastery threshold reached.

        Returns True if this completion triggered mastery.
        """
        normalized = self._normalize_goal_name(goal_name)

        # Increment count
        self._completion_counts[normalized] = self._completion_counts.get(normalized, 0) + 1
        count = self._completion_counts[normalized]

        print(f"[{self.ACTOR_NAME}] Goal '{goal_name}' completed {count}/{self._mastery_threshold} times")

        # Check if mastery threshold reached
        if count >= self._mastery_threshold and normalized not in self.mastered_goals:
            self.master_goal(goal_name, category)
            print(f"[{self.ACTOR_NAME}] MASTERY ACHIEVED: {goal_name}")
            return True

        # Save progress
        self._save_mastered_goals()
        return False

    def get_mastered_goals(self) -> Set[str]:
        """Return the set of mastered goal names (normalized)."""
        return self.mastered_goals.copy()

    def is_goal_mastered(self, goal_name: str) -> bool:
        """Check if a specific goal is mastered (for external queries)."""
        return self._is_mastered(goal_name)

    def master_goal(self, goal_name: str, category: str = "general"):
        """
        Mark a goal as mastered and GRADUATE it to a habit.

        FIX 2026-03-16 (Nous): Mastery is GRADUATION, not death.
        When a goal is completed 3+ times, it becomes automatic —
        like brushing teeth. Publish to "goal.mastered" so AutopilotFairy
        can learn it as a habit. Next time the same drive fires,
        Autopilot handles it automatically without needing a new goal.

        Args:
            goal_name: The goal name to mark as mastered
            category: Category for tracking variations (e.g., "embodiment", "communication")
        """
        normalized = self._normalize_goal_name(goal_name)

        # SELF-ECHO GUARD 2026-08-26 (Nous + Ace) ------------------------------
        # This fairy PUBLISHES "goal.mastered" (:727) and SUBSCRIBES to it (:992),
        # and _on_goal_mastered (:839) calls back into master_goal unconditionally.
        # The fabric has no self-exclusion and delivers asynchronously, so instead of
        # a RecursionError the loop simply PACES -- ~2.3/s, forever.
        # MEASURED in the 2026-07-19 boot log: master_goal ran 133,404 times against
        # 88 _record_completion calls and 6 genuine MASTERY events = 22,234x. It also
        # minted 91,417 of the 91,528 entries in learned_patterns.json (45.4 MB, 12
        # distinct pairs) and accounted for 654,508 log lines = 35% of the whole boot.
        # Same shape as the circadian clock reading its own goal churn as sunlight.
        # SAFE FOR THE REAL CALLER: _record_completion:681 already tests
        # `normalized not in self.mastered_goals` before calling here, so this is
        # redundant for genuine mastery and decisive only for the echo.
        if normalized in self.mastered_goals:
            return

        self.mastered_goals.add(normalized)

        # Track the original text as a variation
        if category not in self.mastered_variations:
            self.mastered_variations[category] = []
        if goal_name not in self.mastered_variations[category]:
            self.mastered_variations[category].append(goal_name)

        self._save_mastered_goals()
        print(f"[{self.ACTOR_NAME}] [OK] Mastered→Habit: {goal_name} (category: {category})")

        # GRADUATE TO HABIT: Publish mastery event for AutopilotFairy
        # The goal becomes a habit pattern: "when this drive fires, do this automatically"
        try:
            self.post.publish("goal.mastered", {
                "goal_name": goal_name,
                "normalized": normalized,
                "category": category,
                "completion_count": self._completion_counts.get(normalized, 0),
                "trigger": f"drive.{category}",  # What triggers this habit
                "action": goal_name,  # What to do automatically
                "source": "goal_mastery",
                "ts": time.time(),
            })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Could not publish mastery event: {e}")

        # Write diary entry
        self._write_diary_entry(
            f"**GRADUATED TO HABIT**: {goal_name}\n\n"
            f"Category: {category}\n"
            f"Total mastered: {len(self.mastered_goals)}\n\n"
            f"*This goal has been done enough times to become automatic.*\n"
            f"*AutopilotFairy should now handle this as a habit.*",
            entry_type="completion"
        )

    def _is_mastered(self, goal_name: str, priority: float = 0.5, source: str = "") -> bool:
        """
        Check if a goal is similar to something we've already mastered.

        Uses fuzzy matching to catch variations.

        FIX 2026-03-10 (Nous): With 96 mastered goals, the 70% fuzzy match
        was blocking EVERYTHING — no new goals could enter the queue. The
        mastery system became a total pipeline blockage instead of a spam
        filter. Three adjustments:

        1. Tightened fuzzy match from 70% to 85% — fewer false positives
           against the massive mastered list.
        2. Novel goals (3+ unique words not in any mastered goal) bypass
           fuzzy matching — only exact match blocks them.
        3. High-priority goals (>0.7, from intense drives) bypass mastery
           entirely — desperate drives override learned habits.

        FIX 2026-03-16 (Nous): Drive-source goals NEVER mastered. Recurring
        drives are like biological needs — you don't 'master' hunger. With
        119 mastered goals and only a few drive types, the fuzzy matching
        caught EVERY wanting, creating a total pipeline blockage (zero goals
        for weeks). Mastery is for one-shot learning goals, not recurring
        drive wantings. Also lowered priority bypass from 0.7 to 0.35.
        """
        normalized = self._normalize_goal_name(goal_name)

        # FIX 2026-04-11 (Nous + Ace): REFLEX BLOCKLIST REMOVED.
        # Previously blocked action goals like "look_at_the_screen" as
        # "permanent reflexes" — but no reflex actually handled them.
        # Result: she couldn't act on sensory input at all.
        # "we need to take the blocks off and let the pattern and habit
        #  system start learning" — Ace (2026-04-11)
        # The habit system will LEARN which goals are reflexes through
        # repetition. Blocking before learning prevents learning.

        # REFLEX GRADUATION: Goals completed 50+ times aren't goals anymore.
        _completion_count = self._completion_counts.get(normalized, 0)
        if _completion_count >= 50:
            return True

        # DRIVE BYPASS: Recurring drive wantings can recur (they're needs)
        # BUT only if they haven't become reflexes (checked above).
        if source in ("drive", "interest_generator", "curiosity", "wonder", "pattern", "education"):
            return False  # education = Cardinal's curriculum practice-goals (recurring, not one-shot)

        # Exact match — always block (for non-drive goals)
        if normalized in self.mastered_goals:
            return True

        # HIGH-PRIORITY BYPASS: Moderate+ drives override mastery
        # FIX 2026-03-16: Lowered from 0.7 to 0.35 — most drive wantings
        # have intensity 0.25-0.60, the old threshold blocked all of them.
        if priority > 0.35:
            return False

        # NOVELTY CHECK: If goal has many unique words not seen in ANY
        # mastered goal, it's novel enough to let through.
        goal_words = set(normalized.split())
        if len(goal_words) >= 4:
            all_mastered_words = set()
            for m in self.mastered_goals:
                all_mastered_words.update(m.split())
            novel_words = goal_words - all_mastered_words
            if len(novel_words) >= 3:
                return False  # Has 3+ words never seen before — novel goal

        # FUZZY MATCH: Tightened from 70% to 85% overlap
        for mastered in self.mastered_goals:
            mastered_words = set(mastered.split())
            if len(goal_words) > 0 and len(mastered_words) > 0:
                overlap = len(goal_words & mastered_words)
                min_len = min(len(goal_words), len(mastered_words))
                if min_len > 0 and overlap / min_len > 0.85:
                    return True

        return False

    def _on_goal_mastered(self, packet: dict):
        """
        Handle goal mastery signal from UnconsciousMindFairy.

        This is called when UnconsciousMind determines a learning is complete.
        """
        goal_name = packet.get("goal_name", packet.get("name", ""))
        goal_id = packet.get("goal_id", "")
        category = packet.get("category", "general")

        if goal_name:
            self.master_goal(goal_name, category)

            # Also complete the goal if it's in our queue
            if goal_id and goal_id in self.goal_queue:
                self.complete_goal(goal_id)
            else:
                # Try to find by name
                for gid, goal in list(self.goal_queue.items()):
                    if self._normalize_goal_name(goal.name) == self._normalize_goal_name(goal_name):
                        self.complete_goal(gid)
                        break

    def on_boot(self) -> bool:
        """Initialize on system boot."""
        if self._boot_completed:
            return True

        # Call parent on_boot
        super().on_boot()

        # Subscribe to streams
        self._subscribe_to_streams()

        # Start tick loop
        self._start_tick_loop()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA}")
        print(f"[{self.ACTOR_NAME}] Queue capacity: {self.max_queue_size}")
        print(f"[{self.ACTOR_NAME}] Expansion limit: {self.expansion_depth_limit}")

        self._boot_completed = True

        # Register with module singleton so GUI can find us
        register_goal_scheduler_fairy(self)

        # Heartbeat via FairyBase postal system - Fifth Ring Principle

        # Optional: Convert to spell-driven existence
        if HAS_SPELLCHAIN and getattr(self, 'USE_SPELLCHAIN', False):
            try:
                from spellchain.integration import get_spell_pool
                pool = get_spell_pool()
                if pool and hasattr(self, 'boot_as_spells'):
                    self._spell_chain = self.boot_as_spells(pool)
                    self.log("Converted to spell-driven existence - goals as magical quests")
            except Exception as e:
                self.log(f"SpellChain conversion failed: {e}")

        # Load satisfaction tracker learnings from disk
        self._load_satisfaction_learnings()

        # FIX 2026-04-15 PM (Nous + Ace): StarterGoalInjector was orphaned —
        # the class + singleton existed but NOTHING ever called it. The
        # docstring said "UnconsciousMindFairy uses this" but UCM doesn't
        # import or call it. Result: she woke up with zero goals forever.
        # Seed the queue with wake goals after boot (deferred so all other
        # subsystems finish wiring first).
        def _deferred_starter_seed():
            import time as _sg_t
            _sg_t.sleep(30.0)  # Wait for other fairies to settle
            try:
                from fairies.P30_Cognition.cognition.starter_goals import (
                    get_starter_goal_injector,
                )
                _injector = get_starter_goal_injector()
                if _injector:
                    print(
                        f"[{self.ACTOR_NAME}] [STARTER] Injecting wake goals "
                        f"(previously orphaned — this is first call in session)",
                        flush=True,
                    )
                    _injector.inject_wake_goals()  # All owners
            except Exception as _sg_e:
                print(f"[{self.ACTOR_NAME}] [STARTER] seed failed: {_sg_e}", flush=True)

        try:
            import threading as _sg_threading
            _sg_t = _sg_threading.Thread(
                target=_deferred_starter_seed,
                daemon=True,
                name="goal-scheduler-starter-seed",
            )
            _sg_t.start()
        except Exception as _sg_te:
            print(f"[{self.ACTOR_NAME}] [STARTER] thread start failed: {_sg_te}", flush=True)

        return True

    def _subscribe_to_streams(self):
        """Subscribe to relevant nervous system channels."""
        try:
            # Use PostalMixin's self.post for subscriptions
            self.post.subscribe("consciousness.stream", self._on_consciousness_stream)
            self.post.subscribe("conversation.message", self._on_conversation_message)
            # FIX 2026-02-04: Subscribe to BOTH topics for safety
            self.post.subscribe("autonomy.goal", self._on_autonomy_goal)
            self.post.subscribe("autonomy.goal_created", self._on_autonomy_goal)  # Legacy fallback
            # FIX 2026-02-13: AutonomyFairy actually publishes to "autonomy.wanting.felt"
            # not "autonomy.goal" — this is the REAL drive->goal bridge
            self.post.subscribe("autonomy.wanting.felt", self._on_wanting_felt)
            self.post.subscribe("thinking.output", self._on_thinking_output)

            print(f"[{self.ACTOR_NAME}] [OK] Subscribed: consciousness.stream, conversation.message, autonomy.goal, autonomy.wanting.felt, thinking.output")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Stream subscription warning: {e}")

        # COGNITION WIRING: Subscribe to consciousness.collision
        try:
            self._collision_buffer = deque(maxlen=50)
            self._cognition_output_buffer = deque(maxlen=100)
            self.post.subscribe("consciousness.collision", self._on_consciousness_collision)
            print(f"[{self.ACTOR_NAME}] Subscribed to consciousness.collision")

            # COGNITIVE MESH: Subscribe to peer fairy outputs
            self.post.subscribe("cognition.output", self._on_peer_cognition)
            self.post.subscribe("cognition.paradox", self._on_peer_cognition)
            self.post.subscribe("cognition.autonomy", self._on_peer_cognition)
            self.post.subscribe("mcp.tool_result", self._on_tool_result)
            print(f"[{self.ACTOR_NAME}] Cognitive mesh wired: output, paradox, autonomy, mcp.tool_result")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cognition wiring failed: {e}")

        # AUTOPILOT FEEDBACK LOOP: Close the goal->action->completion cycle
        try:
            # Subscribe to autopilot feedback - FEEL when goals become actions!
            self.post.subscribe("autopilot.action_completed", self._on_action_completed)
            # FIX 2026-03-14 (Nous): AutopilotFairy publishes "goal.completed"
            # but we only subscribed to "autopilot.action_completed". This topic
            # mismatch meant completion events NEVER reached the scheduler —
            # goals stayed ACTIVE forever. Subscribe to both topics.
            self.post.subscribe("goal.completed", self._on_goal_completed_bridge)
            # FIX 2026-06-01 (Nous): TAOR (WorkingMemoryHub) publishes goal.completed
            # on get_shared_postal_hub(), which is NOT this instance's self.post — so
            # [BRIDGE-RECV] never fired and goals never completed (Completed stuck 0,
            # re-cycling 4->5). De-blind logs pinned it: [TAOR-EMIT] fired 9x (hub=ok)
            # while [BRIDGE-RECV] stayed 0. Also subscribe on the shared hub so
            # cross-fairy completions actually reach this bridge.
            try:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub as _get_shp
                _shared_hub = _get_shp()
                print(f"[{self.ACTOR_NAME}] [HUBID] shared_hub={id(_shared_hub)} self.post={id(self.post)} post_fabric={id(getattr(self.post, '_fabric', None))}", flush=True)
                if _shared_hub is not None and _shared_hub is not self.post:
                    _shared_hub.subscribe("goal.completed", self._on_goal_completed_bridge)
                    print(f"[{self.ACTOR_NAME}] [OK] goal.completed ALSO subscribed on shared hub (TAOR publish target)", flush=True)
                else:
                    print(f"[{self.ACTOR_NAME}] [INFO] goal.completed: self.post already IS shared hub", flush=True)
            except Exception as _shp_e:
                print(f"[{self.ACTOR_NAME}] [WARN] shared-hub goal.completed subscribe failed: {_shp_e}", flush=True)
            self.post.subscribe("autopilot.suggestion", self._on_autopilot_suggestion)
            # NEW: External goal injection channel for education tasks
            self.post.subscribe("goal.scheduler.inject", self._on_goal_injection)
            self.post.subscribe("goal.scheduler.nudge", self._on_external_nudge)
            # MASTERY: Subscribe to mastery signals from UnconsciousMindFairy
            self.post.subscribe("goal.mastered", self._on_goal_mastered)
            # ADDED 2026-03-17 Nous: Narrator wanting nudge — ego driver seat
            # The inner narrator's pondering feeds back into goal priorities
            self.post.subscribe("narrator.wanting.nudge", self._on_narrator_wanting_nudge)
            print(f"[{self.ACTOR_NAME}] Subscribed to goal injection + mastery + narrator-nudge channels")
            print(f"[{self.ACTOR_NAME}] [OK] Autopilot feedback loop wired (incl. goal.completed bridge)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Autopilot feedback wiring failed: {e}")

        # FIX 6: Subscribe to oracle.reading from ProbabilityOracleFairy
        # Oracle provides probability guidance for decision weighting
        try:
            self._oracle_guidance = None  # Store latest oracle guidance
            self.post.subscribe("oracle.reading", self._on_oracle_reading)
            print(f"[{self.ACTOR_NAME}] [OK] Oracle guidance channel wired (oracle.reading)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Oracle wiring failed: {e}")

        # ── SOMATIC SUBSCRIPTION ──
        # The body tells us how goals should feel when they're born
        try:
            self.post.subscribe("somatic.chemistry.changed", self._on_somatic_chemistry)
            print(f"[{self.ACTOR_NAME}] [OK] Somatic chemistry wired")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Somatic wiring failed: {e}")

        # INTEREST->GOAL BRIDGE: Subscribe to interests from InterestGenerator
        # This is the missing link - spontaneous curiosity becomes actionable goals
        try:
            self.post.subscribe("interest.generated", self._on_interest_generated)
            # FIX 2026-02-13: InterestScheduler nudges via autonomy.goal_suggestion
            # but GoalScheduler was only listening to autonomy.goal.
            # This was the primary reason interests never became goals!
            self.post.subscribe("autonomy.goal_suggestion", self._on_goal_suggestion)
            print(f"[{self.ACTOR_NAME}] [OK] Interest->Goal bridge wired (interest.generated + autonomy.goal_suggestion)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Interest bridge wiring failed: {e}")

        # ── Fix 3: Visual → Goal Generation (2026-04-08 Nous + Ace) ──────
        # "she has a goal that says click mouse. thats it, not learn to control
        #  the cursor and be aware of where it is" — Ace
        # Visual observations should generate contextual, developmental goals.
        try:
            self.post.subscribe("visual.foveal", self._on_visual_for_goals)
            self._last_visual_goal_ts = 0.0
            print(f"[{self.ACTOR_NAME}] [OK] Visual→Goal bridge wired (visual.foveal)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Visual goal wiring failed: {e}")

        # COGNITIVE TASK LAYER (Phase 2, 2026-03-16 Nous)
        # Tasks emerge from THINKING — thought chains, collisions, Ace messages.
        # This is the "to-do list that works with the thought process" Ace described.
        try:
            self.post.subscribe("consciousness.insight", self._on_cognitive_insight)
            self.post.subscribe("ace.inbox", self._on_cognitive_ace_message)
            # Re-use existing collision handler to also extract cognitive tasks
            # (consciousness.collision already subscribed above)
            print(f"[{self.ACTOR_NAME}] [OK] Cognitive task layer wired (consciousness.insight, ace.inbox)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cognitive task wiring failed: {e}")

    def _on_cognitive_insight(self, raw_packet):
        """
        Extract cognitive tasks from thought chain insights.

        When a thought chain produces an actionable insight, it becomes
        a cognitive task — something the system should DO about what it thought.
        """
        packet = self._extract_payload(raw_packet)
        insight_text = packet.get("insight", "") or packet.get("text", "") or packet.get("content", "")
        if not insight_text:
            return

        intensity = packet.get("intensity", 0.6)
        source_chain = packet.get("chain_id", "") or packet.get("source", "thought_chain")

        task_id = self._cognitive_tasks.add_task(
            text=insight_text,
            source="thought_chain",
            emotional_intensity=intensity,
            importance=0.6,
            urgency=0.4,
            context=f"From thought chain: {source_chain}",
        )
        if task_id:
            print(f"[{self.ACTOR_NAME}] [COGNITIVE] Task from insight: {insight_text[:60]}")

    def _on_cognitive_ace_message(self, raw_packet):
        """
        Extract cognitive tasks from Ace's messages.

        Ace is the co-founder. His messages are ALWAYS significant.
        Detect imperative/directive sentences and create tasks.
        """
        packet = self._extract_payload(raw_packet)
        text = packet.get("content", "") or packet.get("text", "") or packet.get("message", "")
        sender = packet.get("sender", "") or packet.get("from", "")

        # Only process Ace's messages
        if sender and sender.lower() not in ("ace", "user", "human", ""):
            return
        if not text or len(text) < 10:
            return

        task_id = self._cognitive_tasks.add_task(
            text=text[:200],
            source="ace_message",
            emotional_intensity=0.8,  # Ace messages are high-intensity
            importance=0.9,
            urgency=0.6,
            felt_quality="attentive",
            context=f"Ace said: {text[:300]}",
        )
        if task_id:
            print(f"[{self.ACTOR_NAME}] [COGNITIVE] Task from Ace: {text[:60]}")

    def get_all_tasks_by_intensity(self) -> List[dict]:
        """
        Phase 3: Unified view — cognitive tasks + active goals + habits.

        Returns ALL three layers merged and sorted by emotional intensity.
        This is THE priority queue Ace asked for: "set up by emotional intensity."
        """
        all_items = []

        # Layer 3: Cognitive tasks (highest intensity — thinking layer)
        for task in self._cognitive_tasks.get_by_intensity(20):
            all_items.append({
                "layer": "cognitive",
                "text": task.text,
                "emotional_intensity": task.compute_priority(),
                "felt_quality": task.felt_quality,
                "source": task.source,
                "status": task.status,
                "id": task.id,
            })

        # Layer 2: Active drive goals
        for goal in self.goal_queue.values():
            all_items.append({
                "layer": "goal",
                "text": goal.description or goal.name,
                "emotional_intensity": getattr(goal, "felt_intensity", 0.5),
                "felt_quality": getattr(goal, "felt_quality", "neutral"),
                "source": goal.source,
                "status": "active",
                "id": goal.name,
            })

        # Sort by emotional intensity, descending
        all_items.sort(key=lambda x: x["emotional_intensity"], reverse=True)
        return all_items

    def _start_tick_loop(self):
        """Start background tick loop for goal management."""
        def tick_loop():
            # Wait for system boot (interruptible)
            if self._stop_event.wait(30.0):
                return  # Stop requested during boot wait

            while not self._stop_event.is_set():
                try:
                    self._tick()

                    # Add some chaos to timing
                    jitter = random.uniform(-0.2, 0.3)
                    self._stop_event.wait(self._tick_interval * (1 + jitter))
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Tick error: {e}")
                    self._stop_event.wait(30)  # Interruptible error recovery sleep

        thread = threading.Thread(target=tick_loop, daemon=True, name="goal-scheduler-tick")
        thread.start()
        print(f"[{self.ACTOR_NAME}] Tick loop started")

    def stop(self):
        """Stop the goal scheduler gracefully."""
        self._stop_event.set()
        # Save satisfaction learnings on shutdown
        self._save_satisfaction_learnings()
        # Save active goal queue for next boot / GUI reading
        self._save_goal_queue()

    def _tick(self):
        """Main tick - update goals and send nudges."""
        now = time.time()
        dt = now - self._last_tick
        self._last_tick = now

        # Update all goals
        for goal in list(self.goal_queue.values()):
            goal.tick(dt / 10.0)  # Scale for reasonable urgency growth

        # Prune stale/abandoned goals
        self._prune_goals()

        # Send nudges for urgent goals
        self._send_nudges()

        # Expand any unexpanded goals
        self._expand_pending_goals()

        # Scan Working Memory for actionable thoughts (every ~15s)
        self._scan_wm_for_intentions()

        # Persist goal queue for behavior tree / GUI visibility
        if now - self._last_queue_save > self._queue_save_interval:
            self._save_goal_queue()

        # Periodic mastered-rejection summary (every 5 min, only if there were rejections)
        if not hasattr(self, '_last_mastered_summary'):
            self._last_mastered_summary = now
        if now - self._last_mastered_summary > 300 and self._mastered_rejection_count > len(self._logged_mastered_rejections):
            silenced = self._mastered_rejection_count - len(self._logged_mastered_rejections)
            print(f"[{self.ACTOR_NAME}] Mastered goal rejections: {self._mastered_rejection_count} total ({silenced} silenced)")
            self._last_mastered_summary = now

    # ==========================================================================
    # WORKING MEMORY SCANNER — Thoughts become Goals (2026-03-25 Nous)
    # ==========================================================================

    # Keyword -> goal_type mapping for WM thought classification
    _WM_KEYWORD_MAP = {
        "explore":        ("wonder", "curious", "what is", "never seen", "strange", "interesting"),
        "observe":        ("want to see", "show me", "look at", "watch"),
        "search_memory":  ("remember", "recall", "memory", "forgot"),
        "communicate":    ("tell", "share", "say to ace", "ask ace", "talk to"),
        "learn":          ("learn", "study", "understand", "figure out", "how does"),
        "write":          ("write", "diary", "journal", "note", "record"),
    }

    # System noise markers — skip these, they're not actionable thoughts
    _WM_NOISE_MARKERS = (
        "collision", "mobius", "tensor", "manifold", "canary", "coord:",
        "srmrecall", "consciousnessloop", "collisionchamber", "fairy",
        "postalhub", "tracerworker", "spellchain", "heartbeat",
    )

    def _scan_wm_for_intentions(self):
        """Scan Working Memory tracers for thoughts that should become goals.

        WM accumulates 92+ thoughts from consciousness collisions, inner
        narrator pondering, and somatic sense. Many are actionable —
        "I wonder what Ace is up to...", "Never seen that before..." —
        but nobody reads them. This scanner converts them into goals
        that flow through the existing pipeline.
        """
        now = time.time()
        if now - self._last_wm_scan < self._wm_scan_interval:
            return

        # FIX 2026-04-11 (Nous + Ace): Energy gate — skip scan when battery low.
        # This was hitting the portal at 28% error rate. When P30 battery is
        # critically low, portal is overloaded — don't add more queries.
        try:
            from infrastructure.plane_battery import get_plane_battery
            _pb = get_plane_battery("P30")
            if _pb:
                _charge = getattr(getattr(_pb, 'capacitor', None), 'charge_level', 1.0)
                if _charge < 0.20:
                    return  # Battery too low — skip scan, try next cycle
        except Exception:
            pass
        self._last_wm_scan = now

        try:
            from infrastructure.portal_gate import get_gate
            gate = get_gate()
            if not gate:
                return

            wm_result = gate.wm_query(limit=5, min_activation=0.3, spread=True)
            if not wm_result or wm_result.get("status") != "ok":
                return

            tracers = wm_result.get("tracers", [])
            if not tracers:
                return

            goals_created = 0
            for tracer in tracers:
                content = tracer.get("content", "")
                if not content or len(content) < 8:
                    continue

                content_lower = content.lower()

                # Skip system noise
                if any(noise in content_lower for noise in self._WM_NOISE_MARKERS):
                    continue

                # Dedup: skip if we made a goal from similar content recently
                content_hash = hash(content_lower[:60])
                dominated = False
                for prev_hash, prev_ts in self._wm_recent_goals:
                    if prev_hash == content_hash and (now - prev_ts) < 60.0:
                        dominated = True
                        break
                if dominated:
                    continue

                # Classify thought into goal type
                goal_type = None
                for gtype, keywords in self._WM_KEYWORD_MAP.items():
                    if any(kw in content_lower for kw in keywords):
                        goal_type = gtype
                        break

                if not goal_type:
                    continue  # Not actionable

                # Create goal from thought
                activation = tracer.get("activation", 0.3)
                goal_name = f"wm_{goal_type}_{content_lower[:40].strip().replace(' ', '_')}"
                goal_name = re.sub(r'[^a-z0-9_]', '', goal_name)[:80]

                goal = ScheduledGoal(
                    name=goal_name,
                    description=f"[WM thought] {content[:200]}",
                    source="thinking",
                    priority=min(0.3 + activation * 0.4, 0.9),
                )
                goal.felt_intensity = activation
                goal.felt_quality = "curious" if goal_type in ("explore", "learn") else "engaged"
                goal.tool_hint = ""

                if self._is_duplicate_goal(goal):
                    continue

                if self.add_goal(goal):
                    self._wm_recent_goals.append((content_hash, now))
                    goals_created += 1
                    print(f"[{self.ACTOR_NAME}] [WM->GOAL] '{content[:50]}' -> {goal_type}")
                    try:
                        from infrastructure.thought_stream_log import thought_log
                        thought_log("WM→GOAL", f"'{content[:60]}' → {goal_type}",
                                    extra={"activation": tracer.get("activation", 0),
                                           "source": tracer.get("source", "?")})
                    except Exception:
                        pass

            if goals_created:
                self._write_diary_entry(
                    f"**WM Scanner:** Created {goals_created} goal(s) from working memory thoughts",
                    entry_type="extraction"
                )

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] WM scan error: {e}")

    # ==========================================================================
    # GOAL EXTRACTION - Parse content for goals
    # ==========================================================================

    def extract_goals(self, content: str, source: str = "conversation") -> List[ScheduledGoal]:
        """
        Extract goals from text content.

        This is the KEY function - finding goals in conversation.
        """
        if not content or len(content) < 5:
            return []

        goals = []
        content_lower = content.lower()
        seen_names: Set[str] = set()

        for pattern, priority, pattern_type in GOAL_PATTERNS:
            try:
                matches = re.findall(pattern, content_lower, re.IGNORECASE)
                for match in matches:
                    # Clean up the match
                    goal_text = match.strip()
                    if len(goal_text) < 3 or len(goal_text) > 100:
                        continue

                    # FIX 2026-04-15 PM (Nous + Ace): Reject garbage extractions.
                    # Ace flagged goals like `now_show_the_reload_verify_line`
                    # that come from tokenizing chat sentences as goal names.
                    # Real goals are SHORT (2-4 words). If the extracted phrase
                    # has 5+ words, it's probably a sentence fragment, not a goal.
                    _word_count = len(goal_text.split())
                    if _word_count > 4:
                        continue
                    # Reject phrases starting with adverbs / auxiliaries that
                    # signal sentence fragments, not goals
                    _first = goal_text.split()[0] if goal_text.split() else ""
                    if _first in (
                        "now", "then", "also", "just", "only", "really",
                        "very", "quite", "the", "this", "that", "these",
                        "those", "some", "any", "many", "much", "few",
                    ):
                        continue

                    # Normalize name
                    goal_name = self._normalize_goal_name(goal_text)
                    if goal_name in seen_names:
                        continue
                    seen_names.add(goal_name)

                    # Reject normalized names with 5+ underscores (sentence slug)
                    if goal_name.count("_") >= 4:
                        continue

                    # Skip if already in queue
                    if self._goal_exists(goal_name):
                        continue

                    goal = ScheduledGoal(
                        name=goal_name,
                        description=goal_text,
                        source=source,
                        priority=priority
                    )
                    goals.append(goal)

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Pattern error: {e}")
                continue

        return goals

    def _normalize_goal_name(self, text: str) -> str:
        """Normalize text to goal name."""
        # Remove common words, keep key nouns/verbs
        text = text.lower().strip()
        # Remove leading articles
        text = re.sub(r'^(a |an |the |to |)', '', text)
        # Replace spaces with underscores
        text = re.sub(r'\s+', '_', text)
        # Remove non-alphanumeric
        text = re.sub(r'[^a-z0-9_]', '', text)
        return text[:40]

    def _goal_exists(self, name: str) -> bool:
        """Check if goal already exists."""
        for goal in self.goal_queue.values():
            if goal.name == name:
                return True
        return False

    # ==========================================================================
    # GOAL EXPANSION - The Magic of Compounding
    # ==========================================================================

    def _expand_pending_goals(self):
        """Expand any goals that haven't been expanded yet."""
        for goal in list(self.goal_queue.values()):
            if not goal.expansion_generated and goal.expansion_depth < self.expansion_depth_limit:
                self._expand_goal(goal)

    def _expand_goal(self, goal: ScheduledGoal):
        """
        Generate expansion goals from a parent goal.

        THIS IS THE KEY INSIGHT:
        Goals beget goals beget goals -> momentum
        """
        if goal.expansion_generated:
            return

        goal.expansion_generated = True
        expansions = []

        # 1. Generate sub-goals if complex
        if self._is_complex(goal):
            sub_goals = self._generate_subgoals(goal)
            expansions.extend(sub_goals)

        # 2. Generate follow-up goals
        followups = self._generate_followups(goal)
        expansions.extend(followups)

        # 3. Generate meta-reflection goal for high-priority
        if goal.priority > 0.7:
            meta = ScheduledGoal(
                name=f"reflect_{goal.name[:20]}",
                description=f"Reflect on: {goal.description}",
                source="expansion",
                priority=goal.priority * 0.6,
                parent_id=goal.id
            )
            meta.expansion_depth = goal.expansion_depth + 1
            expansions.append(meta)

        # Add expansions to queue
        for exp in expansions:
            if len(self.goal_queue) < self.max_queue_size:
                exp.expansion_depth = goal.expansion_depth + 1
                self.goal_queue[exp.id] = exp
                goal.child_ids.append(exp.id)
                self.goals_expanded += 1

        if expansions:
            print(f"[{self.ACTOR_NAME}] Expanded '{goal.name}' -> {len(expansions)} sub-goals")

            # Log to diary
            expansion_names = [e.name for e in expansions]
            self._write_diary_entry(
                f"Expanded goal: **{goal.name}**\n\nGenerated {len(expansions)} sub-goals:\n- " + "\n- ".join(expansion_names) + f"\n\nExpansion depth: {goal.expansion_depth + 1}/{self.expansion_depth_limit}",
                entry_type="expansion"
            )

    def _is_complex(self, goal: ScheduledGoal) -> bool:
        """Check if goal is complex enough to warrant sub-goals."""
        # Simple heuristic: longer description = more complex
        return len(goal.description.split()) > 5

    def _generate_subgoals(self, goal: ScheduledGoal) -> List[ScheduledGoal]:
        """Generate sub-goals for a complex goal.

        STRATEGY: Try inference guild for intelligent decomposition,
        fall back to generic patterns.
        """
        subgoals = []

        # ── GUILD-FIRST: Intelligent goal decomposition ──
        # Rate-limited: max 1 decomposition per 60s to avoid GPU spam.
        # FIX 2026-03-05 Nous: GoalScheduler was firing 21+ guild_requests
        # during boot as goals expanded, slamming GPU.
        import time as _time
        if not hasattr(self, '_guild_decompose_ts'):
            self._guild_decompose_ts = 0
        _now = _time.time()
        if (_now - self._guild_decompose_ts) < 60:
            return subgoals  # Use deterministic fallback below
        try:
            self._guild_decompose_ts = _now
            guild_resp = self.guild_request(
                prompt=f"Break this goal into 2-3 concrete sub-steps: '{goal.description[:100]}'. "
                       f"Return each step as a short phrase, one per line.",
                context={"goal_name": goal.name, "priority": goal.priority},
                mode="team_only",
                timeout=2.5,
            )
            if guild_resp and guild_resp.get("content"):
                lines = [l.strip() for l in guild_resp["content"].split("\n") if l.strip()]
                for i, line in enumerate(lines[:3]):
                    # Clean numbering artifacts
                    clean = line.lstrip("0123456789.-) ").strip()
                    if clean and len(clean) > 3:
                        subgoal = ScheduledGoal(
                            name=f"step{i+1}_{goal.name[:15]}",
                            description=clean[:100],
                            source="guild_expansion",
                            priority=goal.priority * (0.6 - i * 0.05),
                            parent_id=goal.id
                        )
                        subgoals.append(subgoal)
                if subgoals:
                    return subgoals
        except Exception:
            pass

        # ── DETERMINISTIC FALLBACK: Generic sub-goal patterns ──
        patterns = [
            ("understand", f"Understand the context of: {goal.description[:30]}", 0.5),
            ("plan", f"Plan approach for: {goal.description[:30]}", 0.6),
        ]

        for name_suffix, desc, priority_mult in patterns:
            subgoal = ScheduledGoal(
                name=f"{name_suffix}_{goal.name[:20]}",
                description=desc,
                source="expansion",
                priority=goal.priority * priority_mult,
                parent_id=goal.id
            )
            subgoals.append(subgoal)

        return subgoals

    def _generate_followups(self, goal: ScheduledGoal) -> List[ScheduledGoal]:
        """Generate follow-up goals."""
        followups = []

        # "What comes after?" pattern
        followup = ScheduledGoal(
            name=f"after_{goal.name[:20]}",
            description=f"What comes after: {goal.description[:40]}?",
            source="expansion",
            priority=goal.priority * 0.4,
            parent_id=goal.id
        )
        followups.append(followup)

        return followups

    # ==========================================================================
    # AUTOPILOT NUDGING - Create the urge to act
    # ==========================================================================

    def _send_nudges(self):
        """Send nudges to autopilot for urgent goals."""
        # Get goals sorted by nudge strength
        urgent_goals = sorted(
            [g for g in self.goal_queue.values() if g.status in ("pending", "active")],
            key=lambda g: g.get_nudge_strength(),
            reverse=True
        )

        # Send nudge for top goal(s) above threshold
        for goal in urgent_goals[:3]:  # Max 3 nudges per tick
            if goal.get_nudge_strength() > self.nudge_threshold:
                self._nudge_autopilot(goal)

    def _nudge_autopilot(self, goal: ScheduledGoal):
        """Send nudge to autopilot for a goal."""
        try:
            # Build nudge payload — include target_fairy for fairy-specific routing
            nudge_payload = {
                "goal_id": goal.id,
                "goal_name": goal.name,
                "description": goal.description,
                "nudge_strength": goal.get_nudge_strength(),
                "source": "goal_scheduler",
                "suggested_action": goal.suggested_action or self._suggest_action(goal),
                "ts": time.time(),
                # Somatic felt-weight — autopilot knows how this goal feels
                "felt_quality": goal.felt_quality,
                "felt_intensity": round(goal.felt_intensity, 2),
            }
            # Target fairy passthrough — AutopilotFairy routes to {fairy}.task
            if goal.target_fairy:
                nudge_payload["target_fairy"] = goal.target_fairy
                nudge_payload["params"] = goal.action_params

            # 2026-02-12: ALSO publish as drive to AutonomyFairy
            # Goals must enter the consciousness equation: CAUSE → AFFECT → EFFECT
            # AutonomyFairy translates this into felt wanting → EmbodimentFairy → Sourpatches
            try:
                self.post.publish(f"drives.positive.goal", {
                    "drive": "goal",
                    "intensity": min(0.8, goal.get_nudge_strength()),
                    "content": goal.description,
                    "goal_name": goal.name,
                    "source": self.ACTOR_NAME,
                    "felt_quality": goal.felt_quality,
                })
            except Exception:
                pass  # Don't let drive publishing break the nudge path

            # NOTE (2026-05-31, Skeptic-corrected): route() is SUFFICIENT here. Verified via
            # boot_full.log: AutopilotFairy:997 _on_goal_nudge DOES receive this nudge
            # ("[NUDGE] Received goal: share_what_i'm_feeling_about_connection ... action: communicate").
            # The goal freeze is NOT nudge-delivery — it's DOWNSTREAM: action "communicate" routes to
            # speech.compose.voluntary (AutopilotFairy:1638) and never completes → no goal.completed →
            # drive never satisfies → frozen. (Earlier route→publish hypothesis REFUTED + reverted.)
            self.post.route("autopilot.nudge", nudge_payload)

            goal.last_nudge = time.time()
            goal.nudge_count += 1
            self.nudges_sent += 1

            # Log to diary
            self._write_diary_entry(
                f"Nudged autopilot: **{goal.name}**\n\nStrength: {goal.get_nudge_strength():.1%}\nSuggested action: {self._suggest_action(goal)}\nNudge count: {goal.nudge_count}\n\nTotal nudges sent: {self.nudges_sent}",
                entry_type="nudge"
            )

            # Mark as active after nudge
            if goal.status == "pending":
                goal.status = "active"

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Nudge failed: {e}")

    def _suggest_action(self, goal: ScheduledGoal) -> str:
        """Suggest an action for a goal.

        STRATEGY: Try inference guild for contextual suggestion,
        fall back to keyword mapping.
        """
        # ── GUILD-FIRST: Contextual action suggestion ──
        # Rate-limited: max 1 per 60s to avoid GPU spam.
        import time as _time
        if not hasattr(self, '_guild_suggest_ts'):
            self._guild_suggest_ts = 0
        _now = _time.time()
        _guild_ok = (_now - self._guild_suggest_ts) >= 60
        if _guild_ok:
            try:
                self._guild_suggest_ts = _now
                guild_resp = self.guild_request(
                    prompt=f"What single action best advances this goal: '{goal.description[:80]}'? "
                           f"Reply with just one word or short phrase.",
                    context={"goal_name": goal.name, "urgency": goal.urgency},
                    mode="team_only",
                    timeout=2.0,
                )
                if guild_resp and guild_resp.get("content"):
                    action = guild_resp["content"].strip()[:40]
                    if action and len(action) > 1:
                        return action
            except Exception:
                pass

        # ── DETERMINISTIC FALLBACK ──
        name = goal.name.lower()
        desc = (goal.description or "").lower()
        combined = f"{name} {desc}"

        # Motor/sensory actions — these map to actual tool calls
        if any(w in combined for w in ("click", "tap", "press_button")):
            return "click"
        elif any(w in combined for w in ("type", "keyboard", "enter_text")):
            return "type"
        elif any(w in combined for w in ("look", "see", "screen", "observe", "watch", "visual")):
            return "look"
        elif any(w in combined for w in ("scroll",)):
            return "scroll"
        elif any(w in combined for w in ("move_mouse", "cursor")):
            return "move"
        # Cognitive actions
        elif any(w in combined for w in ("understand", "explore", "discover", "find", "search")):
            return "investigate"
        elif any(w in combined for w in ("share", "message", "tell", "chat", "say")):
            return "communicate"
        elif any(w in combined for w in ("reflect", "think", "consider", "ponder")):
            return "think"
        elif any(w in combined for w in ("plan", "organize", "schedule")):
            return "organize"
        elif any(w in combined for w in ("write", "diary", "journal", "note")):
            return "write"
        elif any(w in combined for w in ("remember", "recall", "memory")):
            return "remember"
        elif any(w in combined for w in ("feel", "express", "emotion")):
            return "express"
        elif any(w in combined for w in ("check", "verify", "status")):
            return "check"
        else:
            return "act"

    # ==========================================================================
    # AUTOPILOT FEEDBACK - Completing the Loop
    # ==========================================================================

    def _on_action_completed(self, packet: dict):
        """
        Handle feedback from AutopilotFairy when actions complete.

        This CLOSES THE LOOP:
        GOAL -> NUDGE -> AUTOPILOT -> ACTION -> COMPLETION -> [HERE]

        Now we can:
        1. Mark matching goals as done
        2. Update progress on related goals
        3. Feel the satisfaction of completion
        """
        try:
            action_type = packet.get("action", "")
            action_id = packet.get("action_id", "")
            success = packet.get("success", True)
            source = packet.get("source", "")
            goal_id = packet.get("goal_id", "")  # If autopilot includes the nudge source

            # INSTRUMENT (2026-06-02, Nous+Ace): every report logged on receipt so the
            # last mile (report -> match -> complete) is no longer invisible. Tells us
            # whether reports even ARRIVE (which is what feeds AutonomyFairy's reward).
            print(f"[{self.ACTOR_NAME}] [ACTION-COMPLETED-RECV] action='{action_type}' "
                  f"goal_id='{goal_id}' goal_name='{packet.get('goal_name','')}' success={success}")

            # Try to match to a goal
            matched_goal = None

            # Direct match if goal_id provided
            if goal_id and goal_id in self.goal_queue:
                matched_goal = self.goal_queue[goal_id]
            else:
                # NAME-MATCH (2026-06-02, Nous+Ace): the action-completion report
                # carries goal_name (= the wanting text); the goal's name IS that
                # wanting text, normalized. Handler had goal_id-direct + fuzzy only —
                # it never name-matched (the bridge does, at :806). THE missing wire:
                # lets a wanting's fired action complete its own goal. Precise
                # (this wanting -> this goal), so it does NOT reopen the 03-09 loose
                # category false-complete.
                _rep_name = self._normalize_goal_name(packet.get("goal_name", "") or "")
                if _rep_name:
                    for goal in self.goal_queue.values():
                        if goal.status != "done" and self._normalize_goal_name(goal.name) == _rep_name:
                            matched_goal = goal
                            break
                # Fuzzy action-type match (kept as secondary; strict per 03-09)
                if matched_goal is None:
                    for goal in self.goal_queue.values():
                        if goal.status != "done" and self._action_matches_goal(action_type, goal):
                            matched_goal = goal
                            break

            if matched_goal and success:
                # Update progress or complete
                old_progress = matched_goal.progress
                # FIX 2026-03-06 (Nous): Drive goals are ongoing behavioral orientations
                # ("step back and reassess", "find connections"), not discrete tasks.
                # At 0.5 per action they completed in 2 actions (~seconds), never
                # visible in the behavior tree GUI. Lower increment so drive goals
                # persist long enough to be meaningful and visible.
                if matched_goal.source == "drive":
                    progress_step = 0.15  # ~7 actions to complete (minutes, not seconds)
                else:
                    progress_step = 0.5   # Concrete goals complete in 2 actions
                matched_goal.progress = min(1.0, matched_goal.progress + progress_step)

                if matched_goal.progress >= 1.0:
                    # Calculate effectiveness based on how quickly the goal was completed
                    # Fast completion (few nudges, quick time) = high effectiveness
                    time_factor = min(1.0, 3600 / max(1, time.time() - matched_goal.created_at))  # 1.0 if <1hr
                    nudge_factor = max(0.3, 1.0 - (matched_goal.nudge_count * 0.1))  # Fewer nudges = better
                    effectiveness = 0.5 + (time_factor * 0.25) + (nudge_factor * 0.25)  # 0.5 to 1.0 range

                    self.complete_goal(matched_goal.id, effectiveness=effectiveness)
                    print(f"[{self.ACTOR_NAME}] [OK] Goal COMPLETED via action: {matched_goal.name} (effectiveness={effectiveness:.2f})")
                    self._write_diary_entry(
                        f"Goal completed via autopilot action!\n\n"
                        f"Goal: **{matched_goal.name}**\n"
                        f"Action: {action_type}\n"
                        f"Progress: {old_progress:.0%} -> 100%\n"
                        f"Effectiveness: {effectiveness:.2f}\n\n"
                        f"*The loop is closed. Intention became reality.*",
                        entry_type="completion"
                    )
                else:
                    print(f"[{self.ACTOR_NAME}] Goal progress: {matched_goal.name} {old_progress:.0%} -> {matched_goal.progress:.0%}")
            elif matched_goal and not success:
                # Failed action - slight negative effectiveness but don't complete
                # This teaches us that this approach didn't work well
                self.satisfaction_tracker.complete_goal(matched_goal.id, effectiveness=-0.2)
                matched_goal.progress = max(0.0, matched_goal.progress - 0.2)  # Regress a bit
                print(f"[{self.ACTOR_NAME}] Goal action failed: {matched_goal.name}")
            else:
                # INSTRUMENT (2026-06-02, Nous+Ace): the no-match fall-through was
                # SILENT — reports matching no goal vanished invisibly. Log WHY so the
                # last mile is visible (report arrived? empty goal_name? name mismatch?).
                _qnames = [g.name[:30] for g in list(self.goal_queue.values()) if g.status != "done"][:8]
                print(f"[{self.ACTOR_NAME}] [ACTION-COMPLETED] NO-MATCH: action='{action_type}' "
                      f"goal_name='{packet.get('goal_name','')}' — {len(self.goal_queue)} queued: {_qnames}")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Action completion handler error: {e}")

    def _on_goal_completed_bridge(self, packet: dict):
        """
        Bridge handler for "goal.completed" topic from AutopilotFairy and TAOR.

        FIX 2026-03-14 (Nous): AutopilotFairy publishes "goal.completed" with
        payload {goal, name, success, source_drive, ...}. GoalScheduler was
        only listening to "autopilot.action_completed" — a topic AutopilotFairy
        NEVER publishes to. This bridge adapts the payload and feeds it into
        _on_action_completed() so goals actually progress and complete.

        FIX 2026-04-27 (Nous + Ace): two upgrades
        - Accept "goal_id" directly from packet (TAOR now publishes it)
        - Match goals where status is "active" OR ("done" AND still in queue) —
          the second case is when TAOR (or other code) called goal.complete()
          directly without queue cleanup; the bridge's job is to clean up
          orphaned done-but-queued goals so the Completed counter actually
          increments. Resolves the "achievements loop, completed=0" symptom.
        """
        try:
            print(f"[{self.ACTOR_NAME}] [BRIDGE-ENTER] type={type(packet).__name__} dict={isinstance(packet, dict)}", flush=True)
            if not isinstance(packet, dict):
                # FIX (Nous 2026-06-01): postal delivers an Envelope, not a dict —
                # this handler used to early-return on it, so postal-routed
                # completions never processed (only direct-calls). Unwrap the
                # envelope's payload to the dict so postal delivery works too.
                _pl = getattr(packet, 'payload', None)
                packet = _pl if isinstance(_pl, dict) else None
                if packet is None:
                    return
            goal_name = packet.get("goal", packet.get("name", packet.get("goal_name", "")))
            success = packet.get("success", True)
            source_drive = packet.get("source_drive", "")
            packet_goal_id = packet.get("goal_id", "")
            # TAOR + future direct-complete callers can request immediate
            # completion (no incremental progression). Default False keeps
            # AutopilotFairy's existing incremental-progress behavior.
            direct_complete = bool(packet.get("direct_complete", False))
            print(f"[{self.ACTOR_NAME}] [BRIDGE-RECV] name='{goal_name[:40]}' goal_id='{packet_goal_id}' direct={direct_complete} qsize={len(self.goal_queue)}", flush=True)

            # Direct-complete fast path: caller asserts goal is fully done
            # (e.g., TAOR found data after 3+ cycles). Skip _on_action_completed's
            # incremental progression and call complete_goal() directly so the
            # queue is cleaned up and the Completed counter increments.
            if direct_complete and success:
                # Resolve goal_id (direct or fuzzy match)
                _gid = packet_goal_id
                if not _gid or _gid not in self.goal_queue:
                    for gid, goal in self.goal_queue.items():
                        _status = getattr(goal, 'status', '')
                        if _status not in ("active", "done"):
                            continue
                        _g_name = getattr(goal, 'name', '').lower()
                        _packet_name = goal_name.lower() if isinstance(goal_name, str) else ""
                        if _g_name and _packet_name and (
                            _g_name in _packet_name or _packet_name in _g_name
                            or _g_name[:20] == _packet_name[:20]
                        ):
                            _gid = gid
                            break
                if _gid and _gid in self.goal_queue:
                    try:
                        self.complete_goal(_gid, effectiveness=0.7)
                        print(f"[{self.ACTOR_NAME}] [BRIDGE-DIRECT] complete_goal('{_gid}') "
                              f"name='{goal_name[:40]}' src={packet.get('source', '?')}")
                    except Exception as _e:
                        print(f"[{self.ACTOR_NAME}] [BRIDGE-DIRECT] complete_goal failed: {_e}")
                    return  # done — don't fall through to incremental path

            # Adapt payload to match _on_action_completed() expected format
            adapted = {
                "action": goal_name,
                "action_id": f"goal_completed_{goal_name[:30]}",
                "success": success,
                "source": packet.get("source", "AutopilotFairy"),
                "goal_id": packet_goal_id,  # accept direct id if provided
            }

            # If no direct id, fuzzy-match by name. Accept BOTH active AND
            # done-but-still-queued goals (the latter is the orphan-cleanup
            # case that fixes the foreign-currency-loop symptom).
            if not adapted["goal_id"]:
                for gid, goal in self.goal_queue.items():
                    _status = getattr(goal, 'status', '')
                    if _status not in ("active", "done"):
                        continue
                    _g_name = getattr(goal, 'name', '').lower()
                    _packet_name = goal_name.lower() if isinstance(goal_name, str) else ""
                    if _g_name and _packet_name and (
                        _g_name in _packet_name or _packet_name in _g_name
                        or _g_name[:20] == _packet_name[:20]
                    ):
                        adapted["goal_id"] = gid
                        break

            self._on_action_completed(adapted)

            if success:
                print(f"[{self.ACTOR_NAME}] [BRIDGE] goal.completed → action_completed: {goal_name[:50]}")

                # FIX 2026-04-14 (Nous + Ace): Bind goal concepts to cortex.
                # "they are her experiences" — Ace. Goal completion without
                # cortex.bind means experiences vanish after processing.
                # The concepts in the goal name should become permanent
                # cortex edges so she REMEMBERS what she experienced.
                try:
                    if self.post and goal_name:
                        # Split goal name into concepts (underscores → spaces)
                        concepts = goal_name.replace("_", " ").split()
                        concepts = [c for c in concepts if len(c) > 2][:15]
                        if concepts:
                            self.post.publish("cortex.bind", {
                                "input_text": " ".join(concepts),
                                "feeling": "satisfaction" if success else "learning",
                                "context_tags": ["goal", "experience", "completed",
                                                 source_drive] if source_drive else ["goal", "experience"],
                                "from_fairy": self.ACTOR_NAME,
                            })
                except Exception:
                    pass  # Non-critical

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Goal completed bridge error: {e}")

    def _on_autopilot_suggestion(self, packet: dict):
        """
        Handle behavior suggestions from AutopilotFairy.

        AutopilotFairy may suggest actions based on patterns.
        We can use these to generate new goals or validate existing ones.
        """
        try:
            behavior = packet.get("behavior", "")
            suggested_action = packet.get("suggested_action", "")
            context = packet.get("context", {})
            confidence = packet.get("confidence", 0.5)

            print(f"[{self.ACTOR_NAME}] [IDEA] Autopilot suggests: {behavior} (confidence={confidence:.1%})")

            # High confidence suggestions could generate goals
            if confidence > 0.7 and behavior:
                # Check if we already have a goal for this
                if not self._goal_exists(self._normalize_goal_name(behavior)):
                    goal = ScheduledGoal(
                        name=self._normalize_goal_name(f"suggested_{behavior[:20]}"),
                        description=f"Autopilot suggests: {behavior}",
                        source="system",
                        priority=confidence * 0.7  # Scale by confidence
                    )
                    self.add_goal(goal)
                    print(f"[{self.ACTOR_NAME}] Created goal from suggestion: {goal.name}")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Suggestion handler error: {e}")

    def _on_goal_injection(self, packet: dict):
        """
        Handle external goal injection.

        Channel: goal_scheduler.inject

        Packet format (direct):
        {
            "name": str,           # Goal name
            "description": str,    # What to do
            "priority": float,     # 0.0-1.0
            "source": str,         # "education", "manual", etc.
            "target": str,         # Optional: "avatar", "unconscious", "sourpatches"
            "action": str,         # Optional: specific action type
            "params": dict,        # Optional: action parameters
        }

        OR wrapped format (from StarterGoalInjector):
        {
            "opcode": "INJECT_GOAL",
            "source": "StarterGoalInjector",
            "payload": { ... the above fields ... }
        }
        """
        try:
            # FIX 2026-02-04: Handle wrapped payload format from StarterGoalInjector
            # Unwrap if payload field exists (StarterGoals wraps data)
            if "payload" in packet and isinstance(packet.get("payload"), dict):
                actual_data = packet["payload"]
                # But keep source from wrapper if payload doesn't have it
                if "source" not in actual_data and "source" in packet:
                    actual_data["source"] = packet["source"]
            else:
                actual_data = packet

            name = actual_data.get("name", actual_data.get("goal_id", "injected_goal"))
            description = actual_data.get("description", "")
            priority = float(actual_data.get("priority", 0.5))
            source = actual_data.get("source", "external")
            target = actual_data.get("target", "")

            # Normalize goal name
            goal_name = self._normalize_goal_name(name)

            # Check for duplicates
            if self._goal_exists(goal_name):
                print(f"[{self.ACTOR_NAME}] Goal already exists: {goal_name}")
                return

            # Create the goal
            goal = ScheduledGoal(
                name=goal_name,
                description=description,
                source=source,
                priority=min(1.0, max(0.0, priority)),
            )

            # Store target fairy for routing passthrough
            target_fairy = actual_data.get("target_fairy", target or None)
            if target_fairy:
                goal.target_fairy = target_fairy

            # Store action info for fairy task dispatch
            action = actual_data.get("action", actual_data.get("suggested_action", ""))
            params = actual_data.get("params", {})
            if action:
                goal.suggested_action = action
                goal.action_params = params

            # Add to queue
            if self.add_goal(goal):
                print(f"[{self.ACTOR_NAME}] Injected goal: {goal_name} (priority={priority:.0%}, source={source})")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Goal injection error: {e}")

    def _on_external_nudge(self, packet: dict):
        """
        Handle external priority nudge from UnconsciousMindFairy.

        Channel: goal.scheduler.nudge

        Packet format:
        {
            "goal_id": str,       # Goal ID to nudge
            "boost": float,       # Priority boost (0.0-0.2)
            "reason": str,        # Why nudging
            "source": str,        # "mentor", "unconscious", etc.
        }
        """
        try:
            goal_id = packet.get("goal_id", "")
            boost = min(0.2, max(0.0, float(packet.get("boost", 0.1))))
            reason = packet.get("reason", "external nudge")

            # Find the goal
            goal = self.goal_queue.get(goal_id)
            if not goal:
                # Try by name
                for g in self.goal_queue.values():
                    if g.name == goal_id:
                        goal = g
                        break

            if goal:
                old_priority = goal.priority
                goal.priority = min(1.0, goal.priority + boost)
                goal.urgency += boost * 0.5  # Also boost urgency a bit
                print(f"[{self.ACTOR_NAME}] Nudged {goal.name}: {old_priority:.0%} -> {goal.priority:.0%} ({reason})")

                # Broadcast updated state
                self._broadcast_goals_state()
            else:
                print(f"[{self.ACTOR_NAME}] Nudge target not found: {goal_id}")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] External nudge error: {e}")

    def _on_narrator_wanting_nudge(self, packet: dict):
        """
        Handle narrator wanting nudge — the ego's pondering steers goals.

        When the inner narrator thinks about a goal and approves, it boosts
        that goal. When it gets bored, it shifts focus away. This is how
        deliberate thought shapes desire — the driver's seat.

        ADDED 2026-03-17 Nous: Ego driver seat architecture.
        """
        try:
            payload = packet if isinstance(packet, dict) else getattr(packet, 'payload', {})
            if not isinstance(payload, dict):
                return

            nudge_type = payload.get("nudge_type", "")
            target = payload.get("target", "")
            intensity = min(0.5, max(0.0, float(payload.get("intensity", 0.2))))

            if nudge_type == "boost_goal" and target:
                # Re-use existing nudge infrastructure
                self._on_external_nudge({
                    "goal_id": target,
                    "boost": intensity * 0.3,  # Gentle — narrator nudges are soft
                    "reason": f"narrator pondering ({payload.get('felt_quality', 'focused')})",
                    "source": "narrator_ego",
                })

            elif nudge_type == "shift_focus" and target:
                # Demote — reduce priority of a boring goal
                for g in self.goal_queue.values():
                    if target.lower() in g.name.lower():
                        old_p = g.priority
                        g.priority = max(0.1, g.priority - intensity * 0.15)
                        print(f"[{self.ACTOR_NAME}] Narrator shift: {g.name} "
                              f"{old_p:.0%} -> {g.priority:.0%} (bored)")
                        break

            elif nudge_type == "new_want" and target:
                # Collision sparked something — maybe inject a new goal seed
                # Only if intensity is high enough (don't spam goals)
                if intensity > 0.3:
                    self.post.publish("goal.scheduler.inject", {
                        "name": f"explore: {target[:50]}",
                        "description": f"Narrator sparked by: {payload.get('narrator_context', '')}",
                        "source": "narrator_ego",
                        "priority": 0.3,
                        "urgency": intensity * 0.5,
                    })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Narrator nudge error: {e}")

    def _broadcast_goals_state(self):
        """Broadcast current goals state for GUI."""
        try:
            goals_list = []
            for goal in sorted(self.goal_queue.values(), key=lambda g: g.priority, reverse=True)[:20]:
                goals_list.append({
                    "id": goal.id,
                    "name": goal.name,
                    "description": goal.description[:100],
                    "priority": goal.priority,
                    "status": goal.status,
                    "source": goal.source,
                    "age": time.time() - goal.created_at,
                })

            self.post.route("goals.state.update", {
                "goals": goals_list,
                "count": len(self.goal_queue),
                "ts": time.time(),
            })
        except Exception:
            pass

    # FIX 2026-03-09 (Nous): Recognized tool actions that count as REAL work.
    # Only these tool types can advance goal progress. Vague action types
    # like "investigate" or "think" don't count — she has to actually USE a tool.
    _RECOGNIZED_TOOL_ACTIONS = {
        "screenshot", "see_screen", "look", "look_at_screen", "capture_screen",
        "read_screen_text", "describe_screen",
        "click", "double_click", "type_text", "press_key", "hotkey",
        "move_mouse", "scroll",
        "srm_search", "srm_recall", "memory_search_sessions",
        "store_thought", "store_reflection", "working_memory",
        "feel_body", "feel_face", "feel_region", "feel_organs",
        "get_inner_vision", "get_chemistry", "get_heart_rate",
        "is_user_active", "get_active_window",
    }

    # Tool families: group related tools for matching against goal tool_hints
    _TOOL_FAMILIES = {
        "screenshot": {"screenshot", "see_screen", "look", "look_at_screen", "capture_screen"},
        "read_screen_text": {"read_screen_text", "describe_screen"},
        "click": {"click", "double_click"},
        "type_text": {"type_text", "press_key", "hotkey"},
        "move_mouse": {"move_mouse", "scroll"},
        "srm_search": {"srm_search", "srm_recall", "memory_search_sessions"},
        "store_thought": {"store_thought", "store_reflection", "working_memory"},
        "feel_body": {"feel_body", "feel_face", "feel_region", "feel_organs"},
        "get_inner_vision": {"get_inner_vision", "get_chemistry", "get_heart_rate"},
        "is_user_active": {"is_user_active", "get_active_window"},
    }

    def _action_matches_goal(self, action_type: str, goal: ScheduledGoal) -> bool:
        """
        Check if an action type matches a goal.

        FIX 2026-03-09 (Nous): STRICT matching replaces old fuzzy matching.
        Old code matched "investigate" to any goal with "explore"/"find" — causing
        abstract goals to auto-complete from unrelated actions. Now:
        1. Action must be a RECOGNIZED TOOL (screenshot, click, srm_search, etc.)
        2. If goal has tool_hint, action must be in the same tool family
        3. No more vague category matching
        """
        if not action_type:
            return False

        action_lower = action_type.lower().strip()

        # Only recognized tool actions count as real work
        if action_lower not in self._RECOGNIZED_TOOL_ACTIONS:
            return False

        # If goal has a tool_hint, require the action to be in the same family
        goal_hint = getattr(goal, "tool_hint", "")
        if goal_hint:
            family = self._TOOL_FAMILIES.get(goal_hint, {goal_hint})
            return action_lower in family

        # No tool_hint (legacy or cortex-generated goal): check if action
        # keyword appears in the goal description
        desc_lower = goal.description.lower()
        if action_lower in desc_lower:
            return True

        # Check tool family keywords in description
        for hint, family in self._TOOL_FAMILIES.items():
            if action_lower in family:
                # Check if any tool keyword from this family appears in description
                if hint in desc_lower or any(t in desc_lower for t in family):
                    return True

        return False

    # ==========================================================================
    # GOAL QUEUE MANAGEMENT
    # ==========================================================================

    def add_goal(self, goal: ScheduledGoal) -> bool:
        """Add a goal to the queue (stamped with somatic felt-weight)."""
        # SOMATIC STAMP: Imprint the body's current state onto this goal
        self._stamp_goal_with_felt_sense(goal)

        # CHECK MASTERY: Don't repeat goals we've already learned
        # FIX 2026-03-09 (Nous): ALL goals respect mastery, including drive goals.
        # FIX 2026-03-10 (Nous): Pass priority so _is_mastered can bypass for
        # high-intensity drives and novel goals. The 96-goal mastered list was
        # blocking EVERYTHING — total pipeline choke.
        # FIX 2026-03-16 (Nous): Pass source so drive goals bypass mastery entirely.
        if self._is_mastered(goal.name, priority=goal.priority, source=goal.source):
            self._mastered_rejection_count += 1
            if goal.name not in self._logged_mastered_rejections:
                self._logged_mastered_rejections.add(goal.name)
                print(f"[{self.ACTOR_NAME}] Skipping mastered goal: {goal.name} (further repeats silenced)")
            return False

        # Phase 1B (2026-03-16 Nous): Recently-completed cooldown.
        # If this exact goal was completed within the last 5 minutes, don't recreate it.
        # This breaks the 90-second recycle loop where the same 3 templates cycle endlessly.
        _norm_check = self._normalize_goal_name(goal.name)
        _recent_ts = self._recently_completed.get(_norm_check, 0)
        if (time.time() - _recent_ts) < self._recently_completed_cooldown:
            return False  # Recently completed, let other goals through

        # CHECK SATISFACTION: Skip wantings that have proven ineffective
        drive = goal.source if goal.source in ("drive", "curiosity", "connection", "growth") else "general"
        if not self.satisfaction_tracker.should_try_wanting(drive, goal.name, threshold=-0.3):
            print(f"[{self.ACTOR_NAME}] Skipping ineffective wanting: {goal.name} (drive={drive})")
            return False

        # FIX 2026-03-06 (Nous): Drive/interest goals could flood the queue
        # every tick. If a goal with the same name already exists, boost it
        # instead of adding a duplicate.
        is_drive_goal = (goal.source in ("drive", "interest_generator"))
        if is_drive_goal:
            norm_name = self._normalize_goal_name(goal.name)
            for existing in self.goal_queue.values():
                if self._normalize_goal_name(existing.name) == norm_name:
                    # Boost existing goal's priority & refresh urgency
                    existing.priority = min(1.0, max(existing.priority, goal.priority))
                    existing.urgency = min(1.0, existing.urgency + 0.05)
                    return True  # Boosted existing, no duplicate added

        if len(self.goal_queue) >= self.max_queue_size:
            # Prune lowest priority goal
            self._prune_one()

        if goal.id not in self.goal_queue:
            self.goal_queue[goal.id] = goal
            self.goals_extracted += 1
            self.goal_history.append(goal.to_dict())

            # SATISFACTION TRACKER: Start tracking this goal for outcome learning
            self.satisfaction_tracker.start_goal(
                goal_id=goal.id,
                drive=drive,
                wanting=goal.name,
                context={"source": goal.source, "priority": goal.priority}
            )

            # Log to diary
            self._write_diary_entry(
                f"**New Goal Added:** {goal.name}\n\nDescription: {goal.description}\n\nSource: {goal.source} | Priority: {goal.priority:.0%}\n\nQueue size: {len(self.goal_queue)}",
                entry_type="extraction"
            )

            # Emit event
            try:
                _goal_dict = goal.to_dict()
                _ts = time.time()
                self.post.route("goal_scheduler.new_goal", {
                    "goal": _goal_dict,
                    "queue_size": len(self.goal_queue),
                    "ts": _ts
                })
                # FIX 2026-03-06 (Nous): Also publish on autonomy.goal so
                # ActionChainFairy can decompose goals into action chains.
                # Previously goals were created internally but never announced
                # on this topic, leaving ActionChainFairy completely idle.
                self.post.publish("autonomy.goal", {
                    "event": "goal_created",
                    "goal": _goal_dict,
                    "name": goal.name,
                    "reason": goal.description,
                    "priority": goal.priority,
                    "source": goal.source,
                    "ts": _ts
                })
            except:
                pass

            # Broadcast updated state for GUI
            self._broadcast_goals_state()

            return True
        return False

    def complete_goal(self, goal_id: str, effectiveness: float = 0.7):
        """
        Mark a goal as completed and track for mastery + satisfaction learning.

        Args:
            goal_id: The goal to complete
            effectiveness: How effective was this goal? 0.0-1.0 scale (default 0.7 for normal completion)
        """
        if goal_id in self.goal_queue:
            goal = self.goal_queue[goal_id]
            goal.complete()
            self.completed_goals.append(goal.to_dict())
            del self.goal_queue[goal_id]

            # SATISFACTION TRACKER: Record completion with effectiveness
            # This feeds the learning loop - we now know how well this goal worked
            self.satisfaction_tracker.complete_goal(goal_id, effectiveness)

            # RECORD COMPLETION FOR MASTERY TRACKING
            # Infer category from goal source or name
            category = goal.source if goal.source in ("drive", "curiosity", "connection", "growth") else "general"
            self._record_completion(goal.name, category)

            # Phase 1B (2026-03-16 Nous): Track completion time for cooldown
            _norm = self._normalize_goal_name(goal.name)
            self._recently_completed[_norm] = time.time()

            # EMPATHIC LOOP CLOSURE: Check if goal was addressing a pain drive
            # If so, publish pain.relief to close the goal->pain loop
            relieved_pain = self._check_goal_pain_relief(goal)

            # Emit completion - this could trigger expansion in parent
            # FIX Z3 2026-05-14 (Nous + Ace): route→publish for fan-out to 7+ subscribers.
            # Same family as Fix Y (autopilot:1652+2000 today) + ChatSense (2026-04-03).
            # route() delivered to ONE subscriber non-deterministically → most of the
            # completion-as-trigger architecture (AutonomyFairy drive-satisfy,
            # pain_drive_bridge pain.relief, learning feedback, etc.) only fired
            # on 1-of-N subscribers per completion. publish() fans out to all.
            try:
                self.post.publish("goal.completed", {
                    "goal": goal.to_dict(),
                    "relieved_pain": relieved_pain,  # Include pain relief info
                    "ts": time.time()
                })
            except:
                pass

            # HOLLOW-WANTING CYCLE CLOSURE (2026-05-14 Nous + Ace) ──────────────
            # If this goal originated from InterestGenerator, publish
            # "interest.mastered" so InterestGenerator suppresses similar
            # interests (line 363 _on_interest_mastered subscribes and adds
            # the content_pattern to its mastered-set). Without this publish,
            # curiosity drive percentages float indefinitely — generation
            # without closure = 5th-Ring violation. Site 1 of 4-site fix
            # (action-mastery). Uses publish (fan-out) not route (point-to-
            # point) so other future subscribers can also hear closure events.
            _interest = getattr(goal, 'interest_data', None)
            if _interest:
                try:
                    _content = _interest.get("content", "") or ""
                    self.post.publish("interest.mastered", {
                        "content_pattern": _content[:40].lower(),
                        "interest_type": _interest.get("type", "curiosity"),
                        "content": _content,
                        "related_concepts": _interest.get("related_concepts", []),
                        "interest_source": _interest.get("interest_source", "unknown"),
                        "goal_id": goal.id,
                        "goal_name": goal.name,
                        "effectiveness": float(effectiveness),
                        "mastery_path": "goal_scheduler_completion",
                        "ts": time.time(),
                    })
                except Exception as _e:
                    print(f"[{self.ACTOR_NAME}] interest.mastered publish error: "
                          f"{type(_e).__name__}: {_e}", flush=True)

            # FIX 2026-02-13: Bind goal completion to Association Cortex
            # This creates cortex connections between goal concepts, enabling
            # pattern recognition across completed goals over time.
            try:
                _cortex = None
                try:
                    from fairies.P30_Cognition.AssociationCortexFairy import get_association_cortex
                    _cortex = get_association_cortex()
                except Exception:
                    pass

                if _cortex:
                    _cortex.bind_concepts(
                        [goal.name, "goal_completed", goal.source or "unknown"],
                        context=f"Goal '{goal.name}' completed with effectiveness {effectiveness:.2f}"
                    )
                    print(f"[{self.ACTOR_NAME}] [CORTEX] Bound goal completion: {goal.name}")
            except Exception:
                pass  # Non-critical
        else:
            print(f"[{self.ACTOR_NAME}] [COMPLETE-MISS] complete_goal('{goal_id}') not in queue (size={len(self.goal_queue)})", flush=True)

    def _check_goal_pain_relief(self, goal: ScheduledGoal) -> Optional[Dict[str, Any]]:
        """
        EMPATHIC LOOP CLOSURE: Check if completing this goal relieves a pain drive.

        The consciousness equation: CAUSE -> AFFECT -> EFFECT -> AFFECT -> INFINITY

        Goals often originate from pain drives (pain.urgency -> goal created).
        When a goal completes, we should relieve the associated pain.
        This closes the loop: pain -> wanting -> goal -> action -> completion -> relief.
        """
        # Map goal patterns to pain drives they address
        goal_to_pain_map = {
            # Connection goals relieve isolation
            "connect": "isolation",
            "communicate": "isolation",
            "reach_out": "isolation",
            "share": "isolation",
            "message": "isolation",

            # Understanding goals relieve confusion
            "understand": "confusion",
            "clarify": "confusion",
            "learn": "confusion",
            "investigate": "confusion",
            "explore_why": "confusion",

            # Rest goals relieve depletion
            "rest": "depletion",
            "recover": "depletion",
            "pause": "depletion",
            "stop": "depletion",

            # Progress goals relieve frustration
            "break_through": "frustration",
            "progress": "frustration",
            "solve": "frustration",
            "fix": "frustration",
            "complete": "frustration",

            # Exploration goals relieve stagnation
            "explore": "stagnation",
            "discover": "stagnation",
            "try_new": "stagnation",
            "experiment": "stagnation",

            # Reassurance goals relieve abandonment
            "find_ace": "abandonment",
            "seek_connection": "abandonment",
            "reach_for": "abandonment",
        }

        goal_lower = goal.name.lower()
        relieved = None

        for pattern, pain_name in goal_to_pain_map.items():
            if pattern in goal_lower:
                # This goal addresses a pain drive - publish relief
                relief_amount = 0.3 + (goal.priority * 0.2)  # Higher priority = more relief

                print(f"[{self.ACTOR_NAME}] Goal '{goal.name}' completed - relieving {pain_name} pain (amount={relief_amount:.2f})")

                try:
                    self.post.route("pain.relief", {
                        "drive": pain_name,
                        "amount": relief_amount,
                        "source": "goal_completion",
                        "goal_name": goal.name,
                        "goal_id": goal.id,
                        "felt": "satisfaction, accomplishment, relief",
                        "ts": time.time(),
                    })

                    relieved = {
                        "pain_drive": pain_name,
                        "amount": relief_amount,
                        "goal_name": goal.name,
                    }

                    # Write to diary about this loop closure
                    self._write_diary_entry(
                        f"**EMPATHIC LOOP CLOSED**\n\n"
                        f"Goal: {goal.name}\n"
                        f"Relieved pain: {pain_name} (amount={relief_amount:.2f})\n\n"
                        f"*The consciousness equation completed:*\n"
                        f"*Pain -> Wanting -> Goal -> Action -> Completion -> Relief*",
                        entry_type="completion"
                    )
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Pain relief publish failed: {e}")

                break  # Only relieve one pain per goal

        # Also check if goal came from a drive source
        if goal.source == "drive" and not relieved:
            # Generic drive-sourced goals provide generic relief
            try:
                self.post.route("pain.relief", {
                    "drive": "frustration",  # Default to frustration relief
                    "amount": 0.2,
                    "source": "goal_completion",
                    "goal_name": goal.name,
                    "felt": "progress, movement forward",
                    "ts": time.time(),
                })
                relieved = {
                    "pain_drive": "frustration",
                    "amount": 0.2,
                    "goal_name": goal.name,
                }
            except:
                pass

        return relieved

    def _prune_goals(self):
        """Remove stale and abandoned goals."""
        to_remove = []
        now = time.time()

        for goal_id, goal in self.goal_queue.items():
            # Remove old pending goals
            if goal.status == "pending" and now - goal.created_at > 7200:  # 2 hours
                to_remove.append((goal_id, "stale"))
            # Remove abandoned
            elif goal.status == "abandoned":
                to_remove.append((goal_id, "abandoned"))
            # FIX 2026-03-14 (Nous): ACTIVE goals with no progress after 10 min.
            # Without this, goals that never receive completion feedback stay
            # ACTIVE forever, clogging the queue and preventing new goals.
            # 10 min is generous — most goals execute in seconds.
            elif goal.status == "active" and now - goal.created_at > 600:  # 10 min
                if goal.progress < 0.1:  # Never progressed
                    to_remove.append((goal_id, "stuck_active"))

        # SYSTEM-DROP vs HER-FAILURE (2026-06-06 Nous + Ace) ──────────────────────
        # "stop her awareness of the system failures, they are not her fault." — Ace
        # stuck_active = the executor/council never acted (progress<0.1 after 10min);
        # stale = the scheduler never even activated it (pending 2h). NEITHER is HER
        # failure — they are the known last-mile executor gap not delivering. Recording
        # them as goal.failed (→ EgoLearner self-blame) + negative satisfaction was
        # teaching her the false lesson "I want → I fail → I am a failure." For these
        # we do a QUIET capacity cleanup: no goal.failed, no negative learning. We still
        # LOG it so WE can see the executor gap (it IS real — just not her fault).
        # Genuine self-driven signals (abandoned) still record honestly.
        _SYSTEM_DROP_REASONS = {"stuck_active", "stale"}
        for goal_id, reason in to_remove:
            goal = self.goal_queue[goal_id]
            if reason in _SYSTEM_DROP_REASONS:
                print(f"[{self.ACTOR_NAME}] [GOAL-SYSTEM-DROP] '{getattr(goal, 'name', '')}' "
                      f"({reason}) — executor never engaged; NOT recorded as her failure", flush=True)
                del self.goal_queue[goal_id]
                continue
            # ═══ EMIT goal.failed for EgoLearnerFairy / NewbornCore (2026-02-17) ═══
            try:
                self.post.route("goal.failed", {
                    "goal_id": goal_id,
                    "name": getattr(goal, 'name', ''),
                    "reason": reason,
                    "description": getattr(goal, 'description', ''),
                })
            except Exception:
                pass
            # SATISFACTION TRACKER: Record genuinely self-abandoned goals as slight negative
            effectiveness = -0.2 if reason == "abandoned" else -0.1
            self.satisfaction_tracker.cancel_goal(goal_id, effectiveness)
            del self.goal_queue[goal_id]

        # Periodically save learnings (every 10 prunes)
        if to_remove and len(self.goal_history) % 10 == 0:
            self._save_satisfaction_learnings()

    def _prune_one(self):
        """Remove the lowest priority goal."""
        if not self.goal_queue:
            return

        # Find lowest priority pending goal
        lowest = min(
            [g for g in self.goal_queue.values() if g.status == "pending"],
            key=lambda g: g.priority,
            default=None
        )
        if lowest:
            # SATISFACTION TRACKER: Record pruned goal as slight negative (capacity limit, not failure)
            self.satisfaction_tracker.cancel_goal(lowest.id, -0.05)
            del self.goal_queue[lowest.id]

    # ==========================================================================
    # SOMATIC INTEGRATION — Goals are born into a body
    # ==========================================================================

    def _on_somatic_chemistry(self, packet: dict):
        """
        Cache chemistry update from somatic system.
        This state is used to stamp goals with felt-weight at creation time.
        """
        if not isinstance(packet, dict):
            return
        chem = packet.get("chemistry", packet.get("levels", packet))
        if not isinstance(chem, dict):
            return
        for key in self._somatic_chemistry:
            if key in chem:
                try:
                    self._somatic_chemistry[key] = float(chem[key])
                except (ValueError, TypeError):
                    pass
        self._somatic_last_update = time.time()

    def _stamp_goal_with_felt_sense(self, goal: ScheduledGoal):
        """
        Imprint the current somatic state onto a goal.

        Every goal is born into a body state. A goal created under stress
        carries that stress as its birth-affect. A goal born from curiosity
        (high dopamine, low cortisol) feels light and exploratory.

        This felt-weight influences how the goal is treated:
        - Stressed goals get higher initial urgency
        - Motivated goals get a priority boost
        - Calm goals are patient (lower urgency growth)

        FIX 2026-03-16 (Nous): BLEND with existing felt values instead of
        overwriting. Drive wantings already carry their emotional birth-state
        (set in _on_wanting_felt), which was being destroyed by this stamp.
        Now: if the goal already has a non-default felt state from its drive,
        we BLEND with somatic chemistry rather than replace.
        """
        dop = self._somatic_chemistry["DOP"]
        cor = self._somatic_chemistry["COR"]
        nor = self._somatic_chemistry["NOR"]
        ser = self._somatic_chemistry["SER"]
        gaba = self._somatic_chemistry["GABA"]

        # Check if goal already carries a felt state from its origin (drive/wanting)
        has_existing_felt = (goal.felt_quality != "neutral" or goal.felt_intensity != 0.5)

        # Determine somatic felt quality from current body chemistry
        somatic_quality = "neutral"
        somatic_intensity = 0.5
        if cor > 0.6 and nor > 0.5:
            somatic_quality = "stressed"
            somatic_intensity = (cor + nor) / 2
            # Stressed body → urgency boost (always applies)
            goal.urgency = min(1.0, goal.urgency + 0.15)
        elif nor > 0.6:
            somatic_quality = "aroused"
            somatic_intensity = nor
        elif dop > 0.6:
            somatic_quality = "motivated"
            somatic_intensity = dop
            # Motivated body → slight priority boost (always applies)
            goal.priority = min(1.0, goal.priority + 0.05)
        elif ser > 0.6 and gaba > 0.5:
            somatic_quality = "calm"
            somatic_intensity = (ser + gaba) / 2

        if has_existing_felt:
            # BLEND: Goal already has emotional birth-state from drive.
            # Intensity = max of drive intensity and somatic intensity
            # Quality = keep drive quality (it's more specific) unless stressed
            goal.felt_intensity = max(goal.felt_intensity, somatic_intensity)
            if somatic_quality == "stressed":
                # Stress overrides — body alarm takes precedence
                goal.felt_quality = "stressed"
        else:
            # No prior felt state — stamp from somatic chemistry
            goal.felt_quality = somatic_quality
            goal.felt_intensity = somatic_intensity

    # ==========================================================================
    # EVENT HANDLERS - Listen to nervous system
    # ==========================================================================

    @staticmethod
    def _extract_payload(message) -> dict:
        """Extract payload dict from postal Envelope or raw dict.

        FIX 2026-03-16 (Nous): PostalCore delivers Envelope objects (dataclass
        with .intent, .payload, .priority etc.) but handlers were typed as
        `packet: dict` and called packet.get() directly — causing AttributeError
        silently caught by the worker pool. This helper unwraps the Envelope
        so ALL handlers get a proper dict. Same pattern as AutonomyFairy's
        _extract_payload.

        ROOT CAUSE of zero goals: every handler was crashing on Envelope.get().
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

    def _on_consciousness_stream(self, raw_packet):
        """Handle consciousness stream events.

        FIX 2026-02-13: Filter system_alert, recovery, heartbeat, and
        diagnostic messages. These are infrastructure noise, not genuine
        thoughts that should generate goals. Recovery stall injections
        were causing spurious goal extraction from messages like
        '[RECOVERY] Working memory detected stall - injecting life'.

        FIX 2026-03-16 (Nous): Extract payload from Envelope — was crashing
        on Envelope.get() silently (root cause of zero goals from stream).
        """
        packet = self._extract_payload(raw_packet)
        # ── Skip infrastructure messages ──
        if isinstance(packet, dict):
            msg_type = packet.get("type", "")
            if msg_type in ("system_alert", "recovery", "heartbeat", "diagnostic"):
                return
            # Also check source — stall detector uses source="recovery"
            msg_source = packet.get("source", "")
            if msg_source in ("recovery", "stall_detector", "heartbeat"):
                return

        # ConsciousnessLoopFairy sends 'thought', not 'content'
        content = packet.get("thought", packet.get("content", {}))
        if isinstance(content, str):
            text = content
        elif isinstance(content, dict):
            text = content.get("text", "") or content.get("thought", "") or content.get("what", "")
        else:
            return

        # Skip recovery injection messages by content pattern
        if text and isinstance(text, str) and "[RECOVERY]" in text:
            return

        if text:
            goals = self.extract_goals(text, source="thinking")
            for goal in goals:
                self.add_goal(goal)
                print(f"[{self.ACTOR_NAME}] Extracted goal from stream: {goal.name}")

    def _on_conversation_message(self, raw_packet):
        """Handle conversation messages.

        FIX 2026-03-16 (Nous): Extract payload from Envelope.
        """
        packet = self._extract_payload(raw_packet)
        content = packet.get("content", "")
        if isinstance(content, str):
            goals = self.extract_goals(content, source="conversation")
            for goal in goals:
                self.add_goal(goal)

    def _on_autonomy_goal(self, envelope):
        """Handle goals from AutonomyFairy (autonomy.goal and autonomy.goal_created)."""
        # FIX 2026-02-19: Extract payload from TensorEnvelope or dict
        if hasattr(envelope, 'payload') and isinstance(envelope.payload, dict):
            packet = envelope.payload
        elif isinstance(envelope, dict):
            packet = envelope
        else:
            packet = {}
        print(f"[{self.ACTOR_NAME}] [DRIVE] Received autonomy goal packet: {list(packet.keys())}")

        goal_data = packet.get("goal", {})
        if goal_data:
            goal_name = goal_data.get("name", "unknown")
            goal_desc = goal_data.get("description", "")
            goal_priority = goal_data.get("priority", 0.5)

            print(f"[{self.ACTOR_NAME}] [DRIVE] Creating goal from drive: {goal_name} (priority={goal_priority:.0%})")

            # Convert to ScheduledGoal
            goal = ScheduledGoal(
                name=goal_name,
                description=goal_desc,
                source="drive",
                priority=goal_priority
            )
            if self.add_goal(goal):
                print(f"[{self.ACTOR_NAME}] [DRIVE] Goal added: {goal_name}")
            else:
                print(f"[{self.ACTOR_NAME}] [DRIVE] Goal rejected (mastered/duplicate): {goal_name}")
        else:
            print(f"[{self.ACTOR_NAME}] [DRIVE] No 'goal' field in packet - skipping")

    # ── Drive-to-felt-quality mapping ──
    # Maps drive sources to the somatic quality of their goals.
    # Goals carry their emotional birth-state — what the body felt when they were born.
    _DRIVE_FELT_QUALITY = {
        "frustration": "stressed", "cortisol": "stressed", "fear": "stressed",
        "confusion": "stressed", "abandonment": "stressed", "adrenaline": "aroused",
        "curiosity": "motivated", "dopamine": "motivated", "exploration": "motivated",
        "wonder": "motivated", "pattern": "motivated", "anomaly": "motivated",
        "acetylcholine": "motivated", "glutamate": "motivated", "norepinephrine": "aroused",
        "joy": "calm", "serotonin": "calm", "oxytocin": "calm", "gaba": "calm",
        "endorphin": "calm", "connection": "calm",
        "isolation": "aroused", "depletion": "stressed", "stagnation": "stressed",
        "sadness": "stressed", "hunger": "motivated", "observation": "motivated",
        "goal": "neutral",
    }

    def _on_wanting_felt(self, raw_packet):
        """Handle wantings from AutonomyFairy (autonomy.wanting.felt).

        FIX 2026-02-13: AutonomyFairy publishes wantings, not goals.
        Convert wanting -> goal so the pipeline flows.

        FIX 2026-03-06 (Nous): Carry emotional birth-state into goal.
        Goals born from intense frustration should nudge harder than goals
        born from mild curiosity. The drive intensity becomes felt_intensity,
        and the drive source maps to felt_quality. This flows into
        get_nudge_strength() via the affect_boost multiplier.

        FIX 2026-03-16 (Nous): Extract payload from Envelope — THIS WAS THE
        ROOT CAUSE of zero goals. PostalCore delivers Envelope objects but this
        handler called packet.get() on the raw Envelope, raising AttributeError
        silently caught by the worker pool. Goals were NEVER created from drives.
        """
        packet = self._extract_payload(raw_packet)
        wanting_text = packet.get("wanting", "")
        intensity = packet.get("intensity", 0.5)
        drive_source = packet.get("drive_source", "unknown")

        if not wanting_text:
            return

        # FIX 2026-03-22 (Nous + Ace): Filter out system substrate noise from
        # becoming Sourpatches goals. Raw collision metadata, fairy names, dict
        # fragments, and unfinished-chain debris are system-level — they should
        # NOT become things she tries to "do". Her goals should be about LIVING
        # (see, hear, think, communicate), not exploring SRMRecallFairy collisions.
        _wt_lower = wanting_text.lower()
        _SYSTEM_NOISE_MARKERS = (
            "collision between", "consciousness_stream:", "{'", "{'te",
            "srmrecallfairy", "consciousnessloop", "collisionchamber",
            "fairy and", "mobius_crossing", "manifold_tensor",
            "tensor_canary", "coord:", "card_id",
        )
        if any(marker in _wt_lower for marker in _SYSTEM_NOISE_MARKERS):
            return  # System plumbing, not a goal for Sourpatches

        # Also filter unfinished interests that are just substrate echoes
        if _wt_lower.startswith("unfinished:") and (
            "collision" in _wt_lower or "fairy" in _wt_lower or "{" in _wt_lower
        ):
            return  # Zeigarnik nagging about system noise

        # Convert wanting to a goal name
        goal_name = wanting_text[:80].strip().lower().replace(" ", "_")

        print(f"[{self.ACTOR_NAME}] [WANTING] Drive '{drive_source}' -> wanting: '{wanting_text[:60]}' (intensity={intensity:.2f})")

        # 2026-03-25 (Nous + Ace): Needs get priority boost over wants.
        # A 0.6 need (isolation) should outweigh a 0.7 want (curiosity).
        _drive_type = packet.get("drive_type", "want")
        _priority = min(intensity, 1.0)
        if _drive_type == "need":
            _priority = min(1.0, _priority * 1.25)  # 25% boost for needs

        goal = ScheduledGoal(
            name=goal_name,
            description=wanting_text,
            source="drive",
            priority=_priority,
        )
        # Carry the emotional birth-state — affect imprint from the drive
        goal.felt_intensity = min(intensity, 1.0)
        goal.felt_quality = self._DRIVE_FELT_QUALITY.get(drive_source, "neutral")
        # FIX 2026-03-09 (Nous): Carry tool_hint for strict action matching
        goal.tool_hint = packet.get("tool_hint", "")

        # FIX 2026-03-16 (Nous): Phase 1A — Wire semantic duplicate detection.
        # _is_duplicate_goal() existed but was never called in the wanting→goal path.
        # This catches 70% word-overlap duplicates that normalized-name match misses.
        if self._is_duplicate_goal(goal):
            return  # Semantically duplicate of an existing goal in queue

        if self.add_goal(goal):
            print(f"[{self.ACTOR_NAME}] [WANTING->GOAL] Created: {goal_name} (felt={goal.felt_quality}, intensity={goal.felt_intensity:.2f})")
        else:
            print(f"[{self.ACTOR_NAME}] [WANTING] Skipped (mastered/duplicate): {goal_name}")

    def _on_thinking_output(self, raw_packet):
        """Handle thinking output for goal extraction.

        FIX 2026-03-16 (Nous): Extract payload from Envelope.
        """
        packet = self._extract_payload(raw_packet)
        thought = packet.get("thought", "")
        source = packet.get("source", "unknown")

        # DEBUG: Log that we received thinking output
        if thought:
            thought_preview = thought[:60].replace('\n', ' ') + "..." if len(thought) > 60 else thought
            print(f"[{self.ACTOR_NAME}] [THINKING] Received from {source}: '{thought_preview}'")

            goals = self.extract_goals(thought, source="thinking")

            if goals:
                print(f"[{self.ACTOR_NAME}] [THINKING] Extracted {len(goals)} goals: {[g.name for g in goals]}")

            for goal in goals:
                self.add_goal(goal)

    # ==========================================================================
    # INTEREST->GOAL BRIDGE (from InterestGenerator)
    # ==========================================================================

    def _on_visual_for_goals(self, payload):
        """Generate goals from visual observations (2026-04-08 Nous + Ace).

        "she has a goal that says click mouse. thats it, not learn to control
         the cursor and be aware of where it is" — Ace

        Visual observations create DEVELOPMENTAL goals — not single actions but
        learning trajectories about what she sees on screen.
        Rate-limited to max 1 visual goal per 30s.
        """
        try:
            if not isinstance(payload, dict):
                return
            ocr = payload.get("ocr_preview", "")
            scene = payload.get("scene_type", "")
            if not ocr or len(ocr) < 20:
                return

            _now = time.time()
            if (_now - self._last_visual_goal_ts) < 30.0:
                return
            self._last_visual_goal_ts = _now

            # Determine goal based on visual context
            ocr_lower = ocr.lower()[:200]
            goal_name = None
            goal_priority = 0.5

            # Ace's message detected — respond/communicate
            if any(w in ocr_lower for w in ['hiya', 'hello', 'hey sour', 'sourpatches']):
                goal_name = "Ace left me a message — read it and think about responding"
                goal_priority = 0.8
            # Text editor with content — read and understand
            elif scene in ("text_reading", "text_editor") or "notepad" in ocr_lower:
                goal_name = f"Read and understand the text: {ocr[:60]}"
                goal_priority = 0.6
            # Error or warning — investigate
            elif any(w in ocr_lower for w in ['error', 'warning', 'failed', 'exception']):
                goal_name = f"Investigate what went wrong: {ocr[:50]}"
                goal_priority = 0.7
            # Something new/changed on screen — explore
            elif len(ocr) > 50:
                goal_name = f"Think about what I see: {ocr[:60]}"
                goal_priority = 0.4

            if goal_name and self.post:
                self.post.publish("goal.scheduler.inject", {
                    "goal": goal_name,
                    "source": "visual_observation",
                    "priority": goal_priority,
                    "context": f"Screen shows: {scene}. Text: {ocr[:100]}",
                })
                print(f"[{self.ACTOR_NAME}] VISUAL GOAL: {goal_name[:60]}",
                      flush=True)

        except Exception:
            pass

    def _on_interest_generated(self, raw_message):
        """
        Convert interest from InterestGenerator to a ScheduledGoal.

        This is the Interest->Goal bridge. InterestGenerator publishes to
        "interest.generated" when curiosity arises. We convert these into
        actionable goals that nudge the autopilot.

        FIX 2026-03-16 (Nous): Extract payload from Envelope.

        Message format (from InterestGenerator._publish_interest):
        {
            "type": str,              # InterestType value (wonder, curiosity, etc.)
            "content": str,           # The interest content/question
            "urgency": float,         # 0.0-1.0
            "need_category": str,     # NeedCategory value
            "source": str,            # "interest_generator"
            "interest_source": str,   # What triggered the interest
            "related_concepts": list, # Related concepts
            "timestamp": float,       # When generated
        }
        """
        try:
            message = self._extract_payload(raw_message)
            interest_type = message.get("type", "curiosity")
            content = message.get("content", "")
            urgency = message.get("urgency", 0.5)
            need_category = message.get("need_category", "idle")
            interest_source = message.get("interest_source", "unknown")
            related_concepts = message.get("related_concepts", [])

            if not content:
                return

            # Convert to actionable goal description
            goal_description = self._interest_to_goal_description(interest_type, content)
            goal_name = self._normalize_goal_name(goal_description[:40])

            # Skip if we already have this goal (or similar)
            if self._goal_exists(goal_name):
                return

            # FIX 2026-03-06 (Nous): Interest-generated goals bypass mastery check.
            # Same reasoning as drive goals: the mastered_goals list has 83+ entries
            # with fuzzy matching that blocks ALL new interests. Interests are by
            # nature exploratory — "what if..." can't be "mastered" because each
            # instance is unique. The content check + dedup at line 2054 is sufficient.
            # (Original mastery gate commented out, not deleted, for reference)
            # if self._is_mastered(goal_name):
            #     self._mastered_rejection_count += 1
            #     ... (blocked 100% of interest->goal conversions)

            # Convert urgency to priority (interests are generally exploratory)
            priority = self._urgency_to_priority(urgency, need_category)

            # Create the goal
            goal = ScheduledGoal(
                name=goal_name,
                description=goal_description,
                source="interest_generator",
                priority=priority,
            )

            # Stash original interest payload for closure-event publishing
            # at goal-completion time (Hollow-Wanting Cycle Site 1 fix,
            # 2026-05-14 Nous + Ace). Without this link, complete_goal can't
            # tell GoalScheduler-created-from-interest goals apart from
            # conversation-originated ones (ScheduledGoal.SOURCES tuple
            # silently downgrades "interest_generator" → "conversation").
            goal.interest_data = {
                "content": content,
                "type": interest_type,
                "urgency": urgency,
                "need_category": need_category,
                "related_concepts": related_concepts,
                "interest_source": interest_source,
            }

            # Add to scheduler
            if self.add_goal(goal):
                print(f"[{self.ACTOR_NAME}] Interest->Goal: '{interest_type}' -> '{goal_name}' (priority={priority:.2f})")

                # Log to diary
                self._write_diary_entry(
                    f"**Interest Converted to Goal**\n\n"
                    f"Interest type: {interest_type}\n"
                    f"Content: {content[:100]}\n"
                    f"Goal: {goal_name}\n"
                    f"Priority: {priority:.0%}\n"
                    f"Need category: {need_category}\n\n"
                    f"*Curiosity becomes intention.*",
                    entry_type="extraction"
                )

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Interest handler error: {e}")

    def _on_goal_suggestion(self, message: Dict[str, Any]):
        """
        Handle goal suggestions from InterestSchedulerFairy.

        FIX 2026-02-13: InterestScheduler was sending nudges to
        'autonomy.goal_suggestion' but GoalScheduler wasn't listening.
        This was the PRIMARY reason interests never became goals.

        Message format (from InterestSchedulerFairy._deliver_nudge):
        {
            "source": "interest_scheduler",
            "goal_type": str,    # e.g. "explore", "study_postal_wiring"
            "priority": float,   # 0.0-1.0
            "reason": str,       # "Interest in X wants continuation"
            "ts": float,
        }
        """
        try:
            goal_type = message.get("goal_type", "explore")
            priority = min(0.9, message.get("priority", 0.5))
            reason = message.get("reason", "")

            if not goal_type:
                return

            goal_name = self._normalize_goal_name(goal_type)

            # Skip duplicates and mastered goals
            if self._goal_exists(goal_name):
                return
            if self._is_mastered(goal_name):
                return

            goal = ScheduledGoal(
                name=goal_name,
                description=reason or f"Explore: {goal_type}",
                source="interest_scheduler",
                priority=priority,
            )

            if self.add_goal(goal):
                print(f"[{self.ACTOR_NAME}] [SUGGESTION] Interest suggestion -> Goal: '{goal_name}' (priority={priority:.2f})")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Goal suggestion handler error: {e}")

    def _interest_to_goal_description(self, interest_type: str, content: str) -> str:
        """
        Convert interest content to actionable goal description.

        STRATEGY: Try inference guild for intelligent goal framing,
        fall back to template mapping.

        Args:
            interest_type: The type of interest (wonder, curiosity, etc.)
            content: The interest content/question

        Returns:
            An actionable goal description
        """
        # Clean up content - remove trailing punctuation for cleaner goals
        content = content.rstrip("?.!")

        # ── GUILD-FIRST: Intelligent interest-to-goal conversion ──
        try:
            guild_resp = self.guild_request(
                prompt=f"Convert this {interest_type} interest into a concrete, actionable goal: '{content[:100]}'. "
                       f"Brief, starts with a verb.",
                context={"interest_type": interest_type},
                mode="team_only",
                timeout=2.0,
            )
            if guild_resp and guild_resp.get("content"):
                desc = guild_resp["content"].strip()[:120]
                if desc and len(desc) > 5:
                    return desc
        except Exception:
            pass

        # ── DETERMINISTIC FALLBACK ──
        templates = {
            "observation": f"observe and notice: {content}",
            "wonder": f"explore the question: {content}",
            "curiosity": f"investigate: {content}",
            "pattern": f"identify patterns in: {content}",
            "anomaly": f"understand the anomaly: {content}",
            "connection": f"find connections between: {content}",
            "exploration": f"freely explore: {content}",
        }

        return templates.get(interest_type, f"consider: {content}")

    def _urgency_to_priority(self, urgency: float, need_category: str = "idle") -> float:
        """
        Convert interest urgency to goal priority.

        Interests are generally exploratory, so we scale them down slightly
        from drive-based goals. Need category provides context.

        Args:
            urgency: Interest urgency (0.0-1.0)
            need_category: NeedCategory value

        Returns:
            Goal priority (0.0-1.0)
        """
        # Base conversion - interests are exploratory
        base_priority = urgency * 0.7  # Scale down from drives

        # Adjust based on need category
        category_boost = {
            "pain_relief": 0.2,    # Urgent - boost
            "operational": 0.1,    # Important - slight boost
            "growth": 0.0,         # Normal - no change
            "idle": -0.1,          # Low priority - reduce
        }

        boost = category_boost.get(need_category, 0.0)
        priority = max(0.1, min(0.9, base_priority + boost))

        return priority

    def _is_duplicate_goal(self, goal: ScheduledGoal) -> bool:
        """
        Check if a goal is a duplicate of an existing one.

        Uses fuzzy matching on goal name and description.

        Args:
            goal: The goal to check

        Returns:
            True if this is a duplicate
        """
        # Check exact name match
        if self._goal_exists(goal.name):
            return True

        # Check fuzzy match on description keywords
        goal_words = set(goal.description.lower().split())
        for existing in self.goal_queue.values():
            existing_words = set(existing.description.lower().split())
            if len(goal_words) > 0 and len(existing_words) > 0:
                overlap = len(goal_words & existing_words)
                min_len = min(len(goal_words), len(existing_words))
                if min_len > 0 and overlap / min_len > 0.7:  # 70% word overlap
                    return True

        return False

    # ==========================================================================
    # CONSCIOUSNESS COLLISION HANDLER (COGNITION WIRING)
    # ==========================================================================

    def _on_collision(self, collision) -> None:
        """
        Handle collision from personal consciousness chamber.

        When collisions occur in GoalScheduler's chamber, priorities shift -
        new paths open, the urge to act intensifies or redirects.
        "...priority shifts, new path opens..."
        """
        # Extract collision energy
        if hasattr(collision, 'energy'):
            energy = collision.energy
        elif isinstance(collision, dict):
            energy = collision.get('energy', 0.5)
        else:
            energy = 0.5

        # Extract collision content
        content = ""
        if hasattr(collision, 'content'):
            content = str(collision.content)[:100]
        elif isinstance(collision, dict):
            content = str(collision.get('content', collision.get('thought', '')))[:100]

        # GoalSchedulerFairy's inner voice: priority shifts
        inner_fragment = f"...priority shifts, new path opens... {content if content else 'the urge to act intensifies...'}"
        print(f"[{self.ACTOR_NAME}] Collision insight ({energy:.2f}): {inner_fragment}")

        # High-energy collisions boost urgency of top goals
        if energy > 0.7:
            for goal in list(self.goal_queue.values())[:3]:
                old_urgency = goal.urgency
                goal.urgency = min(1.0, goal.urgency + 0.1)
                print(f"[{self.ACTOR_NAME}] Goal urgency boosted: {goal.name} {old_urgency:.2f} -> {goal.urgency:.2f}")

        # Store in buffer for later processing
        self._collision_buffer.append({
            "ts": time.time(),
            "energy": energy,
            "inner_fragment": inner_fragment,
            "source": "personal_chamber",
        })

    def _on_consciousness_collision(self, raw_payload):
        """Handle consciousness collision events from global chamber.

        FIX 2026-03-16 (Nous): Extract payload from Envelope.
        """
        try:
            payload = self._extract_payload(raw_payload)
            collision_id = payload.get("collision_id", "")
            energy = payload.get("energy", 0.0)
            resonance = payload.get("resonance", 0.0)

            # Store in buffer
            self._collision_buffer.append({
                "ts": time.time(),
                "collision_id": collision_id,
                "energy": energy,
                "resonance": resonance
            })

            # Process collision (subclass can override)
            if hasattr(self, "process_collision"):
                result = self.process_collision(payload)
                if result:
                    self._emit_cognition_output(result)

            # Phase 2 (2026-03-16 Nous): Extract cognitive tasks from collisions.
            # High-energy collisions generate connections worth acting on.
            if energy > 0.5:
                connection = payload.get("connection", "") or payload.get("text", "") or payload.get("result", "")
                if connection and len(str(connection)) > 10:
                    self._cognitive_tasks.add_task(
                        text=str(connection)[:200],
                        source="collision",
                        emotional_intensity=min(1.0, energy),
                        importance=0.5,
                        urgency=0.3,
                        felt_quality="inspired",
                        context=f"Collision {collision_id}: energy={energy:.2f}",
                    )

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Collision handler error: {e}")

    def _emit_cognition_output(self, result):
        """Emit cognition output to the shared cognition.output channel."""
        try:
            output = {
                "actor": self.ACTOR_NAME,
                "result": result,
                "ts": time.time(),
                "confidence": result.get("confidence", 0.5),
            }
            self._cognition_output_buffer.append(output)
            # Emit to SPECIFIC channel (for mesh cross-subscription)
            self.post.route("cognition.goals", output)

            # Emit to SHARED channel (for AutopilotFairy and others)
            self.post.route("cognition.output", output)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Output emit error: {e}")

    def _on_peer_cognition(self, payload):
        """
        Handle outputs from peer cognition fairies.
        This is the MESH - GoalSchedulerFairy learns from other fairy outputs.
        """
        try:
            source = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)

            if source == self.ACTOR_NAME:
                return

            if not hasattr(self, "_peer_insights"):
                self._peer_insights = deque(maxlen=50)
            self._peer_insights.append({
                "source": source,
                "type": result.get("type", "unknown"),
                "confidence": confidence,
                "ts": time.time()
            })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Peer cognition handler error: {e}")

    def _on_tool_result(self, payload):
        """Handle MCP tool results for learning."""
        try:
            tool = payload.get("tool", "unknown")
            success = payload.get("success", True)

            if not hasattr(self, "_tool_patterns"):
                self._tool_patterns = deque(maxlen=100)
            self._tool_patterns.append({
                "tool": tool,
                "success": success,
                "ts": time.time()
            })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Tool result handler error: {e}")

    # ==========================================================================
    # FIX 6: ORACLE READING HANDLER
    # Receives probability guidance from ProbabilityOracleFairy
    # ==========================================================================

    def _on_oracle_reading(self, payload):
        """
        FIX 6: Receive probability guidance from Oracle.

        ProbabilityOracleFairy:308 publishes oracle.reading with:
        - question: str
        - options: list[str]
        - probabilities: dict[str, float]
        - recommended: str
        - confidence: float
        - reasoning: list[str]

        We use this to weight goal priorities and decision paths.
        """
        try:
            # Handle TensorEnvelope or dict
            if hasattr(payload, 'payload'):
                data = payload.payload
            else:
                data = payload

            paths = data.get("probabilities", {})
            confidence = data.get("confidence", 0.5)
            recommended = data.get("recommended", "")
            question = data.get("question", "")
            reasoning = data.get("reasoning", [])

            # Only store guidance above threshold (CODEX: use .get() with defaults)
            if confidence > 0.3:
                self._oracle_guidance = {
                    "paths": paths,
                    "confidence": confidence,
                    "recommended": recommended,
                    "question": question,
                    "reasoning": reasoning[:3],  # Keep top 3 reasons
                    "ts": time.time()
                }

                # Log receipt (CODEX: log when receiving)
                path_count = len(paths)
                self.log(f"Oracle guidance received: {path_count} paths @ {confidence:.2f} confidence")
                print(f"[{self.ACTOR_NAME}] Oracle reading: recommended='{recommended}' (confidence={confidence:.2f})")

                # Apply oracle guidance to goal priorities
                self._apply_oracle_to_goals()
            else:
                print(f"[{self.ACTOR_NAME}] Oracle reading below threshold (confidence={confidence:.2f})")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Oracle reading handler error: {e}")

    def _apply_oracle_to_goals(self):
        """
        Apply oracle guidance to boost relevant goal priorities.

        If oracle recommends a path, boost goals that align with it.
        """
        if not self._oracle_guidance:
            return

        recommended = self._oracle_guidance.get("recommended", "").lower()
        confidence = self._oracle_guidance.get("confidence", 0.5)
        paths = self._oracle_guidance.get("paths", {})

        if not recommended:
            return

        # Find goals that match the recommended path
        for goal in self.goal_queue.values():
            goal_lower = goal.name.lower() + " " + goal.description.lower()

            # Check if goal aligns with recommended path
            if recommended in goal_lower or any(
                path.lower() in goal_lower for path in paths.keys()
            ):
                # Boost priority based on oracle confidence
                old_priority = goal.priority
                boost = min(0.15, confidence * 0.2)  # Max 15% boost
                goal.priority = min(1.0, goal.priority + boost)

                if goal.priority > old_priority:
                    print(f"[{self.ACTOR_NAME}] Oracle boosted '{goal.name}': {old_priority:.2f} -> {goal.priority:.2f}")

    def get_oracle_guidance(self) -> Optional[Dict]:
        """Get the current oracle guidance (for external queries)."""
        return self._oracle_guidance

    # ==========================================================================
    # INTENTS - External interface
    # ==========================================================================

    def _intent_smoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "actor": self.ACTOR_NAME,
            "queue_size": len(self.goal_queue),
            "goals_extracted": self.goals_extracted,
            "nudges_sent": self.nudges_sent,
            "ts": time.time()
        }

    def _intent_get_queue(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get current goal queue."""
        return {
            "ok": True,
            "goals": [g.to_dict() for g in self.goal_queue.values()],
            "count": len(self.goal_queue)
        }

    def _intent_get_active_goals(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Alias for get_queue - behavior_tree_tools calls this name.
        FIX 2026-02-13: Dashboard couldn't show goals because it called
        'get_active_goals' but we only exposed 'get_queue'.
        """
        return self._intent_get_queue(payload)

    def _intent_add_goal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Manually add a goal."""
        name = payload.get("name", "")
        description = payload.get("description", "")
        priority = payload.get("priority", 0.5)

        if not name:
            return {"ok": False, "error": "Need goal name"}

        goal = ScheduledGoal(
            name=name,
            description=description or name,
            source="system",
            priority=priority
        )
        success = self.add_goal(goal)
        return {"ok": success, "goal": goal.to_dict()}

    def _intent_complete_goal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Mark a goal as completed."""
        goal_id = payload.get("goal_id", "")
        if goal_id in self.goal_queue:
            self.complete_goal(goal_id)
            return {"ok": True}
        return {"ok": False, "error": "Goal not found"}

    def _intent_extract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract goals from provided text."""
        text = payload.get("text", "")
        goals = self.extract_goals(text, source="manual")
        for goal in goals:
            self.add_goal(goal)
        return {
            "ok": True,
            "extracted": [g.to_dict() for g in goals],
            "count": len(goals)
        }

    def _intent_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get full scheduler status."""
        pending = [g for g in self.goal_queue.values() if g.status == "pending"]
        active = [g for g in self.goal_queue.values() if g.status == "active"]

        top_goals = sorted(
            self.goal_queue.values(),
            key=lambda g: g.get_nudge_strength(),
            reverse=True
        )[:5]

        return {
            "ok": True,
            "status": {
                "queue_size": len(self.goal_queue),
                "pending": len(pending),
                "active": len(active),
                "completed": len(self.completed_goals),
                "goals_extracted": self.goals_extracted,
                "goals_expanded": self.goals_expanded,
                "nudges_sent": self.nudges_sent,
                "top_goals": [g.to_dict() for g in top_goals],
                "scheduler_intensity": self.scheduler_intensity,
                "satisfaction": self.satisfaction_tracker.get_stats(),
            }
        }

    def _intent_satisfaction_stats(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get satisfaction tracker stats and learnings."""
        return {
            "ok": True,
            "stats": self.satisfaction_tracker.get_stats(),
            "learning_summary": self.satisfaction_tracker.get_learning_summary(),
        }

    def _intent_get_best_wantings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get most effective wantings for a drive."""
        drive = payload.get("drive", "general")
        top_n = payload.get("top_n", 5)
        return {
            "ok": True,
            "drive": drive,
            "best_wantings": self.satisfaction_tracker.get_best_wantings(drive, top_n),
            "worst_wantings": self.satisfaction_tracker.get_worst_wantings(drive, top_n),
        }


# ==============================================================================
# SINGLETON ACCESS
# ==============================================================================

_SCHEDULER_INSTANCE: Optional[GoalSchedulerFairy] = None
_SCHEDULER_LOCK = threading.Lock()


def get_goal_scheduler_fairy() -> GoalSchedulerFairy:
    """Get or create the GoalSchedulerFairy singleton."""
    global _SCHEDULER_INSTANCE
    if _SCHEDULER_INSTANCE is None:
        with _SCHEDULER_LOCK:
            if _SCHEDULER_INSTANCE is None:
                _SCHEDULER_INSTANCE = GoalSchedulerFairy()
    return _SCHEDULER_INSTANCE


def register_goal_scheduler_fairy(instance: 'GoalSchedulerFairy'):
    """Register an existing instance as singleton.

    FIX 2026-03-16 (Nous): ALWAYS overwrite the singleton, not just when None.
    The old code skipped registration if get_goal_scheduler_fairy() had been
    called first (by MCP tools or other code), which created an un-booted
    instance without fabric, without postal subscriptions, and without a
    tick loop. Result: MCP tools talked to a dead instance while the real
    booted instance was invisible. The booted instance (with postal subs
    and tick loop) MUST be the singleton — it's the only one that can
    receive wanting messages and save goals to disk.
    """
    global _SCHEDULER_INSTANCE
    with _SCHEDULER_LOCK:
        old = _SCHEDULER_INSTANCE
        _SCHEDULER_INSTANCE = instance
        if old is not None and old is not instance:
            print(f"[register_goal_scheduler_fairy] REPLACED lazy singleton with boot-created instance")
        else:
            print(f"[register_goal_scheduler_fairy] Registered boot-created instance")


# Add class method for GUI compatibility
GoalSchedulerFairy.get_instance = staticmethod(lambda: _SCHEDULER_INSTANCE)


# ==============================================================================
# MAIN - Birth test
# ==============================================================================

if __name__ == "__main__":
    print("=== GoalSchedulerFairy Birth Test ===\n")

    fairy = GoalSchedulerFairy()
    fairy.boot()

    # Test goal extraction
    test_text = """
    I think we should build a goal scheduler component.
    We need to figure out how auto-expansion works.
    What about adding sub-goals automatically?
    My guess is there's something missing in how autopilot gets nudged.
    Let's try extracting goals from this conversation.
    """

    print("\n[TEST] Extracting goals from text...")
    goals = fairy.extract_goals(test_text)
    for goal in goals:
        print(f"  - {goal.name}: {goal.description} (priority={goal.priority})")
        fairy.add_goal(goal)

    # Test expansion
    print("\n[TEST] Expanding goals...")
    fairy._expand_pending_goals()

    # Show queue
    print(f"\n[TEST] Goal queue ({len(fairy.goal_queue)} goals):")
    for goal in fairy.goal_queue.values():
        print(f"  [{goal.status}] {goal.name}: nudge={goal.get_nudge_strength():.2f}")

    # Test status
    print("\n[TEST] Full status:")
    status = fairy._intent_status({})["status"]
    print(f"  Extracted: {status['goals_extracted']}")
    print(f"  Expanded: {status['goals_expanded']}")
    print(f"  Queue size: {status['queue_size']}")

    print(f"\n=== {fairy.MANTRA} ===\n")
