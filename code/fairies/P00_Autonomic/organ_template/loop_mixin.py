"""
HeavyFairyLoopMixin — Self-paced daemon loop for heavy fairies.

2026-04-11 (Nous + Ace): "I wonder if we are using ticks but should be using loops."

SRM history: Heavy fairies (SomaticMind 8.5s, ACF 60s, SomaticEngine 75s) have
been fixed 3 times by making specific calls async. Each time new synchronous calls
crept back in. The loop pattern solves it permanently.

Ticks = heartbeat pushes work, shared worker pool, starvation risk.
Loops = fairy runs own daemon thread, self-paced, independent.

Lightweight heartbeat callbacks (liveness echo, timestamp) stay as ticks.
Heavy work (portal IPC, SRM, thinking, somatic processing) runs in the loop.

ConsciousnessLoop is the proven model. SRM warns about:
- Zombie state (Feb 19): thread dies, flag stays True → need is_alive() check
- Deadlock (Feb 19): postal.publish() under RLock → use fire-and-forget
"""

import threading
import time


class HeavyFairyLoopMixin:
    """Mixin for fairies that run their own daemon loop instead of on_tick.

    Usage:
        class MyHeavyFairy(HeavyFairyLoopMixin, Fairy):
            LOOP_INTERVAL = 10.0

            def on_boot(self):
                super().on_boot()
                self._start_loop()

            def _loop_tick(self):
                # Heavy work here — portal calls, SRM, thinking
                pass
    """

    LOOP_INTERVAL = 10.0       # Seconds between iterations (override per fairy)
    LOOP_ENERGY_GATE = True    # Check plane battery before each iteration
    LOOP_LOW_ENERGY_MULTIPLIER = 3.0  # Sleep multiplier when battery low

    def _start_loop(self):
        """Start the daemon loop. Call from on_boot()."""
        self._loop_running = True
        self._loop_iteration = 0
        self._loop_last_duration = 0.0
        self._loop_errors = 0
        self._loop_thread = threading.Thread(
            target=self._loop_wrapper,
            daemon=True,
            name=f"{getattr(self, 'ACTOR_NAME', 'fairy')}-loop",
        )
        self._loop_thread.start()
        _name = getattr(self, 'ACTOR_NAME', '?')
        print(f"[{_name}] LOOP STARTED (interval={self.LOOP_INTERVAL}s, "
              f"energy_gate={self.LOOP_ENERGY_GATE})", flush=True)

    def _stop_loop(self):
        """Stop the daemon loop. Call from on_shutdown()."""
        self._loop_running = False

    def _loop_wrapper(self):
        """Main loop. Runs in daemon thread. Survives exceptions."""
        _name = getattr(self, 'ACTOR_NAME', '?')
        _interval = self.LOOP_INTERVAL

        while getattr(self, '_loop_running', False):
            t0 = time.perf_counter()
            try:
                # ── Energy gate ──
                if self.LOOP_ENERGY_GATE:
                    _sleep_mult = self._loop_check_energy()
                    if _sleep_mult > 1.0:
                        time.sleep(_interval * _sleep_mult)
                        continue

                # ── Do the work ──
                self._loop_tick()
                self._loop_iteration += 1

            except Exception as e:
                # NEVER let the loop die from an exception
                self._loop_errors += 1
                if self._loop_errors <= 3 or self._loop_errors % 50 == 0:
                    print(f"[{_name}] Loop error #{self._loop_errors} (survived): {e}",
                          flush=True)

            self._loop_last_duration = time.perf_counter() - t0
            time.sleep(_interval)

    def _loop_check_energy(self) -> float:
        """Check plane battery. Returns sleep multiplier (1.0 = normal, >1 = slow down)."""
        try:
            from infrastructure.plane_battery import get_plane_battery
            _plane = getattr(self, 'ACTOR_PLANE', 'P30')
            pb = get_plane_battery(_plane)
            if pb:
                _cap = getattr(pb, 'capacitor', None)
                _charge = getattr(_cap, 'charge_level', 1.0) if _cap else 1.0

                if _charge < 0.10:
                    return self.LOOP_LOW_ENERGY_MULTIPLIER  # Very slow
                elif _charge < 0.25:
                    return 2.0  # Slower
        except Exception:
            pass
        return 1.0  # Normal speed

    def _loop_tick(self):
        """Override this with the heavy work. Replaces the heavy parts of on_tick()."""
        pass

    def _check_loop_health(self):
        """Call from lightweight on_tick to detect zombie loop. Restart if dead."""
        _thread = getattr(self, '_loop_thread', None)
        if _thread and not _thread.is_alive() and getattr(self, '_loop_running', False):
            _name = getattr(self, 'ACTOR_NAME', '?')
            print(f"[{_name}] LOOP ZOMBIE DETECTED — restarting", flush=True)
            self._start_loop()

    def get_loop_state(self) -> dict:
        """Return loop diagnostics for status/dashboard."""
        return {
            "loop_running": getattr(self, '_loop_running', False),
            "loop_alive": getattr(self, '_loop_thread', None) is not None
                          and self._loop_thread.is_alive(),
            "loop_iteration": getattr(self, '_loop_iteration', 0),
            "loop_last_duration_ms": round(
                getattr(self, '_loop_last_duration', 0) * 1000, 1),
            "loop_errors": getattr(self, '_loop_errors', 0),
            "loop_interval": self.LOOP_INTERVAL,
        }
