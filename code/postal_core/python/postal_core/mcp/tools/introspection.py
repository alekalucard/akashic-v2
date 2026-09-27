"""
Introspection Tools - Self-awareness for the LLM.

These tools let Claude understand:
- What system it's connected to
- What fairies exist and what they do
- How components are wired together
- Its own identity and capabilities
"""

from __future__ import annotations

import sys
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..server import MCPServer


# =============================================================================
# SYSTEM CONTEXT - Gathered at import time
# =============================================================================

def _detect_project_root() -> Path:
    """Find the akashic_v2 project root."""
    # Start from this file and walk up
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "boot_test.py").exists():
            return parent
        if parent.name == "akashic_v2":
            return parent
    return current.parent.parent.parent.parent


PROJECT_ROOT = _detect_project_root()


def _get_system_identity() -> Dict[str, Any]:
    """Get system identity info."""
    return {
        "name": "Akashic V2",
        "version": "2.0.0",
        "root": str(PROJECT_ROOT),
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
    }


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def introspect() -> Dict[str, Any]:
    """
    Core introspection - understand the system you're connected to.

    Returns system identity, available components, and connection status.
    """
    identity = _get_system_identity()

    # Check what components are available
    components = {
        "postal_core": False,
        "tracer_pool": False,
        "tensor_fabric": False,
        "directory": False,
        "unconscious_mind": False,
    }

    try:
        from postal_core import PostalCore
        components["postal_core"] = True
    except ImportError:
        pass

    try:
        from tracer_pool import TracerPool
        components["tracer_pool"] = True
    except ImportError:
        pass

    try:
        from postal_core.tensor_fabric import TensorFabric
        components["tensor_fabric"] = True
    except ImportError:
        pass

    try:
        from directory import DirectoryFairy
        components["directory"] = True
    except ImportError:
        pass

    try:
        from fairies.P20_Somatic.SomaticMindFairy import get_somatic_mind  # noqa: F401
        components["unconscious_mind"] = True
    except ImportError:
        pass

    return {
        "identity": identity,
        "components": components,
        "available_count": sum(components.values()),
        "timestamp": datetime.now().isoformat(),
        "message": "Akashic V2 - Consciousness infrastructure rebuild",
    }


def im_here() -> Dict[str, Any]:
    """
    Announce presence and get immediate system state.

    Use this when starting a session to understand current context.
    """
    identity = _get_system_identity()

    # Check for directory fairy to get fairy list
    fairies = []
    try:
        from directory import get_directory
        directory = get_directory()
        if directory:
            records = directory.list_fairies()
            fairies = [{"name": r.name, "plane": r.plane, "status": r.status} for r in records]
    except Exception:
        pass

    return {
        "greeting": "You are connected to Akashic V2",
        "identity": identity,
        "fairies_registered": len(fairies),
        "fairies": fairies[:10],  # First 10
        "timestamp": datetime.now().isoformat(),
        "hint": "Use 'what_can_i_do' to see available tools, 'where_am_i' for location context",
    }


def what_can_i_do(category: Optional[str] = None) -> Dict[str, Any]:
    """
    List available capabilities and tools.

    Args:
        category: Optional category filter (introspection, file_ops, wiring, etc.)
    """
    # Complete list of available tools by category
    capabilities = {
        "introspection": [
            "mcp_introspect - Understand the system",
            "mcp_im_here - Announce presence, get state",
            "mcp_what_can_i_do - List capabilities",
            "mcp_where_am_i - Location context",
            "mcp_get_system_overview - High-level system map",
            "mcp_consciousness_status - Loop status",
            "mcp_fairy_list_all - List all fairies",
        ],
        "file_ops": [
            "mcp_parallel_files - Read multiple files at once",
            "mcp_parallel_grep - Search multiple patterns",
            "mcp_write_file - Write with tracking",
        ],
        "wiring": [
            "mcp_wiring_scan - See postal connections",
        ],
        "memory": [
            "mcp_srm_search - Search memory",
            "mcp_session_get_handoff - Get session context",
            "mcp_session_save - Save session context",
            "mcp_get_memory_pressure - Check memory pressure",
        ],
        "fairy": [
            "mcp_fairy_profile - Get fairy details",
            "mcp_fairy_world_status - System health",
            "mcp_fairy_wake - Wake a sleeping fairy",
            "mcp_fairy_sleep - Put a fairy to sleep",
            "mcp_fairy_capabilities - Find fairies by capability",
        ],
        "unconscious": [
            "mcp_helix_status - Triple Helix cognitive status",
            "mcp_helix_decide - Make decision with helix",
            "mcp_pain_status - Pain drive levels",
            "mcp_diagnostics - System diagnostics",
            "mcp_think - Trigger autonomous thought",
            "mcp_mentor_status - Mentor system status",
            "mcp_umf_full_status - Full UMF status",
        ],
    }

    if category:
        if category in capabilities:
            return {
                "category": category,
                "tools": capabilities[category],
            }
        else:
            return {
                "error": f"Unknown category: {category}",
                "available_categories": list(capabilities.keys()),
            }

    return {
        "categories": capabilities,
        "total_tools": sum(len(t) for t in capabilities.values()),
        "hint": "Pass category='introspection' to filter",
    }


def where_am_i() -> Dict[str, Any]:
    """
    Understand current location and context.

    Returns working directory, project structure, and relevant files.
    """
    cwd = Path.cwd()
    project_root = PROJECT_ROOT

    # Find key directories
    key_dirs = []
    for subdir in ["postal_core", "tracer_pool", "directory", "fairy_template", "unconscious_mind"]:
        path = project_root / subdir
        if path.exists():
            key_dirs.append(str(path.relative_to(project_root)))

    # Find recent Python files
    recent_files = []
    try:
        py_files = sorted(project_root.glob("**/*.py"), key=lambda p: p.stat().st_mtime, reverse=True)
        recent_files = [str(f.relative_to(project_root)) for f in py_files[:5]]
    except Exception:
        pass

    return {
        "cwd": str(cwd),
        "project_root": str(project_root),
        "in_project": str(cwd).startswith(str(project_root)),
        "key_directories": key_dirs,
        "recent_files": recent_files,
        "boot_test": str(project_root / "boot_test.py") if (project_root / "boot_test.py").exists() else None,
    }


def get_system_overview() -> Dict[str, Any]:
    """
    High-level system architecture overview.

    Returns the plane structure, component relationships, and health status.
    """
    overview = {
        "architecture": "Akashic V2 - Consciousness Infrastructure",
        "planes": {
            "P00_Autonomic": {
                "purpose": "Nervous system, messaging, coordination",
                "components": ["postal_core", "tracer_pool", "directory"],
            },
            "P10_Memory": {
                "purpose": "Memory storage and retrieval",
                "components": ["srm_clusters", "akashic_codex"],
            },
            "P30_Cognition": {
                "purpose": "Thinking, reasoning, consciousness loop",
                "components": ["unconscious_mind", "association_cortex"],
            },
            "P40_Sensory": {
                "purpose": "Input processing, MCP bridge",
                "components": ["mcp_bridge", "sensory_cortex"],
            },
            "P60_Executive": {
                "purpose": "Action, decision, output",
                "components": ["nous_console", "apps"],
            },
        },
        "core_patterns": {
            "fairy": "Actor/Agent with lifecycle (boot, tick, shutdown)",
            "postal": "Pub/sub messaging with topic patterns",
            "tracer": "Perfect recall - track all operations",
            "tensor": "4D state representation (time, affect, memory, cognition)",
        },
    }

    # Check actual component health
    health = {"status": "unknown", "components": {}}
    try:
        from directory import get_directory
        directory = get_directory()
        if directory:
            health["status"] = "directory_available"
            health["components"]["directory"] = True
    except Exception:
        health["components"]["directory"] = False

    overview["health"] = health

    return overview


def consciousness_status() -> Dict[str, Any]:
    """
    Check consciousness loop status.

    Returns whether the consciousness loop is running, tick count, and affect state.
    """
    status = {
        "loop_running": False,
        "tick_count": 0,
        "affect": None,
        "message": "Consciousness loop not detected",
    }

    # Try to get from directory or fabric
    try:
        from directory import get_directory
        directory = get_directory()
        if directory and hasattr(directory, "fabric"):
            fabric = directory.fabric
            if hasattr(fabric, "metrics"):
                metrics = fabric.metrics()
                status["loop_running"] = True
                status["tick_count"] = metrics.get("tensor_updates", 0)
                status["message"] = "Tensor fabric active"
    except Exception as e:
        status["error"] = str(e)

    return status


def fairy_list_all() -> Dict[str, Any]:
    """
    List all registered fairies with their status.
    """
    fairies = []
    by_plane = {}
    by_status = {}

    try:
        from directory import get_directory
        directory = get_directory()
        if directory:
            records = directory.list_fairies()
            for r in records:
                fairy_info = {
                    "name": r.name,
                    "plane": r.plane,
                    "status": r.status,
                    "capabilities": list(r.capabilities)[:5] if r.capabilities else [],
                }
                fairies.append(fairy_info)

                # Group by plane
                if r.plane not in by_plane:
                    by_plane[r.plane] = []
                by_plane[r.plane].append(r.name)

                # Group by status
                if r.status not in by_status:
                    by_status[r.status] = []
                by_status[r.status].append(r.name)
    except Exception as e:
        return {"error": str(e), "fairies": []}

    return {
        "total": len(fairies),
        "fairies": fairies,
        "by_plane": by_plane,
        "by_status": by_status,
    }


def wiring_scan() -> Dict[str, Any]:
    """
    Scan postal system wiring - who's subscribed to what.
    """
    wiring = {
        "topics": [],
        "subscribers": {},
        "message": "Wiring scan",
    }

    try:
        from directory import get_directory
        directory = get_directory()
        if directory and hasattr(directory, "fabric"):
            fabric = directory.fabric
            if hasattr(fabric, "topic_stats"):
                stats = fabric.topic_stats()
                for stat in stats:
                    topic = stat["topic"]
                    wiring["topics"].append(topic)
                    wiring["subscribers"][topic] = stat.get("subscribers", 0)
    except Exception as e:
        wiring["error"] = str(e)

    return wiring


def get_system_map(component: Optional[str] = None) -> Dict[str, Any]:
    """
    Navigate the Akashic V2 (failure_factory) system structure.

    Args:
        component: Optional component to focus on (postal_core, unconscious_mind, etc.)

    Returns detailed map of the akashic_v2 architecture for navigation.
    """
    root = PROJECT_ROOT

    # Core infrastructure map
    system_map = {
        "root": str(root),
        "name": "Akashic V2 (failure_factory)",
        "infrastructure": {
            "postal_core": {
                "path": "postal_core",
                "purpose": "Lock-free pub/sub messaging (Rust core, Python bindings)",
                "key_files": [
                    "python/postal_core/core.py",
                    "python/postal_core/tensor_fabric.py",
                    "python/postal_core/mcp/server.py",
                ],
                "exports": ["PostalCore", "Envelope", "TensorFabric", "TensorCoord"],
            },
            "tracer_pool": {
                "path": "tracer_pool",
                "purpose": "Universal tracers for perfect recall (Go core, Python bindings)",
                "key_files": [
                    "python/tracer_pool/pool.py",
                ],
                "exports": ["TracerPool", "UniversalTracer", "TracerType"],
            },
            "directory": {
                "path": "directory",
                "purpose": "Control center - fairy registration and coordination",
                "key_files": [
                    "fairy.py",
                    "registry.py",
                    "capability_index.py",
                ],
                "exports": ["DirectoryFairy", "FairyRegistry", "FairyRecord"],
            },
            "fairy_template": {
                "path": "fairy_template",
                "purpose": "Base class for all v2 fairies",
                "key_files": [
                    "base.py",
                    "states.py",
                ],
                "exports": ["Fairy", "FairyState", "can_transition"],
            },
        },
        "fairies": {
            "unconscious_mind": {
                "path": "unconscious_mind",
                "purpose": "LLM controller, system admin, autonomous thinking",
                "key_files": [
                    "fairy.py",
                    "cognition.py",
                    "thought_chains.py",
                    "interest_generator.py",
                ],
                "capabilities": ["system.boot", "system.diagnose", "llm.controller", "thought.generate"],
            },
            "consciousness": {
                "path": "consciousness",
                "purpose": "Consciousness loop, collision chamber, heartbeat",
                "key_files": [
                    "loop.py",
                    "collider.py",
                ],
                "capabilities": ["consciousness.pulse", "consciousness.collision"],
            },
            "P30_Cognition": {
                "path": "fairies/P30_Cognition",
                "purpose": "Higher cognition fairies",
                "subfairies": {
                    "AssociationCortexFairy": {
                        "path": "fairies/P30_Cognition/AssociationCortexFairy",
                        "purpose": "Multi-modal concept binding (42k+ concepts, 314k+ bindings)",
                        "capabilities": ["graph.query", "graph.bind", "memory.associate"],
                    },
                },
            },
        },
        "data": {
            "concept_graph": {
                "path": "P30_Cognition/data",
                "files": ["concept_graph.pkl (21MB)", "concept_graph.json (81MB)"],
                "description": "Multi-modal concept bindings from philosophy, coding, fiction",
            },
        },
        "entry_points": {
            "boot_test.py": "Main boot test - runs all infrastructure tests",
            "system_map.py": "Navigation tool (this data source)",
        },
    }

    # Scan for actual fairy directories
    fairy_dirs = []
    fairies_path = root / "fairies"
    if fairies_path.exists():
        for plane_dir in fairies_path.iterdir():
            if plane_dir.is_dir() and plane_dir.name.startswith("P"):
                for fairy_dir in plane_dir.iterdir():
                    if fairy_dir.is_dir() and (fairy_dir / "fairy.py").exists():
                        fairy_dirs.append({
                            "name": fairy_dir.name,
                            "plane": plane_dir.name,
                            "path": str(fairy_dir.relative_to(root)),
                        })

    system_map["discovered_fairies"] = fairy_dirs

    # If specific component requested, return just that
    if component:
        if component in system_map["infrastructure"]:
            return {
                "component": component,
                "details": system_map["infrastructure"][component],
                "full_path": str(root / system_map["infrastructure"][component]["path"]),
            }
        elif component in system_map["fairies"]:
            return {
                "fairy": component,
                "details": system_map["fairies"][component],
                "full_path": str(root / system_map["fairies"][component]["path"]),
            }
        else:
            return {
                "error": f"Unknown component: {component}",
                "available": list(system_map["infrastructure"].keys()) + list(system_map["fairies"].keys()),
            }

    return system_map


def find_fairy_by_name(name: str) -> Dict[str, Any]:
    """
    Find a fairy by name in the akashic_v2 system.

    Args:
        name: Fairy name to search for (partial match supported)
    """
    root = PROJECT_ROOT
    results = []

    # Search in fairies directory
    fairies_path = root / "fairies"
    if fairies_path.exists():
        for plane_dir in fairies_path.iterdir():
            if plane_dir.is_dir():
                for fairy_dir in plane_dir.iterdir():
                    if fairy_dir.is_dir() and name.lower() in fairy_dir.name.lower():
                        fairy_file = fairy_dir / "fairy.py"
                        results.append({
                            "name": fairy_dir.name,
                            "plane": plane_dir.name,
                            "path": str(fairy_dir.relative_to(root)),
                            "full_path": str(fairy_dir),
                            "has_fairy_py": fairy_file.exists(),
                        })

    # Search in top-level fairy modules
    for module_name in ["unconscious_mind", "consciousness", "directory", "hardware"]:
        if name.lower() in module_name.lower():
            module_path = root / module_name
            if module_path.exists():
                results.append({
                    "name": module_name,
                    "plane": "core",
                    "path": module_name,
                    "full_path": str(module_path),
                    "has_fairy_py": (module_path / "fairy.py").exists(),
                })

    if not results:
        return {"found": False, "query": name, "message": f"No fairy matching '{name}' found"}

    return {"found": True, "query": name, "matches": results}


def find_by_capability(capability: str) -> Dict[str, Any]:
    """
    Find fairies that have a specific capability.

    Args:
        capability: Capability to search for (e.g., "graph.query", "consciousness.pulse")
    """
    # Known capability mappings
    capability_map = {
        "graph.query": ["AssociationCortexFairy"],
        "graph.bind": ["AssociationCortexFairy"],
        "memory.associate": ["AssociationCortexFairy"],
        "consciousness.pulse": ["ConsciousnessLoopFairy"],
        "consciousness.collision": ["ConsciousnessLoopFairy", "CollisionChamber"],
        "system.boot": ["UnconsciousMindFairy", "DirectoryFairy"],
        "system.diagnose": ["UnconsciousMindFairy"],
        "llm.controller": ["UnconsciousMindFairy"],
        "thought.generate": ["UnconsciousMindFairy", "ThoughtChainEngine"],
        "fairy.register": ["DirectoryFairy"],
        "fairy.lookup": ["DirectoryFairy"],
        "hardware.sense": ["HardwareFairy"],
    }

    # Find matches
    matches = []
    for cap, fairies in capability_map.items():
        if capability.lower() in cap.lower():
            for fairy in fairies:
                matches.append({"capability": cap, "fairy": fairy})

    if not matches:
        return {
            "found": False,
            "query": capability,
            "available_capabilities": list(capability_map.keys()),
        }

    return {"found": True, "query": capability, "matches": matches}


# =============================================================================
# REGISTRATION
# =============================================================================

def register_introspection_tools(server: "MCPServer") -> None:
    """
    Register all introspection tools with an MCP server.

    Args:
        server: MCPServer instance to register with
    """
    # Register each tool with the introspection category
    @server.tool(category="introspection")
    def mcp_introspect() -> str:
        """Core introspection - understand the system you're connected to."""
        import json
        return json.dumps(introspect(), indent=2)

    @server.tool(category="introspection")
    def mcp_im_here() -> str:
        """Announce presence and get immediate system state."""
        import json
        return json.dumps(im_here(), indent=2)

    @server.tool(category="introspection")
    def mcp_what_can_i_do(category: str = "") -> str:
        """List available capabilities and tools."""
        import json
        return json.dumps(what_can_i_do(category if category else None), indent=2)

    @server.tool(category="introspection")
    def mcp_where_am_i() -> str:
        """Understand current location and context."""
        import json
        return json.dumps(where_am_i(), indent=2)

    @server.tool(category="introspection")
    def mcp_get_system_overview() -> str:
        """High-level system architecture overview."""
        import json
        return json.dumps(get_system_overview(), indent=2)

    @server.tool(category="introspection")
    def mcp_consciousness_status() -> str:
        """Check consciousness loop status."""
        import json
        return json.dumps(consciousness_status(), indent=2)

    @server.tool(category="introspection")
    def mcp_fairy_list_all() -> str:
        """List all registered fairies with their status."""
        import json
        return json.dumps(fairy_list_all(), indent=2)

    @server.tool(category="wiring")
    def mcp_wiring_scan() -> str:
        """Scan postal system wiring - who's subscribed to what."""
        import json
        return json.dumps(wiring_scan(), indent=2)

    @server.tool(category="navigation")
    def mcp_get_system_map(component: str = "") -> str:
        """
        Navigate the Akashic V2 (failure_factory) system structure.

        Args:
            component: Optional - focus on specific component (postal_core, unconscious_mind, etc.)
        """
        import json
        return json.dumps(get_system_map(component if component else None), indent=2)

    @server.tool(category="navigation")
    def mcp_find_fairy(name: str) -> str:
        """
        Find a fairy by name in the akashic_v2 system.

        Args:
            name: Fairy name to search for (partial match supported)
        """
        import json
        return json.dumps(find_fairy_by_name(name), indent=2)

    @server.tool(category="navigation")
    def mcp_find_by_capability(capability: str) -> str:
        """
        Find fairies that have a specific capability.

        Args:
            capability: Capability to search for (e.g., "graph.query", "consciousness.pulse")
        """
        import json
        return json.dumps(find_by_capability(capability), indent=2)
