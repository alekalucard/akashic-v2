"""Minimal fairy test."""
import sys
print("Starting minimal fairy test...", flush=True)
sys.stdout.flush()

from postal_core import PostalCore, USING_RUST
print(f"Postal backend: {'Rust' if USING_RUST else 'Python'}", flush=True)

postal = PostalCore()
print("PostalCore created", flush=True)

def handler(env):
    print(f"  Handler called: {env.intent}", flush=True)

postal.subscribe("test", handler, "test-handler")
print("Subscribed", flush=True)

postal.publish("test.hello", {"msg": "world"})
print("Published", flush=True)

import time
time.sleep(0.2)
print("Waited", flush=True)

print("Metrics:", postal.metrics(), flush=True)

postal.shutdown()
print("Done!", flush=True)
