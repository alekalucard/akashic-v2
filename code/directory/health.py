"""
System Health - Aggregate health metrics from all sources.

Combines postal metrics, tracer stats, tensor state, and fairy health
into a unified system health view.
"""

from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from postal_core.tensor_fabric import TensorFabric
    from tracer_pool import TracerPool
    from .registry import FairyRegistry


class SystemHealth:
    """
    Aggregate system health from all sources.

    Provides a unified view of:
    - Postal system metrics (throughput, latency)
    - Tracer pool stats (tracers, fairies tracked)
    - Tensor fabric state (affect, resonance)
    - Fairy health (alive/dead counts)
    """

    def __init__(
        self,
        fabric: Optional["TensorFabric"] = None,
        pool: Optional["TracerPool"] = None,
    ):
        self.fabric = fabric
        self.pool = pool

    def postal_metrics(self) -> Dict[str, Any]:
        """Get postal system metrics."""
        if not self.fabric:
            return {"error": "no_fabric"}

        try:
            metrics = self.fabric.metrics()
            return {
                "messages_published": metrics.get("messages_published", 0),
                "throughput": metrics.get("throughput", 0),
                "p95_ms": metrics.get("p95_ms", 0),
                "p99_ms": metrics.get("p99_ms", 0),
                "queue_depth": metrics.get("queue_depth", 0),
            }
        except Exception as e:
            return {"error": str(e)}

    def tracer_stats(self) -> Dict[str, Any]:
        """Get tracer pool statistics."""
        if not self.pool:
            return {"error": "no_pool"}

        try:
            stats = self.pool.stats()
            return {
                "total_tracers": stats.get("total_tracers", 0),
                "total_fairies": stats.get("total_fairies", 0),
                "total_clusters": stats.get("total_clusters", 0),
                "using_go": stats.get("using_go", False),
            }
        except Exception as e:
            return {"error": str(e)}

    def tensor_state(self) -> Dict[str, Any]:
        """Get tensor fabric state."""
        if not self.fabric:
            return {"error": "no_fabric"}

        try:
            return {
                "time_index": self.fabric.time_index,
                "mean_affect": self.fabric.mean_affect(),
                "tensor_shape": self.fabric.shape.as_tuple(),
                "tensor_updates": self.fabric._stats.get("tensor_updates", 0),
                "resonance_checks": self.fabric._stats.get("resonance_checks", 0),
            }
        except Exception as e:
            return {"error": str(e)}

    def fairy_health(self, registry: "FairyRegistry", timeout_sec: float = 30.0) -> Dict[str, Any]:
        """Get fairy health summary."""
        try:
            stats = registry.stats()
            alive = registry.list_alive(timeout_sec)
            dead = registry.list_dead(timeout_sec)

            return {
                "total": stats.get("total_registered", 0),
                "by_status": stats.get("by_status", {}),
                "alive_count": len(alive),
                "dead_count": len(dead),
                "dead_fairies": [f.name for f in dead],
                "registrations": stats.get("registrations", 0),
                "heartbeats": stats.get("heartbeats", 0),
            }
        except Exception as e:
            return {"error": str(e)}

    def aggregate(self, registry: "FairyRegistry") -> Dict[str, Any]:
        """Get comprehensive system health."""
        return {
            "postal": self.postal_metrics(),
            "tracers": self.tracer_stats(),
            "tensor": self.tensor_state(),
            "fairies": self.fairy_health(registry),
            "overall": self._compute_overall_health(registry),
        }

    def _compute_overall_health(self, registry: "FairyRegistry") -> Dict[str, Any]:
        """Compute overall health score."""
        issues = []
        score = 100

        # Check for dead fairies
        dead = registry.list_dead()
        if dead:
            issues.append(f"{len(dead)} dead fairies")
            score -= len(dead) * 10

        # Check tensor affect (if very low or very high, might indicate issues)
        if self.fabric:
            try:
                mean_affect = self.fabric.mean_affect()
                if mean_affect > 0.9:
                    issues.append("high system affect")
                    score -= 10
            except:
                pass

        # Check postal metrics
        postal = self.postal_metrics()
        if postal.get("p95_ms", 0) > 100:
            issues.append("high postal latency")
            score -= 15

        # Clamp score
        score = max(0, min(100, score))

        status = "healthy"
        if score < 50:
            status = "critical"
        elif score < 75:
            status = "degraded"

        return {
            "score": score,
            "status": status,
            "issues": issues,
        }

    def quick_check(self, registry: "FairyRegistry") -> Dict[str, Any]:
        """Quick health check (minimal computation)."""
        dead_count = len(registry.list_dead())
        total = registry.count()

        status = "healthy"
        if dead_count > 0:
            status = "degraded" if dead_count < total // 2 else "critical"

        return {
            "status": status,
            "fairies": total,
            "dead": dead_count,
        }
