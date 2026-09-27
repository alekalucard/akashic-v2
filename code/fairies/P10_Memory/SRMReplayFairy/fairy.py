"""
SRMReplayFairy — Memory Replay Adapter (V3 Wrapper)

Part of P10 Memory plane / Triple Helix SRM cluster.

Replays memories to strengthen recall and create new associations.
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


class SRMReplayShadow:
    """Shadow for SRMReplayFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "SRMReplayShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        tests.append(("engine_connected", engine is not None))
        return tests


class SRMReplayFairyV3(Fairy):
    """Memory replay adapter — strengthens recall through repetition."""

    ACTOR_NAME = "SRMReplayFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.replay"

    PURPOSE = "Replay memories to strengthen recall and create new associations"
    MANTRA = "Relive to remember, repeat to reinforce"
    LORE = "The dreamer of memories — replaying experience to deepen understanding"

    SHADOW_CLASS = SRMReplayShadow

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
            time.sleep(2.5)
            try:
                from fairies.P10_Memory.triple_helix_srm_memory.replay_adapter import (
                    SRMReplayFairy as ReplayEngine,
                )
                self._engine = ReplayEngine.__new__(ReplayEngine)
                self._engine.post = self.post
                self._engine.__init__()
                self._engine.on_boot()
                print(f"[{self.ACTOR_NAME}] Replay adapter engine ONLINE")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Engine init error: {e}")
                import traceback
                traceback.print_exc()

        threading.Thread(target=_deferred_init, daemon=True, name="defer-SRMReplayFairy").start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting engine...)")
        return True

    def _handle_heartbeat(self, packet):
        if not self._engine:
            return


    def on_die(self):
        super().on_die()


ACTOR_NAME = "SRMReplayFairy"
FAIRY_CLASS = SRMReplayFairyV3
