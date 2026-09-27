"""
Tests for FairyShadow - Self-Monitoring and Evolution

TDD: These tests are written FIRST, before implementation.
Run with: python -m pytest tests/test_fairy_template/test_shadow.py -v
"""

import sys
import threading
import time
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest


class TestFairyShadowBasics:
    """Test FairyShadow creation and basic fields."""

    def test_creation_with_name(self):
        """FairyShadow requires a fairy_name."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        assert shadow.fairy_name == "TestFairy"

    def test_initial_error_count_is_zero(self):
        """New shadow has no errors."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        assert shadow.error_count == 0

    def test_initial_health_is_one(self):
        """New shadow has perfect health (1.0) with no data."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        assert shadow.health == 1.0

    def test_initial_success_rate_is_one(self):
        """New shadow has perfect success rate (1.0) with no data."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        assert shadow.success_rate == 1.0

    def test_initial_last_error_is_none(self):
        """New shadow has no last error."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        assert shadow.last_error is None

    def test_initial_evolution_score_is_zero(self):
        """New shadow has zero evolution score."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        assert shadow.evolution_score == 0.0


class TestFairyShadowErrorTracking:
    """Test error recording and tracking."""

    def test_record_error_increments_count(self):
        """Recording an error increments error_count."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_error(ValueError("test error"))
        assert shadow.error_count == 1

    def test_record_multiple_errors(self):
        """Recording multiple errors increments count correctly."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_error(ValueError("error 1"))
        shadow.record_error(RuntimeError("error 2"))
        shadow.record_error(TypeError("error 3"))
        assert shadow.error_count == 3

    def test_record_error_with_context(self):
        """Error can include context dict."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_error(ValueError("test"), context={"operation": "parse"})
        assert shadow.last_error is not None
        assert shadow.last_error["context"]["operation"] == "parse"

    def test_last_error_has_timestamp(self):
        """Last error includes timestamp."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_error(ValueError("test"))
        assert "ts" in shadow.last_error

    def test_last_error_has_error_message(self):
        """Last error includes error message."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_error(ValueError("specific message"))
        assert "specific message" in str(shadow.last_error["error"])

    def test_last_error_has_type(self):
        """Last error includes error type."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_error(ValueError("test"))
        assert shadow.last_error["type"] == "ValueError"

    def test_error_deque_maxlen_100(self):
        """Error deque has maxlen of 100."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        # Record 150 errors
        for i in range(150):
            shadow.record_error(ValueError(f"error {i}"))
        # Should only keep 100
        assert shadow.error_count == 100

    def test_last_error_is_most_recent(self):
        """last_error returns the most recently recorded error."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_error(ValueError("first"))
        shadow.record_error(ValueError("second"))
        shadow.record_error(ValueError("third"))
        assert "third" in str(shadow.last_error["error"])


class TestFairyShadowSuccessTracking:
    """Test success recording and tracking."""

    def test_record_success(self):
        """Recording success works."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_success()
        # Health should still be 1.0 with only successes
        assert shadow.health == 1.0

    def test_record_success_with_context(self):
        """Success can include context dict."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_success(context={"operation": "process"})
        # No direct accessor for success, but to_dict should work
        report = shadow.get_health_report()
        assert "success_count" in report

    def test_success_deque_maxlen_100(self):
        """Success deque has maxlen of 100."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        # Record 150 successes
        for i in range(150):
            shadow.record_success()
        # Check via health report
        report = shadow.get_health_report()
        assert report["success_count"] == 100


class TestFairyShadowHealth:
    """Test health computation."""

    def test_health_with_only_successes(self):
        """Health is 1.0 with only successes."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_success()
        shadow.record_success()
        shadow.record_success()
        assert shadow.health == 1.0

    def test_health_with_only_errors(self):
        """Health is 0.0 with only errors."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_error(ValueError("test"))
        shadow.record_error(ValueError("test"))
        assert shadow.health == 0.0

    def test_health_calculation_50_50(self):
        """Health is 0.5 with equal errors and successes."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_success()
        shadow.record_success()
        shadow.record_error(ValueError("test"))
        shadow.record_error(ValueError("test"))
        assert shadow.health == 0.5

    def test_health_calculation_75_percent(self):
        """Health is 0.75 with 3 successes, 1 error."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_success()
        shadow.record_success()
        shadow.record_success()
        shadow.record_error(ValueError("test"))
        assert shadow.health == 0.75

    def test_success_rate_equals_health(self):
        """success_rate property equals health."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_success()
        shadow.record_success()
        shadow.record_error(ValueError("test"))
        assert shadow.success_rate == shadow.health


class TestFairyShadowEvolution:
    """Test evolution tracking."""

    def test_record_observation(self):
        """record_observation increments observation count."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_observation()
        shadow.record_observation()
        report = shadow.get_health_report()
        assert report["observations"] == 2

    def test_record_reflection(self):
        """record_reflection increments reflection count."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_reflection()
        report = shadow.get_health_report()
        assert report["reflections"] == 1

    def test_record_crystallization(self):
        """record_crystallization increments crystallization count."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_crystallization()
        report = shadow.get_health_report()
        assert report["crystallizations"] == 1

    def test_evolution_score_observations_only(self):
        """Evolution score with only observations (weight 0.1)."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        # 10 observations * 0.1 weight = 1.0, but max is 1.0
        for _ in range(10):
            shadow.record_observation()
        assert shadow.evolution_score == 1.0

    def test_evolution_score_reflections_only(self):
        """Evolution score with only reflections (weight 0.3)."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        # 3 reflections * 0.3 weight = 0.9
        shadow.record_reflection()
        shadow.record_reflection()
        shadow.record_reflection()
        assert abs(shadow.evolution_score - 0.9) < 0.01

    def test_evolution_score_crystallizations_only(self):
        """Evolution score with only crystallizations (weight 0.6)."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        # 1 crystallization * 0.6 weight = 0.6
        shadow.record_crystallization()
        assert abs(shadow.evolution_score - 0.6) < 0.01

    def test_evolution_score_combined(self):
        """Evolution score combines all three with weights."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_observation()  # 0.1
        shadow.record_reflection()   # 0.3
        # Total = 0.4
        assert abs(shadow.evolution_score - 0.4) < 0.01

    def test_evolution_score_max_one(self):
        """Evolution score is capped at 1.0."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        # Add lots of everything
        for _ in range(100):
            shadow.record_observation()
            shadow.record_reflection()
            shadow.record_crystallization()
        assert shadow.evolution_score == 1.0


class TestFairyShadowShouldRest:
    """Test should_rest() method."""

    def test_should_rest_when_healthy(self):
        """should_rest returns False when health >= 0.3."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        # All successes = health 1.0
        shadow.record_success()
        shadow.record_success()
        shadow.record_success()
        assert shadow.should_rest() is False

    def test_should_rest_when_unhealthy(self):
        """should_rest returns True when health < 0.3."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        # 1 success, 9 errors = 10% health
        shadow.record_success()
        for _ in range(9):
            shadow.record_error(ValueError("test"))
        assert shadow.should_rest() is True

    def test_should_rest_boundary(self):
        """should_rest boundary at exactly 0.3."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        # 3 successes, 7 errors = 30% health
        for _ in range(3):
            shadow.record_success()
        for _ in range(7):
            shadow.record_error(ValueError("test"))
        # At 0.3, should NOT rest
        assert shadow.should_rest() is False


class TestFairyShadowSerialization:
    """Test serialization methods."""

    def test_get_health_report_contains_all_fields(self):
        """get_health_report returns all diagnostic fields."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_success()
        shadow.record_error(ValueError("test"))
        shadow.record_observation()
        shadow.record_reflection()
        shadow.record_crystallization()

        report = shadow.get_health_report()

        assert report["fairy_name"] == "TestFairy"
        assert "health" in report
        assert "error_count" in report
        assert "success_count" in report
        assert "success_rate" in report
        assert "last_error" in report
        assert "observations" in report
        assert "reflections" in report
        assert "crystallizations" in report
        assert "evolution_score" in report
        assert "should_rest" in report

    def test_to_dict_is_alias_for_get_health_report(self):
        """to_dict returns same as get_health_report."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_success()
        shadow.record_error(ValueError("test"))

        assert shadow.to_dict() == shadow.get_health_report()

    def test_to_dict_is_copy(self):
        """to_dict returns a copy, not internal state."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        d = shadow.to_dict()
        d["health"] = 0.0

        assert shadow.health == 1.0  # Original unchanged


class TestFairyShadowThreadSafety:
    """Test FairyShadow thread safety."""

    def test_concurrent_error_recording(self):
        """Concurrent error recording doesn't corrupt state."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        errors = []

        def record_errors():
            try:
                for i in range(50):
                    shadow.record_error(ValueError(f"error {i}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_errors) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # 4 threads * 50 errors = 200, but maxlen is 100
        assert shadow.error_count == 100

    def test_concurrent_success_recording(self):
        """Concurrent success recording doesn't corrupt state."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        errors = []

        def record_successes():
            try:
                for i in range(50):
                    shadow.record_success()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_successes) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # Health should still be 1.0 with only successes
        assert shadow.health == 1.0

    def test_concurrent_evolution_tracking(self):
        """Concurrent evolution tracking doesn't corrupt state."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        errors = []

        def track_observations():
            try:
                for _ in range(50):
                    shadow.record_observation()
            except Exception as e:
                errors.append(e)

        def track_reflections():
            try:
                for _ in range(50):
                    shadow.record_reflection()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=track_observations)
        t2 = threading.Thread(target=track_reflections)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors
        report = shadow.get_health_report()
        assert report["observations"] == 50
        assert report["reflections"] == 50

    def test_to_dict_during_updates(self):
        """to_dict returns consistent state during updates."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        snapshots = []
        errors = []

        def update_loop():
            try:
                for i in range(50):
                    shadow.record_error(ValueError("test"))
                    shadow.record_success()
            except Exception as e:
                errors.append(e)

        def snapshot_loop():
            try:
                for i in range(50):
                    d = shadow.to_dict()
                    snapshots.append(d)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=update_loop)
        t2 = threading.Thread(target=snapshot_loop)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors
        # All snapshots should have valid structure
        for snap in snapshots:
            assert "fairy_name" in snap
            assert "health" in snap
            assert 0.0 <= snap["health"] <= 1.0


class TestFairyShadowEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_error_with_none_context(self):
        """Error with None context works."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_error(ValueError("test"), context=None)
        assert shadow.error_count == 1

    def test_success_with_none_context(self):
        """Success with None context works."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_success(context=None)
        assert shadow.health == 1.0

    def test_empty_context_dict(self):
        """Empty context dict is accepted."""
        from fairy_template.shadow import FairyShadow

        shadow = FairyShadow(fairy_name="TestFairy")
        shadow.record_error(ValueError("test"), context={})
        shadow.record_success(context={})
        assert shadow.error_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
