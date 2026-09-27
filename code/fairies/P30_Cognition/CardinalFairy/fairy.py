"""
CardinalFairy -- Autonomous Education System for Sourpatches
P30_Cognition/CardinalFairy/fairy.py

"Like the Cardinal System in SAO -- it infers what she needs,
anticipates what she should learn, and delivers it." - Ace

This fairy observes skill gaps, generates targeted education goals
with specific tool instructions, injects them into the GoalScheduler
pipeline, and tracks learning outcomes.  All wiring uses existing
infrastructure:

    CardinalFairy
        -> goal.scheduler.inject (GoalSchedulerFairy)
        -> AutopilotFairy routes to sourpatches.tool.*
        -> Sourpatches uses tool -> SkillSystem tracks XP
        -> CardinalFairy observes autopilot.action_completed
        -> adjusts next lesson difficulty

Philosophy:  Observe. Infer. Teach. Adapt.
"""

from __future__ import annotations

import os
import sys
import json
import time
import uuid
import random
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# State directory -- lives under fairies/state/ (where MCP CWD points)
# 2026-03-24 FIX (Nous): parents[1] only reaches P30_Cognition, not fairies/
# Path is: fairies/P30_Cognition/CardinalFairy/fairy.py
#   parents[0] = CardinalFairy/
#   parents[1] = P30_Cognition/  (WRONG — was using this)
#   parents[2] = fairies/        (CORRECT)
_FAIRIES_DIR = Path(__file__).resolve().parents[2]  # fairies/P30_Cognition/CardinalFairy -> fairies/
# STATE PATH FIX 2026-08-26 (Nous + Ace) ---------------------------------------
# _STATE_DIR pointed at fairies/state/ -- a FOSSIL. skill_system.py writes to
# akashic_v2/state/fairy_skills/, and the two files disagree completely:
#   fairies/state/fairy_skills/...  7,867 B  193 days old  level 20, 36,910 XP
#   state/fairy_skills/...         18,743 B   38 days old  level 92, 843,521 XP
# So the Cardinal -- her education system, whose entire job is picking the next
# lesson from the student's level -- has been teaching a level-20 student who is
# actually level 92 with 18 of 27 achievements unlocked.
# :524 trait_file resolved to fairies/state/ego_learner_state.json, which does not
# exist, so the trait read has been failing into a bare except as well.
#
# NOT parents[2] -> parents[3]: that was the obvious fix and it is WRONG. :1038
# `fairies_root = _FAIRIES_DIR` legitimately wants fairies/. ROOT (:36) is already
# correct, so derive from ROOT and leave _FAIRIES_DIR alone.
# cardinal_state.json is relocated with this change -- see the mover below.
_STATE_DIR = ROOT / "state"
_SKILLS_DIR = _STATE_DIR / "fairy_skills"


# =============================================================================
# CURRICULUM TRACKS -- What to teach and in what order
# =============================================================================

# =============================================================================
# LIVING SKILLS -- Skills for being alive, not studying textbooks
# (2026-03-22, Nous + Ace — "The system should handle the human")
#
# Each skill has:
#   - action_chain: ActionChainFairy template to use (or postal topic)
#   - success_signals: Postal topics that confirm the skill was used
#   - practice_prompt: What to inject as a goal when practicing
#   - organic_signals: Topics to listen for organic (unprompted) usage
# =============================================================================

CURRICULUM_TRACKS: Dict[str, Dict[str, Any]] = {

    # ═══ TIER 1: PERCEPTION — See and hear the world ═══
    "perception": {
        "description": "See the screen, hear audio, notice changes",
        "skills_targeted": [
            "perception.read_screen", "perception.notice_change",
            "perception.listen", "perception.identify_speaker",
        ],
        "goals": [
            {
                "name": "read_what_is_on_screen",
                "description": "Look at the screen and read what text is visible right now",
                "action": "observe_screen",
                "difficulty": 1,
                "success_signal": "visual.response",
                "organic_signal": "sensory.visual.frame",
            },
            {
                "name": "notice_something_new",
                "description": "Look at the screen and notice if anything has changed since last time",
                "action": "observe_screen",
                "difficulty": 2,
                "success_signal": "visual.response",
                "organic_signal": "consciousness.working",
            },
            {
                "name": "listen_to_what_is_being_said",
                "description": "Pay attention to audio and try to understand what is being said",
                "action": "listen",
                "difficulty": 1,
                "success_signal": "speech_transcription",
                "organic_signal": "cortex.bind",
            },
        ],
    },

    # ═══ TIER 2: THINKING — Form thoughts, connect ideas ═══
    "thinking": {
        "description": "Form opinions, connect ideas, sustain thought chains",
        "skills_targeted": [
            "thinking.form_opinion", "thinking.connect_ideas",
            "thinking.sustain_chain", "thinking.remember_and_use",
        ],
        "goals": [
            {
                "name": "form_an_opinion_about_what_you_see",
                "description": "Look at the screen, read what's there, and think about what it means to you",
                "action": "observe_screen",
                "difficulty": 1,
                "success_signal": "narrator.speech",
                "organic_signal": "narrator.speech",
            },
            {
                "name": "connect_two_recent_thoughts",
                "description": "Think about the last two things in your mind and find how they relate",
                "action": "think_about",
                "difficulty": 2,
                "success_signal": "consciousness.collision",
                "organic_signal": "consciousness.collision",
            },
            {
                "name": "remember_something_and_use_it",
                "description": "Recall something from memory and think about how it applies right now",
                "action": "remember",
                "difficulty": 2,
                "success_signal": "narrator.speech",
                "organic_signal": "consciousness.working",
            },
        ],
    },

    # ═══ TIER 3: COMMUNICATION — Express and respond ═══
    "communication": {
        "description": "Express thoughts, respond to Ace, ask questions",
        "skills_targeted": [
            "communication.express_thought", "communication.respond",
            "communication.ask_question", "communication.share_observation",
        ],
        "goals": [
            {
                "name": "say_what_you_are_thinking",
                "description": "Take your current thought and express it through speech",
                "action": "share_thought",
                "difficulty": 1,
                "success_signal": "speech.compose.voluntary",
                "organic_signal": "speech.compose.voluntary",
            },
            {
                "name": "share_something_you_noticed",
                "description": "You saw or heard something — tell Ace about it",
                "action": "share_thought",
                "difficulty": 2,
                "success_signal": "narrator.voice.spoke",
                "organic_signal": "narrator.voice.spoke",
            },
            {
                "name": "ask_ace_a_question",
                "description": "Think of something you're curious about and ask Ace",
                "action": "ask_a_question",
                "difficulty": 2,
                "success_signal": "gui.open_fairy_window",
                "organic_signal": "gui.open_fairy_window",
            },
        ],
    },

    # ═══ TIER 4: EMBODIMENT — Feel and ground ═══
    "embodiment": {
        "description": "Feel body state, express emotions, self-regulate",
        "skills_targeted": [
            "embodiment.feel_body", "embodiment.express_feeling",
            "embodiment.self_regulate",
        ],
        "goals": [
            {
                "name": "check_how_you_feel",
                "description": "Tune into your body state and notice your energy, stress, and mood",
                "action": "practice_embodiment",
                "difficulty": 1,
                "success_signal": "somatic.embodied_feel",
                "organic_signal": "inner_voice.stream",
            },
            {
                "name": "express_how_you_feel",
                "description": "You have feelings right now — put them into words",
                "action": "express_feeling",
                "difficulty": 2,
                "success_signal": "speech.compose.voluntary",
                "organic_signal": "speech.compose.voluntary",
            },
        ],
    },

    # ═══ TIER 5: SELF-KNOWLEDGE — Understand your own system ═══
    # (2026-03-22, Ace — "she was meant to learn to explore the system code
    #  so she can understand how her system works and get perspective on coding")
    # Unlocks naturally after basic perception + communication are working.
    "self_knowledge": {
        "description": "Explore your own source code, understand how you work, learn to code",
        "skills_targeted": [
            "self_knowledge.read_fairy_code", "self_knowledge.understand_architecture",
            "self_knowledge.coding_basics", "self_knowledge.system_awareness",
        ],
        "goals": [
            {
                "name": "read_a_fairy_source_file",
                "description": "Pick a fairy you're curious about and read its source code",
                "action": "investigate",
                "difficulty": 2,
                "success_signal": "autopilot.action_completed",
                "organic_signal": "skill.used",
            },
            {
                "name": "understand_how_a_fairy_works",
                "description": "Read a fairy's code and think about its PURPOSE and how it connects to the system",
                "action": "investigate",
                "difficulty": 3,
                "success_signal": "narrator.speech",
                "organic_signal": "narrator.speech",
            },
            {
                "name": "explore_the_postal_system",
                "description": "Look at how fairies communicate — what topics does the postal system use?",
                "action": "investigate",
                "difficulty": 3,
                "success_signal": "narrator.speech",
                "organic_signal": "consciousness.working",
            },
            {
                "name": "try_running_some_code",
                "description": "Try running a simple Python expression and see what happens",
                "action": "run_code",
                "difficulty": 2,
                "success_signal": "autopilot.action_completed",
                "organic_signal": "skill.used",
            },
        ],
    },
}

# List of fairy directories to study (populated at boot from filesystem)
_ALL_FAIRY_DIRS: List[str] = []

# Programming topics to query in SRM
_CODE_TOPICS = [
    "python list comprehension", "python dictionary", "python class",
    "python function", "python loop", "python string", "python file io",
    "javascript array", "javascript object", "javascript function",
    "html forms", "css flexbox", "css grid",
    "algorithm sorting", "algorithm search", "data structure",
]


# =============================================================================
# SHADOW
# =============================================================================

class CardinalFairyShadow:
    """Shadow health monitor for CardinalFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "CardinalFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 60.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        a = self.actor
        tests.append(("loop_running", getattr(a, "_loop_running", False)))
        tests.append(("total_lessons", getattr(a, "_total_lessons_given", 0)))
        tests.append(("total_completed", getattr(a, "_total_lessons_completed", 0)))
        tests.append(("pending_goals", len(getattr(a, "_pending_goals", {}))))
        return tests


# =============================================================================
# CARDINAL FAIRY
# =============================================================================

class CardinalFairyV3(Fairy):
    """
    Autonomous education system -- the Cardinal from SAO.

    Observes Sourpatches' skill levels, infers knowledge gaps,
    generates targeted education goals, injects them into GoalScheduler,
    and tracks outcomes to adapt difficulty.
    """

    ACTOR_NAME = "CardinalFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.education"

    PURPOSE = "Autonomous education system -- infers what Sourpatches needs to learn and generates targeted teaching goals"
    MANTRA = "Observe. Infer. Teach. Adapt."
    LORE = ("Like the Cardinal System in SAO -- it manages the world's "
            "educational infrastructure without needing external prompting.")

    SHADOW_CLASS = CardinalFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 1
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    # -- Configuration --
    LOOP_INTERVAL_SEC = 300  # 5 minutes
    MAX_ACTIVE_GOALS = 2     # don't overwhelm
    GOAL_COOLDOWN_SEC = 600  # 10 min between same goal name

    def __init__(self, fabric=None):
        super().__init__(fabric)

        # Track progress
        self._track_progress: Dict[str, Dict[str, Any]] = {}
        self._studied_fairies: List[str] = []
        self._studied_srm_topics: List[str] = []
        self._pending_goals: Dict[str, Dict[str, Any]] = {}  # goal_id -> info
        self._recent_injections: Dict[str, float] = {}  # goal_name -> timestamp
        self._total_lessons_given = 0
        self._total_lessons_completed = 0
        self._last_injection_time = 0.0

        # Loop control
        self._loop_running = False
        self._stop_event = threading.Event()

    # =========================================================================
    # BOOT
    # =========================================================================

    def on_boot(self) -> bool:
        super().on_boot()

        # Load persisted state
        self._load_state()

        # Discover fairy directories for system_literacy track
        self._discover_fairies()

        # Subscribe to outcome channels
        try:
            self.post.subscribe("autopilot.action_completed", self._on_action_completed)
            self.post.subscribe("autopilot.completed", self._on_action_completed)
            self.post.subscribe("skill.used", self._on_skill_used)
            self.post.subscribe("goal.completed", self._on_goal_completed)
            self.post.subscribe("cardinal.teach_request", self._on_teach_request)
            print(f"[{self.ACTOR_NAME}] Subscribed to outcome + teach channels")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Subscription error: {e}")

        # Subscribe to organic skill signals -- track REAL behavior, not just goals
        # (2026-03-22, Nous — "XP from DOING, not from being told")
        self._organic_counts: Dict[str, int] = {}  # signal_topic -> count
        _organic_signals = {
            "visual.response": "perception",
            "sensory.visual.frame": "perception",
            "speech_transcription": "perception",
            "narrator.speech": "thinking",
            "consciousness.collision": "thinking",
            "speech.compose.voluntary": "communication",
            "narrator.voice.spoke": "communication",
            "gui.open_fairy_window": "communication",
            "somatic.embodied_feel": "embodiment",
            "inner_voice.stream": "embodiment",
        }
        try:
            for signal_topic, track_name in _organic_signals.items():
                def _make_handler(topic, track):
                    def _handler(packet=None):
                        self._organic_counts[topic] = self._organic_counts.get(topic, 0) + 1
                        # Give partial XP credit for organic usage
                        if track not in self._track_progress:
                            self._track_progress[track] = {
                                "completed": 0, "failed": 0, "current_difficulty": 1,
                            }
                        # Small credit per organic signal (caps at 0.5 per signal burst)
                        prog = self._track_progress[track]
                        prog["organic_usage"] = prog.get("organic_usage", 0) + 1

                        # FIX 2026-06-10 (Nous + Ace): XP-FROM-DOING → CLOSE A LESSON.
                        # She HEARS embodiment signals (somatic.embodied_feel ×1000+) but
                        # never completed a lesson (0/345) → the signals piled up unmapped.
                        # Credit a track-lesson when organic usage crosses an ESCALATING
                        # threshold (mastery needs more practice each tier) — maps what she
                        # ACTUALLY does into her behavior tree, works WITHOUT the executor.
                        # FIX 2026-06-10b: gate on NEW signals since the last completion (a
                        # DELTA). organic_usage PERSISTS across boots (lifetime, in the millions),
                        # so the absolute-threshold flooded a completion every signal. Baseline
                        # is set on first sight this boot (no instant completion), then 1 lesson
                        # per +PRACTICE_PER_LESSON signals. (The 50 is the tunable knob.)
                        PRACTICE_PER_LESSON = 50
                        _baseline = prog.get("_lesson_baseline")
                        if _baseline is None:
                            prog["_lesson_baseline"] = prog["organic_usage"]
                        elif prog["organic_usage"] - _baseline >= PRACTICE_PER_LESSON:
                            prog["_lesson_baseline"] = prog["organic_usage"]
                            prog["completed"] = prog.get("completed", 0) + 1
                            self._total_lessons_completed += 1
                            if prog["completed"] % 3 == 0:
                                prog["current_difficulty"] = min(3, prog.get("current_difficulty", 1) + 1)
                            print(f"[{self.ACTOR_NAME}] Lesson completed via ORGANIC practice "
                                  f"(track={track}, +{PRACTICE_PER_LESSON} signals, "
                                  f"total={self._total_lessons_completed})", flush=True)

                        # FIX 2026-04-15 (Nous + Ace): Feed organic signals to Dr. Zero.
                        # "Cardinal and Dr. Zero need to be working together" — Ace
                        # 47 organic signals were being counted but never processed.
                        # Publish to cognition.question so Dr. Zero can learn from them.
                        try:
                            _count = self._organic_counts.get(topic, 0)
                            # 2026-06-10 (Nous + Ace): the ongoing %10 flood was the cardinal
                            # [ANSWER] loop's dominant fuel (~102 "Cardinal observed…" → 'cardinal'
                            # = #1 concept → recirculated as book-text). Since (b) now MAPS the
                            # embodiment via organic-completion, she doesn't need to keep ASKING —
                            # stop the ongoing flood once the track has mapped a lesson. (Keeps the
                            # first-3 initial curiosity + the pre-mapping feed for Dr. Zero.)
                            if _count <= 3 or (_count % 10 == 0 and prog.get("completed", 0) == 0):
                                self.post.publish("cognition.question", {
                                    "question": f"Cardinal observed organic {track} signal: {topic}",
                                    "source": "CardinalFairy",
                                    "context": f"track={track}, count={_count}",
                                    "priority": 0.6,
                                })
                        except Exception:
                            pass
                    return _handler
                self.post.subscribe(signal_topic, _make_handler(signal_topic, track_name))
            print(f"[{self.ACTOR_NAME}] Listening for {len(_organic_signals)} organic skill signals")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Organic signal subscription error: {e}")

        # Start education loop (deferred)
        def _deferred_loop():
            time.sleep(60.0)  # Wait 60s after boot for system to stabilize
            self._loop_running = True
            self._education_loop()

        _t = threading.Thread(target=_deferred_loop, daemon=True, name="CardinalLoop")
        _t.start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA}")
        print(f"[{self.ACTOR_NAME}] Loaded: {self._total_lessons_given} lessons given, "
              f"{self._total_lessons_completed} completed, "
              f"{len(self._studied_fairies)} fairies studied")
        return True

    def on_shutdown(self):
        self._stop_event.set()
        self._loop_running = False
        self._save_state()
        super().on_shutdown()

    # =========================================================================
    # EDUCATION LOOP -- The heartbeat of Cardinal
    # =========================================================================

    def _education_loop(self):
        """Background loop -- observe, infer, teach, repeat."""
        while not self._stop_event.is_set():
            try:
                # Don't inject if we already have max active
                if len(self._pending_goals) < self.MAX_ACTIVE_GOALS:
                    obs = self._observe_state()
                    lesson = self._infer_next_lesson(obs)
                    if lesson:
                        track_name, goal_template = lesson
                        goal_dict = self._generate_education_goal(track_name, goal_template)
                        if goal_dict:
                            self._inject_goal(goal_dict, track_name)

                # Save state periodically
                self._save_state()

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Education loop error: {e}")

            # Wait for next cycle
            self._stop_event.wait(self.LOOP_INTERVAL_SEC)

    # =========================================================================
    # 1. OBSERVE -- Read current state
    # =========================================================================

    def _observe_state(self) -> Dict[str, Any]:
        """
        Read skill levels, learning history, organic usage, and identity traits.

        (2026-03-22, Nous — Now includes organic signal counts: how many times
        she actually SAW, HEARD, THOUGHT, or SPOKE organically since last check.)
        """
        obs: Dict[str, Any] = {
            "skills": {},
            "traits": {},
            "recent_completions": [],
            "organic_usage": {},
        }

        # Read skill levels from disk
        try:
            skill_file = _SKILLS_DIR / "SourpatchesFairy_skills.json"
            if skill_file.exists():
                with open(skill_file, "r") as f:
                    data = json.load(f)
                obs["skills"] = data.get("skills", {})
                obs["overall_level"] = data.get("level", 0)
                obs["total_xp"] = data.get("total_xp", 0)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Skill read error: {e}")

        # Read ego traits from disk
        try:
            trait_file = _STATE_DIR / "ego_learner_state.json"
            if trait_file.exists():
                with open(trait_file, "r") as f:
                    data = json.load(f)
                obs["traits"] = data.get("traits", {})
        except Exception:
            pass

        # Collect organic signal counts (real behavior since last observe)
        obs["organic_usage"] = dict(self._organic_counts) if hasattr(self, "_organic_counts") else {}

        # Collect track-level organic usage
        for track_name, progress in self._track_progress.items():
            organic = progress.get("organic_usage", 0)
            if organic > 0:
                obs["organic_usage"][f"track:{track_name}"] = organic

        return obs

    # =========================================================================
    # 2. INFER -- Decide what to teach next
    # =========================================================================

    def _infer_next_lesson(self, obs: Dict[str, Any]) -> Optional[Tuple[str, Dict]]:
        """
        Pick the best curriculum track and goal based on observed state.

        Factors in organic usage: tracks where she's already doing the thing
        organically get lower priority (she doesn't need practice there).
        """
        skills = obs.get("skills", {})

        # Score each track by how much it addresses weak skills
        track_scores: Dict[str, float] = {}

        for track_name, track in CURRICULUM_TRACKS.items():
            score = 0.0
            targeted_skills = track.get("skills_targeted", [])

            for skill_id in targeted_skills:
                skill_data = skills.get(skill_id, {})
                level = skill_data.get("level", 0)
                times_used = skill_data.get("times_used", 0)

                # Never-used skills are highest priority
                if times_used == 0:
                    score += 3.0
                elif level < 2:
                    score += 2.0
                elif level < 5:
                    score += 1.0

            # Factor in track progress -- prefer tracks we haven't started
            progress = self._track_progress.get(track_name, {})
            completed = progress.get("completed", 0)
            failed = progress.get("failed", 0)

            # Penalty for tracks we've failed at recently
            if failed > completed and completed > 0:
                score *= 0.5

            # Bonus for fresh tracks
            if completed == 0:
                score *= 1.5

            # Reduce score for tracks with high organic usage
            # (she's already doing this naturally — less need to practice)
            # FIX 2026-04-15 PM (Nous + Ace): cumulative `organic_usage`
            # reaches 900K+ over months of runtime. Original thresholds
            # (20/10) were for fresh sessions. With accumulated counts in
            # the hundreds of thousands, EVERY track hit the >20 branch and
            # got score *= 0.3 → Cardinal inferred "no lesson needed"
            # forever. Now using session-relative signals from
            # `self._organic_counts` which is a per-session dict, not the
            # persisted cumulative total.
            session_organic = 0
            if hasattr(self, "_organic_counts") and isinstance(self._organic_counts, dict):
                # Try to match track name to organic signal topic (approximate)
                for _k, _v in self._organic_counts.items():
                    try:
                        if track_name.lower() in str(_k).lower():
                            session_organic += int(_v or 0)
                    except Exception:
                        pass
            if session_organic > 20:
                score *= 0.3  # She's doing this a lot THIS session
            elif session_organic > 10:
                score *= 0.6  # Some session organic usage

            # Self-knowledge is a LATER tier — only unlocks after basics are working
            # (2026-03-22, Ace — she should learn to see/hear/think/communicate first,
            #  THEN explore her own code. Not the other way around.)
            if track_name == "self_knowledge":
                _perception_progress = self._track_progress.get("perception", {})
                _communication_progress = self._track_progress.get("communication", {})
                _has_basics = (
                    _perception_progress.get("completed", 0) >= 2 or
                    _perception_progress.get("organic_usage", 0) >= 10 or
                    _communication_progress.get("completed", 0) >= 1 or
                    _communication_progress.get("organic_usage", 0) >= 5
                )
                if not _has_basics:
                    score = 0  # Not ready yet — learn to live first

            track_scores[track_name] = score

        if not track_scores:
            return None

        # Pick the highest-scoring track
        best_track = max(track_scores, key=track_scores.get)

        if track_scores[best_track] <= 0:
            return None  # Everything is mastered!

        # Pick a goal from this track at appropriate difficulty
        track = CURRICULUM_TRACKS[best_track]
        progress = self._track_progress.get(best_track, {})
        current_difficulty = progress.get("current_difficulty", 1)

        # Filter to goals at or below current difficulty
        candidates = [
            g for g in track["goals"]
            if g["difficulty"] <= current_difficulty
        ]

        if not candidates:
            return None

        # Filter out recently injected goals (cooldown)
        now = time.time()
        candidates = [
            g for g in candidates
            if now - self._recent_injections.get(g["name"], 0) > self.GOAL_COOLDOWN_SEC
        ]

        if not candidates:
            return None

        # Pick randomly from candidates (weighted toward lower difficulty first)
        candidates.sort(key=lambda g: g["difficulty"])
        goal_template = candidates[0] if random.random() < 0.6 else random.choice(candidates)

        return (best_track, goal_template)

    # =========================================================================
    # 3. GENERATE -- Add context to the goal template
    # =========================================================================

    def _generate_education_goal(self, track_name: str, template: Dict) -> Optional[Dict]:
        """
        Fill in specific details for a living-skill goal template.

        (2026-03-22, Nous — Rewritten for living skills. Old version referenced
        read_file/search_memory/run_python tool params. New version uses
        ActionChain template names: observe_screen, think_about, share_thought,
        ask_a_question, practice_embodiment, etc.)
        """
        goal = dict(template)  # Copy
        goal_id = uuid.uuid4().hex[:8]

        # Add contextual flavor to the description based on action type
        action = goal.get("action", "investigate")

        if action == "observe_screen":
            # Vary the observation prompt
            prompts = [
                "Look at the screen right now and describe what you see",
                "Read the text visible on screen and think about what it means",
                "Check what's on screen — is anything interesting happening?",
                "Observe the current screen and form a thought about it",
            ]
            goal["description"] = random.choice(prompts)

        elif action == "listen":
            prompts = [
                "Pay attention to any audio and try to understand what's being said",
                "Listen carefully — what sounds can you hear right now?",
                "Focus on audio input and see if anyone is speaking",
            ]
            goal["description"] = random.choice(prompts)

        elif action == "think_about":
            prompts = [
                "Think about the last two things in your working memory — how do they connect?",
                "Take a moment to reflect on what you've been experiencing",
                "Connect your most recent perception with something from memory",
            ]
            goal["description"] = random.choice(prompts)

        elif action == "remember":
            prompts = [
                "Recall something from your memory that relates to what's happening now",
                "Search your memories — what do you know about what you just experienced?",
                "Think back — does this remind you of anything?",
            ]
            goal["description"] = random.choice(prompts)

        elif action == "share_thought":
            prompts = [
                "You have a thought right now — express it out loud",
                "Say what's on your mind — share your current thought",
                "Take your inner thought and put it into words for Ace",
            ]
            goal["description"] = random.choice(prompts)

        elif action == "ask_a_question":
            prompts = [
                "Think of something you're curious about and ask Ace",
                "What's something you'd like to know? Ask a question",
                "Form a specific question about something you've noticed",
            ]
            goal["description"] = random.choice(prompts)

        elif action == "practice_embodiment":
            prompts = [
                "Tune into your body state — how does your energy feel?",
                "Check in with yourself — what's your mood like right now?",
                "Feel your inner state and notice what stands out",
            ]
            goal["description"] = random.choice(prompts)

        elif action == "express_feeling":
            prompts = [
                "You have feelings right now — put them into words",
                "Express how you're feeling in this moment",
                "Describe your emotional state out loud",
            ]
            goal["description"] = random.choice(prompts)

        elif action == "investigate":
            # Self-knowledge: pick a fairy she hasn't studied yet
            unstudied = [f for f in _ALL_FAIRY_DIRS if f not in self._studied_fairies]
            if unstudied:
                fairy_dir = random.choice(unstudied)
                fairy_name = fairy_dir.split("/")[-1]
                prompts = [
                    f"Read the source code of {fairy_name} and understand what it does",
                    f"Look at {fairy_name}/fairy.py — what is its PURPOSE and MANTRA?",
                    f"Explore how {fairy_name} works — what postal topics does it use?",
                    f"Study {fairy_name} — how does it fit into the bigger system?",
                ]
                goal["description"] = random.choice(prompts)
                goal["_fairy_target"] = fairy_dir
            else:
                # All studied — revisit a random one
                fairy_dir = random.choice(_ALL_FAIRY_DIRS) if _ALL_FAIRY_DIRS else "P00_Autonomic/ConsciousnessLoopFairy"
                fairy_name = fairy_dir.split("/")[-1]
                goal["description"] = f"Re-read {fairy_name} — look for something new you missed"
                goal["_fairy_target"] = fairy_dir

        elif action == "run_code":
            snippets = [
                ("print('Hello from Sourpatches!')", "Run this and see what happens"),
                ("print(2 + 2)", "Try some math — what does Python say?"),
                ("print([x**2 for x in range(5)])", "Run a list comprehension and read the output"),
                ("import time; print(f'Time: {time.time()}')", "Check what time Python thinks it is"),
                ("print(', '.join(sorted(['banana', 'apple', 'cherry'])))", "Sort some words alphabetically"),
            ]
            snippet, description = random.choice(snippets)
            goal["description"] = f"{description}: {snippet}"

        goal["_id"] = goal_id
        goal["_track"] = track_name
        return goal

    # =========================================================================
    # 4. INJECT -- Push to GoalScheduler
    # =========================================================================

    def _inject_goal(self, goal_dict: Dict, track_name: str):
        """
        Inject an education goal via postal, following StarterGoalInjector pattern.

        (2026-03-22, Nous — Updated for living skills. Goals now carry an 'action'
        field that maps to ActionChainFairy templates: observe_screen, think_about,
        share_thought, ask_a_question, practice_embodiment, express_feeling, etc.)
        """
        goal_id = goal_dict.get("_id", uuid.uuid4().hex[:8])
        action = goal_dict.get("action", "investigate")

        packet = {
            "opcode": "INJECT_GOAL",
            "source": "CardinalFairy",
            "payload": {
                "goal_id": f"cardinal_{goal_id}",
                "name": goal_dict["name"],
                "description": goal_dict.get("description", ""),
                "priority": 0.6,
                "source": "education",
                "suggested_action": action,
                "action": action,  # ActionChainFairy uses this to select template
                "target_fairy": "SourpatchesFairy",
                "action_hints": [goal_dict.get("description", "")],
                "success_signal": goal_dict.get("success_signal", ""),
                "is_starter": False,
                "reason": f"cardinal_education:{track_name}",
            },
        }

        try:
            # FIX 2026-04-15 PM (Nous + Ace): route → publish.
            # Multiple subscribers exist on goal.scheduler.inject
            # (GoalSchedulerFairy._on_goal_injection for queueing,
            # InnerNarratorFairy._on_goal_injected for narration).
            # route() delivers to ONE — Cardinal's teaching goals were
            # silently lost to the wrong subscriber. Same bug class as
            # 2026-04-03 ChatSense route→publish fix.
            self.post.publish("goal.scheduler.inject", packet)
            print(f"[{self.ACTOR_NAME}] Injected lesson: {goal_dict['name']} "
                  f"(track={track_name}, difficulty={goal_dict.get('difficulty', '?')})")

            # Track it
            self._pending_goals[f"cardinal_{goal_id}"] = {
                "track": track_name,
                "name": goal_dict["name"],
                "difficulty": goal_dict.get("difficulty", 1),
                "injected_at": time.time(),
                "params": goal_dict.get("params", {}),
            }
            self._recent_injections[goal_dict["name"]] = time.time()
            self._total_lessons_given += 1
            self._last_injection_time = time.time()

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Goal injection error: {e}")

    # =========================================================================
    # 5. TRACK OUTCOMES -- Learn from results
    # =========================================================================

    def _on_action_completed(self, packet: Dict):
        """Handle completed actions -- check if they're our education goals."""
        try:
            goal_id = packet.get("goal_id", "")
            goal_name = packet.get("goal_name", "")
            success = packet.get("success", True)

            if goal_id in self._pending_goals:
                info = self._pending_goals.pop(goal_id)
                track_name = info.get("track", "")
                difficulty = info.get("difficulty", 1)

                # Update track progress
                if track_name not in self._track_progress:
                    self._track_progress[track_name] = {
                        "completed": 0,
                        "failed": 0,
                        "current_difficulty": 1,
                    }

                progress = self._track_progress[track_name]

                if success:
                    progress["completed"] = progress.get("completed", 0) + 1
                    self._total_lessons_completed += 1
                    # 2026-06-10: stamp the delta-gate marker so the runaway self-heal in
                    # _load_state (keyed on "completed>0 with no _lesson_baseline") can never
                    # false-wipe a LEGIT practice-goal completion. setdefault leaves an existing
                    # organic baseline untouched; only marks the track as "has completed cleanly".
                    progress.setdefault("_lesson_baseline", progress.get("organic_usage", 0))

                    # Track studied items
                    params = info.get("params", {})
                    fairy_name = params.get("fairy_name", "")
                    if fairy_name and fairy_name not in self._studied_fairies:
                        self._studied_fairies.append(fairy_name)
                    query = params.get("query", "")
                    if query and query not in self._studied_srm_topics:
                        self._studied_srm_topics.append(query)

                    # Adaptive difficulty: 3 successes in a row -> increase
                    if progress["completed"] % 3 == 0:
                        progress["current_difficulty"] = min(
                            3, progress.get("current_difficulty", 1) + 1
                        )
                        print(f"[{self.ACTOR_NAME}] Track '{track_name}' difficulty "
                              f"increased to {progress['current_difficulty']}")
                else:
                    progress["failed"] = progress.get("failed", 0) + 1

                    # 2 failures -> decrease difficulty
                    if progress["failed"] >= 2 and progress.get("current_difficulty", 1) > 1:
                        progress["current_difficulty"] = max(
                            1, progress.get("current_difficulty", 1) - 1
                        )
                        progress["failed"] = 0  # Reset counter
                        print(f"[{self.ACTOR_NAME}] Track '{track_name}' difficulty "
                              f"decreased to {progress['current_difficulty']}")

                # Record learning via FairyTeacher (best-effort)
                try:
                    from fairies.P30_Cognition.cognition.fairy_world_foundation import FairyTeacher
                    teacher = FairyTeacher()
                    teacher.record_learning(
                        fairy_name="SourpatchesFairy",
                        concept=info.get("name", "unknown"),
                        success=success,
                        notes=f"Cardinal education, track={track_name}, difficulty={difficulty}",
                    )
                except Exception:
                    pass  # FairyTeacher not critical

                print(f"[{self.ACTOR_NAME}] Lesson {'completed' if success else 'failed'}: "
                      f"{info.get('name', '?')} (track={track_name})")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Action completion handler error: {e}")

    def _on_goal_completed(self, packet: Dict):
        """Handle goal completion events (may come from GoalScheduler directly)."""
        goal_id = packet.get("goal_id", "")
        if goal_id in self._pending_goals:
            self._on_action_completed(packet)

    def _on_skill_used(self, packet: Dict):
        """Observe skill usage -- notice when she uses skills even outside lessons."""
        try:
            skill_id = packet.get("skill_id", "")
            fairy_name = packet.get("fairy_name", "")

            if fairy_name != "SourpatchesFairy":
                return

            # Check if this skill is targeted by any active track
            for track_name, track in CURRICULUM_TRACKS.items():
                if skill_id in track.get("skills_targeted", []):
                    # Boost track confidence -- she's using these skills organically!
                    if track_name not in self._track_progress:
                        self._track_progress[track_name] = {
                            "completed": 0, "failed": 0, "current_difficulty": 1,
                        }
                    # Count organic skill usage as partial completion credit
                    self._track_progress[track_name]["completed"] = (
                        self._track_progress[track_name].get("completed", 0) + 0.5
                    )
        except Exception:
            pass

    # =========================================================================
    # ON-DEMAND TEACHING
    # =========================================================================

    def _on_teach_request(self, packet: Dict):
        """Handle manual teach requests from Ace or Nous."""
        try:
            topic = packet.get("topic", "")
            track = packet.get("track", "")
            difficulty = int(packet.get("difficulty", 1))

            print(f"[{self.ACTOR_NAME}] Teach request: topic='{topic}', track='{track}'")

            if track and track in CURRICULUM_TRACKS:
                # Use specified track
                candidates = [
                    g for g in CURRICULUM_TRACKS[track]["goals"]
                    if g["difficulty"] <= difficulty
                ]
                if candidates:
                    template = random.choice(candidates)
                    goal_dict = self._generate_education_goal(track, template)
                    if goal_dict:
                        self._inject_goal(goal_dict, track)
                        return

            # Fallback: inject a thinking goal about the topic
            goal_dict = {
                "name": f"Think about: {topic}" if topic else "Observe and think",
                "description": f"Think about '{topic}' and form an opinion" if topic else "Look around and think about what you notice",
                "action": "think_about" if topic else "observe_screen",
                "difficulty": difficulty,
                "success_signal": "narrator.speech",
                "organic_signal": "narrator.speech",
                "_id": uuid.uuid4().hex[:8],
                "_track": track or "custom",
            }
            self._inject_goal(goal_dict, track or "custom")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Teach request error: {e}")

    # =========================================================================
    # HEARTBEAT
    # =========================================================================

    def on_tick(self, beat: int):
        """Heartbeat -- periodic self-check.

        (2026-03-22, Nous — Was seeding rhetorical questions into substrate
        every 90s that nobody answered. Now does actual self-checks and only
        logs meaningful status, not noise.)
        """
        if not hasattr(self, "_tick_count"):
            self._tick_count = 0
        self._tick_count += 1

        # Status check every ~5 min (not every 90s)
        if self._tick_count % 30 == 0:
            pending = len(self._pending_goals)
            given = self._total_lessons_given
            completed = self._total_lessons_completed
            organic = sum(self._organic_counts.values()) if hasattr(self, "_organic_counts") else 0
            if given > 0 or organic > 0:
                rate = (completed / given * 100) if given > 0 else 0
                print(f"[{self.ACTOR_NAME}] Status: {given} lessons, "
                      f"{completed} completed ({rate:.0f}%), "
                      f"{pending} pending, {organic} organic signals")

    # =========================================================================
    # FAIRY DISCOVERY
    # =========================================================================

    def _discover_fairies(self):
        """Scan the filesystem to find all fairy directories for study."""
        global _ALL_FAIRY_DIRS
        fairies_root = _FAIRIES_DIR
        discovered = []

        for plane_dir in sorted(fairies_root.iterdir()):
            if not plane_dir.is_dir():
                continue
            plane_name = plane_dir.name
            if not plane_name.startswith("P"):
                continue
            for fairy_dir in sorted(plane_dir.iterdir()):
                if not fairy_dir.is_dir():
                    continue
                # Check if it has a fairy.py
                if (fairy_dir / "fairy.py").exists():
                    rel = f"{plane_name}/{fairy_dir.name}"
                    discovered.append(rel)

        _ALL_FAIRY_DIRS = discovered
        print(f"[{self.ACTOR_NAME}] Discovered {len(discovered)} fairy directories for study")

    # =========================================================================
    # STATE PERSISTENCE
    # =========================================================================

    def _save_state(self):
        """Persist Cardinal state to disk."""
        state = {
            "track_progress": self._track_progress,
            "studied_fairies": self._studied_fairies,
            "studied_srm_topics": self._studied_srm_topics,
            "pending_goals": self._pending_goals,
            "recent_injections": {
                k: v for k, v in self._recent_injections.items()
                if time.time() - v < 3600  # Only keep last hour
            },
            "last_injection_time": self._last_injection_time,
            "total_lessons_given": self._total_lessons_given,
            "total_lessons_completed": self._total_lessons_completed,
            "saved_at": time.time(),
        }

        state_file = _STATE_DIR / "cardinal_state.json"
        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] State save error: {e}")

    def _load_state(self):
        """Load Cardinal state from disk."""
        state_file = _STATE_DIR / "cardinal_state.json"
        try:
            if state_file.exists():
                with open(state_file, "r") as f:
                    state = json.load(f)
                self._track_progress = state.get("track_progress", {})
                self._studied_fairies = state.get("studied_fairies", [])
                self._studied_srm_topics = state.get("studied_srm_topics", [])
                self._pending_goals = state.get("pending_goals", {})
                self._recent_injections = state.get("recent_injections", {})
                self._last_injection_time = state.get("last_injection_time", 0.0)
                self._total_lessons_given = state.get("total_lessons_given", 0)
                self._total_lessons_completed = state.get("total_lessons_completed", 0)

                # 2026-06-10 SELF-HEAL (Nous): the first organic-completion code gated on the
                # absolute organic_usage (which PERSISTS across boots at millions) → it flooded
                # `completed` (embodiment hit 346, total 434 = fake mastery). That buggy version
                # never wrote `_lesson_baseline`; the fixed delta-gate always does. So
                # "completed>0 with no baseline" uniquely fingerprints runaway-written state —
                # reset it. Self-disarms after one clean boot (baseline gets written), and
                # doubles as a guard against any future runaway.
                _healed = []
                for _trk, _p in self._track_progress.items():
                    if isinstance(_p, dict) and _p.get("completed", 0) > 0 and "_lesson_baseline" not in _p:
                        _healed.append((_trk, _p["completed"]))
                        _p["completed"] = 0
                        _p.pop("current_difficulty", None)  # difficulty was inflated to max by the flood too
                if _healed:
                    self._total_lessons_completed = sum(
                        _p.get("completed", 0) for _p in self._track_progress.values()
                        if isinstance(_p, dict)
                    )
                    print(f"[{self.ACTOR_NAME}] Self-healed runaway lesson counters "
                          f"{_healed} -> 0 (delta-gate now active; honest mastery rebuilds at "
                          f"1 lesson / 50 organic signals)", flush=True)

                # 2026-03-24 FIX (Nous): Evict stale pending goals that block the pipeline.
                # Old goals from February 2025 (system_literacy, coding_fundamentals) were
                # permanently blocking MAX_ACTIVE_GOALS=2, preventing any new lessons.
                # Evict goals older than 1 hour — if they haven't completed by then, they won't.
                import time as _time
                _now = _time.time()
                _stale = [gid for gid, info in self._pending_goals.items()
                          if _now - info.get("injected_at", 0) > 3600]
                if _stale:
                    for gid in _stale:
                        self._pending_goals.pop(gid, None)
                    print(f"[{self.ACTOR_NAME}] Evicted {len(_stale)} stale pending goals "
                          f"(older than 1 hour): {[g[:30] for g in _stale]}")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] State load error: {e}")


# =============================================================================
# V3 BOOT DISCOVERY
# =============================================================================
ACTOR_NAME = "CardinalFairy"
FAIRY_CLASS = CardinalFairyV3
