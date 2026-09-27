"""
Memory Card Counter - Track SRM memory card statistics

Provides quick stats on the memory cards in SRM_Intake.
Can be run standalone or integrated into the GUI.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from collections import defaultdict


def count_memory_cards(srm_intake_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Count all memory cards in the SRM_Intake directory.

    Args:
        srm_intake_dir: Path to SRM_Intake, defaults to project root

    Returns:
        Dictionary with card counts and statistics
    """
    if srm_intake_dir is None:
        # Default to project root SRM_Intake
        srm_intake_dir = Path(__file__).parent.parent.parent / "SRM_Intake"
    else:
        srm_intake_dir = Path(srm_intake_dir)

    if not srm_intake_dir.exists():
        return {"error": f"SRM_Intake not found at {srm_intake_dir}"}

    stats = {
        "total_cards": 0,
        "total_size_bytes": 0,
        "by_date": {},
        "by_domain": defaultdict(int),
        "by_kind": defaultdict(int),
        "oldest_card": None,
        "newest_card": None,
        "scan_time": datetime.now().isoformat(),
    }

    oldest_time = None
    newest_time = None

    # Scan all JSON files
    for date_dir in srm_intake_dir.iterdir():
        if not date_dir.is_dir():
            continue

        date_str = date_dir.name
        date_count = 0
        date_size = 0

        for card_file in date_dir.glob("*.json"):
            try:
                file_stat = card_file.stat()
                file_size = file_stat.st_size
                file_mtime = file_stat.st_mtime

                stats["total_cards"] += 1
                stats["total_size_bytes"] += file_size
                date_count += 1
                date_size += file_size

                # Track oldest/newest
                if oldest_time is None or file_mtime < oldest_time:
                    oldest_time = file_mtime
                    stats["oldest_card"] = str(card_file.name)
                if newest_time is None or file_mtime > newest_time:
                    newest_time = file_mtime
                    stats["newest_card"] = str(card_file.name)

                # Try to read card metadata (sample first 100 per date for speed)
                if date_count <= 100:
                    try:
                        with open(card_file, 'r', encoding='utf-8') as f:
                            card = json.load(f)

                        # Count by domain
                        domain = card.get("domain", "unknown")
                        stats["by_domain"][domain] += 1

                        # Count by kind
                        kind = card.get("kind", "unknown")
                        stats["by_kind"][kind] += 1

                    except Exception:
                        stats["by_domain"]["parse_error"] += 1
                else:
                    # For cards beyond sample, estimate based on directory
                    stats["by_domain"]["sampled"] += 1

            except Exception:
                pass

        if date_count > 0:
            stats["by_date"][date_str] = {
                "cards": date_count,
                "size_bytes": date_size,
            }

    # Convert defaultdicts to regular dicts for JSON serialization
    stats["by_domain"] = dict(stats["by_domain"])
    stats["by_kind"] = dict(stats["by_kind"])

    # Calculate human-readable size
    size_mb = stats["total_size_bytes"] / (1024 * 1024)
    stats["total_size_mb"] = round(size_mb, 2)

    return stats


def print_memory_stats(stats: Dict[str, Any]):
    """Print memory stats in a nice format."""
    if "error" in stats:
        print(f"Error: {stats['error']}")
        return

    print("\n" + "=" * 60)
    print("   MEMORY CARD STATISTICS")
    print("=" * 60)

    print(f"\n  Total Cards:  {stats['total_cards']:,}")
    print(f"  Total Size:   {stats['total_size_mb']:.2f} MB")

    if stats["by_date"]:
        print(f"\n   By Date:")
        for date, info in sorted(stats["by_date"].items(), reverse=True):
            print(f"     {date}: {info['cards']:,} cards ({info['size_bytes'] / 1024 / 1024:.2f} MB)")

    if stats["by_domain"]:
        print(f"\n    By Domain:")
        for domain, count in sorted(stats["by_domain"].items(), key=lambda x: -x[1])[:10]:
            print(f"     {domain}: {count:,}")

    if stats["by_kind"]:
        print(f"\n   By Kind:")
        for kind, count in sorted(stats["by_kind"].items(), key=lambda x: -x[1])[:10]:
            print(f"     {kind}: {count:,}")

    print(f"\n  Oldest: {stats['oldest_card']}")
    print(f"  Newest: {stats['newest_card']}")
    print(f"\n  Scanned: {stats['scan_time']}")
    print("=" * 60 + "\n")


def get_card_count_simple(srm_intake_dir: Optional[str] = None) -> int:
    """Get just the total card count (fast)."""
    if srm_intake_dir is None:
        srm_intake_dir = Path(__file__).parent.parent.parent / "SRM_Intake"
    else:
        srm_intake_dir = Path(srm_intake_dir)

    if not srm_intake_dir.exists():
        return 0

    count = 0
    for date_dir in srm_intake_dir.iterdir():
        if date_dir.is_dir():
            count += len(list(date_dir.glob("*.json")))

    return count


# ============================================================================
# Standalone execution
# ============================================================================

if __name__ == "__main__":
    import sys

    # Allow custom path as argument
    path = sys.argv[1] if len(sys.argv) > 1 else None

    print("\nScanning memory cards...")
    stats = count_memory_cards(path)
    print_memory_stats(stats)
