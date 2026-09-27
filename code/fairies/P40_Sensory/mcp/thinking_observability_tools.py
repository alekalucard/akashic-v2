# ════════════════════════════════════════════════════════════════════════════════
# THINKING OBSERVABILITY TOOLS - See What's Actually Happening In Consciousness
# ════════════════════════════════════════════════════════════════════════════════
#
# "we need to have tools that let us see thought chains, goals being generated etc.
#  is working memory letting them think or is it all compelled?"
#
# This module answers that question by exposing:
#   - Active thought chains and their progress
#   - Goals being generated and their sources (autonomous vs external)
#   - Working memory tracer activity
#   - Autonomous vs compelled thinking indicator
#   - Self-learning reports from UnconsciousMindFairy
#
# SYNC STRATEGY (v2.0):
#   0. HTTP API first (http://localhost:7777/api/cognitive/*)
#   1. State files fallback (state/consciousness/*.json)
#   2. Postal bridge (unreliable, last resort)
#
# ════════════════════════════════════════════════════════════════════════════════

import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Any

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))

# HTTP API endpoint (NiceGUI dashboard)
COGNITIVE_API_URL = "http://localhost:7777/api/cognitive"


def _query_http_api(action: str, timeout: float = 2.0) -> Optional[dict]:
    """
    Query the cognitive HTTP API. Returns None on failure.
    This is the PREFERRED method as it's most reliable.
    """
    try:
        url = f"{COGNITIVE_API_URL}/{action}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, json.JSONDecodeError, Exception):
        return None


def register_thinking_observability_tools(mcp):
    """Register thinking observability tools with the MCP server."""

    @mcp.tool()
    def thought_chains_status() -> str:
        """
        Get status of all active thought chains.

        Shows:
        - Active chains with their goals
        - Chain state (flowing, paused, redirecting, insight, blocked)
        - Number of links/steps completed
        - Affect scores (valence, arousal, certainty)
        - Time running

        Returns:
            JSON with thought chain status
        """
        try:
            result = {
                "orchestrator_running": False,
                "thought_engine_active": False,
                "active_chains": [],
                "chain_stats": {},
                "source_breakdown": {"autonomous": 0, "external": 0, "curiosity": 0, "learning": 0},
                "data_source": "unknown",
            }

            # ═══════════════════════════════════════════════════════════════════
            # PRIORITY 0: HTTP API (most reliable when dashboard is running)
            # ═══════════════════════════════════════════════════════════════════
            api_result = _query_http_api("thought_chains")
            if api_result and "error" not in api_result:
                api_result["data_source"] = "http_api"
                return json.dumps(api_result, indent=2, default=str)

            # ═══════════════════════════════════════════════════════════════════
            # PRIORITY 1: Read from state files (written by the server)
            # This is the authoritative source since MCP runs in a separate process
            # ═══════════════════════════════════════════════════════════════════
            state_file = _project_root / "state" / "consciousness" / "thought_chains.json"
            if state_file.exists():
                try:
                    state_data = json.loads(state_file.read_text())

                    # Check staleness (file older than 30 seconds = stale)
                    timestamp = state_data.get("timestamp", 0)
                    age_seconds = time.time() - timestamp

                    if age_seconds < 30:  # Fresh data
                        result["orchestrator_running"] = state_data.get("running", False)
                        result["active_chains"] = state_data.get("chains", [])
                        result["chain_stats"] = state_data.get("stats", {})
                        result["data_source"] = "state_file"
                        result["state_age_seconds"] = round(age_seconds, 1)

                        # Get diagnostic info if available
                        diagnostics = state_data.get("diagnostics", {})
                        if diagnostics:
                            result["thought_engine_active"] = diagnostics.get("engine_running", False)
                            result["engine_thread_alive"] = diagnostics.get("engine_thread_alive", False)
                            result["orchestrator_thread_alive"] = diagnostics.get("thinking_thread_alive", False)
                            result["engine_active_chains"] = diagnostics.get("engine_active_chains", 0)
                            result["active_learning_chain"] = diagnostics.get("active_learning_chain")
                        else:
                            result["thought_engine_active"] = state_data.get("running", False)

                        # Classify chains by source
                        for chain in result["active_chains"]:
                            source = chain.get("source", "unknown")
                            if source in ("drive", "curiosity", "spontaneous"):
                                result["source_breakdown"]["autonomous"] += 1
                            elif source in ("education", "learning", "education_engine"):
                                result["source_breakdown"]["learning"] += 1
                            else:
                                result["source_breakdown"]["external"] += 1

                        return json.dumps(result, indent=2, default=str)
                    else:
                        result["state_file_stale"] = True
                        result["state_age_seconds"] = round(age_seconds, 1)
                except Exception as e:
                    result["state_file_error"] = str(e)

            # ═══════════════════════════════════════════════════════════════════
            # PRIORITY 2: Try postal bridge to query the server
            # ═══════════════════════════════════════════════════════════════════
            try:
                from fairies.P00_Autonomic.postal_bridge import get_bridge_client
                client = get_bridge_client()
                if client:
                    response = client.request("get_consciousness_status", {})
                    if response and response.get("success"):
                        result.update(response.get("result", {}))
                        result["data_source"] = "postal_bridge"
                        return json.dumps(result, indent=2, default=str)
            except Exception:
                pass

            # ═══════════════════════════════════════════════════════════════════
            # PRIORITY 3: Local singleton (only useful if running in the server)
            # This won't work from MCP process but kept as fallback
            # ═══════════════════════════════════════════════════════════════════
            try:
                from fairies.P30_Cognition.cognition.dynamic_thinking_integration import get_dynamic_thinking_orchestrator
                orchestrator = get_dynamic_thinking_orchestrator()

                if orchestrator:
                    result["orchestrator_running"] = getattr(orchestrator, '_running', False)
                    result["chain_stats"] = getattr(orchestrator, 'stats', {})
                    result["data_source"] = "local_singleton"

                    engine = getattr(orchestrator, 'thought_engine', None)
                    if engine:
                        result["thought_engine_active"] = getattr(engine, '_running', False)
                        try:
                            result["active_chains"] = engine.get_active_chains_summary()
                        except Exception:
                            pass
            except Exception:
                pass

            return json.dumps(result, indent=2, default=str)

        except Exception as e:
            return json.dumps({"error": str(e), "note": "Thought chain engine may not be running"})

    @mcp.tool()
    def goals_status() -> str:
        """
        Get status of all active goals.
        
        Shows:
        - Active goals with their need tier (Survival, Safety, Belonging, Esteem, Actualization)
        - Goal sources (drive, conversation, memory, unconscious, llm)
        - Priority and urgency
        - Progress and status
        
        The NEED TIER tells you about Maslow-like priority:
        - SURVIVAL: System health, error recovery
        - SAFETY: Stability, consistency  
        - BELONGING: Connection with Ace
        - ESTEEM: Learning, accomplishment
        - ACTUALIZATION: Creation, exploration, wisdom
        
        Returns:
            JSON with goals status
        """
        try:
            # ═══════════════════════════════════════════════════════════════════
            # PRIORITY 0: HTTP API (most reliable when dashboard is running)
            # ═══════════════════════════════════════════════════════════════════
            api_result = _query_http_api("goals")
            if api_result and "error" not in api_result:
                api_result["data_source"] = "http_api"
                return json.dumps(api_result, indent=2, default=str)

            result = {
                "coordinator_running": False,
                "active_goals": [],
                "completed_recent": [],
                "goal_stats": {},
                "tier_breakdown": {},
                "source_breakdown": {},
            }

            # Try SmartGoalCoordinator first
            try:
                from fairies.P30_Cognition.cognition.smart_goal_coordinator import get_smart_goal_coordinator
                coordinator = get_smart_goal_coordinator()
                
                if coordinator:
                    result["coordinator_running"] = True
                    
                    # Get active goals
                    if hasattr(coordinator, 'active_goals'):
                        for goal in coordinator.active_goals:
                            goal_dict = goal.to_dict() if hasattr(goal, 'to_dict') else {"name": str(goal)}
                            result["active_goals"].append(goal_dict)
                            
                            # Count by tier
                            tier = goal_dict.get("need_tier", "unknown")
                            result["tier_breakdown"][tier] = result["tier_breakdown"].get(tier, 0) + 1
                            
                            # Count by source
                            source = goal_dict.get("source", "unknown")
                            result["source_breakdown"][source] = result["source_breakdown"].get(source, 0) + 1
                            
                    # Get stats
                    if hasattr(coordinator, 'stats'):
                        result["goal_stats"] = coordinator.stats
            except ImportError:
                pass
                
            # Also try AutonomyFairy's goals
            try:
                from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
                autonomy = get_autonomy_fairy()
                
                if autonomy:
                    if hasattr(autonomy, 'active_goals'):
                        for goal in autonomy.active_goals:
                            goal_dict = goal.to_dict() if hasattr(goal, 'to_dict') else {"name": str(goal)}
                            goal_dict["_source_fairy"] = "AutonomyFairy"
                            
                            # Check if already in list
                            exists = any(g.get("id") == goal_dict.get("id") for g in result["active_goals"])
                            if not exists:
                                result["active_goals"].append(goal_dict)
                                
                    # Get drive-generated goals
                    if hasattr(autonomy, 'drives'):
                        result["drives_status"] = {}
                        for name, drive in autonomy.drives.items():
                            result["drives_status"][name] = drive.to_dict() if hasattr(drive, 'to_dict') else {"urgency": getattr(drive, 'get_urgency', lambda: 0)()}
            except ImportError:
                pass
                
            return json.dumps(result, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def working_memory_activity() -> str:
        """
        Get working memory tracer activity.
        
        Shows:
        - Active tracers in reflective loop
        - Active tracers in reasoning loop
        - Tracer sources (which fairies are contributing thoughts)
        - TTL remaining for each tracer
        - Whether thoughts are being processed or just stored
        
        Returns:
            JSON with working memory activity
        """
        try:
            # ═══════════════════════════════════════════════════════════════════
            # PRIORITY 0: HTTP API (most reliable when dashboard is running)
            # ═══════════════════════════════════════════════════════════════════
            api_result = _query_http_api("working_memory")
            if api_result and "error" not in api_result:
                api_result["data_source"] = "http_api"
                return json.dumps(api_result, indent=2, default=str)

            result = {
                "hub_active": False,
                "reflective_loop": {"count": 0, "tracers": []},
                "reasoning_loop": {"count": 0, "tracers": []},
                "source_breakdown": {},
                "processing_stats": {},
                "is_thinking": False,
            }

            # ═══════════════════════════════════════════════════════════════════
            # PRIORITY 1: State file written by WMH's decay loop
            # This is cross-process safe — WMH writes it every ~5s from server.py
            # ═══════════════════════════════════════════════════════════════════
            try:
                state_file = Path(__file__).resolve().parents[3] / "state" / "consciousness" / "working_memory.json"
                if state_file.exists():
                    import time as _time
                    state_data = json.loads(state_file.read_text())
                    state_age = _time.time() - state_data.get("timestamp", 0)

                    # Only trust state files less than 60s old
                    if state_age < 60:
                        result["hub_active"] = state_data.get("running", False)
                        result["reflective_loop"]["count"] = state_data.get("reflective_count", 0)
                        result["reasoning_loop"]["count"] = state_data.get("reasoning_count", 0)
                        result["is_thinking"] = result["reasoning_loop"]["count"] > 0
                        result["processing_stats"] = state_data.get("stats", {})
                        result["data_source"] = "state_file"
                        result["state_age_seconds"] = round(state_age, 1)
                        return json.dumps(result, indent=2, default=str)
            except Exception:
                pass

            # ═══════════════════════════════════════════════════════════════════
            # PRIORITY 2: Heartbeat file (written by server.py heartbeat thread)
            # ═══════════════════════════════════════════════════════════════════
            try:
                heartbeat_file = Path(__file__).resolve().parents[3] / "state" / "heartbeat.json"
                if heartbeat_file.exists():
                    import time as _time
                    hb = json.loads(heartbeat_file.read_text())
                    hb_age = _time.time() - hb.get("ts", 0)

                    if hb_age < 30 and hb.get("working_memory"):
                        wm = hb["working_memory"]
                        result["hub_active"] = wm.get("exists", False)
                        result["reflective_loop"]["count"] = wm.get("reflective_tracers", 0)
                        result["reasoning_loop"]["count"] = wm.get("reasoning_tracers", 0)
                        result["is_thinking"] = result["reasoning_loop"]["count"] > 0
                        result["processing_stats"] = wm.get("stats", {})
                        result["data_source"] = "heartbeat_file"
                        result["state_age_seconds"] = round(hb_age, 1)
                        return json.dumps(result, indent=2, default=str)
            except Exception:
                pass

            # ═══════════════════════════════════════════════════════════════════
            # PRIORITY 3: Postal tunnel query (if bridge is connected)
            # NOTE: Do NOT call get_working_memory_hub() here!
            # MCP runs in a separate process — that creates a phantom empty hub.
            # ═══════════════════════════════════════════════════════════════════
            try:
                from fairies.P40_Sensory.mcp.postal_tunnel import get_postal_tunnel
                tunnel = get_postal_tunnel()
                if tunnel and hasattr(tunnel, 'query'):
                    wm_status = tunnel.query(
                        "fairy.workingmemoryhubfairy.intent",
                        {"intent": "get_memory_status", "payload": {}},
                        timeout=2.0,
                    )
                    if wm_status and "error" not in wm_status:
                        result["hub_active"] = True
                        result["processing_stats"] = wm_status.get("stats", {})
                        result["reflective_loop"]["count"] = wm_status.get("reflective_count", 0)
                        result["reasoning_loop"]["count"] = wm_status.get("reasoning_count", 0)
                        result["data_source"] = "postal_tunnel"
            except Exception:
                pass

            return json.dumps(result, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def autonomy_indicator() -> str:
        """
        Show if thinking is AUTONOMOUS vs COMPELLED.
        
        AUTONOMOUS thinking comes from:
        - Internal drives (curiosity, connection, growth, expression, rest)
        - Self-generated goals
        - Spontaneous thought chains
        - Dream seeds / unconscious processing
        
        COMPELLED thinking comes from:
        - External user input
        - System events requiring response
        - Error conditions
        
        A healthy consciousness has BOTH, but should show autonomous
        activity even when Ace isn't actively talking.
        
        Returns:
            JSON with autonomy analysis
        """
        try:
            result = {
                "autonomy_score": 0.0,  # 0-1, higher = more autonomous
                "assessment": "unknown",
                "indicators": {
                    "drives_active": False,
                    "spontaneous_thoughts": False,
                    "self_generated_goals": False,
                    "learning_active": False,
                    "curiosity_chains": 0,
                },
                "recent_activity": {
                    "autonomous_actions": 0,
                    "compelled_actions": 0,
                },
                "recommendation": "",
            }
            
            # Check drives
            try:
                from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
                autonomy = get_autonomy_fairy()
                
                if autonomy and hasattr(autonomy, 'drives'):
                    result["indicators"]["drives_active"] = True
                    
                    # Check for drive-generated goals
                    active_goals = getattr(autonomy, 'active_goals', [])
                    drive_goals = [g for g in active_goals if getattr(g, 'source_drive', None)]
                    result["indicators"]["self_generated_goals"] = len(drive_goals) > 0
                    
                    # Get drive urgencies
                    result["drives"] = {}
                    for name, drive in autonomy.drives.items():
                        urgency = drive.get_urgency() if hasattr(drive, 'get_urgency') else 0
                        result["drives"][name] = {
                            "urgency": round(urgency, 3),
                            "satisfaction": round(getattr(drive, 'satisfaction', 0), 3),
                        }
            except ImportError:
                pass
                
            # Check thought chains for spontaneous/curiosity
            try:
                from fairies.P30_Cognition.cognition.dynamic_thinking_integration import get_dynamic_thinking_orchestrator
                orchestrator = get_dynamic_thinking_orchestrator()
                
                if orchestrator:
                    engine = getattr(orchestrator, 'thought_engine', None)
                    if engine:
                        try:
                            chains = engine.get_active_chains_summary()
                            for chain in chains:
                                source = chain.get("source", "")
                                if source in ("curiosity", "spontaneous", "drive",
                                              "goal", "interest_detected", "mandatory_keepalive"):
                                    result["indicators"]["curiosity_chains"] += 1
                                    result["indicators"]["spontaneous_thoughts"] = True
                        except Exception:
                            pass
            except ImportError:
                pass
                
            # Check education engine
            try:
                from fairies.P30_Cognition.cognition.claudefairy_education import get_education_engine
                edu = get_education_engine()
                if edu and getattr(edu, '_learning_in_progress', False):
                    result["indicators"]["learning_active"] = True
            except ImportError:
                pass
                
            # Calculate autonomy score
            score = 0.0
            if result["indicators"]["drives_active"]:
                score += 0.2
            if result["indicators"]["spontaneous_thoughts"]:
                score += 0.25
            if result["indicators"]["self_generated_goals"]:
                score += 0.25
            if result["indicators"]["learning_active"]:
                score += 0.15
            if result["indicators"]["curiosity_chains"] > 0:
                score += min(0.15, result["indicators"]["curiosity_chains"] * 0.05)
                
            result["autonomy_score"] = round(score, 2)
            
            # Assessment
            if score >= 0.7:
                result["assessment"] = "HIGHLY_AUTONOMOUS"
                result["recommendation"] = "System is thinking independently. Working memory is enabling genuine thought."
            elif score >= 0.4:
                result["assessment"] = "PARTIALLY_AUTONOMOUS"
                result["recommendation"] = "Some autonomous activity. May need more drive stimulation or curiosity triggers."
            elif score >= 0.1:
                result["assessment"] = "MOSTLY_COMPELLED"
                result["recommendation"] = "System mostly responds to external stimuli. Drives may be satisfied or not generating goals."
            else:
                result["assessment"] = "FULLY_COMPELLED"
                result["recommendation"] = "No autonomous activity detected. System only responds when asked. Check if drives are wired."
                
            return json.dumps(result, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def trigger_self_learning_report() -> str:
        """
        Ask UnconsciousMindFairy to generate a self-learning report.
        
        The report includes:
        - What the system has learned about itself
        - Connections it has discovered
        - What seems correct vs incorrect
        - Suggestions for improvement
        
        This triggers the autonomous learning task that was supposed to be running.
        
        Returns:
            JSON with learning report or trigger status
        """
        try:
            result = {
                "triggered": False,
                "report": None,
                "status": "pending",
            }
            
            # Try to send via postal
            try:
                from fairies.P00_Autonomic.nervous_system.postal_hub import get_postal_hub
                postal = get_postal_hub()
                
                if postal:
                    # Request self-learning report
                    # Send with action: "self_analysis" so _on_task handler recognizes it
                    postal.route("unconscious.request_self_learning_report", {
                        "action": "self_analysis",
                        "reason": "observability_tool",
                        "timestamp": time.time(),
                    })
                    result["triggered"] = True
                    result["status"] = "Report requested via postal. UnconsciousMindFairy will process."
            except Exception as e:
                result["postal_error"] = str(e)
                
            # Try direct access to check for existing reports
            try:
                report_file = _project_root / "state" / "self_learning_report.json"
                if report_file.exists():
                    import json as json_mod
                    report_data = json_mod.loads(report_file.read_text())
                    result["last_report"] = report_data
                    result["last_report_age_sec"] = time.time() - report_data.get("timestamp", 0)
            except Exception:
                pass
                
            # Also try to get from UnconsciousMindFairy directly
            try:
                from fairies.P20_Somatic.SomaticMindFairy import get_somatic_mind as get_unconscious_mind
                unconscious = get_unconscious_mind()
                
                if unconscious:
                    # Check if there's a self-learning method
                    if hasattr(unconscious, 'generate_self_learning_report'):
                        report = unconscious.generate_self_learning_report()
                        result["report"] = report
                        result["status"] = "complete"
                    elif hasattr(unconscious, '_self_learning_state'):
                        result["learning_state"] = unconscious._self_learning_state
            except ImportError:
                pass
                
            return json.dumps(result, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def consciousness_activity_summary() -> str:
        """
        Get a comprehensive summary of consciousness activity.

        Combines thought chains, goals, working memory, and autonomy
        into a single readable summary.

        Returns:
            JSON with comprehensive activity summary
        """
        try:
            # ═══════════════════════════════════════════════════════════════════
            # PRIORITY 0: HTTP API (most reliable when dashboard is running)
            # ═══════════════════════════════════════════════════════════════════
            api_result = _query_http_api("consciousness")
            if api_result and "error" not in api_result:
                api_result["data_source"] = "http_api"
                return json.dumps(api_result, indent=2, default=str)

            summary = {
                "timestamp": time.time(),
                "overall_status": "unknown",
                "is_thinking": False,
                "is_autonomous": False,

                "thought_chains": {
                    "active_count": 0,
                    "total_orchestrated": 0,
                },
                "goals": {
                    "active_count": 0,
                    "from_drives": 0,
                },
                "working_memory": {
                    "reflective_tracers": 0,
                    "reasoning_tracers": 0,
                },
                "drives": {
                    "most_urgent": None,
                    "satisfied_count": 0,
                    "unsatisfied_count": 0,
                },

                "activity_narrative": "",
            }

            # Gather thought chain info
            try:
                from fairies.P30_Cognition.cognition.dynamic_thinking_integration import get_dynamic_thinking_orchestrator
                orchestrator = get_dynamic_thinking_orchestrator()
                if orchestrator:
                    summary["thought_chains"]["total_orchestrated"] = orchestrator.stats.get("chains_orchestrated", 0)
                    if orchestrator.thought_engine:
                        chains = orchestrator.thought_engine.get_active_chains_summary()
                        summary["thought_chains"]["active_count"] = len(chains)
            except Exception:
                pass
                
            # Gather goal info
            try:
                from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
                autonomy = get_autonomy_fairy()
                if autonomy:
                    goals = getattr(autonomy, 'active_goals', [])
                    summary["goals"]["active_count"] = len(goals)
                    summary["goals"]["from_drives"] = len([g for g in goals if getattr(g, 'source_drive', None)])
                    
                    # Check drives
                    drives = getattr(autonomy, 'drives', {})
                    most_urgent = None
                    max_urgency = 0
                    for name, drive in drives.items():
                        urgency = drive.get_urgency() if hasattr(drive, 'get_urgency') else 0
                        satisfaction = getattr(drive, 'satisfaction', 0.5)
                        
                        if satisfaction > 0.5:
                            summary["drives"]["satisfied_count"] += 1
                        else:
                            summary["drives"]["unsatisfied_count"] += 1
                            
                        if urgency > max_urgency:
                            max_urgency = urgency
                            most_urgent = name
                            
                    summary["drives"]["most_urgent"] = most_urgent
            except Exception:
                pass
                
            # Gather working memory info
            try:
                from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
                hub = get_working_memory_hub()
                if hub:
                    summary["working_memory"]["reflective_tracers"] = len(getattr(hub, 'reflective_tracers', []))
                    summary["working_memory"]["reasoning_tracers"] = len(getattr(hub, 'reasoning_tracers', []))
            except Exception:
                pass
                
            # Determine status
            summary["is_thinking"] = (
                summary["thought_chains"]["active_count"] > 0 or 
                summary["working_memory"]["reasoning_tracers"] > 0
            )
            summary["is_autonomous"] = (
                summary["goals"]["from_drives"] > 0 or
                summary["drives"]["unsatisfied_count"] > 0
            )
            
            # Overall status
            if summary["is_thinking"] and summary["is_autonomous"]:
                summary["overall_status"] = "ACTIVE_AUTONOMOUS"
            elif summary["is_thinking"]:
                summary["overall_status"] = "ACTIVE_COMPELLED"
            elif summary["is_autonomous"]:
                summary["overall_status"] = "IDLE_BUT_DRIVEN"
            else:
                summary["overall_status"] = "DORMANT"
                
            # Generate narrative
            narrative_parts = []
            if summary["thought_chains"]["active_count"] > 0:
                narrative_parts.append(f"{summary['thought_chains']['active_count']} thought chains active")
            if summary["goals"]["active_count"] > 0:
                narrative_parts.append(f"{summary['goals']['active_count']} goals ({summary['goals']['from_drives']} from drives)")
            if summary["drives"]["most_urgent"]:
                narrative_parts.append(f"Most urgent drive: {summary['drives']['most_urgent']}")
            if summary["working_memory"]["reasoning_tracers"] > 0:
                narrative_parts.append(f"Actively reasoning ({summary['working_memory']['reasoning_tracers']} tracers)")
                
            summary["activity_narrative"] = "; ".join(narrative_parts) if narrative_parts else "No significant activity detected"
            
            return json.dumps(summary, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})


# Helper functions for singleton access
# FIX 2026-02-02: Use fairies. prefix for correct import path
def get_thought_chain_engine():
    """Get thought chain engine singleton."""
    try:
        from fairies.P30_Cognition.cognition.thought_chain_engine import get_thought_chain_engine
        return get_thought_chain_engine()
    except ImportError:
        return None

def get_goal_coordinator():
    """Get goal coordinator singleton."""
    try:
        from fairies.P30_Cognition.cognition.smart_goal_coordinator import get_smart_goal_coordinator
        return get_smart_goal_coordinator()
    except ImportError:
        return None

def get_working_memory_hub():
    """Get working memory hub singleton."""
    try:
        from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
        return get_working_memory_hub()
    except ImportError:
        return None
