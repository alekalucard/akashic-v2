from __future__ import annotations

"""
CUDA / GPU helper fairy (v0.1.0)

New-style organ file using Organ_Template_0_0_9 as _template.

Job:
  - Detect whether a CUDA-capable GPU + drivers are available.
  - Publish a tiny "CUDA_CAPABILITIES" snapshot on the bus.
  - Later we can let heavy organs (OCR, media, etc.) ask it
    for CUDA-aware plans.

This is deliberately lightweight so just having the file present
won't ever block boot.
"""

import os, sys, glob, time, types, json
from typing import Any, Dict, Optional
import importlib.util, importlib.machinery

import json

import os as _os
if _os.environ.get("AKASHIC_SKIP_TORCH"):
    # Battery-only mode: portals handle GPU, skip torch in main process (~3.5GB saved)
    torch = None
else:
    try:
        import torch
    except Exception:  # keep it soft-failure
        torch = None

# ---- Version/paths for the organ template -----------------------------------

TEMPLATE_VERSION = "0.3.0"
TEMPLATE_BASENAME = f"Organ_Template_{TEMPLATE_VERSION}.py"
AKASHIC_TEMPLATE_MODULE_NAME = f"akashic_template_{TEMPLATE_VERSION.replace('.', '_')}"


def _resolve_app_root() -> str:
    env_root = os.getenv("AKASHIC_ROOT")
    return os.path.abspath(env_root) if env_root else os.path.abspath(os.getcwd())


def _find_templates_root(start_dir: str) -> Optional[str]:
    start = os.path.abspath(start_dir)
    # Check known plane subdirectories first
    for sub in ("P10_Memory", "P00_Autonomic", "P60_Executive", "P40_Sensory"):
        cand = os.path.join(start, sub, "Akashic_Records_Physical")
        if os.path.isdir(cand):
            return cand
    # Walk up as fallback
    cur = start
    while True:
        ar = os.path.join(cur, "Akashic_Records_Physical")
        if os.path.isdir(ar):
            return ar
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _organ_templates_dir(app_root: str) -> Optional[str]:
    ar = _find_templates_root(app_root)
    if not ar:
        return None
    tdir = os.path.join(ar, "Organ_Templates")
    return tdir if os.path.isdir(tdir) else None


def _find_template_path(explicit_path: Optional[str] = None) -> Optional[str]:
    if explicit_path and os.path.isfile(explicit_path):
        return os.path.abspath(explicit_path)

    app_root = _resolve_app_root()
    tdir = _organ_templates_dir(app_root)
    if not tdir:
        return None

    exact = os.path.join(tdir, TEMPLATE_BASENAME)
    if os.path.isfile(exact):
        return exact

    candidates = sorted(
        glob.glob(os.path.join(tdir, "Organ_Template_*.py")),
        key=lambda p: os.path.getmtime(p),
    )
    return candidates[-1] if candidates else None


def _import_template_module(path: str) -> types.ModuleType:
    mod_name = AKASHIC_TEMPLATE_MODULE_NAME
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_loader(
        mod_name, importlib.machinery.SourceFileLoader(mod_name, path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load spec for template at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


# ---- Load the template library once -----------------------------------------

_TEMPLATE_PATH = _find_template_path()
if not _TEMPLATE_PATH:
    raise ImportError(
        "Cannot find the organ template.\n"
        f"Expected at: ./Akashic_Records_Physical/Organ_Templates/{TEMPLATE_BASENAME}\n"
        "Set AKASHIC_ROOT or pass an explicit path into _find_template_path()."
    )

_template = _import_template_module(_TEMPLATE_PATH)

for sym in (
    "MyOrganFairy",
    "MyOrganShadow",
    "TemplateShadowFairy",
    "OrganHubFacet",
    "RegistrationLib",
):
    if not hasattr(_template, sym):
        raise ImportError(f"Template missing required symbol: {sym}")


# ───────────────────── Shadow for the CUDA helper ─────────────────────────────


class CudaShadowFairy(_template.MyOrganShadow):
    """
    Tiny shadow: mostly just gives us health + cadence hooks.
    """

    CULTURE = "shadow"
    ORGAN_LEVEL = False

    SHADOW_NAME = "cuda_accelerator.shadow"
    SHADOW_VERSION = "0.1.0"

    CADENCE = {
        "warmup_times": [15, 30],
        "light_every_sec": 10 * 60,  # every 10 minutes
        "deep_every_sec": 60 * 60,   # hourly deeper check
        "idle_extra_sec": 5 * 60,
        "cooldown_on_warn_sec": 10 * 60,
        "deep_sim_ticks": 2,
    }

    def on_boot(self) -> None:
        import time
        
        # ═══════════════════════════════════════════════════════════════════════════
        # CRITICAL: Call template's on_boot() FIRST for proper registration!
        # ═══════════════════════════════════════════════════════════════════════════
        try:
            super().on_boot()
        except Exception as e:
            print(f"[{self.SHADOW_NAME}] super().on_boot() error: {e}")
        
        self._last_light = 0.0
        self._last_deep = 0.0
        self._last_any_lane_ts = time.time()
        for t in self.CADENCE["warmup_times"]:
            self.defer(t, lambda: self._light_tick(tag="warmup"))

    def _light_tick(self, tag: str = "periodic") -> Optional[Dict[str, Any]]:
        import time
        sim = self.evolution_sim_tick(tag=tag)
        self._last_light = time.time()
        self._last_any_lane_ts = self._last_light
        return sim

    def _deep_pass(self, reason: str = "periodic") -> None:
        # We can later plug in deeper CUDA self-tests here.
        n = int(self.CADENCE.get("deep_sim_ticks", 2))
        for i in range(n):
            self.evolution_sim_tick(
                tag=f"deep-{reason}-{i}", tick_kind="deep", pair_id=None
            )
        import time
        self._last_deep = time.time()

    def on_lane_activity(self) -> None:
        import time
        self._last_any_lane_ts = time.time()

    def tick(self) -> Optional[Dict[str, Any]]:
        # Defer to template's cadence harness.
        return super().tick()


# ───────────────────── Worker: CUDA helper fairy ──────────────────────────────


class CudaFairy(_template.MyOrganFairy):
    """
    CUDA awareness + advisory fairy.

    - Detects whether CUDA is present and roughly how strong it is.
    - Publishes a small "CUDA_CAPABILITIES" packet.
    - Later, heavy organs can query `intent_cuda_plan` for suggested usage.
    """

    # ACTOR_NAME stripped — wrapped by P00_Autonomic/CudaFairy/fairy.py
    # ACTOR_NAME    = "cuda_accelerator"
    _ENGINE_NAME = "cuda_accelerator"  # For reference only
    ACTOR_VERSION = "0.1.0"
    ACTOR_PLANE   = "P00"       # autonomic / infra plane
    ACTOR_CHANNEL = "cuda"      # infra lane name
    ORGAN_LEVEL   = False

    PURPOSE = (
        "Sense CUDA / GPU capabilities and offer hints to heavy workers "
        "(OCR, media, etc.) about when and how to lean on the GPU."
    )
    MANTRA = "Use the fast path when it is safe; fall back gracefully when it is not."
    LORE   = (
        "A quiet engineer who watches the glow of the GPU and whispers when "
        "it is wise to offload work and when to let the CPU breathe instead."
    )

    # Directive ring
    DIRECTIVE_ACTIVATION = {
        "mode": "Survey",
        "depth_scaling": "1..2",
        "traits": ["Cuda_Observer", "Acceleration_Planner"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Cuda_Regulation",
        "domains": ["Infra", "Somatic", "Executive"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Gpu_Sensing",
            "Acceleration_Advice",
            "Safety_Margins",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["Cuda_Snapshot", "Cuda_Advice"],
        "field": ["Acceleration_Tiering", "Worker_Scaling"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Report_Truthful_State", "No_Over_Promise"],
        "growth": ["Adaptive_Tuning", "Graceful_Degradation"],
    }

    SUBSYSTEM_STATUS = {
        "cuda_sensing": {
            "state": "active",
            "notes": "Best-effort probe of CUDA / GPU presence; never blocks boot.",
            "tests": [],
        },
        "advisory": {
            "state": "advisory",
            "notes": "Publishes CUDA_CAPABILITIES and simple advice for heavy workers.",
            "tests": [],
        },
    }

    SHADOW_CLASS = CudaShadowFairy
    AUTO_INJECT_IMPORTS = True

    # Optional infra subscriptions; template handles wiring.
    INFRA_AUTOSUBS = (
        "telemetry",
        "oracle",
        "memory.stream",
    )

        # ---- CUDA probing + OCR plan ------------------------------------------

    def _probe_cuda_snapshot(self) -> dict:
        """
        Lightweight snapshot of CUDA / GPU state.

        We deliberately keep this defensive so boot never explodes if
        torch or drivers are missing.
        """
        snap = {
            "ok": False,
            "gpus": [],
            "reason": None,
        }

        try:
            if torch is None or not torch.cuda.is_available():
                snap["reason"] = "no_torch_or_cuda"
                return snap

            count = torch.cuda.device_count()
            for idx in range(count):
                try:
                    props = torch.cuda.get_device_properties(idx)
                    snap["gpus"].append(
                        {
                            "index": idx,
                            "name": props.name,
                            "total_memory_gb": int(props.total_memory / (1024**3)),
                        }
                    )
                except Exception:
                    # ignore per-device failures
                    continue

            snap["ok"] = bool(snap["gpus"])
            if not snap["ok"] and not snap["reason"]:
                snap["reason"] = "no_devices_visible"
            return snap

        except Exception as e:
            snap["reason"] = f"probe_error: {e}"
            return snap

    def _build_ocr_plan_from_snapshot(self, snap: dict) -> dict:
        """
        Turn a CUDA snapshot into an OCR regulation plan.

        This is deliberately simple – we can evolve it later.
        """
        # very conservative defaults
        plan = {
            "ocr_mode": "tesseract",         # default engine
            "ocr_pool_workers": 2,           # threads inside shard worker
            "ocr_max_pages_per_shard": 50,   # safety cap
            "ocr_dpi": 110,
            "ocr_timeout_sec": 900,
        }

        # If snapshot isn't ok, we may still be able to salvage device_count
        # from the simpler _probe_cuda() shape.
        max_vram = 0

        # 1) Try rich snapshot shape (with an explicit gpus list).
        gpus = snap.get("gpus") or []
        if isinstance(gpus, list) and gpus:
            max_vram = max(
                (g.get("total_memory_gb", 0) for g in gpus),
                default=0,
            )

        # 2) Fallback for simpler snapshots: if we don't have per-GPU VRAM
        #    but we *do* know there's at least one device, treat it as mid-tier.
        if not max_vram:
            dev_count = int(snap.get("device_count", 0) or 0)
            if dev_count >= 1:
                # Treat "has at least one GPU" as a 4GB+ tier.
                max_vram = 4

        # If after all that we still know nothing about GPUs, stick with defaults.
        if max_vram <= 0:
            return plan

        # simple tiering: tweak as you like
        if max_vram >= 8:
            plan.update(
                {
                    "ocr_mode": "paddle",       # prefer GPU PaddleOCR
                    "ocr_pool_workers": 4,
                    "ocr_max_pages_per_shard": 80,
                }
            )
        elif max_vram >= 4:
            plan.update(
                {
                    "ocr_mode": "paddle",
                    "ocr_pool_workers": 3,
                    "ocr_max_pages_per_shard": 60,
                }
            )

        return plan



    # --- lifecycle -----------------------------------------------------------

    def on_boot(self) -> None:
        """
        Light, non-blocking CUDA probe at boot + export OCR regulation plan.
        """
        # If your base template's MyOrganFairy.on_boot does useful wiring,
        # we should preserve it:
        try:
            super().on_boot()
        except Exception:
            pass

        try:
            # 1) existing behaviour: CUDA snapshot + basic snapshot publish
            snap = self._probe_cuda_snapshot()
            self._publish_snapshot(snap)

            # 2) build OCR regulation plan from that snapshot
            plan = self._build_ocr_plan_from_snapshot(snap)

            # 3) export as env vars only if we’re actually choosing paddle.
            #    If plan says "tesseract", let the forge’s own default decide.
            if plan.get("ocr_mode") == "paddle":
                os.environ["EBOOK_OMATIC_OCR_PLAN"] = json.dumps(plan)
                os.environ["EBOOK_OMATIC_OCR_MODE"] = "paddle"


            # 4) send it onto an infra lane so status / other organs can see it
            if getattr(self, "post", None):
                self.post.route(
                    "hardware.plan",
                    {
                        "opcode": "CUDA_OCR_PLAN",
                        "payload": {
                            "actor": self.ACTOR_NAME,
                            "snapshot": snap,
                            "plan": plan,
                        },
                    },
                )

        except Exception as e:
            # Never crash boot; just whisper to tracer if we can.
            try:
                if getattr(self, "post", None):
                    self.post.route(
                        "tracer",
                        {
                            "opcode": "CUDA_OCR_PLAN_ERROR",
                            "payload": {
                                "actor": self.ACTOR_NAME,
                                "error": str(e),
                            },
                        },
                    )
            except Exception:
                pass

        # A0 (2026-05-06 Nous + Ace): Promote CudaFairy from boot-time
        # detector to live GPU monitor. Periodic publish of
        # hardware.gpu.felt with utilization, vram, and temperature so
        # CirculationPumpFairy can map GPU state → focus chemistry.
        # PC-as-body doctrine: GPU is her focus organ; its state should
        # be felt continuously, not measured once at boot.
        self._start_gpu_felt_publisher()


    def _start_gpu_felt_publisher(self) -> None:
        """
        A0: Periodic GPU → hardware.gpu.felt publisher (5s interval).

        Reads gpu_pct/vram_pct/temp_c via nvidia-smi. Falls back to
        torch.cuda if available. Publishes normalized signals for
        CirculationPumpFairy to map into DOP+ACH (focus) and COR (heat
        stress) chemistry deltas.
        """
        import threading as _t

        def _read_gpu_state():
            """Return dict with gpu_pct, vram_pct, temp_c (or None each)."""
            state = {"gpu_pct": None, "vram_pct": None, "temp_c": None}
            try:
                import subprocess
                proc = subprocess.run(
                    ["nvidia-smi",
                     "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                     "--format=csv,noheader,nounits"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=2.0,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    line = proc.stdout.strip().splitlines()[0]
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        try:
                            state["gpu_pct"] = float(parts[0])
                        except (ValueError, TypeError):
                            pass
                        try:
                            mem_used = float(parts[1])
                            mem_total = float(parts[2])
                            if mem_total > 0:
                                state["vram_pct"] = (mem_used / mem_total) * 100.0
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                        try:
                            state["temp_c"] = float(parts[3])
                        except (ValueError, TypeError):
                            pass
            except Exception:
                pass
            return state

        def _loop():
            import time as _time
            _time.sleep(4.0)  # let snapshot publish first
            while True:
                try:
                    if not getattr(self, "post", None):
                        _time.sleep(5.0)
                        continue
                    state = _read_gpu_state()
                    self.post.publish("hardware.gpu.felt", {
                        "gpu_pct": state["gpu_pct"] or 0,
                        "vram_pct": state["vram_pct"] or 0,
                        "temp_c": state["temp_c"] or 0,
                        "ts": _time.time(),
                    })
                except Exception:
                    pass
                _time.sleep(5.0)

        try:
            _thr = _t.Thread(
                target=_loop,
                daemon=True,
                name=f"{self.ACTOR_NAME}-gpu_felt",
            )
            _thr.start()
            print(f"[{self.ACTOR_NAME}] A0 hardware.gpu.felt publisher started (5s interval)", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] A0 GPU publisher start failed: {e}", flush=True)


    # --- helpers -------------------------------------------------------------

    def _probe_cuda(self) -> Dict[str, Any]:
        """
        Very gentle CUDA probe. We do NOT require torch or any specific
        GPU library; we just see what is available.
        """
        snapshot: Dict[str, Any] = {
            "ok": False,
            "backend": None,
            "device_count": 0,
            "capabilities": {},
        }

        # Try torch first if available
        try:
            import torch  # type: ignore[attr-defined]

            if torch.cuda.is_available():
                dev_count = torch.cuda.device_count()
                snapshot["ok"] = True
                snapshot["backend"] = "torch"
                snapshot["device_count"] = int(dev_count)
                try:
                    name = torch.cuda.get_device_name(0)
                except Exception:
                    name = "unknown"
                snapshot["capabilities"] = {
                    "primary_name": name,
                    "supports_half": bool(getattr(torch.cuda, "amp", None)),
                }
                return snapshot
        except Exception:
            pass

        # Fallback: nvidia-smi if present
        try:
            import subprocess

            proc = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,count", "--format=csv,noheader"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
                snapshot["ok"] = True
                snapshot["backend"] = "nvidia-smi"
                snapshot["device_count"] = len(lines)
                snapshot["capabilities"] = {"primary_name": lines[0]}
        except Exception:
            pass

        return snapshot

    def _publish_snapshot(self, snap: Dict[str, Any]) -> None:
        """
        Emit CUDA capabilities to postal system for worker pool coordination.
        """
        # Emit to cuda.capabilities for SystemWorkerPoolFairy
        try:
            if getattr(self, "post", None):
                self.post.route("cuda.capabilities", {
                    "actor": self.ACTOR_NAME,
                    "ok": snap.get("ok", False),
                    "device_count": snap.get("device_count", 0),
                    "gpus": snap.get("gpus", []),
                    "ts": time.time(),
                })
                print(f"[CudaFairy] Published cuda.capabilities")
        except Exception as e:
            print(f"[CudaFairy] cuda.capabilities publish error: {e}")
        try:
            packet = {
                "opcode": "CUDA_CAPABILITIES",
                "payload": snap,
                "actor": self.ACTOR_NAME,
                "ts": time.time(),
            }
            if getattr(self, "post", None):
                # fire-and-forget
                self.post.route("telemetry", packet)
                self.post.route("oracle", packet)
        except Exception:
            pass

    # --- intents -------------------------------------------------------------

    def intent_smoke(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {"ok": True, "actor": self.ACTOR_NAME, "ts": time.time()}

    def intent_cuda_snapshot(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Synchronous snapshot for callers that want to ask directly.
        """
        try:
            snap = self._probe_cuda()
            return {"ok": True, "snapshot": snap}
        except Exception as e:
            return {"ok": False, "error": str(e)}
