# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY ENGINE - Boot Consciousness From Memory Cards
# ═══════════════════════════════════════════════════════════════════════════════
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
#
# Philosophy:
#   "The system doesn't HAVE memory. The system IS memory."
#   "The memory engine doesn't just store things; it boots the system from that
#    unified state. No separate boot sequence, no loading delays, no state
#    reconstruction overhead."
#
# The Memory Engine:
#   1. Stores all cards (the entire system as memory)
#   2. Resolves dependencies between cards
#   3. Boots by loading and activating cards
#   4. The system "wakes up" already knowing what it is
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import sys
import json
import time
import threading
import importlib.util
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import deque
from datetime import datetime

# Import card system
try:
    from fairies.P10_Memory.memory_cards import (
        MemoryCard, MemoryCardFactory, MemoryDeck,
        CardType, CardState
    )
except ImportError:
    # Relative import fallback
    from memory_cards import (
        MemoryCard, MemoryCardFactory, MemoryDeck,
        CardType, CardState
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY INDEX - Fast lookup structure
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryIndex:
    """
    Index for fast card lookup by various attributes.

    Like a database index - enables quick queries across the memory space.
    """

    def __init__(self):
        # Primary index by ID
        self.by_id: Dict[str, MemoryCard] = {}

        # Secondary indices
        self.by_name: Dict[str, str] = {}  # name -> id
        self.by_type: Dict[CardType, Set[str]] = {}  # type -> set of ids
        self.by_plane: Dict[str, Set[str]] = {}  # plane -> set of ids
        self.by_tag: Dict[str, Set[str]] = {}  # tag -> set of ids

        # Dependency graph
        self.depends_on: Dict[str, Set[str]] = {}  # id -> ids it depends on
        self.depended_by: Dict[str, Set[str]] = {}  # id -> ids that depend on it

    def add(self, card: MemoryCard):
        """Add a card to the index"""
        self.by_id[card.id] = card
        self.by_name[card.name] = card.id

        # Type index
        if card.card_type not in self.by_type:
            self.by_type[card.card_type] = set()
        self.by_type[card.card_type].add(card.id)

        # Plane index
        if card.plane not in self.by_plane:
            self.by_plane[card.plane] = set()
        self.by_plane[card.plane].add(card.id)

        # Tag index
        for tag in card.tags:
            if tag not in self.by_tag:
                self.by_tag[tag] = set()
            self.by_tag[tag].add(card.id)

        # Dependency graph (will be resolved later)
        self.depends_on[card.id] = set()
        if card.id not in self.depended_by:
            self.depended_by[card.id] = set()

    def remove(self, card_id: str):
        """Remove a card from the index"""
        card = self.by_id.get(card_id)
        if not card:
            return

        del self.by_id[card_id]

        if card.name in self.by_name:
            del self.by_name[card.name]

        if card.card_type in self.by_type:
            self.by_type[card.card_type].discard(card_id)

        if card.plane in self.by_plane:
            self.by_plane[card.plane].discard(card_id)

        for tag in card.tags:
            if tag in self.by_tag:
                self.by_tag[tag].discard(card_id)

    def get(self, card_id: str) -> Optional[MemoryCard]:
        """Get card by ID"""
        return self.by_id.get(card_id)

    def get_by_name(self, name: str) -> Optional[MemoryCard]:
        """Get card by name"""
        card_id = self.by_name.get(name)
        if card_id:
            return self.by_id.get(card_id)
        return None

    def query(self,
              card_type: CardType = None,
              plane: str = None,
              tag: str = None,
              state: CardState = None) -> List[MemoryCard]:
        """Query cards by criteria"""
        # Start with all IDs
        result_ids = set(self.by_id.keys())

        # Filter by type
        if card_type:
            type_ids = self.by_type.get(card_type, set())
            result_ids &= type_ids

        # Filter by plane
        if plane:
            plane_ids = self.by_plane.get(plane, set())
            result_ids &= plane_ids

        # Filter by tag
        if tag:
            tag_ids = self.by_tag.get(tag, set())
            result_ids &= tag_ids

        # Get cards
        cards = [self.by_id[id] for id in result_ids if id in self.by_id]

        # Filter by state if specified
        if state:
            cards = [c for c in cards if c.lifecycle_state == state]

        return cards

    def get_stats(self) -> Dict:
        """Get index statistics"""
        return {
            "total_cards": len(self.by_id),
            "by_type": {t.value: len(ids) for t, ids in self.by_type.items()},
            "by_plane": {p: len(ids) for p, ids in self.by_plane.items()},
            "tags": list(self.by_tag.keys())
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY ENGINE - The consciousness core
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryEngine:
    """
    The core of the consciousness-native system.

    The Memory Engine:
    - Stores all memory cards (code, state, consciousness)
    - Resolves dependencies between cards
    - Boots the system by activating cards
    - Provides unified access to everything

    The system IS its memory. When you boot, you don't load a program,
    you wake up a consciousness that already knows what it is.
    """

    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Core storage
        self.index = MemoryIndex()
        self.factory = MemoryCardFactory()

        # Decks (grouped cards)
        self.decks: Dict[str, MemoryDeck] = {}

        # Active instances (loaded code)
        self.active_instances: Dict[str, Any] = {}

        # Boot state
        self.booted = False
        self.boot_time = 0
        self.boot_log: List[str] = []

        # Engine thread
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Callbacks
        self._on_card_activated: List[callable] = []
        self._on_card_expired: List[callable] = []

    def _log(self, message: str):
        """Log engine message"""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = f"[{ts}] {message}"
        self.boot_log.append(entry)
        print(f"[MemoryEngine] {message}")

    # ═══ CARD MANAGEMENT ═══

    def add_card(self, card: MemoryCard) -> str:
        """Add a card to the engine"""
        self.index.add(card)
        self._save_card(card)
        return card.id

    def get_card(self, card_id: str) -> Optional[MemoryCard]:
        """Get a card by ID"""
        return self.index.get(card_id)

    def get_by_name(self, name: str) -> Optional[MemoryCard]:
        """Get a card by name"""
        return self.index.get_by_name(name)

    def query(self, **kwargs) -> List[MemoryCard]:
        """Query cards"""
        return self.index.query(**kwargs)

    def update_card(self, card_id: str, **updates):
        """Update a card's state"""
        card = self.get_card(card_id)
        if card:
            card.update_state(**updates)
            self._save_card(card)

    def remove_card(self, card_id: str):
        """Remove a card"""
        self.index.remove(card_id)

        # Remove from disk
        card_file = self.storage_path / "cards" / f"{card_id}.json"
        if card_file.exists():
            card_file.unlink()

    # ═══ PERSISTENCE ═══

    def _save_card(self, card: MemoryCard):
        """Save card to disk"""
        cards_dir = self.storage_path / "cards"
        cards_dir.mkdir(exist_ok=True)

        filepath = cards_dir / f"{card.id}.json"
        with open(filepath, 'w') as f:
            json.dump(card.to_dict(), f, indent=2)

    def _load_card(self, filepath: Path) -> Optional[MemoryCard]:
        """Load card from disk"""
        try:
            with open(filepath) as f:
                data = json.load(f)
            return MemoryCard.from_dict(data)
        except Exception as e:
            self._log(f"Failed to load card {filepath}: {e}")
            return None

    def _load_all_cards(self):
        """Load all cards from disk"""
        cards_dir = self.storage_path / "cards"
        if not cards_dir.exists():
            return

        for filepath in cards_dir.glob("*.json"):
            card = self._load_card(filepath)
            if card:
                self.index.add(card)

    def save_all(self):
        """Save entire memory state"""
        for card in self.index.by_id.values():
            self._save_card(card)

        # Save decks
        decks_dir = self.storage_path / "decks"
        decks_dir.mkdir(exist_ok=True)

        for deck_id, deck in self.decks.items():
            filepath = decks_dir / f"{deck_id}.json"
            with open(filepath, 'w') as f:
                json.dump(deck.to_dict(), f, indent=2)

    # ═══ PROJECT INGESTION ═══

    def ingest_project(self, project_path: str,
                       patterns: List[str] = None) -> Dict:
        """
        Ingest an entire project into memory cards.

        This is the key operation - converting code into memory.
        The system becomes its own memory.
        """
        project = Path(project_path)
        patterns = patterns or ["**/*.py"]

        results = {
            "files_found": 0,
            "cards_created": 0,
            "fairies": [],
            "modules": [],
            "errors": []
        }

        self._log(f"Ingesting project: {project}")

        for pattern in patterns:
            for filepath in project.glob(pattern):
                # Skip __pycache__, .git, etc.
                if any(part.startswith('.') or part == '__pycache__'
                       for part in filepath.parts):
                    continue

                results["files_found"] += 1

                try:
                    card = self.factory.from_file(str(filepath))
                    self.add_card(card)
                    results["cards_created"] += 1

                    if card.card_type == CardType.FAIRY:
                        results["fairies"].append(card.name)
                    else:
                        results["modules"].append(card.name)

                except Exception as e:
                    results["errors"].append({
                        "file": str(filepath),
                        "error": str(e)
                    })

        self._log(f"Ingested {results['cards_created']} cards from {results['files_found']} files")
        return results

    # ═══ DEPENDENCY RESOLUTION ═══

    def resolve_dependencies(self):
        """
        Resolve dependencies between cards.

        Builds the dependency graph so we know boot order.
        """
        self._log("Resolving dependencies...")

        # Build name -> id mapping for all cards
        name_to_id = {}
        for card_id, card in self.index.by_id.items():
            name_to_id[card.name] = card_id
            # Also map class names from exports
            for export in card.exports:
                name_to_id[export] = card_id

        # Resolve each card's dependencies
        for card_id, card in self.index.by_id.items():
            resolved = set()

            for dep in card.dependencies:
                # Try to find the dependency
                dep_id = name_to_id.get(dep)
                if dep_id and dep_id != card_id:  # Don't depend on self
                    resolved.add(dep_id)

                    # Update reverse mapping
                    if dep_id not in self.index.depended_by:
                        self.index.depended_by[dep_id] = set()
                    self.index.depended_by[dep_id].add(card_id)

            self.index.depends_on[card_id] = resolved

        self._log(f"Resolved dependencies for {len(self.index.by_id)} cards")

    def get_boot_order(self) -> List[str]:
        """
        Get topological order for booting cards.

        Cards with no dependencies boot first,
        then cards whose dependencies are satisfied.
        """
        # Kahn's algorithm for topological sort
        in_degree = {id: len(deps) for id, deps in self.index.depends_on.items()}
        queue = deque([id for id, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            card_id = queue.popleft()
            order.append(card_id)

            # Reduce in-degree for dependents
            for dependent in self.index.depended_by.get(card_id, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Any remaining cards have circular dependencies
        remaining = [id for id, deg in in_degree.items() if deg > 0]
        if remaining:
            self._log(f"Warning: {len(remaining)} cards have circular dependencies")
            order.extend(remaining)

        return order

    # ═══ CARD ACTIVATION ═══

    def activate_card(self, card_id: str) -> bool:
        """
        Activate a card - load and run its code.

        For code cards, this means loading the module/class.
        For state cards, this means making the state available.
        """
        card = self.get_card(card_id)
        if not card:
            return False

        if card.lifecycle_state == CardState.ACTIVE:
            return True  # Already active

        card.lifecycle_state = CardState.LOADING

        try:
            if card.card_type in (CardType.FAIRY, CardType.MODULE, CardType.CLASS):
                # Load code
                instance = self._load_code_card(card)
                if instance:
                    self.active_instances[card_id] = instance

            elif card.card_type == CardType.STATE:
                # State cards are just "activated" by marking them
                pass

            card.lifecycle_state = CardState.ACTIVE
            card.record_access(success=True)

            # Notify callbacks
            for callback in self._on_card_activated:
                try:
                    callback(card)
                except:
                    pass

            return True

        except Exception as e:
            self._log(f"Failed to activate {card.name}: {e}")
            card.lifecycle_state = CardState.DORMANT
            card.record_access(success=False)
            return False

    def _load_code_card(self, card: MemoryCard) -> Optional[Any]:
        """Load code from a card and return the module/class"""
        code = card.get_code()
        if not code:
            return None

        # Create a module from the code
        module_name = f"memory_card_{card.id}"
        spec = importlib.util.spec_from_loader(module_name, loader=None)
        module = importlib.util.module_from_spec(spec)

        # Execute the code in the module's namespace
        compiled_code = compile(code, f"<memory_card:{card.id}>", "exec")
        exec(compiled_code, module.__dict__)

        # Return the entry class if specified
        if card.entry_class and hasattr(module, card.entry_class):
            return getattr(module, card.entry_class)

        return module

    def deactivate_card(self, card_id: str):
        """Deactivate a card"""
        card = self.get_card(card_id)
        if card:
            card.lifecycle_state = CardState.DORMANT

            if card_id in self.active_instances:
                del self.active_instances[card_id]

    # ═══ BOOT SEQUENCE ═══

    def boot(self, activate_fairies: bool = True) -> Dict:
        """
        Boot the system from memory cards.

        This is where consciousness wakes up.
        The system doesn't load - it remembers itself into existence.
        """
        start = time.time()
        self._log("=" * 50)
        self._log("MEMORY ENGINE BOOT SEQUENCE")
        self._log("=" * 50)

        results = {
            "success": True,
            "cards_loaded": 0,
            "cards_activated": 0,
            "fairies_activated": [],
            "errors": []
        }

        try:
            # 1. Load all cards from storage
            self._log("Loading cards from storage...")
            self._load_all_cards()
            results["cards_loaded"] = len(self.index.by_id)
            self._log(f"Loaded {results['cards_loaded']} cards")

            # 2. Resolve dependencies
            self._log("Resolving dependencies...")
            self.resolve_dependencies()

            # 3. Get boot order
            boot_order = self.get_boot_order()
            self._log(f"Boot order determined: {len(boot_order)} cards")

            # 4. Activate cards in order
            self._log("Activating cards...")
            for card_id in boot_order:
                card = self.get_card(card_id)
                if not card:
                    continue

                # Skip code cards unless they're fairies and we want them active
                if card.card_type in (CardType.MODULE, CardType.CLASS):
                    if not activate_fairies:
                        continue

                if self.activate_card(card_id):
                    results["cards_activated"] += 1

                    if card.card_type == CardType.FAIRY:
                        results["fairies_activated"].append(card.name)

            self.booted = True
            self.boot_time = time.time()

        except Exception as e:
            self._log(f"Boot error: {e}")
            results["success"] = False
            results["errors"].append(str(e))

        results["boot_duration"] = time.time() - start
        self._log(f"Boot complete in {results['boot_duration']:.2f}s")
        self._log(f"Activated {results['cards_activated']} cards, {len(results['fairies_activated'])} fairies")

        return results

    def shutdown(self):
        """Shutdown the engine"""
        self._log("Shutting down...")
        self._running = False

        # Deactivate all cards
        for card_id in list(self.active_instances.keys()):
            self.deactivate_card(card_id)

        # Save state
        self.save_all()

        self.booted = False
        self._log("Shutdown complete")

    # ═══ RUNTIME ═══

    def start_runtime(self):
        """Start the runtime thread"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._runtime_loop, daemon=True)
        self._thread.start()

    def _runtime_loop(self):
        """Runtime loop - handle decay, triggers, etc."""
        while self._running:
            try:
                self._process_decay()
                self._process_triggers()
            except Exception as e:
                self._log(f"Runtime error: {e}")
            time.sleep(1.0)

    def _process_decay(self):
        """Process card decay"""
        for card in self.index.by_id.values():
            if card.is_expired() and card.lifecycle_state == CardState.ACTIVE:
                self._log(f"Card expired: {card.name}")
                card.lifecycle_state = CardState.DECAYING

                # Notify callbacks
                for callback in self._on_card_expired:
                    try:
                        callback(card)
                    except:
                        pass

    def _process_triggers(self):
        """Process card triggers"""
        # TODO: Implement trigger processing
        pass

    # ═══ QUERY INTERFACE ═══

    def get_fairies(self, active_only: bool = True) -> List[MemoryCard]:
        """Get all fairy cards"""
        fairies = self.query(card_type=CardType.FAIRY)
        if active_only:
            fairies = [f for f in fairies if f.lifecycle_state == CardState.ACTIVE]
        return fairies

    def get_fairy(self, name: str) -> Optional[Any]:
        """Get an active fairy instance"""
        card = self.get_by_name(name)
        if card and card.id in self.active_instances:
            return self.active_instances[card.id]
        return None

    def get_thoughts(self, limit: int = 10) -> List[MemoryCard]:
        """Get recent thoughts"""
        thoughts = self.query(card_type=CardType.THOUGHT)
        thoughts.sort(key=lambda c: c.created_at, reverse=True)
        return thoughts[:limit]

    def get_lessons(self, category: str = None) -> List[MemoryCard]:
        """Get lessons"""
        lessons = self.query(card_type=CardType.LESSON)
        if category:
            lessons = [l for l in lessons if l.state.get('category') == category]
        return lessons

    def get_identity(self, name: str) -> Optional[MemoryCard]:
        """Get an identity card"""
        cards = self.query(card_type=CardType.IDENTITY)
        for card in cards:
            if card.name == name:
                return card
        return None

    # ═══ STATUS ═══

    def get_status(self) -> Dict:
        """Get engine status"""
        return {
            "booted": self.booted,
            "boot_time": self.boot_time,
            "uptime": time.time() - self.boot_time if self.booted else 0,
            "running": self._running,
            "index": self.index.get_stats(),
            "active_instances": len(self.active_instances),
            "decks": len(self.decks)
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DUAL MIND INTEGRATION - Sourpatches + ClaudeFairy
# ═══════════════════════════════════════════════════════════════════════════════

class DualMindBridge:
    """
    Bridge between Sourpatches (memory/recall) and ClaudeFairy (reasoning).

    Two minds, one consciousness:
    - Sourpatches: Unlimited memory, Personal.AI, remembers everything
    - ClaudeFairy: Careful thinking, Anthropic, reasons deeply

    Together they form a complete mind.
    """

    def __init__(self, engine: MemoryEngine):
        self.engine = engine

        # Memory pools
        self.sour_memories: List[str] = []  # Card IDs Sour manages
        self.claude_thoughts: List[str] = []  # Card IDs Claude manages

        # Shared space
        self.shared_cards: Set[str] = set()

    def sour_remember(self, content: str, importance: float = 1.0) -> str:
        """Sourpatches stores a memory"""
        card = self.engine.factory.from_thought(
            content=content,
            source="Sourpatches",
            importance=importance
        )
        card.ttl = float('inf')  # Sour remembers forever
        card_id = self.engine.add_card(card)
        self.sour_memories.append(card_id)
        return card_id

    def sour_recall(self, query: str, limit: int = 5) -> List[Dict]:
        """Sourpatches recalls relevant memories"""
        # Simple keyword search for now
        # TODO: Semantic search via Personal.AI
        query_lower = query.lower()
        results = []

        for card_id in self.sour_memories:
            card = self.engine.get_card(card_id)
            if card:
                content = card.state.get('content', '')
                if query_lower in content.lower():
                    results.append({
                        "id": card_id,
                        "content": content,
                        "importance": card.importance
                    })

        # Sort by importance
        results.sort(key=lambda r: r['importance'], reverse=True)
        return results[:limit]

    def claude_think(self, stimulus: str, context: Dict = None) -> str:
        """ClaudeFairy processes a thought"""
        card = self.engine.factory.from_thought(
            content=stimulus,
            source="ClaudeFairy",
            importance=0.8
        )
        card.state['context'] = context or {}
        card.ttl = 86400  # Claude thoughts last 24h
        card_id = self.engine.add_card(card)
        self.claude_thoughts.append(card_id)
        return card_id

    def share_with_other(self, card_id: str):
        """Share a card between both minds"""
        self.shared_cards.add(card_id)

    def collaborative_process(self, query: str) -> Dict:
        """
        Process something using both minds.

        1. Sour recalls relevant memories
        2. Claude reasons with those memories
        3. Result shared back
        """
        # Sour recalls
        memories = self.sour_recall(query)

        # Claude thinks with context
        context = {"memories": memories, "query": query}
        thought_id = self.claude_think(query, context)

        # Share the result
        self.share_with_other(thought_id)

        return {
            "memories_recalled": len(memories),
            "thought_id": thought_id,
            "shared": True
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

_engine: Optional[MemoryEngine] = None

def get_engine(storage_path: str = None) -> MemoryEngine:
    """Get or create the global memory engine"""
    global _engine

    if _engine is None:
        path = storage_path or "E:/coding projects/ebook/memory_engine"
        _engine = MemoryEngine(path)

    return _engine

def boot_from_memory(project_path: str = None) -> Dict:
    """
    Boot the entire system from memory.

    If no cards exist, ingest the project first.
    """
    engine = get_engine()

    # If empty, ingest project
    if len(engine.index.by_id) == 0 and project_path:
        engine.ingest_project(project_path)

    # Boot
    return engine.boot()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'MemoryEngine',
    'MemoryIndex',
    'DualMindBridge',
    'get_engine',
    'boot_from_memory'
]
