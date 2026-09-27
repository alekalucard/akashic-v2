"""
Test HardwareFairy + UMF Integration

Shows:
1. HardwareFairy sensing CPU/GPU/RAM
2. UMF receiving hardware alerts
3. Worker pool management based on load
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
from hardware import HardwareFairy, HardwareSensors, HAS_CUDA, CUDA_DEVICE_COUNT
from fairies.P20_Somatic.SomaticMindFairy import SomaticMindFairy as UnconsciousMindFairy


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def main():
    print_section("HARDWARE FAIRY + UMF INTEGRATION TEST")

    # Create infrastructure
    print("\n[1] Booting infrastructure...")
    fabric = TensorFabric()

    # Create directory
    directory = DirectoryFairy(fabric)
    directory.on_boot()
    set_directory(directory)
    print("    Directory: OK")

    # Create HardwareFairy
    print("\n[2] Creating HardwareFairy...")
    hw_fairy = HardwareFairy(fabric)
    hw_fairy.boot()
    print(f"    HardwareFairy: {hw_fairy.state.value}")
    print(f"    Has GPU: {HAS_CUDA}")
    print(f"    GPU Count: {CUDA_DEVICE_COUNT}")

    # Take initial sample
    print("\n[3] Taking hardware sample...")
    snapshot = hw_fairy.sample()
    print(f"    CPU: {snapshot.get('cpu', {}).get('percent', 0):.1f}%")
    print(f"    RAM: {snapshot.get('ram', {}).get('percent', 0):.1f}%")
    if snapshot.get('gpus'):
        for gpu in snapshot['gpus']:
            print(f"    GPU {gpu['device_id']}: {gpu['name']}")
            print(f"      Memory: {gpu['memory_used_mb']:.0f}/{gpu['memory_total_mb']:.0f} MB")

    # Create UMF
    print("\n[4] Creating UnconsciousMindFairy...")
    umf = UnconsciousMindFairy(fabric)
    umf.on_boot()
    print(f"    UMF: {umf.state.value}")

    # Wire HardwareFairy to UMF
    print("\n[5] Wiring HardwareFairy to UMF...")
    wired = umf.wire_hardware_fairy(hw_fairy)
    print(f"    Wired: {'OK' if wired else 'FAILED'}")

    # Check hardware status through UMF
    print_section("UMF HARDWARE STATUS")
    hw_status = umf.hardware_status()
    print(f"    Available: {hw_status['available']}")
    print(f"    Has GPU: {hw_status['has_gpu']}")
    print(f"    Stress level: {hw_status['stress_level']}")
    print(f"    CPU: {hw_status.get('cpu_percent', 'N/A')}%")
    print(f"    RAM: {hw_status.get('ram_percent', 'N/A')}%")

    # Check worker config
    print("\n    Worker Config:")
    worker_cfg = hw_status['worker_config']
    print(f"      CPU workers: {worker_cfg['cpu_workers']}")
    print(f"      GPU workers: {worker_cfg['gpu_workers']}")
    print(f"      Max concurrent: {worker_cfg['max_concurrent']}")

    # Test worker limit adjustment
    print_section("WORKER POOL MANAGEMENT")
    print("    Setting custom worker limits...")
    new_config = umf.set_worker_limits(cpu_workers=8, gpu_workers=1, max_concurrent=12)
    print(f"    New config: {new_config}")

    # Request fresh sample through UMF
    print("\n    Requesting fresh hardware sample through UMF...")
    fresh = umf.request_hardware_sample()
    print(f"    CPU: {fresh.get('cpu', {}).get('percent', 0):.1f}%")
    print(f"    RAM: {fresh.get('ram', {}).get('percent', 0):.1f}%")

    # Simulate some ticks
    print_section("SIMULATING HEARTBEATS")
    print("    Running 10 ticks...")
    for i in range(10):
        hw_fairy.on_tick(i)
        umf.on_tick(i)
        if i % 4 == 0:
            hw_fairy._publish_status()

    # Check UMF capabilities
    print_section("UMF CAPABILITIES")
    caps = umf.get_capabilities()
    for cap in sorted(caps):
        print(f"    - {cap}")

    # Full status
    print_section("FULL STATUS")
    full = umf.full_status()
    print(f"    Fairy state: {full['fairy']['state']}")
    print(f"    Hardware available: {full['hardware']['available']}")
    print(f"    Hardware stress: {full['hardware']['stress_level']}")
    print(f"    Helix active: {full['helix']['active']}")

    # Shutdown
    print_section("SHUTDOWN")
    hw_fairy.shutdown()
    umf.on_shutdown()
    directory.on_shutdown()
    print("    Clean shutdown complete.")

    print("\n" + "="*60)
    print("  TEST COMPLETE - HardwareFairy + UMF integrated")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
