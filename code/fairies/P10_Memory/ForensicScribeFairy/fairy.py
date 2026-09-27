"""
ForensicScribeFairy - System Telemetry and Health Monitoring

"Witness clearly, alert gently, evolve coherently."

Responsibilities:
1. Sift telemetry across all fairies
2. Surface alerts to the status system
3. Detect drift and anomalies
4. Maintain forensic card per actor for dashboards
5. Track errors for debugging
"""

from __future__ import annotations

import sys
import os
import re
import json
import time
import hashlib
import threading
from pathlib import Path
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# V2 fairy template
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


# Storage directory for forensic logs
FORENSIC_STORAGE = ROOT / "SRM_Intake" / "forensic"


# =============================================================================
# FORENSIC CARD
# =============================================================================

@dataclass
class ForensicCard:
    """Health/status card for an actor."""

    actor: str
    plane: str = ""
    channel: str = ""
    version: str = ""

    # Health tracking
    health_status: str = "unknown"  # ok, warn, error, critical
    health_message: str = ""
    health_history: List[Dict] = field(default_factory=list)  # Last N health states

    # Error tracking
    error_count: int = 0
    last_error: Optional[str] = None
    last_error_ts: Optional[float] = None

    # Timing
    last_seen_ts: float = 0.0
    created_ts: float = field(default_factory=time.time)
    updated_ts: float = field(default_factory=time.time)

    def update_health(self, status: str, message: str = ""):
        """Update health status."""
        self.health_status = status
        self.health_message = message
        self.updated_ts = time.time()
        self.last_seen_ts = time.time()

        # Keep history
        self.health_history.append({
            "status": status,
            "message": message,
            "ts": time.time(),
        })
        # Trim history
        if len(self.health_history) > 20:
            self.health_history = self.health_history[-20:]

    def record_error(self, message: str):
        """Record an error."""
        self.error_count += 1
        self.last_error = message[:500]
        self.last_error_ts = time.time()
        self.updated_ts = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor": self.actor,
            "plane": self.plane,
            "channel": self.channel,
            "version": self.version,
            "health": {
                "status": self.health_status,
                "message": self.health_message,
                "history": self.health_history[-5:],  # Last 5 for API
            },
            "errors": {
                "count": self.error_count,
                "last": self.last_error,
                "last_ts": self.last_error_ts,
            },
            "timing": {
                "last_seen": self.last_seen_ts,
                "created": self.created_ts,
                "updated": self.updated_ts,
            },
        }


# =============================================================================
# FORENSIC SCRIBE FAIRY
# =============================================================================

class ForensicScribeFairy(Fairy):
    """
    Forensic Scribe - System health and telemetry monitor.

    Listens to telemetry/tracer events across all fairies, builds
    per-actor forensic cards, and surfaces alerts to dashboards.
    """

    ACTOR_NAME = "ForensicScribeFairy"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.forensic"
    NEEDS_HEARTBEAT = True
    NEEDS_TENSOR = True

    PURPOSE = "Sift telemetry, surface alerts, maintain forensic cards per actor"
    MANTRA = "Witness clearly, alert gently, evolve coherently"

    # Alert configuration
    ALERT_SUPPRESS_SECONDS = 120.0  # De-duplicate window
    FORENSIC_LOG_LIMIT = 10000  # Max in-memory log entries
    FORENSIC_KEEP_DAYS = 3  # Days to keep on disk

    def __init__(self, fabric=None, **kwargs):
        super().__init__(fabric, **kwargs)

        # Storage
        self.storage_dir = FORENSIC_STORAGE
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Forensic cards (actor -> card)
        self._cards: Dict[str, ForensicCard] = {}
        self._cards_lock = threading.Lock()

        # Error registry (normalized_key -> error_info)
        self._error_registry: Dict[str, Dict[str, Any]] = {}
        self._error_registry_lock = threading.Lock()

        # In-memory forensic log
        from collections import deque as _fl_deque
        self._forensic_log: deque = _fl_deque(maxlen=200)  # FIX 2026-04-05: was unbounded
        self._forensic_log_lock = threading.Lock()

        # Alert deduplication
        self._recent_alerts: Dict[Tuple[str, str], float] = {}  # (actor, title) -> ts

        # Forensic entry deduplication
        self._recent_forensic_sigs: deque = deque(maxlen=2000)

        # Stats
        self._events_processed = 0
        self._alerts_raised = 0

    def get_capabilities(self) -> Set[str]:
        return {
            "forensic.ingest",
            "forensic.card.get",
            "forensic.card.list",
            "forensic.errors.list",
            "forensic.errors.clear",
            "forensic.health.summary",
        }

    def on_boot(self) -> bool:
        """Boot and subscribe to telemetry streams."""
        if self.post:
            # Subscribe to telemetry events
            self.post.subscribe(
                "telemetry.*",
                self._on_telemetry,
                "forensic_telemetry_handler",
            )
            self.post.subscribe(
                "tracer.*",
                self._on_tracer,
                "forensic_tracer_handler",
            )
            self.post.subscribe(
                "fairy.booted",
                self._on_fairy_booted,
                "forensic_fairy_handler",
            )
            self.post.subscribe(
                "fairy.error",
                self._on_fairy_error,
                "forensic_error_handler",
            )
            # Subscribe to shadow health reports (Organ Template shadows publish here)
            self.post.subscribe(
                "shadow.*",
                self._on_shadow_health,
                "forensic_shadow_handler",
            )

        print(f"[{self.ACTOR_NAME}] Booted - monitoring system health")
        # Heartbeat via FairyBase postal system - Fifth Ring Principle
        return True

    def on_tick(self, beat: int) -> None:
        """Periodic maintenance."""
        # Prune old logs periodically
        if beat % 100 == 0:
            self._prune_old_logs()

        # Publish error summary periodically
        if beat % 10 == 0:
            self._publish_error_summary()

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_telemetry(self, envelope) -> None:
        """Handle telemetry events."""
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        self._ingest_event(payload, source="telemetry")

    def _on_tracer(self, envelope) -> None:
        """Handle tracer events."""
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        self._ingest_event(payload, source="tracer")

    def _on_fairy_booted(self, envelope) -> None:
        """Handle fairy boot events."""
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        actor = payload.get("fairy", "unknown")
        plane = payload.get("plane", "")

        card = self._get_or_create_card(actor)
        card.plane = plane
        card.update_health("ok", "Booted successfully")

    def _on_fairy_error(self, envelope) -> None:
        """Handle fairy error events."""
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        actor = payload.get("fairy", payload.get("actor", "unknown"))
        error = payload.get("error", payload.get("message", "Unknown error"))

        # Update card
        card = self._get_or_create_card(actor)
        card.record_error(error)
        card.update_health("error", error[:100])

        # Register in error registry
        self._register_error(actor, error, "error")

        # Raise alert
        self._raise_alert(actor, "Error", error[:200])

    def _on_shadow_health(self, envelope) -> None:
        """Handle shadow health reports from Organ Template fairies."""
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        actor = payload.get("actor", payload.get("fairy", "unknown"))
        status = payload.get("status", "unknown")

        # Update card from shadow health
        card = self._get_or_create_card(actor)
        card.last_seen_ts = time.time()

        # Shadows report health status
        if status in ("ok", "serene", "healthy"):
            card.update_health("ok", "Shadow reports healthy")
        elif status in ("warn", "anxious", "degraded"):
            card.update_health("warn", payload.get("message", "Shadow reports degraded"))
        elif status in ("error", "critical", "panic"):
            card.update_health("error", payload.get("message", "Shadow reports critical"))
            error_msg = payload.get("message", "Shadow health critical")
            self._register_error(actor, error_msg, "shadow_error")

    # =========================================================================
    # CORE LOGIC
    # =========================================================================

    def _ingest_event(self, payload: Dict, source: str = "unknown") -> None:
        """Process an incoming event."""
        self._events_processed += 1

        actor = payload.get("actor", payload.get("actor_name", payload.get("fairy", "unknown")))
        opcode = payload.get("opcode", "")
        level = payload.get("level", "info")

        # Get or create card
        card = self._get_or_create_card(actor)
        card.last_seen_ts = time.time()

        # Detect errors
        if self._is_error_event(payload):
            error_msg = self._extract_error_message(payload)
            card.record_error(error_msg)
            card.update_health("error", error_msg[:100])
            self._register_error(actor, error_msg, "error")
            self._raise_alert(actor, "Error", error_msg[:200])
        elif level in ("warn", "warning"):
            card.update_health("warn", str(payload.get("message", "Warning"))[:100])
        elif opcode in ("HEARTBEAT", "HEALTH_OK"):
            card.update_health("ok", "")

        # Log forensic entry
        self._forensic_log_entry(level, actor, opcode or source, payload)

    def _is_error_event(self, payload: Dict) -> bool:
        """Detect if an event represents an error."""
        # Check explicit error indicators
        if payload.get("level") in ("error", "critical", "fatal"):
            return True
        if payload.get("status") in ("error", "failed", "critical"):
            return True
        if "error" in str(payload.get("opcode", "")).lower():
            return True
        if payload.get("error"):
            return True
        if "exception" in str(payload).lower():
            return True
        return False

    def _extract_error_message(self, payload: Dict) -> str:
        """Extract error message from payload."""
        for key in ("error", "message", "error_message", "exception", "msg"):
            if key in payload and payload[key]:
                return str(payload[key])[:500]

        # Try nested payload
        nested = payload.get("payload", {})
        if isinstance(nested, dict):
            for key in ("error", "message", "exception"):
                if key in nested and nested[key]:
                    return str(nested[key])[:500]

        return "Unknown error"

    # =========================================================================
    # CARD MANAGEMENT
    # =========================================================================

    def _get_or_create_card(self, actor: str) -> ForensicCard:
        """Get or create a forensic card for an actor."""
        with self._cards_lock:
            if actor not in self._cards:
                self._cards[actor] = ForensicCard(actor=actor)
            return self._cards[actor]

    def get_card(self, actor: str) -> Optional[Dict[str, Any]]:
        """Get a card as dict."""
        with self._cards_lock:
            card = self._cards.get(actor)
            return card.to_dict() if card else None

    def get_all_cards(self) -> Dict[str, Dict[str, Any]]:
        """Get all cards."""
        with self._cards_lock:
            return {actor: card.to_dict() for actor, card in self._cards.items()}

    # =========================================================================
    # ERROR REGISTRY
    # =========================================================================

    _MAX_ERROR_REGISTRY_SIZE = 500  # FIX 2026-02-16: Cap error registry to prevent unbounded growth

    def _register_error(
        self, actor: str, message: str, level: str = "error", details: Dict = None
    ) -> None:
        """Register an error for dashboard consumption."""
        now = time.time()
        normalized = self._normalize_error_message(message)
        key = f"{actor}:{level}:{normalized[:100]}"

        with self._error_registry_lock:
            if key in self._error_registry:
                self._error_registry[key]["count"] += 1
                self._error_registry[key]["last_seen"] = now
            else:
                # FIX 2026-02-16: Evict oldest errors if registry is too large.
                # Without this cap, the registry grows forever (~1KB per unique error).
                if len(self._error_registry) >= self._MAX_ERROR_REGISTRY_SIZE:
                    # Remove the 100 oldest entries by last_seen
                    sorted_keys = sorted(
                        self._error_registry.keys(),
                        key=lambda k: self._error_registry[k].get("last_seen", 0)
                    )
                    for old_key in sorted_keys[:100]:
                        del self._error_registry[old_key]

                self._error_registry[key] = {
                    "count": 1,
                    "first_seen": now,
                    "last_seen": now,
                    "message": message[:500],
                    "actor": actor,
                    "level": level,
                    "details": details or {},
                }

    def _normalize_error_message(self, message: str) -> str:
        """Normalize error message for deduplication."""
        msg = str(message)
        # Remove timestamps
        msg = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", "<TS>", msg)
        # Remove hex addresses
        msg = re.sub(r"0x[0-9a-fA-F]+", "<ADDR>", msg)
        # Remove UUIDs
        msg = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "<UUID>",
            msg,
        )
        # Remove line numbers
        msg = re.sub(r"line \d+", "line <N>", msg)
        return msg

    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary for dashboard."""
        with self._error_registry_lock:
            errors = list(self._error_registry.values())
            # Sort by count (most frequent first)
            errors.sort(key=lambda x: x["count"], reverse=True)
            return {
                "count": len(errors),
                "errors": errors[:50],  # Limit to top 50
            }

    def clear_errors(self) -> int:
        """Clear error registry."""
        with self._error_registry_lock:
            count = len(self._error_registry)
            self._error_registry.clear()
            return count

    def _publish_error_summary(self) -> None:
        """Publish error summary to fabric."""
        if not self.post:
            return

        summary = self.get_error_summary()
        if summary["count"] > 0:
            self.post.publish(
                "forensic.error_summary",
                {
                    "error_count": summary["count"],
                    "top_errors": summary["errors"][:10],
                    "ts": time.time(),
                },
            )

    # =========================================================================
    # ALERTS
    # =========================================================================

    def _raise_alert(
        self,
        actor: str,
        title: str,
        message: str,
        level: str = "warn",
    ) -> None:
        """Raise a de-duplicated alert."""
        key = (actor, title)
        now = time.time()
        last = self._recent_alerts.get(key, 0.0)

        if now - last < self.ALERT_SUPPRESS_SECONDS:
            return

        self._recent_alerts[key] = now
        self._alerts_raised += 1

        # FIX 2026-02-16: Cap alert dedup dict to prevent unbounded growth
        if len(self._recent_alerts) > 1000:
            # Remove entries older than 5 minutes
            cutoff = now - 300.0
            self._recent_alerts = {k: v for k, v in self._recent_alerts.items() if v > cutoff}

        payload = {
            "title": title,
            "message": message,
            "actor": actor,
            "level": level,
            "ts": now,
        }

        # Publish to fabric
        if self.post:
            self.post.publish("forensic.alert", payload)

        # Log to forensic diary
        self._forensic_log_entry(level, actor, f"ALERT:{title}", {"message": message})

    # =========================================================================
    # FORENSIC LOG
    # =========================================================================

    def _forensic_log_entry(
        self, level: str, actor: str, event: str, details: Dict
    ) -> None:
        """Add entry to forensic log (in-memory + disk)."""
        now = time.time()
        entry = {
            "ts": now,
            "level": level,
            "actor": actor,
            "event": event,
            "details": details,
        }

        # Deduplicate before adding
        try:
            sig = hashlib.md5(
                json.dumps(
                    {"level": level, "actor": actor, "event": event}, sort_keys=True
                ).encode()
            ).hexdigest()

            if sig in self._recent_forensic_sigs:
                return

            self._recent_forensic_sigs.append(sig)
        except Exception:
            pass

        # Add to in-memory log
        with self._forensic_log_lock:
            self._forensic_log.append(entry)
            # Trim if over limit
            # FIX 2026-04-05: deque auto-caps
            pass

        # Write to disk
        self._write_forensic_diary(entry)

    def _write_forensic_diary(self, entry: Dict) -> None:
        """Write entry to forensic diary file."""
        try:
            day = time.strftime("%Y-%m-%d", time.gmtime())
            diary_path = self.storage_dir / f"{day}.jsonl"

            with open(diary_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _prune_old_logs(self) -> None:
        """Remove old forensic log files."""
        try:
            import glob

            horizon = self.FORENSIC_KEEP_DAYS * 86400
            now = time.time()

            for path in self.storage_dir.glob("*.jsonl"):
                try:
                    if now - path.stat().st_mtime > horizon:
                        path.unlink()
                except Exception:
                    continue
        except Exception:
            pass

    # =========================================================================
    # INTENTS
    # =========================================================================

    def intent_get_system_health(self, params: Dict = None) -> Dict[str, Any]:
        """Get system health snapshot."""
        cards = self.get_all_cards()

        # Aggregate health
        health_counts = {"ok": 0, "warn": 0, "error": 0, "critical": 0, "unknown": 0}
        for card in cards.values():
            status = card.get("health", {}).get("status", "unknown")
            if status in health_counts:
                health_counts[status] += 1
            else:
                health_counts["unknown"] += 1

        # Overall status
        if health_counts["critical"] > 0:
            overall = "critical"
        elif health_counts["error"] > 0:
            overall = "error"
        elif health_counts["warn"] > 0:
            overall = "warn"
        elif health_counts["ok"] > 0:
            overall = "ok"
        else:
            overall = "unknown"

        return {
            "ok": True,
            "overall_status": overall,
            "health_counts": health_counts,
            "actor_count": len(cards),
            "events_processed": self._events_processed,
            "alerts_raised": self._alerts_raised,
        }

    def intent_get_error_summary(self, params: Dict = None) -> Dict[str, Any]:
        """Get error summary."""
        return {"ok": True, **self.get_error_summary()}

    def intent_clear_errors(self, params: Dict = None) -> Dict[str, Any]:
        """Clear error registry."""
        count = self.clear_errors()
        return {"ok": True, "cleared": count}

    # =========================================================================
    # STATUS
    # =========================================================================

    def status(self) -> Dict[str, Any]:
        """Get forensic scribe status."""
        base = super().status()
        base.update({
            "actor_count": len(self._cards),
            "error_registry_count": len(self._error_registry),
            "forensic_log_count": len(self._forensic_log),
            "events_processed": self._events_processed,
            "alerts_raised": self._alerts_raised,
        })
        return base


# =============================================================================
# SINGLETON
# =============================================================================

_forensic_fairy: Optional[ForensicScribeFairy] = None


def get_forensic_fairy() -> ForensicScribeFairy:
    """Get singleton ForensicScribeFairy instance."""
    global _forensic_fairy
    if _forensic_fairy is None:
        _forensic_fairy = ForensicScribeFairy()
        _forensic_fairy.boot()
    return _forensic_fairy


def set_forensic_fairy(fairy: ForensicScribeFairy) -> None:
    """Set the global forensic fairy instance."""
    global _forensic_fairy
    _forensic_fairy = fairy
