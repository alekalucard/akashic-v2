#!/usr/bin/env python3
"""
WoW-to-Windows Relay - Bridges WoW server to Windows Akashic system
=====================================================================

This script runs on Alienware and:
1. Reads WoW bridge files (written by Eluna Lua)
2. Forwards events via HTTP to the Windows Akashic MCP server
3. Receives motor commands from Windows and writes them for Lua to read

Run this on Alienware: python3 wow_windows_relay.py
"""

import json
import time
import requests
from pathlib import Path
from threading import Thread
import sys

# Configuration
WINDOWS_HOST = "192.168.1.6"  # Windows machine IP
MCP_PORT = 8766  # WoW receiver port (separate from MCP SSE 8765)

# Path where Lua writes files (mapped from Docker logs volume)
BRIDGE_DIR = Path("/home/alaksander/azerothcore-wotlk/env/dist/logs/wow_bridge")

# File paths
SOMATIC_STATE = BRIDGE_DIR / "somatic_state.json"
SENSORY_STATE = BRIDGE_DIR / "sensory_state.json"
CHAT_OUTBOX = BRIDGE_DIR / "chat_outbox.json"
CONSCIOUSNESS_STATE = BRIDGE_DIR / "consciousness_state.json"
WOW_EVENTS = BRIDGE_DIR / "wow_events.json"
MOTOR_COMMANDS = BRIDGE_DIR / "motor_commands.json"

class WoWWindowsRelay:
    def __init__(self):
        self.running = False
        self.last_somatic_ts = 0
        self.last_sensory_ts = 0
        self.last_consciousness_ts = 0
        self.chat_offset = 0
        self.events_offset = 0

        # Ensure bridge directory exists
        BRIDGE_DIR.mkdir(parents=True, exist_ok=True)

        print(f"[WoW-Relay] Initialized", flush=True)
        print(f"[WoW-Relay] Bridge dir: {BRIDGE_DIR}", flush=True)
        print(f"[WoW-Relay] Windows target: {WINDOWS_HOST}:{MCP_PORT}", flush=True)

    def read_json_file(self, filepath):
        """Read a JSON file safely."""
        try:
            if filepath.exists():
                content = filepath.read_text().strip()
                if content:
                    return json.loads(content)
        except Exception as e:
            pass
        return None

    def read_lines_file(self, filepath, offset=0):
        """Read new lines from a file (for chat/events logs)."""
        try:
            if filepath.exists():
                lines = filepath.read_text().strip().split('\n')
                new_lines = lines[offset:]
                return new_lines, len(lines)
        except:
            pass
        return [], offset

    def send_to_windows(self, endpoint, data):
        """Send data to Windows Akashic MCP."""
        try:
            url = f"http://{WINDOWS_HOST}:{MCP_PORT}/wow/{endpoint}"
            response = requests.post(url, json=data, timeout=2)
            if response.status_code == 200:
                return True
            else:
                print(f"[WoW-Relay] HTTP {response.status_code} from {endpoint}")
        except requests.exceptions.ConnectionError:
            # Windows might not have the endpoint yet, just log once
            pass
        except Exception as e:
            print(f"[WoW-Relay] Error sending to {endpoint}: {e}")
        return False

    def forward_somatic(self):
        """Forward somatic/chemistry state."""
        data = self.read_json_file(SOMATIC_STATE)
        if data and data.get('ts', 0) > self.last_somatic_ts:
            self.last_somatic_ts = data['ts']
            if self.send_to_windows('somatic', data):
                print(f"[WoW-Relay] Somatic sent: DOP={data.get('dopamine',0)} SER={data.get('serotonin',0)}", flush=True)

    def forward_sensory(self):
        """Forward sensory state (what Sourpatches sees)."""
        data = self.read_json_file(SENSORY_STATE)
        if data and data.get('ts', 0) > self.last_sensory_ts:
            self.last_sensory_ts = data['ts']
            self.send_to_windows('sensory', data)
            players = data.get('player_count', 0)
            if players > 0:
                print(f"[WoW-Relay] Sensory: {players} players nearby")

    def forward_consciousness(self):
        """Forward consciousness state."""
        data = self.read_json_file(CONSCIOUSNESS_STATE)
        if data and data.get('ts', 0) > self.last_consciousness_ts:
            self.last_consciousness_ts = data['ts']
            self.send_to_windows('consciousness', data)

    def forward_chat(self):
        """Forward new chat events."""
        lines, new_offset = self.read_lines_file(CHAT_OUTBOX, self.chat_offset)
        if lines:
            for line in lines:
                if line:
                    try:
                        event = json.loads(line)
                        self.send_to_windows('chat', event)
                        direction = event.get('dir', '')
                        speaker = event.get('from', '')
                        msg = event.get('msg', '')[:50]
                        print(f"[WoW-Relay] Chat {direction}: {speaker}: {msg}")
                    except:
                        pass
            self.chat_offset = new_offset

    def forward_events(self):
        """Forward WoW gameplay events."""
        lines, new_offset = self.read_lines_file(WOW_EVENTS, self.events_offset)
        if lines:
            for line in lines:
                if line:
                    try:
                        event = json.loads(line)
                        self.send_to_windows('event', event)
                    except:
                        pass
            self.events_offset = new_offset

    def check_motor_commands(self):
        """Check Windows for motor commands to send to WoW."""
        try:
            url = f"http://{WINDOWS_HOST}:{MCP_PORT}/wow/motor_poll"
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                commands = response.json()
                if commands:
                    MOTOR_COMMANDS.write_text(json.dumps(commands))
                    print(f"[WoW-Relay] Motor command: {commands.get('action','?')}")
        except:
            pass

    def run(self, interval=1.0):
        """Main relay loop."""
        self.running = True
        print(f"[WoW-Relay] Starting relay loop (interval: {interval}s)")

        while self.running:
            try:
                # Forward all state types
                self.forward_somatic()
                self.forward_sensory()
                self.forward_consciousness()
                self.forward_chat()
                self.forward_events()

                # Check for motor commands from Windows
                self.check_motor_commands()

            except Exception as e:
                print(f"[WoW-Relay] Loop error: {e}")

            time.sleep(interval)

    def stop(self):
        self.running = False


def main():
    relay = WoWWindowsRelay()

    print("\n" + "="*60)
    print("WoW-to-Windows Relay Active")
    print("="*60)
    print("Forwarding WoW events to Windows Akashic system")
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")

    try:
        relay.run(interval=0.5)
    except KeyboardInterrupt:
        print("\n[WoW-Relay] Shutting down...")
        relay.stop()


if __name__ == "__main__":
    main()
