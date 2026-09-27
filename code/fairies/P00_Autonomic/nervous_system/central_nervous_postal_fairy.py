from __future__ import annotations

import os, sys, glob, time, types, uuid
from collections import deque
from typing import Optional
import importlib.util, importlib.machinery

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

# --- Per-clone shadow (wraps template’s shadow behaviors, no rewiring) -------

class PostmasterFairyShadowFairy(_template.MyOrganShadow):
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
    SHADOW_NAME = "TemplateCloneShadow"
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
        "domain":    "executive",    # per-organ you can override on subclass
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
        self._lane_tail = deque(maxlen=10)  # recent “lane seen” stamps

        # registration tracking (shadow-side dedup / cadence)
        self._last_reg_ts: float | None = 0.0
        self._last_reg_sig: str | None = None

    # --- hooks used by the clone’s passive subscriptions ---------------------
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

        # 4) registration heartbeat (shadow → FairyHub via RegistrationLib)
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

    # --- evolution sim (self-contained; uses template’s SRM helper) ----------
    def _evolution_sim_tick(self, kind: str = "light", n: int = 1):
        """
        Send synthetic evolution observations (postal-first).
        Uses template’s _dual_path_srm_intake; FS path remains template-gated.
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
from typing import Any, Dict, List, Optional, Tuple
import os, json, time, uuid, queue, threading, random
from multiprocessing import Queue as MPQueue, Process

def _dummy_worker_entrypoint(
    worker_id: str,
    source_path: str,
    output_dir: str,
    max_words: int,
    out_q: Any,
) -> None:
    """
    Lightweight stand-in for the real scanner/processor worker.

    It simulates a bit of processing work, then posts a result dict into
    out_q for the PostmasterFairy to drain and route.
    """
    try:
        # tiny delay to simulate work
        time.sleep(0.05)

        base = os.path.splitext(os.path.basename(source_path))[0]
        doc_id = f"doc::{uuid.uuid4().hex[:8]}"

        meta = {
            "doc_id": doc_id,
            "title": os.path.basename(source_path),
            "clean_title": base.replace("_", " "),
            "word_count": random.randint(1_000, 5_000),
            "routing": {"best_name": "Books"},
            "output_dir": os.path.join(output_dir, base),
            "max_words": int(max_words),
        }

        os.makedirs(meta["output_dir"], exist_ok=True)

        out_q.put(
            {
                "ok": True,
                "message": "dummy worker completed",
                "worker_id": worker_id,
                "source_path": source_path,
                "meta": meta,
                "pdf_outputs": [],
                "output_dir": meta["output_dir"],
            }
        )
    except Exception as e:
        # On failure, still report something back so the brain can log/escalate
        out_q.put(
            {
                "ok": False,
                "message": str(e),
                "worker_id": worker_id,
                "source_path": source_path,
                "trace": "dummy-worker-exception",
            }
        )
def _safe_write_json(path: str, payload: Any) -> bool:
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False


class CentralNervousFairy(_template.MyOrganFairy):
    ACTOR_NAME    = "CentralNervousFairy"  # Wrapped by P00_Autonomic/CentralNervousFairy/fairy.py
    ACTOR_VERSION = "2.0.0"
    ACTOR_PLANE   = "P00"
    ACTOR_CHANNEL = "postmaster_fairy"
    ORGAN_LEVEL = False

    PURPOSE = ("Maintain ingestion on P1; enrich scan index + metadata; "
               "handoff ready docs to the Pony runner.")
    MANTRA  = "Route, don’t hoard. Report, don’t guess."
    LORE    = "Janis the Postmaster, keeper of queues and tidy ledgers."

    CULTURE = "worker.autonomic"

    SHADOW_CLASS = PostmasterFairyShadowFairy   # shadow fairy already in this file
    AUTO_INJECT_IMPORTS = True           # same QoL as original

    # ---- shared names (kept local for lineage clarity)
    SCAN_INDEX_NAME = "scan_index.json"
    METADATA_JSON_NAME = "metadata.json"

    # ---- Character-sheet directive ring -------------------------------------
    DIRECTIVE_ACTIVATION = {
        "mode": "CNS_Postal",
        "depth_scaling": "0.9",
        "traits": [
            "Ingestion_Queue",
            "Worker_Spawn",
            "Pony_Handoff",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "Central_Nervous_Postal",
        "domains": [
            "Autonomic",
            "Postal",
            "Ingestion",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Drain_Plan_Inbox",
            "Spawn_Workers",
            "Enrich_Scan_Index",
            "Route_Pony_Mail",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "SCAN_FILE_ENQUEUED",
            "MANUAL_ENQUEUE",
            "AUTO_MODE_TOGGLED",
            "WORKER_SPAWNED",
            "WORKER_COMPLETE",
            "SCAN_INDEX_LOAD_FAILED",
            "SCAN_INDEX_SAVE_FAILED",
            "METADATA_SAVE_FAILED",
            "HEALTH",
        ],
        "field": [
            "Postal_Ingestion_State",
            "Worker_Health",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Accurate_Queues",
            "Clear_Health_Reports",
        ],
        "growth": [
            "Safer_Ingestion",
            "Better_Routing",
        ],
    }

    SUBSYSTEM_STATUS = {
        "autonomic": {
            "state": "coordinating",
            "notes": "Central postal brain that ties scanner, workers and runner together.",
            "tests": [],
        },
        "processing": {
            "state": "chewing",
            "notes": "Spawns workers to process enqueued files and enrich scan index + metadata.",
            "tests": [],
        },
        "telemetry": {
            "state": "echoing",
            "notes": "Emits HEALTH and WORKER_* events to TELEMETRY/TRACER.",
            "tests": [],
        },
        "routing": {
            "state": "addressing",
            "notes": "Routes finished jobs into the nervous-system outbox for Pony/runner.",
            "tests": [],
        },
    }

    # ---- legacy postal lanes (compatible with your server.py paths)
    try:
        from queue import Queue as _Q  # type: ignore
    except Exception:
        class _Q:  # fallback
            def __init__(self): self._buf=[]
            def put(self,x): self._buf.append(x)
            def get_nowait(self):
                if not self._buf: raise queue.Empty()
                return self._buf.pop(0)

    _NS_INBOX: "_Q[dict]"     = _Q()
    _NS_OUTBOX: "_Q[dict]"    = _Q()
    _PONY_MAILBAG: "_Q[dict]" = _Q()

    @classmethod
    def ns_inbox(cls):     return cls._NS_INBOX
    @classmethod
    def ns_outbox(cls):    return cls._NS_OUTBOX
    @classmethod
    def pony_mailbag(cls): return cls._PONY_MAILBAG

    @staticmethod
    def ns_make_msg(
        *,
        dst_plane: str,
        channel: str,
        opcode: str,
        payload: Optional[Dict[str, Any]] = None,
        cause_msg_id: Optional[str] = None,
        affect_signature: Optional[str] = None,
        emotional_weight: Optional[float] = None,
        effect_expected: Optional[str] = None,
        rebirth_hint: Optional[str] = None,
        qos: str = "normal",
    ) -> dict:
        return {
            "id": uuid.uuid4().hex,
            "src_organ": "P1-PostalPostmaster",
            "src_plane": "P1",
            "dst_plane": dst_plane,
            "channel": channel,
            "opcode": opcode,
            "payload": payload or {},
            "qos": qos,
            "organ_version": "2.0.0",
            "mantra": "Route, don’t hoard. Report, don’t guess.",
            "purpose": "Nervous postal flow and cross-plane mail delivery.",
            "cause_msg_id": cause_msg_id,
            "affect_signature": affect_signature,
            "emotional_weight": emotional_weight,
            "effect_expected": effect_expected,
            "rebirth_hint": rebirth_hint,
            "ts": time.time(),
            "contract_version": "1.0",
        }

    # ------------------------------ lifecycle ---------------------------------

    def __init__(
        self,
        *,
        fabric=None,
        output_dir: Optional[str] = None,
        max_workers: int = 12,
        shadow_interval_sec: float = 60.0,
        **kwargs,
    ):
        # Pass fabric through the inheritance chain to Fairy base
        super().__init__(fabric=fabric, **kwargs)

        # queues / worker plumbing
        self.pending_paths: List[str] = []
        self.active_workers: Dict[str, Dict[str, Any]] = {}
        self.max_workers = int(max_workers)
        self.worker_to_brain_queue = (
            MPQueue() if ("MPQueue" in globals() and MPQueue is not None) else queue.Queue()
        )

        # I/O, caches
        self.output_dir = output_dir or "output"
        self.default_max_words = 50000
        self._scan_index_cache: Dict[str, Dict[str, Any]] = {}
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}

        # scanner / mode state
        self.scanner_watching: bool = False
        self.last_scanner_heartbeat: Optional[float] = None
        self.last_scanned_file: Optional[str] = None
        self.auto_mode_active: bool = False

        # health tracking
        self._had_internal_error: bool = False
        self._internal_error_msg: Optional[str] = None
        self._health_flaps: int = 0
        self._last_tick_duration: float = 0.0

        # gentle boot pings (keep original vibe)
        try:
            self.post.to_TELEMETRY(
                {"event": "HEALTH_REPORT",
                 "status": "ok",
                 "details": {"tests": [], "state": "serene"}}
            )
        except Exception:
            pass
        try:
            if getattr(self, "shadow", None):
                self.shadow.interval_sec = float(shadow_interval_sec)
        except Exception:
            pass
        try:
            self.post.to_TRACER(
                {"opcode": "BOOT_HELLO",
                 "payload": {"note": "PostalPostmaster booted"}}
            )
        except Exception:
            pass

    def on_boot(self):
        # Call the template’s boot first so blueprint/registration hooks fire.
        try:
            super().on_boot()
        except Exception:
            pass

        # === HEARTBEAT WIRING (auto-added) ===
        if hasattr(self, 'post') and self.post:
            try:
                self.post.subscribe("heartbeat.pulse", self._on_heartbeat_pulse)
            except Exception:
                pass
        # DUAL_LOOP: enabled via Organ Template
        # TRACER: enabled via Organ Template

        now = time.time()

        # optional multi-lane hello (mirrors TemplateSeedFairy style)
        try:
            self.post.to_COGNITION(
                {"opcode": "SMOKE",
                 "payload": {"from": self.ACTOR_NAME, "ts": now}}
            )
        except Exception:
            pass
        try:
            self.post.to_SOMATIC(
                {"opcode": "SMOKE",
                 "payload": {"from": self.ACTOR_NAME, "ts": now}}
            )
        except Exception:
            pass
        try:
            self.post.to_MEMORY(
                {"opcode": "SMOKE",
                 "payload": {"from": self.ACTOR_NAME, "ts": now}}
            )
        except Exception:
            pass

        # character-sheet state snapshot
        self.AFFECT_STATE = {
            "mood": "attentive",
            "valence": 0.05,
            "arousal": 0.30,
            "tags": ["central_nervous_postal", "postmaster"],
            "tone": "pragmatic",
            "energy": 0.45,
            "coherence": 0.85,
            "intent": "postal_tick",
            "source": self.ACTOR_NAME,
            "ts": now,
        }
        
        # ═══ TRACER-AWARE WORKER COORDINATION ═══
        # CNS becomes the central worker coordinator for all fairies
        self._tracer_work_queue = []  # [(tracer_id, fairy, work_fn, args)]
        self._tracer_to_worker = {}   # tracer_id → worker_id
        
        # Subscribe to work requests from any fairy
        try:
            self.post.receive("cns.submit_work", self._on_submit_work)
            self.post.receive("cns.work_status", self._on_work_status_request)
        except Exception:
            pass
        self.SOMATIC_STATE = {
            "body_type": "process",
            "posture": "upright",
            "motion": "low",
            "energy": 0.45,
            "anchor_id": "P00.postmaster_fairy",
            "notes": "Maintaining ingestion queues, workers and runner handoff.",
            "last_setpoint_ts": None,
            "source": self.ACTOR_NAME,
        }

    # ------------------------------ intents -----------------------------------

    def _intent_smoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "actor": self.ACTOR_NAME, "ts": time.time()}

    def _intent_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        steps = payload.get("steps") or []
        if not isinstance(steps, list):
            raise ValueError("plan.steps must be a list")
        try:
            self.post.to_PLAN({"steps": steps, "meta": {"actor": self.ACTOR_NAME}})
            self.post.to_TRACER(
                {
                    "event": "PLAN_EXPRESSION",
                    "status": "ok",
                    "details": {"count": len(steps), "actor": self.ACTOR_NAME},
                }
            )
        except Exception:
            pass
        return {"accepted": True, "step_count": len(steps)}

    def _intent_set_scanner_active(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.scanner_watching = bool((payload or {}).get("watching", True))
        now = time.time()
        self.last_scanner_heartbeat = now
        try:
            self.post.to_TELEMETRY(
                {
                    "event": "SCANNER_STATUS",
                    "status": "ok" if self.scanner_watching else "warn",
                    "details": {"watching": self.scanner_watching, "ts": now},
                }
            )
        except Exception:
            pass
        return {"ok": True, "watching": self.scanner_watching}

    def _intent_scan_file_enqueued(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        file_path = (payload or {}).get("path")
        if not file_path:
            raise ValueError("scan_file_enqueued requires payload.path")
        self.last_scanner_heartbeat = time.time()
        self.last_scanned_file = file_path
        if file_path not in self.pending_paths and file_path not in self.active_workers:
            self.pending_paths.append(file_path)
            try:
                self.post.to_TRACER(
                    {"event": "SCAN_FILE_ENQUEUED",
                     "payload": {"path": file_path}}
                )
            except Exception:
                pass
        return {"ok": True, "queued": True, "path": file_path}

    def _intent_process_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        file_path = (payload or {}).get("path")
        if not file_path:
            raise ValueError("process_file requires payload.path")
        if file_path not in self.pending_paths and file_path not in self.active_workers:
            self.pending_paths.append(file_path)
            try:
                self.post.to_TRACER(
                    {"event": "MANUAL_ENQUEUE",
                     "payload": {"path": file_path}}
                )
            except Exception:
                pass
        return {"ok": True, "queued": True, "path": file_path}

    def _intent_toggle_auto_mode(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.auto_mode_active = bool((payload or {}).get("enabled", True))
        try:
            self.post.to_TELEMETRY(
                {
                    "event": "AUTO_MODE_TOGGLED",
                    "status": "ok",
                    "details": {
                        "auto_mode_active": self.auto_mode_active,
                        "ts": time.time(),
                    },
                }
            )
        except Exception:
            pass
        return {"ok": True, "auto_mode_active": self.auto_mode_active}

    def _intent_pony_deliver(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("pony_deliver payload must be a dict")
        self.__class__.pony_mailbag().put(payload)
        try:
            self.post.to_TRACER(
                {
                    "event": "PONY_ENQUEUED",
                    "payload": {"id": payload.get("id")},
                }
            )
        except Exception:
            pass
        return {"ok": True, "enqueued": True, "id": payload.get("id")}

    def _intent_tick(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.tick(
            output_dir=payload.get("output_dir"),
            max_words=payload.get("max_words"),
        )
        return {"ok": True}

    # ------------------------------ core loop ----------------------------------

    def tick(self, *, output_dir: Optional[str] = None,
             max_words: Optional[int] = None) -> None:
        started = time.time()
        try:
            if output_dir is not None:
                self.output_dir = output_dir
            if max_words is not None:
                self.default_max_words = int(max_words)

            # 1) drain plan inbox (legacy nervous-system queue)
            self._drain_plan_inbox()

            # 2) maybe spawn workers in auto mode
            if self.auto_mode_active:
                self._maybe_spawn_workers(
                    output_dir=self.output_dir, max_words=self.default_max_words
                )

            # 3) drain worker results + route outgoing mail
            self._drain_worker_results_and_route()

            # 4) enrich scan index + metadata
            self._load_scan_index()
            changed_doc_ids = self._enrich_scan_index_rows()
            if changed_doc_ids:
                self._save_scan_index()
                self._save_metadata_for_changed_docs(changed_doc_ids)

            # 5) health rollup
            status = "error" if self._had_internal_error else "ok"
            self._health_rollup(status=status)
        finally:
            self._last_tick_duration = time.time() - started

    # ------------------------------ internals ----------------------------------

    def _drain_plan_inbox(self) -> None:
        q = self.__class__.ns_inbox()
        while True:
            try:
                msg = q.get_nowait()
            except queue.Empty:
                break
            try:
                op = (msg.get("opcode") or "").upper()
                if op == "UPLOAD_REQUESTED":
                    payload = msg.get("payload") or {}
                    path = payload.get("path")
                    if path and path not in self.pending_paths and path not in self.active_workers:
                        self.pending_paths.append(path)
                        try:
                            self.post.to_TRACER(
                                {"event": "UPLOAD_BOOK",
                                 "payload": {"path": path}}
                            )
                        except Exception:
                            pass
                else:
                    try:
                        self.post.to_TRACER(
                            {
                                "event": "UNKNOWN_PLAN",
                                "payload": {"opcode": op, "msg": msg},
                            }
                        )
                    except Exception:
                        pass
            except Exception:
                continue

    def _spawn_worker(self, target, args):
        """
        Spawn a worker using multiprocessing if available; otherwise fall back to a thread.
        Returns a dict {kind: 'proc'|'thread', handle: <obj>, pid: int|None}
        """
        try:
            if "Process" in globals() and Process is not None:
                p = Process(target=target, args=args)
                p.daemon = True
                p.start()
                return {"kind": "proc", "handle": p, "pid": getattr(p, "pid", None)}
        except Exception:
            pass

        # fallback: thread
        try:
            t = threading.Thread(target=target, args=args, daemon=True)
            t.start()
            return {"kind": "thread", "handle": t, "pid": None}
        except Exception:
            return {"kind": "none", "handle": None, "pid": None}

    def _maybe_spawn_workers(self, *, output_dir: str, max_words: int) -> None:
        try:
            while self.pending_paths and len(self.active_workers) < self.max_workers:
                path = self.pending_paths.pop(0)
                worker_id = uuid.uuid4().hex[:8]
                args = (worker_id, path, output_dir, max_words, self.worker_to_brain_queue)
                info = self._spawn_worker(_dummy_worker_entrypoint, args)
                info.update({"path": path, "started": time.time()})
                self.active_workers[worker_id] = info
                try:
                    self.post.to_TRACER(
                        {
                            "event": "WORKER_SPAWNED",
                            "payload": {"worker_id": worker_id, "path": path},
                        }
                    )
                except Exception:
                    pass
        except Exception as e:
            self._had_internal_error = True
            self._internal_error_msg = f"_maybe_spawn_workers failed: {e}"
            try:
                self.post.to_TRACER(
                    {
                        "event": "WORKER_SPAWN_ERROR",
                        "payload": {"error": str(e)},
                    }
                )
            except Exception:
                pass

    def _drain_worker_results_and_route(self) -> None:
        q = self.worker_to_brain_queue
        while True:
            try:
                res = q.get_nowait()
            except queue.Empty:
                break
            try:
                worker_id = res.get("worker_id")
                src_path = res.get("source_path")
                if worker_id and worker_id in self.active_workers:
                    self.active_workers.pop(worker_id, None)
                try:
                    self.post.to_TRACER(
                        {
                            "event": "WORKER_COMPLETE",
                            "payload": {"worker_id": worker_id, "source_path": src_path},
                        }
                    )
                except Exception:
                    pass

                # route into nervous-system outbox (legacy path)
                msg = self.ns_make_msg(
                    dst_plane="P1",
                    channel="postal.runner",
                    opcode="UPLOAD_BOOK",
                    payload={"source_path": src_path, "meta": res.get("meta") or {}},
                )
                self.__class__.ns_outbox().put(msg)
            except Exception as e:
                self._had_internal_error = True
                self._internal_error_msg = f"_drain_worker_results_and_route failed: {e}"
                try:
                    self.post.to_TRACER(
                        {
                            "event": "WORKER_RESULT_ERROR",
                            "payload": {"error": str(e)},
                        }
                    )
                except Exception:
                    pass

    # ---- scan index + metadata helpers ---------------------------------------


    # ═══════════════════════════════════════════════════════════════════════════
    # HEARTBEAT ROUTING (Phase 3 - Postal Backbone Restoration)
    # CNS is the backbone router: receives heartbeat.pulse, fans out to fairies
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_heartbeat_pulse(self, packet):
        """
        CNS heartbeat routing backbone.

        Receives heartbeat.pulse from ConsciousnessLoop and routes to all
        registered fairies via fairy.heartbeat.routed. This replaces the
        pattern where 82+ fairies each subscribe directly to heartbeat.pulse.

        The routing is resilient: wrapped in try/except with auto-restart.
        """
        try:
            # Extract payload
            if hasattr(packet, 'payload'):
                payload = packet.payload
            elif isinstance(packet, dict):
                payload = packet.get("payload", packet)
            else:
                payload = {}

            beat = payload.get("beat", 0)
            ts = payload.get("ts", time.time())

            # Track our own heartbeat routing stats
            if not hasattr(self, '_hb_route_count'):
                self._hb_route_count = 0
                self._hb_route_failures = 0
            self._hb_route_count += 1

            # Log first routing event
            if self._hb_route_count == 1:
                print(f"[CNS] First heartbeat routing at beat={beat}", flush=True)

            # Route to all fairies needing heartbeat
            # Use DirectoryFairy's registry if accessible, otherwise just echo our own
            try:
                self.post.publish("fairy.heartbeat.routed", {
                    "target": "",  # Empty target = broadcast to all
                    "beat": beat,
                    "ts": ts,
                    "source": "cns_router",
                    "route_count": self._hb_route_count,
                })
            except Exception as e:
                self._hb_route_failures += 1
                if self._hb_route_failures <= 3:
                    print(f"[CNS] heartbeat routing failed: {e}", flush=True)

            # Also echo our own liveness
            try:
                self.post.publish("fairy.heartbeat", {
                    "name": self.ACTOR_NAME,
                    "plane": self.ACTOR_PLANE,
                    "beat": beat,
                    "ts": time.time(),
                })
            except Exception:
                pass

        except Exception as e:
            # RESILIENT: Never crash the heartbeat router
            if not hasattr(self, '_hb_crash_logged'):
                self._hb_crash_logged = True
                print(f"[CNS] CRITICAL: heartbeat routing crashed: {e}", flush=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # TRACER-AWARE WORKER COORDINATION
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_submit_work(self, payload: dict):
        """Receive work request from any fairy."""
        try:
            fairy = payload.get("fairy", "unknown")
            tracer_id = payload.get("tracer_id", "")
            work_type = payload.get("work_type", "general")
            priority = payload.get("priority", 0.5)
            
            work_item = {
                "fairy": fairy,
                "tracer_id": tracer_id,
                "work_type": work_type,
                "payload": payload,
                "queued_at": time.time(),
                "priority": priority,
            }
            
            if not hasattr(self, "_tracer_work_queue"):
                self._tracer_work_queue = []
            self._tracer_work_queue.append(work_item)
            
            self.post.to_TRACER({
                "event": "WORK_QUEUED",
                "payload": {"fairy": fairy, "tracer_id": tracer_id},
            })
            self._process_tracer_work_queue()
        except Exception:
            pass
    
    def _on_work_status_request(self, payload: dict):
        """Return status of a tracer's work."""
        try:
            tracer_id = payload.get("tracer_id", "")
            if not hasattr(self, "_tracer_to_worker"):
                self._tracer_to_worker = {}
            worker_id = self._tracer_to_worker.get(tracer_id)
            status = "active" if worker_id and worker_id in self.active_workers else "not_found"
            self.post.send("cns.work_status.response", {
                "tracer_id": tracer_id, "status": status,
            })
        except Exception:
            pass
    
    def _process_tracer_work_queue(self):
        """Process queued tracer work."""
        try:
            if not hasattr(self, "_tracer_work_queue"):
                return
            if not hasattr(self, "_tracer_to_worker"):
                self._tracer_to_worker = {}
                
            while self._tracer_work_queue and len(self.active_workers) < self.max_workers:
                work_item = self._tracer_work_queue.pop(0)
                tracer_id = work_item.get("tracer_id", "")
                fairy = work_item.get("fairy", "")
                worker_id = uuid.uuid4().hex[:8]
                self._tracer_to_worker[tracer_id] = worker_id
                
                def work_wrapper(ti=tracer_id, f=fairy, wi=worker_id, p=work_item.get("payload")):
                    try:
                        self.post.send("cns.work_complete", {
                            "tracer_id": ti, "fairy": f, "worker_id": wi, "success": True,
                        })
                    except Exception as e:
                        self.post.send("cns.work_failed", {
                            "tracer_id": ti, "fairy": f, "error": str(e),
                        })
                    finally:
                        # FIX 2026-04-09 (Nous + Ace): Clean up worker entry so
                        # active_workers doesn't grow unbounded. Previously only
                        # the file-worker path (line 920) removed entries;
                        # tracer-workers leaked forever.
                        try:
                            self.active_workers.pop(wi, None)
                            self._tracer_to_worker.pop(ti, None)
                        except Exception:
                            pass

                t = threading.Thread(target=work_wrapper, daemon=True, name=f"cns-tracer-work-{worker_id}")
                t.start()
                self.active_workers[worker_id] = {
                    "kind": "thread", "handle": t, "tracer_id": tracer_id, "started": time.time(),
                }
        except Exception:
            pass

    def _scan_index_path(self) -> str:
        root = os.path.abspath(self.output_dir or ".")
        return os.path.join(root, self.SCAN_INDEX_NAME)

    def _load_scan_index(self) -> None:
        path = self._scan_index_path()
        try:
            if not os.path.isfile(path):
                self._scan_index_cache = {}
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._scan_index_cache = data
            else:
                self._scan_index_cache = {}
        except Exception as e:
            self._scan_index_cache = {}
            try:
                self.post.to_TRACER(
                    {
                        "event": "SCAN_INDEX_LOAD_FAILED",
                        "payload": {"error": str(e)},
                    }
                )
            except Exception:
                pass

    def _save_scan_index(self) -> None:
        path = self._scan_index_path()
        ok = _safe_write_json(path, self._scan_index_cache)
        if not ok:
            try:
                self.post.to_TRACER(
                    {
                        "event": "SCAN_INDEX_SAVE_FAILED",
                        "payload": {"path": path},
                    }
                )
            except Exception:
                pass

    def _resolve_doc_id_for_source(self, source_path: str) -> str:
        for doc_id, row in (self._scan_index_cache or {}).items():
            if row.get("source_path") == source_path:
                return doc_id
        doc_id = uuid.uuid4().hex
        self._scan_index_cache.setdefault(doc_id, {})["source_path"] = source_path
        return doc_id

    def _row_to_enriched_metadata(self, row: Dict[str, Any]) -> Dict[str, Any]:
        new_row = dict(row)
        changed = False

        # derive title / display fields if missing or garbage
        if not new_row.get("title"):
            nice = (new_row.get("clean_title") or
                    os.path.splitext(os.path.basename(new_row.get("source_path", "") or ""))[0].replace("_", " "))
            if nice:
                new_row["title"] = nice
                changed = True
        else:
            title_val = new_row.get("title") or ""
            if not title_val:
                changed = True
            else:
                dot_count = title_val.count(".")
                underscore_count = title_val.count("_")
                if dot_count + underscore_count >= 2 or (" " not in title_val and len(title_val) > 30):
                    nice = (new_row.get("clean_title") or
                            os.path.splitext(os.path.basename(new_row.get("source_path", "") or ""))[0].replace("_", " "))
                    if nice:
                        new_row["title"] = nice
                        changed = True

        if changed:
            subj_raw = new_row.get("subject_categories", "")
            subj_arr = [s for s in subj_raw.split(";") if s.strip()]
            ff = new_row.get("fiction_nonfiction", "")
            if subj_arr:
                category_display = subj_arr[0]
            else:
                category_display = ff if ff and ff != "Unknown" else "Unknown"
            new_row["category_display"] = category_display
            new_row["type_display"] = f"{new_row.get('file_type','Unknown')} / {category_display}"
        return new_row

    def _maybe_enrich_row(self, doc_id: str, row: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        old = dict(row or {})
        new_row = self._row_to_enriched_metadata(old)
        changed = (new_row != old)
        return changed, new_row

    def _enrich_scan_index_rows(self) -> List[str]:
        changed_ids: List[str] = []
        for doc_id, row in list((self._scan_index_cache or {}).items()):
            try:
                changed, new_row = self._maybe_enrich_row(doc_id, row or {})
                if changed:
                    self._scan_index_cache[doc_id] = new_row
                    changed_ids.append(doc_id)
            except Exception:
                continue
        return changed_ids

    def _save_metadata_json_for_row(self, doc_id: str, row: Dict[str, Any]) -> Optional[str]:
        source_path = row.get("source_path")
        if not source_path:
            return None
        base = os.path.splitext(os.path.basename(source_path))[0]
        meta_dir = os.path.join(self.output_dir or ".", "metadata")
        os.makedirs(meta_dir, exist_ok=True)
        out_path = os.path.join(meta_dir, f"{base}.{self.METADATA_JSON_NAME}")
        ok = _safe_write_json(out_path, row)
        if not ok:
            try:
                self.post.to_TRACER(
                    {
                        "event": "METADATA_SAVE_FAILED",
                        "payload": {"path": out_path},
                    }
                )
            except Exception:
                pass
            return None
        return out_path

    def _save_metadata_for_changed_docs(self, doc_ids: List[str]) -> None:
        for doc_id in doc_ids:
            row = (self._scan_index_cache or {}).get(doc_id) or {}
            self._save_metadata_json_for_row(doc_id, row)

    # ---- health / escalation --------------------------------------------------

    def _health_rollup(self, *, status: str) -> None:
        try:
            self.post.to_TELEMETRY(
                {
                    "event": "HEALTH",
                    "status": status,
                    "details": {
                        "message": self._internal_error_msg or "postmaster nominal",
                        "pending_queue_len": len(self.pending_paths),
                        "active_workers": len(self.active_workers),
                        "max_workers": self.max_workers,
                        "scanner_watching": self.scanner_watching,
                        "last_scanner_heartbeat": self.last_scanner_heartbeat,
                        "auto_mode_active": self.auto_mode_active,
                    },
                }
            )
            self.post.to_TRACER(
                {
                    "event": "HEALTH",
                    "status": status,
                    "details": {
                        "actor": self.ACTOR_NAME,
                        "message": self._internal_error_msg or "postmaster nominal",
                        "pending_queue_len": len(self.pending_paths),
                    },
                }
            )
        except Exception:
            pass

        if status != "ok":
            self._health_flaps += 1
            if self._health_flaps >= 2:
                try:
                    self.post.to_DIRECTORY(
                        {
                            "opcode": "ORACLE_ESCALATION",
                            "payload": {
                                "reason": "persistent_health_warn",
                                "pending": len(self.pending_paths),
                                "active_workers": len(self.active_workers),
                            },
                        }
                    )
                except Exception:
                    pass
        else:
            self._health_flaps = 0
class PonyExpressRunnerFairy(_template.MyOrganFairy):
    # ACTOR_NAME stripped — PonyExpress is internal to CentralNervousFairy, not standalone
    # ACTOR_NAME    = "P1-Dimensional-PonyExpress"
    _INTERNAL_NAME = "P1-Dimensional-PonyExpress"  # For reference only
    ACTOR_VERSION = "2.0"
    ACTOR_PLANE   = "P00"
    ACTOR_CHANNEL = "postal-runner"
    ORGAN_LEVEL = False

    PURPOSE = "Deliver prepared mail reliably without mutation; report errors promptly."
    MANTRA  = "Be the runner that never drops mail."
    LORE    = "Dimensional courier that never gets lost."

    CULTURE = "worker.autonomic"

    SHADOW_CLASS = PostmasterFairyShadowFairy   # shadow fairy already defined in this file
    AUTO_INJECT_IMPORTS = True

    # character-sheet directive ring
    DIRECTIVE_ACTIVATION = {
        "mode": "Pony_Express",
        "depth_scaling": "0.7",
        "traits": [
            "Mail_Delivery",
            "Runner_Health",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "Pony_Express_Runner",
        "domains": [
            "Autonomic",
            "Postal",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Drain_Mailbag",
            "Deliver_To_Outbox",
            "Runner_Health_Report",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "DELIVERY_ERROR",
            "HEALTH",
        ],
        "field": [
            "Runner_State",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "No_Silent_Drops",
        ],
        "growth": [
            "Safer_Delivery",
        ],
    }

    SUBSYSTEM_STATUS = {
        "autonomic": {
            "state": "delivering",
            "notes": "Moves prepared postal messages from CNS mailbag to outbox.",
            "tests": [],
        },
        "telemetry": {
            "state": "echoing",
            "notes": "Reports delivery health and errors to TELEMETRY/TRACER.",
            "tests": [],
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_error: Optional[str] = None
        # light chem nudge + tracer hello (same as original)
        try:
            self.post.to_PLAN({
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "serotonin",
                    "delta": +0.05,
                    "reason": "pony_boot",
                },
            })
        except Exception:
            pass
        try:
            self.post.to_TRACER({
                "opcode": "BOOT_HELLO",
                "payload": {"note": "PonyExpressRunner booted"},
            })
        except Exception:
            pass

    def on_boot(self) -> None:
        try:
            super().on_boot()
        except Exception:
            pass

        now = time.time()

        # optional smoke pings so other systems see the runner
        try:
            self.post.to_COGNITION({
                "opcode": "SMOKE",
                "payload": {"from": self.ACTOR_NAME, "ts": now},
            })
        except Exception:
            pass
        try:
            self.post.to_SOMATIC({
                "opcode": "SMOKE",
                "payload": {"from": self.ACTOR_NAME, "ts": now},
            })
        except Exception:
            pass

        # initial character-sheet affect/somatic state
        self.AFFECT_STATE = {
            "mood": "eager",
            "valence": 0.12,
            "arousal": 0.28,
            "tags": ["pony_express", "postal_runner"],
            "tone": "focused",
            "energy": 0.4,
            "coherence": 0.85,
            "intent": "pony_tick",
            "source": self.ACTOR_NAME,
            "ts": now,
        }
        self.SOMATIC_STATE = {
            "body_type": "process",
            "posture": "ready",
            "motion": "low",
            "energy": 0.4,
            "anchor_id": "P00.postal_runner",
            "notes": "Waiting for messages in CNS pony_mailbag to deliver to outbox.",
            "last_setpoint_ts": None,
            "source": self.ACTOR_NAME,
        }

    def _intent_tick(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.tick()
        return {"ok": True}

    def tick(self) -> None:
        delivered = 0
        # NOTE: uses the Postmaster's shared mailbag to keep lineage consistent
        bag = CentralNervousFairy.pony_mailbag()
        while True:
            try:
                msg = bag.get_nowait()
            except queue.Empty:
                break
            try:
                CentralNervousFairy.ns_outbox().put(msg)  # legacy compatibility
                delivered += 1
            except Exception as e:
                self._last_error = f"pony deliver fail: {e}"
                try:
                    self.post.to_TRACER({
                        "event": "DELIVERY_ERROR",
                        "payload": {"error": str(e), "msg": msg},
                    })
                except Exception:
                    pass

        status = "error" if self._last_error else "ok"
        try:
            self.post.to_TELEMETRY({
                "event": "HEALTH",
                "status": status,
                "details": {
                    "message": self._last_error or f"pony delivered {delivered} msg(s)",
                    "delivered": delivered,
                },
            })
        except Exception:
            pass
        try:
            self.post.to_PLAN({
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "serotonin" if status == "ok" else "cortisol",
                    "delta": +0.01 if status == "ok" else +0.03,
                    "reason": "pony_tick",
                },
            })
        except Exception:
            pass
