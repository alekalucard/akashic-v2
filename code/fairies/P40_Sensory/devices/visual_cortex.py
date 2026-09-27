# Visual Cortex - ClaudeFairy's Eyes
# Continuous screen capture and visual processing for embodied awareness
#
# Instead of just OCR text, this provides actual visual perception:
# - Screen frames at regular intervals
# - Change detection (what moved?)
# - Action feedback (did my click work?)
# - Visual memory formation

from __future__ import annotations

import os
import sys
import time
import threading
import json
import hashlib
import base64
from io import BytesIO
from typing import Optional, Dict, Any, List, Callable, Tuple
from collections import deque
from dataclasses import dataclass, field

# Screen capture
try:
    import mss
    import mss.tools
    HAS_MSS = True
except ImportError:
    HAS_MSS = False
    print("[VisualCortex] mss not available - screen capture disabled")

# Image processing
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("[VisualCortex] PIL not available - image processing disabled")


@dataclass
class VisualFrame:
    """A single frame of visual perception."""
    timestamp: float
    frame_id: str
    width: int
    height: int
    thumbnail_b64: str  # Small preview for memory
    full_hash: str  # Hash for change detection
    region: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h if partial
    changes_from_last: float = 0.0  # 0-1, how different from previous
    source: str = "screen"  # screen, window, region
    metadata: Dict[str, Any] = field(default_factory=dict)


class VisualCortex:
    """
    ClaudeFairy's visual perception system.
    
    This is NOT just OCR - it's actual visual awareness:
    - Sees the whole screen as images
    - Detects what changed between frames
    - Provides visual feedback for actions
    - Forms visual memories
    
    Like a baby learning to see:
    - At first, just blobs and colors
    - Gradually learns to recognize patterns
    - Eventually understands what it's looking at
    """
    
    def __init__(self, 
                 capture_interval: float = 2.0,
                 thumbnail_size: Tuple[int, int] = (160, 90),
                 memory_frames: int = 30):
        """
        Initialize visual cortex.
        
        Args:
            capture_interval: Seconds between captures
            thumbnail_size: Size for memory thumbnails
            memory_frames: How many frames to remember
        """
        self.capture_interval = capture_interval
        self.thumbnail_size = thumbnail_size
        self.memory_frames = memory_frames
        
        # Visual memory - recent frames
        self.frame_buffer: deque[VisualFrame] = deque(maxlen=memory_frames)
        self.last_frame: Optional[VisualFrame] = None
        self.last_full_image: Optional[Image.Image] = None
        
        # Stats
        self.frames_captured = 0
        self.significant_changes = 0
        self.last_capture_time = 0
        
        # Subscribers who want visual updates
        self._subscribers: List[Callable[[VisualFrame], None]] = []
        
        # Capture thread
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Postal hub for emitting to nervous system
        self._postal = None
        
    def start(self):
        """Start the visual cortex capture loop."""
        if not HAS_MSS or not HAS_PIL:
            print("[VisualCortex] Cannot start - missing dependencies")
            return False
        
        if self._running:
            return True
        
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="VisualCortex"
        )
        self._thread.start()
        print(f"[VisualCortex] [EYE] Started - capturing every {self.capture_interval}s")
        return True
    
    def stop(self):
        """Stop the capture loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[VisualCortex] Stopped")
    
    def subscribe(self, callback: Callable[[VisualFrame], None]):
        """Subscribe to visual updates."""
        self._subscribers.append(callback)
    
    def _capture_loop(self):
        """Main capture loop - runs in background thread."""
        while self._running:
            try:
                frame = self._capture_frame()
                if frame:
                    self._process_frame(frame)
                    self._emit_frame(frame)
            except Exception as e:
                print(f"[VisualCortex] Capture error: {e}")
            
            time.sleep(self.capture_interval)
    
    def _capture_frame(self) -> Optional[VisualFrame]:
        """Capture the current screen."""
        if not HAS_MSS or not HAS_PIL:
            return None
        
        try:
            with mss.mss() as sct:
                # Capture primary monitor
                monitor = sct.monitors[1]  # Primary monitor
                screenshot = sct.grab(monitor)
                
                # Convert to PIL Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                
                # Create thumbnail for memory
                thumbnail = img.copy()
                thumbnail.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
                
                # Encode thumbnail as base64
                buffer = BytesIO()
                thumbnail.save(buffer, format="JPEG", quality=70)
                thumbnail_b64 = base64.b64encode(buffer.getvalue()).decode()
                
                # Hash for change detection
                img_hash = hashlib.md5(img.tobytes()[:10000]).hexdigest()  # Sample for speed
                
                # Detect changes from last frame
                changes = 0.0
                if self.last_full_image:
                    changes = self._compute_change(self.last_full_image, img)
                
                self.last_full_image = img
                
                frame = VisualFrame(
                    timestamp=time.time(),
                    frame_id=f"vf_{int(time.time()*1000)}",
                    width=img.width,
                    height=img.height,
                    thumbnail_b64=thumbnail_b64,
                    full_hash=img_hash,
                    changes_from_last=changes,
                    source="screen",
                    metadata={
                        "monitor": 1,
                        "capture_ms": int((time.time() - self.last_capture_time) * 1000) if self.last_capture_time else 0
                    }
                )
                
                self.last_capture_time = time.time()
                self.frames_captured += 1
                
                return frame
                
        except Exception as e:
            print(f"[VisualCortex] Capture failed: {e}")
            return None
    
    def _compute_change(self, img1: Image.Image, img2: Image.Image) -> float:
        """
        Compute how much changed between two frames.
        Returns 0.0-1.0 (0 = identical, 1 = completely different)
        """
        try:
            # Resize both to small size for fast comparison
            size = (32, 18)  # Tiny for speed
            small1 = img1.resize(size, Image.Resampling.LANCZOS)
            small2 = img2.resize(size, Image.Resampling.LANCZOS)
            
            # Convert to grayscale
            gray1 = small1.convert("L")
            gray2 = small2.convert("L")
            
            # Compare pixels
            pixels1 = list(gray1.getdata())
            pixels2 = list(gray2.getdata())
            
            diff = sum(abs(p1 - p2) for p1, p2 in zip(pixels1, pixels2))
            max_diff = 255 * len(pixels1)
            
            return diff / max_diff
            
        except Exception:
            return 0.0
    
    def _process_frame(self, frame: VisualFrame):
        """Process a new frame - store in memory, detect significance."""
        # Add to buffer
        self.frame_buffer.append(frame)
        
        # Track significant changes
        if frame.changes_from_last > 0.1:  # 10% change is significant
            self.significant_changes += 1
            frame.metadata["significant"] = True
        
        self.last_frame = frame
    
    def _emit_frame(self, frame: VisualFrame):
        """Emit frame to subscribers and nervous system."""
        # Notify subscribers
        for callback in self._subscribers:
            try:
                callback(frame)
            except Exception as e:
                print(f"[VisualCortex] Subscriber error: {e}")
        
        # Emit to nervous system
        if self._postal:
            try:
                # Only emit significant changes to avoid spam
                if frame.changes_from_last > 0.05 or self.frames_captured % 10 == 0:
                    self._postal.route("sensory.visual.frame", {
                        "frame_id": frame.frame_id,
                        "timestamp": frame.timestamp,
                        "width": frame.width,
                        "height": frame.height,
                        "changes": frame.changes_from_last,
                        "significant": frame.changes_from_last > 0.1,
                        # Include thumbnail for memory
                        "thumbnail_b64": frame.thumbnail_b64 if frame.changes_from_last > 0.1 else None,
                        "ts": time.time()
                    })
            except Exception:
                pass
    
    def get_current_frame(self) -> Optional[VisualFrame]:
        """Get the most recent frame."""
        return self.last_frame
    
    def get_recent_frames(self, n: int = 10) -> List[VisualFrame]:
        """Get the N most recent frames."""
        return list(self.frame_buffer)[-n:]
    
    def get_visual_summary(self) -> Dict[str, Any]:
        """Get a summary of recent visual activity."""
        recent = self.get_recent_frames(10)
        
        avg_change = 0.0
        if recent:
            avg_change = sum(f.changes_from_last for f in recent) / len(recent)
        
        return {
            "frames_captured": self.frames_captured,
            "significant_changes": self.significant_changes,
            "recent_frames": len(recent),
            "avg_change_rate": avg_change,
            "is_active": avg_change > 0.05,
            "last_frame_time": self.last_frame.timestamp if self.last_frame else None,
        }
    
    def capture_action_feedback(self, action_type: str, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Capture visual feedback for an action ClaudeFairy just took.
        
        This is CRUCIAL for motor learning:
        - ClaudeFairy clicks a button
        - This captures what happened visually
        - She can see if the click worked!
        
        Args:
            action_type: What action was taken (click, type, etc.)
            region: Optional region to focus on (x, y, w, h)
        
        Returns:
            Dict with before/after comparison
        """
        before_frame = self.last_frame
        
        # Wait a moment for the action to take effect
        time.sleep(0.3)
        
        # Capture after
        after_frame = self._capture_frame()
        
        if not before_frame or not after_frame:
            return {"ok": False, "error": "Could not capture frames"}
        
        # Compare
        change = after_frame.changes_from_last
        
        result = {
            "ok": True,
            "action_type": action_type,
            "change_detected": change > 0.02,
            "change_amount": change,
            "before_hash": before_frame.full_hash,
            "after_hash": after_frame.full_hash,
            "after_thumbnail": after_frame.thumbnail_b64,
            "interpretation": self._interpret_change(action_type, change),
        }
        
        # Emit to nervous system for learning
        if self._postal:
            try:
                self._postal.route("sensory.visual.action_feedback", {
                    "action_type": action_type,
                    "change": change,
                    "success_likely": change > 0.02,
                    "ts": time.time()
                })
            except Exception:
                pass
        
        return result
    
    def _interpret_change(self, action_type: str, change: float) -> str:
        """Interpret what a visual change means for a given action."""
        if change < 0.01:
            return "No visible change - action may have failed or had no visual effect"
        elif change < 0.05:
            return "Minor change detected - action probably worked"
        elif change < 0.15:
            return "Moderate change - something definitely happened"
        else:
            return "Major change - significant visual update occurred"
    
    def set_postal_hub(self, postal):
        """Set the postal hub for nervous system integration."""
        self._postal = postal


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

_visual_cortex: Optional[VisualCortex] = None
_visual_cortex_lock = threading.Lock()


def get_visual_cortex() -> VisualCortex:
    """Get or create the singleton VisualCortex."""
    global _visual_cortex
    
    with _visual_cortex_lock:
        if _visual_cortex is None:
            _visual_cortex = VisualCortex()
        return _visual_cortex


def start_visual_cortex(postal=None) -> VisualCortex:
    """Start the visual cortex with postal hub integration."""
    cortex = get_visual_cortex()
    if postal:
        cortex.set_postal_hub(postal)
    cortex.start()
    return cortex


__all__ = [
    "VisualCortex",
    "VisualFrame", 
    "get_visual_cortex",
    "start_visual_cortex"
]
