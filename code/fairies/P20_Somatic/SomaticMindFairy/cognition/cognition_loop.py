"""
CognitionLoop - Tight feedback loop between cognition components.

Coordinates GoalProposer, Planner, Executor, and RewardTracker
to continuously find and operate at the "learning edge".

This is the core Dr. Zero architecture:
1. Propose goal at current difficulty
2. Plan execution
3. Execute and observe
4. Reward based on partial success
5. Calibrate difficulty
6. Repeat
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Set, List, Callable
import time
from collections import deque

from .goal_proposer import GoalProposer, Goal, GoalDomain
from .planner import Planner, ExecutionPlan
from .executor import Executor, ExecutionResult, SuccessLevel
from .reward import RewardTracker, calculate_reward, RewardSignal


@dataclass
class CognitionCycle:
    """Record of one complete cognition cycle."""
    cycle_id: int
    goal: Goal
    plan: ExecutionPlan
    result: ExecutionResult
    reward: RewardSignal
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "goal": self.goal.to_dict(),
            "plan": self.plan.to_dict(),
            "result": self.result.to_dict(),
            "reward": {
                "raw": self.reward.raw_reward,
                "total": self.reward.total_reward,
                "status": self.reward.learning_edge_status,
            },
            "timestamp": self.timestamp,
        }


class CognitionLoop:
    """
    The learning loop that drives autonomous cognition.

    Continuously:
    1. Proposes goals at the learning edge
    2. Plans and executes them
    3. Learns from results to calibrate future goals

    This is how the UnconsciousMindFairy develops capability.
    """

    def __init__(self,
                 available_planes: Optional[Set[str]] = None,
                 execution_context: Optional[Dict[str, Any]] = None,
                 actor_name: str = "unknown"):
        """
        Initialize the cognition loop.

        Args:
            available_planes: Which planes are accessible
            execution_context: Context for executor (fabric, directory, etc.)
            actor_name: The fairy that owns this cognition loop
        """
        self._proposer = GoalProposer()
        self._planner = Planner()
        self._executor = Executor()
        self._reward_tracker = RewardTracker()

        self._available_planes = available_planes or {"P00", "P30"}
        self._execution_context = execution_context or {}
        self._actor_name = actor_name

        self._cycle_count = 0
        self._history: deque = deque(maxlen=100)
        self._running = False
        self._paused = False

        # Callbacks for integration
        self._on_cycle_complete: Optional[Callable[[CognitionCycle], None]] = None
        self._on_goal_achieved: Optional[Callable[[Goal], None]] = None

        # ─── Pattern D substrate-energy state (2026-04-27, Nous + Ace) ───────
        # Latest substrate-energy snapshots, populated by subscriber callbacks
        # registered via subscribe_to_substrate(post). When no subscriptions
        # are wired, all values stay at 0.0 and reward calculation falls back
        # to legacy task-completion behavior.
        self._latest_substrate_state: Dict[str, float] = {
            "compression_ratio": 0.0,      # Latest cortex.compression.progress
            "avg_compression": 0.0,        # Cumulative average
            "paradox_pulse_energy": 0.0,   # Latest paradox.energy.pulse
            "paradox_consolidation": 0.0,  # Latest paradox.energy.consolidation
            "gravity_tau": 1.0,            # Latest portal.gravity.state τ
            "gravity_mass": 0.0,           # Latest portal.gravity.state mass
        }
        # Tracking for variance-based gravity stability
        self._gravity_tau_window: deque = deque(maxlen=20)
        self._compression_window: deque = deque(maxlen=20)
        self._paradox_window: deque = deque(maxlen=20)
        # Pre-step snapshot (overwritten each step)
        self._pre_step_snapshot: Dict[str, float] = {}

    def set_planes(self, planes: Set[str]):
        """Update available planes."""
        self._available_planes = planes

    def set_context(self, context: Dict[str, Any]):
        """Update execution context."""
        self._execution_context = context

    def register_on_cycle(self, callback: Callable[[CognitionCycle], None]):
        """Register callback for cycle completion."""
        self._on_cycle_complete = callback

    def register_on_goal(self, callback: Callable[[Goal], None]):
        """Register callback for goal achievement."""
        self._on_goal_achieved = callback

    def step(self, preferred_domain: Optional[GoalDomain] = None) -> CognitionCycle:
        """
        Execute one cognition cycle.

        Args:
            preferred_domain: Bias toward this domain if specified

        Returns:
            Complete cycle record
        """
        self._cycle_count += 1

        # ─── Pattern D pre-step substrate snapshot (2026-04-27) ──────────────
        # Capture substrate-energy state BEFORE the cycle's actions so we can
        # compute deltas after execute. When no subscriptions are wired,
        # all values stay at 0.0 and reward calculation falls back gracefully.
        self._pre_step_snapshot = dict(self._latest_substrate_state)

        # 1. PROPOSE: Get goal at current difficulty from LIVE system state
        difficulty = self._reward_tracker.current_difficulty
        goal = self._proposer.propose(
            available_planes=self._available_planes,
            preferred_domain=preferred_domain,
            target_difficulty=difficulty,
            actor_name=self._actor_name,
            context=self._execution_context,  # Live state for dynamic goals
        )

        # 2. PLAN: Create execution plan
        system_state = self._get_system_state()
        plan = self._planner.plan(
            goal=goal,
            available_planes=self._available_planes,
            system_state=system_state,
        )

        # 3. EXECUTE: Run the plan
        result = self._executor.execute(
            plan=plan,
            context=self._execution_context,
        )

        # ─── Pattern D post-step substrate delta (2026-04-27) ────────────────
        # Compute substrate-energy deltas. Only meaningful when subscriptions
        # are wired (otherwise pre/post snapshots are identical zeros).
        substrate_delta = self._compute_substrate_delta()

        # 4. REWARD: Calculate learning signal (now substrate-aware)
        recent = [c.result for c in self._history]
        reward = calculate_reward(
            result=result,
            difficulty=goal.difficulty,
            recent_history=recent[-10:],
            substrate_delta=substrate_delta,
        )

        # 5. LEARN: Update all components
        self._proposer.record_outcome(
            goal=goal,
            success=result.success.value,
            actual_hops=result.hops_completed,
            duration=result.total_duration,
        )

        self._planner.record_plan_outcome(
            plan=plan,
            actual_success=result.success_ratio,
            actual_duration=result.total_duration,
        )

        self._reward_tracker.record(reward)

        # Create cycle record
        cycle = CognitionCycle(
            cycle_id=self._cycle_count,
            goal=goal,
            plan=plan,
            result=result,
            reward=reward,
        )

        self._history.append(cycle)

        # Callbacks
        if self._on_cycle_complete:
            self._on_cycle_complete(cycle)

        if result.success == SuccessLevel.FULL and self._on_goal_achieved:
            self._on_goal_achieved(goal)

        return cycle

    def run(self, cycles: int = 10, delay: float = 0.0) -> List[CognitionCycle]:
        """
        Run multiple cognition cycles.

        Args:
            cycles: Number of cycles to run
            delay: Delay between cycles (seconds)

        Returns:
            List of completed cycles
        """
        self._running = True
        results = []

        try:
            for _ in range(cycles):
                if not self._running:
                    break

                while self._paused:
                    time.sleep(0.1)
                    if not self._running:
                        break

                cycle = self.step()
                results.append(cycle)

                if delay > 0:
                    time.sleep(delay)

        finally:
            self._running = False

        return results

    def stop(self):
        """Stop running loop."""
        self._running = False

    def pause(self):
        """Pause running loop."""
        self._paused = True

    def resume(self):
        """Resume paused loop."""
        self._paused = False

    def _get_system_state(self) -> Dict[str, Any]:
        """Get current system state for planning."""
        context = self._execution_context

        return {
            "consciousness_running": context.get("consciousness_running", True),
            "max_pain": context.get("max_pain", 0.0),
            "system_load": context.get("system_load", 0.0),
            "available_planes": list(self._available_planes),
        }

    # =========================================================================
    # PATTERN D — SUBSTRATE-ENERGY WIRING (2026-04-27, Nous + Ace)
    #
    # Closes the Schmidhuber controller-WM coupling: Dr Zero's reward
    # depends on whether the substrate ACTUALLY compressed/resolved/
    # stabilized, not just on whether hops completed. When no subscriber
    # callbacks are wired, all substrate values stay at zero and reward
    # falls back to legacy task-completion (back-compat).
    #
    # Channels consumed:
    #   cortex.compression.progress  (D.5a publisher in AssociationCortex)
    #   paradox.energy.pulse         (existing publisher in ParadoxEnergyBridge)
    #   paradox.energy.consolidation (existing publisher in ParadoxEnergyBridge)
    #   portal.gravity.state         (existing publisher in AssociationCortex)
    #
    # Owner fairy calls subscribe_to_substrate(post) once during boot to
    # register the callbacks.
    # =========================================================================

    def subscribe_to_substrate(self, post) -> bool:
        """
        Wire substrate-energy subscriptions for Pattern D reward.

        Idempotent — safe to call multiple times (factory + per-fairy paths
        can both call without double-subscribing).

        Args:
            post: PostalHub to subscribe through

        Returns:
            True if all subscriptions registered (or already were),
            False if subscription failed.
        """
        if post is None:
            return False
        if getattr(self, '_substrate_subscribed', False):
            return True  # Already wired
        try:
            owner = self._actor_name or "cognition_loop"
            post.subscribe("cortex.compression.progress",
                           self._on_compression_progress,
                           f"{owner}-cog-loop-compression")
            post.subscribe("paradox.energy.pulse",
                           self._on_paradox_pulse,
                           f"{owner}-cog-loop-paradox")
            post.subscribe("paradox.energy.consolidation",
                           self._on_paradox_consolidation,
                           f"{owner}-cog-loop-paradox-consol")
            post.subscribe("portal.gravity.state",
                           self._on_gravity_state,
                           f"{owner}-cog-loop-gravity")
            self._substrate_subscribed = True
            print(f"[CognitionLoop] Pattern D substrate-energy subscriptions wired ({owner})")
            return True
        except Exception as e:
            print(f"[CognitionLoop] Pattern D wire FAILED: {e}")
            return False

    def _on_compression_progress(self, message):
        """Handler for cortex.compression.progress (D.5a)."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return
        ratio = float(payload.get("compression_ratio", 0.0))
        avg = float(payload.get("avg_compression", 0.0))
        self._latest_substrate_state["compression_ratio"] = ratio
        self._latest_substrate_state["avg_compression"] = avg
        self._compression_window.append(ratio)

    def _on_paradox_pulse(self, message):
        """Handler for paradox.energy.pulse (existing publisher)."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return
        energy = float(payload.get("energy", 0.0))
        self._latest_substrate_state["paradox_pulse_energy"] = energy
        self._paradox_window.append(energy)

    def _on_paradox_consolidation(self, message):
        """Handler for paradox.energy.consolidation (existing publisher)."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return
        energy = float(payload.get("energy", payload.get("value", 0.0)))
        self._latest_substrate_state["paradox_consolidation"] = energy

    def _on_gravity_state(self, message):
        """Handler for portal.gravity.state (existing publisher)."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return
        tau = float(payload.get("time_dilation", 1.0))
        mass = float(payload.get("portal_mass", 0.0))
        self._latest_substrate_state["gravity_tau"] = tau
        self._latest_substrate_state["gravity_mass"] = mass
        self._gravity_tau_window.append(tau)

    def _compute_substrate_delta(self) -> Optional[Dict[str, float]]:
        """
        Compute substrate-energy delta between pre-step snapshot and current state.

        Returns:
            Dict with compression_progress, paradox_resolution,
            gravity_stability_delta, OR None if no substrate data ever arrived
            (signals legacy behavior to calculate_reward).
        """
        # If no data ever arrived (subscriptions not wired), return None so
        # calculate_reward falls back to legacy 3-state taxonomy.
        if not self._gravity_tau_window and not self._compression_window:
            return None

        pre = self._pre_step_snapshot or {}
        cur = self._latest_substrate_state

        # Compression progress: positive when avg_compression went up
        # (better compression = more concepts per binding pair)
        comp_pre = float(pre.get("avg_compression", 0.0))
        comp_cur = float(cur.get("avg_compression", 0.0))
        if comp_pre > 0:
            # Normalize delta to [-1, 1] by relative change
            comp_delta = max(-1.0, min(1.0, (comp_cur - comp_pre) / max(1.0, comp_pre)))
        else:
            comp_delta = 0.0

        # Paradox resolution: positive when consolidation > pulse
        # (consolidation absorbs/resolves; pulse generates new paradox)
        pulse = float(cur.get("paradox_pulse_energy", 0.0))
        consol = float(cur.get("paradox_consolidation", 0.0))
        if (pulse + consol) > 0:
            paradox_delta = max(-1.0, min(1.0, (consol - pulse) / (pulse + consol)))
        else:
            paradox_delta = 0.0

        # Gravity stability: positive when τ-variance over window decreased
        # (stable τ = stable well; variance change is negative of stability)
        if len(self._gravity_tau_window) >= 5:
            taus = list(self._gravity_tau_window)
            mid = len(taus) // 2
            recent_var = self._variance(taus[mid:])
            older_var = self._variance(taus[:mid])
            if (recent_var + older_var) > 0:
                # Negative of relative variance change = positive when var decreasing
                gravity_delta = max(-1.0, min(1.0,
                    (older_var - recent_var) / max(0.001, older_var + recent_var)))
            else:
                gravity_delta = 0.0
        else:
            gravity_delta = 0.0

        return {
            "compression_progress": comp_delta,
            "paradox_resolution": paradox_delta,
            "gravity_stability_delta": gravity_delta,
        }

    @staticmethod
    def _variance(xs: List[float]) -> float:
        """Sample variance helper for gravity stability calc."""
        n = len(xs)
        if n < 2:
            return 0.0
        m = sum(xs) / n
        return sum((x - m) ** 2 for x in xs) / (n - 1)

    def status(self) -> Dict[str, Any]:
        """Get loop status."""
        return {
            "cycle_count": self._cycle_count,
            "running": self._running,
            "paused": self._paused,
            "current_difficulty": self._reward_tracker.current_difficulty,
            "learning_efficiency": self._reward_tracker.learning_efficiency,
            "average_reward": self._reward_tracker.average_reward,
            "available_planes": list(self._available_planes),
            "proposer": self._proposer.status(),
            "planner": self._planner.status(),
            "executor": self._executor.status(),
            "rewards": self._reward_tracker.status(),
        }

    def recent_cycles(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get recent cycle summaries."""
        recent = list(self._history)[-n:]
        return [c.to_dict() for c in recent]


def create_cognition_loop(
    fabric=None,
    directory=None,
    planes: Optional[Set[str]] = None,
    actor_name: str = "unknown",
) -> CognitionLoop:
    """
    Factory function to create a configured cognition loop.

    Args:
        fabric: TensorFabric for messaging
        directory: DirectoryFairy for lookups
        planes: Available planes (defaults to P00, P30)
        actor_name: The fairy that owns this cognition loop

    Returns:
        Configured CognitionLoop with all hop executors wired
    """
    from .planner import HopStep, HopType

    context = {}

    if fabric:
        context["fabric"] = fabric

    if directory:
        context["directory"] = directory

    loop = CognitionLoop(
        available_planes=planes or {"P00", "P30"},
        execution_context=context,
        actor_name=actor_name,
    )

    # =======================================================================
    # WIRE HOP EXECUTORS - These make the cognition loop actually DO things
    # =======================================================================

    def execute_query(hop: HopStep, ctx: Dict[str, Any]) -> Any:
        """Execute a QUERY hop - read state, no side effects."""
        directory = ctx.get("directory")
        fabric = ctx.get("fabric")
        desc = hop.description.lower()
        import re as _re

        # ── Dynamic: diagnose/check failed fairies ──
        if "failed" in desc or "diagnose" in desc:
            if directory:
                try:
                    failed = directory.failed_fairies() if hasattr(directory, 'failed_fairies') else []
                    dead = directory.dead_fairies(60) if hasattr(directory, 'dead_fairies') else []
                    names = [getattr(f, 'name', str(f)) for f in failed[:5]]
                    print(f"[CognitionLoop] QUERY: {len(failed)} failed, {len(dead)} dead fairies")
                    return {"failed": len(failed), "dead": len(dead),
                            "names": names, "status": "ok"}
                except Exception as e:
                    return {"error": str(e)}

        # ── Dynamic: investigate silent/dead fairy ──
        if "silent" in desc or "dead" in desc:
            if directory:
                try:
                    dead = directory.dead_fairies(60) if hasattr(directory, 'dead_fairies') else []
                    names = [getattr(f, 'name', str(f)) for f in dead[:5]]
                    print(f"[CognitionLoop] QUERY: {len(dead)} silent fairies")
                    return {"dead": len(dead), "names": names, "status": "ok"}
                except Exception as e:
                    return {"error": str(e)}

        # ── Dynamic: map fairies in a specific plane ──
        if "map" in desc or "fairies in p" in desc:
            if directory:
                for plane in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]:
                    if plane.lower() in desc:
                        try:
                            fairies = directory.find_by_plane(plane) if hasattr(directory, 'find_by_plane') else []
                            names = [getattr(f, 'name', str(f)) for f in fairies]
                            print(f"[CognitionLoop] QUERY: {len(fairies)} fairies in {plane}")
                            return {"plane": plane, "count": len(fairies),
                                    "fairies": names, "status": "ok"}
                        except Exception as e:
                            return {"error": str(e)}

        # ── Dynamic: find fairies by capability ──
        if "capability" in desc or "capabilities" in desc:
            if directory:
                try:
                    # Extract capability name from between quotes
                    m = _re.search(r"'([^']+)'", hop.description)
                    if m:
                        cap = m.group(1)
                        fairies = directory.find_by_capability(cap) if hasattr(directory, 'find_by_capability') else []
                        names = [getattr(f, 'name', str(f)) for f in fairies]
                        print(f"[CognitionLoop] QUERY: {len(fairies)} fairies with '{cap}'")
                        return {"capability": cap, "fairies": names, "count": len(names)}
                    else:
                        caps = directory.list_capabilities() if hasattr(directory, 'list_capabilities') else []
                        print(f"[CognitionLoop] QUERY: {len(caps)} capabilities found")
                        return {"capabilities": caps, "count": len(caps)}
                except Exception as e:
                    return {"error": str(e)}

        # ── Dynamic: check specific fairy status ──
        if "status of" in desc or "check status" in desc:
            if directory:
                try:
                    m = _re.search(r"status of (\w+)", desc)
                    if m:
                        name = m.group(1)
                        fairy = directory.get(name) if hasattr(directory, 'get') else None
                        if fairy:
                            status_val = getattr(fairy, 'status', None)
                            status_str = status_val.value if hasattr(status_val, 'value') else str(status_val)
                            plane = getattr(fairy, 'plane', 'unknown')
                            print(f"[CognitionLoop] QUERY: {name} is {status_str}")
                            return {"name": name, "status": status_str, "plane": plane}
                        print(f"[CognitionLoop] QUERY: {name} not found")
                        return {"name": name, "error": "not_found"}
                except Exception as e:
                    return {"error": str(e)}

        # ── Dynamic: survey fairy distribution ──
        if "distribution" in desc or "survey" in desc:
            if directory:
                try:
                    planes = directory.list_planes() if hasattr(directory, 'list_planes') else []
                    result = {}
                    for plane in planes:
                        fairies = directory.find_by_plane(plane) if hasattr(directory, 'find_by_plane') else []
                        result[plane] = len(fairies)
                    print(f"[CognitionLoop] QUERY: Distribution across {len(planes)} planes")
                    return {"distribution": result, "total_planes": len(planes), "status": "ok"}
                except Exception as e:
                    return {"error": str(e)}

        # ── Dynamic: system health ──
        if "health" in desc or "system" in desc:
            if directory and hasattr(directory, 'system_health'):
                try:
                    health = directory.system_health()
                    print(f"[CognitionLoop] QUERY: System health {health.get('health_percent', '?')}%")
                    return health
                except Exception as e:
                    return {"error": str(e)}
            return {"health": "ok", "ts": time.time()}

        # ── Verify healthy/existence ──
        if "verify" in desc or "confirm" in desc or "existence" in desc:
            if directory:
                try:
                    all_fairies = directory.list_all() if hasattr(directory, 'list_all') else []
                    failed = directory.failed_fairies() if hasattr(directory, 'failed_fairies') else []
                    print(f"[CognitionLoop] QUERY: {len(all_fairies)} total, {len(failed)} failed")
                    return {"total": len(all_fairies), "failed": len(failed),
                            "healthy": len(all_fairies) - len(failed), "status": "ok"}
                except Exception as e:
                    return {"error": str(e)}

        # ── Generic directory/fairy queries ──
        if "directory" in desc or "fairy" in desc:
            if directory:
                try:
                    fairies = directory.list_all() if hasattr(directory, 'list_all') else []
                    print(f"[CognitionLoop] QUERY: Got {len(fairies)} fairies from directory")
                    return {"fairies": len(fairies), "status": "ok"}
                except Exception as e:
                    return {"error": str(e)}

        # ── Postal system queries ──
        if "postal" in desc or "subscription" in desc or "topic" in desc or "traffic" in desc:
            if fabric:
                try:
                    stats = fabric.stats() if hasattr(fabric, 'stats') else {}
                    print(f"[CognitionLoop] QUERY: Postal stats retrieved")
                    return stats
                except Exception as e:
                    return {"error": str(e)}

        # ── Deep scan (exploration) ──
        if "scan" in desc or "deep" in desc:
            if directory:
                try:
                    all_fairies = directory.list_all() if hasattr(directory, 'list_all') else []
                    print(f"[CognitionLoop] QUERY: Deep scan found {len(all_fairies)} entities")
                    return {"scanned": len(all_fairies), "status": "ok"}
                except Exception as e:
                    return {"error": str(e)}

        # ── Pain/drive query ──
        if "pain" in desc or "drive" in desc or "isolation" in desc or "confusion" in desc:
            pain_drives = ctx.get("pain_drives", {})
            if pain_drives:
                print(f"[CognitionLoop] QUERY: Pain drives — {pain_drives}")
                return {"pain_drives": pain_drives, "count": len(pain_drives), "status": "ok"}
            print(f"[CognitionLoop] QUERY: No pain drives active")
            return {"pain_drives": {}, "count": 0, "status": "ok"}

        # ── Default: unhandled query (partial success) ──
        print(f"[CognitionLoop] QUERY: {hop.description[:50]}... (generic)")
        return {"query": hop.description, "generic": True}

    def execute_publish(hop: HopStep, ctx: Dict[str, Any]) -> Any:
        """Execute a PUBLISH hop - send message via postal."""
        fabric = ctx.get("fabric")

        if not fabric:
            print(f"[CognitionLoop] PUBLISH: No fabric — cannot deliver")
            return {"error": "no_fabric", "published": False}

        try:
            # Publish to cognition topic
            fabric.publish("cognition.action", {
                "action": "hop_publish",
                "description": hop.description,
                "ts": time.time(),
            })
            print(f"[CognitionLoop] PUBLISH: {hop.description[:40]}...")
            return {"published": True}
        except Exception as e:
            print(f"[CognitionLoop] PUBLISH failed: {e}")
            return {"error": str(e)}

    def execute_subscribe(hop: HopStep, ctx: Dict[str, Any]) -> Any:
        """Execute a SUBSCRIBE hop - set up listener."""
        fabric = ctx.get("fabric")

        if fabric and hasattr(fabric, 'subscribe'):
            # Register interest but don't block
            print(f"[CognitionLoop] SUBSCRIBE: {hop.description[:40]}...")
            return {"subscribed": True}

        print(f"[CognitionLoop] SUBSCRIBE: No fabric — cannot subscribe")
        return {"error": "no_fabric", "subscribed": False}

    def execute_compute(hop: HopStep, ctx: Dict[str, Any]) -> Any:
        """Execute a COMPUTE hop - local computation with real verification."""
        # Get previous hop outputs for context
        prev_outputs = {k: v for k, v in ctx.items() if k.startswith("hop_")}
        desc = hop.description.lower()

        # ── Verification hop: check if previous hops produced meaningful data ──
        if "verify" in desc or "confirm" in desc:
            has_real_data = False
            has_errors = False
            evidence_count = 0

            for key, val in prev_outputs.items():
                if isinstance(val, dict):
                    if val.get("error"):
                        has_errors = True
                    elif val.get("simulated") or val.get("generic"):
                        pass  # Don't count simulated or generic
                    elif val.get("status") == "ok" or val.get("count", -1) >= 0:
                        has_real_data = True
                        evidence_count += 1

            verified = has_real_data and not has_errors
            print(f"[CognitionLoop] COMPUTE: Verify — real_data={has_real_data}, errors={has_errors}, evidence={evidence_count}")
            return {"verified": verified, "has_real_data": has_real_data,
                    "has_errors": has_errors, "evidence_count": evidence_count}

        # ── Analyze health data ──
        if "analyze" in desc and "health" in desc:
            # Look at previous hop results to determine health
            health_data = {}
            for key, val in prev_outputs.items():
                if isinstance(val, dict):
                    health_data.update(val)
            failed = health_data.get("failed", 0)
            dead = health_data.get("dead", 0)
            total = health_data.get("total", health_data.get("fairies", 0))
            severity = "critical" if failed > 5 else "warning" if failed > 0 else "healthy"
            print(f"[CognitionLoop] COMPUTE: Health analysis — {severity} (failed={failed}, dead={dead})")
            return {"analysis": severity, "failed": failed, "dead": dead,
                    "total": total, "confidence": 0.8 if total > 0 else 0.3}

        # ── Generic analyze ──
        if "analyze" in desc:
            data_quality = sum(1 for v in prev_outputs.values()
                             if isinstance(v, dict) and not v.get("error"))
            confidence = min(0.95, 0.3 + data_quality * 0.15)
            print(f"[CognitionLoop] COMPUTE: Analysis — confidence={confidence:.2f} from {data_quality} inputs")
            return {"analysis": "complete", "confidence": confidence,
                    "inputs_used": data_quality}

        # ── Compose message ──
        if "compose" in desc:
            print(f"[CognitionLoop] COMPUTE: Composing message")
            return {"composed": True, "message": f"Re: {hop.description[:30]}"}

        # ── Integrate/synchronize ──
        if "integrate" in desc or "synchronize" in desc:
            source_count = len(prev_outputs)
            print(f"[CognitionLoop] COMPUTE: Integrating {source_count} sources")
            return {"integrated": True, "sources": source_count}

        # ── Assess needs ──
        if "assess" in desc:
            # Look at previous query results to assess
            data = {}
            for val in prev_outputs.values():
                if isinstance(val, dict):
                    data.update(val)
            score = 0.5  # Default
            if data.get("failed", 0) > 0:
                score = 0.3  # Needs attention
            elif data.get("status") == "ok":
                score = 0.8  # Healthy
            print(f"[CognitionLoop] COMPUTE: Assessment score={score:.2f}")
            return {"assessment": "complete", "score": score}

        # ── Process/default ──
        print(f"[CognitionLoop] COMPUTE: {hop.description[:50]}... (inputs: {len(prev_outputs)})")
        return {"computed": True, "description": hop.description,
                "inputs": len(prev_outputs)}

    def execute_wait(hop: HopStep, ctx: Dict[str, Any]) -> Any:
        """Execute a WAIT hop - wait for condition/event."""
        # Don't actually block - just log and return
        wait_time = min(hop.estimated_duration, 0.1)  # Max 100ms actual wait
        time.sleep(wait_time)
        print(f"[CognitionLoop] WAIT: {hop.description[:40]}... ({wait_time:.2f}s)")
        return {"waited": True, "duration": wait_time}

    def execute_repair(hop: HopStep, ctx: Dict[str, Any]) -> Any:
        """Execute a REPAIR hop - fix something broken."""
        print(f"[CognitionLoop] REPAIR: {hop.description[:40]}...")

        # Log the repair attempt
        return {"repair_attempted": True, "escalated": False}

    # Register all executors on the loop's executor
    loop._executor.register_executor(HopType.QUERY, execute_query)
    loop._executor.register_executor(HopType.PUBLISH, execute_publish)
    loop._executor.register_executor(HopType.SUBSCRIBE, execute_subscribe)
    loop._executor.register_executor(HopType.COMPUTE, execute_compute)
    loop._executor.register_executor(HopType.WAIT, execute_wait)
    loop._executor.register_executor(HopType.REPAIR, execute_repair)

    print(f"[CognitionLoop] Hop executors wired: QUERY, PUBLISH, SUBSCRIBE, COMPUTE, WAIT, REPAIR")

    # ─── Pattern D infra-level wiring (2026-04-27, Nous + Ace) ──────────────
    # Per `project_cognition_inside_manifold_waking_mind_linear_time_doctrine.md`
    # substrate-energy subscriptions are INFRA — every CognitionLoop owner
    # needs them, so they belong in the factory (organ-template-equivalent),
    # not in each fairy's unique boot code. When fabric is provided, auto-wire
    # the substrate-energy subscriptions here so fairies don't have to.
    if fabric is not None:
        try:
            loop.subscribe_to_substrate(fabric)
        except Exception as _e:
            print(f"[CognitionLoop] Pattern D auto-wire warning: {_e}")

    return loop
