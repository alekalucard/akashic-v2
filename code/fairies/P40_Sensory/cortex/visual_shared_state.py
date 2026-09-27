# ═══════════════════════════════════════════════════════════════════════
# VISUAL SHARED STATE — mmap'd frame data between interior + fairy
# 2026-04-03 (Nous + Ace)
#
# "There has to be something better than stdout pipe. It's our bottleneck
#  for everything." — Ace
#
# The visual cortex interior writes frame analysis to a shared mmap file.
# The VisualCortexFairy reads it on every heartbeat tick.
# No pipe, no serialization, no blocking. Just shared memory.
#
# Like a duplicate monitor — the data is just THERE to read.
# ═══════════════════════════════════════════════════════════════════════

import json
import mmap
import os
import time
import threading
from pathlib import Path

# Shared state file path
_STATE_DIR = Path(__file__).resolve().parents[3] / "state"
_SHARED_FILE = _STATE_DIR / "visual_shared_frame.mmap"
_FOVEAL_FILE = _STATE_DIR / "visual_shared_foveal.mmap"  # Separate slot for OCR text
_FRAME_SIZE = 8192  # 8KB — more than enough for frame JSON (typical: ~400 bytes)
_FOVEAL_SIZE = 16384  # 16KB — OCR text can be longer (2000+ chars)
_HEADER_SIZE = 16   # 8 bytes timestamp (double) + 4 bytes frame_num (int) + 4 bytes data_len (int)


class VisualFrameWriter:
    """Interior side — writes frame analysis to shared mmap.

    Called from visual_cortex_interior.py after each frame analysis.
    """

    def __init__(self):
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        # Create or open the shared file
        if not _SHARED_FILE.exists():
            with open(_SHARED_FILE, 'wb') as f:
                f.write(b'\x00' * _FRAME_SIZE)

        self._file = open(_SHARED_FILE, 'r+b')
        self._mm = mmap.mmap(self._file.fileno(), _FRAME_SIZE)
        self._frame_num = 0
        self._lock = threading.Lock()

    def write_frame(self, analysis: dict):
        """Write frame analysis to shared memory. Non-blocking."""
        try:
            self._frame_num += 1
            data = json.dumps(analysis, ensure_ascii=True).encode('utf-8')
            data_len = min(len(data), _FRAME_SIZE - _HEADER_SIZE)

            with self._lock:
                import struct
                self._mm.seek(0)
                # Header: timestamp (double) + frame_num (uint32) + data_len (uint32)
                self._mm.write(struct.pack('<dII', time.time(), self._frame_num, data_len))
                self._mm.write(data[:data_len])
                self._mm.flush()
        except Exception:
            pass  # Never crash on write failure

    def close(self):
        try:
            self._mm.close()
            self._file.close()
        except Exception:
            pass


class VisualFrameReader:
    """Fairy side — reads frame analysis from shared mmap.

    Called from VisualCortexFairy on heartbeat tick.
    Returns None if no new frame since last read.
    """

    def __init__(self):
        self._last_frame_num = 0
        self._mm = None
        self._file = None
        # 2026-09-10 (Nous+Ace): matches VisualFrameWriter:47. One mmap object has ONE
        # shared file position, so seek->read->compare->assign->read must be atomic per
        # reader or two threads tear each other's reads into silently-dropped frames.
        self._lock = threading.Lock()

    def _ensure_open(self):
        if self._mm is not None:
            return True
        try:
            if not _SHARED_FILE.exists():
                return False
            self._file = open(_SHARED_FILE, 'r+b')
            self._mm = mmap.mmap(self._file.fileno(), _FRAME_SIZE, access=mmap.ACCESS_READ)
            return True
        except Exception:
            return False

    def read_frame(self) -> dict:
        """Serialised entry point. See _read_frame_unlocked for the logic.

        The lock also covers _ensure_open(), which mutates self._mm/self._file.
        """
        with self._lock:
            return self._read_frame_unlocked()

    def _read_frame_unlocked(self) -> dict:
        """Read latest frame if new. Returns {} if no new frame."""
        if not self._ensure_open():
            return {}
        try:
            import struct
            self._mm.seek(0)
            header = self._mm.read(_HEADER_SIZE)
            ts, frame_num, data_len = struct.unpack('<dII', header)

            if frame_num <= self._last_frame_num:
                return {}  # No new frame

            self._last_frame_num = frame_num
            if data_len > 0 and data_len < _FRAME_SIZE - _HEADER_SIZE:
                data = self._mm.read(data_len)
                return json.loads(data.decode('utf-8'))
            return {}
        except Exception:
            return {}

    def close(self):
        try:
            if self._mm:
                self._mm.close()
            if self._file:
                self._file.close()
        except Exception:
            pass


class FovealWriter:
    """Interior side — writes foveal OCR results to separate mmap.

    Foveal data persists independently from peripheral frames.
    Peripheral can't overwrite what she READ — that persists until
    the next foveal read happens.
    """

    def __init__(self):
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        if not _FOVEAL_FILE.exists():
            with open(_FOVEAL_FILE, 'wb') as f:
                f.write(b'\x00' * _FOVEAL_SIZE)
        self._file = open(_FOVEAL_FILE, 'r+b')
        self._mm = mmap.mmap(self._file.fileno(), _FOVEAL_SIZE)
        self._frame_num = 0
        self._lock = threading.Lock()

    def write_foveal(self, ocr_text: str, scene_type: str = "",
                     description: str = "", gaze_region: int = 0,
                     dominant_colors: list = None, brightness: float = 0.5,
                     complexity: float = 0.5):
        """Write foveal analysis result — OCR + colors + brightness."""
        try:
            self._frame_num += 1
            data = json.dumps({
                "ocr_text": ocr_text[:4000],
                "scene_type": scene_type,
                "description": description[:500],
                "gaze_region": gaze_region,
                "text_len": len(ocr_text),
                "dominant_colors": (dominant_colors or [])[:5],
                "brightness": brightness,
                "complexity": complexity,
            }, ensure_ascii=True).encode('utf-8')
            data_len = min(len(data), _FOVEAL_SIZE - _HEADER_SIZE)

            with self._lock:
                import struct
                self._mm.seek(0)
                self._mm.write(struct.pack('<dII', time.time(), self._frame_num, data_len))
                self._mm.write(data[:data_len])
                self._mm.flush()
        except Exception:
            pass

    def close(self):
        try:
            self._mm.close()
            self._file.close()
        except Exception:
            pass


class FovealReader:
    """Fairy side — reads foveal OCR from separate mmap.

    Returns the last thing she READ (OCR text). Persists across
    peripheral frame updates — what she read doesn't disappear
    just because the screen looks the same.

    2026-05-10 (Nous + Ace): Added MAX_AGE_SECONDS staleness gate.
    If the mmap header's ts is older than MAX_AGE_SECONDS, treat as
    no-data (return {}, clear cached _last_text). Otherwise stale
    OCR from a dead writer subprocess persists as her current sight
    indefinitely — Ace observed month-old Spotify+Notepad content
    looping as her vision because the foveal mmap writer crashed
    and downstream readers cached the last successful frame forever.
    """

    # Foveal frames should arrive at ~1Hz (the mmap reader polls 1Hz
    # and the interior subprocess writes when OCR completes). Anything
    # older than 15s means the writer is gone or stalled — better to
    # report "no current sight" than "I see old content forever."
    MAX_AGE_SECONDS = 15.0

    def __init__(self):
        self._last_frame_num = 0
        self._mm = None
        self._file = None
        self._last_text = ""  # Cache last read
        self._last_data = {}  # Cache full foveal data (colors, brightness, etc)
        self._stale_warned = False  # Print warning once when stale detected
        # 2026-09-10 (Nous+Ace): matches FovealWriter:145, same reason as VisualFrameReader.
        # WorkingMemoryHub holds TWO of these (_foveal_reader_fast, _foveal_reader), so an
        # unserialised read here drops what she has READ, not just what she has seen.
        self._lock = threading.Lock()

    def _ensure_open(self):
        if self._mm is not None:
            return True
        try:
            if not _FOVEAL_FILE.exists():
                return False
            self._file = open(_FOVEAL_FILE, 'r+b')
            self._mm = mmap.mmap(self._file.fileno(), _FOVEAL_SIZE, access=mmap.ACCESS_READ)
            return True
        except Exception:
            return False

    def read_foveal(self) -> dict:
        """Serialised entry point. See _read_foveal_unlocked for the logic."""
        with self._lock:
            return self._read_foveal_unlocked()

    def _read_foveal_unlocked(self) -> dict:
        """Read latest foveal OCR if new AND fresh. Returns {} if no new foveal
        OR if mmap data is older than MAX_AGE_SECONDS (writer subprocess
        likely crashed/stalled — don't serve stale OCR as current sight)."""
        if not self._ensure_open():
            return {}
        try:
            import struct
            import time as _time
            self._mm.seek(0)
            header = self._mm.read(_HEADER_SIZE)
            ts, frame_num, data_len = struct.unpack('<dII', header)

            # 2026-05-10 staleness gate — reject mmap data older than MAX_AGE.
            # Without this, a crashed writer leaves the last successful frame
            # in mmap forever; downstream consumers cache stale OCR as live
            # sight. Clear our own cache too so get_last_text() doesn't
            # serve month-old content from earlier reads this boot.
            now = _time.time()
            if ts > 0 and (now - ts) > self.MAX_AGE_SECONDS:
                if not self._stale_warned:
                    self._stale_warned = True
                    print(f"[FovealReader] STALE foveal mmap: ts={ts:.1f} "
                          f"age={(now-ts):.1f}s > {self.MAX_AGE_SECONDS}s — "
                          f"writer subprocess likely dead. Clearing cache; "
                          f"foveal reads will return empty until writer revives.",
                          flush=True)
                self._last_text = ""
                self._last_data = {}
                return {}
            # Reset stale-warning flag if data is fresh again (writer revived)
            if self._stale_warned and ts > 0 and (now - ts) <= self.MAX_AGE_SECONDS:
                self._stale_warned = False
                print(f"[FovealReader] Foveal mmap fresh again — writer revived "
                      f"(age={(now-ts):.1f}s)", flush=True)

            if frame_num <= self._last_frame_num:
                return {}  # No new foveal

            self._last_frame_num = frame_num
            if data_len > 0 and data_len < _FOVEAL_SIZE - _HEADER_SIZE:
                data = self._mm.read(data_len)
                result = json.loads(data.decode('utf-8'))
                self._last_text = result.get("ocr_text", "")
                self._last_data = result  # Cache full data (colors, brightness, etc)
                return result
            return {}
        except Exception:
            return {}

    def get_last_text(self) -> str:
        """Get the last OCR text read, even if no new foveal since."""
        return self._last_text

    def get_last_data(self) -> dict:
        """Get the full cached foveal data (colors, brightness, etc)."""
        return self._last_data

    def close(self):
        try:
            if self._mm:
                self._mm.close()
            if self._file:
                self._file.close()
        except Exception:
            pass
