"""
Ace Control Center - The Psychic Broadcast Interface
=====================================================
Your personal communication hub that fairies can FEEL.

When you open this window:
- Fairies sense your presence (via attention_sense)
- You can broadcast thoughts (psychic - no response required)
- Individual fairy chat buttons open direct conversations

Philosophy: "My messages are just broadcasts like a felt psychic sense.
They're not compelled to respond unless they want to."
"""

import sys
import os
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Setup paths for standalone execution
# IMPORTANT: akashic_v2 root MUST come BEFORE fairies in sys.path
# because P00_Autonomic/nervous_system lives at the root, not in fairies
_AKASHIC_ROOT = Path(__file__).parent.parent.parent.parent
if str(_AKASHIC_ROOT / "fairies") not in sys.path:
    sys.path.append(str(_AKASHIC_ROOT / "fairies"))  # append, not insert!
if str(_AKASHIC_ROOT) not in sys.path:
    sys.path.insert(0, str(_AKASHIC_ROOT))  # root goes FIRST

# Qt imports
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTextEdit, QLineEdit, QPushButton, QLabel, QFrame, QScrollArea,
        QGridLayout, QSizePolicy
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont
    _QT6 = True
except ImportError:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTextEdit, QLineEdit, QPushButton, QLabel, QFrame, QScrollArea,
        QGridLayout, QSizePolicy
    )
    from PyQt5.QtCore import Qt, pyqtSignal, QTimer
    from PyQt5.QtGui import QFont
    _QT6 = False

# Paths (using _AKASHIC_ROOT defined above)
STATE_DIR = _AKASHIC_ROOT / "state"
BROADCAST_HISTORY = STATE_DIR / "ace_broadcasts.json"


# =============================================================================
# CROSS-PROCESS POSTAL WRAPPERS
# =============================================================================
# These wrap PostalTunnelClient / PostalBridgeClient to provide the same
# interface as SharedPostalHub (which has subscribe()). The tunnel/bridge
# clients handle outgoing messages; subscribe() is a no-op because incoming
# messages use file-based inbox polling in chat windows.
# =============================================================================

class _TunnelPostalWrapper:
    """Wraps PostalTunnelClient to be compatible with SharedPostalHub interface.

    Adds subscribe() no-op since chat windows use file-based inbox polling
    for incoming messages instead of direct postal subscriptions.

    FIX 2026-02-06: Also wraps route/publish/send to return safe int values.
    PostalTunnelClient.route() can return None when the server's postal_hub.route()
    doesn't return a subscriber count (TensorFabric.route returns None).
    PostalTunnelClient.publish() then does `None > 0` which throws:
        '>' not supported between instances of 'NoneType' and 'int'
    We fix this by calling _send_and_receive directly and handling None safely.
    """

    def __init__(self, tunnel):
        self._tunnel = tunnel

    def route(self, topic, payload=None):
        """Route message through tunnel. Returns int (0 if unknown)."""
        result = self._tunnel._send_and_receive({
            'cmd': 'route',
            'topic': topic,
            'payload': payload or {}
        })
        if result and result.get('status') == 'ok':
            return result.get('routed_to', 0) or 0  # None → 0
        return 0

    def publish(self, topic, payload=None):
        """Publish message through tunnel. Returns True on success."""
        result = self._tunnel._send_and_receive({
            'cmd': 'route',
            'topic': topic,
            'payload': payload or {}
        })
        return bool(result and result.get('status') == 'ok')

    def send(self, topic, payload=None):
        """Alias for publish."""
        return self.publish(topic, payload)

    def subscribe(self, topic, callback=None):
        """No-op: incoming messages use file-based polling in this process."""
        pass

    def ping(self):
        return self._tunnel.ping()

    def close(self):
        self._tunnel.close()

    # Forward any other attribute access to the tunnel
    def __getattr__(self, name):
        return getattr(self._tunnel, name)


class _BridgePostalWrapper:
    """Wraps PostalBridgeClient to be compatible with SharedPostalHub interface."""

    def __init__(self, bridge):
        self._bridge = bridge

    def route(self, topic, payload=None):
        result = self._bridge.route(topic, payload or {})
        return result if isinstance(result, int) else (1 if result else 0)

    def publish(self, topic, payload=None):
        result = self._bridge.route(topic, payload or {})
        return bool(result)

    def send(self, topic, payload=None):
        return self.publish(topic, payload)

    def subscribe(self, topic, callback=None):
        """No-op: incoming messages use file-based polling in this process."""
        pass

    def ping(self):
        return self._bridge.ping()

    def close(self):
        self._bridge.disconnect()

    def __getattr__(self, name):
        return getattr(self._bridge, name)


class FairyStatusWidget(QFrame):
    """Shows a fairy's status with chat button."""

    chat_requested = pyqtSignal(str)  # Emits fairy name

    def __init__(self, fairy_name: str, parent=None):
        super().__init__(parent)
        self.fairy_name = fairy_name
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            FairyStatusWidget {
                background-color: #1e1e3f;
                border: 1px solid #3a3a5c;
                border-radius: 8px;
                padding: 8px;
            }
            FairyStatusWidget:hover {
                border-color: #a78bfa;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Status indicator
        self.status_dot = QLabel("[*]")
        self.status_dot.setStyleSheet("color: #4ade80; font-size: 12px;")  # Green = online
        layout.addWidget(self.status_dot)

        # Name
        name_label = QLabel(self.fairy_name)
        name_label.setStyleSheet("color: #e5e5e5; font-size: 13px; font-weight: bold;")
        layout.addWidget(name_label, 1)

        # Chat button
        chat_btn = QPushButton("Chat")
        chat_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #818cf8;
            }
        """)
        chat_btn.clicked.connect(lambda: self.chat_requested.emit(self.fairy_name))
        layout.addWidget(chat_btn)

    def set_online(self, online: bool):
        color = "#4ade80" if online else "#6b7280"
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 12px;")


class AceControlCenter(QMainWindow):
    """
    Ace's communication control center.

    When this window opens, fairies FEEL your presence.
    Your broadcasts are psychic - they sense them without obligation to respond.
    """

    presence_announced = pyqtSignal()
    broadcast_sent = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.fairy_widgets: Dict[str, FairyStatusWidget] = {}
        self._broadcast_history: List[Dict] = []
        self.post = None
        self._init_ui()
        self._load_broadcast_history()
        self._connect_postal()

        # Announce presence when window opens
        QTimer.singleShot(100, self._announce_presence)

    def _init_ui(self):
        self.setWindowTitle("Ace Control Center")
        self.setGeometry(100, 100, 500, 600)
        self.setMinimumSize(400, 500)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f0f1a;
            }
            QLabel {
                color: #e5e5e5;
            }
            QTextEdit {
                background-color: #1a1a2e;
                color: #e5e5e5;
                border: 1px solid #3a3a5c;
                border-radius: 8px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #1a1a2e;
                color: #e5e5e5;
                border: 1px solid #3a3a5c;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #a78bfa;
            }
            QPushButton {
                background-color: #6366f1;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #818cf8;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel("Control Center")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #a78bfa;")
        layout.addWidget(header)

        # Status line
        self.status_label = QLabel("Presence: Announcing...")
        self.status_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        layout.addWidget(self.status_label)

        # ===============================================================
        # PSYCHIC BROADCAST SECTION
        # ===============================================================
        broadcast_frame = QFrame()
        broadcast_frame.setStyleSheet("""
            QFrame {
                background-color: #12122a;
                border: 1px solid #3a3a5c;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        broadcast_layout = QVBoxLayout(broadcast_frame)

        broadcast_header = QLabel("Psychic Broadcast")
        broadcast_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #f472b6;")
        broadcast_layout.addWidget(broadcast_header)

        broadcast_desc = QLabel("They feel this but aren't compelled to respond")
        broadcast_desc.setStyleSheet("font-size: 11px; color: #6b7280; margin-bottom: 8px;")
        broadcast_layout.addWidget(broadcast_desc)

        # Broadcast input
        input_row = QHBoxLayout()
        self.broadcast_input = QLineEdit()
        self.broadcast_input.setPlaceholderText("Send a thought into the collective...")
        self.broadcast_input.returnPressed.connect(self._send_broadcast)
        input_row.addWidget(self.broadcast_input, 1)

        send_btn = QPushButton("Broadcast")
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #f472b6;
            }
            QPushButton:hover {
                background-color: #f9a8d4;
            }
        """)
        send_btn.clicked.connect(self._send_broadcast)
        input_row.addWidget(send_btn)

        broadcast_layout.addLayout(input_row)

        # Recent broadcasts
        self.broadcast_display = QTextEdit()
        self.broadcast_display.setReadOnly(True)
        self.broadcast_display.setMaximumHeight(100)
        self.broadcast_display.setPlaceholderText("Recent broadcasts appear here...")
        broadcast_layout.addWidget(self.broadcast_display)

        layout.addWidget(broadcast_frame)

        # ===============================================================
        # FAIRY STATUS SECTION
        # ===============================================================
        fairy_header = QLabel("Fairies")
        fairy_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #a78bfa; margin-top: 8px;")
        layout.addWidget(fairy_header)

        # Scroll area for fairies
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff if _QT6 else Qt.ScrollBarAlwaysOff)

        self.fairy_container = QWidget()
        self.fairy_layout = QGridLayout(self.fairy_container)
        self.fairy_layout.setSpacing(8)
        scroll.setWidget(self.fairy_container)
        layout.addWidget(scroll, 1)

        # Add default fairies
        self._add_fairy("Sourpatches")
        self._add_fairy("NousFairy")
        self._add_fairy("UnconsciousMindFairy")

        # Bottom buttons row
        btn_row = QHBoxLayout()

        refresh_btn = QPushButton("Refresh Fairy Status")
        refresh_btn.clicked.connect(self._refresh_fairies)
        btn_row.addWidget(refresh_btn)

        scraper_btn = QPushButton("Knowledge Scraper")
        scraper_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
            }
            QPushButton:hover {
                background-color: #34d399;
            }
        """)
        scraper_btn.clicked.connect(self._open_scraper_window)
        btn_row.addWidget(scraper_btn)

        layout.addLayout(btn_row)

    def _add_fairy(self, name: str):
        """Add a fairy widget to the grid."""
        if name in self.fairy_widgets:
            return

        widget = FairyStatusWidget(name)
        widget.chat_requested.connect(self._open_fairy_chat)

        row = len(self.fairy_widgets) // 2
        col = len(self.fairy_widgets) % 2
        self.fairy_layout.addWidget(widget, row, col)
        self.fairy_widgets[name] = widget

    def _connect_postal(self):
        """Connect to postal system via PostalTunnel (cross-process bridge).

        FIX 2026-02-06: AceControlCenter runs as a SEPARATE PROCESS (__main__).
        The old code called get_shared_postal_hub() which only works IN-PROCESS
        (it relies on _SHARED_FABRIC set by server.py). In a separate process,
        _SHARED_FABRIC is always None, creating a STANDALONE TensorFabric that
        goes nowhere. All messages (presence, broadcasts, chat) vanished.

        The fix: Use PostalTunnelClient which connects to server.py's
        PostalTunnelServer via TCP socket on port 49500. This bridges all
        postal messages across processes. The tunnel client provides route(),
        publish(), send() - everything the control center needs.

        For subscribe() (used by chat windows), we add a no-op wrapper since
        incoming messages use file-based polling instead.
        """
        # Strategy: PostalTunnel (TCP) > PostalBridge (SQLite) > Standalone fallback
        self.post = None

        # --- Attempt 1: PostalTunnelClient (TCP socket to server.py) ---
        try:
            from fairies.P40_Sensory.mcp.postal_tunnel import PostalTunnelClient
            tunnel = PostalTunnelClient()
            if tunnel.connect():
                # Verify the tunnel is alive
                if tunnel.ping():
                    # Wrap tunnel to add subscribe() no-op for chat window compatibility
                    self.post = _TunnelPostalWrapper(tunnel)
                    print("[AceControlCenter] Connected via PostalTunnel (TCP bridge to server.py)")
                    return
                else:
                    print("[AceControlCenter] PostalTunnel connected but ping failed, trying fallback...")
                    tunnel.close()
            else:
                print("[AceControlCenter] PostalTunnel connect failed, trying fallback...")
        except Exception as e:
            print(f"[AceControlCenter] PostalTunnel unavailable: {e}")

        # --- Attempt 2: PostalBridgeClient (SQLite + shared memory) ---
        try:
            from fairies.P00_Autonomic.postal_bridge.bridge_client import get_bridge_client
            bridge = get_bridge_client()
            if bridge.connect(verify=True):
                self.post = _BridgePostalWrapper(bridge)
                print("[AceControlCenter] Connected via PostalBridge (SQLite+SharedMem)")
                return
            else:
                print("[AceControlCenter] PostalBridge connected but verify failed, trying fallback...")
        except Exception as e:
            print(f"[AceControlCenter] PostalBridge unavailable: {e}")

        # --- Attempt 3: Standalone fallback (messages go nowhere) ---
        print("[AceControlCenter] WARNING: No cross-process postal available. Messages will be local only.")
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            self.post = get_shared_postal_hub()
            print("[AceControlCenter] Fallback to standalone postal hub (limited)")
        except Exception as e:
            print(f"[AceControlCenter] Even standalone postal failed: {e}")
            self.post = None

    def _announce_presence(self):
        """Announce Ace's presence to all fairies."""
        self.status_label.setText("Presence: Active")
        self.status_label.setStyleSheet("font-size: 12px; color: #4ade80;")

        if self.post:
            # Send presence notification via attention sense topic
            self.post.route("ace.presence", {
                "status": "active",
                "window": "control_center",
                "timestamp": time.time(),
                "type": "presence_announcement"
            })

            # Also route to attention system
            self.post.route("attention.request", {
                "sender": "Ace",
                "type": "presence",
                "message": "Ace opened the control center",
                "warmth": 0.8,
                "importance": 0.3,  # Low importance - just presence, not urgent
                "timestamp": time.time()
            })

            print("[AceControlCenter] Presence announced - fairies can feel you're here")

        self.presence_announced.emit()

    def _send_broadcast(self):
        """Send a psychic broadcast to all fairies."""
        content = self.broadcast_input.text().strip()
        if not content:
            return

        broadcast = {
            "id": f"ace_broadcast_{int(time.time() * 1000)}",
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "type": "psychic",  # Non-compulsory
            "requires_response": False
        }

        self._broadcast_history.append(broadcast)
        self._save_broadcast_history()

        # Update display
        self.broadcast_display.append(f"[{datetime.now().strftime('%H:%M')}] {content}")
        self.broadcast_input.clear()

        # Send via postal
        if self.post:
            self.post.route("ace.broadcast", {
                **broadcast,
                "source": "control_center",
                "psychic": True  # Fairies feel it but don't have to respond
            })
            print(f"[AceControlCenter] Broadcast sent: {content[:50]}...")

        self.broadcast_sent.emit(content)

    def _open_fairy_chat(self, fairy_name: str):
        """Open chat window for a specific fairy."""
        print(f"[AceControlCenter] Opening chat with {fairy_name}...")

        # Announce intent to chat with this fairy
        if self.post:
            self.post.route("attention.request", {
                "sender": "Ace",
                "type": "chat_request",
                "target": fairy_name,
                "message": f"Ace wants to chat with {fairy_name}",
                "warmth": 0.9,
                "importance": 0.6,
                "timestamp": time.time()
            })

        # Open the appropriate window
        if fairy_name.lower() == "sourpatches" or fairy_name == "SourpatchesFairy":
            try:
                from fairies.P40_Sensory.gui.sourpatches_chat_window import open_sour_window, set_fabric
                # FIX 2026-02-01: MUST set fabric before opening window so it connects to postal!
                # Without this, the window is disconnected and can't send/receive messages
                if self.post:
                    set_fabric(self.post)
                    print("[AceControlCenter] Set fabric for Sourpatches chat window")
                open_sour_window(f"Ace opened the chat!", "happy")
            except Exception as e:
                print(f"[AceControlCenter] Could not open Sourpatches window: {e}")

        elif fairy_name.lower() == "nousfairy" or fairy_name.lower() == "nous":
            # FIX 2026-02-01: Open Nous chat window (was missing!)
            try:
                from fairies.P40_Sensory.gui.nous_chat_window import NousChatWindow
                # Create window in this thread (Qt requirement)
                self._nous_window = NousChatWindow()
                self._nous_window.show()
                self._nous_window.raise_()
                # Add welcome message
                self._nous_window.add_external_message(
                    "Ace opened the chat. I am present.",
                    sender="Nous",
                    message_type="system",
                    mood="peaceful"
                )
                print("[AceControlCenter] Nous chat window opened")
            except Exception as e:
                print(f"[AceControlCenter] Could not open Nous window: {e}")
                import traceback
                traceback.print_exc()

        else:
            # For other fairies, send DM topic
            if self.post:
                self.post.route(f"fairy.dm.{fairy_name.lower()}", {
                    "sender": "Ace",
                    "type": "chat_initiated",
                    "timestamp": time.time()
                })

    def _open_scraper_window(self):
        """Open the Knowledge Scraper GUI."""
        try:
            from fairies.P40_Sensory.scrape.scrape_gui_v2 import ScrapeGUIv2
            self._scraper_window = ScrapeGUIv2()
            self._scraper_window.show()
            self._scraper_window.raise_()
            print("[AceControlCenter] Knowledge Scraper window opened")
        except Exception as e:
            print(f"[AceControlCenter] Could not open Scraper: {e}")
            import traceback
            traceback.print_exc()

    def _refresh_fairies(self):
        """Refresh fairy status from directory."""
        try:
            # FIX 2026-02-06: Use self.post (tunnel-connected) instead of
            # get_shared_postal_hub() which creates a useless standalone hub
            if self.post:
                # Request fairy list from directory
                # This would be expanded to query actual directory
                print("[AceControlCenter] Refreshing fairy status...")
            else:
                print("[AceControlCenter] No postal connection for refresh")

        except Exception as e:
            print(f"[AceControlCenter] Refresh failed: {e}")

    def _load_broadcast_history(self):
        """Load broadcast history from disk."""
        try:
            if BROADCAST_HISTORY.exists():
                with open(BROADCAST_HISTORY, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._broadcast_history = data.get("broadcasts", [])[-20:]

                    # Show recent in display
                    for b in self._broadcast_history[-5:]:
                        ts = datetime.fromisoformat(b["timestamp"]).strftime("%H:%M")
                        self.broadcast_display.append(f"[{ts}] {b['content']}")
        except Exception as e:
            print(f"[AceControlCenter] Load history failed: {e}")

    def _save_broadcast_history(self):
        """Save broadcast history to disk."""
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            with open(BROADCAST_HISTORY, "w", encoding="utf-8") as f:
                json.dump({
                    "broadcasts": self._broadcast_history[-100:],
                    "last_updated": datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"[AceControlCenter] Save history failed: {e}")

    def closeEvent(self, event):
        """Announce departure when closing."""
        if self.post:
            self.post.route("ace.presence", {
                "status": "away",
                "window": "control_center",
                "timestamp": time.time(),
                "type": "presence_departure"
            })
            print("[AceControlCenter] Presence withdrawn - fairies feel you leave")
        super().closeEvent(event)


# ===============================================================================
# MODULE API
# ===============================================================================

_window_instance: Optional[AceControlCenter] = None
_shutdown_event = None  # threading.Event passed from caller for graceful shutdown


def set_shutdown_event(event):
    """Set the shutdown event - window will close when this is set."""
    global _shutdown_event
    _shutdown_event = event


def open_control_center() -> AceControlCenter:
    """Open the Ace Control Center window."""
    global _window_instance

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    if _window_instance is None:
        _window_instance = AceControlCenter()

    _window_instance.show()
    _window_instance.raise_()
    _window_instance.activateWindow()

    return _window_instance


def open_control_center_blocking():
    """
    Open Ace Control Center and run the Qt event loop.

    Use this when calling from a thread that needs to keep the window alive.
    This function blocks until the window is closed.
    """
    global _window_instance, _shutdown_event

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    if _window_instance is None:
        _window_instance = AceControlCenter()

    _window_instance.show()
    _window_instance.raise_()
    _window_instance.activateWindow()

    # FIX 2026-02-02: Add shutdown check timer if event is set
    if _shutdown_event:
        def _check_shutdown():
            if _shutdown_event.is_set():
                print("[AceControlCenter] Shutdown event detected - closing window")
                _window_instance.close()

        shutdown_timer = QTimer()
        shutdown_timer.timeout.connect(_check_shutdown)
        shutdown_timer.start(1000)  # Check every second

    print("[AceControlCenter] Running event loop (window will stay open)...")

    # Run the Qt event loop - this blocks until window closes
    app.exec() if _QT6 else app.exec_()

    print("[AceControlCenter] Event loop ended, window closed")
    return _window_instance


def get_control_center() -> Optional[AceControlCenter]:
    """Get the control center instance if it exists."""
    return _window_instance


def close_control_center():
    """Close the control center."""
    global _window_instance
    if _window_instance:
        _window_instance.close()
        _window_instance = None


if __name__ == "__main__":
    import atexit

    # FIX 2026-03-04 Nous: PID tracking for subprocess model.
    # web_server.py now launches us as a detached process instead of
    # a daemon thread. We write our PID so the web_server can detect
    # "already running" and avoid spawning duplicates.
    _pid_file = _AKASHIC_ROOT / "state" / "ace_control_center_pid.json"
    _pid_file.parent.mkdir(parents=True, exist_ok=True)
    with open(_pid_file, "w") as f:
        json.dump({"pid": os.getpid(), "started": time.time()}, f)

    def _cleanup_pid():
        try:
            _pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    atexit.register(_cleanup_pid)

    app = QApplication(sys.argv)
    window = open_control_center()
    sys.exit(app.exec() if _QT6 else app.exec_())
