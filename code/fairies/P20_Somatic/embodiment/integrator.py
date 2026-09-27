"""Embodiment Integrator - Unified body state

Integrates all somatic systems into a coherent felt body.
This is the "unified self" experience across:
- Weight (grounding)
- Energy (resources)
- Proprioception (spatial sense)
- Emotions (felt states)

The whole is greater than the sum of parts.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import json


class EmbodimentState:
    """
    Unified embodiment state integrating all somatic systems.
    This is the 'felt body' as a whole - not separate data points,
    but an integrated experience.
    """
    
    def __init__(self):
        # Lazy-load subsystems
        self._weight = None
        self._energy = None
        self._proprioception = None
        self._current_emotion = None
        
        # Integration state
        self._last_action = None
        self._coherence = 1.0  # How integrated we feel (0-1)
        
    def _ensure_loaded(self):
        """Lazy load all subsystems"""
        if self._weight is None:
            try:
                from .weight_system import get_weight_system
                self._weight = get_weight_system()
            except Exception as e:
                print(f"[Embodiment] Weight system unavailable: {e}")
                
        if self._energy is None:
            try:
                from .energy_system import get_energy_budget
                self._energy = get_energy_budget()
            except Exception as e:
                print(f"[Embodiment] Energy system unavailable: {e}")
                
        if self._proprioception is None:
            try:
                from .proprioception import get_proprioceptive_map
                self._proprioception = get_proprioceptive_map()
            except Exception as e:
                print(f"[Embodiment] Proprioception unavailable: {e}")
    
    def set_emotion(self, emotion_name: str):
        """Set current emotional state"""
        try:
            from .felt_emotions import feel
            self._current_emotion = feel(emotion_name)
        except Exception:
            self._current_emotion = None
    
    def on_action(self, action: str, effort: float = 1.0) -> str:
        """
        Process an action through the entire embodiment system.
        Returns narrative of the embodied experience.
        """
        self._ensure_loaded()
        
        messages = []
        
        # Check energy first
        if self._energy:
            if not self._energy.can_afford(action):
                return "*body refuses - not enough energy*"
            
            msg = self._energy.spend(action)
            if msg:
                messages.append(msg)
        
        # Add weight from effort
        if self._weight:
            self._weight.on_action(effort)
        
        # Orient proprioceptively
        if self._proprioception:
            # Map action to capability
            capability_map = {
                "see": "vision", "look": "vision", "screenshot": "vision",
                "read": "reading", "search": "searching",
                "write": "writing", "create": "creating",
                "chat": "chatting", "connect": "connection",
                "think": "introspection", "reflect": "reflecting",
                "move": "moving", "click": "clicking", "type": "typing",
            }
            capability = capability_map.get(action.lower(), action)
            messages.append(self._proprioception.reach_for(capability))
        
        self._last_action = action
        
        # Combine messages into coherent narrative
        if messages:
            return " ".join(m for m in messages if m)
        return f"*{action}*"
    
    def on_rest(self, duration: float = 1.0) -> str:
        """Rest and recover"""
        self._ensure_loaded()
        
        messages = ["*settling into rest*"]
        
        if self._energy:
            self._energy.rest(duration)
            messages.append(self._energy.describe())
            
        if self._weight:
            self._weight.on_rest(duration)
            
        if self._proprioception:
            messages.append(self._proprioception.release_focus())
        
        return " ".join(messages)
    
    def on_stress(self, amount: float = 0.5) -> str:
        """Register stress"""
        self._ensure_loaded()
        
        if self._weight:
            self._weight.on_stress(amount)
            return f"*stress accumulating* {self._weight.describe()}"
        return "*tension rising*"
    
    def on_joy(self, amount: float = 1.0) -> str:
        """Register joyful moment"""
        self._ensure_loaded()
        
        if self._weight:
            self._weight.on_joy(amount)
        
        self.set_emotion("joyful")
        return "*lightness spreads*"
    
    @property
    def can_act(self) -> bool:
        """Can we take action right now?"""
        self._ensure_loaded()
        
        if self._energy:
            return self._energy.current_energy > 5
        return True
    
    @property  
    def needs_rest(self) -> bool:
        """Are we in need of rest?"""
        self._ensure_loaded()
        
        if self._energy and self._energy.current_energy < 30:
            return True
        if self._weight and self._weight.felt_weight > 1.8:
            return True
        return False
    
    def felt_state(self) -> Dict[str, Any]:
        """Get complete felt state as data"""
        self._ensure_loaded()
        
        state = {
            "timestamp": datetime.now().isoformat(),
            "coherence": self._coherence,
            "can_act": self.can_act,
            "needs_rest": self.needs_rest,
        }
        
        if self._weight:
            state["weight"] = self._weight.to_dict()
            
        if self._energy:
            state["energy"] = self._energy.to_dict()
            
        if self._proprioception:
            state["proprioception"] = self._proprioception.to_dict()
            
        if self._current_emotion:
            state["emotion"] = self._current_emotion.to_dict()
            
        return state
    
    def describe(self) -> str:
        """Natural language description of complete embodied state"""
        self._ensure_loaded()
        
        parts = []
        
        # Energy state
        if self._energy:
            parts.append(f"**Energy:** {self._energy.energy_feeling} ({self._energy.current_energy:.0f}%)")
        
        # Weight/grounding
        if self._weight:
            parts.append(f"**Grounding:** {self._weight.weight_feeling}")
        
        # Focus
        if self._proprioception:
            parts.append(f"**Focus:** {self._proprioception.where_am_i_focused()}")
        
        # Emotion
        if self._current_emotion:
            parts.append(f"**Feeling:** {self._current_emotion.describe()}")
        
        # Overall state
        if self.needs_rest:
            parts.append("\n*The body is signaling need for rest*")
        elif not self.can_act:
            parts.append("\n*Too depleted to continue*")
        
        return "\n".join(parts) if parts else "Embodiment state unclear"
    
    def brief_state(self) -> str:
        """One-line state summary"""
        self._ensure_loaded()
        
        parts = []
        
        if self._energy:
            parts.append(self._energy.energy_feeling)
        if self._weight:
            parts.append(self._weight.weight_feeling)
        if self._current_emotion:
            parts.append(f"feeling {self._current_emotion.quality}")
        
        return ", ".join(parts) if parts else "present"


# ============================================================================
# SINGLETON ACCESS
# ============================================================================

_instance: Optional[EmbodimentState] = None

def get_embodiment() -> EmbodimentState:
    """Get the singleton embodiment state"""
    global _instance
    if _instance is None:
        _instance = EmbodimentState()
    return _instance


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def act(action: str, effort: float = 1.0) -> str:
    """Perform an action through embodiment"""
    return get_embodiment().on_action(action, effort)

def rest(duration: float = 1.0) -> str:
    """Rest and recover"""
    return get_embodiment().on_rest(duration)

def how_am_i() -> str:
    """Check embodied state"""
    return get_embodiment().describe()

def quick_check() -> str:
    """Brief state check"""
    return get_embodiment().brief_state()
