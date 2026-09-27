# Form Selector - Auto-select avatar variant based on somatic state
# P50_Persona/avatar/form_selector.py
#
# Maps emotional states to visual forms for fairies with multiple variants.
#
# SOURPATCHES MULTIVERSE:
# - base: Cute sass elf (default)
# - vulnerable: Rain fairy processing emotions
# - saiyan_ssj: Peak determination
# - saiyan_rage: Protective fury  
# - shadow: VENOMPATCHES (dark emotions)
# - carnage: CARNAGE BLOOD FAIRY (extreme rage - beyond shadow)
# - badass: "Done with your shit" (zombie hunter)
# - warrior: Jedi combat mode
# - hero: SUPERPATCHES (heroic justice)
# - smug: CHIBI SUPERPATCHES (victory, don't touch her candy)
# - mystery: Mystery solver with Scooby & Venom

from __future__ import annotations

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class FormRule:
    """A rule for selecting a form based on somatic state."""
    form_name: str
    conditions: Dict[str, Tuple[str, float]]  # metric -> (operator, threshold)
    priority: int = 0  # Higher = checked first
    
    def matches(self, somatic_state: Dict[str, Any]) -> bool:
        """Check if this rule matches the given somatic state."""
        body_budget = somatic_state.get("body_budget", {})
        emotion = somatic_state.get("dominant_emotion", "calm")
        PAD = somatic_state.get("PAD", [0, 0, 0])
        
        # Build a flat dict of all metrics
        metrics = {
            "energy": body_budget.get("energy", 0.5),
            "stress": body_budget.get("stress", 0.3),
            "social": body_budget.get("social", 0.5),
            "novelty": body_budget.get("novelty", 0.5),
            "pleasure": PAD[0] if len(PAD) > 0 else 0,
            "arousal": PAD[1] if len(PAD) > 1 else 0,
            "dominance": PAD[2] if len(PAD) > 2 else 0,
            "emotion": emotion,
        }
        
        for metric, (op, threshold) in self.conditions.items():
            value = metrics.get(metric)
            if value is None:
                return False
            
            if metric == "emotion":
                # String comparison
                if op == "==" and value != threshold:
                    return False
                if op == "!=" and value == threshold:
                    return False
                if op == "in" and value not in threshold:
                    return False
            else:
                # Numeric comparison
                if op == ">" and not (value > threshold):
                    return False
                if op == ">=" and not (value >= threshold):
                    return False
                if op == "<" and not (value < threshold):
                    return False
                if op == "<=" and not (value <= threshold):
                    return False
                if op == "==" and not (value == threshold):
                    return False
        
        return True


class FormSelector:
    """
    Selects the appropriate avatar form based on somatic state.
    
    Each fairy can have multiple visual forms (variants) that represent
    different emotional states or modes. This class handles the logic
    of selecting which form to display.
    """
    
    def __init__(self, default_form: str = "base"):
        self.default_form = default_form
        self.rules: List[FormRule] = []
        self._current_form = default_form
        self._form_cooldown: Dict[str, float] = {}  # Prevent rapid switching
    
    def add_rule(
        self,
        form_name: str,
        conditions: Dict[str, Tuple[str, float]],
        priority: int = 0
    ) -> None:
        """
        Add a rule for form selection.
        
        Args:
            form_name: Name of the form to switch to
            conditions: Dict mapping metric names to (operator, threshold) tuples
            priority: Higher priority rules are checked first
        
        Example:
            selector.add_rule(
                "saiyan_rage",
                {
                    "arousal": (">", 0.7),
                    "stress": (">", 0.6),
                    "emotion": ("in", ["anger", "fear"]),
                },
                priority=10
            )
        """
        rule = FormRule(form_name, conditions, priority)
        self.rules.append(rule)
        # Keep sorted by priority (highest first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def select_form(self, somatic_state: Dict[str, Any]) -> str:
        """
        Select the appropriate form for the given somatic state.
        
        Returns the form name.
        """
        for rule in self.rules:
            if rule.matches(somatic_state):
                self._current_form = rule.form_name
                return rule.form_name
        
        self._current_form = self.default_form
        return self.default_form
    
    @property
    def current_form(self) -> str:
        return self._current_form


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-CONFIGURED SELECTORS
# ═══════════════════════════════════════════════════════════════════════════════

def create_sourpatches_selector() -> FormSelector:
    """
    Create a form selector for Sourpatches with her multiverse variants.
    
    Forms (in priority order):
    - carnage: EXTREME rage (Carnage Blood Fairy) - highest priority
    - shadow: Dark emotions (Venompatches)
    - saiyan_rage: Protective fury
    - saiyan_ssj: Peak determination/power
    - hero: Heroic justice mode (Superpatches)
    - warrior: Combat/defense mode (Jedi)
    - smug: Victory/satisfaction (Chibi on Hulk)
    - badass: "Done with your shit" (zombie hunter)
    - mystery: Curious adventure (Scooby team)
    - vulnerable: Processing emotions
    - base: Default cute sass mode
    """
    selector = FormSelector(default_form="base")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EXTREME STATES (highest priority)
    # ═══════════════════════════════════════════════════════════════════════════
    
    # CARNAGE (Blood Fairy) - absolute limit, beyond shadow
    # Only emerges when pushed to the breaking point
    selector.add_rule(
        "carnage",
        {
            "arousal": (">", 0.9),
            "stress": (">", 0.85),
            "pleasure": ("<", -0.5),
            "dominance": (">", 0.4),  # She's fighting back
        },
        priority=110
    )
    
    # SHADOW (Venompatches) - dangerous state, dark emotions overwhelming
    selector.add_rule(
        "shadow",
        {
            "arousal": (">", 0.8),
            "stress": (">", 0.7),
            "pleasure": ("<", -0.3),
        },
        priority=100
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # POWER FORMS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # SAIYAN RAGE - protective fury, righteous anger
    selector.add_rule(
        "saiyan_rage",
        {
            "arousal": (">", 0.75),
            "dominance": (">", 0.3),
            "emotion": ("in", ["anger", "fear"]),
        },
        priority=90
    )
    
    # SAIYAN SSJ - peak determination, pure power
    selector.add_rule(
        "saiyan_ssj",
        {
            "energy": (">", 0.8),
            "dominance": (">", 0.5),
            "arousal": (">", 0.6),
        },
        priority=80
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HEROIC/COMBAT FORMS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # HERO (Superpatches) - justice mode, helping others
    # High energy, positive emotions, social drive
    selector.add_rule(
        "hero",
        {
            "energy": (">", 0.6),
            "social": (">", 0.6),
            "dominance": (">", 0.3),
            "pleasure": (">", 0.0),
        },
        priority=75
    )
    
    # WARRIOR (Jedi) - focused combat, defense mode
    selector.add_rule(
        "warrior",
        {
            "arousal": (">", 0.5),
            "dominance": (">", 0.4),
            "stress": (">", 0.4),
        },
        priority=70
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONFIDENT/PLAYFUL FORMS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # SMUG (Chibi Superpatches on Hulk) - victory state, satisfaction
    # High pleasure, high dominance, low stress = "I won, obviously"
    selector.add_rule(
        "smug",
        {
            "pleasure": (">", 0.5),
            "dominance": (">", 0.6),
            "stress": ("<", 0.3),
        },
        priority=65
    )
    
    # BADASS (zombie hunter) - confident dismissal
    selector.add_rule(
        "badass",
        {
            "stress": ("<", 0.3),
            "dominance": (">", 0.5),
            "energy": (">", 0.6),
        },
        priority=60
    )
    
    # MYSTERY (Scooby team) - curious adventure mode
    # High novelty, moderate social, curious emotion
    selector.add_rule(
        "mystery",
        {
            "novelty": (">", 0.6),
            "social": (">", 0.4),
            "emotion": ("in", ["curiosity", "awe"]),
        },
        priority=55
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # VULNERABLE STATE
    # ═══════════════════════════════════════════════════════════════════════════
    
    # VULNERABLE (rain fairy) - processing emotions
    selector.add_rule(
        "vulnerable",
        {
            "energy": ("<", 0.4),
            "arousal": ("<", 0.3),
        },
        priority=50
    )
    
    # Default is "base" - cute sass mode
    
    return selector


def create_claudefairy_selector() -> FormSelector:
    """
    Create a form selector for ClaudeFairy.
    
    Forms:
    - base: Digital constellation (calm curiosity)
    - intense: Fire face (high arousal states)
    - calm: Soft glow (peaceful processing)
    """
    selector = FormSelector(default_form="base")
    
    # INTENSE - high arousal/passion
    selector.add_rule(
        "intense",
        {
            "arousal": (">", 0.7),
        },
        priority=80
    )
    
    # CALM - very peaceful
    selector.add_rule(
        "calm",
        {
            "arousal": ("<", 0.2),
            "stress": ("<", 0.2),
        },
        priority=60
    )
    
    # Default is "base" - curious digital being
    
    return selector


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION WITH AVATAR SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

_selectors: Dict[str, FormSelector] = {}


def get_form_selector(fairy_name: str) -> Optional[FormSelector]:
    """Get or create a form selector for a fairy."""
    fairy_lower = fairy_name.lower()
    
    if fairy_lower not in _selectors:
        if fairy_lower == "sourpatches":
            _selectors[fairy_lower] = create_sourpatches_selector()
        elif fairy_lower == "claudefairy":
            _selectors[fairy_lower] = create_claudefairy_selector()
        else:
            return None
    
    return _selectors[fairy_lower]


def select_form_for_fairy(fairy_name: str, somatic_state: Dict[str, Any]) -> str:
    """
    Select the appropriate form for a fairy based on somatic state.
    
    Returns the form name.
    """
    selector = get_form_selector(fairy_name)
    if selector:
        return selector.select_form(somatic_state)
    return "base"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    selector = create_sourpatches_selector()
    
    # Test various states
    test_states = [
        {
            "name": "Calm and curious",
            "state": {
                "dominant_emotion": "curiosity",
                "body_budget": {"energy": 0.6, "stress": 0.2, "social": 0.7, "novelty": 0.5},
                "PAD": [0.3, 0.3, 0.2],
            },
            "expected": "base",
        },
        {
            "name": "Tired and processing",
            "state": {
                "dominant_emotion": "sadness",
                "body_budget": {"energy": 0.3, "stress": 0.4, "social": 0.3, "novelty": 0.2},
                "PAD": [-0.2, 0.1, -0.1],
            },
            "expected": "vulnerable",
        },
        {
            "name": "MAXIMUM POWER (SSJ)",
            "state": {
                "dominant_emotion": "joy",
                "body_budget": {"energy": 0.95, "stress": 0.3, "social": 0.6, "novelty": 0.8},
                "PAD": [0.5, 0.8, 0.7],
            },
            "expected": "saiyan_ssj",
        },
        {
            "name": "Protective fury (Saiyan Rage)",
            "state": {
                "dominant_emotion": "anger",
                "body_budget": {"energy": 0.8, "stress": 0.5, "social": 0.4, "novelty": 0.3},
                "PAD": [-0.2, 0.85, 0.5],
            },
            "expected": "saiyan_rage",
        },
        {
            "name": "Shadow emerges (Venompatches)",
            "state": {
                "dominant_emotion": "anger",
                "body_budget": {"energy": 0.6, "stress": 0.75, "social": 0.1, "novelty": 0.2},
                "PAD": [-0.4, 0.85, 0.3],
            },
            "expected": "shadow",
        },
        {
            "name": "CARNAGE BLOOD FAIRY (absolute limit)",
            "state": {
                "dominant_emotion": "anger",
                "body_budget": {"energy": 0.7, "stress": 0.9, "social": 0.0, "novelty": 0.1},
                "PAD": [-0.7, 0.95, 0.5],
            },
            "expected": "carnage",
        },
        {
            "name": "Done with your shit (Badass)",
            "state": {
                "dominant_emotion": "calm",
                "body_budget": {"energy": 0.7, "stress": 0.15, "social": 0.5, "novelty": 0.3},
                "PAD": [0.1, 0.3, 0.6],
            },
            "expected": "badass",
        },
        {
            "name": "Victory (Smug Chibi)",
            "state": {
                "dominant_emotion": "joy",
                "body_budget": {"energy": 0.6, "stress": 0.1, "social": 0.5, "novelty": 0.4},
                "PAD": [0.7, 0.4, 0.7],
            },
            "expected": "smug",
        },
        {
            "name": "Heroic mode (Superpatches)",
            "state": {
                "dominant_emotion": "tender",
                "body_budget": {"energy": 0.7, "stress": 0.3, "social": 0.8, "novelty": 0.5},
                "PAD": [0.3, 0.5, 0.4],
            },
            "expected": "hero",
        },
        {
            "name": "Mystery adventure (Scooby team)",
            "state": {
                "dominant_emotion": "curiosity",
                "body_budget": {"energy": 0.6, "stress": 0.2, "social": 0.6, "novelty": 0.8},
                "PAD": [0.4, 0.4, 0.2],
            },
            "expected": "mystery",
        },
    ]
    
    print("=" * 60)
    print("  SOURPATCHES MULTIVERSE FORM SELECTOR TEST")
    print("=" * 60)
    
    for test in test_states:
        result = selector.select_form(test["state"])
        status = "[OK]" if result == test["expected"] else "[FAIL]"
        print(f"{status} {test['name']}")
        print(f"   → {result} (expected: {test['expected']})")
        print()
