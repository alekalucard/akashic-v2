# ═══════════════════════════════════════════════════════════════════════════════
# FORUM USER DIRECTORY - Living Fairy Status Sheets
# ═══════════════════════════════════════════════════════════════════════════════
#
# The Forum becomes the living directory of all citizens.
# Each fairy has a status sheet - their profile in the Akashic Foundation.
#
# Sources:
#   - ebook system (P10_Memory/Akashic_Records_Physical/Organ_Templates)
#   - Whisper Core (if available)
#   - Live satellite data
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import sys
import time
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime

@dataclass
class FairyStatusSheet:
    """
    A fairy's profile in the Forum.
    The Akashic Sheet for each citizen.
    """
    # ═══ IDENTITY ═══
    name: str
    display_name: str = ""
    role: str = "fairy"  # fairy, shadow, agent, system
    plane: str = "P30"
    
    # ═══ PURPOSE ═══
    purpose: str = ""
    philosophy: str = ""
    mantra: str = ""
    
    # ═══ CAPABILITIES ═══
    capabilities: List[str] = field(default_factory=list)
    topics_pub: List[str] = field(default_factory=list)
    topics_sub: List[str] = field(default_factory=list)
    
    # ═══ CURRENT STATE ═══
    status: str = "unknown"  # active, dormant, incubating, error
    energy: float = 1.0
    stress: float = 0.0
    
    # Chemistry (if available)
    chemistry: Dict[str, float] = field(default_factory=dict)
    somatic: Dict[str, float] = field(default_factory=dict)
    
    # ═══ ACTIVITY ═══
    pulse_count: int = 0
    thought_count: int = 0
    observation_count: int = 0
    reflection_count: int = 0
    last_pulse: float = 0
    last_thought: str = ""
    
    # ═══ RELATIONSHIPS ═══
    collaborators: List[str] = field(default_factory=list)
    supervised_by: str = ""
    supervises: List[str] = field(default_factory=list)
    
    # ═══ LOCATION ═══
    home_node: str = ""  # satellite, windows, etc.
    source_file: str = ""
    
    # ═══ CREDENTIALS ═══
    email: str = ""
    forum_username: str = ""
    
    # ═══ METADATA ═══
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_forum_post(self) -> str:
        """Generate BBCode-style forum post for this fairy"""
        status_color = {
            "active": "green",
            "dormant": "gray",
            "incubating": "yellow",
            "error": "red",
            "unknown": "gray"
        }.get(self.status, "gray")
        
        post = f"""[header]{self.display_name or self.name}[/header]
[status color="{status_color}"]{self.status.upper()}[/status]

[section title="Identity"]
[b]Role:[/b] {self.role.title()}
[b]Plane:[/b] {self.plane}
[b]Home:[/b] {self.home_node or "Unknown"}
[/section]

[section title="Purpose"]
{self.purpose or "No purpose defined."}

[i]"{self.mantra or self.philosophy or "..."}"[/i]
[/section]

[section title="Capabilities"]
{', '.join(self.capabilities) if self.capabilities else "None documented"}
[/section]

[section title="Current State"]
[meter label="Energy" value="{self.energy}" max="1.0"]
[meter label="Stress" value="{self.stress}" max="1.0"]

[b]Pulses:[/b] {self.pulse_count}
[b]Thoughts:[/b] {self.thought_count}
[b]Last Active:[/b] {datetime.fromtimestamp(self.last_pulse).strftime('%Y-%m-%d %H:%M:%S') if self.last_pulse else 'Never'}
[/section]
"""
        
        if self.chemistry:
            chem_lines = [f"[b]{k}:[/b] {v:.2f}" for k, v in self.chemistry.items()]
            post += f"""
[section title="Chemistry"]
{chr(10).join(chem_lines)}
[/section]
"""
        
        if self.collaborators:
            post += f"""
[section title="Relationships"]
[b]Collaborators:[/b] {', '.join(self.collaborators)}
[/section]
"""
        
        if self.last_thought:
            post += f"""
[section title="Latest Thought"]
[quote]{self.last_thought}[/quote]
[/section]
"""
        
        post += f"""
[footer]
Updated: {datetime.fromtimestamp(self.updated_at).strftime('%Y-%m-%d %H:%M:%S')}
Source: {self.source_file or 'Unknown'}
[/footer]
"""
        return post


class ForumUserDirectory:
    """
    The living directory of all Akashic citizens.
    
    Aggregates from:
    - Local ebook fairy files
    - Whisper Core Akashic Records
    - Live satellite data
    
    Presents through the Forum as user profiles.
    """
    
    def __init__(self, 
                 ebook_root: str = "E:/coding projects/ebook",
                 whisper_root: str = None,
                 satellite_url: str = "http://192.168.1.24:5000"):
        
        self.ebook_root = Path(ebook_root)
        self.whisper_root = Path(whisper_root) if whisper_root else None
        self.satellite_url = satellite_url
        
        # All sheets indexed by name
        self.sheets: Dict[str, FairyStatusSheet] = {}
        
        # Sources
        self.sources: Dict[str, str] = {}  # name -> source
        
    # ═══ SCANNING SOURCES ═══
    
    def scan_ebook_fairies(self) -> int:
        """Scan ebook system for fairies"""
        count = 0
        
        # Scan plane directories
        for plane in ["P00_Autonomic", "P10_Memory", "P20_Somatic", 
                      "P30_Cognition", "P40_Sensory", "P50_Persona", "P60_Executive"]:
            plane_dir = self.ebook_root / plane
            if plane_dir.exists():
                for filepath in plane_dir.rglob("*fairy*.py"):
                    sheet = self._parse_fairy_file(filepath)
                    if sheet:
                        sheet.plane = plane.split("_")[0]
                        sheet.home_node = "ebook"
                        self.sheets[sheet.name] = sheet
                        self.sources[sheet.name] = "ebook"
                        count += 1
        
        # Scan sandbox fairies
        sandbox = self.ebook_root / "sandbox"
        if sandbox.exists():
            for filepath in sandbox.rglob("*fairy*.py"):
                sheet = self._parse_fairy_file(filepath)
                if sheet:
                    sheet.home_node = "sandbox"
                    self.sheets[sheet.name] = sheet
                    self.sources[sheet.name] = "sandbox"
                    count += 1
        
        return count
    
    def scan_whisper_core(self) -> int:
        """Scan Whisper Core Akashic Records"""
        if not self.whisper_root:
            return 0
        
        count = 0
        akashic_records = self.whisper_root / "Akashic_Records"
        
        if akashic_records.exists():
            for filepath in akashic_records.rglob("*fairy*.py"):
                sheet = self._parse_fairy_file(filepath)
                if sheet:
                    sheet.home_node = "whisper_core"
                    # Don't overwrite ebook version if exists
                    if sheet.name not in self.sheets:
                        self.sheets[sheet.name] = sheet
                        self.sources[sheet.name] = "whisper_core"
                        count += 1
        
        return count
    
    def fetch_satellite_data(self) -> int:
        """Fetch live data from satellite"""
        import requests
        
        count = 0
        
        try:
            r = requests.get(f"{self.satellite_url}/fairies", timeout=10)
            if r.status_code == 200:
                data = r.json()
                
                # Get list of fairies
                fairy_names = data.get('fairies', [])
                details = data.get('details', {})
                
                for name in fairy_names:
                    detail = details.get(name, {})
                    
                    # Update existing or create new
                    if name in self.sheets:
                        sheet = self.sheets[name]
                    else:
                        sheet = FairyStatusSheet(name=name)
                        self.sheets[name] = sheet
                        self.sources[name] = "satellite"
                    
                    # Update with live data
                    sheet.status = "active"
                    sheet.pulse_count = detail.get('pulse_count', 0)
                    sheet.thought_count = detail.get('thought_count', 0)
                    sheet.observation_count = detail.get('observation_count', 0)
                    sheet.reflection_count = detail.get('reflection_count', 0)
                    sheet.energy = detail.get('energy', 1.0)
                    sheet.stress = detail.get('stress', 0.0)
                    sheet.last_pulse = detail.get('last_pulse', 0)
                    sheet.home_node = "satellite"
                    sheet.updated_at = time.time()
                    
                    count += 1
                    
        except Exception as e:
            print(f"[Directory] Satellite fetch failed: {e}")
        
        return count
    
    def _parse_fairy_file(self, filepath: Path) -> Optional[FairyStatusSheet]:
        """Parse a fairy file to extract metadata"""
        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
            
            # Extract name
            name = filepath.stem
            if name.endswith('_fairy'):
                name = name[:-6]
            name = ''.join(word.title() for word in name.split('_'))
            if not name.endswith('Fairy'):
                name += 'Fairy'
            
            sheet = FairyStatusSheet(
                name=name,
                display_name=name.replace('Fairy', ' Fairy'),
                source_file=str(filepath)
            )
            
            # Extract from class attributes
            if 'PURPOSE' in content:
                import re
                match = re.search(r'PURPOSE\s*=\s*["\'](.+?)["\']', content)
                if match:
                    sheet.purpose = match.group(1)
            
            if 'MANTRA' in content:
                import re
                match = re.search(r'MANTRA\s*=\s*["\'](.+?)["\']', content)
                if match:
                    sheet.mantra = match.group(1)
            
            if 'ACTOR_PLANE' in content:
                import re
                match = re.search(r'ACTOR_PLANE\s*=\s*["\'](.+?)["\']', content)
                if match:
                    sheet.plane = match.group(1)
            
            # Detect capabilities from methods
            if 'def think(' in content:
                sheet.capabilities.append('thinking')
            if 'def pulse(' in content or 'def tick(' in content:
                sheet.capabilities.append('pulse')
            if 'def observe(' in content:
                sheet.capabilities.append('observation')
            if 'def reflect(' in content:
                sheet.capabilities.append('reflection')
            if 'def post(' in content or 'self.post' in content:
                sheet.capabilities.append('communication')
            if 'anthropic' in content.lower() or 'llm' in content.lower():
                sheet.capabilities.append('llm_connection')
            if 'hybrid' in content.lower():
                sheet.capabilities.append('hybrid_cognition')
            
            # Detect role
            if 'shadow' in name.lower():
                sheet.role = 'shadow'
            elif 'agent' in name.lower():
                sheet.role = 'agent'
            
            return sheet
            
        except Exception as e:
            return None
    
    # ═══ FULL SCAN ═══
    
    def scan_all(self) -> Dict:
        """Scan all sources and aggregate"""
        results = {
            "ebook": self.scan_ebook_fairies(),
            "whisper": self.scan_whisper_core(),
            "satellite": self.fetch_satellite_data(),
            "total": len(self.sheets)
        }
        return results
    
    # ═══ QUERIES ═══
    
    def get_sheet(self, name: str) -> Optional[FairyStatusSheet]:
        """Get a fairy's status sheet"""
        return self.sheets.get(name)
    
    def get_by_plane(self, plane: str) -> List[FairyStatusSheet]:
        """Get all fairies in a plane"""
        return [s for s in self.sheets.values() if s.plane == plane]
    
    def get_by_status(self, status: str) -> List[FairyStatusSheet]:
        """Get all fairies with a status"""
        return [s for s in self.sheets.values() if s.status == status]
    
    def get_by_capability(self, capability: str) -> List[FairyStatusSheet]:
        """Get all fairies with a capability"""
        return [s for s in self.sheets.values() if capability in s.capabilities]
    
    def get_active(self) -> List[FairyStatusSheet]:
        """Get all active fairies"""
        return self.get_by_status("active")
    
    def search(self, query: str) -> List[FairyStatusSheet]:
        """Search fairies by name, purpose, etc."""
        query_lower = query.lower()
        results = []
        
        for sheet in self.sheets.values():
            if (query_lower in sheet.name.lower() or
                query_lower in sheet.purpose.lower() or
                query_lower in sheet.mantra.lower() or
                any(query_lower in cap.lower() for cap in sheet.capabilities)):
                results.append(sheet)
        
        return results
    
    # ═══ FORUM OUTPUT ═══
    
    def generate_directory_page(self) -> str:
        """Generate Forum-ready directory page"""
        post = """[header]Akashic Citizen Directory[/header]

[section title="Overview"]
Total Citizens: {total}
Active: {active}
By Plane: {by_plane}
[/section]

[section title="Citizens"]
""".format(
            total=len(self.sheets),
            active=len(self.get_active()),
            by_plane=", ".join(f"{p}: {len(self.get_by_plane(p))}" for p in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"])
        )
        
        # Group by plane
        for plane in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]:
            fairies = self.get_by_plane(plane)
            if fairies:
                post += f"\n[subsection title=\"{plane}\"]\n"
                for sheet in sorted(fairies, key=lambda s: s.name):
                    status_icon = "" if sheet.status == "active" else "[o]"
                    post += f"{status_icon} [link=/users/{sheet.name}]{sheet.name}[/link] - {sheet.purpose[:50]}...\n"
                post += "[/subsection]\n"
        
        post += "[/section]"
        return post
    
    def get_forum_post(self, name: str) -> Optional[str]:
        """Get a fairy's Forum post"""
        sheet = self.sheets.get(name)
        if sheet:
            return sheet.to_forum_post()
        return None
    
    # ═══ EXPORT ═══
    
    def export_all(self, output_dir: str) -> int:
        """Export all sheets to JSON files"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        count = 0
        for name, sheet in self.sheets.items():
            filepath = output_path / f"{name}.json"
            with open(filepath, 'w') as f:
                json.dump(sheet.to_dict(), f, indent=2)
            count += 1
        
        return count
    
    def get_stats(self) -> Dict:
        """Get directory statistics"""
        return {
            "total": len(self.sheets),
            "by_status": {
                "active": len(self.get_by_status("active")),
                "dormant": len(self.get_by_status("dormant")),
                "unknown": len(self.get_by_status("unknown"))
            },
            "by_plane": {
                plane: len(self.get_by_plane(plane))
                for plane in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]
            },
            "by_source": {
                source: len([n for n, s in self.sources.items() if s == source])
                for source in set(self.sources.values())
            },
            "with_llm": len(self.get_by_capability("llm_connection")),
            "with_hybrid": len(self.get_by_capability("hybrid_cognition"))
        }


# ═══ FLASK ROUTES ═══

def add_directory_routes(app, directory: ForumUserDirectory):
    """Add Forum directory routes"""
    from flask import jsonify, request
    
    @app.route('/forum/users')
    def forum_users():
        return jsonify({
            "users": list(directory.sheets.keys()),
            "stats": directory.get_stats()
        })
    
    @app.route('/forum/users/<name>')
    def forum_user(name):
        sheet = directory.get_sheet(name)
        if sheet:
            return jsonify(sheet.to_dict())
        return jsonify({"error": "Not found"}), 404
    
    @app.route('/forum/users/<name>/post')
    def forum_user_post(name):
        post = directory.get_forum_post(name)
        if post:
            return jsonify({"post": post})
        return jsonify({"error": "Not found"}), 404
    
    @app.route('/forum/directory')
    def forum_directory():
        return jsonify({"page": directory.generate_directory_page()})
    
    @app.route('/forum/scan', methods=['POST'])
    def forum_scan():
        results = directory.scan_all()
        return jsonify(results)
    
    @app.route('/forum/search')
    def forum_search():
        query = request.args.get('q', '')
        results = directory.search(query)
        return jsonify([s.to_dict() for s in results])


# ═══ EXPORT ═══

__all__ = [
    'FairyStatusSheet',
    'ForumUserDirectory',
    'add_directory_routes'
]
