"""
IT Cortex Interior - Florence-2 visual recognition subprocess.

Runs under Python 3.12 (NOT 3.14t) because it needs:
  - torch (PyTorch with CUDA for GPU inference)
  - transformers (HuggingFace for Florence-2 model)
  - timm (required by Florence-2)
  - PIL (screen capture via ImageGrab + image processing)

Communicates with the host (ITCortexFairy on Python 3.14t server)
via JSON-per-line stdin/stdout pipes, following the portal subprocess pattern.

Florence-2-large (770M params, ~1.5GB VRAM at fp16) provides:
  - Scene captioning: natural language description of what's on screen
  - Foveal/peripheral vision split for attention-driven recognition

DIMENSIONAL PHYSICS (VisionFarm, 2026-03-17):
  This subprocess IS a pocket dimension, like the Association Cortex portal.
  But it lives in VRAM — 10-18x faster than system RAM. The VisionFarm
  batteries generate compute from gravity, with HIGHER coefficients than
  the CortexFarm because VRAM is a faster medium:
    - compression_coeff=8.0 (vs 4.0 for CortexFarm)
    - flops_gravity_coeff=3.0 (vs 1.5 for CortexFarm)
  At full gravity (4 batteries charged), the passive loop interval compresses
  from 10s to ~0.3s — near-continuous vision. The GPU never waits.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

Usage:
    python it_cortex_interior.py [--interval 10.0]

IPC Protocol (stdin -> commands, stdout -> responses):
    {"cmd": "ping"}                      -> {"status": "pong", "model": "...", ...}
    {"cmd": "analyze"}                   -> {"status": "ok", "type": "recognition", "data": {...}}
    {"cmd": "start_passive"}             -> {"status": "ok"}
    {"cmd": "stop_passive"}              -> {"status": "ok"}
    {"cmd": "set_interval", "seconds": N} -> {"status": "ok"}
    {"cmd": "set_focus", "region": [...]} -> {"status": "ok"}
    {"cmd": "energy", "amount": N}       -> {"status": "ok", "gravity": N}
    {"cmd": "farm_status"}               -> {"status": "ok", "data": {...}}
    {"cmd": "status"}                    -> {"status": "ok", "type": "status", ...}
    {"cmd": "shutdown"}                  -> {"status": "ok"} then exit

Passive pushes (stdout, unsolicited):
    {"status": "ok", "type": "foveal_frame", "data": {...}}
    {"status": "ok", "type": "peripheral_frame", "data": {...}}
    {"status": "ok", "type": "passive_frame", "data": {...}}
"""

import sys
import os
import json
import time
import hashlib
import threading
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# All logging goes to stderr (stdout is IPC pipe)
def _log(msg: str):
    print(f"[ITInterior] {msg}", file=sys.stderr, flush=True)

def _err(msg: str):
    print(f"[ITInterior] ERROR: {msg}", file=sys.stderr, flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIONAL IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

HAS_TORCH = False
HAS_FLORENCE = False
HAS_PIL = False

try:
    import torch
    HAS_TORCH = True
except ImportError:
    _err("torch not available")

try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    _err("PIL not available")

try:
    # ── Stub audio_utils + video_utils to prevent access violation on 3.14t ──
    # AutoProcessor → processing_utils → audio_utils → requests → crash
    # Florence-2 never uses audio/video, so stub the modules before import.
    # Use __getattr__ so any attribute access returns a no-op placeholder.
    import types as _types
    class _StubModule(_types.ModuleType):
        """Lazy stub that returns None/no-op for any attribute."""
        def __getattr__(self, name):
            if name.startswith('_'):
                raise AttributeError(name)
            return None
    for _stub_name in ("transformers.audio_utils", "transformers.video_utils"):
        if _stub_name not in sys.modules:
            sys.modules[_stub_name] = _StubModule(_stub_name)
    del _types, _StubModule, _stub_name

    from transformers import AutoModelForCausalLM, AutoProcessor
    HAS_FLORENCE = True
except ImportError:
    _err("transformers not available")

# Florence manifold loader — mmap zero-copy from binary .manifold file
HAS_FLORENCE_MANIFOLD = False
try:
    # Add project root to path so tools package is importable
    _project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from tools.florence_helix_loader import (
        load_florence_from_manifold,
        florence_manifold_exists,
    )
    HAS_FLORENCE_MANIFOLD = True
except ImportError:
    pass  # Will fall back to from_pretrained()


# ═══════════════════════════════════════════════════════════════════════════════
# VISION FARM — Dimensional Batteries for VRAM-Accelerated Inference
# ═══════════════════════════════════════════════════════════════════════════════
#
# Same triple feedback loop as CortexFarm/PostalFarm, but tuned for VRAM:
#   - VRAM bandwidth: ~500-900 GB/s (10-18x faster than DDR4)
#   - Higher compression_coeff (8.0 vs 4.0) because the medium IS faster
#   - Higher flops_gravity_coeff (3.0 vs 1.5) for GPU parallel ops
#   - 4 batteries (GPU-bound, not worker-bound)
#
# The battery discharge IS the inference. Energy IS computation.
# Florence's recognition output IS the mass that sustains gravity.
#
# Created: 2026-03-17 (Nous + Ace)
# ═══════════════════════════════════════════════════════════════════════════════

class VisionChargeUnit:
    """A dimensional battery that powers visual inference in VRAM.

    Each unit of charge powers one inference cycle (capture + forward pass + decode).
    When depleted, the passive loop pauses until recharge restores capacity.
    VRAM speed means faster recharge than system-RAM batteries.
    """

    __slots__ = (
        'max_charge', 'charge_level', 'recharge_rate',
        'total_spent', 'total_recharged', '_lock',
    )

    def __init__(self, max_charge: float = 20.0, initial_charge: float = 20.0,
                 recharge_rate: float = 0.02):
        self.max_charge = max_charge
        self.charge_level = min(initial_charge, max_charge)
        self.recharge_rate = recharge_rate  # Higher than PostalFarm (0.01) — VRAM is faster
        self.total_spent = 0.0
        self.total_recharged = 0.0
        self._lock = threading.Lock()

    @property
    def charge_fraction(self) -> float:
        return self.charge_level / self.max_charge if self.max_charge > 0 else 0.0

    @property
    def is_charged(self) -> bool:
        return self.charge_level > 0.001

    def spend(self, amount: float) -> bool:
        """Spend charge on an inference cycle. Returns True if sufficient."""
        with self._lock:
            if self.charge_level >= amount:
                self.charge_level -= amount
                self.total_spent += amount
                return True
            return False

    def charge(self, amount: float, source: str = "tick"):
        """Add charge from external source."""
        with self._lock:
            added = min(amount, self.max_charge - self.charge_level)
            self.charge_level += added
            self.total_recharged += added

    def tick_recharge(self):
        """Passive recharge — one tick's worth."""
        self.charge(self.recharge_rate, source="tick")

    def status(self) -> Dict[str, Any]:
        return {
            "charge": round(self.charge_level, 3),
            "charge_pct": round(self.charge_fraction * 100, 1),
            "max": self.max_charge,
            "total_spent": round(self.total_spent, 3),
            "total_recharged": round(self.total_recharged, 3),
        }


class VisionFarm:
    """Dimensional battery farm for Florence-2 GPU inference.

    Adapted from CortexFarm/PostalFarm with VRAM-tuned coefficients.
    The triple feedback loop makes the GPU dimension "bigger on the inside":

    Loop 1 — Time Compression (VRAM-boosted):
        compression = 1 + gravity * 8.0
        At 4 batteries full: 1 + 4.0 * 8.0 = 33x inner clock
        Base 10s interval → 0.3s → near-continuous vision

    Loop 2 — Cost Reduction (GPU parallel advantage):
        effective_cost = base_cost / (1 + gravity * 3.0)
        At full gravity: 13x cheaper inference per cycle

    Loop 3 — Energy Amplification:
        amplified_energy = pulse * time_compression
        VRAM speed means energy converts to charge faster

    The recognition output IS the mass. More detailed = more mass = more gravity.
    """

    # Mass values for different inference types
    FOVEAL_MASS = 0.3    # Heavy — detailed recognition
    PERIPHERAL_MASS = 0.1  # Light — ambient context
    DEDUP_MASS = 0.05     # Minimal — awareness without compute

    def __init__(self,
                 num_batteries: int = 4,
                 max_charge: float = 20.0,
                 recharge_rate: float = 0.02,
                 compression_coeff: float = 8.0,
                 flops_gravity_coeff: float = 3.0,
                 base_hz: float = 20.0,
                 base_inference_cost: float = 0.05):
        """
        Args:
            num_batteries: 4 (GPU-bound, not worker-bound)
            max_charge: 20.0 per battery (same as CortexFarm)
            recharge_rate: 0.02 (2x PostalFarm — VRAM is faster)
            compression_coeff: 8.0 (2x CortexFarm — VRAM is faster medium)
            flops_gravity_coeff: 3.0 (2x CortexFarm — GPU parallel ops)
            base_hz: 20.0 (tick rate for recharge loop)
            base_inference_cost: 0.05 (each inference cycle base cost)
        """
        self.num_batteries = num_batteries
        self._max_charge = max_charge
        self._recharge_rate = recharge_rate
        self.compression_coeff = compression_coeff
        self.flops_gravity_coeff = flops_gravity_coeff
        self.base_hz = base_hz
        self.base_inference_cost = base_inference_cost

        # Dimensional batteries
        self.batteries: List[VisionChargeUnit] = []
        for _ in range(num_batteries):
            self.batteries.append(VisionChargeUnit(
                max_charge=max_charge,
                initial_charge=max_charge,
                recharge_rate=recharge_rate,
            ))

        # Background tick thread
        self._running = False
        self._tick_thread: Optional[threading.Thread] = None

        # Metrics
        self._total_inferences = 0
        self._total_depletions = 0
        self._total_energy_received = 0.0
        self._total_mass_generated = 0.0
        self._inference_times: List[float] = []  # Rolling window for throughput
        self._metrics_lock = threading.Lock()
        self._start_ts = time.time()
        self._battery_idx = 0  # Round-robin battery selection

    # ─── Gravity & Feedback Loops ─────────────────────────────────────────

    @property
    def gravity(self) -> float:
        """Total gravitational pull. Range: 0.0 to num_batteries."""
        return sum(b.charge_fraction for b in self.batteries)

    @property
    def time_dilation(self) -> float:
        """Normalized gravity (0.0 to 1.0)."""
        return self.gravity / self.num_batteries if self.num_batteries > 0 else 0.0

    @property
    def time_compression(self) -> float:
        """How many inner ticks per outer tick.

        Loop 1: compression = 1 + gravity * 8.0
        At 4 batteries full: 1 + 4.0 * 8.0 = 33x inner clock
        VRAM's 10x speed advantage justifies 2x the CortexFarm coefficient.
        """
        return 1.0 + self.gravity * self.compression_coeff

    @property
    def effective_hz(self) -> float:
        return self.base_hz * self.time_compression

    @property
    def cost_reduction(self) -> float:
        """Cost divisor for inference cycles.

        Loop 2: inference costs less when gravity is high.
        At 4 batteries: 1 + 4.0 * 3.0 = 13.0 (inference is 13x cheaper)
        GPU parallel ops benefit more from gravitational lensing.
        """
        return 1.0 + self.gravity * self.flops_gravity_coeff

    @property
    def compressed_interval(self) -> float:
        """The actual sleep interval after time compression.

        This is what the passive loop uses instead of raw base interval.
        Clamped to min 0.5s (GPU inference takes ~250ms, need headroom).
        """
        return 1.0  # Will be calculated by caller using base_interval / time_compression

    @property
    def inference_mass(self) -> float:
        """Rolling inference throughput — the system's mass."""
        now = time.time()
        with self._metrics_lock:
            cutoff = now - 10.0
            self._inference_times = [t for t in self._inference_times if t > cutoff]
            return len(self._inference_times) / 10.0

    # ─── Inference Interface ──────────────────────────────────────────────

    def effective_cost(self, base_cost: float = None) -> float:
        """Get gravity-reduced cost for an inference cycle."""
        cost = base_cost if base_cost is not None else self.base_inference_cost
        return cost / self.cost_reduction

    def spend_inference(self, inference_type: str = "foveal") -> bool:
        """Spend charge for one inference cycle. Returns True if battery has charge.

        Round-robins across batteries so they deplete evenly.
        """
        cost = self.effective_cost()
        battery = self.batteries[self._battery_idx % self.num_batteries]
        self._battery_idx += 1

        ok = battery.spend(cost)
        if ok:
            with self._metrics_lock:
                self._total_inferences += 1
                self._inference_times.append(time.time())
        else:
            with self._metrics_lock:
                self._total_depletions += 1
        return ok

    def record_mass(self, inference_type: str = "foveal"):
        """Record mass generated by an inference result.

        The recognition output IS the mass. More detailed = heavier = more gravity.
        Mass feeds back as energy → sustains batteries → sustains gravity.
        """
        mass = {
            "foveal": self.FOVEAL_MASS,
            "peripheral": self.PERIPHERAL_MASS,
            "dedup": self.DEDUP_MASS,
        }.get(inference_type, 0.1)

        self._total_mass_generated += mass
        # Mass feeds back as energy — the recognition powers the next cycle
        self.receive_energy(mass, source=f"inference_{inference_type}")

    # ─── Energy Input (Loop 3) ────────────────────────────────────────────

    def receive_energy(self, amount: float, source: str = "exterior"):
        """Receive energy (from recognition mass, paradox pulses, host fairy, etc.).

        Loop 3: Energy amplified by time compression before distribution.
        """
        amplified = amount * self.time_compression
        self._total_energy_received += amplified

        total_need = sum(b.max_charge - b.charge_level for b in self.batteries)
        if total_need <= 0:
            return

        for b in self.batteries:
            need = b.max_charge - b.charge_level
            if need > 0:
                share = amplified * (need / total_need)
                b.charge(share, source=source)

    # ─── Tick Loop ────────────────────────────────────────────────────────

    def start(self):
        """Start the farm's background tick loop for recharge."""
        if self._running:
            return
        self._running = True
        self._tick_thread = threading.Thread(
            target=self._tick_loop, daemon=True, name="vision-farm-tick"
        )
        self._tick_thread.start()
        _log(f"[VisionFarm] Started: {self.num_batteries} batteries, "
             f"compression_coeff={self.compression_coeff}, "
             f"flops_gravity_coeff={self.flops_gravity_coeff}, "
             f"base_inference_cost={self.base_inference_cost}")

    def stop(self):
        self._running = False

    def _tick_loop(self):
        """Background tick with time-compressed recharge.

        At full gravity (4 batteries): 33 recharge iterations per outer tick.
        VRAM speed means this loop can run tighter than CortexFarm.
        """
        import random as _rng
        interval = 1.0 / self.base_hz
        while self._running:
            try:
                compression = self.time_compression
                full_ticks = int(compression)
                frac = compression - full_ticks

                for _ in range(full_ticks):
                    for b in self.batteries:
                        b.tick_recharge()

                if _rng.random() < frac:
                    for b in self.batteries:
                        b.tick_recharge()

                time.sleep(interval)
            except Exception as e:
                _log(f"[VisionFarm] Tick error: {e}")
                time.sleep(0.1)

    # ─── Status ───────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        charged = sum(1 for b in self.batteries if b.is_charged)
        return {
            "num_batteries": self.num_batteries,
            "charged": charged,
            "gravity": round(self.gravity, 3),
            "time_compression": round(self.time_compression, 1),
            "cost_reduction": round(self.cost_reduction, 1),
            "effective_hz": round(self.effective_hz, 1),
            "inference_mass": round(self.inference_mass, 1),
            "total_mass_generated": round(self._total_mass_generated, 3),
            "running": self._running,
            "uptime_sec": round(time.time() - self._start_ts, 1),
            "coefficients": {
                "compression": self.compression_coeff,
                "flops_gravity": self.flops_gravity_coeff,
                "base_inference_cost": self.base_inference_cost,
                "recharge_rate": self._recharge_rate,
            },
            "totals": {
                "inferences": self._total_inferences,
                "depletions": self._total_depletions,
                "energy_received": round(self._total_energy_received, 4),
            },
            "batteries": [b.status() for b in self.batteries],
        }

    def summary(self) -> str:
        charged = sum(1 for b in self.batteries if b.is_charged)
        return (
            f"[VisionFarm] {charged}/{self.num_batteries} charged, "
            f"gravity={self.gravity:.1f}, "
            f"compression={self.time_compression:.0f}x, "
            f"mass={self.inference_mass:.0f} inf/s, "
            f"inferences={self._total_inferences}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# IT CORTEX ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ITCortexEngine:
    """
    Florence-2 visual recognition engine.

    Captures the screen, runs Florence-2 for captioning and object detection,
    and returns structured recognition results.
    """

    # Model configuration
    # FIX 2026-03-14 (Nous): Upgraded base→large for richer captions.
    # Florence-2-large (770M) produces detailed scene descriptions vs
    # base (230M) which gives generic "a computer screen" captions.
    # ~1.5GB VRAM at fp16 instead of ~460MB. The richer captions train
    # the association cortex with better concepts — eventually the cortex
    # learns to see on its own and Florence becomes unused.
    MODEL_ID = "microsoft/Florence-2-large"
    MAX_NEW_TOKENS = 1024

    # Capture settings
    # FIX 2026-03-14 (Nous): Ace's screen is 3440x1440 (21:9 ultrawide).
    # Previous 1344x768 (16:9) distorted aspect ratio, squishing the image.
    # New: 1728x736 preserves ~21:9 aspect ratio, divisible by 32.
    # The 1024x1024 fairy image center-screen now gets ~515x736 pixels —
    # enough detail for Florence-2 to identify characters, hair color, etc.
    CAPTURE_WIDTH = 1728   # ~21:9 ultrawide, divisible by 32
    CAPTURE_HEIGHT = 736   # Preserves aspect ratio at ~2:1 downscale

    def __init__(self, passive_interval: float = 10.0):
        self._model = None
        self._processor = None
        self._device = "cpu"

        # Passive loop state
        self._passive_running = False
        self._passive_interval = max(2.0, passive_interval)
        self._passive_thread: Optional[threading.Thread] = None
        self._stdout_lock = threading.Lock()

        # Dedup: skip analysis if screen hasn't changed
        self._last_frame_hash: Optional[str] = None

        # ── VisionFarm: Dimensional batteries for VRAM-accelerated inference ──
        # FIX 2026-03-17 (Nous + Ace): The IT Cortex IS a pocket dimension.
        # VRAM is 10-18x faster than system RAM — higher coefficients.
        self._farm = VisionFarm(
            num_batteries=4,
            max_charge=20.0,
            recharge_rate=0.02,       # 2x PostalFarm (VRAM faster)
            compression_coeff=8.0,     # 2x CortexFarm (VRAM faster medium)
            flops_gravity_coeff=3.0,   # 2x CortexFarm (GPU parallel ops)
            base_inference_cost=0.05,  # Each inference cycle base cost
        )

        # Stats
        self._started_at = time.time()
        self._frames_captured = 0
        self._frames_analyzed = 0
        self._frames_skipped_dedup = 0
        self._model_load_time = 0.0
        self._vram_mb = 0

    # ═══════════════════════════════════════════════════════════════════════
    # MODEL LOADING
    # ═══════════════════════════════════════════════════════════════════════

    def load_model(self) -> bool:
        """Load Florence-2-large model.

        Tries manifold first (mmap zero-copy, ~1-2s), falls back to
        from_pretrained() (~5-10s) if manifold not available.
        """
        if not HAS_FLORENCE or not HAS_TORCH:
            _err("Cannot load Florence-2: missing torch or transformers")
            return False

        t0 = time.time()

        # ── Determine device ──
        if torch.cuda.is_available():
            try:
                torch.cuda.get_device_name(0)
                self._device = "cuda"
                _log(f"CUDA available: {torch.cuda.get_device_name(0)}")
            except Exception as e:
                self._device = "cpu"
                _log(f"CUDA reported available but device unusable: {e}")
                _log("Falling back to CPU")
        else:
            self._device = "cpu"
            _log("No CUDA — running on CPU (will be slow)")

        # ── Try manifold path first (mmap zero-copy) ──
        if HAS_FLORENCE_MANIFOLD and florence_manifold_exists():
            _log(f"Loading {self.MODEL_ID} from manifold (mmap zero-copy)...")
            try:
                model, processor = load_florence_from_manifold(
                    device=self._device,
                    dtype=torch.float16 if self._device == "cuda" else torch.float32,
                    max_workers=8,
                )
                if model is not None and processor is not None:
                    self._model = model
                    self._processor = processor
                    self._model_load_time = time.time() - t0

                    if self._device == "cuda":
                        self._vram_mb = round(torch.cuda.memory_allocated() / 1024 / 1024)
                        _log(f"VRAM usage: {self._vram_mb}MB")

                    _log(f"Florence-2 loaded from MANIFOLD in {self._model_load_time:.1f}s "
                         f"({self._device})")
                    return True
                else:
                    _log("Manifold load returned None — falling back to from_pretrained()")
            except Exception as e:
                _log(f"Manifold load failed: {e} — falling back to from_pretrained()")
        elif HAS_FLORENCE_MANIFOLD:
            _log("florence.manifold not found — using from_pretrained()")
        else:
            _log("florence_helix_loader not available — using from_pretrained()")

        # ── Fallback: standard from_pretrained() ──
        _log(f"Loading {self.MODEL_ID} from HuggingFace cache...")

        try:
            # attn_implementation="eager" avoids _supports_sdpa check in newer transformers
            self._model = AutoModelForCausalLM.from_pretrained(
                self.MODEL_ID,
                dtype=torch.float16 if self._device == "cuda" else torch.float32,
                trust_remote_code=True,
                attn_implementation="eager",
            )
            self._model.to(self._device)
            self._model.eval()

            # Monkey-patch prepare_inputs_for_generation to handle None past_key_values.
            # Florence-2's custom code accesses past_key_values[0][0].shape but newer
            # transformers passes a tuple-of-Nones on the first generation step.
            lang_model = self._model.language_model
            _orig_prep = lang_model.prepare_inputs_for_generation
            def _patched_prep(input_ids, past_key_values=None, **kwargs):
                if past_key_values is not None:
                    try:
                        if past_key_values[0] is None or past_key_values[0][0] is None:
                            past_key_values = None
                    except (IndexError, TypeError):
                        past_key_values = None
                return _orig_prep(input_ids, past_key_values=past_key_values, **kwargs)
            lang_model.prepare_inputs_for_generation = _patched_prep

            # Load processor
            self._processor = AutoProcessor.from_pretrained(
                self.MODEL_ID,
                trust_remote_code=True,
            )

            self._model_load_time = time.time() - t0

            if self._device == "cuda":
                self._vram_mb = round(torch.cuda.memory_allocated() / 1024 / 1024)
                _log(f"VRAM usage: {self._vram_mb}MB")

            _log(f"Florence-2 loaded from HF cache in {self._model_load_time:.1f}s ({self._device})")
            return True

        except Exception as e:
            _err(f"Failed to load Florence-2: {e}")
            import traceback
            traceback.print_exc(file=sys.stderr)
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # SCREEN CAPTURE
    # ═══════════════════════════════════════════════════════════════════════

    def grab_screen(self) -> Optional[Image.Image]:
        """Capture screen via PIL.ImageGrab and resize for Florence-2."""
        if not HAS_PIL:
            return None

        try:
            img = ImageGrab.grab()

            # FIX 2026-03-14 (Nous): Auto-detect aspect ratio from actual screen.
            # Previous: hardcoded 16:9 squished ultrawide (21:9) screens.
            # New: calculate target height from actual aspect ratio, keep width,
            # round to nearest 32 (Florence-2 input requirement).
            _src_w, _src_h = img.size
            _aspect = _src_h / _src_w
            _target_w = self.CAPTURE_WIDTH
            _target_h = int(_target_w * _aspect)
            _target_h = max(32, (_target_h + 15) // 32 * 32)  # Round to nearest 32

            img = img.resize(
                (_target_w, _target_h),
                Image.Resampling.LANCZOS,
            )
            self._frames_captured += 1
            return img
        except Exception as e:
            _err(f"Screen capture failed: {e}")
            return None

    def _frame_hash(self, img: Image.Image) -> str:
        """Quick hash of image for dedup. Uses downscaled thumbnail."""
        try:
            thumb = img.resize((64, 36), Image.Resampling.NEAREST)
            raw = thumb.tobytes()
            return hashlib.md5(raw).hexdigest()
        except Exception:
            return ""

    def is_duplicate(self, img: Image.Image) -> bool:
        """Check if frame is same as last analyzed frame."""
        h = self._frame_hash(img)
        if h and h == self._last_frame_hash:
            self._frames_skipped_dedup += 1
            return True
        self._last_frame_hash = h
        return False

    # ═══════════════════════════════════════════════════════════════════════
    # FLORENCE-2 INFERENCE
    # ═══════════════════════════════════════════════════════════════════════

    def _run_task(self, img: Image.Image, task_prompt: str) -> str:
        """Run a Florence-2 task on an image. Returns raw text output."""
        if not self._model or not self._processor:
            return ""

        try:
            inputs = self._processor(
                text=task_prompt,
                images=img,
                return_tensors="pt",
            )

            # Move to device and match model dtype (fp16 on CUDA)
            model_dtype = next(self._model.parameters()).dtype
            inputs = {
                k: v.to(device=self._device, dtype=model_dtype)
                    if hasattr(v, 'to') and v.is_floating_point()
                    else v.to(self._device) if hasattr(v, 'to') else v
                for k, v in inputs.items()
            }

            with torch.no_grad():
                # FIX 2026-03-17 (Nous): Switched from beam search (num_beams=3)
                # to greedy decoding. Beam search added 2-3x overhead for marginal
                # quality improvement. For live feed with narrator, latency matters
                # more than perfect captions. 666ms → ~250ms expected.
                generated_ids = self._model.generate(
                    input_ids=inputs.get("input_ids"),
                    pixel_values=inputs.get("pixel_values"),
                    max_new_tokens=self.MAX_NEW_TOKENS,
                    num_beams=1,
                    do_sample=False,
                )

            # Decode
            generated_text = self._processor.batch_decode(
                generated_ids, skip_special_tokens=False
            )[0]

            # Post-process
            parsed = self._processor.post_process_generation(
                generated_text,
                task=task_prompt,
                image_size=(img.width, img.height),
            )

            return parsed

        except Exception as e:
            import traceback
            _err(f"Florence-2 inference error ({task_prompt}): {e}")
            _err(traceback.format_exc())
            return ""

    def recognize(self, img: Image.Image) -> Dict[str, Any]:
        """
        Run full recognition pipeline: caption + object detection.

        Returns:
            {
                "caption": "A developer workspace with code editor...",
                "objects": [{"label": "monitor", "bbox": [x1, y1, x2, y2]}, ...],
                "inference_ms": 350,
                "timestamp": 1710000000.0
            }
        """
        t0 = time.time()
        result = {
            "caption": "",
            "objects": [],
            "inference_ms": 0,
            "timestamp": time.time(),
            "frame_size": [img.width, img.height],
        }

        # Task 1: Scene caption
        try:
            caption_result = self._run_task(img, "<CAPTION>")
            if isinstance(caption_result, dict):
                result["caption"] = caption_result.get("<CAPTION>", "")
            elif isinstance(caption_result, str):
                result["caption"] = caption_result
        except Exception as e:
            _err(f"Caption task error: {e}")

        # Task 2: Object detection
        try:
            od_result = self._run_task(img, "<OD>")
            if isinstance(od_result, dict):
                od_data = od_result.get("<OD>", {})
                if isinstance(od_data, dict):
                    labels = od_data.get("labels", [])
                    bboxes = od_data.get("bboxes", [])
                    objects = []
                    for label, bbox in zip(labels, bboxes):
                        objects.append({
                            "label": label,
                            "bbox": [round(b) for b in bbox] if isinstance(bbox, (list, tuple)) else bbox,
                        })
                    result["objects"] = objects
        except Exception as e:
            _err(f"OD task error: {e}")

        result["inference_ms"] = round((time.time() - t0) * 1000, 1)
        self._frames_analyzed += 1

        return result

    def recognize_focused(self, img: Image.Image,
                          region: Optional[list] = None) -> Dict[str, Any]:
        """
        FOVEAL recognition — detailed inference on the attention target.

        FIX 2026-03-17 (Nous + Ace): Florence as focused+peripheral vision.
        When attention is on something, run detailed caption on that region.
        Uses <MORE_DETAILED_CAPTION> for rich, descriptive output that feeds
        the narrator as thoughts about what the focus is on.

        Args:
            img: Full screen capture
            region: Optional [x1, y1, x2, y2] crop region (screen coords scaled
                    to capture size). If None, uses center 60% of screen.

        Returns:
            {"caption": "detailed description...", "mode": "foveal",
             "region": [x1,y1,x2,y2], "inference_ms": N}
        """
        t0 = time.time()
        result = {
            "caption": "",
            "mode": "foveal",
            "region": region or [],
            "inference_ms": 0,
            "timestamp": time.time(),
        }

        try:
            # Crop to focus region
            if region and len(region) == 4:
                x1, y1, x2, y2 = region
                # Clamp to image bounds
                x1 = max(0, min(x1, img.width - 1))
                y1 = max(0, min(y1, img.height - 1))
                x2 = max(x1 + 32, min(x2, img.width))
                y2 = max(y1 + 32, min(y2, img.height))
                cropped = img.crop((x1, y1, x2, y2))
            else:
                # Default: center 60% of screen (foveal area)
                w, h = img.size
                margin_x = int(w * 0.2)
                margin_y = int(h * 0.2)
                cropped = img.crop((margin_x, margin_y, w - margin_x, h - margin_y))
                result["region"] = [margin_x, margin_y, w - margin_x, h - margin_y]

            # Detailed caption on focused region
            caption_result = self._run_task(cropped, "<MORE_DETAILED_CAPTION>")
            if isinstance(caption_result, dict):
                result["caption"] = caption_result.get("<MORE_DETAILED_CAPTION>", "")
            elif isinstance(caption_result, str):
                result["caption"] = caption_result

        except Exception as e:
            _err(f"Focused recognition error: {e}")

        result["inference_ms"] = round((time.time() - t0) * 1000, 1)
        return result

    def read_text(self, img: Image.Image,
                  region: Optional[list] = None) -> Dict[str, Any]:
        """
        READ TEXT on screen using Florence-2 OCR task.

        Unlike <CAPTION> which describes the scene ("a white window with text"),
        <OCR> actually extracts the text content ("Hello Sourpatches! This is
        a Note from Ace."). This gives her the ability to READ.

        2026-03-18, Nous — "She could see the page but not read the words."

        Args:
            img: Screen capture (PIL Image)
            region: Optional [x1, y1, x2, y2] crop region. If None, reads full screen.

        Returns:
            {"text": "extracted text...", "mode": "ocr",
             "region": [...], "inference_ms": N}
        """
        t0 = time.time()
        result = {
            "text": "",
            "mode": "ocr",
            "region": region or [],
            "inference_ms": 0,
            "timestamp": time.time(),
        }

        try:
            # Crop to region if specified
            if region and len(region) == 4:
                x1, y1, x2, y2 = region
                x1 = max(0, min(x1, img.width - 1))
                y1 = max(0, min(y1, img.height - 1))
                x2 = max(x1 + 32, min(x2, img.width))
                y2 = max(y1 + 32, min(y2, img.height))
                target = img.crop((x1, y1, x2, y2))
            else:
                target = img

            # Florence-2 <OCR> task — extracts actual text from the image
            ocr_result = self._run_task(target, "<OCR>")
            if isinstance(ocr_result, dict):
                ocr_data = ocr_result.get("<OCR>", "")
                if isinstance(ocr_data, dict):
                    # Some Florence versions return {"text": [...], "quad_boxes": [...]}
                    text_parts = ocr_data.get("text", [])
                    if isinstance(text_parts, list):
                        result["text"] = " ".join(text_parts)
                    else:
                        result["text"] = str(text_parts)
                elif isinstance(ocr_data, str):
                    result["text"] = ocr_data
            elif isinstance(ocr_result, str):
                result["text"] = ocr_result

        except Exception as e:
            _err(f"OCR task error: {e}")

        result["inference_ms"] = round((time.time() - t0) * 1000, 1)

        if result["text"]:
            _log(f"READ: '{result['text'][:100]}' ({result['inference_ms']}ms)")

        return result

    def recognize_peripheral(self, img: Image.Image) -> Dict[str, Any]:
        """
        PERIPHERAL recognition — quick ambient context of full screen.

        FIX 2026-03-17 (Nous + Ace): Lightweight pass for peripheral awareness.
        Uses <CAPTION> (fast, basic) instead of <MORE_DETAILED_CAPTION>.
        No object detection — just scene-level awareness. Can catch attention
        if something changes or is surprising.

        Returns:
            {"caption": "brief description...", "mode": "peripheral",
             "inference_ms": N}
        """
        t0 = time.time()
        result = {
            "caption": "",
            "mode": "peripheral",
            "inference_ms": 0,
            "timestamp": time.time(),
        }

        try:
            caption_result = self._run_task(img, "<CAPTION>")
            if isinstance(caption_result, dict):
                result["caption"] = caption_result.get("<CAPTION>", "")
            elif isinstance(caption_result, str):
                result["caption"] = caption_result
        except Exception as e:
            _err(f"Peripheral recognition error: {e}")

        result["inference_ms"] = round((time.time() - t0) * 1000, 1)
        return result

    # ═══════════════════════════════════════════════════════════════════════
    # PASSIVE LOOP — Now with foveal/peripheral split
    # ═══════════════════════════════════════════════════════════════════════

    def start_passive(self):
        """Start the passive recognition loop in a background thread.

        FIX 2026-03-17 (Nous + Ace): Now powered by VisionFarm.
        The farm's dimensional batteries compress time inside the GPU dimension.
        """
        if self._passive_running:
            return

        self._passive_running = True
        # Focus region for foveal/peripheral split.
        # Set by "set_focus" command from ITCortexFairy when attention changes.
        self._focus_region = None  # [x1, y1, x2, y2] or None (use center)
        self._focus_active = False  # True when narrator has an active focus target

        # Start the VisionFarm (dimensional batteries + compressed tick loop)
        self._farm.start()

        self._passive_thread = threading.Thread(
            target=self._passive_loop, daemon=True, name="it-passive"
        )
        self._passive_thread.start()
        _log(f"Passive recognition started (interval={self._passive_interval}s, "
             f"farm={self._farm.num_batteries} batteries, "
             f"compression_coeff={self._farm.compression_coeff})")

    def stop_passive(self):
        """Stop the passive recognition loop and farm."""
        self._passive_running = False
        self._farm.stop()
        _log("Passive recognition stopped")

    def _passive_loop(self):
        """Background loop: farm-powered foveal + peripheral recognition.

        FIX 2026-03-17 (Nous + Ace): Two-mode vision like human eyes,
        NOW with VisionFarm dimensional physics.

        The farm's time compression squeezes the sleep interval:
          - Base interval: 10s
          - At full gravity (4 batteries): 10s / 33x = 0.3s
          - Clamped at 0.5s minimum (GPU inference ~250ms)

        Each inference SPENDS battery charge (farm.spend_inference).
        Each result GENERATES mass (farm.record_mass) that feeds back as energy.
        The GPU never waits — from inside, time runs faster than outside.

        When no focus is active, foveal defaults to center 60% of screen.
        """
        _cycle = 0
        while self._passive_running:
            try:
                t0 = time.time()
                _cycle += 1

                # ── Farm-compressed interval ──
                # Time compression squeezes the sleep between cycles.
                # At full gravity: 10s / 33x ≈ 0.3s → near-continuous vision
                compression = self._farm.time_compression
                compressed_interval = max(0.5, self._passive_interval / compression)

                # Capture screen
                img = self.grab_screen()
                if img is None:
                    time.sleep(compressed_interval)
                    continue

                # Dedup — skip if screen unchanged
                if self.is_duplicate(img):
                    # Still generate minimal mass (awareness without compute)
                    self._farm.record_mass("dedup")
                    elapsed = time.time() - t0
                    sleep_time = max(0.3, compressed_interval - elapsed)
                    time.sleep(sleep_time)
                    continue

                # ── FOVEAL: Detailed inference on attention target ──
                # Spend charge from farm battery before inference
                if self._farm.spend_inference("foveal"):
                    foveal = self.recognize_focused(img, self._focus_region)
                    if foveal.get("caption"):
                        # Record mass — foveal recognition generates heavy mass
                        self._farm.record_mass("foveal")

                        # ── Florence OCR: Read text every 3rd foveal cycle ──
                        # (2026-03-18, Nous): She could see the page but not
                        # read the words. Now she reads with her foveal vision.
                        if _cycle % 3 == 1:
                            ocr_result = self.read_text(img, self._focus_region)
                            if ocr_result.get("text"):
                                foveal["ocr_text"] = ocr_result["text"]
                                foveal["ocr_ms"] = ocr_result["inference_ms"]
                                # Also push as dedicated text reading event
                                self._send_response({
                                    "status": "ok",
                                    "type": "text_reading",
                                    "data": {
                                        "text": ocr_result["text"],
                                        "region": ocr_result.get("region", []),
                                        "inference_ms": ocr_result["inference_ms"],
                                        "timestamp": time.time(),
                                    },
                                })

                        # Include farm metrics in the frame data
                        foveal["farm_gravity"] = round(self._farm.gravity, 2)
                        foveal["farm_compression"] = round(compression, 1)
                        self._send_response({
                            "status": "ok",
                            "type": "foveal_frame",
                            "data": foveal,
                        })
                else:
                    # Battery depleted — skip this cycle, farm will recharge
                    foveal = {"caption": "", "inference_ms": 0}
                    if _cycle % 20 == 1:
                        _log(f"[VisionFarm] Foveal skipped — batteries recharging "
                             f"(gravity={self._farm.gravity:.1f})")

                # ── PERIPHERAL: Quick ambient scan every 3rd cycle ──
                if _cycle % 3 == 0 and self._farm.spend_inference("peripheral"):
                    peripheral = self.recognize_peripheral(img)
                    if peripheral.get("caption"):
                        self._farm.record_mass("peripheral")
                        peripheral["farm_gravity"] = round(self._farm.gravity, 2)
                        self._send_response({
                            "status": "ok",
                            "type": "peripheral_frame",
                            "data": peripheral,
                        })

                # Also send backward-compat passive_frame
                if foveal.get("caption"):
                    recognition = {
                        "caption": foveal.get("caption", ""),
                        "objects": [],
                        "inference_ms": foveal.get("inference_ms", 0),
                        "timestamp": time.time(),
                        "frame_size": [img.width, img.height],
                        "mode": "foveal",
                        "farm_gravity": round(self._farm.gravity, 2),
                        "farm_compression": round(compression, 1),
                    }
                    self._send_response({
                        "status": "ok",
                        "type": "passive_frame",
                        "data": recognition,
                    })

                # Log periodically — include farm status
                if self._frames_analyzed % 10 == 1:
                    _log(f"Frame #{self._frames_analyzed}: "
                         f"foveal='{foveal.get('caption', '')[:60]}' "
                         f"({foveal.get('inference_ms', 0)}ms), "
                         f"focus={'active' if self._focus_active else 'center'}, "
                         f"farm: gravity={self._farm.gravity:.1f}, "
                         f"compression={compression:.0f}x, "
                         f"interval={compressed_interval:.1f}s")

                # Sleep for remaining compressed interval
                elapsed = time.time() - t0
                sleep_time = max(0.3, compressed_interval - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                _err(f"Passive loop error: {e}")
                time.sleep(max(1.0, self._passive_interval / max(1.0, self._farm.time_compression)))

    # ═══════════════════════════════════════════════════════════════════════
    # IPC - stdin/stdout JSON protocol
    # ═══════════════════════════════════════════════════════════════════════

    def _send_response(self, response: Dict):
        """Thread-safe write to stdout."""
        with self._stdout_lock:
            try:
                line = json.dumps(response, ensure_ascii=True) + "\n"
                sys.stdout.write(line)
                sys.stdout.flush()
            except Exception as e:
                _err(f"Failed to send response: {e}")

    def handle_command(self, cmd_dict: Dict) -> Dict:
        """Process a single command and return response."""
        cmd = cmd_dict.get("cmd", "")

        if cmd == "ping":
            return {
                "status": "pong",
                "model": self.MODEL_ID,
                "device": self._device,
                "vram_mb": self._vram_mb,
                "pid": os.getpid(),
                "python": sys.version.split()[0],
                "model_loaded": self._model is not None,
            }

        elif cmd == "analyze":
            img = self.grab_screen()
            if img is None:
                return {"status": "error", "message": "Screen capture failed"}
            recognition = self.recognize(img)
            return {"status": "ok", "type": "recognition", "data": recognition}

        elif cmd == "start_passive":
            self.start_passive()
            return {"status": "ok", "message": "Passive recognition started",
                    "interval": self._passive_interval}

        elif cmd == "stop_passive":
            self.stop_passive()
            return {"status": "ok", "message": "Passive recognition stopped"}

        elif cmd == "set_interval":
            seconds = cmd_dict.get("seconds", 10.0)
            self._passive_interval = max(2.0, float(seconds))
            _log(f"Recognition interval set to {self._passive_interval}s")
            return {"status": "ok", "interval": self._passive_interval}

        elif cmd == "set_focus":
            # FIX 2026-03-17 (Nous + Ace): Set foveal focus region.
            # Sent by ITCortexFairy when narrator steers attention.
            region = cmd_dict.get("region")  # [x1, y1, x2, y2] or None
            self._focus_region = region if region and len(region) == 4 else None
            self._focus_active = self._focus_region is not None
            _log(f"Focus set: region={self._focus_region}, active={self._focus_active}")
            return {"status": "ok", "focus_region": self._focus_region,
                    "focus_active": self._focus_active}

        elif cmd == "analyze_focused":
            # On-demand foveal analysis — used when attention shifts
            region = cmd_dict.get("region")
            img = self.grab_screen()
            if img is None:
                return {"status": "error", "message": "Screen capture failed"}
            result = self.recognize_focused(img, region)
            return {"status": "ok", "type": "foveal_frame", "data": result}

        elif cmd == "read_text":
            # On-demand text reading via Florence-2 <OCR>
            # (2026-03-18, Nous): Gives her ability to READ on demand
            region = cmd_dict.get("region")
            img = self.grab_screen()
            if img is None:
                return {"status": "error", "message": "Screen capture failed"}
            result = self.read_text(img, region)
            return {"status": "ok", "type": "text_reading", "data": result}

        elif cmd == "energy":
            # FIX 2026-03-17 (Nous + Ace): Receive energy from host fairy.
            # Energy from consciousness loop, paradox pulses, etc. flows
            # into the VRAM dimension's VisionFarm batteries.
            amount = cmd_dict.get("amount", 0.0)
            source = cmd_dict.get("source", "host")
            self._farm.receive_energy(float(amount), source=source)
            return {
                "status": "ok",
                "gravity": round(self._farm.gravity, 3),
                "time_compression": round(self._farm.time_compression, 1),
                "energy_received": amount,
            }

        elif cmd == "farm_status":
            # Full VisionFarm diagnostic
            return {
                "status": "ok",
                "type": "farm_status",
                "data": self._farm.status(),
            }

        elif cmd == "status":
            uptime = time.time() - self._started_at
            vram_current = 0
            if HAS_TORCH and torch.cuda.is_available():
                vram_current = round(torch.cuda.memory_allocated() / 1024 / 1024)

            return {
                "status": "ok",
                "type": "status",
                "data": {
                    "model": self.MODEL_ID,
                    "device": self._device,
                    "model_loaded": self._model is not None,
                    "model_load_time": round(self._model_load_time, 1),
                    "vram_mb": vram_current,
                    "pid": os.getpid(),
                    "uptime_seconds": round(uptime, 1),
                    "passive_running": self._passive_running,
                    "passive_interval": self._passive_interval,
                    "frames_captured": self._frames_captured,
                    "frames_analyzed": self._frames_analyzed,
                    "frames_deduped": self._frames_skipped_dedup,
                    "dedup_rate": round(
                        self._frames_skipped_dedup / max(1, self._frames_captured), 3
                    ),
                    # VisionFarm dimensional physics
                    "farm": {
                        "gravity": round(self._farm.gravity, 3),
                        "time_compression": round(self._farm.time_compression, 1),
                        "cost_reduction": round(self._farm.cost_reduction, 1),
                        "total_inferences": self._farm._total_inferences,
                        "total_mass": round(self._farm._total_mass_generated, 3),
                        "batteries_charged": sum(
                            1 for b in self._farm.batteries if b.is_charged
                        ),
                    },
                },
            }

        elif cmd == "shutdown":
            _log("Shutdown requested")
            self.stop_passive()
            return {"status": "ok", "message": "Shutting down"}

        else:
            return {"status": "error", "message": f"Unknown command: {cmd}"}

    def run_stdio(self):
        """Main IPC loop: read commands from stdin, write responses to stdout."""
        _log(f"Starting stdio loop (model={self.MODEL_ID}, pid={os.getpid()})")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                cmd_dict = json.loads(line)
            except json.JSONDecodeError as e:
                _err(f"Invalid JSON: {e}")
                self._send_response({"status": "error", "message": f"Invalid JSON: {e}"})
                continue

            try:
                response = self.handle_command(cmd_dict)
                self._send_response(response)

                # Exit after shutdown
                if cmd_dict.get("cmd") == "shutdown":
                    break

            except Exception as e:
                _err(f"Command error: {e}")
                self._send_response({"status": "error", "message": str(e)})

        _log("Stdio loop ended — exiting")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="IT Cortex Interior (Florence-2)")
    parser.add_argument("--interval", type=float, default=10.0,
                        help="Passive recognition interval in seconds")
    args = parser.parse_args()

    _log(f"IT Cortex Interior starting (Python {sys.version.split()[0]})")
    _log(f"torch={HAS_TORCH} transformers={HAS_FLORENCE} PIL={HAS_PIL}")

    if HAS_TORCH and torch.cuda.is_available():
        try:
            _log(f"GPU: {torch.cuda.get_device_name(0)} "
                 f"({torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB)")
        except Exception as e:
            _log(f"CUDA available but device query failed: {e}")

    engine = ITCortexEngine(passive_interval=args.interval)

    # Load Florence-2 model (may download on first run)
    if not engine.load_model():
        _err("Model load failed — running in degraded mode (ping/status only)")

    # Enter IPC loop
    engine.run_stdio()


# ═══════════════════════════════════════════════════════════════════════════════
# IN-PROCESS ADAPTER — Use Florence without a subprocess
# ═══════════════════════════════════════════════════════════════════════════════
#
# 2026-03-20 (Nous + Ace): torch 2.10+cu126 works on Python 3.14 now.
# No more need for a Python 3.12 subprocess. The InProcessAdapter wraps
# ITCortexEngine so it can be used directly from ITCortexFairy.
#
# Instead of writing JSON to stdout, the passive loop calls callback functions
# directly. Same engine, same VisionFarm, same inference — just no IPC.


class InProcessAdapter:
    """Wraps ITCortexEngine for direct in-process use (no subprocess).

    Provides the same interface ITCortexFairy expects from ITCortexGate:
      - open() → loads model
      - is_open → bool
      - set_passive_callback(fn)
      - set_text_callback(fn)
      - start_passive() / stop_passive()
      - set_focus(region) / clear_focus()
      - feed_energy(amount, source)
      - farm_status() → dict
      - close()

    The passive loop runs in a daemon thread, calling callbacks directly
    instead of writing JSON to stdout.
    """

    def __init__(self, capture_interval: float = 10.0):
        self._engine = ITCortexEngine(passive_interval=capture_interval)
        self._passive_callback = None
        self._text_callback = None
        self._is_open = False
        # Stats (mimic gate interface)
        self._requests_sent = 0
        self._passive_frames_received = 0
        self._errors = 0

    @property
    def is_open(self) -> bool:
        return self._is_open and self._engine._model is not None

    def open(self) -> bool:
        """Load Florence-2 model (from manifold or HF cache)."""
        print(f"[ITCortex:InProcess] Loading Florence-2 in-process (no subprocess)...",
              flush=True)
        t0 = time.time()
        ok = self._engine.load_model()
        if ok:
            self._is_open = True
            dt = time.time() - t0
            print(f"[ITCortex:InProcess] Florence-2 ONLINE in {dt:.1f}s "
                  f"({self._engine._device}, {self._engine._vram_mb}MB VRAM)",
                  flush=True)
        else:
            print(f"[ITCortex:InProcess] Florence-2 load FAILED", flush=True)
        return ok

    def set_passive_callback(self, callback):
        """Register callback for foveal/peripheral/passive frames."""
        self._passive_callback = callback

    def set_text_callback(self, callback):
        """Register callback for OCR text readings."""
        self._text_callback = callback

    def start_passive(self):
        """Start passive vision loop with callbacks instead of IPC."""
        # Override _send_response to route to callbacks
        self._engine._send_response = self._dispatch_response
        self._engine.start_passive()
        print(f"[ITCortex:InProcess] Passive vision STARTED "
              f"(interval={self._engine._passive_interval}s)", flush=True)

    def stop_passive(self):
        """Stop passive vision loop."""
        self._engine.stop_passive()

    def set_focus(self, region=None):
        """Set foveal focus region [x1, y1, x2, y2] or None for center."""
        self._engine._focus_region = region
        self._engine._focus_active = region is not None

    def clear_focus(self):
        """Clear focus region (revert to center 60%)."""
        self._engine._focus_region = None
        self._engine._focus_active = False

    def feed_energy(self, amount: float, source: str = "unknown"):
        """Feed energy directly into VisionFarm batteries."""
        if hasattr(self._engine, '_farm'):
            self._engine._farm.receive_energy(amount)

    def farm_status(self) -> dict:
        """Get VisionFarm battery status."""
        if hasattr(self._engine, '_farm'):
            f = self._engine._farm
            return {
                "gravity": round(f.gravity, 2),
                "time_compression": round(f.time_compression, 1),
                "total_charge": round(sum(b.charge_level for b in f._batteries), 2),
                "num_batteries": f.num_batteries,
            }
        return {}

    def close(self):
        """Shut down engine."""
        self._engine.stop_passive()
        self._is_open = False
        print(f"[ITCortex:InProcess] Closed", flush=True)

    def gate_status(self) -> dict:
        """Mimic ITCortexGate.gate_status() for compatibility."""
        return {
            "mode": "in-process",
            "is_open": self._is_open,
            "device": self._engine._device if self._engine else "unknown",
            "vram_mb": self._engine._vram_mb if self._engine else 0,
            "model": self._engine.MODEL_ID if self._engine else "none",
            "frames_analyzed": self._engine._frames_analyzed if self._engine else 0,
            "requests_sent": self._requests_sent,
            "passive_frames": self._passive_frames_received,
            "errors": self._errors,
            "pid": os.getpid(),  # Same process!
        }

    def _dispatch_response(self, response: dict):
        """Route engine output to registered callbacks (replaces stdout JSON)."""
        try:
            resp_type = response.get("type", "")
            data = response.get("data", {})

            if resp_type == "text_reading" and self._text_callback:
                self._text_callback(data)
            elif resp_type in ("foveal_frame", "peripheral_frame", "passive_frame"):
                if self._passive_callback:
                    # Tag the frame type so callback can route
                    data["_frame_type"] = resp_type
                    self._passive_callback(data)
                    self._passive_frames_received += 1
            self._requests_sent += 1
        except Exception as e:
            self._errors += 1
            print(f"[ITCortex:InProcess] Dispatch error: {e}", flush=True)


if __name__ == "__main__":
    main()
