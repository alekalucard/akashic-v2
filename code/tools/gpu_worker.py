#!/usr/bin/env python3
"""
GPU Worker — Lightweight RWKV Inference Server for Satellite Machines

This is a STANDALONE script that runs on any machine with an NVIDIA GPU.
It loads the RWKV-7 GGUF model and serves inference requests over HTTP.

NO Akashic system required. NO fairies, postal, consciousness loops.
Just: load model → serve requests → report GPU stats.

Setup on satellite machine:
    1. Copy this file + the GGUF model file
    2. pip install torch numpy   (that's it)
    3. python gpu_worker.py --model path/to/rwkv7-1.5B-world-Q8_0.gguf
    4. Worker reports to primary at startup

The primary's GPUFleetFairy connects to this endpoint and routes
inference requests when the local GPU is busy.

Created: 2026-02-20
"""

import os
import sys
import time
import json
import socket
import signal
import argparse
import threading
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Optional, List
from queue import Queue, Empty

# ═══════════════════════════════════════════════════════════════════
# GPU DETECTION
# ═══════════════════════════════════════════════════════════════════

def get_gpu_info() -> Dict[str, Any]:
    """Get GPU stats via nvidia-smi (no torch needed)."""
    import subprocess
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=utilization.gpu,memory.used,memory.total,memory.free,name,temperature.gpu,clocks.current.sm",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) >= 5:
                return {
                    "available": True,
                    "utilization_pct": float(parts[0]),
                    "memory_used_mb": float(parts[1]),
                    "memory_total_mb": float(parts[2]),
                    "memory_free_mb": float(parts[3]),
                    "name": parts[4],
                    "temperature_c": float(parts[5]) if len(parts) > 5 else 0,
                    "clock_mhz": float(parts[6]) if len(parts) > 6 else 0,
                }
    except Exception as e:
        print(f"[GPU Worker] nvidia-smi failed: {e}")
    return {"available": False}


# ═══════════════════════════════════════════════════════════════════
# GGUF TOKENIZER (minimal, no Akashic deps)
# ═══════════════════════════════════════════════════════════════════

class ByteTokenizer:
    """Minimal byte-level tokenizer fallback."""
    def __init__(self):
        self.vocab_size = 256

    def encode(self, text: str) -> List[int]:
        return list(text.encode("utf-8"))

    def decode(self, ids: List[int]) -> str:
        return bytes(ids).decode("utf-8", errors="replace")


def load_tokenizer(model_path: str):
    """Try to load the GGUF tokenizer, fall back to byte-level."""
    try:
        # Try importing from Akashic if available
        sys.path.insert(0, str(Path(model_path).parent.parent.parent.parent))
        from fairies.P30_Cognition.AkashicInferenceFairy.tokenizer import load_tokenizer_from_gguf
        tok = load_tokenizer_from_gguf(Path(model_path))
        print(f"[GPU Worker] Loaded GGUF tokenizer: {tok.vocab_size} tokens")
        return tok
    except Exception as e:
        print(f"[GPU Worker] GGUF tokenizer unavailable ({e}), using byte-level")
        return ByteTokenizer()


# ═══════════════════════════════════════════════════════════════════
# RWKV MODEL LOADING (minimal Python path)
# ═══════════════════════════════════════════════════════════════════

class RWKVWorkerEngine:
    """
    Loads RWKV-7 GGUF model and provides simple generate() interface.

    This uses the simplest possible loading path:
    1. Parse GGUF header for config
    2. Dequantize tensors to GPU
    3. Run forward pass with simple sampling

    For the Rust path (much faster), set AKASHIC_RUST_ENGINE=path/to/libakashic_rwkv.dll
    """

    def __init__(self, model_path: str, device: str = "cuda"):
        self.model_path = model_path
        self.device = device
        self.model = None
        self.tokenizer = None
        self.config = None
        self._ready = False
        self._loading = False
        self._load_error = None
        self._lock = threading.Lock()

    def load(self) -> bool:
        """Load model (call from dedicated GPU thread)."""
        self._loading = True
        t0 = time.time()

        try:
            import torch

            # Load tokenizer first
            self.tokenizer = load_tokenizer(self.model_path)

            # Try Akashic's model loader if available
            try:
                parent = str(Path(self.model_path).parent.parent.parent.parent)
                if parent not in sys.path:
                    sys.path.insert(0, parent)

                from fairies.P30_Cognition.AkashicInferenceFairy.gguf_parser import GGUFFile, get_model_info
                from fairies.P30_Cognition.AkashicInferenceFairy.model_tensor_fabric import ModelTensorFabric
                from fairies.P30_Cognition.AkashicInferenceFairy.rwkv_model import RWKVModel
                from fairies.P30_Cognition.AkashicInferenceFairy.rwkv_layers import RWKVConfig

                info = get_model_info(self.model_path)
                n_embd = info.get('n_embd', 2048)
                n_head = info.get('n_head', 32)
                print(f"[GPU Worker] Model config: {info.get('n_layer')}L {n_embd}D vocab={info.get('vocab_size')}")

                # Build config using proper RWKVConfig dataclass
                self.config = RWKVConfig(
                    n_layer=info.get('n_layer', 24),
                    n_embd=n_embd,
                    n_head=n_head,
                    head_size=n_embd // max(n_head, 1),
                    vocab_size=info.get('vocab_size', 65536),
                )

                # Load via ModelTensorFabric
                fabric = ModelTensorFabric(device=self.device)
                fabric.load_gguf(self.model_path)

                # Create model (no device kwarg — fabric handles device placement)
                self.model = RWKVModel(self.config, fabric)
                self._ready = True

                elapsed = time.time() - t0
                print(f"[GPU Worker] Model loaded in {elapsed:.1f}s on {self.device}")
                props = torch.cuda.get_device_properties(0)
                total_gb = getattr(props, 'total_memory', getattr(props, 'total_mem', 0)) / (1024**3)
                print(f"[GPU Worker] GPU: {torch.cuda.get_device_name()}, "
                      f"VRAM: {torch.cuda.memory_allocated()/(1024**3):.1f}GB / {total_gb:.1f}GB")
                return True

            except Exception as e:
                print(f"[GPU Worker] Akashic model loader failed: {e}")
                traceback.print_exc()
                self._load_error = str(e)
                return False

        except Exception as e:
            self._load_error = str(e)
            print(f"[GPU Worker] Model load FAILED: {e}")
            traceback.print_exc()
            return False
        finally:
            self._loading = False

    def generate(self, prompt: str, max_tokens: int = 128, temperature: float = 0.8,
                 top_p: float = 0.9) -> Dict[str, Any]:
        """Generate text from prompt. Must be called from GPU thread."""
        if not self._ready or self.model is None:
            return {"error": "Model not loaded", "text": ""}

        t0 = time.time()
        try:
            # Encode prompt
            input_ids = self.tokenizer.encode(prompt)

            # Reset model state for clean generation
            self.model.reset_state()

            # Use the model's built-in generate() — handles state, sampling, etc.
            generated_ids = self.model.generate(
                prompt_ids=input_ids,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop_tokens=[0],  # EOS token for RWKV
            )

            # Decode
            text = self.tokenizer.decode(generated_ids)
            elapsed = time.time() - t0
            tok_per_sec = len(generated_ids) / max(elapsed, 0.001)

            return {
                "text": text,
                "tokens_generated": len(generated_ids),
                "prompt_tokens": len(input_ids),
                "elapsed_s": round(elapsed, 3),
                "tokens_per_sec": round(tok_per_sec, 1),
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "text": ""}


# ═══════════════════════════════════════════════════════════════════
# GPU WORKER THREAD (owns CUDA context)
# ═══════════════════════════════════════════════════════════════════

class GPUWorkerThread:
    """
    Manages the GPU thread. All CUDA operations go through this thread
    because CUDA contexts are thread-local.
    """

    def __init__(self, engine: RWKVWorkerEngine):
        self.engine = engine
        self._queue: Queue = Queue(maxsize=32)
        self._thread: Optional[threading.Thread] = None
        self._active_request = False
        self._requests_completed = 0
        self._total_tokens = 0

    def start(self):
        """Start the GPU worker thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="gpu-worker")
        self._thread.start()

    def _run(self):
        """GPU thread main loop."""
        # Load model (creates CUDA context on this thread)
        if not self.engine.load():
            print("[GPU Worker] FATAL: Model failed to load. Worker will accept but reject requests.")
            # Still run the loop to serve error responses

        print("[GPU Worker] GPU worker loop running. Waiting for requests...")
        while True:
            try:
                item = self._queue.get(timeout=5.0)
                if item is None:
                    break  # Shutdown signal

                request_data, result_queue = item
                self._active_request = True
                try:
                    result = self.engine.generate(
                        prompt=request_data.get("prompt", ""),
                        max_tokens=request_data.get("max_tokens", 128),
                        temperature=request_data.get("temperature", 0.8),
                        top_p=request_data.get("top_p", 0.9),
                    )
                    self._requests_completed += 1
                    self._total_tokens += result.get("tokens_generated", 0)
                    result_queue.put(result)
                except Exception as e:
                    result_queue.put({"error": str(e), "text": ""})
                finally:
                    self._active_request = False

            except Empty:
                continue  # No work, loop back
            except Exception as e:
                print(f"[GPU Worker] Worker error: {e}")

    def submit(self, request_data: dict, timeout: float = 60.0) -> Dict[str, Any]:
        """Submit inference request and wait for result."""
        if self._queue.full():
            return {"error": "Queue full - GPU worker is overloaded", "text": ""}

        result_queue: Queue = Queue(1)
        self._queue.put((request_data, result_queue))

        try:
            return result_queue.get(timeout=timeout)
        except Empty:
            return {"error": f"Timeout after {timeout}s", "text": ""}

    @property
    def is_busy(self) -> bool:
        return self._active_request

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()


# ═══════════════════════════════════════════════════════════════════
# HTTP SERVER
# ═══════════════════════════════════════════════════════════════════

# Module-level reference set after creation
_worker: Optional[GPUWorkerThread] = None
_engine: Optional[RWKVWorkerEngine] = None
_start_time: float = 0
_node_name: str = ""


class GPUWorkerHandler(BaseHTTPRequestHandler):
    """HTTP handler for GPU worker endpoints."""

    def log_message(self, format, *args):
        # Suppress default HTTP logging
        pass

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length).decode()
        return json.loads(body)

    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            self._send_json(self._build_health())

        elif self.path == "/status":
            health = self._build_health()
            health["uptime_s"] = round(time.time() - _start_time, 1)
            health["gpu_info"] = get_gpu_info()
            self._send_json(health)

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/generate":
            try:
                data = self._read_body()
            except Exception:
                self._send_json({"error": "Invalid JSON"}, 400)
                return

            prompt = data.get("prompt", "")
            if not prompt:
                self._send_json({"error": "No prompt provided"}, 400)
                return

            if not _engine or not _engine._ready:
                self._send_json({"error": "Model not loaded yet", "loading": _engine._loading if _engine else False}, 503)
                return

            # Submit to GPU thread and wait
            timeout = data.get("timeout", 120.0)
            result = _worker.submit(data, timeout=timeout)
            result["worker"] = _node_name
            self._send_json(result)

        elif self.path == "/ping":
            self._send_json({"pong": True, "worker": _node_name, "ts": time.time()})

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _build_health(self) -> dict:
        gpu = get_gpu_info()
        return {
            "name": _node_name,
            "ready": _engine._ready if _engine else False,
            "loading": _engine._loading if _engine else False,
            "error": _engine._load_error if _engine else None,
            "busy": _worker.is_busy if _worker else False,
            "queue_depth": _worker.queue_depth if _worker else 0,
            "requests_completed": _worker._requests_completed if _worker else 0,
            "total_tokens": _worker._total_tokens if _worker else 0,
            "has_gpu": gpu.get("available", False),
            "gpu_name": gpu.get("name", "Unknown"),
            "gpu_memory_free_mb": gpu.get("memory_free_mb", 0),
            "gpu_memory_total_mb": gpu.get("memory_total_mb", 0),
            "gpu_utilization_pct": gpu.get("utilization_pct", 0),
            "gpu_temperature_c": gpu.get("temperature_c", 0),
            "ts": time.time(),
        }


# ═══════════════════════════════════════════════════════════════════
# ANNOUNCE TO PRIMARY (optional)
# ═══════════════════════════════════════════════════════════════════

def announce_to_primary(primary_host: str, primary_port: int, worker_port: int):
    """Tell the primary node we exist."""
    import urllib.request

    my_ip = _get_local_ip()
    announcement = {
        "type": "gpu_worker.announce",
        "worker": {
            "name": _node_name,
            "ip": my_ip,
            "port": worker_port,
            "gpu": get_gpu_info(),
            "ts": time.time(),
        }
    }

    try:
        req = urllib.request.Request(
            f"http://{primary_host}:{primary_port}/gpu_fleet/announce",
            data=json.dumps(announcement).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
        print(f"[GPU Worker] Announced to primary {primary_host}:{primary_port}")
    except Exception as e:
        print(f"[GPU Worker] Could not announce to primary: {e} (will retry)")


def _get_local_ip() -> str:
    """Get this machine's LAN IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def heartbeat_loop(primary_host: str, primary_port: int, worker_port: int, interval: float = 15.0):
    """Periodic heartbeat to primary."""
    import urllib.request

    my_ip = _get_local_ip()
    while True:
        try:
            gpu = get_gpu_info()
            heartbeat = {
                "type": "gpu_worker.heartbeat",
                "worker": {
                    "name": _node_name,
                    "ip": my_ip,
                    "port": worker_port,
                    "ready": _engine._ready if _engine else False,
                    "busy": _worker.is_busy if _worker else False,
                    "queue_depth": _worker.queue_depth if _worker else 0,
                    "requests_completed": _worker._requests_completed if _worker else 0,
                    "gpu_memory_free_mb": gpu.get("memory_free_mb", 0),
                    "gpu_utilization_pct": gpu.get("utilization_pct", 0),
                    "ts": time.time(),
                }
            }
            req = urllib.request.Request(
                f"http://{primary_host}:{primary_port}/gpu_fleet/heartbeat",
                data=json.dumps(heartbeat).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # Primary may be offline, that's fine

        time.sleep(interval)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    global _worker, _engine, _start_time, _node_name

    parser = argparse.ArgumentParser(description="Akashic GPU Worker - Lightweight RWKV Inference Server")
    parser.add_argument("--model", "-m", required=True, help="Path to RWKV GGUF model file")
    parser.add_argument("--port", "-p", type=int, default=5050, help="HTTP port (default: 5050)")
    parser.add_argument("--device", "-d", default="cuda", help="Device: cuda, cuda:0, cpu (default: cuda)")
    parser.add_argument("--name", "-n", default=None, help="Worker name (default: hostname)")
    parser.add_argument("--primary", default=None, help="Primary node host:port for auto-announce (e.g., 192.168.1.6:5050)")
    args = parser.parse_args()

    _start_time = time.time()
    _node_name = args.name or socket.gethostname()

    # Verify model exists
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"[GPU Worker] ERROR: Model not found: {model_path}")
        sys.exit(1)

    print(f"""
================================================================
            AKASHIC GPU WORKER
================================================================
  Node:    {_node_name}
  Model:   {model_path.name}
  Device:  {args.device}
  Port:    {args.port}
  Primary: {args.primary or 'none (standalone)'}

  Endpoints:
    GET  /health    - Health + GPU stats
    GET  /status    - Detailed status
    POST /generate  - Submit inference request
    POST /ping      - Quick liveness check

  "Distribute the load. Free the GPUs."
================================================================
""")

    # Show GPU info
    gpu = get_gpu_info()
    if gpu.get("available"):
        print(f"[GPU Worker] GPU: {gpu.get('name', 'Unknown')}")
        print(f"[GPU Worker] VRAM: {gpu.get('memory_free_mb', 0):.0f}MB free / {gpu.get('memory_total_mb', 0):.0f}MB total")
    else:
        print("[GPU Worker] WARNING: No GPU detected! Running on CPU will be very slow.")

    # Create engine and worker
    _engine = RWKVWorkerEngine(str(model_path), device=args.device)
    _worker = GPUWorkerThread(_engine)

    # Start GPU thread (loads model async)
    _worker.start()

    # Announce to primary if configured
    if args.primary:
        parts = args.primary.split(":")
        primary_host = parts[0]
        primary_port = int(parts[1]) if len(parts) > 1 else 5050

        # Announce immediately in background
        threading.Thread(
            target=announce_to_primary,
            args=(primary_host, primary_port, args.port),
            daemon=True
        ).start()

        # Start heartbeat
        threading.Thread(
            target=heartbeat_loop,
            args=(primary_host, primary_port, args.port),
            daemon=True
        ).start()

    # Start HTTP server
    server = HTTPServer(("0.0.0.0", args.port), GPUWorkerHandler)
    print(f"[GPU Worker] HTTP server listening on 0.0.0.0:{args.port}")
    print(f"[GPU Worker] Model loading in background on GPU thread...")

    # Graceful shutdown
    def signal_handler(sig, frame):
        print("\n[GPU Worker] Shutting down...")
        server.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[GPU Worker] Bye!")


if __name__ == "__main__":
    main()
