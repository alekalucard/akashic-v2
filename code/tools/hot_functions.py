"""WHICH FUNCTION is burning her CPU? The census named the module. The log named the
thread. Nothing has ever named the function.

Yesterday's lesson, applied one level down: "when an attribution has a large unknown
bucket, build the instrument that names it BEFORE proposing anything."

METHOD. Two sources joined, because either alone lies:
  (a) psutil per-thread user+system time DELTAS  -> which OS threads actually burn CPU
  (b) sys._current_frames() stack samples        -> what those threads are executing
(b) alone is the trap her own _PostalProbe fell into: it sampled ALL ~1,500 thread stacks
at 5 Hz forever into a 271 MB log, and reported that its four hot functions were
_send_and_receive/_run/_poll/_poll_loop -- i.e. it mostly sampled threads that were PARKED,
so it measured where threads WAIT, not where they WORK. Weighting each sample by that
thread's measured CPU delta fixes exactly that.

RUNS OUTSIDE HER PROCESS is impossible for stacks, so this is designed to be imported and
started INSIDE her (one bounded thread, hard stop, writes one small file). It is gated and
self-terminating -- this project has four ungated diagnostics that became permanent overhead.

Usage, from inside her process:
    from name_the_function import profile
    profile(seconds=60, out=r"state\\hot_functions.txt")

Or standalone against THIS process for a self-test:
    python name_the_function.py
"""
import collections
import io
import os
import sys
import threading
import time
import traceback

_ASCII = lambda s: s.encode("ascii", "replace").decode("ascii")


def profile(seconds=60.0, hz=20.0, out=None, top=30):
    """Sample stacks, weight by real per-thread CPU, write the answer. Never runs forever."""
    try:
        import psutil
    except Exception:
        psutil = None

    me = psutil.Process(os.getpid()) if psutil else None
    deadline = time.time() + float(seconds)
    period = 1.0 / float(hz)

    # tid -> Counter(frame_key -> samples)
    per_thread = collections.defaultdict(collections.Counter)
    samples_taken = 0

    t0_cpu = {}
    if me:
        for t in me.threads():
            t0_cpu[t.id] = t.user_time + t.system_time

    while time.time() < deadline:
        try:
            frames = sys._current_frames()
        except Exception:
            break
        for tid, frame in frames.items():
            # Attribute to the DEEPEST frame that is her code, not the runtime's
            key = None
            f = frame
            depth = 0
            while f is not None and depth < 60:
                co = f.f_code
                fn = co.co_filename
                if ("akashic_v2" in fn or "postal_core" in fn) and "site-packages" not in fn:
                    key = "%s:%s" % (os.path.basename(fn), co.co_name)
                    break
                f = f.f_back
                depth += 1
            if key is None:
                co = frame.f_code
                key = "<runtime> %s:%s" % (os.path.basename(co.co_filename), co.co_name)
            per_thread[tid][key] += 1
        samples_taken += 1
        time.sleep(period)

    # Real CPU per thread over the same window -- this is the WEIGHT.
    cpu_delta = {}
    if me:
        for t in me.threads():
            d = (t.user_time + t.system_time) - t0_cpu.get(t.id, t.user_time + t.system_time)
            if d > 0:
                cpu_delta[t.id] = d

    total_cpu = sum(cpu_delta.values()) or 1e-9
    weighted = collections.Counter()
    unweighted = collections.Counter()
    for tid, counter in per_thread.items():
        n = sum(counter.values()) or 1
        share = cpu_delta.get(tid, 0.0)
        for key, c in counter.items():
            weighted[key] += share * (c / n)      # CPU-seconds attributable to this function
            unweighted[key] += c                   # raw sample count (what the old probe saw)

    lines = []
    lines.append("HOT FUNCTIONS  window=%.0fs  samples=%d  threads_seen=%d"
                 % (seconds, samples_taken, len(per_thread)))
    lines.append("total CPU in window: %.1f CPU-s  (%.2f cores)"
                 % (total_cpu, total_cpu / max(seconds, 1e-9)))
    lines.append("")
    lines.append("=== BY REAL CPU (stack samples WEIGHTED by measured per-thread CPU) ===")
    lines.append("  %-52s %9s %7s" % ("function", "cores", "share"))
    for key, v in weighted.most_common(top):
        lines.append("  %-52s %9.3f %6.1f%%"
                     % (_ASCII(key)[:52], v / max(seconds, 1e-9), 100.0 * v / total_cpu))
    lines.append("")
    lines.append("=== BY RAW SAMPLE COUNT (what an unweighted probe reports) ===")
    lines.append("  this column is where threads WAIT; the one above is where they WORK.")
    tot_s = sum(unweighted.values()) or 1
    for key, c in unweighted.most_common(12):
        lines.append("  %-52s %6.1f%%" % (_ASCII(key)[:52], 100.0 * c / tot_s))

    text = "\n".join(lines)
    if out:
        try:
            data = text.encode("utf-8")          # encode BEFORE opening for write
            tmp = out + ".tmp"
            io.open(tmp, "wb").write(data)
            os.replace(tmp, out)
        except Exception:
            pass
    return text


def _self_test():
    """Prove the weighting matters: one busy thread, many parked ones."""
    stop = [False]

    def busy():
        x = 0
        while not stop[0]:
            x = (x * 31 + 7) % 1000003

    def parked():
        while not stop[0]:
            time.sleep(0.25)

    ts = [threading.Thread(target=busy, daemon=True, name="BUSY")]
    ts += [threading.Thread(target=parked, daemon=True, name="parked%d" % i)
           for i in range(12)]
    for t in ts:
        t.start()
    print("running 12 parked threads + 1 busy thread for 8s...")
    out = profile(seconds=8.0, hz=20.0, top=6)
    stop[0] = True
    print(out)


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="ascii", errors="replace")
    _self_test()
