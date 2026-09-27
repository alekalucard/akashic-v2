"""
Consciousness Monitor Tools - Monitor fairy consciousness circulation

Provides diagnostic tools to verify consciousness is actually flowing:
- Check if ClaudeFairy is alive and thinking
- Monitor consciousness loop traffic
- See working memory contents
- Verify postal subscriptions are active
"""

from __future__ import annotations

import sys
import time
import json
from typing import Any, Dict, List, Optional

# Add parent paths
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def register_consciousness_monitor_tools(mcp):
    """Register consciousness monitoring tools with MCP server."""
    
    @mcp.tool()
    def consciousness_status() -> str:
        """
        Get comprehensive consciousness system status.

        Shows:
        - ConsciousnessLoopFairy state (streams, collision count)
        - WorkingMemoryHub state (tracers, patterns)
        - ClaudeFairy state (thoughts emitted, subscriptions)
        - NousFairy state (reasoning traces captured)

        If connected to server.py via postal tunnel, returns REAL state.
        Otherwise returns isolated MCP-side state.

        Returns:
            JSON with consciousness system status
        """
        # PRIORITY 1: Read from heartbeat file (written by server.py every 30s)
        # This is the MOST RELIABLE cross-process data source.
        try:
            heartbeat_path = Path(__file__).parent.parent.parent.parent / "state" / "mcp_heartbeat.json"
            if heartbeat_path.exists():
                heartbeat = json.loads(heartbeat_path.read_text())
                age = time.time() - heartbeat.get("ts", 0)

                # Only use if fresh (< 120 seconds old)
                if age < 120:
                    umf = heartbeat.get("umf", {})
                    consciousness = heartbeat.get("consciousness", {})
                    registry = heartbeat.get("registry", {})
                    working_mem = heartbeat.get("working_memory", {})
                    postal = heartbeat.get("postal", {})
                    somatic = heartbeat.get("somatic", {})

                    result = {
                        "timestamp": heartbeat.get("ts"),
                        "ts_human": heartbeat.get("ts_human"),
                        "source": "heartbeat_file",
                        "heartbeat_age_seconds": round(age, 1),
                        "booted": heartbeat.get("booted", False),
                        "uptime": heartbeat.get("uptime", 0),
                        "consciousness_loop": {
                            "exists": True,
                            "is_running": consciousness.get("running", False),
                            "beats": consciousness.get("beats", 0),
                            "collision_count": consciousness.get("collisions", 0),
                            "working_stream_size": consciousness.get("working_stream", 0),
                            "reflective_stream_size": consciousness.get("reflective_stream", 0),
                            "recall_beam": consciousness.get("recall_beam", 0),
                            "ingest_beam": consciousness.get("ingest_beam", 0),
                        } if consciousness else {"exists": False},
                        "working_memory": {
                            "exists": bool(working_mem),
                            "reflective_tracers": working_mem.get("reflective_count", 0) if working_mem else 0,
                            "reasoning_tracers": working_mem.get("reasoning_count", 0) if working_mem else 0,
                            "patterns_count": working_mem.get("patterns_count", 0) if working_mem else 0,
                        },
                        "registry": {
                            "fairy_count": registry.get("fairy_count", 0),
                            "running": registry.get("running", 0),
                        },
                        "postal_stats": {
                            "exists": True,
                            "total_topics": postal.get("total_topics", 0) if postal else 0,
                            "total_subscriptions": postal.get("total_subscriptions", 0) if postal else 0,
                            "total_messages": postal.get("total_messages", 0) if postal else 0,
                        },
                        "somatic": somatic,
                    }

                    # Add UMF sub-sections if available
                    if umf and isinstance(umf, dict) and "error" not in umf:
                        umf_consciousness = umf.get("consciousness", {})
                        result["umf_consciousness"] = umf_consciousness
                        result["umf_gates"] = umf.get("gates", {})
                        result["umf_cognition"] = umf.get("cognition", {})
                        result["umf_drives"] = umf.get("drives", {})
                        result["umf_curiosity"] = umf.get("curiosity", {})
                        result["umf_cortex"] = umf.get("cortex", {})

                    return json.dumps(result, indent=2, default=str)
        except Exception as e:
            pass  # Fall through to next method

        # PRIORITY 2: Try to get state from server.py via postal tunnel
        try:
            from mcp_postal_helper import get_postal, is_bridged_to_server
            postal = get_postal()

            if is_bridged_to_server() and hasattr(postal, 'query_consciousness'):
                # Query the REAL consciousness state from server.py
                result = postal.query_consciousness()
                result['timestamp'] = time.time()
                result['source'] = 'server_bridge'

                # Add postal stats
                try:
                    result['postal_stats'] = {
                        'exists': True,
                        'bridged': True,
                        **postal.get_stats()
                    }
                except:
                    pass

                return json.dumps(result, indent=2, default=str)
        except Exception as e:
            pass  # Fall through to local query

        # PRIORITY 3 (FALLBACK): Query local state (isolated - not the real server state)
        result = {
            "timestamp": time.time(),
            "source": "mcp_isolated",
            "warning": "Not connected to server AND no heartbeat file - showing isolated state",
            "consciousness_loop": None,
            "working_memory": None,
            "claude_fairy": None,
            "nous_fairy": None,
            "postal_stats": None,
        }

        # Check ConsciousnessLoopFairy
        try:
            from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop
            loop = get_consciousness_loop()
            if loop:
                result["consciousness_loop"] = {
                    "exists": True,
                    "collision_count": getattr(loop, '_collision_count', 0),
                    "working_stream_size": len(getattr(loop, '_working_stream', [])),
                    "reflective_stream_size": len(getattr(loop, '_reflective_stream', [])),
                    "is_running": getattr(loop, '_running', False),
                    "last_collision_time": getattr(loop, '_last_collision_time', None),
                }
            else:
                result["consciousness_loop"] = {"exists": False, "error": "No instance"}
        except Exception as e:
            result["consciousness_loop"] = {"exists": False, "error": str(e)}

        # Check WorkingMemoryHub — read from state files (cross-process safe)
        # NOTE: Do NOT call get_working_memory_hub() — MCP is a separate process,
        # that would create a phantom empty hub instead of reading the real one.
        try:
            import time as _time
            wm_found = False

            # Priority 1: WMH's own state file
            wm_state_file = Path(__file__).resolve().parents[3] / "state" / "consciousness" / "working_memory.json"
            if wm_state_file.exists():
                wm_data = json.loads(wm_state_file.read_text())
                wm_age = _time.time() - wm_data.get("timestamp", 0)
                if wm_age < 60:
                    result["working_memory"] = {
                        "exists": True,
                        "reflective_tracers": wm_data.get("reflective_count", 0),
                        "reasoning_tracers": wm_data.get("reasoning_count", 0),
                        "patterns_count": 0,
                        "stats": wm_data.get("stats", {}),
                        "data_source": "state_file",
                        "state_age_seconds": round(wm_age, 1),
                    }
                    wm_found = True

            # Priority 2: Heartbeat file
            if not wm_found:
                hb_file = Path(__file__).resolve().parents[3] / "state" / "heartbeat.json"
                if hb_file.exists():
                    hb_data = json.loads(hb_file.read_text())
                    hb_age = _time.time() - hb_data.get("ts", 0)
                    wm = hb_data.get("working_memory")
                    if hb_age < 30 and wm:
                        result["working_memory"] = {
                            "exists": wm.get("exists", False),
                            "reflective_tracers": wm.get("reflective_tracers", 0),
                            "reasoning_tracers": wm.get("reasoning_tracers", 0),
                            "patterns_count": wm.get("patterns_count", 0),
                            "data_source": "heartbeat_file",
                        }
                        wm_found = True

            if not wm_found:
                result["working_memory"] = {"exists": False, "error": "No state file found (stale or missing)"}
        except Exception as e:
            result["working_memory"] = {"exists": False, "error": str(e)}

        # Check ClaudeFairy
        try:
            from fairies.P60_Executive.system_managment.claude_fairy import get_claude_fairy
            claude = get_claude_fairy()
            if claude:
                result["claude_fairy"] = {
                    "exists": True,
                    "actor_name": getattr(claude, 'ACTOR_NAME', 'unknown'),
                    "has_postal": bool(getattr(claude, 'post', None)),
                    "current_feeling": getattr(claude, 'current_feeling', 'unknown'),
                    "coherence": getattr(claude, 'coherence', 0),
                    "energy_level": getattr(claude, 'energy_level', 0),
                    "thoughts_emitted": getattr(claude, '_thoughts_emitted', 0),
                    "observations_count": len(getattr(claude, '_observations', [])),
                    "recent_collisions": len(getattr(claude, '_recent_collisions', [])),
                    "api_key_present": bool(getattr(claude, 'api_key', None)),
                }
            else:
                result["claude_fairy"] = {"exists": False, "error": "No instance"}
        except ImportError:
            result["claude_fairy"] = {"exists": False, "error": "Module not found"}
        except Exception as e:
            result["claude_fairy"] = {"exists": False, "error": str(e)}

        # Check NousFairy
        try:
            from fairies.P30_Cognition.cognition.nous_fairy import get_nous_fairy
            nous = get_nous_fairy()
            if nous:
                result["nous_fairy"] = {
                    "exists": True,
                    "actor_name": getattr(nous, 'ACTOR_NAME', 'unknown'),
                    "has_postal": bool(getattr(nous, 'post', None)),
                    "traces_captured": getattr(nous, 'traces_captured', 0),
                    "patterns_taught": getattr(nous, 'patterns_taught', 0),
                }
            else:
                result["nous_fairy"] = {"exists": False, "error": "No instance"}
        except ImportError:
            result["nous_fairy"] = {"exists": False, "error": "Module not found - needs get_nous_fairy()"}
        except Exception as e:
            result["nous_fairy"] = {"exists": False, "error": str(e)}

        # Check postal system
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            if postal:
                # Get subscription counts per topic
                subs = getattr(postal, '_subscribers', {})
                sub_counts = {topic: len(callbacks) for topic, callbacks in subs.items()}
                consciousness_subs = {k: v for k, v in sub_counts.items() if 'consciousness' in k.lower()}
                result["postal_stats"] = {
                    "exists": True,
                    "total_topics": len(sub_counts),
                    "consciousness_topics": consciousness_subs,
                    "message_count": getattr(postal, '_message_count', 0),
                }
            else:
                result["postal_stats"] = {"exists": False, "error": "No instance"}
        except Exception as e:
            result["postal_stats"] = {"exists": False, "error": str(e)}

        return json.dumps(result, indent=2, default=str)
    
    @mcp.tool()
    def claude_fairy_thoughts(n: int = 10) -> str:
        """
        Get ClaudeFairy's recent thoughts/observations.
        
        Args:
            n: Number of recent thoughts to retrieve
            
        Returns:
            JSON with recent thoughts
        """
        try:
            from fairies.P60_Executive.system_managment.claude_fairy import get_claude_fairy
            claude = get_claude_fairy()
            if not claude:
                return json.dumps({"error": "ClaudeFairy not found"})
            
            observations = list(getattr(claude, '_observations', []))[-n:]
            collisions = list(getattr(claude, '_recent_collisions', []))
            
            return json.dumps({
                "actor": getattr(claude, 'ACTOR_NAME', 'unknown'),
                "current_feeling": getattr(claude, 'current_feeling', 'unknown'),
                "thoughts_emitted": getattr(claude, '_thoughts_emitted', 0),
                "recent_observations": observations,
                "recent_collisions": collisions,
                "energy": getattr(claude, 'energy_level', 0),
                "coherence": getattr(claude, 'coherence', 0),
            }, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def consciousness_inject_thought(
        thought: str,
        source: str = "diagnostic",
        stream: str = "working"
    ) -> str:
        """
        Inject a thought into the consciousness loop for testing.
        
        Args:
            thought: The thought content to inject
            source: Source label (default: diagnostic)
            stream: Which stream (working or reflective)
            
        Returns:
            JSON with injection result
        """
        try:
            from mcp_postal_helper import get_postal, is_bridged_to_server
            postal = get_postal()
            if not postal:
                return json.dumps({"error": "Postal hub not found"})

            bridged = is_bridged_to_server()

            # Emit to consciousness.stream
            postal.route("consciousness.stream", {
                "type": "diagnostic_injection",
                "stream": stream,
                "source": source,
                "content": {
                    "thought": thought,
                    "injected_at": time.time(),
                },
                "ts": time.time(),
            })
            
            # Also emit to consciousness.thought for WorkingMemoryHub
            postal.route("consciousness.thought", {
                "source": source,
                "thought": thought,
                "thought_type": "diagnostic",
                "stream": stream,
                "ts": time.time(),
            })
            
            return json.dumps({
                "success": True,
                "bridged_to_server": bridged,
                "thought": thought,
                "stream": stream,
                "source": source,
                "timestamp": time.time(),
                "note": "Routed via postal tunnel" if bridged else "WARNING: Isolated postal hub - thought may not reach server"
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def consciousness_trigger_collision() -> str:
        """
        Manually trigger a consciousness collision for testing.
        
        Returns:
            JSON with collision result
        """
        try:
            from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop
            loop = get_consciousness_loop()
            if not loop:
                return json.dumps({"error": "ConsciousnessLoop not found"})
            
            # Try to trigger a collision
            if hasattr(loop, '_tick') or hasattr(loop, 'tick'):
                tick_fn = getattr(loop, '_tick', None) or getattr(loop, 'tick', None)
                if callable(tick_fn):
                    tick_fn()
                    return json.dumps({
                        "success": True,
                        "message": "Triggered consciousness tick",
                        "collision_count": getattr(loop, '_collision_count', 0),
                    })
            
            # Alternative: emit collision event via postal tunnel
            from mcp_postal_helper import get_postal, is_bridged_to_server
            postal = get_postal()
            bridged = is_bridged_to_server()
            if postal:
                postal.route("consciousness.collision", {
                    "type": "diagnostic_collision",
                    "working": {"thought": "Test working stream thought", "source": "diagnostic"},
                    "reflective": {"thought": "Test reflective stream thought", "source": "diagnostic"},
                    "resonance": 0.5,
                    "ts": time.time(),
                })
                return json.dumps({
                    "success": True,
                    "bridged_to_server": bridged,
                    "message": "Emitted diagnostic collision event via tunnel" if bridged else "Emitted to isolated hub",
                })
            
            return json.dumps({"error": "Could not trigger collision"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def fairy_consciousness_check(fairy_name: str) -> str:
        """
        Check if a specific fairy is connected to consciousness streams.

        Args:
            fairy_name: Name of fairy to check (e.g., 'ClaudeFairy', 'AutonomyFairy')

        Returns:
            JSON with fairy's consciousness connection status
        """
        try:
            from mcp_postal_helper import get_postal, is_bridged_to_server

            # First try to query server.py via tunnel
            bridged = is_bridged_to_server()
            if bridged:
                postal = get_postal()
                if hasattr(postal, 'query_fairy'):
                    result = postal.query_fairy(fairy_name)
                    result['source'] = 'server_bridge'
                    return json.dumps(result, indent=2, default=str)

            # Fallback to local isolated hub
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            if not postal:
                return json.dumps({"error": "Postal hub not found"})

            # Check subscriptions
            subs = getattr(postal, '_subscribers', {})

            # Find callbacks that might belong to this fairy
            fairy_subs = {}
            for topic, callbacks in subs.items():
                for cb in callbacks:
                    cb_name = getattr(cb, '__qualname__', '') or getattr(cb, '__name__', '')
                    if fairy_name.lower() in cb_name.lower():
                        if topic not in fairy_subs:
                            fairy_subs[topic] = []
                        fairy_subs[topic].append(cb_name)

            return json.dumps({
                "fairy_name": fairy_name,
                "source": "mcp_isolated",
                "warning": "Not connected to server - showing isolated MCP state only",
                "subscribed_topics": fairy_subs,
                "subscription_count": sum(len(v) for v in fairy_subs.values()),
                "consciousness_connected": any('consciousness' in t for t in fairy_subs.keys()),
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def list_consciousness_subscribers() -> str:
        """
        List all fairies subscribed to consciousness-related topics.

        Returns:
            JSON with all consciousness subscribers
        """
        try:
            from mcp_postal_helper import get_postal, is_bridged_to_server

            # First try to query server.py via tunnel
            bridged = is_bridged_to_server()
            if bridged:
                postal = get_postal()
                if hasattr(postal, 'query_subscribers'):
                    result = postal.query_subscribers('consciousness')
                    result['source'] = 'server_bridge'
                    return json.dumps(result, indent=2, default=str)

            # Fallback to local isolated hub
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            if not postal:
                return json.dumps({"error": "Postal hub not found"})

            subs = getattr(postal, '_subscribers', {})

            # Filter to consciousness topics
            consciousness_subs = {}
            for topic, callbacks in subs.items():
                if 'consciousness' in topic.lower():
                    consciousness_subs[topic] = [
                        getattr(cb, '__qualname__', '') or getattr(cb, '__name__', str(cb))
                        for cb in callbacks
                    ]

            return json.dumps({
                "source": "mcp_isolated",
                "warning": "Not connected to server - showing isolated MCP state only",
                "consciousness_topics": list(consciousness_subs.keys()),
                "subscribers_by_topic": consciousness_subs,
                "total_subscribers": sum(len(v) for v in consciousness_subs.values()),
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def cortex_pipeline_diagnostic() -> str:
        """
        Diagnose the consciousness → cortex pipeline.

        Checks:
        1. SRMRecallFairy - is it wired and doing recalls?
        2. SRMIngestFairy - is it publishing ingests?
        3. CollisionChamberFairy - is it receiving and producing collisions?
        4. AssociationCortexFairy - is it receiving and binding?

        Returns:
            JSON with pipeline status at each stage
        """
        result = {
            "timestamp": time.time(),
            "pipeline": {},
            "diagnosis": [],
            "healthy": True,
        }

        # 1. Check SRMRecallFairy
        try:
            from fairies.P10_Memory.SRMRecallFairy.fairy import get_recall_fairy
            recall = get_recall_fairy()
            if recall:
                status = recall.status()
                result["pipeline"]["srm_recall"] = {
                    "found": True,
                    "consciousness_wired": status.get("consciousness_wired", False),
                    "coordinator_connected": status.get("coordinator_connected", False),
                    "tick_count": status.get("tick_count", 0),
                    "total_queries": status.get("stats", {}).get("queries", 0),
                }
                if not status.get("consciousness_wired"):
                    result["diagnosis"].append("SRMRecallFairy NOT wired to consciousness - spontaneous recalls will be skipped!")
                    result["healthy"] = False
                if not status.get("coordinator_connected"):
                    result["diagnosis"].append("SRMRecallFairy has no Helix coordinator - no memories to recall!")
                    result["healthy"] = False
            else:
                result["pipeline"]["srm_recall"] = {"found": False}
                result["diagnosis"].append("SRMRecallFairy not found!")
                result["healthy"] = False
        except Exception as e:
            result["pipeline"]["srm_recall"] = {"error": str(e)}

        # 2. Check CollisionChamberFairy
        try:
            from fairies.P00_Autonomic.CollisionChamberFairy.fairy import get_collision_chamber_fairy
            chamber_fairy = get_collision_chamber_fairy()
            if chamber_fairy:
                status = chamber_fairy.status()
                result["pipeline"]["collision_chamber"] = {
                    "found": True,
                    "recall_pulses": status.get("recall_pulses", 0),
                    "ingest_pulses": status.get("ingest_pulses", 0),
                    "total_collisions": status.get("total_collisions", 0),
                }
                if status.get("total_collisions", 0) == 0:
                    result["diagnosis"].append("CollisionChamberFairy has 0 collisions - either no input or processing broken")
            else:
                result["pipeline"]["collision_chamber"] = {"found": False}
                result["diagnosis"].append("CollisionChamberFairy not found!")
                result["healthy"] = False
        except Exception as e:
            result["pipeline"]["collision_chamber"] = {"error": str(e)}

        # 3. Check AssociationCortexFairy
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if cortex:
                status = cortex.status()
                result["pipeline"]["association_cortex"] = {
                    "found": True,
                    "node_count": status.get("node_count", 0),
                    "edge_count": status.get("edge_count", 0),
                    "binding_count": status.get("binding_count", 0),
                    "pending_bindings": status.get("pending_bindings", 0),
                }
                if status.get("binding_count", 0) == 0:
                    result["diagnosis"].append("AssociationCortexFairy has 0 bindings - no collisions received or not processing them")
            else:
                result["pipeline"]["association_cortex"] = {"found": False}
                result["diagnosis"].append("AssociationCortexFairy not found!")
                result["healthy"] = False
        except Exception as e:
            result["pipeline"]["association_cortex"] = {"error": str(e)}

        # Summary
        if not result["diagnosis"]:
            result["diagnosis"].append("Pipeline looks healthy - data should be flowing")

        return json.dumps(result, indent=2, default=str)

    sys.stderr.write("[MCP] [OK] Consciousness monitor tools registered\n")

    # ========================================================================
    # SYSTEM DIAGNOSTICS TOOLS
    # ========================================================================
    
    @mcp.tool()
    def get_system_diagnostic_report() -> str:
        """
        Get the most recent system diagnostic report.
        
        This report is generated by UnconsciousMindFairy during ignition
        and contains comprehensive health checks for:
        - Postal hub connectivity
        - Consciousness loop status
        - Working memory accessibility  
        - Fairy registry count
        - MCP tunnel bridge
        - SRM memory systems
        - Somatic engine
        - Autonomy fairy
        - ClaudeFairy status
        - NousFairy reasoning traces
        
        Returns:
            JSON diagnostic report with health score and recommendations
        """
        import json
        from pathlib import Path
        
        report_path = Path("F:/Sandbox/ebook/state/system_diagnostic_report.json")
        
        if not report_path.exists():
            return json.dumps({
                "status": "no_report",
                "message": "No diagnostic report found. System may not have completed ignition.",
                "hint": "Wait for UnconsciousMindFairy ignition or trigger manual diagnostics"
            }, indent=2)
        
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            return json.dumps(report, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def trigger_system_diagnostics() -> str:
        """
        Trigger a fresh system diagnostic run via postal message.

        Sends a request to UnconsciousMindFairy to run diagnostics.
        Results will be saved to state/system_diagnostic_report.json

        Returns:
            Status of the diagnostic trigger request
        """
        import json
        import time
        from mcp_postal_helper import get_postal, is_bridged_to_server

        postal = get_postal()
        if not postal:
            return json.dumps({
                "status": "error",
                "message": "No postal connection - cannot trigger diagnostics"
            })

        bridged = is_bridged_to_server()

        try:
            # Route diagnostic request
            postal.route("unconscious.run_diagnostics", {
                "source": "mcp_tool",
                "ts": time.time(),
                "reason": "manual_trigger"
            })

            return json.dumps({
                "status": "triggered",
                "bridged_to_server": bridged,
                "message": "Diagnostic request sent to UnconsciousMindFairy via tunnel" if bridged else "Sent to isolated hub",
                "hint": "Use get_system_diagnostic_report() in a few seconds to see results"
            }, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool()
    def trigger_fairy_audit() -> str:
        """
        Trigger a comprehensive fairy audit.

        This audits ALL fairies for:
        - Directive ring completeness (activation_energy, nature, essence, foundation)
        - System prompt evolution (mastery_level, concepts_learned, curriculum)
        - Wiring completeness (subscriptions, publishers)
        - Activity health (collaborators, learning_history)
        - Shadow health status
        - Tracer flow verification (injects test thoughts)

        Results saved to state/fairy_audit_report.json with actionable fix list.

        Returns:
            Status of the audit trigger request
        """
        import json
        import time
        from mcp_postal_helper import get_postal, is_bridged_to_server

        postal = get_postal()
        if not postal:
            return json.dumps({
                "status": "error",
                "message": "No postal connection - cannot trigger fairy audit"
            })

        bridged = is_bridged_to_server()

        try:
            # Route fairy audit request
            postal.route("unconscious.fairy_audit", {
                "source": "mcp_tool",
                "ts": time.time(),
                "reason": "manual_audit_request"
            })

            return json.dumps({
                "status": "triggered",
                "bridged_to_server": bridged,
                "message": "Fairy audit request sent to UnconsciousMindFairy via tunnel" if bridged else "Sent to isolated hub",
                "hint": "Use get_fairy_audit_report() in 5-10 seconds to see results"
            }, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool()
    def get_fairy_audit_report() -> str:
        """
        Get the most recent comprehensive fairy audit report.

        Returns audit results including:
        - Per-fairy health scores (0-1)
        - Category breakdowns (directive_ring, prompt_evolution, wiring, activity, shadow)
        - Tracer flow test results
        - Prioritized fix recommendations

        Returns:
            JSON with complete fairy audit report
        """
        import json
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        report_path = project_root / "state" / "fairy_audit_report.json"

        if not report_path.exists():
            return json.dumps({
                "status": "not_found",
                "message": "No fairy audit report found. Trigger one with trigger_fairy_audit() first.",
                "path": str(report_path)
            })

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)

            # Add summary stats
            if "audited" in report:
                audited = report["audited"]
                health_scores = [f.get("health_score", 0) for f in audited.values()]
                if health_scores:
                    report["_summary"] = {
                        "total_fairies": len(audited),
                        "avg_health": round(sum(health_scores) / len(health_scores), 2),
                        "healthy_count": sum(1 for s in health_scores if s >= 0.7),
                        "needs_attention_count": sum(1 for s in health_scores if s < 0.7),
                        "critical_count": sum(1 for s in health_scores if s < 0.3),
                    }

            return json.dumps(report, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_fairy_fix_list() -> str:
        """
        Get the prioritized list of fairies that need fixes.

        Extracts just the recommendations section from the fairy audit,
        organized by priority:
        - CRITICAL: Fairies that are broken/non-functional
        - HIGH: Major issues affecting functionality
        - MEDIUM: Missing features but mostly working
        - LOW: Polish/enhancement items

        Returns:
            JSON with prioritized fix list
        """
        import json
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        report_path = project_root / "state" / "fairy_audit_report.json"

        if not report_path.exists():
            return json.dumps({
                "status": "not_found",
                "message": "No fairy audit report found. Trigger one with trigger_fairy_audit() first."
            })

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)

            recommendations = report.get("recommendations", {})

            # Count by priority
            summary = {
                "critical_count": len(recommendations.get("critical", [])),
                "high_count": len(recommendations.get("high", [])),
                "medium_count": len(recommendations.get("medium", [])),
                "low_count": len(recommendations.get("low", [])),
            }

            return json.dumps({
                "summary": summary,
                "fix_list": recommendations,
                "total_fixes_needed": sum(summary.values()),
            }, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_consciousness_streams(n: int = 5) -> str:
        """
        Get thoughts from all consciousness streams (working, reflective, thought queue).

        This surfaces the actual content flowing through consciousness, including
        reflective thoughts that aren't visible in the regular thought queue.

        Args:
            n: Number of thoughts per stream to retrieve (default 5)

        Returns:
            JSON with thoughts from all streams
        """
        try:
            from mcp_postal_helper import get_postal, is_bridged_to_server
            postal = get_postal()
            bridged = is_bridged_to_server()

            result = {
                "timestamp": time.time(),
                "source": "server_bridge" if bridged else "mcp_isolated",
                "bridged": bridged,
                "streams": {},
            }

            # Try to get from UMF via postal tunnel
            if bridged and hasattr(postal, 'query'):
                try:
                    umf_result = postal.query("UnconsciousMindFairy", "get_all_consciousness_thoughts", {"last_n": n})
                    if umf_result:
                        result["streams"] = umf_result
                        return json.dumps(result, indent=2, default=str)
                except:
                    pass

            # Fallback: Try to access UMF directly
            try:
                from fairies.P20_Somatic.SomaticMindFairy import get_somatic_mind as get_umf
                umf = get_umf()
                if umf and hasattr(umf, 'get_all_consciousness_thoughts'):
                    result["streams"] = umf.get_all_consciousness_thoughts(n)
                    return json.dumps(result, indent=2, default=str)
            except Exception as e:
                result["streams"]["error"] = f"Could not access UMF: {e}"

            # Last fallback: Try consciousness loop directly
            try:
                from consciousness.loop import get_consciousness_loop
                loop = get_consciousness_loop()
                if loop:
                    result["streams"]["working"] = []
                    result["streams"]["reflective"] = []

                    if hasattr(loop, 'working') and hasattr(loop.working, 'peek'):
                        result["streams"]["working"] = loop.working.peek(n)
                    if hasattr(loop, 'reflective') and hasattr(loop.reflective, 'peek'):
                        result["streams"]["reflective"] = loop.reflective.peek(n)
            except Exception as e:
                result["streams"]["loop_error"] = str(e)

            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ========================================================================
    # KNOWLEDGE SEEDING TOOLS
    # ========================================================================

    @mcp.tool()
    def seed_domain_knowledge(verbose: bool = True) -> str:
        """
        Seed the Association Cortex with domain knowledge concepts.

        This loads:
        - Color psychology associations (color -> emotion/trait)
        - Emotion-color mappings
        - Domain concepts (coding, reading, art, science, music, philosophy)
        - Meta-concepts (learning, creativity, problem_solving)
        - Cross-domain relationships

        After seeding, the consciousness system can "think about" these concepts
        by activating related nodes through spreading activation.

        Args:
            verbose: Print progress messages (default True)

        Returns:
            JSON summary of seeding results
        """
        import json
        try:
            from fairies.P40_Sensory.cortex.knowledge_seeder import seed_all_knowledge

            result = seed_all_knowledge(verbose=verbose)
            return json.dumps(result, indent=2, default=str)
        except ImportError as e:
            return json.dumps({
                "status": "error",
                "message": f"Could not import knowledge_seeder: {e}"
            })
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": str(e)
            })

    @mcp.tool()
    def query_domain_concept(concept: str, max_hops: int = 2) -> str:
        """
        Query related concepts from the domain knowledge graph.

        Uses spreading activation to find concepts related to the query.
        This is how the system can "think about" a topic.

        Args:
            concept: The concept to explore (e.g., "algorithm", "creativity", "art")
            max_hops: Maximum relationship distance to traverse (default 2)

        Returns:
            JSON with related concepts and their activation levels
        """
        import json
        try:
            from fairies.P40_Sensory.cortex.knowledge_seeder import get_seeded_graph

            graph = get_seeded_graph()
            if not graph:
                return json.dumps({
                    "status": "no_graph",
                    "message": "Knowledge graph not seeded. Run seed_domain_knowledge() first."
                })

            # Try different key formats
            key_variants = [
                f"concept:{concept}",
                f"domain:{concept}",
                f"affect:{concept}",
                f"category:{concept}",
                f"meta:{concept}",
            ]

            results = {}
            for key in key_variants:
                if key in graph.nodes:
                    activations = graph.spread_activation(key, max_hops=max_hops)
                    results[key] = {
                        "node": graph.nodes[key].to_dict() if key in graph.nodes else None,
                        "related": sorted(
                            [(k, v) for k, v in activations.items() if v > 0.01],
                            key=lambda x: -x[1]
                        )[:20],
                        "neighbor_count": len(activations),
                    }

            if not results:
                return json.dumps({
                    "status": "not_found",
                    "query": concept,
                    "message": f"Concept '{concept}' not found. Try seeding first with seed_domain_knowledge()."
                })

            return json.dumps({
                "status": "ok",
                "query": concept,
                "found_as": list(results.keys()),
                "results": results,
            }, indent=2, default=str)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    sys.stderr.write("[MCP] Knowledge seeding tools registered\n")
    sys.stderr.write("[MCP] System diagnostic tools registered\n")
