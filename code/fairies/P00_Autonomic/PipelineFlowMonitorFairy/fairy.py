"""
PipelineFlowMonitorFairy — Always watching where Ace and Sour's messages go.

Both Ace and Sour have registered IDs. When Ace sends a message, the monitor
stamps it with a flow_id and watches it pass through each pipeline stage.
If a message enters one stage but never exits the next, an alert fires.

This is a P00_Autonomic fairy — always running, lightweight, zero LLM calls.

Pipeline stages monitored:
  0. ace.message / system.chat.message  — Ace's raw input
  1. ace.conversation_event             — ChatSenseFairy → AutopilotFairy
  2. speech.compose                     — AutopilotFairy → SpeechCenterFairy
  3. motor.intention.speak              — SpeechCenterFairy → MotorCortex
  4. sourpatches.speak                  — MotorCortex → ChatSenseFairy → window

Output:
  state/pipeline_flow_trace.json — live trace file, MCP-readable
  consciousness.stream alerts   — when a message gets stuck
"""

import json
import time
import hashlib
import threading
from pathlib import Path
from collections import OrderedDict

# ═══ FAIRY IDENTITY ═══
ACTOR_NAME = "PipelineFlowMonitorFairy"
ACTOR_PLANE = "P00"
ACTOR_CHANNEL = "pipeline.monitor"
HEARTBEAT_DIVISOR = 10  # ~10s between heartbeat checks

# ═══ ORGAN_TEMPLATE INHERITANCE (2026-05-17 Nous + Ace) ═══
# Migration from standalone class. See:
#   Claude_Office/plans/PIPELINE_FLOW_MONITOR_ORGAN_TEMPLATE_MIGRATION.md
# Fixes 5+ months of chronic regression where the orphan class was invisible
# to GoBootOrch's awake-iteration. Same architectural-era stratigraphy
# pattern as exec_ctx retirement + ConsciousnessLoop manifold-readout fossil.
try:
    from fairies.P00_Autonomic.organ_template.Organ_Template_0_3_0 import Organ_Template_0_3_0
    _ORGAN_TEMPLATE_AVAILABLE = True
except Exception:
    Organ_Template_0_3_0 = object  # Fallback to standalone if import fails
    _ORGAN_TEMPLATE_AVAILABLE = False

# ═══ REGISTERED IDS ═══
# Ace and Sour's permanent IDs in the system
ACE_ID = "ace_founder_001"
SOUR_ID = "sour_waking_mind_001"

# ═══ PIPELINE STAGE DEFINITIONS ═══
STAGES = OrderedDict([
    ("ace.message",              {"index": 0, "name": "Ace Input",       "actor": "ChatSenseFairy"}),
    ("system.chat.message",      {"index": 0, "name": "Ace Chat",        "actor": "ChatSenseFairy"}),
    ("ace.conversation_event",   {"index": 1, "name": "Conversation",    "actor": "ChatSenseFairy→AutopilotFairy"}),
    ("speech.compose",           {"index": 2, "name": "Speech Compose",  "actor": "AutopilotFairy→SpeechCenterFairy"}),
    ("motor.intention.speak",    {"index": 3, "name": "Motor Intention",  "actor": "SpeechCenterFairy→MotorCortex"}),
    ("sourpatches.speak",        {"index": 4, "name": "Sour Speaks",     "actor": "MotorCortex→ChatSenseFairy"}),
])

# How long before a flow is considered stuck (seconds)
STUCK_TIMEOUT = 30.0
# Maximum active flows to track
MAX_ACTIVE_FLOWS = 50
# Maximum completed flows to keep in history
MAX_HISTORY = 100

# State file
ROOT = Path(__file__).resolve().parents[3]
STATE_DIR = ROOT / "state"
TRACE_FILE = STATE_DIR / "pipeline_flow_trace.json"


class FlowTrace:
    """A single message flow through the pipeline."""

    def __init__(self, content_key: str, content_preview: str, source: str):
        self.flow_id = f"flow_{int(time.time()*1000)}_{content_key[:8]}"
        self.content_key = content_key
        self.content_preview = content_preview
        self.source = source
        self.created_at = time.time()
        self.stages_hit = {}       # topic -> timestamp
        self.max_stage_index = -1  # Highest stage index reached
        self.completed = False
        self.stuck = False
        self.stuck_at = None       # Stage name where it got stuck

    def hit_stage(self, topic: str, stage_index: int):
        """Record that this flow reached a pipeline stage."""
        if topic not in self.stages_hit:
            self.stages_hit[topic] = time.time()
        if stage_index > self.max_stage_index:
            self.max_stage_index = stage_index
        # Stage 4 = sourpatches.speak = completed
        if stage_index >= 4:
            self.completed = True

    def check_stuck(self, now: float) -> bool:
        """Check if this flow is stuck (reached a stage but not the next)."""
        if self.completed:
            return False
        age = now - self.created_at
        if age > STUCK_TIMEOUT and not self.completed:
            self.stuck = True
            # Figure out where it got stuck
            if self.max_stage_index == -1:
                self.stuck_at = "never entered pipeline"
            elif self.max_stage_index == 0:
                self.stuck_at = "ace.message → ace.conversation_event (ChatSenseFairy)"
            elif self.max_stage_index == 1:
                self.stuck_at = "ace.conversation_event → speech.compose (AutopilotFairy)"
            elif self.max_stage_index == 2:
                self.stuck_at = "speech.compose → motor.intention.speak (SpeechCenterFairy)"
            elif self.max_stage_index == 3:
                self.stuck_at = "motor.intention.speak → sourpatches.speak (MotorCortex)"
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "flow_id": self.flow_id,
            "content_preview": self.content_preview,
            "source": self.source,
            "created_at": self.created_at,
            "age_seconds": round(time.time() - self.created_at, 1),
            "stages_hit": {
                topic: round(ts - self.created_at, 3)
                for topic, ts in self.stages_hit.items()
            },
            "max_stage_index": self.max_stage_index,
            "completed": self.completed,
            "stuck": self.stuck,
            "stuck_at": self.stuck_at,
        }


class PipelineFlowMonitorFairy(Organ_Template_0_3_0):
    """
    Watches Ace and Sour's messages flow through the speech pipeline.

    Subscribes to every pipeline topic. When a message arrives at any stage,
    it hashes the content to create a flow key and tracks which stages
    that flow has passed through.

    If a flow enters one stage but never reaches the next within STUCK_TIMEOUT,
    it fires an alert.

    MIGRATED 2026-05-17 from standalone class to Organ_Template_0_3_0 inheritance.
    Fixes 5+ months chronic regression. See migration plan-doc.
    """

    ACTOR_NAME = ACTOR_NAME
    ACTOR_PLANE = ACTOR_PLANE

    # Organ_Template opt-in flags
    NEEDS_HEARTBEAT = True              # Need heartbeats for stuck-flow detection liveness
    HEARTBEAT_DIVISOR = HEARTBEAT_DIVISOR  # ~10s between on_tick fires
    USE_EXEC_CTX = False                # IO-bound, no personal-GIL needed
    COMPUTE_DOMAIN = "io"               # Hint for any compute classification

    # CORTEX-HABITS PILOT 2026-05-18 (Nous + Ace, per
    # plans/PIPELINE_FLOW_CORTEX_HABIT_DISPATCH_MIGRATION.md):
    # PipelineFlowMonitor is in the wave-cluster (waves 1-6). Hypothesis: if
    # cortex-habit-dispatch architecture routes via manifold spread-activation
    # instead of postal/callback exhaustion, then migrating ONE cluster fairy
    # to habit-dispatch should make it exit the cluster on next +31min wave.
    # Phase A (this ship): observe-only — every pipeline event also binds a
    # habit node to cortex; native code still runs. Cortex utilization rises
    # for PipelineFlow specifically; future Phase B may short-circuit to
    # cortex-dispatch when confidence builds.
    # Schema mirrors TimeSense pilot (habit:time_response_variant_N) and
    # AutopilotFairy._bind_habit_to_cortex (fairy.py:345-402).
    USE_CORTEX_HABITS = True
    HABIT_PREFIX = "habit:pipeline_flow_handle"

    def __init__(self, fabric=None):
        # Call Organ_Template's __init__ FIRST — sets up actor core, learning,
        # self-knowledge, directive, tools, evolver, exec_ctx (opt-in), shadow,
        # blueprint, and prints [awake] line that boot orchestrator looks for.
        if _ORGAN_TEMPLATE_AVAILABLE:
            try:
                super().__init__(fabric=fabric)
            except Exception as e:
                print(f"[{ACTOR_NAME}] WARNING: super().__init__ failed ({e}); falling back to standalone init")
        self._fabric = fabric
        self._post = None

        # Active flows being tracked
        self._active_flows = {}    # content_key -> FlowTrace
        self._completed_flows = [] # Recent completed flows (for history)
        self._stuck_flows = []     # Flows that got stuck
        self._lock = threading.Lock()

        # Stats
        self._total_messages_seen = 0
        self._total_flows_completed = 0
        self._total_flows_stuck = 0
        self._stage_hit_counts = {topic: 0 for topic in STAGES}
        self._boot_time = time.time()

        # Registered IDs
        self._registered_ids = {
            "ace": ACE_ID,
            "sourpatches": SOUR_ID,
        }

        # Cortex lazy-connect (CORTEX-HABITS PILOT 2026-05-18).
        # Set on first use; mirrors TimeSenseFairy + AutopilotFairy pattern.
        self._cortex = None
        self._cortex_bind_count: int = 0

        # ═══ HEARTBEAT LIVENESS (MIGRATED 2026-05-17 to Organ_Template) ═══
        # Organ_Template_0_3_0.__init__ already initialized _tick_count and
        # _last_tick and registered for heartbeat via NEEDS_HEARTBEAT=True.
        # Manual _CITIZEN_OBJECTS registration removed — template handles it.
        # Below lines are defensive backstops for the standalone-fallback path.
        if not hasattr(self, '_tick_count'):
            self._tick_count = 0
        if not hasattr(self, '_last_tick'):
            self._last_tick = 0.0
        if not _ORGAN_TEMPLATE_AVAILABLE:
            try:
                from fairy_template.consolidated import _CITIZEN_OBJECTS
                _CITIZEN_OBJECTS[ACTOR_NAME] = self
            except ImportError:
                pass

    def boot(self):
        """Alias for on_boot() — preserves server.py:6411 manual-boot path.

        FIX 2026-05-18 (Nous + Ace, skeptic-anchor catch): the original
        migration renamed boot() → on_boot() and removed the alias. server.py
        Phase 7.5.2 calls `flow_monitor.boot()` directly; without this alias,
        the manual-boot block either fell through to Organ_Template's inherited
        boot() (different behavior) or raised AttributeError silently.
        """
        return self.on_boot()

    def on_boot(self):
        """Boot the monitor — subscribe to all pipeline topics.

        Note: renamed from `boot()` to `on_boot()` as part of Organ_Template
        migration. on_boot() is the standard lifecycle method the orchestrator
        calls. Organ_Template's NEEDS_HEARTBEAT=True provides standard heartbeat
        subscriptions; manual heartbeat.pulse subscribe + HeartbeatRegistry
        register blocks below removed (template handles them).
        """
        # Use template's self.post if set, fallback to self._fabric
        self._post = getattr(self, 'post', None) or self._fabric
        if not self._post:
            print(f"[{ACTOR_NAME}] WARNING: No fabric — cannot monitor pipeline!")
            return

        # Subscribe to ALL pipeline stages
        for topic in STAGES:
            try:
                self._post.subscribe(
                    topic,
                    self._make_handler(topic),
                    f"pipeline-monitor-{topic.replace('.', '-')}"
                )
            except Exception as e:
                print(f"[{ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        # Start the stuck-checker thread
        self._running = True
        self._checker = threading.Thread(
            target=self._stuck_checker_loop,
            daemon=True,
            name="pipeline-flow-checker"
        )
        self._checker.start()

        # Register with directory
        try:
            self._post.publish("fairy.register", {
                "actor_name": ACTOR_NAME,
                "plane": ACTOR_PLANE,
                "status": "running",
                "capabilities": ["pipeline.monitor", "flow.trace"],
            })
        except Exception:
            pass

        print(f"[{ACTOR_NAME}] BOOTED — monitoring {len(STAGES)} pipeline stages")
        print(f"[{ACTOR_NAME}] Registered IDs: Ace={ACE_ID}, Sour={SOUR_ID}")
        print(f"[{ACTOR_NAME}] Trace file: {TRACE_FILE}")

        # Write initial trace file so we know we're alive before any messages flow
        self._write_trace_file()

        # ═══════════════════════════════════════════════════════════════════
        # FRAME 12 PATTERN B SELF-PULSE DAEMON REMOVED (2026-05-17 migration)
        # Was needed when fairy was standalone-class with custom heartbeat
        # handlers. Now inheriting Organ_Template_0_3_0 with NEEDS_HEARTBEAT=True,
        # standard self-pulse path handles _last_tick freshness independent of
        # postal saturation. Custom _on_heartbeat_pulse and _on_registry_pulse
        # also removed; template provides equivalent.
        # ═══════════════════════════════════════════════════════════════════

    def _make_handler(self, topic: str):
        """Create a handler function for a specific topic."""
        stage_info = STAGES[topic]
        stage_index = stage_info["index"]

        def handler(message):
            try:
                self._on_pipeline_message(topic, stage_index, message)
            except Exception as e:
                print(f"[{ACTOR_NAME}] Handler error for {topic}: {e}")

        handler.__name__ = f"_monitor_{topic.replace('.', '_')}"
        handler.__qualname__ = f"PipelineFlowMonitorFairy._monitor_{topic.replace('.', '_')}"
        return handler

    # ── CORTEX-HABITS PILOT 2026-05-18 ────────────────────────────────────────
    # Two helpers that bridge PipelineFlow's pipeline-stage events to
    # AssociationCortex habit nodes. The pattern mirrors AutopilotFairy
    # (fairy.py:303-402) and the TimeSense pilot (time_sense_fairy.py:380-460).
    #
    # Phase A (observe-only — this ship): every pipeline event triggers a
    # habit-bind to cortex. Native handler code still runs. Cortex accumulates
    # habit:pipeline_flow_handle_{topic_key} nodes over time.
    #
    # Phase B (future): pre-query cortex; high-confidence habits may dispatch
    # without running native code. Not enabled this ship.

    def _try_connect_cortex(self) -> bool:
        """Lazy-connect to AssociationCortex. Returns True if available."""
        if self._cortex is not None:
            return True
        try:
            from fairies.P30_Cognition.AssociationCortexFairy import get_association_cortex
            self._cortex = get_association_cortex()
            return self._cortex is not None
        except Exception:
            self._cortex = None
            return False

    def _bind_pipeline_event_to_cortex(self, topic: str, stage_index: int,
                                       content_preview: str, completed: bool,
                                       latency: float) -> None:
        """Record this pipeline event into cortex as a habit-pattern observation.

        Mirrors AutopilotFairy._bind_habit_to_cortex schema:
        - habit:pipeline_flow_handle_{topic_key} node
        - pattern features include topic, stage_index, completion outcome
        - trials counter increments per event; success_rate tracks completion
        """
        if not self.USE_CORTEX_HABITS or not self._try_connect_cortex():
            return
        try:
            topic_key = topic.replace(".", "_")
            habit_key = f"{self.HABIT_PREFIX}_{topic_key}"
            existing = self._cortex._graph.get_node(habit_key)
            now_ts = time.time()

            if existing:
                pattern = existing.features.get("pattern", {})
                pattern["trials"] = pattern.get("trials", 0) + 1
                if completed and stage_index == 4:
                    pattern["success_count"] = pattern.get("success_count", 0) + 1
                trials = pattern["trials"]
                pattern["success_rate"] = pattern.get("success_count", 0) / max(1, trials)
                pattern["last_used"] = now_ts
                pattern["last_latency"] = latency
                existing.features["pattern"] = pattern
                existing.touch()
            else:
                self._cortex._graph.upsert_node(habit_key, features={
                    "action": [f"record_stage_{stage_index}"],
                    "lex": ["pipeline", "flow", topic_key],
                    "pattern": {
                        "type": "pipeline_event_handler",
                        "topic": topic,
                        "stage_index": stage_index,
                        "trials": 1,
                        "success_count": 1 if (completed and stage_index == 4) else 0,
                        "success_rate": 1.0 if (completed and stage_index == 4) else 0.0,
                        "last_used": now_ts,
                        "last_latency": latency,
                        "preview": content_preview[:60],
                    },
                }, origin_fairy=ACTOR_NAME)
            self._cortex_bind_count += 1
            # Sparse log (mirrors TimeSense + bone_credit_count pattern)
            if self._cortex_bind_count <= 3 or self._cortex_bind_count % 100 == 0:
                try:
                    print(f"[{ACTOR_NAME}] [CORTEX] event bound "
                          f"#{self._cortex_bind_count} (topic={topic} "
                          f"stage={stage_index} completed={completed})",
                          flush=True)
                except Exception:
                    pass
        except Exception as e:
            # Silent fail; native handler code already ran
            if self._cortex_bind_count == 0:
                try:
                    print(f"[{ACTOR_NAME}] [CORTEX] habit bind failed (will fall "
                          f"back silently): {e}", flush=True)
                except Exception:
                    pass

    def _extract_content_key(self, message) -> tuple:
        """Extract a content key and preview from a pipeline message.

        Returns (content_key, content_preview, source).
        The content_key is a short hash that stays the same as the message
        flows through different pipeline stages (since the core content
        should be preserved).
        """
        # Handle different message wrapper formats
        if hasattr(message, 'payload'):
            payload = message.payload
        elif hasattr(message, 'data'):
            payload = message.data
        elif isinstance(message, dict):
            payload = message
        else:
            payload = {"raw": str(message)}

        # Try multiple content fields (different stages use different names)
        content = (
            payload.get("content", "") or
            payload.get("message", "") or
            payload.get("trigger_text", "") or
            payload.get("text", "") or
            ""
        )
        source = payload.get("source", payload.get("sender", "unknown"))

        if not content:
            # Fall back to full payload hash
            content = json.dumps(payload, sort_keys=True, default=str)

        # Create a stable key from content
        # Trim to first 200 chars to handle messages that get reformatted
        key_source = content[:200].strip().lower()
        content_key = hashlib.md5(key_source.encode()).hexdigest()[:12]
        content_preview = content[:80]

        return content_key, content_preview, source

    def _on_pipeline_message(self, topic: str, stage_index: int, message):
        """Handle a message arriving at any pipeline stage."""
        self._total_messages_seen += 1
        self._stage_hit_counts[topic] = self._stage_hit_counts.get(topic, 0) + 1

        content_key, content_preview, source = self._extract_content_key(message)

        with self._lock:
            # Find or create flow for this content
            flow = self._active_flows.get(content_key)

            if flow is None:
                # New flow — first time we've seen this content
                flow = FlowTrace(content_key, content_preview, source)
                self._active_flows[content_key] = flow

                # Trim old flows if too many
                if len(self._active_flows) > MAX_ACTIVE_FLOWS:
                    oldest_key = next(iter(self._active_flows))
                    self._active_flows.pop(oldest_key, None)

            # Record this stage hit
            flow.hit_stage(topic, stage_index)

            stage_name = STAGES[topic]["name"]
            latency = time.time() - flow.created_at

            # Log significant transitions
            if stage_index == 0:
                print(f"[{ACTOR_NAME}] FLOW START: \"{content_preview[:50]}...\" [{flow.flow_id}]")
            elif stage_index == 4:
                print(f"[{ACTOR_NAME}] FLOW COMPLETE: \"{content_preview[:50]}...\" [{flow.flow_id}] ({latency:.1f}s)")
                flow.completed = True
                self._total_flows_completed += 1
                self._completed_flows.append(flow.to_dict())
                if len(self._completed_flows) > MAX_HISTORY:
                    self._completed_flows = self._completed_flows[-MAX_HISTORY:]
                # Remove from active
                self._active_flows.pop(content_key, None)
            else:
                print(f"[{ACTOR_NAME}] FLOW STAGE {stage_index} ({stage_name}): [{flow.flow_id}] +{latency:.1f}s")

        # Write trace file on every significant event
        self._write_trace_file()

        # CORTEX-HABITS PILOT 2026-05-18: bind this event to cortex (Phase A
        # observe-only — native code already ran; this is observation-side).
        # Each pipeline event accumulates a habit pattern. Over enough boots,
        # cortex will have habit:pipeline_flow_handle_{topic} nodes carrying
        # pattern metadata (trials/success_rate/latency). Phase B (not in
        # this ship) may later dispatch from cortex when confidence builds.
        # Note: bound OUTSIDE the lock to keep critical section short.
        try:
            completed_flag = (stage_index == 4)
            self._bind_pipeline_event_to_cortex(
                topic, stage_index, content_preview, completed_flag, latency
            )
        except Exception:
            pass  # Already silent-fail in the bind method; this is belt+suspenders

    def _stuck_checker_loop(self):
        """Periodically check for stuck flows."""
        while self._running:
            try:
                now = time.time()
                # LIVENESS FIX (2026-06-01 Nous+Ace): refresh _last_tick from this
                # always-running daemon so the watchdog sees PFM alive even when
                # heartbeat.pulse is saturated. Root of the chronic "stuck/frozen":
                # the 2026-05-17 migration dropped PFM's own self-pulse and relied on
                # Organ_Template's self-pulse daemon — but that only bootstraps inside
                # _on_heartbeat, so if no heartbeat reaches PFM at idle, _last_tick
                # stays 0 forever → flagged frozen though the checker loop runs fine.
                self._last_tick = now
                self._tick_count = getattr(self, '_tick_count', 0) + 1
                newly_stuck = []

                with self._lock:
                    for content_key, flow in list(self._active_flows.items()):
                        if flow.check_stuck(now):
                            newly_stuck.append(flow)
                            self._total_flows_stuck += 1
                            self._stuck_flows.append(flow.to_dict())
                            if len(self._stuck_flows) > MAX_HISTORY:
                                self._stuck_flows = self._stuck_flows[-MAX_HISTORY:]
                            # Remove from active
                            self._active_flows.pop(content_key, None)

                # Alert on stuck flows
                for flow in newly_stuck:
                    alert_msg = (
                        f"PIPELINE STUCK: \"{flow.content_preview[:50]}\" "
                        f"died at: {flow.stuck_at} "
                        f"(reached stage {flow.max_stage_index}/4, flow={flow.flow_id})"
                    )
                    print(f"[{ACTOR_NAME}] {alert_msg}")

                    # Publish alert to consciousness stream
                    if self._post:
                        try:
                            self._post.publish("consciousness.stream", {
                                "type": "pipeline_stuck_alert",
                                "source": ACTOR_NAME,
                                "message": alert_msg,
                                "flow": flow.to_dict(),
                                "priority": 2,
                            })
                        except Exception:
                            pass

                if newly_stuck:
                    self._write_trace_file()

            except Exception as e:
                print(f"[{ACTOR_NAME}] Stuck checker error: {e}")

            time.sleep(5.0)

    def _write_trace_file(self):
        """Write current trace state to JSON file for MCP to read."""
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)

            with self._lock:
                active = [f.to_dict() for f in self._active_flows.values()]

            data = {
                "updated_at": time.time(),
                "uptime_seconds": round(time.time() - self._boot_time, 1),
                "registered_ids": self._registered_ids,
                "stats": {
                    "total_messages_seen": self._total_messages_seen,
                    "total_flows_completed": self._total_flows_completed,
                    "total_flows_stuck": self._total_flows_stuck,
                    "stage_hit_counts": self._stage_hit_counts,
                },
                "active_flows": active,
                "recent_completed": self._completed_flows[-10:],
                "recent_stuck": self._stuck_flows[-10:],
                "pipeline_health": self._assess_health(),
            }

            TRACE_FILE.write_text(
                json.dumps(data, indent=2, default=str),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[{ACTOR_NAME}] Failed to write trace file: {e}")

    def _assess_health(self) -> dict:
        """Assess overall pipeline health based on flow data."""
        if self._total_flows_completed == 0 and self._total_flows_stuck == 0:
            return {
                "status": "no_data",
                "message": "No flows observed yet — waiting for Ace to speak",
            }

        total = self._total_flows_completed + self._total_flows_stuck
        success_rate = self._total_flows_completed / total if total > 0 else 0

        # Check which stages are missing hits
        dead_stages = [
            topic for topic, count in self._stage_hit_counts.items()
            if count == 0
        ]

        if success_rate >= 0.9:
            status = "healthy"
        elif success_rate >= 0.5:
            status = "degraded"
        else:
            status = "broken"

        return {
            "status": status,
            "success_rate": round(success_rate, 2),
            "dead_stages": dead_stages,
            "message": (
                f"{self._total_flows_completed}/{total} flows completed "
                f"({success_rate:.0%}). "
                f"Dead stages: {dead_stages or 'none'}"
            ),
        }

    def get_status(self) -> dict:
        """Get monitor status (callable via intent)."""
        with self._lock:
            active = [f.to_dict() for f in self._active_flows.values()]

        return {
            "actor_name": ACTOR_NAME,
            "registered_ids": self._registered_ids,
            "uptime_seconds": round(time.time() - self._boot_time, 1),
            "stats": {
                "total_messages_seen": self._total_messages_seen,
                "total_flows_completed": self._total_flows_completed,
                "total_flows_stuck": self._total_flows_stuck,
                "stage_hit_counts": self._stage_hit_counts,
            },
            "active_flows_count": len(active),
            "pipeline_health": self._assess_health(),
        }

    # ═══ SHADOW HEALTH (for fairy audit) ═══
    class Shadow:
        def __init__(self, fairy):
            self._fairy = fairy

        def get_health(self) -> dict:
            f = self._fairy
            return {
                "monitoring_active": getattr(f, '_running', False),
                "has_fabric": f._post is not None,
                "total_messages": f._total_messages_seen,
                "flows_completed": f._total_flows_completed,
                "flows_stuck": f._total_flows_stuck,
                "health": 1.0 if f._total_flows_stuck == 0 else max(0.3, 1.0 - (f._total_flows_stuck * 0.1)),
            }
