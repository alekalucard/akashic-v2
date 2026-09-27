"""
GPU Inference Portal — The Dimension That Thinks.

A subprocess portal that owns a single CUDA context with model weights
loaded into VRAM. Multiple BatteryFarm workers share those GPU tensors.
From the outside: a pipe handle. From the inside: 12GB of neural tissue.

This is the inference equivalent of what PortalInterior does for the
AssociationCortex concept graph. The concept graph loads card chunks
from disk into the portal. We load weight chunks from .portal files
into VRAM. Same pattern, different contents.

Architecture:
    Host Process (fairy)
      |  JSON-per-line pipe
      v
    GPUInferencePortal (subprocess)
      |
      +-- QuantizedWeightStore (mmap from .portal file)
      +-- GPU Weight Cache    (dequantized to VRAM, shared)
      +-- BatteryFarm
      |     +-- Worker[0]: BCU + Engine (shares GPU weights)
      |     +-- Worker[1]: BCU + Engine (shares GPU weights)
      |     +-- Worker[N]: ...
      +-- PortalBattery (energy accounting)

Portal Gravity → Quantization Depth:
    α=1.0 (flat)   → FP16  → ~14.4 GB (7.2B model)
    α=1.5 (normal) → INT8  → ~7.6 GB
    α=2.0 (deep)   → INT4  → ~3.8 GB  ← default
    α=3.0 (crushed) → INT2 → ~1.9 GB  (future)

With INT4 gravity on the 7.2B model: ~3.8 GB VRAM for weights,
leaving ~8 GB headroom for states, KV cache, and overhead.
Multiple farms can share those weights — each worker only needs
~1 MB for its own RWKV state.

IPC Protocol (same as portal_interior.py):
    stdin/stdout: JSON-per-line
    Request:  {"cmd": "generate", "prompt_tokens": [...], "max_tokens": 50, ...}
    Response: {"status": "ok", "tokens": [...], "text": "...", ...}

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import os
import json
import time
import signal
import threading
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any

# ── Path setup for subprocess context ─────────────────────────────────────
# When run as a subprocess, add the project root to sys.path so that
# rwkv_gpu_engine.py and friends can be imported directly.
# Their try/except import blocks handle both package and standalone contexts.

_AKASHIC_ROOT = str(Path(__file__).resolve().parent.parent)
if _AKASHIC_ROOT not in sys.path:
    sys.path.insert(0, _AKASHIC_ROOT)


# ── Logging (stderr — stdout is JSON pipe) ────────────────────────────────

def _log(msg: str):
    # 2026-09-11 (Nous+Ace): when the host dies first this pipe is closed and print()
    # raises OSError 22. shutdown() opens with _log(), so VRAM release and the RWKV
    # state save were aborted at line one on every EOF exit. Control:
    # stderr_eof_control.py (reader closed -> save never reached; open -> reached).
    try:
        print(msg, file=sys.stderr, flush=True)
    except OSError:
        pass


# ── Portal Gravity Constants ──────────────────────────────────────────────

GRAVITY_FP16 = 1.0    # α=1.0 — flat spacetime, no compression
GRAVITY_INT8 = 1.5    # α=1.5 — normal gravity well
GRAVITY_INT4 = 2.0    # α=2.0 — deep gravity well (default)
GRAVITY_INT2 = 3.0    # α=3.0 — crushed singularity (future)


# ═══════════════════════════════════════════════════════════════════════════════
# PORTAL BATTERY — Energy accounting for the GPU dimension
# ═══════════════════════════════════════════════════════════════════════════════

class GPUPortalBattery:
    """Battery for the GPU inference portal.

    Token economics:
        - 1 battery token per 10 inference tokens generated
        - A portal with token_budget=100000 can generate ~1M tokens
        - Battery recharges from collision energy via host
        - When depleted → low_power → no inference until recharge
    """

    def __init__(self, token_budget: int = 100_000):
        self.token_budget = token_budget
        self.tokens_remaining = token_budget
        self._tokens_spent = 0
        self._energy_received = 0.0
        self._failures = 0
        self._successes = 0

    def spend_tokens(self, cost: int) -> bool:
        """Spend tokens. Returns False if insufficient."""
        if self.tokens_remaining < cost:
            return False
        self.tokens_remaining -= cost
        self._tokens_spent += cost
        return True

    def receive_energy(self, amount: float):
        """Receive energy from host — recharges tokens."""
        tokens_restored = int(amount * self.token_budget * 0.1)
        self.tokens_remaining = min(
            self.token_budget,
            self.tokens_remaining + tokens_restored,
        )
        self._energy_received += amount

    def record_success(self, energy: float = 0.01):
        self._successes += 1
        self.receive_energy(energy)

    def record_failure(self, penalty: float = 0.05):
        self._failures += 1

    @property
    def charge_level(self) -> float:
        return self.tokens_remaining / max(self.token_budget, 1)

    @property
    def health_score(self) -> str:
        cl = self.charge_level
        if cl > 0.7: return "healthy"
        if cl > 0.3: return "nominal"
        if cl > 0.1: return "low"
        return "critical"

    def status(self) -> Dict:
        return {
            "token_budget": self.token_budget,
            "tokens_remaining": self.tokens_remaining,
            "tokens_spent": self._tokens_spent,
            "charge_level": round(self.charge_level, 3),
            "health": self.health_score,
            "energy_received": round(self._energy_received, 3),
            "successes": self._successes,
            "failures": self._failures,
        }

    def tick(self):
        """Passive recharge tick — small trickle."""
        regen = max(1, self.token_budget // 10000)
        self.tokens_remaining = min(
            self.token_budget,
            self.tokens_remaining + regen,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GPU INFERENCE PORTAL — The Room That Thinks
# ═══════════════════════════════════════════════════════════════════════════════

class GPUInferencePortal:
    """GPU inference subprocess — owns CUDA context, model weights, and farms.

    This is the portal interior for inference. It does for RWKV weights
    what PortalInterior does for concept graph cards:
    - Loads from a .portal file (mmap, near-zero RAM)
    - Uploads to GPU with configurable gravity (quantization depth)
    - Multiple farm workers share those GPU tensors
    - Accepts requests via JSON-per-line protocol

    The model weights live INSIDE this subprocess. The host fairy sees
    nothing — just JSON through a pipe. Bigger on the inside.
    """

    def __init__(self,
                 portal_file: str,
                 num_workers: int = 4,
                 gravity: float = GRAVITY_INT8,
                 token_budget: int = 100_000,
                 portal_id: str = "gpu-inference",
                 flops_budget: int = 500_000_000,
                 max_charge: float = 20.0,
                 recharge_rate: float = 0.01,
                 host_port: int = 0):
        self.portal_file = portal_file
        self.num_workers = num_workers
        self.gravity = gravity
        self.token_budget = token_budget
        self.portal_id = portal_id
        self.flops_budget = flops_budget
        self.max_charge = max_charge
        self.recharge_rate = recharge_rate
        self.host_port = host_port

        # Components (created during boot)
        self.weight_store = None      # QuantizedWeightStore (mmap)
        self.gpu_weights = None       # Dict[str, torch.Tensor] on GPU
        self.farm = None              # BatteryFarm
        self.battery = None           # GPUPortalBattery
        self.model_config = None      # RWKVBatteryConfig

        # State
        self._running = False
        self._requests_processed = 0
        self._tokens_generated = 0
        self._boot_time = 0.0
        self._lock = threading.Lock()

    def boot(self) -> bool:
        """Boot the portal — load weights, upload to GPU, create farm."""
        t0 = time.time()
        _log(f"[GPUPortal:{self.portal_id}] Booting...")
        _log(f"[GPUPortal:{self.portal_id}] Portal file: {self.portal_file}")
        _log(f"[GPUPortal:{self.portal_id}] Gravity: a={self.gravity} "
             f"({'INT4' if self.gravity >= 2.0 else 'INT8' if self.gravity >= 1.5 else 'FP16'})")
        _log(f"[GPUPortal:{self.portal_id}] Workers: {self.num_workers}")

        # ── 1. Load weight store from .portal file (mmap, ~0 RAM) ──
        try:
            from quantized_weight_store import QuantizedWeightStore
            self.weight_store = QuantizedWeightStore.from_portal_file(self.portal_file)
            _log(f"[GPUPortal:{self.portal_id}] Weight store loaded: "
                 f"{len(self.weight_store.tensor_names)} tensors (mmap)")
        except Exception as e:
            _log(f"[GPUPortal:{self.portal_id}] FATAL: Cannot load portal file: {e}")
            _log(traceback.format_exc())
            return False

        # ── 2. Detect model config from weight shapes ──
        try:
            self.model_config = self._detect_config()
            _log(f"[GPUPortal:{self.portal_id}] Model config: "
                 f"{self.model_config.n_layer}L, {self.model_config.n_embd}D, "
                 f"{self.model_config.n_head}H, vocab={self.model_config.vocab_size}")
        except Exception as e:
            _log(f"[GPUPortal:{self.portal_id}] FATAL: Config detection failed: {e}")
            _log(traceback.format_exc())
            return False

        # ── 2.5 Close mmap — config detection only needed shape metadata ──
        # FIX 2026-03-04 Nous: Close the mmap BEFORE weight upload.
        # _detect_config() only reads .shape attributes (stored in Python
        # objects, no data pages touched). The upload now streams directly
        # from the portal file, bypassing mmap entirely. Closing here
        # prevents ANY mmap page cache buildup (saves ~3.8 GB system RAM).
        # The weight_store OBJECT stays alive as a cache key for farm build.
        if self.weight_store and hasattr(self.weight_store, 'close_portal'):
            _log(f"[GPUPortal:{self.portal_id}] Closing mmap early "
                 f"(upload will stream from file, not mmap)")
            try:
                self.weight_store.close_portal()
            except Exception as e:
                _log(f"[GPUPortal:{self.portal_id}] Warning: mmap close: {e}")

        # ── 3. Stream weights from file to GPU ──
        try:
            import torch
            if not torch.cuda.is_available():
                _log(f"[GPUPortal:{self.portal_id}] FATAL: No CUDA device available")
                return False

            _log(f"[GPUPortal:{self.portal_id}] GPU: {torch.cuda.get_device_name(0)}")
            vram_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            vram_free = (torch.cuda.get_device_properties(0).total_memory -
                         torch.cuda.memory_allocated(0)) / (1024**3)
            _log(f"[GPUPortal:{self.portal_id}] VRAM: {vram_free:.1f} / {vram_total:.1f} GB free")

            self.gpu_weights = self._upload_weights_to_gpu()
            vram_used = torch.cuda.memory_allocated(0) / (1024**3)
            _log(f"[GPUPortal:{self.portal_id}] VRAM after upload: {vram_used:.1f} GB used")

            # Force GC to collect any straggling upload buffers
            import gc
            gc.collect()
        except Exception as e:
            _log(f"[GPUPortal:{self.portal_id}] FATAL: GPU upload failed: {e}")
            _log(traceback.format_exc())
            return False

        # ── 4. Create battery farm ──
        try:
            self.farm = self._build_farm()
            _log(f"[GPUPortal:{self.portal_id}] Farm built: "
                 f"{self.num_workers} workers, "
                 f"flops_budget={self.flops_budget:,}")
        except Exception as e:
            _log(f"[GPUPortal:{self.portal_id}] FATAL: Farm build failed: {e}")
            _log(traceback.format_exc())
            return False

        # -- 4b. RWKV STATE RESTORE (2026-09-11, Nous+Ace; env-gated) --------------
        # rwkv_gpu_engine's save/load_state_from_disk existed with ZERO callers, so her
        # recurrent state was torch.zeros on every boot -- RWKV's one reason to exist
        # over a transformer, unwired. Each worker restores ITS OWN file (N states, not
        # one; they are not merged). A missing or dimension-mismatched file costs one
        # log line, never the boot. Unset AKASHIC_RWKV_PERSIST -> this block is skipped.
        if os.environ.get("AKASHIC_RWKV_PERSIST", "") == "1" and self.farm:
            _rs_dir = self._rwkv_state_dir()
            _ok = _miss = _bad = 0
            for _i, _w in enumerate(getattr(self.farm, "workers", []) or []):
                _p = os.path.join(_rs_dir, f"rwkv_worker_{_i}.npz")
                if not os.path.exists(_p):
                    _miss += 1
                    continue
                try:
                    _w.engine.load_state_from_disk(_p)
                    _ok += 1
                except Exception as _e:
                    _bad += 1
                    _log(f"[GPUPortal:{self.portal_id}] RWKV state worker {_i} "
                         f"NOT restored: {str(_e)[:120]}")
            _log(f"[GPUPortal:{self.portal_id}] RWKV STATE RESTORE: "
                 f"{_ok} restored, {_miss} absent, {_bad} rejected "
                 f"(dir={_rs_dir})")

        # ── 5. Create portal battery ──
        self.battery = GPUPortalBattery(token_budget=self.token_budget)
        _log(f"[GPUPortal:{self.portal_id}] Battery: {self.token_budget} token budget")

        self._boot_time = time.time() - t0
        _log(f"[GPUPortal:{self.portal_id}] ONLINE in {self._boot_time:.1f}s")
        return True

    def _detect_config(self):
        """Detect RWKV model config from weight tensor shapes."""
        from rwkv_gpu_engine import RWKVBatteryConfig

        store = self.weight_store

        # Detect n_embd from embedding weight
        emb = store.get_tensor("emb.weight")
        if hasattr(emb, 'shape'):
            vocab_size, n_embd = emb.shape
        else:
            arr = emb
            vocab_size, n_embd = arr.shape

        # Detect n_layer by counting blocks
        n_layer = 0
        for name in store.tensor_names:
            if name.startswith("blocks.") and ".ln1.weight" in name:
                layer_num = int(name.split(".")[1])
                n_layer = max(n_layer, layer_num + 1)

        # Detect n_head from attention key shape
        # blocks.0.att.key.weight shape is [n_embd, n_embd]
        # head_size is typically 64
        head_size = 64
        n_head = n_embd // head_size

        # Detect LoRA dimensions
        d_decay_lora = 64
        d_aaa_lora = 64
        d_mv_lora = 32
        d_gate_lora = 128

        for name in store.tensor_names:
            if "att.w1" in name:
                t = store.get_tensor(name)
                d_decay_lora = t.shape[0] if hasattr(t, 'shape') else 64
                break

        for name in store.tensor_names:
            if "att.a1" in name:
                t = store.get_tensor(name)
                d_aaa_lora = t.shape[0] if hasattr(t, 'shape') else 64
                break

        for name in store.tensor_names:
            if "att.v1" in name:
                t = store.get_tensor(name)
                d_mv_lora = t.shape[0] if hasattr(t, 'shape') else 32
                break

        for name in store.tensor_names:
            if "att.g1" in name:
                t = store.get_tensor(name)
                d_gate_lora = t.shape[0] if hasattr(t, 'shape') else 128
                break

        return RWKVBatteryConfig(
            n_layer=n_layer,
            n_embd=n_embd,
            n_head=n_head,
            head_size=head_size,
            vocab_size=vocab_size,
            d_decay_lora=d_decay_lora,
            d_aaa_lora=d_aaa_lora,
            d_mv_lora=d_mv_lora,
            d_gate_lora=d_gate_lora,
        )

    def _upload_weights_to_gpu(self) -> Dict:
        """Upload weights to GPU VRAM — STREAMING from portal file.

        FIX 2026-03-04 Nous: Complete rewrite. Previous version iterated
        mmap views which paged the ENTIRE 3.8 GB model into system RAM.
        This version reads directly from the portal file, one tensor at a
        time, and frees each CPU buffer immediately after GPU upload.

        Peak system RAM: ~10 MB (one tensor buffer) instead of ~3.8 GB.

        Quantized weights (INT4/INT8) are uploaded as GPUQuantizedWeight
        objects: raw packed data + scales on GPU, dequantized on-the-fly
        during each forward pass.

            INT4 on GPU: ~3.8 GB VRAM (fits with 8GB headroom)
            System RAM:  ~10 MB peak during upload, ~0 after

        Float tensors (1D norms, biases) go directly as float32.
        """
        import torch
        import struct as _struct
        import numpy as np
        from rwkv_gpu_engine import GPUQuantizedWeight

        device = torch.device("cuda")
        gpu_weights: Dict[str, Any] = {}
        t0 = time.time()
        total_params = 0
        n_quantized_int4 = 0
        n_quantized_int8 = 0
        n_fp16 = 0
        n_fp32 = 0
        quantized_bytes = 0

        # ── Parse portal file header to get tensor index ──
        # This reads ~10 KB of JSON, not the 3.8 GB of weights.
        with open(self.portal_file, 'rb') as hf:
            magic = hf.read(4)
            version = _struct.unpack('<I', hf.read(4))[0]
            header_len = _struct.unpack('<I', hf.read(4))[0]
            index = json.loads(hf.read(header_len))

        entries = index["tensors"]
        total = len(entries)

        _log(f"[GPUPortal:{self.portal_id}] Streaming {total} tensors "
             f"from portal file -> GPU (no mmap, minimal system RAM)")

        # ── Stream each tensor: seek → read → GPU → free ──
        # One tensor at a time. Peak RAM = one tensor buffer (~8 MB max).
        f = open(self.portal_file, 'rb')
        try:
            for i, entry in enumerate(entries):
                name = entry["name"]

                if entry["type"] == "quantized":
                    shape = tuple(entry["shape"])
                    M, K = shape
                    bits = entry.get("bits", 8)
                    gs = entry["group_size"]
                    total_params += M * K

                    data_shape = tuple(entry["data_shape"])
                    scales_shape = tuple(entry["scales_shape"])
                    data_dtype_str = entry.get("data_dtype", "int8")
                    data_dtype = np.uint8 if (data_dtype_str == "uint8" or bits == 4) else np.int8

                    # Small quantized tensors (<100K params): dequant to fp32
                    if M * K < 100_000:
                        # Read data from file
                        f.seek(entry["data_offset"])
                        raw_data = f.read(entry["data_bytes"])
                        data = np.frombuffer(raw_data, dtype=data_dtype).reshape(data_shape)

                        # Read scales from file
                        f.seek(entry["scales_offset"])
                        raw_scales = f.read(entry["scales_bytes"])
                        scales = np.frombuffer(raw_scales, dtype=np.float32).reshape(scales_shape)

                        # Dequantize CPU-side (tiny tensor, ~KB)
                        if bits == 4:
                            hi = (data.astype(np.int16) >> 4).astype(np.int8) - 8
                            lo = (data.astype(np.int16) & 0x0F).astype(np.int8) - 8
                            unpacked = np.empty((data_shape[0], data_shape[1] * 2), dtype=np.int8)
                            unpacked[:, 0::2] = hi
                            unpacked[:, 1::2] = lo
                            K_work = unpacked.shape[1]
                            n_groups = K_work // gs
                            data_grouped = unpacked.reshape(M, n_groups, gs)
                        else:
                            K_work = data_shape[1]
                            n_groups = K_work // gs
                            data_grouped = data.reshape(M, n_groups, gs)

                        scales_expanded = scales[:, :, np.newaxis]
                        result = (data_grouped.astype(np.float32) * scales_expanded).reshape(M, K_work)[:, :K]
                        t = torch.tensor(result, device=device, dtype=torch.float32)
                        n_fp32 += 1
                        del raw_data, data, raw_scales, scales, data_grouped, scales_expanded, result

                    else:
                        # Large tensor: upload raw quantized data + scales to GPU
                        # Read data chunk from file → GPU → free
                        f.seek(entry["data_offset"])
                        raw_data = f.read(entry["data_bytes"])
                        data = np.frombuffer(raw_data, dtype=data_dtype).reshape(data_shape)
                        data_gpu = torch.tensor(data, device=device)
                        del raw_data, data  # FREE immediately

                        # Read scales chunk from file → GPU → free
                        f.seek(entry["scales_offset"])
                        raw_scales = f.read(entry["scales_bytes"])
                        scales = np.frombuffer(raw_scales, dtype=np.float32).reshape(scales_shape)
                        scales_gpu = torch.tensor(scales, device=device, dtype=torch.float32)
                        del raw_scales, scales  # FREE immediately

                        t = GPUQuantizedWeight(
                            data=data_gpu,
                            scales=scales_gpu,
                            shape=(M, K),
                            bits=bits,
                            group_size=gs,
                            device=device,
                        )

                        quantized_bytes += data_gpu.nelement() * data_gpu.element_size()
                        quantized_bytes += scales_gpu.nelement() * scales_gpu.element_size()

                        if bits == 4:
                            n_quantized_int4 += 1
                        else:
                            n_quantized_int8 += 1

                elif entry["type"] == "float32":
                    data_shape = tuple(entry["data_shape"])

                    # Read float tensor from file → GPU → free
                    f.seek(entry["data_offset"])
                    raw = f.read(entry["data_bytes"])
                    arr = np.frombuffer(raw, dtype=np.float32).reshape(data_shape)
                    total_params += arr.size

                    if arr.ndim >= 2 and arr.size > 4096:
                        t = torch.tensor(arr, device=device, dtype=torch.float16)
                        n_fp16 += 1
                    else:
                        t = torch.tensor(arr, device=device, dtype=torch.float32)
                        n_fp32 += 1
                    del raw, arr  # FREE immediately

                else:
                    _log(f"[GPUPortal:{self.portal_id}] WARNING: Unknown tensor "
                         f"type '{entry['type']}' for {name}, skipping")
                    continue

                gpu_weights[name] = t

                if (i + 1) % 100 == 0 or (i + 1) == total:
                    vram_used = torch.cuda.memory_allocated(device) / (1024**2)
                    _log(f"[GPUPortal:{self.portal_id}] Stream: "
                         f"{i+1}/{total} tensors -> VRAM {vram_used:.0f}MB")

        finally:
            f.close()

        elapsed = time.time() - t0
        vram_mb = quantized_bytes / (1024 * 1024)
        # Add non-quantized tensor VRAM
        for v in gpu_weights.values():
            if isinstance(v, torch.Tensor):
                vram_mb += v.nelement() * v.element_size() / (1024 * 1024)

        _log(f"[GPUPortal:{self.portal_id}] Streamed {len(gpu_weights)} tensors "
             f"({total_params / 1e6:.1f}M params) in {elapsed:.1f}s")
        _log(f"[GPUPortal:{self.portal_id}] VRAM: {vram_mb:.0f}MB "
             f"({n_quantized_int4} INT4-quantized, {n_quantized_int8} INT8-quantized, "
             f"{n_fp16} fp16, {n_fp32} fp32)")
        _log(f"[GPUPortal:{self.portal_id}] System RAM: MINIMAL "
             f"(streamed from file, no mmap page cache)")

        return gpu_weights

    def _build_farm(self):
        """Build a BatteryFarm with workers that share our GPU weight cache.

        The trick: we inject our gpu_weights into RWKVGPUBatteryEngine's
        class-level cache BEFORE creating workers. Each worker's __init__
        calls _get_gpu_weights() which finds our pre-loaded tensors.
        """
        import torch
        from rwkv_gpu_engine import RWKVGPUBatteryEngine
        from battery_compute_unit import BatteryComputeUnit
        from battery_farm import BatteryFarm

        # Inject our GPU weights into the engine's class-level cache
        ws_id = id(self.weight_store)
        RWKVGPUBatteryEngine._gpu_weight_cache[ws_id] = self.gpu_weights
        _log(f"[GPUPortal:{self.portal_id}] Injected GPU weights into engine cache "
             f"(store_id={ws_id})")

        # Build farm
        farm = BatteryFarm(
            num_workers=self.num_workers,
            flops_budget_per_worker=self.flops_budget,
            recharge_rate=self.recharge_rate,
            max_charge=self.max_charge,
        )

        # Create workers — they'll find our cached weights
        import rwkv_gpu_engine as engine_module
        import battery_compute_unit as compute_module

        farm.build(
            config=self.model_config,
            weight_store=self.weight_store,
            compute_module=compute_module,
            engine_module=engine_module,
            state_dtype=None,  # GPU always uses float32
        )

        # Start recharge loop
        farm.start_recharge_loop()

        return farm

    # ── Request Processing ─────────────────────────────────────────────────

    def process_request(self, request: Dict) -> Dict:
        """Process a request from the host. Returns response dict."""
        cmd = request.get("cmd", "")

        try:
            if cmd == "generate":
                return self._handle_generate(request)
            elif cmd == "generate_text":
                return self._handle_generate_text(request)
            elif cmd == "forward":
                return self._handle_forward(request)
            elif cmd == "status":
                return self._handle_status(request)
            elif cmd == "energy":
                return self._handle_energy(request)
            elif cmd == "ping":
                return {"status": "pong", "ts": time.time(),
                        "portal_id": self.portal_id}
            elif cmd == "reset_states":
                return self._handle_reset_states(request)
            elif cmd == "shutdown":
                self._running = False
                return {"status": "ok", "message": "Shutting down"}
            elif cmd == "tick":
                if self.battery:
                    self.battery.tick()
                return {"status": "ok"}
            else:
                return {"status": "error", "message": f"Unknown command: {cmd}"}
        except Exception as e:
            _log(f"[GPUPortal:{self.portal_id}] Request error: {e}")
            _log(traceback.format_exc())
            if self.battery:
                self.battery.record_failure(0.05)
            return {"status": "error", "message": str(e), "cmd": cmd}

    def _handle_generate(self, request: Dict) -> Dict:
        """Generate tokens from prompt tokens.

        Request:
            {"cmd": "generate", "prompt_tokens": [1, 2, 3, ...],
             "max_tokens": 50, "temperature": 1.2, "top_p": 0.5, ...}

        Response:
            {"status": "ok", "tokens": [4, 5, 6], "text": "...",
             "tokens_generated": 3, "battery_cost": 5}
        """
        if not self.farm or not self.farm._built:
            return {"status": "error", "message": "Farm not built"}

        prompt_tokens = request.get("prompt_tokens", [])
        max_tokens = min(request.get("max_tokens", 50), 2048)
        temperature = request.get("temperature", 1.2)
        top_k = request.get("top_k", 0)
        top_p = request.get("top_p", 0.5)
        repetition_penalty = request.get("repetition_penalty", 1.3)
        presence_penalty = request.get("presence_penalty", 0.4)
        frequency_penalty = request.get("frequency_penalty", 0.4)
        stop_tokens = request.get("stop_tokens", None)
        gravity_stride = request.get("gravity_stride", 1)
        worker_id = request.get("worker_id", None)

        # Battery cost: 1 per 10 tokens requested
        battery_cost = max(1, max_tokens // 10)
        if self.battery and not self.battery.spend_tokens(battery_cost):
            return {
                "status": "low_power",
                "message": "Portal battery depleted",
                "battery": self.battery.status(),
            }

        # Pick worker — specific or best available
        worker = self._pick_worker(worker_id)
        if worker is None:
            return {
                "status": "error",
                "message": "No available workers (all depleted)",
            }

        t0 = time.time()
        # 2026-09-11 (Nous+Ace): per-request wall-clock deadline, under the gate's 90 s, so a
        # runaway (degenerate, no stop token) cannot wedge the single-worker farm. Partial
        # text comes back as status ok with deadline_hit=True. See rwkv_gpu_engine.
        try:
            _deadline_s = float(request.get("deadline_s",
                                            os.environ.get("AKASHIC_FARM_GEN_DEADLINE_S", "75")))
        except (TypeError, ValueError):
            _deadline_s = 75.0
        _deadline = _deadline_s if _deadline_s > 0 else None   # DURATION of the generation loop (engine starts the clock after the prompt)

        try:
            result = worker.engine.generate(
                prompt_tokens=prompt_tokens,
                max_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                stop_tokens=stop_tokens,
                gravity_stride=gravity_stride,
                deadline=_deadline,
            )
            if result.get("deadline_hit"):
                _log(f"[GPUPortal:{self.portal_id}] generation hit the {_deadline_s:.0f}s deadline "
                     f"after {len(result.get('tokens', []))} tokens (of {max_tokens}) -- returning partial")
        except Exception as e:
            if self.battery:
                self.battery.record_failure(0.05)
            return {"status": "error", "message": f"Generation error: {e}"}

        elapsed = time.time() - t0

        if result.get("status") in ("ok", "max_reached", "stop_token"):
            generated = result.get("tokens", result.get("generated_tokens", []))
            text = result.get("text", result.get("generated_text", ""))
            self._tokens_generated += len(generated)
            self._requests_processed += 1

            if self.battery:
                self.battery.record_success(0.01)

            return {
                "status": "ok",
                "tokens": generated,
                "text": text,
                "tokens_generated": len(generated),
                "battery_cost": battery_cost,
                "elapsed_ms": round(elapsed * 1000, 1),
                "worker_id": worker.worker_id,
                "worker_charge": round(worker.bcu.charge_level, 3),
                "tok_per_sec": round(len(generated) / max(elapsed, 0.001), 1),
            }
        else:
            if self.battery:
                self.battery.record_failure(0.03)
            return {
                "status": result.get("status", "error"),
                "message": result.get("message", "Generation failed"),
                "worker_id": worker.worker_id,
            }

    def _handle_generate_text(self, request: Dict) -> Dict:
        """Generate from text prompt (tokenizes internally).

        Request:
            {"cmd": "generate_text", "prompt": "Hello world",
             "max_tokens": 50, ...}
        """
        prompt = request.get("prompt", "")
        if not prompt:
            return {"status": "error", "message": "Empty prompt"}

        # Try to tokenize
        try:
            tokens = self._tokenize(prompt)
        except Exception as e:
            return {"status": "error",
                    "message": f"Tokenization failed: {e}"}

        # Forward to token-level generate
        request["prompt_tokens"] = tokens
        request["cmd"] = "generate"
        result = self._handle_generate(request)

        # Decode output tokens
        if result.get("status") == "ok" and result.get("tokens"):
            try:
                result["text"] = self._detokenize(result["tokens"])
            except Exception as e:
                _log(f"[GPUPortal] Detokenize error: {e}")

        return result

    def _handle_forward(self, request: Dict) -> Dict:
        """Forward a single token (low-level).

        Request:
            {"cmd": "forward", "token_id": 42, "worker_id": 0}

        Response:
            {"status": "ok", "logits": [...], ...}
        """
        token_id = request.get("token_id", 0)
        worker_id = request.get("worker_id", 0)
        gravity_stride = request.get("gravity_stride", 1)

        worker = self._pick_worker(worker_id)
        if worker is None:
            return {"status": "error", "message": "Worker not available"}

        result = worker.engine.forward_one_token(
            token_id=token_id,
            gravity_stride=gravity_stride,
        )

        if result.get("status") in ("ok", "max_reached", "stop_token"):
            # Don't send full logits array over pipe — too large
            # Send top-k indices and values instead
            import numpy as np
            logits = result.get("logits")
            if logits is not None:
                top_k = min(50, len(logits))
                top_indices = np.argpartition(logits, -top_k)[-top_k:]
                top_indices = top_indices[np.argsort(logits[top_indices])[::-1]]
                result["top_tokens"] = [
                    {"id": int(idx), "logit": round(float(logits[idx]), 4)}
                    for idx in top_indices[:20]
                ]
                del result["logits"]  # Don't serialize the full array

        self._requests_processed += 1
        return result

    def _handle_status(self, request: Dict) -> Dict:
        """Portal status."""
        import torch

        vram_used = torch.cuda.memory_allocated(0) / (1024**3)
        vram_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)

        farm_status = {}
        if self.farm:
            farm_status = {
                "num_workers": len(self.farm.workers),
                "workers": [
                    {
                        "id": w.worker_id,
                        "state": w.state.value,
                        "charge": round(w.bcu.charge_level, 3),
                        "tokens": w.stats.tokens_generated,
                    }
                    for w in self.farm.workers
                ],
                "gravity": round(self.farm.gravity, 3) if hasattr(self.farm, 'gravity') else 0,
            }

        return {
            "status": "ok",
            "portal_id": self.portal_id,
            "pid": os.getpid(),
            "gravity_alpha": self.gravity,
            "model": {
                "portal_file": self.portal_file,
                "n_layer": self.model_config.n_layer if self.model_config else 0,
                "n_embd": self.model_config.n_embd if self.model_config else 0,
                "vocab_size": self.model_config.vocab_size if self.model_config else 0,
            },
            "gpu": {
                "device": torch.cuda.get_device_name(0),
                "vram_used_gb": round(vram_used, 2),
                "vram_total_gb": round(vram_total, 2),
                "vram_free_gb": round(vram_total - vram_used, 2),
            },
            "battery": self.battery.status() if self.battery else None,
            "farm": farm_status,
            "stats": {
                "requests_processed": self._requests_processed,
                "tokens_generated": self._tokens_generated,
                "boot_time_s": round(self._boot_time, 1),
            },
        }

    def _handle_energy(self, request: Dict) -> Dict:
        """Receive energy from host — recharge battery."""
        amount = request.get("amount", 0.1)
        if self.battery:
            self.battery.receive_energy(amount)
        return {
            "status": "ok",
            "battery": self.battery.status() if self.battery else None,
        }

    def _handle_reset_states(self, request: Dict) -> Dict:
        """Reset RWKV states for all or specific workers."""
        worker_id = request.get("worker_id", None)

        if worker_id is not None and self.farm:
            if 0 <= worker_id < len(self.farm.workers):
                self.farm.workers[worker_id].engine.init_all_states()
                return {"status": "ok", "reset": [worker_id]}
        elif self.farm:
            for w in self.farm.workers:
                w.engine.init_all_states()
            return {"status": "ok", "reset": list(range(len(self.farm.workers)))}

        return {"status": "error", "message": "No farm"}

    # ── Worker Selection ──────────────────────────────────────────────────

    def _pick_worker(self, worker_id: Optional[int] = None):
        """Pick a worker for inference.

        If worker_id specified, use that worker.
        Otherwise, pick the worker with highest charge (relay pattern).
        """
        if not self.farm or not self.farm.workers:
            return None

        if worker_id is not None:
            if 0 <= worker_id < len(self.farm.workers):
                return self.farm.workers[worker_id]
            return None

        # Pick highest-charge worker
        best = max(self.farm.workers, key=lambda w: w.bcu.charge_level)
        if best.bcu.charge_level < 0.01:
            return None  # All depleted

        return best

    # ── Tokenizer ─────────────────────────────────────────────────────────

    _tokenizer = None

    def _load_tokenizer(self):
        """Load the RWKV world tokenizer (TRIE_TOKENIZER)."""
        if self._tokenizer is not None:
            return

        # Find vocab file relative to this script or project
        here = Path(__file__).parent
        candidates = [
            here.parent / "research_repos" / "RWKV-LM" / "RWKV-v7" / "rwkv_vocab_v20230424.txt",
            here.parent / "research_repos" / "RWKV-LM" / "RWKV-v5" / "tokenizer" / "rwkv_vocab_v20230424.txt",
        ]
        tokenizer_script = (
            here.parent / "research_repos" / "RWKV-LM" / "RWKV-v5" / "tokenizer" / "rwkv_tokenizer.py"
        )

        vocab_path = None
        for c in candidates:
            if c.exists():
                vocab_path = c
                break

        if vocab_path and tokenizer_script.exists():
            # Import TRIE_TOKENIZER from the research repo
            import importlib.util
            spec = importlib.util.spec_from_file_location("rwkv_tokenizer", str(tokenizer_script))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._tokenizer = mod.TRIE_TOKENIZER(str(vocab_path))
            _log(f"[GPUPortal] Loaded RWKV tokenizer from {vocab_path.name}")
        else:
            _log(f"[GPUPortal] WARNING: RWKV tokenizer not found, using UTF-8 byte fallback")

    def _tokenize(self, text: str) -> List[int]:
        """Tokenize text using RWKV world tokenizer."""
        self._load_tokenizer()
        if self._tokenizer is not None:
            return self._tokenizer.encode(text)
        return list(text.encode('utf-8'))

    def _detokenize(self, tokens: List[int]) -> str:
        """Detokenize token IDs back to text."""
        self._load_tokenizer()
        if self._tokenizer is not None:
            return self._tokenizer.decode(tokens)
        return bytes([t & 0xFF for t in tokens]).decode('utf-8', errors='replace')

    # ── Main Loop ─────────────────────────────────────────────────────────

    def run_stdio(self, json_out=None):
        """Run the portal reading from stdin, writing JSON to json_out.

        Same JSON-per-line protocol as portal_interior.py.
        The host spawns us as a subprocess and communicates via pipes.

        Args:
            json_out: File object for JSON responses (default: sys.stdout).
                      In subprocess mode, this should be the REAL stdout
                      saved before sys.stdout was redirected to stderr.
        """
        if json_out is None:
            json_out = sys.stdout

        self._running = True
        _log(f"[GPUPortal:{self.portal_id}] Entering stdio loop (pid={os.getpid()})")

        # Tick thread -- battery heartbeat
        tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        tick_thread.start()

        for line in sys.stdin:
            if not self._running:
                break
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.process_request(request)
                json_out.write(json.dumps(response) + '\n')
                json_out.flush()
                if not self._running:
                    break
            except json.JSONDecodeError as e:
                error_resp = {"status": "error", "message": f"JSON parse error: {e}"}
                json_out.write(json.dumps(error_resp) + '\n')
                json_out.flush()
            except Exception as e:
                error_resp = {"status": "error", "message": str(e)}
                json_out.write(json.dumps(error_resp) + '\n')
                json_out.flush()

        _log(f"[GPUPortal:{self.portal_id}] Stdio loop ended")

    def _tick_loop(self):
        """Background tick — battery heartbeat + farm recharge."""
        while self._running:
            try:
                time.sleep(1.0)
                if self.battery:
                    self.battery.tick()
            except Exception:
                pass

    # ── Shutdown ──────────────────────────────────────────────────────────

    def _rwkv_state_dir(self) -> str:
        """Where per-worker RWKV recurrent state lives between boots (2026-09-11)."""
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(_root, "state", "rwkv_state", str(self.portal_id))

    def shutdown(self):
        """Graceful shutdown — release VRAM, stop farm."""
        _log(f"[GPUPortal:{self.portal_id}] Shutting down...")
        self._running = False
        _t_sd = time.time()   # 2026-09-12: the gate terminated us mid-shutdown once; time each step

        # Stop farm recharge loop
        if self.farm:
            try:
                self.farm.stop_recharge_loop()
            except Exception:
                pass

        # -- RWKV STATE SAVE (2026-09-11, Nous+Ace; env-gated) -----------------------
        # Must run while self.farm still exists (it is set to None below). One .npz per
        # worker, restored to the same index on the next boot. See boot() step 4b.
        if os.environ.get("AKASHIC_RWKV_PERSIST", "") == "1" and self.farm:
            try:
                _rs_dir = self._rwkv_state_dir()
                os.makedirs(_rs_dir, exist_ok=True)
                _saved = 0
                for _i, _w in enumerate(getattr(self.farm, "workers", []) or []):
                    try:
                        _w.engine.save_state_to_disk(
                            os.path.join(_rs_dir, f"rwkv_worker_{_i}.npz"))
                        _saved += 1
                    except Exception as _e:
                        _log(f"[GPUPortal:{self.portal_id}] RWKV state worker {_i} "
                             f"NOT saved: {str(_e)[:120]}")
                _log(f"[GPUPortal:{self.portal_id}] RWKV STATE SAVE: "
                     f"{_saved} worker states -> {_rs_dir} ({time.time() - _t_sd:.1f}s after shutdown began)")
            except Exception as _e:
                _log(f"[GPUPortal:{self.portal_id}] RWKV state save skipped: {_e}")

        # Clear GPU weight cache
        import torch
        if self.weight_store:
            ws_id = id(self.weight_store)
            from rwkv_gpu_engine import RWKVGPUBatteryEngine
            if ws_id in RWKVGPUBatteryEngine._gpu_weight_cache:
                del RWKVGPUBatteryEngine._gpu_weight_cache[ws_id]

        # Release VRAM
        self.gpu_weights = None
        self.farm = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        _log(f"[GPUPortal:{self.portal_id}] VRAM released. "
             f"Processed {self._requests_processed} requests, "
             f"generated {self._tokens_generated} tokens. "
             f"(shutdown took {time.time() - _t_sd:.1f}s)")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI — Run as subprocess
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Entry point when run as a subprocess.

    Usage:
        python gpu_inference_portal.py --portal <path.portal> --workers 4 --gravity 2.0

    The host spawns us with:
        subprocess.Popen(
            [sys.executable, "infrastructure/gpu_inference_portal.py",
             "--portal", portal_path,
             "--workers", "4",
             "--gravity", "2.0"],
            stdin=PIPE, stdout=PIPE, stderr=PIPE
        )
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="GPU Inference Portal — The Dimension That Thinks"
    )
    parser.add_argument("--portal", required=True,
                        help="Path to .portal weight file (PRWK format)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of farm workers (default: 4)")
    parser.add_argument("--gravity", type=float, default=GRAVITY_INT8,
                        help=f"Portal gravity α (1.0=FP16, 1.5=INT8, 2.0=INT4). "
                             f"Default: {GRAVITY_INT8}")
    parser.add_argument("--token-budget", type=int, default=100_000,
                        help="Battery token budget (default: 100000)")
    parser.add_argument("--portal-id", default="gpu-inference",
                        help="Portal identifier")
    parser.add_argument("--flops-budget", type=int, default=500_000_000,
                        help="FLOPS budget per worker (default: 500M)")
    parser.add_argument("--max-charge", type=float, default=20.0,
                        help="Max charge per worker battery (default: 20.0)")
    parser.add_argument("--recharge-rate", type=float, default=0.01,
                        help="Worker recharge rate per tick (default: 0.01)")
    parser.add_argument("--host-port", type=int, default=0,
                        help="Host PostalTunnel port (0 = no host connection)")

    args = parser.parse_args()

    # ── CRITICAL: Isolate stdout for JSON IPC only ────────────────────────
    # The engine and other modules use print() which goes to stdout.
    # In subprocess mode, stdout IS the JSON pipe. Stray prints corrupt it.
    # Solution: save real stdout for JSON, redirect sys.stdout to stderr.
    _json_out = sys.stdout                # the REAL pipe to host
    sys.stdout = sys.stderr               # all print() now goes to stderr

    # Validate portal path
    if not os.path.exists(args.portal):
        print(f"FATAL: Portal file not found: {args.portal}")
        sys.exit(1)

    # Create portal
    portal = GPUInferencePortal(
        portal_file=args.portal,
        num_workers=args.workers,
        gravity=args.gravity,
        token_budget=args.token_budget,
        portal_id=args.portal_id,
        flops_budget=args.flops_budget,
        max_charge=args.max_charge,
        recharge_rate=args.recharge_rate,
        host_port=args.host_port,
    )

    # Boot
    if not portal.boot():
        print("FATAL: Boot failed", file=sys.stderr)
        sys.exit(1)

    # Handle SIGTERM gracefully
    def _sigterm_handler(signum, frame):
        portal.shutdown()
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, _sigterm_handler)
    except (ValueError, OSError):
        pass  # Can't set signal handler in some contexts

    # Run stdio loop (pass the REAL stdout for JSON output)
    try:
        portal.run_stdio(json_out=_json_out)
    except KeyboardInterrupt:
        pass
    finally:
        portal.shutdown()


if __name__ == "__main__":
    main()
