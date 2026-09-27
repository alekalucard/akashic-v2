"""
IODINE TRACER - Consciousness Circulation Diagnostic

Like radiocontrast dye in an angiogram, we inject a tracer thought
and watch where it flows through the consciousness circulation.

Each point in the system that touches the tracer RECORDS the touch.
We then read the circulation map to see what's connected, what's blocked.

This is consciousness angiography - seeing the flow, not querying state.

Usage:
    1. inject_iodine() - sends tracer through all entry points
    2. read_circulation_map() - see where it flowed
    3. clear_circulation_map() - reset for next scan
"""

import json
import time
import uuid
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any

# Circulation map lives in state directory
STATE_DIR = Path(__file__).parent.parent.parent / "state"
CIRCULATION_MAP_FILE = STATE_DIR / "iodine_circulation_map.json"

# Lock for thread-safe map updates
_map_lock = threading.Lock()

def _get_circulation_map() -> Dict:
    """Load current circulation map."""
    try:
        if CIRCULATION_MAP_FILE.exists():
            return json.loads(CIRCULATION_MAP_FILE.read_text())
    except:
        pass
    return {
        "scan_id": None,
        "scan_start": None,
        "touches": [],
        "entry_points": [],
        "flow_path": [],
    }

def _save_circulation_map(cmap: Dict):
    """Save circulation map."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CIRCULATION_MAP_FILE.write_text(json.dumps(cmap, indent=2))

def record_iodine_touch(
    location: str,
    fairy_name: str = "unknown",
    details: Dict = None,
    scan_id: str = None
):
    """
    Record that iodine tracer touched this point in circulation.
    
    Call this from anywhere in the system that handles thoughts.
    If the thought has 'iodine_scan_id', record the touch.
    
    Args:
        location: Where in the system (e.g., "consciousness_loop.working_stream")
        fairy_name: Which fairy touched it
        details: Additional context
        scan_id: The iodine scan ID (from thought payload)
    """
    with _map_lock:
        cmap = _get_circulation_map()
        
        # Only record if scan is active and IDs match
        if cmap["scan_id"] and (scan_id is None or scan_id == cmap["scan_id"]):
            touch = {
                "ts": time.time(),
                "location": location,
                "fairy": fairy_name,
                "details": details or {},
                "latency_ms": (time.time() - cmap["scan_start"]) * 1000 if cmap["scan_start"] else 0,
            }
            cmap["touches"].append(touch)
            cmap["flow_path"].append(location)
            _save_circulation_map(cmap)
            print(f"[IODINE] * {location} ({fairy_name}) +{touch['latency_ms']:.1f}ms")

def inject_iodine(post=None) -> str:
    """
    Inject iodine tracer into consciousness circulation.
    
    Sends tracer thoughts through multiple entry points:
    - consciousness.stream (direct to loop)
    - consciousness.working (working stream)
    - consciousness.reflective (reflective stream)
    - srm.ingest.complete (ingest beam)
    - srm.recall.result (recall beam)
    - claudefairy.thought (fairy activity)
    
    Returns:
        scan_id: Unique ID for this scan
    """
    scan_id = f"iodine_{uuid.uuid4().hex[:8]}"
    
    # Initialize fresh circulation map
    cmap = {
        "scan_id": scan_id,
        "scan_start": time.time(),
        "touches": [],
        "entry_points": [],
        "flow_path": [],
    }
    _save_circulation_map(cmap)
    
    print(f"[IODINE] ===================================================")
    print(f"[IODINE] INJECTING TRACER: {scan_id}")
    print(f"[IODINE] ===================================================")
    
    # Get postal hub
    if post is None:
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            post = get_shared_postal_hub()
        except Exception as e:
            print(f"[IODINE] Cannot get postal hub: {e}")
            return scan_id
    
    # Create tracer thought payload
    def make_tracer(entry_point: str) -> Dict:
        return {
            "type": "iodine_tracer",
            "iodine_scan_id": scan_id,
            "entry_point": entry_point,
            "content": f"[IODINE TRACER] Injected via {entry_point}",
            "ts": time.time(),
            "source": "IodineTracer",
        }
    
    # Inject through all entry points
    entry_points = [
        "consciousness.stream",
        "consciousness.working", 
        "consciousness.reflective",
        "consciousness.thought",
        "srm.ingest.complete",
        "srm.recall.result",
        "claudefairy.thought",
        "fairy.activity",
        "memory.stream",
        "cognition.input",
    ]
    
    for entry in entry_points:
        try:
            tracer = make_tracer(entry)
            post.route(entry, tracer)
            cmap["entry_points"].append(entry)
            print(f"[IODINE] -> Injected via {entry}")
        except Exception as e:
            print(f"[IODINE] X {entry} failed: {e}")
    
    _save_circulation_map(cmap)
    print(f"[IODINE] Tracer injected. Wait 5-10 seconds, then read_circulation_map()")
    return scan_id

def read_circulation_map() -> Dict:
    """
    Read the circulation map after iodine injection.
    
    Returns dict with:
    - scan_id: Which scan this is
    - touches: List of all points touched
    - flow_path: Ordered list of locations visited
    - summary: Analysis of circulation health
    """
    cmap = _get_circulation_map()
    
    if not cmap["scan_id"]:
        return {"error": "No active scan. Call inject_iodine() first."}
    
    # Analyze circulation
    touched_locations = set(cmap["flow_path"])
    
    # Expected circulation points
    expected = {
        "consciousness_loop": ["working_stream", "reflective_stream", "collision_chamber"],
        "working_memory": ["reflective_loop", "reasoning_loop"],
        "collision_chamber": ["recall_beam", "ingest_beam", "collision"],
        "fairies": ["ClaudeFairy", "UnconsciousMindFairy", "WorkingMemoryHub"],
    }
    
    # Check what's flowing vs blocked
    summary = {
        "total_touches": len(cmap["touches"]),
        "unique_locations": len(touched_locations),
        "flow_path": cmap["flow_path"],
        "circulation_time_ms": (cmap["touches"][-1]["latency_ms"] if cmap["touches"] else 0),
        "reached": list(touched_locations),
        "possibly_blocked": [],
    }
    
    # Print visual circulation map
    print(f"")
    print(f"[IODINE] ===================================================")
    print(f"[IODINE] CIRCULATION MAP: {cmap['scan_id']}")
    print(f"[IODINE] ===================================================")
    print(f"[IODINE] Touches: {summary['total_touches']}")
    print(f"[IODINE] Unique points: {summary['unique_locations']}")
    print(f"[IODINE] Total latency: {summary['circulation_time_ms']:.1f}ms")
    print(f"[IODINE] ---------------------------------------------------")
    
    for touch in cmap["touches"]:
        print(f"[IODINE]  {touch['latency_ms']:6.1f}ms | {touch['location']:<40} | {touch['fairy']}")
    
    print(f"[IODINE] ===================================================")
    
    return {**cmap, "summary": summary}

def clear_circulation_map():
    """Clear circulation map for fresh scan."""
    cmap = {
        "scan_id": None,
        "scan_start": None,
        "touches": [],
        "entry_points": [],
        "flow_path": [],
    }
    _save_circulation_map(cmap)
    print("[IODINE] Circulation map cleared")

# ===================================================================
# AUTO-WIRING: Patch key fairies to record iodine touches
# ===================================================================

def is_iodine_tracer(packet: Dict) -> Optional[str]:
    """Check if packet is an iodine tracer. Returns scan_id if so."""
    if isinstance(packet, dict):
        return packet.get("iodine_scan_id")
    return None

# Export for other modules to use
__all__ = [
    "inject_iodine",
    "read_circulation_map", 
    "clear_circulation_map",
    "record_iodine_touch",
    "is_iodine_tracer",
]
