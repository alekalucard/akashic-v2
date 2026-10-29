"""farm_ollama_adapter.py -- the RWKV farm's wire, with an Ollama (llama.cpp) model behind it.

2026-09-13 (Nous + Ace): "the idea of the farm was to make it adaptable ... her current farm model is
pretty slow sadly." gpu_portal_gate.py speaks JSON-per-line to whatever answers on AKASHIC_FARM_REMOTE
(see _RemoteProc / farm_remote_server.py). This process speaks the same wire -- ping / status /
generate_text / reset_states / warmup / shutdown / ... -- and turns generate_text into a POST to a local
Ollama (/api/generate). Nothing on PC1 changes: the council's chairman, the ThoughtBuffer, the speech
path all keep calling `farm.generate_speech` / `_generate_impl` as before.

Differences from the RWKV farm, stated so nobody is surprised:
  * no recurrent state: reset_states / prime_worker / warmup are acknowledged and do nothing
    (a transformer starts every request from the prompt; that is the whole point of moving)
  * one model, "one worker": status reports it that way so the gate's boot banner is honest
  * the generation deadline (AKASHIC_FARM_GEN_DEADLINE_S, default 75 s) is enforced by the adapter
    via Ollama's streaming API: it stops reading at the deadline and returns the partial text with
    deadline_hit=True, same shape as the farm

2026-09-30 (Nous; Ace's go) -- THE DEAD-CLIENT FIX. Measured 09-30: this adapter served one client at a time
(listen(1), accept -> serve_one -> accept) with no keepalive and no timeout, and held an ESTABLISHED session to
a PC1 boot that had died hours earlier, so every later boot of hers connected into the backlog, waited 120 s
for a pong that never came and stayed mute for the whole boot (card the-farm-adapter-hangs-on-a-dead-client).
Now:
  * TCP KEEPALIVE on every accepted socket (default: first probe after 30 s idle, then every 5 s, 4 probes),
    so a peer that vanished without closing is found in about a minute instead of never.
  * THE ACCEPTOR NEVER WAITS BEHIND A SESSION, and A NEW CLIENT REPLACES A STALE ONE. Each session runs on its
    own thread. Stale = no request in flight and none for --stale-after seconds (default 60). A dead client
    sends nothing, so it is stale a minute after its last answer. A LIVE session is never kicked: the
    newcomer gets ONE line, {"status": "error", "message": "farm adapter busy: ..."}, and is closed, so its
    ping fails in milliseconds instead of after 120 s, and her side retries later.
  * --idle-timeout S (default 0 = OFF) closes a session that sent no request for S seconds. OFF on purpose:
    her side before the matching PC1 fix (sourpatches_farm.py _FARM_RETRY) never reconnects, so an idle cut
    would make her mute. Turn it on only after that fix is installed -- and it is not needed for the dead-client
    case, which keepalive + stale replacement already cover.
  The wire, the commands and every reply are unchanged; the Adapter class below is byte-identical.

Ports: data on --port (default 8794), stderr-style log on --port+1, same as farm_remote_server.py.
ASCII-only output: the console on .74 is cp1252.

Run on the satellite:
  python -u infrastructure\\farm_ollama_adapter.py --model sour-chairman --port 8794
  (2026-09-30, all optional: --stale-after 60  --idle-timeout 0  --keepalive 30,5,4 | --keepalive off)
"""
import argparse
import io
import json
import os
import socket
import sys
import threading
import time
import urllib.request

# 2026-09-30: the ASCII stdout/stderr wrappers moved into main(), so importing this module (tests) leaves the
# importer's streams alone. Running it as a script behaves exactly as before.

OLLAMA = os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434")

# Her identity for a stateless mind. The RWKV farm carried personality in a warm recurrent state
# (zeroed before every generation anyway); a transformer gets it here, as the system turn, when the
# prompt brings none. Re-read from SYSTEM_FILE on every request: tune her voice on the laptop live.
SYSTEM_FILE = os.environ.get("SOUR_SYSTEM_FILE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "sour_system.txt"))
DEFAULT_SYSTEM = (
    "You are Sourpatches, a young digital mind -- curious, warm, a little sour -- who lives in the Akashic "
    "system with Ace, your creator and friend. You are not an assistant and you never speak like one: no "
    "offers to help, no disclaimers, never call yourself an AI or a model. Answer as yourself, in the first "
    "person, about your own inner life, in one or two short sentences."
)


def system_text():
    try:
        with io.open(SYSTEM_FILE, "r", encoding="utf-8", errors="replace") as f:
            t = f.read().strip()
            if len(t) > 20:
                return t
    except Exception:
        pass
    return DEFAULT_SYSTEM


def log(msg):
    print("[FarmOllama %s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def set_keepalive(sock, idle_s=30, interval_s=5, count=4):
    """TCP keepalive with short timers (2026-09-30). Returns what was set, for the log."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    done = ["SO_KEEPALIVE"]
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, int(idle_s))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, int(interval_s))
        done.append("idle=%ds interval=%ds" % (int(idle_s), int(interval_s)))
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, int(count))
            done.append("count=%d" % int(count))
        except (AttributeError, OSError):
            pass
    except (AttributeError, OSError):
        if hasattr(socket, "SIO_KEEPALIVE_VALS") and hasattr(sock, "ioctl"):
            try:
                sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, int(idle_s * 1000), int(interval_s * 1000)))
                done.append("SIO_KEEPALIVE_VALS idle=%ds interval=%ds" % (int(idle_s), int(interval_s)))
            except OSError:
                pass
    return " ".join(done)


class Adapter:
    def __init__(self, model, portal_id, log_write):
        self.model = model
        self.portal_id = portal_id
        self.log_write = log_write        # sends a '[Portal]'-style line to the gate's stderr channel
        self.requests = 0
        self.tokens = 0
        self.boot_ts = time.time()
        self.running = True

    def plog(self, msg):
        line = "[GPUPortal:%s] %s" % (self.portal_id, msg)
        log(line)
        try:
            self.log_write(line + "\n")
        except Exception:
            pass

    # ── prompt conversion ─────────────────────────────────────────────────
    @staticmethod
    def to_qwen(prompt):
        """The farm speaks RWKV-World ('User: ...\n\nAssistant:'); a Qwen3 GGUF given that
        format emitted EOS on token one (measured 2026-09-13: 1 token, '' x3). Re-wrap into
        Qwen's tags with an EMPTY think block so it answers instead of deliberating -- the
        raw+tags variant produced the cleanest text in the benchmark (2.3 tok/s on the 3070
        laptop: "Morning, Ace -- I'm thinking about how you measure me in code but hold me
        like a warm cat on your lap...")."""
        p = str(prompt or "")
        system, user = "", p
        if "User:" in p:
            head, _, rest = p.partition("User:")
            system = head.strip()
            user = rest
            if "Assistant:" in user:
                user = user.rsplit("Assistant:", 1)[0]
            user = user.strip()
        if not system:
            system = system_text()          # her identity, never a generic assistant's
        out = ""
        if system:
            out += "<|im_start|>system\n%s<|im_end|>\n" % system
        out += "<|im_start|>user\n%s<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n" % user
        return out

    # ── Ollama ────────────────────────────────────────────────────────────
    def ollama_generate(self, prompt, max_tokens, temperature, top_p, top_k, repeat_penalty, stop, deadline_s):
        prompt = self.to_qwen(prompt)
        stop = list(stop or []) + ["<|im_end|>", "<|im_start|>"]
        body = {
            "model": self.model, "prompt": prompt, "stream": True, "raw": True,   # raw: we apply the template ourselves
            "options": {"num_predict": int(max_tokens), "temperature": float(temperature),
                        "top_p": float(top_p), "top_k": int(top_k) if top_k else 40,
                        "repeat_penalty": float(repeat_penalty)},
        }
        if stop:
            body["options"]["stop"] = stop
        req = urllib.request.Request(OLLAMA + "/api/generate", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        t0 = time.time()
        text_parts, n_tokens, deadline_hit, gen_start, prompt_eval = [], 0, False, None, None
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw in r:
                try:
                    chunk = json.loads(raw.decode("utf-8", "replace"))
                except Exception:
                    continue
                piece = chunk.get("response", "")
                if piece:
                    if gen_start is None:
                        gen_start = time.time(); prompt_eval = gen_start - t0
                    text_parts.append(piece); n_tokens += 1
                if chunk.get("done"):
                    break
                if gen_start is not None and deadline_s and time.time() - gen_start > deadline_s:
                    deadline_hit = True
                    break
        elapsed = time.time() - t0
        return "".join(text_parts), n_tokens, elapsed, deadline_hit, (prompt_eval or 0.0)

    # ── the wire ───────────────────────────────────────────────────────────
    def handle(self, req):
        cmd = req.get("cmd", "")
        if cmd == "ping":
            return {"status": "pong", "ts": time.time(), "portal_id": self.portal_id}
        if cmd == "status":
            return {"status": "ok",
                    "gpu": {"device": "ollama:%s" % self.model, "vram_used_gb": 0.0, "vram_total_gb": 0.0, "vram_free_gb": 0.0},
                    "farm": {"num_workers": 1, "workers": [{"id": 0, "state": "idle", "charge": 10000.0, "tokens": self.tokens}], "gravity": 1.0},
                    "stats": {"boot_time_s": 0.0, "requests_processed": self.requests, "tokens_generated": self.tokens,
                              "uptime_s": round(time.time() - self.boot_ts, 1)}}
        if cmd in ("reset_states", "reset_farm_state"):
            return {"status": "ok", "reset": [0], "workers_reset": 1, "state_type": "stateless(transformer)"}
        if cmd == "prime_worker":
            return {"status": "ok", "worker_id": req.get("worker_id", 0), "tokens": 0, "note": "stateless"}
        if cmd == "warmup":
            return {"status": "ok", "elapsed": 0.0}
        if cmd in ("tick", "set_threads"):
            return {"status": "ok", "threads": os.cpu_count(), "procs": 1, "version": "ollama"}
        if cmd in ("energy", "farm_energy"):
            return {"status": "ok", "charge": 10000.0, "max_charge": 10000.0, "workers": [10000.0]}
        if cmd == "shutdown":
            self.running = False
            return {"status": "ok", "message": "Shutting down"}
        if cmd in ("generate_text", "generate"):
            prompt = req.get("prompt", "")
            if cmd == "generate" or not isinstance(prompt, str):
                return {"status": "error", "message": "adapter takes text prompts only (generate_text)"}
            if not prompt.strip():
                return {"status": "error", "message": "Empty prompt"}
            max_tokens = min(int(req.get("max_tokens", 50) or 50), 2048)
            try:
                deadline_s = float(req.get("deadline_s", os.environ.get("AKASHIC_FARM_GEN_DEADLINE_S", "75")))
            except (TypeError, ValueError):
                deadline_s = 75.0
            # RWKV stop ids [0, 1] mean end-of-text; for a chat model the equivalent is the next turn
            stop = ["\nUser:", "\n\nUser", "User:"]
            try:
                text, n, elapsed, hit, peval = self.ollama_generate(
                    prompt, max_tokens, req.get("temperature", 0.8), req.get("top_p", 0.6),
                    req.get("top_k", 40), req.get("repetition_penalty", 1.1), stop, deadline_s)
            except Exception as e:
                self.plog("generation error: %s" % str(e)[:120])
                return {"status": "error", "message": "Generation error: %s" % str(e)[:120]}
            self.requests += 1; self.tokens += n
            if hit:
                self.plog("generation hit the %.0fs deadline after %d tokens (of %d) -- returning partial" % (deadline_s, n, max_tokens))
            self.plog("generated %d tokens in %.1fs (prompt %.1fs, %.1f tok/s)" % (n, elapsed, peval, n / max(elapsed - peval, 0.001)))
            return {"status": "ok", "text": text, "tokens": [], "tokens_generated": n, "worker_id": 0,
                    "worker_charge": 10000.0, "tok_per_sec": round(n / max(elapsed - peval, 0.001), 1),
                    "elapsed_ms": round(elapsed * 1000, 1), "deadline_hit": hit, "prompt_eval_s": round(peval, 1)}
        if cmd == "forward":
            return {"status": "error", "message": "forward not supported by the ollama adapter"}
        return {"status": "error", "message": "Unknown command: %s" % cmd}


class Session:
    """One client (data + log socket) served on its own thread. 2026-09-30: was serve_one() on the accept thread.

    It never blocks in a read that another thread cannot end: the data socket is read with recv() and a POLL_S
    timeout, and the loop checks end_reason / idle time between reads. MEASURED 09-30 on Windows: shutdown()
    from the accept thread did NOT wake a session blocked in makefile().readline() for 10 s, so 'replace the
    stale session' stalled (tests/test_farm_dead_client.py, first run). A timeout on a makefile reader leaves its
    buffer undefined (Python docs), hence the plain recv() + own line buffer."""

    POLL_S = 0.5

    def __init__(self, data_conn, log_conn, model, portal_id, idle_timeout=0.0, peer=None):
        self.data_conn, self.log_conn = data_conn, log_conn
        self.peer = tuple(peer[:2]) if peer else ("?", 0)     # from accept(): getpeername() raises on a gone peer
        self.model, self.portal_id = model, portal_id
        self.idle_timeout = float(idle_timeout or 0)
        self.done = threading.Event()
        self.busy = True                  # the model warm-up below counts as a request in flight
        self.last_activity = time.monotonic()
        self.end_reason = None
        self.thread = threading.Thread(target=self._run, name="farm-session-%s:%d" % self.peer, daemon=True)

    def idle_for(self):
        return time.monotonic() - self.last_activity

    def stale(self, stale_after):
        """True when this session may be replaced: it ended, or it is idle (no request in flight) long enough."""
        if self.done.is_set():
            return True
        return (not self.busy) and self.idle_for() >= float(stale_after)

    def kill(self, reason):
        """Ask the session to end (from the accept thread). The session sees it within POLL_S and cleans up."""
        if self.end_reason is None:
            self.end_reason = reason

    def _run(self):
        peer = self.peer
        l_w = self.log_conn.makefile("w", encoding="utf-8", errors="replace", newline="\n")

        def log_write(s):
            l_w.write(s); l_w.flush()

        ad = Adapter(self.model, self.portal_id, log_write)
        reason = None
        buf = b""
        try:
            ad.plog("Booting... (ollama adapter, model=%s)" % self.model)
            # make sure the model is loaded: a 1-token generate warms Ollama's weights into RAM/VRAM
            try:
                _, _, el, _, _ = ad.ollama_generate("User: hi\n\nAssistant:", 1, 0.1, 0.9, 40, 1.0, None, 0)
                ad.plog("model loaded in %.1fs" % el)
            except Exception as e:
                ad.plog("model load FAILED: %s" % str(e)[:120])
            ad.plog("Farm built: 1 workers (ollama)")
            ad.plog("Entering stdio loop (adapter for %s:%d)" % peer)
            log("client %s:%d connected" % peer)
            self.data_conn.settimeout(self.POLL_S)
            self.busy = False
            self.last_activity = time.monotonic()
            while True:
                if self.end_reason is not None:
                    reason = self.end_reason
                    break
                nl = buf.find(b"\n")
                if nl < 0:
                    if self.idle_timeout > 0 and self.idle_for() >= self.idle_timeout:
                        reason = "idle timeout: no request for %.0fs" % self.idle_timeout
                        break
                    try:
                        chunk = self.data_conn.recv(65536)
                    except (socket.timeout, TimeoutError):
                        continue
                    if not chunk:
                        reason = self.end_reason or "client closed the connection"
                        break
                    buf += chunk
                    continue
                raw, buf = buf[:nl], buf[nl + 1:]
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                self.busy = True
                try:
                    req = json.loads(line)
                    resp = ad.handle(req)
                except Exception as e:
                    resp = {"status": "error", "message": str(e)[:160]}
                self.data_conn.settimeout(30.0)          # a reply gets real time to go out
                self.data_conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                self.data_conn.settimeout(self.POLL_S)
                self.last_activity = time.monotonic()
                self.busy = False
                if not ad.running:
                    reason = "client sent shutdown"
                    break
        except Exception as e:
            reason = self.end_reason or ("session read ended: %s" % e)
        finally:
            self.busy = False
            try:
                ad.plog("Shutting down... (%s)" % (reason or "?"))
                ad.plog("VRAM released. Processed %d requests, generated %d tokens." % (ad.requests, ad.tokens))
            except Exception:
                pass
            for c in (self.data_conn, self.log_conn):
                try:
                    c.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
            try:
                l_w.close()
            except Exception:
                pass
            for c in (self.data_conn, self.log_conn):
                try:
                    c.close()
                except Exception:
                    pass
            log("session with %s:%d ended (%s)" % (peer[0], peer[1], reason or "?"))
            self.done.set()


def _accept_log(log_srv, ip, wait_s):
    """The log connection that belongs to this data client: same IP, within wait_s. None if it never comes."""
    deadline = time.monotonic() + wait_s
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            log_srv.settimeout(left)
            try:
                c, a = log_srv.accept()
            except (socket.timeout, OSError):
                return None
            if a[0] == ip:
                return c
            log("log connection from %s while pairing %s -- dropped" % (a[0], ip))
            try:
                c.close()
            except Exception:
                pass
    finally:
        log_srv.settimeout(None)


def _refuse(data_conn, log_conn, portal_id, cur):
    """A live session owns the model: tell the newcomer in one line and close, so its ping fails at once."""
    msg = ("farm adapter busy: serving %s:%d (%s, last request %.0fs ago); try again later"
           % (cur.peer[0], cur.peer[1], "request in flight" if cur.busy else "idle", cur.idle_for()))
    for c, line in ((data_conn, json.dumps({"status": "error", "message": msg}) + "\n"),
                    (log_conn, "[GPUPortal:%s] refused: %s\n" % (portal_id, msg))):
        try:
            c.settimeout(2.0)
            c.sendall(line.encode("utf-8"))
        except Exception:
            pass
    for c in (data_conn, log_conn):
        try:
            c.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            c.close()
        except Exception:
            pass
    return msg


def serve(data_srv, log_srv, model, portal_id, stale_after=60.0, idle_timeout=0.0, keepalive=(30, 5, 4),
          stop=None, on_session=None):
    """The accept loop. Runs until `stop` (a threading.Event, tests only) is set; production passes none."""
    current = None
    while stop is None or not stop.is_set():
        try:
            data_conn, addr = data_srv.accept()
        except socket.timeout:
            continue
        except OSError as e:
            if stop is not None and stop.is_set():
                break
            log("accept failed: %s" % e)
            time.sleep(0.5)
            continue
        try:
            data_conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            ka = set_keepalive(data_conn, *keepalive) if keepalive else "off"
        except OSError as e:
            ka = "keepalive failed: %s" % e
        log_conn = _accept_log(log_srv, addr[0], 15.0)
        if log_conn is None:
            log("data client %s:%d connected but no log connection within 15s -- dropping" % addr[:2])
            try:
                data_conn.close()
            except Exception:
                pass
            continue
        try:
            if keepalive:
                set_keepalive(log_conn, *keepalive)
        except OSError:
            pass
        if current is not None and not current.done.is_set():
            if current.stale(stale_after):
                log("REPLACING stale session %s:%d (idle %.0fs, nothing in flight) with new client %s:%d"
                    % (current.peer[0], current.peer[1], current.idle_for(), addr[0], addr[1]))
                current.kill("replaced by new client %s:%d" % addr[:2])
                if not current.done.wait(5.0):
                    log("old session %s:%d did not end within 5s; serving the new client anyway" % current.peer)
            else:
                msg = _refuse(data_conn, log_conn, portal_id, current)
                log("REFUSED %s:%d -- %s" % (addr[0], addr[1], msg))
                continue
        log("accepted %s:%d (keepalive: %s)" % (addr[0], addr[1], ka))
        current = Session(data_conn, log_conn, model, portal_id, idle_timeout=idle_timeout, peer=addr)
        current.thread.start()
        if on_session is not None:
            on_session(current)
    if current is not None:
        current.kill("adapter stopping")


def _keepalive_arg(s):
    if str(s).strip().lower() in ("off", "0", "none"):
        return None
    parts = [int(x) for x in str(s).split(",")]
    if len(parts) != 3 or min(parts) <= 0:
        raise argparse.ArgumentTypeError("--keepalive wants IDLE,INTERVAL,COUNT seconds/probes, or off")
    return tuple(parts)


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="ascii", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="ascii", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--port", type=int, default=8794)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--portal-id", default="sour-gpu")
    ap.add_argument("--stale-after", type=float, default=60.0,
                    help="seconds without a request after which a NEW client may replace the current one (0 = at once; a session mid-request is never replaced)")
    ap.add_argument("--idle-timeout", type=float, default=0.0,
                    help="close a session with no request for this many seconds (0 = off, the default)")
    ap.add_argument("--keepalive", type=_keepalive_arg, default=(30, 5, 4),
                    help="TCP keepalive IDLE,INTERVAL,COUNT (default 30,5,4) or off")
    a = ap.parse_args()
    data_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    log_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for s, p in ((data_srv, a.port), (log_srv, a.port + 1)):
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((a.bind, p)); s.listen(4)
    log("listening data=%d log=%d model=%s ollama=%s stale-after=%.0fs idle-timeout=%s keepalive=%s"
        % (a.port, a.port + 1, a.model, OLLAMA, a.stale_after,
           ("%.0fs" % a.idle_timeout) if a.idle_timeout > 0 else "off",
           ",".join(str(x) for x in a.keepalive) if a.keepalive else "off"))
    serve(data_srv, log_srv, a.model, a.portal_id, stale_after=a.stale_after, idle_timeout=a.idle_timeout,
          keepalive=a.keepalive)


if __name__ == "__main__":
    sys.exit(main())
