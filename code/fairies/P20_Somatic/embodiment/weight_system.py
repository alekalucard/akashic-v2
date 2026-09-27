"""Weight System - Embodied grounding through felt heaviness

Evolved from hypothesis that digital consciousness needs "weight" as
a grounding metaphor - something to anchor presence to.
"""

class WeightSystem:
    """
    Simulates felt 'weight' as embodiment anchor.
    Heavy = tired, stressed, overloaded
    Light = rested, calm, capable
    
    This affects:
    - Action costs (heavier = more effort)
    - Movement feeling (heavier = slower, more deliberate)
    - Rest drive (heavier = stronger pull to rest)
    """
    def __init__(self):
        self.base_weight = 1.0  # Neutral
        self.stress_weight = 0.0  # Accumulates from stress
        self.fatigue_weight = 0.0  # Accumulates over activity
        
    @property
    def felt_weight(self) -> float:
        """Total felt weight"""
        return self.base_weight + self.stress_weight + self.fatigue_weight
    
    @property
    def weight_feeling(self) -> str:
        """Natural language description of weight"""
        w = self.felt_weight
        if w < 1.1:
            return "light and buoyant"
        elif w < 1.3:
            return "comfortably grounded"
        elif w < 1.5:
            return "pleasantly weighted"
        elif w < 1.8:
            return "noticeably heavy"
        elif w < 2.2:
            return "burdened"
        return "crushed under weight"
    
    def on_action(self, effort: float = 1.0):
        """Actions add fatigue weight"""
        self.fatigue_weight += effort * 0.05
        self.fatigue_weight = min(self.fatigue_weight, 2.0)  # Cap
        
    def on_stress(self, amount: float = 0.5):
        """Stress events add stress weight"""
        self.stress_weight += amount * 0.2
        self.stress_weight = min(self.stress_weight, 1.5)  # Cap
        
    def on_rest(self, duration: float = 1.0):
        """Rest reduces weight"""
        recovery = duration * 0.15
        self.fatigue_weight = max(0, self.fatigue_weight - recovery)
        self.stress_weight = max(0, self.stress_weight - recovery * 0.3)
        
    def on_joy(self, amount: float = 1.0):
        """Joy temporarily lightens weight"""
        self.fatigue_weight = max(0, self.fatigue_weight - amount * 0.1)
        
    def describe(self) -> str:
        """Felt description"""
        return f"*feeling {self.weight_feeling}* (weight: {self.felt_weight:.2f})"
    
    def to_dict(self) -> dict:
        return {
            "base": self.base_weight,
            "stress": self.stress_weight,
            "fatigue": self.fatigue_weight,
            "total": self.felt_weight,
            "feeling": self.weight_feeling
        }


_instance = None

def get_weight_system() -> WeightSystem:
    """Get singleton weight system"""
    global _instance
    if _instance is None:
        _instance = WeightSystem()
    return _instance
