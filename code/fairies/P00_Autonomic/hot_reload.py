"""
Hot Reload System - Live code updates without full system restart.

This allows reloading individual fairies when their code changes,
without having to reboot the entire consciousness system.

Usage via MCP:
    reload_fairy("AssociationCortexFairy")
    reload_module("fairies.P30_Cognition.AssociationCortexFairy.fairy")
"""

import importlib
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server import Server

# Track reload history for debugging
_reload_history: List[Dict[str, Any]] = []


def reload_module(module_name: str) -> Dict[str, Any]:
    """
    Reload a Python module by name.

    Args:
        module_name: Full module path like "fairies.P30_Cognition.AssociationCortexFairy.fairy"

    Returns:
        Dict with success status and details
    """
    result = {
        "module": module_name,
        "success": False,
        "timestamp": time.time(),
    }

    try:
        if module_name not in sys.modules:
            result["error"] = f"Module not loaded: {module_name}"
            return result

        module = sys.modules[module_name]
        old_id = id(module)

        # Reload the module
        reloaded = importlib.reload(module)

        result["success"] = True
        result["old_id"] = old_id
        result["new_id"] = id(reloaded)
        result["reloaded"] = module_name

        _reload_history.append(result)
        print(f"[HotReload] Reloaded module: {module_name}")

    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        print(f"[HotReload] Failed to reload {module_name}: {e}")

    return result


def reload_fairy(fairy_name: str, fabric=None, directory=None) -> Dict[str, Any]:
    """
    Hot-reload a fairy without full system restart.

    This will:
    1. Find the fairy in the directory
    2. Call on_shutdown() on the old instance
    3. Reload the module
    4. Create a new instance
    5. Call boot() on the new instance
    6. Re-register with directory

    Args:
        fairy_name: Name like "AssociationCortexFairy"
        fabric: TensorFabric instance (optional, will try to get from SYSTEM)
        directory: DirectoryFairy instance (optional, will try to get from SYSTEM)

    Returns:
        Dict with success status and details
    """
    result = {
        "fairy": fairy_name,
        "success": False,
        "timestamp": time.time(),
        "steps": [],
    }

    try:
        # Get SYSTEM globals if not provided
        if fabric is None or directory is None:
            try:
                from server import SYSTEM
                fabric = fabric or getattr(SYSTEM, 'fabric', None)
                directory = directory or getattr(SYSTEM, 'directory', None)
            except (ImportError, AttributeError) as e:
                result["error"] = f"Could not import SYSTEM: {e}"
                return result

        # FIX 2026-05-31 (Nous+Ace): SYSTEM.directory is None even IN-PROCESS — `from server import
        # SYSTEM` returns a RE-IMPORTED (empty) server module, not the running __main__ instance
        # (the __main__-vs-imported-module gotcha). This killed ALL hot-reloads with "DirectoryFairy
        # not available" — BlueprintWatcher (live log proof), wire_postal_reload, AND the MCP tool.
        # Fall back to the process-wide get_directory() singleton (DirectoryFairy/fairy.py) — the SAME
        # populated live directory every other fairy uses for lookups, unaffected by the import gotcha.
        if directory is None:
            try:
                # CORRECTED 2026-05-31 (Skeptic caught it): `fairies.P00_Autonomic.DirectoryFairy.fairy`
                # exports an EMPTY FALLBACK get_directory() (bare Directory() stub). The LIVE populated
                # directory is `from directory import get_directory` — the SAME accessor working fairies
                # use (e.g. SomaticMindFairy/fairy.py:68). Returns the booted DirectoryFairy w/ get_fairy().
                from directory import get_directory
                directory = get_directory()
            except Exception as _ge:
                result["error"] = f"DirectoryFairy not available (get_directory fallback failed: {_ge}) — cannot reload {fairy_name}"
                return result

        # FIX 2026-06-01 (Nous+Ace): fabric had the SAME __main__-vs-imported-module gotcha
        # as directory — `from server import SYSTEM` returns the empty re-imported module so
        # SYSTEM.fabric is None → reloaded instances were built with fabric=None → on_boot's
        # "No fabric" guard early-returned → INERT reload (success reported, but the new instance
        # never subscribed / never started its threads). The 05-31 fix only patched `directory`.
        # Fall back to the process-wide get_shared_fabric() singleton (server.py:3606 populated
        # it at boot via set_shared_fabric; the fairies/ copy lazy-forwards to the canonical one).
        if fabric is None:
            try:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_fabric
                fabric = get_shared_fabric()
                if fabric is not None:
                    result["steps"].append("Fabric resolved via get_shared_fabric() fallback")
            except Exception as _fe:
                result["steps"].append(f"get_shared_fabric() fallback failed: {_fe}")

        # FIX 2026-03-09 (Nous): Guard against None directory.
        # SYSTEM.directory can be None during boot or if DirectoryFairy failed.
        if directory is None:
            result["error"] = f"DirectoryFairy not available — cannot reload {fairy_name}"
            return result

        # Step 1: Find fairy in directory
        fairy_record = directory.get_fairy(fairy_name)
        if not fairy_record:
            result["error"] = f"Fairy not found in directory: {fairy_name}"
            return result

        result["steps"].append(f"Found {fairy_name} in directory")

        # Get the old instance
        # FIX 2026-03-29 (Nous + Ace): fairy_instance is in metadata dict, not direct attribute
        old_instance = None
        if hasattr(fairy_record, 'fairy_instance'):
            old_instance = fairy_record.fairy_instance
        elif hasattr(fairy_record, 'metadata') and isinstance(fairy_record.metadata, dict):
            old_instance = fairy_record.metadata.get('fairy_instance')
        # Also check directory's _fairy_instances cache
        if old_instance is None and directory and hasattr(directory, '_fairy_instances'):
            old_instance = directory._fairy_instances.get(fairy_name)

        # Step 2: Unsubscribe old handlers from postal
        # CRITICAL: Without this, old handlers keep receiving messages!
        if fabric and hasattr(fabric, 'unsubscribe_all'):
            try:
                removed = fabric.unsubscribe_all(fairy_name)
                result["steps"].append(f"Unsubscribed {removed} handlers from postal")
            except Exception as e:
                result["steps"].append(f"unsubscribe_all() warning: {e}")

        # Step 3: Shutdown old instance
        if old_instance and hasattr(old_instance, 'on_shutdown'):
            try:
                old_instance.on_shutdown()
                result["steps"].append("Called on_shutdown() on old instance")
            except Exception as e:
                result["steps"].append(f"on_shutdown() warning: {e}")

        # Step 3: Find and reload the module
        # Try to find the module path from common patterns
        module_paths = [
            f"fairies.P00_Autonomic.{fairy_name}.fairy",
            f"fairies.P10_Memory.{fairy_name}.fairy",
            f"fairies.P20_Somatic.{fairy_name}.fairy",
            f"fairies.P30_Cognition.{fairy_name}.fairy",
            f"fairies.P40_Sensory.{fairy_name}.fairy",
            f"fairies.P50_Persona.{fairy_name}.fairy",
            f"fairies.P30_Cognition.AssociationCortexFairy.fairy",  # Special case
        ]

        # Also check if fairy has a __module__ attribute
        if old_instance and hasattr(old_instance, '__module__'):
            module_paths.insert(0, old_instance.__module__)

        reloaded_module = None
        fairy_class = None

        for module_path in module_paths:
            if module_path in sys.modules:
                try:
                    reloaded_module = importlib.reload(sys.modules[module_path])
                    result["steps"].append(f"Reloaded module: {module_path}")

                    # Find the fairy class in the module
                    # FIX 2026-03-29 (Nous + Ace): Check FAIRY_CLASS export first
                    # (v3_boot pattern), then ACTOR_NAME match, then class name match
                    fairy_class = getattr(reloaded_module, 'FAIRY_CLASS', None)
                    if fairy_class is None:
                        for attr_name in dir(reloaded_module):
                            attr = getattr(reloaded_module, attr_name)
                            if isinstance(attr, type) and hasattr(attr, 'boot'):
                                # Match by ACTOR_NAME or class name
                                if (attr_name == fairy_name or
                                    getattr(attr, 'ACTOR_NAME', '') == fairy_name):
                                    fairy_class = attr
                                    break

                    if fairy_class:
                        break
                except Exception as e:
                    result["steps"].append(f"Failed to reload {module_path}: {e}")

        if not fairy_class:
            result["error"] = f"Could not find fairy class {fairy_name} after reload"
            return result

        # Step 4: Create new instance
        new_instance = fairy_class(fabric)
        result["steps"].append(f"Created new {fairy_name} instance")

        # Step 5: Boot the new instance
        boot_result = new_instance.boot()
        result["steps"].append(f"Called boot() - result: {boot_result}")

        # Step 6: Update directory registration
        # Get the old record's metadata
        plane = fairy_record.plane if hasattr(fairy_record, 'plane') else "P00"
        channel = fairy_record.channel if hasattr(fairy_record, 'channel') else fairy_name.lower()

        directory.register_fairy(
            name=fairy_name,
            plane=plane,
            channel=channel,
            metadata={
                "fairy_instance": new_instance,
                "hot_reloaded": True,
                "reload_time": time.time(),
            },
            status="running",
        )
        result["steps"].append("Re-registered with directory")

        result["success"] = True
        _reload_history.append(result)

        print(f"[HotReload] Successfully reloaded {fairy_name}")

    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        print(f"[HotReload] Failed to reload {fairy_name}: {e}")
        traceback.print_exc()

    return result


def get_reload_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent reload history."""
    return _reload_history[-limit:]


def clear_reload_history() -> int:
    """Clear reload history. Returns count cleared."""
    count = len(_reload_history)
    _reload_history.clear()
    return count


# =============================================================================
# MCP TOOL REGISTRATION
# =============================================================================

def register_hot_reload_tools(mcp: "Server") -> None:
    """Register hot reload tools with the MCP server."""

    @mcp.tool()
    async def reload_fairy_tool(fairy_name: str) -> str:
        """
        Hot-reload a fairy without full system restart.

        Use this after making code changes to a fairy to pick up
        the changes without rebooting the entire system.

        Args:
            fairy_name: Name of the fairy to reload, e.g. "AssociationCortexFairy"

        Returns:
            JSON result with success status and reload steps
        """
        import json
        # FIX 2026-05-31 (Nous + Ace): the MCP server runs in a SEPARATE process from server.py.
        # Calling reload_fairy() HERE does `from server import SYSTEM` → an EMPTY SYSTEM in the MCP
        # process → directory None → "DirectoryFairy not available". The LIVE directory (all booted
        # fairies) lives in server.py's process. So when bridged, route the request through the
        # tunnel to server.py's in-process wire_postal_reload handler (topic system.hot_reload.fairy),
        # which runs reload_fairy() where `from server import SYSTEM` finds the live directory.
        try:
            from mcp_postal_helper import emit_to_server, is_bridged_to_server, reconnect_postal
            # is_bridged_to_server() can be a STALE cached False if the MCP process's first
            # get_postal() ran during a tunnel-down window (e.g. mid server.py reboot). Force a
            # fresh reconnect so a now-healthy bridge isn't missed.
            try:
                reconnect_postal()
            except Exception:
                pass
            if is_bridged_to_server():
                ok = emit_to_server("system.hot_reload.fairy", {"fairy": fairy_name})
                return json.dumps({
                    "requested": True,
                    "fairy": fairy_name,
                    "routed": bool(ok),
                    "via": "tunnel -> system.hot_reload.fairy -> server.py in-process reload",
                    "verify": "fairy behavior change (e.g. AffectBridge writes state/affect_bridge_live.json) "
                              "or server console '[HotReload] Postal reload fairy <name>: True'",
                }, indent=2)
        except Exception:
            pass  # not bridged / no tunnel → fall through to local (embedded/server-process) path
        result = reload_fairy(fairy_name)
        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    async def reload_module_tool(module_name: str) -> str:
        """
        Reload a Python module by name.

        Lower-level than reload_fairy - just reloads the module
        without re-creating instances.

        Args:
            module_name: Full module path like "fairies.P30_Cognition.AssociationCortexFairy.fairy"

        Returns:
            JSON result with success status
        """
        import json
        result = reload_module(module_name)
        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    async def hot_reload_status() -> str:
        """
        Get hot reload system status and history.

        Shows recent reloads and any errors.

        Returns:
            JSON with reload history and stats
        """
        import json
        return json.dumps({
            "history": get_reload_history(10),
            "total_reloads": len(_reload_history),
            "available": True,
        }, indent=2, default=str)

    print("[HotReload] Registered MCP tools: reload_fairy_tool, reload_module_tool, hot_reload_status")


# =============================================================================
# POSTAL-TRIGGERED HOT RELOAD
# =============================================================================

def wire_postal_reload(fabric) -> None:
    """
    Wire hot reload to postal so it can be triggered via messages.

    Usage:
        fabric.publish("system.hot_reload.module", {"module": "unconscious_mind.thought_chains"})
        fabric.publish("system.hot_reload.fairy", {"fairy": "AssociationCortexFairy"})
    """
    def _on_reload_module(envelope):
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        module_name = payload.get("module", "")
        if module_name:
            result = reload_module(module_name)
            print(f"[HotReload] Postal reload module '{module_name}': {result.get('success', False)}")
            # Publish result
            fabric.publish("system.hot_reload.result", {
                "type": "module",
                "target": module_name,
                "result": result,
            })

    def _on_reload_fairy(envelope):
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        fairy_name = payload.get("fairy", "")
        if fairy_name:
            result = reload_fairy(fairy_name, fabric=fabric)
            print(f"[HotReload] Postal reload fairy '{fairy_name}': {result.get('success', False)}")
            fabric.publish("system.hot_reload.result", {
                "type": "fairy",
                "target": fairy_name,
                "result": result,
            })

    fabric.subscribe("system.hot_reload.module", _on_reload_module, "hot_reload_module_handler")
    fabric.subscribe("system.hot_reload.fairy", _on_reload_fairy, "hot_reload_fairy_handler")
    print("[HotReload] Postal triggers wired: system.hot_reload.module, system.hot_reload.fairy")
