"""farm_remote_server.py -- host the RWKV GPU farm on a satellite, same wire as the local gate.

2026-09-12 (Nous + Ace): "unless we can use some from the satellite to help with this load."
The farm (gpu_inference_portal.py) is a separate process that speaks JSON-per-line over stdin/
stdout and logs on stderr. PC1's gpu_portal_gate.py normally spawns it as a subprocess; here the
gate connects two TCP sockets instead (data + log) and this server does the spawning on the
satellite. The gate's code path is unchanged -- it sees a Popen-shaped object (see _RemoteProc in
gpu_portal_gate.py). Contract, same as the Florence satellite: RESPONDS, NEVER PUSHES.

  data socket (port P):   client -> farm stdin (JSON lines); farm stdout -> client
  log  socket (port P+1): farm stderr -> client (the gate prints these as '[Portal] ...')

One client at a time. When the client goes away the farm gets {"cmd":"shutdown"} -- so the
RWKV state save runs HERE (state/rwkv_state/<portal-id>/ on the satellite), then a 60 s grace,
then terminate. ASCII-only output: the console on .74 is cp1252.

Run (on the satellite, from the akashic_v2 root):
  python3.14t.exe -u infrastructure\\farm_remote_server.py --portal <path.portal> --port 8792 \\
      --workers 1 --gravity 2.0 --portal-id sour-gpu
"""
import argparse
import io
import os
import socket
import subprocess
import sys
import threading
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="ascii", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="ascii", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def log(msg):
    print("[FarmRemote %s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def pump(src, dst, name, on_eof):
    """Copy lines src -> dst until EOF; dst may be a socket file or a real file."""
    try:
        for line in src:
            if not line:
                break
            try:
                dst.write(line)
                dst.flush()
            except Exception as e:
                log("%s: write failed (%s) -- stopping" % (name, e))
                break
    except Exception as e:
        log("%s: read ended (%s)" % (name, e))
    finally:
        on_eof(name)


def serve_one(data_conn, log_conn, farm_cmd, env, close_wait):
    peer = data_conn.getpeername()
    log("client %s:%d connected -- spawning farm" % peer)
    farm = subprocess.Popen(farm_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, bufsize=1, text=True, cwd=ROOT)
    log("farm pid %d" % farm.pid)
    d_r = data_conn.makefile("r", encoding="utf-8", errors="replace", newline="\n")
    d_w = data_conn.makefile("w", encoding="utf-8", errors="replace", newline="\n")
    l_w = log_conn.makefile("w", encoding="utf-8", errors="replace", newline="\n")
    stderr_file = open(os.path.join(ROOT, "state", "farm_remote_stderr.log"), "a", encoding="utf-8", errors="replace")

    class Tee:
        def write(self, s):
            stderr_file.write(s)
            try:
                l_w.write(s)
            except Exception:
                pass

        def flush(self):
            stderr_file.flush()
            try:
                l_w.flush()
            except Exception:
                pass

    done = threading.Event()

    def on_eof(name):
        log("%s hit EOF" % name)
        done.set()

    threads = [
        threading.Thread(target=pump, args=(d_r, farm.stdin, "client->farm", on_eof), daemon=True),
        threading.Thread(target=pump, args=(farm.stdout, d_w, "farm->client", on_eof), daemon=True),
        threading.Thread(target=pump, args=(farm.stderr, Tee(), "farm stderr", lambda n: None), daemon=True),
    ]
    for t in threads:
        t.start()
    done.wait()
    # Client gone (or farm gone): ask the farm to shut down gracefully -> RWKV save on THIS box.
    if farm.poll() is None:
        log("asking farm to shut down (grace %.0fs)" % close_wait)
        try:
            farm.stdin.write('{"cmd": "shutdown"}\n')
            farm.stdin.flush()
        except Exception:
            pass
        try:
            farm.wait(timeout=close_wait)
            log("farm exited on its own")
        except subprocess.TimeoutExpired:
            log("farm did not exit in %.0fs -- terminating" % close_wait)
            farm.terminate()
            try:
                farm.wait(timeout=10)
            except subprocess.TimeoutExpired:
                farm.kill()
    else:
        log("farm exited with code %s" % farm.returncode)
    # Tell the client the farm is gone NOW: shut the sockets down before closing the file
    # wrappers, or the gate's wait() sees no EOF until IT gives up (measured: 90 s timeout on
    # the first end-to-end test while the save had finished 0.0 s after shutdown began).
    for c in (data_conn, log_conn):
        try:
            c.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
    for f in (d_r, d_w, l_w):
        try:
            f.close()
        except Exception:
            pass
    try:
        stderr_file.close()
    except Exception:
        pass
    for c in (data_conn, log_conn):
        try:
            c.close()
        except Exception:
            pass
    log("session with %s:%d ended" % peer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--portal", required=True)
    ap.add_argument("--port", type=int, default=8792)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--gravity", type=float, default=2.0)
    ap.add_argument("--portal-id", default="sour-gpu")
    ap.add_argument("--token-budget", type=int, default=1000000)
    ap.add_argument("--flops-budget", type=int, default=50000000000)
    ap.add_argument("--max-charge", type=float, default=10000.0)
    ap.add_argument("--recharge-rate", type=float, default=100.0)
    ap.add_argument("--close-wait", type=float, default=60.0)
    a = ap.parse_args()
    if not os.path.exists(a.portal):
        log("portal file not found: %s" % a.portal)
        return 2
    farm_cmd = [sys.executable, "-u", os.path.join(HERE, "gpu_inference_portal.py"),
                "--portal", a.portal, "--workers", str(a.workers), "--gravity", str(a.gravity),
                "--token-budget", str(a.token_budget), "--portal-id", a.portal_id,
                "--flops-budget", str(a.flops_budget), "--max-charge", str(a.max_charge),
                "--recharge-rate", str(a.recharge_rate)]
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.setdefault("AKASHIC_RWKV_PERSIST", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    os.makedirs(os.path.join(ROOT, "state"), exist_ok=True)

    data_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    log_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for s, p in ((data_srv, a.port), (log_srv, a.port + 1)):
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((a.bind, p))
        s.listen(1)
    log("listening data=%d log=%d portal=%s python=%s" % (a.port, a.port + 1, os.path.basename(a.portal), sys.version.split()[0]))
    while True:
        data_conn, _ = data_srv.accept()
        data_conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        log_srv.settimeout(15.0)
        try:
            log_conn, _ = log_srv.accept()
        except socket.timeout:
            log("data client connected but no log connection within 15s -- dropping")
            data_conn.close()
            continue
        finally:
            log_srv.settimeout(None)
        try:
            serve_one(data_conn, log_conn, farm_cmd, env, a.close_wait)
        except Exception as e:
            log("session error: %s" % e)


if __name__ == "__main__":
    sys.exit(main())
