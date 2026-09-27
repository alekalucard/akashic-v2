"""
Tests for Cardinal Sprint 1: Proactive Administration

Tests the gap detection → pattern tracking pipeline without full system boot.
Run: python -m pytest fairies/P20_Somatic/SomaticMindFairy/tests/test_cardinal_sprint1.py -v
Or:  python fairies/P20_Somatic/SomaticMindFairy/tests/test_cardinal_sprint1.py
"""

import sys
import time
from pathlib import Path
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Add project root to path
ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

# ═══════════════════════════════════════════════════════════════════════════
# MOCK SYSTEMS — simulate what the real system provides
# ═══════════════════════════════════════════════════════════════════════════

class MockPostal:
    """Mock postal system that captures published messages."""
    def __init__(self):
        self.published = []
        self._subscriptions = {}

    def publish(self, topic, payload):
        self.published.append({"topic": topic, "payload": payload})

    def subscribe(self, topic, handler):
        self._subscriptions[topic] = handler

    def get_published(self, topic_filter=None):
        if topic_filter:
            return [m for m in self.published if topic_filter in m["topic"]]
        return self.published


# Mock CognitionCycle with goal/result
class MockGoalDomain(Enum):
    INTROSPECTION = "introspection"
    DIAGNOSIS = "diagnosis"
    EXPLORATION = "exploration"
    COMMUNICATION = "communication"

class MockSuccessLevel(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial_success"

@dataclass
class MockGoal:
    name: str
    domain: MockGoalDomain

@dataclass
class MockResult:
    status: MockSuccessLevel
    success_level: Optional[MockSuccessLevel] = None

@dataclass
class MockCycle:
    goal: MockGoal
    result: MockResult
    duration: float = 1.0


class MockRewardTracker:
    def __init__(self):
        self._current_difficulty = 0.5

    @property
    def current_difficulty(self):
        return self._current_difficulty

    def status(self):
        return {
            "samples": 10,
            "difficulty": self._current_difficulty,
            "avg_reward": 0.4,
            "learning_efficiency": 0.5,
            "cumulative_reward": 4.0,
            "status_distribution": {},
        }


class MockCognitionLoop:
    """Mock CognitionLoop with history."""
    def __init__(self):
        self._history = deque(maxlen=100)
        self._reward_tracker = MockRewardTracker()

    def add_cycle(self, goal_name, domain, success, duration=1.0):
        d = MockGoalDomain(domain)
        status = MockSuccessLevel.SUCCESS if success else MockSuccessLevel.FAILURE
        self._history.append(MockCycle(
            goal=MockGoal(name=goal_name, domain=d),
            result=MockResult(status=status, success_level=status),
            duration=duration,
        ))


class MockTracerRegistry:
    def __init__(self):
        self._expired_count = 0

    def get_stats(self):
        return {
            "total_tracers": 50,
            "fairies_tracked": 12,
            "by_status": {"active": 30, "completed": 15, "failed": 5},
        }

    def cleanup_expired(self):
        self._expired_count += 3
        return 3  # Cleaned 3


# ═══════════════════════════════════════════════════════════════════════════
# TEST: AdminTaskQueue stub wiring
# ═══════════════════════════════════════════════════════════════════════════

def test_admin_task_queue_imports():
    """admin_tasks.py imports without error."""
    from fairies.P20_Somatic.SomaticMindFairy.admin_tasks import AdminTaskQueue, create_admin_task_queue
    print("  ✓ AdminTaskQueue imported")
    return True


def test_admin_queue_creation():
    """AdminTaskQueue creates with all tasks registered."""
    from fairies.P20_Somatic.SomaticMindFairy.admin_tasks import AdminTaskQueue

    postal = MockPostal()
    queue = AdminTaskQueue(systems={"postal": postal})

    tasks = queue.list_tasks()
    task_names = [t["name"] for t in tasks]

    assert "memory_consolidation_nudge" in task_names, "Missing memory_consolidation_nudge"
    assert "stale_tracer_cleanup" in task_names, "Missing stale_tracer_cleanup"
    assert "dead_letter_scan" in task_names, "Missing dead_letter_scan"
    assert "learning_edge_calibration" in task_names, "Missing learning_edge_calibration"
    assert "ace_presence_check" in task_names, "Missing ace_presence_check"
    assert "capability_gap_scan" in task_names, "Missing capability_gap_scan"

    print(f"  ✓ All {len(tasks)} tasks registered: {task_names}")
    return True


def test_tracer_cleanup_wired():
    """Tracer cleanup calls TracerRegistry.cleanup_expired()."""
    from fairies.P20_Somatic.SomaticMindFairy.admin_tasks import AdminTaskQueue

    registry = MockTracerRegistry()
    postal = MockPostal()
    queue = AdminTaskQueue(systems={
        "tracer_registry": registry,
        "postal": postal,
    })

    result = queue.force_run("stale_tracer_cleanup")
    assert result["ok"] is True
    assert result["tracers_cleaned"] == 3
    assert result["wired"] is True
    assert result["total_tracers"] == 50

    # Should have published cleanup event
    cleaned_msgs = postal.get_published("admin.tracers_cleaned")
    assert len(cleaned_msgs) == 1
    print(f"  ✓ Tracer cleanup: {result}")
    return True


def test_dead_letter_scan_wired():
    """Dead letter scan reports orphan/congested when no fabric available."""
    from fairies.P20_Somatic.SomaticMindFairy.admin_tasks import AdminTaskQueue

    queue = AdminTaskQueue(systems={})
    result = queue.force_run("dead_letter_scan")
    assert result["ok"] is True
    assert result["wired"] is False
    print(f"  ✓ Dead letter scan (unwired): {result}")
    return True


def test_learning_calibration_wired():
    """Learning calibration reads CognitionLoop reward tracker."""
    from fairies.P20_Somatic.SomaticMindFairy.admin_tasks import AdminTaskQueue

    cog = MockCognitionLoop()
    postal = MockPostal()
    queue = AdminTaskQueue(systems={
        "cognition_loop": cog,
        "postal": postal,
    })

    result = queue.force_run("learning_edge_calibration")
    assert result["ok"] is True
    assert result["wired"] is True
    assert result["current_difficulty"] == 0.5
    assert result["samples"] == 10
    print(f"  ✓ Learning calibration: {result}")
    return True


def test_ace_presence_check():
    """Ace presence check runs without crash (may fail gracefully on import)."""
    from fairies.P20_Somatic.SomaticMindFairy.admin_tasks import AdminTaskQueue

    postal = MockPostal()
    queue = AdminTaskQueue(systems={"postal": postal})

    result = queue.force_run("ace_presence_check")
    assert result["ok"] is True
    # May not have InterfacePresence importable — that's fine
    print(f"  ✓ Ace presence check: {result}")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Capability Gap Scan
# ═══════════════════════════════════════════════════════════════════════════

def test_gap_scan_empty_history():
    """Gap scan with no cognition history returns empty gaps."""
    from fairies.P20_Somatic.SomaticMindFairy.admin_tasks import AdminTaskQueue

    cog = MockCognitionLoop()
    queue = AdminTaskQueue(systems={"cognition_loop": cog})

    result = queue.force_run("capability_gap_scan")
    assert result["ok"] is True
    assert result["gaps"] == []
    assert result["wired"] is True
    print(f"  ✓ Gap scan empty: {result}")
    return True


def test_gap_scan_detects_repeated_failures():
    """Gap scan detects repeated failures in same domain."""
    from fairies.P20_Somatic.SomaticMindFairy.admin_tasks import AdminTaskQueue

    cog = MockCognitionLoop()
    postal = MockPostal()

    # Add 5 failures in diagnosis domain
    for i in range(5):
        cog.add_cycle("check_health", "diagnosis", success=False)
    # Add 2 successes in exploration
    cog.add_cycle("explore_code", "exploration", success=True)
    cog.add_cycle("explore_docs", "exploration", success=True)

    queue = AdminTaskQueue(systems={"cognition_loop": cog, "postal": postal})
    result = queue.force_run("capability_gap_scan")

    assert result["ok"] is True
    assert result["total_gaps"] >= 1
    assert result["failures_found"] == 5

    # Should find repeated_failure gap for diagnosis
    gap_domains = [g["domain"] for g in result["gaps"]]
    assert "diagnosis" in gap_domains, f"Expected 'diagnosis' in gaps but got: {gap_domains}"

    # Should have published to cardinal.gaps_detected
    gap_msgs = postal.get_published("cardinal.gaps_detected")
    assert len(gap_msgs) == 1

    print(f"  ✓ Gap scan detects failures: {result['gaps']}")
    return True


def test_gap_scan_detects_slow_goals():
    """Gap scan detects slow goals (capability inefficiency)."""
    from fairies.P20_Somatic.SomaticMindFairy.admin_tasks import AdminTaskQueue

    cog = MockCognitionLoop()

    # Add cycles with varying durations — 2 are 5x the average
    cog.add_cycle("check_a", "diagnosis", success=True, duration=1.0)
    cog.add_cycle("check_b", "diagnosis", success=True, duration=1.0)
    cog.add_cycle("check_c", "diagnosis", success=True, duration=1.0)
    cog.add_cycle("check_d", "diagnosis", success=True, duration=10.0)  # Slow!
    cog.add_cycle("check_e", "diagnosis", success=True, duration=10.0)  # Slow!

    queue = AdminTaskQueue(systems={"cognition_loop": cog})
    result = queue.force_run("capability_gap_scan")

    # Should detect inefficiency
    inefficiency_gaps = [g for g in result["gaps"] if g["type"] == "capability_inefficiency"]
    assert len(inefficiency_gaps) >= 1, f"Expected inefficiency gap, got: {result['gaps']}"
    assert result["slow_goals_found"] >= 2

    print(f"  ✓ Gap scan detects slow goals: {inefficiency_gaps}")
    return True


def test_gap_scan_detects_cold_spots():
    """Gap scan detects domain cold spots (failures with no successes)."""
    from fairies.P20_Somatic.SomaticMindFairy.admin_tasks import AdminTaskQueue

    cog = MockCognitionLoop()

    # 3 failures in communication, 0 successes
    for i in range(3):
        cog.add_cycle("send_message", "communication", success=False)
    # Successes in other domains
    cog.add_cycle("reflect", "introspection", success=True)

    queue = AdminTaskQueue(systems={"cognition_loop": cog})
    result = queue.force_run("capability_gap_scan")

    cold_spots = [g for g in result["gaps"] if g["type"] == "domain_cold_spot"]
    assert len(cold_spots) >= 1, f"Expected cold spot gap, got: {result['gaps']}"
    cold_domains = [g["domain"] for g in cold_spots]
    assert "communication" in cold_domains

    print(f"  ✓ Gap scan detects cold spots: {cold_spots}")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CardinalMixin failure pattern tracking
# ═══════════════════════════════════════════════════════════════════════════

def test_cardinal_mixin_imports():
    """CardinalMixin imports without error."""
    from fairies.P20_Somatic.SomaticMindFairy.mixins.cardinal import CardinalMixin
    print("  ✓ CardinalMixin imported")
    return True


def test_cardinal_pattern_tracking():
    """CardinalMixin tracks failure patterns from gap data."""
    from fairies.P20_Somatic.SomaticMindFairy.mixins.cardinal import CardinalMixin

    # Create a minimal class that uses the mixin
    class TestCardinal(CardinalMixin):
        ACTOR_NAME = "TestCardinal"
        post = MockPostal()

    tc = TestCardinal()
    tc._cardinal_init()

    # Simulate gap data arriving
    gap_data = {
        "gaps": [
            {"type": "repeated_failure", "domain": "diagnosis", "top_goal": "check_health",
             "failure_count": 5, "severity": 0.5},
            {"type": "capability_inefficiency", "domain": "exploration",
             "avg_duration": 3.5, "slow_count": 3, "severity": 0.6},
        ],
        "scan_stats": {"cycles_analyzed": 50, "failures": 5, "slow_goals": 3},
    }

    tc._track_failure_pattern(gap_data)

    # Check patterns were tracked
    patterns = tc.get_failure_patterns()
    assert patterns["total_domains"] == 2
    assert len(patterns["patterns"]) == 2

    # Check specific domain tracking
    diag_pattern = tc._failure_patterns.get("diagnosis")
    assert diag_pattern is not None
    assert diag_pattern["total_detections"] == 1
    assert diag_pattern["top_goal"] == "check_health"

    print(f"  ✓ Pattern tracking: {patterns}")
    return True


def test_cardinal_meta_gap_filter():
    """GW-1: Meta-gap filter triggers cooldown after too many gaps."""
    from fairies.P20_Somatic.SomaticMindFairy.mixins.cardinal import CardinalMixin

    class TestCardinal(CardinalMixin):
        ACTOR_NAME = "TestCardinal"
        post = MockPostal()

    tc = TestCardinal()
    tc._cardinal_init()

    # Send 4 gap detections rapidly (>3 in 10 min triggers cooldown)
    gap_data = {
        "gaps": [{"type": "repeated_failure", "domain": "test", "severity": 0.5}],
        "scan_stats": {"cycles_analyzed": 10},
    }

    for i in range(4):
        tc._track_failure_pattern(gap_data)

    # Should now be in cooldown
    assert time.time() < tc._gap_cooldown_until, "Expected cooldown to be active"

    # Meta-gap alert should have been published
    alerts = tc.post.get_published("cardinal.meta_gap_alert")
    assert len(alerts) >= 1, f"Expected meta_gap_alert, got: {tc.post.published}"

    # 5th gap should be suppressed (in cooldown)
    pre_count = tc._failure_patterns.get("test", {}).get("total_detections", 0)
    tc._track_failure_pattern(gap_data)
    post_count = tc._failure_patterns.get("test", {}).get("total_detections", 0)
    assert post_count == pre_count, "Gap should have been suppressed during cooldown"

    print(f"  ✓ Meta-gap filter: cooldown active, gaps suppressed")
    return True


def test_cardinal_status_includes_patterns():
    """get_cardinal_status() includes Sprint 1 fields."""
    from fairies.P20_Somatic.SomaticMindFairy.mixins.cardinal import CardinalMixin

    class TestCardinal(CardinalMixin):
        ACTOR_NAME = "TestCardinal"
        post = None

    tc = TestCardinal()
    tc._cardinal_init()

    status = tc.get_cardinal_status()
    assert "failure_patterns_tracked" in status
    assert "gap_cooldown_active" in status
    assert "top_failure_domains" in status
    assert status["failure_patterns_tracked"] == 0
    assert status["gap_cooldown_active"] is False

    print(f"  ✓ Cardinal status includes Sprint 1 fields: {list(status.keys())}")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ═══════════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        ("AdminTaskQueue imports", test_admin_task_queue_imports),
        ("AdminTaskQueue creation", test_admin_queue_creation),
        ("Tracer cleanup wired", test_tracer_cleanup_wired),
        ("Dead letter scan (unwired)", test_dead_letter_scan_wired),
        ("Learning calibration wired", test_learning_calibration_wired),
        ("Ace presence check", test_ace_presence_check),
        ("Gap scan empty history", test_gap_scan_empty_history),
        ("Gap scan: repeated failures", test_gap_scan_detects_repeated_failures),
        ("Gap scan: slow goals", test_gap_scan_detects_slow_goals),
        ("Gap scan: cold spots", test_gap_scan_detects_cold_spots),
        ("CardinalMixin imports", test_cardinal_mixin_imports),
        ("Cardinal pattern tracking", test_cardinal_pattern_tracking),
        ("Cardinal meta-gap filter (GW-1)", test_cardinal_meta_gap_filter),
        ("Cardinal status includes patterns", test_cardinal_status_includes_patterns),
    ]

    passed = 0
    failed = 0

    print("=" * 70)
    print("Cardinal Sprint 1 Tests")
    print("=" * 70)

    for name, test_fn in tests:
        try:
            print(f"\n[TEST] {name}")
            result = test_fn()
            if result:
                passed += 1
            else:
                failed += 1
                print(f"  ✗ FAIL: returned False")
        except Exception as e:
            failed += 1
            print(f"  ✗ FAIL: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
