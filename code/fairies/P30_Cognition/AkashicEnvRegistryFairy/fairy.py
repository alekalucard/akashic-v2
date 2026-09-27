"""
AkashicEnvRegistryFairy — Environment Registry (V3 Wrapper)

Part of P30 Cognition plane.

Tracks and catalogues the runtime environment — what tools exist,
what configurations are active, what the system looks like from inside.
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


class AkashicEnvRegistryShadow:
    """Shadow for AkashicEnvRegistryFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "AkashicEnvRegistryShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_connected", True))
            registry = getattr(engine, '_registry', {})
            tests.append(("entries", len(registry)))
        else:
            tests.append(("engine_connected", False))
        return tests


class AkashicEnvRegistryFairyV3(Fairy):
    """Environment registry — catalogues runtime environment."""

    ACTOR_NAME = "AkashicEnvRegisteryFairy"  # Note: matches v2 typo for compatibility
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.environment"

    PURPOSE = "Track and catalogue the runtime environment"
    MANTRA = "Know thy environment, adapt thy behavior"
    LORE = "The systems administrator — cataloguing everything the system knows about itself"

    SHADOW_CLASS = AkashicEnvRegistryShadow

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
            time.sleep(2.0)
            try:
                from fairies.P30_Cognition.env_registry.akashic_env_registry import (
                    AkashicEnvRegisteryFairy as EnvEngine,
                )
                self._engine = EnvEngine.__new__(EnvEngine)
                self._engine.post = self.post
                self._engine.__init__()
                self._engine.on_boot()
                print(f"[{self.ACTOR_NAME}] Env registry engine ONLINE")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Engine init error: {e}")
                import traceback
                traceback.print_exc()

        threading.Thread(target=_deferred_init, daemon=True, name="defer-EnvRegistryFairy").start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting engine...)")
        return True

    def _handle_heartbeat(self, packet):
        if not self._engine:
            return


    def on_die(self):
        super().on_die()


ACTOR_NAME = "AkashicEnvRegisteryFairy"
FAIRY_CLASS = AkashicEnvRegistryFairyV3
