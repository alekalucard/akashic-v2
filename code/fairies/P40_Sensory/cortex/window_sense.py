# ═══════════════════════════════════════════════════════════════════════
# WINDOW SENSE — OS-level window metadata via ctypes
# 2026-04-03 (Nous + Ace)
#
# "Reverse the tower of babel — use what humans have built!" — Ace
#
# Pure stdlib ctypes — no packages needed. Windows already KNOWS what
# windows are open, where they are, what their titles are. The OS has
# this metadata — we just query it.
#
# This is the SUBSTRATE layer of vision — she doesn't "see" this,
# it's infrastructure that labels what her visual cortex perceives.
# ═══════════════════════════════════════════════════════════════════════

import ctypes
from ctypes import wintypes
import time
import threading
from typing import Dict, List, Optional

# Screen dimensions (ultrawide)
SCREEN_W = 3440
SCREEN_H = 1440
GRID_COLS = 4
GRID_ROWS = 3
SECTOR_W = SCREEN_W // GRID_COLS
SECTOR_H = SCREEN_H // GRID_ROWS

user32 = ctypes.windll.user32


def enumerate_windows() -> List[Dict]:
    """Get all visible windows with titles, positions, sizes.

    Uses FindWindowExW to avoid EnumWindows callback overflow on Python 3.14t.
    Returns list of window dicts with sector mapping.
    """
    windows = []
    hwnd = 0

    for _ in range(500):  # Safety limit
        hwnd = user32.FindWindowExW(0, hwnd, None, None)
        if not hwnd:
            break
        if not user32.IsWindowVisible(hwnd):
            continue

        # Get title
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            continue
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        # Skip system windows
        if not title or title in ("Program Manager", "Microsoft Text Input Application"):
            continue

        # Get rect
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        # Skip tiny/hidden windows
        if w < 100 or h < 50:
            continue

        # Skip off-screen windows
        cx = rect.left + w // 2
        cy = rect.top + h // 2
        if cx < 0 or cx > SCREEN_W or cy < 0 or cy > SCREEN_H:
            continue

        # Map to grid sector
        col = min(GRID_COLS - 1, max(0, cx // SECTOR_W))
        row = min(GRID_ROWS - 1, max(0, cy // SECTOR_H))
        sector = row * GRID_COLS + col

        # Classify window type from title
        title_lower = title.lower()
        win_type = "application"
        if "chrome" in title_lower or "firefox" in title_lower or "edge" in title_lower:
            win_type = "browser"
        elif "notepad" in title_lower:
            win_type = "text_editor"
        elif title_lower.endswith(".py") or "code" in title_lower or "studio" in title_lower:
            win_type = "code_editor"
        elif "dashboard" in title_lower:
            win_type = "dashboard"
        elif "chat" in title_lower or "discord" in title_lower:
            win_type = "chat"
        elif "media" in title_lower or "player" in title_lower or "movie" in title_lower:
            win_type = "media"
        elif "settings" in title_lower:
            win_type = "settings"

        windows.append({
            "title": title[:80],
            "type": win_type,
            "sector": sector,
            "row": row,
            "col": col,
            "x": rect.left,
            "y": rect.top,
            "w": w,
            "h": h,
        })

    return windows


def get_sector_labels(windows: List[Dict] = None) -> Dict[int, str]:
    """Get a label for each sector based on what windows are there.

    Returns dict mapping sector index → description string.
    """
    if windows is None:
        windows = enumerate_windows()

    # Group by sector
    sector_windows: Dict[int, List[Dict]] = {}
    for win in windows:
        s = win["sector"]
        if s not in sector_windows:
            sector_windows[s] = []
        sector_windows[s].append(win)

    labels = {}
    for sector_idx in range(GRID_COLS * GRID_ROWS):
        wins = sector_windows.get(sector_idx, [])
        if not wins:
            labels[sector_idx] = "empty/desktop"
        elif len(wins) == 1:
            w = wins[0]
            labels[sector_idx] = f"{w['type']}: {w['title']}"
        else:
            # Multiple windows — list the top ones
            names = [f"{w['type']}: {w['title']}" for w in wins[:3]]
            labels[sector_idx] = " | ".join(names)

    return labels


def get_focused_window_content() -> dict:
    """Get the focused window's content via UI Automation.

    Returns text content, control structure, and window info.
    No OCR needed — reads directly from the application's UI tree.

    "The OS GIVES us the text. We don't need screenshots." — Nous
    """
    try:
        import uiautomation as auto

        # FIX 2026-04-03 (Nous): UIAutomation requires COM initialization
        # when called from a thread (WMH worker threads, postal handlers).
        # Without this: "CoInitialize has not been called"
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass

        fg = auto.GetForegroundControl()
        if not fg or not fg.Name:
            return {}

        result = {
            "title": fg.Name[:80],
            "class": fg.ClassName,
            "type": fg.ControlTypeName,
            "text_content": "",
            "controls": [],
        }

        # Try to find text content (edit controls, text areas)
        try:
            edit = fg.EditControl(searchDepth=3)
            if edit.Exists(maxSearchSeconds=0.5):
                value = edit.GetValuePattern()
                if value and value.Value:
                    result["text_content"] = value.Value[:2000]
        except Exception:
            pass

        # Get first-level control structure
        try:
            for child in fg.GetChildren()[:10]:
                try:
                    result["controls"].append({
                        "type": child.ControlTypeName,
                        "name": (child.Name or "")[:40],
                    })
                except Exception:
                    pass
        except Exception:
            pass

        return result

    except Exception:
        return {}


def describe_screen() -> str:
    """Build a natural language description of what's on screen.

    Combines window metadata into a spatial description.
    """
    windows = enumerate_windows()
    if not windows:
        return "I can't detect any windows right now."

    _pos_names = {
        0: "top-left", 1: "top-center-left", 2: "top-center-right", 3: "top-right",
        4: "left", 5: "center-left", 6: "center-right", 7: "right",
        8: "bottom-left", 9: "bottom-center-left", 10: "bottom-center-right", 11: "bottom-right",
    }

    # Deduplicate windows (same title appears multiple times)
    seen_titles = set()
    unique_wins = []
    for w in windows:
        if w["title"] not in seen_titles:
            seen_titles.add(w["title"])
            unique_wins.append(w)

    parts = []
    for win in unique_wins[:8]:  # Top 8 windows
        pos = _pos_names.get(win["sector"], f"region {win['sector']}")
        if win["type"] == "browser":
            # Extract page title from "Page Title - Browser Name"
            page = win["title"].rsplit(" - ", 1)[0] if " - " in win["title"] else win["title"]
            parts.append(f"{page} (browser) in the {pos}")
        elif win["type"] == "text_editor":
            parts.append(f"Notepad in the {pos}")
        elif win["type"] == "dashboard":
            parts.append(f"{win['title']} in the {pos}")
        else:
            parts.append(f"{win['title']} in the {pos}")

    # Try to get focused window text content (no OCR needed)
    _focused_text = ""
    try:
        focused = get_focused_window_content()
        if focused and focused.get("text_content"):
            _title = focused.get("title", "")[:30]
            _text = focused["text_content"][:300]
            _focused_text = f" The focused window ({_title}) contains: {_text}"
    except Exception:
        pass

    desc = "I can see: " + ". ".join(parts) + "."
    if _focused_text:
        desc += _focused_text
    return desc
