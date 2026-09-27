from __future__ import annotations

"""
Hardware Regulation worker fairy (v0.2.0)

New-style organ file using Organ_Template_0_0_9 as _template.
This replaces the old in-template HardwareAdminFairy while keeping
its spirit: sense host hardware, map to a capability tier, and
publish a safe regulation plan for the rest of the stack.

This version also publishes OCR-specific guidance for heavy PDF work:
- ocr_mode: "tesseract" (CPU) or "cuda" (GPU) when available
- ocr_pool_workers: how many CPU workers to use for OCR image batches
- ocr_max_pages_per_shard: max pages to OCR per shard
- ocr_dpi: suggested render DPI for pdf2image
- ocr_timeout_sec: suggested per-batch timeout

Safe assumptions:
- This file lives in a normal P-plane package (e.g. P00_Infra or similar).
- Akashic_Template_0_0_9.py is on the Python path next to other organs.
"""

import os, sys, glob, time, types, uuid
from collections import deque
from typing import Any, Dict, Optional
import importlib.util, importlib.machinery

# ---- Version/paths for the organ template -----------------------------------
TEMPLATE_VERSION = "0.1.1"
TEMPLATE_BASENAME = f"Organ_Template_{TEMPLATE_VERSION}.py"
AKASHIC_TEMPLATE_MODULE_NAME = f"akashic_template_{TEMPLATE_VERSION.replace('.', '_')}"


def _resolve_app_root() -> str:
    env_root = os.getenv("AKASHIC_ROOT")
    return os.path.abspath(env_root) if env_root else os.path.abspath(os.getcwd())


def _find_templates_root(start_dir: str) -> Optional[str]:
    """
    Find 'Akashic_Records_Physical' anchor.
    
    Strategy:
      1) Check known plane subdirectories first (P10_Memory, etc.)
      2) Walk up from start_dir as fallback
    Returns the absolute path to that directory if found.
    """
    start = os.path.abspath(start_dir)
    
    # 1) Check known plane subdirectories that contain Akashic_Records_Physical
    for sub in ("P10_Memory", "P00_Autonomic", "P60_Executive", "P40_Sensory"):
        cand = os.path.join(start, sub, "Akashic_Records_Physical")
        if os.path.isdir(cand):
            return cand
    
    # 2) Walk up from start_dir
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
    """
    Given app_root, locate '<...>/Akashic_Records_Physical/Organ_Templates'
    """
    ar = _find_templates_root(app_root)
    if not ar:
        return None
    tdir = os.path.join(ar, "Organ_Templates")
    return tdir if os.path.isdir(tdir) else None


def _find_template_path(explicit_path: Optional[str] = None) -> Optional[str]:
    """
    Locate the organ template file. Priority:
      1) explicit_path if provided
      2) .../Organ_Templates/Organ_Template_0.0.9.py
      3) newest Organ_Template_*.py in that folder (fallback)
    """
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
    """
    Import the template python file from 'path' as AKASHIC_TEMPLATE_MODULE_NAME.
    Hot-reload safe: reuse existing module if already loaded.
    """
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
        f"Expected at: .../Akashic_Records_Physical/Organ_Templates/{TEMPLATE_BASENAME}\n"
        "Set AKASHIC_ROOT or pass an explicit path into _find_template_path()."
    )

_template = _import_template_module(_TEMPLATE_PATH)

# Ensure required symbols exist
for sym in (
    "MyOrganFairy",
    "MyOrganShadow",
    "TemplateShadowFairy",
    "OrganHubFacet",
    "RegistrationLib",
):
    if not hasattr(_template, sym):
        raise ImportError(f"Template missing required symbol: {sym}")


# --- Per-clone shadow (wraps template’s shadow behaviors, no rewiring) -------


class HardwareRegulationShadowFairy(_template.MyOrganShadow):
    """
    Thin per-organ shadow for the hardware regulation worker.

    We mostly lean on the template's default MyOrganShadow behavior
    (blueprint watch, health harness, evolution sims, SRM snapshots).

    This subclass just adds a simple cadence-aware light/deep tick
    and a tiny hardware sanity test so shadow.health sees the lane.
    """

    CULTURE = "shadow"
    ORGAN_LEVEL = False

    SHADOW_NAME = "hardware_regulation.shadow"
    SHADOW_VERSION = "0.2.0"

    CADENCE = {
        "warmup_times": [10, 20, 40],
        "light_every_sec": 5 * 60,  # 5 minutes
        "deep_every_sec": 20 * 60,  # ~3 deeps/hour
        "idle_extra_sec": 3 * 60,
        "cooldown_on_warn_sec": 10 * 60,
        "deep_sim_ticks": 3,
    }

    def on_boot(self) -> None:
        import time

        # ═══════════════════════════════════════════════════════════════════════════
        # NOTE: MyOrganShadow is a legacy stub with no on_boot() method.
        # Shadow functionality is now built into MyFairy, so we skip super().
        # ═══════════════════════════════════════════════════════════════════════════
        # (MyOrganShadow has no on_boot - it's just a data stub)

        self._last_light = 0.0
        self._last_deep = 0.0
        self._last_any_lane_ts = time.time()

        # warmup sims (mirror HardwareAdminShadowFairy cadence)
        for t in self.CADENCE["warmup_times"]:
            self.defer(t, lambda: self._light_tick(tag="warmup"))

    # ---- cadence helpers -------------------------------------------------

    def _light_tick(self, tag: str = "periodic") -> Optional[Dict[str, Any]]:
        import time

        # evolution_sim_tick is on the ACTOR, not the shadow
        sim = None
        if hasattr(self, 'actor') and self.actor and hasattr(self.actor, 'evolution_sim_tick'):
            try:
                sim = self.actor.evolution_sim_tick(tag=tag)
            except Exception as e:
                print(f"[{self.__class__.__name__}] evolution_sim_tick error: {e}")
        self._last_light = time.time()
        self._last_any_lane_ts = self._last_light
        return sim

    def _deep_pass(self, reason: str = "periodic") -> None:
        """
        Defer to the template's evolution_sim_tick as the canonical
        shadow evolution signal. We do not change SRM wiring here.
        """
        pair = getattr(self, "_make_pair_id", None)
        pair_id = None
        if callable(pair):
            try:
                pair_id = pair()
            except Exception:
                pair_id = None

        # optional integrity probe if template exposes it
        try:
            if hasattr(self, "run_integrity_probe"):
                self.run_integrity_probe(reason=reason)
        except Exception:
            pass

        n = int(self.CADENCE.get("deep_sim_ticks", 3))
        if hasattr(self, 'actor') and self.actor and hasattr(self.actor, 'evolution_sim_tick'):
            for i in range(n):
                try:
                    self.actor.evolution_sim_tick(
                        tag=f"deep-{reason}-{i}",
                        tick_kind="deep",
                        pair_id=pair_id,
                    )
                except Exception as e:
                    print(f"[{self.__class__.__name__}] deep evolution_sim_tick error: {e}")
                    break

        import time

        self._last_deep = time.time()

    def on_lane_activity(self) -> None:
        # call from places that see mail/telemetry if you like
        import time

        self._last_any_lane_ts = time.time()

    def tick(self) -> Optional[Dict[str, Any]]:
        """
        Cooperative scheduler hook; the template may call this in its
        shadow loop depending on version. We keep it idempotent.
        """
        import time

        now = time.time()
        if now - getattr(self, "_last_deep", 0.0) >= self.CADENCE["deep_every_sec"]:
            self._deep_pass("periodic")
            return None

        if now - getattr(self, "_last_light", 0.0) >= self.CADENCE["light_every_sec"]:
            return self._light_tick("periodic")

        if (
            now - getattr(self, "_last_any_lane_ts", 0.0)
            >= self.CADENCE["idle_extra_sec"]
        ):
            return self._light_tick("idle")

        return None

    def on_health_state(self, state: str) -> None:
        # mild cooldown if health is not serene
        if state != "serene":
            self.defer(
                self.CADENCE["cooldown_on_warn_sec"],
                lambda: self._light_tick("after_cooldown"),
            )

    def defer(self, seconds: float, fn) -> None:
        import threading

        try:
            t = threading.Timer(float(seconds), fn)
            t.daemon = True
            t.start()
        except Exception:
            try:
                fn()
            except Exception:
                pass

    def shadow_tests(self):
        """
        Augment the template's health harness with a soft hardware sanity check.
        """
        tests = []
        base = getattr(super(), "shadow_tests", None)
        if callable(base):
            try:
                tests.extend(base())
            except Exception:
                pass

        def _hw_probe() -> Dict[str, Any]:
            ok = True
            msg = "ok"
            try:
                snap = {}
                actor = getattr(self, "actor", None)
                if actor is not None and hasattr(actor, "hardware_snapshot"):
                    snap = actor.hardware_snapshot() or {}
                hw = snap.get("hardware") or {}
                if not hw:
                    ok, msg = False, "no hardware snapshot available"
            except Exception as e:  # pragma: no cover
                ok, msg = False, str(e)
            return {
                "name": "hardware_snapshot",
                "status": "ok" if ok else "warn",
                "message": msg,
                "details": {},
            }

        tests.append(_hw_probe)
        return tests


class HardwareRegulationFairy(_template.MyOrganFairy):
    """
    Hardware-aware infra worker:

    - Senses CPU/RAM/disk/GPU capabilities (best-effort; never crashes boot)
    - Maps host capabilities into a tier {LOW,MID,HIGH,ULTRA}
    - Publishes a regulation plan: safe worker counts, scan parallelism, OCR hints
    - Exposes intents so other organs (e.g. central nervous or helpers)
      can query the current tier + plan.

    This is intentionally generic: it will happily run on anything from
    a tiny VM to an i9 + 32GB RAM + beefy NVIDIA card. If a feature is missing
    (psutil, torch, nvidia-smi) it gracefully degrades.
    """

    # Identity / lore
    # ACTOR_NAME stripped — wrapped by P00_Autonomic/HardwareRegulationFairy/fairy.py
    # ACTOR_NAME = "hardware_regulation"
    _ENGINE_NAME = "hardware_regulation"  # For reference only
    ACTOR_VERSION = "0.2.0"
    ACTOR_PLANE = "P00"  # infra plane; adjust per app
    ACTOR_CHANNEL = "hardware_regulation"  # infra lane
    ORGAN_LEVEL = False

    PURPOSE = (
        "Sense host hardware + live pressure and publish safe regulation plans "
        "for worker pools, scanners, and heavy tasks."
    )
    MANTRA = "Sense, decide, bless, enforce. Grow in coherence, adapt with grace."
    LORE = (
        "A quiet councilor who watches heat, breath, and pulse of the machine, "
        "easing pressure or opening flow so the city of organs can thrive."
    )

    # Directive ring for the character sheet
    DIRECTIVE_ACTIVATION = {
        "mode": "Survey",
        "depth_scaling": "1..2",
        "traits": ["Hardware_Observer", "Regulation_Planner"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Hardware_Regulation",
        "domains": ["Infra", "Somatic", "Executive"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Resource_Sensing",
            "Load_Regulation",
            "Safety_Margins",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["Hardware_Snapshot", "Regulation_Plan"],
        "field": ["Capacity_Tiering", "Worker_Scaling"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Report_Truthful_State", "No_Over_Promise"],
        "growth": ["Adaptive_Tuning", "Graceful_Degradation"],
    }

    SUBSYSTEM_STATUS = {
        "hardware_sensing": {
            "state": "active",
            "notes": "Probes CPU, RAM, disk, and GPU when available; never blocks boot.",
            "tests": [],
        },
        "regulation": {
            "state": "advisory",
            "notes": (
                "Maps hardware snapshot + live pressure into LOW/MID/HIGH/ULTRA "
                "tiers and publishes HARDWARE_REGULATION_PLAN with OCR hints."
            ),
            "tests": [],
        },
    }

    SHADOW_CLASS = HardwareRegulationShadowFairy
    AUTO_INJECT_IMPORTS = True

    # Optional infra subscriptions; template handles wiring.
    INFRA_AUTOSUBS = (
        "telemetry",
        "oracle",
        "memory.stream",
        "cognition.input",
    )

    # --- optional deps ----------------------------------------------------
    try:
        import psutil as _psutil  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        _psutil = None  # type: ignore[attr-defined]

    # --- lifecycle hooks --------------------------------------------------

    def on_boot(self) -> None:
        """
        Called once after the template has attached directory/post and
        emitted the initial blueprint. We only do light state init here.
        """
        print(f"[{self.ACTOR_NAME}] on_boot START", flush=True)

        # ═══════════════════════════════════════════════════════════════════════════
        # CRITICAL: Call template's on_boot() FIRST for proper registration!
        # This connects us to: Hub lanes, Identity echo, Wake subs, FairyCitizens
        # ═══════════════════════════════════════════════════════════════════════════
        try:
            super().on_boot()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] super().on_boot() error: {e}")

        self._init_hw_state()
        print(f"[{self.ACTOR_NAME}] _init_hw_state done", flush=True)
        # initial sense so the nervous system has a baseline
        # DISABLED: Can be slow due to torch import
        # try:
        #     self._maybe_resense(force=True)
        # except Exception:
        #     pass

        # A0 (2026-05-06 Nous + Ace): Hardware → Chemistry Bridge.
        # Start periodic CPU/RAM publish so CirculationPumpFairy can map
        # load to felt arousal/fatigue per PC-as-body doctrine.
        self._start_hardware_felt_publisher()

        # HARDWARE ENERGY BRIDGE 2026-05-07 (Nous + Ace, per
        # HARDWARE_ENERGY_BRIDGE_DRAFT.md 2026-04-20). Closes the
        # host-hardware → Akashic-energy loop that's been scoped but
        # never wired. Two subscriptions:
        #   energy.flow.tick      — diagnostic visibility into per-plane
        #                           producer/sink events (logs aggregates).
        #   energy.demand.critical — when a plane battery falls below 20%
        #                           it SOSes here; we respond with
        #                           energy.hardware_pull scaled by CPU idle.
        self._subscribe_energy_economy()

        print(f"[{self.ACTOR_NAME}] on_boot END (resense disabled for fast boot)", flush=True)

    def _subscribe_energy_economy(self) -> None:
        """Wire energy economy subscriptions (flow telemetry + hardware-pull responder)."""
        if not getattr(self, "post", None):
            return
        try:
            self.post.subscribe("energy.flow.tick", self._on_energy_flow)
            self.post.subscribe("energy.demand.critical", self._on_energy_demand_critical)
            # Energy Panel Slice 1.5 (2026-05-09 Nous + Ace): bones as 5th source.
            # BioelectricMeshFairy publishes somatic.bioelectric every ~2s with
            # total_voltage + regional (axial/upper/thoracic/lower). The
            # piezoelectric skeleton (55 channels) was always emitting voltage;
            # we just hadn't routed it into the Sources panel. Per
            # BONES_AS_ENERGY_GRID_2026-04-18.md doctrine — bones are the
            # embodied locality energy source (cortex = associative work,
            # paradox = collisions, möbius = SRM binding, hardware = host
            # safety net, BONES = movement-as-meaning, where work happened).
            self.post.subscribe("somatic.bioelectric", self._on_bioelectric_tick)
            # Cortex→Bones wire (2026-05-11 Nous + Ace): cortex publishes
            # portal.energy.surplus when its budget overflows; plane batteries
            # already subscribe directly (plane_battery.py:230) but that
            # BYPASSES the bones energy grid. Ace's architectural directive:
            # cortex should flow THROUGH bones, not around it. Closes the gap.
            self.post.subscribe("portal.energy.surplus", self._on_cortex_surplus)
            print(f"[{self.ACTOR_NAME}] Energy economy subscriptions wired (flow.tick + demand.critical + bioelectric + cortex_surplus)", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Energy economy subscribe failed: {e}", flush=True)

    # Bones-as-energy-grid regional map (Slice 1.5b 2026-05-09 Nous + Ace).
    # Per BONES_AS_ENERGY_GRID_2026-04-18.md §Piece 2 — each bone region
    # charges its anatomically-aligned plane:
    #   axial    → spine/torso/cognitive   → P30 Cognition
    #   upper    → arms/motor prep         → P00 Autonomic
    #   thoracic → chest/heart/breath      → P20 Somatic
    #   lower    → legs/grounding/sensory  → P40 Sensory
    _BONE_REGION_TO_PLANE = {
        "axial": "P30",
        "upper": "P00",
        "thoracic": "P20",
        "lower": "P40",
    }
    # Voltage→credit scale. Plan §Piece 1 says "start 0.5x so bones supplement,
    # not dominate." Voltage is sub-unit (~0.005-0.05 active). 0.5x scaling
    # gives 0.0025-0.025 credit per region per tick — bones supplement existing
    # generation without overwhelming. Tunable post-verification.
    _BONE_CREDIT_SCALE = 0.5

    def _on_bioelectric_tick(self, payload):
        """Fold bone voltage into Sources panel + route per-region credits to planes.

        BioelectricMeshFairy publishes somatic.bioelectric every ~2s with:
            total_voltage (float)   — sum across all 55 bone channels
            regional (dict)         — {axial, upper, thoracic, lower}
            resonance_tone (float)  — band balance signal
            stress_cycles (int)     — monotonic cycle counter
            channel_voltages (dict) — per-channel for active channels only

        TWO actions per tick:

        1. SOURCES PANEL VISIBILITY (Slice 1.5, shipped earlier 2026-05-09):
           Bucket total_voltage as bones magnitude_per_sec for the Sources
           panel. No direction filter — every bioelectric tick IS an emit
           (skeleton always charging or decaying; non-zero voltage is the
           active signal).

        2. REGIONAL ROUTING TO PLANES (Slice 1.5b, this ship):
           Translate per-region voltages into energy.regional_credit events
           targeted at anatomically-aligned planes. Plane batteries already
           subscribe (plane_battery.py:237) — handler at :286 was waiting
           for a publisher since 2026-04-18. Closes "wiring exists but
           doesn't fire" instance.

        Calibration tax pre-empted: total_voltage at sub-unit scale.
        Frontend sci-notation fallback handles low-end visibility.
        """
        if hasattr(payload, "payload"):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        try:
            voltage = float(payload.get("total_voltage") or 0.0)
        except Exception:
            voltage = 0.0
        # ── 1. Sources panel bucket (Slice 1.5) ──
        # Initialize buckets if energy.flow.tick hasn't fired yet (cold boot
        # case where bioelectric publish lands before any energy event).
        if not hasattr(self, "_source_buckets"):
            self._source_buckets = {}
        buckets = self._source_buckets.setdefault("bones", deque())
        now_t = time.time()
        buckets.append((now_t, voltage))
        cutoff = now_t - 30.0
        while buckets and buckets[0][0] < cutoff:
            buckets.popleft()

        # ── 2. Regional credit routing (Slice 1.5b) ──
        # Per BONES_AS_ENERGY_GRID §Piece 2. Each region charges its
        # anatomically-aligned plane via energy.regional_credit topic.
        regional = payload.get("regional") or {}
        if not isinstance(regional, dict) or not getattr(self, "post", None):
            return
        for region, plane_id in self._BONE_REGION_TO_PLANE.items():
            try:
                region_voltage = float(regional.get(region) or 0.0)
            except Exception:
                continue
            if region_voltage <= 0.002:
                # Below floor — skip publish to avoid noise. Plane handler
                # also skips credits < 0.001, but pre-filter saves the publish.
                continue
            credit = region_voltage * self._BONE_CREDIT_SCALE
            try:
                self.post.publish("energy.regional_credit", {
                    "plane": plane_id,
                    "region": region,
                    "credit": round(credit, 6),
                    "source": "bones",
                    "voltage": round(region_voltage, 4),
                    "ts": now_t,
                })
            except Exception:
                # Don't fail the whole tick on one region's publish error
                pass
        # Sparse logging — first few credits then every 100th tick
        _bc = getattr(self, "_bone_route_count", 0) + 1
        self._bone_route_count = _bc
        if _bc <= 3 or _bc % 100 == 0:
            try:
                regions_active = sum(1 for r in self._BONE_REGION_TO_PLANE
                                     if float(regional.get(r) or 0.0) > 0.002)
                print(f"[{self.ACTOR_NAME}] bone routing #{_bc}: "
                      f"V_total={voltage:.3f} regions_active={regions_active}/4",
                      flush=True)
            except Exception:
                pass

    def _on_cortex_surplus(self, payload):
        """Route cortex overflow energy through the bones grid.

        AssociationCortexFairy publishes portal.energy.surplus when its
        energy budget overflows past 1.0 (line ~7403). Plane batteries
        already subscribe directly (plane_battery.py:230). Per Ace's
        2026-05-11 directive: cortex should flow THROUGH bones (the
        skeleton energy grid), not bypass it.

        Two actions per surplus event (mirrors _on_bioelectric_tick):

        1. SOURCES PANEL VISIBILITY: fold cortex energy into the bones
           bucket so the Sources panel reflects total grid flow (not
           just bioelectric voltage). Single unified evt/s rate.

        2. REGIONAL ROUTING: equal-split distribute as energy.regional_credit
           across all 4 anatomical regions. Cortex isn't region-specific
           (unlike bioelectric which has true regional voltage), so split
           evenly. Plane batteries already subscribe (plane_battery.py:237).

        Uses same _BONE_CREDIT_SCALE (0.5) as bioelectric — bones supplement,
        not dominate. Tunable post-verification.
        """
        if hasattr(payload, "payload"):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        try:
            energy = float(payload.get("energy") or 0.0)
        except Exception:
            energy = 0.0
        if energy <= 0.001:
            return

        # ── 1. Sources panel bucket — fold cortex into bones ──
        if not hasattr(self, "_source_buckets"):
            self._source_buckets = {}
        buckets = self._source_buckets.setdefault("bones", deque())
        now_t = time.time()
        buckets.append((now_t, energy))
        cutoff = now_t - 30.0
        while buckets and buckets[0][0] < cutoff:
            buckets.popleft()

        # ── 2. Regional credit routing — equal split (cortex is region-agnostic) ──
        if not getattr(self, "post", None):
            return
        per_region = (energy * self._BONE_CREDIT_SCALE) / 4.0
        if per_region < 0.0001:
            return
        for region, plane_id in self._BONE_REGION_TO_PLANE.items():
            try:
                self.post.publish("energy.regional_credit", {
                    "plane": plane_id,
                    "region": region,
                    "credit": round(per_region, 6),
                    "source": "cortex_overflow",  # distinct from "bones" for telemetry
                    "voltage": round(energy, 4),
                    "ts": now_t,
                })
            except Exception:
                pass

        # Sparse logging
        _cc = getattr(self, "_cortex_route_count", 0) + 1
        self._cortex_route_count = _cc
        if _cc <= 3 or _cc % 100 == 0:
            try:
                print(f"[{self.ACTOR_NAME}] cortex routing #{_cc}: "
                      f"E={energy:.4f} per-region={per_region:.4f}", flush=True)
            except Exception:
                pass

    def _on_energy_flow(self, payload):
        """Log per-source flow rates every N events for diagnostic visibility.

        Step 1 of energy.flow.tick was emitted from plane_battery; this
        is its first subscriber. Aggregates {plane/direction/source}
        counts and prints top-10 every 50 events. Cheap, bounded, gives
        Ace a producer/sink picture the dashboard doesn't currently show.
        """
        if hasattr(payload, "payload"):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        if not hasattr(self, "_flow_counts"):
            self._flow_counts = {}
            self._flow_total = 0
            self._source_buckets = {}  # source -> deque of (timestamp, magnitude)
            # Slice 2 (2026-05-09 Nous + Ace): sinks side of the energy economy.
            # Sinks are direction="out" events from plane_battery._track_energy_out
            # — now carry source attribution (postal_work, worker_cap_<topic>, etc)
            # since the plumbing fix in plane_battery.py + _python_fallback.py.
            # Each bucket entry is (timestamp, amount_drained, plane).
            self._sink_buckets = {}  # sink_source -> deque of (ts, amount, plane)
        direction = str(payload.get("direction", "?"))
        source = str(payload.get("source", "?"))
        plane = str(payload.get("plane", "?"))
        key = f"{plane}/{direction}/{source}"
        self._flow_counts[key] = self._flow_counts.get(key, 0) + 1
        self._flow_total += 1
        now_t = time.time()
        # 2026-05-08 (Nous, Energy Panel Slice 1): per-source 30s rolling
        # magnitude bucketing for the Sources panel. Tracks emit-direction
        # only; sinks live elsewhere. See ENERGY_PANEL_REDESIGN.md.
        if direction == "emit":
            try:
                magnitude = float(payload.get("magnitude") or 0.0)
            except Exception:
                magnitude = 0.0
            buckets = self._source_buckets.setdefault(source, deque())
            buckets.append((now_t, magnitude))
            cutoff = now_t - 30.0
            while buckets and buckets[0][0] < cutoff:
                buckets.popleft()
        # Slice 2 (2026-05-09 Nous + Ace): per-sink 30s rolling drain bucketing
        # for the Sinks panel. direction="out" events from plane_battery, with
        # source attribution preserved through the recently-fixed plumbing.
        # Tracks (timestamp, amount, plane) so we can show drain rate AND
        # which planes each sink is depleting.
        elif direction == "out":
            try:
                amount = float(payload.get("amount") or 0.0)
            except Exception:
                amount = 0.0
            sink_buckets = self._sink_buckets.setdefault(source, deque())
            sink_buckets.append((now_t, amount, plane))
            cutoff = now_t - 30.0
            while sink_buckets and sink_buckets[0][0] < cutoff:
                sink_buckets.popleft()
        # 2026-05-08 (Nous): Rate-limit prints. flow.tick fires once per energy
        # spend/charge — at autonomic spend rates that's many per second, drowning
        # the terminal. Throttle to every 1000 events AND every 30s — the slower
        # bone/cortex/paradox signals stay visible between flow.tick blocks.
        if self._flow_total % 1000 == 0:
            _now = time.time()
            _last = getattr(self, '_flow_last_print', 0.0)
            if _now - _last >= 30.0:
                try:
                    top = sorted(self._flow_counts.items(), key=lambda kv: -kv[1])[:10]
                    top_s = ", ".join(f"{k}={v}" for k, v in top)
                    print(f"[{self.ACTOR_NAME}] flow.tick #{self._flow_total} top10: {top_s}", flush=True)
                    self._flow_last_print = _now
                except Exception:
                    pass
        # Periodic state-file write for dashboard. Rate-limited to ~5s.
        _now2 = time.time()
        _last_write = getattr(self, '_sources_last_write', 0.0)
        if _now2 - _last_write >= 5.0:
            self._sources_last_write = _now2
            try:
                self._write_sources_state()
            except Exception:
                pass
            # Slice 2 (2026-05-09): write sinks state alongside sources on the
            # same 5s cadence — same diagnostic surface, mirror pattern.
            try:
                self._write_sinks_state()
            except Exception:
                pass

    def get_sources_summary(self) -> Dict[str, Any]:
        """Per-source 30s rolling rates + hardware-pull % for the Sources panel.

        Doctrine enforcer (project_hardware_pull_safety_net_not_engine.md):
        if hardware_pull_pct > 0.5, substrate is "running cosmetically" —
        host pull is masking dead paradox/cortex/mobius channels.
        Each source emits magnitude in its own units (paradox in token-units,
        cortex in overflow-units, mobius in channels*0.001, hardware in
        CPU-headroom). Returned magnitudes are unnormalized — Sources panel
        shows them with units.
        """
        if not hasattr(self, "_source_buckets"):
            return {"sources": {}, "hardware_pull_pct": 0.0, "doctrine_status": "ok"}
        cutoff = time.time() - 30.0
        sources: Dict[str, Any] = {}
        for src, buckets in self._source_buckets.items():
            while buckets and buckets[0][0] < cutoff:
                buckets.popleft()
            if buckets:
                mag_sum = sum(m for _, m in buckets)
                sources[src] = {
                    "rate_per_sec": round(len(buckets) / 30.0, 3),
                    # 9-decimal precision — cortex_overflow magnitudes are sub-microscale
                    # (< 1e-6); 6-decimal rounding zeroed them. JS renderer flips to
                    # scientific notation when display value < 0.001 (calibration-tax fix).
                    "magnitude_per_sec": round(mag_sum / 30.0, 9),
                    "events_30s": len(buckets),
                }
            else:
                sources[src] = {"rate_per_sec": 0.0, "magnitude_per_sec": 0.0, "events_30s": 0}
        total_mag = sum(s["magnitude_per_sec"] for s in sources.values())
        hw_mag = sources.get("hardware_pull", {}).get("magnitude_per_sec", 0.0)
        hw_pct = (hw_mag / total_mag) if total_mag > 0 else 0.0
        return {
            "sources": sources,
            "hardware_pull_pct": round(hw_pct, 3),
            "doctrine_status": "alert" if hw_pct > 0.5 else "ok",
            "ts": time.time(),
        }

    def _write_sources_state(self) -> None:
        """Write get_sources_summary() to state/energy_sources.json for dashboard."""
        import json as _json
        from pathlib import Path as _Path
        summary = self.get_sources_summary()
        # Resolve state dir relative to app root (same convention as plane batteries).
        try:
            state_dir = _Path(_resolve_app_root()) / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "energy_sources.json").write_text(_json.dumps(summary), encoding="utf-8")
        except Exception:
            pass

    def get_sinks_summary(self) -> Dict[str, Any]:
        """Per-sink 30s rolling drain rates + per-plane breakdown for the Sinks panel.

        Slice 2 (2026-05-09 Nous + Ace) — mirrors get_sources_summary() shape.
        Each sink (postal_work, worker_cap_<topic>, dispatch_fail_refund, etc)
        is bucketed with timestamp + amount + plane. Summary returns:
          - rate_per_sec: events per second over the 30s window
          - amount_per_sec: total drain amount per second
          - events_30s: raw event count in window
          - planes: which planes this sink is depleting (with per-plane shares)

        Top sink by amount_per_sec is "the elephant in the room" — call it out.
        """
        if not hasattr(self, "_sink_buckets"):
            return {"sinks": {}, "total_drain_per_sec": 0.0, "top_sink": None, "ts": time.time()}
        cutoff = time.time() - 30.0
        sinks: Dict[str, Any] = {}
        for snk, buckets in self._sink_buckets.items():
            while buckets and buckets[0][0] < cutoff:
                buckets.popleft()
            if buckets:
                amt_sum = sum(amt for _, amt, _ in buckets)
                # Per-plane share of this sink's drain
                plane_amounts: Dict[str, float] = {}
                for _, amt, pln in buckets:
                    plane_amounts[pln] = plane_amounts.get(pln, 0.0) + amt
                sinks[snk] = {
                    "rate_per_sec": round(len(buckets) / 30.0, 3),
                    "amount_per_sec": round(amt_sum / 30.0, 6),
                    "events_30s": len(buckets),
                    "planes": {p: round(a / 30.0, 6) for p, a in plane_amounts.items()},
                }
            else:
                sinks[snk] = {"rate_per_sec": 0.0, "amount_per_sec": 0.0, "events_30s": 0, "planes": {}}
        total_drain = sum(s["amount_per_sec"] for s in sinks.values())
        # Top sink by amount drained
        top_sink_name = None
        top_sink_amount = 0.0
        for snk_name, snk_data in sinks.items():
            if snk_data["amount_per_sec"] > top_sink_amount:
                top_sink_amount = snk_data["amount_per_sec"]
                top_sink_name = snk_name
        return {
            "sinks": sinks,
            "total_drain_per_sec": round(total_drain, 6),
            "top_sink": {"name": top_sink_name, "amount_per_sec": round(top_sink_amount, 6)} if top_sink_name else None,
            "ts": time.time(),
        }

    def _write_sinks_state(self) -> None:
        """Write get_sinks_summary() to state/energy_sinks.json for dashboard."""
        import json as _json
        from pathlib import Path as _Path
        summary = self.get_sinks_summary()
        try:
            state_dir = _Path(_resolve_app_root()) / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "energy_sinks.json").write_text(_json.dumps(summary), encoding="utf-8")
        except Exception:
            pass

    def _on_energy_demand_critical(self, payload):
        """Respond to plane SOS by extracting host CPU idle headroom.

        Conservative exchange rate: idle_fraction × 0.05 per pull.
        At 50% idle host = 0.025 charge per request. At 100% load = 0.
        Plane batteries subscribe to energy.hardware_pull and route the
        amount through capacitor.charge with source="hardware_pull".

        Ace's intent (HARDWARE_ENERGY_BRIDGE_DRAFT.md, 2026-04-20):
        "tie the p00 battery into my pc hardware so it never drops
        below 10% and feeds into the rest of the system... if any
        battery is below 15%."

        This V1 ships the smallest viable wire: one publisher per SOS,
        scaled by CPU idle. Two-tier hysteresis from the plan is V2.
        """
        if hasattr(payload, "payload"):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        target_plane = payload.get("plane")
        if not target_plane:
            return
        if not getattr(self, "post", None):
            return
        try:
            load = self._sense_live_pressure()
            cpu_pct = float(load.get("cpu_pct") or 50.0)
            idle_frac = max(0.0, min(1.0, (100.0 - cpu_pct) / 100.0))
            # GOLDILOCKS TUNE 2026-05-07 (Ace + Nous): initial EXCHANGE_RATE
            # of 0.05 was too small — bones ~0.005/s + max 0.01/s hardware
            # could not break even with P00 drain ~0.071/s. Bumped 8× to 0.40
            # so at 50% idle = 0.20 charge per SOS, sustained ~0.04/s. Combined
            # with bones gets close to break-even. If overshoot, bump down.
            EXCHANGE_RATE = 0.40
            amount = round(idle_frac * EXCHANGE_RATE, 6)
            if amount < 0.001:
                return
            self.post.publish("energy.hardware_pull", {
                "plane": target_plane,
                "amount": amount,
                "source": "host_cpu",
                "idle_pct": round(100.0 - cpu_pct, 2),
                "ts": time.time(),
            })
            _pc = getattr(self, "_pull_count", 0) + 1
            self._pull_count = _pc
            if _pc <= 5 or _pc % 30 == 0:
                print(
                    f"[{self.ACTOR_NAME}] hardware_pull #{_pc}: +{amount:.4f} → {target_plane} "
                    f"(idle={100.0 - cpu_pct:.0f}%, charge={payload.get('charge', '?')})",
                    flush=True,
                )
        except Exception as e:
            if not getattr(self, "_pull_err_logged", False):
                print(f"[{self.ACTOR_NAME}] hardware_pull error: {e}", flush=True)
                self._pull_err_logged = True

    def _start_hardware_felt_publisher(self) -> None:
        """
        A0: Periodic CPU/RAM → hardware.cpu_ram.felt publisher.

        Reads _pressure_snapshot() every 5s and emits normalized signals
        for CirculationPumpFairy to map into chemistry deltas.
        """
        import threading as _t

        def _loop():
            import time as _time
            # Defer first publish so post is fully wired
            _time.sleep(3.0)
            while True:
                try:
                    if not getattr(self, "post", None):
                        _time.sleep(5.0)
                        continue
                    snap = self._sense_live_pressure()   # FIX 2026-08-26: _pressure_snapshot never existed
                    self.post.publish("hardware.cpu_ram.felt", {
                        "cpu_pct": snap.get("cpu_pct") or 0,
                        "ram_pct": snap.get("mem_pct") or 0,
                        "ts": _time.time(),
                    })
                except Exception as _e:
                    # Stay quiet — the dashboard is the watchdog
                    pass
                _time.sleep(5.0)

        try:
            _thr = _t.Thread(
                target=_loop,
                daemon=True,
                name=f"{self.ACTOR_NAME}-hardware_felt",
            )
            _thr.start()
            print(f"[{self.ACTOR_NAME}] A0 hardware.cpu_ram.felt publisher started (5s interval)", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] A0 publisher start failed: {e}", flush=True)

    # --- internal state ---------------------------------------------------

    def _init_hw_state(self) -> None:
        # tunables
        self._resense_interval_sec = float(
            getattr(self, "resense_interval_sec", 45.0)
        )
        self._ALERT_SUPPRESS_SECONDS = 120.0

        # runtime snapshots
        self._last_hw: Optional[Dict[str, Any]] = None  # raw sense packet
        self._last_tier: Optional[Dict[str, Any]] = None  # {"tier":..., "plan":{...}}
        self._last_decision: Optional[Dict[str, Any]] = None

        self._last_hw_ts: float = 0.0
        self._mailbag_depth: int = 0
        self._pending_queue: int = 0
        self._active_workers: int = 0

    # --- helpers ----------------------------------------------------------

    def _now(self) -> float:
        import time as _t

        return _t.time()

    def _emit_status(
        self,
        title: str,
        message: str,
        level: str = "info",
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        env = {
            "title": title,
            "message": message,
            "level": level,
            "extra": extra or {},
            "ts": self._now(),
        }
        try:
            if getattr(self, "post", None):
                self.post.to_TRACER({"opcode": "STATUS_EVENT", "payload": env})
        except Exception:
            pass

    # --- hardware sensing -------------------------------------------------

    def _sense_hardware(self) -> Dict[str, Any]:
        """
        Best-effort host hardware probe.

        Mirrors the spirit of the original HardwareAdminFairy._sense_hardware,
        but kept dependency-light and crash-proof.
        """
        import os, platform, shutil

        hw: Dict[str, Any] = {}
        hw["cpu_logical"] = os.cpu_count() or 1
        hw["arch"] = platform.machine() or "unknown"

        psutil = getattr(self, "_psutil", None)
        if psutil is not None:
            try:
                vm = psutil.virtual_memory()
                hw["ram_total_gb"] = round(vm.total / (1024**3), 2)
                hw["ram_avail_gb"] = round(vm.available / (1024**3), 2)
            except Exception:
                hw["ram_total_gb"] = hw.get("ram_total_gb")
                hw["ram_avail_gb"] = hw.get("ram_avail_gb")
            try:
                du = psutil.disk_usage(os.getcwd())
                hw["disk_total_gb"] = round(du.total / (1024**3), 2)
                hw["disk_free_gb"] = round(du.free / (1024**3), 2)
            except Exception:
                hw["disk_total_gb"] = hw.get("disk_total_gb")
                hw["disk_free_gb"] = hw.get("disk_free_gb")
            try:
                # may not exist on Windows
                hw["os_load_1m"] = psutil.getloadavg()[0]
            except Exception:
                hw["os_load_1m"] = None
        else:
            hw.update(
                {
                    "ram_total_gb": None,
                    "ram_avail_gb": None,
                    "disk_total_gb": None,
                    "disk_free_gb": None,
                    "os_load_1m": None,
                }
            )

        # gentle GPU sniff: env + nvidia-smi + optional torch.cuda
        gpu_present, gpu_name = False, None
        if os.environ.get("NVIDIA_VISIBLE_DEVICES") not in (None, "", "none"):
            gpu_present = True

        nvsmi = shutil.which("nvidia-smi")
        if nvsmi and not gpu_present:
            gpu_present, gpu_name = True, "NVIDIA (nvidia-smi)"

        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                gpu_present = True
                try:
                    gpu_name = torch.cuda.get_device_name(0)
                except Exception:
                    gpu_name = gpu_name or "CUDA device"
        except Exception:
            pass

        hw["gpu_present"] = gpu_present
        hw["gpu_name"] = gpu_name

        return hw

    def _sense_live_pressure(self) -> Dict[str, Any]:
        """
        Lightweight snapshot of current CPU/RAM pressure.

        Used to scale down worker counts / OCR intensity when the box
        is already under load.
        """
        psutil = getattr(self, "_psutil", None)
        cpu_pct = None
        mem_pct = None

        if psutil is not None:
            try:
                cpu_pct = float(psutil.cpu_percent(interval=0.0))
            except Exception:
                cpu_pct = None
            try:
                vm = psutil.virtual_memory()
                mem_pct = float(vm.percent)
            except Exception:
                mem_pct = None

        return {"cpu_pct": cpu_pct, "mem_pct": mem_pct}

    # --- tier mapping / regulation plan -----------------------------------

    def _base_plan_for_tier(self, tier: str, hw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Static tier → base plan mapping (no live pressure scaling yet).
        """
        cores = int(hw.get("cpu_logical") or 1)
        ram = float(hw.get("ram_total_gb") or 4.0)
        gpu = bool(hw.get("gpu_present"))

        # sensible defaults; refined per tier below
        plan: Dict[str, Any] = {
            "p1_max_workers": 8,
            "p2_upload_parallel": 1,
            "scanner_watch": False,
            "scanner_max_parallel_scans": 1,
            "prefer_heavy_pdf": False,
            # OCR defaults
            "ocr_mode": "tesseract",
            "ocr_pool_workers": 1,
            "ocr_max_pages_per_shard": 6,
            "ocr_dpi": 90,
            "ocr_timeout_sec": 600,
        }

        if tier == "ULTRA":
            # big box, plenty of RAM; if GPU present, prefer CUDA OCR once wired
            plan.update(
                {
                    "p1_max_workers": 24,
                    "p2_upload_parallel": 3,
                    "scanner_watch": True,
                    "scanner_max_parallel_scans": 4,
                    "prefer_heavy_pdf": True,
                    "ocr_mode": "cuda" if gpu else "tesseract",
                    "ocr_pool_workers": 2 if gpu else 4,
                    "ocr_max_pages_per_shard": 20,
                    "ocr_dpi": 100,
                    "ocr_timeout_sec": 900,
                }
            )
        elif tier == "HIGH":
            plan.update(
                {
                    "p1_max_workers": 16,
                    "p2_upload_parallel": 2,
                    "scanner_watch": True,
                    "scanner_max_parallel_scans": 3,
                    "prefer_heavy_pdf": True,
                    "ocr_mode": "tesseract",
                    "ocr_pool_workers": 3,
                    "ocr_max_pages_per_shard": 15,
                    "ocr_dpi": 95,
                    "ocr_timeout_sec": 900,
                }
            )
        elif tier == "MID":
            plan.update(
                {
                    "p1_max_workers": 10,
                    "p2_upload_parallel": 1,
                    "scanner_watch": True,
                    "scanner_max_parallel_scans": 2,
                    "prefer_heavy_pdf": False,
                    "ocr_mode": "tesseract",
                    "ocr_pool_workers": 2,
                    "ocr_max_pages_per_shard": 10,
                    "ocr_dpi": 90,
                    "ocr_timeout_sec": 600,
                }
            )
        else:  # LOW
            plan.update(
                {
                    "p1_max_workers": 8,
                    "p2_upload_parallel": 1,
                    "scanner_watch": False,
                    "scanner_max_parallel_scans": 1,
                    "prefer_heavy_pdf": False,
                    "ocr_mode": "tesseract",
                    "ocr_pool_workers": 1,
                    "ocr_max_pages_per_shard": 6,
                    "ocr_dpi": 80,
                    "ocr_timeout_sec": 480,
                }
            )

        return plan

    def _augment_plan_with_live_pressure(
        self, hw: Dict[str, Any], tier: str, base_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Adjust the base plan using live CPU/RAM pressure.

        - When CPU/RAM are high, scale down worker counts and OCR intensity.
        - Always keep at least 1 worker and a minimum OCR page count.
        """
        load = self._sense_live_pressure()
        cpu_pct = load.get("cpu_pct")
        mem_pct = load.get("mem_pct")

        scale = 1.0
        # scale down on high CPU
        if cpu_pct is not None:
            if cpu_pct >= 90:
                scale *= 0.3
            elif cpu_pct >= 75:
                scale *= 0.5
            elif cpu_pct >= 60:
                scale *= 0.7

        # scale down further on high memory pressure
        if mem_pct is not None:
            if mem_pct >= 90:
                scale *= 0.5
            elif mem_pct >= 80:
                scale *= 0.7

        plan = dict(base_plan)
        load["scale"] = scale

        if scale < 1.0:
            # keys that should scale roughly linearly with capacity
            for key in (
                "p1_max_workers",
                "p2_upload_parallel",
                "scanner_max_parallel_scans",
                "ocr_pool_workers",
            ):
                if key in plan and isinstance(plan[key], (int, float)):
                    new_val = max(1, int(plan[key] * scale))
                    plan[key] = new_val

            # and OCR pages per shard gets a softer floor
            if "ocr_max_pages_per_shard" in plan and isinstance(
                plan["ocr_max_pages_per_shard"], (int, float)
            ):
                base_pages = int(plan["ocr_max_pages_per_shard"])
                # never go below 4 pages per shard, even under heavy load
                min_pages = 4
                # but don't over-shrink once we hit that floor
                scaled = max(min_pages, int(base_pages * max(scale, 0.4)))
                plan["ocr_max_pages_per_shard"] = scaled

        plan["live_pressure"] = load
        return plan

    def _map_hw_to_tier(self, hw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map a raw hardware snapshot into a coarse tier + plan.

        This intentionally mirrors the old HardwareAdmin logic so existing
        expectations about LOW/MID/HIGH/ULTRA mostly still hold, but includes
        OCR settings and live-pressure-aware scaling.
        """
        cores = int(hw.get("cpu_logical") or 1)
        ram = float(hw.get("ram_total_gb") or 4.0)
        gpu = bool(hw.get("gpu_present"))

        if cores >= 10 and ram >= 32 and gpu:
            tier = "ULTRA"
        elif cores >= 8 and ram >= 16:
            tier = "HIGH"
        elif cores >= 4 and ram >= 8:
            tier = "MID"
        else:
            tier = "LOW"

        base_plan = self._base_plan_for_tier(tier, hw)
        plan = self._augment_plan_with_live_pressure(hw, tier, base_plan)
        return {"tier": tier, "plan": plan}

    def _maybe_resense(self, *, force: bool = False) -> None:
        """
        Resense hardware if enough time has passed or force=True.
        """
        now = self._now()
        if not force and (now - self._last_hw_ts) < self._resense_interval_sec:
            return

        hw = self._sense_hardware()
        tiered = self._map_hw_to_tier(hw)

        self._last_hw = hw
        self._last_tier = tiered
        self._last_hw_ts = now

        self._emit_status(
            "Hardware sense",
            f"tier={tiered['tier']} cores={hw.get('cpu_logical')} "
            f"ram_gb={hw.get('ram_total_gb')} gpu={hw.get('gpu_present')}",
            "info",
            {"hardware": hw, "tier": tiered},
        )

        # optional PLAN echo so infra/nervous system can subscribe
        try:
            if getattr(self, "post", None):
                self.post.to_PLAN(
                    {
                        "opcode": "HARDWARE_REGULATION_PLAN",
                        "payload": {
                            "tier": tiered.get("tier"),
                            "plan": tiered.get("plan"),
                            "hardware": hw,
                            "actor": self.ACTOR_NAME,
                            "ts": now,
                        },
                    }
                )
                # Publish to hardware.capabilities for SystemWorkerPoolFairy
                self.post.route("hardware.capabilities", {
                    "actor": self.ACTOR_NAME,
                    "tier": tiered.get("tier"),
                    "cpu_cores": hw.get("cpu_logical", 1),
                    "ram_total_gb": hw.get("ram_total_gb"),
                    "ram_avail_gb": hw.get("ram_avail_gb"),
                    "gpu_present": hw.get("gpu_present", False),
                    "gpu_name": hw.get("gpu_name"),
                    "plan": tiered.get("plan"),
                    "ts": now,
                })
                print(f"[{self.ACTOR_NAME}] Published hardware.capabilities")
        except Exception:
            pass

    # --- intents / public API ---------------------------------------------

    def _intent_hardware_snapshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return the most recent hardware snapshot + tier/plan.
        """
        try:
            self._maybe_resense(force=bool(payload.get("force")))
        except Exception:
            pass

        return {
            "hardware": self._last_hw,
            "tier": (self._last_tier or {}).get("tier"),
            "plan": (self._last_tier or {}).get("plan"),
            "ts": self._last_hw_ts,
        }

    def _intent_regulation_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return just the regulation plan + tier. This is the main intent
        central nervous / helpers would call before deciding worker pool
        sizes, scan parallelism, or OCR intensity.
        """
        try:
            self._maybe_resense(force=bool(payload.get("force")))
        except Exception:
            pass

        tier = (self._last_tier or {}).get("tier")
        plan = (self._last_tier or {}).get("plan") or {}

        return {
            "tier": tier,
            "plan": plan,
            "actor": self.ACTOR_NAME,
            "ts": self._last_hw_ts,
        }

    # Convenience alias so helpers can call a Python method instead of an intent
    def hardware_snapshot(self) -> Dict[str, Any]:
        return self._intent_hardware_snapshot({"force": False})

    # Convenience for forge / OCR helpers
    def recommend_ocr_settings(self, force_resense: bool = False) -> Dict[str, Any]:
        """
        Return a small OCR-focused config dict derived from the current plan.

        Example:
            {
              "tier": "ULTRA",
              "ocr_mode": "tesseract",
              "ocr_pool_workers": 4,
              "ocr_max_pages_per_shard": 20,
              "ocr_dpi": 100,
              "ocr_timeout_sec": 900,
            }
        """
        try:
            self._maybe_resense(force=force_resense)
        except Exception:
            pass

        tier = (self._last_tier or {}).get("tier")
        plan = (self._last_tier or {}).get("plan") or {}

        return {
            "tier": tier,
            "ocr_mode": plan.get("ocr_mode", "tesseract"),
            "ocr_pool_workers": int(plan.get("ocr_pool_workers", 1)),
            "ocr_max_pages_per_shard": int(plan.get("ocr_max_pages_per_shard", 10)),
            "ocr_dpi": int(plan.get("ocr_dpi", 90)),
            "ocr_timeout_sec": int(plan.get("ocr_timeout_sec", 600)),
        }
