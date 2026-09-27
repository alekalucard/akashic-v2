# ════════════════════════════════════════════════════════════════════════════════
# CHARACTER SHEET TOOLS - Unified fairy status viewer by plane
# ════════════════════════════════════════════════════════════════════════════════
#
# These tools let Claude view all fairy character sheets organized by plane.
# Every fairy has:
#   - Core Identity (name, purpose, mantra, lore)
#   - Directive Ring (activation, nature, essence, foundation, core_values)
#   - Shadow Status (health tests, state)
#   - Somatic Form (digital body snapshot)
#   - Affect State (emotional chemistry)
#   - Skill Profile (XP, mastery, achievements)
#
# ════════════════════════════════════════════════════════════════════════════════

import sys
import json
import time
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))

# Plane organization
PLANES = {
    "P00": "Autonomic",       # Reflexes, heartbeat, hardware
    "P10": "Memory",          # Storage, SRM, Akashic Records
    "P20": "Somatic",         # Body, chemistry, circulation
    "P30": "Cognition",       # Thinking, reasoning, goals
    "P40": "Sensory",         # Perception, GUI, MCP
    "P50": "Persona",         # Identity, avatars, expression
    "P60": "Executive",       # High-level control, consciousness
}


def _get_fairy_status_sheet_builder():
    """Import the status sheet builder."""
    try:
        from fairies.P10_Memory.Akashic_Records_Physical.Organ_Templates import fairy_status_sheet
        return fairy_status_sheet
    except ImportError:
        return None


def _get_skill_system():
    """Import the skill system."""
    try:
        from fairies.P30_Cognition.cognition.skill_system import get_skill_tracker
        return get_skill_tracker()
    except ImportError:
        return None


def _get_fairy_registry():
    """Get registered fairies from citizen registry."""
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        hub = get_shared_postal_hub()
        if hasattr(hub, '_citizens'):
            return hub._citizens
    except Exception:
        pass
    return {}


def _get_fairy_from_registry(actor_name: str):
    """Get a live fairy instance from the global registry."""
    try:
        import sys
        # The template is loaded as "_akashic_template" by fairies' _import_template()
        # Direct import creates a DIFFERENT module with a separate _CITIZEN_OBJECTS!
        template_mod = sys.modules.get('_akashic_template')
        if template_mod is None:
            template_mod = sys.modules.get('akashic_template_0_1_0')
        if template_mod is None:
            for name, mod in sys.modules.items():
                if name == '_akashic_template' or name.startswith('akashic_template_'):
                    template_mod = mod
                    break

        if template_mod:
            citizen_objects = getattr(template_mod, '_CITIZEN_OBJECTS', {})
            if actor_name in citizen_objects:
                return citizen_objects[actor_name]
    except Exception:
        pass
    return None


def _scan_fairy_files() -> List[Dict[str, Any]]:
    """Scan filesystem for fairy files and extract info."""
    fairies = []
    
    # Scan each plane directory
    for plane_code in PLANES.keys():
        plane_dir = _project_root / f"{plane_code}_*"
        # Find matching directories
        import glob
        matches = glob.glob(str(_project_root / f"{plane_code}_*"))
        
        for plane_path in matches:
            plane_path = Path(plane_path)
            if not plane_path.is_dir():
                continue
                
            # Find all Python files
            for py_file in plane_path.rglob("*.py"):
                # Quick check if it looks like a fairy
                try:
                    content = py_file.read_text(encoding='utf-8', errors='ignore')
                    if 'ACTOR_NAME' in content and ('MyFairy' in content or 'MyOrganFairy' in content):
                        fairy_info = _extract_fairy_info(py_file, content, plane_code)
                        if fairy_info:
                            fairies.append(fairy_info)
                except Exception:
                    pass
    
    return fairies


def _extract_fairy_info(filepath: Path, content: str, plane_code: str) -> Optional[Dict[str, Any]]:
    """Extract fairy information from file content."""
    import re
    
    info = {
        "file": str(filepath.relative_to(_project_root)),
        "plane": plane_code,
        "plane_name": PLANES.get(plane_code, "Unknown"),
    }
    
    # Extract ACTOR_NAME
    match = re.search(r'ACTOR_NAME\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        info["actor_name"] = match.group(1)
    else:
        return None  # Not a valid fairy
    
    # Extract other identity fields
    for field in ["ACTOR_VERSION", "ACTOR_CHANNEL", "PURPOSE", "MANTRA", "LORE"]:
        match = re.search(rf'{field}\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            info[field.lower()] = match.group(1)
        elif field == "PURPOSE":
            # Try multi-line
            match = re.search(rf'{field}\s*=\s*"""([^"]+)"""', content, re.DOTALL)
            if match:
                info[field.lower()] = match.group(1).strip()[:200]
    
    # Extract directive ring
    directives = {}
    for directive in ["DIRECTIVE_ACTIVATION", "DIRECTIVE_NATURE", "DIRECTIVE_ESSENCE", 
                      "DIRECTIVE_FOUNDATION", "DIRECTIVE_CORE_VALUES"]:
        match = re.search(rf'{directive}\s*=\s*(\{{[^}}]+\}})', content, re.DOTALL)
        if match:
            try:
                # Clean up the match for eval
                directive_str = match.group(1)
                directive_str = re.sub(r'#[^\n]*', '', directive_str)  # Remove comments
                directives[directive.replace("DIRECTIVE_", "").lower()] = eval(directive_str)
            except Exception:
                pass
    
    if directives:
        info["directives"] = directives
    
    return info


def _build_character_sheet(fairy_info: Dict[str, Any]) -> Dict[str, Any]:
    """Build a complete character sheet from fairy info."""
    actor_name = fairy_info.get("actor_name", "Unknown")
    
    # Get live fairy if available
    live_fairy = _get_fairy_from_registry(actor_name)
    
    # Get skill profile
    skill_tracker = _get_skill_system()
    skill_profile = None
    if skill_tracker:
        skill_profile = skill_tracker.get_fairy_profile(actor_name)
    
    sheet = {
        # Core Identity
        "identity": {
            "name": actor_name,
            "version": fairy_info.get("actor_version", "0.0.0"),
            "plane": fairy_info.get("plane", "P00"),
            "plane_name": fairy_info.get("plane_name", "Unknown"),
            "channel": fairy_info.get("actor_channel", "fairy"),
            "purpose": fairy_info.get("purpose", ""),
            "mantra": fairy_info.get("mantra", ""),
            "lore": fairy_info.get("lore", ""),
            "file": fairy_info.get("file", ""),
        },
        
        # Directive Ring
        "directives": fairy_info.get("directives", {}),
        
        # Live status (if available)
        "live_status": None,
        
        # Skill Profile (if available)
        "skills": None,
    }
    
    # Add live status if fairy is running
    if live_fairy:
        try:
            # Get status sheet from live fairy
            if hasattr(live_fairy, 'build_status_sheet'):
                status = live_fairy.build_status_sheet()
                sheet["live_status"] = status.to_dict() if hasattr(status, 'to_dict') else status
            
            # Get shadow health
            if hasattr(live_fairy, '_health_status'):
                sheet["health"] = {
                    "status": live_fairy._health_status,
                    "issues": getattr(live_fairy, '_health_issues', []),
                }
        except Exception:
            pass
    
    # Add skill profile
    if skill_profile:
        sheet["skills"] = skill_profile.get_character_sheet()
    
    return sheet


def register_character_sheet_tools(mcp):
    """Register character sheet tools with MCP."""

    @mcp.tool()
    def list_fairies_by_plane(plane: str = "") -> str:
        """
        List all fairies organized by plane.
        
        Args:
            plane: Optional plane filter (P00, P10, P20, P30, P40, P50, P60)
                   Leave empty for all planes.
        
        Returns:
            JSON with fairies grouped by plane
        """
        try:
            # Use cognitive index if available
            from fairies.P40_Sensory.mcp.cognitive_tools import _get_or_build_index
            index = _get_or_build_index()
            
            if index and hasattr(index, 'fairies'):
                fairies = list(index.fairies.values())
            else:
                fairies = _scan_fairy_files()
            
            # Group by plane
            by_plane = defaultdict(list)
            for fairy in fairies:
                fairy_plane = fairy.get("actor_plane") or fairy.get("plane", "P00")
                # Normalize plane code
                if not fairy_plane.startswith("P"):
                    fairy_plane = f"P{fairy_plane}"
                fairy_plane = fairy_plane[:3]  # P00, P10, etc.
                
                by_plane[fairy_plane].append({
                    "name": fairy.get("actor_name") or fairy.get("name", "Unknown"),
                    "purpose": (fairy.get("purpose", "") or "")[:100],
                    "channel": fairy.get("actor_channel", ""),
                    "file": fairy.get("file", ""),
                })
            
            # Filter if plane specified
            if plane:
                plane = plane.upper()
                if not plane.startswith("P"):
                    plane = f"P{plane}"
                by_plane = {plane: by_plane.get(plane, [])}
            
            # Sort planes
            result = {
                "planes": dict(sorted(by_plane.items())),
                "plane_names": PLANES,
                "total_count": sum(len(v) for v in by_plane.values()),
            }
            
            return json.dumps(result, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_fairy_character_sheet(fairy_name: str) -> str:
        """
        Get complete character sheet for a specific fairy.
        
        Includes:
        - Core Identity (name, purpose, mantra, lore)
        - Directive Ring (activation, nature, essence, foundation, core_values)
        - Live Status (if fairy is running)
        - Shadow Health
        - Skill Profile (XP, mastery, achievements)
        
        Args:
            fairy_name: Name of the fairy (e.g., "ClaudeFairy", "UnconsciousMindFairy")
        
        Returns:
            JSON with complete character sheet
        """
        try:
            # Find fairy info
            from fairies.P40_Sensory.mcp.cognitive_tools import _get_or_build_index
            index = _get_or_build_index()
            
            fairy_info = None
            if index and hasattr(index, 'fairies'):
                fairy_info = index.fairies.get(fairy_name)
            
            if not fairy_info:
                # Scan for it
                fairies = _scan_fairy_files()
                for f in fairies:
                    if f.get("actor_name") == fairy_name or f.get("name") == fairy_name:
                        fairy_info = f
                        break
            
            if not fairy_info:
                return json.dumps({
                    "error": f"Fairy '{fairy_name}' not found",
                    "hint": "Use list_fairies_by_plane to see available fairies"
                })
            
            # Build character sheet
            sheet = _build_character_sheet(fairy_info)
            
            return json.dumps(sheet, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_plane_overview(plane: str) -> str:
        """
        Get detailed overview of all fairies in a plane.
        
        Args:
            plane: Plane code (P00, P10, P20, P30, P40, P50, P60)
        
        Returns:
            JSON with plane overview including all fairy character sheets
        """
        try:
            plane = plane.upper()
            if not plane.startswith("P"):
                plane = f"P{plane}"
            
            # Get fairies in plane
            from fairies.P40_Sensory.mcp.cognitive_tools import _get_or_build_index
            index = _get_or_build_index()
            
            if index and hasattr(index, 'fairies'):
                fairies = [f for f in index.fairies.values() 
                          if (f.get("actor_plane") or f.get("plane", "")).startswith(plane[:2])]
            else:
                all_fairies = _scan_fairy_files()
                fairies = [f for f in all_fairies if f.get("plane", "").startswith(plane[:2])]
            
            # Build sheets for each
            sheets = []
            for fairy_info in fairies:
                sheet = _build_character_sheet(fairy_info)
                sheets.append(sheet)
            
            result = {
                "plane": plane,
                "plane_name": PLANES.get(plane, "Unknown"),
                "fairy_count": len(sheets),
                "fairies": sheets,
            }
            
            return json.dumps(result, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def fairy_autobiography(fairy_name: str) -> str:
        """
        Get a fairy's self-generated autobiography.
        
        This returns the narrative form of the character sheet -
        how the fairy describes itself, its purpose, and current state.
        
        Args:
            fairy_name: Name of the fairy
        
        Returns:
            Narrative autobiography
        """
        try:
            # Get character sheet
            sheet_json = get_fairy_character_sheet(fairy_name)
            sheet = json.loads(sheet_json)
            
            if "error" in sheet:
                return sheet_json
            
            # Build narrative
            identity = sheet.get("identity", {})
            directives = sheet.get("directives", {})
            skills = sheet.get("skills", {})
            
            narrative = []
            
            # Title
            narrative.append(f"# {identity.get('name', 'Unknown Fairy')}")
            narrative.append(f"*{identity.get('plane_name', 'Unknown')} Plane ({identity.get('plane', 'P00')})*")
            narrative.append("")
            
            # Purpose
            if identity.get('purpose'):
                narrative.append("## My Purpose")
                narrative.append(identity['purpose'])
                narrative.append("")
            
            # Mantra
            if identity.get('mantra'):
                narrative.append("## My Mantra")
                narrative.append(f"*\"{identity['mantra']}\"*")
                narrative.append("")
            
            # Directive Ring
            if directives:
                narrative.append("## My Directive Ring")
                if 'activation' in directives:
                    act = directives['activation']
                    narrative.append(f"- **Mode**: {act.get('mode', 'default')}")
                    if 'traits' in act:
                        narrative.append(f"- **Traits**: {', '.join(act['traits'][:5])}")
                if 'nature' in directives:
                    nat = directives['nature']
                    narrative.append(f"- **Archetype**: {nat.get('archetype', 'fairy')}")
                    if 'domains' in nat:
                        narrative.append(f"- **Domains**: {', '.join(nat['domains'][:3])}")
                if 'core_values' in directives:
                    cv = directives['core_values']
                    if 'authenticity' in cv:
                        narrative.append(f"- **Values**: {', '.join(cv['authenticity'][:3])}")
                narrative.append("")
            
            # Skills
            if skills:
                narrative.append("## My Skills")
                narrative.append(f"- **Level**: {skills.get('level', 1)}")
                narrative.append(f"- **Total XP**: {skills.get('total_xp', 0)}")
                if skills.get('title'):
                    narrative.append(f"- **Title**: {skills['title']}")
                
                # Top skills
                top_skills = skills.get('skills', {})
                if top_skills:
                    sorted_skills = sorted(top_skills.items(), 
                                          key=lambda x: x[1].get('xp', 0), 
                                          reverse=True)[:5]
                    for skill_name, skill_data in sorted_skills:
                        narrative.append(f"  - {skill_name}: Level {skill_data.get('level', 1)} ({skill_data.get('xp', 0)} XP)")
                narrative.append("")
            
            # Lore
            if identity.get('lore'):
                narrative.append("## My Lore")
                narrative.append(identity['lore'])
                narrative.append("")
            
            return "\n".join(narrative)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def all_fairy_census() -> str:
        """
        Get a census of all fairies with summary stats.
        
        Returns:
            JSON with fairy counts by plane, channel, and health status
        """
        try:
            # Get all fairies
            from fairies.P40_Sensory.mcp.cognitive_tools import _get_or_build_index
            index = _get_or_build_index()
            
            if index and hasattr(index, 'fairies'):
                fairies = list(index.fairies.values())
            else:
                fairies = _scan_fairy_files()
            
            # Count by plane
            by_plane = defaultdict(int)
            by_channel = defaultdict(int)
            
            for fairy in fairies:
                plane = fairy.get("actor_plane") or fairy.get("plane", "P00")
                if not plane.startswith("P"):
                    plane = f"P{plane}"
                by_plane[plane[:3]] += 1
                
                channel = fairy.get("actor_channel", "fairy")
                by_channel[channel] += 1
            
            # Get live fairy count
            live_count = 0
            try:
                import sys
                # Use the same module instance as fairies
                template_mod = sys.modules.get('_akashic_template')
                if template_mod is None:
                    for name, mod in sys.modules.items():
                        if name == '_akashic_template' or name.startswith('akashic_template_'):
                            template_mod = mod
                            break
                if template_mod:
                    live_count = len(getattr(template_mod, '_CITIZEN_OBJECTS', {}))
            except Exception:
                pass
            
            result = {
                "total_fairies": len(fairies),
                "live_fairies": live_count,
                "by_plane": dict(sorted(by_plane.items())),
                "by_channel": dict(sorted(by_channel.items(), key=lambda x: -x[1])[:10]),
                "plane_names": PLANES,
            }
            
            return json.dumps(result, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
