"""
Bulk fix for bare plane imports.

Changes:
    from P00_Autonomic.  ->  from fairies.P00_Autonomic.
    from P10_Memory.     ->  from fairies.P10_Memory.
    etc.

This fixes ~300+ broken imports across the codebase.
"""

import re
import os
from pathlib import Path
from typing import List, Tuple

# Patterns to fix
PLANE_PATTERNS = [
    "P00_Autonomic",
    "P10_Memory",
    "P20_Somatic",
    "P30_Cognition",
    "P40_Sensory",
    "P50_Persona",
    "P60_Executive",
]

def should_skip_file(filepath: Path) -> bool:
    """Check if file should be skipped."""
    # Skip __pycache__, .git, research_repos
    skip_dirs = ["__pycache__", ".git", "research_repos", "node_modules", ".venv", "venv"]
    for part in filepath.parts:
        if part in skip_dirs:
            return True
    return False

def fix_imports_in_file(filepath: Path, dry_run: bool = True) -> Tuple[int, List[str]]:
    """
    Fix bare plane imports in a single file.

    Returns: (count_of_fixes, list_of_changes)
    """
    if should_skip_file(filepath):
        return 0, []

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return 0, [f"ERROR reading {filepath}: {e}"]

    original = content
    changes = []

    for plane in PLANE_PATTERNS:
        # Pattern: from P00_Autonomic. (but not already fairies.P00_Autonomic)
        # This handles both "from P00_Autonomic." and "from  P00_Autonomic." (with extra space)
        pattern = rf'(from\s+)({plane}\.)'

        def replacer(match):
            # Only replace if not already prefixed with "fairies."
            # Check the characters before the match
            start = match.start()
            prefix = content[max(0, start-8):start]
            if "fairies." in prefix:
                return match.group(0)  # Already prefixed

            changes.append(f"  Line {content[:start].count(chr(10))+1}: from {plane}. -> from fairies.{plane}.")
            return f"{match.group(1)}fairies.{match.group(2)}"

        content = re.sub(pattern, replacer, content)

    if content != original:
        if not dry_run:
            filepath.write_text(content, encoding="utf-8")
        return len(changes), changes

    return 0, []

def scan_and_fix(root_dir: Path, dry_run: bool = True) -> dict:
    """
    Scan all Python files and fix bare imports.

    Args:
        root_dir: Root directory to scan
        dry_run: If True, don't actually modify files

    Returns:
        Summary dict with counts and details
    """
    total_files = 0
    fixed_files = 0
    total_fixes = 0
    all_changes = {}

    # Only scan fairies/ directory
    fairies_dir = root_dir / "fairies"
    if not fairies_dir.exists():
        return {"error": "fairies/ directory not found"}

    for py_file in fairies_dir.rglob("*.py"):
        if should_skip_file(py_file):
            continue

        total_files += 1
        count, changes = fix_imports_in_file(py_file, dry_run=dry_run)

        if count > 0:
            fixed_files += 1
            total_fixes += count
            rel_path = str(py_file.relative_to(root_dir))
            all_changes[rel_path] = changes

    return {
        "dry_run": dry_run,
        "total_files_scanned": total_files,
        "files_with_fixes": fixed_files,
        "total_fixes": total_fixes,
        "changes": all_changes,
    }

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fix bare plane imports in fairies/")
    parser.add_argument("--apply", action="store_true", help="Actually apply fixes (default is dry run)")
    parser.add_argument("--root", default="F:/Sandbox/failure_factory/akashic_v2", help="Root directory")
    args = parser.parse_args()

    root = Path(args.root)
    dry_run = not args.apply

    print(f"{'DRY RUN - ' if dry_run else ''}Scanning {root / 'fairies'}...")
    print()

    result = scan_and_fix(root, dry_run=dry_run)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        return 1

    print(f"Files scanned: {result['total_files_scanned']}")
    print(f"Files to fix:  {result['files_with_fixes']}")
    print(f"Total fixes:   {result['total_fixes']}")
    print()

    if result['changes']:
        print("Changes:")
        for filepath, changes in result['changes'].items():
            print(f"\n{filepath}:")
            for change in changes[:5]:  # Show first 5 changes per file
                print(change)
            if len(changes) > 5:
                print(f"  ... and {len(changes) - 5} more")

    if dry_run:
        print()
        print("This was a DRY RUN. To apply changes, run with --apply")
    else:
        print()
        print("Fixes applied!")

    return 0

if __name__ == "__main__":
    exit(main())
