"""
HeartbeatPacemaker — The Unkillable System Heartbeat

This is the system's PACEMAKER — an independent daemon thread that publishes
`heartbeat.pulse` at 1Hz regardless of consciousness loop state.

WHY THIS EXISTS:
  Previously, heartbeat.pulse was published inside ConsciousnessLoop._tick().
  When the consciousness loop stalled, ALL 99+ fairies lost their heartbeat
  source simultaneously and the watchdog killed them after 300s timeout.

  This is like a human whose heart is wired to their prefrontal cortex —
  if they stop thinking, they stop living. That's wrong.

  The pacemaker runs in its own daemon thread with triple-redundant error
  handling. It CANNOT die unless the entire Python process dies.

INTEGRATION WITH PARADOX ENERGY:
  Subscribes to paradox.energy.pulse to include energy metrics in heartbeat.
  Even with zero paradox energy, the zero-point floor ensures the pacemaker
  never truly stops — just like ParadoxEnergyBridgeFairy's ZERO_POINT_FLOOR.

  "As long as it thinks, it has energy. As long as it has energy, it can think."
  The pacemaker ensures that chain never breaks.

ARCHITECTURE:
  ConsciousnessLoop._tick() → consciousness.tick (thinking)
  HeartbeatPacemaker._beat() → heartbeat.pulse (liveness)

  These are DECOUPLED. Thinking can stall without killing liveness.
  Liveness keeps fairies alive so they can restart thinking.

Created: 2026-02-07
"""

import time
import threading
from typing import Any, Dict, Optional

# ── Infrastructure Tracer (lazy import to avoid circular deps) ──────────
_infra_tracer = None
def _get_tracer():
    global _infra_tracer
    if _infra_tracer is not None:
        return _infra_tracer
    try:
        from infrastructure.infra_tracer import get_infra_tracer
        _infra_tracer = get_infra_tracer()
        _infra_tracer.register_actor("pacemaker", role="daemon",
                                     description="Unkillable 1Hz heartbeat generator")
        return _infra_tracer
    except Exception:
        return None


class HeartbeatPacemaker:
    """
    Independent heartbeat generator — the system's cardiac pacemaker.

    Publishes heartbeat.pulse at 1Hz on its own daemon thread.
    Cannot be stopped by consciousness loop failures.

    The zero-point floor: even in the worst case, beats never stop.
    """

    # Pacemaker rate (Hz) — matches what consciousness loop was doing
    RATE_HZ = 1.0

    # Zero-point energy floor — the pacemaker always has SOMETHING
    # Mirrors ParadoxEnergyBridgeFairy.ZERO_POINT_FLOOR
    ZERO_POINT_FLOOR = 0.005

    def __init__(self, postal):
        """
        Args:
            postal: The PostalCore/TensorFabric instance for publishing
        """
        self._postal = postal
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._beat_count = 0
        self._start_time = 0.0

        # Paradox energy integration
        self._paradox_energy = self.ZERO_POINT_FLOOR
        self._paradox_battery = 0.0
        self._last_paradox_ts = 0.0

        # Subscribe to paradox energy pulse for integration
        self._wire_paradox_energy()

        # Health tracking
        self._consecutive_errors = 0
        self._total_errors = 0
        self._last_beat_ts = 0.0

    def _wire_paradox_energy(self):
        """Subscribe to paradox energy pulse to fuel the pacemaker."""
        try:
            self._postal.subscribe(
                "paradox.energy.pulse",
                self._on_paradox_pulse,
                "pacemaker-paradox"
            )
        except Exception:
            pass  # Run without paradox energy if unavailable

    def _on_paradox_pulse(self, packet):
        """Receive paradox energy updates."""
        try:
            payload = packet.get("payload", packet) if isinstance(packet, dict) else {}
            if isinstance(payload, dict):
                self._paradox_energy = max(
                    self.ZERO_POINT_FLOOR,
                    payload.get("energy", self.ZERO_POINT_FLOOR)
                )
                self._paradox_battery = payload.get("battery", 0.0)
                self._last_paradox_ts = time.time()
        except Exception:
            pass  # Never let paradox errors affect heartbeat

    def start(self) -> None:
        """Start the pacemaker. Idempotent — safe to call multiple times."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._start_time = time.time()

        self._thread = threading.Thread(
            target=self._loop,
            name="HeartbeatPacemaker",
            daemon=True  # Dies with the process
        )
        self._thread.start()
        print("[HeartbeatPacemaker] STARTED — independent heartbeat at 1Hz")

        # ── Trace lifecycle ──
        t = _get_tracer()
        if t:
            t.lifecycle("pacemaker", "started", {"rate_hz": self.RATE_HZ})

    def stop(self) -> None:
        """Stop the pacemaker gracefully."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

        print(f"[HeartbeatPacemaker] Stopped after {self._beat_count} beats")

        t = _get_tracer()
        if t:
            t.lifecycle("pacemaker", "stopped", {
                "beats": self._beat_count, "errors": self._total_errors,
            })

    def _loop(self) -> None:
        """
        The main pacemaker loop — TRIPLE REDUNDANT error handling.

        This loop CANNOT die from exceptions. Every possible failure
        point is wrapped. The only way this stops is:
        1. _stop_event is set (graceful shutdown)
        2. The entire Python process exits (daemon thread)
        """
        # Import global shutdown check
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import is_global_shutdown
        except ImportError:
            is_global_shutdown = lambda: False

        print(f"[HeartbeatPacemaker] Loop started (thread={threading.current_thread().name})")

        while not self._stop_event.is_set():
            # Check global shutdown
            try:
                if is_global_shutdown():
                    print("[HeartbeatPacemaker] Global shutdown — stopping")
                    break
            except Exception:
                pass  # Can't check shutdown, keep beating anyway

            # === THE BEAT — triple-wrapped for resilience ===
            try:
                self._beat()
                self._consecutive_errors = 0
            except Exception as e:
                # Level 1: Beat failed, try minimal publish
                self._consecutive_errors += 1
                self._total_errors += 1
                # ── Trace beat errors (emit every 5th consecutive) ──
                if self._consecutive_errors == 1 or self._consecutive_errors % 5 == 0:
                    _t = _get_tracer()
                    if _t:
                        _t.emit("pacemaker", "beat_error", {
                            "consecutive": self._consecutive_errors,
                            "total_errors": self._total_errors,
                            "error": str(e)[:200],
                        }, severity="error" if self._consecutive_errors >= 5 else "warning")
                try:
                    self._minimal_beat()
                except Exception:
                    # Level 2: Even minimal beat failed
                    # Just increment counter and try again next cycle
                    try:
                        print(f"[HeartbeatPacemaker] Beat failed ({self._consecutive_errors}x): {e}")
                    except Exception:
                        pass  # Can't even print, just survive

            # Sleep until next beat
            try:
                self._stop_event.wait(1.0 / self.RATE_HZ)
            except Exception:
                # Even wait failed — busy-wait as last resort
                try:
                    time.sleep(1.0 / self.RATE_HZ)
                except Exception:
                    pass

        print(f"[HeartbeatPacemaker] Loop exited after {self._beat_count} beats "
              f"({self._total_errors} errors)")

    def _beat(self) -> None:
        """Publish a single heartbeat.pulse event."""
        now = time.time()
        self._beat_count += 1
        self._last_beat_ts = now

        pulse_data = {
            "beat": self._beat_count,
            "ts": now,
            "source": "pacemaker",  # Distinguishes from consciousness-loop origin
            "uptime": now - self._start_time,
            "paradox_energy": self._paradox_energy,
            "paradox_battery": self._paradox_battery,
            "errors": self._total_errors,
        }

        # === PRIMARY: Direct-call delivery via HeartbeatRegistry ===
        # Cannot be dropped. Every registered fairy gets every beat.
        try:
            from consciousness.heartbeat_registry import get_heartbeat_registry
            registry = get_heartbeat_registry()
            stats = registry.pulse(pulse_data)
            self._last_registry_stats = stats
        except Exception as e:
            # Registry failed — postal below is the backup
            if self._beat_count <= 3 or self._beat_count % 300 == 0:
                print(f"[HeartbeatPacemaker] Registry pulse failed: {e}", flush=True)

        # === BACKUP: Postal publish for non-fairy consumers (MCP, dashboard) ===
        # Drops here are acceptable — fairies already got their beat above.
        try:
            self._postal.publish("heartbeat.pulse", pulse_data)
        except Exception:
            pass  # Postal failure is non-critical now

    def _minimal_beat(self) -> None:
        """Minimal fallback beat — just enough to keep watchdog happy."""
        self._beat_count += 1
        self._last_beat_ts = time.time()

        pulse_data = {
            "beat": self._beat_count,
            "ts": self._last_beat_ts,
            "source": "pacemaker-fallback",
        }

        # Direct delivery first (cannot drop)
        try:
            from consciousness.heartbeat_registry import get_heartbeat_registry
            get_heartbeat_registry().pulse(pulse_data)
        except Exception:
            pass

        # Postal backup
        try:
            self._postal.publish("heartbeat.pulse", pulse_data)
        except Exception:
            pass

    @property
    def beat_count(self) -> int:
        return self._beat_count

    @property
    def is_running(self) -> bool:
        return self._running and (self._thread is not None and self._thread.is_alive())

    def get_status(self) -> Dict[str, Any]:
        """Get pacemaker health status."""
        now = time.time()
        status = {
            "running": self.is_running,
            "beat_count": self._beat_count,
            "uptime": now - self._start_time if self._start_time else 0,
            "rate_hz": self.RATE_HZ,
            "last_beat_ts": self._last_beat_ts,
            "last_beat_age": now - self._last_beat_ts if self._last_beat_ts else -1,
            "consecutive_errors": self._consecutive_errors,
            "total_errors": self._total_errors,
            "paradox_energy": self._paradox_energy,
            "paradox_battery": self._paradox_battery,
            "source": "HeartbeatPacemaker",
        }

        # Include registry delivery stats if available
        registry_stats = getattr(self, '_last_registry_stats', None)
        if registry_stats:
            status["registry"] = registry_stats

        return status


# =============================================================================
# SINGLETON
# =============================================================================

_pacemaker_instance: Optional[HeartbeatPacemaker] = None
_pacemaker_lock = threading.Lock()


def get_pacemaker() -> Optional[HeartbeatPacemaker]:
    """Get the global pacemaker instance (if started)."""
    return _pacemaker_instance


def start_pacemaker(postal) -> HeartbeatPacemaker:
    """Start the global pacemaker singleton."""
    global _pacemaker_instance
    with _pacemaker_lock:
        if _pacemaker_instance is None:
            _pacemaker_instance = HeartbeatPacemaker(postal)
        _pacemaker_instance.start()
        return _pacemaker_instance
