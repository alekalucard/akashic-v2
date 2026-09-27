"""
Fix module path inconsistencies.

Redirects imports from old/wrong locations to correct fairy structure paths.
"""

import re
from pathlib import Path
from typing import List, Tuple

# Path redirections: (wrong_pattern, correct_replacement)
PATH_FIXES = [
    # Association Cortex - old integration path -> new fairy path
    (
        r'from fairies\.P30_Cognition\.integration\.association_cortex_fairy import',
        'from fairies.P30_Cognition.AssociationCortexFairy.fairy import'
    ),
    # SRM Recall - wrong path -> correct fairy path
    (
        r'from fairies\.P10_Memory\.triple_helix_srm_memory\.srm_recall_fairy import',
        'from fairies.P10_Memory.SRMRecallFairy.fairy import'
    ),
    # Forensic Scribe - wrong path -> correct fairy path
    (
        r'from fairies\.P10_Memory\.forensic\.forensic_scribe_fairy import',
        'from fairies.P10_Memory.ForensicScribeFairy.fairy import'
    ),
    # SRM tools - P00 path -> actual P40 path
    (
        r'from fairies\.P00_Autonomic\.mcp\.srm_tools import',
        'from fairies.P40_Sensory.mcp.srm_tools import'
    ),
    # Agent framework - P00 path -> actual P40 path
    (
        r'from fairies\.P00_Autonomic\.mcp\.agent_framework import',
        'from fairies.P40_Sensory.mcp.agent_framework import'
    ),
]

def fix_paths_in_file(filepath: Path, dry_run: bool = True) -> Tuple[int, List[str]]:
    """Fix module paths in a single file."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return 0, [f"ERROR reading: {e}"]

    original = content
    changes = []

    for pattern, replacement in PATH_FIXES:
        matches = re.findall(pattern, content)
        if matches:
            for _ in matches:
                changes.append(f"  {pattern[:50]}... -> {replacement[:50]}...")
            content = re.sub(pattern, replacement, content)

    if content != original:
        if not dry_run:
            filepath.write_text(content, encoding="utf-8")
        return len(changes), changes

    return 0, []

def scan_and_fix(root_dir: Path, dry_run: bool = True) -> dict:
    """Scan and fix module paths."""
    total_files = 0
    fixed_files = 0
    total_fixes = 0
    all_changes = {}

    fairies_dir = root_dir / "fairies"

    for py_file in fairies_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        total_files += 1
        count, changes = fix_paths_in_file(py_file, dry_run=dry_run)

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
    parser = argparse.ArgumentParser(description="Fix module path inconsistencies")
    parser.add_argument("--apply", action="store_true", help="Apply fixes")
    parser.add_argument("--root", default="F:/Sandbox/failure_factory/akashic_v2", help="Root directory")
    args = parser.parse_args()

    root = Path(args.root)
    dry_run = not args.apply

    print(f"{'DRY RUN - ' if dry_run else ''}Fixing module paths...")
    print()

    result = scan_and_fix(root, dry_run=dry_run)

    print(f"Files scanned: {result['total_files_scanned']}")
    print(f"Files to fix:  {result['files_with_fixes']}")
    print(f"Total fixes:   {result['total_fixes']}")
    print()

    if result['changes']:
        print("Changes:")
        for filepath, changes in result['changes'].items():
            print(f"\n{filepath}:")
            for change in changes:
                print(change)

    if dry_run:
        print("\nThis was a DRY RUN. To apply changes, run with --apply")

    return 0

if __name__ == "__main__":
    exit(main())
