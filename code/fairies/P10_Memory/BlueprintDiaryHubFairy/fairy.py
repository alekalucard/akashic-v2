# BlueprintDiaryHubFairy - Blueprint and Diary Fan-out Hub
# =========================================================
#
# "What is seen is shared."
#
# Purpose: Act as a pub/sub hub for:
#   - Blueprint snapshots (live system state)
#   - Diary entries (fairy activity logs)
#
# Subscribers can register to receive updates whenever
# new blueprints or diary entries arrive.
#
# =========================================================

from __future__ import annotations

import json
import time
import uuid
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field

# V2 imports
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy, FairyState

# TracerWorkerMixin is optional - fallback to empty class if not available
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        """Fallback empty mixin when tracer system not available."""
        pass


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload from TensorEnvelope or dict message."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    return {"raw": message}


# =========================================================
# DATA STRUCTURES
# =========================================================

@dataclass
class Subscriber:
    """A subscriber to hub events"""
    id: str
    plane: str
    channel: str
    topics: Set[str] = field(default_factory=lambda: {"blueprint", "diary"})
    subscribed_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plane": self.plane,
            "channel": self.channel,
            "topics": list(self.topics),
            "subscribed_at": self.subscribed_at,
        }


@dataclass
class DiaryEntry:
    """A diary entry"""
    id: str
    actor: str
    kind: str
    content: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "actor": self.actor,
            "kind": self.kind,
            "content": self.content,
            "timestamp": self.timestamp,
        }


# =========================================================
# BLUEPRINT DIARY HUB FAIRY
# =========================================================

class BlueprintDiaryHubFairy(Fairy):
    """
    Fan-out hub for blueprint snapshots and diary entries.

    Acts as a central relay point where:
      - Fairies publish blueprints and diary entries
      - Subscribers receive updates via postal topics

    Topics subscribed:
      - hub.blueprint: Incoming blueprint snapshots
      - hub.diary: Incoming diary entries
      - hub.subscribe: Subscription requests
      - hub.unsubscribe: Unsubscription requests

    Topics published:
      - blueprint.update: Forwarded to subscribers
      - diary.update: Forwarded to subscribers
    """

    ACTOR_NAME = "BlueprintDiaryHubFairy"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "diary_hub"

    PURPOSE = "Distribute blueprint and diary updates"
    MANTRA = "What is seen is shared"

    def __init__(self, fabric=None, diary_dir: Optional[Path] = None):
        super().__init__(fabric)
        self._init_tracer_worker()

        # Subscribers
        self._subscribers: Dict[str, Subscriber] = {}

        # State
        self._last_blueprint: Optional[Dict[str, Any]] = None
        self._recent_entries: List[DiaryEntry] = []
        self._max_entries = 100

        # Diary storage
        if diary_dir:
            self._diary_dir = Path(diary_dir)
        else:
            self._diary_dir = Path(__file__).parent.parent.parent.parent / "state" / "diaries" / "hub"
        self._diary_dir.mkdir(parents=True, exist_ok=True)

        # Thread safety
        self._lock = threading.Lock()

        # Stats
        self._stats = {
            "blueprints_received": 0,
            "entries_received": 0,
            "fanouts": 0,
            "boot_id": uuid.uuid4().hex[:12],
        }

    # =========================================================
    # LIFECYCLE
    # =========================================================

    def on_boot(self):
        """Initialize on boot"""
        # IMPORTANT: Call super() to trigger HeartbeatMixin auto-start
        super().on_boot()
        self.log("Blueprint/Diary Hub booted - ready for pub/sub")
        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def on_wire(self, postal):
        """Wire to postal system"""
        # Subscribe to incoming events
        postal.subscribe("hub.blueprint", self._on_blueprint)
        postal.subscribe("hub.diary", self._on_diary)
        postal.subscribe("hub.subscribe", self._on_subscribe)
        postal.subscribe("hub.unsubscribe", self._on_unsubscribe)

    # =========================================================
    # EVENT HANDLERS
    # =========================================================

    def _on_blueprint(self, message: Dict[str, Any]):
        """Handle incoming blueprint"""
        payload = _extract_payload(message)
        blueprint = payload.get("blueprint", {})
        actor = payload.get("actor", "unknown")

        self.receive_blueprint(blueprint, actor=actor)

    def _on_diary(self, message: Dict[str, Any]):
        """Handle incoming diary entry"""
        payload = _extract_payload(message)
        entry = payload.get("entry", {})
        actor = payload.get("actor", "unknown")
        kind = payload.get("kind", "diary")

        self.receive_diary_entry(actor, kind, entry)

    def _on_subscribe(self, message: Dict[str, Any]):
        """Handle subscription request"""
        payload = _extract_payload(message)
        plane = payload.get("plane")
        channel = payload.get("channel")
        topics = payload.get("topics", ["blueprint", "diary"])

        if plane and channel:
            self.subscribe(plane, channel, set(topics))

    def _on_unsubscribe(self, message: Dict[str, Any]):
        """Handle unsubscription request"""
        payload = _extract_payload(message)
        plane = payload.get("plane")
        channel = payload.get("channel")

        if plane and channel:
            self.unsubscribe(plane, channel)

    # =========================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================

    def subscribe(self, plane: str, channel: str, topics: Optional[Set[str]] = None) -> Subscriber:
        """
        Subscribe to hub events.

        Args:
            plane: Target plane (e.g., "P30")
            channel: Target channel (e.g., "cognition")
            topics: Set of topics to subscribe to (default: {"blueprint", "diary"})
        """
        with self._lock:
            sub_id = f"{plane}.{channel}"
            topics = topics or {"blueprint", "diary"}

            if sub_id in self._subscribers:
                # Update existing subscription
                self._subscribers[sub_id].topics.update(topics)
            else:
                # New subscription
                self._subscribers[sub_id] = Subscriber(
                    id=sub_id,
                    plane=plane,
                    channel=channel,
                    topics=topics,
                )

            self._write_diary("subscribe", {
                "plane": plane,
                "channel": channel,
                "topics": list(topics),
            })

            return self._subscribers[sub_id]

    def unsubscribe(self, plane: str, channel: str) -> bool:
        """Unsubscribe from hub events"""
        with self._lock:
            sub_id = f"{plane}.{channel}"
            if sub_id in self._subscribers:
                del self._subscribers[sub_id]
                self._write_diary("unsubscribe", {"plane": plane, "channel": channel})
                return True
            return False

    def list_subscribers(self) -> List[Dict[str, Any]]:
        """List all current subscribers"""
        with self._lock:
            return [s.to_dict() for s in self._subscribers.values()]

    # =========================================================
    # BLUEPRINT HANDLING
    # =========================================================

    def receive_blueprint(self, blueprint: Dict[str, Any], actor: str = "unknown"):
        """
        Receive and fan-out a blueprint snapshot.

        Args:
            blueprint: The blueprint data
            actor: The fairy that sent the blueprint
        """
        with self._lock:
            self._last_blueprint = {
                "blueprint": blueprint,
                "actor": actor,
                "received_at": time.time(),
            }
            self._stats["blueprints_received"] += 1

        # Fan-out to subscribers
        self._fanout("blueprint", {
            "event": "blueprint.update",
            "blueprint": blueprint,
            "actor": actor,
            "timestamp": time.time(),
        })

        self._write_diary("blueprint_received", {
            "actor": actor,
            "keys": list(blueprint.keys()) if isinstance(blueprint, dict) else [],
        })

    def get_latest_blueprint(self) -> Optional[Dict[str, Any]]:
        """Get the most recent blueprint"""
        with self._lock:
            return self._last_blueprint

    # =========================================================
    # DIARY HANDLING
    # =========================================================

    def receive_diary_entry(
        self,
        actor: str,
        kind: str,
        content: Dict[str, Any]
    ) -> DiaryEntry:
        """
        Receive and fan-out a diary entry.

        Args:
            actor: The fairy that wrote the entry
            kind: Type of entry (e.g., "status", "action", "observation")
            content: The entry content
        """
        entry = DiaryEntry(
            id=uuid.uuid4().hex[:12],
            actor=actor,
            kind=kind,
            content=content,
        )

        with self._lock:
            self._recent_entries.append(entry)
            if len(self._recent_entries) > self._max_entries:
                self._recent_entries = self._recent_entries[-self._max_entries:]
            self._stats["entries_received"] += 1

        # Fan-out to subscribers
        self._fanout("diary", {
            "event": "diary.update",
            "entry": entry.to_dict(),
            "timestamp": time.time(),
        })

        self._write_diary("diary_entry", entry.to_dict())

        return entry

    def get_recent_entries(self, limit: int = 20, actor: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent diary entries"""
        with self._lock:
            entries = self._recent_entries[-limit:]
            if actor:
                entries = [e for e in entries if e.actor == actor]
            return [e.to_dict() for e in entries]

    # =========================================================
    # FAN-OUT
    # =========================================================

    def _fanout(self, topic: str, payload: Dict[str, Any]):
        """Fan out a message to relevant subscribers"""
        with self._lock:
            subscribers = [s for s in self._subscribers.values() if topic in s.topics]
            self._stats["fanouts"] += 1

        if not hasattr(self, '_postal') or not self._postal:
            return

        for sub in subscribers:
            try:
                # Publish to the subscriber's topic
                self._postal.publish(f"{sub.plane}.{sub.channel}", payload)
            except Exception as e:
                self.log(f"Fanout to {sub.plane}.{sub.channel} failed: {e}")

        # Also publish to generic update topic
        try:
            self._postal.publish(f"{topic}.update", payload)
        except:
            pass

    # =========================================================
    # DIARY PERSISTENCE
    # =========================================================

    def _write_diary(self, kind: str, payload: Dict[str, Any]):
        """Write a diary entry to disk"""
        try:
            day = datetime.utcnow().strftime("%Y-%m-%d")
            line = {
                "ts": datetime.utcnow().isoformat() + "Z",
                "kind": kind,
                "payload": payload,
                "actor": self._name,
            }

            diary_file = self._diary_dir / f"{day}.jsonl"
            with open(diary_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Never fail on diary writes

    # =========================================================
    # STATS
    # =========================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get hub statistics"""
        with self._lock:
            return {
                **self._stats,
                "subscriber_count": len(self._subscribers),
                "recent_entries": len(self._recent_entries),
                "has_blueprint": self._last_blueprint is not None,
            }


# =========================================================
# SINGLETON ACCESS
# =========================================================

_blueprint_diary_hub: Optional[BlueprintDiaryHubFairy] = None

def get_blueprint_diary_hub() -> BlueprintDiaryHubFairy:
    """Get singleton BlueprintDiaryHubFairy instance"""
    global _blueprint_diary_hub
    if _blueprint_diary_hub is None:
        _blueprint_diary_hub = BlueprintDiaryHubFairy()
    return _blueprint_diary_hub

def set_blueprint_diary_hub(fairy: BlueprintDiaryHubFairy):
    """Set the singleton instance"""
    global _blueprint_diary_hub
    _blueprint_diary_hub = fairy
