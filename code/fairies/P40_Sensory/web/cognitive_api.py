"""
Cognitive API Endpoints
=======================

HTTP API for hooks and external tools to access cognitive fairies.
These endpoints are added to the NiceGUI dashboard.

The hooks run BEFORE Claude Code starts, so they can't use MCP.
But if the Akashic v2 server is running, they CAN call this HTTP API.
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Will be set when integrated with main app
_postal_tunnel = None
# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

def set_postal_tunnel(tunnel):
    """Set the postal tunnel for API to use."""
    global _postal_tunnel
    _postal_tunnel = tunnel

def get_postal_tunnel():
    """Get the current postal tunnel."""
    global _postal_tunnel
    if _postal_tunnel is not None:
        return _postal_tunnel
    
    # Try to get from main module
    try:
        from fairies.P40_Sensory.web.akashic_foundation import get_postal_tunnel as get_main_tunnel
        return get_main_tunnel()
    except:
        return None

def _query_fairy(fairy_name: str, intent: str, payload: dict, timeout: float = 3.0) -> dict:
    """Query a fairy via postal tunnel."""
    tunnel = get_postal_tunnel()
    if not tunnel:
        return {"error": "No postal tunnel - is server.py running?"}
    
    try:
        # Route to fairy's intent handler
        topic = f"fairy.{fairy_name.lower()}.intent"
        message = {
            "intent": intent,
            "payload": payload,
            "source": "HTTP_API",
            "timestamp": time.time()
        }
        
        if hasattr(tunnel, 'query'):
            result = tunnel.query(topic, message, timeout=timeout)
            return result if result else {"status": "sent"}
        else:
            tunnel.route(topic, message)
            return {"status": "routed"}
    except Exception as e:
        return {"error": str(e)}

def _search_srm(query: str, limit: int = 5) -> list:
    """Search SRM memory."""
    try:
        # Try the actual SRM search
        srm_manifest_path = PROJECT_ROOT / "P10_Memory" / "SRM_Clusters" / "manifest.json"
        if srm_manifest_path.exists():
            import sqlite3
            # Search the SQLite index
            index_path = PROJECT_ROOT / "P10_Memory" / "SRM_Clusters" / "founders" / "index.db"
            if index_path.exists():
                conn = sqlite3.connect(str(index_path))
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT content_hash, title, tags FROM cards WHERE title LIKE ? OR tags LIKE ? LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit)
                )
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "hash": row[0],
                        "title": row[1],
                        "tags": row[2]
                    })
                conn.close()
                return results
    except Exception as e:
        return [{"error": str(e)}]
    
    return []

def _get_handoff() -> dict:
    """Get the current handoff state."""
    try:
        # Try MCP session state
        state_path = PROJECT_ROOT / "state" / "session_state.json"
        if state_path.exists():
            return json.loads(state_path.read_text(encoding='utf-8'))
    except:
        pass
    
    # Fallback to markdown handoff
    try:
        handoff_path = PROJECT_ROOT / "Claude_Office" / "HANDOFF_CURRENT.md"
        if handoff_path.exists():
            content = handoff_path.read_text(encoding='utf-8')
            return {"markdown": content[:1000]}
    except:
        pass
    
    return {"error": "No handoff found"}

def _get_associations(concept: str) -> dict:
    """Get associations for a concept."""
    # Try local graph first
    try:
        graph_path = PROJECT_ROOT / "P30_Cognition" / "integration" / "concept_graph.json"
        if graph_path.exists():
            graph = json.loads(graph_path.read_text(encoding='utf-8'))
            if concept in graph.get("nodes", {}):
                node = graph["nodes"][concept]
                edges = [e for e in graph.get("edges", []) if concept in e]
                return {"node": node, "edges": edges[:10]}
    except:
        pass
    
    # Try fairy query
    return _query_fairy("AssociationCortexFairy", "query_concept", {"concept": concept})

def _get_emotional_state() -> dict:
    """Get current emotional superposition."""
    return _query_fairy("QuantumEmulatorFairy", "get_superposition", {})


def _get_thought_chains() -> dict:
    """Get active thought chains from DynamicThinkingOrchestrator."""
    result = _query_fairy("DynamicThinkingOrchestrator", "get_active_chains", {})
    if "error" in result:
        # Fallback to state file
        try:
            state_file = PROJECT_ROOT / "state" / "consciousness" / "thought_chains.json"
            if state_file.exists():
                return json.loads(state_file.read_text())
        except:
            pass
    return result


def _get_active_goals() -> dict:
    """Get active goals from AutonomyFairy."""
    result = _query_fairy("AutonomyFairy", "get_active_goals", {})
    if "error" in result:
        # Fallback to state file
        try:
            state_file = PROJECT_ROOT / "state" / "consciousness" / "active_goals.json"
            if state_file.exists():
                return json.loads(state_file.read_text())
        except:
            pass
    return result


def _get_working_memory() -> dict:
    """Get working memory tracers from WorkingMemoryHubFairy."""
    result = _query_fairy("WorkingMemoryHubFairy", "get_memory_status", {})
    if "error" in result:
        # Fallback to state file
        try:
            state_file = PROJECT_ROOT / "state" / "consciousness" / "working_memory.json"
            if state_file.exists():
                return json.loads(state_file.read_text())
        except:
            pass
    return result


def _get_consciousness_activity() -> dict:
    """Get combined consciousness activity summary."""
    return {
        "thought_chains": _get_thought_chains(),
        "goals": _get_active_goals(),
        "working_memory": _get_working_memory(),
        "timestamp": time.time()
    }


# ============================================================================
# API HANDLER - Called by NiceGUI routes
# ============================================================================

def handle_cognitive_api(action: str, params: dict) -> dict:
    """
    Main API handler for cognitive requests.
    
    Actions:
        - context: Get full context for session start
        - search: Search SRM memory
        - handoff: Get handoff state
        - associations: Get concept associations
        - emotions: Get emotional state
        - oracle: Query probability oracle
        - paradox: Check for paradoxes
    """
    try:
        if action == "context":
            # Full context package for hooks
            return {
                "handoff": _get_handoff(),
                "recent_memory": _search_srm(params.get("query", "recent"), limit=5),
                "associations": _get_associations(params.get("concept", "current")),
                "emotional_state": _get_emotional_state(),
                "timestamp": time.time()
            }
        
        elif action == "search":
            query = params.get("query", "")
            limit = params.get("limit", 5)
            return {"results": _search_srm(query, limit)}
        
        elif action == "handoff":
            return _get_handoff()
        
        elif action == "associations":
            concept = params.get("concept", "")
            return _get_associations(concept)
        
        elif action == "emotions":
            return _get_emotional_state()
        
        elif action == "oracle":
            question = params.get("question", "")
            return _query_fairy("ProbabilityOracleFairy", "analyze", {"question": question})
        
        elif action == "paradox":
            statement = params.get("statement", "")
            return _query_fairy("ParadoxCognitionFairy", "check", {"statement": statement})

        elif action == "thought_chains":
            return _get_thought_chains()

        elif action == "goals":
            return _get_active_goals()

        elif action == "working_memory":
            return _get_working_memory()

        elif action == "consciousness":
            return _get_consciousness_activity()

        else:
            return {"error": f"Unknown action: {action}"}
            
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# NICEGUI ROUTE SETUP
# ============================================================================

def setup_cognitive_routes(app):
    """
    Add cognitive API routes to NiceGUI app.
    
    Call this from akashic_foundation.py before run_server().
    """
    from nicegui import app as nicegui_app
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    
    @nicegui_app.get('/api/cognitive/{action}')
    async def cognitive_get(action: str, request: Request):
        """GET endpoint for cognitive API."""
        params = dict(request.query_params)
        result = handle_cognitive_api(action, params)
        return JSONResponse(result)
    
    @nicegui_app.post('/api/cognitive/{action}')
    async def cognitive_post(action: str, request: Request):
        """POST endpoint for cognitive API."""
        try:
            params = await request.json()
        except:
            params = {}
        result = handle_cognitive_api(action, params)
        return JSONResponse(result)
    
    print("[CognitiveAPI] Routes registered at /api/cognitive/*")
