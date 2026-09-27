# reflection_pool.py — Core Reflection Infrastructure
# ═══════════════════════════════════════════════════════════════════════════════
# INFRA: This is foundational infrastructure, not app-level functionality.
#
# The ReflectionPool is where fairies send thoughts for pondering.
# Unlike immediate processing, reflections marinate - they accumulate,
# cross-reference, and eventually crystallize into learning traces.
#
# Biological analog: The "default mode network" - the brain's idle processing
# that integrates experiences when you're not focused on tasks.
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import uuid
import json
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

# Optional numpy for tensor operations
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False


@dataclass
class Reflection:
    """
    A single reflection - a thought sent for pondering.
    
    Reflections are not immediate responses. They're observations about:
    - What happened (observation)
    - What was expected vs actual (delta)
    - What emotional resonance occurred (affect)
    - What might be learned (hypothesis)
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # Source identification
    source_fairy: str = ""
    source_action: str = ""
    source_context: Dict[str, Any] = field(default_factory=dict)
    
    # The reflection content
    observation: str = ""                    # What happened
    expected: Optional[str] = None           # What was expected
    actual: Optional[str] = None             # What actually occurred
    delta: Optional[str] = None              # The gap/surprise
    hypothesis: Optional[str] = None         # What might be learned
    
    # Affect metadata
    affect: Dict[str, Any] = field(default_factory=lambda: {
        "valence": 0.0,      # -1 to +1 (negative to positive)
        "arousal": 0.0,      # 0 to 1 (calm to activated)
        "resonance": [],     # emotional tags
    })
    
    # Lifecycle tracking
    created_at: float = field(default_factory=time.time)
    pondered_count: int = 0                  # How many times this was considered
    crystallized: bool = False               # Has this become a learning trace?
    crystallized_at: Optional[float] = None
    
    # Linkage
    related_reflections: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_fairy": self.source_fairy,
            "source_action": self.source_action,
            "source_context": self.source_context,
            "observation": self.observation,
            "expected": self.expected,
            "actual": self.actual,
            "delta": self.delta,
            "hypothesis": self.hypothesis,
            "affect": self.affect,
            "created_at": self.created_at,
            "pondered_count": self.pondered_count,
            "crystallized": self.crystallized,
            "crystallized_at": self.crystallized_at,
            "related_reflections": self.related_reflections,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Reflection":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class ReflectionPool:
    """
    The pool where reflections accumulate and marinate.
    
    Core responsibilities:
    1. Accept reflections from fairies
    2. Find related reflections (pattern detection)
    3. Age reflections (pondering increases with time)
    4. Crystallize mature reflections into learning traces
    5. Prune stale reflections that never crystallized
    
    This is the "slow thinking" system - it doesn't respond immediately,
    it accumulates and integrates over time.
    """
    
    def __init__(
        self,
        max_pool_size: int = 1000,
        crystallization_threshold: int = 3,      # Ponder count to crystallize
        crystallization_age_sec: float = 300.0,  # Min age before crystallization
        prune_after_sec: float = 3600.0,         # Prune if not crystallized after this
        on_crystallize: Optional[Callable[[Reflection], None]] = None,
    ):
        self._pool: Dict[str, Reflection] = {}
        self._lock = threading.RLock()
        self._max_size = max_pool_size
        self._crystallization_threshold = crystallization_threshold
        self._crystallization_age = crystallization_age_sec
        self._prune_after = prune_after_sec
        self._on_crystallize = on_crystallize
        
        # Index structures for fast lookup
        self._by_fairy: Dict[str, List[str]] = {}     # fairy_name -> [reflection_ids]
        self._by_tag: Dict[str, List[str]] = {}       # tag -> [reflection_ids]
        self._recent: deque = deque(maxlen=100)       # Recent reflection IDs
        
        # Crystallization queue
        self._crystallization_queue: deque = deque(maxlen=50)
    
    def reflect(
        self,
        source_fairy: str,
        observation: str,
        *,
        source_action: str = "",
        source_context: Optional[Dict[str, Any]] = None,
        expected: Optional[str] = None,
        actual: Optional[str] = None,
        hypothesis: Optional[str] = None,
        affect: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Reflection:
        """
        Submit a reflection to the pool.
        
        This is the primary interface for fairies to reflect on their actions.
        """
        # Compute delta if we have expected and actual
        delta = None
        if expected and actual and expected != actual:
            delta = f"Expected: {expected[:100]}... Got: {actual[:100]}..."
        
        reflection = Reflection(
            source_fairy=source_fairy,
            source_action=source_action,
            source_context=source_context or {},
            observation=observation,
            expected=expected,
            actual=actual,
            delta=delta,
            hypothesis=hypothesis,
            affect=affect or {"valence": 0.0, "arousal": 0.0, "resonance": []},
            tags=tags or [],
        )
        
        with self._lock:
            # Find related reflections before adding
            related = self._find_related_unlocked(reflection)
            reflection.related_reflections = [r.id for r in related[:5]]
            
            # Add to pool
            self._pool[reflection.id] = reflection
            self._recent.append(reflection.id)
            
            # Update indices
            if source_fairy not in self._by_fairy:
                self._by_fairy[source_fairy] = []
            self._by_fairy[source_fairy].append(reflection.id)
            
            for tag in reflection.tags:
                if tag not in self._by_tag:
                    self._by_tag[tag] = []
                self._by_tag[tag].append(reflection.id)
            
            # Increment ponder count on related reflections
            for rel in related:
                rel.pondered_count += 1
            
            # Prune if over max size
            if len(self._pool) > self._max_size:
                self._prune_oldest_unlocked()
        
        return reflection
    
    def ponder(self, reflection_id: str) -> Optional[Reflection]:
        """
        Explicitly ponder a reflection, incrementing its consideration count.
        """
        with self._lock:
            r = self._pool.get(reflection_id)
            if r:
                r.pondered_count += 1
                self._check_crystallization(r)
            return r
    
    def ponder_cycle(self, n: int = 10) -> List[Reflection]:
        """
        Run a pondering cycle on the N oldest non-crystallized reflections.
        
        This is meant to be called periodically (e.g., by a shadow thread)
        to simulate the "marinating" of reflections over time.
        """
        now = time.time()
        pondered = []
        
        with self._lock:
            # Get oldest non-crystallized reflections
            candidates = [
                r for r in self._pool.values()
                if not r.crystallized
            ]
            candidates.sort(key=lambda r: r.created_at)
            
            for r in candidates[:n]:
                r.pondered_count += 1
                pondered.append(r)
                
                # Check if ready to crystallize
                age = now - r.created_at
                if (r.pondered_count >= self._crystallization_threshold 
                    and age >= self._crystallization_age):
                    self._crystallize_unlocked(r)
        
        return pondered
    
    def get_crystallized(self, limit: int = 20) -> List[Reflection]:
        """Get recently crystallized reflections (ready to become learning traces)."""
        with self._lock:
            return list(self._crystallization_queue)[:limit]
    
    def pop_crystallized(self) -> Optional[Reflection]:
        """Pop the oldest crystallized reflection for processing into a learning trace."""
        with self._lock:
            if self._crystallization_queue:
                return self._crystallization_queue.popleft()
            return None
    
    def get_by_fairy(self, fairy_name: str, limit: int = 20) -> List[Reflection]:
        """Get reflections from a specific fairy."""
        with self._lock:
            ids = self._by_fairy.get(fairy_name, [])[-limit:]
            return [self._pool[rid] for rid in ids if rid in self._pool]
    
    def get_by_tag(self, tag: str, limit: int = 20) -> List[Reflection]:
        """Get reflections with a specific tag."""
        with self._lock:
            ids = self._by_tag.get(tag, [])[-limit:]
            return [self._pool[rid] for rid in ids if rid in self._pool]
    
    def find_related(self, reflection: Reflection, limit: int = 5) -> List[Reflection]:
        """Find reflections related to the given one."""
        with self._lock:
            return self._find_related_unlocked(reflection)[:limit]
    
    def _find_related_unlocked(self, reflection: Reflection) -> List[Reflection]:
        """Find related reflections (must hold lock)."""
        scores: Dict[str, float] = {}
        
        for rid, r in self._pool.items():
            if rid == reflection.id:
                continue
            
            score = 0.0
            
            # Same fairy boost
            if r.source_fairy == reflection.source_fairy:
                score += 0.3
            
            # Same action boost
            if r.source_action == reflection.source_action:
                score += 0.2
            
            # Tag overlap
            common_tags = set(r.tags) & set(reflection.tags)
            score += 0.1 * len(common_tags)
            
            # Recency boost (more recent = higher)
            age_hours = (time.time() - r.created_at) / 3600
            if age_hours < 1:
                score += 0.2
            elif age_hours < 24:
                score += 0.1
            
            # Text similarity (simple word overlap)
            if r.observation and reflection.observation:
                words_r = set(r.observation.lower().split())
                words_ref = set(reflection.observation.lower().split())
                overlap = len(words_r & words_ref)
                score += 0.05 * min(overlap, 5)
            
            if score > 0:
                scores[rid] = score
        
        # Sort by score descending
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [self._pool[rid] for rid in sorted_ids if rid in self._pool]
    
    def _check_crystallization(self, r: Reflection):
        """Check if a reflection is ready to crystallize (must hold lock)."""
        if r.crystallized:
            return
        
        now = time.time()
        age = now - r.created_at
        
        if (r.pondered_count >= self._crystallization_threshold 
            and age >= self._crystallization_age):
            self._crystallize_unlocked(r)
    
    def _crystallize_unlocked(self, r: Reflection):
        """Mark a reflection as crystallized (must hold lock)."""
        if r.crystallized:
            return
        
        r.crystallized = True
        r.crystallized_at = time.time()
        self._crystallization_queue.append(r)
        
        # Call callback if registered
        if self._on_crystallize:
            try:
                self._on_crystallize(r)
            except Exception:
                pass
    
    def _prune_oldest_unlocked(self):
        """Prune oldest non-crystallized reflections (must hold lock)."""
        now = time.time()
        to_prune = []
        
        for rid, r in self._pool.items():
            age = now - r.created_at
            if not r.crystallized and age > self._prune_after:
                to_prune.append(rid)
        
        # Also prune if over max size (oldest first)
        if len(self._pool) - len(to_prune) > self._max_size:
            remaining = [
                (rid, r) for rid, r in self._pool.items()
                if rid not in to_prune and not r.crystallized
            ]
            remaining.sort(key=lambda x: x[1].created_at)
            excess = len(self._pool) - len(to_prune) - self._max_size
            for rid, _ in remaining[:excess]:
                to_prune.append(rid)
        
        for rid in to_prune:
            r = self._pool.pop(rid, None)
            if r:
                # Clean up indices
                if r.source_fairy in self._by_fairy:
                    try:
                        self._by_fairy[r.source_fairy].remove(rid)
                    except ValueError:
                        pass
                for tag in r.tags:
                    if tag in self._by_tag:
                        try:
                            self._by_tag[tag].remove(rid)
                        except ValueError:
                            pass
    
    def prune_cycle(self):
        """Run a pruning cycle to clean up old reflections."""
        with self._lock:
            self._prune_oldest_unlocked()
    
    def stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            total = len(self._pool)
            crystallized = sum(1 for r in self._pool.values() if r.crystallized)
            by_fairy_counts = {k: len(v) for k, v in self._by_fairy.items()}
            
            return {
                "total_reflections": total,
                "crystallized": crystallized,
                "pending": total - crystallized,
                "crystallization_queue": len(self._crystallization_queue),
                "by_fairy": by_fairy_counts,
                "unique_tags": len(self._by_tag),
            }


# ═══════════════════════════════════════════════════════════════════════════════
# Global pool instance (can be overridden)
# ═══════════════════════════════════════════════════════════════════════════════

_global_pool: Optional[ReflectionPool] = None
_pool_lock = threading.Lock()

def get_reflection_pool() -> ReflectionPool:
    """Get or create the global reflection pool."""
    global _global_pool
    with _pool_lock:
        if _global_pool is None:
            _global_pool = ReflectionPool()
        return _global_pool

def set_reflection_pool(pool: ReflectionPool):
    """Set a custom global reflection pool."""
    global _global_pool
    with _pool_lock:
        _global_pool = pool
