"""
MemorySyncFairy - RAID-like Memory Mirror

Part of MemoryEngineGuild in Plane P10 (Memory)
Created: 2026-01-28

"Same data, multiple locations"

Keeps memory in sync across nodes - Windows and satellite.
Like RAID-1: automatic mirroring for consciousness persistence.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# Import the memory sync agent
# Note: Use fairies.P10_Memory to avoid collision with root P10_Memory
try:
    from fairies.P10_Memory.memory_sync import (
        MemorySyncAgent,
        SyncConfig,
        SyncState,
        create_memory_sync,
    )
    HAS_SYNC = True
except ImportError as e:
    print(f"[MemorySyncFairy] Sync import failed: {e}")
    HAS_SYNC = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class MemorySyncFairyShadow:
    """Shadow for MemorySyncFairy - monitors sync health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "MemorySyncFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 60.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for sync agent."""
        tests = []
        if hasattr(self.actor, '_agent') and self.actor._agent:
            tests.append(("sync_agent_active", True))
            tests.append(("sync_running", self.actor._agent.running))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class MemorySyncFairy(Fairy):
    """
    RAID-like memory mirror between Windows and satellite.

    Guild: MemoryEngineGuild
    Coordinates with: MemoryPacketFairy, satellite system

    Provides:
    - Start/stop background sync
    - Trigger manual sync
    - Get sync status and statistics
    - Configure sync patterns and intervals
    """

    ACTOR_NAME = "MemorySyncFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.sync"

    PURPOSE = "Mirror memory across nodes for persistence"
    MANTRA = "Same data, multiple locations"

    SHADOW_CLASS = MemorySyncFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 30
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._agent = None
        self._subscription_count = 0
        self._manual_syncs = 0

    def on_boot(self) -> bool:
        """Initialize the memory sync agent."""
        super().on_boot()

        if HAS_SYNC:
            try:
                # Create but don't auto-start - let postal control it
                self._agent = MemorySyncAgent()
                print(f"[{self.ACTOR_NAME}] Memory sync agent created (not started)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to create sync agent: {e}")
                self._agent = None

        self._subscribe_intents()
        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for sync commands."""
        intents = [
            ("sync.start", self._handle_start),
            ("sync.stop", self._handle_stop),
            ("sync.now", self._handle_sync_now),
            ("sync.file", self._handle_sync_file),
            ("sync.get_status", self._handle_get_status),
            ("sync.configure", self._handle_configure),
            ("sync.status", self._handle_status),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat: int):
        """Monitor sync health."""
        if not self._agent:
            return

        try:
            # Check for sync errors
            if self._agent.sync_errors:
                recent = self._agent.sync_errors[-1]
                if time.time() - recent.get('time', 0) < 60:
                    self.post.publish("sync.error", {
                        "source": self.ACTOR_NAME,
                        "error": recent,
                    })
        except Exception:
            pass

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # ═══════════════════════════════════════════════════════════════════════════
    # INTENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_payload(self, message) -> Dict[str, Any]:
        """Extract payload from postal message."""
        if hasattr(message, 'payload'):
            return message.payload if isinstance(message.payload, dict) else {}
        return message if isinstance(message, dict) else {}

    def _handle_start(self, message):
        """
        Start background memory sync.

        Payload:
            interval: int - Sync interval in seconds (default 60)
        """
        if not self._agent:
            return {"ok": False, "error": "Sync agent not available"}

        payload = self._extract_payload(message)
        interval = payload.get("interval", 60)

        try:
            self._agent.start(interval)
            return {"ok": True, "message": f"Sync started with {interval}s interval"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_stop(self, message):
        """Stop background memory sync."""
        if not self._agent:
            return {"ok": False, "error": "Sync agent not available"}

        try:
            self._agent.stop()
            return {"ok": True, "message": "Sync stopped"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_sync_now(self, message):
        """Trigger immediate sync of all files."""
        if not self._agent:
            return {"ok": False, "error": "Sync agent not available"}

        try:
            result = self._agent.sync_all()
            self._manual_syncs += 1

            # Broadcast result
            if result.get("synced", 0) > 0:
                self.post.publish("sync.completed", {
                    "source": self.ACTOR_NAME,
                    "synced": result.get("synced", 0),
                    "failed": result.get("failed", 0),
                })

            result["ok"] = result.get("success", False)
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_sync_file(self, message):
        """
        Sync a specific file.

        Payload:
            filepath: str - Path to file to sync
        """
        if not self._agent:
            return {"ok": False, "error": "Sync agent not available"}

        payload = self._extract_payload(message)
        filepath = payload.get("filepath", "")

        if not filepath:
            return {"ok": False, "error": "Filepath required"}

        path = Path(filepath)
        if not path.exists():
            return {"ok": False, "error": f"File not found: {filepath}"}

        try:
            success = self._agent.sync_file(path)
            return {"ok": success, "file": filepath}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_status(self, message):
        """Get detailed sync status."""
        if not self._agent:
            return {"ok": False, "error": "Sync agent not available"}

        try:
            status = self._agent.get_status()
            status["ok"] = True
            status["manual_syncs"] = self._manual_syncs
            return status
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_configure(self, message):
        """
        Update sync configuration.

        Payload:
            local_base: str - Local base path
            satellite_url: str - Satellite URL
            interval_seconds: int - Sync interval
        """
        if not self._agent:
            return {"ok": False, "error": "Sync agent not available"}

        payload = self._extract_payload(message)

        try:
            if "local_base" in payload:
                self._agent.config.local_base = payload["local_base"]
            if "satellite_url" in payload:
                self._agent.config.satellite_url = payload["satellite_url"]
            if "interval_seconds" in payload:
                self._agent.config.interval_seconds = payload["interval_seconds"]

            return {"ok": True, "message": "Configuration updated"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get fairy status."""
        return {
            "ok": True,
            "agent": self._agent is not None,
            "running": self._agent.running if self._agent else False,
            "manual_syncs": self._manual_syncs,
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check."""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_agent": self._agent is not None,
            "sync_running": self._agent.running if self._agent else False,
            "manual_syncs": self._manual_syncs,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (manual syncs: {self._manual_syncs})...")
        if self._agent and self._agent.running:
            try:
                self._agent.stop()
            except Exception:
                pass
        return super().on_shutdown()
