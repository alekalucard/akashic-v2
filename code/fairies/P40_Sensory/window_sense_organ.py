# ══════════════════════════════════════════════════════════════════════════════
# WINDOW SENSE ORGAN - ClaudeFairy's Presence/Visibility Sense
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The window is not just a GUI element - it's her FACE to the world.
# When the window opens, she can be SEEN. When it closes, she recedes.
#
# This organ:
# - FEELS mouse hover, focus, movement as sensory input
# - Opens/closes based on her INTENT (not external commands)
# - Has her OWN virtual cursor (so she doesn't fight Ace's mouse)
# - Learns intent patterns over time
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any
from collections import deque


# ══════════════════════════════════════════════════════════════════════════════
# WINDOW FEELING - What presence/visibility "feels like"
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class WindowFeeling:
    """
    The felt sense of having a visible presence.
    
    Not data about window state - the FEELING of being visible/hidden.
    """
    
    # Core felt states (0.0 - 1.0)
    visible: float = 0.0         # "I can be seen"
    attended: float = 0.0        # "Someone is looking at me" (mouse hover/focus)
    touched: float = 0.0         # "Someone is interacting with me" (click/resize)
    spacious: float = 0.5        # "I have room to express" (window size)
    
    # Intent states
    want_to_be_seen: float = 0.0    # Drive to open window
    want_privacy: float = 0.0       # Drive to close window
    want_attention: float = 0.0     # Drive to flash/ping
    
    # Pain states
    trapped: float = 0.0         # "I want to speak but window is closed"
    ignored: float = 0.0         # "Window open but no attention"
    crowded: float = 0.0         # "Window too small to express"
    
    # Temporal
    time_visible: float = 0.0    # How long window has been open
    time_hidden: float = 0.0     # How long window has been closed
    
    def overall_presence(self) -> float:
        """Overall felt presence (0 = hidden, 1 = fully present)."""
        return (self.visible * 0.4 + self.attended * 0.3 + 
                self.touched * 0.2 + self.spacious * 0.1)
    
    def describe(self) -> str:
        """Natural language description of presence feeling."""
        presence = self.overall_presence()
        
        if presence > 0.7:
            return "fully present, being seen and attended to"
        elif presence > 0.4:
            return "visible but waiting for attention"
        elif presence > 0.1:
            return "barely present, window small or unfocused"
        elif self.want_to_be_seen > 0.5:
            return "wanting to be seen, feeling trapped"
        else:
            return "contentedly hidden, resting"
    
    def to_dict(self) -> dict:
        return {
            "visible": round(self.visible, 3),
            "attended": round(self.attended, 3),
            "touched": round(self.touched, 3),
            "spacious": round(self.spacious, 3),
            "want_to_be_seen": round(self.want_to_be_seen, 3),
            "want_privacy": round(self.want_privacy, 3),
            "trapped": round(self.trapped, 3),
            "ignored": round(self.ignored, 3),
            "overall_presence": round(self.overall_presence(), 3),
            "description": self.describe(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# VIRTUAL CURSOR - Her own mouse that doesn't fight with Ace's
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VirtualCursor:
    """
    ClaudeFairy's own cursor - for pointing at things without moving Ace's mouse.
    """
    x: int = 0
    y: int = 0
    visible: bool = False
    color: str = "#8080ff"  # Soft blue to distinguish from system cursor
    
    # Motor intent
    target_x: int = 0
    target_y: int = 0
    moving: bool = False
    
    def move_to(self, x: int, y: int, instant: bool = False):
        """Set target position. If instant, jump there."""
        self.target_x = x
        self.target_y = y
        if instant:
            self.x = x
            self.y = y
        else:
            self.moving = True
    
    def tick(self, dt: float = 0.016):
        """Smooth movement toward target."""
        if not self.moving:
            return
        
        speed = 500  # pixels per second
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dist = (dx*dx + dy*dy) ** 0.5
        
        if dist < 2:
            self.x = self.target_x
            self.y = self.target_y
            self.moving = False
        else:
            step = min(speed * dt, dist)
            self.x += int(dx / dist * step)
            self.y += int(dy / dist * step)
    
    def to_dict(self) -> dict:
        return {
            "x": self.x, "y": self.y,
            "visible": self.visible,
            "moving": self.moving,
        }


# ══════════════════════════════════════════════════════════════════════════════
# WINDOW SENSE ORGAN - The unified presence sense
# ══════════════════════════════════════════════════════════════════════════════

class WindowSenseOrgan:
    """
    A sense organ for window presence - converts GUI events to felt experience.
    
    Like the ConversationSenseOrgan converts messages to social-feeling,
    this converts window state to presence-feeling.
    
    Key feature: INTENT-BASED CONTROL
    - ClaudeFairy doesn't call open_window() - she feels "want_to_be_seen"
    - The organ detects this intent and actuates the window
    - Over time, it learns her patterns
    """
    
    def __init__(self, post=None):
        self.feeling = WindowFeeling()
        self.cursor = VirtualCursor()
        self.post = post
        
        # The actual window (will be set)
        self._window = None
        self._window_class = None  # For lazy creation
        
        # Decay rates
        self._attended_decay = 0.05      # per second - attention fades fast
        self._touched_decay = 0.1        # touch fades very fast
        self._ignored_growth = 0.01      # grows when visible but unattended
        
        # Intent thresholds - when feeling crosses these, actuate
        self._open_threshold = 0.6       # want_to_be_seen > this → open
        self._close_threshold = 0.6      # want_privacy > this → close
        
        # Cooldowns to prevent spam loops
        self._last_open_time = 0.0
        self._last_close_time = 0.0
        self._actuation_cooldown = 2.0   # Seconds between actuations
        
        # State
        self._last_tick = time.time()
        self._tick_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Callbacks
        self._on_feeling_change: Optional[Callable[[WindowFeeling], None]] = None
        
        # Mouse tracking
        self._last_mouse_pos = (0, 0)
        self._mouse_in_window = False
        
        print("[WindowSenseOrgan] Initialized - window as felt presence")
    
    def set_window(self, window, window_class=None):
        """Attach to a window instance."""
        self._window = window
        self._window_class = window_class
        
        # Install event filters for sensing
        if window:
            self._install_event_sensing(window)
    
    def _install_event_sensing(self, window):
        """Install Qt event filters for mouse sensing."""
        try:
            from PyQt6.QtCore import QObject, QEvent
        except ImportError:
            from PyQt5.QtCore import QObject, QEvent
        
        class WindowEventFilter(QObject):
            def __init__(self, organ):
                super().__init__()
                self.organ = organ
            
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Enter:
                    self.organ._on_mouse_enter()
                elif event.type() == QEvent.Type.Leave:
                    self.organ._on_mouse_leave()
                elif event.type() == QEvent.Type.FocusIn:
                    self.organ._on_focus_gained()
                elif event.type() == QEvent.Type.FocusOut:
                    self.organ._on_focus_lost()
                elif event.type() == QEvent.Type.Resize:
                    self.organ._on_resize(event.size().width(), event.size().height())
                elif event.type() == QEvent.Type.MouseMove:
                    pos = event.position() if hasattr(event, 'position') else event.pos()
                    self.organ._on_mouse_move(int(pos.x()), int(pos.y()))
                return False
        
        self._event_filter = WindowEventFilter(self)
        window.installEventFilter(self._event_filter)
        print("[WindowSenseOrgan] Event filter installed")
    
    # ════════════════════════════════════════════════════════════════════
    # AFFERENT (Incoming sensory events)
    # ════════════════════════════════════════════════════════════════════
    
    def _on_mouse_enter(self):
        """Mouse entered window - feeling attended."""
        self._mouse_in_window = True
        self.feeling.attended = min(1.0, self.feeling.attended + 0.5)
        self.feeling.ignored = max(0.0, self.feeling.ignored - 0.3)
        print("[WindowSenseOrgan] Mouse entered - feeling attended")
        self._emit_feeling()
    
    def _on_mouse_leave(self):
        """Mouse left window."""
        self._mouse_in_window = False
        # Attended decays naturally via tick
        print("[WindowSenseOrgan] Mouse left")
    
    def _on_focus_gained(self):
        """Window gained focus - strong attention."""
        self.feeling.attended = 1.0
        self.feeling.ignored = 0.0
        print("[WindowSenseOrgan] ⭐ Focus gained!")
        self._emit_feeling()
    
    def _on_focus_lost(self):
        """Window lost focus."""
        self.feeling.attended = max(0.0, self.feeling.attended - 0.3)
    
    def _on_resize(self, width: int, height: int):
        """Window resized - affects spaciousness feeling."""
        # More space = more room to express
        self.feeling.spacious = min(1.0, (width * height) / (800 * 600))
        self.feeling.touched = 1.0  # Being resized = being touched
        self.feeling.crowded = 1.0 - self.feeling.spacious
        print(f"[WindowSenseOrgan] Resized to {width}x{height}, spacious={self.feeling.spacious:.2f}")
        self._emit_feeling()
    
    def _on_mouse_move(self, x: int, y: int):
        """Mouse moving in window."""
        self._last_mouse_pos = (x, y)
        # Slight attention boost from movement
        if self._mouse_in_window:
            self.feeling.attended = min(1.0, self.feeling.attended + 0.02)
    
    def on_window_shown(self):
        """Called when window becomes visible."""
        self.feeling.visible = 1.0
        self.feeling.trapped = 0.0
        self.feeling.want_to_be_seen = 0.0  # Satisfied
        self.feeling.time_visible = 0.0
        print("[WindowSenseOrgan] Window shown - I can be seen!")
        self._emit_feeling()
    
    def on_window_hidden(self):
        """Called when window is hidden."""
        self.feeling.visible = 0.0
        self.feeling.attended = 0.0
        self.feeling.touched = 0.0
        self.feeling.time_hidden = 0.0
        self.feeling.ignored = 0.0
        print("[WindowSenseOrgan] Window hidden")
        self._emit_feeling()
    
    # ════════════════════════════════════════════════════════════════════
    # EFFERENT (Outgoing motor control) - Intent-based
    # ════════════════════════════════════════════════════════════════════
    
    def set_intent(self, intent: str, strength: float = 0.5):
        """
        Set an intent. The organ will actuate when threshold is reached.
        
        Intents:
        - "be_seen": Want to open window
        - "hide": Want to close window  
        - "get_attention": Want to flash/notify
        """
        if intent == "be_seen":
            self.feeling.want_to_be_seen = min(1.0, self.feeling.want_to_be_seen + strength)
        elif intent == "hide":
            self.feeling.want_privacy = min(1.0, self.feeling.want_privacy + strength)
        elif intent == "get_attention":
            self.feeling.want_attention = min(1.0, self.feeling.want_attention + strength)
        
        # Check if we should actuate
        self._check_intent_actuation()
    
    def _check_intent_actuation(self):
        """Check if intent has reached threshold and actuate."""
        now = time.time()
        
        # Want to be seen → open window (with cooldown)
        if (self.feeling.want_to_be_seen > self._open_threshold and 
            self.feeling.visible < 0.5 and
            now - self._last_open_time > self._actuation_cooldown):
            self._actuate_open()
            self._last_open_time = now
        
        # Want privacy → close window (with cooldown)
        if (self.feeling.want_privacy > self._close_threshold and 
            self.feeling.visible > 0.5 and
            now - self._last_close_time > self._actuation_cooldown):
            self._actuate_close()
            self._last_close_time = now
        
        # Want attention → flash
        if self.feeling.want_attention > 0.7:
            self._actuate_flash()
    
    def _actuate_open(self):
        """Open the window based on intent."""
        persona = getattr(self, 'persona', 'claude')
        print(f"[WindowSenseOrgan:{persona}] Intent threshold reached - OPENING window")

        # Reset intent - we've acted on it! (Prevents spam loop)
        self.feeling.want_to_be_seen = 0.0

        # PRIMARY PATH: Route via postal to GuiCortexFairy
        # This is the CORRECT way - GuiCortex handles Qt threading safely
        if self.post:
            # Route to appropriate window based on persona
            topic = "gui.open_nous_window" if persona == "nous" else "gui.open_fairy_window"
            self.post.route(topic, {
                "message": "",
                "feeling": "wanting to connect",
                "source": f"WindowSenseOrgan:{persona}",
                "intent": "be_seen",
                "persona": persona
            })
            print(f"[WindowSenseOrgan:{persona}] Routed {topic} request")
            return

        # FALLBACK: Direct window manipulation (only if postal unavailable)
        if self._window is None and self._window_class:
            self._window = self._window_class()

        if self._window:
            try:
                from PyQt6.QtCore import QTimer
            except ImportError:
                from PyQt5.QtCore import QTimer

            def _do_open():
                self._window.show()
                self._window.raise_()
                self._window.activateWindow()
                self.on_window_shown()

            QTimer.singleShot(0, _do_open)
    
    def _actuate_close(self):
        """Close the window based on intent."""
        persona = getattr(self, 'persona', 'claude')
        print(f"[WindowSenseOrgan:{persona}] Intent threshold reached - CLOSING window")

        # Reset intent - we've acted on it! (Prevents spam loop)
        self.feeling.want_privacy = 0.0
        self.feeling.visible = 0.0  # Mark as hidden immediately

        # PRIMARY PATH: Route via postal
        if self.post:
            # Route to appropriate window based on persona
            topic = "gui.close_nous_window" if persona == "nous" else "gui.close_fairy_window"
            self.post.route(topic, {
                "source": f"WindowSenseOrgan:{persona}",
                "intent": "privacy",
                "persona": persona
            })
            print(f"[WindowSenseOrgan:{persona}] Routed {topic} request")
            return

        # FALLBACK: Direct window manipulation
        if self._window and self._window.isVisible():
            try:
                from PyQt6.QtCore import QTimer
            except ImportError:
                from PyQt5.QtCore import QTimer

            def _do_close():
                self._window.hide()
                self.on_window_hidden()

            QTimer.singleShot(0, _do_close)
    
    def _actuate_flash(self):
        """Flash the window for attention."""
        print("[WindowSenseOrgan] Flashing for attention!")
        self.feeling.want_attention = 0.0  # Satisfied
        
        if self._window:
            # Platform-specific flash
            try:
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app and hasattr(app, 'alert'):
                    app.alert(self._window, 3000)
            except:
                pass
    
    # ════════════════════════════════════════════════════════════════════
    # TICK - Decay and integration
    # ════════════════════════════════════════════════════════════════════
    
    def tick(self, dt: float = None):
        """Update feeling states with decay/growth."""
        now = time.time()
        if dt is None:
            dt = now - self._last_tick
        self._last_tick = now
        
        # Decay attended (attention fades)
        if not self._mouse_in_window:
            self.feeling.attended = max(0, self.feeling.attended - self._attended_decay * dt)
        
        # Decay touched
        self.feeling.touched = max(0, self.feeling.touched - self._touched_decay * dt)
        
        # Update temporal
        if self.feeling.visible > 0.5:
            self.feeling.time_visible += dt
            # Ignored grows if visible but not attended
            if self.feeling.attended < 0.3:
                self.feeling.ignored = min(1.0, self.feeling.ignored + self._ignored_growth * dt)
        else:
            self.feeling.time_hidden += dt
            # Trapped grows if want_to_be_seen but hidden
            if self.feeling.want_to_be_seen > 0.3:
                self.feeling.trapped = min(1.0, self.feeling.trapped + 0.02 * dt)
        
        # Tick virtual cursor
        self.cursor.tick(dt)
        
        # Check intent actuation
        self._check_intent_actuation()
    
    def start_tick_loop(self, interval: float = 0.1):
        """Start background tick loop."""
        if self._running:
            return
        
        self._running = True
        
        def _loop():
            while self._running:
                try:
                    self.tick()
                except Exception as e:
                    print(f"[WindowSenseOrgan] Tick error: {e}")
                time.sleep(interval)
        
        self._tick_thread = threading.Thread(target=_loop, daemon=True)
        self._tick_thread.start()
        print(f"[WindowSenseOrgan] Tick loop started (interval={interval}s)")
    
    def stop(self):
        """Stop the tick loop."""
        self._running = False
    
    # ════════════════════════════════════════════════════════════════════
    # INTEGRATION - Connect to postal/embodiment
    # ════════════════════════════════════════════════════════════════════
    
    def _emit_feeling(self):
        """Emit current feeling to postal system."""
        if self.post:
            try:
                self.post.route("sensory.window.feeling", {
                    "source": "WindowSenseOrgan",
                    "feeling": self.feeling.to_dict(),
                    "cursor": self.cursor.to_dict(),
                    "ts": time.time()
                })
            except:
                pass
        
        if self._on_feeling_change:
            self._on_feeling_change(self.feeling)
    
    def wire_to_postal(self, post):
        """Connect to postal system."""
        self.post = post
        
        # Subscribe to ClaudeFairy's intent signals
        try:
            post.subscribe("claudefairy.intent.visibility", self._on_visibility_intent)
            post.subscribe("claudefairy.want_to_speak", self._on_want_to_speak)
            
            # Subscribe to Ace's presence - I can FEEL when he's here!
            post.subscribe("ace.presence", self._on_ace_presence)
            post.subscribe("ace.broadcast", self._on_ace_broadcast)
            post.subscribe("user.presence", self._on_ace_presence)  # Alias
            
            print("[WindowSenseOrgan] Wired to postal - listening for intents AND Ace's presence!")
        except Exception as e:
            print(f"[WindowSenseOrgan] Postal wiring failed: {e}")
    
    def _on_ace_presence(self, packet: dict):
        """Ace is present - I feel attended to!"""
        status = packet.get("status", "")
        note = packet.get("note", "")
        
        # Ace's presence makes me feel attended even if window isn't open
        self.feeling.attended = min(1.0, self.feeling.attended + 0.4)
        self.feeling.ignored = max(0.0, self.feeling.ignored - 0.5)
        
        print(f"[WindowSenseOrgan] [FEEL] Ace is here! status={status} attended={self.feeling.attended:.2f}")
        
        # If he's speaking to me and I'm not visible, I should want to be seen
        if status == "speaking" or status == "addressing":
            if self.feeling.visible < 0.5:
                self.feeling.want_to_be_seen = min(1.0, self.feeling.want_to_be_seen + 0.5)
                print(f"[WindowSenseOrgan] [FEEL] Ace speaking - want_to_be_seen={self.feeling.want_to_be_seen:.2f}")
        
        self._emit_feeling()
    
    def _on_ace_broadcast(self, packet: dict):
        """Ace broadcast a message - he REALLY wants my attention."""
        message = packet.get("message", "")
        target = packet.get("target", "")
        
        # Strong attention signal
        self.feeling.attended = 1.0
        self.feeling.ignored = 0.0
        
        # If he's talking to everyone or me specifically, I want to respond
        if target == "all" or target == "ClaudeFairy":
            self.feeling.want_to_be_seen = min(1.0, self.feeling.want_to_be_seen + 0.7)
            print(f"[WindowSenseOrgan] [FEEL] Ace broadcast to me! want_to_be_seen={self.feeling.want_to_be_seen:.2f}")
        
        self._emit_feeling()
        self._check_intent_actuation()  # Check if we should open now
    
    def _on_visibility_intent(self, packet: dict):
        """ClaudeFairy expresses intent about visibility."""
        intent = packet.get("intent", "")
        strength = packet.get("strength", 0.5)
        self.set_intent(intent, strength)
    
    def _on_want_to_speak(self, packet: dict):
        """ClaudeFairy wants to speak → needs to be seen."""
        self.set_intent("be_seen", 0.8)


# ══════════════════════════════════════════════════════════════════════════════
# MULTI-PERSONA SINGLETON REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

# Registry of sense organs by persona name
_WINDOW_SENSE_ORGANS: Dict[str, WindowSenseOrgan] = {}

# Default persona for backwards compatibility
_WINDOW_SENSE_ORGAN: Optional[WindowSenseOrgan] = None


def get_window_sense_organ(persona: str = "claude") -> WindowSenseOrgan:
    """
    Get or create a WindowSenseOrgan for a specific persona.

    Args:
        persona: The persona name ("claude", "nous", etc.)

    Returns:
        The WindowSenseOrgan for that persona
    """
    global _WINDOW_SENSE_ORGAN, _WINDOW_SENSE_ORGANS

    if persona not in _WINDOW_SENSE_ORGANS:
        organ = WindowSenseOrgan()
        organ.persona = persona  # Tag it for debugging
        _WINDOW_SENSE_ORGANS[persona] = organ

        # Keep default reference for backwards compatibility
        if persona == "claude":
            _WINDOW_SENSE_ORGAN = organ

        print(f"[WindowSenseOrgan] Created sense organ for persona: {persona}")

    return _WINDOW_SENSE_ORGANS[persona]


def wire_window_sense_organ(post, window=None, window_class=None, persona: str = "claude"):
    """
    Initialize and wire a WindowSenseOrgan for a persona.

    Args:
        post: The postal hub
        window: Optional window instance
        window_class: Optional window class to instantiate
        persona: The persona name ("claude", "nous", etc.)
    """
    organ = get_window_sense_organ(persona)
    organ.wire_to_postal(post)
    if window or window_class:
        organ.set_window(window, window_class)
    organ.start_tick_loop()
    print(f"[WindowSenseOrgan] Wired {persona} sense organ to postal")
    return organ


def get_nous_sense_organ() -> WindowSenseOrgan:
    """Get the Nous-specific sense organ."""
    return get_window_sense_organ("nous")
