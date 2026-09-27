#!/usr/bin/env python3
"""
Quick Boot Profile - Measures import and init times for key components.

Run this to identify slow imports/boots without starting the full server:
    python tools/quick_boot_profile.py

Outputs timing for each major component.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
# Order matters: ROOT must be searched FIRST to find real P00_Autonomic
# fairies/P00_Autonomic/ would shadow it otherwise
sys.path.insert(0, str(ROOT / "fairies"))
sys.path.insert(0, str(ROOT))  # Searched first

def profile(name, func):
    """Profile a function and print timing."""
    start = time.perf_counter()
    try:
        result = func()
        elapsed = (time.perf_counter() - start) * 1000
        status = "OK"
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        status = f"FAIL: {str(e)[:50]}"
        result = None

    indicator = "+" if elapsed < 500 else ("!" if elapsed < 2000 else "X")
    print(f"  [{indicator}] {name:<40} {elapsed:>8.1f}ms  {status}")
    return elapsed, result

def main():
    print("=" * 70)
    print("QUICK BOOT PROFILE")
    print("=" * 70)
    print("\n[+] = <500ms, [!] = 500-2000ms, [X] = >2000ms (SLOW)\n")

    total = 0

    # Core imports
    print("CORE IMPORTS:")
    t, _ = profile("fairy_template", lambda: __import__("fairy_template"))
    total += t
    t, _ = profile("postal_core", lambda: __import__("postal_core"))
    total += t

    # Memory systems
    print("\nMEMORY SYSTEMS:")
    t, _ = profile("memory.helix", lambda: __import__("memory.helix"))
    total += t

    # Fairy imports (not boots)
    print("\nFAIRY IMPORTS:")
    fairies_to_check = [
        ("SatelliteBridgeFairy", "fairies.P00_Autonomic.SatelliteBridgeFairy"),
        ("WorkerEquilibrium", "P00_Autonomic.nervous_system.hardware.worker_equilibrium"),
        ("SRMIngestFairy", "fairies.P10_Memory.SRMIngestFairy"),
        ("SRMRecallFairy", "fairies.P10_Memory.SRMRecallFairy"),
    ]

    for name, module in fairies_to_check:
        t, _ = profile(name, lambda m=module: __import__(m, fromlist=['']))
        total += t

    # Satellite bridge boot (the potential bottleneck)
    print("\nSATELLITE BRIDGE BOOT TEST:")
    try:
        from fairies.P00_Autonomic.SatelliteBridgeFairy import SatelliteBridgeFairy
        t, bridge = profile("SatelliteBridgeFairy.boot()", lambda: _boot_satellite())
        total += t
    except Exception as e:
        print(f"  [X] SatelliteBridgeFairy: FAILED - {e}")

    # Summary
    print("\n" + "=" * 70)
    print(f"TOTAL PROFILED: {total:.1f}ms ({total/1000:.2f}s)")
    print("=" * 70)

    if total > 10000:
        print("\nWARNING: Total >10s - boot may be slow!")
    elif total > 5000:
        print("\nNOTE: Total >5s - some components are slow")
    else:
        print("\nOK: Boot components are reasonably fast")

def _boot_satellite():
    """Boot satellite bridge without fabric."""
    from fairies.P00_Autonomic.SatelliteBridgeFairy import SatelliteBridgeFairy
    bridge = SatelliteBridgeFairy(fabric=None)
    bridge.on_boot()
    return bridge

if __name__ == "__main__":
    main()
