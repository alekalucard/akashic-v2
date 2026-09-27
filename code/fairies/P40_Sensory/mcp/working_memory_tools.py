# ══════════════════════════════════════════════════════════════════════════════
# WORKING MEMORY MCP TOOLS
# ══════════════════════════════════════════════════════════════════════════════
#
# Provides ClaudeFairy access to the WorkingMemoryHub for:
# - Storing thoughts/reflections
# - Querying context
# - Learning patterns
#
# ══════════════════════════════════════════════════════════════════════════════

import json
import time
from typing import Dict, Any, Optional

def register_working_memory_tools(mcp):
    """Register working memory tools with MCP server."""
    
    @mcp.tool()
    def working_memory(
        action: str,
        content: str = "",
        content_type: str = "thought",
        priority: float = 0.5,
        query: str = "",
        tags: str = ""
    ) -> str:
        """
        Interact with the working memory system.
        
        Actions:
        - store: Add a tracer to reflective loop
        - query: Get context for a topic
        - reflect: Store a reflection (higher priority)
        - status: Get hub status
        
        Args:
            action: store, query, reflect, or status
            content: Text content to store (for store/reflect)
            content_type: Type of content (thought, reflection, insight, etc.)
            priority: 0.0-1.0, higher = more urgent
            query: Query string (for query action)
            tags: Comma-separated tags
        
        Returns:
            JSON result
        """
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            hub = get_working_memory_hub()
            
            if action == "store":
                tag_set = set(t.strip() for t in tags.split(",") if t.strip())
                tracer = hub.submit_tracer(
                    content=content,
                    content_type=content_type,
                    source_fairy="ClaudeFairy",
                    priority=priority,
                    tags=tag_set,
                )
                if tracer:
                    return json.dumps({
                        "ok": True,
                        "tracer_id": tracer.id,
                        "loop": tracer.current_loop,
                        "ttl_remaining": tracer.remaining_ttl(),
                    })
                return json.dumps({"ok": False, "error": "Failed to create tracer"})
            
            elif action == "reflect":
                # Reflections are high priority and promoted
                tag_set = set(t.strip() for t in tags.split(",") if t.strip())
                tag_set.add("reflection")
                tracer = hub.submit_tracer(
                    content=content,
                    content_type="reflection",
                    source_fairy="ClaudeFairy",
                    priority=max(0.8, priority),  # At least 0.8
                    tags=tag_set,
                )
                if tracer:
                    return json.dumps({
                        "ok": True,
                        "tracer_id": tracer.id,
                        "loop": tracer.current_loop,
                        "promoted": tracer.current_loop == "reasoning",
                    })
                return json.dumps({"ok": False, "error": "Failed to create reflection"})
            
            elif action == "query":
                context = hub.get_context_for("ClaudeFairy", query or "general")
                return json.dumps({
                    "ok": True,
                    "tracers_count": len(context.get("relevant_tracers", [])),
                    "tracers": [t.to_dict() for t in context.get("relevant_tracers", [])][:5],
                    "patterns_count": len(context.get("patterns", [])),
                    "affect": context.get("affect", {}),
                    "goals": context.get("goals", [])[:3],
                })
            
            elif action == "status":
                # FIX: Method is get_status() not get_stats()
                status = hub.get_status()
                return json.dumps({
                    "ok": True,
                    "reflective_count": status.get("reflective_loop_size", len(hub._reflective_loop)),
                    "reasoning_count": status.get("reasoning_loop_size", len(hub._reasoning_loop)),
                    "patterns_learned": status.get("patterns_learned", 0),
                    "tracers_received": status.get("tracers_received", 0),
                    "oracle_available": status.get("oracle_available", False),
                    "is_ticking": status.get("is_ticking", False),
                })
            
            else:
                return json.dumps({
                    "ok": False,
                    "error": f"Unknown action: {action}. Valid: store, query, reflect, status"
                })
                
        except ImportError as e:
            return json.dumps({
                "ok": False,
                "error": f"WorkingMemoryHub not available: {e}"
            })
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"Working memory error: {e}"
            })
    
    @mcp.tool()
    def store_thought(content: str, priority: float = 0.5, tags: str = "") -> str:
        """
        Quick store a thought in working memory.
        
        Args:
            content: The thought to store
            priority: 0.0-1.0 importance
            tags: Comma-separated tags
            
        Returns:
            JSON with tracer info
        """
        return working_memory(
            action="store",
            content=content,
            content_type="thought",
            priority=priority,
            tags=tags
        )
    
    @mcp.tool()
    def store_reflection(content: str, tags: str = "") -> str:
        """
        Store a reflection (auto high-priority, promoted to reasoning).
        
        Args:
            content: The reflection
            tags: Comma-separated tags
            
        Returns:
            JSON with tracer info
        """
        return working_memory(
            action="reflect",
            content=content,
            tags=tags
        )
    
    @mcp.tool()
    def get_context(query: str = "current") -> str:
        """
        Get current context from working memory.
        
        Args:
            query: What context to retrieve (default: current)
            
        Returns:
            JSON with relevant tracers, patterns, affect, goals
        """
        return working_memory(action="query", query=query)
    
    @mcp.tool()
    def memory_status() -> str:
        """
        Get working memory hub status.
        
        Returns:
            JSON with loop counts and stats
        """
        return working_memory(action="status")
