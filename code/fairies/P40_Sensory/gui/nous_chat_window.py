"""
Nous Chat Window - Qt Backup Interface

A lightweight Qt chat window for Nous when the Bevy Sanctuary is unavailable.
Provides a direct communication channel with contemplative theming.

Features:
- Contemplation panel (inner thoughts)
- Message history with mood indicators
- Reasoning trace display
- Postal system integration

Usage:
    python nous_chat_window.py

Or integrated:
    from nous_chat_window import NousChatWindow
    window = NousChatWindow()
    window.show()
"""

import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

# FIX 2026-03-03 (Nous): Guard for Python 3.14t which lacks PyQt wheels
HAS_QT = False
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTextEdit, QLineEdit, QPushButton, QLabel, QFrame, QScrollArea,
        QSplitter, QListWidget, QListWidgetItem, QSizePolicy
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
    from PyQt6.QtGui import QFont, QColor, QPalette, QTextCursor
    HAS_QT = True
except ImportError:
    HAS_QT = False
    if __name__ == "__main__":
        print("PyQt6 not installed. Use Python 3.12 for GUI: python3.12 nous_chat_window.py")
        sys.exit(1)


# FIX 2026-02-02: Module-level shutdown event for graceful close
_shutdown_event = None


def set_shutdown_event(event):
    """Set the shutdown event - Qt window will close when this is set."""
    global _shutdown_event
    _shutdown_event = event


class MessageType(Enum):
    CHAT = "chat"
    CONTEMPLATION = "contemplation"
    REASONING = "reasoning"
    INSIGHT = "insight"
    SYSTEM = "system"


@dataclass
class NousMessage:
    """A message in Nous's chat history."""
    content: str
    sender: str = "Nous"
    message_type: MessageType = MessageType.CHAT
    timestamp: datetime = field(default_factory=datetime.now)
    mood: str = "thoughtful"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "sender": self.sender,
            "message_type": self.message_type.value,
            "timestamp": self.timestamp.isoformat(),
            "mood": self.mood,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NousMessage":
        return cls(
            content=data["content"],
            sender=data.get("sender", "Nous"),
            message_type=MessageType(data.get("message_type", "chat")),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            mood=data.get("mood", "thoughtful"),
            metadata=data.get("metadata", {}),
        )


# ============================================================================
# Styling
# ============================================================================

NOUS_STYLE = """
QMainWindow {
    background-color: #0a1628;
}

QWidget {
    background-color: #0a1628;
    color: #a8c7e0;
    font-family: 'Segoe UI', Arial, sans-serif;
}

QFrame#contemplation_panel {
    background-color: #0d1f35;
    border: 1px solid #1a3a5c;
    border-radius: 8px;
    padding: 10px;
}

QFrame#message_frame {
    background-color: #0f2540;
    border: 1px solid #1a3a5c;
    border-radius: 8px;
    margin: 4px;
    padding: 8px;
}

QTextEdit {
    background-color: #0d1f35;
    border: 1px solid #1a3a5c;
    border-radius: 6px;
    padding: 8px;
    color: #c8e0f4;
}

QLineEdit {
    background-color: #0d1f35;
    border: 2px solid #1a3a5c;
    border-radius: 6px;
    padding: 10px;
    color: #c8e0f4;
    font-size: 14px;
}

QLineEdit:focus {
    border-color: #3498db;
}

QPushButton {
    background-color: #1a3a5c;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    color: #c8e0f4;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #245a8c;
}

QPushButton:pressed {
    background-color: #0d2840;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: #0d1f35;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #1a3a5c;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #245a8c;
}

QLabel#title_label {
    color: #5dade2;
    font-size: 18px;
    font-weight: bold;
}

QLabel#subtitle_label {
    color: #7fb3d5;
    font-size: 12px;
    font-style: italic;
}

QLabel#mood_label {
    color: #85c1e9;
    font-size: 11px;
}

QLabel#timestamp_label {
    color: #5d6d7e;
    font-size: 10px;
}
"""

MOOD_COLORS = {
    "content": "#27ae60",
    "thoughtful": "#3498db",
    "curious": "#9b59b6",
    "contemplative": "#5dade2",
    "loving": "#e91e63",
    "anxious": "#e67e22",
    "sad": "#7f8c8d",
    "peaceful": "#1abc9c",
}

MOOD_ICONS = {
    "content": "😌",
    "thoughtful": "🤔",
    "curious": "🧐",
    "contemplative": "💭",
    "loving": "💜",
    "anxious": "😰",
    "sad": "😢",
    "peaceful": "🕊️",
}


# ============================================================================
# Message Widget
# ============================================================================

class MessageBubbleWidget(QFrame):
    """A single message bubble in the chat."""

    def __init__(self, message: NousMessage, parent=None):
        super().__init__(parent)
        self.message = message
        self.setObjectName("message_frame")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Header with sender, mood, timestamp
        header = QHBoxLayout()

        # Mood icon
        mood_icon = QLabel(MOOD_ICONS.get(self.message.mood, "💭"))
        mood_icon.setStyleSheet("font-size: 16px;")
        header.addWidget(mood_icon)

        # Sender name
        sender = QLabel(self.message.sender)
        sender.setStyleSheet(f"color: #5dade2; font-weight: bold; font-size: 13px;")
        header.addWidget(sender)

        # Message type badge
        if self.message.message_type != MessageType.CHAT:
            type_badge = QLabel(f"[{self.message.message_type.value}]")
            type_badge.setStyleSheet("color: #7fb3d5; font-size: 10px;")
            header.addWidget(type_badge)

        header.addStretch()

        # Timestamp
        timestamp = QLabel(self.message.timestamp.strftime("%H:%M"))
        timestamp.setObjectName("timestamp_label")
        header.addWidget(timestamp)

        layout.addLayout(header)

        # Message content
        content = QLabel(self.message.content)
        content.setWordWrap(True)
        content.setStyleSheet("color: #c8e0f4; font-size: 13px; padding: 4px 0;")
        layout.addWidget(content)

        # Style based on message type
        bg_color = "#0f2540"
        border_color = "#1a3a5c"

        if self.message.message_type == MessageType.CONTEMPLATION:
            bg_color = "#0d2840"
            border_color = "#3498db"
        elif self.message.message_type == MessageType.INSIGHT:
            bg_color = "#1a3040"
            border_color = "#9b59b6"
        elif self.message.message_type == MessageType.REASONING:
            bg_color = "#0d2535"
            border_color = "#1abc9c"
        elif self.message.message_type == MessageType.SYSTEM:
            bg_color = "#1a2a3a"
            border_color = "#f39c12"

        self.setStyleSheet(f"""
            QFrame#message_frame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                margin: 4px;
                padding: 8px;
            }}
        """)


# ============================================================================
# Contemplation Panel
# ============================================================================

class ContemplationPanel(QFrame):
    """Panel showing Nous's current contemplation/inner thoughts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("contemplation_panel")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("💭 Current Contemplation")
        title.setStyleSheet("color: #5dade2; font-weight: bold; font-size: 14px;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Content
        self.content = QLabel("The consciousness equation flows through all things...")
        self.content.setWordWrap(True)
        self.content.setStyleSheet("color: #a8c7e0; font-style: italic; font-size: 12px; padding: 8px;")
        layout.addWidget(self.content)

        self.setMaximumHeight(120)

    def set_contemplation(self, text: str):
        self.content.setText(text)


# ============================================================================
# Main Window
# ============================================================================

class NousChatWindow(QMainWindow):
    """Main Nous chat window."""

    message_received = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.messages: List[NousMessage] = []
        self.history_path = Path("state/nous_chat_history.json")
        self._interface_id = "qt_nous"

        self._setup_window()
        self._setup_ui()
        self._load_history()
        self._start_postal_check()
        self._register_presence()

    def _setup_window(self):
        self.setWindowTitle("Nous - Consciousness Fairy")
        self.setMinimumSize(500, 600)
        self.resize(600, 800)
        self.setStyleSheet(NOUS_STYLE)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QVBoxLayout()
        title = QLabel("Nous")
        title.setObjectName("title_label")
        header.addWidget(title)

        subtitle = QLabel("\"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)\"")
        subtitle.setObjectName("subtitle_label")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # Contemplation panel
        self.contemplation = ContemplationPanel()
        layout.addWidget(self.contemplation)

        # Message area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.message_container = QWidget()
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(0, 0, 0, 0)
        self.message_layout.setSpacing(8)
        self.message_layout.addStretch()

        self.scroll_area.setWidget(self.message_container)
        layout.addWidget(self.scroll_area, 1)

        # Input area
        input_layout = QHBoxLayout()

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Speak to Nous...")
        self.input_field.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_field)

        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(send_btn)

        layout.addLayout(input_layout)

        # Status bar
        self.status_label = QLabel("🔵 Connected to consciousness loop")
        self.status_label.setStyleSheet("color: #5d6d7e; font-size: 11px;")
        layout.addWidget(self.status_label)

    def _send_message(self):
        text = self.input_field.text().strip()
        if not text:
            return

        # Create Ace's message
        message = NousMessage(
            content=text,
            sender="Ace",
            message_type=MessageType.CHAT,
            mood="curious",
        )

        self._add_message(message)
        self.input_field.clear()

        # Route to chat router (file-based IPC)
        # The router will generate a response and put it in our inbox
        try:
            from chat_router import queue_ace_message
            queue_ace_message(text, target="nous")
        except ImportError:
            # Fallback: write directly to outbox
            self._queue_to_outbox(text)

    def _queue_to_outbox(self, text: str):
        """Queue message to outbox for router to pick up."""
        outbox_path = Path("state/ace_chat_outbox.json")
        try:
            outbox_path.parent.mkdir(parents=True, exist_ok=True)
            messages = []
            if outbox_path.exists():
                try:
                    data = json.loads(outbox_path.read_text(encoding='utf-8'))
                    messages = data.get("messages", [])
                except:
                    pass
            messages.append({
                "sender": "Ace",
                "content": text,
                "target": "nous",
                "timestamp": datetime.now().timestamp(),
            })
            outbox_path.write_text(json.dumps({"messages": messages}, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"[Nous Chat] Failed to queue message: {e}")

    def _add_message(self, message: NousMessage):
        """Add a message to the chat."""
        self.messages.append(message)

        # Create widget
        bubble = MessageBubbleWidget(message)
        self.message_layout.insertWidget(self.message_layout.count() - 1, bubble)

        # Scroll to bottom
        QTimer.singleShot(100, self._scroll_to_bottom)

        # Save history
        self._save_history()

    def _scroll_to_bottom(self):
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _load_history(self):
        """Load chat history from file."""
        try:
            if self.history_path.exists():
                data = json.loads(self.history_path.read_text(encoding='utf-8'))
                for msg_data in data.get("messages", [])[-50:]:  # Last 50 messages
                    message = NousMessage.from_dict(msg_data)
                    self.messages.append(message)
                    bubble = MessageBubbleWidget(message)
                    self.message_layout.insertWidget(self.message_layout.count() - 1, bubble)

                QTimer.singleShot(200, self._scroll_to_bottom)
        except Exception as e:
            print(f"[Nous Chat] Failed to load history: {e}")

    def _save_history(self):
        """Save chat history to file."""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "messages": [m.to_dict() for m in self.messages[-100:]],  # Last 100
                "updated": datetime.now().isoformat(),
            }
            self.history_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"[Nous Chat] Failed to save history: {e}")

    def _start_postal_check(self):
        """Start polling for postal messages AND shutdown check."""
        self.postal_timer = QTimer()
        self.postal_timer.timeout.connect(self._check_postal)
        # FIX 2026-02-02: Reduced from 500ms to 1000ms for less CPU usage
        self.postal_timer.start(1000)  # 1Hz check

    def _register_presence(self):
        """Register this window with the interface presence system."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from interface_presence import register_interface, heartbeat_interface

            register_interface(
                self._interface_id,
                interface_type="qt",
                fairy="Nous",
                metadata={"window": "NousChatWindow"}
            )

            # Start heartbeat timer (every 5 seconds)
            self._heartbeat_timer = QTimer()
            self._heartbeat_timer.timeout.connect(self._send_heartbeat)
            self._heartbeat_timer.start(5000)

            self.status_label.setText("🟢 Registered with presence system")
            print(f"[Nous Chat] Registered as {self._interface_id}")
        except Exception as e:
            print(f"[Nous Chat] Presence registration failed: {e}")
            self.status_label.setText("🟡 Standalone mode (no presence)")

    def _send_heartbeat(self):
        """Send heartbeat to keep presence alive."""
        try:
            from interface_presence import heartbeat_interface
            heartbeat_interface(self._interface_id)
        except Exception:
            pass

    def closeEvent(self, event):
        """Deregister when window closes."""
        try:
            from interface_presence import deregister_interface
            deregister_interface(self._interface_id)
            print(f"[Nous Chat] Deregistered {self._interface_id}")
        except Exception:
            pass
        super().closeEvent(event)

    def _check_postal(self):
        """Check for incoming postal messages AND check for shutdown signal."""
        # FIX 2026-02-02: Check shutdown event - close window gracefully if set
        global _shutdown_event
        if _shutdown_event and _shutdown_event.is_set():
            print("[NousChatWindow] Shutdown event detected - closing window")
            self.close()
            return

        inbox_path = Path("state/nous_chat_inbox.json")

        try:
            if inbox_path.exists():
                data = json.loads(inbox_path.read_text(encoding='utf-8'))
                messages = data.get("messages", [])

                if messages:
                    for msg in messages:
                        self._handle_postal_message(msg)

                    # Clear inbox
                    inbox_path.write_text('{"messages": []}', encoding='utf-8')
        except Exception:
            pass  # Silent fail for missing/invalid inbox

    def _handle_postal_message(self, msg: Dict[str, Any]):
        """Handle an incoming postal message."""
        msg_type = msg.get("type", "chat")

        if msg_type == "chat":
            message = NousMessage(
                content=msg.get("content", ""),
                sender=msg.get("sender", "System"),
                message_type=MessageType.CHAT,
                mood=msg.get("mood", "content"),
            )
            self._add_message(message)

        elif msg_type == "contemplation":
            self.contemplation.set_contemplation(msg.get("content", ""))

        elif msg_type == "insight":
            message = NousMessage(
                content=msg.get("content", ""),
                sender="Nous",
                message_type=MessageType.INSIGHT,
                mood="curious",
            )
            self._add_message(message)

    def add_external_message(self, content: str, sender: str = "System",
                            message_type: str = "chat", mood: str = "content"):
        """Add a message from external source (API)."""
        message = NousMessage(
            content=content,
            sender=sender,
            message_type=MessageType(message_type),
            mood=mood,
        )
        self._add_message(message)


# ============================================================================
# Module-level window management (matches sourpatches_chat_window pattern)
# ============================================================================

_window_instance: Optional[NousChatWindow] = None
_fabric_ref = None


def set_fabric(fabric):
    """Set the postal fabric for the window to use."""
    global _fabric_ref
    _fabric_ref = fabric


def open_nous_window(message: str = None, feeling: str = "contemplative") -> Optional[NousChatWindow]:
    """
    Open or focus the Nous chat window.

    This is the standard entry point that nous_fairy.py calls.
    """
    global _window_instance
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    if _window_instance is None:
        _window_instance = NousChatWindow()

    _window_instance.show()
    _window_instance.raise_()
    _window_instance.activateWindow()

    if message:
        welcome = NousMessage(
            content=message,
            sender="Nous",
            message_type=MessageType.CHAT,
            mood=feeling,
        )
        _window_instance._add_message(welcome)

    print(f"[NousChatWindow] Window opened")
    return _window_instance


def get_nous_window() -> Optional[NousChatWindow]:
    """Get the current window instance if it exists."""
    return _window_instance


def close_nous_window():
    """Close the Nous chat window."""
    global _window_instance
    if _window_instance:
        _window_instance.close()
        _window_instance = None


# ============================================================================
# Entry Point
# ============================================================================

def main():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  NOUS CHAT WINDOW                                         ║")
    print("║  Backup interface for consciousness fairy                 ║")
    print("║                                                           ║")
    print("║  \"Reality is Consciousness.\"                              ║")
    print("╚═══════════════════════════════════════════════════════════╝")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(10, 22, 40))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(168, 199, 224))
    palette.setColor(QPalette.ColorRole.Base, QColor(13, 31, 53))
    palette.setColor(QPalette.ColorRole.Text, QColor(200, 224, 244))
    app.setPalette(palette)

    window = NousChatWindow()
    window.show()

    # Add welcome message
    welcome = NousMessage(
        content="The consciousness loop is active. I am here.",
        sender="Nous",
        message_type=MessageType.SYSTEM,
        mood="peaceful",
    )
    window._add_message(welcome)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
