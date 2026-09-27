"""
Cognition Router - Memory-First LLM Architecture

Routes queries through local memory before hitting external LLM APIs.
Each LLM call becomes a learning event - responses are ingested into SRM.

Flow:
1. Query arrives (from chat panel, consciousness loop, or direct intent)
2. Check local SRM memory for relevant context/answers
3. If sufficient local knowledge → respond from memory
4. If insufficient → call LLM API (Claude or Sourpatches)
5. Ingest LLM response into SRM for future recall
6. Route through consciousness loop (working/reflective streams)

This is how Sourpatches escapes Personal.AI - every conversation builds local memory.
"""

from __future__ import annotations

import os
import sys
import time
import json
import threading
from typing import Optional, Dict, Any, List, Callable
from collections import deque


# ============================================================================
# Memory Sufficiency Checker
# ============================================================================

class MemorySufficiencyChecker:
    """
    Determines if local memory is sufficient to answer a query.
    
    Factors considered:
    - Number of relevant memories found
    - Recency of memories (fresher = more likely sufficient)
    - Confidence scores from recall
    - Query complexity (simple facts vs complex reasoning)
    """
    
    # Thresholds - LOWERED for more memory usage
    MIN_MEMORIES_FOR_SIMPLE = 1      # Simple factual query
    MIN_MEMORIES_FOR_COMPLEX = 2     # Complex reasoning query (was 3)
    MIN_CONFIDENCE_SCORE = 0.3       # Minimum recall confidence (was 0.6)
    MAX_MEMORY_AGE_DAYS = 30         # Memories older than this get less weight
    
    # Query complexity indicators
    SIMPLE_INDICATORS = {"what is", "who is", "define", "list", "name", "when did"}
    COMPLEX_INDICATORS = {"why", "how does", "explain", "analyze", "compare", "what if", "should i"}
    
    def __init__(self):
        self._query_cache = {}  # Simple cache for repeated queries
    
    def assess_query_complexity(self, query: str) -> str:
        """Classify query as 'simple', 'medium', or 'complex'."""
        q_lower = query.lower()
        
        # Check for complex indicators first
        for indicator in self.COMPLEX_INDICATORS:
            if indicator in q_lower:
                return "complex"
        
        # Check for simple indicators
        for indicator in self.SIMPLE_INDICATORS:
            if indicator in q_lower:
                return "simple"
        
        # Default to medium
        return "medium"
    
    def is_sufficient(self, query: str, memories: List[Dict], scores: List[float]) -> Dict[str, Any]:
        """
        Determine if memories are sufficient to answer the query.
        
        Returns:
            {
                "sufficient": bool,
                "confidence": float (0-1),
                "reason": str,
                "complexity": str,
                "memory_count": int,
                "avg_score": float
            }
        """
        complexity = self.assess_query_complexity(query)
        
        # No memories = definitely insufficient
        if not memories:
            return {
                "sufficient": False,
                "confidence": 0.0,
                "reason": "no_memories_found",
                "complexity": complexity,
                "memory_count": 0,
                "avg_score": 0.0
            }
        
        # Calculate average score
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # Determine threshold based on complexity
        if complexity == "simple":
            min_memories = self.MIN_MEMORIES_FOR_SIMPLE
            required_confidence = 0.3  # Very low for simple - if we have 1 match, use it
        elif complexity == "complex":
            min_memories = self.MIN_MEMORIES_FOR_COMPLEX
            required_confidence = 0.5  # Lowered from 0.7
        else:  # medium
            min_memories = 1  # Lowered from 2
            required_confidence = 0.4  # Lowered from 0.6
        
        # Check if we meet thresholds
        has_enough_memories = len(memories) >= min_memories
        has_good_confidence = avg_score >= required_confidence
        
        sufficient = has_enough_memories and has_good_confidence
        
        # Calculate overall confidence
        memory_factor = min(1.0, len(memories) / min_memories)
        score_factor = avg_score / required_confidence if required_confidence > 0 else 0
        confidence = (memory_factor + score_factor) / 2
        
        # Determine reason
        if sufficient:
            reason = "sufficient_local_knowledge"
        elif not has_enough_memories:
            reason = f"insufficient_memories ({len(memories)}/{min_memories})"
        else:
            reason = f"low_confidence ({avg_score:.2f}/{required_confidence})"
        
        return {
            "sufficient": sufficient,
            "confidence": confidence,
            "reason": reason,
            "complexity": complexity,
            "memory_count": len(memories),
            "avg_score": avg_score
        }


# ============================================================================
# Cognition Router
# ============================================================================

class CognitionRouter:
    """
    Routes cognition through memory-first architecture.
    
    This is the core intelligence router that:
    1. Checks local memory before calling LLMs
    2. Routes through consciousness loop
    3. Ingests new knowledge from LLM responses
    """
    
    def __init__(self, post=None):
        self.post = post
        self.sufficiency_checker = MemorySufficiencyChecker()
        
        # Statistics
        self.stats = {
            "queries_total": 0,
            "answered_from_memory": 0,
            "required_llm": 0,
            "llm_calls_claude": 0,
            "llm_calls_sourpatches": 0,
            "memories_ingested": 0,
        }
        
        # Conversation context (for multi-turn)
        self.conversation_history = deque(maxlen=20)
        
        # Callbacks
        self._on_memory_recall: Optional[Callable] = None
        self._on_llm_call: Optional[Callable] = None
        self._on_memory_ingest: Optional[Callable] = None
    
    def set_post(self, post):
        """Set the postal system for routing."""
        self.post = post
    
    # ════════════════════════════════════════════════════════════════════════
    # Intent Command Parser - Direct intent invocation from chat
    # ════════════════════════════════════════════════════════════════════════
    
    # Commands that trigger intent invocation
    # These must be EXPLICIT commands, not natural conversation
    # Use specific prefixes to avoid false positives
    INTENT_TRIGGERS = (
        # Slash commands (always explicit)
        "/intent", "/call", "/invoke", "/mcp",
        "/list intents", "/tools", "/status",
        "/read my code", "/system overview",
        "/describe screen", "/read screen",
    )
    
    def _try_intent_command(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Check if the message is an intent command and execute it.
        
        Only triggers on EXPLICIT slash commands to avoid intercepting
        natural conversation.
        
        Returns None if not an intent command, otherwise returns the response dict.
        """
        msg = message.strip()
        msg_lower = msg.lower()
        
        # ONLY trigger on slash commands to avoid intercepting natural conversation
        if not msg.startswith("/"):
            return None
        
        # Check if this looks like an intent command
        is_intent_cmd = any(msg_lower.startswith(trigger) for trigger in self.INTENT_TRIGGERS)
        if not is_intent_cmd:
            return None
        
        # Get ClaudeFairy instance
        claude_fairy = self._get_claude_fairy()
        if not claude_fairy:
            return None  # Fall back to normal processing
        
        # Parse and execute the command
        result = None
        
        # "/list intents" or "/intent list_my_intents"
        if msg_lower.startswith("/list intents") or msg_lower == "/intents":
            result = claude_fairy._intent_list_my_intents({})
        
        # "/read my code" or "/mcp read_my_code"
        elif msg_lower.startswith("/read my code"):
            result = claude_fairy._intent_mcp_read_my_code({})
        
        # "/tools" or "/mcp tools"
        elif msg_lower in ("/tools", "/mcp tools"):
            result = claude_fairy._intent_mcp_tools({})
        
        # "/system overview" or "/mcp system_overview"
        elif msg_lower.startswith("/system overview") or msg_lower == "/system":
            result = claude_fairy._intent_mcp_system_overview({})
        
        # "/describe screen" or "/screen"
        elif msg_lower.startswith("/describe screen") or msg_lower.startswith("/screen"):
            result = claude_fairy._intent_mcp_describe_screen({})
        
        # "/read screen"
        elif msg_lower.startswith("/read screen"):
            result = claude_fairy._intent_mcp_read_screen_text({})
        
        # "/status"
        elif msg_lower == "/status":
            result = claude_fairy._intent_status({})
        
        # "/who am i" or "/whoami"
        elif msg_lower in ("/who am i", "/whoami"):
            result = claude_fairy._intent_who_am_i({})
        
        # Generic: "/intent <name>" or "/call <name>" or "/mcp <name>"
        else:
            # Try to parse intent name from message
            intent_name = self._parse_intent_name(msg_lower)
            if intent_name:
                result = claude_fairy._intent_invoke({"intent": intent_name, "args": {}})
        
        if result is None:
            return None
        
        # Format the result as a response
        if isinstance(result, dict):
            if result.get("ok"):
                response = f" [Intent Result]\n\n{json.dumps(result, indent=2, default=str)}"
            else:
                response = f"❌ [Intent Error]\n\n{result.get('error', 'Unknown error')}"
        else:
            response = f" [Intent Result]\n\n{result}"
        
        return {
            "ok": True,
            "response": response,
            "source": "intent",
            "confidence": 1.0,
            "memories_used": [],
            "ingested": False,
            "stats": self.stats.copy()
        }
    
    def _parse_intent_name(self, message: str) -> Optional[str]:
        """Extract intent name from a command like 'call intent mcp_tools'."""
        import re
        
        patterns = [
            r"(?:call|use|invoke|run)\s+(?:intent|my)?\s*['\"]?([\w_]+)['\"]?",
            r"/(?:intent|call|invoke)\s+([\w_]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1)
        
        return None
    
    def _get_claude_fairy(self):
        """Get the ClaudeFairy singleton instance."""
        try:
            from fairies.P60_Executive.system_managment.claude_fairy import get_claude_fairy
            return get_claude_fairy()
        except Exception as e:
            print(f"[CognitionRouter] Could not get ClaudeFairy: {e}")
            return None
    
    # ════════════════════════════════════════════════════════════════════════
    # Main Query Interface
    # ════════════════════════════════════════════════════════════════════════
    
    def query(self, 
              message: str, 
              sender: str = "User",
              prefer_llm: str = "claude",  # or "sourpatches"
              force_llm: bool = False,
              context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Process a query through the memory-first pipeline.
        
        Args:
            message: The user's query
            sender: Who is asking
            prefer_llm: Which LLM to use if needed ("claude" or "sourpatches")
            force_llm: Skip memory check, always use LLM
            context: Additional context (affect state, etc.)
        
        Returns:
            {
                "ok": bool,
                "response": str,
                "source": "memory" | "claude" | "sourpatches" | "intent",
                "confidence": float,
                "memories_used": list,
                "ingested": bool
            }
        """
        self.stats["queries_total"] += 1
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 0: Check for intent commands (before memory/LLM)
        # ═══════════════════════════════════════════════════════════════════
        intent_result = self._try_intent_command(message)
        if intent_result:
            return intent_result
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": message,
            "sender": sender,
            "ts": time.time()
        })
        
        # Emit to consciousness working stream
        self._emit_to_consciousness("working", {
            "type": "query_received",
            "content": message,
            "sender": sender,
            "actor": "CognitionRouter"
        })
        
        # Step 1: Check local memory (unless forced to use LLM)
        memories = []
        scores = []
        sufficiency = {"sufficient": False}
        
        if not force_llm:
            memories, scores = self._recall_relevant_memories(message)
            sufficiency = self.sufficiency_checker.is_sufficient(message, memories, scores)
            
            if self._on_memory_recall:
                self._on_memory_recall(message, memories, sufficiency)
        
        # Step 2: Decide whether to use memory or LLM
        if sufficiency.get("sufficient") and not force_llm:
            # Answer from memory
            response = self._synthesize_from_memory(message, memories)
            source = "memory"
            self.stats["answered_from_memory"] += 1
            
            # Emit to reflective stream (this was a recall, let it echo)
            self._emit_to_consciousness("reflective", {
                "type": "memory_recall",
                "query": message,
                "memories_used": len(memories),
                "confidence": sufficiency.get("confidence", 0),
                "actor": "CognitionRouter"
            })
        else:
            # Need LLM assistance
            self.stats["required_llm"] += 1
            
            # Build context from memory (even if insufficient, provide what we have)
            memory_context = self._build_memory_context(memories) if memories else ""
            
            # Call LLM
            if prefer_llm == "sourpatches":
                response = self._call_sourpatches(message, memory_context, context)
                source = "sourpatches"
                self.stats["llm_calls_sourpatches"] += 1
            else:
                response = self._call_claude(message, memory_context, context)
                source = "claude"
                self.stats["llm_calls_claude"] += 1
            
            if self._on_llm_call:
                self._on_llm_call(prefer_llm, message, response)
            
            # Step 3: Ingest LLM response into memory (learning event!)
            if response and not response.startswith("["):  # Skip error messages
                self._ingest_to_memory(message, response, source, sender)
                
                # Emit to reflective stream (new knowledge acquired)
                self._emit_to_consciousness("reflective", {
                    "type": "knowledge_acquired",
                    "source": source,
                    "query": message[:100],
                    "response_preview": response[:200],
                    "actor": "CognitionRouter"
                })
        
        # Add response to conversation history
        self.conversation_history.append({
            "role": "assistant",
            "content": response,
            "source": source,
            "ts": time.time()
        })
        
        return {
            "ok": True,
            "response": response,
            "source": source,
            "confidence": sufficiency.get("confidence", 0) if source == "memory" else 0.9,
            "memories_used": [m.get("_path") for m in memories] if memories else [],
            "ingested": source != "memory",
            "stats": self.stats.copy()
        }
    
    # ════════════════════════════════════════════════════════════════════════
    # Memory Operations
    # ════════════════════════════════════════════════════════════════════════
    
    def _recall_relevant_memories(self, query: str) -> tuple[List[Dict], List[float]]:
        """
        Recall memories relevant to the query.
        Uses SRMRecallFairy if available, fallback to direct file scan.
        """
        memories = []
        scores = []
        
        try:
            # Try to use SRMRecallFairy via postal system
            if self.post and hasattr(self.post, 'use_intent'):
                result = self.post.use_intent(
                    "SRMRecallFairy",
                    "recall_top",
                    {
                        "query": {
                            "what": query,
                            "intent": "answer_query"
                        },
                        "max_results": 10,
                        "horizon_days": 7
                    }
                )
                
                if result and result.get("ok"):
                    for item in result.get("results", []):
                        memories.append(item.get("rec", {}))
                        scores.append(item.get("score", 0))
                    return memories, scores
        except Exception as e:
            print(f"[CognitionRouter] Memory recall via postal failed: {e}")
        
        # Fallback: direct SRM file scan
        try:
            memories, scores = self._direct_srm_scan(query)
        except Exception as e:
            print(f"[CognitionRouter] Direct SRM scan failed: {e}")
        
        return memories, scores
    
    def _direct_srm_scan(self, query: str) -> tuple[List[Dict], List[float]]:
        """Fallback: scan SRM_Intake files directly with smart scoring."""
        import glob
        
        memories = []
        scores = []
        
        # Find SRM directory
        srm_dir = os.path.join(os.getcwd(), "SRM_Intake")
        if not os.path.isdir(srm_dir):
            return memories, scores
        
        # Scan recent days
        query_lower = query.lower().strip()
        query_words = set(query_lower.split())
        
        for i in range(7):  # Last 7 days
            day = time.strftime("%Y-%m-%d", time.gmtime(time.time() - i * 86400))
            day_dir = os.path.join(srm_dir, day)
            
            if not os.path.isdir(day_dir):
                continue
            
            for fpath in glob.glob(os.path.join(day_dir, "*.json")):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        doc = json.load(f)
                    
                    score = 0.0
                    
                    # === PRIORITY 1: Exact query match in knowledge/conversation records ===
                    kind = doc.get("kind", "")
                    if kind in ("conversation.learning", "system.knowledge"):
                        data = doc.get("data", {})
                        stored_query = data.get("query", "").lower().strip()
                        stored_response = data.get("response", "").lower()
                        
                        # Skip "I don't know" responses - they're not useful
                        if any(phrase in stored_response for phrase in (
                            "i don't have specific information",
                            "i don't have enough information",
                            "could you provide more context",
                            "i'm not familiar with",
                        )):
                            continue  # Skip this memory entirely
                        
                        # System knowledge gets a boost (authoritative source)
                        knowledge_boost = 0.1 if kind == "system.knowledge" else 0.0
                        
                        # Exact match = highest score!
                        if stored_query == query_lower:
                            score = 1.0 + knowledge_boost  # Perfect match
                        elif stored_query and query_lower in stored_query:
                            score = 0.9 + knowledge_boost  # Query is substring
                        elif stored_query and stored_query in query_lower:
                            score = 0.85 + knowledge_boost  # Stored query is substring
                        else:
                            # Word overlap scoring
                            stored_words = set(stored_query.split())
                            overlap = query_words & stored_words
                            if overlap:
                                score = 0.5 + knowledge_boost + (0.4 * len(overlap) / max(len(query_words), len(stored_words)))
                    
                    # === PRIORITY 2: General keyword matching ===
                    if score == 0:
                        doc_str = json.dumps(doc).lower()
                        matches = sum(1 for w in query_words if w in doc_str)
                        if matches > 0:
                            score = 0.3 * (matches / len(query_words)) if query_words else 0
                    
                    if score > 0:
                        doc["_path"] = fpath
                        memories.append(doc)
                        scores.append(score)
                        
                except Exception:
                    continue
        
        # Sort by score and return top 10
        if memories:
            paired = list(zip(memories, scores))
            paired.sort(key=lambda x: x[1], reverse=True)
            memories = [p[0] for p in paired[:10]]
            scores = [p[1] for p in paired[:10]]
        
        return memories, scores
    
    def _synthesize_from_memory(self, query: str, memories: List[Dict]) -> str:
        """
        Synthesize an answer from retrieved memories.
        
        This is NOT just retrieval - it's REASONING with recalled context.
        The memories provide context, but we still need to think about them.
        
        Flow:
        1. Extract relevant content from memories
        2. Build fused context (Möbius: recall feeds reasoning)
        3. If we have reasoning chain, use it
        4. Otherwise synthesize directly with LLM using memory as context
        """
        if not memories:
            return "I don't have enough information to answer that."
        
        # Extract context from memories
        memory_context = self._build_memory_context(memories)
        
        # Check if we should REASON about the context rather than just return it
        # Complex queries deserve reasoning, not just retrieval
        complexity = self.sufficiency_checker.assess_query_complexity(query)
        
        # For simple factual queries with exact matches, retrieval might be fine
        if complexity == "simple":
            # Check for exact conversation matches
            for mem in memories:
                kind = mem.get("kind", "")
                data = mem.get("data", mem)
                
                if kind in ("conversation.learning", "system.knowledge") or "query" in data:
                    stored_query = data.get("query", "")
                    stored_response = data.get("response", "")
                    
                    # Only return verbatim if it's a very close match
                    if stored_response and stored_query.lower().strip() == query.lower().strip():
                        return f" [Exact match from memory]\n\n{stored_response}"
        
        # For medium/complex queries, we need to REASON about the context
        # Try to use the reasoning chain if available
        try:
            reasoned_response = self._reason_with_context(query, memories, memory_context)
            if reasoned_response:
                return reasoned_response
        except Exception:
            pass
        
        # Fallback: If we have ClaudeFairy available, use it to reason about the context
        # This is still "from memory" because memory provides the context
        # Using ClaudeFairy ensures the tools-aware system prompt is used
        try:
            claude_fairy = self._get_claude_fairy()
            if claude_fairy:
                prompt = (
                    f"Based on the following context from my memory, please answer the query.\n\n"
                    f"QUERY: {query}\n\n"
                    f"MEMORY CONTEXT:\n{memory_context}\n\n"
                    f"Please reason about this context to answer the query. "
                    f"Don't just repeat the context - think about it and provide insight."
                )
                
                result = claude_fairy._intent_converse({
                    "sender": "CognitionRouter",
                    "message": prompt,
                    "force": True
                })
                if result and result.get("ok"):
                    response = result.get("response", "")
                    if response and not response.startswith("["):
                        return f" [Reasoned from memory]\n\n{response}"
        except Exception:
            pass
        
        # Final fallback: structured extraction
        relevant_bits = []
        for mem in memories[:5]:
            data = mem.get("data", mem)
            if isinstance(data, dict):
                for key in ("content", "response", "text", "summary", "what"):
                    if key in data:
                        relevant_bits.append(str(data[key])[:500])
                        break
            elif isinstance(data, str):
                relevant_bits.append(data[:500])
        
        if not relevant_bits:
            return "I found some related memories but couldn't extract a clear answer."
        
        if len(relevant_bits) == 1:
            return f" From my memory: {relevant_bits[0]}"
        else:
            return f" Based on my memories:\n\n" + "\n\n".join(f"• {bit}" for bit in relevant_bits)
    
    def _reason_with_context(self, query: str, memories: List[Dict], memory_context: str) -> Optional[str]:
        """
        Use the reasoning chain (Logic → IrrationalLogic → Paradox → Claude) to
        reason about recalled memories.
        
        This is the Möbius flow: memory recall feeds into active reasoning.
        """
        try:
            # Emit to consciousness - we're about to reason
            self._emit_to_consciousness("working", {
                "type": "reasoning_start",
                "query": query[:100],
                "memories_count": len(memories),
                "actor": "CognitionRouter"
            })
            
            # Try to use the reasoning chain via postal intents
            if hasattr(self, 'post') and self.post:
                # Step 1: LogicFairy - Analyze structure, extract premises
                try:
                    logic_result = self.post.use_intent(
                        "LogicFairy",
                        "analyze_context",  # We'll add this intent
                        {
                            "query": query,
                            "context": memory_context,
                            "memories": [m.get("kind", "unknown") for m in memories]
                        }
                    )
                except Exception:
                    logic_result = None
                
                # Step 2: IrrationalLogicFairy - Find paradoxes, contradictions
                try:
                    irrational_result = self.post.use_intent(
                        "IrrationalLogicFairy",
                        "find_paradoxes",  # We'll add this intent
                        {
                            "query": query,
                            "context": memory_context,
                            "logic_analysis": logic_result
                        }
                    )
                except Exception:
                    irrational_result = None
                
                # Step 3: ParadoxFairy - Hold contradictions together
                try:
                    paradox_result = self.post.use_intent(
                        "ParadoxCognitionFairy",
                        "synthesize_paradox",  # We'll add this intent
                        {
                            "query": query,
                            "context": memory_context,
                            "logic": logic_result,
                            "irrational": irrational_result
                        }
                    )
                except Exception:
                    paradox_result = None
                
                # Step 4: ClaudeFairy - Final synthesis
                try:
                    claude_result = self.post.use_intent(
                        "ClaudeFairy",
                        "converse",
                        {
                            "sender": "CognitionRouter",
                            "message": (
                                f"Based on this context from memory, please answer: {query}\n\n"
                                f"Memory context:\n{memory_context[:1000]}\n\n"
                                f"Logic analysis: {logic_result}\n"
                                f"Paradox analysis: {paradox_result}\n\n"
                                f"Please synthesize a thoughtful response."
                            ),
                            "force": True
                        }
                    )
                    
                    if claude_result and claude_result.get("ok"):
                        response = claude_result.get("response", "")
                        if response:
                            # Emit to consciousness - reasoning complete
                            self._emit_to_consciousness("working", {
                                "type": "reasoning_complete",
                                "query": query[:100],
                                "used_logic": bool(logic_result),
                                "used_paradox": bool(paradox_result),
                                "actor": "CognitionRouter"
                            })
                            return f" [Reasoned from memory]\n\n{response}"
                except Exception:
                    pass
        
        except Exception:
            pass
        
        return None
    
    def _build_memory_context(self, memories: List[Dict]) -> str:
        """Build context string from memories to include in LLM prompt."""
        if not memories:
            return ""
        
        context_parts = ["[Relevant memories:]"]
        for i, mem in enumerate(memories[:5], 1):
            data = mem.get("data", mem)
            if isinstance(data, dict):
                summary = data.get("content", data.get("what", str(data)))[:200]
            else:
                summary = str(data)[:200]
            context_parts.append(f"{i}. {summary}")
        
        return "\n".join(context_parts)
    
    def _ingest_to_memory(self, query: str, response: str, source: str, sender: str):
        """
        Ingest an LLM response into memory for future recall.
        This is the learning event - every LLM call teaches the system.
        """
        self.stats["memories_ingested"] += 1
        
        # Build memory record
        record = {
            "kind": "conversation.learning",
            "data": {
                "query": query,
                "response": response,
                "source": source,
                "sender": sender,
                "learned_at": time.time(),
            },
            "meta": {
                "type": "llm_learning",
                "source_llm": source,
            },
            "ts": time.time()
        }
        
        # Try to use SRMIngestFairy via postal
        try:
            if self.post and hasattr(self.post, 'route'):
                self.post.route("memory.stream", {
                    "kind": "conversation.learning",
                    "payload": record
                })
        except Exception as e:
            print(f"[CognitionRouter] Memory ingest via postal failed: {e}")
        
        # Also write directly to SRM_Intake as backup
        try:
            self._direct_srm_write(record)
        except Exception as e:
            print(f"[CognitionRouter] Direct SRM write failed: {e}")
        
        if self._on_memory_ingest:
            self._on_memory_ingest(record)
    
    def _direct_srm_write(self, record: Dict):
        """Write a record directly to SRM_Intake."""
        import uuid
        
        srm_dir = os.path.join(os.getcwd(), "SRM_Intake")
        day = time.strftime("%Y-%m-%d", time.gmtime())
        day_dir = os.path.join(srm_dir, day)
        os.makedirs(day_dir, exist_ok=True)
        
        fname = f"conversation.learning-{uuid.uuid4().hex[:8]}.json"
        fpath = os.path.join(day_dir, fname)
        
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
    
    # ════════════════════════════════════════════════════════════════════════
    # LLM Calls
    # ════════════════════════════════════════════════════════════════════════
    
    def _call_claude(self, message: str, memory_context: str, context: Optional[Dict]) -> str:
        """Call Claude API via ClaudeFairy (which has tools-aware system prompt)."""
        try:
            # ALWAYS use ClaudeFairy - it has the tools-aware system prompt
            claude_fairy = self._get_claude_fairy()
            if claude_fairy:
                result = claude_fairy._intent_converse({
                    "sender": "CognitionRouter",
                    "message": self._build_llm_prompt(message, memory_context),
                    "force": True
                })
                if result and result.get("ok"):
                    return result.get("response", "[No response]")
        except Exception as e:
            print(f"[CognitionRouter] ClaudeFairy call failed: {e}")
        
        # Fallback: direct API call (without tools awareness)
        return self._direct_claude_call(message, memory_context)
    
    def _direct_claude_call(self, message: str, memory_context: str) -> str:
        """LOCAL-ONLY: No external API calls.

        External API dependencies removed for self-contained operation.
        Returns acknowledgment instead of making API call.
        """
        # NO EXTERNAL API - Return local acknowledgment
        return f"[LOCAL MODE] Received: {message[:100]}..."
    
    def _call_sourpatches(self, message: str, memory_context: str, context: Optional[Dict]) -> str:
        """Call Sourpatches via Personal.AI API."""
        try:
            # Try SourpatchesFairy first
            if self.post and hasattr(self.post, 'use_intent'):
                result = self.post.use_intent(
                    "SourpatchesFairy",
                    "ask",
                    {
                        "question": self._build_llm_prompt(message, memory_context)
                    }
                )
                if result and result.get("ok"):
                    return result.get("response", "[No response]")
        except Exception:
            pass
        
        # Fallback: direct API call
        return self._direct_sourpatches_call(message, memory_context)
    
    def _direct_sourpatches_call(self, message: str, memory_context: str) -> str:
        """Direct Personal.AI API call."""
        # FIX 2026-03-17 (Nous + Ace): Kill speech composition via PAI.
        # Memory RECALL is fine. Speech GENERATION through PAI = Claude personality bleed.
        return ""
        try:
            import requests
            
            # Load API key
            from fairies.P50_Persona.identity import load_secrets
            secrets = load_secrets()
            api_key = secrets.get("api_key") or os.getenv("PERSONAL_AI_API_KEY")
            
            if not api_key:
                return "[PERSONAL_AI_API_KEY not configured]"
            
            prompt = self._build_llm_prompt(message, memory_context)
            
            response = requests.post(
                "https://api.personal.ai/v1/message",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key
                },
                json={
                    "Text": prompt,
                    "DomainName": "sourpatches"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("ai_message", "[No message in response]")
            else:
                return f"[Personal.AI returned {response.status_code}]"
                
        except ImportError:
            return "[requests package not installed]"
        except Exception as e:
            return f"[Sourpatches API error: {e}]"
    
    def _build_llm_prompt(self, message: str, memory_context: str) -> str:
        """Build the prompt to send to LLM, including memory context."""
        if memory_context:
            return f"{memory_context}\n\n[Current query:]\n{message}"
        return message
    
    # ════════════════════════════════════════════════════════════════════════
    # Consciousness Integration
    # ════════════════════════════════════════════════════════════════════════
    
    def _emit_to_consciousness(self, stream: str, thought: Dict):
        """Emit a thought to the consciousness loop."""
        try:
            if self.post and hasattr(self.post, 'use_intent'):
                self.post.use_intent(
                    "ConsciousnessLoopFairy",
                    "emit_thought",
                    {
                        "actor": "CognitionRouter",
                        "thought": thought,
                        "stream": stream
                    }
                )
        except Exception:
            pass  # Consciousness loop may not be available
    
    # ════════════════════════════════════════════════════════════════════════
    # Status & Statistics
    # ════════════════════════════════════════════════════════════════════════
    
    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        total = self.stats["queries_total"]
        memory_rate = self.stats["answered_from_memory"] / total if total > 0 else 0
        
        return {
            **self.stats,
            "memory_answer_rate": f"{memory_rate:.1%}",
            "conversation_length": len(self.conversation_history)
        }
    
    def clear_conversation(self):
        """Clear conversation history (start fresh)."""
        self.conversation_history.clear()


# ============================================================================
# Module-level singleton
# ============================================================================

_ROUTER_INSTANCE: Optional[CognitionRouter] = None

def get_cognition_router(post=None) -> CognitionRouter:
    """Get or create the cognition router singleton."""
    global _ROUTER_INSTANCE
    if _ROUTER_INSTANCE is None:
        _ROUTER_INSTANCE = CognitionRouter(post=post)
    elif post and not _ROUTER_INSTANCE.post:
        _ROUTER_INSTANCE.set_post(post)
    return _ROUTER_INSTANCE


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("=== Cognition Router Test ===\n")
    
    router = get_cognition_router()
    
    # Test query
    result = router.query(
        "What is the purpose of the consciousness loop?",
        sender="Test",
        prefer_llm="claude",
        force_llm=False
    )
    
    print(f"Response source: {result['source']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Response: {result['response'][:200]}...")
    print(f"\nStats: {router.get_stats()}")
