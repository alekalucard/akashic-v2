"""
Memory Pressure Fairy - Real-time Python memory monitoring.

Tracks:
- Process RSS (Resident Set Size) - actual RAM used
- Python object counts by type
- Garbage collection stats
- Memory trends over time

Useful for detecting memory leaks in long-running processes like the MCP server.
"""

import gc
import sys
import time
import threading
from collections import defaultdict
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

# Try to get psutil for process-level stats
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class MemorySample:
    """A single memory measurement."""
    timestamp: float
    rss_mb: float  # Resident Set Size in MB
    vms_mb: float  # Virtual Memory Size in MB
    gc_counts: tuple  # (gen0, gen1, gen2) collection counts
    object_count: int  # Total tracked objects
    top_types: Dict[str, int] = field(default_factory=dict)  # Top object types by count


class MemoryPressureFairy:
    """
    Monitors Python memory usage and detects leaks.

    Usage:
        fairy = get_memory_pressure_fairy()
        fairy.start_monitoring(interval=30)  # Sample every 30 seconds

        # Later...
        status = fairy.get_status()
        trend = fairy.get_trend()
    """

    def __init__(self, max_samples: int = 100):
        self.max_samples = max_samples
        self.samples: List[MemorySample] = []
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._interval = 60  # Default: sample every minute
        self._process = psutil.Process() if HAS_PSUTIL else None

        # Baseline for detecting leaks
        self._baseline_rss: Optional[float] = None
        self._baseline_objects: Optional[int] = None

        # Alert thresholds
        self.alert_rss_growth_mb = 500  # Alert if RSS grows by this much
        self.alert_object_growth_pct = 50  # Alert if objects grow by this %

    def take_sample(self) -> MemorySample:
        """Take a memory sample right now."""
        # Get process memory if available
        if self._process:
            try:
                mem_info = self._process.memory_info()
                rss_mb = mem_info.rss / (1024 * 1024)
                vms_mb = mem_info.vms / (1024 * 1024)
            except:
                rss_mb = 0.0
                vms_mb = 0.0
        else:
            rss_mb = 0.0
            vms_mb = 0.0

        # Get GC stats
        gc_counts = gc.get_count()

        # Count objects by type (expensive, so just get top types)
        type_counts = defaultdict(int)
        for obj in gc.get_objects():
            type_counts[type(obj).__name__] += 1

        # Get top 10 types
        top_types = dict(sorted(type_counts.items(), key=lambda x: -x[1])[:10])
        object_count = sum(type_counts.values())

        sample = MemorySample(
            timestamp=time.time(),
            rss_mb=rss_mb,
            vms_mb=vms_mb,
            gc_counts=gc_counts,
            object_count=object_count,
            top_types=top_types,
        )

        with self._lock:
            self.samples.append(sample)

            # Set baseline on first sample
            if self._baseline_rss is None:
                self._baseline_rss = rss_mb
                self._baseline_objects = object_count

            # Trim old samples
            while len(self.samples) > self.max_samples:
                self.samples.pop(0)

        return sample

    def get_status(self) -> Dict[str, Any]:
        """Get current memory status."""
        # Force a fresh sample
        sample = self.take_sample()

        # Calculate pressure level
        if self._baseline_rss and self._baseline_rss > 0:
            growth_mb = sample.rss_mb - self._baseline_rss
            growth_pct = (growth_mb / self._baseline_rss) * 100
        else:
            growth_mb = 0
            growth_pct = 0

        # Determine pressure level
        if growth_mb > self.alert_rss_growth_mb:
            pressure_level = "HIGH"
        elif growth_mb > self.alert_rss_growth_mb / 2:
            pressure_level = "MEDIUM"
        else:
            pressure_level = "LOW"

        return {
            "status": "active" if self._monitoring else "idle",
            "pressure_level": pressure_level,
            "current_rss_mb": round(sample.rss_mb, 2),
            "current_vms_mb": round(sample.vms_mb, 2),
            "baseline_rss_mb": round(self._baseline_rss or 0, 2),
            "growth_mb": round(growth_mb, 2),
            "growth_pct": round(growth_pct, 2),
            "object_count": sample.object_count,
            "gc_counts": sample.gc_counts,
            "top_types": sample.top_types,
            "samples_collected": len(self.samples),
            "has_psutil": HAS_PSUTIL,
        }

    def get_trend(self, minutes: int = 10) -> Dict[str, Any]:
        """Get memory trend over the last N minutes."""
        cutoff = time.time() - (minutes * 60)

        with self._lock:
            recent = [s for s in self.samples if s.timestamp > cutoff]

        if len(recent) < 2:
            return {
                "trend": "UNKNOWN",
                "message": f"Not enough samples (need 2+, have {len(recent)})",
                "samples": len(recent),
            }

        # Calculate linear trend
        first_rss = recent[0].rss_mb
        last_rss = recent[-1].rss_mb
        rss_change = last_rss - first_rss
        time_span = recent[-1].timestamp - recent[0].timestamp

        # MB per minute
        if time_span > 0:
            rate_per_min = (rss_change / time_span) * 60
        else:
            rate_per_min = 0

        # Determine trend
        if rate_per_min > 10:
            trend = "GROWING_FAST"
        elif rate_per_min > 1:
            trend = "GROWING"
        elif rate_per_min < -1:
            trend = "SHRINKING"
        else:
            trend = "STABLE"

        return {
            "trend": trend,
            "rate_mb_per_min": round(rate_per_min, 3),
            "start_rss_mb": round(first_rss, 2),
            "end_rss_mb": round(last_rss, 2),
            "change_mb": round(rss_change, 2),
            "time_span_min": round(time_span / 60, 1),
            "samples": len(recent),
        }

    def force_gc(self) -> Dict[str, Any]:
        """Force garbage collection and return stats."""
        before = self.take_sample()

        # Run full collection
        collected = gc.collect()

        after = self.take_sample()

        return {
            "collected_objects": collected,
            "rss_before_mb": round(before.rss_mb, 2),
            "rss_after_mb": round(after.rss_mb, 2),
            "freed_mb": round(before.rss_mb - after.rss_mb, 2),
            "objects_before": before.object_count,
            "objects_after": after.object_count,
        }

    def start_monitoring(self, interval: int = 60):
        """Start background monitoring thread."""
        if self._monitoring:
            return {"status": "already_monitoring"}

        self._interval = interval
        self._monitoring = True

        def monitor_loop():
            while self._monitoring:
                try:
                    self.take_sample()
                except Exception as e:
                    print(f"[MemoryPressure] Sample error: {e}")
                time.sleep(self._interval)

        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()

        return {"status": "started", "interval": interval}

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
        return {"status": "stopped"}

    def reset_baseline(self):
        """Reset the baseline to current values."""
        sample = self.take_sample()
        self._baseline_rss = sample.rss_mb
        self._baseline_objects = sample.object_count
        return {
            "new_baseline_rss_mb": round(self._baseline_rss, 2),
            "new_baseline_objects": self._baseline_objects,
        }

    def get_leak_suspects(self) -> Dict[str, Any]:
        """
        Analyze object growth to identify potential leak suspects.
        Compares first and last samples' top types.
        """
        with self._lock:
            if len(self.samples) < 2:
                return {"error": "Need at least 2 samples"}

            first = self.samples[0]
            last = self.samples[-1]

        # Compare type counts
        suspects = []
        for type_name, current_count in last.top_types.items():
            original_count = first.top_types.get(type_name, 0)
            if original_count > 0:
                growth = current_count - original_count
                growth_pct = (growth / original_count) * 100
                if growth > 100 and growth_pct > 20:  # Significant growth
                    suspects.append({
                        "type": type_name,
                        "original_count": original_count,
                        "current_count": current_count,
                        "growth": growth,
                        "growth_pct": round(growth_pct, 1),
                    })

        # Sort by growth
        suspects.sort(key=lambda x: -x["growth"])

        return {
            "time_span_sec": round(last.timestamp - first.timestamp, 1),
            "total_object_growth": last.object_count - first.object_count,
            "suspects": suspects[:10],  # Top 10
        }


# Global instance
_fairy: Optional[MemoryPressureFairy] = None


def get_memory_pressure_fairy() -> MemoryPressureFairy:
    """Get the global memory pressure fairy instance."""
    global _fairy
    if _fairy is None:
        _fairy = MemoryPressureFairy()
    return _fairy


def start_memory_pressure_monitor(interval: int = 60) -> Dict[str, Any]:
    """Convenience function to start monitoring."""
    return get_memory_pressure_fairy().start_monitoring(interval)


def stop_memory_pressure_monitor() -> Dict[str, Any]:
    """Convenience function to stop monitoring."""
    return get_memory_pressure_fairy().stop_monitoring()
