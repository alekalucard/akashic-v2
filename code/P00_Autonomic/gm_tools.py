"""
GM Tools - Game Master utilities for Akashic system inspection.

These functions provide direct access to system state for:
- UMF (UnconsciousMindFairy)
- Claude/Nous (via MCP)
- Sourpatches (via MCP)

Used as fallbacks when postal tunnel isn't available.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Project root for state files
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def gm_inject_tracer(tracer_id: Optional[str] = None) -> str:
    """
    Inject iodine tracer into consciousness circulation.

    Args:
        tracer_id: Optional custom tracer ID. If None, generates one.

    Returns:
        The tracer_id that was injected
    """
    if not tracer_id:
        tracer_id = f"gm_{uuid.uuid4().hex[:8]}"

    try:
        # Try to get the shared postal hub
        from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        hub = get_shared_postal_hub()

        if hub:
            # Inject tracer via postal
            hub.route("consciousness.tracer", {
                "tracer_id": tracer_id,
                "source": "gm_tools",
                "ts": time.time(),
            })

            # Also inject via iodine tracer if available
            try:
                from P00_Autonomic.nervous_system.iodine_tracer import inject_tracer
                inject_tracer(tracer_id, "gm_inject")
            except ImportError:
                pass

            return tracer_id
    except ImportError:
        pass

    return tracer_id


def gm_postal_stats() -> Dict[str, Any]:
    """
    Get postal hub statistics.

    Returns:
        Dict with topic subscriptions, message counts, etc.
    """
    try:
        from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        hub = get_shared_postal_hub()

        if hub and hasattr(hub, 'get_stats'):
            return hub.get_stats()

        # Fallback: Try to get basic stats from hub
        if hub:
            stats = {
                "topics": {},
                "total_messages": 0,
                "source": "gm_tools_direct"
            }

            # Try to get subscriber counts
            if hasattr(hub, '_subscribers'):
                for topic, subs in hub._subscribers.items():
                    stats["topics"][topic] = len(subs)

            return stats
    except ImportError:
        pass

    return {"error": "Postal hub not available", "source": "gm_tools"}


def gm_fairy_audit() -> Dict[str, Any]:
    """
    Comprehensive audit of all fairies.

    Returns:
        Dict with audit results sorted by health score
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "fairies": [],
        "summary": {
            "total": 0,
            "healthy": 0,
            "needs_attention": 0,
        }
    }

    try:
        # Try to get from directory fairy
        from P00_Autonomic.directory_fairy import get_directory_fairy
        directory = get_directory_fairy()

        if directory and hasattr(directory, 'registry'):
            for name, contract in directory.registry.items():
                fairy_audit = {
                    "name": name,
                    "plane": contract.get("plane", "?"),
                    "channel": contract.get("channel", "?"),
                    "registration_complete": bool(contract.get("actor_name") and contract.get("plane")),
                    "has_purpose": bool(contract.get("purpose")),
                    "has_subscriptions": bool(contract.get("subscriptions")),
                    "has_intents": bool(contract.get("intents")),
                    "health_score": 0,
                }

                # Calculate health score
                score = 0
                if fairy_audit["registration_complete"]:
                    score += 25
                if fairy_audit["has_purpose"]:
                    score += 25
                if fairy_audit["has_subscriptions"]:
                    score += 25
                if fairy_audit["has_intents"]:
                    score += 25
                fairy_audit["health_score"] = score

                results["fairies"].append(fairy_audit)
                results["summary"]["total"] += 1
                if score >= 75:
                    results["summary"]["healthy"] += 1
                else:
                    results["summary"]["needs_attention"] += 1

            # Sort by health score (worst first)
            results["fairies"].sort(key=lambda f: f["health_score"])
    except ImportError:
        results["error"] = "DirectoryFairy not available"

    return results


def gm_missing_fairies() -> Dict[str, Any]:
    """
    Compare registered fairies against booted fairies.

    Returns:
        Dict with registered, booted, and missing fairy lists
    """
    result = {
        "registered": [],
        "booted": [],
        "missing": [],
        "timestamp": datetime.now().isoformat(),
    }

    try:
        # Get registered fairies from directory
        from P00_Autonomic.directory_fairy import get_directory_fairy
        directory = get_directory_fairy()

        if directory and hasattr(directory, 'registry'):
            result["registered"] = list(directory.registry.keys())

        # Get booted fairies from boot records if available
        boot_file = PROJECT_ROOT / "state" / "boot" / "booted_fairies.json"
        if boot_file.exists():
            try:
                booted = json.loads(boot_file.read_text())
                if isinstance(booted, list):
                    result["booted"] = booted
                elif isinstance(booted, dict):
                    result["booted"] = list(booted.keys())
            except:
                pass

        # Calculate missing
        registered_set = set(result["registered"])
        booted_set = set(result["booted"])
        result["missing"] = list(booted_set - registered_set)

        result["summary"] = {
            "registered_count": len(result["registered"]),
            "booted_count": len(result["booted"]),
            "missing_count": len(result["missing"]),
        }
    except ImportError as e:
        result["error"] = str(e)

    return result


def gm_world_status() -> Dict[str, Any]:
    """
    Get comprehensive world status snapshot.

    Returns:
        Dict with fairy registry, postal stats, consciousness loop state
    """
    status = {
        "ts": time.time(),
        "timestamp": datetime.now().isoformat(),
    }

    # Registry info
    try:
        from P00_Autonomic.directory_fairy import get_directory_fairy
        directory = get_directory_fairy()
        if directory and hasattr(directory, 'registry'):
            status["registry"] = {
                "count": len(directory.registry),
                "fairies": list(directory.registry.keys())[:50],  # Limit for size
            }
    except ImportError:
        status["registry"] = {"error": "DirectoryFairy not available"}

    # Postal info
    status["postal"] = gm_postal_stats()

    # Consciousness loop
    try:
        from P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop_fairy
        loop = get_consciousness_loop_fairy()
        if loop:
            status["consciousness_loop"] = {
                "exists": True,
                "running": getattr(loop, '_running', False),
                "collision_count": getattr(loop, '_collision_count', 0),
            }
    except ImportError:
        status["consciousness_loop"] = {"exists": False}

    # Write to state file for MCP to read
    state_dir = PROJECT_ROOT / "state" / "gm"
    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        (state_dir / "world_status.json").write_text(json.dumps(status, indent=2, default=str))
    except:
        pass

    return status
