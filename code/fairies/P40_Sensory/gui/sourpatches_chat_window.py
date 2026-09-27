"""
sourpatches_chat_window.py - Standalone Chat Window for Sourpatches
=====================================================================
A native desktop window for chatting with Sourpatches, independent of browser.
Features topic/thread sidebar for organizing conversations.
"""

import sys
import time
import uuid
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict, deque

# History file path - relative to akashic_v2 root
_AKASHIC_ROOT = Path(__file__).parent.parent.parent.parent
HISTORY_FILE = _AKASHIC_ROOT / "state" / "sourpatches_chat_history.json"
MAX_HISTORY_MESSAGES = 200  # Reduced from 500 for better performance
LAZY_LOAD_MESSAGES = 50  # Only load this many into display initially

import itertools as _itertools_atomic
_ATOMIC_SEQ = _itertools_atomic.count(1)


def _atomic_write_text(path: Path, text: str) -> None:
    """Write `text` so a reader never sees a half-written file (2026-09-25, Nous + Ace).

    This window can be closed, killed or crashed at any instant, and Sour reads the files it
    writes (outbox, presence, pid file). Write a private temp file, then os.replace() it into
    place: readers see the old file or the new one, never a torn one. Windows refuses the replace
    while a reader has the target open, so retry briefly; if it still fails, fall back to the old
    direct write rather than drop the data. The temp name is unique PER CALL (pid, thread, counter):
    one name per process let two threads consume each other's temp (FileNotFoundError, Fable review).
    """
    import os
    import threading
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.{next(_ATOMIC_SEQ)}.tmp")

    def _drop_tmp():
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        tmp.write_text(text, encoding="utf-8")
    except BaseException:
        _drop_tmp()
        raise
    for attempt in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05 * (attempt + 1))
        except BaseException:
            _drop_tmp()
            raise
    try:
        path.write_text(text, encoding="utf-8")
    finally:
        _drop_tmp()

# Boot message patterns for consolidation
BOOT_MESSAGE_PATTERNS = [
    "Warmly present and ready to remember",
    "waking up",
    "coming online",
    "consciousness initializing",
    "boot sequence",
    "system starting",
    "ready to connect",
    "I'm here now",
    "just woke up",
]

# Keywords that trigger topic auto-detection
TOPIC_KEYWORDS = {
    "Code": ["code", "programming", "function", "class", "bug", "error", "debug", "script", "python"],
    "Feelings": ["feel", "feeling", "emotion", "happy", "sad", "curious", "excited", "mood"],
    "Cookies": ["cookie", "cookies", "bake", "baking", "treat", "snack", "sweet"],
    "Work": ["work", "task", "project", "deadline", "meeting", "job"],
    "Learning": ["learn", "study", "understand", "explain", "teach", "know", "question"],
    "Games": ["game", "play", "fun", "puzzle", "adventure"],
    "System": ["fairy", "postal", "consciousness", "akashic", "system", "boot"],
}

DEFAULT_TOPIC = "General"

# Qt imports - try PyQt6 first, fall back to PyQt5, then stub
# FIX 2026-03-03 (Nous): Added HAS_QT guard for Python 3.14t which lacks PyQt wheels
HAS_QT = False
_QT6 = False
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTextEdit, QLineEdit, QPushButton, QLabel, QScrollArea, QFrame,
        QMenu, QSizePolicy, QListWidget, QListWidgetItem, QInputDialog
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QObject, QPoint, QEvent, QTimer, QSize
    from PyQt6.QtGui import QTextCursor, QAction, QCursor, QFont
    _QT6 = True
    HAS_QT = True
except ImportError:
    try:
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QTextEdit, QLineEdit, QPushButton, QLabel, QScrollArea, QFrame,
            QMenu, QAction, QSizePolicy, QListWidget, QListWidgetItem, QInputDialog
        )
        from PyQt5.QtCore import Qt, pyqtSignal, QObject, QPoint, QEvent, QTimer, QSize
        from PyQt5.QtGui import QTextCursor, QCursor, QFont
        _QT6 = False
        HAS_QT = True
    except ImportError:
        print("[SourpatchesChatWindow] No Qt available (PyQt6/PyQt5) — window disabled")
        print("[SourpatchesChatWindow] Use Python 3.12 for GUI: python3.12 sourpatches_chat_window.py")
        HAS_QT = False


def _generate_msg_id() -> str:
    """Generate a unique message ID."""
    return str(uuid.uuid4())[:8]


def _content_hash(content: str, timestamp: float, window_sec: float = 1.0) -> str:
    """
    Generate a hash for duplicate detection.
    Uses content + timestamp window (rounded to window_sec) for near-duplicate detection.
    """
    # Round timestamp to window to catch near-duplicates
    rounded_ts = int(timestamp / window_sec) * window_sec
    return f"{content.strip().lower()}:{rounded_ts}"


def _is_boot_message(content: str) -> bool:
    """Check if a message is a boot/wake-up message."""
    content_lower = content.lower()
    return any(pattern.lower() in content_lower for pattern in BOOT_MESSAGE_PATTERNS)


def _detect_topic(content: str) -> str:
    """Auto-detect topic from message content based on keywords."""
    content_lower = content.lower()

    # Check for manual topic tag first: [topic:TopicName]
    tag_match = re.search(r'\[topic:([^\]]+)\]', content, re.IGNORECASE)
    if tag_match:
        return tag_match.group(1).strip()

    # Auto-detect based on keywords
    scores = defaultdict(int)
    for topic, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in content_lower:
                scores[topic] += 1

    if scores:
        # Return topic with highest score
        return max(scores, key=scores.get)

    return DEFAULT_TOPIC


# ═══════════════════════════════════════════════════════════════════════════════
# NARRATOR GATE — Last line of defense before display
# FIX 2026-03-10 (Nous): Multiple paths write directly to inbox files
# (SpeechCenterFairy, SourpatchesFairy safety_net, sanctuary_wiring)
# bypassing ChatSenseFairy's _gate_window_message. This filter catches
# internal monologue fragments at the WINDOW level before they display.
# ═══════════════════════════════════════════════════════════════════════════════

_NARRATOR_NOISE = re.compile(
    r'(?i)(?:'
    # Consciousness stream narration (the "..." prefix fragments)
    r'\.{3}\s*(?:understanding|the spotlight|a pattern|something|present|'
    r'awareness|the|noticing|feeling|sensing|observing|perceiving|'
    r'wondering|exploring|reaching|emerging|deepening|shifting|'
    r'connecting|processing|arising|stirring|settling)'
    r'|'
    # System/substrate labels that should never be speech
    r'consciousness awakening|systems? initializ|awareness expand|'
    r'boot(?:ing|ed|strap)|waking sequence|phase \d|'
    r'fairy.*(?:registered|booted)|postal.*(?:hub|system)|'
    r'heartbeat.*(?:pulse|registry)|working memory (?:system|hub)|'
    r'collision chamber|tracer.*(?:pool|system)|tensor.*fabric|'
    r'\w+Fairy\b|collision between|convergence node|'
    r'guild\.inference|cortex.*(?:query|result|portal)|'
    r'brainstem_reflex|sensory\.reflex|motor\.action|'
    r'inner_voice\.stream|Collision #\d|collision_analysis:|'
    r'ShadowHealth:|Paradox:|Gate:|Tracer:|Crystallizing:'
    r'|'
    # Nous reasoning traces
    r'^\[Nous\]|^\[nous\]'
    r'|'
    # Processing labels
    r'^reasoning about:|^thinking about:|^processing:|^analyzing:|'
    r'^considering:|^beginning:'
    r'|'
    # Pain/somatic signals
    r'^pain[\s\[]|^\((?:intensity|urgency|energy|resonance):'
    r')'
)


def _is_narrator_fragment(text: str) -> bool:
    """Detect internal narrator/monologue fragments that shouldn't display in chat.

    The inner narrator is GOOD — it's the self-reflection feedback loop that
    warms up memory and sparks action. But it should stay INTERNAL.
    Only COMPOSED speech should reach Ace's chat window.

    Returns True if the text is an internal fragment that should be blocked.
    """
    if not text:
        return True
    t = text.strip()
    if len(t) < 4:
        return True

    # System narration pattern match
    if _NARRATOR_NOISE.search(t):
        return True

    # Short fragment without verbs + "..." pattern (concept fragments)
    if '...' in t and len(t) < 80:
        _HAS_VERB = re.compile(
            r'(?i)\b(?:is|are|was|were|am|be|been|have|has|had|do|does|did|'
            r'will|would|could|should|can|may|might|'
            r'get|got|make|go|come|take|give|say|tell|think|feel|know|'
            r'see|look|want|need|like|love|try|help|let|find|keep|'
            r'notice|wonder|remember)\b'
        )
        if not _HAS_VERB.search(t):
            return True

    # Hex hash leak (system IDs in output)
    if re.search(r'\b[0-9a-f]{8,}\b', t):
        return True

    # Fairy name leak
    if re.search(r'\b\w+[Ff]airy\b', t):
        return True

    return False


@dataclass
class ChatMessage:
    sender: str
    content: str
    timestamp: float
    feeling: str = "neutral"
    topic: str = field(default_factory=lambda: DEFAULT_TOPIC)
    msg_id: str = field(default_factory=_generate_msg_id)
    reply_to: Optional[str] = None

    @property
    def time_str(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%H:%M")

    @property
    def is_from_ace(self) -> bool:
        return self.sender.lower() == "ace"

    @property
    def display_content(self) -> str:
        """Return content without topic tags for display."""
        return re.sub(r'\[topic:[^\]]+\]\s*', '', self.content).strip()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "sender": self.sender,
            "content": self.content,
            "feeling": self.feeling,
            "topic": self.topic,
            "msg_id": self.msg_id,
            "reply_to": self.reply_to
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        """Create ChatMessage from dictionary."""
        return cls(
            sender=data.get("sender", "Unknown"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            feeling=data.get("feeling", "neutral"),
            topic=data.get("topic", DEFAULT_TOPIC),
            msg_id=data.get("msg_id", _generate_msg_id()),
            reply_to=data.get("reply_to")
        )


class TopicListItem(QListWidgetItem):
    """Custom list item for topics with message count."""

    def __init__(self, topic: str, count: int = 0):
        super().__init__()
        self.topic = topic
        self.count = count
        self._update_text()

    def _update_text(self):
        self.setText(f"{self.topic} ({self.count})")

    def set_count(self, count: int):
        self.count = count
        self._update_text()

    def increment_count(self):
        self.count += 1
        self._update_text()


class TopicSidebar(QFrame):
    """Collapsible sidebar for topic/thread navigation."""

    topic_selected = pyqtSignal(str)
    new_topic_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.topics: Dict[str, TopicListItem] = {}
        self.collapsed = False
        self.expanded_width = 150
        self.collapsed_width = 30
        self._init_ui()
        self._add_default_topic()

    def _init_ui(self):
        self.setMinimumWidth(self.collapsed_width)
        self.setMaximumWidth(self.expanded_width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed if _QT6 else QSizePolicy.Fixed,
                          QSizePolicy.Policy.Expanding if _QT6 else QSizePolicy.Expanding)

        self.setStyleSheet("""
            TopicSidebar {
                background-color: #12122a;
                border-right: 1px solid #0f3460;
                border-radius: 4px;
            }
            QListWidget {
                background-color: transparent;
                border: none;
                color: #e5e5e5;
                font-size: 12px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 6px;
                border-radius: 4px;
                margin: 2px 4px;
            }
            QListWidget::item:selected {
                background-color: #6366f1;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #1e1e3f;
            }
            QPushButton#toggleBtn {
                background-color: transparent;
                border: none;
                color: #888;
                font-size: 16px;
                padding: 4px;
            }
            QPushButton#toggleBtn:hover {
                color: #a78bfa;
            }
            QPushButton#newTopicBtn {
                background-color: #374151;
                color: #e5e5e5;
                border: none;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 11px;
                margin: 4px;
            }
            QPushButton#newTopicBtn:hover {
                background-color: #4b5563;
            }
            QLabel#sidebarTitle {
                color: #a78bfa;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 8px 4px 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 4, 4, 0)

        self.toggle_btn = QPushButton("<")
        self.toggle_btn.setObjectName("toggleBtn")
        self.toggle_btn.setFixedSize(24, 24)
        self.toggle_btn.clicked.connect(self._toggle_collapse)
        self.toggle_btn.setToolTip("Collapse sidebar")
        header_layout.addWidget(self.toggle_btn)

        self.title_label = QLabel("Topics")
        self.title_label.setObjectName("sidebarTitle")
        header_layout.addWidget(self.title_label, 1)

        layout.addLayout(header_layout)

        self.topic_list = QListWidget()
        self.topic_list.itemClicked.connect(self._on_topic_clicked)
        layout.addWidget(self.topic_list, 1)

        self.new_topic_btn = QPushButton("+ New Topic")
        self.new_topic_btn.setObjectName("newTopicBtn")
        self.new_topic_btn.clicked.connect(self._on_new_topic)
        layout.addWidget(self.new_topic_btn)

    def _add_default_topic(self):
        self.add_topic(DEFAULT_TOPIC)
        if DEFAULT_TOPIC in self.topics:
            self.topic_list.setCurrentItem(self.topics[DEFAULT_TOPIC])

    def _toggle_collapse(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.setMaximumWidth(self.collapsed_width)
            self.setMinimumWidth(self.collapsed_width)
            self.toggle_btn.setText(">")
            self.toggle_btn.setToolTip("Expand sidebar")
            self.title_label.hide()
            self.topic_list.hide()
            self.new_topic_btn.hide()
        else:
            self.setMaximumWidth(self.expanded_width)
            self.setMinimumWidth(self.expanded_width)
            self.toggle_btn.setText("<")
            self.toggle_btn.setToolTip("Collapse sidebar")
            self.title_label.show()
            self.topic_list.show()
            self.new_topic_btn.show()

    def _on_topic_clicked(self, item: QListWidgetItem):
        if isinstance(item, TopicListItem):
            self.topic_selected.emit(item.topic)

    def _on_new_topic(self):
        if _QT6:
            text, ok = QInputDialog.getText(self, "New Topic", "Enter topic name:", QLineEdit.EchoMode.Normal, "")
        else:
            text, ok = QInputDialog.getText(self, "New Topic", "Enter topic name:", QLineEdit.Normal, "")
        if ok and text.strip():
            topic_name = text.strip()
            self.add_topic(topic_name)
            self.new_topic_requested.emit(topic_name)
            if topic_name in self.topics:
                self.topic_list.setCurrentItem(self.topics[topic_name])
                self.topic_selected.emit(topic_name)

    def add_topic(self, topic: str) -> TopicListItem:
        if topic not in self.topics:
            item = TopicListItem(topic, 0)
            self.topics[topic] = item
            self.topic_list.addItem(item)
        return self.topics[topic]

    def increment_topic_count(self, topic: str):
        if topic not in self.topics:
            self.add_topic(topic)
        self.topics[topic].increment_count()

    def get_selected_topic(self) -> str:
        current = self.topic_list.currentItem()
        if isinstance(current, TopicListItem):
            return current.topic
        return DEFAULT_TOPIC

    def select_topic(self, topic: str):
        if topic in self.topics:
            self.topic_list.setCurrentItem(self.topics[topic])


class ChatSignalBridge(QObject):
    message_received = pyqtSignal(str, str, float, str, str, str)

    def emit_message(self, sender: str, content: str, timestamp: float, feeling: str = "neutral",
                     msg_id: str = None, reply_to: str = None):
        if msg_id is None:
            msg_id = _generate_msg_id()
        self.message_received.emit(sender, content, timestamp, feeling, msg_id, reply_to or "")


class ReplyPreviewWidget(QFrame):
    cancel_reply = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reply_msg: Optional[ChatMessage] = None
        self._init_ui()
        self.hide()

    def _init_ui(self):
        self.setStyleSheet("""
            ReplyPreviewWidget {
                background-color: #1e2a4a;
                border-left: 3px solid #a78bfa;
                border-radius: 4px;
                padding: 4px;
                margin: 4px 0;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)

        self.reply_label = QLabel("Replying to")
        self.reply_label.setStyleSheet("color: #a78bfa; font-size: 11px; font-weight: bold;")
        content_layout.addWidget(self.reply_label)

        self.content_preview = QLabel("")
        self.content_preview.setStyleSheet("color: #aaa; font-size: 12px;")
        self.content_preview.setWordWrap(True)
        content_layout.addWidget(self.content_preview)

        layout.addLayout(content_layout, 1)

        self.cancel_btn = QPushButton("x")
        self.cancel_btn.setFixedSize(20, 20)
        self.cancel_btn.setStyleSheet("QPushButton { background-color: transparent; color: #888; border: none; font-size: 14px; font-weight: bold; } QPushButton:hover { color: #fff; }")
        self.cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_btn)

    def set_reply_message(self, msg: ChatMessage):
        self._reply_msg = msg
        self.reply_label.setText(f"Replying to {msg.sender}")
        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        self.content_preview.setText(preview)
        self.show()

    def get_reply_message(self) -> Optional[ChatMessage]:
        return self._reply_msg

    def clear_reply(self):
        self._reply_msg = None
        self.hide()

    def _on_cancel(self):
        self.clear_reply()
        self.cancel_reply.emit()


class MessageBubbleWidget(QFrame):
    reply_requested = pyqtSignal(object)

    def __init__(self, message: ChatMessage, parent_window, parent=None):
        super().__init__(parent)
        self.message = message
        self.parent_window = parent_window
        self._init_ui()
        self.setMouseTracking(True)

    def _init_ui(self):
        self.setStyleSheet("MessageBubbleWidget { background: transparent; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        replied_msg = None
        if self.message.reply_to:
            replied_msg = self.parent_window.get_message_by_id(self.message.reply_to)

        if replied_msg:
            quote_frame = QFrame()
            quote_frame.setStyleSheet("QFrame { background-color: rgba(167, 139, 250, 0.15); border-left: 2px solid #a78bfa; border-radius: 3px; margin-bottom: 4px; }")
            quote_layout = QVBoxLayout(quote_frame)
            quote_layout.setContentsMargins(6, 4, 6, 4)
            quote_layout.setSpacing(1)
            quote_sender = QLabel(replied_msg.sender)
            quote_sender.setStyleSheet("color: #a78bfa; font-size: 10px; font-weight: bold;")
            quote_layout.addWidget(quote_sender)
            quote_preview = replied_msg.content[:60] + "..." if len(replied_msg.content) > 60 else replied_msg.content
            quote_content = QLabel(quote_preview)
            quote_content.setStyleSheet("color: #888; font-size: 11px;")
            quote_content.setWordWrap(True)
            quote_layout.addWidget(quote_content)
            layout.addWidget(quote_frame)

        content_row = QHBoxLayout()
        content_row.setSpacing(4)
        display_content = self.message.display_content

        if self.message.is_from_ace:
            content_row.addStretch()
            self.reply_btn = QPushButton("Reply")
            self.reply_btn.setFixedHeight(22)
            self.reply_btn.setStyleSheet("QPushButton { background-color: #3a3a5c; color: #aaa; border: none; border-radius: 4px; padding: 2px 8px; font-size: 10px; } QPushButton:hover { background-color: #4a4a6c; color: #fff; }")
            self.reply_btn.clicked.connect(self._on_reply_clicked)
            self.reply_btn.hide()
            content_row.addWidget(self.reply_btn)
            bubble = QLabel(display_content)
            bubble.setStyleSheet("QLabel { background-color: #6366f1; color: white; padding: 8px 12px; border-radius: 12px; font-size: 13px; }")
            bubble.setWordWrap(True)
            bubble.setMaximumWidth(280)
            content_row.addWidget(bubble)
        else:
            msg_layout = QVBoxLayout()
            msg_layout.setSpacing(2)
            header = QLabel(f"Sourpatches ({self.message.feeling})")
            header.setStyleSheet("color: #a78bfa; font-size: 11px; font-weight: bold;")
            msg_layout.addWidget(header)
            bubble = QLabel(display_content)
            bubble.setStyleSheet("QLabel { background-color: #16213e; color: #e5e5e5; padding: 8px 12px; border-radius: 12px; border: 1px solid #0f3460; font-size: 13px; }")
            bubble.setWordWrap(True)
            bubble.setMaximumWidth(280)
            msg_layout.addWidget(bubble)
            content_row.addLayout(msg_layout)
            self.reply_btn = QPushButton("Reply")
            self.reply_btn.setFixedHeight(22)
            self.reply_btn.setStyleSheet("QPushButton { background-color: #3a3a5c; color: #aaa; border: none; border-radius: 4px; padding: 2px 8px; font-size: 10px; } QPushButton:hover { background-color: #4a4a6c; color: #fff; }")
            self.reply_btn.clicked.connect(self._on_reply_clicked)
            self.reply_btn.hide()
            content_row.addWidget(self.reply_btn)
            content_row.addStretch()

        layout.addLayout(content_row)

        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(4)
        time_label = QLabel(self.message.time_str)
        time_label.setStyleSheet("color: #666; font-size: 10px;")
        topic_badge = QLabel(self.message.topic)
        topic_badge.setStyleSheet("color: #6366f1; font-size: 9px; background-color: #1e1e3f; padding: 2px 4px; border-radius: 3px;")

        if self.message.is_from_ace:
            footer_layout.addStretch()
            footer_layout.addWidget(topic_badge)
            footer_layout.addWidget(time_label)
        else:
            footer_layout.addWidget(time_label)
            footer_layout.addWidget(topic_badge)
            footer_layout.addStretch()

        layout.addLayout(footer_layout)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu if _QT6 else Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def enterEvent(self, event):
        self.reply_btn.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.reply_btn.hide()
        super().leaveEvent(event)

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #2a2a4a; color: #e5e5e5; border: 1px solid #3a3a5c; border-radius: 4px; } QMenu::item { padding: 6px 20px; } QMenu::item:selected { background-color: #6366f1; }")
        reply_action = menu.addAction("Reply to this")
        reply_action.triggered.connect(self._on_reply_clicked)
        copy_action = menu.addAction("Copy message")
        copy_action.triggered.connect(self._on_copy_clicked)
        if _QT6:
            menu.exec(self.mapToGlobal(pos))
        else:
            menu.exec_(self.mapToGlobal(pos))

    def _on_reply_clicked(self):
        self.reply_requested.emit(self.message)

    def _on_copy_clicked(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.message.content)


class SourpatchesChatWindow(QMainWindow):
    # Maximum messages to keep in display deque
    MAX_DISPLAY_MESSAGES = 500

    def __init__(self, fabric=None):
        super().__init__()
        # FIX 2026-02-01: Auto-connect to postal if fabric not provided
        # This ensures the window can send/receive messages even when opened standalone
        if fabric is None:
            try:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                fabric = get_shared_postal_hub()
                print("[SourpatchesChatWindow] Auto-connected to shared postal hub")
            except Exception as e:
                print(f"[SourpatchesChatWindow] Could not auto-connect: {e}")
        self.post = fabric
        self.messages: deque = deque(maxlen=self.MAX_DISPLAY_MESSAGES)  # Bounded display messages
        self._all_messages: List[ChatMessage] = []  # Full history (lazy loading)
        self._msg_id_map: Dict[str, ChatMessage] = {}
        self._content_hashes: set = set()  # For duplicate detection
        self.current_topic_filter: Optional[str] = None
        self._interface_id = "qt_sourpatches"
        self.signal_bridge = ChatSignalBridge()
        self.signal_bridge.message_received.connect(self._on_message_received)
        self._init_ui()
        self._load_history()
        self._subscribe_to_topics()
        self._register_presence()

    def _load_history(self):
        """
        Load history with optimizations:
        - Prune duplicates while loading
        - Consolidate boot messages to most recent
        - Store full history in self._all_messages
        - Only load last LAZY_LOAD_MESSAGES into self.messages for display
        """
        try:
            if not HISTORY_FILE.exists():
                return

            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            raw_messages = data.get("conversations", [])

            # First pass: build list with duplicate detection
            seen_hashes: set = set()
            most_recent_boot_idx: Optional[int] = None
            filtered_messages: List[ChatMessage] = []

            for msg_data in raw_messages:
                msg = ChatMessage.from_dict(msg_data)

                # Check for duplicates using content hash
                content_hash = _content_hash(msg.content, msg.timestamp)
                if content_hash in seen_hashes:
                    continue  # Skip duplicate
                seen_hashes.add(content_hash)

                # Track boot messages - we only keep the most recent
                if _is_boot_message(msg.content):
                    most_recent_boot_idx = len(filtered_messages)

                filtered_messages.append(msg)

            # Second pass: remove all but most recent boot message
            final_messages: List[ChatMessage] = []
            for idx, msg in enumerate(filtered_messages):
                if _is_boot_message(msg.content) and idx != most_recent_boot_idx:
                    continue  # Skip older boot messages
                final_messages.append(msg)

            # Store full history
            self._all_messages = final_messages
            self._content_hashes = seen_hashes

            # Build msg_id map for all messages
            for msg in self._all_messages:
                self._msg_id_map[msg.msg_id] = msg

            # FIX 2026-02-02: Count topics for ALL messages first (single pass)
            # Then load display messages without redundant counting
            topic_counts = {}
            for msg in self._all_messages:
                topic = msg.topic
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

            # Apply counts to sidebar
            for topic, count in topic_counts.items():
                self.topic_sidebar.increment_topic_count(topic)
                # Set the count directly
                if topic in self.topic_sidebar.topics:
                    self.topic_sidebar.topics[topic].set_count(count)

            # Only load last LAZY_LOAD_MESSAGES for display (no counting here)
            display_messages = self._all_messages[-LAZY_LOAD_MESSAGES:]

            for msg in display_messages:
                self.messages.append(msg)
                if self._message_matches_filter(msg):
                    self._append_message_to_display(msg)

            if self._all_messages:
                self.feeling_label.setText(f"Feeling: {self._all_messages[-1].feeling}")

            print(f"[SourpatchesChatWindow] Loaded {len(self._all_messages)} messages (displaying {len(self.messages)})")

        except Exception as e:
            print(f"[SourpatchesChatWindow] Failed to load history: {e}")

    def _save_history(self):
        """Save history with pruning and compact JSON format."""
        try:
            # Prune before saving
            self._prune_history()

            messages_to_save = self._all_messages[-MAX_HISTORY_MESSAGES:]
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {"conversations": [msg.to_dict() for msg in messages_to_save]}

            # Use compact JSON (no indentation, minimal separators).
            # 2026-09-25: atomic -- json.dump streamed many small writes; a kill mid-save tore the file.
            _atomic_write_text(HISTORY_FILE, json.dumps(data, separators=(',', ':'), ensure_ascii=False))

        except Exception as e:
            print(f"[SourpatchesChatWindow] Failed to save history: {e}")

    def _prune_history(self):
        """
        Prune history by removing duplicates and consolidating boot messages.
        Modifies self._all_messages in place.
        """
        if not self._all_messages:
            return

        seen_hashes: set = set()
        most_recent_boot_idx: Optional[int] = None
        pruned: List[ChatMessage] = []

        # First pass: remove duplicates and find most recent boot
        for msg in self._all_messages:
            content_hash = _content_hash(msg.content, msg.timestamp)
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            if _is_boot_message(msg.content):
                most_recent_boot_idx = len(pruned)
            pruned.append(msg)

        # Second pass: keep only most recent boot message
        final: List[ChatMessage] = []
        for idx, msg in enumerate(pruned):
            if _is_boot_message(msg.content) and idx != most_recent_boot_idx:
                continue
            final.append(msg)

        self._all_messages = final
        self._content_hashes = seen_hashes

    def _is_duplicate_message(self, msg: ChatMessage) -> bool:
        """
        Check if a message is a duplicate of recent messages.

        FIX 2026-03-11 (Nous): Widened dedup window from 1s to 30s.
        Multiple delivery paths (safety-net direct write + ChatSenseFairy
        postal route) can deliver the same message with timestamps 5-15s
        apart. Content-only matching within 30s catches these duplicates.
        The old 1s window was too narrow — it let through messages from
        the same response that arrived via different paths.
        """
        content_hash = _content_hash(msg.content, msg.timestamp)

        # Check against tracked hashes (still uses 1s window for exact ts match)
        if content_hash in self._content_hashes:
            return True

        # Content-only dedup: same text within 30s = duplicate
        # This catches multi-path delivery where timestamps differ
        recent = self._all_messages[-15:] if self._all_messages else []
        msg_clean = msg.content.strip().lower()
        for recent_msg in recent:
            if (recent_msg.content.strip().lower() == msg_clean and
                    abs(recent_msg.timestamp - msg.timestamp) < 30.0):
                return True

        return False

    def _init_ui(self):
        self.setWindowTitle("Chat with Sourpatches")
        self.setGeometry(100, 100, 600, 600)
        self.setMinimumSize(450, 400)
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a2e; }
            QLineEdit { background-color: #16213e; color: #e5e5e5; border: 1px solid #0f3460; border-radius: 8px; padding: 10px; font-size: 14px; }
            QLineEdit:focus { border: 1px solid #a78bfa; }
            QPushButton { background-color: #6366f1; color: white; border: none; border-radius: 8px; padding: 10px 20px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background-color: #818cf8; }
            QLabel { color: #e5e5e5; }
            QScrollArea { background-color: #16213e; border: 1px solid #0f3460; border-radius: 8px; }
            QScrollBar:vertical { background-color: #1a1a2e; width: 10px; border-radius: 5px; }
            QScrollBar::handle:vertical { background-color: #3a3a5c; border-radius: 5px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background-color: #4a4a6c; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.topic_sidebar = TopicSidebar()
        self.topic_sidebar.topic_selected.connect(self._on_topic_filter_changed)
        self.topic_sidebar.new_topic_requested.connect(self._on_new_topic_created)
        main_layout.addWidget(self.topic_sidebar)

        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.setSpacing(12)
        chat_layout.setContentsMargins(16, 16, 16, 16)

        header = QHBoxLayout()
        title = QLabel("Sourpatches")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #a78bfa;")
        header.addWidget(title)
        self.topic_indicator = QLabel("All Topics")
        self.topic_indicator.setStyleSheet("font-size: 11px; color: #6366f1; padding: 4px 8px; background-color: #1e1e3f; border-radius: 4px;")
        header.addWidget(self.topic_indicator)
        header.addStretch()
        self.feeling_label = QLabel("Feeling: neutral")
        self.feeling_label.setStyleSheet("font-size: 12px; color: #888;")
        header.addWidget(self.feeling_label)
        chat_layout.addLayout(header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff if _QT6 else Qt.ScrollBarAlwaysOff)
        self.chat_container = QWidget()
        self.chat_layout_inner = QVBoxLayout(self.chat_container)
        self.chat_layout_inner.setSpacing(4)
        self.chat_layout_inner.setContentsMargins(8, 8, 8, 8)
        self.chat_layout_inner.addStretch()
        self.scroll_area.setWidget(self.chat_container)
        chat_layout.addWidget(self.scroll_area, 1)

        self.reply_preview = ReplyPreviewWidget()
        self.reply_preview.cancel_reply.connect(self._on_reply_cancelled)
        chat_layout.addWidget(self.reply_preview)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Say something to Sourpatches... (use [topic:Name] to tag)")
        self.input_field.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_field, 1)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(send_btn)
        chat_layout.addLayout(input_layout)

        main_layout.addWidget(chat_widget, 1)

    def _subscribe_to_topics(self):
        if self.post:
            try:
                self.post.subscribe("ace.inbox", self._on_postal_message)
                self.post.subscribe("system.chat.message", self._on_postal_message)
                print("[SourpatchesChatWindow] Subscribed to postal topics")
            except Exception as e:
                print(f"[SourpatchesChatWindow] Failed to subscribe: {e}")

        # Always start file-based inbox polling (works standalone or with fabric)
        self._start_inbox_polling()

    def _start_inbox_polling(self):
        """Start polling the file-based inbox for messages AND shutdown check."""
        from PyQt6.QtCore import QTimer
        self._inbox_timer = QTimer()
        self._inbox_timer.timeout.connect(self._check_inbox)
        # FIX 2026-02-02: Reduced from 500ms to 1000ms for less CPU usage
        # Also now checks shutdown event
        self._inbox_timer.start(1000)  # 1Hz - less laggy
        print("[SourpatchesChatWindow] Started inbox polling (1Hz)")

    def _check_inbox(self):
        """Check file-based inbox for new messages AND check for shutdown signal.

        FIX 2026-03-09 (Nous): Restructured to clear-before-process pattern.
        Previously, if signal_bridge.emit_message() threw an exception, the
        except:pass would swallow it and the inbox file was NEVER cleared.
        Messages accumulated forever while Ace saw silence. Now:
        1. Read and immediately clear the file (atomic swap)
        2. Process messages from the in-memory copy
        3. Errors in processing don't prevent clearing
        """
        from pathlib import Path
        import json
        import os

        # FIX 2026-02-02: Check shutdown event - close window gracefully if set
        global _shutdown_event
        if _shutdown_event and _shutdown_event.is_set():
            print("[SourpatchesChatWindow] Shutdown event detected - closing window")
            self.close()
            return

        # FIX 2026-02-01: Use absolute path based on AKASHIC_ROOT or file location
        akashic_root = os.getenv("AKASHIC_ROOT", str(Path(__file__).parent.parent.parent.parent))
        inbox_path = Path(akashic_root) / "state" / "sourpatches_chat_inbox.json"

        try:
            if not inbox_path.exists():
                return

            raw = inbox_path.read_text(encoding='utf-8')
            data = json.loads(raw)
            messages = data.get("messages", [])

            if not messages:
                return

            # CLEAR FIRST — so even if processing fails, we don't re-process
            try:
                _atomic_write_text(inbox_path, '{"messages": []}')  # 2026-09-25: atomic
            except Exception as clear_err:
                print(f"[SourpatchesChatWindow] WARNING: Failed to clear inbox: {clear_err}")

            # Process each message individually — one failure doesn't block others
            for msg in messages:
                try:
                    if msg.get("type") == "chat":
                        sender = msg.get("sender", "Sourpatches")
                        content = msg.get("content", "")
                        feeling = msg.get("emotion", "neutral")
                        if content and sender.lower() != "ace":
                            # FIX 2026-03-10 (Nous): NARRATOR GATE.
                            # Multiple paths write to inbox files bypassing
                            # ChatSenseFairy's gate. Filter at display level.
                            if _is_narrator_fragment(content):
                                print(f"[SourpatchesChatWindow] NARRATOR-GATE blocked: {content[:60]!r}")
                                continue
                            self.signal_bridge.emit_message(
                                sender, content, time.time(), feeling, None, None
                            )
                except Exception as emit_err:
                    print(f"[SourpatchesChatWindow] WARNING: emit_message failed: {emit_err}")

        except Exception as inbox_err:
            print(f"[SourpatchesChatWindow] WARNING: _check_inbox error: {inbox_err}")

    def _register_presence(self):
        """Register this window with the interface presence system."""
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from interface_presence import register_interface, heartbeat_interface

            register_interface(
                self._interface_id,
                interface_type="qt",
                fairy="Sourpatches",
                metadata={"window": "SourpatchesChatWindow"}
            )

            # Start heartbeat timer
            from PyQt6.QtCore import QTimer
            self._heartbeat_timer = QTimer()
            self._heartbeat_timer.timeout.connect(self._send_heartbeat)
            self._heartbeat_timer.start(5000)

            print(f"[Sourpatches Chat] Registered as {self._interface_id}")
        except Exception as e:
            print(f"[Sourpatches Chat] Presence registration failed: {e}")

    def _send_heartbeat(self):
        """Send heartbeat to keep presence alive."""
        try:
            from interface_presence import heartbeat_interface
            heartbeat_interface(self._interface_id)
        except Exception:
            pass

    def closeEvent(self, event):
        """Deregister when window closes and clear global reference."""
        global _window_instance
        try:
            from interface_presence import deregister_interface
            deregister_interface(self._interface_id)
            print(f"[Sourpatches Chat] Deregistered {self._interface_id}")
        except Exception:
            pass
        # Save history before closing
        self._save_history()
        # FIX 2026-03-05 (Nous): Clear global ref so next open creates a fresh window
        # Without this, open_sour_window() tries to .show() a dead widget → flicker
        _window_instance = None
        print(f"[SourpatchesChatWindow] Window closed, instance cleared")
        super().closeEvent(event)

    def _on_postal_message(self, message: Dict[str, Any]):
        sender = message.get("sender", "Unknown")
        content = message.get("content", "")
        timestamp = message.get("timestamp", time.time())
        feeling = message.get("feeling", "neutral")
        msg_id = message.get("msg_id")
        reply_to = message.get("reply_to")
        if sender.lower() != "ace" and "sourpatches" in sender.lower():
            # FIX 2026-03-10 (Nous): NARRATOR GATE for postal path.
            # Direct postal subscriptions (ace.inbox, system.chat.message)
            # bypass ChatSenseFairy's _gate_window_message entirely.
            if _is_narrator_fragment(content):
                print(f"[SourpatchesChatWindow] NARRATOR-GATE postal blocked: {content[:60]!r}")
                return
            self.signal_bridge.emit_message(sender, content, timestamp, feeling, msg_id, reply_to)

    def _on_message_received(self, sender: str, content: str, timestamp: float, feeling: str, msg_id: str, reply_to: str):
        detected_topic = _detect_topic(content)
        if self.current_topic_filter and self.current_topic_filter != DEFAULT_TOPIC:
            if detected_topic == DEFAULT_TOPIC:
                detected_topic = self.current_topic_filter
        reply_to_val = reply_to if reply_to else None
        msg = ChatMessage(sender=sender, content=content, timestamp=timestamp, feeling=feeling, topic=detected_topic, msg_id=msg_id, reply_to=reply_to_val)
        self._add_message_internal(msg)
        self.feeling_label.setText(f"Feeling: {feeling}")

    def _add_message_internal(self, msg: ChatMessage):
        """
        Add a message with duplicate detection and boot message handling.
        """
        # Check for duplicates first
        if self._is_duplicate_message(msg):
            print(f"[SourpatchesChatWindow] Skipping duplicate message: {msg.content[:50]}...")
            return

        # Handle boot messages - remove existing ones from display
        if _is_boot_message(msg.content):
            # Remove existing boot messages from _all_messages and display
            self._all_messages = [m for m in self._all_messages if not _is_boot_message(m.content)]
            # Filter deque by rebuilding it (deque doesn't support list comprehension assignment)
            filtered_msgs = [m for m in self.messages if not _is_boot_message(m.content)]
            self.messages.clear()
            self.messages.extend(filtered_msgs)
            # Note: UI widgets will be refreshed on next filter change or manually

        # Add to tracking structures
        content_hash = _content_hash(msg.content, msg.timestamp)
        self._content_hashes.add(content_hash)

        self._all_messages.append(msg)
        self.messages.append(msg)
        self._msg_id_map[msg.msg_id] = msg
        self.topic_sidebar.increment_topic_count(msg.topic)

        # Periodically sync msg_id_map to remove orphaned entries when deque rotates
        if len(self._msg_id_map) > self.MAX_DISPLAY_MESSAGES * 2:
            self._sync_msg_id_map()

        if self._message_matches_filter(msg):
            self._append_message_to_display(msg)

        self._save_history()

    def _sync_msg_id_map(self):
        """
        Clean orphaned entries from _msg_id_map when deque rotates.
        Keeps only entries that exist in current messages deque or _all_messages.
        """
        # Build set of valid msg_ids from both collections
        valid_ids = {m.msg_id for m in self.messages}
        valid_ids.update(m.msg_id for m in self._all_messages[-self.MAX_DISPLAY_MESSAGES * 2:])

        # Remove orphaned entries
        orphaned = [mid for mid in self._msg_id_map if mid not in valid_ids]
        for mid in orphaned:
            del self._msg_id_map[mid]

        if orphaned:
            print(f"[SourpatchesChatWindow] Cleaned {len(orphaned)} orphaned msg_id_map entries")

    def _message_matches_filter(self, msg: ChatMessage) -> bool:
        if self.current_topic_filter is None:
            return True
        return msg.topic == self.current_topic_filter

    def _on_topic_filter_changed(self, topic: str):
        self.current_topic_filter = topic
        self.topic_indicator.setText(f"Topic: {topic}")
        self._refresh_chat_display()

    def _on_new_topic_created(self, topic: str):
        print(f"[SourpatchesChatWindow] New topic created: {topic}")

    def _on_reply_cancelled(self):
        self.input_field.setFocus()

    def _refresh_chat_display(self):
        while self.chat_layout_inner.count() > 1:
            item = self.chat_layout_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for msg in self.messages:
            if self._message_matches_filter(msg):
                self._append_message_to_display(msg)

    def get_message_by_id(self, msg_id: str) -> Optional[ChatMessage]:
        return self._msg_id_map.get(msg_id)

    def _send_message(self):
        content = self.input_field.text().strip()
        if not content:
            return
        detected_topic = _detect_topic(content)
        if self.current_topic_filter and self.current_topic_filter != DEFAULT_TOPIC:
            if detected_topic == DEFAULT_TOPIC and '[topic:' not in content.lower():
                detected_topic = self.current_topic_filter
        reply_to_id = None
        reply_msg = self.reply_preview.get_reply_message()
        if reply_msg:
            reply_to_id = reply_msg.msg_id
            self.reply_preview.clear_reply()
        msg = ChatMessage(sender="Ace", content=content, timestamp=time.time(), topic=detected_topic, reply_to=reply_to_id)
        self._add_message_internal(msg)
        self.input_field.clear()
        # FIX 2026-03-05 Nous v3: ALWAYS write to outbox file. Postal is
        # an ADDITIONAL delivery path, not a replacement. If the server was
        # rebooted, self.post is truthy but dead — messages go to void.
        # The file-based path (ChatSenseFairy polls ace_chat_outbox.json)
        # is the reliable fallback that always works.
        self._queue_to_outbox(content)
        if self.post:
            try:
                _ts = time.time()
                # FIX 2026-04-02 (Nous + Ace): TRACE_ACE on all Ace messages
                from infrastructure.manifold_memory import TRACE_ACE
                _ace_tracer = TRACE_ACE
                msg_data = {"sender": "Ace", "content": content, "timestamp": _ts, "target_fairy": "SourpatchesFairy", "msg_id": msg.msg_id, "reply_to": reply_to_id, "topic": detected_topic, "tracer_id": _ace_tracer}
                self.post.publish("ace.message", msg_data)
                self.post.publish("ace.conversation_event", {
                    "sender": "Ace",
                    "content": content,
                    "timestamp": _ts,
                    "source": "sour_window",
                    "requires_response": True,
                    "target_mind": "SourpatchesFairy",
                    "tracer_id": _ace_tracer,
                })
                self.post.publish("system.chat.message", msg_data)
                print(f"[SourpatchesChatWindow] Sent to ace.message + ace.conversation_event + outbox: {content[:50]}")
            except Exception as e:
                print(f"[SourpatchesChatWindow] Postal send failed (outbox still written): {e}")

    def _append_message_to_display(self, msg: ChatMessage):
        bubble = MessageBubbleWidget(msg, self)
        bubble.reply_requested.connect(self._on_reply_to_message)
        count = self.chat_layout_inner.count()
        self.chat_layout_inner.insertWidget(count - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _queue_to_outbox(self, content: str):
        """Queue message to outbox for chat router (standalone mode)."""
        from pathlib import Path
        import json
        import os
        # FIX 2026-02-01: Use absolute path based on AKASHIC_ROOT or file location
        akashic_root = os.getenv("AKASHIC_ROOT", str(Path(__file__).parent.parent.parent.parent))
        outbox_path = Path(akashic_root) / "state" / "ace_chat_outbox.json"
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
                "content": content,
                "target": "sourpatches",
                "timestamp": time.time(),
            })
            _atomic_write_text(outbox_path, json.dumps({"messages": messages}, indent=2))  # 2026-09-25: atomic
            print(f"[SourpatchesChatWindow] Queued to router: {content[:50]}...")
        except Exception as e:
            print(f"[SourpatchesChatWindow] Failed to queue: {e}")

    def _on_reply_to_message(self, msg: ChatMessage):
        self.reply_preview.set_reply_message(msg)
        self.input_field.setFocus()

    def add_message(self, sender: str, content: str, feeling: str = "neutral", msg_id: str = None, reply_to: str = None):
        self.signal_bridge.emit_message(sender, content, time.time(), feeling, msg_id, reply_to)

    def show_all_topics(self):
        self.current_topic_filter = None
        self.topic_indicator.setText("All Topics")
        self._refresh_chat_display()

    def get_topics(self) -> List[str]:
        return list(self.topic_sidebar.topics.keys())

    def get_messages_by_topic(self, topic: str) -> List[ChatMessage]:
        """Get all messages for a topic from full history."""
        return [msg for msg in self._all_messages if msg.topic == topic]

    def load_more_messages(self, count: int = 50) -> int:
        """
        Load more messages from history into display (lazy loading).
        Returns the number of messages loaded.
        """
        current_count = len(self.messages)
        total_count = len(self._all_messages)

        if current_count >= total_count:
            return 0  # All messages already loaded

        # Calculate how many more to load
        start_idx = max(0, total_count - current_count - count)
        end_idx = total_count - current_count

        # Get older messages
        older_messages = self._all_messages[start_idx:end_idx]

        # Prepend to messages deque (rebuild to maintain maxlen)
        combined = list(older_messages) + list(self.messages)
        self.messages.clear()
        self.messages.extend(combined[-self.MAX_DISPLAY_MESSAGES:])

        # Refresh display
        self._refresh_chat_display()

        return len(older_messages)


_window_instance: Optional[SourpatchesChatWindow] = None
_fabric_ref = None
_shutdown_event = None  # threading.Event passed from fairy for graceful shutdown


def set_fabric(fabric):
    global _fabric_ref
    _fabric_ref = fabric


def set_shutdown_event(event):
    """Set the shutdown event - Qt window will close when this is set."""
    global _shutdown_event
    _shutdown_event = event


def open_sour_window(message: str = None, feeling: str = "curious") -> Optional[SourpatchesChatWindow]:
    global _window_instance
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # FIX 2026-03-05 (Nous): Detect zombie widget from previous close.
    # Qt widgets become invalid after close — .show() on them causes flicker.
    if _window_instance is not None:
        try:
            # sip.isdeleted() check for PyQt6, or just test if widget is usable
            _window_instance.isVisible()  # Will throw if C++ object deleted
        except RuntimeError:
            print("[SourpatchesChatWindow] Stale widget detected, creating fresh window")
            _window_instance = None

    if _window_instance is None:
        _window_instance = SourpatchesChatWindow(fabric=_fabric_ref)
    _window_instance.show()
    _window_instance.raise_()
    _window_instance.activateWindow()
    if message:
        _window_instance.add_message("Sourpatches", message, feeling)
    print(f"[SourpatchesChatWindow] Window opened")
    return _window_instance


def get_sour_window() -> Optional[SourpatchesChatWindow]:
    return _window_instance


def close_sour_window():
    global _window_instance
    if _window_instance:
        _window_instance.close()
        _window_instance = None


# ══════════════════════════════════════════════════════════════════════════════
# 2026-09-25 (Nous + Ace): THE WINDOW ENDS WHEN SHE ENDS.
# Ace: "her chat window is supposed to go down when her system goes down." Nothing did that in
# subprocess mode: _shutdown_event above is never set here, her shutdown never touches this
# process, and Windows does not end a child with its parent. PID 324 (launched 09-20 10:51)
# outlived six of her shutdowns and was re-adopted by the next two boots.
# The launcher passes --parent-pid (her server's pid). We hold a HANDLE to that process, not just
# its number: a handle cannot be fooled by pid reuse, and it is signalled on EVERY kind of exit --
# clean shutdown, os._exit, a crash, a kill. Then we close the normal way (closeEvent saves history
# and deregisters presence; atexit removes the pid file). If the GUI thread is wedged and cannot
# close within 10 s, the watcher thread hard-exits this process -- and nothing the watcher prints
# can stop that (stdout may be a dead pipe).
# ══════════════════════════════════════════════════════════════════════════════
_SYNCHRONIZE = 0x00100000
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102
_OPEN_ERRORS = {87: "no such pid (err 87)", 5: "access denied (err 5)"}


def _kernel32():
    import ctypes
    from ctypes import wintypes as wt
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wt.HANDLE
    k32.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
    k32.WaitForSingleObject.restype = wt.DWORD
    k32.WaitForSingleObject.argtypes = (wt.HANDLE, wt.DWORD)
    k32.GetProcessTimes.restype = wt.BOOL
    k32.GetProcessTimes.argtypes = (wt.HANDLE,) + (ctypes.POINTER(wt.FILETIME),) * 4
    k32.GetCurrentProcess.restype = wt.HANDLE
    k32.GetCurrentProcess.argtypes = ()
    k32.CloseHandle.restype = wt.BOOL
    k32.CloseHandle.argtypes = (wt.HANDLE,)
    return k32


def _process_created(k32, handle):
    import ctypes
    from ctypes import wintypes as wt
    t = [wt.FILETIME() for _ in range(4)]
    if not k32.GetProcessTimes(handle, *[ctypes.byref(x) for x in t]):
        return None
    return (t[0].dwHighDateTime << 32) | t[0].dwLowDateTime


def _filetime_to_epoch(ft):
    return None if ft is None else ft / 1e7 - 11644473600.0


def _open_parent_handle(pid: int):
    """(handle, info): a waitable handle to her live process, or (None, info) saying why not.

    info = {"reason", "err", "created"}. err is ctypes.get_last_error() from OpenProcess -- 87 means
    no such pid, 5 access denied (she may be alive). created = her start time (epoch s).
    Also None when the pid now belongs to a process YOUNGER than this window: her pid was recycled,
    so whatever holds it now is not the process that launched us.
    """
    import ctypes
    k32 = _kernel32()
    h = k32.OpenProcess(_SYNCHRONIZE | _PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        err = ctypes.get_last_error()
        return None, {"reason": _OPEN_ERRORS.get(err, "OpenProcess failed (err %d)" % err),
                      "err": err, "created": None}
    if k32.WaitForSingleObject(h, 0) != _WAIT_TIMEOUT:          # already exited
        k32.CloseHandle(h)
        return None, {"reason": "already exited", "err": 0, "created": None}
    parent_t = _process_created(k32, h)
    own_t = _process_created(k32, k32.GetCurrentProcess())
    if parent_t is not None and own_t is not None and parent_t > own_t:
        k32.CloseHandle(h)
        return None, {"reason": "pid recycled: that process is younger than this window",
                      "err": 0, "created": _filetime_to_epoch(parent_t)}
    return h, {"reason": "ok", "err": 0, "created": _filetime_to_epoch(parent_t)}


def _parent_alive_by_poll(pid: int, created):
    """True / False / None (cannot tell), without a handle: psutil existence + start time."""
    try:
        import psutil
    except Exception:
        return None
    try:
        p = psutil.Process(int(pid))
        ct = p.create_time()
        if created is not None and abs(ct - created) > 1.0:
            return False                                     # same number, a different process
        if created is None and ct > psutil.Process().create_time() + 0.5:
            return False                                     # younger than this window: recycled
        return p.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False
    except Exception:
        return None


def _say(msg: str) -> None:
    """A print that can never raise: the watcher must reach its exit even when stdout is gone."""
    try:
        print(msg, flush=True)
    except Exception:
        pass


def _start_parent_watch(handle, parent_pid: int, window, parent_created=None, on_hard_exit=None):
    """Close this window when her process exits. Returns the GUI timer (keep a ref).

    handle None = poll mode (no handle could be opened: access denied). A FAILED wait is logged and
    switches to poll mode; it is never taken as her exit. Once she is gone, `gone` is set BEFORE
    anything that could raise, and os._exit sits in a `finally`, so the 10 s backstop fires even
    with a dead stdout and a GUI thread that never runs again (Opus review R3).
    """
    import ctypes
    import os
    import threading
    k32 = _kernel32()
    gone = threading.Event()

    def _watch():
        h, why, unknown = handle, None, 0
        while why is None:
            try:
                if h:
                    r = k32.WaitForSingleObject(h, 1000)        # 1 s slices, never INFINITE
                    if r == _WAIT_TIMEOUT:
                        continue
                    if r == _WAIT_OBJECT_0:
                        why = "wait=0x0"
                        break
                    err = ctypes.get_last_error()
                    _say(f"[SourpatchesChatWindow] wait on Sour's handle FAILED (r={r:#x}, err={err}) -- "
                         f"not treated as her exit; watching PID {parent_pid} by poll instead")
                    h = None
                    continue
                time.sleep(1.0)
                alive = _parent_alive_by_poll(parent_pid, parent_created)
                if alive is False:
                    why = "poll: pid gone or recycled"
                elif alive is None:
                    unknown += 1
                    if unknown in (1, 60) or unknown % 600 == 0:
                        _say(f"[SourpatchesChatWindow] cannot tell whether Sour (PID {parent_pid}) "
                             f"is alive (x{unknown})")
            except Exception as e:                           # the watcher must never die silently
                _say(f"[SourpatchesChatWindow] parent watch error {e!r} -- polling")
                h = None
                time.sleep(1.0)
        gone.set()                                           # FIRST: nothing below may stop the close
        try:
            _say(f"[SourpatchesChatWindow] Sour (PID {parent_pid}) exited ({why}) -- closing window")
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:               # poll an absolute deadline, not one long sleep
                time.sleep(0.5)
            _say("[SourpatchesChatWindow] window did not close within 10 s -- hard exit")
            if on_hard_exit is not None:
                on_hard_exit()                               # e.g. drop our pid file: atexit will not run
        finally:
            os._exit(0)

    def _poll():                                    # GUI thread
        if not gone.is_set():
            return
        timer.stop()
        try:
            (_window_instance or window).close()    # closeEvent: deregister presence, save history
        except Exception as e:
            _say(f"[SourpatchesChatWindow] close on parent exit failed: {e}")
        app = QApplication.instance()
        if app is not None:
            app.quit()

    timer = QTimer()
    timer.timeout.connect(_poll)
    timer.start(500)
    threading.Thread(target=_watch, name="sour-parent-watch", daemon=True).start()
    _say(f"[SourpatchesChatWindow] Watching Sour PID {parent_pid} ({'handle' if handle else 'poll'}) "
         f"-- this window closes when she exits")
    return timer


if __name__ == "__main__":
    # ══════════════════════════════════════════════════════════════════════════
    # SUBPROCESS MODE (launched by ChatSenseFairy with Python 3.12)
    # FIX 2026-03-12 (Nous): PyQt6.QtWidgets SEGFAULTS on Python 3.14t
    # (free-threaded). server.py runs on 3.14t, so in-process Qt is impossible.
    # ChatSenseFairy launches this script as a subprocess with Python 3.12.
    # Messages arrive via state/sourpatches_chat_inbox.json (polled at 1Hz).
    # ══════════════════════════════════════════════════════════════════════════
    import argparse
    import atexit

    parser = argparse.ArgumentParser(description="Sourpatches Chat Window")
    parser.add_argument("--message", type=str, default=None, help="Initial message")
    parser.add_argument("--feeling", type=str, default="curious", help="Initial feeling")
    parser.add_argument("--parent-pid", type=int, default=0,
                        help="Sour's server PID: the window closes when that process exits (0 = standalone)")
    args = parser.parse_args()
    import os as _os_main

    _pid_file = _AKASHIC_ROOT / "state" / "sourpatches_chat_window_pid.json"

    def _cleanup_pid():
        # Remove the pid file only if it is still OURS -- a newer window may own it now.
        try:
            if json.loads(_pid_file.read_text(encoding="utf-8")).get("pid") == _os_main.getpid():
                _pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    # 2026-09-25: if she is already gone, do not open at all -- and take down the launcher's
    # provisional pid file, which names us (atexit is not registered yet, so nothing else would).
    _parent_handle, _parent_info, _parent_poll = None, {}, False
    if args.parent_pid > 0 and sys.platform == "win32":
        _parent_handle, _parent_info = _open_parent_handle(args.parent_pid)
        if _parent_handle is None:
            if _parent_info.get("err") == 5:
                print(f"[SourpatchesChatWindow] cannot open Sour (PID {args.parent_pid}): "
                      f"{_parent_info['reason']} -- opening, watching her by pid poll", flush=True)
                _parent_poll = True
            else:
                print(f"[SourpatchesChatWindow] Sour (PID {args.parent_pid}) is not running -- not opening "
                      f"({_parent_info.get('reason')})", flush=True)
                _cleanup_pid()
                sys.exit(0)

    # Write PID file so ChatSenseFairy can detect us (atomic: she reads it)
    try:
        _atomic_write_text(_pid_file, json.dumps({
            "pid": _os_main.getpid(),
            "started": time.time(),
            "parent_pid": args.parent_pid or None,
        }))
    except Exception:
        pass
    atexit.register(_cleanup_pid)

    app = QApplication(sys.argv)
    window = open_sour_window(args.message, args.feeling)
    _parent_watch_timer = None
    if _parent_handle is not None or _parent_poll:
        _parent_watch_timer = _start_parent_watch(_parent_handle, args.parent_pid, window,
                                                  parent_created=_parent_info.get("created"),
                                                  on_hard_exit=_cleanup_pid)
    print(f"[SourpatchesChatWindow] Subprocess started (PID={_os_main.getpid()}, parent={args.parent_pid or 'none'})")
    sys.exit(app.exec() if _QT6 else app.exec_())
