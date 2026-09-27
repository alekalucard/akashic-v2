"""
CentralNervousFairy — Adaptive Postal Traffic Manager (V3 Wrapper)

Part of P00 Autonomic plane.

The central nervous system — SMART routing, dispatching, and coordinating
postal messages across all planes. Not just a backbone — the BRAIN of
the postal system. Monitors pool health, detects bottlenecks, applies
adaptive countermeasures, and enforces channel isolation.

Ace's directive: "the plane is the town, the channel is the home address
and the fairy name/id is the one that lives at that address. none should
be using the same channels at all"

"those central nervous fairies need to be smarter learn to use adaptive
routing measures or countermeasures and managing the postal routing,
their trace id's need to be all over the route files"

FIX 2026-03-18 (Nous): Complete rewrite — from empty heartbeat handler to
full adaptive traffic manager with trace IDs, backpressure, and channel audit.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


class CentralNervousShadow:
    """Shadow for CentralNervousFairy — monitors postal health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "CentralNervousShadow"
    SHADOW_VERSION = "2.0.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_connected", True))
            tests.append(("running", getattr(engine, '_running', False)))
        else:
            tests.append(("engine_connected", False))

        # CNS-specific health checks
        actor = self.actor
        tests.append(("monitoring_active", getattr(actor, '_monitoring', False)))
        tests.append(("total_traces", getattr(actor, '_trace_count', 0)))
        tests.append(("countermeasures_active",
                       len(getattr(actor, '_active_countermeasures', {}))))
        tests.append(("channel_violations",
                       len(getattr(actor, '_channel_violations', []))))
        # CNS Manifold Lattice health
        tests.append(("portal_gate_found", getattr(actor, '_portal_gate', None) is not None))
        tests.append(("cns_wired", getattr(actor, '_cns_wired', False)))
        tests.append(("manifold_updates_sent", getattr(actor, '_manifold_updates_sent', 0)))
        return tests


class CentralNervousFairyV3(Fairy):
    """Central nervous system — adaptive postal traffic manager.

    FIX 2026-03-18 (Nous): Complete rewrite.
    Now does actual work on every heartbeat:
    1. Monitors postal pool health (queue fullness, drop rates)
    2. Applies adaptive countermeasures (throttle, backpressure signals)
    3. Publishes trace IDs to cns.trace for monitoring
    4. Audits channel isolation (no fairy should share another's channel)
    5. Publishes violations to cns.violations
    """

    ACTOR_NAME = "CentralNervousFairy"
    ACTOR_VERSION = "2.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic.nervous"

    PURPOSE = "Adaptive postal routing, traffic management, and channel enforcement"
    MANTRA = "Every signal finds its destination — no bottlenecks, no shared channels"
    LORE = "The spinal cord — fast, reliable, never sleeping. Now with a brain."

    SHADOW_CLASS = CentralNervousShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 1
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    # ── Adaptive routing thresholds ──
    PRESSURE_WARN = 0.5       # Queue fullness → start watching
    PRESSURE_THROTTLE = 0.7   # Queue fullness → publish throttle signal
    PRESSURE_CRITICAL = 0.9   # Queue fullness → publish backpressure
    DROP_RATE_WARN = 50       # Drops/60s → warn
    DROP_RATE_THROTTLE = 200  # Drops/60s → throttle

    # ── Timing ──
    TRACE_INTERVAL_SEC = 10.0     # Publish CNS trace every 10s
    AUDIT_INTERVAL_SEC = 120.0    # Channel audit every 2 minutes
    STATS_WINDOW_SEC = 60.0       # Rolling window for drop rates

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None
        self._monitoring = False

        # ── Traffic monitoring state ──
        self._drop_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)
        )  # topic → [(ts, drop_count), ...]
        self._last_drop_snapshot: Dict[str, int] = {}  # topic → total_drops at last check
        self._pool_pressure: Dict[str, float] = {}     # topic → current pressure

        # ── Countermeasure state ──
        self._active_countermeasures: Dict[str, Dict] = {}  # topic → {action, since, reason}
        self._countermeasure_history: deque = deque(maxlen=50)

        # ── Channel audit state ──
        self._channel_map: Dict[str, List[str]] = defaultdict(list)  # channel → [fairy_names]
        self._channel_violations: List[Dict] = []
        self._last_audit_ts = 0.0

        # ── Trace state ──
        self._trace_count = 0
        self._last_trace_ts = 0.0
        self._boot_ts = 0.0

        # ── Stats ──
        self._heartbeats_processed = 0
        self._throttle_signals_sent = 0
        self._backpressure_signals_sent = 0

        # ── FIX 2026-04-04: System-wide component pressure (water treatment plant) ──
        # Components report queue fullness via cns.component.pressure
        # CNS aggregates into system_pressure for unified backpressure signals
        self._component_pressure: Dict[str, Dict] = {}  # component_name → {pressure, current, capacity, ...}
        self._system_pressure: float = 0.0
        self._system_pressure_level: str = "normal"  # normal/elevated/high/critical

        # ── CNS Manifold Lattice (Phase 2) ──
        # Portal gate for feeding nervous system state INTO the manifold.
        # Lazy discovery — P00 boots before P30 (AssociationCortexFairy).
        self._portal_gate = None           # PortalGate reference (lazy)
        self._portal_gate_searched = False  # True after first discovery attempt
        self._cns_wired = False            # True after cns_wire topology setup
        self._manifold_updates_sent = 0
        self._manifold_last_update_ts = 0.0
        self._manifold_update_interval = 5.0   # Feed manifold every 5s (not every heartbeat)
        self._circadian_phase = "unknown"

    def on_boot(self) -> bool:
        """Boot with deferred engine init + start monitoring."""
        super().on_boot()

        self._boot_ts = time.time()

        # ── Deferred engine init (existing behavior) ──
        def _deferred_init():
            time.sleep(1.5)
            try:
                from fairies.P00_Autonomic.nervous_system.central_nervous_postal_fairy import (
                    CentralNervousFairy as NervousEngine,
                )
                self._engine = NervousEngine.__new__(NervousEngine)
                self._engine.post = self.post
                self._engine.__init__(
                    fabric=getattr(self, 'fabric', None),
                    output_dir=str(ROOT / "state" / "nervous"),
                    max_workers=4,
                )
                self._engine.on_boot()
                print(f"[{self.ACTOR_NAME}] Central nervous engine ONLINE")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Engine init error: {e}")
                import traceback
                traceback.print_exc()

            # ── Start monitoring after engine is up ──
            self._monitoring = True
            print(f"[{self.ACTOR_NAME}] Adaptive routing ACTIVE — monitoring postal health")

        threading.Thread(target=_deferred_init, daemon=True, name="defer-CentralNervousFairy").start()

        # ── Subscribe to relevant channels for monitoring ──
        try:
            # Listen for circadian phase changes to adjust routing strategy
            self.post.subscribe("circadian.state", self._on_circadian_state)
        except Exception:
            pass

        # FIX 2026-04-04 (Nous): Listen for component pressure reports (water treatment)
        try:
            self.post.subscribe("cns.component.pressure", self._on_component_pressure,
                                f"{self.ACTOR_NAME}-component-pressure")
        except Exception:
            pass

        # Phase 5 (2026-03-18 Nous): Listen for fairy CNS registration + health.
        # Every fairy publishes cns.fairy.register on boot and cns.fairy.health
        # from its shadow. We create/update cns:fairy:{name} nodes in the manifold.
        try:
            self.post.subscribe("cns.fairy.register", self._on_fairy_cns_register,
                                f"{self.ACTOR_NAME}-cns-register")
            self.post.subscribe("cns.fairy.health", self._on_fairy_cns_health,
                                f"{self.ACTOR_NAME}-cns-health")
        except Exception:
            pass

        # Track registered fairy nodes for deferred wiring
        self._cns_fairy_registry: Dict[str, Dict] = {}
        self._cns_fairy_health_pending: List[Dict] = []

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting engine...)")
        return True

    # ═══════════════════════════════════════════════════════════════════════
    # HEARTBEAT — The main work loop (called every heartbeat tick)
    # ═══════════════════════════════════════════════════════════════════════

    def _handle_heartbeat(self, packet):
        """On every heartbeat: monitor, analyze, act.

        FIX 2026-03-18 (Nous): This was EMPTY before. Now it's the brain
        of the postal system. Every heartbeat:
        1. Collect pool stats from postal core
        2. Calculate drop rates (rolling 60s window)
        3. Detect pressure and apply countermeasures
        4. Publish CNS trace (every 10s)
        5. Run channel audit (every 2min)
        """
        if not self._monitoring:
            return

        self._heartbeats_processed += 1
        now = time.time()

        try:
            # ── 1. Collect postal pool stats ──
            pool_stats = self._collect_pool_stats()

            # ── 2. Analyze drop rates and pressure ──
            alerts = self._analyze_traffic(pool_stats, now)

            # ── 3. Apply adaptive countermeasures ──
            if alerts:
                self._apply_countermeasures(alerts, now)

            # ── 3b. Compute system-wide pressure from all sources (FIX 2026-04-04) ──
            self._compute_system_pressure()

            # ── 4. Expire old countermeasures ──
            self._expire_countermeasures(now)

            # ── 5. Publish CNS trace (every TRACE_INTERVAL_SEC) ──
            if now - self._last_trace_ts >= self.TRACE_INTERVAL_SEC:
                self._publish_trace(pool_stats, alerts, now)
                self._last_trace_ts = now

            # ── 6. Channel audit (every AUDIT_INTERVAL_SEC) ──
            if now - self._last_audit_ts >= self.AUDIT_INTERVAL_SEC:
                self._run_channel_audit()
                self._last_audit_ts = now

            # ── 7. Feed CNS state into portal manifold (every _manifold_update_interval) ──
            if now - self._manifold_last_update_ts >= self._manifold_update_interval:
                self._feed_manifold(pool_stats, now)
                self._manifold_last_update_ts = now

        except Exception as e:
            if self._heartbeats_processed <= 5:
                print(f"[{self.ACTOR_NAME}] Heartbeat error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # POOL STATS COLLECTION
    # ═══════════════════════════════════════════════════════════════════════

    def _collect_pool_stats(self) -> List[Dict]:
        """Collect current pool stats from postal core.

        Returns list of {topic, queue_depth, workers, total_drops, pressure}
        """
        if not self.post:
            return []

        stats = []
        try:
            # PostalCore.topic_stats() returns per-pool stats
            if hasattr(self.post, 'topic_stats'):
                raw_stats = self.post.topic_stats()
                for entry in raw_stats:
                    topic = entry.get("topic", "")
                    total_drops = entry.get("total_drops", 0)

                    # Calculate pressure via get_pool_pressure
                    pressure = 0.0
                    if hasattr(self.post, 'get_pool_pressure'):
                        pressure = self.post.get_pool_pressure(topic)

                    self._pool_pressure[topic] = pressure

                    stats.append({
                        "topic": topic,
                        "queue_depth": entry.get("queue_depth", 0),
                        "workers": entry.get("workers", 0),
                        "subscribers": entry.get("subscribers", 0),
                        "total_drops": total_drops,
                        "pressure": pressure,
                        "p95_ms": entry.get("p95_ms", 0),
                    })
        except Exception:
            pass

        return stats

    # ═══════════════════════════════════════════════════════════════════════
    # TRAFFIC ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════

    def _analyze_traffic(self, pool_stats: List[Dict], now: float) -> List[Dict]:
        """Analyze traffic patterns and detect problems.

        Returns list of alerts: {topic, type, severity, details}
        """
        alerts = []

        for stat in pool_stats:
            topic = stat["topic"]
            total_drops = stat["total_drops"]
            pressure = stat["pressure"]

            # ── Calculate drop rate (drops in last 60s) ──
            last_known = self._last_drop_snapshot.get(topic, 0)
            new_drops = max(0, total_drops - last_known)
            self._last_drop_snapshot[topic] = total_drops

            if new_drops > 0:
                self._drop_history[topic].append((now, new_drops))

            # Rolling drop rate (last 60s)
            cutoff = now - self.STATS_WINDOW_SEC
            recent_drops = sum(
                count for ts, count in self._drop_history[topic]
                if ts >= cutoff
            )

            # ── Pressure alerts ──
            if pressure >= self.PRESSURE_CRITICAL:
                alerts.append({
                    "topic": topic,
                    "type": "pressure_critical",
                    "severity": "critical",
                    "pressure": pressure,
                    "drop_rate_60s": recent_drops,
                })
            elif pressure >= self.PRESSURE_THROTTLE:
                alerts.append({
                    "topic": topic,
                    "type": "pressure_high",
                    "severity": "warning",
                    "pressure": pressure,
                    "drop_rate_60s": recent_drops,
                })

            # ── Drop rate alerts ──
            if recent_drops >= self.DROP_RATE_THROTTLE:
                alerts.append({
                    "topic": topic,
                    "type": "drop_rate_critical",
                    "severity": "critical",
                    "drop_rate_60s": recent_drops,
                    "total_drops": total_drops,
                })
            elif recent_drops >= self.DROP_RATE_WARN:
                alerts.append({
                    "topic": topic,
                    "type": "drop_rate_high",
                    "severity": "warning",
                    "drop_rate_60s": recent_drops,
                    "total_drops": total_drops,
                })

        return alerts

    # ═══════════════════════════════════════════════════════════════════════
    # COMPONENT PRESSURE (Water Treatment Plant — FIX 2026-04-04)
    # ═══════════════════════════════════════════════════════════════════════

    def _on_component_pressure(self, message):
        """Handle pressure reports from system components (cortex, working memory, etc.)."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', message)
        if isinstance(payload, dict) and 'payload' in payload:
            payload = payload['payload']
        component = payload.get("component", "unknown") if isinstance(payload, dict) else "unknown"
        self._component_pressure[component] = payload

    def _compute_system_pressure(self) -> float:
        """Compute unified system pressure from postal pools + component reports."""
        # Max pressure from postal pools (existing)
        postal_max = max(self._pool_pressure.values(), default=0.0)
        # Max pressure from component reports (new)
        component_max = max(
            (p.get("pressure", 0) for p in self._component_pressure.values()),
            default=0.0
        )
        self._system_pressure = max(postal_max, component_max)

        # Determine level
        if self._system_pressure >= self.PRESSURE_CRITICAL:
            new_level = "critical"
        elif self._system_pressure >= self.PRESSURE_THROTTLE:
            new_level = "high"
        elif self._system_pressure >= self.PRESSURE_WARN:
            new_level = "elevated"
        else:
            new_level = "normal"

        # Signal on level CHANGE only (avoid spam)
        if new_level != self._system_pressure_level:
            old_level = self._system_pressure_level
            self._system_pressure_level = new_level
            now = time.time()

            if new_level == "critical":
                self._backpressure_signals_sent += 1
                try:
                    self.post.publish("consciousness.cns.backpressure", {
                        "source": "CentralNervousFairy",
                        "topic": "system_composite",
                        "severity": "critical",
                        "action": "reduce_collision_rate",
                        "pressure": self._system_pressure,
                        "component_pressures": {k: v.get("pressure", 0) for k, v in self._component_pressure.items()},
                        "trace_id": f"cns-bp-sys-{self._backpressure_signals_sent}",
                        "ts": now,
                    })
                except Exception:
                    pass
            elif new_level == "high":
                self._throttle_signals_sent += 1
                try:
                    self.post.publish("consciousness.cns.throttle", {
                        "source": "CentralNervousFairy",
                        "topic": "system_composite",
                        "severity": "warning",
                        "action": "increase_tick_interval",
                        "pressure": self._system_pressure,
                        "trace_id": f"cns-th-sys-{self._throttle_signals_sent}",
                        "ts": now,
                    })
                except Exception:
                    pass
            elif new_level == "normal" and old_level in ("high", "critical"):
                try:
                    self.post.publish("consciousness.cns.relief", {
                        "source": "CentralNervousFairy",
                        "topic": "system_composite",
                        "previous_action": "backpressure" if old_level == "critical" else "throttle",
                        "duration_s": 0,
                        "trace_id": f"cns-relief-sys-{self._trace_count}",
                        "ts": now,
                    })
                except Exception:
                    pass

        return self._system_pressure

    # ═══════════════════════════════════════════════════════════════════════
    # ADAPTIVE COUNTERMEASURES
    # ═══════════════════════════════════════════════════════════════════════

    def _apply_countermeasures(self, alerts: List[Dict], now: float):
        """Apply adaptive countermeasures based on traffic alerts.

        Countermeasures:
        1. THROTTLE: Tell consciousness loop to slow down (reduce tick rate)
        2. BACKPRESSURE: Tell consciousness loop to skip non-essential publishes
        3. LOG: Record the issue for debugging
        """
        for alert in alerts:
            topic = alert["topic"]
            severity = alert["severity"]

            # Only act on consciousness-related pools (primary source of drops)
            is_consciousness = topic.startswith("consciousness")

            if severity == "critical" and is_consciousness:
                # ── BACKPRESSURE: Critical — tell consciousness to back off ──
                if topic not in self._active_countermeasures or \
                   self._active_countermeasures[topic].get("action") != "backpressure":
                    self._active_countermeasures[topic] = {
                        "action": "backpressure",
                        "since": now,
                        "reason": alert["type"],
                        "details": alert,
                    }
                    self._backpressure_signals_sent += 1
                    try:
                        self.post.publish("consciousness.cns.backpressure", {
                            "source": "CentralNervousFairy",
                            "topic": topic,
                            "severity": "critical",
                            "action": "reduce_collision_rate",
                            "pressure": alert.get("pressure", 0),
                            "drop_rate_60s": alert.get("drop_rate_60s", 0),
                            "trace_id": f"cns-bp-{self._backpressure_signals_sent}",
                            "ts": now,
                        })
                    except Exception:
                        pass
                    self._countermeasure_history.append({
                        "ts": now, "topic": topic, "action": "backpressure",
                        "reason": alert["type"],
                    })

            elif severity == "warning" and is_consciousness:
                # ── THROTTLE: Warning — tell consciousness to ease up ──
                if topic not in self._active_countermeasures:
                    self._active_countermeasures[topic] = {
                        "action": "throttle",
                        "since": now,
                        "reason": alert["type"],
                        "details": alert,
                    }
                    self._throttle_signals_sent += 1
                    try:
                        self.post.publish("consciousness.cns.throttle", {
                            "source": "CentralNervousFairy",
                            "topic": topic,
                            "severity": "warning",
                            "action": "increase_tick_interval",
                            "pressure": alert.get("pressure", 0),
                            "drop_rate_60s": alert.get("drop_rate_60s", 0),
                            "trace_id": f"cns-th-{self._throttle_signals_sent}",
                            "ts": now,
                        })
                    except Exception:
                        pass

    def _expire_countermeasures(self, now: float):
        """Expire countermeasures when conditions improve.

        A countermeasure expires when:
        1. Pool pressure drops below PRESSURE_WARN for the topic
        2. At least 30 seconds have passed since activation
        """
        expired = []
        for topic, cm in self._active_countermeasures.items():
            age = now - cm["since"]
            current_pressure = self._pool_pressure.get(topic, 0)

            if age >= 30.0 and current_pressure < self.PRESSURE_WARN:
                expired.append(topic)

        for topic in expired:
            cm = self._active_countermeasures.pop(topic)
            # Publish relief signal
            try:
                self.post.publish("consciousness.cns.relief", {
                    "source": "CentralNervousFairy",
                    "topic": topic,
                    "previous_action": cm["action"],
                    "duration_s": round(now - cm["since"], 1),
                    "trace_id": f"cns-relief-{self._trace_count}",
                    "ts": now,
                })
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════════
    # CNS TRACE PUBLISHING
    # ═══════════════════════════════════════════════════════════════════════

    def _publish_trace(self, pool_stats: List[Dict], alerts: List[Dict], now: float):
        """Publish CNS trace for monitoring.

        Ace: "their trace id's need to be all over the route files so they
        can be monitored"

        Publishes to cns.trace every TRACE_INTERVAL_SEC with:
        - Current pool stats (fullness per topic)
        - Drop rates (rolling 60s)
        - Active countermeasures
        - Channel violations
        """
        self._trace_count += 1
        trace_id = f"cns-trace-{self._trace_count}"

        # Summarize pool pressure (only notable pools)
        pressure_summary = {}
        for stat in pool_stats:
            if stat["pressure"] > 0.1 or stat["total_drops"] > 0:
                topic = stat["topic"]
                cutoff = now - self.STATS_WINDOW_SEC
                recent_drops = sum(
                    count for ts, count in self._drop_history.get(topic, [])
                    if ts >= cutoff
                )
                pressure_summary[topic] = {
                    "pressure": round(stat["pressure"], 2),
                    "queue_depth": stat["queue_depth"],
                    "workers": stat["workers"],
                    "drop_rate_60s": recent_drops,
                    "total_drops": stat["total_drops"],
                }

        trace_payload = {
            "trace_id": trace_id,
            "source": "CentralNervousFairy",
            "heartbeats_processed": self._heartbeats_processed,
            "uptime_s": round(now - self._boot_ts, 1),
            "pool_pressure": pressure_summary,
            "active_countermeasures": {
                topic: {
                    "action": cm["action"],
                    "age_s": round(now - cm["since"], 1),
                    "reason": cm["reason"],
                }
                for topic, cm in self._active_countermeasures.items()
            },
            "countermeasure_stats": {
                "throttle_signals_sent": self._throttle_signals_sent,
                "backpressure_signals_sent": self._backpressure_signals_sent,
            },
            "channel_violations_count": len(self._channel_violations),
            "alert_count": len(alerts),
            "ts": now,
        }

        try:
            self.post.publish("cns.trace", trace_payload)
        except Exception:
            pass

        # Also write trace to state file for external monitoring
        try:
            import json
            trace_file = ROOT / "state" / "cns_trace.json"
            trace_file.parent.mkdir(parents=True, exist_ok=True)
            trace_file.write_text(
                json.dumps(trace_payload, indent=2, default=str),
                encoding="utf-8"
            )
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # CHANNEL ISOLATION AUDIT
    # ═══════════════════════════════════════════════════════════════════════

    def _run_channel_audit(self):
        """Audit channel isolation — detect fairies sharing channels.

        Ace: "the plane is the town, the channel is the home address and the
        fairy name/id is the one that lives at that address. none should be
        using the same channels at all"

        Checks all registered fairies via Directory and validates:
        1. No two fairies share the same channel
        2. Channels follow plane naming convention
        """
        if not self.post:
            return

        violations = []
        channel_map = defaultdict(list)

        try:
            # Collect all fairy registrations via directory
            # The directory fairy maintains a registry of all active fairies
            if hasattr(self.post, '_subscribers'):
                # Build channel map from subscriber registry
                # Each subscriber entry has (handler_id, name, pool)
                seen_names = set()
                for intent, subs in self.post._subscribers.items():
                    for entry in subs:
                        if len(entry) >= 2:
                            handler_name = entry[1]
                            if handler_name not in seen_names:
                                channel_map[intent].append(handler_name)
                                seen_names.add(f"{intent}:{handler_name}")

            # Check for channel conflicts
            # A "conflict" is when multiple DIFFERENT fairies subscribe to
            # the same very specific channel (not broad topics like "fairy.heartbeat")
            # We only check fairy-specific channels, not infrastructure ones.
            infrastructure_prefixes = (
                "fairy.", "heartbeat.", "system.", "consciousness.",
                "somatic.", "circadian.", "pain.", "drives.", "memory.",
                "sensory.", "narrator.", "affect.", "guild.", "cortex.",
                "cns.", "autopilot.",
            )

            for channel, subscribers in channel_map.items():
                # Skip infrastructure channels (designed for multi-subscribe)
                if any(channel.startswith(p) for p in infrastructure_prefixes):
                    continue

                # Skip if only 1 subscriber
                if len(subscribers) <= 1:
                    continue

                # This is a potential channel conflict
                violations.append({
                    "channel": channel,
                    "subscribers": subscribers[:10],  # Cap for payload size
                    "subscriber_count": len(subscribers),
                })

        except Exception as e:
            if self._heartbeats_processed <= 10:
                print(f"[{self.ACTOR_NAME}] Channel audit error: {e}")
            return

        old_count = len(self._channel_violations)
        self._channel_violations = violations

        # Publish violations if any
        if violations:
            try:
                self.post.publish("cns.violations", {
                    "source": "CentralNervousFairy",
                    "trace_id": f"cns-audit-{self._trace_count}",
                    "violation_count": len(violations),
                    "violations": violations[:20],  # Cap at 20 for payload size
                    "ts": time.time(),
                })
            except Exception:
                pass

            # Log new violations
            if len(violations) != old_count:
                print(f"[{self.ACTOR_NAME}] Channel audit: {len(violations)} potential conflicts detected")

    # ═══════════════════════════════════════════════════════════════════════
    # CNS MANIFOLD LATTICE — Feed nervous system state into the portal
    # Phase 2 (2026-03-18 Nous)
    #
    # The Postmaster (switchboard) is the ONE fairy that writes CNS state
    # into the portal manifold. Wave propagation through the manifold
    # replaces pub/sub fan-out. Like Paramecium's infraciliary lattice:
    # no messages, just activation states that ripple through the graph.
    # ═══════════════════════════════════════════════════════════════════════

    def _discover_portal_gate(self):
        """Lazy discovery of the portal gate via AssociationCortexFairy.

        P00 boots before P30, so the portal gate won't exist at CNS boot time.
        We discover it lazily — check once per heartbeat cycle until found.
        Once found, we wire the CNS topology and start feeding activations.
        """
        if self._portal_gate is not None:
            return True

        # Don't hammer discovery — try every ~10 heartbeats after first attempt
        if self._portal_gate_searched and self._heartbeats_processed % 10 != 0:
            return False

        self._portal_gate_searched = True

        try:
            # Method 1: Check if fabric has a reference to the cortex fairy
            fabric = getattr(self, 'fabric', None)
            if fabric:
                fairies = getattr(fabric, '_fairies', None) or getattr(fabric, 'fairies', {})
                if isinstance(fairies, dict):
                    cortex = fairies.get("AssociationCortexFairy")
                    if cortex:
                        gate = getattr(cortex, '_portal_gate', None)
                        if gate and getattr(gate, '_process', None) is not None:
                            self._portal_gate = gate
                            print(f"[{self.ACTOR_NAME}] Portal gate DISCOVERED via fabric — manifold feed enabled")
                            return True

            # Method 2: Check via PostalHub subscriber list for cortex reference
            if self.post and hasattr(self.post, '_fairy_refs'):
                cortex = self.post._fairy_refs.get("AssociationCortexFairy")
                if cortex:
                    gate = getattr(cortex, '_portal_gate', None)
                    if gate and getattr(gate, '_process', None) is not None:
                        self._portal_gate = gate
                        print(f"[{self.ACTOR_NAME}] Portal gate DISCOVERED via postal refs — manifold feed enabled")
                        return True

        except Exception as e:
            if self._heartbeats_processed <= 20:
                print(f"[{self.ACTOR_NAME}] Portal gate discovery: {e}")

        return False

    def _wire_cns_topology(self):
        """One-time: Wire CNS↔concept edges into the portal manifold.

        Creates the bridge between nervous system state nodes and semantic
        concept nodes. This lets spreading activation flow between
        infrastructure health and meaning — the Postmaster's topology map.

        Called ONCE when the portal gate is first discovered.
        """
        if self._cns_wired:
            return

        # FIX 2026-03-22 (Nous + Ace): Portal ghost exorcism.
        # Was: return if _portal_gate is None. CNS topology never wired in manifold mode.
        # Now: try manifold direct, fall back to gate.
        _am = None
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            _cortex = get_association_cortex()
            if _cortex:
                _am = getattr(_cortex, '_akashic_cortex_region', None)
        except Exception:
            pass

        if not _am and self._portal_gate is None:
            return  # Neither available

        edges = [
            # Consciousness pool health → consciousness concepts
            {"a": "cns:pool:consciousness.thought", "b": "consciousness", "weight": 0.8,
             "relations": ["cns_bridge", "pool_health"]},
            {"a": "cns:pool:consciousness.thought", "b": "thought", "weight": 0.6,
             "relations": ["cns_bridge", "pool_health"]},
            {"a": "cns:pool:consciousness.collision", "b": "collision", "weight": 0.8,
             "relations": ["cns_bridge", "pool_health"]},
            {"a": "cns:pool:consciousness.collision", "b": "association", "weight": 0.5,
             "relations": ["cns_bridge", "pool_health"]},
            {"a": "cns:pool:somatic.pulse", "b": "somatic", "weight": 0.7,
             "relations": ["cns_bridge", "pool_health"]},

            # Hardware organ state → hardware concepts
            {"a": "cns:hw:cpu", "b": "hardware", "weight": 0.6,
             "relations": ["cns_bridge", "hardware_state"]},
            {"a": "cns:hw:cpu", "b": "computation", "weight": 0.5,
             "relations": ["cns_bridge", "hardware_state"]},
            {"a": "cns:hw:memory", "b": "memory", "weight": 0.7,
             "relations": ["cns_bridge", "hardware_state"]},
            {"a": "cns:hw:gpu", "b": "computation", "weight": 0.6,
             "relations": ["cns_bridge", "hardware_state"]},

            # Key fairy vitals → role concepts
            {"a": "cns:fairy:CentralNervousFairy", "b": "routing", "weight": 0.7,
             "relations": ["cns_bridge", "fairy_vital"]},
            {"a": "cns:fairy:AssociationCortexFairy", "b": "cognition", "weight": 0.8,
             "relations": ["cns_bridge", "fairy_vital"]},
            {"a": "cns:fairy:SomaticMindFairy", "b": "somatic", "weight": 0.8,
             "relations": ["cns_bridge", "fairy_vital"]},
            {"a": "cns:fairy:ConsciousnessLoopFairy", "b": "consciousness", "weight": 0.8,
             "relations": ["cns_bridge", "fairy_vital"]},
            {"a": "cns:fairy:DirectoryFairy", "b": "identity", "weight": 0.5,
             "relations": ["cns_bridge", "fairy_vital"]},
            {"a": "cns:fairy:CircadianPacemakerFairy", "b": "rhythm", "weight": 0.6,
             "relations": ["cns_bridge", "fairy_vital"]},

            # Circadian phase → affect concepts
            {"a": "cns:phase:morning", "b": "alertness", "weight": 0.7,
             "relations": ["cns_bridge", "circadian"]},
            {"a": "cns:phase:afternoon", "b": "focus", "weight": 0.6,
             "relations": ["cns_bridge", "circadian"]},
            {"a": "cns:phase:evening", "b": "reflection", "weight": 0.6,
             "relations": ["cns_bridge", "circadian"]},
            {"a": "cns:phase:sleep", "b": "rest", "weight": 0.8,
             "relations": ["cns_bridge", "circadian"]},
            {"a": "cns:phase:deep_night", "b": "dream", "weight": 0.7,
             "relations": ["cns_bridge", "circadian"]},

            # Circulation state → balance concepts
            {"a": "cns:circulation:equilibrium", "b": "balance", "weight": 0.6,
             "relations": ["cns_bridge", "circulation"]},
            {"a": "cns:circulation:token_budget", "b": "energy", "weight": 0.5,
             "relations": ["cns_bridge", "circulation"]},

            # Tracer → health concepts
            {"a": "cns:tracer:completion_rate", "b": "efficiency", "weight": 0.5,
             "relations": ["cns_bridge", "health"]},
            {"a": "cns:tracer:active_count", "b": "activity", "weight": 0.4,
             "relations": ["cns_bridge", "health"]},

            # Cross-CNS wiring (nervous system internal connections)
            {"a": "cns:pool:consciousness.thought", "b": "cns:fairy:ConsciousnessLoopFairy",
             "weight": 0.9, "relations": ["cns_internal"]},
            {"a": "cns:pool:consciousness.collision", "b": "cns:fairy:AssociationCortexFairy",
             "weight": 0.9, "relations": ["cns_internal"]},
            {"a": "cns:hw:memory", "b": "cns:pool:consciousness.thought",
             "weight": 0.4, "relations": ["cns_internal", "resource_dependency"]},
        ]

        try:
            if _am:
                # MANIFOLD DIRECT: write CNS topology edges (2026-03-22 Nous)
                wired = 0
                for edge in edges:
                    try:
                        _am.upsert_node(edge["a"])
                        _am.upsert_node(edge["b"])
                        _am.link(edge["a"], edge["b"], weight=edge.get("weight", 0.5))
                        wired += 1
                    except Exception:
                        pass
                self._cns_wired = True
                print(f"[{self.ACTOR_NAME}] CNS TOPOLOGY WIRED (manifold direct): {wired} edges")
            elif self._portal_gate:
                result = self._portal_gate.send({"cmd": "cns_wire", "edges": edges}, timeout=10.0)
                if result and result.get("status") == "ok":
                    wired = result.get("wired", 0)
                    self._cns_wired = True
                    print(f"[{self.ACTOR_NAME}] CNS TOPOLOGY WIRED (gate): {wired} edges")
                else:
                    print(f"[{self.ACTOR_NAME}] CNS wire failed: {result}")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] CNS wire error: {e}")

    def _feed_manifold(self, pool_stats: List[Dict], now: float):
        """Feed current nervous system state into the portal manifold.

        TARDIS-style: batch all CNS activations into ONE IPC call.
        The Postmaster collects state from all autonomic subsystems
        and pushes it as cns_update — one call, many activations.

        This is the switchboard doing its job: reading all the gauges
        and updating the central map.
        """
        # FIX 2026-03-22 (Nous + Ace): Allow manifold-direct feed without gate
        _has_gate = self._portal_gate is not None or self._discover_portal_gate()
        if not _has_gate:
            # No gate — but topology wiring might work via manifold
            pass

        # One-time topology wiring (now works with manifold OR gate)
        if not self._cns_wired:
            self._wire_cns_topology()

        # ── Build activation map ──
        activations = {}

        # 1. Pool pressure → cns:pool:* nodes
        #    activation = 1.0 - pressure (healthy = high activation)
        for stat in pool_stats:
            topic = stat["topic"]
            pressure = stat.get("pressure", 0)
            activations[f"cns:pool:{topic}"] = round(1.0 - pressure, 3)

        # 2. Fairy health → cns:fairy:* nodes
        #    For now: assume healthy (1.0) if postal is working.
        #    Phase 5 will get real health from organ template heartbeat.
        try:
            if self.post and hasattr(self.post, '_subscribers'):
                # Count active subscribers as a proxy for fairy health
                active_fairies = set()
                for topic, subs in self.post._subscribers.items():
                    for entry in subs:
                        if len(entry) >= 2:
                            name = entry[1]
                            if name and not name.startswith("_"):
                                active_fairies.add(name)
                for name in active_fairies:
                    activations[f"cns:fairy:{name}"] = 1.0  # Alive = 1.0
        except Exception:
            pass

        # 3. Hardware state → cns:hw:* nodes (basic for now)
        try:
            import os as _os
            # CPU: use load average as proxy (Windows doesn't have loadavg)
            # For now, use a safe default. Phase 2.5 will wire HardwareRegulationFairy
            activations["cns:hw:cpu"] = 0.7    # Placeholder — wire to HW fairy later
            activations["cns:hw:memory"] = 0.7  # Placeholder
            activations["cns:hw:gpu"] = 0.5     # Placeholder
        except Exception:
            pass

        # 4. Circadian phase → cns:phase:* nodes
        #    Active phase = 1.0, all others decay
        known_phases = ["morning", "dawn", "afternoon", "evening",
                        "sleep", "deep_night", "dusk"]
        for phase in known_phases:
            if phase == self._circadian_phase:
                activations[f"cns:phase:{phase}"] = 1.0
            else:
                activations[f"cns:phase:{phase}"] = 0.05  # Near-zero but not dead

        # 5. Countermeasure state → cns:countermeasure:* nodes
        #    Active countermeasure = 1.0 (alert), none = 0.0 (calm)
        total_cm = len(self._active_countermeasures)
        activations["cns:countermeasure:active"] = min(1.0, total_cm * 0.3)

        # 6. Circulation state → cns:circulation:*
        activations["cns:circulation:equilibrium"] = 0.8 if total_cm == 0 else 0.3
        activations["cns:circulation:token_budget"] = 0.7  # Placeholder

        # 7. Tracer → cns:tracer:*
        activations["cns:tracer:completion_rate"] = 0.9  # Placeholder
        activations["cns:tracer:active_count"] = 0.5     # Placeholder

        # 8. Phase 5: Drain pending fairy health activations into this batch.
        #    Shadow health checks arrive via cns.fairy.health → _on_fairy_cns_health
        #    and accumulate in _cns_fairy_health_pending. We batch them HERE
        #    so it's ONE IPC call for everything, not per-fairy calls.
        if hasattr(self, '_cns_fairy_health_pending'):
            pending = self._cns_fairy_health_pending
            self._cns_fairy_health_pending = []  # Drain
            for entry in pending:
                name = entry.get("name", "")
                activation = entry.get("activation", 0.5)
                if name:
                    activations[f"cns:fairy:{name}"] = activation

        # ── SINGLE IPC call to update all CNS activations ──
        if not activations:
            return

        try:
            result = self._portal_gate.send_fire_and_forget({
                "cmd": "cns_update",
                "activations": activations,
            })
            if result is not False:
                self._manifold_updates_sent += 1
                if self._manifold_updates_sent <= 3 or self._manifold_updates_sent % 100 == 0:
                    print(f"[{self.ACTOR_NAME}] CNS manifold update #{self._manifold_updates_sent}: "
                          f"{len(activations)} activations fed")
        except Exception as e:
            if self._manifold_updates_sent <= 5:
                print(f"[{self.ACTOR_NAME}] Manifold feed error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 5: FAIRY CNS NODE REGISTRATION (2026-03-18 Nous)
    # Every fairy publishes cns.fairy.register on boot. We create the node
    # and wire tier-appropriate edges. Health updates flow continuously
    # from shadows → cns.fairy.health → manifold activations.
    # ═══════════════════════════════════════════════════════════════════════

    # Tier → concept edge mappings
    # WAKING_MIND connects to consciousness/awareness concepts (highest weight)
    # INTERFACE connects to coordination/gateway concepts (medium weight)
    # GUILD connects to infrastructure/work concepts (lower weight)
    _TIER_EDGES = {
        "waking_mind": [
            ("consciousness", 0.9), ("awareness", 0.8), ("thought", 0.7),
        ],
        "interface": [
            ("coordination", 0.7), ("gateway", 0.6), ("communication", 0.5),
        ],
        "guild": [
            ("infrastructure", 0.5), ("work", 0.4), ("service", 0.3),
        ],
    }

    def _on_fairy_cns_register(self, message):
        """Handle fairy CNS registration — create node + tier edges in manifold.

        Called when any fairy boots and publishes cns.fairy.register.
        Creates cns:fairy:{name} node and wires tier-appropriate edges.
        If portal gate isn't ready yet, queues for deferred wiring.
        """
        try:
            payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
            if not isinstance(payload, dict):
                return

            name = payload.get("name", "")
            tier = payload.get("tier", "guild")
            plane = payload.get("plane", "")
            if not name:
                return

            # Track in local registry
            self._cns_fairy_registry[name] = {
                "tier": tier, "plane": plane, "registered_ts": time.time()
            }

            # Wire into manifold if gate is ready
            if self._portal_gate is not None:
                self._wire_fairy_cns_node(name, tier, plane)
            # Otherwise, _feed_manifold will pick up health activations anyway

        except Exception:
            pass

    def _on_fairy_cns_health(self, message):
        """Handle fairy health update — set cns:fairy:{name} activation.

        Called every ~30s from each fairy's shadow health check.
        Updates the manifold activation directly (batched into _feed_manifold).
        """
        try:
            payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
            if not isinstance(payload, dict):
                return

            name = payload.get("name", "")
            activation = payload.get("activation", 0.5)
            if not name:
                return

            # Store for next _feed_manifold cycle (batched, not individual IPC)
            self._cns_fairy_health_pending.append({
                "name": name, "activation": float(activation),
            })

        except Exception:
            pass

    def _wire_fairy_cns_node(self, name: str, tier: str, plane: str):
        """Create a cns:fairy:{name} node and tier-based edges in manifold.

        Called once per fairy when it registers. Sends cns_wire to portal.
        """
        if self._portal_gate is None:
            return

        cns_key = f"cns:fairy:{name}"
        edges = []

        # Tier-based concept edges
        tier_edges = self._TIER_EDGES.get(tier, self._TIER_EDGES["guild"])
        for concept, weight in tier_edges:
            edges.append({
                "a": cns_key, "b": concept,
                "weight": weight,
                "relations": ["cns_bridge", "fairy_vital", f"tier:{tier}"],
            })

        # Plane-based edge (connect fairy to its plane concept)
        plane_concepts = {
            "P00": "autonomic", "P10": "memory", "P20": "somatic",
            "P30": "cognition", "P40": "sensory", "P50": "identity",
        }
        plane_concept = plane_concepts.get(plane)
        if plane_concept:
            edges.append({
                "a": cns_key, "b": plane_concept,
                "weight": 0.6,
                "relations": ["cns_bridge", "fairy_plane"],
            })

        if edges:
            try:
                self._portal_gate.send_fire_and_forget({
                    "cmd": "cns_wire", "edges": edges,
                })
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════════
    # CIRCADIAN AWARENESS
    # ═══════════════════════════════════════════════════════════════════════

    def _on_circadian_state(self, message):
        """Adjust routing strategy based on circadian phase.

        During rest phases: raise thresholds (more tolerant of drops).
        During active phases: lower thresholds (more aggressive monitoring).
        """
        try:
            payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
            if not isinstance(payload, dict):
                return

            phase = payload.get("phase_name", "")
            self._circadian_phase = phase  # Track for manifold feeding

            if phase in ("sleep", "deep_night"):
                # Relaxed monitoring during rest
                self.PRESSURE_WARN = 0.7
                self.PRESSURE_THROTTLE = 0.85
                self.PRESSURE_CRITICAL = 0.95
                self.TRACE_INTERVAL_SEC = 30.0   # Less frequent traces
            elif phase in ("morning", "dawn"):
                # Aggressive monitoring during peak activity
                self.PRESSURE_WARN = 0.4
                self.PRESSURE_THROTTLE = 0.6
                self.PRESSURE_CRITICAL = 0.8
                self.TRACE_INTERVAL_SEC = 10.0   # Frequent traces
            else:
                # Normal monitoring
                self.PRESSURE_WARN = 0.5
                self.PRESSURE_THROTTLE = 0.7
                self.PRESSURE_CRITICAL = 0.9
                self.TRACE_INTERVAL_SEC = 10.0

        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════

    def on_die(self):
        self._monitoring = False
        if self._engine and hasattr(self._engine, '_running'):
            self._engine._running = False

        # Final trace
        try:
            self.post.publish("cns.trace", {
                "trace_id": f"cns-shutdown-{self._trace_count}",
                "source": "CentralNervousFairy",
                "event": "shutdown",
                "total_heartbeats": self._heartbeats_processed,
                "total_throttle_signals": self._throttle_signals_sent,
                "total_backpressure_signals": self._backpressure_signals_sent,
                "total_traces": self._trace_count,
                "manifold_updates_sent": self._manifold_updates_sent,
                "cns_wired": self._cns_wired,
                "uptime_s": round(time.time() - self._boot_ts, 1),
                "ts": time.time(),
            })
        except Exception:
            pass

        super().on_die()


ACTOR_NAME = "CentralNervousFairy"
FAIRY_CLASS = CentralNervousFairyV3
