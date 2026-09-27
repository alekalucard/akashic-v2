"""
Admin Task Queue - Background Administrative Jobs

The unconscious mind's administrative task scheduler.
These are the "housekeeping" jobs that keep the system healthy:
- Memory consolidation
- Health checks
- Resource cleanup
- Pattern analysis
- Capability gap detection (Cardinal Sprint 1)

Philosophy: A healthy unconscious is a BUSY unconscious. Idle hands
(processes) are the devil's workshop. The admin queue ensures
there's always useful work being done in the background.

Cardinal Evolution (2026-02-22): Sprint 1 wired real implementations
into 5 previously-stub tasks + added capability_gap_scan.
"""

from __future__ import annotations

import time
import random
import threading
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from enum import Enum


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 0  # Do immediately
    HIGH = 1      # Do soon
    NORMAL = 2    # Do when convenient
    LOW = 3       # Do when idle
    BACKGROUND = 4  # Only when nothing else to do


class TaskCategory(Enum):
    """Categories of admin tasks."""
    HEALTH = "health"           # System health checks
    MEMORY = "memory"           # Memory operations
    CLEANUP = "cleanup"         # Resource cleanup
    ANALYSIS = "analysis"       # Pattern analysis
    COMMUNICATION = "comm"      # Communication tasks
    MAINTENANCE = "maintenance" # General maintenance


@dataclass
class AdminTask:
    """An administrative task to be executed."""
    name: str
    category: TaskCategory
    priority: TaskPriority
    action: Callable[[], Dict[str, Any]]  # Function to execute
    description: str = ""

    # Scheduling
    interval_seconds: Optional[float] = None  # Recurring interval
    last_run: float = 0.0
    next_run: float = 0.0
    run_count: int = 0

    # State
    enabled: bool = True
    last_result: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None

    def is_due(self, now: float = None) -> bool:
        """Check if task is due to run."""
        if not self.enabled:
            return False
        now = now or time.time()

        if self.interval_seconds is None:
            # One-time task
            return self.run_count == 0

        return now >= self.next_run

    def run(self) -> Dict[str, Any]:
        """Execute the task."""
        now = time.time()
        self.last_run = now
        self.run_count += 1

        if self.interval_seconds:
            self.next_run = now + self.interval_seconds

        try:
            self.last_result = self.action()
            self.last_error = None
            return self.last_result
        except Exception as e:
            self.last_error = str(e)
            return {"ok": False, "error": str(e)}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "priority": self.priority.value,
            "description": self.description,
            "interval": self.interval_seconds,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
            "enabled": self.enabled,
            "last_error": self.last_error,
        }


class AdminTaskQueue:
    """
    Background Administrative Task Queue.

    Manages and executes administrative tasks:
    - Prioritizes by urgency and category
    - Respects task intervals (no hammering)
    - Tracks execution history
    - Provides status for monitoring
    """

    def __init__(self, max_tasks_per_tick: int = 3, systems: Dict[str, Any] = None):
        self._tasks: Dict[str, AdminTask] = {}
        self._execution_history: deque = deque(maxlen=100)
        self._max_per_tick = max_tasks_per_tick

        # System references for real wiring
        self._systems = systems or {}

        # Metrics
        self._total_runs = 0
        self._total_errors = 0

        # Thread safety
        self._lock = threading.Lock()

        # Initialize with default admin tasks
        self._register_default_tasks()

    def wire_systems(self, systems: Dict[str, Any]):
        """Wire system references after initialization."""
        self._systems.update(systems)

    def _register_default_tasks(self):
        """Register default administrative tasks."""

        # Health checks - every 30 seconds
        self.register(AdminTask(
            name="plane_health_scan",
            category=TaskCategory.HEALTH,
            priority=TaskPriority.NORMAL,
            action=self._action_plane_health_scan,
            description="Scan all planes for health issues",
            interval_seconds=30.0,
        ))

        self.register(AdminTask(
            name="fairy_heartbeat_check",
            category=TaskCategory.HEALTH,
            priority=TaskPriority.HIGH,
            action=self._action_fairy_heartbeat_check,
            description="Check for unresponsive fairies",
            interval_seconds=20.0,
        ))

        # Memory operations - every 60 seconds
        self.register(AdminTask(
            name="memory_consolidation_nudge",
            category=TaskCategory.MEMORY,
            priority=TaskPriority.NORMAL,
            action=self._action_memory_consolidation,
            description="Nudge memory consolidation process",
            interval_seconds=60.0,
        ))

        self.register(AdminTask(
            name="collision_chamber_analysis",
            category=TaskCategory.MEMORY,
            priority=TaskPriority.LOW,
            action=self._action_collision_analysis,
            description="Analyze collision chamber patterns",
            interval_seconds=45.0,
        ))

        # Cleanup - every 120 seconds
        self.register(AdminTask(
            name="stale_tracer_cleanup",
            category=TaskCategory.CLEANUP,
            priority=TaskPriority.LOW,
            action=self._action_tracer_cleanup,
            description="Clean up stale tracers",
            interval_seconds=120.0,
        ))

        self.register(AdminTask(
            name="dead_letter_scan",
            category=TaskCategory.CLEANUP,
            priority=TaskPriority.NORMAL,
            action=self._action_dead_letter_scan,
            description="Check for stuck messages",
            interval_seconds=90.0,
        ))

        # Analysis - every 180 seconds
        self.register(AdminTask(
            name="pattern_recognition",
            category=TaskCategory.ANALYSIS,
            priority=TaskPriority.BACKGROUND,
            action=self._action_pattern_recognition,
            description="Look for emergent patterns",
            interval_seconds=180.0,
        ))

        self.register(AdminTask(
            name="learning_edge_calibration",
            category=TaskCategory.ANALYSIS,
            priority=TaskPriority.LOW,
            action=self._action_learning_calibration,
            description="Calibrate cognition loop difficulty",
            interval_seconds=300.0,
        ))

        # Communication - every 60 seconds
        self.register(AdminTask(
            name="ace_presence_check",
            category=TaskCategory.COMMUNICATION,
            priority=TaskPriority.NORMAL,
            action=self._action_ace_presence_check,
            description="Check for Ace's presence",
            interval_seconds=60.0,
        ))

        # Cardinal - capability gap detection (Sprint 1)
        self.register(AdminTask(
            name="capability_gap_scan",
            category=TaskCategory.ANALYSIS,
            priority=TaskPriority.NORMAL,
            action=self._action_capability_gap_scan,
            description="Detect capability gaps from goal failures and slow execution",
            interval_seconds=300.0,
        ))

    # =========================================================================
    # TASK ACTIONS — Wired to live systems (Cardinal Sprint 1, 2026-02-22)
    # =========================================================================

    def _action_plane_health_scan(self) -> Dict[str, Any]:
        """Scan planes for health issues."""
        directory = self._systems.get("directory")
        issues = []
        planes_checked = []

        if directory and hasattr(directory, 'registry'):
            # Get fairies by plane
            for plane in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]:
                planes_checked.append(plane)
                fairies = [f for f in directory.registry.list_fairies()
                          if f.get("plane") == plane]
                # Check for failures
                for f in fairies:
                    if f.get("state") == "FAILED":
                        issues.append({"plane": plane, "fairy": f.get("name"), "issue": "failed"})

        return {
            "ok": True,
            "action": "plane_health_scan",
            "planes_checked": planes_checked or ["P00", "P10", "P30", "P40"],
            "issues": issues,
            "wired": directory is not None,
        }

    def _action_fairy_heartbeat_check(self) -> Dict[str, Any]:
        """Check for unresponsive fairies."""
        directory = self._systems.get("directory")
        unresponsive = []
        fairies_checked = 0

        if directory and hasattr(directory, 'registry'):
            now = time.time()
            for record in directory.registry.list_fairies():
                fairies_checked += 1
                last_seen = record.get("last_heartbeat", 0)
                if last_seen and (now - last_seen) > 60:  # 60 second timeout
                    unresponsive.append(record.get("name"))

        return {
            "ok": True,
            "action": "fairy_heartbeat_check",
            "fairies_checked": fairies_checked,
            "unresponsive": unresponsive,
            "wired": directory is not None,
        }

    def _action_memory_consolidation(self) -> Dict[str, Any]:
        """Nudge memory consolidation via WorkingMemoryHub.

        Checks for expired tracers, promotes mature reflective tracers
        to reasoning loop, and publishes a consolidation pulse.
        """
        wmh = self._systems.get("working_memory")
        postal = self._systems.get("postal")
        promoted = 0
        expired = 0
        active = 0

        if wmh:
            try:
                status = wmh.get_status() if hasattr(wmh, 'get_status') else {}
                active = status.get("reflective_count", 0) + status.get("reasoning_count", 0)

                # Get tracers and check for promotion candidates
                tracers = wmh.get_recent_tracers(20) if hasattr(wmh, 'get_recent_tracers') else []
                for t in tracers:
                    if hasattr(t, 'is_expired') and t.is_expired():
                        expired += 1
                    elif (hasattr(t, 'current_loop') and t.current_loop == "reflective"
                          and hasattr(t, 'remaining_ttl') and t.remaining_ttl() < 60
                          and hasattr(t, 'content_type') and t.content_type in ("reflection", "insight", "decision")):
                        # Mature reflective tracers → promote to reasoning
                        if hasattr(wmh, '_promote_to_reasoning'):
                            if wmh._promote_to_reasoning(t):
                                promoted += 1
            except Exception as e:
                return {"ok": False, "error": str(e), "action": "memory_consolidation_nudge"}

        # Publish consolidation pulse for other systems to respond
        if postal and (promoted > 0 or expired > 0):
            try:
                postal.publish("admin.memory_consolidated", {
                    "promoted": promoted,
                    "expired": expired,
                    "active": active,
                    "timestamp": time.time(),
                })
            except Exception:
                pass

        return {
            "ok": True,
            "action": "memory_consolidation_nudge",
            "active_tracers": active,
            "promoted_to_reasoning": promoted,
            "expired_found": expired,
            "wired": wmh is not None,
        }

    def _action_collision_analysis(self) -> Dict[str, Any]:
        """Analyze collision chamber."""
        chamber = self._systems.get("collision_chamber")
        collisions_analyzed = 0
        patterns_found = []

        if chamber:
            # Get collision stats
            stats = chamber.status() if hasattr(chamber, 'status') else {}
            collisions_analyzed = stats.get("total_collisions", 0)

            # Look for patterns in collision sources
            history = getattr(chamber, '_history', [])
            if history:
                sources = {}
                for c in list(history)[-20:]:  # Last 20 collisions
                    recall_src = c.get("recall", {}).get("source", "unknown")
                    sources[recall_src] = sources.get(recall_src, 0) + 1
                # Find dominant sources
                for src, count in sources.items():
                    if count >= 3:
                        patterns_found.append(f"frequent_recall:{src}")

        return {
            "ok": True,
            "action": "collision_analysis",
            "collisions_analyzed": collisions_analyzed,
            "patterns_found": patterns_found,
            "wired": chamber is not None,
        }

    def _action_tracer_cleanup(self) -> Dict[str, Any]:
        """Clean up stale tracers via TracerRegistry.

        Calls cleanup_expired() to remove completed/failed tracers past TTL,
        then reports registry health stats for monitoring.
        """
        tracer_registry = self._systems.get("tracer_registry")
        postal = self._systems.get("postal")
        cleaned = 0
        stats = {}

        if tracer_registry:
            try:
                # Remove expired tracers
                if hasattr(tracer_registry, 'cleanup_expired'):
                    cleaned = tracer_registry.cleanup_expired()

                # Get current registry health
                if hasattr(tracer_registry, 'get_stats'):
                    stats = tracer_registry.get_stats()
            except Exception as e:
                return {"ok": False, "error": str(e), "action": "tracer_cleanup"}

        # Publish cleanup event if meaningful work was done
        if postal and cleaned > 0:
            try:
                postal.publish("admin.tracers_cleaned", {
                    "cleaned": cleaned,
                    "remaining": stats.get("total_tracers", 0),
                    "by_status": stats.get("by_status", {}),
                    "timestamp": time.time(),
                })
            except Exception:
                pass

        return {
            "ok": True,
            "action": "tracer_cleanup",
            "tracers_cleaned": cleaned,
            "total_tracers": stats.get("total_tracers", 0),
            "fairies_tracked": stats.get("fairies_tracked", 0),
            "by_status": stats.get("by_status", {}),
            "wired": tracer_registry is not None,
        }

    def _action_dead_letter_scan(self) -> Dict[str, Any]:
        """Scan postal system for stuck messages and unhealthy topics.

        Uses TensorFabric/PostalHub metrics() and topic_stats() to detect:
        - Topics with zero subscribers (orphan topics — messages go nowhere)
        - Topics with unusually high pending counts (congestion)
        - Overall fabric health indicators
        """
        postal = self._systems.get("postal")
        fabric = self._systems.get("tensor_fabric")
        orphan_topics = []
        congested_topics = []
        fabric_metrics = {}

        # Try TensorFabric first (richer metrics), fall back to PostalHub
        source = fabric or postal

        if source:
            try:
                # Get overall metrics
                if hasattr(source, 'metrics'):
                    fabric_metrics = source.metrics()

                # Get per-topic stats to find orphans and congestion
                if hasattr(source, 'topic_stats'):
                    topic_list = source.topic_stats()
                    for ts in (topic_list or []):
                        topic_name = ts.get("topic", ts.get("name", "unknown"))
                        sub_count = ts.get("subscribers", ts.get("sub_count", 0))
                        pending = ts.get("pending", ts.get("queued", 0))

                        if sub_count == 0:
                            orphan_topics.append(topic_name)
                        if pending > 50:  # Threshold for congestion warning
                            congested_topics.append({
                                "topic": topic_name,
                                "pending": pending,
                                "subscribers": sub_count,
                            })
            except Exception as e:
                return {"ok": False, "error": str(e), "action": "dead_letter_scan"}

        # Publish if issues found
        if postal and (orphan_topics or congested_topics):
            try:
                postal.publish("admin.postal_issues", {
                    "orphan_topics": orphan_topics[:10],  # Cap at 10
                    "congested_topics": congested_topics[:5],
                    "timestamp": time.time(),
                })
            except Exception:
                pass

        return {
            "ok": True,
            "action": "dead_letter_scan",
            "orphan_topics": len(orphan_topics),
            "congested_topics": len(congested_topics),
            "orphan_samples": orphan_topics[:5],
            "congested_samples": congested_topics[:3],
            "mean_affect": fabric_metrics.get("mean_affect", 0.0),
            "wired": source is not None,
        }

    def _action_pattern_recognition(self) -> Dict[str, Any]:
        """Look for emergent patterns in the association cortex."""
        cortex = self._systems.get("cortex")
        patterns_detected = []

        if cortex and hasattr(cortex, '_binding_count'):
            binding_count = cortex._binding_count
            node_count = len(cortex._graph.nodes) if cortex._graph else 0

            # Simple pattern detection based on growth
            if binding_count > 0:
                patterns_detected.append(f"bindings_growing:{binding_count}")

            # Check for highly connected nodes (hubs)
            if cortex._graph and hasattr(cortex._graph, 'get_hubs'):
                hubs = cortex._graph.get_hubs(limit=3)
                for hub in hubs:
                    patterns_detected.append(f"hub:{hub}")

        return {
            "ok": True,
            "action": "pattern_recognition",
            "patterns_detected": patterns_detected,
            "wired": cortex is not None,
        }

    def _action_learning_calibration(self) -> Dict[str, Any]:
        """Calibrate cognition loop difficulty via RewardTracker.

        Reads current difficulty, success rate, and learning efficiency
        from the CognitionLoop's RewardTracker. If efficiency is too low
        (struggling) or too high (coasting), publishes a calibration nudge.
        """
        cognition = self._systems.get("cognition_loop")
        postal = self._systems.get("postal")
        difficulty = 0.5
        adjustment = 0.0
        tracker_status = {}

        if cognition:
            try:
                reward_tracker = getattr(cognition, '_reward_tracker', None)
                if reward_tracker:
                    # Get full status from tracker
                    if hasattr(reward_tracker, 'status'):
                        tracker_status = reward_tracker.status()
                        difficulty = tracker_status.get("difficulty", 0.5)
                        avg_reward = tracker_status.get("avg_reward", 0.0)
                        efficiency = tracker_status.get("learning_efficiency", 0.5)
                        samples = tracker_status.get("samples", 0)

                        # Only calibrate if we have enough data
                        if samples >= 5:
                            if efficiency < 0.2 and difficulty > 0.2:
                                # Struggling — suggest easing difficulty
                                adjustment = -0.05
                            elif efficiency > 0.8 and difficulty < 0.9:
                                # Coasting — suggest increasing difficulty
                                adjustment = 0.05
                    elif hasattr(reward_tracker, 'current_difficulty'):
                        difficulty = reward_tracker.current_difficulty

                # Also peek at recent cognition history for failure streaks
                history = getattr(cognition, '_history', None)
                if history and len(history) > 0:
                    recent = list(history)[-10:]
                    failures = sum(1 for h in recent
                                   if hasattr(h, 'success') and not h.success)
                    if failures >= 7:
                        # 70%+ failure in recent history — strong downward nudge
                        adjustment = min(adjustment, -0.1)

            except Exception as e:
                return {"ok": False, "error": str(e), "action": "learning_calibration"}

        # Publish calibration event if adjustment warranted
        if postal and adjustment != 0.0:
            try:
                postal.publish("admin.learning_calibrated", {
                    "difficulty": difficulty,
                    "adjustment": adjustment,
                    "new_target": max(0.1, min(1.0, difficulty + adjustment)),
                    "efficiency": tracker_status.get("learning_efficiency", 0.0),
                    "timestamp": time.time(),
                })
            except Exception:
                pass

        return {
            "ok": True,
            "action": "learning_calibration",
            "current_difficulty": difficulty,
            "adjustment": adjustment,
            "learning_efficiency": tracker_status.get("learning_efficiency", 0.0),
            "avg_reward": tracker_status.get("avg_reward", 0.0),
            "samples": tracker_status.get("samples", 0),
            "wired": cognition is not None,
        }

    def _action_ace_presence_check(self) -> Dict[str, Any]:
        """Check for Ace's presence via InterfacePresence.

        Queries the interface registry to see if any UI interfaces
        (sanctuary, qt, web) have recent heartbeats — a proxy for
        whether Ace is actively at the keyboard.
        """
        postal = self._systems.get("postal")
        ace_present = False
        last_seen = None
        interfaces_alive = 0
        interface_details = {}

        try:
            # InterfacePresence uses module-level functions, not instance methods
            from fairies.P40_Sensory.interface_presence import (
                get_presence_summary, get_available_interfaces
            )

            summary = get_presence_summary()
            now = time.time()

            for itype, info in summary.items():
                if info.get("available"):
                    interfaces_alive += 1
                    interface_details[itype] = True
                    # Track most recent heartbeat across all interfaces
                    for entry in info.get("entries", []):
                        hb = entry.get("last_heartbeat", 0)
                        if hb and (last_seen is None or hb > last_seen):
                            last_seen = hb
                else:
                    interface_details[itype] = False

            # Ace is "present" if any interface has heartbeat within 120s
            if last_seen and (now - last_seen) < 120:
                ace_present = True

        except ImportError:
            # InterfacePresence not available — fall back gracefully
            pass
        except Exception as e:
            return {"ok": False, "error": str(e), "action": "ace_presence_check"}

        # Publish presence change events for other systems
        if postal:
            try:
                postal.publish("admin.ace_presence", {
                    "present": ace_present,
                    "interfaces_alive": interfaces_alive,
                    "last_seen": last_seen,
                    "timestamp": time.time(),
                })
                # Also publish to user.presence — 4 fairies subscribe to this topic
                # (AutonomyFairy, ConversationSenseFairy, PerceptualGateFairy, WindowSenseFairy)
                postal.publish("user.presence", {
                    "present": ace_present,
                    "source": "interface_heartbeat",
                    "idle_seconds": (time.time() - last_seen) if last_seen else 9999.0,
                    "timestamp": time.time(),
                })
            except Exception:
                pass

        return {
            "ok": True,
            "action": "ace_presence_check",
            "ace_present": ace_present,
            "last_seen": last_seen,
            "interfaces_alive": interfaces_alive,
            "interfaces": interface_details,
            "wired": True,  # Uses module-level import, always "wired"
        }

    def _action_capability_gap_scan(self) -> Dict[str, Any]:
        """Detect capability gaps from CognitionLoop history.

        Cardinal Sprint 1 — the core gap-detection engine.

        Scans for:
        1. Repeated failures: Same goal/domain failing 3+ times → missing skill
        2. Slow goals: Goals taking 2x+ expected time → capability inefficiency
        3. Domain cold spots: Goal domains with zero recent successes → blind spot

        Publishes detected gaps to 'cardinal.gaps_detected' for downstream
        processing (future Sprint 2: SkillFactory will consume these).
        """
        cognition = self._systems.get("cognition_loop")
        postal = self._systems.get("postal")
        gaps = []
        scan_stats = {"cycles_analyzed": 0, "failures": 0, "slow_goals": 0}

        if not cognition:
            return {
                "ok": True, "action": "capability_gap_scan",
                "gaps": [], "wired": False,
            }

        try:
            history = getattr(cognition, '_history', None)
            if not history or len(history) == 0:
                return {
                    "ok": True, "action": "capability_gap_scan",
                    "gaps": [], "cycles_analyzed": 0, "wired": True,
                }

            recent = list(history)[-50:]  # Last 50 cognition cycles
            scan_stats["cycles_analyzed"] = len(recent)

            # --- 1. Repeated failure detection ---
            # Group failures by domain/goal-name
            failure_counts = defaultdict(list)
            success_domains = set()
            goal_durations = defaultdict(list)

            for cycle in recent:
                # CognitionCycle has .goal, .plan, .result, .reward
                goal = getattr(cycle, 'goal', None)
                result = getattr(cycle, 'result', None)

                if not goal:
                    continue

                domain = getattr(goal, 'domain', 'unknown')
                if hasattr(domain, 'value'):
                    domain = domain.value  # Enum → string
                goal_name = getattr(goal, 'name', str(goal))

                # Check success/failure
                success = False
                if result:
                    status = getattr(result, 'status', None)
                    if status:
                        status_val = status.value if hasattr(status, 'value') else str(status)
                        success = status_val in ('success', 'partial_success', 'completed')
                    # Also check SuccessLevel if available
                    slevel = getattr(result, 'success_level', None)
                    if slevel:
                        slevel_val = slevel.value if hasattr(slevel, 'value') else str(slevel)
                        success = slevel_val not in ('failure', 'none', 'error')

                if success:
                    success_domains.add(domain)
                else:
                    failure_counts[domain].append(goal_name)
                    scan_stats["failures"] += 1

                # Track duration for slow-goal detection
                duration = getattr(cycle, 'duration', None) or getattr(cycle, 'elapsed', None)
                if duration and duration > 0:
                    goal_durations[domain].append(duration)

            # Emit gaps for domains with 3+ failures
            for domain, failed_goals in failure_counts.items():
                if len(failed_goals) >= 3:
                    # Deduplicate goal names to find THE recurring one
                    name_counts = defaultdict(int)
                    for gn in failed_goals:
                        name_counts[gn] += 1
                    top_failure = max(name_counts, key=name_counts.get)

                    gaps.append({
                        "type": "repeated_failure",
                        "domain": domain,
                        "top_goal": top_failure,
                        "failure_count": len(failed_goals),
                        "severity": min(1.0, len(failed_goals) / 10.0),
                    })

            # --- 2. Slow-goal detection (Ace's polish suggestion) ---
            for domain, durations in goal_durations.items():
                if len(durations) < 3:
                    continue
                avg_dur = sum(durations) / len(durations)
                # Goals taking more than 2x the domain average → inefficient
                slow_count = sum(1 for d in durations if d > avg_dur * 2.0)
                if slow_count >= 2:
                    scan_stats["slow_goals"] += slow_count
                    gaps.append({
                        "type": "capability_inefficiency",
                        "domain": domain,
                        "avg_duration": round(avg_dur, 2),
                        "slow_count": slow_count,
                        "severity": min(1.0, slow_count / 5.0),
                    })

            # --- 3. Domain cold spots ---
            all_domains = {"introspection", "communication", "diagnosis",
                           "mentorship", "exploration", "coordination"}
            cold_domains = all_domains - success_domains
            for cd in cold_domains:
                # Only flag if we had attempts (failures) in this domain
                if cd in failure_counts:
                    gaps.append({
                        "type": "domain_cold_spot",
                        "domain": cd,
                        "attempts": len(failure_counts[cd]),
                        "successes": 0,
                        "severity": 0.6,
                    })

        except Exception as e:
            return {"ok": False, "error": str(e), "action": "capability_gap_scan"}

        # Sort gaps by severity descending
        gaps.sort(key=lambda g: g.get("severity", 0), reverse=True)

        # Publish gaps for downstream consumption
        if postal and gaps:
            try:
                postal.publish("cardinal.gaps_detected", {
                    "gaps": gaps[:10],  # Cap at 10 gaps per scan
                    "scan_stats": scan_stats,
                    "timestamp": time.time(),
                })
            except Exception:
                pass

        return {
            "ok": True,
            "action": "capability_gap_scan",
            "gaps": gaps[:10],
            "total_gaps": len(gaps),
            "cycles_analyzed": scan_stats["cycles_analyzed"],
            "failures_found": scan_stats["failures"],
            "slow_goals_found": scan_stats["slow_goals"],
            "wired": True,
        }

    # =========================================================================
    # TASK MANAGEMENT
    # =========================================================================

    def register(self, task: AdminTask):
        """Register a task."""
        with self._lock:
            self._tasks[task.name] = task
            # Set initial next_run
            if task.interval_seconds and task.next_run == 0.0:
                # Stagger initial runs to avoid thundering herd
                task.next_run = time.time() + random.uniform(0, task.interval_seconds)

    def unregister(self, name: str) -> bool:
        """Unregister a task."""
        with self._lock:
            if name in self._tasks:
                del self._tasks[name]
                return True
            return False

    def enable(self, name: str, enabled: bool = True):
        """Enable or disable a task."""
        with self._lock:
            if name in self._tasks:
                self._tasks[name].enabled = enabled

    def tick(self) -> List[Dict[str, Any]]:
        """
        Tick the task queue - run due tasks.

        Returns list of task results.
        """
        now = time.time()
        results = []

        with self._lock:
            # Get due tasks, sorted by priority
            due_tasks = [
                t for t in self._tasks.values()
                if t.is_due(now)
            ]
            due_tasks.sort(key=lambda t: t.priority.value)

            # Run up to max_per_tick tasks
            for task in due_tasks[:self._max_per_tick]:
                result = task.run()
                results.append({
                    "task": task.name,
                    "result": result,
                    "duration_ms": (time.time() - now) * 1000,
                })

                self._execution_history.append({
                    "task": task.name,
                    "ts": now,
                    "result": result,
                })

                self._total_runs += 1
                if not result.get("ok", True):
                    self._total_errors += 1

        return results

    def force_run(self, name: str) -> Optional[Dict[str, Any]]:
        """Force run a specific task."""
        with self._lock:
            if name in self._tasks:
                task = self._tasks[name]
                return task.run()
        return None

    def get_task(self, name: str) -> Optional[Dict[str, Any]]:
        """Get task info."""
        with self._lock:
            if name in self._tasks:
                return self._tasks[name].to_dict()
        return None

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks."""
        with self._lock:
            return [t.to_dict() for t in sorted(
                self._tasks.values(),
                key=lambda t: (t.priority.value, t.name)
            )]

    def status(self) -> Dict[str, Any]:
        """Get queue status."""
        now = time.time()
        with self._lock:
            due_count = sum(1 for t in self._tasks.values() if t.is_due(now))
            return {
                "total_tasks": len(self._tasks),
                "enabled_tasks": sum(1 for t in self._tasks.values() if t.enabled),
                "due_now": due_count,
                "total_runs": self._total_runs,
                "total_errors": self._total_errors,
                "error_rate": self._total_errors / max(1, self._total_runs),
                "history_length": len(self._execution_history),
            }


# Factory function
def create_admin_task_queue(
    max_tasks_per_tick: int = 3,
    systems: Dict[str, Any] = None
) -> AdminTaskQueue:
    """Create an admin task queue instance with optional system wiring."""
    return AdminTaskQueue(max_tasks_per_tick=max_tasks_per_tick, systems=systems)
