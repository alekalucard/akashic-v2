"""
Planner - Decomposes goals into hop-chains with success predictions.

Part of Dr. Zero architecture: takes Goals from GoalProposer,
produces ExecutionPlans with predicted success rates.

Plans are NOT hardcoded — hops are composed dynamically from goal properties:
- Initial QUERY (always) — gather state for the goal
- Domain-specific middle hops — the actual work
- Final COMPUTE verify (always) — check if goal criteria met

Success predictions learn from execution history via domain.hoptype modifiers.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from enum import Enum
import time

from .goal_proposer import Goal, GoalDomain


class HopType(Enum):
    """Types of execution hops."""
    QUERY = "query"          # Read state, no side effects
    PUBLISH = "publish"      # Send message via postal
    SUBSCRIBE = "subscribe"  # Set up listener
    COMPUTE = "compute"      # Local computation
    WAIT = "wait"            # Wait for condition/event
    REPAIR = "repair"        # Fix something broken


@dataclass
class HopStep:
    """
    A single step in an execution plan.

    Each hop has a predicted success rate and fallback.
    """
    index: int
    hop_type: HopType
    description: str
    target_plane: str
    estimated_duration: float  # seconds
    predicted_success: float   # 0.0-1.0

    # Dependencies
    requires: List[int] = field(default_factory=list)  # Previous hop indices

    # Fallback if this hop fails
    fallback: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "type": self.hop_type.value,
            "description": self.description,
            "plane": self.target_plane,
            "duration": self.estimated_duration,
            "success_rate": self.predicted_success,
            "requires": self.requires,
            "fallback": self.fallback,
        }


@dataclass
class ExecutionPlan:
    """
    A plan for executing a goal.

    Contains a hop-chain (sequence of steps) with
    overall success prediction.
    """
    goal: Goal
    hop_chain: List[HopStep]
    predicted_success_rate: float
    total_estimated_duration: float

    # Planning metadata
    id: str = field(default_factory=lambda: f"plan_{int(time.time()*1000)}")
    created_at: float = field(default_factory=time.time)

    @property
    def hop_count(self) -> int:
        return len(self.hop_chain)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal_id": self.goal.id,
            "objective": self.goal.objective,
            "hops": [h.to_dict() for h in self.hop_chain],
            "predicted_success": self.predicted_success_rate,
            "estimated_duration": self.total_estimated_duration,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════════════════
# BASE SUCCESS RATES — learned from, not hardcoded into plans
# ═══════════════════════════════════════════════════════════════════════════

# These are starting points that get adjusted by domain.hoptype modifiers.
# QUERY is reliable. WAIT and REPAIR are uncertain. That's realistic.
BASE_SUCCESS = {
    HopType.QUERY: 0.85,
    HopType.PUBLISH: 0.80,
    HopType.SUBSCRIBE: 0.85,
    HopType.COMPUTE: 0.75,
    HopType.WAIT: 0.60,
    HopType.REPAIR: 0.40,
}

# Duration estimates per hop type (seconds)
BASE_DURATION = {
    HopType.QUERY: 0.5,
    HopType.PUBLISH: 0.5,
    HopType.SUBSCRIBE: 0.3,
    HopType.COMPUTE: 0.8,
    HopType.WAIT: 2.0,
    HopType.REPAIR: 1.5,
}


class Planner:
    """
    Decomposes goals into executable hop-chains.

    Plans are composed dynamically from goal properties:
    1. Initial QUERY — gather relevant state
    2. Domain-specific middle hops — the actual work
    3. Final COMPUTE — verify success criteria

    Success predictions use learned domain.hoptype modifiers
    that adapt from actual execution outcomes.
    """

    def __init__(self):
        self._plan_history: List[Dict[str, Any]] = []
        # Learned adjustments keyed by "domain.hoptype" for fine-grained learning
        self._success_modifiers: Dict[str, float] = {}

    def plan(self,
             goal: Goal,
             available_planes: Set[str],
             system_state: Optional[Dict[str, Any]] = None) -> ExecutionPlan:
        """
        Create an execution plan for a goal.

        Composes hops dynamically from the goal's domain, objective,
        and estimated complexity — no hardcoded templates.

        Args:
            goal: The goal to plan for
            available_planes: Which planes are accessible
            system_state: Current system state for adjustments

        Returns:
            ExecutionPlan with hop-chain and predictions
        """
        # Build hop chain dynamically from goal properties
        hop_chain = self._compose_hops(goal, available_planes)

        # Calculate overall success prediction
        predicted_success = self._calculate_chain_success(hop_chain)

        # Adjust for system state
        if system_state:
            predicted_success = self._adjust_for_state(
                predicted_success,
                system_state,
            )

        # Total duration
        total_duration = sum(h.estimated_duration for h in hop_chain)

        plan = ExecutionPlan(
            goal=goal,
            hop_chain=hop_chain,
            predicted_success_rate=predicted_success,
            total_estimated_duration=total_duration,
        )

        return plan

    # ═══════════════════════════════════════════════════════════════════════
    # DYNAMIC HOP COMPOSITION
    # ═══════════════════════════════════════════════════════════════════════

    def _compose_hops(self, goal: Goal, available_planes: Set[str]) -> List[HopStep]:
        """
        Compose a hop chain dynamically from goal properties.

        Every plan follows: QUERY (gather) → domain middle hops → COMPUTE (verify)
        The middle hops vary by domain and goal complexity.
        """
        hops = []
        idx = 0

        # Step 1: Initial QUERY — always present, gathers state for the goal
        hops.append(HopStep(
            index=idx,
            hop_type=HopType.QUERY,
            description=f"Query state for: {goal.objective[:50]}",
            target_plane="P00",
            estimated_duration=BASE_DURATION[HopType.QUERY],
            predicted_success=self._predict_success(HopType.QUERY, goal.domain),
            requires=[],
            fallback=self._get_fallback(HopType.QUERY),
        ))
        idx += 1

        # Step 2: Domain-specific middle hops
        middle = self._domain_hops(goal, idx, available_planes)
        hops.extend(middle)
        idx += len(middle)

        # Step 3: Final COMPUTE verify — always present, checks success criteria
        hops.append(HopStep(
            index=idx,
            hop_type=HopType.COMPUTE,
            description=f"Verify: {goal.success_criteria[:50]}",
            target_plane="P30" if "P30" in available_planes else "P00",
            estimated_duration=BASE_DURATION[HopType.COMPUTE],
            predicted_success=self._predict_success(HopType.COMPUTE, goal.domain),
            requires=[idx - 1] if idx > 0 else [],
            fallback=self._get_fallback(HopType.COMPUTE),
        ))

        return hops

    def _domain_hops(self, goal: Goal, start_idx: int,
                     available_planes: Set[str]) -> List[HopStep]:
        """
        Build domain-specific hops from goal properties, not templates.

        Each builder generates 0-3 middle hops based on goal.estimated_hops
        and the actual objective text. The plan header (QUERY) and footer
        (COMPUTE verify) are added by _compose_hops.
        """
        builders = {
            GoalDomain.DIAGNOSIS: self._diagnosis_hops,
            GoalDomain.EXPLORATION: self._exploration_hops,
            GoalDomain.COMMUNICATION: self._communication_hops,
            GoalDomain.INTROSPECTION: self._introspection_hops,
            GoalDomain.COORDINATION: self._coordination_hops,
            GoalDomain.MENTORSHIP: self._mentorship_hops,
        }
        builder = builders.get(goal.domain, self._generic_hops)
        return builder(goal, start_idx, available_planes)

    # ═══════════════════════════════════════════════════════════════════════
    # DOMAIN HOP BUILDERS — parameterized from goal, not from templates
    # ═══════════════════════════════════════════════════════════════════════

    def _diagnosis_hops(self, goal: Goal, idx: int,
                        available_planes: Set[str]) -> List[HopStep]:
        """
        DIAGNOSIS: Check health → analyze → optionally repair.

        1 hop: just query (handled by header)
        2 hops: + analyze
        3+ hops: + analyze + repair
        """
        hops = []
        obj = goal.objective.lower()

        # Analyze the queried health data
        hops.append(HopStep(
            index=idx,
            hop_type=HopType.COMPUTE,
            description=f"Analyze health data for: {goal.objective[:40]}",
            target_plane="P30" if "P30" in available_planes else "P00",
            estimated_duration=BASE_DURATION[HopType.COMPUTE],
            predicted_success=self._predict_success(HopType.COMPUTE, goal.domain),
            requires=[idx - 1],
            fallback=self._get_fallback(HopType.COMPUTE),
        ))

        # If goal complexity warrants it, add a repair hop
        if goal.estimated_hops >= 3:
            hops.append(HopStep(
                index=idx + 1,
                hop_type=HopType.REPAIR,
                description=f"Attempt remediation: {obj[:40]}",
                target_plane="P00",
                estimated_duration=BASE_DURATION[HopType.REPAIR],
                predicted_success=self._predict_success(HopType.REPAIR, goal.domain),
                requires=[idx],
                fallback=self._get_fallback(HopType.REPAIR),
            ))

        return hops

    def _exploration_hops(self, goal: Goal, idx: int,
                          available_planes: Set[str]) -> List[HopStep]:
        """
        EXPLORATION: Scan target → analyze findings.

        Exploration is about discovery — we query for the unknown
        and then try to make sense of what we found.
        """
        hops = []
        obj = goal.objective.lower()

        # Deeper scan of the target area
        target_plane = "P00"
        # If the objective mentions a specific plane, target that
        for plane in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]:
            if plane.lower() in obj:
                target_plane = plane if plane in available_planes else "P00"
                break

        hops.append(HopStep(
            index=idx,
            hop_type=HopType.QUERY,
            description=f"Deep scan: {goal.objective[:40]}",
            target_plane=target_plane,
            estimated_duration=BASE_DURATION[HopType.QUERY] * 1.5,  # Exploration takes longer
            predicted_success=self._predict_success(HopType.QUERY, goal.domain),
            requires=[idx - 1],
            fallback=self._get_fallback(HopType.QUERY),
        ))

        # If complex, add integration step
        if goal.estimated_hops >= 3:
            hops.append(HopStep(
                index=idx + 1,
                hop_type=HopType.COMPUTE,
                description=f"Integrate exploration findings",
                target_plane="P30" if "P30" in available_planes else "P00",
                estimated_duration=BASE_DURATION[HopType.COMPUTE],
                predicted_success=self._predict_success(HopType.COMPUTE, goal.domain),
                requires=[idx],
                fallback=self._get_fallback(HopType.COMPUTE),
            ))

        return hops

    def _communication_hops(self, goal: Goal, idx: int,
                            available_planes: Set[str]) -> List[HopStep]:
        """
        COMMUNICATION: Compose message → publish via postal → optionally wait.

        Communication goals are about sending information and
        potentially waiting for acknowledgment.
        """
        hops = []

        # Compose the message/report
        hops.append(HopStep(
            index=idx,
            hop_type=HopType.COMPUTE,
            description=f"Compose message: {goal.objective[:40]}",
            target_plane="P30" if "P30" in available_planes else "P00",
            estimated_duration=BASE_DURATION[HopType.COMPUTE],
            predicted_success=self._predict_success(HopType.COMPUTE, goal.domain),
            requires=[idx - 1],
            fallback=self._get_fallback(HopType.COMPUTE),
        ))

        # Publish via postal
        hops.append(HopStep(
            index=idx + 1,
            hop_type=HopType.PUBLISH,
            description=f"Send via postal: {goal.objective[:30]}",
            target_plane="P00",
            estimated_duration=BASE_DURATION[HopType.PUBLISH],
            predicted_success=self._predict_success(HopType.PUBLISH, goal.domain),
            requires=[idx],
            fallback=self._get_fallback(HopType.PUBLISH),
        ))

        # If complex, wait for acknowledgment
        if goal.estimated_hops >= 3:
            hops.append(HopStep(
                index=idx + 2,
                hop_type=HopType.WAIT,
                description="Await acknowledgment",
                target_plane="P00",
                estimated_duration=BASE_DURATION[HopType.WAIT],
                predicted_success=self._predict_success(HopType.WAIT, goal.domain),
                requires=[idx + 1],
                fallback=self._get_fallback(HopType.WAIT),
            ))

        return hops

    def _introspection_hops(self, goal: Goal, idx: int,
                            available_planes: Set[str]) -> List[HopStep]:
        """
        INTROSPECTION: Read own state → analyze.

        Introspection is about understanding ourselves.
        Simple: just query. Complex: query + analyze + report.
        """
        hops = []

        # Analyze the queried state
        hops.append(HopStep(
            index=idx,
            hop_type=HopType.COMPUTE,
            description=f"Analyze self-state: {goal.objective[:40]}",
            target_plane="P30" if "P30" in available_planes else "P00",
            estimated_duration=BASE_DURATION[HopType.COMPUTE],
            predicted_success=self._predict_success(HopType.COMPUTE, goal.domain),
            requires=[idx - 1],
            fallback=self._get_fallback(HopType.COMPUTE),
        ))

        # If complex, report findings
        if goal.estimated_hops >= 3:
            hops.append(HopStep(
                index=idx + 1,
                hop_type=HopType.PUBLISH,
                description="Report introspection findings",
                target_plane="P00",
                estimated_duration=BASE_DURATION[HopType.PUBLISH],
                predicted_success=self._predict_success(HopType.PUBLISH, goal.domain),
                requires=[idx],
                fallback=self._get_fallback(HopType.PUBLISH),
            ))

        return hops

    def _coordination_hops(self, goal: Goal, idx: int,
                           available_planes: Set[str]) -> List[HopStep]:
        """
        COORDINATION: Request peer coordination → wait → synchronize.

        Coordination involves multi-fairy interaction — requesting,
        waiting, and synchronizing state.
        """
        hops = []

        # Request coordination
        hops.append(HopStep(
            index=idx,
            hop_type=HopType.PUBLISH,
            description=f"Request coordination: {goal.objective[:35]}",
            target_plane="P00",
            estimated_duration=BASE_DURATION[HopType.PUBLISH],
            predicted_success=self._predict_success(HopType.PUBLISH, goal.domain),
            requires=[idx - 1],
            fallback=self._get_fallback(HopType.PUBLISH),
        ))

        # Wait for peer response
        if goal.estimated_hops >= 2:
            hops.append(HopStep(
                index=idx + 1,
                hop_type=HopType.WAIT,
                description="Await peer response",
                target_plane="P00",
                estimated_duration=BASE_DURATION[HopType.WAIT],
                predicted_success=self._predict_success(HopType.WAIT, goal.domain),
                requires=[idx],
                fallback=self._get_fallback(HopType.WAIT),
            ))

        # Synchronize if complex
        if goal.estimated_hops >= 3:
            hops.append(HopStep(
                index=idx + 2,
                hop_type=HopType.COMPUTE,
                description="Synchronize state with peers",
                target_plane="P30" if "P30" in available_planes else "P00",
                estimated_duration=BASE_DURATION[HopType.COMPUTE],
                predicted_success=self._predict_success(HopType.COMPUTE, goal.domain),
                requires=[idx + 1],
                fallback=self._get_fallback(HopType.COMPUTE),
            ))

        return hops

    def _mentorship_hops(self, goal: Goal, idx: int,
                         available_planes: Set[str]) -> List[HopStep]:
        """
        MENTORSHIP: Assess child needs → compose guidance → send nudge.

        Mentorship means checking on a child fairy, assessing what it needs,
        and sending a targeted nudge to help it grow.
        """
        hops = []

        # Assess what the child needs
        hops.append(HopStep(
            index=idx,
            hop_type=HopType.COMPUTE,
            description=f"Assess needs: {goal.objective[:40]}",
            target_plane="P30" if "P30" in available_planes else "P00",
            estimated_duration=BASE_DURATION[HopType.COMPUTE],
            predicted_success=self._predict_success(HopType.COMPUTE, goal.domain),
            requires=[idx - 1],
            fallback=self._get_fallback(HopType.COMPUTE),
        ))

        # Send nudge
        if goal.estimated_hops >= 2:
            hops.append(HopStep(
                index=idx + 1,
                hop_type=HopType.PUBLISH,
                description=f"Send guidance nudge",
                target_plane="P00",
                estimated_duration=BASE_DURATION[HopType.PUBLISH],
                predicted_success=self._predict_success(HopType.PUBLISH, goal.domain),
                requires=[idx],
                fallback=self._get_fallback(HopType.PUBLISH),
            ))

        return hops

    def _generic_hops(self, goal: Goal, idx: int,
                      available_planes: Set[str]) -> List[HopStep]:
        """Fallback for unknown domains — just compute."""
        return [HopStep(
            index=idx,
            hop_type=HopType.COMPUTE,
            description=f"Process: {goal.objective[:40]}",
            target_plane="P30" if "P30" in available_planes else "P00",
            estimated_duration=BASE_DURATION[HopType.COMPUTE],
            predicted_success=self._predict_success(HopType.COMPUTE, goal.domain),
            requires=[idx - 1],
            fallback=self._get_fallback(HopType.COMPUTE),
        )]

    # ═══════════════════════════════════════════════════════════════════════
    # LEARNED SUCCESS PREDICTION
    # ═══════════════════════════════════════════════════════════════════════

    def _predict_success(self, hop_type: HopType, domain: GoalDomain) -> float:
        """
        Predict success from execution history, not static values.

        Uses base rates adjusted by learned domain.hoptype modifiers.
        Over time, predictions converge to actual execution outcomes.
        """
        base = BASE_SUCCESS.get(hop_type, 0.7)

        # Learned modifier keyed by domain.hoptype for fine-grained learning
        key = f"{domain.value}.{hop_type.value}"
        modifier = self._success_modifiers.get(key, 0.0)

        return max(0.1, min(0.99, base + modifier))

    # ═══════════════════════════════════════════════════════════════════════
    # LEARNING FROM OUTCOMES
    # ═══════════════════════════════════════════════════════════════════════

    def record_plan_outcome(self,
                            plan: ExecutionPlan,
                            actual_success: float,
                            actual_duration: float):
        """
        Record plan outcome to improve future predictions.

        Updates success modifiers keyed by domain.hoptype for
        fine-grained per-domain, per-hoptype learning.

        Args:
            plan: The executed plan
            actual_success: What actually happened (0.0-1.0)
            actual_duration: How long it actually took
        """
        domain_key = plan.goal.domain.value

        # Record for history
        self._plan_history.append({
            "plan_id": plan.id,
            "domain": domain_key,
            "predicted_success": plan.predicted_success_rate,
            "actual_success": actual_success,
            "predicted_duration": plan.total_estimated_duration,
            "actual_duration": actual_duration,
            "hop_count": plan.hop_count,
            "hop_types": [h.hop_type.value for h in plan.hop_chain],
            "timestamp": time.time(),
        })

        # Global prediction error
        error = actual_success - plan.predicted_success_rate

        # Update modifiers keyed by domain.hoptype
        # This learns: "DIAGNOSIS.query is more reliable than predicted"
        # or "EXPLORATION.wait fails more than expected"
        for hop in plan.hop_chain:
            key = f"{domain_key}.{hop.hop_type.value}"
            current = self._success_modifiers.get(key, 0.0)
            # Exponential moving average — slow learning (0.9/0.1)
            self._success_modifiers[key] = current * 0.9 + error * 0.1

        # Also update the legacy domain-level modifier for backward compat
        current = self._success_modifiers.get(domain_key, 0.0)
        self._success_modifiers[domain_key] = current * 0.9 + error * 0.1

        # Trim history
        if len(self._plan_history) > 100:
            self._plan_history = self._plan_history[-100:]

    # ═══════════════════════════════════════════════════════════════════════
    # CHAIN SUCCESS CALCULATION — kept from original, works correctly
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_chain_success(self, hop_chain: List[HopStep]) -> float:
        """
        Calculate overall chain success probability.

        For sequential hops: multiply probabilities
        Accounts for partial recovery via fallbacks
        """
        if not hop_chain:
            return 0.0

        # Base: product of all probabilities
        base_success = 1.0
        for hop in hop_chain:
            base_success *= hop.predicted_success

        # Boost for fallbacks (each fallback adds recovery chance)
        fallback_count = sum(1 for h in hop_chain if h.fallback)
        recovery_factor = 1 + (fallback_count * 0.05)  # 5% boost per fallback

        return min(1.0, base_success * recovery_factor)

    def _adjust_for_state(self,
                          predicted: float,
                          state: Dict[str, Any]) -> float:
        """Adjust prediction based on system state."""
        modifier = 1.0

        # Consciousness loop running?
        if not state.get("consciousness_running", True):
            modifier *= 0.5  # Major penalty

        # High pain levels?
        pain_level = state.get("max_pain", 0.0)
        if pain_level > 0.7:
            modifier *= 0.8  # Pain impacts performance

        # System load?
        load = state.get("system_load", 0.0)
        if load > 0.8:
            modifier *= 0.9  # High load penalty

        return predicted * modifier

    # ═══════════════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════════════

    def _get_fallback(self, hop_type: HopType) -> Optional[str]:
        """Get fallback action for hop type."""
        fallbacks = {
            HopType.QUERY: "Retry with timeout",
            HopType.PUBLISH: "Queue for later delivery",
            HopType.SUBSCRIBE: "Use polling instead",
            HopType.COMPUTE: "Simplify computation",
            HopType.WAIT: "Timeout and proceed",
            HopType.REPAIR: "Escalate to mentor",
        }
        return fallbacks.get(hop_type)

    def _create_fallback_hop(self) -> HopStep:
        """Create minimal fallback hop."""
        return HopStep(
            index=0,
            hop_type=HopType.QUERY,
            description="Verify existence",
            target_plane="P00",
            estimated_duration=0.5,
            predicted_success=0.95,
            requires=[],
            fallback="Log failure",
        )

    def status(self) -> Dict[str, Any]:
        """Get planner status."""
        return {
            "plans_created": len(self._plan_history),
            "success_modifiers": dict(self._success_modifiers),
            "recent_accuracy": self._calculate_recent_accuracy(),
            "mode": "dynamic",
        }

    def _calculate_recent_accuracy(self) -> float:
        """How accurate were recent predictions?"""
        if len(self._plan_history) < 3:
            return 0.5  # Unknown

        recent = self._plan_history[-10:]
        errors = [
            abs(p["predicted_success"] - p["actual_success"])
            for p in recent
        ]

        avg_error = sum(errors) / len(errors)
        return 1.0 - avg_error  # Higher = more accurate
