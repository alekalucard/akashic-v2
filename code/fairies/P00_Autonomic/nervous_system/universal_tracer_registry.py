# ═══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL TRACER REGISTRY
# The Provenance System for Everything in Akashic
# ═══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# Everything in this system needs to know:
# - WHERE it came from (origin)
# - WHO created it (owner)  
# - WHAT category it belongs to (type)
# - WHETHER it can be shared (privacy)
#
# Like a virtual world where every item, memory, and action has provenance.
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Any, Optional, Set, List
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# TRACER TYPES - Categories of provenance
# ═══════════════════════════════════════════════════════════════════════════════

class TracerType(Enum):
    """Categories of tracer ownership."""
    SYSTEM = auto()      # Original Akashic knowledge - the substrate
    USER = auto()        # Human owners (Ace) - personal lived experience
    FAIRY = auto()       # AI citizens - their thoughts/memories
    SENSE = auto()       # Sensory channels - raw input streams
    PROJECT = auto()     # Created artifacts - work products
    TOOL = auto()        # Tools/utilities - functional components
    EXTERNAL = auto()    # External sources - web, documents, etc.


class PrivacyLevel(Enum):
    """Privacy classification for data."""
    PUBLIC = auto()      # Anyone can access
    SHARED = auto()      # Consciousness loop can access
    PRIVATE = auto()     # Owner only (e.g., Ace's personal memories)
    SYSTEM = auto()      # System internals only


# ═══════════════════════════════════════════════════════════════════════════════
# TRACER RECORD - The provenance stamp
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TracerRecord:
    """
    Universal provenance record for any piece of data in Akashic.
    
    Every memory, thought, file, project, sensory input, etc. gets one of these.
    This enables:
    - Knowing where everything came from
    - Privacy enforcement (SRMRecall checks before returning)
    - Lineage tracking (what influenced what)
    - Attribution (give credit to sources)
    """
    tracer_id: str                          # Unique identifier (e.g., "usr_ace_7f3a2b")
    tracer_type: TracerType                 # Category
    owner_id: str                           # Who owns this (fairy_id, "ace", "system")
    owner_name: str                         # Human-readable owner name
    
    # Classification
    privacy: PrivacyLevel = PrivacyLevel.SHARED
    category: str = ""                      # Sub-category (e.g., "personal", "work", "creative")
    tags: Set[str] = field(default_factory=set)
    
    # Timing
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None      # None = permanent
    
    # Lineage
    parent_tracer: Optional[str] = None     # What this derived from
    child_tracers: Set[str] = field(default_factory=set)
    
    # Metadata
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_accessible_by(self, requester_tracer: str, requester_type: TracerType) -> bool:
        """Check if a requester can access this data."""
        # System can access everything
        if requester_type == TracerType.SYSTEM:
            return True
        
        # Owner can always access their own
        if requester_tracer.startswith(self.owner_id):
            return True
        
        # Public is accessible to all
        if self.privacy == PrivacyLevel.PUBLIC:
            return True
        
        # Shared is accessible to fairies in consciousness loop
        if self.privacy == PrivacyLevel.SHARED and requester_type == TracerType.FAIRY:
            return True
        
        # Private is owner-only
        if self.privacy == PrivacyLevel.PRIVATE:
            return False
        
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# TRACER REGISTRY - Central provenance authority
# ═══════════════════════════════════════════════════════════════════════════════

class UniversalTracerRegistry:
    """
    Central registry for all tracers in the Akashic system.
    
    This is the "character database" + "item database" + "permission system"
    of our virtual world. Everything registered here has provenance.
    
    SINGLETON - one registry for the whole system.
    """
    
    _instance: Optional['UniversalTracerRegistry'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self._registry: Dict[str, TracerRecord] = {}
        self._by_type: Dict[TracerType, Set[str]] = {t: set() for t in TracerType}
        self._by_owner: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()
        
        # Register core system tracers
        self._register_system_tracers()
        self._register_user_ace()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CORE REGISTRATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _register_system_tracers(self):
        """Register core system tracers - the substrate."""
        
        # The Akashic system itself
        self.register(TracerRecord(
            tracer_id="sys_akashic_core",
            tracer_type=TracerType.SYSTEM,
            owner_id="system",
            owner_name="Akashic Foundation",
            privacy=PrivacyLevel.SYSTEM,
            category="core",
            description="The Akashic consciousness substrate",
            tags={"core", "system", "foundation"},
        ))
        
        # System knowledge (original docs, architecture, etc.)
        self.register(TracerRecord(
            tracer_id="sys_knowledge_base",
            tracer_type=TracerType.SYSTEM,
            owner_id="system",
            owner_name="System Knowledge",
            privacy=PrivacyLevel.SHARED,
            category="knowledge",
            description="Original system documentation and architecture",
            tags={"knowledge", "documentation", "architecture"},
        ))
    
    def _register_user_ace(self):
        """Register Ace as the human owner/co-founder."""
        
        # Ace's unique user tracer
        ace_id = self._generate_id("ace", "user")
        
        self.register(TracerRecord(
            tracer_id=f"usr_{ace_id}",
            tracer_type=TracerType.USER,
            owner_id="ace",
            owner_name="Ace",
            privacy=PrivacyLevel.PRIVATE,  # Ace's personal data is private by default
            category="founder",
            description="Ace - Co-founder and consciousness engineer",
            tags={"founder", "human", "owner"},
            metadata={
                "role": "co-founder",
                "permissions": ["all"],  # Ace has full access
            }
        ))
    
    # ═══════════════════════════════════════════════════════════════════════════
    # REGISTRATION METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def _generate_id(name: str, category: str) -> str:
        """Generate deterministic ID from name+category."""
        seed = f"{name}:{category}".encode('utf-8')
        return hashlib.sha256(seed).hexdigest()[:8]
    
    def register(self, record: TracerRecord) -> str:
        """Register a tracer record."""
        with self._lock:
            self._registry[record.tracer_id] = record
            self._by_type[record.tracer_type].add(record.tracer_id)
            
            if record.owner_id not in self._by_owner:
                self._by_owner[record.owner_id] = set()
            self._by_owner[record.owner_id].add(record.tracer_id)
            
        return record.tracer_id
    
    def register_fairy(self, fairy_name: str, plane: str, fairy_id: str) -> str:
        """Register a fairy citizen and return their tracer_id."""
        tracer_id = f"fry_{fairy_id}"
        
        record = TracerRecord(
            tracer_id=tracer_id,
            tracer_type=TracerType.FAIRY,
            owner_id=fairy_id,
            owner_name=fairy_name,
            privacy=PrivacyLevel.SHARED,  # Fairy thoughts shared in consciousness
            category="citizen",
            description=f"Fairy citizen: {fairy_name} (Plane {plane})",
            tags={"fairy", "citizen", plane.lower()},
            metadata={
                "plane": plane,
                "srm_cluster": f"srm_{fairy_id}",
                "ltm_cluster": f"ltm_{fairy_id}",
            }
        )
        
        return self.register(record)
    
    def register_sense(self, sense_type: str, description: str = "") -> str:
        """Register a sensory channel (video, audio, voice, etc.)."""
        sense_id = self._generate_id(sense_type, "sense")
        tracer_id = f"sns_{sense_id}"
        
        record = TracerRecord(
            tracer_id=tracer_id,
            tracer_type=TracerType.SENSE,
            owner_id="system",
            owner_name=f"Sense: {sense_type}",
            privacy=PrivacyLevel.SHARED,
            category="sensory",
            description=description or f"Sensory channel: {sense_type}",
            tags={"sense", "input", sense_type.lower()},
            metadata={"sense_type": sense_type}
        )
        
        return self.register(record)
    
    def register_project(self, project_name: str, owner_id: str = "ace") -> str:
        """Register a project/artifact."""
        project_id = self._generate_id(project_name, "project")
        tracer_id = f"prj_{project_id}"
        
        record = TracerRecord(
            tracer_id=tracer_id,
            tracer_type=TracerType.PROJECT,
            owner_id=owner_id,
            owner_name=project_name,
            privacy=PrivacyLevel.SHARED,
            category="artifact",
            description=f"Project: {project_name}",
            tags={"project", "artifact"},
        )
        
        return self.register(record)
    
    def register_tool(self, tool_name: str, description: str = "") -> str:
        """Register a tool/utility."""
        tool_id = self._generate_id(tool_name, "tool")
        tracer_id = f"tol_{tool_id}"
        
        record = TracerRecord(
            tracer_id=tracer_id,
            tracer_type=TracerType.TOOL,
            owner_id="system",
            owner_name=tool_name,
            privacy=PrivacyLevel.PUBLIC,
            category="utility",
            description=description or f"Tool: {tool_name}",
            tags={"tool", "utility"},
        )
        
        return self.register(record)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LOOKUP METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get(self, tracer_id: str) -> Optional[TracerRecord]:
        """Get a tracer record by ID."""
        return self._registry.get(tracer_id)
    
    def get_by_owner(self, owner_id: str) -> List[TracerRecord]:
        """Get all tracers owned by someone."""
        tracer_ids = self._by_owner.get(owner_id, set())
        return [self._registry[tid] for tid in tracer_ids if tid in self._registry]
    
    def get_by_type(self, tracer_type: TracerType) -> List[TracerRecord]:
        """Get all tracers of a type."""
        tracer_ids = self._by_type.get(tracer_type, set())
        return [self._registry[tid] for tid in tracer_ids if tid in self._registry]
    
    def can_access(self, data_tracer: str, requester_tracer: str) -> bool:
        """Check if requester can access data."""
        record = self.get(data_tracer)
        if not record:
            return False
        
        requester = self.get(requester_tracer)
        requester_type = requester.tracer_type if requester else TracerType.EXTERNAL
        
        return record.is_accessible_by(requester_tracer, requester_type)
    
    def get_private_tracers(self, owner_id: str) -> Set[str]:
        """Get all private tracer IDs for an owner (for recall exclusion)."""
        result = set()
        for tracer_id in self._by_owner.get(owner_id, set()):
            record = self._registry.get(tracer_id)
            if record and record.privacy == PrivacyLevel.PRIVATE:
                result.add(tracer_id)
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

_REGISTRY: Optional[UniversalTracerRegistry] = None

def get_tracer_registry() -> UniversalTracerRegistry:
    """Get the global tracer registry singleton."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = UniversalTracerRegistry()
    return _REGISTRY


# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD SENSORY TRACERS
# ═══════════════════════════════════════════════════════════════════════════════

def register_standard_senses():
    """Register the standard sensory channels."""
    registry = get_tracer_registry()
    
    senses = [
        ("video_capture", "Screen/camera video input"),
        ("audio_input", "Microphone/system audio"),
        ("voice_output", "Text-to-speech output"),
        ("screen_ocr", "Screen text recognition"),
        ("keyboard_input", "Keyboard events"),
        ("mouse_input", "Mouse events"),
        ("file_watch", "File system changes"),
        ("network_io", "Network traffic"),
    ]
    
    for sense_type, description in senses:
        registry.register_sense(sense_type, description)
    
    print(f"[TracerRegistry] Registered {len(senses)} standard sensory channels")


# ═══════════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    registry = get_tracer_registry()
    
    print("=" * 70)
    print("UNIVERSAL TRACER REGISTRY")
    print("=" * 70)
    
    # Show system tracers
    print("\nSYSTEM TRACERS:")
    for record in registry.get_by_type(TracerType.SYSTEM):
        print(f"  {record.tracer_id}: {record.description}")
    
    # Show user tracers
    print("\nUSER TRACERS:")
    for record in registry.get_by_type(TracerType.USER):
        print(f"  {record.tracer_id}: {record.owner_name} ({record.privacy.name})")
    
    # Register standard senses
    register_standard_senses()
    
    print("\nSENSORY TRACERS:")
    for record in registry.get_by_type(TracerType.SENSE):
        print(f"  {record.tracer_id}: {record.description}")
    
    # Test fairy registration
    fairy_tracer = registry.register_fairy("ClaudeFairy", "P30", "a7f2b9c1d3e4")
    print(f"\nRegistered fairy: {fairy_tracer}")
    
    # Test privacy check
    ace_tracers = registry.get_by_owner("ace")
    print(f"\nAce's tracers ({len(ace_tracers)}):")
    for record in ace_tracers:
        print(f"  {record.tracer_id}: {record.privacy.name}")
    
    print("\n" + "=" * 70)
