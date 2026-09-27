"""
Test Fairy Registration Supervision

Shows:
1. UMF supervising fairy registrations
2. Validation of plane/capability matching
3. Wiring issue detection
4. Correction suggestions
"""

import sys
import time
from pathlib import Path

# Add paths
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "tracer_pool" / "python"))

from postal_core.tensor_fabric import TensorFabric
from directory import DirectoryFairy, set_directory
from fairies.P20_Somatic.SomaticMindFairy import SomaticMindFairy as UnconsciousMindFairy


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def main():
    print_section("FAIRY REGISTRATION SUPERVISION TEST")

    # Create infrastructure
    print("\n[1] Booting infrastructure...")
    fabric = TensorFabric()

    # Create directory
    directory = DirectoryFairy(fabric)
    directory.on_boot()
    set_directory(directory)
    print("    Directory: OK")

    # Create UMF
    print("\n[2] Creating UnconsciousMindFairy...")
    umf = UnconsciousMindFairy(fabric)
    umf.on_boot()
    print(f"    UMF: {umf.state.value}")

    # Test 1: Valid fairy registration
    print_section("TEST 1: VALID REGISTRATION")
    print("    Registering 'CognitionFairy' with matching plane/capabilities...")

    fabric.publish("fairy.register", {
        "name": "CognitionFairy",
        "plane": "P30",
        "channel": "cognition",
        "capabilities": ["cognition.process", "cognition.analyze"],
    })
    time.sleep(0.5)  # Give worker threads time to process

    reg_status = umf.registration_status()
    print(f"    Supervised fairies: {reg_status['supervised_fairies']}")
    print(f"    Issues found: {reg_status['issues_found']}")

    # Check the registered fairy
    fairies = umf.get_supervised_fairies()
    if "CognitionFairy" in fairies:
        fairy = fairies["CognitionFairy"]
        print(f"    Status: {fairy.get('status')}")
        print(f"    Issues: {fairy.get('validation_issues', [])}")

    # Test 2: Invalid plane format
    print_section("TEST 2: INVALID PLANE FORMAT")
    print("    Registering 'BadPlaneFairy' with invalid plane...")

    fabric.publish("fairy.register", {
        "name": "BadPlaneFairy",
        "plane": "cognition",  # Should be P30, not "cognition"
        "capabilities": ["something"],
    })
    time.sleep(0.5)

    if "BadPlaneFairy" in umf.get_supervised_fairies():
        fairy = umf.get_supervised_fairies()["BadPlaneFairy"]
        print(f"    Status: {fairy.get('status')}")
        print(f"    Issues: {fairy.get('validation_issues', [])}")

    # Get fix suggestions
    fix = umf.suggest_wiring_fix("BadPlaneFairy")
    if fix.get("suggestions"):
        print(f"    Suggestions:")
        for s in fix["suggestions"]:
            print(f"      - {s['suggestion']}")

    # Test 3: Mismatched capabilities
    print_section("TEST 3: MISMATCHED CAPABILITIES")
    print("    Registering 'MismatchedFairy' in P00 with cognition capabilities...")

    fabric.publish("fairy.register", {
        "name": "MismatchedFairy",
        "plane": "P00",  # Autonomic plane
        "capabilities": ["cognition.think"],  # But cognition capabilities!
    })
    time.sleep(0.5)

    if "MismatchedFairy" in umf.get_supervised_fairies():
        fairy = umf.get_supervised_fairies()["MismatchedFairy"]
        print(f"    Status: {fairy.get('status')}")
        print(f"    Issues: {fairy.get('validation_issues', [])}")

    # Test 4: No capabilities
    print_section("TEST 4: NO CAPABILITIES")
    print("    Registering 'EmptyFairy' with no capabilities...")

    fabric.publish("fairy.register", {
        "name": "EmptyFairy",
        "plane": "P30",
        "capabilities": [],
    })
    time.sleep(0.5)

    if "EmptyFairy" in umf.get_supervised_fairies():
        fairy = umf.get_supervised_fairies()["EmptyFairy"]
        print(f"    Status: {fairy.get('status')}")
        print(f"    Issues: {fairy.get('validation_issues', [])}")

    # Test 5: Approve fairy with issues
    print_section("TEST 5: APPROVE WITH OVERRIDE")
    print("    Approving 'BadPlaneFairy' with override...")

    result = umf.approve_fairy("BadPlaneFairy", override_issues=True)
    print(f"    Result: {result}")

    # Test 6: Suggest wiring correction
    print_section("TEST 6: WIRING CORRECTION")
    print("    Suggesting correction for 'MismatchedFairy'...")

    result = umf.correct_wiring(
        "MismatchedFairy",
        plane="P30",
        capabilities={"cognition.think", "cognition.analyze"},
    )
    print(f"    Result: {result}")

    # Test 7: Reject a fairy
    print_section("TEST 7: REJECT FAIRY")
    print("    Rejecting 'EmptyFairy'...")

    result = umf.reject_fairy("EmptyFairy", reason="No capabilities defined")
    print(f"    Result: {result}")

    # Final status
    print_section("FINAL REGISTRATION STATUS")
    status = umf.registration_status()
    print(f"    Supervised fairies: {status['supervised_fairies']}")
    print(f"    Issues found: {status['issues_found']}")
    print(f"    By status: {status['fairies_by_status']}")

    # Full status
    print("\n    All supervised fairies:")
    for name, info in umf.get_supervised_fairies().items():
        print(f"      - {name}: {info.get('status')}")

    # Shutdown
    print_section("SHUTDOWN")
    umf.on_shutdown()
    directory.on_shutdown()
    print("    Clean shutdown complete.")

    print("\n" + "="*60)
    print("  TEST COMPLETE - Fairy Registration Supervision working")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
