# ════════════════════════════════════════════════════════════════════════════════
# MEMORY LEAK TRACER - Find what's eating your RAM
# ════════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   from fairies.P00_Autonomic.utils.memory_leak_tracer import MemoryLeakTracer
#   tracer = MemoryLeakTracer()
#   tracer.start()
#   # ... run your code ...
#   tracer.snapshot("after_boot")
#   # ... more code ...
#   tracer.snapshot("after_1hr")
#   tracer.compare("after_boot", "after_1hr")
#   tracer.report()
#
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import gc
import sys
import time
import tracemalloc
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import json


class MemoryLeakTracer:
    """
    Track memory usage and identify potential leaks.

    Uses tracemalloc for allocation tracking and gc for object counts.
    """

    def __init__(self, auto_snapshot_interval: float = 300.0):
        """
        Args:
            auto_snapshot_interval: Seconds between automatic snapshots (default 5 min)
        """
        self._running = False
        self._snapshots: Dict[str, Dict] = {}
        self._object_counts: Dict[str, Dict[type, int]] = {}
        self._auto_interval = auto_snapshot_interval
        self._auto_thread: Optional[threading.Thread] = None
        self._start_time = 0
        self._lock = threading.Lock()

        # State file for persistence
        self._state_dir = Path(__file__).parent.parent.parent / "state" / "memory"
        self._state_dir.mkdir(parents=True, exist_ok=True)

    def start(self, nframes: int = 10):
        """Start memory tracking.

        Args:
            nframes: Number of stack frames to capture (more = more detail but slower)
        """
        if self._running:
            print("[MemoryTracer] Already running")
            return

        tracemalloc.start(nframes)
        self._running = True
        self._start_time = time.time()

        # Take initial snapshot
        self.snapshot("start")

        # Start auto-snapshot thread
        self._auto_thread = threading.Thread(
            target=self._auto_snapshot_loop,
            daemon=True,
            name="MemoryLeakTracer"
        )
        self._auto_thread.start()

        print(f"[MemoryTracer] Started - tracking allocations (nframes={nframes})")

    def stop(self):
        """Stop memory tracking."""
        self._running = False
        tracemalloc.stop()

        if self._auto_thread:
            self._auto_thread.join(timeout=1.0)

        print("[MemoryTracer] Stopped")

    def snapshot(self, name: str) -> Dict:
        """Take a memory snapshot.

        Args:
            name: Name for this snapshot (e.g., "after_boot", "1hr_mark")

        Returns:
            Snapshot data dict
        """
        with self._lock:
            # Get tracemalloc snapshot
            if tracemalloc.is_tracing():
                trace_snap = tracemalloc.take_snapshot()
                top_stats = trace_snap.statistics('lineno')[:50]
            else:
                trace_snap = None
                top_stats = []

            # Get object counts by type
            gc.collect()
            obj_counts = defaultdict(int)
            for obj in gc.get_objects():
                obj_counts[type(obj).__name__] += 1

            # Get total memory
            current, peak = tracemalloc.get_traced_memory() if tracemalloc.is_tracing() else (0, 0)

            snapshot_data = {
                "name": name,
                "timestamp": time.time(),
                "elapsed_since_start": time.time() - self._start_time if self._start_time else 0,
                "current_memory_mb": current / 1024 / 1024,
                "peak_memory_mb": peak / 1024 / 1024,
                "object_counts": dict(obj_counts),
                "top_allocations": [
                    {
                        "file": str(stat.traceback),
                        "size_kb": stat.size / 1024,
                        "count": stat.count,
                    }
                    for stat in top_stats[:20]
                ],
            }

            self._snapshots[name] = snapshot_data
            self._object_counts[name] = obj_counts

            # Save to state file
            self._save_snapshot(name, snapshot_data)

            print(f"[MemoryTracer] Snapshot '{name}': {snapshot_data['current_memory_mb']:.1f}MB current, {snapshot_data['peak_memory_mb']:.1f}MB peak")

            return snapshot_data

    def compare(self, before: str, after: str) -> Dict:
        """Compare two snapshots to find memory growth.

        Args:
            before: Name of earlier snapshot
            after: Name of later snapshot

        Returns:
            Comparison data showing growth
        """
        if before not in self._snapshots or after not in self._snapshots:
            return {"error": f"Snapshot not found: {before} or {after}"}

        before_data = self._snapshots[before]
        after_data = self._snapshots[after]
        before_counts = self._object_counts.get(before, {})
        after_counts = self._object_counts.get(after, {})

        # Calculate memory growth
        memory_growth_mb = after_data["current_memory_mb"] - before_data["current_memory_mb"]
        time_elapsed = after_data["timestamp"] - before_data["timestamp"]

        # Find object count growth
        type_growth = {}
        all_types = set(before_counts.keys()) | set(after_counts.keys())
        for t in all_types:
            before_count = before_counts.get(t, 0)
            after_count = after_counts.get(t, 0)
            delta = after_count - before_count
            if abs(delta) > 10:  # Only report significant changes
                type_growth[t] = {
                    "before": before_count,
                    "after": after_count,
                    "delta": delta,
                    "percent_change": (delta / before_count * 100) if before_count > 0 else float('inf'),
                }

        # Sort by growth
        sorted_growth = sorted(
            type_growth.items(),
            key=lambda x: abs(x[1]["delta"]),
            reverse=True
        )[:20]

        comparison = {
            "before": before,
            "after": after,
            "time_elapsed_seconds": time_elapsed,
            "memory_before_mb": before_data["current_memory_mb"],
            "memory_after_mb": after_data["current_memory_mb"],
            "memory_growth_mb": memory_growth_mb,
            "memory_growth_rate_mb_per_hour": (memory_growth_mb / time_elapsed * 3600) if time_elapsed > 0 else 0,
            "top_growing_types": dict(sorted_growth),
        }

        # Print summary
        print(f"\n[MemoryTracer] ═══ COMPARISON: {before} → {after} ═══")
        print(f"  Time elapsed: {time_elapsed:.0f}s ({time_elapsed/60:.1f}min)")
        print(f"  Memory growth: {memory_growth_mb:.1f}MB")
        print(f"  Growth rate: {comparison['memory_growth_rate_mb_per_hour']:.1f}MB/hour")
        print(f"  Top growing types:")
        for t, data in list(sorted_growth)[:10]:
            print(f"    {t}: {data['before']} → {data['after']} ({data['delta']:+d})")

        return comparison

    def report(self) -> Dict:
        """Generate comprehensive memory report."""
        if not self._snapshots:
            return {"error": "No snapshots taken yet"}

        # Get current state
        current = self.snapshot("report_now")

        # Compare with start if available
        comparison = None
        if "start" in self._snapshots:
            comparison = self.compare("start", "report_now")

        report = {
            "timestamp": time.time(),
            "runtime_seconds": time.time() - self._start_time if self._start_time else 0,
            "current_snapshot": current,
            "comparison_from_start": comparison,
            "all_snapshots": list(self._snapshots.keys()),
            "recommendations": self._generate_recommendations(current, comparison),
        }

        return report

    def get_top_consumers(self, n: int = 20) -> List[Dict]:
        """Get the top memory consuming allocations right now."""
        if not tracemalloc.is_tracing():
            return [{"error": "Tracing not active"}]

        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('traceback')[:n]

        consumers = []
        for stat in top_stats:
            consumers.append({
                "size_mb": stat.size / 1024 / 1024,
                "count": stat.count,
                "traceback": [str(line) for line in stat.traceback.format()[:5]],
            })

        return consumers

    def _auto_snapshot_loop(self):
        """Background thread for automatic snapshots."""
        snapshot_num = 0
        while self._running:
            time.sleep(self._auto_interval)
            if not self._running:
                break

            snapshot_num += 1
            elapsed_min = (time.time() - self._start_time) / 60
            self.snapshot(f"auto_{snapshot_num}_{elapsed_min:.0f}min")

    def _save_snapshot(self, name: str, data: Dict):
        """Save snapshot to state file."""
        try:
            # Save individual snapshot
            snapshot_file = self._state_dir / f"snapshot_{name.replace('/', '_')}.json"
            with open(snapshot_file, 'w') as f:
                # Convert non-serializable data
                serializable = {k: v for k, v in data.items() if k != "object_counts"}
                serializable["object_counts_sample"] = dict(list(data["object_counts"].items())[:50])
                json.dump(serializable, f, indent=2, default=str)

            # Update summary file
            summary_file = self._state_dir / "memory_summary.json"
            summary = {}
            if summary_file.exists():
                try:
                    with open(summary_file) as f:
                        summary = json.load(f)
                except:
                    pass

            summary[name] = {
                "timestamp": data["timestamp"],
                "current_mb": data["current_memory_mb"],
                "peak_mb": data["peak_memory_mb"],
            }

            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)

        except Exception as e:
            print(f"[MemoryTracer] Failed to save snapshot: {e}")

    def _generate_recommendations(self, current: Dict, comparison: Optional[Dict]) -> List[str]:
        """Generate recommendations based on analysis."""
        recs = []

        if comparison:
            growth_rate = comparison.get("memory_growth_rate_mb_per_hour", 0)
            if growth_rate > 100:
                recs.append(f"CRITICAL: Memory growing at {growth_rate:.0f}MB/hour - severe leak detected")
            elif growth_rate > 50:
                recs.append(f"WARNING: Memory growing at {growth_rate:.0f}MB/hour - likely leak")
            elif growth_rate > 20:
                recs.append(f"NOTICE: Memory growing at {growth_rate:.0f}MB/hour - monitor closely")

            # Check for specific type growth
            for type_name, data in comparison.get("top_growing_types", {}).items():
                if data["delta"] > 10000:
                    recs.append(f"Type '{type_name}' grew by {data['delta']} objects - investigate source")

        # Check common leak patterns
        counts = current.get("object_counts", {})
        if counts.get("dict", 0) > 100000:
            recs.append("High dict count - check for unbounded caches or accumulators")
        if counts.get("list", 0) > 50000:
            recs.append("High list count - check for growing buffers without cleanup")
        if counts.get("function", 0) > 10000:
            recs.append("High function count - possible closure leaks")
        if counts.get("frame", 0) > 1000:
            recs.append("High frame count - possible thread/generator leaks")

        return recs


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON & CONVENIENCE FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

_tracer_instance: Optional[MemoryLeakTracer] = None


def get_memory_tracer() -> MemoryLeakTracer:
    """Get or create the memory tracer singleton."""
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = MemoryLeakTracer()
    return _tracer_instance


def start_memory_tracing(nframes: int = 10) -> MemoryLeakTracer:
    """Start memory tracing (convenience function)."""
    tracer = get_memory_tracer()
    tracer.start(nframes)
    return tracer


def memory_snapshot(name: str) -> Dict:
    """Take a memory snapshot (convenience function)."""
    return get_memory_tracer().snapshot(name)


def memory_report() -> Dict:
    """Generate memory report (convenience function)."""
    return get_memory_tracer().report()


# ════════════════════════════════════════════════════════════════════════════════
# MCP TOOL REGISTRATION
# ════════════════════════════════════════════════════════════════════════════════

def register_mcp_tools(mcp):
    """Register memory tracing MCP tools."""

    @mcp.tool()
    def start_memory_monitor(nframes: int = 10) -> str:
        """Start monitoring memory usage for leak detection.

        Args:
            nframes: Stack frames to capture (more = more detail, slower)

        Call memory_snapshot periodically to track growth.
        """
        tracer = start_memory_tracing(nframes)
        return f"Memory monitoring started. Use memory_snapshot('name') to capture state."

    @mcp.tool()
    def stop_memory_monitor() -> str:
        """Stop memory monitoring."""
        tracer = get_memory_tracer()
        tracer.stop()
        return "Memory monitoring stopped."

    @mcp.tool()
    def get_memory_pressure() -> str:
        """Get current memory pressure and potential leaks.

        Returns detailed report of memory usage and growth patterns.
        """
        tracer = get_memory_tracer()
        report = tracer.report()

        # Format for display
        lines = [
            "═══ MEMORY PRESSURE REPORT ═══",
            f"Runtime: {report.get('runtime_seconds', 0)/60:.1f} minutes",
        ]

        current = report.get("current_snapshot", {})
        lines.append(f"Current: {current.get('current_memory_mb', 0):.1f}MB")
        lines.append(f"Peak: {current.get('peak_memory_mb', 0):.1f}MB")

        comparison = report.get("comparison_from_start")
        if comparison:
            lines.append(f"Growth: {comparison.get('memory_growth_mb', 0):.1f}MB")
            lines.append(f"Rate: {comparison.get('memory_growth_rate_mb_per_hour', 0):.1f}MB/hour")

            lines.append("\nTop growing types:")
            for t, data in list(comparison.get("top_growing_types", {}).items())[:10]:
                lines.append(f"  {t}: {data['before']} → {data['after']} ({data['delta']:+d})")

        lines.append("\nRecommendations:")
        for rec in report.get("recommendations", ["None"]):
            lines.append(f"  • {rec}")

        return "\n".join(lines)

    @mcp.tool()
    def force_garbage_collection() -> str:
        """Force Python garbage collection to free unreferenced memory."""
        import gc
        before = len(gc.get_objects())
        gc.collect()
        gc.collect()
        gc.collect()
        after = len(gc.get_objects())
        freed = before - after

        return f"Garbage collection complete. Objects: {before} → {after} (freed {freed})"

    print("[MemoryTracer] MCP tools registered")


# ════════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Memory Leak Tracer Test ===\n")

    tracer = MemoryLeakTracer(auto_snapshot_interval=10)
    tracer.start()

    print("\nCreating some objects...")
    leak = []
    for i in range(1000):
        leak.append({"data": "x" * 1000, "index": i})

    tracer.snapshot("after_allocation")

    print("\nMore allocation...")
    for i in range(1000):
        leak.append({"data": "y" * 1000, "index": i})

    tracer.snapshot("after_more")

    print("\nComparison:")
    tracer.compare("after_allocation", "after_more")

    print("\nTop consumers:")
    for consumer in tracer.get_top_consumers(5):
        print(f"  {consumer['size_mb']:.2f}MB - {consumer['count']} allocations")

    print("\nFull report:")
    report = tracer.report()
    print(f"  Recommendations: {report.get('recommendations', [])}")

    tracer.stop()
    print("\nDone!")
