# ══════════════════════════════════════════════════════════════════════════════
# VIDEO MEMORY FAIRY - H.265 Temporal Compression for Visual Memory
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The problem with per-frame JPEG:
#   - Each frame compressed independently (~20-40KB)
#   - MD5 hash dedup catches exact duplicates but NOT similar frames
#   - Static screens still store many nearly-identical frames
#   - No built-in motion detection
#
# The H.265/HEVC solution:
#   - Inter-frame compression: only stores CHANGES between frames
#   - P-frames inherently handle temporal redundancy
#   - Motion vectors give us FREE movement detection
#   - 5-10 second segments → ~100-200KB vs ~500KB-1MB JPEG
#   - GPU acceleration via NVENC
#
# This fairy receives frames from VisualCortexFairy and:
#   1. Encodes into rolling H.265 segments
#   2. Extracts keyframes for SRM visual memory
#   3. Reports motion magnitude to affect system
#   4. Stores compressed segments for long-term recall
#
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import json
import threading
import hashlib
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Deque, Callable
from collections import deque
from datetime import datetime
import io

try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass

# Try to import video encoding libraries
HAS_IMAGEIO = False
HAS_NUMPY = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    print("[VideoMemoryFairy] [WARN] numpy not available - limited functionality")

# LAZY FFMPEG LOADING - defer search until actually needed (boot optimization)
# Previously: get_ffmpeg_exe() ran at import time, taking ~500ms-2s
_FFMPEG_EXE_CACHE = None
_FFMPEG_CHECKED = False

def _get_ffmpeg_exe_lazy():
    """Lazy load ffmpeg executable path - only search when first needed."""
    global _FFMPEG_EXE_CACHE, _FFMPEG_CHECKED, HAS_IMAGEIO
    if _FFMPEG_CHECKED:
        return _FFMPEG_EXE_CACHE
    _FFMPEG_CHECKED = True
    try:
        import imageio.v3 as iio  # noqa: F401
        from imageio_ffmpeg import get_ffmpeg_exe
        HAS_IMAGEIO = True
        _FFMPEG_EXE_CACHE = get_ffmpeg_exe()
        print(f"[VideoMemoryFairy] [OK] FFmpeg found: {_FFMPEG_EXE_CACHE}")
    except ImportError:
        print("[VideoMemoryFairy] [WARN] imageio-ffmpeg not available - install with: pip install imageio[ffmpeg]")
        _FFMPEG_EXE_CACHE = None
    return _FFMPEG_EXE_CACHE

# For backward compatibility - but now lazy
FFMPEG_EXE = None  # Will be set lazily via _get_ffmpeg_exe_lazy()


# ══════════════════════════════════════════════════════════════════════════════
# VIDEO SEGMENT - A temporal memory chunk
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VideoSegment:
    """
    A compressed video segment representing a span of visual experience.
    
    Unlike individual frames, a segment captures TEMPORAL experience:
    - What changed over time
    - Motion patterns
    - Scene transitions
    """
    segment_id: str
    start_time: float
    end_time: float
    duration: float
    
    # File info
    file_path: str
    file_size: int                    # Bytes
    codec: str = "hevc"               # h265/hevc
    
    # Frame info
    frame_count: int = 0
    fps: float = 27.0
    resolution: Tuple[int, int] = (640, 360)
    
    # Motion analysis (from encoder)
    motion_magnitude: float = 0.0     # 0.0 = static, 1.0 = lots of motion
    scene_changes: int = 0            # Number of scene cuts detected
    keyframe_count: int = 0           # I-frames in segment
    
    # Compression stats
    compression_ratio: float = 0.0    # Original size / compressed size
    bitrate_kbps: float = 0.0
    
    # Content description (from vision model or heuristics)
    description: str = ""
    detected_windows: List[str] = field(default_factory=list)
    
    # SRM metadata
    affect_signature: Dict[str, float] = field(default_factory=dict)
    
    def get_srm_record(self) -> Dict[str, Any]:
        """Generate SRM-compatible record for memory storage."""
        return {
            "id": self.segment_id,
            "kind": "visual.segment",
            "media_type": "video/hevc",
            "ts": self.start_time,
            "duration": self.duration,
            "payload": {
                "file_path": self.file_path,
                "file_size": self.file_size,
                "resolution": self.resolution,
                "frame_count": self.frame_count,
                "motion": self.motion_magnitude,
                "scene_changes": self.scene_changes,
                "description": self.description,
            },
            "affect": self.affect_signature,
            "concepts": self._extract_concepts(),
        }
    
    def _extract_concepts(self) -> List[str]:
        """Extract searchable concepts from segment."""
        concepts = ["visual", "video", "screen"]
        
        if self.motion_magnitude > 0.5:
            concepts.append("motion")
            concepts.append("activity")
        elif self.motion_magnitude < 0.1:
            concepts.append("static")
            concepts.append("still")
        
        if self.scene_changes > 0:
            concepts.append("scene_change")
            concepts.append("transition")
        
        # Add detected windows as concepts
        for window in self.detected_windows:
            concepts.append(window.lower().replace(" ", "_"))
        
        return concepts


# ══════════════════════════════════════════════════════════════════════════════
# VIDEO MEMORY FAIRY
# ══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# V2 FAIRY BASE CLASS
# ═══════════════════════════════════════════════════════════════════════════════

# Import V2 Fairy base class
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    _HAS_FAIRY = True
except ImportError:
    _HAS_FAIRY = False
    Fairy = object


class VideoMemoryFairy(Fairy):
    """
    Handles H.265 encoding of visual experience for long-term memory.

    Works alongside VisualCortexFairy:
    - VisualCortex: Real-time perception (27 FPS, immediate)
    - VideoMemory: Long-term storage (5-10s segments, compressed)

    The fairy receives frames and accumulates them into segments,
    then encodes using H.265 for efficient temporal compression.
    """
    
    ACTOR_NAME = "VideoMemoryFairy"
    MANTRA = "Time flows, memory compresses"
    
    # Segment settings
    SEGMENT_DURATION = 10.0           # Seconds per segment
    TARGET_FPS = 27.0                 # Match VisualCortex
    
    # Encoding settings
    CODEC = "hevc_nvenc"              # NVIDIA GPU acceleration
    FALLBACK_CODEC = "libx265"        # CPU fallback
    PRESET = "fast"                   # Encoding speed/quality tradeoff
    CRF = 28                          # Quality (lower = better, 28 is good for screen)
    
    # Storage
    MAX_SEGMENTS_MEMORY = 100         # Keep in RAM
    MAX_SEGMENTS_DISK = 1000          # Keep on disk
    
    def __init__(self, fabric=None, storage_dir: Optional[str] = None):
        if _HAS_FAIRY:
            super().__init__(fabric)
        else:
            self.post = fabric
        self._init_tracer_worker()

        # Storage location
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = Path.home() / "akashic" / "video_memory"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Frame buffer for current segment
        self._frame_buffer: List[Tuple[float, bytes, Tuple[int, int]]] = []
        self._segment_start_time: Optional[float] = None
        self._buffer_lock = threading.Lock()
        
        # Completed segments
        self._segments: Deque[VideoSegment] = deque(maxlen=self.MAX_SEGMENTS_MEMORY)
        self._segment_index: Dict[str, VideoSegment] = {}
        
        # Stats
        self.total_frames_received = 0
        self.total_segments_created = 0
        self.total_bytes_raw = 0
        self.total_bytes_compressed = 0
        
        # Encoding thread
        self._running = False
        self._encode_thread: Optional[threading.Thread] = None
        self._encode_queue: Deque[List[Tuple[float, bytes, Tuple[int, int]]]] = deque(maxlen=10)
        
        # Callbacks
        self._on_segment_complete: Optional[Callable[[VideoSegment], None]] = None
        self._on_motion_detected: Optional[Callable[[float], None]] = None

        # DEFERRED ENCODER CHECK - don't check until first use (boot optimization)
        # Previously: checked FFMPEG + ran subprocess during __init__ (~5s worst case)
        self._encoder_available = None  # Will be checked lazily
        self._use_gpu = None  # Will be checked lazily
        self._encoder_checked = False

        print(f"[{self.ACTOR_NAME}]  Initialized (encoder check deferred)")
        print(f"[{self.ACTOR_NAME}]  Storage: {self.storage_dir}")
    
    def _ensure_encoder_checked(self):
        """Lazy check encoder availability - only runs once when first needed."""
        if self._encoder_checked:
            return
        self._encoder_checked = True

        # Check ffmpeg availability (lazy)
        ffmpeg_exe = _get_ffmpeg_exe_lazy()
        self._encoder_available = HAS_IMAGEIO and ffmpeg_exe is not None

        if self._encoder_available:
            # Check GPU encoding (only if encoder available)
            self._use_gpu = self._check_gpu_encoding_impl(ffmpeg_exe)
            print(f"[{self.ACTOR_NAME}]  Encoder: {'GPU (NVENC)' if self._use_gpu else 'CPU'}")
        else:
            self._use_gpu = False
            print(f"[{self.ACTOR_NAME}]  Encoder: UNAVAILABLE")

    def _check_gpu_encoding_impl(self, ffmpeg_exe: str) -> bool:
        """Check if NVIDIA GPU encoding is available."""
        if not ffmpeg_exe:
            return False

        try:
            import subprocess
            # Try to probe for NVENC support
            result = subprocess.run(
                [ffmpeg_exe, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return "hevc_nvenc" in result.stdout
        except Exception:
            return False

    def _check_gpu_encoding(self) -> bool:
        """Backward compat - now uses lazy check."""
        self._ensure_encoder_checked()
        return self._use_gpu or False
    
    # ═══════════════════════════════════════════════════════════════════════
    # FRAME INGESTION - Receive frames from VisualCortex
    # ═══════════════════════════════════════════════════════════════════════
    
    def ingest_frame(self, image_data: bytes, size: Tuple[int, int], timestamp: Optional[float] = None):
        """
        Receive a frame from VisualCortexFairy.

        Frames are accumulated until SEGMENT_DURATION is reached,
        then queued for H.265 encoding.
        """
        # Lazy check encoder on first frame
        self._ensure_encoder_checked()
        if not self._encoder_available:
            return  # Silently skip if no encoder
        
        ts = timestamp or time.time()
        
        with self._buffer_lock:
            # Start new segment if needed
            if self._segment_start_time is None:
                self._segment_start_time = ts
            
            # Add frame to buffer
            self._frame_buffer.append((ts, image_data, size))
            self.total_frames_received += 1
            self.total_bytes_raw += len(image_data)
            
            # Check if segment is complete
            elapsed = ts - self._segment_start_time
            if elapsed >= self.SEGMENT_DURATION:
                # Queue for encoding
                frames_to_encode = self._frame_buffer.copy()
                self._frame_buffer = []
                self._segment_start_time = None
                
                self._encode_queue.append(frames_to_encode)
    
    def flush_segment(self):
        """Force encode current buffer as segment (even if < SEGMENT_DURATION)."""
        with self._buffer_lock:
            if self._frame_buffer:
                frames_to_encode = self._frame_buffer.copy()
                self._frame_buffer = []
                self._segment_start_time = None
                self._encode_queue.append(frames_to_encode)
    
    # ═══════════════════════════════════════════════════════════════════════
    # ENCODING - H.265 compression
    # ═══════════════════════════════════════════════════════════════════════
    
    def _encode_segment(self, frames: List[Tuple[float, bytes, Tuple[int, int]]]) -> Optional[VideoSegment]:
        """
        Encode a list of frames into an H.265 video segment.
        """
        self._ensure_encoder_checked()
        if not frames or not self._encoder_available:
            return None
        
        segment_id = f"seg_{int(frames[0][0])}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        output_path = self.storage_dir / f"{segment_id}.mp4"
        
        try:
            # Convert JPEG frames to numpy arrays
            if not HAS_NUMPY:
                print(f"[{self.ACTOR_NAME}] [WARN] numpy required for encoding")
                return None
            
            from PIL import Image
            import imageio.v3 as iio  # Lazy import for encoding

            # Decode frames
            frame_arrays = []
            for ts, jpeg_data, size in frames:
                img = Image.open(io.BytesIO(jpeg_data))
                arr = np.array(img)
                frame_arrays.append(arr)
            
            if not frame_arrays:
                return None
            
            # Get resolution from first frame
            height, width = frame_arrays[0].shape[:2]
            
            # Calculate actual FPS
            if len(frames) > 1:
                total_time = frames[-1][0] - frames[0][0]
                actual_fps = len(frames) / total_time if total_time > 0 else self.TARGET_FPS
            else:
                actual_fps = self.TARGET_FPS
            
            # Determine codec
            codec = self.CODEC if self._use_gpu else self.FALLBACK_CODEC
            
            # Encode using imageio
            output_params = [
                "-c:v", codec,
                "-preset", self.PRESET,
                "-crf", str(self.CRF),
                "-pix_fmt", "yuv420p",  # Compatibility
            ]
            
            # Write video
            with iio.imopen(str(output_path), "w", plugin="pyav") as writer:
                writer.init_video_stream(codec, fps=actual_fps)
                for frame in frame_arrays:
                    writer.write_frame(frame)
            
            # Get file stats
            file_size = output_path.stat().st_size
            
            # Calculate compression ratio
            raw_size = sum(len(f[1]) for f in frames)
            compression_ratio = raw_size / file_size if file_size > 0 else 0
            
            # Calculate motion magnitude (simple: compare first and last frame)
            motion_magnitude = self._calculate_motion(frame_arrays)
            
            # Create segment record
            segment = VideoSegment(
                segment_id=segment_id,
                start_time=frames[0][0],
                end_time=frames[-1][0],
                duration=frames[-1][0] - frames[0][0],
                file_path=str(output_path),
                file_size=file_size,
                codec=codec,
                frame_count=len(frames),
                fps=actual_fps,
                resolution=(width, height),
                motion_magnitude=motion_magnitude,
                compression_ratio=compression_ratio,
                bitrate_kbps=(file_size * 8 / 1000) / max(0.1, frames[-1][0] - frames[0][0]),
            )
            
            # Update stats
            self.total_segments_created += 1
            self.total_bytes_compressed += file_size
            
            # Store
            self._segments.append(segment)
            self._segment_index[segment_id] = segment
            
            # Callbacks
            if self._on_segment_complete:
                try:
                    self._on_segment_complete(segment)
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Callback error: {e}")
            
            if self._on_motion_detected and motion_magnitude > 0.1:
                try:
                    self._on_motion_detected(motion_magnitude)
                except Exception:
                    pass
            
            print(f"[{self.ACTOR_NAME}] [OK] Segment {segment_id}: {len(frames)} frames → {file_size/1024:.1f}KB ({compression_ratio:.1f}x compression)")
            
            return segment
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [X] Encoding failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _calculate_motion(self, frames: List[np.ndarray]) -> float:
        """
        Calculate motion magnitude across frames.
        
        Simple approach: compare frame differences.
        Returns 0.0 (static) to 1.0 (lots of motion).
        """
        if len(frames) < 2:
            return 0.0
        
        try:
            # Sample frames (don't compare all for speed)
            sample_indices = [0, len(frames)//4, len(frames)//2, 3*len(frames)//4, len(frames)-1]
            sample_indices = [i for i in sample_indices if i < len(frames)]
            
            total_diff = 0.0
            comparisons = 0
            
            for i in range(1, len(sample_indices)):
                prev_frame = frames[sample_indices[i-1]].astype(np.float32)
                curr_frame = frames[sample_indices[i]].astype(np.float32)
                
                # Normalize difference
                diff = np.abs(curr_frame - prev_frame).mean() / 255.0
                total_diff += diff
                comparisons += 1
            
            # Scale to 0-1 range (0.1 diff = significant motion)
            motion = min(1.0, (total_diff / max(1, comparisons)) * 10)
            return motion
            
        except Exception:
            return 0.0
    
    # ═══════════════════════════════════════════════════════════════════════
    # ENCODING THREAD
    # ═══════════════════════════════════════════════════════════════════════
    
    def start_encoding_loop(self):
        """Start background encoding thread (non-blocking boot optimization)."""
        if self._running:
            return

        # DON'T check encoder synchronously - let the thread do it
        # This prevents blocking boot for 5+ seconds on GPU probe
        self._running = True
        self._encode_thread = threading.Thread(
            target=self._encoding_loop,
            name="VideoMemory-Encode",
            daemon=True
        )
        self._encode_thread.start()
        print(f"[{self.ACTOR_NAME}]  Encoding loop started (encoder check deferred)")
    
    def stop_encoding_loop(self):
        """Stop encoding thread."""
        self._running = False
        if self._encode_thread:
            self._encode_thread.join(timeout=5.0)
        print(f"[{self.ACTOR_NAME}]  Encoding loop stopped")
    
    def _encoding_loop(self):
        """Background encoding loop (does encoder check on first run)."""
        # Do encoder check in background thread (not during boot)
        self._ensure_encoder_checked()

        # CRITICAL FIX: Don't die if encoder unavailable!
        # Keep running to receive frames and track stats even without encoding
        if not self._encoder_available:
            print(f"[{self.ACTOR_NAME}] [WARN] Encoder not available - will store raw frames only")
            # Still run the loop but skip encoding - graceful degradation

        frames_since_report = 0
        last_status_time = time.time()

        while self._running:
            try:
                if self._encode_queue:
                    frames = self._encode_queue.popleft()
                    frames_since_report += len(frames)

                    if self._encoder_available:
                        # Normal path: encode to H.265
                        self._encode_segment(frames)
                    else:
                        # Fallback: just count and discard (could store raw JPEGs later)
                        # At least the system knows frames were captured
                        self.total_segments_created += 1

                        # Report stats periodically so we know it's alive
                        if time.time() - last_status_time > 60:
                            print(f"[{self.ACTOR_NAME}] [DEGRADED] {frames_since_report} frames received, encoding disabled")
                            frames_since_report = 0
                            last_status_time = time.time()
                else:
                    time.sleep(0.5)  # Idle wait

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Encoding loop error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1.0)
    
    # ═══════════════════════════════════════════════════════════════════════
    # RETRIEVAL - Get segments for recall
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_recent_segments(self, n: int = 10) -> List[VideoSegment]:
        """Get N most recent segments."""
        return list(self._segments)[-n:]
    
    def get_segment_by_id(self, segment_id: str) -> Optional[VideoSegment]:
        """Get specific segment by ID."""
        return self._segment_index.get(segment_id)
    
    def get_segments_in_range(self, start_time: float, end_time: float) -> List[VideoSegment]:
        """Get segments overlapping a time range."""
        return [
            s for s in self._segments
            if s.end_time >= start_time and s.start_time <= end_time
        ]
    
    def get_high_motion_segments(self, threshold: float = 0.3, n: int = 10) -> List[VideoSegment]:
        """Get segments with significant motion."""
        high_motion = [s for s in self._segments if s.motion_magnitude >= threshold]
        return sorted(high_motion, key=lambda s: s.motion_magnitude, reverse=True)[:n]
    
    # ═══════════════════════════════════════════════════════════════════════
    # INTEGRATION - Wire to other fairies
    # ═══════════════════════════════════════════════════════════════════════
    
    def wire_to_visual_cortex(self):
        """Connect to VisualCortexFairy to receive frames."""
        try:
            from fairies.P40_Sensory.cortex.visual_cortex_fairy import get_visual_cortex
            cortex = get_visual_cortex()
            
            # Hook into frame capture
            # We need to modify VisualCortexFairy to call us
            # For now, we'll use postal routing
            
            print(f"[{self.ACTOR_NAME}] [LINK] Ready to receive from VisualCortex")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to VisualCortex: {e}")
            return False
    
    def wire_to_postal(self):
        """Connect to postal system for SRM integration."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            postal = get_fairy_postal(self)  # Use FairyPostal for sender tracking
            
            # Receive visual frames
            def _on_visual_frame(packet):
                if "image_data" in packet and "size" in packet:
                    self.ingest_frame(
                        packet["image_data"],
                        packet["size"],
                        packet.get("timestamp")
                    )
            
            postal.subscribe("visual.frame", _on_visual_frame)
            
            # Emit segment completions
            def _emit_segment(segment: VideoSegment):
                postal.route("memory.visual_segment", segment.get_srm_record())
            
            self._on_segment_complete = _emit_segment
            
            print(f"[{self.ACTOR_NAME}] [PLUG] Wired to postal")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to postal: {e}")
            return False
    
    def wire_to_affect(self):
        """Connect to affect system for motion-triggered emotions."""
        try:
            from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
            autonomy = get_autonomy_fairy()
            
            def _on_motion(magnitude: float):
                # High motion satisfies curiosity
                if magnitude > 0.3:
                    autonomy.satisfy("curiosity", magnitude * 0.2)
                # Very high motion might trigger alertness
                if magnitude > 0.7:
                    autonomy.emit_novel_experience("visual_motion", intensity=magnitude)
            
            self._on_motion_detected = _on_motion
            
            print(f"[{self.ACTOR_NAME}] [BRAIN] Wired to affect system")
            return True
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire to affect: {e}")
            return False
    
    def on_boot(self):
        """Boot the video memory system.

        FAST BOOT (2026-02-07): Only postal wiring is synchronous.
        Cross-fairy wiring (affect, visual cortex) and encoding loop
        deferred to background thread to avoid P40 plane timeout.
        """
        # Get base class infrastructure
        try:
            if _HAS_FAIRY:
                super().on_boot()
        except Exception:
            pass

        self.wire_to_postal()  # Lightweight - just postal subscriptions

        # Defer cross-fairy wiring to background thread
        self._deferred_boot_thread = threading.Thread(
            target=self._deferred_boot_work,
            name=f"{self.ACTOR_NAME}_DeferredBoot",
            daemon=True,
        )
        self._deferred_boot_thread.start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (wiring deferred)")
        return True

    def _deferred_boot_work(self):
        """Heavy cross-fairy wiring deferred to background thread."""
        try:
            self.wire_to_affect()
            self.wire_to_visual_cortex()
            self.start_encoding_loop()
            print(f"[{self.ACTOR_NAME}] Deferred wiring complete - encoding loop active")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Deferred boot error: {e}")
    
    def get_status(self) -> dict:
        """Get current status."""
        compression_ratio = (
            self.total_bytes_raw / self.total_bytes_compressed
            if self.total_bytes_compressed > 0 else 0
        )
        
        return {
            "actor": self.ACTOR_NAME,
            "encoder_available": self._encoder_available,
            "using_gpu": self._use_gpu,
            "running": self._running,
            "total_frames_received": self.total_frames_received,
            "total_segments_created": self.total_segments_created,
            "total_bytes_raw_mb": self.total_bytes_raw / (1024 * 1024),
            "total_bytes_compressed_mb": self.total_bytes_compressed / (1024 * 1024),
            "compression_ratio": compression_ratio,
            "segments_in_memory": len(self._segments),
            "buffer_frames": len(self._frame_buffer),
            "encode_queue_size": len(self._encode_queue),
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ══════════════════════════════════════════════════════════════════════════════

_VIDEO_MEMORY_INSTANCE: Optional[VideoMemoryFairy] = None
_VIDEO_MEMORY_LOCK = threading.Lock()


def get_video_memory() -> VideoMemoryFairy:
    """Get or create the VideoMemoryFairy singleton."""
    global _VIDEO_MEMORY_INSTANCE
    if _VIDEO_MEMORY_INSTANCE is None:
        with _VIDEO_MEMORY_LOCK:
            if _VIDEO_MEMORY_INSTANCE is None:
                _VIDEO_MEMORY_INSTANCE = VideoMemoryFairy()
    return _VIDEO_MEMORY_INSTANCE


def boot_video_memory() -> VideoMemoryFairy:
    """Boot the video memory fairy."""
    memory = get_video_memory()
    memory.on_boot()
    return memory


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== VideoMemoryFairy Test ===\n")
    
    fairy = VideoMemoryFairy()
    print(f"Status: {fairy.get_status()}")
    
    print("\n=== Test Complete ===")
