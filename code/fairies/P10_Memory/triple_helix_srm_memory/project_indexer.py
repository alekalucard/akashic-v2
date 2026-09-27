from __future__ import annotations

import os, sys, glob, time, types, uuid, json, pathlib
from collections import deque
from typing import Any, Dict, List, Optional, Callable, Tuple, Union
import importlib.util, importlib.machinery
import importlib
# --- put these near the top-level helpers (with your other tiny utils) ---
from zipfile import ZipFile, BadZipFile

def _ti_now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _ti_guess_plane(name: str) -> Optional[str]:
    n = str(name).replace("\\", "/").lower()
    if "/p00_" in n or "autonomic" in n: return "P00"
    if "/p10_" in n or "/memory/" in n:  return "P10"
    if "/p20_" in n or "somatic" in n:   return "P20"
    if "/p30_" in n or "cognition" in n: return "P30"
    if "/p40_" in n or "sensory" in n or "gui" in n: return "P40"
    if "/p50_" in n or "persona" in n or "uploader" in n or "skyporter" in n: return "P50"
    return None

def _ti_looks_documented(name: str) -> bool:
    n = str(name).lower()
    return ("fairy" in n) or ("daemon" in n) or n.endswith(".md")

def _ti_srm_env(subject: str, predicate: str, obj: str, *, context: Dict[str, Any]) -> Dict[str, Any]:
    """Shape used by SRM upsert messages on MEMORY lane."""
    return {
        "intent": "srm.upsert",
        "t": time.time(),
        "payload": {
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "strength": 0.9,
            "context": context,
        },
        "meta": {"plane": "P10", "channel": "memory.project", "module": "project_indexer_fairy"},
    }

# Legacy logging / diary helpers (lightweight, best-effort)

CHANNEL = {"TRACER": "TRACER"}

def _emit(*args, **kwargs):
    """Legacy logger shim kept for compatibility (now a no-op)."""
    return None

def _diary_write(diaries, actor: str, entry: dict, lane: str = "fairy") -> None:
    """Best-effort JSONL diary writer used by project indexer."""
    try:
        root = getattr(diaries, "root", None) or "./akashic_records"
        day = time.strftime("%Y-%m-%d", time.gmtime())
        d = os.path.join(root, "diaries", actor)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{day}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # never crash the caller
        pass

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

    # Mirror template SRM root (for local SRM helpers)
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

class SRMProjectIndexerShadowFairy(_template.MyOrganShadow):
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
    SHADOW_NAME = "SRMProjectIndexerShadowFairy"
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


# ─────────────────────────────────────────────────────────────────────────────

class SRMProjectIndexerFairy(_template.MyOrganFairy):
    ACTOR_NAME    = "SRMProjectIndexerFairy"  # Wrapped by P10_Memory/SRMProjectIndexerFairy/fairy.py
    ACTOR_VERSION = "0.2.0"   # character sheet + status emit
    ACTOR_PLANE   = "P10"
    ACTOR_CHANNEL = "memory"
    ORGAN_LEVEL = False
    # ⬇ adopt the Project Indexer's PURPOSE/MANTRA (voice + function)
    PURPOSE = "Open project archives, detect Akashic-ish modules, and upsert SRM relations."
    MANTRA  = "Name the pieces so memory can find the whole."
    LORE    = "Placeholder spirit that now moonlights as a project indexer clerk."

    # ── character sheet / directive ring ─────────────────────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Index",
        "depth_scaling": "1..3",
        "traits": [
            "SRM_Project_Indexer",
            "Akashic_Project_Clerk",
            "Helix_Strand_B",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "SRM_Project_Indexer",
        "domains": [
            "Memory",
            "SRM",
            "Project_Topology",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Project_Scan",
            "Module_Recognition",
            "SRM_Relation_Emit",
            "Human_Doc_Query",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "Project_Node",
            "Module_Node",
            "SRM_Relation",
        ],
        "field": [
            "TripleHelix_Memory",
            "Project_Index",
            "Plane_Topology",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Reflect_Real_Project_State",
            "No_Fabricated_Modules",
        ],
        "growth": [
            "Refine_Heuristics",
            "Improve_Coverage",
        ],
        "precision": [
            "Deterministic_Indexing",
            "Minimal_Noise_In_Relations",
        ],
    }

    SUBSYSTEM_STATUS = {
        "zip_scanner": {
            "state": "active",
            "notes": "Opens project ZIP archives and enumerates contents.",
            "tests": [],
        },
        "srm_relation_emitter": {
            "state": "active",
            "notes": "Emits SRM upsert events for Akashic-ish modules.",
            "tests": [],
        },
        "human_doc_query": {
            "state": "active",
            "notes": "Asks for purpose/mantra when modules look undocumented.",
            "tests": [],
        },
    }

    SHADOW_CLASS = SRMProjectIndexerShadowFairy
    AUTO_INJECT_IMPORTS = True

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

    # ────────────────────────── Existing intents (kept) ─────────────────────────
    # if your file used `intent_*` names before, keep them AND add underscored aliases so the
    # v0.0.7 intent discovery (which looks for _intent_*) picks them up transparently.

    def intent_evolution_smoke(self, payload: dict):
        tag = (payload or {}).get("tag", "default")
        sh = getattr(self, "shadow", None) or self.SHADOW_CLASS(self)
        sim = sh.evolution_sim_tick(tag=tag)
        _dual_path_srm_intake(self.post, kind="evolution.sim.echo", data=sim)
        return {"ok": True, "sim": sim}
    _intent_evolution_smoke = intent_evolution_smoke  # ← alias for discovery

    def intent_memory_snapshot(self, payload: dict):
        data = {"note": "manual snapshot", "payload": payload or {}, "ts": time.time()}
        rec = _dual_path_srm_intake(self.post, kind="memory.snapshot", data=data)
        self.post.to_TRACER({"opcode": "SNAPSHOT_OK", "payload": rec})
        return {"ok": rec.get("write_ok", False), **rec}
    _intent_memory_snapshot = intent_memory_snapshot  # ← alias

    def intent_memory_recall_latest(self, payload: dict):
        kind = (payload or {}).get("kind", "memory.snapshot")
        day = time.strftime("%Y-%m-%d", time.gmtime())
        base = os.path.join(_SRMDIR, day)
        latest = None
        try:
            candidates = sorted([p for p in glob.glob(os.path.join(base, f"{kind}-*.json"))],
                                key=os.path.getmtime)
            if candidates:
                latest = candidates[-1]
                with open(latest, "r", encoding="utf-8") as f:
                    doc = json.load(f)
            else:
                doc = {"error": "no snapshots today"}
        except Exception as e:
            doc = {"error": str(e)}
        return {"path": latest, "doc": doc}
    _intent_memory_recall_latest = intent_memory_recall_latest  # ← alias

    # ────────────────────────── NEW: Project Indexer intent ─────────────────────
    def _intent_project_index(self, payload: dict) -> dict:
        """
        Index a project ZIP like ProjectIndexerFairy.handle_project, but via Directory MEMORY lane.
        payload: { "path": "<zip file path>" }
        """
        path = (payload or {}).get("path")
        if not path or not os.path.isfile(path):
            raise ValueError("project_index requires payload.path to an existing .zip")

        zpath = pathlib.Path(path)
        try:
            with ZipFile(zpath, "r") as zf:
                namelist = zf.namelist()[:20000]  # generous cap
        except BadZipFile as e:
            # diary + gentle cortisol nudge; still no crash
            _emit(self.ACTOR_NAME, "PROJECT_INDEX_BAD_ZIP", "warn",
                  {"zip": str(zpath), "error": str(e)}, CHANNEL["TRACER"])
            try:
                self.post.to_TRACER({"opcode": "PROJECT_INDEX_BAD_ZIP", "payload": {"zip": str(zpath), "error": str(e)}})
            except Exception:
                pass
            return {"ok": False, "error": "bad_zip", "zip": str(zpath), "detail": str(e)}

        # lightweight helix breadcrumb (matches the project indexer style)
        helix = {
            "L": {"addr": {"affect": 0.2, "sem_domain": 4, "depth": 0},
                  "concept": "project_index",
                  "w": {"what": zpath.name, "how": "project.index", "when": _ti_now_iso()}},
            "R": {"addr": {"affect": -0.2, "sem_domain": 4, "depth": 0},
                  "concept": "project_index",
                  "w": {"what": zpath.name, "how": "project.index", "when": _ti_now_iso()}},
            "C": {"affect": "curious", "energy": 0.2, "coherence": 0.8},
        }
        try:
            _diary_write(self.diary, self.ACTOR_NAME,
                         {"ts": _ti_now_iso(), "kind": "project.discovered",
                          "payload": {"zip": str(zpath), "count": len(namelist), "card": {"ts": _ti_now_iso(),
                                                                                          "helix": helix,
                                                                                          "ptr": None,
                                                                                          "tags": ["memory","p10","project_index"],
                                                                                          "files": len(namelist)}}},
                         lane="fairy")
        except Exception:
            pass

        # 1) project node
        ctx = {"plane": "P10", "channel": "memory.project", "module": "project_indexer_fairy"}
        try:
            self.post.to_MEMORY(_ti_srm_env(
                subject=f"project:{zpath.name}",
                predicate="discovered_at",
                obj=_ti_now_iso(),
                context=ctx,
            ))
        except Exception:
            pass

        # 2) walk files and upsert SRM relations (only Akashic-ish)
        emitted = 0
        for name in namelist:
            if name.endswith("/"):
                continue
            lowered = name.lower()
            is_akashicish = any(h in lowered for h in (
                "nervous_system","tracer","somatic","fairy","shadow","codex","persona","gui","splitting","triple_helix"
            )) or lowered.endswith(".py") or lowered.endswith(".md")
            if not is_akashicish:
                continue

            module_subject = f"project:{zpath.name}/module:{name}"
            # a) module exists
            try:
                self.post.to_MEMORY(_ti_srm_env(
                    subject=module_subject,
                    predicate="part_of",
                    obj=f"project:{zpath.name}",
                    context=ctx,
                ))
            except Exception:
                pass

            # b) plane guess
            plane_guess = _ti_guess_plane(name)
            if plane_guess:
                try:
                    self.post.to_MEMORY(_ti_srm_env(
                        subject=module_subject,
                        predicate="implements_plane",
                        obj=plane_guess,
                        context=ctx,
                    ))
                except Exception:
                    pass

            # c) human doc request if not documented
            if not _ti_looks_documented(name):
                try:
                    self.post.to_MEMORY({
                        "intent": "memory.project.human_query",
                        "t": time.time(),
                        "payload": {
                            "project": zpath.name,
                            "module": name,
                            "reason": "missing_purpose_or_mantra",
                            "expected_reply_shape": {"purpose": "string", "mantra": "string", "intent_of_existence": "string"},
                        },
                        "meta": ctx,
                    })
                except Exception:
                    pass
            emitted += 1

        # tracer / plan echoes (nice-to-have)
        try:
            self.post.to_TRACER({"opcode": "PROJECT_INDEX_SUMMARY",
                                 "payload": {"zip": str(zpath), "count": len(namelist), "emitted": emitted}})
        except Exception:
            pass

        return {"ok": True, "zip": str(zpath), "files_scanned": len(namelist), "relations_emitted": emitted}
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
