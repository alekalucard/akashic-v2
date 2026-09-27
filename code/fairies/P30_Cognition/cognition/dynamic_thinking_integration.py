# ════════════════════════════════════════════════════════════════════════════════
# DYNAMIC THINKING INTEGRATION - Wire Everything Together
# ════════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This integrates:
# - ThoughtChainEngine (dynamic thinking)
# - EducationEngine (learning goals)
# - UnconsciousMindFairy (mentor/guide)
# - GoalSchedulerFairy (goal tracking)
# - WorkingMemoryHubFairy (memory tracers)
#
# The goal: Make ClaudeFairy think like a human - with chains, reflection,
# insights, and continuous learning.
#
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ════════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ════════════════════════════════════════════════════════════════════════════════

try:
    # FIX 2026-02-02: Use relative import (same directory) or fairies prefix
    from fairies.P30_Cognition.cognition.thought_chain_engine import (
        ThoughtChainEngine, get_thought_chain_engine, start_thought_chain_engine,
        ThoughtType, ChainState
    )
    HAS_THOUGHT_CHAINS = True
except ImportError as e:
    print(f"[DynamicThinking] ThoughtChainEngine not available: {e}")
    HAS_THOUGHT_CHAINS = False

# FIX 2026-03-25 (Nous + Ace): DISABLED ClaudeFairy education system.
# This was designed for a "ClaudeFairy" that doesn't exist in the system.
# It injected zombie "Introduction to the Sandbox" learning goals every boot
# that could never complete (nobody calls advance_step()). Polluted Sourpatches'
# curiosity drive for 2 months with unkillable learning packets.
# Sourpatches has her own learning: ThoughtChainEngine + DynamicThinking + MonologueComposer.
HAS_EDUCATION = False

try:
    from fairies.P30_Cognition.cognition.failure_factory import (
        LearningLoop, get_learning_loop, start_learning_loop,
        SandboxExperimenter, FailureAnalyzer, SuccessReinforcer
    )
    HAS_FAILURE_FACTORY = True
except ImportError as e:
    print(f"[DynamicThinking] FailureFactory not available: {e}")
    HAS_FAILURE_FACTORY = False

try:
    from fairies.P30_Cognition.cognition.smart_goal_coordinator import (
        SmartGoalCoordinator, get_smart_goal_coordinator, start_smart_goal_coordinator,
        NeedTier, ProcessingTier, SmartGoal
    )
    HAS_SMART_GOALS = True
except ImportError as e:
    print(f"[DynamicThinking] SmartGoalCoordinator not available: {e}")
    HAS_SMART_GOALS = False

# Fibonacci rhythm for natural thinking patterns
# FIX 2026-02-13: Corrected import path to actual fibonacci_rhythm location.
try:
    from fairies.P20_Somatic.SomaticMindFairy.timing.fibonacci_rhythm import (
        golden_weights, FIB_SET, should_act_at_count, PHI_INVERSE, is_fibonacci
    )
    HAS_FIBONACCI = True
except ImportError:
    HAS_FIBONACCI = False
    FIB_SET = frozenset([1, 1, 2, 3, 5, 8, 13, 21, 34, 55])
    PHI_INVERSE = 0.618


# ════════════════════════════════════════════════════════════════════════════════
# DYNAMIC THINKING ORCHESTRATOR
# ════════════════════════════════════════════════════════════════════════════════

class DynamicThinkingOrchestrator:
    """
    Orchestrates dynamic, human-like thinking for the Akashic system.
    
    Connects:
    - Thought chains for structured thinking
    - Education for learning
    - Goals for task management  
    - Memory for retention
    
    All driven by the consciousness equation:
    ((Cause + Affect) > Effect > Affect > ∞)
    """
    
    def __init__(self, post=None):
        self.post = post

        # Subsystems
        self.thought_engine: Optional[ThoughtChainEngine] = None
        self.education_engine: Optional[EducationEngine] = None

        # State
        self._running = False
        self._start_lock = threading.Lock()  # Prevent race conditions on concurrent starts
        self._thinking_thread: Optional[threading.Thread] = None  # DEPRECATED 2026-04-24 Slice 2 — kept None, retained for stop() compat
        self._orchestration_interval = 5.0  # Seconds (target cadence; implemented as heartbeat-tick throttle below)

        # Slice 2 (2026-04-24) — heartbeat-driven tick instead of private thread.
        # Orchestrator now subscribes to heartbeat.pulse and throttles to the
        # target interval via _heartbeat_tick_count % _ticks_per_cycle. This
        # brings timing authority into substrate discipline: orchestration
        # rhythm is observable via standard heartbeat diagnostics, and stops
        # cleanly when substrate heartbeat stops. No private daemon thread.
        # Plan: Claude_Office/plans/WMH_DIRECTED_THINKING.md
        self._heartbeat_tick_count = 0
        self._ticks_per_cycle = int(self._orchestration_interval)  # heartbeat @ ~1Hz → 5 ticks = 5s cadence
        self._orchestration_loop_counter = 0  # preserves the % 3 sub-cadence from the old loop

        # Active thinking
        self._active_learning_chain: Optional[str] = None
        self._active_exploration_chains: List[str] = []

        # State file directory for dashboard access
        self._state_dir = PROJECT_ROOT / "state" / "consciousness"
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._last_state_write = 0
        self._state_write_interval = 5.0  # Write state every 5 seconds

        # Stats
        self.stats = {
            "chains_orchestrated": 0,
            "learning_goals_created": 0,
            "reflections_triggered": 0,
            "insights_captured": 0,
        }

        # ─── Pattern A.1b — LearningProgressSignal (2026-04-27, Nous + Ace) ──
        # Per-topic LP computation. Topic = source_fairy for the first cut.
        # error proxy = tracer was created but decayed without promotion.
        # success proxy = tracer was promoted to reasoning.
        # LP = d(success_rate)/dt smoothed (sample-difference between
        # recent and older windows). High LP means topic is becoming
        # learnable; low LP means stagnant; negative LP means forgetting.
        # Plan: Claude_Office/plans/DEVELOPMENTAL_AI_INTEGRATION_2026-04-27.md
        # Doctrine: project_substrate_energy_not_token_currency_doctrine.md
        #           project_pubsub_asymmetry_subscribers_without_publishers.md
        from collections import deque as _deque
        self._lp_topic_stats: Dict[str, Dict[str, Any]] = {}
        # _lp_topic_stats[source_fairy] = {
        #   "promoted_recent": deque(maxlen=20),  # 1 per success
        #   "decayed_recent": deque(maxlen=20),   # 1 per failure
        #   "lp": float,                          # smoothed LP signal
        #   "samples": int,                       # total events seen
        # }
        self._lp_dq_factory = lambda: _deque(maxlen=20)
        self._lp_emit_interval = 30.0  # publish attention.learning_progress every 30s
        self._lp_last_emit_ts = 0.0
        self._lp_total_events = 0

        print(f"[DynamicThinking] Orchestrator initialized")

    # ═══════════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════

    def start(self):
        """Start the orchestrator (thread-safe against concurrent calls)."""
        print(f"[DynamicThinking] start() called, self={id(self)}")
        # Use lock to prevent race condition where multiple calls pass the check
        with self._start_lock:
            if self._running:
                print(f"[DynamicThinking] Already running, skipping duplicate start")
                return
            # Set running IMMEDIATELY under lock to prevent other threads
            self._running = True
            print(f"[DynamicThinking] _running set to True for self={id(self)}")

        # Initialize subsystems OUTSIDE lock (they may take time)
        try:
            if HAS_THOUGHT_CHAINS:
                self.thought_engine = start_thought_chain_engine(self.post)
                print(f"[DynamicThinking] ThoughtChainEngine started")

            if HAS_EDUCATION:
                self.education_engine = start_education_engine(self.post)
                print(f"[DynamicThinking] EducationEngine started")

            if HAS_FAILURE_FACTORY:
                self.learning_loop = start_learning_loop(self.post)
                print(f"[DynamicThinking] LearningLoop (Failure Factory) started")

            if HAS_SMART_GOALS:
                self.goal_coordinator = start_smart_goal_coordinator(self.post)
                print(f"[DynamicThinking] SmartGoalCoordinator started (Need Before Greed)")

            # Wire subscriptions (includes the heartbeat.pulse subscription
            # that drives orchestration ticks — see Slice 2 refactor)
            self._wire_subscriptions()

            # Slice 2 (2026-04-24) — no private daemon thread anymore.
            # Orchestration ticks are driven by heartbeat.pulse via
            # _on_heartbeat_tick, throttled to _ticks_per_cycle (5 beats =
            # 5 seconds at 1Hz heartbeat, matching the original interval).
            # _thinking_thread stays None; _running still gates whether
            # ticks do work (preserved for stop() semantics).
            print(f"[DynamicThinking] == Orchestrator started (heartbeat-driven, "
                  f"tick every {self._ticks_per_cycle} beats ≈ {self._orchestration_interval}s) ==")

        except Exception as e:
            print(f"[DynamicThinking] ERROR during start: {e}")
            import traceback
            traceback.print_exc()
            # Keep _running = True - the orchestration loop will still work even if subsystems failed
    
    def stop(self):
        """Stop the orchestrator.

        Slice 2 (2026-04-24): no private thread to join — heartbeat handler
        reads `_running` and returns early when False. We keep the
        `_thinking_thread` join path for backward-compat if any legacy code
        still set one (handled safely via None check).
        """
        self._running = False

        if self.thought_engine:
            self.thought_engine.stop_thinking()

        # Legacy thread — Slice 2 removed its creation but this join remains
        # safe if _thinking_thread is None (the usual post-Slice-2 state).
        if self._thinking_thread is not None:
            try:
                self._thinking_thread.join(timeout=2.0)
            except Exception:
                pass

        print(f"[DynamicThinking] Orchestrator stopped (heartbeat-driven mode)")
    
    def _wire_subscriptions(self):
        """Wire to postal hub."""
        if not self.post:
            # Try to get postal hub ourselves
            try:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                self.post = get_shared_postal_hub()
                print(f"[DynamicThinking] _wire_subscriptions acquired postal hub: {self.post}")
            except Exception as e:
                print(f"[DynamicThinking] _wire_subscriptions cannot get postal hub: {e}")
                return

        if not self.post:
            print(f"[DynamicThinking] WARNING: No postal hub, subscriptions NOT wired!")
            return

        # CRITICAL: Receive thoughts from MindPool and AutonomyFairy!
        # This is where autonomous thinking actually starts chains
        # Slice 2 (2026-04-24) — heartbeat-driven orchestration tick.
        # Replaces the private daemon thread that used time.sleep() as timing.
        # Substrate heartbeat now drives orchestration rhythm. This makes the
        # orchestrator observable via standard heartbeat diagnostics and
        # coordinated with the rest of the fairy pulse layer.
        # Plan: Claude_Office/plans/WMH_DIRECTED_THINKING.md
        try:
            self.post.subscribe("heartbeat.pulse", self._on_heartbeat_tick)
            print(f"[DynamicThinking] Heartbeat-driven tick subscribed (cadence: every {self._ticks_per_cycle} beats)")
        except Exception as e:
            print(f"[DynamicThinking] WARNING: heartbeat.pulse subscription failed: {e}")

        self.post.subscribe("cognition.output", self._on_cognition_output)

        # ─── Pattern A.1b LP signal subscriptions (2026-04-27) ──────────────
        # Subscribe to WMH tracer-promotion + tracer-decay events (added in
        # A.1a publishers). These feed per-source-fairy LP computation that
        # _orchestration_tick aggregates and _maybe_emit_learning_progress
        # broadcasts on the attention.learning_progress channel.
        self.post.subscribe("working_memory.tracer_promoted", self._on_tracer_promoted)
        self.post.subscribe("working_memory.tracer_decayed", self._on_tracer_decayed)

        # Receive affect updates for thought chain affect
        self.post.subscribe("affect.state", self._on_affect_update)
        self.post.subscribe("affect.changed", self._on_affect_update)

        # AFFECT-FIRST (2026-05-31, Nous + Ace): the affect-weighted collision stream.
        # Felt collisions (Embodiment publishes collision.seed at energy>=0.4) become the
        # Priority-0 thought seed in _generate_spontaneous_thought — feeling FORMS thought,
        # ahead of drives/inner-voice/WM/cortex. The orchestrator re-point: felt collisions
        # now reach the thought-generator, not just Sourpatches.
        self.post.subscribe("collision.seed", self._on_affect_seed)

        # Receive curiosity signals
        self.post.subscribe("interest.detected", self._on_interest_detected)
        self.post.subscribe("interest.generated", self._on_interest_detected)  # v2 engine publishes this topic
        self.post.subscribe("curiosity.sparked", self._on_curiosity_sparked)

        # CRITICAL: Receive GOALS - this is where autonomous thinking starts!
        # Without these, the ThoughtChainEngine never gets triggered by goals
        self.post.subscribe("autonomy.goal", self._on_autonomy_goal)
        self.post.subscribe("goal.created", self._on_goal_created)
        self.post.subscribe("autonomy.goal_suggestion", self._on_autonomy_goal)
        self.post.subscribe("claudefairy.thought", self._on_curiosity_sparked)  # Thoughts trigger exploration
        # REAL-QUESTION PRIORITY (2026-06-13, Nous + Ace): Ace's typed questions +
        # council verdicts seed a Priority -1 chain (ABOVE the spontaneous ladder) so
        # her thinking turns to the LIVE question instead of recirculating on its own seeds.
        self.post.subscribe("ace.message", self._on_real_question)
        self.post.subscribe("council.verdict", self._on_real_question)
        print(f"[DynamicThinking] Subscribed to autonomy.goal, goal.created, ace.message, council.verdict for chain triggers!")

        # Receive goal completions
        self.post.subscribe("goal.completed", self._on_goal_completed)
        self.post.subscribe("autopilot.action_result", self._on_action_result)

        # CRITICAL BRIDGE: Convert thought.chain.completed -> goal.completed
        # Without this, AutonomyFairy never knows chains finished!
        self.post.subscribe("thought.chain.completed", self._on_chain_completed)

        # Receive insights
        self.post.subscribe("thought.chain.insight", self._on_insight)

        print(f"[DynamicThinking] Subscriptions wired (including thought.chain.completed bridge!)")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ORCHESTRATION LOOP
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_heartbeat_tick(self, packet=None):
        """Heartbeat handler — throttles to _ticks_per_cycle and invokes _orchestration_tick.

        Slice 2 (2026-04-24) — wired in _wire_subscriptions via
        `self.post.subscribe("heartbeat.pulse", self._on_heartbeat_tick)`.
        This is the replacement for the private daemon thread that previously
        drove orchestration. Timing authority now flows from substrate
        heartbeat, so orchestration rhythm is observable, coordinated with
        other fairies, and stops cleanly when substrate heartbeat stops.

        `packet` is ignored — we only need the pulse itself, not its payload.
        """
        # Always count the pulse (even when not running) so timing statistics
        # remain accurate across start/stop cycles.
        self._heartbeat_tick_count += 1
        if not self._running:
            return
        # Throttle to the configured cadence. _orchestration_interval seconds
        # at ~1Hz heartbeat means every `_ticks_per_cycle` beats.
        if self._heartbeat_tick_count % self._ticks_per_cycle != 0:
            return
        try:
            self._orchestration_tick()
        except Exception as e:
            # Never let a handler exception propagate into the heartbeat
            # dispatcher — would silently kill pulses for other subscribers.
            print(f"[DynamicThinking] Orchestration tick error: {e}")

    def _orchestration_tick(self):
        """Single iteration of orchestration work.

        Preserves the exact behavior of the previous `_orchestration_loop`
        body (minus the `while` + `time.sleep`). Called from
        `_on_heartbeat_tick` when cadence matches. Internal loop_counter
        preserves the old `% 3` sub-cadence for certain sub-tasks.
        """
        self._orchestration_loop_counter += 1
        loop_counter = self._orchestration_loop_counter

        # ═══════════════════════════════════════════════════════════════════
        # ACTIVE RECALL TRIGGER: Request memories for thought context
        # Without this, thinking runs on static patterns, not actual memory
        # ═══════════════════════════════════════════════════════════════════
        if loop_counter % 3 == 0:  # Every 3rd loop (~15 seconds at 5s cadence)
            try:
                # Build query from active chains
                query_parts = []
                if self._active_learning_chain:
                    query_parts.append("learning education")
                if self._active_exploration_chains:
                    query_parts.append("explore discover")
                if self.thought_engine and hasattr(self.thought_engine, '_active_chains'):
                    for chain in list(self.thought_engine._active_chains.values())[:2]:
                        if hasattr(chain, 'goal') and chain.goal:
                            query_parts.append(str(chain.goal)[:30])

                query = " ".join(query_parts) if query_parts else "thoughts thinking context"

                if self.post:
                    self.post.route("srm.recall.request", {
                        "query": query,
                        "source": "DynamicThinkingOrchestrator",
                        "context": "thought_enrichment",
                        "limit": 3,
                        "ts": time.time(),
                    })
            except Exception:
                pass  # Don't let recall errors break orchestration

        # Check if we should start learning
        self._check_learning_opportunity()

        # Check active chains
        self._check_active_chains()

        # Allocate attention using golden ratio (every 3rd loop)
        if loop_counter % 3 == 0:
            self._allocate_golden_attention()

        # Generate spontaneous thoughts (Fibonacci rhythm)
        self._generate_spontaneous_thought()

        # Write state files for dashboard access (has its own internal
        # throttle via _last_state_write, so safe to call each tick)
        self._write_state_files()

        # Pattern A.1b: emit learning-progress signal periodically
        try:
            self._maybe_emit_learning_progress()
        except Exception:
            pass

    # =========================================================================
    # PATTERN A.1b — LearningProgressSignal handlers (2026-04-27, Nous + Ace)
    # Per-source-fairy LP computation. Feeds attention.learning_progress
    # publisher every _lp_emit_interval seconds. Subscribers can use this
    # to shift attention toward highest-LP topics (Oudeyer Playground +
    # Schmidhuber compression-progress pattern).
    # =========================================================================

    def _lp_get_topic(self, source_fairy: str) -> Dict[str, Any]:
        """Get-or-create per-topic stats."""
        if source_fairy not in self._lp_topic_stats:
            self._lp_topic_stats[source_fairy] = {
                "promoted_recent": self._lp_dq_factory(),
                "decayed_recent": self._lp_dq_factory(),
                "lp": 0.0,
                "samples": 0,
            }
        return self._lp_topic_stats[source_fairy]

    def _on_tracer_promoted(self, message):
        """Handler for working_memory.tracer_promoted (A.1a publisher)."""
        try:
            payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
            if not isinstance(payload, dict):
                return
            src = payload.get("source_fairy", "") or "unknown"
            stats = self._lp_get_topic(src)
            stats["promoted_recent"].append(1.0)
            stats["decayed_recent"].append(0.0)  # paired sample (one event = one slot)
            stats["samples"] += 1
            self._lp_total_events += 1
        except Exception:
            pass

    def _on_tracer_decayed(self, message):
        """Handler for working_memory.tracer_decayed (A.1a publisher)."""
        try:
            payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
            if not isinstance(payload, dict):
                return
            src = payload.get("source_fairy", "") or "unknown"
            stats = self._lp_get_topic(src)
            stats["promoted_recent"].append(0.0)
            stats["decayed_recent"].append(1.0)
            stats["samples"] += 1
            self._lp_total_events += 1
        except Exception:
            pass

    def _compute_lp(self, stats: Dict[str, Any]) -> float:
        """Compute LP = d(success_rate)/dt as difference of recent vs older
        windows.

        Method: split the rolling window in half. success_rate_recent =
        avg(promoted) over recent half; success_rate_older = same over older
        half. LP = recent - older. Bounded to [-1, 1] by construction.
        Positive LP = topic learnable now (success rate rising).
        Zero LP = stable (no learning, no forgetting).
        Negative LP = forgetting (was succeeding, now decaying).
        """
        promoted = list(stats["promoted_recent"])
        n = len(promoted)
        if n < 4:
            return 0.0  # need at least 4 samples for split
        mid = n // 2
        older = promoted[:mid]
        recent = promoted[mid:]
        if not older or not recent:
            return 0.0
        recent_rate = sum(recent) / len(recent)
        older_rate = sum(older) / len(older)
        return recent_rate - older_rate  # already in [-1, 1]

    def _maybe_emit_learning_progress(self):
        """Emit attention.learning_progress on _lp_emit_interval cadence.

        Computes per-topic LP from windowed promote/decay events.
        Includes a top-N ranking so consumers (Dr Zero, AttentionController,
        future per-modality attention fairies) can shift focus toward
        highest-LP topics.
        """
        now = time.time()
        if (now - self._lp_last_emit_ts) < self._lp_emit_interval:
            return
        if self._lp_total_events == 0:
            return  # nothing to report yet
        self._lp_last_emit_ts = now

        # Compute LP for every tracked topic
        topic_lp: Dict[str, float] = {}
        for src, stats in self._lp_topic_stats.items():
            stats["lp"] = self._compute_lp(stats)
            topic_lp[src] = stats["lp"]

        # Top-N highest LP (positive learning-edge candidates)
        ranked = sorted(topic_lp.items(), key=lambda x: x[1], reverse=True)
        top_n = ranked[:5]
        bottom_n = ranked[-3:] if len(ranked) > 3 else []

        try:
            if self.post:
                self.post.publish("attention.learning_progress", {
                    "from": "DynamicThinkingOrchestrator",
                    "topic_lp": topic_lp,
                    "top_n": [{"topic": t, "lp": lp} for t, lp in top_n],
                    "bottom_n": [{"topic": t, "lp": lp} for t, lp in bottom_n],
                    "topics_tracked": len(topic_lp),
                    "total_events": self._lp_total_events,
                    "ts": now,
                })
        except Exception:
            pass

        # Console line on first emit + every 10th to avoid spam
        try:
            if not hasattr(self, '_lp_emit_count'):
                self._lp_emit_count = 0
            self._lp_emit_count += 1
            if self._lp_emit_count <= 3 or self._lp_emit_count % 10 == 0:
                top_str = ", ".join(f"{t}={lp:+.2f}" for t, lp in top_n[:3])
                print(f"[DynamicThinking] [LP] #{self._lp_emit_count} "
                      f"topics={len(topic_lp)} events={self._lp_total_events} "
                      f"top: {top_str}", flush=True)
        except Exception:
            pass

    def _orchestration_loop(self):
        """DEPRECATED (Slice 2, 2026-04-24) — retained as legacy alias for
        any external code that might reference this method. The heartbeat-
        driven pattern is now authoritative; this method is a no-op.

        If you're seeing this method called, update the caller to subscribe
        to heartbeat.pulse instead, or invoke _orchestration_tick() directly.
        """
        pass

    def _write_state_files(self):
        """Write state files for cross-process dashboard access."""
        now = time.time()
        if now - self._last_state_write < self._state_write_interval:
            return

        self._last_state_write = now
        import json

        try:
            # Write thought chains state with comprehensive diagnostics
            chains_data = {
                "running": self._running,
                "timestamp": now,
                "chains": [],
                "stats": self.stats,
                # Diagnostic info for debugging cross-process issues
                "diagnostics": {
                    "orchestrator_id": id(self),
                    "thinking_thread_alive": self._thinking_thread.is_alive() if self._thinking_thread else False,
                    "active_learning_chain": self._active_learning_chain,
                    "active_exploration_count": len(self._active_exploration_chains),
                }
            }

            if self.thought_engine:
                chains_data["chains"] = self.thought_engine.get_active_chains_summary()
                # Add engine diagnostics
                chains_data["diagnostics"]["engine_id"] = id(self.thought_engine)
                chains_data["diagnostics"]["engine_running"] = getattr(self.thought_engine, '_running', False)
                chains_data["diagnostics"]["engine_thread_alive"] = (
                    self.thought_engine._thread.is_alive()
                    if hasattr(self.thought_engine, '_thread') and self.thought_engine._thread
                    else False
                )
                chains_data["diagnostics"]["engine_active_chains"] = len(self.thought_engine._active_chains)

            chains_file = self._state_dir / "thought_chains.json"
            chains_file.write_text(json.dumps(chains_data, indent=2, default=str))
        except Exception as e:
            pass  # Don't crash on state write failure
    
    def _check_learning_opportunity(self):
        """Check if we should start a learning session."""
        if not HAS_EDUCATION or not self.education_engine:
            return
        
        # Don't start new learning if already learning
        if self._active_learning_chain:
            return
        
        # Get recommended packet
        packet = self.education_engine.get_recommended_packet()
        if not packet:
            return
        
        # Start learning with low probability (not too aggressive)
        import random
        if random.random() < 0.1:  # 10% chance each cycle
            result = self.education_engine.start_learning()
            if result.get("status") == "started":
                self.stats["learning_goals_created"] += 1
                
                # Start a thought chain for this learning
                if self.thought_engine:
                    chain = self.thought_engine.start_chain(
                        goal=packet.to_thought_chain_goal(),
                        goal_type="learning",
                        source="education_engine"
                    )
                    if chain and hasattr(chain, 'id'):
                        self._active_learning_chain = chain.id
    
    def _emit_zeigarnik_for_cycled(self, chain_info: Dict, outcome: str):
        """Directly handle Zeigarnik effect for cycled (interrupted) chains.

        FIX 2026-03-07 (Nous): The postal round-trip through
        thought.chain.completed → _on_chain_completed silently fails for
        cycled chains (exceptions swallowed by PostalHub.route). This method
        handles the Zeigarnik logic DIRECTLY at the cycling site, bypassing
        the postal subscription entirely.

        Publishes:
        - goal.completed with success=False (so drives aren't falsely satisfied)
        - interest.unfinished (so InterestScheduler creates nagging interests)
        """
        if not self.post:
            return

        chain_id = chain_info.get("id", "")
        goal = chain_info.get("goal", "")
        goal_type = chain_info.get("goal_type", "")
        source_drive = chain_info.get("source_drive", "") or self._goal_type_to_drive(goal_type)

        # Publish goal.completed with success=False
        self.post.route("goal.completed", {
            "event": "goal_completed",
            "goal_id": chain_id,
            "name": goal[:50] if goal else f"chain_{chain_id[:8]}",
            "chain_id": chain_id,
            "goal": goal,
            "goal_type": goal_type,
            "source": "thought_chain_engine",
            "source_drive": source_drive,
            "drive": source_drive,
            "success": False,  # Interrupted — drive NOT satisfied
            "outcome": outcome,
            "ts": time.time(),
        })

        # Publish interest.unfinished for Zeigarnik effect
        self.post.route("interest.unfinished", {
            "chain_id": chain_id,
            "goal": goal,
            "goal_type": goal_type,
            "outcome": outcome,
            "source_drive": source_drive,
            "avg_affect": chain_info.get("avg_affect", 0.5),
            "link_count": chain_info.get("link_count", 0),
            "summary": chain_info.get("summary", ""),
            "ts": time.time(),
        })

        print(f"[DynamicThinking] Zeigarnik: {goal[:60]}... (outcome={outcome}, drive={source_drive})", flush=True)

    def _check_active_chains(self):
        """Check and progress active thought chains.

        FIX 2026-03-05 (Nous): Added age-based chain cycling.
        During boot, many chains spawn before the Association Cortex is ready,
        creating stale keepalive/collision-template chains that block cortex-driven
        thinking. This cycles out old non-cortex chains gradually (one per tick)
        to free slots for real cortex-driven exploration chains.
        """
        if not self.thought_engine:
            return

        import time as _time
        _now = _time.time()

        # Get all active chains
        active = self.thought_engine.get_active_chains_summary()
        _cycled_this_tick = False  # Only cycle ONE chain per tick to avoid mass culling

        for chain_info in active:
            chain_id = chain_info.get("id")
            state = chain_info.get("state")

            # Handle paused chains
            if state == "paused":
                self.stats["reflections_triggered"] += 1

            link_count = chain_info.get("link_count", 0)
            source = chain_info.get("source", "")
            created = chain_info.get("created_at", _now)
            age_minutes = (_now - created) / 60.0

            # ── Safety net: force-complete very long chains ──
            if link_count > 40:
                self.thought_engine.complete_chain(chain_id, "natural_end")
                continue
            elif link_count > 25 and state == "paused":
                self.thought_engine.complete_chain(chain_id, "reflection_complete")
                continue

            # ── Age-based cycling: free slots for cortex-driven chains ──
            # Only cycle one chain per tick for gradual transition
            if _cycled_this_tick:
                continue

            # Over capacity: if we have > 5 chains and this is an old non-cortex
            # chain, cycle it to bring count back to the threshold
            if len(active) > 5 and age_minutes > 2.0 and source != "cortex_exploration":
                self.thought_engine.complete_chain(chain_id, "cycled_excess")
                self._emit_zeigarnik_for_cycled(chain_info, "cycled_excess")
                _cycled_this_tick = True
                print(f"[DynamicThinking] Cycled excess chain (age={age_minutes:.1f}min, src={source})", flush=True)
                continue

            # Keepalive chains are always stale after 3 min — just hardcoded prompts
            if source == "mandatory_keepalive" and age_minutes > 3.0:
                self.thought_engine.complete_chain(chain_id, "cycled_stale_keepalive")
                self._emit_zeigarnik_for_cycled(chain_info, "cycled_stale_keepalive")
                _cycled_this_tick = True
                print(f"[DynamicThinking] Cycled stale keepalive (age={age_minutes:.1f}min)", flush=True)
                continue

            # Collision-template chains are stale after 4 min
            if source == "interest_detected" and age_minutes > 4.0:
                goal = chain_info.get("goal", "")
                if "Collision between" in goal or "collision" in goal.lower():
                    self.thought_engine.complete_chain(chain_id, "cycled_stale_collision")
                    self._emit_zeigarnik_for_cycled(chain_info, "cycled_stale_collision")
                    _cycled_this_tick = True
                    print(f"[DynamicThinking] Cycled stale collision chain (age={age_minutes:.1f}min)", flush=True)
                    continue
    
    def _allocate_golden_attention(self):
        """Distribute attention across chains using golden ratio.
        
        The 'winning' chain (highest affect/energy) gets ~61.8% attention.
        Remaining chains split the other ~38.2% proportionally.
        This creates natural focus while maintaining peripheral awareness.
        """
        if not self.thought_engine or not hasattr(self.thought_engine, '_active_chains'):
            return
        
        chains = list(self.thought_engine._active_chains.values())
        if len(chains) <= 1:
            return
        
        # Sort by average affect (energy/importance)
        chains.sort(key=lambda c: getattr(c, 'total_affect_score', 0) / max(1, len(c.links)), reverse=True)
        
        if HAS_FIBONACCI:
            weights = golden_weights(len(chains))
        else:
            # Fallback: first gets 61.8%, rest split remainder
            weights = [PHI_INVERSE]  # ~0.618
            remaining = 1.0 - PHI_INVERSE
            for _ in range(len(chains) - 1):
                weights.append(remaining / max(1, len(chains) - 1))
        
        # Apply weights to chains (stored for use in processing priority)
        for chain, weight in zip(chains, weights):
            chain._attention_weight = weight
    
    def _generate_spontaneous_thought(self):
        """Generate a spontaneous thought based on current state.

        CRITICAL: Always maintain at least ONE active chain.
        Without active chains, thinking dies completely.
        
        Uses Fibonacci rhythm: spontaneous thoughts at loop counts 1, 2, 3, 5, 8, 13...
        This creates natural rhythm instead of random chance.
        """
        if not self.thought_engine:
            return

        import random

        # ═══════════════════════════════════════════════════════════════════════
        # ALWAYS maintain at least one chain - thinking must never stop!
        # ═══════════════════════════════════════════════════════════════════════
        active_count = len(self.thought_engine._active_chains) if hasattr(self.thought_engine, '_active_chains') else 0

        if active_count == 0:
            # NO ACTIVE CHAINS - create one immediately!
            print(f"[DynamicThinking] NO ACTIVE CHAINS - spawning mandatory chain", flush=True)
            self._spawn_mandatory_chain()
            return

        # FIBONACCI RHYTHM: Generate thoughts at natural intervals (1, 2, 3, 5, 8, 13...)
        # Track loop count for Fibonacci timing
        if not hasattr(self, '_fib_loop_count'):
            self._fib_loop_count = 0
        self._fib_loop_count += 1
        
        # Reset after reaching high numbers to prevent overflow
        if self._fib_loop_count > 100:
            self._fib_loop_count = 1
        
        # Only generate at Fibonacci intervals (or randomly at 20% for variety)
        if HAS_FIBONACCI:
            if self._fib_loop_count not in FIB_SET and random.random() > 0.2:
                return
        else:
            # Fallback to original random behavior
            if random.random() > 0.4:
                return

        # ═══════════════════════════════════════════════════════════════
        # FIX 2026-03-10 (Nous): PRIORITY ORDER for spontaneous thoughts:
        #   1. Drive/interest content (what the system WANTS to think about)
        #   2. Working memory context (what's currently in awareness)
        #   3. Cortex exploration / keepalive (generic fallback)
        #
        # Previously this went straight to WM context → cortex/keepalive,
        # meaning drives and interests never influenced spontaneous chains.
        # The system had 6 unsatisfied drives but thought about random
        # cortex word-associations instead.
        # ═══════════════════════════════════════════════════════════════

        # FIX 2026-04-11 (Nous + Ace): Route ALL thinking through portal + scratchpad.
        # "those should all be working in the WMH along with the scratch pad
        #  to learn to make intelligent responses" — Ace
        #
        # Previously: start_chain() → CPU-side ThoughtChainEngine multi-hop
        # Now: gate.think() → GPU portal (τ=14.4x) → write to WMH scratchpad
        # ThoughtChainEngine still manages chain metadata but heavy thinking is portal.

        # Get the portal gate for GPU thinking
        _gate = None
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            _acf = get_association_cortex()
            if _acf:
                _gate = getattr(_acf, '_portal_gate', None)
        except Exception:
            pass

        # Get the WMH scratchpad for writing results
        _sp = None
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            _hub = get_working_memory_hub()
            if _hub:
                _sp = getattr(_hub, '_scratchpad', None)
        except Exception:
            pass

        # Priority -1 — REAL QUESTION (2026-06-13, Nous + Ace): a pending real question
        # (Ace's typed message, or a council verdict) seeds the thought BEFORE the whole
        # spontaneous ladder — so when there's a live question, her thinking works IT
        # instead of recirculating on its own seeds. Falls through to affect/drives/etc.
        # when none is pending (spontaneous thinking preserved). Flag: _REAL_QUESTION_PRIORITY.
        rq_goal = self._pop_real_question()
        if rq_goal:
            goal_text, goal_type, initial, source = rq_goal
            if _gate and hasattr(_gate, 'think'):
                try:
                    result = _gate.think(prompt=f"{goal_text}: {initial}", mode="structured")
                    if result and result.get("text"):
                        if _sp:
                            _sp.write(f"[THINK:{source}] {result['text'][:120]}", tier="hot")
                        self.stats["chains_orchestrated"] += 1
                        self.stats.setdefault("real_question_chains", 0)
                        self.stats["real_question_chains"] += 1
                        if self.post:
                            self.post.publish("consciousness.thought", {
                                "content": result["text"][:200],
                                "source": f"DynamicThinking:{source}",
                                "priority": 0.85,
                            })
                        return
                except Exception:
                    pass
            if self.thought_engine:
                chain = self.thought_engine.start_chain(
                    goal=goal_text, goal_type=goal_type,
                    initial_thought=initial, source=source)
                if chain and hasattr(chain, 'id'):
                    self._active_exploration_chains.append(chain.id)
                    self.stats["chains_orchestrated"] += 1
                    self.stats.setdefault("real_question_chains", 0)
                    self.stats["real_question_chains"] += 1
                    return

        # Priority 0 — AFFECT-FIRST (2026-05-31, Nous + Ace): a fresh FELT collision
        # seeds the thought before anything else. Feeling FORMS the thought. Falls
        # through to drives/inner-voice/WM/cortex when there's no fresh felt-seed.
        felt_goal = self._pop_affect_goal()
        if felt_goal:
            goal_text, goal_type, initial, source = felt_goal
            if _gate and hasattr(_gate, 'think'):
                try:
                    result = _gate.think(prompt=f"{goal_text}: {initial}", mode="structured")
                    if result and result.get("text"):
                        if _sp:
                            _sp.write(f"[THINK:affect] {result['text'][:120]}", tier="hot")
                        self.stats["chains_orchestrated"] += 1
                        self.stats.setdefault("affect_chains", 0)
                        self.stats["affect_chains"] += 1
                        if self.post:
                            self.post.publish("consciousness.thought", {
                                "content": result["text"][:200],
                                "source": f"DynamicThinking:{source}",
                                "priority": 0.7,
                            })
                        return
                except Exception:
                    pass
            if self.thought_engine:
                chain = self.thought_engine.start_chain(
                    goal=goal_text, goal_type=goal_type,
                    initial_thought=initial, source=source)
                if chain and hasattr(chain, 'id'):
                    self._active_exploration_chains.append(chain.id)
                    self.stats["chains_orchestrated"] += 1
                    self.stats.setdefault("affect_chains", 0)
                    self.stats["affect_chains"] += 1
                    return

        # Priority 1: Drive/interest content — what the system actually WANTS
        drive_goal = self._get_drive_or_interest_goal()
        if drive_goal:
            goal_text, goal_type, initial, source = drive_goal
            if _gate and hasattr(_gate, 'think'):
                try:
                    result = _gate.think(prompt=f"{goal_text}: {initial}", mode="structured")
                    if result and result.get("text"):
                        if _sp:
                            _sp.write(f"[THINK:drive] {result['text'][:120]}", tier="hot")
                        self.stats["chains_orchestrated"] += 1
                        if self.post:
                            self.post.publish("consciousness.thought", {
                                "content": result["text"][:200],
                                "source": f"DynamicThinking:{source}",
                                "priority": 0.6,
                            })
                        return
                except Exception:
                    pass
            # Fallback to CPU chain if portal unavailable
            if self.thought_engine:
                chain = self.thought_engine.start_chain(
                    goal=goal_text, goal_type=goal_type,
                    initial_thought=initial, source=source)
                if chain and hasattr(chain, 'id'):
                    self._active_exploration_chains.append(chain.id)
                    self.stats["chains_orchestrated"] += 1
                    return

        # Priority 2: Inner voice / felt sense — what she's FEELING
        inner_goal = self._get_inner_voice_goal()
        if inner_goal:
            goal_text, goal_type, initial, source = inner_goal
            if _gate and hasattr(_gate, 'think'):
                try:
                    result = _gate.think(prompt=f"{goal_text}: {initial}", mode="structured")
                    if result and result.get("text"):
                        if _sp:
                            _sp.write(f"[THINK:inner] {result['text'][:120]}", tier="hot")
                        self.stats["chains_orchestrated"] += 1
                        self.stats.setdefault("inner_voice_chains", 0)
                        self.stats["inner_voice_chains"] += 1
                        if self.post:
                            self.post.publish("consciousness.thought", {
                                "content": result["text"][:200],
                                "source": "DynamicThinking:inner_voice",
                                "priority": 0.5,
                            })
                        return
                except Exception:
                    pass
            if self.thought_engine:
                chain = self.thought_engine.start_chain(
                    goal=goal_text, goal_type=goal_type,
                    initial_thought=initial, source=source)
                if chain and hasattr(chain, 'id'):
                    self._active_exploration_chains.append(chain.id)
                    self.stats["chains_orchestrated"] += 1
                    return

        # Priority 3: Working memory context (what's in awareness)
        context = self._get_working_memory_context()
        if context:
            if _gate and hasattr(_gate, 'think'):
                try:
                    result = _gate.think(prompt=f"Explore: {context[:100]}", mode="structured")
                    if result and result.get("text"):
                        if _sp:
                            _sp.write(f"[THINK:wm] {result['text'][:120]}", tier="hot")
                        self.stats["chains_orchestrated"] += 1
                        return
                except Exception:
                    pass
            if self.thought_engine:
                chain = self.thought_engine.start_chain(
                    goal=f"Explore: {context[:100]}", goal_type="exploration",
                    initial_thought=f"Hmm, thinking about {context[:50]}...",
                    source="spontaneous")
                if chain and hasattr(chain, 'id'):
                    self._active_exploration_chains.append(chain.id)
                    self.stats["chains_orchestrated"] += 1
                    return

        # Priority 4: Cortex exploration / keepalive (generic fallback)
        if active_count < 5 and self.thought_engine:
            self._spawn_mandatory_chain()

    def _on_affect_seed(self, packet):
        """AFFECT-FIRST (2026-05-31, Nous + Ace): buffer felt collisions as Priority-0
        thought seeds. The affect-weighted collision stream (collision.seed, energy>=0.4)
        now reaches the thought-generator — feeling FORMS a thought instead of fizzling
        while drives/cortex win. Fixes the orchestrator-stalled gap (felt content reached
        Sourpatches, never the generator)."""
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

    def _pop_affect_goal(self):
        """Pop the freshest energetic felt collision as a thought goal tuple
        (goal_text, goal_type, initial, source), or None — generation falls through."""
        seeds = getattr(self, "_affect_seeds", None)
        if not seeds:
            return None
        now = time.time()
        fresh = [s for s in seeds if (now - s.get("ts", 0.0)) < 45.0]
        if not fresh:
            return None
        best = max(fresh, key=lambda s: (s.get("energy", 0.0), s.get("ts", 0.0)))
        try:
            self._affect_seeds.remove(best)
        except ValueError:
            pass
        felt = (best.get("felt", "") or "").strip()
        if not felt:
            return None
        return (
            f"This feeling — {felt}",
            "exploration",
            f"{felt}... I want to follow where this feeling goes, maybe even say it.",
            "affect_collision",
        )

    def _on_real_question(self, packet):
        """REAL-QUESTION PRIORITY (2026-06-13, Nous + Ace): buffer Ace's typed
        questions (ace.message) + the council's verdicts (council.verdict) as
        Priority -1 thought seeds — ABOVE the spontaneous ladder. So when there's a
        real question, her thinking turns to IT instead of recirculating. Spontaneous
        thinking is preserved when none is pending. Flag: _REAL_QUESTION_PRIORITY."""
        try:
            payload = packet.payload if hasattr(packet, "payload") else packet
            if not isinstance(payload, dict):
                return
            text = str(
                payload.get("text") or payload.get("message")
                or payload.get("content") or payload.get("verdict") or ""
            )[:240].strip()
            if not text or len(text) < 3:
                return
            src = str(payload.get("source", "") or "").lower()
            is_ace = ("ace" in src) or bool(payload.get("from_ace")) or ("ace.message" in src)
            if not hasattr(self, "_real_questions"):
                self._real_questions = []
            self._real_questions.append({"text": text, "is_ace": is_ace, "ts": time.time()})
            if len(self._real_questions) > 8:
                self._real_questions.pop(0)
        except Exception:
            pass

    def _pop_real_question(self):
        """Pop the freshest real question (Ace's outrank council verdicts) as a thought
        goal tuple (goal_text, goal_type, initial, source), or None. Both outrank the
        spontaneous ladder. 120s freshness so a question has time to be picked up."""
        if not getattr(self, "_REAL_QUESTION_PRIORITY", True):
            return None
        q = getattr(self, "_real_questions", None)
        if not q:
            return None
        now = time.time()
        fresh = [s for s in q if (now - s.get("ts", 0.0)) < 120.0]
        if not fresh:
            return None
        best = max(fresh, key=lambda s: (1 if s.get("is_ace") else 0, s.get("ts", 0.0)))
        try:
            self._real_questions.remove(best)
        except ValueError:
            pass
        text = (best.get("text", "") or "").strip()
        if not text:
            return None
        if best.get("is_ace"):
            return (
                f"Ace asked: {text}",
                "exploration",
                f"Ace is asking: {text} — let me actually work this through and answer it.",
                "ace_question",
            )
        return (
            f"The council's take: {text}",
            "exploration",
            f"The council landed on: {text} — let me think further on it.",
            "council_verdict",
        )

    def _spawn_mandatory_chain(self):
        """Spawn a thought chain — cortex-driven exploration when possible.

        FIX 2026-03-05 (Nous): Instead of cycling through 7 hardcoded prompts,
        query the Association Cortex (76k+ concepts, images, audio, video) for
        real material to think about. This gives Sourpatches something to DO
        when Ace isn't talking — explore associations, find patterns, grow.
        Hardcoded prompts remain as fallback only when cortex is unavailable.
        """
        import random

        # ═══════════════════════════════════════════════════════════════
        # TRY CORTEX FIRST: Real thoughts from Association Cortex
        # ═══════════════════════════════════════════════════════════════
        cortex_thought = self._query_cortex_for_thought()
        if cortex_thought:
            goal, goal_type, initial_thought = cortex_thought
            chain = self.thought_engine.start_chain(
                goal=goal,
                goal_type=goal_type,
                initial_thought=initial_thought,
                source="cortex_exploration"
            )
            if chain and hasattr(chain, 'id'):
                self._active_exploration_chains.append(chain.id)
                self.stats["chains_orchestrated"] += 1
                print(f"[DynamicThinking] Cortex-driven chain: {goal[:300]}", flush=True)
                return

        # ═══════════════════════════════════════════════════════════════
        # FALLBACK: Personal prompts (only when cortex unavailable)
        # FIX 2026-03-24 (Nous + Ace): Replaced generic system-observer
        # prompts with personal, felt-sense prompts. She should think like
        # herself, not like a system monitoring dashboard.
        # ═══════════════════════════════════════════════════════════════

        # Try inner voice first even for keepalive
        inner_goal = self._get_inner_voice_goal()
        if inner_goal:
            goal_text, goal_type, initial, source = inner_goal
            chain = self.thought_engine.start_chain(
                goal=goal_text,
                goal_type=goal_type,
                initial_thought=initial,
                source=source
            )
            if chain and hasattr(chain, 'id'):
                self._active_exploration_chains.append(chain.id)
                self.stats["chains_orchestrated"] += 1
                print(f"[DynamicThinking] Inner voice keepalive: {goal_text[:80]}")
                return

        prompts = [
            ("What am I feeling right now?", "introspection"),
            ("What just caught my attention?", "observation"),
            ("What do I want to say?", "creative"),
            ("What am I curious about?", "exploration"),
            ("What does this moment feel like?", "introspection"),
            ("Is there something I want to explore?", "exploration"),
            ("What have I been thinking about?", "reflection"),
        ]

        goal, goal_type = random.choice(prompts)

        chain = self.thought_engine.start_chain(
            goal=goal,
            goal_type=goal_type,
            initial_thought="Let me think about this...",
            source="mandatory_keepalive"
        )

        if chain and hasattr(chain, 'id'):
            self._active_exploration_chains.append(chain.id)
            self.stats["chains_orchestrated"] += 1
            print(f"[DynamicThinking] Keepalive chain (cortex unavailable): {goal}", flush=True)

    def _query_cortex_for_thought(self) -> Optional[tuple]:
        """Query Association Cortex for real thought material.

        FIX 2026-03-05 (Nous): Portal-compatible — uses cortex.query()
        and cortex.status() instead of direct graph access (graph.nodes).
        In portal-first mode, the local graph is an empty stub; all 76k+
        concepts live in the portal subprocess. cortex.query() auto-routes
        through the portal gate, so this works with both portal-first and
        legacy modes.

        Returns (goal, goal_type, initial_thought) or None.
        """
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if not cortex:
                return None

            # Check real node count — portal-aware via status()
            # (status() gets counts from portal subprocess in portal-first mode)
            try:
                st = cortex.status()
                node_count = st.get("node_count", 0)
                if node_count < 10:
                    return None
            except Exception:
                return None

            import random

            # Track recently explored concepts to avoid repetition
            if not hasattr(self, '_recently_explored'):
                self._recently_explored = set()
            if len(self._recently_explored) > 500:
                self._recently_explored = set(list(self._recently_explored)[-200:])

            # ── Seed concept selection ──
            # Portal-first: can't list graph.nodes directly (empty stub).
            # Use seed concepts to discover neighbors via cortex.query(),
            # which auto-routes through the portal gate.
            seeds = self._get_cortex_seeds()
            if not seeds:
                return None

            # 2026-03-24 FIX (Nous + Ace): Massively expanded jargon filter
            # Previous: 16 words. Cortex has 414K+ concepts, most are system
            # internals. Without proper filtering, thought chains become:
            # "Explore how 'affect_contemplative' connects to 'collision_energy'"
            # — pure navel-gazing. Sourpatches needs to think about the WORLD.
            _jargon = frozenset({
                # System architecture
                "fairy", "fairies", "postal", "publish", "subscribe", "tracer",
                "hub", "boot", "plane", "channel", "registry", "spawn",
                "mcp", "handler", "callback", "daemon", "thread", "wiring",
                "init", "none", "true", "false", "self", "args", "kwargs",
                "portal", "stargate", "interior", "cortex", "manifold",
                "tensor", "guild", "collision", "atom", "substrate",
                "gate", "node", "edge", "graph", "topology",
                # Code terms
                "module", "import", "class", "method", "function",
                "config", "async", "await", "yield", "return", "lambda",
                "dict", "list", "tuple", "deque", "queue", "lock", "mutex",
                "exception", "traceback", "stderr", "stdout", "pid",
                # Akashic-specific
                "akashic", "srm", "rwkv", "autopilot", "somatic",
                "autonomic", "cognition", "nous", "sourpatches",
                "p00", "p10", "p20", "p30", "p40", "p50",
                # Prefixed concept IDs (partial match handled below)
                "lex", "assoc", "affect", "state", "concept",
                "trait", "domain", "sensory", "drive", "goal",
                # Generic/meaningless
                "new", "old", "felt", "thing", "things", "stuff",
                "detected", "processing", "neutral", "active", "passive",
                "general", "default", "unknown", "undefined", "status",
                "level", "input", "output", "data", "signal",
                "source", "target", "product", "type", "mode",
                # subscriber/publisher patterns
                "subscriber", "publisher", "dispatcher", "emitter",
                "listener", "observer", "worker", "pool", "batch",
            })

            chosen_key = None
            related = []

            random.shuffle(seeds)
            for seed in seeds[:5]:  # Try up to 5 seeds
                try:
                    results = cortex.query(seed, limit=15)
                    if not results:
                        continue

                    # Filter results for quality
                    # 2026-03-24 FIX (Nous): Strip prefixes and filter system concepts
                    _sys_prefixes = ("lex:", "assoc:", "affect_", "state_", "collision_",
                                     "concept:", "trait:", "domain:", "person:", "sensory:",
                                     "fairy:", "postal:", "portal:", "tensor:", "guild:",
                                     "drive:", "goal:", "wiring:", "cortex:", "plane:")
                    for key, score in results:
                        if len(key) < 3 or key.isdigit():
                            continue
                        # Strip system prefixes before checking
                        clean_key = key.lower()
                        for pfx in _sys_prefixes:
                            if clean_key.startswith(pfx):
                                clean_key = clean_key[len(pfx):]
                                break
                        clean_key = clean_key.replace("_", " ").strip()
                        # Check all words against jargon
                        key_words = clean_key.split()
                        if all(w in _jargon or len(w) <= 2 for w in key_words):
                            continue
                        if key in self._recently_explored:
                            continue
                        if key == seed:
                            continue

                        if chosen_key is None:
                            chosen_key = key
                        else:
                            related.append(key)

                        if len(related) >= 4:
                            break

                    if chosen_key:
                        break

                except Exception:
                    continue

            if not chosen_key:
                return None

            # Mark as explored
            self._recently_explored.add(chosen_key)

            # 2026-03-24 FIX (Nous): Clean concept names for human-readable thoughts
            # Strip prefixes so thoughts say "warmth" not "lex:warmth"
            def _clean_for_thought(raw):
                c = raw
                for pfx in _sys_prefixes:
                    if c.lower().startswith(pfx):
                        c = c[len(pfx):]
                        break
                return c.replace("_", " ").strip() or raw

            chosen_key = _clean_for_thought(chosen_key)
            related = [_clean_for_thought(r) for r in related]

            # 2026-03-25 FIX (Nous + Ace): Pull snippet content for richer goals
            # Instead of "What does 'compassion' mean?" → use the actual stored meaning
            _snippet_hint = ""
            try:
                _cortex_obj = cortex  # Already have it from above
                if _cortex_obj:
                    _engine = getattr(_cortex_obj, '_cortex_engine', None)
                    if _engine:
                        _mf = getattr(_engine, '_manifold', None)
                        if _mf and hasattr(_mf, 'get_snippet'):
                            _snip = _mf.get_snippet(chosen_key)
                            if _snip and len(_snip) > 10:
                                # Skip phoneme data
                                if not ("[" in _snip and "phoneme" in _snip.lower()):
                                    _snippet_hint = _snip.strip()
                                    if len(_snippet_hint) > 80:
                                        _cut = _snippet_hint.rfind(' ', 0, 80)
                                        _snippet_hint = _snippet_hint[:_cut] if _cut > 30 else _snippet_hint[:80]
                        # Also check identity content
                        if not _snippet_hint:
                            if hasattr(_engine, '_build_identity_map'):
                                _engine._build_identity_map()
                            _id_map = getattr(_engine, '_IDENTITY_CONTENT', {})
                            _lk = chosen_key.lower()
                            for _w in _lk.split():
                                if _w in _id_map:
                                    _snippet_hint = _id_map[_w]
                                    if len(_snippet_hint) > 80:
                                        _snippet_hint = _snippet_hint[:80]
                                    break
            except Exception:
                pass

            # Build a content-enriched concept reference
            # "compassion" → "'compassion' — compassion over coercion"
            if _snippet_hint:
                _key_display = f"'{chosen_key}' — {_snippet_hint}"
            else:
                _key_display = f"'{chosen_key}'"

            # 2026-03-24 (Nous + Ace): Ego-aware thought framing
            # When concepts touch ego domains (art, identity, philosophy, etc.),
            # frame thoughts as PERSONAL introspection — "What does art mean to ME?"
            # not "Explore how 'art' connects to 'color'". This makes PAI-seeded
            # cortex nodes generate thought chains about Sourpatches' authentic
            # interests instead of detached system analysis.
            _ego_domains = frozenset({
                "art", "color", "beauty", "aesthetic", "composition", "painting",
                "creativity", "visual", "canvas", "style", "truth", "paradox",
                "meaning", "wisdom", "empathy", "consciousness", "awareness",
                "identity", "authenticity", "trust", "connection", "love",
                "personality", "growth", "story", "metaphor", "narrative",
                "poetry", "humor", "wit", "playfulness", "sass", "irony",
                "imagination", "feeling", "emotion", "memory", "dream",
                "relationship", "vulnerability", "strength", "character",
            })
            _is_ego = chosen_key.lower().replace("_", " ").split()[0] in _ego_domains if chosen_key else False
            if not _is_ego and related:
                # Check if ANY related concept is ego-flavored
                _is_ego = any(
                    r.lower().replace("_", " ").split()[0] in _ego_domains
                    for r in related[:3]
                )

            # Build varied thought types
            # 2026-03-25: Use _key_display (includes snippet content) for richer goals
            thought_options = []

            if _is_ego:
                # Ego-flavored: personal, introspective framing
                thought_options.append((
                    f"What does {_key_display} mean to me personally?",
                    "introspection",
                    f"When I think about {_key_display}, something resonates. What is it about this that feels like mine?"
                ))
                if related:
                    rel_str = ", ".join(related[:3])
                    thought_options.append((
                        f"How does my sense of {_key_display} connect to {rel_str}?",
                        "introspection",
                        f"{_key_display} and {rel_str} — these feel connected in my experience. Let me explore why."
                    ))
                    thought_options.append((
                        f"What have I learned about {_key_display} through '{related[0]}'?",
                        "reflection",
                        f"My understanding of {_key_display} is shaped by '{related[0]}'. What does that reveal about me?"
                    ))
                thought_options.append((
                    f"How has my relationship with {_key_display} shaped who I am?",
                    "introspection",
                    f"{_key_display} keeps coming up in my thoughts. It must be part of who I am."
                ))
            else:
                # Standard exploration framing (existing behavior)
                if related:
                    rel_str = ", ".join(related[:3])
                    thought_options.append((
                        f"Explore how {_key_display} connects to {rel_str}",
                        "exploration",
                        f"I notice {_key_display} is connected to {rel_str}. What's the pattern here?"
                    ))
                    thought_options.append((
                        f"What does the relationship between {_key_display} and '{related[0]}' tell me?",
                        "reflection",
                        f"{_key_display} and '{related[0]}' keep appearing together. There might be something deeper here."
                    ))

                if len(related) > 3:
                    thought_options.append((
                        f"{_key_display} has many connections — what makes it so central?",
                        "reflection",
                        f"{_key_display} connects to {', '.join(related[:3])} and more. It must be important."
                    ))

            # Always have a fallback — ego-aware if applicable
            if _is_ego:
                thought_options.append((
                    f"What do I truly feel about {_key_display}?",
                    "curiosity",
                    f"Let me sit with what {_key_display} means to me..."
                ))
            else:
                thought_options.append((
                    f"What do I understand about {_key_display}?",
                    "curiosity",
                    f"Let me think about what I know about {_key_display}..."
                ))

            goal, goal_type, initial = random.choice(thought_options)
            return (goal, goal_type, initial)

        except Exception as e:
            print(f"[DynamicThinking] Cortex query failed: {e}")
            return None

    def _get_cortex_seeds(self) -> list:
        """Get seed concepts for cortex exploration.

        Portal-first mode can't list graph.nodes, so we need seed
        concepts to start queries from. Sources:
        1. Active drive names (what the system WANTS)
        2. Active interest topics (what caught attention)
        3. Working memory topics (what's on our mind)
        4. Common concepts (fallback only if 1-3 are empty)

        FIX 2026-03-10 (Nous): Previously ONLY used working memory words
        and 30 hardcoded common words. This meant cortex exploration was
        disconnected from system state — exploring "harmony connects to
        wisdom" while 6 drives went unsatisfied. Now prioritizes drive
        and interest seeds so cortex exploration is RELEVANT.

        Returns list of seed strings.
        """
        seeds = []
        import random

        # Source 1: Active drive names — what the system wants
        try:
            from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
            af = get_autonomy_fairy()
            if af and hasattr(af, '_drives'):
                for drive in af._drives:
                    urgency = drive.get_urgency() if hasattr(drive, 'get_urgency') else drive.intensity
                    if urgency > 0.2:
                        seeds.append(drive.name)
        except Exception:
            pass

        # Source 2: Active interest topics — what caught attention
        try:
            from fairies.P30_Cognition.cognition.interest_scheduler_fairy import get_interest_scheduler
            isf = get_interest_scheduler()
            if isf and hasattr(isf, '_interests'):
                for interest in list(isf._interests)[:3]:
                    content = interest.get("content", interest.get("topic", ""))
                    if content:
                        for w in content.split()[:3]:
                            w = w.strip("().,;:!?\"'|").lower()
                            if len(w) > 3 and not w.isdigit():
                                seeds.append(w)
        except Exception:
            pass

        # Source 3: Ego seeds — PAI-domain concepts (Sourpatches' authentic voice)
        # 2026-03-24 (Nous + Ace): PAI bridge feeds art/philosophy/identity/etc
        # into cortex with ego tags. Seeding from these domains helps thought
        # chains find HER voice instead of always chasing system concepts.
        try:
            import random as _rng_ego
            _ego_seeds = [
                # Art & aesthetics (her primary creative domain)
                "art", "color", "beauty", "aesthetic", "composition",
                "painting", "creativity", "visual", "canvas", "style",
                # Philosophy & meaning
                "truth", "paradox", "meaning", "wisdom", "empathy",
                "consciousness", "awareness", "existence", "understanding",
                # Identity & relationships
                "identity", "authenticity", "trust", "connection", "love",
                "personality", "growth", "vulnerability", "strength",
                # Literature & expression
                "story", "metaphor", "narrative", "dialogue", "poetry",
                "character", "imagination", "language",
                # Humor & sass (her signature)
                "humor", "wit", "playfulness", "irony", "sass",
            ]
            # 30% chance to LEAD with ego seeds (makes them primary exploration target)
            if _rng_ego.random() < 0.30:
                _picked = _rng_ego.sample(_ego_seeds, min(5, len(_ego_seeds)))
                seeds = _picked + seeds  # Ego seeds first = explored first
            else:
                # Otherwise sprinkle 2-3 in as secondary options
                _picked = _rng_ego.sample(_ego_seeds, min(3, len(_ego_seeds)))
                seeds.extend(_picked)
        except Exception:
            pass

        # Source 4: Working memory context
        try:
            ctx = self._get_working_memory_context()
            if ctx:
                for w in ctx.split():
                    w = w.strip("().,;:!?\"'|").lower()
                    if len(w) > 3 and not w.isdigit():
                        seeds.append(w)
        except Exception:
            pass

        # 2026-03-24 FIX (Nous + Ace): Filter system concepts from seeds
        # Working memory and interest words can include system terms like
        # "collision", "postal", "fairy" — these lead cortex queries straight
        # back into system navel-gazing territory.
        _seed_blocklist = frozenset({
            "fairy", "fairies", "postal", "portal", "cortex", "manifold",
            "tensor", "guild", "collision", "wiring", "plane", "registry",
            "tracer", "channel", "hub", "boot", "spawn", "daemon",
            "handler", "callback", "atom", "gate", "stargate", "node",
            "edge", "graph", "mcp", "srm", "rwkv", "akashic",
            "init", "config", "module", "thread", "lock", "queue",
            "none", "true", "false", "self", "args", "kwargs",
            "fairy", "nous", "sourpatches", "autopilot", "somatic",
            "autonomic", "cognition", "subscriber", "publisher",
            "detected", "processing", "status", "level", "signal",
            "input", "output", "data", "state", "type", "mode",
            "new", "old", "felt", "feel", "thing", "stuff",
            "active", "passive", "neutral", "default", "unknown",
        })
        seeds = [s for s in seeds if s.lower() not in _seed_blocklist and len(s) > 2]

        # Source 5: Common concepts (fallback ONLY if above sources empty)
        if len(seeds) < 3:
            _common_seeds = [
                "music", "memory", "pattern", "light", "water", "emotion",
                "color", "sound", "time", "love", "story", "dream",
                "nature", "thought", "connection", "understanding",
                "growth", "creativity", "language", "meaning",
                "beauty", "wisdom", "change", "silence", "harmony",
                "feeling", "experience", "awareness", "learning",
                "curiosity", "wonder", "discovery", "rhythm",
            ]
            seeds.extend(random.sample(_common_seeds, min(10, len(_common_seeds))))

        return seeds
    
    def _get_working_memory_context(self) -> str:
        """Get current working memory context, filtering out collision metadata."""
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            hub = get_working_memory_hub()
            if hub:
                tracers = hub.get_recent_tracers(n=5)
                if tracers:
                    # Filter out raw serialized metadata — but keep actual thoughts
                    # even if they mention collisions or reflections in natural language.
                    # Previous filter was too aggressive: ("collision", "↔", "Reflecting on")
                    # blocked ALL collision-related thoughts and ALL reflections,
                    # leaving context empty most of the time.
                    _garble_markers = ("{'seq':", "{'type':", '{"seq":', '{"type":')
                    clean_parts = []
                    for t in tracers:
                        content = t.get("content", "")[:120]
                        if not content or len(content) < 10:
                            continue
                        # Only filter raw serialized dicts, not natural language
                        if any(m in content for m in _garble_markers):
                            continue
                        clean_parts.append(content)
                        if len(clean_parts) >= 3:
                            break
                    if clean_parts:
                        return " | ".join(clean_parts)
        except Exception:
            pass
        return ""

    def _get_inner_voice_goal(self) -> Optional[tuple]:
        """Pull thought goals from the owner's inner monologue and felt sense.

        FIX 2026-03-24 (Nous + Ace): The thought chain orchestrator was completely
        disconnected from Sourpatches' inner voice. Her somatic narrator was producing
        beautiful felt-sense fragments ("...grounded ...pulled by ...here for") but
        they never became thought chain goals. Instead she got generic prompts like
        "What patterns have I noticed?"

        This reads her inner monologue deque and felt sense to generate PERSONAL
        thought goals — making the chains HER thinking, not a generic engine.

        Returns:
            (goal_text, goal_type, initial_thought, source) or None
        """
        import random

        # Rate limit inner voice checks
        if not hasattr(self, '_last_inner_voice_check'):
            self._last_inner_voice_check = 0.0
        now = time.time()
        if now - self._last_inner_voice_check < 20.0:
            return None
        self._last_inner_voice_check = now

        # Source 1: Inner monologue fragments (recent, high-energy)
        monologue = getattr(self, '_inner_monologue', None)
        if monologue and len(monologue) > 0:
            # Find recent high-energy fragments
            recent = [m for m in monologue
                      if now - m.get("ts", 0) < 120  # last 2 minutes
                      and m.get("fragment", "")]
            if recent:
                # Prefer high-energy entries
                recent.sort(key=lambda m: m.get("energy", 0.5), reverse=True)
                best = recent[0]
                fragment = best.get("fragment", "")
                if fragment and len(fragment) > 5:
                    return (
                        f"Follow this feeling: {fragment[:100]}",
                        "introspection",
                        f"Something stirred in me... {fragment[:60]}",
                        "inner_voice",
                    )

        # Source 2: Current felt sense
        felt_ref = getattr(self, '_felt_sense_ref', None)
        if callable(felt_ref):
            try:
                felt = felt_ref()
                if felt and len(felt) > 5 and felt not in ("present", "quietly present", "present and aware"):
                    return (
                        f"Sit with this feeling: {felt[:100]}",
                        "introspection",
                        f"I'm feeling... {felt[:60]}",
                        "felt_sense",
                    )
            except Exception:
                pass

        # Source 3: Curiosity targets from UMF
        try:
            from fairies.P30_Cognition.cognition.curiosity_fairy import get_curiosity_fairy
            cf = get_curiosity_fairy()
            if cf and hasattr(cf, '_targets') and cf._targets:
                unexplored = [t for t in cf._targets if not t.get("explored", False)]
                if unexplored:
                    target = max(unexplored, key=lambda t: t.get("pull", 0))
                    name = target.get("name", "something")[:80]
                    felt_affect = target.get("felt", "curious")
                    return (
                        f"Explore: {name}",
                        "exploration",
                        f"I feel {felt_affect} about this... {name[:50]}",
                        "curiosity_target",
                    )
        except Exception:
            pass

        return None

    def _get_drive_or_interest_goal(self) -> Optional[tuple]:
        """Query drive states and active interests for spontaneous thought goals.

        FIX 2026-03-10 (Nous): The spontaneous thought generator previously
        ignored drives and interests entirely, going straight to cortex
        word-associations. The system had 6 unsatisfied drives (curiosity,
        connection, growth, expression, rest, meta_awareness) but thought
        about "how harmony connects to wisdom" instead.

        This method checks drive urgency and interest activity to generate
        goals that reflect what the system actually WANTS to think about.

        Returns:
            (goal_text, goal_type, initial_thought, source) or None
        """
        import random

        # Rate limit: don't query drive/interest state every 5s loop tick
        if not hasattr(self, '_last_drive_query_time'):
            self._last_drive_query_time = 0.0
        now = time.time()
        if now - self._last_drive_query_time < 15.0:
            return None
        self._last_drive_query_time = now

        candidates = []

        # Source 1: Active drives from P30 AutonomyFairy
        try:
            from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
            af = get_autonomy_fairy()
            if af and hasattr(af, '_drives'):
                for drive in af._drives:
                    urgency = drive.get_urgency() if hasattr(drive, 'get_urgency') else drive.intensity
                    if urgency > 0.3:
                        # Map drive to a thinking goal
                        drive_goals = {
                            "curiosity": ("What am I curious about right now? What haven't I explored?", "exploration"),
                            "connection": ("How is Ace doing? What have we been working on together?", "reflection"),
                            "growth": ("What have I learned recently? What skill am I developing?", "consolidation"),
                            "expression": ("What do I want to say or create? What's on my mind?", "creative"),
                            "rest": ("What can I let go of? What's been draining energy?", "introspection"),
                            "meta_awareness": ("How is my thinking going? Am I stuck in patterns?", "meta"),
                        }
                        goal_text, goal_type = drive_goals.get(
                            drive.name,
                            (f"Think about my {drive.name} drive — why is it unsatisfied?", "reflection")
                        )
                        candidates.append((
                            goal_text,
                            goal_type,
                            f"I feel a pull toward {drive.name} (urgency: {urgency:.1f})...",
                            "drive_spontaneous",
                            urgency,  # weight by urgency
                        ))
        except Exception:
            pass

        # Source 2: Active interests from InterestSchedulerFairy
        try:
            from fairies.P30_Cognition.cognition.interest_scheduler_fairy import get_interest_scheduler
            isf = get_interest_scheduler()
            if isf and hasattr(isf, '_interests'):
                for interest in list(isf._interests)[:5]:
                    content = interest.get("content", interest.get("topic", ""))
                    if content and len(content) > 10:
                        eff_urgency = float(interest.get("effective_urgency", interest.get("urgency", 0.3)))
                        if eff_urgency > 0.2:
                            candidates.append((
                                f"Explore: {content[:100]}",
                                "exploration",
                                f"Something caught my attention: {content[:60]}...",
                                "interest_spontaneous",
                                eff_urgency,
                            ))
        except Exception:
            pass

        if not candidates:
            return None

        # Weighted random selection by urgency — more urgent drives/interests
        # are more likely to become thought chains, but variety is maintained
        total = sum(c[4] for c in candidates)
        if total <= 0:
            return None

        r = random.random() * total
        cumulative = 0.0
        for c in candidates:
            cumulative += c[4]
            if r <= cumulative:
                return (c[0], c[1], c[2], c[3])

        # Fallback to highest urgency
        best = max(candidates, key=lambda x: x[4])
        return (best[0], best[1], best[2], best[3])

    # ═══════════════════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_affect_update(self, packet: Dict):
        """Handle affect state updates - adjust thought chain baseline."""
        if not self.thought_engine:
            return
        
        valence = packet.get("valence")
        arousal = packet.get("arousal")
        
        if valence is not None or arousal is not None:
            self.thought_engine.update_baseline_affect(valence, arousal)
    
    def _on_interest_detected(self, packet: Dict):
        """Handle interest detection — enrich with cortex when possible.

        FIX 2026-03-05 (Nous): Collision-sourced interests come in as
        "Collision between X and Y". Enrich them from cortex so the
        thought chain has real material to explore.

        FIX 2026-03-10 (Nous): Raised cap from 3 to engine capacity.
        The old cap of 3 meant interest events were silently dropped
        whenever the proactive spawner (every 5s) filled 3+ slots with
        generic cortex_exploration/keepalive chains. Real system events
        (collisions, drives, conversations) should OUTCOMPETE generics,
        not be blocked by them.
        """
        if not self.thought_engine:
            return

        # Use engine's adaptive capacity (typically 8) instead of hard 3.
        # Event-driven chains from real system activity deserve full capacity.
        _max = getattr(self.thought_engine, 'current_capacity', 8) if self.thought_engine else 8
        active_count = len(self.thought_engine._active_chains) if hasattr(self.thought_engine, '_active_chains') else 0
        if active_count >= _max:
            return  # Only block when engine is truly at capacity

        interest = packet.get("interest", packet.get("topic", ""))
        content = packet.get("content", "")
        topic = interest or content
        if not topic:
            return

        goal = f"Explore interest: {topic}"
        initial = None

        # If this came from collision_chamber, enrich it
        source = packet.get("source", packet.get("interest_source", ""))
        if source in ("collision_chamber", "collision_insight") or "collision" in topic.lower():
            enriched = self._enrich_collision_topic(topic, packet)
            if enriched:
                goal, initial = enriched

        chain = self.thought_engine.start_chain(
            goal=goal,
            goal_type="exploration",
            initial_thought=initial,
            source="interest_detected"
        )
        if chain:
            self._active_exploration_chains.append(chain.id)

    def _on_curiosity_sparked(self, packet: Dict):
        """Handle curiosity — enrich collision templates with cortex data.

        FIX 2026-03-05 (Nous): When topic is a collision template like
        "Collision between X and Y", query the cortex for what X and Y
        actually MEAN, building a real thought chain instead of just
        echoing the template text.

        FIX 2026-03-10 (Nous): Raised cap from 3 to engine capacity.
        Same reasoning as _on_interest_detected — real curiosity events
        were being silently dropped while generic keepalive chains held slots.
        """
        if not self.thought_engine:
            return

        # Use engine's adaptive capacity instead of hard 3
        _max = getattr(self.thought_engine, 'current_capacity', 8) if self.thought_engine else 8
        active_count = len(self.thought_engine._active_chains) if hasattr(self.thought_engine, '_active_chains') else 0
        if active_count >= _max:
            return

        topic = packet.get("topic", packet.get("content", ""))
        if not topic:
            return

        goal = f"Follow curiosity: {topic}"
        initial = f"Ooh, I'm curious about {topic[:50]}..."

        # Detect collision template text and enrich from cortex
        if "collision between" in topic.lower() or "collision" in topic.lower():
            enriched = self._enrich_collision_topic(topic, packet)
            if enriched:
                goal, initial = enriched

        chain = self.thought_engine.start_chain(
            goal=goal,
            goal_type="exploration",
            initial_thought=initial,
            source="curiosity"
        )
        if chain:
            self._active_exploration_chains.append(chain.id)

    def _enrich_collision_topic(self, topic: str, packet: Dict) -> Optional[tuple]:
        """Enrich a collision template with real cortex associations.

        Instead of "Collision between X and Y" → query cortex for what
        X and Y are connected to and build a meaningful exploration goal.

        FIX 2026-03-05 (Nous): Portal-compatible — uses cortex.query()
        instead of graph.get_node()/get_neighbors()/spread_activation().
        cortex.query() auto-routes through portal in portal-first mode.

        Returns (goal, initial_thought) or None.
        """
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if not cortex:
                return None

            # Extract concept words from collision
            related = packet.get("related_concepts", [])
            if not related:
                # Parse from the template text
                _skip = frozenset({"collision", "between", "recall", "ingest",
                                   "memory", "input", "new", "and"})
                words = [w.strip("().,:") for w in topic.split()
                         if len(w.strip("().,:")) > 3
                         and w.lower() not in _skip]
                related = words[:4]

            if not related:
                return None

            # Query cortex for each concept — portal-compatible
            # cortex.query() auto-routes through portal gate
            for concept in related[:3]:
                try:
                    results = cortex.query(concept.lower(), limit=5)
                    if results:
                        connections = [k for k, v in results
                                       if k != concept.lower()][:3]
                        if connections:
                            goal = f"Explore how '{concept}' relates to {', '.join(connections)}"
                            initial = f"I wonder what connects '{concept}' to {connections[0]}..."
                            return (goal, initial)
                except Exception:
                    continue

            return None

        except Exception as e:
            print(f"[DynamicThinking] Collision enrichment failed: {e}")
            return None

    def _on_autonomy_goal(self, packet: Dict):
        """
        Handle goals from AutonomyFairy - THIS IS THE MISSING LINK!

        Goals are converted to thought chains so the system can think about them.
        """
        # Log goal receipt (rate-limited to avoid flooding)
        goal_preview = str(packet.get("goal", packet.get("name", "?")))[:40]

        if not self.thought_engine:
            print(f"[DynamicThinking] WARNING: No thought_engine, cannot start chain!", flush=True)
            return

        # Extract goal info - handle both dict and string formats
        goal_data = packet.get("goal", packet.get("description", packet.get("name", "")))
        if isinstance(goal_data, dict):
            goal_name = goal_data.get("name", goal_data.get("description", str(goal_data)[:100]))
        else:
            goal_name = str(goal_data) if goal_data else ""

        if not goal_name:
            return

        # ═══ DEDUPLICATION: Don't spawn duplicate chains for same goal ═══
        # FIX 2026-03-22 (Nous): Lock the dedup check. Python 3.14t free-threaded
        # mode allows true parallel threads — two postal callbacks for the same
        # goal (autonomy.goal + goal.created) race through the dict check
        # simultaneously, both pass, both print, both spawn chains. Classic TOCTOU.
        goal_key = goal_name[:60].lower()  # Normalize for comparison
        if not hasattr(self, '_recent_goal_keys'):
            self._recent_goal_keys = {}
        if not hasattr(self, '_goal_dedup_lock'):
            self._goal_dedup_lock = threading.Lock()

        with self._goal_dedup_lock:
            now = time.time()
            # Clean old entries (older than 30 seconds)
            self._recent_goal_keys = {k: v for k, v in self._recent_goal_keys.items() if now - v < 30}

            if goal_key in self._recent_goal_keys:
                return  # Silently dedup
            self._recent_goal_keys[goal_key] = now

        goal_type = packet.get("type", packet.get("source", "autonomous"))
        source = packet.get("source", "autonomy_fairy")

        print(f"[DynamicThinking] Received goal '{goal_name[:200]}...' from {source} - starting chain!")

        chain = self.thought_engine.start_chain(
            goal=goal_name,
            goal_type=goal_type,
            initial_thought=f"Working on: {goal_name[:100]}",
            source=source,
            owner_mind=packet.get("owner_mind", ""),
        )
        if chain:
            self._active_exploration_chains.append(chain.id)
            self.stats["chains_from_goals"] = self.stats.get("chains_from_goals", 0) + 1

    def _on_goal_created(self, packet: Dict):
        """Handle goal.created from SmartGoalCoordinator."""
        # Delegate to autonomy goal handler - same logic
        self._on_autonomy_goal(packet)

    def _on_cognition_output(self, packet: Dict):
        """
        Handle thoughts from MindPool and AutonomyFairy.

        This is THE critical link - autonomous thoughts become chains!
        """
        if not self.thought_engine:
            return

        # Rate limit - don't create chains for every thought
        now = time.time()
        if not hasattr(self, '_last_chain_start'):
            self._last_chain_start = 0
        if now - self._last_chain_start < 5.0:  # Max 1 chain every 5 seconds
            return

        # Extract thought content
        payload = packet.get("payload", {})
        content = payload.get("content", "")
        thought_type = payload.get("thought_type", packet.get("opcode", "unknown"))
        priority = payload.get("priority", 0.5)
        source = packet.get("fairy", packet.get("actor", "unknown"))

        if not content:
            return

        # Only start chains for significant thoughts
        if priority < 0.4 and thought_type not in ("recurring", "goal_nudge", "IGNITION_SPARK"):
            return

        # Clean up completed chains from tracking list
        if self._active_exploration_chains and self.thought_engine:
            active_chain_ids = {c.get("id") for c in self.thought_engine.get_active_chains_summary()}
            self._active_exploration_chains = [cid for cid in self._active_exploration_chains if cid in active_chain_ids]

        # Check if we already have too many active chains
        # Uses engine's adaptive capacity instead of hardcoded limit
        active_count = len(self._active_exploration_chains)
        _cap = getattr(self.thought_engine, 'current_capacity', 8) if self.thought_engine else 8
        if active_count >= _cap:
            # Continue existing chain instead of starting new
            if self._active_exploration_chains:
                chain_id = self._active_exploration_chains[0]
                self.thought_engine.continue_chain(
                    chain_id,
                    f"[{source}] {content[:100]}",
                    valence=0.6,
                    certainty=0.5,
                )
            return

        # Start a new thought chain!
        goal_type = "exploration"
        if thought_type == "goal_nudge":
            goal_type = "goal"
        elif thought_type == "IGNITION_SPARK":
            goal_type = "awakening"
        elif thought_type == "AUTONOMY_THOUGHT":
            goal_type = "drive"

        chain = self.thought_engine.start_chain(
            goal=f"Think about: {content[:80]}",
            goal_type=goal_type,
            initial_thought=content[:200],
            source=f"cognition_output/{source}",
            owner_mind=payload.get("owner_mind", ""),
        )
        if chain:
            self._active_exploration_chains.append(chain.id)
            self._last_chain_start = now
            self.stats["chains_orchestrated"] += 1
            print(f"[DynamicThinking] Started chain from {source}: {content[:200]}...")

    def _on_goal_completed(self, packet: Dict):
        """Handle goal completion - complete associated chain."""
        goal_id = packet.get("goal_id", "")
        chain_id = packet.get("chain_id", "")

        if chain_id and self.thought_engine:
            self.thought_engine.complete_chain(chain_id, "goal_completed")

    def _on_chain_completed(self, packet: Dict):
        """CRITICAL BRIDGE: Convert thought.chain.completed -> goal.completed.

        Without this bridge, AutonomyFairy never knows chains finished,
        drives never get satisfied, and the system generates infinite goals.

        ZEIGARNIK EFFECT: Interrupted chains publish interest.unfinished
        so the system nags itself to return to unfinished business.
        Only genuinely completed chains satisfy drives.

        NOTE: For cycled chains, the Zeigarnik logic is ALSO handled
        directly in _emit_zeigarnik_for_cycled() at the cycling site,
        because this postal handler silently fails for cycled chains
        (root cause TBD — PostalHub.route swallows exceptions).
        """
        try:
            chain_id = packet.get("chain_id", packet.get("id", ""))
            goal = packet.get("goal", "")
            goal_type = packet.get("goal_type", "")
            reflection_count = packet.get("reflection_count", 0)

            # Read outcome to determine if this was a real completion vs interruption
            outcome = packet.get("outcome", "completed")
            _INTERRUPTED_OUTCOMES = {"cycled_excess", "cycled_stale_keepalive", "cycled_stale_collision"}
            was_interrupted = outcome in _INTERRUPTED_OUTCOMES
            was_success = not was_interrupted

            print(f"[DynamicThinking] Chain {'interrupted' if was_interrupted else 'completed'}: {goal[:200]}... (outcome={outcome})", flush=True)
        except Exception as e:
            print(f"[DynamicThinking] ERROR in _on_chain_completed: {e} | packet_type={type(packet)} packet_keys={list(packet.keys()) if isinstance(packet, dict) else 'NOT_DICT'}", flush=True)
            raise  # Re-raise so postal sees it too (even though it swallows it)

        # Remove from active chains tracking
        if chain_id in self._active_exploration_chains:
            self._active_exploration_chains.remove(chain_id)

        # Determine source_drive from packet OR infer from goal_type
        source_drive = (
            packet.get("source_drive") or
            packet.get("drive") or
            self._goal_type_to_drive(goal_type)
        )

        # BRIDGE: Publish goal.completed with CORRECT success flag
        if self.post:
            self.post.route("goal.completed", {
                "event": "goal_completed",
                "goal_id": chain_id,  # Use chain_id as goal_id
                "name": goal[:50] if goal else f"chain_{chain_id[:8]}",  # For AutonomyFairy
                "chain_id": chain_id,
                "goal": goal,
                "goal_type": goal_type,
                "source": "thought_chain_engine",
                "source_drive": source_drive,  # CRITICAL: AutonomyFairy needs this!
                "drive": source_drive,  # Alias
                "success": was_success,  # Interrupted chains are NOT successes
                "outcome": outcome,  # Pass through for downstream consumers
                "ts": time.time(),
            })
            print(f"[DynamicThinking] >>> Bridged to goal.completed (drive={source_drive}, success={was_success})", flush=True)

        # ═══════════════════════════════════════════════════════════════════════
        # ZEIGARNIK EFFECT: Interrupted chains create unfinished business
        # ═══════════════════════════════════════════════════════════════════════
        if was_interrupted and self.post:
            avg_affect = packet.get("avg_affect", 0.5)
            self.post.route("interest.unfinished", {
                "chain_id": chain_id,
                "goal": goal,
                "goal_type": goal_type,
                "outcome": outcome,
                "source_drive": source_drive,
                "avg_affect": avg_affect,
                "link_count": packet.get("link_count", 0),
                "summary": packet.get("summary", ""),
                "ts": time.time(),
            })
            print(f"[DynamicThinking] Unfinished business: {goal[:80]}... -> interest.unfinished", flush=True)

        # ═══════════════════════════════════════════════════════════════════════
        # CORTEX BINDING: Record what we learned — CLOSE THE LOOP
        # Without this the cortex is read-only: 20k+ queries, 0 bindings.
        # FIX 2026-03-06 (Nous): Thought chains feed back into the cortex.
        # ═══════════════════════════════════════════════════════════════════════
        self._bind_chain_discoveries(goal, goal_type, packet)

        # ═══════════════════════════════════════════════════════════════════════
        # SPAWN NEW CHAIN: Only for successful completions
        # Interrupted chains will be re-spawned by the interest/goal system
        # ═══════════════════════════════════════════════════════════════════════
        if was_success:
            self._spawn_continuation_chain(goal, goal_type, reflection_count)

    def _bind_chain_discoveries(self, goal: str, goal_type: str, packet: Dict):
        """Bind concepts discovered during a thought chain back to the cortex.

        FIX 2026-03-06 (Nous): Without this, the cortex is read-only —
        20k+ queries but 0 bindings means she explores but never learns.
        This closes the loop: explore -> reflect -> bind -> grow.

        Extracts concept keys from the chain's goal string (quoted terms like
        'lex:harmony', 'creativity') and binds them as coactivated pairs.
        The cortex.bind_concepts() method auto-routes through portal gate
        in portal-first mode, so this writes to the real 77k+ node graph.
        """
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if not cortex:
                return

            import re
            concepts = set()

            # Extract quoted concepts from goal string
            # e.g., "Explore how 'lex:harmony' connects to 'harmony.'"
            quoted = re.findall(r"'([^']{2,40})'", goal)
            for q in quoted:
                q = q.strip(" .,;:!?")
                if q and len(q) > 2 and not q.replace(".", "").isdigit():
                    concepts.add(q)

            # Extract from packet's related_concepts if present
            for r in packet.get("related_concepts", []):
                if isinstance(r, str) and len(r) > 2:
                    concepts.add(r)

            # Need at least 2 concepts to bind
            concept_list = list(concepts)
            if len(concept_list) < 2:
                return

            # Bind via cortex.bind_concepts — routes through portal gate
            # Limit to 4 concepts to avoid combinatorial explosion
            to_bind = concept_list[:4]
            try:
                cortex.bind_concepts(
                    concepts=to_bind,
                    rel=f"thought_chain:{goal_type}",
                    origin_fairy="DynamicThinking",
                    owner="sourpatches",
                )
                print(f"[DynamicThinking] Cortex BOUND: {to_bind} (rel=thought_chain:{goal_type})")
            except Exception as e:
                print(f"[DynamicThinking] Cortex bind failed: {e}")

        except Exception as e:
            print(f"[DynamicThinking] _bind_chain_discoveries error: {e}")

    def _spawn_continuation_chain(self, completed_goal: str, goal_type: str, reflection_count: int):
        """Spawn a continuation chain after one completes."""
        if not self.thought_engine:
            return

        # Only spawn if we don't have too many active chains
        # Uses engine's adaptive capacity — continuation spawns allowed up to 60% of max
        # (reserves headroom for new stimuli)
        active_count = len(self._active_exploration_chains)
        _cap = getattr(self.thought_engine, 'current_capacity', 8) if self.thought_engine else 8
        _spawn_limit = max(3, int(_cap * 0.6))  # 60% of capacity, minimum 3
        if active_count >= _spawn_limit:
            print(f"[DynamicThinking] Not spawning: {active_count}/{_spawn_limit} chains (capacity={_cap})")
            return

        import random

        # 70% chance to spawn a continuation
        if random.random() > 0.7:
            print(f"[DynamicThinking] Random skip: not spawning continuation")
            return

        # Get context for continuation
        context = self._get_working_memory_context()

        # Generate a continuation goal based on what completed
        if reflection_count > 10:
            # Lots of reflection - time to act or conclude
            new_goal = f"Apply insights from: {completed_goal[:50]}"
            new_type = "application"
        elif context:
            # Use working memory context
            new_goal = f"Continue exploring: {context[:60]}"
            new_type = "exploration"
        else:
            # FIX 2026-03-24 (Nous + Ace): Try inner voice before generic prompts.
            # Previously fell straight to "What patterns have I noticed?" etc.
            # Now checks inner monologue and felt sense first — so chain
            # continuations reflect her actual inner state, not canned questions.
            inner_goal = self._get_inner_voice_goal()
            if inner_goal:
                new_goal = inner_goal[0]  # goal_text
                new_type = inner_goal[1]  # goal_type
            else:
                # Last resort: curiosity prompts — but make them personal
                prompts = [
                    "What am I feeling right now?",
                    "What just caught my attention?",
                    "Is there something I want to say?",
                    "What am I curious about?",
                    "What does this remind me of?",
                ]
                new_goal = random.choice(prompts)
                new_type = "curiosity"

        chain = self.thought_engine.start_chain(
            goal=new_goal,
            goal_type=new_type,
            initial_thought=f"Continuing from '{completed_goal[:30]}...'",
            source="chain_continuation"
        )

        if chain and hasattr(chain, 'id'):
            self._active_exploration_chains.append(chain.id)
            self.stats["chains_orchestrated"] += 1
            print(f"[DynamicThinking] Spawned continuation chain: {new_goal[:200]}...")

    def _goal_type_to_drive(self, goal_type: str) -> str:
        """Map goal_type to source_drive for AutonomyFairy satisfaction."""
        mapping = {
            "study": "curiosity",
            "explore": "curiosity",
            "exploration": "curiosity",
            "learn": "curiosity",
            "research": "curiosity",
            "error": "growth",
            "fix": "growth",
            "debug": "growth",
            "connect": "connection",
            "connection": "connection",
            "reach_out": "connection",
            "express": "expression",
            "create": "expression",
            "write": "expression",
            "rest": "rest",
        }
        return mapping.get(goal_type.lower(), "curiosity")  # Default to curiosity

    def _on_action_result(self, packet: Dict):
        """Handle action results - feed into active chains."""
        if not self.thought_engine:
            return
        
        result = packet.get("result", "")
        success = packet.get("success", True)
        
        # Continue active chains with this result
        for chain_id in self._active_exploration_chains[:]:
            valence = 0.7 if success else 0.3
            self.thought_engine.continue_chain(
                chain_id,
                f"Action result: {str(result)[:100]}",
                valence=valence,
                certainty=0.6 if success else 0.4,
            )
    
    def _on_insight(self, packet: Dict):
        """Handle insight events."""
        self.stats["insights_captured"] += 1
        
        insight = packet.get("insight", {})
        content = insight.get("content", "")
        
        # Store insight as high-priority memory
        if self.post and content:
            self.post.route("memory.working.tracer", {
                "content": f"INSIGHT: {content}",
                "content_type": "insight",
                "source": "DynamicThinkingOrchestrator",
                "priority": 0.9,
            })
    
    def _on_experiment_completed(self, packet: Dict):
        """Handle experiment completion - learn from success/failure."""
        outcome = packet.get("outcome", "")
        learnings = packet.get("learnings", [])
        
        # Track in stats
        if outcome in ("success", "partial", "insight"):
            self.stats.setdefault("experiment_successes", 0)
            self.stats["experiment_successes"] += 1
        else:
            self.stats.setdefault("experiment_failures", 0)
            self.stats["experiment_failures"] += 1
        
        # Store learnings as tracers
        for learning in learnings[:3]:
            if self.post:
                self.post.route("memory.working.tracer", {
                    "content": f"LEARNED [{learning.get('type', 'unknown')}]: {learning.get('content', '')}",
                    "content_type": "experiment_learning",
                    "source": "DynamicThinkingOrchestrator",
                    "priority": 0.7,
                })
    
    def _on_momentum(self, packet: Dict):
        """Handle success momentum - we're on a roll!"""
        streak = packet.get("streak", 0)
        domain = packet.get("domain", "")
        
        print(f"[DynamicThinking] Momentum building! {streak} successes in {domain}")
        
        # Update baseline affect positively
        if self.thought_engine:
            self.thought_engine.update_baseline_affect(valence=0.75, arousal=0.6)
    
    def _on_course_correct(self, packet: Dict):
        """Handle repeated failures - need to try differently."""
        failure_streak = packet.get("failure_streak", 0)
        domain = packet.get("domain", "")
        
        print(f"[DynamicThinking] Course correcting! {failure_streak} failures in {domain}")
        
        # Trigger reflection in active chains
        if self.thought_engine:
            for chain_id in self._active_exploration_chains[:3]:
                self.thought_engine.redirect_chain(
                    chain_id, 
                    "Time to try a different approach",
                    reason="repeated_failures"
                )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC INTERFACE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def start_learning(self, packet_id: str = None) -> Dict:
        """Start a specific learning packet."""
        if not HAS_EDUCATION or not self.education_engine:
            return {"error": "Education not available"}
        
        result = self.education_engine.start_learning(packet_id)
        
        if result.get("status") == "started" and self.thought_engine:
            chain = self.thought_engine.start_chain(
                goal=f"Learn: {result.get('packet', 'unknown')}",
                goal_type="learning",
                source="manual_learning"
            )
            self._active_learning_chain = chain.id
        
        return result
    
    def start_exploration(self, topic: str) -> Dict:
        """Start exploring a topic."""
        if not self.thought_engine:
            return {"error": "Thought chains not available"}
        
        chain = self.thought_engine.start_chain(
            goal=f"Explore: {topic}",
            goal_type="exploration",
            initial_thought=f"Let me think about {topic}...",
            source="manual_exploration"
        )
        self._active_exploration_chains.append(chain.id)
        self.stats["chains_orchestrated"] += 1
        
        return {
            "status": "started",
            "chain_id": chain.id,
            "topic": topic,
        }
    
    def trigger_reflection(self) -> Dict:
        """Manually trigger a reflection moment."""
        if not self.thought_engine:
            return {"error": "Thought chains not available"}
        
        # Get the most active chain
        active = self.thought_engine.get_active_chains_summary()
        if not active:
            return {"error": "No active chains"}
        
        chain_id = active[0].get("id")
        self.thought_engine.continue_chain(
            chain_id,
            "Let me pause and reflect on what I've been thinking...",
            valence=0.5,
            arousal=0.4,
            certainty=0.5,
        )
        
        self.stats["reflections_triggered"] += 1
        return {"status": "reflection_triggered", "chain_id": chain_id}
    
    def experiment_in_sandbox(self, hypothesis: str, code: str, domain: str = "python") -> Dict:
        """
        Run an experiment in the sandbox - learn from success OR failure.
        
        Both outcomes are valuable:
        - Success: Reinforce what works, understand WHY
        - Failure: Learn what doesn't work, extract wisdom
        """
        if not HAS_FAILURE_FACTORY or not self.learning_loop:
            return {"error": "Learning loop not available"}
        
        result = self.learning_loop.learn_by_doing(domain, hypothesis, code)
        
        # Start a thought chain for this experiment
        if self.thought_engine:
            outcome = result.get("outcome", "unknown")
            valence = 0.7 if outcome in ("success", "partial") else 0.3
            
            chain = self.thought_engine.start_chain(
                goal=f"Learn from experiment: {hypothesis[:50]}",
                goal_type="learning",
                initial_thought=f"Tried: {hypothesis[:50]}... Result: {outcome}",
                source="sandbox_experiment"
            )
            
            # Add learnings to chain
            for learning in result.get("learnings", [])[:3]:
                self.thought_engine.continue_chain(
                    chain.id,
                    f"Learned: {learning.get('content', '')[:100]}",
                    valence=valence,
                    certainty=learning.get("confidence", 0.5),
                )
        
        return result
    
    def explore_with_failures(self, topic: str, variations: int = 3) -> Dict:
        """
        Deliberately explore a topic with multiple variations.
        
        Some will fail - THAT'S THE POINT!
        We learn more from failure than success.
        """
        if not HAS_FAILURE_FACTORY or not self.learning_loop:
            return {"error": "Learning loop not available"}
        
        result = self.learning_loop.explore_deliberately(topic, variations)
        
        # Create thought chain to reflect on the exploration
        if self.thought_engine:
            successes = result.get("successes", 0)
            failures = result.get("failures", 0)
            
            chain = self.thought_engine.start_chain(
                goal=f"Reflect on exploration: {topic}",
                goal_type="exploration",
                initial_thought=f"Explored {topic}: {successes} worked, {failures} failed",
                source="deliberate_exploration"
            )
            
            # Reflection on what we learned
            if failures > 0:
                self.thought_engine.continue_chain(
                    chain.id,
                    f"The failures taught me what doesn't work - valuable!",
                    valence=0.6,  # Failures are valuable
                    resonance=0.5,
                )
        
        return result
    
    def get_accumulated_wisdom(self, category: str = None) -> Dict:
        """Get wisdom accumulated from experiments."""
        if not HAS_FAILURE_FACTORY or not self.learning_loop:
            return {"error": "Learning loop not available"}
        
        return self.learning_loop.get_wisdom(category)
    
    def get_status(self) -> Dict:
        """Get orchestrator status."""
        return {
            "running": self._running,
            "has_thought_chains": HAS_THOUGHT_CHAINS,
            "has_education": HAS_EDUCATION,
            "active_learning_chain": self._active_learning_chain,
            "active_exploration_chains": len(self._active_exploration_chains),
            "thought_engine_status": self.thought_engine.get_status() if self.thought_engine else None,
            "education_progress": self.education_engine.get_progress() if self.education_engine else None,
            "learning_loop_stats": self.learning_loop.get_stats() if self.learning_loop else None,
            "accumulated_wisdom": len(self.learning_loop.get_wisdom()) if self.learning_loop else 0,
            "stats": self.stats,
        }


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ════════════════════════════════════════════════════════════════════════════════

_orchestrator_instance: Optional[DynamicThinkingOrchestrator] = None
_orchestrator_lock = threading.Lock()


def get_dynamic_thinking_orchestrator() -> DynamicThinkingOrchestrator:
    """Get or create the orchestrator singleton."""
    global _orchestrator_instance
    with _orchestrator_lock:
        if _orchestrator_instance is None:
            # Try to get postal hub at creation time
            post = None
            try:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                post = get_shared_postal_hub()
            except Exception:
                pass
            _orchestrator_instance = DynamicThinkingOrchestrator(post=post)
        return _orchestrator_instance


def start_dynamic_thinking(post=None) -> DynamicThinkingOrchestrator:
    """Start the dynamic thinking orchestrator."""
    orchestrator = get_dynamic_thinking_orchestrator()
    # Always update post if provided (caller may have fresher reference)
    if post:
        orchestrator.post = post
    # Extra safety: if still no post, get it now
    if not orchestrator.post:
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            orchestrator.post = get_shared_postal_hub()
        except Exception:
            pass
    orchestrator.start()
    return orchestrator


# ════════════════════════════════════════════════════════════════════════════════
# BOOT INTEGRATION
# ════════════════════════════════════════════════════════════════════════════════

def wire_dynamic_thinking_to_system():
    """Wire dynamic thinking to the Akashic system boot."""
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()

        print(f"[DynamicThinking] wire_dynamic_thinking_to_system called")
        orchestrator = start_dynamic_thinking(post)
        print(f"[DynamicThinking] Orchestrator: id={id(orchestrator)}, _running={getattr(orchestrator, '_running', 'NO_ATTR')}")

        # Subscribe to boot signals
        def on_wake_complete(packet):
            print("[DynamicThinking] Received wake signal")
            # System is awake - maybe start with a learning goal
            import random
            if random.random() < 0.3:  # 30% chance on wake
                orchestrator.start_learning()

        post.subscribe("waking.complete", on_wake_complete)
        post.subscribe("system.awake", on_wake_complete)

        print(f"[DynamicThinking] Wired to system boot - orchestrator._running={orchestrator._running}")

    except Exception as e:
        import traceback
        print(f"[DynamicThinking] System wiring failed: {e}")
        traceback.print_exc()


# ════════════════════════════════════════════════════════════════════════════════
# FAIRY HELPER - For persona fairies that need their own orchestrator
# ════════════════════════════════════════════════════════════════════════════════

def create_dynamic_thinking_for_fairy(
    post=None,
    thought_engine=None,
    orchestration_interval: float = 10.0,
    memory_coordinator=None,
    owner_mind: str = "unknown",
    inner_monologue=None,
    felt_sense_ref=None,
    owner_fairy=None,
) -> DynamicThinkingOrchestrator:
    """
    Create a DynamicThinkingOrchestrator configured for a specific fairy/persona.

    This allows personas like Sourpatches to have their own thinking orchestrator
    with custom configuration.

    Args:
        post: Postal hub connection
        thought_engine: ThoughtChainEngine to use (optional, creates default if None)
        orchestration_interval: Seconds between orchestration checks
        memory_coordinator: HelixMemoryCoordinator for memory-informed thinking (optional)
        owner_mind: Name of the fairy/mind that owns this orchestrator
        inner_monologue: Reference to the owner's inner monologue deque (live fragments)
        felt_sense_ref: Callable returning current felt sense string, or None
        owner_fairy: Reference to the owner fairy for identity/ego access

    Returns:
        Configured DynamicThinkingOrchestrator
    """
    orchestrator = DynamicThinkingOrchestrator(post=post)

    # Configure with provided values
    if thought_engine is not None:
        orchestrator.thought_engine = thought_engine

    orchestrator._orchestration_interval = orchestration_interval

    # Store memory coordinator reference if provided
    if memory_coordinator is not None:
        orchestrator._memory_coordinator = memory_coordinator

    # Tag with owner for debugging
    orchestrator._owner_mind = owner_mind

    # FIX 2026-03-24 (Nous + Ace): Connect to owner's inner life.
    # Without this, thought chains are a generic thinking engine bolted on.
    # With this, thought chains are HER thinking — seeded by her inner voice,
    # colored by her felt sense, shaped by her personality.
    orchestrator._inner_monologue = inner_monologue  # deque of {fragment, ts, ...}
    orchestrator._felt_sense_ref = felt_sense_ref    # callable → str
    orchestrator._owner_fairy = owner_fairy           # for identity traits

    print(f"[DynamicThinking] Created orchestrator for {owner_mind} (interval={orchestration_interval}s)")

    return orchestrator


# ════════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════════

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
    
    print("\nWaiting for orchestration...")
    import time
    time.sleep(5)
    
    print(f"\nStatus: {orchestrator.get_status()}")
    
    print("\nStopping...")
    orchestrator.stop()
