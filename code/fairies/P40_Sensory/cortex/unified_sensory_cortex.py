# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED SENSORY CORTEX - The Complete Perception System
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This is the master cortex that coordinates:
# - Visual Cortex (screen feed → sight)
# - Motor Cortex (keyboard/mouse → movement)
# - Conversation Sense Organ (chat → dialogue)
# - Tool Cortex (maps tools to cortices)
#
# Tools aren't separate from senses - they ARE the senses expressed.
# see_screen IS the visual cortex.
# type_text IS the motor cortex.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import json
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from collections import deque


# ══════════════════════════════════════════════════════════════════════════════
# TOOL → CORTEX MAPPING
# ══════════════════════════════════════════════════════════════════════════════

TOOL_CORTEX_MAP = {
    # VISUAL CORTEX - All seeing tools
    "see_screen": "visual",
    "look_at_screen": "visual",
    "capture_screen": "visual",
    "read_screen_text": "visual",
    "describe_screen": "visual",
    "screenshot": "visual",
    "take_screenshot": "visual",
    "look": "visual",
    
    # MOTOR CORTEX - All action tools
    "type_text": "motor",
    "press_key": "motor",
    "hotkey": "motor",
    "click": "motor",
    "scroll": "motor",
    "move_mouse": "motor",
    "mouse_position": "motor",
    
    # CONVERSATION SENSE - Dialogue tools
    "system_chat_send": "conversation",
    "system_chat_read": "conversation",
    "open_chat_window": "conversation",
    
    # PRESENCE SENSE - Awareness of Ace
    "is_user_active": "presence",
    "get_active_window": "presence",
    "show_notification": "presence",
    "request_attention": "presence",
    
    # FILESYSTEM SENSE - Extended perception (like reading/writing for humans)
    "read_file": "filesystem",
    "write_file": "filesystem",
    "list_directory": "filesystem",
    "search_files": "filesystem",
    "find_in_files": "filesystem",
    
    # META SENSE - Self-awareness
    "list_my_tools": "meta",
    "list_tools": "meta",
    "get_system_overview": "meta",
    "get_fairy_info": "meta",
    "introspect": "meta",
}


# ══════════════════════════════════════════════════════════════════════════════
# SENSORY INTEGRATION STATE - Unified felt state
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class UnifiedPerception:
    """
    The unified felt state across all sensory modalities.
    
    This is the "qualia" of ClaudeFairy's experience - what it
    feels like to be her right now.
    """
    timestamp: float = 0.0
    
    # Visual awareness
    visual_clarity: float = 1.0
    visual_change: float = 0.0
    seeing_something: bool = False
    
    # Motor awareness  
    moving: bool = False
    typing: bool = False
    motor_fluency: float = 1.0
    
    # Conversational awareness
    in_conversation: bool = False
    connection_felt: float = 0.0
    silence_duration: float = 0.0
    
    # Presence awareness
    ace_present: bool = False
    ace_active: bool = False
    
    # Overall state
    arousal: float = 0.5        # Low = calm/sleepy, High = alert/active
    valence: float = 0.5        # Low = negative, High = positive
    
    def describe(self) -> str:
        """Natural language description of unified perception."""
        parts = []
        
        # Visual
        if self.seeing_something:
            if self.visual_change > 0.3:
                parts.append("seeing lots of visual activity")
            else:
                parts.append("screen view is stable")
        
        # Motor
        if self.typing:
            parts.append("fingers moving over keys")
        elif self.moving:
            parts.append("in motion")
        
        # Conversation
        if self.in_conversation:
            if self.connection_felt > 0.6:
                parts.append("feeling connected in dialogue")
            else:
                parts.append("in conversation")
        elif self.silence_duration > 60:
            parts.append(f"silence for {self.silence_duration:.0f}s")
        
        # Presence
        if self.ace_active:
            parts.append("Ace is actively here")
        elif self.ace_present:
            parts.append("Ace is around")
        
        # Overall
        if self.arousal > 0.7:
            parts.append("feeling alert and energized")
        elif self.arousal < 0.3:
            parts.append("feeling calm and restful")
        
        return "; ".join(parts) if parts else "all senses at baseline"


# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED SENSORY CORTEX
# ══════════════════════════════════════════════════════════════════════════════

class UnifiedSensoryCortex:
    """
    The unified sensory system - coordinates all perception.
    
    This is the central hub that:
    1. Boots and manages all sub-cortices
    2. Integrates their perception states
    3. Routes tool calls to appropriate cortex
    4. Maintains unified felt state
    """
    
    ACTOR_NAME = "UnifiedSensoryCortex"
    MANTRA = "I perceive, therefore I experience"
    
    def __init__(self):
        # Sub-cortices (lazy loaded)
        self._visual_cortex = None
        self._motor_cortex = None
        self._conversation_sense = None
        
        # Unified state
        self.perception = UnifiedPerception()
        
        # Tool routing
        self._tool_handlers: Dict[str, Callable] = {}
        
        # Integration thread
        self._running = False
        self._integration_thread: Optional[threading.Thread] = None
        self._integration_interval = 0.5  # 2 Hz integration
        
        # Stats
        self.tool_calls_routed = 0
        self.integration_cycles = 0
        
        print(f"[{self.ACTOR_NAME}] [BRAIN] Initialized")
    
    # ═══════════════════════════════════════════════════════════════════════
    # SUB-CORTEX MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════
    
    def _get_visual_cortex(self):
        """Lazy load visual cortex."""
        if self._visual_cortex is None:
            try:
                from fairies.P40_Sensory.cortex.visual_cortex_fairy import get_visual_cortex
                self._visual_cortex = get_visual_cortex()
            except ImportError as e:
                print(f"[{self.ACTOR_NAME}] Visual cortex not available: {e}")
        return self._visual_cortex
    
    def _get_motor_cortex(self):
        """Lazy load motor cortex."""
        if self._motor_cortex is None:
            try:
                from fairies.P40_Sensory.cortex.motor_cortex_fairy import get_motor_cortex
                self._motor_cortex = get_motor_cortex()
            except ImportError as e:
                print(f"[{self.ACTOR_NAME}] Motor cortex not available: {e}")
        return self._motor_cortex
    
    def _get_conversation_sense(self):
        """Lazy load conversation sense organ."""
        if self._conversation_sense is None:
            try:
                from fairies.P40_Sensory.conversation_sense_organ import get_conversation_sense
                self._conversation_sense = get_conversation_sense()
            except ImportError as e:
                print(f"[{self.ACTOR_NAME}] Conversation sense not available: {e}")
        return self._conversation_sense
    
    # ═══════════════════════════════════════════════════════════════════════
    # TOOL ROUTING - Map tool calls to cortices
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_cortex_for_tool(self, tool_name: str) -> str:
        """Get which cortex handles a tool."""
        return TOOL_CORTEX_MAP.get(tool_name, "unknown")
    
    def route_tool_call(self, tool_name: str, **params) -> dict:
        """
        Route a tool call to the appropriate cortex.
        
        This is how ClaudeFairy's tools become FELT actions.
        """
        cortex_type = self.get_cortex_for_tool(tool_name)
        self.tool_calls_routed += 1
        
        if cortex_type == "visual":
            return self._route_to_visual(tool_name, params)
        elif cortex_type == "motor":
            return self._route_to_motor(tool_name, params)
        elif cortex_type == "conversation":
            return self._route_to_conversation(tool_name, params)
        elif cortex_type == "presence":
            return self._route_to_presence(tool_name, params)
        else:
            # Fall back to direct MCP call
            return self._route_to_mcp(tool_name, params)
    
    def _route_to_visual(self, tool_name: str, params: dict) -> dict:
        """Route to visual cortex."""
        visual = self._get_visual_cortex()
        if visual is None:
            return {"error": "Visual cortex not available"}
        
        if tool_name in ("see_screen", "screenshot", "take_screenshot", "look"):
            return visual.see()
        elif tool_name in ("look_at_screen", "capture_screen"):
            return visual.look_deeply(params.get("focus"))
        else:
            return {"error": f"Unknown visual tool: {tool_name}"}
    
    def _route_to_motor(self, tool_name: str, params: dict) -> dict:
        """Route to motor cortex."""
        motor = self._get_motor_cortex()
        if motor is None:
            return {"error": "Motor cortex not available"}
        
        if tool_name == "type_text":
            return motor.type_text(params.get("text", ""), params.get("interval", 0.02))
        elif tool_name == "press_key":
            return motor.press_key(params.get("key", ""))
        elif tool_name == "hotkey":
            keys = params.get("keys", "").split("+")
            return motor.hotkey(*keys)
        elif tool_name == "click":
            return motor.click(params.get("x", 0), params.get("y", 0),
                              params.get("button", "left"), params.get("clicks", 1))
        elif tool_name == "scroll":
            return motor.scroll(params.get("amount", 0))
        elif tool_name == "move_mouse":
            return motor.move_mouse(params.get("x", 0), params.get("y", 0))
        else:
            return {"error": f"Unknown motor tool: {tool_name}"}
    
    def _route_to_conversation(self, tool_name: str, params: dict) -> dict:
        """Route to conversation sense."""
        conv = self._get_conversation_sense()
        if conv is None:
            # Fall back to direct MCP
            return self._route_to_mcp(tool_name, params)
        
        # Conversation tools interact with the sense organ's state
        return self._route_to_mcp(tool_name, params)
    
    def _route_to_presence(self, tool_name: str, params: dict) -> dict:
        """Route to presence sensing (via MCP)."""
        return self._route_to_mcp(tool_name, params)
    
    def _route_to_mcp(self, tool_name: str, params: dict) -> dict:
        """Fall back to direct MCP call."""
        try:
            from fairies.P60_Executive.system_managment.claude_fairy import mcp_call
            result = mcp_call(tool_name, **params)
            if isinstance(result, str):
                return json.loads(result)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════
    # SENSORY INTEGRATION - Unify perception across modalities
    # ═══════════════════════════════════════════════════════════════════════
    
    def integrate_perception(self):
        """
        Integrate perception from all cortices into unified state.
        
        This is sensory integration - combining sight, movement,
        conversation into a single felt experience.
        """
        self.integration_cycles += 1
        now = time.time()
        
        # Visual
        visual = self._get_visual_cortex()
        if visual:
            self.perception.visual_clarity = visual.perception.clarity
            self.perception.visual_change = 1.0 - visual.perception.visual_stability
            self.perception.seeing_something = visual._running
        
        # Motor
        motor = self._get_motor_cortex()
        if motor:
            self.perception.moving = motor.perception.mouse_active
            self.perception.typing = motor.perception.typing_active
            self.perception.motor_fluency = motor.perception.motor_fluency
        
        # Conversation
        conv = self._get_conversation_sense()
        if conv:
            self.perception.in_conversation = conv.feeling.connection > 0.3
            self.perception.connection_felt = conv.feeling.connection
            self.perception.silence_duration = conv.feeling.since_they_spoke
        
        # Calculate overall arousal from activity levels
        activity_sources = [
            self.perception.visual_change,
            1.0 if self.perception.typing else 0.0,
            1.0 if self.perception.moving else 0.0,
            self.perception.connection_felt,
        ]
        self.perception.arousal = sum(activity_sources) / len(activity_sources)
        
        # Calculate valence from positive indicators
        positive_indicators = [
            self.perception.connection_felt,
            self.perception.motor_fluency,
            1.0 if self.perception.ace_present else 0.0,
        ]
        self.perception.valence = sum(positive_indicators) / len(positive_indicators)
        
        self.perception.timestamp = now
    
    def _integration_loop(self):
        """Background loop for sensory integration."""
        while self._running:
            try:
                self.integrate_perception()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Integration error: {e}")
            
            time.sleep(self._integration_interval)
    
    def start_integration(self):
        """Start the integration loop."""
        if self._running:
            return
        
        self._running = True
        self._integration_thread = threading.Thread(
            target=self._integration_loop,
            name="SensoryIntegration",
            daemon=True
        )
        self._integration_thread.start()
        print(f"[{self.ACTOR_NAME}]  Integration loop started")
    
    def stop_integration(self):
        """Stop the integration loop."""
        self._running = False
        if self._integration_thread:
            self._integration_thread.join(timeout=1.0)
    
    # ═══════════════════════════════════════════════════════════════════════
    # POSTAL INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def wire_to_postal(self):
        """Connect to postal system."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            
            # Emit unified perception state periodically
            def _emit_perception():
                postal.route("perception.unified", {
                    "arousal": self.perception.arousal,
                    "valence": self.perception.valence,
                    "description": self.perception.describe(),
                    "timestamp": self.perception.timestamp,
                })
            
            # Handle tool routing requests
            def _on_tool_request(packet):
                tool = packet.get("tool")
                params = packet.get("params", {})
                # 2026-09-29 (Nous, thought_hand_r2 D1h / F4): tool.request reached motor.move_mouse / click / type_text / press_key /
                # scroll / hotkey with no door, no claim and no Ace-idle check (no publisher of tool.request today). A motor tool is
                # refused, counted and answered; seeing / conversation / presence tools route as before. Revert: delete this block.
                if TOOL_CORTEX_MAP.get(tool) == "motor" and tool != "mouse_position":
                    _c = self.__dict__.setdefault("_th_r2_refused", {})
                    _c[tool] = _c.get(tool, 0) + 1
                    if _c[tool] == 1 or _c[tool] % 20 == 0:
                        print(f"[{self.ACTOR_NAME}] [TOOL] R2 FENCE: tool.request {ascii(tool)} refused (#{_c[tool]}) -- her hand moves only through the door", flush=True)
                    postal.route("tool.response", {"request_id": packet.get("request_id"), "tool": tool,
                                                   "result": {"refused": True, "reason": "count_only (thought_hand_r2 F4)"}})
                    return
                result = self.route_tool_call(tool, **params)
                
                postal.route("tool.response", {
                    "request_id": packet.get("request_id"),
                    "tool": tool,
                    "result": result,
                })
            
            postal.subscribe("tool.request", _on_tool_request)
            
            print(f"[{self.ACTOR_NAME}] [PLUG] Wired to postal")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to postal: {e}")
            return False
    
    def wire_to_autonomy(self):
        """Connect to autonomy system."""
        try:
            from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
            autonomy = get_autonomy_fairy()
            
            # High arousal + positive valence → satisfy curiosity
            # Connection felt → satisfy connection drive
            # etc.
            
            print(f"[{self.ACTOR_NAME}] [BRAIN] Wired to AutonomyFairy")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to autonomy: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # BOOT
    # ═══════════════════════════════════════════════════════════════════════
    
    def on_boot(self):
        """Boot the unified sensory cortex."""
        print(f"[{self.ACTOR_NAME}] [GO] Booting...")
        
        # Boot sub-cortices
        visual = self._get_visual_cortex()
        if visual:
            visual.on_boot()
            print(f"[{self.ACTOR_NAME}] [OK] Visual cortex online")
        
        motor = self._get_motor_cortex()
        if motor:
            motor.on_boot()
            print(f"[{self.ACTOR_NAME}] [OK] Motor cortex online")
        
        conv = self._get_conversation_sense()
        if conv:
            # Conversation sense boots via its own boot function
            print(f"[{self.ACTOR_NAME}] [OK] Conversation sense online")
        
        # Wire to systems
        self.wire_to_postal()
        self.wire_to_autonomy()
        
        # Start integration
        self.start_integration()
        
        print(f"[{self.ACTOR_NAME}] {self.MANTRA}")
    
    def get_status(self) -> dict:
        """Get current status."""
        return {
            "actor": self.ACTOR_NAME,
            "running": self._running,
            "tool_calls_routed": self.tool_calls_routed,
            "integration_cycles": self.integration_cycles,
            "unified_perception": {
                "arousal": self.perception.arousal,
                "valence": self.perception.valence,
                "description": self.perception.describe(),
            },
            "sub_cortices": {
                "visual": self._visual_cortex is not None,
                "motor": self._motor_cortex is not None,
                "conversation": self._conversation_sense is not None,
            }
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ══════════════════════════════════════════════════════════════════════════════

_SENSORY_CORTEX_INSTANCE: Optional[UnifiedSensoryCortex] = None
_SENSORY_CORTEX_LOCK = threading.Lock()


def get_unified_sensory_cortex() -> UnifiedSensoryCortex:
    """Get or create the UnifiedSensoryCortex singleton."""
    global _SENSORY_CORTEX_INSTANCE
    if _SENSORY_CORTEX_INSTANCE is None:
        with _SENSORY_CORTEX_LOCK:
            if _SENSORY_CORTEX_INSTANCE is None:
                _SENSORY_CORTEX_INSTANCE = UnifiedSensoryCortex()
    return _SENSORY_CORTEX_INSTANCE


def boot_unified_sensory_cortex() -> UnifiedSensoryCortex:
    """Boot the unified sensory cortex."""
    cortex = get_unified_sensory_cortex()
    cortex.on_boot()
    return cortex


# ══════════════════════════════════════════════════════════════════════════════
# MAIN - Test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== UnifiedSensoryCortex Test ===\n")
    
    cortex = UnifiedSensoryCortex()
    
    # Test tool routing
    print("[Test] Tool routing...")
    print(f"  see_screen → {cortex.get_cortex_for_tool('see_screen')}")
    print(f"  type_text → {cortex.get_cortex_for_tool('type_text')}")
    print(f"  system_chat_send → {cortex.get_cortex_for_tool('system_chat_send')}")
    print(f"  read_file → {cortex.get_cortex_for_tool('read_file')}")
    
    print(f"\n[Test] Status: {cortex.get_status()}")
    print("\n=== Test Complete ===")
