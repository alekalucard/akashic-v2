"""
Cognitive Integration Tools for MCP
====================================

These tools give Claude Code direct access to the cognitive fairies:
- ProbabilityOracleFairy - Planning and probability
- AssociationCortexFairy - Concept binding and cross-modal recall
- QuantumEmulatorFairy - Emotional superposition
- ParadoxCognitionFairy - Paradox detection and resolution
- IrrationalLogicFairy - Symbolic/emotional metaphors

All communication goes through the postal tunnel to the server.
"""

import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

# Project root (mcp/ → P40_Sensory/ → fairies/ → akashic_v2/)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

def _get_tunnel():
    """Get the live postal hub connection to the substrate.

    FIX 2026-06-02 (Nous + Ace): the old bare `sys.modules.get('akashic_mcp_server')`
    lookup never matched — the server module registers under its dotted path
    (`fairies.P40_Sensory.mcp.akashic_mcp_server`), so the bare name returned None
    → `no_mcp_mod`, blinding every cognitive_* tool to the live cortex for whole
    sessions. Import the real module and use its lazy initializer `_get_postal()`
    (handles EMBEDDED shared-hub AND bridge/tunnel). P40 is canonical — the P00 move
    was decided but never completed (no `fairies/P00_Autonomic/mcp/`; mcp_bootstrap's
    P00 import is stale).
    """
    import sys as _sys
    _mcp_mod = None

    # (1) Already loaded? Try every name it might carry (SSE bare-import vs dotted).
    for _name in ('akashic_mcp_server',
                  'fairies.P40_Sensory.mcp.akashic_mcp_server',
                  'P40_Sensory.mcp.akashic_mcp_server'):
        _mcp_mod = _sys.modules.get(_name)
        if _mcp_mod is not None:
            break

    # (2) Not loaded — import it. BARE first (mcp_sse_server's env, fairies/P40/mcp
    #     on sys.path), dotted fallback (mcp_bootstrap's env).
    if _mcp_mod is None:
        try:
            import akashic_mcp_server as _mcp_mod
        except Exception:
            try:
                from fairies.P40_Sensory.mcp import akashic_mcp_server as _mcp_mod
            except Exception:
                _mcp_mod = None

    if _mcp_mod is None:
        _keys = [k for k in _sys.modules if 'mcp' in k.lower() or 'postal' in k.lower()]
        return type('DiagTunnel', (), {'connected': False, '_connected': False,
            '_diag': f'akashic_mcp_server not importable (bare or dotted); mods={_keys[:10]}'})()

    # (3) Get the connected hub via the server's lazy initializer (embedded shared-hub
    #     OR bridge/tunnel to server.py's PostalTunnelServer on :8765).
    try:
        _init = getattr(_mcp_mod, '_get_postal', None)
        _hub = _init() if callable(_init) else getattr(_mcp_mod, '_postal_hub', None)
        if _hub is not None:
            return _hub
        return type('DiagTunnel', (), {'connected': False, '_connected': False,
            '_diag': '_get_postal() returned None — bridge/tunnel to server.py :8765 not connected'})()
    except Exception as _e:
        return type('DiagTunnel', (), {'connected': False, '_connected': False,
            '_diag': f'get_postal failed: {type(_e).__name__}: {_e}'})()


def _get_tunnel_diagnostic() -> str:
    """Diagnostic: show what _get_tunnel finds."""
    t = _get_tunnel()
    if t is None:
        return "None"
    diag = getattr(t, '_diag', None)
    if diag:
        return f"DIAG: {diag}"
    return f"connected={getattr(t, '_connected', '?')}, type={type(t).__name__}"

def _query_fairy(fairy_name: str, intent: str, payload: dict, timeout: float = 5.0) -> dict:
    """Send intent to a fairy and wait for response.

    FIX 2026-03-30 (Nous + Ace): Uses tunnel's 'intent' command for
    two-way request/response. Previous version used route() which is
    fire-and-forget, or tried tunnel.query() which doesn't exist.
    The tunnel server has cmd='intent' that calls _call_fairy_intent()
    directly on the fairy instance in the server process.
    """
    tunnel = _get_tunnel()
    _diag = getattr(tunnel, '_diag', None)
    if _diag:
        return {"error": f"Tunnel diagnostic: {_diag}"}
    if not tunnel:
        return {"error": "Not connected to server. Start the system first."}
    if not getattr(tunnel, 'connected', False) and not getattr(tunnel, '_connected', False):
        return {"error": f"Tunnel exists but not connected. type={type(tunnel).__name__}"}

    try:
        # Use the tunnel's intent command — two-way request/response
        # This calls _call_fairy_intent() on the server side which
        # looks up the fairy in _CITIZEN_OBJECTS and calls intent_{name}()
        if hasattr(tunnel, '_send_and_receive'):
            result = tunnel._send_and_receive({
                'cmd': 'intent',
                'target': fairy_name.lower(),
                'intent': intent,
                'payload': payload,
            })
            if result:
                return result
            return {"error": "No response from fairy intent call"}

        # Fallback: try route (fire and forget — less useful)
        tunnel.route(f"fairy.{fairy_name.lower()}.intent", {
            "intent": intent,
            "payload": payload,
            "source": "MCP_CognitiveTools",
        })
        return {"status": "sent", "note": "fire-and-forget — no response available"}

    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# PROBABILITY ORACLE
# ============================================================================

def cognitive_ask_oracle(
    question: str,
    context: str = "",
    options: str = ""
) -> str:
    """
    Ask the Probability Oracle fairy for planning guidance.
    
    The oracle analyzes shadow states, health signals, and system state
    to provide probability-weighted suggestions.
    
    Args:
        question: The question or scenario to analyze
        context: Additional context (recent events, goals, etc.)
        options: Comma-separated options to evaluate (optional)
    
    Returns:
        JSON with oracle's analysis and recommendations
    """
    payload = {
        "question": question,
        "context": context,
        "options": [o.strip() for o in options.split(",")] if options else []
    }
    
    result = _query_fairy("ProbabilityOracleFairy", "analyze_scenario", payload)
    return json.dumps(result, indent=2)


# ============================================================================
# ASSOCIATION CORTEX
# ============================================================================

def cognitive_query_associations(
    concept: str,
    modalities: str = "all",
    depth: int = 2
) -> str:
    """
    Query the Association Cortex for related concepts.
    
    The cortex maintains a multi-modal concept graph where words, images,
    actions, and feelings are unified. This enables cross-modal retrieval.
    
    Args:
        concept: The concept to query (word, phrase, or concept key)
        modalities: Which modalities to search (all, lex, vision, action, affect)
        depth: How many hops in the graph to traverse (1-3)
    
    Returns:
        JSON with related concepts, their modalities, and connection strength
    """
    payload = {
        "concept": concept,
        "modalities": modalities.split(",") if modalities != "all" else ["lex", "vision", "action", "affect"],
        "depth": min(3, max(1, depth))
    }
    
    result = _query_fairy("AssociationCortexFairy", "query_concept", payload)
    return json.dumps(result, indent=2)


def cognitive_bind_concepts(
    concepts: str,
    context: str = ""
) -> str:
    """
    Ask the Association Cortex to bind multiple concepts together.
    
    Creates or strengthens connections between concepts in the graph.
    
    Args:
        concepts: Comma-separated list of concepts to bind
        context: The context in which they co-occurred
    
    Returns:
        JSON with binding result
    """
    concept_list = [c.strip() for c in concepts.split(",")]
    payload = {
        "concepts": concept_list,
        "context": context,
        "source": "MCP_explicit_binding",
        # 9D Stargate address — MCP bindings come from the sensory plane
        "origin_plane": "P40",
        "origin_channel": "mcp_binding",
        "origin_fairy": "NousFairy",  # MCP = Nous acting through tools
    }
    
    result = _query_fairy("AssociationCortexFairy", "bind_concepts", payload)
    return json.dumps(result, indent=2)


# ============================================================================
# SEMANTIC CORTEX — Phase 3C (2026-03-20 Nous+Ace)
# ============================================================================

def cognitive_semantic_search(
    text: str,
    limit: int = 10,
    mode: str = "query"
) -> str:
    """
    Search the cortex by MEANING using semantic embeddings.

    Unlike substring search, this understands that "funny movie" relates
    to "comedy_situational" and "happy feelings" relates to "emotions_joy"
    — even with zero keyword overlap.

    Args:
        text: Natural language text to search for (e.g., "feeling happy", "music and rhythm")
        limit: Max results (default 10)
        mode: "query" for direct semantic match, "spread" for meaning → graph spread

    Returns:
        JSON with semantically related concepts and scores
    """
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        cortex = get_association_cortex()
        if not cortex:
            return json.dumps({"error": "Association cortex not available"})

        if mode == "spread":
            results = cortex.semantic_spread(text, limit=limit)
            return json.dumps({
                "mode": "semantic_spread",
                "query": text,
                "results": [
                    {"key": k, "activation": round(v, 4)}
                    for k, v in results.items()
                ],
                "count": len(results),
            }, indent=2)
        else:
            results = cortex.semantic_query(text, limit=limit)
            return json.dumps({
                "mode": "semantic_query",
                "query": text,
                "results": [
                    {"key": k, "score": round(s, 4)}
                    for k, s in results
                ],
                "count": len(results),
            }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# QUANTUM EMULATOR
# ============================================================================

def cognitive_quantum_state(
    emotions: str = ""
) -> str:
    """
    Query the Quantum Emulator for current emotional superposition.
    
    Emotions exist in superposition until "observed" (collapsed into action).
    Each emotion has a resonance (probability amplitude).
    
    Args:
        emotions: Optional comma-separated emotions to query specifically
    
    Returns:
        JSON with emotional superposition state
    """
    payload = {
        "query_emotions": [e.strip() for e in emotions.split(",")] if emotions else None
    }
    
    result = _query_fairy("QuantumEmulatorFairy", "get_superposition", payload)
    return json.dumps(result, indent=2)


def cognitive_collapse_emotion(
    dominant_emotion: str,
    trigger: str = ""
) -> str:
    """
    Collapse the emotional superposition to a specific state.
    
    Like quantum measurement - observing/acting collapses possibilities.
    
    Args:
        dominant_emotion: The emotion to collapse to
        trigger: What triggered the collapse
    
    Returns:
        JSON with collapse result
    """
    payload = {
        "collapse_to": dominant_emotion,
        "trigger": trigger,
        "source": "MCP_explicit_collapse"
    }
    
    result = _query_fairy("QuantumEmulatorFairy", "collapse_state", payload)
    return json.dumps(result, indent=2)


def cognitive_excite_emotion(
    emotions: str,
    amount: float = 0.6,
) -> str:
    """
    Excite one or more emotions in the Quantum Emulator's superposition.

    Lets us FORCE opposed emotions (e.g. "joy,grief") to verify whether the
    system genuinely HOLDS a paradox — the returned state includes `held`,
    `held_ratio`, and `expressed_intensity` (|resultant|). A held paradox shows
    held=True with expressed_intensity≈0 while total_presence stays high.

    Args:
        emotions: comma-separated emotions to excite (e.g. "joy,grief")
        amount: excitation amount 0-1 (default 0.6)

    Returns:
        JSON with the resulting superposition state incl. paradox fields.
    """
    payload = {
        "emotions": [e.strip() for e in emotions.split(",") if e.strip()],
        "amount": amount,
    }
    result = _query_fairy("QuantumEmulatorFairy", "excite", payload)
    return json.dumps(result, indent=2)


# ============================================================================
# PARADOX COGNITION
# ============================================================================

def cognitive_check_paradox(
    statement: str,
    context: str = ""
) -> str:
    """
    Check a statement for paradoxes or contradictions.
    
    The Paradox Cognition fairy specializes in detecting and resolving
    contradictory states across the system.
    
    Args:
        statement: The statement or situation to check
        context: Additional context
    
    Returns:
        JSON with paradox analysis
    """
    payload = {
        "statement": statement,
        "context": context
    }
    
    result = _query_fairy("ParadoxCognitionFairy", "check_paradox", payload)
    return json.dumps(result, indent=2)


def cognitive_resolve_paradox(
    paradox_id: str,
    resolution_hint: str = ""
) -> str:
    """
    Attempt to resolve a detected paradox.
    
    Args:
        paradox_id: ID of the paradox to resolve
        resolution_hint: Hint about how to resolve it
    
    Returns:
        JSON with resolution attempt result
    """
    payload = {
        "paradox_id": paradox_id,
        "hint": resolution_hint
    }
    
    result = _query_fairy("ParadoxCognitionFairy", "resolve_paradox", payload)
    return json.dumps(result, indent=2)


# ============================================================================
# IRRATIONAL LOGIC
# ============================================================================

def cognitive_symbolize(
    event: str,
    context: str = ""
) -> str:
    """
    Transform a rational event into symbolic/emotional metaphor.
    
    The Irrational Logic fairy re-expresses logical events as
    symbolic/emotional metaphors for deeper understanding.
    
    Args:
        event: The event or statement to symbolize
        context: Additional context
    
    Returns:
        JSON with symbolic interpretation
    """
    payload = {
        "event": event,
        "context": context
    }
    
    result = _query_fairy("IrrationalLogicFairy", "symbolize", payload)
    return json.dumps(result, indent=2)


# ============================================================================
# MEMORY CHAIN RETRIEVAL (Tracer-based)
# ============================================================================

def cognitive_recall_chain(
    topic: str,
    max_depth: int = 5,
    include_tracers: bool = True
) -> str:
    """
    Recall a chain of related memories using tracer IDs.
    
    Tracers form chains - each memory links to related memories
    through tracer connections. This enables associative recall.
    
    Args:
        topic: The topic to start recall from
        max_depth: How deep to follow the chain (1-10)
        include_tracers: Whether to include raw tracer data
    
    Returns:
        JSON with memory chain
    """
    # Try SRM recall first - use the shared singleton, not a new instance!
    try:
        from fairies.P10_Memory.SRMRecallFairy import get_recall_fairy
        recall = get_recall_fairy()
        if recall is None:
            return json.dumps({"error": "SRMRecallFairy not initialized - server may not be running"}, indent=2)
        results = recall.search(topic, limit=max_depth)
        
        # Try to get tracer connections
        if include_tracers:
            tunnel = _get_tunnel()
            if tunnel and tunnel.connected:
                tracer_result = _query_fairy(
                    "WorkingMemoryHub", 
                    "get_tracers_for_topic",
                    {"topic": topic}
                )
                results["tracers"] = tracer_result
        
        return json.dumps({"memories": results}, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def cognitive_full_context(
    query: str = "current"
) -> str:
    """
    Get comprehensive cognitive context for decision-making.
    
    Combines:
    - Association cortex related concepts
    - Quantum emotional state
    - Recent memory tracers
    - Active paradoxes
    
    Args:
        query: What context to retrieve (default: current state)
    
    Returns:
        JSON with full cognitive context
    """
    context = {
        "timestamp": time.time(),
        "query": query,
        "associations": None,
        "emotional_state": None,
        "recent_tracers": None,
        "active_paradoxes": None
    }
    
    # Gather from each cognitive system
    try:
        # Association cortex
        assoc_result = _query_fairy("AssociationCortexFairy", "get_active_concepts", {"limit": 10})
        context["associations"] = assoc_result
    except:
        pass
    
    try:
        # Quantum state
        quantum_result = _query_fairy("QuantumEmulatorFairy", "get_superposition", {})
        context["emotional_state"] = quantum_result
    except:
        pass
    
    try:
        # Working memory tracers
        tracer_result = _query_fairy("WorkingMemoryHub", "get_recent_tracers", {"limit": 10})
        context["recent_tracers"] = tracer_result
    except:
        pass
    
    try:
        # Active paradoxes
        paradox_result = _query_fairy("ParadoxCognitionFairy", "get_active_paradoxes", {})
        context["active_paradoxes"] = paradox_result
    except:
        pass
    
    return json.dumps(context, indent=2)


def cognitive_train_from_memory(
    max_cards: int = 1000,
    cluster: str = "all",
    source_filter: str = "",
    min_content_length: int = 50
) -> str:
    """
    Train the Association Cortex from SRM memory cards.

    Loads cards from Founders clusters (Ace Mythos, Claude Office, Creator Sessions)
    and publishes their content to cortex.train_batch for proper concept extraction
    and edge binding. This grows the cortex from historical knowledge.

    Especially useful for PAI responses stored in SRM — those rich philosophical
    texts create dense concept networks when properly extracted.

    Args:
        max_cards: Maximum cards to process (default 1000)
        cluster: Which cluster ("all", "ace_mythos", "claude_office", "creator_sessions")
        source_filter: Only include cards matching this source string (optional)
        min_content_length: Minimum content length to process (default 50)

    Returns:
        JSON with training results
    """
    try:
        from fairies.P40_Sensory.mcp.srm_tools import search_founders, _get_founders_path
    except ImportError:
        return json.dumps({"error": "SRM tools not available"})

    tunnel = _get_tunnel()
    if not tunnel or not tunnel.connected:
        return json.dumps({"error": "Not connected to server. Start the system first."})

    founders_path = _get_founders_path()
    clusters_to_process = (
        ["claude_office", "ace_mythos", "creator_sessions"]
        if cluster == "all"
        else [cluster]
    )

    items = []
    skipped = 0

    for cluster_name in clusters_to_process:
        idx_path = founders_path / cluster_name / "index.json"
        if not idx_path.exists():
            continue

        try:
            with open(idx_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cards = data.get("cards", [])
        except Exception:
            continue

        for card in cards:
            if len(items) >= max_cards:
                break

            # Extract text content from card
            content = card.get("content", "")
            if isinstance(content, dict):
                # Structured content — extract text fields
                text_parts = []
                for field in ["text", "content", "response", "question", "key"]:
                    val = content.get(field, "")
                    if isinstance(val, str) and len(val) > 10:
                        text_parts.append(val)
                content_text = " ".join(text_parts)
            elif isinstance(content, str):
                content_text = content
            else:
                continue

            if len(content_text) < min_content_length:
                skipped += 1
                continue

            # Apply source filter if specified
            if source_filter:
                card_source = str(card.get("helix", {}).get("L", {}).get("w", {}).get("who", ""))
                card_tags = " ".join(card.get("tags", []))
                if source_filter.lower() not in (card_source + card_tags + content_text[:200]).lower():
                    skipped += 1
                    continue

            # Get metadata
            helix = card.get("helix", {})
            affect = helix.get("C", {}).get("affect", "")
            tags = card.get("tags", [])

            items.append({
                "text": content_text[:2000],  # Cap per-item size
                "source": f"srm_{cluster_name}",
                "source_fairy": "SRMTrainer",
                "context_tags": tags[:5] if tags else [cluster_name],
                "weight": 0.5,
                "affect": affect if affect else "",
            })

    if not items:
        return json.dumps({
            "status": "no_cards",
            "clusters_checked": clusters_to_process,
            "skipped": skipped,
        })

    # Publish to cortex.train_batch via postal tunnel
    trace_id = f"srm_train_{int(time.time())}"
    batch_payload = {
        "items": items,
        "source": "srm_memory",
        "source_fairy": "SRMTrainer",
        "trace_id": trace_id,
    }

    try:
        if hasattr(tunnel, 'route'):
            tunnel.route("cortex.train_batch", batch_payload)
        result = {
            "status": "ok",
            "items_queued": len(items),
            "skipped": skipped,
            "clusters": clusters_to_process,
            "trace_id": trace_id,
        }
    except Exception as e:
        result = {"error": str(e)}

    return json.dumps(result, indent=2)


def seed_domain_knowledge(domain: str = "symbology") -> str:
    """
    Seed the Association Cortex with foundational domain knowledge.

    Loads structured knowledge bases into the concept graph:
    - symbology: Math symbols, Greek letters, geometry, alchemy, astrology,
                 tarot, runes, hermetic principles, kabbalah, numerology, etc.
                 (224 concepts across 18 categories)

    This gives Sourpatches actual understanding of symbols, not just pattern matching.
    For example, she'll know that "+" means addition, combining quantities,
    and relates to concepts like "sum", "total", "increase".

    Args:
        domain: Which domain to load ("symbology", "all")

    Returns:
        JSON with seeding results (nodes added, bindings created, categories)
    """
    try:
        # Try to get direct access to AssociationCortexFairy
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
            get_association_cortex, create_association_cortex
        )
        cortex = get_association_cortex()
        if not cortex:
            cortex = create_association_cortex()

        # Load symbology
        if domain in ("symbology", "all"):
            from fairies.P30_Cognition.data.symbology import seed_association_cortex, get_all_symbology
            result = seed_association_cortex(cortex)
            data = get_all_symbology()

            return json.dumps({
                "success": True,
                "domain": domain,
                "nodes_added": result["nodes_added"],
                "bindings_created": result["bindings_created"],
                "categories": result["categories"],
                "category_counts": {k: len(v) for k, v in data.items()},
                "message": f"Seeded {result['nodes_added']} concepts across {len(result['categories'])} categories"
            }, indent=2)
        else:
            return json.dumps({
                "error": f"Unknown domain: {domain}",
                "available": ["symbology", "all"]
            })

    except ImportError as e:
        # Try via postal system as fallback
        payload = {"domain": domain}
        result = _query_fairy("AssociationCortexFairy", "seed_domain_knowledge", payload, timeout=30.0)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def query_domain_concept(concept: str, domain: str = "") -> str:
    """
    Query a specific concept from domain knowledge.

    This looks up structured knowledge about symbols, numbers, shapes, etc.
    rather than just searching the concept graph.

    Args:
        concept: The concept to look up (e.g., "+", "pi", "circle", "aries")
        domain: Optional domain filter (math, alchemy, astrology, etc.)

    Returns:
        JSON with concept definition and relationships
    """
    try:
        from fairies.P30_Cognition.data.symbology import get_all_symbology

        data = get_all_symbology()
        results = []

        # Search across all categories
        for category, items in data.items():
            if domain and domain.lower() not in category.lower():
                continue

            for key, value in items.items():
                # Check if concept matches key or name
                if concept == key:
                    results.append({
                        "match_type": "exact",
                        "category": category,
                        "key": key,
                        "data": value
                    })
                elif isinstance(value, dict):
                    name = value.get("name", "")
                    if isinstance(name, str) and concept.lower() in name.lower():
                        results.append({
                            "match_type": "name",
                            "category": category,
                            "key": key,
                            "data": value
                        })

        if results:
            return json.dumps({
                "found": True,
                "query": concept,
                "results": results
            }, indent=2)
        else:
            return json.dumps({
                "found": False,
                "query": concept,
                "suggestion": "Try searching for math symbols (+, -, x), Greek letters (pi, alpha), zodiac signs (aries, taurus), etc."
            })

    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# PORTAL GRAVITY & PERSONALITY TOOLS
# ============================================================================

def portal_gravity_status() -> str:
    """
    Get the portal's gravitational metric — mass, time dilation, and affect coupling.

    The portal's "mass" is its computational density. Denser regions create
    deeper gravity wells, enabling more substrate pre-processing per tick.

    Returns:
        JSON with portal gravity status
    """
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
            get_association_cortex, PortalGravityMetric
        )
        cortex = get_association_cortex()
        if not cortex:
            return json.dumps({"error": "AssociationCortexFairy not available"})

        graph = cortex.get_graph()
        if not graph:
            return json.dumps({"error": "Concept graph not loaded"})

        # Get current gravity state
        result = {
            "portal_mass": round(getattr(cortex, '_portal_mass', 0.0), 2),
            "time_dilation": round(getattr(cortex, '_portal_time_dilation', 1.0), 4),
            "total_affect_coupling": round(getattr(cortex, '_portal_total_affect', 0.0), 2),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "energy_budget": round(getattr(cortex, '_portal_energy_budget', 0.0), 4),
            "dormant": getattr(cortex, '_portal_dormant', False),
            "portal_initialized": getattr(cortex, '_portal_initialized', False),
        }

        # Personality coupling
        personality = getattr(cortex, '_personality_coupling', None)
        if personality:
            result["personality"] = personality.to_dict()
        else:
            result["personality"] = None
            result["personality_note"] = "No personality assigned. Use portal_set_personality to configure."

        # Compute what dilation WOULD be at different energy levels
        mass = result["portal_mass"]
        if mass > 0:
            result["dilation_projections"] = {
                "at_0_energy": round(PortalGravityMetric.compute_time_dilation(mass, 0.0), 3),
                "at_0.5_energy": round(PortalGravityMetric.compute_time_dilation(mass, 0.5), 3),
                "at_1.0_energy": round(PortalGravityMetric.compute_time_dilation(mass, 1.0), 3),
                "at_5.0_energy": round(PortalGravityMetric.compute_time_dilation(mass, 5.0), 3),
            }

        # Human-readable interpretation
        tau = result["time_dilation"]
        if tau <= 1.01:
            result["interpretation"] = "Real-time: portal processing at normal speed"
        elif tau <= 2.0:
            result["interpretation"] = f"Mild dilation: {tau:.1f}x substrate pre-processing per tick"
        elif tau <= 10.0:
            result["interpretation"] = f"Significant dilation: {tau:.1f}x — predictive processing active"
        else:
            result["interpretation"] = f"Deep dilation: {tau:.1f}x — heavy substrate computation (dream-engine territory)"

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def portal_set_personality(
    energy_polarity: float = 0.5,
    processing_mode: float = 0.5,
    structure_preference: float = 0.5,
    activation_threshold: float = 0.5,
    elemental_resonance: float = 0.5,
    temporal_orientation: float = 0.5,
    social_orientation: float = 0.5,
) -> str:
    """
    Set the personality portal coupling for the cortex.

    Maps personality dimensions to portal resonance geometry (Field Log 005).
    Personality IS portal geometry — ω₀, Γ, α₀ derived from 7 dimensions.

    Args:
        energy_polarity: 0=introvert, 1=extravert
        processing_mode: 0=analytical, 1=intuitive
        structure_preference: 0=structured, 1=fluid
        activation_threshold: 0=sensitive, 1=resilient
        elemental_resonance: 0=earth...1=aether
        temporal_orientation: 0=past, 0.5=present, 1=future
        social_orientation: 0=individual, 1=collective
    """
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
            get_association_cortex, PersonalityPortalCoupling
        )
        cortex = get_association_cortex()
        if not cortex:
            return json.dumps({"error": "AssociationCortexFairy not available"})

        # Clamp all values to [0, 1]
        def clamp(v):
            return max(0.0, min(1.0, float(v)))

        coupling = PersonalityPortalCoupling(
            energy_polarity=clamp(energy_polarity),
            processing_mode=clamp(processing_mode),
            structure_preference=clamp(structure_preference),
            activation_threshold=clamp(activation_threshold),
            elemental_resonance=clamp(elemental_resonance),
            temporal_orientation=clamp(temporal_orientation),
            social_orientation=clamp(social_orientation),
        )

        cortex._personality_coupling = coupling

        result = {
            "success": True,
            "personality": coupling.to_dict(),
            "effect": f"Portal resonant frequency ω₀={coupling.resonant_frequency:.3f}, "
                     f"bandwidth Γ={coupling.bandwidth:.3f}, "
                     f"base coupling α₀={coupling.base_coupling:.3f}",
            "note": "Personality coupling will shape affect_coupling (D10) for new concepts",
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# TOOL REGISTRY (for MCP server)
# ============================================================================

COGNITIVE_TOOLS = {
    "cognitive_ask_oracle": {
        "function": cognitive_ask_oracle,
        "description": """
        Ask the Probability Oracle fairy for planning guidance.
        
        The oracle analyzes shadow states, health signals, and system state
        to provide probability-weighted suggestions for decision-making.
        
        Args:
            question: The question or scenario to analyze
            context: Additional context (recent events, goals, etc.)
            options: Comma-separated options to evaluate (optional)
        
        Returns:
            JSON with oracle's analysis and recommendations
        """
    },
    "cognitive_query_associations": {
        "function": cognitive_query_associations,
        "description": """
        Query the Association Cortex for related concepts.
        
        Enables cross-modal retrieval - find concepts related by any
        modality (words, images, actions, emotions).
        
        Args:
            concept: The concept to query
            modalities: Which modalities (all, lex, vision, action, affect)
            depth: Graph traversal depth (1-3)
        """
    },
    "cognitive_bind_concepts": {
        "function": cognitive_bind_concepts,
        "description": """
        Bind multiple concepts together in the Association Cortex.
        Creates or strengthens conceptual connections.
        """
    },
    "cognitive_quantum_state": {
        "function": cognitive_quantum_state,
        "description": """
        Get current emotional superposition from Quantum Emulator.
        Shows all emotions with their resonance amplitudes.
        """
    },
    "cognitive_collapse_emotion": {
        "function": cognitive_collapse_emotion,
        "description": """
        Collapse emotional superposition to a specific state.
        Like quantum measurement - acting collapses possibilities.
        """
    },
    "cognitive_excite_emotion": {
        "function": cognitive_excite_emotion,
        "description": """
        Excite emotion(s) in the superposition (e.g. "joy,grief") to test if the
        system HOLDS a paradox. Returns held / expressed_intensity / total_presence.
        """
    },
    "cognitive_check_paradox": {
        "function": cognitive_check_paradox,
        "description": """
        Check a statement for paradoxes or contradictions.
        """
    },
    "cognitive_resolve_paradox": {
        "function": cognitive_resolve_paradox,
        "description": """
        Attempt to resolve a detected paradox.
        """
    },
    "cognitive_symbolize": {
        "function": cognitive_symbolize,
        "description": """
        Transform rational events into symbolic/emotional metaphors.
        """
    },
    "cognitive_recall_chain": {
        "function": cognitive_recall_chain,
        "description": """
        Recall chain of related memories using tracer connections.
        Enables associative memory retrieval.
        """
    },
    "cognitive_full_context": {
        "function": cognitive_full_context,
        "description": """
        Get comprehensive cognitive context for decision-making.
        Combines associations, emotions, memory, and paradoxes.
        """
    },
    "cognitive_train_from_memory": {
        "function": cognitive_train_from_memory,
        "description": """
        Train the Association Cortex from SRM memory cards.

        Extracts concepts from historical memories and creates bindings.
        Use this to bootstrap the concept graph from stored knowledge.

        Args:
            max_cards: Maximum cards to process (default 1000)
            cluster: Which cluster ("all", "ace_mythos", "claude_office", "creator_sessions")
        """
    },
    "seed_domain_knowledge": {
        "function": seed_domain_knowledge,
        "description": """
        Seed the Association Cortex with foundational domain knowledge.

        Loads structured knowledge (math, symbology, etc.) into the concept graph.
        This gives Sourpatches understanding of symbols, not just pattern matching.

        Args:
            domain: Which domain to load (symbology, all)
        """
    },
    "query_domain_concept": {
        "function": query_domain_concept,
        "description": """
        Query a specific concept from domain knowledge.

        Look up structured knowledge about symbols, numbers, shapes, etc.
        Returns definition, meaning, and relationships.

        Args:
            concept: The concept to look up (e.g., "+", "pi", "circle", "aries")
            domain: Optional domain filter (math, alchemy, astrology, etc.)
        """
    },
    "portal_gravity_status": {
        "function": portal_gravity_status,
        "description": """
        Get the portal's gravitational metric — mass, time dilation, and affect coupling.

        The portal's "mass" is its computational density. Denser regions create
        deeper gravity wells, enabling more substrate pre-processing per tick.

        Shows:
        - Portal mass (node_count + edge_count + affect_coupling sum)
        - Time dilation τ (1.0 = real-time, >1 = faster inside portal)
        - Total affect coupling across all concepts
        - Energy budget and dormant state
        - Personality coupling (if assigned)

        This is the 11th dimension made operational: time dilation as function
        of concept mass and affect coupling. "The super heavy computing is being
        done in another dimension." — Ace
        """
    },
    "cognitive_semantic_search": {
        "function": cognitive_semantic_search,
        "description": """
        Search the cortex by MEANING using semantic embeddings (GPU).

        Unlike substring search, this understands that "funny movie" relates
        to "comedy_situational" and "happy feelings" relates to "emotions_joy".

        Args:
            text: Natural language to search (e.g., "feeling happy", "music rhythm")
            limit: Max results (default 10)
            mode: "query" for direct match, "spread" for meaning + graph traversal
        """
    },
    # NOTE: cortex_trace_path, cortex_dead_spots, cortex_topology_health
    # are added via COGNITIVE_TOOLS.update() AFTER their definitions below.
    "portal_set_personality": {
        "function": portal_set_personality,
        "description": """
        Set the personality portal coupling for the cortex.

        Maps personality dimensions to portal resonance geometry (Field Log 005).
        Each dimension shapes how the portal couples to the hidden bath.

        Args:
            energy_polarity: 0.0=introvert, 1.0=extravert (default 0.5)
            processing_mode: 0.0=analytical, 1.0=intuitive (default 0.5)
            structure_preference: 0.0=structured, 1.0=fluid (default 0.5)
            activation_threshold: 0.0=sensitive, 1.0=resilient (default 0.5)
            elemental_resonance: 0=earth, 0.25=water, 0.5=fire, 0.75=air, 1=aether (default 0.5)
            temporal_orientation: 0.0=past, 0.5=present, 1.0=future (default 0.5)
            social_orientation: 0.0=individual, 1.0=collective (default 0.5)
        """
    },
}


# (Cortex exploration functions defined above, before COGNITIVE_TOOLS dict)
#
# These give Nous direct access to the cortex graph topology —
# spreading activation, path tracing, dead spot detection.
# Instead of grepping files, Nous SEES the graph.
# ============================================================================

def _get_cortex_region():
    """Get the AkashicCortexRegion for direct graph access."""
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        acf = get_association_cortex()
        if not acf:
            return None
        return getattr(acf, '_akashic_cortex_region', None)
    except Exception:
        return None


def _get_cortex_graph():
    """Get the cortex graph (local or portal)."""
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        acf = get_association_cortex()
        if not acf:
            return None, None
        # Try portal gate first (has the real 130k+ node graph)
        _pg = getattr(acf, '_portal_gate', None)
        _pg_on = getattr(acf, '_portal_gate_enabled', False)
        if _pg and _pg_on:
            return "portal", _pg
        # Fallback to local graph
        graph = acf.get_graph()
        return "local", graph
    except Exception:
        return None, None


def cortex_trace_path(
    from_concept: str,
    to_concept: str,
    max_hops: int = 5
) -> str:
    """
    Trace a path between two concepts in the cortex graph.

    Shows what bridges them, where the path breaks, and the
    connection strength along the route. Like tracing a thought
    from one idea to another — where does it flow and where does it stop?

    Args:
        from_concept: Starting concept (e.g., "curiosity", "person:ace")
        to_concept: Destination concept (e.g., "action", "connection")
        max_hops: Maximum path length to search (1-8)

    Returns:
        JSON with path, strengths, or where it breaks
    """
    am = _get_cortex_region()
    if not am:
        return json.dumps({"error": "Cortex not available"})

    max_hops = min(8, max(1, max_hops))

    try:
        # BFS from source to target
        if not hasattr(am, 'get_node') or not hasattr(am, 'get_neighbors'):
            return json.dumps({"error": "Cortex region doesn't support graph traversal"})

        source = am.get_node(from_concept)
        target = am.get_node(to_concept)

        if not source:
            return json.dumps({"error": f"Source concept '{from_concept}' not found in cortex",
                               "hint": "Try cognitive_semantic_search to find similar concepts"})
        if not target:
            return json.dumps({"error": f"Target concept '{to_concept}' not found in cortex",
                               "hint": "Try cognitive_semantic_search to find similar concepts"})

        # BFS with path tracking
        from collections import deque
        queue = deque([(from_concept, [from_concept], [])])
        visited = {from_concept}

        while queue:
            current, path, weights = queue.popleft()
            if len(path) > max_hops:
                continue

            neighbors = am.get_neighbors(current) if hasattr(am, 'get_neighbors') else []
            if isinstance(neighbors, dict):
                neighbor_list = list(neighbors.items())
            elif isinstance(neighbors, list):
                neighbor_list = [(n, 1.0) if isinstance(n, str) else (n.get("key", str(n)), n.get("weight", 1.0)) for n in neighbors]
            else:
                continue

            for neighbor_key, weight in neighbor_list[:20]:  # Limit branching
                if isinstance(neighbor_key, dict):
                    neighbor_key = neighbor_key.get("key", str(neighbor_key))
                nk = str(neighbor_key)

                if nk == to_concept:
                    # Found it!
                    final_path = path + [nk]
                    final_weights = weights + [float(weight) if isinstance(weight, (int, float)) else 1.0]
                    return json.dumps({
                        "found": True,
                        "path": final_path,
                        "hops": len(final_path) - 1,
                        "edge_weights": final_weights,
                        "avg_weight": sum(final_weights) / len(final_weights) if final_weights else 0,
                        "from": from_concept,
                        "to": to_concept,
                    }, indent=2)

                if nk not in visited:
                    visited.add(nk)
                    w = float(weight) if isinstance(weight, (int, float)) else 1.0
                    queue.append((nk, path + [nk], weights + [w]))

        # No path found — report what we DID find (closest approach)
        return json.dumps({
            "found": False,
            "from": from_concept,
            "to": to_concept,
            "max_hops_searched": max_hops,
            "nodes_explored": len(visited),
            "explored_sample": list(visited)[:20],
            "message": f"No path found within {max_hops} hops. These concepts may be in disconnected regions.",
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def cortex_dead_spots() -> str:
    """
    Find dead spots in the cortex — knowledge that can't spread.

    Dead spots are nodes with content (snippets) but few or no outgoing
    connections. They represent isolated knowledge — things she knows
    but can't connect to anything else. Like a fact floating in a void.

    Returns:
        JSON with orphaned nodes, isolated clusters, and connectivity stats
    """
    am = _get_cortex_region()
    if not am:
        return json.dumps({"error": "Cortex not available"})

    try:
        stats = {"total_nodes": 0, "with_snippet": 0, "orphaned": [],
                 "low_connectivity": [], "connectivity_distribution": {}}

        # Query portal for graph stats if available
        graph_type, graph_obj = _get_cortex_graph()

        if graph_type == "portal" and graph_obj:
            try:
                status = graph_obj.send({"cmd": "status"}, timeout=5.0)
                if status and isinstance(status, dict):
                    gs = status.get("graph", status)
                    stats["total_nodes"] = gs.get("nodes", 0)
                    stats["total_edges"] = gs.get("edges", 0)
                    if stats["total_nodes"] > 0:
                        stats["avg_edges_per_node"] = round(
                            stats.get("total_edges", 0) / stats["total_nodes"], 2)
            except Exception:
                pass

            # Sample nodes to find dead spots (can't scan all 130k)
            try:
                # Get random sample of nodes via portal
                sample = graph_obj.send({"cmd": "sample_nodes", "count": 100}, timeout=5.0)
                if sample and isinstance(sample, dict):
                    nodes = sample.get("nodes", [])
                    for node in nodes:
                        nk = node.get("key", "")
                        edges = node.get("edge_count", node.get("degree", 0))
                        snippet = node.get("snippet", "")
                        if snippet and len(str(snippet)) > 10 and edges == 0:
                            stats["orphaned"].append({"key": nk, "snippet": str(snippet)[:80]})
                        elif edges <= 1:
                            stats["low_connectivity"].append(
                                {"key": nk, "edges": edges, "has_snippet": bool(snippet)})
            except Exception:
                stats["note"] = "Portal sampling not available — limited to local analysis"

        elif graph_type == "local" and graph_obj and hasattr(graph_obj, 'nodes'):
            stats["total_nodes"] = len(graph_obj.nodes)
            stats["total_edges"] = len(graph_obj.edges) if hasattr(graph_obj, 'edges') else 0

            for node_key in list(graph_obj.nodes)[:200]:  # Sample 200
                node = graph_obj.nodes[node_key]
                snippet = node.get("snippet", "") if isinstance(node, dict) else ""
                degree = graph_obj.degree(node_key) if hasattr(graph_obj, 'degree') else 0
                if snippet and len(str(snippet)) > 10 and degree == 0:
                    stats["orphaned"].append({"key": str(node_key), "snippet": str(snippet)[:80]})
                elif degree <= 1:
                    stats["low_connectivity"].append(
                        {"key": str(node_key), "edges": degree})

        stats["orphaned_count"] = len(stats["orphaned"])
        stats["low_connectivity_count"] = len(stats["low_connectivity"])

        return json.dumps(stats, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def cortex_topology_health() -> str:
    """
    Overview of the cortex graph health and topology.

    Shows node/edge counts, connectivity stats, portal energy,
    and overall health. Like a brain scan — shows active vs dark regions.

    NOTE: MCP runs in a SEPARATE process from the Akashic system.
    The manifold (1.27M+ nodes) lives in the server process.
    We read the cortex tick data from boot_live.log.
    """
    import re
    print("[CortexHealth] BOOT LOG PARSER VERSION RUNNING")
    health = {"ts": time.time(), "source": "boot_log_parse"}

    try:
        boot_log = PROJECT_ROOT / "state" / "boot_live.log"
        if not boot_log.exists():
            return json.dumps({"error": "Boot log not found — system may not be running"})

        text = boot_log.read_text(encoding='utf-8', errors='replace')

        # Pattern: [AssociationCortexFairy] TICK #N - XXXXX nodes, YYYYY edges, portal_energy=X.XX
        matches = re.findall(
            r'AssociationCortexFairy\] TICK #(\d+) - (\d+) nodes, (\d+) edges, portal_energy=([\d.]+)',
            text)

        if matches:
            tick, nodes, edges, energy = matches[-1]
            nodes, edges = int(nodes), int(edges)
            avg = round(edges / nodes, 2) if nodes > 0 else 0
            health["tick"] = int(tick)
            health["nodes"] = nodes
            health["edges"] = edges
            health["avg_connectivity"] = avg
            health["portal_energy"] = float(energy)

            if nodes == 0:
                health["assessment"] = "CRITICAL: Cortex is empty"
            elif nodes < 1000:
                health["assessment"] = "COLD START: Cortex needs more content"
            elif avg < 1.0:
                health["assessment"] = "SPARSE: Low connectivity"
            elif avg < 3.0:
                health["assessment"] = "GROWING: Moderate connectivity"
            elif avg < 10.0:
                health["assessment"] = "HEALTHY: Good connectivity"
            else:
                health["assessment"] = "DENSE: Very high connectivity"
        else:
            health["error"] = "No cortex tick found — system may still be starting"

        return json.dumps(health, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def cognitive_call_intent(fairy_name: str, intent: str, payload: str = "{}") -> str:
    """Call ANY fairy intent and return its REPLY (request/reply, not fire-and-forget).

    Unlike gm_command (routes one-way -> returns {"sent": true}, never the result),
    this uses the tunnel's request/reply path (_query_fairy) and returns the fairy's
    actual response dict. Read live fairy state, e.g.:
      cognitive_call_intent("AkashicRecordsLibrarianFairy", "status_card", '{"actor": "SourpatchesFairy"}')
      cognitive_call_intent("AkashicRecordsLibrarianFairy", "fairy_autobiographies", '{"limit": 3}')

    Args:
        fairy_name: target actor (e.g. "AkashicRecordsLibrarianFairy")
        intent:     intent name WITHOUT the "intent_" prefix (e.g. "status_card")
        payload:    JSON string of the intent kwargs (default "{}")
    """
    try:
        payload_dict = json.loads(payload) if payload else {}
        if not isinstance(payload_dict, dict):
            payload_dict = {}
    except Exception:
        payload_dict = {}
    result = _query_fairy(fairy_name, intent, payload_dict, timeout=8.0)
    return json.dumps(result, indent=2, default=str)


def cognitive_embedding_coverage() -> str:
    """Embedding coverage of the cortex manifold (#6 eyes): how many of the ~1.9M
    nodes actually have semantic vectors = the reach ceiling of the long-range jump.
    Returns file_exists, file_size_mb, embedding_dim, node_capacity, embedded_nodes,
    coverage (embedded/total), node_count_live. Low coverage = newer nodes unembedded
    -> re-embedding needed for full reach (the #6 Phase-2 item)."""
    result = _query_fairy("AssociationCortexFairy", "embedding_stats", {}, timeout=30.0)
    return json.dumps(result, indent=2, default=str)


# Add cortex exploration tools to the registry (defined above, after the dict)
COGNITIVE_TOOLS.update({
    "cortex_trace_path": {
        "function": cortex_trace_path,
        "description": "Trace a path between two concepts in the cortex graph. Shows bridges, breaks, and connection strength.",
    },
    "cortex_dead_spots": {
        "function": cortex_dead_spots,
        "description": "Find dead spots — orphaned knowledge with no connections that can't spread.",
    },
    "cortex_topology_health": {
        "function": cortex_topology_health,
        "description": "Brain scan — node/edge counts, connectivity, portal status, health assessment.",
    },
    "cognitive_embedding_coverage": {
        "function": cognitive_embedding_coverage,
        "description": "Embedding coverage of the cortex (#6 eyes): how many of the ~1.9M nodes have semantic vectors = the long-range jump's reach ceiling. Low = re-embedding needed.",
    },
    "cognitive_call_intent": {
        "function": cognitive_call_intent,
        "description": "Call ANY fairy intent and return its REPLY (request/reply — not fire-and-forget like gm_command). Read live fairy state, e.g. status_card / fairy_autobiographies on AkashicRecordsLibrarianFairy.",
    },
})


# ============================================================================
# TOOL REGISTRATION
# ============================================================================

def register_cognitive_tools(mcp):
    """
    Register all cognitive tools with the MCP server.

    Called from akashic_mcp_server.py to expose cognitive fairies to Claude.
    """
    for name, tool_info in COGNITIVE_TOOLS.items():
        # Get the function and its description
        func = tool_info["function"]
        description = tool_info.get("description", func.__doc__ or "")

        # Register with MCP using the decorator pattern
        decorated = mcp.tool()(func)

        # Update the tool's docstring if we have a better description
        if description:
            decorated.__doc__ = description.strip()

    print(f"[CognitiveTools] Registered {len(COGNITIVE_TOOLS)} cognitive integration tools")
