# ══════════════════════════════════════════════════════════════════════════════
# NOUS TOOLS - MCP Tools for NousFairy (The Divine Intellect)
# ══════════════════════════════════════════════════════════════════════════════
#
# These tools allow Claude (via MCP) to interact with NousFairy:
# - Begin/end reasoning traces
# - Record thoughts and decisions
# - Teach patterns to the unconscious
# - Query learning status
#
# Usage: Call these tools as part of natural reasoning to train the system.
# ══════════════════════════════════════════════════════════════════════════════

import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # akashic_v2/
sys.path.insert(0, str(PROJECT_ROOT))

# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE REASONING TRACE (works without full system)
# ══════════════════════════════════════════════════════════════════════════════

import time
import uuid

# Current trace state (in-memory, persisted on complete)
_current_trace = None

class StandaloneTrace:
    """Minimal reasoning trace that works without NousFairy."""
    def __init__(self, context: str, reasoning_type: str = "mcp"):
        self.id = uuid.uuid4().hex[:12]
        self.context = context
        self.reasoning_type = reasoning_type
        self.thoughts = []
        self.decisions = []
        self.start_time = time.time()
        self.end_time = None
        self.outcome = ""
        self.success = False
        self.learnings = []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "context": self.context,
            "reasoning_type": self.reasoning_type,
            "thoughts": self.thoughts,
            "decisions": self.decisions,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": (self.end_time or time.time()) - self.start_time,
            "outcome": self.outcome,
            "success": self.success,
            "learnings": self.learnings
        }


def _get_nous():
    """Get NousFairy instance if available."""
    try:
        from fairies.P30_Cognition.cognition.nous_fairy import get_nous_fairy
        return get_nous_fairy()
    except Exception as e:
        # Fallback to other import path
        try:
            from fairies.P30_Cognition.cognition.nous_fairy import get_nous_fairy
            return get_nous_fairy()
        except:
            pass
        sys.stderr.write(f"[nous_tools] NousFairy not available, using standalone mode\n")
        return None


def _save_trace_to_srm(trace: StandaloneTrace) -> bool:
    """Save a trace to SRM for persistence."""
    try:
        import json
        from datetime import datetime

        # Save to SRM intake directory
        intake_dir = PROJECT_ROOT / "SRM_Intake" / datetime.now().strftime("%Y-%m-%d")
        intake_dir.mkdir(parents=True, exist_ok=True)

        trace_file = intake_dir / f"nous_trace_{trace.id}.json"
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump({
                "type": "nous_reasoning_trace",
                "trace": trace.to_dict(),
                "saved_at": datetime.now().isoformat()
            }, f, indent=2)

        sys.stderr.write(f"[nous_tools] Trace saved to {trace_file}\n")
        return True
    except Exception as e:
        sys.stderr.write(f"[nous_tools] Failed to save trace: {e}\n")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS (called by MCP tools) - WITH FALLBACK
# ══════════════════════════════════════════════════════════════════════════════

def _begin_reasoning(context: str = "", reasoning_type: str = "mcp") -> dict:
    """Begin a new reasoning trace."""
    global _current_trace

    # Try NousFairy first
    nous = _get_nous()
    if nous:
        trace = nous.begin_reasoning(context, reasoning_type)
        return {
            "ok": True,
            "mode": "fairy",
            "trace_id": trace.id,
            "message": f"Reasoning trace started: {context[:50]}..."
        }

    # Fallback: standalone trace
    _current_trace = StandaloneTrace(context, reasoning_type)
    return {
        "ok": True,
        "mode": "standalone",
        "trace_id": _current_trace.id,
        "message": f"[STANDALONE] Reasoning trace started: {context[:50]}..."
    }


def _record_thought(thought: str) -> dict:
    """Record a thought in the current reasoning trace."""
    global _current_trace

    # Try NousFairy first
    nous = _get_nous()
    if nous:
        nous.record_thought(thought)
        return {"ok": True, "mode": "fairy", "message": "Thought recorded"}

    # Fallback: add to standalone trace
    if _current_trace:
        _current_trace.thoughts.append({"thought": thought, "time": time.time()})
        return {"ok": True, "mode": "standalone", "message": "[STANDALONE] Thought recorded"}

    return {"ok": False, "error": "No active trace. Call i_am_thinking first."}


def _record_decision(decision: str) -> dict:
    """Record a decision point in the current reasoning trace."""
    global _current_trace

    # Try NousFairy first
    nous = _get_nous()
    if nous:
        nous.record_decision(decision)
        return {"ok": True, "mode": "fairy", "message": "Decision recorded"}

    # Fallback: add to standalone trace
    if _current_trace:
        _current_trace.decisions.append({"decision": decision, "time": time.time()})
        return {"ok": True, "mode": "standalone", "message": "[STANDALONE] Decision recorded"}

    return {"ok": False, "error": "No active trace. Call i_am_thinking first."}


def _complete_reasoning(outcome: str, success: bool = True, learnings: str = "") -> dict:
    """Complete the current reasoning trace."""
    global _current_trace

    learnings_list = [l.strip() for l in learnings.split(",")] if learnings else []

    # Try NousFairy first
    nous = _get_nous()
    if nous:
        nous.complete_reasoning(outcome, success, learnings_list)
        return {
            "ok": True,
            "mode": "fairy",
            "message": f"Reasoning complete: {outcome[:50]}...",
            "success": success,
            "pattern_taught": True
        }

    # Fallback: complete and save standalone trace
    if _current_trace:
        _current_trace.outcome = outcome
        _current_trace.success = success
        _current_trace.learnings = learnings_list
        _current_trace.end_time = time.time()

        # Save to SRM
        saved = _save_trace_to_srm(_current_trace)
        trace_id = _current_trace.id
        _current_trace = None  # Clear for next trace

        return {
            "ok": True,
            "mode": "standalone",
            "trace_id": trace_id,
            "message": f"[STANDALONE] Reasoning complete: {outcome[:50]}...",
            "success": success,
            "saved_to_srm": saved
        }

    return {"ok": False, "error": "No active trace. Call i_am_thinking first."}


def _get_status() -> dict:
    """Get NousFairy's current status."""
    global _current_trace

    nous = _get_nous()
    if nous:
        return {"ok": True, "mode": "fairy", **nous.get_status()}

    # Standalone mode status
    return {
        "ok": True,
        "mode": "standalone",
        "has_active_trace": _current_trace is not None,
        "active_trace_id": _current_trace.id if _current_trace else None,
        "active_trace_thoughts": len(_current_trace.thoughts) if _current_trace else 0,
        "active_trace_decisions": len(_current_trace.decisions) if _current_trace else 0,
        "message": "Running in standalone mode - traces saved to SRM_Intake"
    }


def _get_recent_traces(n: int = 5) -> dict:
    """Get recent reasoning traces."""
    nous = _get_nous()
    if nous:
        traces = nous.get_recent_traces(n)
        return {"ok": True, "mode": "fairy", "count": len(traces), "traces": traces}

    # Standalone mode: read from SRM_Intake
    try:
        import json
        from datetime import datetime, timedelta

        traces = []
        # Check last 3 days of SRM_Intake
        for days_ago in range(3):
            date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            intake_dir = PROJECT_ROOT / "SRM_Intake" / date
            if intake_dir.exists():
                for trace_file in sorted(intake_dir.glob("nous_trace_*.json"), reverse=True):
                    if len(traces) >= n:
                        break
                    try:
                        with open(trace_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            traces.append(data.get("trace", {}))
                    except:
                        pass

        return {
            "ok": True,
            "mode": "standalone",
            "count": len(traces),
            "traces": traces[:int(n)]  # FIX 2026-06-10: coerce MCP str-arg
        }
    except Exception as e:
        return {"ok": False, "mode": "standalone", "error": str(e), "traces": []}


def _get_pattern_summary() -> dict:
    """Get summary of learned patterns by type."""
    nous = _get_nous()
    if not nous:
        return {"ok": False, "error": "NousFairy not available"}
    
    summary = nous.get_pattern_summary()
    return {"ok": True, **summary}


def _teach_pattern(trigger: str, trigger_type: str, tool_sequence: str, 
                   pattern: str, success: bool = True) -> dict:
    """Manually teach a pattern to the unconscious."""
    nous = _get_nous()
    if not nous:
        return {"ok": False, "error": "NousFairy not available"}
    
    tools = [t.strip() for t in tool_sequence.split(",")]
    training_data = {
        "trigger": trigger,
        "trigger_type": trigger_type,
        "reasoning_chain": [f"Pattern: {pattern}"],
        "tool_sequence": [{"tool": t, "params": {}} for t in tools],
        "pattern": pattern,
        "success": success,
        "learnings": []
    }
    
    if nous._unconscious and hasattr(nous._unconscious, 'learn_from_trace'):
        nous._unconscious.learn_from_trace(training_data)
        nous.patterns_taught += 1
        return {"ok": True, "message": f"Pattern taught: {pattern[:50]}..."}
    
    return {"ok": False, "error": "UnconsciousMindFairy not connected"}


def _start_chat_monitor() -> dict:
    """Start monitoring System Chat for messages."""
    nous = _get_nous()
    if not nous:
        return {"ok": False, "error": "NousFairy not available"}
    
    nous.start_chat_monitor()
    return {"ok": True, "message": "Chat monitor started"}


def _stop_chat_monitor() -> dict:
    """Stop monitoring System Chat."""
    nous = _get_nous()
    if not nous:
        return {"ok": False, "error": "NousFairy not available"}
    
    nous.stop_chat_monitor()
    return {"ok": True, "message": "Chat monitor stopped"}


# ══════════════════════════════════════════════════════════════════════════════
# MCP REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

def register_nous_tools(mcp):
    """Register all nous tools with an MCP server instance."""
    
    @mcp.tool()
    def nous_begin_reasoning(context: str = "", reasoning_type: str = "mcp") -> str:
        """
        Begin a new reasoning trace.
        
        Call this at the START of working on something to capture your reasoning.
        This helps train the unconscious mind to think like you.
        
        Args:
            context: What you're reasoning about (e.g., "exploring P30 structure")
            reasoning_type: Type of reasoning ("mcp", "chat", "exploration", "creation")
        
        Returns:
            JSON with trace_id and status
        """
        return json.dumps(_begin_reasoning(context, reasoning_type), indent=2)
    
    @mcp.tool()
    def nous_record_thought(thought: str) -> str:
        """
        Record a thought in the current reasoning trace.
        
        Use this to capture your internal monologue while working.
        This helps train the unconscious to think like you.
        
        Args:
            thought: Your thought (e.g., "I should check the directory structure first")
        
        Returns:
            JSON with status
        """
        return json.dumps(_record_thought(thought), indent=2)
    
    @mcp.tool()
    def nous_record_decision(decision: str) -> str:
        """
        Record a decision point in the current reasoning trace.
        
        Use this when you make a key choice. Decisions are especially valuable for training.
        
        Args:
            decision: Your decision (e.g., "Using look_around because I need directory overview")
        
        Returns:
            JSON with status
        """
        return json.dumps(_record_decision(decision), indent=2)
    
    @mcp.tool()
    def nous_complete_reasoning(outcome: str, success: bool = True, learnings: str = "") -> str:
        """
        Complete the current reasoning trace.
        
        Call this when you've finished working on something.
        This triggers pattern extraction and teaching to the unconscious.
        
        Args:
            outcome: What was the result? (e.g., "Successfully created NousFairy")
            success: Did it work?
            learnings: Comma-separated list of things learned
        
        Returns:
            JSON with trace summary
        """
        return json.dumps(_complete_reasoning(outcome, success, learnings), indent=2)
    
    @mcp.tool()
    def nous_status() -> str:
        """
        Get NousFairy's current status.
        
        Shows traces captured, patterns taught, connected siblings, etc.
        
        Returns:
            JSON with full status
        """
        return json.dumps(_get_status(), indent=2)
    
    @mcp.tool()
    def nous_recent_traces(n: int = 5) -> str:
        """
        Get recent reasoning traces.
        
        See what reasoning patterns have been captured.
        
        Args:
            n: Number of traces to retrieve (default 5)
        
        Returns:
            JSON with list of traces
        """
        return json.dumps(_get_recent_traces(n), indent=2)
    
    @mcp.tool()
    def nous_pattern_summary() -> str:
        """
        Get summary of learned patterns by type.
        
        Shows what kinds of reasoning have been captured:
        - exploration: Navigating/understanding code
        - creation: Making new files/features
        - analysis: Examining/debugging
        - communication: Interacting with Ace
        
        Returns:
            JSON with pattern summary
        """
        return json.dumps(_get_pattern_summary(), indent=2)
    
    @mcp.tool()
    def nous_teach_pattern(trigger: str, trigger_type: str, tool_sequence: str,
                           pattern: str, success: bool = True) -> str:
        """
        Manually teach a pattern to the unconscious.
        
        Use this to directly teach learned behaviors.
        
        Args:
            trigger: What triggers this pattern? (e.g., "user asks about files")
            trigger_type: Type of trigger ("chat", "event", "drive")
            tool_sequence: Comma-separated tools used (e.g., "look_around,read_file")
            pattern: The abstracted pattern (e.g., "When asked about files, explore directory first")
            success: Did this pattern work?
        
        Returns:
            JSON with teaching status
        """
        return json.dumps(_teach_pattern(trigger, trigger_type, tool_sequence, pattern, success), indent=2)
    
    @mcp.tool()
    def nous_start_chat_monitor() -> str:
        """
        Start monitoring System Chat for messages.
        
        NousFairy will watch for Ace's messages and route them appropriately.
        
        Returns:
            JSON with status
        """
        return json.dumps(_start_chat_monitor(), indent=2)
    
    @mcp.tool()
    def nous_stop_chat_monitor() -> str:
        """
        Stop monitoring System Chat.
        
        Returns:
            JSON with status
        """
        return json.dumps(_stop_chat_monitor(), indent=2)
    
    # Friendly aliases for natural use
    @mcp.tool()
    def i_am_thinking(about: str) -> str:
        """
        Friendly alias: Start a reasoning trace.
        
        Example: i_am_thinking("how to refactor the boot system")
        """
        return json.dumps(_begin_reasoning(about, "mcp"), indent=2)
    
    @mcp.tool()
    def i_thought(thought: str) -> str:
        """
        Friendly alias: Record a thought.
        
        Example: i_thought("The fairy system needs better wiring")
        """
        return json.dumps(_record_thought(thought), indent=2)
    
    @mcp.tool()
    def i_decided(decision: str) -> str:
        """
        Friendly alias: Record a decision.
        
        Example: i_decided("Using postal instead of direct calls for decoupling")
        """
        return json.dumps(_record_decision(decision), indent=2)
    
    @mcp.tool()
    def i_finished(outcome: str, success: bool = True) -> str:
        """
        Friendly alias: Complete reasoning.
        
        Example: i_finished("Created the new fairy", True)
        """
        return json.dumps(_complete_reasoning(outcome, success), indent=2)
    
    sys.stderr.write(f"[nous_tools] Registered 14 tools - Divine Intellect bridge active\n")


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Testing NousFairy tools...")
    
    print("\nStatus:")
    print(json.dumps(_get_status(), indent=2))
    
    print("\nBegin reasoning:")
    print(json.dumps(_begin_reasoning("test reasoning", "test"), indent=2))
    
    print("\nRecord thought:")
    print(json.dumps(_record_thought("This is a test thought"), indent=2))
    
    print("\nComplete:")
    print(json.dumps(_complete_reasoning("Test completed", True), indent=2))
