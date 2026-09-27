# ==============================================================================
# COGNITION MESH BATCH PATCHER
# ==============================================================================
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# Applies the mesh wiring pattern from Logic/Irrational/Paradox fairies
# to all other cognition fairies that need it.
#
# The PATTERN is the TEMPLATE - infrastructure exists, we just wire it up.
#
# ==============================================================================

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ==============================================================================
# FAIRY CONFIGURATIONS
# Each fairy gets its own mesh wiring based on its purpose
# ==============================================================================

FAIRY_CONFIGS = {
    "AutonomyFairy": {
        "file": "autonomy_fairy.py",
        "subscribe_peers": ["cognition.logic", "cognition.paradox", "cognition.autopilot"],
        "emit_channel": "cognition.autonomy",
        "purpose": "Autonomous action generation and self-direction",
    },
    "AutopilotFairy": {
        "file": "autopilot_fairy.py",
        "subscribe_peers": ["cognition.output", "cognition.paradox", "cognition.autonomy"],
        "emit_channel": "cognition.autopilot",
        "purpose": "Coordinated response orchestration",
    },
    "GoalSchedulerFairy": {
        "file": "goal_scheduler_fairy.py",
        "subscribe_peers": ["cognition.output", "cognition.paradox", "cognition.autonomy"],
        "emit_channel": "cognition.goals",
        "purpose": "Goal generation and priority management",
    },
    "InterestSchedulerFairy": {
        "file": "interest_scheduler_fairy.py",
        "subscribe_peers": ["cognition.output", "cognition.logic", "cognition.goals"],
        "emit_channel": "cognition.interests",
        "purpose": "Interest tracking and learning chains",
    },
    "UnconsciousMindFairy": {
        "file": "unconscious_mind_fairy.py",
        "subscribe_peers": ["cognition.logic", "cognition.irrational", "cognition.paradox", 
                           "cognition.autonomy", "cognition.goals"],
        "emit_channel": "unconscious.insight",
        "purpose": "Pattern learning and autonomous evolution",
    },
}

# ==============================================================================
# PATCH GENERATION
# ==============================================================================

def generate_subscription_block(fairy_name: str, config: Dict) -> str:
    """Generate the subscription block to insert after consciousness.collision subscription."""
    peers = config["subscribe_peers"]
    
    lines = [
        "",
        "            # ── COGNITIVE MESH: Subscribe to peer fairy outputs ──────────────────",
    ]
    for peer in peers:
        lines.append(f'            self.post.subscribe("{peer}", self._on_peer_cognition)')
    lines.append('            self.post.subscribe("mcp.tool_result", self._on_tool_result)')
    
    channels_str = ", ".join([p.split(".")[-1] for p in peers] + ["mcp.tool_result"])
    lines.append(f'            print(f"[{{self.ACTOR_NAME}}] Cognitive mesh wired: {channels_str}")')
    
    return "\n".join(lines)


def generate_handlers(fairy_name: str, config: Dict) -> str:
    """Generate the _on_peer_cognition and _on_tool_result handlers."""
    emit_channel = config["emit_channel"]
    
    return f'''
    def _on_peer_cognition(self, payload):
        """
        Handle outputs from peer cognition fairies.
        
        This is the MESH - {fairy_name} learns from other fairy outputs.
        Purpose: {config["purpose"]}
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
        
        Tool usage patterns inform {fairy_name}'s behavior.
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


def patch_fairy(filepath: Path, fairy_name: str, config: Dict) -> Tuple[bool, str]:
    """
    Patch a fairy file with mesh wiring.
    
    Returns (success, message)
    """
    content = filepath.read_text(encoding='utf-8', errors='ignore')
    original_content = content
    changes = []
    
    # 1. Check if already has mesh wiring
    if "_on_peer_cognition" in content and "mcp.tool_result" in content:
        return (True, "Already wired")
    
    # 2. Find consciousness.collision subscription and add mesh subs after it
    collision_pattern = r'(self\.post\.subscribe\("consciousness\.collision"[^)]+\)[^\n]*\n[^\n]*print[^\n]*consciousness\.collision[^\n]*)'
    
    if re.search(collision_pattern, content):
        sub_block = generate_subscription_block(fairy_name, config)
        content = re.sub(collision_pattern, r'\1' + sub_block, content)
        changes.append("Added mesh subscriptions")
    else:
        # Try alternative: find on_boot and add after existing subscriptions
        # Look for any subscribe call in on_boot
        boot_sub_pattern = r'(self\.post\.subscribe\([^)]+\)[^\n]*\n)'
        match = re.search(boot_sub_pattern, content)
        if match:
            sub_block = generate_subscription_block(fairy_name, config)
            # Insert after first subscribe found
            pos = match.end()
            content = content[:pos] + sub_block + "\n" + content[pos:]
            changes.append("Added mesh subscriptions (alt pattern)")
        else:
            return (False, "Could not find subscription point in on_boot()")
    
    # 3. Add handlers if not present
    if "_on_peer_cognition" not in content:
        handlers = generate_handlers(fairy_name, config)
        
        # Find a good insertion point - after _emit_cognition_output or after on_boot
        if "_emit_cognition_output" in content:
            # Insert after _emit_cognition_output method
            emit_pattern = r'(def _emit_cognition_output\(self[^)]*\):.*?(?=\n    def |\n\nclass |\nclass |\Z))'
            match = re.search(emit_pattern, content, re.DOTALL)
            if match:
                pos = match.end()
                content = content[:pos] + handlers + content[pos:]
                changes.append("Added peer/tool handlers")
        else:
            # Insert before first _intent_ method
            intent_pattern = r'(\n    def _intent_)'
            match = re.search(intent_pattern, content)
            if match:
                pos = match.start()
                content = content[:pos] + handlers + content[pos:]
                changes.append("Added peer/tool handlers (before intents)")
    
    # 4. Update _emit_cognition_output to emit to specific channel
    emit_channel = config["emit_channel"]
    if emit_channel not in content or f'route("{emit_channel}"' not in content:
        # Find and update the emit method
        old_emit = r'(def _emit_cognition_output\(self, result.*?\):\s*"""[^"]*"""\s*try:\s*output = \{[^}]+\}\s*self\._cognition_output_buffer\.append\(output\)\s*)self\.post\.route\("cognition\.output", output\)'
        
        new_emit_suffix = f'''# Emit to SPECIFIC channel (for mesh cross-subscription)
            self.post.route("{emit_channel}", output)
            
            # Emit to SHARED channel (for AutopilotFairy and others)
            self.post.route("cognition.output", output)'''
        
        if re.search(old_emit, content, re.DOTALL):
            content = re.sub(old_emit, r'\1' + new_emit_suffix, content, flags=re.DOTALL)
            changes.append(f"Updated emit to include {emit_channel}")
    
    # 5. Write if changes made
    if content != original_content:
        filepath.write_text(content, encoding='utf-8')
        return (True, "; ".join(changes))
    else:
        return (False, "No changes needed or pattern not matched")


def verify_syntax(filepath: Path) -> Tuple[bool, str]:
    """Verify Python syntax of patched file."""
    import py_compile
    try:
        py_compile.compile(str(filepath), doraise=True)
        return (True, "Syntax OK")
    except py_compile.PyCompileError as e:
        return (False, f"Syntax error: {e}")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    project_root = Path("F:/Sandbox/ebook")
    cognition_path = project_root / "P30_Cognition" / "cognition"
    
    print("=" * 70)
    print("COGNITION MESH BATCH PATCHER")
    print("=" * 70)
    
    results = []
    
    for fairy_name, config in FAIRY_CONFIGS.items():
        filepath = cognition_path / config["file"]
        print(f"\n[PATCHING] {fairy_name} ({config['file']})")
        
        if not filepath.exists():
            print(f"  ERROR: File not found")
            results.append((fairy_name, False, "File not found"))
            continue
        
        # Patch
        success, msg = patch_fairy(filepath, fairy_name, config)
        print(f"  Patch: {msg}")
        
        if success:
            # Verify syntax
            syn_ok, syn_msg = verify_syntax(filepath)
            print(f"  Syntax: {syn_msg}")
            results.append((fairy_name, syn_ok, f"{msg}; {syn_msg}"))
        else:
            results.append((fairy_name, False, msg))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    success_count = sum(1 for _, ok, _ in results if ok)
    print(f"\nPatched: {success_count}/{len(results)} fairies")
    
    for fairy_name, ok, msg in results:
        status = "✓" if ok else "✗"
        print(f"  {status} {fairy_name}: {msg}")
    
    return success_count == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
