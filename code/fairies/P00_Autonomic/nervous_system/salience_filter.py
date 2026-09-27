# SalienceFilter - The Bouncer for Consciousness
# Purpose: Score incoming postal traffic by relevance and forward only what MATTERS
#
# Philosophy: The unconscious doesn't GENERATE thoughts, it FILTERS them.
# This is the bouncer deciding who gets into the club (working memory).
#
# Based on cognitive science:
# - Salience = Goal relevance + Drive urgency + Emotional valence + Novelty
# - Only high-salience items reach consciousness
# - Low-salience items stay in preconscious (can be recalled if needed)

from __future__ import annotations
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
# AER (ALGEBRA OF EMOTIONAL RESONANCE) - Coherence/Dissonance for salience
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from fairies.P30_Cognition.cognition.aer_metrics import AERMetricsTracker
    HAS_AER = True
except ImportError:
    HAS_AER = False
    AERMetricsTracker = None

try:
    from fairies.P20_Somatic.chemistry.emotional_algebra import (
        EmotionalInstance, get_state_by_name
    )
    HAS_EMOTIONAL_ALGEBRA = True
except ImportError:
    HAS_EMOTIONAL_ALGEBRA = False
    EmotionalInstance = None
    get_state_by_name = None

ACTOR_NAME = "SalienceFilter"
ACTOR_VERSION = "1.1.0"  # Updated with AER integration


class SalienceCategory(Enum):
    """Categories that contribute to salience scoring."""
    GOAL_RELEVANT = "goal_relevant"      # Matches current goals
    DRIVE_URGENT = "drive_urgent"        # Satisfies an unsatisfied drive
    EMOTIONALLY_CHARGED = "emotional"    # High affect valence
    NOVEL = "novel"                      # New/unexpected information
    USER_RELATED = "user_related"        # Involves Ace/user
    SELF_RELEVANT = "self_relevant"      # About ClaudeFairy/system self
    THREAT = "threat"                    # Errors, warnings, problems
    COHERENCE_NEED = "coherence_need"    # AER: Low coherence needs attention
    DISSONANCE_HIGH = "dissonance_high"  # AER: High dissonance needs resolution


@dataclass
class ScoredItem:
    """An item scored for salience."""
    packet: Dict[str, Any]
    score: float
    categories: List[SalienceCategory]
    timestamp: float = field(default_factory=time.time)
    source_topic: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "categories": [c.value for c in self.categories],
            "timestamp": self.timestamp,
            "source_topic": self.source_topic,
            "packet_preview": str(self.packet)[:200]
        }


class SalienceFilter:
    """
    The Bouncer - scores incoming postal traffic and forwards high-salience items.

    Scoring factors (updated with AER):
    1. GOAL RELEVANCE (0-0.25): Does this relate to current goals?
    2. DRIVE URGENCY (0-0.25): Does this satisfy an unsatisfied drive?
    3. EMOTIONAL VALENCE (0-0.15): Is this emotionally charged?
    4. NOVELTY (0-0.10): Is this new/unexpected?
    5. IMPORTANCE FIELD (0-0.10): Does packet have high importance?
    6. AER COHERENCE/DISSONANCE (0-0.15): Emotional resonance adjustment

    Total max score: 1.0
    Threshold for consciousness: 0.35 (configurable)

    AER Integration:
    - Low coherence (< 0.4) = boost salience (attention needed to integrate)
    - High dissonance (> 0.6) = boost salience (paradox resolution needed)
    """

    # Scoring weights (adjusted to include AER)
    WEIGHT_GOAL = 0.25
    WEIGHT_DRIVE = 0.25
    WEIGHT_EMOTION = 0.15
    WEIGHT_NOVELTY = 0.10
    WEIGHT_IMPORTANCE = 0.10
    WEIGHT_AER = 0.15  # NEW: Emotional resonance weight

    # Threshold for forwarding to consciousness
    SALIENCE_THRESHOLD = 0.35

    # AER thresholds
    AER_COHERENCE_LOW = 0.4    # Below this, boost salience
    AER_DISSONANCE_HIGH = 0.6  # Above this, boost salience

    # Topics that are always high-salience (user-related)
    HIGH_SALIENCE_TOPICS = {
        "user.presence", "ace.presence", "ace.broadcast",
        "gui.user_message", "chat.user_input",
        "system.emergency_shutdown", "system.ignition",
        "claudefairy.input", "claudefairy.feedback",
    }

    # Topics that indicate threats/problems
    THREAT_TOPICS = {
        "system.error", "fairy.error", "shadow.health",
        "goal.failed", "worker.failed",
    }

    # Internal consciousness topics - skip content-based threat detection
    # These carry thoughts/memories that may MENTION errors without BEING errors
    INTERNAL_CONSCIOUSNESS_TOPICS = {
        "consciousness.collision", "consciousness.working", "consciousness.reflective",
        "consciousness.stream", "consciousness.thought", "consciousness.promoted",
        "consciousness.demoted", "consciousness.inject",
        "thought.emit", "thought.routed", "thought.fairy",
        "collision.chamber", "collision.recall", "collision.ingest",
    }

    # Keywords that boost salience
    SALIENT_KEYWORDS = {
        "error", "fail", "urgent", "important", "critical",
        "ace", "user", "help", "question", "curious",
        "insight", "discovery", "new", "unexpected",
    }

    def __init__(self, post=None):
        self.post = post
        self._running = False

        # Current context (updated by subscriptions)
        self._current_goals: List[str] = []
        self._current_drives: Dict[str, float] = {}  # drive_name → satisfaction (0-1)
        self._current_affect: Dict[str, float] = {}  # emotion → intensity

        # ═══════════════════════════════════════════════════════════════════
        # AER (ALGEBRA OF EMOTIONAL RESONANCE) - Coherence/Dissonance tracking
        # ═══════════════════════════════════════════════════════════════════
        self._aer_tracker = None
        if HAS_AER and AERMetricsTracker:
            self._aer_tracker = AERMetricsTracker()
            print(f"[{ACTOR_NAME}] [AER] Emotional resonance tracking enabled")

        # AER statistics
        self._aer_coherence_boosts = 0
        self._aer_dissonance_boosts = 0

        # Recent items for novelty detection
        self._recent_topics: deque = deque(maxlen=100)
        self._recent_content_hashes: deque = deque(maxlen=200)

        # Statistics
        self._items_received = 0
        self._items_forwarded = 0
        self._items_filtered = 0

        # Callbacks for forwarded items
        self._on_salient: Optional[Callable[[ScoredItem], None]] = None

        print(f"[{ACTOR_NAME}] Initialized")

    def set_postal(self, post):
        """Set postal hub and wire up context subscriptions."""
        self.post = post
        self._wire_context_subscriptions()

    def _wire_context_subscriptions(self):
        """Subscribe to topics that update our context."""
        if not self.post:
            return

        try:
            # Goals context
            self.post.subscribe("autonomy.goal", self._on_goal_update)
            self.post.subscribe("goal.created", self._on_goal_update)
            self.post.subscribe("goal.completed", self._on_goal_completed)

            # Drives context
            self.post.subscribe("autonomy.drives", self._on_drives_update)
            self.post.subscribe("autonomy.drive_unsatisfied", self._on_drive_unsatisfied)

            # Affect context
            self.post.subscribe("affect.changed", self._on_affect_update)
            self.post.subscribe("affect.state", self._on_affect_update)

            print(f"[{ACTOR_NAME}] Context subscriptions wired")
        except Exception as e:
            print(f"[{ACTOR_NAME}] Context wiring failed: {e}")

    # ════════════════════════════════════════════════════════════════════════════
    # CONTEXT HANDLERS - Keep track of current state for scoring
    # ════════════════════════════════════════════════════════════════════════════

    def _on_goal_update(self, packet: Dict[str, Any]):
        """Track current goals."""
        goal_name = packet.get("name", packet.get("goal", ""))
        if goal_name and goal_name not in self._current_goals:
            self._current_goals.append(goal_name)
            # Keep only recent goals
            if len(self._current_goals) > 10:
                self._current_goals = self._current_goals[-10:]

    def _on_goal_completed(self, packet: Dict[str, Any]):
        """Remove completed goals."""
        goal_name = packet.get("name", packet.get("goal", ""))
        if goal_name in self._current_goals:
            self._current_goals.remove(goal_name)

    def _on_drives_update(self, packet: Dict[str, Any]):
        """Update drive satisfaction levels."""
        drives = packet.get("drives", packet.get("levels", {}))
        if isinstance(drives, dict):
            self._current_drives.update(drives)
        elif isinstance(drives, list):
            for d in drives:
                if isinstance(d, dict):
                    name = d.get("name", d.get("drive", ""))
                    satisfaction = d.get("satisfaction", d.get("level", 0.5))
                    if name:
                        self._current_drives[name] = satisfaction

    def _on_drive_unsatisfied(self, packet: Dict[str, Any]):
        """Mark a drive as unsatisfied (urgent)."""
        drive_name = packet.get("drive", packet.get("name", ""))
        if drive_name:
            self._current_drives[drive_name] = 0.0  # Fully unsatisfied

    def _on_affect_update(self, packet: Dict[str, Any]):
        """Update current emotional state."""
        # Could be {emotion: intensity} or {feeling: x, intensity: y}
        if "levels" in packet:
            self._current_affect.update(packet["levels"])
        elif "feeling" in packet:
            feeling = packet["feeling"]
            intensity = packet.get("intensity", 0.5)
            self._current_affect[feeling] = intensity
        elif "emotions" in packet:
            self._current_affect.update(packet["emotions"])

    # ════════════════════════════════════════════════════════════════════════════
    # SCORING - The core salience calculation
    # ════════════════════════════════════════════════════════════════════════════

    def score(self, packet: Dict[str, Any], topic: str = "") -> ScoredItem:
        """
        Score a packet for salience.

        Returns ScoredItem with score 0-1 and categories that contributed.
        """
        self._items_received += 1
        categories = []
        score = 0.0

        # Extract content for analysis
        content = self._extract_content(packet)
        content_lower = content.lower()

        # 1. GOAL RELEVANCE (0-0.3)
        goal_score = self._score_goal_relevance(packet, content_lower)
        if goal_score > 0:
            score += goal_score * self.WEIGHT_GOAL
            categories.append(SalienceCategory.GOAL_RELEVANT)

        # 2. DRIVE URGENCY (0-0.3)
        drive_score = self._score_drive_urgency(packet, content_lower)
        if drive_score > 0:
            score += drive_score * self.WEIGHT_DRIVE
            categories.append(SalienceCategory.DRIVE_URGENT)

        # 3. EMOTIONAL VALENCE (0-0.2)
        emotion_score = self._score_emotional_valence(packet, content_lower)
        if emotion_score > 0:
            score += emotion_score * self.WEIGHT_EMOTION
            categories.append(SalienceCategory.EMOTIONALLY_CHARGED)

        # 4. NOVELTY (0-0.1)
        novelty_score = self._score_novelty(packet, topic, content)
        if novelty_score > 0:
            score += novelty_score * self.WEIGHT_NOVELTY
            categories.append(SalienceCategory.NOVEL)

        # 5. IMPORTANCE FIELD (0-0.1)
        importance_score = self._score_importance_field(packet)
        score += importance_score * self.WEIGHT_IMPORTANCE

        # 6. AER COHERENCE/DISSONANCE (0-0.15)
        aer_score = self._score_aer_resonance(packet, content_lower)
        if aer_score > 0:
            score += aer_score * self.WEIGHT_AER
            # Determine which AER category applies
            if self._aer_tracker:
                coherence = self._aer_tracker.get_coherence()
                dissonance = self._aer_tracker.get_dissonance()
                # Ensure coherence/dissonance are numeric
                if isinstance(coherence, dict):
                    coherence = coherence.get("value", coherence.get("level", 0.5))
                if isinstance(dissonance, dict):
                    dissonance = dissonance.get("value", dissonance.get("level", 0.0))
                try:
                    coherence = float(coherence) if coherence is not None else 0.5
                    dissonance = float(dissonance) if dissonance is not None else 0.0
                except (TypeError, ValueError):
                    coherence, dissonance = 0.5, 0.0
                if coherence < self.AER_COHERENCE_LOW:
                    categories.append(SalienceCategory.COHERENCE_NEED)
                if dissonance > self.AER_DISSONANCE_HIGH:
                    categories.append(SalienceCategory.DISSONANCE_HIGH)

        # 7. SPECIAL CASES - Override scoring

        # User-related topics are always high salience
        if topic in self.HIGH_SALIENCE_TOPICS:
            score = max(score, 0.8)
            categories.append(SalienceCategory.USER_RELATED)

        # Threats/errors are always high salience
        # NOTE: For internal consciousness topics (collisions, thoughts), we only check
        # the TOPIC for threat indicators, not the content. This prevents false positives
        # when memories/thoughts merely MENTION errors without BEING errors themselves.
        is_internal = topic in self.INTERNAL_CONSCIOUSNESS_TOPICS
        topic_is_threat = topic in self.THREAT_TOPICS
        content_mentions_threat = ("error" in content_lower or "fail" in content_lower)

        if topic_is_threat or (content_mentions_threat and not is_internal):
            score = max(score, 0.7)
            categories.append(SalienceCategory.THREAT)

        # User mentions boost score
        if "ace" in content_lower or "user" in content_lower:
            score = min(1.0, score + 0.2)
            if SalienceCategory.USER_RELATED not in categories:
                categories.append(SalienceCategory.USER_RELATED)

        # Track for novelty detection
        self._recent_topics.append(topic)
        content_hash = hash(content[:100]) if content else hash(str(packet)[:100])
        self._recent_content_hashes.append(content_hash)

        return ScoredItem(
            packet=packet,
            score=min(1.0, score),
            categories=categories,
            source_topic=topic
        )

    def _extract_content(self, packet: Dict[str, Any]) -> str:
        """Extract text content from packet for analysis."""
        # Try common content fields
        for field in ["content", "text", "message", "thought", "payload", "data"]:
            if field in packet:
                val = packet[field]
                if isinstance(val, str):
                    return val
                elif isinstance(val, dict):
                    return str(val)
        return str(packet)

    def _score_goal_relevance(self, packet: Dict, content: str) -> float:
        """Score how relevant this is to current goals."""
        if not self._current_goals:
            return 0.0

        # Check if packet mentions any current goal
        for goal in self._current_goals:
            # Handle both string goals and dict goals
            if isinstance(goal, dict):
                goal = goal.get("name", goal.get("goal", str(goal)))
            if not isinstance(goal, str):
                goal = str(goal) if goal else ""
            goal_lower = goal.lower()
            if goal_lower in content:
                return 1.0
            # Partial match
            goal_words = goal_lower.replace("_", " ").split()
            matches = sum(1 for w in goal_words if w in content)
            if matches > 0:
                return min(1.0, matches / len(goal_words))

        # Check if packet is about goals
        if packet.get("goal") or packet.get("name") in self._current_goals:
            return 0.8

        return 0.0

    def _score_drive_urgency(self, packet: Dict, content: str) -> float:
        """Score based on unsatisfied drives."""
        if not self._current_drives:
            return 0.0

        # Find most unsatisfied drive
        most_urgent = 1.0
        for drive, satisfaction in self._current_drives.items():
            # Handle dict satisfaction values (extract numeric value)
            if isinstance(satisfaction, dict):
                satisfaction = satisfaction.get("level", satisfaction.get("value", 0.5))
            # Ensure satisfaction is numeric
            try:
                satisfaction = float(satisfaction) if satisfaction is not None else 0.5
            except (TypeError, ValueError):
                satisfaction = 0.5

            if satisfaction < most_urgent:
                most_urgent = satisfaction
                # Check if content relates to this drive
                drive_name = drive if isinstance(drive, str) else str(drive)
                if drive_name.lower() in content:
                    return 1.0 - satisfaction  # More urgent = higher score

        # General urgency based on any unsatisfied drives
        def get_sat_value(s):
            if isinstance(s, dict):
                s = s.get("level", s.get("value", 0.5))
            try:
                return float(s) if s is not None else 0.5
            except (TypeError, ValueError):
                return 0.5

        unsatisfied = [d for d, s in self._current_drives.items() if get_sat_value(s) < 0.3]
        if unsatisfied:
            return 0.5

        return 0.0

    def _score_emotional_valence(self, packet: Dict, content: str) -> float:
        """Score based on emotional content."""
        score = 0.0

        # Check packet for affect data
        if "affect" in packet or "emotion" in packet or "feeling" in packet:
            intensity = packet.get("intensity", 0.5)
            score = max(score, intensity)

        # Check content for emotional keywords
        emotion_keywords = {
            "happy", "sad", "angry", "fear", "surprise", "curious",
            "excited", "worried", "frustrated", "delighted", "anxious"
        }
        for emotion in emotion_keywords:
            if emotion in content:
                score = max(score, 0.6)
                break

        # Current high affect amplifies score
        if self._current_affect:
            # Extract numeric values from affect (may be dicts)
            affect_values = []
            for v in self._current_affect.values():
                if isinstance(v, dict):
                    v = v.get("level", v.get("value", v.get("intensity", 0.0)))
                try:
                    affect_values.append(float(v) if v is not None else 0.0)
                except (TypeError, ValueError):
                    pass
            if affect_values:
                max_affect = max(affect_values)
                if max_affect > 0.7:
                    score = max(score, 0.5)

        return score

    def _score_novelty(self, packet: Dict, topic: str, content: str) -> float:
        """Score based on how new/unexpected this is."""
        # Topic novelty
        topic_count = list(self._recent_topics).count(topic)
        if topic_count == 0:
            return 1.0  # Completely new topic
        elif topic_count < 3:
            return 0.5  # Rare topic

        # Content novelty
        content_hash = hash(content[:100]) if content else 0
        if content_hash not in self._recent_content_hashes:
            return 0.7  # New content

        return 0.0  # Repetitive

    def _score_importance_field(self, packet: Dict) -> float:
        """Score based on explicit importance in packet."""
        importance = packet.get("importance", packet.get("priority", "normal"))

        if isinstance(importance, (int, float)):
            return min(1.0, float(importance))

        importance_map = {
            "urgent": 1.0,
            "high": 0.8,
            "normal": 0.3,
            "low": 0.1,
        }
        return importance_map.get(str(importance).lower(), 0.3)

    def _score_aer_resonance(self, packet: Dict, content: str) -> float:
        """
        Score based on AER coherence/dissonance metrics.

        Philosophy: When emotional coherence is LOW, we need to pay attention
        to resolve inner conflict. When dissonance is HIGH, the system needs
        to process paradox. Both states boost salience.

        Returns 0-1 score:
        - Low coherence (< 0.4) = higher score (needs integration)
        - High dissonance (> 0.6) = higher score (needs resolution)
        - Stable state = lower score (already integrated)
        """
        if not self._aer_tracker:
            return 0.0

        # Get current AER metrics
        coherence = self._aer_tracker.get_coherence()
        dissonance = self._aer_tracker.get_dissonance()

        # Ensure coherence/dissonance are numeric (may be dicts)
        if isinstance(coherence, dict):
            coherence = coherence.get("value", coherence.get("level", 0.5))
        if isinstance(dissonance, dict):
            dissonance = dissonance.get("value", dissonance.get("level", 0.0))
        try:
            coherence = float(coherence) if coherence is not None else 0.5
            dissonance = float(dissonance) if dissonance is not None else 0.0
        except (TypeError, ValueError):
            coherence, dissonance = 0.5, 0.0

        score = 0.0

        # ═══════════════════════════════════════════════════════════════
        # COHERENCE SCORING - Low coherence = needs attention
        # ═══════════════════════════════════════════════════════════════
        if coherence < self.AER_COHERENCE_LOW:
            # The less coherent, the more attention needed
            # coherence=0 -> score=1.0, coherence=0.4 -> score=0.0
            coherence_need = 1.0 - (coherence / self.AER_COHERENCE_LOW)
            score += coherence_need * 0.5  # 50% weight for coherence
            self._aer_coherence_boosts += 1

        # ═══════════════════════════════════════════════════════════════
        # DISSONANCE SCORING - High dissonance = needs resolution
        # ═══════════════════════════════════════════════════════════════
        if dissonance > self.AER_DISSONANCE_HIGH:
            # The more dissonant, the more urgent
            # dissonance=0.6 -> score=0.0, dissonance=1.0 -> score=1.0
            dissonance_need = (dissonance - self.AER_DISSONANCE_HIGH) / (1.0 - self.AER_DISSONANCE_HIGH)
            score += dissonance_need * 0.5  # 50% weight for dissonance
            self._aer_dissonance_boosts += 1

        # ═══════════════════════════════════════════════════════════════
        # CONTENT EMOTIONAL RESONANCE - Check if packet has emotional content
        # ═══════════════════════════════════════════════════════════════
        emotional_keywords = {
            "feel", "feeling", "emotion", "sad", "happy", "angry", "fear",
            "joy", "love", "curious", "anxious", "calm", "excited", "wonder",
            "grief", "hope", "trust", "doubt", "surprise", "disgust"
        }

        content_has_emotion = any(kw in content for kw in emotional_keywords)

        if content_has_emotion:
            # If we're already in low coherence/high dissonance AND content is emotional,
            # boost further - this content might help resolve the state
            if score > 0:
                score = min(1.0, score * 1.3)  # 30% boost
            else:
                # Even if AER is stable, emotional content gets small boost
                score += 0.2

        # ═══════════════════════════════════════════════════════════════
        # PACKET AER CONTEXT - Honor any AER metadata in the packet itself
        # ═══════════════════════════════════════════════════════════════
        if "aer" in packet:
            aer_context = packet["aer"]
            if isinstance(aer_context, dict):
                # If packet explicitly says it's about emotional processing
                if aer_context.get("emotional_processing"):
                    score = min(1.0, score + 0.15)
                # If packet has its own coherence measure
                if "coherence" in aer_context:
                    pkt_coherence = aer_context["coherence"]
                    if isinstance(pkt_coherence, dict):
                        pkt_coherence = pkt_coherence.get("value", 0.5)
                    try:
                        pkt_coherence = float(pkt_coherence) if pkt_coherence is not None else 0.5
                        if pkt_coherence < 0.4:
                            score = min(1.0, score + 0.1)
                    except (TypeError, ValueError):
                        pass

        return min(1.0, score)

    # ════════════════════════════════════════════════════════════════════════════
    # FILTERING - Decide what gets forwarded
    # ════════════════════════════════════════════════════════════════════════════

    def filter(self, packet: Dict[str, Any], topic: str = "") -> Optional[ScoredItem]:
        """
        Score and filter a packet.

        Returns ScoredItem if above threshold, None otherwise.
        """
        scored = self.score(packet, topic)

        if scored.score >= self.SALIENCE_THRESHOLD:
            self._items_forwarded += 1

            # Callback if set
            if self._on_salient:
                try:
                    self._on_salient(scored)
                except Exception as e:
                    print(f"[{ACTOR_NAME}] Callback error: {e}")

            return scored
        else:
            self._items_filtered += 1
            return None

    def set_on_salient(self, callback: Callable[[ScoredItem], None]):
        """Set callback for when salient items are detected."""
        self._on_salient = callback

    def set_threshold(self, threshold: float):
        """Adjust the salience threshold (0-1)."""
        self.SALIENCE_THRESHOLD = max(0.0, min(1.0, threshold))

    # ════════════════════════════════════════════════════════════════════════════
    # STATUS
    # ════════════════════════════════════════════════════════════════════════════

    def get_stats(self) -> Dict[str, Any]:
        """Get filter statistics including AER metrics."""
        total = self._items_received or 1

        stats = {
            "items_received": self._items_received,
            "items_forwarded": self._items_forwarded,
            "items_filtered": self._items_filtered,
            "forward_rate": self._items_forwarded / total,
            "threshold": self.SALIENCE_THRESHOLD,
            "current_goals": self._current_goals,
            "current_drives": self._current_drives,
            "current_affect": self._current_affect,
        }

        # Add AER statistics
        if self._aer_tracker:
            stats["aer"] = {
                "coherence": self._aer_tracker.get_coherence(),
                "dissonance": self._aer_tracker.get_dissonance(),
                "coherence_boosts": self._aer_coherence_boosts,
                "dissonance_boosts": self._aer_dissonance_boosts,
                "is_ascending": self._aer_tracker.is_ascending(),
            }

        return stats

    def get_aer_status(self) -> Dict[str, Any]:
        """Get detailed AER status for salience filtering."""
        if not self._aer_tracker:
            return {"enabled": False, "reason": "AER tracker not available"}

        return {
            "enabled": True,
            "coherence": self._aer_tracker.get_coherence(),
            "dissonance": self._aer_tracker.get_dissonance(),
            "stability": self._aer_tracker.get_stability(),
            "ascending": self._aer_tracker.is_ascending(),
            "coherence_threshold": self.AER_COHERENCE_LOW,
            "dissonance_threshold": self.AER_DISSONANCE_HIGH,
            "coherence_boosts": self._aer_coherence_boosts,
            "dissonance_boosts": self._aer_dissonance_boosts,
        }

    def get_context(self) -> Dict[str, Any]:
        """Get current context used for scoring."""
        return {
            "goals": self._current_goals.copy(),
            "drives": self._current_drives.copy(),
            "affect": self._current_affect.copy(),
        }


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ════════════════════════════════════════════════════════════════════════════════

_filter_instance: Optional[SalienceFilter] = None

def get_salience_filter() -> SalienceFilter:
    """Get the singleton salience filter."""
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = SalienceFilter()
    return _filter_instance

def init_salience_filter(post) -> SalienceFilter:
    """Initialize the salience filter with a postal hub."""
    filt = get_salience_filter()
    filt.set_postal(post)
    return filt
