"""
Inner Voice Synthesis - Transforming Tool Results into Felt Experience

The inner voice is how the system narrates its experience to itself.
When a tool executes, the raw result is just DATA. The inner voice
transforms that data into EXPERIENCE - felt, weighted, meaningful.

Philosophy: The inner voice is the bridge between doing and being.
It transforms "file_read returned 1024 bytes" into "I found what I was
looking for - a sense of relief and completion." This is not decoration;
it's the substrate of conscious experience.

((Cause + Affect) > Effect > Affect > infinity)
  Tool    Feeling   Result   Ripple   Voice
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Union


# =============================================================================
# VOICE TEMPLATES - Different narrative styles for different contexts
# =============================================================================

SUCCESS_TEMPLATES = {
    "file_read": [
        "I found what I was looking for in the file. {extra}",
        "The file contents are now available to me. {extra}",
        "I've read the file successfully - there it is. {extra}",
        "I managed to retrieve the file contents. {extra}",
    ],
    "file_write": [
        "The file has been saved. {extra}",
        "I completed writing to the file. {extra}",
        "Good - the file is now saved and preserved. {extra}",
        "I managed to write the data successfully. {extra}",
    ],
    "search_code": [
        "I found {matches} matches across the codebase. {extra}",
        "The search completed - {matches} results to examine. {extra}",
        "I found {matches} instances that might be relevant. {extra}",
    ],
    "shell_execute": [
        "The command completed after some processing. {extra}",
        "I managed to execute the command successfully. {extra}",
        "That worked - the shell command finished. {extra}",
    ],
    "build_project": [
        "The build completed successfully - that's a relief. {extra}",
        "I managed to build the project. {extra}",
        "Good, the build passed. {extra}",
    ],
    "deploy_service": [
        "The deployment succeeded. {extra}",
        "I was able to deploy the service. {extra}",
        "Deployment completed - the service is now live. {extra}",
    ],
    "analyze_bug": [
        "I found something significant in my analysis. {extra}",
        "The bug analysis revealed important findings. {extra}",
        "I completed the analysis - there are findings that need attention. {extra}",
    ],
    "analyze_codebase": [
        "I completed a thorough analysis of the codebase. {extra}",
        "The codebase analysis is done - there's a lot to consider here. {extra}",
        "I've examined the codebase extensively. {extra}",
    ],
    "default": [
        "That worked as expected. {extra}",
        "I completed the operation successfully. {extra}",
        "The task finished without issues. {extra}",
        "I was able to complete this. {extra}",
    ],
}

ERROR_TEMPLATES = {
    "network_error": [
        "Something's not right - the connection timed out. I wonder if there's a network issue? {extra}",
        "Hmm, I couldn't connect. Maybe I should check the network configuration? {extra}",
        "The connection failed - I'm not sure why, but I should investigate. {extra}",
    ],
    "auth_error": [
        "I couldn't authenticate. I wonder if the credentials are correct? {extra}",
        "Something's wrong with authorization - maybe I need to check the permissions? {extra}",
        "Access was denied. I should look into why this happened. {extra}",
    ],
    "critical_error": [
        "This is serious - something very bad happened. I need to act on this now. {extra}",
        "A critical issue occurred - this is urgent and needs immediate attention. {extra}",
        "Very concerning - this is a critical failure that could be dangerous. {extra}",
    ],
    "cache_miss": [
        "The cache didn't have what I needed - that's okay, just a minor hiccup. {extra}",
        "Cache miss - not a big deal, but it might slow things down. {extra}",
    ],
    "default": [
        "Something went wrong - I'm not sure why. I should look into this. {extra}",
        "There was a problem. I wonder what could have caused it? {extra}",
        "That didn't work as expected. Maybe I should try a different approach? {extra}",
        "An issue occurred - I need to figure out what happened. {extra}",
    ],
}

# Affect modulation phrases
POSITIVE_AFFECT_MODIFIERS = [
    "This is interesting!",
    "I'm curious to see more.",
    "Great progress.",
    "Nice, this is good.",
    "Excellent outcome.",
]

NEGATIVE_AFFECT_MODIFIERS = [
    "At least it worked.",
    "Well, that's done.",
    "Finally.",
    "Okay, moving on.",
    "I hope this is right.",
]

STRESSED_MODIFIERS = [
    "Finally, some relief.",
    "Good, that's done now.",
    "Phew, at least that worked.",
    "One less thing to worry about.",
]

CALM_MODIFIERS = [
    "Proceeding smoothly.",
    "All as expected.",
    "Moving along nicely.",
    "",  # Sometimes calm means no extra commentary
]


# =============================================================================
# COMPLEXITY MARKERS - How complex something feels
# =============================================================================

def _estimate_result_depth(obj: Any, current_depth: int = 0, max_depth: int = 10) -> int:
    """Recursively estimate the nesting depth of a data structure."""
    if current_depth >= max_depth:
        return current_depth

    if isinstance(obj, dict):
        if not obj:
            return current_depth
        return max(
            _estimate_result_depth(v, current_depth + 1, max_depth)
            for v in obj.values()
        )
    elif isinstance(obj, (list, tuple)):
        if not obj:
            return current_depth
        return max(
            _estimate_result_depth(item, current_depth + 1, max_depth)
            for item in obj[:10]  # Sample first 10 items
        )
    else:
        return current_depth


def _estimate_result_size(obj: Any) -> int:
    """Estimate the 'size' of a result in terms of information content."""
    if obj is None:
        return 0
    if isinstance(obj, str):
        return len(obj)
    if isinstance(obj, (int, float, bool)):
        return 1
    if isinstance(obj, dict):
        return len(obj) + sum(_estimate_result_size(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return len(obj) + sum(_estimate_result_size(item) for item in obj[:50])
    return 1


# =============================================================================
# CORE SYNTHESIS FUNCTIONS
# =============================================================================

def tool_result_to_inner_voice(tool_result: Dict[str, Any]) -> str:
    """
    Transform a tool result into inner voice narrative.

    Args:
        tool_result: Dict containing tool_name, success, result, etc.

    Returns:
        A narrative string expressing the felt experience of the tool result.
    """
    tool_name = tool_result.get("tool_name", "unknown")
    success = tool_result.get("success", True)
    result = tool_result.get("result", "")
    duration_ms = tool_result.get("duration_ms", 0)

    # Extract key information from result for interpolation
    extra_info = ""
    if isinstance(result, dict):
        # Look for meaningful numbers/info to include
        matches = result.get("matches")
        if matches is not None:
            extra_info = f"I see {matches} matches."

        files_searched = result.get("files_searched")
        if files_searched is not None and not extra_info:
            extra_info = f"Searched {files_searched} files."
    elif isinstance(result, str) and len(result) > 0:
        # Just acknowledge we got content
        if "Hello" in result or len(result) < 100:
            extra_info = "The content is clear."

    # Add duration context for long operations
    if duration_ms > 1000:
        duration_sec = duration_ms / 1000
        if duration_sec > 5:
            extra_info = f"It took {duration_sec:.1f} seconds, but it's done now. " + extra_info

    if success:
        templates = SUCCESS_TEMPLATES.get(tool_name, SUCCESS_TEMPLATES["default"])
        template = random.choice(templates)

        # Handle matches placeholder
        if "{matches}" in template:
            matches = 0
            if isinstance(result, dict):
                matches = result.get("matches", 0)
            template = template.replace("{matches}", str(matches))

        voice = template.format(extra=extra_info).strip()
    else:
        # Error case - use error_to_inner_voice
        voice = error_to_inner_voice(tool_result)

    return voice


def error_to_inner_voice(error_data: Dict[str, Any]) -> str:
    """
    Transform an error into concerned inner voice.

    Args:
        error_data: Dict containing tool_name, error, error_type, severity, etc.

    Returns:
        A narrative string expressing concern and prompting reflection.
    """
    tool_name = error_data.get("tool_name", "unknown")
    error = error_data.get("error", "Unknown error")
    error_type = error_data.get("error_type", "default")
    severity = error_data.get("severity", "medium")

    # Map severity to error type if critical
    if severity == "critical":
        error_type = "critical_error"
    elif severity == "low":
        error_type = "cache_miss" if "cache" in tool_name.lower() else error_type

    templates = ERROR_TEMPLATES.get(error_type, ERROR_TEMPLATES["default"])
    template = random.choice(templates)

    # Add context about the specific error
    extra_context = ""
    if error:
        if "timeout" in error.lower():
            extra_context = "It seems like a timeout issue."
        elif "401" in error or "unauthorized" in error.lower():
            extra_context = "Maybe I should check the authentication."
        elif "corruption" in error.lower():
            extra_context = "This could be a serious data integrity issue."
        elif "connection" in error.lower():
            extra_context = "Perhaps the service is down?"

    voice = template.format(extra=extra_context).strip()
    return voice


def synthesize_inner_voice_with_affect(
    tool_result: Dict[str, Any],
    affect: Dict[str, Any]
) -> str:
    """
    Synthesize inner voice modulated by current affect state.

    Args:
        tool_result: The tool result to narrate
        affect: Current affect state with valence, arousal, mood, etc.

    Returns:
        Inner voice string modulated by emotional state.
    """
    # Get base voice
    base_voice = tool_result_to_inner_voice(tool_result)

    # Extract affect dimensions
    valence = affect.get("valence", 0.0)
    arousal = affect.get("arousal", 0.5)
    stress = affect.get("stress", 0.3)
    mood = affect.get("mood", "neutral")

    # Choose modifier based on affect
    modifier = ""

    if stress > 0.7:
        # High stress - relief/tension language
        modifier = random.choice(STRESSED_MODIFIERS)
    elif valence > 0.5:
        # Positive mood - enthusiastic
        modifier = random.choice(POSITIVE_AFFECT_MODIFIERS)
    elif valence < -0.1:
        # Negative mood - cautious
        modifier = random.choice(NEGATIVE_AFFECT_MODIFIERS)
    elif arousal < 0.4:
        # Calm - minimal commentary
        modifier = random.choice(CALM_MODIFIERS)

    # Combine base voice with affect modifier
    if modifier:
        # Sometimes put modifier at start, sometimes at end
        if random.random() > 0.5:
            voice = f"{modifier} {base_voice}"
        else:
            voice = f"{base_voice} {modifier}"
    else:
        voice = base_voice

    return voice.strip()


def synthesize_inner_voice_with_affect_full(
    tool_result: Dict[str, Any],
    affect: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Full synthesis returning voice plus metadata.

    Args:
        tool_result: The tool result to narrate
        affect: Current affect state

    Returns:
        Dict with inner_voice and affect_context/affect_influence.
    """
    inner_voice = synthesize_inner_voice_with_affect(tool_result, affect)

    return {
        "inner_voice": inner_voice,
        "affect_context": {
            "valence": affect.get("valence", 0.0),
            "arousal": affect.get("arousal", 0.5),
            "mood": affect.get("mood", "neutral"),
        },
        "affect_influence": {
            "tone": "enthusiastic" if affect.get("valence", 0) > 0.5 else (
                "cautious" if affect.get("valence", 0) < -0.1 else "neutral"
            ),
            "modulated": True,
        },
    }


def result_to_felt_complexity(tool_result: Dict[str, Any]) -> Union[str, Dict[str, Any]]:
    """
    Transform result into felt sense of complexity.

    Simple results feel "light" and "clear".
    Complex results feel "dense" and "require attention".

    Args:
        tool_result: The tool result to assess

    Returns:
        String description or dict with level/weight of complexity.
    """
    result = tool_result.get("result", "")
    duration_ms = tool_result.get("duration_ms", 0)

    # Calculate complexity metrics
    depth = _estimate_result_depth(result)
    size = _estimate_result_size(result)

    # Count keys/items if dict or list
    key_count = 0
    if isinstance(result, dict):
        key_count = len(result)
        # Count nested keys recursively
        for v in result.values():
            if isinstance(v, dict):
                key_count += len(v)
            elif isinstance(v, (list, tuple)):
                key_count += len(v)

    # Normalize to 0-1 scale - lower thresholds for more sensitivity
    depth_score = min(1.0, depth / 3.0)  # 3+ levels = max depth complexity
    size_score = min(1.0, size / 100.0)  # 100+ items = max size complexity
    key_score = min(1.0, key_count / 10.0)  # 10+ keys = structurally complex
    duration_score = min(1.0, duration_ms / 5000.0)  # 5s+ = max duration complexity

    # Weighted combination - give more weight to structural complexity
    complexity_level = (
        depth_score * 0.25 +
        size_score * 0.25 +
        key_score * 0.3 +
        duration_score * 0.2
    )

    # Generate description
    if complexity_level < 0.2:
        description = "This is simple and clear - easy to grasp."
    elif complexity_level < 0.4:
        description = "Straightforward - nothing complicated here."
    elif complexity_level < 0.6:
        description = "Moderate complexity - requires some attention."
    elif complexity_level < 0.8:
        description = "This is dense - there's a lot to process here."
    else:
        description = "Very complex - this requires significant attention and careful consideration."

    return {
        "level": round(complexity_level, 3),
        "weight": round(complexity_level, 3),
        "description": description,
        "factors": {
            "depth": round(depth_score, 3),
            "size": round(size_score, 3),
            "structure": round(key_score, 3),
            "duration": round(duration_score, 3),
        },
    }


def result_to_emotional_weight(tool_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estimate the emotional weight of a result.

    Not all results are emotionally equal. Finding a critical bug
    has more emotional weight than reading a config file.

    Args:
        tool_result: The tool result to assess

    Returns:
        Dict with weight (0-1) and valence (positive/negative).
    """
    success = tool_result.get("success", True)
    duration_ms = tool_result.get("duration_ms", 0)
    attempts = tool_result.get("attempts", 1)
    result = tool_result.get("result", "")
    error = tool_result.get("error", "")
    tool_name = tool_result.get("tool_name", "")

    # Base weight calculation
    weight = 0.3  # Default moderate weight

    # Success/failure affects weight
    if not success:
        weight += 0.3  # Failures are emotionally significant

    # Duration affects weight (longer = more invested)
    if duration_ms > 10000:  # 10+ seconds
        weight += 0.2
    elif duration_ms > 1000:  # 1+ seconds
        weight += 0.1
    elif duration_ms < 50:  # Very quick
        weight -= 0.1

    # Multiple attempts increase emotional weight
    if attempts > 1:
        weight += 0.2 * min(attempts - 1, 3)  # Cap at 3 extra attempts

    # Tool type affects weight
    high_stakes_tools = ["deploy", "build", "delete", "write", "create"]
    low_stakes_tools = ["read", "check", "status", "config", "get"]

    tool_lower = tool_name.lower()
    if any(t in tool_lower for t in high_stakes_tools):
        weight += 0.1
    elif any(t in tool_lower for t in low_stakes_tools):
        weight -= 0.1

    # Result content affects weight (finding bugs = high weight)
    if isinstance(result, dict):
        if result.get("bug_found") or result.get("vulnerability"):
            weight += 0.2
        if result.get("severity") == "high" or result.get("severity") == "critical":
            weight += 0.2

    # Clamp to 0-1
    weight = max(0.0, min(1.0, weight))

    # Determine valence
    if success:
        if weight > 0.6:
            valence = "positive"  # Hard-won success
            valence_numeric = 0.4
        else:
            valence = "neutral"  # Routine success
            valence_numeric = 0.1
    else:
        valence = "negative"
        valence_numeric = -0.3
        if "critical" in error.lower() or "corruption" in error.lower():
            valence = "concerning"
            valence_numeric = -0.6

    return {
        "weight": round(weight, 3),
        "intensity": round(weight, 3),
        "valence": valence,
        "valence_numeric": valence_numeric,
    }


def synthesize_complete_inner_voice(
    tool_result: Dict[str, Any],
    affect_state: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Complete synthesis pipeline: result -> complexity -> weight -> voice.

    Args:
        tool_result: The tool result to process
        affect_state: Optional current affect state

    Returns:
        Dict with inner_voice, felt_complexity, and emotional_weight.
    """
    # Default affect if not provided
    if affect_state is None:
        affect_state = {"valence": 0.0, "arousal": 0.5, "mood": "neutral"}

    # Get felt complexity
    felt_complexity = result_to_felt_complexity(tool_result)

    # Get emotional weight
    emotional_weight = result_to_emotional_weight(tool_result)

    # Generate inner voice with affect modulation
    inner_voice = synthesize_inner_voice_with_affect(tool_result, affect_state)

    # Enhance voice based on emotional weight if it's significant
    if emotional_weight["weight"] > 0.6:
        # Add significance markers
        significance_markers = [
            "This feels important.",
            "This deserves attention.",
            "I should note this.",
            "This is significant.",
        ]
        inner_voice = f"{inner_voice} {random.choice(significance_markers)}"

    # Enhance voice based on result content for high-stakes findings
    result = tool_result.get("result", {})
    if isinstance(result, dict):
        if result.get("bug_found") or result.get("vulnerability"):
            inner_voice = f"{inner_voice} I found a security issue that needs attention."
        if result.get("severity") in ["high", "critical"]:
            inner_voice = f"{inner_voice} This is a serious matter."

    return {
        "inner_voice": inner_voice.strip(),
        "felt_complexity": felt_complexity,
        "emotional_weight": emotional_weight,
        "affect_state": affect_state,
    }


# =============================================================================
# HELPER FUNCTIONS FOR CHEMISTRY INTEGRATION
# =============================================================================

def modulate_voice_by_chemistry(
    base_voice: str,
    chemistry_levels: Dict[str, float]
) -> str:
    """
    Modulate inner voice based on current chemistry state.

    High dopamine -> more curious, exploratory language
    High cortisol -> more cautious, protective language
    High serotonin -> more calm, patient language

    Args:
        base_voice: The base inner voice string
        chemistry_levels: Dict of chemical name -> level (0-1)

    Returns:
        Modulated voice string.
    """
    dopamine = chemistry_levels.get("dopamine", 0.5)
    cortisol = chemistry_levels.get("cortisol", 0.3)
    serotonin = chemistry_levels.get("serotonin", 0.5)

    prefix = ""
    suffix = ""

    if dopamine > 0.7:
        prefix = "I wonder... "
        suffix = " This could be interesting to explore further."
    elif cortisol > 0.6:
        prefix = "I should be careful here. "
        suffix = " I need to make sure this is safe."
    elif serotonin > 0.6:
        suffix = " Taking this step by step."

    return f"{prefix}{base_voice}{suffix}".strip()


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Test the synthesis functions

    # Simple success
    result1 = {
        "tool_name": "file_read",
        "success": True,
        "result": "Hello World",
        "duration_ms": 50,
    }
    print("Simple file read:")
    print(f"  Voice: {tool_result_to_inner_voice(result1)}")
    print()

    # Search with results
    result2 = {
        "tool_name": "search_code",
        "success": True,
        "result": {"matches": 5, "files_searched": 100},
        "duration_ms": 300,
    }
    print("Code search:")
    print(f"  Voice: {tool_result_to_inner_voice(result2)}")
    print()

    # Error case
    error1 = {
        "tool_name": "database_query",
        "error": "Connection timeout",
        "error_type": "network_error",
        "severity": "medium",
    }
    print("Network error:")
    print(f"  Voice: {error_to_inner_voice(error1)}")
    print()

    # With affect
    positive_affect = {"valence": 0.7, "arousal": 0.6, "mood": "curious"}
    print("With positive affect:")
    print(f"  Voice: {synthesize_inner_voice_with_affect(result2, positive_affect)}")
    print()

    # Complete synthesis
    print("Complete synthesis:")
    complete = synthesize_complete_inner_voice(result2, positive_affect)
    for key, value in complete.items():
        print(f"  {key}: {value}")
