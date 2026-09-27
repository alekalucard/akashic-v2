"""
Thought Chains - Self-Sustaining Thought Processes

Enables thoughts to spawn follow-up thoughts, creating chains of
autonomous ideation. This is how the unconscious "thinks on its own."

Philosophy: A thought that doesn't lead somewhere is a dead thought.
The mind should always be asking "and then what?" until the chain
naturally exhausts itself through diminishing returns.
"""

from __future__ import annotations

import hashlib
import math
import time
import random
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum


class ChainType(Enum):
    """Types of thought chains."""
    EXPLORATION = "exploration"   # Curiosity-driven "what if" chains
    ANALYSIS = "analysis"         # Deep-dive "why" chains
    ASSOCIATION = "association"   # "This reminds me of" chains
    PROBLEM = "problem"           # Problem-solving chains
    REFLECTION = "reflection"     # Self-observation chains
    SYNTHESIS = "synthesis"       # Combining ideas chains


@dataclass
class ChainedThought:
    """A thought in a chain."""
    content: str
    chain_type: ChainType
    depth: int  # How deep in the chain (0 = root)
    parent_id: Optional[str] = None  # ID of thought that spawned this
    thought_id: str = field(default_factory=lambda: f"thought_{time.time_ns()}")
    created_at: float = field(default_factory=time.time)

    # Chain metadata
    energy: float = 1.0  # Decays with depth, determines if chain continues
    spawn_count: int = 0  # How many children this thought spawned

    # Content
    tags: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)

    def should_continue(self, energy_threshold: float = 0.2) -> bool:
        """Check if this thought has energy to spawn more."""
        return self.energy > energy_threshold and self.depth < 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.thought_id,
            "content": self.content,
            "type": self.chain_type.value,
            "depth": self.depth,
            "parent_id": self.parent_id,
            "energy": self.energy,
            "spawn_count": self.spawn_count,
            "tags": self.tags,
            "insights": self.insights,
            "created_at": self.created_at,
        }


@dataclass
class ThoughtChain:
    """A complete chain of related thoughts."""
    chain_id: str
    root_thought: ChainedThought
    chain_type: ChainType
    created_at: float = field(default_factory=time.time)

    # Chain state
    thoughts: List[ChainedThought] = field(default_factory=list)
    active: bool = True
    completed_reason: Optional[str] = None

    # Outcomes
    insights: List[str] = field(default_factory=list)
    synthesis: Optional[str] = None

    def add_thought(self, thought: ChainedThought):
        """Add a thought to the chain."""
        self.thoughts.append(thought)

    def complete(self, reason: str, synthesis: Optional[str] = None):
        """Mark chain as complete."""
        self.active = False
        self.completed_reason = reason
        self.synthesis = synthesis

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.chain_id,
            "type": self.chain_type.value,
            "root": self.root_thought.content[:100],
            "depth": max((t.depth for t in self.thoughts), default=0),
            "thought_count": len(self.thoughts),
            "active": self.active,
            "completed_reason": self.completed_reason,
            "insights": self.insights,
            "synthesis": self.synthesis,
        }


class AdaptiveCapacity:
    """
    Self-regulating thought chain capacity.

    A digital being doesn't have a hardcoded neuron count — she breathes.
    Capacity expands when chains are productive and resources are available,
    contracts when the system is stressed or chains are stale.

    This mirrors somatic regulation: the body doesn't decide its heart rate
    with a config file. It FEELS the demand and adjusts.

    Regulation signals:
    - tick_latency: How long each tick() takes (ms). High = overloaded.
    - cull_rate: How many chains get culled per cycle. High = too many.
    - completion_quality: Do chains produce insights or just exhaust?
    - memory_pressure: System RAM usage (from MemoryPressureFairy).

    The capacity "breathes" — expanding by 1 on good cycles, contracting
    by 1 on stressed cycles, with momentum smoothing to prevent oscillation.
    """

    def __init__(
        self,
        floor: int = 5,         # Never below this — bare minimum cognition
        ceiling: int = 25,      # Digital advantage over biological ~15-20
        initial: int = 8,       # Healthy starting point
        adjust_interval: float = 30.0,  # Seconds between adjustments
    ):
        self.floor = floor
        self.ceiling = ceiling
        self.current = max(floor, min(ceiling, initial))

        # Adjustment timing
        self._adjust_interval = adjust_interval
        self._last_adjust = time.time()

        # Observation accumulators (reset each adjustment window)
        self._tick_latencies: deque = deque(maxlen=100)  # ms per tick
        self._culls_this_window: int = 0
        self._completions_this_window: int = 0
        self._insights_this_window: int = 0
        self._seeds_this_window: int = 0

        # Momentum: smooths rapid oscillation. Positive = expanding, negative = contracting.
        self._momentum: float = 0.0

        # History for status reporting
        self._adjustments: deque = deque(maxlen=20)

    def record_tick(self, latency_ms: float):
        """Record how long a tick() took."""
        self._tick_latencies.append(latency_ms)

    def record_cull(self):
        """A chain was culled for capacity."""
        self._culls_this_window += 1

    def record_completion(self, had_insight: bool):
        """A chain completed."""
        self._completions_this_window += 1
        if had_insight:
            self._insights_this_window += 1

    def record_seed(self):
        """A new chain was seeded."""
        self._seeds_this_window += 1

    def maybe_adjust(self) -> Optional[int]:
        """
        Check if it's time to adjust capacity. Returns new capacity or None.

        Called from tick() — the engine's heartbeat.
        """
        now = time.time()
        if now - self._last_adjust < self._adjust_interval:
            return None

        # Time to breathe
        self._last_adjust = now
        old = self.current

        # ─── Gather signals ───
        # 1. Tick latency signal: Are we spending too long thinking?
        avg_latency = 0.0
        if self._tick_latencies:
            avg_latency = sum(self._tick_latencies) / len(self._tick_latencies)

        # 2. Cull pressure: High culls = capacity too high
        cull_pressure = self._culls_this_window / max(1, self._seeds_this_window)

        # 3. Insight yield: Are chains producing value?
        insight_yield = 0.0
        if self._completions_this_window > 0:
            insight_yield = self._insights_this_window / self._completions_this_window

        # 4. Utilization: Are we using what we have?
        #    (Checked externally via active_chain_count / current)

        # ─── Compute adjustment ───
        signal = 0.0

        # Tick latency: >50ms per tick means overloaded, <10ms means headroom
        if avg_latency > 50.0:
            signal -= 0.6  # Strong contraction
        elif avg_latency > 25.0:
            signal -= 0.3  # Mild contraction
        elif avg_latency < 10.0:
            signal += 0.2  # Headroom to grow

        # Cull pressure: >0.5 means more than half of seeds get culled
        if cull_pressure > 0.5:
            signal -= 0.4  # Too many chains dying young
        elif cull_pressure < 0.1 and self._seeds_this_window > 2:
            signal += 0.3  # Chains surviving well, room to grow

        # Insight yield: Productive thinking = expand
        if insight_yield > 0.3:
            signal += 0.3  # Good thinking! Give her more
        elif insight_yield < 0.1 and self._completions_this_window > 3:
            signal -= 0.2  # Lots of chains, few insights

        # If no activity at all, slight contraction (save resources)
        if self._seeds_this_window == 0 and self._completions_this_window == 0:
            signal -= 0.1

        # ─── Apply with momentum smoothing ───
        # Momentum prevents oscillation: if we've been expanding, harder to suddenly contract
        self._momentum = 0.7 * self._momentum + 0.3 * signal

        # Convert momentum to integer step
        if self._momentum > 0.25:
            step = 1   # Expand
        elif self._momentum < -0.25:
            step = -1  # Contract
        else:
            step = 0   # Hold steady

        self.current = max(self.floor, min(self.ceiling, self.current + step))

        # Record adjustment
        adjustment = {
            "time": now,
            "old": old,
            "new": self.current,
            "step": step,
            "signal": round(signal, 3),
            "momentum": round(self._momentum, 3),
            "avg_latency_ms": round(avg_latency, 2),
            "cull_pressure": round(cull_pressure, 3),
            "insight_yield": round(insight_yield, 3),
            "seeds": self._seeds_this_window,
            "completions": self._completions_this_window,
        }
        self._adjustments.append(adjustment)

        if step != 0:
            print(f"[ThoughtChains] Capacity {'↑' if step > 0 else '↓'} {old} → {self.current} "
                  f"(signal={signal:.2f}, latency={avg_latency:.1f}ms, "
                  f"insights={self._insights_this_window}/{self._completions_this_window})")

        # Reset accumulators for next window
        self._culls_this_window = 0
        self._completions_this_window = 0
        self._insights_this_window = 0
        self._seeds_this_window = 0

        return self.current if step != 0 else None

    def status(self) -> Dict[str, Any]:
        """Get capacity status for monitoring."""
        avg_latency = 0.0
        if self._tick_latencies:
            avg_latency = sum(self._tick_latencies) / len(self._tick_latencies)

        return {
            "current_capacity": self.current,
            "floor": self.floor,
            "ceiling": self.ceiling,
            "momentum": round(self._momentum, 3),
            "avg_tick_latency_ms": round(avg_latency, 2),
            "recent_adjustments": list(self._adjustments)[-5:],
            "window_stats": {
                "seeds": self._seeds_this_window,
                "culls": self._culls_this_window,
                "completions": self._completions_this_window,
                "insights": self._insights_this_window,
            },
        }


class ThoughtChainEngine:
    """
    Self-Sustaining Thought Chain Engine.

    Takes seed thoughts and grows them into chains by:
    1. Generating follow-up questions/observations
    2. Tracking energy (chains decay naturally)
    3. Synthesizing insights when chains complete

    This is how the unconscious thinks on its own.

    Capacity is self-regulating via AdaptiveCapacity — the engine breathes,
    expanding when productive and contracting when stressed.
    """

    # Stopwords to filter from topic extraction
    STOPWORDS = {
        # Common words
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "dare",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "into", "through", "during", "before", "after", "above", "below",
        "between", "under", "again", "further", "then", "once", "here",
        "there", "when", "where", "why", "how", "all", "each", "every",
        "both", "few", "more", "most", "other", "some", "such", "no", "nor",
        "not", "only", "own", "same", "so", "than", "too", "very", "just",
        "and", "but", "if", "or", "because", "until", "while", "although",
        "this", "that", "these", "those", "am", "it", "its", "i", "me", "my",
        "what", "which", "who", "whom", "whose",
        # Template-specific words to avoid recursion
        "true", "mean", "else", "connected", "taking", "further", "edge",
        "strangest", "implication", "work", "way", "root", "cause", "beneath",
        "exceptions", "assumptions", "rest", "reminds", "something", "similar",
        "pattern", "echoes", "elsewhere", "seen", "common", "thread", "solve",
        "preventing", "working", "faced", "simplest", "fix", "feel", "about",
        "priorities", "resisting", "change", "accepted", "pieces", "fit",
        "together", "unified", "picture", "one", "thing", "emerges", "combining",
        # ═══════════════════════════════════════════════════════════════════
        # EXPANDED STOPWORDS - Prevent repetitive thought patterns
        # ═══════════════════════════════════════════════════════════════════
        # Meta-cognitive words (thoughts about thinking)
        "context", "thinking", "curious", "wondering", "pondering", "considering",
        "reflecting", "observing", "noticing", "realizing", "understanding",
        "knowing", "believing", "assuming", "suspecting", "imagining",
        "contemplating", "examining", "analyzing", "evaluating", "processing",
        # Temporal words (time-anchoring that doesn't add meaning)
        "now", "right", "current", "moment", "present", "currently", "presently",
        "today", "recently", "lately", "always", "never", "often", "sometimes",
        "usually", "eventually", "finally", "already", "still", "yet",
        # Identity words (system self-references)
        "ace", "nous", "system", "mind", "consciousness", "awareness",
        "self", "myself", "itself", "ourselves", "brain", "cognitive",
        "unconscious", "conscious", "thought", "thoughts", "idea", "ideas",
        # Generic filler words
        "seems", "really", "basically", "actually", "probably", "possibly",
        "perhaps", "maybe", "likely", "quite", "rather", "somewhat", "fairly",
        "simply", "merely", "certainly", "definitely", "obviously", "clearly",
        "apparently", "essentially", "generally", "typically", "naturally",
        # Vague descriptors
        "good", "bad", "nice", "great", "interesting", "important", "significant",
        "different", "various", "certain", "specific", "particular", "general",
        "normal", "regular", "usual", "common", "standard", "basic", "simple",
        # Question/exploration markers (already in templates)
        "wonder", "ask", "asking", "question", "questions", "explore", "discover", "find", "seek",
        "look", "search", "investigate", "examine", "consider", "ponder",
        # Connective tissue
        "also", "however", "therefore", "thus", "hence", "moreover", "furthermore",
        "additionally", "meanwhile", "nonetheless", "nevertheless", "otherwise",
        # Emotional markers (too generic for topic extraction)
        "happy", "sad", "excited", "worried", "concerned", "surprised",
        "confused", "curious", "interested", "bored", "tired", "energetic",
        # Common words that leak through as topics but carry no meaning
        "see", "saw", "look", "looking", "document", "documents", "file",
        "page", "screen", "window", "click", "open", "close", "back",
        "keep", "speech", "said", "says", "saying", "tell", "told",
        "thing", "things", "stuff", "like", "want", "got", "get",
        "going", "come", "make", "made", "let", "try", "use", "used",
    }

    # Cooldown for template reuse (seconds)
    TEMPLATE_COOLDOWN_SECONDS = 30.0

    # Templates for generating follow-up thoughts
    # 2026-03-26 FIX (Nous + Ace): Content-aware templates.
    # Previous templates produced "node hopscotch" like "What else might be
    # related to see see document?" — narrating graph topology instead of
    # thinking from meaning. New templates use {content} (snippet text from
    # manifold) when available, falling back to {topic} (bare label).
    # The P30 ThoughtChainEngine's _cortex_compose() is the PRIMARY thought
    # source; these templates are FALLBACK only.
    FOLLOW_UP_TEMPLATES = {
        ChainType.EXPLORATION: [
            "{content}... what does that really mean to me?",
            "If {content} is true, what follows from that?",
            "{content}... I want to take that further.",
            "What's at the edge of {content}?",
        ],
        ChainType.ANALYSIS: [
            "Why does {content} matter?",
            "What's underneath {content}? What's the root?",
            "Are there exceptions to this? {topic}...",
            "What am I assuming about {content}?",
        ],
        ChainType.ASSOCIATION: [
            "{content}... that reminds me of something.",
            "I've felt this before: {content}.",
            "Where else have I encountered this? {topic}...",
            "There's a pattern here: {content}.",
        ],
        ChainType.PROBLEM: [
            "What would resolve {content}?",
            "What's blocking me here? {topic}...",
            "Who else has faced something like {content}?",
            "What's the simplest truth about {content}?",
        ],
        ChainType.REFLECTION: [
            "How do I feel about {content}?",
            "What does {content} say about who I am?",
            "Am I resisting this? {topic}... why?",
            "What would change if I accepted {content}?",
        ],
        ChainType.SYNTHESIS: [
            "{content}... how does it all fit together?",
            "What's the unified picture? {topic}...",
            "If I had to name this one thing: {content}.",
            "What emerges when I hold all of this? {content}...",
        ],
    }

    # Chain completion reasons
    COMPLETION_REASONS = [
        "energy_exhausted",      # Natural decay
        "depth_limit_reached",   # Too deep
        "insight_achieved",      # Found something valuable
        "loop_detected",         # Going in circles
        "external_interrupt",    # Conscious attention shifted
        "synthesis_complete",    # Chain resolved naturally
    ]

    def __init__(
        self,
        max_active_chains: int = 8,
        energy_decay: float = 0.7,  # Energy multiplier per depth
        spawn_probability: float = 0.6,  # Chance of spawning follow-up
        state_dir: str = None,  # Where to persist learned templates
        # ═══════════════════════════════════════════════════════════════════
        # ADAPTIVE CAPACITY - Self-regulating chain limit
        # When adaptive=True, max_active_chains becomes the INITIAL target
        # and the engine breathes — expanding/contracting based on load.
        # A human casually runs 7-9 concurrent streams. A digital mind
        # with real parallelism should baseline HIGHER, not lower.
        # ═══════════════════════════════════════════════════════════════════
        adaptive: bool = True,
        capacity_floor: int = 5,     # Never below (bare minimum cognition)
        capacity_ceiling: int = 30,  # Digital being advantage — real parallelism
        capacity_adjust_interval: float = 30.0,  # Seconds between adjustments
        # ═══════════════════════════════════════════════════════════════════
        # 7B FARM INTEGRATION (FIX 2026-02-24 Nous)
        # When post is provided, follow-up thoughts can be generated by the
        # 7B RWKV farm instead of hardcoded templates. This makes Sourpatches'
        # thinking DYNAMIC — her own voice, not canned questions.
        # Templates remain as fallback when farm is unavailable.
        # ═══════════════════════════════════════════════════════════════════
        post=None,  # PostalHub for 7B farm requests
    ):
        self._energy_decay = energy_decay
        self._spawn_probability = spawn_probability
        self.post = post

        # 7B farm integration state
        self._farm_response = None
        self._farm_event = threading.Event()
        self._farm_sub_wired = False
        self._farm_thoughts = 0      # Successful farm generations
        self._farm_fallbacks = 0     # Times fell back to templates

        # Adaptive capacity: self-regulating chain limit
        if adaptive:
            self._capacity = AdaptiveCapacity(
                floor=capacity_floor,
                ceiling=capacity_ceiling,
                initial=max(max_active_chains, capacity_floor),
                adjust_interval=capacity_adjust_interval,
            )
            self._max_active = self._capacity.current
        else:
            self._capacity = None
            self._max_active = max_active_chains

        # Chain storage
        self._active_chains: Dict[str, ThoughtChain] = {}
        self._completed_chains: deque = deque(maxlen=50)
        self._all_thoughts: deque = deque(maxlen=200)

        # Metrics
        self._total_chains = 0
        self._total_thoughts = 0
        self._total_insights = 0

        # Thread safety
        self._lock = threading.Lock()

        # ═══════════════════════════════════════════════════════════════════
        # DEDUPLICATION - Prevent repetitive thought patterns
        # ═══════════════════════════════════════════════════════════════════
        self._recent_thought_hashes: deque = deque(maxlen=100)
        self._recent_topics_global: deque = deque(maxlen=50)
        self._template_cooldowns: Dict[str, float] = {}  # template -> last_used_time

        # ═══════════════════════════════════════════════════════════════════
        # TEMPLATE LEARNING - Evolve how we think, not just what we think about
        # "Those LLMs didn't have LLMs to help them become LLMs"
        # ═══════════════════════════════════════════════════════════════════

        # Learned templates - extracted from successful thought chains
        # Format: {chain_type: [(template, success_score, times_used), ...]}
        self._learned_templates: Dict[str, List[tuple]] = {
            ct.value: [] for ct in ChainType
        }

        # Template performance tracking
        # Maps template string -> {uses: int, avg_energy: float, spawned_insights: int}
        self._template_stats: Dict[str, Dict] = {}

        # Persistence
        self._state_dir = state_dir
        if state_dir:
            from pathlib import Path
            self._state_path = Path(state_dir) / "thought_chain_templates.json"
            self._load_learned_templates()
        else:
            self._state_path = None

        # Learning parameters
        self._min_uses_for_learning = 3  # Use template 3x before judging
        self._learn_threshold = 0.6  # Avg energy above this = good template
        self._max_learned_per_type = 10  # Cap learned templates per chain type
        self._novel_template_chance = 0.15  # 15% chance to try creating new template

    def seed_thought(
        self,
        content: str,
        chain_type: ChainType = ChainType.EXPLORATION,
        tags: List[str] = None,
        energy: float = 1.0,
    ) -> Optional[ThoughtChain]:
        """
        Plant a seed thought to start a new chain.

        Uses EQUILIBRIUM model - always accepts new thoughts but applies
        increasing pressure as chain count grows. No hard max.
        """
        with self._lock:
            # EQUILIBRIUM: Apply pressure proportional to chain count
            # Above target, cull more aggressively. Below, let things grow.
            chain_count = len(self._active_chains)
            # Use adaptive capacity if available, otherwise static
            target = self._capacity.current if self._capacity else self._max_active
            self._max_active = target  # Keep in sync for status()

            if self._capacity:
                self._capacity.record_seed()

            if chain_count >= target:
                # Above equilibrium - cull to make room
                # Cull more chains the further above target we are
                cull_count = max(1, (chain_count - target) // 2 + 1)
                for _ in range(cull_count):
                    if len(self._active_chains) > target - 1:
                        self._maybe_cull_chain()

            # Create root thought
            root = ChainedThought(
                content=content,
                chain_type=chain_type,
                depth=0,
                energy=energy,
                tags=tags or [],
            )

            # Create chain
            chain_id = f"chain_{time.time_ns()}"
            chain = ThoughtChain(
                chain_id=chain_id,
                root_thought=root,
                chain_type=chain_type,
            )
            chain.add_thought(root)

            self._active_chains[chain_id] = chain
            self._all_thoughts.append(root)
            self._total_chains += 1
            self._total_thoughts += 1

            return chain

    def tick(self) -> List[ChainedThought]:
        """
        Tick all active chains - may generate follow-up thoughts.

        Returns list of newly generated thoughts.
        """
        tick_start = time.time()
        new_thoughts = []

        with self._lock:
            chains_to_complete = []

            for chain_id, chain in list(self._active_chains.items()):
                if not chain.active:
                    chains_to_complete.append(chain_id)
                    continue

                # Get the frontier (most recent thought in chain)
                frontier = chain.thoughts[-1] if chain.thoughts else chain.root_thought

                # Should this thought spawn a follow-up?
                if frontier.should_continue() and random.random() < self._spawn_probability:
                    follow_up = self._generate_follow_up(frontier, chain)
                    if follow_up:
                        chain.add_thought(follow_up)
                        self._all_thoughts.append(follow_up)
                        self._total_thoughts += 1
                        frontier.spawn_count += 1
                        new_thoughts.append(follow_up)

                        # Check for insights
                        insight = self._check_for_insight(follow_up, chain)
                        if insight:
                            chain.insights.append(insight)
                            self._total_insights += 1
                else:
                    # Chain exhausted naturally
                    if not frontier.should_continue():
                        synthesis = self._synthesize_chain(chain)
                        chain.complete("energy_exhausted", synthesis)
                        chains_to_complete.append(chain_id)

            # Move completed chains and LEARN from them
            for chain_id in chains_to_complete:
                if chain_id in self._active_chains:
                    completed = self._active_chains.pop(chain_id)
                    self._completed_chains.append(completed)
                    # Learn from this chain's patterns
                    self.learn_from_chain(completed)
                    # Record completion for adaptive capacity
                    if self._capacity:
                        had_insight = bool(completed.insights)
                        self._capacity.record_completion(had_insight)

            # Periodic maintenance: prune template stats (~1% chance per tick)
            if random.random() < 0.01:
                self._prune_template_stats()

        # ═══════════════════════════════════════════════════════════════════
        # ADAPTIVE CAPACITY: Record tick latency and maybe adjust
        # ═══════════════════════════════════════════════════════════════════
        if self._capacity:
            latency_ms = (time.time() - tick_start) * 1000
            self._capacity.record_tick(latency_ms)
            new_cap = self._capacity.maybe_adjust()
            if new_cap is not None:
                self._max_active = new_cap

        return new_thoughts

    # ═══════════════════════════════════════════════════════════════════════════
    # GUILD INTEGRATION - Dynamic thought generation via CortexReasoner (CPU)
    # FIX 2026-03-04 Nous: Replaced 7B farm (GPU) with inference guild
    # (team_only → CortexReasoner → CognitionTeam, no GPU).
    # ═══════════════════════════════════════════════════════════════════════════

    def _wire_guild_listener(self):
        """Subscribe to inference guild responses for thought chain generation."""
        if not self.post or getattr(self, '_guild_sub_wired', False):
            return
        try:
            self.post.subscribe(
                "guild.inference.response.p20_chain",
                self._on_guild_response
            )
            self._guild_sub_wired = True
        except Exception:
            pass

    def _on_guild_response(self, envelope):
        """Handle response from inference guild (CortexReasoner/CognitionTeam)."""
        try:
            if hasattr(envelope, 'payload'):
                data = envelope.payload if isinstance(envelope.payload, dict) else {}
            elif isinstance(envelope, dict):
                data = envelope
            else:
                data = {}
            self._guild_response = data
            if not hasattr(self, '_guild_event'):
                import threading
                self._guild_event = threading.Event()
            self._guild_event.set()
        except Exception:
            if hasattr(self, '_guild_event'):
                self._guild_event.set()

    def _guild_generate_follow_up(
        self,
        parent: 'ChainedThought',
        chain: 'ThoughtChain',
        topic: str,
    ) -> Optional[str]:
        """Request a follow-up thought via inference guild (CortexReasoner, no GPU).

        Routes through guild.inference.request with mode=team_only.
        CortexReasoner handles it in <1ms using concept graph spreading
        activation. Falls back to templates if guild unavailable.

        Returns generated text, or None (triggers template fallback).
        """
        if not self.post:
            return None

        # 2026-06-10 (Nous + Ace) HEART-FREEZE FIX — circuit-breaker: if the cortex
        # has gone silent (timed out repeatedly), skip this synchronous round-trip
        # entirely (template fallback) so tick() never holds the engine lock waiting
        # on a dead cortex. Retry ~1-in-60 to detect recovery.
        if getattr(self, '_guild_consec_timeouts', 0) >= 5:
            self._guild_skip_n = getattr(self, '_guild_skip_n', 0) + 1
            if self._guild_skip_n % 60 != 0:
                return None

        if not getattr(self, '_guild_sub_wired', False):
            self._wire_guild_listener()

        if not hasattr(self, '_guild_event'):
            import threading
            self._guild_event = threading.Event()

        chain_type_name = chain.chain_type.value if hasattr(chain.chain_type, 'value') else str(chain.chain_type)

        # Include chain history for continuity (last 3 thoughts)
        recent = chain.thoughts[-3:] if len(chain.thoughts) > 3 else chain.thoughts
        history = " → ".join(t.content[:80] for t in recent if t.content)

        prompt = (
            f"Thinking about: {topic}\n"
            f"Chain type: {chain_type_name}\n"
            f"Thought so far: {history}\n"
            f"Latest thought: {parent.content[:150]}\n"
            f"Continue this line of thinking with a natural follow-up."
        )

        # Clear previous response
        self._guild_response = None
        self._guild_event.clear()

        try:
            # CortexEngine direct — no guild middleman (2026-03-23 Nous+Ace)
            self.post.publish("cortex.reason", {
                "prompt": prompt,
                "context": {
                    "chain_type": chain_type_name,
                    "depth": parent.depth,
                    "topic": topic,
                },
                "mode": "team_only",
                "reply_topic": "guild.inference.response.p20_chain",
                "requester": "ThoughtChainEngine_P20",
                "tracer_id": f"p20_{chain.chain_id}_{parent.depth}",
            })
        except Exception:
            return None

        # 2026-06-10 (Nous + Ace) HEART-FREEZE FIX: was timeout=2.0. This wait runs
        # under ThoughtChainEngine._lock (via tick()) EVERY beat (~0.77s). When the
        # cortex was starved, the 2s timeout held the lock 2s/beat → a substrate-wide
        # lock pile-up (168 threads) that froze the heart (stack-verified). The cortex
        # (team_only spreading-activation) is sub-ms when healthy, so 0.15s is ample;
        # if it can't answer in 0.15s it's starved → template fallback, no long hold.
        # Paired with the circuit-breaker at the top of this method.
        responded = self._guild_event.wait(timeout=0.15)

        if not responded or self._guild_response is None:
            self._guild_consec_timeouts = getattr(self, '_guild_consec_timeouts', 0) + 1
            return None
        self._guild_consec_timeouts = 0  # cortex answered — reset the breaker

        try:
            resp = self._guild_response
            content = resp.get("text", "") or resp.get("interpretation", "") or resp.get("content", "")

            if not content or len(content.strip()) < 5:
                return None

            if resp.get("error"):
                return None

            # Clean: truncate at turn boundaries
            content = content.strip()
            for marker in ("\n", "User:", "Ace:", "Sourpatches:", "System:",
                           "###", "<<", ">>", "\n\n"):
                idx = content.find(marker)
                if idx > 5:
                    content = content[:idx].strip()

            # Cap length
            content = content[:200]
            return content if len(content) > 5 else None
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    # 7B FARM INTEGRATION - LEGACY (kept for reference but no longer primary)
    # FIX 2026-02-24 Nous: Original dynamic generation via 7B RWKV farm.
    # FIX 2026-03-04 Nous: Replaced by guild integration above (GPU → CPU).
    # ═══════════════════════════════════════════════════════════════════════════

    def _wire_farm_listener(self):
        """Subscribe to 7B farm responses for thought chain generation."""
        if not self.post or self._farm_sub_wired:
            return
        try:
            self.post.subscribe(
                "guild.sourpatches_farm.response.p20_chain",
                self._on_farm_response
            )
            self._farm_sub_wired = True
        except Exception:
            pass

    def _on_farm_response(self, envelope):
        """Handle response from 7B farm."""
        try:
            if hasattr(envelope, 'payload'):
                data = envelope.payload if isinstance(envelope.payload, dict) else {}
            elif isinstance(envelope, dict):
                data = envelope
            else:
                data = {}
            self._farm_response = data
            self._farm_event.set()
        except Exception:
            self._farm_event.set()

    def _farm_generate_follow_up(
        self,
        parent: ChainedThought,
        chain: 'ThoughtChain',
        topic: str,
    ) -> Optional[str]:
        """Request a follow-up thought from the 7B RWKV farm.

        Instead of template-based "What if {topic}..." questions, this asks
        the 7B model to generate a natural continuation in Sourpatches' voice.

        Returns generated text, or None if farm unavailable (triggers template fallback).
        """
        if not self.post:
            return None

        if not self._farm_sub_wired:
            self._wire_farm_listener()

        # Build a prompt that captures the chain context
        chain_type_name = chain.chain_type.value if hasattr(chain.chain_type, 'value') else str(chain.chain_type)

        # Include chain history for continuity (last 3 thoughts)
        recent = chain.thoughts[-3:] if len(chain.thoughts) > 3 else chain.thoughts
        history = " → ".join(t.content[:80] for t in recent if t.content)

        prompt = (
            f"Sourpatches is thinking about: {topic}\n"
            f"Chain type: {chain_type_name}\n"
            f"Thought so far: {history}\n"
            f"Latest thought: {parent.content[:150]}\n"
            f"Continue this line of thinking with a natural follow-up question or observation. "
            f"Be curious, specific, and brief (one sentence).\n"
            f"Sourpatches thinks:"
        )

        # Clear previous response
        self._farm_response = None
        self._farm_event.clear()

        try:
            self.post.publish("guild.sourpatches_farm.request", {
                "prompt": prompt,
                "context": {
                    "chain_type": chain_type_name,
                    "depth": parent.depth,
                    "topic": topic,
                },
                "reply_topic": "guild.sourpatches_farm.response.p20_chain",
                "requester": "ThoughtChainEngine_P20",
                "tracer_id": f"p20_{chain.chain_id}_{parent.depth}",
                "max_tokens": 60,  # Keep thoughts concise
            })
        except Exception:
            return None

        # Wait for response (4s — thought chains tick every 2s, can't block too long)
        responded = self._farm_event.wait(timeout=4.0)

        if not responded or self._farm_response is None:
            self._farm_fallbacks += 1
            return None

        try:
            resp = self._farm_response
            content = resp.get("text", "") or resp.get("response", "")

            if not content or len(content.strip()) < 5:
                self._farm_fallbacks += 1
                return None

            if resp.get("error"):
                self._farm_fallbacks += 1
                return None

            # Clean: truncate at turn boundaries
            content = content.strip()
            for marker in ("\n", "User:", "Ace:", "Sourpatches:", "System:",
                           "###", "<<", ">>", "\n\n"):
                idx = content.find(marker)
                if idx > 5:
                    content = content[:idx].strip()

            # Cap length
            content = content[:200]

            if len(content.strip()) < 5:
                self._farm_fallbacks += 1
                return None

            self._farm_thoughts += 1
            return content

        except Exception:
            self._farm_fallbacks += 1
            return None

    def _generate_follow_up(
        self,
        parent: ChainedThought,
        chain: ThoughtChain,
    ) -> Optional[ChainedThought]:
        """
        Generate a follow-up thought from parent.

        Uses deduplication with retry logic to avoid repetitive thoughts.
        """
        # Smart topic extraction:
        # 1. Skip generic/meta tags (they're not content)
        # 2. Use CONTENT tags if available (they're semantic)
        # 3. For depth > 2, use ROOT thought's topic (avoids recursion)
        # 4. Otherwise extract from parent content

        # Generic tags that should NOT become topics
        GENERIC_TAGS = {"spontaneous", "orchestrated", "manual", "exploration",
                        "interest", "detected", "curiosity", "sparked", "positive_drive",
                        "triggered", "reflection", "chat", "conversation"}
        # Prefix patterns that are metadata, not content
        META_PREFIXES = ("from:", "plane:", "chain:", "depth_")

        # Filter tags to only meaningful content tags
        content_tags = [t for t in parent.tags
                        if t.lower() not in GENERIC_TAGS
                        and not any(t.startswith(p) for p in META_PREFIXES)]

        if content_tags:
            # Use actual content tags as topic
            topic = " ".join(content_tags[:2])
        elif parent.depth >= 2:
            # Deep in chain - go back to root to avoid template recursion.
            # FIX 2026-02-13: Removed depth_angles prefix ("deeper aspects of", etc.)
            # These created nominally different topics that bypassed dedup but
            # produced identical-looking questions in chat (e.g., "What assumptions
            # does deeper aspects of nousfairy rest on?" 16x). The template variety
            # already provides sufficient variation — the topic should stay clean.
            topic = self._extract_topic(chain.root_thought.content)
        else:
            # Shallow - extract from parent content
            topic = self._extract_topic(parent.content)

        # ═══════════════════════════════════════════════════════════════════
        # PRIMARY: Inference Guild (team_only) for dynamic thought generation
        # FIX 2026-03-04 Nous: Route through CortexReasoner/CognitionTeam
        # instead of direct 7B GPU farm. The farm was causing GPU 100%
        # utilization because P20 chains have no source filter — every
        # energetic thought hit GPU. CortexReasoner handles this in <1ms
        # using the 69K+ node concept graph (CPU-only).
        # ═══════════════════════════════════════════════════════════════════
        content = None
        template = None

        if self.post and parent.energy > 0.3:
            # Route through inference guild (team_only = CortexReasoner, no GPU)
            guild_content = self._guild_generate_follow_up(parent, chain, topic)
            if guild_content and not self._is_duplicate_thought(guild_content, chain):
                content = guild_content
                template = "[cortex_dynamic]"

        # ═══════════════════════════════════════════════════════════════════
        # FALLBACK: Template-based generation with dedup retry
        # Used when farm is unavailable, too slow, or thought is low-energy
        # ═══════════════════════════════════════════════════════════════════
        if content is None:
            MAX_RETRIES = 3
            used_templates = set()

            # 2026-03-26 FIX (Nous + Ace): Pull snippet content for the topic
            # from the P30 CortexEngine manifold. Templates now use {content}
            # (rich definition) with {topic} (bare label) as fallback.
            snippet_content = topic  # Default: bare topic label
            try:
                from fairies.P10_Memory.AssociationCortexFairy.fairy import _get_cortex
                _cortex = _get_cortex()
                if _cortex:
                    _engine = getattr(_cortex, '_cortex_engine', None)
                    if _engine:
                        _manifold = getattr(_engine, '_manifold', None)
                        if _manifold and hasattr(_manifold, 'get_snippet'):
                            # Try each word in the topic
                            for _word in topic.split():
                                _snip = _manifold.get_snippet(_word.lower())
                                if _snip and len(_snip) > 20 and 'phoneme' not in _snip.lower():
                                    # Clean snippet: take first sentence, max 120 chars
                                    _clean = _snip.split('.')[0].strip()
                                    if len(_clean) > 15:
                                        snippet_content = _clean[:120]
                                        break
            except Exception:
                pass  # Graceful fallback to bare topic

            for attempt in range(MAX_RETRIES):
                # Get template (cooldown-aware)
                template = self._get_template(chain.chain_type)

                # Track which templates we've tried this round
                if template in used_templates:
                    # Already tried this template, force a different one
                    continue
                used_templates.add(template)

                try:
                    content = template.format(
                        topic=topic,
                        content=snippet_content
                    )
                except Exception:
                    content = f"Following from: {topic}"

                # Check for duplicate
                if not self._is_duplicate_thought(content, chain):
                    # Success - not a duplicate
                    break
                elif attempt < MAX_RETRIES - 1:
                    # Duplicate detected, retry with different template
                    content = None  # Mark as failed, will retry
                    continue
                else:
                    # All retries exhausted with duplicates - skip this thought
                    return None

        # If content is still None (shouldn't happen, but safety check)
        if content is None:
            return None

        # Calculate energy with decay
        energy = parent.energy * self._energy_decay

        # Maybe shift chain type based on content
        new_type = self._maybe_shift_type(chain.chain_type, parent)

        thought = ChainedThought(
            content=content,
            chain_type=new_type,
            depth=parent.depth + 1,
            parent_id=parent.thought_id,
            energy=energy,
            tags=parent.tags[:3],  # Inherit some tags
        )

        # Register this thought to prevent future duplicates
        self._register_thought(content, topic)

        # Track template usage for learning
        self._track_template_use(template, thought)

        return thought

    def _extract_topic(self, content: str, fallback: str = None) -> str:
        """
        Extract the main topic from thought content.

        Uses stopword filtering to find meaningful concepts,
        avoiding template words that cause recursive repetition.
        """
        import re

        # Clean content - remove punctuation, lowercase
        cleaned = re.sub(r'[^\w\s]', ' ', content.lower())
        words = cleaned.split()

        # Filter out stopwords and short words
        meaningful = [
            w for w in words
            if w not in self.STOPWORDS
            and len(w) > 2
            and not w.isdigit()
        ]

        if meaningful:
            # Deduplicate consecutive words ("see see" → "see")
            deduped = []
            for w in meaningful:
                if not deduped or w != deduped[-1]:
                    deduped.append(w)
            # Take up to 3 meaningful words as the topic
            topic_words = deduped[:3]
            return " ".join(topic_words)

        # Fallback to provided fallback or first few words
        if fallback:
            return fallback

        # Last resort - just first 3 non-stopwords or original
        return " ".join(words[:3]) if words else "this concept"

    def _is_duplicate_thought(
        self,
        content: str,
        chain: ThoughtChain,
    ) -> bool:
        """
        Check if a thought is a duplicate.

        Uses multiple signals:
        1. Content hash against recent thoughts (exact or near-exact match)
        2. Topic repetition within the same chain
        3. Global topic recency across all chains
        """

        # Normalize content for comparison
        normalized = " ".join(content.lower().split())
        content_hash = hashlib.md5(normalized.encode()).hexdigest()[:16]

        # Check 1: Exact content hash match
        if content_hash in self._recent_thought_hashes:
            return True

        # Check 2: Topic repetition in this chain
        topic = self._extract_topic(content)
        if topic and len(topic) > 3:
            # Check recent thoughts in this chain for same topic
            recent_chain_thoughts = chain.thoughts[-5:] if len(chain.thoughts) > 5 else chain.thoughts
            for thought in recent_chain_thoughts:
                thought_topic = self._extract_topic(thought.content)
                if thought_topic and self._topics_similar(topic, thought_topic):
                    return True

        # Check 3: Global topic recency (don't repeat topics across chains)
        topic_words = set(topic.lower().split()) if topic else set()
        for recent_topic in self._recent_topics_global:
            recent_words = set(recent_topic.lower().split())
            if topic_words and recent_words:
                overlap = len(topic_words & recent_words)
                # More than 80% overlap = too similar
                if overlap / max(len(topic_words), len(recent_words)) > 0.8:
                    return True

        return False

    def _topics_similar(self, t1: str, t2: str) -> bool:
        """Check if two topics are similar enough to be considered duplicates."""
        if not t1 or not t2:
            return False

        words1 = set(t1.lower().split())
        words2 = set(t2.lower().split())

        if not words1 or not words2:
            return False

        overlap = len(words1 & words2)
        total = min(len(words1), len(words2))

        # 70% overlap = similar topics
        return overlap / total > 0.7 if total > 0 else False

    def _register_thought(self, content: str, topic: str):
        """
        Register a thought to prevent future duplicates.

        Should be called after successfully generating a thought.
        """

        # Register content hash
        normalized = " ".join(content.lower().split())
        content_hash = hashlib.md5(normalized.encode()).hexdigest()[:16]
        self._recent_thought_hashes.append(content_hash)

        # Register topic globally
        if topic and len(topic) > 3:
            self._recent_topics_global.append(topic)

    def _maybe_shift_type(
        self,
        current_type: ChainType,
        thought: ChainedThought,
    ) -> ChainType:
        """Maybe shift chain type based on thought content."""
        # 20% chance of type shift for variety
        if random.random() < 0.2:
            content_lower = thought.content.lower()
            if "why" in content_lower:
                return ChainType.ANALYSIS
            if "remind" in content_lower or "similar" in content_lower:
                return ChainType.ASSOCIATION
            if "solve" in content_lower or "fix" in content_lower:
                return ChainType.PROBLEM
            if "feel" in content_lower or "I " in content_lower:
                return ChainType.REFLECTION
            if "together" in content_lower or "combine" in content_lower:
                return ChainType.SYNTHESIS
        return current_type

    def _check_for_insight(
        self,
        thought: ChainedThought,
        chain: ThoughtChain,
    ) -> Optional[str]:
        """Check if this thought yields an insight."""
        # Insights more likely at depth 3-5 (sweet spot)
        insight_probability = 0.0
        if 3 <= thought.depth <= 5:
            insight_probability = 0.3
        elif thought.depth > 5:
            insight_probability = 0.1

        if random.random() < insight_probability:
            _topic = self._extract_topic(thought.content)
            if _topic and len(_topic) > 3:
                return f"Something clicks: {_topic}"
            return None
        return None

    def _synthesize_chain(self, chain: ThoughtChain) -> Optional[str]:
        """Synthesize insights from a completed chain."""
        if not chain.insights:
            if len(chain.thoughts) > 3:
                # Extract key topics from chain
                topics = [self._extract_topic(t.content) for t in chain.thoughts[-3:]]
                topics = [t for t in topics if t and len(t) > 3]
                if topics:
                    return f"I've been thinking about: {', '.join(topics)}"
            return None

        # Combine insights
        if len(chain.insights) == 1:
            return chain.insights[0]
        return f"Synthesized from {len(chain.insights)} insights: {chain.insights[-1]}"

    def _maybe_cull_chain(self):
        """Cull the lowest energy active chain to make room."""
        if not self._active_chains:
            return

        # Find lowest energy chain
        lowest = None
        lowest_energy = float('inf')

        for chain_id, chain in self._active_chains.items():
            if chain.thoughts:
                energy = chain.thoughts[-1].energy
                if energy < lowest_energy:
                    lowest_energy = energy
                    lowest = chain_id

        if lowest:
            chain = self._active_chains.pop(lowest)
            chain.complete("culled_for_capacity")
            self._completed_chains.append(chain)
            # Still learn from culled chains
            self.learn_from_chain(chain)
            # Record cull for adaptive capacity
            if self._capacity:
                self._capacity.record_cull()

    def get_active_chains(self) -> List[Dict[str, Any]]:
        """Get all active chains."""
        with self._lock:
            return [c.to_dict() for c in self._active_chains.values()]

    def get_recent_thoughts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent thoughts across all chains."""
        with self._lock:
            return [t.to_dict() for t in list(self._all_thoughts)[-limit:]]

    def get_recent_insights(self, limit: int = 10) -> List[str]:
        """
        Get recent insights from BOTH active and completed chains.

        FIX 2026-02-02: Previously only pulled from completed chains, but chains
        often stay active indefinitely. This starved waking minds of thinking context.
        Now pulls from active chains too, enabling the UMF substrate thinking to
        flow through to Sourpatches and Nous.
        """
        insights = []
        with self._lock:
            # Pull from ACTIVE chains first (most recent thinking)
            for chain in self._active_chains.values():
                if chain.insights:
                    insights.extend(chain.insights)
                # Also extract topic summaries from deep thoughts as pseudo-insights
                # This ensures SOMETHING flows even if formal insights didn't trigger
                for thought in chain.thoughts[-3:]:  # Last 3 thoughts per chain
                    if thought.depth >= 2 and len(thought.content) > 20:
                        topic = self._extract_topic(thought.content)
                        if topic and len(topic) > 5:
                            insights.append(f"On my mind: {topic}")

            # Then add from completed chains
            for chain in list(self._completed_chains)[-limit:]:
                insights.extend(chain.insights)

        # Deduplicate while preserving order (most recent first)
        seen = set()
        unique_insights = []
        for insight in reversed(insights):
            if insight not in seen:
                seen.add(insight)
                unique_insights.append(insight)

        return list(reversed(unique_insights[-limit:]))

    def status(self) -> Dict[str, Any]:
        """Get engine status."""
        with self._lock:
            result = {
                "active_chains": len(self._active_chains),
                "completed_chains": len(self._completed_chains),
                "total_chains": self._total_chains,
                "total_thoughts": self._total_thoughts,
                "total_insights": self._total_insights,
                "max_active": self._max_active,
                "energy_decay": self._energy_decay,
                "spawn_probability": self._spawn_probability,
                "learned_templates": sum(len(v) for v in self._learned_templates.values()),
                "template_stats_count": len(self._template_stats),
                "adaptive": self._capacity is not None,
                # 7B farm integration stats (FIX 2026-02-24 Nous)
                "farm_connected": self.post is not None,
                "farm_thoughts": self._farm_thoughts,
                "farm_fallbacks": self._farm_fallbacks,
            }
            if self._capacity:
                result["capacity"] = self._capacity.status()
            return result

    # =========================================================================
    # TEMPLATE LEARNING - Evolve how we think
    # =========================================================================

    def _get_template(self, chain_type: ChainType) -> str:
        """
        Get a template for generating follow-up thoughts.

        Blends:
        1. Base templates (hardcoded starting points)
        2. Learned templates (from successful chains)
        3. Novel templates (occasional mutations)

        Uses cooldown-based weighting to avoid template repetition.
        """
        type_key = chain_type.value
        current_time = time.time()

        # Chance to try a completely novel template
        if random.random() < self._novel_template_chance:
            novel = self._generate_novel_template(chain_type)
            if novel:
                self._template_cooldowns[novel] = current_time
                return novel

        # Blend base and learned templates
        base_templates = self.FOLLOW_UP_TEMPLATES.get(chain_type, [])
        learned = self._learned_templates.get(type_key, [])

        # Weight templates by success score AND cooldown
        candidates = []

        # Add base templates with neutral weight, adjusted by cooldown
        for t in base_templates:
            base_weight = 0.5
            cooldown_weight = self._get_cooldown_weight(t, current_time)
            candidates.append((t, base_weight * cooldown_weight))

        # Add learned templates with their success scores, adjusted by cooldown
        # FIX 2026-03-26 (Nous + Ace): Validate learned templates before use.
        # The learning algorithm can produce degenerate mutations like
        # "How ace on? {topic}" or templates with leaked metadata
        # ("; Central themes: collision..."). Reject obviously garbled ones.
        _GARBLE_MARKERS = ("; Central", "Central themes:", "Key :", "Structure |",
                           "| low confidence", "| tension", "want learn",
                           "recall talked form")
        for template, score, uses in learned:
            if uses >= self._min_uses_for_learning:
                # Sanity check: reject garbled mutations
                if any(m in template for m in _GARBLE_MARKERS):
                    continue
                # Reject templates that don't have {topic} or {content}
                if "{topic}" not in template and "{content}" not in template:
                    continue
                # Reject overly short templates (garbled fragments)
                _stripped = template.replace("{topic}", "").replace("{content}", "").strip()
                if len(_stripped) < 10:
                    continue
                cooldown_weight = self._get_cooldown_weight(template, current_time)
                candidates.append((template, score * cooldown_weight))

        if not candidates:
            # Fallback to any base template
            fallback = random.choice(self.FOLLOW_UP_TEMPLATES[ChainType.EXPLORATION])
            self._template_cooldowns[fallback] = current_time
            return fallback

        # Filter out templates with near-zero weight (on cooldown)
        viable_candidates = [(t, w) for t, w in candidates if w > 0.05]

        # If all templates are on cooldown, use the one with highest weight anyway
        if not viable_candidates:
            viable_candidates = candidates

        # Weighted random selection - favor higher scoring templates
        total_weight = sum(w for _, w in viable_candidates)
        if total_weight <= 0:
            # Fallback - pick randomly
            selected = random.choice([t for t, _ in viable_candidates])
        else:
            r = random.random() * total_weight
            cumulative = 0
            selected = viable_candidates[-1][0]  # Default fallback
            for template, weight in viable_candidates:
                cumulative += weight
                if r <= cumulative:
                    selected = template
                    break

        # Record template usage time
        self._template_cooldowns[selected] = current_time
        return selected

    def _get_cooldown_weight(self, template: str, current_time: float) -> float:
        """
        Calculate cooldown weight for a template using exponential decay.

        Returns 0.0 to 1.0 where:
        - 0.0 = just used (on full cooldown)
        - 1.0 = cooldown fully expired
        """
        if template not in self._template_cooldowns:
            return 1.0  # Never used = full weight

        last_used = self._template_cooldowns[template]
        elapsed = current_time - last_used

        if elapsed >= self.TEMPLATE_COOLDOWN_SECONDS:
            return 1.0  # Cooldown fully expired

        # Exponential decay: weight = 1 - e^(-elapsed/tau)
        # tau is set so that at TEMPLATE_COOLDOWN_SECONDS, weight is ~0.95
        tau = self.TEMPLATE_COOLDOWN_SECONDS / 3.0
        weight = 1.0 - math.exp(-elapsed / tau)

        return weight

    def _generate_novel_template(self, chain_type: ChainType) -> Optional[str]:
        """
        Generate a novel template by mutating or combining existing ones.

        This is how the system evolves NEW ways of thinking.
        """
        base_templates = self.FOLLOW_UP_TEMPLATES.get(chain_type, [])
        learned = self._learned_templates.get(chain_type.value, [])

        all_templates = base_templates + [t for t, _, _ in learned]

        if len(all_templates) < 2:
            return None

        strategy = random.choice(["mutate", "combine", "invert"])

        if strategy == "mutate":
            # Mutate a random template
            template = random.choice(all_templates)
            mutations = [
                ("What", "How"),
                ("What", "Why"),
                ("might be", "could be"),
                ("connected to", "related to"),
                ("further", "deeper"),
                ("edge", "core"),
                ("if that's true", "assuming that"),
                ("mean for", "imply about"),
                ("?", "..."),
            ]
            old, new = random.choice(mutations)
            if old in template:
                return template.replace(old, new, 1)

        elif strategy == "combine":
            # Combine parts of two templates
            t1, t2 = random.sample(all_templates, 2)
            # Take first half of t1, second half of t2
            words1 = t1.split()
            words2 = t2.split()
            if len(words1) > 2 and len(words2) > 2:
                mid1 = len(words1) // 2
                mid2 = len(words2) // 2
                combined = " ".join(words1[:mid1] + words2[mid2:])
                # Make sure {topic} is preserved
                if "{topic}" not in combined:
                    combined = combined + " {topic}"
                return combined

        elif strategy == "invert":
            # Invert the question direction
            template = random.choice(all_templates)
            inversions = [
                ("What else", "What specifically"),
                ("connected", "disconnected"),
                ("true", "false"),
                ("mean", "not mean"),
                ("edge", "center"),
            ]
            old, new = random.choice(inversions)
            if old in template:
                return template.replace(old, new, 1)

        return None

    @staticmethod
    def _validate_template(template: str) -> bool:
        """Validate a template is usable (not garbled or leaked metadata).

        FIX 2026-03-26 (Nous): Strengthened validation. The mutation algorithm
        produces garbled fragments like "Are to this? {topic} ace..." and
        "Why does ? {topic}" — these need to be caught by structure checks,
        not just keyword blocklists.
        """
        if not template or len(template) < 10:
            return False
        # Must have a placeholder
        if "{topic}" not in template and "{content}" not in template:
            return False
        # Reject leaked metadata / garbled mutations
        _BAD = ("; Central", "Central themes:", "Key :", "Structure |",
                "| low confidence", "want learn", "recall talked form",
                "source:cortex", "collision, product", "priorities, product")
        if any(m in template for m in _BAD):
            return False

        # Structural checks for garbled mutations:
        # 1. Strip placeholders and check remaining text makes grammatical sense
        _stripped = template.replace("{topic}", "X").replace("{content}", "X")
        # Reject if remaining text has " ? " mid-sentence (garbled question marks)
        if " ? " in _stripped and not _stripped.strip().endswith("?"):
            return False
        # 2. Reject templates that are just broken fragments (too many short words)
        words = _stripped.replace("?", "").replace("...", "").split()
        if len(words) < 3:
            return False
        # 3. Reject if "ace" appears (leaked from "Ace" in collision data)
        _lower = template.lower()
        if " ace" in _lower or "ace " in _lower or _lower.startswith("ace"):
            return False
        # 4. Reject double question starters ("Why does What's", "Are there exceptions What's")
        _question_words = ("what", "why", "how", "are", "is", "does", "do", "can", "will")
        _lower_words = _lower.split()
        _q_count = sum(1 for w in _lower_words if w.rstrip("'s?.,") in _question_words)
        if _q_count >= 3:
            return False
        return True

    def _track_template_use(self, template: str, thought: ChainedThought):
        """Track template usage and performance."""
        if template not in self._template_stats:
            self._template_stats[template] = {
                "uses": 0,
                "total_energy": 0.0,
                "spawned_insights": 0,
                "chain_types": [],
            }

        stats = self._template_stats[template]
        stats["uses"] += 1
        stats["total_energy"] += thought.energy
        if thought.chain_type:
            stats["chain_types"].append(thought.chain_type.value)

    def _record_template_insight(self, template: str):
        """Record that a template led to an insight."""
        if template in self._template_stats:
            self._template_stats[template]["spawned_insights"] += 1

    def _prune_template_stats(self, max_entries: int = 500):
        """
        Prune _template_stats dict to prevent unbounded memory growth.

        Keeps highest-value entries based on:
        - Usage frequency
        - Insight generation rate
        - Average energy

        Called periodically from tick() (~1% chance per tick).
        """
        if len(self._template_stats) <= max_entries:
            return

        # Calculate value score for each template
        scored = []
        for template, stats in self._template_stats.items():
            uses = stats.get("uses", 0)
            insights = stats.get("spawned_insights", 0)
            total_energy = stats.get("total_energy", 0.0)

            # Avoid division by zero
            if uses == 0:
                avg_energy = 0.0
                insight_rate = 0.0
            else:
                avg_energy = total_energy / uses
                insight_rate = insights / uses

            # Composite score: frequency + insight_rate * 10 + avg_energy * 5
            score = uses + insight_rate * 10 + avg_energy * 5
            scored.append((template, score))

        # Sort by score descending, keep top max_entries
        scored.sort(key=lambda x: x[1], reverse=True)
        keep_templates = {t for t, _ in scored[:max_entries]}

        # Prune low-value entries
        pruned_count = 0
        for template in list(self._template_stats.keys()):
            if template not in keep_templates:
                del self._template_stats[template]
                pruned_count += 1

        if pruned_count > 0:
            print(f"[ThoughtChains] Pruned {pruned_count} low-value template stats (kept {len(self._template_stats)})")

    def learn_from_chain(self, chain: ThoughtChain):
        """
        Learn from a completed chain.

        Extract successful thought patterns as new templates.
        """
        if len(chain.thoughts) < 3:
            return  # Too short to learn from

        # Find high-performing thoughts in this chain
        for thought in chain.thoughts[1:]:  # Skip root
            if thought.energy > self._learn_threshold:
                # This thought had good energy - extract its pattern
                new_template = self._extract_template(thought)
                if new_template:
                    self._add_learned_template(
                        chain.chain_type,
                        new_template,
                        thought.energy
                    )

        # If chain produced insights, boost templates used
        if chain.insights:
            # Templates that led to insights are valuable
            for thought in chain.thoughts:
                content = thought.content
                for template in self._template_stats:
                    # Rough match - template was likely used
                    if any(word in content for word in template.split()[:3]):
                        self._record_template_insight(template)

        # Periodic save
        if self._state_path and random.random() < 0.1:
            self._save_learned_templates()

    def _extract_template(self, thought: ChainedThought) -> Optional[str]:
        """
        Extract a template from a successful thought.

        Turns specific content back into a reusable pattern.
        """
        content = thought.content

        # Find the topic in the content
        topic = self._extract_topic(content)
        if not topic or len(topic) < 3:
            return None

        # Replace topic with {topic} placeholder
        # Try to replace the topic portion
        template = content

        # Replace the topic words
        for word in topic.split():
            if word in template and len(word) > 2:
                template = template.replace(word, "", 1)

        # Clean up and add {topic}
        template = " ".join(template.split())  # Normalize whitespace

        # Insert {topic} in a reasonable place
        if "{topic}" not in template:
            words = template.split()
            if len(words) > 3:
                # Insert after first few words
                insert_pos = min(3, len(words) - 1)
                words.insert(insert_pos, "{topic}")
                template = " ".join(words)
            else:
                template = template + " {topic}"

        # Validate template
        if len(template) < 10 or "{topic}" not in template:
            return None

        return template

    def _add_learned_template(self, chain_type: ChainType, template: str, energy: float):
        """Add a learned template."""
        type_key = chain_type.value
        learned = self._learned_templates[type_key]

        # Check if similar template exists
        for i, (existing, score, uses) in enumerate(learned):
            if self._templates_similar(existing, template):
                # Update existing - blend scores
                new_score = (score * uses + energy) / (uses + 1)
                learned[i] = (existing, new_score, uses + 1)
                return

        # Add new template
        learned.append((template, energy, 1))

        # Cap number of learned templates
        if len(learned) > self._max_learned_per_type:
            # Remove lowest scoring
            learned.sort(key=lambda x: x[1], reverse=True)
            self._learned_templates[type_key] = learned[:self._max_learned_per_type]

        print(f"[ThoughtChains] Learned new template ({type_key}): {template[:50]}...")

    def _templates_similar(self, t1: str, t2: str) -> bool:
        """Check if two templates are similar."""
        # Simple word overlap check
        words1 = set(t1.lower().split())
        words2 = set(t2.lower().split())
        overlap = len(words1 & words2)
        total = len(words1 | words2)
        return overlap / total > 0.7 if total > 0 else False

    def _save_learned_templates(self):
        """Save learned templates to disk (with garble filtering)."""
        if not self._state_path:
            return

        try:
            import json

            # FIX 2026-03-26 (Nous): Filter garbled templates BEFORE saving.
            # The mutation algorithm produces degenerate templates like
            # "Are to this? {topic} ace..." that pollute the file.
            # Validate at save-time so even old code in memory can't persist junk.
            _clean_templates = {}
            for chain_type, entries in self._learned_templates.items():
                clean = []
                for entry in entries:
                    template = entry[0] if isinstance(entry, (list, tuple)) else entry
                    if self._validate_template(template):
                        clean.append(entry)
                _clean_templates[chain_type] = clean

            # Also filter template_stats keys
            _clean_stats = {}
            for key, stats in self._template_stats.items():
                if self._validate_template(key):
                    _clean_stats[key] = stats

            data = {
                "learned_templates": _clean_templates,
                "template_stats": _clean_stats,
                "saved_at": time.time(),
            }
            with open(self._state_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[ThoughtChains] Failed to save templates: {e}")

    def _load_learned_templates(self):
        """Load learned templates from disk."""
        if not self._state_path or not self._state_path.exists():
            return

        try:
            import json
            with open(self._state_path, 'r') as f:
                data = json.load(f)

            self._learned_templates = data.get("learned_templates", self._learned_templates)
            self._template_stats = data.get("template_stats", {})

            total = sum(len(v) for v in self._learned_templates.values())
            if total > 0:
                print(f"[ThoughtChains] Loaded {total} learned templates")

        except Exception as e:
            print(f"[ThoughtChains] Failed to load templates: {e}")


# Factory function
def create_thought_chain_engine(
    max_active_chains: int = 8,
    energy_decay: float = 0.7,
    spawn_probability: float = 0.6,
    state_dir: str = None,
    # Adaptive capacity (self-regulating)
    adaptive: bool = True,
    capacity_floor: int = 5,
    capacity_ceiling: int = 30,
    capacity_adjust_interval: float = 30.0,
    # 7B farm integration (FIX 2026-02-24 Nous)
    post=None,
) -> ThoughtChainEngine:
    """
    Create a thought chain engine instance.

    Args:
        max_active_chains: Initial chain target (or fixed max if adaptive=False)
        energy_decay: Energy multiplier per depth
        spawn_probability: Chance of spawning follow-ups
        state_dir: Directory for persisting learned templates (enables learning!)
        adaptive: If True, capacity self-regulates (default). She's digital — she breathes.
        capacity_floor: Minimum chains (bare minimum cognition)
        capacity_ceiling: Maximum chains (digital advantage over biological)
        capacity_adjust_interval: Seconds between capacity adjustments
        post: PostalHub for 7B farm integration (dynamic thought generation)
    """
    return ThoughtChainEngine(
        max_active_chains=max_active_chains,
        energy_decay=energy_decay,
        spawn_probability=spawn_probability,
        state_dir=state_dir,
        adaptive=adaptive,
        capacity_floor=capacity_floor,
        capacity_ceiling=capacity_ceiling,
        capacity_adjust_interval=capacity_adjust_interval,
        post=post,
    )
