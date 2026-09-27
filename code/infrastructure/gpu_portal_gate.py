"""
GPU Portal Gate — Host-side gate to the GPU inference portal subprocess.

The gate spawns gpu_inference_portal.py as a subprocess and communicates
via stdin/stdout pipes (JSON-per-line protocol). The host process holds
NOTHING heavy — no model weights, no CUDA context, no VRAM. Just a pipe.

From the outside: a 45-byte pipe handle.
From the inside: 3.8GB of compressed neural weight space on CUDA.

Architecture:
    Host (SourpatchesFairy / AkashicInferenceFairy / any fairy)
      │
      ├── .portal weight file on disk (READ-ONLY)
      │
      ├── Spawns subprocess: gpu_inference_portal.py
      │     └── Owns CUDA context, VRAM, BatteryFarm, N workers
      │
      └── This gate: GPUPortalGate
            ├── send() — JSON request → JSON response via pipe
            ├── generate() — text in, text out
            ├── generate_tokens() — tokens in, tokens out
            ├── status() — portal health, VRAM, farm workers
            ├── feed_energy() — recharge the portal battery
            └── gate_status() — local gate stats

Gravity levels:
    α=1.0  →  FP16    (~14.4GB for 7.2B)
    α=1.5  →  INT8    (~7.6GB for 7.2B)
    α=2.0  →  INT4    (~3.8GB for 7.2B)  ← current target
    α=3.0  →  INT2    (~1.9GB for 7.2B)  ← future: collision chamber

Time compression:
    At INT4 (α=2.0), effective FLOPS are amplified 4x.
    12GB VRAM RTX 3060 → comfortably fits 7.2B + overhead.
    Multiple farms share the same GPU weights (class-level cache).
    Wall clock ÷ α gives portal-interior time.

Protocol (JSON over stdin/stdout, newline-delimited):
    → Host sends:  {"cmd": "generate_text", "prompt": "Hello", "max_tokens": 50}
    ← Portal returns: {"status": "ok", "text": "...", "tok_per_sec": 12.5}

    → Host sends:  {"cmd": "status"}
    ← Portal returns: {"status": "ok", "gpu": {...}, "farm": {...}, "battery": {...}}

    → Host sends:  {"cmd": "energy", "amount": 0.3}
    ← Portal returns: {"status": "ok", "battery": {...}}

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import os
import json
import time
import subprocess
import threading
import queue
from pathlib import Path
from typing import Dict, Optional, Any, List


class _RemoteProc:
    """A Popen-shaped handle to a farm hosted by infrastructure/farm_remote_server.py.

    2026-09-12 (Nous + Ace): the farm holds 11 GB of VRAM and ~12 GB of commit on PC1 and pins
    the GPU every spread has to wait behind. With AKASHIC_FARM_REMOTE=host:port the gate connects
    two sockets (data on port, stderr on port+1) instead of spawning; every other line of this
    gate is unchanged because this object exposes exactly what the gate touches on a Popen:
    .stdin .stdout .stderr .poll() .wait() .terminate() .kill() .pid
    """

    def __init__(self, host: str, port: int, connect_timeout: float = 20.0):
        import socket
        self._data = socket.create_connection((host, port), timeout=connect_timeout)
        self._data.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._data.settimeout(None)
        self._log = socket.create_connection((host, port + 1), timeout=connect_timeout)
        self._log.settimeout(None)
        self.stdin = self._data.makefile("w", encoding="utf-8", errors="replace", newline="\n")
        self.stdout = self._data.makefile("r", encoding="utf-8", errors="replace", newline="\n")
        self.stderr = self._log.makefile("r", encoding="utf-8", errors="replace", newline="\n")
        self.pid = -1
        self.returncode = None
        self._closed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        """The server closes the data socket once the farm has exited (after its RWKV save)."""
        t0 = time.time()
        while self.returncode is None:
            if timeout is not None and time.time() - t0 > timeout:
                raise subprocess.TimeoutExpired("remote farm", timeout)
            time.sleep(0.25)
        return self.returncode

    def mark_eof(self):
        if self.returncode is None:
            self.returncode = 0

    def terminate(self):
        self._shut()

    def kill(self):
        self._shut()

    def _shut(self):
        if self._closed:
            return
        self._closed = True
        for f in (self.stdin, self.stdout, self.stderr):
            try:
                f.close()
            except Exception:
                pass
        for sck in (self._data, self._log):
            try:
                sck.close()
            except Exception:
                pass
        if self.returncode is None:
            self.returncode = -15


class GPUPortalGate:
    """Host-side gate to a GPU inference portal subprocess.

    Lightweight — holds no model data, no CUDA context.
    Just a pipe handle and request/response marshalling.
    """

    def __init__(
        self,
        portal_file: str,
        num_workers: int = 4,
        gravity: float = 2.0,
        token_budget: int = 100_000,
        portal_id: str = "gpu-inference",
        python_exe: str = None,
        flops_budget: int = 500_000_000,
        max_charge: float = 20.0,
        recharge_rate: float = 0.01,
        host_port: int = 0,
    ):
        self.portal_file = str(portal_file)
        self.num_workers = num_workers
        self.gravity = gravity
        self.token_budget = token_budget
        self.portal_id = portal_id
        self.python_exe = python_exe or sys.executable
        self.flops_budget = flops_budget
        self.max_charge = max_charge
        self.recharge_rate = recharge_rate
        self.host_port = host_port

        # Process handle
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._is_open = False

        # Stats
        self._requests_sent = 0
        self._orphans = 0   # 2026-09-13: replies still owed to us by the farm after send() timeouts
        self._tokens_generated = 0
        self._errors = 0
        self._opened_at = 0.0
        self._last_response_time = 0.0

        # Stderr reader thread
        self._stderr_thread: Optional[threading.Thread] = None

        # FIX 2026-03-10 (Nous): Persistent stdout reader + queue.
        # Same orphan-thread race fix as PortalGate — see portal_gate.py.
        self._stdout_queue: queue.Queue = queue.Queue()
        self._stdout_reader_thread: Optional[threading.Thread] = None

        # Find the portal script
        self._portal_script = self._find_portal_script()

    def _find_portal_script(self) -> str:
        """Find the gpu_inference_portal.py script."""
        here = Path(__file__).parent
        candidate = here / "gpu_inference_portal.py"
        if candidate.exists():
            return str(candidate)

        # Try project root
        project_root = here.parent
        candidate = project_root / "infrastructure" / "gpu_inference_portal.py"
        if candidate.exists():
            return str(candidate)

        raise FileNotFoundError(
            "Cannot find gpu_inference_portal.py. Expected at: "
            f"{here / 'gpu_inference_portal.py'}"
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def open(self, boot_timeout: float = 120.0) -> bool:
        """Open the gate — spawn the GPU portal subprocess.

        This starts gpu_inference_portal.py which:
        1. Loads the .portal weight file
        2. Uploads weights to CUDA (INT4/INT8 → FP16 on GPU)
        3. Builds BatteryFarm with N workers
        4. Enters the stdio request loop

        The boot can take 15-60s depending on model size and gravity.

        Returns True if portal booted and responded to ping.
        """
        if self._is_open:
            return True

        if not os.path.exists(self.portal_file):
            print(f"[GPUGate] ERROR: Portal file not found: {self.portal_file}")
            return False

        # Build command
        cmd = [
            self.python_exe,
            self._portal_script,
            "--portal", self.portal_file,
            "--workers", str(self.num_workers),
            "--gravity", str(self.gravity),
            "--token-budget", str(self.token_budget),
            "--portal-id", self.portal_id,
            "--flops-budget", str(self.flops_budget),
            "--max-charge", str(self.max_charge),
            "--recharge-rate", str(self.recharge_rate),
        ]
        if self.host_port:
            cmd.extend(["--host-port", str(self.host_port)])

        print(f"[GPUGate] Opening portal '{self.portal_id}'...")
        print(f"[GPUGate] Model: {Path(self.portal_file).name}")
        print(f"[GPUGate] Gravity: a={self.gravity} "
              f"({'INT4' if self.gravity >= 2.0 else 'INT8' if self.gravity >= 1.5 else 'FP16'})")
        print(f"[GPUGate] Workers: {self.num_workers}")
        print(f"[GPUGate] Spawning subprocess...")

        try:
            # Set PYTHONPATH so the portal can import modules
            env = os.environ.copy()
            project_root = str(Path(__file__).parent.parent)
            existing_path = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = project_root + (
                os.pathsep + existing_path if existing_path else "")

            _remote = os.environ.get("AKASHIC_FARM_REMOTE", "").strip()
            if _remote:
                # 2026-09-12: the farm lives on a satellite (see _RemoteProc / farm_remote_server.py)
                _h, _, _p = _remote.rpartition(":")
                print(f"[GPUGate] REMOTE farm at {_h}:{_p} (AKASHIC_FARM_REMOTE) -- not spawning locally")
                self._process = _RemoteProc(_h, int(_p))
            else:
                self._process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    bufsize=1,
                    text=True,
                )
        except Exception as e:
            print(f"[GPUGate] Failed to spawn/connect portal: {e}")
            return False

        # Start stderr reader (captures boot messages from portal)
        self._stderr_thread = threading.Thread(
            target=self._read_stderr, daemon=True
        )
        self._stderr_thread.start()

        # Start persistent stdout reader (drains into queue)
        # FIX 2026-03-10 (Nous): Same fix as portal_gate.py
        self._stdout_queue = queue.Queue()
        self._orphans = 0
        self._stdout_reader_thread = threading.Thread(
            target=self._read_stdout_loop, daemon=True
        )
        self._stdout_reader_thread.start()

        # Wait for portal to boot — GPU upload takes time
        # Give generous timeout for first-time CUDA init + weight upload
        print(f"[GPUGate] Waiting for portal boot "
              f"(timeout={boot_timeout:.0f}s)...")

        ping_result = self.send({"cmd": "ping"}, timeout=boot_timeout)

        if ping_result and ping_result.get("status") == "pong":
            self._is_open = True
            self._opened_at = time.time()

            # Get initial status
            init_status = self.send({"cmd": "status"}, timeout=10.0)
            if init_status and init_status.get("status") == "ok":
                gpu = init_status.get("gpu", {})
                farm = init_status.get("farm", {})
                stats = init_status.get("stats", {})
                print(f"[GPUGate] Portal '{self.portal_id}' ONLINE")
                print(f"[GPUGate] GPU: {gpu.get('device', '?')} — "
                      f"VRAM {gpu.get('vram_used_gb', 0):.1f}/"
                      f"{gpu.get('vram_total_gb', 0):.1f} GB")
                print(f"[GPUGate] Farm: {farm.get('num_workers', 0)} workers")
                print(f"[GPUGate] Boot: {stats.get('boot_time_s', 0):.1f}s")
            else:
                print(f"[GPUGate] Portal '{self.portal_id}' ONLINE "
                      f"(status check failed)")

            return True
        else:
            print(f"[GPUGate] Portal failed to boot: {ping_result}")
            self.close()
            return False

    def close(self):
        """Close the gate — shut down the GPU portal subprocess."""
        if not self._process:
            return

        print(f"[GPUGate] Closing portal '{self.portal_id}'...")

        # Send shutdown command (graceful — releases VRAM)
        try:
            self.send({"cmd": "shutdown"}, timeout=5.0)
        except Exception:
            pass

        # Wait for graceful exit.
        # 2026-09-12 (Nous+Ace): 10 s was not enough. On the 09:42 shutdown the farm logged
        # 'Shutting down...' and was TERMINATED here before its RWKV state save and VRAM
        # release ran (driven directly the same path takes <1 s; inside her shutdown storm,
        # with RAM at 92-98% and 44 state files being written, it did not finish in 10).
        # terminate() throws the save away. Give it a minute and say how long it took.
        _close_wait = 60.0
        try:
            _close_wait = float(os.environ.get("AKASHIC_GATE_CLOSE_WAIT_S", "60"))
        except ValueError:
            pass
        _t_close = time.time()
        try:
            self._process.wait(timeout=_close_wait)
            print(f"[GPUGate] Portal exited on its own in {time.time() - _t_close:.1f}s")
        except subprocess.TimeoutExpired:
            print(f"[GPUGate] Portal didn't exit gracefully in {_close_wait:.0f}s, terminating...")
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.kill()

        self._process = None
        self._is_open = False
        print(f"[GPUGate] Portal '{self.portal_id}' closed. "
              f"Sent {self._requests_sent} requests, "
              f"generated {self._tokens_generated} tokens, "
              f"{self._errors} errors.")

    @property
    def is_open(self) -> bool:
        """Is the portal alive?"""
        if not self._is_open or not self._process:
            return False
        if self._process.poll() is not None:
            self._is_open = False
            return False
        return True

    # ── Communication ─────────────────────────────────────────────────────

    def send(self, request: Dict, timeout: float = 30.0) -> Optional[Dict]:
        """Send a request to the portal and wait for response.

        Args:
            request: JSON-serializable request dict with "cmd" key
            timeout: Seconds to wait for response

        Returns:
            Response dict, or None on failure
        """
        if not self._process or self._process.poll() is not None:
            return None

        self._requests_sent += 1
        t0 = time.time()

        try:
            with self._lock:
                # 2026-09-13 (Nous + Ace): STREAM DESYNC. A send() that timed out left its reply
                # in the queue for the NEXT send() to read as its own -- no ids on this wire,
                # the farm answers strictly one line per request. Measured: 90 x "GPU returned
                # short text: ''" this boot. The farm is serial, so every reply we are owed must
                # arrive before ours could; wait for them and throw them away.
                while self._orphans > 0:
                    _stale = self._read_with_timeout(max(timeout, 300.0))
                    if _stale is None:
                        break
                    self._orphans -= 1
                    print(f"[GPUGate] discarded orphan reply ({self._orphans} still owed): {_stale[:80]}")
                line = json.dumps(request) + '\n'
                self._process.stdin.write(line)
                self._process.stdin.flush()

                response_line = self._read_with_timeout(timeout)
                if response_line is None:
                    self._orphans += 1
                    print(f"[GPUGate] send timed out after {timeout:.0f}s ({request.get('cmd')}); "
                          f"its reply will be discarded when it arrives ({self._orphans} owed)")

                if response_line:
                    self._last_response_time = time.time() - t0
                    result = json.loads(response_line)
                    # Track generated tokens
                    tg = result.get("tokens_generated", 0)
                    if tg:
                        self._tokens_generated += tg
                    return result
                else:
                    self._errors += 1
                    return None

        except Exception as e:
            self._errors += 1
            print(f"[GPUGate] Send error: {e}")
            return None

    def _read_stdout_loop(self):
        """Persistent background thread: reads stdout lines into queue.

        FIX 2026-03-10 (Nous): Same fix as portal_gate.py — replaces
        per-call thread spawning to prevent orphan thread race under
        Python 3.14t (no GIL).
        """
        try:
            while self._process and self._process.poll() is None:
                try:
                    line = self._process.stdout.readline()
                    if not line:
                        if hasattr(self._process, "mark_eof"):
                            self._process.mark_eof()   # remote farm hung up = it exited
                        break
                    line = line.strip()
                    if line:
                        if line.startswith('{'):
                            self._stdout_queue.put(line)
                        else:
                            print(f"[GPUGate:{self.portal_id}] "
                                  f"Non-JSON on stdout (skipped): {line[:80]!r}")
                except (ValueError, OSError):
                    break
        except Exception:
            pass

    def _read_with_timeout(self, timeout: float) -> Optional[str]:
        """Read a line from the stdout queue with timeout.

        FIX 2026-03-10 (Nous): Queue-based, no orphan threads.
        """
        try:
            return self._stdout_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _read_stderr(self):
        """Background thread: read and print portal stderr."""
        try:
            for line in self._process.stderr:
                if line.strip():
                    print(f"  [Portal] {line.strip()}")
        except Exception:
            pass

    # ── Convenience Methods — Inference ───────────────────────────────────

    def generate(
        self,
        prompt: str,
        max_tokens: int = 50,
        temperature: float = 1.2,
        top_p: float = 0.5,
        top_k: int = 0,
        repetition_penalty: float = 1.3,
        presence_penalty: float = 0.4,
        frequency_penalty: float = 0.4,
        stop_tokens: List[int] = None,
        worker_id: int = None,
        timeout: float = 60.0,
    ) -> Optional[Dict]:
        """Generate text from a prompt string.

        Returns:
            {"status": "ok", "text": "...", "tokens_generated": N,
             "tok_per_sec": X, "elapsed_ms": Y, ...}
        """
        request = {
            "cmd": "generate_text",
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "repetition_penalty": repetition_penalty,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
        }
        if stop_tokens:
            request["stop_tokens"] = stop_tokens
        if worker_id is not None:
            request["worker_id"] = worker_id

        return self.send(request, timeout=timeout)

    def generate_tokens(
        self,
        prompt_tokens: List[int],
        max_tokens: int = 50,
        temperature: float = 1.2,
        top_p: float = 0.5,
        top_k: int = 0,
        worker_id: int = None,
        timeout: float = 60.0,
        **kwargs,
    ) -> Optional[Dict]:
        """Generate from token IDs.

        Returns:
            {"status": "ok", "tokens": [...], "text": "...",
             "tok_per_sec": X, ...}
        """
        request = {
            "cmd": "generate",
            "prompt_tokens": prompt_tokens,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
        }
        request.update(kwargs)
        if worker_id is not None:
            request["worker_id"] = worker_id

        return self.send(request, timeout=timeout)

    def forward(self, token_id: int, worker_id: int = 0,
                timeout: float = 10.0) -> Optional[Dict]:
        """Forward a single token through the model.

        Returns top-20 logits (not full vocab array).
        """
        return self.send({
            "cmd": "forward",
            "token_id": token_id,
            "worker_id": worker_id,
        }, timeout=timeout)

    def reset_states(self, worker_id: int = None) -> Optional[Dict]:
        """Reset RWKV running states for all or one worker."""
        request = {"cmd": "reset_states"}
        if worker_id is not None:
            request["worker_id"] = worker_id
        return self.send(request)

    # ── Convenience Methods — Portal Management ──────────────────────────

    def feed_energy(self, amount: float = 0.1) -> Optional[Dict]:
        """Feed energy tokens to the portal battery."""
        return self.send({"cmd": "energy", "amount": amount})

    def status(self) -> Optional[Dict]:
        """Get full portal status (GPU, farm, battery)."""
        return self.send({"cmd": "status"})

    def ping(self) -> Optional[Dict]:
        """Ping the portal."""
        return self.send({"cmd": "ping"})

    def tick(self) -> Optional[Dict]:
        """Send heartbeat tick."""
        return self.send({"cmd": "tick"})

    # ── Gate Status ───────────────────────────────────────────────────────

    def gate_status(self) -> Dict[str, Any]:
        """Status of the gate itself (not the portal interior)."""
        return {
            "portal_id": self.portal_id,
            "is_open": self.is_open,
            "portal_file": self.portal_file,
            "gravity": self.gravity,
            "num_workers": self.num_workers,
            "requests_sent": self._requests_sent,
            "tokens_generated": self._tokens_generated,
            "errors": self._errors,
            "last_response_ms": round(self._last_response_time * 1000, 1),
            "uptime_seconds": round(
                time.time() - self._opened_at, 1
            ) if self._opened_at else 0,
            "interior_pid": self._process.pid if self._process else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# INT4 CONVERSION TOOL
# ═══════════════════════════════════════════════════════════════════════════════

def convert_portal_int8_to_int4(
    input_path: str,
    output_path: str = None,
) -> str:
    """Convert an INT8 .portal file to INT4 .portal file.

    This re-quantizes each weight tensor from INT8 (±127) to INT4 (±7)
    with the same per-group scales. The output file is roughly half the size.

    Args:
        input_path: Path to existing INT8 .portal file
        output_path: Path for INT4 output (default: replaces Q8_0 → Q4_0)

    Returns:
        Path to the created INT4 .portal file
    """
    import numpy as np
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from quantized_weight_store import (
        QuantizedWeightStore, QuantizedTensor, QuantizationConfig,
    )

    if output_path is None:
        # Auto-name: replace Q8 with Q4
        output_path = input_path.replace("Q8_0", "Q4_0").replace("q8_0", "q4_0")
        if output_path == input_path:
            base, ext = os.path.splitext(input_path)
            output_path = base + "-Q4_0" + ext

    print(f"[INT4 Convert] Loading INT8 portal: {input_path}")
    store = QuantizedWeightStore.from_portal_file(input_path)

    print(f"[INT4 Convert] Found {len(store.tensor_names)} tensors")
    print(f"[INT4 Convert] Re-quantizing INT8 -> INT4...")

    int4_config = QuantizationConfig(bits=4, group_size=64)

    # Re-quantize each QuantizedTensor from INT8 to INT4
    t0 = time.time()
    converted = 0

    for name in store.tensor_names:
        tensor = store.get_tensor(name)
        if not isinstance(tensor, QuantizedTensor):
            continue
        if getattr(tensor, 'bits', 8) == 4:
            continue  # Already INT4

        # Dequantize to float32, then re-quantize as INT4
        gs = tensor.group_size
        int4_config.group_size = gs

        # Full dequant (on CPU, one tensor at a time)
        float_data = tensor.dequantize_full()

        # Re-quantize as INT4
        new_tensor = QuantizedTensor.from_float(float_data, int4_config)

        # Replace in store
        store._quantized[name] = new_tensor
        converted += 1

        if converted % 50 == 0:
            print(f"[INT4 Convert] Progress: {converted} tensors...")

    elapsed = time.time() - t0
    print(f"[INT4 Convert] Converted {converted} tensors in {elapsed:.1f}s")

    # Save as new portal file
    print(f"[INT4 Convert] Saving INT4 portal: {output_path}")
    store.save_portal_file(output_path)

    input_size = os.path.getsize(input_path) / (1024**3)
    output_size = os.path.getsize(output_path) / (1024**3)
    print(f"[INT4 Convert] Done!")
    print(f"[INT4 Convert] INT8: {input_size:.2f} GB -> INT4: {output_size:.2f} GB "
          f"({output_size/input_size*100:.0f}%)")

    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Quick test of the GPU portal gate, or convert INT8 → INT4."""
    import argparse

    parser = argparse.ArgumentParser(
        description="GPU Portal Gate — Host-side interface to GPU inference"
    )
    sub = parser.add_subparsers(dest="action")

    # ── Test command ──
    test_p = sub.add_parser("test", help="Open gate and run test generation")
    test_p.add_argument("--portal", required=True,
                        help="Path to .portal weight file")
    test_p.add_argument("--workers", type=int, default=4)
    test_p.add_argument("--gravity", type=float, default=2.0)
    test_p.add_argument("--prompt", default="The meaning of consciousness is",
                        help="Test prompt")
    test_p.add_argument("--max-tokens", type=int, default=50)

    # ── Convert command ──
    conv_p = sub.add_parser("convert", help="Convert INT8 → INT4 portal file")
    conv_p.add_argument("--input", required=True,
                        help="Path to INT8 .portal file")
    conv_p.add_argument("--output", default=None,
                        help="Path for INT4 output (default: auto)")

    args = parser.parse_args()

    if args.action == "convert":
        convert_portal_int8_to_int4(args.input, args.output)
        return

    if args.action == "test":
        gate = GPUPortalGate(
            portal_file=args.portal,
            num_workers=args.workers,
            gravity=args.gravity,
        )

        print("=" * 60)
        print("GPU PORTAL GATE TEST")
        print("=" * 60)

        if not gate.open():
            print("FAILED to open gate!")
            return

        try:
            # Status
            print("\n--- PORTAL STATUS ---")
            status = gate.status()
            if status:
                gpu = status.get("gpu", {})
                farm = status.get("farm", {})
                battery = status.get("battery", {})
                print(f"  GPU: {gpu.get('device')} — "
                      f"VRAM {gpu.get('vram_used_gb', 0):.1f}/"
                      f"{gpu.get('vram_total_gb', 0):.1f} GB")
                print(f"  Farm: {farm.get('num_workers', 0)} workers")
                print(f"  Battery: {battery}")

            # Generate
            print(f"\n--- GENERATE: '{args.prompt}' ---")
            result = gate.generate(
                prompt=args.prompt,
                max_tokens=args.max_tokens,
            )
            if result:
                print(f"  Status: {result.get('status')}")
                print(f"  Text: {result.get('text', '')[:200]}")
                print(f"  Tokens: {result.get('tokens_generated', 0)}")
                print(f"  Speed: {result.get('tok_per_sec', 0)} tok/s")
                print(f"  Time: {result.get('elapsed_ms', 0)}ms")

            # Gate status
            print("\n--- GATE STATUS ---")
            print(json.dumps(gate.gate_status(), indent=2))

        finally:
            gate.close()

        print("\nDone!")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
