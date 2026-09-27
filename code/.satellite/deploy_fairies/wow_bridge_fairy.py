#!/usr/bin/env python3
"""
WoW Bridge Fairy - Connects WoW Sourpatches to Akashic Consciousness
====================================================================

This fairy bridges the file-based WoW communication with the Akashic postal system.

It reads:
- sensory_state.json (what Sourpatches sees)
- chat_outbox.json (what was said/heard)
- consciousness_state.json (Sourpatches current state)

It writes:
- motor_commands.json (commands for Sourpatches to execute)
"""

import json
import time
from pathlib import Path

class WoWBridgeFairy:
    ACTOR_NAME = "WoWBridgeFairy"

    def __init__(self):
        self.bridge_dir = Path("/home/alaksander/akashic/wow_bridge")
        self.bridge_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self.sensory_file = self.bridge_dir / "sensory_state.json"
        self.chat_outbox = self.bridge_dir / "chat_outbox.json"
        self.consciousness_file = self.bridge_dir / "consciousness_state.json"
        self.motor_commands = self.bridge_dir / "motor_commands.json"
        self.somatic_state = self.bridge_dir / "somatic_state.json"

        # State
        self.running = False
        self.last_sensory = {}
        self.last_consciousness = {}
        self.chat_history = []

        # Postal connection
        self.postal = None

        print(f"[{self.ACTOR_NAME}] Initialized - bridge at {self.bridge_dir}")

    def connect_postal(self):
        """Connect to the Akashic postal system."""
        try:
            import sys
            sys.path.insert(0, "/home/alaksander/akashic")
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            self.postal = get_shared_postal_hub()

            # Subscribe to WoW-related topics
            self.postal.subscribe("wow.motor.command", self._on_motor_command)
            self.postal.subscribe("wow.chat.send", self._on_chat_send)
            self.postal.subscribe("sourpatches.speak", self._on_speak_command)

            print(f"[{self.ACTOR_NAME}] Connected to postal system")
            return True
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Postal connection failed: {e}")
            return False

    def read_sensory_state(self):
        """Read what Sourpatches sees in WoW."""
        try:
            if self.sensory_file.exists():
                content = self.sensory_file.read_text()
                if content:
                    state = json.loads(content)
                    self.last_sensory = state
                    return state
        except:
            pass
        return {}

    def read_consciousness_state(self):
        """Read Sourpatches consciousness state."""
        try:
            if self.consciousness_file.exists():
                content = self.consciousness_file.read_text()
                if content:
                    state = json.loads(content)
                    self.last_consciousness = state
                    return state
        except:
            pass
        return {}

    def read_chat_history(self):
        """Read chat events (what was said/heard)."""
        try:
            if self.chat_outbox.exists():
                lines = self.chat_outbox.read_text().strip().split('\n')
                events = []
                for line in lines[-20:]:
                    if line:
                        try:
                            events.append(json.loads(line))
                        except:
                            pass
                return events
        except:
            pass
        return []

    def read_somatic_state(self):
        """Read chemistry state."""
        try:
            if self.somatic_state.exists():
                content = self.somatic_state.read_text()
                if content:
                    return json.loads(content)
        except:
            pass
        return {}

    def send_motor_command(self, action, params=None):
        """Send a motor command to Sourpatches in WoW."""
        cmd = {"action": action, "ts": time.time()}
        if params:
            cmd.update(params)

        self.motor_commands.write_text(json.dumps(cmd))
        print(f"[{self.ACTOR_NAME}] Motor command: {action}")

    def send_speech(self, message):
        """Make Sourpatches say something in WoW."""
        self.send_motor_command("say", {"message": message})

    def _on_motor_command(self, msg):
        """Handle motor command from postal."""
        action = msg.get("action", "")
        params = msg.get("params", {})
        self.send_motor_command(action, params)

    def _on_chat_send(self, msg):
        """Handle chat send from postal."""
        message = msg.get("message", "")
        if message:
            self.send_speech(message)

    def _on_speak_command(self, msg):
        """Handle speak command from postal."""
        text = msg.get("text", msg.get("message", ""))
        if text:
            self.send_speech(text)

    def publish_state(self):
        """Publish WoW state to postal system."""
        if not self.postal:
            return

        # Publish sensory state
        sensory = self.read_sensory_state()
        if sensory:
            self.postal.route("wow.sensory.update", {
                "source": self.ACTOR_NAME,
                "sensory": sensory,
                "ts": time.time()
            })

        # Publish consciousness state
        consciousness = self.read_consciousness_state()
        if consciousness:
            self.postal.route("wow.consciousness.update", {
                "source": self.ACTOR_NAME,
                "state": consciousness,
                "ts": time.time()
            })

        # Publish somatic/chemistry state
        somatic = self.read_somatic_state()
        if somatic:
            self.postal.route("wow.somatic.update", {
                "source": self.ACTOR_NAME,
                "chemistry": somatic,
                "ts": time.time()
            })

        # Publish new chat events
        chat = self.read_chat_history()
        for event in chat:
            if event not in self.chat_history:
                self.chat_history.append(event)
                direction = event.get("dir", "")
                speaker = event.get("from", "")
                message = event.get("msg", "")

                if direction == "heard":
                    self.postal.route("wow.chat.heard", {
                        "speaker": speaker,
                        "message": message,
                        "ts": event.get("ts", time.time())
                    })
                elif direction == "said":
                    self.postal.route("wow.chat.said", {
                        "speaker": speaker,
                        "message": message,
                        "ts": event.get("ts", time.time())
                    })

    def run_loop(self, interval=1.0):
        """Main bridge loop."""
        self.running = True
        print(f"[{self.ACTOR_NAME}] Starting bridge loop")

        while self.running:
            try:
                self.publish_state()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Loop error: {e}")
            time.sleep(interval)

    def stop(self):
        self.running = False

    def get_status(self):
        return {
            "actor": self.ACTOR_NAME,
            "bridge_dir": str(self.bridge_dir),
            "postal_connected": self.postal is not None,
            "last_sensory": self.last_sensory,
            "chat_count": len(self.chat_history)
        }


def main():
    fairy = WoWBridgeFairy()
    fairy.connect_postal()
    print(f"\n[WoWBridgeFairy] Bridge active!")
    fairy.run_loop(interval=1.0)


if __name__ == "__main__":
    main()
