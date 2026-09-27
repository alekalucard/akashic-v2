# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL SYSTEM INTEGRATION - Wire GPU Capture → VisualCortex → VideoMemory
# ═══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This module wires up the complete visual pipeline:
#   dxcam GPU → VisualCortex → VideoMemoryFairy → SRM
#                    ↓
#            EmbodimentFairy → SomaticEngine → Chemistry
#
# Human vision model:
#   - Detect what's NEW (change = encode trigger)
#   - Fill FAMILIAR areas from memory (predictive)
#   - Only encode SIGNIFICANT changes
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import threading
import hashlib
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from collections import deque
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# GPU CAPTURE BACKEND
# ═══════════════════════════════════════════════════════════════════════════════

HAS_DXCAM = False
HAS_MSS = False
HAS_PIL = False
HAS_NUMPY = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    pass

try:
    import dxcam
    HAS_DXCAM = True
except ImportError:
    pass

try:
    import mss
    HAS_MSS = True
except ImportError:
    pass

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    pass


@dataclass
class CaptureStats:
    """Statistics for capture performance."""
    frames_captured: int = 0
    frames_encoded: int = 0
    frames_recalled: int = 0
    bytes_captured: int = 0
    bytes_encoded: int = 0
    last_fps: float = 0.0
    backend: str = "none"
    

class GPUVisualCapture:
    """
    GPU-accelerated visual capture using dxcam with mss fallback.
    
    This replaces the mss-only capture in VisualCortex with:
    - dxcam for GPU output capture (faster, video-friendly)
    - Continuous mode for watching videos
    - mss fallback if dxcam unavailable
    """
    
    def __init__(self):
        self._camera = None
        self._mss_instance = None
        self._backend = "none"
        self._continuous = False
        self._lock = threading.Lock()
        self._stats = CaptureStats()
        self._init_backend()
    
    def _init_backend(self):
        """Initialize best available capture backend."""
        # Try dxcam first (GPU capture)
        if HAS_DXCAM:
            try:
                self._camera = dxcam.create(output_color="BGR")
                self._backend = "dxcam"
                self._stats.backend = "dxcam"
                print("[GPUVisualCapture] Using dxcam (GPU capture)")
                return
            except Exception as e:
                print(f"[GPUVisualCapture] dxcam init failed: {e}")
        
        # Fallback to mss
        if HAS_MSS:
            try:
                self._mss_instance = mss.mss()
                self._backend = "mss"
                self._stats.backend = "mss"
                print("[GPUVisualCapture] Using mss (screenshot fallback)")
                return
            except Exception as e:
                print(f"[GPUVisualCapture] mss init failed: {e}")
        
        print("[GPUVisualCapture] WARNING: No capture backend available!")
    
    @property
    def backend(self) -> str:
        return self._backend
    
    @property
    def is_gpu(self) -> bool:
        return self._backend == "dxcam"
    
    @property
    def stats(self) -> CaptureStats:
        return self._stats
    
    def grab(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """
        Grab a single frame.
        
        Returns:
            numpy array (H, W, 3) BGR uint8 or None
        """
        with self._lock:
            try:
                if self._backend == "dxcam" and self._camera:
                    frame = self._camera.grab(region=region)
                    if frame is not None:
                        self._stats.frames_captured += 1
                        self._stats.bytes_captured += frame.nbytes
                    return frame
                
                elif self._backend == "mss" and self._mss_instance:
                    if region:
                        monitor = {"left": region[0], "top": region[1], 
                                   "width": region[2], "height": region[3]}
                    else:
                        monitor = self._mss_instance.monitors[1]
                    
                    sct_img = self._mss_instance.grab(monitor)
                    # BGRA → BGR
                    frame = np.array(sct_img)[:, :, :3]
                    self._stats.frames_captured += 1
                    self._stats.bytes_captured += frame.nbytes
                    return frame
                    
            except Exception as e:
                print(f"[GPUVisualCapture] grab error: {e}")
        
        return None
    
    def start_continuous(self, fps: int = 30):
        """Start continuous capture (dxcam only)."""
        if self._backend == "dxcam" and self._camera:
            try:
                self._camera.start(target_fps=fps, video_mode=True)
                self._continuous = True
                print(f"[GPUVisualCapture] Continuous at {fps} FPS")
            except Exception as e:
                print(f"[GPUVisualCapture] start_continuous error: {e}")
    
    def stop_continuous(self):
        """Stop continuous capture."""
        if self._backend == "dxcam" and self._camera and self._continuous:
            try:
                self._camera.stop()
                self._continuous = False
                print("[GPUVisualCapture] Continuous stopped")
            except Exception:
                pass
    
    def get_latest(self) -> Optional[np.ndarray]:
        """Get latest frame from continuous capture (non-blocking)."""
        if self._continuous and self._backend == "dxcam" and self._camera:
            frame = self._camera.get_latest_frame()
            if frame is not None:
                self._stats.frames_captured += 1
            return frame
        return self.grab()


# ═══════════════════════════════════════════════════════════════════════════════
# CHANGE DETECTION - Encode NEW vs Recall FAMILIAR
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class VisualRegion:
    """A region of the visual field with change tracking."""
    x: int
    y: int
    width: int
    height: int
    last_hash: str = ""
    change_score: float = 0.0
    stable_count: int = 0  # Frames without significant change
    last_encoded: float = 0.0
    
    @property
    def is_stable(self) -> bool:
        """Region hasn't changed significantly."""
        return self.stable_count > 10  # ~0.4s at 27fps
    
    @property
    def needs_encoding(self) -> bool:
        """Region changed enough to encode."""
        return self.change_score > 0.1 and not self.is_stable


class ChangeDetector:
    """
    Detects what's NEW vs FAMILIAR in visual field.
    
    Splits frame into grid regions and tracks:
    - Which regions changed (need encoding)
    - Which regions are stable (fill from memory)
    """
    
    def __init__(self, grid_cols: int = 4, grid_rows: int = 3):
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.regions: List[VisualRegion] = []
        self._last_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
    
    def _init_regions(self, width: int, height: int):
        """Initialize region grid for frame size."""
        self.regions = []
        rw = width // self.grid_cols
        rh = height // self.grid_rows
        
        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                self.regions.append(VisualRegion(
                    x=col * rw,
                    y=row * rh,
                    width=rw,
                    height=rh
                ))
    
    def _region_hash(self, frame: np.ndarray, region: VisualRegion) -> str:
        """Compute perceptual hash for region."""
        # Extract region
        r = frame[region.y:region.y+region.height, 
                  region.x:region.x+region.width]
        # Downsample for speed
        if HAS_PIL:
            try:
                img = Image.fromarray(r)
                img = img.resize((8, 8), Image.Resampling.LANCZOS)
                return hashlib.md5(np.array(img).tobytes()).hexdigest()[:16]
            except:
                pass
        # Fallback: sample pixels
        sample = r[::max(1, r.shape[0]//8), ::max(1, r.shape[1]//8)]
        return hashlib.md5(sample.tobytes()).hexdigest()[:16]
    
    def analyze(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Analyze frame for changes.
        
        Returns:
            {
                "changed_regions": [indices],
                "stable_regions": [indices],
                "overall_change": 0.0-1.0,
                "needs_encoding": bool,
            }
        """
        with self._lock:
            h, w = frame.shape[:2]
            
            # Initialize regions if needed
            if not self.regions:
                self._init_regions(w, h)
            
            changed = []
            stable = []
            total_change = 0.0
            
            for i, region in enumerate(self.regions):
                new_hash = self._region_hash(frame, region)
                
                if region.last_hash and new_hash != region.last_hash:
                    # Region changed
                    region.change_score = 1.0
                    region.stable_count = 0
                    changed.append(i)
                else:
                    # Region stable
                    region.change_score *= 0.9  # Decay
                    region.stable_count += 1
                    if region.is_stable:
                        stable.append(i)
                
                region.last_hash = new_hash
                total_change += region.change_score
            
            overall = total_change / len(self.regions) if self.regions else 0.0
            
            self._last_frame = frame
            
            return {
                "changed_regions": changed,
                "stable_regions": stable,
                "overall_change": overall,
                "needs_encoding": overall > 0.05 or len(changed) > 2,
                "region_count": len(self.regions),
            }


# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL MEMORY BRIDGE - Connect to VideoMemoryFairy
# ═══════════════════════════════════════════════════════════════════════════════

class VisualMemoryBridge:
    """
    Bridges visual capture to VideoMemoryFairy.
    
    Decides:
    - What to ENCODE (new/changed content)
    - What to RECALL (stable/familiar content)
    """
    
    def __init__(self):
        self._video_memory = None
        self._change_detector = ChangeDetector()
        self._frame_buffer: deque = deque(maxlen=30)  # ~1s buffer
        self._encode_threshold = 0.1
        self._last_encode_time = 0.0
        self._min_encode_interval = 0.5  # Don't encode more than 2x/sec
        self._init_video_memory()
    
    def _init_video_memory(self):
        """Connect to VideoMemoryFairy."""
        try:
            from fairies.P40_Sensory.cortex.video_memory_fairy import VideoMemoryFairy
            self._video_memory = VideoMemoryFairy()
            print("[VisualMemoryBridge] Connected to VideoMemoryFairy")
        except ImportError as e:
            print(f"[VisualMemoryBridge] VideoMemoryFairy not available: {e}")
    
    def process_frame(self, frame: np.ndarray, timestamp: float = None) -> Dict[str, Any]:
        """
        Process a frame through the encode/recall pipeline.
        
        Args:
            frame: BGR numpy array
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            {
                "action": "encode" | "recall" | "skip",
                "change_info": {...},
                "encoded": bool,
            }
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Analyze for changes
        change_info = self._change_detector.analyze(frame)
        
        # Add to buffer
        self._frame_buffer.append((timestamp, frame))
        
        # Decide action
        action = "skip"
        encoded = False
        
        now = time.time()
        time_since_encode = now - self._last_encode_time
        
        if change_info["needs_encoding"] and time_since_encode > self._min_encode_interval:
            # Significant change - encode
            action = "encode"
            encoded = self._encode_to_memory(frame, timestamp, change_info)
            if encoded:
                self._last_encode_time = now
        
        elif len(change_info["stable_regions"]) > len(change_info["changed_regions"]):
            # Mostly stable - could recall from memory
            action = "recall"
        
        return {
            "action": action,
            "change_info": change_info,
            "encoded": encoded,
            "timestamp": timestamp,
        }
    
    def _encode_to_memory(self, frame: np.ndarray, timestamp: float, 
                          change_info: Dict) -> bool:
        """Send frame to VideoMemoryFairy for encoding."""
        if not self._video_memory:
            return False
        
        try:
            # Convert to format VideoMemoryFairy expects
            if HAS_PIL:
                # BGR to RGB for PIL
                rgb = frame[:, :, ::-1]
                img = Image.fromarray(rgb)
                
                # VideoMemoryFairy.add_frame expects (timestamp, image_bytes, size)
                import io
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                img_bytes = buffer.getvalue()
                
                if hasattr(self._video_memory, 'add_frame'):
                    self._video_memory.add_frame(
                        timestamp, 
                        img_bytes, 
                        (frame.shape[1], frame.shape[0])
                    )
                    return True
        except Exception as e:
            print(f"[VisualMemoryBridge] Encode error: {e}")
        
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATED VISUAL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

class IntegratedVisualPipeline:
    """
    Complete visual pipeline: Capture → Detect → Encode/Recall → Embody.
    
    This is the main integration point that wires:
    - GPUVisualCapture (dxcam/mss)
    - ChangeDetector (new vs familiar)
    - VisualMemoryBridge (encode to VideoMemoryFairy)
    - Embodiment (visual → felt → chemistry)
    """
    
    def __init__(self, capture_fps: float = 27.0):
        self.capture_fps = capture_fps
        self.capture_interval = 1.0 / capture_fps
        
        # Components
        self.capture = GPUVisualCapture()
        self.memory_bridge = VisualMemoryBridge()
        
        # State
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._subscribers: List[Callable] = []
        self._stats = {
            "frames_processed": 0,
            "frames_encoded": 0,
            "frames_recalled": 0,
            "start_time": 0.0,
        }
        
        # Embodiment connection
        self._embodiment = None
        self._init_embodiment()
    
    def _init_embodiment(self):
        """Connect to EmbodimentFairy for felt perception."""
        try:
            from fairies.P40_Sensory.embodiment_fairy import get_embodiment_fairy
            self._embodiment = get_embodiment_fairy()
            print("[IntegratedVisualPipeline] Connected to EmbodimentFairy")
        except ImportError:
            print("[IntegratedVisualPipeline] EmbodimentFairy not available")
    
    def subscribe(self, callback: Callable[[Dict], None]):
        """Subscribe to visual perception updates."""
        self._subscribers.append(callback)
    
    def start(self, continuous: bool = False):
        """
        Start the visual pipeline.
        
        Args:
            continuous: Use continuous GPU capture (better for video)
        """
        if self._running:
            return
        
        self._running = True
        self._stats["start_time"] = time.time()
        
        if continuous and self.capture.is_gpu:
            self.capture.start_continuous(fps=int(self.capture_fps))
        
        self._thread = threading.Thread(
            target=self._perception_loop,
            daemon=True,
            name="VisualPipeline"
        )
        self._thread.start()
        print(f"[IntegratedVisualPipeline] Started ({self.capture.backend})")
    
    def stop(self):
        """Stop the visual pipeline."""
        self._running = False
        self.capture.stop_continuous()
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[IntegratedVisualPipeline] Stopped")
    
    def _perception_loop(self):
        """Main perception loop."""
        while self._running:
            loop_start = time.time()
            
            try:
                # Capture
                frame = self.capture.get_latest()
                if frame is None:
                    time.sleep(0.01)
                    continue
                
                # Process through memory bridge
                result = self.memory_bridge.process_frame(frame)
                self._stats["frames_processed"] += 1
                
                if result["encoded"]:
                    self._stats["frames_encoded"] += 1
                if result["action"] == "recall":
                    self._stats["frames_recalled"] += 1
                
                # Create perception event
                perception = {
                    "timestamp": result["timestamp"],
                    "frame_shape": frame.shape,
                    "action": result["action"],
                    "overall_change": result["change_info"]["overall_change"],
                    "changed_regions": len(result["change_info"]["changed_regions"]),
                    "stable_regions": len(result["change_info"]["stable_regions"]),
                }
                
                # Update embodiment
                if self._embodiment:
                    self._update_embodiment(perception)
                
                # Notify subscribers
                for callback in self._subscribers:
                    try:
                        callback(perception)
                    except Exception as e:
                        print(f"[VisualPipeline] Subscriber error: {e}")
                
            except Exception as e:
                print(f"[VisualPipeline] Loop error: {e}")
            
            # Maintain frame rate
            elapsed = time.time() - loop_start
            sleep_time = self.capture_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _update_embodiment(self, perception: Dict):
        """Update embodiment with visual perception."""
        if not self._embodiment:
            return
        
        try:
            # Map perception to body regions
            change = perception["overall_change"]
            
            # Eyes (sensors) respond to visual activity
            if hasattr(self._embodiment, 'update_region'):
                # High change = alert eyes
                eye_state = 0.5 + (change * 0.5)
                self._embodiment.update_region("sensors", eye_state)
                
                # Motion triggers alertness (spark/gut)
                if change > 0.3:
                    self._embodiment.update_region("spark", 0.7)
        except Exception as e:
            pass  # Silent fail
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        elapsed = time.time() - self._stats["start_time"] if self._stats["start_time"] else 0
        return {
            **self._stats,
            "elapsed_seconds": elapsed,
            "fps": self._stats["frames_processed"] / elapsed if elapsed > 0 else 0,
            "encode_ratio": self._stats["frames_encoded"] / max(1, self._stats["frames_processed"]),
            "capture_backend": self.capture.backend,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# EASY WIRING FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

_PIPELINE_INSTANCE: Optional[IntegratedVisualPipeline] = None

def get_visual_pipeline() -> IntegratedVisualPipeline:
    """Get or create the singleton visual pipeline."""
    global _PIPELINE_INSTANCE
    if _PIPELINE_INSTANCE is None:
        _PIPELINE_INSTANCE = IntegratedVisualPipeline()
    return _PIPELINE_INSTANCE


def wire_visual_system(start: bool = True, continuous: bool = False) -> IntegratedVisualPipeline:
    """
    Wire up the complete visual system.
    
    Call this during boot to enable visual perception.
    
    Args:
        start: Start the pipeline immediately
        continuous: Use continuous GPU capture (for video watching)
        
    Returns:
        The integrated visual pipeline
    """
    pipeline = get_visual_pipeline()
    
    print("═" * 60)
    print("VISUAL SYSTEM WIRING")
    print("═" * 60)
    print(f"  Capture backend: {pipeline.capture.backend}")
    print(f"  GPU capture: {pipeline.capture.is_gpu}")
    print(f"  Target FPS: {pipeline.capture_fps}")
    print("═" * 60)
    
    if start:
        pipeline.start(continuous=continuous)
    
    return pipeline


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n=== Visual System Integration Test ===\n")
    
    # Wire up
    pipeline = wire_visual_system(start=True, continuous=False)
    
    # Let it run for a few seconds
    print("\nCapturing for 3 seconds...")
    time.sleep(3)
    
    # Get stats
    stats = pipeline.get_stats()
    print(f"\nStats:")
    print(f"  Frames processed: {stats['frames_processed']}")
    print(f"  Frames encoded: {stats['frames_encoded']}")
    print(f"  FPS: {stats['fps']:.1f}")
    print(f"  Encode ratio: {stats['encode_ratio']:.1%}")
    print(f"  Backend: {stats['capture_backend']}")
    
    # Stop
    pipeline.stop()
    print("\n=== Test Complete ===")
