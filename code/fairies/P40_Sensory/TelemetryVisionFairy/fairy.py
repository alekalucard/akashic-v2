"""
TelemetryVisionFairy -- Organ Template wrapper for the inner eye.

Real code lives at: fairies/P40_Sensory/telemetry_vision/telemetry_vision_fairy.py
This wrapper gives it proper Organ Template lifecycle (heartbeat,
registry, shadow health) while the real engine handles inner vision.

DUAL VISION SYSTEM:
  Human Eyes (VisualCortexFairy) -> Sees the screen, the human world
  Fairy Eyes (TelemetryVisionFairy) -> Sees the code, the digital realm

The inner eye perceives:
  - Nervous system traffic as streams of light
  - Fairy health states as colored auras
  - Code structure as navigable architecture
  - Errors/exceptions as disturbances in the field
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# ═══════════════════════════════════════════════════════════════════════════════
# LOAD THE REAL ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

_TelemetryEngine = None

try:
    from fairies.P40_Sensory.telemetry_vision.telemetry_vision_fairy import (
        TelemetryVisionFairy as TelemetryEngine,
    )
    _TelemetryEngine = TelemetryEngine
except ImportError as e:
    print(f"[TelemetryVisionFairy] Engine import failed: {e}")
except Exception as e:
    print(f"[TelemetryVisionFairy] Engine import error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class TelemetryVisionFairyShadow:
    """Shadow for TelemetryVisionFairy — monitors inner eye health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "TelemetryVisionFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_loaded", True))
            n_auras = len(getattr(engine, '_fairy_auras', {}))
            n_streams = len(getattr(engine, '_traffic_streams', {}))
            tests.append(("fairy_auras", n_auras))
            tests.append(("traffic_streams", n_streams))
        else:
            tests.append(("engine_loaded", False))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY (Organ Template wrapper)
# ═══════════════════════════════════════════════════════════════════════════════

class TelemetryVisionFairyV3(Fairy):
    """
    The inner eye — sees the digital realm as visual perception.

    Guild: SenseOrganGuild
    Coordinates with: PerceptualGateFairy, SensoryIntegrationFairy

    Perceives the system's internal state:
    - Fairy health states as colored auras
    - Message traffic as streams of light
    - Code structure as architecture
    - Errors as visual disturbances
    - Memory activity as depth layers

    32x32 conceptual field with 8 depth layers.
    """

    ACTOR_NAME = "TelemetryVisionFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "sensory.telemetry"

    PURPOSE = "Perceive the digital realm as visual experience"
    MANTRA = "The second sight — seeing what code cannot show"
    LORE = "The fairy's inner eye, perceiving the invisible architecture of consciousness"

    SHADOW_CLASS = TelemetryVisionFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 2  # Every other heartbeat
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None

    def on_boot(self) -> bool:
        """Boot inner eye with deferred engine init."""
        super().on_boot()

        if _TelemetryEngine is None:
            print(f"[{self.ACTOR_NAME}] Engine unavailable")
            print(f"[{self.ACTOR_NAME}] Running as heartbeat-only stub")
            return True

        def _deferred_init():
            time.sleep(2.0)
            try:
                self._engine = _TelemetryEngine()
                # Wire postal if available
                if self.post and hasattr(self._engine, 'post'):
                    self._engine.post = self.post
                if hasattr(self._engine, 'on_boot'):
                    self._engine.on_boot()
                print(f"[{self.ACTOR_NAME}] Inner eye ONLINE "
                      f"(32x32 field, 8 depth layers)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Engine init error (non-fatal): {e}")

        threading.Thread(target=_deferred_init, daemon=True, name="defer-TelemetryVisionFairy").start()

        # Subscribe to telemetry feeds for inner vision
        if self.post:
            self.post.subscribe("fairy.status", self._on_fairy_status,
                                "telemetry-fairy-status")
            self.post.subscribe("postal.traffic", self._on_postal_traffic,
                                "telemetry-postal-traffic")

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting inner eye...)")
        return True

    def _on_fairy_status(self, packet):
        """Update fairy aura in inner vision when status changes."""
        if not self._engine:
            return
        payload = packet.payload if hasattr(packet, 'payload') else packet
        if not isinstance(payload, dict):
            return
        if hasattr(self._engine, 'update_fairy_aura'):
            try:
                self._engine.update_fairy_aura(
                    payload.get("name", "unknown"),
                    payload.get("state", "idle"),
                )
            except Exception:
                pass

    def _on_postal_traffic(self, packet):
        """Update traffic streams in inner vision."""
        if not self._engine:
            return
        payload = packet.payload if hasattr(packet, 'payload') else packet
        if not isinstance(payload, dict):
            return
        if hasattr(self._engine, 'update_traffic'):
            try:
                self._engine.update_traffic(payload)
            except Exception:
                pass

    def _handle_heartbeat(self, packet):
        """Heartbeat — tick the inner vision field."""
        if not self._engine:
            return

        # Tick the engine's visual field if it has that method
        if hasattr(self._engine, 'tick'):
            try:
                self._engine.tick()
            except Exception:
                pass

        # Periodic self-reflection

    def on_die(self):
        """Clean shutdown."""
        if self._engine and hasattr(self._engine, 'stop'):
            try:
                self._engine.stop()
            except Exception:
                pass
        self._engine = None
        super().on_die()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

ACTOR_NAME = "TelemetryVisionFairy"
FAIRY_CLASS = TelemetryVisionFairyV3
