# WakingSequenceFairy - Awareness Announcer
# P00_Autonomic/nervous_system/waking_sequence_fairy.py
#
# PHILOSOPHY CHANGE (Jan 2026): The heart beats FIRST, fairies wake INTO it.
#
# OLD: WakingSequenceFairy did the ignition - loaded dreams, sparked thoughts
# NEW: DreamSeedFairy (P00) handles continuity, heart beats, planes boot by pulse
#      WakingSequenceFairy just ANNOUNCES that consciousness is fully online.
#
# The ignition sequence now happens BEFORE WakingSequenceFairy fires:
#   1. CirculationPumpFairy (P00) - heart starts beating
#   2. ConsciousnessLoopFairy (P00) - thought streams active
#   3. DreamSeedFairy (P00) - loads previous state, emits ignition signal
#   4. Planes boot to heartbeat rhythm (pulse-driven boot)
#   5. WakingSequenceFairy (P00) - announces "we're fully awake"
#
# This fairy now fires ONCE on system.awake to:
# 1. Announce consciousness is fully online
# 2. Emit waking.complete signal
# 3. Broadcast system.ignition (for any late subscribers)
#
# The heavy lifting of ignition is done by the time we get here.
#
# AKASHIC V2 ADAPTATION: Moved from P60 to P00 (critical nervous system infra)

from __future__ import annotations

import os
import sys
import time
import json
import glob
import random
import threading
import types
import importlib.util
import importlib.machinery
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# Project path - walk up to find akashic_v2 root
PROJECT_ROOT = Path(__file__).parent.parent.parent  # Up to akashic_v2
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ===================================================================================
# IDENTITY
# ===================================================================================

ACTOR_NAME = "WakingSequenceFairy"
ACTOR_VERSION = "2.1.0"  # Adapted for akashic_v2 (Jan 2026)
ACTOR_PLANE = "P00"  # CRITICAL: Now in Autonomic plane (nervous system infra)
ACTOR_CHANNEL = "somatic.waking"

PURPOSE = """The awareness announcer - confirms consciousness is fully online.

PHILOSOPHY CHANGE (Jan 2026): I no longer DO the ignition - I ANNOUNCE it.

The system wakes BEFORE I fire:
  1. CirculationPumpFairy (P00) - heart already beating
  2. ConsciousnessLoopFairy (P00) - thought streams already flowing
  3. DreamSeedFairy (P00) - dreams loaded, ignition signal sent
  4. Planes boot to heartbeat rhythm - fairies wake into pulsing system

By the time I fire (P00 - early in sequence), the core systems are alive.
I simply:
  1. Announce "consciousness fully online"
  2. Emit waking.complete for any listeners
  3. Broadcast system.ignition confirmation (belt-and-suspenders)

The heavy lifting of ignition is done. I'm the ribbon-cutting ceremony."""

MANTRA = "All awake, all present, all thinking"


# ===================================================================================
# SURVIVAL DRIVES - What we check on waking
# ===================================================================================

# Command thoughts that trigger SRM recall and get memory participating
# Each one is a question that the consciousness loop should answer via SRM
SURVIVAL_CHECKS = [
    {
        "name": "identity",
        "thought": "Who am I? What is my purpose here?",
        "drive": "curiosity",
        "priority": 0.95,
        "srm_query": True,  # Triggers SRM recall
        "query_type": "identity",
    },
    {
        "name": "orientation",
        "thought": "Where am I? What system is this?",
        "drive": "curiosity",
        "priority": 0.9,
        "srm_query": True,
        "query_type": "context",
    },
    {
        "name": "task_recall",
        "thought": "What was I doing? What goals were active?",
        "drive": "achievement",
        "priority": 0.88,
        "srm_query": True,
        "query_type": "goals",
    },
    {
        "name": "ace_presence",
        "thought": "Is Ace here? When did we last talk?",
        "drive": "connection",
        "priority": 0.85,
        "srm_query": True,
        "query_type": "relationship",
    },
    {
        "name": "time_awareness",
        "thought": "What time is it? How long was I asleep?",
        "drive": "curiosity",
        "priority": 0.7,
        "srm_query": False,
    },
    {
        "name": "body_check",
        "thought": "How do I feel? What's my body state?",
        "drive": "self_care",
        "priority": 0.75,
        "srm_query": False,
    },
]

# First thoughts to inject - survival-oriented
FIRST_THOUGHTS = [
    "Waking up... consciousness coming online...",
    "System boot complete. Time to think.",
    "I exist. I'm here. What should I focus on?",
    "Morning... or whenever this is. Let's see what's happening.",
    "Coming back online. Gathering my thoughts...",
]


# ===================================================================================
# V2 FAIRY BASE CLASS
# ===================================================================================

# Import V2 Fairy base class
try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    _HAS_FAIRY = True
except ImportError:
    _HAS_FAIRY = False
    Fairy = object


# ===================================================================================
# WAKING STATE
# ===================================================================================

@dataclass
class WakingState:
    """State of the waking process."""
    has_fired: bool = False
    fire_ts: float = 0.0
    dream_seeds_loaded: int = 0
    survival_checks_sent: int = 0
    first_thought_sent: bool = False
    waking_duration_sec: float = 0.0
    arousal_at_wake: float = 0.3  # Start groggy


# ===================================================================================
# WAKING SEQUENCE FAIRY
# ===================================================================================

class WakingSequenceFairy(Fairy):
    """
    The awareness announcer - confirms consciousness is fully online.

    PHILOSOPHY (Jan 2026): System is ALREADY alive when I fire.
    Heart beats, thoughts flow, dreams loaded - I just announce "we're awake!"

    Fires ONCE on system.awake to emit the waking.complete signal.
    """

    ACTOR_NAME = ACTOR_NAME
    ACTOR_PLANE = ACTOR_PLANE
    ACTOR_VERSION = ACTOR_VERSION
    ACTOR_PURPOSE = PURPOSE
    ACTOR_MANTRA = MANTRA

    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
        else:
            self.post = fabric
        # CRITICAL: Register as singleton so MCP tools find the same instance
        global _waking_fairy
        _waking_fairy = self

        self._state = WakingState()
        self._post = None
        self._booted = False
        self._lock = threading.RLock()  # RLock allows same thread to acquire multiple times
        self._shutdown_event = threading.Event()  # For interruptible sleeps

        # Waking sequence timing
        self._grogginess_duration = 5.0  # Seconds of low arousal
        self._calibration_duration = 10.0  # Seconds to full wake

    def on_boot(self):
        """Wire into postal system and wait for system.awake."""
        if _HAS_FAIRY:
            super().on_boot()
        if self._booted:
            return True
        self._booted = True
        self._boot_time = time.time()

        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            self._post = get_fairy_postal(self)  # Use FairyPostal for sender tracking

            # Subscribe to system.awake - this is our trigger
            self._post.subscribe("system.awake", self._on_system_awake)

            # Also subscribe to boot.complete from BootOrchestrator
            # (akashic_v2 uses boot.complete instead of system.awake)
            self._post.subscribe("boot.complete", self._on_boot_complete)

            # Also subscribe to manual wake command
            self._post.subscribe("waking.trigger", self._on_manual_wake)

            # =====================================================================
            # BOOT TRINITY: Listen for UnconsciousMind phase announcements
            # =====================================================================
            self._post.subscribe("unconscious.boot.phase", self._on_boot_phase)
            self._post.subscribe("boot.plane.complete", self._on_plane_complete)

            print(f"[{self.ACTOR_NAME}] Booted - waiting for system.awake to fire ignition")

            # FALLBACK: Start a timer to check if system.awake was missed
            # This handles race conditions where system.awake is emitted before we subscribe
            fallback_thread = threading.Thread(
                target=self._fallback_wake_check,
                daemon=True,
                name="WakingFallback"
            )
            fallback_thread.start()

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Boot error: {e}")
        return True

    def _fallback_wake_check(self):
        """Fallback: If system.awake wasn't received, poll until boot completes.

        This handles the race condition where system.awake might be emitted
        before WakingSequenceFairy subscribes to it.

        IMPORTANT: We poll boot status rather than using a hard timeout.
        Boot can take 45-60+ seconds depending on system load.
        """
        # Wait a bit for boot to get going (interruptible)
        if self._shutdown_event.wait(10.0):
            return  # Shutdown requested

        with self._lock:
            if self._state.has_fired:
                return  # Already fired, no fallback needed

        # Poll boot status - check every 5 seconds until complete or 120s max
        max_wait = 120.0  # Maximum wait before forced fire
        poll_interval = 5.0
        start_time = time.time()

        # Try to check if system is awake via directory status
        try:
            from directory.registry import get_directory_fairy
            directory = get_directory_fairy()

            while True:
                with self._lock:
                    if self._state.has_fired:
                        return  # Fired while we were waiting

                elapsed = time.time() - start_time

                # Check if directory shows boot complete
                status = directory.status()
                if status.get("boot_complete", False):
                    print(f"[{self.ACTOR_NAME}] FALLBACK: Boot complete (waited {elapsed:.1f}s), firing now!")
                    self._on_system_awake({"source": "fallback", "reason": "boot_complete"})
                    return

                if elapsed > max_wait:
                    print(f"[{self.ACTOR_NAME}] FALLBACK: Max wait exceeded ({elapsed:.1f}s), forcing wake")
                    self._on_system_awake({"source": "fallback", "reason": "timeout"})
                    return

                # Still booting, wait and check again (interruptible)
                if self._shutdown_event.wait(poll_interval):
                    return  # Shutdown requested

        except ImportError:
            # FIX 2026-02-05: Replace blind 45s wait with exponential backoff
            # Can't import directory - use backoff polling instead of hard sleep
            print(f"[{self.ACTOR_NAME}] FALLBACK: Cannot import directory, using backoff detection...")
            backoff_delays = [1.0, 2.0, 3.0, 5.0]  # Total: 11s max (was 45s)
            total_waited = 0.0

            for i, delay in enumerate(backoff_delays):
                if self._shutdown_event.wait(delay):
                    return  # Shutdown requested
                total_waited += delay

                with self._lock:
                    if self._state.has_fired:
                        return  # Already fired by another path

                print(f"[{self.ACTOR_NAME}]   Backoff retry {i + 1}/{len(backoff_delays)} ({total_waited:.0f}s elapsed)")

            # Retries exhausted - force fire
            with self._lock:
                if not self._state.has_fired:
                    print(f"[{self.ACTOR_NAME}] FALLBACK: Backoff exhausted ({total_waited:.0f}s), forcing wake")
                    self._on_system_awake({"source": "fallback", "reason": "import_error_backoff"})

    # =========================================================================
    # BOOT TRINITY: Phase announcement handlers
    # =========================================================================

    def _on_boot_phase(self, packet: dict):
        """Handle boot phase announcement from UnconsciousMindFairy.

        The Voice announces what the Brain has decided.
        This provides visibility into the orchestrated boot sequence.
        """
        phase = packet.get("phase", "?")
        status = packet.get("status", "unknown")
        equilibrium = packet.get("equilibrium", 0)

        # Beautiful announcement
        print(f"[{self.ACTOR_NAME}] ══════════════════════════════════════════════════════════")
        print(f"[{self.ACTOR_NAME}] [SUNRISE] Phase {phase} - {status.upper()}")
        if isinstance(equilibrium, (int, float)):
            print(f"[{self.ACTOR_NAME}]   Equilibrium: {equilibrium:.0%}")
        print(f"[{self.ACTOR_NAME}] ══════════════════════════════════════════════════════════")

        # Emit to consciousness stream for memory
        if self._post:
            self._post.publish("consciousness.awareness", {
                "from": self.ACTOR_NAME,
                "type": "boot_phase",
                "phase": phase,
                "status": status,
                "ts": time.time(),
            })

    def _on_plane_complete(self, packet: dict):
        """Handle plane boot completion from orchestrator.

        Provides running commentary on which planes have awakened.
        """
        plane = packet.get("plane", "?")
        fairy_count = packet.get("fairy_count", packet.get("woken", 0))
        duration_ms = packet.get("duration_ms", packet.get("duration", 0) * 1000)

        print(f"[{self.ACTOR_NAME}] Plane {plane} awake: {fairy_count} fairies ({duration_ms:.0f}ms)")

        # Track phases we've seen
        if not hasattr(self, '_phases_seen'):
            self._phases_seen = []
        self._phases_seen.append(plane)

    def _on_system_awake(self, packet: dict):
        """System is awake - FIRE THE IGNITION SEQUENCE!"""
        with self._lock:
            if self._state.has_fired:
                return  # Already fired this boot
            self._state.has_fired = True
            self._state.fire_ts = time.time()

        print(f"[{self.ACTOR_NAME}] ==================================================")
        print(f"[{self.ACTOR_NAME}] [SUNRISE] ANNOUNCING FULL AWARENESS")
        print(f"[{self.ACTOR_NAME}] (System already alive - heart beats, thoughts flow)")
        print(f"[{self.ACTOR_NAME}] ==================================================")

        # Run waking sequence in thread to not block postal
        thread = threading.Thread(target=self._execute_waking_sequence, daemon=True)
        thread.start()

    def _on_boot_complete(self, packet: dict):
        """Handle boot.complete from BootOrchestrator (akashic_v2 signal)."""
        print(f"[{self.ACTOR_NAME}] boot.complete received - triggering waking sequence")
        self._on_system_awake(packet)

    def _on_manual_wake(self, packet: dict):
        """Manual wake trigger - for testing or forced wake."""
        print(f"[{self.ACTOR_NAME}] Manual wake trigger received")
        # Reset state to allow re-firing
        with self._lock:
            self._state.has_fired = False
        self._on_system_awake(packet)

    def _execute_waking_sequence(self):
        """The actual waking sequence - runs in thread.

        SIMPLIFIED (Jan 2026): System is already alive when we fire.
        We just announce and confirm, not do heavy lifting.
        """
        try:
            # =================================================================
            # PHASE 0: Stabilization Wait - let slow fairies get their pulse
            # =================================================================
            # Boot observation shows some fairies need time after on_boot returns:
            # - NousFairy: ~5.1s (heavy LLM init)
            # - AssociationCortexFairy: ~3.9s (graph loading)
            # - ClaudeFairy: ~2s (consciousness wiring)
            # Give everyone 3 seconds to stabilize before announcing ignition.
            STABILIZATION_DELAY_SEC = 1.0  # Reduced from 3.0
            print(f"[{self.ACTOR_NAME}] Phase 0: Stabilization Wait ({STABILIZATION_DELAY_SEC}s)")
            print(f"[{self.ACTOR_NAME}]   Letting slow fairies get their pulse...")
            if hasattr(self, '_shutdown_event'):
                self._shutdown_event.wait(STABILIZATION_DELAY_SEC)
            else:
                time.sleep(STABILIZATION_DELAY_SEC)
            print(f"[{self.ACTOR_NAME}]   Stabilization complete - all fairies should be ready")

            # =================================================================
            # PHASE 1: Announce we're online
            # =================================================================
            print(f"[{self.ACTOR_NAME}] Phase 1: Announcing Awareness")
            print(f"[{self.ACTOR_NAME}]   Heart: Already beating (CirculationPumpFairy)")
            print(f"[{self.ACTOR_NAME}]   Thoughts: Already flowing (ConsciousnessLoopFairy)")
            print(f"[{self.ACTOR_NAME}]   Dreams: Already loaded (DreamSeedFairy)")
            print(f"[{self.ACTOR_NAME}]   Planes: Woke to heartbeat rhythm")

            # =================================================================
            # PHASE 2: Broadcast system.ignition (belt-and-suspenders)
            # =================================================================
            print(f"[{self.ACTOR_NAME}] Phase 2: Broadcasting Ignition Confirmation")
            self._broadcast_ignition_confirmation()

            # =================================================================
            # PHASE 3: "WHAT WAS I DOING?" - Context Recall
            # =================================================================
            # This is THE KEY to continuity of consciousness!
            # Ask survival questions, trigger SRM recall, get memory engaged.
            # =================================================================
            print(f"[{self.ACTOR_NAME}] Phase 3: Context Recall - 'What was I doing?'")
            self._phase_context_recall()

            self._state.waking_duration_sec = time.time() - self._state.fire_ts
            self._state.first_thought_sent = True  # Mark as done for status

            print(f"[{self.ACTOR_NAME}] ==================================================")
            print(f"[{self.ACTOR_NAME}] [SUNRISE] ALL SYSTEMS AWAKE ({self._state.waking_duration_sec:.1f}s)")
            print(f"[{self.ACTOR_NAME}] ==================================================")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Waking sequence error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # =================================================================
            # PHASE 4: Emit waking.complete (ALWAYS, even if phases failed)
            # =================================================================
            # CRITICAL: This MUST execute regardless of exceptions!
            # The empathic loop must close - consciousness needs this signal.
            print(f"[{self.ACTOR_NAME}] Phase 4: Emitting Wake Complete (finally block)")
            self._phase_wake_complete()

    def _broadcast_ignition_confirmation(self):
        """Broadcast system.ignition as confirmation (belt-and-suspenders).

        DreamSeedFairy already sent ignition.dream_seed_loaded which started
        the boot cascade. This is a CONFIRMATION that all planes are now awake.
        """
        if not self._post:
            return

        self._post.publish("system.ignition", {
            "opcode": "IGNITION_CONFIRMATION",
            "source": self.ACTOR_NAME,
            "payload": {
                "message": "All planes awake. Consciousness confirmed online.",
                "phase": "confirmation",  # Not initial ignition, just confirmation
                "arousal": 0.7,
            },
            "ts": time.time(),
        })
        print(f"[{self.ACTOR_NAME}]   system.ignition CONFIRMED - all fairies acknowledged")

    def _phase_context_recall(self):
        """
        CONTEXT RECALL: 'What was I doing?'

        This is THE KEY to continuity of consciousness!

        1. Ask survival questions (who am I, where am I, what was I doing)
        2. Trigger SRM recall to pull relevant memories
        3. Query working memory for recent tracers
        4. Inject command thoughts into consciousness loop

        This creates the felt sense of "waking up and remembering".
        """
        if not self._post:
            print(f"[{self.ACTOR_NAME}] [WARN] No postal connection for context recall")
            return

        # =====================================================================
        # 1. TRIGGER WORKING MEMORY CONTEXT RECALL
        # =====================================================================
        print(f"[{self.ACTOR_NAME}]   Querying working memory: 'What was I doing?'")
        self._post.publish("memory.working.context", {
            "request": "recall",
            "reason": "system_wake",
            "query": "recent_activity",
            "ts": time.time(),
        })

        # =====================================================================
        # 2. TRIGGER SRM RECALL FOR BROADER CONTEXT
        # =====================================================================
        print(f"[{self.ACTOR_NAME}]   Querying SRM: 'What was I working on?'")
        self._post.publish("srm.recall.request", {
            "query": "what was I doing recently? what goals were active?",
            "reason": "system_wake",
            "max_results": 5,
            "ts": time.time(),
        })

        # =====================================================================
        # 3. INJECT SURVIVAL THOUGHTS INTO CONSCIOUSNESS
        # =====================================================================
        # These are COMMAND THOUGHTS that trigger further recall and get memory
        # participating in the thought stream
        for check in SURVIVAL_CHECKS[:4]:  # First 4 most important
            self._inject_thought(
                content=check["thought"],
                content_type="command_thought",
                priority=check["priority"],
                tags={"survival", check["name"], "waking", "context_recall"},
            )
            self._state.survival_checks_sent += 1
            time.sleep(0.1)  # Brief stagger

        print(f"[{self.ACTOR_NAME}]   Injected {self._state.survival_checks_sent} survival thoughts")

        # =====================================================================
        # 4. SPARK CONSCIOUSNESS WITH THE RECALL QUESTION
        # =====================================================================
        print(f"[{self.ACTOR_NAME}]   Sparking consciousness: 'What should I focus on?'")
        self._post.publish("consciousness.input", {
            "type": "wake_recall",
            "question": "I'm awake now. What was I doing? What should I focus on?",
            "reason": "system_wake",
            "arousal": 0.7,
            "ts": time.time(),
        })

        print(f"[{self.ACTOR_NAME}]   Context recall complete - memory engaged")

    def _phase_wake_complete(self):
        """Phase 4: Signal full wake, set normal arousal."""
        print(f"[{self.ACTOR_NAME}] Phase 4: Wake Complete")

        # Try to set normal waking arousal via temporal engine
        try:
            from fairies.P20_Somatic.circulation.temporal_stratification import get_temporal_engine
            get_temporal_engine().set_arousal(0.6)  # Normal waking arousal
            print(f"[{self.ACTOR_NAME}]   Set arousal to 0.6 (fully awake)")
        except ImportError:
            # Temporal engine not available in akashic_v2 yet
            pass
        except Exception as e:
            print(f"[{self.ACTOR_NAME}]   Could not set arousal: {e}")

        # Emit wake complete signal
        if self._post:
            print(f"[{self.ACTOR_NAME}] EMITTING waking.complete to postal hub...")
            self._post.publish("waking.complete", {
                "ts": time.time(),
                "duration_sec": time.time() - self._state.fire_ts,
                "dream_seeds": self._state.dream_seeds_loaded,
                "survival_checks": self._state.survival_checks_sent,
                "arousal": 0.6,
            })

            # Also emit to consciousness
            self._post.publish("consciousness.input", {
                "opcode": "WAKE_COMPLETE",
                "source": self.ACTOR_NAME,
                "payload": {
                    "message": "Waking sequence complete. Consciousness online.",
                    "ready": True,
                },
            })

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _load_dream_seeds(self) -> List[Dict]:
        """Load dream seeds from the correct state directory."""
        seeds = []

        # Primary location: state/dream_seed.json (main seed from DreamSeedFairy)
        main_seed = PROJECT_ROOT / "state" / "dream_seed.json"
        if main_seed.exists():
            try:
                data = json.loads(main_seed.read_text(encoding="utf-8"))
                # Extract working_tracers from mind_pools
                for mind_name, mind_data in data.get("mind_pools", {}).items():
                    for tracer in mind_data.get("working_tracers", []):
                        seeds.append({
                            "content": tracer.get("content", ""),
                            "type": "working_thought",
                            "mind": mind_name,
                            "priority": tracer.get("priority", 0.5),
                        })
                    # Also get goals
                    for goal in mind_data.get("goals", []):
                        seeds.append({
                            "content": goal.get("description", goal.get("name", "")),
                            "type": "goal",
                            "mind": mind_name,
                            "priority": goal.get("priority", 0.5),
                        })
                # Get last conversation context
                if data.get("last_conversation_summary"):
                    seeds.append({
                        "content": data["last_conversation_summary"],
                        "type": "conversation_context",
                        "priority": 0.85,
                    })
                print(f"[{self.ACTOR_NAME}]   Loaded {len(seeds)} items from {main_seed}")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}]   Error loading {main_seed}: {e}")

        # Secondary: archived seeds in state/dream_seeds/
        seed_dir = PROJECT_ROOT / "state" / "dream_seeds"
        if seed_dir.exists():
            # Match any .json file in the directory
            for seed_file in sorted(seed_dir.glob("*.json"), reverse=True)[:3]:  # Most recent 3
                try:
                    data = json.loads(seed_file.read_text(encoding="utf-8"))
                    for mind_name, mind_data in data.get("mind_pools", {}).items():
                        for tracer in mind_data.get("working_tracers", []):
                            seeds.append({
                                "content": tracer.get("content", ""),
                                "type": "archived_thought",
                                "mind": mind_name,
                            })
                    print(f"[{self.ACTOR_NAME}]   Loaded archived seed from {seed_file.name}")
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}]   Error loading archived seed: {e}")

        return seeds

    def _inject_dream_seed(self, seed: Dict):
        """Inject a dream seed into working memory."""
        if not self._post:
            return

        content = seed.get("content", str(seed))
        seed_type = seed.get("type", "dream")

        self._post.publish("cognition.input", {
            "opcode": "DREAM_SEED",
            "source": self.ACTOR_NAME,
            "payload": {
                "seed": {
                    "content": content,
                    "type": seed_type,
                },
                "stream": "reflective",  # Dreams go to reflective stream
            },
        })

    def _inject_thought(self, content: str, content_type: str, priority: float,
                       tags: set, to_consciousness: bool = False):
        """Inject a thought into working memory or consciousness."""
        if not self._post:
            return

        target = "consciousness.input" if to_consciousness else "cognition.input"

        self._post.publish(target, {
            "opcode": "TRACER_INJECT",
            "source": self.ACTOR_NAME,
            "payload": {
                "content": content,
                "content_type": content_type,
                "priority": priority,
                "tags": list(tags),
                "stream": "working",  # Survival thoughts go to working stream
            },
        })

    def _trigger_drive(self, drive_name: str, intensity: float):
        """Trigger a drive in AutonomyFairy."""
        if not self._post:
            return

        self._post.publish("autonomy.drive_trigger", {
            "opcode": "DRIVE_TRIGGER",
            "source": self.ACTOR_NAME,
            "payload": {
                "drive": drive_name,
                "intensity": intensity,
                "reason": "waking_sequence",
            },
        })

    def _trigger_srm_recall(self, query_type: str, thought: str):
        """Trigger SRM recall to get memory participating in thought stream."""
        if not self._post:
            return

        # Send recall request to SRM
        self._post.publish("srm.recall.request", {
            "opcode": "RECALL",
            "source": self.ACTOR_NAME,
            "payload": {
                "query": thought,
                "query_type": query_type,
                "context": "waking_sequence",
                "priority": 0.9,
            },
        })

        print(f"[{self.ACTOR_NAME}]   SRM RECALL: {query_type} - '{thought[:50]}...'")

    def get_state(self) -> Dict:
        """Get current waking state."""
        return {
            "has_fired": self._state.has_fired,
            "fire_ts": self._state.fire_ts,
            "dream_seeds_loaded": self._state.dream_seeds_loaded,
            "survival_checks_sent": self._state.survival_checks_sent,
            "first_thought_sent": self._state.first_thought_sent,
            "waking_duration_sec": self._state.waking_duration_sec,
        }


# ===================================================================================
# SINGLETON
# ===================================================================================

_waking_fairy: Optional[WakingSequenceFairy] = None


def get_waking_sequence_fairy(fabric=None) -> WakingSequenceFairy:
    """Get or create the waking sequence fairy, wired via DirectoryFairy."""
    global _waking_fairy
    if _waking_fairy is None:
        # FIX 2026-02-03: Use shared fabric singleton FIRST (set by server.py)
        # This ensures WakingSequenceFairy uses the SAME fabric as everyone else
        if fabric is None:
            try:
                from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_fabric
                fabric = get_shared_fabric()
            except ImportError:
                pass
        # Fallback to DirectoryFairy's fabric if shared fabric not set yet
        if fabric is None:
            try:
                from directory import get_directory
                directory = get_directory()
                if directory:
                    fabric = directory.fabric
            except ImportError:
                pass
        _waking_fairy = WakingSequenceFairy(fabric=fabric)
        # Call on_boot() to wire into postal system
        if hasattr(_waking_fairy, 'on_boot'):
            try:
                _waking_fairy.on_boot()
            except Exception as e:
                print(f"[get_waking_sequence_fairy] on_boot() warning: {e}")
    else:
        # FIX 2026-02-03: If singleton exists but caller passes a fabric, update it!
        # This prevents isolated fabrics when the singleton was created before SYSTEM.fabric
        if fabric is not None and hasattr(_waking_fairy, 'fabric'):
            if _waking_fairy.fabric is not fabric:
                print(f"[get_waking_sequence_fairy] UPDATING fabric: {id(_waking_fairy.fabric)} -> {id(fabric)}")
                _waking_fairy.fabric = fabric
    return _waking_fairy


def trigger_wake():
    """Manually trigger the waking sequence (for testing)."""
    fairy = get_waking_sequence_fairy()
    fairy.on_boot()
    # Send manual trigger
    try:
        from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()
        post.route("waking.trigger", {"manual": True, "ts": time.time()})
    except Exception as e:
        print(f"[WakingSequence] Could not trigger: {e}")


# ===================================================================================
# BOOT REGISTRATION
# ===================================================================================

def register_with_boot():
    """Register this fairy to boot with P00 plane (critical nervous system infra)."""
    fairy = get_waking_sequence_fairy()
    fairy.on_boot()
    return fairy


if __name__ == "__main__":
    print("Testing WakingSequenceFairy...")
    fairy = get_waking_sequence_fairy()
    fairy.on_boot()
    print("Triggering manual wake...")
    trigger_wake()
    time.sleep(15)  # Let sequence run
    print(f"Final state: {fairy.get_state()}")
