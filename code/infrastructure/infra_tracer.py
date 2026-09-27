"""
Infrastructure Tracer — Lightweight tracing for non-fairy system actors.

Non-fairy infrastructure (watchdog, pacemaker, GPU monitor, etc.) runs in
background threads making critical decisions (killing processes, scaling pools,
detecting failures) with ZERO visibility to the consciousness layer.

This module provides a minimal, safe-to-call-anywhere tracer that:
  1. Generates trace_ids for every significant action
  2. Publishes to postal via `telemetry.infra.*` topics
     (ForensicScribeFairy already subscribes to `telemetry.*`)
  3. Maintains an in-memory ring buffer for direct query
  4. Registers infrastructure actors so they're discoverable
  5. Degrades gracefully when postal isn't ready (early boot)

Usage:
    from infrastructure.infra_tracer import get_infra_tracer

    tracer = get_infra_tracer()

    # Register your module once at startup
    tracer.register_actor("memory_watchdog", role="daemon",
                          description="Monitors RAM, kills zombie processes")

    # Emit events for significant actions
    tracer.emit("memory_watchdog", "zombie_killed", {
        "pid": 1234, "role": "stale_mcp", "freed_mb": 150.3
    }, severity="warning")

    # Emit with auto-generated trace_id returned
    trace_id = tracer.emit("pacemaker", "heartbeat_degraded", {
        "consecutive_errors": 5
    }, severity="error")

Topics published (all under telemetry.* so ForensicScribe picks them up):
    telemetry.infra.{actor}.{event}
    e.g. telemetry.infra.watchdog.zombie_killed
         telemetry.infra.pacemaker.beat_error
         telemetry.infra.gpu_monitor.threshold_crossed

2026-03-14 — Created for the Invisible Actors initiative.
"""

import time
import uuid
import threading
from collections import deque
from typing import Any, Dict, List, Optional


# ── Severity levels ──────────────────────────────────────────────────────
SEVERITY_DEBUG = "debug"
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"
SEVERITY_CRITICAL = "critical"


class InfraEvent:
    """A single infrastructure event with trace context."""

    __slots__ = (
        "trace_id", "actor", "event", "payload", "severity",
        "timestamp", "thread_name",
    )

    def __init__(self, actor: str, event: str, payload: Dict[str, Any],
                 severity: str = SEVERITY_INFO):
        self.trace_id = uuid.uuid4().hex[:12]
        self.actor = actor
        self.event = event
        self.payload = payload or {}
        self.severity = severity
        self.timestamp = time.time()
        self.thread_name = threading.current_thread().name

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "actor": self.actor,
            "event": self.event,
            "payload": self.payload,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "thread": self.thread_name,
        }


class InfraActor:
    """Registration record for an infrastructure actor."""

    __slots__ = (
        "name", "role", "description", "registered_at",
        "event_count", "last_event_at",
    )

    def __init__(self, name: str, role: str = "unknown",
                 description: str = ""):
        self.name = name
        self.role = role
        self.description = description
        self.registered_at = time.time()
        self.event_count = 0
        self.last_event_at = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "registered_at": self.registered_at,
            "event_count": self.event_count,
            "last_event_at": self.last_event_at,
        }


class InfraTracer:
    """Lightweight tracer for non-fairy infrastructure actors.

    Thread-safe. Safe to call from any thread, any time, even during
    early boot before postal is available.
    """

    def __init__(self, max_events: int = 2000):
        self._lock = threading.Lock()
        self._actors: Dict[str, InfraActor] = {}
        self._events: deque = deque(maxlen=max_events)
        self._postal = None
        self._postal_checked = False
        self._started = False

        # Stats
        self._total_emitted = 0
        self._total_published = 0
        self._total_dropped = 0  # postal not available

    def start(self):
        """Mark tracer as started. Called from server.py boot."""
        self._started = True
        self._try_connect_postal()
        print(f"[InfraTracer] Started — tracking infrastructure actors via telemetry.infra.*")

    def _try_connect_postal(self):
        """Lazily connect to the shared postal hub.

        FIX 2026-03-16 Nous: Check if shared fabric exists BEFORE calling
        get_shared_postal_hub(). That function creates a STANDALONE orphan
        TensorFabric when the shared one isn't set yet — which happens when
        error_capture/infra_tracer start before SYSTEM.fabric is created.
        Better to return False and retry later than create an orphan.
        """
        if self._postal is not None:
            return True
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_fabric, get_shared_postal_hub
            # Don't trigger orphan creation — only connect if fabric is ready
            if get_shared_fabric() is None:
                return False  # Too early in boot — fabric not created yet
            hub = get_shared_postal_hub()
            if hub is not None:
                self._postal = hub
                self._postal_checked = True
                return True
        except Exception:
            pass
        return False

    def register_actor(self, name: str, role: str = "daemon",
                       description: str = ""):
        """Register an infrastructure actor for discoverability.

        Args:
            name: Unique actor name (e.g., "memory_watchdog")
            role: Actor role (daemon, monitor, bridge, proxy, worker)
            description: What this actor does
        """
        with self._lock:
            if name not in self._actors:
                self._actors[name] = InfraActor(name, role, description)
                # Announce registration to postal if available
                self._publish_event(InfraEvent(
                    actor=name,
                    event="registered",
                    payload={"role": role, "description": description},
                    severity=SEVERITY_INFO,
                ))

    def emit(self, actor: str, event: str, payload: Optional[Dict] = None,
             severity: str = SEVERITY_INFO) -> str:
        """Emit an infrastructure event.

        This is the primary API. Call this for any significant action:
        process kills, health alerts, state changes, threshold crossings.

        Args:
            actor: Infrastructure actor name (e.g., "memory_watchdog")
            event: Event name (e.g., "zombie_killed", "threshold_crossed")
            payload: Event data dict
            severity: debug/info/warning/error/critical

        Returns:
            trace_id for the event (12-char hex)
        """
        evt = InfraEvent(actor, event, payload or {}, severity)

        with self._lock:
            self._events.append(evt)
            self._total_emitted += 1

            # Update actor stats if registered
            if actor in self._actors:
                self._actors[actor].event_count += 1
                self._actors[actor].last_event_at = evt.timestamp

        # Publish to postal (outside lock to avoid deadlocks)
        self._publish_event(evt)

        return evt.trace_id

    def _publish_event(self, evt: InfraEvent):
        """Publish event to postal hub. Safe to call anytime."""
        # Try to connect if we haven't yet
        if self._postal is None:
            self._try_connect_postal()

        if self._postal is None:
            self._total_dropped += 1
            return

        topic = f"telemetry.infra.{evt.actor}.{evt.event}"
        try:
            self._postal.publish(topic, evt.to_dict())
            self._total_published += 1
        except Exception:
            self._total_dropped += 1

    # ── Query API ────────────────────────────────────────────────────

    def get_actors(self) -> List[dict]:
        """Get all registered infrastructure actors."""
        with self._lock:
            return [a.to_dict() for a in self._actors.values()]

    def get_events(self, actor: Optional[str] = None,
                   severity: Optional[str] = None,
                   limit: int = 50) -> List[dict]:
        """Get recent events, optionally filtered.

        Args:
            actor: Filter by actor name
            severity: Filter by severity level
            limit: Max events to return

        Returns:
            List of event dicts, newest first.
        """
        with self._lock:
            events = list(self._events)

        # Filter
        if actor:
            events = [e for e in events if e.actor == actor]
        if severity:
            events = [e for e in events if e.severity == severity]

        # Newest first, limited
        events.reverse()
        return [e.to_dict() for e in events[:limit]]

    def get_events_by_trace(self, trace_id: str) -> Optional[dict]:
        """Find a specific event by trace_id."""
        with self._lock:
            for e in self._events:
                if e.trace_id == trace_id:
                    return e.to_dict()
        return None

    def get_status(self) -> dict:
        """Get tracer status summary."""
        with self._lock:
            actor_summary = {}
            for name, actor in self._actors.items():
                actor_summary[name] = {
                    "role": actor.role,
                    "events": actor.event_count,
                    "last_event": actor.last_event_at,
                }
        return {
            "started": self._started,
            "actors_registered": len(actor_summary),
            "actors": actor_summary,
            "total_emitted": self._total_emitted,
            "total_published": self._total_published,
            "total_dropped": self._total_dropped,
            "postal_connected": self._postal is not None,
            "buffer_size": len(self._events),
        }

    # ── Convenience methods for common patterns ──────────────────────

    def process_killed(self, actor: str, pid: int, reason: str,
                       freed_mb: float = 0.0, role: str = "unknown"):
        """Convenience: emit a process-kill event (always WARNING+)."""
        self.emit(actor, "process_killed", {
            "pid": pid,
            "reason": reason,
            "freed_mb": round(freed_mb, 1),
            "process_role": role,
        }, severity=SEVERITY_WARNING)

    def health_alert(self, actor: str, metric: str, value: float,
                     threshold: float, severity: str = SEVERITY_WARNING):
        """Convenience: emit a health threshold crossing."""
        self.emit(actor, "health_alert", {
            "metric": metric,
            "value": round(value, 2),
            "threshold": round(threshold, 2),
        }, severity=severity)

    def lifecycle(self, actor: str, event: str, details: Optional[Dict] = None):
        """Convenience: emit a lifecycle event (started/stopped/error)."""
        self.emit(actor, event, details or {}, severity=SEVERITY_INFO)

    def decision(self, actor: str, what: str, details: Optional[Dict] = None):
        """Convenience: emit a decision event (scaling, routing, gating)."""
        self.emit(actor, "decision", {
            "what": what,
            **(details or {}),
        }, severity=SEVERITY_INFO)


# ── Module-level singleton ───────────────────────────────────────────────
_infra_tracer: Optional[InfraTracer] = None
_infra_lock = threading.Lock()


def get_infra_tracer() -> InfraTracer:
    """Get the global infrastructure tracer singleton.

    Safe to call from anywhere, anytime. Creates the instance on first call.
    """
    global _infra_tracer
    if _infra_tracer is None:
        with _infra_lock:
            if _infra_tracer is None:
                _infra_tracer = InfraTracer()
    return _infra_tracer


def start_infra_tracer() -> InfraTracer:
    """Start the infrastructure tracer. Called from server.py boot."""
    tracer = get_infra_tracer()
    tracer.start()
    return tracer
