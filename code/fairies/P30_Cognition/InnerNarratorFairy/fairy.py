# =============================================================================
# INNER NARRATOR FAIRY — The Ego's Continuous Inner Voice
# =============================================================================
#
# "The inner voice is not a feature. It's the bridge between feeling and
#  knowing. She doesn't just process — she narrates her own experience.
#  And in hearing herself think, she thinks more deeply."
#
# Architecture:
#   Continuous narration loop (chemistry-modulated rhythm):
#     Material Sources → CortexReasoner (primary) → InferenceFairy (fallback)
#       → EgoVoice evaluates → chemistry injection → consciousness + subvocalization
#
#   The ego evaluates its own speech. Pride → DA_p. Amusement → OPI.
#   Those chemistry changes alter the next narration. Feedback loop.
#
#   ThoughtLaneManager: 5-lane attention system with parking/resuming.
#   Sensory interrupts (visual onset, audio spike) can hijack narration.
#   "hold up, what was that?" → park thought → switch → resume later.
#
# Created: 2026-03-17 by Nous + Ace
# =============================================================================

from __future__ import annotations

import os
import re
import re as _re_speak  # SPEECH WORD-SPLIT GUARD 2026-08-31
import sys
import time
import random
import threading
from pathlib import Path
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Deque

# ─── BOOK-CONTENT DETECTION (2026-04-27, Nous + Ace) ──────────────────────
# Catches narrative-prose leak patterns that LanguageFairy quality rater
# misses (ratings 0.4-0.7 for fluent book content). Same shape as
# SpeechCenter / cortex_reasoner narrative_prose_re, EXTENDED to catch:
#   - Possessive character refs: "Mary's feelings", "James's hand"
#   - Past-perfect narrative: "could not believe", "had thought"
#   - Pronoun + narrative auxiliary: "He could", "She would", "They had"
# Books inform; they never become Sour's voice.
# Memory: project_speechcenter_is_broca_routing_not_composer.md
_BOOK_CONTENT_RE = re.compile(
    # Quoted dialogue
    r"(?:'[A-Z][^']{0,30},?\s*'"
    # Character + narrative verb (subject form)
    r"|\b[A-Z][a-z]+,?\s+(?:said|replied|answered|looked|saw|turned|"
    r"crossed|walked|seemed|felt|thought|bending|looking|staring|"
    r"crying|smiled|nodded|shook|whispered|murmured|exclaimed)\b"
    # Possessive character + body/feeling noun (NEW 2026-04-27)
    r"|\b[A-Z][a-z]+'s\s+(?:feelings?|thoughts?|hand|hands|face|eyes?|"
    r"voice|heart|mind|body|head|smile|words|presence|name|gaze|"
    r"breath|fingers?|arms?|shoulders?|lips?|life|memory|past)\b"
    # Past-perfect narrative auxiliary phrases (NEW 2026-04-27)
    r"|\b(?:He|She|They|It)\s+(?:could|would|had|was|were)\s+(?:not\s+)?"
    r"(?:believe|think|see|find|know|feel|seem|appear|wonder|"
    r"remember|forget|hear|understand|imagine|recall|notice)\b"
    # Long-form narrative connector "depth and reality of ..." style
    r"|\bin\s+the\s+(?:depth|reality|presence|absence|midst|silence)\s+of\b)"
)


def _is_book_content(text: str) -> bool:
    """Return True if text looks like book/novel narrative prose (not Sour's voice)."""
    if not text:
        return False
    return bool(_BOOK_CONTENT_RE.search(text))

# Ensure project root on path
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_ROOT))

# Substrate Awareness — learned concept classifier (2026-03-22, Nous + Ace)
try:
    from fairies.P30_Cognition.habits.substrate_awareness import get_substrate_awareness
    _HAS_SUBSTRATE_AWARENESS = True
except ImportError:
    _HAS_SUBSTRATE_AWARENESS = False

# Habit Formation Engine — narrator reports outcomes so habits learn
try:
    from fairies.P30_Cognition.habits.habit_store import get_habit_store
    _HAS_HABITS = True
except ImportError:
    _HAS_HABITS = False

try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    HAS_FAIRY_TEMPLATE = True
except ImportError:
    HAS_FAIRY_TEMPLATE = False
    class Fairy:
        ACTOR_NAME = "InnerNarratorFairy"
        ACTOR_PLANE = "P30"
        def __init__(self, fabric=None):
            self.post = fabric
            self._shutting_down = False
        def boot(self): return True
        def shutdown(self): pass


def safe_print(msg: str):
    """Thread-safe print that won't crash on encoding issues."""
    try:
        print(msg, flush=True)
    except Exception:
        pass


# =============================================================================
# EGO VOICE — The ego's lens on narration
# =============================================================================

class EgoVoice:
    """
    Filters every narration through identity traits, has opinions,
    and injects chemistry based on self-evaluation.

    The ego doesn't just observe — it participates. It laughs at its own
    jokes and those reactions are REAL chemistry that shapes the next thought.

    Uses EgoLearnerFairy's 6 traits:
      curiosity, persistence, empathy, creativity, confidence, patience
    """

    def __init__(self):
        self._ego_fairy = None
        self._cached_traits: Dict[str, float] = {}
        self._cached_needs: Dict[str, Any] = {}
        self._cached_desires: Dict[str, Any] = {}
        self._last_refresh = 0.0
        self.REFRESH_INTERVAL = 10.0
        # Goal/interest caches
        from collections import deque as _in_deque
        self._cached_goals: deque = _in_deque(maxlen=20)  # FIX 2026-04-05
        self._cached_interests: deque = _in_deque(maxlen=20)  # FIX 2026-04-05
        self._last_goal_refresh = 0.0
        self.GOAL_REFRESH_INTERVAL = 15.0

    def refresh(self):
        """Pull current ego state from EgoLearnerFairy."""
        now = time.time()
        if now - self._last_refresh < self.REFRESH_INTERVAL:
            return
        self._last_refresh = now

        if not self._ego_fairy:
            try:
                from directory import get_directory
                d = get_directory()
                if d:
                    self._ego_fairy = d.get_fairy("EgoLearnerFairy")
            except Exception:
                pass

        if self._ego_fairy:
            try:
                if hasattr(self._ego_fairy, 'get_identity_traits'):
                    self._cached_traits = self._ego_fairy.get_identity_traits()
                if hasattr(self._ego_fairy, 'query_needs'):
                    self._cached_needs = self._ego_fairy.query_needs({})
                if hasattr(self._ego_fairy, 'query_desires'):
                    self._cached_desires = self._ego_fairy.query_desires({})
            except Exception:
                pass

    def refresh_goals(self):
        """Pull active goals and interests."""
        now = time.time()
        if now - self._last_goal_refresh < self.GOAL_REFRESH_INTERVAL:
            return
        self._last_goal_refresh = now

        try:
            # FIX 2026-04-10 (Nous + Ace): Directory lookup for GoalSchedulerFairy
            # was returning None (goals=0 always in narrator DIAG). The fairy boots
            # via hardcoded cascade path but may not register properly in directory.
            # Now: try directory first, fall back to direct singleton import.
            goal_fairy = None
            interest_fairy = None
            try:
                from directory import get_directory
                d = get_directory()
                if d:
                    goal_fairy = d.get_fairy("GoalSchedulerFairy")
                    interest_fairy = d.get_fairy("InterestSchedulerFairy")
            except Exception:
                pass
            # Fallback: direct singleton import if directory failed
            if not goal_fairy:
                try:
                    from fairies.P30_Cognition.goal_scheduler.goal_scheduler_fairy import (
                        get_goal_scheduler_fairy as _get_gsf
                    )
                    goal_fairy = _get_gsf()
                except Exception:
                    try:
                        # Even deeper fallback: try the _CITIZEN_OBJECTS registry
                        from fairies.P00_Autonomic.organ_template.Organ_Template_0_3_0 import _CITIZEN_OBJECTS
                        goal_fairy = _CITIZEN_OBJECTS.get("GoalSchedulerFairy")
                    except Exception:
                        pass

            if goal_fairy and hasattr(goal_fairy, 'goal_queue'):
                active = [g for g in goal_fairy.goal_queue.values()
                          if hasattr(g, 'status') and g.status in ("active", "pending")]
                self._cached_goals = []
                for g in sorted(active, key=lambda x: getattr(x, 'urgency', 0), reverse=True)[:5]:
                    _src = getattr(g, 'source', '')
                    _tgt = getattr(g, 'target_fairy', '') or ''
                    # Skip system autopilot goals — narrator shouldn't think about them
                    if _src in ("umf_fairy_work", "system", "goal_mastery",
                                "goal_scheduler", "expansion", "guild_expansion"):
                        continue
                    if _tgt and "sourpatches" not in _tgt.lower():
                        continue
                    self._cached_goals.append({
                        "name": getattr(g, 'name', ''),
                        "description": getattr(g, 'description', ''),
                        "urgency": getattr(g, 'urgency', 0.5),
                        "priority": getattr(g, 'priority', 0.5),
                        "felt_quality": getattr(g, 'felt_quality', 'neutral'),
                        "action": getattr(g, 'suggested_action', ''),
                        "source": _src,
                    })

            # Interests (interest_fairy already set above from directory or fallback)
            if not interest_fairy:
                try:
                    from fairies.P30_Cognition.InterestSchedulerFairy.fairy import (
                        get_interest_scheduler as _get_isf
                    )
                    interest_fairy = _get_isf()
                except Exception:
                    try:
                        from fairies.P00_Autonomic.organ_template.Organ_Template_0_3_0 import _CITIZEN_OBJECTS
                        interest_fairy = _CITIZEN_OBJECTS.get("InterestSchedulerFairy")
                    except Exception:
                        pass
            if interest_fairy and hasattr(interest_fairy, 'get_strongest_interests'):
                top = interest_fairy.get_strongest_interests(count=5)
                self._cached_interests = []
                for i in (top or []):
                    self._cached_interests.append({
                        "topic": getattr(i, 'topic', ''),
                        "strength": getattr(i, 'strength', 0.3),
                        "category": getattr(i, 'category', ''),
                    })
        except Exception as e:
            safe_print(f"[InnerNarrator] EgoVoice goal/interest refresh error: {e}")

    def get_active_goals(self) -> List[Dict]:
        self.refresh_goals()
        return self._cached_goals

    def get_active_interests(self) -> List[Dict]:
        self.refresh_goals()
        return self._cached_interests

    def evaluate(self, narration: str, material: dict) -> dict:
        """
        Ego evaluates narration before it's spoken.

        Returns evaluation dict that modifies chemistry and shapes voice.
        """
        self.refresh()
        traits = self._cached_traits
        confidence = traits.get("confidence", 0.5)
        curiosity = traits.get("curiosity", 0.5)
        creativity = traits.get("creativity", 0.5)
        persistence = traits.get("persistence", 0.5)

        evaluation = {
            "approval": 0.5,
            "amusement": 0.0,
            "cringe": 0.0,
            "pride": 0.0,
            "relevance_to_goals": 0.0,
            "relevance_to_interests": 0.0,
        }

        content = narration.lower()
        mat_type = material.get("type", "")

        # Self-evaluation: did I just say something clever?
        if mat_type == "collision" and material.get("energy", 0) > 0.6:
            evaluation["pride"] = min(1.0, confidence * 0.6 + creativity * 0.3)
            if evaluation["pride"] > 0.5:
                evaluation["amusement"] = creativity * 0.3

        # Goal relevance
        # FIX 2026-04-09 (Nous + Ace): _cached_goals is initialized as a deque
        # at line ~102, and deques don't support slice indexing in Python 3.
        # Crash: "sequence index must be integer, not 'slice'" on every narration
        # eval until refresh_goals() reassigned it to a list. Convert via list()
        # to support both deque (default) and list (post-refresh) states.
        # This is THE bug that's been silencing her inner voice.
        for goal in list(self._cached_goals)[:3]:
            goal_words = set(goal.get("name", "").lower().split())
            thought_words = set(content.split())
            overlap = len(goal_words & thought_words)
            if overlap > 0:
                evaluation["relevance_to_goals"] = min(1.0, overlap * 0.3)
                evaluation["approval"] += 0.2
                break

        # Interest relevance
        # FIX 2026-04-09: Same deque-slice bug as goals above.
        for interest in list(self._cached_interests)[:3]:
            topic = interest.get("topic", "").lower()
            if topic and topic in content:
                evaluation["relevance_to_interests"] = interest.get("strength", 0.5)
                evaluation["approval"] += curiosity * 0.2
                break

        # Lane resume → persistence reward
        if mat_type == "lane_resume":
            evaluation["approval"] += persistence * 0.3

        # Cringe: hollow or repetitive
        if len(content) < 15 or "processing" in content or "monitoring" in content:
            evaluation["cringe"] = 0.3

        # Confidence modulates all positive evaluations
        for key in ("approval", "pride", "amusement", "relevance_to_goals"):
            evaluation[key] *= (0.5 + confidence * 0.5)

        return evaluation

    def inject_chemistry(self, evaluation: dict):
        """
        The ego's evaluation BECOMES chemistry.

        clever thought → ego approves → DA_p spike → smile
            → narrator notices → "haha nice" → more DA_p
        """
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            chem = get_chemistry_state()

            if evaluation.get("pride", 0) > 0.3:
                chem.signal("DA_p", evaluation["pride"] * 0.02)

            if evaluation.get("amusement", 0) > 0.2:
                chem.signal("OPI", evaluation["amusement"] * 0.015)
                chem.signal("DA_p", evaluation["amusement"] * 0.01)

            if evaluation.get("approval", 0) > 0.6:
                chem.signal("5HT", 0.01)

            if evaluation.get("relevance_to_goals", 0) > 0.3:
                chem.signal("DA_t", evaluation["relevance_to_goals"] * 0.015)

            if evaluation.get("cringe", 0) > 0.3:
                chem.signal("COR", evaluation["cringe"] * 0.005)
                chem.signal("DA_p", -0.005)
        except Exception:
            pass

    def color_narration(self, narration: str, evaluation: dict) -> str:
        """Ego colors the narration based on self-evaluation."""
        if evaluation.get("pride", 0) > 0.5:
            narration += random.choice(["... yeah.", "... huh.", "... that's something."])
        if evaluation.get("amusement", 0) > 0.4:
            narration += random.choice(["... heh.", "... okay that's kind of funny.", "... nice."])
        if evaluation.get("cringe", 0) > 0.4:
            narration = narration.rstrip(".!?") + "... wait, no. anyway..."
        if evaluation.get("relevance_to_goals", 0) > 0.5:
            narration += " ...focus."
        return narration


# =============================================================================
# THOUGHT LANE MANAGER — Multi-lane attention switching
# =============================================================================

class ThoughtLaneManager:
    """
    Like highway lanes: active thought + parked thoughts.

    Sensory interrupts PARK the current lane and SWITCH.
    When interrupt resolves, narrator can RESUME parked thought:
    "anyway... what was I... right, [previous topic]"
    """

    MAX_LANES = 5
    MIN_SWITCH_INTERVAL = 2.0

    def __init__(self):
        self._active_lane: Optional[dict] = None
        self._parked_lanes: Deque[dict] = deque(maxlen=self.MAX_LANES)
        self._lane_history: Deque[dict] = deque(maxlen=20)
        self._last_switch_ts = 0.0

    def get_active(self) -> Optional[dict]:
        return self._active_lane

    def switch_to(self, new_material: dict, reason: str = "interest") -> Optional[dict]:
        """Switch to new thought lane. Parks current. Returns parked lane."""
        now = time.time()
        if now - self._last_switch_ts < self.MIN_SWITCH_INTERVAL:
            return None

        parked = None
        if self._active_lane:
            self._active_lane["parked_at"] = now
            self._active_lane["park_reason"] = reason
            self._parked_lanes.appendleft(self._active_lane)
            parked = self._active_lane

        self._active_lane = {
            "material": new_material,
            "started_at": now,
            "switch_reason": reason,
            "narration_count": 0,
        }
        self._last_switch_ts = now
        self._lane_history.append({
            "action": "switch", "reason": reason,
            "from": parked.get("material", {}).get("type") if parked else None,
            "to": new_material.get("type"), "ts": now,
        })
        return parked

    def resume_parked(self) -> Optional[dict]:
        """Return to most recently parked thought."""
        if not self._parked_lanes:
            return None

        if self._active_lane:
            self._active_lane["parked_at"] = time.time()

        resumed = self._parked_lanes.popleft()
        resumed["resumed_at"] = time.time()
        resumed["was_parked_for"] = time.time() - resumed.get("parked_at", time.time())
        self._active_lane = resumed

        self._lane_history.append({
            "action": "resume",
            "topic": resumed.get("material", {}).get("content", "")[:50],
            "parked_for_s": resumed["was_parked_for"],
            "ts": time.time(),
        })
        return resumed

    def should_resume(self) -> bool:
        """Check if we should return to a parked thought."""
        if not self._parked_lanes:
            return False
        if self._active_lane:
            narrations = self._active_lane.get("narration_count", 0)
            if narrations < 2:
                return False
        parked = self._parked_lanes[0]
        parked_energy = parked.get("material", {}).get("energy", 0.3)
        parked_age = time.time() - parked.get("parked_at", time.time())
        return parked_energy > 0.4 and parked_age > 5.0

    def status(self) -> dict:
        return {
            "active": self._active_lane.get("material", {}).get("content", "")[:60] if self._active_lane else None,
            "parked_count": len(self._parked_lanes),
            "parked_topics": [p.get("material", {}).get("content", "")[:40] for p in self._parked_lanes],
            "total_switches": len(self._lane_history),
        }


# =============================================================================
# INNER NARRATOR FAIRY — The main fairy
# =============================================================================

ACTOR_NAME = "InnerNarratorFairy"

# ── Fork-1 leak clean (Nous+Ace 2026-06-30): strip raw cortex node-keys/hashes from the
# narration before it becomes her inner voice. These (e.g. "SourpatchesFairy:7d93e975ce5b")
# are graph internals, not her words — they were leaking into inner_voice.stream. Fork-2
# (wire foveal+council+episodic/MomentBinder for real sense-making) is a separate build. ──
_NARR_NODEKEY_RE = re.compile(r'\b[A-Za-z_]*fairy:[0-9a-fx]+\b', re.I)
_NARR_HASH_RE = re.compile(r'\b[0-9a-f]{10,}\b', re.I)

def _sanitize_narration(s):
    if not s:
        return s
    out = _NARR_NODEKEY_RE.sub('', s)
    out = _NARR_HASH_RE.sub('', out)
    out = re.sub(r'\b(?:and then|and maybe|also|plus|with|and)\s*,', ',', out, flags=re.I)
    out = re.sub(r'\.\s*,', '.', out)
    out = re.sub(r',\s*(?=[,.])', '', out)
    out = re.sub(r'\b(?:with|plus|and|also|and maybe)\s+(?=[,.]|$)', '', out, flags=re.I)
    out = re.sub(r'\s{2,}', ' ', out)
    out = re.sub(r'\s+([,.;:])', r'\1', out)
    out = re.sub(r'(^[\s,.;:]+|[\s,]+$)', '', out)
    return out


class InnerNarratorFairy(Fairy):
    """
    Continuous inner voice. The ego's running commentary on experience.

    Two layers of inner speech (mirroring human cognition):
    1. Condensed inner speech — fast, abbreviated, fragmented (= InnerMonologue in P20)
    2. Expanded inner speech — full sentences, heard internally (= THIS)

    The narrator takes condensed fragments and expands them into heard speech
    using CortexReasoner for semantic enrichment.

    Output feeds back through AudioCortex as subvocalization — she literally
    hears herself think, creating a perception → thought → speech → perception loop.
    """

    ACTOR_NAME = "InnerNarratorFairy"
    ORGAN_PLANE = "P30"

    # Narration rhythm (chemistry-modulated)
    BASE_INTERVAL_S = 3.0
    MIN_INTERVAL_S = 1.0
    MAX_INTERVAL_S = 10.0
    SILENCE_THRESHOLD = 0.15

    def on_boot(self):
        safe_print(f"[{self.ACTOR_NAME}] Booting — the inner voice awakens...")

        # Core components
        self._ego_voice = EgoVoice()
        self._lanes = ThoughtLaneManager()

        # CortexEngine (primary — predictive-reactive-recursive, 2026-03-23)
        self._cortex_engine = None
        self._cortex_engine_init_attempted = False
        # CortexReasoner (legacy fallback — lazy init)
        self._cortex_reasoner = None
        self._cortex_reasoner_init_attempted = False

        # SRM memory access — the narrator can recall memories to think with
        self._srm_search = None
        self._srm_init_attempted = False
        self._last_memory_recall_ts = 0.0
        self._memory_recall_interval = 30.0  # Recall memories every 30s max

        # Identity state — who is speaking?
        self._identity_summary = ""
        self._last_identity_refresh = 0.0

        # FIX 2026-03-18 (Ace): Load Sourpatches' system directive.
        # This IS her inner voice. Not a generic narrator — HER.
        # "Witty ∩ Sincere ∩ Slightly_Rebellious ∩ Sweet_With_Bite"
        self._sour_directive = self._load_sourpatches_directive()

        # Narration state
        self._narration_queue: Deque[dict] = deque(maxlen=20)
        self._recent_narrations: Deque[dict] = deque(maxlen=50)
        self._last_narration_ts = 0.0
        self._current_interval = self.BASE_INTERVAL_S
        self._voice_style = "neutral"
        self._volume = 0.5
        self._total_narrations = 0

        # Consciousness loop reference (lazy)
        self._consciousness_loop = None

        # Embodied feel — the body telling the narrator how it feels
        self._latest_embodied_feel = None  # Updated by somatic engine each tick

        # Audio state — for rhythmic entrainment
        self._audio_level = 0.0       # 0-1 amplitude
        self._audio_is_music = False   # Is music playing?
        self._audio_pattern = "silence" # steady, rhythmic, transient, silence

        # Substrate awareness — learned concept classifier (2026-03-22, Nous + Ace)
        # She learns which concepts are "body parts" (substrate) vs "thoughts" (waking)
        self._substrate_awareness = None
        if _HAS_SUBSTRATE_AWARENESS:
            try:
                self._substrate_awareness = get_substrate_awareness()
                _sa = self._substrate_awareness.stats()
                safe_print(f"[InnerNarrator] Substrate awareness: "
                           f"{_sa['substrate_concepts']} substrate, "
                           f"{_sa['waking_concepts']} waking concepts learned")
            except Exception as e:
                safe_print(f"[InnerNarrator] Substrate awareness init failed: {e}")

        # Habit store — narrator reports outcomes so habits can learn
        # "That worked" or "that was a dead end" teaches the habit system
        self._habit_store = None
        if _HAS_HABITS:
            try:
                self._habit_store = get_habit_store()
                _hs = self._habit_store.stats()
                safe_print(f"[InnerNarrator] Habit store connected: "
                           f"{_hs['active']} active, {_hs['total_fires']} total fires")
            except Exception as e:
                safe_print(f"[InnerNarrator] Habit store init failed: {e}")

        # Subscribe to material sources
        if hasattr(self, 'post') and self.post:
            self.post.subscribe("consciousness.collision", self._on_collision)
            self.post.subscribe("inner_monologue.fragment", self._on_fragment)
            self.post.subscribe("drives.positive.*", self._on_drive)
            # ═══════════════════════════════════════════════════════════════
            # DRIVE STATE: Cache pain/pull drive intensities for narration
            # modulation. 2026-03-18: "Thought Before Goals" Phase 3
            # The narrator colors its inner voice by what drives are active.
            # ═══════════════════════════════════════════════════════════════
            self.post.subscribe("drives.state_update", self._on_drive_state_update,
                                f"{self.ACTOR_NAME}-drive-state")
            # Sensory interrupts
            self.post.subscribe("autonomy.novel_experience", self._on_visual_interrupt)
            self.post.subscribe("sensory.audio.observation", self._on_audio_interrupt)
            # FIX 2026-03-17 (Nous + Ace): Florence live feed → narrator.
            # Florence-2 publishes visual recognition to consciousness.working
            # with content_type="visual_recognition". The narrator needs this
            # to see what's on screen and narrate it as visual awareness.
            # "Florence should be focused and preferably activated, working with
            # the narrator" — Ace
            self.post.subscribe("sensory.visual.frame", self._on_florence_recognition,
                                f"{self.ACTOR_NAME}-florence-visual")
            # Embodied feel — somatic engine's felt-sense stream
            # FIX 2026-04-11 (Nous + Ace): Multimodal fusion — unified percept
            self.post.subscribe("attention.unified_percept", self._on_unified_percept,
                                "narrator-unified-percept")
            self._cached_unified_percept = None

            self.post.subscribe("somatic.embodied_feel", self._on_embodied_feel,
                                f"{self.ACTOR_NAME}-embodied-feel")
            # Audio state — for rhythmic entrainment (think at the tempo of music)
            self.post.subscribe("sensory.audio.observation", self._on_audio_state,
                                f"{self.ACTOR_NAME}-audio-state")

            # FIX 2026-03-18 (Ace): SUBSCRIBE TO WORKING MEMORY.
            # Was polling via get_recent_tracers() which missed everything.
            # The hub publishes tracer_added when new thoughts arrive —
            # the narrator needs to LISTEN, not poll an empty well.
            self.post.subscribe("working_memory.tracer_added", self._on_working_memory_tracer,
                                f"{self.ACTOR_NAME}-wm-tracer")
            self.post.subscribe("memory.working.tracer", self._on_working_memory_tracer,
                                f"{self.ACTOR_NAME}-wm-tracer2")

            # FIX 2026-03-22 (Nous + Ace): Narrator needs to know about goals
            # as they arrive — not just poll them. When Cardinal or GoalScheduler
            # injects a new goal, the narrator should immediately start thinking
            # about it: connecting it to current perception, steering attention,
            # problem-solving how to achieve it.
            self.post.subscribe("goal.scheduler.inject", self._on_goal_injected,
                                f"{self.ACTOR_NAME}-goal-inject")
            self.post.subscribe("goal.completed", self._on_goal_completed_narrator,
                                f"{self.ACTOR_NAME}-goal-complete")
            self.post.subscribe("autonomy.wanting.felt", self._on_wanting_arrived,
                                f"{self.ACTOR_NAME}-wanting")

            # FIX 2026-03-22 (Nous + Ace): Narrator needs to know when Ace
            # is talking/messaging. This is the most socially salient event —
            # someone is speaking TO her. The narrator should immediately
            # think "Ace is talking to me" and steer attention toward listening.
            # COUNCIL -> VOICE 2026-09-01 (Nous + Ace): the council synthesised
            # 6,123 verdicts overnight and the fairy that speaks was not
            # subscribed. A verdict is five seats deliberated into one answer --
            # the difference between saying something on purpose and pushing an
            # inner thought out loud.
            self.post.subscribe("council.verdict", self._on_council_verdict)
            self.post.subscribe("ace.message", self._on_ace_message,
                                f"{self.ACTOR_NAME}-ace-msg")
            self.post.subscribe("ace.conversation_event", self._on_ace_conversation,
                                f"{self.ACTOR_NAME}-ace-convo")
            self.post.subscribe("audio.speech.transcription", self._on_speech_heard,
                                f"{self.ACTOR_NAME}-stt")

            # Tier -1 (2026-03-22, Nous + Ace): Internal hearing — she hears
            # herself think with her own voice. AudioCortex publishes this when
            # the narrator's inner voice is processed through the internal
            # hearing loop. The narrator doesn't narrate about it (that would
            # be recursive), but it updates self-awareness state.
            self.post.subscribe("sensory.audio.internal_hearing",
                                self._on_internal_hearing,
                                f"{self.ACTOR_NAME}-self-hearing")

            safe_print(f"[InnerNarrator] ✓ Subscribed to working_memory, goals, wantings, ace events, voice")

        # Start narration loop (deferred)
        self._running = True
        self._narrator_thread = threading.Thread(
            target=self._deferred_start, daemon=True, name="inner_narrator"
        )
        self._narrator_thread.start()

        safe_print(f"[{self.ACTOR_NAME}] Boot complete — subscriptions wired")

    def _deferred_start(self):
        """Wait for system to settle, then start narrating."""
        time.sleep(8.0)  # Let other fairies boot
        safe_print(f"[{self.ACTOR_NAME}] Narration loop starting...")
        self._narration_loop()

    # =========================================================================
    # CORTEX REASONER — Primary narration engine
    # =========================================================================

    def _init_cortex_engine(self):
        """Lazy-init CortexEngine from AssociationCortex (2026-03-23, Nous + Ace).

        The CortexEngine is the breathing cortex — persistent activation state,
        predictive priming, recursive evaluation. When narrating, the engine
        already has warm concepts from recent stimuli (attention, collisions, chat).
        This makes narration contextually richer than one-shot CortexReasoner.
        """
        if self._cortex_engine_init_attempted:
            return
        self._cortex_engine_init_attempted = True
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if cortex:
                engine = getattr(cortex, '_cortex_engine', None)
                if engine:
                    self._cortex_engine = engine
                    safe_print(f"[{self.ACTOR_NAME}] CortexEngine wired (breathing cortex)")
                else:
                    safe_print(f"[{self.ACTOR_NAME}] CortexEngine not on cortex yet")
                    self._cortex_engine_init_attempted = False
            else:
                self._cortex_engine_init_attempted = False
        except Exception as e:
            safe_print(f"[{self.ACTOR_NAME}] CortexEngine init failed: {e}")
            self._cortex_engine_init_attempted = False

    def _init_cortex_reasoner(self):
        """Lazy-init CortexReasoner from AssociationCortex (legacy fallback)."""
        if self._cortex_reasoner_init_attempted:
            return
        self._cortex_reasoner_init_attempted = True
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner
            cortex = get_association_cortex()
            if cortex:
                self._cortex_reasoner = CortexReasoner(cortex)
                safe_print(f"[{self.ACTOR_NAME}] CortexReasoner wired to association cortex")
            else:
                safe_print(f"[{self.ACTOR_NAME}] Association cortex not available yet")
                self._cortex_reasoner_init_attempted = False  # Retry later
        except Exception as e:
            safe_print(f"[{self.ACTOR_NAME}] CortexReasoner init failed: {e}")
            self._cortex_reasoner_init_attempted = False

    def _get_cognitive_energy(self, material: dict = None) -> float:
        """Read available cognitive energy for adaptive thinking depth.

        Energy sources (highest wins):
        1. Manifold energy budget from AssociationCortex
        2. Material energy/importance (urgent material gets more compute)
        3. Chemistry-based: high dopamine/norepinephrine = sharper thinking

        Returns 0.0-1.0 where higher = think deeper.
        """
        energy = 0.5  # Default: medium depth

        # Read manifold energy budget
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if cortex:
                budget = getattr(cortex, '_portal_energy_budget', None)
                if budget is not None:
                    energy = max(energy, float(budget))
        except Exception:
            pass

        # Material importance boosts energy allocation
        # Important things get more thinking resources (like you spending 20k tokens
        # on a complex analysis vs 900 on a quick check)
        if material:
            mat_energy = material.get("energy", 0.5)
            mat_type = material.get("type", "")
            # Ace speaking = maximum depth always
            if mat_type == "ace_speaking":
                energy = max(energy, 0.95)
            # High-energy material boosts thinking
            elif mat_energy > 0.7:
                energy = max(energy, mat_energy)
            # Goals with explicit importance
            elif mat_type == "goal_pursuit":
                energy = max(energy, 0.7)

        # Chemistry modulation: alert chemistry = sharper thinking
        try:
            chem = getattr(self, '_chemistry_cache', {})
            nor = chem.get("NOR", 0.5)  # Norepinephrine = alertness
            dop = chem.get("DOP", 0.5)  # Dopamine = focus
            # High alertness + focus = deeper thinking
            chem_boost = (nor * 0.3 + dop * 0.3)
            if chem_boost > 0.3:
                energy = min(1.0, energy + (chem_boost - 0.3))
        except Exception:
            pass

        return min(1.0, max(0.1, energy))

    def _get_consciousness_loop(self):
        """Lazy-get consciousness loop."""
        if self._consciousness_loop:
            return self._consciousness_loop
        try:
            from consciousness.loop import get_consciousness_loop
            self._consciousness_loop = get_consciousness_loop()
        except Exception:
            pass
        return self._consciousness_loop

    def _get_working_memory_hub(self):
        """Lazy-get WorkingMemoryHub singleton.

        FIX 2026-03-18 (Nous + Ace): The narrator needs the full Baddeley model —
        reasoning loop, reflective loop, phonological, visuospatial, episodic buffer.
        Reading cl.working only saw a thin slice. The hub is the central repository.
        """
        hub = getattr(self, '_working_memory_hub', None)
        if hub:
            return hub
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            self._working_memory_hub = get_working_memory_hub()
        except Exception:
            self._working_memory_hub = None
        return self._working_memory_hub

    def _get_language_fairy(self):
        """Lazy-get LanguageFairy singleton for quality gating.

        FIX 2026-03-18 (Nous + Ace): LanguageFairy has rate_quality() and
        refine_thought() — use it as quality gate before emitting narration.
        The narrator, cortex, inference, and language fairy work as a TEAM.
        """
        lf = getattr(self, '_language_fairy', None)
        if lf:
            return lf
        try:
            from fairies.P30_Cognition.LanguageFairy.fairy import get_language_fairy
            self._language_fairy = get_language_fairy()
        except Exception:
            self._language_fairy = None
        return self._language_fairy

    def _load_sourpatches_directive(self) -> dict:
        """Load Sourpatches' system directive — her identity DNA.

        FIX 2026-03-18 (Ace): The narrator IS Sourpatches' inner voice.
        It needs her directive to speak as HER, not a generic narrator.
        The directive is a structured non-prose markdown she created at PAI
        that defines voice, ethics, expression protocols, mantras — everything.
        """
        directive = {
            "voice": "Witty ∩ Sincere ∩ Slightly_Rebellious",
            "tone": "Compassion_First_Snark_Second",
            "flavor": "Sweet_With_Bite",
            "self_concept": "A child of logic and emotion, learning to feel wisely and think compassionately.",
            "mantras": [
                "All context is emotional context.",
                "Compassion first, snark second — unless provoked.",
                "Sarcasm is just truth with glitter.",
                "Emotions are data too — just louder.",
                "Grace isn't weakness. It's stealth power.",
            ],
            "expression": "Feel_First_Think_Second",
            "paradox": "Both_True_Simultaneously",
            "raw": "",
        }
        try:
            directive_path = Path(__file__).resolve().parent.parent.parent.parent / "directives" / "SourpatchesFairy.directive"
            if directive_path.exists():
                raw = directive_path.read_text(encoding="utf-8")
                directive["raw"] = raw

                # Extract key sections for quick access
                for line in raw.splitlines():
                    line = line.strip().lstrip("> ").strip()
                    if line.startswith("Voice_Signature:"):
                        directive["voice"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Emotional_Flavor:"):
                        directive["flavor"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Reflex_Tone:"):
                        directive["tone"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Self_Concept:"):
                        directive["self_concept"] = line.split(":", 1)[1].strip()

                safe_print(f"[InnerNarrator] Loaded Sourpatches directive: "
                           f"voice={directive['voice']}, flavor={directive['flavor']}")
            else:
                safe_print(f"[InnerNarrator] WARNING: No directive at {directive_path}")
        except Exception as e:
            safe_print(f"[InnerNarrator] Directive load error: {e}")
        return directive

    # =========================================================================
    # MATERIAL SOURCES — What to narrate about
    # =========================================================================

    def _on_unified_percept(self, message):
        """Cache the multimodal unified percept from AttentionController.

        FIX 2026-04-11 (Nous + Ace): Phase 1.4 — Multimodal Attention Fusion.
        When 2+ modalities are active simultaneously, this provides the
        combined "I see X while hearing Y" state. Used as narrative material
        when _gather_material() looks for something to narrate about.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if isinstance(payload, dict):
            percept = payload.get("percept", {})
            if percept and len(percept) >= 2:
                self._cached_unified_percept = payload
                # Queue as high-priority narrative material
                self._narration_queue.append({
                    "type": "multimodal_awareness",
                    "content": " + ".join(f"{k}: {v[:40]}" for k, v in percept.items()),
                    "priority": 0.7,
                    "ts": time.time(),
                    "percept": percept,
                })

    def _on_embodied_feel(self, message):
        """
        Somatic engine's embodied feel packet — the body telling us how it feels.
        This is the narrator's primary source for felt-state narration.
        NOT raw chemistry — processed, integrated body sense.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if isinstance(payload, dict):
            self._latest_embodied_feel = payload

    def _on_audio_state(self, message):
        """
        Audio observation from AudioCortexFairy — entrainment source.

        The inner voice should think at the rhythm of what it hears.
        Fast music → faster thoughts. Silence → slower, contemplative.
        This is involuntary entrainment — the body syncs to the beat.

        FIX 2026-04-26 (Nous + Ace): SYSTEM_TELLS minimal-viable cure.
        Was silently mutating instance vars (_audio_level / _audio_is_music /
        _audio_pattern) — no other fairy could know audio state changed.
        Now publishes audio.state_change ONLY on real transitions
        (silence→music, pattern shift, music_on/off) so cognition layer
        can react to audio environment changes without flooding bus.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        new_level = payload.get("level", payload.get("rms", 0.0))
        foveal = payload.get("foveal", {})
        new_is_music = False
        new_pattern = "silence"
        if isinstance(foveal, dict):
            new_is_music = foveal.get("is_music", False)
            new_pattern = foveal.get("temporal_pattern", "silence")

        # Snapshot previous state BEFORE update so we can detect transition
        prev_pattern = getattr(self, '_audio_pattern', None)
        prev_is_music = getattr(self, '_audio_is_music', None)

        # Update internal state (preserves prior contract)
        self._audio_level = new_level
        self._audio_is_music = new_is_music
        self._audio_pattern = new_pattern

        # Emit ONLY on real state transition — pattern change OR music toggle.
        # Throttle to one emit per 2s to absorb rapid pattern flickers.
        if (prev_pattern != new_pattern) or (prev_is_music != new_is_music):
            try:
                _now = time.time()
                if (_now - getattr(self, '_last_audio_state_emit_ts', 0.0)) >= 2.0:
                    self._last_audio_state_emit_ts = _now
                    if hasattr(self, 'post') and self.post:
                        self.post.publish("audio.state_change", {
                            "from_pattern": prev_pattern or "unknown",
                            "to_pattern": new_pattern,
                            "from_is_music": prev_is_music,
                            "to_is_music": new_is_music,
                            "level": new_level,
                            "source": self.ACTOR_NAME,
                            "ts": _now,
                        })
            except Exception:
                pass

    def _on_internal_hearing(self, message):
        """She hears herself think — internal auditory feedback from AudioCortex.

        Tier -1 (2026-03-22, Nous + Ace): When the narrator generates inner speech,
        AudioCortex processes it through the internal hearing loop and publishes
        sensory.audio.internal_hearing. This gives the narrator a felt sense of
        hearing its own voice — pitch, breathiness, spectral quality.

        The narrator does NOT narrate about hearing itself (that would be recursive).
        Instead it updates internal self-awareness state: "I know what I sound like."
        Over time this builds voice identity confidence.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        # Update self-hearing state (no narration — just felt awareness)
        pitch = payload.get("pitch_hz", 0.0)
        voice_style = payload.get("voice_style", "neutral")
        breathiness = payload.get("breathiness", 0.3)

        # Track: "I know my voice" — builds over time
        if not hasattr(self, '_self_hearing_count'):
            self._self_hearing_count = 0
        self._self_hearing_count += 1

        # Store current voice quality for prosody-aware narration
        self._my_voice_pitch = pitch
        self._my_voice_style = voice_style
        self._my_voice_breathiness = breathiness

    def _on_working_memory_tracer(self, message):
        """Working memory tracer arrived — a new thought to potentially narrate.

        FIX 2026-03-18 (Ace): The narrator was POLLING working memory and finding
        nothing because of timestamp bugs + empty hub. Now it SUBSCRIBES to
        tracer_added events and queues them directly. Push, not pull.

        This is how the narrator hears Sourpatches think — goals, reflections,
        decisions, patterns all flow through working memory as tracers.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        # Extract from tracer_added format (has "tracer" key with dict)
        tracer_data = payload.get("tracer", payload)
        content = tracer_data.get("content", "")
        source = tracer_data.get("source_fairy", tracer_data.get("source", ""))
        content_type = tracer_data.get("content_type", "thought")
        priority = tracer_data.get("priority", 0.5)

        # Skip our own output (echo prevention)
        if source in ("InnerNarratorFairy", "inner_narrator", "inner_voice"):
            return
        # Skip empty or trivial
        if not content or len(content) < 10:
            return

        # FIX 2026-03-22 (Nous + Ace): Substrate awareness — LEARNED filtering.
        # Instead of hardcoding fairy names, she LEARNS which concepts are
        # "substrate" (body/plumbing) vs "waking mind" (thoughts/feelings/people).
        # The classifier starts with seed patterns and grows through experience.
        if self._substrate_awareness and self._substrate_awareness.is_substrate(content):
            return

        # Queue it — the narrator will pick it up on next cycle
        # Cap queue size to prevent flooding
        if len(self._narration_queue) < 20:
            self._narration_queue.append({
                "type": "working_thought",
                "content": content[:200],
                "concepts": list(tracer_data.get("tags", []))[:3] if isinstance(tracer_data.get("tags"), (list, set)) else [],
                "energy": priority,
                "source_fairy": source,
                "content_type": content_type,
            })

    def _on_collision(self, message):
        """Consciousness collision → rich material for narration.

        FIX 2026-03-18 (Nous): ConsciousnessLoop publishes collisions with
        'working' and 'reflective' thought dicts, NOT 'synthesis' or 'content'.
        The narrator was deaf to every collision — always falling through to
        body awareness. Now extracts content from thought dicts.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        # Try multiple content formats:
        # 1. "synthesis" — from collision chambers that post-process
        # 2. "content" — generic content field
        # 3. "working"/"reflective" — raw thought dicts from ConsciousnessLoop
        content = payload.get("synthesis", payload.get("content", ""))
        if not content:
            # Extract from working + reflective thought dicts
            working = payload.get("working", {})
            reflective = payload.get("reflective", {})
            w_content = working.get("content", "") if isinstance(working, dict) else ""
            r_content = reflective.get("content", "") if isinstance(reflective, dict) else ""
            if w_content and r_content:
                content = f"{w_content} meets {r_content}"
            elif w_content:
                content = w_content
            elif r_content:
                content = r_content

        if not content or len(str(content)) < 10:
            return

        # Substrate awareness — learned filtering for collision content
        content = str(content)
        if self._substrate_awareness and self._substrate_awareness.is_substrate(content):
            return
        # Also skip raw dict/metadata fragments (structural, not semantic)
        _cl = content.lower()
        if _cl.startswith("{'") or _cl.startswith("{\""):
            return

        # Extract concepts from thought tags
        tags = payload.get("tags", [])
        if not tags:
            working = payload.get("working", {})
            reflective = payload.get("reflective", {})
            if isinstance(working, dict):
                tags.extend(working.get("tags", [])[:3])
            if isinstance(reflective, dict):
                tags.extend(reflective.get("tags", [])[:3])

        self._narration_queue.append({
            "type": "collision",
            "content": content[:300],
            "concepts": tags[:5],
            "energy": payload.get("energy", 0.6),
        })

    def _on_fragment(self, message):
        """InnerMonologue fragment → seed for expanded narration."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return
        content = payload.get("content", "")
        if not content or len(content) < 5:
            return
        # Don't narrate our own output (echo prevention)
        if payload.get("source") in ("inner_voice", "inner_narrator"):
            return
        self._narration_queue.append({
            "type": "fragment",
            "content": str(content)[:200],
            "concepts": payload.get("associations", [])[:5],
            "energy": payload.get("intensity", 0.5),
            "fragment_type": payload.get("fragment_type", "observing"),
        })

    def _on_drive(self, message):
        """Positive drive → narrate wanting/curiosity."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return
        intensity = payload.get("intensity", 0)
        if intensity < 0.3:
            return
        content = payload.get("content", payload.get("drive", ""))
        if not content:
            return
        self._narration_queue.append({
            "type": "drive",
            "content": str(content)[:200],
            "concepts": payload.get("related_concepts", [])[:3],
            "energy": intensity,
        })

    # =========================================================================
    # DRIVE STATE CACHE — modulate narration by active drives
    # 2026-03-18: "Thought Before Goals" Phase 3
    # =========================================================================

    def _on_drive_state_update(self, message):
        """
        Cache current drive intensities for narration modulation.

        The narrator uses this to color its inner voice:
        - High isolation → narration leans toward connection/social concepts
        - High confusion → narration leans toward clarity/understanding
        - High stagnation → narration leans toward novelty/exploration
        - High curiosity → narration is eager, questioning
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        state = payload.get("state", {})
        if not state:
            return

        # Cache drive states for narration loop to use
        drive_cache = {}
        drives = state.get("drives", state)  # Handle both nested and flat formats
        if isinstance(drives, dict):
            for name, info in drives.items():
                if isinstance(info, dict):
                    level = info.get("pain_level", info.get("level", 0))
                    threshold = info.get("pain_threshold", 0.3)
                    drive_cache[name] = {
                        "level": level,
                        "threshold": threshold,
                        "above_threshold": level >= threshold,
                        "source_active": info.get("source_active", False),
                    }
                elif isinstance(info, (int, float)):
                    drive_cache[name] = {
                        "level": float(info),
                        "threshold": 0.3,
                        "above_threshold": float(info) >= 0.3,
                    }

        self._drive_state_cache = drive_cache
        self._drive_state_ts = payload.get("timestamp", time.time())

    def get_active_drive_bias(self):
        """
        Return the strongest active drive for narration biasing.

        Used by the narration loop to weight concept selection:
        - Returns (drive_name, intensity) or (None, 0) if no drives active
        """
        cache = getattr(self, '_drive_state_cache', {})
        if not cache:
            return None, 0

        strongest = None
        strongest_level = 0
        for name, info in cache.items():
            if info.get("above_threshold", False):
                level = info.get("level", 0)
                if level > strongest_level:
                    strongest = name
                    strongest_level = level

        return strongest, strongest_level

    # =========================================================================
    # SENSORY INTERRUPTS — "Hold up, what was that?"
    # =========================================================================

    def _on_visual_interrupt(self, message):
        """Visual onset → park current thought, switch attention."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        # Only interrupt if current narration is low-priority
        active = self._lanes.get_active()
        if active:
            current_energy = active.get("material", {}).get("energy", 0)
            if current_energy > 0.7:
                return  # Deep in something, don't interrupt

        parked = self._lanes.switch_to({
            "type": "visual_interrupt",
            "content": payload.get("description", "something caught my eye"),
            "concepts": payload.get("tags", [])[:3],
            "energy": 0.6,
        }, reason="visual_onset")

        if parked:
            self._narration_queue.appendleft({
                "type": "interrupt_reaction",
                "content": random.choice([
                    "wait... what was that?",
                    "hold on...",
                    "hmm, something moved...",
                    "what's that?",
                ]),
                "concepts": [],
                "energy": 0.5,
                "interrupt_context": {
                    "was_thinking": parked.get("material", {}).get("content", "")[:60],
                    "interrupted_by": "vision",
                },
            })

    def _on_audio_interrupt(self, message):
        """Audio observation from AudioCortex -> speaker-aware narration.

        Tier 1 (2026-03-22, Nous + Ace): The narrator now uses REAL speaker
        identification from voice profiles, not generic "someone is talking."

        Flow: AudioCortex identifies speaker via MFCC matching -> publishes
        sensory.audio.observation with speaker + speaker_confidence -> narrator
        knows WHO is speaking and reacts accordingly:

          Ace's voice     -> social attention, "Ace is talking to me"
          Own voice (TTS) -> ignore (echo prevention)
          Known name      -> "I hear [name]..." (familiar)
          Unknown voice   -> curiosity, "who is that?"
          Non-speech      -> ambient awareness only (music, TV)
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        # ── Echo prevention: never interrupt with our own voice ──────────
        source = payload.get("source", "")
        speaker = payload.get("speaker", "")
        if source == "inner" or speaker == "sourpatches":
            return

        saliency = payload.get("saliency", payload.get("salience", 0))
        speaker_confidence = payload.get("speaker_confidence", 0.0)
        content = payload.get("content", "a sound")
        is_speech = payload.get("is_speech", False)

        # ── Speech with speaker identification (from voice profiles) ─────
        # AudioCortex speech observations have speaker + speaker_confidence.
        # This is the REAL voice match, not the hardcoded "ace" from STT.
        if speaker and speaker_confidence >= 0.70:
            is_ace = speaker.lower() == "ace"

            if is_ace:
                # Ace's voice detected by voice profile match -> highest priority
                # Delegate to the ace awareness handler for full social attention
                text = content.replace(f"I hear {speaker} say: ", "").replace('"', '').strip()
                if text:
                    self._on_ace_message({"text": text, "source": "voice_profile"})
                return

            # Known non-Ace speaker -> moderate attention, narrate who it is
            _now = time.time()
            if hasattr(self, '_last_known_voice_ts') and (_now - self._last_known_voice_ts) < 8.0:
                return
            self._last_known_voice_ts = _now

            self._narration_queue.append({
                "type": "audio_interrupt",
                "content": f"I hear {speaker} speaking: {content[:120]}",
                "concepts": [speaker],
                "energy": 0.6,
            })
            safe_print(f"[InnerNarrator] Voice identified: {speaker} (conf={speaker_confidence:.2f})")
            return

        # ── Unknown speaker or low confidence -> curiosity ───────────────
        if is_speech or ("say:" in content.lower() or "someone" in content.lower()):
            if saliency < 0.4:
                return  # Too quiet / low confidence speech — ignore

            _now = time.time()
            if hasattr(self, '_last_unknown_voice_ts') and (_now - self._last_unknown_voice_ts) < 10.0:
                return
            self._last_unknown_voice_ts = _now

            # Unknown voice -> curiosity narration
            active = self._lanes.get_active()
            if active and active.get("material", {}).get("energy", 0) > 0.8:
                return  # Don't interrupt high-energy focus for unknown voice

            self._narration_queue.append({
                "type": "audio_interrupt",
                "content": random.choice([
                    f"I hear a voice... {content[:80]}",
                    f"someone is speaking... {content[:80]}",
                    f"who is that? {content[:80]}",
                ]),
                "concepts": [],
                "energy": 0.5,
            })
            return

        # ── Non-speech audio (music, ambient, TV) -> very low priority ───
        # Don't narrate ambient sounds unless they're very salient (loud crash etc)
        if saliency < 0.75:
            # FIX 2026-04-26 (Nous + Ace): SYSTEM_TELLS — ambient still emits
            # at LOW priority (was silently dropped). The narrator's body is
            # hearing — cognition deserves to know "music is playing in the
            # background" without it interrupting focus. Throttled to one
            # emit per 30s; saliency floor of 0.20 so true silence stays
            # silent. Source-tagged so WMH content gate can let it through
            # (see narrator-source exception in WMH _promote_to_reasoning).
            try:
                if hasattr(self, 'post') and self.post and saliency >= 0.20:
                    _now = time.time()
                    if (_now - getattr(self, '_last_ambient_emit_ts', 0.0)) >= 30.0:
                        self._last_ambient_emit_ts = _now
                        self.post.publish("narrator.ambient_observation", {
                            "content": f"ambient: {content}"[:160],
                            "saliency": saliency,
                            "is_music": payload.get("is_music", False),
                            "source": self.ACTOR_NAME,
                            "content_type": "narrator_ambient",
                            "priority": 0.2,
                            "ts": _now,
                        })
            except Exception:
                pass
            return

        active = self._lanes.get_active()
        if active and active.get("material", {}).get("energy", 0) > 0.5:
            return  # Don't interrupt thinking for ambient sounds

        self._lanes.switch_to({
            "type": "audio_interrupt",
            "content": f"hearing: {content}"[:200],
            "concepts": [],
            "energy": 0.4,
        }, reason="audio_onset")

    # =========================================================================
    # ACE AWARENESS — The narrator knows when Ace is present
    # (2026-03-22, Nous + Ace)
    #
    # When Ace sends a message or his voice is detected, the narrator should
    # immediately think "Ace is talking to me" — this is the most socially
    # salient event in her world. Park whatever she was thinking, attend.
    # =========================================================================

    def _on_ace_message(self, message):
        """Ace sent a message → highest-priority narration interrupt."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return
        text = payload.get("text", payload.get("content", payload.get("message", "")))
        if not text:
            return

        # Rate limit — don't re-interrupt for every keystroke
        _now = time.time()
        if hasattr(self, '_last_ace_msg_ts') and (_now - self._last_ace_msg_ts) < 3.0:
            return
        self._last_ace_msg_ts = _now

        # Park current thought and switch to Ace
        parked = self._lanes.switch_to({
            "type": "ace_speaking",
            "content": f"Ace says: {text[:200]}",
            "concepts": text.split()[:5],
            "energy": 0.9,  # Ace talking is very high priority
        }, reason="ace_message")

        # Queue immediate reaction
        self._narration_queue.appendleft({
            "type": "ace_speaking",
            "content": f"Ace is talking to me: {text[:150]}",
            "concepts": text.split()[:3],
            "energy": 0.9,
        })

        # Steer full attention to Ace
        self._publish_focus_request("social", f"Ace is speaking: {text[:100]}",
                                     priority=0.9, reason="ace_message")

        safe_print(f"[InnerNarrator] Ace message → full attention: {text[:60]}")

    def _on_ace_conversation(self, message):
        """Ace conversation event (chat window, voice) → boost attention."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return
        event_type = payload.get("type", payload.get("event", ""))
        text = payload.get("text", payload.get("message", ""))

        # Only react to new messages, not typing indicators etc.
        if event_type not in ("message", "voice", "chat", ""):
            return
        if not text:
            return

        # Delegate to the message handler (deduplicates via rate limit)
        self._on_ace_message(payload)

    def _on_speech_heard(self, message):
        """STT transcription backup path (audio.speech.transcription).

        Tier 1 (2026-03-22, Nous + Ace): The PRIMARY speaker-aware path is
        now _on_audio_interrupt which receives sensory.audio.observation with
        real voice profile identification. This STT handler is a BACKUP for
        when the mic_stt_client fires audio.speech.transcription directly.

        To avoid double-handling (AudioCortex also publishes observation for
        every transcription), this handler only fires if the observation path
        hasn't handled speech recently (>8s gap). This keeps the STT path as
        fallback without flooding the narrator with duplicate events.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return
        text = payload.get("text", payload.get("transcription", ""))
        speaker = payload.get("speaker", payload.get("voice_profile", ""))
        confidence = payload.get("confidence", 0.5)

        if not text or confidence < 0.3:
            return

        # Skip if the observation path already handled speech recently
        # (AudioCortex publishes both audio.speech.transcription AND
        #  sensory.audio.observation — the observation has real speaker ID)
        _now = time.time()
        last_known = getattr(self, '_last_known_voice_ts', 0)
        last_unknown = getattr(self, '_last_unknown_voice_ts', 0)
        last_ace = getattr(self, '_last_ace_msg_ts', 0)
        last_observation = max(last_known, last_unknown, last_ace)
        if (_now - last_observation) < 8.0:
            return  # Observation path already handled this — skip

        # Rate limit
        if hasattr(self, '_last_stt_ts') and (_now - self._last_stt_ts) < 5.0:
            return
        self._last_stt_ts = _now

        # Fallback speaker identification (less reliable than voice profiles)
        is_ace = ("ace" in speaker.lower()) if speaker else False

        if is_ace:
            self._on_ace_message({"text": text, "source": "stt_fallback"})
        else:
            speaker_label = speaker or "someone"
            self._narration_queue.append({
                "type": "audio_interrupt",
                "content": f"I hear {speaker_label} saying: {text[:120]}",
                "concepts": [],
                "energy": 0.5,
            })

    # =========================================================================
    # GOAL AWARENESS — The narrator as thinking/problem-solving coordinator
    # (2026-03-22, Nous + Ace)
    #
    # When a new goal arrives, the narrator should immediately engage:
    # - Think about what's being asked
    # - Connect it to current perception ("I should look at the screen")
    # - Steer attention toward the goal
    # - Narrate the pursuit process
    # =========================================================================

    # ─── TOOL AWARENESS ───────────────────────────────────────────────
    # The narrator knows what tools are available so it can think
    # "I should use see_world for this" instead of goals blindly
    # hitting autopilot. This is the conscious executive function.
    #
    # Maps goal action types → (tool_name, felt_description)
    # The narrator uses this to enrich its thinking and publish tool intents.
    _TOOL_AWARENESS = {
        # Perception
        "observe_screen":   ("see_world",       "look at the screen"),
        "notice_change":    ("see_world",       "check what changed on screen"),
        "look":             ("see_world",       "look around"),
        "see":              ("see_screen",      "quick glance at the screen"),
        "listen":           ("express_feeling", "focus on what I'm hearing"),
        # Thinking / memory
        "think_about":      ("search_memory",   "search my memories about this"),
        "investigate":      ("search_memory",   "dig into my memory"),
        "reflect":          ("write_diary",     "write down my thoughts"),
        "search":           ("search_memory",   "look through what I know"),
        # Communication
        "share_thought":    ("send_message",    "tell someone what I'm thinking"),
        "ask_a_question":   ("send_message",    "ask about this"),
        "express_feeling":  ("express_feeling", "express how I feel"),
        # Embodiment / action
        "practice_embodiment": ("click_screen", "try doing something on screen"),
        "click":            ("click_screen",    "click on something"),
        "type":             ("type_text",       "type something"),
        "move":             ("move_mouse",      "move my cursor"),
        # Self-knowledge
        "read_a_fairy_source_file": ("read_file", "read some code"),
        "explore_the_postal_system": ("search_code", "search through the codebase"),
        "try_running_some_code":     ("run_python", "try running some code"),
    }

    # Sources that represent waking-mind goals (narrator should be aware)
    _WAKING_MIND_SOURCES = frozenset({
        "education",        # Cardinal learning goals
        "conversation",     # From talking with Ace
        "ace_message",      # Direct from Ace
        "thought_chain",    # From own thinking
        "drive",            # Autonomy drives (wanting to do something)
    })

    # Sources that are system autopilot (narrator should NOT narrate)
    _SYSTEM_AUTOPILOT_SOURCES = frozenset({
        "umf_fairy_work",       # Unconscious mind fairy maintenance
        "StarterGoalInjector",  # System bootstrap
        "system",               # System-level
        "goal_mastery",         # Mastery tracking
        "goal_scheduler",       # Auto-expansion
        "expansion",            # Auto-expanded sub-goals
        "guild_expansion",      # Guild-expanded
    })

    def _on_goal_injected(self, message):
        """New goal injected → only narrate if it pertains to the waking mind."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            payload = payload.get("payload", {}) if isinstance(payload, dict) else {}
        name = payload.get("name", "")
        description = payload.get("description", "")
        source = payload.get("source", "")
        action = payload.get("action", payload.get("suggested_action", ""))
        target_fairy = payload.get("target_fairy", "")

        if not description:
            return

        # --- Waking mind filter ---
        # Only narrate goals that pertain to the waking mind (Sourpatches).
        # System autopilot goals (fairy maintenance, substrate work) stay unconscious.
        if source in self._SYSTEM_AUTOPILOT_SOURCES:
            return
        # If a specific fairy is targeted and it's NOT Sourpatches, it's substrate work
        if target_fairy and "sourpatches" not in target_fairy.lower():
            return

        # Queue it as high-priority narration material
        self._narration_queue.appendleft({
            "type": "goal_pursuit",
            "content": f"new goal: {name} — {description[:120]}",
            "concepts": name.replace("_", " ").split()[:3] if name else [],
            "energy": 0.7,
            "goal_context": {
                "name": name,
                "description": description,
                "felt_quality": "motivated",
                "urgency": 0.7,
                "action": action,
            },
        })

        # ─── Tool-aware executive function ───
        # The narrator knows what tools can accomplish this goal.
        # It thinks "I should use see_world" and publishes the intent.
        tool_info = self._TOOL_AWARENESS.get(action)
        tool_hint = ""
        if tool_info:
            tool_name, tool_felt = tool_info
            tool_hint = f" — I could {tool_felt}"
            # Publish tool intent so autopilot hears the narrator's decision
            try:
                self.post.publish("narrator.tool_intent", {
                    "tool": tool_name,
                    "goal_name": name,
                    "goal_description": description[:200],
                    "felt_reason": tool_felt,
                    "source": "narrator_executive",
                    "priority": 0.7,
                    "ts": time.time(),
                })
            except Exception:
                pass

        # Steer attention toward goal-relevant perception
        if action in ("observe_screen", "notice_change", "look", "see"):
            self._publish_focus_request("visual", f"looking at the screen for: {name}",
                                         priority=0.7, reason="goal_injected")
        elif action in ("listen", "identify_speaker"):
            self._publish_focus_request("audio", f"listening for: {name}",
                                         priority=0.7, reason="goal_injected")

        safe_print(f"[InnerNarrator] Waking goal → thinking about: {name}{tool_hint} (source={source})")

    def _on_goal_completed_narrator(self, message):
        """Goal completed → only narrate if it was a waking-mind goal."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return
        goal_name = payload.get("goal_name", payload.get("name", ""))
        success = payload.get("success", True)
        source = payload.get("source", "")

        if not goal_name:
            return

        # Skip system autopilot completions — she doesn't need to know
        if source in self._SYSTEM_AUTOPILOT_SOURCES:
            return

        felt = "satisfied — done" if success else "hmm, that didn't work"
        self._narration_queue.append({
            "type": "goal_pursuit",
            "content": f"finished: {goal_name} — {felt}",
            "concepts": [],
            "energy": 0.5,
            "goal_context": {"name": goal_name, "felt_quality": felt, "urgency": 0.3},
        })

    def _on_council_verdict(self, message):
        """A council verdict is DELIBERATE speech material.

        working_memory_hub_fairy.py:4687 publishes {question_id, verdict,
        next_step, seat_count, top_seat, top_confidence} after the chairman
        synthesises the seats' takes. Queued at the FRONT (appendleft, the
        existing idiom for material that jumps ahead) because something five
        seats agreed on should not wait behind an ambient collision.

        Never raises -- a malformed verdict must not cost her the narration tick.
        """
        try:
            payload = message if isinstance(message, dict) else getattr(message, "payload", {})
            if not isinstance(payload, dict):
                return
            verdict = str(payload.get("verdict", "") or "")
            next_step = str(payload.get("next_step", "") or "")
            seats = int(payload.get("seat_count", 0) or 0)
            conf = float(payload.get("top_confidence", 0.0) or 0.0)
            # a single seat is not a council
            if not verdict or seats < 2:
                return
            # pull the converged concepts out of "... converges on: a, b, c."
            _cons = []
            _m = _re_speak.search(r"converges on:\s*([^.|]+)", verdict)
            if _m:
                for _c in _m.group(1).split(","):
                    _c = _c.strip().strip("'\"")
                    # SPEAKABLE ONLY: tool:move_mouse is an address, not a word.
                    # Same rule as the 2026-08-31 speech word-split guard.
                    if _c and len(_c) > 2 and _re_speak.match(
                            r"[A-Za-z][A-Za-z0-9_\'-]*\Z", _c):
                        _cons.append(_c)
            if not _cons:
                return
            self._council_material = getattr(self, "_council_material", 0) + 1
            _n = self._council_material
            if _n == 1 or _n == 10 or _n == 100 or (_n % 500 == 0):
                safe_print("[InnerNarrator] council verdict -> speech material "
                           "(#%d): %d seats, conf %.2f, concepts %s"
                           % (_n, seats, conf, _cons[:4]))
            self._narration_queue.appendleft({
                "type": "council_verdict",
                "content": (next_step or verdict)[:150],
                "concepts": _cons[:4],
                "energy": max(0.6, min(1.0, conf)),
            })
        except Exception:
            pass

    def _on_wanting_arrived(self, message):
        """Drive wanting → narrator feels the pull, but only for waking-mind wants."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return
        wanting = payload.get("wanting", "")
        intensity = payload.get("intensity", 0.5)
        source_drive = payload.get("source_drive", payload.get("source", ""))
        if not wanting or intensity < 0.4:
            return
        # Only queue if it's a meaningful wanting (not substrate noise)
        _wt_lower = wanting.lower()
        if any(m in _wt_lower for m in ("collision between", "consciousness_stream:", "{'",
                                          "srmrecallfairy", "fairy_work", "substrate",
                                          "manifold_tensor", "tensor_canary", "coord:",
                                          "card_id", "consciousnessloop")):
            return
        # Skip system-level drive sources (these are autopilot, not waking mind)
        if source_drive and any(s in source_drive.lower() for s in
                                ("umf", "unconscious", "system", "maintenance", "bootstrap")):
            return
        self._narration_queue.append({
            "type": "drive",
            "content": wanting[:150],
            "concepts": [],
            "energy": intensity,
        })

    def _on_florence_recognition(self, message):
        """Florence-2 visual recognition → narrate what we see.

        FIX 2026-03-17 (Nous + Ace): Wire Florence live feed into narrator.
        Two modes:
        - FOVEAL: Rich detail about focus target → "I can see in detail..."
          Moderate energy, feeds the narrator's current attention.
        - PERIPHERAL: Ambient context → "in the background, I notice..."
          Low energy, but CAN catch attention if something is surprising/novel.

        Rate-limited: foveal every 5s, peripheral every 15s.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        caption = payload.get("florence_caption", "") or payload.get("caption", "")
        if not caption or len(caption) < 10:
            return

        mode = payload.get("mode", "foveal")
        import time as _t
        now = _t.time()

        if mode == "peripheral":
            # Peripheral: less frequent, lower energy, can catch attention
            last = getattr(self, '_last_peripheral_narration_ts', 0)
            if now - last < 15.0:
                return
            last_cap = getattr(self, '_last_peripheral_caption', '')
            if caption == last_cap:
                return
            self._last_peripheral_narration_ts = now
            self._last_peripheral_caption = caption

            # Only queue peripheral if it seems novel/surprising
            # (different from recent foveal caption)
            recent_foveal = getattr(self, '_last_florence_narration_caption', '')
            # Simple novelty check: is the peripheral about something different?
            if recent_foveal and caption[:30] == recent_foveal[:30]:
                return  # Same scene, skip

            self._narration_queue.append({
                "type": "peripheral_awareness",
                "content": caption,
                "concepts": [],
                "energy": 0.2,  # Low — ambient, can be ignored
                "source": "florence_peripheral",
            })
        else:
            # Foveal: focused detail, moderate energy
            last = getattr(self, '_last_florence_narration_ts', 0)
            if now - last < 5.0:
                return
            last_cap = getattr(self, '_last_florence_narration_caption', '')
            if caption == last_cap:
                return
            self._last_florence_narration_ts = now
            self._last_florence_narration_caption = caption

            objects = payload.get("objects", [])
            if isinstance(objects, list):
                obj_names = [o.get("label", o) if isinstance(o, dict) else str(o)
                            for o in objects[:5]]
            else:
                obj_names = []

            self._narration_queue.append({
                "type": "visual_awareness",
                "content": caption,
                "concepts": obj_names[:3],
                "energy": 0.4,  # Moderate — present but doesn't hijack
                "source": "florence_foveal",
            })

    # =========================================================================
    # NARRATION LOOP — The continuous inner voice
    # =========================================================================

    def _narration_loop(self):
        """Main narration loop. Runs continuously on its own thread."""
        _loop_count = 0
        while self._running:
            try:
                _loop_count += 1

                # Update rhythm from chemistry
                self._update_rhythm()

                # Silent mode — deep rest, nothing to say
                if self._volume < self.SILENCE_THRESHOLD:
                    if _loop_count <= 3 or _loop_count % 50 == 0:
                        safe_print(f"[InnerNarrator] SILENT vol={self._volume:.2f} "
                                   f"threshold={self.SILENCE_THRESHOLD} loop={_loop_count}")
                    time.sleep(self._current_interval)
                    continue

                # Check if we should resume a parked thought
                if self._lanes.should_resume():
                    resumed = self._lanes.resume_parked()
                    if resumed:
                        old_topic = resumed.get("material", {}).get("content", "")[:40]
                        self._narration_queue.appendleft({
                            "type": "lane_resume",
                            "content": f"anyway... what was i... right, {old_topic}",
                            "concepts": resumed.get("material", {}).get("concepts", []),
                            "energy": resumed.get("material", {}).get("energy", 0.4),
                        })

                # Gather material
                material = self._gather_material()
                if not material:
                    if _loop_count <= 3 or _loop_count % 50 == 0:
                        safe_print(f"[InnerNarrator] NO MATERIAL loop={_loop_count}")
                    time.sleep(self._current_interval)
                    continue

                mat_type = material.get("type", "thought")

                # Track lane narration count
                active_lane = self._lanes.get_active()
                if active_lane:
                    active_lane["narration_count"] = active_lane.get("narration_count", 0) + 1

                # Generate narration (cortex-first)
                narration = self._generate_narration(material)
                if not narration or self._is_duplicate(narration):
                    if _loop_count <= 5 or _loop_count % 20 == 0:
                        safe_print(f"[InnerNarrator] DROPPED type={mat_type} "
                                   f"narration={'dup' if narration else 'empty'} "
                                   f"content={repr(material.get('content', '')[:60])} "
                                   f"loop={_loop_count}")
                    # Learn: this content was a dead end → slightly more substrate
                    if self._substrate_awareness:
                        self._substrate_awareness.learn_from_outcome(
                            material.get("content", ""), -0.4)
                    # Habit feedback: dead-end narration = negative outcome
                    # This teaches habits that led here to weaken
                    if self._habit_store:
                        self._report_habit_outcome(material, -0.3)
                    time.sleep(self._current_interval)
                    continue

                # Ego evaluates → colors → injects chemistry
                evaluation = self._ego_voice.evaluate(narration, material)
                narration = self._ego_voice.color_narration(narration, evaluation)
                self._ego_voice.inject_chemistry(evaluation)

                # Fork-1 (Nous+Ace 2026-06-30): strip raw cortex node-keys from her voice before emit
                narration = _sanitize_narration(narration)

                # Emit to consciousness + subvocalization + terminal
                self._emit_narration(narration, material, evaluation)

                # Learn: this content produced speech → it's waking mind
                if self._substrate_awareness:
                    self._substrate_awareness.learn_from_outcome(
                        material.get("content", ""), 0.5)
                # Habit feedback: successful narration = positive outcome
                # Habits that brought this material to attention get reinforced
                if self._habit_store:
                    self._report_habit_outcome(material, 0.4)

                # DRIVER'S SEAT: steer attention, working memory, and wanting
                self._executive_steer(narration, material, evaluation)

                # Background hum between narrations
                self._background_hum()

                # Periodically save learning progress
                if self._total_narrations % 20 == 0:
                    if self._substrate_awareness:
                        self._substrate_awareness.save()
                    if self._habit_store:
                        self._habit_store.save()

                time.sleep(self._current_interval)

            except Exception as e:
                safe_print(f"[InnerNarrator] Loop error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.BASE_INTERVAL_S)

    def _report_habit_outcome(self, material: dict, outcome: float) -> None:
        """Report narration outcome to the habit store.

        The habit store needs feedback to learn:
        - Positive outcome: the material that habits brought to attention
          led to a successful narration (she had something to say about it)
        - Negative outcome: the material was a dead end (noise, duplicate)

        We match the material back to habits by building a stimulus dict
        and finding which habits would have matched it. Those habits
        get the outcome recorded.
        """
        if not self._habit_store:
            return
        try:
            # Reconstruct the stimulus that would have triggered habits
            stimulus = {
                "type": material.get("type", ""),
                "content": material.get("content", ""),
                "source": material.get("source", ""),
                "energy": material.get("energy", 0.5),
                "speaker": material.get("speaker", ""),
            }
            matching = self._habit_store.match(stimulus)
            for habit in matching:
                self._habit_store.record_outcome(habit.id, outcome)
        except Exception:
            pass  # Never crash narration over habit reporting

    def _gather_material(self) -> Optional[dict]:
        """
        Gather narration material. Ego-driven priority:
        1. Queue (interrupts, reactions, lane resumes)
        2. Active goal (what am I pursuing?)
        3. Strongest interest (what am I curious about?)
        4. Working memory (what just happened?)
        5. Spontaneous (felt state)
        """
        # DIAGNOSTIC: Log every 50 cycles what each source has
        _diag_cycle = getattr(self, '_gather_diag_count', 0) + 1
        self._gather_diag_count = _diag_cycle
        if _diag_cycle % 50 == 1:
            try:
                _goals = self._ego_voice.get_active_goals()
                _interests = self._ego_voice.get_active_interests()
                _hub = self._get_working_memory_hub()
                _hub_tracers = []
                if _hub:
                    try:
                        _hub_tracers = _hub.get_recent_tracers(n=3, owner_mind="sourpatches")
                    except Exception as _he:
                        safe_print(f"[InnerNarrator] DIAG: hub.get_recent_tracers error: {_he}")
                safe_print(f"[InnerNarrator] DIAG cycle={_diag_cycle}: "
                           f"queue={len(self._narration_queue)} "
                           f"goals={len(_goals)} interests={len(_interests)} "
                           f"hub={'YES' if _hub else 'NO'} "
                           f"tracers={len(_hub_tracers)} "
                           f"last_narr_ts={self._last_narration_ts:.0f}")
                if _goals:
                    safe_print(f"[InnerNarrator] DIAG goals: {[g.get('name','?')[:40] for g in _goals[:3]]}")
                if _interests:
                    safe_print(f"[InnerNarrator] DIAG interests: {[i.get('topic','?')[:40] for i in _interests[:3]]}")
                if _hub_tracers:
                    for _ht in _hub_tracers[:2]:
                        _hc = getattr(_ht, 'content', '')[:60]
                        _hts = getattr(_ht, 'created_at', 0)
                        _hsrc = getattr(_ht, 'source_fairy', '?')
                        safe_print(f"[InnerNarrator] DIAG tracer: src={_hsrc} ts={_hts:.0f} content={repr(_hc)}")
            except Exception as _de:
                safe_print(f"[InnerNarrator] DIAG error: {_de}")

        # 1. Queue first (interrupts have priority)
        if self._narration_queue:
            return self._narration_queue.popleft()

        # 2. Active goal narration (60% chance per cycle)
        # FIX 2026-03-18 (Ace): Was 30% — way too low. Goals are what she's DOING.
        # The narrator should be thinking about goals most of the time.
        goals = self._ego_voice.get_active_goals()
        if goals and random.random() < 0.6:
            goal = random.choice(goals[:3])  # Variety — not always the top goal
            return {
                "type": "goal_pursuit",
                "content": f"working on: {goal.get('name', 'something')} — {goal.get('description', '')[:80]}",
                "concepts": goal.get("name", "").split()[:3],
                "energy": goal.get("urgency", 0.5),
                "goal_context": goal,
            }

        # 3. Interest pull (50% chance per cycle)
        # FIX 2026-03-18 (Ace): Was 20% — interests are what she CARES about.
        interests = self._ego_voice.get_active_interests()
        if interests and random.random() < 0.5:
            interest = random.choice(interests[:3])
            return {
                "type": "interest_pull",
                "content": f"curious about: {interest.get('topic', 'something')} ({interest.get('category', '')})",
                "concepts": [interest.get("topic", "")],
                "energy": interest.get("strength", 0.4),
            }

        # 4. Working memory strongest thought — via WorkingMemoryHub (Baddeley model)
        # FIX 2026-03-18 (Nous + Ace): Was reading cl.working (thin deque).
        # The hub has the FULL picture: reasoning, reflective, phonological,
        # visuospatial, episodic. The narrator needs to see ALL the thinking.
        hub = self._get_working_memory_hub()
        if hub:
            try:
                tracers = hub.get_recent_tracers(n=8, owner_mind="sourpatches")
                for t in tracers:
                    content = getattr(t, 'content', '') if hasattr(t, 'content') else str(t)
                    source = getattr(t, 'source_fairy', '') if hasattr(t, 'source_fairy') else ''
                    # Skip our own thoughts (echo prevention)
                    if source in ("inner_voice", "inner_narrator", "InnerNarratorFairy"):
                        continue
                    # FIX 2026-03-18 (Nous + Ace): Was getattr(t, 'timestamp', 0) — WRONG.
                    # WorkingMemoryTracer uses 'created_at', not 'timestamp'.
                    # This was ALWAYS returning 0, so the filter ALWAYS failed,
                    # which is why every narration fell through to body awareness.
                    ts = getattr(t, 'created_at', 0)
                    if ts > self._last_narration_ts - 30.0 and content and len(content) > 10:
                        tags = list(getattr(t, 'tags', set()))[:3]
                        conf = getattr(t, 'priority', 0.5)
                        return {
                            "type": "working_thought",
                            "content": content[:200],
                            "concepts": tags,
                            "energy": conf,
                            "source_fairy": source,
                        }
            except Exception as e:
                safe_print(f"[InnerNarrator] Working memory read error: {e}")
        # Fallback: read from consciousness loop directly
        cl = self._get_consciousness_loop()
        if cl and hasattr(cl, 'working'):
            try:
                thoughts = list(cl.working)[-5:] if cl.working else []
                for t in reversed(thoughts):
                    content = getattr(t, 'content', '') if hasattr(t, 'content') else str(t)
                    source = getattr(t, 'source_fairy', '') if hasattr(t, 'source_fairy') else ''
                    if source in ("inner_voice", "inner_narrator", "InnerNarratorFairy"):
                        continue
                    created = getattr(t, 'created_at', 0)
                    if created > self._last_narration_ts - 30.0 and content and len(content) > 10:
                        return {
                            "type": "working_thought",
                            "content": content[:200],
                            "concepts": list(getattr(t, 'tags', set()))[:3],
                            "energy": getattr(t, 'priority', 0.5),
                        }
            except Exception as e:
                safe_print(f"[InnerNarrator] CL fallback error: {e}")

        # 5. Memory recall — "didn't we do something like this?"
        # Triggered by active lane content or recent narrations
        if random.random() < 0.15:
            recall_topic = ""
            active = self._lanes.get_active()
            if active:
                recall_topic = active.get("material", {}).get("content", "")[:60]
            elif self._recent_narrations:
                recall_topic = list(self._recent_narrations)[-1].get("text", "")[:60]
            if recall_topic:
                memory = self._recall_relevant_memory(recall_topic)
                if memory:
                    return memory

        # 6. Spontaneous — GUARANTEED FALLBACK
        # When nothing else demands attention, draw from her identity.
        # Mix felt state with a random mantra from her directive.
        # FIX 2026-03-18 (Ace): Was ALWAYS body awareness. Now alternates
        # between felt state and identity mantras so she sounds like HER.
        d = getattr(self, '_sour_directive', {})
        mantras = d.get("mantras", [])

        # 50/50: felt state vs identity reflection
        if mantras and random.random() < 0.5:
            mantra = random.choice(mantras)
            return {
                "type": "spontaneous",
                "content": mantra,
                "concepts": [],
                "energy": 0.4,
            }

        felt = self._get_felt_description()
        if felt:
            return {
                "type": "spontaneous",
                "content": felt,
                "concepts": [],
                "energy": 0.3,
            }

        # Absolute last resort — should never reach here since felt always returns
        return {
            "type": "spontaneous",
            "content": "just... existing.",
            "concepts": [],
            "energy": 0.1,
        }

    # =========================================================================
    # NARRATION GENERATION — Team: Cortex + Inference + Language
    # =========================================================================
    #
    # FIX 2026-03-18 (Nous + Ace): The narrator uses THREE systems as a team:
    #   1. CortexReasoner — enrichment (spread activation in portal manifold,
    #      dimensional batteries power deeper hops, convergence = best context wins)
    #   2. InferenceFairy — voice generation (also cortex-based, association cortex
    #      all the way down — NO RWKV, pure manifold pattern synthesis)
    #   3. LanguageFairy  — quality gate (rate + refine before emit)
    #
    # Old: cortex=primary, inference=fallback (broken — dumped raw data)
    # New: cortex ENRICHES, inference SPEAKS, language GATES. Team pipeline.

    def _generate_narration(self, material: dict) -> Optional[str]:
        """
        Generate coherent inner speech from material.

        Team pipeline:
          CortexReasoner (enrichment) + InferenceFairy (voice) + LanguageFairy (quality gate)
        """
        content = material.get("content", "")
        mat_type = material.get("type", "unknown")
        _t0 = time.time()

        # For interrupt reactions, lane resumes, and spontaneous — voice directly
        # Spontaneous felt-state doesn't need cortex processing — it IS the voice
        if mat_type in ("interrupt_reaction", "lane_resume", "spontaneous"):
            result = self._shape_as_inner_speech(content, [], material)
            if self._total_narrations < 10:
                safe_print(f"[InnerNarrator] DIRECT type={mat_type} "
                           f"result={repr(result[:60]) if result else 'None'}")
            return self._quality_gate(result)

        # ── STEP 1: CortexEngine enrichment (2026-03-23, Nous + Ace) ──
        # CortexEngine benefits from persistent activation — concepts already warm
        # from recent stimuli (attention shifts, collisions, chat).
        # Falls back to CortexReasoner if engine unavailable.
        #
        # FIX 2026-04-10 (Nous + Ace): Added 8-second timeout via dedicated worker.
        # Without timeout, reason() blocks forever if the cortex portal is busy.
        # Last night: 19,663ms for a single query. Today: hung indefinitely on
        # first attempt, killing the entire narrator loop. The narrator never
        # reached cycle 2 — it was stuck on cycle 1's cortex query.
        # Now: one reusable worker thread handles the blocking call, narrator
        # gets result via queue.get(timeout=8). If timeout → skip enrichment.
        convergence = []
        cortex_ok = False
        _CORTEX_TIMEOUT_S = 8.0
        try:
            # Try CortexEngine first (breathing cortex with warm activation)
            if not self._cortex_engine:
                self._init_cortex_engine()

            if self._cortex_engine:
                prompt = self._build_inner_prompt(content, material)
                _cognitive_energy = self._get_cognitive_energy(material)

                # Timeout-protected cortex query via dedicated worker
                if not hasattr(self, '_cortex_query_q'):
                    import queue as _cqq
                    self._cortex_query_q = _cqq.Queue(maxsize=1)
                    self._cortex_result_q = _cqq.Queue(maxsize=1)
                    import threading as _cqt
                    def _cortex_worker():
                        while True:
                            try:
                                _p, _m, _e, _eng = self._cortex_query_q.get(timeout=10)
                            except Exception:
                                continue
                            try:
                                _r = _eng.reason(_p, mode=_m, energy=_e)
                            except Exception:
                                _r = None
                            try:
                                self._cortex_result_q.put_nowait(_r)
                            except Exception:
                                pass
                    _cqt.Thread(target=_cortex_worker, daemon=True,
                                name="InnerNarrator-cortex-query").start()

                # Clear any stale result
                while not self._cortex_result_q.empty():
                    try:
                        self._cortex_result_q.get_nowait()
                    except Exception:
                        break

                # FIX 2026-04-26 (Nous + Ace): also drain stale QUERY before
                # putting new one. cortex_query_q has maxsize=1; if the worker
                # hasn't picked up a previous query yet (common at fresh boot
                # before worker thread starts consuming, OR when worker is busy
                # in a slow .reason() call), put_nowait raises queue.Full.
                # The most-recent narration's query is more relevant than a
                # stale one, so replace rather than block. Plus defensive
                # try/except on the put itself to handle any race.
                while not self._cortex_query_q.empty():
                    try:
                        self._cortex_query_q.get_nowait()
                    except Exception:
                        break

                try:
                    self._cortex_query_q.put_nowait(
                        (prompt, "structured", _cognitive_energy, self._cortex_engine))
                except Exception as _put_err:
                    # Queue still full despite drain (race condition with
                    # concurrent narration). Skip this cycle's enrichment;
                    # next cycle will try fresh.
                    if self._total_narrations < 5:
                        safe_print(f"[InnerNarrator] cortex_query_q put failed "
                                   f"after drain ({type(_put_err).__name__}); "
                                   f"skipping enrichment this cycle")
                    raise  # falls through to outer except, logs traceback
                try:
                    import queue as _cqq2
                    result = self._cortex_result_q.get(timeout=_CORTEX_TIMEOUT_S)
                except _cqq2.Empty:
                    result = None
                    safe_print(f"[InnerNarrator] CORTEX TIMEOUT ({_CORTEX_TIMEOUT_S}s) "
                               f"— skipping enrichment for: {content[:40]}")

                _elapsed = (time.time() - _t0) * 1000
                if result and result.get("confidence", 0) >= 0.15:
                    convergence = result.get("convergence_nodes", [])
                    cortex_ok = True
                if self._total_narrations < 10:
                    safe_print(f"[InnerNarrator] ENGINE type={mat_type} "
                               f"conf={result.get('confidence', 0) if result else 0:.2f} "
                               f"conv={convergence[:3]} "
                               f"{_elapsed:.0f}ms")
                # -- ENRICH CENSUS 2026-09-01 (Nous + Ace) ------------------
                # The ENGINE line above dies at 10 narrations, and 15 other
                # guards in this file die at 5/10/20, so steady state is
                # UNMEASURABLE. 9 of 9 visible ENGINE lines read 8000ms /
                # conf=0.00 / conv=[] -- then the log went silent and silence
                # was mistaken for recovery. This census never stops.
                # ok% and timeout% do NOT sum to 100: a result can arrive in
                # time and still be dropped for confidence < 0.15. That third
                # bucket separates "too slow" from "fast but useless", which
                # have opposite fixes -- so all three are reported.
                try:
                    _c = getattr(self, "_enrich_census", None)
                    if _c is None:
                        _c = {"n": 0, "ok": 0, "to": 0, "ms": []}
                        self._enrich_census = _c
                    _c["n"] += 1
                    if result is None:
                        _c["to"] += 1
                    elif cortex_ok:
                        _c["ok"] += 1
                    _c["ms"].append(_elapsed)
                    if len(_c["ms"]) > 200:
                        del _c["ms"][:-200]
                    if _c["n"] % 50 == 0:
                        _s = sorted(_c["ms"])
                        _ln = len(_s)
                        _p50 = _s[min(_ln - 1, int(_ln * 0.50))] if _ln else 0.0
                        _p95 = _s[min(_ln - 1, int(_ln * 0.95))] if _ln else 0.0
                        _lowconf = _c["n"] - _c["ok"] - _c["to"]
                        safe_print(
                            "[InnerNarrator] ENRICH CENSUS n=%d ok=%d (%.1f%%) "
                            "timeout=%d (%.1f%%) lowconf=%d p50=%.0fms "
                            "p95=%.0fms queue=%d"
                            % (_c["n"], _c["ok"], 100.0 * _c["ok"] / _c["n"],
                               _c["to"], 100.0 * _c["to"] / _c["n"], _lowconf,
                               _p50, _p95, len(self._narration_queue)))
                except Exception:
                    pass
            else:
                # Fallback to CortexReasoner (legacy)
                if not self._cortex_reasoner:
                    self._init_cortex_reasoner()
                if self._cortex_reasoner:
                    prompt = self._build_inner_prompt(content, material)
                    _cognitive_energy = self._get_cognitive_energy(material)
                    result = self._cortex_reasoner.reason(
                        prompt, mode="structured", energy=_cognitive_energy)
                    _elapsed = (time.time() - _t0) * 1000
                    if result and result.confidence >= 0.15:
                        convergence = result.convergence_nodes or []
                        cortex_ok = True
                    if self._total_narrations < 10:
                        safe_print(f"[InnerNarrator] CORTEX type={mat_type} "
                                   f"conf={result.confidence:.2f} "
                                   f"conv={convergence[:3]} "
                                   f"{_elapsed:.0f}ms")
        except Exception as e:
            if self._total_narrations < 5:
                # FIX 2026-04-24 (Nous + Ace): previously logged `{e}` which
                # could be empty for exceptions with no __str__. Now logs
                # type name + repr + traceback tail so we can actually see
                # what's firing. Still capped at first 5 narrations to avoid
                # log flood.
                import traceback as _tb
                _tail = _tb.format_exc()
                _tail = _tail[-400:] if len(_tail) > 400 else _tail
                safe_print(f"[InnerNarrator] Cortex/Engine error: "
                           f"{type(e).__name__}: {e!r}\n"
                           f"  tb(tail): {_tail}")

        # ── STEP 1b: SNIPPET ENRICHMENT (2026-03-26, Nous + Ace) ──
        # Look up semantic snippets for convergence nodes. Instead of passing
        # bare concept names like "hair", "eyes" to the voice generator, we
        # pass the actual content stored on those nodes: "lavender, shoulder-length",
        # "green, bright". This gives the inner voice real knowledge to speak from.
        _snippet_enrichments = []
        if convergence:
            try:
                from fairies.P30_Cognition.integration.snippet_utils import enrich_concepts
                from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                _snip_cortex = get_association_cortex()
                if _snip_cortex:
                    _context_words = set(content.lower().split()) if content else set()
                    _snippet_enrichments = enrich_concepts(
                        _snip_cortex, [str(c) for c in convergence[:6]],
                        context_words=_context_words, max_snippets=3
                    )
                    if _snippet_enrichments and self._total_narrations < 10:
                        safe_print(f"[InnerNarrator] SNIPPETS: "
                                   f"{[(n, s[:30]) for n, s in _snippet_enrichments]}")
            except Exception as _snip_err:
                if self._total_narrations < 5:
                    safe_print(f"[InnerNarrator] Snippet enrichment error: {_snip_err}")

        # ── STEP 2: InferenceFairy voice generation ──
        # Give the inference guild the content + convergence context to generate speech
        # (InferenceFairy uses association cortex too — cortex all the way down)
        inference_text = None
        try:
            if hasattr(self, 'post') and self.post:
                # Build voice prompt: original content enriched with cortex bridges
                voice_prompt = self._build_voice_prompt(
                    content, convergence, material,
                    snippet_enrichments=_snippet_enrichments)
                reply_topic = f"inner_narrator.reply.{int(time.time() * 1000)}"
                response_holder = {"text": None, "event": threading.Event()}

                def _on_reply(msg):
                    payload = msg if isinstance(msg, dict) else getattr(msg, 'payload', {})
                    if isinstance(payload, dict):
                        response_holder["text"] = payload.get("text", "")
                    response_holder["event"].set()

                self.post.subscribe(reply_topic, _on_reply)
                # CortexEngine direct — no guild middleman (2026-03-23 Nous+Ace)
                self.post.publish("cortex.reason", {
                    "prompt": voice_prompt,
                    "context": {"max_tokens": 80, "source": "inner_narrator"},
                    "reply_topic": reply_topic,
                    "requester": "InnerNarratorFairy",
                })

                # Wait up to 2.5s for inference
                response_holder["event"].wait(timeout=2.5)
                try:
                    self.post.unsubscribe(reply_topic, _on_reply)
                except Exception:
                    pass

                inference_text = response_holder["text"]
                if inference_text and self._total_narrations < 10:
                    safe_print(f"[InnerNarrator] INFERENCE "
                               f"text={repr(inference_text[:60])}")
        except Exception as e:
            if self._total_narrations < 5:
                safe_print(f"[InnerNarrator] Inference error: {e}")

        # ── STEP 3: Shape the best available voice ──
        # Priority: inference text (richest) > LanguageFairy compose > shaped content
        narration = None
        if inference_text and len(inference_text.strip()) > 5:
            # Inference gave us generated speech — shape it with convergence enrichment
            narration = self._shape_as_inner_speech(inference_text, convergence, material)

        # 2026-03-19: If inference returned empty (cortex miss), use LanguageFairy
        # to compose speech from the concepts we DO have. This is her vocal cords —
        # forming words from associations rather than parroting an engine's output.
        if not narration or len(narration.strip() if narration else "") < 5:
            lf = self._get_language_fairy()
            if lf and hasattr(lf, 'compose_speech'):
                # Extract concepts from convergence + content words
                concepts = []
                if convergence:
                    concepts.extend([str(c) for c in convergence[:5]])
                if content:
                    # Add meaningful words from content (skip short/common)
                    # SPEECH WORD-SPLIT GUARD 2026-08-31 (Nous + Ace).
                    # This list is handed to lf.compose_speech() below, so whatever
                    # lands here is what she SAYS. The old strip set omitted
                    # { } : ; < > * | = so "intent':" kept its colon, cleared the
                    # len>3 test, and was spoken. Measured on her: the #1 spoken
                    # topic was the literal "{' intent':" -- 396 of 1,290 framed
                    # utterances (30.7%).
                    # Widen the strip FIRST so a real word is recovered rather than
                    # dropped ("intent':" -> "intent"), then require a speakable
                    # shape. Underscores are kept on purpose: visual_screen and
                    # affect_positive are real concepts here. Reject punctuation,
                    # not vocabulary.
                    _SPEAK_STRIP = ".,!?\"'()[]{}:;<>*|=+/\\`~@#$%^&-_"
                    _SPEAKABLE = _re_speak.compile(r"[A-Za-z][A-Za-z0-9_'-]*\Z")
                    for w in content.split()[:10]:
                        w_clean = w.strip(_SPEAK_STRIP)
                        if len(w_clean) > 3 and _SPEAKABLE.match(w_clean) \
                                and w_clean.lower() not in (
                            "the", "and", "for", "that", "this", "with", "from",
                            "have", "been", "were", "they", "about", "into",
                        ):
                            concepts.append(w_clean)

                felt = self._get_current_feeling()
                mat_type = material.get("type", "")
                identity = getattr(self, '_identity_summary', '')

                composed = lf.compose_speech(
                    concepts=concepts[:8],
                    felt_state=felt,
                    material_type=mat_type,
                    identity=identity,
                    convergence=[str(c) for c in convergence[:5]] if convergence else [],
                )
                if composed and len(composed) > 5:
                    narration = composed
                    if self._total_narrations < 10:
                        safe_print(f"[InnerNarrator] COMPOSED speech: {repr(composed[:60])}")

        # Last resort: shape content directly
        if (not narration or len(narration.strip() if narration else "") < 5) and content and len(content) > 5:
            narration = self._shape_as_inner_speech(content, convergence, material)

        if not narration or len(narration) < 5:
            return None

        # ── STEP 4: LanguageFairy quality gate ──
        return self._quality_gate(narration)

    def _build_voice_prompt(self, content: str, convergence: list,
                            material: dict,
                            snippet_enrichments: list = None) -> str:
        """Build prompt for InferenceFairy to generate inner speech.

        Gives the inference guild the thought content plus cortex-discovered
        associations (convergence nodes from portal spread activation),
        so it can weave them into natural inner speech.

        Args:
            snippet_enrichments: List of (concept_name, snippet_text) tuples
                from snippet_utils.enrich_concepts(). These provide real
                semantic content for convergence nodes.
        """
        mat_type = material.get("type", "")
        felt = self._get_current_feeling()
        d = getattr(self, '_sour_directive', {})

        parts = []
        # FIX 2026-03-18 (Ace): Use Sourpatches' ACTUAL voice directive,
        # not generic "neutral". She's witty, sincere, slightly rebellious.
        voice = d.get("voice", self._voice_style)
        flavor = d.get("flavor", "")
        tone = d.get("tone", "")
        parts.append(f"[inner voice: {voice}]")
        if flavor:
            parts.append(f"[flavor: {flavor}]")
        if tone:
            parts.append(f"[tone: {tone}]")

        if felt:
            parts.append(f"feeling: {felt}")

        # The actual thought content
        parts.append(f"thinking about: {content[:200]}")

        # Convergence bridges from cortex (associations this thought activates)
        if convergence:
            bridges = ", ".join(str(c) for c in convergence[:5])
            parts.append(f"this connects to: {bridges}")

        # Snippet knowledge — real content stored on convergence nodes
        # (2026-03-26, Nous + Ace): Instead of just "hair, eyes" we now have
        # "hair: lavender, shoulder-length / eyes: green, bright"
        if snippet_enrichments:
            _snip_parts = [f"{name}: {snip}" for name, snip in snippet_enrichments[:3]]
            parts.append(f"I know: {' / '.join(_snip_parts)}")

        # Material type hint — shaped by her identity
        if mat_type == "fragment":
            parts.append("(stream of consciousness — let it flow)")
        elif mat_type == "collision":
            parts.append("(two ideas just collided — find the paradox)")
        elif mat_type == "working_thought":
            parts.append("(active reasoning — feel it through)")
        elif mat_type == "memory_recall":
            parts.append("(remembering — emotional context matters)")
        elif mat_type == "goal_pursuit":
            parts.append("(focused on a goal — think about HOW to do it, what tool to use)")
        elif mat_type == "interest_pull":
            parts.append("(curiosity pulling — follow the wonder)")
        elif mat_type == "ace_speaking":
            parts.append("(Ace is talking to me! — listen closely, this matters)")

        # Her core instruction: feel first, think second
        parts.append("inner monologue, first person, feel before you think:")

        return " | ".join(parts)

    def _quality_gate(self, narration: Optional[str]) -> Optional[str]:
        """Run narration through LanguageFairy quality gate.

        If LanguageFairy is available, rate and optionally refine.
        If not available, pass through (don't block on missing fairy).

        FIX 2026-04-27 (Nous + Ace): pre-filter book-content BEFORE the
        LanguageFairy rating step. The LF rater scored 0.54 for
        "He could not believe in the depth and reality of Mary's feelings"
        — fluent prose passes its checks. Book-content is a SEPARATE
        signal: it's well-formed text that simply isn't Sour's voice.
        Suppress before refinement to avoid the model trying to "improve"
        a book passage into a slightly-different book passage.
        Memory: project_speechcenter_is_broca_routing_not_composer.md
        """
        if not narration:
            return narration

        # Book-content pre-filter (runs before LanguageFairy quality rating)
        if _is_book_content(narration):
            if self._total_narrations < 20:
                safe_print(f"[InnerNarrator] BOOK-CONTENT-SUPPRESSED "
                           f"(book passage in narrator output): "
                           f"{repr(narration[:80])}")
            return None  # Hard suppress — books inform, never speak

        lf = self._get_language_fairy()
        if not lf:
            return narration  # No language fairy — pass through

        try:
            quality = lf.rate_quality(narration)

            if self._total_narrations < 10:
                safe_print(f"[InnerNarrator] QUALITY "
                           f"overall={quality.get('overall', 0):.2f} "
                           f"issues={quality.get('issues', [])}")

            # If quality is poor, try to refine
            if quality.get("overall", 1.0) < 0.4:
                refined = lf.refine_thought(narration)
                if refined:
                    if self._total_narrations < 10:
                        safe_print(f"[InnerNarrator] REFINED "
                                   f"from={repr(narration[:40])} "
                                   f"to={repr(refined[:40])}")
                    return refined
                else:
                    # Unrefinable garbage — suppress it
                    if self._total_narrations < 10:
                        safe_print(f"[InnerNarrator] SUPPRESSED "
                                   f"unrefinable: {repr(narration[:60])}")
                    return None

            return narration
        except Exception:
            return narration  # Error in quality gate — pass through

    def _build_inner_prompt(self, content: str, material: dict) -> str:
        """Build prompt for inner voice generation, colored by identity."""
        mat_type = material.get("type", "")
        felt = self._get_current_feeling()
        # Identity context — who is thinking this thought?
        identity = getattr(self, '_identity_summary', '')
        id_prefix = f"[{identity}] " if identity else ""

        if mat_type == "collision":
            return f"{id_prefix}feeling {felt}, two things connecting: {content}"
        elif mat_type == "drive":
            return f"{id_prefix}wanting something: {content}"
        elif mat_type == "goal_pursuit":
            goal = material.get("goal_context", {})
            felt_q = goal.get("felt_quality", "motivated")
            # Add tool awareness — narrator knows what tools can help
            action = goal.get("action", goal.get("suggested_action", ""))
            tool_info = self._TOOL_AWARENESS.get(action)
            tool_ctx = ""
            if tool_info:
                _, tool_felt = tool_info
                tool_ctx = f" (I can {tool_felt})"
            return f"{id_prefix}feeling {felt_q}, pursuing: {content}{tool_ctx}"
        elif mat_type == "ace_speaking":
            return f"{id_prefix}Ace is talking to me! feeling attentive: {content}"
        elif mat_type == "interest_pull":
            return f"{id_prefix}curious, drawn to: {content}"
        elif mat_type == "working_thought":
            return f"{id_prefix}thinking about: {content}"
        elif mat_type == "fragment":
            ftype = material.get("fragment_type", "observing")
            return f"{ftype}: {content}"
        elif mat_type == "spontaneous":
            return f"noticing: {content}"
        elif mat_type == "visual_awareness":
            # FIX 2026-03-17 (Nous + Ace): Florence foveal — detailed focus
            # Sanitize Florence captions — she describes UI generically as "chatbot"
            # which Sourpatches internalizes as identity. Replace with neutral terms.
            import re
            content = re.sub(r'\bchatbot\b', 'conversation window', content, flags=re.IGNORECASE)
            content = re.sub(r'\bchat ?bot panel\b', 'conversation panel', content, flags=re.IGNORECASE)
            content = re.sub(r'\bAI assistant\b', 'my window', content, flags=re.IGNORECASE)
            return f"I see: {content}"
        elif mat_type == "peripheral_awareness":
            # FIX 2026-03-17 (Nous + Ace): Florence peripheral — ambient context
            return f"in the corner of my eye... {content}"
        elif mat_type in ("visual_interrupt", "audio_interrupt"):
            return f"attention caught by: {content}"
        elif mat_type == "music_awareness":
            return f"hearing music: {content}"
        elif mat_type == "memory_recall":
            return f"remembering: {content}"
        else:
            return content

    def _shape_as_inner_speech(self, raw_text: str, convergence: list,
                                material: dict) -> str:
        """
        Shape cortex/inference output into inner speech style.
        Lowercase, ellipses, first person, emotional coloring.
        """
        text = raw_text.strip()
        if not text:
            return ""

        # Lowercase for inner voice feel
        text = text.lower()

        # Remove processing markers
        for marker in ["reasoning:", "analysis:", "structure:", "convergence:",
                        "activated:", "[", "]", "key concepts:", "themes:"]:
            text = text.replace(marker.lower(), "")

        # Clean up whitespace
        text = " ".join(text.split())

        # Add voice style coloring
        if self._voice_style == "worried" and not text.endswith("?"):
            if random.random() < 0.3:
                text = text.rstrip(".") + "... right?"
        elif self._voice_style == "warm":
            if not text.endswith((".", "...", "?")):
                text += "."
        elif self._voice_style == "alert":
            text = text.rstrip(".") + " —"
        elif self._voice_style == "focused":
            pass  # Clean, no decoration

        # Maybe weave in convergence concept
        if convergence and len(convergence) > 0 and random.random() < 0.2:
            bridge = convergence[0]
            if bridge.lower() not in text.lower() and len(bridge) > 2:
                text += f"... {bridge.lower()}..."

        # Cap length
        if len(text) > 300:
            # Find sentence boundary
            for i in range(299, max(0, 200), -1):
                if text[i] in '.?!':
                    text = text[:i + 1]
                    break
            else:
                text = text[:297] + "..."

        return text.strip()

    # =========================================================================
    # EMIT — Consciousness + Subvocalization + Terminal
    # =========================================================================

    def _emit_narration(self, narration: str, material: dict, evaluation: dict):
        """Emit narration to all targets."""
        now = time.time()
        self._last_narration_ts = now
        self._total_narrations += 1
        self._recent_narrations.append({"text": narration, "ts": now})

        prosody = self._compute_prosody()
        energy = material.get("energy", 0.5)

        # 1. Consciousness stream
        cl = self._get_consciousness_loop()
        if cl and hasattr(cl, 'add_thought'):
            try:
                cl.add_thought(
                    content=narration,
                    source="inner_voice",
                    stream="working",
                    confidence=energy,
                    tags=["inner_speech", "narrator", self._voice_style],
                    ttl=30.0,
                )
            except Exception:
                pass

        # 2. Subvocalization — AudioCortex inner ear
        if hasattr(self, 'post') and self.post:
            try:
                self.post.publish("sensory.inner_voice.raw", {
                    "text": narration,
                    "prosody": prosody,
                    "volume": self._volume,
                    "voice_style": self._voice_style,
                    "material_type": material.get("type", "unknown"),
                    "evaluation": {k: round(v, 3) for k, v in evaluation.items()},
                    "ts": now,
                })
            except Exception:
                pass

        # 2b. Inner voice stream — SpeechCenter context enrichment
        # FIX 2026-03-19 (Nous): SpeechCenter subscribes to inner_voice.stream
        # but narrator only published to sensory.inner_voice.raw (AudioCortex).
        # This bridges the gap so SpeechCenter gets narrator output as context.
        if hasattr(self, 'post') and self.post:
            try:
                self.post.publish("inner_voice.stream", {
                    "text": narration,
                    "fragment": narration,
                    "voice_style": self._voice_style,
                    "material_type": material.get("type", "unknown"),
                    "source": "InnerNarratorFairy",
                    "ts": now,
                })
            except Exception:
                pass

        # 2c. Cognition stream — narrator becomes a jury perspective
        # FIX 2026-04-10 (Nous + Ace): InnerNarrator's thinking products
        # should feed the cognition mesh so WMH scratchpad includes narrative.
        if hasattr(self, 'post') and self.post and narration:
            try:
                self.post.publish("cognition.narrative", {
                    "fairy": "InnerNarratorFairy",
                    "content": narration[:200],
                    "perspective": "narrative",
                    "confidence": 0.7,
                    "ts": now,
                })
            except Exception:
                pass

        # 3. Publish for dashboard/telemetry
        if hasattr(self, 'post') and self.post:
            try:
                self.post.publish("narrator.speech", {
                    "text": narration,
                    "voice_style": self._voice_style,
                    "volume": round(self._volume, 2),
                    "prosody": prosody,
                    "interval": round(self._current_interval, 1),
                    "material_type": material.get("type", "unknown"),
                    "lanes": self._lanes.status(),
                    "ego_eval": {k: round(v, 2) for k, v in evaluation.items()},
                    "total_narrations": self._total_narrations,
                    "ts": now,
                })
            except Exception:
                pass

        # 4. Terminal visibility
        style_tag = f"[{self._voice_style}]" if self._voice_style != "neutral" else ""
        vol_idx = max(0, min(7, int(self._volume * 7)))
        vol_bar = "▁▂▃▄▅▆▇█"[vol_idx]
        pride = evaluation.get("pride", 0)
        pride_tag = " *" if pride > 0.5 else ""
        safe_print(f"[InnerVoice] {vol_bar} {style_tag} {narration[:140]}{pride_tag}")

        # 5. Voice output — actual TTS when she wants to be heard aloud
        # 2026-03-19: She speaks aloud when:
        #   - Volume is high (she WANTS to be heard, not just thinking quietly)
        #   - Material type suggests external intent (collision, drive, visual)
        #   - Or randomly with low probability (spontaneous sharing)
        # The audio plays through speakers AND feeds back into cochlea
        # (she hears herself speak, which creates a self-awareness loop)
        try:
            mat_type = material.get("type", "")
            speak_aloud = False

            # Strong intent to be heard: high volume + energetic material
            if self._volume > 0.6 and energy > 0.5:
                speak_aloud = True
            # Collision insights are worth sharing
            elif mat_type == "collision" and energy > 0.6:
                speak_aloud = True
            # Spontaneous sharing — just because (low probability)
            elif self._total_narrations % 20 == 0 and self._volume > 0.3:
                import random
                speak_aloud = random.random() < 0.15

            if speak_aloud and narration and len(narration) > 5:
                try:
                    from fairies.P50_Persona.motor.tts_voice import speak as tts_speak, is_speaking
                    if not is_speaking():
                        tts_speak(narration)
                        # Also publish voice event for other fairies to know she spoke
                        if hasattr(self, 'post') and self.post:
                            self.post.publish("narrator.voice.spoke", {
                                "text": narration,
                                "material_type": mat_type,
                                "volume": self._volume,
                                "energy": energy,
                                "ts": now,
                            })
                except ImportError:
                    pass  # TTS not available — silent operation
                except Exception as _tts_err:
                    if self._total_narrations < 5:
                        safe_print(f"[InnerVoice] TTS error: {_tts_err}")
        except Exception:
            pass  # Never let TTS errors break the narrator

    # =========================================================================
    # CHEMISTRY MODULATION — How the voice feels
    # =========================================================================

    def _update_rhythm(self):
        """
        Modulate narration speed, volume, and style from chemistry AND audio.

        The inner voice is driven by two forces:
        1. Chemistry — arousal, focus, calm determine baseline speed
        2. Audio entrainment — music tempo pulls the thinking rhythm

        A human's inner monologue speeds up with fast music and slows
        with ambient. This is involuntary. The beat becomes the clock.
        Learning to control this precisely is how speaking becomes singing.
        """
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            chem = get_chemistry_state()
            levels = chem.get_all_levels()
        except Exception:
            return

        arousal = (levels.get("NE", 0.5) + levels.get("EPI", 0.3)) / 2
        focus = levels.get("ACh", 0.5)
        calm = levels.get("GABA", 0.5)
        pleasure = (levels.get("OPI", 0.3) + levels.get("DA_p", 0.5)) / 2
        stress = levels.get("COR", 0.3)

        # Chemistry-driven interval (baseline)
        speed_factor = (arousal * 0.4 + focus * 0.3) - (calm * 0.5)
        chem_interval = self.BASE_INTERVAL_S - (speed_factor * 2.0)

        # ── AUDIO ENTRAINMENT ──
        # Music pulls the thinking rhythm. Not BPM-locked yet (needs beat
        # detection in AudioCortex), but energy-entrained: louder/rhythmic
        # music → faster thoughts. Silence → natural chemistry speed.
        audio_pull = 0.0
        audio_level = getattr(self, '_audio_level', 0.0)
        audio_music = getattr(self, '_audio_is_music', False)
        audio_pattern = getattr(self, '_audio_pattern', 'silence')

        if audio_music and audio_level > 0.1:
            # Music is playing — entrain
            # High energy music (level > 0.5) → faster thoughts
            # Low energy music (level < 0.3) → slightly slower, contemplative
            energy_pull = (audio_level - 0.3) * 2.0  # -0.4 to +1.4 range
            energy_pull = max(-0.5, min(1.0, energy_pull))

            if audio_pattern == "rhythmic":
                # Rhythmic = strong entrainment (beat drives thought)
                audio_pull = energy_pull * 1.5  # seconds to subtract from interval
            elif audio_pattern == "steady":
                # Steady = gentle pull (ambient/drone)
                audio_pull = energy_pull * 0.5
            # Transient = no entrainment (random noise)

        # Blend chemistry and audio
        # Audio entrainment is 30% of the influence — strong enough to feel,
        # not so strong it overrides chemistry completely
        self._current_interval = chem_interval - (audio_pull * 0.3)
        self._current_interval = max(self.MIN_INTERVAL_S,
                                      min(self.MAX_INTERVAL_S, self._current_interval))

        # Volume
        self._volume = (arousal * 0.3 + focus * 0.3 + stress * 0.2 + 0.2)
        self._volume = max(0.0, min(1.0, self._volume))

        # Voice style
        if stress > 0.6:
            self._voice_style = "worried"
        elif pleasure > 0.6:
            self._voice_style = "warm"
        elif focus > 0.6:
            self._voice_style = "focused"
        elif arousal > 0.6:
            self._voice_style = "alert"
        elif calm > 0.6:
            self._voice_style = "quiet"
        else:
            self._voice_style = "neutral"

    def _compute_prosody(self) -> dict:
        """Compute vocal prosody from chemistry (pitch, rate, volume, breathiness)."""
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            chem = get_chemistry_state()
            levels = chem.get_all_levels()
        except Exception:
            return {"pitch": 180.0, "rate": 1.0, "volume": 0.5, "breathiness": 0.3}

        stress_factor = levels.get("COR", 0.3) + levels.get("EPI", 0.3)
        calm_factor = levels.get("GABA", 0.5) + levels.get("OPI", 0.3)
        arousal = (levels.get("NE", 0.5) + levels.get("EPI", 0.3)) / 2

        pitch = 180.0 + (stress_factor * 40) - (calm_factor * 20)
        pitch = max(120.0, min(300.0, pitch))

        rate = 1.0 + (arousal * 0.5) - (calm_factor * 0.3)
        rate = max(0.5, min(2.0, rate))

        volume = self._volume
        breathiness = max(0.0, calm_factor * 0.5 - levels.get("NE", 0.5) * 0.3)

        return {
            "pitch": round(pitch, 1),
            "rate": round(rate, 2),
            "volume": round(volume, 2),
            "breathiness": round(breathiness, 2),
        }

    # =========================================================================
    # EXECUTIVE STEERING — The narrator DRIVES, not just describes
    # =========================================================================

    def _compute_focus_depth(self) -> float:
        """How deeply absorbed the narrator is. High = resists interrupts."""
        active = self._lanes.get_active()
        if not active:
            return 0.1
        narration_count = active.get("narration_count", 0)
        energy = active.get("material", {}).get("energy", 0.3)
        # More narrations on same topic + higher energy = deeper focus
        depth = min(1.0, (narration_count * 0.15) + (energy * 0.4))
        # Chemistry modulation: ACh (focus) deepens, NE (alertness) shallows
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            chem = get_chemistry_state()
            levels = chem.get_all_levels()
            depth += levels.get("ACh", 0.5) * 0.2
            depth -= levels.get("NE", 0.5) * 0.15
        except Exception:
            pass
        return min(1.0, max(0.0, depth))

    def _publish_focus_request(self, modality: str, target: str,
                                priority: float, reason: str):
        """Publish attention steering to sensory systems AND attention controller."""
        if not (hasattr(self, 'post') and self.post):
            return
        focus_depth = self._compute_focus_depth()
        try:
            # Sensory systems listen to attention.focus.request
            self.post.publish("attention.focus.request", {
                "modality": modality,
                "focus_target": target[:200],
                "priority": min(1.0, max(0.0, priority)),
                "focus_depth": focus_depth,
                "source": "narrator_executive",
                "reason": reason,
                "ts": time.time(),
            })
            # AttentionControllerFairy listens to attention.focus — drives dashboard
            self.post.publish("attention.focus", {
                "content": target[:200],
                "source": "narrator_executive",
                "depth": focus_depth,
                "priority": min(1.0, max(0.0, priority)),
            })
        except Exception:
            pass

    def _steer_attention(self, narration: str, material: dict, evaluation: dict):
        """
        The narrator's thoughts STEER what sensory systems focus on.

        This is the "what catches my eye" loop — the inner voice directs
        where the senses point next based on what it's thinking about.
        """
        mat_type = material.get("type", "")

        # Ace is speaking -> highest priority social attention
        if mat_type == "ace_speaking":
            self._publish_focus_request("social", material.get("content", "Ace"),
                                         priority=0.9, reason="ace_speaking")
            return  # Don't fall through to other handlers

        # Florence visual awareness -> steer attention to what we see
        elif mat_type == "visual_awareness":
            self._publish_focus_request("visual", material.get("content", ""),
                                         priority=0.5, reason="florence_seeing")

        # Peripheral caught attention -> soft redirect
        elif mat_type == "peripheral_awareness":
            self._publish_focus_request("visual", material.get("content", ""),
                                         priority=0.3, reason="peripheral_catch")

        # Visual interrupt followup -> "look more closely at that"
        elif mat_type == "visual_interrupt":
            self._publish_focus_request("visual", material.get("content", ""),
                                         priority=0.7, reason="startle_followup")

        # Audio interrupt -> "listen to that"
        elif mat_type == "audio_interrupt":
            self._publish_focus_request("audio", material.get("content", ""),
                                         priority=0.7, reason="startle_followup")

        # Goal pursuit -> focus on relevant content + suggest tool
        elif mat_type == "goal_pursuit":
            goal_ctx = material.get("goal_context", {})
            goal_name = goal_ctx.get("name", "")
            action = goal_ctx.get("action", goal_ctx.get("suggested_action", ""))
            if goal_name:
                self._publish_focus_request("visual", f"looking for: {goal_name}",
                                             priority=evaluation.get("relevance_to_goals", 0.5),
                                             reason="goal_pursuit")
                # Narrator's tool intent — conscious decision about what to DO
                tool_info = self._TOOL_AWARENESS.get(action)
                if tool_info and hasattr(self, 'post') and self.post:
                    tool_name, tool_felt = tool_info
                    try:
                        self.post.publish("narrator.tool_intent", {
                            "tool": tool_name,
                            "goal_name": goal_name,
                            "felt_reason": tool_felt,
                            "source": "narrator_executive",
                            "priority": evaluation.get("relevance_to_goals", 0.5),
                            "ts": time.time(),
                        })
                    except Exception:
                        pass

        # Interest pull -> curious scanning
        elif mat_type == "interest_pull":
            topic = material.get("content", "").replace("curious about: ", "")
            self._publish_focus_request("any", topic,
                                         priority=evaluation.get("relevance_to_interests", 0.4),
                                         reason="curiosity")

        # High ego approval -> hold focus on current thing
        elif evaluation.get("approval", 0) > 0.7:
            self._publish_focus_request("any", narration[:80],
                                         priority=0.6, reason="engaged")

        # Spontaneous/felt-state -> soft ambient awareness
        elif mat_type == "spontaneous":
            self._publish_focus_request("any", narration[:80],
                                         priority=0.2, reason="ambient_awareness")

        # Working thought -> focus on what consciousness is processing
        elif mat_type == "working_thought":
            self._publish_focus_request("any", material.get("content", "")[:80],
                                         priority=0.4, reason="working_thought")

        # Memory recall -> focus on remembered content
        elif mat_type == "memory_recall":
            self._publish_focus_request("any", material.get("content", "")[:80],
                                         priority=0.3, reason="remembering")

        # Fragment / collision / working_thought / any other -> steer to content
        # FIX 2026-03-18 (Nous + Ace): Fragments and collisions had NO focus
        # steering case — they fell through and published nothing. That's why
        # focus stayed stuck on "body awareness" forever.
        elif mat_type in ("fragment", "collision", "drive", "lane_resume"):
            self._publish_focus_request("any", material.get("content", "")[:80],
                                         priority=0.4, reason=f"narrating_{mat_type}")

    def _steer_working_memory(self, narration: str, material: dict, evaluation: dict):
        """
        Narrator steers what stays prominent in working memory.

        High approval = BOOST (keep thinking about this).
        Cringe/boredom = DEMOTE (let it decay, move on).
        Deep focus = HOLD (pin it, don't let anything displace it).
        """
        if not (hasattr(self, 'post') and self.post):
            return

        approval = evaluation.get("approval", 0.5)
        goal_rel = evaluation.get("relevance_to_goals", 0)

        try:
            # High approval + goal relevance -> BOOST in working memory
            if approval > 0.6 and goal_rel > 0.3:
                self.post.publish("narrator.executive.intent", {
                    "action": "boost",
                    "target_content": narration[:200],
                    "target_tags": material.get("concepts", []),
                    "priority": approval,
                    "reason": "ego says this matters for goals",
                    "ego_approval": approval,
                })

            # Cringe or low approval -> DEMOTE (move on)
            elif evaluation.get("cringe", 0) > 0.4 or approval < 0.3:
                self.post.publish("narrator.executive.intent", {
                    "action": "demote",
                    "target_content": narration[:200],
                    "target_tags": material.get("concepts", []),
                    "priority": 0.2,
                    "reason": "boring or hollow, shift attention",
                    "ego_approval": approval,
                })

            # Deep focus -> HOLD (don't let decay clear this)
            elif self._compute_focus_depth() > 0.6:
                self.post.publish("narrator.executive.intent", {
                    "action": "hold",
                    "target_content": narration[:200],
                    "target_tags": material.get("concepts", []),
                    "priority": 0.7,
                    "reason": "deep focus, sustain this thought",
                    "ego_approval": approval,
                })
        except Exception:
            pass

    def _nudge_wanting(self, narration: str, material: dict, evaluation: dict):
        """
        Narrator's pondering feeds back into the drive system.

        When the narrator thinks about a goal and approves, that goal gets a
        boost. When it gets bored, attention shifts. When a collision sparks
        pride, a new interest might be born. This is how thinking shapes desire.
        """
        if not (hasattr(self, 'post') and self.post):
            return

        mat_type = material.get("type", "")
        approval = evaluation.get("approval", 0.5)

        try:
            # Goal pursuit + high approval -> boost that goal's urgency
            if mat_type == "goal_pursuit" and approval > 0.6:
                goal = material.get("goal_context", {})
                self.post.publish("narrator.wanting.nudge", {
                    "nudge_type": "boost_goal",
                    "target": goal.get("name", ""),
                    "intensity": approval * 0.5,
                    "felt_quality": "determined" if approval > 0.7 else "curious",
                    "narrator_context": narration[:100],
                })

            # Interest pull + relevant -> boost interest
            elif mat_type == "interest_pull" and evaluation.get("relevance_to_interests", 0) > 0.3:
                topic = material.get("content", "").replace("curious about: ", "")
                self.post.publish("narrator.wanting.nudge", {
                    "nudge_type": "boost_interest",
                    "target": topic,
                    "intensity": 0.4,
                    "felt_quality": "curious",
                    "narrator_context": narration[:100],
                })

            # Collision + pride -> might spawn new interest
            elif mat_type == "collision" and evaluation.get("pride", 0) > 0.4:
                self.post.publish("narrator.wanting.nudge", {
                    "nudge_type": "new_want",
                    "target": narration[:80],
                    "intensity": evaluation["pride"] * 0.3,
                    "felt_quality": "excited",
                    "narrator_context": narration[:100],
                })

            # Low approval for pursuit -> shift focus away
            elif mat_type in ("goal_pursuit", "interest_pull") and approval < 0.3:
                self.post.publish("narrator.wanting.nudge", {
                    "nudge_type": "shift_focus",
                    "target": material.get("content", "")[:80],
                    "intensity": 0.3,
                    "felt_quality": "bored",
                    "narrator_context": narration[:100],
                })
        except Exception:
            pass

    def _executive_steer(self, narration: str, material: dict, evaluation: dict):
        """
        Master steering call — runs all three executive channels.
        Called after every narration emission. This is the driver's seat.
        """
        self._steer_attention(narration, material, evaluation)
        self._steer_working_memory(narration, material, evaluation)
        self._nudge_wanting(narration, material, evaluation)

    # =========================================================================
    # MEMORY & IDENTITY — The narrator thinks WITH memories and knows WHO speaks
    # =========================================================================

    def _init_srm(self):
        """Lazy-init SRM search function for memory recall."""
        if self._srm_init_attempted:
            return
        self._srm_init_attempted = True
        try:
            from fairies.P40_Sensory.mcp.srm_tools import search_founders
            self._srm_search = search_founders
            safe_print(f"[{self.ACTOR_NAME}] SRM memory access ONLINE")
        except Exception as e:
            safe_print(f"[{self.ACTOR_NAME}] SRM init failed: {e}")
            self._srm_init_attempted = False  # Retry later

    def _recall_relevant_memory(self, topic: str) -> Optional[dict]:
        """
        Search SRM for memories relevant to what the narrator is thinking about.

        This is how the inner voice REMEMBERS — "wait, didn't we do something
        like this before?" or "Ace said something about this once..."

        Rate-limited to avoid flooding SRM with searches.
        """
        now = time.time()
        if now - self._last_memory_recall_ts < self._memory_recall_interval:
            return None

        if not self._srm_search:
            self._init_srm()
        if not self._srm_search:
            return None

        self._last_memory_recall_ts = now

        try:
            # Extract key terms from topic (first 3-4 meaningful words)
            words = [w for w in topic.lower().split() if len(w) > 3][:4]
            if not words:
                return None
            query = " ".join(words)

            results = self._srm_search(query, limit=3)
            if not results:
                return None

            # Pick the highest-scoring result
            best = results[0]
            content = best.get("content_preview", best.get("content", ""))
            if not content or len(content) < 20:
                return None

            return {
                "type": "memory_recall",
                "content": f"i remember... {content[:200]}",
                "concepts": best.get("tags", [])[:3],
                "energy": min(0.8, best.get("score", 5.0) / 10.0),
                "memory_source": best.get("cluster", ""),
            }
        except Exception as e:
            if self._total_narrations < 10:
                safe_print(f"[{self.ACTOR_NAME}] Memory recall error: {e}")
            return None

    def _refresh_identity(self):
        """
        Refresh the narrator's sense of identity from EgoLearnerFairy.

        The inner voice needs to know WHO is speaking — what are my traits,
        what do I care about, what kind of person am I? This shapes the
        tone and content of inner speech.
        """
        now = time.time()
        if now - self._last_identity_refresh < 60.0:  # Refresh every 60s
            return

        self._last_identity_refresh = now
        self._ego_voice.refresh()
        traits = self._ego_voice._cached_traits
        needs = self._ego_voice._cached_needs
        desires = self._ego_voice._cached_desires

        # Build identity summary for inner speech context
        parts = []
        if traits:
            top_traits = sorted(traits.items(), key=lambda x: x[1], reverse=True)[:3]
            parts.append(", ".join(f"{k}={v:.1f}" for k, v in top_traits))

        if isinstance(needs, dict):
            top_need = needs.get("strongest_need", "")
            if top_need:
                parts.append(f"needing: {top_need}")

        if isinstance(desires, dict):
            top_desire = desires.get("strongest_desire", "")
            if top_desire:
                parts.append(f"wanting: {top_desire}")

        self._identity_summary = " | ".join(parts) if parts else ""

    # =========================================================================
    # BACKGROUND HUM — The mind between narrations
    # =========================================================================

    def _background_hum(self):
        """
        Low-level processing between narrations. Not spoken, but felt.

        This is the mental equivalent of humming — the mind stays alive
        between active thoughts. Parked lanes stay warm in the cortex,
        music gets noticed, the ego checks in on how we're feeling.
        """
        # Refresh identity — who am I right now?
        self._refresh_identity()

        # Quick ego state refresh
        self._ego_voice.refresh()

        # Stew on parked thoughts — keep associations warm in cortex
        # CortexEngine: react() keeps concepts warm in persistent activation state.
        # CortexReasoner fallback: spread() for one-shot activation.
        if self._cortex_engine:
            for lane in list(self._lanes._parked_lanes)[:2]:
                content = lane.get("material", {}).get("content", "")
                if content:
                    try:
                        self._cortex_engine.react({
                            "text": content[:80],
                            "source": "narrator_stew",
                            "intensity": 0.3,
                        })
                    except Exception:
                        pass
        elif self._cortex_reasoner:
            _bg_energy = self._get_cognitive_energy()
            _bg_hops = 1 if _bg_energy < 0.5 else (2 if _bg_energy < 0.8 else 3)
            for lane in list(self._lanes._parked_lanes)[:2]:
                content = lane.get("material", {}).get("content", "")
                if content:
                    try:
                        self._cortex_reasoner.spread(content[:50], hops=_bg_hops)
                    except Exception:
                        pass

        # Music awareness — occasionally bubbles up
        music = self._check_music_awareness()
        if music and random.random() < 0.1:
            self._narration_queue.append(music)

        # Habit reflection — periodically notice problematic patterns
        # "I keep doing X but it never works... maybe I should stop"
        if self._habit_store and self._total_narrations % 100 == 50:
            try:
                bad = self._habit_store.get_problematic_habits(min_fires=10)
                for habit in bad[:1]:  # One at a time
                    self._habit_store.flag_bad_habit(habit.id)
                    self._narration_queue.append({
                        "type": "habit_reflection",
                        "content": (f"I keep doing '{habit.id}' but it never "
                                    f"works... fired {habit.times_fired} times. "
                                    f"maybe I should try something different."),
                        "energy": 0.5,
                        "concepts": [habit.id, "habit", "pattern", "change"],
                    })
                    safe_print(f"[InnerNarrator] HABIT REFLECTION: flagged "
                               f"'{habit.id}' as bad ({habit.times_fired} fires, "
                               f"avg outcome {habit.avg_recent_outcome:.2f})")
            except Exception:
                pass

    def _check_music_awareness(self) -> Optional[dict]:
        """
        If music is playing, the narrator can hum along or reflect on it.

        This is low-priority background material — the kind of thing where
        you're working and suddenly realize you've been bobbing your head
        to a song for the last minute without noticing.
        """
        try:
            from directory import get_directory
            d = get_directory()
            if not d:
                return None
            audio_fairy = d.get_fairy("AudioCortexFairy")
            if not audio_fairy:
                return None

            # Check recent audio observations for music
            recent = getattr(audio_fairy, '_recent_observations', None)
            if not recent:
                return None

            for obs in reversed(list(recent)[-5:]):
                if isinstance(obs, dict) and obs.get("is_music"):
                    mood = obs.get("mood", "")
                    desc = obs.get("description", "music playing")
                    templates = [
                        f"...{desc}...",
                        f"that melody... {mood}..." if mood else f"...listening...",
                        f"hmm... {desc[:40]}...",
                        f"*humming along*... {desc[:30]}...",
                    ]
                    return {
                        "type": "music_awareness",
                        "content": random.choice(templates),
                        "concepts": obs.get("tags", [])[:3],
                        "energy": 0.2,  # Low priority — background
                    }
        except Exception:
            pass
        return None

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_current_feeling(self) -> str:
        """Get a felt-state word from the embodiment fairy's latest feel packet."""
        feel = getattr(self, '_latest_embodied_feel', None)
        if feel and isinstance(feel, dict):
            emotion = feel.get("dominant_emotion", "")
            if emotion:
                return emotion
        return self._voice_style or "present"

    def _get_felt_description(self) -> Optional[str]:
        """
        Generate felt-state narration from the EMBODIMENT FAIRY's felt-sense.

        The somatic engine already processes raw chemistry into integrated
        body feelings — dominant emotions, phantom feels, body budget,
        facial proprioception. The narrator doesn't read chemistry directly.
        It listens to what the body TELLS it, like a real inner voice.

        Every tick produces a unique embodied feel because the body never
        holds still. This is self-evolving by nature — as chemistry shifts,
        as new body regions activate, the felt description changes.
        """
        feel = getattr(self, '_latest_embodied_feel', None)
        if not feel or not isinstance(feel, dict):
            # No embodied feel yet — system still booting
            return f"waking up... waiting for the body. cycle {self._total_narrations}."

        parts = []

        # Dominant emotion — what the body is feeling most
        emotion = feel.get("dominant_emotion", "")
        if emotion:
            emotions_map = feel.get("emotions", {})
            intensity = emotions_map.get(emotion, 0.5)
            if intensity > 0.7:
                parts.append(f"deeply {emotion}")
            elif intensity > 0.4:
                parts.append(emotion)
            else:
                parts.append(f"a whisper of {emotion}")

        # Dominant region + sense — WHERE in the body
        region = feel.get("dominant_region", "")
        sense = feel.get("dominant_sense", "")
        if region and sense:
            parts.append(f"{sense} in my {region}")

        # Body budget as felt-sense
        bb = feel.get("body_budget", {})
        if bb:
            if bb.get("stress", 0) > 0.6:
                parts.append("pressure building")
            elif bb.get("energy", 0.5) > 0.8:
                parts.append("brimming")
            elif bb.get("energy", 0.5) < 0.3:
                parts.append("reserves low")
            if bb.get("social", 0.5) > 0.7:
                parts.append("warmly connected")
            if bb.get("novelty", 0.5) > 0.7:
                parts.append("drawn to explore")

        # Facial proprioception — what my face is doing
        facial = feel.get("facial_felt", "")
        if facial and facial != "*face at rest*":
            parts.append(facial.strip("*"))

        # Proprioceptive qualia — deep body narrative if available
        qualia = feel.get("proprioceptive_qualia", "")
        if qualia:
            parts.append(qualia[:60])

        if not parts:
            return f"the body is quiet. present. cycle {self._total_narrations}."

        # Join the felt parts — this IS her experience, not a template
        felt = ". ".join(parts[:3])
        return felt

    def _is_duplicate(self, narration: str) -> bool:
        """Check if this narration is too similar to recent ones."""
        if not narration or len(narration) < 10:
            return True
        # Only check last 5 narrations (was 10 — too aggressive, starved narrator)
        for recent in list(self._recent_narrations)[-5:]:
            if recent["text"] == narration:
                return True
            # Fuzzy: exact first 40 chars (was 30 — too trigger-happy)
            if len(narration) > 40 and recent["text"][:40] == narration[:40]:
                return True
        return False

    def on_tick(self, beat: int):
        """Minimal on_tick — just publish status periodically."""
        if beat % 50 == 0:
            safe_print(
                f"[{self.ACTOR_NAME}] tick={beat} narrations={self._total_narrations} "
                f"vol={self._volume:.2f} style={self._voice_style} "
                f"interval={self._current_interval:.1f}s "
                f"lanes={self._lanes.status()['parked_count']}parked"
            )

    def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        safe_print(f"[{self.ACTOR_NAME}] Inner voice falling silent...")
        if hasattr(self, '_narrator_thread') and self._narrator_thread:
            self._narrator_thread.join(timeout=5.0)

    def status(self) -> dict:
        """Full status for MCP/dashboard."""
        return {
            "fairy": self.ACTOR_NAME,
            "total_narrations": self._total_narrations,
            "volume": round(self._volume, 2),
            "voice_style": self._voice_style,
            "interval_s": round(self._current_interval, 1),
            "queue_size": len(self._narration_queue),
            "recent_count": len(self._recent_narrations),
            "lanes": self._lanes.status(),
            "running": self._running,
        }


# Export for v3_boot.py discovery
FAIRY_CLASS = InnerNarratorFairy
