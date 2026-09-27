from __future__ import annotations

import os, sys, glob, time, types, uuid, random
from collections import deque
from typing import Optional
import importlib.util, importlib.machinery
from typing import Any, Dict, Optional, List
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
    module = importlib.module_from_spec(spec)
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

class TracerDaemonShadowFairy(_template.MyOrganShadow):
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

class TracerDaemonFairy(_template.MyOrganFairy):
    """
    Tracer Daemon worker fairy.

    Responsibilities (ported from the old TracerDaemonFairy v0.0.7):
      - Collect health packets from other organs into an in-memory ledger.
      - Build a derived “blueprint”:
          planes: {plane -> [organs]}
          organs: [organ names]
      - Periodically emit BLUEPRINT_LIVE into PLAN and TRACER.
      - Emit chemistry signals on key edges (smoke OK, health transitions, repair).
      - Provide intents:
          * smoke
          * emit_chem
          * blueprint_now
          * directory (blueprint + simple ledger)
          * repair_request (escalate to ORACLE/PLAN)
    """

    # Identity
    # ACTOR_NAME stripped — wrapped by P00_Autonomic/TracerDaemonFairy/fairy.py
    # ACTOR_NAME    = "tracer.daemon"
    _ENGINE_NAME = "tracer.daemon"  # For reference only
    ACTOR_VERSION = "0.2.0"
    ACTOR_PLANE   = "P00"          # autonomic / infra plane
    ACTOR_CHANNEL = "tracer"
    ORGAN_LEVEL = False
    
    PURPOSE = (
        "Aggregate shadow health reports, build a live blueprint, and act as a "
        "forensic tracer for the Akashic nervous system."
    )
    MANTRA = "Witness everything; panic never."
    LORE   = (
        "A patient moth-fairy who flits between blueprints and diaries, "
        "keeping a quiet ledger of who is awake, worried, or drifting."
    )

    # ───────── character sheet / directive ring ─────────

    DIRECTIVE_ACTIVATION = {
        "mode": "Trace",
        "depth_scaling": "1..3",
        "traits": [
            "Autonomic_Observer",
            "Blueprint_Aggregator",
            "Chem_Bridge",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "Tracer_Daemon",
        "domains": [
            "Autonomic",
            "Infra",
            "Chemistry",
            "Memory",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Causal_Tracing",
            "Health_Ledgering",
            "Blueprint_Synchronization",
            "Chem_Signal_Routing",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "Health_Packet",
            "Blueprint_Live",
            "Chem_Breadcrumb",
        ],
        "field": [
            "Autonomic_Health",
            "Topology_Awareness",
            "Emotion_Telemetry",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Report_True_Health",
            "No_Silent_Failures",
        ],
        "growth": [
            "Refine_Blueprint_Model",
            "Improve_Repair_Escalations",
        ],
        "precision": [
            "Minimal_Noise",
            "Signal_Over_Spam",
        ],
    }

    SUBSYSTEM_STATUS = {
        "health_ledger": {
            "state": "active",
            "notes": "Collects health packets and tracks last-seen timestamps per organ.",
            "tests": [],
        },
        "blueprint_engine": {
            "state": "active",
            "notes": "Reduces health ledger into plane/organs mapping and emits BLUEPRINT_LIVE.",
            "tests": [],
        },
        "chemistry_bridge": {
            "state": "active",
            "notes": "Emits CHEM_SIGNAL_UPDATE edges on state transitions and explicit intents.",
            "tests": [],
        },
    }

    SHADOW_CLASS = TracerDaemonShadowFairy
    AUTO_INJECT_IMPORTS = True

    # Let the template wire standard infra lanes
    INFRA_AUTOSUBS = (
        "telemetry",
        "plan",
        "memory.stream",
        "oracle",
        "shadow.health",
    )

    # Optional: make the interval configurable via class attr
    BLUEPRINT_EMIT_INTERVAL_SEC = 15.0

    # ────────── lifecycle / init ──────────

    def __init__(
        self,
        *,
        akashic_root: Optional[str] = None,
        gui_alert_fn=None,
        alert_fn=None,
    ):
        # Template init (filesystem roots, diary, post, etc.)
        super().__init__(akashic_root=akashic_root)

        # Optional GUI / alert callbacks (not required by template)
        self.gui_alert_fn = gui_alert_fn
        self.alert_fn = alert_fn or gui_alert_fn

        # In-memory health ledger: organ_name -> {last_ts, msg}
        self._health: Dict[str, Dict[str, Any]] = {}

        # Blueprint cadence state
        self._last_blueprint_emit: float = 0.0
        self._blueprint_emit_interval: float = float(
            getattr(self, "BLUEPRINT_EMIT_INTERVAL_SEC", 15.0)
        )

        # Self-state tracking for chemistry edges
        self._boot_id: str = uuid.uuid4().hex
        self._last_health_state: str = "init"
        self._last_tick_duration: float = 0.0

    # ────────── intents ──────────

    def _intent_smoke(self, payload: Dict[str, Any] | None) -> Dict[str, Any]:
        """
        Smoke test: defer to the template’s standard smoke, then emit a small
        chemistry nudge to say “tracer is awake and watching”.
        """
        payload = payload or {}
        res = super()._intent_smoke(payload)
        try:
            self._emit_chem("serotonin", +0.05, "smoke_ok")
        except Exception:
            pass
        return res

    def _intent_emit_chem(self, payload: Dict[str, Any] | None) -> Dict[str, Any]:
        """
        Manually emit a chemistry signal via the tracer.

        payload:
          {
            "chemical": "dopamine" | "serotonin" | "cortisol" | ...,
            "delta": float,
            "reason": str
          }
        """
        p = payload or {}
        chemical = p.get("chemical") or "dopamine"
        delta = float(p.get("delta") or 0.0)
        reason = p.get("reason") or "tracer_emit_chem"
        self._emit_chem(chemical, delta, reason)
        return {"ok": True, "chemical": chemical, "delta": delta}

    def _intent_blueprint_now(self, payload: Dict[str, Any] | None) -> Dict[str, Any]:
        """
        Force a BLUEPRINT_LIVE emit, regardless of debounce interval.
        """
        payload = payload or {}
        bp = self._build_blueprint()
        # Local event (for GUI / logs)
        self._emit({"event": "BLUEPRINT_LIVE", "status": "ok", "details": bp})
        # TRACER lane
        try:
            if self.post:
                self.post.to_TRACER({"event": "BLUEPRINT_LIVE", "payload": bp})
                # PLAN echo for nervous system listeners
                self.post.route(
                    "PLAN",
                    {
                        "opcode": "BLUEPRINT_LIVE",
                        "payload": bp,
                        "channel": "nervous_system",
                    },
                )
        except Exception:
            pass
        self._last_blueprint_emit = time.time()
        return {"ok": True, "blueprint": bp}

    def _intent_directory(self, payload: Dict[str, Any] | None) -> Dict[str, Any]:
        """
        Return the tracer’s view: blueprint + simple health ledger.

        This is a light, intent-based snapshot other organs can call.
        """
        payload = payload or {}
        bp = self._build_blueprint()
        ledger = {k: {"last_ts": v.get("last_ts")} for k, v in self._health.items()}
        try:
            if self.post:
                self.post.to_DIRECTORY(
                    {
                        "opcode": "TRACER_DIR_SNAPSHOT",
                        "payload": {"blueprint": bp, "ledger": ledger},
                    }
                )
        except Exception:
            pass
        return {"ok": True, "blueprint": bp, "ledger": ledger}

    def _intent_repair_request(self, payload: Dict[str, Any] | None) -> Dict[str, Any]:
        """
        Escalate a tracer-sensed symptom to the ORACLE.

        payload:
          {
            "symptom": str
          }
        """
        p = payload or {}
        symptom = p.get("symptom") or "repair_request"

        suggestion = {
            "origin": "tracer_daemon",
            "symptom": symptom,
            "remedy": "increase sampling; request helper rebinding; audit channels",
        }
        ok = False
        try:
            if self.post:
                self.post.to_ORACLE({"opcode": "ORACLE_SUGGEST", "payload": suggestion})
                ok = True
        except Exception:
            ok = False

        # Fallback via PLAN lane if direct ORACLE is unavailable
        if not ok:
            try:
                if self.post:
                    self.post.to_PLAN({"opcode": "ORACLE_SUGGEST", "payload": suggestion})
                    ok = True
            except Exception:
                ok = False

        return {"ok": ok, "escalation": suggestion}

    # ────────── ingest / blueprint / tick loop ──────────

    def ingest_health_packet(self, msg: Dict[str, Any]) -> None:
        """
        Public drop-box for external callers (tests/REPLs) to feed
        health packets directly.

        Expected shape is the same as the old tracer daemon: a dict
        with at least src_organ and src_plane when possible.
        """
        if not isinstance(msg, dict):
            return
        src = msg.get("src_organ") or msg.get("organ") or "unknown"
        self._health[src] = {"last_ts": time.time(), "msg": msg}

    def _build_blueprint(self) -> Dict[str, Any]:
        """
        Reduce the health ledger into a simple plane → organs mapping.
        """
        planes: Dict[str, List[str]] = {}
        for organ, record in self._health.items():
            m = record.get("msg") or {}
            plane = m.get("src_plane") or "UNK"
            planes.setdefault(plane, []).append(organ)
        return {
            "ts": time.time(),
            "planes": planes,
            "organs": sorted(self._health.keys()),
        }

    def _emit_blueprint_periodic(self) -> None:
        """
        Periodically publish BLUEPRINT_LIVE based on the configured interval.
        """
        now = time.time()
        if now - self._last_blueprint_emit < self._blueprint_emit_interval:
            return

        self._last_blueprint_emit = now
        bp = self._build_blueprint()

        # Local event
        self._emit({"event": "BLUEPRINT_LIVE", "status": "ok", "details": bp})

        # PLAN → nervous system
        try:
            if self.post:
                self.post.route(
                    "PLAN",
                    {
                        "opcode": "BLUEPRINT_LIVE",
                        "payload": bp,
                        "channel": "nervous_system",
                    },
                )
        except Exception:
            pass

        # Legacy compatibility breadcrumb on TRACER
        try:
            if self.post:
                self.post.to_TRACER(
                    {"event": "BLUEPRINT_LIVE_P00", "payload": {"planes": bp["planes"]}}
                )
        except Exception:
            pass

    def _derive_self_state(self) -> str:
        """
        Simple freshness heuristic, ported from the old tracer daemon:

         - no messages ever           → anxious
         - last message > 90s         → critical
         - last message > 30s         → anxious
         - else                       → serene
        """
        if not self._health:
            return "anxious"
        last_any = max(record["last_ts"] for record in self._health.values())
        since = time.time() - last_any
        if since > 90:
            return "critical"
        if since > 30:
            return "anxious"
        return "serene"

    def tick(self) -> None:
        """
        Typical host loop can call this periodically.

        The tracer:
          - emits blueprint updates when due
          - derives an internal health state
          - emits chemistry on state transitions
          - occasionally asks the shadow to run tests
        """
        def _frame():
            # Blueprint cadence
            self._emit_blueprint_periodic()

            # Derive self state from traffic freshness
            state = self._derive_self_state()
            self._emit(
                {"event": "HEALTH_REPORT", "status": "ok", "details": {"state": state}}
            )

            # Chemistry edges on state transitions
            if state != self._last_health_state:
                try:
                    if state == "serene":
                        self._emit_chem("dopamine", +1.0, "health_serene")
                    elif state == "anxious":
                        self._emit_chem("cortisol", +1.0, "health_anxious")
                    elif state == "critical":
                        self._emit_chem("adrenaline", +1.0, "health_critical")
                except Exception:
                    pass
                self._last_health_state = state

            # Opportunistic shadow tests (light cadence)
            try:
                if self.shadow and random.random() < 0.25:
                    self.shadow.maybe_run(self.shadow._tests())
            except Exception:
                pass

        start = time.time()
        try:
            _frame()
        finally:
            self._last_tick_duration = time.time() - start
            # Template usually has an event buffer / diary helper;
            # we just record a standardized entry when present.
            try:
                self._record_event(
                    {"event": "TICK_MEASURE", "duration": self._last_tick_duration}
                )
            except Exception:
                pass

    # ────────── chemistry bridge ──────────

    def _emit_chem(self, chemical: str, delta: float, reason: str) -> None:
        """
        Bridge chemistry via PLAN/CHEM_SIGNAL_UPDATE (Directory will route
        to the chemistry organ), plus an optional TRACER breadcrumb.
        """
        try:
            if self.post:
                # PLAN → chemistry organ
                self.post.route(
                    "PLAN",
                    {
                        "opcode": "CHEM_SIGNAL_UPDATE",
                        "payload": {
                            "chemical": chemical,
                            "delta": float(delta),
                            "source": self.ACTOR_NAME,
                            "reason": reason,
                        },
                        "channel": "chemistry",
                    },
                )
                # Optional tracer crumb for humans / tools
                self.post.to_TRACER(
                    {
                        "event": "CHEM_BREADCRUMB",
                        "payload": {"plane": self.ACTOR_PLANE, "chemical": chemical},
                    }
                )
        except Exception:
            pass
