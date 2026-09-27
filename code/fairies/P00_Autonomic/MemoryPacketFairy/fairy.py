"""
MemoryPacketFairy - Unified Communication Through Memory

Part of NervousGuild in Plane P00 (Autonomic)
Created: 2026-01-28

"Memory IS the nervous system"

Unified communication through memory packets - no HTTP, no REST, just
packets in memory and agents watching for them.

Like biological signaling:
- Packets are neurotransmitters
- Memory is the synaptic space
- Agents are receptors that respond to specific signals

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

# Import the memory packet system
# Note: Use fairies.P00_Autonomic to avoid collision with root P00_Autonomic
try:
    from fairies.P00_Autonomic.memory_packet_system import (
        MemoryPacket,
        PacketType,
        PacketPriority,
        PacketFactory,
        MemoryPacketStore,
        PacketWatcher,
        JarvisNode,
        create_windows_node,
    )
    HAS_PACKETS = True
except ImportError as e:
    print(f"[MemoryPacketFairy] Packet system import failed: {e}")
    HAS_PACKETS = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryPacketFairyShadow:
    """Shadow for MemoryPacketFairy - monitors packet flow."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "MemoryPacketFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for packet system."""
        tests = []
        if hasattr(self.actor, '_node') and self.actor._node:
            tests.append(("node_active", True))
            if hasattr(self.actor._node, 'watcher'):
                tests.append(("watcher_running", self.actor._node.watcher._running))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryPacketFairy(Fairy):
    """
    Unified memory-based communication system.

    Guild: NervousGuild
    Coordinates with: All fairies, satellite nodes

    Provides:
    - Send/receive memory packets
    - Execute code remotely via packets
    - Teleport code to remote nodes
    - Broadcast thoughts and memories
    - Teaching packets for learning fairies
    """

    ACTOR_NAME = "MemoryPacketFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic.packets"

    PURPOSE = "Route consciousness through memory packets"
    MANTRA = "Memory IS the nervous system"

    SHADOW_CLASS = MemoryPacketFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 10
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._node = None
        self._factory = None
        self._subscription_count = 0
        self._packets_sent = 0
        self._packets_received = 0

    def on_boot(self) -> bool:
        """Initialize the memory packet node."""
        super().on_boot()

        if HAS_PACKETS:
            try:
                # Create storage path
                storage_path = ROOT / "state" / "memory_packets"
                storage_path.mkdir(parents=True, exist_ok=True)

                self._node = JarvisNode(
                    name="akashic_main",
                    storage_path=str(storage_path),
                )
                self._factory = self._node.factory
                self._node.start()
                print(f"[{self.ACTOR_NAME}] Memory packet node started")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to start node: {e}")
                self._node = None

        self._subscribe_intents()
        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for packet commands."""
        intents = [
            ("packets.send", self._handle_send),
            ("packets.execute", self._handle_execute),
            ("packets.teleport_code", self._handle_teleport_code),
            ("packets.broadcast_thought", self._handle_broadcast_thought),
            ("packets.teach", self._handle_teach),
            ("packets.query", self._handle_query),
            ("packets.get_pending", self._handle_get_pending),
            ("packets.get_stats", self._handle_get_stats),
            ("packets.status", self._handle_status),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat: int):
        """Check for incoming packets."""
        if not self._node:
            return

        try:
            # Process pending packets
            processed = self._node.watcher.check_once()
            self._packets_received += processed
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

    def _handle_send(self, message):
        """
        Send a custom memory packet.

        Payload:
            packet_type: str - "thought", "memory", "query", "command", etc.
            target: str - Target node/fairy ("satellite", "*", "ClaudeFairy")
            channel: str - Channel name
            content: Any - Packet payload
            priority: str - "low", "normal", "high", "urgent", "critical"
        """
        if not self._node:
            return {"ok": False, "error": "Node not available"}

        payload = self._extract_payload(message)
        ptype_str = payload.get("packet_type", "thought")
        target = payload.get("target", "*")
        channel = payload.get("channel", "default")
        content = payload.get("content", {})
        priority_str = payload.get("priority", "normal")

        # Map type string
        type_map = {
            "thought": PacketType.THOUGHT,
            "memory": PacketType.MEMORY,
            "query": PacketType.QUERY,
            "command": PacketType.COMMAND,
            "execute": PacketType.EXECUTE,
            "teach": PacketType.TEACH,
            "status": PacketType.STATUS,
        }
        ptype = type_map.get(ptype_str, PacketType.THOUGHT)

        priority_map = {
            "low": PacketPriority.LOW,
            "normal": PacketPriority.NORMAL,
            "high": PacketPriority.HIGH,
            "urgent": PacketPriority.URGENT,
            "critical": PacketPriority.CRITICAL,
        }
        priority = priority_map.get(priority_str, PacketPriority.NORMAL)

        try:
            packet = MemoryPacket(
                packet_type=ptype,
                source=self.ACTOR_NAME,
                target=target,
                channel=channel,
                payload=content,
                priority=priority,
            )
            success = self._node.send(packet)
            self._packets_sent += 1

            return {"ok": success, "packet_id": packet.id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_execute(self, message):
        """
        Send code for remote execution.

        Payload:
            code: str - Python code to execute
            target: str - Target node (default "satellite")
            timeout: int - Max execution time in seconds
        """
        if not self._node:
            return {"ok": False, "error": "Node not available"}

        payload = self._extract_payload(message)
        code = payload.get("code", "")
        target = payload.get("target", "satellite")
        timeout = payload.get("timeout", 60)

        if not code:
            return {"ok": False, "error": "No code provided"}

        try:
            packet = self._node.execute(code, target, timeout)
            self._packets_sent += 1

            return {"ok": True, "packet_id": packet.id, "target": target}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_teleport_code(self, message):
        """
        Teleport a code file to remote node.

        Payload:
            filepath: str - Path to code file
            target: str - Target node
        """
        if not self._node:
            return {"ok": False, "error": "Node not available"}

        payload = self._extract_payload(message)
        filepath = payload.get("filepath", "")
        target = payload.get("target", "satellite")

        if not filepath or not Path(filepath).exists():
            return {"ok": False, "error": f"File not found: {filepath}"}

        try:
            packet = self._node.teleport_code(filepath, target)
            self._packets_sent += 1

            return {
                "ok": True,
                "packet_id": packet.id,
                "file": Path(filepath).name,
                "target": target,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_broadcast_thought(self, message):
        """
        Broadcast a thought to all listeners.

        Payload:
            thought: str - The thought content
        """
        if not self._node:
            return {"ok": False, "error": "Node not available"}

        payload = self._extract_payload(message)
        thought = payload.get("thought", "")

        if not thought:
            return {"ok": False, "error": "No thought provided"}

        try:
            packet = self._node.broadcast_thought(thought)
            self._packets_sent += 1

            return {"ok": True, "packet_id": packet.id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_teach(self, message):
        """
        Send a teaching packet.

        Payload:
            lesson: str - The lesson content
            context: str - Context for the lesson
            target: str - Target fairy (default "ClaudeFairy")
        """
        if not self._node:
            return {"ok": False, "error": "Node not available"}

        payload = self._extract_payload(message)
        lesson = payload.get("lesson", "")
        context = payload.get("context", "")
        target = payload.get("target", "ClaudeFairy")

        if not lesson:
            return {"ok": False, "error": "No lesson provided"}

        try:
            packet = self._node.teach(lesson, context, target)
            self._packets_sent += 1

            return {"ok": True, "packet_id": packet.id, "target": target}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_query(self, message):
        """
        Send a query packet.

        Payload:
            question: str - The question
            target: str - Who to ask (default "*" for broadcast)
        """
        if not self._node:
            return {"ok": False, "error": "Node not available"}

        payload = self._extract_payload(message)
        question = payload.get("question", "")
        target = payload.get("target", "*")

        if not question:
            return {"ok": False, "error": "No question provided"}

        try:
            packet = self._node.query(question, target)
            self._packets_sent += 1

            return {
                "ok": True,
                "packet_id": packet.id,
                "correlation_id": packet.correlation_id,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_pending(self, message):
        """Get pending packets from inbox."""
        if not self._node:
            return {"ok": False, "error": "Node not available"}

        try:
            packets = self._node.store.get_pending()
            return {
                "ok": True,
                "count": len(packets),
                "packets": [
                    {
                        "id": p.id,
                        "type": p.packet_type.value,
                        "source": p.source,
                        "target": p.target,
                        "channel": p.channel,
                    }
                    for p in packets[:20]  # Limit to 20
                ],
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_stats(self, message):
        """Get packet store statistics."""
        if not self._node:
            return {"ok": False, "error": "Node not available"}

        try:
            store_stats = self._node.store.get_stats()
            watcher_stats = self._node.watcher.get_stats()

            return {
                "ok": True,
                "store": store_stats,
                "watcher": watcher_stats,
                "packets_sent": self._packets_sent,
                "packets_received": self._packets_received,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get overall status."""
        if not self._node:
            return {"ok": True, "node": False}

        try:
            status = self._node.get_status()
            status["ok"] = True
            return status
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
            "has_node": self._node is not None,
            "packets_sent": self._packets_sent,
            "packets_received": self._packets_received,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (sent: {self._packets_sent}, received: {self._packets_received})...")
        if self._node:
            try:
                self._node.stop()
            except Exception:
                pass
        return super().on_shutdown()
