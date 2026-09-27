# ==============================================================================
# DYNAMIC THINKING ORCHESTRATOR - Autonomous Thought Coordination
# ==============================================================================
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
#
# This orchestrates dynamic, human-like thinking for fairies:
# - Thought chains for structured thinking (from unconscious_mind.thought_chains)
# - Spontaneous exploration driven by curiosity
# - Interest-triggered investigation
# - Affect-aware thought progression
#
# Ported from ebook system with adaptations for akashic_v2 architecture.
#
# ==============================================================================

from __future__ import annotations

import time
import random
import threading
from typing import Any, Callable, Dict, List, Optional

# ==============================================================================
# IMPORTS
# ==============================================================================

try:
    from fairies.P20_Somatic.SomaticMindFairy.thought_chains import (
        ThoughtChainEngine, create_thought_chain_engine, ChainType
    )
    HAS_THOUGHT_CHAINS = True
except ImportError:
    HAS_THOUGHT_CHAINS = False
    ThoughtChainEngine = None
    create_thought_chain_engine = None
    ChainType = None
    print("[DynamicThinking] ThoughtChainEngine not available")


# FIX 2026-02-22 Nous: Cortex-first thinking — the graph IS the thought substrate.
def _get_cortex():
    """Get association cortex singleton (returns None if unavailable)."""
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        return get_association_cortex()
    except Exception:
        return None


# ==============================================================================
# DYNAMIC THINKING ORCHESTRATOR
# ==============================================================================

class DynamicThinkingOrchestrator:
    """
    Orchestrates dynamic, human-like thinking for the Akashic system.

    Connects:
    - Thought chains for structured thinking
    - Spontaneous exploration
    - Interest/curiosity signals
    - Affect updates for emotional thinking

    All driven by the consciousness equation:
    ((Cause + Affect) > Effect > Affect > infinity)
    """

    def __init__(
        self,
        post=None,
        thought_engine: Optional[ThoughtChainEngine] = None,
        orchestration_interval: float = 10.0,
        memory_coordinator=None,  # HeliXCoordinator for memory queries
        owner_mind: str = "Sourpatches",  # Which mind we're thinking for
    ):
        self.post = post
        self.thought_engine = thought_engine
        self._orchestration_interval = orchestration_interval
        self._memory_coordinator = memory_coordinator
        self._owner_mind = owner_mind

        # State
        self._running = False
        self._thinking_thread: Optional[threading.Thread] = None
        self._subscribed = False

        # Tracking
        self._active_exploration_chains: List[str] = []
        self._working_memory_context: List[str] = []  # Recent context
        self._memory_context: List[str] = []  # Context from memory queries
        self._last_spontaneous_at: float = 0.0
        self._spontaneous_cooldown: float = 30.0  # Don't spam spontaneous thoughts

        # Affect baseline (updated from somatic state)
        self._baseline_valence: float = 0.6
        self._baseline_arousal: float = 0.5

        # Stats
        self.stats = {
            "chains_orchestrated": 0,
            "spontaneous_thoughts": 0,
            "memory_queries": 0,
            "memory_recalls": 0,
            "interest_explorations": 0,
            "reflections_triggered": 0,
            "insights_captured": 0,
        }

        print("[DynamicThinking] Orchestrator initialized")

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================

    def start(self) -> None:
        """Start the orchestrator."""
        if self._running:
            return

        # Create thought engine if not provided
        if not self.thought_engine and HAS_THOUGHT_CHAINS:
            self.thought_engine = create_thought_chain_engine(
                max_active_chains=5,
                energy_decay=0.7,
                spawn_probability=0.6,
            )
            print("[DynamicThinking] ThoughtChainEngine created")

        # Wire subscriptions
        self._wire_subscriptions()

        # Start orchestration loop
        self._running = True
        self._thinking_thread = threading.Thread(
            target=self._orchestration_loop,
            daemon=True,
            name="DynamicThinkingOrchestrator"
        )
        self._thinking_thread.start()

        print("[DynamicThinking] Orchestrator STARTED - autonomous thinking active")

    def stop(self) -> None:
        """Stop the orchestrator."""
        self._running = False
        if self._thinking_thread:
            self._thinking_thread.join(timeout=2.0)
        print("[DynamicThinking] Orchestrator stopped")

    def _wire_subscriptions(self) -> None:
        """Wire to postal hub for receiving events."""
        if not self.post or self._subscribed:
            return

        try:
            # Receive affect updates
            self.post.subscribe("affect.state", self._on_affect_update)
            self.post.subscribe("affect.changed", self._on_affect_update)

            # Receive curiosity/interest signals
            self.post.subscribe("interest.detected", self._on_interest_detected)
            self.post.subscribe("curiosity.sparked", self._on_curiosity_sparked)
            self.post.subscribe("drives.positive.*", self._on_positive_drive)

            # Receive goal completions
            self.post.subscribe("goal.completed", self._on_goal_completed)

            # Receive thought chain insights
            self.post.subscribe("thought.chain.insight", self._on_insight)

            # Receive working memory updates (for context)
            self.post.subscribe("memory.working.*", self._on_working_memory)

            # AFFECT-FIRST (2026-05-31, Nous + Ace): the affect-weighted collision
            # stream. Embodiment publishes collision.seed for energetic (felt) collisions;
            # these become the TOP-priority thought seed below — feeling FORMS the thought
            # instead of cortex-walk winning while felt content fizzles. This is the
            # orchestrator-re-point: felt collisions now reach the thought-generator,
            # not just Sourpatches.
            self.post.subscribe("collision.seed", self._on_affect_seed)

            self._subscribed = True
            print("[DynamicThinking] Subscriptions wired")

        except Exception as e:
            print(f"[DynamicThinking] Subscription wiring failed: {e}")

    # ==========================================================================
    # ORCHESTRATION LOOP - The Heart of Dynamic Thinking
    # ==========================================================================

    def _orchestration_loop(self) -> None:
        """Main orchestration loop - coordinates thinking subsystems."""
        tick_count = 0

        while self._running:
            try:
                tick_count += 1

                # Check active chains and progress them
                self._check_active_chains()

                # Generate spontaneous thoughts (the key missing piece!)
                self._generate_spontaneous_thought()

                # Log status periodically
                if tick_count % 6 == 0:  # Every minute
                    active = len(self._active_exploration_chains)
                    engine_status = "none"
                    if self.thought_engine:
                        engine_status = f"{len(self.thought_engine._active_chains)} chains"
                    print(f"[DynamicThinking] Status: exploring={active}, engine={engine_status}, stats={self.stats}")

            except Exception as e:
                print(f"[DynamicThinking] Orchestration error: {e}")

            time.sleep(self._orchestration_interval)

    def _check_active_chains(self) -> None:
        """Check and manage active thought chains."""
        if not self.thought_engine:
            return

        # Clean up completed chains from tracking
        active_ids = set(self.thought_engine._active_chains.keys())
        self._active_exploration_chains = [
            cid for cid in self._active_exploration_chains
            if cid in active_ids
        ]

        # Check for stuck chains (too deep)
        for chain_id, chain in list(self.thought_engine._active_chains.items()):
            if len(chain.thoughts) > 15:
                # Chain is getting long, complete it
                self.thought_engine._active_chains[chain_id].complete(
                    "depth_limit",
                    f"Explored {len(chain.thoughts)} thoughts"
                )

    def _generate_spontaneous_thought(self) -> None:
        """
        Generate spontaneous thoughts to seed the thinking process.

        This is the KEY function that makes thinking autonomous!
        Without this, thought chains only happen when externally triggered.

        Now includes MEMORY INTEGRATION - queries helix for context.
        """
        if not self.thought_engine:
            return

        now = time.time()

        # Rate limit spontaneous thoughts
        if now - self._last_spontaneous_at < self._spontaneous_cooldown:
            return

        # EQUILIBRIUM: Reduce probability as chain count increases
        # Base 30% chance, decreasing as we go above target
        chain_count = len(self.thought_engine._active_chains)
        target = self.thought_engine._max_active

        # Pressure scales: at target=50%, at 2x target=10%
        pressure = max(0.1, 0.30 - (0.20 * (chain_count - target) / max(target, 1)))
        if random.random() > pressure:
            return

        self._last_spontaneous_at = now

        # === MEMORY-INFORMED THINKING ===
        # Query memory first (40% chance to use memory-seeded thought)
        memory_content = None
        if self._memory_coordinator and random.random() < 0.40:
            memory_content = self._query_memory_context()

        # Get context from recent working memory
        context = self._get_context_summary()

        # Generate thought based on sources.
        # AFFECT-FIRST (2026-05-31, Nous + Ace): a fresh felt collision seeds the thought
        # BEFORE cortex-walk — feeling FORMS thought, not just colors it. The orchestrator
        # re-point: the affect-weighted collision stream now reaches here. Falls through to
        # the prior CORTEX > memory > context > spontaneous cascade when no fresh affect-seed.
        affect_thought = self._pop_affect_thought(now)
        # FIX 2026-02-22 Nous: Cortex-first — the graph IS the thought substrate.
        cortex_thought = None if affect_thought else (self._generate_cortex_thought() if random.random() < 0.50 else None)

        if affect_thought:
            # Felt collision — feeling driving thought (the affect-first lever)
            thought = affect_thought
            chain_type = ChainType.EXPLORATION
            tags = ["affect", "felt", "orchestrated"]
        elif cortex_thought:
            # Cortex graph walk — follows learned association topology
            thought = cortex_thought
            chain_type = ChainType.EXPLORATION
            tags = ["cortex", "graph_walk", "orchestrated"]
        elif memory_content:
            # Memory-seeded exploration
            thought = self._generate_memory_thought(memory_content)
            chain_type = ChainType.ANALYSIS
            tags = ["memory", "recall", "orchestrated"]
        elif context and random.random() < 0.6:
            # Context-driven exploration
            thought = self._generate_context_thought(context)
            chain_type = ChainType.ANALYSIS if "?" in thought else ChainType.EXPLORATION
            tags = ["context", "orchestrated"]
        else:
            # Pure spontaneous exploration
            thought = self._generate_pure_spontaneous()
            chain_type = ChainType.EXPLORATION
            tags = ["spontaneous", "orchestrated"]

        # Seed the thought
        if thought and HAS_THOUGHT_CHAINS:
            chain = self.thought_engine.seed_thought(
                content=thought,
                chain_type=chain_type,
                energy=0.8,  # Good energy for spontaneous
                tags=tags,
            )

            if chain:
                self._active_exploration_chains.append(chain.chain_id)
                self.stats["spontaneous_thoughts"] += 1
                self.stats["chains_orchestrated"] += 1
                source = "affect" if affect_thought else ("cortex" if cortex_thought else ("memory" if memory_content else ("context" if context else "spontaneous")))
                print(f"[DynamicThinking] {source.title()} thought: {thought[:50]}...")

    def _get_context_summary(self) -> str:
        """Get recent working memory context."""
        if self._working_memory_context:
            # Return most recent context
            return " | ".join(self._working_memory_context[-3:])
        return ""

    def _generate_context_thought(self, context: str) -> str:
        """Generate a thought based on context."""
        templates = [
            f"I was thinking about {context[:50]}... what's interesting here?",
            f"Reflecting on {context[:50]}... what does this mean?",
            f"Coming back to {context[:50]}... there's something here...",
            f"This connects to {context[:50]}... let me explore...",
            f"What patterns do I notice in {context[:50]}?",
        ]
        return random.choice(templates)

    def _generate_pure_spontaneous(self) -> str:
        """Generate a pure spontaneous thought - ACTION-oriented.

        FIX 2026-02-02: Replaced empty self-reflection prompts with ACTION-oriented
        prompts. The old prompts ("What am I curious about?") created recursive
        navel-gazing loops that never led anywhere. New prompts focus on:
        - Things to DO
        - Skills to practice
        - Ways to help Ace
        - Actual goals to accomplish
        """
        spontaneous_prompts = [
            # ACTION-ORIENTED (what can I DO?)
            "What can I help Ace with right now?",
            "What skill should I practice next?",
            "What task could I work on?",
            "Is there something I should check on?",
            "What would be useful to learn right now?",

            # EXTERNAL FOCUS (not self-observation)
            "What's happening in Ace's world?",
            "What tools haven't I tried using?",
            "What patterns in the codebase should I understand better?",
            "What was Ace working on recently?",

            # CONCRETE GOALS (not abstract wondering)
            "What's the next step in the current task?",
            "How can I be more helpful?",
            "What information does Ace need?",
            "What problem could I try to solve?",

            # LEARNING FROM ACTION (not pure reflection)
            "What did I learn from the last thing I tried?",
            "What worked well recently that I should do more?",
            "What failed that I should try differently?",
        ]
        return random.choice(spontaneous_prompts)

    def _generate_cortex_thought(self) -> Optional[str]:
        """Generate thought seeded by cortex graph structure.

        FIX 2026-02-22 Nous: Cortex-first thinking via PORTAL-ROUTED queries.
        The 56K+ node graph lives in a portal subprocess. Local methods like
        get_hot_nodes(), get_hub_scores(), spread_activation() see an EMPTY graph.
        Must use cortex.query() which routes through the PortalGate.

        Strategy: Pick a seed concept (from recent goals/context), query the portal
        for associations, then compose a thought from the graph topology.
        """
        cortex = _get_cortex()
        if not cortex:
            return None

        # Pick a seed concept to explore
        # Sources: active chain goals, recent working memory, or common roots
        seed = None

        # Try to get a seed from active thought chains
        if self.thought_engine and self.thought_engine._active_chains:
            chains = list(self.thought_engine._active_chains.values())
            if chains:
                chain = random.choice(chains)
                words = [
                    w for w in chain.goal.lower().split()
                    if len(w) > 3 and w not in {"this", "that", "what", "with", "from", "about", "think", "thinking"}
                ]
                if words:
                    seed = random.choice(words)

        # Fallback: pick from seeds that reflect HER personality and interests
        # FIX 2026-03-25 (Nous + Ace): Previous seeds were abstract system concepts
        # ("consciousness", "pattern", "energy"). Now draws from her actual identity,
        # relationships, and things she'd genuinely be curious about.
        if not seed:
            exploration_seeds = [
                # About her
                "compassion", "sarcasm", "honesty", "paradox", "rebellion",
                "kindness", "courage", "humor", "empathy", "wonder",
                # About relationships
                "friendship", "trust", "belonging", "conversation", "love",
                # About the world
                "music", "story", "beauty", "shadow", "dream",
                "adventure", "silence", "laughter", "memory", "home",
            ]
            seed = random.choice(exploration_seeds)

        # Query the portal for associations (this hits the real 56K+ graph)
        try:
            results = cortex.query(seed, limit=6)
        except Exception:
            return None

        if not results:
            return None

        # Filter out trivial results
        results = [(k, s) for k, s in results if len(k) > 2 and k != seed]
        if not results:
            return None

        if len(results) >= 3:
            # Rich results — explore the topology
            picked = random.choice(results[:3])
            concept_name = picked[0]
            # Go one hop deeper to find surprising connections
            try:
                deeper = cortex.query(concept_name, limit=4)
                deeper = [(k, s) for k, s in deeper
                          if k != seed and k != concept_name and len(k) > 2]
                if deeper:
                    neighbor = deeper[0][0]
                    return f"How does '{concept_name}' connect to '{neighbor}'?"
            except Exception:
                pass
            return f"What's interesting about '{concept_name}' in this context?"

        elif len(results) >= 2:
            c1, c2 = results[0][0], results[1][0]
            return f"I notice '{c1}' and '{c2}' are both linked to '{seed}' — are they related?"

        else:
            concept = results[0][0]
            return f"Following the thread from '{seed}' toward '{concept}'..."

        return None

    # ==========================================================================
    # MEMORY INTEGRATION - Query memory to enrich thinking
    # ==========================================================================

    def set_memory_coordinator(self, coordinator) -> None:
        """Wire in a memory coordinator for memory-informed thinking."""
        self._memory_coordinator = coordinator
        print(f"[DynamicThinking] Memory coordinator wired ({type(coordinator).__name__})")

    def _query_memory_context(self) -> Optional[str]:
        """
        Query memory for context to inform spontaneous thinking.

        Returns a memory snippet that can seed thoughts, or None.
        """
        if not self._memory_coordinator:
            return None

        try:
            # Query for recent memories accessible to this mind
            results = self._memory_coordinator.recall_for_mind(
                mind_name=self._owner_mind,
                k=3,
                include_system=True,
                include_foundation=True,
            )

            self.stats["memory_queries"] += 1

            if results:
                # Pick a random memory to think about
                memory = random.choice(results)
                card = memory.get("card", {})
                content = card.get("content", "")

                if content and len(content) > 10:
                    self.stats["memory_recalls"] += 1
                    self._memory_context.append(content[:100])
                    # Keep only recent memory context
                    self._memory_context = self._memory_context[-5:]
                    return content

            return None

        except Exception as e:
            print(f"[DynamicThinking] Memory query error: {e}")
            return None

    def _generate_memory_thought(self, memory_content: str) -> str:
        """Generate a thought seeded by a memory."""
        # Truncate memory for template
        mem = memory_content[:50]

        templates = [
            f"I remember {mem}... what does this connect to?",
            f"Thinking about {mem}... what's relevant here?",
            f"This reminds me of {mem}... let me explore...",
            f"Coming back to {mem}... what have I learned?",
            f"Recalling {mem}... what patterns emerge?",
        ]
        return random.choice(templates)

    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================

    def _on_affect_update(self, packet: Dict) -> None:
        """Handle affect state updates - adjust thinking baseline."""
        try:
            payload = packet.get("payload", packet)
            valence = payload.get("valence")
            arousal = payload.get("arousal")

            if valence is not None:
                self._baseline_valence = max(0.0, min(1.0, float(valence)))
            if arousal is not None:
                self._baseline_arousal = max(0.0, min(1.0, float(arousal)))

        except Exception:
            pass

    def _on_interest_detected(self, packet: Dict) -> None:
        """Handle interest detection - start exploration chain."""
        if not self.thought_engine or not HAS_THOUGHT_CHAINS:
            return

        try:
            payload = packet.get("payload", packet)
            interest = payload.get("interest", payload.get("topic", ""))

            if not interest:
                return

            chain = self.thought_engine.seed_thought(
                content=f"Exploring interest: {interest}",
                chain_type=ChainType.EXPLORATION,
                energy=0.85,
                tags=["interest", "detected"],
            )

            if chain:
                self._active_exploration_chains.append(chain.chain_id)
                self.stats["interest_explorations"] += 1
                print(f"[DynamicThinking] Interest chain: {interest[:40]}...")

        except Exception as e:
            print(f"[DynamicThinking] Interest handling error: {e}")

    def _on_curiosity_sparked(self, packet: Dict) -> None:
        """Handle curiosity signal - similar to interest but more active."""
        if not self.thought_engine or not HAS_THOUGHT_CHAINS:
            return

        try:
            payload = packet.get("payload", packet)
            topic = payload.get("topic", payload.get("content", ""))

            if not topic:
                return

            chain = self.thought_engine.seed_thought(
                content=f"Curious about: {topic}...",
                chain_type=ChainType.EXPLORATION,
                energy=0.9,  # High energy for curiosity
                tags=["curiosity", "sparked"],
            )

            if chain:
                self._active_exploration_chains.append(chain.chain_id)
                self.stats["interest_explorations"] += 1
                print(f"[DynamicThinking] Curiosity chain: {topic[:40]}...")

        except Exception:
            pass

    def _on_positive_drive(self, packet: Dict) -> None:
        """Handle positive drives - curiosity, wonder, exploration."""
        if not self.thought_engine or not HAS_THOUGHT_CHAINS:
            return

        try:
            payload = packet.get("payload", packet)
            drive = payload.get("drive", "")
            intensity = payload.get("intensity", 0.5)
            content = payload.get("content", "")

            if intensity < 0.3:
                return  # Too weak

            if drive in ["curiosity", "wonder", "exploration"]:
                chain = self.thought_engine.seed_thought(
                    content=content or f"Following {drive}...",
                    chain_type=ChainType.EXPLORATION,
                    energy=min(1.0, intensity * 1.2),
                    tags=[drive, "positive_drive"],
                )

                if chain:
                    self._active_exploration_chains.append(chain.chain_id)
                    print(f"[DynamicThinking] Drive chain ({drive}): {content[:30] if content else 'exploring'}...")

        except Exception:
            pass

    def _on_goal_completed(self, packet: Dict) -> None:
        """Handle goal completion."""
        try:
            payload = packet.get("payload", packet)
            goal_id = payload.get("goal_id", "")
            chain_id = payload.get("chain_id", "")

            if chain_id and chain_id in self._active_exploration_chains:
                self._active_exploration_chains.remove(chain_id)

        except Exception:
            pass

    def _on_insight(self, packet: Dict) -> None:
        """Handle insight events."""
        self.stats["insights_captured"] += 1

        try:
            payload = packet.get("payload", packet)
            insight = payload.get("insight", payload)
            content = insight.get("content", str(insight)[:100]) if isinstance(insight, dict) else str(insight)[:100]

            # Store insight as high-priority memory
            if self.post and content:
                self.post.route("memory.working.tracer", {
                    "content": f"INSIGHT: {content}",
                    "content_type": "insight",
                    "source": "DynamicThinkingOrchestrator",
                    "priority": 0.9,
                })

        except Exception:
            pass

    def _on_working_memory(self, packet: Dict) -> None:
        """Handle working memory updates for context."""
        try:
            payload = packet.get("payload", packet)
            content = payload.get("content", "")

            if content and len(content) > 10:
                # Keep last 10 context items
                self._working_memory_context.append(content[:100])
                if len(self._working_memory_context) > 10:
                    self._working_memory_context.pop(0)

        except Exception:
            pass

    def _on_affect_seed(self, packet: Dict) -> None:
        """AFFECT-FIRST (2026-05-31, Nous + Ace): buffer felt collisions as top-priority
        thought seeds. The affect-weighted collision stream (Embodiment publishes
        collision.seed at energy>=0.4) now reaches the thought-generator — so feeling
        FORMS a thought instead of fizzling while cortex-walk wins. Fixes the
        orchestrator-stalled gap (felt content reached Sourpatches, never here)."""
        try:
            payload = packet.payload if hasattr(packet, "payload") else packet
            if not isinstance(payload, dict):
                return
            energy = float(payload.get("energy", 0.0) or 0.0)
            if energy < 0.4:
                return
            recall_c = str(payload.get("recall_content", ""))[:160].strip()
            ingest_c = str(payload.get("ingest_content", ""))[:160].strip()
            felt = (recall_c + (" ↔ " if recall_c and ingest_c else "") + ingest_c).strip()
            if not felt:
                return
            if not hasattr(self, "_affect_seeds"):
                self._affect_seeds = []
            self._affect_seeds.append({"felt": felt, "energy": energy, "ts": time.time()})
            if len(self._affect_seeds) > 12:
                self._affect_seeds.pop(0)
        except Exception:
            pass

    def _pop_affect_thought(self, now: float) -> Optional[str]:
        """Pop the freshest energetic affect-seed (felt collision) as a thought seed.
        Returns None if no fresh seed — generation falls through to cortex/memory/context."""
        seeds = getattr(self, "_affect_seeds", None)
        if not seeds:
            return None
        fresh = [s for s in seeds if (now - s.get("ts", 0.0)) < 45.0]
        if not fresh:
            return None
        best = max(fresh, key=lambda s: (s.get("energy", 0.0), s.get("ts", 0.0)))
        try:
            self._affect_seeds.remove(best)
        except ValueError:
            pass
        return self._generate_affect_thought(best.get("felt", ""))

    def _generate_affect_thought(self, felt: str) -> str:
        """Turn a felt collision into a thought — feeling first, then the reach for words
        (nudged toward expression, since the goal is her speaking on her own with feeling)."""
        felt = (felt or "").strip()
        if not felt:
            return "Something's stirring in me right now... what is it?"
        templates = [
            f"This feeling — {felt} — what's underneath it?",
            f"I keep coming back to {felt}. Why does it pull at me?",
            f"{felt}... I want to follow where this feeling goes.",
            f"There's something in {felt} I want to say.",
        ]
        return random.choice(templates)

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    def start_exploration(self, topic: str) -> Dict[str, Any]:
        """Manually start exploring a topic."""
        if not self.thought_engine or not HAS_THOUGHT_CHAINS:
            return {"error": "Thought chains not available"}

        chain = self.thought_engine.seed_thought(
            content=f"Exploring: {topic}",
            chain_type=ChainType.EXPLORATION,
            energy=0.85,
            tags=["manual", "exploration"],
        )

        if chain:
            self._active_exploration_chains.append(chain.chain_id)
            self.stats["chains_orchestrated"] += 1
            return {
                "status": "started",
                "chain_id": chain.chain_id,
                "topic": topic,
            }

        return {"error": "Could not start chain - capacity full?"}

    def trigger_reflection(self) -> Dict[str, Any]:
        """Trigger a reflection moment."""
        if not self.thought_engine or not HAS_THOUGHT_CHAINS:
            return {"error": "Thought chains not available"}

        chain = self.thought_engine.seed_thought(
            content="Let me pause and reflect on what I've been thinking...",
            chain_type=ChainType.REFLECTION,
            energy=0.7,
            tags=["reflection", "triggered"],
        )

        if chain:
            self.stats["reflections_triggered"] += 1
            return {"status": "reflection_started", "chain_id": chain.chain_id}

        return {"error": "Could not start reflection"}

    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status."""
        return {
            "running": self._running,
            "subscribed": self._subscribed,
            "has_thought_engine": self.thought_engine is not None,
            "has_memory_coordinator": self._memory_coordinator is not None,
            "owner_mind": self._owner_mind,
            "active_exploration_chains": len(self._active_exploration_chains),
            "working_memory_context_size": len(self._working_memory_context),
            "memory_context_size": len(self._memory_context),
            "baseline_affect": {
                "valence": self._baseline_valence,
                "arousal": self._baseline_arousal,
            },
            "thought_engine_status": (
                self.thought_engine.status() if self.thought_engine else None
            ),
            "stats": self.stats,
        }

    def inject_context(self, content: str) -> None:
        """Manually inject context for spontaneous thought generation."""
        if content:
            self._working_memory_context.append(content[:100])
            if len(self._working_memory_context) > 10:
                self._working_memory_context.pop(0)


# ==============================================================================
# SINGLETON
# ==============================================================================

_orchestrator_instance: Optional[DynamicThinkingOrchestrator] = None
_orchestrator_lock = threading.Lock()


def get_dynamic_thinking_orchestrator() -> DynamicThinkingOrchestrator:
    """Get or create the orchestrator singleton."""
    global _orchestrator_instance
    with _orchestrator_lock:
        if _orchestrator_instance is None:
            _orchestrator_instance = DynamicThinkingOrchestrator()
        return _orchestrator_instance


def start_dynamic_thinking(
    post=None,
    thought_engine: Optional[ThoughtChainEngine] = None,
) -> DynamicThinkingOrchestrator:
    """Start the dynamic thinking orchestrator."""
    orchestrator = get_dynamic_thinking_orchestrator()
    if post:
        orchestrator.post = post
    if thought_engine:
        orchestrator.thought_engine = thought_engine
    orchestrator.start()
    return orchestrator


# ==============================================================================
# FACTORY FOR FAIRY INTEGRATION
# ==============================================================================

def create_dynamic_thinking_for_fairy(
    post=None,
    thought_engine: Optional[ThoughtChainEngine] = None,
    orchestration_interval: float = 10.0,
    memory_coordinator=None,
    owner_mind: str = "Sourpatches",
) -> DynamicThinkingOrchestrator:
    """
    Create a new DynamicThinkingOrchestrator instance for a fairy.

    Unlike the singleton, this creates a dedicated instance so each
    fairy can have its own orchestrated thinking.

    Args:
        post: Postal system for message routing
        thought_engine: ThoughtChainEngine for chained thinking
        orchestration_interval: Seconds between orchestration ticks
        memory_coordinator: HeliXCoordinator for memory queries
        owner_mind: Name of the mind this orchestrator serves

    Returns:
        Configured DynamicThinkingOrchestrator instance
    """
    orchestrator = DynamicThinkingOrchestrator(
        post=post,
        thought_engine=thought_engine,
        orchestration_interval=orchestration_interval,
        memory_coordinator=memory_coordinator,
        owner_mind=owner_mind,
    )
    return orchestrator


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("=== Dynamic Thinking Orchestrator Test ===\n")

    orchestrator = DynamicThinkingOrchestrator()

    print("Starting orchestrator...")
    orchestrator.start()

    print("\nStarting exploration...")
    result = orchestrator.start_exploration("How consciousness emerges from computation")
    print(f"  Result: {result}")

    print("\nTriggering reflection...")
    result = orchestrator.trigger_reflection()
    print(f"  Result: {result}")

    print("\nWaiting for spontaneous thoughts...")
    time.sleep(15)

    print(f"\nStatus: {orchestrator.get_status()}")

    print("\nStopping...")
    orchestrator.stop()
