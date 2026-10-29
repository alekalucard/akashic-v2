"""thread_snapshot.py -- ONE sys._current_frames() snapshot of her process, taken ONLY when asked.

2026-09-30 (Nous; staged, needs Ace's go). Stdlib only. ASCII only.

WHY THIS EXISTS
  The 5 Hz postal probe (postal_core/python/postal_core/tensor_fabric.py:683) is OFF now (state/postal_probe.off),
  because on 3.14t every sys._current_frames() call stops the world, and one stop-the-world that lands while
  fabric.shutdown() sits in its attached join (directory/fairy.py:414 -> postal_core/src/lib.rs:201-202 ->
  worker.rs:142) freezes the whole process: 5 of 5 probe-on shutdowns wedged, 0 of 2 probe-off
  (nous_builds/probe_ab/runs/ab_20260930_0535/shed/FINDINGS.md, W1-W5). With the probe off we also lost its
  _STALL_AUTOPSY. This module gives that view back, one call at a time, and never during a shutdown.

CONTRACT
  take(system, reason)  server.py's /command action=thread_snapshot calls this. It makes exactly ONE
                        sys._current_frames() call, and only when ALL hold:
                          * the gate is open (close() has not been called in this process),
                          * system.shutdown_requested is not True and system.booted is True,
                          * no other snapshot is running (it never waits for one: it refuses),
                          * at least MIN_INTERVAL_S since the last one (a client loop must not rebuild the probe).
                        The stacks are walked right after the call, still inside the gate. The tally and the file
                        are built after the gate is released. Output: state/thread_snapshots/
                        snap_<YYYYmmdd_HHMMSS>_<pid>_<n>.txt, written to a temp name and renamed. Nothing is deleted.
  close(reason, wait_s) every shutdown path calls this FIRST (server.py shutdown_system). It waits up to wait_s for
                        a snapshot that is already running, then shuts the gate for the life of the process.
                        When it returns True, no snapshot is running and none can start, so no snapshot can
                        overlap fabric.shutdown(). False = a snapshot was still running after wait_s (the gate is
                        shut anyway; the caller logs it).
  tally_text(text)      re-tally a written snapshot, or an old STALL AUTOPSY block, offline (the client uses it).
  Never raises into the caller: take() answers {"ok": False, "refused": ...} or {"ok": False, "error": ...}.

WHAT IS STILL RISKY (stated so nobody is surprised)
  The one call is still a stop-the-world. At run time the only attached, unbounded wait found in postal_core is
  shutdown() (lib.rs:201; publish uses try_send, worker.rs:173), and the probe made ~5 such calls a second for
  weeks with only the shutdown collision observed. A future native call that blocks while attached, waiting on a
  thread that needs Python, would collide with this call the same way. That is why the gate also refuses during
  boot, and why there is a rate limit.
"""
import collections
import os
import sys
import threading
import time

MIN_INTERVAL_S = 10.0           # one snapshot per 10 s at most, process-wide
MAX_DEPTH = 60                  # frames walked per thread
_DEFAULT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "state",
                                            "thread_snapshots"))

# innermost function names that mean "this thread is parked, not working"
_PARKED = frozenset(("wait", "acquire", "_wait_for_tstate_lock", "sleep", "select", "accept", "recv", "recv_into",
                     "readline", "readinto", "get", "_worker", "poll", "serve_forever", "join", "wait_for",
                     "_recv_bytes", "read", "_poll", "_read_stdout_loop", "run_forever", "_run_once"))

_gate = threading.Lock()        # held only while ONE snapshot is being taken; close() takes it to wait one out
_closed = False
_closed_why = ""
_last_t = None                  # time.monotonic() of the last snapshot taken
_count = 0
_frames = sys._current_frames   # indirection so a test can slow the call down; production never reassigns it


def close(reason="shutdown", wait_s=5.0):
    """Shut the gate for good. Waits up to wait_s for a running snapshot. True = none running now."""
    global _closed, _closed_why
    got = False
    try:
        try:
            got = _gate.acquire(timeout=float(wait_s)) if wait_s and wait_s > 0 else _gate.acquire(blocking=False)
        except Exception:
            got = False
        if not _closed:
            _closed = True
            _closed_why = str(reason)[:80]
    finally:
        if got:
            _gate.release()
    return got


def is_open():
    return not _closed


def _refusal(system, min_interval_s, now):
    if _closed:
        return "shutdown has started (%s): no snapshots until she restarts" % (_closed_why or "closed")
    if system is not None:
        if getattr(system, "shutdown_requested", False):
            return "shutdown requested: no snapshots until she restarts"
        if getattr(system, "booted", True) is not True:
            return "boot not finished: no snapshots during boot"
    gap = MIN_INTERVAL_S if min_interval_s is None else float(min_interval_s)
    if _last_t is not None and now - _last_t < gap:
        return "rate limit: last snapshot %.1fs ago, minimum %.0fs" % (now - _last_t, gap)
    return None


def _walk(fr, limit=MAX_DEPTH):
    """(file, function, line) outermost first, innermost last; plus whether the walk was cut."""
    out = []
    f, hops = fr, 0
    while f is not None and hops < limit:
        try:
            c = f.f_code
            out.append((os.path.basename(c.co_filename), c.co_name, f.f_lineno or 0))
        except Exception:
            out.append(("?", "?", 0))
        try:
            f = f.f_back
        except Exception:
            f = None
        hops += 1
    cut = f is not None
    out.reverse()
    return tuple(out), cut


def take(system=None, reason="", out_dir=None, min_interval_s=None):
    """ONE sys._current_frames() call, if allowed. Returns a JSON-able dict; never raises."""
    global _last_t, _count
    if not _gate.acquire(blocking=False):
        return {"ok": False, "refused": "another snapshot is running"}
    try:
        try:
            now = time.monotonic()
            why = _refusal(system, min_interval_s, now)
            if why:
                return {"ok": False, "refused": why}
            me = threading.get_ident()
            names = {}
            for t in threading.enumerate():
                try:
                    names[t.ident] = (t.name, bool(t.daemon))
                except Exception:
                    pass
            t_wall = time.time()
            t0 = time.perf_counter()
            frames = _frames()                 # <<< THE ONE STOP-THE-WORLD CALL >>>
            stw_s = time.perf_counter() - t0
            stacks = {}
            for tid, fr in frames.items():
                stacks[tid] = _walk(fr)
            frames = fr = None                 # drop frame references before leaving the gate
            walk_s = time.perf_counter() - t0 - stw_s
            _last_t = now
            _count += 1
            n = _count
        except Exception as e:
            return {"ok": False, "error": "snapshot failed: %s: %s" % (type(e).__name__, e)}
    finally:
        _gate.release()
    try:
        text, summary = render(stacks, names, me=me, n=n, reason=reason, t_wall=t_wall, stw_s=stw_s, walk_s=walk_s)
        path = _write(text, out_dir, t_wall, n)
        summary.update({"ok": True, "path": path})
        return summary
    except Exception as e:
        return {"ok": False, "error": "snapshot taken but not written: %s: %s" % (type(e).__name__, e)}


def _family(name):
    """'postal[memory]#3' -> 'postal[memory]#', 'http_12' -> 'http_', 'Thread-7 (run)' -> 'Thread-N (run)'."""
    s = str(name)
    out, i = [], 0
    while i < len(s):
        if s[i].isdigit():
            while i < len(s) and s[i].isdigit():
                i += 1
            out.append("N")
            continue
        out.append(s[i])
        i += 1
    return "".join(out)[:48]


def _is_postal(stack):
    return any(fn == "tensor_fabric.py" and nm == "wrapper" for fn, nm, _ln in stack)


def render(stacks, names, me=None, n=0, reason="", t_wall=None, stw_s=0.0, walk_s=0.0):
    """Tallied autopsy text + a short summary dict. Layout is compatible with step25/tally_autopsy.py."""
    t_wall = time.time() if t_wall is None else t_wall
    groups = collections.defaultdict(list)
    cut_n = 0
    for tid, (stack, cut) in stacks.items():
        groups[stack].append(tid)
        cut_n += 1 if cut else 0
    total = len(stacks)
    inner = collections.Counter()
    mm = collections.Counter()
    fam = collections.Counter()
    postal = 0
    parked = 0
    native = 0
    for stack, tids in groups.items():
        k = len(tids)
        if stack:
            inner[stack[-1]] += k
            if stack[-1][1] in _PARKED:
                parked += k
            mmf = [f for f in stack if f[0] == "manifold_memory.py"]
            if mmf:
                mm[mmf[-1]] += k
            if _is_postal(stack):
                postal += k
        for tid in tids:
            nm = names.get(tid)
            if nm is None:
                native += 1
                fam["(not a threading thread: rust/native)"] += 1
            else:
                fam[_family(nm[0])] += 1
    L = []
    L.append("")
    L.append("=" * 96)
    L.append("[%s] THREAD SNAPSHOT #%d -- pid %d -- reason: %s"
             % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t_wall)), n, os.getpid(), (reason or "-")[:80]))
    L.append("  python threads: %d   frames: %d   distinct stacks: %d   stop-the-world call: %.1f ms   walk: %.1f ms"
             % (len(names), total, len(groups), stw_s * 1000.0, walk_s * 1000.0))
    L.append("  threads inside a postal handler: %d   inside manifold_memory.py: %d   parked (wait-like innermost): %d"
             "   not threading threads (rust/native): %d   stacks cut at %d frames: %d"
             % (postal, sum(mm.values()), parked, native, MAX_DEPTH, cut_n))
    L.append("=" * 96)
    L.append("  TALLY -- innermost frames (what each thread is executing right now)")
    for (f, fn, ln), v in inner.most_common(25):
        L.append("    %5d  %-34s %-34s :%s" % (v, f[:34], fn[:34], ln))
    L.append("  TALLY -- deepest manifold_memory.py frame (threads inside the manifold): %d" % sum(mm.values()))
    for (f, fn, ln), v in mm.most_common(12):
        L.append("    %5d  %-34s %-34s :%s" % (v, f[:34], fn[:34], ln))
    L.append("  TALLY -- thread families (digits folded to N)")
    for k, v in fam.most_common(25):
        L.append("    %5d  %s" % (v, k))
    L.append("")
    L.append("  STACKS -- postal-handler stacks first, then rarest first (the outlier is the answer in a deadlock);"
             " outermost frame first, innermost last")
    ordered = sorted(groups.items(), key=lambda kv: (not _is_postal(kv[0]), len(kv[1]), kv[0]))
    for stack, tids in ordered:
        nm = names.get(tids[0])
        label = nm[0] if nm else "(not a threading thread -- rust/native)"
        tags = []
        if _is_postal(stack):
            tags.append("<< INSIDE A POSTAL HANDLER")
        if me in tids:
            tags.append("<< this request's own thread")
        L.append("")
        L.append("  --- %d thread(s), e.g. tid=%s name=%s %s" % (len(tids), tids[0], label, " ".join(tags)))
        for f, fn, ln in stack:
            L.append("        %-34s %-34s :%s" % (f[:34], fn[:34], ln))
    L.append("")
    summary = {
        "n": n, "threads": total, "python_threads": len(names), "distinct_stacks": len(groups),
        "stw_ms": round(stw_s * 1000.0, 2), "walk_ms": round(walk_s * 1000.0, 2),
        "postal_handler_threads": postal, "manifold_threads": sum(mm.values()), "parked": parked,
        "native_threads": native,
        "top_innermost": [["%s %s :%s" % k, v] for k, v in inner.most_common(10)],
    }
    return "\n".join(L) + "\n", summary


def _write(text, out_dir, t_wall, n):
    d = os.path.abspath(out_dir or _DEFAULT_DIR)
    os.makedirs(d, exist_ok=True)
    name = "snap_%s_%d_%d.txt" % (time.strftime("%Y%m%d_%H%M%S", time.localtime(t_wall)), os.getpid(), n)
    path = os.path.join(d, name)
    data = text.encode("ascii", "replace")     # built and encoded BEFORE any file is opened
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    return path


def tally_text(text, top=14):
    """Re-tally snapshot blocks (THREAD SNAPSHOT or STALL AUTOPSY) from file text. Returns a report string."""
    lines = text.split("\n")
    starts = [i for i, l in enumerate(lines) if ("THREAD SNAPSHOT" in l or "STALL AUTOPSY" in l) and "[" in l]
    out = []
    for si, s in enumerate(starts):
        end = starts[si + 1] if si + 1 < len(starts) else len(lines)
        blk = lines[s:end]
        inner = collections.Counter()
        mm = collections.Counter()
        total = 0
        i = 0
        while i < len(blk):
            st = blk[i].strip()
            if st.startswith("--- ") and " thread" in st:
                try:
                    k = int(st.split()[1])
                except Exception:
                    i += 1
                    continue
                total += k
                frames = []
                j = i + 1
                while j < len(blk) and blk[j].strip() and not blk[j].lstrip().startswith("---"):
                    parts = blk[j].split()
                    if len(parts) >= 3 and parts[-1].startswith(":"):
                        frames.append((parts[0], parts[1], parts[-1]))
                    j += 1
                if frames:
                    inner[frames[-1]] += k
                    mmf = [f for f in frames if f[0] == "manifold_memory.py"]
                    if mmf:
                        mm[mmf[-1]] += k
                i = j
            else:
                i += 1
        out.append("== " + blk[0].strip())
        out.append("   threads counted: %d" % total)
        out.append("   innermost frames:")
        for kk, v in inner.most_common(top):
            out.append("     %4d  %s %s %s" % ((v,) + kk))
        out.append("   deepest manifold_memory frame (threads inside the manifold): %d" % sum(mm.values()))
        for kk, v in mm.most_common(10):
            out.append("     %4d  %s %s %s" % ((v,) + kk))
    return "\n".join(out) + ("\n" if out else "no THREAD SNAPSHOT or STALL AUTOPSY block found\n")
