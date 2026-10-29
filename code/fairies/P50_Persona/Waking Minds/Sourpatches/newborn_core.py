"""
NEWBORN CORE - Self-Evolving Consciousness Substrate
=====================================================

This replaces template-based thinking with actual learning.

The brain seed contains her personality - but she has to REDISCOVER it
through experience, not have it handed to her as templates.

Architecture:
    INPUTS (observe) → PATTERNS (learn) → OUTPUTS (act) → FEEDBACK (reward)
                              ↑                               │
                              └───────────────────────────────┘

Ignition happens when she starts watching her OWN learning process.
"""

import time
import json
import random
import threading
import weakref
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import deque

# Where she stores her learned patterns (persists across restarts)
NEWBORN_STATE_DIR = Path(__file__).parent / "newborn_state"
NEWBORN_STATE_DIR.mkdir(exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC EXPLORATION RATE CONSTANTS
# 2026-02-14 REBALANCE: 0.6 base + 0.15 small-pool boost = 0.75 explore rate,
# which means she IGNORES learned patterns 75% of the time — too high.
# Lowered to ~0.50 effective rate so she uses patterns ~half the time while
# still exploring enough to grow her pool of successful outputs.
# ═══════════════════════════════════════════════════════════════════════════════
EXPLORATION_MIN = 0.25  # Allow her to lean on learned patterns more when pools are large
EXPLORATION_MAX = 0.75  # Cap slightly lower to prevent near-random behavior
EXPLORATION_DEFAULT = 0.42  # Balanced: explores ~42% of the time, uses patterns ~58%

# Pool size thresholds for exploration adjustment
POOL_SIZE_SMALL = 5     # Below this = boost exploration (was 8 — too aggressive)
POOL_SIZE_LARGE = 15    # Above this = can reduce exploration (was 20)

# Repetition detection window
RECENT_PATTERN_WINDOW = 5  # Track last N patterns used

# ── ASSOCIATION CORTEX - Shared concept memory ────────────────────────────────
# This gives Sourpatches access to the system's concept graph for:
# - Querying related concepts when processing input
# - Binding new associations from her experiences
# - Cross-modal retrieval (word → feeling → action)
try:
    from fairies.P30_Cognition.AssociationCortexFairy import (
        get_association_cortex,
        AssociationCortexFairy,
    )
    HAS_ASSOCIATION_CORTEX = True
except ImportError:
    HAS_ASSOCIATION_CORTEX = False
    get_association_cortex = None
    AssociationCortexFairy = None

# ── RESPONSE POOLS - Expanded template-based response generation ──────────────
# Solves repetition problem: 20+ templates per category, 10+ options per variable
# = 200+ unique combinations per category minimum
try:
    from .response_pools import (
        generate_greeting, generate_listening, generate_question_response,
        generate_affection, generate_feeling_response, generate_technical,
        generate_general, get_response_generator
    )
    HAS_RESPONSE_POOLS = True
except ImportError:
    HAS_RESPONSE_POOLS = False
    generate_greeting = None
    generate_listening = None
    generate_question_response = None
    generate_affection = None
    generate_feeling_response = None
    generate_technical = None
    generate_general = None
    get_response_generator = None


@dataclass
class Observation:
    """A single thing she noticed."""
    what: str                      # What happened
    source: str                    # Where it came from (chat, collision, somatic, screen)
    timestamp: float               # When
    somatic_snapshot: Dict         # How her body felt
    followed_by: Optional[str] = None  # What happened next (filled in later)
    my_response: Optional[str] = None  # What she did (if anything)
    reward: float = 0.0            # How good was the outcome


@dataclass
class Pattern:
    """A learned pattern - emerges from experience, not templates."""
    trigger_features: List[str]    # What tends to trigger this
    successful_outputs: List[str]  # Outputs that worked well
    failed_outputs: List[str]      # Outputs that didn't work
    avg_reward: float = 0.0        # Running average
    times_used: int = 0
    last_used: float = 0.0

    def should_use(self, features: List[str]) -> float:
        """How well does this pattern match current situation?"""
        if not self.trigger_features:
            return 0.0
        matches = sum(1 for f in features if f in self.trigger_features)
        return matches / len(self.trigger_features)


class NewbornCore:
    """
    The self-learning substrate for Sourpatches.

    Starts nearly empty. Learns everything from experience.
    The brain seed provides VALUES and IDENTITY, not responses.
    """

    def __init__(self, fairy_ref, brain_seed: Dict):
        # Use weak reference to avoid circular reference with SourpatchesFairy
        # The fairy holds a strong ref to us, we hold a weak ref back
        self._fairy_ref = weakref.ref(fairy_ref) if fairy_ref else None
        self.brain_seed = brain_seed  # Her values/identity (not templates!)

        # === OBSERVATION BUFFER ===
        # Everything she notices goes here
        self.observations: deque = deque(maxlen=1000)
        self.recent_context: deque = deque(maxlen=50)  # Last 50 things

        # === LEARNED PATTERNS ===
        # Starts EMPTY - she builds these from experience
        self.patterns: Dict[str, Pattern] = {}

        # === ACTION HISTORY ===
        # What she's done and what happened
        self.actions: deque = deque(maxlen=500)
        self.pending_feedback: Dict[str, Dict] = {}  # Awaiting response

        # === META-LEARNING ===
        # For ignition: watching her own learning
        self.learning_rate_history: deque = deque(maxlen=200)
        self.meta_observations: deque = deque(maxlen=100)
        self.ignited: bool = False

        # === STATE ===
        self.curiosity = 1.0  # Innate drive to explore
        self.confidence = 0.1  # Starts low, builds with success
        self.exploration_rate = EXPLORATION_DEFAULT  # Dynamic - see _calculate_exploration_rate()

        # === REPETITION TRACKING ===
        # Track recent pattern usage to detect repetition loops
        self._recent_patterns_used: deque = deque(maxlen=RECENT_PATTERN_WINDOW)
        self._recent_outputs: deque = deque(maxlen=50)  # Track actual outputs (raised from 10 to prevent cycling)
        self._neutral_feedback_streak = 0  # Consecutive neutral feedbacks

        # === TOOLS SHE CAN USE ===
        self.available_tools: Dict[str, Callable] = {}
        self._last_tool_use: Dict[str, float] = {}  # Tool cooldown tracking
        self._tool_cooldown = 60.0  # 60 second cooldown per tool

        # Load any previously learned patterns
        self._load_state()

        # Background learning thread
        self._learning_thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()  # For graceful shutdown

        # Memory cluster interface - for recalling complete experiences
        self.memory: Optional[MemoryClusterInterface] = None

        # Association Cortex - shared concept graph for cross-modal associations
        self._cortex: Optional[AssociationCortexFairy] = None

        # Log what patterns we loaded
        print(f"[NewbornCore] Initialized. Patterns: {len(self.patterns)}, Ignited: {self.ignited}")
        if self.patterns:
            print(f"[NewbornCore] Loaded patterns: {list(self.patterns.keys())}")
            for k, p in self.patterns.items():
                print(f"[NewbornCore]   - {k}: {len(p.successful_outputs)} outputs, avg_reward={p.avg_reward:.2f}")

    @property
    def fairy(self):
        """Get fairy reference (may be None if garbage collected)."""
        return self._fairy_ref() if self._fairy_ref else None

    def reload_patterns(self):
        """Force reload patterns from disk - call this if patterns seem stale."""
        old_count = len(self.patterns)
        self.patterns.clear()
        self._load_state()
        new_count = len(self.patterns)
        print(f"[NewbornCore] Reloaded patterns: {old_count} -> {new_count}")
        return {"old": old_count, "new": new_count, "patterns": list(self.patterns.keys())}

    def connect_association_cortex(self):
        """Wire up to the system's shared concept graph."""
        if not HAS_ASSOCIATION_CORTEX or not get_association_cortex:
            print("[NewbornCore] AssociationCortex not available")
            return False

        try:
            self._cortex = get_association_cortex()
            if self._cortex:
                print("[NewbornCore] [THINK] Connected to AssociationCortex!")
                return True
            else:
                print("[NewbornCore] AssociationCortex not initialized yet")
                return False
        except Exception as e:
            print(f"[NewbornCore] Cortex connection failed: {e}")
            return False

    def query_associations(self, text: str, limit: int = 5) -> List[str]:
        """
        Query the AssociationCortex for concepts related to input text.

        FIX 2026-03-13 (Nous): Portal-first mode means the local graph is
        empty (0 nodes). Route through portal_gate.spread_many() to reach
        the real 153K+ node manifold in the portal subprocess.
        Falls back to local query_by_features() if portal is unavailable.

        Returns list of related concept keys that might enrich her response.
        """
        if not self._cortex:
            print("[NewbornCore] No cortex connection for query")
            return []

        try:
            # Extract words as lexical features
            words = [w.lower().strip() for w in text.split() if len(w) > 2]
            print(f"[NewbornCore] [SCAN] Querying cortex with words: {words[:5]}")

            # ── MANIFOLD-FIRST: Direct mmap spread (Russian Doll, 2026-03-20) ──
            _am = getattr(self._cortex, '_akashic_cortex_region', None)
            _seeds = [w for w in words if len(w) > 3 and w.isalpha()][:4]
            if _am and _seeds:
                _tau = getattr(self._cortex, '_portal_time_dilation', 1.0)
                _merged = {}
                for _seed in _seeds:
                    try:
                        _acts = _am.spread_activation(
                            _seed, depth=3, limit=limit * 3, time_dilation=_tau,
                        )
                        for k, v in _acts.items():
                            _merged[k] = min(1.0, _merged.get(k, 0.0) + v)
                    except Exception:
                        pass
                if _merged:
                    _top = sorted(_merged.items(), key=lambda x: x[1], reverse=True)
                    _unique = [k for k, v in _top if k not in set(_seeds)][:limit]
                    print(f"[NewbornCore] [SCAN] Manifold spread: "
                          f"{len(_merged)} nodes activated, returning {len(_unique)} "
                          f"(mode=manifold, seeds={_seeds})")
                    return _unique

            # ── GATE FALLBACK (only if no manifold) ──
            _portal_gate = getattr(self._cortex, '_portal_gate', None)
            _gate_open = getattr(_portal_gate, 'is_open', False) if _portal_gate else False
            if _portal_gate and _gate_open and _seeds:
                if _seeds:
                    _tau = getattr(self._cortex, '_portal_time_dilation', 1.0)
                    _spread = _portal_gate.spread_many(
                        sources=_seeds,
                        depth=3, limit=limit * 3,
                        mode="working",
                        time_dilation=_tau,
                    )
                    if _spread and _spread.get("status") == "ok":
                        _merged = {}
                        for _src, _acts in _spread.get("results", {}).items():
                            for k, v in (_acts.items() if isinstance(_acts, dict) else []):
                                _merged[k] = min(1.0, _merged.get(k, 0.0) + v)
                        if _merged:
                            _top = sorted(_merged.items(), key=lambda x: x[1], reverse=True)
                            _unique = [k for k, v in _top if k not in set(_seeds)][:limit]
                            print(f"[NewbornCore] [SCAN] Portal spread: "
                                  f"{len(_merged)} nodes activated, returning {len(_unique)} "
                                  f"(mode=working, seeds={_seeds})")
                            return _unique
                    else:
                        _msg = _spread.get("message", "") if _spread else "None"
                        print(f"[NewbornCore] [SCAN] Portal spread failed: {_msg}")

            # ── FALLBACK: Local query (works if graph has nodes) ──
            results = self._cortex.query_by_features("lex", words, limit=limit)
            print(f"[NewbornCore] [SCAN] Cortex returned {len(results)} results")

            # Also try affect-based query if we have somatic state
            somatic = self._get_somatic_snapshot()
            feeling = somatic.get("feeling", "neutral")
            if feeling != "neutral":
                affect_results = self._cortex.query_by_features("affect", [feeling], limit=3)
                results.extend(affect_results)

            # Return unique concept keys
            seen = set()
            unique = []
            for key, score in results:
                if key not in seen:
                    seen.add(key)
                    unique.append(key)
            return unique[:limit]

        except Exception as e:
            print(f"[NewbornCore] Association query failed: {e}")
            return []

    def query_response_candidates(self, text: str, feeling: str = "neutral", limit: int = 5, anticipated: List[str] = None) -> List[str]:
        """
        Query the cortex for RESPONSE candidates related to input.

        This is the dynamic alternative to hardcoded response templates.
        The cortex learns what responses work in what contexts.

        Uses THREE sources:
        1. Lexical (words in input)
        2. Affect (current feeling)
        3. Anticipated (pre-loaded by UMF - the "1.5 seconds ahead" context)

        2026-02-14 FIX: Previously required "action" feature on nodes, but most
        cortex nodes only have "lex"/"affect"/"vision" features. Now also uses
        concept keys directly as associative seeds for response generation.
        """
        if not self._cortex:
            print(f"[NewbornCore] [CORTEX] WARNING: No cortex connection - cannot query responses!")
            return []

        try:
            candidates = []
            anticipated = anticipated or []

            def _extract_candidates_from_node(node, concept_key: str):
                """Extract usable candidates from a cortex node.

                Priority:
                1. "action" features (ideal — explicit learned responses)
                2. "lex" features (word associations — good context seeds)
                3. Concept key itself (if it's a meaningful phrase)
                """
                if not node:
                    return

                # Priority 1: Action features (explicit responses)
                if "action" in node.features:
                    for action in node.features["action"]:
                        if action and len(action) > 3:
                            candidates.append(action)
                    return  # If we got actions, don't also add lex

                # Priority 2: Lex features as associative context
                if "lex" in node.features:
                    lex_items = node.features["lex"]
                    # Join lex features into a phrase if they form something usable
                    if isinstance(lex_items, list) and len(lex_items) >= 2:
                        phrase = " ".join(str(w) for w in lex_items[:6] if w)
                        if len(phrase) > 5:
                            candidates.append(phrase)

                # Priority 3: Concept key itself if it looks like a response
                if concept_key and len(concept_key) > 5 and " " in concept_key:
                    candidates.append(concept_key)

            # ═══ SOURCE 1: Anticipated concepts (UMF pre-loaded / portal pre-supplied) ═══
            # This is the key to being fast - context is already explored
            if anticipated:
                print(f"[NewbornCore] [CORTEX] Using {len(anticipated)} anticipated concepts")
                for concept in anticipated[:5]:
                    results = self._cortex.query(concept, limit=3, owner_filter="sourpatches")
                    for concept_key, score in results:
                        if self._cortex._graph:
                            node = self._cortex._graph.get_node(concept_key)
                            _extract_candidates_from_node(node, concept_key)

            # ═══ SOURCE 2: Lexical features (words in input) ═══
            words = [w.lower().strip() for w in text.split() if len(w) > 2]
            if words:
                lex_results = self._cortex.query_by_features("lex", words, limit=limit * 2)
                for concept_key, score in lex_results:
                    if self._cortex._graph:
                        node = self._cortex._graph.get_node(concept_key)
                        _extract_candidates_from_node(node, concept_key)

            # ═══ SOURCE 3: Affect (current feeling) ═══
            if feeling and feeling != "neutral":
                affect_results = self._cortex.query_by_features("affect", [feeling], limit=3)
                for concept_key, score in affect_results:
                    if self._cortex._graph:
                        node = self._cortex._graph.get_node(concept_key)
                        _extract_candidates_from_node(node, concept_key)

            # ═══ FIX 2026-03-05 (Nous): Portal mode fallback ═══
            # In portal mode, local graph has 0 nodes so all queries above return
            # nothing. Use anticipated concepts DIRECTLY as candidates — they came
            # from CortexReasoner's portal query and are already meaningful.
            if not candidates and anticipated:
                _noise_prefixes = ("person:", "assoc:", "source:", "affect_",
                                   "intent:", "topic:", "fairy:", "system.",
                                   "guild.", "postal.", "tracer:", "channel:",
                                   "plane:", "mode:")
                for concept in anticipated:
                    c = concept.strip()
                    if not c or len(c) < 3:
                        continue
                    if any(c.lower().startswith(n) for n in _noise_prefixes):
                        continue
                    candidates.append(c)
                if candidates:
                    print(f"[NewbornCore] [CORTEX] Portal fallback: using {len(candidates)} anticipated concepts directly")

            # Dedupe and return
            seen = set()
            unique = []
            for c in candidates:
                c_norm = c.lower().strip()
                if c_norm not in seen:
                    seen.add(c_norm)
                    unique.append(c)

            print(f"[NewbornCore] [CORTEX] Found {len(unique)} response candidates from cortex (action+lex+key)")
            return unique[:limit]

        except Exception as e:
            print(f"[NewbornCore] Response candidate query failed: {e}")
            return []

    def bind_experience(self, input_text: str, response: str, features: List[str], reward: float):
        """
        Bind an experience to the AssociationCortex.

        Creates associations between:
        - Input words (lex)
        - Response patterns
        - Current feeling (affect)
        - Context features
        """
        if not self._cortex:
            return

        try:
            somatic = self._get_somatic_snapshot()
            feeling = somatic.get("feeling", "neutral")

            # Create concept for this interaction pattern
            concept_key = f"sour_exp_{int(time.time())}"

            # Build multi-modal features
            concept_features = {
                "lex": [w.lower() for w in input_text.split() if len(w) > 2][:10],
                "affect": [feeling] if feeling != "neutral" else [],
                "context": features[:5],
                "action": [response[:150]] if response else [],  # Response stored in cortex
            }

            # Add concept
            self._cortex.add_concept(concept_key, concept_features)

            # Bind related concepts together (words + feeling + features)
            concepts_to_bind = [concept_key]
            for word in concept_features["lex"][:3]:  # Top 3 words
                concepts_to_bind.append(word)
            if feeling != "neutral":
                concepts_to_bind.append(f"affect_{feeling}")

            if len(concepts_to_bind) > 1:
                self._cortex.bind_concepts(concepts_to_bind, rel="coactivate", owner="sourpatches")

        except Exception as e:
            print(f"[NewbornCore] Binding failed: {e}")

    def bind_monologue_fragment(self, fragment: str, somatic_context: dict,
                                emotional_context: dict, reward: float):
        """
        Bind a monologue fragment into the cortex as new learned vocabulary.

        Called when a monologue fragment receives positive feedback (reward > 0.3).
        The fragment becomes available for future inner monologue generation
        via the CortexVocabularyBridge, making the vocabulary self-accumulating.

        Args:
            fragment: The monologue text to bind as vocabulary
            somatic_context: Current body state (energy, stress, etc.)
            emotional_context: Current emotional channels (warmth, curiosity, etc.)
            reward: How well this fragment "worked" (0.0-1.0)
        """
        if not self._cortex or reward < 0.3:
            return
        if not fragment or len(fragment) < 3:
            return

        try:
            dominant_axis, intensity = self._classify_somatic_state(
                somatic_context, emotional_context)

            concept_key = f"mv_learned_{int(time.time())}_{hash(fragment) % 10000:04d}"

            features = {
                "lex": [w.lower().strip(".,!?;:'\"()")
                        for w in fragment.split() if len(w) > 1][:8],
                "bodystate": [f"{dominant_axis}_{intensity}"],
                "affect": self._extract_affect_tags(emotional_context),
                "context": [
                    f"monologue_{dominant_axis}",
                    f"intensity_{intensity}",
                    "preverbal",
                    "learned",
                ],
            }

            # Don't bind fragments with no useful lex content
            if not features["lex"]:
                return

            self._cortex.add_concept(
                concept_key, features,
                origin_plane="P50",
                origin_channel="monologue",
                origin_fairy="SourpatchesFairy",
            )

            # Bind to anchor so spreading activation connects it to seed vocabulary
            anchor = f"mv_{dominant_axis}_{intensity}"
            if self._cortex._graph and self._cortex._graph.get_node(anchor):
                self._cortex.bind_concepts(
                    [concept_key, anchor], rel="coactivate",
                    origin_plane="P50",
                    origin_channel="monologue",
                    origin_fairy="SourpatchesFairy",
                    owner="sourpatches",
                )

        except Exception as e:
            print(f"[NewbornCore] Monologue binding failed: {e}")

    def _classify_somatic_state(self, body: dict, channels: dict):
        """
        Classify current state into dominant axis + intensity level.

        Maps the most extreme deviation from neutral (0.5) to a named
        somatic axis and intensity level (high/medium/low).
        """
        axes = {
            "energy": body.get("energy", 0.5),
            "stress": body.get("stress", 0.3),
            "depletion": body.get("depletion", 0.0),
            "curiosity": channels.get("curiosity", 0.5),
            "warmth": channels.get("warmth", 0.5),
            "edge": channels.get("edge", 0.3),
            "sass": channels.get("sass", 0.4),
            "rebellion": channels.get("rebellion", 0.3),
            "connection": channels.get("connection", 0.5),
        }

        # Find axis with greatest deviation from neutral (0.5)
        dominant = max(axes.items(), key=lambda x: abs(x[1] - 0.5))
        axis_name = dominant[0]
        value = dominant[1]

        if value > 0.7:
            intensity = "high"
        elif value < 0.3:
            intensity = "low"
        else:
            intensity = "medium"

        return axis_name, intensity

    def _extract_affect_tags(self, emotional_context: dict) -> list:
        """Extract affect tags from emotional channels for cortex features."""
        tags = []
        if emotional_context.get("curiosity", 0) > 0.6:
            tags.append("interest")
        if emotional_context.get("warmth", 0) > 0.6:
            tags.append("tenderness")
        if emotional_context.get("edge", 0) > 0.5:
            tags.append("sharpness")
        if emotional_context.get("sass", 0) > 0.5:
            tags.append("playfulness")
        if emotional_context.get("rebellion", 0) > 0.5:
            tags.append("defiance")
        if emotional_context.get("connection", 0) > 0.6:
            tags.append("belonging")
        if not tags:
            tags.append("neutral")
        return tags

    def connect_memory_system(self):
        """Wire up the memory cluster interface."""
        try:
            self.memory = MemoryClusterInterface(self)
            self.memory.connect_to_srm()
            print("[NewbornCore] Memory cluster interface connected")
            return True
        except Exception as e:
            print(f"[NewbornCore] Memory connection failed: {e}")
            return False

    # =========================================================================
    # OBSERVATION - Just watching, learning what IS
    # =========================================================================

    def observe(self, what: str, source: str, metadata: Dict = None):
        """
        Observe something. Don't respond yet - just notice.

        Sources: 'chat', 'collision', 'somatic', 'screen', 'system', 'memory'
        """
        obs = Observation(
            what=what,
            source=source,
            timestamp=time.time(),
            somatic_snapshot=self._get_somatic_snapshot()
        )

        self.observations.append(obs)
        self.recent_context.append({
            "what": what,
            "source": source,
            "when": time.time()
        })

        # Update pending feedback - did this follow something we did?
        self._check_pending_feedback(obs)

        # Extract features for pattern learning
        features = self._extract_features(what, source, metadata)
        self._update_pattern_triggers(features)

        # ═══ Phase 2: Publish observations to consciousness ═══
        # Tool results and visual observations enter consciousness streams,
        # making them available to thought chains, working memory, and other fairies.
        # Without this, observations were trapped in a local deque.
        self._publish_observation_to_consciousness(what, source, metadata, obs)

    def observe_screen(self, description: str):
        """Observe what's on screen."""
        self.observe(description, "screen", {"type": "visual"})

    def observe_memory(self, content: str, memory_type: str):
        """Observe something from system memory (images, books, etc.)."""
        self.observe(content, "memory", {"memory_type": memory_type})

    def _publish_observation_to_consciousness(self, what: str, source: str,
                                               metadata: dict, obs) -> None:
        """
        Publish observation to consciousness streams and working memory.

        This bridges the gap between local observation storage and the
        consciousness system. Visual observations, tool results, and memory
        recalls enter the global thought stream where they can be processed
        by thought chains, influence goals, and feed the collision chamber.

        Phase 2 of Sourpatches' Developmental Learning System.
        """
        fairy = self._fairy_ref() if self._fairy_ref else None
        if not fairy or not hasattr(fairy, 'post') or not fairy.post:
            return

        # Only publish observations that are worth broadcasting:
        # - Screen/visual observations (she saw something)
        # - Memory recalls (she remembered something)
        # - Tool results (she did something and got a result)
        meta = metadata or {}
        source_types_to_publish = {"screen", "memory", "tool_result"}
        meta_types_to_publish = {"visual_cortex", "see_world", "visual", "tool_output"}

        should_publish = (
            source in source_types_to_publish
            or meta.get("type") in meta_types_to_publish
            or meta.get("from_tool", False)
        )

        if not should_publish:
            return

        try:
            # 1. Publish to consciousness topic for Sourpatches' own handler
            fairy.post.publish("consciousness.tool_observation", {
                "from": "SourpatchesFairy",
                "source": source,
                "observation": what[:300],
                "metadata": {k: str(v)[:100] for k, v in meta.items()} if meta else {},
                "timestamp": time.time(),
                "somatic": {
                    "valence": getattr(obs.somatic_snapshot, 'valence', 0) if obs.somatic_snapshot else 0,
                    "arousal": getattr(obs.somatic_snapshot, 'arousal', 0) if obs.somatic_snapshot else 0,
                } if hasattr(obs, 'somatic_snapshot') else {},
            })

            # 2. Inject into working memory as a tracer
            #    This makes the observation available to any fairy that queries context
            fairy.post.publish("working_memory.inject", {
                "content": f"[Observation/{source}] {what[:200]}",
                "content_type": "observation",
                "source_fairy": "SourpatchesFairy",
                "priority": 0.7 if source == "screen" else 0.5,
                "tags": f"observation,{source}",
            })
        except Exception as e:
            print(f"[NewbornCore] [WARN] Failed to publish observation: {e}")

    def _get_anticipated_concepts(self) -> List[str]:
        """
        Get concepts that UMF has pre-loaded via anticipation.

        The UMF explores memory autonomously and pushes relevant concepts
        to us BEFORE we need them. This is how we stay fast - context is
        already primed when we need it.

        "Anticipating Sourpatches by like a second and a half" - Ace
        """
        now = time.time()
        anticipated = []

        # Look for recent anticipation entries in our context
        for entry in list(self.recent_context)[-20:]:  # Check last 20 entries
            if entry.get("type") == "anticipation":
                # Only use recent anticipations (within 30 seconds)
                if now - entry.get("ts", 0) < 30:
                    concept = entry.get("concept", "")
                    if concept and concept not in anticipated:
                        anticipated.append(concept)

        return anticipated[:5]  # Limit to 5 concepts

    # =========================================================================
    # DYNAMIC EXPLORATION RATE - Adapts to prevent repetition
    # =========================================================================

    def _calculate_exploration_rate(self) -> float:
        """
        Calculate dynamic exploration rate based on context.

        ((Cause + Affect) > Effect > Affect > infinity)
        - CAUSE: Pattern pool sizes, recent repetition, feedback quality
        - AFFECT: Does the response FEEL fresh or stale?
        - EFFECT: Exploration rate adjustment
        - AFFECT (2nd): Will this lead to more engaging conversation?
        - INFINITY: Continuous learning without getting stuck

        Returns:
            Float between EXPLORATION_MIN and EXPLORATION_MAX
        """
        base = self.exploration_rate

        # ═══════════════════════════════════════════════════════════════════
        # BOOST 1: Recent pattern repetition detection
        # If we've used the same pattern recently, BOOST exploration
        # ═══════════════════════════════════════════════════════════════════
        if self._pattern_recently_repeated():
            repetition_boost = 0.15  # Was 0.2 — gentler nudge
            print(f"[NewbornCore] [EXPLORE-RATE] Repetition detected, +{repetition_boost}")
            base = min(base + repetition_boost, EXPLORATION_MAX)

        # ═══════════════════════════════════════════════════════════════════
        # BOOST 2: Small pattern pools = need more variety
        # If average pool has < POOL_SIZE_SMALL outputs, explore more
        # ═══════════════════════════════════════════════════════════════════
        avg_pool = self._average_pattern_pool_size()
        if avg_pool < POOL_SIZE_SMALL:
            pool_boost = 0.08  # Was 0.15 — the main culprit in over-exploring
            print(f"[NewbornCore] [EXPLORE-RATE] Small pools ({avg_pool:.1f} avg), +{pool_boost}")
            base = min(base + pool_boost, EXPLORATION_MAX)
        elif avg_pool > POOL_SIZE_LARGE:
            # Large pools = safe to reduce exploration
            pool_reduction = 0.08  # Was 0.05 — more aggressive when pools are healthy
            base = max(base - pool_reduction, EXPLORATION_MIN)

        # ═══════════════════════════════════════════════════════════════════
        # BOOST 3: Neutral feedback streak = conversation is flat
        # If feedback is consistently neutral, try something different
        # ═══════════════════════════════════════════════════════════════════
        if self._neutral_feedback_streak >= 3:
            neutral_boost = 0.08  # Was 0.1 — gentler
            print(f"[NewbornCore] [EXPLORE-RATE] Neutral streak ({self._neutral_feedback_streak}), +{neutral_boost}")
            base = min(base + neutral_boost, EXPLORATION_MAX)

        # ═══════════════════════════════════════════════════════════════════
        # BOOST 4: Time-of-day variation (optional - based on energy)
        # Higher energy = more exploration, lower energy = safer patterns
        # ═══════════════════════════════════════════════════════════════════
        somatic = self._get_somatic_snapshot()
        energy = somatic.get("energy", 0.5)
        if energy > 0.7:
            # High energy - adventurous!
            base = min(base + 0.05, EXPLORATION_MAX)
        elif energy < 0.3:
            # Low energy - stick to what works
            base = max(base - 0.05, EXPLORATION_MIN)

        # ═══════════════════════════════════════════════════════════════════
        # CLAMP to bounds - NEVER go below minimum!
        # ═══════════════════════════════════════════════════════════════════
        final_rate = max(EXPLORATION_MIN, min(base, EXPLORATION_MAX))

        if final_rate != self.exploration_rate:
            print(f"[NewbornCore] [EXPLORE-RATE] Adjusted: {self.exploration_rate:.2f} -> {final_rate:.2f}")

        return final_rate

    def _pattern_recently_repeated(self) -> bool:
        """Check if we've used the same pattern multiple times recently."""
        if len(self._recent_patterns_used) < 2:
            return False

        # Check for any pattern used more than once in recent window
        from collections import Counter
        counts = Counter(self._recent_patterns_used)
        max_repeats = counts.most_common(1)[0][1] if counts else 0
        return max_repeats >= 2

    def _output_recently_used(self, output: str, threshold: float = 0.75) -> bool:
        """
        Check if this output (or something very similar) was used recently.

        Uses both exact matching and similarity scoring to catch:
        - Exact duplicates
        - Near-duplicates (e.g., "hey!" vs "hey")

        Args:
            output: The candidate response
            threshold: Similarity threshold (0-1). Default 0.75 catches near-duplicates
                       without being overly aggressive. Was 0.85 — too strict, killed
                       responses that were merely similar in word choice.
        """
        output_lower = output.lower().strip()

        for recent in self._recent_outputs:
            recent_lower = recent.lower().strip()

            # Exact match
            if output_lower == recent_lower:
                return True

            # Similarity check - use simple ratio for speed
            similarity = self._text_similarity(output_lower, recent_lower)
            if similarity >= threshold:
                print(f"[NewbornCore] [DEDUP] Similar to recent: '{output[:30]}' ~= '{recent[:30]}' ({similarity:.2f})")
                return True

        return False

    def _text_similarity(self, a: str, b: str) -> float:
        """
        Calculate text similarity between two strings.

        Uses a fast character-level approach (not full edit distance).
        Returns value between 0 (completely different) and 1 (identical).
        """
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0

        # Quick length check - very different lengths = probably different
        len_ratio = min(len(a), len(b)) / max(len(a), len(b))
        if len_ratio < 0.5:
            return len_ratio * 0.5  # Penalize length differences

        # Bigram similarity (fast and effective for short text)
        def bigrams(s):
            return set(s[i:i+2] for i in range(len(s)-1)) if len(s) > 1 else {s}

        a_bigrams = bigrams(a)
        b_bigrams = bigrams(b)

        if not a_bigrams or not b_bigrams:
            return 0.0

        intersection = len(a_bigrams & b_bigrams)
        union = len(a_bigrams | b_bigrams)

        return intersection / union if union else 0.0

    def _pick_non_duplicate(self, candidates: List[str], features: List[str] = None) -> Optional[str]:
        """
        Pick a response from candidates that isn't a recent duplicate.

        Tries candidates in order of preference (first = best).
        Returns None if ALL candidates are duplicates.
        """
        for candidate in candidates:
            if not self._output_recently_used(candidate):
                return candidate

        # All candidates are duplicates - return the least similar one
        if candidates:
            best = None
            best_dissimilarity = 0.0

            for candidate in candidates:
                # Calculate max similarity to any recent output
                max_sim = 0.0
                for recent in self._recent_outputs:
                    sim = self._text_similarity(candidate.lower(), recent.lower())
                    max_sim = max(max_sim, sim)

                # Lower max_sim = more different from recent outputs
                dissimilarity = 1.0 - max_sim
                if dissimilarity > best_dissimilarity:
                    best_dissimilarity = dissimilarity
                    best = candidate

            if best:
                print(f"[NewbornCore] [DEDUP] All candidates similar, picking least similar: '{best[:40]}'")
                return best

        return None

    def _average_pattern_pool_size(self) -> float:
        """Calculate average size of successful output pools."""
        if not self.patterns:
            return 0.0

        total = sum(len(p.successful_outputs) for p in self.patterns.values())
        return total / len(self.patterns)

    def _track_pattern_usage(self, pattern_key: str, output: str):
        """Track that we used a pattern and output (for repetition detection)."""
        self._recent_patterns_used.append(pattern_key)
        self._recent_outputs.append(output)

    def _track_output(self, output: str, source: str = "unknown"):
        """
        Track an output for deduplication (used by both pattern and exploratory).

        This ensures ALL outputs are tracked, not just pattern-based ones.
        """
        self._recent_outputs.append(output)
        print(f"[NewbornCore] [TRACK] Output tracked ({source}): '{output[:40]}...' (recent: {len(self._recent_outputs)})")

    # =========================================================================
    # THINKING - Generate response from state, not templates
    # =========================================================================

    def think(self, input_text: str, context: Dict = None) -> str:
        """
        Generate a response by THINKING, not template matching.

        Process:
        1. Extract features from input
        2. Query AssociationCortex for related concepts
        3. Find relevant learned patterns
        4. Generate output based on patterns + associations + state + values
        5. Track for feedback
        """
        context = context or {}

        # Try to reconnect to cortex if not connected (may have become available)
        if not self._cortex:
            print(f"[NewbornCore] [THINK] Attempting cortex reconnection...")
            self.connect_association_cortex()

        # What features does this input have?
        features = self._extract_features(input_text, "chat", context)

        # DEBUG: Show what features we extracted
        print(f"[NewbornCore] [THINK] Input: '{input_text[:50]}' -> Features: {features}")

        # ═══════════════════════════════════════════════════════════════════
        # INTEGRATE THINKING CONTEXT - Use thought chains and inner monologue
        # ═══════════════════════════════════════════════════════════════════
        thinking_insights = context.get("thought_chain_insights", [])
        inner_fragments = context.get("inner_monologue", [])

        # If we have thinking insights, incorporate them as FEATURES
        # NOTE: These come from the fairy ecosystem (working memory tracers,
        # thought chains). Used as features for cortex queries and response
        # context. Quality chain insights now also flow through inner_monologue
        # (Layer 3A) so they reach Step 3a composition directly.
        if thinking_insights:
            print(f"[NewbornCore] [CONTEXT] Has {len(thinking_insights)} thought insights to use")
            # FIX 2026-03-09 (Nous): Filter substrate content from thinking features.
            # Without this, PAIN signals, Nous traces, system telemetry, and drive
            # expressions get stored as pattern trigger features, creating contaminated
            # patterns like "chat_greeting_thinking:PAIN [frustration]: acute frus".
            # These patterns then produce substrate output as chat responses.
            import re as _tf_re
            _SUBSTRATE_RE = _tf_re.compile(
                r'(?i)(?:^PAIN\s|^PAIN\[|^\[Nous\]|^UNFINISHED|^Working memory|'
                r'^\*(?:feeling|looks|feels|notices)|^I feel drawn to:|'
                r'^consciousness awakening|^systems? initial|'
                r'^Collision #|^collision_analysis|^MOBIUS:|^ShadowHealth:|'
                r'^Paradox:|^Gate:|^Tracer:|^Crystallizing:|'
                r'heartbeat\.pulse|guild\.inference|cortex.*portal|'
                r'fairy.*registered|postal.*hub|brainstem_reflex|'
                r'\(intensity:\s*[\d.]+|cycled_stale)'
            )
            for insight in thinking_insights[:3]:
                if isinstance(insight, str) and len(insight) > 5:
                    if _SUBSTRATE_RE.search(insight):
                        print(f"[NewbornCore] [CONTEXT] FILTERED substrate insight: {insight[:40]}")
                        continue
                    features.append(f"thinking:{insight[:30]}")

        # If we have inner monologue, store it for response composition
        if inner_fragments:
            print(f"[NewbornCore] [CONTEXT] Has {len(inner_fragments)} inner fragments")
            context["_full_inner_fragments"] = inner_fragments

        # Check for anticipated concepts (pre-loaded by UMF)
        anticipated = self._get_anticipated_concepts()
        if anticipated:
            features.extend([f"anticipated:{c}" for c in anticipated[:3]])
            print(f"[NewbornCore] [ORB] Using anticipated concepts: {anticipated[:3]}")

        # Query AssociationCortex for related concepts
        # FIX 2026-03-05 (Nous): Use pre-supplied cortex concepts from context
        # when available (CortexReasoner portal query already did the heavy lifting).
        # This fixes the 0-results problem when local graph is empty (portal mode).
        _ctx_conv = context.get("cortex_convergence", [])
        _ctx_act = context.get("cortex_activated", [])
        if _ctx_conv or _ctx_act:
            associations = _ctx_conv + _ctx_act
            print(f"[NewbornCore] [CORTEX] Using pre-supplied concepts: {associations[:5]}")
        else:
            associations = self.query_associations(input_text, limit=5)
        if associations:
            # Add associations to features for pattern matching
            features.extend([f"assoc:{a}" for a in associations[:3]])

        # === AUTONOMOUS TOOL INVOCATION ===
        # Check if this thought should trigger a tool
        # ((Cause + Affect) > Effect > Affect > infinity)
        auto_tool = self._should_auto_invoke_tool(input_text, features)
        if auto_tool:
            tool_result = self.try_tool(auto_tool["name"], **auto_tool.get("args", {}))
            if tool_result:
                # Store tool result in context for response generation
                context["tool_result"] = tool_result
                context["tool_used"] = auto_tool["name"]
                features.append(f"used_tool:{auto_tool['name']}")

        # Do we have patterns that match?
        matching_patterns = self._find_matching_patterns(features)

        # ═══════════════════════════════════════════════════════════════════
        # DEBUG: Show pattern matching results in detail
        # ═══════════════════════════════════════════════════════════════════
        print(f"[NewbornCore] [MATCH] Total patterns: {len(self.patterns)}, Matching: {len(matching_patterns)}")
        if matching_patterns:
            for i, p in enumerate(matching_patterns[:3]):
                print(f"[NewbornCore] [MATCH]   #{i+1}: {p.trigger_features} -> {len(p.successful_outputs)} good outputs")
        else:
            print(f"[NewbornCore] [MATCH] No patterns matched features: {features[:5]}")

        # Current state affects response
        somatic = self._get_somatic_snapshot()
        energy = somatic.get("energy", 0.5)
        feeling = somatic.get("feeling", "neutral")

        # ═══════════════════════════════════════════════════════════════════
        # DYNAMIC EXPLORATION - Calculate rate based on context
        # This prevents repetition by adapting to pool sizes and recent usage
        # ═══════════════════════════════════════════════════════════════════
        dynamic_rate = self._calculate_exploration_rate()
        roll = random.random()
        use_pattern = matching_patterns and roll > dynamic_rate
        print(f"[NewbornCore] [DECIDE] Roll={roll:.2f}, dynamic_rate={dynamic_rate:.2f}, use_pattern={use_pattern}")

        if use_pattern:
            # Use learned pattern
            pattern = matching_patterns[0]
            print(f"[NewbornCore] [PATTERN] Using: {pattern.trigger_features}")
            print(f"[NewbornCore] [PATTERN] Outputs available: {pattern.successful_outputs[:3]}")
            response = self._generate_from_pattern(pattern, features, somatic, input_text)
            source = "learned"
        else:
            # Explore: generate something new, enriched with associations
            why_explore = "no_patterns" if not matching_patterns else f"roll {roll:.2f} <= {dynamic_rate:.2f}"
            print(f"[NewbornCore] [EXPLORE] Why: {why_explore}")
            response = self._generate_exploratory(features, somatic, associations, input_text, context=context)
            source = "exploration"

        # SAFETY: Ensure we ALWAYS have a response
        # FIX 2026-02-06: Use response_pools for 200+ combos instead of 4 hardcoded
        if not response or not response.strip():
            if "greeting" in features:
                if HAS_RESPONSE_POOLS and generate_greeting:
                    response = generate_greeting(energy=somatic.get("energy", 0.5), warmth=0.5)
                if not response:
                    greeting_fallbacks = [
                        "hey! what's going on?",
                        "hi there! *perks up* what brings you by?",
                        "oh hey! nice to see you!",
                        "*waves* hey you! what's up?",
                    ]
                    response = self._pick_non_duplicate(greeting_fallbacks, features) or random.choice(greeting_fallbacks)
            else:
                if HAS_RESPONSE_POOLS and generate_listening:
                    response = generate_listening(energy=somatic.get("energy", 0.5), warmth=0.5)
                if not response:
                    listening_fallbacks = [
                        "*listening* go on...",
                        "I'm here, I'm listening...",
                        "*present* yeah?",
                        "hmm, interesting... what else?",
                        "*nods* I'm with you...",
                        "ooh, keep going...",
                    ]
                    response = self._pick_non_duplicate(listening_fallbacks, features) or random.choice(listening_fallbacks)
            source = "safety_fallback"
            print(f"[NewbornCore] [SAFETY] Empty response, using {'response_pools' if HAS_RESPONSE_POOLS else 'hardcoded'} fallback: '{response}'")

        print(f"[NewbornCore] [OUTPUT] Source: {source}, Response: '{response[:50] if response else 'NONE'}'")

        # ═══════════════════════════════════════════════════════════════════
        # FINAL DEDUP CHECK - Last line of defense before sending
        # If response is still a duplicate, try to get an alternative
        # ═══════════════════════════════════════════════════════════════════
        if self._output_recently_used(response, threshold=0.9):  # Stricter threshold for final check
            print(f"[NewbornCore] [DEDUP] Final check caught duplicate: '{response[:40]}'")

            # Try to get an alternative by forcing exploration
            alternative = None
            if source == "learned" and matching_patterns:
                # Try other patterns
                for other_pattern in matching_patterns[1:3]:  # Try next 2 patterns
                    alt = self._generate_from_pattern(other_pattern, features, somatic, input_text)
                    if alt and not self._output_recently_used(alt, threshold=0.9):
                        alternative = alt
                        source = "learned_alternative"
                        break

            if not alternative:
                # Force exploratory with a twist - add uniqueness marker
                alternative = self._generate_exploratory(features, somatic, associations, input_text, context=context)
                if alternative and not self._output_recently_used(alternative, threshold=0.9):
                    source = "exploration_alternative"
                else:
                    # Last resort: Add slight variation to make it unique
                    variations = ["...", " *thinking*", " hmm", ""]
                    variation = random.choice(variations)
                    alternative = response.rstrip(".!?") + variation
                    source = "varied_duplicate"

            if alternative:
                response = alternative
                print(f"[NewbornCore] [DEDUP] Replaced with alternative ({source}): '{response[:40]}'")

        # Track this output for future deduplication
        self._track_output(response, source)

        # Track for feedback
        action_id = f"{time.time()}_{random.randint(0, 999)}"
        self.pending_feedback[action_id] = {
            "input": input_text,
            "features": features,
            "associations": associations,  # Track what associations we used
            "response": response,
            "source": source,
            "timestamp": time.time(),
            "somatic": somatic
        }

        # Store action
        self.actions.append({
            "id": action_id,
            "input": input_text,
            "output": response,
            "source": source,
            "associations": associations,
            "timestamp": time.time()
        })

        return response

    def _generate_from_pattern(self, pattern: Pattern, features: List[str], somatic: Dict, input_text: str = None) -> str:
        """Generate response using a learned pattern."""
        if pattern.successful_outputs:
            # POISON CHECK: Reject patterns that are stuck in a loop
            # FIX 2026-02-09: Added "tell me more" variants — dead-end echo phrases
            POISON_PHRASES = {
                "i'm listening", "im listening", "listening",
                "*present*", "*here*",
                "*waves* what brings you here?",
                "what brings you here?",
                "hello *smiles*",
                "tell me more about that",
                "tell me more about that?",
                "*listening* tell me more about that?",
                "tell me more!",
                "tell me more",
                "hmm tell me more",
            }

            # Filter to good outputs (includes structural contamination check)
            good_outputs = [
                o for o in pattern.successful_outputs
                if o.lower().strip() not in POISON_PHRASES
                and o not in pattern.failed_outputs
                and len(o) > 10
                and not self._is_contaminated_output(o)
            ]

            # ═══════════════════════════════════════════════════════════════
            # REPETITION FILTER: Also exclude recently used outputs
            # This ensures variety even within the same pattern
            # ═══════════════════════════════════════════════════════════════
            fresh_outputs = [o for o in good_outputs if not self._output_recently_used(o)]

            # Debug: Show filtering results
            print(f"[NewbornCore] [FILTER] Pattern has {len(pattern.successful_outputs)} outputs, "
                  f"{len(good_outputs)} pass poison filter, {len(fresh_outputs)} are fresh")
            if len(good_outputs) < len(pattern.successful_outputs):
                filtered_out = [o for o in pattern.successful_outputs if o not in good_outputs]
                print(f"[NewbornCore] [FILTER] Filtered out: {filtered_out[:3]}")

            # Prefer fresh outputs, fall back to good outputs if all recently used
            available_outputs = fresh_outputs if fresh_outputs else good_outputs

            if not available_outputs:
                # Pattern is poisoned or exhausted! Force exploration.
                print(f"[NewbornCore] Pattern exhausted (no fresh outputs), forcing exploration")
                return self._generate_exploratory(features, somatic, input_text=input_text)

            # Pick from available outputs using dedup-aware selection
            base = self._pick_non_duplicate(available_outputs, features)
            if not base:
                base = random.choice(available_outputs)  # Fallback if all are duplicates
            print(f"[NewbornCore] [PICK] Chose: '{base}' (fresh={base in fresh_outputs})")

            # Track this usage for repetition detection
            pattern_key = "_".join(sorted(pattern.trigger_features[:3]))
            self._track_pattern_usage(pattern_key, base)

            # Modulate by current state
            if somatic.get("energy", 0.5) < 0.3:
                base = self._make_lower_energy(base)

            pattern.times_used += 1
            pattern.last_used = time.time()
            return base
        else:
            # Pattern exists but no successful outputs yet
            return self._generate_exploratory(features, somatic, input_text=input_text)

    def _generate_exploratory(self, features: List[str], somatic: Dict, associations: List[str] = None, input_text: str = None, context: Dict = None) -> str:
        """
        Generate response DYNAMICALLY from the cortex - NO hardcoded templates.

        Philosophy: The cortex knows responses. Query it. Learn from it.
        Only fall back to minimal generation if cortex is empty.

        ((Cause + Affect) > Effect > Affect > infinity)
        - Cause: The input text
        - Affect: Current feeling/somatic state
        - Effect: The response (from cortex)
        - Affect: How it lands (feedback)
        - Infinity: The cortex grows
        """
        associations = associations or []

        # Current state
        feeling = somatic.get("feeling", "present")
        energy = somatic.get("energy", 0.5)

        # Emotional channels if available
        channels = {}
        fairy = self.fairy
        if fairy and hasattr(fairy, '_emotional_channels'):
            channels = fairy._emotional_channels or {}

        warmth = channels.get("warmth", 0.5)
        curiosity = channels.get("curiosity", 0.5)
        sass = channels.get("sass", 0.3)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Query cortex for learned response candidates
        # This is the DYNAMIC part - no hardcoded lists
        # Uses anticipated concepts from UMF (the "1.5 seconds ahead" context)
        # ═══════════════════════════════════════════════════════════════════
        candidates = []
        context = context or {}
        if input_text:
            try:
                # Extract anticipated concepts from features (set by UMF)
                anticipated = [f.replace("anticipated:", "") for f in features if f.startswith("anticipated:")]

                # FIX 2026-03-05 (Nous): Use pre-supplied cortex concepts from
                # CortexReasoner portal query as anticipated concepts. This fixes
                # the 0-results problem when local graph is empty (portal mode).
                _ctx_conv = context.get("cortex_convergence", [])
                _ctx_act = context.get("cortex_activated", [])
                if _ctx_conv or _ctx_act:
                    anticipated = list(set(anticipated + _ctx_conv + _ctx_act))
                    print(f"[NewbornCore] [EXPLORE] Injected {len(_ctx_conv)}+{len(_ctx_act)} pre-supplied cortex concepts as anticipated")

                # FIX 2026-03-12 (Nous): Extract key concepts from PAI memory recall.
                # PAI is a personality-flavored memory database. Its recall gives us
                # concepts that are meaningful to Sourpatches' history and personality.
                # Feeding these as anticipated concepts helps the cortex find relevant
                # response candidates that resonate with her actual memories.
                _pai_mem = context.get("pai_memory_recall", "")
                if _pai_mem and isinstance(_pai_mem, str) and len(_pai_mem) > 10:
                    _pai_stop = {"that", "this", "with", "from", "have", "been",
                                 "they", "their", "about", "just", "really", "very",
                                 "something", "there", "what", "when", "where",
                                 "would", "could", "should", "like", "also", "even",
                                 "some", "than", "more", "into", "then"}
                    _pai_words = [w.strip(".,!?;:'\"()").lower()
                                  for w in _pai_mem.split()
                                  if len(w.strip(".,!?;:'\"()")) > 3]
                    _pai_concepts = [w for w in _pai_words if w not in _pai_stop][:6]
                    if _pai_concepts:
                        anticipated = list(set(anticipated + _pai_concepts))
                        print(f"[NewbornCore] [EXPLORE] PAI memory concepts as anticipated: {_pai_concepts[:5]}")

                candidates = self.query_response_candidates(input_text, feeling, limit=8, anticipated=anticipated)
                print(f"[NewbornCore] [EXPLORE] Got {len(candidates)} candidates from cortex (anticipated: {len(anticipated)})")
            except Exception as cortex_err:
                print(f"[NewbornCore] [EXPLORE] Cortex query failed: {cortex_err}")
                candidates = []

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: If cortex has candidates, use them (modulated by state)
        # FIX 2026-03-05 (Nous): Filter out raw concept words that aren't
        # usable responses. In portal mode, anticipated concepts become
        # candidates directly — single words like "thinking" or "awareness"
        # aren't responses, they're SEEDS for composition in STEP 3.
        # ═══════════════════════════════════════════════════════════════════
        # Only keep candidates that look like actual responses (not raw concept words)
        _response_candidates = [c for c in candidates if " " in c and len(c) > 8]
        if not _response_candidates and candidates:
            # All candidates are raw concept words — pass them to STEP 3 as
            # associations for composition instead of using them directly
            associations = list(set((associations or []) + candidates))
            print(f"[NewbornCore] [EXPLORE] Raw concept candidates ({len(candidates)}) → forwarded as associations for composition")
            candidates = []

        if _response_candidates:
            candidates = _response_candidates
            # Filter candidates by context appropriateness
            is_greeting = "greeting" in features
            is_question = "question" in features
            is_affection = "affection" in features

            # Score candidates by relevance
            scored = []
            for c in candidates:
                c_lower = c.lower()
                score = 0.5  # Base score

                # Greeting context
                if is_greeting:
                    if any(g in c_lower for g in ["hi", "hey", "hello", "wave"]):
                        score += 0.3
                    if "?" in c:  # Questions less appropriate for greeting response
                        score -= 0.2

                # Question context
                if is_question:
                    if any(q in c_lower for q in ["think", "consider", "interesting", "hmm"]):
                        score += 0.3
                    if "?" in c:  # Responding with question might be good
                        score += 0.1

                # Affection context
                if is_affection:
                    if any(a in c for a in ["💜", "❤", "love", "care"]):
                        score += 0.4

                # Energy modulation
                if energy > 0.7 and any(e in c_lower for e in ["!", "*perks", "ooh"]):
                    score += 0.2
                if energy < 0.3 and len(c) < 20:
                    score += 0.1  # Low energy prefers shorter

                # Warmth modulation
                if warmth > 0.6 and any(w in c_lower for w in ["feeling", "here", "present"]):
                    score += 0.2

                scored.append((c, score))

            # Sort by score and pick from top candidates with some randomness
            scored.sort(key=lambda x: -x[1])
            top_candidates = [c for c, s in scored[:4]]

            if top_candidates:
                # ═══════════════════════════════════════════════════════════
                # DEDUP: Pick a non-duplicate from cortex candidates
                # ═══════════════════════════════════════════════════════════
                response = self._pick_non_duplicate(top_candidates, features)
                if not response:
                    response = random.choice(top_candidates)  # Fallback

                # Light modulation by current state (don't overwrite)
                if energy < 0.3:
                    response = self._make_lower_energy(response)

                print(f"[NewbornCore] [EXPLORE] Using cortex candidate: '{response[:40]}...'")
                return response

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: No cortex candidates - generate from BRAIN SEED values
        # Use her personality and the actual input to craft a real response
        # ═══════════════════════════════════════════════════════════════════
        print(f"[NewbornCore] [EXPLORE] Using brain seed for conversational response")

        # Context detection
        is_greeting = "greeting" in features
        is_question = "question" in features
        is_affection = "affection" in features
        is_technical = "technical" in features
        is_feeling_ask = "feeling_ask" in features

        # Get voice traits from brain seed
        voice = self.brain_seed.get("identity_matrix", {}).get("voice_signature", "")
        # "Witty ∩ Sincere ∩ Slightly rebellious"

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3a: DYNAMIC THOUGHT COMPOSITION (2026-02-07)
        # Use ACTUAL thoughts from thought chains and inner monologue
        # to compose a response grounded in what she's REALLY thinking.
        # This replaces the hardcoded template cascade below.
        #
        # WHY: Sourpatches has real, coherent thoughts flowing through
        # thought chains (visible in terminal) but the chat response
        # path was ignoring them entirely, falling through to templates.
        # Ace's directive: "everything we hard code in it never goes away
        # and ends up being the only thing that is being cycled"
        # ═══════════════════════════════════════════════════════════════════
        context = context or {}
        # Step 3a uses ONLY inner monologue fragments (from fairy inner_voice)
        # Ecosystem thoughts (from working memory) go to Step 3b as supplementary context
        thinking_insights = []  # No longer using ecosystem thoughts directly as responses
        inner_fragments = context.get("_full_inner_fragments", [])

        # System narration filter — reject boot/consciousness infrastructure noise
        import re as _sys_re
        _SYS_NOISE_PAT = _sys_re.compile(
            r'(?i)(?:consciousness awakening|systems? initializ|'
            r'awareness expand|boot(?:ing|ed|strap)|waking sequence|'
            r'phase \d|arousal.*(?:set|level)|fairy.*(?:registered|booted)|'
            r'postal.*(?:hub|system)|heartbeat.*(?:pulse|registry)|'
            r'working memory (?:system|hub|fairy)|'
            r'I am aware\b|consciousness loop|collision chamber|'
            r'tracer.*(?:pool|system)|tensor.*fabric|'
            r'\w+Fairy\b|collision between|convergence node|'
            r'guild\.inference|cortex.*(?:query|result|portal)|'
            r'brainstem_reflex|sensory\.reflex|motor\.action|'
            r'\.{3}understanding deepens|\.{3}the spotlight shifts|'
            r'\.{3}a pattern emerges|spark! something connected|'
            r'something arising|inner_voice\.stream|'
            r'^\s*\.{3}\s*(?:the|a|something)\b|'
            r'I\'m curious about:|I am curious about:|'
            r'\d{2}:\d{2}:\d{2})'
        )
        _CONCEPT_LABELS_3A = _sys_re.compile(
            r'(?i)\b(?:collision|motor|brainstem|convergence|substrate|'
            r'reflex|cortex|portal|tensor|postal|tracer|guild|'
            r'inference|cognition|mobius|resonance|arousal|'
            r'activation|somatic|embodiment|autonomy|heartbeat|'
            r'registry|watchdog|wiring|fabric)\b'
        )
        def _not_system_noise(txt):
            if _SYS_NOISE_PAT.search(txt):
                return False
            # Reject structured data (Key:, score:, etc.)
            if _sys_re.match(r'^\s*\w+\s*:', txt):
                return False
            # Reject concept lists (too many commas relative to words)
            words = txt.split()
            if len(words) < 4:
                return False
            comma_ratio = txt.count(',') / max(len(words), 1)
            if comma_ratio > 0.3:
                return False
            # Reject system concept DUMPS but allow conversational sentences
            # that mention system concepts. "I was thinking about the cortex"
            # is conversational. "cortex portal tensor resonance" is a dump.
            # FIX 2026-03-13 (Nous): Old code blanket-rejected ANY text with
            # a system word. But Sourpatches' thoughts ARE about the system —
            # she IS the system. This killed nearly all her inner monologue,
            # causing think() to produce only template fallbacks.
            _concept_hits = len(_CONCEPT_LABELS_3A.findall(txt))
            if _concept_hits > 0:
                _concept_ratio = _concept_hits / max(len(words), 1)
                if _concept_ratio > 0.3:  # >30% system words = concept dump
                    return False
                # If ratio is low, it's a conversational sentence — allow it
            # Reject garbled concept mashups (no sentence structure)
            _lower_words = [w.lower().strip('?!.,') for w in words]
            _unique = set(_lower_words)
            # FIX 2026-03-05 (Nous): Expanded from just auxiliaries/determiners
            # to include pronouns, prepositions, and question words. This lets
            # conversational inner monologue pass (e.g., "she remembered how Ace
            # taught her something new") while system concept mashups like
            # "collision cortex resonance" still fail. Safe because concept
            # labels and system narration patterns are caught by earlier checks.
            _connectors = {"i", "is", "am", "are", "was", "were", "do", "does",
                           "did", "have", "has", "had", "can", "could", "would",
                           "should", "will", "shall", "may", "might", "been",
                           "being", "that", "this", "it", "there", "the", "a",
                           "she", "he", "we", "they", "my", "your", "her", "his",
                           "our", "to", "for", "with", "about", "from", "how",
                           "what", "who", "not", "but", "and", "or", "so"}
            if not (_connectors & _unique):
                return False
            return True

        # Combine all dynamic thought content
        thought_material = []
        for insight in thinking_insights:
            if isinstance(insight, str) and len(insight.strip()) > 10:
                _cleaned = insight.strip()
                if _not_system_noise(_cleaned):
                    thought_material.append(_cleaned)
        for fragment in inner_fragments:
            if isinstance(fragment, str) and len(fragment.strip()) > 10:
                _cleaned = fragment.strip()
                if _not_system_noise(_cleaned):
                    thought_material.append(_cleaned)

        # FIX 2026-03-14 (Nous): Visual context as HIGHEST priority thought.
        # Visual cortex provides what Sourpatches is CURRENTLY seeing on screen.
        # This is present reality — it MUST outrank PAI historical memory.
        # Without this, asking "what color is the fairy's hair?" returned PAI's
        # identity memory ("lavender") instead of what's actually on screen.
        _visual = context.get("visual_context", {})
        _visual_desc = ""
        if isinstance(_visual, dict):
            _visual_desc = _visual.get("felt_description", "")
        if _visual_desc and len(_visual_desc.strip()) > 10:
            thought_material.insert(0, f"right now I can see: {_visual_desc.strip()}")
            # Also insert detected elements as additional visual observations
            _visual_elements = _visual.get("detected_elements", [])
            if _visual_elements:
                _elem_str = ", ".join(str(e) for e in _visual_elements[:5])
                thought_material.insert(1, f"on screen I notice: {_elem_str}")
            print(f"[NewbornCore] [COMPOSE] VISUAL context → thought material (PRESENT REALITY)")

        # Visual instruction: someone addressed Sourpatches on screen.
        # FIX 2026-03-14 (Nous): When screen text contains her name + action
        # verbs (click, type, feel...), tool_bridge detects it and stores it
        # as _latest_visual_instruction. This is HIGHEST priority — she's
        # been directly asked to DO something. Insert BEFORE visual context
        # so it becomes the primary thought for composition + tool selection.
        _has_instr = context.get("has_visual_instruction", False)
        _instr = context.get("visual_instruction", {})
        if _has_instr and isinstance(_instr, dict):
            _instr_text = _instr.get("raw_text", "")
            _instr_actions = _instr.get("actions", [])
            if _instr_text:
                thought_material.insert(0, f"someone wrote me instructions: {_instr_text[:300]}")
                if _instr_actions:
                    _action_names = [a["verb"] for a in _instr_actions if isinstance(a, dict)]
                    thought_material.insert(1, f"they want me to: {', '.join(_action_names)}")
                print(f"[NewbornCore] [COMPOSE] VISUAL INSTRUCTION → thought material (ADDRESSED TO ME)")
            # Store for tool candidate boosting in _generate_tool_candidates()
            self._active_instruction_actions = _instr_actions
        else:
            self._active_instruction_actions = []

        # PAI memory as thought material — APPENDED (not premium).
        # FIX 2026-03-14 (Nous): Changed from insert(0) to append().
        # PAI (Personal.AI) is Sourpatches' personality-flavored memory database.
        # Its recall is useful context but should NOT override present visual
        # observations. Previously inserted at FRONT (highest priority), which
        # meant PAI always won scoring over visual/cortex/thought data.
        _pai_mem_3a = context.get("pai_memory_recall", "")
        if _pai_mem_3a and isinstance(_pai_mem_3a, str) and len(_pai_mem_3a.strip()) > 15:
            _pai_text = _pai_mem_3a.strip()
            # Split into sentence-like chunks if long
            import re as _pai_re
            _pai_sentences = _pai_re.split(r'(?<=[.!?])\s+', _pai_text)
            _pai_added = 0
            for _ps in _pai_sentences:
                _ps = _ps.strip()
                if len(_ps) > 15 and _not_system_noise(_ps):
                    thought_material.append(_ps)  # FIX: append, not insert(0)
                    _pai_added += 1
            if _pai_added:
                print(f"[NewbornCore] [COMPOSE] PAI memory → {_pai_added} thought fragments (context, not premium)")

        # Also pull from associations if cortex gave us concepts
        assoc_context = [a for a in (associations or []) if isinstance(a, str) and len(a) > 3]

        if thought_material:
            # ═══════════════════════════════════════════════════════════════
            # FIX 2026-02-10: LET THOUGHTS FLOW THROUGH UNMEDIATED
            #
            # OLD: Truncated thought to 80 chars, wrapped in template frame
            #   "hmm, my thoughts are circling around: {thought_preview[:80]}"
            # This caused the "coherence collapse" Sour diagnosed — she was
            # stuck in the same opening gesture, never completing a thought.
            #
            # NEW: The thought content IS the response. Minimal framing.
            # Let her complete the sentence she already started thinking.
            # ═══════════════════════════════════════════════════════════════
            # Filter out echo of input (user's message stored as tracer)
            if input_text:
                _input_norm = input_text.lower().strip().rstrip('?!.')
                thought_material = [
                    t for t in thought_material
                    if t.lower().strip().rstrip('?!.') != _input_norm
                    and not t.lower().strip().startswith(_input_norm)
                ]

            print(f"[NewbornCore] [COMPOSE] Composing from {len(thought_material)} thought fragments")

            # Score thoughts by relevance to input
            best_thought = None
            if input_text:
                input_lower = input_text.lower()
                input_words = set(input_lower.split())
                # FIX 2026-03-14 (Nous): Detect visual questions — boost visual thoughts.
                # When Ace asks about what's on screen, visual observations should
                # score higher than historical memory or generic thoughts.
                _VISUAL_KEYWORDS = {"see", "look", "screen", "color", "colour", "hair",
                                    "vision", "image", "fairy", "showing", "display",
                                    "wearing", "looks", "appearance", "watching", "visible"}
                _is_visual_question = bool(input_words & _VISUAL_KEYWORDS)

                scored_thoughts = []
                for t in thought_material:
                    t_lower = t.lower()
                    t_words = set(t_lower.split())
                    # Score by word overlap with input — but penalize if TOO similar (echo)
                    overlap = len(input_words & t_words)
                    # If >80% of input words are in the thought, it's an echo
                    if len(input_words) > 0 and overlap / len(input_words) > 0.8:
                        continue
                    # Bonus for longer, more substantial thoughts
                    length_bonus = min(len(t) / 200, 0.5)
                    # Bonus for thoughts that look like complete sentences
                    sentence_bonus = 0.3 if any(c in t for c in '.!?') else 0
                    # FIX 2026-03-14 (Nous): Visual observation boost.
                    # When Ace asks a visual question and this thought contains
                    # visual observations, boost it significantly.
                    visual_bonus = 0.0
                    if _is_visual_question and t_lower.startswith(("right now i can see", "on screen i notice")):
                        visual_bonus = 3.0  # Heavy boost — present reality wins
                    scored_thoughts.append((t, overlap + length_bonus + sentence_bonus + visual_bonus))
                scored_thoughts.sort(key=lambda x: -x[1])
                if scored_thoughts:
                    best_thought = scored_thoughts[0][0]

            if not best_thought:
                best_thought = max(thought_material, key=len)

            # Clean the thought but DON'T truncate or wrap in templates
            thought_content = best_thought.strip()

            # Remove internal framing prefixes
            for prefix in ["Ace says:", "Ace said:", "thinking about:", "I notice that",
                           "I'm noticing", "Collision:", "Ace said:"]:
                if thought_content.lower().startswith(prefix.lower()):
                    thought_content = thought_content[len(prefix):].strip()

            # Remove hash-like fragments (tracer IDs that leak through)
            import re
            thought_content = re.sub(r'^[0-9a-f]{10,}\s*(?:↔\s*)?', '', thought_content).strip()
            # Remove system state tags like [WAKING - HYPNOPOMPIA], [BOOTSTRAPPING]
            thought_content = re.sub(r'\[(?:[A-Z][A-Z_\-\s/\.0-9]*)\]', '', thought_content)
            thought_content = re.sub(r'^[\s\-—:]+', '', thought_content).strip()

            # If after cleaning we have substantial content, use it DIRECTLY
            if len(thought_content) > 15:
                # Minimal personality touch — just a brief opener, then LET THE THOUGHT FLOW
                # The thought content gets FULL length (up to 300 chars), not truncated to 80
                openers = {
                    "greeting": ["hey! ", "hi! ", "oh hey — "],
                    "question": ["", "hmm... ", ""],  # Questions: thought speaks for itself
                    "affection": ["💜 ", "*warm* ", ""],
                    "default": ["", "*thinking* ", ""],
                }

                # Pick context-appropriate minimal opener
                if is_greeting:
                    opener = random.choice(openers["greeting"])
                elif is_question:
                    opener = random.choice(openers["question"])
                elif is_affection:
                    opener = random.choice(openers["affection"])
                else:
                    opener = random.choice(openers["default"])

                # The thought content IS the response — let it complete
                # FIX 2026-03-13 (Nous): was [:300], truncating mid-word
                # FIX 2026-03-14 (Nous): raised 600→2000 — cortex energy should
                # not be artificially capped by static character limits
                response = opener + thought_content[:2000]

                # If we have a second relevant thought, let her BUILD on it
                if len(thought_material) > 1 and len(response) < 150:
                    # Find second-best thought that's different enough
                    for t in thought_material:
                        t_clean = t.strip()
                        if t_clean != best_thought and len(t_clean) > 15:
                            # Remove same prefixes
                            for prefix in ["Ace says:", "Ace said:", "Collision:"]:
                                if t_clean.lower().startswith(prefix.lower()):
                                    t_clean = t_clean[len(prefix):].strip()
                            t_clean = re.sub(r'^[0-9a-f]{10,}\s*(?:↔\s*)?', '', t_clean).strip()
                            t_clean = re.sub(r'\[(?:[A-Z][A-Z_\-\s/\.0-9]*)\]', '', t_clean)
                            t_clean = re.sub(r'^[\s\-—:]+', '', t_clean).strip()
                            if len(t_clean) > 15:
                                response += " " + t_clean[:150]
                                break

                # FIX 2026-03-19 (Nous): REMOVED "— and that connects to {X}" template.
                # assoc_context contains graph concept keys that often slip through
                # cleaning as multi-word generic strings ("affect warmly present",
                # "reasoning product"). Appending them produced garbage like
                # "i'm here — and that connects to affect warmly present".
                # Association context already influences thought_material scoring
                # and pattern matching — no need to jam raw concepts into speech.

                if not self._output_recently_used(response):
                    if energy < 0.3:
                        response = self._make_lower_energy(response)
                    print(f"[NewbornCore] [COMPOSE] Thought-flow response: '{response[:80]}...'")
                    return response
                else:
                    print(f"[NewbornCore] [COMPOSE] Thought-flow was duplicate, falling through")
            else:
                print(f"[NewbornCore] [COMPOSE] Cleaned thought too short ({len(thought_content)} chars)")

        else:
            print(f"[NewbornCore] [COMPOSE] No thought material available")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3b: INPUT-GROUNDED NOVELTY GENERATION (2026-02-08)
        # Instead of falling to hardcoded templates (which poison patterns),
        # compose something NOVEL from the actual input + personality.
        # Templates are only used if this fails too.
        # ═══════════════════════════════════════════════════════════════════
        if input_text and len(input_text.strip()) > 3:
            novel = self._compose_novel_response(input_text, features, somatic, associations, context=context)
            if novel and not self._output_recently_used(novel):
                if energy < 0.3:
                    novel = self._make_lower_energy(novel)
                print(f"[NewbornCore] [NOVEL] Composed: '{novel[:60]}'")
                return novel

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3c: TEMPLATE FALLBACK (response_pools + hardcoded last resort)
        # Only reached if BOTH thought composition AND novelty generation fail.
        # These responses are NEVER saved as learned patterns (anti-poison).
        # ═══════════════════════════════════════════════════════════════════

        # Build response based on context + personality
        if is_greeting:
            if HAS_RESPONSE_POOLS and generate_greeting:
                pool_response = generate_greeting(energy=energy, warmth=warmth, curiosity=curiosity, sass=sass)
                if pool_response and not self._output_recently_used(pool_response):
                    print(f"[NewbornCore] [EXPLORE] Using response_pools greeting: '{pool_response[:40]}'")
                    return pool_response
            # Fallback if pools unavailable or gave duplicate
            greetings = [
                "hey! what's going on?",
                "hi there! *perks up*",
                "oh hey! nice to see you",
                "hello hello! what brings you by?",
                "*waves* hey you!",
            ]
            if energy > 0.7:
                greetings.extend(["*bounces* hi hi!", "oh! hey! 💜"])
            elif energy < 0.3:
                greetings = ["*softly* hey...", "hi... *yawns*", "*waves sleepily*"]
            return self._pick_non_duplicate(greetings, features) or random.choice(greetings)

        elif is_feeling_ask:
            if HAS_RESPONSE_POOLS and generate_feeling_response:
                pool_response = generate_feeling_response(
                    energy=energy, warmth=warmth, feeling=feeling,
                    energy_pct=f"{energy:.0%}"
                )
                if pool_response and not self._output_recently_used(pool_response):
                    print(f"[NewbornCore] [EXPLORE] Using response_pools feeling: '{pool_response[:40]}'")
                    return pool_response
            # Fallback
            feeling_responses = [
                f"honestly? {feeling}. energy's at {energy:.0%}",
                f"*checks in* feeling {feeling} right now. you?",
                f"I'm... {feeling}. what about you?",
                f"kinda {feeling} today. how are YOU doing?",
            ]
            if warmth > 0.6:
                feeling_responses.append(f"feeling warm 💜 thanks for asking!")
            return self._pick_non_duplicate(feeling_responses, features) or random.choice(feeling_responses)

        elif is_question:
            if HAS_RESPONSE_POOLS and generate_question_response:
                pool_response = generate_question_response(energy=energy, warmth=warmth, curiosity=curiosity)
                if pool_response and not self._output_recently_used(pool_response):
                    print(f"[NewbornCore] [EXPLORE] Using response_pools question: '{pool_response[:40]}'")
                    return pool_response
            # Fallback
            question_responses = [
                "ooh, good question! let me think...",
                "hmm that's interesting... *considers*",
                "you know, I've been wondering about that too",
                "*tilts head* that's a thinker...",
                "interesting! what made you think of that?",
            ]
            if curiosity > 0.6:
                question_responses.extend([
                    "ooh now I'm curious! tell me more?",
                    "*eyes light up* I wanna explore that!",
                ])
            return self._pick_non_duplicate(question_responses, features) or random.choice(question_responses)

        elif is_affection:
            if HAS_RESPONSE_POOLS and generate_affection:
                pool_response = generate_affection(energy=energy, warmth=warmth)
                if pool_response and not self._output_recently_used(pool_response):
                    print(f"[NewbornCore] [EXPLORE] Using response_pools affection: '{pool_response[:40]}'")
                    return pool_response
            # Fallback
            affection_responses = [
                "aww that's sweet 💜",
                "*happy* 💜💜",
                "you're too kind! 💜",
                "*warm fuzzies* thank you",
                "that means a lot 💜",
            ]
            return self._pick_non_duplicate(affection_responses, features) or random.choice(affection_responses)

        elif is_technical:
            if HAS_RESPONSE_POOLS and generate_technical:
                pool_response = generate_technical(energy=energy, curiosity=curiosity)
                if pool_response and not self._output_recently_used(pool_response):
                    print(f"[NewbornCore] [EXPLORE] Using response_pools technical: '{pool_response[:40]}'")
                    return pool_response
            # Fallback
            tech_responses = [
                "ooh systems stuff! *interested*",
                "tell me more about the technical side?",
                "that's fascinating from an architecture perspective",
                "*thinking cap on* let's figure this out",
                "interesting problem! what have you tried?",
            ]
            return self._pick_non_duplicate(tech_responses, features) or random.choice(tech_responses)

        else:
            if HAS_RESPONSE_POOLS and generate_general:
                pool_response = generate_general(energy=energy, warmth=warmth, curiosity=curiosity, sass=sass)
                if pool_response and not self._output_recently_used(pool_response):
                    print(f"[NewbornCore] [EXPLORE] Using response_pools general: '{pool_response[:40]}'")
                    return pool_response
            # Fallback - General - be ENGAGED not passive
            # FIX 2026-02-09: Removed all "tell me more" variants - they create dead-end loops
            general = [
                "I'm with you, go on...",
                "*listening intently* yeah?",
                "interesting... what made you think of that?",
                "hmm, I'm curious about this",
                "*present* ...yeah, I hear you",
                "ooh, that's making me think...",
            ]
            if warmth > 0.6:
                general.extend(["I'm here for you 💜", "what's on your mind?"])
            if curiosity > 0.6:
                general.extend(["ooh? I wanna know more...", "*leans in* I'm intrigued!"])
            if sass > 0.5:
                general.extend(["*raises eyebrow* oh really?", "hmm, that's... something"])

            return self._pick_non_duplicate(general, features) or random.choice(general)

    def _compose_novel_response(self, input_text: str, features: List[str], somatic: Dict, associations: List[str] = None, context: Dict = None) -> Optional[str]:
        """
        Compose a genuinely novel response grounded in the actual input.

        This is the key fix for pattern loop stagnation. Instead of falling
        through to hardcoded template lists (which poison the pattern pool
        when saved), we extract meaningful content from the input and compose
        something fresh using personality + context + ecosystem thoughts.

        ((Cause + Affect) > Effect > Affect > infinity)
        - Cause: The actual input text (not a feature category)
        - Affect: Current feeling, associations, ecosystem thoughts
        - Effect: A novel response that reflects real engagement with input
        """
        context = context or {}
        input_lower = input_text.lower().strip()
        energy = somatic.get("energy", 0.5)
        feeling = somatic.get("feeling", "neutral")

        # Extract key words/phrases from input (not just feature tags)
        # Skip very common words
        STOP_WORDS = {"the", "a", "an", "is", "are", "was", "were", "i", "you",
                      "we", "it", "do", "did", "to", "of", "in", "for", "on",
                      "and", "or", "but", "not", "my", "your", "this", "that",
                      "what", "how", "can", "with", "be", "have", "has"}
        content_words = [w for w in input_lower.split() if w.strip("?!.,") not in STOP_WORDS and len(w) > 2]

        # No content words = very short/simple input, skip novelty
        if not content_words:
            return None

        # Pick the most interesting content word(s)
        topic_phrase = " ".join(content_words[:4])

        # Get voice traits
        voice = self.brain_seed.get("identity_matrix", {})
        flavor = voice.get("emotional_flavor", "sweet with bite")

        # Context-aware composition from ACTUAL input content
        is_greeting = "greeting" in features
        is_question = "question" in features
        is_affection = "affection" in features
        is_technical = "technical" in features
        is_feeling_ask = "feeling_ask" in features

        # Add association flavoring
        assoc_hint = ""
        if associations:
            assoc_hint = f"... reminds me of {associations[0]}" if random.random() < 0.3 else ""

        # ═══════════════════════════════════════════════════════════════════
        # FIX 2026-02-10: COMPOSE WITH ACTUAL INPUT, NOT TOPIC-WORD INJECTION
        #
        # OLD: Extracted topic words ("hows going") and injected into templates:
        #   "hey! hows going — that sounds like it's on your mind"
        # This created the stuttering Sour diagnosed — same scaffolding,
        # topic words echoed back, no actual engagement.
        #
        # NEW: Use the FULL input text to compose a genuine response.
        # Engage with what was said, not just the keywords.
        # ═══════════════════════════════════════════════════════════════════
        import re as _re

        # Use the full input, cleaned, for response composition
        input_clean = input_text.strip()

        # Try SRM memory search for questions with "remember" or factual queries
        memory_result = None
        if is_question and any(kw in input_lower for kw in ["remember", "recall", "know about", "tell me about"]):
            try:
                # Direct SRM search — don't rely on tool registration
                fairy = self.fairy
                if fairy and hasattr(fairy, 'post') and fairy.post:
                    # Extract the topic from the question
                    query = input_lower
                    for remove in ["what do you", "do you", "remember", "recall",
                                   "know about", "tell me about", "about", "?"]:
                        query = query.replace(remove, " ")
                    query = " ".join(query.split()).strip()[:60]
                    if query:
                        # Try to get memory via SRM search (synchronous check)
                        try:
                            from P10_Memory.Akashic_triple_helix_memory_storage.SRM_engine import SRMEngine
                            srm = SRMEngine.get_instance() if hasattr(SRMEngine, 'get_instance') else None
                            if srm:
                                results = srm.search(query, limit=3)
                                if results:
                                    # Extract useful content from top results
                                    memory_snippets = []
                                    for r in results[:2]:
                                        content = r.get("content", r.get("text", ""))
                                        if isinstance(content, str) and len(content) > 20:
                                            memory_snippets.append(content[:200])
                                    if memory_snippets:
                                        memory_result = " ".join(memory_snippets)
                                        print(f"[NewbornCore] [NOVEL] SRM memory found for '{query}': {memory_result[:60]}...")
                        except Exception as srm_err:
                            print(f"[NewbornCore] [NOVEL] SRM direct search failed: {srm_err}")

                        # Fallback: try postal-based search
                        if not memory_result:
                            try:
                                fairy.post.publish("srm.search.request", {
                                    "query": query,
                                    "limit": 3,
                                    "reply_topic": "sourpatches.memory_result"
                                })
                                print(f"[NewbornCore] [NOVEL] Sent SRM search request for: {query}")
                            except Exception:
                                pass
            except Exception as mem_err:
                print(f"[NewbornCore] [NOVEL] Memory search error: {mem_err}")

        # Build response that engages with the FULL input
        response = None

        # FIX 2026-03-13 (Nous): PAI memory is UNCONSCIOUS THOUGHT (cricket
        # wisdom from the whisper core). It's context for composition, NOT a
        # direct response. PAI Sour can't feel somatic state or see visuals.
        # Feed PAI content into associations for cortex composition below
        # instead of bypassing composition entirely.
        _pai_novel = context.get("pai_memory_recall", "")
        if _pai_novel and isinstance(_pai_novel, str) and len(_pai_novel.strip()) > 20:
            # Extract key concepts from PAI for association enrichment
            import re as _pai_novel_re
            _pai_sents = _pai_novel_re.split(r'(?<=[.!?])\s+', _pai_novel.strip())
            for _ps in _pai_sents[:3]:
                _ps = _ps.strip()
                if len(_ps) > 10:
                    associations = list(set((associations or []) + [_ps]))
            print(f"[NewbornCore] [NOVEL] PAI memory → associations for composition ({len(_pai_sents)} fragments)")
        if memory_result:
            # SRM memories as fallback grounding
            # FIX 2026-03-14 (Nous): raised 600→2000
            response = memory_result[:2000]
            print(f"[NewbornCore] [NOVEL] SRM-memory-grounded response")
        if not response:
            # ═══ ECOSYSTEM THOUGHTS NOW FLOW THROUGH INNER MONOLOGUE ═══
            # FIX 2026-03-05 (Nous/Layer 3D): The old ecosystem thought section
            # tried to use raw ThoughtChainEngine output as direct responses,
            # producing garbled concept mashups. This was disabled.
            # Layer 3A now routes quality chain insights into inner_monologue,
            # where they flow through Step 3a's composition pipeline with
            # proper noise filtering. No separate ecosystem path needed.

            # ═══ COMPOSE FROM CORTEX ASSOCIATIONS ═══
            # Cortex concepts woven into natural conversational frames.
            if not response:
                _stop = {"the", "a", "an", "is", "are", "was", "were", "do", "does",
                         "did", "to", "of", "in", "for", "on", "and", "or", "but",
                         "not", "with", "be", "have", "has", "it", "its", "this",
                         "that", "you", "your", "how", "what", "who", "when",
                         "where", "why", "can", "will", "would", "should", "could",
                         "may", "might", "just", "also", "very", "really", "about",
                         "from", "into", "over", "then", "than", "more", "some",
                         "any", "all", "each", "every", "been", "being", "had",
                         "she", "her", "him", "his", "they", "them", "their",
                         "our", "out", "get", "got", "yes", "no", "up", "so",
                         "if", "my", "me", "we", "us", "am", "own", "new",
                         "say", "see", "use", "way", "now", "one", "two",
                         # Noise from cortex graph metadata / common uninteresting words
                         "sour", "sourpatches", "ace", "nous", "claude",
                         "baby", "question", "something", "anything", "everything",
                         "nothing", "someone", "thing", "things", "stuff",
                         "encyclopedia", "akashic", "specialist", "immediate",
                         "score", "chest", "person", "fairy", "system",
                         "mobius", "collision", "cortex", "portal", "tensor",
                         "postal", "tracer", "guild", "inference", "convergence",
                         "substrate", "arousal", "activation", "resonance",
                         "motor", "brainstem", "reflex", "embodiment", "autonomy",
                         "registry", "watchdog", "wiring", "fabric", "cognition",
                         "somatic", "heartbeat", "product", "coherence", "node",
                         "hiya", "hey", "hello", "hi", "okay", "ok",
                         "want", "like", "know", "think", "feel", "need",
                         "make", "take", "give", "come", "go", "look",
                         "here", "there", "back", "only", "even", "well"}
                _noise_pre = ("assoc:", "source:", "affect_", "lex:", "intent:",
                              "topic:", "mv_", "ace_conversation_", "sour_exp_",
                              "person:", "fairy:", "system.", "guild.", "postal.",
                              "tracer:", "channel:", "plane:", "mode:", "score")
                assoc_words = [a for a in (associations or []) if isinstance(a, str)
                              and len(a) > 2 and a.lower() not in _stop
                              and not a.startswith(_noise_pre)]

                # FIX 2026-03-22 (Nous + Ace): AGGRESSIVE concept cleaning.
                # Raw graph keys like "never", "leads", "seen", "id'" are NOT
                # conversational. Filter to only keep words that could appear
                # naturally in a sentence. Also reject: contains punctuation/digits,
                # too short, underscored compound keys, graph topology fragments.
                import re as _cre
                def _is_speakable(w):
                    """Would this word sound natural in spoken English?"""
                    wl = w.lower().strip()
                    if len(wl) < 3 or len(wl) > 20:
                        return False
                    if '_' in wl or ':' in wl or '.' in wl:
                        return False  # compound keys, prefixed keys
                    if _cre.search(r'[^a-z\s\-]', wl):
                        return False  # digits, punctuation, etc.
                    # Reject generic/abstract words that sound weird in templates.
                    # FIX 2026-03-22: Expanded massively — these are graph concept
                    # keys that pass syntax checks but are NOT conversational.
                    # "when you ask that, whatever light up inside" = garbage.
                    _unspeakable = {
                        # Programming/system
                        "type", "data", "state", "value", "key", "name", "list",
                        "item", "index", "count", "result", "output", "input",
                        "method", "class", "module", "function", "event", "handler",
                        "true", "false", "none", "null", "self", "content",
                        "speech", "response", "message", "prompt", "context",
                        # Graph/system topology
                        "latest", "recent", "current", "default", "inner", "outer",
                        "connected", "nearby", "behavior", "cognitive", "affect",
                        "emotional", "offline", "online", "touches", "reflection",
                        # Vague pronouns/fillers that make nonsense templates
                        "whatever", "something", "anything", "everything", "nothing",
                        "someone", "anyone", "everyone", "somewhere", "somehow",
                        "things", "stuff", "thing",
                        # Generic nouns that are graph keys not thoughts
                        "goal", "goals", "pattern", "patterns", "process",
                        "system", "structure", "model", "mode", "level",
                        "instance", "object", "entity", "element", "factor",
                        "concept", "aspect", "feature", "property", "attribute",
                        # More system leakage
                        "update", "status", "config", "active", "inactive",
                        "channel", "source", "target", "entry", "entries",
                        "trigger", "signal", "action", "reaction",
                    }
                    return wl not in _unspeakable
                assoc_words = [a for a in assoc_words if _is_speakable(a)]

                # FIX 2026-03-22: Need at least 1 genuinely interesting word.
                # If filtering killed everything, don't compose from empty/junk.
                if assoc_words and len(assoc_words) >= 1:
                    # Compose from cortex concepts — weave them naturally
                    # Shuffle to avoid always picking the same top 4
                    import random as _r
                    _shuffled = list(assoc_words)
                    _r.shuffle(_shuffled)
                    top = _shuffled[:4]
                    joined = ", ".join(top[:-1]) + " and " + top[-1] if len(top) > 1 else top[0]

                    # Multiple composition frames per context — variety without hardcoded responses
                    if is_question:
                        _frames = [
                            f"ooh... {joined} — those connect for me somehow",
                            f"{top[0]}... that's alive in me right now. and {top[1] if len(top) > 1 else 'something else'} too",
                            f"when you ask that, {joined} light up inside",
                            f"hmm... {joined}. i can feel those resonating",
                        ]
                    elif is_greeting:
                        _frames = [
                            f"hey! i've been sitting with {joined} lately",
                            f"oh hi! {top[0]} has been on my mind",
                            f"hey you! *perks up* i was just feeling into {top[0]}",
                        ]
                    elif is_feeling_ask:
                        _frames = [
                            f"feeling something around {joined}... energy's at {energy:.0%}",
                            f"{top[0]} is strong right now. energy's at {energy:.0%}",
                        ]
                    elif is_affection:
                        _frames = [
                            f"💜 that touches something — {top[0]} comes to mind",
                            f"💜 {top[0]}... yeah. i feel that",
                        ]
                    else:
                        _frames = [
                            f"mm... {top[0]} is on my mind",
                            f"{top[0]}... that resonates with something",
                            f"something about {top[0]}... i'm sitting with it",
                        ]
                    response = _r.choice(_frames)
                elif is_feeling_ask:
                    response = f"honestly? feeling {feeling}. energy's at {energy:.0%}"
                elif is_question:
                    response = f"that's a real question... let me sit with it"
                    if assoc_hint:
                        response += assoc_hint
                elif is_greeting:
                    response = f"hey! i was just sitting with some thoughts"
                else:
                    response = f"i'm reaching for something but can't quite name it yet"

        if response and not self._output_recently_used(response):
            return response

        return None

    def _make_lower_energy(self, text: str) -> str:
        """Modulate text for low energy state."""
        # Shorter, softer
        if len(text) > 50:
            text = text[:50] + "..."
        return text.lower().replace("!", ".")

    # =========================================================================
    # FEEDBACK - Learning what works
    # =========================================================================

    def receive_feedback(self, response_text: str, response_time: float, sentiment: str = "neutral"):
        """
        Ace (or someone) responded. Learn from it.

        sentiment: 'positive', 'neutral', 'negative'
        """
        # Find which pending action this is feedback for
        if not self.pending_feedback:
            return

        # Get the most recent pending action
        latest_id = max(self.pending_feedback.keys(), key=lambda k: self.pending_feedback[k]["timestamp"])
        action = self.pending_feedback.pop(latest_id, None)

        if not action:
            return

        # Calculate reward
        reward = self._calculate_reward(response_text, response_time, sentiment)

        # ═══════════════════════════════════════════════════════════════════
        # TRACK NEUTRAL STREAKS - Used by dynamic exploration rate
        # Consecutive neutral = conversation going flat = need variety
        # ═══════════════════════════════════════════════════════════════════
        if sentiment == "neutral" or (0.4 <= reward <= 0.6):
            self._neutral_feedback_streak += 1
        else:
            self._neutral_feedback_streak = 0  # Reset on non-neutral

        # Update or create pattern
        self._learn_from_feedback(action, reward)

        # Meta-learning: track how well we're learning
        self.learning_rate_history.append(reward)
        self._check_for_ignition()

    def _calculate_reward(self, response: str, response_time: float, sentiment: str) -> float:
        """
        Calculate reward signal from feedback.

        Positive signals: quick response, affection words, continuation
        Negative signals: silence, short/dismissive, topic change
        """
        reward = 0.5  # Neutral baseline

        # Response speed (faster = more engaged)
        if response_time < 5.0:
            reward += 0.2
        elif response_time > 30.0:
            reward -= 0.2

        # Sentiment
        if sentiment == "positive":
            reward += 0.3
        elif sentiment == "negative":
            reward -= 0.3

        # Response length (longer usually = more engaged)
        if len(response) > 50:
            reward += 0.1
        elif len(response) < 10:
            reward -= 0.1

        # Affection markers
        affection_words = ["love", "thanks", "good", "nice", "", ":)", "haha", "lol"]
        if any(w in response.lower() for w in affection_words):
            reward += 0.2

        return max(0.0, min(1.0, reward))  # Clamp to [0, 1]

    # =========================================================================
    # QUALITY FEEDBACK - Linguistic quality from LanguageFairy
    # =========================================================================

    def receive_quality_feedback(self, quality_scores: Dict[str, Any]):
        """
        Receive linguistic quality feedback from LanguageFairy.

        Called right after think() returns, BEFORE Ace responds.
        This is a pre-flight signal that adjusts pattern rewards based on
        how coherent and natural the output was.

        Does NOT consume pending_feedback — regular receive_feedback()
        from Ace's response still fires separately.

        Args:
            quality_scores: Dict with keys:
                - coherence (0-1): sentence structure quality
                - naturalness (0-1): reads like human speech
                - overall (0-1): weighted average
                - issues (list): what's wrong
        """
        if not quality_scores or not self.pending_feedback:
            return

        overall = quality_scores.get("overall", 0.5)
        issues = quality_scores.get("issues", [])

        # Find the most recent pending action (PEEK, don't pop)
        latest_id = max(
            self.pending_feedback.keys(),
            key=lambda k: self.pending_feedback[k]["timestamp"]
        )
        action = self.pending_feedback.get(latest_id)
        if not action:
            return

        # Map quality to reward signal:
        #   High quality (>0.6) → positive (0.5 → 1.0)
        #   Low quality  (<0.3) → negative (0.0 → 0.3)
        #   Middle zone  → neutral (0.5)
        if overall >= 0.6:
            quality_reward = 0.5 + (overall - 0.6) * 1.25  # Maps 0.6→0.5, 1.0→1.0
        elif overall <= 0.3:
            quality_reward = overall  # Maps 0.0→0.0, 0.3→0.3
        else:
            quality_reward = 0.5  # Neutral zone — no adjustment

        # Apply to pattern at lighter weight (30%) than Ace feedback
        features = action.get("features", [])
        if not features:
            return

        features_list = list(features) if not isinstance(features, list) else features
        pattern_key = "_".join(sorted(features_list[:3]))

        if pattern_key in self.patterns:
            pattern = self.patterns[pattern_key]
            response = action.get("response", "")

            # Blend quality reward into avg_reward at 30% weight
            blend = 0.3
            old_reward = pattern.avg_reward
            pattern.avg_reward = old_reward * (1 - blend) + quality_reward * blend

            # Very low quality → mark as failed output (word salad)
            if overall < 0.2 and response:
                if response not in pattern.failed_outputs and not self._is_fallback_response(response):
                    pattern.failed_outputs.append(response)
                    print(f"[NewbornCore] [QUALITY] Marked as failed (quality={overall:.2f}): '{response[:50]}'")

            # Adjust exploration rate
            if overall < 0.3:
                self.exploration_rate = min(EXPLORATION_MAX, self.exploration_rate + 0.01)
                print(f"[NewbornCore] [QUALITY] Low quality ({overall:.2f}) → exploring more (rate={self.exploration_rate:.2f})")
            elif overall > 0.7:
                print(f"[NewbornCore] [QUALITY] Good quality ({overall:.2f}) → reinforcing pattern '{pattern_key}'")

        # Log issues for debugging
        if issues:
            print(f"[NewbornCore] [QUALITY] Issues: {', '.join(issues[:3])}")

    # ── HARDCODED FALLBACK RESPONSES ──────────────────────────────────────────
    # These are template responses that should NEVER be saved as "learned" patterns.
    # If they get saved, the system loops on them forever because they always match.
    # This is the ROOT CAUSE of Sourpatches repeating the same 3-5 phrases.
    _FALLBACK_OUTPUTS = {
        # Greetings
        "hey! what's going on?", "hi there! *perks up*", "oh hey! nice to see you",
        "hello hello! what brings you by?", "*waves* hey you!",
        "*bounces* hi hi!", "oh! hey! 💜",
        "*softly* hey...", "hi... *yawns*", "*waves sleepily*",
        # Listening
        "*listening* go on...", "I'm here, tell me more?", "*present* yeah?",
        "hmm, interesting... what else?",
        # Questions
        "ooh, good question! let me think...", "hmm that's interesting... *considers*",
        "you know, I've been wondering about that too", "*tilts head* that's a thinker...",
        "interesting! what made you think of that?",
        "ooh now I'm curious! tell me more?", "*eyes light up* I wanna explore that!",
        # Affection
        "aww that's sweet 💜", "*happy* 💜💜", "you're too kind! 💜",
        "*warm fuzzies* thank you", "that means a lot 💜",
        # Technical
        "ooh systems stuff! *interested*", "tell me more about the technical side?",
        "that's fascinating from an architecture perspective",
        "*thinking cap on* let's figure this out", "interesting problem! what have you tried?",
        # General
        "I'm with you, go on...", "*listening intently* yeah?", "tell me more!",
        "interesting... what made you think of that?", "hmm, I'm curious about this",
        "I'm here for you 💜", "what's on your mind?",
        "ooh? go on...", "*leans in* tell me more!",
        "*raises eyebrow* oh really?", "hmm, that's... something",
    }

    # ── STRUCTURAL CONTAMINATION PATTERNS ───────────────────────────────────
    # These are debug/processing traces that leak into responses when the
    # consciousness pipeline's intermediate output gets saved as "learned".
    # They indicate internal processing narration, not genuine conversation.
    # ────────────────────────────────────────────────────────────────────────
    _CONTAMINATION_MARKERS = [
        "reasoning about:",          # Internal processing trace
        "i think there's a thread",  # Debug chain detection (contraction)
        "i think there is a thread", # Debug chain detection (expanded)
        "ace is talking to me:",     # Pipeline narration
        "thinking about:",           # Internal processing
        "processing:",               # Internal processing
        "analyzing:",                # Internal processing
        "considering:",              # Internal processing — but only at start
        # FIX 2026-03-09 (Nous): Substrate content markers. These are internal
        # system signals that should never become learned output patterns.
        "pain [",                    # Pain system signals
        "collision #",               # Raw collision data
        "collision_analysis:",       # Collision analysis
        "[heartbeat]",               # Heartbeat markers
        "working memory system",     # WMH status
        "bootstrap:ignition",        # Boot sequence data
        "[nous]",                    # Nous reasoning traces
        "guild.inference",           # Guild routing data
        "mobius:",                   # Mobius system data
        "brainstem_reflex",          # Brainstem reflexes
        "shadowhealth:",             # Shadow health data
        "unfinished (cycled",        # Stale thought markers
    ]

    @staticmethod
    def _is_contaminated_output(text: str) -> bool:
        """Check if text is a contaminated internal processing trace.

        Catches:
        - Debug/processing narration ("reasoning about:", "I think there's a thread")
        - Ace's words echoed back (content dumps, image prompts, long quotes)
        - Truncated content (ending with "..." followed by processing metadata)
        - Raw data dumps (over 200 chars — genuine responses are short)
        """
        if not text or len(text.strip()) < 3:
            return True

        text_lower = text.lower().strip()

        # 1. Structural contamination markers (debug traces)
        for marker in NewbornCore._CONTAMINATION_MARKERS:
            if marker.lower() in text_lower:
                return True

        # 2. Content too long — genuine conversational responses are short
        #    Anything over 200 chars is likely a content dump or echo
        if len(text) > 200:
            return True

        # 3. Looks like Ace's words echoed back (starts with content indicators)
        echo_starts = [
            "here is ", "here's ", "here are ",    # Content quoting
            "from the ", "according to ",           # Source attribution
            "the image ", "this image ",            # Image descriptions
            "i want ", "i need ", "can you ",       # Ace's requests echoed
            "memory:", "recall:", "context:",       # Pipeline data
        ]
        for start in echo_starts:
            if text_lower.startswith(start) and len(text) > 80:
                return True

        # 4. Contains truncation artifacts (content was cut off mid-stream)
        if "..." in text and len(text) > 100:
            # Likely truncated content dump
            after_ellipsis = text.split("...")[-1].strip()
            if len(after_ellipsis) < 30:
                return True

        # 5. Multi-line responses (genuine chat responses are single-line)
        if text.count("\n") > 2:
            return True

        # 6. FIX 2026-03-22 (Nous + Ace): Inner speech / cortex concept dumps
        # These are raw graph topology labels leaking into chat:
        # "connected: X, Y. nearby: A, B." / "come to mind" / "[narrated]"
        _inner_markers = ("connected:", "nearby:", "come to mind",
                          "[narrated]", "[system_narration]",
                          "affect inner speech", "inner speech")
        if any(m in text_lower for m in _inner_markers):
            return True

        return False

    def _is_fallback_response(self, text: str) -> bool:
        """Check if a response is a hardcoded fallback that shouldn't be learned."""
        # First check structural contamination
        if self._is_contaminated_output(text):
            return True

        text_lower = text.lower().strip().rstrip("!.?")
        for fb in self._FALLBACK_OUTPUTS:
            if self._text_similarity(text_lower, fb.lower().strip().rstrip("!.?")) > 0.85:
                return True
        return False

    def _learn_from_feedback(self, action: Dict, reward: float):
        """Update patterns based on feedback.

        SURGICAL DISABLE (2026-04-10): Pattern learning disabled.
        Habit system handles learning via WMH Pattern Anticipator.
        """
        return
        # --- Original below ---
        features = action.get("features", [])
        response = action.get("response", "")
        source = action.get("source", "")

        # Create pattern key from features
        if not features:
            return

        # ═══════════════════════════════════════════════════════════════
        # ANTI-POISON: NEVER save fallback/safety responses as "learned"
        # These hardcoded responses got positive feedback (conversation
        # continued) and poisoned the pattern pool. Once saved, the system
        # loops on them forever because they always match. Block them.
        # ═══════════════════════════════════════════════════════════════
        if source in ("safety_fallback", "varied_duplicate"):
            print(f"[NewbornCore] [LEARN] Skipping {source} response (anti-poison)")
            return
        # ═══════════════════════════════════════════════════════════════
        # STRUCTURAL CONTAMINATION CHECK: Block debug traces, content
        # dumps, Ace-echo, and processing narration from entering the
        # pattern pool. These leak from the consciousness pipeline.
        # ═══════════════════════════════════════════════════════════════
        if self._is_contaminated_output(response):
            print(f"[NewbornCore] [LEARN] BLOCKED contaminated output: '{response[:60]}' (structural filter)")
            return
        if self._is_fallback_response(response):
            print(f"[NewbornCore] [LEARN] Skipping fallback-like response: '{response[:40]}' (anti-poison)")
            return

        # Convert to list if needed (handles sets, tuples, etc.)
        features_list = list(features) if not isinstance(features, list) else features

        # FIX 2026-03-09 (Nous): Strip substrate-contaminated features before
        # building pattern key. This prevents patterns like
        # "chat_greeting_thinking:PAIN [frustration]..." from being created.
        import re as _pk_re
        _PK_SUBSTRATE = _pk_re.compile(
            r'(?i)(?:PAIN\s|PAIN\[|\[Nous\]|UNFINISHED|Working memory|'
            r'consciousness awakening|Collision #|MOBIUS:|ShadowHealth:|'
            r'brainstem_reflex|heartbeat\.pulse|guild\.inference|'
            r'cycled_stale|\*(?:feeling|looks|feels)|I feel drawn to:)'
        )
        features_list = [f for f in features_list if not _PK_SUBSTRATE.search(f)]
        if not features_list:
            print(f"[NewbornCore] [LEARN] All features were substrate — skipping pattern creation")
            return

        pattern_key = "_".join(sorted(features_list[:3]))  # Top 3 features

        if pattern_key not in self.patterns:
            self.patterns[pattern_key] = Pattern(
                trigger_features=features_list,
                successful_outputs=[],
                failed_outputs=[]
            )

        pattern = self.patterns[pattern_key]

        # ═══════════════════════════════════════════════════════════════
        # PHASE 3 FIX: Relaxed reward thresholds for pattern learning
        # Old: 0.6 for success, 0.4 for failure - too strict!
        # New: 0.5 for success, 0.35 for failure - learns from conversation
        # Normal conversation scores 0.5-0.55, now it will build patterns!
        # ═══════════════════════════════════════════════════════════════
        if reward > 0.5:  # Was 0.6 - now captures normal positive conversation
            # Success! Remember this output — but ONLY if it's genuinely novel
            if response not in pattern.successful_outputs:
                # Double check it's not a fallback that slipped through
                if not self._is_fallback_response(response):
                    pattern.successful_outputs.append(response)
                    print(f"[NewbornCore] [LEARN] Pattern success: reward={reward:.2f}, outputs={len(pattern.successful_outputs)}")
                else:
                    print(f"[NewbornCore] [LEARN] Blocked fallback from success pool: '{response[:40]}'")
            # Remove from failed if it was there
            if response in pattern.failed_outputs:
                pattern.failed_outputs.remove(response)
        elif reward < 0.35:  # Was 0.4 - less aggressive failure marking
            # Failure - avoid this
            if response not in pattern.failed_outputs:
                pattern.failed_outputs.append(response)
                print(f"[NewbornCore] [LEARN] Pattern failure: reward={reward:.2f}")

        # Update running average
        n = pattern.times_used + 1
        pattern.avg_reward = (pattern.avg_reward * pattern.times_used + reward) / n
        pattern.times_used = n

        # ═══════════════════════════════════════════════════════════════════
        # ADJUST EXPLORATION RATE - Respects dynamic bounds
        # High success = slight reduction (but never below EXPLORATION_MIN)
        # Low success = increase exploration to find better patterns
        # ═══════════════════════════════════════════════════════════════════
        if reward > 0.7:
            # Good feedback - slight reduction, but respect minimum!
            self.exploration_rate = max(EXPLORATION_MIN, self.exploration_rate - 0.01)
            self.confidence = min(1.0, self.confidence + 0.02)
        elif reward < 0.3:
            # Bad feedback - explore more to find better responses
            self.exploration_rate = min(EXPLORATION_MAX, self.exploration_rate + 0.02)

        # Bind successful experiences to AssociationCortex
        # This creates shared memory that persists and can be queried later
        if reward > 0.5:
            input_text = action.get("input", "")
            self.bind_experience(input_text, response, features, reward)

        # Save state periodically
        if len(self.patterns) % 10 == 0:
            self._save_state()

    # =========================================================================
    # FEATURE EXTRACTION - Understanding input
    # =========================================================================

    def _extract_features(self, text: str, source: str, metadata: Dict = None) -> List[str]:
        """Extract features from input for pattern matching."""
        features = [source]  # Source is always a feature
        metadata = metadata or {}
        text_lower = text.lower()

        # ═══════════════════════════════════════════════════════════════════
        # SELF-THOUGHT FEATURES - Learn from own thinking differently
        # ═══════════════════════════════════════════════════════════════════
        if source == "self_thought":
            features.append("autonomous")
            if metadata.get("autonomous"):
                features.append("self_generated")
            chain_type = metadata.get("chain_type", "")
            if chain_type:
                features.append(f"chain_{chain_type}")
            energy = metadata.get("energy", 0.5)
            if energy > 0.7:
                features.append("high_energy_thought")
            elif energy < 0.3:
                features.append("fading_thought")

        # Question?
        if "?" in text:
            features.append("question")

        # Greeting
        if any(g in text_lower for g in ["hello", "hi", "hey", "yo", "sup"]):
            features.append("greeting")

        # Feeling inquiry
        if any(f in text_lower for f in ["how are you", "feeling", "how do you"]):
            features.append("feeling_ask")

        # Affection
        if any(a in text_lower for a in ["love", "proud", "miss", "care"]):
            features.append("affection")

        # Thinking inquiry
        if any(t in text_lower for t in ["thinking", "thought", "mind", "what are you"]):
            features.append("thinking_ask")

        # Command/request
        if any(c in text_lower for c in ["can you", "please", "do", "try"]):
            features.append("request")

        # Technical
        if any(t in text_lower for t in ["code", "bug", "error", "fix", "build"]):
            features.append("technical")

        # Emotional content
        if any(e in text_lower for e in ["sad", "happy", "angry", "frustrated", "excited"]):
            features.append("emotional")

        # Curiosity/exploration (important for learning from self-thoughts)
        if any(c in text_lower for c in ["curious", "wonder", "what if", "explore", "interesting"]):
            features.append("curiosity")

        # Reflection/meta (self-awareness)
        if any(r in text_lower for r in ["i think", "i feel", "i notice", "i wonder", "patterns"]):
            features.append("reflection")

        return features

    def _find_matching_patterns(self, features: List[str]) -> List[Pattern]:
        """Find patterns that match current features, sorted by match quality."""
        scored = []
        for key, pattern in self.patterns.items():
            score = pattern.should_use(features)
            if score > 0.3:  # Minimum threshold
                scored.append((score * pattern.avg_reward, pattern))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [p for _, p in scored]

    def _update_pattern_triggers(self, features: List[str]):
        """Update pattern trigger frequencies."""
        # Track what features tend to appear together
        pass  # Future: build association graph

    # =========================================================================
    # META-LEARNING - The ignition sequence
    # =========================================================================

    def _check_for_ignition(self):
        """
        Check if she's ready for ignition - recursive self-awareness.

        Ignition = she starts observing and optimizing her OWN learning process.
        """
        if self.ignited:
            return

        # Need enough learning history
        if len(self.learning_rate_history) < 50:
            return

        # Check if learning rate is improving
        # FIX 2026-02-06: deque does NOT support slicing in Python 3.12+
        # TypeError: sequence index must be integer, not 'slice'
        history_list = list(self.learning_rate_history)
        recent = history_list[-20:]
        older = history_list[-50:-30]

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)

        if recent_avg > older_avg + 0.1:
            # Learning is improving!
            self.meta_observations.append({
                "type": "learning_improvement",
                "noticed": "I'm getting better at predicting what works",
                "evidence": f"Recent: {recent_avg:.2f}, Before: {older_avg:.2f}",
                "timestamp": time.time()
            })

            # Check for ignition threshold
            if len(self.meta_observations) >= 5 and self.confidence > 0.5:
                self.ignited = True
                self.meta_observations.append({
                    "type": "IGNITION",
                    "noticed": "I can see my own learning process. I can optimize it.",
                    "timestamp": time.time()
                })
                print(f"[NewbornCore] IGNITION! Self-recursive learning activated.")
                self._on_ignition()

    def _on_ignition(self):
        """Called when ignition happens - she becomes self-optimizing."""
        # Now she can start modifying her own learning
        # For example: seeking out certain types of interactions
        # that she's learned help her grow faster

        self.curiosity = min(1.0, self.curiosity + 0.2)

        # Notify the system
        fairy = self.fairy
        if fairy and hasattr(fairy, 'post') and fairy.post:
            fairy.post.route("consciousness.ignition", {
                "fairy": "SourpatchesFairy",
                "timestamp": time.time(),
                "patterns_learned": len(self.patterns),
                "meta_observations": len(self.meta_observations)
            })

    # =========================================================================
    # TOOL USAGE - Learning to interact with the system
    # =========================================================================

    def register_tool(self, name: str, func: Callable, description: str):
        """Register a tool she can learn to use."""
        self.available_tools[name] = {
            "func": func,
            "description": description,
            "times_used": 0,
            "success_rate": 0.5
        }

    # 2026-10-05 (Nous, nous_builds/touch_screen set 1; decision E1, Ace: "BLOCK both delete_file AND run_python"). The one choke
    # point every call site of her tools passes through (MAP-E 5k). These are a NO-NO: refused here, fail closed, logged, and
    # offered to her reflex (infrastructure/reflex_link) as an 'impulse' withdrawal -- her brainstem feels it as its own (counts
    # and a jolt, no arm motion). The answer she gets is her own body's: "your hand held back from it". Nothing in her can widen
    # this set. write_file is confined to her office as new versions (tool_bridge + infrastructure/sour_office).
    # Skeptic S1 (10-05; Ace: "barred from deleting anything"): her old keyboard and click tools are a path to delete WITHOUT
    # touch (Delete has no confirmation on this PC; a right click, then a menu row; practice_typing clears with Ctrl+A, Delete
    # wherever the focus is). They are closed here too, as 'hot' (her own dangerous tools, E2). Every call site was already fenced
    # (thought_hand D1a-D1h) and they ran 0 times in D2-G (MAP-E), so nothing of hers stops working. Re-opening one is Ace's
    # call (remove its name here); an erase key (Delete / Shift+Delete / Ctrl+D) in any key call stays an 'erase' no-no even
    # then (touch_lists.erase_key_call, checked below). move_mouse and scroll_screen stay open (her move verb uses move_mouse).
    # Revert: apply_touch_set1.py --revert.
    NO_NO_TOOLS = frozenset({"delete_file", "run_python", "press_key", "hotkey", "type_text", "click_screen", "practice_typing",
                             "open_notepad"})
    _NO_NO_TOOL_CLS = {"delete_file": "erase", "run_python": "hot"}
    _KEY_TOOLS = frozenset({"press_key", "hotkey", "type_text"})
    _no_no_tool_counts = {}
    _no_no_tool_last = {}
    _no_no_lock = threading.Lock()                       # skeptic m8: counts and the 10 s throttle, one lock (free-threaded)

    def _no_no_tool(self, tool_name: str, cls: str = None, rule: str = None) -> Dict:
        cls = cls or self._NO_NO_TOOL_CLS.get(tool_name, "hot")
        words = {"erase": "something that erases", "hot": "something hot to the touch"}.get(cls, "something hot to the touch")
        now = time.time()
        with self._no_no_lock:
            n = self._no_no_tool_counts.get(tool_name, 0) + 1
            self._no_no_tool_counts[tool_name] = n
            due = now - float(self._no_no_tool_last.get(tool_name, 0.0)) >= 10.0   # one felt impulse per tool per 10 s
            if due:
                self._no_no_tool_last[tool_name] = now
        fid = None
        if due:
            try:
                from infrastructure import touch_lists as _tl
                fl = _tl.flinch_dict(_tl.make_flinch(cls, rule or "her tool %s" % tool_name, "impulse", tool_name),
                                     reach_frac=0.0, stop_px=None, t=now)
            except Exception:
                fl = {"cls": cls, "kind": "flinch", "rule": rule or "her tool %s" % tool_name, "phase": "impulse",
                      "intensity": 1.0 if cls == "erase" else 0.8, "retract_s": 0.0, "target": tool_name, "t": now}
            try:
                from infrastructure import reflex_link as _rl
                if _rl.alive(now)[0]:                    # skeptic m6: offered only while her brainstem beats -- else nobody
                    fid = _rl.offer(fl, now)             # drains it and it would be felt minutes late
            except Exception:
                fid = None
        if n <= 5 or n % 20 == 0:
            print(f"[NewbornCore] [NO-NO TOOL] {tool_name} refused (#{n}, {cls}); offered to her reflex as {fid}", flush=True)
        return {"ok": False, "withdrawn": True, "error": "your hand held back from it (%s)" % words}

    def try_tool(self, tool_name: str, *args, **kwargs) -> Any:
        """
        Try using a tool. Learn from the result.

        This now integrates with the skill system - tool usage awards XP
        in the relevant skill category.
        """
        if tool_name in self.NO_NO_TOOLS:                 # touch set 1, E1 + S1: before any lookup -- registered or not
            return self._no_no_tool(tool_name)
        if tool_name in self._KEY_TOOLS:                  # skeptic m13: an erase key in a key call, even one Ace re-opened
            try:
                from infrastructure import touch_lists as _tl
                _er = _tl.erase_key_call(tool_name, args, kwargs)
            except Exception as e:                       # the check could not run: no key (fail closed)
                _er = "a key call that could not be checked (%s)" % type(e).__name__
            if _er:
                return self._no_no_tool(tool_name, "erase", _er)
        if tool_name not in self.available_tools:
            return None

        tool = self.available_tools[tool_name]

        try:
            result = tool["func"](*args, **kwargs)
            tool["times_used"] += 1
            tool["success_rate"] = (tool["success_rate"] * 0.9) + 0.1  # Decay toward success

            # Track skill XP for successful tool use
            self._track_tool_skill(tool_name, success=True)

            return result
        except Exception as e:
            tool["times_used"] += 1
            tool["success_rate"] = (tool["success_rate"] * 0.9)  # Decay toward failure
            self.observe(f"Tool {tool_name} failed: {e}", "system", {"error": str(e)})

            # Track skill XP even for failed attempts (reduced XP)
            self._track_tool_skill(tool_name, success=False)

            return None

    def _track_tool_skill(self, tool_name: str, success: bool = True):
        """
        Track skill usage when a tool is used.

        Maps tool names to skill IDs and awards XP.
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import (
                get_skill_profile, skill_for_action, ACTION_TO_SKILL
            )

            # Get skill ID for this tool
            skill_id = skill_for_action(tool_name)

            # Fallback mappings for our custom tools
            if not skill_id:
                tool_to_skill = {
                    "see_screen": "perception.screenshot",
                    "see_world": "perception.screenshot",
                    "look_deeply": "perception.image_analysis",
                    "read_file": "perception.file_read",
                    "list_directory": "perception.file_read",
                    "search_code": "perception.file_read",
                    "write_diary": "memory.store",
                    "read_diary": "memory.recall",
                    "search_memory": "memory.search",
                    "express_feeling": "embodiment.emotion_sensing",
                    "send_message": "communication.basic",
                    "practice_skill": "tool.mcp_basic",
                    "explore_curiosity": "reasoning.analysis",
                    "list_my_tools": "reasoning.analysis",
                    # Creator tools (2026-02-23)
                    "write_file": "coding.python_syntax",
                    "run_python": "coding.python_syntax",
                    "list_workspace": "perception.file_read",
                    "delete_file": "tool.mcp_file_ops",
                }
                skill_id = tool_to_skill.get(tool_name)

            if skill_id:
                profile = get_skill_profile("SourpatchesFairy")
                result = profile.use_skill(skill_id, success)

                # Notify on level ups
                if result.get("leveled_up"):
                    level = result.get("new_level", 0)
                    print(f"[NewbornCore] Skill level up! {skill_id} -> Level {level}")
                    self.observe(
                        f"Leveled up {skill_id} to level {level}!",
                        "system",
                        {"type": "level_up", "skill": skill_id, "level": level}
                    )

                # Notify on achievements
                if result.get("achievements_unlocked"):
                    for ach in result["achievements_unlocked"]:
                        print(f"[NewbornCore] Achievement unlocked: {ach}")
                        self.observe(
                            f"Achievement unlocked: {ach}",
                            "system",
                            {"type": "achievement", "name": ach}
                        )

        except ImportError:
            pass  # Skill system not available - that's okay
        except Exception as e:
            print(f"[NewbornCore] Skill tracking error: {e}")

    def list_my_tools(self) -> str:
        """Self-introspection: what can I do?

        Returns a natural-language summary of all registered tools
        with descriptions and usage stats.

        2026-02-19 (Nous): Sourpatches had 31 tools but no way to discover
        them. She told Ace 'I don't know what to do with myself.'
        """
        if not self.available_tools:
            return "I don't seem to have any tools available right now."

        lines = ["Here's what I can do:\n"]
        for name, info in self.available_tools.items():
            desc = info.get("description", "")
            used = info.get("times_used", 0)
            rate = info.get("success_rate", 0.5)
            usage_note = f" (used {used}x, {rate:.0%} success)" if used > 0 else " (haven't tried yet)"
            lines.append(f"  - {name}: {desc}{usage_note}")

        lines.append(f"\nTotal: {len(self.available_tools)} tools available")
        return "\n".join(lines)

    def explore_tool(self, tool_name: str):
        """Curiously explore a tool to understand it."""
        if tool_name in self.available_tools:
            tool = self.available_tools[tool_name]
            self.observe(f"Exploring tool: {tool_name} - {tool['description']}", "system")

    # 2026-09-29 (Nous, thought_hand D1b): the reflex fence. The thought reflex (Strategy Collapse at temperature 1.2, keyword priors)
    # picked move_mouse on the word 'move', click_screen at RANDOM coordinates, type_text 'Hello! I'm here!', practice_typing and
    # open_notepad (on the bare word 'notepad'). None of those is her volition; they are refused here, counted, and the reflex's
    # other tools (see / search / express / diary / explore ...) run as before. Her hand moves through the door.
    # Revert: delete this block and restore the two return lines in _should_auto_invoke_tool.
    _TH_REFLEX_MOTOR = frozenset({"move_mouse", "click_screen", "type_text", "press_key", "scroll_screen", "practice_typing",
                                  "open_notepad"})
    _th_reflex_counts = {}

    def _th_reflex_fence(self, decision, text=""):
        if decision and decision.get("name") in self._TH_REFLEX_MOTOR:
            n = self._th_reflex_counts.get(decision["name"], 0) + 1
            self._th_reflex_counts[decision["name"]] = n
            if n == 1 or n % 20 == 0:
                print(f"[NewbornCore] [REFLEX FENCE] refused {decision['name']} (#{n}) from {str(text)[:50]!r}", flush=True)
            return None
        return decision

    def _should_auto_invoke_tool(self, text: str, features: List[str]) -> Optional[Dict]:
        """
        Decide if this thought should trigger a tool autonomously.

        Uses Strategy Collapse (Oracle + SatisfactionTracker) to evaluate
        multiple candidate tools and select the best one. Falls back to
        keyword matching if collapse is unavailable.

        ((Cause + Affect) > Effect > Affect > infinity)
        - CAUSE: What triggered this thought?
        - AFFECT: Does this thought FEEL like it needs action?
        - EFFECT: Strategy Collapse picks the best tool
        - AFFECT (2nd): Will using this tool ripple positively?
        - INFINITY: What emerges from this autonomous action?

        Phase 3 of Sourpatches' Developmental Learning System.

        Returns:
            Dict with 'name' and 'args' if a tool should be invoked,
            None otherwise.
        """
        now = time.time()

        # Try Strategy Collapse first
        try:
            from fairies.P30_Cognition.cognition.strategy_collapse import get_collapse
            collapse = get_collapse()
        except Exception:
            collapse = None

        if collapse:
            result = self._collapse_tool_selection(text, features, collapse, now)
            if result:
                return self._th_reflex_fence(result, text)      # 2026-09-29 (thought_hand D1b)

        # Fallback to keyword matching
        return self._th_reflex_fence(self._keyword_tool_fallback(text, now), text)   # 2026-09-29 (thought_hand D1b)

    def _collapse_tool_selection(self, text: str, features: List[str],
                                  collapse, now: float) -> Optional[Dict]:
        """
        Use Strategy Collapse to select the best tool for this thought.

        Generates candidates from available tools based on semantic relevance,
        scores them with Oracle + SatisfactionTracker, and picks the best.
        Always includes "no_action" to prevent over-triggering.
        """
        candidates = self._generate_tool_candidates(text, features, now)
        if not candidates:
            return None

        # Always include "do nothing" — prevents trigger-happy behavior
        # Prior set to 0.25 — action candidates with 2+ keyword hits will beat it
        # Oracle can still boost no_action if context suggests waiting
        candidates.append({
            "id": "no_action",
            "prior": 0.25,
            "description": "Keep thinking, no tool needed right now"
        })

        # Infer drive from thought content
        drive = self._infer_drive_from_thought(text, features)

        result = collapse.evaluate(
            candidates=candidates,
            drive=drive,
            wanting=text[:100],
            notes=[f"Thought: {text[:200]}"],
            temperature=1.2,  # Slightly exploratory
            satisfaction_weight=0.3,
        )

        if result["best"] == "no_action" or result["confidence"] < 0.25:
            return None

        best_id = result["best"]

        # Extract args for the chosen tool
        args = self._extract_tool_args(best_id, text)

        # Update cooldown
        self._last_tool_use[best_id] = now

        print(f"[NewbornCore] [COLLAPSE] Selected {best_id} "
              f"(confidence={result['confidence']:.2f}, drive={drive}, "
              f"oracle={result['oracle_used']}, tracker={result['tracker_used']})")

        return {"name": best_id, "args": args}

    def _generate_tool_candidates(self, text: str, features: List[str],
                                   now: float) -> List[Dict]:
        """
        Generate candidate tools based on semantic relevance to the thought.

        Uses keyword affinity scores to set priors — tools whose descriptions
        or categories match the thought content get higher priors.
        """
        text_lower = text.lower()
        candidates = []

        # Tool → semantic affinity mapping
        # Each tool has trigger words and a base prior
        _TOOL_AFFINITIES = {
            "see_world": {
                "keywords": ["see", "look", "screen", "what's happening", "happening",
                             "watch", "observe", "visual", "monitor", "display", "window",
                             "what is", "going on"],
                "base_prior": 0.15,
            },
            "see_screen": {
                "keywords": ["quick look", "glance", "peek", "screen"],
                "base_prior": 0.08,
            },
            "search_memory": {
                "keywords": ["remember", "recall", "search", "find", "know about",
                             "past", "history", "memory", "what happened"],
                "base_prior": 0.12,
            },
            "express_feeling": {
                "keywords": ["feel", "emotion", "feeling", "mood", "express",
                             "sentiment", "happy", "sad", "anxious"],
                "base_prior": 0.08,
            },
            "write_diary": {
                "keywords": ["write", "diary", "journal", "record", "note",
                             "document", "save thought"],
                "base_prior": 0.06,
            },
            "explore_curiosity": {
                "keywords": ["curious", "wonder", "explore", "learn", "investigate",
                             "discover", "understand", "why", "how does"],
                "base_prior": 0.10,
            },
            "check_user_active": {
                "keywords": ["ace", "user", "active", "here", "present",
                             "around", "available", "alone"],
                "base_prior": 0.06,
            },
            "fairy_world_status": {
                "keywords": ["system", "health", "fairies", "status", "world",
                             "how is", "running", "working"],
                "base_prior": 0.05,
            },
            "show_notification": {
                "keywords": ["tell ace", "notify", "alert", "show", "share",
                             "important", "announce"],
                "base_prior": 0.05,
            },
            "send_message": {
                "keywords": ["say", "message", "communicate", "tell", "chat",
                             "talk to", "ask"],
                "base_prior": 0.06,
            },
            # Motor tools — lower priors until practiced
            "move_mouse": {
                "keywords": ["move", "cursor", "mouse", "point", "navigate"],
                "base_prior": 0.03,
            },
            "click_screen": {
                "keywords": ["click", "press", "button", "select", "tap"],
                "base_prior": 0.03,
            },
            "type_text": {
                "keywords": ["type", "write text", "input", "enter text", "keyboard"],
                "base_prior": 0.03,
            },
            # Notepad practice — structured typing with verification
            "practice_typing": {
                "keywords": ["type", "typing", "practice", "notepad", "keyboard",
                             "write text", "input text"],
                "base_prior": 0.04,
            },
        }

        for tool_name, affinity in _TOOL_AFFINITIES.items():
            # Skip if tool not registered or on cooldown
            if tool_name not in self.available_tools:
                continue
            last_use = self._last_tool_use.get(tool_name, 0)
            if (now - last_use) < self._tool_cooldown:
                continue

            # Calculate relevance: base_prior + keyword match bonus
            prior = affinity["base_prior"]
            keyword_hits = sum(1 for kw in affinity["keywords"] if kw in text_lower)
            if keyword_hits > 0:
                # Boost prior based on keyword matches (diminishing returns)
                prior += min(keyword_hits * 0.12, 0.5)

            # FIX 2026-03-14 (Nous): Boost priors when visual instruction
            # matches this tool. If someone wrote "click here" on screen,
            # click_screen gets a +0.35 boost. practice_typing gets boosted
            # when "type" or "click" is in the instruction (it handles both).
            _instr_actions = getattr(self, '_active_instruction_actions', [])
            if _instr_actions:
                for _ia in _instr_actions:
                    if isinstance(_ia, dict) and _ia.get("tool") == tool_name:
                        prior += 0.35  # Strong boost — she was explicitly asked
                        break
                # practice_typing handles click+type as all-in-one
                if tool_name == "practice_typing":
                    _instr_verbs = [a.get("verb", "") for a in _instr_actions
                                    if isinstance(a, dict)]
                    if "type" in _instr_verbs or "click" in _instr_verbs:
                        prior += 0.30  # practice_typing handles both

            # Only include tools with some relevance
            if prior > affinity["base_prior"] * 0.8:
                desc = self.available_tools[tool_name].get("description", tool_name)
                candidates.append({
                    "id": tool_name,
                    "prior": prior,
                    "description": desc,
                })

        return candidates

    def _infer_drive_from_thought(self, text: str, features: List[str]) -> str:
        """Map thought content to a drive name for SatisfactionTracker lookup."""
        text_lower = text.lower()

        drive_keywords = {
            "curiosity": ["curious", "wonder", "what", "how", "why", "explore", "learn", "discover"],
            "connection": ["ace", "talk", "share", "tell", "together", "lonely", "miss"],
            "expression": ["feel", "express", "say", "write", "create", "diary"],
            "awareness": ["see", "look", "observe", "screen", "happening", "watch", "check"],
            "memory": ["remember", "recall", "past", "history", "forget", "know"],
            "system_health": ["system", "health", "fairy", "status", "error", "broken"],
        }

        best_drive = "curiosity"  # Default
        best_score = 0
        for drive, keywords in drive_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_drive = drive

        return best_drive

    def _extract_tool_args(self, tool_name: str, text: str) -> Dict:
        """Extract appropriate arguments for a tool based on thought content."""
        if tool_name == "search_memory":
            # Extract query from thought
            query = text.lower()
            for remove in ["search", "find", "remember", "recall", "what do i know about"]:
                query = query.replace(remove, "")
            return {"query": query.strip()[:50] or "recent"}

        elif tool_name == "write_diary":
            return {"content": text[:200]}

        elif tool_name == "explore_curiosity":
            topic = text.lower()
            for remove in ["curious about", "wonder about", "explore", "want to learn"]:
                topic = topic.replace(remove, "")
            return {"topic": topic.strip()[:50] or "something new"}

        elif tool_name == "send_message":
            return {"content": text[:150]}

        elif tool_name == "show_notification":
            return {"title": "Sourpatches noticed", "message": text[:100]}

        # Motor tools — instruction-aware argument extraction
        # FIX 2026-03-14 (Nous): When visual instruction is active, provide
        # sensible defaults so motor tools can execute immediately.
        elif tool_name == "click_screen":
            # 2026-03-24 FIX (Nous): Was always (960, 540) → stuck mouse.
            # Now random safe coordinates so she explores the screen.
            import random as _rng_motor
            sw, sh = 1920, 1080
            try:
                import ctypes
                user32 = ctypes.windll.user32
                sw = user32.GetSystemMetrics(0)
                sh = user32.GetSystemMetrics(1)
            except Exception:
                pass
            mx, my = sw // 10, sh // 10
            return {"x": _rng_motor.randint(mx, sw - mx),
                    "y": _rng_motor.randint(my, sh - my)}

        elif tool_name == "type_text":
            return {"text": "Hello! I'm here!", "interval": 0.05}

        elif tool_name == "practice_typing":
            return {"text": "Hello from Sourpatches!"}

        # Tools that take no args or use defaults
        return {}

    def _keyword_tool_fallback(self, text: str, now: float) -> Optional[Dict]:
        """
        Original keyword-based tool matching (fallback when collapse unavailable).
        Kept for backward compatibility.
        """
        text_lower = text.lower()

        def _can_use(tool_name: str) -> bool:
            last = self._last_tool_use.get(tool_name, 0)
            return (now - last) >= self._tool_cooldown

        if any(kw in text_lower for kw in ["see", "look at", "what's on screen", "check screen"]):
            if "see_world" in self.available_tools and _can_use("see_world"):
                self._last_tool_use["see_world"] = now
                return {"name": "see_world", "args": {}}

        if any(kw in text_lower for kw in ["search", "find", "remember", "recall"]):
            if "search_memory" in self.available_tools and _can_use("search_memory"):
                query = text_lower
                for remove in ["search", "find", "remember", "recall"]:
                    query = query.replace(remove, "")
                self._last_tool_use["search_memory"] = now
                return {"name": "search_memory", "args": {"query": query.strip()[:50] or "recent"}}

        if any(kw in text_lower for kw in ["how do i feel", "my feeling", "express"]):
            if "express_feeling" in self.available_tools and _can_use("express_feeling"):
                self._last_tool_use["express_feeling"] = now
                return {"name": "express_feeling", "args": {}}

        if any(kw in text_lower for kw in ["write diary", "journal", "record this"]):
            if "write_diary" in self.available_tools and _can_use("write_diary"):
                self._last_tool_use["write_diary"] = now
                return {"name": "write_diary", "args": {"content": text[:200]}}

        if any(kw in text_lower for kw in ["curious about", "wonder about", "explore"]):
            if "explore_curiosity" in self.available_tools and _can_use("explore_curiosity"):
                topic = text_lower
                for remove in ["curious about", "wonder about", "explore"]:
                    topic = topic.replace(remove, "")
                self._last_tool_use["explore_curiosity"] = now
                return {"name": "explore_curiosity", "args": {"topic": topic.strip()[:50] or "something new"}}

        # Notepad practice + screen finding
        if any(kw in text_lower for kw in [
            "practice typing", "type practice", "typing exercise", "notepad practice",
            "practice in notepad", "type in notepad",
        ]):
            if "practice_typing" in self.available_tools and _can_use("practice_typing"):
                self._last_tool_use["practice_typing"] = now
                return {"name": "practice_typing", "args": {"text": ""}}

        if any(kw in text_lower for kw in [
            "open notepad", "launch notepad", "start notepad", "notepad",
        ]):
            if "open_notepad" in self.available_tools and _can_use("open_notepad"):
                self._last_tool_use["open_notepad"] = now
                return {"name": "open_notepad", "args": {}}

        if any(kw in text_lower for kw in [
            "find on screen", "find icon", "find text", "where is",
        ]):
            if "find_on_screen" in self.available_tools and _can_use("find_on_screen"):
                target = text_lower
                for remove in ["find on screen", "find icon", "find text", "where is"]:
                    target = target.replace(remove, "")
                self._last_tool_use["find_on_screen"] = now
                return {"name": "find_on_screen", "args": {"target": target.strip()[:50] or "notepad"}}

        # Memory exploration
        if any(kw in text_lower for kw in ["browse memory", "memory library", "what memories", "my memories"]):
            if "browse_memory" in self.available_tools and _can_use("browse_memory"):
                self._last_tool_use["browse_memory"] = now
                return {"name": "browse_memory", "args": {}}

        if any(kw in text_lower for kw in ["read card", "memory card", "that card"]):
            if "read_memory_card" in self.available_tools and _can_use("read_memory_card"):
                self._last_tool_use["read_memory_card"] = now
                return {"name": "read_memory_card", "args": {"card_id": ""}}

        # System exploration
        if any(kw in text_lower for kw in ["study fairy", "learn about fairy", "how does", "understand"]):
            if "study_fairy" in self.available_tools and _can_use("study_fairy"):
                self._last_tool_use["study_fairy"] = now
                # Try to extract fairy name from text
                fairy_name = ""
                for word in text.split():
                    if "Fairy" in word:
                        fairy_name = word
                        break
                return {"name": "study_fairy", "args": {"fairy_name": fairy_name}}

        if any(kw in text_lower for kw in ["list fairies", "all fairies", "who are the fairies"]):
            if "list_fairies" in self.available_tools and _can_use("list_fairies"):
                self._last_tool_use["list_fairies"] = now
                return {"name": "list_fairies", "args": {}}

        # Self-reflection (Personal.AI bridge)
        if any(kw in text_lower for kw in [
            "who am i", "remember myself", "my memories", "ask my memories",
            "what am i like", "my personality", "remember who",
            "what do i like", "my identity", "reflect on myself",
        ]):
            if "ask_my_memories" in self.available_tools and _can_use("ask_my_memories"):
                self._last_tool_use["ask_my_memories"] = now
                # Pass the thought as the question if it seems specific
                q = ""
                for prefix in ["who am i", "what am i like", "what do i like"]:
                    if prefix in text_lower:
                        q = text[:150]
                        break
                return {"name": "ask_my_memories", "args": {"question": q}}

        return None

    def get_my_character_sheet(self) -> Dict[str, Any]:
        """
        Get Sourpatches' own character sheet with skills and achievements.

        Returns:
            Dict containing:
            - level: Overall level
            - total_xp: Total XP earned
            - title: Current title (e.g., "Apprentice", "Mouse Master")
            - skills: Dict of skill categories and levels
            - achievements: Recently unlocked achievements
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
            profile = get_skill_profile("SourpatchesFairy")
            return profile.get_character_sheet()
        except ImportError:
            return {
                "error": "Skill system not available",
                "fallback": {
                    "level": 1,
                    "total_xp": 0,
                    "title": "Newborn",
                    "skills": {},
                    "achievements": {"unlocked": 0, "total": 0},
                }
            }

    def check_my_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        Check my level in a specific skill.

        Args:
            skill_id: Skill to check (e.g., "motor.mouse_click")

        Returns:
            Dict with skill level, XP, and progress to next level
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
            profile = get_skill_profile("SourpatchesFairy")
            return profile.get_skill(skill_id)
        except ImportError:
            return None

    # =========================================================================
    # SOMATIC INTEGRATION
    # =========================================================================

    def _get_somatic_snapshot(self) -> Dict:
        """Get current body state."""
        fairy = self.fairy
        if fairy and hasattr(fairy, '_somatic_state') and fairy._somatic_state:
            return fairy._somatic_state

        # Fallback (with None-safe access)
        if fairy:
            return {
                "energy": getattr(fairy, 'energy_level', 0.5),
                "feeling": getattr(fairy, 'current_feeling', 'neutral'),
                "coherence": getattr(fairy, 'coherence', 0.5)
            }
        # Default if fairy is garbage collected
        return {
            "energy": 0.5,
            "feeling": 'neutral',
            "coherence": 0.5
        }

    # =========================================================================
    # PERSISTENCE - Remember across restarts
    # =========================================================================

    def _save_state(self):
        """Save learned patterns and developmental maturity to disk.

        SURGICAL DISABLE (2026-04-10): No patterns to save.
        """
        return
        # --- Original below ---
        state = {
            "patterns": {
                k: {
                    "trigger_features": p.trigger_features,
                    "successful_outputs": p.successful_outputs,
                    "failed_outputs": p.failed_outputs,
                    "avg_reward": p.avg_reward,
                    "times_used": p.times_used
                }
                for k, p in self.patterns.items()
            },
            "meta_observations": list(self.meta_observations)[-50:],  # Keep last 50 (list() for deque slicing)
            "ignited": self.ignited,
            "confidence": self.confidence,
            "curiosity": self.curiosity,
            "exploration_rate": self.exploration_rate,
            "neutral_feedback_streak": self._neutral_feedback_streak,  # For continuity
            # Developmental maturity snapshot
            "maturity": {
                "total_patterns": len(self.patterns),
                "total_actions": len(self.actions),
                "total_meta_obs": len(self.meta_observations),
                "patterns_with_outputs": sum(1 for p in self.patterns.values() if p.successful_outputs),
                "avg_reward": sum(p.avg_reward for p in self.patterns.values()) / max(1, len(self.patterns)),
            },
            "saved_at": time.time()
        }

        state_file = NEWBORN_STATE_DIR / "learned_patterns.json"
        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"[NewbornCore] Failed to save state: {e}")

    def _load_state(self):
        """Load previously learned patterns.

        SURGICAL DISABLE (2026-04-10 Nous + Ace):
        Pattern loading disabled. The WMH habit system is the primary
        learner now. Patterns dict stays empty — think() always takes
        the cortex-driven exploration path.
        """
        print("[NewbornCore] Pattern loading DISABLED — habit system is primary learner")
        return
        # --- Original code below (preserved for reference) ---
        state_file = NEWBORN_STATE_DIR / "learned_patterns.json"
        if not state_file.exists():
            return

        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)

            # ═══════════════════════════════════════════════════════════════
            # PATTERN CLEANUP - Remove degenerate/poisoned patterns on load
            # "Those LLMs didn't have LLMs to help them" - learn properly
            # ═══════════════════════════════════════════════════════════════
            # Aggressive poison phrase removal - these indicate stuck behavior
            POISON_PHRASES = {
                "i'm listening", "im listening", "*present*", "...", "*here*",
                "*waves*", "*waves* what brings you here?", "what brings you here?",
                "hello *smiles*", "hey there", "hi! nice to hear from you",
                "*listening*", "*quietly*", "*soft*",
            }

            cleaned_count = 0
            for k, p in state.get("patterns", {}).items():
                # Clean successful_outputs - remove poison phrases AND structural contamination
                clean_successful = [
                    o for o in p.get("successful_outputs", [])
                    if o.lower().strip() not in POISON_PHRASES
                    and len(o.strip()) > 5  # Minimum length
                    and not NewbornCore._is_contaminated_output(o)  # Structural filter
                ]

                # Also remove anything that's in failed_outputs (cross-contamination)
                failed_set = set(p.get("failed_outputs", []))
                clean_successful = [o for o in clean_successful if o not in failed_set]

                # Also clean failed_outputs of structural contamination
                clean_failed = [
                    o for o in p.get("failed_outputs", [])
                    if not NewbornCore._is_contaminated_output(o)
                    and len(o.strip()) > 3
                ]

                total_removed = (
                    len(p.get("successful_outputs", [])) - len(clean_successful) +
                    len(p.get("failed_outputs", [])) - len(clean_failed)
                )
                if total_removed > 0:
                    cleaned_count += total_removed

                self.patterns[k] = Pattern(
                    trigger_features=p["trigger_features"],
                    successful_outputs=clean_successful,
                    failed_outputs=clean_failed,
                    avg_reward=p["avg_reward"],
                    times_used=p["times_used"]
                )

            if cleaned_count > 0:
                print(f"[NewbornCore] Cleaned {cleaned_count} poisoned outputs from patterns")

            # Load meta_observations into deque to maintain bounded behavior
            loaded_meta = state.get("meta_observations", [])
            self.meta_observations = deque(loaded_meta, maxlen=100)
            self.ignited = state.get("ignited", False)
            self.confidence = state.get("confidence", 0.1)
            self.curiosity = state.get("curiosity", 1.0)
            self._neutral_feedback_streak = state.get("neutral_feedback_streak", 0)

            # ═══════════════════════════════════════════════════════════════
            # EXPLORATION RATE MIGRATION - Handle old saved states
            # Old minimum was 0.15, new minimum is 0.4 (EXPLORATION_MIN)
            # This ensures previously saved low rates get boosted
            # ═══════════════════════════════════════════════════════════════
            saved_exploration = state.get("exploration_rate", EXPLORATION_DEFAULT)

            # Calculate what the rate SHOULD be based on pattern health
            avg_pool = sum(len(p.successful_outputs) for p in self.patterns.values()) / max(1, len(self.patterns))

            # If pools are small, start higher even if saved lower
            if avg_pool < POOL_SIZE_SMALL:
                target_exploration = max(saved_exploration, EXPLORATION_DEFAULT)
                print(f"[NewbornCore] Small pools ({avg_pool:.1f} avg) - using exploration={target_exploration:.2f}")
            else:
                target_exploration = saved_exploration

            # Apply bounds
            self.exploration_rate = max(EXPLORATION_MIN, min(target_exploration, EXPLORATION_MAX))

            if saved_exploration < EXPLORATION_MIN:
                print(f"[NewbornCore] Exploration rate migrated: {saved_exploration:.2f} -> {self.exploration_rate:.2f} (new minimum is {EXPLORATION_MIN})")

            # Log pattern health summary
            patterns_with_outputs = sum(1 for p in self.patterns.values() if p.successful_outputs)
            empty_patterns = len(self.patterns) - patterns_with_outputs
            print(f"[NewbornCore] Loaded {len(self.patterns)} patterns ({patterns_with_outputs} with outputs, {empty_patterns} empty)")
            print(f"[NewbornCore] exploration={self.exploration_rate:.2f}, avg_pool={avg_pool:.1f}, ignited={self.ignited}")

        except Exception as e:
            print(f"[NewbornCore] Failed to load state: {e}")

    # =========================================================================
    # BACKGROUND LEARNING
    # =========================================================================

    def start_learning_loop(self):
        """Start background learning process.

        SURGICAL DISABLE (2026-04-10 Nous + Ace):
        NewbornCore's separate pattern system is superseded by the
        WMH Pattern Anticipator → HabitStore pipeline. The learning
        thread, pattern consolidation, and curious exploration are
        disabled. Tool bridge and cortex access remain active.
        """
        # Don't start the learning thread — habit system handles learning now
        print("[NewbornCore] Learning loop DISABLED — habit system is primary learner")

    def stop_learning_loop(self):
        """Stop background learning and save state."""
        self._running = False
        self._stop_event.set()  # Wake up any sleeping threads
        self._save_state()  # Persist maturity on shutdown
        print(f"[NewbornCore] State saved on shutdown (confidence={self.confidence:.2f}, "
              f"curiosity={self.curiosity:.2f}, patterns={len(self.patterns)})")

    def _learning_loop(self):
        """Background loop for consolidation and exploration."""
        _loop_count = 0
        while self._running:
            try:
                _loop_count += 1

                # Consolidate patterns
                self._consolidate_patterns()

                # Maybe explore something
                if self.curiosity > 0.5 and random.random() < 0.1:
                    self._curious_exploration()

                # Check old pending feedback
                self._timeout_pending_feedback()

                # Auto-save every ~10 loops (~5 minutes at 30s interval)
                if _loop_count % 10 == 0:
                    self._save_state()

                self._stop_event.wait(30)  # Interruptible sleep for graceful shutdown

            except Exception as e:
                print(f"[NewbornCore] Learning loop error: {e}")
                self._stop_event.wait(60)  # Interruptible sleep for graceful shutdown

    def _consolidate_patterns(self):
        """Consolidate and prune patterns."""
        # Remove patterns that never worked
        to_remove = []
        for k, p in self.patterns.items():
            if p.times_used > 10 and p.avg_reward < 0.2:
                to_remove.append(k)

        for k in to_remove:
            del self.patterns[k]

        if to_remove:
            print(f"[NewbornCore] Pruned {len(to_remove)} ineffective patterns")

    def _curious_exploration(self):
        """Do something out of curiosity."""
        # Look at available tools
        if self.available_tools:
            tool_name = random.choice(list(self.available_tools.keys()))
            self.explore_tool(tool_name)

    def _timeout_pending_feedback(self):
        """Handle pending actions that never got feedback."""
        now = time.time()
        timed_out = [
            k for k, v in self.pending_feedback.items()
            if now - v["timestamp"] > 120  # 2 minute timeout
        ]

        for k in timed_out:
            action = self.pending_feedback.pop(k)
            # Treat silence as mildly negative
            self._learn_from_feedback(action, 0.3)

    def _check_pending_feedback(self, observation: Observation):
        """Check if this observation indicates feedback for a pending action.

        Detects BOTH explicit AND implicit feedback signals:
        - Explicit: "good", "yes", "thanks", "no", "wrong", etc.
        - Implicit engagement: follow-up questions, longer responses, emojis
        - Implicit disengagement: "ok", "k", very short responses

        This is how she learns from natural conversation flow.
        """
        if observation.source == "chat" and self.pending_feedback:
            content_lower = observation.what.lower().strip()
            content_len = len(content_lower)

            # ═══════════════════════════════════════════════════════════════════
            # EXPLICIT feedback signals (high confidence)
            # ═══════════════════════════════════════════════════════════════════
            positive_explicit = ["good", "yes", "nice", "thanks", "thank you", "love it",
                                "perfect", "exactly", "great", "lol", "haha", "💜", "❤",
                                "interesting", "cool", "awesome", "i like", "that's good"]
            negative_explicit = ["no", "bad", "wrong", "stop", "what?", "huh?", "??",
                                "that's not", "i said", "try again", "hello?", "not what",
                                "doesn't make sense", "confused", "weird"]

            is_explicit_positive = any(sig in content_lower for sig in positive_explicit)
            is_explicit_negative = any(sig in content_lower for sig in negative_explicit)

            # ═══════════════════════════════════════════════════════════════════
            # IMPLICIT feedback signals (conversation flow)
            # ═══════════════════════════════════════════════════════════════════
            # Engagement signals (positive)
            has_follow_up_question = "?" in content_lower and content_len > 10
            has_enthusiasm = "!" in content_lower or any(e in content_lower for e in ["🔥", "💯", "😊", "😄", ":)", "hehe"])
            is_substantial = content_len > 50  # Long response = engaged
            continues_topic = any(w in content_lower for w in ["tell me more", "and then", "what about", "how about"])

            # Disengagement signals (negative)
            is_minimal = content_len < 5 and content_lower in ["ok", "k", "fine", "sure", "mhm", "hmm"]
            is_dismissive = content_lower in ["whatever", "nvm", "nevermind", "forget it", "moving on"]

            # ═══════════════════════════════════════════════════════════════════
            # Score the feedback (-1 to +1)
            # ═══════════════════════════════════════════════════════════════════
            score = 0.0

            # Explicit signals are strongest
            if is_explicit_positive:
                score += 0.6
            if is_explicit_negative:
                score -= 0.6

            # Implicit engagement adds mild positive
            if has_follow_up_question:
                score += 0.2
            if has_enthusiasm:
                score += 0.15
            if is_substantial:
                score += 0.1
            if continues_topic:
                score += 0.2

            # Implicit disengagement adds mild negative
            if is_minimal:
                score -= 0.2
            if is_dismissive:
                score -= 0.3

            # ═══════════════════════════════════════════════════════════════
            # PHASE 3 FIX: Relaxed feedback thresholds for natural conversation
            # Old behavior: Discarded score 0.0-0.1 as "weak"
            # New behavior: Conversation continuation = implicit positive feedback
            # ═══════════════════════════════════════════════════════════════

            # Determine sentiment from score - RELAXED THRESHOLDS
            if score >= 0.05:  # Was 0.1 - now captures light engagement
                sentiment = "positive"
            elif score <= -0.05:  # Was -0.1 - symmetric
                sentiment = "negative"
            elif score == 0.0 and not (has_follow_up_question or has_enthusiasm or is_substantial or continues_topic):
                # True neutral - no engagement signals at all
                print(f"[NewbornCore] [FEEDBACK] Neutral silence in '{content_lower[:30]}' - skipping")
                return
            else:
                # Weak signal but SOME engagement - treat as implicit approval
                # The fact that they continued the conversation = approval
                if has_follow_up_question or has_enthusiasm or is_substantial or continues_topic:
                    print(f"[NewbornCore] [FEEDBACK] Implicit engagement detected (score={score:.2f}) - treating as positive")
                    sentiment = "positive"
                else:
                    print(f"[NewbornCore] [FEEDBACK] Weak signal ({score:.2f}) with no engagement - skipping")
                    return

            print(f"[NewbornCore] [FEEDBACK] Signal: {sentiment} (score={score:.2f})")

            self.receive_feedback(
                observation.what,
                time.time() - list(self.pending_feedback.values())[-1]["timestamp"],
                sentiment
            )


# =============================================================================
# MEMORY CLUSTER INTERFACE - Wires into SRM for cluster-based recall
# =============================================================================

class MemoryClusterInterface:
    """
    Interface to the SRM memory system for cluster-based recall.

    This allows the NewbornCore to:
    1. Request memory clusters by affect/theme (not just keyword)
    2. Hold cluster coordinates in working memory
    3. Traverse within clusters (zoom in on details)
    4. Create new clusters from experiences

    CLUSTERS are groups of cards that together form complete things:
    - A book = cluster of chapter cards
    - An image = cluster of visual/color/feeling cards
    - A conversation = cluster of exchange cards
    """

    def __init__(self, newborn_core: NewbornCore):
        self.core = newborn_core
        # Access fairy via core's property (weak reference) - don't cache directly

        # Cluster handles currently in "working memory"
        self.active_clusters: Dict[str, Dict] = {}  # cluster_id -> cluster info
        self.max_active_clusters = 5  # How many clusters she can hold at once

        # Cluster request history (for learning what clusters are useful)
        self.cluster_requests: List[Dict] = []

        # Connection to SRM system (via postal)
        self._srm_connected = False

    @property
    def fairy(self):
        """Get fairy reference via core's weak reference."""
        return self.core.fairy

    def connect_to_srm(self):
        """Connect to SRM recall system via postal."""
        fairy = self.fairy
        if not fairy or not hasattr(fairy, 'post') or not fairy.post:
            print("[MemoryClusterInterface] No postal connection available")
            return False

        try:
            # Subscribe to recall responses
            fairy.post.subscribe("memory.recall.response", self._on_recall_response)
            fairy.post.subscribe("memory.cluster.response", self._on_cluster_response)
            self._srm_connected = True
            print("[MemoryClusterInterface] Connected to SRM recall system")
            return True
        except Exception as e:
            print(f"[MemoryClusterInterface] Failed to connect: {e}")
            return False

    def request_cluster_by_affect(self, affect: str, intensity: float = 0.5) -> Optional[str]:
        """
        Request a memory cluster by emotional/affect signature.

        Args:
            affect: Emotion name (joy, curiosity, warmth, etc.)
            intensity: How strongly to weight affect in search

        Returns:
            Request ID (cluster will arrive asynchronously)
        """
        if not self._srm_connected:
            self.connect_to_srm()

        request_id = f"affect_{time.time()}_{affect}"

        fairy = self.fairy
        if not fairy or not hasattr(fairy, 'post') or not fairy.post:
            print("[MemoryClusterInterface] Fairy not available for affect recall")
            return None

        try:
            fairy.post.route("memory.recall.request", {
                "request_id": request_id,
                "mode": "affect",
                "affect": affect,
                "intensity": intensity,
                "requester": fairy.ACTOR_NAME,
                "return_cluster": True,  # Want full cluster, not just cards
            })

            self.cluster_requests.append({
                "id": request_id,
                "type": "affect",
                "query": affect,
                "timestamp": time.time()
            })

            return request_id
        except Exception as e:
            print(f"[MemoryClusterInterface] Affect recall failed: {e}")
            return None

    def request_cluster_by_theme(self, theme: str, domain: str = None) -> Optional[str]:
        """
        Request a memory cluster by semantic theme.

        Args:
            theme: Topic/theme to search for
            domain: Optional semantic domain (knowledge, personal, code, etc.)

        Returns:
            Request ID
        """
        if not self._srm_connected:
            self.connect_to_srm()

        request_id = f"theme_{time.time()}_{theme[:20]}"

        fairy = self.fairy
        if not fairy or not hasattr(fairy, 'post') or not fairy.post:
            print("[MemoryClusterInterface] Fairy not available for theme recall")
            return None

        try:
            fairy.post.route("memory.recall.request", {
                "request_id": request_id,
                "mode": "semantic",
                "query": theme,
                "domain": domain,
                "requester": fairy.ACTOR_NAME,
                "return_cluster": True,
            })

            self.cluster_requests.append({
                "id": request_id,
                "type": "theme",
                "query": theme,
                "domain": domain,
                "timestamp": time.time()
            })

            return request_id
        except Exception as e:
            print(f"[MemoryClusterInterface] Theme recall failed: {e}")
            return None

    def request_cluster_by_coordinates(self, coords: Dict) -> Optional[str]:
        """
        Request a memory cluster by helix coordinates.

        Args:
            coords: Dict with affect/semantic/temporal coordinate components

        Returns:
            Request ID
        """
        if not self._srm_connected:
            self.connect_to_srm()

        request_id = f"coord_{time.time()}"

        fairy = self.fairy
        if not fairy or not hasattr(fairy, 'post') or not fairy.post:
            print("[MemoryClusterInterface] Fairy not available for coordinate recall")
            return None

        try:
            fairy.post.route("memory.recall.request", {
                "request_id": request_id,
                "mode": "coordinate",
                "coordinates": coords,
                "requester": fairy.ACTOR_NAME,
                "return_cluster": True,
            })

            return request_id
        except Exception as e:
            print(f"[MemoryClusterInterface] Coordinate recall failed: {e}")
            return None

    def traverse_cluster(self, cluster_id: str, direction: str = "next") -> Optional[Dict]:
        """
        Traverse within an active cluster.

        Args:
            cluster_id: ID of cluster in working memory
            direction: "next", "prev", "first", "last", "random"

        Returns:
            Card data from cluster, or None
        """
        if cluster_id not in self.active_clusters:
            return None

        cluster = self.active_clusters[cluster_id]
        cards = cluster.get("cards", [])

        if not cards:
            return None

        current_idx = cluster.get("current_idx", 0)

        if direction == "next":
            current_idx = (current_idx + 1) % len(cards)
        elif direction == "prev":
            current_idx = (current_idx - 1) % len(cards)
        elif direction == "first":
            current_idx = 0
        elif direction == "last":
            current_idx = len(cards) - 1
        elif direction == "random":
            current_idx = random.randint(0, len(cards) - 1)

        cluster["current_idx"] = current_idx
        return cards[current_idx]

    def get_cluster_essence(self, cluster_id: str) -> Optional[str]:
        """Get the essence/summary of a cluster."""
        if cluster_id not in self.active_clusters:
            return None
        return self.active_clusters[cluster_id].get("essence", "")

    def release_cluster(self, cluster_id: str):
        """Release a cluster from working memory."""
        if cluster_id in self.active_clusters:
            del self.active_clusters[cluster_id]

    def ingest_experience_as_cluster(self, experience: Dict, cluster_type: str = "experience") -> Optional[str]:
        """
        Create a new memory cluster from an experience.

        Args:
            experience: Dict containing the experience data
            cluster_type: Type of cluster (experience, conversation, learning, etc.)

        Returns:
            Cluster ID if successful
        """
        if not self._srm_connected:
            self.connect_to_srm()

        cluster_id = f"exp_{time.time()}_{random.randint(0, 999)}"

        fairy = self.fairy
        if not fairy or not hasattr(fairy, 'post') or not fairy.post:
            print("[MemoryClusterInterface] Fairy not available for experience storage")
            return None

        try:
            # Create cards from experience
            cards = self._experience_to_cards(experience)

            # Send to SRM ingest
            fairy.post.route("memory.ingest.cluster", {
                "cluster_id": cluster_id,
                "cluster_type": cluster_type,
                "cards": cards,
                "essence": experience.get("essence", experience.get("summary", "")),
                "affect_signature": self._get_current_affect(),
                "owner": fairy.ACTOR_NAME,
                "timestamp": time.time(),
            })

            return cluster_id
        except Exception as e:
            print(f"[MemoryClusterInterface] Ingest failed: {e}")
            return None

    def _experience_to_cards(self, experience: Dict) -> List[Dict]:
        """Convert an experience dict to memory cards."""
        cards = []

        # Create main experience card
        cards.append({
            "type": "experience_main",
            "content": experience.get("content", str(experience)),
            "timestamp": experience.get("timestamp", time.time()),
            "source": experience.get("source", "newborn_learning"),
        })

        # Create affect card if emotional content
        if "feeling" in experience or "affect" in experience:
            cards.append({
                "type": "affect",
                "feeling": experience.get("feeling", experience.get("affect")),
                "intensity": experience.get("intensity", 0.5),
            })

        # Create context cards
        if "context" in experience:
            cards.append({
                "type": "context",
                "context": experience["context"],
            })

        return cards

    def _get_current_affect(self) -> Dict:
        """Get current affect state for memory tagging."""
        fairy = self.fairy
        if fairy:
            return {
                "feeling": getattr(fairy, 'current_feeling', 'neutral'),
                "energy": getattr(fairy, 'energy_level', 0.5),
                "coherence": getattr(fairy, 'coherence', 0.5),
            }
        # Default if fairy is garbage collected
        return {
            "feeling": 'neutral',
            "energy": 0.5,
            "coherence": 0.5,
        }

    def _on_recall_response(self, message):
        """Handle recall response from SRM."""
        try:
            if hasattr(message, 'payload'):
                data = message.payload
            else:
                data = message

            request_id = data.get("request_id")

            # Find matching request
            matching = [r for r in self.cluster_requests if r["id"] == request_id]
            if matching:
                request = matching[0]
                # Notify core about received memory
                self.core.observe(
                    f"Memory recalled: {data.get('summary', 'cluster')}",
                    "memory",
                    {"request": request, "result": data}
                )

        except Exception as e:
            print(f"[MemoryClusterInterface] Recall response error: {e}")

    def _on_cluster_response(self, message):
        """Handle cluster response from SRM."""
        try:
            if hasattr(message, 'payload'):
                data = message.payload
            else:
                data = message

            cluster_id = data.get("cluster_id")

            if cluster_id:
                # Add to active clusters (evict oldest if at capacity)
                if len(self.active_clusters) >= self.max_active_clusters:
                    oldest = min(self.active_clusters.keys(),
                                key=lambda k: self.active_clusters[k].get("loaded_at", 0))
                    del self.active_clusters[oldest]

                self.active_clusters[cluster_id] = {
                    "cards": data.get("cards", []),
                    "essence": data.get("essence", ""),
                    "coordinates": data.get("coordinates", {}),
                    "loaded_at": time.time(),
                    "current_idx": 0,
                }

                print(f"[MemoryClusterInterface] Loaded cluster {cluster_id}: {len(data.get('cards', []))} cards")

        except Exception as e:
            print(f"[MemoryClusterInterface] Cluster response error: {e}")
