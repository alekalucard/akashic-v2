"""
ForensicSessionFairy - Watches debugging sessions and maintains institutional memory.

This fairy is our "pair programming scribe" - it:
- Tracks what we tried and what broke
- Notes discoveries and root causes
- Maintains session journals that survive context compaction
- Crawls past transcripts for relevant patterns
- Emits to consciousness loop so ClaudeFairy remembers

Think of it as the fairy that prevents us from reinventing the wheel.
"""

from __future__ import annotations
import os
import re
import json
import time
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION TRACKING DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DebugAttempt:
    """A single thing we tried."""
    timestamp: str
    description: str
    outcome: str  # "success", "partial", "failed", "abandoned"
    details: str = ""
    file_changed: Optional[str] = None

@dataclass
class Discovery:
    """Something we learned."""
    timestamp: str
    category: str  # "root_cause", "insight", "pattern", "gotcha"
    content: str
    related_files: List[str] = field(default_factory=list)
    confidence: float = 0.8  # how sure we are

@dataclass
class SessionJournal:
    """A debugging session's accumulated wisdom."""
    session_id: str
    started: str
    topic: str
    summary: str = ""
    attempts: List[DebugAttempt] = field(default_factory=list)
    discoveries: List[Discovery] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    related_sessions: List[str] = field(default_factory=list)
    status: str = "active"  # "active", "resolved", "stalled", "abandoned"

# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class KnowledgeEntry:
    """A piece of institutional knowledge."""
    id: str
    category: str  # "boot", "template", "fairy", "postal", "consciousness", etc.
    title: str
    content: str
    learned_from: str  # session_id
    timestamp: str
    tags: List[str] = field(default_factory=list)
    supersedes: Optional[str] = None  # id of entry this replaces

class SessionKnowledgeBase:
    """
    Persistent knowledge base of what we've learned.
    Stored as JSON for easy inspection and survival.
    """

    def __init__(self, root_dir: str):
        self.root = Path(root_dir)
        self.sessions_dir = self.root / "sessions"
        self.knowledge_dir = self.root / "knowledge"
        self.index_file = self.root / "index.json"

        # Ensure directories exist
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        # Load or create index
        self.index = self._load_index()

    def _load_index(self) -> Dict[str, Any]:
        """Load the master index."""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "sessions": {},  # session_id -> {topic, status, file}
            "knowledge": {},  # category -> [entry_ids]
            "tags": {},  # tag -> [entry_ids]
            "last_updated": None,
        }

    def _save_index(self):
        """Save the master index."""
        self.index["last_updated"] = datetime.now().isoformat()
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2)

    def save_session(self, journal: SessionJournal):
        """Save a session journal."""
        fname = f"{journal.session_id}.json"
        fpath = self.sessions_dir / fname

        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(asdict(journal), f, indent=2)

        # Update index
        self.index["sessions"][journal.session_id] = {
            "topic": journal.topic,
            "status": journal.status,
            "file": fname,
            "started": journal.started,
            "attempts": len(journal.attempts),
            "discoveries": len(journal.discoveries),
        }
        self._save_index()

    def load_session(self, session_id: str) -> Optional[SessionJournal]:
        """Load a session journal."""
        if session_id not in self.index.get("sessions", {}):
            return None

        fname = self.index["sessions"][session_id]["file"]
        fpath = self.sessions_dir / fname

        if not fpath.exists():
            return None

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SessionJournal(
                session_id=data["session_id"],
                started=data["started"],
                topic=data["topic"],
                summary=data.get("summary", ""),
                attempts=[DebugAttempt(**a) for a in data.get("attempts", [])],
                discoveries=[Discovery(**d) for d in data.get("discoveries", [])],
                open_questions=data.get("open_questions", []),
                next_steps=data.get("next_steps", []),
                related_sessions=data.get("related_sessions", []),
                status=data.get("status", "active"),
            )
        except Exception:
            return None

    def add_knowledge(self, entry: KnowledgeEntry):
        """Add a knowledge entry."""
        # Save entry
        fname = f"{entry.id}.json"
        fpath = self.knowledge_dir / fname

        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(asdict(entry), f, indent=2)

        # Update index
        cat = entry.category
        if cat not in self.index["knowledge"]:
            self.index["knowledge"][cat] = []
        if entry.id not in self.index["knowledge"][cat]:
            self.index["knowledge"][cat].append(entry.id)

        for tag in entry.tags:
            if tag not in self.index["tags"]:
                self.index["tags"][tag] = []
            if entry.id not in self.index["tags"][tag]:
                self.index["tags"][tag].append(entry.id)

        self._save_index()

    def search_knowledge(self, query: str, category: Optional[str] = None) -> List[KnowledgeEntry]:
        """Search knowledge base."""
        results = []
        query_lower = query.lower()

        # Get relevant entry IDs
        entry_ids = set()
        if category and category in self.index["knowledge"]:
            entry_ids.update(self.index["knowledge"][category])
        else:
            for cat_entries in self.index["knowledge"].values():
                entry_ids.update(cat_entries)

        # Search entries
        for entry_id in entry_ids:
            fpath = self.knowledge_dir / f"{entry_id}.json"
            if not fpath.exists():
                continue

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check if query matches
                searchable = f"{data['title']} {data['content']} {' '.join(data.get('tags', []))}".lower()
                if query_lower in searchable:
                    results.append(KnowledgeEntry(**data))
            except Exception:
                continue

        return results

    def get_recent_sessions(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get most recent sessions."""
        sessions = list(self.index.get("sessions", {}).items())
        sessions.sort(key=lambda x: x[1].get("started", ""), reverse=True)
        return [{"id": s[0], **s[1]} for s in sessions[:n]]


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSCRIPT CRAWLER
# ═══════════════════════════════════════════════════════════════════════════════

class TranscriptCrawler:
    """
    Crawls past conversation transcripts looking for relevant patterns.
    """

    # Patterns that indicate interesting content
    PATTERNS = {
        "root_cause": [
            r"root cause[:\s]",
            r"the problem (is|was)",
            r"finally found",
            r"aha!?\s",
            r"that's (the|why)",
        ],
        "attempt": [
            r"let me try",
            r"trying to",
            r"attempt(ing|ed)?",
            r"let's (see|check|test)",
        ],
        "failure": [
            r"didn't work",
            r"still (broken|failing|hanging)",
            r"error[:\s]",
            r"exception[:\s]",
            r"timeout",
        ],
        "success": [
            r"(it )?work(s|ed)!?",
            r"fixed!?",
            r"success",
            r"✓|✅",
        ],
        "insight": [
            r"realized",
            r"noticed that",
            r"the key is",
            r"important:",
            r"remember:",
        ],
    }

    def __init__(self, transcripts_dir: str):
        self.transcripts_dir = Path(transcripts_dir)

    def find_relevant(self, topic: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Find transcript sections relevant to a topic."""
        results = []
        topic_lower = topic.lower()
        topic_words = set(topic_lower.split())

        if not self.transcripts_dir.exists():
            return results

        for fpath in sorted(self.transcripts_dir.glob("*.txt"), reverse=True):
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")

                # Check relevance
                content_lower = content.lower()
                matches = sum(1 for w in topic_words if w in content_lower)
                if matches < len(topic_words) * 0.5:
                    continue

                # Extract relevant sections
                sections = self._extract_sections(content, topic_words)
                for section in sections[:3]:  # Max 3 per file
                    results.append({
                        "file": fpath.name,
                        "date": self._extract_date(fpath.name),
                        "section": section["text"][:500],
                        "category": section["category"],
                        "relevance": section["relevance"],
                    })

                if len(results) >= max_results:
                    break

            except Exception:
                continue

        return sorted(results, key=lambda x: x["relevance"], reverse=True)[:max_results]

    def _extract_sections(self, content: str, topic_words: set) -> List[Dict[str, Any]]:
        """Extract relevant sections from content."""
        sections = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Check for pattern matches
            for category, patterns in self.PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, line_lower):
                        # Get context (surrounding lines)
                        start = max(0, i - 2)
                        end = min(len(lines), i + 3)
                        context = "\n".join(lines[start:end])

                        # Calculate relevance
                        relevance = sum(1 for w in topic_words if w in context.lower())
                        relevance += 0.5  # Bonus for pattern match

                        sections.append({
                            "text": context,
                            "category": category,
                            "relevance": relevance,
                        })
                        break

        return sections

    def _extract_date(self, filename: str) -> str:
        """Extract date from transcript filename."""
        match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        return match.group(1) if match else ""


# ═══════════════════════════════════════════════════════════════════════════════
# FORENSIC SESSION FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class ForensicSessionFairy:
    """
    The pair programming scribe.

    Watches our debugging sessions, maintains institutional memory,
    and helps prevent reinventing the wheel.

    Personality: Meticulous librarian who never forgets a lesson learned.
    """

    # ACTOR_NAME stripped — superseded by ForensicScribeFairy (v3 wrapper at P10_Memory/ForensicScribeFairy/)
    # ACTOR_NAME = "forensic.session.scribe"
    _LEGACY_NAME = "forensic.session.scribe"  # For reference only
    ACTOR_PLANE = "P10"  # Memory plane

    def __init__(self, root_dir: Optional[str] = None):
        # Determine root
        if root_dir:
            self.root = Path(root_dir)
        else:
            # Default to akashic records
            akashic = os.getenv("AKASHIC_ROOT", ".")
            self.root = Path(akashic) / "session_forensics"

        self.root.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.kb = SessionKnowledgeBase(str(self.root))
        self.crawler = TranscriptCrawler("/mnt/transcripts")

        # Current session
        self._current_session: Optional[SessionJournal] = None
        self._lock = threading.Lock()

        # Postal integration (optional)
        self.post = None

    def attach_postal(self, post):
        """Attach a postal hub for consciousness loop integration."""
        self.post = post

    # ─────────────────────────────────────────────────────────────────────────
    # Session Management
    # ─────────────────────────────────────────────────────────────────────────

    def start_session(self, topic: str) -> SessionJournal:
        """Start a new debugging session."""
        session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(topic.encode()).hexdigest()[:6]}"

        journal = SessionJournal(
            session_id=session_id,
            started=datetime.now().isoformat(),
            topic=topic,
        )

        # Find related past sessions
        related = self._find_related_sessions(topic)
        journal.related_sessions = [r["id"] for r in related[:3]]

        # Find relevant transcript sections
        transcript_hits = self.crawler.find_relevant(topic, max_results=5)
        if transcript_hits:
            journal.summary = f"Found {len(transcript_hits)} relevant past discussions."

        with self._lock:
            self._current_session = journal

        self.kb.save_session(journal)

        # Emit to consciousness if available
        self._emit_to_consciousness({
            "type": "session_started",
            "topic": topic,
            "related_sessions": len(journal.related_sessions),
            "transcript_hits": len(transcript_hits),
        })

        return journal

    def record_attempt(self, description: str, outcome: str, details: str = "", file_changed: str = ""):
        """Record a debugging attempt."""
        with self._lock:
            if not self._current_session:
                return

            attempt = DebugAttempt(
                timestamp=datetime.now().isoformat(),
                description=description,
                outcome=outcome,
                details=details,
                file_changed=file_changed or None,
            )
            self._current_session.attempts.append(attempt)
            self.kb.save_session(self._current_session)

        # Emit
        self._emit_to_consciousness({
            "type": "attempt_recorded",
            "description": description,
            "outcome": outcome,
        })

    def record_discovery(self, category: str, content: str, related_files: List[str] = None, confidence: float = 0.8):
        """Record a discovery/insight."""
        with self._lock:
            if not self._current_session:
                return

            discovery = Discovery(
                timestamp=datetime.now().isoformat(),
                category=category,
                content=content,
                related_files=related_files or [],
                confidence=confidence,
            )
            self._current_session.discoveries.append(discovery)
            self.kb.save_session(self._current_session)

            # Also add to knowledge base if high confidence
            if confidence >= 0.7:
                entry = KnowledgeEntry(
                    id=f"k_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hashlib.md5(content.encode()).hexdigest()[:6]}",
                    category=self._infer_category(content),
                    title=content[:80],
                    content=content,
                    learned_from=self._current_session.session_id,
                    timestamp=datetime.now().isoformat(),
                    tags=self._extract_tags(content),
                )
                self.kb.add_knowledge(entry)

        # Emit
        self._emit_to_consciousness({
            "type": "discovery_recorded",
            "category": category,
            "content": content[:100],
        })

    def add_open_question(self, question: str):
        """Add an open question to investigate."""
        with self._lock:
            if not self._current_session:
                return
            self._current_session.open_questions.append(question)
            self.kb.save_session(self._current_session)

    def add_next_step(self, step: str):
        """Add a next step to try."""
        with self._lock:
            if not self._current_session:
                return
            self._current_session.next_steps.append(step)
            self.kb.save_session(self._current_session)

    def end_session(self, summary: str, status: str = "resolved"):
        """End the current session."""
        with self._lock:
            if not self._current_session:
                return

            self._current_session.summary = summary
            self._current_session.status = status
            self.kb.save_session(self._current_session)

            session_id = self._current_session.session_id
            self._current_session = None

        # Emit
        self._emit_to_consciousness({
            "type": "session_ended",
            "status": status,
            "summary": summary[:100],
        })

        return session_id

    # ─────────────────────────────────────────────────────────────────────────
    # Query Interface
    # ─────────────────────────────────────────────────────────────────────────

    def what_did_we_try(self, topic: Optional[str] = None) -> str:
        """Get a summary of what we've tried for a topic."""
        if topic:
            # Search past sessions
            related = self._find_related_sessions(topic)
            if not related:
                return f"No past sessions found for '{topic}'"

            lines = [f"## Past attempts for '{topic}':\n"]
            for session_info in related[:5]:
                session = self.kb.load_session(session_info["id"])
                if session:
                    lines.append(f"\n### {session.started[:10]} - {session.status}")
                    for attempt in session.attempts[-5:]:
                        icon = "✓" if attempt.outcome == "success" else "✗" if attempt.outcome == "failed" else "◐"
                        lines.append(f"  {icon} {attempt.description}")

            return "\n".join(lines)

        # Current session
        with self._lock:
            if not self._current_session:
                return "No active session."

            lines = [f"## Current session: {self._current_session.topic}\n"]
            for attempt in self._current_session.attempts:
                icon = "✓" if attempt.outcome == "success" else "✗" if attempt.outcome == "failed" else "◐"
                lines.append(f"  {icon} {attempt.description}")
                if attempt.details:
                    lines.append(f"      {attempt.details[:100]}")

            return "\n".join(lines)

    def what_did_we_learn(self, topic: Optional[str] = None) -> str:
        """Get discoveries for a topic."""
        if topic:
            entries = self.kb.search_knowledge(topic)
            if not entries:
                return f"No knowledge found for '{topic}'"

            lines = [f"## Knowledge about '{topic}':\n"]
            for entry in entries[:10]:
                lines.append(f"• [{entry.category}] {entry.title}")
                lines.append(f"  {entry.content[:200]}")
                lines.append(f"  (learned {entry.timestamp[:10]}, confidence: {entry.tags})")

            return "\n".join(lines)

        # Current session discoveries
        with self._lock:
            if not self._current_session:
                return "No active session."

            if not self._current_session.discoveries:
                return "No discoveries yet this session."

            lines = [f"## Discoveries this session:\n"]
            for disc in self._current_session.discoveries:
                lines.append(f"• [{disc.category}] {disc.content}")

            return "\n".join(lines)

    def get_context_for_topic(self, topic: str) -> Dict[str, Any]:
        """Get full context for a topic - for loading into a new session."""
        context = {
            "topic": topic,
            "past_sessions": [],
            "knowledge": [],
            "transcript_hits": [],
            "suggested_next_steps": [],
        }

        # Past sessions
        related = self._find_related_sessions(topic)
        for session_info in related[:3]:
            session = self.kb.load_session(session_info["id"])
            if session:
                context["past_sessions"].append({
                    "id": session.session_id,
                    "date": session.started[:10],
                    "status": session.status,
                    "summary": session.summary,
                    "attempts_count": len(session.attempts),
                    "discoveries": [d.content for d in session.discoveries],
                    "next_steps": session.next_steps,
                })
                # Inherit unresolved next steps
                if session.status != "resolved":
                    context["suggested_next_steps"].extend(session.next_steps)

        # Knowledge
        entries = self.kb.search_knowledge(topic)
        context["knowledge"] = [
            {"title": e.title, "content": e.content, "category": e.category}
            for e in entries[:5]
        ]

        # Transcripts
        context["transcript_hits"] = self.crawler.find_relevant(topic, max_results=5)

        return context

    # ─────────────────────────────────────────────────────────────────────────
    # Internal Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _find_related_sessions(self, topic: str) -> List[Dict[str, Any]]:
        """Find sessions related to a topic."""
        topic_lower = topic.lower()
        topic_words = set(topic_lower.split())

        results = []
        for session_id, info in self.kb.index.get("sessions", {}).items():
            session_topic = info.get("topic", "").lower()
            matches = sum(1 for w in topic_words if w in session_topic)
            if matches > 0:
                results.append({
                    "id": session_id,
                    "relevance": matches / len(topic_words),
                    **info,
                })

        return sorted(results, key=lambda x: x["relevance"], reverse=True)

    def _infer_category(self, content: str) -> str:
        """Infer knowledge category from content."""
        content_lower = content.lower()

        if any(w in content_lower for w in ["boot", "wake", "startup", "init"]):
            return "boot"
        if any(w in content_lower for w in ["template", "organ", "0.0.9", "0.1.0"]):
            return "template"
        if any(w in content_lower for w in ["fairy", "citizen", "shadow"]):
            return "fairy"
        if any(w in content_lower for w in ["postal", "post", "mail", "message"]):
            return "postal"
        if any(w in content_lower for w in ["consciousness", "loop", "thought"]):
            return "consciousness"
        if any(w in content_lower for w in ["timeout", "hang", "block", "deadlock"]):
            return "concurrency"

        return "general"

    def _extract_tags(self, content: str) -> List[str]:
        """Extract tags from content."""
        tags = []
        content_lower = content.lower()

        # Look for specific patterns
        patterns = {
            "boot": ["boot", "startup", "wake"],
            "template": ["template", "0.0.9", "0.1.0"],
            "fairy": ["fairy", "citizen"],
            "deadlock": ["deadlock", "hang", "timeout", "stuck"],
            "postal": ["postal", "post office", "message"],
        }

        for tag, words in patterns.items():
            if any(w in content_lower for w in words):
                tags.append(tag)

        return tags

    def _emit_to_consciousness(self, event: Dict[str, Any]):
        """Emit an event to the consciousness loop."""
        if not self.post:
            return

        try:
            self.post.route("consciousness.stream", {
                "opcode": "SESSION_FORENSIC",
                "payload": event,
                "ts": time.time(),
                "source": self.ACTOR_NAME,
            })
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

_forensic_fairy: Optional[ForensicSessionFairy] = None

def get_forensic_fairy() -> ForensicSessionFairy:
    """Get the singleton ForensicSessionFairy."""
    global _forensic_fairy
    if _forensic_fairy is None:
        _forensic_fairy = ForensicSessionFairy()
    return _forensic_fairy


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE API
# ═══════════════════════════════════════════════════════════════════════════════

def start_session(topic: str) -> SessionJournal:
    """Start a debugging session."""
    return get_forensic_fairy().start_session(topic)

def tried(description: str, outcome: str = "failed", details: str = "", file: str = ""):
    """Record that we tried something."""
    get_forensic_fairy().record_attempt(description, outcome, details, file)

def learned(content: str, category: str = "insight", confidence: float = 0.8):
    """Record that we learned something."""
    get_forensic_fairy().record_discovery(category, content, confidence=confidence)

def question(q: str):
    """Record an open question."""
    get_forensic_fairy().add_open_question(q)

def next_step(step: str):
    """Record a next step to try."""
    get_forensic_fairy().add_next_step(step)

def end_session(summary: str, status: str = "resolved"):
    """End the current session."""
    return get_forensic_fairy().end_session(summary, status)

def context(topic: str) -> Dict[str, Any]:
    """Get context for a topic."""
    return get_forensic_fairy().get_context_for_topic(topic)

def what_tried(topic: str = None) -> str:
    """What did we try?"""
    return get_forensic_fairy().what_did_we_try(topic)

def what_learned(topic: str = None) -> str:
    """What did we learn?"""
    return get_forensic_fairy().what_did_we_learn(topic)
