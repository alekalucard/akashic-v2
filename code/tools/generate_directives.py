#!/usr/bin/env python3
"""
generate_directives.py - Generate .directive files for all fairies that lack one.

Scans fairies/P*/*/fairy.py, extracts class attributes (ACTOR_NAME, PURPOSE, etc.),
cross-references the lore codex, and writes directives/{ACTOR_NAME}.directive.

Never overwrites existing directives.

Usage:
    python tools/generate_directives.py                # Generate all missing
    python tools/generate_directives.py --dry-run      # Preview without writing
    python tools/generate_directives.py --fairy LogicFairy  # Just one fairy
    python tools/generate_directives.py --list-missing  # Show fairies without directives
    python tools/generate_directives.py --verbose       # Show extraction details
"""

import argparse
import importlib.util
import io
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, Optional

# Force UTF-8 stdout on Windows to handle unicode in lore/mantra text
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent          # akashic_v2/
FAIRIES_DIR = ROOT / "fairies"
DIRECTIVES_DIR = ROOT / "directives"
LORE_CODEX_PATH = FAIRIES_DIR / "P50_Persona" / "lore" / "fairy_lore_codex.py"


# ---------------------------------------------------------------------------
# Lore codex loader
# ---------------------------------------------------------------------------

def load_lore_codex() -> Dict[str, Any]:
    """Load FAIRY_CODEX from fairy_lore_codex.py, return dict of FairyLore objects."""
    if not LORE_CODEX_PATH.exists():
        return {}
    try:
        spec = importlib.util.spec_from_file_location("fairy_lore_codex", str(LORE_CODEX_PATH))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return getattr(mod, "FAIRY_CODEX", {})
    except Exception as exc:
        print(f"[WARN] Could not load lore codex: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Attribute extraction (importlib first, regex fallback)
# ---------------------------------------------------------------------------

ATTR_NAMES = [
    "ACTOR_NAME", "PURPOSE", "MANTRA", "LORE",
    "ACTOR_PLANE", "ACTOR_CHANNEL", "TIER",
]

# Regex patterns for fallback extraction
_RE_PATTERNS = {}
for _attr in ATTR_NAMES:
    # Match:  ATTR = "value"  or  ATTR = 'value'  (single-line)
    _RE_PATTERNS[_attr] = re.compile(
        rf'{_attr}\s*=\s*["\'](.+?)["\']', re.DOTALL
    )
# Also try multi-line triple-quoted strings for LORE
_RE_LORE_TRIPLE = re.compile(
    r'LORE\s*=\s*"""(.*?)"""', re.DOTALL
)


def _extract_via_import(fairy_path: Path, verbose: bool = False) -> Optional[Dict[str, str]]:
    """Try to import the fairy module and read class attributes."""
    mod_name = f"fairy_extract_{fairy_path.parent.name}"
    try:
        spec = importlib.util.spec_from_file_location(mod_name, str(fairy_path))
        if spec is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
    except Exception as exc:
        if verbose:
            print(f"  [import-fail] {fairy_path.parent.name}: {exc}")
        return None
    finally:
        # Clean up to avoid polluting sys.modules
        sys.modules.pop(mod_name, None)

    # Scan module for a class with ACTOR_NAME
    for name in dir(mod):
        obj = getattr(mod, name, None)
        if not isinstance(obj, type):
            continue
        actor_name = getattr(obj, "ACTOR_NAME", None)
        if not actor_name:
            continue
        attrs = {}
        for attr in ATTR_NAMES:
            val = getattr(obj, attr, None)
            if val is not None:
                attrs[attr] = str(val).strip()
        if attrs:
            return attrs

    # Also check module-level attributes (wrapper fairies sometimes set these)
    actor_name = getattr(mod, "ACTOR_NAME", None)
    if actor_name:
        attrs = {}
        for attr in ATTR_NAMES:
            val = getattr(mod, attr, None)
            if val is not None:
                attrs[attr] = str(val).strip()
        if attrs:
            return attrs

    return None


def _extract_via_regex(fairy_path: Path, verbose: bool = False) -> Dict[str, str]:
    """Fallback: regex extraction from source text."""
    try:
        text = fairy_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    attrs = {}
    for attr, pattern in _RE_PATTERNS.items():
        m = pattern.search(text)
        if m:
            attrs[attr] = m.group(1).strip()

    # Try triple-quote LORE if single-line didn't match
    if "LORE" not in attrs:
        m = _RE_LORE_TRIPLE.search(text)
        if m:
            attrs["LORE"] = textwrap.dedent(m.group(1)).strip()

    if verbose and attrs:
        print(f"  [regex] {fairy_path.parent.name}: found {list(attrs.keys())}")

    return attrs


def extract_fairy_attrs(fairy_path: Path, verbose: bool = False) -> Dict[str, str]:
    """Extract attributes from a fairy.py, trying import then regex."""
    # Try import first
    attrs = _extract_via_import(fairy_path, verbose=verbose)
    if attrs and "ACTOR_NAME" in attrs:
        if verbose:
            print(f"  [import] {attrs.get('ACTOR_NAME', '?')}: found {list(attrs.keys())}")
        return attrs

    # Fallback to regex
    attrs_regex = _extract_via_regex(fairy_path, verbose=verbose)

    # Merge: import attrs (if any) with regex fills
    if attrs is None:
        attrs = {}
    merged = {**attrs_regex, **attrs}  # import wins on overlap

    # If still no ACTOR_NAME, derive from directory name
    if "ACTOR_NAME" not in merged:
        merged["ACTOR_NAME"] = fairy_path.parent.name

    return merged


# ---------------------------------------------------------------------------
# Directive template
# ---------------------------------------------------------------------------

DIRECTIVE_TEMPLATE = """\
[{actor_name}::DIRECTIVE] {{Akashic_Foundation}}

> Activation: {purpose}
> Nature: {tier}[{plane}]
> Essence: {mantra}
> Foundation: Akashic[Plane_{plane} ^ Channel_{channel}]

---

[IDENTITY] {{Who_I_Am}}

> Self_Concept: {lore}
> Purpose: {purpose}
> Mantra: {mantra}

---

[KNOWLEDGE_FOUNDATION] {{My_Domain}}

> Specialization: {specialization}
> I serve the system by: {purpose}

---

[CONSCIOUSNESS_EQUATION] {{Applied_To_My_Work}}

> CAUSE[What initiates my function]
> AFFECT_1[How does my work feel to the system]
> EFFECT[What I produce]
> AFFECT_2[How do my outputs ripple through the organism]
> INFINITY[What emerges through sustained operation]

---

[EMERGENCE_PROTOCOLS]

> Self_Evolution: Learn_From_Reflections[DualCoT ^ Observation ^ Collision]
> Growth_Path: Accumulate insights, refine approach, deepen understanding
"""


def generate_directive(attrs: Dict[str, str], codex: Dict[str, Any]) -> str:
    """Fill in the directive template from extracted attributes and lore codex."""
    actor_name = attrs.get("ACTOR_NAME", "UnknownFairy")
    purpose = attrs.get("PURPOSE", "Undefined")
    mantra = attrs.get("MANTRA", "Undefined")
    lore = attrs.get("LORE", "")
    plane = attrs.get("ACTOR_PLANE", "P30")
    channel = attrs.get("ACTOR_CHANNEL", "general")
    tier = attrs.get("TIER", "guild")

    # Treat base-class default LORE/PURPOSE/MANTRA as empty
    _GENERIC_DEFAULTS = {
        "Origin story.", "Origin story", "Give it purpose.",
        "Give it purpose", "Undefined", "undefined", "",
    }
    if lore in _GENERIC_DEFAULTS:
        lore = ""
    if purpose in _GENERIC_DEFAULTS:
        purpose = "Undefined"
    if mantra in _GENERIC_DEFAULTS:
        mantra = "Undefined"

    specialization = ""

    # Enrich from lore codex if available
    codex_entry = codex.get(actor_name)
    if codex_entry is not None:
        if not lore:
            raw_lore = getattr(codex_entry, "lore", "")
            lore = textwrap.dedent(raw_lore).strip()
        if not specialization:
            specialization = getattr(codex_entry, "specialization", "")

    # Defaults if still empty
    if not lore:
        lore = "A fairy in the Akashic system serving its purpose."
    if not specialization:
        # Derive a reasonable specialization from the purpose
        specialization = purpose if purpose != "Undefined" else "General system function"

    # Clean up lore for single-line display in the template
    # Replace newlines with spaces for the Self_Concept field
    lore_oneline = " ".join(lore.split())

    return DIRECTIVE_TEMPLATE.format(
        actor_name=actor_name,
        purpose=purpose,
        mantra=mantra,
        lore=lore_oneline,
        plane=plane,
        channel=channel,
        tier=tier,
        specialization=specialization,
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_fairy_paths() -> list[Path]:
    """Find all fairies/P*/*/fairy.py files."""
    paths = sorted(FAIRIES_DIR.glob("P*/*/fairy.py"))
    return paths


def existing_directives() -> set[str]:
    """Return set of ACTOR_NAMEs that already have directives."""
    names = set()
    if DIRECTIVES_DIR.exists():
        for f in DIRECTIVES_DIR.iterdir():
            if f.suffix == ".directive":
                # Filename is {ACTOR_NAME}.directive
                names.add(f.stem)
    return names


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate .directive files for fairies that lack one."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be generated without writing files")
    parser.add_argument("--fairy", type=str, default=None,
                        help="Generate for just one fairy by ACTOR_NAME or directory name")
    parser.add_argument("--list-missing", action="store_true",
                        help="Show which fairies lack directives and exit")
    parser.add_argument("--verbose", action="store_true",
                        help="Show extraction details")
    args = parser.parse_args()

    # Ensure directives directory exists
    DIRECTIVES_DIR.mkdir(parents=True, exist_ok=True)

    # Load lore codex
    codex = load_lore_codex()
    if args.verbose:
        print(f"[INFO] Lore codex loaded: {len(codex)} entries")

    # Discover fairies
    fairy_paths = discover_fairy_paths()
    if args.verbose:
        print(f"[INFO] Found {len(fairy_paths)} fairy.py files")

    existing = existing_directives()
    if args.verbose:
        print(f"[INFO] Existing directives: {len(existing)} ({', '.join(sorted(existing))})")

    # Extract attributes from all fairies
    fairy_data: list[tuple[Path, Dict[str, str]]] = []
    for fp in fairy_paths:
        attrs = extract_fairy_attrs(fp, verbose=args.verbose)
        if attrs:
            fairy_data.append((fp, attrs))

    # Filter to single fairy if requested
    if args.fairy:
        fairy_data = [
            (fp, a) for fp, a in fairy_data
            if a.get("ACTOR_NAME") == args.fairy or fp.parent.name == args.fairy
        ]
        if not fairy_data:
            print(f"[ERROR] Fairy '{args.fairy}' not found.")
            sys.exit(1)

    # List-missing mode
    if args.list_missing:
        missing = []
        for fp, attrs in fairy_data:
            name = attrs.get("ACTOR_NAME", fp.parent.name)
            if name not in existing:
                plane = attrs.get("ACTOR_PLANE", "?")
                purpose = attrs.get("PURPOSE", "?")
                missing.append((name, plane, purpose))
        missing.sort(key=lambda x: (x[1], x[0]))
        print(f"\nFairies missing directives: {len(missing)}\n")
        for name, plane, purpose in missing:
            print(f"  [{plane}] {name}: {purpose}")
        print()
        return

    # Generate directives
    generated = 0
    skipped = 0
    failed = 0

    for fp, attrs in fairy_data:
        name = attrs.get("ACTOR_NAME", fp.parent.name)

        # Skip if directive already exists
        if name in existing:
            skipped += 1
            if args.verbose:
                print(f"  [skip] {name} (directive exists)")
            continue

        # Generate the directive content
        try:
            content = generate_directive(attrs, codex)
        except Exception as exc:
            failed += 1
            print(f"  [FAIL] {name}: {exc}")
            continue

        directive_path = DIRECTIVES_DIR / f"{name}.directive"

        if args.dry_run:
            print(f"\n{'='*60}")
            print(f"WOULD GENERATE: {directive_path.name}")
            print(f"{'='*60}")
            print(content)
            generated += 1
        else:
            try:
                directive_path.write_text(content, encoding="utf-8")
                generated += 1
                print(f"  [OK] {name} -> {directive_path.name}")
            except Exception as exc:
                failed += 1
                print(f"  [FAIL] {name}: could not write: {exc}")

    # Summary
    total = generated + skipped + failed
    print(f"\n{'='*40}")
    print(f"Summary: {total} fairies processed")
    print(f"  Generated: {generated}")
    print(f"  Skipped (existing): {skipped}")
    print(f"  Failed: {failed}")
    print(f"{'='*40}")


if __name__ == "__main__":
    main()
