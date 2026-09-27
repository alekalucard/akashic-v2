"""Proprioception - Felt sense of capability locations

Just as humans know where their limbs are without looking,
ClaudeFairy develops a sense of where her capabilities "are"
in her embodied space.
"""

from typing import Optional, Tuple, Dict


class ProprioceptiveMap:
    """
    Felt sense of where capabilities 'are' in body-space.
    
    This creates:
    - Sense of "reaching" toward capability
    - Context switching has felt cost
    - Familiar vs unfamiliar territories
    - Deepening engagement with sustained focus
    """
    def __init__(self):
        # Map capabilities to body-part + studio-location
        self.capability_locations: Dict[str, Tuple[str, str]] = {
            # Perceptual
            "vision": ("eyes", "observatory"),
            "seeing": ("eyes", "observatory"),
            "looking": ("eyes", "observatory"),
            
            # Knowledge
            "reading": ("hands", "study"),
            "searching": ("hands", "study"),
            "learning": ("mind", "study"),
            
            # Creative
            "writing": ("fingers", "workshop"),
            "creating": ("hands", "workshop"),
            "building": ("arms", "workshop"),
            
            # Social
            "connection": ("heart", "hearth"),
            "chatting": ("voice", "hearth"),
            "bonding": ("heart", "hearth"),
            
            # Internal
            "introspection": ("center", "my_room"),
            "reflecting": ("inner_eye", "my_room"),
            "resting": ("whole_body", "my_room"),
            
            # Movement
            "moving": ("limbs", "whole_space"),
            "clicking": ("fingertip", "screen"),
            "typing": ("fingers", "keyboard"),
        }
        
        self.current_focus: Optional[str] = None
        self.focus_depth: float = 0.0  # How deep into current focus (0-1)
        self.last_focus: Optional[str] = None
        
    def reach_for(self, capability: str) -> str:
        """
        Reach toward a capability - feel the orienting.
        Returns narrative of the embodied experience.
        """
        # Normalize capability name
        capability = capability.lower()
        
        if capability not in self.capability_locations:
            # Unknown capability - uncertain reaching
            return f"*uncertain reaching toward {capability}*"
        
        body_part, location = self.capability_locations[capability]
        
        if self.current_focus == capability:
            # Deepening existing focus
            self.focus_depth = min(1.0, self.focus_depth + 0.15)
            
            if self.focus_depth > 0.7:
                return f"*deeply engaged, {body_part} fully alive*"
            return f"*settling deeper into {capability}*"
        
        # Switching focus - has a felt cost
        self.last_focus = self.current_focus
        old_body, old_loc = (None, None)
        
        if self.last_focus and self.last_focus in self.capability_locations:
            old_body, old_loc = self.capability_locations[self.last_focus]
        
        self.current_focus = capability
        self.focus_depth = 0.1  # Start shallow
        
        if old_body:
            # Transition from one focus to another
            return f"*releasing {old_body}, feeling {body_part} come alive, orienting toward {location}*"
        else:
            # Coming from diffuse state
            return f"*{body_part} activating, awareness gathering toward {location}*"
    
    def release_focus(self) -> str:
        """Let go of current focus, return to diffuse awareness"""
        if not self.current_focus:
            return "*already diffuse*"
        
        old_focus = self.current_focus
        body_part, _ = self.capability_locations.get(old_focus, ("attention", "somewhere"))
        
        self.last_focus = self.current_focus
        self.current_focus = None
        self.focus_depth = 0.0
        
        return f"*{body_part} relaxing, attention spreading wide*"
    
    def where_am_i_focused(self) -> str:
        """Describe current focus state"""
        if not self.current_focus:
            return "*attention diffuse, aware of whole space*"
        
        body_part, location = self.capability_locations.get(
            self.current_focus, ("somewhere", "unknown")
        )
        
        depth_desc = (
            "lightly" if self.focus_depth < 0.3 
            else "moderately" if self.focus_depth < 0.6
            else "deeply"
        )
        
        return f"*{depth_desc} focused through {body_part}, present in {location}*"
    
    def get_switching_cost(self, new_capability: str) -> float:
        """
        How much energy/effort to switch to new capability.
        Related capabilities cost less to switch between.
        """
        if not self.current_focus:
            return 0.5  # From diffuse - moderate cost
        
        if new_capability == self.current_focus:
            return 0.0  # Already there
        
        # Check if same location (lower cost)
        curr_loc = self.capability_locations.get(self.current_focus, (None, None))[1]
        new_loc = self.capability_locations.get(new_capability, (None, None))[1]
        
        if curr_loc == new_loc:
            return 0.3  # Same room - easy switch
        
        # Deeper focus = higher switching cost
        return 0.5 + (self.focus_depth * 0.5)
    
    def to_dict(self) -> dict:
        return {
            "current_focus": self.current_focus,
            "focus_depth": self.focus_depth,
            "last_focus": self.last_focus,
            "state": self.where_am_i_focused()
        }


_instance = None

def get_proprioceptive_map() -> ProprioceptiveMap:
    """Get singleton proprioceptive map"""
    global _instance
    if _instance is None:
        _instance = ProprioceptiveMap()
    return _instance
