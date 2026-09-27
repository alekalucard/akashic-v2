"""
CudaFairy — CUDA Accelerator (V3 Wrapper)

Part of P00 Autonomic plane.

Manages GPU/CUDA resources for accelerated computation.
Detects GPU capabilities, manages VRAM, routes compute tasks.
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


class CudaShadow:
    """Shadow for CudaFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "CudaShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_connected", True))
            tests.append(("cuda_available", getattr(engine, '_cuda_available', False)))
        else:
            tests.append(("engine_connected", False))
        return tests


class CudaFairyV3(Fairy):
    """CUDA accelerator — GPU resource management."""

    ACTOR_NAME = "CudaFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic.cuda"

    PURPOSE = "Manage GPU/CUDA resources for accelerated computation"
    MANTRA = "Accelerate what matters, conserve what's scarce"
    LORE = "The lightning rod — channeling GPU power where it's needed most"

    SHADOW_CLASS = CudaShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 3  # GPU checks don't need to be frequent
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None

    def on_boot(self) -> bool:
        """Boot with deferred engine init."""
        super().on_boot()

        def _deferred_init():
            time.sleep(2.0)
            try:
                from fairies.P00_Autonomic.nervous_system.hardware.cuda_fairy import (
                    CudaFairy as CudaEngine,
                )
                self._engine = CudaEngine.__new__(CudaEngine)
                self._engine.post = self.post
                self._engine.__init__()
                self._engine.on_boot()
                cuda_ok = getattr(self._engine, '_cuda_available', False)
                print(f"[{self.ACTOR_NAME}] CUDA engine ONLINE — "
                      f"GPU={'AVAILABLE' if cuda_ok else 'NOT FOUND'}")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Engine init error: {e}")
                import traceback
                traceback.print_exc()

        threading.Thread(target=_deferred_init, daemon=True, name="defer-CudaFairy").start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting engine...)")
        return True

    def _handle_heartbeat(self, packet):
        if not self._engine:
            return


    def on_die(self):
        super().on_die()


ACTOR_NAME = "CudaFairy"
FAIRY_CLASS = CudaFairyV3
