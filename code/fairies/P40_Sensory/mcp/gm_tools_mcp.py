"""
MCP GM Tools - Expose GM functions to Claude via MCP

These tools let Claude query and observe the Akashic world.
Uses file-based communication for cross-process reads since
the fairies run in server.py, not the MCP subprocess.

Strategy:
1. Send command via postal tunnel -> server.py writes to state/gm/
2. MCP reads from state/gm/ files
3. Return results to Claude
"""

import sys
import json
import time
from pathlib import Path

# Add project root
# Path: fairies/P40_Sensory/mcp -> parent.parent.parent.parent = akashic_v2 (project root)
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root))

STATE_DIR = _project_root / "state" / "gm"


def _get_production_directory():
    """Get the PRODUCTION DirectoryFairy instance (directory/fairy.py).

    FIX 2026-02-06: Consolidation — use the production DirectoryFairy which has:
    - FairyRegistry with thread-safe routing tables
    - HeartbeatHandler with death detection
    - CapabilityIndex for capability routing
    - TensorFabric integration
    - Full postal backbone (Phase 2 routing)

    Falls back to the P00 Organ Template version if production isn't available.
    """
    # Try production DirectoryFairy first (the one that boots with the system)
    try:
        from directory.fairy import get_directory
        directory = get_directory()
        if directory:
            return directory
    except ImportError:
        pass

    # Fallback: P00 Organ Template version (simple Directory class)
    try:
        from fairies.P00_Autonomic.DirectoryFairy import get_directory_fairy
        return get_directory_fairy()
    except ImportError:
        pass

    return None


def register_gm_tools(mcp):
    """Register GM tools with the MCP server."""

    @mcp.tool()
    def gm_world_status() -> str:
        """
        Get comprehensive world status snapshot.

        Shows:
        - Fairy registry (from DirectoryFairy)
        - Postal system stats
        - Consciousness loop state

        Returns:
            JSON with full world status
        """
        # PRIORITY 1: Read from heartbeat file (written by server.py every 30s)
        heartbeat_path = _project_root / "state" / "mcp_heartbeat.json"
        try:
            if heartbeat_path.exists():
                heartbeat = json.loads(heartbeat_path.read_text())
                age = time.time() - heartbeat.get("ts", 0)

                # Only use if fresh (< 120 seconds old)
                if age < 120:
                    registry = heartbeat.get("registry", {})
                    postal = heartbeat.get("postal", {})
                    consciousness = heartbeat.get("consciousness", {})

                    result = {
                        "ts": heartbeat.get("ts"),
                        "ts_human": heartbeat.get("ts_human"),
                        "source": "heartbeat_file",
                        "_age_seconds": round(age, 1),
                        "booted": heartbeat.get("booted", False),
                        "uptime": heartbeat.get("uptime", 0),
                        "registry": registry,
                        "postal": postal,
                        "consciousness": consciousness,
                        "working_memory": heartbeat.get("working_memory"),
                        "somatic": heartbeat.get("somatic"),
                    }

                    # Include UMF summary if available
                    umf = heartbeat.get("umf", {})
                    if umf and isinstance(umf, dict) and "error" not in umf:
                        result["umf_fairy"] = umf.get("fairy", {})
                        result["umf_drives"] = umf.get("drives", {})
                        result["umf_gates"] = umf.get("gates", {})

                    return json.dumps(result, indent=2, default=str)
        except Exception:
            pass  # Fall through to legacy method

        # PRIORITY 2: Trigger tunnel refresh + read from gm/world_status.json
        _trigger_status_refresh()

        status_file = STATE_DIR / "world_status.json"
        if status_file.exists():
            try:
                status = json.loads(status_file.read_text())
                age = time.time() - status.get("ts", 0)
                status["_age_seconds"] = round(age, 1)
                status["source"] = "world_status_file"
                return json.dumps(status, indent=2)
            except Exception as e:
                return json.dumps({"error": f"Failed to read status: {e}"})

        return json.dumps({"error": "No world status available. Server.py heartbeat not running and no fallback file found."})

    @mcp.tool()
    def gm_list_fairies() -> str:
        """
        List all registered fairies from DirectoryFairy.

        Returns:
            JSON with fairy list, count, and source
        """
        # Try reading registry.json directly
        reg_paths = [
            _project_root / "diaries" / "P00.Directory" / "directory" / "registry.json",  # Fixed: was P0
            _project_root / "config" / "registry.json",
            _project_root / "registry.json",
        ]

        for reg_path in reg_paths:
            if reg_path.exists():
                try:
                    data = json.loads(reg_path.read_text())
                    if isinstance(data, dict):
                        if "organs" in data:
                            fairies = list(data["organs"].values())
                        else:
                            fairies = list(data.values())

                        summary = []
                        for f in fairies:
                            if isinstance(f, dict):
                                summary.append({
                                    "name": f.get("actor_name", f.get("name", "?")),
                                    "plane": f.get("plane", "?"),
                                    "channel": f.get("channel", "?"),
                                    "purpose": f.get("purpose", "")[:80],
                                })

                        return json.dumps({
                            "source": str(reg_path),
                            "count": len(summary),
                            "fairies": summary,
                        }, indent=2)
                except:
                    continue

        # Fallback: read from world_status
        status_file = STATE_DIR / "world_status.json"
        if status_file.exists():
            try:
                status = json.loads(status_file.read_text())
                return json.dumps(status.get("registry", {"error": "No registry in status"}), indent=2)
            except:
                pass

        return json.dumps({"error": "Could not find registry. Run gm_list_fairies() in server."})

    @mcp.tool()
    def gm_inject_tracer() -> str:
        """
        Inject iodine tracer into consciousness circulation.

        Sends tracer through all postal entry points.
        Then use gm_read_circulation() to see where it flowed.

        Returns:
            JSON with tracer_id and injection status
        """
        import uuid
        tracer_id = f"mcp_{uuid.uuid4().hex[:8]}"

        # Send injection command via tunnel
        result = _send_tunnel_command("gm.inject_tracer", {"tracer_id": tracer_id})

        if result:
            return json.dumps({"ok": True, "tracer_id": tracer_id, "message": "Tracer injected. Wait a few seconds, then call gm_read_circulation()"})

        # Direct injection via postal if tunnel fails
        try:
            from fairies.P00_Autonomic.gm_tools import gm_inject_tracer as _inject
            tid = _inject(tracer_id)
            return json.dumps({"ok": True, "tracer_id": tid, "method": "direct"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def gm_read_circulation() -> str:
        """
        Read circulation map after tracer injection.

        Shows where the tracer flowed through the system.

        Returns:
            JSON with touches, latencies, and flow analysis
        """
        circ_file = STATE_DIR / "circulation_map.json"
        if circ_file.exists():
            try:
                cmap = json.loads(circ_file.read_text())

                # Add analysis
                if cmap.get("touches"):
                    cmap["analysis"] = {
                        "total_touches": len(cmap["touches"]),
                        "unique_locations": len(set(t["location"] for t in cmap["touches"])),
                        "total_latency_ms": cmap["touches"][-1]["latency_ms"],
                        "flow_path": [t["location"] for t in cmap["touches"]],
                    }

                return json.dumps(cmap, indent=2)
            except Exception as e:
                return json.dumps({"error": f"Failed to read circulation: {e}"})

        return json.dumps({"error": "No circulation data. Call gm_inject_tracer() first."})

    @mcp.tool()
    def gm_postal_stats() -> str:
        """
        Get postal hub statistics.

        Shows topic subscriptions, message counts, handlers.

        Returns:
            JSON with postal system stats
        """
        # PRIORITY 1: Use postal tunnel to query server's REAL stats
        # This is THE correct way - MCP runs in a separate process with its own hub
        try:
            from .postal_tunnel import get_postal_tunnel_client, is_tunnel_available
            if is_tunnel_available():
                tunnel = get_postal_tunnel_client()
                if tunnel:
                    stats = tunnel.get_stats()
                    if stats:
                        stats["source"] = "server_tunnel"
                        return json.dumps(stats, indent=2)
        except Exception as e:
            pass  # Fall through to other methods

        # PRIORITY 2: Try from world_status file (stale but better than nothing)
        status_file = STATE_DIR / "world_status.json"
        if status_file.exists():
            try:
                status = json.loads(status_file.read_text())
                if "postal" in status:
                    status["postal"]["source"] = "world_status_file"
                    return json.dumps(status["postal"], indent=2)
            except:
                pass

        # PRIORITY 3: Local hub stats (WARNING: This is MCP's hub, not server's!)
        try:
            from fairies.P00_Autonomic.gm_tools import gm_postal_stats as _stats
            result = _stats()
            result["warning"] = "Stats from MCP's LOCAL hub - not server's real hub"
            result["source"] = "mcp_local"
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e), "source": "failed"})

    @mcp.tool()
    def gm_lookup_fairy(fairy_name: str) -> str:
        """
        Look up a specific fairy's contract details.

        Args:
            fairy_name: Actor name (e.g., "ConsciousnessLoopFairy")

        Returns:
            JSON with fairy contract or error
        """
        # Try registry file
        reg_paths = [
            _project_root / "diaries" / "P00.Directory" / "directory" / "registry.json",  # Fixed: was P0
            _project_root / "config" / "registry.json",
            _project_root / "registry.json",
        ]

        for reg_path in reg_paths:
            if reg_path.exists():
                try:
                    data = json.loads(reg_path.read_text())
                    if isinstance(data, dict):
                        if "organs" in data:
                            data = data["organs"]
                        contract = data.get(fairy_name)
                        if contract:
                            return json.dumps({"ok": True, "contract": contract}, indent=2)
                except:
                    continue

        return json.dumps({"ok": False, "error": f"Fairy '{fairy_name}' not found in registry"})

    @mcp.tool()
    def gm_command(fairy_name: str, intent: str, payload: str = "{}") -> str:
        """
        Send a command to a fairy via postal intent.

        Args:
            fairy_name: Target fairy actor name
            intent: Intent to invoke (e.g., "get_stream_snapshot")
            payload: JSON payload string

        Returns:
            JSON with intent result
        """
        try:
            payload_dict = json.loads(payload)
        except:
            payload_dict = {}

        # Send via tunnel
        result = _send_tunnel_command("use_intent", {
            "actor": fairy_name,
            "intent": intent,
            "payload": payload_dict,
        })

        if result:
            return json.dumps(result, indent=2)

        return json.dumps({"error": "Command failed - tunnel may not be connected"})

    # Register directory watchdog tools (defined below)
    register_directory_tools(mcp)


def _trigger_status_refresh():
    """Ask server.py to refresh world status via tunnel."""
    try:
        _send_tunnel_command("gm.world_status", {})
    except:
        pass

def _send_tunnel_command(topic: str, payload: dict) -> dict:
    """Send command through postal tunnel to server.py."""
    try:
        # Get tunnel port
        port_file = _project_root / "state" / "postal_tunnel_port.txt"
        if not port_file.exists():
            return None

        port = int(port_file.read_text().strip())

        # Connect and send
        from .postal_tunnel import PostalTunnelClient
        client = PostalTunnelClient(port)
        if client.connect():
            client.route(topic, payload)
            client.close()
            return {"ok": True, "sent": topic}
        return None
    except Exception as e:
        return None


# ==============================================================================
# DIRECTORY WATCHDOG GM TOOLS
# ==============================================================================
# NOTE: These tools are registered via register_directory_tools() below.
# They cannot be decorated at module level because 'mcp' doesn't exist here.
# ==============================================================================

def _read_status_dump() -> dict:
    """Read system state from file — the shared state written by server.py.

    Priority:
    1. mcp_heartbeat.json (written every 30s by heartbeat thread)
    2. status_dump.json (also updated by heartbeat, legacy path)

    FIX 2026-02-06: MCP process doesn't share memory with server.py.
    FIX 2026-02-12: Use heartbeat file as primary source (always fresh).
    """
    import os

    # Try heartbeat first (most reliable)
    heartbeat_path = _project_root / "state" / "mcp_heartbeat.json"
    if heartbeat_path.exists():
        try:
            data = json.loads(heartbeat_path.read_text(encoding="utf-8"))
            data["_file_age_sec"] = round(time.time() - os.path.getmtime(heartbeat_path), 1)
            data["_source"] = "mcp_heartbeat.json"
            return data
        except Exception:
            pass

    # Fallback to status_dump.json
    status_path = _project_root / "state" / "status_dump.json"
    if not status_path.exists():
        return {}
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
        data["_file_age_sec"] = round(time.time() - os.path.getmtime(status_path), 1)
        data["_source"] = "status_dump.json"
        return data
    except Exception:
        return {}


def _read_death_data() -> dict:
    """Read fairy death data from state files."""
    result = {"deaths": [], "summary": ""}

    # Read death summary
    summary_path = _project_root / "state" / "death_summary.txt"
    if summary_path.exists():
        try:
            result["summary"] = summary_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    # Read recent deaths from JSONL (last 50 entries)
    deaths_path = _project_root / "state" / "fairy_deaths.jsonl"
    if deaths_path.exists():
        try:
            lines = deaths_path.read_text(encoding="utf-8").strip().split("\n")
            # Only DEATH events (not STALE)
            for line in lines[-200:]:
                try:
                    entry = json.loads(line)
                    if entry.get("event") == "FAIRY_DEATH":
                        result["deaths"].append(entry)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    return result


def register_directory_tools(mcp):
    """Register directory watchdog tools. Called from register_gm_tools."""

    @mcp.tool()
    async def gm_directory_status() -> str:
        """
        Get DirectoryFairy registration status and watchdog health.

        Shows:
        - Registered fairy count
        - Missing fairies (booted but not registered)
        - Watchdog status and strike counts
        - Last check time

        Returns:
            JSON with directory health status
        """
        try:
            # PRIMARY: Read from state file (works in MCP process)
            status = _read_status_dump()
            if status:
                fairies = status.get("fairies", {})
                telemetry = status.get("telemetry", {})
                result = {
                    "source": "status_dump.json",
                    "file_age_sec": status.get("_file_age_sec", "?"),
                    "registered_count": fairies.get("total", 0),
                    "by_status": {
                        "running": fairies.get("running", 0),
                        "sleeping": fairies.get("sleeping", 0),
                        "waking": fairies.get("waking", 0),
                        "failed": fairies.get("failed", 0),
                    },
                    "health_score": telemetry.get("summary", {}).get("healthScore", 0),
                    "dead_count": len(telemetry.get("deadFairies", [])),
                    "dead_fairies": [f.get("name", "?") for f in telemetry.get("deadFairies", [])],
                    "bad_count": telemetry.get("summary", {}).get("bad", 0),
                    "ugly_count": telemetry.get("summary", {}).get("ugly", 0),
                }
                return json.dumps(result, indent=2, default=str)

            # FALLBACK: Try in-memory access (works when running inside server.py)
            directory = _get_production_directory()
            if directory:
                reg = getattr(directory, 'registry', None)
                if reg and hasattr(reg, 'count'):
                    stats = reg.stats()
                    return json.dumps({
                        "source": "in_memory",
                        "registered_count": reg.count(),
                        "by_status": stats.get("by_status", {}),
                    }, indent=2, default=str)

            return json.dumps({"error": "No status_dump.json and no in-memory DirectoryFairy"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def gm_directory_missing() -> str:
        """
        Get list of fairies that booted but didn't register.

        Returns:
            JSON with missing fairies and their strike counts
        """
        try:
            # Read death data from state files
            death_data = _read_death_data()
            status = _read_status_dump()

            deaths = death_data.get("deaths", [])
            telemetry = status.get("telemetry", {}) if status else {}
            dead_from_dump = telemetry.get("deadFairies", [])

            result = {
                "source": "state_files",
                "dead_count": len(dead_from_dump) if dead_from_dump else len(deaths),
                "dead_fairies": (
                    [{"name": f.get("name", "?"), "plane": f.get("plane", "?")} for f in dead_from_dump]
                    if dead_from_dump else
                    [{"name": d.get("fairy", "?"), "plane": d.get("plane", "?"),
                      "silence_seconds": round(d.get("silence_seconds", 0), 1),
                      "timestamp": d.get("timestamp", "?")}
                     for d in deaths]
                ),
                "total_registered": status.get("fairies", {}).get("total", 0) if status else "?",
                "summary": death_data.get("summary", ""),
            }
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def gm_directory_census() -> str:
        """
        Trigger a census - ask all fairies to re-register.

        Use this to recover missing registrations.

        Returns:
            JSON with census trigger status
        """
        try:
            # Send census request via postal tunnel to server.py
            result = _send_tunnel_command("fairy.census.request", {
                "reason": "gm_tool_request",
                "ts": time.time(),
            })
            if result:
                return json.dumps({"status": "census_broadcast_sent",
                                   "note": "Published fairy.census.request via tunnel"})

            # Fallback: try in-memory
            directory = _get_production_directory()
            if directory:
                fabric = getattr(directory, 'fabric', None)
                if fabric:
                    fabric.publish("fairy.census.request", {
                        "reason": "gm_tool_request",
                        "ts": time.time(),
                    })
                    return json.dumps({"status": "census_broadcast_sent",
                                       "note": "Published via in-memory fabric"})

            return json.dumps({"error": "No tunnel or in-memory fabric available"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def gm_directory_force_check() -> str:
        """
        Force an immediate registration check.

        Returns current status after the check.

        Returns:
            JSON with updated registration status
        """
        try:
            # Read latest state from files
            status = _read_status_dump()
            if status:
                fairies = status.get("fairies", {})
                telemetry = status.get("telemetry", {})
                boot = status.get("boot", {}) if "boot" in status else (
                    status.get("umf", {}).get("boot", {}) if "umf" in status else {}
                )
                dead_list = telemetry.get("deadFairies", [])
                return json.dumps({
                    "source": "status_dump.json",
                    "file_age_sec": status.get("_file_age_sec", "?"),
                    "total_registered": fairies.get("total", 0),
                    "by_status": {
                        "running": fairies.get("running", 0),
                        "sleeping": fairies.get("sleeping", 0),
                        "failed": fairies.get("failed", 0),
                    },
                    "dead_count": len(dead_list),
                    "dead_fairies": [f.get("name", "?") for f in dead_list],
                    "boot_complete": boot.get("is_complete", "?") if boot else "?",
                    "health_score": telemetry.get("summary", {}).get("healthScore", 0),
                }, indent=2, default=str)

            # Fallback
            directory = _get_production_directory()
            if directory:
                reg = getattr(directory, 'registry', None)
                if reg and hasattr(reg, 'count'):
                    stats = reg.stats()
                    dead = reg.list_dead()
                    return json.dumps({
                        "source": "in_memory",
                        "total_registered": reg.count(),
                        "by_status": stats.get("by_status", {}),
                        "dead_count": len(dead),
                        "dead_fairies": [f.name for f in dead],
                    }, indent=2, default=str)

            return json.dumps({"error": "No status_dump.json and no in-memory DirectoryFairy"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def gm_directory_request_missing() -> str:
        """
        Request missing fairies to re-register (targeted, not broadcast).

        This directly calls _register_with_directory() on each missing fairy.

        Returns:
            JSON with re-registration results
        """
        try:
            # Read death data
            death_data = _read_death_data()
            status = _read_status_dump()

            deaths = death_data.get("deaths", [])
            telemetry = status.get("telemetry", {}) if status else {}
            dead_list = telemetry.get("deadFairies", [])

            dead_names = [f.get("name", "?") for f in dead_list] if dead_list else [
                d.get("fairy", "?") for d in deaths
            ]

            if not dead_names:
                return json.dumps({
                    "status": "all_healthy",
                    "dead_count": 0,
                    "total_registered": status.get("fairies", {}).get("total", 0) if status else "?",
                    "message": "No dead fairies found. All registered fairies are running.",
                }, indent=2)

            # Try sending re-registration request via tunnel
            result = _send_tunnel_command("fairy.reregister.request", {
                "fairies": dead_names,
                "reason": "gm_tool_request",
                "ts": time.time(),
            })

            return json.dumps({
                "dead_count": len(dead_names),
                "dead_fairies": dead_names,
                "tunnel_sent": result is not None,
                "suggestion": "Dead fairies may need a system restart to recover.",
            }, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def gm_fairy_audit() -> str:
        """
        Comprehensive audit of all fairies showing multiple health dimensions.

        Returns for each fairy:
        - registration_complete: Are all required fields filled?
        - using_defaults: Is it using template default values?
        - has_system_prompt: Does it have a custom system prompt?
        - evolution_enabled: Is it configured to evolve?
        - has_shadow: Does it have shadow health monitoring?
        - has_subscriptions: Does it subscribe to postal topics?
        - has_intents: Does it expose intents?
        - plane_channel_valid: Is plane/channel properly set?

        Returns:
            JSON with audit results sorted by health score (worst first)
        """
        try:
            from fairies.P00_Autonomic.gm_tools import gm_fairy_audit as _audit
            result = _audit()
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def gm_missing_fairies() -> str:
        """
        Compare registered fairies against expected/booted fairies.

        Shows which fairies booted but didn't register.
        Helps identify registration failures.

        Returns:
            JSON with registered, booted, and missing fairy lists
        """
        try:
            from fairies.P00_Autonomic.gm_tools import gm_missing_fairies as _missing
            result = _missing()
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})


# ════════════════════════════════════════════════════════════════════════════════
# UNIFIED CITIZEN REGISTRY TOOLS
# "Every waking mind is a first-class citizen"
# ════════════════════════════════════════════════════════════════════════════════

def register_citizen_tools(mcp):
    """Register Unified Citizen Registry tools with MCP."""

    @mcp.tool()
    def gm_citizen_registry_status() -> str:
        """
        Get Unified Citizen Registry status.

        Shows:
        - Total citizens registered
        - Citizens by type (human, waking_mind, fairy, tool)
        - Online citizens
        - Health monitor status
        - Whether we're in embedded mode (shared singleton)

        Returns:
            JSON with registry status
        """
        import os
        embedded = os.environ.get("AKASHIC_EMBEDDED_MCP", "") == "1"

        try:
            from fairies.P00_Autonomic.unified_citizen_wiring import get_unified_registry
            registry = get_unified_registry()

            # Get directory info
            directory = registry.get_directory()
            health = registry.get_health_report()

            return json.dumps({
                "embedded_mode": embedded,
                "singleton_id": id(registry),
                "total_citizens": directory.get("total", 0),
                "by_type": directory.get("by_type", {}),
                "waking_minds": directory.get("waking_minds", []),
                "founder": directory.get("founder"),
                "online_count": health.get("online", 0),
                "healthy_count": health.get("healthy", 0),
                "health_monitor_active": registry._monitor_running,
                "note": "Shared singleton - same as server" if embedded else "Separate process - may differ from server"
            }, indent=2)
        except ImportError as e:
            return json.dumps({"error": f"Module not available: {e}", "embedded_mode": embedded})
        except Exception as e:
            return json.dumps({"error": str(e), "embedded_mode": embedded})

    @mcp.tool()
    def gm_citizen_list(citizen_type: str = "") -> str:
        """
        List all citizens in the registry.

        Args:
            citizen_type: Optional filter - "human", "waking_mind", "fairy", "tool"

        Returns:
            JSON list of citizens with their status
        """
        try:
            from fairies.P00_Autonomic.unified_citizen_wiring import (
                get_unified_registry,
                CitizenType,
            )
            registry = get_unified_registry()

            if citizen_type:
                try:
                    ct = CitizenType(citizen_type)
                    citizens = registry.get_by_type(ct)
                except ValueError:
                    return json.dumps({"error": f"Invalid type: {citizen_type}. Use: human, waking_mind, fairy, tool"})
            else:
                citizens = list(registry._citizens.values())

            result = []
            for c in citizens:
                result.append({
                    "citizen_id": c.citizen_id,
                    "name": c.name,
                    "display_name": c.display_name,
                    "type": c.citizen_type.value,
                    "plane": c.plane,
                    "status": c.presence.status.value,
                    "is_reachable": c.presence.is_reachable(),
                    "health_score": c.get_health_score(),
                    "tracer_id": c.tracer_id,
                })

            return json.dumps({
                "count": len(result),
                "filter": citizen_type or "all",
                "citizens": result
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def gm_citizen_get(name: str) -> str:
        """
        Get a specific citizen by name.

        Args:
            name: Name of the citizen (e.g., "Ace", "ClaudeFairy")

        Returns:
            JSON with full citizen info
        """
        try:
            from fairies.P00_Autonomic.unified_citizen_wiring import get_unified_registry
            registry = get_unified_registry()

            citizen = registry.get_by_name(name)
            if not citizen:
                return json.dumps({
                    "error": f"Citizen '{name}' not found",
                    "registered_names": list(registry._by_name.keys())
                })

            # Full citizen dump
            result = citizen.to_dict()
            result["health_probes"] = citizen.health.to_dict() if citizen.health else None

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def gm_citizen_health_report() -> str:
        """
        Get comprehensive health report for all citizens.

        Probes all citizens for liveness, readiness, and tracer status.

        Returns:
            JSON with health report
        """
        try:
            from fairies.P00_Autonomic.unified_citizen_wiring import get_unified_registry
            registry = get_unified_registry()

            report = registry.get_health_report()
            return json.dumps(report, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})
