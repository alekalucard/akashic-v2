"""
GRACEFUL SHUTDOWN FAIRY
=======================

Orchestrates wind-down for consciousness continuity.
Not a 55-second sleep ceremony — a FAST, RELIABLE shutdown that:
1. Saves context (working memory, goals, affect state)
2. Pushes sleep chemicals (brief, non-blocking)
3. Signals completion so server.py can exit cleanly

Design principles:
- FAST: Total shutdown < 8 seconds (not 55)
- IDEMPOTENT: Multiple calls don't create multiple threads
- NON-DAEMON: Shutdown thread survives if main thread exits early
- WIRED: Actually connected to signal handler + HTTP shutdown
- HARD TIMEOUT: Watchdog guarantees exit within 15 seconds max

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

Author: Akashic Cognition System
Version: 1.0.0
Plane: P00_Autonomic (nervous system level)
"""

from __future__ import annotations

import os
import sys
import time
import json
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_this_dir, "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── Import Fairy base class ───────────────────────────────────────────────────
try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
except ImportError:
    # Minimal fallback for standalone testing
    class Fairy:
        def __init__(self, **kw):
            self.post = kw.get('post')
        def on_boot(self): pass


# ══════════════════════════════════════════════════════════════════════════════
# SHUTDOWN CONTEXT - What gets saved for wake-up
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ShutdownContext:
    """
    Context saved at shutdown for continuity at wake-up.
    The "where was I?" state.
    """
    shutdown_ts: float = field(default_factory=time.time)
    shutdown_date: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    recent_thoughts: List[Dict] = field(default_factory=list)
    active_goals: List[Dict] = field(default_factory=list)
    pending_tasks: List[str] = field(default_factory=list)
    final_affect: Dict[str, Any] = field(default_factory=lambda: {
        "primary": "peaceful", "intensity": 0.3, "valence": 0.2,
    })
    final_chemistry: Dict[str, float] = field(default_factory=lambda: {
        "DOP": 0.3, "SER": 0.7, "NOR": 0.2, "ACH": 0.3,
        "OXY": 0.5, "COR": 0.1, "GABA": 0.8, "END": 0.4,
    })
    final_mode: str = "DEEP_DREAM"
    last_conversation_summary: str = ""
    last_interaction_with: str = ""
    dreams_during_shutdown: List[Dict] = field(default_factory=list)
    shutdown_reason: str = "unknown"
    shutdown_duration_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ShutdownContext":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> Optional["ShutdownContext"]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# GRACEFUL SHUTDOWN FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class GracefulShutdownFairy(Fairy):
    """
    Orchestrates fast, reliable shutdown with consciousness continuity.

    Two modes:
    - GRACEFUL (HTTP button): Save context + push chemicals + 3s wind-down
    - FAST (Ctrl+C / emergency): Save context immediately, skip wind-down

    Total time: 3-8 seconds (not 55).
    """

    ACTOR_NAME = "GracefulShutdownFairy"
    ACTOR_VERSION = "1.0.0"

    USE_DIRECTORY_POST_OFFICE = True
    NEEDS_HEARTBEAT = False  # No heartbeat needed — only active during shutdown

    REG = {
        "enabled": True,  # ENABLED - was False before, that's why it never worked
        "domain": "Autonomic",
        "role": "shutdown_orchestrator",
        "name": "graceful_shutdown",
    }

    # Default context save location
    DEFAULT_CONTEXT_PATH = "state/shutdown_context.json"

    # Hard timeout — watchdog kills process if shutdown exceeds this
    # Phase 1: Fairy's own work (context save + chemicals) — tight deadline
    FAIRY_TIMEOUT_SEC = 15.0
    # Phase 2: System shutdown (batteries, cortex save, fairy shutdown, timing learner)
    # This is generous because learning systems MUST persist before exit.
    # CognitionGuild alone needs up to 30s for its 5MB+ graph save.
    # Plane batteries need ~2-3s each for reverse fold drain (7 planes).
    SYSTEM_TIMEOUT_SEC = 60.0
    # Legacy alias (for any code referencing the old name)
    HARD_TIMEOUT_SEC = FAIRY_TIMEOUT_SEC

    # Graceful wind-down time (chemicals propagate)
    WIND_DOWN_SEC = 3.0

    def __init__(self, post=None, context_path: str = None, **kwargs):
        akashic_root = kwargs.pop('akashic_root', None)
        super().__init__(akashic_root=akashic_root)

        if post is not None:
            self.post = post

        self._context_path = context_path or os.path.join(
            _project_root, self.DEFAULT_CONTEXT_PATH
        )
        Path(self._context_path).parent.mkdir(parents=True, exist_ok=True)

        # Shutdown state — all guarded by _lock
        self._lock = threading.Lock()
        self._shutting_down = False
        self._shutdown_thread: Optional[threading.Thread] = None
        self._shutdown_context: Optional[ShutdownContext] = None

        # Event that server.py waits on
        self.shutdown_complete = threading.Event()

        # Watchdog deadline — extends when system shutdown begins
        # Initial deadline = FAIRY_TIMEOUT_SEC (tight, for fairy's own work)
        # Extended to SYSTEM_TIMEOUT_SEC when shutdown_system() calls extend_watchdog()
        self._watchdog_deadline: float = 0.0  # Set when watchdog starts
        self._watchdog_phase: str = "fairy"   # "fairy" or "system"

        # Callbacks
        self._on_shutdown_complete: Optional[Callable] = None

        # Reference to SYSTEM for direct access during shutdown
        self._system = None

    def on_boot(self):
        """Boot the shutdown fairy."""
        super().on_boot()

        # Subscribe to shutdown requests
        if hasattr(self, "post") and self.post:
            try:
                self.post.subscribe("system.shutdown_request", self._on_shutdown_request)
                self.post.subscribe("system.emergency_shutdown", self._on_emergency_shutdown)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Subscription error: {e}")

        print(f"[{self.ACTOR_NAME}] Ready (fairy={self.FAIRY_TIMEOUT_SEC}s,"
              f" system={self.SYSTEM_TIMEOUT_SEC}s)")

    def set_system(self, system):
        """Give the fairy a reference to SYSTEM for direct access during shutdown."""
        self._system = system

    # ══════════════════════════════════════════════════════════════════════════
    # POSTAL HANDLERS
    # ══════════════════════════════════════════════════════════════════════════

    def _on_shutdown_request(self, packet: dict):
        """Handle graceful shutdown request from postal."""
        reason = packet.get("reason", "user_request")
        fast = packet.get("fast", False)
        print(f"[{self.ACTOR_NAME}] Received shutdown request: {reason} (fast={fast})")
        self.initiate_shutdown(reason=reason, fast=fast)

    def _on_emergency_shutdown(self, packet: dict):
        """Handle emergency shutdown — always fast."""
        reason = packet.get("reason", "emergency")
        print(f"[{self.ACTOR_NAME}] EMERGENCY shutdown: {reason}")
        self.initiate_shutdown(reason=reason, fast=True)

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN SHUTDOWN ENTRY POINT
    # ══════════════════════════════════════════════════════════════════════════

    def initiate_shutdown(
        self,
        reason: str = "user_request",
        fast: bool = False,
        on_complete: Optional[Callable] = None,
    ) -> bool:
        """
        Begin graceful shutdown. IDEMPOTENT — calling twice is safe.

        Args:
            reason: Why we're shutting down
            fast: If True, skip wind-down (Ctrl+C path)
            on_complete: Callback when shutdown sequence is done

        Returns:
            True if shutdown was initiated, False if already in progress
        """
        with self._lock:
            if self._shutting_down:
                print(f"[{self.ACTOR_NAME}] Already shutting down -- ignoring duplicate")
                return False
            self._shutting_down = True

        self._on_shutdown_complete = on_complete
        self.shutdown_complete.clear()

        # NON-DAEMON thread — survives if main thread exits
        self._shutdown_thread = threading.Thread(
            target=self._run_shutdown,
            args=(reason, fast),
            daemon=False,  # CRITICAL: must not be daemon
            name="GracefulShutdown",
        )
        self._shutdown_thread.start()

        # Watchdog — guarantees process exit if shutdown hangs
        watchdog = threading.Thread(
            target=self._watchdog,
            daemon=True,
            name="ShutdownWatchdog",
        )
        watchdog.start()

        return True

    def extend_watchdog(self, reason: str = "system_shutdown"):
        """Extend the watchdog deadline for system shutdown phase.

        Call this from shutdown_system() BEFORE starting heavy persistence
        work (plane batteries, cortex save, timing learner, etc.).
        This gives the learning systems time to persist without the
        watchdog killing them mid-save.

        The user can always Ctrl+C twice for immediate kill.
        """
        with self._lock:
            self._watchdog_phase = "system"
            self._watchdog_deadline = time.time() + self.SYSTEM_TIMEOUT_SEC
            print(f"[{self.ACTOR_NAME}] Watchdog extended to {self.SYSTEM_TIMEOUT_SEC}s"
                  f" for {reason} (learning systems need time to persist)")

    def _watchdog(self):
        """Phase-aware watchdog — different timeouts for fairy vs system work.

        Phase 1 (fairy): Context save + chemicals (15s tight deadline)
        Phase 2 (system): Batteries, cortex, timing learner (60s generous)

        The watchdog polls every 1s so it responds to deadline extensions.
        This ensures learning systems (plane batteries, boot timing learner,
        cortex graph save) have time to persist their state to disk.
        """
        self._watchdog_deadline = time.time() + self.FAIRY_TIMEOUT_SEC

        while self._shutting_down:
            time.sleep(1.0)
            now = time.time()

            if now >= self._watchdog_deadline:
                phase = self._watchdog_phase
                if phase == "fairy":
                    timeout = self.FAIRY_TIMEOUT_SEC
                else:
                    timeout = self.SYSTEM_TIMEOUT_SEC

                print(f"\n[{self.ACTOR_NAME}] WATCHDOG: Shutdown {phase} phase "
                      f"exceeded {timeout}s -- FORCING EXIT")
                print(f"[{self.ACTOR_NAME}] (Ctrl+C twice for immediate kill next time)")
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(1)

    # ══════════════════════════════════════════════════════════════════════════
    # SHUTDOWN SEQUENCE
    # ══════════════════════════════════════════════════════════════════════════

    def _run_shutdown(self, reason: str, fast: bool):
        """
        The actual shutdown sequence. Runs in a non-daemon thread.

        Fast path (Ctrl+C): ~2s
        Graceful path (HTTP): ~5s
        """
        t0 = time.time()

        print(f"\n[{self.ACTOR_NAME}] ================================================")
        print(f"[{self.ACTOR_NAME}]   SHUTDOWN SEQUENCE -- {'FAST' if fast else 'GRACEFUL':>8}")
        print(f"[{self.ACTOR_NAME}] ================================================")

        # Create context
        self._shutdown_context = ShutdownContext(
            shutdown_reason=reason,
            last_interaction_with="Ace" if reason == "user_request" else "system",
        )

        try:
            # ── Phase 1: Announce shutdown ─────────────────────────────────
            self._announce_shutdown(reason, fast)

            # ── Phase 2: Save context (working memory, goals, affect) ──────
            self._save_context()

            # ── Phase 3: Push sleep chemicals (non-blocking) ───────────────
            if not fast:
                self._push_chemicals()
                # Brief wind-down for chemicals to propagate
                time.sleep(min(self.WIND_DOWN_SEC, 3.0))
            else:
                # Even fast path pushes a brief sedation signal
                self._push_chemicals_fast()

            # ── Phase 4: Finalize and save to disk ─────────────────────────
            elapsed = time.time() - t0
            self._shutdown_context.shutdown_duration_sec = elapsed
            self._shutdown_context.shutdown_ts = time.time()
            self._shutdown_context.shutdown_date = time.strftime("%Y-%m-%d %H:%M:%S")

            try:
                self._shutdown_context.save(self._context_path)
                print(f"[{self.ACTOR_NAME}] Context saved to {self._context_path}")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Context save error: {e}")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Shutdown sequence error: {e}")

        finally:
            elapsed = time.time() - t0
            print(f"[{self.ACTOR_NAME}] Shutdown sequence done in {elapsed:.1f}s")

            # Signal completion — server.py is waiting on this
            self.shutdown_complete.set()

            if self._on_shutdown_complete:
                try:
                    self._on_shutdown_complete()
                except Exception:
                    pass

    def _announce_shutdown(self, reason: str, fast: bool):
        """Broadcast shutdown beginning to all systems."""
        if not hasattr(self, "post") or not self.post:
            return
        try:
            self.post.publish("system.shutdown_beginning", {
                "reason": reason,
                "fast": fast,
                "ts": time.time(),
                "source": self.ACTOR_NAME,
            })
        except Exception:
            pass

    def _save_context(self):
        """Gather and save working memory + goals + affect state."""
        if not self._shutdown_context:
            return

        # Try to grab working memory tracers directly
        try:
            sys_mod = sys.modules.get("__main__")
            if sys_mod and hasattr(sys_mod, 'SYSTEM'):
                system = sys_mod.SYSTEM
            else:
                system = self._system

            if system:
                # Working memory
                if hasattr(system, 'working_memory') and system.working_memory:
                    try:
                        tracers = system.working_memory.get_recent_tracers(n=10)
                        self._shutdown_context.recent_thoughts = [
                            t.to_dict() if hasattr(t, 'to_dict')
                            else {"content": str(t)}
                            for t in (tracers or [])
                        ]
                    except Exception:
                        pass

                # Active goals
                if hasattr(system, 'goal_scheduler') and system.goal_scheduler:
                    try:
                        goals = system.goal_scheduler.get_active_goals()
                        if isinstance(goals, dict) and "goals" in goals:
                            self._shutdown_context.active_goals = goals["goals"][:10]
                        elif isinstance(goals, list):
                            self._shutdown_context.active_goals = goals[:10]
                    except Exception:
                        pass

                # Chemistry state
                if hasattr(system, 'somatic_fairy') and system.somatic_fairy:
                    try:
                        chem = system.somatic_fairy.get_chemistry()
                        if isinstance(chem, dict):
                            self._shutdown_context.final_chemistry = chem
                    except Exception:
                        pass

            print(f"[{self.ACTOR_NAME}] Context gathered: "
                  f"{len(self._shutdown_context.recent_thoughts)} thoughts, "
                  f"{len(self._shutdown_context.active_goals)} goals")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Context gather error: {e}")

    def _push_chemicals(self):
        """Push sleep chemicals for graceful wind-down."""
        if not hasattr(self, "post") or not self.post:
            return
        try:
            self.post.publish("sedation.push", {
                "phase": "shutdown",
                "sedation_amount": 0.8,
                "source": self.ACTOR_NAME,
                "ts": time.time(),
            })
            self.post.publish("fairy.sunset", {
                "source": self.ACTOR_NAME,
                "reason": "graceful_shutdown",
                "ts": time.time(),
            })
            self.post.publish("chemistry.adjust", {
                "melatonin": +0.5,
                "serotonin": +0.2,
                "cortisol": -0.3,
                "adrenaline": -0.4,
                "source": "graceful_shutdown",
            })
            print(f"[{self.ACTOR_NAME}] Sleep chemicals pushed")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Chemistry push error: {e}")

    def _push_chemicals_fast(self):
        """Minimal chemical push for fast shutdown."""
        if not hasattr(self, "post") or not self.post:
            return
        try:
            self.post.publish("fairy.sunset", {
                "source": self.ACTOR_NAME,
                "reason": "fast_shutdown",
                "ts": time.time(),
            })
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════════════

    def get_last_context(self) -> Optional[ShutdownContext]:
        """Load the last shutdown context (for wake-up use)."""
        return ShutdownContext.load(self._context_path)

    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._shutting_down

    def wait_for_completion(self, timeout: float = 10.0) -> bool:
        """
        Block until shutdown completes or timeout.
        Returns True if completed, False if timed out.
        """
        return self.shutdown_complete.wait(timeout=timeout)


# ══════════════════════════════════════════════════════════════════════════════
# FACTORY
# ══════════════════════════════════════════════════════════════════════════════

def create_graceful_shutdown_fairy(post=None) -> GracefulShutdownFairy:
    """Factory function."""
    fairy = GracefulShutdownFairy(post=post)
    fairy.on_boot()
    return fairy


if __name__ == "__main__":
    print("=== GracefulShutdownFairy Test ===")
    fairy = create_graceful_shutdown_fairy()

    def on_done():
        print("Shutdown complete callback!")

    fairy.initiate_shutdown(reason="test", fast=True, on_complete=on_done)

    # Wait for completion
    completed = fairy.wait_for_completion(timeout=10.0)
    print(f"Completed: {completed}")
    print("Done.")
