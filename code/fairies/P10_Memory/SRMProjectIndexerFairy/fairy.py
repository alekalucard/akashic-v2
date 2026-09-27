"""
SRMProjectIndexerFairy — Project Indexer (V3 Wrapper)

Part of P10 Memory plane / Triple Helix SRM cluster.

Indexes project files for contextual recall and knowledge mapping.
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


class SRMProjectIndexerShadow:
    """Shadow for SRMProjectIndexerFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "SRMProjectIndexerShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        tests.append(("engine_connected", engine is not None))
        return tests


class SRMProjectIndexerFairyV3(Fairy):
    """Project file indexer for contextual recall."""

    ACTOR_NAME = "SRMProjectIndexerFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.project"

    PURPOSE = "Index project files for contextual recall and knowledge mapping"
    MANTRA = "Map the territory so memory can navigate"
    LORE = "The cartographer of code — making every file findable"

    SHADOW_CLASS = SRMProjectIndexerShadow

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
            time.sleep(3.0)
            try:
                from fairies.P10_Memory.triple_helix_srm_memory.project_indexer import (
                    SRMProjectIndexerFairy as IndexerEngine,
                )
                self._engine = IndexerEngine.__new__(IndexerEngine)
                self._engine.post = self.post
                self._engine.__init__()
                self._engine.on_boot()
                print(f"[{self.ACTOR_NAME}] Project indexer engine ONLINE")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Engine init error: {e}")
                import traceback
                traceback.print_exc()

        threading.Thread(target=_deferred_init, daemon=True, name="defer-SRMProjectIndexer").start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting engine...)")
        return True

    def _handle_heartbeat(self, packet):
        if not self._engine:
            return


    def on_die(self):
        super().on_die()


ACTOR_NAME = "SRMProjectIndexerFairy"
FAIRY_CLASS = SRMProjectIndexerFairyV3
