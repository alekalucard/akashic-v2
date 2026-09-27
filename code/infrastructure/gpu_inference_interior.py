"""
GPU Inference Interior — RWKV model in an isolated subprocess.

This runs as a portal worker, spawned by PortalGate.
The CUDA context, model weights, and all VRAM live HERE,
completely isolated from the main fairy process.

Benefits:
- 0 VRAM in main process (model is entirely in this subprocess)
- Crash isolation (GPU OOM kills only this process)
- Can be restarted without affecting 90 fairies
- Can spawn sub-portals (e.g., KV cache manager)

Protocol:
    → {"cmd": "generate", "prompt": "...", "max_tokens": 200}
    ← {"status": "ok", "text": "...", "tokens": 42, "time": 1.2}

    → {"cmd": "health"}
    ← {"status": "ok", "gpu_mem_used": 1.7, "gpu_mem_total": 12.0, ...}

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import os
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root for imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from infrastructure.portal_worker import PortalWorker, run_worker, _log


class GPUInferenceWorker(PortalWorker):
    """Portal worker that owns the RWKV model + CUDA context.

    The GPU thread affinity pattern: a single thread creates and owns the
    CUDA context. All inference requests queue through that thread.
    This prevents CUDA context corruption from multi-threaded access.
    """

    WORKER_NAME = "GPUInferenceWorker"

    def __init__(self, config: Dict = None):
        super().__init__(config)
        self._model = None
        self._model_path = None
        self._device = "cuda"
        self._gpu_thread = None
        self._work_queue = None
        self._model_ready = False
        self._total_tokens = 0
        self._total_requests = 0

    def on_boot(self):
        """Load RWKV model on the GPU thread."""
        import queue
        self._work_queue = queue.Queue()

        # Find model
        self._model_path = self.config.get("model_path", "")
        if not self._model_path:
            self._model_path = self._find_model()

        if not self._model_path or not os.path.exists(self._model_path):
            raise FileNotFoundError(f"Model not found: {self._model_path}")

        _log(f"[{self.WORKER_NAME}] Model: {self._model_path}")
        _log(f"[{self.WORKER_NAME}] Starting GPU thread...")

        # Start the GPU-owning thread
        self._gpu_thread = threading.Thread(
            target=self._gpu_thread_main,
            daemon=True,
            name="gpu-inference-owner",
        )
        self._gpu_thread.start()

        # Wait for model load
        deadline = time.time() + 120  # 2 min max for model load
        while not self._model_ready and time.time() < deadline:
            time.sleep(0.5)

        if not self._model_ready:
            raise RuntimeError("Model failed to load within 120s")

        _log(f"[{self.WORKER_NAME}] Model loaded and ready!")

    def handle(self, cmd: str, payload: Dict) -> Dict:
        """Dispatch commands to the GPU thread."""
        if cmd == "generate":
            return self._queue_generate(payload)
        elif cmd == "health":
            return self._get_health()
        elif cmd == "model_info":
            return self._get_model_info()
        else:
            return {"status": "error", "error": f"Unknown command: {cmd}"}

    def on_shutdown(self):
        """Cleanup CUDA resources."""
        _log(f"[{self.WORKER_NAME}] Releasing model and CUDA context...")
        if self._work_queue:
            self._work_queue.put(("__shutdown__", None, None))
        if self._gpu_thread:
            self._gpu_thread.join(timeout=5.0)
        self._model = None

    def get_status(self) -> Dict:
        """Custom status fields."""
        return {
            "model_path": str(self._model_path) if self._model_path else None,
            "model_ready": self._model_ready,
            "total_tokens": self._total_tokens,
            "total_requests": self._total_requests,
            "device": self._device,
        }

    # ── GPU Thread ─────────────────────────────────────────

    def _gpu_thread_main(self):
        """Main loop for the GPU-owning thread.

        This thread creates the CUDA context and owns it exclusively.
        All model operations happen here.
        """
        _log(f"[{self.WORKER_NAME}] GPU thread started. Loading model...")

        try:
            self._load_model()
            self._model_ready = True
            _log(f"[{self.WORKER_NAME}] GPU thread: model ready")
        except Exception as e:
            _log(f"[{self.WORKER_NAME}] GPU thread: model load FAILED: {e}")
            import traceback
            _log(traceback.format_exc())
            return

        # Process work queue
        while True:
            try:
                item = self._work_queue.get(timeout=1.0)
            except Exception:
                continue  # Queue.Empty timeout, loop again

            if item is None:
                continue

            cmd, payload, result_holder = item

            if cmd == "__shutdown__":
                break

            try:
                if cmd == "generate":
                    result = self._do_generate(payload)
                    result_holder["result"] = result
                else:
                    result_holder["result"] = {"status": "error", "error": f"Unknown GPU cmd: {cmd}"}
            except Exception as e:
                _log(f"[{self.WORKER_NAME}] GPU thread error: {e}")
                result_holder["result"] = {"status": "error", "error": str(e)}
            finally:
                result_holder["done"].set()

        _log(f"[{self.WORKER_NAME}] GPU thread exiting")

    def _load_model(self):
        """Load the RWKV model. Tries Rust first, Python fallback."""
        model_path = self._model_path

        # Try Rust-based loader first (fast, ~5s)
        try:
            _log(f"[{self.WORKER_NAME}] Trying Rust RWKV loader...")
            from fairies.P30_Cognition.AkashicInferenceFairy.rwkv_rust_bridge import RWKVRustBridge
            self._model = RWKVRustBridge(model_path)
            self._model_type = "rust"
            _log(f"[{self.WORKER_NAME}] Rust loader succeeded!")
            return
        except Exception as e:
            _log(f"[{self.WORKER_NAME}] Rust loader failed: {e}")

        # Python fallback (slow, ~174s)
        try:
            _log(f"[{self.WORKER_NAME}] Trying Python GGUF loader...")
            from fairies.P30_Cognition.AkashicInferenceFairy.gguf_loader import GGUFModel
            self._model = GGUFModel(model_path, device=self._device)
            self._model_type = "python_gguf"
            _log(f"[{self.WORKER_NAME}] Python GGUF loader succeeded!")
            return
        except Exception as e:
            _log(f"[{self.WORKER_NAME}] Python GGUF loader failed: {e}")

        # Last resort: raw PyTorch state dict
        try:
            _log(f"[{self.WORKER_NAME}] Trying raw PyTorch loader...")
            import torch
            self._model = torch.load(model_path, map_location=self._device, weights_only=True)
            self._model_type = "raw_pytorch"
            _log(f"[{self.WORKER_NAME}] PyTorch loader succeeded (WARNING: no generate method)")
            return
        except Exception as e:
            _log(f"[{self.WORKER_NAME}] All loaders failed: {e}")
            raise RuntimeError(f"Cannot load model from {model_path}")

    def _do_generate(self, payload: Dict) -> Dict:
        """Generate text using the model. Runs on GPU thread."""
        prompt = payload.get("prompt", "")
        max_tokens = payload.get("max_tokens", 200)

        if not prompt:
            return {"status": "error", "error": "No prompt provided"}

        t0 = time.time()

        try:
            if hasattr(self._model, "generate"):
                result_text = self._model.generate(prompt, max_tokens=max_tokens)
            elif hasattr(self._model, "completion"):
                result_text = self._model.completion(prompt, max_tokens=max_tokens)
            else:
                return {"status": "error", "error": "Model has no generate method"}

            elapsed = time.time() - t0
            tokens_generated = len(result_text.split()) if result_text else 0
            self._total_tokens += tokens_generated
            self._total_requests += 1

            return {
                "status": "ok",
                "text": result_text,
                "tokens": tokens_generated,
                "time": round(elapsed, 3),
                "tok_per_sec": round(tokens_generated / max(elapsed, 0.001), 1),
            }

        except Exception as e:
            _log(f"[{self.WORKER_NAME}] Generate error: {e}")
            return {"status": "error", "error": str(e)}

    def _queue_generate(self, payload: Dict) -> Dict:
        """Queue a generate request to the GPU thread and wait."""
        import threading as _th

        result_holder = {"result": None, "done": _th.Event()}
        self._work_queue.put(("generate", payload, result_holder))

        # Wait with timeout
        timeout = payload.get("timeout", 60.0)
        if result_holder["done"].wait(timeout=timeout):
            return result_holder["result"]
        else:
            return {"status": "error", "error": f"Generate timed out after {timeout}s"}

    # ── Health / Info ──────────────────────────────────────

    def _get_health(self) -> Dict:
        """GPU health check."""
        health = {
            "status": "ok",
            "model_ready": self._model_ready,
            "total_tokens": self._total_tokens,
            "total_requests": self._total_requests,
        }

        try:
            import torch
            if torch.cuda.is_available():
                health["gpu_name"] = torch.cuda.get_device_name(0)
                health["gpu_mem_used_gb"] = round(torch.cuda.memory_allocated(0) / 1e9, 2)
                health["gpu_mem_total_gb"] = round(torch.cuda.get_device_properties(0).total_mem / 1e9, 2)
                health["gpu_mem_reserved_gb"] = round(torch.cuda.memory_reserved(0) / 1e9, 2)
        except Exception:
            health["gpu"] = "unavailable"

        return health

    def _get_model_info(self) -> Dict:
        """Model information."""
        return {
            "status": "ok",
            "model_path": str(self._model_path),
            "model_type": getattr(self, '_model_type', 'unknown'),
            "model_ready": self._model_ready,
        }

    # ── Model Discovery ────────────────────────────────────

    def _find_model(self) -> str:
        """Auto-discover RWKV model file."""
        search_dirs = [
            ROOT / "models",
            ROOT / "rwkv_models",
            Path.home() / ".cache" / "rwkv",
        ]

        patterns = ["*.gguf", "*.pth"]

        for d in search_dirs:
            if d.exists():
                for pat in patterns:
                    matches = sorted(d.glob(pat), key=lambda p: p.stat().st_size, reverse=True)
                    if matches:
                        return str(matches[0])

        return ""


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    run_worker(GPUInferenceWorker)
