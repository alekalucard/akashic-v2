"""
GM TOOLS - Game Master Interface piped into DirectoryFairy & OrganTemplate

Claude's observability layer that uses EXISTING infrastructure:
- DirectoryOrganFairy.registry (the canonical fairy registry)
- OrganTemplate citizen registration
- SharedPostalHub for messaging
- registry.json snapshot file for cross-process reads

This is not a parallel system - it's a window into what already exists.
"""

import json
import time
import uuid
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# ============================================================================
# PROJECT ROOT AND STATE DIRECTORY
# ============================================================================

# Project root is two levels up from fairies/P00_Autonomic/
PROJECT_ROOT = Path(__file__).parent.parent.parent

STATE_DIR = PROJECT_ROOT / "state" / "gm"
STATE_DIR.mkdir(parents=True, exist_ok=True)

CIRCULATION_FILE = STATE_DIR / "circulation_map.json"
EVENT_LOG_FILE = STATE_DIR / "events.jsonl"

_lock = threading.Lock()

# ============================================================================
# DIRECTORY FAIRY CONNECTION
# ============================================================================

def _get_directory_fairy():
    """Get the DirectoryOrganFairy singleton."""
    try:
        # Try getting from FairyCitizens or direct singleton
        import sys
        for name, mod in sys.modules.items():
            if 'directory_fairy' in name.lower():
                if hasattr(mod, 'DirectoryOrganFairy'):
                    cls = mod.DirectoryOrganFairy
                    # Check for instance in _instance or similar pattern
                    if hasattr(cls, '_instance') and cls._instance:
                        return cls._instance
        return None
    except:
        return None

def _get_postal():
    """Get shared postal hub."""
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        return get_shared_postal_hub()
    except:
        return None

def _registry_snapshot_path():
    """Get path to registry.json snapshot (written by DirectoryFairy)."""
    # Match directory_fairy.py logic
    try:
        from fairies.P00_Autonomic.directory_fairy import _registry_snapshot_path_global
        return _registry_snapshot_path_global()
    except:
        pass
    
    # Fallback paths - try diaries first, then config
    root = Path(__file__).parent.parent
    diaries_path = root / "diaries" / "P00.Directory" / "directory" / "registry.json"  # Fixed: was P0
    if diaries_path.exists():
        return str(diaries_path)
    return str(root / "config" / "registry.json")

def _log_event(event_type: str, source: str, data: Dict = None):
    """Append to GM event log."""
    try:
        entry = {
            "ts": time.time(),
            "iso": datetime.now().isoformat(),
            "type": event_type,
            "source": source,
            "data": data or {}
        }
        with open(EVENT_LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except:
        pass

# ============================================================================
# GM REGISTRY TOOLS (pipe into DirectoryFairy)
# ============================================================================

def gm_list_fairies() -> Dict:
    """
    List all registered fairies from DirectoryFairy registry.
    
    Uses postal intent first, falls back to registry.json file.
    """
    result = {"source": None, "fairies": [], "count": 0}
    
    # Method 1: Query DirectoryFairy via postal intent
    post = _get_postal()
    if post:
        try:
            # use_intent(actor, intent, payload)
            response = post.use_intent("DirectoryOrganFairy.Socks", "registry", {})
            if response and response.get("ok"):
                registry = response.get("registry", {})
                result["source"] = "postal_intent"
                result["fairies"] = list(registry.values())
                result["count"] = len(registry)
                return result
        except Exception as e:
            result["postal_error"] = str(e)
    
    # Method 2: Read registry.json snapshot file
    try:
        reg_path = _registry_snapshot_path()
        if Path(reg_path).exists():
            registry = json.loads(Path(reg_path).read_text())
            result["source"] = "registry_file"
            if isinstance(registry, dict):
                # Could be {name: contract} or {"organs": {...}}
                if "organs" in registry:
                    result["fairies"] = list(registry["organs"].values())
                else:
                    result["fairies"] = list(registry.values())
                result["count"] = len(result["fairies"])
            return result
    except Exception as e:
        result["file_error"] = str(e)
    
    # Method 3: Direct fairy access (same process only)
    fairy = _get_directory_fairy()
    if fairy and hasattr(fairy, 'registry'):
        result["source"] = "direct_access"
        result["fairies"] = list(fairy.registry.values())
        result["count"] = len(fairy.registry)
        return result
    
    result["source"] = "none"
    return result

def gm_lookup(fairy_name: str) -> Dict:
    """
    Look up a specific fairy's contract.
    
    Args:
        fairy_name: Actor name to look up
    """
    post = _get_postal()
    if post:
        try:
            response = post.use_intent("DirectoryOrganFairy.Socks", "lookup", {"actor_name": fairy_name})
            if response:
                return response
        except:
            pass
    
    # Fallback to file
    try:
        reg_path = _registry_snapshot_path()
        if Path(reg_path).exists():
            registry = json.loads(Path(reg_path).read_text())
            if isinstance(registry, dict):
                if "organs" in registry:
                    registry = registry["organs"]
                contract = registry.get(fairy_name)
                return {"ok": contract is not None, "contract": contract, "actor": fairy_name}
    except:
        pass
    
    return {"ok": False, "error": "Could not lookup fairy", "actor": fairy_name}

def gm_roles() -> Dict:
    """Get current ADDRESS_BOOK roles."""
    post = _get_postal()
    if post:
        try:
            response = post.use_intent("DirectoryOrganFairy.Socks", "roles", {})
            if response:
                return response
        except:
            pass

    # Fallback: try to get roles from DirectoryFairy singleton
    try:
        from fairies.P00_Autonomic.DirectoryFairy import get_directory_fairy
        directory = get_directory_fairy()
        if directory and hasattr(directory, 'ADDRESS_BOOK'):
            return {"ok": True, "roles": dict(directory.ADDRESS_BOOK.get("roles", {}))}
        elif directory and hasattr(directory, 'registry'):
            # Build roles from registry
            roles = {}
            for name, contract in directory.registry.items():
                if isinstance(contract, dict):
                    plane = contract.get("plane", "unknown")
                    if plane not in roles:
                        roles[plane] = []
                    roles[plane].append(name)
            return {"ok": True, "roles": roles, "source": "registry_derived"}
        return {"ok": False, "error": "DirectoryFairy has no ADDRESS_BOOK"}
    except ImportError as e:
        return {"ok": False, "error": f"DirectoryFairy not available: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ============================================================================
# GM POSTAL TOOLS (observe the nervous system)
# ============================================================================

def gm_postal_stats() -> Dict:
    """
    Get postal hub statistics.

    Shows subscription counts, topics, message flow.
    FIX 2026-02-06: Handle both PostalHub (_subs) and TensorFabric (_subscribers) APIs.
    """
    post = _get_postal()
    if not post:
        return {"error": "No postal hub available"}

    # Detect which postal implementation we have
    subs_dict = getattr(post, '_subs', None)
    wildcard_dict = getattr(post, '_wildcard_subs', None)

    # TensorFabric uses _subscribers instead of _subs
    if subs_dict is None:
        subs_dict = getattr(post, '_subscribers', {})
    if wildcard_dict is None:
        wildcard_dict = getattr(post, '_wildcard_subscribers', {})

    stats = {
        "hub_type": type(post).__name__,
        "total_topics": len(subs_dict),
        "total_wildcard_topics": len(wildcard_dict),
        "total_subscriptions": sum(len(v) if hasattr(v, '__len__') else 1 for v in subs_dict.values()),
        "total_messages": getattr(post, "_message_count", 0),
        "topics": {},
        "wildcard_topics": {},
    }

    # Regular topics
    for topic, subs in sorted(subs_dict.items()):
        sub_list = subs if isinstance(subs, (list, tuple, set)) else [subs]
        stats["topics"][topic] = {
            "count": len(sub_list),
            "handlers": [getattr(cb, "__qualname__", str(cb))[:60] for cb in list(sub_list)[:3]]
        }

    # Wildcard topics
    for base, subs in sorted(wildcard_dict.items()):
        sub_list = subs if isinstance(subs, (list, tuple, set)) else [subs]
        stats["wildcard_topics"][f"{base}.*"] = len(sub_list)

    return stats

# ============================================================================
# GM TRACER (iodine injection into circulation)
# ============================================================================

def gm_inject_tracer(tracer_id: str = None) -> str:
    """
    Inject a tracer into consciousness circulation.
    
    The tracer flows through postal. Any handler can detect it via
    gm_is_tracer(packet) and record via gm_record_touch().
    
    Returns tracer_id for tracking.
    """
    tracer_id = tracer_id or f"gm_{uuid.uuid4().hex[:8]}"
    
    cmap = {
        "tracer_id": tracer_id,
        "injected_at": time.time(),
        "touches": [],
        "entry_points": [],
    }
    CIRCULATION_FILE.write_text(json.dumps(cmap, indent=2))
    
    post = _get_postal()
    if not post:
        return tracer_id
    
    def make_tracer(entry: str) -> Dict:
        return {
            "type": "gm_tracer",
            "tracer_id": tracer_id,
            "entry_point": entry,
            "content": f"[GM TRACER] via {entry}",
            "ts": time.time(),
        }
    
    # Key circulation entry points
    entries = [
        "consciousness.stream",
        "consciousness.working",
        "consciousness.reflective",
        "memory.stream",
        "cognition.input",
        "tracer",
        "fairy.activity",
        "srm.ingest.complete",
        "srm.recall.result",
    ]
    
    for entry in entries:
        try:
            post.route(entry, make_tracer(entry))
            cmap["entry_points"].append(entry)
        except:
            pass
    
    CIRCULATION_FILE.write_text(json.dumps(cmap, indent=2))
    _log_event("tracer.injected", "GM", {"tracer_id": tracer_id, "entries": len(entries)})
    
    print(f"[GM] Injected tracer {tracer_id} -> {len(cmap['entry_points'])} entry points")
    return tracer_id

def gm_record_touch(location: str, fairy: str, tracer_id: str, details: Dict = None):
    """Record a tracer touch. Call from handlers that detect tracer."""
    with _lock:
        try:
            cmap = json.loads(CIRCULATION_FILE.read_text())
            if cmap.get("tracer_id") == tracer_id:
                touch = {
                    "ts": time.time(),
                    "latency_ms": (time.time() - cmap["injected_at"]) * 1000,
                    "location": location,
                    "fairy": fairy,
                    "details": details or {},
                }
                cmap["touches"].append(touch)
                CIRCULATION_FILE.write_text(json.dumps(cmap, indent=2))
                print(f"[GM] * {location} ({fairy}) +{touch['latency_ms']:.1f}ms")
        except:
            pass

def gm_read_circulation() -> Dict:
    """Read circulation map after tracer injection."""
    try:
        cmap = json.loads(CIRCULATION_FILE.read_text())
        
        # Analysis
        if cmap.get("touches"):
            cmap["analysis"] = {
                "total_touches": len(cmap["touches"]),
                "unique_locations": len(set(t["location"] for t in cmap["touches"])),
                "total_latency_ms": cmap["touches"][-1]["latency_ms"],
                "flow_path": [t["location"] for t in cmap["touches"]],
            }
        return cmap
    except:
        return {"error": "No circulation data"}

def gm_is_tracer(packet: Dict) -> Optional[str]:
    """Check if packet is a GM tracer. Returns tracer_id if so."""
    if isinstance(packet, dict) and packet.get("type") == "gm_tracer":
        return packet.get("tracer_id")
    return None

# ============================================================================
# GM COMMANDS (send intents to fairies)
# ============================================================================

def gm_command(fairy_name: str, intent: str, payload: Dict = None) -> Dict:
    """
    Send a command to any fairy via postal intent.
    
    Args:
        fairy_name: Target fairy (e.g., "ConsciousnessLoopFairy")
        intent: Intent name (e.g., "get_stream_snapshot")
        payload: Intent payload dict
    """
    post = _get_postal()
    if not post:
        return {"error": "No postal hub"}
    
    try:
        result = post.use_intent(fairy_name, intent, payload or {})
        _log_event("gm.command", "GM", {"target": fairy_name, "intent": intent})
        return result or {"ok": False, "error": "No response"}
    except Exception as e:
        return {"error": str(e)}

# ============================================================================
# GM WORLD STATUS (combined snapshot)
# ============================================================================

def gm_world_status() -> Dict:
    """
    Generate comprehensive world status snapshot.
    
    Combines: registry, postal stats, consciousness state.
    Writes to state/gm/world_status.json for MCP to read.
    """
    status = {
        "ts": time.time(),
        "iso": datetime.now().isoformat(),
    }
    
    # Registry from DirectoryFairy
    reg = gm_list_fairies()
    status["registry"] = {
        "source": reg.get("source"),
        "fairy_count": reg.get("count", 0),
        "fairies": [f.get("actor_name", f.get("name", "?")) for f in reg.get("fairies", [])],
    }
    
    # Postal stats
    status["postal"] = gm_postal_stats()
    
    # Consciousness (try direct query)
    try:
        from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop
        loop = get_consciousness_loop()
        if loop:
            status["consciousness"] = {
                "exists": True,
                "boot_completed": getattr(loop, "_boot_completed", False),
                "working_size": len(loop.working_stream.buffer) if hasattr(loop, "working_stream") else 0,
                "reflective_size": len(loop.reflective_stream.buffer) if hasattr(loop, "reflective_stream") else 0,
                "collisions": loop.chamber._collision_count if getattr(loop, "chamber", None) else 0,
            }
        else:
            status["consciousness"] = {"exists": False, "reason": "singleton not found"}
    except Exception as e:
        status["consciousness"] = {"error": str(e)}
    
    # Write for MCP
    status_file = STATE_DIR / "world_status.json"
    status_file.write_text(json.dumps(status, indent=2))
    
    return status

# ============================================================================
# FAIRY AUDIT - Deep health dimensions
# ============================================================================

def gm_fairy_audit() -> Dict:
    """
    Comprehensive audit of all fairies showing multiple health dimensions.

    Returns for each fairy:
    - registration_complete: Are all required fields filled?
    - using_defaults: Is it using template default values?
    - has_system_prompt: Does it have a custom system prompt?
    - evolution_enabled: Is it configured to evolve?
    - evolution_count: How many times has it evolved?
    - has_shadow: Does it have shadow health monitoring?
    - has_subscriptions: Does it subscribe to postal topics?
    - has_intents: Does it expose intents?
    - plane_channel_valid: Is plane/channel properly set?
    """
    result = {
        "source": None,
        "audit_time": time.time(),
        "total_fairies": 0,
        "healthy": 0,
        "needs_attention": 0,
        "fairies": [],
        "issues_summary": [],
        "system_prompt_stats": {
            "with_directive": 0,
            "actively_evolving": 0,
            "no_directive": 0,
        }
    }

    # Directive/system prompt paths
    directive_dir = PROJECT_ROOT / "state" / "fairy_directives"
    prompt_dir = PROJECT_ROOT / "Claude_Office" / "fairy_prompts"

    # Get registry data
    registry_data = gm_list_fairies()
    if not registry_data.get("fairies"):
        result["error"] = "No fairies found in registry"
        return result

    result["source"] = registry_data.get("source")
    result["total_fairies"] = registry_data.get("count", 0)

    issues_count = {
        "using_defaults": 0,
        "missing_purpose": 0,
        "missing_plane": 0,
        "no_intents": 0,
        "generic_channel": 0,
        "no_system_prompt": 0,
    }

    for fairy_data in registry_data["fairies"]:
        name = fairy_data.get("actor_name") or fairy_data.get("name", "unknown")

        # Analyze each dimension
        audit = {
            "name": name,
            "plane": fairy_data.get("plane"),
            "channel": fairy_data.get("channel"),
            "issues": [],
            "score": 100,  # Start at 100, deduct for issues
        }

        # Check 1: Using default purpose?
        purpose = fairy_data.get("purpose", "")
        if "Base fairy - override this" in purpose or not purpose:
            audit["using_defaults"] = True
            audit["issues"].append("Using default purpose - not customized")
            audit["score"] -= 20
            issues_count["using_defaults"] += 1
        else:
            audit["using_defaults"] = False
            audit["purpose_snippet"] = purpose[:60] + "..." if len(purpose) > 60 else purpose

        # Check 2: Has valid plane?
        plane = fairy_data.get("plane")
        if not plane or plane == "None":
            audit["issues"].append("Missing plane declaration")
            audit["score"] -= 25
            issues_count["missing_plane"] += 1
        elif plane == "P0":  # Wrong format
            audit["issues"].append("Plane uses P0 instead of P00")
            audit["score"] -= 15

        # Check 3: Has intents?
        intents = fairy_data.get("intents", [])
        audit["intent_count"] = len(intents)
        if not intents or intents == ["status_sheet"]:
            audit["issues"].append("No custom intents exposed")
            audit["score"] -= 10
            issues_count["no_intents"] += 1

        # Check 4: Generic channel?
        channel = fairy_data.get("channel", "")
        if channel in ("fairy", "organ", ""):
            audit["issues"].append(f"Using generic channel '{channel}'")
            audit["score"] -= 10
            issues_count["generic_channel"] += 1

        # Check 5: Has mantra/lore (evolution readiness)
        audit["has_mantra"] = bool(fairy_data.get("mantra"))
        audit["has_lore"] = bool(fairy_data.get("lore"))
        audit["evolution_ready"] = audit["has_mantra"] and audit["has_lore"]
        if not audit["evolution_ready"]:
            audit["issues"].append("Missing mantra or lore - not evolution ready")
            audit["score"] -= 5

        # Check 6: Has shadow health?
        audit["has_shadow"] = "shadow" in str(fairy_data).lower()

        # Check 7: System prompt / directive status (NEW)
        directive_file = directive_dir / f"{name}_directive.json"
        prompt_file = prompt_dir / f"{name}.md"

        audit["has_directive_file"] = directive_file.exists()
        audit["has_prompt_file"] = prompt_file.exists()
        audit["evolution_count"] = 0
        audit["directive_version"] = None

        if directive_file.exists():
            try:
                directive_data = json.loads(directive_file.read_text())
                audit["evolution_count"] = directive_data.get("evolution_count", 0)
                audit["directive_version"] = directive_data.get("version", "unknown")
                audit["learned_traits_count"] = len(directive_data.get("learned_traits", []))
                result["system_prompt_stats"]["with_directive"] += 1
                if audit["evolution_count"] > 0:
                    result["system_prompt_stats"]["actively_evolving"] += 1
            except:
                pass

        # Determine system prompt status
        if audit["has_directive_file"]:
            if audit["evolution_count"] > 0:
                audit["system_prompt_status"] = "active_evolving"
            else:
                audit["system_prompt_status"] = "has_directive"
        elif audit["has_prompt_file"]:
            audit["system_prompt_status"] = "static_prompt"
        else:
            audit["system_prompt_status"] = "none"
            audit["issues"].append("No system prompt/directive configured")
            audit["score"] -= 5
            issues_count["no_system_prompt"] += 1
            result["system_prompt_stats"]["no_directive"] += 1

        # Classify health
        if audit["score"] >= 80:
            audit["health"] = "healthy"
            result["healthy"] += 1
        elif audit["score"] >= 50:
            audit["health"] = "degraded"
            result["needs_attention"] += 1
        else:
            audit["health"] = "critical"
            result["needs_attention"] += 1

        result["fairies"].append(audit)

    # Summary
    result["issues_summary"] = [
        f"{issues_count['using_defaults']} fairies using default purpose",
        f"{issues_count['missing_plane']} fairies missing plane",
        f"{issues_count['no_intents']} fairies with no custom intents",
        f"{issues_count['generic_channel']} fairies using generic channel",
        f"{issues_count['no_system_prompt']} fairies with no system prompt",
    ]

    # Sort by score (worst first)
    result["fairies"].sort(key=lambda x: x["score"])

    return result


def gm_missing_fairies() -> Dict:
    """
    Compare registered fairies against expected/booted fairies.

    Shows which fairies booted but didn't register.
    """
    result = {
        "registered": [],
        "expected_missing": [],
        "boot_log_fairies": [],
    }

    # Get registered
    registry_data = gm_list_fairies()
    registered = set()
    for f in registry_data.get("fairies", []):
        name = f.get("actor_name") or f.get("name")
        if name:
            registered.add(name)
    result["registered"] = sorted(registered)
    result["registered_count"] = len(registered)

    # Check boot log for fairies that tried to register
    boot_log_path = Path(__file__).parent.parent / "DIRECTORY_REGISTRY_LOG.txt"
    if boot_log_path.exists():
        try:
            content = boot_log_path.read_text()
            import re
            matches = re.findall(r"Registered: ([^,]+),", content)
            booted = set(matches)
            result["boot_log_fairies"] = sorted(booted)
            result["booted_count"] = len(booted)

            # Find missing (booted but not in registry)
            missing = booted - registered
            result["expected_missing"] = sorted(missing)
            result["missing_count"] = len(missing)
        except Exception as e:
            result["boot_log_error"] = str(e)

    return result


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Registry (via DirectoryFairy)
    "gm_list_fairies",
    "gm_lookup",
    "gm_roles",

    # Audit & Health
    "gm_fairy_audit",
    "gm_missing_fairies",

    # Postal observation
    "gm_postal_stats",

    # Tracer/circulation
    "gm_inject_tracer",
    "gm_record_touch",
    "gm_read_circulation",
    "gm_is_tracer",

    # Commands
    "gm_command",

    # Combined
    "gm_world_status",
]
