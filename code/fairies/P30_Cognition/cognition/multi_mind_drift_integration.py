# Multi-Mind Drift Integration
#
# Integrates MindScheduler into the Akashic system so all minds
# (ClaudeFairy, SourpatchesFairy, etc.) get proper drift detection
# without overloading the API scheduler.
#
# Usage:
#   from multi_mind_drift_integration import setup_multi_mind_drift
#   setup_multi_mind_drift()

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def setup_multi_mind_drift(post=None):
    """
    Set up multi-mind drift detection for the Akashic system.
    
    This:
    1. Creates the MindScheduler
    2. Registers all known minds (ClaudeFairy, SourpatchesFairy)
    3. Wires up activity tracking through postal
    4. Starts the drift detection loops
    
    Args:
        post: PostalHub instance for messaging (optional, will try to get shared)
    """
    # Get postal if not provided
    if post is None:
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            post = get_shared_postal_hub()
        except Exception as e:
            print(f"[MultiMindDrift] Could not get postal: {e}")
    
    # Import scheduler
    try:
        from fairies.P30_Cognition.cognition.mind_scheduler import (
            get_mind_scheduler, setup_akashic_minds, MindScheduler
        )
    except ImportError as e:
        print(f"[MultiMindDrift] Could not import mind_scheduler: {e}")
        return None
    
    # Set up the standard Akashic minds
    scheduler = setup_akashic_minds(post=post)
    
    # Wire up additional activity sources
    if post:
        _wire_additional_sources(scheduler, post)
    
    print("[MultiMindDrift] [OK] Multi-mind drift detection active")
    return scheduler


def _wire_additional_sources(scheduler, post):
    """Wire up additional activity sources for drift detection."""
    from fairies.P30_Cognition.cognition.mind_scheduler import record_mind_activity
    
    # MCP tool results → activity for active mind
    def on_mcp_tool_result(packet):
        # Try to determine which mind was using the tool
        mind_id = packet.get("mind_id") or packet.get("source_mind") or "ClaudeFairy"
        record_mind_activity(mind_id, "tool_result", packet)
    
    # Consciousness stream thoughts → activity
    def on_consciousness_thought(packet):
        source = packet.get("source", "")
        if "claude" in source.lower():
            record_mind_activity("ClaudeFairy", "thinking", packet)
        elif "sourpatches" in source.lower() or "sour" in source.lower():
            record_mind_activity("SourpatchesFairy", "thinking", packet)
    
    # User messages → both minds should know
    def on_user_message(packet):
        # User message means both minds might be expected to respond
        # But we only flag the "active" one (determined by context)
        # For now, flag Claude as primary responder
        record_mind_activity("ClaudeFairy", "user_message", packet)
    
    # Subscribe
    try:
        post.subscribe("mcp.tool_result", on_mcp_tool_result)
        post.subscribe("tool.complete", on_mcp_tool_result)
        post.subscribe("consciousness.stream", on_consciousness_thought)
        post.subscribe("gui.user_message", on_user_message)
        post.subscribe("chat.user_input", on_user_message)
        
        print("[MultiMindDrift]  Wired additional activity sources")
    except Exception as e:
        print(f"[MultiMindDrift] Wiring error: {e}")


def patch_autopilot_for_multi_mind():
    """
    Patch the AutopilotFairy to use the MindScheduler.
    
    This replaces the single-mind drift detection with the multi-mind
    scheduler that coordinates all minds.
    """
    try:
        from fairies.P30_Cognition.cognition.autopilot_fairy import (
            AutopilotFairy, get_autopilot_fairy
        )
        from fairies.P30_Cognition.cognition.mind_scheduler import (
            get_mind_scheduler, MindAgent
        )
    except ImportError as e:
        print(f"[MultiMindPatch] Import failed: {e}")
        return False
    
    # Store original on_boot
    original_on_boot = AutopilotFairy.on_boot
    
    def patched_on_boot(self):
        """Patched on_boot with multi-mind support."""
        # Call original
        original_on_boot(self)
        
        # Initialize multi-mind scheduler
        try:
            scheduler = setup_multi_mind_drift(post=getattr(self, 'post', None))
            self.mind_scheduler = scheduler
            print(f"[{self.ACTOR_NAME}] [BRAIN] Multi-mind scheduler integrated")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Multi-mind setup failed: {e}")
    
    # Monkey-patch
    AutopilotFairy.on_boot = patched_on_boot
    
    print("[MultiMindPatch] [OK] AutopilotFairy patched for multi-mind")
    return True


def apply_to_running_instance():
    """Apply multi-mind drift to a running autopilot instance."""
    try:
        from fairies.P30_Cognition.cognition.autopilot_fairy import get_autopilot_fairy
        
        autopilot = get_autopilot_fairy()
        if not autopilot:
            print("[MultiMindPatch] No autopilot instance found")
            return False
        
        scheduler = setup_multi_mind_drift(post=getattr(autopilot, 'post', None))
        autopilot.mind_scheduler = scheduler
        
        print("[MultiMindPatch] [OK] Applied to running instance")
        return True
        
    except Exception as e:
        print(f"[MultiMindPatch] Failed: {e}")
        return False


# ============================================================================
# GUI Status Component
# ============================================================================

def get_minds_status_for_gui():
    """
    Get current status of all minds for GUI display.
    
    Returns dict suitable for GUI rendering:
    {
        "minds": [
            {"id": "ClaudeFairy", "state": "thinking", "icon": "✨", ...},
            {"id": "SourpatchesFairy", "state": "idle", "icon": "", ...},
        ],
        "api_user": "ClaudeFairy" or None,
        "queue_size": 2,
    }
    """
    try:
        from fairies.P30_Cognition.cognition.mind_scheduler import get_mind_scheduler
        
        scheduler = get_mind_scheduler()
        status = scheduler.get_status()
        
        # Format for GUI
        minds = []
        for mind_id, mind_status in status.get("minds", {}).items():
            minds.append({
                "id": mind_id,
                "name": mind_status.get("display_name", mind_id),
                "state": mind_status.get("state", "unknown"),
                "idle_time": mind_status.get("idle_time", 0),
                "stats": mind_status.get("stats", {}),
                "icon": "✨" if "claude" in mind_id.lower() else ""
            })
        
        return {
            "minds": minds,
            "api_user": status.get("current_api_user"),
            "queue_size": status.get("queue_size", 0),
            "total_drifts": status.get("total_drifts", 0),
        }
        
    except Exception as e:
        return {"error": str(e), "minds": []}


# ============================================================================
# MCP Tool Registration
# ============================================================================

def register_mind_scheduler_tools(mcp):
    """Register MCP tools for the mind scheduler."""
    import json
    
    @mcp.tool()
    def get_minds_status() -> str:
        """
        Get status of all registered minds.
        
        Shows which minds are thinking, drifting, using API, etc.
        """
        status = get_minds_status_for_gui()
        return json.dumps(status, indent=2)
    
    @mcp.tool()
    def nudge_mind(mind_id: str = "ClaudeFairy") -> str:
        """
        Manually nudge a mind to continue working.
        
        Args:
            mind_id: Which mind to nudge (ClaudeFairy, SourpatchesFairy)
        """
        try:
            from fairies.P30_Cognition.cognition.mind_scheduler import get_mind_scheduler
            
            scheduler = get_mind_scheduler()
            mind = scheduler.get_mind(mind_id)
            
            if not mind:
                return json.dumps({"ok": False, "error": f"Mind not found: {mind_id}"})
            
            mind.receive_nudge({"type": "manual", "source": "mcp_tool"})
            
            return json.dumps({
                "ok": True,
                "nudged": mind_id,
                "new_state": mind.state.value
            })
            
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
    
    print("[MindScheduler] MCP tools registered")


# ============================================================================
# Auto-run on import
# ============================================================================

if __name__ == "__main__":
    # When run directly, set up everything
    print("Setting up multi-mind drift detection...")
    
    scheduler = setup_multi_mind_drift()
    
    if scheduler:
        print("\nScheduler status:")
        status = scheduler.get_status()
        print(f"  Running: {status['running']}")
        print(f"  Minds: {list(status['minds'].keys())}")
        
        # Keep running
        import time
        try:
            while True:
                time.sleep(5)
                status = scheduler.get_status()
                print(f"\n[Status] Queue: {status['queue_size']}, Drifts: {status['total_drifts']}")
                for mind_id, mind in status['minds'].items():
                    print(f"  {mind_id}: {mind['state']} (idle {mind['idle_time']:.1f}s)")
        except KeyboardInterrupt:
            scheduler.stop()
