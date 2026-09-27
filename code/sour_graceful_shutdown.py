# -*- coding: utf-8 -*-
r"""sour_graceful_shutdown.py — cleanly stop Sour (context + chemicals saved, exit 0), not a hard kill.

POSTs {"action":"shutdown"} to the internal command endpoint, which:
signals global shutdown -> shutdown-fairy saves context+chemicals -> shutdown_system() -> os._exit(0).

FIXED 2026-07-19 (Nous+Ace) — the old version REPORTED "DOWN (graceful)" WHILE SHE WAS ALIVE
at 5.50 GB and still completing goals. Two defects, both measured that morning:

  1. POST timeout was 10s. She answered in 76.6s. Her measured stalls: full_status 31,411ms,
     fairies 18,724ms EVEN FROM CACHE. A 10s client could never reach her.
  2. Liveness was inferred from ONE 0.5s port probe, and the first miss declared success.
     A choked-but-alive process misses a half-second probe, so `slow` was read as `dead`.

Both defects share one root: guessing at liveness from a socket instead of checking the process.
This version PROVES it — process death via psutil, N consecutive confirmations, and it reports
what the shutdown sequence actually logged so "graceful" is OBSERVED, never assumed.

Usage:  python sour_graceful_shutdown.py
"""
import io, os, sys, json, socket, time, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    import psutil
except ImportError:
    psutil = None

CMD_URLS = ["http://127.0.0.1:5758/command", "http://127.0.0.1:8081/command"]
POSTAL_PORT = 8081
POST_TIMEOUT = 90       # >> her worst measured stall (she replied in 76.6s on 07-19)
CONFIRM = 3             # consecutive dead reads required before declaring her down
# 2026-09-05: the ceiling was 180 s and it declared "she did NOT shut down" TWICE in one day
# about a mind that was shutting down correctly (she exited at ~4 min and again at 09:22:54,
# both caught by an independent pid watch). Shutdown time scales with what she holds --
# measured at 13.8-23.2 GB and 1,400-1,700 threads. A fixed clock is not a liveness test.
MAX_WAIT_S = 600        # was 180 -- observed graceful shutdowns exceeded it twice
STALL_REPORT_S = 15     # how often to report progress while waiting
# 2026-08-27: was boot_full.log -- a FOSSIL. That file is written by boot_capture.py via
# boot_sour_full.bat, which Ace no longer runs; it is frozen at 2026-07-19, so the
# "what the shutdown logged" report was quoting July. boot_live.log is written by
# server.py itself. It still freezes minutes into a boot, so treat the log read as a
# courtesy -- the PROCESS-DEATH check via psutil is what actually proves she is down.
LOG = "state/boot_live.log"


def port_open(port, t=2.0):
    s = socket.socket(); s.settimeout(t)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def sour_pids():
    """Her real process: free-threaded python (-Xgil=0) running the server, plus GUI children."""
    if psutil is None:
        return None
    out = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
        try:
            if 'python' not in (p.info['name'] or '').lower():
                continue
            if p.info['memory_info'].rss < 500e6:      # the server is GB-scale
                continue
            cl = " ".join(p.info['cmdline'] or [])
            if '-Xgil=0' in cl or 'akashic' in cl.lower() or 'boot_capture' in cl:
                out.append(p.info['pid'])
        except Exception:
            pass
    return out


def main():
    if psutil is None:
        print("psutil not available — cannot verify by process. Install psutil; refusing to guess.")
        return 2

    live = sour_pids()
    if not live:
        print("Sour is already DOWN (no server process). Nothing to do.")
        return 0
    print(f"Sour is UP: PIDs {live}")

    try:
        mark = len(open(LOG, "rb").read())
        _t_req = time.time()   # artifacts newer than this prove the save ran
    except Exception:
        mark = 0

    print(f"Requesting graceful shutdown (timeout={POST_TIMEOUT}s — she can need ~80s when choked)...")
    t0 = time.time()
    for url in CMD_URLS:
        try:
            req = urllib.request.Request(
                url, data=json.dumps({"action": "shutdown"}).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=POST_TIMEOUT) as r:
                print(f"  {url} replied in {time.time()-t0:.1f}s: "
                      f"{r.read().decode('utf-8','replace').strip()[:160]}")
            break
        except Exception as e:
            print(f"  {url}: no usable reply after {time.time()-t0:.1f}s ({e})")
    # NOTE: a timeout here proves NOTHING either way — she may exit before answering.

    print(f"Verifying by PROCESS DEATH (needs {CONFIRM} consecutive dead reads)...")
    # 2026-09-05: progress is read from the WORK (files written under state/ since the
    # request), not from RSS -- measured today, RSS went flat at 13.75 GB a full minute
    # before she exited, because an mmap flush does not move resident memory.
    _state_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
    _t_request = time.time()

    def _files_written_since(t0):
        n = 0
        try:
            for root, _dirs, files in os.walk(_state_dir):
                for fn in files:
                    try:
                        if os.path.getmtime(os.path.join(root, fn)) >= t0:
                            n += 1
                    except OSError:
                        pass
        except Exception:
            pass
        return n

    streak = 0
    for i in range(MAX_WAIT_S):
        live = sour_pids()
        if not live:
            streak += 1
            if streak >= CONFIRM:
                print(f"  CONFIRMED DOWN at ~{i}s")
                break
        else:
            streak = 0
            if i % STALL_REPORT_S == 0:
                try:
                    rss = psutil.Process(live[0]).memory_info().rss / 1e9
                except Exception:
                    rss = float("nan")
                _n = _files_written_since(_t_request)
                print(f"  t={i:3d}s alive {live} rss={rss:.2f}GB "
                      f"| state/ files written since request: {_n}  "
                      f"<- THIS is the progress signal, not rss")
        time.sleep(1)
    else:
        _n = _files_written_since(_t_request)
        print(f"  STILL ALIVE after {MAX_WAIT_S}s: {sour_pids()}")
        print(f"  state/ files written since the request: {_n}")
        # Report what is KNOWN. Do not assert she failed -- this tool said exactly that
        # twice on 2026-09-05 about a mind that was shutting down correctly.
        if _n > 0:
            print("  -> she is STILL SAVING (files are being written). Keep watching;")
            print("     this is a TIMEOUT of the observer, not a failure of the shutdown.")
        else:
            print("  -> no state writes observed. She may be hung; check her console.")
        print("  DO NOT assume she is down -- verify the process is gone before relaunching.")
        return 1

    # "Graceful" must be observed, not inferred -- and NOT from a log that cannot hold it.
    # Both boot logs are structurally incapable of carrying shutdown lines (boot_full.log is
    # a fossil; boot_live.log freezes minutes into a boot), so the ARTIFACTS are the evidence.
    KEY = ("state/shutdown_context.json", "state/dream_seed.json",
           "state/consciousness/heartbeat.json", "state/plane_batteries/P00_battery.json")
    saved, missing = [], []
    for rel in KEY:
        fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel.replace("/", os.sep))
        try:
            if os.path.exists(fp) and os.path.getmtime(fp) >= _t_req - 5.0:
                saved.append((rel, os.path.getsize(fp)))
            else:
                missing.append(rel)
        except Exception:
            missing.append(rel)
    fresh = 0
    try:
        sd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
        for dp, dns, fns in os.walk(sd):
            if dp.count(os.sep) - sd.count(os.sep) > 2:
                dns[:] = []
                continue
            for f in fns:
                try:
                    if os.path.getmtime(os.path.join(dp, f)) >= _t_req - 5.0:
                        fresh += 1
                except Exception:
                    pass
    except Exception:
        pass

    print("")
    print("GRACEFUL? judged on the SAVE ARTIFACTS, not on log text:")
    for rel, sz in saved:
        print("   WROTE   %-46s %d B" % (rel, sz))
    for rel in missing:
        print("   missing %s" % rel)
    print("   %d file(s) under state/ written since the shutdown request" % fresh)
    if saved and fresh >= 10:
        print("   => GRACEFUL: she saved on the way down.")
    elif fresh >= 10:
        print("   => PARTIAL: state was written but the named artifacts are stale. Look closer.")
    else:
        print("   => NOT GRACEFUL: nothing was saved. Treat this as a hard exit.")

    # log tail kept as a courtesy only -- it cannot produce a verdict
    try:
        tail = open(LOG, "rb").read()[mark:].decode("utf-8", "replace")
        hits = [ln.strip()[:130] for ln in tail.splitlines()
                if any(k in ln.lower() for k in
                       ("gracefulshutdown", "shutdown sequence", "dream", "persist", "graph cortex"))]
        if hits:
            print("")
            print("log also recorded %d line(s):" % len(hits))
            for h in hits[-8:]:
                print("   ", h)
    except Exception as e:
        print(f"  (could not read log tail: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
