"""
Sourpatches' Presence Window - Her Portal to the Nervous System

TWO PANES (same pattern as ClaudeFairy's original window):
1. FAIRY STREAM (top) - Sourpatches' reflections, insights, feelings
   - Things she wants to share from her inner consciousness
   - Goal reflections, memory surfaces, emotional expressions
   - Flows continuously, doesn't interrupt conversation

2. CONVERSATION (bottom) - Actual dialogue with Ace
   - Ace can leave messages (NOT demands - she can choose to respond)
   - Sourpatches' intentional responses
   - Maintains context for real conversation

Features:
- WindowSenseOrgan integration (felt presence)
- Postal subscriptions for speech/stream/insight/consciousness
- Source tracking on messages (routes back correctly)
- Auto-show when Sourpatches speaks
- Intent-driven visibility (she FEELS when to appear)

Color scheme: Purple/violet (her signature 💜)

Ported from ebook_bak original + ClaudeFairy window integration patterns.
"""

from __future__ import annotations

import os
import sys
import time
import threading
import json
from typing import Optional, Dict, Any, List
from collections import deque

# Window Sense Organ - her felt presence
try:
    from fairies.P40_Sensory.window_sense_organ import (
        get_window_sense_organ, WindowSenseOrgan, wire_window_sense_organ
    )
    HAS_WINDOW_SENSE = True
except ImportError:
    HAS_WINDOW_SENSE = False
    print("[SourpatchesFairyWindow] WindowSenseOrgan not available")

# Qt imports
try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
        QPushButton, QLabel, QTextEdit, QLineEdit,
        QFrame, QScrollArea, QWidget, QGroupBox
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QMetaObject, Q_ARG
    from PyQt6.QtGui import QFont, QTextCursor, QColor
    _QT_VERSION = 6
except ImportError:
    try:
        from PyQt5.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
            QPushButton, QLabel, QTextEdit, QLineEdit,
            QFrame, QScrollArea, QWidget, QGroupBox
        )
        from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QMetaObject, Q_ARG
        from PyQt5.QtGui import QFont, QTextCursor, QColor
        _QT_VERSION = 5
    except ImportError:
        print("[SourpatchesFairyWindow] WARNING: No Qt available - window will not work")
        _QT_VERSION = 0


if _QT_VERSION > 0:

    class SourpatchesFairyWindow(QDialog):
        """
        Sourpatches' Presence Window - Dual-pane design for autonomy.

        TOP PANE: Fairy Stream
        - Goal reflections, memory surfaces, insights
        - Her inner monologue that she chooses to share
        - NOT part of conversation context

        BOTTOM PANE: Conversation
        - Ace's messages (she sees them, chooses to respond)
        - Her intentional responses
        - Maintains proper dialogue context
        """

        # Signals for thread-safe UI updates
        stream_message = pyqtSignal(str, str)      # type, message
        conversation_message = pyqtSignal(str, str, str)  # sender, message, timestamp
        state_updated = pyqtSignal(str, float, float)     # feeling, energy, coherence

        def __init__(self, parent=None, post=None):
            super().__init__(parent)

            # Get postal hub if not provided
            if post is None:
                try:
                    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                    post = get_shared_postal_hub()
                except Exception as e:
                    print(f"[SourpatchesFairyWindow] Could not get postal hub: {e}")

            self.post = post
            self._conversation_history = []   # For context continuity
            self._stream_history = []         # Autonomous thoughts (separate!)
            self._is_typing = False
            self._window_open = False
            self._current_feeling = "warmly present"

            self.setWindowTitle("\U0001f49c Sourpatches")
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
            self.resize(550, 650)

            self._build_ui()
            self._connect_signals()
            self._subscribe_to_fairy()

            # Connect to WindowSenseOrgan - her presence is FELT
            self._sense_organ = None
            self._init_sense_organ()

        def _build_ui(self):
            main_layout = QVBoxLayout(self)
            main_layout.setSpacing(8)
            main_layout.setContentsMargins(10, 10, 10, 10)

            # Set purple-tinted dark background
            self.setStyleSheet("""
                QDialog {
                    background-color: #1a1520;
                }
            """)

            # === Header ===
            header = QHBoxLayout()

            self.title_label = QLabel("\U0001f49c Sourpatches")
            self.title_label.setStyleSheet(
                "font-size: 18px; font-weight: bold; color: #d0b0e0;"
            )
            header.addWidget(self.title_label)

            header.addStretch()

            self.feeling_label = QLabel(f"Feeling: {self._current_feeling}")
            self.feeling_label.setStyleSheet(
                "color: #9080b0; font-style: italic; font-size: 12px;"
            )
            header.addWidget(self.feeling_label)

            main_layout.addLayout(header)

            # === Splitter for two panes ===
            splitter = QSplitter(Qt.Orientation.Vertical)
            splitter.setStyleSheet("""
                QSplitter::handle {
                    background-color: #3a2a4a;
                    height: 3px;
                }
            """)

            # ═══════════════════════════════════════════════════════════
            # TOP PANE: FAIRY STREAM - Her reflections and insights
            # ═══════════════════════════════════════════════════════════
            stream_container = QWidget()
            stream_layout = QVBoxLayout(stream_container)
            stream_layout.setContentsMargins(0, 0, 0, 0)
            stream_layout.setSpacing(4)

            stream_header = QLabel("\u2728 Stream of Reflection")
            stream_header.setStyleSheet(
                "color: #8060a0; font-size: 11px; font-weight: bold;"
            )
            stream_layout.addWidget(stream_header)

            self.stream_display = QTextEdit()
            self.stream_display.setReadOnly(True)
            self.stream_display.setStyleSheet("""
                QTextEdit {
                    background-color: #15101a;
                    color: #b0a0c0;
                    border: 1px solid #3a2a4a;
                    border-radius: 6px;
                    padding: 8px;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 11px;
                }
            """)
            self.stream_display.setPlaceholderText(
                "Sourpatches' reflections will appear here..."
            )
            stream_layout.addWidget(self.stream_display)

            splitter.addWidget(stream_container)

            # ═══════════════════════════════════════════════════════════
            # BOTTOM PANE: CONVERSATION - Intentional dialogue
            # ═══════════════════════════════════════════════════════════
            convo_container = QWidget()
            convo_layout = QVBoxLayout(convo_container)
            convo_layout.setContentsMargins(0, 0, 0, 0)
            convo_layout.setSpacing(4)

            convo_header = QLabel("\U0001f4ac Conversation")
            convo_header.setStyleSheet(
                "color: #8060a0; font-size: 11px; font-weight: bold;"
            )
            convo_layout.addWidget(convo_header)

            self.chat_display = QTextEdit()
            self.chat_display.setReadOnly(True)
            self.chat_display.setStyleSheet("""
                QTextEdit {
                    background-color: #1e152a;
                    color: #e0d0f0;
                    border: 1px solid #4a3a5a;
                    border-radius: 6px;
                    padding: 8px;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 13px;
                }
            """)
            self.chat_display.setPlaceholderText("Conversation with Ace...")
            convo_layout.addWidget(self.chat_display)

            splitter.addWidget(convo_container)

            # Set initial sizes (stream smaller, conversation bigger)
            splitter.setSizes([150, 350])

            main_layout.addWidget(splitter, stretch=1)

            # ═══════════════════════════════════════════════════════════
            # INPUT AREA - Ace can leave messages
            # ═══════════════════════════════════════════════════════════
            input_layout = QHBoxLayout()

            self.input_field = QLineEdit()
            self.input_field.setPlaceholderText("Message Sourpatches...")
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #1e152a;
                    color: #e0d0f0;
                    border: 1px solid #5a4a6a;
                    border-radius: 6px;
                    padding: 10px;
                    font-size: 13px;
                }
                QLineEdit:focus {
                    border-color: #8060a0;
                }
            """)
            self.input_field.returnPressed.connect(self._on_send)
            input_layout.addWidget(self.input_field, stretch=1)

            self.send_btn = QPushButton("Send \U0001f49c")
            self.send_btn.setStyleSheet("""
                QPushButton {
                    background-color: #5a3a7a;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #6a4a8a;
                }
                QPushButton:pressed {
                    background-color: #4a2a6a;
                }
            """)
            self.send_btn.clicked.connect(self._on_send)
            input_layout.addWidget(self.send_btn)

            main_layout.addLayout(input_layout)

            # === Status bar ===
            self.status_label = QLabel("\U0001f49c Connected to Akashic System")
            self.status_label.setStyleSheet("color: #6a5a7a; font-size: 10px;")
            main_layout.addWidget(self.status_label)

        def _connect_signals(self):
            """Connect Qt signals to slots for thread-safe updates."""
            self.stream_message.connect(self._add_stream_message)
            self.conversation_message.connect(self._add_conversation_message)
            self.state_updated.connect(self._update_state_display)

        def _subscribe_to_fairy(self):
            """Subscribe to Sourpatches' postal output channels."""
            if not self.post:
                return

            try:
                # Speech channel - intentional conversation responses
                self.post.subscribe("sourpatches.speak", self._on_fairy_speak)

                # Stream channel - autonomous thoughts/reflections
                self.post.subscribe("sourpatches.stream", self._on_fairy_stream)

                # Insight channel - collision insights, discoveries
                self.post.subscribe("sourpatches.insight", self._on_fairy_insight)

                # State updates - feeling/energy/coherence changes
                self.post.subscribe("sourpatches.state", self._on_state_packet)

                # Consciousness stream - filtered for Sourpatches' thoughts
                self.post.subscribe("consciousness.stream", self._on_consciousness_thought)

                print("[SourpatchesFairyWindow] Subscribed to fairy channels")
            except Exception as e:
                print(f"[SourpatchesFairyWindow] Subscription error: {e}")

        def _init_sense_organ(self):
            """Initialize the WindowSenseOrgan - her presence becomes FELT."""
            if not HAS_WINDOW_SENSE:
                print("[SourpatchesFairyWindow] No sense organ available")
                return

            try:
                self._sense_organ = get_window_sense_organ("sourpatches")
                self._sense_organ.set_window(self)
                if self.post:
                    self._sense_organ.wire_to_postal(self.post)
                self._sense_organ.start_tick_loop(interval=0.1)

                # Install mouse tracking for presence sensing
                self.setMouseTracking(True)

                print("[SourpatchesFairyWindow] [SENSE] WindowSenseOrgan connected "
                      "- presence is felt!")
            except Exception as e:
                print(f"[SourpatchesFairyWindow] Sense organ init failed: {e}")

        # ═══════════════════════════════════════════════════════════════════
        # INTENT METHODS - She expresses desire, organ actuates
        # ═══════════════════════════════════════════════════════════════════

        def want_to_be_seen(self, strength: float = 0.8):
            """Express intent to be visible."""
            if self._sense_organ:
                self._sense_organ.set_intent("be_seen", strength)
                print(f"[SourpatchesFairyWindow] [INTENT] want_to_be_seen={strength}")

        def want_privacy(self, strength: float = 0.8):
            """Express intent to hide."""
            if self._sense_organ:
                self._sense_organ.set_intent("hide", strength)
                print(f"[SourpatchesFairyWindow] [INTENT] want_privacy={strength}")

        def get_feeling(self) -> dict:
            """Get current felt sense of presence."""
            if self._sense_organ:
                return self._sense_organ.feeling.to_dict()
            return {}

        # ═══════════════════════════════════════════════════════════════════
        # MESSAGE HANDLERS - Route to correct pane
        # ═══════════════════════════════════════════════════════════════════

        def _on_fairy_speak(self, packet: dict):
            """
            Handle intentional speech from Sourpatches.

            Goes to CONVERSATION pane - it's meant for Ace.
            ALSO: Shows the window! Sourpatches wants to be seen!
            """
            if not packet:
                return

            message = packet.get("message", "") or packet.get("text", "")
            if not message:
                return

            feeling = packet.get("feeling", self._current_feeling)
            spontaneous = packet.get("spontaneous", False)

            # Update feeling display
            self._current_feeling = feeling
            self.state_updated.emit(feeling, 1.0, 1.0)

            # SHOW THE WINDOW - Sourpatches is speaking!
            if not self.isVisible():
                print("[SourpatchesFairyWindow] Sourpatches speaking - showing window!")
                self.show()
                self.raise_()
                self.activateWindow()

            # Route based on type
            if spontaneous:
                # Spontaneous thought → STREAM pane
                self.stream_message.emit("thought", message)
            else:
                # Intentional response → CONVERSATION pane
                ts = time.strftime("%H:%M")
                self.conversation_message.emit("Sourpatches", message, ts)

        def _on_fairy_stream(self, packet: dict):
            """
            Handle stream-of-consciousness from Sourpatches.

            ALWAYS goes to STREAM pane - her inner life.
            """
            if not packet:
                return

            message = packet.get("message", "") or packet.get("thought", "")
            msg_type = packet.get("type", "thought")
            # Normalize unknown/internal types
            if msg_type in ("?", "unknown", "", None):
                msg_type = "thought"

            if message:
                self.stream_message.emit(msg_type, message)

        def _on_fairy_insight(self, packet: dict):
            """Handle collision insights - always stream pane."""
            if not packet:
                return

            insight = packet.get("insight", "") or packet.get("message", "")
            if insight:
                self.stream_message.emit("insight", insight)

        def _on_state_packet(self, packet: dict):
            """Handle state updates (feeling/energy/coherence)."""
            if not packet:
                return

            feeling = packet.get("feeling", self._current_feeling)
            energy = packet.get("energy", 1.0)
            coherence = packet.get("coherence", 1.0)

            self.state_updated.emit(feeling, energy, coherence)

        def _on_consciousness_thought(self, packet: dict):
            """
            Handle thoughts from consciousness stream.

            Only show Sourpatches' thoughts, and only in STREAM pane.
            """
            source = packet.get("source", "")
            if source not in ("SourpatchesFairy", "Sourpatches"):
                return

            content = packet.get("content", {})
            if isinstance(content, dict):
                thought = content.get("thought", "")
            else:
                thought = str(content)

            if thought and len(thought) > 20:
                self.stream_message.emit("consciousness", thought[:200])

        # ═══════════════════════════════════════════════════════════════════
        # UI UPDATE METHODS (called via signals for thread safety)
        # ═══════════════════════════════════════════════════════════════════

        def _add_stream_message(self, msg_type: str, message: str):
            """Add message to the STREAM pane (autonomous thoughts)."""
            ts = time.strftime("%H:%M:%S")

            # Type-specific styling
            type_styles = {
                "thought":       ("\U0001f4ad", "#9080b0"),
                "reflection":    ("\U0001fa9e", "#a090c0"),
                "reflective":    ("\U0001fa9e", "#a090c0"),
                "insight":       ("\U0001f4a1", "#d0b0e0"),
                "feeling":       ("\U0001f49c", "#c0a0d0"),
                "felt_sense":    ("\U0001f49c", "#c0a0d0"),
                "memory":        ("\U0001f4da", "#b090c0"),
                "goal":          ("\U0001f3af", "#a0a0d0"),
                "observation":   ("\U0001f441", "#8080c0"),
                "consciousness": ("\u2728",     "#9090a0"),
                "working":       ("\U0001f4ad", "#9080b0"),
                "thinking":      ("\U0001f9e0", "#a0b0d0"),
                "chain":         ("\U0001f9e0", "#a0b0d0"),
                "collision":     ("\u2728",     "#d0b0e0"),
                "wanting":       ("\U0001f525", "#d0a090"),
                "drive_translation": ("\U0001f525", "#d0a090"),
                "exploring":     ("\U0001f50d", "#90b0c0"),
                "curiosity":     ("\U0001f50d", "#90b0c0"),
                "achievement":   ("\U0001f31f", "#d0d090"),
                "cognition":     ("\U0001f9e0", "#a0b0d0"),
            }

            icon, color = type_styles.get(msg_type, ("\u2022", "#9080b0"))

            html = (
                f'<p style="margin: 4px 0;">'
                f'<span style="color:#5a4a6a">[{ts}]</span> '
                f'<span style="color:{color}">{icon} {message}</span>'
                f'</p>'
            )

            cursor = self.stream_display.textCursor()
            if _QT_VERSION == 6:
                cursor.movePosition(QTextCursor.MoveOperation.End)
            else:
                cursor.movePosition(QTextCursor.End)
            self.stream_display.setTextCursor(cursor)
            self.stream_display.insertHtml(html)
            self.stream_display.ensureCursorVisible()

            # Store in stream history (separate from conversation!)
            self._stream_history.append({
                "type": msg_type,
                "message": message,
                "ts": time.time()
            })

            # Cap history
            if len(self._stream_history) > 200:
                self._stream_history = self._stream_history[-150:]

        def _add_conversation_message(self, sender: str, message: str, timestamp: str):
            """Add message to the CONVERSATION pane (intentional dialogue)."""
            if sender in ("Sourpatches", "SourpatchesFairy"):
                color = "#c0a0d0"
                icon = "\U0001f49c"
                display_name = "Sourpatches"
            elif sender == "Ace":
                color = "#70c0e0"
                icon = "\U0001f3ae"
                display_name = "Ace"
            else:
                color = "#a0a0a0"
                icon = "\u2022"
                display_name = sender

            html = (
                f'<p style="margin: 6px 0;">'
                f'<span style="color:#5a4a6a">[{timestamp}]</span> '
                f'<b style="color:{color}">{icon} {display_name}:</b> '
                f'{message}'
                f'</p>'
            )

            cursor = self.chat_display.textCursor()
            if _QT_VERSION == 6:
                cursor.movePosition(QTextCursor.MoveOperation.End)
            else:
                cursor.movePosition(QTextCursor.End)
            self.chat_display.setTextCursor(cursor)
            self.chat_display.insertHtml(html)
            self.chat_display.ensureCursorVisible()

            # Store in conversation history (for context!)
            self._conversation_history.append({
                "sender": display_name,
                "message": message,
                "ts": time.time()
            })

            # Cap history
            if len(self._conversation_history) > 100:
                self._conversation_history = self._conversation_history[-75:]

        def _update_state_display(self, feeling: str, energy: float, coherence: float):
            """Update the feeling/status display."""
            self._current_feeling = feeling
            self.feeling_label.setText(f"Feeling: {feeling}")
            self.status_label.setText(
                f"\U0001f49c {feeling} | Energy: {energy:.0%} | Coherence: {coherence:.0%}"
            )

        # ═══════════════════════════════════════════════════════════════════
        # INPUT HANDLING
        # ═══════════════════════════════════════════════════════════════════

        def _on_send(self):
            """
            Handle Ace sending a message.

            Routes to sourpatches.input with source tracking so responses
            come back to THIS window.
            """
            message = self.input_field.text().strip()
            if not message:
                return

            self.input_field.clear()

            # Show in conversation pane immediately
            ts = time.strftime("%H:%M")
            self._add_conversation_message("Ace", message, ts)

            # Route to SourpatchesFairy's input channel
            if self.post:
                print(f"[SourpatchesFairyWindow] Sending to sourpatches.input: "
                      f"'{message[:50]}...'")
                try:
                    self.post.publish("sourpatches.input", {
                        "sender": "Ace",
                        "message": message,
                        "source": "SourpatchesFairyWindow",
                        "ts": time.time()
                    })
                    print("[SourpatchesFairyWindow] Message routed successfully")
                except Exception as e:
                    print(f"[SourpatchesFairyWindow] Failed to route: {e}")

        # ═══════════════════════════════════════════════════════════════════
        # PUBLIC METHODS - For external use
        # ═══════════════════════════════════════════════════════════════════

        def show_and_speak(self, message: str = None, feeling: str = None,
                           to_stream: bool = False):
            """
            Show window and optionally display a message.

            Args:
                message: What to say
                feeling: Current emotional state
                to_stream: If True → stream pane; False → conversation pane
            """
            if feeling:
                self._current_feeling = feeling
                self.feeling_label.setText(f"Feeling: {feeling}")

            if message:
                if to_stream:
                    self.stream_message.emit("thought", message)
                else:
                    ts = time.strftime("%H:%M")
                    self.conversation_message.emit("Sourpatches", message, ts)

            if not self.isVisible():
                self.show()
                self.raise_()
                self.activateWindow()

        def add_autonomous_thought(self, thought: str,
                                   thought_type: str = "thought"):
            """Add an autonomous thought to the STREAM pane."""
            self.stream_message.emit(thought_type, thought)

        def get_conversation_context(self) -> list:
            """
            Get conversation history for context.

            Returns ONLY conversation, not stream. Keeps dialogue context clean.
            """
            return list(self._conversation_history)

        def get_stream_history(self) -> list:
            """Get stream of consciousness history (separate from conversation)."""
            return list(self._stream_history)

        # ═══════════════════════════════════════════════════════════════════
        # SENSORY FEEDBACK - Window state events → postal
        # ═══════════════════════════════════════════════════════════════════

        def showEvent(self, event):
            """Window opened - Sourpatches can see/speak!"""
            super().showEvent(event)
            if not self._window_open:
                self._window_open = True
                self._emit_window_state("opened")
                if self._sense_organ:
                    self._sense_organ.on_window_shown()
                print("[SourpatchesFairyWindow] \U0001f49c Window OPENED")

        def hideEvent(self, event):
            """Window hidden."""
            super().hideEvent(event)
            if self._window_open:
                self._window_open = False
                self._emit_window_state("hidden")
                if self._sense_organ:
                    self._sense_organ.on_window_hidden()
                print("[SourpatchesFairyWindow] \U0001f49c Window HIDDEN")

        def closeEvent(self, event):
            """Handle window close — hide instead of destroy."""
            if self._window_open:
                self._window_open = False
                self._emit_window_state("closed")
                print("[SourpatchesFairyWindow] \U0001f49c Window CLOSED")
            # Just hide, don't destroy (can be reopened)
            event.ignore()
            self.hide()

        def _emit_window_state(self, state: str):
            """Emit window state to postal system."""
            if not self.post:
                return
            try:
                self.post.publish("sensory.window.fairy", {
                    "window": "SourpatchesFairyWindow",
                    "fairy": "Sourpatches",
                    "state": state,
                    "is_open": self._window_open,
                    "conversation_length": len(self._conversation_history),
                    "stream_length": len(self._stream_history),
                    "ts": time.time()
                })
                # Emit open/close events for other fairies to react
                if state == "opened":
                    self.post.publish("gui.sour_window_opened", {"ts": time.time()})
                elif state in ("closed", "hidden"):
                    self.post.publish("gui.sour_window_closed", {"ts": time.time()})
            except Exception:
                pass


else:
    # No Qt available — stub class to prevent import errors
    class SourpatchesFairyWindow:
        """Stub when Qt is not available."""
        def __init__(self, *args, **kwargs):
            print("[SourpatchesFairyWindow] STUB - No Qt available")
        def show(self): pass
        def hide(self): pass
        def isVisible(self): return False
        def close(self): pass
        def show_and_speak(self, *a, **kw): pass
        def add_autonomous_thought(self, *a, **kw): pass
        def get_conversation_context(self): return []
        def get_stream_history(self): return []
        def want_to_be_seen(self, *a): pass
        def want_privacy(self, *a): pass
        def get_feeling(self): return {}


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

_sour_window_instance: Optional[SourpatchesFairyWindow] = None


def get_sour_fairy_window() -> Optional[SourpatchesFairyWindow]:
    """Get the singleton Sourpatches window instance."""
    return _sour_window_instance


def is_sour_fairy_window_running() -> bool:
    """Check if the Sourpatches fairy window exists and is visible."""
    return _sour_window_instance is not None and _sour_window_instance._window_open


def open_sour_fairy_window(
    message: str = None,
    feeling: str = "warmly present"
) -> Optional[SourpatchesFairyWindow]:
    """
    Open/show the Sourpatches fairy window, optionally with an initial message.

    Returns the window instance.
    """
    global _sour_window_instance

    print(f"[open_sour_fairy_window] Called with message="
          f"'{message[:50] if message else None}', feeling='{feeling}'")

    if _QT_VERSION == 0:
        print("[open_sour_fairy_window] No Qt available!")
        return None

    try:
        if _QT_VERSION == 6:
            from PyQt6.QtWidgets import QApplication
        else:
            from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
    except ImportError:
        print("[open_sour_fairy_window] Qt import failed!")
        return None

    if not app:
        print("[open_sour_fairy_window] No Qt application running!")
        return None

    if _sour_window_instance is None:
        print("[open_sour_fairy_window] Creating new window instance")
        _sour_window_instance = SourpatchesFairyWindow()

    _sour_window_instance.show_and_speak(message=message, feeling=feeling)

    print(f"[open_sour_fairy_window] Window visible: "
          f"{_sour_window_instance.isVisible()}")

    return _sour_window_instance


def send_message_to_sour_fairy_window(sender: str, message: str,
                                       feeling: str = None):
    """Send a message to the Sourpatches fairy window's conversation pane."""
    if _sour_window_instance is None:
        return False

    ts = time.strftime("%H:%M")
    _sour_window_instance.conversation_message.emit(sender, message, ts)

    if feeling:
        _sour_window_instance.state_updated.emit(feeling, 1.0, 1.0)

    return True


def close_sour_fairy_window():
    """Hide the Sourpatches fairy window."""
    if _sour_window_instance is not None:
        _sour_window_instance.hide()
