"""
GoalProposer - Generates goals from LIVE system state.

Part of Dr. Zero architecture: tight feedback loop between
GoalProposer, Planner, and Executor to find the "learning edge".

Goals are NOT hardcoded — they emerge from observing the system:
- Directory health → DIAGNOSIS goals
- Postal traffic → COORDINATION goals
- Pain signals → COMMUNICATION goals
- Random exploration → EXPLORATION goals

The system itself tells us what to learn about.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from enum import Enum
import time
import random


class GoalDomain(Enum):
    """Domains where goals can be proposed."""
    INTROSPECTION = "introspection"      # Understanding self/system
    COMMUNICATION = "communication"      # Messaging, reporting
    DIAGNOSIS = "diagnosis"              # Health checks, repairs
    MENTORSHIP = "mentorship"            # Guiding children
    EXPLORATION = "exploration"          # Learning new things
    COORDINATION = "coordination"        # Multi-fairy tasks


@dataclass
class GoalSeed:
    """
    Raw goal candidate from system probe.

    Intermediate between live system observation and a full Goal.
    The proposer collects seeds, then selects the best one
    based on difficulty calibration.
    """
    objective: str              # What to do
    domain: GoalDomain          # Which domain
    estimated_hops: int         # Complexity 1-4
    required_planes: List[str]  # Which planes involved
    source: str                 # Where this came from ("directory", "postal", etc.)
    urgency: float              # 0-1, how pressing
    verifiable: str             # How to verify success
    context_key: str            # Key into execution context for relevant data


@dataclass
class Goal:
    """
    A proposed goal with difficulty calibration.

    The key insight: goals should be challenging but achievable.
    Too easy = no learning. Too hard = frustration.
    """
    objective: str
    domain: GoalDomain
    estimated_hops: int  # 1-4, complexity estimate
    required_planes: List[str]  # Which planes must be involved
    timeout_seconds: float  # How long before giving up
    success_criteria: str  # Verifiable condition

    # Calibration metadata
    difficulty: float = 0.5  # 0.0 (trivial) to 1.0 (impossible)
    confidence: float = 0.5  # How sure we are about difficulty estimate

    # Identity - WHO is learning/proposing this goal
    actor_name: str = "unknown"  # The fairy running this cognition loop

    # Source tracking
    source: str = "probe"  # Where the goal seed came from

    # Tracking
    id: str = field(default_factory=lambda: f"goal_{int(time.time()*1000)}")
    proposed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "objective": self.objective,
            "domain": self.domain.value,
            "estimated_hops": self.estimated_hops,
            "required_planes": self.required_planes,
            "timeout_seconds": self.timeout_seconds,
            "success_criteria": self.success_criteria,
            "difficulty": self.difficulty,
            "confidence": self.confidence,
            "actor_name": self.actor_name,
            "source": self.source,
            "proposed_at": self.proposed_at,
        }


@dataclass
class GoalHistory:
    """Tracks goal outcomes to calibrate future proposals."""
    goal_id: str
    domain: GoalDomain
    estimated_hops: int
    actual_hops: int
    difficulty: float
    success: str  # "full", "partial", "none"
    duration: float
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM PROBE — Observes live state to generate goal seeds
# ═══════════════════════════════════════════════════════════════════════════

class SystemProbe:
    """
    Queries live system state to find what needs attention.

    Each probe method checks one aspect of the system and returns
    GoalSeeds if it finds something worth investigating.
    """

    def probe(self, context: Dict[str, Any]) -> List[GoalSeed]:
        """Return prioritized list of goal seeds from live state."""
        seeds = []
        seeds.extend(self._probe_directory(context))
        seeds.extend(self._probe_postal(context))
        seeds.extend(self._probe_health(context))
        seeds.extend(self._probe_pain(context))
        seeds.extend(self._probe_serendipity(context))
        return seeds

    def _probe_directory(self, ctx: Dict[str, Any]) -> List[GoalSeed]:
        """Check directory for failed/dead/degraded fairies."""
        seeds = []
        directory = ctx.get("directory")
        if not directory:
            return seeds

        # Check for failed fairies
        failed = ctx.get("failed_fairies", [])
        if failed:
            fairy_name = failed[0] if isinstance(failed[0], str) else str(failed[0])
            seeds.append(GoalSeed(
                objective=f"Diagnose failed fairy: {fairy_name}",
                domain=GoalDomain.DIAGNOSIS,
                estimated_hops=2,
                required_planes=["P00"],
                source="directory",
                urgency=0.8,
                verifiable=f"Get status and error info for {fairy_name}",
                context_key="failed_fairies",
            ))

        # Check for silent/dead fairies
        dead = ctx.get("dead_fairies", [])
        if dead:
            fairy_name = dead[0] if isinstance(dead[0], str) else str(dead[0])
            seeds.append(GoalSeed(
                objective=f"Investigate silent fairy: {fairy_name}",
                domain=GoalDomain.DIAGNOSIS,
                estimated_hops=2,
                required_planes=["P00"],
                source="directory",
                urgency=0.6,
                verifiable=f"Determine if {fairy_name} is responsive",
                context_key="dead_fairies",
            ))

        # Check system health percentage
        health = ctx.get("system_health", {})
        health_pct = health.get("health_percent", 100)
        if health_pct < 90:
            seeds.append(GoalSeed(
                objective=f"Assess system health ({health_pct:.0f}%)",
                domain=GoalDomain.DIAGNOSIS,
                estimated_hops=3,
                required_planes=["P00", "P30"],
                source="directory",
                urgency=0.7,
                verifiable=f"Identify degraded components and severity",
                context_key="system_health",
            ))

        # Healthy system — rotate between varied introspective goals
        fairy_count = ctx.get("fairy_count", 0)
        if fairy_count > 0 and not failed and not dead:
            # Rotate through different healthy-system goals to avoid monotony
            tick = ctx.get("tick_count", int(time.time()))
            variant = tick % 6
            if variant == 0:
                seeds.append(GoalSeed(
                    objective=f"Survey postal traffic patterns",
                    domain=GoalDomain.COORDINATION,
                    estimated_hops=2,
                    required_planes=["P00"],
                    source="directory",
                    urgency=0.2,
                    verifiable="Identify busiest postal topics",
                    context_key="postal_stats",
                ))
            elif variant == 1:
                planes = ctx.get("planes", [])
                plane = random.choice(planes) if planes else "P30"
                seeds.append(GoalSeed(
                    objective=f"Profile fairies in {plane}",
                    domain=GoalDomain.EXPLORATION,
                    estimated_hops=2,
                    required_planes=["P00", plane],
                    source="directory",
                    urgency=0.2,
                    verifiable=f"List fairy names and status in {plane}",
                    context_key="serendipity_plane",
                ))
            elif variant == 2:
                seeds.append(GoalSeed(
                    objective=f"Assess system load and resource health",
                    domain=GoalDomain.DIAGNOSIS,
                    estimated_hops=2,
                    required_planes=["P00", "P30"],
                    source="directory",
                    urgency=0.2,
                    verifiable="Report load level and any bottlenecks",
                    context_key="system_load",
                ))
            elif variant == 3:
                seeds.append(GoalSeed(
                    objective=f"Survey fairy distribution across planes",
                    domain=GoalDomain.EXPLORATION,
                    estimated_hops=2,
                    required_planes=["P00"],
                    source="directory",
                    urgency=0.2,
                    verifiable="Count fairies per plane",
                    context_key="serendipity_distribution",
                ))
            elif variant == 4:
                seeds.append(GoalSeed(
                    objective=f"Check consciousness loop vitals",
                    domain=GoalDomain.DIAGNOSIS,
                    estimated_hops=2,
                    required_planes=["P00", "P30"],
                    source="directory",
                    urgency=0.3,
                    verifiable="Report beat rate, collision count, stream health",
                    context_key="consciousness_running",
                ))
            else:
                seeds.append(GoalSeed(
                    objective=f"Verify {fairy_count} fairies healthy",
                    domain=GoalDomain.INTROSPECTION,
                    estimated_hops=1,
                    required_planes=["P00"],
                    source="directory",
                    urgency=0.1,
                    verifiable=f"Confirm all {fairy_count} fairies are awake",
                    context_key="fairy_count",
                ))

        return seeds

    def _probe_postal(self, ctx: Dict[str, Any]) -> List[GoalSeed]:
        """Check postal system for anomalies."""
        seeds = []
        fabric = ctx.get("fabric")
        if not fabric:
            return seeds

        try:
            stats = fabric.stats() if hasattr(fabric, 'stats') else None
            if not stats:
                return seeds

            # Check for topics with no subscribers (orphans)
            topics = stats.get("topics", {})
            if isinstance(topics, dict):
                orphans = [t for t, info in topics.items()
                           if isinstance(info, dict) and info.get("subscribers", 1) == 0]
                if orphans:
                    topic = orphans[0]
                    seeds.append(GoalSeed(
                        objective=f"Investigate orphan topic: {topic[:30]}",
                        domain=GoalDomain.COORDINATION,
                        estimated_hops=2,
                        required_planes=["P00"],
                        source="postal",
                        urgency=0.4,
                        verifiable=f"Determine if topic '{topic[:30]}' should have subscribers",
                        context_key="postal_orphans",
                    ))

            # Check total message count for activity
            total_msgs = stats.get("total_messages", 0)
            if total_msgs > 0:
                seeds.append(GoalSeed(
                    objective=f"Survey postal traffic ({total_msgs} msgs)",
                    domain=GoalDomain.COORDINATION,
                    estimated_hops=1,
                    required_planes=["P00"],
                    source="postal",
                    urgency=0.2,
                    verifiable=f"Get topic list and subscriber counts",
                    context_key="postal_stats",
                ))

        except Exception:
            pass  # Postal not available — skip

        return seeds

    def _probe_health(self, ctx: Dict[str, Any]) -> List[GoalSeed]:
        """Check system health indicators."""
        seeds = []

        # Consciousness loop running?
        if not ctx.get("consciousness_running", True):
            seeds.append(GoalSeed(
                objective="Alert: consciousness loop not running",
                domain=GoalDomain.DIAGNOSIS,
                estimated_hops=2,
                required_planes=["P00", "P30"],
                source="health",
                urgency=0.9,
                verifiable="Verify consciousness loop state",
                context_key="consciousness_running",
            ))

        # System load high?
        load = ctx.get("system_load", 0.0)
        if load > 0.7:
            seeds.append(GoalSeed(
                objective=f"Assess system load spike ({load:.1%})",
                domain=GoalDomain.DIAGNOSIS,
                estimated_hops=1,
                required_planes=["P00"],
                source="health",
                urgency=0.5,
                verifiable=f"Identify load sources and assess severity",
                context_key="system_load",
            ))

        # Memory not available?
        if not ctx.get("memory_available", True):
            seeds.append(GoalSeed(
                objective="Check memory system availability",
                domain=GoalDomain.DIAGNOSIS,
                estimated_hops=2,
                required_planes=["P00", "P10"],
                source="health",
                urgency=0.6,
                verifiable="Verify memory fairy connectivity",
                context_key="memory_available",
            ))

        # Gates not active?
        if not ctx.get("gates_active", True):
            seeds.append(GoalSeed(
                objective="Check gate system wiring",
                domain=GoalDomain.COORDINATION,
                estimated_hops=2,
                required_planes=["P00", "P30"],
                source="health",
                urgency=0.5,
                verifiable="Verify three gates are active and routing",
                context_key="gates_active",
            ))

        return seeds

    def _probe_pain(self, ctx: Dict[str, Any]) -> List[GoalSeed]:
        """Check pain drives for unmet needs."""
        seeds = []
        pain_drives = ctx.get("pain_drives", {})

        for drive_name, level in pain_drives.items():
            if level > 0.3:
                # Map pain drives to appropriate domains
                domain = GoalDomain.COMMUNICATION
                if "isolation" in drive_name:
                    objective = f"Address isolation pain ({level:.1f})"
                    domain = GoalDomain.COMMUNICATION
                elif "confusion" in drive_name:
                    objective = f"Resolve confusion state ({level:.1f})"
                    domain = GoalDomain.INTROSPECTION
                elif "depletion" in drive_name:
                    objective = f"Address depletion ({level:.1f})"
                    domain = GoalDomain.DIAGNOSIS
                else:
                    objective = f"Investigate pain: {drive_name} ({level:.1f})"

                seeds.append(GoalSeed(
                    objective=objective,
                    domain=domain,
                    estimated_hops=3,
                    required_planes=["P00", "P30"],
                    source="pain",
                    urgency=min(1.0, level + 0.2),
                    verifiable=f"Reduce {drive_name} pain below 0.3",
                    context_key=f"pain_{drive_name}",
                ))

        return seeds

    def _probe_serendipity(self, ctx: Dict[str, Any]) -> List[GoalSeed]:
        """
        Generate an exploration goal from live data.

        Serendipity probability scales with system health:
        - Healthy system (no failed/dead): 50% chance → explore often
        - Problems exist: 20% chance → focus on issues first

        Serendipity prevents the system from only doing routine work —
        it ensures curiosity-driven exploration, especially when healthy.
        """
        # Higher serendipity when healthy — boredom drives curiosity
        has_problems = bool(ctx.get("failed_fairies") or ctx.get("dead_fairies"))
        serendipity_chance = 0.2 if has_problems else 0.5  # 20% when busy, 50% when healthy
        if random.random() > serendipity_chance:
            return []

        directory = ctx.get("directory")
        if not directory:
            return [self._generic_serendipity()]

        strategies = []

        # Strategy 1: Explore a random plane
        planes = ctx.get("planes", [])
        if planes:
            plane = random.choice(planes)
            try:
                fairies = directory.find_by_plane(plane)
                strategies.append(GoalSeed(
                    objective=f"Map {len(fairies)} fairies in {plane}",
                    domain=GoalDomain.EXPLORATION,
                    estimated_hops=2,
                    required_planes=["P00", plane],
                    source="serendipity",
                    urgency=0.3,
                    verifiable=f"List all fairy names and statuses in {plane}",
                    context_key="serendipity_plane",
                ))
            except Exception:
                pass

        # Strategy 2: Explore a random capability
        try:
            caps = directory.list_capabilities()
            if caps:
                cap = random.choice(caps)
                strategies.append(GoalSeed(
                    objective=f"Find fairies with capability '{cap}'",
                    domain=GoalDomain.EXPLORATION,
                    estimated_hops=1,
                    required_planes=["P00"],
                    source="serendipity",
                    urgency=0.2,
                    verifiable=f"Return list of fairy names with '{cap}'",
                    context_key="serendipity_cap",
                ))
        except Exception:
            pass

        # Strategy 3: Check a random peer fairy's status
        try:
            all_fairies = directory.list_names()
            if all_fairies:
                peer = random.choice(all_fairies)
                strategies.append(GoalSeed(
                    objective=f"Check status of {peer}",
                    domain=GoalDomain.INTROSPECTION,
                    estimated_hops=1,
                    required_planes=["P00"],
                    source="serendipity",
                    urgency=0.2,
                    verifiable=f"Get status and last_seen for {peer}",
                    context_key="serendipity_peer",
                ))
        except Exception:
            pass

        # Strategy 4: Count fairies per plane
        if planes and len(planes) > 1:
            strategies.append(GoalSeed(
                objective=f"Survey fairy distribution across {len(planes)} planes",
                domain=GoalDomain.EXPLORATION,
                estimated_hops=2,
                required_planes=["P00"],
                source="serendipity",
                urgency=0.2,
                verifiable="Get fairy count per plane",
                context_key="serendipity_distribution",
            ))

        return [random.choice(strategies)] if strategies else [self._generic_serendipity()]

    def _generic_serendipity(self) -> GoalSeed:
        """Fallback serendipity when no directory available — randomized."""
        fallbacks = [
            GoalSeed(
                objective="Verify own existence in directory",
                domain=GoalDomain.INTROSPECTION,
                estimated_hops=1,
                required_planes=["P00"],
                source="serendipity",
                urgency=0.1,
                verifiable="Confirm registration status",
                context_key="self_check",
            ),
            GoalSeed(
                objective="Measure own response latency",
                domain=GoalDomain.INTROSPECTION,
                estimated_hops=1,
                required_planes=["P00"],
                source="serendipity",
                urgency=0.2,
                verifiable="Time a self-ping round-trip",
                context_key="self_check",
            ),
            GoalSeed(
                objective="Inventory available postal topics",
                domain=GoalDomain.COORDINATION,
                estimated_hops=2,
                required_planes=["P00"],
                source="serendipity",
                urgency=0.2,
                verifiable="List active topics and subscriber counts",
                context_key="postal_stats",
            ),
            GoalSeed(
                objective="Reflect on recent cognition outcomes",
                domain=GoalDomain.INTROSPECTION,
                estimated_hops=1,
                required_planes=["P00"],
                source="serendipity",
                urgency=0.1,
                verifiable="Summarize last 5 cycle results",
                context_key="self_check",
            ),
        ]
        return random.choice(fallbacks)


# ═══════════════════════════════════════════════════════════════════════════
# GOAL PROPOSER
# ═══════════════════════════════════════════════════════════════════════════

class GoalProposer:
    """
    Generates goals calibrated to current capability.

    Uses SystemProbe for dynamic goals from live state,
    and history of past attempts to find the "learning edge" -
    goals that are challenging but achievable (partial success zone).
    """

    def __init__(self, max_history: int = 100):
        self._probe = SystemProbe()
        self._history: List[GoalHistory] = []
        self._max_history = max_history
        self._domain_performance: Dict[GoalDomain, Dict[str, float]] = {
            domain: {"success_rate": 0.5, "avg_difficulty": 0.5}
            for domain in GoalDomain
        }
        self._recent_objectives: List[str] = []  # Track recent goals for diversity

    def propose(self,
                available_planes: Set[str],
                preferred_domain: Optional[GoalDomain] = None,
                target_difficulty: Optional[float] = None,
                actor_name: str = "unknown",
                context: Optional[Dict[str, Any]] = None) -> Goal:
        """
        Propose a goal from live system state, calibrated to learning edge.

        Args:
            available_planes: Which planes are currently accessible
            preferred_domain: Bias toward this domain if specified
            target_difficulty: Aim for this difficulty (0.0-1.0)
            actor_name: The fairy running this cognition loop
            context: Live system state (directory, fabric, health, etc.)

        Returns:
            A Goal calibrated to the learning edge
        """
        # Determine target difficulty from history if not specified
        if target_difficulty is None:
            target_difficulty = self._calculate_learning_edge()

        # Probe live system for goal seeds
        seeds = self._probe.probe(context or {})

        # Filter by available planes
        seeds = [s for s in seeds
                 if all(p in available_planes for p in s.required_planes)]

        # Filter by preferred domain if specified
        if preferred_domain:
            domain_seeds = [s for s in seeds if s.domain == preferred_domain]
            if domain_seeds:
                seeds = domain_seeds

        # Avoid repeating recent goals — stronger diversity
        if self._recent_objectives and seeds:
            recent = self._recent_objectives[-5:]

            def _is_diverse(seed: GoalSeed) -> bool:
                """Check seed isn't too similar to recent objectives."""
                obj = seed.objective
                if obj in recent:
                    return False
                # Also check prefix overlap (e.g. "Address isolation" repeated)
                prefix = obj[:25].lower()
                for prev in recent:
                    if prev[:25].lower() == prefix:
                        return False
                return True

            diverse = [s for s in seeds if _is_diverse(s)]
            if diverse:
                seeds = diverse

        # If no seeds from probes, force serendipity
        if not seeds:
            seeds = self._probe._probe_serendipity(context or {})
            # Force serendipity even if the 20% roll failed
            if not seeds:
                seeds = [self._probe._generic_serendipity()]

        # Still nothing? Use existence check fallback
        if not seeds:
            return self._create_fallback_goal(actor_name)

        # Select by difficulty match (closest to learning edge)
        seed = self._select_seed_by_difficulty(seeds, target_difficulty)

        # Track for diversity
        self._recent_objectives.append(seed.objective)
        if len(self._recent_objectives) > 10:
            self._recent_objectives = self._recent_objectives[-10:]

        # Convert to Goal with calibrated metadata
        return self._seed_to_goal(seed, actor_name, target_difficulty)

    def _seed_to_goal(self, seed: GoalSeed, actor_name: str,
                      target_difficulty: float) -> Goal:
        """Convert a GoalSeed into a full Goal with calibrated metadata."""
        difficulty = self._estimate_difficulty(seed.domain, seed.estimated_hops)
        confidence = self._estimate_confidence(seed.domain)
        timeout = self._calculate_timeout(seed.estimated_hops, difficulty)

        return Goal(
            objective=seed.objective,
            domain=seed.domain,
            estimated_hops=seed.estimated_hops,
            required_planes=seed.required_planes,
            timeout_seconds=timeout,
            success_criteria=seed.verifiable,
            difficulty=difficulty,
            confidence=confidence,
            actor_name=actor_name,
            source=seed.source,
        )

    def _select_seed_by_difficulty(self, seeds: List[GoalSeed],
                                   target: float) -> GoalSeed:
        """Select seed closest to target difficulty."""
        def seed_difficulty(seed: GoalSeed) -> float:
            """Estimate difficulty from hops and urgency."""
            base = (seed.estimated_hops - 1) / 3  # 1 hop = 0.0, 4 hops = 1.0
            # Urgent seeds get slight difficulty reduction (we've seen them before)
            urgency_adj = seed.urgency * 0.1
            return base - urgency_adj

        return min(seeds, key=lambda s: abs(seed_difficulty(s) - target))

    def record_outcome(self,
                       goal: Goal,
                       success: str,
                       actual_hops: int,
                       duration: float):
        """
        Record goal outcome to improve future calibration.

        Args:
            goal: The attempted goal
            success: "full", "partial", or "none"
            actual_hops: How many hops actually needed
            duration: How long it took
        """
        history = GoalHistory(
            goal_id=goal.id,
            domain=goal.domain,
            estimated_hops=goal.estimated_hops,
            actual_hops=actual_hops,
            difficulty=goal.difficulty,
            success=success,
            duration=duration,
        )

        self._history.append(history)

        # Trim old history
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Update domain performance
        self._update_domain_stats(goal.domain)

    def _calculate_learning_edge(self) -> float:
        """
        Find the difficulty level where learning happens.

        The learning edge is where we get partial successes -
        challenging enough to learn, achievable enough to succeed.
        """
        if len(self._history) < 5:
            return 0.5  # Default to middle

        # Look at recent history
        recent = self._history[-20:]

        # Find difficulty where partial success happens most
        partial_diffs = [h.difficulty for h in recent if h.success == "partial"]
        if partial_diffs:
            return sum(partial_diffs) / len(partial_diffs)

        # No partial successes - look at boundary
        full_diffs = [h.difficulty for h in recent if h.success == "full"]
        none_diffs = [h.difficulty for h in recent if h.success == "none"]

        if full_diffs and none_diffs:
            # Learning edge is between success and failure
            max_success = max(full_diffs)
            min_failure = min(none_diffs)
            return (max_success + min_failure) / 2

        if full_diffs:
            # All successes - push harder
            return min(1.0, max(full_diffs) + 0.1)

        if none_diffs:
            # All failures - ease off
            return max(0.0, min(none_diffs) - 0.1)

        return 0.5

    def _estimate_difficulty(self, domain: GoalDomain, hops: int) -> float:
        """Estimate difficulty based on domain history and hop count."""
        base = (hops - 1) / 3  # Hops contribute

        # Adjust based on domain performance
        perf = self._domain_performance[domain]
        domain_modifier = 1 - perf["success_rate"]  # Lower success = harder

        return min(1.0, max(0.0, base * 0.7 + domain_modifier * 0.3))

    def _estimate_confidence(self, domain: GoalDomain) -> float:
        """How confident are we in our difficulty estimate?"""
        domain_history = [h for h in self._history if h.domain == domain]

        if len(domain_history) < 3:
            return 0.3  # Low confidence
        if len(domain_history) < 10:
            return 0.5  # Medium confidence
        return 0.8  # High confidence

    def _calculate_timeout(self, hops: int, difficulty: float) -> float:
        """Calculate appropriate timeout for goal."""
        base_timeout = 5.0  # 5 seconds base
        hop_factor = hops * 3.0  # 3 seconds per hop
        difficulty_factor = 1 + difficulty  # Harder = more time

        return base_timeout + (hop_factor * difficulty_factor)

    def _update_domain_stats(self, domain: GoalDomain):
        """Update performance stats for domain."""
        domain_history = [h for h in self._history if h.domain == domain]

        if not domain_history:
            return

        recent = domain_history[-10:]

        # Calculate success rate (partial = 0.5, full = 1.0)
        success_scores = {
            "full": 1.0,
            "partial": 0.5,
            "none": 0.0,
        }
        total = sum(success_scores[h.success] for h in recent)

        self._domain_performance[domain] = {
            "success_rate": total / len(recent),
            "avg_difficulty": sum(h.difficulty for h in recent) / len(recent),
        }

    def _create_fallback_goal(self, actor_name: str = "unknown") -> Goal:
        """Create simplest possible goal when nothing else works."""
        return Goal(
            objective="Verify own existence",
            domain=GoalDomain.INTROSPECTION,
            estimated_hops=1,
            required_planes=["P00"],
            timeout_seconds=5.0,
            success_criteria="Confirm registration in directory",
            difficulty=0.1,
            confidence=0.9,
            actor_name=actor_name,
            source="fallback",
        )

    def status(self) -> Dict[str, Any]:
        """Get proposer status."""
        return {
            "history_count": len(self._history),
            "domain_performance": {
                d.value: p for d, p in self._domain_performance.items()
            },
            "learning_edge": self._calculate_learning_edge(),
            "recent_objectives": self._recent_objectives[-5:],
            "mode": "dynamic",
        }
