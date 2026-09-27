"""
TEMPORAL CONTEXT MANAGER FAIRY
==============================

Maintains the linear narrative of lived experience.
This is the autobiographical thread that connects moments across time.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

What this does:
1. Tags memories with temporal markers (when)
2. Maintains "sessions" - contiguous periods of activity
3. Enables temporal recall: "yesterday...", "last week...", "this morning..."
4. Preserves narrative continuity across shutdowns
5. Tracks conversation threads and their temporal relationships

Author: Akashic Foundation
Version: 0.2.0
Plane: P10_Memory
"""

from __future__ import annotations

import os
import time
import json
import uuid
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from collections import deque
from pathlib import Path

# Import from Organ Template 0.1.2 (migrated from 0.3.0)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


# ══════════════════════════════════════════════════════════════════════════════
# TEMPORAL MARKERS - Human-like time references
# ══════════════════════════════════════════════════════════════════════════════

class TemporalMarker:
    """Convert timestamps to human-like temporal references."""

    @staticmethod
    def describe(ts: float, reference_ts: float = None) -> str:
        """
        Convert timestamp to human temporal description.

        Returns things like:
        - "just now"
        - "a few minutes ago"
        - "this morning"
        - "yesterday afternoon"
        - "last week"
        """
        ref = reference_ts or time.time()
        dt = datetime.fromtimestamp(ts)
        ref_dt = datetime.fromtimestamp(ref)
        delta = ref_dt - dt

        if delta.total_seconds() < 0:
            return "in the future"

        seconds = delta.total_seconds()
        minutes = seconds / 60
        hours = minutes / 60
        days = hours / 24
        weeks = days / 7

        if seconds < 30:
            return "just now"
        if seconds < 90:
            return "a minute ago"
        if minutes < 5:
            return "a few minutes ago"
        if minutes < 30:
            return f"about {int(minutes)} minutes ago"
        if minutes < 90:
            return "about an hour ago"

        if dt.date() == ref_dt.date():
            hour = dt.hour
            if hour < 12:
                return "this morning"
            elif hour < 17:
                return "this afternoon"
            else:
                return "this evening"

        if (ref_dt.date() - dt.date()).days == 1:
            hour = dt.hour
            if hour < 12:
                return "yesterday morning"
            elif hour < 17:
                return "yesterday afternoon"
            else:
                return "yesterday evening"

        if days < 7:
            day_name = dt.strftime("%A")
            return f"on {day_name}"

        if weeks < 2:
            return "last week"
        if weeks < 4:
            return f"about {int(weeks)} weeks ago"

        months = days / 30
        if months < 2:
            return "last month"
        if months < 12:
            return f"about {int(months)} months ago"

        years = days / 365
        if years < 2:
            return "last year"
        return f"about {int(years)} years ago"

    @staticmethod
    def get_session_boundary(ts: float) -> str:
        """Get session identifier for a timestamp."""
        dt = datetime.fromtimestamp(ts)
        hour = dt.hour
        if 5 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 17:
            period = "afternoon"
        elif 17 <= hour < 21:
            period = "evening"
        else:
            period = "night"
        return f"{dt.strftime('%Y-%m-%d')}_{period}"


# ══════════════════════════════════════════════════════════════════════════════
# SESSION - A contiguous period of activity
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Session:
    """A contiguous period of activity (morning, afternoon, evening, night)."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_key: str = ""

    start_ts: float = field(default_factory=time.time)
    end_ts: float = field(default_factory=time.time)

    memory_count: int = 0
    conversation_count: int = 0
    key_topics: List[str] = field(default_factory=list)

    affect_summary: Dict[str, float] = field(default_factory=lambda: {
        "valence": 0.0,
        "arousal": 0.0,
    })

    participants: List[str] = field(default_factory=lambda: ["Ace", "Nous"])
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_key": self.session_key,
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "memory_count": self.memory_count,
            "conversation_count": self.conversation_count,
            "key_topics": self.key_topics,
            "affect_summary": self.affect_summary,
            "participants": self.participants,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Session":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def describe(self, ref_ts: float = None) -> str:
        """Get human description of this session."""
        when = TemporalMarker.describe(self.start_ts, ref_ts)
        duration_mins = (self.end_ts - self.start_ts) / 60
        topics = ", ".join(self.key_topics[:3]) if self.key_topics else "various things"
        return f"{when}: we worked on {topics} ({int(duration_mins)} minutes)"


# ══════════════════════════════════════════════════════════════════════════════
# TEMPORAL MEMORY INDEX
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TemporalMemoryRef:
    """Reference to a memory with temporal metadata."""
    memory_id: str
    timestamp: float
    session_key: str
    content_preview: str = ""
    topics: List[str] = field(default_factory=list)
    affect: Dict[str, float] = field(default_factory=dict)


class TemporalIndex:
    """Index for temporal lookup of memories."""

    def __init__(self, max_entries: int = 10000):
        self._entries: Dict[str, TemporalMemoryRef] = {}
        self._by_session: Dict[str, List[str]] = {}
        self._by_day: Dict[str, List[str]] = {}
        self._chronological: deque = deque(maxlen=max_entries)
        self._lock = threading.RLock()

    def add(self, memory_id: str, timestamp: float, content_preview: str = "",
            topics: List[str] = None, affect: Dict = None):
        """Add a memory to the temporal index."""
        session_key = TemporalMarker.get_session_boundary(timestamp)
        day_key = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

        ref = TemporalMemoryRef(
            memory_id=memory_id,
            timestamp=timestamp,
            session_key=session_key,
            content_preview=content_preview[:100],
            topics=topics or [],
            affect=affect or {},
        )

        with self._lock:
            self._entries[memory_id] = ref
            if session_key not in self._by_session:
                self._by_session[session_key] = []
            self._by_session[session_key].append(memory_id)
            if day_key not in self._by_day:
                self._by_day[day_key] = []
            self._by_day[day_key].append(memory_id)
            self._chronological.append(memory_id)

    def get_by_session(self, session_key: str) -> List[TemporalMemoryRef]:
        with self._lock:
            ids = self._by_session.get(session_key, [])
            return [self._entries[mid] for mid in ids if mid in self._entries]

    def get_by_day(self, day_key: str) -> List[TemporalMemoryRef]:
        with self._lock:
            ids = self._by_day.get(day_key, [])
            return [self._entries[mid] for mid in ids if mid in self._entries]

    def get_recent(self, n: int = 20) -> List[TemporalMemoryRef]:
        with self._lock:
            recent_ids = list(self._chronological)[-n:]
            return [self._entries[mid] for mid in recent_ids if mid in self._entries]

    def get_by_timerange(self, start_ts: float, end_ts: float) -> List[TemporalMemoryRef]:
        with self._lock:
            return [ref for ref in self._entries.values()
                    if start_ts <= ref.timestamp <= end_ts]

    def get_sessions(self) -> List[str]:
        with self._lock:
            return list(self._by_session.keys())


# ══════════════════════════════════════════════════════════════════════════════
# TEMPORAL CONTEXT MANAGER FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class TemporalContextManagerFairy(Fairy):
    """
    Maintains the linear narrative of lived experience.

    Tracks current session, recent sessions, temporal index of all memories,
    and session summaries for quick recall.
    """

    # ═══ IDENTITY ═══
    ACTOR_NAME = "TemporalContextManagerFairy"
    ACTOR_VERSION = "0.2.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.temporal"

    # ═══ SOUL ═══
    PURPOSE = "Maintain autobiographical consciousness - the temporal thread of lived experience"
    MANTRA = "Time is the canvas on which memory paints identity"
    LORE = "I weave moments into narrative, transforming events into story"

    # ═══ STATE PATHS ═══
    SESSIONS_PATH = "state/temporal_sessions.json"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Current session
        self._current_session: Optional[Session] = None
        self._current_session_key: str = ""

        # Session history
        self._sessions: Dict[str, Session] = {}
        self._session_order: deque = deque(maxlen=100)

        # Temporal index
        self._index = TemporalIndex()

        # Active topics
        self._active_topics: deque = deque(maxlen=20)

        # Thread safety
        self._lock = threading.RLock()

        # Persistence path
        self._sessions_path = os.path.join(self.root, self.SESSIONS_PATH)
        Path(self._sessions_path).parent.mkdir(parents=True, exist_ok=True)

    def on_boot(self):
        """Boot the temporal context manager."""
        super().on_boot()

        # Load persisted state
        self._load_state()

        # Start current session
        self._start_session()

        # Subscribe to events via postal
        self.post.subscribe("consciousness.stream", self._on_consciousness_stream)
        self.post.subscribe("memory.ingest.complete", self._on_memory_ingested)
        self.post.subscribe("conversation.message", self._on_conversation_message)
        self.post.subscribe("system.shutdown", self._on_shutdown)

        print(f"[{self.ACTOR_NAME}] Ready - session: {self._current_session_key}")


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def _load_state(self):
        """Load persisted sessions."""
        try:
            if os.path.exists(self._sessions_path):
                with open(self._sessions_path, "r") as f:
                    data = json.load(f)
                    for s in data.get("sessions", []):
                        session = Session.from_dict(s)
                        self._sessions[session.session_key] = session
                        self._session_order.append(session.session_key)
                    print(f"[{self.ACTOR_NAME}] Loaded {len(self._sessions)} sessions")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [WARN] Session load error: {e}")

    def _save_state(self):
        """Save sessions to disk."""
        try:
            sessions_list = [
                self._sessions[key].to_dict()
                for key in self._session_order
                if key in self._sessions
            ]
            with open(self._sessions_path, "w") as f:
                json.dump({"sessions": sessions_list}, f, indent=2)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [WARN] Session save error: {e}")

    def _start_session(self):
        """Start or resume a session."""
        now = time.time()
        session_key = TemporalMarker.get_session_boundary(now)

        with self._lock:
            if session_key in self._sessions:
                self._current_session = self._sessions[session_key]
                self._current_session.end_ts = now
            else:
                self._current_session = Session(
                    session_key=session_key,
                    start_ts=now,
                    end_ts=now,
                )
                self._sessions[session_key] = self._current_session
                self._session_order.append(session_key)

            self._current_session_key = session_key

    def _on_consciousness_stream(self, packet: dict):
        """Handle consciousness stream events."""
        if not isinstance(packet, dict):
            return

        content = packet.get("content") or packet.get("thought", {}).get("content", "")

        if isinstance(content, str) and len(content) > 10:
            words = content.lower().split()
            topics = [w for w in words if len(w) > 5 and w.isalpha()][:3]

            with self._lock:
                for topic in topics:
                    if topic not in self._active_topics:
                        self._active_topics.append(topic)

                if self._current_session:
                    for topic in topics:
                        if topic not in self._current_session.key_topics:
                            self._current_session.key_topics.append(topic)
                            if len(self._current_session.key_topics) > 10:
                                self._current_session.key_topics.pop(0)

    def _on_memory_ingested(self, packet: dict):
        """Handle memory ingestion."""
        if not isinstance(packet, dict):
            return

        memory_id = packet.get("memory_id") or packet.get("id", str(uuid.uuid4()))
        ts = packet.get("ts", time.time())
        content = packet.get("content_preview", "")
        topics = packet.get("topics", [])
        affect = packet.get("affect", {})

        self._index.add(
            memory_id=memory_id,
            timestamp=ts,
            content_preview=content,
            topics=topics,
            affect=affect,
        )

        with self._lock:
            if self._current_session:
                self._current_session.memory_count += 1
                self._current_session.end_ts = ts

    def _on_conversation_message(self, packet: dict):
        """Handle conversation messages."""
        with self._lock:
            if self._current_session:
                self._current_session.conversation_count += 1
                self._current_session.end_ts = time.time()

    def _on_shutdown(self, packet: dict):
        """Handle shutdown."""
        with self._lock:
            if self._current_session:
                self._current_session.end_ts = time.time()
                self._current_session.summary = self._generate_session_summary(
                    self._current_session
                )
        self._save_state()
        print(f"[{self.ACTOR_NAME}] Temporal context saved")

    def _generate_session_summary(self, session: Session) -> str:
        """Generate a brief summary of a session."""
        duration_mins = (session.end_ts - session.start_ts) / 60
        topics = ", ".join(session.key_topics[:5]) if session.key_topics else "various activities"
        return (
            f"Session {session.session_key}: {int(duration_mins)} minutes, "
            f"{session.memory_count} memories, {session.conversation_count} conversations. "
            f"Topics: {topics}"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC API - Temporal queries
    # ══════════════════════════════════════════════════════════════════════════

    def what_did_we_do(self, when: str = "yesterday") -> str:
        """Answer 'what did we do [when]?' questions."""
        now = time.time()

        if when == "yesterday":
            yesterday = datetime.now() - timedelta(days=1)
            day_key = yesterday.strftime("%Y-%m-%d")
            sessions = [s for k, s in self._sessions.items() if k.startswith(day_key)]
        elif when == "this morning":
            today = datetime.now().strftime("%Y-%m-%d")
            sessions = [s for k, s in self._sessions.items() if k == f"{today}_morning"]
        elif when == "last week":
            week_ago = datetime.now() - timedelta(days=7)
            sessions = [
                s for k, s in self._sessions.items()
                if datetime.fromtimestamp(s.start_ts) >= week_ago
            ][:10]
        else:
            sessions = []

        if not sessions:
            return f"I don't have clear memories of {when}."

        return "\n".join(s.describe(now) for s in sessions)

    def get_narrative_context(self, n_sessions: int = 5) -> str:
        """Get narrative context for continuity."""
        now = time.time()
        recent_keys = list(self._session_order)[-n_sessions:]

        lines = ["Here's what we've been doing recently:"]
        for key in reversed(recent_keys):
            if key in self._sessions:
                lines.append(f"- {self._sessions[key].describe(now)}")

        return "\n".join(lines)

    def get_current_session(self) -> Optional[Session]:
        return self._current_session

    def get_session_by_key(self, key: str) -> Optional[Session]:
        return self._sessions.get(key)

    def get_recent_sessions(self, n: int = 10) -> List[Session]:
        keys = list(self._session_order)[-n:]
        return [self._sessions[k] for k in keys if k in self._sessions]

    def get_temporal_marker(self, ts: float) -> str:
        return TemporalMarker.describe(ts)

    def get_memories_from(self, when: str) -> List[TemporalMemoryRef]:
        if when == "today":
            return self._index.get_by_day(datetime.now().strftime("%Y-%m-%d"))
        elif when == "yesterday":
            return self._index.get_by_day(
                (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            )
        return []
