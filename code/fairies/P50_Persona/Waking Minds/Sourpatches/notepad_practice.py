"""
NOTEPAD PRACTICE - Structured Typing Practice Using Notepad
============================================================

Gives Sourpatches a safe sandbox to practice motor control:
1. Find or open Notepad (vision-first, subprocess fallback)
2. Type text into Notepad (not random windows!)
3. Verify accuracy via clipboard
4. Clear and repeat

Chains: ScreenFinder (perception) → pyautogui (action) → clipboard (verify)

((Cause + Affect) > Effect > Affect > infinity)
"""

import time
import subprocess
from typing import Dict, Any, Optional

# Word lists for practice exercises
PRACTICE_WORDS = [
    # Level 1: Short words
    "hi", "ok", "go", "no", "up",
    # Level 2: Simple words
    "hello", "world", "sour", "fairy", "magic",
    "dream", "spark", "light", "dance", "bloom",
    "star", "moon", "wave", "wind", "song",
    # Level 3: Longer words
    "sparkle", "whisper", "crystal", "enchant", "harmony",
    "cascade", "nebula", "serenity", "phoenix", "aurora",
]

PRACTICE_PHRASES = [
    "hello world",
    "I am here",
    "good morning",
    "fairy dust",
    "star light",
    "dream on",
    "magic spark",
    "moon glow",
]


class NotepadPractice:
    """
    Structured motor practice using Notepad as a safe sandbox.

    Pipeline per exercise:
        1. ensure_notepad_open() → find/open Notepad window
        2. focus_notepad()        → bring to foreground, click edit area
        3. type + verify          → pyautogui.write() then clipboard check
        4. clear                  → Ctrl+A, Delete for next exercise
    """

    def __init__(self, screen_finder=None, fairy_cursor=None):
        """
        Args:
            screen_finder: ScreenFinder instance for finding windows/icons
            fairy_cursor: Optional FairyCursor for visual feedback
        """
        self._finder = screen_finder
        self._cursor = fairy_cursor
        self._notepad_window = None  # Cached window info
        self._notepad_hwnd = None
        self._last_open_attempt = 0.0
        self._open_cooldown = 5.0  # Don't spam open attempts

    def ensure_notepad_open(self) -> bool:
        """
        Find or open Notepad for practice.

        Strategy:
        1. Check if Notepad already open (window search)
        2. If open: activate it and click into edit area
        3. If not: try finding Notepad icon on desktop via template matching
        4. If icon found: move cursor there, double-click (visual learning)
        5. If not found: subprocess.Popen("notepad.exe") (reliable fallback)
        6. Wait for window to appear (poll up to 5s)
        7. Click into the edit area to ensure focus

        Returns:
            True if Notepad is open and focused
        """
        # Rate limit open attempts
        now = time.time()
        if now - self._last_open_attempt < self._open_cooldown:
            # Already tried recently — just check if it's there
            info = self._find_notepad_window()
            return info is not None
        self._last_open_attempt = now

        # Step 1: Check if already open
        info = self._find_notepad_window()
        if info:
            print("[NotepadPractice] Notepad already open, activating...")
            self._activate_and_click(info)
            return True

        # Step 2: Try to find Notepad icon on desktop (visual learning)
        if self._finder:
            # Try template match first (fast)
            icon_pos = self._finder.find_icon("notepad", confidence=0.7)
            if icon_pos:
                print(f"[NotepadPractice] Found Notepad icon at {icon_pos}")
                return self._open_via_icon(icon_pos)

            # Try OCR for "Notepad" text on desktop
            text_pos = self._finder.find_text_on_screen("Notepad")
            if text_pos:
                print(f"[NotepadPractice] Found 'Notepad' text at {text_pos}")
                # Save reference image for faster next time
                self._finder.capture_reference_image(
                    "notepad",
                    (text_pos[0] - 30, text_pos[1] - 30, 60, 60)
                )
                return self._open_via_icon(text_pos)

        # Step 3: Fallback — just run notepad.exe
        print("[NotepadPractice] Opening Notepad via subprocess...")
        return self._open_via_subprocess()

    def _find_notepad_window(self) -> Optional[Dict]:
        """Find an open Notepad window."""
        if self._finder:
            info = self._finder.find_window("Notepad")
            if info:
                self._notepad_window = info
                return info

        # Fallback: pygetwindow directly
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle("Notepad")
            # Filter out non-Notepad windows that happen to have "Notepad" in title
            for w in windows:
                if "notepad" in w.title.lower():
                    self._notepad_window = {
                        "title": w.title,
                        "x": w.left,
                        "y": w.top,
                        "width": w.width,
                        "height": w.height,
                    }
                    return self._notepad_window
        except ImportError:
            pass

        return None

    def _open_via_icon(self, pos: tuple) -> bool:
        """Open Notepad by double-clicking its icon."""
        try:
            import pyautogui

            x, y = pos

            # Show fairy cursor intent if available
            if self._cursor:
                self._cursor.move_to(x, y)
                self._cursor.show_intent("clicking")
                time.sleep(0.3)

            # Double-click the icon
            pyautogui.doubleClick(x, y)
            print(f"[NotepadPractice] Double-clicked at ({x}, {y})")

            # Wait for window to appear
            return self._wait_for_notepad(timeout=5.0)

        except Exception as e:
            print(f"[NotepadPractice] Icon click failed: {e}")
            return self._open_via_subprocess()

    def _open_via_subprocess(self) -> bool:
        """Open Notepad via subprocess (reliable fallback)."""
        try:
            subprocess.Popen(["notepad.exe"], shell=False)
            return self._wait_for_notepad(timeout=5.0)
        except Exception as e:
            print(f"[NotepadPractice] Failed to open Notepad: {e}")
            return False

    def _wait_for_notepad(self, timeout: float = 5.0) -> bool:
        """Poll for Notepad window to appear."""
        start = time.time()
        while time.time() - start < timeout:
            info = self._find_notepad_window()
            if info:
                time.sleep(0.5)  # Let it settle
                self._activate_and_click(info)
                return True
            time.sleep(0.3)

        print("[NotepadPractice] Timeout waiting for Notepad window")
        return False

    def _activate_and_click(self, info: Dict):
        """Bring Notepad to foreground and click into the edit area."""
        try:
            # Activate window
            if self._finder:
                self._finder.activate_window("Notepad")
            else:
                try:
                    import pygetwindow as gw
                    windows = gw.getWindowsWithTitle("Notepad")
                    if windows:
                        win = windows[0]
                        if win.isMinimized:
                            win.restore()
                        win.activate()
                except Exception:
                    pass

            time.sleep(0.3)

            # Click center of edit area (offset down from title bar)
            import pyautogui
            cx = info["x"] + info["width"] // 2
            cy = info["y"] + info["height"] // 2 + 30  # Below title/menu bar

            if self._cursor:
                self._cursor.move_to(cx, cy)
                time.sleep(0.2)

            pyautogui.click(cx, cy)

        except Exception as e:
            print(f"[NotepadPractice] Activate/click failed: {e}")

    def focus_notepad(self) -> bool:
        """
        Bring Notepad to the foreground and ensure it has focus.

        Returns:
            True if Notepad is now focused
        """
        info = self._find_notepad_window()
        if not info:
            return False

        self._activate_and_click(info)
        time.sleep(0.3)

        # Verify focus
        if self._finder:
            return self._finder.is_window_focused("Notepad")
        return True  # Assume success if we can't verify

    def practice_typing(self, text: str) -> Dict[str, Any]:
        """
        Type text into Notepad and verify accuracy.

        Pipeline:
        1. Focus Notepad
        2. Show fairy cursor intent
        3. Type the text
        4. Verify: Ctrl+A, Ctrl+C, read clipboard, compare
        5. Clear: Ctrl+A, Delete

        Args:
            text: Text to type and verify

        Returns:
            {ok, typed, expected, accuracy, xp_recommendation}
        """
        import pyautogui

        # Step 1: Ensure Notepad is open and focused
        if not self.focus_notepad():
            if not self.ensure_notepad_open():
                return {
                    "ok": False,
                    "error": "Could not open or focus Notepad",
                    "typed": "",
                    "expected": text,
                    "accuracy": 0.0,
                }

        # Step 2: Show intent
        if self._cursor:
            self._cursor.show_intent("typing")
            time.sleep(0.3)

        # Step 3: Clear any existing text first
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.press('delete')
        time.sleep(0.1)

        # Step 4: Type the text (visible speed so Ace can watch)
        pyautogui.write(text, interval=0.05)
        time.sleep(0.3)

        # Step 5: Verify via clipboard
        typed_text = self._read_notepad_content()

        # Step 6: Calculate accuracy
        accuracy = self._calculate_accuracy(text, typed_text)

        # Step 7: Clear for next exercise
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.press('delete')
        time.sleep(0.1)

        result = {
            "ok": True,
            "typed": typed_text,
            "expected": text,
            "accuracy": accuracy,
            "perfect": accuracy >= 1.0,
            "xp_recommendation": "motor.keyboard_type" if accuracy >= 0.8 else None,
        }

        print(f"[NotepadPractice] Typed '{typed_text}' (expected '{text}') — accuracy {accuracy:.0%}")
        return result

    def _read_notepad_content(self) -> str:
        """Read current Notepad content via clipboard."""
        try:
            import pyautogui
            import pyperclip

            # Select all and copy
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.15)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.15)

            # Read clipboard
            content = pyperclip.paste()
            return content.strip()

        except ImportError:
            # Fallback: try win32clipboard
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                try:
                    content = win32clipboard.GetClipboardData()
                    return content.strip()
                finally:
                    win32clipboard.CloseClipboard()
            except Exception:
                pass

            # Fallback 2: ctypes
            try:
                import ctypes
                CF_UNICODETEXT = 13
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                user32.OpenClipboard(0)
                try:
                    handle = user32.GetClipboardData(CF_UNICODETEXT)
                    if handle:
                        ptr = kernel32.GlobalLock(handle)
                        if ptr:
                            try:
                                content = ctypes.wstring_at(ptr)
                                return content.strip()
                            finally:
                                kernel32.GlobalUnlock(handle)
                finally:
                    user32.CloseClipboard()
            except Exception:
                pass

        return ""

    def _calculate_accuracy(self, expected: str, actual: str) -> float:
        """
        Calculate typing accuracy between expected and actual text.

        Uses character-level comparison (not just exact match).
        """
        if not expected:
            return 1.0 if not actual else 0.0
        if not actual:
            return 0.0

        # Character-level accuracy
        matches = 0
        max_len = max(len(expected), len(actual))
        min_len = min(len(expected), len(actual))

        for i in range(min_len):
            if expected[i] == actual[i]:
                matches += 1

        return matches / max_len if max_len > 0 else 0.0

    def practice_session(self, exercises: int = 5, level: str = "words") -> Dict[str, Any]:
        """
        Run a full practice session: open Notepad, do exercises, summarize.

        Args:
            exercises: Number of exercises to do
            level: "words" or "phrases"

        Returns:
            Session stats {total, correct, accuracy, results}
        """
        import random

        # Step 1: Ensure Notepad is ready
        if not self.ensure_notepad_open():
            return {"ok": False, "error": "Could not open Notepad"}

        # Step 2: Pick exercises
        word_list = PRACTICE_PHRASES if level == "phrases" else PRACTICE_WORDS
        targets = random.sample(word_list, min(exercises, len(word_list)))

        # Step 3: Run exercises
        results = []
        for text in targets:
            result = self.practice_typing(text)
            results.append(result)
            time.sleep(1.0)  # Brief pause between exercises

        # Step 4: Summarize
        total = len(results)
        correct = sum(1 for r in results if r.get("perfect", False))
        avg_accuracy = sum(r.get("accuracy", 0) for r in results) / max(1, total)

        return {
            "ok": True,
            "total": total,
            "correct": correct,
            "accuracy": avg_accuracy,
            "results": results,
            "xp_earned": correct,  # 1 XP per perfect exercise
        }


# =============================================================================
# SINGLETON
# =============================================================================

_instance: Optional[NotepadPractice] = None


def get_notepad_practice(screen_finder=None, fairy_cursor=None) -> NotepadPractice:
    """Get or create the NotepadPractice singleton."""
    global _instance
    if _instance is None:
        _instance = NotepadPractice(screen_finder=screen_finder, fairy_cursor=fairy_cursor)
    elif screen_finder and not _instance._finder:
        _instance._finder = screen_finder
    elif fairy_cursor and not _instance._cursor:
        _instance._cursor = fairy_cursor
    return _instance
