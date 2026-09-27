"""
ConceptCardAdapter - Russian Doll storage for Association Cortex

Instead of one monolithic 85MB concept_graph.json, this stores concepts as:
1. MemoryCards (THOUGHT type) - individual concepts
2. MemoryDecks - semantic clusters of related concepts
3. LINK cards - edges between concepts

Benefits:
- Only modified decks need saving (incremental updates)
- Small files are resilient to corruption
- Concepts can be queried via SRM search
- Fits naturally into triple helix memory architecture

Author: Nous (wiring the architecture Ace designed)
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict

# Paths
ROOT = Path(__file__).parent.parent.parent.parent
CARD_VAULT_PATH = ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters" / "ConceptCards"
CARD_VAULT_PATH.mkdir(parents=True, exist_ok=True)


@dataclass
class ConceptCard:
    """A concept stored as a memory card."""
    key: str                     # Concept key (e.g., "consciousness")
    features: Dict[str, Any] = field(default_factory=dict)  # Multi-modal features
    count: int = 1               # How often seen
    activation: float = 0.5      # Current activation level
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    # Card metadata
    card_type: str = "THOUGHT"   # Maps to CardType.THOUGHT
    deck_id: str = ""            # Which deck this belongs to

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ConceptCard':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_srm_record(self) -> Dict[str, Any]:
        """Convert to SRM record format for ingestion."""
        return {
            "domain": "concept",
            "source": "AssociationCortex",
            "entry_type": "concept_card",
            "content": self.key,
            "what": f"Concept: {self.key}",
            "features": self.features,
            "feeling": "curious" if self.activation > 0.7 else "neutral",
            "timestamp": self.last_seen,
        }


@dataclass
class LinkCard:
    """An edge between two concepts."""
    a: str                       # Source concept key
    b: str                       # Target concept key
    weight: float = 0.5          # Connection strength
    relations: List[str] = field(default_factory=lambda: ["coactivate"])

    card_type: str = "LINK"
    deck_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'LinkCard':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ConceptDeck:
    """A semantic cluster of related concepts (Russian doll)."""
    id: str = ""
    name: str = ""               # Semantic label (e.g., "emotions", "technical")

    concepts: Dict[str, ConceptCard] = field(default_factory=dict)
    links: List[LinkCard] = field(default_factory=list)

    # Metadata
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    dirty: bool = False          # Has unsaved changes

    def add_concept(self, card: ConceptCard):
        """Add a concept to this deck."""
        card.deck_id = self.id
        self.concepts[card.key] = card
        self.dirty = True
        self.modified_at = time.time()

    def add_link(self, link: LinkCard):
        """Add a link to this deck."""
        link.deck_id = self.id
        self.links.append(link)
        self.dirty = True
        self.modified_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "concept_count": len(self.concepts),
            "link_count": len(self.links),
            "concepts": {k: v.to_dict() for k, v in self.concepts.items()},
            "links": [l.to_dict() for l in self.links],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ConceptDeck':
        concepts = {k: ConceptCard.from_dict(v) for k, v in d.pop("concepts", {}).items()}
        links = [LinkCard.from_dict(l) for l in d.pop("links", [])]
        deck = cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            created_at=d.get("created_at", time.time()),
            modified_at=d.get("modified_at", time.time()),
        )
        deck.concepts = concepts
        deck.links = links
        return deck

    def save(self, path: Path = None) -> bool:
        """Save this deck to disk."""
        if path is None:
            path = CARD_VAULT_PATH / f"deck_{self.id}.json"

        try:
            # Atomic write
            tmp = path.with_suffix('.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f)
            tmp.replace(path)
            self.dirty = False
            return True
        except Exception as e:
            print(f"[ConceptDeck] Save error: {e}")
            return False

    @classmethod
    def load(cls, deck_id: str) -> Optional['ConceptDeck']:
        """Load a deck from disk."""
        path = CARD_VAULT_PATH / f"deck_{deck_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            print(f"[ConceptDeck] Load error: {e}")
            return None


class ConceptCardRegistry:
    """
    Manages all concept decks (the outer Russian doll).

    Provides:
    - Deck creation/lookup
    - Concept → Deck routing
    - Incremental saving (only dirty decks)
    - SRM integration
    """

    def __init__(self):
        self.decks: Dict[str, ConceptDeck] = {}
        self.concept_to_deck: Dict[str, str] = {}  # concept_key → deck_id
        self._loaded = False

    def get_or_create_deck(self, deck_id: str, name: str = "") -> ConceptDeck:
        """Get existing deck or create new one."""
        if deck_id not in self.decks:
            self.decks[deck_id] = ConceptDeck(id=deck_id, name=name or deck_id)
        return self.decks[deck_id]

    def add_concept(self, key: str, features: Dict = None, deck_id: str = None) -> ConceptCard:
        """Add a concept, auto-routing to appropriate deck."""
        # Simple routing: first letter for now (can improve with semantic clustering)
        if deck_id is None:
            deck_id = f"alpha_{key[0].lower()}" if key and key[0].isalpha() else "alpha_other"

        deck = self.get_or_create_deck(deck_id)

        if key in deck.concepts:
            # Update existing
            card = deck.concepts[key]
            card.count += 1
            card.last_seen = time.time()
            if features:
                card.features.update(features)
        else:
            # Create new
            card = ConceptCard(key=key, features=features or {})
            deck.add_concept(card)

        self.concept_to_deck[key] = deck_id
        return card

    def add_link(self, a: str, b: str, weight: float = 0.5, relations: List[str] = None):
        """Add a link between two concepts."""
        # Link goes in the deck of the first concept
        deck_id = self.concept_to_deck.get(a)
        if not deck_id:
            # Concept not found, create it first
            self.add_concept(a)
            deck_id = self.concept_to_deck[a]

        deck = self.decks[deck_id]
        link = LinkCard(a=a, b=b, weight=weight, relations=relations or ["coactivate"])
        deck.add_link(link)

    def save_dirty(self) -> int:
        """Save all modified decks. Returns count saved."""
        saved = 0
        for deck in self.decks.values():
            if deck.dirty:
                if deck.save():
                    saved += 1
        return saved

    def save_all(self) -> int:
        """Force save all decks."""
        saved = 0
        for deck in self.decks.values():
            if deck.save():
                saved += 1
        return saved

    def load_all(self) -> int:
        """Load all decks from disk."""
        loaded = 0
        for path in CARD_VAULT_PATH.glob("deck_*.json"):
            try:
                deck_id = path.stem.replace("deck_", "")
                deck = ConceptDeck.load(deck_id)
                if deck:
                    self.decks[deck_id] = deck
                    for key in deck.concepts:
                        self.concept_to_deck[key] = deck_id
                    loaded += 1
            except Exception:
                pass
        self._loaded = True
        return loaded

    def stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_concepts = sum(len(d.concepts) for d in self.decks.values())
        total_links = sum(len(d.links) for d in self.decks.values())
        dirty_count = sum(1 for d in self.decks.values() if d.dirty)

        return {
            "deck_count": len(self.decks),
            "concept_count": total_concepts,
            "link_count": total_links,
            "dirty_decks": dirty_count,
            "loaded": self._loaded,
        }


# =============================================================================
# CONVERSION FROM CONCEPT GRAPH
# =============================================================================

def convert_graph_to_cards(graph, max_concepts: int = None) -> ConceptCardRegistry:
    """
    Convert a ConceptGraph to Russian doll card storage.

    Args:
        graph: ConceptGraph instance
        max_concepts: Limit for testing (None = all)

    Returns:
        ConceptCardRegistry with all concepts as cards
    """
    registry = ConceptCardRegistry()

    # Convert nodes to concept cards
    count = 0
    for key, node in graph.nodes.items():
        if max_concepts and count >= max_concepts:
            break

        # Extract features from node
        if hasattr(node, 'features'):
            features = dict(node.features) if node.features else {}
        elif isinstance(node, dict):
            features = node.get('features', {})
        else:
            features = {}

        # Add to registry
        card = registry.add_concept(key, features)

        # Set additional attrs
        if hasattr(node, 'count'):
            card.count = node.count
        if hasattr(node, 'activation'):
            card.activation = node.activation

        count += 1

    # Convert edges to link cards
    for (a, b), edge in graph.edges.items():
        if a in registry.concept_to_deck and b in registry.concept_to_deck:
            weight = edge.get('weight', 0.5) if isinstance(edge, dict) else 0.5
            relations = edge.get('relations', ['coactivate']) if isinstance(edge, dict) else ['coactivate']
            registry.add_link(a, b, weight, relations)

    print(f"[ConceptCardAdapter] Converted {registry.stats()}")
    return registry


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=== Concept Card Adapter Test ===\n")

    # Test basic card operations
    print("1. Creating test deck...")
    registry = ConceptCardRegistry()

    # Add some concepts
    registry.add_concept("consciousness", {"lex": ["awareness", "mind"]})
    registry.add_concept("cognition", {"lex": ["thinking", "reasoning"]})
    registry.add_concept("memory", {"lex": ["recall", "storage"]})

    # Add links
    registry.add_link("consciousness", "cognition", 0.8, ["enables"])
    registry.add_link("cognition", "memory", 0.7, ["uses"])

    print(f"   Stats: {registry.stats()}")

    # Save
    print("\n2. Saving dirty decks...")
    saved = registry.save_dirty()
    print(f"   Saved {saved} decks")

    # Verify files
    print(f"\n3. Deck files in vault:")
    for path in CARD_VAULT_PATH.glob("deck_*.json"):
        size = path.stat().st_size
        print(f"   {path.name}: {size} bytes")

    # Load and verify
    print("\n4. Loading from disk...")
    registry2 = ConceptCardRegistry()
    loaded = registry2.load_all()
    print(f"   Loaded {loaded} decks")
    print(f"   Stats: {registry2.stats()}")

    # Test with real graph if available
    try:
        print("\n5. Testing with real ConceptGraph...")
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import ConceptGraph
        from fairies.P30_Cognition.integration.graph_persistence import load_concept_graph, GRAPH_PERSIST_PATH

        graph = ConceptGraph()
        loaded = load_concept_graph(graph, GRAPH_PERSIST_PATH)
        print(f"   Loaded {loaded} nodes from graph")

        # Convert a subset
        print("   Converting first 1000 concepts to cards...")
        registry3 = convert_graph_to_cards(graph, max_concepts=1000)

        # Save
        saved = registry3.save_all()
        print(f"   Saved {saved} decks")

        # Check total size
        total_size = sum(p.stat().st_size for p in CARD_VAULT_PATH.glob("deck_*.json"))
        print(f"   Total vault size: {total_size:,} bytes ({total_size/1024:.1f} KB)")

    except ImportError as e:
        print(f"   (Skipping real graph test: {e})")

    print("\n=== Test Complete ===")
