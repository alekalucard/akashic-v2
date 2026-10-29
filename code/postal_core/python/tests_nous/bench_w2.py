"""W2 per-publish cost of the Python fallback, switch OFF vs ON. Synthetic, in-process.

    python3 code/postal_core/python/tests_nous/bench_w2.py

Cases: a letter nobody wants (the new path), and a letter with one subscriber (must be unchanged).
Median of 5 runs of N publishes each. Handlers are no-ops; worker threads drain in the background.
"""
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_w2_return_to_sender import FB, Env  # noqa: E402

N = 20000


def per_publish_us(on: bool, subscribed: bool) -> float:
    env = {"AKASHIC_RETURN_TO_SENDER": "1", "AKASHIC_RETURN_RATE": "1"} if on else {}
    with Env(**env):
        pc = FB.PostalCore()
    try:
        if subscribed:
            pc.subscribe("bench.hit", lambda e: None, name="bench")
        intent = "bench.hit" if subscribed else "bench.miss"
        payload = {"source": "Bench"}
        runs = []
        for _ in range(5):
            t0 = time.perf_counter()
            for _ in range(N):
                pc.publish(intent, payload)
            runs.append((time.perf_counter() - t0) / N * 1e6)
        return statistics.median(runs)
    finally:
        pc.shutdown()


if __name__ == "__main__":
    for subscribed in (False, True):
        off = per_publish_us(False, subscribed)
        on = per_publish_us(True, subscribed)
        print("python fallback, %-13s OFF %6.2f us/publish   ON %6.2f us/publish   (ON-OFF %+.2f us)"
              % ("subscribed:" if subscribed else "no subscriber:", off, on, on - off))
