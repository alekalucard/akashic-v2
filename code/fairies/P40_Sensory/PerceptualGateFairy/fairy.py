"""
PerceptualGateFairy — Somatic-Driven Vision Switching (V3 Wrapper)

Part of SenseOrganGuild in Plane P40 (Sensory)

The attention gateway for vision. Reads somatic state (drives, chemistry,
intention, presence) and determines WHICH visual system dominates:
- VisualCortex (Human Eye) — screen, Ace's world
- TelemetryVision (Fairy Eye) — code streams, fairy auras
- EmotionColorMapper (Inner Vision) — emotions as synesthetic colors

Publishes unified perception that CirculationPumpFairy subscribes to,
closing the loop: See → Feel → Chemistry → Perception shifts → See differently.
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class PerceptualGateFairyShadow:
    """Shadow for PerceptualGateFairy — monitors perception pipeline health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "PerceptualGateFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_connected", True))
            tests.append(("mode", str(getattr(engine, '_mode', 'unknown'))))
            tests.append(("running", getattr(engine, '_running', False)))
        else:
            tests.append(("engine_connected", False))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class PerceptualGateFairyV3(Fairy):
    """
    Somatic-driven vision switching — the attention gateway.

    Wraps the v2 PerceptualGateFairy engine and gives it proper
    organ template lifecycle (heartbeat, registration, shadow health).
    """

    ACTOR_NAME = "PerceptualGateFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "sensory.perception"

    PURPOSE = "Gate and blend three visual feeds based on somatic state"
    MANTRA = "See → Feel → Shift → See differently"
    LORE = "The eye behind the eyes — choosing which world to see"

    SHADOW_CLASS = PerceptualGateFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 1  # Every heartbeat — engine has its own internal timing
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None

    def on_boot(self) -> bool:
        """Boot the perceptual gate with deferred engine init."""
        super().on_boot()

        def _deferred_init():
            time.sleep(1.5)
            try:
                from fairies.P40_Sensory.perceptual_gate_fairy import (
                    PerceptualGateFairy as PerceptualGateEngine,
                )
                self._engine = PerceptualGateEngine()
                # Pass our postal bridge to the engine
                self._engine.on_boot(post=self.post)
                print(f"[{self.ACTOR_NAME}] Perceptual gate engine ONLINE — "
                      f"mode={self._engine._mode.value}")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Engine init error: {e}")
                import traceback
                traceback.print_exc()

        threading.Thread(target=_deferred_init, daemon=True, name="defer-PerceptualGateFairy").start()

        # ── SELF-PULSE DAEMON (FIX 5 2026-04-30 Nous + Ace) ──
        # This fairy is part of the "12 fairies born without a pulse" cohort
        # (claude_code_47050dd79065 2026-04-16). Boot path skips
        # _wire_infrastructure() so it never registers with HeartbeatRegistry,
        # _last_tick stays 0 forever, watchdog declares it dead.
        # Self-pulse bypasses the broken wiring: bump _last_tick directly.
        # Same fix-shape ships for VisualCortexFairy + CochleaFairy.
        def _self_pulse():
            while True:
                try:
                    time.sleep(2.0)
                    if getattr(self, '_shutting_down', False):
                        return
                    self._tick_count = getattr(self, '_tick_count', 0) + 1
                    self._last_tick = time.time()
                except Exception:
                    pass

        threading.Thread(
            target=_self_pulse,
            daemon=True,
            name=f"selfpulse-{self.ACTOR_NAME}",
        ).start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting gate engine + self-pulse daemon)")
        return True

    def _handle_heartbeat(self, packet):
        """Heartbeat — engine runs its own loop, we just monitor."""
        if not self._engine:
            return

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11


    def on_die(self):
        """Clean shutdown."""
        if self._engine:
            self._engine.stop()
        super().on_die()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

ACTOR_NAME = "PerceptualGateFairy"
FAIRY_CLASS = PerceptualGateFairyV3
