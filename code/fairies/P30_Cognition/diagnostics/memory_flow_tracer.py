"""
Memory Flow Tracer - Verify Dual CoT Wiring
============================================

This diagnostic traces packets through the memory system to verify:
1. Recording stream is feeding collision chamber
2. Recall stream is feeding collision chamber
3. Concurrent recording + recall produces collision
4. UnconsciousMindFairy can see all planes

Usage:
    from fairies.P30_Cognition.diagnostics.memory_flow_tracer import MemoryFlowTracer
    tracer = MemoryFlowTracer()
    results = tracer.run_all_tests()
    tracer.print_report(results)
"""

import time
import threading
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# Get postal system
try:
    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
    _HAS_POSTAL = True
except ImportError:
    _HAS_POSTAL = False


@dataclass
class FlowEvent:
    """A single event in the flow trace."""
    topic: str
    payload: Dict
    timestamp: float
    source: str = "unknown"


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    events: List[FlowEvent] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    duration_sec: float = 0.0


class MemoryFlowTracer:
    """
    Traces packet flow through the memory system.

    Subscribes to all relevant topics and logs what arrives.
    Then sends test packets and verifies the expected flow.
    """

    # Topics to monitor for flow tracing
    TRACE_TOPICS = [
        # Recording path
        "srm.ingest.packet",
        "srm.ingest.result",
        "consciousness.to_ingest",

        # Recall path
        "srm.recall.request",
        "srm.recall.result",
        "memory.recall.request",
        "memory.recall.result",
        "consciousness.to_recall",

        # Collision path
        "consciousness.collision",
        "consciousness.stream",
        "consciousness.working_stream",
        "consciousness.reflective_stream",

        # Working memory path
        "memory.working.tracer",
        "working_memory.tracer_added",
        "working_memory.context",

        # Affect path (triggers recall)
        "affect.changed",
        "affect.state",

        # All-plane visibility
        "fairy.status",
        "fairy.boot",
        "fairy.health",
    ]

    def __init__(self):
        self.post = None
        self.events: List[FlowEvent] = []
        self.events_lock = threading.Lock()
        self._subscribed = False

    def _ensure_postal(self) -> bool:
        """Get postal hub connection."""
        if self.post:
            return True
        if not _HAS_POSTAL:
            print("[MemoryFlowTracer] No postal system available")
            return False
        try:
            self.post = get_shared_postal_hub()
            return True
        except Exception as e:
            print(f"[MemoryFlowTracer] Could not get postal: {e}")
            return False

    def _on_event(self, topic: str, packet: Dict):
        """Record an event."""
        with self.events_lock:
            self.events.append(FlowEvent(
                topic=topic,
                payload=packet,
                timestamp=time.time(),
                source=packet.get("source", packet.get("fairy", "unknown"))
            ))

    def subscribe_all(self):
        """Subscribe to all trace topics."""
        if not self._ensure_postal():
            return False

        for topic in self.TRACE_TOPICS:
            try:
                self.post.subscribe(topic, lambda p, t=topic: self._on_event(t, p))
            except Exception as e:
                print(f"[MemoryFlowTracer] Could not subscribe to {topic}: {e}")

        self._subscribed = True
        print(f"[MemoryFlowTracer] Subscribed to {len(self.TRACE_TOPICS)} topics")
        return True

    def clear_events(self):
        """Clear recorded events."""
        with self.events_lock:
            self.events.clear()

    def get_events_since(self, start_time: float) -> List[FlowEvent]:
        """Get events since a timestamp."""
        with self.events_lock:
            return [e for e in self.events if e.timestamp >= start_time]

    def get_events_by_topic(self, topic: str, since: float = 0) -> List[FlowEvent]:
        """Get events for a specific topic."""
        with self.events_lock:
            return [e for e in self.events
                    if e.topic == topic and e.timestamp >= since]

    # =========================================================================
    # TEST CASES
    # =========================================================================

    def test_recording_path(self) -> TestResult:
        """
        Test: Recording stream feeds collision chamber.

        Send a packet to srm.ingest.packet and verify it appears in
        consciousness.working_stream or consciousness.stream.
        """
        result = TestResult(name="Recording Path", passed=False)

        if not self._ensure_postal():
            result.notes.append("No postal connection")
            return result

        start = time.time()
        test_content = f"TEST_RECORDING_{int(start)}"

        # Send test packet
        self.post.route("srm.ingest.packet", {
            "content": test_content,
            "source": "MemoryFlowTracer",
            "test_marker": "recording_path_test",
            "ts": start
        })

        # Wait for propagation
        time.sleep(1.0)

        # Check if it arrived at collision-related topics
        events = self.get_events_since(start)
        result.events = events
        result.duration_sec = time.time() - start

        # Look for our content in consciousness streams
        found_in_stream = False
        for e in events:
            if "consciousness" in e.topic:
                payload_str = json.dumps(e.payload)
                if test_content in payload_str or "recording_path_test" in payload_str:
                    found_in_stream = True
                    result.notes.append(f"Found in {e.topic}")
                    break

        if found_in_stream:
            result.passed = True
            result.notes.append("Recording successfully reached consciousness stream")
        else:
            result.notes.append("Recording did NOT reach consciousness stream")
            result.notes.append(f"Events seen: {[e.topic for e in events]}")

        return result

    def test_recall_path(self) -> TestResult:
        """
        Test: Recall request produces results that reach collision chamber.

        Send a recall request and verify srm.recall.result is produced
        and fed to consciousness.
        """
        result = TestResult(name="Recall Path", passed=False)

        if not self._ensure_postal():
            result.notes.append("No postal connection")
            return result

        start = time.time()

        # Send recall request
        self.post.route("srm.recall.request", {
            "query": "test consciousness memory",
            "source": "MemoryFlowTracer",
            "context": "recall_path_test",
            "ts": start
        })

        # Wait for propagation
        time.sleep(1.5)

        events = self.get_events_since(start)
        result.events = events
        result.duration_sec = time.time() - start

        # Check for recall result
        recall_results = [e for e in events if "recall.result" in e.topic]
        consciousness_events = [e for e in events if "consciousness" in e.topic]

        if recall_results:
            result.notes.append(f"Got {len(recall_results)} recall results")
            if consciousness_events:
                result.passed = True
                result.notes.append(f"Recall reached consciousness ({len(consciousness_events)} events)")
            else:
                result.notes.append("Recall result NOT reaching consciousness")
        else:
            result.notes.append("No recall results produced")
            result.notes.append(f"Events seen: {[e.topic for e in events]}")

        return result

    def test_concurrent_collision(self) -> TestResult:
        """
        Test: Concurrent recording + recall produces collision.

        Send both recording and recall at the same time and verify
        a consciousness.collision event is produced.
        """
        result = TestResult(name="Concurrent Collision", passed=False)

        if not self._ensure_postal():
            result.notes.append("No postal connection")
            return result

        start = time.time()
        test_id = f"collision_test_{int(start)}"

        def send_recording():
            self.post.route("srm.ingest.packet", {
                "content": f"New event for collision test {test_id}",
                "source": "MemoryFlowTracer",
                "test_marker": test_id,
                "ts": time.time()
            })

        def send_recall():
            self.post.route("srm.recall.request", {
                "query": "collision test event",
                "source": "MemoryFlowTracer",
                "context": test_id,
                "ts": time.time()
            })

        # Fire concurrently
        t1 = threading.Thread(target=send_recording)
        t2 = threading.Thread(target=send_recall)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Wait for collision to happen
        time.sleep(2.0)

        events = self.get_events_since(start)
        result.events = events
        result.duration_sec = time.time() - start

        # Check for collision event
        collisions = [e for e in events if "collision" in e.topic.lower()]

        if collisions:
            result.passed = True
            result.notes.append(f"Collision detected! {len(collisions)} events")
            for c in collisions[:3]:
                result.notes.append(f"  - {c.topic}: {str(c.payload)[:100]}")
        else:
            result.notes.append("No collision detected from concurrent streams")

            # Diagnose what DID happen
            recording_events = [e for e in events if "ingest" in e.topic]
            recall_events = [e for e in events if "recall" in e.topic]
            result.notes.append(f"Recording events: {len(recording_events)}")
            result.notes.append(f"Recall events: {len(recall_events)}")

        return result

    def test_umf_plane_visibility(self) -> TestResult:
        """
        Test: UnconsciousMindFairy can see all planes.

        Check what fairy.status/boot/health events are visible.
        """
        result = TestResult(name="UMF All-Plane Visibility", passed=False)

        if not self._ensure_postal():
            result.notes.append("No postal connection")
            return result

        start = time.time()

        # Emit test status from each plane
        for plane in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]:
            try:
                self.post.route("fairy.status", {
                    "plane": plane,
                    "fairy": f"TestFairy_{plane}",
                    "source": "MemoryFlowTracer",
                    "test_marker": "visibility_test",
                    "ts": time.time()
                })
            except:
                pass

        time.sleep(1.0)

        events = self.get_events_since(start)
        result.events = events
        result.duration_sec = time.time() - start

        # Check which planes were visible
        visible_planes = set()
        for e in events:
            if "fairy.status" in e.topic:
                plane = e.payload.get("plane")
                if plane:
                    visible_planes.add(plane)

        expected = {"P00", "P10", "P20", "P30", "P40", "P50", "P60"}
        missing = expected - visible_planes

        if not missing:
            result.passed = True
            result.notes.append("All planes visible!")
        else:
            result.notes.append(f"Visible planes: {sorted(visible_planes)}")
            result.notes.append(f"MISSING planes: {sorted(missing)}")

        return result

    def test_o1_lookup_speed(self) -> TestResult:
        """
        Test: Is memory recall O(1) or O(n)?

        Time multiple recall requests to see if latency is constant.
        """
        result = TestResult(name="O(1) Lookup Speed", passed=False)

        if not self._ensure_postal():
            result.notes.append("No postal connection")
            return result

        latencies = []

        for i in range(5):
            start = time.time()
            self.clear_events()

            self.post.route("srm.recall.request", {
                "query": f"test query {i}",
                "source": "MemoryFlowTracer",
                "context": "latency_test"
            })

            # Wait for result
            timeout = 2.0
            while (time.time() - start) < timeout:
                results = self.get_events_by_topic("srm.recall.result", start)
                if results:
                    latency = results[0].timestamp - start
                    latencies.append(latency)
                    break
                time.sleep(0.05)
            else:
                latencies.append(timeout)  # Timeout

        result.duration_sec = sum(latencies)

        if latencies:
            avg = sum(latencies) / len(latencies)
            variance = sum((l - avg) ** 2 for l in latencies) / len(latencies)

            result.notes.append(f"Latencies: {[f'{l:.3f}s' for l in latencies]}")
            result.notes.append(f"Average: {avg:.3f}s, Variance: {variance:.6f}")

            # O(1) should have low variance
            if variance < 0.01 and avg < 0.5:
                result.passed = True
                result.notes.append("Looks like O(1) - consistent fast lookups")
            elif variance > 0.05:
                result.notes.append("High variance suggests O(n) search, not O(1) lookup")
            else:
                result.notes.append("Borderline - may need optimization")

        return result

    # =========================================================================
    # RUN ALL TESTS
    # =========================================================================

    def run_all_tests(self) -> Dict[str, TestResult]:
        """Run all diagnostic tests."""
        print("\n" + "="*60)
        print("MEMORY FLOW TRACER - Diagnostic Suite")
        print("="*60 + "\n")

        # Ensure subscribed
        if not self._subscribed:
            self.subscribe_all()
            time.sleep(0.5)  # Let subscriptions settle

        results = {}
        tests = [
            ("recording_path", self.test_recording_path),
            ("recall_path", self.test_recall_path),
            ("concurrent_collision", self.test_concurrent_collision),
            ("umf_visibility", self.test_umf_plane_visibility),
            ("o1_lookup", self.test_o1_lookup_speed),
        ]

        for name, test_fn in tests:
            print(f"Running: {name}...")
            self.clear_events()
            try:
                results[name] = test_fn()
            except Exception as e:
                results[name] = TestResult(
                    name=name,
                    passed=False,
                    notes=[f"Exception: {e}"]
                )
            print(f"  {'PASS' if results[name].passed else 'FAIL'}")

        return results

    def print_report(self, results: Dict[str, TestResult]):
        """Print a formatted report of test results."""
        print("\n" + "="*60)
        print("MEMORY FLOW TRACER - Results")
        print("="*60 + "\n")

        passed = sum(1 for r in results.values() if r.passed)
        total = len(results)

        for name, result in results.items():
            status = "PASS" if result.passed else "FAIL"
            print(f"[{status}] {result.name}")
            print(f"    Duration: {result.duration_sec:.3f}s")
            for note in result.notes:
                print(f"    - {note}")
            print()

        print("-"*60)
        print(f"TOTAL: {passed}/{total} tests passed")

        if passed == total:
            print("\nAll memory pathways verified!")
        else:
            print("\nSome pathways need wiring attention.")


# Quick run function
def run_diagnostics():
    """Quick diagnostic run."""
    tracer = MemoryFlowTracer()
    results = tracer.run_all_tests()
    tracer.print_report(results)
    return results


if __name__ == "__main__":
    run_diagnostics()
