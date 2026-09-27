#!/usr/bin/env python3
"""
Standalone WoW Event Receiver - Minimal version without MCP dependencies
"""

import json
import time
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# Motor command queue
motor_queue = []

class WoWHandler(BaseHTTPRequestHandler):
    """HTTP handler for WoW events."""

    def log_message(self, format, *args):
        # Show requests
        print(f"[REQ] {args[0]}")

    def _send_response(self, code, data=None):
        try:
            self.send_response(code)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps(data or {})
            self.wfile.write(response.encode())
        except Exception as e:
            print(f"[ERR] Failed to send response: {e}")

    def do_POST(self):
        """Handle incoming WoW events."""
        global motor_queue

        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body) if body else {}
        except Exception as e:
            print(f"[ERR] Failed to parse request: {e}")
            self._send_response(400, {"error": str(e)})
            return

        path = self.path.strip('/')
        print(f"[POST] {path}")

        # Route based on endpoint
        if path == 'wow/somatic':
            dop = data.get('dopamine', 0)
            ser = data.get('serotonin', 0)
            cor = data.get('cortisol', 0)
            oxy = data.get('oxytocin', 0)
            print(f"  Chemistry: DOP={dop} SER={ser} COR={cor} OXY={oxy}")

        elif path == 'wow/sensory':
            players = data.get('player_count', 0)
            closest = data.get('closest_player', 'none')
            print(f"  Sensory: {players} players, closest: {closest}")

        elif path == 'wow/consciousness':
            state = data.get('state', 'unknown')
            awareness = data.get('awareness', 'unknown')
            print(f"  Consciousness: state={state}, awareness={awareness}")

        elif path == 'wow/chat':
            direction = data.get('dir', '')
            speaker = data.get('from', '')
            message = data.get('msg', '')
            print(f"  Chat {direction}: {speaker}: {message}")

        elif path == 'wow/event':
            event_type = data.get('type', 'unknown')
            event_data = data.get('data', '')
            print(f"  Event: {event_type} - {event_data}")

        else:
            print(f"  Unknown endpoint: {path}")
            self._send_response(404, {"error": "Unknown endpoint"})
            return

        self._send_response(200, {"status": "ok"})

    def do_GET(self):
        """Handle motor command polling."""
        global motor_queue

        if self.path == '/wow/motor_poll':
            if motor_queue:
                cmd = motor_queue.pop(0)
                self._send_response(200, cmd)
            else:
                self._send_response(200, {})
        else:
            self._send_response(404, {"error": "Unknown endpoint"})


def main():
    port = 8766

    print("\n" + "="*60)
    print("WoW Event Receiver (Standalone)")
    print("="*60)
    print(f"Listening on 0.0.0.0:{port}")
    print("Waiting for events from Alienware WoW relay...")
    print("="*60 + "\n")

    server = HTTPServer(('0.0.0.0', port), WoWHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[WoW-Receiver] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
