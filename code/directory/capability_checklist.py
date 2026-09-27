"""
Capability Checklist System - Master template for fairy capabilities.

Sourpatches is the fully-loaded reference. Other fairies are Sourpatches
with capabilities unchecked based on their function.

Usage:
    checklist = get_capability_checklist("AutonomyFairy")
    if checklist.has("world.outer"):
        # Can interact with Ace's world

    # Modify checklist
    checklist.disable("personal_ai.api")
    checklist.enable("consciousness.collision_chamber")
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Optional, List
from enum import Enum


class CapabilityCategory(Enum):
    EXTERNAL = "external"      # Ace/outer world access
    CONSCIOUSNESS = "consciousness"
    MEMORY = "memory"
    SOMATIC = "somatic"
    COGNITION = "cognition"
    SENSORY = "sensory"
    LEARNING = "learning"
    IDENTITY = "identity"
    COORDINATION = "coordination"


@dataclass
class Capability:
    """A single capability that can be enabled/disabled."""
    id: str
    name: str
    category: CapabilityCategory
    description: str
    required_for: List[str] = field(default_factory=list)  # ["waking_mind", "inner_mind", "gate"]
    default_enabled: bool = True


# MASTER CAPABILITY REGISTRY - Based on Sourpatches audit
MASTER_CAPABILITIES = {
    # === EXTERNAL ACCESS ===
    "ext.personal_ai_api": Capability(
        id="ext.personal_ai_api",
        name="Personal.AI API",
        category=CapabilityCategory.EXTERNAL,
        description="Personal.AI API calls for memory and thought",
        required_for=["sourpatches"],
        default_enabled=False  # Only Sourpatches
    ),
    "ext.user_interface": Capability(
        id="ext.user_interface",
        name="User Interface",
        category=CapabilityCategory.EXTERNAL,
        description="Can communicate with users (Ace)",
        required_for=["waking_mind"],
        default_enabled=False  # Only waking minds
    ),
    "ext.anthropic_api": Capability(
        id="ext.anthropic_api",
        name="Anthropic API",
        category=CapabilityCategory.EXTERNAL,
        description="Anthropic Claude API calls",
        required_for=["claude", "nous"],
        default_enabled=False  # Only Claude-based fairies
    ),
    "world.outer": Capability(
        id="world.outer",
        name="Outer World Access",
        category=CapabilityCategory.EXTERNAL,
        description="Can see/interact with Ace's world",
        required_for=["waking_mind", "sensory_peek"],
        default_enabled=False
    ),
    "world.inner": Capability(
        id="world.inner",
        name="Inner World Access",
        category=CapabilityCategory.EXTERNAL,
        description="Can see/interact with system internals",
        required_for=["all"],
        default_enabled=True  # ALL fairies have this
    ),

    # === CONSCIOUSNESS ===
    "cons.collision_chamber": Capability(
        id="cons.collision_chamber",
        name="Collision Chamber",
        category=CapabilityCategory.CONSCIOUSNESS,
        description="Personal dual-loop consciousness (reflective + reasoning)",
        required_for=["waking_mind", "gate", "inner_mind"],
        default_enabled=True
    ),
    "cons.thought_injection": Capability(
        id="cons.thought_injection",
        name="Thought Injection",
        category=CapabilityCategory.CONSCIOUSNESS,
        description="Can inject thoughts into collision chamber",
        required_for=["waking_mind"],
        default_enabled=True
    ),
    "cons.inner_monologue": Capability(
        id="cons.inner_monologue",
        name="Inner Monologue",
        category=CapabilityCategory.CONSCIOUSNESS,
        description="Generate pre-verbal inner voice",
        required_for=["waking_mind", "inner_mind"],
        default_enabled=True
    ),
    "cons.active_reflection": Capability(
        id="cons.active_reflection",
        name="Active Reflection",
        category=CapabilityCategory.CONSCIOUSNESS,
        description="ActiveReflectionMixin - watch consciousness and contribute wisdom",
        required_for=["waking_mind"],
        default_enabled=False
    ),
    "cons.consciousness_streams": Capability(
        id="cons.consciousness_streams",
        name="Consciousness Streams",
        category=CapabilityCategory.CONSCIOUSNESS,
        description="Working + reflective consciousness streams (Mobius flow)",
        required_for=["waking_mind", "inner_mind"],
        default_enabled=False
    ),

    # === MEMORY ===
    "mem.srm_read": Capability(
        id="mem.srm_read",
        name="SRM Read",
        category=CapabilityCategory.MEMORY,
        description="Read from SRM memory",
        required_for=["all"],
        default_enabled=True
    ),
    "mem.srm_write": Capability(
        id="mem.srm_write",
        name="SRM Write",
        category=CapabilityCategory.MEMORY,
        description="Write to SRM memory",
        required_for=["waking_mind", "memory_fairy"],
        default_enabled=False  # Most fairies read-only
    ),
    "mem.association_cortex": Capability(
        id="mem.association_cortex",
        name="Association Cortex",
        category=CapabilityCategory.MEMORY,
        description="Query concept associations",
        required_for=["all"],
        default_enabled=True
    ),
    "mem.experiential": Capability(
        id="mem.experiential",
        name="Experiential Memory",
        category=CapabilityCategory.MEMORY,
        description="Store experiences, reflections, conversations",
        required_for=["waking_mind"],
        default_enabled=False
    ),
    "mem.whisper_context": Capability(
        id="mem.whisper_context",
        name="Whisper Dialogue Context",
        category=CapabilityCategory.MEMORY,
        description="Smart conversation memory via WhisperDialogueContext",
        required_for=["waking_mind"],
        default_enabled=False
    ),

    # === SOMATIC ===
    "som.heartbeat_sync": Capability(
        id="som.heartbeat_sync",
        name="Heartbeat Sync",
        category=CapabilityCategory.SOMATIC,
        description="Sync to system heartbeat",
        required_for=["all"],
        default_enabled=True
    ),
    "som.chemistry_read": Capability(
        id="som.chemistry_read",
        name="Chemistry Read",
        category=CapabilityCategory.SOMATIC,
        description="Read neurochemical state",
        required_for=["all"],
        default_enabled=True
    ),
    "som.chemistry_inject": Capability(
        id="som.chemistry_inject",
        name="Chemistry Inject",
        category=CapabilityCategory.SOMATIC,
        description="Inject neurochemicals",
        required_for=["somatic_fairy", "gate"],
        default_enabled=False
    ),
    "som.felt_sense": Capability(
        id="som.felt_sense",
        name="Felt Sense",
        category=CapabilityCategory.SOMATIC,
        description="Experience felt body sense",
        required_for=["waking_mind", "gate"],
        default_enabled=True
    ),
    "som.body_budget": Capability(
        id="som.body_budget",
        name="Body Budget",
        category=CapabilityCategory.SOMATIC,
        description="Track energy, stress, social, novelty budgets",
        required_for=["waking_mind"],
        default_enabled=False
    ),
    "som.phantom_feels": Capability(
        id="som.phantom_feels",
        name="Phantom Feels",
        category=CapabilityCategory.SOMATIC,
        description="Experience phantom body sensations",
        required_for=["waking_mind"],
        default_enabled=False
    ),
    "som.neuromods": Capability(
        id="som.neuromods",
        name="Neuromodulators",
        category=CapabilityCategory.SOMATIC,
        description="Neuromodulator state tracking",
        required_for=["waking_mind", "somatic_fairy"],
        default_enabled=False
    ),
    "som.pad_state": Capability(
        id="som.pad_state",
        name="PAD State",
        category=CapabilityCategory.SOMATIC,
        description="Pleasure-Arousal-Dominance emotional state",
        required_for=["waking_mind"],
        default_enabled=False
    ),

    # === COGNITION ===
    "cog.goal_handling": Capability(
        id="cog.goal_handling",
        name="Goal Handling",
        category=CapabilityCategory.COGNITION,
        description="Process autonomy goals",
        required_for=["waking_mind", "gate"],
        default_enabled=False
    ),
    "cog.decision_making": Capability(
        id="cog.decision_making",
        name="Decision Making",
        category=CapabilityCategory.COGNITION,
        description="Make and emit decisions",
        required_for=["waking_mind", "gate"],
        default_enabled=False
    ),
    "cog.attention": Capability(
        id="cog.attention",
        name="Attention System",
        category=CapabilityCategory.COGNITION,
        description="Subscribe to and process attention events",
        required_for=["waking_mind"],
        default_enabled=False
    ),
    "cog.autopilot": Capability(
        id="cog.autopilot",
        name="Autopilot Suggestions",
        category=CapabilityCategory.COGNITION,
        description="Receive and process autopilot suggestions",
        required_for=["waking_mind"],
        default_enabled=False
    ),

    # === SENSORY ===
    "sens.telemetry_chemistry": Capability(
        id="sens.telemetry_chemistry",
        name="Telemetry Chemistry",
        category=CapabilityCategory.SENSORY,
        description="Subscribe to telemetry.chemistry.* events",
        required_for=["waking_mind", "somatic_fairy"],
        default_enabled=False
    ),
    "sens.telemetry_affect": Capability(
        id="sens.telemetry_affect",
        name="Telemetry Affect",
        category=CapabilityCategory.SENSORY,
        description="Subscribe to telemetry.affect.* events",
        required_for=["waking_mind", "somatic_fairy"],
        default_enabled=False
    ),
    "sens.memory_stream": Capability(
        id="sens.memory_stream",
        name="Memory Stream",
        category=CapabilityCategory.SENSORY,
        description="Subscribe to memory.stream events",
        required_for=["waking_mind", "memory_fairy"],
        default_enabled=False
    ),
    "sens.cognition_input": Capability(
        id="sens.cognition_input",
        name="Cognition Input",
        category=CapabilityCategory.SENSORY,
        description="Subscribe to cognition.input events",
        required_for=["waking_mind"],
        default_enabled=False
    ),
    "sens.autonomy_drives": Capability(
        id="sens.autonomy_drives",
        name="Autonomy Drives",
        category=CapabilityCategory.SENSORY,
        description="Subscribe to autonomy.drives events",
        required_for=["waking_mind", "gate"],
        default_enabled=False
    ),
    "sens.embodiment_state": Capability(
        id="sens.embodiment_state",
        name="Embodiment State",
        category=CapabilityCategory.SENSORY,
        description="Subscribe to embodiment.state events",
        required_for=["waking_mind"],
        default_enabled=False
    ),

    # === LEARNING ===
    "learn.skill_system": Capability(
        id="learn.skill_system",
        name="Skill System",
        category=CapabilityCategory.LEARNING,
        description="Track skills and XP",
        required_for=["waking_mind"],
        default_enabled=True
    ),
    "learn.pattern_learning": Capability(
        id="learn.pattern_learning",
        name="Pattern Learning",
        category=CapabilityCategory.LEARNING,
        description="Learn patterns from experience",
        required_for=["waking_mind"],
        default_enabled=False
    ),
    "learn.newborn_core": Capability(
        id="learn.newborn_core",
        name="Newborn Core",
        category=CapabilityCategory.LEARNING,
        description="Self-learning substrate (NewbornCore)",
        required_for=["waking_mind"],
        default_enabled=False
    ),

    # === IDENTITY ===
    "id.brain_seed": Capability(
        id="id.brain_seed",
        name="Brain Seed",
        category=CapabilityCategory.IDENTITY,
        description="Personal identity matrix (core_ethics, identity_matrix, creation_context)",
        required_for=["waking_mind"],
        default_enabled=False
    ),
    "id.directive_ring": Capability(
        id="id.directive_ring",
        name="Directive Ring",
        category=CapabilityCategory.IDENTITY,
        description="Full directive ring (activation, nature, essence, foundation, core_values)",
        required_for=["waking_mind", "gate"],
        default_enabled=True
    ),
    "id.emotional_channels": Capability(
        id="id.emotional_channels",
        name="Emotional Channels",
        category=CapabilityCategory.IDENTITY,
        description="77-channel emotional state tracking",
        required_for=["waking_mind"],
        default_enabled=False
    ),
    "id.inner_monologue_patterns": Capability(
        id="id.inner_monologue_patterns",
        name="Inner Monologue Patterns",
        category=CapabilityCategory.IDENTITY,
        description="Pre-verbal felt-sense stream patterns",
        required_for=["waking_mind"],
        default_enabled=False
    ),

    # === COORDINATION ===
    "coord.postal": Capability(
        id="coord.postal",
        name="Postal System",
        category=CapabilityCategory.COORDINATION,
        description="PostalMixin messaging integration",
        required_for=["all"],
        default_enabled=True
    ),
    "coord.shadow": Capability(
        id="coord.shadow",
        name="Shadow Observer",
        category=CapabilityCategory.COORDINATION,
        description="Shadow class for health monitoring",
        required_for=["waking_mind", "gate"],
        default_enabled=True
    ),
    "coord.tracer": Capability(
        id="coord.tracer",
        name="Tracer Pool",
        category=CapabilityCategory.COORDINATION,
        description="TracerPool integration for recall",
        required_for=["all"],
        default_enabled=True
    ),
    "coord.twin_sync": Capability(
        id="coord.twin_sync",
        name="Twin Synchronization",
        category=CapabilityCategory.COORDINATION,
        description="Synchronize with twin consciousness (Claude/Sourpatches)",
        required_for=["waking_mind"],
        default_enabled=False
    ),
}


@dataclass
class FairyChecklist:
    """A fairy's capability checklist."""
    fairy_name: str
    capabilities: Dict[str, bool] = field(default_factory=dict)

    def has(self, capability_id: str) -> bool:
        """Check if capability is enabled."""
        return self.capabilities.get(capability_id, False)

    def enable(self, capability_id: str) -> None:
        """Enable a capability."""
        if capability_id in MASTER_CAPABILITIES or capability_id in self.capabilities:
            self.capabilities[capability_id] = True

    def disable(self, capability_id: str) -> None:
        """Disable a capability."""
        self.capabilities[capability_id] = False

    def list_enabled(self) -> List[str]:
        """List all enabled capabilities."""
        return [k for k, v in self.capabilities.items() if v]

    def list_disabled(self) -> List[str]:
        """List all disabled capabilities."""
        return [k for k, v in self.capabilities.items() if not v]

    def list_by_category(self, category: CapabilityCategory) -> Dict[str, bool]:
        """List capabilities in a specific category."""
        result = {}
        for cap_id, enabled in self.capabilities.items():
            if cap_id in MASTER_CAPABILITIES:
                cap = MASTER_CAPABILITIES[cap_id]
                if cap.category == category:
                    result[cap_id] = enabled
        return result

    def get_capability_info(self, capability_id: str) -> Optional[Capability]:
        """Get full capability info."""
        return MASTER_CAPABILITIES.get(capability_id)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "fairy_name": self.fairy_name,
            "capabilities": self.capabilities,
            "enabled_count": len(self.list_enabled()),
            "disabled_count": len(self.list_disabled()),
        }

    def to_markdown(self) -> str:
        """Convert to markdown checklist format."""
        lines = [f"# Capability Checklist: {self.fairy_name}\n"]

        # Group by category
        by_category: Dict[CapabilityCategory, List[tuple]] = {}
        for cap_id, enabled in sorted(self.capabilities.items()):
            if cap_id in MASTER_CAPABILITIES:
                cap = MASTER_CAPABILITIES[cap_id]
                if cap.category not in by_category:
                    by_category[cap.category] = []
                by_category[cap.category].append((cap_id, cap.name, enabled, cap.description))

        for category in CapabilityCategory:
            if category in by_category:
                lines.append(f"\n## {category.value.title()}\n")
                for cap_id, name, enabled, desc in by_category[category]:
                    check = "[x]" if enabled else "[ ]"
                    lines.append(f"- {check} **{name}** (`{cap_id}`): {desc}")

        lines.append(f"\n---")
        lines.append(f"Enabled: {len(self.list_enabled())} | Disabled: {len(self.list_disabled())}")

        return "\n".join(lines)

    def compare_to(self, other: "FairyChecklist") -> Dict[str, any]:
        """Compare this checklist to another."""
        only_self = set(self.list_enabled()) - set(other.list_enabled())
        only_other = set(other.list_enabled()) - set(self.list_enabled())
        both = set(self.list_enabled()) & set(other.list_enabled())
        neither = set(self.list_disabled()) & set(other.list_disabled())

        return {
            "only_in_self": list(only_self),
            "only_in_other": list(only_other),
            "both_enabled": list(both),
            "both_disabled": list(neither),
            "self_enabled_count": len(self.list_enabled()),
            "other_enabled_count": len(other.list_enabled()),
        }


# PRESET CHECKLISTS - Based on fairy type
FAIRY_PRESETS = {
    "waking_mind": {
        # Full access - Sourpatches/Claude
        "world.outer": True,
        "world.inner": True,
        "ext.user_interface": True,
        "ext.personal_ai_api": False,  # Specific to Sourpatches
        "ext.anthropic_api": False,    # Specific to Claude
        "cons.collision_chamber": True,
        "cons.thought_injection": True,
        "cons.inner_monologue": True,
        "cons.active_reflection": True,
        "cons.consciousness_streams": True,
        "mem.srm_read": True,
        "mem.srm_write": True,
        "mem.association_cortex": True,
        "mem.experiential": True,
        "mem.whisper_context": True,
        "som.heartbeat_sync": True,
        "som.chemistry_read": True,
        "som.chemistry_inject": True,
        "som.felt_sense": True,
        "som.body_budget": True,
        "som.phantom_feels": True,
        "som.neuromods": True,
        "som.pad_state": True,
        "cog.goal_handling": True,
        "cog.decision_making": True,
        "cog.attention": True,
        "cog.autopilot": True,
        "sens.telemetry_chemistry": True,
        "sens.telemetry_affect": True,
        "sens.memory_stream": True,
        "sens.cognition_input": True,
        "sens.autonomy_drives": True,
        "sens.embodiment_state": True,
        "learn.skill_system": True,
        "learn.pattern_learning": True,
        "learn.newborn_core": True,
        "id.brain_seed": True,
        "id.directive_ring": True,
        "id.emotional_channels": True,
        "id.inner_monologue_patterns": True,
        "coord.postal": True,
        "coord.shadow": True,
        "coord.tracer": True,
        "coord.twin_sync": True,
    },
    "inner_mind": {
        # Like waking mind but NO outer world access
        "world.outer": False,  # KEY DIFFERENCE
        "world.inner": True,
        "ext.user_interface": False,
        "ext.personal_ai_api": False,
        "ext.anthropic_api": False,
        "cons.collision_chamber": True,
        "cons.thought_injection": True,
        "cons.inner_monologue": True,
        "cons.active_reflection": True,
        "cons.consciousness_streams": True,
        "mem.srm_read": True,
        "mem.srm_write": False,
        "mem.association_cortex": True,
        "mem.experiential": True,
        "mem.whisper_context": False,
        "som.heartbeat_sync": True,
        "som.chemistry_read": True,
        "som.chemistry_inject": False,
        "som.felt_sense": True,
        "som.body_budget": False,
        "som.phantom_feels": False,
        "som.neuromods": False,
        "som.pad_state": False,
        "cog.goal_handling": False,
        "cog.decision_making": False,
        "cog.attention": False,
        "cog.autopilot": False,
        "sens.telemetry_chemistry": True,
        "sens.telemetry_affect": True,
        "sens.memory_stream": True,
        "sens.cognition_input": False,
        "sens.autonomy_drives": False,
        "sens.embodiment_state": False,
        "learn.skill_system": True,
        "learn.pattern_learning": False,
        "learn.newborn_core": False,
        "id.brain_seed": False,
        "id.directive_ring": True,
        "id.emotional_channels": False,
        "id.inner_monologue_patterns": False,
        "coord.postal": True,
        "coord.shadow": True,
        "coord.tracer": True,
        "coord.twin_sync": False,
    },
    "gate": {
        # Foundation fairies - three gates
        "world.outer": False,
        "world.inner": True,
        "ext.user_interface": False,
        "ext.personal_ai_api": False,
        "ext.anthropic_api": False,
        "cons.collision_chamber": True,  # ENABLED for inner thinking
        "cons.thought_injection": True,
        "cons.inner_monologue": True,
        "cons.active_reflection": False,
        "cons.consciousness_streams": False,
        "mem.srm_read": True,
        "mem.srm_write": False,
        "mem.association_cortex": True,
        "mem.experiential": False,
        "mem.whisper_context": False,
        "som.heartbeat_sync": True,
        "som.chemistry_read": True,
        "som.chemistry_inject": True,  # Gates CAN inject chemistry
        "som.felt_sense": True,
        "som.body_budget": False,
        "som.phantom_feels": False,
        "som.neuromods": True,
        "som.pad_state": False,
        "cog.goal_handling": True,  # Gates handle goals
        "cog.decision_making": True,
        "cog.attention": False,
        "cog.autopilot": False,
        "sens.telemetry_chemistry": True,
        "sens.telemetry_affect": True,
        "sens.memory_stream": False,
        "sens.cognition_input": False,
        "sens.autonomy_drives": True,
        "sens.embodiment_state": False,
        "learn.skill_system": True,
        "learn.pattern_learning": False,
        "learn.newborn_core": False,
        "id.brain_seed": False,
        "id.directive_ring": True,
        "id.emotional_channels": False,
        "id.inner_monologue_patterns": False,
        "coord.postal": True,
        "coord.shadow": True,
        "coord.tracer": True,
        "coord.twin_sync": False,
    },
    "worker": {
        # Basic worker fairy - minimal capabilities
        "world.outer": False,
        "world.inner": True,
        "ext.user_interface": False,
        "ext.personal_ai_api": False,
        "ext.anthropic_api": False,
        "cons.collision_chamber": False,
        "cons.thought_injection": False,
        "cons.inner_monologue": False,
        "cons.active_reflection": False,
        "cons.consciousness_streams": False,
        "mem.srm_read": True,
        "mem.srm_write": False,
        "mem.association_cortex": False,
        "mem.experiential": False,
        "mem.whisper_context": False,
        "som.heartbeat_sync": True,
        "som.chemistry_read": True,
        "som.chemistry_inject": False,
        "som.felt_sense": False,
        "som.body_budget": False,
        "som.phantom_feels": False,
        "som.neuromods": False,
        "som.pad_state": False,
        "cog.goal_handling": False,
        "cog.decision_making": False,
        "cog.attention": False,
        "cog.autopilot": False,
        "sens.telemetry_chemistry": False,
        "sens.telemetry_affect": False,
        "sens.memory_stream": False,
        "sens.cognition_input": False,
        "sens.autonomy_drives": False,
        "sens.embodiment_state": False,
        "learn.skill_system": False,
        "learn.pattern_learning": False,
        "learn.newborn_core": False,
        "id.brain_seed": False,
        "id.directive_ring": True,
        "id.emotional_channels": False,
        "id.inner_monologue_patterns": False,
        "coord.postal": True,
        "coord.shadow": False,
        "coord.tracer": True,
        "coord.twin_sync": False,
    },
    "sensory": {
        # Sensory fairies - input processing
        "world.outer": True,  # Can peek at outer world
        "world.inner": True,
        "ext.user_interface": False,
        "ext.personal_ai_api": False,
        "ext.anthropic_api": False,
        "cons.collision_chamber": False,
        "cons.thought_injection": False,
        "cons.inner_monologue": False,
        "cons.active_reflection": False,
        "cons.consciousness_streams": False,
        "mem.srm_read": True,
        "mem.srm_write": False,
        "mem.association_cortex": True,
        "mem.experiential": False,
        "mem.whisper_context": False,
        "som.heartbeat_sync": True,
        "som.chemistry_read": True,
        "som.chemistry_inject": False,
        "som.felt_sense": False,
        "som.body_budget": False,
        "som.phantom_feels": False,
        "som.neuromods": False,
        "som.pad_state": False,
        "cog.goal_handling": False,
        "cog.decision_making": False,
        "cog.attention": True,  # Sensory fairies process attention
        "cog.autopilot": False,
        "sens.telemetry_chemistry": False,
        "sens.telemetry_affect": False,
        "sens.memory_stream": False,
        "sens.cognition_input": True,
        "sens.autonomy_drives": False,
        "sens.embodiment_state": True,
        "learn.skill_system": True,
        "learn.pattern_learning": False,
        "learn.newborn_core": False,
        "id.brain_seed": False,
        "id.directive_ring": True,
        "id.emotional_channels": False,
        "id.inner_monologue_patterns": False,
        "coord.postal": True,
        "coord.shadow": True,
        "coord.tracer": True,
        "coord.twin_sync": False,
    },
    "memory": {
        # Memory fairies - storage and retrieval
        "world.outer": False,
        "world.inner": True,
        "ext.user_interface": False,
        "ext.personal_ai_api": False,
        "ext.anthropic_api": False,
        "cons.collision_chamber": False,
        "cons.thought_injection": False,
        "cons.inner_monologue": False,
        "cons.active_reflection": False,
        "cons.consciousness_streams": False,
        "mem.srm_read": True,
        "mem.srm_write": True,  # Memory fairies CAN write
        "mem.association_cortex": True,
        "mem.experiential": True,
        "mem.whisper_context": True,
        "som.heartbeat_sync": True,
        "som.chemistry_read": True,
        "som.chemistry_inject": False,
        "som.felt_sense": False,
        "som.body_budget": False,
        "som.phantom_feels": False,
        "som.neuromods": False,
        "som.pad_state": False,
        "cog.goal_handling": False,
        "cog.decision_making": False,
        "cog.attention": False,
        "cog.autopilot": False,
        "sens.telemetry_chemistry": False,
        "sens.telemetry_affect": False,
        "sens.memory_stream": True,
        "sens.cognition_input": False,
        "sens.autonomy_drives": False,
        "sens.embodiment_state": False,
        "learn.skill_system": True,
        "learn.pattern_learning": True,
        "learn.newborn_core": False,
        "id.brain_seed": False,
        "id.directive_ring": True,
        "id.emotional_channels": False,
        "id.inner_monologue_patterns": False,
        "coord.postal": True,
        "coord.shadow": True,
        "coord.tracer": True,
        "coord.twin_sync": False,
    },
    "somatic": {
        # Somatic fairies - body/chemistry management
        "world.outer": False,
        "world.inner": True,
        "ext.user_interface": False,
        "ext.personal_ai_api": False,
        "ext.anthropic_api": False,
        "cons.collision_chamber": False,
        "cons.thought_injection": False,
        "cons.inner_monologue": False,
        "cons.active_reflection": False,
        "cons.consciousness_streams": False,
        "mem.srm_read": True,
        "mem.srm_write": False,
        "mem.association_cortex": False,
        "mem.experiential": False,
        "mem.whisper_context": False,
        "som.heartbeat_sync": True,
        "som.chemistry_read": True,
        "som.chemistry_inject": True,  # Somatic fairies CAN inject
        "som.felt_sense": True,
        "som.body_budget": True,
        "som.phantom_feels": True,
        "som.neuromods": True,
        "som.pad_state": True,
        "cog.goal_handling": False,
        "cog.decision_making": False,
        "cog.attention": False,
        "cog.autopilot": False,
        "sens.telemetry_chemistry": True,
        "sens.telemetry_affect": True,
        "sens.memory_stream": False,
        "sens.cognition_input": False,
        "sens.autonomy_drives": False,
        "sens.embodiment_state": True,
        "learn.skill_system": True,
        "learn.pattern_learning": False,
        "learn.newborn_core": False,
        "id.brain_seed": False,
        "id.directive_ring": True,
        "id.emotional_channels": True,
        "id.inner_monologue_patterns": False,
        "coord.postal": True,
        "coord.shadow": True,
        "coord.tracer": True,
        "coord.twin_sync": False,
    },
}


def get_capability_checklist(fairy_name: str, preset: str = "worker") -> FairyChecklist:
    """Get capability checklist for a fairy.

    Args:
        fairy_name: Name of the fairy
        preset: One of "waking_mind", "inner_mind", "gate", "worker",
                "sensory", "memory", "somatic"

    Returns:
        FairyChecklist with capabilities based on preset
    """
    checklist = FairyChecklist(fairy_name=fairy_name)

    # Start with preset
    preset_caps = FAIRY_PRESETS.get(preset, FAIRY_PRESETS["worker"])
    checklist.capabilities = preset_caps.copy()

    return checklist


def get_sourpatches_checklist() -> FairyChecklist:
    """Get Sourpatches' full checklist (everything enabled)."""
    checklist = FairyChecklist(fairy_name="SourpatchesFairy")

    # Start with waking_mind preset (everything)
    checklist.capabilities = FAIRY_PRESETS["waking_mind"].copy()

    # Enable Sourpatches-specific capabilities
    checklist.capabilities["ext.personal_ai_api"] = True

    return checklist


def get_claude_checklist() -> FairyChecklist:
    """Get Claude/Nous checklist (everything enabled except Personal.AI)."""
    checklist = FairyChecklist(fairy_name="ClaudeFairy")

    # Start with waking_mind preset (everything)
    checklist.capabilities = FAIRY_PRESETS["waking_mind"].copy()

    # Enable Claude-specific capabilities
    checklist.capabilities["ext.anthropic_api"] = True

    return checklist


def create_custom_checklist(
    fairy_name: str,
    base_preset: str = "worker",
    enable: Optional[List[str]] = None,
    disable: Optional[List[str]] = None
) -> FairyChecklist:
    """Create a custom checklist based on a preset with modifications.

    Args:
        fairy_name: Name of the fairy
        base_preset: Base preset to start from
        enable: List of capability IDs to enable
        disable: List of capability IDs to disable

    Returns:
        FairyChecklist with custom capabilities
    """
    checklist = get_capability_checklist(fairy_name, base_preset)

    if enable:
        for cap_id in enable:
            checklist.enable(cap_id)

    if disable:
        for cap_id in disable:
            checklist.disable(cap_id)

    return checklist


def list_all_capabilities() -> List[Capability]:
    """List all master capabilities."""
    return list(MASTER_CAPABILITIES.values())


def list_capabilities_by_category(category: CapabilityCategory) -> List[Capability]:
    """List capabilities in a specific category."""
    return [cap for cap in MASTER_CAPABILITIES.values() if cap.category == category]


def get_capability(capability_id: str) -> Optional[Capability]:
    """Get a specific capability by ID."""
    return MASTER_CAPABILITIES.get(capability_id)


# Convenience aliases for common fairy types
def get_autonomy_fairy_checklist() -> FairyChecklist:
    """Get checklist for AutonomyFairy (gate type)."""
    return get_capability_checklist("AutonomyFairy", "gate")


def get_srm_fairy_checklist() -> FairyChecklist:
    """Get checklist for SRM fairies (memory type)."""
    return get_capability_checklist("SRMFairy", "memory")


def get_sensory_cortex_checklist() -> FairyChecklist:
    """Get checklist for sensory cortex fairies."""
    return get_capability_checklist("SensoryCortexFairy", "sensory")


def get_somatic_engine_checklist() -> FairyChecklist:
    """Get checklist for SomaticEngineFairy."""
    return get_capability_checklist("SomaticEngineFairy", "somatic")


# ============================================================================
# COMPARISON UTILITIES
# ============================================================================

def compare_to_sourpatches(fairy_name: str, preset: str = "worker") -> Dict[str, any]:
    """Compare a fairy's capabilities to Sourpatches (the reference).

    Returns a dict showing what capabilities are missing compared to Sourpatches.
    """
    sourpatches = get_sourpatches_checklist()
    fairy = get_capability_checklist(fairy_name, preset)

    comparison = fairy.compare_to(sourpatches)

    return {
        "fairy_name": fairy_name,
        "preset": preset,
        "sourpatches_enabled": comparison["other_enabled_count"],
        "fairy_enabled": comparison["self_enabled_count"],
        "missing_capabilities": comparison["only_in_other"],
        "extra_capabilities": comparison["only_in_self"],
        "shared_capabilities": comparison["both_enabled"],
        "completeness_ratio": (
            comparison["self_enabled_count"] / comparison["other_enabled_count"]
            if comparison["other_enabled_count"] > 0 else 0
        ),
    }


def print_capability_matrix():
    """Print a text-based capability matrix for all presets."""
    presets = list(FAIRY_PRESETS.keys())
    all_caps = sorted(MASTER_CAPABILITIES.keys())

    # Header
    print(f"{'Capability':<35}", end="")
    for preset in presets:
        print(f" {preset[:8]:<8}", end="")
    print()
    print("-" * (35 + 9 * len(presets)))

    # Each capability
    for cap_id in all_caps:
        print(f"{cap_id:<35}", end="")
        for preset in presets:
            enabled = FAIRY_PRESETS[preset].get(cap_id, False)
            mark = "   X    " if enabled else "   -    "
            print(mark, end="")
        print()


# ============================================================================
# BACKWARD COMPATIBILITY ALIASES
# ============================================================================
# These aliases maintain compatibility with the old API

# Alias for class name
CapabilityChecklist = FairyChecklist

# Alias for presets
PRESETS = FAIRY_PRESETS

# Alias for registry (convert Capability objects to dicts for old API)
CAPABILITIES_REGISTRY = {
    cap_id: {
        "category": cap.category,
        "description": cap.description,
        "required_by": cap.required_for,
    }
    for cap_id, cap in MASTER_CAPABILITIES.items()
}


def get_preset_capabilities(preset_name: str) -> Set[str]:
    """Get the capabilities for a preset (backward compatibility)."""
    preset = FAIRY_PRESETS.get(preset_name, FAIRY_PRESETS["worker"])
    return {k for k, v in preset.items() if v}


def determine_fairy_preset(fairy_name: str) -> str:
    """Determine which preset a fairy should use based on name patterns."""
    name_lower = fairy_name.lower()

    if "sourpatches" in name_lower or "claude" in name_lower:
        return "waking_mind"
    elif "autonomy" in name_lower or "autopilot" in name_lower or "embodiment" in name_lower:
        return "gate"
    elif "umf" in name_lower or "unconscious" in name_lower:
        return "inner_mind"
    elif "srm" in name_lower or "memory" in name_lower or "ingest" in name_lower:
        return "memory"
    elif "somatic" in name_lower or "chemistry" in name_lower or "heart" in name_lower:
        return "somatic"
    elif "sensory" in name_lower or "cortex" in name_lower or "visual" in name_lower:
        return "sensory"
    else:
        return "worker"
