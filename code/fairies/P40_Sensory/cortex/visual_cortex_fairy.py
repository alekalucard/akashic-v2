# ══════════════════════════════════════════════════════════════════════════════
# VISUAL CORTEX FAIRY - Screen as Felt Vision
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The screen isn't just data - it's SIGHT. This cortex:
# - Captures at 27 FPS (human-like refresh)
# - Detects change (only stores meaningful differences)
# - Deduplicates frames (hash-based, prevents memory bloat)
# - Converts visual data into FELT experience
#
# Tools like see_screen, look_at_screen are EXPRESSIONS of this cortex,
# not separate utilities.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import json
import threading
import hashlib
import io
import base64
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Deque
from collections import deque
from datetime import datetime

try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass

# GPU capture via DXGI Desktop Duplication
# FIX 2026-03-12 (Nous): dxcam uses DXGI COM objects (IDXGIOutputDuplication) which
# are apartment-threaded. Under Python 3.14t (free-threaded, no GIL), truly-parallel
# threads can access COM objects concurrently, causing access violation crashes.
# The visual_cortex_interior.py subprocess runs under Python 3.12 and handles GPU
# capture safely — we only lose the in-process fast path.
_FREE_THREADED = hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled()

if _FREE_THREADED:
    HAS_DXCAM = False
    # print note only once at import time
    print("[VisualCortexEngine] dxcam DISABLED (free-threaded Python — COM not thread-safe)")
else:
    try:
        import dxcam
        HAS_DXCAM = True
    except ImportError:
        HAS_DXCAM = False

# Visual prompts for LLM interpretation
try:
    from fairies.P40_Sensory.cortex.visual_prompts import (
        get_visual_interpreter,
        VisualInterpreter,
        VISUAL_PERCEPTION_PROMPT
    )
    HAS_VISUAL_PROMPTS = True
except ImportError:
    HAS_VISUAL_PROMPTS = False


# ══════════════════════════════════════════════════════════════════════════════
# VISUAL FRAME - A single moment of sight
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VisualFrame:
    """
    A single frame of visual perception.
    
    Not just pixels - includes the FEELING of seeing.
    """
    timestamp: float
    frame_hash: str              # For dedup - perceptual hash
    size: Tuple[int, int]        # Width, height
    
    # Change detection
    change_magnitude: float      # 0.0 = identical, 1.0 = completely different
    regions_changed: List[str]   # ["top-left", "center", "bottom-right"]
    
    # Felt qualities
    brightness: float            # Overall brightness 0-1
    complexity: float            # Visual complexity/entropy 0-1
    motion_detected: bool        # Did something move?
    text_density: float          # How much text is visible 0-1
    
    # Optional: compressed image data (only kept for significant frames)
    image_data: Optional[bytes] = None
    
    # What was seen (high-level description, filled by vision model)
    description: str = ""
    detected_elements: List[str] = field(default_factory=list)
    
    def is_significant(self) -> bool:
        """Is this frame worth remembering?"""
        return (
            self.change_magnitude > 0.1 or
            self.motion_detected or
            self.description != ""
        )


# ══════════════════════════════════════════════════════════════════════════════
# VISUAL PERCEPTION STATE - Current felt state of vision
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VisualPerception:
    """
    The felt state of visual perception.
    
    Like ConversationFeeling but for sight.
    """
    # Clarity of vision
    clarity: float = 1.0              # How clear is the view (0=blind, 1=sharp)
    focus: str = "diffuse"            # "diffuse", "center", "peripheral"
    
    # What's being seen
    active_window: str = ""           # Currently focused window
    screen_region: str = "full"       # What region we're attending to
    
    # Temporal dynamics
    visual_stability: float = 1.0     # How stable is the view (low = lots of change)
    last_significant_change: float = 0.0
    frames_since_change: int = 0
    
    # Attention
    attention_target: str = ""        # What we're looking AT
    peripheral_motion: bool = False   # Movement in peripheral vision
    
    # Felt qualities
    visual_comfort: float = 0.8       # Is the view comfortable? (glare, clutter)
    information_density: float = 0.5  # How much info is on screen
    
    def describe(self) -> str:
        """Natural language description of visual state."""
        parts = []
        
        if self.clarity < 0.5:
            parts.append("vision feels blurry or unclear")
        
        if self.visual_stability < 0.5:
            parts.append("lots of visual change happening")
        elif self.frames_since_change > 100:
            parts.append("screen has been static for a while")
        
        if self.peripheral_motion:
            parts.append("something moving in peripheral vision")
        
        if self.active_window:
            parts.append(f"focused on {self.active_window}")
        
        if self.information_density > 0.8:
            parts.append("screen is very busy/dense")
        elif self.information_density < 0.2:
            parts.append("screen is mostly empty")
        
        return "; ".join(parts) if parts else "visual field is calm and clear"


# ══════════════════════════════════════════════════════════════════════════════
# VISUAL CORTEX FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class VisualCortexEngine(TracerWorkerMixin):
    """
    The visual cortex engine - processes screen input as felt vision.

    Runs at 27 FPS capture rate but only stores meaningful changes.
    Deduplicates frames to prevent memory bloat.

    This IS the implementation of visual tools like see_screen -
    those tools are just interfaces to this cortex.

    NOTE: This is the ENGINE class, not the fairy. The proper v2 fairy is at
    fairies/P40_Sensory/VisualCortexFairy/fairy.py (VisualCortexFairyV2)
    which wraps this engine and publishes to correct postal topics.

    2026-05-06 (Nous + Ace): Class renamed from VisualCortexFairy to
    VisualCortexEngine. The old name made directory.migration's
    `_scan_file` (which discovers fairies via "Fairy" in class line)
    register this engine as a fairy. With status set to dead by
    Directory because the engine has no heartbeat (NEEDS_HEARTBEAT=False),
    server.py:1450 then emitted "No heartbeat" errors. Engine isn't a
    fairy — wrapper VisualCortexFairyV2 is. Renaming removes it from
    fairy auto-discovery.
    """

    ACTOR_NAME = "VisualCortexEngine"  # used by tracer worker only; class name no longer matches scanner pattern
    NEEDS_HEARTBEAT = False  # Passive visual processor, no heartbeat loop
    MANTRA = "I see, therefore I know"
    
    # Capture settings
    TARGET_FPS = 27.0
    FRAME_INTERVAL = 1.0 / TARGET_FPS  # ~37ms
    
    # Memory management
    MAX_FRAMES_BUFFER = 100            # Rolling buffer of recent frames
    MAX_SIGNIFICANT_FRAMES = 500       # Long-term significant frame storage
    HASH_HISTORY_SIZE = 1000           # How many hashes to remember for dedup
    
    # Change detection thresholds
    CHANGE_THRESHOLD = 0.05            # Below this = "same frame"
    SIGNIFICANT_CHANGE = 0.15          # Above this = "worth remembering"
    
    def __init__(self):
        self._init_tracer_worker()

        # Frame buffers
        self._recent_frames: Deque[VisualFrame] = deque(maxlen=self.MAX_FRAMES_BUFFER)
        self._significant_frames: Deque[VisualFrame] = deque(maxlen=self.MAX_SIGNIFICANT_FRAMES)

        # Dedup tracking
        self._seen_hashes: Deque[str] = deque(maxlen=self.HASH_HISTORY_SIZE)
        self._duplicate_count = 0
        self._unique_count = 0

        # Current perception state
        self.perception = VisualPerception()

        # Last frame for comparison
        self._last_frame: Optional[VisualFrame] = None
        self._last_frame_data: Optional[bytes] = None

        # Capture thread
        self._running = False
        self._capture_thread: Optional[threading.Thread] = None
        self._capture_lock = threading.Lock()

        # Stats
        self.total_frames_captured = 0
        self.frames_stored = 0
        self.frames_deduplicated = 0

        # Screen capture interface
        self._screen_capturer = None
        self._init_screen_capture()

        # GPU capture (dxcam - faster than mss)
        self._dxcam_camera = None
        self._use_gpu_capture = False
        self._continuous_gpu_mode = False
        self._init_gpu_capture()

        # Frame callbacks for VideoMemoryFairy integration
        self._frame_callbacks: List[callable] = []
        self._video_memory = None  # Lazy-loaded VideoMemoryFairy

        # Postal hub reference for frame emission
        self._postal_hub = None

        # LLM-based visual interpretation (human-like seeing)
        self._interpreter: Optional[VisualInterpreter] = None
        self._llm_interpretation_enabled = False
        self._known_scenes: Dict[str, str] = {}  # memory_key -> last_description
        self._last_scene_key: Optional[str] = None

        if HAS_VISUAL_PROMPTS:
            self._interpreter = get_visual_interpreter()
            print(f"[{self.ACTOR_NAME}] Visual interpreter loaded (human-like seeing)")

        # Capture method indicator
        capture_method = "dxcam (GPU)" if self._use_gpu_capture else (
            "mss" if self._screen_capturer_type == "mss" else "PIL"
        )
        print(f"[{self.ACTOR_NAME}] [EYE] Initialized - {self.TARGET_FPS} FPS target ({capture_method})")
    
    def _init_screen_capture(self):
        """Initialize screen capture capability."""
        # NOTE: We don't create the mss instance here because mss uses
        # thread-local Windows device contexts. The actual mss instance
        # must be created in the capture thread itself.
        self._screen_capturer_type = None

        try:
            import mss
            self._screen_capturer_type = "mss"
            print(f"[{self.ACTOR_NAME}] Screen capture ready (mss - deferred)")
        except ImportError:
            try:
                from PIL import ImageGrab
                self._screen_capturer_type = "pillow"
                print(f"[{self.ACTOR_NAME}] Screen capture ready (PIL)")
            except ImportError:
                print(f"[{self.ACTOR_NAME}] [WARN] No screen capture library available")
                self._screen_capturer_type = None

    def _init_gpu_capture(self):
        """
        Initialize dxcam for GPU-accelerated capture via DXGI Desktop Duplication.

        Benefits of GPU capture:
        - Much lower latency (~3ms vs ~30ms for GDI/mss)
        - Captures video frames properly (no tearing)
        - Lower CPU usage
        - Zero-copy from GPU framebuffer
        """
        if not HAS_DXCAM:
            return

        try:
            cam = dxcam.create(output_color="BGR")
            self._dxcam_camera = cam
            self._use_gpu_capture = True
            print(f"[{self.ACTOR_NAME}] [GPU] dxcam initialized (DXGI Desktop Duplication)")
        except Exception as e:
            # Suppress __del__ crash on half-constructed DXCamera objects
            import warnings
            warnings.filterwarnings("ignore", message=".*DXCamera.*is_capturing.*")
            self._dxcam_camera = None
            self._use_gpu_capture = False
            print(f"[{self.ACTOR_NAME}] [WARN] dxcam init failed, using mss fallback")

    def start_continuous_gpu(self, target_fps: int = 30):
        """
        Start continuous GPU capture mode for watching videos.

        In continuous mode, frames are captured at target_fps and
        get_latest_frame() returns the most recent one without blocking.
        """
        if not self._use_gpu_capture or not self._dxcam_camera:
            print(f"[{self.ACTOR_NAME}] [WARN] GPU capture not available")
            return False

        try:
            self._dxcam_camera.start(target_fps=target_fps, video_mode=True)
            self._continuous_gpu_mode = True
            print(f"[{self.ACTOR_NAME}] [GPU] Continuous capture started at {target_fps} FPS")
            return True
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [WARN] Continuous GPU start failed: {e}")
            return False

    def stop_continuous_gpu(self):
        """Stop continuous GPU capture mode."""
        if self._dxcam_camera and self._continuous_gpu_mode:
            try:
                self._dxcam_camera.stop()
                self._continuous_gpu_mode = False
                print(f"[{self.ACTOR_NAME}] [GPU] Continuous capture stopped")
            except Exception:
                pass
    
    # ═══════════════════════════════════════════════════════════════════════
    # FRAME CAPTURE - The act of seeing
    # ═══════════════════════════════════════════════════════════════════════
    
    def _capture_raw_frame(self, mss_instance=None) -> Optional[Tuple[bytes, Tuple[int, int]]]:
        """Capture raw screen data.

        Uses GPU capture (dxcam) when available, falls back to mss/PIL.

        Args:
            mss_instance: Pre-created mss instance (for thread-safe capture loops)
        """
        # TIMING INSTRUMENTATION (2026-03-14 Nous) — captures were taking 40s+,
        # need to isolate which stage is slow: grab, convert, resize, or compress.
        import time as _t
        _timings = {}
        try:
            # Try GPU capture first (dxcam via DXGI)
            if self._use_gpu_capture and self._dxcam_camera:
                return self._capture_gpu_frame()

            if self._screen_capturer_type is None:
                return None

            if self._screen_capturer_type == "pillow":
                _t0 = _t.time()
                from PIL import ImageGrab
                img = ImageGrab.grab()
                _timings["grab"] = (_t.time() - _t0) * 1000
                size = img.size
                # Compress to JPEG for memory efficiency
                _t0 = _t.time()
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=50)
                _timings["compress"] = (_t.time() - _t0) * 1000
                _total = sum(_timings.values())
                if _total > 2000:  # Only log if slow (>2s)
                    print(f"[{self.ACTOR_NAME}] SLOW capture (pillow): "
                          f"grab={_timings['grab']:.0f}ms compress={_timings['compress']:.0f}ms "
                          f"total={_total:.0f}ms size={size}")
                return (buffer.getvalue(), size)
            else:
                # mss - use provided instance or create new one
                _t0 = _t.time()
                import mss
                capturer = mss_instance if mss_instance else mss.mss()
                _timings["mss_init"] = (_t.time() - _t0) * 1000
                try:
                    _t0 = _t.time()
                    monitor = capturer.monitors[1]  # Primary monitor
                    sct_img = capturer.grab(monitor)
                    size = (sct_img.width, sct_img.height)
                    _timings["grab"] = (_t.time() - _t0) * 1000

                    # Convert to PIL and compress
                    _t0 = _t.time()
                    from PIL import Image
                    img = Image.frombytes('RGB', size, sct_img.bgra, 'raw', 'BGRX')
                    _timings["convert"] = (_t.time() - _t0) * 1000

                    # Downscale for memory efficiency (1/4 size)
                    _t0 = _t.time()
                    small_size = (size[0] // 4, size[1] // 4)
                    img = img.resize(small_size, Image.Resampling.LANCZOS)
                    _timings["resize"] = (_t.time() - _t0) * 1000

                    _t0 = _t.time()
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=50)
                    _timings["compress"] = (_t.time() - _t0) * 1000

                    _total = sum(_timings.values())
                    if _total > 2000:  # Only log if slow (>2s)
                        parts = " ".join(f"{k}={v:.0f}ms" for k, v in _timings.items())
                        print(f"[{self.ACTOR_NAME}] SLOW capture (mss): {parts} "
                              f"total={_total:.0f}ms raw_size={size}")
                    return (buffer.getvalue(), small_size)
                finally:
                    # Only close if we created it ourselves
                    if mss_instance is None:
                        capturer.close()

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Capture error: {e}")
            return None

    def _capture_gpu_frame(self) -> Optional[Tuple[bytes, Tuple[int, int]]]:
        """
        Capture frame using GPU (dxcam/DXGI Desktop Duplication).

        Much faster than GDI-based capture:
        - ~3ms vs ~30ms latency
        - Direct GPU framebuffer access
        - Zero-copy capture
        """
        try:
            from PIL import Image
            import numpy as np

            # Grab frame from GPU
            if self._continuous_gpu_mode:
                frame_array = self._dxcam_camera.get_latest_frame()
            else:
                frame_array = self._dxcam_camera.grab()

            if frame_array is None:
                return None

            # dxcam returns BGR numpy array - convert to RGB PIL
            rgb_array = frame_array[:, :, ::-1]
            img = Image.fromarray(rgb_array)
            size = img.size

            # Downscale for memory efficiency (1/4 size)
            small_size = (size[0] // 4, size[1] // 4)
            img = img.resize(small_size, Image.Resampling.LANCZOS)

            # Compress to JPEG
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=50)

            return (buffer.getvalue(), small_size)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [GPU] Capture error: {e}")
            # Fall back to mss/PIL
            self._use_gpu_capture = False
            return None
    
    def _compute_frame_hash(self, image_data: bytes) -> str:
        """Compute perceptual hash of frame for dedup."""
        # Simple hash for now - could use perceptual hashing (phash) for better results
        return hashlib.md5(image_data).hexdigest()[:16]
    
    def _compute_change_magnitude(self, current_data: bytes, previous_data: Optional[bytes]) -> float:
        """Compute how different this frame is from previous."""
        if previous_data is None:
            return 1.0  # First frame is completely "new"
        
        if current_data == previous_data:
            return 0.0
        
        # Simple byte-level comparison (could be smarter with image diff)
        # Compare sample of bytes for speed
        sample_size = min(1000, len(current_data), len(previous_data))
        step = max(1, len(current_data) // sample_size)
        
        differences = 0
        for i in range(0, len(current_data), step):
            if i < len(previous_data) and current_data[i] != previous_data[i]:
                differences += 1
        
        return min(1.0, differences / sample_size)
    
    def _analyze_frame(self, image_data: bytes, size: Tuple[int, int], 
                       change_mag: float) -> VisualFrame:
        """Analyze a captured frame and create VisualFrame object."""
        frame_hash = self._compute_frame_hash(image_data)
        
        # Estimate visual properties from image data
        # (These are approximations - real implementation would use image analysis)
        brightness = sum(image_data[::100]) / (len(image_data[::100]) * 255) if image_data else 0.5
        complexity = len(set(image_data[::50])) / 256  # Unique byte values as proxy
        
        frame = VisualFrame(
            timestamp=time.time(),
            frame_hash=frame_hash,
            size=size,
            change_magnitude=change_mag,
            regions_changed=[],  # Would need more analysis
            brightness=brightness,
            complexity=complexity,
            motion_detected=change_mag > 0.1,
            text_density=0.0,  # Would need OCR
        )
        
        # Only store image data for significant frames
        if frame.is_significant():
            frame.image_data = image_data
        
        return frame
    
    def capture_frame(self) -> Optional[VisualFrame]:
        """
        Capture and process a single frame.
        
        This is the core "seeing" action.
        """
        self.total_frames_captured += 1
        
        # Capture raw
        result = self._capture_raw_frame()
        if result is None:
            return None
        
        image_data, size = result
        
        # Check for duplicate
        frame_hash = self._compute_frame_hash(image_data)
        if frame_hash in self._seen_hashes:
            self.frames_deduplicated += 1
            self._duplicate_count += 1
            # Update perception but don't store
            self.perception.frames_since_change += 1
            return None
        
        # New frame
        self._seen_hashes.append(frame_hash)
        self._unique_count += 1
        
        # Compute change from last frame
        change_mag = self._compute_change_magnitude(image_data, self._last_frame_data)
        
        # Analyze
        frame = self._analyze_frame(image_data, size, change_mag)
        
        # Update perception state
        self._update_perception(frame)
        
        # Store
        with self._capture_lock:
            self._recent_frames.append(frame)
            self.frames_stored += 1

            if frame.is_significant():
                self._significant_frames.append(frame)
                self.perception.last_significant_change = time.time()
                self.perception.frames_since_change = 0
                # Emit to AssociationCortex for concept binding
                self._emit_to_association_cortex(frame)
            else:
                self.perception.frames_since_change += 1

        # Remember for next comparison
        self._last_frame = frame
        self._last_frame_data = image_data

        return frame

    def _update_perception(self, frame: VisualFrame):
        """Update felt perception state from frame."""
        # Update stability based on recent changes
        if frame.change_magnitude > self.SIGNIFICANT_CHANGE:
            self.perception.visual_stability = max(0.0, self.perception.visual_stability - 0.2)
        else:
            self.perception.visual_stability = min(1.0, self.perception.visual_stability + 0.05)
        
        # Update other perception qualities
        self.perception.peripheral_motion = frame.motion_detected
        self.perception.information_density = frame.complexity
    
    # ═══════════════════════════════════════════════════════════════════════
    # CONTINUOUS CAPTURE LOOP
    # ═══════════════════════════════════════════════════════════════════════
    
    def start_capture_loop(self):
        """Start the continuous capture loop at target FPS."""
        if self._running:
            return
        
        self._running = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            name="VisualCortex-Capture",
            daemon=True
        )
        self._capture_thread.start()
        print(f"[{self.ACTOR_NAME}]  Capture loop started at {self.TARGET_FPS} FPS")
    
    def stop_capture_loop(self):
        """Stop the capture loop."""
        self._running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=1.0)
        print(f"[{self.ACTOR_NAME}]  Capture loop stopped")
    
    def _capture_loop(self):
        """The main capture loop.
        
        Creates mss instance in THIS thread (required for Windows device context).
        Falls back to PIL if mss fails.
        """
        last_capture = 0
        
        # Create mss instance in this thread (thread-local requirement)
        mss_capturer = None
        use_pillow_fallback = False
        
        if self._screen_capturer_type == "mss":
            try:
                import mss
                mss_capturer = mss.mss()
                print(f"[{self.ACTOR_NAME}] [EYE] MSS capturer created in capture thread")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [WARN] MSS failed in thread ({e}), falling back to PIL")
                use_pillow_fallback = True
        
        try:
            while self._running:
                now = time.time()
                elapsed = now - last_capture
                
                # Maintain target FPS
                if elapsed < self.FRAME_INTERVAL:
                    time.sleep(self.FRAME_INTERVAL - elapsed)
                    continue
                
                last_capture = time.time()
                
                try:
                    if use_pillow_fallback:
                        self._capture_frame_pillow()
                    else:
                        self._capture_frame_internal(mss_capturer)
                except Exception as e:
                    # Only log occasionally to avoid spam
                    if self.total_frames_captured % 100 == 0:
                        print(f"[{self.ACTOR_NAME}] Capture error (frame {self.total_frames_captured}): {e}")
                    time.sleep(0.1)  # Back off on error
                
                # Log stats periodically
                if self.total_frames_captured % 1000 == 0 and self.total_frames_captured > 0:
                    dedup_rate = self.frames_deduplicated / max(1, self.total_frames_captured)
                    print(f"[{self.ACTOR_NAME}]  Frames: {self.total_frames_captured}, "
                          f"Stored: {self.frames_stored}, Dedup rate: {dedup_rate:.1%}")
        finally:
            # Clean up mss instance
            if mss_capturer:
                try:
                    mss_capturer.close()
                except:
                    pass
    
    def _capture_frame_pillow(self) -> Optional[VisualFrame]:
        """
        Capture using PIL (fallback for when mss fails in threads).
        """
        self.total_frames_captured += 1
        
        try:
            from PIL import ImageGrab, Image
            img = ImageGrab.grab()
            size = img.size
            
            # Downscale for memory efficiency (1/4 size)
            small_size = (size[0] // 4, size[1] // 4)
            img = img.resize(small_size, Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=50)
            image_data = buffer.getvalue()
            
        except Exception as e:
            if self.total_frames_captured % 100 == 0:
                print(f"[{self.ACTOR_NAME}] PIL capture error: {e}")
            return None
        
        # Check for duplicate
        frame_hash = self._compute_frame_hash(image_data)
        if frame_hash in self._seen_hashes:
            self.frames_deduplicated += 1
            self._duplicate_count += 1
            self.perception.frames_since_change += 1
            return None
        
        # New frame
        self._seen_hashes.append(frame_hash)
        self._unique_count += 1
        
        # Compute change from last frame
        change_mag = self._compute_change_magnitude(image_data, self._last_frame_data)
        
        # Analyze
        frame = self._analyze_frame(image_data, small_size, change_mag)
        
        # Update perception state
        self._update_perception(frame)
        
        # Store
        with self._capture_lock:
            self._recent_frames.append(frame)
            self.frames_stored += 1

            if frame.is_significant():
                self._significant_frames.append(frame)
                self.perception.last_significant_change = time.time()
                self.perception.frames_since_change = 0
                # Emit to AssociationCortex for concept binding
                self._emit_to_association_cortex(frame)
            else:
                self.perception.frames_since_change += 1

        # Remember for next comparison
        self._last_frame = frame
        self._last_frame_data = image_data

        # Emit to VideoMemoryFairy for H.265 encoding
        self._emit_frame_to_callbacks(image_data, small_size, frame.timestamp)

        return frame

    def _capture_frame_internal(self, mss_instance=None) -> Optional[VisualFrame]:
        """
        Internal capture using provided mss instance (for thread-safe loops).
        """
        self.total_frames_captured += 1
        
        # Capture raw using the provided mss instance
        result = self._capture_raw_frame(mss_instance)
        if result is None:
            return None
        
        image_data, size = result
        
        # Check for duplicate
        frame_hash = self._compute_frame_hash(image_data)
        if frame_hash in self._seen_hashes:
            self.frames_deduplicated += 1
            self._duplicate_count += 1
            self.perception.frames_since_change += 1
            return None
        
        # New frame
        self._seen_hashes.append(frame_hash)
        self._unique_count += 1
        
        # Compute change from last frame
        change_mag = self._compute_change_magnitude(image_data, self._last_frame_data)
        
        # Analyze
        frame = self._analyze_frame(image_data, size, change_mag)
        
        # Update perception state
        self._update_perception(frame)
        
        # Store
        with self._capture_lock:
            self._recent_frames.append(frame)
            self.frames_stored += 1

            if frame.is_significant():
                self._significant_frames.append(frame)
                self.perception.last_significant_change = time.time()
                self.perception.frames_since_change = 0
                # Emit to AssociationCortex for concept binding
                self._emit_to_association_cortex(frame)
            else:
                self.perception.frames_since_change += 1

        # Remember for next comparison
        self._last_frame = frame
        self._last_frame_data = image_data

        # Emit to VideoMemoryFairy for H.265 encoding
        self._emit_frame_to_callbacks(image_data, size, frame.timestamp)

        return frame
    
    # ═══════════════════════════════════════════════════════════════════════
    # TOOL INTERFACES - How ClaudeFairy accesses vision
    # ═══════════════════════════════════════════════════════════════════════
    
    def see(self) -> dict:
        """
        Quick look at the screen - returns current perception + latest frame.
        
        This is what see_screen tool calls.
        """
        frame = self.capture_frame()
        
        return {
            "ok": True,
            "perception": {
                "clarity": self.perception.clarity,
                "stability": self.perception.visual_stability,
                "active_window": self.perception.active_window,
                "information_density": self.perception.information_density,
                "description": self.perception.describe(),
            },
            "frame": {
                "timestamp": frame.timestamp if frame else None,
                "size": frame.size if frame else None,
                "change": frame.change_magnitude if frame else 0,
                "motion": frame.motion_detected if frame else False,
            } if frame else None,
            "stats": {
                "total_captured": self.total_frames_captured,
                "unique_stored": self.frames_stored,
                "dedup_rate": self.frames_deduplicated / max(1, self.total_frames_captured),
            }
        }
    
    def look_deeply(self, focus: Optional[str] = None) -> dict:
        """
        Conscious, focused looking - captures and analyzes in detail.
        
        This is what look_at_screen tool calls.
        """
        # Capture fresh frame
        result = self._capture_raw_frame()
        if result is None:
            return {"ok": False, "error": "Cannot capture screen"}
        
        image_data, size = result
        
        # For deep looking, we'd send to vision model for description
        # For now, return frame data for external processing
        import base64
        
        return {
            "ok": True,
            "focus": focus or "full screen",
            "perception": self.perception.describe(),
            "image": {
                "base64": base64.b64encode(image_data).decode('utf-8'),
                "size": size,
                "format": "jpeg",
            },
            "visual_state": {
                "brightness": self._last_frame.brightness if self._last_frame else 0.5,
                "complexity": self._last_frame.complexity if self._last_frame else 0.5,
            }
        }
    
    def get_visual_memory(self, n: int = 10, significant_only: bool = True) -> List[dict]:
        """
        Get recent visual memories.
        
        Returns descriptions of recent frames, not the actual image data.
        """
        with self._capture_lock:
            source = self._significant_frames if significant_only else self._recent_frames
            frames = list(source)[-n:]
        
        return [
            {
                "timestamp": f.timestamp,
                "time_ago": time.time() - f.timestamp,
                "change_magnitude": f.change_magnitude,
                "motion": f.motion_detected,
                "description": f.description or "No description",
            }
            for f in frames
        ]

    # ═══════════════════════════════════════════════════════════════════════
    # LLM-BASED VISUAL INTERPRETATION (Human-like seeing)
    # ═══════════════════════════════════════════════════════════════════════

    def enable_llm_interpretation(self, enable: bool = True) -> dict:
        """
        Enable/disable LLM-based visual interpretation.

        When enabled, the visual cortex will:
        - Build visual memory of familiar scenes
        - Only deeply process NEW or CHANGED content
        - Provide felt descriptions of what is seen

        This mimics human visual processing.
        """
        if not HAS_VISUAL_PROMPTS:
            return {"ok": False, "error": "Visual prompts not available"}

        self._llm_interpretation_enabled = enable

        if enable and not self._interpreter:
            self._interpreter = get_visual_interpreter()

        return {
            "ok": True,
            "llm_interpretation": enable,
            "known_scenes": list(self._known_scenes.keys())
        }

    def see_like_human(self) -> dict:
        """
        Human-like seeing: see from memory, only process changes.

        This is how humans actually see:
        - Familiar scenes are recognized instantly from memory
        - Only novel or changed content gets full processing
        - Most of "seeing" is actually remembering

        Returns:
            {
                "matched_memory": scene_key or None,
                "changed": bool,
                "perception": description,
                "felt_sense": emotional feel of the view
            }
        """
        # Capture frame first
        result = self._capture_raw_frame()
        if result is None:
            return {"ok": False, "error": "Cannot capture screen"}

        image_data, size = result

        # Compute change magnitude
        change_mag = self._compute_change_magnitude(image_data, self._last_frame_data)

        # Estimate visual properties
        brightness = sum(image_data[::100]) / (len(image_data[::100]) * 255) if image_data else 0.5
        complexity = len(set(image_data[::50])) / 256

        # Update last frame
        self._last_frame_data = image_data

        # Low change = see from memory
        if change_mag < self.CHANGE_THRESHOLD and self._last_scene_key:
            return {
                "ok": True,
                "matched_memory": self._last_scene_key,
                "changed": False,
                "perception": f"Same as before: {self._known_scenes.get(self._last_scene_key, 'familiar scene')}",
                "felt_sense": "Visual field stable - no change needing attention",
                "metrics": {
                    "change": change_mag,
                    "brightness": brightness,
                    "complexity": complexity
                }
            }

        # Significant change - use LLM interpretation if available
        if self._llm_interpretation_enabled and self._interpreter:
            image_b64 = base64.b64encode(image_data).decode('utf-8')

            # Get scene recognition
            scene_result = self._interpreter.interpret_scene(image_b64)

            if scene_result and "memory_key" in scene_result:
                self._last_scene_key = scene_result["memory_key"]
                self._known_scenes[scene_result["memory_key"]] = scene_result.get("signature", "")

            # Get felt vision
            felt_sense = self._interpreter.get_felt_vision(image_b64)

            return {
                "ok": True,
                "matched_memory": None,
                "changed": True,
                "perception": scene_result.get("signature", "Unknown scene") if scene_result else "Processing...",
                "scene_type": scene_result.get("scene_type", "unknown") if scene_result else "unknown",
                "felt_sense": felt_sense or "Neutral visual experience",
                "metrics": {
                    "change": change_mag,
                    "brightness": brightness,
                    "complexity": complexity
                }
            }

        # Fallback: simple perception without LLM
        return {
            "ok": True,
            "matched_memory": None,
            "changed": change_mag > self.CHANGE_THRESHOLD,
            "perception": self.perception.describe(),
            "felt_sense": "Visual processing without LLM interpretation",
            "metrics": {
                "change": change_mag,
                "brightness": brightness,
                "complexity": complexity
            }
        }

    def get_capture_screenshot(self, as_base64: bool = True) -> dict:
        """
        Direct screen capture for MCP tool integration.

        Returns the current screen as base64 JPEG.

        Args:
            as_base64: If True, return base64 encoded image

        Returns:
            {
                "ok": True,
                "image": base64_string or bytes,
                "size": (width, height),
                "capture_method": "gpu" or "mss" or "pil"
            }
        """
        result = self._capture_raw_frame()
        if result is None:
            return {"ok": False, "error": "Cannot capture screen"}

        image_data, size = result

        capture_method = "gpu" if self._use_gpu_capture else (
            "mss" if self._screen_capturer_type == "mss" else "pil"
        )

        if as_base64:
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            return {
                "ok": True,
                "image": image_b64,
                "size": size,
                "format": "jpeg",
                "capture_method": capture_method
            }
        else:
            return {
                "ok": True,
                "image": image_data,
                "size": size,
                "format": "jpeg",
                "capture_method": capture_method
            }

    def get_known_scenes(self) -> list:
        """Get list of known visual memory scene keys."""
        return list(self._known_scenes.keys())

    # ═══════════════════════════════════════════════════════════════════════
    # POSTAL INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def wire_to_postal(self):
        """Connect to postal system."""
        # Guard against double wiring
        if getattr(self, '_wired_to_postal', False):
            print(f"[{self.ACTOR_NAME}] Already wired to postal - skipping")
            return True

        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            postal = get_fairy_postal(self)  # Use FairyPostal for sender tracking

            # Store postal reference for frame emission to AssociationCortex
            self._postal_hub = postal
            
            # Subscribe to visual requests - ZERO-WORK HANDLER (Whisper pattern)
            # Heavy work happens in thread, handler returns FAST
            def _on_visual_request(packet):
                import threading
                request_type = packet.get("type", "see")
                source = packet.get("source", "unknown")
                request_id = packet.get("request_id")

                # IMMEDIATE ACK - don't block postal worker
                print(f"[{self.ACTOR_NAME}] Visual request: {request_type} (from {source})")

                def _do_capture():
                    """Heavy work in thread - not blocking postal."""
                    import time as _time
                    _start = _time.time()
                    try:
                        if request_type == "see":
                            result = self.see()
                        elif request_type == "look_deeply":
                            result = self.look_deeply(packet.get("focus"))
                        elif request_type == "quick_ack":
                            result = {"ok": True, "quick": True}
                        else:
                            result = {"error": f"Unknown visual request: {request_type}"}

                        _elapsed = (_time.time() - _start) * 1000
                        print(f"[{self.ACTOR_NAME}] Capture took {_elapsed:.0f}ms")

                        # Send response
                        postal.route("visual.response", {
                            "request_id": request_id,
                            "result": result,
                            "source": self.ACTOR_NAME,
                        })
                        print(f"[{self.ACTOR_NAME}] Visual response sent")
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] Capture FAILED: {e}")
                        import traceback
                        traceback.print_exc()
                        postal.route("visual.response", {
                            "request_id": request_id,
                            "result": {"error": str(e)},
                            "source": self.ACTOR_NAME,
                        })

                # Fire and forget - don't block
                t = threading.Thread(target=_do_capture, daemon=True,
                                     name="visual-capture")
                t.start()

            postal.subscribe("visual.request", _on_visual_request)

            self._wired_to_postal = True
            print(f"[{self.ACTOR_NAME}] [PLUG] Wired to postal")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to postal: {e}")
            return False
    
    def wire_to_autonomy(self):
        """Connect to autonomy system for drive satisfaction."""
        try:
            from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
            autonomy = get_autonomy_fairy()
            
            # Visual stimulation satisfies curiosity
            def _on_significant_frame(frame: VisualFrame):
                if frame.is_significant():
                    autonomy.satisfy("curiosity", 0.1)
                    autonomy.emit_novel_experience("visual_change")
            
            # Wire to frame processing
            self._on_significant_frame_callback = _on_significant_frame
            
            print(f"[{self.ACTOR_NAME}] [BRAIN] Wired to AutonomyFairy")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to autonomy: {e}")
            return False
    
    def wire_to_video_memory(self):
        """
        Connect to VideoMemoryFairy for H.265 temporal compression.
        
        This enables long-term visual memory storage with efficient
        inter-frame compression instead of per-frame JPEG dedup.
        """
        try:
            from fairies.P40_Sensory.cortex.video_memory_fairy import get_video_memory
            self._video_memory = get_video_memory()
            
            # Add callback to emit frames to video memory
            def _emit_to_video_memory(image_data: bytes, size: tuple, timestamp: float):
                if self._video_memory:
                    self._video_memory.ingest_frame(image_data, size, timestamp)
            
            self._frame_callbacks.append(_emit_to_video_memory)
            
            print(f"[{self.ACTOR_NAME}]  Wired to VideoMemoryFairy (H.265)")
            return True
            
        except ImportError:
            print(f"[{self.ACTOR_NAME}] VideoMemoryFairy not available (optional)")
            return False
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to video memory: {e}")
            return False
    
    def _emit_frame_to_callbacks(self, image_data: bytes, size: tuple, timestamp: float):
        """Emit captured frame to all registered callbacks (including VideoMemory)."""
        for callback in self._frame_callbacks:
            try:
                callback(image_data, size, timestamp)
            except Exception:
                pass  # Don't let callback errors break capture loop

    def _emit_to_association_cortex(self, frame: 'VisualFrame'):
        """
        Emit visual frame to AssociationCortex via postal system.

        AssociationCortex subscribes to 'sensory.visual.frame' and expects:
        - scene_type: classification of what's being viewed
        - dominant_color: primary color in the frame
        - objects: list of detected elements
        - ts: timestamp

        This bridges VisualCortex -> AssociationCortex for concept binding.
        """
        if not self._postal_hub:
            return

        try:
            # Transform VisualFrame into AssociationCortex-expected format
            payload = {
                "ts": frame.timestamp,
                "scene_type": frame.description if frame.description else "screen",
                "objects": frame.detected_elements[:10] if frame.detected_elements else [],
                # Derive dominant "brightness zone" from brightness
                "dominant_color": (
                    "bright" if frame.brightness > 0.7 else
                    "dark" if frame.brightness < 0.3 else
                    "neutral"
                ),
                # Include raw visual metrics for richer binding
                "brightness": frame.brightness,
                "complexity": frame.complexity,
                "motion": frame.motion_detected,
                "change_magnitude": frame.change_magnitude,
                "text_density": frame.text_density,
                "source": self.ACTOR_NAME,
            }

            self._postal_hub.route("sensory.visual.frame", payload)

            # Also emit to legacy topic for backward compatibility
            self._postal_hub.route("visual.significant_change", {
                "timestamp": frame.timestamp,
                "change": frame.change_magnitude,
                "motion": frame.motion_detected,
                "source": self.ACTOR_NAME,
            })

        except Exception as e:
            # Don't break capture loop on postal errors
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # MEDIA MEMORY REFLECTION - Review stored images, tag to Sourpatches
    # ═══════════════════════════════════════════════════════════════════════

    def _init_media_reflection(self):
        """Initialize media memory reflection state."""
        self._media_reflection_cursor = 0
        self._media_reflection_tick = 0
        self._media_processed_ids = set()
        self._media_reflection_interval = 30  # Every 30th heartbeat (~30-40 seconds)

    def reflect_on_media_memory(self):
        """Review stored images in media memory and tag to association cortex.

        Most stored images are of Sourpatches in different personas.
        Extract traits (colors, tags, descriptions) and publish to the
        association cortex as visual experiences for Sourpatches.

        This builds her visual identity — she learns what she looks like
        across different personas, moods, and settings.
        """
        try:
            # Import MediaIndex for reading stored media
            from fairies.P10_Memory.media.media_memory_fairy import MediaIndex
            index = MediaIndex()

            # Get all records we haven't processed yet
            all_records = list(index.records.values())
            unprocessed = [r for r in all_records if r.media_id not in self._media_processed_ids]

            if not unprocessed:
                return  # All caught up

            # Process 1-3 images per cycle (don't flood)
            batch = unprocessed[:3]

            for record in batch:
                self._media_processed_ids.add(record.media_id)

                # Extract visual experience from record
                tags = list(record.tags) if record.tags else []
                description = record.description or ""
                colors = record.dominant_colors or []
                media_type = record.media_type or "image"

                # Detect if this is a Sourpatches image
                sour_tags = {"sourpatches", "sour", "sourpatch", "sp", "avatar"}
                is_sourpatches = bool(sour_tags.intersection(set(t.lower() for t in tags)))

                # Build association cortex payload
                experience = {
                    "ts": record.ingested_at or 0,
                    "source": self.ACTOR_NAME,
                    "type": "media_memory_reflection",
                    "media_id": record.media_id,
                    "media_type": media_type,
                    "tags": tags,
                    "description": description[:200],
                    "dominant_colors": colors[:5],
                    "is_sourpatches": is_sourpatches,
                }

                if is_sourpatches:
                    # Tag specifically for Sourpatches' association cortex
                    experience["target"] = "SourpatchesFairy"
                    experience["experience_type"] = "visual_identity"
                    experience["persona_tags"] = [t for t in tags if t.lower() not in sour_tags]

                    # Emit to association cortex with Sourpatches routing
                    if self._postal_hub:
                        self._postal_hub.route("cortex.association.visual_experience", experience)
                        # Also emit concepts for binding
                        concepts = tags + [f"color:{c}" for c in colors[:3]]
                        if concepts:
                            self._postal_hub.route("cortex.association.bind_concepts", {
                                "concepts": concepts,
                                "context": f"Sourpatches visual identity: {description[:100]}",
                                "source": self.ACTOR_NAME,
                                "target": "SourpatchesFairy",
                            })
                else:
                    # Non-Sourpatches images still go to association cortex
                    if self._postal_hub:
                        self._postal_hub.route("cortex.association.visual_experience", experience)

            if batch:
                print(f"[{self.ACTOR_NAME}] Reflected on {len(batch)} media memories "
                      f"({len(self._media_processed_ids)}/{len(all_records)} total)")

        except ImportError:
            # MediaIndex not available yet
            pass
        except Exception as e:
            if not hasattr(self, '_media_reflect_err_logged'):
                self._media_reflect_err_logged = True
                print(f"[{self.ACTOR_NAME}] Media memory reflection error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # HEARTBEAT-DRIVEN CAPTURE - Periodic vision without mouse flicker
    # ═══════════════════════════════════════════════════════════════════════

    def _on_heartbeat_pulse(self, event: dict):
        """
        Heartbeat-triggered capture for passive visual awareness.

        Instead of continuous 27 FPS capture (which causes mouse flicker),
        we capture once per N heartbeats. This gives Sourpatches periodic
        visual awareness without overwhelming the system.

        Timing:
        - Heartbeat: ~1.0-1.3 seconds
        - Capture every 4th beat: ~4-5 seconds between captures
        - Still enough for experiential memory without flicker
        """
        try:
            payload = event.get("payload", event)
            beat_count = payload.get("beat_count", 0)

            # Media memory reflection: every Nth heartbeat, review stored images
            # This builds Sourpatches' visual identity from stored media
            if hasattr(self, '_media_reflection_tick'):
                self._media_reflection_tick += 1
                if self._media_reflection_tick % self._media_reflection_interval == 0:
                    import threading
                    threading.Thread(
                        target=self.reflect_on_media_memory,
                        daemon=True,
                        name=f"{self.ACTOR_NAME}_media_reflect"
                    ).start()

            # Capture every 4th heartbeat (roughly every 4-5 seconds)
            # This is slow enough to avoid flicker but frequent enough for awareness
            if beat_count % 4 == 0:
                # Use see() for quick capture - this is the human-like seeing
                result = self.see()

                # If we got a meaningful result, it's already published to postal
                if result.get("ok"):
                    # Track that we did a heartbeat-driven capture
                    self.total_frames_captured += 1

        except Exception as e:
            # Never crash on heartbeat - just skip this beat
            pass

    def on_boot(self):
        """Boot the visual cortex.

        NOTE: Capture is HEARTBEAT-DRIVEN for passive awareness.
        - see() captures single frame when Claude looks
        - look_deeply() captures for detailed analysis
        - Heartbeat pulse triggers periodic capture every ~4-5 seconds

        This prevents mouse flicker while still building visual memory.

        FUTURE: Use DXGI Desktop Duplication API for event-driven capture.
        """
        # Guard against double boot
        if getattr(self, '_booted', False):
            print(f"[{self.ACTOR_NAME}] Already booted - skipping")
            return
        self._booted = True

        # ── SELF-PULSE DAEMON (FIX 5b 2026-04-30 Nous + Ace) ──
        # VisualCortexEngine is the inner engine class; its dashboard
        # entry shows "no heartbeat" because it doesn't inherit from
        # the organ template's _handle_heartbeat path that updates
        # _last_tick. _on_heartbeat_pulse only triggers see(), doesn't
        # mark liveness. Self-pulse daemon updates _last_tick directly
        # so the watchdog stops calling this engine dead. Same shape as
        # Fix 5 for VisualCortexFairy (wrapper) + Cochlea + PerceptualGate.
        import threading as _threading_sp
        import time as _time_sp
        def _self_pulse_engine():
            while True:
                try:
                    _time_sp.sleep(2.0)
                    if getattr(self, '_shutting_down', False):
                        return
                    self._tick_count = getattr(self, '_tick_count', 0) + 1
                    self._last_tick = _time_sp.time()
                except Exception:
                    pass
        _threading_sp.Thread(
            target=_self_pulse_engine,
            daemon=True,
            name=f"selfpulse-{self.ACTOR_NAME}",
        ).start()

        # Wire to postal for visual frame emission
        self.wire_to_postal()
        self.wire_to_autonomy()
        self.wire_to_video_memory()  # H.265 temporal compression

        # === HEARTBEAT WIRING - Periodic visual awareness ===
        # This gives Sourpatches passive vision without continuous polling
        if hasattr(self, 'post') and self.post:
            try:
                self.post.subscribe("heartbeat.pulse", self._on_heartbeat_pulse)
                print(f"[{self.ACTOR_NAME}] Wired to heartbeat for periodic capture")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [WARN] Heartbeat wiring failed: {e}")
        elif self._postal_hub:
            try:
                self._postal_hub.subscribe("heartbeat.pulse", self._on_heartbeat_pulse)
                print(f"[{self.ACTOR_NAME}] Wired to heartbeat via postal_hub")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [WARN] Heartbeat wiring failed: {e}")

        # Initialize media memory reflection (reviews stored images)
        self._init_media_reflection()

        # NO continuous capture loop - heartbeat-driven only
        # self.start_capture_loop()  # DISABLED - causes mouse flicker
        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (heartbeat-driven mode, media reflection enabled)")
    
    def get_status(self) -> dict:
        """Get current status."""
        return {
            "actor": self.ACTOR_NAME,
            "running": self._running,
            "target_fps": self.TARGET_FPS,
            "total_captured": self.total_frames_captured,
            "unique_stored": self.frames_stored,
            "deduplicated": self.frames_deduplicated,
            "dedup_rate": self.frames_deduplicated / max(1, self.total_frames_captured),
            "buffer_size": len(self._recent_frames),
            "significant_frames": len(self._significant_frames),
            "perception": self.perception.describe(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ══════════════════════════════════════════════════════════════════════════════

_VISUAL_CORTEX_INSTANCE: Optional[VisualCortexFairy] = None
_VISUAL_CORTEX_LOCK = threading.Lock()


def get_visual_cortex() -> VisualCortexFairy:
    """Get or create the VisualCortexFairy singleton."""
    global _VISUAL_CORTEX_INSTANCE
    if _VISUAL_CORTEX_INSTANCE is None:
        with _VISUAL_CORTEX_LOCK:
            if _VISUAL_CORTEX_INSTANCE is None:
                _VISUAL_CORTEX_INSTANCE = VisualCortexEngine()
    return _VISUAL_CORTEX_INSTANCE


def boot_visual_cortex() -> VisualCortexFairy:
    """Boot the visual cortex."""
    cortex = get_visual_cortex()
    cortex.on_boot()
    return cortex


# ══════════════════════════════════════════════════════════════════════════════
# MAIN - Test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== VisualCortexFairy Test ===\n")
    
    cortex = VisualCortexFairy()
    
    # Test single capture
    print("[Test] Single capture...")
    result = cortex.see()
    print(f"  Result: {result}")
    
    # Test capture loop for a few seconds
    print("\n[Test] Starting capture loop for 5 seconds...")
    cortex.start_capture_loop()
    time.sleep(5)
    cortex.stop_capture_loop()
    
    print(f"\n[Test] Status: {cortex.get_status()}")
    print("\n=== Test Complete ===")
