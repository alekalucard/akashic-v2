# ═══════════════════════════════════════════════════════════════════════════════
# CITIZEN REGISTRY - Digital Identity System for Fairies
# ═══════════════════════════════════════════════════════════════════════════════
#
# Every fairy is a citizen of the Akashic Foundation.
# The Registry tracks their identity, capabilities, history, and relationships.
#
# This is the foundation for giving fairies real digital identity
# (email, accounts, presence on the internet).
#
# ═══════════════════════════════════════════════════════════════════════════════

import time
import json
import threading
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set
from enum import Enum

class CitizenStatus(Enum):
    ACTIVE = "active"
    DORMANT = "dormant"
    INCUBATING = "incubating"
    RETIRED = "retired"
    SHADOW = "shadow"

class CitizenRole(Enum):
    FAIRY = "fairy"
    SHADOW = "shadow"
    AGENT = "agent"  # Ephemeral
    SYSTEM = "system"
    HUMAN = "human"

@dataclass
class Capability:
    """A capability a citizen has"""
    name: str
    level: float = 1.0  # 0-1 proficiency
    acquired_at: float = field(default_factory=time.time)
    description: str = ""

@dataclass
class Relationship:
    """A relationship between citizens"""
    target_id: str
    relationship_type: str  # "collaborator", "supervisor", "shadow_of", "created_by"
    strength: float = 0.5  # 0-1
    established_at: float = field(default_factory=time.time)
    notes: str = ""

@dataclass
class Credential:
    """External credential/identity"""
    service: str  # "email", "github", "forum", etc.
    identifier: str  # email address, username, etc.
    created_at: float = field(default_factory=time.time)
    verified: bool = False
    metadata: Dict = field(default_factory=dict)

@dataclass
class Citizen:
    """A registered citizen of the Akashic Foundation"""

    # Core Identity
    id: str
    name: str
    display_name: str
    role: CitizenRole = CitizenRole.FAIRY
    status: CitizenStatus = CitizenStatus.ACTIVE

    # Location
    plane: str = "P30"  # Primary plane (P00-P60)
    home_node: str = ""  # Which node they primarily live on

    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    # Description
    purpose: str = ""
    philosophy: str = ""
    bio: str = ""

    # Capabilities
    capabilities: List[Capability] = field(default_factory=list)

    # Relationships
    relationships: List[Relationship] = field(default_factory=list)

    # External Identity
    credentials: List[Credential] = field(default_factory=list)

    # Stats
    actions_taken: int = 0
    thoughts_generated: int = 0
    memories_created: int = 0

    # Metadata
    tags: Set[str] = field(default_factory=set)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['role'] = self.role.value
        d['status'] = self.status.value
        d['tags'] = list(self.tags)
        return d

    def get_email(self) -> Optional[str]:
        """Get primary email if registered"""
        for cred in self.credentials:
            if cred.service == "email":
                return cred.identifier
        return None

    def add_capability(self, name: str, level: float = 1.0, description: str = ""):
        self.capabilities.append(Capability(name=name, level=level, description=description))

    def add_relationship(self, target_id: str, rel_type: str, strength: float = 0.5):
        self.relationships.append(Relationship(
            target_id=target_id,
            relationship_type=rel_type,
            strength=strength
        ))

    def register_credential(self, service: str, identifier: str, verified: bool = False):
        self.credentials.append(Credential(
            service=service,
            identifier=identifier,
            verified=verified
        ))


class CitizenRegistry:
    """
    The Akashic Citizen Registry.

    Tracks all digital citizens:
    - Fairies (permanent residents)
    - Shadows (observers and evolver)
    - Agents (ephemeral workers)
    - Humans (collaborators)

    Provides:
    - Identity management
    - Capability tracking
    - Relationship mapping
    - External credential management (email, accounts)
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = Path(storage_path or "P10_Memory/registry")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()

        # All citizens by ID
        self.citizens: Dict[str, Citizen] = {}

        # Indices
        self.by_name: Dict[str, str] = {}  # name -> id
        self.by_role: Dict[str, List[str]] = {}
        self.by_status: Dict[str, List[str]] = {}
        self.by_plane: Dict[str, List[str]] = {}
        self.by_capability: Dict[str, List[str]] = {}

        # Load existing
        self._load()

    def _load(self):
        """Load existing registry"""
        registry_file = self.storage_path / "citizens.json"

        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    data = json.load(f)
                    for c in data:
                        # Convert enums and complex types
                        c['role'] = CitizenRole(c['role'])
                        c['status'] = CitizenStatus(c['status'])
                        c['tags'] = set(c.get('tags', []))
                        c['capabilities'] = [Capability(**cap) for cap in c.get('capabilities', [])]
                        c['relationships'] = [Relationship(**rel) for rel in c.get('relationships', [])]
                        c['credentials'] = [Credential(**cred) for cred in c.get('credentials', [])]

                        citizen = Citizen(**c)
                        self.citizens[citizen.id] = citizen
                        self._index_citizen(citizen)
            except Exception as e:
                print(f"[Registry] Error loading: {e}")

    def _save(self):
        """Save registry to storage"""
        registry_file = self.storage_path / "citizens.json"

        with open(registry_file, 'w') as f:
            json.dump([c.to_dict() for c in self.citizens.values()], f, indent=2)

    def _index_citizen(self, citizen: Citizen):
        """Add citizen to indices"""
        self.by_name[citizen.name.lower()] = citizen.id
        self.by_role.setdefault(citizen.role.value, []).append(citizen.id)
        self.by_status.setdefault(citizen.status.value, []).append(citizen.id)
        self.by_plane.setdefault(citizen.plane, []).append(citizen.id)
        for cap in citizen.capabilities:
            self.by_capability.setdefault(cap.name.lower(), []).append(citizen.id)

    # ═══ Registration ═══

    def register(
        self,
        name: str,
        role: CitizenRole = CitizenRole.FAIRY,
        plane: str = "P30",
        purpose: str = "",
        philosophy: str = "",
        capabilities: List[str] = None,
        home_node: str = ""
    ) -> Citizen:
        """Register a new citizen"""
        citizen_id = str(uuid.uuid4())

        citizen = Citizen(
            id=citizen_id,
            name=name,
            display_name=name.replace("Fairy", "").replace("_", " ").strip(),
            role=role,
            status=CitizenStatus.ACTIVE,
            plane=plane,
            purpose=purpose,
            philosophy=philosophy,
            home_node=home_node
        )

        # Add capabilities
        for cap in (capabilities or []):
            citizen.add_capability(cap)

        with self._lock:
            self.citizens[citizen_id] = citizen
            self._index_citizen(citizen)
            self._save()

        return citizen

    def register_from_fairy(self, fairy, home_node: str = "") -> Citizen:
        """Register a citizen from an existing fairy object"""
        name = getattr(fairy, 'name', str(fairy))

        # Try to determine plane from name
        plane = "P30"  # Default to cognition
        name_lower = name.lower()
        if any(x in name_lower for x in ['memory', 'srm', 'helix', 'librarian']):
            plane = 'P10'
        elif any(x in name_lower for x in ['somatic', 'chemistry', 'body']):
            plane = 'P20'
        elif any(x in name_lower for x in ['sensory', 'vision', 'audio']):
            plane = 'P40'
        elif any(x in name_lower for x in ['persona', 'identity']):
            plane = 'P50'
        elif any(x in name_lower for x in ['executive', 'mission', 'decision']):
            plane = 'P60'
        elif any(x in name_lower for x in ['autonomic', 'nervous', 'heartbeat']):
            plane = 'P00'

        # Detect capabilities from fairy attributes
        capabilities = []
        if hasattr(fairy, 'think'):
            capabilities.append('thinking')
        if hasattr(fairy, 'pulse'):
            capabilities.append('pulse')
        if hasattr(fairy, 'observe'):
            capabilities.append('observation')
        if hasattr(fairy, 'reflect'):
            capabilities.append('reflection')
        if hasattr(fairy, 'post'):
            capabilities.append('communication')
        if hasattr(fairy, 'spawn_agent'):
            capabilities.append('agent_spawning')
        if hasattr(fairy, 'remember'):
            capabilities.append('memory_access')

        # Check if shadow
        role = CitizenRole.SHADOW if 'shadow' in name_lower else CitizenRole.FAIRY

        return self.register(
            name=name,
            role=role,
            plane=plane,
            capabilities=capabilities,
            home_node=home_node
        )

    def register_all_fairies(self, node, home_node: str = "") -> int:
        """Register all fairies from a node"""
        count = 0
        for name, fairy in node.fairies.items():
            if name.lower() not in self.by_name:
                self.register_from_fairy(fairy, home_node)
                count += 1
        return count

    # ═══ Lookup ═══

    def get(self, citizen_id: str) -> Optional[Citizen]:
        """Get citizen by ID"""
        return self.citizens.get(citizen_id)

    def get_by_name(self, name: str) -> Optional[Citizen]:
        """Get citizen by name"""
        citizen_id = self.by_name.get(name.lower())
        if citizen_id:
            return self.citizens.get(citizen_id)
        return None

    def get_by_role(self, role: CitizenRole) -> List[Citizen]:
        """Get all citizens with a role"""
        ids = self.by_role.get(role.value, [])
        return [self.citizens[cid] for cid in ids if cid in self.citizens]

    def get_by_plane(self, plane: str) -> List[Citizen]:
        """Get all citizens in a plane"""
        ids = self.by_plane.get(plane, [])
        return [self.citizens[cid] for cid in ids if cid in self.citizens]

    def get_active(self) -> List[Citizen]:
        """Get all active citizens"""
        ids = self.by_status.get(CitizenStatus.ACTIVE.value, [])
        return [self.citizens[cid] for cid in ids if cid in self.citizens]

    def get_with_capability(self, capability: str) -> List[Citizen]:
        """Get citizens with a specific capability"""
        ids = self.by_capability.get(capability.lower(), [])
        return [self.citizens[cid] for cid in ids if cid in self.citizens]

    # ═══ Updates ═══

    def update_status(self, citizen_id: str, status: CitizenStatus):
        """Update citizen status"""
        with self._lock:
            citizen = self.citizens.get(citizen_id)
            if citizen:
                old_status = citizen.status
                citizen.status = status
                # Update index
                if old_status.value in self.by_status:
                    self.by_status[old_status.value].remove(citizen_id)
                self.by_status.setdefault(status.value, []).append(citizen_id)
                self._save()

    def record_activity(self, citizen_id: str):
        """Record that a citizen was active"""
        with self._lock:
            citizen = self.citizens.get(citizen_id)
            if citizen:
                citizen.last_seen = time.time()
                citizen.actions_taken += 1

    def add_credential(self, citizen_id: str, service: str, identifier: str, verified: bool = False):
        """Add an external credential to a citizen"""
        with self._lock:
            citizen = self.citizens.get(citizen_id)
            if citizen:
                citizen.register_credential(service, identifier, verified)
                self._save()

    # ═══ Directory ═══

    def get_directory(self) -> Dict:
        """Get a directory listing for curious minds"""
        directory = {
            "total_citizens": len(self.citizens),
            "by_role": {},
            "by_plane": {},
            "active_count": len(self.get_active()),
            "citizens": []
        }

        # Count by role
        for role in CitizenRole:
            count = len(self.by_role.get(role.value, []))
            if count > 0:
                directory["by_role"][role.value] = count

        # Count by plane
        for plane in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]:
            count = len(self.by_plane.get(plane, []))
            if count > 0:
                directory["by_plane"][plane] = count

        # List all citizens
        for citizen in self.citizens.values():
            directory["citizens"].append({
                "id": citizen.id,
                "name": citizen.name,
                "display_name": citizen.display_name,
                "role": citizen.role.value,
                "status": citizen.status.value,
                "plane": citizen.plane,
                "capabilities": [c.name for c in citizen.capabilities],
                "email": citizen.get_email()
            })

        return directory

    def get_stats(self) -> Dict:
        """Get registry statistics"""
        return {
            "total": len(self.citizens),
            "by_role": {k: len(v) for k, v in self.by_role.items()},
            "by_status": {k: len(v) for k, v in self.by_status.items()},
            "by_plane": {k: len(v) for k, v in self.by_plane.items()},
            "capabilities_tracked": len(self.by_capability)
        }


# ═══ Global Instance ═══
_registry: Optional[CitizenRegistry] = None

def get_registry(storage_path: str = None) -> CitizenRegistry:
    """Get or create the global Registry instance"""
    global _registry
    if _registry is None:
        _registry = CitizenRegistry(storage_path)
    return _registry


# ═══ Flask Routes ═══

def add_registry_routes(app, registry: CitizenRegistry = None):
    """Add Registry routes to Flask app"""
    from flask import jsonify, request

    registry = registry or get_registry()

    @app.route('/registry')
    def registry_directory():
        return jsonify(registry.get_directory())

    @app.route('/registry/stats')
    def registry_stats():
        return jsonify(registry.get_stats())

    @app.route('/registry/citizen/<citizen_id>')
    def get_citizen(citizen_id):
        citizen = registry.get(citizen_id)
        if citizen:
            return jsonify(citizen.to_dict())
        return jsonify({"error": "Not found"}), 404

    @app.route('/registry/by-name/<name>')
    def get_citizen_by_name(name):
        citizen = registry.get_by_name(name)
        if citizen:
            return jsonify(citizen.to_dict())
        return jsonify({"error": "Not found"}), 404

    @app.route('/registry/by-plane/<plane>')
    def get_citizens_by_plane(plane):
        citizens = registry.get_by_plane(plane)
        return jsonify([c.to_dict() for c in citizens])

    @app.route('/registry/register', methods=['POST'])
    def register_citizen():
        data = request.json
        if 'role' in data:
            data['role'] = CitizenRole(data['role'])
        citizen = registry.register(**data)
        return jsonify(citizen.to_dict())


# Export
__all__ = [
    'CitizenRegistry',
    'Citizen',
    'CitizenRole',
    'CitizenStatus',
    'Capability',
    'Relationship',
    'Credential',
    'get_registry',
    'add_registry_routes'
]
