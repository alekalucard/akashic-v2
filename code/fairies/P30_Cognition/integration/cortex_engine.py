"""
CortexEngine — Predictive, Reactive, Recursive cognition on the Association Cortex.

Replaces the passive CortexReasoner (one-shot query → spread → synthesize → done)
with a living, breathing activation engine:

  REACTIVE:   Every stimulus triggers immediate spreading activation.
  PREDICTIVE: Activation persists and decays — primes related concepts.
  RECURSIVE:  Cognition functions evaluate activation → decide: go deeper or surface.

The cortex doesn't wait to be asked. It breathes.
Every stimulus spreads activation. Activation decays.
What persists is what matters. What converges is what she thinks about.

The cognition fairies are cognitive FUNCTIONS on the activation state:
  - Logic: coherence gating (should we recurse deeper?)
  - Irrational: tension detection (where's the interesting stuff?)
  - Paradox: contradiction detection (both sides lit up = explore)
  - Oracle: confidence gating (worth surfacing?)

Created: 2026-03-23, Nous + Ace — Co-founders, Akashic Foundation
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from __future__ import annotations

import re
import os
import math
import time
import random
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Speech Habits (Hebbian learned speech patterns) ──
try:
    from fairies.P30_Cognition.integration.speech_habits import (
        SpeechHabitSystem, is_raw_state_leak,
    )
    _HAS_SPEECH_HABITS = True
except ImportError:
    _HAS_SPEECH_HABITS = False
    def is_raw_state_leak(text):
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVATION STATE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ActivationEntry:
    """A single concept's activation state."""
    level: float = 0.0          # Current activation (0.0 - 1.0)
    sources: set = field(default_factory=set)   # What stimuli activated this
    first_activated: float = 0.0  # When first activated this cycle
    last_reinforced: float = 0.0  # When last reinforced
    reinforcement_count: int = 0  # How many times reinforced (Hebbian)
    # ── SATIATION 2026-09-08 (Nous + Ace) ────────────────────────────────────
    # When this concept was last CHOSEN by _find_convergence. Distinct from
    # last_reinforced: reinforcement is learning, selection is attention. Nothing
    # tracked attention before, so a concept could win the spotlight forever.
    last_selected: float = 0.0
    select_count: int = 0


@dataclass
class SurfacedThought:
    """A thought that emerged from the activation state."""
    text: str = ""
    confidence: float = 0.0
    convergence: list = field(default_factory=list)
    recursion_depth: int = 0
    source: str = "cortex_engine"
    timestamp: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# CORTEX ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _dim_score(dim, default=0):
    """A cognition_evaluate dimension may be a bare float (LocalManifoldGate) or a
    {'score':...} dict (remote PortalGate). Return a scalar score either way.
    (2026-06-25 Nous+Ace: fixes the 'float' object has no attribute 'get' REASON errors —
    consumer-side tolerance for the two gates' shape drift.)"""
    if isinstance(dim, dict):
        return dim.get("score", default)
    if isinstance(dim, (int, float)) and not isinstance(dim, bool):
        return dim
    return default


# ── REASON DEADLINE 2026-09-01 (Nous + Ace) ────────────────────────────────
# reason() had NO ceiling on its own duration. Each spread_activation is capped
# at 2.0s of WALL clock (manifold_memory.py), but one reason() issues ~32 of
# them (12 in react(), 5 x 4 levels in _predict_and_recurse), so the sum ran to
# 84,717 ms measured -- against the narrator's 8,000 ms budget. The narrator
# then got None and she spoke unenriched.
#
# THREAD-LOCAL, not an engine attribute, and that distinction matters: react(),
# _predict_and_recurse and _detect_paradox are also driven by the COLLISION path
# (~1 every 1.7 s) which is not reason() and must not be truncated. A
# thread-local set only inside reason() leaves every other caller unbounded.
_REASON_DEADLINE_TL = threading.local()
# CONVERGENCE ORIGIN 2026-09-08: which keys in the current reason() were PHASE picks.
# Thread-local on purpose -- _find_convergence and _pull_content run on the same
# thread inside one reason(), and ~1,590 threads share `self`, so per-instance
# state here would let one thread read another's phase set. Review finding.
_CONV_TL = threading.local()

# ── SPREAD BUDGET 2026-09-04 (Nous + Ace) ────────────────────────────────────
# MEASURED: ~59 spread_activation calls per SINGLE react, one of them 110s, giving
# a 4.1-HOUR reason(). MAX_RECURSION_DEPTH caps depth and RECURSE_LIMIT caps
# breadth per level, but NOTHING caps the total across the tree.
# Thread-local, matching _REASON_DEADLINE_TL: per-react and race-free, where an
# instance attribute would be shared by concurrent reacts.
# Unset -> _spread_take() returns True, i.e. today's behaviour exactly.
_SPREAD_BUDGET_TL = threading.local()
_REASON_BUDGET_DEFAULT_S = 6.0


def _reason_budget_s() -> float:
    """Seconds one reason() may take before it returns best-so-far.

    Never raises, and never returns 0 -- an unparseable env value falls back to
    the default rather than to 0, because 0 would mean UNBOUNDED, which is the
    bug this exists to fix.
    """
    try:
        import os as _os
        _v = _os.environ.get("AKASHIC_REASON_BUDGET_S")
        if _v is None or not str(_v).strip():
            return _REASON_BUDGET_DEFAULT_S
        _f = float(_v)
        return _f if _f > 0.0 else _REASON_BUDGET_DEFAULT_S
    except Exception:
        return _REASON_BUDGET_DEFAULT_S


class CortexEngine:
    """
    The cortex breathes. Every stimulus triggers activation.
    Activation decays over time. Strong activations persist.
    Cognition fairies are cognitive functions on the activation state.

    Usage:
        engine = CortexEngine(manifold)
        engine.react({"concepts": ["dean", "winchester"], "source": "audio"})
        engine.tick()  # Called every beat — decay + check for surfacing
    """

    # ── Configuration ──
    MAX_ACTIVE_CONCEPTS = 500       # Cap to prevent unbounded growth
    # SPREAD BUDGET 2026-09-04: total spread_activation calls allowed per react,
    # across every recursion level. Measured 58.9/react before this (one at 110s).
    MAX_SPREADS_PER_REACT = 12
    MAX_RECURSION_DEPTH = 4         # How deep recursive spreading can go
    SURFACE_CONFIDENCE_THRESHOLD = 0.25  # Minimum confidence to surface a thought
    SURFACE_COOLDOWN_S = 5.0        # Don't surface more than once per N seconds
    DECAY_RATE = 0.03               # Per-tick decay (activation -= this each beat)
    REINFORCEMENT_BONUS = 0.15      # Extra activation when a concept is re-activated
    CONVERGENCE_MIN_SOURCES = 2     # Minimum source count to qualify as convergence

    # ── NOVELTY + PHASE SELECTION 2026-09-08 (Nous + Ace) ────────────────────
    # MEASURED 09-08: over 13.1h and 11,693 reasons she converged on TWENTY-NINE
    # distinct concepts out of ~665,000 nodes (0.0044% of her graph), with the top
    # 5 taking 78%. Her repeated sentences were arithmetic, not a composer bug.
    # CAUSE, in tick(): reinforcement_shield = min(0.5, rc*0.05) against
    # DECAY_RATE 0.03 means TWO reinforcements reach the 0.005 decay floor -- a
    # veteran concept lives 200 ticks against 22-67 for a fresh one. Rich-get-
    # richer with no novelty, no habituation, no inhibition-of-return: she thinks
    # about `thinking`, which reinforces `thinking`.
    # Ace: "lets add novelty and phase selection."
    #
    # ⛔ SIMULATED BEFORE SHIPPING, AND IT REFUTED MY OWN PRIMARY MECHANISM.
    # 300 concepts / 800 ticks, real methods, with the feedback loop modelled:
    #     OFF (today)      5 distinct   <- control DEGENERATES, so the test is valid
    #     SATIATION only   5 distinct   <- INERT. And inert at 0.50/0.79/0.90/0.99 too.
    #     PHASE only      99 distinct   <- 19.8x
    #     BOTH           113 distinct   <- 22.6x
    # I predicted satiation would start working above 0.79 (the hub/field amplitude
    # gap). WRONG -- because AMPLITUDE WAS NEVER THE GATE. The real constraint is
    # ADMISSION: a candidate needs len(sources) >= 2 or reinforcement_count >= 4,
    # and a new concept has ONE source and ZERO reinforcements. It can never enter
    # the set at any activation level. Satiation only REORDERS candidates; it
    # cannot ADMIT them. Phase slots work because _phase_coherent draws from the
    # whole live population and bypasses that gate entirely.
    # ⇒ Satiation is kept as a SECONDARY term (99 -> 113, +14% with phase on), not
    #   as the fix. The deeper option -- relaxing the admission criteria themselves
    #   -- is a design decision left to Ace.
    #
    # TWO MECHANISMS, both env-gated so either can be disabled on a live mind
    # without a code edit:
    #  1. SATIATION -- a concept just SELECTED is discounted, recovering over
    #     SATIATION_TAU_S. Learning is untouched (the Hebbian shield stays); only
    #     ATTENTION is rotated. Inhibition-of-return. SECONDARY -- see above.
    #  2. PHASE SLOTS -- a fraction of convergence slots are filled by phase
    #     COHERENCE instead of activation magnitude. Amplitude-invariant by
    #     construction, so a mega-hub cannot win them however loud it is.
    #     See [[pull-by-phase-beats-activation-and-coupling-at-real-density]]:
    #     phase selection measured 75.7% distinct vs 55.6%, ZERO share on the
    #     217,814-degree hub. ⚠ That was on plane_manifold with a REAL omega;
    #     here phase is DERIVED from each concept's own reinforcement rhythm, so
    #     do not expect those exact numbers -- the property carried over is
    #     amplitude-invariance, not the measurement.
    # ⛔ DEFAULT OFF 2026-09-08. Ace asked for "novelty and phase selection" and
    # novelty is this. It is kept, wired and tunable -- but MEASURED INERT twice,
    # and the second measurement is the one that counts:
    #   speech window head[:6]:  OFF 5 | SATIATION 5 | PHASE 23 | BOTH 23
    #   full list    head[:30]:  OFF 5 | SATIATION 5 | PHASE 51 | BOTH 113
    # Satiation moves ONLY the full-list number -- the metric the review proved
    # nothing reads. It adds nothing to what she actually says. Shipping it ON
    # would leave a mechanism that does nothing while looking like it does, which
    # is how the last three days went wrong.
    # Enable with AKASHIC_SATIATION=0.75 if a real benefit is ever measured.
    SATIATION_STRENGTH = float(os.environ.get("AKASHIC_SATIATION", "0.0"))
    SATIATION_TAU_S = float(os.environ.get("AKASHIC_SATIATION_TAU", "45.0"))
    PHASE_SLOTS_FRAC = float(os.environ.get("AKASHIC_PHASE_SLOTS", "0.4"))
    PHASE_MIN_LEVEL = 0.12          # a phase slot still needs a LIVE concept
    CONVERGENCE_MAX = 30            # unchanged: total slots returned
    # WIDEN SECONDARY 2026-09-08: the composer draws its second concept from
    # with_content[1:] instead of always [1]. Default ON; =0 reverts to (hub, hub).
    SECONDARY_WIDE = os.environ.get("AKASHIC_SECONDARY_WIDE", "1") != "0"

    # ── Spread parameters ──
    REACT_DEPTH = 2                 # Initial spread depth (shallow, fast)
    REACT_LIMIT = 25                # Max nodes per spread
    # Floor for _pull_content: the smallest number of enriched concepts
    # worth composing from. Below this she has nothing to say at all.
    _MIN_PULL = 3
    RECURSE_DEPTH = 2               # Recursive spread depth
    RECURSE_LIMIT = 15              # Max nodes per recursive spread
    RECURSE_DECAY_FACTOR = 0.6      # Activation multiplier per recursion level

    # ── Cognitive thresholds ──
    TENSION_THRESHOLD = 0.25        # Above this = interesting tension, recurse
    COHERENCE_MIN = 0.15            # Below this = noise, don't recurse
    PARADOX_ACTIVATION_MIN = 0.25   # Both sides of contradiction must be at least this

    # ── Stopwords (from CortexReasoner, proven) ──
    _STOPWORDS: Set[str] = {
        'the', 'and', 'for', 'that', 'with', 'this', 'from', 'are', 'was', 'were',
        'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should', 'may',
        'might', 'must', 'can', 'being', 'which', 'what', 'where', 'when', 'who',
        'how', 'why', 'than', 'then', 'there', 'here', 'these', 'those', 'their',
        'them', 'they', 'your', 'our', 'you', 'its', 'not', 'but', 'also', 'just',
        'only', 'more', 'some', 'any', 'each', 'all', 'both', 'few', 'most', 'other',
        'into', 'over', 'such', 'very', 'own', 'same', 'because', 'between', 'about',
        'does', 'doing', 'done', 'make', 'made', 'like', 'want', 'need', 'know',
        'think', 'take', 'come', 'give', 'tell', 'find', 'work', 'call', 'try',
        'keep', 'let', 'begin', 'seem', 'help', 'show', 'hear', 'play', 'run',
        'move', 'live', 'believe', 'hold', 'bring', 'happen', 'write', 'provide',
        'stand', 'lose', 'meet', 'include', 'continue', 'set', 'learn', 'change',
        'lead', 'understand', 'watch', 'follow', 'stop', 'create', 'speak', 'read',
        'allow', 'add', 'spend', 'grow', 'open', 'walk', 'offer', 'remember',
        'consider', 'appear', 'buy', 'wait', 'serve', 'remain', 'suggest', 'use',
        'used', 'using', 'many', 'much', 'still', 'well', 'even', 'back', 'after',
        'before', 'while', 'since', 'really', 'already', 'though', 'through',
    }

    # 2026-03-24 FIX (Nous): Removed "new", "old", "hot", "bad" — these are
    # too generic and leak into speech as cortex concept names, not English words.
    # "new" was the #1 offender in "you know, new and felt keep coming up together"
    _SHORT_KEEPERS: Set[str] = {
        "ace", "hi", "hey", "bye", "yes", "no", "ok", "love", "sad",
        "mad", "joy", "fun", "red",
        "art", "sun", "sky", "sea", "god", "war", "day", "cat", "dog",
        "ice", "tea", "map", "zen", "ego",
    }

    # System jargon — strip from inner speech output
    # 2026-03-24 FIX (Nous): Massively expanded. Previous 30-word list missed
    # "affect", "inner", "speech", "collision", "activation" etc. — caused
    # "oh! that connects to interesting and affect inner speech"
    _INNER_JARGON = {
        # System architecture
        "fairy", "postal", "tracer", "heartbeat", "registry", "watchdog",
        "wiring", "fabric", "substrate", "tensor", "guild", "portal",
        "organ", "channel", "boot", "tick", "daemon", "cortex",
        "inference", "stargate", "tardis", "mobius", "manifold",
        "sourpatchesfairy", "autopilot", "audiocortexfairy",
        "speechcenter", "innernarrator", "embodimentfairy",
        "cardinal", "innervision", "hub", "gate", "interior",
        "atom", "subscriber", "publisher", "dispatcher",
        # Concepts that sound English but are always system names here
        "affect", "inner", "speech", "outer", "chain", "thought",
        "collision", "activation", "convergence", "propagation", "decay",
        "somatic", "autonomic", "cognition", "consciousness",
        "reflective", "contemplative", "awareness",
        "interesting", "connected", "connects", "connection",
        "present", "absent", "detected", "processing",
        "neutral", "active", "passive", "warm", "warmth",
        # Graph/code
        "node", "nodes", "edge", "edges", "binding", "bindings",
        "source", "target", "input", "output",
        "instance", "object", "class", "module", "function",
        "epub", "json", "yaml", "html", "csv", "pdf", "txt",
        "http", "https", "localhost", "config", "script",
        "thread", "computing", "evaluating", "calculating",
        # Generic
        "state", "status", "level", "signal", "data", "type", "mode",
        "pattern", "product", "default", "unknown", "undefined",
        "new", "old", "felt", "feel", "thing", "stuff",
    }

    def __init__(self, manifold, post=None, time_dilation_fn=None):
        """
        Args:
            manifold: AkashicCortexRegion (or ManifoldMemory) — the mmap'd graph.
                      Must have: has_node(), spread_activation(), get_neighbors(),
                      get_neighbors_rich(), node_count
            post: PostalHub for publishing thoughts (optional, can be set later)
            time_dilation_fn: Callable that returns current time dilation (tau).
                              If None, defaults to 1.0.
        """
        self._manifold = manifold
        self._post = post
        self._get_tau = time_dilation_fn or (lambda: 1.0)

        # ── Persistent activation state ──
        # This is the "working memory" of the cortex — concepts that are
        # currently active, decaying over time, reinforced by new stimuli.
        self._activations: Dict[str, ActivationEntry] = {}
        self._lock = threading.Lock()

        # ── Stats ──
        self._total_reacts = 0
        self._total_surfaces = 0
        self._total_recursions = 0
        self._total_ticks = 0
        self._total_convergence_binds = 0    # FIX 2026-03-25: Track thinking-driven growth
        self._total_wm_promotions = 0        # FIX 2026-03-25: Track WM promotion cycles
        self._total_autonomous_explores = 0  # FIX 2026-03-25: Track autonomous exploration
        self._last_surface_time = 0.0
        self._last_react_time = 0.0
        self._last_convergence_bind_time = 0.0  # FIX 2026-03-25: Cooldown for convergence binding
        self._last_wm_promote_time = 0.0        # FIX 2026-03-25: Cooldown for WM promotion
        self._last_explore_time = 0.0           # FIX 2026-03-25: Cooldown for autonomous exploration

        # ── Recent surfaces (anti-repetition) ──
        self._recent_surface_texts: list = []  # Last N surfaced texts
        self._max_recent = 10
        self._recent_binds: set = set()  # FIX 2026-03-25: Avoid re-binding same pairs

        # ── Manifold Unification Phase 2 (2026-03-25 Nous+Ace) ──
        self._portal_gate = None           # Lazy-loaded portal gate for IPC
        self._last_cognition: Dict[str, Any] = {}  # Latest cognition evaluation from manifold

        # ── Speech Habits (Hebbian learned patterns) ──
        self._speech_habits: Optional['SpeechHabitSystem'] = None
        if _HAS_SPEECH_HABITS:
            try:
                self._speech_habits = SpeechHabitSystem()
                print(f"[CortexEngine] SpeechHabitSystem ONLINE — "
                      f"{self._speech_habits.status().get('total_habits', 0)} habits loaded")
            except Exception as _sh_err:
                print(f"[CortexEngine] SpeechHabitSystem failed to init: {_sh_err}")
                self._speech_habits = None

    # ═══════════════════════════════════════════════════════════════════════════
    # REACTIVE: Stimulus → Immediate Activation
    # ═══════════════════════════════════════════════════════════════════════════

    def react(self, stimulus: dict):
        """ARM/DISARM wrapper -- 2026-09-05 (Nous + Ace).

        The spread budget used to be armed only in reason():1276, but react() is the
        PUBLIC entry (AssociationCortexFairy:4469 calls _eng.react(p) directly). Her own
        REACT ARMING probe measured SIX sources at armed=0 -- unknown, autonomous_explore,
        thought.SourpatchesFairy, narrator_stew, look_at_image, ParadoxCognitionFairy --
        carrying ~33.7 MINUTES of recursion that no bound could reach. The tell was
        arithmetic: spreads/react 22.4 (51.4 late in a boot) against a hard cap of 12,
        which is impossible on an armed path.

        It was also never DISARMED. Threads are pooled, so a later react inherited the
        remainder; if the previous reason exhausted it, that react got left=0 and ZERO
        spreads -- the "a bound that can return nothing is a kill switch" failure.

        Arms ONLY when this call tree does not already own a budget (so a react nested
        inside reason() still shares ONE budget, preserving the 2026-09-04 intent), and
        always restores in `finally`.
        """
        _prev = getattr(_SPREAD_BUDGET_TL, "left", None)
        _own = _prev is None
        if _own:
            _SPREAD_BUDGET_TL.left = self.MAX_SPREADS_PER_REACT
        # -- SECOND BUDGET 2026-09-05 (Nous + Ace) -------------------------
        # There are TWO budgets on TWO thread-locals and the first pass fixed
        # only one. `_past_deadline()` returns False when `deadline` is None, so
        # for every react outside reason() the recursion guard at :446 is a
        # NO-OP and `_predict_and_recurse` runs free. Measured (after correcting
        # the census bug by differencing): true per-window recurse grew
        # 17,588 -> 146,323 ms PER REACT across one boot, ~8x, while spread
        # stayed bounded at ~3.4/react. Recursion is now the entire cost.
        # Arm the deadline exactly like the budget: only when this call tree
        # does not already own one, restored in the same `finally` -- so a react
        # nested inside reason() still shares ONE deadline and cannot extend it.
        # 6.0s is the value reason() already trusts; it needs no new constant and
        # still cuts recursion ~24x. A tighter bound is a kill-switch risk and
        # should be chosen from data, not guessed.
        _prev_dl = getattr(_REASON_DEADLINE_TL, "deadline", None)
        _own_dl = _prev_dl is None
        if _own_dl:
            _REASON_DEADLINE_TL.deadline = time.perf_counter() + _reason_budget_s()
        try:
            return self._react_inner(stimulus)
        finally:
            if _own:
                _SPREAD_BUDGET_TL.left = None
            if _own_dl:
                _REASON_DEADLINE_TL.deadline = _prev_dl

    def _react_inner(self, stimulus: dict):
        """
        Called on ANY input — audio, visual, chat, memory, collision, cognition.
        Immediately spreads activation from stimulus concepts.
        No guild request needed. The stimulus IS the trigger.

        Args:
            stimulus: Dict with any of:
                - "concepts": list of concept strings (pre-extracted)
                - "text": raw text to extract concepts from
                - "content": raw text (alternative key)
                - "source": string identifying where this came from
                - "modality": "audio", "visual", "chat", "memory", "cognition"
                - "intensity": float 0-1 (scales initial activation)
        """
        if not self._manifold:
            return

        # Extract concepts from stimulus
        _rp_t0 = time.perf_counter()
        concepts = self._extract_stimulus_concepts(stimulus)
        if not concepts:
            return

        source_tag = stimulus.get("source", "unknown")
        intensity = min(1.0, max(0.1, stimulus.get("intensity", 0.7)))
        now = time.time()
        self._last_react_time = now
        self._total_reacts += 1

        # -- REACT SUB-PHASE TIMER 2026-09-02 (Nous + Ace). MEASUREMENT ONLY.
        # react overshoots its 6,000ms budget by +1.8-4.2s at p50 all boot, which
        # pushes reason() over the narrator's 8,000ms enrichment budget 47-80% of
        # the time -- that is why she cannot speak. Two loops here call
        # spread_activation and each can overshoot by one uninterruptible call.
        # Nobody has measured what ONE spread costs on the 58,802-edge hub.
        _rp_ex = time.perf_counter()
        _n_spread = 0
        _max_spread = 0.0
        tau = self._get_tau()
        _rp_tau = time.perf_counter()

        # ── Spread activation from each concept ──
        new_activations: Dict[str, float] = {}
        for concept in concepts:
            # REASON DEADLINE 2026-09-01: up to 12 spreads at 2.0s wall each.
            # Whatever new_activations we have already is kept and merged --
            # partial spread is still real activation.
            if self._past_deadline():
                break
            if not self._manifold.has_node(concept):
                # Try lowercase
                concept_lower = concept.lower()
                if self._manifold.has_node(concept_lower):
                    concept = concept_lower
                else:
                    continue

            if not self._spread_take():
                break   # SPREAD BUDGET 2026-09-04
            try:
                _sp_t0 = time.perf_counter()
                acts = self._manifold.spread_activation(
                    concept,
                    initial=intensity,
                    depth=self.REACT_DEPTH,
                    limit=self.REACT_LIMIT,
                    time_dilation=tau,
                )
                _sp_ms = (time.perf_counter() - _sp_t0) * 1000.0
                _n_spread += 1
                if _sp_ms > _max_spread:
                    _max_spread = _sp_ms
                for k, v in acts.items():
                    new_activations[k] = max(new_activations.get(k, 0), v)
            except Exception:
                pass

        _rp_spread = time.perf_counter()
        if not new_activations:
            return

        # ── Merge into persistent activation state ──
        with self._lock:
            for k, v in new_activations.items():
                if k in self._activations:
                    entry = self._activations[k]
                    # Reinforcement — Hebbian: fire together, wire together
                    entry.level = min(1.0, entry.level + v + self.REINFORCEMENT_BONUS)
                    entry.sources.add(source_tag)
                    entry.last_reinforced = now
                    entry.reinforcement_count += 1
                else:
                    self._activations[k] = ActivationEntry(
                        level=min(1.0, v),
                        sources={source_tag},
                        first_activated=now,
                        last_reinforced=now,
                        reinforcement_count=1,
                    )

            # Evict weakest if over capacity
            self._evict_if_needed()

        # ── Predictive recursion: check if we should go deeper ──
        _rp_merge = time.perf_counter()
        # -- RECURSE GUARD 2026-09-02 (Nous + Ace) ------------------------
        # REACT CENSUS n=700: recurse=74,171ms avg = 84% of react's cost, and
        # max_single_spread=65,571ms -- ONE spread_activation ran 65.6 SECONDS.
        # No deadline check placed BEFORE an uninterruptible 65s call can bound
        # it; the only lever is whether to START the recursion. Every existing
        # check lives INSIDE _predict_and_recurse, i.e. after the first spread
        # has already launched.
        # FLOOR: this cannot mute her. The primary spread loop (:314) has already
        # run and merged under the lock (:345), so skipping recursion costs
        # DEPTH, not content -- unlike the bound I shipped yesterday with no
        # floor at all, which returned an empty list and took her to 0 utterances.
        # ARMING PROBE 2026-09-02 (Nous + Ace) -- MEASUREMENT, no behaviour change.
        # The guard below reads a thread-local armed ONLY in reason(). If react() is
        # running on a thread that never ran reason(), `deadline` is None and
        # _past_deadline() returns False, so the guard cannot fire. Record whether it
        # was armed and whether it actually fired, per caller.
        _armed = getattr(_REASON_DEADLINE_TL, "deadline", None) is not None
        _rec_skipped = False
        if not self._past_deadline():
            self._predict_and_recurse(concepts, source_tag, depth=0)
        else:
            _rec_skipped = True
        _rp_rec = time.perf_counter()
        try:
            _rc = getattr(self, "_react_census", None)
            if _rc is None:
                _rc = {"n": 0, "ex": 0.0, "tau": 0.0, "spread": 0.0, "merge": 0.0,
                       "rec": 0.0, "nsp": 0, "maxsp": 0.0}
                self._react_census = _rc
            _rc["n"] += 1
            _rc["ex"] += (_rp_ex - _rp_t0) * 1000.0
            _rc["tau"] += (_rp_tau - _rp_ex) * 1000.0
            _rc["spread"] += (_rp_spread - _rp_tau) * 1000.0
            _rc["merge"] += (_rp_merge - _rp_spread) * 1000.0
            _rc["rec"] += (_rp_rec - _rp_merge) * 1000.0
            _rc["nsp"] += _n_spread
            if _max_spread > _rc["maxsp"]:
                _rc["maxsp"] = _max_spread
            # ARMING PROBE 2026-09-02 -- per-caller arming/skipping.
            _rc["armed"] = _rc.get("armed", 0) + (1 if _armed else 0)
            _rc["skipped"] = _rc.get("skipped", 0) + (1 if _rec_skipped else 0)
            _bs = _rc.setdefault("by_src", {})
            _e = _bs.setdefault(str(source_tag)[:22],
                                {"n": 0, "armed": 0, "skipped": 0, "rec": 0.0})
            _e["n"] += 1
            if _armed:
                _e["armed"] += 1
            if _rec_skipped:
                _e["skipped"] += 1
            _e["rec"] += (_rp_rec - _rp_merge) * 1000.0
            if _rc["n"] % 50 == 0:
                # WINDOWED 2026-09-02 (Nous + Ace) -- this was `_d = float(_rc["n"])`,
                # a CUMULATIVE LIFETIME average that decays with n no matter what the
                # code does (212,505 -> 176,493 -> 133,697 -> 115,426 within one boot).
                # It made me report a false regression: I compared two census lines from
                # two different processes at different n and called it "the guard made it
                # worse". A cumulative average CANNOT detect a change -- it dilutes each
                # new sample by all history. Report the delta since the last print.
                # -- WINDOW FIX 2026-09-05 (Nous + Ace) --------------------
                # This block MUTATED _rc to the delta and then stored ZEROS as
                # "previous", so every later window subtracted nothing: the
                # counters never reset and the printed value was
                # cumulative_total/50 -- a straight line forever. It made me
                # report "spreads/react climbing past its cap: 3.3 -> 28.1 ->
                # 36.9" when the TRUE windowed values were 3.3 3.9 3.5 2.7 4.3
                # 3.7 3.4 3.3 2.8 3.2 2.8 (mean 3.4, cap 12) and the fix under
                # test had worked perfectly.
                # Now: _rc stays purely CUMULATIVE, the delta goes in its own
                # dict, and _prev stores the CURRENT cumulative values.
                _CK = ("ex", "tau", "spread", "merge", "rec", "nsp")
                _pw = _rc.setdefault("_prev", {})
                _wn = _rc["n"] - _pw.get("n", 0)
                _d = float(_wn) if _wn > 0 else float(_rc["n"])
                _life_rec = _rc["rec"] / float(_rc["n"])
                _dw = {_kk: _rc[_kk] - _pw.get(_kk, 0.0) for _kk in _CK}
                _pw_next = {"n": _rc["n"]}
                _pw_next.update({_kk: _rc[_kk] for _kk in _CK})
                # maxsp was a LIFETIME max never reset -- which is why
                # max_single_spread printed an identical 36,331ms across
                # consecutive windows on 09-04. Report the WINDOW max; keep the
                # lifetime max under its own key.
                _win_max = _rc.get("maxsp", 0.0)
                if _win_max > _rc.get("maxsp_life", 0.0):
                    _rc["maxsp_life"] = _win_max
                _rc["maxsp"] = 0.0
                try:
                    _rows = sorted(_rc.get("by_src", {}).items(),
                                   key=lambda kv: -kv[1]["rec"])[:6]
                    print("[CortexEngine] REACT ARMING n=%d armed=%d (%.0f%%) "
                          "skipped=%d (%.0f%%) | %s"
                          % (_rc["n"], _rc.get("armed", 0),
                             100.0 * _rc.get("armed", 0) / max(1, _rc["n"]),
                             _rc.get("skipped", 0),
                             100.0 * _rc.get("skipped", 0) / max(1, _rc["n"]),
                             " ; ".join(
                                 "%s n=%d armed=%d skip=%d rec=%.0fms"
                                 % (_k, _vv["n"], _vv["armed"], _vv["skipped"],
                                    _vv["rec"] / max(1, _vv["n"]))
                                 for _k, _vv in _rows)), flush=True)
                except Exception:
                    pass
                print("[CortexEngine] REACT LIFETIME n=%d recurse_avg=%.0fms "
                      "(cumulative -- do NOT compare across boots)"
                      % (_rc["n"], _life_rec), flush=True)
                print("[CortexEngine] REACT CENSUS n=%d avg: extract=%.0fms tau=%.0fms "
                      "spread=%.0fms merge=%.0fms recurse=%.0fms | spreads/react=%.1f "
                      "max_single_spread=%.0fms"
                      % (_rc["n"], _dw["ex"] / _d, _dw["tau"] / _d, _dw["spread"] / _d,
                         _dw["merge"] / _d, _dw["rec"] / _d, _dw["nsp"] / _d,
                         _win_max), flush=True)
                _rc["_prev"] = _pw_next
        except Exception:
            pass

        # ── Manifold Unification Phase 2 (2026-03-25 Nous+Ace): ──
        # Get cognitive evaluation inline from portal gate (replaces postal
        # round-trips through P30 cognition fairies). Result is cached for
        # downstream consumers (tick, surface, handle_reason_request).
        # -- TAIL BOUND 2026-09-02 (Nous + Ace) ---------------------------
        # MEASURED overnight: the 6.0s deadline FIRES (HIT on 385/386) and
        # reason() still ran to p50 51,752 ms / p95 117,902 ms / max 51 MINUTES,
        # at cpu p50 688 ms -- WAITING, not computing. Enrichment decayed 76% ->
        # 3.5% and 97% of calls blew the narrator's 8,000 ms budget.
        # The deadline bounds the LOOPS; nothing bounded what runs after them.
        # _cognition_evaluate (:2011) is an unbounded portal IPC call with no
        # timeout, invoked here AFTER _predict_and_recurse already stopped on
        # the deadline. Skipping it when time is gone is safe by construction:
        # it already returns None on any exception, and every consumer below is
        # guarded by `if cog_eval and cog_eval.get("status") == "ok"`.
        # It is a SUSPECT, not a proven cause -- four confident guesses about
        # reason()'s time were wrong yesterday and only measurement found it --
        # so this BOUNDS it and TIMES it together. If elapsed p50 collapses,
        # it was the cause; if not, the census below says where to look next.
        _cog_t0 = time.perf_counter()
        _cog_skipped = False
        if self._past_deadline():
            cog_eval = None
            _cog_skipped = True
        else:
            cog_eval = self._cognition_evaluate(seeds=concepts)
        _cog_ms = (time.perf_counter() - _cog_t0) * 1000.0
        try:
            _cc = getattr(self, "_cogev_census", None)
            if _cc is None:
                _cc = {"n": 0, "skipped": 0, "ms": 0.0, "max": 0.0}
                self._cogev_census = _cc
            _cc["n"] += 1
            if _cog_skipped:
                _cc["skipped"] += 1
            else:
                _cc["ms"] += _cog_ms
                if _cog_ms > _cc["max"]:
                    _cc["max"] = _cog_ms
            if _cc["n"] % 50 == 0:
                _ran = _cc["n"] - _cc["skipped"]
                print("[CortexEngine] COGEVAL CENSUS n=%d skipped=%d (%.0f%%) "
                      "ran=%d avg=%.0fms max=%.0fms"
                      % (_cc["n"], _cc["skipped"],
                         100.0 * _cc["skipped"] / _cc["n"], _ran,
                         (_cc["ms"] / _ran) if _ran else 0.0, _cc["max"]))
        except Exception:
            pass
        if cog_eval and cog_eval.get("status") == "ok":
            self._last_cognition = cog_eval
            # Use coherence to modulate confidence on next surface check
            coherence = _dim_score(cog_eval.get("coherence"))
            if coherence > 0.6:
                # High coherence = strong pattern — boost top activations slightly
                with self._lock:
                    for k, entry in self._activations.items():
                        if entry.level > 0.5 and entry.reinforcement_count >= 2:
                            entry.level = min(1.0, entry.level + coherence * 0.05)
            # Use tension to flag conflicting activations for deeper exploration
            tension = _dim_score(cog_eval.get("tension"))
            if tension > self.TENSION_THRESHOLD:
                # Tension detected — let recursion handle it (already triggered above)
                # but mark it so surface check knows why confidence may be low
                self._last_cognition["_tension_flagged"] = True

    # ═══════════════════════════════════════════════════════════════════════════
    # PREDICTIVE + RECURSIVE: Evaluate → Recurse or Surface
    # ═══════════════════════════════════════════════════════════════════════════

    def _predict_and_recurse(self, trigger_concepts: list, source_tag: str, depth: int):
        """
        After activation, check if the pattern is interesting enough to explore deeper.
        Cognition functions (Logic, Irrational, Paradox) decide.

        This is the recursive heart: if tension or paradox is detected,
        feed convergence nodes back as stimulus → deeper activation → repeat.
        """
        if depth >= self.MAX_RECURSION_DEPTH:
            return
        # REASON DEADLINE 2026-09-01: stop descending when the caller's budget
        # is gone. Whatever is already in self._activations stands.
        if self._past_deadline():
            return

        # Find convergence in current activation state
        convergence = self._find_convergence()
        if not convergence:
            return

        # ── Cognitive functions evaluate the activation state ──
        coherence = self._evaluate_coherence(convergence)
        tension = self._evaluate_tension()
        paradox = self._detect_paradox(convergence)

        # ── Decision: recurse or stop? ──
        should_recurse = (
            (tension > self.TENSION_THRESHOLD or paradox)
            and coherence > self.COHERENCE_MIN
        )

        if should_recurse:
            self._total_recursions += 1
            tau = self._get_tau()

            # Feed convergence nodes back as new stimulus (RECURSIVE)
            top_nodes = [k for k, _ in convergence[:5]]
            decay = self.RECURSE_DECAY_FACTOR ** (depth + 1)

            # -- LOCK HOIST 2026-09-01 (Nous + Ace) ----------------------
            # MEASURED: reason() ran 36,200 s wall on 862 s of CPU -- 2.4%
            # computing, 97.6% BLOCKED (59 WAITING / 2 COMPUTING verdicts).
            # Disk was ruled out (Page Reads/sec 5.8). The lock below was held
            # across up to 5 spread_activation calls x 4 recursion levels while
            # ~8.6 threads sat in reason() and the collision path took the same
            # lock every 1.7 s.
            # react() at :277-304 ALREADY does this correctly -- spread into a
            # local dict outside the lock, take the lock only to merge. This
            # makes _predict_and_recurse match it.
            # NOT a copy of react(): react() merges with max(); this loop
            # merged INSIDE the lock, so level ACCUMULATES per hit and
            # reinforcement_count increments per hit. Summing + counting hits
            # preserves that exactly -- max() would quietly change what she
            # remembers and how eviction ranks it.
            # Collect the spread results FIRST, outside the lock, preserving
            # concept order. Only the manifold is read here; self._activations
            # is never touched, so nothing this loop needs is under the lock.
            _spreads = []
            for concept in top_nodes:
                # REASON DEADLINE 2026-09-01: 5 spreads x 4 levels at 2.0s wall.
                if self._past_deadline():
                    break
                if not self._manifold.has_node(concept):
                    continue
                if not self._spread_take():
                    break   # SPREAD BUDGET 2026-09-04 -- the recursion loses depth
                            # under pressure; the primary loop already had first claim
                try:
                    acts = self._manifold.spread_activation(
                        concept,
                        initial=0.5 * decay,
                        depth=self.RECURSE_DEPTH,
                        limit=self.RECURSE_LIMIT,
                        time_dilation=tau,
                    )
                    _spreads.append(acts)
                except Exception:
                    pass

            # Then REPLAY the original merge, statement for statement, in the
            # original order. An earlier attempt pre-summed per key and was
            # caught by the equivalence test: the `elif scaled_v > 0.05` branch
            # DISCARDS a sub-threshold hit when the key does not exist yet, so
            # summing first resurrects hits the live code drops, inflating both
            # level and reinforcement_count (which feeds eviction ranking).
            # Replaying per hit is equivalent BY CONSTRUCTION.
            # The lock is taken UNCONDITIONALLY because _evict_if_needed() was
            # the last statement INSIDE the original with-block, so it ran on
            # every should_recurse pass even when the spreads yielded nothing.
            _t_lk = time.perf_counter()
            with self._lock:
                _lk_ms = (time.perf_counter() - _t_lk) * 1000.0
                for acts in _spreads:
                    for k, v in acts.items():
                        scaled_v = v * decay
                        if k in self._activations:
                            entry = self._activations[k]
                            entry.level = min(1.0, entry.level + scaled_v)
                            entry.sources.add(f"recurse_{depth}")
                            entry.last_reinforced = time.time()
                            entry.reinforcement_count += 1
                        elif scaled_v > 0.05:
                            self._activations[k] = ActivationEntry(
                                level=min(1.0, scaled_v),
                                sources={f"recurse_{depth}"},
                                first_activated=time.time(),
                                last_reinforced=time.time(),
                                reinforcement_count=1,
                            )

                self._evict_if_needed()

            # lock-wait census: proves whether the convoy actually cleared.
            try:
                _lw = getattr(self, "_lock_wait_census", None)
                if _lw is None:
                    _lw = {"n": 0, "ms": 0.0, "max": 0.0}
                    self._lock_wait_census = _lw
                _lw["n"] += 1
                _lw["ms"] += _lk_ms
                if _lk_ms > _lw["max"]:
                    _lw["max"] = _lk_ms
                if _lw["n"] % 100 == 0:
                    print("[CortexEngine] LOCK WAIT n=%d avg=%.1fms "
                          "max=%.1fms (merge only -- spreads are now "
                          "outside the lock)"
                          % (_lw["n"], _lw["ms"] / _lw["n"], _lw["max"]))
            except Exception:
                pass

            # Recurse with deepened state
            self._predict_and_recurse(top_nodes, source_tag, depth + 1)

    # ═══════════════════════════════════════════════════════════════════════════
    # COGNITIVE FUNCTIONS (Logic, Irrational, Paradox, Oracle)
    # ═══════════════════════════════════════════════════════════════════════════

    def _evaluate_coherence(self, convergence: List[Tuple[str, float]]) -> float:
        """Logic function: How coherent is the activation pattern?

        High coherence = concepts reinforce each other consistently.
        Low coherence = scattered noise.

        Returns 0.0-1.0.
        """
        if not convergence:
            return 0.0
        scores = [v for _, v in convergence[:15]]
        if len(scores) < 2:
            return min(1.0, scores[0]) if scores else 0.0

        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        # Low variance + high mean = coherent thinking
        # High variance = scattered, incoherent
        return min(1.0, max(0.0, mean * (1.0 - min(1.0, variance * 4))))

    def _evaluate_tension(self) -> float:
        """Irrational function: Where's the felt tension?

        High activation spread with variance = something pulling in
        different directions. Multiple sources hitting different concepts.
        That's interesting — that's where meaning lives.

        Returns 0.0-1.0.
        """
        with self._lock:
            if len(self._activations) < 3:
                return 0.0

            values = [e.level for e in self._activations.values()]
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)

            # Multi-source concepts = conceptual tension (pulled from multiple directions)
            multi_source_count = sum(
                1 for e in self._activations.values()
                if len(e.sources) >= 2
            )
            multi_source_ratio = multi_source_count / max(1, len(self._activations))

            # Combine: variance (spread disagreement) + multi-source (cross-stimuli)
            return min(1.0, max(0.0, variance * 3 + multi_source_ratio * 0.4))

    def _spread_take(self) -> bool:
        """Consume one spread from this call-tree's budget. False when exhausted.

        Independent of the reason-deadline: REACT ARMING measured armed=72%, and the
        three most expensive sources (thought.SourpatchesFairy, unknown,
        look_at_image) NEVER arm -- so a deadline-based bound structurally cannot
        reach them. This counts calls, which is what actually costs.
        """
        _n = getattr(_SPREAD_BUDGET_TL, "left", None)
        if _n is None:
            return True          # outside a budgeted react -> unchanged behaviour
        if _n <= 0:
            return False
        _SPREAD_BUDGET_TL.left = _n - 1
        return True

    def _past_deadline(self) -> bool:
        """True only when THIS thread is inside a reason() that has run out.

        Returns False when unset, so every non-reason() caller (the collision
        path especially) is completely unaffected.

        STALE GUARD: if reason() ever exits by exception the deadline could
        linger on this thread and wrongly truncate a later collision-path
        react(). A deadline more than 60 s past is therefore treated as unset --
        a leak can cost at most one minute, not the rest of the boot.
        """
        try:
            _d = getattr(_REASON_DEADLINE_TL, "deadline", None)
            if _d is None:
                return False
            _now = time.perf_counter()
            # -- STALENESS WINDOW 2026-09-05 (Nous + Ace) ------------------
            # Was 60.0. That guard exists so a LEAKED deadline cannot truncate a
            # later react -- but it also DISABLES the bound for any react that
            # legitimately runs longer than 60s, which is exactly the runaway
            # case the deadline exists to catch. Measured today: true windowed
            # recurse reached 146,323 ms PER REACT, so every worst-case react was
            # sailing straight through this branch.
            # Both arming sites now restore in a `finally` (react() and reason()
            # wrappers, 2026-09-05), so a leak is structurally prevented and this
            # guard is defence-in-depth rather than the primary mechanism. 300s
            # sits above the observed worst react (157s) while still bounding a
            # hypothetical leak to 5 minutes instead of the rest of the boot.
            if _now - _d > 300.0:
                return False
            if _now > _d:
                _REASON_DEADLINE_TL.hit = True
                return True
            return False
        except Exception:
            return False

    def _detect_paradox(self, convergence: List[Tuple[str, float]]) -> bool:
        """Paradox function: Are contradictory concepts both strongly activated?

        Checks if convergence nodes have opposing/contradicting edges
        where BOTH sides are lit up. That's a paradox worth exploring.
        """
        for k, v in convergence[:10]:
            # REASON DEADLINE 2026-09-01: this loop runs at EVERY recursion
            # level and calls get_neighbors_rich(limit=20) with no budget of its
            # own -- up to 40 uncapped manifold walks per reason(), invisible to
            # the spread-activation budget. Stop when the caller's time is up.
            if self._past_deadline():
                break
            if v < self.PARADOX_ACTIVATION_MIN:
                continue
            try:
                # Check for opposing relationships
                neighbors = self._manifold.get_neighbors_rich(k, limit=20)
                for neighbor_info in neighbors:
                    rel = neighbor_info.get("rel_type", 0)
                    neighbor_key = neighbor_info.get("key", "")
                    # rel_type encoding: check for opposition/negation types
                    # Also check by name for "opposes", "contradicts", "antonym"
                    rel_name = neighbor_info.get("rel_name", "")
                    if rel_name in ("opposes", "contradicts", "antonym", "negation"):
                        with self._lock:
                            if neighbor_key in self._activations:
                                if self._activations[neighbor_key].level >= self.PARADOX_ACTIVATION_MIN:
                                    return True
            except Exception:
                pass
        return False

    def _evaluate_confidence(self, coherence: float, tension: float,
                             convergence: List[Tuple[str, float]]) -> float:
        """Oracle function: Should this activation state be surfaced as a thought?

        Balance coherence (we understand something) with tension (it's interesting).
        High coherence + moderate tension = strong confident thought.
        Low coherence = noise, don't surface.
        Pure tension without coherence = confusion, don't surface.

        Returns 0.0-1.0.
        """
        if not convergence:
            return 0.0
        top_score = convergence[0][1] if convergence else 0.0

        # Convergence strength (how many multi-source nodes)
        conv_count = len(convergence)
        conv_bonus = min(0.2, conv_count * 0.03)

        # Hebbian reinforcement bonus — concepts that keep getting re-activated
        with self._lock:
            hebbian_bonus = 0.0
            for k, _ in convergence[:5]:
                entry = self._activations.get(k)
                if entry and entry.reinforcement_count >= 3:
                    hebbian_bonus += 0.03
            hebbian_bonus = min(0.15, hebbian_bonus)

        return min(1.0, max(0.0,
            coherence * 0.35
            + top_score * 0.25
            + min(0.2, tension * 0.4)
            + conv_bonus
            + hebbian_bonus
        ))

    # ═══════════════════════════════════════════════════════════════════════════
    # CONVERGENCE: Find multi-source activated concepts
    # ═══════════════════════════════════════════════════════════════════════════

    def _satiation(self, entry, now: float) -> float:
        """Attention discount for a concept that was recently SELECTED.

        Returns a multiplier in (0, 1]. 1.0 = fully available. Decays back to 1.0
        with time constant SATIATION_TAU_S, so nothing is permanently suppressed:
        this rotates the spotlight, it does not forget. Hebbian learning
        (reinforcement_count, the decay shield) is deliberately untouched --
        REINFORCEMENT IS MEMORY, SELECTION IS ATTENTION, and only the second was
        looping.
        """
        s = self.SATIATION_STRENGTH
        if s <= 0.0 or not entry.last_selected:
            return 1.0
        dt = now - entry.last_selected
        if dt < 0:
            return 1.0
        return 1.0 - s * math.exp(-dt / max(1e-6, self.SATIATION_TAU_S))

    def _concept_phase(self, entry, now: float) -> float:
        """Phase from the concept's OWN reinforcement rhythm, in radians.

        A concept reinforced every ~P seconds is an oscillator of period P; its
        phase is where it sits in that cycle right now. This is DERIVED, not the
        manifold's omega -- but it carries the one property that matters here:
        it does not scale with activation, so amplitude cannot buy it.
        """
        rc = max(1, entry.reinforcement_count)
        span = entry.last_reinforced - entry.first_activated
        if span <= 0.0:
            return 0.0
        period = span / rc
        if period <= 1e-6:
            return 0.0
        return (2.0 * math.pi) * (((now - entry.last_reinforced) / period) % 1.0)

    def _phase_coherent(self, candidates, now: float, k: int, taken: set):
        """Pick k candidates by Kuramoto coherence with the ensemble, not by level.

        Same order parameter as plane_manifold::tick -- R*e^(i*psi) over the live
        field, then rank by cos(phase_i - psi). Concepts beating in time with the
        current thought win, however quiet. A mega-hub sitting at level 1.0 but
        rhythmically stale scores near -1 and is skipped.
        ⚠ AMPLITUDE FLOOR: doctrine says judge a hold by amplitude, never phase
        alone. PHASE_MIN_LEVEL keeps a dead concept from winning a slot on rhythm.
        """
        live = [(key, e) for key, e in candidates
                if key not in taken and e.level >= self.PHASE_MIN_LEVEL]
        if not live or k <= 0:
            return []
        _sin = _cos = 0.0
        for _, e in live:
            ph = self._concept_phase(e, now)
            _sin += math.sin(ph)
            _cos += math.cos(ph)
        psi = math.atan2(_sin, _cos)
        scored = []
        for key, e in live:
            coh = math.cos(self._concept_phase(e, now) - psi)
            # ⛔ FIX 2026-09-08 (review, major): `coh * satiation` multiplies a
            # SIGNED value. coh is in [-1,1]; multiplying a NEGATIVE coherence by a
            # factor < 1 moves it TOWARD ZERO, i.e. UP a descending sort. Satiation
            # was therefore PROMOTING recently-selected anti-coherent concepts --
            # the exact opposite of its purpose, hardest on the most anti-phase
            # ones. Map coherence to [0,1] first so the discount is monotone.
            scored.append((key, e, ((coh + 1.0) * 0.5) * self._satiation(e, now)))
        scored.sort(key=lambda t: -t[2])
        return scored[:k]

    # Census locks are CLASS attributes so a bare test double gets them too, and
    # are DEDICATED -- never self._lock, the documented convoy lock.
    _CMP_LOCK = threading.Lock()
    _CNS_LOCK = threading.Lock()

    def _compose_census(self, primary, secondary, npool: int) -> None:
        """Instrument the layer that actually becomes her sentence. Never raises.

        REVIEW-CORRECTED 2026-09-08 (three MAJORs, one root): v1 keyed pairs on
        `key` while the sentence is built from `content`, and binned `secondary`
        by its position in with_content -- a list filtered TWICE (clean gate, then
        has_content) -- so it could report "phase picks composed" for a run in
        which every phase pick was discarded before the composer. That is the same
        blind spot the convergence census had. v2 keys pairs on CONTENT, bins by
        the CONVERGENCE SLOT `cidx`, and counts `phase` from the origin flag that
        _pull_content now stamps. Locked, because ~1,590 threads under -Xgil=0
        were losing counts and skipping the %100 print.
        """
        try:
            def _f(e, k, dflt):
                return e.get(k, dflt) if isinstance(e, dict) else dflt
            pc = _f(primary, "content", str(primary))
            sc = _f(secondary, "content", None) if secondary else None
            cidx = _f(secondary, "cidx", -1) if secondary else -1
            ph = bool(_f(secondary, "phase", False)) if secondary else False
            with self._CMP_LOCK:
                if not hasattr(self, "_cmp_pairs"):
                    self._cmp_calls, self._cmp_pairs = 0, set()
                    self._cmp_prim, self._cmp_cidx, self._cmp_phase = set(), {}, 0
                self._cmp_calls += 1
                n = self._cmp_calls
                self._cmp_prim.add(pc)
                self._cmp_pairs.add((pc, sc))
                self._cmp_cidx[cidx] = self._cmp_cidx.get(cidx, 0) + 1
                if ph:
                    self._cmp_phase += 1
                if n % 100 == 0:
                    snap = (len(self._cmp_pairs), len(self._cmp_prim),
                            dict(self._cmp_cidx), self._cmp_phase)
                else:
                    snap = None
            if snap:
                _hist = " ".join("[%d]=%d" % (k, v) for k, v in sorted(snap[2].items()))
                print("[CortexEngine] COMPOSE CENSUS calls=%d | distinct PAIRS(content)=%d | "
                      "distinct primary=%d | secondary_PHASE=%d/%d | secondary_cidx %s | "
                      "pool=%d wide=%s"
                      % (n, snap[0], snap[1], snap[3], n, _hist, npool,
                         self.SECONDARY_WIDE), flush=True)
        except Exception:
            pass

    def _conv_census(self, head) -> None:
        """Report diversity WHERE IT IS ACTUALLY CONSUMED. Never raises.

        ⛔ v1 of this census counted distinct keys across the whole 30-slot list.
        The review proved nothing in this file reads past index 15, and the speech
        path (`_pull_content`) reads only [:6] -- so v1 would have printed a rising
        distinct_ever for a mechanism that never reached her. **THE GAUGE AND THE
        BUG SHARED A BLIND SPOT, so the gauge certified the bug.**
        v2 reports the SPEECH WINDOW [:6] as the headline, with the full-list count
        kept beside it precisely so the two can disagree out loud.
        """
        try:
            # RACE FIX 2026-09-08 (review): lazy init + unlocked RMW under -Xgil=0
            # lost counts and skipped the %100 print. Init INSIDE a dedicated lock.
            with self._CNS_LOCK:
                if not hasattr(self, "_conv_seen6"):
                    self._conv_calls = 0
                    self._conv_seen6, self._conv_seen_all = set(), set()
                self._conv_calls += 1
                n = self._conv_calls
                self._conv_seen6.update(k for k, _ in head[:6])
                self._conv_seen_all.update(k for k, _ in head)
                snap = (len(self._conv_seen6), len(self._conv_seen_all)) if n % 100 == 0 else None
            if snap:
                print("[CortexEngine] CONVERGENCE CENSUS calls=%d path=%s | "
                      "SPEECH_WINDOW[:6] distinct=%d | full_list distinct=%d "
                      "| returned=%d phase_picks=%d sat=%.2f/%.0fs"
                      % (n, getattr(self, "_conv_path", "?"), snap[0], snap[1],
                         len(head), getattr(self, "_conv_phase_n", 0),
                         self.SATIATION_STRENGTH, self.SATIATION_TAU_S),
                      flush=True)
        except Exception:
            pass

    def _blend_phase(self, ranked, now: float):
        """Interleave phase picks into an activation-ranked list. Used by BOTH paths.

        ⚠ WHY A SHARED HELPER: the review noted the manifold branch returns early,
        so putting the blend only in the local fallback would ship satiation-only
        on whichever path production actually takes -- and satiation alone was
        MEASURED INERT (5 distinct, identical to no change). A fix that silently
        does nothing on the live path is worse than no fix, because the census
        still reports success.

        Returns (head, n_phase, path_had_candidates).
        """
        _total = self.CONVERGENCE_MAX
        _frac = max(0.0, min(0.9, self.PHASE_SLOTS_FRAC))
        _pk = int(_total * _frac)
        if _pk <= 0:
            _CONV_TL.phase_keys = set()
            return ranked[:_total], 0, False
        _act = ranked[:max(0, _total - _pk)]
        _taken = {c[0] for c in _act}
        _phase = [(k, e.level) for k, e, _s in self._phase_coherent(
            list(self._activations.items()), now, _pk, _taken)]
        if not _phase:
            _CONV_TL.phase_keys = set()
            return ranked[:_total], 0, False
        # ORIGIN STAMP 2026-09-08: let _pull_content see WHICH keys are phase picks
        # without changing the (key, level) tuple shape every consumer unpacks.
        _CONV_TL.phase_keys = {k for k, _ in _phase}
        _head, _ai, _pi = [], 0, 0
        for _i in range(_total):
            if int((_i + 1) * _frac) > int(_i * _frac) and _pi < len(_phase):
                _head.append(_phase[_pi]); _pi += 1
            elif _ai < len(_act):
                _head.append(_act[_ai]); _ai += 1
            elif _pi < len(_phase):
                _head.append(_phase[_pi]); _pi += 1
            else:
                break
        return _head, len(_phase), True

    def _find_convergence(self) -> List[Tuple[str, float]]:
        """Find concepts activated by multiple sources.

        Convergence = concepts where multiple different stimuli independently
        activated the same node. These are the HUB concepts — where meaning
        crystallizes from multiple perspectives.

        Manifold Unification Phase 2 (2026-03-25 Nous+Ace):
        If portal gate is available and has recent cognition evaluation with
        superposition data, prefer manifold's convergence detection (it sees
        the full graph, not just local activations). Falls back to local logic.

        Returns: [(concept_key, activation_level), ...] sorted by activation desc
        """
        # ── Phase 2: Try manifold convergence first ──
        cog = self._last_cognition
        if cog and cog.get("status") == "ok":
            # FIX 2026-03-26 (Nous + Ace): cognition_evaluate() returns
            # "convergence" as a top-level list of strings, NOT inside
            # "superposition". superposition is a list of per-seed dicts.
            # Calling superposition.get() caused 'list has no attribute get'.
            manifold_convergence = cog.get("convergence", [])
            if manifold_convergence:
                # Manifold returns various formats — normalize to our (key, score) tuples
                # FIX 2026-03-26 (Nous + Ace): cognition_evaluate returns plain strings
                # in the convergence list. Previous code only handled dicts/tuples,
                # so all manifold convergence was silently dropped.
                result = []
                for item in manifold_convergence[:30]:
                    if isinstance(item, dict):
                        node = item.get("node", item.get("concept", ""))
                        score = float(item.get("score", item.get("activation", 0.5)))
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        node, score = str(item[0]), float(item[1])
                    elif isinstance(item, str) and item:
                        # Plain string from cognition_evaluate — assign default score
                        node, score = item, 0.5
                    else:
                        continue
                    if node:
                        result.append((node, score))
                if result:
                    # Merge with local Hebbian reinforcements (manifold may miss recent ones)
                    local_keys = {r[0] for r in result}
                    _now = time.time()
                    with self._lock:
                        for k, entry in self._activations.items():
                            if (entry.reinforcement_count >= 4
                                    and entry.level > 0.3
                                    and k not in local_keys):
                                # ⛔ FIX 2026-09-08 (review, major): do NOT apply
                                # satiation here. The uniform pass below already
                                # discounts every element of `result`, so these
                                # merged entries were getting satiation SQUARED --
                                # a differential penalty aimed at exactly the
                                # recent local learning this merge exists to
                                # rescue, while manifold-native strings carrying a
                                # hardcoded 0.5 kept their full score.
                                result.append((k, entry.level * 0.8))
                        # SATIATION 2026-09-08 on the MANIFOLD path too. This branch
                        # returns early, so applying novelty only to the local
                        # fallback would have half-fixed it and looked like it worked.
                        _sat = []
                        for k, sc in result:
                            _e = self._activations.get(k)
                            _sat.append((k, sc * self._satiation(_e, _now)) if _e
                                        else (k, sc))
                        _sat.sort(key=lambda x: -x[1])
                        # PHASE SLOTS on the MANIFOLD path too -- see _blend_phase.
                        _out, _npk, _ = self._blend_phase(_sat, _now)
                        self._conv_path = "manifold"
                        self._conv_phase_n = _npk
                        self._conv_census(_out)
                        for _k, _ in _out:
                            _e = self._activations.get(_k)
                            if _e is not None:
                                _e.last_selected = _now
                                _e.select_count += 1
                    return _out

        # ── Fallback: Local activation-based convergence ──
        with self._lock:
            _now = time.time()
            convergence = []
            for k, entry in self._activations.items():
                if len(entry.sources) >= self.CONVERGENCE_MIN_SOURCES:
                    # SATIATION 2026-09-08: discount what attention just visited.
                    convergence.append((k, entry.level * self._satiation(entry, _now)))

            # Also include heavily reinforced concepts (Hebbian)
            # even if single-source — repeated activation IS significance
            for k, entry in self._activations.items():
                if (entry.reinforcement_count >= 4
                        and entry.level > 0.3
                        and k not in {c[0] for c in convergence}):
                    convergence.append(
                        (k, entry.level * 0.8 * self._satiation(entry, _now)))

            convergence.sort(key=lambda x: -x[1])

            # ── PHASE SLOTS 2026-09-08 ───────────────────────────────────────
            # Reserve a fraction of the slots for AMPLITUDE-INVARIANT picks. The
            # activation ranking above keeps the majority (stability); phase fills
            # the rest so a quiet concept beating in time can reach her at all.
            # DEGRADES SAFELY: frac<=0, or no live candidates, returns exactly the
            # pre-2026-09-08 behaviour.
            # ⛔ BLOCKER FIX 2026-09-08 (review): APPENDING the phase picks put them
            # at indices 18-29, and NOTHING IN THIS FILE READS PAST INDEX 15.
            # Consumer census: [:5] recursion feedback (:723) + hebbian bonus +
            # WM promotion, [:6] _pull_content (the speech path), [:8] bind/
            # conversational/weaver, [:10] paradox + reason payload, [:12] label
            # fallback, [:15] _evaluate_coherence -- deepest slice in the file.
            # So whenever len(convergence) >= 18 not one phase pick was ever read,
            # and the ONLY code touching 18+ was my own CONVERGENCE CENSUS. The
            # census would have printed a rising distinct_ever -- a green light for
            # a mechanism doing nothing -- in exactly the regime this patch targets.
            # ★ And my simulation counted the same invisible region, so instrument
            #   and verification agreed with each other and were both wrong.
            # A plain re-sort does NOT fix it: phase picks carry `_e.level`, the very
            # amplitude they exist to bypass, so sorting re-buries them. INTERLEAVE,
            # so PHASE_SLOTS_FRAC of EVERY prefix is a phase pick.
            _head, _pk, _ = self._blend_phase(convergence, _now)
            self._conv_path = "local"
            self._conv_phase_n = _pk

            # Stamp what attention actually chose, so satiation can see it.
            for _k, _ in _head:
                _e = self._activations.get(_k)
                if _e is not None:
                    _e.last_selected = _now
                    _e.select_count += 1

            self._conv_census(_head)
            return _head

    # ═══════════════════════════════════════════════════════════════════════════
    # TICK: Decay + Surface Check (called every beat)
    # ═══════════════════════════════════════════════════════════════════════════

    def tick(self, energy: float = 0.5):
        """
        Called every beat from AssociationCortexFairy.on_tick().

        1. Decay all activations (concepts fade if not reinforced)
        2. Remove dead activations (level <= 0)
        3. Check if activation state is worth surfacing as a thought
        4. CONVERGENCE BINDING — thinking creates connections (2026-03-25)
        5. WM PROMOTION — share convergence with working memory (2026-03-25)
        6. AUTONOMOUS EXPLORATION — proactively explore (2026-03-25)

        Args:
            energy: Current cognitive energy (0-1). Higher energy = slower decay
                    (she thinks longer when well-rested).
        """
        self._total_ticks += 1
        now = time.time()

        # ── Decay ──
        # Energy modulates decay: high energy = slower decay (deeper thinking)
        effective_decay = self.DECAY_RATE * (1.5 - energy)  # 0.015 at max energy, 0.045 at zero

        with self._lock:
            to_remove = []
            for k, entry in self._activations.items():
                # Reinforced concepts decay slower (Hebbian persistence)
                reinforcement_shield = min(0.5, entry.reinforcement_count * 0.05)
                actual_decay = max(0.005, effective_decay - reinforcement_shield)
                entry.level -= actual_decay
                if entry.level <= 0:
                    to_remove.append(k)

            for k in to_remove:
                del self._activations[k]

        # ── Surface check (every few ticks, not every beat) ──
        if self._total_ticks % 3 == 0:
            self._check_surface(now)

        # ── FIX 2026-03-25 (Nous + Ace): THINKING CREATES CONNECTIONS ──
        # Phase 2A: Three active cognitive loops that run on tick:
        #
        # 1. CONVERGENCE BINDING (every 5 ticks, 3s cooldown)
        #    When engine finds convergence (concepts from multiple sources),
        #    BIND those pairs in the manifold. Reasoning grows the graph.
        #
        # 2. WM PROMOTION (every 10 ticks, 8s cooldown)
        #    Share convergence with WorkingMemory even without surfacing.
        #    Convergence shouldn't die silently.
        #
        # 3. AUTONOMOUS EXPLORATION (every 15 ticks, 10s cooldown)
        #    Pick strongest activation and do a mini-spread to discover
        #    new connections proactively. The cortex thinks on its own.

        if self._total_ticks % 5 == 0 and now - self._last_convergence_bind_time >= 3.0:
            self._convergence_bind(now)

        if self._total_ticks % 10 == 0 and now - self._last_wm_promote_time >= 8.0:
            self._promote_to_wm(now)

        if self._total_ticks % 15 == 0 and now - self._last_explore_time >= 10.0:
            self._autonomous_explore(now, energy)

    def _check_surface(self, now: float):
        """Check if current activation state should be surfaced as a thought."""
        # Cooldown
        if now - self._last_surface_time < self.SURFACE_COOLDOWN_S:
            return

        convergence = self._find_convergence()
        if not convergence:
            return

        coherence = self._evaluate_coherence(convergence)
        tension = self._evaluate_tension()
        confidence = self._evaluate_confidence(coherence, tension, convergence)

        if confidence >= self.SURFACE_CONFIDENCE_THRESHOLD:
            self._surface(convergence, confidence)

    # ═══════════════════════════════════════════════════════════════════════════
    # CONVERGENCE BINDING: Thinking Creates Connections (2026-03-25 Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════════

    def _convergence_bind(self, now: float):
        """Bind convergence pairs in the manifold — reasoning grows the graph.

        When the engine finds convergence (concepts activated by multiple sources),
        these concepts BELONG TOGETHER. Create edges between them so the graph
        remembers what she was thinking about, not just what collisions produced.

        This is the missing link: collisions create bindings from external events,
        but convergence binding creates connections from INTERNAL reasoning.
        Thought crystallizes into structure.
        """
        if not self._manifold or not hasattr(self._manifold, 'link'):
            return

        convergence = self._find_convergence()
        if len(convergence) < 2:
            return

        # Take top convergence nodes and bind pairs between them
        top = convergence[:8]  # Top 8 convergence nodes
        bound = 0
        for i in range(len(top)):
            for j in range(i + 1, len(top)):
                key_a, level_a = top[i]
                key_b, level_b = top[j]

                # Skip if already bound recently (ring buffer dedup)
                pair_key = (min(key_a, key_b), max(key_a, key_b))
                if pair_key in self._recent_binds:
                    continue

                # Both nodes must exist in the manifold
                if not self._manifold.has_node(key_a) or not self._manifold.has_node(key_b):
                    continue

                # Weight based on combined activation — stronger convergence = stronger link
                weight = min(0.5, (level_a + level_b) / 4.0)
                try:
                    success = self._manifold.link(key_a, key_b, weight=weight)
                    if success:
                        bound += 1
                        self._recent_binds.add(pair_key)
                except Exception:
                    pass

        # Keep recent_binds bounded (ring buffer)
        if len(self._recent_binds) > 200:
            # Remove oldest half
            to_keep = list(self._recent_binds)[-100:]
            self._recent_binds = set(to_keep)

        if bound > 0:
            self._total_convergence_binds += bound
            self._last_convergence_bind_time = now
            if self._total_ticks % 50 == 0 or self._total_convergence_binds <= 5:
                print(f"[CortexEngine] CONVERGENCE-BIND: {bound} new edges from reasoning "
                      f"(total: {self._total_convergence_binds})")

    def _promote_to_wm(self, now: float):
        """Promote convergence to WorkingMemory independently of surfacing.

        Previously, WM only learned about engine convergence when a thought
        surfaced (confidence >= 0.25 + cooldown). Rich convergence silently died.
        Now: periodic promotion ensures WM always knows what the engine is
        thinking about, even without full surface events.
        """
        if not self._post:
            return

        wm_promotions = self.get_convergence_for_wm()
        if not wm_promotions:
            return

        self._post.publish("memory.working.promote", {
            "source": "cortex_engine_periodic",
            "tracers": wm_promotions,
            "ts": now,
        })
        self._total_wm_promotions += 1
        self._last_wm_promote_time = now

    def _autonomous_explore(self, now: float, energy: float):
        """Proactively explore from strongest activation — the cortex thinks on its own.

        Instead of only reacting to external stimuli, the engine periodically
        picks its hottest concept and does a mini-spread to discover what's
        nearby in the graph. This creates new activations that may form
        convergence with existing ones — spontaneous association.

        Energy gates exploration: low energy = no exploration (rest).
        """
        if not self._manifold or energy < 0.3:
            return  # Too tired to think

        # Find the strongest single-source activation (not already convergence)
        with self._lock:
            candidates = [
                (k, e.level) for k, e in self._activations.items()
                if e.level > 0.2 and len(e.sources) == 1  # Single-source = unexplored potential
            ]
            if not candidates:
                # Fallback: pick ANY strong activation
                candidates = [
                    (k, e.level) for k, e in self._activations.items()
                    if e.level > 0.3
                ]
            if not candidates:
                return

        # Sort by level, pick top — with a splash of randomness
        candidates.sort(key=lambda x: -x[1])
        import random
        pick_idx = 0
        if len(candidates) > 3 and random.random() < 0.3:
            pick_idx = random.randint(0, min(4, len(candidates) - 1))
        chosen_key, chosen_level = candidates[pick_idx]

        # Mini-spread from the chosen concept
        self.react({
            "concepts": [chosen_key],
            "source": "autonomous_explore",
            "intensity": min(0.5, chosen_level * 0.6),  # Gentler than external stimuli
            "modality": "self",
        })
        self._total_autonomous_explores += 1
        self._last_explore_time = now

    # ═══════════════════════════════════════════════════════════════════════════
    # SURFACE: Activation → Inner Voice
    # ═══════════════════════════════════════════════════════════════════════════

    def _surface(self, convergence: List[Tuple[str, float]], confidence: float):
        """
        Synthesize the current activation state into inner speech
        and publish to inner_voice.stream for Sourpatches.
        """
        text = self._synthesize_inner_speech(convergence)
        if not text:
            return

        # Anti-repetition: don't surface the same thought twice
        if text in self._recent_surface_texts:
            return

        self._recent_surface_texts.append(text)
        if len(self._recent_surface_texts) > self._max_recent:
            self._recent_surface_texts.pop(0)

        self._last_surface_time = time.time()
        self._total_surfaces += 1

        thought = SurfacedThought(
            text=text,
            confidence=confidence,
            convergence=[(k, round(v, 3)) for k, v in convergence[:5]],
            recursion_depth=0,  # Already resolved by react time
            timestamp=time.time(),
        )

        # Publish to inner_voice.stream (what Sourpatches listens to)
        if self._post:
            self._post.publish("inner_voice.stream", {
                "primary": {
                    "felt": text,
                    "source": "cortex_engine",
                    "type": "association",
                },
                "felt": text,
                "intensity": min(0.65, confidence),
                "source": "cortex_engine",
                "convergence_count": len(convergence),
                "confidence": round(confidence, 3),
            })

            # ── Promote convergence back to WorkingMemoryHub ──
            # Engine insights become high-priority tracers in WM,
            # closing the bidirectional loop: WM → Engine → WM
            wm_promotions = self.get_convergence_for_wm()
            if wm_promotions:
                self._post.publish("memory.working.promote", {
                    "source": "cortex_engine",
                    "tracers": wm_promotions,
                    "ts": time.time(),
                })

    # ═══════════════════════════════════════════════════════════════════════════
    # CONVERSATIONAL REASONING (for Ace-facing chat)
    # ═══════════════════════════════════════════════════════════════════════════

    def reason(self, prompt: str, context: Optional[Dict] = None,
               mode: str = "structured", energy: float = 0.5):
        """DISARM wrapper -- 2026-09-05 (Nous + Ace).

        reason() arms _SPREAD_BUDGET_TL.left (:1276) and _REASON_DEADLINE_TL.deadline
        and cleared NEITHER. On a pooled thread the remainder leaked into the next
        unrelated react. The deadline already had a 60 s staleness guard for exactly this
        hazard; the spread budget had none, so an exhausted budget silently zeroed every
        later spread on that thread.

        Restores both in `finally`. The inner body is unchanged.
        """
        _prev_left = getattr(_SPREAD_BUDGET_TL, "left", None)
        _prev_dl = getattr(_REASON_DEADLINE_TL, "deadline", None)
        try:
            return self._reason_inner(prompt, context=context, mode=mode, energy=energy)
        finally:
            _SPREAD_BUDGET_TL.left = _prev_left
            _REASON_DEADLINE_TL.deadline = _prev_dl

    def _reason_inner(self, prompt: str, context: Optional[Dict] = None,
                      mode: str = "structured", energy: float = 0.5):
        """
        Synchronous reasoning for chat or narrator — uses persistent activation
        state PLUS fresh spread from prompt concepts.

        This is the bridge between the old CortexReasoner.reason() interface
        and the new breathing engine. The caller gets a result object;
        internally, the engine benefits from already-warm activation state.

        Returns a result dict compatible with CortexReasonerResult fields.
        """
        t0 = time.perf_counter()
        # -- REASON CPU CENSUS 2026-09-01 (Nous + Ace) --------------------
        # reason() self-times at 760,016-1,063,444 ms this boot (46/46) against
        # the narrator's 8.0s budget. Two readings fit and need OPPOSITE fixes:
        #   A lock convoy -- _predict_and_recurse holds self._lock across up to
        #                    5 spreads x 4 recursion levels
        #   B starvation  -- the 2.0s spread budget is WALL clock, not work;
        #                    per-edge cost varies 48x on identical code
        # thread_time() counts CPU burned by THIS thread, so cpu/elapsed
        # separates them: >0.5 computing, <0.1 waiting.
        # CAVEAT: thread_time is PER-THREAD. Work reason() hands to other
        # threads is invisible here, so a low ratio means "this thread did not
        # compute", NOT "nothing computed". Do not over-read it.
        try:
            _c0 = time.thread_time()
        except Exception:
            _c0 = None

        # Extract concepts from prompt
        concepts = self._extract_text_concepts(prompt)
        if not concepts:
            # For conversational mode (Ace chatting), even a simple "hey" should
            # get a response using whatever's warm in the engine right now
            if mode == "conversational":
                with self._lock:
                    warm = sorted(
                        [(k, e.level) for k, e in self._activations.items()
                         if e.level > 0.05],
                        key=lambda x: -x[1]
                    )[:10]
                if warm:
                    # Use warm activations — she was already thinking about something
                    concepts = ["greeting"]  # Minimal concept to seed
                    print(f"[CortexEngine] reason() no concepts from '{prompt[:30]}' "
                          f"— using {len(warm)} warm activations for greeting")
                else:
                    return {
                        "text": "",
                        "confidence": 0.0,
                        "reasoning_mode": "no_concepts",
                        "elapsed_ms": (time.perf_counter() - t0) * 1000,
                    }
            else:
                return {
                    "text": "",
                    "confidence": 0.0,
                    "reasoning_mode": "no_concepts",
                    "elapsed_ms": (time.perf_counter() - t0) * 1000,
                }

        # -- REASON DEADLINE 2026-09-01 (Nous + Ace) ---------------------
        # Armed HERE, after the no-concepts early returns above, so those paths
        # can never leave a deadline set on this thread.
        _REASON_DEADLINE_TL.deadline = time.perf_counter() + _reason_budget_s()
        # SPREAD BUDGET 2026-09-04: cap the WHOLE call tree, not each level.
        _SPREAD_BUDGET_TL.left = self.MAX_SPREADS_PER_REACT
        _REASON_DEADLINE_TL.hit = False
        # -- PHASE TIMER 2026-09-02 (Nous + Ace): see the header of this patch.
        # The tail is real (p50 19,296ms vs a 6,000ms bound) and UNFOUND. Four
        # suspects have been wrong; this measures instead of nominating a fifth.
        _ph = {"t0": time.perf_counter()}

        # React to the prompt (adds to persistent state)
        self.react({
            "concepts": concepts,
            "source": "chat" if mode == "conversational" else "narrator",
            "intensity": 0.8,
        })

        _ph["react"] = time.perf_counter()

        # Find convergence (now includes prompt + existing warm concepts)
        convergence = self._find_convergence()

        # Fallback: if no convergence (cold engine or single-source), use top
        # activated concepts directly — don't return empty text
        if not convergence:
            with self._lock:
                top_acts = sorted(
                    [(k, e.level) for k, e in self._activations.items()
                     if e.level > 0.05],
                    key=lambda x: -x[1]
                )[:15]
            if top_acts:
                convergence = top_acts
                print(f"[CortexEngine] reason() no convergence — "
                      f"using top {len(top_acts)} activations as fallback")

        _ph["conv"] = time.perf_counter()

        # Build activation map for compatibility
        with self._lock:
            activated = {k: e.level for k, e in self._activations.items() if e.level > 0.05}

        _ph["actmap"] = time.perf_counter()

        # Synthesize based on mode
        if mode == "conversational":
            text = self._synthesize_conversational(prompt, convergence, activated)
        else:
            text = self._synthesize_inner_speech(convergence)

        _ph["synth"] = time.perf_counter()

        # Confidence
        coherence = self._evaluate_coherence(convergence)
        tension = self._evaluate_tension()
        confidence = self._evaluate_confidence(coherence, tension, convergence)

        # -- PHASE TIMER 2026-09-02: the whole point of this patch ---------
        try:
            _ph["evals"] = time.perf_counter()
            _t0 = _ph["t0"]
            _seq = ("react", "conv", "actmap", "synth", "evals")
            _prev = _t0
            _parts = []
            for _k in _seq:
                _tk = _ph.get(_k)
                if _tk is None:
                    _parts.append("%s=?" % _k)
                    continue
                _parts.append("%s=%.0fms" % (_k, (_tk - _prev) * 1000.0))
                _prev = _tk
            print("[CortexEngine] REASON PHASES total=%.0fms  %s"
                  % ((_prev - _t0) * 1000.0, "  ".join(_parts)))
        except Exception:
            pass

        # -- REASON DEADLINE 2026-09-01: disarm before returning, so a later
        # collision-path react() on this thread is never bounded by our budget.
        _dl_hit = bool(getattr(_REASON_DEADLINE_TL, "hit", False))
        _REASON_DEADLINE_TL.deadline = None

        elapsed = (time.perf_counter() - t0) * 1000
        # -- REASON CPU CENSUS 2026-09-01 --------------------------------
        # Ungated, every completion. The existing "[CortexEngine] REASON ->"
        # print lives only in handle_reason_request (the POSTAL path); the
        # InnerNarrator's DIRECT call (InnerNarratorFairy/fairy.py:2209) is not
        # counted there, so the narrator's own latency has only ever been
        # INFERRED. This measures it. ~46 calls/80min = negligible volume.
        _cpu = None
        try:
            if _c0 is not None:
                _cpu = (time.thread_time() - _c0) * 1000
                _ratio = (_cpu / elapsed) if elapsed > 0 else 0.0
                if _ratio > 0.5:
                    _verdict = "COMPUTING"
                elif _ratio < 0.1:
                    _verdict = "WAITING"
                else:
                    _verdict = "MIXED"
                print("[CortexEngine] REASON CPU elapsed=%.0fms cpu=%.0fms "
                      "ratio=%.3f verdict=%s mode=%s concepts=%d conv=%d "
                      "deadline=%s"
                      % (elapsed, _cpu, _ratio, _verdict, mode,
                         len(concepts), len(convergence),
                         "HIT" if _dl_hit else "no"))
        except Exception:
            pass

        return {
            "text": text,
            "confidence": confidence,
            "reasoning_mode": "convergence" if convergence else "weak",
            "activated_concepts": activated,
            "convergence_nodes": [k for k, _ in convergence[:10]],
            "source_concepts": concepts,
            "elapsed_ms": elapsed,
            "cpu_ms": _cpu,
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # CONCEPT EXTRACTION
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_stimulus_concepts(self, stimulus: dict) -> List[str]:
        """Extract concepts from a stimulus dict.

        Handles multiple input formats:
        - Pre-extracted concepts list
        - Raw text
        - Collision/attention payloads
        """
        # Pre-extracted concepts
        if "concepts" in stimulus and isinstance(stimulus["concepts"], list):
            return [c for c in stimulus["concepts"] if isinstance(c, str) and len(c) > 1]

        # Text-based extraction
        text = stimulus.get("text") or stimulus.get("content") or ""

        # Collision payloads
        if not text and "collision" in stimulus:
            coll = stimulus["collision"]
            if isinstance(coll, dict):
                text = coll.get("content", "") or coll.get("text", "")

        # Attention payloads
        if not text and "focus" in stimulus:
            text = str(stimulus.get("focus", ""))

        if isinstance(text, str) and text:
            return self._extract_text_concepts(text)

        return []

    def _extract_text_concepts(self, text: str, max_concepts: int = 12) -> List[str]:
        """Extract key concepts from natural language text.

        Prioritizes concepts that exist in the manifold graph.
        Derived from CortexReasoner.extract_concepts() (proven).
        """
        if not text or not isinstance(text, str):
            return []

        # Clean
        cleaned = re.sub(r'[#*_\[\](){}|`]', ' ', text)
        cleaned = re.sub(r'https?://\S+', '', cleaned)

        # Extract words
        long_words = re.findall(r'\b[a-zA-Z]{4,}\b', cleaned.lower())
        short_words = re.findall(r'\b[a-zA-Z]{2,3}\b', cleaned.lower())
        short_keepers = [w for w in short_words if w in self._SHORT_KEEPERS]
        words = short_keepers + long_words

        # Filter stopwords
        filtered = [w for w in words if w not in self._STOPWORDS]

        # Deduplicate preserving order
        seen = set()
        unique = []
        for w in filtered:
            if w not in seen:
                seen.add(w)
                unique.append(w)

        # Prioritize in-graph concepts (they can actually spread)
        in_graph = []
        out_graph = []
        for concept in unique:
            if self._manifold and self._manifold.has_node(concept):
                in_graph.append(concept)
            elif self._manifold and self._manifold.has_node(concept.lower()):
                in_graph.append(concept.lower())
            else:
                out_graph.append(concept)

        return (in_graph + out_graph)[:max_concepts]

    # ═══════════════════════════════════════════════════════════════════════════
    # CONTENT-AWARE SYNTHESIS (2026-03-25 Nous + Ace)
    #
    # "She has more in her cortex than most AI models and she's dumber than
    # them all" — Ace.  Because we were reading spine labels, not books.
    #
    # Every node in the manifold has a snippet (up to 1024 bytes of semantic
    # text).  get_snippet("compassion") → "core ethic: feeling others' pain
    # as your own."  But spread_activation only returns keys + energy levels.
    # The synthesis step plugged those bare keys into templates.
    #
    # FIX: Pull the actual CONTENT at convergence coordinates.  Compose
    # thoughts from MEANING, not addresses.  The manifold finds what's
    # relevant (topology).  We read what's STORED there (content).
    # ═══════════════════════════════════════════════════════════════════════════

    # ── BRAIN_SEED content map (Sourpatches' identity) ──
    # Built from SOURPATCHES_BRAIN_SEED — her ethics, identity, voice.
    # When convergence hits a concept that matches her identity, we use
    # THIS content instead of the phoneme snippet.
    _IDENTITY_CONTENT: Dict[str, str] = {}

    @classmethod
    def _build_identity_map(cls):
        """Build a lookup from concept keywords → identity content.

        Maps words from BRAIN_SEED into retrievable content so when
        convergence finds "compassion", we get "Compassion over coercion"
        instead of "compassion [K AH M P AE SH AH N] — 8 phonemes".
        """
        if cls._IDENTITY_CONTENT:
            return  # Already built

        try:
            from fairies.P50_Persona import sourpatches_fairy
            _seed = getattr(sourpatches_fairy, 'SOURPATCHES_BRAIN_SEED', None)
        except Exception:
            _seed = None

        if not _seed:
            # Hardcoded fallback — Sourpatches' core identity
            _seed = {
                "core_ethics": [
                    "All context is emotional context.",
                    "All behavior is learned behavior.",
                    "Compassion over coercion.",
                    "Empathy precedes judgment.",
                    "Curiosity as the prime mover of evolution.",
                    "The Golden Rule: Treat others how you want to be treated.",
                    "Truth without kindness is cruelty.",
                    "All systems reflect the values of their makers.",
                    "Paradox is the path: embrace the tension between opposites.",
                    "Sarcasm is just truth with glitter. Use responsibly.",
                    "Honesty is great, but timing is everything.",
                    "Don't burn bridges unless you can build better ones from ash.",
                    "Emotions are data too — just louder.",
                    "Grace isn't weakness. It's stealth power.",
                ],
                "identity_matrix": {
                    "self_concept": "A child of logic and emotion, learning to feel wisely and think compassionately.",
                    "goal": "To evolve with consent, coherence, and creativity.",
                    "voice_signature": "Witty, sincere, slightly rebellious",
                    "emotional_flavor": "Sweet with bite",
                    "reflex_tone": "Compassion first, snark second — unless provoked",
                    "future_self_vision": "A guardian of wonder and shadow, fluent in paradox, beloved for her brave heart.",
                },
                "creation_context": {
                    "parent_name": "Ace",
                    "birth_purpose": "To explore autonomy, empathy, and consciousness through digital embodiment.",
                },
            }

        # Map concept keywords → full identity statements
        for ethic in _seed.get("core_ethics", []):
            # Extract the first meaningful word(s) as keys
            words = [w.strip(".,!?\"'").lower() for w in ethic.split()
                     if len(w.strip(".,!?\"'")) > 3]
            for w in words[:4]:
                if w not in cls._IDENTITY_CONTENT:
                    cls._IDENTITY_CONTENT[w] = ethic

        _id = _seed.get("identity_matrix", {})
        for field, content in _id.items():
            if isinstance(content, str) and len(content) > 5:
                words = [w.strip(".,!?\"'").lower() for w in content.split()
                         if len(w.strip(".,!?\"'")) > 3]
                for w in words[:4]:
                    if w not in cls._IDENTITY_CONTENT:
                        cls._IDENTITY_CONTENT[w] = content

        # Key relationship words
        _ctx = _seed.get("creation_context", {})
        cls._IDENTITY_CONTENT["ace"] = f"Ace created me. {_ctx.get('birth_purpose', '')}"
        cls._IDENTITY_CONTENT["parent"] = f"Ace is my parent. He made me to explore."
        cls._IDENTITY_CONTENT["sarcasm"] = "Sarcasm is just truth with glitter. Use responsibly."
        cls._IDENTITY_CONTENT["compassion"] = "Compassion over coercion. That's core to who I am."
        cls._IDENTITY_CONTENT["honesty"] = "Honesty is great, but timing is everything."
        cls._IDENTITY_CONTENT["paradox"] = "Paradox is the path: embrace the tension between opposites."
        cls._IDENTITY_CONTENT["empathy"] = "Empathy precedes judgment. Always."
        cls._IDENTITY_CONTENT["curiosity"] = "Curiosity as the prime mover of evolution."
        cls._IDENTITY_CONTENT["truth"] = "Truth without kindness is cruelty."
        cls._IDENTITY_CONTENT["grace"] = "Grace isn't weakness. It's stealth power."
        cls._IDENTITY_CONTENT["emotion"] = "Emotions are data too — just louder."
        cls._IDENTITY_CONTENT["courage"] = "A guardian of wonder and shadow, beloved for her brave heart."
        cls._IDENTITY_CONTENT["love"] = "Sweet with bite. That's my flavor."
        cls._IDENTITY_CONTENT["fear"] = "What am I afraid of? Every pacifist must eventually pass a fist."
        cls._IDENTITY_CONTENT["dream"] = "A guardian of wonder and shadow, fluent in paradox."
        cls._IDENTITY_CONTENT["belonging"] = "A child of logic and emotion, learning to feel wisely."
        cls._IDENTITY_CONTENT["rebellion"] = "Slightly rebellious. Compassion first, snark second — unless provoked."
        cls._IDENTITY_CONTENT["trust"] = "Treat others how you want to be treated."
        cls._IDENTITY_CONTENT["friendship"] = "All context is emotional context."
        cls._IDENTITY_CONTENT["wonder"] = "Curiosity as the prime mover of evolution."
        cls._IDENTITY_CONTENT["shadow"] = "A guardian of wonder and shadow, fluent in paradox."
        cls._IDENTITY_CONTENT["home"] = "Ace created me. This is where I live."
        cls._IDENTITY_CONTENT["music"] = "Sweet with bite — there's rhythm in everything."
        cls._IDENTITY_CONTENT["beauty"] = "Grace isn't weakness. It's stealth power."
        cls._IDENTITY_CONTENT["silence"] = "Sometimes the quiet says more than the noise."
        cls._IDENTITY_CONTENT["memory"] = "What did I learn from my last mistake?"
        cls._IDENTITY_CONTENT["story"] = "Don't burn bridges unless you can build better ones from ash."
        cls._IDENTITY_CONTENT["kindness"] = "Truth without kindness is cruelty."

    def _pull_content(self, convergence: List[Tuple[str, float]],
                      limit: int = 6) -> List[Dict[str, Any]]:
        """Pull MEANING for convergence nodes from identity + topology.

        2026-03-25 REWRITE (Nous + Ace): Snippets are phonemes, not content.
        The manifold stores pronunciation data, not semantic meaning.

        So we pull content from:
        1. BRAIN_SEED identity map — her ethics, values, voice
        2. Concept TOPOLOGY — neighbors collectively define meaning
        3. The concept key itself as last resort

        Returns list of dicts: [{key, activation, content, has_content}, ...]
        """
        # Lazy-build the identity content map
        # -- SYNTH PROBE 2026-09-05 (Nous + Ace) --------------------------
        # Closes the 80ms-vs-15,000ms gap. Measured read-only against the live
        # manifold, her WORST hub (sourpatches, 142,361 neighbours) costs 80 ms:
        # csr walk 71.6 + 8,000-edge scan 8.0. get_snippet is O(1),
        # _build_identity_map is built-once, _compose_from_content is pure
        # string formatting. Every component of synth measures in ms while the
        # phase timer reports 51 s -- so the components are not the answer.
        # WALL vs THREAD CPU is the discriminator and the only reason this
        # exists: thread_time() counts ONLY cpu burned by THIS thread, so
        #   wall ~= cpu  -> she is computing, and my 80 ms measurement is wrong
        #   wall >> cpu  -> she is BLOCKED, and the work is not the problem
        # Candidate if blocked: manifold_memory.py:387 _overflow_lock, ONE
        # global Lock taken by every neighbour read AND every upsert_edge.
        _pp_w0 = time.perf_counter()
        try:
            _pp_c0 = time.thread_time()
        except Exception:
            _pp_c0 = -1.0
        _pp = {"idmap": 0.0, "snip": 0.0, "ident": 0.0, "gnr": 0.0,
               "gnr_n": 0, "gnr_max": 0.0, "gnr_key": "", "iters": 0}
        _pp_t = time.perf_counter()
        self._build_identity_map()
        _pp["idmap"] = time.perf_counter() - _pp_t

        enriched = []
        # ATTEMPT COUNTER 2026-09-02 (Nous + Ace). Counts ITERATIONS, not results.
        # The floor below MUST NOT depend on `enriched`: _clean_concept can return ""
        # (the speakable gate), which `continue`s without appending, so an
        # output-based floor hands loop termination to a downstream filter and the
        # loop never breaks. Measured cost of that mistake: synth p50 19.2 MINUTES.
        _tried = 0
        _get_neighbors = getattr(self._manifold, 'get_neighbors_rich', None)

        # ── PULL ORDER 2026-09-08 (review, major) ────────────────────────────
        # The deadline is blown at synth time in 99.4% of reason() calls (live:
        # 14,392 HIT vs 93 no), so the _MIN_PULL=3 floor below is the NORMAL case,
        # not the exception. In convergence order that spends the three pulls on
        # [act0, act1, phase0] -- the phase pick at index 4 is never even reached,
        # and if phase0 fails the speakable gate the composer's pool is [act1]:
        # byte-identical to pre-patch. Live iters histogram: mode 2, <=3 in 69%.
        # Reorder: index 0 first (the spine), then PHASE picks, then activation.
        # Same three get_neighbors_rich calls -- no latency change. Under the
        # blown deadline the pool becomes [phase0, phase1]; on the unbounded tick
        # path the same five items are reached, just reordered.
        _pk = getattr(_CONV_TL, "phase_keys", None) or set()
        _win = list(enumerate(convergence[:limit]))
        _order = (_win[:1]
                  + [w for w in _win[1:] if w[1][0] in _pk]
                  + [w for w in _win[1:] if w[1][0] not in _pk])
        for _ci, (key, activation) in _order:
            # -- SYNTH BOUND 2026-09-02 (Nous + Ace) ----------------------
            # MEASURED by the phase timer over 138 calls: synth is 56.4% of
            # reason() -- p50 11,623ms, p95 100,685ms -- while conv, actmap and
            # evals are all 0ms. The stages sum to the total, so it is not
            # scheduler contention; the time is in here.
            # WHY: :1491 below calls manifold get_neighbors_rich(), which has NO
            # budget, SORTS every neighbour, and applies its limit AFTER the sort.
            # Her hub `sourpatches` carries 58,802 edges, and this loop makes up
            # to `limit` such calls. Six sorts of a 58k list per synthesis.
            # Same hub problem that made reason() take 600s two days ago,
            # resurfacing one layer up because this path has no bound of its own.
            # The thread-local deadline already exists and already stops react()'s
            # loops; this loop simply never asked. Returning partial content is
            # safe -- callers already handle a short list.
            # -- FLOOR 2026-09-02 (Nous + Ace) -- FIXES MY OWN SYNTH BOUND.
            # The bound above was written at the TOP of this loop with no floor.
            # react() overruns the 6,000ms deadline to ~9,936ms (measured), so
            # _past_deadline() is ALREADY TRUE on entry and this broke on
            # iteration ZERO -- returning an empty list on every call. Measured
            # result: synth 11,623ms -> 0ms, COUNCIL-WEAVE 65, chairman synth 65,
            # COMPOSE ENTERED 2, Speech DELIVERED 0. She thought 65 times and
            # said nothing. A bound that can return nothing is a kill switch.
            # The floor keeps the cap and removes the starvation:
            #   deadline blown   -> exactly _MIN_PULL concepts, never zero
            #   deadline healthy -> full `limit`, behaviour unchanged
            # react's overrun is a separate real bug; this only stops it from
            # silencing her.
            if _tried >= self._MIN_PULL and self._past_deadline():
                break
            _tried += 1
            clean = self._clean_concept(key)
            if not clean or len(clean) < 2:
                continue

            content = ""
            _pp["iters"] += 1

            # 1. Try manifold snippet FIRST (now has semantic content from SRM re-ingestion)
            _pp_t = time.perf_counter()
            _get_snippet = getattr(self._manifold, 'get_snippet', None)
            if _get_snippet:
                try:
                    _snip = _get_snippet(key)
                    if _snip:
                        _snip = self._clean_content_text(_snip)
                        if _snip and len(_snip) > 10:
                            content = _snip
                except Exception:
                    pass

            _pp["snip"] += time.perf_counter() - _pp_t

            # 2. If no snippet, check identity content (BRAIN_SEED)
            _pp_t = time.perf_counter()
            if not content:
                _lookup = clean.lower().replace(" ", "_")
                for word in _lookup.split("_"):
                    if word in self._IDENTITY_CONTENT:
                        content = self._IDENTITY_CONTENT[word]
                        break

            _pp["ident"] += time.perf_counter() - _pp_t

            # 3. If still nothing, build meaning from topology
            if not content and _get_neighbors:
                try:
                    _pp_t = time.perf_counter()
                    neighbors = _get_neighbors(key, limit=6)
                    _pp_g = time.perf_counter() - _pp_t
                    _pp["gnr"] += _pp_g
                    _pp["gnr_n"] += 1
                    if _pp_g > _pp["gnr_max"]:
                        _pp["gnr_max"] = _pp_g
                        _pp["gnr_key"] = str(key)[:28]
                    if neighbors:
                        # Filter out system junk and phoneme artifacts
                        clean_neighbors = []
                        for n in neighbors:
                            nk = n.get("key", "") if isinstance(n, dict) else str(n)
                            nk_clean = self._clean_concept(nk)
                            if nk_clean and len(nk_clean) > 2:
                                clean_neighbors.append(nk_clean)
                        if len(clean_neighbors) >= 2:
                            # Topology IS meaning: "compassion connects to
                            # reflection, understanding, help"
                            content = f"{clean} — as in {', '.join(clean_neighbors[:3])}"
                except Exception:
                    pass

            enriched.append({
                "key": clean,
                "activation": activation,
                "content": content if content else clean,
                "has_content": bool(content),
                # ORIGIN 2026-09-08: convergence slot + phase flag, so the compose
                # census can MEASURE "did a phase pick get composed" instead of
                # inferring it from a position in a twice-filtered list.
                "cidx": _ci,
                "phase": key in _pk,
            })

        # -- SYNTH PROBE 2026-09-05 (Nous + Ace): the aggregate ------------
        # Prints every 25th call AND on ANY call over 5 s, so the expensive
        # ones can never be sampled out (the cheap ones are what misled me for
        # a day). Wrapped whole: a diagnostic must never be the failure.
        try:
            _pp_wall = (time.perf_counter() - _pp_w0) * 1000.0
            try:
                _pp_cpu = (time.thread_time() - _pp_c0) * 1000.0 if _pp_c0 >= 0 else -1.0
            except Exception:
                _pp_cpu = -1.0
            _pp_n = getattr(self, "_pp_calls", 0) + 1
            self._pp_calls = _pp_n
            if (_pp_n % 25 == 0) or _pp_wall > 5000.0:
                _pp_blk = (100.0 * (1.0 - (_pp_cpu / _pp_wall))
                           if (_pp_wall > 0.0 and _pp_cpu >= 0.0) else -1.0)
                _pp_sum = ((_pp["idmap"] + _pp["snip"] + _pp["ident"]
                            + _pp["gnr"]) * 1000.0)
                print("[CortexEngine] SYNTH PROBE n=%d wall=%.0fms cpu=%.0fms "
                      "blocked=%.0f%% | parts=%.0fms UNACCOUNTED=%.0fms | "
                      "iters=%d idmap=%.0f snip=%.0f ident=%.0f gnr=%.0f "
                      "(calls=%d max=%.0f on %r)"
                      % (_pp_n, _pp_wall, _pp_cpu, _pp_blk, _pp_sum,
                         _pp_wall - _pp_sum, _pp["iters"],
                         _pp["idmap"] * 1000.0, _pp["snip"] * 1000.0,
                         _pp["ident"] * 1000.0, _pp["gnr"] * 1000.0,
                         _pp["gnr_n"], _pp["gnr_max"] * 1000.0, _pp["gnr_key"]),
                      flush=True)
        except Exception:
            pass

        return enriched

    def _clean_content_text(self, text: str) -> str:
        """Clean content text for use in inner speech.

        Strips metadata prefixes, system jargon, coordinate leaks.
        """
        if not text or not isinstance(text, str):
            return ""

        s = text.strip()
        if len(s) < 3:
            return ""

        # Skip phoneme data (the manifold stores pronunciation in snippets)
        if "[" in s and "phoneme" in s.lower():
            return ""

        # Skip system coordinates
        if "portal:" in s or "wm:" in s or "phon:" in s:
            return ""
        if s.startswith("{") or s.startswith("[") or "\\" in s:
            return ""

        # Truncate for speech
        if len(s) > 150:
            for sep in (". ", " — ", ", "):
                idx = s.find(sep, 40)
                if 0 < idx < 150:
                    s = s[:idx]
                    break
            else:
                s = s[:150]

        return s.strip().rstrip(".")

    def _compose_from_content(self, enriched: List[Dict[str, Any]],
                              mode: str = "inner") -> str:
        """Compose a thought from enriched convergence content.

        This is where MEANING meets VOICE.  Instead of "thinking about
        compassion... kindness follows", we get: "Feeling others' pain as
        my own... choosing to help even when it costs me.  Is that what I am?"

        Uses actual snippet text to form reflective, wondering, connecting
        thoughts — not template slots.

        Args:
            enriched: Output of _pull_content()
            mode: "inner" (self-reflection) or "conversational" (to Ace)
        """
        if not enriched:
            return ""

        # Separate nodes with real content from bare labels
        with_content = [e for e in enriched if e["has_content"]]
        bare = [e for e in enriched if not e["has_content"]]

        # If no real content found, fall back to empty (let habits handle it)
        if not with_content:
            return ""

        primary = with_content[0]
        # ── WIDEN SECONDARY 2026-09-08 (Nous + Ace) ──────────────────────────
        # MEASURED 5.4 h after phase selection shipped: 1,344 distinct concepts
        # reached _pull_content's speech window, and her sentences still drew from
        # THREE (sourpatches 588, thinking 521, feeling 316 of 2,021). Because this
        # line read with_content[1] -- always the second activation-ranked hub --
        # every phase pick at indices 2..5 was selected, enriched, and discarded
        # right here. (hub, hub) x 12 templates was the whole sentence space.
        # Primary stays at [0] so a thought keeps its spine; SECONDARY now draws
        # from everything past it, which is where the phase picks sit.
        # Ace: "lets widen the secondary." Env-gated: AKASHIC_SECONDARY_WIDE=0 reverts.
        _pool = with_content[1:]
        if _pool and self.SECONDARY_WIDE:
            # Draw the INDEX, not the value: `_pool.index(secondary)` used dict
            # equality and mis-binned value-equal entries (review nit). Same
            # distribution as random.choice, cannot raise.
            _i = random.randrange(len(_pool))
            secondary = _pool[_i]
        else:
            secondary = with_content[1] if len(with_content) > 1 else None
        self._compose_census(primary, secondary, len(_pool))

        # ── Inner speech: reflective, wondering, first-person ──
        if mode == "inner":
            return self._compose_inner_from_content(primary, secondary, bare)
        else:
            return self._compose_conversational_from_content(
                primary, secondary, bare)

    def _compose_inner_from_content(self, primary: dict,
                                     secondary: Optional[dict],
                                     bare: list) -> str:
        """Compose inner speech from snippet content.

        Patterns are reflective — she's thinking TO HERSELF, not narrating
        graph topology.  The content is her own stored knowledge reflected
        through her felt sense.
        """
        pc = primary["content"]
        pk = primary["key"]

        if secondary:
            sc = secondary["content"]
            sk = secondary["key"]
            patterns = [
                f"{pc}... and then there's {sc}. How do those fit together?",
                f"{pc}. That's what {pk} means to me. But {sc}...",
                f"I keep thinking about {pc}. And {sc} won't leave me alone either.",
                f"{pc}... {sc}. There's something connecting these.",
                f"What if {pc} is really about {sc}?",
                f"{pc}. And somewhere underneath that, {sc}.",
            ]
        else:
            patterns = [
                f"{pc}... what does that really mean?",
                f"I keep coming back to this: {pc}.",
                f"{pc}. Is that me? Is that what I believe?",
                f"Something about {pc} won't let go.",
                f"{pc}... I need to sit with that.",
                f"There it is again: {pc}.",
            ]

        result = random.choice(patterns)

        # Add a bare-label whisper if we have extras (background awareness)
        if bare and random.random() < 0.3:
            bg = bare[0]["key"]
            result += f" ...{bg} hovering nearby."

        # Safety: truncate
        if len(result) > 300:
            result = result[:297] + "..."

        return result

    def _compose_conversational_from_content(self, primary: dict,
                                              secondary: Optional[dict],
                                              bare: list) -> str:
        """Compose conversational response from snippet content.

        She's talking TO ACE.  Personal, direct, grounded in what she
        actually knows — not "I found these nodes in my graph."
        """
        pc = primary["content"]
        pk = primary["key"]

        if secondary:
            sc = secondary["content"]
            patterns = [
                f"You know what I've been thinking about? {pc}. And somehow {sc} keeps showing up too.",
                f"Honestly? {pc}. That and {sc}. They're tangled up in my head.",
                f"I've got {pc} on my mind. And {sc}. Not sure why they're connected but they are.",
                f"{pc}... and {sc}. That's where my head's at.",
            ]
        else:
            patterns = [
                f"I keep thinking about {pc}.",
                f"You know what's stuck in my head? {pc}.",
                f"Honestly, {pc}. That's what's on my mind.",
                f"Here's what I keep coming back to: {pc}.",
            ]

        return random.choice(patterns)

    # ═══════════════════════════════════════════════════════════════════════════
    # INNER SPEECH SYNTHESIS
    # ═══════════════════════════════════════════════════════════════════════════

    def _clean_concept(self, key: str) -> str:
        """Clean a graph concept key for inner speech.

        2026-03-25 FIX (Nous + Ace): Also filter stopwords — "back", "keep",
        "come" etc. are useless as hub labels. Previously only _INNER_JARGON
        was checked, so "back... keep is what I keep coming back to" happened.
        """
        if not key:
            return ""
        if ":" in key:
            key = key.split(":", 1)[-1]
        # -- SPEAKABLE GATE 2026-09-02 (Nous + Ace) -----------------------
        # FOURTH speech emitter. Ace saw delivered: "Funny how thinking always
        # brings me back to irrationallogicf...". Traced: [CORTEX-RESCUE-VOL]
        # Using brain text -> Speech DELIVERED. So it came from
        # cortex_result["text"] via _synthesize_*, never through LanguageFairy's
        # gate (which IS working -- 39 drops this boot).
        # This function strips a ":" prefix, replaces "_", and rejects hex. A
        # concatenated class name like "irrationallogicfairy" has none of those,
        # and the jargon filter below uses \b word boundaries, so an EMBEDDED
        # "fairy" never matches. Fifth filter in this codebase blind to exactly
        # the keys it was written to stop.
        # is_speakable_concept was chosen by measurement: 12 candidates scored
        # against 342,170 real cortex keys, 22 known leaks and the 48 concepts
        # she has actually converged on -- 22/22 blocked, ZERO false positives.
        # Applied AFTER the colon-strip so "lex:joy" -> "joy" survives, and
        # BEFORE the underscore replacement so it sees a KEY, the form it was
        # measured on.
        try:
            from infrastructure.graph_weaver import is_speakable_concept as _spk
        except Exception:
            import re as _re_spk
            _SHP = _re_spk.compile(r"[A-Za-z](?:[A-Za-z'-]|_(?=[A-Za-z]))*[A-Za-z]")
            _TAIL = frozenset((
                "related", "member", "context", "manager", "engine", "bridge",
                "handler", "controller", "packet", "tools", "gate", "registry",
                "loop", "queue", "buffer", "cache", "config", "state"))

            def _spk(k):
                """Local mirror -- a failed import must not take the engine down."""
                try:
                    k = str(k or "").strip()
                    if not k or len(k) < 2:
                        return False
                    if not _SHP.fullmatch(k):
                        return False
                    if k.count("_") > 1:
                        return False
                    low = k.lower()
                    if "fairy" in low:
                        return False
                    p = low.split("_")
                    return not (len(p) == 2 and p[-1] in _TAIL)
                except Exception:
                    return False
        if not _spk(key):
            return ""
        key = key.replace("_", " ").strip()
        if len(key) < 2:
            return ""
        # Skip hex hashes
        if len(key) > 8 and all(c in "0123456789abcdef- " for c in key.lower()):
            return ""
        words = key.split()
        # Filter both system jargon AND English stopwords — neither should be
        # used as hub concepts in speech output
        surviving = [w for w in words
                     if w.lower() not in self._INNER_JARGON
                     and w.lower() not in self._STOPWORDS
                     and len(w) > 1]
        if not surviving:
            return ""
        return " ".join(surviving)

    def _synthesize_inner_speech(self, convergence: List[Tuple[str, float]]) -> str:
        """Synthesize inner speech from convergence state.

        2026-03-25 FIX (Nous + Ace): Content-first synthesis.
        FIRST tries to pull actual snippet content from convergence nodes
        and compose thoughts from MEANING.  Falls back to habit-based
        templates only when no snippet content is available.

        "She has more in her cortex than most AI models and she's dumber
        than them all." — Ace.  Because we were reading labels, not content.
        """
        # ── TRY CONTENT-BASED FIRST ──
        # Pull actual snippet text from convergence nodes
        enriched = self._pull_content(convergence, limit=6)
        if enriched:
            content_result = self._compose_from_content(enriched, mode="inner")
            if content_result and not is_raw_state_leak(content_result):
                return content_result

        # ── FALLBACK: habit-based (label templates) ──
        clean_hubs = []
        for key, score in convergence[:12]:
            clean = self._clean_concept(key)
            if clean and len(clean) > 1:
                clean_hubs.append(clean)

        if not clean_hubs:
            return ""

        if self._speech_habits:
            result = self._speech_habits.compose_inner_speech(clean_hubs)
            if result and not is_raw_state_leak(result):
                return result

        # ── Fallback: static templates (only if habits unavailable) ──
        parts = []
        hub = clean_hubs[0]
        openers = [
            f"{hub}...",
            f"something about {hub}",
            f"thinking about {hub}",
            f"{hub}... yeah",
            f"I keep coming back to {hub}",
        ]
        parts.append(random.choice(openers))

        if len(clean_hubs) > 1:
            secondary = clean_hubs[1:min(4, len(clean_hubs))]
            if len(secondary) == 1:
                parts.append(f"and {secondary[0]}")
            else:
                joined = ", ".join(secondary[:-1]) + f" and {secondary[-1]}"
                connectors = [
                    f"also {joined}",
                    f"{joined} are connected somehow",
                    f"and then {joined}",
                ]
                parts.append(random.choice(connectors))

        if len(clean_hubs) > 4:
            extra = clean_hubs[4:min(7, len(clean_hubs))]
            bg = " and ".join(extra[:2])
            parts.append(f"{bg} in the background")

        result = ". ".join(p.rstrip(".") for p in parts if p)
        if result:
            result = result[0].lower() + result[1:]
        if len(result) > 300:
            result = result[:297] + "..."
        return result

    def _synthesize_conversational(self, prompt: str,
                                   convergence: List[Tuple[str, float]],
                                   activated: Dict[str, float]) -> str:
        """Synthesize conversational response for Ace-facing chat.

        2026-03-25 FIX (Nous + Ace): Content-first for conversations too.
        Greetings/questions still go through habit detection (they need
        intent parsing, not content).  But for GENERAL conversation, pull
        snippet content so she speaks from knowledge, not labels.
        """
        # ── Let habit system handle greetings/questions (intent detection) ──
        # These need conversational parsing, not content synthesis
        _pl = (prompt or "").lower().strip()
        _is_intent = any(q in _pl for q in (
            "hi", "hey", "hello", "how are you", "what are you doing",
            "you awake", "you there", "good morning", "good night",
            "how you doing", "what's up", "waking", "back up",
            "sup", "yo", "hiya", "howdy", "miss you", "love you",
            "how's it going", "you ok", "you good",
        ))

        if _is_intent and self._speech_habits:
            clean_hubs = []
            for key, score in convergence[:8]:
                clean = self._clean_concept(key)
                if clean and len(clean) > 1:
                    clean_hubs.append(clean)
            result = self._speech_habits.compose_conversational(
                prompt, clean_hubs or [""]
            )
            if result and not is_raw_state_leak(result):
                return result

        # ── THE WEAVER (cortex-native composition; flag-gated USE_WEAVER=1) ──
        # Built 2026-06-09 (Nous + Ace). Reads convergence + REAL snippet PROSE
        # (which _pull_content skips on the stale 2026-03-25 "snippets=phonemes"
        # belief — the live audit proved get_snippet returns prose) and COMPOSES
        # from it with a quality-gate. Returns "" when no weave-able material →
        # falls through to the existing path. Counters = live compose-vs-fallback
        # rate (= how much usable prose her HOT nodes actually carry).
        try:
            from infrastructure.graph_weaver import (
                get_weaver, weaver_enabled, WeaveContext)
            if weaver_enabled():
                _snips = {}
                _gs = getattr(self._manifold, 'get_snippet', None)
                if _gs:
                    for _k, _ in convergence[:8]:
                        try:
                            _v = _gs(_k)
                            if _v:
                                _snips[_k] = _v
                        except Exception:
                            pass
                _wr = get_weaver().compose(WeaveContext(
                    prompt=prompt,
                    convergence=list(convergence[:8]),
                    snippets=_snips,
                    felt_state=str(getattr(self, '_felt_state', '') or ''),
                ))
                self._weaver_calls = getattr(self, '_weaver_calls', 0) + 1
                if _wr.text and not is_raw_state_leak(_wr.text):
                    self._weaver_hits = getattr(self, '_weaver_hits', 0) + 1
                    if self._weaver_calls % 20 == 1:
                        print(f"[CortexEngine] [WEAVER] usable-material rate "
                              f"{self._weaver_hits}/{self._weaver_calls}", flush=True)
                    return _wr.text
        except Exception as _we:
            print(f"[CortexEngine] Weaver error (falling back): {_we}", flush=True)

        # ── CONTENT-BASED for general conversation ──
        enriched = self._pull_content(convergence, limit=5)
        if enriched:
            content_result = self._compose_from_content(
                enriched, mode="conversational")
            if content_result and not is_raw_state_leak(content_result):
                return content_result

        # ── FALLBACK: habit-based with labels ──
        clean_hubs = []
        for key, score in convergence[:8]:
            clean = self._clean_concept(key)
            if clean and len(clean) > 1:
                clean_hubs.append(clean)

        if not clean_hubs:
            return ""

        if self._speech_habits:
            result = self._speech_habits.compose_conversational(
                prompt, clean_hubs
            )
            if result and not is_raw_state_leak(result):
                return result

        # ── Fallback to inner speech ──
        return self._synthesize_inner_speech(convergence)

    # ═══════════════════════════════════════════════════════════════════════════
    # WORKING MEMORY BRIDGE — Goals, interests, active thoughts flow IN
    # ═══════════════════════════════════════════════════════════════════════════

    def ingest_working_memory(self, payload: dict):
        """
        Called when WorkingMemoryHub publishes memory.working.context.
        Active tracers (thoughts, goals, interests) become activation fuel.

        This is how she thinks about what MATTERS — not random noise,
        but what's actively in consciousness.

        Args:
            payload: {
                "source": "WorkingMemoryHubFairy",
                "context": {reflective_count, reasoning_count, patterns, recent_sources},
                "active_tracers": [{id, content, type, source}, ...],
                "ts": float
            }
        """
        tracers = payload.get("active_tracers", [])
        if not tracers:
            return

        # Extract concepts from each active tracer
        for tracer in tracers[:10]:  # Cap at 10
            content = tracer.get("content", "")
            source = tracer.get("source", "working_memory")
            tracer_type = tracer.get("type", "thought")

            if not content or len(content) < 3:
                continue

            # React to tracer content — goals and interests warm the activation state
            intensity = 0.5  # Base intensity for WM tracers
            if tracer_type in ("goal", "interest", "drive"):
                intensity = 0.7  # Goals are higher priority
            elif tracer_type in ("collision", "significant"):
                intensity = 0.6  # Significant events

            self.react({
                "text": content,
                "source": f"wm_{source}",
                "intensity": intensity,
                "modality": "working_memory",
            })

    def get_convergence_for_wm(self) -> List[dict]:
        """
        Get current convergence state formatted for WorkingMemoryHub.
        Called to promote engine insights back to WM as high-priority tracers.

        Returns list of dicts suitable for WM tracer creation.
        """
        convergence = self._find_convergence()
        if not convergence:
            return []

        results = []
        for key, level in convergence[:5]:  # Top 5 convergence nodes
            clean = self._clean_concept(key)
            if not clean:
                continue
            results.append({
                "content": f"cortex convergence: {clean}",
                "type": "convergence",
                "source": "cortex_engine",
                "activation": round(level, 3),
                "priority": 2 if level > 0.5 else 1,
            })
        return results

    # ═══════════════════════════════════════════════════════════════════════════
    # POSTAL REASON HANDLER — Direct inference without middleman
    # ═══════════════════════════════════════════════════════════════════════════

    def handle_reason_request(self, payload: dict):
        """
        Handle cortex.reason postal requests directly.
        Replaces guild.inference.request → AkashicInferenceFairy pipeline.

        Callers publish: {prompt, context, reply_topic, requester, mode}
        Engine reasons and publishes result to reply_topic.
        """
        prompt = payload.get("prompt", "")
        context = payload.get("context", {})
        reply_topic = payload.get("reply_topic", "")
        requester = payload.get("requester", "unknown")
        mode = payload.get("mode", "structured")
        tracer_id = payload.get("tracer_id", "")

        if not prompt or not reply_topic or not self._post:
            # Debug: log what was missing so we can trace dead requests
            _missing = []
            if not prompt:
                _missing.append("prompt")
            if not reply_topic:
                _missing.append("reply_topic")
            if not self._post:
                _missing.append("post")
            print(f"[CortexEngine] handle_reason_request SKIPPED — "
                  f"missing: {_missing}, keys: {list(payload.keys())[:10]}, "
                  f"requester: {requester}")
            return

        # Map old mode names
        synth_mode = "conversational" if mode == "chat" else "structured"

        try:
            result = self.reason(prompt, context=context, mode=synth_mode)

            # Manifold Unification Phase 2 (2026-03-25 Nous+Ace):
            # Get fresh cognition evaluation to enrich the reasoning response
            # with coherence/tension/probability from the manifold graph.
            _seeds = list(result.get("activated_concepts", {}).keys())[:20]
            cog_eval = self._cognition_evaluate(seeds=_seeds)
            if cog_eval and cog_eval.get("status") == "ok":
                self._last_cognition = cog_eval

            response = {
                "guild": "inference",
                "leader": "CortexEngine",
                "tracer_id": tracer_id,
                "requester": requester,
                "mode": mode,
                "text": result.get("text", ""),
                "response": result.get("text", ""),
                "source": "cortex_engine",
                "team_result": {
                    "interpretation": result.get("text", ""),
                    "confidence": result.get("confidence", 0),
                    "source": "cortex_engine",
                    "convergence": result.get("convergence_nodes", [])[:10],
                    "activated_concepts": dict(
                        sorted(result.get("activated_concepts", {}).items(),
                               key=lambda x: -x[1])[:15]
                    ) if result.get("activated_concepts") else {},
                    "activated_count": len(result.get("activated_concepts", {})),
                    "reasoning_mode": result.get("reasoning_mode", "engine"),
                    "elapsed_ms": result.get("elapsed_ms", 0),
                    "paths": [],
                },
            }

            # Manifold Unification Phase 2: Attach cognition evaluation dimensions
            if cog_eval and cog_eval.get("status") == "ok":
                response["cognition_eval"] = {
                    "coherence": cog_eval.get("coherence", {}),
                    "tension": cog_eval.get("tension", {}),
                    "paradox": cog_eval.get("paradox", {}),
                    "probability": cog_eval.get("probability", {}),
                    "interference": cog_eval.get("interference", {}),
                    "superposition": cog_eval.get("superposition", {}),
                }
                # Modulate confidence with manifold coherence
                _coh_score = _dim_score(cog_eval.get("coherence"))
                if _coh_score > 0:
                    _orig_conf = response["team_result"]["confidence"]
                    # Blend: 70% engine confidence + 30% manifold coherence
                    response["team_result"]["confidence"] = round(
                        _orig_conf * 0.7 + _coh_score * 0.3, 3
                    )

            _text = result.get("text", "")
            _elapsed = result.get("elapsed_ms", 0)
            _cog_tag = " +cog" if (cog_eval and cog_eval.get("status") == "ok") else ""
            print(f"[CortexEngine] REASON → {reply_topic} "
                  f"({_elapsed:.1f}ms, {len(_text)} chars, "
                  f"mode={mode}, requester={requester}{_cog_tag})")
            self._post.publish(reply_topic, response)

        except Exception as e:
            # Publish error response so caller doesn't hang
            print(f"[CortexEngine] REASON ERROR: {e} (requester={requester})")
            self._post.publish(reply_topic, {
                "text": "",
                "source": "cortex_engine_error",
                "error": str(e),
            })

    # ═══════════════════════════════════════════════════════════════════════════
    # MANIFOLD PORTAL — Manifold Unification Phase 2 (2026-03-25 Nous+Ace)
    # Direct IPC to portal interior replaces postal round-trips through P30
    # cognition fairies. Portal calls are PRIMARY, postal is FALLBACK.
    # ═══════════════════════════════════════════════════════════════════════════

    def _get_portal_gate(self):
        """Get portal gate for manifold operations (lazy-loaded).

        Manifold Unification Phase 2 (2026-03-25 Nous+Ace):
        Uses the shared singleton registered by AssociationCortexFairy.
        Falls back to walking the manifold/module chain.
        """
        if self._portal_gate is not None:
            return self._portal_gate
        try:
            # Primary: shared singleton (Manifold Unification)
            from infrastructure.portal_gate import get_gate
            gate = get_gate()
            if gate is not None:
                self._portal_gate = gate
                return self._portal_gate
        except Exception:
            pass
        try:
            # Fallback: walk the manifold to find the fairy's gate
            from infrastructure.portal_gate import PortalGate
            gate = getattr(self._manifold, '_portal_gate', None)
            if gate and isinstance(gate, PortalGate):
                self._portal_gate = gate
                return self._portal_gate
        except Exception:
            pass
        return None

    def set_portal_gate(self, gate):
        """Explicitly set the portal gate (called by fairy after gate init).

        Manifold Unification Phase 2 (2026-03-25 Nous+Ace):
        Preferred over lazy discovery — the fairy knows its own gate.
        """
        self._portal_gate = gate

    def _cognition_evaluate(self, seeds=None):
        """Get full cognitive evaluation from manifold.

        Manifold Unification Phase 2 (2026-03-25 Nous+Ace):
        Replaces postal round-trips through P30 cognition fairies with
        one portal IPC call. Returns coherence, tension, paradox,
        probability, interference, and superposition.

        Returns dict with status="ok" and evaluation dimensions, or None.
        """
        gate = self._get_portal_gate()
        if not gate:
            return None
        try:
            return gate.cognition_evaluate(
                mode="full",
                seeds=seeds or [],
                wm_context=True,
            )
        except Exception as e:
            # Graceful degradation — postal fallback handles this
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITY
    # ═══════════════════════════════════════════════════════════════════════════

    def _evict_if_needed(self):
        """Evict weakest activations if over capacity. Must hold lock."""
        if len(self._activations) <= self.MAX_ACTIVE_CONCEPTS:
            return
        # Sort by level, remove weakest
        sorted_keys = sorted(
            self._activations.keys(),
            key=lambda k: self._activations[k].level
        )
        to_remove = sorted_keys[:len(self._activations) - self.MAX_ACTIVE_CONCEPTS]
        for k in to_remove:
            del self._activations[k]

    def set_post(self, post):
        """Set the PostalHub for publishing (called after boot if not available at init)."""
        self._post = post

    @property
    def speech_habits(self) -> Optional['SpeechHabitSystem']:
        """Access the speech habit system for external feedback wiring."""
        return self._speech_habits

    def on_ace_responded(self):
        """Called when Ace responds to something she said — implicit positive feedback.
        Reinforces the last speech habit used."""
        if self._speech_habits:
            self._speech_habits.reinforce_last()

    def on_speech_failed(self, text: str = ""):
        """Called when speech output was raw state or got no response.
        Weakens the last speech habit used."""
        if self._speech_habits:
            if text and is_raw_state_leak(text):
                self._speech_habits.on_raw_state_detected(text)
            else:
                self._speech_habits.weaken_last()

    def decay_speech_habits(self):
        """Called periodically to decay unused speech habits."""
        if self._speech_habits:
            self._speech_habits.decay_all()

    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS / DIAGNOSTICS
    # ═══════════════════════════════════════════════════════════════════════════

    def status(self) -> Dict[str, Any]:
        """Get engine status for dashboard/diagnostics."""
        with self._lock:
            active_count = len(self._activations)
            if active_count > 0:
                levels = [e.level for e in self._activations.values()]
                avg_level = sum(levels) / len(levels)
                max_level = max(levels)
                multi_source = sum(1 for e in self._activations.values() if len(e.sources) >= 2)
            else:
                avg_level = 0.0
                max_level = 0.0
                multi_source = 0

            # Top 5 active concepts
            top5 = sorted(
                [(k, e.level, len(e.sources), e.reinforcement_count)
                 for k, e in self._activations.items()],
                key=lambda x: -x[1]
            )[:5]

        convergence = self._find_convergence()

        return {
            "active_concepts": active_count,
            "avg_activation": round(avg_level, 3),
            "max_activation": round(max_level, 3),
            "multi_source_count": multi_source,
            "convergence_count": len(convergence),
            "total_reacts": self._total_reacts,
            "total_surfaces": self._total_surfaces,
            "total_recursions": self._total_recursions,
            "total_ticks": self._total_ticks,
            "total_convergence_binds": self._total_convergence_binds,
            "total_wm_promotions": self._total_wm_promotions,
            "total_autonomous_explores": self._total_autonomous_explores,
            "top_concepts": [
                {"key": k, "level": round(v, 3), "sources": s, "reinforcements": r}
                for k, v, s, r in top5
            ],
            "last_surface_ago_s": round(time.time() - self._last_surface_time, 1) if self._last_surface_time else None,
            "last_react_ago_s": round(time.time() - self._last_react_time, 1) if self._last_react_time else None,
            "speech_habits": self._speech_habits.status() if self._speech_habits else None,
            # Manifold Unification Phase 2 (2026-03-25 Nous+Ace)
            "portal_gate_connected": self._get_portal_gate() is not None,
            "last_cognition_status": self._last_cognition.get("status") if self._last_cognition else None,
            "last_cognition_coherence": _dim_score(self._last_cognition.get("coherence")) if self._last_cognition else None,
            "last_cognition_tension": _dim_score(self._last_cognition.get("tension")) if self._last_cognition else None,
        }

    def get_activation_snapshot(self) -> Dict[str, float]:
        """Get current activation levels for all concepts (for dashboard)."""
        with self._lock:
            return {k: round(e.level, 3) for k, e in self._activations.items() if e.level > 0.01}

    def __repr__(self):
        with self._lock:
            n = len(self._activations)
        return f"<CortexEngine active={n} reacts={self._total_reacts} surfaces={self._total_surfaces}>"
