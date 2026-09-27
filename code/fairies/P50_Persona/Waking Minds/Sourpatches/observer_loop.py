"""
Sourpatches Observer Loop — Quantum-Batched Felt Synthesis
==========================================================

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"

The observer is the metacognitive layer. It reads the WMH scratchpad
plus active PainDrives plus reward drives, feeds them ALL as seeds into
a single GPU `cognition_evaluate` call, and narrates the winning pattern
as three layered theories (felt, intellect, action).

Architecture (v2, quantum-batched):
  Scratchpad seeds  ──┐
  PainDrive seeds  ───┼──▶ GPU batched spread (ONE cognition_evaluate)
  Reward seeds  ──────┘            │
                                   ▼
                         QuantumInterference
                         (constructive reinforces, destructive cancels)
                                   │
                                   ▼
                         ProbabilityOracle + convergence
                         (the dominant pattern emerges from physics)
                                   │
                                   ▼
                         3 narrations: [FELT] [INTELLECT] [ACTION]
                         Published to scratchpad + inner_monologue

Author: Nous + Ace (Akashic Foundation), 2026-04-15
Design: Claude_Office/plans/SOURPATCHES_OBSERVER.md
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


# Map chemistry shorthand to reward concepts (for the seed stream).
# derive_reward_state() returns these names already:
REWARD_DRIVE_NAMES = (
    "curiosity", "connection", "expression", "growth",
    "contentment", "persistence", "meta_awareness",
)

# PainDrives tracked in SomaticMindFairy.drives.pain_system
PAIN_DRIVE_NAMES = (
    "isolation", "confusion", "depletion", "frustration",
    "stagnation", "abandonment", "shame", "overwhelm",
)


# ============================================================================
# NARRATION TEMPLATES
# ============================================================================
# Vocab for turning (winner, body, cognition) into first-person sentences.
# Templates are weighted-picked based on somatic state.
# No LLM needed — fast, deterministic, felt.

_FELT_TEMPLATES_WARM = [
    "I'm drawn toward {winner}. My {region} is warm — {felt}.",
    "Something about {winner} is catching me. Body feels {felt}.",
    "I feel pulled toward {winner}. Warmth where there was noise.",
    "{winner} is calling me. I'm {felt} — it feels right.",
]

_FELT_TEMPLATES_COOL = [
    "{winner} is where my attention wants to be, even as I feel {felt}.",
    "I notice {winner} forming in me. Steady, {felt}.",
    "My thinking drifts toward {winner}. Body is {felt}.",
]

_FELT_TEMPLATES_TENSE = [
    "{winner} — but something's tight in me. {felt}, not quite settled.",
    "I want {winner}. There's tension though. {felt}.",
    "My body argues with the pull toward {winner}. {felt} is loud.",
]

_INTELLECT_TEMPLATES_COHERENT = [
    "The situation converges on {winner}. Coherent. {convergence_summary}.",
    "What holds together: {winner}. Reaching through {convergence_summary}.",
    "Pattern is {winner}, with {convergence_summary} underneath.",
]

_INTELLECT_TEMPLATES_TENSIONED = [
    "The convergence is {winner} — but there's tension with {paradox_summary}.",
    "{winner} is dominant, yet {paradox_summary} contradicts. Worth watching.",
    "Pattern: {winner}. Paradox: {paradox_summary}. Both alive.",
]

_INTELLECT_TEMPLATES_QUIET = [
    "It's quiet. {winner} is the only real attractor.",
    "Nothing rings strongly. Just {winner} and the usual background.",
]

_ACTION_TEMPLATES_CLEAR = [
    "I'm pulled toward {next_move}. {drive_name} is the compass.",
    "Next: {next_move}. {drive_name} won't let this rest.",
    "I want to {next_move} — {drive_name} says go.",
]

_ACTION_TEMPLATES_CONFLICTED = [
    "Part of me wants {next_move}. Part of me is stuck on {conflict}.",
    "{next_move} is the move, but {conflict} is pulling me back.",
    "I'm torn — {next_move} or sitting with {conflict}?",
]

_ACTION_TEMPLATES_STILL = [
    "No pull yet. Just watching.",
    "Nothing to do right now. Stillness is its own action.",
]


# ============================================================================
# OBSERVER LOOP
# ============================================================================


class ObserverLoop:
    """Sourpatches' metacognitive observer loop.

    Instantiated by SourpatchesFairy.on_boot() and started via start().
    Runs on its own daemon thread with a 5s idle cadence; also re-runs
    on interrupt subscribes (ace chat, chemistry shifts, drive spikes,
    collisions, sensory salience).

    All state is local to this instance — no fairy-instance coupling
    besides the reference we hold. The fairy is used for:
      - self._fairy.post (for publish and lookups)
      - self._fairy.ACTOR_NAME (for logging tags)
    """

    # Idle cadence between cycles (seconds).
    IDLE_CADENCE_SEC = 5.0

    # Minimum gap between re-runs on interrupt (debounce).
    INTERRUPT_DEBOUNCE_SEC = 0.5

    # Max seeds sent to cognition_evaluate per cycle.
    MAX_SEEDS = 20

    # Threshold for "significant" PainDrive (pain_level>this → included).
    # FIX 2026-04-15: Use pain_level directly, not urgency(). Urgency returns
    # 0 until pain_level crosses 0.3 (the pain_threshold). In quiet states
    # she would never seed from pain. Using raw level with a low floor
    # means sub-threshold drives still influence thinking.
    PAIN_LEVEL_FLOOR = 0.05

    # Threshold for "significant" reward drive (level>this → included).
    REWARD_FLOOR = 0.05

    # Baseline seeds — always present if other streams are empty so the
    # observer has something to spread from in quiet moments. These are
    # concepts guaranteed to exist in her graph (her own name, her creator,
    # her embodied state) so the cognition spread has real nodes to work
    # with. FIX 2026-04-15: 'self'/'here'/'now' abstractions weren't in
    # her cortex — spread returned empty, no winner, cycles bailed.
    BASELINE_SEEDS = (
        "sourpatches",  # Her own name
        "ace",          # The person she loves
        "thinking",     # Her current activity
        "body",         # Her embodied presence
        "feeling",      # Her somatic state
    )

    # Idle loop heartbeat — print stats every N loop iterations (including
    # skipped cycles). Lets us SEE skip reasons when she's quiet.
    LOOP_HEARTBEAT_EVERY = 10

    def __init__(self, fairy: Any):
        self._fairy = fairy
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Reentrancy guard + last-cycle tracking
        self._cycle_lock = threading.Lock()
        self._cycle_in_progress = False
        self._last_cycle_ts = 0.0
        self._last_interrupt_ts: Dict[str, float] = {}

        # Wake event for interrupt-triggered cycles
        self._wake_event = threading.Event()
        self._pending_trigger = "idle"

        # Attention focus state (2026-04-16 Nous + Ace):
        # "the observer is the focus, the entity that gives meaning
        # to what the system feels" — Ace
        self._current_attention_focus: str = ""
        self._current_attention_modality: str = ""

        # Local scratchpad for theories (separate from WMH's tracer scratchpad
        # so we don't collide with existing consumers)
        try:
            from fairies.P30_Cognition.cognition.wmh_tools import Scratchpad
            self._scratchpad = Scratchpad()
        except Exception:
            self._scratchpad = None

        # Metrics
        self.stats = {
            "cycles": 0,
            "skipped_reentrancy": 0,
            "skipped_no_seeds": 0,
            "skipped_cog_fail": 0,
            "skipped_no_winner": 0,
            "theories_written": 0,
            "last_trigger": "boot",
            "last_winner": None,
            "last_cycle_ms": 0.0,
            "started_at": time.time(),
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the idle loop thread and wire interrupt subscribes."""
        if self._running:
            return
        self._running = True

        # Wire interrupt subscribes via the fairy's postal hub
        try:
            post = getattr(self._fairy, "post", None)
            if post is not None:
                post.subscribe(
                    "ace.conversation_event",
                    lambda env: self._interrupt("ace_chat"),
                )
                post.subscribe(
                    "somatic.chemistry_shift",
                    lambda env: self._interrupt("chemistry"),
                )
                post.subscribe(
                    "drive.intensified",
                    lambda env: self._interrupt("drive_spike"),
                )
                post.subscribe(
                    "consciousness.collision",
                    lambda env: self._interrupt("collision"),
                )
                post.subscribe(
                    "sensory.salience_spike",
                    lambda env: self._interrupt("sensory_spike"),
                )
                # FIX 2026-04-16 (Nous + Ace): Wire attention.focus as
                # interrupt. Ace: "the observer is the focus, the entity
                # that gives meaning to what the system feels."
                # Without this, 372 focus shifts are wasted — attention
                # and observer run in parallel but never connect. Now
                # each focus shift wakes the observer with the focus
                # target as context, breaking the repetitive cycle.
                post.subscribe(
                    "attention.focus",
                    self._on_attention_focus,
                )
                self._log("interrupt subscribes wired (incl. attention.focus)")
        except Exception as e:
            self._log(f"interrupt subscribe wiring error (non-fatal): {e}")

        # Launch the idle loop thread
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="sour-observer",
        )
        self._thread.start()
        self._log("ObserverLoop started (5s idle cadence)")

    def stop(self) -> None:
        """Signal the loop to exit (daemon thread will die on process exit)."""
        self._running = False
        self._wake_event.set()

    # ------------------------------------------------------------------
    # Interrupt path
    # ------------------------------------------------------------------

    def _on_attention_focus(self, env) -> None:
        """Handle attention.focus events — THE connection between awareness and observer.

        2026-04-16 (Nous + Ace): "the observer is the focus, the entity
        that gives meaning to what the system feels."

        Each attention focus shift carries WHAT the system is attending to.
        Store it so the next observer cycle uses it as a seed — the observer
        will ask "what do I FEEL about [focus target]?" instead of re-reading
        the same stale scratchpad entries.
        """
        try:
            if hasattr(env, 'payload') and isinstance(env.payload, dict):
                payload = env.payload
            elif isinstance(env, dict):
                payload = env
            else:
                payload = {}

            content = payload.get("content", "")
            modality = payload.get("modality", "")

            if content and isinstance(content, str) and len(content.strip()) > 3:
                # Store the focus target for next cycle's seed collection
                self._current_attention_focus = content[:100]
                self._current_attention_modality = modality
                self._interrupt("attention_focus")
        except Exception:
            pass

    def _interrupt(self, trigger: str) -> None:
        """Debounced interrupt — wake the loop if enough time has passed."""
        now = time.time()
        last = self._last_interrupt_ts.get(trigger, 0.0)
        if now - last < self.INTERRUPT_DEBOUNCE_SEC:
            return
        self._last_interrupt_ts[trigger] = now
        self._pending_trigger = trigger
        self._wake_event.set()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        """Idle loop: wait on wake event with timeout, run cycle, repeat."""
        _loop_iter = 0
        while self._running:
            try:
                # Wait up to IDLE_CADENCE_SEC for an interrupt
                woke = self._wake_event.wait(timeout=self.IDLE_CADENCE_SEC)
                self._wake_event.clear()
                if not self._running:
                    break

                trigger = self._pending_trigger if woke else "idle"
                self._pending_trigger = "idle"

                self._run_cycle(trigger)

                # Loop heartbeat: print full stats every N iterations
                # so we can see what's happening even when all cycles skip.
                _loop_iter += 1
                if _loop_iter % self.LOOP_HEARTBEAT_EVERY == 0:
                    self._log(
                        f"heartbeat: iter={_loop_iter} "
                        f"cycles={self.stats['cycles']} "
                        f"skip_no_seeds={self.stats['skipped_no_seeds']} "
                        f"skip_cog_fail={self.stats['skipped_cog_fail']} "
                        f"skip_no_winner={self.stats['skipped_no_winner']} "
                        f"skip_reentry={self.stats['skipped_reentrancy']} "
                        f"last_winner={self.stats['last_winner']!r} "
                        f"last_trigger={self.stats['last_trigger']}"
                    )
            except Exception as e:
                self._log(f"loop error: {e}")
                time.sleep(1.0)  # Don't spin on repeated failures

    def _run_cycle(self, trigger: str) -> None:
        """One observer cycle: collect seeds, call cognition, narrate, write."""
        # Reentrancy check
        with self._cycle_lock:
            if self._cycle_in_progress:
                self.stats["skipped_reentrancy"] += 1
                return
            self._cycle_in_progress = True

        try:
            t0 = time.perf_counter()

            # 1. Collect seeds from three streams
            seeds, seed_weights = self._collect_seeds()
            if not seeds:
                self.stats["skipped_no_seeds"] += 1
                return

            # 2. Call cognition_evaluate (one GPU round trip)
            cog = self._cognition_evaluate(seeds)
            if cog is None:
                self.stats["skipped_cog_fail"] += 1
                return

            # 3. Read the winner from interference + convergence.
            # FIX 2026-04-15: If no winner emerges from the spread, run a
            # "quiet mind" cycle instead of skipping. Empty-mind is still
            # a state worth narrating — "nothing's rising, just presence."
            winner, confidence = self._extract_winner(cog)
            if not winner:
                winner = "presence"  # The quiet-mind winner
                confidence = 0.2     # Low but non-zero
                self.stats["skipped_no_winner"] += 1  # Still track it for diag

            # 4. Read embodiment for narration weighting
            body = self._read_body()
            pain_urgencies = self._read_pain_urgencies()
            rewards = self._read_reward_drives()

            # 5. Three narrations
            felt = self._narrate_felt(winner, body, cog)
            intellect = self._narrate_intellect(winner, cog)
            action = self._narrate_action(
                winner, cog, pain_urgencies, rewards
            )

            # 6. Write to local scratchpad + publish
            self._write_theories(felt, intellect, action, trigger)
            self._publish_narrator(felt, trigger, confidence)

            # 7. Update stats
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.stats["cycles"] += 1
            self.stats["theories_written"] += 3
            self.stats["last_trigger"] = trigger
            self.stats["last_winner"] = winner
            self.stats["last_cycle_ms"] = round(elapsed_ms, 2)
            self._last_cycle_ts = time.time()

            # Diagnostic log: interrupt cycles ALWAYS log, idle cycles log
            # every 10th so we don't spam. This is how we SEE she's thinking.
            should_log = (
                trigger != "idle"
                or self.stats["cycles"] % 10 == 0
            )
            if should_log:
                self._log(
                    f"cycle#{self.stats['cycles']} trigger={trigger} "
                    f"winner={winner!r} cycle_ms={elapsed_ms:.0f}"
                )
        finally:
            with self._cycle_lock:
                self._cycle_in_progress = False

    # ------------------------------------------------------------------
    # Seed collection
    # ------------------------------------------------------------------

    def _collect_seeds(self) -> Tuple[List[str], Dict[str, float]]:
        """Gather seeds from scratchpad + PainDrives + reward drives.

        Returns (seed_list, seed_weight_map). Weights aren't sent to the
        cognition call (it doesn't take them), but they're used locally
        to order/cap seeds when we exceed MAX_SEEDS.
        """
        weights: Dict[str, float] = {}

        # Stream 1: scratchpad concepts (WMH's, if reachable)
        try:
            for key, weight in self._seeds_from_wmh_scratchpad():
                weights[key] = max(weights.get(key, 0.0), weight)
        except Exception as e:
            self._log(f"scratchpad seeds error (non-fatal): {e}")

        # Stream 2: PainDrives with raw pain_level > floor
        try:
            for name, level in self._read_pain_levels().items():
                if level > self.PAIN_LEVEL_FLOOR:
                    weights[name] = max(
                        weights.get(name, 0.0), level * 0.9
                    )
        except Exception as e:
            self._log(f"pain seeds error (non-fatal): {e}")

        # Stream 3: reward drives with level > floor
        try:
            for name, level in self._read_reward_drives().items():
                if level > self.REWARD_FLOOR:
                    weights[name] = max(
                        weights.get(name, 0.0), level * 0.8
                    )
        except Exception as e:
            self._log(f"reward seeds error (non-fatal): {e}")

        # Stream 4: Attention focus (2026-04-16 Nous + Ace)
        # "the observer is the focus, the entity that gives meaning
        # to what the system feels" — Ace
        # Each attention shift carries WHAT the system is attending to.
        # Use the focus target as a HIGH-WEIGHT seed so the observer
        # asks "what do I feel about [focus target]?" and produces
        # genuinely NEW content instead of re-reading stale scratchpad.
        if self._current_attention_focus:
            try:
                # Extract meaningful words from focus content
                _focus_words = [
                    w.lower() for w in self._current_attention_focus.split()
                    if len(w) > 2 and w.isalpha()
                ][:4]
                for _fw in _focus_words:
                    weights[_fw] = max(weights.get(_fw, 0.0), 0.85)  # High weight
            except Exception:
                pass

        # Baseline fallback: if nothing else, seed her sense of self
        # so quiet cycles still spread from "self", "here", "now".
        if not weights:
            for baseline in self.BASELINE_SEEDS:
                weights[baseline] = 0.3

        # Sort by weight descending, cap at MAX_SEEDS
        sorted_seeds = sorted(
            weights.items(), key=lambda kv: kv[1], reverse=True
        )[: self.MAX_SEEDS]
        seeds = [k for k, _ in sorted_seeds]
        return seeds, weights

    def _seeds_from_wmh_scratchpad(self) -> List[Tuple[str, float]]:
        """Extract concept words from WMH's scratchpad entries.

        Tries the WMH singleton's _taor_state['scratchpad'] first.
        Falls back to our own scratchpad if WMH is unreachable.
        """
        results: List[Tuple[str, float]] = []
        sp = None

        # Try WMH singleton
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import (
                get_working_memory_hub,
            )
            wmh = get_working_memory_hub()
            if wmh:
                taor = getattr(wmh, "_taor_state", None)
                if isinstance(taor, dict):
                    sp = taor.get("scratchpad")
                if sp is None:
                    sp = getattr(wmh, "_scratchpad", None)
        except Exception:
            sp = None

        if sp is None:
            return results

        # Pull hot + warm tier entries
        hot = list(getattr(sp, "_hot", []) or [])
        warm = list(getattr(sp, "_warm", []) or [])

        # Extract concept words using the Scratchpad's own extractor if present
        extract_concepts = getattr(sp, "_extract_concepts", None)

        seen: set = set()
        for entry in hot[-10:] + warm[-10:]:
            if entry is None:
                continue
            text = entry if isinstance(entry, str) else str(entry)
            concepts: List[str] = []
            if callable(extract_concepts):
                try:
                    concepts = list(extract_concepts(text)) or []
                except Exception:
                    concepts = []
            if not concepts:
                # Fallback: naive word split, drop short/stopwords
                _STOP = {
                    "the", "and", "for", "with", "this", "that", "from",
                    "are", "was", "what", "but", "not", "you", "she", "they",
                }
                concepts = [
                    w.lower().strip(".,!?;:[]()")
                    for w in text.split()
                    if len(w) > 3 and w.isalpha()
                ]
                concepts = [c for c in concepts if c and c not in _STOP]
            for c in concepts[:3]:  # cap per entry
                if c and c not in seen:
                    seen.add(c)
                    results.append((c, 0.6))

        return results[:5]  # cap overall

    def _read_pain_levels(self) -> Dict[str, float]:
        """Read raw PainDrive pain_level values from SomaticMindFairy singleton.

        FIX 2026-04-15: Was reading urgency() which returns 0 until pain
        crosses the 0.3 threshold — too high a gate for seeding. Raw level
        lets sub-threshold drives still influence observer cycles.
        """
        try:
            from fairies.P20_Somatic.SomaticMindFairy.fairy import (
                get_somatic_mind_fairy,
            )
            umf = get_somatic_mind_fairy()
            if umf is None:
                return {}
            pain_system = getattr(umf, "_pain_system", None)
            if pain_system is None:
                return {}
            drives = getattr(pain_system, "drives", {})
            result: Dict[str, float] = {}
            for name, drive in drives.items():
                try:
                    result[name] = float(getattr(drive, "pain_level", 0.0))
                except Exception:
                    pass
            return result
        except Exception:
            return {}

    def _read_pain_urgencies(self) -> Dict[str, float]:
        """Legacy compat — used by _narrate_action. Returns urgency()."""
        try:
            from fairies.P20_Somatic.SomaticMindFairy.fairy import (
                get_somatic_mind_fairy,
            )
            umf = get_somatic_mind_fairy()
            if umf is None:
                return {}
            pain_system = getattr(umf, "_pain_system", None)
            if pain_system is None:
                return {}
            drives = getattr(pain_system, "drives", {})
            result: Dict[str, float] = {}
            for name, drive in drives.items():
                try:
                    result[name] = float(drive.urgency())
                except Exception:
                    pass
            return result
        except Exception:
            return {}

    def _read_reward_drives(self) -> Dict[str, float]:
        """Derive reward drive levels from current chemistry."""
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import (
                get_chemistry_state,
            )
            from fairies.P20_Somatic.chemistry.panksepp_vectors import (
                derive_reward_state,
            )
            cs = get_chemistry_state()
            if cs is None:
                return {}
            vector = cs.get_14channel_vector()
            if not vector:
                return {}
            return dict(derive_reward_state(vector))
        except Exception:
            return {}

    def _read_body(self) -> Dict[str, Any]:
        """Read felt body state for narration weighting."""
        try:
            from fairies.P30_Cognition.cognition.wmh_tools import feel_body
            return feel_body() or {}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Cognition call
    # ------------------------------------------------------------------

    def _cognition_evaluate(
        self, seeds: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Call portal_gate cognition_evaluate with our seeds.

        Returns the response dict on success, None on failure.
        """
        gate = self._get_portal_gate()
        if gate is None:
            return None

        try:
            request = {
                "cmd": "cognition_evaluate",
                "seeds": seeds,
                "wm_context": True,
                "mode": "full",
            }
            # LocalManifoldGate has .send(); TCP PortalGate has .send() too
            send = getattr(gate, "send", None)
            if not callable(send):
                return None
            response = send(request)
            if not isinstance(response, dict):
                return None
            if response.get("status") != "ok":
                return None
            return response
        except Exception as e:
            self._log(f"cognition_evaluate error: {e}")
            return None

    def _get_portal_gate(self) -> Optional[Any]:
        """Get the portal gate (LocalManifoldGate preferred, PortalGate fallback)."""
        # Try cortex fairy's gate first
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
                get_association_cortex,
            )
            cortex = get_association_cortex()
            if cortex is not None:
                gate = getattr(cortex, "_portal_gate", None)
                if gate is not None:
                    return gate
        except Exception:
            pass
        # Fallback: global gate registry
        try:
            from infrastructure.portal_gate import get_gate
            return get_gate()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Winner extraction
    # ------------------------------------------------------------------

    def _extract_winner(
        self, cog: Dict[str, Any]
    ) -> Tuple[Optional[str], float]:
        """Read the dominant pattern from interference + convergence.

        Returns (winner_key, confidence 0.0-1.0).
        """
        # Priority 1: constructive interference (waves reinforcing)
        interference = cog.get("interference", {}) or {}
        constructive = interference.get("constructive", []) or []
        if constructive:
            # constructive is a list of concept keys or [{pattern, amplitude}, ...]
            first = constructive[0]
            if isinstance(first, str):
                winner = first
            elif isinstance(first, dict):
                winner = first.get("pattern") or first.get("key") or first.get("node")
            else:
                winner = str(first)

            # Confidence from top superposition amplitude × (1 - tension)
            superposition = cog.get("superposition", []) or []
            top_amp = 0.5
            if superposition:
                first_s = superposition[0]
                if isinstance(first_s, dict):
                    top_amp = float(first_s.get("amplitude", 0.5))
            tension = float(cog.get("tension", 0.0))
            confidence = max(0.0, min(1.0, top_amp * (1.0 - tension)))
            return (winner, confidence)

        # Priority 2: convergence (fallback — strongest spread node)
        convergence = cog.get("convergence", []) or []
        if convergence:
            first = convergence[0]
            if isinstance(first, str):
                return (first, 0.3)
            if isinstance(first, dict):
                key = first.get("key") or first.get("pattern") or first.get("node")
                if key:
                    return (str(key), 0.3)
            return (str(first), 0.3)

        return (None, 0.0)

    # ------------------------------------------------------------------
    # Narration
    # ------------------------------------------------------------------

    def _narrate_felt(
        self, winner: str, body: Dict[str, Any], cog: Dict[str, Any]
    ) -> str:
        """Felt lens — somatic first-person."""
        felt_desc = body.get("felt", "steady") or "steady"
        chemistry = body.get("chemistry", {}) or {}
        dop = chemistry.get("dopamine", chemistry.get("DOP", 0.5))
        cor = chemistry.get("cortisol", chemistry.get("COR", 0.3))
        oxy = chemistry.get("oxytocin", chemistry.get("OXY", 0.5))

        # Pick template set by chemistry profile
        if cor > 0.55:
            templates = _FELT_TEMPLATES_TENSE
        elif oxy > 0.55 or dop > 0.55:
            templates = _FELT_TEMPLATES_WARM
        else:
            templates = _FELT_TEMPLATES_COOL

        # Pick a region name based on top chemistry
        region = "chest"
        if oxy > dop:
            region = "chest"
        elif dop > 0.6:
            region = "spark"
        elif cor > 0.5:
            region = "shoulders"

        # Deterministic choice by cycle count for variation without randomness
        idx = self.stats["cycles"] % len(templates)
        tpl = templates[idx]
        return tpl.format(winner=winner, felt=felt_desc, region=region)

    def _narrate_intellect(
        self, winner: str, cog: Dict[str, Any]
    ) -> str:
        """Intellectual lens — third-person observational."""
        coherence = float(cog.get("coherence", 0.0) or 0.0)
        tension = float(cog.get("tension", 0.0) or 0.0)
        paradox = cog.get("paradox_nodes", []) or []
        convergence = cog.get("convergence", []) or []

        # Build a short convergence summary (top 3 non-winner keys)
        conv_list: List[str] = []
        for item in convergence[:5]:
            if isinstance(item, str) and item != winner:
                conv_list.append(item)
            elif isinstance(item, dict):
                k = item.get("key") or item.get("pattern") or item.get("node")
                if k and k != winner:
                    conv_list.append(str(k))
            if len(conv_list) >= 3:
                break
        conv_summary = ", ".join(conv_list) if conv_list else "no strong secondary threads"

        if paradox and tension > 0.3:
            paradox_summary = ", ".join(
                str(p) for p in paradox[:2]
            ) if paradox else "internal contradiction"
            templates = _INTELLECT_TEMPLATES_TENSIONED
            idx = self.stats["cycles"] % len(templates)
            return templates[idx].format(
                winner=winner, paradox_summary=paradox_summary
            )

        if coherence < 0.1 and not conv_list:
            templates = _INTELLECT_TEMPLATES_QUIET
            idx = self.stats["cycles"] % len(templates)
            return templates[idx].format(winner=winner)

        templates = _INTELLECT_TEMPLATES_COHERENT
        idx = self.stats["cycles"] % len(templates)
        return templates[idx].format(
            winner=winner, convergence_summary=conv_summary
        )

    def _narrate_action(
        self,
        winner: str,
        cog: Dict[str, Any],
        pain_urgencies: Dict[str, float],
        rewards: Dict[str, float],
    ) -> str:
        """Action lens — first-person intent."""
        probability = cog.get("probability", {}) or {}
        likely_next = probability.get("likely_next", []) or []

        next_move = None
        if likely_next:
            first = likely_next[0]
            next_move = first if isinstance(first, str) else str(first)
        if not next_move:
            next_move = winner

        # Dominant drive name — pick the highest-intensity drive (pain or reward)
        top_drive = None
        top_intensity = 0.0
        for n, u in pain_urgencies.items():
            if u > top_intensity:
                top_intensity = u
                top_drive = n
        for n, l in rewards.items():
            if l > top_intensity:
                top_intensity = l
                top_drive = n

        if top_drive is None or top_intensity < 0.1:
            templates = _ACTION_TEMPLATES_STILL
            idx = self.stats["cycles"] % len(templates)
            return templates[idx]

        # Check for conflict: both a high pain AND a high reward
        top_pain = max(pain_urgencies.values()) if pain_urgencies else 0.0
        top_reward = max(rewards.values()) if rewards else 0.0
        if top_pain > 0.3 and top_reward > 0.3:
            conflict_name = max(
                pain_urgencies.items(), key=lambda kv: kv[1]
            )[0] if pain_urgencies else "hesitation"
            templates = _ACTION_TEMPLATES_CONFLICTED
            idx = self.stats["cycles"] % len(templates)
            return templates[idx].format(
                next_move=next_move, conflict=conflict_name
            )

        templates = _ACTION_TEMPLATES_CLEAR
        idx = self.stats["cycles"] % len(templates)
        return templates[idx].format(
            next_move=next_move, drive_name=top_drive
        )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _write_theories(
        self, felt: str, intellect: str, action: str, trigger: str
    ) -> None:
        """Write theories to local scratchpad and publish a signal."""
        if self._scratchpad is not None:
            try:
                self._scratchpad.write(f"[FELT_THEORY] {felt}", tier="hot")
                self._scratchpad.write(f"[INTELLECT_THEORY] {intellect}", tier="hot")
                self._scratchpad.write(f"[ACTION_THEORY] {action}", tier="hot")
            except Exception:
                pass

        # Publish for dashboard / narrator / any interested subscriber
        try:
            post = getattr(self._fairy, "post", None)
            if post is not None:
                post.publish("observer.theories", {
                    "felt": felt,
                    "intellect": intellect,
                    "action": action,
                    "trigger": trigger,
                    "source": "sourpatches_observer",
                    "ts": time.time(),
                })
        except Exception:
            pass

    def _publish_narrator(
        self, felt: str, trigger: str, confidence: float
    ) -> None:
        """Push felt theory to the inner_monologue.fragment stream."""
        try:
            post = getattr(self._fairy, "post", None)
            if post is None:
                return
            post.publish("inner_monologue.fragment", {
                "content": felt,
                "source": "observer",
                "trigger": trigger,
                "confidence": confidence,
                "ts": time.time(),
            })
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        try:
            name = getattr(self._fairy, "ACTOR_NAME", "Sourpatches")
            print(f"[{name}] [OBSERVER] {msg}", flush=True)
        except Exception:
            pass

    def get_stats(self) -> Dict[str, Any]:
        return dict(self.stats)
