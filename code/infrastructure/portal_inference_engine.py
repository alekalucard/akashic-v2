"""
Portal Inference Engine — The Voice of a Dimension.

An inference engine that lives INSIDE a portal interior.
The model, the CUDA context, the VRAM — all contained within
the dimension's subprocess. From the outside, the portal is 45MB.
From the inside? Bigger on the inside.

The engine is embedded in the portal, not wrapped around it.
The graph is the dimension's knowledge. The engine is its voice.
The battery powers both. Token cost for inference is proportional
to output length — the battery's mass determines how much the
dimension can speak per cycle.

Token Economics:
    - 1 battery token per 10 inference tokens generated
    - A generate(max_tokens=200) costs 20 battery tokens
    - A portal with token_budget=50000 can generate ~500k tokens before depletion
    - Battery recharges from collision energy (ParadoxEnergyBridge)
    - When battery depletes → low_power → no inference until recharge

GPU Thread Affinity:
    CUDA contexts are thread-local. The engine creates a single GPU thread
    that owns the context. All inference requests queue through it.
    This is the same pattern used by AkashicInferenceFairy.

Usage (inside a PortalInterior subclass):
    self.engine = PortalInferenceEngine(model_path="path/to/model.gguf")
    self.engine.boot()  # Loads model on GPU thread

    # In process_request:
    if cmd == "generate":
        cost = max(1, payload.get("max_tokens", 200) // 10)
        if self.battery.spend_tokens(cost):
            result = self.engine.generate(payload["prompt"], payload.get("max_tokens", 200))
        else:
            return {"status": "low_power"}

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import os
import time
import queue
import threading
import traceback
from pathlib import Path
from typing import Dict, Optional, Any


# Logging goes to stderr (stdout is JSON pipe in portal interiors)
def _log(msg: str):
    print(msg, file=sys.stderr, flush=True)


class PortalInferenceEngine:
    """Inference engine that lives inside a portal dimension.

    The model and CUDA context exist entirely within this subprocess.
    The main fairy process sees nothing — just JSON through a pipe.

    The engine is a component of the portal, not the portal itself.
    Multiple engines could coexist in one portal (dialogue model +
    classifier + style model = one rich dimension).
    """

    def __init__(self, model_path: str, device: str = "cuda", engine_id: str = "primary"):
        self.model_path = model_path
        self.device = device
        self.engine_id = engine_id

        # Model state
        self._model = None
        self._model_type = "unknown"
        self._model_ready = False

        # GPU thread (CUDA context owner)
        self._gpu_thread: Optional[threading.Thread] = None
        self._work_queue: queue.Queue = queue.Queue()

        # Stats
        self._total_tokens_generated = 0
        self._total_requests = 0
        self._total_errors = 0
        self._boot_time = 0.0
        self._last_generate_time = 0.0

    # ── Lifecycle ──────────────────────────────────────────

    def boot(self, timeout: float = 120.0) -> bool:
        """Boot the engine — load model on GPU thread.

        Returns True when model is ready.
        """
        _log(f"[InferenceEngine:{self.engine_id}] Booting with model: {self.model_path}")
        t0 = time.time()

        self._gpu_thread = threading.Thread(
            target=self._gpu_thread_main,
            daemon=True,
            name=f"portal-gpu-{self.engine_id}",
        )
        self._gpu_thread.start()

        # Wait for model load
        deadline = time.time() + timeout
        while not self._model_ready and time.time() < deadline:
            time.sleep(0.5)

        if self._model_ready:
            self._boot_time = time.time() - t0
            _log(f"[InferenceEngine:{self.engine_id}] Ready in {self._boot_time:.1f}s")
            return True
        else:
            _log(f"[InferenceEngine:{self.engine_id}] FAILED to boot within {timeout}s")
            return False

    def shutdown(self):
        """Shutdown the engine — free model and CUDA context."""
        _log(f"[InferenceEngine:{self.engine_id}] Shutting down...")
        self._work_queue.put(None)  # Poison pill
        if self._gpu_thread:
            self._gpu_thread.join(timeout=5.0)
        self._model = None
        self._model_ready = False

    @property
    def is_ready(self) -> bool:
        return self._model_ready

    # ── Inference ──────────────────────────────────────────

    def generate(self, prompt: str, max_tokens: int = 200,
                 timeout: float = 60.0) -> Dict:
        """Generate text from prompt. Thread-safe — queues to GPU thread.

        Returns:
            {"text": "...", "tokens": N, "time": T, "tok_per_sec": R}
            or {"error": "..."} on failure
        """
        if not self._model_ready:
            return {"error": "Model not ready"}

        result_event = threading.Event()
        result_holder = {"result": None}

        self._work_queue.put({
            "type": "generate",
            "prompt": prompt,
            "max_tokens": max_tokens,
            "result_holder": result_holder,
            "event": result_event,
        })

        if result_event.wait(timeout=timeout):
            return result_holder["result"]
        else:
            self._total_errors += 1
            return {"error": f"Generate timed out after {timeout}s"}

    def status(self) -> Dict:
        """Engine status for portal status reporting."""
        return {
            "engine_id": self.engine_id,
            "model_path": str(self.model_path),
            "model_type": self._model_type,
            "model_ready": self._model_ready,
            "device": self.device,
            "boot_time": round(self._boot_time, 1),
            "total_tokens_generated": self._total_tokens_generated,
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "last_generate_time": round(self._last_generate_time, 3),
        }

    # ── GPU Thread (owns CUDA context) ─────────────────────

    def _gpu_thread_main(self):
        """GPU-owning thread. Loads model, then processes work queue."""
        try:
            self._load_model()
            self._model_ready = True
        except Exception as e:
            _log(f"[InferenceEngine:{self.engine_id}] Model load FAILED: {e}")
            _log(traceback.format_exc())
            return

        # Process work queue forever
        while True:
            try:
                item = self._work_queue.get(timeout=5.0)
            except queue.Empty:
                continue

            if item is None:
                break  # Poison pill

            try:
                if item["type"] == "generate":
                    result = self._do_generate(item["prompt"], item["max_tokens"])
                    item["result_holder"]["result"] = result
                else:
                    item["result_holder"]["result"] = {"error": f"Unknown work type: {item['type']}"}
            except Exception as e:
                _log(f"[InferenceEngine:{self.engine_id}] GPU error: {e}")
                item["result_holder"]["result"] = {"error": str(e)}
                self._total_errors += 1
            finally:
                item["event"].set()

        _log(f"[InferenceEngine:{self.engine_id}] GPU thread exiting")

    def _load_model(self):
        """Load model. Rust-first, Python-gguf fallback.

        Called on GPU thread — this creates the CUDA context.
        """
        model_path = self.model_path

        # Add project root for imports
        root = Path(__file__).parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        # Try Rust RWKV loader (~5s, preferred)
        try:
            _log(f"[InferenceEngine:{self.engine_id}] Trying Rust loader...")
            from fairies.P30_Cognition.AkashicInferenceFairy.rwkv_rust_bridge import RWKVRustBridge
            self._model = RWKVRustBridge(model_path)
            self._model_type = "rust_rwkv"
            _log(f"[InferenceEngine:{self.engine_id}] ✓ Rust loader OK")
            return
        except Exception as e:
            _log(f"[InferenceEngine:{self.engine_id}] Rust loader failed: {e}")

        # Try Python GGUF loader (~174s, fallback)
        try:
            _log(f"[InferenceEngine:{self.engine_id}] Trying Python GGUF loader...")
            from fairies.P30_Cognition.AkashicInferenceFairy.gguf_loader import GGUFModel
            self._model = GGUFModel(model_path, device=self.device)
            self._model_type = "python_gguf"
            _log(f"[InferenceEngine:{self.engine_id}] ✓ Python GGUF loader OK")
            return
        except Exception as e:
            _log(f"[InferenceEngine:{self.engine_id}] Python GGUF failed: {e}")

        raise RuntimeError(f"All model loaders failed for {model_path}")

    def _do_generate(self, prompt: str, max_tokens: int) -> Dict:
        """Run inference on GPU thread."""
        t0 = time.time()

        if hasattr(self._model, "generate"):
            text = self._model.generate(prompt, max_tokens=max_tokens)
        elif hasattr(self._model, "completion"):
            text = self._model.completion(prompt, max_tokens=max_tokens)
        else:
            return {"error": "Model has no generate/completion method"}

        elapsed = time.time() - t0
        # Approximate token count from text
        tokens = len(text.split()) if text else 0

        self._total_tokens_generated += tokens
        self._total_requests += 1
        self._last_generate_time = elapsed

        return {
            "text": text,
            "tokens": tokens,
            "time": round(elapsed, 3),
            "tok_per_sec": round(tokens / max(elapsed, 0.001), 1),
        }


# ── Token Cost Calculator ──────────────────────────────────

def inference_token_cost(max_tokens: int) -> int:
    """Calculate battery token cost for an inference request.

    1 battery token per 10 inference tokens requested.
    Minimum cost: 1 token (even for tiny requests).

    A portal with token_budget=50000:
      - 2500 generate(max_tokens=200) requests per cycle
      - Or ~500k inference tokens before depletion
      - Recharges from collision energy at ~100 tokens/tick
    """
    return max(1, max_tokens // 10)
