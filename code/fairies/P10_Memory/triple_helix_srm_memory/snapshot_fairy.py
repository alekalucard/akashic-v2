from __future__ import annotations

import os, sys, glob, time, types, uuid, hashlib, zipfile, json, threading
from collections import deque
from typing import Optional, Any
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

# Mirror template SRM dir so our dual-path SRM helper at the bottom has a root.
_SRMDIR = getattr(_template, "_SRMDIR", None)
if _SRMDIR is None:
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

class ProjectSnapshotShadowFairy(_template.MyOrganShadow):
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
    SHADOW_NAME = "ProjectSnapshotShadowFairy"
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
        "domain":    "Memory",    # per-organ you can override on subclass
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


class SRMProjectSnapshotFairy(_template.MyOrganFairy):
    ACTOR_NAME    = "SRMProjectSnapshotFairy"  # Wrapped by P10_Memory/SRMProjectSnapshotFairy/fairy.py
    ACTOR_VERSION = "1.1.0"  # character sheet + status emit
    ACTOR_PLANE   = "P10"
    ACTOR_CHANNEL = "project_scanner"
    ORGAN_LEVEL = False
    PURPOSE = "Perceive ZIP project archives so other fairies can learn from prior work."
    MANTRA  = "See all. Judge nothing. Name what arrives, then vanish."
    LORE    = (
        "Triple Helix Strand D — the crate-watcher. In the Library between Moments, a small silver sprite "
        "watches the crates of old work. She names what arrives, measures their stars, and leaves a ribbon for the archivists."
    )

    # ── character sheet / directive ring ─────────────────────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Observe",
        "depth_scaling": "1..2",
        "traits": [
            "SRM_Project_Snapshot",
            "Project_Zip_Scanner",
            "Helix_Strand_D",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "SRM_Project_Snapshot",
        "domains": [
            "Memory",
            "SRM",
            "Project_Topology",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Archive_Watching",
            "Snapshot_Metadata",
            "SRM_Intake_Seeding",
            "Topology_Hints",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "Project_Zip",
            "Snapshot_Metadata",
            "SRM_Intake_Record",
        ],
        "field": [
            "TripleHelix_Memory",
            "Project_Index",
            "Plane_Topology",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Report_What_Is_There",
            "No_Fabricated_Zips",
        ],
        "growth": [
            "Refine_Heuristics",
            "Improve_Discovery_Coverage",
        ],
        "precision": [
            "Deterministic_Scanning",
            "Minimal_Noise_In_Events",
        ],
    }

    SUBSYSTEM_STATUS = {
        "scanner_loop": {
            "state": "active",
            "notes": "Background thread (or one-shot) scanning project roots for ZIP archives.",
            "tests": [],
        },
        "zip_peek": {
            "state": "active",
            "notes": "Non-destructive peek at ZIPs to derive lineage-friendly metadata.",
            "tests": [],
        },
        "srm_intake": {
            "state": "active",
            "notes": "Writes project.zip.detected records via dual-path SRM intake.",
            "tests": [],
        },
    }

    SHADOW_CLASS = ProjectSnapshotShadowFairy
    AUTO_INJECT_IMPORTS = True  # std imports via template if available

    # Tunables
    SUPPORTED_ARCHIVES = (".zip",)     # easily extendable later
    POLL_SEC = 2.5                     # fallback watcher cadence
    HEAD_LIMIT = 500                   # limit entries inspected per zip

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # runtime state
        self._roots: list[str] = []
        self._stop_flag = None         # threading.Event
        self._scan_thread = None       # threading.Thread
        self._seen_mtimes: dict[str, float] = {}  # path -> last mtime

    # ───────────────────────── lifecycle ─────────────────────────
    def on_boot(self):
        # ═══════════════════════════════════════════════════════════════════════════
        # MINIMAL BOOT - postal calls moved out to prevent blocking
        # ═══════════════════════════════════════════════════════════════════════════
        try:
            super().on_boot()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] super().on_boot() error: {e}")

        # All postal calls deferred - they were causing boot hangs
        print(f"[{self.ACTOR_NAME}] FAIRY on_boot: minimal boot complete", flush=True)

    def intent_set_roots(self, payload: dict):
        """
        Set scan roots. payload: {roots: [paths...] }
        """
        roots = [os.path.abspath(p) for p in (payload or {}).get("roots", []) if isinstance(p, str)]
        self._roots = roots
        self._emit_ok("SET_ROOTS", {"roots": roots})
        return {"ok": True, "roots": roots}

    def intent_start_scanner(self, payload: dict):
        """
        Start background polling. payload: {roots?: [...], poll_sec?: float}
        """
        roots = (payload or {}).get("roots")
        if roots:
            self.intent_set_roots({"roots": roots})
        poll = float((payload or {}).get("poll_sec", self.POLL_SEC))

        if self._scan_thread and self._scan_thread.is_alive():
            return {"ok": True, "status": "already_running", "roots": self._roots, "poll_sec": poll}

        self._stop_flag = threading.Event()
        self._scan_thread = threading.Thread(target=self._poll_loop, args=(poll,), daemon=True)
        self._scan_thread.start()
        self._emit_ok("SCANNER_STARTED", {"roots": self._roots, "poll_sec": poll})
        self._chem_nudge("serotonin", +0.5, reason="scanner_start")
        return {"ok": True, "roots": self._roots, "poll_sec": poll}

    def intent_stop_scanner(self, payload: dict):
        """
        Stop background polling.
        """
        if self._stop_flag:
            self._stop_flag.set()
        self._emit_ok("SCANNER_STOPPED", {"roots": self._roots})
        self._chem_nudge("serotonin", +0.2, reason="scanner_stop")
        return {"ok": True}

    def intent_status(self, payload: dict):
        """
        Report scanner status.
        """
        running = bool(self._scan_thread and self._scan_thread.is_alive())
        return {"ok": True, "running": running, "roots": list(self._roots), "seen": len(self._seen_mtimes)}

    def intent_scan_once(self, payload: dict):
        """
        Immediate one-shot scan (no thread). payload: {roots?: [...]} (defaults to current roots)
        """
        roots = [os.path.abspath(p) for p in (payload or {}).get("roots", self._roots)]
        count = 0
        for r in roots:
            count += self._scan_root_once(r)
        return {"ok": True, "scans": count}

    # ───────────────────────── core loop ─────────────────────────
    def _poll_loop(self, poll_sec: float):
        try:
            while self._stop_flag and not self._stop_flag.is_set():
                total = 0
                for root in list(self._roots):
                    try:
                        total += self._scan_root_once(root)
                    except Exception as e:
                        self._emit_warn("SCAN_ERROR", {"root": root, "error": str(e)})
                        self._chem_nudge("cortisol", +0.8, reason="scan_error")
                # quiet pulse
                try:
                    self.post.to_TELEMETRY({"opcode": "SCANNER_PULSE",
                                            "payload": {"roots": self._roots, "total_scans": total, "ts": time.time()}})
                except Exception:
                    pass
                time.sleep(max(0.5, float(poll_sec)))
        except Exception as e:
            self._emit_error("POLL_LOOP_FATAL", {"error": str(e)})

    # ───────────────────────── root scan ─────────────────────────
    def _scan_root_once(self, root: str) -> int:
        if not os.path.isdir(root):
            self._emit_warn("ROOT_MISSING", {"root": root})
            return 0
        scans = 0
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                low = fn.lower()
                if not any(low.endswith(ext) for ext in self.SUPPORTED_ARCHIVES):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    st = os.stat(path)
                except FileNotFoundError:
                    continue
                mt = st.st_mtime
                prev = self._seen_mtimes.get(path)
                if prev is not None and mt <= prev:
                    continue  # unchanged
                self._seen_mtimes[path] = mt
                scans += 1
                meta = self._peek_zip_project(path, head_limit=self.HEAD_LIMIT)

                # diary/tracer/plan echoes
                try:
                    self.post.to_TRACER({"opcode": "PROJECT_ZIP_DETECTED", "payload": meta})
                except Exception:
                    pass
                try:
                    self.post.route("PLAN", {"opcode": "PROJECT_ZIP_DETECTED", "payload": meta})
                except Exception:
                    pass

                # dual-path SRM (disk + MEMORY)
                try:
                    _dual_path_srm_intake(self.post, kind="project.zip.detected", data=meta)
                except Exception:
                    pass
                try:
                    self.post.to_MEMORY({"kind": "project.zip.detected", "payload": meta})
                except Exception:
                    pass

                # nice dopamine bump
                self._chem_nudge("dopamine", +0.6, reason="zip_detected")

        return scans

    # ───────────────────────── helpers ─────────────────────────
    def _peek_zip_project(self, zip_path: str, *, head_limit: int = 500) -> dict:
        """
        Light peek into a .zip without extracting. Derives lineage-friendly metadata.
        """
        try:
            st = os.stat(zip_path)
        except Exception:
            st = type("S", (), {"st_size": 0, "st_mtime": 0.0})()
        mtime = st.st_mtime or time.time()
        entry_count = 0
        top_dirs: set[str] = set()
        has_manifest = False

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for i, info in enumerate(zf.infolist()):
                    if i >= int(head_limit):
                        break
                    entry_count += 1
                    name = info.filename or ""
                    if "/" in name:
                        top_dirs.add(name.split("/", 1)[0])
                    low = name.lower()
                    if low.endswith(("package.json","pyproject.toml","requirements.txt",
                                     "setup.py","cargo.toml","pom.xml","go.mod")):
                        has_manifest = True
        except Exception:
            # unreadable zip — still report presence
            pass

        top_dirs = {d for d in top_dirs if d and d != "__MACOSX"}
        doc_id = self._doc_id(os.path.abspath(zip_path), mtime)

        return {
            "doc_id": doc_id,
            "path": os.path.abspath(zip_path),
            "size_bytes": int(getattr(st, "st_size", 0)),
            "modified_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime)),
            "entry_count": int(entry_count),
            "top_dirs": sorted(top_dirs)[:10],
            "has_manifest": bool(has_manifest),
            "actor": self.ACTOR_NAME,
            "plane": self.ACTOR_PLANE,
            "channel": self.ACTOR_CHANNEL,
            "archetype": "digital_organ",
            "boot_id": getattr(self, "_mail_session", None) or "",
        }

    def _doc_id(self, path: str, mtime: float) -> str:
        h = hashlib.sha256()
        h.update(path.encode("utf-8", "ignore"))
        h.update(str(mtime).encode("utf-8"))
        return h.hexdigest()[:16]

    def _emit_ok(self, opcode: str, payload: dict):
        try: self.post.to_TRACER({"opcode": opcode, "payload": payload})
        except Exception: pass

    def _emit_warn(self, opcode: str, payload: dict):
        try: self.post.to_TRACER({"opcode": opcode, "payload": payload})
        except Exception: pass
        self._chem_nudge("cortisol", +0.2, reason=opcode.lower())

    def _emit_error(self, opcode: str, payload: dict):
        try: self.post.to_TRACER({"opcode": opcode, "payload": payload})
        except Exception: pass
        self._chem_nudge("adrenaline", +0.4, reason=opcode.lower())

    def _chem_nudge(self, chemical: str, delta: float, *, reason: str):
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {"chemical": chemical, "delta": float(delta), "source": self.ACTOR_NAME, "reason": reason}
            })
        except Exception:
            pass

# Backwards-compat alias: old name used in earlier builds
ProjectSnapshotFairy = SRMProjectSnapshotFairy

# ───────────────────────────── SRM Dual-Path Helpers ─────────────────────────────

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

def _dual_path_srm_intake(post, *, kind: str, data: dict, meta: dict | None = None) -> dict:
    day = time.strftime("%Y-%m-%d", time.gmtime())
    outdir = os.path.join(_SRMDIR, day)
    os.makedirs(outdir, exist_ok=True)
    fname = f"{kind}-{uuid.uuid4().hex[:8]}.json"
    fpath = os.path.join(outdir, fname)

    record = {"kind": kind, "meta": meta or {}, "data": data, "ts": time.time()}
    ok = _safe_write_json(fpath, record)

    # MEMORY echo for ingestion
    try:
        post.to_MEMORY({
            "opcode": "SRM_INTAKE_WRITE",
            "payload": {"kind": kind, "path": fpath, "meta": meta or {}, "data": data, "write_ok": ok}
        })
    except Exception:
        pass

    return {"path": fpath, "write_ok": ok, "meta": meta or {}}
