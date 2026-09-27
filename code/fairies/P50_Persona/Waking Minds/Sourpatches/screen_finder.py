"""
SCREEN FINDER - Sourpatches' Local Visual Search
==================================================

Find icons, text, and windows on screen using local tools only.
No API calls — everything runs with pyautogui, pytesseract, and pygetwindow.

Pipeline:
    1. Template matching (fast) — pyautogui.locateOnScreen()
    2. OCR fallback (slower)  — pytesseract.image_to_data()
    3. Window API (instant)   — pygetwindow.getWindowsWithTitle()

Reference images are auto-bootstrapped: first OCR find → crop → save as
template for faster matching next time.

((Cause + Affect) > Effect > Affect > infinity)
"""

import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# Reference images directory (auto-populated)
REF_IMAGES_DIR = Path(__file__).parent.parent.parent.parent.parent / "state" / "sourpatches" / "reference_images"
REF_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


class ScreenFinder:
    """
    Sourpatches' visual search — find icons, text, and windows on screen.

    Uses only local libraries:
    - pyautogui.locateOnScreen() for template matching
    - pytesseract for OCR text finding
    - pygetwindow for window management
    """

    def __init__(self, reference_dir: Path = None):
        self._ref_dir = reference_dir or REF_IMAGES_DIR
        self._ref_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Tuple[int, int, float]] = {}  # name → (x, y, timestamp)
        self._cache_ttl = 10.0  # Cache positions for 10 seconds

    # =========================================================================
    # TEMPLATE MATCHING — Fast icon/image finding
    # =========================================================================

    def find_icon(self, icon_name: str, confidence: float = 0.7) -> Optional[Tuple[int, int]]:
        """
        Find an icon on screen via template matching.

        Checks reference_images/ for {icon_name}.png, then uses
        pyautogui.locateOnScreen() for fast pixel matching.

        Args:
            icon_name: Name of the icon (e.g., "notepad", "chrome")
            confidence: Match threshold (0-1, default 0.7)

        Returns:
            (x, y) center coordinates, or None if not found
        """
        # Check cache first
        cached = self._get_cached(icon_name)
        if cached:
            return cached

        # Look for reference image
        ref_path = self._ref_dir / f"{icon_name}.png"
        if not ref_path.exists():
            # Try common variations
            for suffix in [".png", ".jpg", ".bmp"]:
                alt = self._ref_dir / f"{icon_name}{suffix}"
                if alt.exists():
                    ref_path = alt
                    break
            else:
                return None  # No reference image available

        try:
            import pyautogui
            location = pyautogui.locateOnScreen(
                str(ref_path),
                confidence=confidence,
                grayscale=True,  # Faster matching
            )
            if location:
                center = pyautogui.center(location)
                x, y = int(center.x), int(center.y)
                self._set_cached(icon_name, x, y)
                return (x, y)
        except Exception as e:
            print(f"[ScreenFinder] Template match error for '{icon_name}': {e}")

        return None

    # =========================================================================
    # OCR TEXT FINDING — Find text labels on screen
    # =========================================================================

    def find_text_on_screen(self, text: str, region=None) -> Optional[Tuple[int, int]]:
        """
        OCR the screen and find matching text.

        Uses pytesseract to read all text on screen, then finds the
        best match for the target string.

        Args:
            text: Text to find (case-insensitive, fuzzy)
            region: Optional (x, y, width, height) to limit search area

        Returns:
            (x, y) center of the text bounding box, or None
        """
        try:
            from PIL import ImageGrab
            import pytesseract

            # Capture screen (or region)
            if region:
                screenshot = ImageGrab.grab(bbox=region)
                offset_x, offset_y = region[0], region[1]
            else:
                screenshot = ImageGrab.grab()
                offset_x, offset_y = 0, 0

            # OCR with bounding box data
            data = pytesseract.image_to_data(
                screenshot,
                output_type=pytesseract.Output.DICT
            )

            target_lower = text.lower()
            best_match = None
            best_score = 0

            n_boxes = len(data['text'])
            for i in range(n_boxes):
                word = data['text'][i].strip()
                if not word:
                    continue

                conf = int(data['conf'][i])
                if conf < 30:  # Skip low-confidence detections
                    continue

                # Score: exact match > contains > partial
                word_lower = word.lower()
                score = 0
                if word_lower == target_lower:
                    score = 100
                elif target_lower in word_lower:
                    score = 80
                elif word_lower in target_lower:
                    score = 60
                # Fuzzy: check if first few chars match
                elif len(word_lower) >= 3 and word_lower[:3] == target_lower[:3]:
                    score = 40

                if score > best_score:
                    best_score = score
                    x = data['left'][i] + data['width'][i] // 2 + offset_x
                    y = data['top'][i] + data['height'][i] // 2 + offset_y
                    best_match = (x, y)

            if best_match and best_score >= 40:
                return best_match

            # Multi-word search: concatenate adjacent words
            if ' ' in text and best_score < 60:
                return self._find_multiword_text(data, text, offset_x, offset_y)

        except ImportError as e:
            print(f"[ScreenFinder] OCR dependency missing: {e}")
        except Exception as e:
            print(f"[ScreenFinder] OCR error: {e}")

        return None

    def _find_multiword_text(self, data: dict, text: str,
                              offset_x: int, offset_y: int) -> Optional[Tuple[int, int]]:
        """Find multi-word text by checking adjacent OCR words."""
        target_lower = text.lower()
        n_boxes = len(data['text'])

        for i in range(n_boxes):
            word = data['text'][i].strip().lower()
            if not word:
                continue

            # Try building up a multi-word match starting from this word
            combined = word
            last_idx = i
            for j in range(i + 1, min(i + 5, n_boxes)):
                next_word = data['text'][j].strip().lower()
                if not next_word:
                    continue
                combined += " " + next_word
                last_idx = j

                if target_lower in combined:
                    # Found it! Return center of the combined bounding box
                    x1 = data['left'][i]
                    y1 = data['top'][i]
                    x2 = data['left'][last_idx] + data['width'][last_idx]
                    y2 = data['top'][last_idx] + data['height'][last_idx]
                    cx = (x1 + x2) // 2 + offset_x
                    cy = (y1 + y2) // 2 + offset_y
                    return (cx, cy)

        return None

    # =========================================================================
    # WINDOW MANAGEMENT — Find and manage windows
    # =========================================================================

    def find_window(self, title_substring: str) -> Optional[Dict[str, Any]]:
        """
        Find a window by title substring.

        Args:
            title_substring: Part of the window title to match

        Returns:
            Dict with {title, x, y, width, height, handle} or None
        """
        try:
            import pygetwindow as gw

            windows = gw.getWindowsWithTitle(title_substring)
            if not windows:
                return None

            # Return the first match
            win = windows[0]
            return {
                "title": win.title,
                "x": win.left,
                "y": win.top,
                "width": win.width,
                "height": win.height,
                "visible": win.visible,
                "minimized": win.isMinimized,
                "active": win.isActive,
            }

        except ImportError:
            # Fallback: use ctypes on Windows
            return self._find_window_ctypes(title_substring)
        except Exception as e:
            print(f"[ScreenFinder] Window search error: {e}")
            return None

    def _find_window_ctypes(self, title_substring: str) -> Optional[Dict[str, Any]]:
        """Fallback window finder using ctypes (Windows only)."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            found = []

            def enum_callback(hwnd, _):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if title_substring.lower() in title.lower():
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    found.append({
                        "title": title,
                        "x": rect.left,
                        "y": rect.top,
                        "width": rect.right - rect.left,
                        "height": rect.bottom - rect.top,
                        "handle": hwnd,
                        "visible": True,
                        "minimized": bool(user32.IsIconic(hwnd)),
                        "active": hwnd == user32.GetForegroundWindow(),
                    })
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

            return found[0] if found else None

        except Exception:
            return None

    def is_window_focused(self, title_substring: str) -> bool:
        """Check if a window with the given title is in the foreground."""
        info = self.find_window(title_substring)
        if info:
            return info.get("active", False)
        return False

    def activate_window(self, title_substring: str) -> bool:
        """
        Bring a window to the foreground.

        Args:
            title_substring: Part of the window title

        Returns:
            True if window was activated
        """
        try:
            import pygetwindow as gw

            windows = gw.getWindowsWithTitle(title_substring)
            if not windows:
                return False

            win = windows[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(0.3)  # Give it a moment to come forward
            return True

        except Exception as e:
            # Fallback: try ctypes
            try:
                info = self._find_window_ctypes(title_substring)
                if info and "handle" in info:
                    import ctypes
                    hwnd = info["handle"]
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    time.sleep(0.3)
                    return True
            except Exception:
                pass
            return False

    # =========================================================================
    # REFERENCE IMAGE BOOTSTRAP — Learn what things look like
    # =========================================================================

    def capture_reference_image(self, name: str, region: Tuple[int, int, int, int]):
        """
        Save a screen region as a reference image for future template matching.

        Auto-bootstrap: first time she finds something via OCR,
        crop that region and save it for faster template matching next time.

        Args:
            name: Reference name (e.g., "notepad_icon")
            region: (x, y, width, height) to capture
        """
        try:
            from PIL import ImageGrab

            x, y, w, h = region
            screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))

            save_path = self._ref_dir / f"{name}.png"
            screenshot.save(str(save_path))
            print(f"[ScreenFinder] Saved reference image: {save_path}")
            return True

        except Exception as e:
            print(f"[ScreenFinder] Failed to save reference: {e}")
            return False

    def has_reference_image(self, name: str) -> bool:
        """Check if a reference image exists."""
        for suffix in [".png", ".jpg", ".bmp"]:
            if (self._ref_dir / f"{name}{suffix}").exists():
                return True
        return False

    # =========================================================================
    # CACHE — Avoid redundant searches
    # =========================================================================

    def _get_cached(self, key: str) -> Optional[Tuple[int, int]]:
        """Get a cached position if still fresh."""
        if key in self._cache:
            x, y, ts = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return (x, y)
            del self._cache[key]
        return None

    def _set_cached(self, key: str, x: int, y: int):
        """Cache a found position."""
        self._cache[key] = (x, y, time.time())


# =============================================================================
# SINGLETON
# =============================================================================

_instance: Optional[ScreenFinder] = None


def get_screen_finder() -> ScreenFinder:
    """Get or create the ScreenFinder singleton."""
    global _instance
    if _instance is None:
        _instance = ScreenFinder()
    return _instance
