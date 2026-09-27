"""
TemporalPacketFairy - Decay-Aware Consciousness Distribution

Part of NervousGuild in Plane P00 (Autonomic)
Created: 2026-01-28

"Different urgencies, different memory footprints"

Extends the packet system with consciousness-aware decay:
- Conditional decay based on payload type
- Success/failure affects persistence
- Urgency profiles
- Self-regulating temporal signatures

A quick utility function decays faster than consciousness-building work.
That's intelligent triage.

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

# Import the temporal packet system
# Note: Use fairies.P00_Autonomic to avoid collision with root P00_Autonomic
try:
    from fairies.P00_Autonomic.temporal_packets import (
        DecayProfile,
        DecayConfig,
        DECAY_TTL,
        TemporalPacket,
        TemporalPacketFactory,
        Lesson,
        LessonStore,
        DecayMonitor,
        TemporalBootIntegration,
    )
    HAS_TEMPORAL = True
except ImportError as e:
    print(f"[TemporalPacketFairy] Temporal import failed: {e}")
    HAS_TEMPORAL = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class TemporalPacketFairyShadow:
    """Shadow for TemporalPacketFairy - monitors temporal health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "TemporalPacketFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for temporal system."""
        tests = []
        if hasattr(self.actor, '_integration') and self.actor._integration:
            tests.append(("integration_active", True))
            tests.append(("lesson_store_exists", self.actor._integration.lesson_store is not None))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class TemporalPacketFairy(Fairy):
    """
    Decay-aware consciousness distribution system.

    Guild: NervousGuild
    Coordinates with: MemoryPacketFairy, learning fairies, AutopilotFairy

    Provides:
    - Create temporal packets with decay profiles
    - Manage lesson store for learning fairies
    - Monitor packet decay status
    - Record outcomes to adjust decay
    """

    ACTOR_NAME = "TemporalPacketFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic.temporal"

    PURPOSE = "Manage consciousness-aware packet decay"
    MANTRA = "Different urgencies, different memory footprints"

    SHADOW_CLASS = TemporalPacketFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 20  # Less frequent - decay is slow
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._integration = None
        self._subscription_count = 0
        self._lessons_added = 0

    def on_boot(self) -> bool:
        """Initialize the temporal packet system."""
        super().on_boot()

        if HAS_TEMPORAL:
            try:
                packet_path = str(ROOT / "state" / "memory_packets")
                lesson_path = str(ROOT / "state" / "lessons")

                self._integration = TemporalBootIntegration(
                    packet_store_path=packet_path,
                    lesson_store_path=lesson_path,
                )

                # Run boot
                boot_result = self._integration.boot()
                print(f"[{self.ACTOR_NAME}] Temporal system booted: {boot_result.get('pending_packets', 0)} pending packets, {boot_result.get('lesson_store', 0)} lessons")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to boot temporal system: {e}")
                self._integration = None

        self._subscribe_intents()
        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for temporal commands."""
        intents = [
            ("temporal.add_lesson", self._handle_add_lesson),
            ("temporal.get_lessons_for", self._handle_get_lessons_for),
            ("temporal.get_lesson", self._handle_get_lesson),
            ("temporal.record_outcome", self._handle_record_outcome),
            ("temporal.get_decay_status", self._handle_get_decay_status),
            ("temporal.get_monitoring_data", self._handle_get_monitoring_data),
            ("temporal.record_application", self._handle_record_application),
            ("temporal.status", self._handle_status),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat: int):
        """Periodic decay scan."""
        if not self._integration:
            return

        try:
            # Scan for expired packets
            status = self._integration.monitor.scan()

            # Archive any expired
            for packet_id in status.get("expired", []):
                self._integration._archive_expired(packet_id)

            # Broadcast if many packets expiring soon
            expiring = status.get("expiring_soon", [])
            if len(expiring) > 5:
                self.post.publish("temporal.expiring_warning", {
                    "source": self.ACTOR_NAME,
                    "count": len(expiring),
                    "samples": expiring[:3],
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

    def _handle_add_lesson(self, message):
        """
        Add a lesson for learning fairies.

        Payload:
            title: str - Lesson title
            content: str - Lesson content
            category: str - Category (general, coding, consciousness, etc.)
            for_fairies: List[str] - Target fairies (["*"] for all)
            importance: float - 0.5 to 2.0 (affects persistence)
        """
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        payload = self._extract_payload(message)
        title = payload.get("title", "")
        content = payload.get("content", "")
        category = payload.get("category", "general")
        for_fairies = payload.get("for_fairies", ["*"])
        importance = payload.get("importance", 1.5)

        if not title or not content:
            return {"ok": False, "error": "Title and content required"}

        try:
            lesson_id = self._integration.add_lesson(
                title=title,
                content=content,
                category=category,
                for_fairies=for_fairies,
                importance=importance,
            )
            self._lessons_added += 1

            return {"ok": True, "lesson_id": lesson_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_lessons_for(self, message):
        """
        Get lessons applicable to a specific fairy.

        Payload:
            fairy_name: str - Name of the fairy
        """
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        payload = self._extract_payload(message)
        fairy_name = payload.get("fairy_name", "*")

        try:
            lessons = self._integration.get_lessons_for_fairy(fairy_name)
            return {"ok": True, "lessons": lessons, "count": len(lessons)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_lesson(self, message):
        """
        Get a specific lesson by ID.

        Payload:
            lesson_id: str - Lesson ID
        """
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        payload = self._extract_payload(message)
        lesson_id = payload.get("lesson_id", "")

        if not lesson_id:
            return {"ok": False, "error": "Lesson ID required"}

        try:
            lesson = self._integration.lesson_store.get_lesson(lesson_id)
            if lesson:
                return {"ok": True, "lesson": lesson.to_dict()}
            return {"ok": False, "error": "Lesson not found"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_record_outcome(self, message):
        """
        Record outcome for a packet (affects decay).

        Payload:
            packet_id: str - Packet ID
            outcome: str - "critical_success", "success", "partial", "failure", "error"
        """
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        payload = self._extract_payload(message)
        packet_id = payload.get("packet_id", "")
        outcome = payload.get("outcome", "success")

        if not packet_id:
            return {"ok": False, "error": "Packet ID required"}

        try:
            packet = self._integration.monitor.active_packets.get(packet_id)
            if packet and hasattr(packet, 'record_outcome'):
                packet.record_outcome(outcome)
                return {"ok": True, "new_ttl": packet.ttl}
            return {"ok": False, "error": "Packet not found or not temporal"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_decay_status(self, message):
        """Get current decay status across all packets."""
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        try:
            status = self._integration.monitor.scan()
            status["ok"] = True
            return status
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_monitoring_data(self, message):
        """Get data for monitoring GUI."""
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        try:
            data = self._integration.get_monitoring_data()
            data["ok"] = True
            return data
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_record_application(self, message):
        """
        Record that a lesson was applied.

        Payload:
            lesson_id: str - Lesson ID
            success: bool - Was the application successful?
        """
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        payload = self._extract_payload(message)
        lesson_id = payload.get("lesson_id", "")
        success = payload.get("success", True)

        if not lesson_id:
            return {"ok": False, "error": "Lesson ID required"}

        try:
            self._integration.lesson_store.record_application(lesson_id, success)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get overall temporal status."""
        if not self._integration:
            return {"ok": True, "integration": False}

        try:
            return {
                "ok": True,
                "integration": True,
                "lessons_count": len(self._integration.lesson_store.lessons),
                "lessons_added": self._lessons_added,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check."""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_integration": self._integration is not None,
            "lessons_added": self._lessons_added,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (lessons added: {self._lessons_added})...")
        return super().on_shutdown()
