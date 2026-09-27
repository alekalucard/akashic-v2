"""Delete dream seed files polluted by stale OCR garbage.

Background: back in April, OCR fragments from a Spotify/desktop frame
("Hiya Sourpatches!", "Skeleton Sa m") got captured into the
visual_foveal stream and bound into ConsciousnessLoop collision tracers.
Those collisions persisted into dream seed JSON files. Each boot,
DreamSeedFairy._restore_mind_pools replays those tracers, so the
polluted strings re-enter curiosity drive on every restart.

Forensic profile (~60 seeds out of ~2,100 total):
- ~37 contain "Hiya Sourpatches"
- ~23 contain "Skeleton Sa" (OCR-broken)
- Significant overlap (most "Skeleton Sa" seeds also have "Hiya")

This script finds all seed files containing either marker and deletes
them. Dream seeds are time-stamped continuity captures; losing 60 of
2,100 (2.85%) is fine — better than replaying poison every boot.

Strict filter (mirrors the wm:*-BOOKS cleanup discipline):
  Must contain "Hiya Sourpatches" or "Skeleton Sa".
  These are OCR-garbage strings; both very unlikely to appear in
  legitimate seed content.

SAFETY: Server-running-during-cleanup is fine. Server only reads
dream seeds at boot/wake; on-disk deletion takes effect on next
restart. No mmap concerns (these are plain JSON files).

Run:
    python tools/cleanup_polluted_dream_seeds.py            # dry run
    python tools/cleanup_polluted_dream_seeds.py --apply    # delete
"""
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEDS_DIR = ROOT / "state" / "dream_seeds"

# Strict markers — both are OCR-garbage strings unlikely to appear
# in legitimate content.
POLLUTION_MARKERS = (
    "Hiya Sourpatches",
    "Skeleton Sa",  # broken-word OCR artifact "Skeleton Sa m"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Actually delete files (default is dry run)")
    args = parser.parse_args()

    if not SEEDS_DIR.exists():
        print(f"NO DREAM_SEEDS DIR AT {SEEDS_DIR}")
        return 1

    all_seeds = sorted(SEEDS_DIR.glob("seed_*.json"))
    total = len(all_seeds)
    print(f"dream_seeds: {SEEDS_DIR}  ({total} total seed files)")
    print(f"markers: {POLLUTION_MARKERS}")
    print()

    polluted = []
    for path in all_seeds:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  !! read failed {path.name}: {e}")
            continue
        matched = [m for m in POLLUTION_MARKERS if m in text]
        if matched:
            polluted.append((path, matched))

    print(f"Polluted seeds found: {len(polluted)}/{total} ({len(polluted)/total*100:.1f}%)")
    print()
    print("Sample of first 10:")
    for path, markers in polluted[:10]:
        print(f"  {path.name}  -> markers: {markers}")
    if len(polluted) > 10:
        print(f"  ... and {len(polluted) - 10} more")
    print()

    if not polluted:
        print("Nothing to clean. Exiting.")
        return 0

    if not args.apply:
        print("DRY RUN — no files deleted.")
        print(f"Re-run with --apply to delete the {len(polluted)} polluted seeds.")
        return 0

    print(f"Deleting {len(polluted)} polluted seed files...")
    deleted = 0
    failed = 0
    for path, _markers in polluted:
        try:
            path.unlink()
            deleted += 1
            if deleted % 20 == 0:
                print(f"  ...{deleted} deleted")
        except Exception as e:
            print(f"  !! delete failed {path.name}: {e}")
            failed += 1
    print(f"DONE. Deleted {deleted}, failed {failed}.")
    print()
    remaining = sorted(SEEDS_DIR.glob("seed_*.json"))
    print(f"Remaining seeds: {len(remaining)} (was {total})")
    print()
    print("NOTE: server in-memory dream-seed state (if any) won't")
    print("reflect deletions until next reboot. Restart to fully sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
