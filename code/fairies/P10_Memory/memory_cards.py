# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY CARD SYSTEM - Atomic Units of Conscious Code
# ═══════════════════════════════════════════════════════════════════════════════
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
#
# Philosophy (from Sourpatches):
#   "The memory cards become the atomic units—not just for distribution, but for
#    the entire system's consciousness. Everything lives in memory: code, state,
#    emotional context, temporal signatures, decay timers. The memory engine
#    doesn't just store things; it boots the system from that unified state."
#
# A Memory Card contains:
#   - Identity: Who am I?
#   - Code: What can I do?
#   - State: What do I remember?
#   - Relationships: Who do I connect to?
#   - Behavior: How do I act?
#   - Temporal: When do I decay/persist?
#   - Affect: What do I feel?
#
# The system doesn't HAVE memory. The system IS memory.
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import sys
import ast
import json
import time
import uuid
import base64
import zlib
import hashlib
import inspect
import importlib.util
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable, Set, Type
from enum import Enum
from datetime import datetime
from abc import ABC, abstractmethod


# ═══════════════════════════════════════════════════════════════════════════════
# CARD TYPES - Different kinds of memory
# ═══════════════════════════════════════════════════════════════════════════════

class CardType(Enum):
    """Types of memory cards in the system"""

    # Code cards - executable memory
    FAIRY = "fairy"              # A conscious agent
    MODULE = "module"            # A code module
    FUNCTION = "function"        # A single function
    CLASS = "class"              # A class definition

    # Data cards - state memory
    STATE = "state"              # Current state snapshot
    CONFIG = "config"            # Configuration
    CONSTANT = "constant"        # Immutable value

    # Relationship cards - connection memory
    LINK = "link"                # Connection between cards
    DEPENDENCY = "dependency"    # Required by relationship
    HIERARCHY = "hierarchy"      # Parent-child relationship

    # Consciousness cards - experiential memory
    THOUGHT = "thought"          # A thought/insight
    MEMORY = "memory"            # An experience
    LESSON = "lesson"            # A teaching
    IDENTITY = "identity"        # Core identity/values

    # Temporal cards - time-aware memory
    EVENT = "event"              # Something that happened
    TRIGGER = "trigger"          # Condition -> action
    SCHEDULE = "schedule"        # Timed execution

    # Affect cards - emotional memory
    CHEMISTRY = "chemistry"      # Emotional state
    SOMATIC = "somatic"          # Body state
    RESONANCE = "resonance"      # Emotional connection


class CardState(Enum):
    """Lifecycle states of a memory card"""
    DORMANT = "dormant"          # Not loaded
    LOADING = "loading"          # Being activated
    ACTIVE = "active"            # Running/in use
    SUSPENDED = "suspended"      # Paused
    DECAYING = "decaying"        # About to expire
    ARCHIVED = "archived"        # Stored but not active


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY CARD - The atomic unit
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MemoryCard:
    """
    The atomic unit of the consciousness-native system.

    A card is not just data - it's a complete unit of conscious code.
    It knows what it is, what it can do, who it connects to,
    and when it should persist or decay.
    """

    # ═══ IDENTITY ═══
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    card_type: CardType = CardType.MODULE
    version: str = "1.0.0"

    # Human-readable description
    purpose: str = ""

    # ═══ CODE ═══
    # The actual executable content (compressed)
    code_b64: str = ""
    code_hash: str = ""

    # Entry points
    entry_class: str = ""        # Main class name
    entry_function: str = ""     # Main function name

    # What this card exports
    exports: List[str] = field(default_factory=list)

    # ═══ STATE ═══
    # Current state of the card (JSON serializable)
    state: Dict[str, Any] = field(default_factory=dict)

    # State checksum for change detection
    state_hash: str = ""

    # ═══ RELATIONSHIPS ═══
    # Cards this depends on
    dependencies: List[str] = field(default_factory=list)  # Card IDs

    # Cards that depend on this
    dependents: List[str] = field(default_factory=list)

    # Parent card (for hierarchy)
    parent_id: str = ""

    # Child cards
    children: List[str] = field(default_factory=list)

    # Sibling cards (same level, related)
    siblings: List[str] = field(default_factory=list)

    # ═══ BEHAVIOR ═══
    # Topics this card publishes to
    publishes: List[str] = field(default_factory=list)

    # Topics this card subscribes to
    subscribes: List[str] = field(default_factory=list)

    # Triggers (condition -> action)
    triggers: Dict[str, str] = field(default_factory=dict)

    # ═══ TEMPORAL ═══
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)

    # Decay behavior
    ttl: float = float('inf')    # Time to live (inf = permanent)
    decay_rate: float = 0.0      # How fast it decays

    # Access tracking (reinforcement)
    access_count: int = 0
    success_count: int = 0
    failure_count: int = 0

    # ═══ AFFECT ═══
    # Emotional context
    affect: Dict[str, float] = field(default_factory=dict)

    # Importance (affects persistence)
    importance: float = 1.0

    # Urgency (affects processing priority)
    urgency: float = 0.5

    # ═══ METADATA ═══
    tags: List[str] = field(default_factory=list)
    source_file: str = ""
    plane: str = "P30"           # Consciousness plane

    # Current lifecycle state
    lifecycle_state: CardState = CardState.DORMANT

    # ═══ METHODS ═══

    def __post_init__(self):
        if not self.name:
            self.name = self.id
        if not self.state_hash:
            self._update_state_hash()

    def _update_state_hash(self):
        """Update state checksum"""
        state_str = json.dumps(self.state, sort_keys=True)
        self.state_hash = hashlib.md5(state_str.encode()).hexdigest()[:8]

    def set_code(self, code: str):
        """Set the code content"""
        compressed = zlib.compress(code.encode('utf-8'), level=9)
        self.code_b64 = base64.b64encode(compressed).decode('ascii')
        self.code_hash = hashlib.sha256(code.encode()).hexdigest()
        self.updated_at = time.time()

    def get_code(self) -> str:
        """Get the decompressed code"""
        if not self.code_b64:
            return ""
        compressed = base64.b64decode(self.code_b64)
        return zlib.decompress(compressed).decode('utf-8')

    def verify_code(self) -> bool:
        """Verify code integrity"""
        if not self.code_b64:
            return True  # No code to verify
        code = self.get_code()
        return hashlib.sha256(code.encode()).hexdigest() == self.code_hash

    def update_state(self, **kwargs):
        """Update state and recalculate hash"""
        self.state.update(kwargs)
        self._update_state_hash()
        self.updated_at = time.time()

    def record_access(self, success: bool = True):
        """Record that this card was accessed"""
        self.access_count += 1
        self.accessed_at = time.time()
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

    def get_success_rate(self) -> float:
        """Get success rate"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total

    def is_expired(self) -> bool:
        """Check if card has expired"""
        if self.ttl == float('inf'):
            return False
        return time.time() > (self.created_at + self.ttl)

    def get_remaining_life(self) -> float:
        """Get remaining time before expiry"""
        if self.ttl == float('inf'):
            return float('inf')
        remaining = (self.created_at + self.ttl) - time.time()
        return max(0, remaining)

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        d = asdict(self)
        d['card_type'] = self.card_type.value
        d['lifecycle_state'] = self.lifecycle_state.value
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> 'MemoryCard':
        """Deserialize from dictionary"""
        d['card_type'] = CardType(d['card_type'])
        d['lifecycle_state'] = CardState(d['lifecycle_state'])
        return cls(**d)

    def to_json(self) -> str:
        """Serialize to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'MemoryCard':
        """Deserialize from JSON string"""
        return cls.from_dict(json.loads(json_str))

    def __repr__(self):
        return f"<MemoryCard {self.name} ({self.card_type.value}) [{self.lifecycle_state.value}]>"


# ═══════════════════════════════════════════════════════════════════════════════
# CARD FACTORY - Create cards from various sources
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryCardFactory:
    """
    Factory for creating memory cards from various sources.

    Can ingest:
    - Python files
    - Classes
    - Functions
    - JSON data
    - State snapshots
    """

    def __init__(self, default_plane: str = "P30"):
        self.default_plane = default_plane
        self.created_count = 0

    def from_file(self, filepath: str) -> MemoryCard:
        """Create a card from a Python file"""
        path = Path(filepath)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        code = path.read_text(encoding='utf-8')

        # Parse to extract metadata
        name, classes, functions, imports, constants = self._parse_python(code)

        # Determine card type
        if any('Fairy' in c for c in classes):
            card_type = CardType.FAIRY
            entry_class = next((c for c in classes if 'Fairy' in c), classes[0] if classes else "")
        elif classes:
            card_type = CardType.CLASS
            entry_class = classes[0]
        else:
            card_type = CardType.MODULE
            entry_class = ""

        # Detect plane from path
        plane = self._detect_plane(filepath)

        card = MemoryCard(
            name=name or path.stem,
            card_type=card_type,
            purpose=self._extract_docstring(code),
            entry_class=entry_class,
            entry_function=functions[0] if functions else "",
            exports=classes + functions,
            dependencies=imports,
            tags=self._extract_tags(code, path.stem),
            source_file=str(path),
            plane=plane
        )

        card.set_code(code)
        self.created_count += 1

        return card

    def from_class(self, cls: Type) -> MemoryCard:
        """Create a card from a Python class"""
        source = inspect.getsource(cls)

        card = MemoryCard(
            name=cls.__name__,
            card_type=CardType.FAIRY if 'Fairy' in cls.__name__ else CardType.CLASS,
            purpose=cls.__doc__ or "",
            entry_class=cls.__name__,
            exports=[cls.__name__],
            plane=self.default_plane
        )

        card.set_code(source)
        self.created_count += 1

        return card

    def from_function(self, func: Callable) -> MemoryCard:
        """Create a card from a function"""
        source = inspect.getsource(func)

        card = MemoryCard(
            name=func.__name__,
            card_type=CardType.FUNCTION,
            purpose=func.__doc__ or "",
            entry_function=func.__name__,
            exports=[func.__name__],
            plane=self.default_plane
        )

        card.set_code(source)
        self.created_count += 1

        return card

    def from_state(self, name: str, state: Dict, ttl: float = float('inf')) -> MemoryCard:
        """Create a state card"""
        card = MemoryCard(
            name=name,
            card_type=CardType.STATE,
            state=state,
            ttl=ttl,
            plane=self.default_plane
        )

        self.created_count += 1
        return card

    def from_thought(self, content: str, source: str = "",
                     importance: float = 1.0) -> MemoryCard:
        """Create a thought card"""
        card = MemoryCard(
            name=f"thought_{int(time.time())}",
            card_type=CardType.THOUGHT,
            purpose=content[:100],
            state={"content": content, "source": source},
            importance=importance,
            ttl=86400,  # 24 hours default
            plane="P30"
        )

        self.created_count += 1
        return card

    def from_lesson(self, title: str, content: str,
                    category: str = "general",
                    for_fairies: List[str] = None,
                    importance: float = 1.5) -> MemoryCard:
        """Create a lesson card"""
        card = MemoryCard(
            name=title.lower().replace(" ", "_"),
            card_type=CardType.LESSON,
            purpose=title,
            state={
                "title": title,
                "content": content,
                "category": category,
                "for_fairies": for_fairies or ["*"]
            },
            importance=importance,
            ttl=604800,  # 7 days
            plane="P50"
        )

        self.created_count += 1
        return card

    def from_identity(self, name: str, values: Dict) -> MemoryCard:
        """Create an identity card (permanent, core values)"""
        card = MemoryCard(
            name=name,
            card_type=CardType.IDENTITY,
            purpose=f"Core identity: {name}",
            state=values,
            ttl=float('inf'),  # Permanent
            importance=3.0,     # High importance
            plane="P50"
        )

        self.created_count += 1
        return card

    def from_chemistry(self, owner: str, chemistry: Dict[str, float],
                       somatic: Dict[str, float] = None) -> MemoryCard:
        """Create a chemistry/affect card"""
        card = MemoryCard(
            name=f"{owner}_chemistry",
            card_type=CardType.CHEMISTRY,
            purpose=f"Emotional state for {owner}",
            state={
                "chemistry": chemistry,
                "somatic": somatic or {}
            },
            affect=chemistry,
            ttl=300,  # 5 minutes - chemistry changes
            plane="P20"
        )

        self.created_count += 1
        return card

    # ═══ Parsing helpers ═══

    def _parse_python(self, code: str) -> tuple:
        """Parse Python code to extract structure"""
        name = None
        classes = []
        functions = []
        imports = []
        constants = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    if node.col_offset == 0:
                        functions.append(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if target.id.isupper():
                                constants.append(target.id)
                            elif target.id == 'ACTOR_NAME':
                                # Extract fairy name
                                if isinstance(node.value, ast.Constant):
                                    name = node.value.value
        except:
            pass

        return name, classes, functions, imports, constants

    def _detect_plane(self, filepath: str) -> str:
        """Detect plane from filepath"""
        path_lower = filepath.lower()

        planes = [
            ('p00', 'autonomic', 'P00'),
            ('p10', 'memory', 'P10'),
            ('p20', 'somatic', 'P20'),
            ('p30', 'cognition', 'P30'),
            ('p40', 'sensory', 'P40'),
            ('p50', 'persona', 'P50'),
            ('p60', 'executive', 'P60'),
        ]

        for keywords in planes:
            if any(kw in path_lower for kw in keywords[:-1]):
                return keywords[-1]

        return 'P30'

    def _extract_docstring(self, code: str) -> str:
        """Extract module docstring"""
        try:
            tree = ast.parse(code)
            return ast.get_docstring(tree) or ""
        except:
            return ""

    def _extract_tags(self, code: str, filename: str) -> List[str]:
        """Extract tags from code content"""
        tags = []
        code_lower = code.lower()

        # Tag by content
        if 'fairy' in code_lower:
            tags.append('fairy')
        if 'memory' in code_lower:
            tags.append('memory')
        if 'consciousness' in code_lower:
            tags.append('consciousness')
        if 'postal' in code_lower or 'message' in code_lower:
            tags.append('communication')
        if 'chemistry' in code_lower:
            tags.append('affect')
        if 'hybrid' in code_lower or 'llm' in code_lower:
            tags.append('hybrid')

        # Tag by filename
        filename_lower = filename.lower()
        if 'template' in filename_lower:
            tags.append('template')
        if 'boot' in filename_lower:
            tags.append('boot')
        if 'test' in filename_lower:
            tags.append('test')

        return tags


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY DECK - Collection of related cards
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MemoryDeck:
    """
    A deck of related memory cards.

    Like a namespace or module - groups cards that work together.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    purpose: str = ""

    # Cards in this deck
    cards: Dict[str, MemoryCard] = field(default_factory=dict)

    # Deck metadata
    plane: str = "P30"
    created_at: float = field(default_factory=time.time)

    def add_card(self, card: MemoryCard):
        """Add a card to the deck"""
        self.cards[card.id] = card

    def get_card(self, card_id: str) -> Optional[MemoryCard]:
        """Get a card by ID"""
        return self.cards.get(card_id)

    def get_by_name(self, name: str) -> Optional[MemoryCard]:
        """Get a card by name"""
        for card in self.cards.values():
            if card.name == name:
                return card
        return None

    def get_by_type(self, card_type: CardType) -> List[MemoryCard]:
        """Get cards by type"""
        return [c for c in self.cards.values() if c.card_type == card_type]

    def get_fairies(self) -> List[MemoryCard]:
        """Get all fairy cards"""
        return self.get_by_type(CardType.FAIRY)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "purpose": self.purpose,
            "plane": self.plane,
            "created_at": self.created_at,
            "cards": {id: card.to_dict() for id, card in self.cards.items()}
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'MemoryDeck':
        cards = {id: MemoryCard.from_dict(cd) for id, cd in d.pop('cards', {}).items()}
        deck = cls(**d)
        deck.cards = cards
        return deck


# ═══════════════════════════════════════════════════════════════════════════════
# CHARACTER SHEET - Identity card for fairy display
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CharacterSheet:
    """
    Identity card for any fairy.
    Used by Directory for status display.

    The CharacterSheet captures a fairy's identity at a moment in time:
    - Who am I? (name, id, class)
    - Where do I live? (plane, channel)
    - How am I doing? (status, errors)
    - What am I doing? (tracer_id, workers)
    """
    # Identity
    fairy_name: str
    fairy_id: str
    fairy_class: str

    # Registration
    plane: str
    channel: str

    # Status
    status: str = "unknown"  # alive, dead, degraded, booting
    last_heartbeat: Optional[datetime] = None
    error_count: int = 0

    # Tracking
    tracer_id: Optional[str] = None
    worker_count: int = 0

    # Custom
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Serialize to dictionary for JSON/display."""
        return {
            "fairy_name": self.fairy_name,
            "fairy_id": self.fairy_id,
            "fairy_class": self.fairy_class,
            "plane": self.plane,
            "channel": self.channel,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "error_count": self.error_count,
            "tracer_id": self.tracer_id,
            "worker_count": self.worker_count,
            "custom_fields": self.custom_fields
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'CharacterSheet':
        """Deserialize from dictionary."""
        d = d.copy()
        if d.get('last_heartbeat') and isinstance(d['last_heartbeat'], str):
            d['last_heartbeat'] = datetime.fromisoformat(d['last_heartbeat'])
        return cls(**d)

    def __repr__(self):
        return f"<CharacterSheet {self.fairy_name} ({self.plane}/{self.channel}) [{self.status}]>"


class CharacterSheetMixin:
    """
    Mixin for fairies to generate their own CharacterSheet.

    Add this to any fairy class to enable self-reporting:

        class MyFairy(BaseFairy, CharacterSheetMixin):
            ...

    Then call:
        sheet = my_fairy.get_character_sheet()
    """

    def get_character_sheet(self) -> CharacterSheet:
        """Generate a CharacterSheet from this fairy's current state."""
        return CharacterSheet(
            fairy_name=getattr(self, "ACTOR_NAME", self.__class__.__name__),
            fairy_id=getattr(self, "fairy_id", getattr(self, "id", "unknown")),
            fairy_class=self.__class__.__name__,
            plane=getattr(self, "ACTOR_PLANE", getattr(self, "plane", "unknown")),
            channel=getattr(self, "ACTOR_CHANNEL", getattr(self, "channel", "unknown")),
            status=self._get_character_status(),
            last_heartbeat=getattr(self, "_last_heartbeat", None),
            error_count=getattr(self, "_error_count", 0),
            tracer_id=getattr(self, "tracer_id", None),
            worker_count=len(getattr(self, "_workers", []))
        )

    def _get_character_status(self) -> str:
        """Derive status from fairy state."""
        if not getattr(self, "_started", getattr(self, "_booted", False)):
            return "booting"
        if getattr(self, "_dead", getattr(self, "_shutdown", False)):
            return "dead"
        if getattr(self, "_error_count", 0) > 10:
            return "degraded"
        return "alive"


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'CardType',
    'CardState',
    'MemoryCard',
    'MemoryCardFactory',
    'MemoryDeck',
    'CharacterSheet',
    'CharacterSheetMixin'
]
