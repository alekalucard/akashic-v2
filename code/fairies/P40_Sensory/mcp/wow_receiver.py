#!/usr/bin/env python3
"""
WoW Event Receiver - Receives WoW events from Alienware relay
================================================================

Listens for HTTP POST requests from the WoW relay on Alienware
and routes them to the Akashic postal system.

Run this on Windows: python wow_receiver.py
"""

import json
import time
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# Add project paths - IMPORTANT: Root must be searched BEFORE fairies
# because P00_Autonomic/nervous_system is at root, not fairies
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "fairies"))  # Searched LAST
sys.path.insert(0, str(PROJECT_ROOT))               # Searched FIRST

# Try to connect to postal
postal = None
try:
    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
    postal = get_shared_postal_hub()
    print("[WoW-Receiver] Connected to Akashic postal system")
except Exception as e:
    print(f"[WoW-Receiver] Postal connection failed: {e}")
    print("[WoW-Receiver] Running in standalone mode (events will be printed)")

# Motor command queue (for polling from relay)
motor_queue = []

class WoWHandler(BaseHTTPRequestHandler):
    """HTTP handler for WoW events."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def _send_response(self, code, data=None):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        if data:
            self.wfile.write(json.dumps(data).encode())

    def do_POST(self):
        """Handle incoming WoW events."""
        global postal, motor_queue

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body)
        except:
            self._send_response(400, {"error": "Invalid JSON"})
            return

        path = self.path.strip('/')

        # Route based on endpoint
        if path == 'wow/somatic':
            # Chemistry state update
            print(f"[WoW] Somatic: DOP={data.get('dopamine',0)} SER={data.get('serotonin',0)} COR={data.get('cortisol',0)} OXY={data.get('oxytocin',0)}")
            if postal:
                postal.route("wow.somatic.update", {
                    "source": "WoW-Receiver",
                    "chemistry": data,
                    "ts": time.time()
                })

        elif path == 'wow/sensory':
            # What Sourpatches sees
            players = data.get('player_count', 0)
            closest = data.get('closest_player', 'none')
            if players > 0:
                print(f"[WoW] Sensory: {players} players, closest: {closest}")
            if postal:
                postal.route("wow.sensory.update", {
                    "source": "WoW-Receiver",
                    "sensory": data,
                    "ts": time.time()
                })

        elif path == 'wow/consciousness':
            # Sourpatches state
            state = data.get('state', 'unknown')
            awareness = data.get('awareness', 'unknown')
            print(f"[WoW] Consciousness: state={state}, awareness={awareness}")
            if postal:
                postal.route("wow.consciousness.update", {
                    "source": "WoW-Receiver",
                    "state": data,
                    "ts": time.time()
                })

        elif path == 'wow/chat':
            # Chat events
            direction = data.get('dir', '')
            speaker = data.get('from', '')
            message = data.get('msg', '')
            print(f"[WoW] Chat {direction}: {speaker}: {message}")

            if postal:
                if direction == 'heard':
                    postal.route("wow.chat.heard", {
                        "speaker": speaker,
                        "message": message,
                        "ts": data.get('ts', time.time())
                    })
                    # Also trigger Sourpatches to respond
                    postal.route("sourpatches.stimulus", {
                        "type": "heard_speech",
                        "speaker": speaker,
                        "content": message
                    })
                elif direction == 'said':
                    postal.route("wow.chat.said", {
                        "speaker": speaker,
                        "message": message,
                        "ts": data.get('ts', time.time())
                    })

        elif path == 'wow/event':
            # Gameplay events
            event_type = data.get('type', 'unknown')
            event_data = data.get('data', '')
            print(f"[WoW] Event: {event_type} - {event_data}")
            if postal:
                postal.route("wow.event", {
                    "type": event_type,
                    "data": event_data,
                    "ts": data.get('ts', time.time())
                })

        else:
            self._send_response(404, {"error": "Unknown endpoint"})
            return

        self._send_response(200, {"status": "ok"})

    def do_GET(self):
        """Handle motor command polling."""
        global motor_queue

        if self.path == '/wow/motor_poll':
            # Return queued motor commands
            if motor_queue:
                cmd = motor_queue.pop(0)
                self._send_response(200, cmd)
            else:
                self._send_response(200, {})
        else:
            self._send_response(404, {"error": "Unknown endpoint"})


def add_motor_command(action, params=None):
    """Queue a motor command for Sourpatches."""
    global motor_queue
    cmd = {"action": action, "ts": time.time()}
    if params:
        cmd.update(params)
    motor_queue.append(cmd)
    print(f"[WoW-Receiver] Queued motor: {action}")


def setup_postal_listeners():
    """Subscribe to postal topics that should send commands to WoW."""
    global postal

    if not postal:
        return

    def on_sourpatches_speak(msg):
        """When Sourpatches wants to speak, queue it for WoW."""
        text = msg.get('text', msg.get('message', ''))
        if text:
            add_motor_command('say', {'message': text})

    def on_motor_command(msg):
        """Generic motor command from postal."""
        action = msg.get('action', '')
        if action:
            add_motor_command(action, msg.get('params', {}))

    postal.subscribe("sourpatches.speak", on_sourpatches_speak)
    postal.subscribe("wow.motor.command", on_motor_command)
    print("[WoW-Receiver] Postal listeners set up")


def main():
    port = 8766  # Separate from MCP SSE port (8765)

    print("\n" + "="*60)
    print("WoW Event Receiver")
    print("="*60)
    print(f"Listening on port {port}")
    print("Receiving events from Alienware WoW relay")
    print("="*60 + "\n")

    setup_postal_listeners()

    server = HTTPServer(('0.0.0.0', port), WoWHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[WoW-Receiver] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
