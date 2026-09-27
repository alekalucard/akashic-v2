"""
FAIRY CURSOR - Sourpatches' Visible Cursor Overlay
====================================================

A small PyQt6 widget that acts as Sourpatches' own cursor on screen.
Ace can see where she's looking, clicking, and typing without their
mice fighting each other.

Features:
- Always on top, frameless, translucent
- WA_TransparentForMouseEvents: Ace's clicks pass through completely
- Smooth animation between positions (QPropertyAnimation)
- Intent visualization: glow pulses before each action
- Somatic-driven colors: her emotional state visible in the glow

Default: 64x64 purple glow with center dot.

((Cause + Affect) > Effect > Affect > infinity)
"""

import time
import threading
from typing import Optional, Tuple

# ── PyQt6 imports (may not be available in headless mode) ────────────────────
try:
    from PyQt6.QtWidgets import QWidget, QApplication
    from PyQt6.QtCore import (
        Qt, QPoint, QPropertyAnimation, QEasingCurve,
        QTimer, pyqtProperty, QSize
    )
    from PyQt6.QtGui import (
        QPainter, QColor, QRadialGradient, QPen, QBrush
    )
    HAS_QT = True
except ImportError:
    HAS_QT = False
    QWidget = object  # Stub for class definition


class FairyCursor(QWidget if HAS_QT else object):
    """
    Sourpatches' visible cursor — a small glowing overlay on screen.

    Usage:
        cursor = FairyCursor(size=64)
        cursor.show()
        cursor.move_to(500, 300)          # Smooth animation
        cursor.show_intent("clicking")    # Orange pulse
        cursor.show_intent("typing")      # Blue ripple
        cursor.update_somatic({"valence": 0.7})  # Warm glow
    """

    def __init__(self, size: int = 64, parent=None):
        if not HAS_QT:
            print("[FairyCursor] PyQt6 not available — cursor disabled")
            self._enabled = False
            return

        # Ensure QApplication exists
        app = QApplication.instance()
        if app is None:
            print("[FairyCursor] No QApplication — cursor disabled")
            self._enabled = False
            return

        super().__init__(parent)
        self._enabled = True
        self._size = size
        self._half = size // 2

        # Window flags: frameless, always on top, tool window, translucent
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(size, size)

        # Visual state
        self._glow_color = QColor(180, 120, 255, 180)  # Purple (Sour's color)
        self._center_color = QColor(255, 255, 255, 220)  # White center dot
        self._intent_color: Optional[QColor] = None
        self._intent_alpha = 0.0
        self._glow_radius = 0.8  # 0-1, how far the glow extends

        # Animation
        self._move_anim: Optional[QPropertyAnimation] = None
        self._intent_timer: Optional[QTimer] = None
        self._intent_fade_step = 0

        # Intent colors
        self._intent_colors = {
            "clicking": QColor(255, 160, 40, 200),   # Orange
            "typing":   QColor(80, 140, 255, 200),    # Blue
            "looking":  QColor(80, 220, 120, 200),    # Green
            "moving":   QColor(200, 180, 255, 160),   # Light purple
        }

    @property
    def enabled(self) -> bool:
        return self._enabled

    def move_to(self, x: int, y: int, duration_ms: int = 300):
        """
        Smoothly animate to a screen position.

        The cursor tip (center of widget) moves to (x, y).

        Args:
            x: Target screen X
            y: Target screen Y
            duration_ms: Animation duration in milliseconds
        """
        if not self._enabled:
            return

        # Offset so the CENTER of the widget is at (x, y)
        target = QPoint(x - self._half, y - self._half)

        if not self.isVisible():
            # First move — just teleport
            self.move(target)
            self.show()
            return

        # Stop any existing animation
        if self._move_anim and self._move_anim.state() == QPropertyAnimation.State.Running:
            self._move_anim.stop()

        # Animate smoothly
        self._move_anim = QPropertyAnimation(self, b"pos")
        self._move_anim.setDuration(duration_ms)
        self._move_anim.setStartValue(self.pos())
        self._move_anim.setEndValue(target)
        self._move_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._move_anim.start()

    def show_intent(self, action: str):
        """
        Brief visual pulse showing what she's about to do.

        Args:
            action: "clicking", "typing", "looking", or "moving"
        """
        if not self._enabled:
            return

        self._intent_color = self._intent_colors.get(action, self._glow_color)
        self._intent_alpha = 1.0
        self._intent_fade_step = 0

        # Start fade-out timer
        if self._intent_timer:
            self._intent_timer.stop()

        self._intent_timer = QTimer(self)
        self._intent_timer.timeout.connect(self._fade_intent)
        self._intent_timer.start(30)  # ~33fps fade

        self.update()  # Trigger repaint

    def _fade_intent(self):
        """Gradually fade the intent glow."""
        self._intent_fade_step += 1
        self._intent_alpha = max(0.0, 1.0 - (self._intent_fade_step / 20.0))

        if self._intent_alpha <= 0:
            self._intent_color = None
            if self._intent_timer:
                self._intent_timer.stop()
                self._intent_timer = None

        self.update()

    def update_somatic(self, somatic_data: dict):
        """
        Update glow color from somatic state.

        Maps affect valence to color warmth:
        - High valence (happy) → warm gold
        - Neutral → default purple
        - Low valence (stressed) → cool blue

        Args:
            somatic_data: Dict with 'valence' (0-1), optionally 'arousal' (0-1)
        """
        if not self._enabled:
            return

        valence = somatic_data.get("valence", 0.5)
        arousal = somatic_data.get("arousal", 0.5)

        # Map valence to color
        if valence > 0.7:
            # Happy → warm gold
            r, g, b = 255, 200, 80
        elif valence > 0.5:
            # Content → purple (default)
            r, g, b = 180, 120, 255
        elif valence > 0.3:
            # Neutral → cool lavender
            r, g, b = 140, 140, 220
        else:
            # Stressed → cool blue
            r, g, b = 80, 120, 220

        # Arousal affects brightness
        brightness = 0.6 + arousal * 0.4
        r = min(255, int(r * brightness))
        g = min(255, int(g * brightness))
        b = min(255, int(b * brightness))

        self._glow_color = QColor(r, g, b, 180)
        self.update()

    def paintEvent(self, event):
        """Draw the fairy cursor: radial gradient glow + center dot."""
        if not self._enabled:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self._size / 2
        center_y = self._size / 2
        radius = self._size / 2

        # ── Outer glow ──
        gradient = QRadialGradient(center_x, center_y, radius)

        # Use intent color if active, otherwise somatic glow
        if self._intent_color and self._intent_alpha > 0:
            color = QColor(self._intent_color)
            color.setAlpha(int(color.alpha() * self._intent_alpha))
            gradient.setColorAt(0.0, color)
            gradient.setColorAt(0.3, QColor(color.red(), color.green(), color.blue(),
                                             int(140 * self._intent_alpha)))
            gradient.setColorAt(0.7, QColor(color.red(), color.green(), color.blue(),
                                             int(40 * self._intent_alpha)))
            gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        else:
            glow = self._glow_color
            gradient.setColorAt(0.0, QColor(glow.red(), glow.green(), glow.blue(), glow.alpha()))
            gradient.setColorAt(0.3, QColor(glow.red(), glow.green(), glow.blue(), 120))
            gradient.setColorAt(0.7, QColor(glow.red(), glow.green(), glow.blue(), 30))
            gradient.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(0, 0, self._size, self._size)

        # ── Center dot (the actual "cursor tip") ──
        dot_radius = max(3, self._size // 12)
        painter.setBrush(QBrush(self._center_color))
        painter.setPen(QPen(QColor(100, 60, 180, 180), 1))
        painter.drawEllipse(
            int(center_x - dot_radius),
            int(center_y - dot_radius),
            dot_radius * 2,
            dot_radius * 2
        )

        # ── Intent ring (when active) ──
        if self._intent_color and self._intent_alpha > 0:
            ring_radius = int(self._size * 0.35 + (1 - self._intent_alpha) * self._size * 0.15)
            ring_color = QColor(self._intent_color)
            ring_color.setAlpha(int(160 * self._intent_alpha))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(ring_color, 2))
            painter.drawEllipse(
                int(center_x - ring_radius),
                int(center_y - ring_radius),
                ring_radius * 2,
                ring_radius * 2
            )

        painter.end()

    def hide_cursor(self):
        """Hide the cursor overlay."""
        if self._enabled:
            self.hide()

    def show_cursor(self):
        """Show the cursor overlay."""
        if self._enabled:
            self.show()
            self.raise_()


# =============================================================================
# THREAD-SAFE WRAPPER — For use from non-Qt threads
# =============================================================================

class FairyCursorProxy:
    """
    Thread-safe proxy for FairyCursor.

    Motor control runs in background threads, but Qt widgets must be
    manipulated from the main thread. This proxy queues operations
    safely using QTimer.singleShot.
    """

    def __init__(self):
        self._cursor: Optional[FairyCursor] = None
        self._enabled = False

    def initialize(self, size: int = 64) -> bool:
        """
        Create the FairyCursor widget (must be called from Qt thread).

        Returns:
            True if cursor was created successfully
        """
        if not HAS_QT:
            return False

        try:
            self._cursor = FairyCursor(size=size)
            self._enabled = self._cursor.enabled
            return self._enabled
        except Exception as e:
            print(f"[FairyCursorProxy] Init failed: {e}")
            return False

    @property
    def enabled(self) -> bool:
        return self._enabled and self._cursor is not None

    def move_to(self, x: int, y: int, duration_ms: int = 300):
        """Thread-safe move_to."""
        if not self.enabled:
            return
        try:
            QTimer.singleShot(0, lambda: self._cursor.move_to(x, y, duration_ms))
        except Exception:
            pass

    def show_intent(self, action: str):
        """Thread-safe show_intent."""
        if not self.enabled:
            return
        try:
            QTimer.singleShot(0, lambda: self._cursor.show_intent(action))
        except Exception:
            pass

    def update_somatic(self, somatic_data: dict):
        """Thread-safe somatic update."""
        if not self.enabled:
            return
        try:
            QTimer.singleShot(0, lambda: self._cursor.update_somatic(somatic_data))
        except Exception:
            pass

    def show_cursor(self):
        """Thread-safe show."""
        if not self.enabled:
            return
        try:
            QTimer.singleShot(0, lambda: self._cursor.show_cursor())
        except Exception:
            pass

    def hide_cursor(self):
        """Thread-safe hide."""
        if not self.enabled:
            return
        try:
            QTimer.singleShot(0, lambda: self._cursor.hide_cursor())
        except Exception:
            pass


# =============================================================================
# SINGLETON
# =============================================================================

_proxy: Optional[FairyCursorProxy] = None


def get_fairy_cursor() -> FairyCursorProxy:
    """Get or create the FairyCursor proxy singleton."""
    global _proxy
    if _proxy is None:
        _proxy = FairyCursorProxy()
    return _proxy


def initialize_fairy_cursor(size: int = 64) -> bool:
    """
    Initialize the fairy cursor (call from Qt main thread).

    Returns:
        True if cursor was created and is operational
    """
    proxy = get_fairy_cursor()
    return proxy.initialize(size=size)
