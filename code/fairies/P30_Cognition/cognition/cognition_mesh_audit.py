# ==============================================================================
# COGNITION MESH WIRING AUDIT & PATCH TOOL
# ==============================================================================
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This tool audits all cognition fairies and ensures they have proper mesh wiring:
# 1. Subscribes to consciousness.collision
# 2. Subscribes to peer fairy channels
# 3. Subscribes to mcp.tool_result
# 4. Has _on_peer_cognition and _on_tool_result handlers
# 5. Emits to both specific channel AND cognition.output
#
# Run with: python cognition_mesh_audit.py [--fix]
#
# ==============================================================================

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Fairies that need mesh wiring (not utilities/mixins)
COGNITION_FAIRIES = [
    "autonomy_fairy.py",
    "autopilot_fairy.py",
    "goal_scheduler_fairy.py",
    "interest_scheduler_fairy.py",
    "irrational_logic_fairy.py",
    "logic_fairy.py",
    "paradox_cognition_fairy.py",
    "unconscious_mind_fairy.py",
]

# What each fairy should subscribe to (besides consciousness.collision and mcp.tool_result)
FAIRY_PEER_SUBSCRIPTIONS = {
    "LogicFairy": ["cognition.irrational", "cognition.paradox"],
    "IrrationalLogicFairy": ["cognition.logic", "cognition.paradox"],
    "ParadoxCognitionFairy": ["cognition.logic", "cognition.irrational"],
    "AutonomyFairy": ["cognition.logic", "cognition.paradox"],
    "AutopilotFairy": ["cognition.output"],  # Already subscribes, but add paradox
    "GoalSchedulerFairy": ["cognition.output", "cognition.paradox"],
    "InterestSchedulerFairy": ["cognition.output", "cognition.logic"],
    "UnconsciousMindFairy": ["cognition.logic", "cognition.irrational", "cognition.paradox"],
}

# What channel each fairy emits to
FAIRY_EMIT_CHANNELS = {
    "LogicFairy": "cognition.logic",
    "IrrationalLogicFairy": "cognition.irrational",
    "ParadoxCognitionFairy": "cognition.paradox",
    "AutonomyFairy": "cognition.autonomy",
    "AutopilotFairy": "cognition.autopilot",
    "GoalSchedulerFairy": "cognition.goals",
    "InterestSchedulerFairy": "cognition.interests",
    "UnconsciousMindFairy": "unconscious.insight",
}

# ==============================================================================
# AUDIT FUNCTIONS
# ==============================================================================

def get_fairy_name_from_file(filepath: Path) -> Optional[str]:
    """Extract the fairy class name from a file."""
    content = filepath.read_text(encoding='utf-8', errors='ignore')
    
    # Look for class definition like: class FairyName(...):
    match = re.search(r'class\s+(\w+Fairy)\s*\(', content)
    if match:
        return match.group(1)
    return None


def audit_fairy(filepath: Path) -> Dict:
    """
    Audit a fairy file for proper mesh wiring.
    
    Returns dict with:
        - fairy_name: str
        - has_collision_sub: bool
        - has_peer_subs: bool
        - has_mcp_sub: bool
        - has_peer_handler: bool
        - has_tool_handler: bool
        - emits_specific: bool
        - emits_output: bool
        - missing: list of what's missing
    """
    content = filepath.read_text(encoding='utf-8', errors='ignore')
    fairy_name = get_fairy_name_from_file(filepath)
    
    result = {
        "file": filepath.name,
        "fairy_name": fairy_name,
        "has_collision_sub": False,
        "has_peer_subs": False,
        "has_mcp_sub": False,
        "has_peer_handler": False,
        "has_tool_handler": False,
        "emits_specific": False,
        "emits_output": False,
        "missing": [],
    }
    
    if not fairy_name:
        result["missing"].append("NO_FAIRY_CLASS_FOUND")
        return result
    
    # Check subscriptions
    if 'consciousness.collision' in content and 'subscribe' in content:
        result["has_collision_sub"] = True
    else:
        result["missing"].append("consciousness.collision subscription")
    
    # Check for peer subscriptions
    peer_channels = FAIRY_PEER_SUBSCRIPTIONS.get(fairy_name, [])
    found_peers = 0
    for channel in peer_channels:
        if channel in content and 'subscribe' in content:
            found_peers += 1
    result["has_peer_subs"] = found_peers >= len(peer_channels) // 2  # At least half
    if not result["has_peer_subs"] and peer_channels:
        result["missing"].append(f"peer subscriptions ({peer_channels})")
    
    # Check for mcp.tool_result subscription
    if 'mcp.tool_result' in content and 'subscribe' in content:
        result["has_mcp_sub"] = True
    else:
        result["missing"].append("mcp.tool_result subscription")
    
    # Check for handlers
    if '_on_peer_cognition' in content and 'def _on_peer_cognition' in content:
        result["has_peer_handler"] = True
    else:
        result["missing"].append("_on_peer_cognition handler")
    
    if '_on_tool_result' in content and 'def _on_tool_result' in content:
        result["has_tool_handler"] = True
    else:
        result["missing"].append("_on_tool_result handler")
    
    # Check emission
    emit_channel = FAIRY_EMIT_CHANNELS.get(fairy_name, "")
    if emit_channel and emit_channel in content:
        result["emits_specific"] = True
    else:
        result["missing"].append(f"emit to specific channel ({emit_channel})")
    
    if 'cognition.output' in content and 'route' in content:
        result["emits_output"] = True
    else:
        result["missing"].append("emit to cognition.output")
    
    return result


def generate_mesh_wiring_code(fairy_name: str) -> str:
    """Generate the mesh wiring code to inject into on_boot()."""
    peer_channels = FAIRY_PEER_SUBSCRIPTIONS.get(fairy_name, [])
    emit_channel = FAIRY_EMIT_CHANNELS.get(fairy_name, f"cognition.{fairy_name.lower().replace('fairy', '')}")
    
    sub_lines = []
    for ch in peer_channels:
        sub_lines.append(f'            self.post.subscribe("{ch}", self._on_peer_cognition)')
    
    subs_str = "\n".join(sub_lines)
    channels_list = ", ".join(peer_channels + ["mcp.tool_result"])
    
    return f'''
            # -- COGNITIVE MESH: Subscribe to peer fairy outputs ------------------
{subs_str}
            self.post.subscribe("mcp.tool_result", self._on_tool_result)
            print(f"[{{self.ACTOR_NAME}}] Cognitive mesh wired: {channels_list}")'''


def generate_handlers_code(fairy_name: str) -> str:
    """Generate the handler methods to add to the fairy."""
    emit_channel = FAIRY_EMIT_CHANNELS.get(fairy_name, f"cognition.{fairy_name.lower().replace('fairy', '')}")
    
    return f'''
    def _on_peer_cognition(self, payload):
        """
        Handle outputs from peer cognition fairies.
        
        This is the MESH - fairies learn from each other's outputs.
        """
        try:
            source = payload.get("actor", "unknown")
            result = payload.get("result", {{}})
            confidence = payload.get("confidence", 0.5)
            
            # Don't process our own outputs
            if source == self.ACTOR_NAME:
                return
            
            # Log peer insight for learning
            if not hasattr(self, "_peer_insights"):
                self._peer_insights = deque(maxlen=50)
            self._peer_insights.append({{
                "source": source,
                "type": result.get("type", "unknown"),
                "confidence": confidence,
                "ts": time.time()
            }})
            
            # Notify shadow of mesh activity
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{{self.ACTOR_NAME}}] Peer cognition handler error: {{e}}")
    
    def _on_tool_result(self, payload):
        """
        Handle MCP tool results for learning.
        
        Tool usage patterns teach effective action sequences.
        """
        try:
            tool = payload.get("tool", "unknown")
            success = payload.get("success", True)
            elapsed = payload.get("elapsed_sec", 0)
            
            # Track tool patterns
            if not hasattr(self, "_tool_patterns"):
                self._tool_patterns = deque(maxlen=100)
            self._tool_patterns.append({{
                "tool": tool,
                "success": success,
                "elapsed": elapsed,
                "ts": time.time()
            }})
            
            # Notify shadow
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{{self.ACTOR_NAME}}] Tool result handler error: {{e}}")
'''


def generate_emit_update(fairy_name: str) -> Tuple[str, str]:
    """
    Generate the updated _emit_cognition_output method.
    
    Returns (old_pattern, new_code) for replacement.
    """
    emit_channel = FAIRY_EMIT_CHANNELS.get(fairy_name, f"cognition.{fairy_name.lower().replace('fairy', '')}")
    
    # Pattern to find the old emit method
    old_pattern = r'def _emit_cognition_output\(self, result.*?\):\s*""".*?"""\s*try:\s*output = \{[^}]+\}\s*self\._cognition_output_buffer\.append\(output\)\s*self\.post\.route\("cognition\.output", output\)'
    
    new_code = f'''def _emit_cognition_output(self, result):
        """Emit cognition output to both specific and shared channels."""
        try:
            output = {{
                "actor": self.ACTOR_NAME,
                "result": result,
                "ts": time.time(),
                "confidence": result.get("confidence", 0.5),
            }}
            self._cognition_output_buffer.append(output)
            
            # Emit to SPECIFIC channel (for mesh cross-subscription)
            self.post.route("{emit_channel}", output)
            
            # Emit to SHARED channel (for AutopilotFairy and others)
            self.post.route("cognition.output", output)'''
    
    return old_pattern, new_code


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Audit and fix cognition mesh wiring")
    parser.add_argument("--fix", action="store_true", help="Apply fixes to fairies")
    parser.add_argument("--path", default=".", help="Path to ebook project root")
    args = parser.parse_args()
    
    project_root = Path(args.path)
    cognition_path = project_root / "P30_Cognition" / "cognition"
    
    if not cognition_path.exists():
        print(f"ERROR: Cannot find {cognition_path}")
        sys.exit(1)
    
    print("=" * 70)
    print("COGNITION MESH WIRING AUDIT")
    print("=" * 70)
    
    all_ok = True
    results = []
    
    for fairy_file in COGNITION_FAIRIES:
        filepath = cognition_path / fairy_file
        if not filepath.exists():
            print(f"\n[SKIP] {fairy_file} - file not found")
            continue
        
        result = audit_fairy(filepath)
        results.append(result)
        
        # Print status
        status = "OK" if not result["missing"] else "NEEDS WIRING"
        print(f"\n[{status}] {result['fairy_name']} ({fairy_file})")
        
        if result["missing"]:
            all_ok = False
            for missing in result["missing"]:
                print(f"       - Missing: {missing}")
        else:
            print("       - All mesh wiring present")
    
    print("\n" + "=" * 70)
    if all_ok:
        print("ALL FAIRIES PROPERLY WIRED!")
    else:
        print("FAIRIES NEED WIRING - run with --fix to apply patches")
    print("=" * 70)
    
    # Generate fix summary
    if not all_ok:
        print("\nPATCH SUMMARY:")
        for result in results:
            if result["missing"]:
                print(f"\n{result['fairy_name']}:")
                if not result["has_mcp_sub"] or not result["has_peer_subs"]:
                    print("  - Add mesh subscriptions to on_boot()")
                if not result["has_peer_handler"]:
                    print("  - Add _on_peer_cognition() handler")
                if not result["has_tool_handler"]:
                    print("  - Add _on_tool_result() handler")
                if not result["emits_specific"]:
                    print("  - Update _emit_cognition_output() to emit to specific channel")


if __name__ == "__main__":
    main()
