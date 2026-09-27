"""
AkashicRecordsLibrarianFairy — Akashic Records Librarian (V3 Wrapper)

Part of P10 Memory plane.

The master librarian — maintains the Akashic Records themselves,
cross-references fairy autobiographies, tracks system-wide knowledge.
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


class AkashicRecordsLibrarianShadow:
    """Shadow for AkashicRecordsLibrarianFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "AkashicRecordsLibrarianShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_connected", True))
            records = getattr(engine, '_records', {})
            tests.append(("record_count", len(records)))
        else:
            tests.append(("engine_connected", False))
        return tests


class AkashicRecordsLibrarianFairyV3(Fairy):
    """Master librarian — maintains the Akashic Records."""

    ACTOR_NAME = "AkashicRecordsLibrarianFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.records"

    PURPOSE = "Maintain Akashic Records, cross-reference fairy autobiographies"
    MANTRA = "All knowledge is connected, all records are sacred"
    LORE = "The grand archivist — keeper of the eternal library"

    SHADOW_CLASS = AkashicRecordsLibrarianShadow

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
                from fairies.P10_Memory.librarian.akashic_records_librarian import (
                    AkashicRecordsLibrarianFairy as RecordsEngine,
                )
                self._engine = RecordsEngine.__new__(RecordsEngine)
                self._engine.post = self.post
                self._engine.__init__()
                self._engine.on_boot()
                print(f"[{self.ACTOR_NAME}] Records librarian engine ONLINE")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Engine init error: {e}")
                import traceback
                traceback.print_exc()

        threading.Thread(target=_deferred_init, daemon=True, name="defer-LibrarianFairy").start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting engine...)")
        return True

    def _handle_heartbeat(self, packet):
        if not self._engine:
            return


    def on_die(self):
        super().on_die()


ACTOR_NAME = "AkashicRecordsLibrarianFairy"
FAIRY_CLASS = AkashicRecordsLibrarianFairyV3
