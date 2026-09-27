# ══════════════════════════════════════════════════════════════════════════════
# SAFE PRINT - Windows-compatible console output
# ══════════════════════════════════════════════════════════════════════════════
#
# Windows cp1252 encoding cannot handle Unicode emojis.
# This module provides a safe print function that replaces emojis with ASCII.
#
# Usage:
#   from fairies.P00_Autonomic.utils.safe_print import safe_print
#   safe_print(f"[Fairy] [OK] Something worked")  # Won't crash on Windows
#
# ══════════════════════════════════════════════════════════════════════════════

import sys

# Emoji to ASCII replacement map
EMOJI_MAP = {
    "✅": "[OK]",
    "⚠": "[WARN]",
    "❌": "[ERR]",
    "": "[BRAIN]",
    "": "[STAR]",
    "": "[TARGET]",
    "": "[HEART]",
    "": "[PLUG]",
    "": "[MOON]",
    "": "[SAVE]",
    "": "[SUNRISE]",
    "": "[NEW]",
    "": "[GEM]",
    "": "[BOT]",
    "": "[8BALL]",
    "": "[HEART]",
    "": "[EYE]",
    "": "[THOUGHT]",
    "": "[CYCLE]",
    "▶": "[PLAY]",
    "⏹": "[STOP]",
    "": "[SLEEP]",
    "": "[LAB]",
    "": "[TROPHY]",
    "": "[CHART]",
    "": "[NOTE]",
    "": "[SEARCH]",
    "⚡": "[BOLT]",
    "": "[LOCK]",
    "": "[UNLOCK]",
    "": "[FOLDER]",
    "": "[FOLDER]",
    "": "[FILES]",
    "": "[IDEA]",
    "": "[WEB]",
    "": "[LINK]",
    "⏰": "[CLOCK]",
    "": "[SIGNAL]",
    "": "[TOOL]",
    "⚙": "[GEAR]",
    "": "[MUSIC]",
    "": "[GAME]",
    "": "[BOOK]",
    "✨": "[SPARK]",
    "": "[GLOW]",
    "→": "->",
    "←": "<-",
    "↔": "<->",
    "⇒": "=>",
    "⇐": "<=",
    "└": "|_",
    "├": "|-",
    "│": "|",
    "─": "-",
    "═": "=",
    "╔": "+",
    "╗": "+",
    "╚": "+",
    "╝": "+",
    "║": "|",
}


def _is_windows_console():
    """Check if we're running in a Windows console that can't handle UTF-8."""
    if sys.platform != "win32":
        return False
    try:
        # Check if stdout encoding can handle Unicode
        if hasattr(sys.stdout, 'encoding'):
            enc = sys.stdout.encoding or ""
            if enc.lower() in ("utf-8", "utf8"):
                return False
        return True
    except Exception:
        return True


def safe_print(*args, **kwargs):
    """
    Print with emoji-to-ASCII conversion for Windows compatibility.
    
    Falls back to standard print on Linux/Mac or UTF-8 terminals.
    """
    if not _is_windows_console():
        # Safe to print normally
        print(*args, **kwargs)
        return
    
    # Convert args to strings and replace emojis
    safe_args = []
    for arg in args:
        s = str(arg)
        for emoji, replacement in EMOJI_MAP.items():
            s = s.replace(emoji, replacement)
        # Handle any remaining non-ASCII by escaping
        try:
            s.encode(sys.stdout.encoding or 'cp1252')
        except UnicodeEncodeError:
            # Replace problematic characters
            s = s.encode(sys.stdout.encoding or 'cp1252', errors='replace').decode(sys.stdout.encoding or 'cp1252')
        safe_args.append(s)
    
    print(*safe_args, **kwargs)


def configure_utf8_output():
    """
    Try to configure stdout/stderr for UTF-8 output.
    
    Call this early in boot to potentially enable full Unicode support.
    Returns True if successful.
    """
    if sys.platform != "win32":
        return True
    
    try:
        import io
        # Reconfigure stdout for UTF-8
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, 
            encoding='utf-8', 
            errors='replace',
            line_buffering=True
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True
        )
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE ALIASES
# ══════════════════════════════════════════════════════════════════════════════

# For direct import
sprint = safe_print
slog = safe_print


if __name__ == "__main__":
    # Test
    print("Testing safe_print:")
    safe_print("[Test] [OK] This should work!")
    safe_print("[Test] [WARN] Warning test")
    safe_print("[Test] [BRAIN] Brain emoji")
    safe_print("[Test] Mode: ACTIVE → SLEEP")
    print("Done!")
