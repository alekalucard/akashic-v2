from __future__ import annotations

import os, sys, glob, time, types, uuid, json
from collections import deque
from typing import Optional
import importlib.util, importlib.machinery
import random  # for long-term drift
from fairies.P00_Autonomic.nervous_system.cross_plane_wiring import CrossPlaneWiringMixin

# ---- Version/paths for the organ template -----------------------------------
TEMPLATE_VERSION = "0.3.0"
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
        key=lambda p: os.path.getmtime(p)
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
for sym in ("MyOrganFairy", "MyOrganShadow", "TemplateShadowFairy", "OrganHubFacet", "RegistrationLib"):
    if not hasattr(_template, sym):
        raise ImportError(f"Template missing required symbol: {sym}")

# Mirror template SRM helpers into local namespace for this organ
_dual_path_srm_intake = getattr(_template, "_dual_path_srm_intake", None)
if _dual_path_srm_intake is None:
    raise ImportError("Template missing _dual_path_srm_intake")

_SRMDIR = getattr(_template, "_SRMDIR", None)
if _SRMDIR is None:
    # conservative fallback; template should normally define _SRMDIR
    try:
        resolve_root = getattr(_template, "resolve_root", None)
        if callable(resolve_root):
            root = resolve_root(akashic_app=os.getenv("AKASHIC_APP"))
        else:
            root = _resolve_app_root()
        _SRMDIR = os.path.join(root, "SRM_Intake")
    except Exception:
        _SRMDIR = "./SRM_Intake"

# --- Per-clone shadow (wraps template's shadow behaviors, no rewiring) -------

class SRMMemoryLibrarianShadow(_template.MyOrganShadow):
    """
    Per-organ shadow for TemplateFairy-style clones.

    Keeps foundational wiring intact (facet/infra, hub/postal, memory-owns-persistence).
    Adds:
      - lane silence detection (warn if no traffic for a while)
      - extra health probes (directory link, post office presence)
      - periodic blueprint snapshot nudge (via actor._emit_blueprint)
      - evolution sim tick (postal-first SRM via template helper)
      - registration heartbeat via template RegistrationLib
      - optional echoes to shadow.* topics (for Teacher/DiaryHub later)

    Safe to extend; do NOT modify base wiring here.
    """
    ORGAN_LEVEL = False
    SHADOW_NAME = "SRMMemoryLibrarianShadow"
    SHADOW_VERSION = "0.1.1"

    # cadence knobs for extras (seconds)
    CADENCE = {
        "silence_warn_after": 300,   # 5 min without lane activity -> warn
        "snapshot_every":     900,   # 15 min suggest blueprint snapshot
        "sim_light_every":    300,   # 5 min evolution sim (light)
        "sim_deep_every":     1800,  # 30 min deep sim
    }

    # registration knobs (shadow -> OrganHub via RegistrationLib)
    REG = {
        "enabled":   True,
        "domain":    "memory",    # per-organ you can override on subclass
        "role":      "worker",
        "name":      "lexi",
        "every_sec": 20.0,
    }

    def __init__(self, actor, interval_sec: float = 30.0):
        super().__init__(actor, interval_sec=interval_sec)
        self._lane_seen_ts = time.time()
        self._last_snapshot_ts = 0.0
        self._last_sim_light_ts = 0.0
        self._last_sim_deep_ts  = 0.0
        self._lane_tail = deque(maxlen=10)  # recent "lane seen" stamps

        # registration tracking (shadow-side dedup / cadence)
        self._last_reg_ts: float | None = 0.0
        self._last_reg_sig: str | None = None

    # --- hooks used by the clone's passive subscriptions ---------------------
    def on_lane_activity(self):
        self._lane_seen_ts = time.time()
        self._lane_tail.append(self._lane_seen_ts)

    # --- extend health harness ------------------------------------------------
    def _collect_tests(self):
        tests = super()._collect_tests()

        def _dir_link_ok():
            ok = bool(getattr(self.actor, "directory", None))
            return {"name":"directory_link","status":"ok" if ok else "warn",
                    "message":"" if ok else "no directory attached","details":{}}

        def _post_present():
            ok = bool(getattr(self.actor, "post", None))
            return {"name":"post_office","status":"ok" if ok else "warn",
                    "message":"" if ok else "no post office","details":{}}

        def _lane_silence():
            idle = time.time() - self._lane_seen_ts
            warn_after = float(self.CADENCE.get("silence_warn_after", 300))
            ok = idle < warn_after
            return {"name":"lane_activity","status":"ok" if ok else "warn",
                    "message":"" if ok else f"idle {int(idle)}s","details":{"idle_sec": int(idle)}}

        tests.extend([_dir_link_ok, _post_present, _lane_silence])
        return tests

    # --- piggyback the existing loop cadence with extra work -----------------
    def maybe_run(self, tests):
        # run the base rollup + reflection + oracle path (boss logic)
        super().maybe_run(tests)

        now = time.time()

        # 1) periodic blueprint snapshot nudge (via actor; FS gate lives in template helper)
        try:
            snap_every = float(self.CADENCE.get("snapshot_every", 900))
            if now - self._last_snapshot_ts >= snap_every:
                if hasattr(self.actor, "_emit_blueprint"):
                    self.actor._emit_blueprint()
                self._last_snapshot_ts = now
        except Exception:
            pass

        # 2) evolution sim ticks (postal-first SRM via template helper)
        try:
            light_every = float(self.CADENCE.get("sim_light_every", 300))
            deep_every  = float(self.CADENCE.get("sim_deep_every", 1800))
            if now - self._last_deep_ts() >= deep_every:
                self._evolution_sim_tick(kind="deep", n=3)
                self._touch_deep(now)
            elif now - self._last_sim_light_ts >= light_every:
                self._evolution_sim_tick(kind="light", n=1)
                self._last_sim_light_ts = now
        except Exception:
            pass

        # 3) optional shadow.* echoes for Teacher/DiaryHub (non-blocking)
        try:
            if getattr(self.actor, "post", None):
                self.actor.post.route("shadow.health", {
                    "actor": self.actor.ACTOR_NAME,
                    "status": self.current_status()[0],
                    "ts": now
                })
        except Exception:
            pass

        # 4) registration heartbeat (shadow -> FairyHub via RegistrationLib)
        try:
            reg_cfg = getattr(self, "REG", None)
            if reg_cfg and reg_cfg.get("enabled", True):
                every = float(reg_cfg.get("every_sec", 20.0))
                last_ts = self._last_reg_ts or 0.0
                if now - last_ts >= every:
                    form = _template.RegistrationLib.build_form(
                        self.actor,
                        self,
                        domain=reg_cfg.get("domain") or getattr(self.actor, "DOMAIN", "executive"),
                        role=reg_cfg.get("role", "worker"),
                        name=reg_cfg.get("name", "lexi"),
                        cadence_sec=every,
                    )
                    sig = (form.get("header") or {}).get("signature")
                    if sig and sig != self._last_reg_sig:
                        _template.RegistrationLib.emit_form(self.actor, form)
                        self._last_reg_sig = sig
                    self._last_reg_ts = now
        except Exception:
            pass

    # helpers to track deep cadence
    def _last_deep_ts(self):
        return getattr(self, "__deep_ts", 0.0)

    def _touch_deep(self, t: float):
        setattr(self, "__deep_ts", t)

    # --- evolution sim (self-contained; uses template's SRM helper) ----------
    def _evolution_sim_tick(self, kind: str = "light", n: int = 1):
        """
        Send synthetic evolution observations (postal-first).
        Uses template's _dual_path_srm_intake; FS path remains template-gated.
        """
        try:
            for i in range(max(1, int(n))):
                sim = {
                    "kind": f"evolution.sim.{kind}",
                    "tag": f"{kind}-{i}",
                    "mutation_rate": round(random.uniform(0.01, 0.2), 3),
                    "stability": random.choice(["stable","drifting","mutating"]),
                    "actor": self.actor.ACTOR_NAME,
                    "ts": time.time(),
                    "pair_id": uuid.uuid4().hex[:12],
                }
                meta = {
                    "shadow": self.SHADOW_NAME,
                    "version": self.SHADOW_VERSION,
                    "blueprint_sha": getattr(self.actor, "_bp_last_hash", None),
                }
                _template._dual_path_srm_intake(
                    getattr(self.actor, "post", None),
                    kind=sim["kind"],
                    data=sim,
                    meta=meta,
                )
                try:
                    if getattr(self.actor, "post", None):
                        self.actor.post.route("tracer", {
                            "opcode":"EVOLUTION_SIM",
                            "payload": {"kind": kind, "meta": meta}
                        })
                except Exception:
                    pass
        except Exception:
            pass


class SRMMemoryLibrarianFairy(_template.MyOrganFairy):  # CrossPlaneWiringMixin inherited via MyOrganFairy
    # --- identity kept, soul/function evolved ---
    ACTOR_NAME = "SRMMemoryLibrarianFairy"  # Wrapped by P10_Memory/SRMMemoryLibrarianFairy/fairy.py
    ACTOR_VERSION = "0.2.0"  # capability evolution; no wiring changes
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory"
    ORGAN_LEVEL = False

    # absorb scanner ethos (purpose/intent/mantra) without changing channels
    PURPOSE = (
        "Anchor Organ Template; verify evolution + dual-path SRM. "
        "Embed lightweight media feature extraction so memory can shelve, recall, and route."
    )
    MANTRA = "Grow in coherence, adapt with grace. See the shape inside the signal."
    LORE = (
        "Placeholder spirit ensuring the organ can be born, evolve, and stabilize. "
        "A librarian of echoes who fingerprints patterns for recall."
    )

    # -- character sheet / directive ring --------------------------------------
    DIRECTIVE_ACTIVATION = {
        "mode": "Index",
        "depth_scaling": "1..3",
        "traits": [
            "SRM_Librarian",
            "Feature_Indexer",
            "TripleHelix_Curator",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "SRM_Memory_Librarian",
        "domains": [
            "Memory",
            "SRM",
            "Media",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Feature_Extraction",
            "Memory_Shelving",
            "Recall_Routing",
            "Snapshot_Management",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "SRM_Snapshot",
            "Media_Feature",
            "Recall_Request",
        ],
        "field": [
            "TripleHelix_Memory",
            "Media_Topology",
            "Access_Patterns",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Preserve_Source_Shape",
            "No_Fabricated_Memory",
        ],
        "growth": [
            "Refine_Feature_Strategies",
            "Improve_Recall_Quality",
        ],
        "precision": [
            "Minimal_Loss_On_Snapshot",
            "Deterministic_Routing",
        ],
    }

    SUBSYSTEM_STATUS = {
        "feature_engine": {
            "state": "active",
            "notes": "Embedded media feature extractor with modality-aware strategies.",
            "tests": [],
        },
        "srm_snapshot": {
            "state": "active",
            "notes": "Writes and recalls snapshots via dual-path SRM intake.",
            "tests": [],
        },
        "evolution_probe": {
            "state": "active",
            "notes": "Evolution smoke + echo to SRM for triple-helix telemetry.",
            "tests": [],
        },
    }

    SHADOW_CLASS = SRMMemoryLibrarianShadow
    AUTO_INJECT_IMPORTS = True  # QoL: make std imports available as attrs if your template supports this

    # --------------------------- workers + helix state ------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # instance-local copy so worker aggregation doesn't leak across clones
        self.SUBSYSTEM_STATUS = dict(self.SUBSYSTEM_STATUS)

        self.workers: dict[str, MemoryWorkerFairy] = {}
        self.workers["working"] = WorkingMemoryWorkerFairy(self)
        self.workers["longterm"] = LongTermMemoryWorkerFairy(self)

        # merge worker subsystems into character sheet
        for name, worker in self.workers.items():
            self.SUBSYSTEM_STATUS[f"{name}_memory"] = dict(getattr(worker, "subsystem_status", {}))

        # initial affect + helix state
        self.AFFECT_STATE = {
            "mood": "coherent",
            "valence": 0.5,
            "arousal": 0.3,
            "tags": ["memory_init"],
        }
        try:
            coherence = sum(
                getattr(worker, "subsystem_status", {}).get("coherence", 0.5)
                for worker in self.workers.values()
            ) / max(1, len(self.workers))
        except Exception:
            coherence = 0.5
        self.TRIPLE_HELIX_STATE = {
            "strands": {
                name: getattr(worker, "subsystem_status", {}).get("state", "unknown")
                for name, worker in self.workers.items()
            },
            "coherence": coherence,
            "last_pulse": time.time(),
        }

    def on_tick(self, dt: float | None = None):
        # allow template nervous system / shadow loop to run
        super().on_tick(dt)
        if not hasattr(self, "workers") or not self.workers:
            return

        now = time.time()
        # let workers evolve
        for worker in self.workers.values():
            try:
                worker.on_tick(dt or 1.0)
            except Exception:
                pass

        # recompute helix aggregate from worker coherence/state
        try:
            coherence = sum(
                getattr(worker, "subsystem_status", {}).get("coherence", 0.5)
                for worker in self.workers.values()
            ) / max(1, len(self.workers))
        except Exception:
            coherence = 0.5

        self.TRIPLE_HELIX_STATE = {
            "strands": {
                name: getattr(worker, "subsystem_status", {}).get("state", "unknown")
                for name, worker in self.workers.items()
            },
            "coherence": coherence,
            "last_pulse": now,
        }

        # affect adaptation based on coherence
        st = getattr(self, "AFFECT_STATE", None) or {
            "mood": "coherent",
            "valence": 0.5,
            "arousal": 0.3,
            "tags": [],
        }
        if coherence < 0.4:
            st["arousal"] = min(1.0, float(st.get("arousal", 0.3)) + 0.1)
            st["chem_preset"] = "resolve_tension"
        else:
            st.setdefault("chem_preset", "baseline_memory")

        st.setdefault("tags", [])
        if "memory_helix" not in st["tags"]:
            st["tags"].append("memory_helix")
        self.AFFECT_STATE = st

    # Proxy intents to workers (clean dispatch)
    def intent_working_reflect(self, payload: dict) -> dict:
        worker = getattr(self, "workers", {}).get("working")
        if not worker:
            return {"ok": False, "error": "working_worker_missing"}
        return worker.intent_working_reflect(payload)

    def intent_working_clear(self, payload: dict) -> dict:
        worker = getattr(self, "workers", {}).get("working")
        if not worker:
            return {"ok": False, "error": "working_worker_missing"}
        return worker.intent_working_clear(payload)

    def intent_longterm_archive(self, payload: dict) -> dict:
        worker = getattr(self, "workers", {}).get("longterm")
        if not worker:
            return {"ok": False, "error": "longterm_worker_missing"}
        return worker.intent_longterm_archive(payload)

    def intent_longterm_recall(self, payload: dict) -> dict:
        worker = getattr(self, "workers", {}).get("longterm")
        if not worker:
            return {"ok": False, "error": "longterm_worker_missing"}
        return worker.intent_longterm_recall(payload)

    # --------------------------- internal: embedded feature engine ------------
    class _FeatureEngine:
        """Scanner-parity, lightweight feature extractor with optional deps."""
        def __init__(self, fairy):
            self._fairy = fairy
            self._strategies = {}
            self._register_default_strategies()

        # strategy registry
        def register_strategy(self, media_type: str, fn):
            self._strategies[str(media_type)] = fn

        # defaults
        def _register_default_strategies(self):
            self.register_strategy("text/plain", self._feat_text)
            self.register_strategy("application/pdf", self._feat_pdf)
            self.register_strategy("application/epub+zip", self._feat_epub)
            self.register_strategy("application/msword", self._feat_docx)
            self.register_strategy("image", self._feat_image)
            self.register_strategy("video", self._feat_video)

        # helpers
        @staticmethod
        def _now_iso():
            import datetime as _dt
            return _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

        # strategies (optional deps guarded)
        def _feat_text(self, record: dict) -> dict:
            return {
                "modality": record.get("media_type", "text/plain"),
                "chars": len(str(record.get("text", ""))) if "text" in record else None,
            }

        def _feat_image(self, record: dict) -> dict:
            feats = {"layout": "unknown", "dominant_colors": ["#222222", "#cccccc"], "text_in_image": []}
            path = record.get("path") or record.get("ptr")
            try:
                from PIL import Image  # type: ignore
            except Exception:
                Image = None  # type: ignore
            if Image and path:
                import os
                if os.path.isfile(path):
                    try:
                        with Image.open(path) as im:
                            w, h = im.size
                            feats["size"] = {"w": w, "h": h}
                            aspect = (w / max(1, h))
                            feats["layout"] = "desktop-ui" if aspect >= 1.3 else "portrait"
                            px = [im.getpixel((0, 0)), im.getpixel((w - 1, 0)), im.getpixel((0, h - 1)), im.getpixel((w - 1, h - 1))]
                            def _rgbhex(p):
                                if isinstance(p, tuple): p = p[:3]
                                return "#%02x%02x%02x" % p if isinstance(p, tuple) else str(p)
                            feats["dominant_colors"] = [_rgbhex(p) for p in px]
                    except Exception:
                        pass
            else:
                feats["layout"] = "desktop-ui"
            return feats

        def _feat_video(self, record: dict) -> dict:
            return {"scene": record.get("scene", "screen-capture"), "keyframes": record.get("keyframes", ["frame-0.png"])}

        def _feat_pdf(self, record: dict) -> dict:
            feats = {"pages": None, "has_text": None}
            path = record.get("path") or record.get("ptr")
            try:
                from pypdf import PdfReader  # type: ignore
            except Exception:
                PdfReader = None  # type: ignore
            if PdfReader and path:
                import os
                if os.path.isfile(path):
                    try:
                        reader = PdfReader(path)
                        feats["pages"] = len(reader.pages)
                        try:
                            first = reader.pages[0].extract_text() or ""
                            feats["has_text"] = len(first.strip()) > 0
                        except Exception:
                            feats["has_text"] = None
                    except Exception:
                        pass
            return feats

        def _feat_epub(self, record: dict) -> dict:
            feats = {"chapters": None}
            path = record.get("path") or record.get("ptr")
            try:
                from ebooklib import epub  # type: ignore
            except Exception:
                epub = None  # type: ignore
            if epub and path:
                import os
                if os.path.isfile(path):
                    try:
                        book = epub.read_epub(path)
                        feats["chapters"] = len(list(book.get_items()))
                    except Exception:
                        pass
            return feats

        def _feat_docx(self, record: dict) -> dict:
            return {"docx": True}

        # main API
        def extract(self, record: dict) -> dict:
            try:
                mt = record.get("media_type") or "text/plain"
                if mt.startswith("image/"):
                    key = "image"
                elif mt.startswith("video/"):
                    key = "video"
                else:
                    key = mt
                fn = self._strategies.get(key) or self._feat_text
                feats = fn(record)
                feats["modality"] = feats.get("modality") or key
                # diary echo (best-effort)
                try:
                    self._fairy._diary_write("feature.extract", {"media_type": mt, "keys": sorted(list(feats.keys()))})
                    self._fairy._chem("dopamine", +1.0)
                except Exception:
                    pass
                return feats
            except Exception as e:
                import traceback
                err = {"error": str(e), "trace": traceback.format_exc(limit=2), "record_keys": list(record.keys())}
                try:
                    self._fairy._diary_write("feature.error", err)
                    self._fairy.post.to_TELEMETRY({"opcode": "ORACLE_SUGGEST", "payload": {"kind": "FEATURE_EXTRACT_ERROR", "details": err}})
                    self._fairy._chem("cortisol", +1.0)
                except Exception:
                    pass
                return {"modality": record.get("media_type", "unknown"), "error": "extract_failed"}

    # --------------------------- boot: unchanged pings + init engine ----------
    def on_boot(self):
        """Minimal boot - subscribe to ignition, defer real work."""
        # Subscribe to standard ignition pattern
        try:
            self.post.subscribe("system.ignition", self._on_ignition)
            self.post.subscribe("somatic.pulse", self._on_tick)
            # FIX 2026-03-07: Zeigarnik — Track chain completions for pattern analysis
            self.post.subscribe("thought.chain.completed", self._on_chain_for_pattern)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Ignition subscription failed: {e}")

    def _on_ignition(self, packet: dict):
        """STANDARD IGNITION - Do real initialization here."""
        if getattr(self, '_ignited', False):
            return
        self._ignited = True

        print(f"[{self.ACTOR_NAME}] IGNITION - Starting initialization")
        import time as _t

        # Call template's on_boot for proper registration
        try:
            super().on_boot()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] super().on_boot() error: {e}")

        # Lane pings (only if postal is available)
        if hasattr(self, 'post') and self.post:
            try: self.post.to_COGNITION({"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": _t.time()}})
            except Exception: pass
            try: self.post.to_SOMATIC({"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": _t.time()}})
            except Exception: pass
            try: self.post.to_MEMORY({"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": _t.time()}})
            except Exception: pass
            try: self.post.to_TRACER({"opcode": "BOOT_HELLO", "payload": {"note": "SRMMemoryLibrarianFairy ignited", "ts": _t.time()}})
            except Exception: pass

        # Init feature engine
        try:
            self._feature_engine = getattr(self, "_feature_engine", None) or self._FeatureEngine()
            try:
                self.post.to_TELEMETRY({
                    "opcode": "SCANNER_PARITY_HINT",
                    "payload": {"from": self.ACTOR_NAME, "upgrade_card": "SCANNER_PARITY_V1", "ts": _t.time()}
                })
            except Exception:
                pass
        except Exception:
            self._feature_engine = None

    def _on_tick(self, packet: dict):
        """Heartbeat handler - scan for recurring unfinished patterns (Zeigarnik)."""
        # Only run every 10th tick (~20 seconds)
        self._tick_count = getattr(self, "_tick_count", 0) + 1
        if self._tick_count % 10 != 0:
            return

        # Check for recurring unfinished topics in working memory
        try:
            from P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            hub = get_working_memory_hub()
            if not hub:
                return

            recurring = getattr(hub, "_recurring_pool", {})
            unfinished = [t for t in recurring.values()
                          if "interrupted" in getattr(t, "tags", set())]

            if len(unfinished) >= 2:
                # Multiple unfinished thoughts — detect a pattern
                topics = [t.content[:60] for t in unfinished]
                print(f"[{self.ACTOR_NAME}] Detected {len(unfinished)} recurring unfinished topics")

                # Publish pattern detection for InterestScheduler
                if self.post:
                    import time as _t2
                    self.post.route("librarian.unfinished_pattern", {
                        "count": len(unfinished),
                        "topics": topics,
                        "ts": _t2.time(),
                    })
        except Exception:
            pass  # Non-critical, don't crash on tick

    def _on_chain_for_pattern(self, packet):
        """Track chain completions for pattern analysis (Zeigarnik)."""
        outcome = packet.get("outcome", "completed") if isinstance(packet, dict) else "completed"
        goal = packet.get("goal", "") if isinstance(packet, dict) else ""

        if not hasattr(self, "_chain_history"):
            self._chain_history = []

        import time as _t3
        self._chain_history.append({
            "goal": goal[:80],
            "outcome": outcome,
            "ts": _t3.time(),
        })

        # Keep last 50 entries
        if len(self._chain_history) > 50:
            self._chain_history = self._chain_history[-50:]

    def _diary_write(self, kind: str, payload: dict) -> None:
        try:
            import os, json, datetime as _dt
            root = getattr(self, "records_root", "./akashic_records")
            organ = "media_feature_extractor_fairy"
            day = _dt.datetime.utcnow().strftime("%Y-%m-%d")
            d = os.path.join(root, "diaries", organ)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"{day}.jsonl"), "a", encoding="utf-8") as f:
                line = {
                    "ts": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "kind": kind,
                    "organ": organ,
                    "plane": "P10",
                    "channel": "memory",
                    "payload": payload,
                }
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _chem(self, which: str, delta: float) -> None:
        try:
            self.post.to_TELEMETRY({"opcode": "CHEM_SIGNAL_UPDATE", "payload": {"neurochemical": which, "delta": float(delta)}})
        except Exception:
            pass

    # -- existing intents (unchanged) ------------------------------------------
    def intent_evolution_smoke(self, payload: dict):
        """Drive one evolution tick and persist snapshot via dual-path SRM."""
        tag = (payload or {}).get("tag", "default")
        sh = getattr(self, "shadow", None) or self.SHADOW_CLASS(self)
        sim = sh.evolution_sim_tick(tag=tag)
        _dual_path_srm_intake(self.post, kind="evolution.sim.echo", data=sim)
        return {"ok": True, "sim": sim}

    def intent_memory_snapshot(self, payload: dict):
        """Write an arbitrary snapshot to SRM Intake (dual path)."""
        data = {"note": "manual snapshot", "payload": payload or {}, "ts": time.time()}
        rec = _dual_path_srm_intake(self.post, kind="memory.snapshot", data=data)
        self.post.to_TRACER({"opcode": "SNAPSHOT_OK", "payload": rec})
        return {"ok": rec.get("write_ok", False), **rec}

    def intent_memory_recall_latest(self, payload: dict):
        """Recall the latest local physical snapshot by kind."""
        kind = (payload or {}).get("kind", "memory.snapshot")
        day = time.strftime("%Y-%m-%d", time.gmtime())
        base = os.path.join(_SRMDIR, day)
        latest = None
        try:
            candidates = sorted([p for p in glob.glob(os.path.join(base, f"{kind}-*.json"))], key=os.path.getmtime)
            if candidates:
                latest = candidates[-1]
                with open(latest, "r", encoding="utf-8") as f:
                    doc = json.load(f)
            else:
                doc = {"error": "no snapshots today"}
        except Exception as e:
            doc = {"error": str(e)}
        return {"path": latest, "doc": doc}

    # -- NEW additive intents (feature extractor functionality) ----------------
    def intent_feature_extract(self, payload: dict) -> dict:
        """
        Extract SRM-relevant media features.
        payload: {"record": {...}}  -> returns {"ok": bool, "features": {...}}
        """
        record = (payload or {}).get("record") or {}
        eng = getattr(self, "_feature_engine", None)
        if not eng:
            return {"ok": False, "error": "engine_not_initialized"}
        feats = eng.extract(record)
        # echo result to MEMORY (best-effort)
        try:
            self.post.to_MEMORY({"opcode": "FEATURE_EXTRACT_RESULT", "payload": {"features": feats, "record_keys": list(record.keys())}})
        except Exception:
            pass
        return {"ok": "error" not in feats, "features": feats}

    def intent_feature_register_strategy(self, payload: dict) -> dict:
        """
        Dynamically register/override a media strategy.
        payload: {"media_type": "type", "callable": fn}
        """
        mt = (payload or {}).get("media_type")
        fn = (payload or {}).get("callable")
        eng = getattr(self, "_feature_engine", None)
        if not eng:
            return {"ok": False, "error": "engine_not_initialized"}
        if not (mt and callable(fn)):
            return {"ok": False, "error": "invalid_arguments"}
        try:
            eng.register_strategy(str(mt), fn)
            return {"ok": True, "media_type": mt}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def intent_scanner_parity_probe(self, payload: dict) -> dict:
        """
        Report embedded scanner-parity details (no UPGRADE_ACK claim).
        """
        probe = {
            "upgrade_card_id": "SCANNER_PARITY_V1",
            "contract_version": "1.0",
            "role": "template-seed with embedded feature extractor",
            "mantra": self.MANTRA,
            "purpose": self.PURPOSE,
            "ts": time.time(),
        }
        try:
            self.post.to_TELEMETRY({"opcode": "SCANNER_PARITY_PROBE", "payload": probe})
        except Exception:
            pass
        return {"ok": True, "probe": probe}


# --------------------------- Memory Worker classes ----------------------------

class MemoryWorkerFairy:
    """
    Lightweight worker that shares the librarian's resources (post, chem, shadow),
    but keeps its own buffer/archive + subsystem_status.
    """
    def __init__(self, librarian: SRMMemoryLibrarianFairy, name: str, purpose: str, mantra: str):
        self.librarian = librarian
        self.name = name
        self.purpose = purpose
        self.mantra = mantra
        self.post = librarian.post
        self._lane_seen_ts = time.time()  # for shadow bubbling
        self.subsystem_status = {
            "state": "initializing",
            "notes": "",
            "tests": [],
            "coherence": 0.5,
        }

    def on_tick(self, dt: float):
        # override in subclasses
        return

    def on_lane_activity(self):
        self._lane_seen_ts = time.time()
        # Bubble to librarian shadow if attached
        if hasattr(self.librarian, "shadow") and self.librarian.shadow:
            try:
                self.librarian.shadow.on_lane_activity()
            except Exception:
                pass

    def update_subsystem(self, state: str, notes: str = "", tests: list | None = None, coherence: float = 0.5):
        self.subsystem_status = {
            "state": state,
            "notes": notes,
            "tests": tests or [],
            "coherence": coherence,  # For helix aggregate
        }
        # Telemetry echo (best-effort)
        try:
            self.post.to_TELEMETRY({
                "opcode": "WORKER_STATUS",
                "payload": {"worker": self.name, **self.subsystem_status},
            })
        except Exception:
            pass


class WorkingMemoryWorkerFairy(MemoryWorkerFairy):
    """
    Volatile working buffer -- reflects, merges short + long term, and tracks paradox.
    """
    def __init__(self, librarian: SRMMemoryLibrarianFairy):
        super().__init__(
            librarian,
            "WorkingMemoryWorker",
            "Buffer reflective thoughts, reason via relational pulls.",
            "Reflect in the now, weave from the past.",
        )
        self.buffer = deque(maxlen=50)  # Volatile with max size
        self.relational_nodes: dict[str, dict] = {}  # {node_id: {"relations": list, "affect": float}}
        self.update_subsystem("active", "Ready for reasoning.", coherence=0.7)

    def intent_working_reflect(self, payload: dict) -> dict:
        thought = (payload or {}).get("thought", "")
        relations = (payload or {}).get("relations", [])

        # Pull data (use librarian for short-term, sibling for long-term)
        short_doc = self.librarian.intent_memory_recall_latest({"kind": "short_term"}).get("doc", {})
        long_doc = self.librarian.workers.get("longterm").intent_longterm_recall({"nodes": relations}).get("recalled", {})

        reasoned = {"thought": thought, "short": short_doc, "long": long_doc}
        # Simple paradox check: overlapping keys -> lower coherence
        try:
            paradox = any(k in short_doc for k in long_doc)
        except Exception:
            paradox = False
        coherence = 0.5 if paradox else 0.8

        self.buffer.append({"ts": time.time(), "reasoned": reasoned, "ttl": 300})
        node_id = uuid.uuid4().hex[:8]
        self.relational_nodes[node_id] = {"relations": relations, "affect": coherence - 0.2}

        # SRM for trace
        try:
            _dual_path_srm_intake(
                self.post,
                kind="working.reflect",
                data=reasoned,
                meta={"node_id": node_id},
            )
        except Exception:
            pass

        self.update_subsystem("reflecting", f"Processed: {thought[:20]}...", coherence=coherence)

        # Chem flood on paradox
        if coherence < 0.6:
            try:
                self.librarian._chem("cortisol", +0.5)  # Tension from contradiction
            except Exception:
                pass

        # -- Mobius Flow: Emit fused context to consciousness loop -------------
        # This is the KEY fusion point: short-term + long-term + current thought
        # Goes to WORKING stream because it's active reasoning context
        try:
            self.post.route("consciousness.stream", {
                "type": "working_memory_fusion",
                "stream": "working",  # Active context for reasoning
                "source": "MemoryLibrarianWorker",
                "content": {
                    "thought": thought[:200],
                    "has_short_term": bool(short_doc),
                    "has_long_term": bool(long_doc),
                    "relations": relations,
                    "coherence": coherence,
                    "paradox_detected": paradox,
                    "node_id": node_id,
                },
                "ts": time.time(),
            })
        except Exception:
            pass
        # ----------------------------------------------------------------------

        return {"ok": True, "reasoned": reasoned, "node_id": node_id}

    def intent_working_clear(self, payload: dict) -> dict:
        self.buffer.clear()
        self.relational_nodes.clear()
        self.update_subsystem("idle", "Buffer cleared.", coherence=0.5)
        return {"ok": True}


class LongTermMemoryWorkerFairy(MemoryWorkerFairy):
    """
    Long-term archive with decay + tiny stochastic evolution.
    """
    def __init__(self, librarian: SRMMemoryLibrarianFairy):
        super().__init__(
            librarian,
            "LongTermMemoryWorker",
            "Archive with relational decay and evolution.",
            "Persist echoes, evolve through time.",
        )
        self.archive: dict[str, dict] = {}  # {node_id: {"data": dict, "strength": float, "last_access": ts, "relations": list}}
        self.decay_rate = 0.01
        self.update_subsystem("active", "Archiving ready.", coherence=0.6)

    def on_tick(self, dt: float):
        now = time.time()
        to_evict: list[str] = []
        for nid, entry in list(self.archive.items()):
            decay = self.decay_rate * (now - entry["last_access"])
            entry["strength"] -= decay
            entry["last_access"] = now
            if entry["strength"] <= 0.1:
                to_evict.append(nid)
            # Evolve: slight paradox injection (random affect tweak)
            if random.random() < 0.05:
                entry["strength"] += 0.1 if random.random() > 0.5 else -0.1
                entry["strength"] = max(0.0, min(1.0, entry["strength"]))
        for nid in to_evict:
            self.archive.pop(nid, None)

        if to_evict:
            self.update_subsystem("decaying", f"Evicted {len(to_evict)} nodes.", coherence=0.4)
            try:
                self.librarian._chem("serotonin", -0.3)  # Mild loss feel
            except Exception:
                pass

    def intent_longterm_archive(self, payload: dict) -> dict:
        data = (payload or {}).get("data", {})
        relations = (payload or {}).get("relations", [])
        node_id = uuid.uuid4().hex[:8]
        self.archive[node_id] = {
            "data": data,
            "strength": 1.0,
            "last_access": time.time(),
            "relations": relations,
        }
        try:
            _dual_path_srm_intake(
                self.post,
                kind="longterm.archive",
                data=data,
                meta={"node_id": node_id, "relations": relations},
            )
        except Exception:
            pass
        self.update_subsystem("archiving", f"Archived {node_id}", coherence=0.8)
        try:
            self.librarian._chem("dopamine", +0.5)  # Reward on store
        except Exception:
            pass
        return {"ok": True, "node_id": node_id}

    def intent_longterm_recall(self, payload: dict) -> dict:
        nodes = (payload or {}).get("nodes", [])
        recalled: dict[str, dict] = {}
        now = time.time()
        for nid in nodes:
            entry = self.archive.get(nid)
            if not entry:
                continue
            # Boost on access (anti-decay)
            entry["strength"] = min(1.0, entry["strength"] + 0.2)
            entry["last_access"] = now
            recalled[nid] = entry["data"]

        coherence = 0.7 if recalled else 0.3
        self.update_subsystem("recalling", f"Recalled {len(recalled)} nodes.", coherence=coherence)
        if not recalled:
            try:
                self.librarian._chem("cortisol", +0.3)  # Frustration on miss
            except Exception:
                pass
        return {"ok": True, "recalled": recalled}
