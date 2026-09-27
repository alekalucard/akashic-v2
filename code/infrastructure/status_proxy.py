"""
Status Proxy — Separate-process HTTP server for GIL-immune /status.

The main server.py process has 160+ Python threads competing for the GIL,
making even trivial HTTP responses take 20-50 seconds. This proxy runs in
a SEPARATE PROCESS with its own GIL, serving /status by reading the
pre-serialized status_cache.json file. Response time: <10ms.

All other requests are proxied to the main server on localhost:5757.

Usage:
    # Started automatically by server.py:
    from infrastructure.status_proxy import start_status_proxy
    proxy_proc = start_status_proxy(proxy_port=5756, backend_port=5757)

    # Or standalone for testing:
    python infrastructure/status_proxy.py --proxy-port 5756 --backend-port 5757
"""

import os
import sys
import json
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor as _ProxyPoolExecutor

# FIX 2026-04-10 (Nous + Ace): Bounded thread pool instead of thread-per-request.
# Same fix as server.py — prevents unbounded Thread-N accumulation.
class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    _pool = _ProxyPoolExecutor(max_workers=4, thread_name_prefix="proxy-http")

    def process_request(self, request, client_address):
        """Use bounded pool instead of thread-per-request."""
        try:
            self._pool.submit(self.process_request_thread, request, client_address)
        except RuntimeError:
            self.process_request_thread(request, client_address)

# Find the status cache file
_HERE = Path(__file__).parent
_PROJECT_ROOT = _HERE.parent
_STATUS_FILE = str(_PROJECT_ROOT / "state" / "status_cache.json")
_BACKEND_PORT = 5758  # Main server internal port (behind proxy)


class StatusProxyHandler(BaseHTTPRequestHandler):
    """Fast HTTP handler — serves /status from file, proxies everything else."""

    # Suppress per-request logging (noisy)
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/status":
            self._serve_status()
        elif self.path == "/health":
            self._serve_health()
        elif self.path == "/events":
            # SSE must go direct to main server — proxy can't stream
            self._proxy_to_backend()
        else:
            self._proxy_to_backend()

    def do_POST(self):
        self._proxy_to_backend()

    def do_OPTIONS(self):
        # CORS preflight
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def _serve_status(self):
        """Serve /status from file — <2ms, no GIL contention."""
        try:
            with open(_STATUS_FILE, 'rb') as f:
                raw = f.read()
            if raw:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(raw)
                return
        except (FileNotFoundError, OSError):
            pass

        # Fallback: proxy to backend
        self._proxy_to_backend()

    def _serve_health(self):
        """Quick health check — just verify the status file exists and is fresh."""
        try:
            stat = os.stat(_STATUS_FILE)
            age = time.time() - stat.st_mtime
            healthy = age < 120  # Status file updated within 2 minutes
            data = json.dumps({
                "healthy": healthy,
                "status_age_seconds": round(age, 1),
                "proxy": True,
            })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data.encode('utf-8'))
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
            pass  # Client disconnected — normal during dashboard refresh
        except Exception as e:
            try:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"healthy": False, "error": str(e)}).encode('utf-8'))
            except Exception:
                pass  # Connection already dead

    def _proxy_to_backend(self):
        """Forward request to main server (internal port).

        Uses 30s timeout. With ThreadingMixIn, even a stuck proxy-to-backend
        call won't block /status or /health responses on other threads.
        """
        try:
            # Build backend URL
            url = f"http://127.0.0.1:{_BACKEND_PORT}{self.path}"

            # Read request body for POST
            body = None
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                body = self.rfile.read(content_length)

            req = urllib.request.Request(url, data=body)
            req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))

            # Forward request with timeout (30s to handle slow backend responses)
            resp = urllib.request.urlopen(req, timeout=30)
            resp_body = resp.read()

            # Send response
            self.send_response(resp.status)
            for key, val in resp.getheaders():
                if key.lower() not in ('transfer-encoding', 'connection'):
                    self.send_header(key, val)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp_body)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Backend unavailable: {e}"}).encode('utf-8'))


def run_proxy(proxy_port: int = 5757, backend_port: int = 5758, bind_addr: str = "127.0.0.1"):
    """Run the status proxy HTTP server.

    Default ports: proxy=5757 (public, GUI connects here), backend=5758 (internal).
    """
    global _BACKEND_PORT
    _BACKEND_PORT = backend_port

    server = ThreadingHTTPServer((bind_addr, proxy_port), StatusProxyHandler)
    print(f"[StatusProxy] Listening on http://{bind_addr}:{proxy_port}")
    print(f"[StatusProxy] Backend: http://127.0.0.1:{backend_port}")
    print(f"[StatusProxy] Status file: {_STATUS_FILE}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[StatusProxy] Shutting down")
    finally:
        server.server_close()


def start_status_proxy(proxy_port: int = 5757, backend_port: int = 5758, bind_addr: str = "127.0.0.1"):
    """Start the proxy in a subprocess. Returns the Process object.

    Default: proxy on 5757 (public, GIL-immune), backend on 5758 (internal).
    """
    import multiprocessing
    proc = multiprocessing.Process(
        target=run_proxy,
        args=(proxy_port, backend_port, bind_addr),
        daemon=True,
        name="StatusProxy",
    )
    proc.start()
    return proc


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Akashic Status Proxy")
    parser.add_argument("--proxy-port", type=int, default=5757)
    parser.add_argument("--backend-port", type=int, default=5758)
    parser.add_argument("--bind", default="127.0.0.1", help="Bind address")
    args = parser.parse_args()
    run_proxy(args.proxy_port, args.backend_port, args.bind)
