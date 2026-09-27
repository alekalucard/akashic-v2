"""
HardwareRegulationFairy — Hardware Regulation (V3 Wrapper)

Part of P00 Autonomic plane.

Monitors and regulates hardware resources — CPU, RAM, GPU, thermal.
The body's autonomic temperature and resource regulation.
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


class HardwareRegulationShadow:
    """Shadow for HardwareRegulationFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "HardwareRegulationShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_connected", True))
            hw_state = getattr(engine, '_hw_state', None)
            if hw_state:
                tests.append(("cpu_percent", getattr(hw_state, 'cpu_percent', -1)))
                tests.append(("ram_percent", getattr(hw_state, 'ram_percent', -1)))
        else:
            tests.append(("engine_connected", False))
        return tests


class HardwareRegulationFairyV3(Fairy):
    """Hardware regulation — autonomic resource management."""

    ACTOR_NAME = "HardwareRegulationFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic.hardware"

    PURPOSE = "Monitor and regulate hardware resources — CPU, RAM, GPU, thermal"
    MANTRA = "Keep the body running within safe parameters"
    LORE = "The thermostat — maintaining homeostasis across all hardware"

    SHADOW_CLASS = HardwareRegulationShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 2
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None

    def on_boot(self) -> bool:
        """Boot with deferred engine init."""
        super().on_boot()

        def _deferred_init():
            time.sleep(1.5)
            try:
                from fairies.P00_Autonomic.nervous_system.hardware.hardware_regulation_fairy import (
                    HardwareRegulationFairy as HWEngine,
                )
                self._engine = HWEngine.__new__(HWEngine)
                self._engine.post = self.post
                self._engine.__init__()
                self._engine.on_boot()
                print(f"[{self.ACTOR_NAME}] Hardware regulation engine ONLINE")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Engine init error: {e}")
                import traceback
                traceback.print_exc()

        threading.Thread(target=_deferred_init, daemon=True, name="defer-HardwareRegulationFairy").start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting engine...)")
        return True

    def _handle_heartbeat(self, packet):
        if not self._engine:
            return


    def on_die(self):
        super().on_die()


ACTOR_NAME = "HardwareRegulationFairy"
FAIRY_CLASS = HardwareRegulationFairyV3
