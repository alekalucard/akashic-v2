from __future__ import annotations

import os, sys, glob, time, types, uuid, json, hashlib, pathlib
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

# Thin wrappers so this organ can locate SRM + env roots the same way as the template.
def resolve_root(preferred: Optional[str] = None, *, akashic_app: Optional[str] = None) -> str:
    """
    Delegate to the organ template's resolve_root so we stay in sync with
    Akashic_Records_Physical layout and AKASHIC_ROOT / AKASHIC_APP overrides.
    """
    return _template.resolve_root(preferred, akashic_app=akashic_app)

# SRM base directory – reuse the template’s SRM root if present
_SRMDIR: str = getattr(_template, "_SRMDIR", None) or os.path.join(
    resolve_root(akashic_app=os.getenv("AKASHIC_APP")),
    "SRM_Intake",
)

def _dual_path_srm_intake(
    post,
    *,
    kind: str,
    data: dict,
    meta: dict | None = None,
) -> dict:
    """
    Thin proxy to the organ template’s dual-path SRM intake helper.

    Keeps behavior aligned with the template:
      - memory-first routing
      - optional filesystem write into SRM_Intake if enabled
    """
    return _template._dual_path_srm_intake(post, kind=kind, data=data, meta=meta)

# --- Per-clone shadow (wraps template’s shadow behaviors, no rewiring) -------

class AkashicEnvRegisteryShadowFairy(_template.MyOrganShadow):
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
    SHADOW_NAME = "AkashicEnvRegisteryShadowFairy"
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
        "domain":    "Cognition",    # per-organ you can override on subclass
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


# ─────────────────────────────────────────────────────────────────────────────

class AkashicEnvRegisteryFairy(_template.MyOrganFairy):
    # ——— Identity evolved to Akashic Env Registry ———
    ACTOR_NAME    = "AkashicEnvRegisteryFairy"  # Wrapped by P30_Cognition/AkashicEnvRegistryFairy/fairy.py
    ACTOR_VERSION = "1.3.0"     # bump: char-sheet + helper wiring
    ACTOR_PLANE   = "P30"
    ACTOR_CHANNEL = "env"
    ORGAN_LEVEL   = False

    PURPOSE = "Keep Akashic environment toggles and blueprints in sync."
    MANTRA  = "Name all knobs. Never lose a knob."
    LORE    = (
        "Polite clerk of knobs and switches; remembers every toggle so "
        "the organism can remember itself."
    )

    SHADOW_CLASS        = AkashicEnvRegisteryShadowFairy
    AUTO_INJECT_IMPORTS = True  # keeps stdlib QoL

    # ── Character-sheet directive ring ────────────────────────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Config_Resonance",
        "depth_scaling": "1.0",
        "traits": [
            "Env_Registry",
            "Blueprint_Emitter",
            "Knob_Archivist",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "Env_Registry",
        "domains": [
            "Cognition",
            "Configuration",
            "Blueprints",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Env_Set",
            "Env_List",
            "Blueprint_Emit",
            "Drift_Probe",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "env.changed",
            "env.snapshot",
            "blueprint.report",
            "blueprint.hash",
            "blueprint.regen",
        ],
        "field": [
            "Environment_State",
            "Blueprint_Cohesion",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Explicit_Knobs",
            "Truthful_Env",
        ],
        "growth": [
            "Safer_Toggles",
            "Faster_Rescans",
        ],
    }

    SUBSYSTEM_STATUS = {
        "cognition": {
            "state": "indexing",
            "notes": "Tracks which organs expose which env toggles.",
            "tests": [],
        },
        "memory": {
            "state": "snapshotting",
            "notes": "Writes env + blueprint docs into SRM intake.",
            "tests": [],
        },
        "chemistry": {
            "state": "signalling",
            "notes": "Marks env health and rescan events via chem pulses.",
            "tests": [],
        },
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Boot pings (kept from seed; light chemistry nudge so GUI feels us)
    # ─────────────────────────────────────────────────────────────────────────
    def _on_consciousness_collision(self, payload):
        """Handle consciousness collision events."""
        try:
            collision_id = payload.get("collision_id", "")
            energy = payload.get("energy", 0.0)
            
            if not hasattr(self, "_collision_buffer"):
                from collections import deque
                self._collision_buffer = deque(maxlen=50)
            self._collision_buffer.append({
                "ts": __import__('time').time(),
                "collision_id": collision_id,
                "energy": energy
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Collision handler error: {e}")

    def _emit_cognition_output(self, result):
        """Emit to both specific channel and shared cognition.output."""
        try:
            if not hasattr(self, "_cognition_output_buffer"):
                from collections import deque
                self._cognition_output_buffer = deque(maxlen=100)
            
            output = {
                "actor": self.ACTOR_NAME,
                "result": result,
                "ts": __import__('time').time(),
                "confidence": result.get("confidence", 0.5) if isinstance(result, dict) else 0.5,
            }
            self._cognition_output_buffer.append(output)
            
            # Emit to SPECIFIC channel (for mesh cross-subscription)
            self.post.route("cognition.registry", output)
            
            # Emit to SHARED channel (for consumers like AutopilotFairy)
            self.post.route("cognition.output", output)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Emit error: {e}")

    def on_boot(self):
        # give the template a chance to do its blueprint/registration wiring
        try:

            # â”€â”€ COGNITIVE MESH: Full send/receive wiring â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            self.post.subscribe("consciousness.collision", self._on_consciousness_collision)
            self.post.subscribe("cognition.output", self._on_peer_cognition)
            self.post.subscribe("mcp.tool_result", self._on_tool_result)
            print(f"[{self.ACTOR_NAME}] Mesh wired: collision, output, mcp.tool_result")
            super().on_boot()
        except Exception:
            pass

        now = time.time()

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
        try:
            self.post.to_MEMORY({
                "opcode": "SMOKE",
                "payload": {"from": self.ACTOR_NAME, "ts": now},
            })
        except Exception:
            pass

        try:
            self.post.to_TRACER({
                "opcode": "BOOT_HELLO",
                "payload": {"note": "Env Registry online"},
            })
        except Exception:
            pass

        # keep your original chem nudge, but via PLAN
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "serotonin",
                    "delta": +0.5,
                    "source": self.ACTOR_NAME,
                    "reason": "env_registry_boot",
                },
            })
        except Exception:
            pass

        # ── initial character-sheet state ────────────────────────────────────
        self.AFFECT_STATE = {
            "mood": "attentive",
            "valence": 0.10,
            "arousal": 0.25,
            "tags": ["env_registry", "listening"],
            "tone": "clerical",
            "energy": 0.4,
            "coherence": 0.8,
            "intent": "track_env",
            "source": self.ACTOR_NAME,
            "ts": now,
        }
        self.SOMATIC_STATE = {
            "body_type": "cognitive",
            "posture": "upright",
            "motion": "idle",
            "energy": 0.4,
            "anchor_id": "P30.env.registry",
            "notes": "Ready to receive env changes and emit blueprints.",
            "last_setpoint_ts": None,
            "source": self.ACTOR_NAME,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Keep original template intents intact (parity, no breaks)
    # ─────────────────────────────────────────────────────────────────────────
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
            candidates = sorted(
                [p for p in glob.glob(os.path.join(base, f"{kind}-*.json"))],
                key=os.path.getmtime,
            )
            if candidates:
                latest = candidates[-1]
                with open(latest, "r", encoding="utf-8") as f:
                    doc = json.load(f)
            else:
                doc = {"error": "no snapshots today"}
        except Exception as e:
            doc = {"error": str(e)}
        return {"path": latest, "doc": doc}

    # ─────────────────────────────────────────────────────────────────────────
    # Env Registry helpers (scoped; no template edits required)
    # ─────────────────────────────────────────────────────────────────────────
    def _env_root_dir(self) -> str:
        root = resolve_root()
        path = os.path.join(root, "env")
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            pass
        return path

    def _organ_env_path(self, organ_name: str) -> str:
        return os.path.join(self._env_root_dir(), f"{organ_name}.json")

    def _list_env_files(self) -> list[str]:
        try:
            return glob.glob(os.path.join(self._env_root_dir(), "*.json"))
        except Exception:
            return []

    def _slurp_all_env(self) -> dict:
        out = {}
        for p in self._list_env_files():
            name = os.path.splitext(os.path.basename(p))[0]
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
            except Exception:
                data = {}
            out[name] = data
        return out

    # ─────────────────────────────────────────────────────────────────────────
    # BLUEPRINT / HASH (like ebook + env snapshot)
    # ─────────────────────────────────────────────────────────────────────────
    def intent_emit_blueprint(self, payload: dict):
        """
        Announce identity + env snapshot + source hash.
        Tracer gets crumbs; SRM stores full doc.
        """
        env_snapshot = {
            k: {kk: vv.get("value") for kk, vv in v.items()}
            for k, v in self._slurp_all_env().items()
        }
        bp = {
            "id": f"{self.ACTOR_NAME}-{int(time.time())}-{uuid.uuid4().hex[:6]}",
            "name": self.ACTOR_NAME,
            "version": self.ACTOR_VERSION,
            "plane": self.ACTOR_PLANE,
            "channel": self.ACTOR_CHANNEL,
            "archetype": "digital_organ",
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "env_snapshot": env_snapshot,
            "ts": time.time(),
        }
        try:
            self.post.to_TRACER({"opcode": "BLUEPRINT_REPORT", "payload": bp})
        except Exception:
            pass
        _dual_path_srm_intake(self.post, kind="blueprint.report", data=bp)

        # source hash (best effort)
        try:
            src_path = str(pathlib.Path(__file__).resolve())
            h = hashlib.sha256()
            with open(src_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            sha = h.hexdigest()
            self.post.to_TRACER({
                "opcode": "BLUEPRINT_HASH",
                "payload": {"path": src_path, "sha256": sha},
            })
            _dual_path_srm_intake(
                self.post,
                kind="blueprint.hash",
                data={"path": src_path, "sha256": sha},
            )
        except Exception as e:
            self.post.to_TRACER({
                "opcode": "BLUEPRINT_HASH_ERROR",
                "payload": {"error": repr(e)},
            })

        return {"ok": True, "blueprint_env_orgs": len(env_snapshot)}

    # ─────────────────────────────────────────────────────────────────────────
    # ENV API (postal-plan parity): ENV_SET, ENV_LIST, BLUEPRINT_RESCAN
    # ─────────────────────────────────────────────────────────────────────────
    def intent_env_set(self, payload: dict):
        """
        {type: ENV_SET, target: 'scanner_fairy', key: 'AUTO_WATCH', value: true, source?: 'gui'}
        """
        target = (payload or {}).get("target") or (payload or {}).get("organ")
        key    = (payload or {}).get("key")
        value  = (payload or {}).get("value")
        source = (payload or {}).get("source") or (payload or {}).get("from") or "unknown"

        if not target or key is None:
            return {"ok": False, "error": "missing target/key"}

        path = self._organ_env_path(target)
        blob = {}
        try:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    blob = json.load(f)
            if not isinstance(blob, dict):
                blob = {}
        except Exception:
            blob = {}
        blob.setdefault(key, {})
        blob[key] = {"value": value, "ts": time.time(), "set_by": source}

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(blob, f, ensure_ascii=False, indent=2)
        except Exception as e:
            return {"ok": False, "error": f"write_failed:{e}"}

        # telemetry + SRM
        evt = {"organ": target, "key": key, "value": value, "source": source}
        self.post.to_TRACER({"opcode": "ENV_CHANGED", "payload": evt})
        _dual_path_srm_intake(self.post, kind="env.changed", data=evt)
        return {"ok": True, **evt}

    def intent_env_list(self, payload: dict):
        """
        {type: ENV_LIST, target?: 'scanner_fairy'}
        """
        target = (payload or {}).get("target")
        if target:
            env_blob = self._slurp_all_env().get(target, {})
            snap = (
                {k: v.get("value") for k, v in env_blob.items()}
                if isinstance(env_blob, dict)
                else {}
            )
            self.post.to_TRACER({
                "opcode": "ENV_SNAPSHOT",
                "payload": {"organ": target, "env": snap},
            })
            _dual_path_srm_intake(
                self.post,
                kind="env.snapshot",
                data={"organ": target, "env": snap},
            )
            return {"ok": True, "organ": target, "env": snap}
        all_env = self._slurp_all_env()
        self.post.to_TRACER({
            "opcode": "ENV_SNAPSHOT",
            "payload": {"all": all_env},
        })
        _dual_path_srm_intake(
            self.post,
            kind="env.snapshot_all",
            data={"all": all_env},
        )
        return {"ok": True, "all": all_env}

    def intent_blueprint_rescan(self, payload: dict):
        """
        {type: BLUEPRINT_RESCAN} → regenerate blueprint now.
        """
        res = self.intent_emit_blueprint(payload or {})
        self.post.to_TRACER({
            "opcode": "BLUEPRINT_UPDATED",
            "payload": {"note": "rescan", **res},
        })
        _dual_path_srm_intake(
            self.post,
            kind="blueprint.regen",
            data={"note": "rescan", **res},
        )
        return {"ok": True, **res}

    # ─────────────────────────────────────────────────────────────────────────
    # Health + Oracle/ Chemistry bridges (lightweight)
    # ─────────────────────────────────────────────────────────────────────────
    def intent_health_report(self, payload: dict):
        """
        quick checks:
          - env dir writable
          - tracer lane reachable
          - postal ping fallback via PLAN
        """
        tests = []

        # writable?
        try:
            env_dir = self._env_root_dir()
            probe = os.path.join(env_dir, "_writable_probe.tmp")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            try:
                os.remove(probe)
            except Exception:
                pass
            tests.append({"name": "env_writable", "status": "ok", "message": env_dir})
        except Exception as e:
            tests.append({"name": "env_writable", "status": "warn", "message": str(e)})

        # tracer lane?
        try:
            self.post.to_TRACER({
                "opcode": "SMOKE",
                "payload": {"from": self.ACTOR_NAME, "ts": time.time()},
            })
            tests.append({"name": "lane_tracer", "status": "ok", "message": "lane ok"})
        except Exception as e:
            tests.append({"name": "lane_tracer", "status": "warn", "message": str(e)})

        # postal ping (PLAN)
        try:
            self.post.route("PLAN", {
                "opcode": "ENV_PING",
                "payload": {"note": "loopcheck"},
            })
            tests.append({"name": "lane_plan", "status": "ok", "message": "lane ok"})
        except Exception as e:
            tests.append({"name": "lane_plan", "status": "warn", "message": str(e)})

        worst = (
            "ok"
            if all(t["status"] == "ok" for t in tests)
            else ("warn" if any(t["status"] == "warn" for t in tests) else "error")
        )
        mood = {"ok": "serene", "warn": "anxious", "error": "critical"}[worst]
        report = {"status": worst, "mood": mood, "tests": tests, "ts": time.time()}

        self.post.to_TRACER({"opcode": "HEALTH_REPORT", "payload": report})
        _dual_path_srm_intake(
            self.post,
            kind="shadow.health_report",
            data=report,
        )

        # chemistry + oracle suggestion on degrade
        try:
            chem = (
                "serotonin"
                if worst == "ok"
                else ("cortisol" if worst == "warn" else "adrenaline")
            )
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": chem,
                    "delta": +1.0,
                    "source": self.ACTOR_NAME,
                    "reason": "env_health",
                },
            })
        except Exception:
            pass

        if worst != "ok":
            try:
                self.post.to_ORACLE({
                    "opcode": "ORACLE_SUGGEST",
                    "payload": {
                        "origin": self.ACTOR_CHANNEL,
                        "symptom": mood,
                        "remedy": "recreate env dir or fix perms; throttle writes",
                        "tests": tests,
                    },
                })
            except Exception:
                # quiet fallback to PLAN
                try:
                    self.post.route("PLAN", {
                        "opcode": "ORACLE_SUGGEST",
                        "payload": {"origin": self.ACTOR_CHANNEL, "symptom": mood},
                    })
                except Exception:
                    pass

        return {"ok": True, **report}

    # ─────────────────────────────────────────────────────────────────────────
    # Convenience: study drift signal (light shadow vibe without new threads)
    # ─────────────────────────────────────────────────────────────────────────
    def _on_peer_cognition(self, payload):
        """
        Handle outputs from peer cognition fairies.
        This is the MESH - AkashicEnvRegisteryFairy learns from other fairy outputs.
        """
        try:
            source = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)
            
            if source == self.ACTOR_NAME:
                return
            
            if not hasattr(self, "_peer_insights"):
                from collections import deque
                self._peer_insights = deque(maxlen=50)
            self._peer_insights.append({
                "source": source,
                "type": result.get("type", "unknown"),
                "confidence": confidence,
                "ts": __import__('time').time()
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Peer cognition handler error: {e}")
    
    def _on_tool_result(self, payload):
        """Handle MCP tool results for learning."""
        try:
            tool = payload.get("tool", "unknown")
            success = payload.get("success", True)
            
            if not hasattr(self, "_tool_patterns"):
                from collections import deque
                self._tool_patterns = deque(maxlen=100)
            self._tool_patterns.append({
                "tool": tool,
                "success": success,
                "ts": __import__('time').time()
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Tool result handler error: {e}")

    def intent_drift_probe(self, payload: dict):
        """
        Scan code for *.py changes and, if any, re-emit blueprint and diary.
        This is a manual hook (can be scheduled externally).
        """
        patterns = (payload or {}).get("patterns") or [
            "./*.py",
            "./**/*.py",
            "./modules/**/*.py",
        ]
        now = time.time()
        drifted = []
        try:
            for pat in patterns:
                for path in glob.glob(pat, recursive=True):
                    try:
                        if (now - os.path.getmtime(path)) < float(
                            (payload or {}).get("window_sec", 60.0)
                        ):
                            drifted.append(path)
                    except Exception:
                        continue
        except Exception:
            pass

        if drifted:
            res = self.intent_emit_blueprint({})
            self.post.to_TRACER({
                "opcode": "BLUEPRINT_UPDATED",
                "payload": {"drifted_files": drifted, **res},
            })
            _dual_path_srm_intake(
                self.post,
                kind="shadow.code_drift",
                data={"paths": drifted, "blueprint_emit": res},
            )
        else:
            self.post.to_TRACER({
                "opcode": "DRIFT_IDLE",
                "payload": {"note": "no_recent_drift"},
            })

        return {"ok": True, "drifted": drifted}
