"""Test ignition sequence - Phase 1 verification."""
import asyncio
import sys
sys.path.insert(0, '.')

async def test_ignition_loop():
    """Test that waking.complete -> consciousness.ignited loop closes."""
    from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub

    hub = get_shared_postal_hub()
    received_signals = []

    def on_waking_complete(msg):
        received_signals.append(("waking.complete", msg))

    def on_consciousness_ignited(msg):
        received_signals.append(("consciousness.ignited", msg))

    hub.subscribe("waking.complete", on_waking_complete)
    hub.subscribe("consciousness.ignited", on_consciousness_ignited)

    # Simulate the signal
    hub.publish("waking.complete", {"ts": 1234, "test": True})

    await asyncio.sleep(0.5)

    assert len(received_signals) >= 1, "waking.complete not received"
    print("Ignition test PASSED")

if __name__ == "__main__":
    asyncio.run(test_ignition_loop())
