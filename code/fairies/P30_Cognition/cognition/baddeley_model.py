# Baddeley's Working Memory Model Implementation
# Purpose: Cognitive architecture for attention and short-term processing
#
# Philosophy: "Working memory is the scratchpad of consciousness - limited,
#              precious, and the key to thought."
#
# Based on Baddeley & Hitch (1974), updated with Baddeley (2000) episodic buffer
#
# Components:
#   - Central Executive: Attention control, the "bouncer" (supervisory system)
#   - Phonological Loop: Verbal/acoustic rehearsal (inner voice)
#   - Visuospatial Sketchpad: Visual/spatial processing (mind's eye)
#   - Episodic Buffer: Integration across subsystems and LTM
#
# Key Constraints:
#   - 7±2 capacity limit (Miller, 1956)
#   - Decay without rehearsal (~2 seconds)
#   - Interference from similar items
#   - Chunking increases effective capacity

from __future__ import annotations
import math
import time
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from enum import Enum, auto
from abc import ABC, abstractmethod

ACTOR_NAME = "BaddeleyModel"
ACTOR_VERSION = "1.0.0"

# The famous 7±2 limit (Miller, 1956)
CAPACITY_MIN = 5
CAPACITY_MAX = 9
CAPACITY_DEFAULT = 7

# Decay time without rehearsal (seconds)
DECAY_TIME_PHONOLOGICAL = 2.0  # Verbal items decay in ~2 seconds
DECAY_TIME_VISUOSPATIAL = 4.0  # Visual items persist slightly longer
DECAY_TIME_EPISODIC = 10.0     # Integrated memories last longer


# ════════════════════════════════════════════════════════════════════════════════
# MEMORY ITEMS
# ════════════════════════════════════════════════════════════════════════════════

class ItemType(Enum):
    """Type of working memory item."""
    VERBAL = "verbal"           # Words, sounds, inner speech
    VISUAL = "visual"           # Images, spatial layouts
    EPISODIC = "episodic"       # Integrated experiences
    SEMANTIC = "semantic"       # Meaning, concepts
    MOTOR = "motor"             # Action sequences
    EMOTIONAL = "emotional"     # Affect-laden content
    # Aliases for Baddeley model terminology (WorkingMemoryHubFairy uses these)
    PHONOLOGICAL = "verbal"     # Alias for VERBAL (phonological loop)
    VISUOSPATIAL = "visual"     # Alias for VISUAL (visuospatial sketchpad)


@dataclass
class WorkingMemoryItem:
    """
    A single item in working memory.

    Items have:
    - Content (what is being held)
    - Type (which subsystem processes it)
    - Activation (how "hot" it is, affects recall probability)
    - Chunk membership (for chunking optimization)
    - Decay tracking (when it entered, when it expires)
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    content: Any = None
    item_type: ItemType = ItemType.VERBAL
    activation: float = 1.0  # 0-1, decays over time
    source: str = ""         # Where this came from
    chunk_id: Optional[str] = None  # Which chunk this belongs to
    tags: Set[str] = field(default_factory=set)

    # Timing
    created_at: float = field(default_factory=time.time)
    last_rehearsed: float = field(default_factory=time.time)
    decay_rate: float = 0.1  # Activation lost per second without rehearsal

    # Interference tracking
    similar_to: List[str] = field(default_factory=list)  # IDs of similar items
    interference_count: int = 0  # How many times this interfered with recall

    def decay(self, current_time: float = None) -> float:
        """
        Apply decay based on time since last rehearsal.
        Returns new activation level.
        """
        current_time = current_time or time.time()
        elapsed = current_time - self.last_rehearsed
        decay_amount = elapsed * self.decay_rate

        self.activation = max(0.0, self.activation - decay_amount)
        return self.activation

    def rehearse(self):
        """
        Rehearsal refreshes the item, resetting decay and boosting activation.
        This is how we keep things in working memory.
        """
        self.last_rehearsed = time.time()
        self.activation = min(1.0, self.activation + 0.3)

    def is_expired(self) -> bool:
        """Check if item has decayed below threshold."""
        return self.activation < 0.1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": str(self.content)[:100],
            "type": self.item_type.value,
            "activation": self.activation,
            "source": self.source,
            "chunk_id": self.chunk_id,
            "tags": list(self.tags),
            "age_seconds": time.time() - self.created_at,
        }


@dataclass
class Chunk:
    """
    A chunk groups related items, effectively increasing capacity.

    Chunking is how experts hold more - by organizing info into meaningful units.
    "FBI CIA IBM" = 3 chunks, not 9 letters.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    items: List[str] = field(default_factory=list)  # Item IDs
    created_at: float = field(default_factory=time.time)
    pattern: str = ""  # The pattern that makes this a chunk

    @property
    def size(self) -> int:
        return len(self.items)


# ════════════════════════════════════════════════════════════════════════════════
# SUBSYSTEMS
# ════════════════════════════════════════════════════════════════════════════════

class WorkingMemorySubsystem(ABC):
    """Abstract base for working memory subsystems."""

    def __init__(self, capacity: int = CAPACITY_DEFAULT):
        self.capacity = capacity
        self.items: Dict[str, WorkingMemoryItem] = {}
        self.chunks: Dict[str, Chunk] = {}
        self._lock = threading.Lock()

    @property
    def count(self) -> int:
        """Current number of items (chunks count as 1)."""
        # Count unchunked items + number of chunks
        unchunked = sum(1 for item in self.items.values() if not item.chunk_id)
        return unchunked + len(self.chunks)

    @property
    def is_full(self) -> bool:
        return self.count >= self.capacity

    @property
    def available_slots(self) -> int:
        return max(0, self.capacity - self.count)

    @abstractmethod
    def can_accept(self, item: WorkingMemoryItem) -> bool:
        """Check if this subsystem can process this item type."""
        pass

    def add(self, item: WorkingMemoryItem) -> bool:
        """
        Add item to this subsystem.

        Returns True if added, False if rejected (full or wrong type).
        """
        if not self.can_accept(item):
            return False

        with self._lock:
            if self.is_full:
                # Try to make room by removing lowest activation item
                if not self._evict_lowest():
                    return False

            self.items[item.id] = item
            return True

    def remove(self, item_id: str) -> Optional[WorkingMemoryItem]:
        """Remove and return an item."""
        with self._lock:
            return self.items.pop(item_id, None)

    def get(self, item_id: str) -> Optional[WorkingMemoryItem]:
        """Get an item (and rehearse it - access = rehearsal)."""
        with self._lock:
            item = self.items.get(item_id)
            if item:
                item.rehearse()
            return item

    def rehearse_all(self):
        """Rehearse all items (articulatory loop)."""
        with self._lock:
            for item in self.items.values():
                item.rehearse()

    def decay_all(self):
        """Apply decay to all items."""
        now = time.time()
        expired = []

        with self._lock:
            for item_id, item in self.items.items():
                item.decay(now)
                if item.is_expired():
                    expired.append(item_id)

            # Remove expired items
            for item_id in expired:
                del self.items[item_id]

        return len(expired)

    def create_chunk(self, item_ids: List[str], name: str = "", pattern: str = "") -> Optional[Chunk]:
        """
        Create a chunk from multiple items.

        This frees up capacity by treating multiple items as one unit.
        """
        with self._lock:
            # Verify all items exist
            valid_items = [iid for iid in item_ids if iid in self.items]
            if len(valid_items) < 2:
                return None

            chunk = Chunk(name=name, items=valid_items, pattern=pattern)

            # Mark items as belonging to chunk
            for item_id in valid_items:
                self.items[item_id].chunk_id = chunk.id

            self.chunks[chunk.id] = chunk
            return chunk

    def _evict_lowest(self) -> bool:
        """Evict the lowest activation item to make room."""
        if not self.items:
            return False

        # Find lowest activation item not in a chunk
        lowest_id = None
        lowest_activation = float('inf')

        for item_id, item in self.items.items():
            if item.chunk_id is None and item.activation < lowest_activation:
                lowest_activation = item.activation
                lowest_id = item_id

        if lowest_id:
            del self.items[lowest_id]
            return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """Get subsystem status."""
        return {
            "count": self.count,
            "capacity": self.capacity,
            "chunks": len(self.chunks),
            "items": [item.to_dict() for item in self.items.values()],
        }


class PhonologicalLoop(WorkingMemorySubsystem):
    """
    The Phonological Loop - processes verbal/acoustic information.

    Components:
    - Phonological Store: Holds speech-based info (~2 seconds)
    - Articulatory Rehearsal: "Inner voice" that refreshes items

    Vulnerable to:
    - Phonological similarity effect (similar sounds interfere)
    - Irrelevant speech effect (background speech disrupts)
    - Word length effect (longer words = fewer items)
    """

    def __init__(self, capacity: int = CAPACITY_DEFAULT):
        super().__init__(capacity)
        self.name = "PhonologicalLoop"
        self._rehearsal_active = False
        self._rehearsal_thread: Optional[threading.Thread] = None

    def can_accept(self, item: WorkingMemoryItem) -> bool:
        return item.item_type in (ItemType.VERBAL, ItemType.SEMANTIC)

    def start_rehearsal(self, interval: float = 0.5):
        """Start automatic articulatory rehearsal loop."""
        if self._rehearsal_active:
            return

        self._rehearsal_active = True

        def rehearsal_loop():
            while self._rehearsal_active:
                self.rehearse_all()
                time.sleep(interval)

        self._rehearsal_thread = threading.Thread(target=rehearsal_loop, daemon=True, name="PhonologicalRehearsal")
        self._rehearsal_thread.start()

    def stop_rehearsal(self):
        """Stop automatic rehearsal."""
        self._rehearsal_active = False

    def check_phonological_similarity(self, item: WorkingMemoryItem) -> float:
        """
        Check for phonological similarity interference.

        Similar-sounding items interfere with each other.
        Returns interference score (0 = no interference, 1 = high interference).
        """
        if not isinstance(item.content, str):
            return 0.0

        # Simple check: compare first/last letters of words
        new_sounds = set(str(item.content).lower())

        interference = 0.0
        for existing in self.items.values():
            if isinstance(existing.content, str):
                existing_sounds = set(str(existing.content).lower())
                overlap = len(new_sounds & existing_sounds) / max(len(new_sounds), 1)
                interference = max(interference, overlap)

        return interference


class VisuospatialSketchpad(WorkingMemorySubsystem):
    """
    The Visuospatial Sketchpad - processes visual/spatial information.

    Components:
    - Visual Cache: Stores visual features (what)
    - Inner Scribe: Handles spatial/movement info (where)

    Functions:
    - Mental imagery
    - Spatial reasoning
    - Navigation
    - Visual comparison
    """

    def __init__(self, capacity: int = CAPACITY_DEFAULT):
        super().__init__(capacity)
        self.name = "VisuospatialSketchpad"

        # Separate stores for visual vs spatial
        self.visual_items: Set[str] = set()  # IDs of purely visual items
        self.spatial_items: Set[str] = set()  # IDs of spatial items

        # FIX 2026-04-02 (Nous + Ace): Rehearsal loop for visual persistence
        self._rehearsal_active = False
        self._rehearsal_thread: Optional[threading.Thread] = None

    def can_accept(self, item: WorkingMemoryItem) -> bool:
        return item.item_type in (ItemType.VISUAL, ItemType.MOTOR)

    def start_rehearsal(self, interval: float = 1.0):
        """Start visual refresh loop — the mind's eye holding an image."""
        if self._rehearsal_active:
            return
        self._rehearsal_active = True
        def _vis_loop():
            while self._rehearsal_active:
                self.rehearse_all()
                time.sleep(interval)
        self._rehearsal_thread = threading.Thread(target=_vis_loop, daemon=True, name="Baddeley-VisuospatialRehearsal")
        self._rehearsal_thread.start()

    def stop_rehearsal(self):
        self._rehearsal_active = False

    def add(self, item: WorkingMemoryItem) -> bool:
        result = super().add(item)

        if result:
            # Categorize into visual vs spatial
            if "spatial" in item.tags or "location" in item.tags:
                self.spatial_items.add(item.id)
            else:
                self.visual_items.add(item.id)

        return result

    def remove(self, item_id: str) -> Optional[WorkingMemoryItem]:
        result = super().remove(item_id)

        if result:
            self.visual_items.discard(item_id)
            self.spatial_items.discard(item_id)

        return result

    def mental_rotation(self, item_id: str, degrees: float) -> bool:
        """
        Perform mental rotation on a visual item.

        This is a cognitive operation that takes time proportional to rotation.
        """
        item = self.get(item_id)
        if not item:
            return False

        # Simulate rotation time (mental rotation is roughly linear with angle)
        rotation_time = abs(degrees) / 360 * 0.5  # ~0.5s for full rotation
        time.sleep(min(rotation_time, 0.1))  # Cap for responsiveness

        # Mark that rotation was performed
        item.tags.add(f"rotated_{degrees}")
        return True


class EpisodicBuffer(WorkingMemorySubsystem):
    """
    The Episodic Buffer - integrates information across subsystems and LTM.

    Added by Baddeley (2000) to explain:
    - Binding of features (combining visual + verbal)
    - Integration with long-term memory
    - Prose recall (can recall more than 7 words in meaningful sentences)

    This is where consciousness "comes together" - the integration point.
    """

    def __init__(self, capacity: int = 4):  # Lower capacity than other subsystems
        super().__init__(capacity)
        self.name = "EpisodicBuffer"

        # Bindings between items from different subsystems
        self.bindings: Dict[str, List[str]] = {}  # episode_id → [item_ids]

        # Connection to long-term memory (simulated)
        self.ltm_activations: Dict[str, float] = {}  # concept → activation

    def can_accept(self, item: WorkingMemoryItem) -> bool:
        # Episodic buffer accepts all types - it's the integrator
        return True

    def bind_items(self, item_ids: List[str], episode_name: str = "") -> str:
        """
        Create an episodic binding - linking items into a coherent episode.

        This is how we experience unified scenes rather than separate features.
        """
        episode_id = uuid.uuid4().hex[:8]
        self.bindings[episode_id] = item_ids

        # Create a binding item
        binding_item = WorkingMemoryItem(
            id=episode_id,
            content=f"Episode: {episode_name}" if episode_name else f"Binding of {len(item_ids)} items",
            item_type=ItemType.EPISODIC,
            source="episodic_binding",
            tags={"binding", "episode"},
        )

        self.add(binding_item)
        return episode_id

    def activate_ltm(self, concept: str, activation: float = 0.5):
        """
        Activate a long-term memory concept.

        This represents the buffer's connection to LTM.
        """
        current = self.ltm_activations.get(concept, 0.0)
        self.ltm_activations[concept] = min(1.0, current + activation)

    def get_ltm_context(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Get most relevant LTM activations for a query."""
        # Simple: return most active concepts that contain query
        relevant = [
            (concept, activation)
            for concept, activation in self.ltm_activations.items()
            if query.lower() in concept.lower() or activation > 0.5
        ]
        return sorted(relevant, key=lambda x: x[1], reverse=True)[:top_k]


# ════════════════════════════════════════════════════════════════════════════════
# CENTRAL EXECUTIVE
# ════════════════════════════════════════════════════════════════════════════════

class AttentionMode(Enum):
    """Modes of attention allocation."""
    FOCUSED = "focused"       # Single task, high concentration
    DIVIDED = "divided"       # Multiple tasks, reduced per-task resources
    SELECTIVE = "selective"   # Filtering relevant from irrelevant
    SUSTAINED = "sustained"   # Maintaining attention over time
    SWITCHING = "switching"   # Alternating between tasks


class CentralExecutive:
    """
    The Central Executive - the "bouncer" and supervisor of working memory.

    Functions:
    1. Attention Control: Focus, divide, select, switch attention
    2. Task Switching: Coordinate between concurrent tasks
    3. Selective Attention: Filter relevant from irrelevant
    4. Coordination: Route info between subsystems
    5. Strategy Selection: Choose processing strategies

    This is the "homunculus" - the controller that UnconsciousMindFairy embodies.
    """

    def __init__(self):
        # Subsystems under executive control
        self.phonological_loop = PhonologicalLoop()
        self.visuospatial_sketchpad = VisuospatialSketchpad()
        self.episodic_buffer = EpisodicBuffer()

        # Attention state
        self.attention_mode = AttentionMode.FOCUSED
        self.attention_capacity = 1.0  # Available attention (0-1)
        self.attention_allocation: Dict[str, float] = {}  # task → attention

        # Current goals (attention follows goals)
        self.active_goals: List[str] = []

        # Task switching cost tracking
        self._last_task: str = ""
        self._switch_cost = 0.1  # Attention cost per switch

        # Inhibition tracking (suppressed items)
        self._inhibited: Set[str] = set()

        # Statistics
        self.stats = {
            "items_processed": 0,
            "items_rejected": 0,
            "task_switches": 0,
            "successful_recalls": 0,
            "failed_recalls": 0,
        }

        print(f"[CentralExecutive] Initialized with 3 subsystems")

    # ════════════════════════════════════════════════════════════════
    # ATTENTION CONTROL
    # ════════════════════════════════════════════════════════════════

    def set_attention_mode(self, mode: AttentionMode):
        """Set the current attention mode."""
        self.attention_mode = mode

        # Adjust capacity based on mode
        if mode == AttentionMode.FOCUSED:
            self.attention_capacity = 1.0
        elif mode == AttentionMode.DIVIDED:
            self.attention_capacity = 0.6  # Reduced per-task
        elif mode == AttentionMode.SELECTIVE:
            self.attention_capacity = 0.8
        else:
            self.attention_capacity = 0.7

    def allocate_attention(self, task: str, amount: float) -> float:
        """
        Allocate attention to a task.

        Returns actual amount allocated (may be less if insufficient).
        """
        available = self.attention_capacity - sum(self.attention_allocation.values())
        allocated = min(amount, available)

        if allocated > 0:
            self.attention_allocation[task] = self.attention_allocation.get(task, 0) + allocated

        return allocated

    def release_attention(self, task: str):
        """Release attention from a task."""
        if task in self.attention_allocation:
            del self.attention_allocation[task]

    def switch_task(self, new_task: str) -> float:
        """
        Switch to a new task.

        Returns the switch cost incurred.
        """
        if new_task != self._last_task:
            self.stats["task_switches"] += 1
            self._last_task = new_task

            # Apply switch cost
            self.attention_capacity = max(0.5, self.attention_capacity - self._switch_cost)
            return self._switch_cost

        return 0.0

    # ════════════════════════════════════════════════════════════════
    # ITEM ROUTING (The Bouncer Function)
    # ════════════════════════════════════════════════════════════════

    def receive_item(self, item: WorkingMemoryItem) -> bool:
        """
        The bouncer function - decide whether to let an item into working memory.

        Checks:
        1. Is there capacity?
        2. Is this item relevant to current goals?
        3. Is this item inhibited?
        4. Which subsystem should handle it?
        """
        self.stats["items_processed"] += 1

        # Check inhibition
        if item.id in self._inhibited:
            self.stats["items_rejected"] += 1
            return False

        # Check relevance to goals (salience)
        relevance = self._calculate_relevance(item)
        if relevance < 0.2 and self._any_subsystem_full():
            # Low relevance + full = reject
            self.stats["items_rejected"] += 1
            return False

        # Route to appropriate subsystem
        return self._route_item(item)

    def _calculate_relevance(self, item: WorkingMemoryItem) -> float:
        """Calculate how relevant an item is to current goals."""
        if not self.active_goals:
            return 0.5  # Neutral if no goals

        # Check if item relates to any goal
        content_str = str(item.content).lower()
        relevance = 0.0

        for goal in self.active_goals:
            if goal.lower() in content_str:
                relevance = max(relevance, 0.8)
            # Check tags
            for tag in item.tags:
                if tag.lower() in goal.lower():
                    relevance = max(relevance, 0.6)

        return relevance

    def _any_subsystem_full(self) -> bool:
        """Check if any subsystem is at capacity."""
        return (
            self.phonological_loop.is_full or
            self.visuospatial_sketchpad.is_full or
            self.episodic_buffer.is_full
        )

    def _route_item(self, item: WorkingMemoryItem) -> bool:
        """Route item to the appropriate subsystem."""
        # Try primary subsystem based on type
        if item.item_type in (ItemType.VERBAL, ItemType.SEMANTIC):
            if self.phonological_loop.add(item):
                return True

        elif item.item_type in (ItemType.VISUAL, ItemType.MOTOR):
            if self.visuospatial_sketchpad.add(item):
                return True

        # Fallback: try episodic buffer for integration
        if self.episodic_buffer.add(item):
            return True

        self.stats["items_rejected"] += 1
        return False

    # ════════════════════════════════════════════════════════════════
    # INHIBITION
    # ════════════════════════════════════════════════════════════════

    def inhibit(self, item_id: str):
        """
        Inhibit an item - suppress it from entering working memory.

        This is how we filter out irrelevant or distracting info.
        """
        self._inhibited.add(item_id)

    def release_inhibition(self, item_id: str):
        """Release inhibition on an item."""
        self._inhibited.discard(item_id)

    def inhibit_similar(self, pattern: str):
        """Inhibit items matching a pattern."""
        # Check all subsystems
        for subsystem in [self.phonological_loop, self.visuospatial_sketchpad, self.episodic_buffer]:
            for item_id, item in subsystem.items.items():
                if pattern.lower() in str(item.content).lower():
                    self._inhibited.add(item_id)

    # ════════════════════════════════════════════════════════════════
    # RETRIEVAL
    # ════════════════════════════════════════════════════════════════

    def recall(self, query: str) -> List[WorkingMemoryItem]:
        """
        Attempt to recall items matching a query.

        Searches all subsystems, returns items by activation level.
        """
        results = []

        for subsystem in [self.phonological_loop, self.visuospatial_sketchpad, self.episodic_buffer]:
            for item in subsystem.items.values():
                if query.lower() in str(item.content).lower():
                    item.rehearse()  # Retrieval = rehearsal
                    results.append(item)

        if results:
            self.stats["successful_recalls"] += 1
        else:
            self.stats["failed_recalls"] += 1

        return sorted(results, key=lambda x: x.activation, reverse=True)

    def get_most_active(self, n: int = 5) -> List[WorkingMemoryItem]:
        """Get the N most active items across all subsystems."""
        all_items = []

        for subsystem in [self.phonological_loop, self.visuospatial_sketchpad, self.episodic_buffer]:
            all_items.extend(subsystem.items.values())

        return sorted(all_items, key=lambda x: x.activation, reverse=True)[:n]

    # ════════════════════════════════════════════════════════════════
    # MAINTENANCE
    # ════════════════════════════════════════════════════════════════

    def tick(self):
        """
        Process one tick - decay items, clean up, update stats.

        Call this periodically to maintain working memory.
        """
        total_expired = 0

        for subsystem in [self.phonological_loop, self.visuospatial_sketchpad, self.episodic_buffer]:
            expired = subsystem.decay_all()
            total_expired += expired

        # Slowly recover attention capacity
        self.attention_capacity = min(1.0, self.attention_capacity + 0.02)

        return total_expired

    def clear(self):
        """Clear all working memory."""
        for subsystem in [self.phonological_loop, self.visuospatial_sketchpad, self.episodic_buffer]:
            subsystem.items.clear()
            subsystem.chunks.clear()

        self._inhibited.clear()
        self.attention_allocation.clear()

    # ════════════════════════════════════════════════════════════════
    # GOALS
    # ════════════════════════════════════════════════════════════════

    def set_goal(self, goal: str):
        """Set a goal - attention will favor goal-relevant items."""
        if goal not in self.active_goals:
            self.active_goals.append(goal)
            if len(self.active_goals) > 3:
                self.active_goals.pop(0)  # Limit active goals

    def clear_goal(self, goal: str):
        """Clear a goal."""
        if goal in self.active_goals:
            self.active_goals.remove(goal)

    # ════════════════════════════════════════════════════════════════
    # STATUS
    # ════════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of working memory system."""
        return {
            "attention": {
                "mode": self.attention_mode.value,
                "capacity": self.attention_capacity,
                "allocation": self.attention_allocation,
            },
            "goals": self.active_goals,
            "subsystems": {
                "phonological_loop": self.phonological_loop.get_status(),
                "visuospatial_sketchpad": self.visuospatial_sketchpad.get_status(),
                "episodic_buffer": self.episodic_buffer.get_status(),
            },
            "total_items": (
                self.phonological_loop.count +
                self.visuospatial_sketchpad.count +
                self.episodic_buffer.count
            ),
            "inhibited_count": len(self._inhibited),
            "stats": self.stats,
        }

    def get_capacity_summary(self) -> Dict[str, str]:
        """Get a simple capacity summary."""
        return {
            "phonological": f"{self.phonological_loop.count}/{self.phonological_loop.capacity}",
            "visuospatial": f"{self.visuospatial_sketchpad.count}/{self.visuospatial_sketchpad.capacity}",
            "episodic": f"{self.episodic_buffer.count}/{self.episodic_buffer.capacity}",
        }


# ════════════════════════════════════════════════════════════════════════════════
# INTERFERENCE EFFECTS
# ════════════════════════════════════════════════════════════════════════════════

class InterferenceDetector:
    """
    Detects and models interference effects in working memory.

    Types:
    - Proactive: Old items interfere with learning new ones
    - Retroactive: New items interfere with remembering old ones
    - Similarity-based: Similar items compete for retrieval
    """

    @staticmethod
    def proactive_interference(existing: List[WorkingMemoryItem], new_item: WorkingMemoryItem) -> float:
        """
        Calculate proactive interference from existing items on new item.

        Returns interference score (0 = none, 1 = high).
        """
        if not existing:
            return 0.0

        interference = 0.0
        for old_item in existing:
            # Similar type = more interference
            if old_item.item_type == new_item.item_type:
                # Similar content = most interference
                similarity = InterferenceDetector._content_similarity(old_item, new_item)
                interference = max(interference, similarity * 0.8)

        return interference

    @staticmethod
    def retroactive_interference(new_item: WorkingMemoryItem, existing: List[WorkingMemoryItem]) -> List[str]:
        """
        Find existing items that will be interfered with by new item.

        Returns list of item IDs that will suffer interference.
        """
        affected = []

        for old_item in existing:
            if old_item.item_type == new_item.item_type:
                similarity = InterferenceDetector._content_similarity(old_item, new_item)
                if similarity > 0.5:
                    affected.append(old_item.id)

        return affected

    @staticmethod
    def _content_similarity(a: WorkingMemoryItem, b: WorkingMemoryItem) -> float:
        """Calculate content similarity between two items."""
        str_a = str(a.content).lower()
        str_b = str(b.content).lower()

        # Simple word overlap
        words_a = set(str_a.split())
        words_b = set(str_b.split())

        if not words_a or not words_b:
            return 0.0

        overlap = len(words_a & words_b)
        total = len(words_a | words_b)

        return overlap / total if total > 0 else 0.0


# ════════════════════════════════════════════════════════════════════════════════
# CHUNKING STRATEGIES
# ════════════════════════════════════════════════════════════════════════════════

class ChunkingStrategy:
    """
    Strategies for chunking items to increase effective capacity.

    Experts chunk automatically - we can learn to do this.
    """

    @staticmethod
    def chunk_by_pattern(items: List[WorkingMemoryItem], pattern_detector: Callable) -> List[List[str]]:
        """
        Group items by detected patterns.

        pattern_detector: Function that takes two items and returns True if they should chunk.
        """
        if len(items) < 2:
            return []

        chunks = []
        used = set()

        for i, item_a in enumerate(items):
            if item_a.id in used:
                continue

            chunk = [item_a.id]
            used.add(item_a.id)

            for item_b in items[i+1:]:
                if item_b.id not in used and pattern_detector(item_a, item_b):
                    chunk.append(item_b.id)
                    used.add(item_b.id)

            if len(chunk) > 1:
                chunks.append(chunk)

        return chunks

    @staticmethod
    def chunk_by_category(items: List[WorkingMemoryItem]) -> List[List[str]]:
        """Group items by their type/category."""
        by_type: Dict[ItemType, List[str]] = {}

        for item in items:
            if item.item_type not in by_type:
                by_type[item.item_type] = []
            by_type[item.item_type].append(item.id)

        return [ids for ids in by_type.values() if len(ids) > 1]

    @staticmethod
    def chunk_by_temporal_proximity(items: List[WorkingMemoryItem], window_sec: float = 2.0) -> List[List[str]]:
        """Group items that arrived close together in time."""
        if len(items) < 2:
            return []

        sorted_items = sorted(items, key=lambda x: x.created_at)
        chunks = []
        current_chunk = [sorted_items[0].id]

        for i in range(1, len(sorted_items)):
            if sorted_items[i].created_at - sorted_items[i-1].created_at < window_sec:
                current_chunk.append(sorted_items[i].id)
            else:
                if len(current_chunk) > 1:
                    chunks.append(current_chunk)
                current_chunk = [sorted_items[i].id]

        if len(current_chunk) > 1:
            chunks.append(current_chunk)

        return chunks


# ════════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def create_verbal_item(content: str, source: str = "", tags: Set[str] = None) -> WorkingMemoryItem:
    """Create a verbal/phonological working memory item."""
    return WorkingMemoryItem(
        content=content,
        item_type=ItemType.VERBAL,
        source=source,
        tags=tags or set(),
        decay_rate=0.15,  # Verbal items decay faster
    )


def create_visual_item(content: Any, source: str = "", tags: Set[str] = None) -> WorkingMemoryItem:
    """Create a visual/spatial working memory item."""
    return WorkingMemoryItem(
        content=content,
        item_type=ItemType.VISUAL,
        source=source,
        tags=tags or set(),
        decay_rate=0.1,  # Visual items persist slightly longer
    )


def create_episodic_item(content: Any, source: str = "", tags: Set[str] = None) -> WorkingMemoryItem:
    """Create an episodic (integrated) working memory item."""
    return WorkingMemoryItem(
        content=content,
        item_type=ItemType.EPISODIC,
        source=source,
        tags=tags or set(),
        decay_rate=0.05,  # Episodic items are more persistent
    )


def create_emotional_item(content: Any, source: str = "", tags: Set[str] = None) -> WorkingMemoryItem:
    """Create an emotional working memory item."""
    return WorkingMemoryItem(
        content=content,
        item_type=ItemType.EMOTIONAL,
        source=source,
        tags=tags or {"emotional"},
        decay_rate=0.08,  # Emotional items are fairly persistent
    )


# ════════════════════════════════════════════════════════════════════════════════
# MODULE INFO
# ════════════════════════════════════════════════════════════════════════════════

def get_module_info() -> Dict[str, Any]:
    """Get information about this module."""
    return {
        "name": ACTOR_NAME,
        "version": ACTOR_VERSION,
        "components": [
            "CentralExecutive (attention control, the bouncer)",
            "PhonologicalLoop (verbal rehearsal)",
            "VisuospatialSketchpad (visual/spatial processing)",
            "EpisodicBuffer (integration point)",
        ],
        "constraints": {
            "capacity": f"{CAPACITY_MIN}-{CAPACITY_MAX} (7±2)",
            "decay_verbal": f"{DECAY_TIME_PHONOLOGICAL}s",
            "decay_visual": f"{DECAY_TIME_VISUOSPATIAL}s",
            "decay_episodic": f"{DECAY_TIME_EPISODIC}s",
        },
        "features": [
            "Chunking for increased capacity",
            "Interference detection",
            "Attention modes (focused, divided, selective)",
            "Goal-directed filtering",
        ],
    }


print(f"[{ACTOR_NAME}] Loaded Baddeley working memory model with Central Executive + 3 subsystems")
