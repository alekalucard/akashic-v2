"""Simple integration test for postal_core."""

from postal_core import PostalCore, USING_RUST
import time
import threading

print(f"Backend: {'Rust' if USING_RUST else 'Python'}")

postal = PostalCore()

# Simple observer
msgs = []
def observer(env):
    msgs.append(env.intent)
    print(f"  [{env.intent}]")

# Heartbeat thread
beats = 0
running = True
def heartbeat_loop():
    global beats
    while running:
        beats += 1
        postal.publish("consciousness.heartbeat", {"beat": beats})
        time.sleep(0.2)

postal.subscribe("consciousness", observer, "observer")
postal.subscribe("fairy", observer, "observer")

# Start heartbeat
t = threading.Thread(target=heartbeat_loop, daemon=True)
t.start()

# Publish some events
postal.publish("fairy.booted", {"name": "TestFairy"})
time.sleep(0.3)
postal.publish("fairy.stopped", {"name": "TestFairy"})
time.sleep(0.3)

running = False
t.join(timeout=0.5)

print(f"\nMessages received: {len(msgs)}")
print(f"Heartbeats: {beats}")
print("Metrics:", postal.metrics())
postal.shutdown()
print("Done!")
