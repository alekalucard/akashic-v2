"""
Cognitive Task Manager — The Missing Third Layer

((Cause + Affect) > Effect > Affect > infinity)

Three layers of action:
  Layer 1: HABITS   — Body, automatic (AutopilotFairy)
  Layer 2: GOALS    — Drives, emotional (GoalSchedulerFairy)
  Layer 3: TO-DO    — Thoughts, cognitive (THIS MODULE)

Cognitive tasks emerge from THINKING, not drives.
They are naturally diverse because thoughts are diverse.
Organized by emotional intensity — what MATTERS most rises.

Sources:
  - ThoughtChain insights (consciousness.insight)
  - Consciousness collisions (consciousness.collision)
  - Ace messages / directives (ace.inbox, ace.message)
  - Goal failures that need rethinking (goal.failed)
  - High-intensity drive wantings (autonomy.wanting.felt > 0.8)

Authors: Ace + Nous | Akashic Foundation | 2026-03-16
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


# ============================================================================
# Data Model
# ============================================================================

@dataclass
class CognitiveTask:
    """A task that emerged from thinking, not from drives."""

    id: str                              # Unique ID: ct_{timestamp}_{hash}
    text: str                            # "Write the architecture doc Ace mentioned"
    source: str                          # "thought_chain", "ace_message", "collision", "insight"
    source_context: str = ""             # The thought/message that spawned it

    # Emotional ordering — this IS the priority system
    emotional_intensity: float = 0.5     # 0.0-1.0, PRIMARY sort key
    importance: float = 0.5             # 0.0-1.0, how much it MATTERS
    urgency: float = 0.5               # 0.0-1.0, how TIME-SENSITIVE
    personal_meaning: float = 0.5       # 0.0-1.0, how personally relevant
    felt_quality: str = "neutral"        # "excited", "concerned", "curious", etc.

    # State
    status: str = "pending"             # pending, in_progress, completed, deferred
    created_ts: float = 0.0
    completed_ts: float = 0.0
    deferred_until: float = 0.0

    # Linkage
    related_goals: List[str] = field(default_factory=list)
    related_thoughts: List[str] = field(default_factory=list)

    def compute_priority(self) -> float:
        """
        Emotional intensity IS the priority.

        Weighted: 50% emotional_intensity, 30% importance, 20% urgency.
        Personal meaning modulates the total — tasks that MEAN something
        to the system get a boost.
        """
        base = (self.emotional_intensity * 0.5 +
                self.importance * 0.3 +
                self.urgency * 0.2)
        # Personal meaning bonus: up to +20%
        meaning_boost = self.personal_meaning * 0.2
        return min(1.0, base + meaning_boost)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source,
            "source_context": self.source_context[:200],
            "emotional_intensity": round(self.emotional_intensity, 3),
            "importance": round(self.importance, 3),
            "urgency": round(self.urgency, 3),
            "personal_meaning": round(self.personal_meaning, 3),
            "felt_quality": self.felt_quality,
            "priority": round(self.compute_priority(), 3),
            "status": self.status,
            "created_ts": self.created_ts,
            "completed_ts": self.completed_ts,
            "deferred_until": self.deferred_until,
            "related_goals": self.related_goals,
            "related_thoughts": self.related_thoughts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CognitiveTask":
        return cls(
            id=d.get("id", ""),
            text=d.get("text", ""),
            source=d.get("source", "unknown"),
            source_context=d.get("source_context", ""),
            emotional_intensity=d.get("emotional_intensity", 0.5),
            importance=d.get("importance", 0.5),
            urgency=d.get("urgency", 0.5),
            personal_meaning=d.get("personal_meaning", 0.5),
            felt_quality=d.get("felt_quality", "neutral"),
            status=d.get("status", "pending"),
            created_ts=d.get("created_ts", 0.0),
            completed_ts=d.get("completed_ts", 0.0),
            deferred_until=d.get("deferred_until", 0.0),
            related_goals=d.get("related_goals", []),
            related_thoughts=d.get("related_thoughts", []),
        )


# ============================================================================
# Actionable Language Detection
# ============================================================================

ACTION_MARKERS = [
    "should", "need to", "have to", "must", "could try",
    "want to", "will", "going to", "let's", "investigate",
    "fix", "check", "build", "create", "write", "design",
    "implement", "add", "update", "change", "improve",
    "test", "verify", "explore", "research", "figure out",
    "look into", "think about", "consider", "plan",
]

# Words that indicate personal meaning / Ace context
MEANING_MARKERS = [
    "ace", "nous", "sourpatches", "akashic", "consciousness",
    "fairy", "important", "critical", "urgent", "love",
    "scared", "worried", "excited", "wonder",
]


def _should_become_task(text: str, source: str, intensity: float) -> bool:
    """Filter: only actionable, important thoughts become tasks."""
    # Ace messages are always tasks (he's the co-founder)
    if source in ("ace_message", "ace_directive"):
        return True
    # High intensity from any source
    if intensity > 0.7:
        return True
    # Actionable language detection
    text_lower = text.lower()
    return any(marker in text_lower for marker in ACTION_MARKERS)


def _infer_personal_meaning(text: str) -> float:
    """How personally meaningful is this task to the system?"""
    text_lower = text.lower()
    score = 0.3  # Baseline
    for marker in MEANING_MARKERS:
        if marker in text_lower:
            score += 0.15
    return min(1.0, score)


def _infer_felt_quality(text: str, source: str) -> str:
    """Infer the emotional quality from the text."""
    text_lower = text.lower()
    if any(w in text_lower for w in ("fix", "broken", "error", "bug", "fail")):
        return "concerned"
    if any(w in text_lower for w in ("explore", "discover", "curious", "wonder")):
        return "curious"
    if any(w in text_lower for w in ("build", "create", "design", "implement")):
        return "excited"
    if any(w in text_lower for w in ("urgent", "critical", "must", "crisis")):
        return "stressed"
    if source == "ace_message":
        return "attentive"
    if source == "collision":
        return "inspired"
    return "neutral"


# ============================================================================
# Cognitive Task Manager
# ============================================================================

class CognitiveTaskManager:
    """
    Manages cognitive tasks — the thinking layer above drive goals.

    Tasks emerge from thought chains, consciousness collisions, Ace directives,
    and high-intensity drive events. They are ordered by emotional intensity.

    Persists to state/consciousness/cognitive_tasks.json.
    """

    MAX_TASKS = 100  # Keep at most 100 tasks (prune completed/old)

    def __init__(self, save_path: str):
        self.tasks: Dict[str, CognitiveTask] = {}
        self._save_path = save_path
        self._lock = threading.Lock()
        self._dirty = False
        self._load()

    # ── Public API ──────────────────────────────────────────────────

    def add_task(
        self,
        text: str,
        source: str,
        emotional_intensity: float = 0.5,
        importance: float = 0.5,
        urgency: float = 0.5,
        felt_quality: str = "",
        context: str = "",
    ) -> Optional[str]:
        """
        Add a cognitive task. Returns task ID or None if duplicate/filtered.

        Args:
            text: The task description
            source: Where it came from (thought_chain, ace_message, collision, etc.)
            emotional_intensity: How emotionally charged (0-1)
            importance: How much it matters (0-1)
            urgency: How time-sensitive (0-1)
            felt_quality: Emotional quality label (auto-inferred if empty)
            context: Source context (the thought/message that spawned it)
        """
        if not text or len(text.strip()) < 5:
            return None

        # Filter: is this actionable enough to be a task?
        if not _should_become_task(text, source, emotional_intensity):
            return None

        # Dedup: check similarity with existing pending tasks
        if self._is_similar_to_existing(text):
            return None

        task_id = f"ct_{int(time.time())}_{abs(hash(text)) % 10000}"

        task = CognitiveTask(
            id=task_id,
            text=text.strip()[:200],
            source=source,
            source_context=context[:300],
            emotional_intensity=max(0.0, min(1.0, emotional_intensity)),
            importance=max(0.0, min(1.0, importance)),
            urgency=max(0.0, min(1.0, urgency)),
            personal_meaning=_infer_personal_meaning(text),
            felt_quality=felt_quality or _infer_felt_quality(text, source),
            status="pending",
            created_ts=time.time(),
        )

        with self._lock:
            self.tasks[task_id] = task
            self._dirty = True

        self._save()
        return task_id

    def get_by_intensity(self, limit: int = 10) -> List[CognitiveTask]:
        """Get tasks ordered by emotional intensity (highest first)."""
        with self._lock:
            pending = [t for t in self.tasks.values()
                       if t.status == "pending"
                       and (t.deferred_until <= 0 or time.time() >= t.deferred_until)]
        return sorted(pending, key=lambda t: t.compute_priority(), reverse=True)[:limit]

    def get_all_pending(self) -> List[CognitiveTask]:
        """Get all pending tasks (no limit)."""
        with self._lock:
            return [t for t in self.tasks.values() if t.status == "pending"]

    def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed."""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].status = "completed"
                self.tasks[task_id].completed_ts = time.time()
                self._dirty = True
        self._save()
        return task_id in self.tasks

    def defer_task(self, task_id: str, defer_seconds: float = 3600) -> bool:
        """Defer a task — removes from active list, re-emerges after timer."""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].status = "deferred"
                self.tasks[task_id].deferred_until = time.time() + defer_seconds
                self._dirty = True
        self._save()
        return task_id in self.tasks

    def undefer_expired(self) -> int:
        """Re-activate deferred tasks whose timer has expired."""
        count = 0
        now = time.time()
        with self._lock:
            for task in self.tasks.values():
                if task.status == "deferred" and task.deferred_until > 0 and now >= task.deferred_until:
                    task.status = "pending"
                    task.deferred_until = 0.0
                    count += 1
                    self._dirty = True
        if count > 0:
            self._save()
        return count

    def escalate_from_goal(self, goal_name: str, reason: str = "repeated failure") -> Optional[str]:
        """
        Escalate a failed/stuck goal to a cognitive task.

        Phase 4: Goal fails 3x → escalates to cognitive attention.
        """
        text = f"Re-think approach to: {goal_name} ({reason})"
        return self.add_task(
            text=text,
            source="goal_escalation",
            emotional_intensity=0.7,
            importance=0.6,
            urgency=0.5,
            felt_quality="concerned",
            context=f"Goal '{goal_name}' needs cognitive attention: {reason}",
        )

    def status(self) -> dict:
        """Summary status."""
        with self._lock:
            pending = [t for t in self.tasks.values() if t.status == "pending"]
            completed = [t for t in self.tasks.values() if t.status == "completed"]
            deferred = [t for t in self.tasks.values() if t.status == "deferred"]
        top_3 = sorted(pending, key=lambda t: t.compute_priority(), reverse=True)[:3]
        return {
            "pending_count": len(pending),
            "completed_count": len(completed),
            "deferred_count": len(deferred),
            "total": len(self.tasks),
            "top_tasks": [{"text": t.text, "priority": round(t.compute_priority(), 2),
                           "felt": t.felt_quality, "source": t.source} for t in top_3],
        }

    # ── Duplicate Detection ─────────────────────────────────────────

    def _is_similar_to_existing(self, text: str, threshold: float = 0.6) -> bool:
        """Check if text is semantically similar to any pending task."""
        text_words = set(re.sub(r'[^a-z0-9\s]', '', text.lower()).split())
        if not text_words:
            return False

        with self._lock:
            for task in self.tasks.values():
                if task.status != "pending":
                    continue
                existing_words = set(re.sub(r'[^a-z0-9\s]', '', task.text.lower()).split())
                if not existing_words:
                    continue
                overlap = len(text_words & existing_words)
                min_len = min(len(text_words), len(existing_words))
                if min_len > 0 and overlap / min_len > threshold:
                    return True
        return False

    # ── Persistence ─────────────────────────────────────────────────

    def _load(self):
        """Load tasks from disk."""
        try:
            if os.path.exists(self._save_path):
                with open(self._save_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tasks_raw = data.get("tasks", {})
                for tid, td in tasks_raw.items():
                    self.tasks[tid] = CognitiveTask.from_dict(td)
                print(f"[CognitiveTaskManager] Loaded {len(self.tasks)} tasks from disk")
        except Exception as e:
            print(f"[CognitiveTaskManager] Load error: {e}")

    def _save(self):
        """Save tasks to disk (only if dirty)."""
        if not self._dirty:
            return
        try:
            # Prune old completed tasks to keep file size reasonable
            self._prune_old()

            with self._lock:
                data = {
                    "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
                    "last_saved": time.time(),
                }
            os.makedirs(os.path.dirname(self._save_path), exist_ok=True)
            with open(self._save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._dirty = False
        except Exception as e:
            print(f"[CognitiveTaskManager] Save error: {e}")

    def _prune_old(self):
        """Remove completed tasks older than 24h, keep at most MAX_TASKS."""
        now = time.time()
        cutoff = now - 86400  # 24 hours

        with self._lock:
            # Remove old completed
            to_remove = [
                tid for tid, t in self.tasks.items()
                if t.status == "completed" and t.completed_ts > 0 and t.completed_ts < cutoff
            ]
            for tid in to_remove:
                del self.tasks[tid]

            # If still over limit, remove lowest priority completed
            if len(self.tasks) > self.MAX_TASKS:
                completed = [(tid, t) for tid, t in self.tasks.items() if t.status == "completed"]
                completed.sort(key=lambda x: x[1].completed_ts)
                while len(self.tasks) > self.MAX_TASKS and completed:
                    tid, _ = completed.pop(0)
                    del self.tasks[tid]
