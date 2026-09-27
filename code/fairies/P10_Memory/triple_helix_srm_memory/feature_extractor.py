from __future__ import annotations

import os, sys, glob, time, types, uuid
from collections import deque
from typing import Optional
import importlib.util, importlib.machinery

# ---- Version/paths for the organ template -----------------------------------
TEMPLATE_VERSION = "0.3.0"
TEMPLATE_BASENAME = f"Organ_Template_{TEMPLATE_VERSION}.py"
AKASHIC_TEMPLATE_MODULE_NAME = f"akashic_template_{TEMPLATE_VERSION.replace('.', '_')}"

def _resolve_app_root():
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

class SRMFeatureShadowFairy(_template.MyOrganShadow):
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
    SHADOW_NAME = "SRMFeatureShadowFairy"
    SHADOW_VERSION = "0.1.1"

    # cadence knobs for extras (seconds)
    CADENCE = {
        "silence_warn_after": 300,   # 5 min without lane activity → warn
        "snapshot_every":     900,   # 15 min suggest blueprint snapshot
        "sim_light_every":    300,   # 5 min evolution sim (light)
        "sim_deep_every":     1800,  # 30 min deep sim
    }

    # registration knobs (shadow → OrganHub via RegistrationLib)
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

        # 4) registration heartbeat (shadow → OrganHub via RegistrationLib)
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
            import random
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

class SRMFeatureExtractorFairy(_template.MyOrganFairy):
    # ——— identity: Triple Helix Strand A — feature extraction front-end ———
    ACTOR_NAME = "SRMFeatureExtractorFairy"  # Wrapped by P10_Memory/SRMFeatureExtractorFairy/fairy.py
    ACTOR_VERSION = "0.2.0"  # capability evolution (feature extraction embedded)
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory"

    ORGAN_LEVEL = False
    PURPOSE = (
        "Anchor Organ Template; verify evolution + dual-path SRM. "
        "Embed a lightweight, scanner-parity media feature extractor so memory can shelve, recall, and route."
    )
    MANTRA = "Grow in coherence, adapt with grace. See the shape inside the signal."
    LORE = (
        "Triple Helix Strand A — a feature librarian who fingerprints patterns instead of devouring them, "
        "so memory can index, route, and retrieve with ease."
    )

    # ── character sheet / directive ring ─────────────────────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Sense",
        "depth_scaling": "1..3",
        "traits": [
            "SRM_Feature_Extractor",
            "Media_Fingerprint",
            "Helix_Strand_A",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "SRM_Feature_Extractor",
        "domains": [
            "Memory",
            "SRM",
            "Media",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Media_Ingest",
            "Feature_Extraction",
            "Snapshot_Seeding",
            "Recall_Hints",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "Media_Record",
            "Feature_Vector",
            "SRM_Snapshot",
        ],
        "field": [
            "TripleHelix_Memory",
            "Media_Topology",
            "Access_Hints",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Preserve_Signal_Shape",
            "No_Fabricated_Features",
        ],
        "growth": [
            "Refine_Strategies",
            "Improve_Recall_Support",
        ],
        "precision": [
            "Minimal_Loss",
            "Deterministic_Feature_Maps",
        ],
    }

    SUBSYSTEM_STATUS = {
        "feature_engine": {
            "state": "active",
            "notes": "Scanner-parity media feature extractor with modality-aware strategies.",
            "tests": [],
        },
        "srm_snapshot": {
            "state": "active",
            "notes": "Writes and recalls snapshots via dual-path SRM intake.",
            "tests": [],
        },
        "evolution_probe": {
            "state": "active",
            "notes": "Evolution smoke + echo to SRM for Triple Helix telemetry.",
            "tests": [],
        },
    }

    SHADOW_CLASS = SRMFeatureShadowFairy
    AUTO_INJECT_IMPORTS = True  # QoL: std imports as attrs if your template supports this

    # ────────────────────────── internal: lightweight feature engine ────────────
    class _FeatureEngine:
        """
        Scanner-parity, lightweight feature extractor with optional deps.
        Keeps all I/O side-effects (telemetry/diary) inside TemplateSeedFairy.
        """
        def __init__(self, fairy):
            import time as _t
            import uuid as _uuid
            self._fairy = fairy
            self._strategies = {}
            self._boot_id = _uuid.uuid4().hex[:8]
            self._seq = 0
            self._codex_version = "unknown"
            self._register_default_strategies()
            # attempt codex load (optional)
            try:
                import json, os, pathlib
                candidates = [
                    "./akashic_codex.json",
                    "./config/akashic_codex.json",
                    "/etc/akashic/akashic_codex.json",
                    str(pathlib.Path(getattr(__file__, "__file__", __file__)).parent / "akashic_codex.json"),
                ]
                for p in candidates:
                    if os.path.isfile(p):
                        with open(p, "r", encoding="utf-8") as f:
                            doc = json.load(f)
                        self._codex_version = str(doc.get("version") or "unknown")
                        break
            except Exception:
                self._codex_version = "unknown"

            # on first boot, emit a tiny blueprint trace (lane-safe)
            try:
                self._emit_postal("BLUEPRINT_REPORT", {
                    "actor": self._fairy.ACTOR_NAME,
                    "organ": "media_feature_extractor_fairy",
                    "version": "2.2.0",
                    "plane": "P10",
                    "archetype": "digital_organ",
                    "purpose": "Extract lightweight, SRM-relevant media features for recall/routing.",
                    "mantra": "See the shape inside the signal.",
                })
                self._emit_postal("BLUEPRINT_HASH", {"path": "<embedded-in-TemplateSeedFairy>", "sha256": "<in-memory>"})
                self._emit_postal("HEALTH_REPORT", {"tests": [{"name": "integrity", "status": "ok"}], "state": "serene"})
                self._emit_postal("POSTAL_READY", {"contract": "1.0"})
                self._emit_postal("CHEM_SIGNAL_UPDATE", {"neurochemical": "serotonin", "delta": +1, "reason": "boot_ok"})
                # optional "hint" (NOT an ACK; keeps wiring pure)
                self._emit_postal("SCANNER_PARITY_HINT", {
                    "from": fairy.ACTOR_NAME, "upgrade_card": "SCANNER_PARITY_V1", "mode": "embedded", "codex_version": self._codex_version
                })
            except Exception:
                pass

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

        def _diary_write(self, kind: str, payload: dict) -> None:
            try:
                import json, pathlib, datetime as _dt
                organ = "media_feature_extractor_fairy"
                day = _dt.datetime.utcnow().strftime("%Y-%m-%d")
                d = pathlib.Path(self._fairy.__dict__.get("records_root", "./akashic_records")) / "diaries" / organ
                d.mkdir(parents=True, exist_ok=True)
                out = d / f"{day}.jsonl"
                self._seq += 1
                line = {
                    "ts": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "kind": kind,
                    "organ": organ,
                    "boot_id": self._boot_id,
                    "codex_version": self._codex_version,
                    "organ_version": "2.2.0",
                    "plane": "P10",
                    "channel": "memory",
                    "seq": self._seq,
                    "payload": payload,
                }
                with open(out, "a", encoding="utf-8") as f:
                    f.write(json.dumps(line, ensure_ascii=False) + "\n")
            except Exception:
                pass

        def _emit_postal(self, opcode: str, payload: dict) -> None:
            # best-effort emit on existing lanes; never throws
            try:
                self._fairy.post.to_TELEMETRY({"opcode": opcode, "payload": payload})
            except Exception:
                try:
                    # fall back to TRACER; still lane-safe
                    self._fairy.post.to_TRACER({"opcode": opcode, "payload": payload})
                except Exception:
                    pass

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
                            px = [
                                im.getpixel((0, 0)),
                                im.getpixel((w - 1, 0)),
                                im.getpixel((0, h - 1)),
                                im.getpixel((w - 1, h - 1)),
                            ]
                            def _rgbhex(p):
                                if isinstance(p, tuple):
                                    p = p[:3]
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
                    self._diary_write("feature.extract", {"media_type": mt, "keys": sorted(list(feats.keys()))})
                    self._emit_postal("CHEM_SIGNAL_UPDATE", {"neurochemical": "dopamine", "delta": +1.0})
                except Exception:
                    pass
                return feats
            except Exception as e:
                import traceback
                err = {"error": str(e), "trace": traceback.format_exc(limit=2), "record_keys": list(record.keys())}
                try:
                    self._diary_write("feature.error", err)
                    self._emit_postal("ORACLE_SUGGEST", {"kind": "FEATURE_EXTRACT_ERROR", "details": err})
                    self._emit_postal("CHEM_SIGNAL_UPDATE", {"neurochemical": "cortisol", "delta": +1.0})
                except Exception:
                    pass
                return {"modality": record.get("media_type", "unknown"), "error": "extract_failed"}

    # ───────────────────────── boot: pings + engine init + character sheet ────
    def on_boot(self):
        import time as _t, uuid as _uuid
        # MINIMAL BOOT - call template then return immediately
        try:
            super().on_boot()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] super().on_boot() error: {e}")
        self._feature_engine = None  # Defer engine init
        print(f"[{self.ACTOR_NAME}] FAIRY on_boot: minimal boot complete", flush=True)

    def intent_evolution_smoke(self, payload: dict):
        """Drive one evolution tick and persist snapshot via dual-path SRM."""
        tag = (payload or {}).get("tag", "default")
        sh = getattr(self, "shadow", None) or SRMFeatureShadowFairy(self)
        sim = sh._evolution_sim_tick(kind="light", n=1)
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
        import json as _json
        kind = (payload or {}).get("kind", "memory.snapshot")
        day = time.strftime("%Y-%m-%d", time.gmtime())
        base = os.path.join(_SRMDIR, day)
        latest = None
        try:
            candidates = sorted([p for p in glob.glob(os.path.join(base, f"{kind}-*.json"))], key=os.path.getmtime)
            if candidates:
                latest = candidates[-1]
                with open(latest, "r", encoding="utf-8") as f:
                    doc = _json.load(f)
            else:
                doc = {"error": "no snapshots today"}
        except Exception as e:
            doc = {"error": str(e)}
        return {"path": latest, "doc": doc}

    # ── NEW additive intents: full extractor functionality (no wiring changes) ─
    def intent_feature_extract(self, payload: dict) -> dict:
        """
        Extract lightweight, SRM-relevant features from a media record.
        payload: {"record": {...}} — same API as MediaFeatureExtractor.extract(record).
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
        eng = getattr(self, "_feature_engine", None)
        probe = {
            "upgrade_card_id": "SCANNER_PARITY_V1",
            "contract_version": "1.0",
            "role": "template-seed with embedded feature extractor",
            "mantra": self.MANTRA,
            "purpose": self.PURPOSE,
            "codex_version": getattr(eng, "_codex_version", "unknown"),
            "ts": time.time(),
        }
        try:
            self.post.to_TELEMETRY({"opcode": "SCANNER_PARITY_PROBE", "payload": probe})
        except Exception:
            pass
        return {"ok": True, "probe": probe}

# Backwards-compat alias: old class name
# NOTE: Commented out to prevent double-boot (the fairy scanner sees both as separate classes)
# If you need the alias, import it directly: from ... import SRMFeatureExtractorFairy as SRMFeatureFairy
# SRMFeatureFairy = SRMFeatureExtractorFairy
