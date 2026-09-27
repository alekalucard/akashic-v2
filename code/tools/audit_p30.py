"""Quick audit of P30 Cognition fairies — what subscribes/publishes what."""
import os, re
from pathlib import Path

P30 = Path(r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition")

for d in sorted(P30.iterdir()):
    if not d.is_dir() or d.name.startswith("__"):
        continue

    fairy_py = d / "fairy.py"
    if not fairy_py.exists():
        # Check subdirs
        candidates = list(d.glob("**/fairy.py"))
        if candidates:
            fairy_py = candidates[0]
        else:
            print(f"\n{'='*60}")
            print(f"{d.name}: NO fairy.py (support dir)")
            continue

    try:
        code = fairy_py.read_text(encoding="utf-8", errors="replace")
    except:
        print(f"\n{d.name}: UNREADABLE")
        continue

    print(f"\n{'='*60}")
    print(f"{d.name}")
    print(f"  File: {fairy_py}")
    print(f"  Lines: {len(code.splitlines())}")

    # Find subscriptions
    subs = re.findall(r'subscribe\(["\']([^"\']+)', code)
    pubs = re.findall(r'publish\(["\']([^"\']+)', code)
    routes = re.findall(r'route\(["\']([^"\']+)', code)

    if subs:
        print(f"  SUBSCRIBES: {', '.join(sorted(set(subs)))}")
    if pubs:
        print(f"  PUBLISHES:  {', '.join(sorted(set(pubs)))}")
    if routes:
        print(f"  ROUTES:     {', '.join(sorted(set(routes)))}")

    # Find class name
    classes = re.findall(r'class (\w+Fairy)\w*[\(:]', code)
    if classes:
        print(f"  CLASS: {classes[0]}")

    # Find key methods (on_boot, on_tick, etc)
    methods = re.findall(r'def (on_\w+|_on_\w+|_handle_\w+)\(', code)
    if methods:
        # Dedupe
        unique = list(dict.fromkeys(methods))
        print(f"  HANDLERS: {', '.join(unique[:15])}")
