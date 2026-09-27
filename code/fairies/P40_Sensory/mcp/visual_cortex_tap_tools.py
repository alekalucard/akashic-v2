# ══════════════════════════════════════════════════════════════════════════════
# VISUAL CORTEX TAP TOOLS - Let Claude Code see what the Visual Cortex sees
# ══════════════════════════════════════════════════════════════════════════════
#
# These tools bridge between:
#   - The Akashic Visual Cortex (dxcam + Florence-2 running in server.py)
#   - Claude Code / Nous (this MCP client)
#
# Two modes:
#   1. TEXT-ONLY (token-light ~500 tokens): Scene type, OCR text, Florence-2
#      caption, colors, brightness, complexity. Good for monitoring.
#   2. WITH THUMBNAIL (token-heavier ~2-5K tokens): Includes base64 JPEG
#      thumbnail so Claude's native vision can compare against the system's
#      interpretation. Good for fine-tuning the visual cortex.
#
# Data sources (all on-disk, no live connection required):
#   - SRM_Intake/YYYY-MM-DD/visual_*.json  (SRM memory cards)
#   - state/cortex_stats.json              (association cortex graph stats)
#   - state/screen_check.jpg               (last screenshot from cortex)
#
# ══════════════════════════════════════════════════════════════════════════════

import json
import time
import base64
from pathlib import Path
from typing import Optional
from datetime import datetime


# Resolve project root: mcp/ -> P40_Sensory/ -> fairies/ -> akashic_v2/
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def _find_latest_visual_card() -> Optional[dict]:
    """Find the most recent visual SRM card on disk."""
    srm_dir = _PROJECT_ROOT / "SRM_Intake"
    if not srm_dir.exists():
        return None

    # Walk date directories in reverse order (most recent first)
    # Filter to YYYY-MM-DD dirs only (skip .md files, backups/, seeds/, etc.)
    date_dirs = sorted(
        [d for d in srm_dir.iterdir() if d.is_dir() and len(d.name) == 10 and d.name[4] == "-"],
        reverse=True,
    )
    for date_dir in date_dirs[:7]:  # Check last 7 days max
        # Find visual cards in this date dir
        cards = sorted(date_dir.glob("visual_*.json"), reverse=True,
                       key=lambda p: p.stat().st_mtime)
        if cards:
            try:
                return json.loads(cards[0].read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def _find_recent_visual_cards(n: int = 5) -> list:
    """Find the N most recent visual SRM cards."""
    srm_dir = _PROJECT_ROOT / "SRM_Intake"
    if not srm_dir.exists():
        return []

    all_cards = []
    date_dirs = sorted(
        [d for d in srm_dir.iterdir() if d.is_dir() and len(d.name) == 10 and d.name[4] == "-"],
        reverse=True,
    )
    for date_dir in date_dirs[:7]:
        for card_path in date_dir.glob("visual_*.json"):
            all_cards.append(card_path)
            if len(all_cards) >= n * 3:  # Collect extras for sorting
                break
        if len(all_cards) >= n * 3:
            break

    # Sort by modification time, most recent first
    all_cards.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    results = []
    for card_path in all_cards[:int(n)]:  # FIX 2026-06-10: coerce MCP str-arg
        try:
            results.append(json.loads(card_path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return results


def _read_cortex_stats() -> Optional[dict]:
    """Read the association cortex graph statistics."""
    stats_path = _PROJECT_ROOT / "state" / "cortex_stats.json"
    if stats_path.exists():
        try:
            return json.loads(stats_path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _read_screen_check_thumbnail(max_dimension: int = 640, quality: int = 60) -> Optional[str]:
    """Read state/screen_check.jpg and return as base64 JPEG thumbnail."""
    screen_path = _PROJECT_ROOT / "state" / "screen_check.jpg"
    if not screen_path.exists():
        return None

    try:
        # Try to resize with PIL for token efficiency
        try:
            from PIL import Image
            import io
            img = Image.open(screen_path)
            # Resize to max_dimension maintaining aspect ratio
            w, h = img.size
            if max(w, h) > max_dimension:
                scale = max_dimension / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            return base64.b64encode(buf.getvalue()).decode("ascii")
        except ImportError:
            # No PIL — send raw file (larger but works)
            raw = screen_path.read_bytes()
            return base64.b64encode(raw).decode("ascii")
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

def register_visual_cortex_tap_tools(mcp):
    """Register visual cortex tap tools with MCP."""

    # ──────────────────────────────────────────────────────────────────────
    # TOOL 1: What does the visual cortex see? (text-only, token-light)
    # ──────────────────────────────────────────────────────────────────────

    @mcp.tool()
    def visual_cortex_report() -> str:
        """
        Get the Visual Cortex's latest interpretation of the screen (TEXT ONLY).

        Returns the system's own perception — what IT thinks it sees:
        - Scene type (code_editor, browser, desktop, etc.)
        - OCR text extracted from screen
        - Colors, brightness, complexity
        - Florence-2 caption (if IT Cortex is running)
        - Association cortex graph stats

        This is TOKEN-LIGHT (~500 tokens). Use visual_cortex_compare()
        if you want the actual thumbnail for Claude vision comparison.

        Returns:
            JSON with the system's visual perception summary
        """
        result = {
            "timestamp": time.time(),
            "source": "visual_cortex_tap",
        }

        # 1. Latest SRM visual card
        card = _find_latest_visual_card()
        if card:
            content = card.get("content", "")
            tags = card.get("tags", [])
            helix = card.get("helix", {})
            helix_l = helix.get("L", {})
            helix_c = helix.get("C", {})
            helix_w = helix_l.get("w", {})

            result["perception"] = {
                "description": content,
                "scene_type": helix_w.get("what", "unknown"),
                "affect": helix_c.get("affect", "unknown"),
                "energy": helix_c.get("energy", 0),
                "coherence": helix_c.get("coherence", 0),
                "tags": tags,
            }

            # Card age
            card_ts = card.get("timestamp", 0)
            if card_ts:
                age_seconds = time.time() - card_ts
                result["perception"]["age_seconds"] = round(age_seconds, 1)
                if age_seconds > 300:
                    result["perception"]["stale"] = True
                    result["perception"]["note"] = (
                        f"Card is {age_seconds/60:.0f}min old. "
                        "Visual cortex may not be capturing."
                    )
        else:
            result["perception"] = {
                "error": "No visual SRM cards found. Visual cortex may not be running.",
            }

        # 2. Cortex graph stats
        stats = _read_cortex_stats()
        if stats:
            result["cortex_graph"] = {
                "nodes": stats.get("nodes", 0),
                "edges": stats.get("edges", 0),
                "portal_mode": stats.get("portal_mode", False),
                "growth_from_memory": stats.get("growth_from_memory", 0),
            }

        # 3. Screen check file age
        screen_path = _PROJECT_ROOT / "state" / "screen_check.jpg"
        if screen_path.exists():
            age = time.time() - screen_path.stat().st_mtime
            result["screen_check"] = {
                "exists": True,
                "age_seconds": round(age, 1),
                "size_kb": round(screen_path.stat().st_size / 1024, 1),
            }
        else:
            result["screen_check"] = {"exists": False}

        return json.dumps(result, indent=2)

    # ──────────────────────────────────────────────────────────────────────
    # TOOL 2: Compare — get thumbnail + system interpretation for Claude
    #         vision to analyze side-by-side
    # ──────────────────────────────────────────────────────────────────────

    @mcp.tool()
    def visual_cortex_compare(max_dimension: int = 480, quality: int = 40) -> str:
        """
        Get what the Visual Cortex sees WITH a thumbnail for Claude vision comparison.

        Returns BOTH:
        1. The system's interpretation (scene type, OCR, colors, affect)
        2. A base64 JPEG thumbnail of what it was looking at

        Use this to COMPARE what the system thinks vs what Claude's native
        vision sees. This enables fine-tuning the visual cortex by identifying
        where interpretations diverge.

        TOKEN COST: ~3000-6000 tokens depending on image size.

        Args:
            max_dimension: Max width/height for thumbnail (default 480)
            quality: JPEG quality 1-100 (default 40)

        Returns:
            JSON with system interpretation + base64 thumbnail
        """
        result = {
            "timestamp": time.time(),
            "source": "visual_cortex_compare",
            "purpose": "Compare system perception vs Claude vision",
        }

        # 1. System's interpretation
        card = _find_latest_visual_card()
        if card:
            content = card.get("content", "")
            helix = card.get("helix", {})
            helix_l = helix.get("L", {})
            helix_c = helix.get("C", {})
            helix_w = helix_l.get("w", {})

            result["system_sees"] = {
                "description": content,
                "scene_type": helix_w.get("what", "unknown"),
                "affect": helix_c.get("affect", "unknown"),
                "energy": helix_c.get("energy", 0),
                "tags": card.get("tags", []),
            }

            card_ts = card.get("timestamp", 0)
            if card_ts:
                result["system_sees"]["age_seconds"] = round(
                    time.time() - card_ts, 1
                )
        else:
            result["system_sees"] = {
                "error": "No visual cards found — cortex may not be running",
            }

        # 2. Thumbnail from screen_check.jpg
        thumb_b64 = _read_screen_check_thumbnail(max_dimension, quality)
        if thumb_b64:
            result["thumbnail"] = {
                "format": "image/jpeg",
                "base64": thumb_b64,
                "max_dimension": max_dimension,
                "quality": quality,
                "note": (
                    "Use Claude's native vision to analyze this image, "
                    "then compare against 'system_sees' above. "
                    "Divergences reveal where the visual cortex needs tuning."
                ),
            }
        else:
            result["thumbnail"] = {
                "error": "No screen_check.jpg found in state/",
            }

        return json.dumps(result, indent=2)

    # ──────────────────────────────────────────────────────────────────────
    # TOOL 3: Visual perception history — recent card timeline
    # ──────────────────────────────────────────────────────────────────────

    @mcp.tool()
    def visual_cortex_history(n: int = 5) -> str:
        """
        Get recent visual cortex perception history.

        Returns the last N visual SRM cards showing what the system
        has been seeing over time. Useful for understanding perception
        patterns and checking if the visual cortex is actively capturing.

        Args:
            n: Number of recent perceptions to return (default 5, max 20)

        Returns:
            JSON with recent visual perception entries
        """
        n = min(max(1, n), 20)
        cards = _find_recent_visual_cards(n)

        if not cards:
            return json.dumps({
                "error": "No visual SRM cards found",
                "hint": "Visual cortex may not be running or writing cards",
            }, indent=2)

        entries = []
        for card in cards:
            helix = card.get("helix", {})
            helix_w = helix.get("L", {}).get("w", {})
            helix_c = helix.get("C", {})

            entry = {
                "id": card.get("id", "?"),
                "timestamp": card.get("timestamp", 0),
                "age_seconds": round(time.time() - card.get("timestamp", 0), 1),
                "description": card.get("content", ""),
                "scene_type": helix_w.get("what", "unknown"),
                "affect": helix_c.get("affect", "unknown"),
                "tags": card.get("tags", []),
            }
            entries.append(entry)

        return json.dumps({
            "count": len(entries),
            "entries": entries,
        }, indent=2)
