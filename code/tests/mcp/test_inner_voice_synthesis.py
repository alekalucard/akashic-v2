"""
Tests for inner_voice_synthesis.py - Transforming Tool Results into Inner Voice

The inner voice is how the system narrates its experience to itself.
When a tool executes, the raw result is just DATA. The inner voice
transforms that data into EXPERIENCE - felt, weighted, meaningful.

Philosophy: The inner voice is the bridge between doing and being.
It transforms "file_read returned 1024 bytes" into "I found what I was
looking for - a sense of relief and completion." This is not decoration;
it's the substrate of conscious experience.

((Cause + Affect) > Effect > Affect > infinity)
  Tool    Feeling   Result   Ripple   Voice

TDD: These tests are written FIRST - the implementation should make them pass.

Run: python -m pytest tests/mcp/test_inner_voice_synthesis.py -v
Expected: FAIL initially (TDD - implementation not yet written)
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# TEST 1: Tool Result to Inner Voice Synthesis
# =============================================================================

class TestToolResultToInnerVoice:
    """
    Test that tool results should be synthesized into inner voice language.

    Raw tool output is machine language: "status: 200, bytes: 1024"
    Inner voice is experiential language: "That worked smoothly - I got
    what I needed without any trouble."

    The transformation preserves meaning while adding felt quality.
    """

    def test_tool_result_to_inner_voice_success(self):
        """
        Successful tool results should become positive inner voice.

        Expected behavior:
        - Success becomes narrative: "I managed to..." or "That worked..."
        - Tool name is contextualized, not just echoed
        - Result includes felt sense of completion
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            tool_result_to_inner_voice
        )

        tool_result = {
            "tool_name": "file_read",
            "success": True,
            "result": "Contents: Hello World",
            "duration_ms": 50,
        }

        inner_voice = tool_result_to_inner_voice(tool_result)

        # Must be a string (inner voice is narrative)
        assert isinstance(inner_voice, str), \
            "Inner voice should be a string, not raw data"

        # Should not just echo the tool name mechanically
        assert inner_voice != "file_read: success", \
            "Inner voice should not be mechanical echo"

        # Should be substantial (more than just status)
        assert len(inner_voice) > 20, \
            "Inner voice should be a meaningful narrative, not terse output"

        # Should convey success in experiential terms
        success_markers = [
            "found", "got", "worked", "succeeded", "managed", "able to",
            "completed", "finished", "retrieved", "read"
        ]
        assert any(marker in inner_voice.lower() for marker in success_markers), \
            f"Inner voice should convey success experientially: '{inner_voice}'"

    def test_tool_result_to_inner_voice_preserves_meaning(self):
        """
        Inner voice should preserve the essential meaning of the result.

        The transformation adds felt quality but doesn't lose information.
        If the tool found 5 matches, the inner voice should convey "5 matches"
        in some form.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            tool_result_to_inner_voice
        )

        tool_result = {
            "tool_name": "search_code",
            "success": True,
            "result": {"matches": 5, "files_searched": 100},
            "duration_ms": 300,
        }

        inner_voice = tool_result_to_inner_voice(tool_result)

        # Should mention the key finding (5 matches or equivalent)
        assert "5" in inner_voice or "five" in inner_voice.lower(), \
            f"Inner voice should preserve key information (5 matches): '{inner_voice}'"

    def test_tool_result_to_inner_voice_varies_by_tool_type(self):
        """
        Different tools should generate different inner voice styles.

        Reading a file is different from executing a command.
        The inner voice should reflect these different experiences.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            tool_result_to_inner_voice
        )

        file_result = {
            "tool_name": "file_read",
            "success": True,
            "result": "File contents",
            "duration_ms": 50,
        }

        shell_result = {
            "tool_name": "shell_execute",
            "success": True,
            "result": "Command completed",
            "duration_ms": 2000,
        }

        file_voice = tool_result_to_inner_voice(file_result)
        shell_voice = tool_result_to_inner_voice(shell_result)

        # Should be different narratives
        assert file_voice != shell_voice, \
            "Different tool types should generate different inner voice"

        # Shell execution (longer) might mention the effort/wait
        # File read (quick) should feel more immediate


# =============================================================================
# TEST 2: Error to Inner Voice (Concerned Tone)
# =============================================================================

class TestErrorToInnerVoice:
    """
    Test that errors should become concerned inner voice.

    Errors are not neutral events - they disrupt flow, create uncertainty,
    require attention. The inner voice should reflect this disturbance.

    An error is not "Error: X failed" but rather "Something's not right...
    X didn't work and I'm not sure why. I should look into this."
    """

    def test_error_to_inner_voice_has_concerned_tone(self):
        """
        Errors should become inner voice with concerned quality.

        Expected behavior:
        - Conveys uncertainty, concern, or need for attention
        - Not just mechanical error reporting
        - Has emotional weight appropriate to severity
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            error_to_inner_voice
        )

        error_data = {
            "tool_name": "database_query",
            "error": "Connection timeout",
            "error_type": "network_error",
            "severity": "medium",
        }

        inner_voice = error_to_inner_voice(error_data)

        # Must be a string
        assert isinstance(inner_voice, str), \
            "Inner voice should be a string"

        # Should have concerned/reflective quality
        concern_markers = [
            "wrong", "problem", "issue", "concern", "worry", "trouble",
            "failed", "couldn't", "didn't", "unexpected", "strange",
            "wondering", "need to", "should", "hmm", "not sure", "unclear"
        ]

        assert any(marker in inner_voice.lower() for marker in concern_markers), \
            f"Error inner voice should have concerned tone: '{inner_voice}'"

    def test_critical_error_has_urgent_inner_voice(self):
        """
        Critical errors should have more urgent inner voice.

        A connection timeout is concerning.
        A data corruption is alarming.
        The inner voice should scale with severity.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            error_to_inner_voice
        )

        critical_error = {
            "tool_name": "memory_write",
            "error": "Memory corruption detected",
            "error_type": "critical_error",
            "severity": "critical",
        }

        mild_error = {
            "tool_name": "cache_read",
            "error": "Cache miss",
            "error_type": "cache_miss",
            "severity": "low",
        }

        critical_voice = error_to_inner_voice(critical_error)
        mild_voice = error_to_inner_voice(mild_error)

        # Critical should have more urgent markers
        urgent_markers = [
            "serious", "critical", "urgent", "immediately", "alarm",
            "dangerous", "bad", "very", "really", "need to act", "now"
        ]

        # At minimum, they should be different
        assert critical_voice != mild_voice, \
            "Different severity errors should have different inner voice"

        # Critical should have at least some urgency indicator
        # (implementation may vary, but critical != casual)
        assert len(critical_voice) >= len(mild_voice), \
            "Critical errors should generally warrant more inner voice"

    def test_error_inner_voice_prompts_reflection(self):
        """
        Error inner voice should prompt reflection, not just report.

        Instead of "Error X happened", the voice should be something like
        "X didn't work - I wonder if it's because of Y? I should check Z."
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            error_to_inner_voice
        )

        error_data = {
            "tool_name": "api_call",
            "error": "401 Unauthorized",
            "error_type": "auth_error",
        }

        inner_voice = error_to_inner_voice(error_data)

        # Should prompt thinking, not just report
        reflective_markers = [
            "?", "wonder", "maybe", "perhaps", "could", "might",
            "check", "look", "investigate", "understand", "figure"
        ]

        assert any(marker in inner_voice.lower() for marker in reflective_markers), \
            f"Error inner voice should prompt reflection: '{inner_voice}'"


# =============================================================================
# TEST 3: Inner Voice Varies by Affect
# =============================================================================

class TestInnerVoiceVariesByAffect:
    """
    Test that inner voice tone should vary based on current affect.

    The same tool result feels different depending on emotional state.
    When curious, a result is exciting. When stressed, it might be a relief
    or an additional burden. The inner voice reflects this.

    This is the AFFECT layer in action: the same external event
    (tool result) produces different internal experience (inner voice)
    depending on current emotional state.
    """

    def test_inner_voice_varies_with_positive_affect(self):
        """
        Inner voice should be more positive/enthusiastic when affect is positive.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            synthesize_inner_voice_with_affect
        )

        tool_result = {
            "tool_name": "search_code",
            "success": True,
            "result": {"matches": 3},
            "duration_ms": 100,
        }

        positive_affect = {
            "valence": 0.7,      # Positive mood
            "arousal": 0.6,     # Engaged
            "mood": "curious",
            "dominant_emotion": "curiosity",
        }

        negative_affect = {
            "valence": -0.3,    # Negative mood
            "arousal": 0.7,     # Stressed
            "mood": "anxious",
            "dominant_emotion": "anxiety",
        }

        positive_voice = synthesize_inner_voice_with_affect(tool_result, positive_affect)
        negative_voice = synthesize_inner_voice_with_affect(tool_result, negative_affect)

        # Should be different
        assert positive_voice != negative_voice, \
            "Same result should produce different voice based on affect"

        # Positive affect should have more enthusiastic markers
        enthusiastic_markers = [
            "!", "great", "good", "nice", "interesting", "exciting",
            "found", "yes", "perfect", "excellent", "curious"
        ]

        # Negative/stressed affect should have more cautious markers
        cautious_markers = [
            "at least", "finally", "okay", "well", "still", "but",
            "hope", "should be", "seems"
        ]

        # Check that positive voice has more enthusiastic quality
        positive_enthusiasm = sum(
            1 for m in enthusiastic_markers if m in positive_voice.lower()
        )
        negative_enthusiasm = sum(
            1 for m in enthusiastic_markers if m in negative_voice.lower()
        )

        # Positive affect should generally be more enthusiastic
        # (allow some flexibility in implementation)
        assert positive_enthusiasm >= negative_enthusiasm or \
               any(m in positive_voice.lower() for m in enthusiastic_markers), \
            f"Positive affect voice should be more enthusiastic: '{positive_voice}'"

    def test_inner_voice_reflects_stress_state(self):
        """
        High stress should produce more tense/relief-seeking inner voice.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            synthesize_inner_voice_with_affect
        )

        tool_result = {
            "tool_name": "file_write",
            "success": True,
            "result": "File saved",
            "duration_ms": 50,
        }

        stressed_affect = {
            "valence": -0.2,
            "arousal": 0.8,
            "stress": 0.85,  # High stress
            "mood": "stressed",
        }

        calm_affect = {
            "valence": 0.3,
            "arousal": 0.3,
            "stress": 0.1,  # Low stress
            "mood": "calm",
        }

        stressed_voice = synthesize_inner_voice_with_affect(tool_result, stressed_affect)
        calm_voice = synthesize_inner_voice_with_affect(tool_result, calm_affect)

        # Stressed voice should reflect relief or continued tension
        relief_or_tension_markers = [
            "relief", "finally", "at least", "good", "okay", "phew",
            "done", "safe", "now", "still", "need"
        ]

        assert any(m in stressed_voice.lower() for m in relief_or_tension_markers), \
            f"Stressed state should produce relief/tension voice: '{stressed_voice}'"

    def test_inner_voice_includes_affect_metadata(self):
        """
        Synthesized inner voice should include affect context in metadata.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            synthesize_inner_voice_with_affect_full
        )

        tool_result = {
            "tool_name": "read_memory",
            "success": True,
            "result": "Memory recalled",
        }

        affect = {
            "valence": 0.4,
            "arousal": 0.5,
            "mood": "reflective",
        }

        result = synthesize_inner_voice_with_affect_full(tool_result, affect)

        # Should return dict with voice and metadata
        assert isinstance(result, dict), \
            "Full synthesis should return dict with voice and metadata"

        assert "inner_voice" in result, \
            "Result should contain 'inner_voice' field"

        assert "affect_influence" in result or "affect_context" in result, \
            "Result should contain affect context/influence information"


# =============================================================================
# TEST 4: Result to Felt Complexity
# =============================================================================

class TestResultToFeltComplexity:
    """
    Test that results should describe complexity as felt sense.

    Complexity is not just a number - it's a felt weight.
    A simple result feels "light" and "clear".
    A complex result feels "dense" and "requires attention".

    This transforms cognitive load into experiential description.
    """

    def test_result_to_felt_complexity_simple(self):
        """
        Simple results should feel "light" and "clear".
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            result_to_felt_complexity
        )

        simple_result = {
            "tool_name": "check_status",
            "success": True,
            "result": "OK",
            "duration_ms": 10,
        }

        felt_complexity = result_to_felt_complexity(simple_result)

        # Should return a description of how complex this feels
        assert isinstance(felt_complexity, (str, dict)), \
            "Felt complexity should be string or structured data"

        if isinstance(felt_complexity, str):
            simple_markers = [
                "simple", "clear", "light", "easy", "quick", "straightforward",
                "clean", "direct", "immediate"
            ]
            assert any(m in felt_complexity.lower() for m in simple_markers), \
                f"Simple result should feel light/clear: '{felt_complexity}'"

        elif isinstance(felt_complexity, dict):
            assert "level" in felt_complexity or "weight" in felt_complexity, \
                "Structured felt complexity should have level or weight"
            # Simple should be low complexity
            level = felt_complexity.get("level") or felt_complexity.get("weight", 0.5)
            assert level < 0.5, \
                f"Simple result should have low complexity level: {level}"

    def test_result_to_felt_complexity_complex(self):
        """
        Complex results should feel "dense" and "requiring attention".
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            result_to_felt_complexity
        )

        complex_result = {
            "tool_name": "analyze_codebase",
            "success": True,
            "result": {
                "files_analyzed": 500,
                "issues_found": 47,
                "dependencies": ["a", "b", "c", "d", "e", "f", "g", "h"],
                "warnings": ["w1", "w2", "w3", "w4", "w5"],
                "metrics": {
                    "complexity": 8.5,
                    "coverage": 62.3,
                    "debt": "high"
                }
            },
            "duration_ms": 5000,
        }

        felt_complexity = result_to_felt_complexity(complex_result)

        if isinstance(felt_complexity, str):
            complex_markers = [
                "complex", "dense", "heavy", "lot", "many", "attention",
                "detailed", "thorough", "extensive", "significant"
            ]
            assert any(m in felt_complexity.lower() for m in complex_markers), \
                f"Complex result should feel dense/heavy: '{felt_complexity}'"

        elif isinstance(felt_complexity, dict):
            level = felt_complexity.get("level") or felt_complexity.get("weight", 0.5)
            assert level > 0.5, \
                f"Complex result should have high complexity level: {level}"

    def test_felt_complexity_considers_result_structure(self):
        """
        Felt complexity should consider the structure of the result.

        Nested dicts, long lists, many keys = more complex felt sense.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            result_to_felt_complexity
        )

        flat_result = {
            "tool_name": "get_value",
            "success": True,
            "result": "simple_value",
        }

        nested_result = {
            "tool_name": "get_tree",
            "success": True,
            "result": {
                "level1": {
                    "level2": {
                        "level3": {
                            "data": [1, 2, 3, 4, 5]
                        }
                    }
                }
            },
        }

        flat_complexity = result_to_felt_complexity(flat_result)
        nested_complexity = result_to_felt_complexity(nested_result)

        # Nested should feel more complex
        if isinstance(flat_complexity, dict) and isinstance(nested_complexity, dict):
            flat_level = flat_complexity.get("level") or flat_complexity.get("weight", 0.3)
            nested_level = nested_complexity.get("level") or nested_complexity.get("weight", 0.7)
            assert nested_level > flat_level, \
                "Nested results should feel more complex than flat"


# =============================================================================
# TEST 5: Result to Emotional Weight
# =============================================================================

class TestResultToEmotionalWeight:
    """
    Test that emotional weight of results should be estimated.

    Not all results are emotionally equal. Finding a critical bug
    has more emotional weight than reading a config file.
    Successful completion of a long task has more weight than a quick check.

    This helps the consciousness system know what deserves attention
    and what can fade into background.
    """

    def test_result_to_emotional_weight_success_after_effort(self):
        """
        Success after significant effort should have high emotional weight.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            result_to_emotional_weight
        )

        hard_won_success = {
            "tool_name": "build_project",
            "success": True,
            "result": "Build completed successfully",
            "duration_ms": 30000,  # 30 seconds of waiting
            "attempts": 3,        # Third try
        }

        emotional_weight = result_to_emotional_weight(hard_won_success)

        assert isinstance(emotional_weight, (float, dict)), \
            "Emotional weight should be numeric or structured"

        if isinstance(emotional_weight, float):
            assert 0.0 <= emotional_weight <= 1.0, \
                f"Emotional weight should be 0-1, got {emotional_weight}"
            assert emotional_weight > 0.5, \
                f"Hard-won success should have high emotional weight: {emotional_weight}"

        elif isinstance(emotional_weight, dict):
            weight = emotional_weight.get("weight") or emotional_weight.get("intensity", 0.5)
            assert weight > 0.5, \
                f"Hard-won success should have high weight: {weight}"

    def test_result_to_emotional_weight_failure(self):
        """
        Failures should have emotional weight (negative valence).
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            result_to_emotional_weight
        )

        failure_result = {
            "tool_name": "deploy_service",
            "success": False,
            "error": "Deployment failed: connection refused",
            "duration_ms": 5000,
        }

        emotional_weight = result_to_emotional_weight(failure_result)

        if isinstance(emotional_weight, float):
            # Failures should have significant weight
            assert emotional_weight > 0.3, \
                f"Failures should have significant emotional weight: {emotional_weight}"

        elif isinstance(emotional_weight, dict):
            weight = emotional_weight.get("weight") or emotional_weight.get("intensity", 0.5)
            valence = emotional_weight.get("valence", "neutral")

            assert weight > 0.3, \
                f"Failures should have significant weight: {weight}"

            # Should indicate negative valence
            if isinstance(valence, str):
                assert valence in ["negative", "concerning", "frustrating"], \
                    f"Failure valence should be negative: {valence}"
            elif isinstance(valence, (int, float)):
                assert valence < 0, \
                    f"Failure valence should be negative: {valence}"

    def test_result_to_emotional_weight_routine_success(self):
        """
        Routine successful operations should have low emotional weight.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            result_to_emotional_weight
        )

        routine_result = {
            "tool_name": "read_config",
            "success": True,
            "result": {"setting": "value"},
            "duration_ms": 10,  # Quick
        }

        emotional_weight = result_to_emotional_weight(routine_result)

        if isinstance(emotional_weight, float):
            assert emotional_weight < 0.5, \
                f"Routine success should have low emotional weight: {emotional_weight}"

        elif isinstance(emotional_weight, dict):
            weight = emotional_weight.get("weight") or emotional_weight.get("intensity", 0.5)
            assert weight < 0.5, \
                f"Routine success should have low weight: {weight}"

    def test_emotional_weight_includes_valence(self):
        """
        Emotional weight should include valence (positive/negative/neutral).
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            result_to_emotional_weight
        )

        success_result = {
            "tool_name": "create_file",
            "success": True,
            "result": "File created",
        }

        failure_result = {
            "tool_name": "create_file",
            "success": False,
            "error": "Permission denied",
        }

        success_weight = result_to_emotional_weight(success_result)
        failure_weight = result_to_emotional_weight(failure_result)

        # If returning dict, should have valence
        if isinstance(success_weight, dict):
            assert "valence" in success_weight, \
                "Emotional weight should include valence"

            # Success should have positive valence
            success_valence = success_weight["valence"]
            if isinstance(success_valence, str):
                assert success_valence in ["positive", "satisfied", "good", "neutral"], \
                    f"Success should have positive valence: {success_valence}"
            elif isinstance(success_valence, (int, float)):
                assert success_valence >= 0, \
                    f"Success should have non-negative valence: {success_valence}"

        if isinstance(failure_weight, dict):
            assert "valence" in failure_weight, \
                "Emotional weight should include valence"

            # Failure should have negative valence
            failure_valence = failure_weight["valence"]
            if isinstance(failure_valence, str):
                assert failure_valence in ["negative", "frustrated", "concerned", "bad"], \
                    f"Failure should have negative valence: {failure_valence}"
            elif isinstance(failure_valence, (int, float)):
                assert failure_valence < 0, \
                    f"Failure should have negative valence: {failure_valence}"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestInnerVoiceSynthesisIntegration:
    """
    Integration tests for the full inner voice synthesis pipeline.
    """

    def test_full_synthesis_pipeline(self):
        """
        Test complete pipeline: result -> felt complexity -> emotional weight -> inner voice.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            synthesize_complete_inner_voice
        )

        tool_result = {
            "tool_name": "analyze_bug",
            "success": True,
            "result": {
                "bug_found": True,
                "severity": "high",
                "location": "auth_module.py:142",
                "description": "SQL injection vulnerability"
            },
            "duration_ms": 800,
        }

        affect_state = {
            "valence": 0.2,
            "arousal": 0.6,
            "mood": "focused",
        }

        result = synthesize_complete_inner_voice(tool_result, affect_state)

        # Should have all components
        assert "inner_voice" in result, "Missing inner_voice"
        assert "felt_complexity" in result, "Missing felt_complexity"
        assert "emotional_weight" in result, "Missing emotional_weight"

        # Inner voice should be meaningful
        assert len(result["inner_voice"]) > 20, \
            "Inner voice should be substantial narrative"

        # Should reflect the significance of finding a security bug
        significant_markers = [
            "important", "significant", "serious", "found", "bug",
            "security", "vulnerability", "issue", "attention"
        ]
        assert any(m in result["inner_voice"].lower() for m in significant_markers), \
            f"Finding security bug should be reflected in voice: {result['inner_voice']}"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
