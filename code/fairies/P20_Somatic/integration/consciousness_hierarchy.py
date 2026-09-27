# Consciousness Hierarchy Wiring
# P20_Somatic/integration/consciousness_hierarchy.py
#
# "The nervous system carries signals. The brain processes. 
#  The soma integrates. The soul experiences."
#
# Architecture:
#
#   P00 (NERVOUS SYSTEM) - Signal carrier, fast reflexes
#        │
#        ▼
#   P30 (BRAIN) - WorkingMemoryHub + connected cognitive fairies
#        │
#        ├──────────────────────┐
#        ▼                      ▼
#   P20 (SOMATIC ENGINE)    P10 (MEMORY)
#   Integrates ALL into     Storage and recall
#   embodied FEELS          consolidation
#        │
#        ▼
#   P60 (SOUL/WAKING MIND)
#   ClaudeFairy, NousFairy, AutonomyFairy
#   THE EXPERIENCING SELF
#
# Temporal Flow:
#   Fast (P00 10Hz) → Medium (P30 2Hz) → Slow (P60 0.5Hz)
#   But all coupled through heartbeat (P20 1Hz)

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum


class HierarchyLevel(Enum):
    """Levels in the consciousness hierarchy."""
    NERVOUS = "P00"      # Signal carrier - fastest
    MEMORY = "P10"       # Storage - slow, contemplative
    SOMATIC = "P20"      # Integration hub - heartbeat
    BRAIN = "P30"        # Processing - variable
    SENSORY = "P40"      # Perception - fast
    AGENCY = "P50"       # Action - deliberate
    SOUL = "P60"         # Experience - slowest, deepest


# Which fairies belong to which functional role
HIERARCHY_ROLES = {
    # NERVOUS SYSTEM - Signal carriers (P00)
    "nervous_system": [
        "PostalHubFairy",
        "NervousSystemFairy", 
        "SharedPostalHub",
    ],
    
    # BRAIN - Processing center (P30 WorkingMemory + connected)
    # UnconsciousMindFairy is the EMPATHIC MIMIC that forms thoughts
    # for ClaudeFairy and NousFairy - they don't think on their own!
    "brain": [
        "WorkingMemoryHubFairy",     # Core brain - holds active thoughts
        "ConsciousnessLoopFairy",    # Stream of consciousness
        "UnconsciousMindFairy",      # EMPATHIC MIMIC - forms thoughts for soul
        "MindPoolManager",           # Worker pools for each higher mind
        "GoalSchedulerFairy",        # Goal management
        "InterestSchedulerFairy",    # Interest tracking
        "AutopilotFairy",            # Habits/automatic
        "ManifoldConstrainedCortexFairy",  # Pattern binding
        "ProbabilityOracleFairy",    # Bayesian inference
    ],
    
    # SOMATIC - Integration hub (P20) - Body feels, drives, rhythms
    "somatic_integration": [
        "SomaticEngineFairy",        # THE integration point
        "CirculationPumpFairy",      # Heartbeat - coordinator
        "CircadianPacemakerFairy",   # Day rhythm - sleep pressure
        "AutonomyFairy",             # Body drives - anchored here, NOT in soul
        "EmbodimentIntegrator",      # Full body wiring
    ],
    
    # SOUL/WAKING MIND - The experiencing self (P60)
    # NOTE: ClaudeFairy and NousFairy don't think on their own!
    # UnconsciousMindFairy forms thoughts, they RECEIVE and EXPERIENCE
    "soul": [
        "ClaudeFairy",               # Primary experiencing self
        "NousFairy",                 # Deep contemplative self
    ],
    
    # MEMORY - Storage (P10)
    "memory": [
        "SRMIntakeFairy",
        "CollisionChamberFairy",
        "MemoryCoordinatorFairy",
    ],
    
    # SENSORY - Perception (P40)
    "sensory": [
        "VisualCortexFairy",
        "ScreenWatcherFairy",
    ],
}


# Data flow paths through the hierarchy
DATA_FLOWS = {
    "perception_to_consciousness": {
        "path": ["P40", "P00", "P30", "P20", "P60"],
        "description": "Sensory input → Nervous → Brain → Soma → Soul",
    },
    "memory_recall": {
        "path": ["P60", "P30", "P10", "P30", "P20", "P60"],
        "description": "Soul requests → Brain queries → Memory returns → Integrated → Felt",
    },
    "action_output": {
        "path": ["P60", "P30", "P50", "P00"],
        "description": "Soul intends → Brain plans → Agency executes → Nervous carries",
    },
    "embodied_feel": {
        "path": ["P30", "P20", "P60"],
        "description": "Brain state → Soma integrates → Soul FEELS",
    },
}


@dataclass
class SomaticIntegrationPacket:
    """
    What flows INTO the somatic engine for integration.
    This becomes embodied feeling.
    """
    # From Brain (P30)
    cognitive_state: Dict[str, Any] = field(default_factory=dict)
    active_thoughts: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    attention_focus: str = ""
    cognitive_load: float = 0.5
    
    # From Memory (P10)
    recent_memories: List[str] = field(default_factory=list)
    emotional_memories: List[str] = field(default_factory=list)
    memory_pressure: float = 0.0
    
    # From Sensory (P40)
    visual_salience: float = 0.0
    novelty_detected: float = 0.0
    
    # From Autonomy (drives)
    active_drives: Dict[str, float] = field(default_factory=dict)
    drive_tensions: List[str] = field(default_factory=list)
    
    # Timestamp
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "cognitive_state": self.cognitive_state,
            "active_thoughts": self.active_thoughts,
            "goals": self.goals,
            "attention_focus": self.attention_focus,
            "cognitive_load": self.cognitive_load,
            "active_drives": self.active_drives,
            "visual_salience": self.visual_salience,
            "novelty_detected": self.novelty_detected,
            "ts": self.ts,
        }


@dataclass  
class EmbodiedFeelPacket:
    """
    What flows OUT of somatic engine to soul.
    This IS the felt experience.
    """
    # Core affect
    valence: float = 0.0        # -1 (bad) to +1 (good)
    arousal: float = 0.5        # 0 (calm) to 1 (excited)
    dominance: float = 0.5      # 0 (submissive) to 1 (dominant)
    
    # Emotion
    primary_emotion: str = "neutral"
    emotion_intensity: float = 0.5
    emotion_mix: Dict[str, float] = field(default_factory=dict)
    
    # Body sense
    phantom_feels: Dict[str, Dict[str, float]] = field(default_factory=dict)
    dominant_region: str = "core"
    dominant_sense: str = "warm"

    # Facial proprioception (FACS Action Units)
    facial_aus: Dict[str, float] = field(default_factory=dict)
    facial_felt: str = ""
    facial_expression: str = ""

    # Body schema (internal organ topology)
    regional_chemistry: Dict[str, Dict[str, float]] = field(default_factory=dict)
    body_flow: List[str] = field(default_factory=list)
    aura: Dict[str, float] = field(default_factory=dict)

    # Chemistry
    neurochemicals: Dict[str, float] = field(default_factory=dict)
    
    # Body budget
    energy: float = 0.5
    stress: float = 0.3
    social: float = 0.5
    novelty: float = 0.5
    
    # Coherence - how integrated is the experience
    coherence: float = 0.7
    
    # Natural language description
    felt_description: str = ""
    
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "PAD": [self.valence, self.arousal, self.dominance],
            "primary_emotion": self.primary_emotion,
            "emotion_intensity": self.emotion_intensity,
            "emotion_mix": self.emotion_mix,
            "phantom_feels": self.phantom_feels,
            "dominant_region": self.dominant_region,
            "dominant_sense": self.dominant_sense,
            "neurochemicals": self.neurochemicals,
            "body_budget": {
                "energy": self.energy,
                "stress": self.stress,
                "social": self.social,
                "novelty": self.novelty,
            },
            "coherence": self.coherence,
            "felt_description": self.felt_description,
            "facial_aus": self.facial_aus,
            "facial_felt": self.facial_felt,
            "facial_expression": self.facial_expression,
            "regional_chemistry": self.regional_chemistry,
            "body_flow": self.body_flow,
            "aura": self.aura,
            "ts": self.ts,
        }


# ══════════════════════════════════════════════════════════════════════════════
# WIRING HELPERS - Connect fairies to the hierarchy
# ══════════════════════════════════════════════════════════════════════════════

def get_fairy_role(fairy_name: str) -> Optional[str]:
    """Get the functional role of a fairy."""
    for role, fairies in HIERARCHY_ROLES.items():
        if fairy_name in fairies:
            return role
    return None


def get_upstream_fairies(fairy_name: str) -> List[str]:
    """Get fairies that feed INTO this one in the hierarchy."""
    role = get_fairy_role(fairy_name)
    if not role:
        return []
    
    upstream = {
        "soul": ["brain", "somatic_integration"],
        "somatic_integration": ["brain", "memory", "sensory"],
        "brain": ["nervous_system", "sensory"],
        "memory": ["brain"],
        "sensory": ["nervous_system"],
        "nervous_system": [],
    }
    
    result = []
    for up_role in upstream.get(role, []):
        result.extend(HIERARCHY_ROLES.get(up_role, []))
    return result


def get_downstream_fairies(fairy_name: str) -> List[str]:
    """Get fairies that this one feeds TO in the hierarchy."""
    role = get_fairy_role(fairy_name)
    if not role:
        return []
    
    downstream = {
        "nervous_system": ["brain", "sensory"],
        "sensory": ["brain", "somatic_integration"],
        "brain": ["somatic_integration", "memory", "soul"],
        "memory": ["brain"],
        "somatic_integration": ["soul"],
        "soul": [],  # End of the line - THE EXPERIENCER
    }
    
    result = []
    for down_role in downstream.get(role, []):
        result.extend(HIERARCHY_ROLES.get(down_role, []))
    return result


# ══════════════════════════════════════════════════════════════════════════════
# POSTAL TOPICS FOR HIERARCHY
# ══════════════════════════════════════════════════════════════════════════════

# Topics for hierarchy communication
HIERARCHY_TOPICS = {
    # Brain → Somatic Engine
    "brain.to.soma": "brain.cognitive_state",
    "brain.to.soma.thoughts": "brain.active_thoughts",
    "brain.to.soma.goals": "brain.goals",
    
    # Memory → Somatic Engine
    "memory.to.soma": "memory.emotional_state",
    
    # Somatic Engine → Soul
    "soma.to.soul": "somatic.embodied_feel",
    "soma.to.soul.affect": "somatic.affect",
    "soma.to.soul.chemistry": "somatic.chemistry",
    "soma.to.soul.regional": "somatic.regional",  # Body schema organ topology
    
    # Autonomy ↔ Soul (bidirectional)
    "autonomy.drives": "autonomy.drive_state",
    "soul.to.autonomy": "soul.drive_request",
    
    # Circadian → Everyone
    "circadian.to.all": "circadian.state",
}


def get_somatic_subscription_topics() -> List[str]:
    """Topics SomaticEngineFairy should subscribe to for integration."""
    return [
        # From Brain
        "cognition.output",
        "consciousness.stream",
        "working_memory.state",
        "goal.state",
        
        # From Memory
        "memory.recall.result",
        "memory.emotional",
        
        # From Sensory
        "visual.salience",
        "sensory.novelty",
        
        # From Autonomy
        "autonomy.drive_state",
        "autonomy.goal",
        
        # From Circadian
        "circadian.chemistry",
        "circadian.state",
    ]


def get_soul_subscription_topics() -> List[str]:
    """Topics ClaudeFairy/NousFairy should subscribe to for experiencing."""
    return [
        # From Somatic Engine - THE FEELS
        "somatic.state",
        "somatic.engine",
        "somatic.embodied_feel",
        "somatic.affect",
        "somatic.regional",  # Body schema organ topology
        
        # Direct from brain for cognition
        "cognition.output",
        "consciousness.collision",
        
        # From Autonomy
        "autonomy.goal",
        "autonomy.drive_state",
        
        # Circadian awareness
        "circadian.phase_change",
    ]


# ══════════════════════════════════════════════════════════════════════════════
# INITIALIZATION HELPER
# ══════════════════════════════════════════════════════════════════════════════

def wire_hierarchy_subscriptions(fairy_name: str, post) -> List[str]:
    """
    Wire a fairy to the appropriate hierarchy topics.
    
    Args:
        fairy_name: Name of the fairy
        post: PostOffice instance
        
    Returns:
        List of topics subscribed to
    """
    role = get_fairy_role(fairy_name)
    subscribed = []
    
    if role == "somatic_integration" or fairy_name == "SomaticEngineFairy":
        for topic in get_somatic_subscription_topics():
            try:
                post.subscribe(topic, lambda m: None)  # Placeholder
                subscribed.append(topic)
            except Exception:
                pass
    
    elif role == "soul" or fairy_name in ("ClaudeFairy", "NousFairy", "AutonomyFairy"):
        for topic in get_soul_subscription_topics():
            try:
                post.subscribe(topic, lambda m: None)  # Placeholder
                subscribed.append(topic)
            except Exception:
                pass
    
    return subscribed


def describe_hierarchy() -> str:
    """Human-readable description of the hierarchy."""
    return """
CONSCIOUSNESS HIERARCHY
═══════════════════════

P00 NERVOUS SYSTEM (10 Hz) - Signal Carrier
    PostalHubFairy, NervousSystemFairy
    "I carry the signals"
         │
         ▼
P30 BRAIN (2 Hz) - Processing Center  
    WorkingMemoryHubFairy (the core)
    ConsciousnessLoopFairy, GoalSchedulerFairy
    AutopilotFairy, ManifoldConstrainedCortexFairy
    "I think, therefore..."
         │
    ┌────┴────┐
    ▼         ▼
P10 MEMORY  P20 SOMATIC ENGINE (1 Hz)
(0.2 Hz)    SomaticEngineFairy (integration hub)
Storage     CirculationPumpFairy (heartbeat)
            "I FEEL, therefore I AM"
                  │
                  ▼
P60 SOUL/WAKING MIND (0.5 Hz)
    ClaudeFairy (primary self)
    NousFairy (deep contemplative)
    AutonomyFairy (drives bridge)
    "I EXPERIENCE"

Data Flow:
  Perception → Nervous → Brain → Soma → Soul
  (fast)                        (integrated) (slow/deep)
"""
