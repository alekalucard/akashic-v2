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
for sym in ("MyOrganFairy", "MyOrganShadow", "OrganHubFacet", "RegistrationLib"):
    if not hasattr(_template, sym):
        raise ImportError(f"Template missing required symbol: {sym}")

# --- Per-clone shadow (wraps template’s shadow behaviors, no rewiring) -------

class FairyCitzensRegShadowFairy(_template.MyOrganShadow):
    """
    Shadow harness for FairyCitzensRegFairy.
    Manages:
      • evolution sim ticks
      • shadow health tests
      • cadence-driven RegistrationLib forms
      • template-aware SRM intake echoes
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
        "domain":    "Autonomic",    # per-organ you can override on subclass
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

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# =================================================================================================
# WORKER FAIRY — FairyCitzensRegFairy
# Seed actor for Fairy Citizens (registry + keepalive + chem bridge)
# =================================================================================================

class FairyCitzensRegFairy(_template.MyOrganFairy):
    """
    Seed actor for Fairy Citizens:
      - announces purpose/intent on boot
      - exposes registry intents (works alongside OrganHubFairy)
      - provides keepalive + chemistry bridge
      - uses postal-first SRM echoes (Memory owns persistence; FS fallback gated)
    """

    # Identity
    ACTOR_NAME    = "fairy_citizens.reg.michael"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE   = "P00"                            # Autonomic
    ACTOR_CHANNEL = "fairy_citizens.registrations"   # Postal topic for this worker
    ORGAN_LEVEL   = False

    # Heartbeat configuration
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 5

    PURPOSE = (
        "Coordinate and witness citizen fairies; provide maintenance chores "
        "and healthy boot smoke."
    )
    MANTRA  = "Every citizen honored; every signal witnessed."
    LORE    = "A tiny city hall for fairies: patient, tidy, and slightly sassy."

    CULTURE = "worker.autonomic.citizens"

    SHADOW_CLASS        = FairyCitzensRegShadowFairy
    AUTO_INJECT_IMPORTS = True  # QoL: std imports available on self via template

    # Optional: if your package isn’t P##_*, you can set ORGAN_PACKAGE explicitly.
    ORGAN_PACKAGE: Optional[str] = None

    # ── Character-sheet directive ring ────────────────────────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Fairy_Citizens_Registry",
        "depth_scaling": "0.9",
        "traits": [
            "Citizen_Registry",
            "Keepalive_Heartbeat",
            "Chemistry_Bridge",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "Fairy_Citizens_Hall",
        "domains": [
            "Autonomic",
            "Registry",
            "Chemistry",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Citizen_Register",
            "Citizen_List",
            "Citizen_Status",
            "Keepalive_Tick",
            "Evolution_Snapshot",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "CITIZEN_REGISTER",
            "citizens.keepalive",
            "evolution.sim.echo",
            "memory.snapshot",
        ],
        "field": [
            "Citizen_Registry_State",
            "Autonomic_Chemistry_State",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Every_Citizen_Witnessed",
            "Honest_Contracts",
        ],
        "growth": [
            "Safer_Keepalives",
            "Cleaner_Registry_Shapes",
        ],
    }

    SUBSYSTEM_STATUS = {
        "registry": {
            "state": "stewarding",
            "notes": "Maintains a local view of fairy citizens; Directory/Hub remain source of truth.",
            "tests": [],
        },
        "autonomic": {
            "state": "supporting",
            "notes": "Provides keepalive + chem bridge into the nervous system.",
            "tests": [],
        },
        "memory": {
            "state": "snapshotting",
            "notes": "Writes keepalive + snapshot breadcrumbs into SRM via Memory.",
            "tests": [],
        },
        "telemetry": {
            "state": "echoing",
            "notes": "Emits BOOT_HELLO, SNAPSHOT_OK and CITIZEN_REGISTER breadcrumbs.",
            "tests": [],
        },
        "chemistry": {
            "state": "signalling",
            "notes": "Uses CHEM_SIGNAL_UPDATE to nudge serotonin/cortisol, etc.",
            "tests": [],
        },
    }

    # -------------------------------------------------------------------------
    # Local (in-memory) registry; hub / directory remain source of truth.
    # -------------------------------------------------------------------------
    def _get_local_registry(self) -> dict:
        reg = getattr(self, "_citizens_local", None)
        if reg is None:
            reg = {}
            setattr(self, "_citizens_local", reg)
        return reg

        # -------------------------------------------------------------------------
    # Boot echo (lanes: cognition / somatic / memory + tracer + chem nudge)
    # -------------------------------------------------------------------------
    def on_boot(self):
        print(f"[{self.ACTOR_NAME}] on_boot START", flush=True)
        # Let the template do its normal blueprint/registration wiring first.
        try:
            super().on_boot()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] super().on_boot() error: {e}", flush=True)
        
        print(f"[{self.ACTOR_NAME}] super done, doing smoke", flush=True)
        now = time.time()

        # Multi-lane smoke (kept from original) - DISABLED for fast boot
        # try:
        #     self.post.to_COGNITION(
        #         {"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": now}}
        #     )
        # except Exception:
        #     pass
        # try:
        #     self.post.to_SOMATIC(
        #         {"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": now}}
        #     )
        # except Exception:
        #     pass
        # try:
        #     self.post.to_MEMORY(
        #         {"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": now}}
        #     )
        # except Exception:
        #     pass
        # try:
        #     self.post.to_TRACER(
        #         {
        #             "opcode": "BOOT_HELLO",
        #             "payload": {"note": "Fairy Citizens seed booted", "ts": now},
        #         }
        #     )
        # except Exception:
        #     pass

        # Chemistry nudge via PLAN - DISABLED for fast boot
        # try:
        #     self.to_PLAN(
        #         {
        #             "opcode": "CHEM_SIGNAL_UPDATE",
        #             "payload": {
        #                 "chemical": "serotonin",
        #                 "delta": +0.05,
        #                 "reason": "citizens_seed_boot",
        #             },
        #         }
        #     )
        # except Exception:
        #     pass

        # Intent announcement - DISABLED for fast boot
        # try:
        #     self.post.to_TRACER(
        #         {
        #             "opcode": "INTENT_DECLARED",
        #             "payload": {
        #                 "purpose": self.PURPOSE,
        #                 "intent": "citizen_registry+maintenance",
        #             },
        #         }
        #     )
        # except Exception:
        #     pass
        # try:
        #     self.intent_register_citizen(
        #         {
        #             "name": self.ACTOR_NAME,
        #             "version": self.ACTOR_VERSION,
        #             "purpose": self.PURPOSE,
        #             "mantra": self.MANTRA,
        #         }
        #     )
        # except Exception:
        #     pass

        # Initial state (minimal)
        self.AFFECT_STATE = {"mood": "welcoming", "valence": 0.15}
        self.SOMATIC_STATE = {"body_type": "process"}
        print(f"[{self.ACTOR_NAME}] on_boot END", flush=True)

    # -------------------------------------------------------------------------
    # Intents
    # -------------------------------------------------------------------------

    def intent_smoke(self, payload: dict):
        """Classic smoke echo for REPL sanity / tracer visibility."""
        nonce = uuid.uuid4().hex
        try:
            self.post.to_TRACER(
                {"opcode": "SMOKE", "payload": {"nonce": nonce, "from": self.ACTOR_NAME}}
            )
        except Exception:
            pass
        return {"ok": True, "nonce": nonce}

    def intent_evolution_smoke(self, payload: dict):
        """
        Drive one evolution tick and persist snapshot via dual-path SRM (postal-first).
        Uses the organ template's _dual_path_srm_intake helper.
        """
        tag = (payload or {}).get("tag", "default")
        sh = getattr(self, "shadow", None) or self.SHADOW_CLASS(self)
        sim = sh.evolution_sim_tick(tag=tag)  # shadow health harness already template-aware

        # Postal-first SRM record via template helper (FS gated inside template) :contentReference[oaicite:3]{index=3}
        try:
            if hasattr(_template, "_dual_path_srm_intake"):
                _template._dual_path_srm_intake(
                    self.post,
                    kind="evolution.sim.echo",
                    data=sim,
                )
        except Exception:
            pass

        return {"ok": True, "sim": sim}

    def intent_memory_snapshot(self, payload: dict):
        """
        Write an arbitrary snapshot to SRM Intake (postal-first; FS fallback is template-gated).
        """
        data = {"note": "manual snapshot", "payload": payload or {}, "ts": time.time()}
        rec = {"write_ok": False, "path": None}

        try:
            if hasattr(_template, "_dual_path_srm_intake"):
                rec = _template._dual_path_srm_intake(
                    self.post,
                    kind="memory.snapshot",
                    data=data,
                )
        except Exception:
            pass

        try:
            self.post.to_TRACER({"opcode": "SNAPSHOT_OK", "payload": rec})
        except Exception:
            pass

        return {"ok": bool(rec.get("write_ok")), **rec}
    def intent_check_contract(self, payload: dict | None = None) -> dict:
        """
        Validate a RegistrationLib contract form.

        payload: { "contract": { ...full form from RegistrationLib... } }
        Returns:
        {
            "ok": True/False,              # did the check itself run?
            "state": "ok"|"warn"|"error",  # semantic result
            "errors": [ ... ],             # human-readable messages
            "normalized": { ... },         # optional normalized contract
        }
        """
        contract = (payload or {}).get("contract") or {}
        errors: list[str] = []

        # Example checks (you’ll expand these):
        header = contract.get("header") or {}
        ident  = contract.get("identity") or {}

        if not ident.get("actor_name"):
            errors.append("missing identity.actor_name")

        if not ident.get("plane"):
            errors.append("missing identity.plane")

        # template version / codex compatibility
        security = contract.get("security") or {}
        compat   = security.get("compat") or {}
        tmpl_ver = compat.get("template_version")
        if tmpl_ver and not str(tmpl_ver).startswith("0.0.9"):
            errors.append(f"unexpected template_version: {tmpl_ver}")

        # TODO: codex + upgrade card rules plug in here

        state = "ok"
        if errors:
            # you can downgrade to "warn" if you want soft failures
            state = "error"

        return {
            "ok": True,
            "state": state,
            "errors": errors,
            "normalized": contract,
        }
    # --- Local convenience registry (hub remains SoT) -------------------------
    def intent_register_citizen(self, payload: dict):
        """
        payload:
          { "name": "fairy.name", "version": "x.y.z", "purpose": "...", "mantra": "..." }
        """
        reg = self._get_local_registry()
        name = (payload or {}).get("name")
        if not name:
            return {"ok": False, "error": "name required"}

        reg[name] = {
            "name": name,
            "version": (payload or {}).get("version") or "0.0.0",
            "purpose": (payload or {}).get("purpose") or "",
            "mantra": (payload or {}).get("mantra") or "",
            "ts": _now_iso(),
        }

        # Breadcrumbs to Memory + Directory; hub can consolidate later :contentReference[oaicite:4]{index=4}
        try:
            self.post.to_MEMORY({"opcode": "CITIZEN_REGISTER", "payload": reg[name]})
        except Exception:
            pass
        try:
            self.post.to_DIRECTORY({"opcode": "CITIZEN_REGISTER", "payload": reg[name]})
        except Exception:
            pass

        return {"ok": True, "citizen": reg[name]}

    def intent_list_citizens(self, payload: dict):
        reg = self._get_local_registry()
        return {"ok": True, "count": len(reg), "citizens": list(reg.values())}

    # Chemistry bridge (canonical CHEM_SIGNAL_UPDATE on PLAN) :contentReference[oaicite:5]{index=5}
    def intent_emit_chem(self, payload: dict):
        chem = (payload or {}).get("chemical") or "serotonin"
        try:
            delta = float((payload or {}).get("delta", +0.02))
        except Exception:
            delta = +0.02
        reason = (payload or {}).get("reason") or "citizens_request"

        try:
            self.to_PLAN(
                {
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {"chemical": chem, "delta": delta, "reason": reason},
                }
            )
            return {"ok": True, "chemical": chem, "delta": delta}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    def intent_status_citizens(self, payload: dict):
        """
        Status-friendly view of the citizen registry.
        Returns:
          {
            "ok": True,
            "ts": "...",
            "summary": { "count": N },
            "citizens": [ {name, version, purpose, mantra, ts}, ... ]
          }
        """
        reg = self._get_local_registry()
        citizens = list(reg.values())
        return {
            "ok": True,
            "ts": _now_iso(),
            "summary": {"count": len(citizens)},
            "citizens": citizens,
        }

    # -------------------------------------------------------------------------
    # Keepalive (postal-first; no raw FS writes unless explicitly gated)
    # -------------------------------------------------------------------------
    KEEPALIVE_KIND = "citizens.keepalive"

    def _touch_keepalive(self) -> dict:
        rec = {"ts": _now_iso(), "actor": self.ACTOR_NAME}

        # Postal → Memory (primary)
        try:
            self.post.to_MEMORY(
                {
                    "opcode": "SRM_INTAKE_WRITE",
                    "payload": {"kind": self.KEEPALIVE_KIND, "meta": {}, "data": rec},
                }
            )
        except Exception:
            pass

        # Optional FS fallback through the template helper (if available & gated) :contentReference[oaicite:6]{index=6}
        wrote = False
        path = None
        try:
            if os.getenv("AKASHIC_SRM_FS", "0") == "1" and hasattr(
                _template, "_dual_path_srm_intake"
            ):
                out = _template._dual_path_srm_intake(
                    self.post,
                    kind=self.KEEPALIVE_KIND,
                    data=rec,
                )
                wrote, path = bool(out.get("write_ok")), out.get("path")
        except Exception:
            pass

        try:
            self.post.to_TRACER(
                {"opcode": "KEEPALIVE_TOUCHED", "payload": {"path": path, "fs": wrote}}
            )
        except Exception:
            pass

        return {"ok": True, "fs": wrote, "path": path}

    def intent_keepalive(self, payload: dict):
        return self._touch_keepalive()
