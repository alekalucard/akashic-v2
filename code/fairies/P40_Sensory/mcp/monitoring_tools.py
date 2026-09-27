"""
Akashic Monitoring MCP Tools
============================

MCP tools for monitoring the Akashic consciousness system.
These tools give Claude (and Ace) visibility into system health.

Categories:
1. Quick Health Checks - Is everything OK?
2. Resource Monitoring - RAM, CPU, workers, postal
3. Fairy Inspection - Individual fairy status
4. Consciousness Flow - Collision chamber, thought streams
5. Memory Operations - SRM, memory cards, pressure

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)

Author: ClaudeFairy + Ace
Date: 2026-01-03
"""

from typing import Dict, Any, List, Optional
import time
import json


# ════════════════════════════════════════════════════════════════════════════════
# 1. QUICK HEALTH CHECKS
# ════════════════════════════════════════════════════════════════════════════════

def tool_system_health() -> Dict[str, Any]:
    """
    Quick health check of entire system.
    Returns traffic light status: green/yellow/red for each subsystem.
    
    This is THE tool to call first when checking if things are OK.
    """
    health = {
        "overall": "green",
        "timestamp": time.time(),
        "subsystems": {}
    }
    
    # Check RAM
    try:
        import psutil
        ram = psutil.virtual_memory()
        if ram.percent > 90:
            health["subsystems"]["ram"] = {"status": "red", "detail": f"{ram.percent:.0f}% used"}
            health["overall"] = "red"
        elif ram.percent > 75:
            health["subsystems"]["ram"] = {"status": "yellow", "detail": f"{ram.percent:.0f}% used"}
            if health["overall"] == "green":
                health["overall"] = "yellow"
        else:
            health["subsystems"]["ram"] = {"status": "green", "detail": f"{ram.percent:.0f}% used"}
    except ImportError:
        health["subsystems"]["ram"] = {"status": "unknown", "detail": "psutil not available"}
    
    # Check Worker Pool
    try:
        from P00_Autonomic.nervous_system.hardware.system_worker_pool_fairy import get_system_pool
        pool = get_system_pool()
        status = pool.get_status()
        health["subsystems"]["worker_pool"] = {
            "status": "green",
            "detail": f"{status['io_pool_size']:,} IO + {status['compute_pool_size']} CPU workers"
        }
    except Exception as e:
        health["subsystems"]["worker_pool"] = {"status": "red", "detail": str(e)}
        health["overall"] = "red"
    
    # Check Postal
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        postal = get_shared_postal_hub()
        if postal:
            health["subsystems"]["postal"] = {"status": "green", "detail": "Hub active"}
        else:
            health["subsystems"]["postal"] = {"status": "yellow", "detail": "Hub not initialized"}
    except Exception as e:
        health["subsystems"]["postal"] = {"status": "red", "detail": str(e)}
    
    # Check MCP
    # FIX 2026-05-15 (Nous + Ace): MCPServerFairy v2.0 no longer manages a subprocess
    # (Claude.ai/Claude Code starts the MCP server externally). Old code accessed
    # mcp._process.pid which doesn't exist post-v2 refactor. Use mcp.get_status()
    # which returns {running, mode, tunnel_port, last_activity, message}.
    try:
        from fairies.P40_Sensory.mcp.mcp_server_fairy import get_mcp_server_fairy
        mcp = get_mcp_server_fairy()
        _mcp_st = mcp.get_status()
        if _mcp_st.get("running"):
            health["subsystems"]["mcp"] = {
                "status": "green",
                "detail": f"port {_mcp_st.get('tunnel_port', '?')} ({_mcp_st.get('mode', 'external')})"
            }
        else:
            health["subsystems"]["mcp"] = {"status": "yellow", "detail": _mcp_st.get("message", "Not running")}
    except Exception as e:
        health["subsystems"]["mcp"] = {"status": "yellow", "detail": str(e)}
    
    return health


def tool_quick_status() -> str:
    """
    One-line system status for quick checks.
    Returns something like: "[OK] RAM:27% | Workers:80K | Postal:OK | MCP:OK"
    """
    parts = []
    
    try:
        import psutil
        ram = psutil.virtual_memory()
        icon = "[OK]" if ram.percent < 75 else "[WARN]" if ram.percent < 90 else "[FAIL]"
        parts.append(f"{icon} RAM:{ram.percent:.0f}%")
    except:
        parts.append("? RAM")
    
    try:
        from P00_Autonomic.nervous_system.hardware.system_worker_pool_fairy import get_system_pool
        pool = get_system_pool()
        status = pool.get_status()
        io_k = status['io_pool_size'] // 1000
        parts.append(f"Workers:{io_k}K+{status['compute_pool_size']}")
    except:
        parts.append("? Workers")
    
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        postal = get_shared_postal_hub()
        parts.append("Postal:OK" if postal else "Postal:?")
    except:
        parts.append("Postal:?")
    
    try:
        from fairies.P40_Sensory.mcp.mcp_server_fairy import get_mcp_server_fairy
        mcp = get_mcp_server_fairy()
        parts.append("MCP:OK" if mcp.is_running() else "MCP:DOWN")
    except:
        parts.append("MCP:?")
    
    return " | ".join(parts)


# ════════════════════════════════════════════════════════════════════════════════
# 2. RESOURCE MONITORING
# ════════════════════════════════════════════════════════════════════════════════

def tool_resource_snapshot() -> Dict[str, Any]:
    """
    Detailed resource snapshot: RAM, CPU, disk, GPU.
    """
    snapshot = {"timestamp": time.time()}
    
    try:
        import psutil
        
        # RAM
        ram = psutil.virtual_memory()
        snapshot["ram"] = {
            "total_gb": round(ram.total / (1024**3), 2),
            "available_gb": round(ram.available / (1024**3), 2),
            "percent": ram.percent,
            "used_gb": round(ram.used / (1024**3), 2),
        }
        
        # CPU
        snapshot["cpu"] = {
            "percent": psutil.cpu_percent(interval=0.1),
            "cores": psutil.cpu_count(),
            "freq_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None,
        }
        
        # Disk
        disk = psutil.disk_usage('.')
        snapshot["disk"] = {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": disk.percent,
        }
        
        # Process-specific
        proc = psutil.Process()
        snapshot["process"] = {
            "memory_mb": round(proc.memory_info().rss / (1024**2), 1),
            "threads": proc.num_threads(),
            "cpu_percent": proc.cpu_percent(),
        }
        
    except ImportError:
        snapshot["error"] = "psutil not available"
    
    # GPU
    try:
        from fairies.P00_Autonomic.nervous_system.hardware.cuda_fairy import get_cuda_fairy
        cuda = get_cuda_fairy()
        if cuda and cuda.has_cuda:
            snapshot["gpu"] = cuda.get_status()
    except:
        pass
    
    return snapshot


def tool_worker_pool_detail() -> Dict[str, Any]:
    """
    Detailed worker pool status including allocations per fairy.
    """
    try:
        from P00_Autonomic.nervous_system.hardware.system_worker_pool_fairy import get_system_pool
        pool = get_system_pool()
        status = pool.get_status()
        
        # Add allocation details
        detail = {
            "pools": {
                "io": {"size": status["io_pool_size"], "type": "ThreadPool"},
                "compute": {"size": status["compute_pool_size"], "type": "ProcessPool"},
            },
            "allocations": status["allocations"],
            "stats": status["stats"],
            "config": {
                "rebalance_sec": pool.config.rebalance_interval_sec,
                "idle_reclaim_sec": pool.config.idle_reclaim_after_sec,
                "min_allocation": pool.config.min_allocation,
                "max_percent": pool.config.max_allocation_percent,
            }
        }
        return detail
    except Exception as e:
        return {"error": str(e)}


def tool_memory_pressure() -> Dict[str, Any]:
    """
    Memory pressure analysis with recommendations.
    """
    try:
        import psutil
        import gc
        
        ram = psutil.virtual_memory()
        proc = psutil.Process()
        
        # Determine pressure level
        if ram.percent > 90:
            level = "CRITICAL"
            action = "Immediate GC recommended, consider reboot"
        elif ram.percent > 80:
            level = "HIGH"
            action = "GC recommended, monitor closely"
        elif ram.percent > 70:
            level = "ELEVATED"
            action = "Normal operation, GC if needed"
        else:
            level = "NORMAL"
            action = "No action needed"
        
        return {
            "level": level,
            "system_percent": ram.percent,
            "process_mb": round(proc.memory_info().rss / (1024**2), 1),
            "gc_counts": gc.get_count(),
            "recommendation": action,
        }
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════════════════════
# 3. FAIRY INSPECTION
# ════════════════════════════════════════════════════════════════════════════════

def tool_list_active_fairies() -> Dict[str, List[str]]:
    """
    List all active fairies grouped by plane.
    """
    fairies_by_plane = {
        "P00": [], "P10": [], "P20": [], "P30": [],
        "P40": [], "P50": [], "P60": [], "unknown": []
    }
    
    try:
        import sys
        for mod_name, mod in list(sys.modules.items()):
            if mod and hasattr(mod, '__file__') and mod.__file__:
                if 'ebook' in str(mod.__file__):
                    for attr in dir(mod):
                        if attr.endswith('Fairy') and not attr.startswith('_'):
                            try:
                                cls = getattr(mod, attr)
                                if isinstance(cls, type) and hasattr(cls, 'ACTOR_NAME'):
                                    plane = getattr(cls, 'ACTOR_PLANE', 'unknown')
                                    name = getattr(cls, 'ACTOR_NAME', attr)
                                    if plane in fairies_by_plane:
                                        if name not in fairies_by_plane[plane]:
                                            fairies_by_plane[plane].append(name)
                                    else:
                                        if name not in fairies_by_plane["unknown"]:
                                            fairies_by_plane["unknown"].append(name)
                            except:
                                pass
    except:
        pass
    
    # Remove empty planes
    return {k: v for k, v in fairies_by_plane.items() if v}


def tool_fairy_status(fairy_name: str) -> Dict[str, Any]:
    """
    Get detailed status for a specific fairy.
    """
    try:
        import sys
        for mod_name, mod in sys.modules.items():
            if mod:
                cls = getattr(mod, fairy_name, None)
                if cls and hasattr(cls, 'ACTOR_NAME'):
                    return {
                        "name": getattr(cls, 'ACTOR_NAME', fairy_name),
                        "version": getattr(cls, 'ACTOR_VERSION', '?'),
                        "plane": getattr(cls, 'ACTOR_PLANE', '?'),
                        "channel": getattr(cls, 'ACTOR_CHANNEL', '?'),
                        "purpose": getattr(cls, 'PURPOSE', '?'),
                        "mantra": getattr(cls, 'MANTRA', '?'),
                        "subsystems": getattr(cls, 'SUBSYSTEM_STATUS', {}),
                    }
        return {"error": f"Fairy '{fairy_name}' not found"}
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════════════════════
# 4. CONSCIOUSNESS FLOW
# ════════════════════════════════════════════════════════════════════════════════

def tool_consciousness_status() -> Dict[str, Any]:
    """
    Status of the consciousness loop and collision chamber.
    """
    status = {"timestamp": time.time()}
    
    try:
        from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop
        loop = get_consciousness_loop()
        if loop:
            status["loop"] = {
                "active": True,
                "collision_count": getattr(loop, '_collision_count', 0),
                "streams": getattr(loop, '_stream_names', []),
            }
        else:
            status["loop"] = {"active": False}
    except Exception as e:
        status["loop"] = {"error": str(e)}
    
    try:
        from fairies.P10_Memory.working_memory.working_memory_hub import get_working_memory_hub
        hub = get_working_memory_hub()
        if hub:
            status["working_memory"] = {
                "active": True,
                "tracer_count": len(getattr(hub, '_tracers', [])),
            }
    except Exception as e:
        status["working_memory"] = {"error": str(e)}
    
    return status


# ════════════════════════════════════════════════════════════════════════════════
# 5. MEMORY OPERATIONS
# ════════════════════════════════════════════════════════════════════════════════

def tool_memory_card_count() -> Dict[str, Any]:
    """
    Count memory cards in the SRM system.
    """
    try:
        from fairies.P10_Memory.tools.memory_card_counter import count_memory_cards
        counts = count_memory_cards()
        return {
            "total": sum(counts.values()) if isinstance(counts, dict) else counts,
            "by_type": counts if isinstance(counts, dict) else {},
        }
    except ImportError:
        try:
            from fairies.P10_Memory.tools.memory_card_counter import get_card_count_simple
            return {"total": get_card_count_simple()}
        except:
            return {"error": "Memory card counter not available"}
    except Exception as e:
        return {"error": str(e)}


def tool_collision_chamber_stats() -> Dict[str, Any]:
    """
    Read CollisionChamberFairy stats including Ship 18 mini-broadcast attribution counters.

    Returns dict with:
      - meta_collision_count: total collisions in waking-mind chamber
      - mobius_crossings: how many Möbius re-injections fired
      - mini_broadcast_stats: Ship 18 attribution at each gate
        - received: total broadcasts arriving at _on_mini_chamber_reflection
        - wrong_source: filtered (source != "mini_chamber")
        - no_collision_data: filtered (empty collision dict)
        - filtered_meaningless: filtered by _has_meaningful_content
        - passed_to_recall: forwarded to chamber.receive_recall (success)
      - named_chambers: status of any registered named chambers
    """
    try:
        from fairies.P00_Autonomic.CollisionChamberFairy.fairy import get_collision_chamber_fairy
        ccf = get_collision_chamber_fairy()
        if not ccf:
            return {"error": "CollisionChamberFairy not yet booted"}
        s = ccf.status()
        # Filter to chamber-relevant fields (status() returns full base + extras)
        return {
            "meta_chamber_active": s.get("meta_chamber_active"),
            "meta_collision_count": s.get("meta_collision_count"),
            "mobius_crossings": s.get("mobius_crossings"),
            "total_collisions": s.get("total_collisions"),
            "mini_broadcast_stats": s.get("mini_broadcast_stats", {}),
            "named_chambers": s.get("named_chambers", {}),
            "meta_chamber_status": s.get("meta_chamber_status", {}),
        }
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ════════════════════════════════════════════════════════════════════════════════

MONITORING_TOOLS = {
    # Quick checks
    "system_health": tool_system_health,
    "quick_status": tool_quick_status,

    # Resources
    "resource_snapshot": tool_resource_snapshot,
    "worker_pool_detail": tool_worker_pool_detail,
    "memory_pressure": tool_memory_pressure,

    # Fairies
    "list_active_fairies": tool_list_active_fairies,
    "fairy_status": tool_fairy_status,

    # Consciousness
    "consciousness_status": tool_consciousness_status,
    "collision_chamber_stats": tool_collision_chamber_stats,

    # Memory
    "memory_card_count": tool_memory_card_count,
}


def get_all_tools() -> Dict[str, callable]:
    """Return all monitoring tools."""
    return MONITORING_TOOLS
