"""
Worker Pool MCP Tools
=====================

MCP tools for accessing the SystemWorkerPoolFairy and tracer diagnostics.
Provides equilibrium-based worker allocation across the system.

Tools:
  worker_pool_status      - Get current pool status and allocations
  worker_pool_config      - Get pool configuration
  tracer_diagnostic       - Diagnose which fairies are processing tracers
  tracer_activity_summary - Quick summary of fairy activity

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > inf)
"""

from typing import Dict, Any, List
from collections import defaultdict
import time


def get_worker_pool():
    """Get the system worker pool singleton."""
    try:
        from P00_Autonomic.nervous_system.hardware.system_worker_pool_fairy import get_system_pool
        return get_system_pool()
    except ImportError:
        return None


def tool_worker_pool_status() -> Dict[str, Any]:
    """
    Get current worker pool status.
    
    Returns pool sizes, fairy allocations, and stats.
    """
    pool = get_worker_pool()
    if pool is None:
        return {"error": "Worker pool not available"}
    
    try:
        return pool.get_status()
    except Exception as e:
        return {"error": str(e)}


def tool_worker_pool_config() -> Dict[str, Any]:
    """
    Get worker pool configuration.
    
    Shows IO pool size, compute pool size, and equilibrium settings.
    """
    pool = get_worker_pool()
    if pool is None:
        return {"error": "Worker pool not available"}
    
    try:
        config = pool.config
        return {
            "io_pool_base": config.io_pool_base,
            "io_pool_max": config.io_pool_max,
            "compute_pool_max": config.compute_pool_max,
            "rebalance_interval_sec": config.rebalance_interval_sec,
            "idle_reclaim_after_sec": config.idle_reclaim_after_sec,
            "min_allocation": config.min_allocation,
            "max_allocation_percent": config.max_allocation_percent,
        }
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# TRACER DIAGNOSTIC TOOLS
# "Who is actually working and who is sitting idle?"
# ══════════════════════════════════════════════════════════════════════════════

def get_tracer_registry():
    """Get the Python TracerRegistry singleton."""
    try:
        from fairies.P00_Autonomic.tracer_worker_system import get_tracer_registry
        return get_tracer_registry()
    except ImportError:
        try:
            from fairies.P00_Autonomic.tracer_worker_system import get_tracer_registry
            return get_tracer_registry()
        except ImportError:
            return None


def get_go_tracer_pool():
    """Get the Go TracerPool if available."""
    try:
        from tracer_pool.tracer_pool import TracerPool, USING_GO
        if USING_GO:
            return TracerPool.global_instance()
    except (ImportError, RuntimeError):
        pass
    return None


def tool_tracer_diagnostic() -> Dict[str, Any]:
    """
    Comprehensive tracer diagnostic - shows which fairies are processing work.

    Returns:
        Dict with:
        - fairy_activity: Dict mapping fairy names to their tracer stats
        - registry_stats: Overall registry statistics
        - working_fairies: List of fairies with active (running) tracers
        - idle_fairies: List of fairies with no recent activity
        - go_pool_available: Whether Go DLL is active
    """
    result = {
        "timestamp": time.time(),
        "fairy_activity": {},
        "registry_stats": {},
        "working_fairies": [],
        "idle_fairies": [],
        "recently_completed": [],
        "go_pool_available": False,
        "errors": [],
    }

    # Query Python TracerRegistry
    registry = get_tracer_registry()
    if registry:
        try:
            # Get overall stats
            result["registry_stats"] = registry.get_stats()

            # Analyze each fairy
            fairy_activity = {}
            now = time.time()

            for fairy_id, tracer_ids in registry._by_fairy.items():
                stats = {
                    "total_tracers": len(tracer_ids),
                    "pending": 0,
                    "running": 0,
                    "completed": 0,
                    "failed": 0,
                    "recent_activity": False,  # Activity in last 5 minutes
                    "last_completed_at": None,
                    "active_operations": [],
                }

                for tid in tracer_ids:
                    tracer = registry._tracers.get(tid)
                    if not tracer:
                        continue

                    status = tracer.status.value
                    stats[status] = stats.get(status, 0) + 1

                    # Track running operations
                    if status == "running":
                        stats["active_operations"].append({
                            "id": tracer.id[:8],
                            "operation": tracer.operation,
                            "started": tracer.started_at,
                            "progress": tracer.progress,
                        })

                    # Check for recent activity
                    completed_at = tracer.completed_at
                    if completed_at and (now - completed_at) < 300:  # 5 minutes
                        stats["recent_activity"] = True
                        if stats["last_completed_at"] is None or completed_at > stats["last_completed_at"]:
                            stats["last_completed_at"] = completed_at

                    if tracer.started_at and (now - tracer.started_at) < 300:
                        stats["recent_activity"] = True

                # Get fairy name from first tracer
                fairy_name = fairy_id
                for tid in tracer_ids:
                    tracer = registry._tracers.get(tid)
                    if tracer and tracer.fairy_name:
                        fairy_name = tracer.fairy_name
                        break

                fairy_activity[fairy_name] = stats

                # Categorize
                if stats["running"] > 0:
                    result["working_fairies"].append(fairy_name)
                elif stats["recent_activity"]:
                    result["recently_completed"].append(fairy_name)
                elif stats["total_tracers"] == 0 or (stats["completed"] + stats["failed"]) == stats["total_tracers"]:
                    if not stats["recent_activity"]:
                        result["idle_fairies"].append(fairy_name)

            result["fairy_activity"] = fairy_activity

        except Exception as e:
            result["errors"].append(f"Registry query error: {e}")
    else:
        result["errors"].append("Python TracerRegistry not available")

    # Query Go TracerPool (if available)
    go_pool = get_go_tracer_pool()
    if go_pool:
        result["go_pool_available"] = True
        try:
            result["go_registry_stats"] = go_pool.registry_stats()
            result["go_pool_stats"] = go_pool.stats()
        except Exception as e:
            result["errors"].append(f"Go pool query error: {e}")

    return result


def tool_tracer_activity_summary() -> Dict[str, Any]:
    """
    Quick summary of fairy activity - simpler than full diagnostic.

    Returns:
        Dict with:
        - total_fairies: Count of fairies with tracers
        - working: Count of fairies with running tracers
        - idle: Count of fairies with no recent activity
        - total_running_tracers: Total tracers in running state
        - total_completed_tracers: Total completed (for tracking throughput)
    """
    result = {
        "timestamp": time.time(),
        "total_fairies": 0,
        "working": 0,
        "idle": 0,
        "recently_active": 0,
        "total_running_tracers": 0,
        "total_completed_tracers": 0,
        "total_failed_tracers": 0,
        "working_fairy_names": [],
        "error": None,
    }

    registry = get_tracer_registry()
    if not registry:
        result["error"] = "TracerRegistry not available"
        return result

    try:
        now = time.time()
        result["total_fairies"] = len(registry._by_fairy)

        for fairy_id, tracer_ids in registry._by_fairy.items():
            has_running = False
            has_recent = False
            fairy_name = fairy_id

            for tid in tracer_ids:
                tracer = registry._tracers.get(tid)
                if not tracer:
                    continue

                if tracer.fairy_name:
                    fairy_name = tracer.fairy_name

                if tracer.status.value == "running":
                    has_running = True
                    result["total_running_tracers"] += 1
                elif tracer.status.value == "completed":
                    result["total_completed_tracers"] += 1
                    if tracer.completed_at and (now - tracer.completed_at) < 300:
                        has_recent = True
                elif tracer.status.value == "failed":
                    result["total_failed_tracers"] += 1

            if has_running:
                result["working"] += 1
                result["working_fairy_names"].append(fairy_name)
            elif has_recent:
                result["recently_active"] += 1
            else:
                result["idle"] += 1

    except Exception as e:
        result["error"] = str(e)

    return result


def tool_tracer_by_fairy(fairy_name: str = None) -> Dict[str, Any]:
    """
    Get detailed tracer info for a specific fairy.

    Args:
        fairy_name: Name of the fairy to query (optional - lists all if omitted)

    Returns:
        Dict with tracer details for the fairy
    """
    registry = get_tracer_registry()
    if not registry:
        return {"error": "TracerRegistry not available"}

    try:
        if fairy_name:
            # Find fairy by name
            for fid, tracer_ids in registry._by_fairy.items():
                for tid in tracer_ids:
                    tracer = registry._tracers.get(tid)
                    if tracer and tracer.fairy_name == fairy_name:
                        # Found the fairy
                        tracers_info = []
                        for tid2 in tracer_ids:
                            t = registry._tracers.get(tid2)
                            if t:
                                tracers_info.append({
                                    "id": t.id[:8],
                                    "type": t.tracer_type.value,
                                    "operation": t.operation,
                                    "status": t.status.value,
                                    "progress": t.progress,
                                    "created": t.created_at,
                                    "started": t.started_at,
                                    "completed": t.completed_at,
                                    "error": t.error if t.error else None,
                                })
                        return {
                            "fairy_name": fairy_name,
                            "fairy_id": fid,
                            "tracer_count": len(tracers_info),
                            "tracers": tracers_info,
                        }
            return {"error": f"Fairy '{fairy_name}' not found in registry"}

        else:
            # List all fairies
            fairies = []
            for fid, tracer_ids in registry._by_fairy.items():
                name = fid
                for tid in tracer_ids:
                    tracer = registry._tracers.get(tid)
                    if tracer and tracer.fairy_name:
                        name = tracer.fairy_name
                        break
                fairies.append({
                    "fairy_id": fid,
                    "fairy_name": name,
                    "tracer_count": len(tracer_ids),
                })
            return {
                "total_fairies": len(fairies),
                "fairies": sorted(fairies, key=lambda x: x["tracer_count"], reverse=True),
            }

    except Exception as e:
        return {"error": str(e)}


# Register tools
WORKER_POOL_TOOLS = {
    "worker_pool_status": tool_worker_pool_status,
    "worker_pool_config": tool_worker_pool_config,
    "tracer_diagnostic": tool_tracer_diagnostic,
    "tracer_activity_summary": tool_tracer_activity_summary,
    "tracer_by_fairy": tool_tracer_by_fairy,
}
