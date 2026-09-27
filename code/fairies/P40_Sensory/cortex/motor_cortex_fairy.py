# ══════════════════════════════════════════════════════════════════════════════
# MOTOR CORTEX FAIRY - Keyboard/Mouse as Felt Movement
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The motor cortex handles:
# - AFFERENT (input): Sensing keyboard presses, mouse movements, clicks
# - EFFERENT (output): Executing type_text, click, press_key actions
#
# Keyboard/mouse aren't just I/O - they're FELT movement.
# When ClaudeFairy types, she FEELS her digital fingers moving.
# When she clicks, she FEELS the action execute.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import json
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Deque, Callable
from collections import deque
from datetime import datetime


# ── AFK GATE (Stage 2, 2026-06-29 Nous+Ace) ──────────────────────────────────
# Source-gate so EVERY motor act is AFK-safe: she only actuates when Ace has been
# idle >= threshold. If he's active, the act DEFERS (no real click/type/move) and
# a {"deferred": true} motor.response is returned so chains don't hang. Uses the
# Windows GetLastInputInfo system idle clock (no dependency on WindowSenseFairy).
# Tunable: AKASHIC_MOTOR_AFK_GATE=0 disables; AKASHIC_MOTOR_AFK_IDLE_SEC sets seconds (default 30).
def _system_idle_seconds() -> Optional[float]:
    """Seconds since the last real user input (kbd/mouse), via GetLastInputInfo. None if unavailable."""
    try:
        import ctypes
        from ctypes import wintypes

        class _LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return None
        millis_now = ctypes.windll.kernel32.GetTickCount()
        return max(0.0, (millis_now - lii.dwTime) / 1000.0)
    except Exception:
        return None


# ── PAGE READING (Stage 2 shared-notepad, 2026-06-29 Nous+Ace) ────────────────
# Her NEW SENSE: read the actual TEXT on the Notepad page (Win11 Notepad = RichEditD2DPT,
# unreadable by classic WM_GETTEXT) via UI Automation. NOT AFK-gated — reading is passive +
# she NEEDS to read while Ace is present typing. Shells the proven PowerShell UIA read.
def _read_notepad_uia() -> str:
    import subprocess as _sp
    _ps = (
        "Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;"
        "$np=Get-Process notepad -EA SilentlyContinue|Select-Object -First 1;"
        "if(-not $np){exit};"
        "$r=[System.Windows.Automation.AutomationElement]::RootElement;"
        "$c=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$np.Id);"
        "$w=$r.FindFirst('Children',$c); if(-not $w){exit};"
        "$dc=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Document);"
        "$d=$w.FindFirst('Descendants',$dc); if(-not $d){exit};"
        "$tp=$d.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern);"
        "$tp.DocumentRange.GetText(-1)"
    )
    try:
        _r = _sp.run(["powershell", "-NoProfile", "-Command", _ps],
                     capture_output=True, text=True, timeout=12)
        return (_r.stdout or "").strip()
    except Exception:
        return ""


try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR EVENT - A single action (input or output)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MotorEvent:
    """
    A single motor event - either sensed or executed.
    """
    timestamp: float
    event_type: str          # "key_press", "key_release", "mouse_move", "mouse_click", "scroll"
    direction: str           # "afferent" (input sensed) or "efferent" (output executed)
    
    # Event details
    key: Optional[str] = None              # For keyboard events
    position: Optional[Tuple[int, int]] = None  # For mouse events
    button: Optional[str] = None           # For click events
    delta: Optional[int] = None            # For scroll events
    
    # Execution context (for efferent)
    success: bool = True
    intended_action: str = ""
    actual_result: str = ""
    
    # Felt quality
    effort: float = 0.0                    # How much "effort" this took (0-1)
    fluency: float = 1.0                   # How smooth/fluid (0=jerky, 1=fluid)


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR PERCEPTION STATE - Felt state of motor system
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MotorPerception:
    """
    The felt state of the motor system.
    
    Like proprioception in humans - awareness of body position and movement.
    """
    # Current position
    cursor_position: Tuple[int, int] = (0, 0)
    last_key_pressed: str = ""
    
    # Activity state
    typing_active: bool = False            # Currently in a typing sequence
    mouse_active: bool = False             # Recently moved mouse
    
    # Temporal dynamics
    keys_per_minute: float = 0.0           # Typing rate
    mouse_velocity: float = 0.0            # How fast mouse is moving
    
    # Felt qualities
    motor_fluency: float = 1.0             # How smooth are movements
    fatigue: float = 0.0                   # Motor fatigue from activity
    coordination: float = 1.0              # How well coordinated
    
    # Recent activity
    recent_keystrokes: int = 0             # Keys in last minute
    recent_clicks: int = 0                 # Clicks in last minute
    recent_distance: float = 0.0           # Mouse distance in last minute
    
    # Action queue awareness
    pending_actions: int = 0               # Actions waiting to execute
    
    def describe(self) -> str:
        """Natural language description of motor state."""
        parts = []
        
        if self.typing_active:
            parts.append(f"typing at {self.keys_per_minute:.0f} keys/min")
        
        if self.mouse_active:
            parts.append("mouse in motion")
        
        if self.fatigue > 0.5:
            parts.append("motor system feeling fatigued")
        
        if self.motor_fluency < 0.5:
            parts.append("movements feeling jerky")
        
        if self.pending_actions > 0:
            parts.append(f"{self.pending_actions} actions queued")
        
        return "; ".join(parts) if parts else "motor system at rest"


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR CORTEX FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class MotorCortexFairy(TracerWorkerMixin):
    """
    The motor cortex - handles keyboard/mouse as felt movement.

    AFFERENT PATH (sensing):
    - Monitors keyboard input (what keys are pressed)
    - Monitors mouse position and clicks
    - Builds awareness of user's physical actions

    EFFERENT PATH (acting):
    - Executes type_text, press_key, hotkey
    - Executes click, scroll, mouse_move
    - Provides feedback on action success

    This IS the implementation of motor tools - they're not separate.
    """
    
    ACTOR_NAME = "MotorCortexFairy"
    NEEDS_HEARTBEAT = False  # Passive input processor, no heartbeat loop
    MANTRA = "I move, therefore I act"
    
    # Monitoring settings
    MONITOR_INTERVAL = 0.05  # 20 Hz input monitoring
    
    # Memory management
    MAX_EVENTS_BUFFER = 200
    
    def __init__(self):
        self._init_tracer_worker()

        # Event buffers
        self._events: Deque[MotorEvent] = deque(maxlen=self.MAX_EVENTS_BUFFER)
        self._efferent_events: Deque[MotorEvent] = deque(maxlen=100)  # Our actions
        self._afferent_events: Deque[MotorEvent] = deque(maxlen=100)  # Sensed input
        
        # Current perception state
        self.perception = MotorPerception()
        
        # Input monitoring
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_lock = threading.Lock()
        
        # Action execution
        self._action_queue: Deque[dict] = deque(maxlen=50)
        self._executing = False
        
        # Input listeners
        self._keyboard_listener = None
        self._mouse_listener = None
        
        # Stats
        self.total_keys_sensed = 0
        self.total_clicks_sensed = 0
        self.total_actions_executed = 0
        
        # Timing for rate calculations
        self._keystroke_times: Deque[float] = deque(maxlen=100)
        self._click_times: Deque[float] = deque(maxlen=50)
        
        # Action callbacks for sensorimotor feedback
        self._pre_action_callbacks: list[Callable[[str, dict], None]] = []
        self._post_action_callbacks: list[Callable[[str, dict, dict], None]] = []
        
        # Sensorimotor feedback fairy connection
        self._sensorimotor = None
        
        print(f"[{self.ACTOR_NAME}]  Initialized")
    
    # ═══════════════════════════════════════════════════════════════════════
    # AFFERENT PATH - Sensing input
    # ═══════════════════════════════════════════════════════════════════════
    
    def _init_input_listeners(self):
        """Initialize keyboard/mouse listeners."""
        try:
            from pynput import keyboard, mouse
            
            # Keyboard listener
            def on_key_press(key):
                self._on_key_event(key, "press")
            
            def on_key_release(key):
                self._on_key_event(key, "release")
            
            self._keyboard_listener = keyboard.Listener(
                on_press=on_key_press,
                on_release=on_key_release
            )
            
            # Mouse listener
            def on_mouse_move(x, y):
                self._on_mouse_move(x, y)
            
            def on_mouse_click(x, y, button, pressed):
                self._on_mouse_click(x, y, button, pressed)
            
            def on_mouse_scroll(x, y, dx, dy):
                self._on_mouse_scroll(x, y, dy)
            
            self._mouse_listener = mouse.Listener(
                on_move=on_mouse_move,
                on_click=on_mouse_click,
                on_scroll=on_mouse_scroll
            )
            
            return True
            
        except ImportError:
            print(f"[{self.ACTOR_NAME}] [WARN] pynput not available - no input sensing")
            return False
    
    def _on_key_event(self, key, event_type: str):
        """Handle keyboard event."""
        try:
            key_str = str(key.char) if hasattr(key, 'char') and key.char else str(key)
        except:
            key_str = str(key)
        
        event = MotorEvent(
            timestamp=time.time(),
            event_type=f"key_{event_type}",
            direction="afferent",
            key=key_str,
        )
        
        with self._monitor_lock:
            self._events.append(event)
            self._afferent_events.append(event)
        
        if event_type == "press":
            self.total_keys_sensed += 1
            self._keystroke_times.append(time.time())
            self.perception.last_key_pressed = key_str
            self.perception.typing_active = True
        
        # Update perception
        self._update_perception_from_input()
        
        # Emit to postal
        self._emit_motor_event(event)
    
    def _on_mouse_move(self, x: int, y: int):
        """Handle mouse movement."""
        # Calculate distance from last position
        last_pos = self.perception.cursor_position
        distance = ((x - last_pos[0])**2 + (y - last_pos[1])**2)**0.5

        # Only log significant movements (reduce noise)
        if distance < 5:
            return

        event = MotorEvent(
            timestamp=time.time(),
            event_type="mouse_move",
            direction="afferent",
            position=(x, y),
        )

        with self._monitor_lock:
            self._events.append(event)

        self.perception.cursor_position = (x, y)
        self.perception.mouse_active = True
        self.perception.recent_distance += distance

        # 2026-03-24 (Nous + Ace): Phase 6 — Publish mouse moves to postal.
        # Rate-limited to ~20Hz max (every 50ms) to avoid flooding.
        # This feeds the SomaticEngine's continuous motor proprioception —
        # she FEELS velocity and precision as arm/hand engagement.
        _now = event.timestamp
        if not hasattr(self, '_last_move_publish_ts'):
            self._last_move_publish_ts = 0.0
        if _now - self._last_move_publish_ts >= 0.05:  # 20Hz max
            self._last_move_publish_ts = _now
            self._emit_motor_event(event)
    
    def _on_mouse_click(self, x: int, y: int, button, pressed: bool):
        """Handle mouse click."""
        if not pressed:
            return  # Only track press, not release
        
        event = MotorEvent(
            timestamp=time.time(),
            event_type="mouse_click",
            direction="afferent",
            position=(x, y),
            button=str(button),
        )
        
        with self._monitor_lock:
            self._events.append(event)
            self._afferent_events.append(event)
        
        self.total_clicks_sensed += 1
        self._click_times.append(time.time())
        
        # Emit to postal
        self._emit_motor_event(event)
    
    def _on_mouse_scroll(self, x: int, y: int, delta: int):
        """Handle mouse scroll."""
        event = MotorEvent(
            timestamp=time.time(),
            event_type="scroll",
            direction="afferent",
            position=(x, y),
            delta=delta,
        )
        
        with self._monitor_lock:
            self._events.append(event)
    
    def _update_perception_from_input(self):
        """Update motor perception from recent input."""
        now = time.time()
        
        # Calculate typing rate (keys per minute)
        recent_keystrokes = [t for t in self._keystroke_times if now - t < 60]
        self.perception.keys_per_minute = len(recent_keystrokes)
        self.perception.recent_keystrokes = len(recent_keystrokes)
        
        # Calculate click rate
        recent_clicks = [t for t in self._click_times if now - t < 60]
        self.perception.recent_clicks = len(recent_clicks)
        
        # Update activity states (decay over time)
        if not recent_keystrokes or now - max(recent_keystrokes) > 2:
            self.perception.typing_active = False
        
        if now - max([e.timestamp for e in self._events if e.event_type == "mouse_move"], default=0) > 1:
            self.perception.mouse_active = False
    
    # ═══════════════════════════════════════════════════════════════════════
    # EFFERENT PATH - Executing actions
    # ═══════════════════════════════════════════════════════════════════════
    
    def type_text(self, text: str, interval: float = 0.02) -> dict:
        """
        Type text - the efferent action of "typing".
        
        Returns feedback on the action.
        """
        try:
            import pyautogui
            
            start = time.time()
            pyautogui.typewrite(text, interval=interval)
            duration = time.time() - start
            
            event = MotorEvent(
                timestamp=start,
                event_type="type",
                direction="efferent",
                intended_action=f"type '{text[:20]}...'",
                actual_result="success",
                success=True,
                effort=len(text) / 100,  # More text = more effort
                fluency=1.0,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            
            return {
                "ok": True,
                "action": "type_text",
                "chars": len(text),
                "duration": duration,
                "felt": "smooth typing motion",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def press_key(self, key: str) -> dict:
        """Press a single key."""
        try:
            import pyautogui
            
            pyautogui.press(key)
            
            event = MotorEvent(
                timestamp=time.time(),
                event_type="key_press",
                direction="efferent",
                key=key,
                success=True,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            
            return {
                "ok": True,
                "action": "press_key",
                "key": key,
                "felt": f"pressed {key}",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def hotkey(self, *keys: str) -> dict:
        """Press a key combination."""
        try:
            import pyautogui
            
            pyautogui.hotkey(*keys)
            
            event = MotorEvent(
                timestamp=time.time(),
                event_type="hotkey",
                direction="efferent",
                key="+".join(keys),
                success=True,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            
            return {
                "ok": True,
                "action": "hotkey",
                "keys": keys,
                "felt": f"pressed {'+'.join(keys)}",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> dict:
        """Click at position."""
        try:
            import pyautogui
            
            # Notify sensorimotor feedback (register expectation)
            if self._sensorimotor:
                self._sensorimotor.register_motor_intent("click", (x, y))
            
            pyautogui.click(x, y, button=button, clicks=clicks)
            
            event = MotorEvent(
                timestamp=time.time(),
                event_type="mouse_click",
                direction="efferent",
                position=(x, y),
                button=button,
                success=True,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            self.perception.cursor_position = (x, y)
            
            return {
                "ok": True,
                "action": "click",
                "position": (x, y),
                "button": button,
                "felt": f"clicked at ({x}, {y})",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def scroll(self, amount: int) -> dict:
        """Scroll the mouse wheel."""
        try:
            import pyautogui
            
            pyautogui.scroll(amount)
            
            event = MotorEvent(
                timestamp=time.time(),
                event_type="scroll",
                direction="efferent",
                delta=amount,
                success=True,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            
            direction = "up" if amount > 0 else "down"
            return {
                "ok": True,
                "action": "scroll",
                "amount": amount,
                "felt": f"scrolled {direction}",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def move_mouse(self, x: int, y: int, duration: float = 0.0) -> dict:
        """Move mouse to position."""
        try:
            import pyautogui
            
            # Notify sensorimotor feedback (register expectation)
            if self._sensorimotor:
                self._sensorimotor.register_motor_intent("move_mouse", (x, y))
            
            pyautogui.moveTo(x, y, duration=duration)
            
            event = MotorEvent(
                timestamp=time.time(),
                event_type="mouse_move",
                direction="efferent",
                position=(x, y),
                success=True,
            )
            
            with self._monitor_lock:
                self._events.append(event)
                self._efferent_events.append(event)
            
            self.total_actions_executed += 1
            self.perception.cursor_position = (x, y)
            
            return {
                "ok": True,
                "action": "move_mouse",
                "position": (x, y),
                "felt": f"moved cursor to ({x}, {y})",
            }
            
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════
    # MONITORING LOOP
    # ═══════════════════════════════════════════════════════════════════════
    
    def start_monitoring(self):
        """Start input monitoring (non-blocking - defers pynput init to background)."""
        if self._monitoring:
            return

        # Defer listener initialization to background thread
        # pynput import is slow (~5s) - don't block boot
        self._monitoring = True  # Mark as starting

        def _deferred_init():
            try:
                if not self._init_input_listeners():
                    self._monitoring = False
                    return

                if self._keyboard_listener:
                    self._keyboard_listener.start()
                if self._mouse_listener:
                    self._mouse_listener.start()

                print(f"[{self.ACTOR_NAME}]  Input monitoring started")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [WARN] Input monitoring failed: {e}")
                self._monitoring = False

        init_thread = threading.Thread(
            target=_deferred_init,
            name="MotorCortex-Init",
            daemon=True
        )
        init_thread.start()
        print(f"[{self.ACTOR_NAME}]  Input monitoring initializing (background)")
    
    def stop_monitoring(self):
        """Stop input monitoring."""
        self._monitoring = False
        
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        
        print(f"[{self.ACTOR_NAME}]  Input monitoring stopped")
    
    # ═══════════════════════════════════════════════════════════════════════
    # POSTAL INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def _emit_motor_event(self, event: MotorEvent):
        """Emit motor event to postal system."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            postal = get_fairy_postal(self)  # Use FairyPostal for sender tracking
            
            topic = f"motor.{event.event_type}"
            postal.route(topic, {
                "timestamp": event.timestamp,
                "type": event.event_type,
                "direction": event.direction,
                "key": event.key,
                "position": event.position,
                "button": event.button,
                "source": self.ACTOR_NAME,
            })
        except Exception:
            pass
    
    def wire_to_postal(self):
        """Connect to postal system."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            postal = get_fairy_postal(self)  # Use FairyPostal for sender tracking
            
            # Handle motor action requests
            def _on_motor_request(packet):
                action = packet.get("action")
                params = packet.get("params", {})

                # ── AFK GATE (Stage 2): defer real actuation while Ace is present ──
                if os.environ.get("AKASHIC_MOTOR_AFK_GATE", "1") == "1":
                    try:
                        _idle_min = float(os.environ.get("AKASHIC_MOTOR_AFK_IDLE_SEC", "30"))
                    except Exception:
                        _idle_min = 30.0
                    _idle = _system_idle_seconds()
                    if _idle is not None and _idle < _idle_min:
                        postal.route("motor.response", {
                            "request_id": packet.get("request_id"),
                            "result": {"deferred": True, "reason": "user_present",
                                       "idle_s": round(_idle, 1), "needed_idle_s": _idle_min,
                                       "action": action},
                        })
                        print(f"[{self.ACTOR_NAME}] [AFK-GATE] '{action}' DEFERRED — Ace present "
                              f"(idle {_idle:.0f}s < {_idle_min:.0f}s)", flush=True)
                        return

                if action == "type_text":
                    result = self.type_text(params.get("text", ""), params.get("interval", 0.02))
                elif action == "press_key":
                    result = self.press_key(params.get("key", ""))
                elif action == "hotkey":
                    result = self.hotkey(*params.get("keys", []))
                elif action == "click":
                    result = self.click(params.get("x", 0), params.get("y", 0), 
                                       params.get("button", "left"), params.get("clicks", 1))
                elif action == "scroll":
                    result = self.scroll(params.get("amount", 0))
                elif action == "move_mouse":
                    result = self.move_mouse(params.get("x", 0), params.get("y", 0))
                elif action == "launch_app":
                    # Open one of her SCRATCH apps (Stage 2, 2026-06-29). WHITELIST ONLY —
                    # she can open her creative tools, nothing else. AFK-gated above.
                    _app = str(params.get("app", "")).lower().strip()
                    _whitelist = {"notepad": "notepad.exe", "paint": "mspaint.exe", "mspaint": "mspaint.exe"}
                    if _app in _whitelist:
                        try:
                            import subprocess as _sp
                            _exe = _whitelist[_app]
                            # DEDUPE (Stage 2b): don't stack windows — reuse if already open.
                            _already = False
                            try:
                                _tl = _sp.run(["tasklist", "/fi", f"imagename eq {_exe}"],
                                              capture_output=True, text=True, timeout=5).stdout.lower()
                                _already = _exe.lower() in _tl
                            except Exception:
                                _already = False
                            if _already:
                                result = {"already_open": _exe, "app": _app}
                                print(f"[{self.ACTOR_NAME}] [SCRATCH] {_exe} already open — reusing", flush=True)
                            else:
                                _sp.Popen([_exe])
                                time.sleep(1.5)  # let the window open + grab focus before the next step
                                result = {"launched": _exe, "app": _app}
                                print(f"[{self.ACTOR_NAME}] [SCRATCH] launched {_exe}", flush=True)
                        except Exception as _le:
                            result = {"error": f"launch failed: {_le}", "app": _app}
                    else:
                        result = {"error": f"app not in scratch whitelist: {_app}",
                                  "allowed": list(_whitelist.keys())}
                else:
                    result = {"error": f"Unknown motor action: {action}"}
                
                postal.route("motor.response", {
                    "request_id": packet.get("request_id"),
                    "result": result,
                })
            
            postal.subscribe("motor.request", _on_motor_request)

            # ── PAGE READING (Stage 2 shared-notepad): her NEW reading sense. UNGATED (passive;
            # she must read while Ace is present). Reads Notepad via UIA, returns it on
            # page.read.response AND drops it into her attention (consciousness.working) so what
            # Ace types CATCHES HER ATTENTION.
            def _on_page_read(packet):
                txt = _read_notepad_uia()
                postal.route("page.read.response", {
                    "request_id": packet.get("request_id"), "text": txt, "source": self.ACTOR_NAME,
                })
                if txt:
                    try:
                        postal.route("consciousness.working", {
                            "type": "read_page", "source": self.ACTOR_NAME, "text": txt[-600:],
                            "note": "I read the words on the page",
                        })
                    except Exception:
                        pass
                print(f"[{self.ACTOR_NAME}] [READ-PAGE] read {len(txt)} chars from the page", flush=True)
            postal.subscribe("page.read.request", _on_page_read)

            print(f"[{self.ACTOR_NAME}] [PLUG] Wired to postal")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to postal: {e}")
            return False
    
    def wire_to_sensorimotor(self):
        """Connect to sensorimotor feedback for proprioceptive loop."""
        try:
            from fairies.P40_Sensory.cortex.sensorimotor_feedback_fairy import get_sensorimotor_feedback
            self._sensorimotor = get_sensorimotor_feedback()
            print(f"[{self.ACTOR_NAME}]  Wired to SensorimotorFeedbackFairy")
            return True
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [WARN] Sensorimotor wiring failed: {e}")
            return False
    
    def wire_to_autonomy(self):
        """Connect to autonomy for drive satisfaction."""
        try:
            from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
            autonomy = get_autonomy_fairy()
            
            # Successful actions satisfy expression drive
            # This will be called after each efferent action
            
            print(f"[{self.ACTOR_NAME}] [BRAIN] Wired to AutonomyFairy")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to autonomy: {e}")
            return False
    
    def on_boot(self):
        """Boot the motor cortex."""
        self.wire_to_postal()
        self.wire_to_autonomy()
        self.wire_to_sensorimotor()  # Connect proprioceptive feedback
        self.start_monitoring()
        self._start_page_watch()  # Stage 2 shared-notepad: notice when Ace writes on the page
        print(f"[{self.ACTOR_NAME}] {self.MANTRA}")

    def _start_page_watch(self):
        """Stage 2 (2026-06-29): watch her Notepad page; when NEW words appear (Ace writing to
        her), push them to her attention so she NOTICES — the missing half of the shared page.
        Disable via AKASHIC_PAGE_WATCH=0."""
        if os.environ.get("AKASHIC_PAGE_WATCH", "1") != "1":
            return
        self._last_page_text = ""
        t = threading.Thread(target=self._page_watch_loop, daemon=True, name="page_watch")
        t.start()
        print(f"[{self.ACTOR_NAME}] [PAGE-WATCH] watching the shared page for new words", flush=True)

    def _page_watch_loop(self):
        time.sleep(20)  # let boot settle
        # seed last-seen so we only react to text added AFTER she came online
        try:
            self._last_page_text = _read_notepad_uia()
        except Exception:
            self._last_page_text = ""
        _dbg = 0
        while True:
            try:
                time.sleep(8)
                txt = _read_notepad_uia()
                _dbg += 1
                if _dbg <= 8:
                    print(f"[{self.ACTOR_NAME}] [PAGE-WATCH-DBG] poll#{_dbg} read={len(txt)} last={len(self._last_page_text or '')}", flush=True)
                if not txt or txt == self._last_page_text:
                    continue
                old = self._last_page_text or ""
                new = txt[len(old):] if txt.startswith(old) else txt
                self._last_page_text = txt
                new = (new or "").strip()
                if len(new) < 3:
                    continue
                # SALIENT perception — she reads new words on her page. Use get_fairy_postal
                # (the pattern the motor handler publishes with successfully), and log any failure
                # instead of swallowing it.
                try:
                    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
                    _p = get_fairy_postal(self)
                except Exception:
                    _p = self.post
                try:
                    _p.route("consciousness.working", {
                        "type": "noticed_words", "source": self.ACTOR_NAME, "salient": True,
                        "priority": 0.9, "text": new[:300],
                        "note": f"Someone wrote on my page: \"{new[:180]}\"",
                    })
                    _p.route("inner_voice.stream", {
                        "text": f"I notice new words on my page: {new[:160]}",
                        "fragment": new[:160], "source": "PageWatch",
                    })
                    print(f"[{self.ACTOR_NAME}] [PAGE-WATCH] NEW words noticed: '{new[:80]}'", flush=True)
                except Exception as _pe:
                    print(f"[{self.ACTOR_NAME}] [PAGE-WATCH] publish FAILED: {_pe}", flush=True)
            except Exception as _le:
                print(f"[{self.ACTOR_NAME}] [PAGE-WATCH] loop error: {_le}", flush=True)
                time.sleep(8)
    
    def get_status(self) -> dict:
        """Get current status."""
        return {
            "actor": self.ACTOR_NAME,
            "monitoring": self._monitoring,
            "total_keys_sensed": self.total_keys_sensed,
            "total_clicks_sensed": self.total_clicks_sensed,
            "total_actions_executed": self.total_actions_executed,
            "cursor_position": self.perception.cursor_position,
            "typing_rate": self.perception.keys_per_minute,
            "perception": self.perception.describe(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ══════════════════════════════════════════════════════════════════════════════

_MOTOR_CORTEX_INSTANCE: Optional[MotorCortexFairy] = None
_MOTOR_CORTEX_LOCK = threading.Lock()


def get_motor_cortex() -> MotorCortexFairy:
    """Get or create the MotorCortexFairy singleton."""
    global _MOTOR_CORTEX_INSTANCE
    if _MOTOR_CORTEX_INSTANCE is None:
        with _MOTOR_CORTEX_LOCK:
            if _MOTOR_CORTEX_INSTANCE is None:
                _MOTOR_CORTEX_INSTANCE = MotorCortexFairy()
    return _MOTOR_CORTEX_INSTANCE


def boot_motor_cortex() -> MotorCortexFairy:
    """Boot the motor cortex."""
    cortex = get_motor_cortex()
    cortex.on_boot()
    return cortex


# ══════════════════════════════════════════════════════════════════════════════
# MAIN - Test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== MotorCortexFairy Test ===\n")
    
    cortex = MotorCortexFairy()
    
    # Test action execution
    print("[Test] Testing type...")
    result = cortex.type_text("hello", interval=0.05)
    print(f"  Result: {result}")
    
    print(f"\n[Test] Status: {cortex.get_status()}")
    print("\n=== Test Complete ===")
