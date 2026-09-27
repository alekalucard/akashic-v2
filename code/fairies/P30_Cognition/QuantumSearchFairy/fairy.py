"""
Quantum Search Fairy - Parallel Dimensional Exploration

"The One Becomes Many, The Many Become One"

Inspired by "Next" (2007) — Nicolas Cage sees all futures simultaneously,
explores them in parallel, then collapses to the one path that works.

This fairy implements the Fork-Explore-Collapse pattern:
1. FORK: An intent splits into N lightweight dimensional copies
2. EXPLORE: Each copy runs a different strategy in parallel
3. COLLAPSE: The ProbabilityOracle scores all results, picks the best

Instead of trying strategies one at a time (O(N) serial),
we try them all simultaneously (O(1) wall-clock, N parallel).

The system learns which strategies work for which problems
via the SatisfactionTracker feedback loop. Over time,
the fork allocations shift — developing intuition.

Plane: P30 (Cognition)
Channel: quantum_search

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import time
import math
import uuid
import threading
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Set
from collections import deque
from concurrent.futures import Future, as_completed, TimeoutError as FuturesTimeout

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from infrastructure.spellchain.spell import Spell, SpellType, SpellStatus


# ============================================================================
# Phase 1: Core Dataclasses
# ============================================================================


class BranchStatus(Enum):
    """Lifecycle of a quantum branch."""
    PENDING = "pending"        # Created but not yet dispatched
    EXPLORING = "exploring"    # Actively running a strategy
    FOUND = "found"            # Strategy produced a result
    FAILED = "failed"          # Strategy failed or errored
    CANCELLED = "cancelled"    # Collapsed away by oracle
    TIMEOUT = "timeout"        # Exceeded time budget


class StrategyType(Enum):
    """Built-in exploration strategies."""
    MEMORY_RECALL = "memory_recall"
    ASSOCIATION_WALK = "association_walk"
    INFERENCE = "inference"
    PATTERN_MATCH = "pattern_match"
    SIMULATION = "simulation"
    ORACLE_CONSULT = "oracle_consult"
    SERENDIPITY = "serendipity"


@dataclass
class SearchStrategy:
    """A specific approach to explore.

    Each strategy represents a different way to answer the same question.
    They're lightweight — just configuration, not full agent state.
    """
    name: str                       # Human-readable name
    strategy_type: StrategyType     # Which built-in strategy
    params: Dict[str, Any] = field(default_factory=dict)
    max_time: float = 5.0           # Time budget for this branch (seconds)
    max_cost: float = 1.0           # Resource budget (abstract units)
    weight: float = 1.0             # How much to weight this strategy in allocation
    description: str = ""           # What this strategy does


@dataclass
class QuantumBranch:
    """One dimensional copy exploring one strategy.

    This is a lightweight structure — we don't clone an entire fairy.
    We clone the INTENT and give each copy a different strategy.
    The branch tracks its lifecycle from dispatch to result.
    """
    branch_id: str = field(default_factory=lambda: f"qb_{uuid.uuid4().hex[:10]}")
    search_id: str = ""             # Parent search this belongs to
    strategy: SearchStrategy = field(default_factory=SearchStrategy)
    state_snapshot: Dict[str, Any] = field(default_factory=dict)
    status: BranchStatus = BranchStatus.PENDING
    result: Any = None
    confidence: float = 0.0         # Self-assessed confidence (0-1)
    cost: float = 0.0               # Resources consumed
    started_at: float = 0.0
    completed_at: float = 0.0
    error: Optional[str] = None
    depth: int = 0                  # Recursion depth (0 = top level)
    parent_branch_id: Optional[str] = None  # For sub-branching

    @property
    def elapsed(self) -> float:
        if self.started_at <= 0:
            return 0.0
        end = self.completed_at if self.completed_at > 0 else time.time()
        return end - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "search_id": self.search_id,
            "strategy": self.strategy.name,
            "status": self.status.value,
            "confidence": round(self.confidence, 3),
            "cost": round(self.cost, 3),
            "elapsed": round(self.elapsed, 3),
            "depth": self.depth,
            "error": self.error,
        }


@dataclass
class QuantumSearch:
    """A complete search operation — fork, explore, collapse.

    Tracks the full lifecycle from intent to result.
    """
    search_id: str = field(default_factory=lambda: f"qs_{uuid.uuid4().hex[:10]}")
    intent: str = ""                # What we're searching for
    context: Dict[str, Any] = field(default_factory=dict)
    branches: List[QuantumBranch] = field(default_factory=list)
    status: str = "pending"         # pending, exploring, collapsed, failed
    started_at: float = 0.0
    collapsed_at: float = 0.0
    winner: Optional[QuantumBranch] = None
    total_cost: float = 0.0
    source_drive: str = ""          # What drive triggered this search
    source_topic: str = ""          # What postal topic triggered it
    depth: int = 0                  # Search recursion depth

    @property
    def elapsed(self) -> float:
        if self.started_at <= 0:
            return 0.0
        end = self.collapsed_at if self.collapsed_at > 0 else time.time()
        return end - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "search_id": self.search_id,
            "intent": self.intent,
            "status": self.status,
            "branches": len(self.branches),
            "elapsed": round(self.elapsed, 3),
            "total_cost": round(self.total_cost, 3),
            "winner": self.winner.to_dict() if self.winner else None,
            "depth": self.depth,
        }


# ============================================================================
# Phase 2: Strategy Registry
# ============================================================================


# Default strategies available to every search
DEFAULT_STRATEGIES: List[SearchStrategy] = [
    SearchStrategy(
        name="memory_recall",
        strategy_type=StrategyType.MEMORY_RECALL,
        max_time=3.0,
        max_cost=0.2,
        weight=1.5,  # Slightly favor — memory is fast and reliable
        description="Search SRM for relevant past experiences",
    ),
    SearchStrategy(
        name="association_walk",
        strategy_type=StrategyType.ASSOCIATION_WALK,
        max_time=3.0,
        max_cost=0.3,
        weight=1.2,
        description="Walk the AssociationCortex graph from seed concepts",
    ),
    SearchStrategy(
        name="pattern_match",
        strategy_type=StrategyType.PATTERN_MATCH,
        max_time=2.0,
        max_cost=0.1,
        weight=1.0,
        description="Search for literal patterns in codebase/data",
    ),
    SearchStrategy(
        name="oracle_consult",
        strategy_type=StrategyType.ORACLE_CONSULT,
        max_time=2.0,
        max_cost=0.2,
        weight=0.8,
        description="Ask the ProbabilityOracle for probabilistic guidance",
    ),
    SearchStrategy(
        name="serendipity",
        strategy_type=StrategyType.SERENDIPITY,
        max_time=2.0,
        max_cost=0.1,
        weight=0.5,  # Low default — but sometimes finds gold
        description="Random exploration — break out of local optima",
    ),
]


# ============================================================================
# Phase 2: The Exploration Spell
# ============================================================================


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload dict from message (handles TensorEnvelope)."""
    if hasattr(message, 'payload'):
        payload = message.payload
        return dict(payload) if isinstance(payload, dict) else {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    return {"raw": message}


def _make_exploration_spell(
    branch: QuantumBranch,
    fairy_ref: "QuantumSearchFairy",
) -> Spell:
    """Create a spell that explores one strategy branch.

    The spell's HOW function is a closure that captures the branch,
    strategy, and fairy reference. It executes the strategy and
    writes results back to the branch.
    """

    def _explore(spell: Spell) -> Any:
        """Execute the strategy within time/cost budget."""
        branch.started_at = time.time()
        branch.status = BranchStatus.EXPLORING
        strategy = branch.strategy
        snapshot = branch.state_snapshot

        try:
            # Dispatch to strategy implementation
            result, confidence = fairy_ref._execute_strategy(
                strategy, snapshot, branch
            )

            branch.result = result
            branch.confidence = confidence
            branch.status = BranchStatus.FOUND if result is not None else BranchStatus.FAILED
            branch.completed_at = time.time()

            # Early collapse signal — if high confidence, broadcast immediately
            if confidence >= fairy_ref.EARLY_COLLAPSE_THRESHOLD:
                fairy_ref._signal_early_hit(branch)

            return {
                "branch_id": branch.branch_id,
                "result": result,
                "confidence": confidence,
                "strategy": strategy.name,
                "elapsed": branch.elapsed,
            }

        except Exception as e:
            branch.status = BranchStatus.FAILED
            branch.error = str(e)
            branch.completed_at = time.time()
            return None

    return Spell(
        spell_type=SpellType.REACTION,
        who=fairy_ref.fairy_id,
        who_name=fairy_ref.ACTOR_NAME,
        who_plane="P30",
        what=f"quantum_explore:{branch.strategy.name}",
        what_intent=f"quantum_search.explore.{branch.strategy.strategy_type.value}",
        what_payload={
            "branch_id": branch.branch_id,
            "search_id": branch.search_id,
            "strategy": branch.strategy.name,
        },
        why=f"Exploring '{branch.strategy.name}' strategy for search {branch.search_id}",
        why_goal_id=branch.search_id,
        how=_explore,
        energy_required=branch.strategy.max_cost,
        when_deadline=time.time() + branch.strategy.max_time,
        when_priority=0.8,  # High priority — search is time-sensitive
        tags={"quantum_search", branch.strategy.strategy_type.value},
    )


# ============================================================================
# Phase 3 & 4: The Fairy — Orchestrator + Strategy Implementations
# ============================================================================


class QuantumSearchFairy(Fairy):
    """Orchestrates fork-explore-collapse search patterns.

    The One Becomes Many, The Many Become One.

    When a search-worthy intent arrives:
    1. FORK: Create N branches, each with a different strategy
    2. EXPLORE: Dispatch branches as spells to worker pools
    3. COLLAPSE: Score results with Oracle rails, pick the best

    The system learns which strategies work via SatisfactionTracker.
    Over time, fork allocations shift — developing intuition.
    """

    ACTOR_NAME = "QuantumSearchFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "quantum_search"

    PURPOSE = "Parallel dimensional exploration — fork intents into N strategies, collapse to best"
    MANTRA = "The one becomes many. The many become one. Each time, wiser."

    CAPABILITIES = [
        "quantum_search.fork",
        "quantum_search.collapse",
        "quantum_search.strategy_registry",
        "cognition.parallel_exploration",
    ]

    SUBSCRIPTIONS = [
        "goal.search_request",           # Explicit search requests
        "consciousness.collision",        # Collisions can spawn searches
    ]

    # ── Configuration ──────────────────────────────────────────────────
    MAX_BRANCHES = 5                  # Never fork more than N dimensions
    MAX_SEARCH_TIME = 10.0            # Total wall-clock budget (seconds)
    MAX_BRANCH_TIME = 5.0             # Per-branch time budget
    EARLY_COLLAPSE_THRESHOLD = 0.9    # Collapse immediately if confidence > this
    MAX_DEPTH = 2                     # Recursive sub-branching depth limit
    MAX_CONCURRENT_SEARCHES = 3       # Don't run more than N searches at once
    MAX_HISTORY = 50                  # How many past searches to remember
    COLLAPSE_TEMPERATURE = 0.5        # Softmax temperature for collapse selection

    def __init__(self, fabric=None):
        super().__init__(fabric)

        # Active searches
        self._active_searches: Dict[str, QuantumSearch] = {}
        self._search_lock = threading.Lock()

        # History
        self._search_history: deque = deque(maxlen=self.MAX_HISTORY)

        # Strategy registry (mutable — strategies can be added at runtime)
        self._strategies: List[SearchStrategy] = list(DEFAULT_STRATEGIES)

        # Strategy effectiveness tracking (strategy_name -> [confidence scores])
        self._strategy_scores: Dict[str, deque] = {}
        for s in self._strategies:
            self._strategy_scores[s.name] = deque(maxlen=20)

        # Stats
        self._total_searches = 0
        self._total_collapses = 0
        self._total_early_hits = 0
        self._total_branches = 0

        # Early hit signal
        self._early_hit_event = threading.Event()

    # ── Boot ───────────────────────────────────────────────────────────

    def on_boot(self) -> bool:
        """Boot the quantum search system.

        2026-03-19 DISABLED: Cortex reasoner's spread activation IS the
        parallel dimensional search. Fork-Explore-Collapse happens natively
        in the portal's graph traversal. Keeping fairy alive but dormant.
        """
        print(f"[{self.ACTOR_NAME}] DORMANT — cortex spread activation is the search")
        return True
        # --- Original boot below (disabled) ---
        if self.post:
            self.post.subscribe("goal.search_request", self._on_search_request)
            self.post.subscribe("consciousness.collision", self._on_collision)

        self.log("Booted — dimensional search ready")
        self.log(f"  Strategies: {[s.name for s in self._strategies]}")
        self.log(f"  Max branches: {self.MAX_BRANCHES}, Max time: {self.MAX_SEARCH_TIME}s")
        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def on_shutdown(self):
        """Clean shutdown — cancel active searches."""
        with self._search_lock:
            for search in self._active_searches.values():
                search.status = "cancelled"
                for branch in search.branches:
                    if branch.status == BranchStatus.EXPLORING:
                        branch.status = BranchStatus.CANCELLED
        self.log("Shutdown — all searches cancelled")

    # ── Postal Handlers ────────────────────────────────────────────────

    def _on_search_request(self, message):
        """Handle explicit search requests from any fairy.

        Expected payload:
        {
            "intent": "What to search for",
            "context": { ... optional context ... },
            "strategies": ["memory_recall", "association_walk"],  # optional filter
            "source_drive": "curiosity",  # optional
            "max_time": 8.0,  # optional override
        }
        """
        payload = _extract_payload(message)
        intent = payload.get("intent", "")
        if not intent:
            return

        # Don't queue if we're already overloaded
        if len(self._active_searches) >= self.MAX_CONCURRENT_SEARCHES:
            self.log(f"Search rejected (overloaded): {intent[:50]}")
            return

        context = payload.get("context", {})
        strategy_filter = payload.get("strategies", None)
        source_drive = payload.get("source_drive", "")
        max_time = payload.get("max_time", self.MAX_SEARCH_TIME)

        # Build state snapshot from working memory
        snapshot = self._build_snapshot(intent, context)

        # Select strategies
        strategies = self._select_strategies(intent, strategy_filter)

        # Launch the search
        self._fork_and_explore(
            intent=intent,
            snapshot=snapshot,
            strategies=strategies,
            source_drive=source_drive,
            source_topic="goal.search_request",
            max_time=max_time,
        )

    def _on_collision(self, message):
        """Optionally spawn searches from high-energy collisions.

        Only triggers if collision has high resonance + uncertainty,
        suggesting the system is grasping for something it can't find
        through normal consciousness processing.
        """
        payload = _extract_payload(message)
        resonance = payload.get("resonance", 0.0)
        uncertainty = payload.get("uncertainty", 0.0)

        # Only search if collision is high-energy AND uncertain
        if resonance < 0.7 or uncertainty < 0.5:
            return

        # Don't flood — max 1 collision-triggered search at a time
        collision_searches = [
            s for s in self._active_searches.values()
            if s.source_topic == "consciousness.collision"
        ]
        if collision_searches:
            return

        # Extract search intent from collision context
        recall_text = payload.get("recall_text", "")
        ingest_text = payload.get("ingest_text", "")
        intent = f"collision_explore: {recall_text[:40]} x {ingest_text[:40]}"

        snapshot = self._build_snapshot(intent, payload)
        strategies = self._select_strategies(intent, None)

        # Use fewer branches for collision searches (they're speculative)
        strategies = strategies[:3]

        self._fork_and_explore(
            intent=intent,
            snapshot=snapshot,
            strategies=strategies,
            source_drive="curiosity",
            source_topic="consciousness.collision",
            max_time=5.0,  # Shorter budget for speculative searches
        )

    # ── Core: Fork → Explore → Collapse ───────────────────────────────

    def _fork_and_explore(
        self,
        intent: str,
        snapshot: Dict[str, Any],
        strategies: List[SearchStrategy],
        source_drive: str = "",
        source_topic: str = "",
        max_time: float = 0.0,
        depth: int = 0,
        parent_search_id: str = "",
    ):
        """The main orchestration loop: fork, explore, collapse.

        Runs in a daemon thread to avoid blocking the postal handler.
        """
        max_time = max_time or self.MAX_SEARCH_TIME

        # Create the search
        search = QuantumSearch(
            intent=intent,
            context=snapshot,
            status="forking",
            started_at=time.time(),
            source_drive=source_drive,
            source_topic=source_topic,
            depth=depth,
        )

        with self._search_lock:
            self._active_searches[search.search_id] = search
            self._total_searches += 1

        # Run in a thread so we don't block postal
        t = threading.Thread(
            target=self._search_lifecycle,
            args=(search, strategies, snapshot, max_time),
            daemon=True,
            name=f"qsearch_{search.search_id[-8:]}",
        )
        t.start()

    def _search_lifecycle(
        self,
        search: QuantumSearch,
        strategies: List[SearchStrategy],
        snapshot: Dict[str, Any],
        max_time: float,
    ):
        """Full search lifecycle — fork, wait, collapse."""
        try:
            # ── FORK ──────────────────────────────────────────────
            self.log(f"FORK: '{search.intent[:50]}' → {len(strategies)} branches")

            branches = []
            futures: Dict[str, Future] = {}

            for strategy in strategies:
                branch = QuantumBranch(
                    search_id=search.search_id,
                    strategy=strategy,
                    state_snapshot=snapshot,
                    depth=search.depth,
                )
                branches.append(branch)
                search.branches.append(branch)
                self._total_branches += 1

            search.status = "exploring"

            # Publish fork event
            if self.post:
                self.post.publish("quantum_search.fork", {
                    "search_id": search.search_id,
                    "intent": search.intent,
                    "branch_count": len(branches),
                    "strategies": [b.strategy.name for b in branches],
                    "source": self.ACTOR_NAME,
                })

            # ── EXPLORE ───────────────────────────────────────────
            # Dispatch branches to worker pool
            self._early_hit_event.clear()

            for branch in branches:
                spell = _make_exploration_spell(branch, self)
                # Use the fairy's own worker pool (from Organ Template)
                # This is lightweight — max 2 threads from our pool
                if hasattr(self, '_worker_pool') and self._worker_pool:
                    future = self._worker_pool.submit(spell.how, spell)
                    futures[branch.branch_id] = future
                else:
                    # Fallback: run synchronously (shouldn't happen)
                    spell.how(spell)

            # ── WAIT ──────────────────────────────────────────────
            # Wait for all branches OR early hit OR timeout
            deadline = time.time() + max_time

            completed_branches = []
            for branch_id, future in futures.items():
                remaining = deadline - time.time()
                if remaining <= 0:
                    break

                # Check early hit signal between waits
                if self._early_hit_event.is_set():
                    self.log("EARLY HIT detected — collapsing immediately")
                    self._total_early_hits += 1
                    break

                try:
                    future.result(timeout=remaining)
                except FuturesTimeout:
                    # Mark timed-out branches
                    for b in branches:
                        if b.status == BranchStatus.EXPLORING:
                            b.status = BranchStatus.TIMEOUT
                            b.completed_at = time.time()
                except Exception as e:
                    # Branch error — already handled in spell
                    pass

            # ── COLLAPSE ──────────────────────────────────────────
            winner = self._collapse(search, branches)

            if winner:
                search.status = "collapsed"
                search.winner = winner
                self._total_collapses += 1
                self.log(
                    f"COLLAPSE: '{search.intent[:40]}' → "
                    f"strategy='{winner.strategy.name}' "
                    f"confidence={winner.confidence:.2f} "
                    f"elapsed={search.elapsed:.1f}s"
                )

                # Record strategy score for learning
                scores = self._strategy_scores.get(winner.strategy.name)
                if scores is not None:
                    scores.append(winner.confidence)

                # Publish result
                if self.post:
                    self.post.publish("quantum_search.result", {
                        "search_id": search.search_id,
                        "intent": search.intent,
                        "strategy": winner.strategy.name,
                        "confidence": winner.confidence,
                        "result": winner.result,
                        "branches_explored": len(branches),
                        "elapsed": search.elapsed,
                        "source": self.ACTOR_NAME,
                    })

                    self.post.publish("quantum_search.collapse", {
                        "search_id": search.search_id,
                        "winner_branch": winner.branch_id,
                        "strategy": winner.strategy.name,
                        "confidence": winner.confidence,
                        "branches_total": len(branches),
                        "branches_found": len([
                            b for b in branches if b.status == BranchStatus.FOUND
                        ]),
                        "source": self.ACTOR_NAME,
                    })
            else:
                search.status = "failed"
                self.log(f"FAILED: '{search.intent[:40]}' — no viable branches")

        except Exception as e:
            search.status = "error"
            self.log(f"ERROR in search lifecycle: {e}")
            import traceback
            traceback.print_exc()

        finally:
            search.collapsed_at = time.time()
            search.total_cost = sum(b.cost for b in search.branches)

            # Move to history
            with self._search_lock:
                self._active_searches.pop(search.search_id, None)
            self._search_history.append(search)

    # ── Collapse Logic ─────────────────────────────────────────────────

    def _collapse(
        self,
        search: QuantumSearch,
        branches: List[QuantumBranch],
    ) -> Optional[QuantumBranch]:
        """Select the best branch using scoring + softmax selection.

        Scoring factors:
        - Self-assessed confidence (from strategy)
        - Resource efficiency (lower cost = better)
        - Historical strategy performance
        - Time efficiency (faster = slight bonus)
        """
        # Filter to branches that found something
        viable = [
            b for b in branches
            if b.status == BranchStatus.FOUND and b.result is not None
        ]

        if not viable:
            return None

        if len(viable) == 1:
            return viable[0]

        # Score each branch
        scores: Dict[str, float] = {}
        for branch in viable:
            score = branch.confidence  # Base: self-assessed confidence

            # Efficiency bonus: lower cost relative to budget = better
            if branch.strategy.max_cost > 0:
                efficiency = 1.0 - (branch.cost / branch.strategy.max_cost)
                score *= (0.8 + 0.2 * max(0, efficiency))

            # Speed bonus: faster branches get slight edge
            if branch.strategy.max_time > 0:
                speed = 1.0 - (branch.elapsed / branch.strategy.max_time)
                score *= (0.9 + 0.1 * max(0, speed))

            # Historical performance: weight by past success rate
            hist_scores = self._strategy_scores.get(branch.strategy.name)
            if hist_scores and len(hist_scores) >= 3:
                avg_hist = sum(hist_scores) / len(hist_scores)
                score *= (0.7 + 0.3 * avg_hist)

            scores[branch.branch_id] = max(0.001, score)

        # Softmax selection (probabilistic, not greedy)
        selected_id = self._softmax_select(scores, self.COLLAPSE_TEMPERATURE)

        # Find and return the selected branch
        for branch in viable:
            if branch.branch_id == selected_id:
                return branch

        # Fallback: highest raw confidence
        return max(viable, key=lambda b: b.confidence)

    @staticmethod
    def _softmax_select(
        scores: Dict[str, float],
        temperature: float = 1.0,
    ) -> str:
        """Softmax selection — probabilistic but biased toward high scores.

        Lower temperature = more greedy (picks highest score more often).
        Higher temperature = more exploratory (more uniform selection).
        """
        import random

        if not scores:
            return ""

        # Compute softmax probabilities
        items = list(scores.items())
        max_score = max(s for _, s in items)

        # Subtract max for numerical stability, apply temperature
        exp_scores = []
        for key, score in items:
            exp_s = math.exp((score - max_score) / max(temperature, 0.01))
            exp_scores.append((key, exp_s))

        total = sum(e for _, e in exp_scores)
        if total <= 0:
            return items[0][0]

        # Weighted random selection
        r = random.random() * total
        cumulative = 0.0
        for key, exp_s in exp_scores:
            cumulative += exp_s
            if r <= cumulative:
                return key

        return exp_scores[-1][0]

    # ── Strategy Implementations ───────────────────────────────────────

    def _execute_strategy(
        self,
        strategy: SearchStrategy,
        snapshot: Dict[str, Any],
        branch: QuantumBranch,
    ) -> Tuple[Any, float]:
        """Execute a specific strategy and return (result, confidence).

        Each strategy talks to existing system components:
        - Memory recall → SRM search
        - Association walk → AssociationCortex query
        - Pattern match → parallel_grep
        - Oracle consult → ProbabilityOracle intent
        - Serendipity → random concept exploration
        """
        intent = snapshot.get("intent", "")
        keywords = snapshot.get("keywords", [])
        context = snapshot.get("context", {})

        st = strategy.strategy_type

        if st == StrategyType.MEMORY_RECALL:
            return self._strategy_memory_recall(intent, keywords, context, branch)
        elif st == StrategyType.ASSOCIATION_WALK:
            return self._strategy_association_walk(intent, keywords, context, branch)
        elif st == StrategyType.PATTERN_MATCH:
            return self._strategy_pattern_match(intent, keywords, context, branch)
        elif st == StrategyType.ORACLE_CONSULT:
            return self._strategy_oracle_consult(intent, keywords, context, branch)
        elif st == StrategyType.SERENDIPITY:
            return self._strategy_serendipity(intent, keywords, context, branch)
        elif st == StrategyType.INFERENCE:
            return self._strategy_inference(intent, keywords, context, branch)
        elif st == StrategyType.SIMULATION:
            return self._strategy_simulation(intent, keywords, context, branch)
        else:
            return None, 0.0

    def _strategy_memory_recall(self, intent, keywords, context, branch) -> Tuple[Any, float]:
        """Search SRM for relevant past experiences."""
        try:
            # Try to use SRM search via the system
            from P10_Memory.Akashic_triple_helix_memory_storage.relational_clusters import (
                search as srm_search
            )
            query = intent if intent else " ".join(keywords[:5])
            results = srm_search.search_all_clusters(query, limit=5)

            if results:
                # Score based on best match score
                best_score = max(r.get("score", 0) for r in results) if results else 0
                confidence = min(1.0, best_score / 10.0)  # Normalize
                branch.cost = 0.1
                return {
                    "type": "memory_recall",
                    "matches": results[:3],
                    "query": query,
                    "best_score": best_score,
                }, confidence
            return None, 0.0
        except Exception as e:
            branch.error = f"memory_recall: {e}"
            return None, 0.0

    def _strategy_association_walk(self, intent, keywords, context, branch) -> Tuple[Any, float]:
        """Walk the AssociationCortex concept graph."""
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
                get_cortex_singleton
            )
            cortex = get_cortex_singleton()
            if not cortex:
                return None, 0.0

            # Walk from keywords
            all_related = []
            for kw in keywords[:3]:
                related = cortex.query(kw, depth=2, limit=5)
                if related:
                    all_related.extend(related)

            if all_related:
                # Deduplicate by concept key
                seen = set()
                unique = []
                for item in all_related:
                    key = item.get("key", item.get("concept", ""))
                    if key and key not in seen:
                        seen.add(key)
                        unique.append(item)

                confidence = min(1.0, len(unique) / 10.0)
                branch.cost = 0.2
                return {
                    "type": "association_walk",
                    "concepts": unique[:8],
                    "seed_keywords": keywords[:3],
                }, confidence
            return None, 0.0
        except Exception as e:
            branch.error = f"association_walk: {e}"
            return None, 0.0

    def _strategy_pattern_match(self, intent, keywords, context, branch) -> Tuple[Any, float]:
        """Search for literal patterns in codebase/data."""
        try:
            import subprocess
            query = keywords[0] if keywords else intent.split()[0] if intent else ""
            if not query:
                return None, 0.0

            # Quick grep search (bounded by time)
            result = subprocess.run(
                ["python", "-c", f"""
import sys; sys.path.insert(0, '.')
from postal_core.mcp.tools.file_ops import search_text
results = search_text('{query}', max_results=5)
print(results)
"""],
                capture_output=True,
                text=True,
                timeout=3,
                cwd=str(Path(__file__).parent.parent.parent.parent),
            )

            if result.stdout.strip():
                branch.cost = 0.1
                return {
                    "type": "pattern_match",
                    "query": query,
                    "raw_output": result.stdout[:500],
                }, 0.4  # Pattern match gives moderate confidence
            return None, 0.0
        except Exception as e:
            branch.error = f"pattern_match: {e}"
            return None, 0.0

    def _strategy_oracle_consult(self, intent, keywords, context, branch) -> Tuple[Any, float]:
        """Ask the ProbabilityOracle for guidance."""
        try:
            from fairies.P30_Cognition.ProbabilityOracleFairy.fairy import (
                ProbabilityOracleFairy as OracleClass
            )
            # Try to get singleton
            oracle = getattr(OracleClass, '_instance', None)
            if oracle and hasattr(oracle, '_intent_oracle_suggest'):
                suggestion = oracle._intent_oracle_suggest({
                    "intent": intent,
                    "keywords": keywords,
                    "context": context,
                })
                if suggestion:
                    branch.cost = 0.15
                    confidence = suggestion.get("confidence", 0.3)
                    return {
                        "type": "oracle_consult",
                        "suggestion": suggestion,
                    }, confidence
            return None, 0.0
        except Exception as e:
            branch.error = f"oracle_consult: {e}"
            return None, 0.0

    def _strategy_serendipity(self, intent, keywords, context, branch) -> Tuple[Any, float]:
        """Random concept exploration — break out of local optima."""
        try:
            import random

            # Pick a random seed from keywords, associations, or pure random
            seeds = list(keywords) if keywords else intent.split()[:3]
            if not seeds:
                seeds = ["curiosity", "pattern", "emergence"]

            seed = random.choice(seeds)

            # Try association cortex with a twist — go deeper, wider
            try:
                from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
                    get_cortex_singleton
                )
                cortex = get_cortex_singleton()
                if cortex:
                    # Walk 3 hops deep from a random seed
                    deep_walk = cortex.query(seed, depth=3, limit=10)
                    if deep_walk and len(deep_walk) > 2:
                        # Pick a random non-obvious result
                        surprise = random.choice(deep_walk[2:])
                        branch.cost = 0.1
                        return {
                            "type": "serendipity",
                            "seed": seed,
                            "discovery": surprise,
                            "path_length": 3,
                        }, 0.3  # Serendipity is low confidence but novel
            except Exception:
                pass

            # Fallback: return the seed itself as a "starting point"
            branch.cost = 0.05
            return {
                "type": "serendipity",
                "seed": seed,
                "discovery": {"concept": seed, "note": "seed concept for exploration"},
            }, 0.1
        except Exception as e:
            branch.error = f"serendipity: {e}"
            return None, 0.0

    def _strategy_inference(self, intent, keywords, context, branch) -> Tuple[Any, float]:
        """Run through inference fairy (RWKV or external LLM). Expensive."""
        try:
            from fairies.P30_Cognition.AkashicInferenceFairy.fairy import (
                AkashicInferenceFairy
            )
            inference = getattr(AkashicInferenceFairy, '_instance', None)
            if inference and hasattr(inference, 'generate'):
                result = inference.generate(
                    prompt=intent,
                    max_tokens=100,
                    temperature=0.7,
                )
                if result:
                    branch.cost = 0.8  # Expensive
                    return {
                        "type": "inference",
                        "response": result,
                    }, 0.6
            return None, 0.0
        except Exception as e:
            branch.error = f"inference: {e}"
            return None, 0.0

    def _strategy_simulation(self, intent, keywords, context, branch) -> Tuple[Any, float]:
        """Run a mini simulation. Reserved for future expansion."""
        # Placeholder — simulation strategies will be added
        # when we have specific sim frameworks to call
        branch.cost = 0.0
        return None, 0.0

    # ── Helpers ─────────────────────────────────────────────────────────

    def _build_snapshot(
        self,
        intent: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a lightweight state snapshot for branch exploration.

        Extracts keywords and relevant context without cloning the whole system.
        """
        # Extract keywords from intent
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "and", "or", "not", "no", "but", "if", "then", "so", "as",
            "it", "its", "this", "that", "what", "how", "why", "when",
            "where", "who", "which", "do", "does", "did", "has", "have",
            "had", "can", "could", "should", "would", "will", "may",
            "might", "shall", "i", "me", "my", "we", "our", "you", "your",
        }
        words = intent.lower().split()
        keywords = [w.strip(".,!?;:'\"()[]{}") for w in words if w not in stop_words]
        keywords = [k for k in keywords if len(k) > 2][:10]

        return {
            "intent": intent,
            "keywords": keywords,
            "context": context,
            "timestamp": time.time(),
        }

    def _select_strategies(
        self,
        intent: str,
        filter_names: Optional[List[str]] = None,
    ) -> List[SearchStrategy]:
        """Select which strategies to use for this search.

        If filter_names provided, use only those.
        Otherwise, use weighted selection up to MAX_BRANCHES.
        """
        if filter_names:
            selected = [
                s for s in self._strategies if s.name in filter_names
            ]
            return selected[:self.MAX_BRANCHES]

        # Weight strategies by their base weight + learned performance
        weighted = []
        for strategy in self._strategies:
            weight = strategy.weight
            hist = self._strategy_scores.get(strategy.name)
            if hist and len(hist) >= 3:
                avg = sum(hist) / len(hist)
                weight *= (0.5 + avg)  # Boost by historical success
            weighted.append((strategy, weight))

        # Sort by weight descending, take top N
        weighted.sort(key=lambda x: -x[1])
        return [s for s, _ in weighted[:self.MAX_BRANCHES]]

    def _signal_early_hit(self, branch: QuantumBranch):
        """Signal that a branch found a high-confidence result."""
        self._early_hit_event.set()
        if self.post:
            self.post.publish("quantum_search.early_hit", {
                "search_id": branch.search_id,
                "branch_id": branch.branch_id,
                "strategy": branch.strategy.name,
                "confidence": branch.confidence,
                "source": self.ACTOR_NAME,
            })

    # ── Public API (MCP / Intent) ──────────────────────────────────────

    def search(
        self,
        intent: str,
        context: Optional[Dict[str, Any]] = None,
        strategies: Optional[List[str]] = None,
        max_time: float = 0.0,
    ) -> str:
        """Public API to trigger a quantum search.

        Returns the search_id for tracking.
        """
        context = context or {}
        snapshot = self._build_snapshot(intent, context)
        strategy_objs = self._select_strategies(intent, strategies)

        search = QuantumSearch(
            intent=intent,
            context=snapshot,
            status="forking",
            started_at=time.time(),
        )

        with self._search_lock:
            self._active_searches[search.search_id] = search
            self._total_searches += 1

        # Launch
        t = threading.Thread(
            target=self._search_lifecycle,
            args=(search, strategy_objs, snapshot, max_time or self.MAX_SEARCH_TIME),
            daemon=True,
            name=f"qsearch_{search.search_id[-8:]}",
        )
        t.start()

        return search.search_id

    def get_search_status(self, search_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an active or recent search."""
        with self._search_lock:
            active = self._active_searches.get(search_id)
            if active:
                return active.to_dict()

        # Check history
        for s in self._search_history:
            if s.search_id == search_id:
                return s.to_dict()
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get quantum search statistics."""
        # Compute strategy effectiveness
        strategy_effectiveness = {}
        for name, scores in self._strategy_scores.items():
            if scores:
                strategy_effectiveness[name] = {
                    "avg_confidence": round(sum(scores) / len(scores), 3),
                    "samples": len(scores),
                }

        return {
            "total_searches": self._total_searches,
            "total_collapses": self._total_collapses,
            "total_early_hits": self._total_early_hits,
            "total_branches": self._total_branches,
            "active_searches": len(self._active_searches),
            "history_size": len(self._search_history),
            "strategies": [s.name for s in self._strategies],
            "strategy_effectiveness": strategy_effectiveness,
        }

    # ── Intents (for postal system) ────────────────────────────────────

    def _intent_search(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Intent: Trigger a quantum search."""
        intent = payload.get("intent", "")
        if not intent:
            return {"error": "No intent provided"}
        search_id = self.search(
            intent=intent,
            context=payload.get("context"),
            strategies=payload.get("strategies"),
            max_time=payload.get("max_time", 0.0),
        )
        return {"search_id": search_id, "status": "forking"}

    def _intent_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Intent: Get search status."""
        search_id = payload.get("search_id", "")
        status = self.get_search_status(search_id)
        return status or {"error": f"Search {search_id} not found"}

    def _intent_stats(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Intent: Get quantum search statistics."""
        return self.get_stats()


# ============================================================================
# Module exports for v3_boot / fairy discovery
# ============================================================================

ACTOR_NAME = "QuantumSearchFairy"
FAIRY_CLASS = QuantumSearchFairy
