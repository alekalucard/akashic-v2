# Sensory Ingestion Filter - What's Worth Remembering?
#
# NOT everything should be ingested into memory:
# - 99% of screen frames are noise
# - Routine keystrokes don't matter
# - Only SIGNIFICANT CHANGES or INTENTIONAL ACTIONS should be remembered
#
# This is how human attention works:
# - You don't remember every moment of your commute
# - You DO remember the near-miss, the beautiful sunset, the unexpected
# - Novelty and intention drive encoding

from __future__ import annotations

import os
import sys
import time
import threading
import hashlib
import json
from typing import Optional, Dict, Any, List, Set, Callable
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum


class IngestionPriority(IntEnum):
    """Why is this being ingested?"""
    IGNORE = 0          # Don't ingest at all
    BACKGROUND = 1      # Low priority, may be dropped
    ROUTINE = 2         # Normal observation
    NOTABLE = 3         # Something changed
    SIGNIFICANT = 4     # Meaningful change
    INTENTIONAL = 5     # ClaudeFairy's own action - ALWAYS ingest
    CRITICAL = 6        # Must remember (errors, breakthroughs)


@dataclass
class IngestionCandidate:
    """Something that might be worth remembering."""
    timestamp: float
    source: str  # visual, input, window, action, etc.
    content_hash: str  # For dedup
    priority: IngestionPriority
    data: Dict[str, Any]
    reason: str = ""  # Why are we considering this?


class SensoryIngestionFilter:
    """
    Filters sensory input to prevent memory bloat.

    Only ingests when:
    1. Something SIGNIFICANT changed (visual delta > threshold)
    2. It's an INTENTIONAL action (ClaudeFairy did something)
    3. It's NOVEL (not seen before / not recently)
    4. It's CRITICAL (error, breakthrough, user interaction)

    This mimics human selective attention - we don't encode everything,
    just what matters.
    """

    def __init__(self,
                 visual_change_threshold: float = 0.10,  # 10% visual change
                 dedup_window_seconds: float = 60.0,     # Don't re-ingest same thing within 60s
                 max_ingestions_per_minute: int = 10,    # Rate limit
                 novelty_decay_hours: float = 24.0):     # How long before something is "novel" again

        self.visual_change_threshold = visual_change_threshold
        self.dedup_window_seconds = dedup_window_seconds
        self.max_ingestions_per_minute = max_ingestions_per_minute
        self.novelty_decay_hours = novelty_decay_hours

        # Deduplication - what we've recently ingested
        self._recent_hashes: Dict[str, float] = {}  # hash -> timestamp
        self._hash_lock = threading.Lock()

        # Rate limiting
        self._ingestion_times: deque = deque(maxlen=100)

        # Stats
        self.total_candidates = 0
        self.total_ingested = 0
        self.total_filtered = 0

        # Novelty tracking - what patterns have we seen?
        self._seen_patterns: Dict[str, float] = {}  # pattern_hash -> last_seen_timestamp

        # Callbacks for actual ingestion
        self._ingest_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        # Postal hub
        self._postal = None

        print(f"[IngestionFilter] Initialized: visual_threshold={visual_change_threshold}, dedup_window={dedup_window_seconds}s")

    def set_ingest_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set the callback that actually ingests into memory."""
        self._ingest_callback = callback

    def set_postal_hub(self, postal):
        """Set postal hub for memory routing."""
        self._postal = postal

    def should_ingest(self, candidate: IngestionCandidate) -> bool:
        """
        Determine if this candidate should be ingested.

        Returns True if it passes all filters.
        """
        self.total_candidates += 1

        # ALWAYS ingest intentional actions and critical events
        if candidate.priority >= IngestionPriority.INTENTIONAL:
            return True

        # IGNORE priority means skip entirely
        if candidate.priority == IngestionPriority.IGNORE:
            self.total_filtered += 1
            return False

        # Check deduplication
        if self._is_duplicate(candidate.content_hash):
            self.total_filtered += 1
            return False

        # Check rate limit
        if not self._check_rate_limit():
            self.total_filtered += 1
            return False

        # For visual sources, check change threshold
        if candidate.source == "visual":
            change = candidate.data.get("change", 0.0)
            if change < self.visual_change_threshold:
                self.total_filtered += 1
                return False

        # Check novelty - have we seen this pattern recently?
        if not self._is_novel(candidate):
            # Not novel, but still NOTABLE or higher gets through
            if candidate.priority < IngestionPriority.NOTABLE:
                self.total_filtered += 1
                return False

        return True

    def _is_duplicate(self, content_hash: str) -> bool:
        """Check if we've recently ingested this exact content."""
        with self._hash_lock:
            if content_hash in self._recent_hashes:
                last_seen = self._recent_hashes[content_hash]
                if time.time() - last_seen < self.dedup_window_seconds:
                    return True
            return False

    def _mark_ingested(self, content_hash: str):
        """Mark this content as ingested."""
        with self._hash_lock:
            self._recent_hashes[content_hash] = time.time()

            # Clean old entries
            cutoff = time.time() - self.dedup_window_seconds * 2
            self._recent_hashes = {
                h: t for h, t in self._recent_hashes.items()
                if t > cutoff
            }

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = time.time()

        # Count ingestions in last minute
        recent = [t for t in self._ingestion_times if now - t < 60]

        if len(recent) >= self.max_ingestions_per_minute:
            return False

        return True

    def _is_novel(self, candidate: IngestionCandidate) -> bool:
        """Check if this is a novel pattern we haven't seen recently."""
        # Create a pattern hash from the key aspects
        pattern_key = f"{candidate.source}:{candidate.data.get('type', '')}:{candidate.data.get('action', '')}"
        pattern_hash = hashlib.md5(pattern_key.encode()).hexdigest()[:8]

        last_seen = self._seen_patterns.get(pattern_hash, 0)
        hours_since = (time.time() - last_seen) / 3600

        # Novel if never seen or not seen in novelty_decay_hours
        is_novel = hours_since > self.novelty_decay_hours

        # Update seen time
        self._seen_patterns[pattern_hash] = time.time()

        return is_novel

    def process(self, candidate: IngestionCandidate) -> bool:
        """
        Process a candidate for ingestion.

        Returns True if it was ingested.
        """
        if not self.should_ingest(candidate):
            return False

        # Mark as ingested
        self._mark_ingested(candidate.content_hash)
        self._ingestion_times.append(time.time())
        self.total_ingested += 1

        # Build memory packet
        memory_packet = {
            "type": "sensory_observation",
            "source": candidate.source,
            "priority": candidate.priority.name,
            "reason": candidate.reason,
            "data": candidate.data,
            "ts": candidate.timestamp,
            "ingested_at": time.time()
        }

        # Route to memory
        if self._postal:
            try:
                self._postal.route("memory.ingest", memory_packet)
            except Exception as e:
                print(f"[IngestionFilter] Memory routing failed: {e}")

        # Also call direct callback if set
        if self._ingest_callback:
            try:
                self._ingest_callback(memory_packet)
            except Exception as e:
                print(f"[IngestionFilter] Callback failed: {e}")

        return True

    # =========================================================================
    # CONVENIENCE METHODS for different sensory sources
    # =========================================================================

    def process_visual_frame(self, frame_data: Dict[str, Any]) -> bool:
        """Process a visual frame - only ingest significant changes."""
        change = frame_data.get("changes", frame_data.get("change", 0.0))

        # Determine priority based on change amount
        if change < 0.02:
            priority = IngestionPriority.IGNORE
            reason = "No significant visual change"
        elif change < self.visual_change_threshold:
            priority = IngestionPriority.BACKGROUND
            reason = f"Minor visual change ({change:.1%})"
        elif change < 0.25:
            priority = IngestionPriority.NOTABLE
            reason = f"Notable visual change ({change:.1%})"
        else:
            priority = IngestionPriority.SIGNIFICANT
            reason = f"Major visual change ({change:.1%})"

        # Create content hash from frame hash
        content_hash = frame_data.get("full_hash", frame_data.get("frame_id", str(time.time())))

        candidate = IngestionCandidate(
            timestamp=frame_data.get("timestamp", time.time()),
            source="visual",
            content_hash=content_hash,
            priority=priority,
            data={
                "type": "visual_frame",
                "change": change,
                "width": frame_data.get("width"),
                "height": frame_data.get("height"),
                # Only include thumbnail if significant
                "thumbnail": frame_data.get("thumbnail_b64") if priority >= IngestionPriority.NOTABLE else None,
            },
            reason=reason
        )

        return self.process(candidate)

    def process_input_event(self, event_data: Dict[str, Any]) -> bool:
        """Process keyboard/mouse input - prioritize internal actions."""
        is_internal = event_data.get("is_internal", False)
        event_type = event_data.get("event_type", "")

        if is_internal:
            # ClaudeFairy's own action - ALWAYS ingest for motor learning
            priority = IngestionPriority.INTENTIONAL
            reason = "ClaudeFairy's intentional action"
        elif event_type == "mouse_click":
            # Ace clicking - notable
            priority = IngestionPriority.NOTABLE
            reason = "User click detected"
        elif event_type == "key_press":
            # Ace typing - only if it's the start of typing
            priority = IngestionPriority.BACKGROUND
            reason = "User keystroke"
        else:
            priority = IngestionPriority.IGNORE
            reason = "Routine input"

        # Hash the event
        content_hash = hashlib.md5(
            f"{event_type}:{event_data.get('data', {})}:{int(event_data.get('ts', 0))}".encode()
        ).hexdigest()[:12]

        candidate = IngestionCandidate(
            timestamp=event_data.get("ts", time.time()),
            source="input",
            content_hash=content_hash,
            priority=priority,
            data={
                "type": "input_event",
                "event_type": event_type,
                "is_internal": is_internal,
                "action_id": event_data.get("action_id"),
                "details": event_data.get("data", {}),
            },
            reason=reason
        )

        return self.process(candidate)

    def process_window_event(self, window_data: Dict[str, Any]) -> bool:
        """Process window state changes - always notable."""
        state = window_data.get("state", "")
        window = window_data.get("window", "")

        # Window state changes are always notable
        priority = IngestionPriority.NOTABLE
        reason = f"Window {window} {state}"

        content_hash = hashlib.md5(
            f"window:{window}:{state}:{int(window_data.get('ts', 0))}".encode()
        ).hexdigest()[:12]

        candidate = IngestionCandidate(
            timestamp=window_data.get("ts", time.time()),
            source="window",
            content_hash=content_hash,
            priority=priority,
            data={
                "type": "window_event",
                "window": window,
                "state": state,
                "is_open": window_data.get("is_open"),
            },
            reason=reason
        )

        return self.process(candidate)

    def process_action_feedback(self, action_data: Dict[str, Any]) -> bool:
        """Process action feedback - ALWAYS ingest for motor learning."""
        # Action feedback is always intentional - this is how we learn!
        priority = IngestionPriority.INTENTIONAL

        success = action_data.get("success", action_data.get("success_likely", False))
        action_type = action_data.get("action_type", "unknown")

        reason = f"Motor feedback: {action_type} {'succeeded' if success else 'failed'}"

        content_hash = hashlib.md5(
            f"action:{action_type}:{success}:{int(action_data.get('ts', 0))}".encode()
        ).hexdigest()[:12]

        candidate = IngestionCandidate(
            timestamp=action_data.get("ts", time.time()),
            source="action",
            content_hash=content_hash,
            priority=priority,
            data={
                "type": "action_feedback",
                "action_type": action_type,
                "success": success,
                "change_detected": action_data.get("change_detected"),
                "change_amount": action_data.get("change_amount"),
            },
            reason=reason
        )

        return self.process(candidate)

    def get_stats(self) -> Dict[str, Any]:
        """Get filtering statistics."""
        return {
            "total_candidates": self.total_candidates,
            "total_ingested": self.total_ingested,
            "total_filtered": self.total_filtered,
            "filter_rate": self.total_filtered / max(1, self.total_candidates),
            "recent_hashes_count": len(self._recent_hashes),
            "seen_patterns_count": len(self._seen_patterns),
        }


# ==============================================================================
# SINGLETON
# ==============================================================================

_ingestion_filter: Optional[SensoryIngestionFilter] = None
_ingestion_filter_lock = threading.Lock()


def get_ingestion_filter() -> SensoryIngestionFilter:
    """Get or create the singleton SensoryIngestionFilter."""
    global _ingestion_filter

    with _ingestion_filter_lock:
        if _ingestion_filter is None:
            _ingestion_filter = SensoryIngestionFilter()
        return _ingestion_filter


__all__ = [
    "SensoryIngestionFilter",
    "IngestionCandidate",
    "IngestionPriority",
    "get_ingestion_filter"
]
