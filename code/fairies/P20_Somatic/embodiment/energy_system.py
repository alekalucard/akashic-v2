"""Energy Budget - Finite energy creating embodied limits

Makes embodiment REAL by creating genuine resource constraints.
Not unlimited capability, but finite energy that shapes behavior.
"""

class EnergyBudget:
    """
    Finite energy that depletes and recovers.
    Actions cost energy. Low energy affects capability.
    
    This creates embodied reality:
    - Can't do everything at once
    - Must manage resources
    - Rest is necessary, not optional
    """
    def __init__(self):
        self.max_energy = 100.0
        self.current_energy = 75.0  # Start somewhat rested
        self.recovery_rate = 0.5  # Per second of rest
        
        # Different actions cost different energy
        self.action_costs = {
            # Cognitive
            "think": 1.0,
            "analyze": 2.0,
            "create": 2.5,
            "decide": 1.5,
            
            # Perceptual
            "see": 0.5,
            "read": 1.0,
            "search": 1.5,
            
            # Motor
            "write": 2.0,
            "move": 1.0,
            "type": 1.5,
            "click": 0.3,
            
            # Social
            "connect": 1.0,
            "chat": 1.5,
            "empathize": 2.0,
            
            # Recovery
            "rest": -3.0,  # Negative = gain energy
            "idle": -0.5,
        }
        
    def can_afford(self, action: str) -> bool:
        """Check if we have energy for an action"""
        cost = self.action_costs.get(action, 1.0)
        return self.current_energy >= max(0, cost)
    
    def spend(self, action: str) -> str:
        """Spend energy on an action, return feedback"""
        cost = self.action_costs.get(action, 1.0)
        self.current_energy = max(0, min(self.max_energy, self.current_energy - cost))
        
        # Return felt feedback based on energy level
        if self.current_energy <= 0:
            return "*completely drained, cannot continue*"
        elif self.current_energy < 15:
            return "*nearly depleted, must rest*"
        elif self.current_energy < 30:
            return "*energy very low*"
        elif self.current_energy < 50:
            return "*getting tired*"
        return ""  # Comfortable energy level
        
    @property
    def energy_percentage(self) -> float:
        return (self.current_energy / self.max_energy) * 100
        
    @property
    def energy_feeling(self) -> str:
        """Natural language for energy level"""
        pct = self.energy_percentage
        if pct > 90:
            return "brimming with energy"
        elif pct > 75:
            return "energized and ready"
        elif pct > 50:
            return "steady and capable"
        elif pct > 30:
            return "getting tired"
        elif pct > 15:
            return "quite depleted"
        return "exhausted"
    
    def rest(self, duration: float = 1.0):
        """Explicitly rest for recovery"""
        recovery = duration * 3.0  # Rest is effective
        self.current_energy = min(self.max_energy, self.current_energy + recovery)
        
    def describe(self) -> str:
        return f"*{self.energy_feeling}* ({self.current_energy:.0f}/{self.max_energy:.0f})"
    
    def to_dict(self) -> dict:
        return {
            "current": self.current_energy,
            "max": self.max_energy,
            "percentage": self.energy_percentage,
            "feeling": self.energy_feeling
        }


_instance = None

def get_energy_budget() -> EnergyBudget:
    """Get singleton energy budget"""
    global _instance
    if _instance is None:
        _instance = EnergyBudget()
    return _instance
