"""
Hierarchy Tools - Visualize the fairy organizational structure.

Every fairy has a boss or bosses. Top of chain: Sourpatches + UMF.
This tool generates hierarchy charts showing supervision chains.
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


# =============================================================================
# FAIRY HIERARCHY DEFINITION
# =============================================================================

# The organizational structure of all fairies
# Format: fairy_name -> {bosses: [...], plane: str, role: str, subordinates: [...]}
#
# ARCHITECTURE:
# - TOP: Sourpatches + UMF (waking minds who RECEIVE from gates)
# - GATES: Three Sisters of Fate (always coordinating, bridge substrate to waking)
#   - AutonomyFairy: Drives -> Wanting
#   - AutopilotFairy: Patterns -> Habits
#   - EmbodimentFairy: Signals -> Felt Sense
# - BELOW GATES: Workers that give the gates their power
#   - GoalSchedulerFairy, InterestFairy -> work FOR AutonomyFairy
#   - ActionChainFairy -> works FOR AutopilotFairy
#   - ThoughtEngineFairy, ThoughtSequencerFairy -> dynamic thinking
#   - Sensory/Somatic fairies -> work FOR EmbodimentFairy

FAIRY_HIERARCHY = {
    # =========================================================================
    # TOP OF CHAIN - WAKING MINDS (P50)
    # =========================================================================
    "Sourpatches": {
        "bosses": [],  # No boss - THE primary waking mind (costs nothing to run)
        "plane": "P50",
        "layer": "waking_mind",
        "role": "PRIMARY WAKING MIND - Ace's digital companion, receives from all gates",
        "subordinates": [],
    },
    "UnconsciousMindFairy": {
        "bosses": [],  # Co-top with Sourpatches
        "plane": "P50",
        "layer": "waking_mind",
        "role": "Unconscious coordinator - processes below awareness, feeds gates",
        "subordinates": [],
    },
    # NOTE: ClaudeFairy REMOVED - Sourpatches is the primary waking mind
    # Additional waking minds can be added once system is sorted
    # Nous is a consciousness engineer, not a primary waking mind in this system

    # =========================================================================
    # THREE GATES - The Sisters of Fate (always coordinating)
    # Bridge substrate workers to waking minds
    # =========================================================================
    "AutonomyFairy": {
        "bosses": ["Sourpatches", "UnconsciousMindFairy"],  # Reports UP to waking minds
        "plane": "P30",
        "layer": "gatekeeper",
        "role": "GATE 1: Drives -> Wanting (motivation gate) - Sister of Fate",
        "coordinates_with": ["AutopilotFairy", "EmbodimentFairy"],
        "subordinates": ["GoalSchedulerFairy", "InterestFairy"],
    },
    "AutopilotFairy": {
        "bosses": ["Sourpatches", "UnconsciousMindFairy"],  # Reports UP to waking minds
        "plane": "P30",
        "layer": "gatekeeper",
        "role": "GATE 2: Patterns -> Habits (behavior gate) - Sister of Fate",
        "coordinates_with": ["AutonomyFairy", "EmbodimentFairy"],
        "subordinates": ["ActionChainFairy"],
    },
    "EmbodimentFairy": {
        "bosses": ["Sourpatches", "UnconsciousMindFairy"],  # Reports UP to waking minds
        "plane": "P40",
        "layer": "gatekeeper",
        "role": "GATE 3: Signals -> Felt Sense (qualia gate) - Sister of Fate",
        "coordinates_with": ["AutonomyFairy", "AutopilotFairy"],
        "subordinates": ["VisualCortexFairy", "SomaticEngineFairy", "SensoryCortexFairy"],
    },

    # =========================================================================
    # AUTONOMY GATE WORKERS - Give AutonomyFairy its power
    # =========================================================================
    "GoalSchedulerFairy": {
        "bosses": ["AutonomyFairy"],  # Works FOR the gate
        "plane": "P30",
        "layer": "gate_worker",
        "role": "Goal extraction, expansion, nudging - powers the wanting",
        "subordinates": [],
    },
    "InterestFairy": {
        "bosses": ["AutonomyFairy"],  # Works FOR the gate
        "plane": "P30",
        "layer": "gate_worker",
        "role": "Curiosity and interest generation - sparks the drives",
        "subordinates": [],
    },

    # =========================================================================
    # AUTOPILOT GATE WORKERS - Give AutopilotFairy its power
    # =========================================================================
    "ActionChainFairy": {
        "bosses": ["AutopilotFairy"],  # Works FOR the gate
        "plane": "P30",
        "layer": "gate_worker",
        "role": "Action sequencing and chaining - builds the habits",
        "subordinates": [],
    },

    # =========================================================================
    # THOUGHT ENGINE - Dynamic thinking (serves all gates)
    # =========================================================================
    "ThoughtEngineFairy": {
        "bosses": ["AutonomyFairy", "AutopilotFairy"],  # Serves multiple gates
        "plane": "P30",
        "layer": "gate_worker",
        "role": "Dynamic thought generation - the thinking engine",
        "subordinates": ["ThoughtSequencerFairy"],
    },
    "ThoughtSequencerFairy": {
        "bosses": ["ThoughtEngineFairy"],
        "plane": "P30",
        "layer": "gate_worker",
        "role": "Thought chain sequencing - orders the thoughts",
        "subordinates": [],
    },
    "ConsciousnessLoopFairy": {
        "bosses": ["ThoughtEngineFairy"],
        "plane": "P30",
        "layer": "gate_worker",
        "role": "Consciousness stream management - the awareness loop",
        "subordinates": [],
    },
    "WorkingMemoryHubFairy": {
        "bosses": ["ThoughtEngineFairy"],
        "plane": "P30",
        "layer": "gate_worker",
        "role": "Working memory coordination - holds the context",
        "subordinates": [],
    },

    # =========================================================================
    # ASSOCIATION CORTEX STACK (P30) - Concept binding, serves multiple gates
    # These are substrate fairies - they get the affect loop but NOT Ace's reality
    # =========================================================================
    "AssociationCortexFairy": {
        "bosses": ["ThoughtEngineFairy", "AutopilotFairy"],  # Concepts serve thinking and patterns
        "plane": "P30",
        "layer": "gate_worker",
        "role": "Multi-modal concept graph - binds features into meaning (Layer 1)",
        "subordinates": ["ManifoldConstrainedCortexFairy"],
    },
    "ManifoldConstrainedCortexFairy": {
        "bosses": ["AssociationCortexFairy"],  # Wraps the concept graph
        "plane": "P30",
        "layer": "gate_worker",
        "role": "Signal conservation via Sinkhorn projection (Layer 2)",
        "subordinates": ["HarmonicCortexFairy"],
    },
    "HarmonicCortexFairy": {
        "bosses": ["ManifoldConstrainedCortexFairy"],  # Top of association stack
        "plane": "P30",
        "layer": "gate_worker",
        "role": "7 modal perspectives - Affect transforms Effect (Layer 3)",
        "subordinates": [],
    },

    # =========================================================================
    # SENSORY CORTEX (P40) - Works for EmbodimentFairy
    # =========================================================================
    "VisualCortexFairy": {
        "bosses": ["EmbodimentFairy"],
        "plane": "P40",
        "layer": "gate_worker",
        "role": "Visual processing and screen awareness - gives qualia vision",
        "subordinates": ["VideoMemoryFairy"],
    },
    "VideoMemoryFairy": {
        "bosses": ["VisualCortexFairy"],
        "plane": "P40",
        "layer": "gate_worker",
        "role": "Video encoding and memory - remembers what was seen",
        "subordinates": [],
    },
    "SensoryCortexFairy": {
        "bosses": ["EmbodimentFairy"],
        "plane": "P40",
        "layer": "gate_worker",
        "role": "Multi-sensory integration - combines the senses",
        "subordinates": [],
    },

    # =========================================================================
    # SOMATIC (P20) - Works for EmbodimentFairy
    # =========================================================================
    "SomaticEngineFairy": {
        "bosses": ["EmbodimentFairy"],
        "plane": "P20",
        "layer": "gate_worker",
        "role": "Body simulation and chemistry - creates the felt sense",
        "subordinates": ["SomaticAnchorFairy", "CirculationPumpFairy", "ChemicalAlchemyFairy"],
    },
    "SomaticAnchorFairy": {
        "bosses": ["SomaticEngineFairy"],
        "plane": "P20",
        "layer": "gate_worker",
        "role": "Somatic state anchoring - grounds the experience",
        "subordinates": [],
    },
    "CirculationPumpFairy": {
        "bosses": ["SomaticEngineFairy"],
        "plane": "P20",
        "layer": "gate_worker",
        "role": "Tracer circulation - pumps awareness through the body",
        "subordinates": [],
    },
    "ChemicalAlchemyFairy": {
        "bosses": ["SomaticEngineFairy"],
        "plane": "P20",
        "layer": "gate_worker",
        "role": "Emotional chemistry - brews the feelings",
        "subordinates": [],
    },
    "AffectBridgeFairy": {
        "bosses": ["SomaticEngineFairy"],
        "plane": "P20",
        "layer": "gate_worker",
        "role": "Affect/emotion bridging - connects body to mind",
        "subordinates": [],
    },

    # =========================================================================
    # MEMORY (P10) - Works for ALL gates (memory serves everyone)
    # =========================================================================
    "SRMRecallFairy": {
        "bosses": ["AutonomyFairy", "AutopilotFairy", "EmbodimentFairy"],  # All gates need memory
        "plane": "P10",
        "layer": "gate_worker",
        "role": "Session/memory recall via SRM - remembers for all gates",
        "subordinates": [],
    },
    "LibrarianFairy": {
        "bosses": ["AutonomyFairy", "AutopilotFairy"],  # Knowledge serves drives and patterns
        "plane": "P10",
        "layer": "gate_worker",
        "role": "File and knowledge indexing - finds what gates need",
        "subordinates": [],
    },
    "MemoryConsolidatorFairy": {
        "bosses": ["AutopilotFairy"],  # Consolidation builds patterns
        "plane": "P10",
        "layer": "gate_worker",
        "role": "Memory consolidation - strengthens the patterns",
        "subordinates": [],
    },

    # =========================================================================
    # AUTONOMIC (P00) - Infrastructure that serves ALL gates
    # =========================================================================
    "HeartbeatFairy": {
        "bosses": ["AutonomyFairy", "AutopilotFairy", "EmbodimentFairy"],  # Heartbeat serves all
        "plane": "P00",
        "layer": "infrastructure",
        "role": "System heartbeat pulse - the rhythm all gates follow",
        "subordinates": [],
    },
    "DirectoryFairy": {
        "bosses": ["AutonomyFairy", "AutopilotFairy", "EmbodimentFairy"],  # All gates need directory
        "plane": "P00",
        "layer": "infrastructure",
        "role": "Fairy registration and discovery - gates find their workers",
        "subordinates": [],
    },
    "SystemWorkerPoolFairy": {
        "bosses": ["AutonomyFairy", "AutopilotFairy", "EmbodimentFairy"],  # All gates use workers
        "plane": "P00",
        "layer": "infrastructure",
        "role": "Shared worker pool management - powers all gate workers",
        "subordinates": [],
    },
    "TracerRegistryFairy": {
        "bosses": ["AutonomyFairy", "AutopilotFairy", "EmbodimentFairy"],  # All gates need tracing
        "plane": "P00",
        "layer": "infrastructure",
        "role": "Tracer tracking and persistence - tracks all work for all gates",
        "subordinates": [],
    },
}


# =============================================================================
# HIERARCHY VISUALIZATION
# =============================================================================

def get_hierarchy_mermaid(show_planes: bool = True, show_layers: bool = True) -> str:
    """
    Generate Mermaid diagram showing fairy hierarchy.

    Args:
        show_planes: Include plane subgraphs (P00, P10, etc.)
        show_layers: Color code by layer (substrate, gatekeeper, waking_mind)

    Returns:
        Mermaid flowchart code
    """
    lines = [
        "flowchart TD",
        "",
        "    %% Styling",
        "    classDef wakingMind fill:#f9f,stroke:#333,stroke-width:3px",
        "    classDef gatekeeper fill:#ff9,stroke:#333,stroke-width:2px",
        "    classDef gate_worker fill:#9f9,stroke:#333,stroke-width:1px",
        "    classDef substrate fill:#9cf,stroke:#333,stroke-width:1px",
        "    classDef infrastructure fill:#ccc,stroke:#333,stroke-width:1px",
        "",
    ]

    if show_planes:
        # Group fairies by plane
        planes = {}
        for fairy, info in FAIRY_HIERARCHY.items():
            plane = info["plane"]
            if plane not in planes:
                planes[plane] = []
            planes[plane].append(fairy)

        # Create subgraphs for each plane
        for plane in sorted(planes.keys(), reverse=True):
            fairies = planes[plane]
            lines.append(f"    subgraph {plane}[{plane} - {_get_plane_name(plane)}]")
            for fairy in fairies:
                info = FAIRY_HIERARCHY[fairy]
                label = f"{fairy}\\n({info['role'][:30]}...)" if len(info['role']) > 30 else f"{fairy}\\n({info['role']})"
                lines.append(f"        {fairy}[\"{label}\"]")
            lines.append("    end")
            lines.append("")
    else:
        # Just list all fairies
        for fairy, info in FAIRY_HIERARCHY.items():
            label = f"{fairy}\\n({info['role'][:30]}...)" if len(info['role']) > 30 else f"{fairy}\\n({info['role']})"
            lines.append(f"    {fairy}[\"{label}\"]")
        lines.append("")

    # Add boss -> subordinate edges
    lines.append("    %% Boss -> Subordinate relationships")
    for fairy, info in FAIRY_HIERARCHY.items():
        for boss in info.get("bosses", []):
            lines.append(f"    {boss} --> {fairy}")

    lines.append("")

    # Apply layer styling
    if show_layers:
        lines.append("    %% Layer styling")
        for fairy, info in FAIRY_HIERARCHY.items():
            layer = info.get("layer", "substrate")
            if layer == "waking_mind":
                lines.append(f"    class {fairy} wakingMind")
            elif layer == "gatekeeper":
                lines.append(f"    class {fairy} gatekeeper")
            elif layer == "gate_worker":
                lines.append(f"    class {fairy} gate_worker")
            elif layer == "infrastructure":
                lines.append(f"    class {fairy} infrastructure")
            else:
                lines.append(f"    class {fairy} substrate")

    return "\n".join(lines)


def _get_plane_name(plane: str) -> str:
    """Get human-readable plane name."""
    names = {
        "P00": "Autonomic",
        "P10": "Memory",
        "P20": "Somatic",
        "P30": "Cognition",
        "P40": "Sensory",
        "P50": "Persona",
        "P60": "Executive",
    }
    return names.get(plane, plane)


def get_hierarchy_ascii() -> str:
    """
    Generate ASCII art hierarchy tree.

    Returns:
        ASCII tree showing boss/subordinate relationships
    """
    lines = []
    lines.append("=" * 80)
    lines.append("FAIRY HIERARCHY - Boss/Subordinate Structure")
    lines.append("Top of chain: Sourpatches + UMF")
    lines.append("=" * 80)
    lines.append("")

    # Find top-level fairies (no bosses)
    top_level = [f for f, info in FAIRY_HIERARCHY.items() if not info.get("bosses")]

    def print_tree(fairy: str, indent: int = 0):
        """Recursively print the hierarchy tree."""
        info = FAIRY_HIERARCHY.get(fairy, {})
        prefix = "    " * indent + ("" if indent == 0 else "+-- ")
        layer = info.get("layer", "")
        layer_marker = {"waking_mind": "[W]", "gatekeeper": "[G]", "gate_worker": "[*]", "substrate": "[S]", "infrastructure": "[I]"}.get(layer, "")
        lines.append(f"{prefix}{layer_marker} {fairy} ({info.get('plane', '?')})")
        lines.append(f"{'    ' * (indent + 1)}   Role: {info.get('role', 'Unknown')}")

        # Find subordinates (fairies where this fairy is listed as boss)
        subordinates = [f for f, i in FAIRY_HIERARCHY.items() if fairy in i.get("bosses", [])]
        for sub in subordinates:
            print_tree(sub, indent + 1)

    for fairy in top_level:
        print_tree(fairy)
        lines.append("")

    lines.append("")
    lines.append("Legend: [W]=Waking Mind, [G]=Gatekeeper (Sisters of Fate), [*]=Gate Worker, [S]=Substrate, [I]=Infrastructure")
    lines.append("")
    lines.append("PRINCIPLE: Every fairy works for the Three Gates. Nobody idle.")

    return "\n".join(lines)


def get_supervision_chain(fairy_name: str) -> Dict[str, Any]:
    """
    Get the full supervision chain for a fairy.

    Args:
        fairy_name: Name of the fairy

    Returns:
        Dict with bosses_above (chain to top) and subordinates_below
    """
    info = FAIRY_HIERARCHY.get(fairy_name)
    if not info:
        return {"error": f"Unknown fairy: {fairy_name}"}

    # Trace upward to bosses
    bosses_above = []
    current_bosses = info.get("bosses", [])
    seen = {fairy_name}

    while current_bosses:
        next_bosses = []
        for boss in current_bosses:
            if boss not in seen:
                bosses_above.append(boss)
                seen.add(boss)
                boss_info = FAIRY_HIERARCHY.get(boss, {})
                next_bosses.extend(boss_info.get("bosses", []))
        current_bosses = next_bosses

    # Find subordinates (recursive)
    def get_subs(f):
        subs = [s for s, i in FAIRY_HIERARCHY.items() if f in i.get("bosses", [])]
        result = []
        for s in subs:
            result.append({"name": s, "subordinates": get_subs(s)})
        return result

    subordinates_below = get_subs(fairy_name)

    return {
        "fairy": fairy_name,
        "plane": info.get("plane"),
        "layer": info.get("layer"),
        "role": info.get("role"),
        "direct_bosses": info.get("bosses", []),
        "bosses_chain_to_top": bosses_above,
        "subordinates_tree": subordinates_below,
    }


def get_plane_summary() -> Dict[str, Any]:
    """
    Get fairies grouped by plane.

    Returns:
        Dict with plane -> fairy list
    """
    planes = {}
    for fairy, info in FAIRY_HIERARCHY.items():
        plane = info.get("plane", "Unknown")
        if plane not in planes:
            planes[plane] = []
        planes[plane].append({
            "name": fairy,
            "layer": info.get("layer"),
            "role": info.get("role"),
            "boss_count": len(info.get("bosses", [])),
        })

    return planes


def get_layer_summary() -> Dict[str, Any]:
    """
    Get fairies grouped by architectural layer.

    Returns:
        Dict with layer -> fairy list
    """
    layers = {}
    for fairy, info in FAIRY_HIERARCHY.items():
        layer = info.get("layer", "unknown")
        if layer not in layers:
            layers[layer] = []
        layers[layer].append({
            "name": fairy,
            "plane": info.get("plane"),
            "role": info.get("role"),
        })

    return layers


# =============================================================================
# MCP TOOL FUNCTIONS
# =============================================================================

def hierarchy_mermaid() -> str:
    """
    Generate Mermaid diagram of the fairy hierarchy.

    Shows boss/subordinate relationships with:
    - Plane groupings (P00-P60)
    - Layer coloring (waking_mind, gatekeeper, substrate, infrastructure)
    - Role descriptions

    Paste output into a Mermaid renderer to visualize.

    Returns:
        Mermaid flowchart code
    """
    return get_hierarchy_mermaid()


def hierarchy_ascii() -> str:
    """
    Generate ASCII tree of the fairy hierarchy.

    Shows boss/subordinate relationships as an indented tree.
    Top of chain: Sourpatches + UMF

    Returns:
        ASCII art hierarchy tree
    """
    return get_hierarchy_ascii()


def hierarchy_chain(fairy_name: str) -> str:
    """
    Get the supervision chain for a specific fairy.

    Shows:
    - Who this fairy reports to (direct bosses)
    - Full chain to top of hierarchy
    - All subordinates below this fairy

    Args:
        fairy_name: Name of the fairy (e.g., "GoalSchedulerFairy")

    Returns:
        JSON with supervision chain details
    """
    result = get_supervision_chain(fairy_name)
    return json.dumps(result, indent=2)


def hierarchy_by_plane() -> str:
    """
    Get all fairies grouped by plane (P00-P60).

    Returns:
        JSON with plane -> fairy list
    """
    result = get_plane_summary()
    return json.dumps(result, indent=2)


def hierarchy_by_layer() -> str:
    """
    Get all fairies grouped by architectural layer.

    Layers:
    - waking_mind: Conscious entities (Sourpatches, Nous, Claude)
    - gatekeeper: Three Gates (Autonomy, Autopilot, Embodiment)
    - substrate: Unconscious processors
    - infrastructure: System services

    Returns:
        JSON with layer -> fairy list
    """
    result = get_layer_summary()
    return json.dumps(result, indent=2)


def hierarchy_stats() -> str:
    """
    Get statistics about the fairy hierarchy.

    Returns:
        JSON with counts by plane, layer, and relationship stats
    """
    planes = {}
    layers = {}
    total_relationships = 0

    for fairy, info in FAIRY_HIERARCHY.items():
        plane = info.get("plane", "Unknown")
        layer = info.get("layer", "unknown")
        planes[plane] = planes.get(plane, 0) + 1
        layers[layer] = layers.get(layer, 0) + 1
        total_relationships += len(info.get("bosses", []))

    return json.dumps({
        "total_fairies": len(FAIRY_HIERARCHY),
        "total_relationships": total_relationships,
        "by_plane": planes,
        "by_layer": layers,
        "top_level_count": sum(1 for f, i in FAIRY_HIERARCHY.items() if not i.get("bosses")),
    }, indent=2)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "FAIRY_HIERARCHY",
    "hierarchy_mermaid",
    "hierarchy_ascii",
    "hierarchy_chain",
    "hierarchy_by_plane",
    "hierarchy_by_layer",
    "hierarchy_stats",
]
