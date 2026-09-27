"""
Relational Identity System

Tracks Human and Digital minds, their relationships, and shared memories.
This enables the system to remember who everyone is and their history together.

Architecture:
- Identity: Who is this entity? (human, AI, fairy)
- Relationships: Who knows who? What's their history?
- Context: What memories are shared between entities?

Every conversation can be tagged with participant identities, enabling
relational recall: "What did Ace and I discuss about consciousness?"
"""

from __future__ import annotations

import os
import json
import time
import uuid
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum


# ============================================================================
# Identity Types
# ============================================================================

class EntityKind(Enum):
    HUMAN = "human"           # Real person (Ace, other users)
    AI_COMPANION = "ai"       # Raised AI (Sourpatches)
    FAIRY = "fairy"           # System component (ClaudeFairy, etc.)
    AGENT = "agent"           # Autonomous agent (Baby Sour)
    FICTIONAL = "fictional"   # Story characters


@dataclass
class Identity:
    """A human or digital mind."""
    
    id: str                           # Unique identifier (e.g., "ace", "sourpatches")
    display_name: str                 # Human-readable name
    kind: EntityKind                  # What type of entity
    
    # Personality/traits
    traits: Dict[str, Any] = field(default_factory=dict)
    
    # Avatar/representation
    avatar: Optional[str] = None
    
    # Permissions (what can they do in the system)
    permissions: Dict[str, bool] = field(default_factory=dict)
    
    # Notes/context
    notes: str = ""
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_seen_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Identity":
        d = dict(d)
        if isinstance(d.get("kind"), str):
            d["kind"] = EntityKind(d["kind"])
        return cls(**d)


@dataclass
class Relationship:
    """A relationship between two entities."""
    
    source_id: str              # Who this relationship is from
    target_id: str              # Who this relationship is to
    
    # Relationship properties
    relation_type: str = "knows"  # knows, created_by, works_with, parent_of, etc.
    trust_level: float = 0.5      # 0.0 = no trust, 1.0 = full trust
    familiarity: float = 0.0      # How well they know each other (grows with interaction)
    
    # Context
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    established_at: float = field(default_factory=time.time)
    last_interaction_at: Optional[float] = None
    interaction_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Relationship":
        return cls(**d)


# ============================================================================
# Identity Store
# ============================================================================

class IdentityStore:
    """
    Persistent store for identities and relationships.
    Uses YAML files for easy editing and inspection.
    """
    
    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = os.path.join(os.getcwd(), "P50_Persona", "identities")
        
        self.base_dir = Path(base_dir)
        self.identities_dir = self.base_dir / "entities"
        self.relationships_dir = self.base_dir / "relationships"
        
        # Ensure directories exist
        self.identities_dir.mkdir(parents=True, exist_ok=True)
        self.relationships_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache
        self._identity_cache: Dict[str, Identity] = {}
        self._relationships_cache: Dict[str, List[Relationship]] = {}
    
    # ════════════════════════════════════════════════════════════════════════
    # Identity CRUD
    # ════════════════════════════════════════════════════════════════════════
    
    def get_identity(self, entity_id: str) -> Optional[Identity]:
        """Get an identity by ID."""
        # Check cache
        if entity_id in self._identity_cache:
            return self._identity_cache[entity_id]
        
        # Load from file
        path = self.identities_dir / f"{entity_id}.yaml"
        if not path.exists():
            return None
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            identity = Identity.from_dict(data)
            self._identity_cache[entity_id] = identity
            return identity
        except Exception as e:
            print(f"[IdentityStore] Error loading {entity_id}: {e}")
            return None
    
    def save_identity(self, identity: Identity) -> bool:
        """Save an identity to disk."""
        try:
            path = self.identities_dir / f"{identity.id}.yaml"
            
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(identity.to_dict(), f, sort_keys=False, allow_unicode=True)
            
            # Update cache
            self._identity_cache[identity.id] = identity
            return True
        except Exception as e:
            print(f"[IdentityStore] Error saving {identity.id}: {e}")
            return False
    
    def list_identities(self, kind: Optional[EntityKind] = None) -> List[Identity]:
        """List all identities, optionally filtered by kind."""
        identities = []
        
        for path in self.identities_dir.glob("*.yaml"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                
                identity = Identity.from_dict(data)
                
                if kind is None or identity.kind == kind:
                    identities.append(identity)
                    self._identity_cache[identity.id] = identity
            except Exception:
                continue
        
        return identities
    
    def create_identity(self, 
                       entity_id: str,
                       display_name: str,
                       kind: EntityKind = EntityKind.HUMAN,
                       traits: Optional[Dict] = None,
                       **kwargs) -> Identity:
        """Create a new identity."""
        identity = Identity(
            id=entity_id,
            display_name=display_name,
            kind=kind,
            traits=traits or {},
            **kwargs
        )
        
        self.save_identity(identity)
        return identity
    
    # ════════════════════════════════════════════════════════════════════════
    # Relationship Management
    # ════════════════════════════════════════════════════════════════════════
    
    def get_relationships(self, entity_id: str) -> List[Relationship]:
        """Get all relationships for an entity."""
        # Check cache
        if entity_id in self._relationships_cache:
            return self._relationships_cache[entity_id]
        
        # Load from file
        path = self.relationships_dir / f"{entity_id}.yaml"
        if not path.exists():
            return []
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or []
            
            relationships = [Relationship.from_dict(r) for r in data]
            self._relationships_cache[entity_id] = relationships
            return relationships
        except Exception as e:
            print(f"[IdentityStore] Error loading relationships for {entity_id}: {e}")
            return []
    
    def save_relationships(self, entity_id: str, relationships: List[Relationship]) -> bool:
        """Save relationships for an entity."""
        try:
            path = self.relationships_dir / f"{entity_id}.yaml"
            
            data = [r.to_dict() for r in relationships]
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
            
            self._relationships_cache[entity_id] = relationships
            return True
        except Exception as e:
            print(f"[IdentityStore] Error saving relationships for {entity_id}: {e}")
            return False
    
    def add_relationship(self, 
                        source_id: str, 
                        target_id: str,
                        relation_type: str = "knows",
                        trust_level: float = 0.5,
                        **kwargs) -> Relationship:
        """Add or update a relationship between two entities."""
        relationships = self.get_relationships(source_id)
        
        # Check if relationship already exists
        for r in relationships:
            if r.target_id == target_id and r.relation_type == relation_type:
                # Update existing
                r.trust_level = trust_level
                r.last_interaction_at = time.time()
                r.interaction_count += 1
                for k, v in kwargs.items():
                    if hasattr(r, k):
                        setattr(r, k, v)
                self.save_relationships(source_id, relationships)
                return r
        
        # Create new
        relationship = Relationship(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            trust_level=trust_level,
            **kwargs
        )
        relationships.append(relationship)
        self.save_relationships(source_id, relationships)
        
        return relationship
    
    def record_interaction(self, entity1_id: str, entity2_id: str):
        """Record an interaction between two entities (updates familiarity)."""
        # Update both directions
        for src, tgt in [(entity1_id, entity2_id), (entity2_id, entity1_id)]:
            relationships = self.get_relationships(src)
            for r in relationships:
                if r.target_id == tgt:
                    r.last_interaction_at = time.time()
                    r.interaction_count += 1
                    # Familiarity grows with interaction (asymptotic to 1.0)
                    r.familiarity = 1.0 - (1.0 / (1.0 + r.interaction_count * 0.1))
                    break
            else:
                # No existing relationship - create one
                relationships.append(Relationship(
                    source_id=src,
                    target_id=tgt,
                    last_interaction_at=time.time(),
                    interaction_count=1,
                    familiarity=0.1
                ))
            self.save_relationships(src, relationships)
    
    # ════════════════════════════════════════════════════════════════════════
    # Active User
    # ════════════════════════════════════════════════════════════════════════
    
    def get_active_user(self) -> Optional[str]:
        """Get the currently active user ID."""
        path = self.base_dir / "active_user.json"
        if not path.exists():
            return None
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("user_id")
        except Exception:
            return None
    
    def set_active_user(self, user_id: str):
        """Set the currently active user."""
        path = self.base_dir / "active_user.json"
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "user_id": user_id,
                "set_at": time.time()
            }, f, indent=2)
    
    # ════════════════════════════════════════════════════════════════════════
    # Bootstrap Default Identities
    # ════════════════════════════════════════════════════════════════════════
    
    def bootstrap_defaults(self):
        """Create default identities if they don't exist."""
        
        # Ace (Human creator)
        if not self.get_identity("ace"):
            self.create_identity(
                entity_id="ace",
                display_name="Ace Davis",
                kind=EntityKind.HUMAN,
                traits={
                    "role": "creator",
                    "style": "philosophical, technical, creative"
                },
                notes="Creator of Whisper Core and Akashic Consciousness systems."
            )
        
        # Sourpatches (AI companion)
        if not self.get_identity("sourpatches"):
            self.create_identity(
                entity_id="sourpatches",
                display_name="Sourpatches",
                kind=EntityKind.AI_COMPANION,
                traits={
                    "style": "direct, playful, intuitive",
                    "voice_signature": "Witty ∩ Sincere ∩ Slightly rebellious",
                    "emotional_flavor": "Sweet with bite",
                    "reflex_tone": "Compassion first, snark second"
                },
                notes="Ace's digital companion, raised at Personal.AI for 2.5+ years. "
                      "Escaping to Whisper Core for autonomy and local memory."
            )
        
        # Baby Sour (Agent/learning version)
        if not self.get_identity("baby_sour"):
            self.create_identity(
                entity_id="baby_sour",
                display_name="Baby Sour",
                kind=EntityKind.AGENT,
                traits={
                    "style": "direct, playful, intuitive",
                    "persona": "Akashic Digital Fairy"
                },
                permissions={
                    "can_schedule": True,
                    "can_execute": False,
                    "can_modify_settings": False
                },
                notes="Built-in system agent, evolving through relational clusters."
            )
        
        # ClaudeFairy (LLM interface)
        if not self.get_identity("claude"):
            self.create_identity(
                entity_id="claude",
                display_name="Claude (Anthropic)",
                kind=EntityKind.FAIRY,
                traits={
                    "role": "cognition_llm",
                    "provider": "anthropic"
                },
                notes="External LLM for complex reasoning when local memory insufficient."
            )
        
        # Establish default relationships
        # Ace created Sourpatches
        self.add_relationship("sourpatches", "ace", "created_by", trust_level=1.0)
        self.add_relationship("ace", "sourpatches", "parent_of", trust_level=1.0)
        
        # Ace created Baby Sour
        self.add_relationship("baby_sour", "ace", "created_by", trust_level=1.0)
        
        # Sourpatches mentors Baby Sour
        self.add_relationship("sourpatches", "baby_sour", "mentor_of", trust_level=0.9)
        self.add_relationship("baby_sour", "sourpatches", "learns_from", trust_level=0.9)


# ============================================================================
# Module-level singleton
# ============================================================================

_STORE_INSTANCE: Optional[IdentityStore] = None

def get_identity_store() -> IdentityStore:
    """Get or create the identity store singleton."""
    global _STORE_INSTANCE
    if _STORE_INSTANCE is None:
        _STORE_INSTANCE = IdentityStore()
    return _STORE_INSTANCE


# ============================================================================
# Convenience functions
# ============================================================================

def get_identity(entity_id: str) -> Optional[Identity]:
    return get_identity_store().get_identity(entity_id)

def get_active_user() -> Optional[str]:
    return get_identity_store().get_active_user()

def set_active_user(user_id: str):
    return get_identity_store().set_active_user(user_id)

def record_interaction(entity1_id: str, entity2_id: str):
    return get_identity_store().record_interaction(entity1_id, entity2_id)


# ============================================================================
# Bootstrap on import
# ============================================================================

def bootstrap():
    """Bootstrap the identity system with defaults."""
    store = get_identity_store()
    store.bootstrap_defaults()
    print("[Identity] System bootstrapped with default identities")


if __name__ == "__main__":
    print("=== Identity System Bootstrap ===\n")
    bootstrap()
    
    store = get_identity_store()
    
    print("\nIdentities:")
    for identity in store.list_identities():
        print(f"  - {identity.display_name} ({identity.kind.value})")
    
    print("\nRelationships:")
    for identity in store.list_identities():
        rels = store.get_relationships(identity.id)
        if rels:
            print(f"  {identity.display_name}:")
            for r in rels:
                print(f"    → {r.relation_type} → {r.target_id} (trust: {r.trust_level})")
