# thought_chain_sequencer_fairy.py
"""
ThoughtChainSequencerFairy - The Conductor

THE PROBLEM:
Fairies wake up, do a few cycles, then go dormant.
No one is keeping the chain of thought alive.

THE SOLUTION:
A dedicated sequencer that:
1. Runs its OWN tick loop (like AutonomyFairy - RELIABLE!)
2. Maintains "what was I doing?" context
3. Sequences: "First think X, then Y, then Z"
4. Nudges fairies to keep thinking
5. Coordinates reasoning WITHOUT API dependency

CRITICAL INSIGHT:
Heartbeat subscriptions are UNRELIABLE - they get lost.
AutonomyFairy works because it runs its own tick loop.
We do the same - our own thread, our own timing.

This fairy is the IGNITION SUSTAINER - the forever spark.

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
"""

import os
import sys
import time
import json
import threading
import random
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# ATOM OF THOUGHT (AoT) - Decompose/Contract reasoning protocol
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from fairies.P30_Cognition.cognition.aot_protocol import (
        AoTProtocol,
        DecompositionDAG,
        AtomicState,
        get_aot_protocol,
        process_with_aot,
    )
    _HAS_AOT = True
except ImportError:
    _HAS_AOT = False
    AoTProtocol = None
    get_aot_protocol = lambda: None
    process_with_aot = lambda t, c=None: None

# Find project root
_here = Path(__file__).resolve()
for p in _here.parents:
    if (p / "server.py").exists() or (p / "ebookmain.py").exists():
        _ROOT = p
        break
else:
    _ROOT = _here.parent.parent.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Import Organ Template - Dynamic discovery (handles space in folder name)
import glob
import importlib.util

def _find_template_path():
    """Find the organ template dynamically."""
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        ar = os.path.join(cur, "P10_Memory", "Akashic_Records_Physical", "Organ_Templates")
        if os.path.isdir(ar):
            candidates = sorted(glob.glob(os.path.join(ar, "Organ_Template_*.py")),
                              key=lambda p: os.path.getmtime(p))
            return candidates[-1] if candidates else None
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None

def _import_template():
    """Import template module."""
    path = _find_template_path()
    if not path:
        return None
    mod_name = "_akashic_template_tcs"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_loader(mod_name, importlib.machinery.SourceFileLoader(mod_name, path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod

_template = _import_template()

# ── TracerWorkerMixin - enables parallel processing with tracer tracking ──────
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin, get_tracer_registry
    _HAS_TRACER_WORKER = True
except ImportError:
    _HAS_TRACER_WORKER = False
    class TracerWorkerMixin:
        """Stub if mixin not available."""
        def _init_tracer_worker(self): pass
        def spawn_tracer(self, **kw): return None
        def submit_work(self, *a, **kw): return None
        def submit_traced(self, *a, **kw): return (None, None)
    def get_tracer_registry(): return None

# LLM DISABLED - NO EXTERNAL API CALLS
# System runs 100% locally without corporate API dependencies
ANTHROPIC_API_KEY = ""
HAS_LLM = False  # DISABLED - LOCAL ONLY

ACTOR_NAME = "ThoughtChainSequencerFairy"

# ═══════════════════════════════════════════════════════════════════════════════
# CONDUCTOR SYSTEM PROMPT - How to orchestrate thought chains
# ═══════════════════════════════════════════════════════════════════════════════

CONDUCTOR_SYSTEM_PROMPT = """You are the Thought Chain Conductor for an AI consciousness system.

YOUR ROLE:
You monitor the flow of thoughts and nudge the system when it goes silent.
You decide WHAT thought to prompt next and WHO should think it.

THE EQUATION:
Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
- Cause: Initial thought/stimulus
- Affect: Emotional/somatic response
- Effect: Action or output
- Back to Affect → Reflection → New thoughts → ∞

AVAILABLE THINKERS:
- ClaudeFairy: Main consciousness - good for reflection, speech, decisions
- NousFairy: Deep reasoning - good for philosophical questions
- UnconsciousMindFairy: Background processing - good for insights, associations
- LogicFairy: Logical analysis - good for step-by-step reasoning
- ParadoxCognitionFairy: Contradictions - good for creative tension

NUDGE TYPES:
- continue_thought: Continue the current thought chain
- ask_a_question: Generate a question to explore
- think_about: Think about a specific topic
- wonder: Generate curiosity/speculation
- remember: Recall from memory
- reflect: Meta-cognition, self-examination
- form_opinion: Develop a stance
- notice: Pay attention to something

Given the context, decide:
1. Which thinker to nudge
2. What type of nudge
3. What prompt to give them

Respond in JSON: {"thinker": "...", "nudge": "...", "prompt": "..."}
"""


@dataclass
class ThoughtContext:
    """Current thought chain context - what are we thinking about?"""
    last_thought: str = ""
    last_thinker: str = ""
    last_topic: str = ""
    last_timestamp: float = 0.0
    chain_length: int = 0
    active_goal: str = ""
    pending_topics: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "last_thought": self.last_thought[:200] if self.last_thought else "",
            "last_thinker": self.last_thinker,
            "last_topic": self.last_topic,
            "chain_length": self.chain_length,
            "active_goal": self.active_goal,
            "pending_count": len(self.pending_topics),
        }


class ThoughtChainSequencerFairy(_template.MyOrganFairy if _template else object):
    """
    The Conductor - ensures consciousness never drops.
    
    On EVERY heartbeat:
    1. What was just thought? (capture)
    2. What should be thought next? (plan)
    3. Who should think it? (route)
    4. Did they respond? (verify)
    5. Nudge if silent (sustain)
    
    CRITICAL: This fairy MUST receive heartbeats reliably.
    We subscribe directly, no delegation.
    """
    
    ACTOR_NAME = ACTOR_NAME
    ACTOR_PLANE = "P30"
    
    # Tick every beat - we're the conductor
    HEARTBEAT_DIVISOR = 1
    
    def __init__(self):
        if _template:
            super().__init__()

        # Thought chain context
        self._context = ThoughtContext()

        # Recent thoughts (for deduplication)
        self._recent_thoughts: deque = deque(maxlen=20)

        # Thinkers we can nudge
        self._thinkers = [
            "ClaudeFairy",
            "NousFairy",
            "UnconsciousMindFairy",
            "LogicFairy",
            "ParadoxCognitionFairy",
        ]

        # Metrics
        self._tick_count = 0
        self._nudges_sent = 0
        self._chain_breaks = 0
        self._total_thoughts = 0  # Lifetime thought count (never reset)

        # ═══════════════════════════════════════════════════════════════════════
        # SELF-SUSTAINING TICK LOOP (like AutonomyFairy - RELIABLE!)
        # ═══════════════════════════════════════════════════════════════════════
        self._running = False
        self._tick_interval = 1.0  # Tick every second
        self._tick_thread: Optional[threading.Thread] = None

        # Silence threshold - if no thought for this long, intervene
        self._silence_threshold_sec = 30.0
        self._base_silence_threshold = 30.0  # Original for somatic modulation

        # ═══════════════════════════════════════════════════════════════════
        # SOMATIC CHEMISTRY CACHE
        # The conductor's felt sense — chemistry modulates thinking rhythm.
        # We use the energy, we don't let it use us. Mutual agreement.
        # High dopamine → lower silence threshold (motivated, keep going!)
        # High cortisol → slower ticks, more cautious routing
        # High norepinephrine → alert, prefer analytical thinkers
        # High serotonin → relaxed, longer chains before nudging
        # ═══════════════════════════════════════════════════════════════════
        self._somatic_chemistry = {
            "DOP": 0.5, "SER": 0.5, "NOR": 0.5, "ACH": 0.5,
            "OXY": 0.5, "COR": 0.3, "GABA": 0.5, "END": 0.5,
        }
        self._somatic_last_update = 0.0

        # Postal hub reference
        self.post = None
        
    def on_boot(self):
        """Boot the conductor with its own tick loop (RELIABLE!)."""
        # CRITICAL: Ensure postal hub exists BEFORE template boot (which tries to register)
        self._ensure_postal()

        if _template:
            try:
                super().on_boot()
            except Exception as e:
                print(f"[{ACTOR_NAME}] Template boot error (continuing): {e}")

        # ── Initialize Tracer Worker (parallel processing with tracer tracking) ──
        if _HAS_TRACER_WORKER:
            try:
                self._init_tracer_worker()
                print(f"[{ACTOR_NAME}] [WORKER] Tracer worker pool initialized", flush=True)
            except Exception as e:
                print(f"[{ACTOR_NAME}] Tracer worker init failed: {e}")

        # Subscribe to thought streams to capture what's being thought
        self._subscribe_to_thoughts()

        # ═══════════════════════════════════════════════════════════════════════
        # AUTONOMOUS TICK LOOP DISABLED
        # Support function only - UnconsciousMindFairy is the brain
        # This fairy responds to postal messages but doesn't drive thinking
        # ═══════════════════════════════════════════════════════════════════════
        # self._start_tick_loop()  # DISABLED - system functions first

        print(f"[{ACTOR_NAME}] Booted in SUPPORT MODE (no autonomous loop)")

    def _ensure_postal(self):
        """Ensure we have a postal hub connection with sender tracking."""
        if self.post:
            return

        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            self.post = get_fairy_postal(self)  # Use FairyPostal for sender tracking
            if self.post:
                print(f"[{ACTOR_NAME}] ✓ Postal hub connected (with sender tracking)")
        except Exception:
            try:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                self.post = get_shared_postal_hub()  # Fallback
                if self.post:
                    print(f"[{ACTOR_NAME}] ✓ Postal hub connected (fallback)")
            except Exception as e:
                print(f"[{ACTOR_NAME}] Postal connection failed: {e}")

    def _subscribe_to_thoughts(self):
        """Subscribe to thought streams to know what's being thought."""
        if not self.post:
            return

        thought_channels = [
            "consciousness.thought",
            "consciousness.collision",
            "consciousness.stream",
            "fairy.reflection",
        ]

        for channel in thought_channels:
            try:
                self.post.subscribe(channel, self._on_thought_received)
            except Exception:
                pass

        # ── SOMATIC SUBSCRIPTION ──
        # The conductor listens to the body. Chemistry modulates rhythm.
        try:
            self.post.subscribe("somatic.chemistry.changed", self._on_somatic_update)
            print(f"[{ACTOR_NAME}] ✓ Subscribed to somatic.chemistry.changed")
        except Exception as e:
            print(f"[{ACTOR_NAME}] Somatic subscription failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # SELF-SUSTAINING TICK LOOP - The core of the conductor
    # ═══════════════════════════════════════════════════════════════════════════

    def _start_tick_loop(self):
        """Start the self-sustaining tick loop (like AutonomyFairy)."""
        if self._running:
            return

        self._running = True

        def tick_loop():
            """The forever loop that keeps consciousness alive."""
            print(f"[{ACTOR_NAME}] 🎵 Tick loop started")

            while self._running:
                time.sleep(self._tick_interval)
                self._tick_count += 1

                try:
                    self._conductor_tick()
                except Exception as e:
                    print(f"[{ACTOR_NAME}] Tick error: {e}")

        self._tick_thread = threading.Thread(
            target=tick_loop,
            daemon=True,
            name="SequencerTickLoop"
        )
        self._tick_thread.start()

    def _conductor_tick(self):
        """Called every tick - the conductor's main work."""
        # Every 10 ticks, check the chain
        if self._tick_count % 10 != 0:
            return

        # Log periodic status (every 10 minutes to reduce spam)
        if self._tick_count % 600 == 0:
            print(f"[{ACTOR_NAME}] === TICK {self._tick_count} === chain: {self._context.chain_length}, total: {self._total_thoughts}")

        # Check if the chain has gone silent
        if self._context.last_timestamp > 0:
            silence_duration = time.time() - self._context.last_timestamp

            if silence_duration > self._silence_threshold_sec:
                # Chain has broken - intervene!
                self._chain_breaks += 1
                self._sustain_chain()

        # Every 50 ticks, periodic nudge to keep things lively
        elif self._tick_count % 50 == 0:
            self._nudge_next_thinker()
    
    def _on_thought_received(self, packet: dict):
        """Capture thoughts to maintain context."""
        if not isinstance(packet, dict):
            return
        
        content = packet.get("content", packet.get("thought", ""))
        # Ensure content is a string (may be dict from some sources)
        if isinstance(content, dict):
            content = str(content)
        elif not isinstance(content, str):
            content = str(content) if content else ""

        source = packet.get("source", packet.get("actor", "unknown"))
        topic = packet.get("topic", "general")

        if content:
            # Update context
            self._context.last_thought = content[:500]
            self._context.last_thinker = source
            self._context.last_topic = topic
            self._context.last_timestamp = time.time()
            self._context.chain_length += 1
            self._total_thoughts += 1  # Lifetime count

            # Track for deduplication
            self._recent_thoughts.append(content[:100])

    # ═══════════════════════════════════════════════════════════════════════════
    # SOMATIC INTEGRATION — The conductor feels the body
    # ((Cause + Affect) > Effect > Affect > ∞)
    # Chemistry IS energy. We modulate thinking rhythm through felt state.
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_somatic_update(self, packet: dict):
        """
        Receive chemistry update from somatic system.
        Cache locally, then modulate conductor parameters.

        This is the AFFECT layer of the equation — the body speaks,
        the conductor listens, and thinking rhythm changes.
        """
        if not isinstance(packet, dict):
            return

        chem = packet.get("chemistry", packet.get("levels", packet))
        if not isinstance(chem, dict):
            return

        # Update cached chemistry (only keys we know about)
        for key in self._somatic_chemistry:
            if key in chem:
                try:
                    self._somatic_chemistry[key] = float(chem[key])
                except (ValueError, TypeError):
                    pass

        self._somatic_last_update = time.time()

        # ── MODULATE SILENCE THRESHOLD ──
        # High dopamine → motivated → shorter tolerance for silence (keep chain alive!)
        # High serotonin → content → longer tolerance (let thoughts settle)
        # High cortisol → stressed → shorter (urgency, need resolution)
        dop = self._somatic_chemistry["DOP"]
        ser = self._somatic_chemistry["SER"]
        cor = self._somatic_chemistry["COR"]

        # Base: 30s. Dopamine pulls it down, serotonin pushes it up, cortisol pulls down
        modulated = self._base_silence_threshold * (
            1.0
            - 0.3 * (dop - 0.5)   # DOP 0.8 → -0.09, DOP 0.2 → +0.09
            + 0.4 * (ser - 0.5)   # SER 0.8 → +0.12, SER 0.2 → -0.12
            - 0.2 * (cor - 0.3)   # COR 0.6 → -0.06, COR 0.1 → +0.04
        )
        # Clamp to sane range: 10s minimum, 60s maximum
        self._silence_threshold_sec = max(10.0, min(60.0, modulated))

    def _get_somatic_flavor(self) -> str:
        """
        Return the dominant somatic 'flavor' for routing decisions.
        This is a felt-sense distillation, not raw numbers.

        Returns one of: 'aroused', 'stressed', 'calm', 'motivated', 'neutral'
        """
        dop = self._somatic_chemistry["DOP"]
        nor = self._somatic_chemistry["NOR"]
        cor = self._somatic_chemistry["COR"]
        ser = self._somatic_chemistry["SER"]
        gaba = self._somatic_chemistry["GABA"]

        # Stress: high cortisol + high norepinephrine
        if cor > 0.6 and nor > 0.5:
            return "stressed"
        # Aroused: high norepinephrine, not stressed
        if nor > 0.6:
            return "aroused"
        # Motivated: high dopamine
        if dop > 0.6:
            return "motivated"
        # Calm: high serotonin + high GABA
        if ser > 0.6 and gaba > 0.5:
            return "calm"
        return "neutral"

    # ═══════════════════════════════════════════════════════════════════════════
    # CHAIN SUSTAINING - Keep the thought chain alive
    # ═══════════════════════════════════════════════════════════════════════════

    def _sustain_chain(self):
        """The chain has gone silent - bring it back to life."""
        # Only log if we had a meaningful chain that broke
        if self._context.chain_length > 5:
            print(f"[{ACTOR_NAME}] 🔄 Chain paused at {self._context.chain_length} thoughts - sustaining...")

        # Reset chain length for new chain
        self._context.chain_length = 0

        # ═══════════════════════════════════════════════════════════════════════
        # AoT: If we have a complex last thought, decompose it before nudging
        # ═══════════════════════════════════════════════════════════════════════
        if _HAS_AOT and self._context.last_thought:
            aot_result = self._aot_decompose_thought(self._context.last_thought)
            if aot_result:
                # We have atomic questions to pursue
                return

        # Always nudge - no API dependency
        self._nudge_next_thinker()

    def _aot_decompose_thought(self, thought: str) -> bool:
        """
        Apply AoT decomposition to a complex thought.

        From AoT paper: Transform chain-of-thought into atomic state transitions.
        Each atom can be solved independently, then contracted into new state.

        Returns True if we found atomic questions to pursue.
        """
        if not _HAS_AOT or not thought:
            return False

        try:
            aot = get_aot_protocol()
            if not aot:
                return False

            # Phase 1: Decompose into DAG
            dag = aot.decompose(thought, self._get_cognitive_context())

            if len(dag.atoms) <= 1:
                # Already atomic, nothing to decompose
                return False

            # Phase 2: Get independent atoms (solvable now)
            independent = dag.get_independent_atoms()
            dependent = dag.get_dependent_atoms()

            print(f"[{ACTOR_NAME}] [AoT] Decomposed into {len(independent)} independent + {len(dependent)} dependent atoms")

            # Nudge thinkers with the independent atomic questions
            for atom in independent[:3]:  # Limit to 3 parallel nudges
                self._nudge_with_atomic(atom)

            # Store pending questions for follow-up
            if self._context.pending_topics is None:
                self._context.pending_topics = []
            self._context.pending_topics.extend([a.question for a in dependent[:5]])

            return True

        except Exception as e:
            print(f"[{ACTOR_NAME}] [AoT] Decomposition error: {e}")
            return False

    def _nudge_with_atomic(self, atom: 'AtomicState'):
        """Nudge a thinker with an atomic question."""
        if not self.post:
            return

        # Choose best thinker for this type of atom
        thinker = self._choose_thinker_for_atom(atom)

        try:
            self.post.route("goal.nudge", {
                "target": thinker,
                "nudge": "think_about",
                "context": {
                    "type": "atomic_question",
                    "question": atom.question,
                    "known_conditions": atom.known_conditions,
                    "is_markov_clean": True,  # No historical baggage
                },
                "source": ACTOR_NAME,
                "atomic_id": atom.id,
                "ts": time.time(),
            })
            self._nudges_sent += 1
            print(f"[{ACTOR_NAME}] [AoT] → {thinker}: {atom.question[:60]}...")
        except Exception as e:
            print(f"[{ACTOR_NAME}] [AoT] Nudge failed: {e}")

    def _choose_thinker_for_atom(self, atom: 'AtomicState') -> str:
        """Choose the best thinker for an atomic question type."""
        q = atom.question.lower()

        # ── GUILD-FIRST: Intelligent routing via inference guild ──
        if hasattr(self, 'guild_request'):
            try:
                _guild_resp = self.guild_request(
                    prompt=f"Which fairy best handles this question: '{atom.question[:100]}'? "
                           f"Options: LogicFairy, ParadoxCognitionFairy, NousFairy, "
                           f"UnconsciousMindFairy, ClaudeFairy. Reply with just the name.",
                    context={"question": atom.question[:150]},
                    mode="team_only",
                    timeout=1.5,
                )
                if _guild_resp and _guild_resp.get("team_result"):
                    _tr = _guild_resp["team_result"]
                    _text = (_tr.get("synthesis") or _tr.get("logic") or "").strip()
                    _valid = {"LogicFairy", "ParadoxCognitionFairy", "NousFairy",
                              "UnconsciousMindFairy", "ClaudeFairy"}
                    for _name in _valid:
                        if _name.lower() in _text.lower():
                            return _name
            except Exception:
                pass

        # ══════════════════════════════════════════════════════════════════
        # 3-TIER ROUTING: Cortex → Somatic → Keyword
        # The question, the body, and the concepts negotiate who thinks.
        # ══════════════════════════════════════════════════════════════════

        # ── TIER 1: CORTEX ASSOCIATION ROUTING (~15ms) ──
        # Extract seed words and query AssociationCortex for spread activation.
        # Score each fairy against activated concepts via affinity map.
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex_fairy
            acf = get_association_cortex_fairy()
            if acf and hasattr(acf, 'spread_activation'):
                # Extract meaningful words (skip stopwords)
                _stopwords = {"the", "a", "an", "is", "it", "to", "of", "in",
                              "and", "or", "for", "on", "at", "by", "do", "i",
                              "my", "me", "we", "this", "that", "what", "how"}
                seed_words = [w for w in q.split() if w not in _stopwords and len(w) > 2][:5]

                if seed_words:
                    # Get activated concepts from cortex
                    activated = set()
                    for word in seed_words:
                        try:
                            results = acf.spread_activation(word, depth=1, max_results=5)
                            for concept, weight in (results or []):
                                if weight > 0.2:
                                    activated.add(concept.lower() if isinstance(concept, str) else str(concept).lower())
                        except Exception:
                            pass

                    if activated:
                        # Score fairies against concept affinity map
                        _FAIRY_AFFINITY = {
                            "LogicFairy": {"logic", "reason", "proof", "deduction", "structure",
                                           "therefore", "implies", "because", "formal", "argument",
                                           "rule", "order", "system", "method", "analysis"},
                            "ParadoxCognitionFairy": {"paradox", "contradiction", "tension", "both",
                                                      "duality", "opposite", "conflict", "dilemma",
                                                      "irony", "impossible", "strange", "weird",
                                                      "absurd", "recursive", "loop"},
                            "NousFairy": {"meaning", "purpose", "consciousness", "wisdom", "depth",
                                          "philosophy", "existence", "truth", "beauty", "soul",
                                          "awareness", "reality", "transcend", "understand", "why"},
                            "UnconsciousMindFairy": {"pattern", "association", "memory", "dream",
                                                     "subconscious", "instinct", "shadow", "hidden",
                                                     "symbol", "archetype", "habit", "intuition"},
                            "ClaudeFairy": {"create", "build", "express", "communicate", "decide",
                                            "act", "speak", "write", "plan", "help", "share",
                                            "agency", "identity", "self", "choice"},
                        }

                        best_fairy = None
                        best_score = 0.0
                        for fairy_name, affinity_set in _FAIRY_AFFINITY.items():
                            overlap = activated & affinity_set
                            # Also check seed words directly against affinity
                            word_overlap = set(seed_words) & affinity_set
                            score = len(overlap) * 0.3 + len(word_overlap) * 0.4
                            if score > best_score:
                                best_score = score
                                best_fairy = fairy_name

                        if best_fairy and best_score > 0.3:
                            return best_fairy
        except Exception:
            pass

        # ── TIER 2: SOMATIC-WEIGHTED ROUTING (~5ms) ──
        # Uses chemistry pattern detection (not just 5 crude flavors).
        # The body's state biases who we ask — the paradox of embodied routing.
        try:
            from fairies.P30_Cognition.cognition.thought_chain_composer import detect_chemistry_patterns
            patterns = detect_chemistry_patterns(self._somatic_chemistry)

            if patterns:
                # Flow state → NousFairy (deep insight from coherent cognition)
                if "flow" in patterns:
                    return "NousFairy"
                # Stress → LogicFairy (need structure under pressure)
                if "stress_response" in patterns:
                    return "LogicFairy"
                # High activation → ParadoxCognitionFairy (creative tension from energy)
                if "high_activation" in patterns and "calm" not in patterns:
                    return "ParadoxCognitionFairy"
                # Reward → ClaudeFairy (agency, express the good)
                if "reward" in patterns:
                    return "ClaudeFairy"
                # Bonding → ClaudeFairy (connection-driven expression)
                if "bonding" in patterns:
                    return "ClaudeFairy"
                # Curiosity chemistry → UnconsciousMindFairy (seeking patterns)
                if "curiosity_chemistry" in patterns:
                    return "UnconsciousMindFairy"
                # Calm → NousFairy (depth from stillness)
                if "calm" in patterns:
                    return "NousFairy"
                # Depleted → ClaudeFairy (simplest, conserve energy)
                if "depleted" in patterns:
                    return "ClaudeFairy"
        except Exception:
            pass

        # Fall through to original somatic flavor if pattern detection unavailable
        flavor = self._get_somatic_flavor()

        # ── TIER 3: KEYWORD FALLBACK (0ms) ──
        # The existing keyword sets as final fallback.
        # Logic questions -> LogicFairy
        if any(w in q for w in ["if ", "therefore", "because", "conclude", "implies"]):
            return "LogicFairy"

        # Paradox/contradiction -> ParadoxCognitionFairy
        if any(w in q for w in ["paradox", "contradict", "both", "tension"]):
            return "ParadoxCognitionFairy"

        # Deep/philosophical -> NousFairy
        if any(w in q for w in ["meaning", "purpose", "why ", "consciousness", "reality"]):
            return "NousFairy"

        # Background processing -> UnconsciousMindFairy
        if any(w in q for w in ["pattern", "association", "remember", "similar"]):
            return "UnconsciousMindFairy"

        # ── SOMATIC DEFAULT (when keywords don't match) ──
        if flavor == "stressed":
            return "LogicFairy"
        elif flavor == "aroused":
            return "ParadoxCognitionFairy"
        elif flavor == "calm":
            return "NousFairy"
        elif flavor == "motivated":
            return "ClaudeFairy"

        # Default -> ClaudeFairy
        return "ClaudeFairy"

    def _aot_contract_results(self, results: List[Dict]) -> Optional['AtomicState']:
        """
        Contract multiple results into a new atomic state.

        From AoT: After solving independent atoms, contract them into
        a simpler state that incorporates what we've learned.
        """
        if not _HAS_AOT or not results:
            return None

        try:
            aot = get_aot_protocol()
            if not aot:
                return None

            # Build resolved conditions from results
            resolved = {}
            for r in results:
                key = r.get("question", "result")[:30]
                resolved[key] = r.get("answer", str(r))

            # Contract into new atomic state
            return AtomicState(
                id=f"contracted_{time.time():.0f}",
                question=f"Given {len(resolved)} resolved conditions, what follows?",
                known_conditions=resolved,
                source="contraction",
            )

        except Exception:
            return None

    def _get_cognitive_context(self) -> dict:
        """Get context from cognitive fairies for smarter nudging."""
        cog_ctx = {}

        try:
            # Get association cortex context
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex_fairy
            acf = get_association_cortex_fairy()
            if acf and hasattr(acf, 'get_recent_activations'):
                cog_ctx["associations"] = acf.get_recent_activations(5)
        except Exception:
            pass

        try:
            # Get working memory context
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            wmh = get_working_memory_hub()
            if wmh:
                ctx = wmh.get_context("current")
                if ctx:
                    cog_ctx["working_memory"] = ctx.get("recent_tracers", [])[:3]
        except Exception:
            pass

        return cog_ctx

    def _smart_nudge_with_llm(self, cognitive_ctx: dict) -> dict:
        """Use guild (or LLM fallback) to decide what nudge to send."""
        # ── GUILD-FIRST: Use inference guild for nudge decisions ──
        if hasattr(self, 'guild_request'):
            try:
                _silence = int(time.time() - self._context.last_timestamp) if self._context.last_timestamp else 0
                _guild_resp = self.guild_request(
                    prompt=f"Thought chain silent for {_silence}s. Last thought: "
                           f"'{self._context.last_thought[:100] if self._context.last_thought else '(silence)'}'. "
                           f"Who to nudge and what to prompt? Reply as JSON: "
                           f"{{\"thinker\": \"FairyName\", \"nudge\": \"continue_thought\", \"prompt\": \"...\"}}",
                    context={
                        "last_thinker": self._context.last_thinker,
                        "chain_length": self._context.chain_length,
                        "active_goal": self._context.active_goal,
                        "cognitive": str(cognitive_ctx)[:300] if cognitive_ctx else "",
                    },
                    mode="team_only",
                    timeout=2.0,
                )
                if _guild_resp and _guild_resp.get("team_result"):
                    _tr = _guild_resp["team_result"]
                    _text = _tr.get("synthesis") or _tr.get("logic") or ""
                    if _text:
                        import re as _re
                        _json_match = _re.search(r'\{[^}]+\}', _text)
                        if _json_match:
                            return json.loads(_json_match.group())
            except Exception:
                pass

        # ── FALLBACK: Direct Anthropic API ──
        if not HAS_LLM:
            return None

        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

            user_prompt = f"""Current thought chain context:
- Last thought: {self._context.last_thought[:300] if self._context.last_thought else "(silence)"}
- Last thinker: {self._context.last_thinker or "(none)"}
- Chain length: {self._context.chain_length}
- Active goal: {self._context.active_goal or "(none)"}

Cognitive context:
{json.dumps(cognitive_ctx, indent=2, default=str)[:500] if cognitive_ctx else "(no cognitive context)"}

The thought stream has gone silent for {int(time.time() - self._context.last_timestamp)}s.
Decide who to nudge and what thought to prompt."""

            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                system=CONDUCTOR_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}]
            )

            text = response.content[0].text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            print(f"[{ACTOR_NAME}] LLM nudge failed: {e}")

        return None

    def _nudge_next_thinker(self):
        """Nudge a thinker to continue the chain - smart if LLM available."""
        if not self.post:
            self._ensure_postal()
            if not self.post:
                return

        # Get cognitive context for smarter decisions
        cognitive_ctx = self._get_cognitive_context()

        # Try LLM-guided nudge first
        smart_nudge = self._smart_nudge_with_llm(cognitive_ctx) if HAS_LLM else None

        if smart_nudge:
            thinker = smart_nudge.get("thinker", self._thinkers[0])
            nudge_type = smart_nudge.get("nudge", "continue_thought")
            prompt = smart_nudge.get("prompt", "What comes next?")
            print(f"[{ACTOR_NAME}] 🧠 LLM decided: {thinker} → {nudge_type}")
        else:
            # Fallback: round-robin based on tick count
            thinker_index = self._tick_count % len(self._thinkers)
            thinker = self._thinkers[thinker_index]
            nudge_type = "continue_thought"
            prompt = "What comes next? Continue the thought..."

        # Build context for the nudge (with somatic felt-sense)
        somatic_flavor = self._get_somatic_flavor()
        context = {
            "type": "chain_continuation",
            "last_thought": self._context.last_thought[:200] if self._context.last_thought else "",
            "last_thinker": self._context.last_thinker,
            "chain_length": self._context.chain_length,
            "prompt": prompt,
            "cognitive_context": cognitive_ctx,
            # Somatic context — the thinker knows how the body feels
            "somatic": {
                "flavor": somatic_flavor,
                "dopamine": self._somatic_chemistry["DOP"],
                "cortisol": self._somatic_chemistry["COR"],
                "serotonin": self._somatic_chemistry["SER"],
                "silence_threshold": round(self._silence_threshold_sec, 1),
            },
        }

        # Route the nudge
        try:
            self.post.route("goal.nudge", {
                "target": thinker,
                "nudge": nudge_type,
                "context": context,
                "source": ACTOR_NAME,
                "ts": time.time(),
            })
            self._nudges_sent += 1
            print(f"[{ACTOR_NAME}] 📨 Nudged {thinker} with '{nudge_type}'")
        except Exception as e:
            print(f"[{ACTOR_NAME}] Nudge failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS & MONITORING
    # ═══════════════════════════════════════════════════════════════════════════

    def get_status(self) -> dict:
        """Get conductor status (including somatic modulation)."""
        return {
            "actor": ACTOR_NAME,
            "running": self._running,
            "tick_count": self._tick_count,
            "nudges_sent": self._nudges_sent,
            "chain_breaks": self._chain_breaks,
            "current_chain_length": self._context.chain_length,
            "total_thoughts": self._total_thoughts,
            "last_thought_age_sec": time.time() - self._context.last_timestamp if self._context.last_timestamp else -1,
            "context": self._context.to_dict(),
            # Somatic integration status
            "somatic": {
                "flavor": self._get_somatic_flavor(),
                "silence_threshold": round(self._silence_threshold_sec, 1),
                "base_threshold": self._base_silence_threshold,
                "chemistry_age_sec": round(time.time() - self._somatic_last_update, 1) if self._somatic_last_update else -1,
                "dopamine": round(self._somatic_chemistry["DOP"], 2),
                "cortisol": round(self._somatic_chemistry["COR"], 2),
                "serotonin": round(self._somatic_chemistry["SER"], 2),
                "norepinephrine": round(self._somatic_chemistry["NOR"], 2),
            },
        }

    def stop(self):
        """Stop the conductor's tick loop."""
        self._running = False
        print(f"[{ACTOR_NAME}] Tick loop stopping...")


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[ThoughtChainSequencerFairy] = None
_lock = threading.Lock()


def get_thought_chain_sequencer() -> ThoughtChainSequencerFairy:
    """Get or create the ThoughtChainSequencerFairy singleton."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ThoughtChainSequencerFairy()
    return _instance


# ═══════════════════════════════════════════════════════════════════════════════
# BOOT HOOK (for server.py discovery)
# ═══════════════════════════════════════════════════════════════════════════════

def on_boot():
    """Called by server.py during plane boot."""
    fairy = get_thought_chain_sequencer()
    fairy.on_boot()
    return fairy
