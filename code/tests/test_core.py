# Test Core Components
# Run: python -m pytest test_core.py -v

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.checklist import Checklist, CheckStatus
from core.function import Function, EchoFunction, CounterFunction
from core.fairy import Fairy
from core.directory import Directory, get_directory, reset_directory
from core.config import Config, get_config, reset_config


class TestChecklist:
    """Test the checklist validation system."""

    def test_all_pass(self):
        """Checklist passes when all checks pass."""
        cl = Checklist("test")
        cl.add("check1", "Always passes", lambda: True)
        cl.add("check2", "Also passes", lambda: True)

        result = cl.run()
        assert result.all_passed
        assert result.passed_count == 2
        assert result.failed_count == 0

    def test_one_fail(self):
        """Checklist fails if ANY required check fails."""
        cl = Checklist("test")
        cl.add("check1", "Passes", lambda: True)
        cl.add("check2", "Fails", lambda: False)

        result = cl.run()
        assert not result.all_passed
        assert result.failed_count == 1

    def test_optional_check(self):
        """Optional checks don't fail the checklist."""
        cl = Checklist("test")
        cl.add("check1", "Passes", lambda: True)
        cl.add("check2", "Fails but optional", lambda: False, required=False)

        result = cl.run()
        assert result.all_passed  # Still passes because check2 is optional
        assert result.skipped_count == 1

    def test_exception_handling(self):
        """Exceptions in checks are caught and reported."""
        cl = Checklist("test")
        cl.add("check1", "Throws", lambda: 1/0)

        result = cl.run()
        assert not result.all_passed
        assert "Exception" in result.failures[0].message


class TestFunction:
    """Test the Function base class."""

    def test_echo_function(self):
        """EchoFunction echoes input."""
        fn = EchoFunction()
        assert fn.initialize()
        result = fn.call(message="hello")
        assert result == "Echo: hello"

    def test_counter_function(self):
        """CounterFunction counts calls."""
        fn = CounterFunction()
        assert fn.initialize()

        assert fn.call() == 1
        assert fn.call() == 2
        assert fn.call() == 3

    def test_metrics_tracked(self):
        """Function calls track metrics."""
        fn = EchoFunction()
        fn.initialize()

        fn.call(message="test")
        fn.call(message="test2")

        assert fn.metrics.calls_total == 2
        assert fn.metrics.calls_success == 2
        assert fn.metrics.success_rate == 1.0


class TestFairy:
    """Test the Fairy base class."""

    def test_basic_fairy(self):
        """Create and boot a basic fairy."""
        fairy = Fairy(name="TestFairy", plane="P00")
        assert fairy.boot()
        assert fairy.status.value == "awake"

    def test_fairy_with_function(self):
        """Fairy can manage functions."""
        fairy = Fairy(name="TestFairy", plane="P00")
        fn = EchoFunction()

        fairy.register_function(fn)
        assert "echo" in fairy.list_functions()

        assert fairy.boot()
        assert fairy.get_function("echo").is_ready()

    def test_intent_registration(self):
        """Fairy can register and invoke intents."""
        fairy = Fairy(name="TestFairy", plane="P00")

        fairy.register_intent(
            "greet",
            "Say hello",
            lambda params: f"Hello {params.get('name', 'world')}"
        )

        result = fairy.invoke_intent("greet", {"name": "Ace"})
        assert result == "Hello Ace"


class TestDirectory:
    """Test the Directory."""

    def setup_method(self):
        """Reset directory before each test."""
        reset_directory()

    def test_registration(self):
        """Fairies can register with directory."""
        directory = get_directory()
        fairy = Fairy(name="TestFairy", plane="P00")
        fairy.boot()

        directory.register(fairy, capabilities={"test", "demo"})

        assert "TestFairy" in directory.list_names()
        assert directory.get("TestFairy") is not None

    def test_find_by_capability(self):
        """Can find fairies by capability."""
        directory = get_directory()

        fairy1 = Fairy(name="Fairy1", plane="P00")
        fairy2 = Fairy(name="Fairy2", plane="P00")
        fairy1.boot()
        fairy2.boot()

        directory.register(fairy1, capabilities={"memory"})
        directory.register(fairy2, capabilities={"memory", "recall"})

        memory_fairies = directory.find_by_capability("memory")
        assert len(memory_fairies) == 2

        recall_fairies = directory.find_by_capability("recall")
        assert len(recall_fairies) == 1

    def test_find_by_plane(self):
        """Can find fairies by plane."""
        directory = get_directory()

        fairy1 = Fairy(name="Fairy1", plane="P00")
        fairy2 = Fairy(name="Fairy2", plane="P10")
        fairy1.boot()
        fairy2.boot()

        directory.register(fairy1)
        directory.register(fairy2)

        p00 = directory.find_by_plane("P00")
        p10 = directory.find_by_plane("P10")

        assert len(p00) == 1
        assert len(p10) == 1
        assert p00[0].name == "Fairy1"

    def test_system_health(self):
        """Directory reports system health."""
        directory = get_directory()

        fairy = Fairy(name="TestFairy", plane="P00")
        fairy.boot()
        directory.register(fairy)

        health = directory.system_health()
        assert health["fairies_total"] == 1
        assert health["fairies_awake"] == 1
        assert health["health_percent"] == 100.0


class TestConfig:
    """Test the Config system."""

    def setup_method(self):
        reset_config()

    def test_get_default(self):
        """Can get default config values."""
        config = get_config()
        workers = config.get("postal.worker_count")
        assert workers == 32

    def test_set_adjustable(self):
        """Can set adjustable values."""
        config = get_config()
        assert config.set("postal.worker_count", 64)
        assert config.get("postal.worker_count") == 64

    def test_validation(self):
        """Values are validated against constraints."""
        config = get_config()

        # Should fail - below min
        assert not config.set("postal.worker_count", 1)
        assert config.get("postal.worker_count") == 32  # Unchanged

        # Should fail - above max
        assert not config.set("postal.worker_count", 500)

    def test_reset(self):
        """Can reset to defaults."""
        config = get_config()
        config.set("postal.worker_count", 64)
        config.reset("postal.worker_count")
        assert config.get("postal.worker_count") == 32


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
