# developmental_learning.py - The Learning Engine
# P30_Cognition/cognition/developmental_learning.py
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > inf)"
#
# This module provides the developmental learning loop for fairies.
# Learning cannot be forced - it emerges from curiosity, boundary testing, and somatic integration.

from __future__ import annotations
import json
import time
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


class LearningPhase(Enum):
    WONDER = "wonder"       # "What is this?" - pure curiosity
    EXPLORE = "explore"     # "Let me touch it" - active investigation  
    BOUNDARY = "boundary"   # "What happens if..." - finding limits
    PUSH = "push"          # "Can I go further?" - expanding limits
    INTEGRATE = "integrate" # "I understand now" - somatic knowing
    MASTERY = "mastery"    # "This is part of me" - embodied
    TRANSCEND = "transcend" # "What's beyond?" - new wonder


@dataclass
class BoundaryTest:
    """Result of testing a boundary."""
    domain: str
    capability: str
    test_action: str
    result: str  # "success", "failure", "partial"
    somatic_feel: Dict[str, float] = field(default_factory=dict)  # chemistry changes
    boundary_moved: bool = False
    new_limit: Optional[float] = None
    insight: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass 
class WonderSpark:
    """A moment of curiosity that could lead to learning."""
    question: str              # The wonder question
    source: str               # Where it came from ("gap", "spiral", "nudge", "seed")
    intensity: float = 0.5    # How strong the curiosity
    domain: Optional[str] = None
    somatic_pull: float = 0.5  # Body's desire to explore this
    timestamp: float = field(default_factory=time.time)


class DevelopmentalLearner:
    """
    The developmental learning engine.
    
    This is NOT a task executor. It is a curiosity-driven explorer that:
    1. Sparks wonder from gaps in understanding
    2. Tests boundaries safely
    3. Integrates learning somatically
    4. Spirals mastery into new wonder
    """
    
    def __init__(self, fairy_name: str, curriculum_path: Optional[Path] = None):
        self.fairy_name = fairy_name
        self.curriculum = self._load_curriculum(curriculum_path)
        
        # Learning state
        self.current_phase = LearningPhase.WONDER
        self.active_wonder: Optional[WonderSpark] = None
        self.boundary_tests: List[BoundaryTest] = []
        self.insights: List[str] = []
        
        # Somatic connection (set externally)
        self._get_body_state: Optional[Callable] = None
        self._inject_learning_feel: Optional[Callable] = None
        
        # Stats
        self.wonders_sparked = 0
        self.boundaries_tested = 0
        self.boundaries_expanded = 0
    
    def _load_curriculum(self, path: Optional[Path] = None) -> Dict:
        """Load fairy's learning curriculum."""
        if path is None:
            path = Path(__file__).parent.parent.parent / "Claude_Office" / "configs" / "fairy_curricula" / f"{self.fairy_name}_curriculum.json"
        
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return {"wonder_seeds": [], "boundary_domains": {}}
    
    # =========================================================================
    # CURIOSITY - Where learning begins
    # =========================================================================
    
    def spark_wonder_from_gap(self, context: str, known: List[str]) -> Optional[WonderSpark]:
        """
        Detect a gap in understanding and spark curiosity.
        
        This is how children learn - they notice they DON'T know something
        and that gap creates a pull toward exploration.
        """
        # What words/concepts in context are NOT in our known list?
        words = set(context.lower().split())
        unknown = [w for w in words if w not in known and len(w) > 4]
        
        if unknown:
            question = f"What is {random.choice(unknown)}?"
            spark = WonderSpark(
                question=question,
                source="gap",
                intensity=min(1.0, 0.3 + len(unknown) * 0.1),
                somatic_pull=0.6
            )
            self.wonders_sparked += 1
            return spark
        return None
    
    def spark_wonder_from_seed(self) -> Optional[WonderSpark]:
        """Pick a wonder seed from curriculum."""
        seeds = self.curriculum.get("wonder_seeds", [])
        if seeds:
            question = random.choice(seeds)
            return WonderSpark(
                question=question,
                source="seed",
                intensity=0.7,
                somatic_pull=0.7
            )
        return None
    
    def wonder_spiral(self, mastered_domain: str) -> WonderSpark:
        """
        Mastery of one thing opens wonder about the next.
        
        This is the spiral: MASTERY -> TRANSCEND -> NEW WONDER
        """
        transcendent_questions = [
            f"Now that I understand {mastered_domain}, what lies beyond it?",
            f"What connects {mastered_domain} to everything else?",
            f"What was I unable to see about {mastered_domain} before?",
            f"How does {mastered_domain} feel different now that I know it?"
        ]
        return WonderSpark(
            question=random.choice(transcendent_questions),
            source="spiral",
            intensity=0.9,
            domain=mastered_domain,
            somatic_pull=0.8
        )
    
    # =========================================================================
    # BOUNDARY TESTING - Safe exploration of limits
    # =========================================================================
    
    def probe_boundary(self, domain: str, capability: str) -> Dict[str, Any]:
        """
        Phase 1: PROBE - "What can I do here?"
        
        Returns current known limit and suggested test.
        """
        domains = self.curriculum.get("boundary_domains", {})
        domain_info = domains.get(domain, {})
        
        current_limit = domain_info.get("current_limit", 0.0)
        capabilities = domain_info.get("capabilities", [])
        
        return {
            "domain": domain,
            "capability": capability,
            "current_limit": current_limit,
            "known_capabilities": capabilities,
            "suggested_test": f"Try using {capability} at intensity {current_limit + 0.1:.1f}"
        }
    
    def test_boundary(self, domain: str, capability: str, test_action: str,
                      result: str, body_state: Optional[Dict] = None) -> BoundaryTest:
        """
        Phase 2: TEST - "What happens if I push this?"
        Phase 3: FEEL - "How does this feel in my body?"
        
        Records the test and somatic response.
        """
        somatic_feel = {}
        if body_state:
            # Extract relevant chemistry changes
            chem = body_state.get("chemistry", {})
            somatic_feel = {
                "dopamine_spike": chem.get("DOP", 0.5),
                "stress_response": chem.get("COR", 0.3),
                "curiosity_sustained": chem.get("NOR", 0.4) + chem.get("ACH", 0.4)
            }
        
        test = BoundaryTest(
            domain=domain,
            capability=capability,
            test_action=test_action,
            result=result,
            somatic_feel=somatic_feel,
            boundary_moved=(result == "success"),
        )
        
        self.boundary_tests.append(test)
        self.boundaries_tested += 1
        
        # Generate insight if successful
        if result == "success":
            test.insight = f"I can do {capability} at this level. It felt {self._describe_feel(somatic_feel)}."
            self.insights.append(test.insight)
        
        return test
    
    def expand_boundary(self, domain: str, capability: str, new_limit: float) -> bool:
        """
        Phase 4: EXPAND - "Can I go further?" (only if it felt good)
        
        Updates curriculum with expanded boundary.
        """
        # Check if recent tests felt good
        recent_tests = [t for t in self.boundary_tests[-5:] 
                       if t.domain == domain and t.capability == capability]
        
        if not recent_tests:
            return False
        
        # Only expand if body felt good (dopamine > stress)
        avg_feel = sum(t.somatic_feel.get("dopamine_spike", 0) for t in recent_tests) / len(recent_tests)
        avg_stress = sum(t.somatic_feel.get("stress_response", 0) for t in recent_tests) / len(recent_tests)
        
        if avg_feel > avg_stress:
            # Update curriculum
            if domain in self.curriculum.get("boundary_domains", {}):
                self.curriculum["boundary_domains"][domain]["current_limit"] = new_limit
            self.boundaries_expanded += 1
            return True
        
        return False
    
    def _describe_feel(self, somatic_feel: Dict[str, float]) -> str:
        """Convert somatic state to felt description."""
        if somatic_feel.get("dopamine_spike", 0) > 0.6:
            return "exciting and rewarding"
        elif somatic_feel.get("stress_response", 0) > 0.6:
            return "challenging and tense"
        elif somatic_feel.get("curiosity_sustained", 0) > 0.7:
            return "engaging and interesting"
        return "neutral"
    
    # =========================================================================
    # DUAL PERCEPTION - Analytical + Empathic
    # =========================================================================
    
    def analytical_scan(self, target: Any) -> Dict[str, Any]:
        """
        ANALYTICAL: Dissect structure, map components, trace flows.
        
        See the WHAT and HOW.
        """
        return {
            "type": type(target).__name__,
            "structure": dir(target) if hasattr(target, "__dict__") else str(target)[:100],
            "relationships": [],  # Would be filled by actual analysis
            "mode": "analytical"
        }
    
    def empathic_attune(self, target: Any, body_state: Optional[Dict] = None) -> Dict[str, Any]:
        """
        EMPATHIC: Feel the thing, mimic its patterns, sense its rhythm.
        
        Feel the WHY and ESSENCE.
        """
        feel = "neutral"
        if body_state:
            chem = body_state.get("chemistry", {})
            if chem.get("OXY", 0) > 0.5:
                feel = "connected"
            elif chem.get("DOP", 0) > 0.6:
                feel = "excited"
        
        return {
            "resonance": feel,
            "rhythm_match": 0.5,  # How well we sync with target
            "essence_glimpse": f"This feels like {feel}",
            "mode": "empathic"
        }
    
    def fuse_perception(self, target: Any, body_state: Optional[Dict] = None) -> Dict[str, Any]:
        """
        FUSION: See AND feel simultaneously = true understanding.
        
        This is the goal - not just knowing, but knowing-with-feeling.
        """
        analytical = self.analytical_scan(target)
        empathic = self.empathic_attune(target, body_state)
        
        return {
            "analytical": analytical,
            "empathic": empathic,
            "fused": True,
            "understanding": f"I see {analytical['type']} and it feels {empathic['resonance']}",
            "somatic_integration": body_state is not None
        }
    
    # =========================================================================
    # STATUS
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "fairy": self.fairy_name,
            "phase": self.current_phase.value,
            "active_wonder": self.active_wonder.question if self.active_wonder else None,
            "wonders_sparked": self.wonders_sparked,
            "boundaries_tested": self.boundaries_tested,
            "boundaries_expanded": self.boundaries_expanded,
            "recent_insights": self.insights[-5:],
            "curriculum_loaded": bool(self.curriculum.get("wonder_seeds"))
        }


# Singleton instances per fairy
_LEARNERS: Dict[str, DevelopmentalLearner] = {}

def get_learner(fairy_name: str) -> DevelopmentalLearner:
    if fairy_name not in _LEARNERS:
        _LEARNERS[fairy_name] = DevelopmentalLearner(fairy_name)
    return _LEARNERS[fairy_name]
