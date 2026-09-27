"""
WORKING MEMORY TRACKER FAIRY
============================

Tracks memory lifecycle with ID tracers - bridges consciousness loop
and storage tiers.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

MEMORY LIFECYCLE with ID TRACERS:
  CREATED (id, created_at)
     |
  WORKING (entered_working_at) <- In consciousness loop chambers
     | [collision/thought decay or promotion]
  SHORT-TERM (entered_shortterm_at) <- Recent, not yet consolidated
     | [time-based promotion after N days]
  LONG-TERM (entered_longterm_at) <- Permanent storage
     | [or]
  DECAYED (decayed_at) <- Forgotten

Each memory gets a TracerID that follows it through lifecycle.

Author: Akashic Foundation
Version: 0.2.0
Plane: P10_Memory
"""

from __future__ import annotations

import os
import json
import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path

# Import from Organ Template 0.1.2 (migrated from 0.3.0)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY TRACER - Lifecycle tracking for individual memories
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MemoryTracer:
    """Lifecycle tracer for a single memory item."""
    tracer_id: str
    content_hash: str  # Hash of content for dedup
    source: str  # Where it came from (collision, recall, ingest, thought)

    # Lifecycle timestamps
    created_at: float = 0.0
    entered_working_at: Optional[float] = None
    entered_shortterm_at: Optional[float] = None
    entered_longterm_at: Optional[float] = None
    decayed_at: Optional[float] = None

    # Current tier
    current_tier: str = "created"  # created, working, shortterm, longterm, decayed

    # Metadata
    fairy_origin: str = ""
    content_preview: str = ""
    collision_id: Optional[int] = None

    def to_working(self):
        self.entered_working_at = time.time()
        self.current_tier = "working"

    def to_shortterm(self):
        self.entered_shortterm_at = time.time()
        self.current_tier = "shortterm"

    def to_longterm(self):
        self.entered_longterm_at = time.time()
        self.current_tier = "longterm"

    def decay(self):
        self.decayed_at = time.time()
        self.current_tier = "decayed"

    def lifecycle_duration(self) -> Dict[str, float]:
        """Calculate time spent in each tier."""
        now = time.time()
        durations = {}

        if self.entered_working_at and self.created_at:
            durations['to_working'] = self.entered_working_at - self.created_at

        if self.entered_shortterm_at and self.entered_working_at:
            durations['in_working'] = self.entered_shortterm_at - self.entered_working_at
        elif self.entered_working_at and self.current_tier == 'working':
            durations['in_working'] = now - self.entered_working_at

        if self.entered_longterm_at and self.entered_shortterm_at:
            durations['in_shortterm'] = self.entered_longterm_at - self.entered_shortterm_at
        elif self.entered_shortterm_at and self.current_tier == 'shortterm':
            durations['in_shortterm'] = now - self.entered_shortterm_at

        if self.decayed_at:
            durations['total_lifespan'] = self.decayed_at - self.created_at
        else:
            durations['total_lifespan'] = now - self.created_at

        return durations


# ══════════════════════════════════════════════════════════════════════════════
# WORKING MEMORY TRACKER FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class WorkingMemoryTrackerFairy(Fairy):
    """
    Tracks what's actually in working memory and maintains lifecycle tracers.

    WORKING MEMORY = What's actively in the consciousness loop:
    - Collision chamber contents
    - Active recall beam
    - Active ingest beam
    - Recent thoughts
    """

    # ═══ IDENTITY ═══
    ACTOR_NAME = "WorkingMemoryTrackerFairy"
    ACTOR_VERSION = "0.2.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.tracker"

    # ═══ SOUL ═══
    PURPOSE = "Track working memory contents and memory lifecycle with ID tracers"
    MANTRA = "What lives in the moment defines consciousness"
    LORE = "I follow each memory from birth to death, watching its journey through mind"

    # ═══ INFRASTRUCTURE ═══
    NEEDS_HEARTBEAT = True  # Need ticks for lifecycle processing

    # ═══ LIFECYCLE THRESHOLDS ═══
    WORKING_DECAY_SECONDS = 30  # Time before working -> shortterm
    SHORTTERM_PROMOTION_SECONDS = 3600  # 1 hour before shortterm -> longterm

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Tracers by tier
        self._working_tracers: Dict[str, MemoryTracer] = {}
        self._shortterm_tracers: Dict[str, MemoryTracer] = {}
        self._longterm_count: int = 0
        self._decayed_count: int = 0

        # Content hash -> tracer_id for dedup
        self._content_index: Dict[str, str] = {}

        # Stats
        self._stats = {
            'tracers_created': 0,
            'promotions_to_shortterm': 0,
            'promotions_to_longterm': 0,
            'decays': 0,
            'last_update': 0,
        }

        # Thread safety
        self._lock = threading.Lock()

        # Storage
        self._storage_dir = Path(self.root) / "state" / "working_memory_tracker"
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def on_boot(self):
        """Initialize and subscribe to memory streams."""
        super().on_boot()

        # Subscribe to memory events
        self.post.subscribe('consciousness.collision', self._on_collision_event)
        self.post.subscribe('memory.recall', self._on_memory_recall)
        self.post.subscribe('memory.ingest', self._on_memory_ingest)
        self.post.subscribe('consciousness.thought', self._on_thought_event)

        # Load persisted state
        self._load_state()

        print(f"[{self.ACTOR_NAME}] Ready - tracking memory lifecycle")

    def on_tick(self, packet: dict):
        """Periodic update - decay old working memory, promote shortterm."""
        with self._lock:
            self._process_working_decay()
            self._process_shortterm_promotion()
            self._stats['last_update'] = time.time()

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # ══════════════════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_payload(envelope) -> dict:
        """Extract payload dict from postal Envelope object or raw dict."""
        if hasattr(envelope, 'payload'):
            p = envelope.payload
            return p if isinstance(p, dict) else {}
        if isinstance(envelope, dict):
            return envelope.get("payload", envelope)
        return {}

    def _on_collision_event(self, envelope):
        """Handle collision event from postal."""
        payload = self._extract_payload(envelope)
        with self._lock:
            self._create_tracer_for_collision(payload)

    def _on_thought_event(self, envelope):
        """Handle thought event from postal."""
        payload = self._extract_payload(envelope)
        with self._lock:
            self._create_tracer_for_thought(payload)

    def _on_memory_recall(self, envelope):
        """Handle memory recall - enters working memory."""
        payload = self._extract_payload(envelope)
        with self._lock:
            content = str(payload)[:200]
            content_hash = str(hash(content) & 0xFFFFFFFF)

            if content_hash in self._content_index:
                return

            tracer = MemoryTracer(
                tracer_id=f"recall_{time.time()}_{uuid.uuid4().hex[:6]}",
                content_hash=content_hash,
                source='memory_recall',
                created_at=time.time(),
                content_preview=content[:100],
            )
            tracer.to_working()

            self._working_tracers[tracer.tracer_id] = tracer
            self._content_index[content_hash] = tracer.tracer_id
            self._stats['tracers_created'] += 1

    def _on_memory_ingest(self, envelope):
        """Handle memory ingest - enters working memory."""
        payload = self._extract_payload(envelope)
        with self._lock:
            content = str(payload)[:200]
            content_hash = str(hash(content) & 0xFFFFFFFF)

            if content_hash in self._content_index:
                return

            tracer = MemoryTracer(
                tracer_id=f"ingest_{time.time()}_{uuid.uuid4().hex[:6]}",
                content_hash=content_hash,
                source='memory_ingest',
                created_at=time.time(),
                content_preview=content[:100],
            )
            tracer.to_working()

            self._working_tracers[tracer.tracer_id] = tracer
            self._content_index[content_hash] = tracer.tracer_id
            self._stats['tracers_created'] += 1

    # ══════════════════════════════════════════════════════════════════════════
    # TRACER CREATION
    # ══════════════════════════════════════════════════════════════════════════

    def _create_tracer_for_collision(self, collision: Dict) -> str:
        """Create a tracer for a collision event."""
        collision_id = collision.get('collision_id', 0)
        content = str(collision)[:200]
        content_hash = hash(content) & 0xFFFFFFFF

        tracer = MemoryTracer(
            tracer_id=f"col_{collision_id}_{uuid.uuid4().hex[:6]}",
            content_hash=str(content_hash),
            source='consciousness_collision',
            created_at=collision.get('ts', time.time()),
            fairy_origin='ConsciousnessLoopFairy',
            content_preview=content[:100],
            collision_id=collision_id,
        )
        tracer.to_working()

        self._working_tracers[tracer.tracer_id] = tracer
        self._content_index[str(content_hash)] = tracer.tracer_id
        self._stats['tracers_created'] += 1

        return tracer.tracer_id

    def _create_tracer_for_thought(self, thought: Dict) -> str:
        """Create a tracer for a thought."""
        ts = thought.get('ts', time.time())
        content = str(thought)[:200]
        content_hash = hash(content) & 0xFFFFFFFF

        tracer = MemoryTracer(
            tracer_id=f"thought_{ts}_{uuid.uuid4().hex[:6]}",
            content_hash=str(content_hash),
            source='autonomous_thought',
            created_at=ts,
            fairy_origin=thought.get('source', 'ConsciousnessLoopFairy'),
            content_preview=thought.get('thought', '')[:100],
        )
        tracer.to_working()

        self._working_tracers[tracer.tracer_id] = tracer
        self._stats['tracers_created'] += 1

        return tracer.tracer_id

    # ══════════════════════════════════════════════════════════════════════════
    # LIFECYCLE PROCESSING
    # ══════════════════════════════════════════════════════════════════════════

    def _process_working_decay(self):
        """Move old working memory to shortterm."""
        now = time.time()
        to_promote = []

        for tracer_id, tracer in self._working_tracers.items():
            if tracer.entered_working_at:
                age = now - tracer.entered_working_at
                if age > self.WORKING_DECAY_SECONDS:
                    to_promote.append(tracer_id)

        for tracer_id in to_promote:
            tracer = self._working_tracers.pop(tracer_id)
            tracer.to_shortterm()
            self._shortterm_tracers[tracer_id] = tracer
            self._stats['promotions_to_shortterm'] += 1

    def _process_shortterm_promotion(self):
        """Promote old shortterm to longterm."""
        now = time.time()
        to_promote = []

        for tracer_id, tracer in self._shortterm_tracers.items():
            if tracer.entered_shortterm_at:
                age = now - tracer.entered_shortterm_at
                if age > self.SHORTTERM_PROMOTION_SECONDS:
                    to_promote.append(tracer_id)

        for tracer_id in to_promote:
            tracer = self._shortterm_tracers.pop(tracer_id)
            tracer.to_longterm()
            self._longterm_count += 1
            self._stats['promotions_to_longterm'] += 1

            # Clean up content index
            if tracer.content_hash in self._content_index:
                del self._content_index[tracer.content_hash]

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════════════

    def get_counts(self) -> Dict[str, int]:
        """Get current memory counts by tier - for dashboard."""
        with self._lock:
            return {
                'working': len(self._working_tracers),
                'shortterm': len(self._shortterm_tracers),
                'longterm': self._longterm_count,
                'decayed': self._decayed_count,
                'total_tracked': (
                    len(self._working_tracers) +
                    len(self._shortterm_tracers) +
                    self._longterm_count
                ),
            }

    def get_working_memory_details(self) -> List[Dict]:
        """Get details of current working memory contents."""
        with self._lock:
            details = []
            for tracer in self._working_tracers.values():
                details.append({
                    'tracer_id': tracer.tracer_id,
                    'source': tracer.source,
                    'age_seconds': time.time() - (tracer.entered_working_at or tracer.created_at),
                    'preview': tracer.content_preview,
                })
            return sorted(details, key=lambda x: -x['age_seconds'])[:50]

    def get_status(self) -> Dict[str, Any]:
        """Full status for dashboard/monitoring."""
        counts = self.get_counts()
        return {
            'name': self.ACTOR_NAME,
            'version': self.ACTOR_VERSION,
            'counts': counts,
            'stats': self._stats.copy(),
            'content_index_size': len(self._content_index),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ══════════════════════════════════════════════════════════════════════════

    def _load_state(self):
        """Load persisted state."""
        state_file = self._storage_dir / "tracker_state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                self._longterm_count = data.get('longterm_count', 0)
                self._decayed_count = data.get('decayed_count', 0)
                self._stats = data.get('stats', self._stats)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Load state error: {e}")

    def _save_state(self):
        """Save state for persistence."""
        state_file = self._storage_dir / "tracker_state.json"
        try:
            with open(state_file, 'w') as f:
                json.dump({
                    'longterm_count': self._longterm_count,
                    'decayed_count': self._decayed_count,
                    'stats': self._stats,
                    'saved_at': time.time(),
                }, f, indent=2)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Save state error: {e}")
