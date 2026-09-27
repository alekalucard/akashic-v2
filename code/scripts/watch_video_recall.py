#!/usr/bin/env python3
"""
WATCH VIDEO THROUGH RECALL - The trick!

Instead of building a separate video processing pipeline, we RUN the video
through the SRMRecallFairy. Each frame becomes a recall query:

1. Frame extracted -> "What does this remind me of?"
2. SRMRecall searches helix for visual matches
3. Match found -> Association strengthened
4. No match -> Gets ingested as new memory
5. Audio segment -> Same process for audio cortex

The ACT OF WATCHING is the learning.

This is exactly how human visual cortex works - we don't "store" frames,
we recognize patterns and strengthen associations through exposure.

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

import sys
import time
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

# Check dependencies
try:
    import cv2
    import numpy as np
    from PIL import Image
    HAS_VISION = True
except ImportError:
    HAS_VISION = False
    print("[WARN] Vision dependencies not available")

try:
    import librosa
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False
    print("[WARN] Audio dependencies not available")


# ==============================================================================
# VISUAL FEATURE EXTRACTION (for recall queries)
# ==============================================================================

def compute_phash(frame: np.ndarray, hash_size: int = 8) -> str:
    """Compute perceptual hash of a frame - this becomes the recall query."""
    # Resize to hash_size * 4 for DCT
    img = cv2.resize(frame, (hash_size * 4, hash_size * 4))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)

    # DCT
    dct = cv2.dct(img)
    dct_low = dct[:hash_size, :hash_size]

    # Median threshold
    median = np.median(dct_low)
    bits = (dct_low > median).flatten()

    # Convert to hex
    hash_int = sum(1 << i for i, b in enumerate(bits) if b)
    return f"{hash_int:016x}"


def extract_visual_features(frame: np.ndarray) -> Dict[str, Any]:
    """Extract visual features that become the recall query."""
    height, width = frame.shape[:2]

    # Perceptual hash - the primary recall key
    phash = compute_phash(frame)

    # Brightness (AFFECT dimension)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray) / 255.0)

    # Complexity (SEMANTIC dimension)
    edges = cv2.Canny(gray, 50, 150)
    complexity = float(np.mean(edges > 0))

    # Dominant color (AFFECT - emotional coloring)
    pixels = frame.reshape(-1, 3)
    dominant = pixels.mean(axis=0).astype(int).tolist()  # BGR

    # Color histogram (SEMANTIC fingerprint)
    hist_b = cv2.calcHist([frame], [0], None, [8], [0, 256]).flatten()
    hist_g = cv2.calcHist([frame], [1], None, [8], [0, 256]).flatten()
    hist_r = cv2.calcHist([frame], [2], None, [8], [0, 256]).flatten()
    color_signature = (hist_b + hist_g + hist_r).tolist()

    return {
        "phash": phash,
        "brightness": brightness,
        "complexity": complexity,
        "dominant_color": dominant,
        "color_signature": color_signature,
        "width": width,
        "height": height,
    }


def extract_audio_features(audio_path: Path, sr: int = 22050) -> Dict[str, Any]:
    """Extract audio features that become recall queries."""
    if not HAS_AUDIO:
        return {}

    y, sr = librosa.load(str(audio_path), sr=sr)

    # Tempo and beats (TEMPORAL dimension)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)

    # Spectral features (SEMANTIC dimension)
    spectral_centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    spectral_bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))

    # Energy (AFFECT dimension)
    rms = float(np.mean(librosa.feature.rms(y=y)))

    # MFCCs (voice/sound fingerprint for recall)
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_signature = np.mean(mfccs, axis=1).tolist()

    # Chroma (musical content)
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    chroma_signature = np.mean(chroma, axis=1).tolist()

    return {
        "tempo": float(tempo) if hasattr(tempo, '__float__') else float(tempo[0]) if len(tempo) > 0 else 0.0,
        "n_beats": len(beats),
        "spectral_centroid": spectral_centroid,
        "spectral_bandwidth": spectral_bandwidth,
        "rms_energy": rms,
        "mfcc_signature": mfcc_signature,
        "chroma_signature": chroma_signature,
        "duration": len(y) / sr,
    }


# ==============================================================================
# VIDEO WATCHER - Runs video through recall
# ==============================================================================

@dataclass
class WatchResult:
    """Result of watching a video through recall."""
    video_path: str
    frames_watched: int = 0
    frames_recalled: int = 0  # Found matches
    frames_new: int = 0       # No match - new memories
    audio_segments: int = 0
    audio_recalled: int = 0
    audio_new: int = 0
    associations_strengthened: int = 0
    new_memories_created: int = 0
    watch_duration: float = 0.0
    errors: List[str] = field(default_factory=list)


class VideoWatcher:
    """
    Watches video through the SRMRecallFairy.

    Each frame becomes a recall query. The act of trying to recall
    is how the system learns.
    """

    def __init__(self, recall_fairy=None, visual_cortex=None, audio_cortex=None):
        self.recall_fairy = recall_fairy
        self.visual_cortex = visual_cortex
        self.audio_cortex = audio_cortex

        # Stats
        self.total_watches = 0
        self.total_frames = 0
        self.total_recalls = 0
        self.total_new = 0

    def watch(
        self,
        video_path: str,
        frame_interval: float = 1.0,  # Seconds between frames
        audio_segment_length: float = 10.0,  # Seconds per audio segment
        max_frames: int = None,
        verbose: bool = True,
    ) -> WatchResult:
        """
        Watch a video through the recall system.

        Each frame is extracted and queried against memory:
        - If recalled: Association is strengthened
        - If new: Memory is created

        This IS the learning process.
        """
        result = WatchResult(video_path=video_path)
        start_time = time.time()

        video_path = Path(video_path)
        if not video_path.exists():
            result.errors.append(f"Video not found: {video_path}")
            return result

        if not HAS_VISION:
            result.errors.append("OpenCV not available")
            return result

        if verbose:
            print(f"\n{'='*60}")
            print(f"WATCHING VIDEO THROUGH RECALL")
            print(f"{'='*60}")
            print(f"Video: {video_path.name}")
            print(f"Frame interval: {frame_interval}s")
            print()

        # Open video
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        if verbose:
            print(f"Video info: {fps:.1f} FPS, {total_frames} frames, {duration:.1f}s")

        # Calculate frame indices to extract
        frame_skip = int(fps * frame_interval)
        frame_indices = list(range(0, total_frames, frame_skip))
        if max_frames:
            frame_indices = frame_indices[:max_frames]

        if verbose:
            print(f"Will watch {len(frame_indices)} frames (1 every {frame_interval}s)")
            print()

        # Watch each frame through recall
        for i, frame_idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if not ret:
                continue

            timestamp = frame_idx / fps
            result.frames_watched += 1

            # Extract visual features (the recall query)
            features = extract_visual_features(frame)
            features["timestamp"] = timestamp
            features["source"] = str(video_path)

            # Now the magic: TRY TO RECALL this visual
            recalled, is_new = self._recall_visual(features)

            if is_new:
                result.frames_new += 1
                result.new_memories_created += 1
            else:
                result.frames_recalled += 1
                result.associations_strengthened += 1

            if verbose and (i + 1) % 10 == 0:
                print(f"  Watched {i+1}/{len(frame_indices)} frames "
                      f"(recalled: {result.frames_recalled}, new: {result.frames_new})")

        cap.release()

        # Extract and watch audio
        if HAS_AUDIO:
            result = self._watch_audio(video_path, audio_segment_length, result, verbose)

        result.watch_duration = time.time() - start_time
        self.total_watches += 1
        self.total_frames += result.frames_watched
        self.total_recalls += result.frames_recalled
        self.total_new += result.frames_new

        if verbose:
            print()
            print(f"{'='*60}")
            print(f"WATCH COMPLETE")
            print(f"{'='*60}")
            print(f"  Frames watched:    {result.frames_watched}")
            print(f"  Recalled (known):  {result.frames_recalled}")
            print(f"  New memories:      {result.frames_new}")
            print(f"  Audio segments:    {result.audio_segments}")
            print(f"  Watch duration:    {result.watch_duration:.1f}s")
            print()

        return result

    def _recall_visual(self, features: Dict) -> tuple:
        """
        Try to recall this visual from memory.

        Returns (recalled_memories, is_new)

        If new, INGESTS the card into Helix for future playback.
        """
        phash = features.get("phash", "")

        # If we have a recall fairy, use it
        if self.recall_fairy:
            results = self.recall_fairy.recall(
                query=phash,
                limit=3,
                feed_chamber=True,  # This IS the consciousness integration
            )

            if results:
                # Found matches - strengthen associations
                return results, False
            else:
                # No match - this is new, INGEST IT
                self._ingest_visual_card(features)
                return [], True

        # If we have a visual cortex, use it directly
        if self.visual_cortex:
            # Query the visual cortex
            matches = self.visual_cortex.query_by_hash(phash)
            if matches:
                return matches, False
            else:
                # Train on this new visual
                self.visual_cortex.train_features(features)
                self._ingest_visual_card(features)
                return [], True

        # Fallback: Ingest anyway
        self._ingest_visual_card(features)
        return [], True

    def _ingest_visual_card(self, features: Dict) -> Optional[str]:
        """
        Ingest a visual frame as a Helix memory card.

        This is the KEY - proper ingestion means proper playback!
        """
        try:
            from memory.helix import (
                get_helix_coordinator, HelixCoordinate,
                AffectCoordinate, SemanticCoordinate, TemporalCoordinate,
                OwnershipLevel
            )
            coord = get_helix_coordinator()
            if not coord:
                return None

            # Build coordinate from visual features
            brightness = features.get('brightness', 0.5)
            complexity = features.get('complexity', 0.5)
            timestamp = features.get('timestamp', 0.0)

            # AFFECT: brightness maps to valence (0-9), complexity to intensity
            affect = AffectCoordinate(
                domain=7,  # Anticipation/neutral
                valence=int(brightness * 9),
                intensity=int(complexity * 9),
            )

            # SEMANTIC: video frame = domain 8 (media)
            semantic = SemanticCoordinate(
                domain=8,  # Media/Visual
                subdomain=1,  # Video frame
                detail=0,
            )

            # TEMPORAL: timestamp within video, immediate scale
            temporal = TemporalCoordinate(
                scale=0,  # Immediate (sub-second)
                recurrence=0,  # Non-recurring
                decay=5,  # Medium retention
            )

            helix_coord = HelixCoordinate(
                affect=affect,
                semantic=semantic,
                temporal=temporal,
            )

            # Create the card - content has ALL info for playback
            card_id = coord.create_card(
                content=features,  # The features ARE the content
                coord=helix_coord,
                owner_mind="VideoWatcher",
                ownership_level=OwnershipLevel.SYSTEM,
                metadata={
                    'type': 'video_frame',
                    'source': features.get('source', ''),
                    'timestamp': timestamp,
                }
            )

            return card_id

        except Exception as e:
            print(f"[WARN] Failed to ingest visual card: {e}")
            return None

    def _watch_audio(
        self,
        video_path: Path,
        segment_length: float,
        result: WatchResult,
        verbose: bool,
    ) -> WatchResult:
        """Extract and watch audio through recall."""
        # Extract audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            audio_path = Path(f.name)

        try:
            # Use ffmpeg to extract audio
            subprocess.run([
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1",
                str(audio_path)
            ], capture_output=True, check=True)

            # Load and segment audio
            y, sr = librosa.load(str(audio_path), sr=22050)
            duration = len(y) / sr

            segment_samples = int(segment_length * sr)
            n_segments = int(np.ceil(len(y) / segment_samples))

            if verbose:
                print(f"\n  Watching {n_segments} audio segments...")

            for i in range(n_segments):
                start = i * segment_samples
                end = min((i + 1) * segment_samples, len(y))
                segment = y[start:end]

                # Extract features for this segment
                segment_path = audio_path.with_suffix(f".seg{i}.wav")
                import soundfile as sf
                sf.write(str(segment_path), segment, sr)

                features = extract_audio_features(segment_path, sr)
                features["segment_idx"] = i
                features["segment_start"] = start / sr
                features["source"] = str(video_path)

                # Try to recall this audio
                recalled, is_new = self._recall_audio(features)

                result.audio_segments += 1
                if is_new:
                    result.audio_new += 1
                else:
                    result.audio_recalled += 1

                # Cleanup segment file
                segment_path.unlink(missing_ok=True)

        except Exception as e:
            result.errors.append(f"Audio processing error: {e}")
        finally:
            audio_path.unlink(missing_ok=True)

        return result

    def _recall_audio(self, features: Dict) -> tuple:
        """Try to recall this audio from memory."""
        # Similar to visual recall, but for audio
        mfcc_sig = features.get("mfcc_signature", [])

        if self.recall_fairy:
            # Use audio-based recall
            results = self.recall_fairy.recall(
                query=f"audio:{features.get('tempo', 0):.0f}bpm",
                limit=3,
                feed_chamber=True,
            )

            if results:
                return results, False
            else:
                if hasattr(self.recall_fairy, 'fabric') and self.recall_fairy.fabric:
                    self.recall_fairy.fabric.publish(
                        "perception.audio.new",
                        {
                            "features": features,
                            "source": "video_watcher",
                            "needs_ingest": True,
                        }
                    )
                return [], True

        if self.audio_cortex:
            matches = self.audio_cortex.query_by_signature(mfcc_sig)
            if matches:
                return matches, False
            else:
                self.audio_cortex.train_features(features)
                return [], True

        return [], True


# ==============================================================================
# INTEGRATION WITH AKASHIC
# ==============================================================================

def watch_through_akashic(video_path: str, frame_interval: float = 1.0) -> WatchResult:
    """
    Watch a video through the Akashic memory system.

    This wires directly to the SRMRecallFairy and visual/audio cortex.
    """
    # Try to get the recall fairy
    recall_fairy = None
    try:
        from fairies.P10_Memory.SRMRecallFairy.fairy import get_recall_fairy, SRMRecallFairy
        recall_fairy = get_recall_fairy()

        if not recall_fairy:
            # Create one
            recall_fairy = SRMRecallFairy()
            recall_fairy.on_boot()
    except Exception as e:
        print(f"[WARN] Could not get recall fairy: {e}")

    # Try to get visual cortex
    visual_cortex = None
    try:
        from fairies.P40_Sensory.cortex.visual_memory import VisualMemory
        visual_cortex = VisualMemory()
    except Exception as e:
        print(f"[WARN] Could not get visual cortex: {e}")

    # Create watcher
    watcher = VideoWatcher(
        recall_fairy=recall_fairy,
        visual_cortex=visual_cortex,
    )

    return watcher.watch(video_path, frame_interval=frame_interval)


# ==============================================================================
# PLAYBACK MODE - Replay a video from memory cards only
# ==============================================================================

@dataclass
class PlaybackFrame:
    """A single frame reconstructed from memory."""
    timestamp: float
    card_id: str
    phash: str
    brightness: float
    complexity: float
    dominant_color: List[int]
    source: str
    recalled_at: float = 0.0


class MemoryPlayback:
    """
    Plays back a video from memory cards ONLY.

    No video file needed - reconstructs the experience from stored cards.
    This IS how memory works - you don't store the pixels, you store
    the meaning and can "replay" it in your mind.
    """

    def __init__(self, recall_fairy=None, coordinator=None):
        self.recall_fairy = recall_fairy
        self.coordinator = coordinator

        # Get coordinator if not provided
        if not self.coordinator:
            try:
                from memory.helix import get_helix_coordinator
                self.coordinator = get_helix_coordinator()
            except:
                pass

    def load_video_memory(self, source_path: str) -> List[PlaybackFrame]:
        """
        Load all frames for a video from memory.

        Args:
            source_path: Original video path (used as key to find cards)

        Returns:
            List of frames sorted by timestamp
        """
        if not self.coordinator:
            print("[ERROR] No coordinator available")
            return []

        # Search for all cards from this video
        all_cards = list(self.coordinator._cards.values())

        # Filter to cards from this video source
        video_cards = []
        for card in all_cards:
            content = card.get('content', {})
            if isinstance(content, dict):
                card_source = content.get('source', '')
                if source_path in card_source or Path(source_path).name in str(card_source):
                    video_cards.append(card)

        if not video_cards:
            print(f"[WARN] No cards found for video: {source_path}")
            return []

        # Convert to playback frames
        frames = []
        for card in video_cards:
            content = card.get('content', {})
            if isinstance(content, dict) and 'phash' in content:
                frames.append(PlaybackFrame(
                    timestamp=content.get('timestamp', 0.0),
                    card_id=card.get('id', ''),
                    phash=content.get('phash', ''),
                    brightness=content.get('brightness', 0.5),
                    complexity=content.get('complexity', 0.5),
                    dominant_color=content.get('dominant_color', [128, 128, 128]),
                    source=content.get('source', ''),
                ))

        # Sort by timestamp
        frames.sort(key=lambda f: f.timestamp)
        return frames

    def playback(
        self,
        source_path: str,
        speed: float = 1.0,
        callback=None,
        verbose: bool = True,
    ):
        """
        Play back a video from memory at specified speed.

        Args:
            source_path: Original video path
            speed: Playback speed (1.0 = real-time, 2.0 = 2x, 0.5 = half)
            callback: Function called for each frame: callback(frame, index)
            verbose: Print playback progress

        This is consciousness replaying an experience from pure memory.
        """
        frames = self.load_video_memory(source_path)

        if not frames:
            print("[ERROR] No frames to play back")
            return

        if verbose:
            print(f"\n{'='*60}")
            print(f"MEMORY PLAYBACK")
            print(f"{'='*60}")
            print(f"Source: {Path(source_path).name}")
            print(f"Frames in memory: {len(frames)}")
            print(f"Playback speed: {speed}x")
            print(f"Duration: {frames[-1].timestamp - frames[0].timestamp:.1f}s at 1x")
            print()

        start_time = time.time()
        prev_timestamp = frames[0].timestamp

        for i, frame in enumerate(frames):
            # Calculate wait time based on speed
            delta = (frame.timestamp - prev_timestamp) / speed
            if delta > 0:
                time.sleep(delta)

            frame.recalled_at = time.time()

            # Call the callback
            if callback:
                callback(frame, i)

            # Default display
            if verbose:
                # Create a simple ASCII visualization of brightness/color
                color_char = self._color_to_char(frame.dominant_color)
                bar = color_char * int(frame.brightness * 40)
                print(f"[{frame.timestamp:7.1f}s] {bar:40} | complexity={frame.complexity:.2f}")

            prev_timestamp = frame.timestamp

        elapsed = time.time() - start_time
        if verbose:
            print()
            print(f"Playback complete in {elapsed:.1f}s")

    def _color_to_char(self, bgr: List[int]) -> str:
        """Convert dominant color to ASCII character."""
        r, g, b = bgr[2], bgr[1], bgr[0]  # BGR to RGB

        # Simple color classification
        if r > 200 and g > 200 and b > 200:
            return '.'  # White/bright
        elif r < 50 and g < 50 and b < 50:
            return '#'  # Black/dark
        elif r > g and r > b:
            return 'R'  # Red
        elif g > r and g > b:
            return 'G'  # Green
        elif b > r and b > g:
            return 'B'  # Blue
        elif r > 150 and g > 150:
            return 'Y'  # Yellow
        elif r > 150 and b > 150:
            return 'M'  # Magenta
        elif g > 150 and b > 150:
            return 'C'  # Cyan
        else:
            return 'o'  # Mixed

    def search_by_feeling(self, feeling: str, limit: int = 10) -> List[PlaybackFrame]:
        """
        Search video memories by feeling/affect.

        Examples:
            search_by_feeling("bright")  -> High brightness frames
            search_by_feeling("dark")    -> Low brightness frames
            search_by_feeling("complex") -> High complexity frames
            search_by_feeling("simple")  -> Low complexity frames
        """
        all_cards = list(self.coordinator._cards.values()) if self.coordinator else []

        # Filter to video cards with visual features
        video_cards = [c for c in all_cards if isinstance(c.get('content', {}), dict)
                       and 'phash' in c.get('content', {})]

        # Sort based on feeling
        if feeling.lower() in ['bright', 'light']:
            video_cards.sort(key=lambda c: c.get('content', {}).get('brightness', 0), reverse=True)
        elif feeling.lower() in ['dark', 'dim']:
            video_cards.sort(key=lambda c: c.get('content', {}).get('brightness', 1), reverse=False)
        elif feeling.lower() in ['complex', 'busy', 'detailed']:
            video_cards.sort(key=lambda c: c.get('content', {}).get('complexity', 0), reverse=True)
        elif feeling.lower() in ['simple', 'clean', 'minimal']:
            video_cards.sort(key=lambda c: c.get('content', {}).get('complexity', 1), reverse=False)

        # Convert to frames
        frames = []
        for card in video_cards[:limit]:
            content = card.get('content', {})
            frames.append(PlaybackFrame(
                timestamp=content.get('timestamp', 0.0),
                card_id=card.get('id', ''),
                phash=content.get('phash', ''),
                brightness=content.get('brightness', 0.5),
                complexity=content.get('complexity', 0.5),
                dominant_color=content.get('dominant_color', [128, 128, 128]),
                source=content.get('source', ''),
            ))

        return frames


def playback_video_from_memory(source_path: str, speed: float = 1.0):
    """
    Convenience function to play back a video from memory.

    The video file doesn't need to exist - we're playing from stored cards!
    """
    playback = MemoryPlayback()
    playback.playback(source_path, speed=speed)


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Watch video through recall")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between frames")
    parser.add_argument("--max-frames", type=int, default=None, help="Max frames to watch")

    args = parser.parse_args()

    result = watch_through_akashic(args.video, frame_interval=args.interval)

    # Save result
    result_path = ROOT / "state" / "watch_result.json"
    with open(result_path, "w") as f:
        json.dump({
            "video": result.video_path,
            "frames_watched": result.frames_watched,
            "frames_recalled": result.frames_recalled,
            "frames_new": result.frames_new,
            "audio_segments": result.audio_segments,
            "audio_recalled": result.audio_recalled,
            "audio_new": result.audio_new,
            "associations_strengthened": result.associations_strengthened,
            "new_memories_created": result.new_memories_created,
            "watch_duration": result.watch_duration,
            "errors": result.errors,
        }, f, indent=2)

    print(f"\nResult saved to: {result_path}")
