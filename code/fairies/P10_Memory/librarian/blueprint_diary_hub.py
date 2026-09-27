from __future__ import annotations
from fairies.P00_Autonomic.nervous_system.cross_plane_wiring import CrossPlaneWiringMixin

import os, sys, glob, time, types, uuid, json
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

# Mirror template-level SRM + dual-path routing into local namespace
_dual_path_srm_intake = getattr(_template, "_dual_path_srm_intake", None)
if _dual_path_srm_intake is None:
    raise ImportError("Template missing _dual_path_srm_intake")

_SRMDIR = getattr(_template, "_SRMDIR", None)
if _SRMDIR is None:
    # fallback — should never happen under correct template 0.0.9
    _SRMDIR = os.path.join(
        _template.resolve_root(akashic_app=os.getenv("AKASHIC_APP")),
        "SRM_Intake",
    )


# --- Per-clone shadow (wraps template's shadow behaviors, no rewiring) -------

class BlueprintDiaryHubShadowFairy(_template.MyOrganShadow):
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
    SHADOW_NAME = "BlueprintDiaryHubShadowFairy"
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

# -----------------------------------------------------------------------------

class BlueprintDiaryHubFairy(_template.MyOrganFairy):  # CrossPlaneWiringMixin inherited via MyOrganFairy
    # --- identity kept; soul evolves to "Blueprint Diary Hub" ---
    ACTOR_NAME = "BlueprintDiaryHubFairy"
    ACTOR_VERSION = "0.2.0"  # additive hub capability; no wiring changes
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory"
    ORGAN_LEVEL = False

    PURPOSE = (
        "Anchor Organ Template; verify evolution + dual-path SRM. "
        "Act as a fan-out hub for BLUEPRINT_LIVE & DIARY_ENTRY to subscribed listeners."
    )
    MANTRA = "Grow in coherence, adapt with grace. What is seen is shared."
    LORE = (
        "A clear window between organs and witnesses. It receives live blueprints and diary pulses, "
        "then shares them faithfully so the system can learn in real time."
    )

    # -- character sheet / directive ring --------------------------------------
    DIRECTIVE_ACTIVATION = {
        "mode": "Relay",
        "depth_scaling": "1..3",
        "traits": [
            "Blueprint_Hub",
            "Diary_Hub",
            "Memory_Bridge",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "Blueprint_Diary_Hub",
        "domains": [
            "Memory",
            "Autonomic",
            "Teacher",
            "GUI",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Blueprint_Synchronization",
            "Diary_Stream",
            "Hub_Fanout",
            "Subscriber_Registry",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "Blueprint_Live",
            "Diary_Entry",
            "Hub_Event",
        ],
        "field": [
            "Memory_Broadcast",
            "Topology_Snapshots",
            "Witness_Stream",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Forward_True_Blueprints",
            "No_Silent_Drops",
        ],
        "growth": [
            "Refine_Fanout_Paths",
            "Improve_Subscriber_Coverage",
        ],
        "precision": [
            "No_Duplicate_Fanout",
            "Minimal_Noise",
        ],
    }

    SUBSYSTEM_STATUS = {
        "blueprint_hub": {
            "state": "active",
            "notes": "Receives BLUEPRINT_LIVE-like payloads and caches the latest snapshot.",
            "tests": [],
        },
        "diary_stream": {
            "state": "active",
            "notes": "Accepts DIARY_ENTRY-style payloads and redistributes as DIARY_UPDATE.",
            "tests": [],
        },
        "subscription_registry": {
            "state": "active",
            "notes": "Tracks {plane, channel} subscribers for fan-out routing.",
            "tests": [],
        },
    }

    SHADOW_CLASS = BlueprintDiaryHubShadowFairy
    AUTO_INJECT_IMPORTS = True  # QoL: make std imports available as attrs if your template supports this

    # --------------------------- internal hub state ---------------------------
    def _init_hub_state(self):
        # default subscribers (non-breaking; editable via intents)
        self._subscribers = [
            {"plane": "P10", "channel": "Akashic_Records"},     # AkashicRecordsLibrarian — stores autobiographies
            {"plane": "P00", "channel": "cognition.unconscious"},  # UnconsciousMindFairy — system oversight
        ]
        self._last_blueprint = None
        # optional records root if template exposes it; otherwise default local
        try:
            root = getattr(self, "records_root", None)
        except Exception:
            root = None
        self._records_root = root or "./akashic_records"
        # simple boot token for status / diary linkage
        self._boot_id = uuid.uuid4().hex

    # best-effort JSONL diary writer (never throws; purely additive)
    def _diary_write(self, kind: str, payload: dict) -> None:
        try:
            import os, json, datetime as _dt
            day = _dt.datetime.utcnow().strftime("%Y-%m-%d")
            ddir = os.path.join(self._records_root, "diaries", "blueprint_diary_hub")
            os.makedirs(ddir, exist_ok=True)
            line = {
                "ts": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "kind": kind,
                "payload": payload,
                "plane": self.ACTOR_PLANE,
                "channel": self.ACTOR_CHANNEL,
                "actor": self.ACTOR_NAME,
                "version": self.ACTOR_VERSION,
            }
            with open(os.path.join(ddir, f"{day}.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # fan-out helper: try router if available, else fall back to TRACER telemetry
    def _fanout(self, event: str, content: dict) -> None:
        sent = 0
        for sub in list(getattr(self, "_subscribers", [])):
            pkt = {
                "event": event,
                "status": "ok",
                "dst_plane": sub.get("plane"),
                "dst_channel": sub.get("channel"),
                "details": content,
                "ts": time.time(),
            }
            routed = False
            # try generic router if template offers it
            try:
                if hasattr(self.post, "route"):
                    self.post.route(sub.get("plane"), {
                        "opcode": event,
                        "channel": sub.get("channel"),
                        "payload": content
                    })
                    routed = True
            except Exception:
                routed = False
            # try specific lanes when they match known helpers
            if not routed:
                try:
                    plane = (sub.get("plane") or "").upper()
                    ch = (sub.get("channel") or "").lower()
                    if plane == "P20":  # ui
                        self.post.to_COGNITION({"opcode": event, "payload": content})  # closest observable lane
                        routed = True
                    elif plane == "P15":  # cognition
                        self.post.to_COGNITION({"opcode": event, "payload": content})
                        routed = True
                    elif plane == "P05":  # memory
                        self.post.to_MEMORY({"opcode": event, "payload": content})
                        routed = True
                except Exception:
                    routed = False
            # always echo to TRACER for observability
            try:
                self.post.to_TRACER({"opcode": f"HUB_{event}", "payload": pkt | {"routed": routed}})
            except Exception:
                pass
            sent += 1
        # tiny dopamine nudge + diary line (best-effort)
        try:
            self.post.to_TRACER({"opcode": "CHEM_SIGNAL_UPDATE",
                                 "payload": {"neurochemical": "dopamine", "delta": +0.1}})
        except Exception:
            pass
        self._diary_write(f"fanout.{event.lower()}", {"count": sent, "keys": list((content or {}).keys())})

    # --------------------------- boot (unchanged signals + status) ------------
    def on_boot(self):
        # init hub state first
        # Get template infrastructure
        try:
            super().on_boot()
        except Exception:
            pass

        self._init_hub_state()

        # === STANDARD IGNITION WIRING ===
        # Subscribe to ignition - postal work happens there, not during boot
        try:
            self.post.subscribe("system.ignition", self._on_ignition)
            self.post.subscribe("somatic.pulse", self._on_tick)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Ignition subscription failed: {e}")

    def _on_ignition(self, packet: dict):
        """STANDARD IGNITION - Send boot signals after boot completes."""
        if getattr(self, '_ignited', False):
            return
        self._ignited = True

        print(f"[{self.ACTOR_NAME}] IGNITION - Sending boot signals")

        # lane pings so the other systems hear us
        try: self.post.to_COGNITION({"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": time.time()}})
        except Exception: pass
        try: self.post.to_SOMATIC({"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": time.time()}})
        except Exception: pass
        try: self.post.to_MEMORY({"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": time.time()}})
        except Exception: pass
        try: self.post.to_TRACER({"opcode": "BOOT_HELLO", "payload": {"note": "BlueprintDiaryHub boot complete", "ts": time.time()}})
        except Exception: pass

        # emit a STATUS_EVENT with the character sheet
        try:
            if getattr(self, "post", None):
                env = {
                    "event": "STATUS_EVENT",
                    "status": "info",
                    "title": "Blueprint Diary Hub online",
                    "message": f"template={TEMPLATE_VERSION}",
                    "details": {
                        "boot_id": self._boot_id,
                        "character_sheet": {
                            "activation": self.DIRECTIVE_ACTIVATION,
                            "nature": self.DIRECTIVE_NATURE,
                            "essence": self.DIRECTIVE_ESSENCE,
                            "foundation": self.DIRECTIVE_FOUNDATION,
                            "core_values": self.DIRECTIVE_CORE_VALUES,
                            "subsystems": self.SUBSYSTEM_STATUS,
                        },
                    },
                    "fairy": self.ACTOR_NAME,
                    "fairy_version": getattr(self, "ACTOR_VERSION", None),
                    "plane": getattr(self, "ACTOR_PLANE", None),
                    "channel": getattr(self, "ACTOR_CHANNEL", None),
                    "ts": time.time(),
                }
                pkt = {"opcode": "STATUS_EVENT", "payload": env}
                try: self.post.to_TRACER(pkt)
                except Exception: pass
                try: self.post.to_TELEMETRY(pkt)
                except Exception: pass
        except Exception:
            pass

    def _on_tick(self, packet: dict):
        """Heartbeat handler - minimal work each pulse."""
        pass  # No periodic work needed for this fairy

    # -- Existing intents (preserved verbatim) ---------------------------------
    def intent_evolution_smoke(self, payload: dict):
        """Drive one evolution tick and persist snapshot via dual-path SRM."""
        tag = (payload or {}).get("tag", "default")
        sh = getattr(self, "shadow", None) or self.SHADOW_CLASS(self)
        sim = sh.evolution_sim_tick(tag=tag)
        # extra memory echo (optional)
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

    # -- NEW additive hub intents (no wiring changes) --------------------------
    def intent_hub_subscribe(self, payload: dict) -> dict:
        """
        Add a subscriber. payload: {"plane":"Pxx","channel":"name"}.
        Idempotent. Persists a small diary line; never blocks.
        """
        plane = (payload or {}).get("plane")
        channel = (payload or {}).get("channel")
        if not plane or not channel:
            return {"ok": False, "error": "missing plane/channel"}
        item = {"plane": str(plane), "channel": str(channel)}
        if item not in self._subscribers:
            self._subscribers.append(item)
            self._diary_write("subscribe", item)
        self.post.to_TRACER({"opcode": "HUB_SUBSCRIBERS", "payload": {"count": len(self._subscribers)}})
        return {"ok": True, "subscribers": list(self._subscribers)}

    def intent_hub_unsubscribe(self, payload: dict) -> dict:
        """
        Remove a subscriber. payload: {"plane":"Pxx","channel":"name"}.
        """
        plane = (payload or {}).get("plane")
        channel = (payload or {}).get("channel")
        if not plane or not channel:
            return {"ok": False, "error": "missing plane/channel"}
        item = {"plane": str(plane), "channel": str(channel)}
        self._subscribers = [s for s in self._subscribers if s != item]
        self._diary_write("unsubscribe", item)
        self.post.to_TRACER({"opcode": "HUB_SUBSCRIBERS", "payload": {"count": len(self._subscribers)}})
        return {"ok": True, "subscribers": list(self._subscribers)}

    def intent_hub_list_subscribers(self, payload: dict) -> dict:
        """Return current subscribers."""
        return {"ok": True, "subscribers": list(self._subscribers)}

    def intent_blueprint_live(self, payload: dict) -> dict:
        """
        Receive a live blueprint snapshot and fan it out.
        Expected payload: {"blueprint": {...}} (shape is pass-through).
        """
        bp = (payload or {}).get("blueprint") or {}
        self._last_blueprint = bp
        self._diary_write("blueprint_live", {"keys": list(bp.keys())})
        self._fanout("BLUEPRINT_UPDATE", bp)
        return {"ok": True, "forwarded": True, "keys": list(bp.keys())}

    def intent_diary_entry(self, payload: dict) -> dict:
        """
        Receive a diary entry and fan it out.
        Expected payload: {"entry": {...}} -- pass-through.
        """
        entry = (payload or {}).get("entry") or {}
        self._diary_write("diary_entry", {"keys": list(entry.keys())})
        self._fanout("DIARY_UPDATE", entry)
        return {"ok": True, "forwarded": True, "keys": list(entry.keys())}

    def intent_blueprint_get_latest(self, payload: dict) -> dict:
        """Recall the most recent blueprint we received (if any)."""
        return {"ok": self._last_blueprint is not None, "blueprint": self._last_blueprint}
