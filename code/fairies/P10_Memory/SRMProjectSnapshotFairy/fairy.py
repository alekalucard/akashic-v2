"""
SRMProjectSnapshotFairy — Project Snapshot (V3 Wrapper)

Part of P10 Memory plane / Triple Helix SRM cluster.

Takes periodic snapshots of the project state for versioning and rollback.
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


class SRMProjectSnapshotShadow:
    """Shadow for SRMProjectSnapshotFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "SRMProjectSnapshotShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_connected", True))
            tests.append(("polling", getattr(engine, '_poll_running', False)))
        else:
            tests.append(("engine_connected", False))
        return tests


class SRMProjectSnapshotFairyV3(Fairy):
    """Project state snapshotter — versioning and rollback."""

    ACTOR_NAME = "SRMProjectSnapshotFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.snapshot"

    PURPOSE = "Take periodic snapshots of project state for versioning and rollback"
    MANTRA = "Capture the moment, preserve the state"
    LORE = "The photographer of code — freezing moments in time for safety"

    SHADOW_CLASS = SRMProjectSnapshotShadow

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
                from fairies.P10_Memory.triple_helix_srm_memory.snapshot_fairy import (
                    SRMProjectSnapshotFairy as SnapshotEngine,
                )
                self._engine = SnapshotEngine.__new__(SnapshotEngine)
                self._engine.post = self.post
                self._engine.__init__()
                self._engine.on_boot()
                print(f"[{self.ACTOR_NAME}] Project snapshot engine ONLINE")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Engine init error: {e}")
                import traceback
                traceback.print_exc()

        threading.Thread(target=_deferred_init, daemon=True, name="defer-SRMProjectSnapshot").start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting engine...)")
        return True

    def _handle_heartbeat(self, packet):
        if not self._engine:
            return


    def on_die(self):
        if self._engine and hasattr(self._engine, '_poll_running'):
            self._engine._poll_running = False
        super().on_die()


ACTOR_NAME = "SRMProjectSnapshotFairy"
FAIRY_CLASS = SRMProjectSnapshotFairyV3
