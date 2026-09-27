"""
Tests for UnifiedFairy - The Complete Organ Template

TDD: These tests are written FIRST, before implementation.
Run with: python -m pytest tests/test_fairy_template/test_unified.py -v
"""

import sys
import threading
import time
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest


class TestUnifiedFairyIdentity:
    """Test UnifiedFairy identity class variables."""

    def test_default_actor_name(self):
        """Default ACTOR_NAME is 'UnifiedFairy'."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        assert fairy.ACTOR_NAME == "UnifiedFairy"

    def test_default_plane(self):
        """Default PLANE is 'P00'."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        assert fairy.PLANE == "P00"

    def test_default_channel(self):
        """Default CHANNEL is empty string."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        assert fairy.CHANNEL == ""

    def test_default_purpose(self):
        """Default PURPOSE is 'Base unified fairy'."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        assert fairy.PURPOSE == "Base unified fairy"

    def test_default_mantra(self):
        """Default MANTRA is empty string."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        assert fairy.MANTRA == ""

    def test_default_capabilities(self):
        """Default CAPABILITIES is empty list."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        assert fairy.CAPABILITIES == []

    def test_default_subscriptions(self):
        """Default SUBSCRIPTIONS is empty list."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        assert fairy.SUBSCRIPTIONS == []

    def test_subclass_can_override_identity(self):
        """Subclass can override identity class variables."""
        from fairy_template.unified import UnifiedFairy

        class CustomFairy(UnifiedFairy):
            ACTOR_NAME = "CustomFairy"
            PLANE = "P30"
            CHANNEL = "cognition"
            PURPOSE = "Custom processing"
            MANTRA = "Think deeply"
            CAPABILITIES = ["process", "analyze"]
            SUBSCRIPTIONS = ["cognition.input", "cognition.query"]

        fairy = CustomFairy()
        assert fairy.ACTOR_NAME == "CustomFairy"
        assert fairy.PLANE == "P30"
        assert fairy.CHANNEL == "cognition"
        assert fairy.PURPOSE == "Custom processing"
        assert fairy.MANTRA == "Think deeply"
        assert fairy.CAPABILITIES == ["process", "analyze"]
        assert fairy.SUBSCRIPTIONS == ["cognition.input", "cognition.query"]


class TestUnifiedFairyComponents:
    """Test UnifiedFairy built-in components."""

    def test_has_body(self):
        """UnifiedFairy has a body component."""
        from fairy_template.unified import UnifiedFairy
        from fairy_template.body import FairyBody

        fairy = UnifiedFairy()
        assert hasattr(fairy, "body")
        assert isinstance(fairy.body, FairyBody)

    def test_body_uses_actor_name(self):
        """Body component uses fairy's ACTOR_NAME."""
        from fairy_template.unified import UnifiedFairy

        class NamedFairy(UnifiedFairy):
            ACTOR_NAME = "NamedFairy"

        fairy = NamedFairy()
        assert fairy.body.fairy_name == "NamedFairy"

    def test_has_shadow(self):
        """UnifiedFairy has a shadow component."""
        from fairy_template.unified import UnifiedFairy
        from fairy_template.shadow import FairyShadow

        fairy = UnifiedFairy()
        assert hasattr(fairy, "shadow")
        assert isinstance(fairy.shadow, FairyShadow)

    def test_shadow_uses_actor_name(self):
        """Shadow component uses fairy's ACTOR_NAME."""
        from fairy_template.unified import UnifiedFairy

        class NamedFairy(UnifiedFairy):
            ACTOR_NAME = "NamedFairy"

        fairy = NamedFairy()
        assert fairy.shadow.fairy_name == "NamedFairy"

    def test_has_workers(self):
        """UnifiedFairy has a workers component."""
        from fairy_template.unified import UnifiedFairy
        from fairy_template.workers import FairyWorkerPool

        fairy = UnifiedFairy()
        assert hasattr(fairy, "workers")
        assert isinstance(fairy.workers, FairyWorkerPool)

    def test_workers_uses_actor_name(self):
        """Workers component uses fairy's ACTOR_NAME."""
        from fairy_template.unified import UnifiedFairy

        class NamedFairy(UnifiedFairy):
            ACTOR_NAME = "NamedFairy"

        fairy = NamedFairy()
        assert fairy.workers.fairy_name == "NamedFairy"

    def test_workers_default_max_workers(self):
        """Workers default to 4 max workers."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        assert fairy.workers.max_workers == 4

    def test_has_post_attribute(self):
        """UnifiedFairy has a post attribute (None before boot)."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        assert hasattr(fairy, "post")
        # post is None until boot provides shared postal hub
        assert fairy.post is None


class TestUnifiedFairyLifecycle:
    """Test UnifiedFairy lifecycle methods."""

    def test_boot_returns_bool(self):
        """boot() returns a boolean."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        result = fairy.boot()
        assert isinstance(result, bool)
        # Cleanup
        fairy.shutdown()

    def test_boot_sets_running(self):
        """boot() sets is_running to True on success."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()
        assert fairy.is_running is True
        fairy.shutdown()

    def test_boot_records_boot_time(self):
        """boot() records the boot time."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        before = time.time()
        fairy.boot()
        after = time.time()
        assert fairy._boot_time is not None
        assert before <= fairy._boot_time <= after
        fairy.shutdown()

    def test_shutdown_returns_bool(self):
        """shutdown() returns a boolean."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()
        result = fairy.shutdown()
        assert isinstance(result, bool)

    def test_shutdown_stops_running(self):
        """shutdown() sets is_running to False."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()
        fairy.shutdown()
        assert fairy.is_running is False

    def test_on_boot_hook_called(self):
        """on_boot() hook is called during boot."""
        from fairy_template.unified import UnifiedFairy

        class HookFairy(UnifiedFairy):
            boot_called = False

            def on_boot(self) -> bool:
                HookFairy.boot_called = True
                return True

        fairy = HookFairy()
        fairy.boot()
        assert HookFairy.boot_called is True
        fairy.shutdown()

    def test_on_boot_failure_fails_boot(self):
        """on_boot() returning False fails the boot."""
        from fairy_template.unified import UnifiedFairy

        class FailingFairy(UnifiedFairy):
            def on_boot(self) -> bool:
                return False

        fairy = FailingFairy()
        result = fairy.boot()
        assert result is False
        assert fairy.is_running is False

    def test_on_shutdown_hook_called(self):
        """on_shutdown() hook is called during shutdown."""
        from fairy_template.unified import UnifiedFairy

        class HookFairy(UnifiedFairy):
            shutdown_called = False

            def on_shutdown(self) -> bool:
                HookFairy.shutdown_called = True
                return True

        fairy = HookFairy()
        fairy.boot()
        fairy.shutdown()
        assert HookFairy.shutdown_called is True

    def test_on_tick_hook_exists(self):
        """on_tick() method exists and can be called."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        # Should not raise
        fairy.on_tick(1)


class TestUnifiedFairyLearning:
    """Test UnifiedFairy learning methods."""

    def test_observe_records_to_shadow(self):
        """observe() records to shadow and returns observation."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()

        result = fairy.observe(
            action="test_action",
            input_summary="test input",
            output_summary="test output",
            success=True,
            duration_ms=100
        )

        assert isinstance(result, dict)
        assert result["action"] == "test_action"
        assert result["success"] is True
        # Shadow should have recorded observation
        assert fairy.shadow._observations > 0
        fairy.shutdown()

    def test_observe_emits_to_postal(self):
        """observe() emits observation to postal if connected."""
        from fairy_template.unified import UnifiedFairy

        emissions = []

        class PostalMock:
            def publish(self, topic, payload, priority=1):
                emissions.append((topic, payload))
                return True

        fairy = UnifiedFairy()
        fairy.post = PostalMock()
        fairy.boot()

        fairy.observe(action="test", success=True)

        # Should have emitted to learning channel
        learning_emissions = [e for e in emissions if "learning" in e[0]]
        assert len(learning_emissions) > 0
        fairy.shutdown()

    def test_reflect_records_to_shadow(self):
        """reflect() records to shadow and returns reflection."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()

        result = fairy.reflect(
            topic="test_topic",
            thought="This is a test thought",
            insight_type="general",
            confidence=0.7
        )

        assert isinstance(result, dict)
        assert result["topic"] == "test_topic"
        assert result["confidence"] == 0.7
        # Shadow should have recorded reflection
        assert fairy.shadow._reflections > 0
        fairy.shutdown()

    def test_crystallize_records_learning(self):
        """crystallize() creates a learning record."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()

        result = fairy.crystallize(
            learning_type="pattern",
            content="Test pattern learned",
            confidence=0.8
        )

        assert isinstance(result, dict)
        assert result["type"] == "pattern"
        assert result["content"] == "Test pattern learned"
        assert result["confidence"] == 0.8
        # Shadow should have recorded crystallization
        assert fairy.shadow._crystallizations > 0
        fairy.shutdown()


class TestUnifiedFairyState:
    """Test UnifiedFairy state methods."""

    def test_status_returns_dict(self):
        """status() returns a dictionary."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        status = fairy.status()
        assert isinstance(status, dict)

    def test_status_contains_identity(self):
        """status() contains identity fields."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        status = fairy.status()
        assert "name" in status
        assert "plane" in status
        assert status["name"] == "UnifiedFairy"
        assert status["plane"] == "P00"

    def test_status_contains_state(self):
        """status() contains state fields."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()
        status = fairy.status()
        assert "is_running" in status
        assert "uptime" in status
        assert status["is_running"] is True
        fairy.shutdown()

    def test_status_contains_components(self):
        """status() contains component statuses."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        status = fairy.status()
        assert "body" in status
        assert "shadow" in status
        assert "workers" in status

    def test_log_method_exists(self):
        """log() method exists and accepts message and level."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        # Should not raise
        fairy.log("test message", level="info")
        fairy.log("warning message", level="warn")
        fairy.log("error message", level="error")


class TestUnifiedFairyProperties:
    """Test UnifiedFairy properties."""

    def test_is_running_false_before_boot(self):
        """is_running is False before boot."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        assert fairy.is_running is False

    def test_is_running_true_after_boot(self):
        """is_running is True after boot."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()
        assert fairy.is_running is True
        fairy.shutdown()

    def test_is_awake_after_boot(self):
        """is_awake is True after boot (not in sleep mode)."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()
        # After boot, fairy should be awake
        assert fairy.is_awake is True
        fairy.shutdown()

    def test_uptime_zero_before_boot(self):
        """uptime is 0.0 before boot."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        assert fairy.uptime == 0.0

    def test_uptime_increases_after_boot(self):
        """uptime increases after boot."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()
        time.sleep(0.1)
        assert fairy.uptime > 0
        fairy.shutdown()


class TestUnifiedFairySubclassing:
    """Test that UnifiedFairy can be properly subclassed."""

    def test_custom_fairy_with_all_overrides(self):
        """Custom fairy can override all identity and hooks."""
        from fairy_template.unified import UnifiedFairy

        class TestFairy(UnifiedFairy):
            ACTOR_NAME = "TestFairy"
            PLANE = "P40"
            CHANNEL = "sensory"
            PURPOSE = "Test sensory processing"
            MANTRA = "Sense and respond"
            CAPABILITIES = ["sense", "respond"]
            SUBSCRIPTIONS = ["sensory.input"]

            boot_hook_called = False
            shutdown_hook_called = False
            tick_hook_called = False

            def on_boot(self) -> bool:
                TestFairy.boot_hook_called = True
                return True

            def on_shutdown(self) -> bool:
                TestFairy.shutdown_hook_called = True
                return True

            def on_tick(self, beat: int):
                TestFairy.tick_hook_called = True

        fairy = TestFairy()
        assert fairy.ACTOR_NAME == "TestFairy"
        assert fairy.body.fairy_name == "TestFairy"
        assert fairy.shadow.fairy_name == "TestFairy"
        assert fairy.workers.fairy_name == "TestFairy"

        fairy.boot()
        assert TestFairy.boot_hook_called is True

        fairy.on_tick(1)
        assert TestFairy.tick_hook_called is True

        fairy.shutdown()
        assert TestFairy.shutdown_hook_called is True


class TestUnifiedFairyWorkerIntegration:
    """Test that workers integrate properly with the fairy."""

    def test_can_submit_work(self):
        """Can submit work to workers through the fairy."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()

        def test_fn(x):
            return x * 2

        tracer_id = fairy.workers.submit(fn=test_fn, args=(5,), intent="test")
        result = fairy.workers.get_result(tracer_id, timeout=5.0)
        assert result == 10
        fairy.shutdown()

    def test_shutdown_cleans_up_workers(self):
        """shutdown() cleans up the worker pool."""
        from fairy_template.unified import UnifiedFairy

        fairy = UnifiedFairy()
        fairy.boot()

        # Submit some work
        fairy.workers.submit(fn=lambda: None, intent="test")

        fairy.shutdown()
        # Workers should be shut down - further submits may fail
        # Just verify shutdown completes without error


class TestUnifiedFairyCriticality:
    """Test criticality levels and energy management."""

    def test_default_criticality_is_app(self):
        """Default criticality is 'app' (can fizzle)."""
        from fairy_template.unified import UnifiedFairy
        fairy = UnifiedFairy()
        assert fairy.CRITICALITY == "app"
        fairy.workers.shutdown(wait=False)

    def test_critical_fairy_cannot_fizzle(self):
        """Critical fairies cannot fizzle spells."""
        from fairy_template.unified import UnifiedFairy

        class CriticalFairy(UnifiedFairy):
            ACTOR_NAME = "CriticalFairy"
            CRITICALITY = "critical"

        fairy = CriticalFairy()
        assert fairy.is_critical == True
        assert fairy.can_fizzle == False
        fairy.workers.shutdown(wait=False)

    def test_app_fairy_can_fizzle(self):
        """App fairies can fizzle spells."""
        from fairy_template.unified import UnifiedFairy

        class AppFairy(UnifiedFairy):
            ACTOR_NAME = "AppFairy"
            CRITICALITY = "app"

        fairy = AppFairy()
        assert fairy.is_critical == False
        assert fairy.can_fizzle == True
        fairy.workers.shutdown(wait=False)

    def test_energy_thresholds_for_critical(self):
        """Critical fairies have higher sleep threshold (30%)."""
        from fairy_template.unified import UnifiedFairy

        class CriticalFairy(UnifiedFairy):
            CRITICALITY = "critical"

        fairy = CriticalFairy()
        thresholds = fairy.energy_thresholds
        assert thresholds["sleep_at"] == 0.30
        assert thresholds["wake_at"] == 0.70
        assert thresholds["fizzle_allowed"] == False
        fairy.workers.shutdown(wait=False)

    def test_energy_thresholds_for_important(self):
        """Important fairies have medium sleep threshold (20%)."""
        from fairy_template.unified import UnifiedFairy

        class ImportantFairy(UnifiedFairy):
            CRITICALITY = "important"

        fairy = ImportantFairy()
        thresholds = fairy.energy_thresholds
        assert thresholds["sleep_at"] == 0.20
        assert thresholds["wake_at"] == 0.50
        assert thresholds["fizzle_allowed"] == False
        fairy.workers.shutdown(wait=False)

    def test_energy_thresholds_for_app(self):
        """App fairies have low sleep threshold (10%)."""
        from fairy_template.unified import UnifiedFairy

        class AppFairy(UnifiedFairy):
            CRITICALITY = "app"

        fairy = AppFairy()
        thresholds = fairy.energy_thresholds
        assert thresholds["sleep_at"] == 0.10
        assert thresholds["wake_at"] == 0.30
        assert thresholds["fizzle_allowed"] == True
        fairy.workers.shutdown(wait=False)

    def test_should_sleep_based_on_energy(self):
        """should_sleep is True when energy below threshold."""
        from fairy_template.unified import UnifiedFairy

        class CriticalFairy(UnifiedFairy):
            CRITICALITY = "critical"

        fairy = CriticalFairy()
        # Full energy - should NOT sleep
        assert fairy.should_sleep == False
        # Drop energy below threshold
        fairy.body.update_somatic({"energy": 0.25})
        assert fairy.should_sleep == True
        fairy.workers.shutdown(wait=False)

    def test_check_energy_status(self):
        """check_energy_status returns full energy report."""
        from fairy_template.unified import UnifiedFairy
        fairy = UnifiedFairy()
        status = fairy.check_energy_status()
        assert "energy" in status
        assert "criticality" in status
        assert "should_sleep" in status
        assert "can_fizzle" in status
        assert "status" in status
        assert "thresholds" in status
        fairy.workers.shutdown(wait=False)

    def test_energy_status_healthy(self):
        """Status is 'healthy' when energy above wake threshold."""
        from fairy_template.unified import UnifiedFairy
        fairy = UnifiedFairy()
        fairy.body.update_somatic({"energy": 0.8})
        status = fairy.check_energy_status()
        assert status["status"] == "healthy"
        fairy.workers.shutdown(wait=False)

    def test_energy_status_warning(self):
        """Status is 'warning' when energy between sleep and wake."""
        from fairy_template.unified import UnifiedFairy
        fairy = UnifiedFairy()
        # App: sleep_at=0.10, wake_at=0.30, so 0.20 is warning
        fairy.body.update_somatic({"energy": 0.20})
        status = fairy.check_energy_status()
        assert status["status"] == "warning"
        fairy.workers.shutdown(wait=False)

    def test_energy_status_critical(self):
        """Status is 'critical' when energy below sleep threshold."""
        from fairy_template.unified import UnifiedFairy
        fairy = UnifiedFairy()
        fairy.body.update_somatic({"energy": 0.05})
        status = fairy.check_energy_status()
        assert status["status"] == "critical"
        fairy.workers.shutdown(wait=False)


class TestUnifiedFairyPostalAddressing:
    """Test postal addressing system - ID, PLANE, CHANNEL."""

    def test_postal_address_with_channel(self):
        """Postal address is PLANE.CHANNEL when channel set."""
        from fairy_template.unified import UnifiedFairy

        class WeatherFairy(UnifiedFairy):
            ACTOR_NAME = "WeatherFairy"
            PLANE = "P40"
            CHANNEL = "weather"

        fairy = WeatherFairy()
        assert fairy.postal_address == "P40.weather"
        fairy.workers.shutdown(wait=False)

    def test_postal_address_without_channel(self):
        """Postal address is just PLANE when no channel."""
        from fairy_template.unified import UnifiedFairy

        class BaseFairy(UnifiedFairy):
            ACTOR_NAME = "BaseFairy"
            PLANE = "P00"
            CHANNEL = ""

        fairy = BaseFairy()
        assert fairy.postal_address == "P00"
        fairy.workers.shutdown(wait=False)

    def test_full_address_includes_name(self):
        """Full address is PLANE.CHANNEL.ACTOR_NAME."""
        from fairy_template.unified import UnifiedFairy

        class CognitionFairy(UnifiedFairy):
            ACTOR_NAME = "CognitionFairy"
            PLANE = "P30"
            CHANNEL = "cognition"

        fairy = CognitionFairy()
        assert fairy.full_address == "P30.cognition.CognitionFairy"
        fairy.workers.shutdown(wait=False)

    def test_send_to_returns_false_without_postal(self):
        """send_to returns False when postal not available."""
        from fairy_template.unified import UnifiedFairy
        fairy = UnifiedFairy()
        # post is None by default (no shared postal)
        result = fairy.send_to("P30.cognition", {"test": True})
        assert result == False
        fairy.workers.shutdown(wait=False)

    def test_broadcast_returns_false_without_postal(self):
        """broadcast returns False when postal not available."""
        from fairy_template.unified import UnifiedFairy
        fairy = UnifiedFairy()
        result = fairy.broadcast({"test": True})
        assert result == False
        fairy.workers.shutdown(wait=False)

    def test_send_to_enriches_payload(self):
        """send_to adds sender info to payload."""
        from fairy_template.unified import UnifiedFairy

        # Mock postal hub
        class MockPostal:
            def __init__(self):
                self.published = []
            def publish(self, topic, payload):
                self.published.append((topic, payload))
            def subscribe(self, topic, handler):
                pass

        class SenderFairy(UnifiedFairy):
            ACTOR_NAME = "SenderFairy"
            PLANE = "P40"
            CHANNEL = "sensory"

        fairy = SenderFairy()
        fairy.post = MockPostal()
        fairy.send_to("P30.cognition", {"data": "test"})

        assert len(fairy.post.published) == 1
        topic, payload = fairy.post.published[0]
        assert topic == "P30.cognition"
        assert payload["from"] == "P40.sensory.SenderFairy"
        assert payload["from_plane"] == "P40"
        assert payload["from_fairy"] == "SenderFairy"
        assert payload["data"] == "test"
        fairy.workers.shutdown(wait=False)

    def test_no_cross_talk_principle(self):
        """Fairies communicate through channels, not direct calls."""
        from fairy_template.unified import UnifiedFairy

        # This test verifies the API enforces the pattern:
        # - send_to(channel, payload) for sending
        # - _on_message() for receiving
        # - No direct fairy.method() calls between fairies

        class FairyA(UnifiedFairy):
            ACTOR_NAME = "FairyA"
            PLANE = "P30"
            CHANNEL = "alpha"

        class FairyB(UnifiedFairy):
            ACTOR_NAME = "FairyB"
            PLANE = "P40"
            CHANNEL = "beta"

        fairy_a = FairyA()
        fairy_b = FairyB()

        # Verify they have different addresses (no collision)
        assert fairy_a.postal_address != fairy_b.postal_address
        assert fairy_a.full_address != fairy_b.full_address

        # The ONLY way to communicate is through postal
        # (No fairy_a.call_fairy_b() methods exist)
        assert not hasattr(fairy_a, 'call')
        assert hasattr(fairy_a, 'send_to')
        assert hasattr(fairy_a, 'broadcast')

        fairy_a.workers.shutdown(wait=False)
        fairy_b.workers.shutdown(wait=False)


class TestUnifiedFairyDocstring:
    """Test that UnifiedFairy has proper documentation."""

    def test_module_docstring_exists(self):
        """Module has a docstring."""
        from fairy_template import unified
        assert unified.__doc__ is not None
        assert "Unified Fairy" in unified.__doc__

    def test_class_docstring_mentions_components(self):
        """Class docstring mentions body, shadow, workers."""
        from fairy_template.unified import UnifiedFairy
        assert UnifiedFairy.__doc__ is not None
        # Should mention the key components
        doc = UnifiedFairy.__doc__.lower()
        assert "body" in doc or "somatic" in doc
        assert "shadow" in doc or "monitor" in doc
        assert "worker" in doc or "tracer" in doc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
