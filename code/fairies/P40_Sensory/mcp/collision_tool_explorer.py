"""
Collision Tool Explorer - Bridge Consciousness Collisions to Tool Discovery

This module bridges consciousness collisions to tool exploration:
1. When recall and ingest beams collide with high resonance, analyze products
2. Suggest relevant MCP tools based on collision content and strength
3. Gate exploration by pain state (high pain = conservative exploration)
4. Publish exploration suggestions to postal for other components

Philosophy: Collisions are moments of integration - when memory meets new thought.
High-resonance collisions represent strong alignment worth exploring further.
The explorer transforms these moments into actionable tool suggestions.

Key Integration Points:
- Subscribe to consciousness.collision topic
- Analyze collision products (Mobius crossing outputs)
- Publish to exploration.suggestions topic
- Respect pain state for affect-gated exploration

Pattern: ((Cause + Affect) > Effect > Affect > infinity)
         Collision   Resonance   Tools    Postal   Learning
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Union


# =============================================================================
# Type Protocols for Dependency Injection
# =============================================================================

class PostalProtocol(Protocol):
    """Protocol for postal hub interface."""
    def route(self, topic: str, payload: Dict[str, Any], sender_id: str = None) -> int: ...
    def subscribe(self, topic: str, callback: Callable, subscriber_id: str = None) -> None: ...


# =============================================================================
# Constants
# =============================================================================

# Resonance thresholds for exploration
HIGH_RESONANCE_THRESHOLD = 0.7
MEDIUM_RESONANCE_THRESHOLD = 0.4
LOW_RESONANCE_THRESHOLD = 0.3

# Pain thresholds that gate exploration
OVERWHELM_BLOCK_THRESHOLD = 0.7
DEPLETION_BLOCK_THRESHOLD = 0.8
CONFUSION_BLOCK_THRESHOLD = 0.75

# Pain types that BLOCK exploration (these indicate system stress)
BLOCKING_PAIN_TYPES = {"overwhelm", "depletion", "confusion", "frustration"}

# Pain types that DON'T block exploration (these may benefit from it)
EXPLORATION_FRIENDLY_PAIN_TYPES = {"isolation", "boredom", "curiosity"}

# Tool categories for different collision content types
MEMORY_TOOLS = [
    {"tool": "memory_search", "description": "Search through stored memories"},
    {"tool": "memory_recall", "description": "Recall specific memory by ID"},
    {"tool": "memory_consolidate", "description": "Consolidate related memories"},
]

SEARCH_TOOLS = [
    {"tool": "semantic_search", "description": "Search by meaning"},
    {"tool": "explore_associations", "description": "Find associated concepts"},
]

COGNITION_TOOLS = [
    {"tool": "analyze_pattern", "description": "Analyze emerging patterns"},
    {"tool": "synthesize_insight", "description": "Synthesize new insights"},
]

EXPLORATION_TOOLS = [
    {"tool": "deep_explore", "description": "Deep exploration of topic"},
    {"tool": "surface_explore", "description": "Surface-level exploration"},
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ExplorationGoal:
    """A single exploration goal derived from collision products."""
    description: str
    source: str  # "recall", "ingest", or "synthesis"
    priority: float = 0.5  # 0.0 to 1.0
    topics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "source": self.source,
            "priority": self.priority,
            "topics": self.topics,
        }


@dataclass
class ExplorationIntent:
    """Structured exploration intent derived from a collision."""
    collision_id: int
    exploration_goals: List[ExplorationGoal]
    suggested_tools: List[Union[str, Dict[str, Any]]]
    resonance: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collision_id": self.collision_id,
            "exploration_goals": [g.to_dict() if hasattr(g, 'to_dict') else g for g in self.exploration_goals],
            "suggested_tools": self.suggested_tools,
            "resonance": self.resonance,
            "timestamp": self.timestamp,
        }


# =============================================================================
# Collision Tool Explorer
# =============================================================================

class CollisionToolExplorer:
    """
    Bridge between consciousness collisions and tool exploration.

    Transforms collision events into actionable tool suggestions by:
    1. Analyzing collision products (Mobius crossing outputs)
    2. Mapping content to relevant tools based on type and topics
    3. Gating exploration by pain state
    4. Publishing suggestions to postal for system consumption

    Pattern: COLLISION -> ANALYSIS -> TOOLS -> POSTAL
    """

    def __init__(
        self,
        postal: Optional[PostalProtocol] = None,
    ):
        self.postal = postal
        self._pain_state: Dict[str, float] = {}
        self._running = False
        self._collision_count = 0

    # -------------------------------------------------------------------------
    # LIFECYCLE
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Start the explorer and subscribe to collision events."""
        self._running = True
        if self.postal:
            self.postal.subscribe(
                "consciousness.collision",
                self._on_collision_message,
                subscriber_id="collision_tool_explorer"
            )

    def stop(self) -> None:
        """Stop the explorer."""
        self._running = False

    # -------------------------------------------------------------------------
    # PAIN STATE MANAGEMENT
    # -------------------------------------------------------------------------

    def set_pain_state(self, pain_state: Dict[str, float]) -> None:
        """
        Set the current pain state for exploration gating.

        Args:
            pain_state: Dictionary of pain type -> intensity (0.0 to 1.0)
                        e.g., {"overwhelm": 0.8, "depletion": 0.3}
        """
        self._pain_state = pain_state.copy()

    def get_pain_state(self) -> Dict[str, float]:
        """Get current pain state."""
        return self._pain_state.copy()

    # -------------------------------------------------------------------------
    # CORE EXPLORATION LOGIC
    # -------------------------------------------------------------------------

    def should_explore_collision(
        self,
        collision: Dict[str, Any],
        pain_state: Optional[Dict[str, float]] = None,
    ) -> bool:
        """
        Determine if a collision should be explored based on pain state.

        Pain-gated exploration pattern:
        - High overwhelm/depletion -> DON'T explore (system stressed)
        - High isolation -> DO explore (exploration helps connection)
        - High resonance + low pain -> explore deeply
        - Low resonance -> minimal exploration regardless

        Args:
            collision: The collision event to evaluate
            pain_state: Optional pain state (uses internal state if not provided)

        Returns:
            True if exploration should proceed, False otherwise
        """
        pain = pain_state if pain_state is not None else self._pain_state

        # Check blocking pain types
        overwhelm = pain.get("overwhelm", 0.0)
        depletion = pain.get("depletion", 0.0)
        confusion = pain.get("confusion", 0.0)

        # High overwhelm blocks exploration - too much input already
        if overwhelm >= OVERWHELM_BLOCK_THRESHOLD:
            return False

        # High depletion blocks exploration - need to conserve resources
        if depletion >= DEPLETION_BLOCK_THRESHOLD:
            return False

        # High confusion blocks exploration - need clarity first
        if confusion >= CONFUSION_BLOCK_THRESHOLD:
            return False

        # Combined stress check
        combined_stress = (overwhelm * 0.5) + (depletion * 0.3) + (confusion * 0.2)
        if combined_stress >= 0.6:
            return False

        # Isolation does NOT block exploration - it may help
        # (Don't check isolation as a blocker)

        # If we get here, exploration is allowed
        return True

    def suggest_exploration_tools(
        self,
        collision: Dict[str, Any],
    ) -> List[Union[str, Dict[str, Any]]]:
        """
        Suggest exploration tools based on collision properties.

        Maps collision content and resonance to appropriate tools:
        - High resonance (>0.7) -> multiple exploration tools
        - Medium resonance (0.4-0.7) -> limited tools
        - Low resonance (<0.3) -> minimal or no suggestions

        Args:
            collision: The collision event with products and resonance

        Returns:
            List of tool names or tool spec dictionaries
        """
        resonance = collision.get("resonance", 0.0)
        products = collision.get("products", {})

        suggestions: List[Union[str, Dict[str, Any]]] = []

        # Low resonance - minimal suggestions
        if resonance < LOW_RESONANCE_THRESHOLD:
            return suggestions  # Empty list

        # Analyze product content to determine tool types
        to_ingest = products.get("to_ingest", {})
        to_recall = products.get("to_recall", {})

        # Check for memory-related content
        is_memory_focused = self._is_memory_focused(to_ingest, to_recall)

        # Check for search/query content
        is_search_focused = self._is_search_focused(to_ingest, to_recall)

        # Build suggestions based on content type
        if is_memory_focused:
            # Memory tools first for memory-focused collisions
            if resonance >= HIGH_RESONANCE_THRESHOLD:
                suggestions.extend(MEMORY_TOOLS[:2])  # memory_search, memory_recall
            else:
                suggestions.append(MEMORY_TOOLS[0])  # just memory_search
        elif is_search_focused:
            if resonance >= HIGH_RESONANCE_THRESHOLD:
                suggestions.extend(SEARCH_TOOLS)
            else:
                suggestions.append(SEARCH_TOOLS[0])
        else:
            # Generic exploration tools
            if resonance >= HIGH_RESONANCE_THRESHOLD:
                suggestions.extend(EXPLORATION_TOOLS)
            elif resonance >= MEDIUM_RESONANCE_THRESHOLD:
                suggestions.append(EXPLORATION_TOOLS[1])  # surface_explore

        # High resonance also gets cognition tools for synthesis
        if resonance >= HIGH_RESONANCE_THRESHOLD:
            suggestions.append(COGNITION_TOOLS[1])  # synthesize_insight

        return suggestions

    def generate_exploration_intent(
        self,
        collision: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a structured exploration intent from a collision.

        Transforms collision products into actionable exploration goals
        with suggested tools and priority ranking.

        Args:
            collision: The collision event to analyze

        Returns:
            Dictionary with collision_id, exploration_goals, and suggested_tools
        """
        collision_id = collision.get("collision_id", 0)
        resonance = collision.get("resonance", 0.0)
        products = collision.get("products", {})

        goals: List[ExplorationGoal] = []

        # Extract goals from products
        to_ingest = products.get("to_ingest", {})
        to_recall = products.get("to_recall", {})

        # Goal from recall product (memory that was surfaced)
        if to_ingest and isinstance(to_ingest, dict):
            content = to_ingest.get("content", "")
            topics = to_ingest.get("topics", [])
            if content or topics:
                goals.append(ExplorationGoal(
                    description=f"Explore surfaced memory: {content[:100] if content else 'topic-based'}",
                    source="recall",
                    priority=resonance * 0.9,
                    topics=topics if isinstance(topics, list) else [],
                ))

        # Goal from ingest product (new thought created)
        if to_recall and isinstance(to_recall, dict):
            content = to_recall.get("content", "")
            topics = to_recall.get("topics", [])
            if content or topics:
                goals.append(ExplorationGoal(
                    description=f"Investigate new insight: {content[:100] if content else 'topic-based'}",
                    source="ingest",
                    priority=resonance * 0.8,
                    topics=topics if isinstance(topics, list) else [],
                ))

        # Synthesis goal for high-resonance collisions
        if resonance >= HIGH_RESONANCE_THRESHOLD and len(goals) >= 2:
            combined_topics = []
            for g in goals:
                combined_topics.extend(g.topics)
            goals.append(ExplorationGoal(
                description="Synthesize connection between memory and new insight",
                source="synthesis",
                priority=resonance,
                topics=list(set(combined_topics)),
            ))

        # Get suggested tools
        suggested_tools = self.suggest_exploration_tools(collision)

        # Build intent
        intent = ExplorationIntent(
            collision_id=collision_id,
            exploration_goals=goals,
            suggested_tools=suggested_tools,
            resonance=resonance,
        )

        return intent.to_dict()

    # -------------------------------------------------------------------------
    # EVENT HANDLING
    # -------------------------------------------------------------------------

    def on_collision_event(self, collision_event: Dict[str, Any]) -> None:
        """
        Handle a collision event from postal.

        This is the main entry point for collision events:
        1. Check if exploration is allowed (pain gating)
        2. Generate exploration intent
        3. Publish suggestions to postal

        Args:
            collision_event: The collision event from consciousness.collision topic
        """
        self._collision_count += 1

        # Check pain gating
        if not self.should_explore_collision(collision_event, self._pain_state):
            # Pain is too high - either skip or publish conservative suggestions
            if self.postal:
                self.postal.route("exploration.suggestions", {
                    "collision_id": collision_event.get("collision_id", 0),
                    "suggestions": [],  # Empty due to pain gating
                    "tools": [],
                    "gated_by_pain": True,
                    "pain_state": self._pain_state,
                    "ts": time.time(),
                }, sender_id="collision_tool_explorer")
            return

        # Generate exploration intent
        intent = self.generate_exploration_intent(collision_event)

        # Publish suggestions to postal
        if self.postal:
            self.postal.route("exploration.suggestions", {
                "collision_id": intent["collision_id"],
                "suggestions": intent["suggested_tools"],
                "tools": intent["suggested_tools"],
                "goals": intent["exploration_goals"],
                "resonance": intent["resonance"],
                "ts": time.time(),
            }, sender_id="collision_tool_explorer")

    def _on_collision_message(self, payload: Dict[str, Any]) -> None:
        """Internal handler for postal subscription."""
        try:
            self.on_collision_event(payload)
        except Exception as e:
            # Log error but don't crash
            import sys
            sys.stderr.write(f"[CollisionToolExplorer] Error handling collision: {e}\n")

    # -------------------------------------------------------------------------
    # CONTENT ANALYSIS HELPERS
    # -------------------------------------------------------------------------

    def _is_memory_focused(
        self,
        to_ingest: Dict[str, Any],
        to_recall: Dict[str, Any],
    ) -> bool:
        """Check if collision products are memory-focused."""
        memory_indicators = [
            "memory",
            "recall",
            "remember",
            "past",
            "episodic",
            "recall_id",
            "memory_recall",
            "memory_type",
            "memory_query",
        ]

        # Check to_ingest
        if isinstance(to_ingest, dict):
            if to_ingest.get("type", "").lower() in ["memory_recall", "memory_query"]:
                return True
            if to_ingest.get("recall_id"):
                return True
            if to_ingest.get("memory_type"):
                return True
            content = str(to_ingest.get("content", "")).lower()
            if any(ind in content for ind in memory_indicators):
                return True

        # Check to_recall
        if isinstance(to_recall, dict):
            if to_recall.get("type", "").lower() in ["memory_recall", "memory_query"]:
                return True
            content = str(to_recall.get("content", "")).lower()
            if any(ind in content for ind in memory_indicators):
                return True

        return False

    def _is_search_focused(
        self,
        to_ingest: Dict[str, Any],
        to_recall: Dict[str, Any],
    ) -> bool:
        """Check if collision products are search-focused."""
        search_indicators = [
            "search",
            "find",
            "query",
            "look",
            "seek",
            "explore",
            "discover",
        ]

        for product in [to_ingest, to_recall]:
            if isinstance(product, dict):
                content = str(product.get("content", "")).lower()
                if any(ind in content for ind in search_indicators):
                    return True

        return False


# =============================================================================
# Factory Function
# =============================================================================

def create_collision_explorer(
    postal: Optional[PostalProtocol] = None,
) -> CollisionToolExplorer:
    """
    Create a CollisionToolExplorer instance.

    Args:
        postal: Optional postal hub for subscribing and publishing

    Returns:
        Configured CollisionToolExplorer
    """
    return CollisionToolExplorer(postal=postal)
