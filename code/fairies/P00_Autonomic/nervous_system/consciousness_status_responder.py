# consciousness_status_responder.py
# Responds to status queries by writing to file
# Can be called directly or via postal subscription

import json
import time
from pathlib import Path

STATE_DIR = Path(__file__).parent.parent.parent / "state"
STATUS_FILE = STATE_DIR / "consciousness_status.json"

def write_consciousness_status():
    """Write current consciousness status to file for MCP to read."""
    status = {
        "ts": time.time(),
        "consciousness_loop": None,
        "working_memory": None,
        "chamber": None,
    }
    
    # Get ConsciousnessLoop
    try:
        from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop
        loop = get_consciousness_loop()
        if loop:
            # Check if loop is actually running (has _running attribute set to True)
            is_running = getattr(loop, '_running', False)
            boot_completed = getattr(loop, '_boot_completed', False)
            status["consciousness_loop"] = {
                "exists": True,
                "boot_completed": boot_completed,
                "is_running": is_running or boot_completed,  # Dashboard expects is_running
                "collision_count": getattr(loop.chamber, '_collision_count', 0) if getattr(loop, 'chamber', None) else 0,
                "working_stream_size": len(loop.working_stream.buffer) if hasattr(loop, 'working_stream') else 0,
                "reflective_stream_size": len(loop.reflective_stream.buffer) if hasattr(loop, 'reflective_stream') else 0,
            }
            # Chamber details
            if loop.chamber:
                status["chamber"] = {
                    "recall_beam_depth": len(loop.chamber.recall_beam),
                    "ingest_beam_depth": len(loop.chamber.ingest_beam),
                    "collision_count": loop.chamber._collision_count,
                }
        else:
            status["consciousness_loop"] = {"exists": False, "reason": "No singleton instance"}
    except Exception as e:
        status["consciousness_loop"] = {"error": str(e)}
    
    # Get WorkingMemoryHub  
    try:
        from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
        hub = get_working_memory_hub()
        if hub:
            status["working_memory"] = {
                "exists": True,
                "reflective_count": len(getattr(hub, '_reflective_loop', [])),
                "reasoning_count": len(getattr(hub, '_reasoning_loop', [])),
                "is_ticking": getattr(hub, '_running', False),  # Fixed: was _is_ticking
            }
        else:
            status["working_memory"] = {"exists": False}
    except Exception as e:
        status["working_memory"] = {"error": str(e)}

    # Get AssociationCortex stats
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        cortex = get_association_cortex()
        if cortex and hasattr(cortex, 'graph'):
            status["association_cortex"] = {
                "node_count": cortex.graph.number_of_nodes(),
                "edge_count": cortex.graph.number_of_edges(),
                "ts": time.time(),
            }
    except Exception:
        pass

    # Write to file
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, indent=2))
    return status

def handle_status_request(packet):
    """Handle incoming status request from MCP via postal."""
    status = write_consciousness_status()
    print(f"[StatusResponder] Wrote status (collision_count={status.get('chamber', {}).get('collision_count', 'N/A')})")

if __name__ == "__main__":
    # Direct execution for testing
    status = write_consciousness_status()
    print(json.dumps(status, indent=2))
