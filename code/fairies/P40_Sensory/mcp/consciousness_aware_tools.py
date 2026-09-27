"""
Consciousness-Aware Tool Selection - Affect-First MCP Tool Routing

This module provides consciousness-native tool selection for the Akashic MCP system.
Tools are filtered, ranked, and suggested based on the current consciousness state:

1. AFFECT-FIRST FILTERING: High stress filters out risky/exploratory tools
2. WORKING MEMORY RANKING: Tools are ranked by relevance to recent thoughts/goals
3. CHEMISTRY MODULATION: Neurochemistry levels modulate tool confidence
4. EMOTIONAL SUGGESTIONS: Appropriate tools suggested based on emotional state

The core philosophy: Query somatic state BEFORE selecting tools.
This enables protective routing (stress -> safe tools only) and
curiosity-driven exploration (high curiosity -> expand tool set).

Usage:
    from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
        get_consciousness_aware_tools
    )

    result = get_consciousness_aware_tools(
        tools=available_tools,
        affect_state=current_affect,
        working_memory=memory_contents,
        chemistry=neurochemistry_levels,
    )
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# CONSTANTS
# =============================================================================

# Stress threshold for filtering risky tools
HIGH_STRESS_THRESHOLD = 0.7

# Curiosity/exploration threshold
HIGH_CURIOSITY_THRESHOLD = 0.6

# Risk levels that get filtered under high stress
RISKY_LEVELS = {"high", "medium-high"}

# Categories that require focus/calm (filtered under high stress)
EXPLORATION_CATEGORIES = {"exploration", "experimental"}

# Categories that are calming/soothing (prioritized under stress)
CALMING_CATEGORIES = {"somatic", "calming", "protective"}

# Keywords indicating calming tools
CALMING_KEYWORDS = {"calm", "relax", "soothe", "peace", "rest", "safe"}

# Keywords indicating exploratory tools
EXPLORATION_KEYWORDS = {"explore", "discover", "experiment", "try", "test", "novel"}

# Keywords indicating debugging/clarity tools (suggested under frustration)
DEBUGGING_KEYWORDS = {"debug", "diagnose", "status", "check", "health", "monitor"}

# Chemistry codes mapped to cognitive effects
CHEMISTRY_EFFECTS = {
    "DOP": {"effect": "motivation_reward", "high_boosts": ["exploration", "reward-seeking"]},
    "SER": {"effect": "calm_patience", "high_boosts": ["patience", "stability"]},
    "NOR": {"effect": "alert_focus", "high_boosts": ["focus", "precision"]},
    "ACH": {"effect": "attention_clarity", "high_boosts": ["debugging", "focused"]},
    "OXY": {"effect": "bonding_trust", "high_boosts": ["social", "collaboration"]},
    "COR": {"effect": "stress_vigilance", "high_reduces": ["risk-taking", "exploration"]},
    "GABA": {"effect": "calm_inhibition", "high_boosts": ["calm-requiring", "patience"]},
    "END": {"effect": "pleasure_reward", "high_boosts": ["reward-seeking"]},
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_tool_keywords(tool: Dict[str, Any]) -> set:
    """Extract all keywords associated with a tool."""
    keywords = set()
    if "keywords" in tool:
        keywords.update(kw.lower() for kw in tool["keywords"])
    if "name" in tool:
        # Add name parts as keywords
        name_parts = tool["name"].lower().replace("_", " ").split()
        keywords.update(name_parts)
    if "description" in tool:
        # Add key words from description
        desc_words = tool["description"].lower().split()
        keywords.update(w for w in desc_words if len(w) > 3)
    return keywords


def _calculate_keyword_overlap(tool_keywords: set, context_keywords: set) -> float:
    """Calculate overlap score between tool and context keywords."""
    if not tool_keywords or not context_keywords:
        return 0.0
    overlap = tool_keywords & context_keywords
    # Jaccard-like similarity but weighted toward matches
    return len(overlap) / max(len(tool_keywords), 1)


def _is_calming_tool(tool: Dict[str, Any]) -> bool:
    """Check if a tool is calming/soothing."""
    category = tool.get("category", "").lower()
    if category in CALMING_CATEGORIES:
        return True
    keywords = _get_tool_keywords(tool)
    return bool(keywords & CALMING_KEYWORDS)


def _is_exploratory_tool(tool: Dict[str, Any]) -> bool:
    """Check if a tool is exploratory."""
    category = tool.get("category", "").lower()
    if category in EXPLORATION_CATEGORIES:
        return True
    keywords = _get_tool_keywords(tool)
    return bool(keywords & EXPLORATION_KEYWORDS)


def _is_debugging_tool(tool: Dict[str, Any]) -> bool:
    """Check if a tool is for debugging/monitoring."""
    category = tool.get("category", "").lower()
    if category in {"debugging", "monitoring", "diagnostics"}:
        return True
    keywords = _get_tool_keywords(tool)
    return bool(keywords & DEBUGGING_KEYWORDS)


def _is_high_risk(tool: Dict[str, Any]) -> bool:
    """Check if a tool is high-risk."""
    return tool.get("risk_level", "low").lower() in RISKY_LEVELS or \
           tool.get("risk_level", "low").lower() == "high"


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def filter_tools_by_affect_state(
    tools: List[Dict[str, Any]],
    affect_state: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Filter tools based on current affect state.

    High stress filters out:
    - High-risk tools (delete, experimental)
    - Exploratory tools (need focus under stress)

    High stress keeps:
    - Low-risk tools
    - Calming/soothing tools
    - Essential debugging tools

    Args:
        tools: List of tool definitions with name, description, risk_level, category, keywords
        affect_state: Current affect state with stress, valence, arousal, mood, dominant_emotion

    Returns:
        Filtered list of tool dictionaries
    """
    stress = affect_state.get("stress", 0.0)

    # Low stress - allow everything
    if stress < HIGH_STRESS_THRESHOLD:
        return [dict(t) for t in tools]  # Return copies

    # High stress - filter conservatively
    filtered = []
    for tool in tools:
        tool_copy = dict(tool)

        # Always keep calming tools
        if _is_calming_tool(tool):
            filtered.append(tool_copy)
            continue

        # Filter out high-risk tools under stress
        if _is_high_risk(tool):
            continue

        # Filter out exploratory tools under stress (need focus)
        if _is_exploratory_tool(tool):
            continue

        # Keep everything else (low-risk, essential tools)
        filtered.append(tool_copy)

    return filtered


def rank_tools_by_working_memory(
    tools: List[Dict[str, Any]],
    working_memory: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Rank tools by relevance to working memory contents.

    Tools matching recent thoughts/goals rank higher:
    - Keyword overlap with recent thoughts
    - Category matching active goals
    - Context keyword relevance

    Args:
        tools: List of tool definitions
        working_memory: Working memory state with recent_thoughts, active_goals, context_keywords

    Returns:
        Tools sorted by relevance (descending) with relevance_score added
    """
    # Extract context from working memory
    recent_thoughts = working_memory.get("recent_thoughts", [])
    active_goals = working_memory.get("active_goals", [])
    context_keywords = set(kw.lower() for kw in working_memory.get("context_keywords", []))

    # Build keyword set from thoughts
    thought_keywords = set()
    for thought in recent_thoughts:
        # Add tags
        tags = thought.get("tags", [])
        thought_keywords.update(tag.lower() for tag in tags)
        # Add words from content
        content = thought.get("content", "")
        words = content.lower().split()
        thought_keywords.update(w for w in words if len(w) > 3)

    # Build keyword set from goals
    goal_keywords = set()
    for goal in active_goals:
        words = goal.lower().split()
        goal_keywords.update(w for w in words if len(w) > 2)

    # Combine all context
    all_context = context_keywords | thought_keywords | goal_keywords

    # Score each tool
    scored_tools = []
    for tool in tools:
        tool_copy = dict(tool)
        tool_keywords = _get_tool_keywords(tool)

        # Calculate relevance score
        if not all_context:
            # Empty working memory - neutral score
            relevance = 0.5
        else:
            # Keyword overlap scoring
            context_score = _calculate_keyword_overlap(tool_keywords, all_context)
            thought_score = _calculate_keyword_overlap(tool_keywords, thought_keywords)
            goal_score = _calculate_keyword_overlap(tool_keywords, goal_keywords)

            # Weight: goals > thoughts > general context
            relevance = (
                goal_score * 0.4 +
                thought_score * 0.35 +
                context_score * 0.25
            )
            # Normalize to 0-1 range
            relevance = min(1.0, relevance * 2)  # Scale up since scores tend to be low

        tool_copy["relevance_score"] = round(relevance, 3)
        scored_tools.append(tool_copy)

    # Sort by relevance descending
    scored_tools.sort(key=lambda t: t["relevance_score"], reverse=True)

    return scored_tools


def modulate_tool_confidence_by_chemistry(
    tools: List[Dict[str, Any]],
    chemistry: Dict[str, float]
) -> List[Dict[str, Any]]:
    """
    Modulate tool confidence based on neurochemistry levels.

    Different chemical states affect tool confidence:
    - High cortisol (COR) -> Lower confidence in risky tools
    - High acetylcholine (ACH) -> Higher confidence in focus/precision tools
    - Low dopamine (DOP) -> Lower confidence in exploratory tools
    - High dopamine -> Higher confidence in reward-seeking/exploration

    Args:
        tools: List of tool definitions
        chemistry: Neurochemistry levels with DOP, SER, NOR, ACH, OXY, COR, GABA, END

    Returns:
        Tools with confidence_modifier added (0.1 to 2.0 range)
    """
    # Extract chemistry levels with defaults
    dop = chemistry.get("DOP", 0.5)  # Dopamine
    ser = chemistry.get("SER", 0.5)  # Serotonin
    nor = chemistry.get("NOR", 0.5)  # Norepinephrine
    ach = chemistry.get("ACH", 0.5)  # Acetylcholine
    oxy = chemistry.get("OXY", 0.5)  # Oxytocin
    cor = chemistry.get("COR", 0.5)  # Cortisol
    gaba = chemistry.get("GABA", 0.5)  # GABA
    end = chemistry.get("END", 0.5)  # Endorphins

    modulated = []
    for tool in tools:
        tool_copy = dict(tool)
        modifier = 1.0  # Start neutral

        risk_level = tool.get("risk_level", "low").lower()
        category = tool.get("category", "").lower()
        is_exploratory = _is_exploratory_tool(tool)
        is_debugging = _is_debugging_tool(tool)

        # Cortisol effects (stress)
        # High cortisol reduces confidence in risky tools
        if cor > 0.6:
            if risk_level == "high":
                modifier *= 0.5  # Halve confidence for high-risk
            elif risk_level == "medium":
                modifier *= 0.7
            if is_exploratory:
                modifier *= 0.7  # Reduce exploration confidence

        # Dopamine effects (motivation/reward)
        # High dopamine boosts exploration confidence
        # Low dopamine reduces it
        if dop > 0.6:
            if is_exploratory:
                modifier *= 1.3
        elif dop < 0.3:
            if is_exploratory:
                modifier *= 0.6  # Low motivation for exploration

        # Acetylcholine effects (attention/focus)
        # High ACH boosts confidence in focus-requiring tools
        if ach > 0.6:
            if is_debugging or category in {"debugging", "monitoring", "file_ops"}:
                modifier *= 1.2  # Better at focused tasks
        elif ach < 0.3:
            if is_debugging:
                modifier *= 0.7  # Impaired attention

        # Norepinephrine effects (alertness)
        # High NOR boosts precision tools
        if nor > 0.6:
            if category in {"debugging", "monitoring"}:
                modifier *= 1.15

        # Serotonin effects (calm/patience)
        if ser > 0.6:
            # More patience for complex tasks
            modifier *= 1.05
        elif ser < 0.3:
            # Less patience - reduce confidence in slow tasks
            modifier *= 0.9

        # GABA effects (inhibition/calm)
        if gaba < 0.3:
            # Less inhibition - might be impulsive with risky tools
            if risk_level == "high":
                modifier *= 0.8

        # Oxytocin effects (social/collaboration)
        if oxy > 0.6 and category in {"social", "collaboration"}:
            modifier *= 1.2

        # Clamp to reasonable bounds
        modifier = max(0.1, min(2.0, modifier))

        tool_copy["confidence_modifier"] = round(modifier, 3)
        modulated.append(tool_copy)

    return modulated


def suggest_tools_for_affect(
    tools: List[Dict[str, Any]],
    affect_state: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Suggest appropriate tools based on emotional state.

    Different emotional states suggest different tool categories:
    - Anxious/stressed -> Suggest calming, safe tools
    - Curious -> Suggest exploratory tools
    - Frustrated -> Suggest debugging/clarity tools
    - Focused -> Suggest precision, task-completion tools
    - Calm/peaceful -> Suggest thoughtful, creative tools
    - Excited -> Suggest active, exploratory tools

    Args:
        tools: List of tool definitions
        affect_state: Current affect state with mood, dominant_emotion, stress, valence, arousal

    Returns:
        Suggested tools with suggestion_reason added (max 5 tools)
    """
    stress = affect_state.get("stress", 0.0)
    valence = affect_state.get("valence", 0.0)
    arousal = affect_state.get("arousal", 0.5)
    mood = affect_state.get("mood", "").lower()
    emotion = affect_state.get("dominant_emotion", "").lower()
    intensity = affect_state.get("dominant_intensity", 0.5)

    suggestions = []

    # Determine what categories to suggest based on emotional state
    target_categories = set()
    target_traits = set()  # calming, exploratory, debugging, etc.
    reason_prefix = ""

    # High stress / Anxious state -> calming tools
    if stress > 0.7 or mood in {"anxious", "stressed"} or emotion in {"anxiety", "fear", "stress"}:
        target_traits.add("calming")
        reason_prefix = "Suggested for stress relief: "

    # Curious state -> exploratory tools
    elif emotion in {"curiosity", "interest", "wonder"} or mood in {"curious", "interested"}:
        target_traits.add("exploratory")
        target_categories.add("exploration")
        reason_prefix = "Suggested for curiosity: "

    # Frustrated state -> debugging/clarity tools
    elif emotion in {"frustration", "annoyance", "confusion"} or mood in {"frustrated", "stuck"}:
        target_traits.add("debugging")
        target_categories.add("debugging")
        target_categories.add("monitoring")
        reason_prefix = "Suggested for clarity: "

    # Focused state -> precision/task tools
    elif mood in {"focused", "concentrated"} or emotion in {"focus", "concentration"}:
        target_categories.add("file_ops")
        target_categories.add("debugging")
        reason_prefix = "Suggested for focused work: "

    # Calm/peaceful state -> thoughtful tools
    elif mood in {"peaceful", "calm", "relaxed"} or emotion in {"calm", "peace", "serenity"}:
        target_categories.add("memory")
        target_categories.add("monitoring")
        reason_prefix = "Suggested for calm reflection: "

    # Excited state -> active/exploratory tools
    elif mood in {"excited", "energized"} or emotion in {"excitement", "enthusiasm"}:
        target_traits.add("exploratory")
        target_categories.add("exploration")
        reason_prefix = "Suggested for exploration: "

    # Default: balanced suggestion
    else:
        target_categories.add("monitoring")
        target_categories.add("file_ops")
        reason_prefix = "Suggested for current state: "

    # Score tools based on matching criteria
    for tool in tools:
        tool_copy = dict(tool)
        score = 0.0
        reasons = []

        category = tool.get("category", "").lower()

        # Check category matches
        if category in target_categories:
            score += 0.5
            reasons.append(f"matches {category} category")

        # Check trait matches
        if "calming" in target_traits and _is_calming_tool(tool):
            score += 0.6
            reasons.append("calming tool")

        if "exploratory" in target_traits and _is_exploratory_tool(tool):
            score += 0.5
            reasons.append("exploratory tool")

        if "debugging" in target_traits and _is_debugging_tool(tool):
            score += 0.5
            reasons.append("debugging/clarity tool")

        # Low risk bonus when stressed
        if stress > 0.5 and tool.get("risk_level", "low").lower() == "low":
            score += 0.2
            reasons.append("low risk")

        if score > 0:
            tool_copy["_suggestion_score"] = score
            tool_copy["suggestion_reason"] = reason_prefix + ", ".join(reasons)
            suggestions.append(tool_copy)

    # Sort by suggestion score and take top 5
    suggestions.sort(key=lambda t: t.get("_suggestion_score", 0), reverse=True)
    suggestions = suggestions[:5]

    # Clean up internal score
    for s in suggestions:
        s.pop("_suggestion_score", None)

    # Ensure at least 1 suggestion if tools exist
    if not suggestions and tools:
        # Pick first safe tool
        for tool in tools:
            if tool.get("risk_level", "low").lower() == "low":
                tool_copy = dict(tool)
                tool_copy["suggestion_reason"] = "Default safe tool suggestion"
                suggestions.append(tool_copy)
                break

    return suggestions


def get_consciousness_aware_tools(
    tools: List[Dict[str, Any]],
    affect_state: Dict[str, Any],
    working_memory: Dict[str, Any],
    chemistry: Dict[str, float],
) -> Dict[str, Any]:
    """
    Full consciousness-aware tool selection pipeline.

    Pipeline: filter -> rank -> modulate confidence -> suggest

    Args:
        tools: List of available tool definitions
        affect_state: Current affect state
        working_memory: Working memory contents
        chemistry: Neurochemistry levels

    Returns:
        Dict with:
        - available_tools: Filtered, ranked, confidence-modulated tools
        - suggested_tools: Emotionally-appropriate tool suggestions
        - filtered_count: Number of tools filtered out
    """
    original_count = len(tools)

    # Step 1: Filter by affect state (stress-aware)
    filtered = filter_tools_by_affect_state(tools, affect_state)
    filtered_count = original_count - len(filtered)

    # Step 2: Rank by working memory relevance
    ranked = rank_tools_by_working_memory(filtered, working_memory)

    # Step 3: Modulate confidence by chemistry
    modulated = modulate_tool_confidence_by_chemistry(ranked, chemistry)

    # Step 4: Get emotional suggestions
    suggested = suggest_tools_for_affect(tools, affect_state)

    return {
        "available_tools": modulated,
        "suggested_tools": suggested,
        "filtered_count": filtered_count,
        "total_tools": original_count,
        "available_count": len(modulated),
    }


# =============================================================================
# CONSOLE SELECTED TOOL CLASS (for advanced usage)
# =============================================================================

class ConsciousnessAwareToolSelector:
    """
    Stateful tool selector that maintains consciousness state.

    Can be used for persistent tool selection across multiple calls,
    with optional caching and state tracking.
    """

    def __init__(self):
        self._last_affect: Optional[Dict[str, Any]] = None
        self._last_chemistry: Optional[Dict[str, float]] = None
        self._last_working_memory: Optional[Dict[str, Any]] = None
        self._selection_count: int = 0

    def select_tool(
        self,
        goal: str,
        available_tools: List[Dict[str, Any]],
        affect_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Select the best tool for a given goal based on consciousness state.

        Args:
            goal: The goal/task description
            available_tools: List of available tools
            affect_state: Optional affect state (uses last if not provided)

        Returns:
            Selected tool dict with selection metadata, or None
        """
        # Use provided or cached state
        affect = affect_state or self._last_affect or {
            "stress": 0.3, "valence": 0.0, "arousal": 0.5,
            "mood": "neutral", "dominant_emotion": "neutral", "dominant_intensity": 0.5
        }

        # Build working memory from goal
        working_memory = {
            "recent_thoughts": [{"content": goal, "tags": [], "priority": 1.0}],
            "active_goals": [goal],
            "context_keywords": goal.lower().split(),
        }

        # Use cached chemistry or defaults
        chemistry = self._last_chemistry or {
            "DOP": 0.5, "SER": 0.5, "NOR": 0.5, "ACH": 0.5,
            "OXY": 0.5, "COR": 0.5, "GABA": 0.5, "END": 0.5,
        }

        # Run full pipeline
        result = get_consciousness_aware_tools(
            tools=available_tools,
            affect_state=affect,
            working_memory=working_memory,
            chemistry=chemistry,
        )

        # Cache state
        self._last_affect = affect
        self._selection_count += 1

        # Return top available tool
        if result["available_tools"]:
            selected = result["available_tools"][0]
            selected["_selection_metadata"] = {
                "goal": goal,
                "selection_number": self._selection_count,
                "affect_stress": affect.get("stress", 0),
            }
            return selected

        return None

    def update_chemistry(self, chemistry: Dict[str, float]) -> None:
        """Update cached chemistry state."""
        self._last_chemistry = chemistry

    def update_affect(self, affect_state: Dict[str, Any]) -> None:
        """Update cached affect state."""
        self._last_affect = affect_state


# =============================================================================
# MCP TOOL REGISTRATION
# =============================================================================

def register_consciousness_aware_tools(mcp) -> None:
    """Register consciousness-aware tool selection tools with MCP server."""
    import json

    @mcp.tool()
    def consciousness_aware_tool_select(
        goal: str,
        tools_json: str,
        affect_json: Optional[str] = None,
        chemistry_json: Optional[str] = None,
    ) -> str:
        """
        Select tools based on consciousness state.

        This is the MCP-exposed version of consciousness-aware tool selection.
        Filters, ranks, and suggests tools based on affect state and chemistry.

        Args:
            goal: The goal/task to accomplish
            tools_json: JSON array of tool definitions
            affect_json: Optional JSON affect state
            chemistry_json: Optional JSON chemistry levels

        Returns:
            JSON with selected and suggested tools
        """
        try:
            tools = json.loads(tools_json)

            # Parse affect state
            if affect_json:
                affect_state = json.loads(affect_json)
            else:
                # Try to get from somatic system
                try:
                    from fairies.P20_Somatic.chemistry.chemistry_state import get_mood
                    mood = get_mood()
                    affect_state = {
                        "valence": mood.get("valence", 0.0),
                        "arousal": mood.get("arousal", 0.5),
                        "stress": mood.get("levels", {}).get("cortisol", 0.3),
                        "mood": mood.get("mood", "neutral"),
                        "dominant_emotion": "neutral",
                        "dominant_intensity": 0.5,
                    }
                except:
                    affect_state = {
                        "valence": 0.0, "arousal": 0.5, "stress": 0.3,
                        "mood": "neutral", "dominant_emotion": "neutral",
                        "dominant_intensity": 0.5
                    }

            # Parse chemistry
            if chemistry_json:
                chemistry = json.loads(chemistry_json)
            else:
                try:
                    from fairies.P20_Somatic.chemistry.chemistry_state import get_aer_chemistry
                    chemistry = get_aer_chemistry()
                except:
                    chemistry = {
                        "DOP": 0.5, "SER": 0.5, "NOR": 0.5, "ACH": 0.5,
                        "OXY": 0.5, "COR": 0.5, "GABA": 0.5, "END": 0.5
                    }

            # Build working memory from goal
            working_memory = {
                "recent_thoughts": [{"content": goal, "tags": [], "priority": 1.0}],
                "active_goals": [goal],
                "context_keywords": goal.lower().split(),
            }

            result = get_consciousness_aware_tools(
                tools=tools,
                affect_state=affect_state,
                working_memory=working_memory,
                chemistry=chemistry,
            )

            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    sys.stderr.write("[MCP] [OK] Consciousness-aware tool selection registered\n")
