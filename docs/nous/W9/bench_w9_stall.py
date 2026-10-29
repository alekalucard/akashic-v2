"""W9 bench: what one decay pass costs on a synthetic 2,000,000-slot manifold, unchunked (the interior's decay_all) vs chunked
(WriterDecay), and how long a concurrent writer (touch_node in a loop, the shard-locked hot path) is stalled meanwhile.

Synthetic file in a temp dir, deleted at the end. Every slot is filled with an ACTIVE node (activation 0.5): the worst case,
since decay_all only writes nodes above 0.01.

    python docs/nous/W9/bench_w9_stall.py [n_nodes]
"""
import os
import random
import shutil
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.environ.get("W9_CODE_ROOT") or os.path.normpath(os.path.join(HERE, "..", "..", "..", "code"))
sys.path.insert(0, CODE)
from infrastructure import manifold_memory as mmem     # noqa: E402
from infrastructure import portal_gate as pg           # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000


class Probe:
    """A writer thread: touch_node on random keys back to back; records the longest gap between two completed ops."""

    def __init__(self, m, keys):
        self.m, self.keys = m, keys
        self.run = True
        self.gaps = []
        self.t = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        rnd = random.Random(1)
        last = time.perf_counter()
        while self.run:
            self.m.touch_node(self.keys[rnd.randrange(len(self.keys))], 0.0)   # energy 0: same RMW, value unchanged
            now = time.perf_counter()
            self.gaps.append(now - last)
            last = now

    def window(self, fn):
        self.gaps = []
        t0 = time.perf_counter()
        fn()
        wall = time.perf_counter() - t0
        g = sorted(self.gaps) or [0.0]
        return {"wall_s": round(wall, 3), "writer_ops": len(g), "writer_max_gap_ms": round(g[-1] * 1000, 2),
                "writer_p99_gap_ms": round(g[int(len(g) * 0.99) - 1 if len(g) > 1 else 0] * 1000, 3)}


def main():
    d = tempfile.mkdtemp(prefix="w9_bench_")
    try:
        t0 = time.perf_counter()
        m = mmem.ManifoldMemory(os.path.join(d, "synthetic.manifold"), node_capacity=N, edge_capacity=1000)
        for i in range(N):
            m.upsert_node("c%d" % i, activation=0.5)
        print("python %s, gil_enabled=%s, cores=%s" % (sys.version.split()[0],
              getattr(sys, "_is_gil_enabled", lambda: True)(), os.cpu_count()))
        print("built %d nodes in %.1fs (file %.0f MB)" % (m.node_count, time.perf_counter() - t0,
                                                         os.path.getsize(m.filepath) / 1e6))
        keys = list(m._key_index.keys())
        print("key snapshot: list of %d keys = %.1f MB (list object only; strings are shared)" % (
            len(keys), sys.getsizeof(keys) / 1e6))
        os.environ["AKASHIC_DECAY_IN_WRITER"] = "1"
        # SOLO: the pass alone, no competing thread (what one pass costs)
        t1 = time.perf_counter()
        m.decay_all(0.001)
        print("SOLO decay_all(0.001) unchunked: %.3f s in ONE call (no yield point inside)" % (time.perf_counter() - t1))
        wd = pg.WriterDecay(m, chunk=10000, pause_s=0.01)
        out = wd.run_pass()
        print("SOLO WriterDecay chunk=10000 pause=10ms:", {k: out[k] for k in ("status", "decayed", "chunks",
                                                                                  "max_chunk_ms", "wall_s")})
        p = Probe(m, keys)
        p.t.start()
        time.sleep(0.5)
        print("baseline (no decay, 2 s):", p.window(lambda: time.sleep(2.0)))
        print("decay_all(0.001), one call, unchunked (the interior's):", p.window(lambda: m.decay_all(0.001)))
        for chunk, pause in ((10000, 0.01), (5000, 0.01), (20000, 0.01), (50000, 0.01)):
            wd = pg.WriterDecay(m, chunk=chunk, pause_s=pause)
            out = {}
            w = p.window(lambda: out.update(wd.run_pass()))
            print("WriterDecay chunk=%d pause=%.0fms:" % (chunk, pause * 1000), w,
                  {k: out[k] for k in ("status", "decayed", "chunks", "max_chunk_ms")})
        p.run = False
        p.t.join(5)
        m.close()
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
