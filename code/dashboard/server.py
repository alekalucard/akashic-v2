"""
Akashic Dashboard Server - Boots UMF and exposes via bridge.

This is the Python backend that the Tauri dashboard launches.
It creates the full UnconsciousMindFairy stack and exposes it.
"""

import sys
import time
import signal
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

def main():
    """Boot the UMF and start the bridge server."""
    print("[Server] Starting Akashic Dashboard Server...")

    # Import after path setup
    from dashboard.http_bridge import HTTPDashboardBridge as DashboardBridge
    from directory import DirectoryFairy, set_directory
    from postal_core.tensor_fabric import TensorFabric
    from fairies.P20_Somatic.SomaticMindFairy import SomaticMindFairy
    UnconsciousMindFairy = SomaticMindFairy
    from consciousness import ConsciousnessLoop, CollisionChamber

    # Create infrastructure
    print("[Server] Creating infrastructure...")
    fabric = TensorFabric()
    directory = DirectoryFairy(fabric)
    directory.on_boot()
    set_directory(directory)

    # Create consciousness system
    print("[Server] Creating consciousness system...")
    chamber = CollisionChamber()
    consciousness = ConsciousnessLoop(tick_interval=0.5)
    consciousness.set_chamber(chamber)

    # Create and boot UMF
    print("[Server] Booting UnconsciousMindFairy...")
    umf = UnconsciousMindFairy(fabric)
    umf.boot()

    # Wire consciousness
    print("[Server] Wiring consciousness...")
    umf.wire_to_consciousness(consciousness, chamber)

    # Wire memory
    print("[Server] Wiring memory backbone...")
    umf.wire_memory(auto_create=True)

    # Wire cognition
    print("[Server] Wiring cognition loop...")
    umf.wire_cognition(auto_create=True)

    # Wire circadian clock
    print("[Server] Wiring circadian clock...")
    umf.wire_circadian()

    # Wire three gates
    print("[Server] Wiring three gates...")
    umf.wire_three_gates(auto_create=True)

    # Start consciousness loop
    print("[Server] Starting consciousness loop...")
    consciousness.start()

    # Create and start bridge
    print("[Server] Starting dashboard bridge on port 5757...")
    bridge = DashboardBridge(umf, port=5757)
    bridge.start()

    # Track running state
    running = True

    def shutdown_handler(signum, frame):
        nonlocal running
        print("\n[Server] Shutdown signal received...")
        running = False

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print("[Server] Ready! Dashboard can now connect.")
    print("[Server] Press Ctrl+C to stop.")

    # Main loop - tick the clock periodically
    try:
        tick_count = 0
        while running:
            time.sleep(1.0)
            tick_count += 1

            # Tick the circadian clock
            umf.clock_tick()

            # Periodic status
            if tick_count % 30 == 0:
                status = umf.full_status()
                print(f"[Server] Heartbeat: beats={status.get('consciousness', {}).get('loop_beats', 0)}, "
                      f"thoughts={len(umf.get_thoughts(5))}")

    except KeyboardInterrupt:
        pass

    # Cleanup
    print("[Server] Shutting down...")
    bridge.stop()
    consciousness.stop()
    umf.shutdown()
    directory.on_shutdown()
    print("[Server] Goodbye!")


if __name__ == "__main__":
    main()
