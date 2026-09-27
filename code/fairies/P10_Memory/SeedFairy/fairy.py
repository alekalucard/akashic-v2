"""
SeedFairy - Creative Element Storage System

"Every creation is a remix of beautiful seeds."

Seeds are atoms of creative content:
- Clothing items (dresses, outfits, accessories)
- Scenery elements (sunsets, forests, cityscapes)
- Poses and gestures
- Art styles and aesthetics
- Emotional tones

These seeds can be combined to generate new media.
"""

from __future__ import annotations

import sys
import json
import uuid
import hashlib
import threading
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Set, Tuple

# V2 fairy template
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# TracerWorkerMixin is optional - fallback to empty class if not available
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        """Fallback empty mixin when tracer system not available."""
        pass


# Storage directory for seeds
SEED_STORAGE = ROOT / "SRM_Intake" / "seeds"


# =============================================================================
# SEED DATA STRUCTURES
# =============================================================================

@dataclass
class MemorySeed:
    """A reusable creative element - the atom of visual/creative memory."""

    id: str
    schema_ver: str = "1.0"

    # Core content
    objects: List[str] = field(default_factory=list)  # What things are in this seed
    relations: List[str] = field(default_factory=list)  # How they relate
    semantics: Dict[str, float] = field(default_factory=dict)  # Meaning weights

    # Context hints
    time_hint: float = 0.0  # Temporal context
    emotion_hint: str = "neutral"  # Emotional tone
    style_hint: str = ""  # Art style

    # 77-frequency alignment (for future resonance matching)
    resonance: Dict[str, float] = field(default_factory=dict)

    # Provenance
    source: str = "unknown"  # Where this came from
    created_at: str = ""  # ISO timestamp
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MemorySeed":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SeedQuery:
    """Query parameters for seed retrieval."""

    keywords: List[str] = field(default_factory=list)
    emotion: Optional[str] = None
    style: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    max_results: int = 10
    min_score: float = 0.0


# =============================================================================
# SEED INDEX
# =============================================================================

class SeedIndex:
    """Index seeds by keywords for fast retrieval."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._keyword_map: Dict[str, set] = defaultdict(set)  # keyword -> seed_ids
        self._tag_map: Dict[str, set] = defaultdict(set)  # tag -> seed_ids
        self._seeds: Dict[str, MemorySeed] = {}  # id -> seed
        self._lock = threading.RLock()

        self._load_index()

    def _load_index(self):
        """Load existing seeds from storage."""
        index_file = self.storage_path / "seed_index.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for seed_dict in data.get("seeds", []):
                    seed = MemorySeed.from_dict(seed_dict)
                    self._index_seed(seed)
                print(f"[SeedIndex] Loaded {len(self._seeds)} seeds")
            except Exception as e:
                print(f"[SeedIndex] Load failed: {e}")

    def _save_index(self):
        """Persist index to storage."""
        index_file = self.storage_path / "seed_index.json"
        try:
            data = {
                "schema_ver": "1.0",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "seeds": [s.to_dict() for s in self._seeds.values()],
            }
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[SeedIndex] Save failed: {e}")

    def _index_seed(self, seed: MemorySeed):
        """Add seed to all relevant indices."""
        self._seeds[seed.id] = seed

        # Index by objects and relations as keywords
        for obj in seed.objects:
            for word in obj.lower().split():
                self._keyword_map[word].add(seed.id)
        for rel in seed.relations:
            for word in rel.lower().split():
                self._keyword_map[word].add(seed.id)

        # Index by semantics
        for key in seed.semantics:
            self._keyword_map[key.lower()].add(seed.id)

        # Index by tags
        for tag in seed.tags:
            self._tag_map[tag.lower()].add(seed.id)

    def add(self, seed: MemorySeed) -> str:
        """Add a new seed to the index."""
        with self._lock:
            if not seed.id:
                seed.id = f"seed-{uuid.uuid4().hex[:12]}"
            if not seed.created_at:
                seed.created_at = datetime.now(timezone.utc).isoformat()
            self._index_seed(seed)
            self._save_index()
            return seed.id

    def query(self, q: SeedQuery) -> List[Tuple[MemorySeed, float]]:
        """Query seeds by keywords, returning (seed, score) tuples."""
        with self._lock:
            scores: Dict[str, float] = defaultdict(float)

            # Score by keyword matches
            for kw in q.keywords:
                for word in kw.lower().split():
                    for sid in self._keyword_map.get(word, set()):
                        scores[sid] += 1.0

            # Boost by tag matches
            for tag in q.tags:
                for sid in self._tag_map.get(tag.lower(), set()):
                    scores[sid] += 2.0  # Tags are more specific

            # Filter by emotion if specified
            if q.emotion:
                emotion_lower = q.emotion.lower()
                for sid in list(scores.keys()):
                    seed = self._seeds.get(sid)
                    if seed and seed.emotion_hint.lower() != emotion_lower:
                        scores[sid] *= 0.5  # Penalize non-matching emotion

            # Sort and filter
            results = [
                (self._seeds[sid], score)
                for sid, score in sorted(scores.items(), key=lambda x: -x[1])
                if score >= q.min_score and sid in self._seeds
            ]

            return results[: q.max_results]

    def get(self, seed_id: str) -> Optional[MemorySeed]:
        """Get a specific seed by ID."""
        return self._seeds.get(seed_id)

    def count(self) -> int:
        return len(self._seeds)


# =============================================================================
# SEED FAIRY
# =============================================================================

class SeedFairy(Fairy):
    """
    Manages creative seeds - reusable elements for media generation.

    Seeds are the "wardrobe department" - storing clothing, scenery,
    poses, styles, and other elements that can be combined.
    """

    ACTOR_NAME = "SeedFairy"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.seed"
    NEEDS_HEARTBEAT = False  # No periodic work needed
    NEEDS_TENSOR = False

    PURPOSE = "Store and retrieve reusable creative elements"
    MANTRA = "Every creation is a remix of beautiful seeds"

    def __init__(self, fabric=None, storage_path: Path = None, **kwargs):
        super().__init__(fabric, **kwargs)
        self._init_tracer_worker()

        # Default storage in SRM_Intake/seeds
        if storage_path is None:
            storage_path = SEED_STORAGE
        self.storage_path = storage_path

        self.index = SeedIndex(storage_path)
        print(f"[{self.ACTOR_NAME}] Initialized with {self.index.count()} seeds")

    def get_capabilities(self) -> Set[str]:
        return {
            "seed.extract",
            "seed.query",
            "seed.get",
            "seed.status",
        }

    def on_boot(self) -> bool:
        """Boot the seed fairy."""
        # Subscribe to visual trait extraction events
        if self.post:
            self.post.subscribe(
                "visual.traits.extracted",
                self._on_visual_traits,
                "seed_visual_handler",
            )
        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # =========================================================================
    # INTENTS
    # =========================================================================

    def intent_extract(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract a seed from content.

        params:
            text: str - Content to extract from
            objects: List[str] - Objects/items found
            relations: List[str] - Relationships
            emotion: str - Emotional tone
            style: str - Art style
            tags: List[str] - Classification tags
            source: str - Where this came from
        """
        try:
            seed = MemorySeed(
                id="",  # Will be generated
                objects=params.get("objects", []),
                relations=params.get("relations", []),
                semantics=params.get("semantics", {}),
                emotion_hint=params.get("emotion", "neutral"),
                style_hint=params.get("style", ""),
                tags=params.get("tags", []),
                source=params.get("source", "manual"),
            )

            # Extract keywords from text if provided
            text = params.get("text", "")
            if text:
                # Simple extraction - split into keywords
                words = [w.strip().lower() for w in text.split() if len(w) > 3]
                for word in words[:20]:  # Limit to 20 keywords
                    seed.semantics[word] = seed.semantics.get(word, 0) + 1.0

            seed_id = self.index.add(seed)

            return {"ok": True, "seed_id": seed_id, "seed": seed.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def intent_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query for matching seeds.

        params:
            keywords: List[str] - Search terms
            emotion: str - Filter by emotion
            style: str - Filter by style
            tags: List[str] - Filter by tags
            max_results: int - Limit results
        """
        try:
            query = SeedQuery(
                keywords=params.get("keywords", []),
                emotion=params.get("emotion"),
                style=params.get("style"),
                tags=params.get("tags", []),
                max_results=params.get("max_results", 10),
            )

            results = self.index.query(query)

            return {
                "ok": True,
                "count": len(results),
                "seeds": [{"seed": s.to_dict(), "score": score} for s, score in results],
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def intent_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get a specific seed by ID."""
        seed_id = params.get("seed_id", params.get("id", ""))
        seed = self.index.get(seed_id)
        if seed:
            return {"ok": True, "seed": seed.to_dict()}
        return {"ok": False, "error": "Seed not found"}

    def intent_status(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get seed system status."""
        return {
            "ok": True,
            "seed_count": self.index.count(),
            "storage_path": str(self.index.storage_path),
        }

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_visual_traits(self, envelope) -> None:
        """Handle visual.traits.extracted events - auto-create seeds."""
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        self.intent_extract({
            "objects": payload.get("objects", []),
            "relations": payload.get("relations", []),
            "emotion": payload.get("emotion", "neutral"),
            "style": payload.get("style", ""),
            "tags": payload.get("tags", ["visual", "auto-extracted"]),
            "source": "visual_traits",
        })

    # =========================================================================
    # STATUS
    # =========================================================================

    def status(self) -> Dict[str, Any]:
        """Get seed fairy status."""
        base = super().status()
        base.update({
            "seed_count": self.index.count(),
            "storage_path": str(self.storage_path),
        })
        return base


# =============================================================================
# SINGLETON
# =============================================================================

_seed_fairy: Optional[SeedFairy] = None
_seed_fairy_lock = threading.Lock()


def get_seed_fairy() -> SeedFairy:
    """Get singleton SeedFairy instance."""
    global _seed_fairy
    if _seed_fairy is None:
        with _seed_fairy_lock:
            if _seed_fairy is None:
                _seed_fairy = SeedFairy()
                _seed_fairy.boot()
    return _seed_fairy


def set_seed_fairy(fairy: SeedFairy) -> None:
    """Set the global seed fairy instance."""
    global _seed_fairy
    _seed_fairy = fairy
