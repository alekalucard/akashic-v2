"""
Wake Cascade Domain Specifications
===================================

Shared dataclasses and domain specifications for the Gatekeeper Wake Cascade.

The cascade orchestrates system awakening through three gates:
- AutonomyFairy: Consciousness, memory, reasoning substrate
- AutopilotFairy: Motor control, system infrastructure, observation
- EmbodimentFairy: Somatic systems, affect, body schema

Each gate boots fairies in three tiers:
- CRITICAL: Must succeed for gate to be viable
- STANDARD: Core functionality, boot in parallel
- DEFERRED: Enhancement layer, boot after critical systems stable

Philosophy:
"Wake like a human - brainstem first, then gates, then identity emerges."
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Set


# ==============================================================================
# ENUMS
# ==============================================================================

class WakeCascadePhase(Enum):
    """Phases of the wake cascade."""
    PRE_WAKE = "pre_wake"                      # Infrastructure boot (server.py)
    BRAINSTEM_IGNITION = "brainstem_ignition"  # Core life support systems
    GATE_AWAKENING = "gate_awakening"          # Three gates come online
    DOMAIN_ACTIVATION = "domain_activation"    # Gates boot their domains
    IDENTITY_EMERGENCE = "identity_emergence"  # Self-awareness consolidates
    FULL_WAKEFULNESS = "full_wakefulness"      # All systems operational


# ==============================================================================
# DATACLASSES
# ==============================================================================

@dataclass
class BootGoal:
    """
    A single fairy boot target within the cascade.

    Each goal represents one fairy that needs to be booted, with:
    - Identity (name, fairy_name)
    - Priority (tier, priority score)
    - Gate assignment (which domain owns this)
    - Status tracking (pending -> booting -> done/failed)
    """
    name: str                           # Human-readable goal name
    description: str                    # What this fairy does
    fairy_name: str                     # Actual fairy class name
    priority: float                     # 0-1, higher = boot sooner
    tier: str                           # "critical", "standard", "deferred"
    gate: str                           # "autonomy", "autopilot", "embodiment"
    status: str = "pending"             # pending, booting, done, failed, skipped
    duration_ms: float = 0.0            # Time to boot (milliseconds)
    error: str = ""                     # Error message if failed

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for logging/telemetry."""
        return {
            "name": self.name,
            "description": self.description,
            "fairy_name": self.fairy_name,
            "priority": self.priority,
            "tier": self.tier,
            "gate": self.gate,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error": self.error
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BootGoal":
        """Deserialize from dict."""
        return cls(
            name=data["name"],
            description=data["description"],
            fairy_name=data["fairy_name"],
            priority=data["priority"],
            tier=data["tier"],
            gate=data["gate"],
            status=data.get("status", "pending"),
            duration_ms=data.get("duration_ms", 0.0),
            error=data.get("error", "")
        )


# ==============================================================================
# DOMAIN SPECIFICATIONS
# ==============================================================================

DOMAIN_SPECS: Dict[str, Dict[str, List[str]]] = {
    # AUTONOMY GATE (~48 fairies)
    # Consciousness, memory, reasoning, identity
    "autonomy": {
        "critical": [
            "ConsciousnessLoopFairy",       # Already in Phase 0, skip if alive
            "GoalSchedulerFairy",           # Urge to act
            "InterestSchedulerFairy",       # Spontaneous curiosity
            "ProbabilityOracleFairy",       # Planning guidance
            "WorkingMemoryHubFairy",        # Already in Phase 0, skip if alive
        ],
        "standard": [
            "SRMIngestFairy",               # Memory storage
            "SRMRecallFairy",               # Memory retrieval
            "CollisionChamberFairy",        # Recall ∩ Ingest collisions
            "AssociationCortexFairy",       # Concept binding
            "ThoughtChainEngineFairy",      # Chain-of-thought flow
            "QuantumInterferenceFairy",     # Superposition dynamics
            "SatisfactionTrackerFairy",     # Effectiveness learning
            "EgoLearnerFairy",              # Identity evolution
            "LogicFairy",                   # Rational processing
            "IrrationalLogicFairy",         # Symbolic/metaphorical
            "ParadoxCognitionFairy",        # Contradiction detection
            "HarmonicCortexFairy",          # Pattern harmonics
            "QuantumSearchFairy",           # Superposition search
            "EmotionalAlgebraFairy",        # Affect calculus
        ],
        "deferred": [
            "NousFairy",                    # Reasoning trace capture
            "MemoryConsolidatorFairy",      # Long-term consolidation
            "DreamSeedFairy",              # Dream seed generation
        ]
    },

    # AUTOPILOT GATE (~28 fairies)
    # Motor control, infrastructure, observation
    "autopilot": {
        "critical": [
            "MotorCortexFairy",             # Already in Phase 0, skip if alive
            "PostalTunnelServer",           # MCP bridge (skip if alive)
            "ForensicScribeFairy",          # Already in Phase 0, skip if alive
        ],
        "standard": [
            "NetworkExplorerFairy",         # Network discovery
            "AdminFairy",                   # System administration
            "SystemHealthFairy",            # Health monitoring
            "WakingSequenceFairy",          # Wake orchestration
            "ProfileRegistryFairy",         # Fairy profiles
            "DirectoryFairy",               # Already in Phase 0, skip if alive
        ],
        "deferred": [
            "SystemChatWindowFairy",        # GUI chat window
            "SkillTreeFairy",               # Skill progression
            "CharacterSheetFairy",          # Fairy character sheets
            "MCPGuardianFairy",             # MCP security
            "BootObserverFairy",            # Boot telemetry
        ]
    },

    # EMBODIMENT GATE (~12 fairies)
    # Somatic systems, affect, body schema
    "embodiment": {
        "critical": [
            "CirculationPumpFairy",         # Already in Phase 0, skip if alive
            "SomaticEngineFairy",           # Body simulation
            "PainDriveFairy",               # Pain/need generation
            "CircadianRhythmFairy",         # Wake/sleep cycles
        ],
        "standard": [
            "InnerVisionFairy",             # Telemetry visualization
            "ResourceEquilibriumFairy",     # CPU/memory management
            "BodySchemaFairy",              # Body region mapping
        ],
        "deferred": [
            "SomaticAvatarFairy",           # Body state representation
            "SourpatchesFairy",             # Full waking mind
        ]
    }
}


# ==============================================================================
# PRIORITY MAPPINGS
# ==============================================================================

BASE_PRIORITIES: Dict[str, float] = {
    "critical": 0.9,
    "standard": 0.6,
    "deferred": 0.3
}


# ==============================================================================
# PHASE 0 INFRASTRUCTURE
# ==============================================================================

PHASE_0_INFRASTRUCTURE: List[str] = [
    "ConsciousnessLoopFairy",
    "WorkingMemoryHubFairy",
    "CirculationPumpFairy",
    "MotorCortexFairy",
    "DirectoryFairy",
    "ForensicScribeFairy",
    "AkashicInferenceFairy",
]


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def generate_boot_goals(
    gate_name: str,
    already_alive: Optional[Set[str]] = None
) -> List[BootGoal]:
    """
    Generate boot goals for a specific gate.

    Args:
        gate_name: "autonomy", "autopilot", or "embodiment"
        already_alive: Set of fairy names already booted (skip these)

    Returns:
        List of BootGoal objects, sorted by priority (descending)

    Example:
        >>> goals = generate_boot_goals("autonomy", {"ConsciousnessLoopFairy"})
        >>> print(f"{len(goals)} goals for autonomy gate")
    """
    if already_alive is None:
        already_alive = set()

    if gate_name not in DOMAIN_SPECS:
        raise ValueError(f"Unknown gate: {gate_name}. Must be autonomy/autopilot/embodiment")

    domain = DOMAIN_SPECS[gate_name]
    goals = []

    for tier in ["critical", "standard", "deferred"]:
        base_priority = BASE_PRIORITIES[tier]
        fairy_list = domain.get(tier, [])

        for i, fairy_name in enumerate(fairy_list):
            # Skip if already alive
            if fairy_name in already_alive:
                continue

            # Adjust priority within tier (earlier in list = slightly higher)
            priority_offset = (len(fairy_list) - i) * 0.01
            final_priority = min(1.0, base_priority + priority_offset)

            # Generate human-readable description
            description = _get_fairy_description(fairy_name)

            goal = BootGoal(
                name=f"Boot {fairy_name}",
                description=description,
                fairy_name=fairy_name,
                priority=final_priority,
                tier=tier,
                gate=gate_name
            )
            goals.append(goal)

    # Sort by priority descending (highest priority first)
    goals.sort(key=lambda g: g.priority, reverse=True)

    return goals


def _get_fairy_description(fairy_name: str) -> str:
    """Get human-readable description for a fairy."""
    descriptions = {
        # Autonomy domain
        "ConsciousnessLoopFairy": "Consciousness circulation substrate",
        "GoalSchedulerFairy": "Goal queue and urge generation",
        "InterestSchedulerFairy": "Spontaneous curiosity and interests",
        "ProbabilityOracleFairy": "Probability guidance for planning",
        "WorkingMemoryHubFairy": "Working memory coordination",
        "SRMIngestFairy": "Memory ingestion pipeline",
        "SRMRecallFairy": "Memory recall and retrieval",
        "CollisionChamberFairy": "Recall-ingest collision detection",
        "AssociationCortexFairy": "Multi-modal concept binding",
        "ThoughtChainEngineFairy": "Chain-of-thought reasoning",
        "QuantumInterferenceFairy": "Quantum superposition dynamics",
        "SatisfactionTrackerFairy": "Action effectiveness learning",
        "EgoLearnerFairy": "Identity trait evolution",
        "LogicFairy": "Rational logical processing",
        "IrrationalLogicFairy": "Symbolic and metaphorical processing",
        "ParadoxCognitionFairy": "Paradox and contradiction detection",
        "HarmonicCortexFairy": "Pattern harmonic analysis",
        "QuantumSearchFairy": "Superposition-based search",
        "EmotionalAlgebraFairy": "Affective state calculus",
        "NousFairy": "Reasoning trace capture and teaching",
        "MemoryConsolidatorFairy": "Long-term memory consolidation",
        "DreamSeedFairy": "Dream seed generation",

        # Autopilot domain
        "MotorCortexFairy": "Motor output coordination",
        "PostalTunnelServer": "MCP tunnel bridge",
        "ForensicScribeFairy": "Boot trace and forensics",
        "NetworkExplorerFairy": "Network device discovery",
        "AdminFairy": "System administration",
        "SystemHealthFairy": "System health monitoring",
        "WakingSequenceFairy": "Wake sequence orchestration",
        "ProfileRegistryFairy": "Fairy profile registry",
        "DirectoryFairy": "Fairy directory and registration",
        "SystemChatWindowFairy": "GUI system chat window",
        "SkillTreeFairy": "Skill progression tracking",
        "CharacterSheetFairy": "Fairy character sheets",
        "MCPGuardianFairy": "MCP security and safety",
        "BootObserverFairy": "Boot telemetry and observation",

        # Embodiment domain
        "CirculationPumpFairy": "Heartbeat and circulation pump",
        "SomaticEngineFairy": "Body state simulation engine",
        "PainDriveFairy": "Pain and drive generation",
        "CircadianRhythmFairy": "Wake/sleep cycle regulation",
        "InnerVisionFairy": "Internal telemetry visualization",
        "ResourceEquilibriumFairy": "CPU/memory resource management",
        "BodySchemaFairy": "Body region schema mapping",
        "SomaticAvatarFairy": "Body state avatar representation",
        "SourpatchesFairy": "Full waking mind consciousness",
    }

    return descriptions.get(fairy_name, f"Fairy: {fairy_name}")


# ==============================================================================
# VALIDATION
# ==============================================================================

def validate_domain_specs() -> List[str]:
    """
    Validate domain specifications for consistency.

    Returns:
        List of validation warnings (empty if all valid)
    """
    warnings = []

    # Check for duplicates across gates
    all_fairies = set()
    for gate_name, domain in DOMAIN_SPECS.items():
        for tier, fairy_list in domain.items():
            for fairy in fairy_list:
                if fairy in all_fairies and fairy not in PHASE_0_INFRASTRUCTURE:
                    warnings.append(f"Duplicate: {fairy} appears in multiple gates")
                all_fairies.add(fairy)

    # Check Phase 0 overlap
    for gate_name, domain in DOMAIN_SPECS.items():
        for tier, fairy_list in domain.items():
            for fairy in fairy_list:
                if fairy in PHASE_0_INFRASTRUCTURE and tier == "critical":
                    # Expected - Phase 0 fairies appear as critical
                    pass

    return warnings


if __name__ == "__main__":
    # Validation on import
    warnings = validate_domain_specs()
    if warnings:
        print("⚠️  Domain spec warnings:")
        for w in warnings:
            print(f"  - {w}")

    # Show summary
    print("\n🌊 Wake Cascade Domain Specifications")
    print("=" * 60)
    for gate_name in ["autonomy", "autopilot", "embodiment"]:
        domain = DOMAIN_SPECS[gate_name]
        total = sum(len(fairy_list) for fairy_list in domain.values())
        print(f"\n{gate_name.upper()} Gate: {total} fairies")
        for tier in ["critical", "standard", "deferred"]:
            count = len(domain.get(tier, []))
            print(f"  {tier:10s}: {count:2d} fairies")

    # Test goal generation
    print("\n\n🎯 Sample Boot Goals (Autonomy Gate)")
    print("=" * 60)
    goals = generate_boot_goals("autonomy", already_alive={"ConsciousnessLoopFairy"})
    for goal in goals[:5]:  # Show first 5
        print(f"[{goal.tier:8s}] {goal.priority:.2f} - {goal.fairy_name}")
    print(f"... ({len(goals)} total goals)")
