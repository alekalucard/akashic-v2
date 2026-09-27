#!/usr/bin/env python3
"""
Reset progress files for fresh ingestion.
Since the coordinator wasn't loading cards before, we need to start fresh.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "state"

def reset_progress():
    progress_files = [
        "tardis_images_progress.json",
        "tardis_simple_progress.json",
        "tardis_full_progress.json",
    ]

    for fname in progress_files:
        path = STATE / fname
        if path.exists():
            # Read to get stats before clearing
            try:
                with open(path) as f:
                    data = json.load(f)
                print(f"Resetting {fname}:")
                print(f"  Had {data.get('processed_files', 0)} processed files")
                print(f"  Had {len(data.get('seen_hashes', []))} hashes")
                print(f"  Had {len(data.get('completed_sources', []))} completed sources")
            except:
                print(f"Resetting {fname}: (couldn't read)")

            # Remove the file
            path.unlink()
            print(f"  [REMOVED]")
        else:
            print(f"Skipping {fname}: not found")

    print()
    print("Progress files reset. Ready for fresh ingestion.")

if __name__ == "__main__":
    reset_progress()
