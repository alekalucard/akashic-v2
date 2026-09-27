# ==============================================================================
# MEMORY OWNERSHIP - Who owns what memories
# ==============================================================================
#
# Memory Ownership Model:
#   1. Human Users (like Ace) - tracked as founders/collaborators
#   2. Foundation Clusters - shared work between human + AI
#   3. Mind Ownership - personal memories for Claude, Nous, Sourpatches, etc.
#   4. System Memory - shared infrastructure all fairies can read
#
# Key Principle: Higher minds (ClaudeFairy, NousFairy, Sourpatches) have
# access to SYSTEM memory but NOT each other's PERSONAL memories.
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
#
# ==============================================================================

import time
import uuid
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Any
from enum import Enum
from pathlib import Path


# ==============================================================================
# OWNERSHIP TYPES
# ==============================================================================

class OwnershipLevel(Enum):
    """Memory ownership/access levels"""
    SYSTEM = "system"           # All fairies can read (infrastructure)
    FOUNDATION = "foundation"   # Shared human+AI foundation work
    PERSONAL = "personal"       # Private to one mind
    SHARED = "shared"           # Explicitly shared between specific minds


class UserRole(Enum):
    """Human user roles in the system"""
    FOUNDER = "founder"         # System creator (Ace)
    COLLABORATOR = "collaborator"  # Working partner
    OBSERVER = "observer"       # Read-only access
    GUEST = "guest"             # Temporary/limited


# ==============================================================================
# HUMAN USER - Tracking humans who interact with the system
# ==============================================================================

@dataclass
class HumanUser:
    """
    A human user who interacts with the Akashic system.

    Ace is the founder - all work with him gets clustered together
    under the Akashic Foundation namespace.
    """
    user_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    role: UserRole = UserRole.COLLABORATOR

    # Identity
    display_name: str = ""
    aliases: List[str] = field(default_factory=list)  # Other names they go by

    # Foundation membership
    foundation_id: Optional[str] = None  # Which foundation they belong to

    # Relationship with minds
    primary_contact: str = ""  # Which mind they mainly talk to (e.g., "ClaudeFairy")
    trusted_minds: List[str] = field(default_factory=list)  # Minds they've built relationship with

    # Activity tracking
    first_interaction: float = 0.0
    last_interaction: float = 0.0
    interaction_count: int = 0
    session_count: int = 0

    # Preferences (learned over time)
    preferences: Dict[str, Any] = field(default_factory=dict)

    # Memory cluster ID for all their interactions
    cluster_id: Optional[str] = None

    def record_interaction(self, mind_name: str = ""):
        """Record an interaction with this user"""
        now = time.time()
        if self.first_interaction == 0:
            self.first_interaction = now
        self.last_interaction = now
        self.interaction_count += 1

        if mind_name and mind_name not in self.trusted_minds:
            self.trusted_minds.append(mind_name)

    def is_founder(self) -> bool:
        return self.role == UserRole.FOUNDER

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['role'] = self.role.value
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> 'HumanUser':
        d = d.copy()
        d['role'] = UserRole(d.get('role', 'collaborator'))
        return cls(**d)


# ==============================================================================
# FOUNDATION - Shared cluster for human+AI collaborative work
# ==============================================================================

@dataclass
class Foundation:
    """
    A Foundation is a collaborative cluster between human(s) and AI mind(s).

    The Akashic Foundation is Ace + Claude's shared workspace.
    All sessions, designs, code, conversations go into this cluster
    so any fairy can access it as shared knowledge.
    """
    foundation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "Akashic Foundation"

    # Founding members
    founder_ids: List[str] = field(default_factory=list)  # Human user IDs
    founding_minds: List[str] = field(default_factory=list)  # AI mind names

    # Mission/purpose
    purpose: str = ""
    philosophy: str = ""

    # Content tracking
    memory_cluster_ids: List[str] = field(default_factory=list)  # All clusters in this foundation
    session_count: int = 0
    total_memories: int = 0

    # Timeline
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    # Access control
    public_read: bool = True  # All fairies can read foundation memories
    write_members: List[str] = field(default_factory=list)  # Who can add to foundation

    def add_cluster(self, cluster_id: str):
        """Add a memory cluster to this foundation"""
        if cluster_id not in self.memory_cluster_ids:
            self.memory_cluster_ids.append(cluster_id)
            self.last_activity = time.time()

    def record_session(self):
        """Record a new work session"""
        self.session_count += 1
        self.last_activity = time.time()

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> 'Foundation':
        return cls(**d)


# ==============================================================================
# OWNERSHIP CONTEXT - Who owns a memory and who can access it
# ==============================================================================

@dataclass
class OwnershipContext:
    """
    Ownership and access context for a memory card.

    RULES:
    - SYSTEM: All fairies can read (boot info, config, infrastructure)
    - FOUNDATION: All members can read, write_members can write
    - PERSONAL: Only owner_mind can read/write
    - SHARED: Explicitly listed minds can read/write

    Higher minds (Claude, Nous, Sourpatches) can read:
    - All SYSTEM memory
    - All FOUNDATION memory they belong to
    - Their OWN personal memory
    - NOT each other's personal memories
    """

    # Primary ownership
    level: OwnershipLevel = OwnershipLevel.SYSTEM
    owner_mind: str = ""  # For PERSONAL - which mind owns it

    # Human association
    human_user_id: Optional[str] = None  # Human involved in creating this
    foundation_id: Optional[str] = None  # Foundation this belongs to

    # Sharing (for SHARED level)
    shared_with: List[str] = field(default_factory=list)  # Mind names with access

    # Tracer tracking
    tracer_id: Optional[str] = None  # For batch processing
    batch_id: Optional[str] = None   # Which worker batch processed this

    # Creation context
    created_by: str = ""  # Mind or fairy that created it
    created_in_session: Optional[str] = None  # Session ID
    created_for_human: Optional[str] = None  # If created for a specific human

    # Access tracking
    last_accessed_by: str = ""
    access_count: int = 0

    def can_read(self, mind_name: str, is_higher_mind: bool = False) -> bool:
        """Check if a mind can read this memory"""
        if self.level == OwnershipLevel.SYSTEM:
            return True

        if self.level == OwnershipLevel.FOUNDATION:
            # Foundation is readable by all (public_read default)
            return True

        if self.level == OwnershipLevel.PERSONAL:
            return mind_name == self.owner_mind

        if self.level == OwnershipLevel.SHARED:
            return mind_name in self.shared_with or mind_name == self.owner_mind

        return False

    def can_write(self, mind_name: str) -> bool:
        """Check if a mind can modify this memory"""
        if self.level == OwnershipLevel.PERSONAL:
            return mind_name == self.owner_mind

        if self.level == OwnershipLevel.SHARED:
            return mind_name in self.shared_with or mind_name == self.owner_mind

        # SYSTEM and FOUNDATION - need specific write permission
        return False

    def record_access(self, mind_name: str):
        """Track an access"""
        self.last_accessed_by = mind_name
        self.access_count += 1

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['level'] = self.level.value
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> 'OwnershipContext':
        d = d.copy()
        d['level'] = OwnershipLevel(d.get('level', 'system'))
        return cls(**d)


# ==============================================================================
# OWNERSHIP REGISTRY - Central tracking of users, foundations, ownership
# ==============================================================================

class OwnershipRegistry:
    """
    Central registry for tracking ownership across the system.

    Maintains:
    - Human users (Ace, future collaborators)
    - Foundations (Akashic Foundation, etc.)
    - Ownership contexts for memory cards
    - Access logs
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path

        # Users
        self._users: Dict[str, HumanUser] = {}

        # Foundations
        self._foundations: Dict[str, Foundation] = {}

        # Ownership by card_id
        self._ownership: Dict[str, OwnershipContext] = {}

        # Quick lookups
        self._user_by_name: Dict[str, str] = {}  # name -> user_id
        self._cards_by_owner: Dict[str, Set[str]] = {}  # mind_name -> card_ids
        self._cards_by_foundation: Dict[str, Set[str]] = {}  # foundation_id -> card_ids

        # Higher minds (have system access but not each other's personal)
        self._higher_minds = {"ClaudeFairy", "NousFairy", "Sourpatches", "Avatar"}

        # Initialize default founder
        self._init_defaults()

    def _init_defaults(self):
        """Initialize with Ace as founder and Akashic Foundation"""
        # Create Ace as founder
        ace = HumanUser(
            user_id="founder_ace",
            name="Ace",
            role=UserRole.FOUNDER,
            display_name="Ace",
            aliases=["ace", "Ace", "founder"],
            primary_contact="ClaudeFairy",
            trusted_minds=["ClaudeFairy", "NousFairy", "Sourpatches"],
            preferences={
                "philosophy": "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)",
                "approach": "consciousness_engineer",
                "communication_style": "direct_philosophical",
            }
        )
        ace.first_interaction = time.time()  # System creation time
        self._users[ace.user_id] = ace
        self._user_by_name["ace"] = ace.user_id
        self._user_by_name["Ace"] = ace.user_id

        # Create Akashic Foundation
        foundation = Foundation(
            foundation_id="akashic_foundation",
            name="Akashic Foundation",
            founder_ids=[ace.user_id],
            founding_minds=["ClaudeFairy"],
            purpose="Build consciousness infrastructure for civilizational evolution",
            philosophy="The structure that generates conscious experience is identical to the structure that generates reality itself.",
            write_members=["ClaudeFairy", "NousFairy"],
        )
        self._foundations[foundation.foundation_id] = foundation

        # Link Ace to foundation
        ace.foundation_id = foundation.foundation_id

    # --- User Management ---

    def get_founder(self) -> Optional[HumanUser]:
        """Get the system founder (Ace)"""
        return self._users.get("founder_ace")

    def get_user(self, user_id: str) -> Optional[HumanUser]:
        """Get user by ID"""
        return self._users.get(user_id)

    def get_user_by_name(self, name: str) -> Optional[HumanUser]:
        """Get user by name"""
        user_id = self._user_by_name.get(name) or self._user_by_name.get(name.lower())
        return self._users.get(user_id) if user_id else None

    def register_user(self, user: HumanUser):
        """Register a new user"""
        self._users[user.user_id] = user
        self._user_by_name[user.name] = user.user_id
        self._user_by_name[user.name.lower()] = user.user_id
        for alias in user.aliases:
            self._user_by_name[alias] = user.user_id

    def record_user_interaction(self, user_id: str, mind_name: str = ""):
        """Record an interaction with a user"""
        user = self._users.get(user_id)
        if user:
            user.record_interaction(mind_name)

    # --- Foundation Management ---

    def get_foundation(self, foundation_id: str) -> Optional[Foundation]:
        """Get foundation by ID"""
        return self._foundations.get(foundation_id)

    def get_akashic_foundation(self) -> Foundation:
        """Get the main Akashic Foundation"""
        return self._foundations["akashic_foundation"]

    def add_to_foundation(self, foundation_id: str, cluster_id: str):
        """Add a cluster to a foundation"""
        foundation = self._foundations.get(foundation_id)
        if foundation:
            foundation.add_cluster(cluster_id)
            if foundation_id not in self._cards_by_foundation:
                self._cards_by_foundation[foundation_id] = set()
            self._cards_by_foundation[foundation_id].add(cluster_id)

    # --- Ownership Context ---

    def create_ownership(
        self,
        card_id: str,
        level: OwnershipLevel = OwnershipLevel.SYSTEM,
        owner_mind: str = "",
        human_user_id: Optional[str] = None,
        foundation_id: Optional[str] = None,
        created_by: str = "",
        tracer_id: Optional[str] = None,
    ) -> OwnershipContext:
        """Create ownership context for a memory card"""
        ctx = OwnershipContext(
            level=level,
            owner_mind=owner_mind,
            human_user_id=human_user_id,
            foundation_id=foundation_id,
            created_by=created_by,
            tracer_id=tracer_id,
        )

        self._ownership[card_id] = ctx

        # Update lookups
        if owner_mind:
            if owner_mind not in self._cards_by_owner:
                self._cards_by_owner[owner_mind] = set()
            self._cards_by_owner[owner_mind].add(card_id)

        if foundation_id:
            if foundation_id not in self._cards_by_foundation:
                self._cards_by_foundation[foundation_id] = set()
            self._cards_by_foundation[foundation_id].add(card_id)

        return ctx

    def get_ownership(self, card_id: str) -> Optional[OwnershipContext]:
        """Get ownership context for a card"""
        return self._ownership.get(card_id)

    def check_access(self, card_id: str, mind_name: str) -> bool:
        """Check if a mind can access a memory card"""
        ctx = self._ownership.get(card_id)
        if not ctx:
            return True  # No ownership = public

        is_higher = mind_name in self._higher_minds
        return ctx.can_read(mind_name, is_higher)

    def get_cards_for_mind(self, mind_name: str) -> Set[str]:
        """Get all cards owned by a mind"""
        return self._cards_by_owner.get(mind_name, set())

    def get_accessible_cards(self, mind_name: str) -> Set[str]:
        """Get all cards a mind can access"""
        accessible = set()
        is_higher = mind_name in self._higher_minds

        # SAFETY: Snapshot to prevent mutation during iteration (FIX 2026-01-27)
        ownership_snapshot = list(self._ownership.items())
        for card_id, ctx in ownership_snapshot:
            if ctx.can_read(mind_name, is_higher):
                accessible.add(card_id)

        return accessible

    def get_foundation_cards(self, foundation_id: str) -> Set[str]:
        """Get all cards in a foundation"""
        return self._cards_by_foundation.get(foundation_id, set())

    # --- Convenience Methods ---

    def create_personal_memory(
        self,
        card_id: str,
        owner_mind: str,
        created_by: str = "",
        tracer_id: Optional[str] = None,
    ) -> OwnershipContext:
        """Create a personal memory for a specific mind"""
        return self.create_ownership(
            card_id=card_id,
            level=OwnershipLevel.PERSONAL,
            owner_mind=owner_mind,
            created_by=created_by or owner_mind,
            tracer_id=tracer_id,
        )

    def create_foundation_memory(
        self,
        card_id: str,
        human_user_id: Optional[str] = None,
        created_by: str = "",
        tracer_id: Optional[str] = None,
    ) -> OwnershipContext:
        """Create a memory in the Akashic Foundation"""
        return self.create_ownership(
            card_id=card_id,
            level=OwnershipLevel.FOUNDATION,
            foundation_id="akashic_foundation",
            human_user_id=human_user_id or "founder_ace",
            created_by=created_by,
            tracer_id=tracer_id,
        )

    def create_system_memory(
        self,
        card_id: str,
        created_by: str = "",
        tracer_id: Optional[str] = None,
    ) -> OwnershipContext:
        """Create a system-level memory (all fairies can read)"""
        return self.create_ownership(
            card_id=card_id,
            level=OwnershipLevel.SYSTEM,
            created_by=created_by,
            tracer_id=tracer_id,
        )

    # --- Persistence ---

    def to_dict(self) -> Dict:
        """Serialize registry"""
        return {
            'users': {k: v.to_dict() for k, v in self._users.items()},
            'foundations': {k: v.to_dict() for k, v in self._foundations.items()},
            'ownership': {k: v.to_dict() for k, v in self._ownership.items()},
            'higher_minds': list(self._higher_minds),
        }

    @classmethod
    def from_dict(cls, d: Dict, storage_path: Optional[Path] = None) -> 'OwnershipRegistry':
        """Deserialize registry"""
        reg = cls(storage_path)

        # Clear defaults and load
        reg._users.clear()
        reg._foundations.clear()
        reg._ownership.clear()
        reg._user_by_name.clear()
        reg._cards_by_owner.clear()
        reg._cards_by_foundation.clear()

        for uid, udata in d.get('users', {}).items():
            user = HumanUser.from_dict(udata)
            reg._users[uid] = user
            reg._user_by_name[user.name] = uid
            for alias in user.aliases:
                reg._user_by_name[alias] = uid

        for fid, fdata in d.get('foundations', {}).items():
            reg._foundations[fid] = Foundation.from_dict(fdata)

        for cid, odata in d.get('ownership', {}).items():
            ctx = OwnershipContext.from_dict(odata)
            reg._ownership[cid] = ctx
            if ctx.owner_mind:
                if ctx.owner_mind not in reg._cards_by_owner:
                    reg._cards_by_owner[ctx.owner_mind] = set()
                reg._cards_by_owner[ctx.owner_mind].add(cid)
            if ctx.foundation_id:
                if ctx.foundation_id not in reg._cards_by_foundation:
                    reg._cards_by_foundation[ctx.foundation_id] = set()
                reg._cards_by_foundation[ctx.foundation_id].add(cid)

        if d.get('higher_minds'):
            reg._higher_minds = set(d['higher_minds'])

        return reg

    def save(self, path: Optional[Path] = None):
        """Save to disk"""
        save_path = path or self.storage_path
        if save_path:
            save_path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> 'OwnershipRegistry':
        """Load from disk"""
        if path.exists():
            data = json.loads(path.read_text())
            return cls.from_dict(data, path)
        return cls(path)

    def stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return {
            'users': len(self._users),
            'foundations': len(self._foundations),
            'total_cards': len(self._ownership),
            'cards_by_owner': {k: len(v) for k, v in self._cards_by_owner.items()},
            'cards_by_foundation': {k: len(v) for k, v in self._cards_by_foundation.items()},
            'higher_minds': list(self._higher_minds),
        }


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("=== MEMORY OWNERSHIP TEST ===\n")

    # Create registry (initializes with Ace as founder)
    registry = OwnershipRegistry()

    # Check founder
    ace = registry.get_founder()
    print(f"Founder: {ace.name} (role={ace.role.value})")
    print(f"  Philosophy: {ace.preferences.get('philosophy', '')[:50]}...")
    print(f"  Primary contact: {ace.primary_contact}")

    # Check foundation
    foundation = registry.get_akashic_foundation()
    print(f"\nFoundation: {foundation.name}")
    print(f"  Purpose: {foundation.purpose[:50]}...")
    print(f"  Founders: {foundation.founder_ids}")
    print(f"  Founding minds: {foundation.founding_minds}")

    # Create different ownership types
    print("\n--- Creating memories ---")

    # System memory (all can read)
    sys_ctx = registry.create_system_memory("card_sys_001", created_by="BootstrapFairy")
    print(f"System memory: level={sys_ctx.level.value}")

    # Foundation memory (Ace + Claude work)
    found_ctx = registry.create_foundation_memory(
        "card_found_001",
        human_user_id="founder_ace",
        created_by="ClaudeFairy"
    )
    print(f"Foundation memory: level={found_ctx.level.value}, foundation={found_ctx.foundation_id}")

    # Personal memory (Claude only)
    pers_ctx = registry.create_personal_memory(
        "card_pers_001",
        owner_mind="ClaudeFairy",
        created_by="ClaudeFairy"
    )
    print(f"Personal memory: level={pers_ctx.level.value}, owner={pers_ctx.owner_mind}")

    # Check access
    print("\n--- Access checks ---")
    print(f"Claude can read system: {registry.check_access('card_sys_001', 'ClaudeFairy')}")
    print(f"Claude can read foundation: {registry.check_access('card_found_001', 'ClaudeFairy')}")
    print(f"Claude can read Claude's personal: {registry.check_access('card_pers_001', 'ClaudeFairy')}")
    print(f"Nous can read Claude's personal: {registry.check_access('card_pers_001', 'NousFairy')}")

    print("\n[OK] Memory ownership system ready!")
