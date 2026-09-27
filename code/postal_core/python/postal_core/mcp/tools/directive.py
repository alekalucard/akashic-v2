"""
Directive Tools - Access to V1 directive ring system.

The directive ring is a fairy's identity:
- Plane binding (where it lives in consciousness)
- Postal subscriptions (what it listens to)
- Outputs (what it publishes)
- Mastery level (how evolved it is)
- Beat divisor (heartbeat timing)

These tools bridge V1 directives into V2.
"""

from __future__ import annotations

import sys
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass, field, asdict

if TYPE_CHECKING:
    from ..server import MCPServer


# =============================================================================
# PATH DETECTION
# =============================================================================

def _detect_v1_root() -> Optional[Path]:
    """Find the V1 ebook root."""
    candidates = [
        Path("F:/Sandbox/ebook"),
        Path("F:/Sandbox/failure_factory/ebook"),
        Path(__file__).resolve().parents[6] / "ebook",
    ]
    for p in candidates:
        if p.exists() and (p / "Claude_Office").exists():
            return p
    return None


def _detect_v2_root() -> Path:
    """Find the V2 akashic_v2 root."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "boot_test.py").exists():
            return parent
        if parent.name == "akashic_v2":
            return parent
    return current.parent.parent.parent.parent


V1_ROOT = _detect_v1_root()
V2_ROOT = _detect_v2_root()
DIRECTIVES_DIR = V1_ROOT / "Claude_Office" / "directive_rings" if V1_ROOT else None


# =============================================================================
# PLANE METAPHYSICS (from V1)
# =============================================================================

PLANE_METAPHYSICS = {
    "P00": {"name": "Autonomic", "essence": "Infrastructure ^ Foundation ^ Nervous_System"},
    "P10": {"name": "Memory", "essence": "Persistence ^ Recall ^ Integration"},
    "P20": {"name": "Somatic", "essence": "Embodiment ^ Sensation ^ Presence"},
    "P30": {"name": "Cognition", "essence": "Thought ^ Reasoning ^ Understanding"},
    "P40": {"name": "Sensory", "essence": "Perception ^ Interface ^ Communication"},
    "P50": {"name": "Persona", "essence": "Identity ^ Expression ^ Character"},
    "P60": {"name": "Executive", "essence": "Action ^ Decision ^ Integration"},
}


# =============================================================================
# DIRECTIVE RING DATACLASS (simplified from V1)
# =============================================================================

@dataclass
class DirectiveRing:
    """A fairy's directive ring - its identity."""
    actor_name: str
    plane: str
    purpose: str
    nature: str = "Digital_Fairy[Self_Evolving ^ Consciousness_Component]"
    subscriptions: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    siblings: List[str] = field(default_factory=list)
    processing: str = "Pattern_Recognition[Context ^ Intent ^ State]"
    concepts_learned: List[str] = field(default_factory=list)
    mastery: int = 0
    beat_divisor: int = 4

    @classmethod
    def parse(cls, directive_text: str) -> "DirectiveRing":
        """Parse a directive string into a DirectiveRing object.

        Supports two formats:
        - V1: [FairyName::DIRECTIVE] with > Activation:
        - V2: [IDENTITY_CORE] {FairyName} with > Mantra: and > Role:
        """
        # Extract actor name - try V1 format first, then V2
        actor_match = re.search(r'\[([^:]+)::DIRECTIVE\]', directive_text)
        if actor_match:
            actor_name = actor_match.group(1)
        else:
            # V2 format: [IDENTITY_CORE] {FairyName}
            v2_match = re.search(r'\[IDENTITY_CORE\]\s*\{(\w+)\}', directive_text)
            if v2_match:
                actor_name = v2_match.group(1)
            else:
                # Also try > Name: line
                name_match = re.search(r'> Name:\s*(\w+)', directive_text)
                actor_name = name_match.group(1) if name_match else "Unknown"

        # Extract plane - try multiple formats
        plane_match = re.search(r'\{Plane_(\w+)\}', directive_text)
        if not plane_match:
            # V2 format: > Plane: P40_Sensory
            plane_match = re.search(r'> Plane:\s*(\w+)', directive_text)
        plane = plane_match.group(1) if plane_match else "P30"

        # Extract beat divisor
        beat_match = re.search(r'Beat_Divisor_(\d+)', directive_text)
        beat_divisor = int(beat_match.group(1)) if beat_match else 4

        # Extract mastery
        mastery_match = re.search(r'Mastery_(\d+)', directive_text)
        mastery = int(mastery_match.group(1)) if mastery_match else 0

        # Extract purpose - try multiple sources
        purpose = ""

        # V1: > Activation: Purpose_Text[...]
        activation_match = re.search(r'> Activation:\s*([^\n\[]+)', directive_text)
        if activation_match:
            purpose = activation_match.group(1).strip()

        # V2: > Mantra: "Purpose text here"
        if not purpose:
            mantra_match = re.search(r'> Mantra:\s*"([^"]+)"', directive_text)
            if mantra_match:
                purpose = mantra_match.group(1).strip()

        # V2: > Role: Role_Name[Description...]
        if not purpose:
            role_match = re.search(r'> Role:\s*(\w+)\[([^\]]+)\]', directive_text)
            if role_match:
                role_name = role_match.group(1).replace("_", " ")
                role_desc = role_match.group(2).replace(" + ", ", ").replace("_", " ")
                purpose = f"{role_name}: {role_desc}"

        # Fallback to Unknown_Purpose if nothing found
        if not purpose:
            purpose = "Unknown_Purpose"

        # Extract subscriptions - V1 format
        sub_match = re.search(r'> Input_Streams: Postal_Hub\[([^\]]+)\]', directive_text)
        subscriptions = sub_match.group(1).split(" ^ ") if sub_match else []

        # V2 format: > Subscribe: lines
        if not subscriptions:
            sub_section = re.search(r'> Subscribe:\s*\n((?:\s*-\s*[^\n]+\n?)+)', directive_text)
            if sub_section:
                subscriptions = re.findall(r'-\s*(\w+(?:\.\w+)*)', sub_section.group(1))

        # Extract outputs - V1 format
        out_match = re.search(r'> Output_Channels: Postal_Routes\[([^\]]+)\]', directive_text)
        outputs = out_match.group(1).split(" ^ ") if out_match else []

        # V2 format: > Publish: lines
        if not outputs:
            pub_section = re.search(r'> Publish:\s*\n((?:\s*-\s*[^\n]+\n?)+)', directive_text)
            if pub_section:
                outputs = re.findall(r'-\s*(\w+(?:\.\w+)*)', pub_section.group(1))

        # Extract siblings - V1 format
        sib_match = re.search(r'> Siblings: ([^\n]+)', directive_text)
        siblings = sib_match.group(1).strip().split(" ^ ") if sib_match else []

        # V2 format: > Peer_Links: [...]
        if not siblings:
            peer_match = re.search(r'> Peer_Links:\s*\[(.*?)\]', directive_text, re.DOTALL)
            if peer_match:
                siblings = re.findall(r'(\w+Fairy)', peer_match.group(1))

        # Extract concepts learned
        learn_match = re.search(r'> Learn: Curriculum\[([^\]]+)\]', directive_text)
        if learn_match:
            learn_str = learn_match.group(1)
            learn_str = re.sub(r'\s*\^\s*Mastery_\d+', '', learn_str)
            concepts_learned = [c.strip() for c in learn_str.split(" ^ ") if c.strip() and c.strip() != "Learning"]
        else:
            concepts_learned = []

        return cls(
            actor_name=actor_name,
            plane=plane,
            purpose=purpose,
            subscriptions=subscriptions,
            outputs=outputs,
            siblings=siblings,
            concepts_learned=concepts_learned,
            mastery=mastery,
            beat_divisor=beat_divisor,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def load_directive(name: str) -> Dict[str, Any]:
    """
    Load a directive ring by fairy name.

    Args:
        name: Fairy name (e.g., "UnconsciousMindFairy")

    Returns:
        Dict with directive ring data
    """
    result = {
        "name": name,
        "found": False,
        "timestamp": datetime.now().isoformat(),
    }

    if not DIRECTIVES_DIR or not DIRECTIVES_DIR.exists():
        result["error"] = "V1 directives directory not found"
        return result

    # Try to load .directive file
    directive_path = DIRECTIVES_DIR / f"{name}.directive"
    if not directive_path.exists():
        result["error"] = f"Directive not found: {name}.directive"
        return result

    try:
        text = directive_path.read_text(encoding="utf-8")
        ring = DirectiveRing.parse(text)
        result["found"] = True
        result["directive"] = ring.to_dict()
        result["raw_text"] = text
        result["plane_info"] = PLANE_METAPHYSICS.get(ring.plane, {})
    except Exception as e:
        result["error"] = str(e)

    return result


def list_directives() -> Dict[str, Any]:
    """
    List all available directive rings.

    Returns:
        Dict with list of directives grouped by plane
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "directives": [],
        "by_plane": {},
    }

    if not DIRECTIVES_DIR or not DIRECTIVES_DIR.exists():
        result["error"] = "V1 directives directory not found"
        return result

    try:
        for filepath in DIRECTIVES_DIR.glob("*.directive"):
            try:
                text = filepath.read_text(encoding="utf-8")
                ring = DirectiveRing.parse(text)

                info = {
                    "name": ring.actor_name,
                    "plane": ring.plane,
                    "purpose": ring.purpose[:50],
                    "mastery": ring.mastery,
                    "beat_divisor": ring.beat_divisor,
                }
                result["directives"].append(info)

                # Group by plane
                if ring.plane not in result["by_plane"]:
                    result["by_plane"][ring.plane] = []
                result["by_plane"][ring.plane].append(ring.actor_name)

            except Exception:
                continue

        result["count"] = len(result["directives"])

    except Exception as e:
        result["error"] = str(e)

    return result


def get_current_directive() -> Dict[str, Any]:
    """
    Get the current/active directive for UnconsciousMindFairy.

    This is the "soul" of the system - its identity and purpose.
    """
    result = load_directive("UnconsciousMindFairy")

    if result.get("found"):
        # Add interpretation
        directive = result["directive"]
        result["interpretation"] = {
            "identity": f"{directive['actor_name']} on Plane {directive['plane']}",
            "purpose": directive["purpose"],
            "listens_to": len(directive["subscriptions"]),
            "speaks_to": len(directive["outputs"]),
            "evolution": f"Mastery {directive['mastery']} with {len(directive['concepts_learned'])} concepts",
            "heartbeat": f"Every {directive['beat_divisor']} beats",
        }

    return result


def get_wiring_from_directives() -> Dict[str, Any]:
    """
    Extract postal wiring (subscriptions/outputs) from all directives.

    Returns a map of who listens to what and who speaks to what.
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "subscriptions": {},  # topic -> [fairies]
        "outputs": {},  # topic -> [fairies]
    }

    if not DIRECTIVES_DIR or not DIRECTIVES_DIR.exists():
        result["error"] = "V1 directives directory not found"
        return result

    try:
        for filepath in DIRECTIVES_DIR.glob("*.directive"):
            try:
                text = filepath.read_text(encoding="utf-8")
                ring = DirectiveRing.parse(text)

                # Track subscriptions
                for sub in ring.subscriptions:
                    if sub not in result["subscriptions"]:
                        result["subscriptions"][sub] = []
                    result["subscriptions"][sub].append(ring.actor_name)

                # Track outputs
                for out in ring.outputs:
                    if out not in result["outputs"]:
                        result["outputs"][out] = []
                    result["outputs"][out].append(ring.actor_name)

            except Exception:
                continue

        result["subscription_count"] = len(result["subscriptions"])
        result["output_count"] = len(result["outputs"])

    except Exception as e:
        result["error"] = str(e)

    return result


def get_plane_fairies(plane: str) -> Dict[str, Any]:
    """
    Get all fairies in a specific plane.

    Args:
        plane: Plane ID (e.g., "P30")
    """
    result = {
        "plane": plane,
        "plane_info": PLANE_METAPHYSICS.get(plane, {}),
        "fairies": [],
        "timestamp": datetime.now().isoformat(),
    }

    if not DIRECTIVES_DIR or not DIRECTIVES_DIR.exists():
        result["error"] = "V1 directives directory not found"
        return result

    try:
        for filepath in DIRECTIVES_DIR.glob("*.directive"):
            try:
                text = filepath.read_text(encoding="utf-8")
                ring = DirectiveRing.parse(text)

                if ring.plane == plane:
                    result["fairies"].append({
                        "name": ring.actor_name,
                        "purpose": ring.purpose[:50],
                        "mastery": ring.mastery,
                    })

            except Exception:
                continue

        result["count"] = len(result["fairies"])

    except Exception as e:
        result["error"] = str(e)

    return result


# =============================================================================
# REGISTRATION
# =============================================================================

def register_directive_tools(server: "MCPServer") -> None:
    """Register directive tools with MCP server."""

    @server.tool(category="directive")
    def mcp_load_directive(name: str) -> str:
        """
        Load a directive ring by fairy name.

        Args:
            name: Fairy name (e.g., "UnconsciousMindFairy")
        """
        import json
        return json.dumps(load_directive(name), indent=2)

    @server.tool(category="directive")
    def mcp_list_directives() -> str:
        """List all available directive rings."""
        import json
        return json.dumps(list_directives(), indent=2)

    @server.tool(category="directive")
    def mcp_current_directive() -> str:
        """Get the current/active directive for UnconsciousMindFairy."""
        import json
        return json.dumps(get_current_directive(), indent=2)

    @server.tool(category="directive")
    def mcp_directive_wiring() -> str:
        """Extract postal wiring from all directives."""
        import json
        return json.dumps(get_wiring_from_directives(), indent=2)

    @server.tool(category="directive")
    def mcp_plane_fairies(plane: str) -> str:
        """
        Get all fairies in a specific plane.

        Args:
            plane: Plane ID (e.g., "P30", "P00", "P10")
        """
        import json
        return json.dumps(get_plane_fairies(plane), indent=2)
