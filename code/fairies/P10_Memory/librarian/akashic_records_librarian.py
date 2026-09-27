from __future__ import annotations

import os, sys, glob, time, types, uuid, importlib, weakref, json, hashlib
from collections import deque
from typing import Any, Dict, List, Optional, Callable, Tuple, Union
import importlib.util, importlib.machinery, threading
from fairies.P00_Autonomic.nervous_system.cross_plane_wiring import CrossPlaneWiringMixin

# MCP-SAFE: redirect prints to stderr
_builtin_print = print
def print(*args, **kwargs):
    kwargs['file'] = sys.stderr
    _builtin_print(*args, **kwargs)

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
DIR_CHANNEL = getattr(_template, "DIR_CHANNEL", {})
# Ensure required symbols exist
for sym in ("MyOrganFairy", "MyOrganShadow", "TemplateShadowFairy", "OrganHubFacet", "RegistrationLib"):
    if not hasattr(_template, sym):
        raise ImportError(f"Template missing required symbol: {sym}")


class _SignalBus:
        def __init__(self):
            self._subs = {}  # topic -> set(weakref to callbacks)

        def subscribe(self, topic: str, fn):
            bucket = self._subs.setdefault(topic, set())
            try:
                ref = weakref.WeakMethod(fn) if hasattr(fn, "__self__") else weakref.ref(fn)
            except TypeError:
                ref = weakref.ref(fn)
            bucket.add(ref)
            return True

        def publish(self, topic: str, data):
            dead = []
            for ref in list(self._subs.get(topic, ())):
                cb = ref()
                if cb is None:
                    dead.append(ref); continue
                try:
                    cb(data)
                except Exception:
                    # never crash the bus
                    pass
            for ref in dead:
                self._subs[topic].discard(ref)
# --- Per-clone shadow (wraps template's shadow behaviors, no rewiring) -------

class AkashicRecordsLibrarianShadowFairy(_template.MyOrganShadow):
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

    def _attach_subscriptions(self) -> None:
        if not getattr(self, "post", None):
            return

        def _safe_sub(lane: str):
            try:
                self.post.subscribe(lane, self._on_bus_packet)
            except Exception:
                pass

        for lane in ("telemetry", "fairy.autobiography"):
            _safe_sub(lane)

    def _on_bus_packet(self, payload: dict) -> None:
        """
        Bridge bus packets (telemetry / tracer / memory.stream)
        into the Librarian's ingestion pipeline.
        """
        # Re-entrancy guard to prevent infinite recursion
        # (librarian emits telemetry while processing telemetry)
        if getattr(self, '_processing_packet', False):
            return
        try:
            self._processing_packet = True
            actor = getattr(self, "actor", None)
            if actor is not None and hasattr(actor, "_on_ingest"):
                actor._on_ingest(payload or {})
        except Exception:
            # never break the bus on bad packets
            pass
        finally:
            self._processing_packet = False


# ─────────────────────────────────────────────────────────────────────────────

class AkashicRecordsLibrarianFairy(_template.MyOrganFairy):  # CrossPlaneWiringMixin inherited via MyOrganFairy
    """
    Minimal change-gating librarian:
      • Ingests human-formatted scribe packets
      • Maintains per-organ state (status, counters, bugs, last_seen)
      • Emits blueprint/GUI only when normalized payload changed
      • First GUI snapshot is emitted at boot; subsequent frames emit on change only
    """
    # — Identity —
    ACTOR_NAME    = "AkashicRecordsLibrarianFairy"  # Wrapped by P10_Memory/AkashicRecordsLibrarianFairy/fairy.py
    ACTOR_VERSION = "0.2.0"
    ACTOR_PLANE   = "P10"
    ACTOR_CHANNEL = "Akashic_Records"
    ORGAN_LEVEL = False

    PURPOSE = ("Anchor Organ Template; verify evolution + dual-path SRM. "
               "Gate GUI updates to only-on-change and avoid bloat.")
    MANTRA  = "Grow in coherence, adapt with grace. See the shape inside the signal."
    LORE    = ("A librarian of echoes who fingerprints patterns for recall; "
               "only writes when the page has truly changed.")

    # — Character sheet / directive ring —
    DIRECTIVE_ACTIVATION = {
        "mode": "Curate",
        "depth_scaling": "1..3",
        "traits": [
            "Archive_Librarian",
            "Signal_Curator",
            "GUI_Weaver",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "Akashic_Librarian",
        "domains": [
            "Memory",
            "Directory",
            "Status_GUI",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Scribe_Ingestion",
            "Card_Synchronization",
            "Blueprint_Emission",
            "GUI_Frame_Composition",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "Akashic_Card",
            "Organ_Directory",
            "GUI_Status_Frame",
        ],
        "field": [
            "System_Health_Overview",
            "Plane_Summaries",
            "Bug_Feed",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Reflect_True_State",
            "No_Ghost_Organs",
        ],
        "growth": [
            "Refine_Card_Models",
            "Improve_Status_Summaries",
        ],
        "precision": [
            "Change_Gated_Emits",
            "Dedup_Noise",
        ],
    }

    SUBSYSTEM_STATUS = {
        "scribe_ingest": {
            "state": "active",
            "notes": "Ingests Forensic Scribe status packets via intent_ingest_scribe_packet and _on_ingest.",
            "tests": [],
        },
        "card_engine": {
            "state": "active",
            "notes": "Maintains per-actor Akashic cards and emits AKASHIC_CARD_UPSERT with hash-based dedupe.",
            "tests": [],
        },
        "directory_index": {
            "state": "active",
            "notes": "Tracks lightweight _orgs directory seeded from telemetry, Directory, and citizen registry.",
            "tests": [],
        },
        "gui_status": {
            "state": "active",
            "notes": "Builds GUI_STATUS frames and emits only when the normalized signature changes.",
            "tests": [],
        },
    }

    SHADOW_CLASS = AkashicRecordsLibrarianShadowFairy
    AUTO_INJECT_IMPORTS = False

    # — State —
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Shadow will handle all the real work
        self.shadow = self.SHADOW_CLASS(self)
        self._cards: Dict[str, Dict[str, Any]] = {}     # actor -> {"card": {...}, "sha": "..."}
        self._emit_lock = threading.Lock()
        self._throttle_due: Dict[str, float] = {}       # actor -> next allowed ts
        self._throttle_sec: float = 0.5
        self._orgs: Dict[str, Dict[str, Any]] = {}
        self._bugs: List[Dict[str, Any]] = []
        self._meters: Dict[str, float] = {"dopamine": 0.0, "serotonin": 0.0, "cortisol": 0.0, "adrenaline": 0.0}

        self._last_bp_sig: Optional[str] = None
        self._last_gui_sig: Optional[str] = None
        self._gui_seq: int = 0
        self._bus = _SignalBus()
        # emit initial GUI once after boot completes
        try:
            self.intent_emit_gui_if_changed({})
        except Exception:
            pass

    def _bind_shadow(self):
        self.shadow = AkashicRecordsLibrarianShadowFairy(self, interval_sec=60.0)

    # — Utilities —
    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _norm_for_sig(self, obj: Any) -> Any:
        """Strip volatile keys so signatures are stable and dedup works.

        This ensures the GUI only refreshes on *semantic* changes,
        not on timing noise, last_seen updates, or sequence counters.
        """
        drop = {
            "ts",
            "time",
            "id",
            "nonce",
            "_seq",
            "seq",
            "last_seen",
        }

        if isinstance(obj, dict):
            return {
                k: self._norm_for_sig(v)
                for k, v in obj.items()
                if k not in drop
            }

        if isinstance(obj, list):
            return [self._norm_for_sig(v) for v in obj]

        return obj


    def _stable_sig(self, obj: Any) -> Optional[str]:
        try:
            norm = self._norm_for_sig(obj)
            raw = json.dumps(norm, sort_keys=True, ensure_ascii=False).encode("utf-8")
            return hashlib.sha256(raw).hexdigest()
        except Exception:
            return None

    def _push_bug(self, item: Dict[str, Any], maxlen: int = 200) -> None:
        self._bugs.append(item)
        if len(self._bugs) > maxlen:
            self._bugs = self._bugs[-maxlen:]


    def gui_subscribe(self, topic: str, callback) -> bool:
        """GUI calls: librarian.gui_subscribe('CARD_CHANGED'|'GUI_FRAME_CHANGED', cb)"""
        return self._bus.subscribe(topic, callback)

    def _signal(self, topic: str, data: dict) -> None:
        try:
            self._bus.publish(topic, data)
        except Exception:
            pass
    # — Blueprint (change-only) —
    def _make_blueprint(self) -> Dict[str, Any]:
        return {
            "actor": {
                "name": self.ACTOR_NAME,
                "version": self.ACTOR_VERSION,
                "plane": self.ACTOR_PLANE,
                "channel": self.ACTOR_CHANNEL,
                "purpose": self.PURPOSE,
                "mantra": self.MANTRA,
            },
            "lanes": dict(DIR_CHANNEL),
            "org_index": sorted(self._orgs.keys()),
            "meters": dict(self._meters),
        }

    def intent_blueprint_if_changed(self, payload: dict) -> dict:
        bp = self._make_blueprint()
        sig = self._stable_sig(bp)
        if not sig:
            return {"ok": False, "error": "sig_failed"}

        if sig != self._last_bp_sig:
            self._last_bp_sig = sig
            try: self.post.to_TELEMETRY({"opcode": "BLUEPRINT_REPORT", "payload": bp})
            except Exception: pass
            try: self.post.to_TELEMETRY({"opcode": "BLUEPRINT_HASH", "payload": {"sha256": sig}})
            except Exception: pass
            try: self.post.to_TRACER({"opcode": "BLUEPRINT_REPORT", "payload": {"sha256": sig, "actor": self.ACTOR_NAME}})
            except Exception: pass
            # SRM snapshot (available in 0.0.7 template)
            try:
                path = _template._persist_blueprint_snapshot(
                    bp,
                    sig,
                    actor=self.ACTOR_NAME,
                    post=getattr(self, "post", None),
                )
            except Exception:
                path = None
            self._diary_write("blueprint.emit", {"sha": sig, "path": path})
            return {"ok": True, "emitted": True, "sha": sig, "path": path}
        return {"ok": True, "emitted": False, "sha": sig}

    # — Scribe ingestion (the only input this fairy needs right now) —
    def intent_ingest_scribe_packet(self, payload: dict) -> dict:
        """
        Accepts human-friendly forensic scribe telemetry:
            {event, status, details, fairy, fairy_version, ...}
        Normalizes into per-organ state; NO GUI emit here unless state changed.
        """
        pkt = payload or {}
        src = (pkt.get("fairy") or pkt.get("src_fairy") or "unknown").strip()
        status = str(pkt.get("status", "info")).lower()
        details = pkt.get("details") or {}

        rec = self._orgs.get(src, {
            "name": src,
            "plane": details.get("plane"),
            "channel": details.get("channel"),
            "version": pkt.get("fairy_version"),
            "counters": {},
            "bugs": [],
        })

        # merge stable fields; update heartbeat
        rec["status"] = status if status in {"ok", "warn", "error", "info"} else "info"
        rec["last_seen"] = self._now_iso()

        # optional counters/fields passed through details
        if isinstance(details.get("counters"), dict):
            rec["counters"].update(details["counters"])

        # bug feed on warn/error or explicit event mentions
        if status in {"warn", "error"} or "bug" in str(pkt.get("event", "")).lower():
            bug = {
                "when": rec["last_seen"],
                "from": src,
                "event": pkt.get("event"),
                "status": status,
                "details": {k: v for k, v in details.items() if k not in {"ts", "time", "nonce"}},
            }
            rec["bugs"].append(bug)
            self._push_bug(bug)

        # store and diary (dedup by normalized entry)
        self._orgs[src] = rec
        self._diary_write("telemetry.ingest", {"from": src, "status": rec["status"], "event": pkt.get("event")})

        # Return whether this *state* changed (so caller can decide to tick GUI)
        sig = self._stable_sig(rec)
        changed = (rec.get("_last_sig") != sig)
        rec["_last_sig"] = sig
        return {"ok": True, "organ": src, "changed": bool(changed)}

    def intent_ingest_packet(self, payload: dict) -> dict:
        """
        Backwards-compatible alias for older callers that still send
        `ingest_packet` instead of `ingest_scribe_packet`.

        For now this is just a thin wrapper so ForensicScribeFairy and any
        other legacy producers can talk to the librarian without having to
        know the newer intent name.
        """
        return self.intent_ingest_scribe_packet(payload)


    # — GUI: emit once at boot, then only on change —
    def _compose_gui_frame(self) -> Dict[str, Any]:
        # "character sheet" concept + per-organ panels + meters + bug feed
        character = {
            "name": "Akashic System",
            "level": 1,
            "archetype": "Librarian",
            "hp": 100,
            "mp": 100,
        }

        panels = [{
            "organ": n,
            "plane": s.get("plane"),
            "channel": s.get("channel"),
            "version": s.get("version"),
            "status": s.get("status"),
            "last_seen": s.get("last_seen"),
            "bugs": s.get("bugs", [])[-5:],
            "counters": s.get("counters", {}),
        } for n, s in sorted(self._orgs.items())]

        # health rollup
        worst = "ok"
        for p in panels:
            st = (p.get("status") or "unknown").lower()
            if st == "error":
                worst = "error"
                break
            if st == "warn" and worst == "ok":
                worst = "warn"
        mood = {"ok": "serene", "warn": "anxious", "error": "critical"}.get(worst, "serene")

        tabs = [
            {"id": "health", "label": "Health"},
            {"id": "organs", "label": "Organs"},
            {"id": "bugs", "label": f"Bugs ({len(self._bugs)})"},
            {"id": "blueprints", "label": "Blueprints"},
        ]

        # NEW: plane → directory view (this is what AkashicStatusDock expects)
        planes: Dict[str, Dict[str, Any]] = {}

        for actor, rec in sorted(self._orgs.items()):
            plane = rec.get("plane") or "unknown"
            status = (rec.get("status") or "unknown").lower()
            if status not in {"ok", "warn", "error", "info"}:
                status = "unknown"

            entry = {
                "actor": actor,
                "name": rec.get("name") or actor,
                "plane": plane,
                "channel": rec.get("channel") or "unknown",
                "status": status,
                "role": rec.get("role") or rec.get("purpose") or "organ",
                "version": rec.get("version") or "",
                "last_seen": rec.get("last_seen"),
                "bugs": len(rec.get("bugs") or []),
                "counters": rec.get("counters") or {},
                "has_card": actor in self._cards,
            }

            bucket = planes.setdefault(plane, {"directory": [], "summary": {}})
            bucket["directory"].append(entry)

        # per-plane summaries
        for plane, pdata in planes.items():
            counts = {"ok": 0, "warn": 0, "error": 0, "info": 0, "unknown": 0}
            for ent in pdata["directory"]:
                st = ent["status"]
                if st not in counts:
                    st = "unknown"
                counts[st] += 1

            # worst status wins: error > warn > ok > info > unknown
            worst_plane = "unknown"
            for candidate in ("error", "warn", "ok", "info"):
                if counts[candidate] > 0:
                    worst_plane = candidate
                    break

            pdata["summary"] = {
                "count": len(pdata["directory"]),
                "status": worst_plane,
                "states": counts,
            }

        frame = {
            "event": "GUI_STATUS",
            "status": worst,
            "details": {
                "seq": self._gui_seq + 1,
                "character": character,
                "panels": panels,
                "meters": dict(self._meters),
                "tabs": tabs,
                "bug_feed": self._bugs[-50:],
                "mood": mood,
            },
            # this is the crucial piece for the Status dock:
            "planes": planes,
            "fairy": self.ACTOR_NAME,
            "fairy_version": self.ACTOR_VERSION,
            "contract_version": "1.0",
        }
        return frame



    def intent_emit_gui_if_changed(self, payload: dict) -> dict:
        """
        Build the GUI frame and emit to GUI/TELEMETRY only when its normalized signature changed.
        On first call (after boot), it will emit once.
        """
        frame = self._compose_gui_frame()
        sig = self._stable_sig(frame)
        if sig and sig == self._last_gui_sig:
            return {"ok": True, "emitted": False, "seq": self._gui_seq, "sha": sig}

        # bump seq and emit
        self._gui_seq += 1
        frame["details"]["seq"] = self._gui_seq

        try:
            # GUI lane (v0.0.7): gui.state
            self.post.route("GUI", {"opcode": "GUI_STATUS", "payload": frame})
        except Exception:
            pass
        try:
            # Telemetry echo for history/forensics
            self.post.to_TELEMETRY({"opcode": "GUI_STATUS", "payload": frame})
        except Exception:
            pass

        self._last_gui_sig = sig
        self._diary_write("telemetry.gui_status", {"seq": self._gui_seq, "sha": sig})
        self._signal("GUI_FRAME_CHANGED", {"seq": self._gui_seq, "sha": sig, "frame": frame})
        return {"ok": True, "emitted": True, "seq": self._gui_seq, "sha": sig}

    # — Optional: chemistry pings usable by GUI meters —
    def intent_chem_bump(self, payload: dict) -> dict:
        chem = str((payload or {}).get("neurochemical") or "dopamine")
        delta = float((payload or {}).get("delta") or 0.1)
        self._meters[chem] = float(self._meters.get(chem, 0.0)) + delta
        try:
            self.post.to_TELEMETRY({"opcode": "CHEM_SIGNAL_UPDATE", "payload": {"neurochemical": chem, "delta": delta}})
        except Exception:
            pass
        return {"ok": True, "neurochemical": chem, "value": self._meters[chem]}

    # — Boot: keep the canonical smokes, then emit first GUI frame —
    def on_boot(self) -> None:
        super().on_boot()
        # LET THE SHADOW DO ALL THE HEAVY LIFTING — THIS IS THE CORRECT WAY
        if hasattr(self, "shadow") and self.shadow:
            # This calls the FULLY WORKING _attach_subscriptions with _on_bus_packet
            self.shadow._attach_subscriptions()
            print("[LIBRARIAN] Shadow subscriptions attached — now ingesting all telemetry")

        # Emit hello so everyone knows we're alive
        try:
            self.post.to_TRACER({
                "opcode": "BOOT_HELLO",
                "payload": {"actor": self.ACTOR_NAME, "plane": "P10", "role": "librarian"}
            })
        except Exception:
            pass

        print(f"[LIBRARIAN] {self.ACTOR_NAME} booted — shadow subscriptions active")

    # — Diary helper (dedup path from template if available; else minimal) —
    def _diary_write(self, kind: str, payload: dict) -> None:
        try:
            root = getattr(self, "records_root", "./akashic_records")
            organ = "akashic_records_librarian"
            day = time.strftime("%Y-%m-%d", time.gmtime())
            d = os.path.join(root, "diaries", organ)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"{day}.jsonl"), "a", encoding="utf-8") as f:
                line = {"ts": self._now_iso(), "kind": kind, "organ": organ,
                        "plane": self.ACTOR_PLANE, "channel": self.ACTOR_CHANNEL, "payload": payload}
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except Exception:
            pass

    from typing import Optional, Dict, Any  # at top of file if not present

    def _on_ingest(self, payload: Optional[dict]) -> None:
        """Normalize tracer/telemetry/memory packets into librarian observations.

        New behavior: be permissive.
        Any packet that names an actor becomes an observation. We still
        normalize inner/outer payloads and details, but we do NOT filter
        on `kind`/`opcode` strings anymore.

        Also: explicitly handle FORENSIC_CARD_UPSERT / AKASHIC_CARD_UPSERT
        for card-style updates.
        """
        p = payload or {}

        # ---------- special path: fairy autobiography (status sheet) ----------
        if p.get("opcode") == "FAIRY_STATUS_SHEET":
            actor = p.get("actor")
            sheet = p.get("sheet") or {}
            if not actor or not isinstance(sheet, dict):
                return

            # Store the status sheet in a dedicated autobiographies dict
            if not hasattr(self, "_autobiographies"):
                self._autobiographies = {}

            # Keep last N status sheets per actor (autobiography history)
            if actor not in self._autobiographies:
                self._autobiographies[actor] = []
            self._autobiographies[actor].append({
                "ts": p.get("ts", time.time()),
                "sheet": sheet,
            })
            # Keep only last 100 entries per actor
            if len(self._autobiographies[actor]) > 100:
                self._autobiographies[actor] = self._autobiographies[actor][-100:]

            # Also merge into the actor's card as character_sheet
            existing_card = self._cards.get(actor, {}).get("card", {})
            existing_card["character_sheet"] = sheet
            self._cards[actor] = {"card": existing_card, "sha": None}

            # Update directory record
            rec = self._orgs.get(actor, {
                "name": actor,
                "plane": None,
                "channel": None,
                "version": None,
                "status": "unknown",
                "last_seen": None,
                "role": None,
                "purpose": None,
                "bugs": [],
                "counters": {},
            })
            rec["last_seen"] = self._now_iso()
            core = sheet.get("core", {})
            if core.get("actor_plane"):
                rec["plane"] = core["actor_plane"]
            if core.get("actor_channel"):
                rec["channel"] = core["actor_channel"]
            if core.get("actor_version"):
                rec["version"] = core["actor_version"]
            if core.get("purpose"):
                rec["purpose"] = core["purpose"]
            self._orgs[actor] = rec

            # Write to librarian diary for persistence
            self._diary_write("autobiography", {
                "actor": actor,
                "sheet": sheet,
            })
            return

        # ---------- special path: forensic / akashic cards (from ForensicScribeFairy or others) ----------
        if p.get("opcode") in ("FORENSIC_CARD_UPSERT", "AKASHIC_CARD_UPSERT"):
            inner = p.get("payload") or {}

            # prefer inner.actor, but fall back to outer actor if needed
            actor = inner.get("actor") or p.get("actor")
            card  = inner.get("card") or {}
            sha   = inner.get("sha")

            # must at least have an actor and a dict-like card
            if not actor or not isinstance(card, dict):
                return

            # previous card info (if any) so we can check whether sha actually changed
            prev = self._cards.get(actor) or {}
            prev_sha = prev.get("sha")

            # store the card directly
            self._cards[actor] = {"card": card, "sha": sha}

            # build/update lightweight directory record
            rec = self._orgs.get(actor, {
                "name": actor,
                "plane": None,
                "channel": None,
                "version": None,
                "status": "unknown",
                "last_seen": None,
                "role": None,
                "purpose": None,
                "bugs": [],
                "counters": {},
            })

            # fold card details into directory record
            rec["plane"]   = card.get("plane")   or rec.get("plane")   or "unknown"
            rec["channel"] = card.get("channel") or rec.get("channel") or "unknown"
            rec["version"] = card.get("actor_version") or rec.get("version")

            # health/status normalization
            h  = card.get("health") or {}
            st = (h.get("status") or rec.get("status") or "unknown").lower()
            if st not in {"ok", "warn", "error", "info"}:
                st = "unknown"
            rec["status"] = st

            # optional semantic fields
            rec["role"]    = card.get("role")    or rec.get("role")
            rec["purpose"] = card.get("purpose") or rec.get("purpose")

            # update last_seen on any card ingest
            rec["last_seen"] = self._now_iso()

            first_seen = actor not in self._orgs
            self._orgs[actor] = rec

            # DEBUG: first time we see this actor from card path
            if first_seen:
                print(f"[LIBRARIAN] first card for actor={actor} status={st}")

            # only nudge GUI if the card's sha actually changed
            if sha and sha != prev_sha:
                try:
                    self.intent_emit_gui_if_changed({})
                except Exception:
                    pass

            return

        # ---------- generic permissive path (other telemetry) ----------
        # Many senders wrap the actual content in `payload`
        inner = p.get("payload") or {}
        # Normalized `details` view
        details = p.get("details") or inner.get("details") or {}

        # Resolve the actor / organ name from the most common fields
        actor = (
            p.get("actor")
            or p.get("fairy")
            or inner.get("actor")
            or inner.get("organ")
            or inner.get("fairy")
            or details.get("actor")
        )
        if not actor:
            return

        # Flatten inner payload onto the outer dict so downstream logic
        # sees a unified observation.
        merged: Dict[str, Any] = {}
        merged.update(inner)
        merged.update(p)
        if "details" not in merged:
            merged["details"] = details

        # DEBUG: log first time we see an actor via generic path
        if actor not in self._orgs:
            print(
                "[LIBRARIAN] first observation for actor:",
                actor,
                "opcode=", p.get("opcode"),
                "kind=", p.get("kind"),
            )

        # Let the card/directory merger figure out how to store it.
        try:
            self._merge_observation(actor, merged)
        except Exception:
            # never crash on bad telemetry
            return

        # after any observation, ask GUI to refresh;
        # this is change-gated inside intent_emit_gui_if_changed
        try:
            self.intent_emit_gui_if_changed({})
        except Exception:
            pass




    def intent_status_citizens(self, payload: dict) -> dict:
        """
        Bridge into FairyCitzensRegFairy for GUI / tools.
        """
        try:
            use_intent = getattr(self.post, "use_intent", None)
            if not callable(use_intent):
                return {"ok": False, "error": "no_use_intent"}

            # choose list_citizens or status_citizens depending on what you added
            res = use_intent(
                "fairy_citizens.reg.michael",
                "status_citizens",   # or "list_citizens"
                payload or {},
            )
            if isinstance(res, dict):
                return {"ok": True, **res}
            return {"ok": True, "raw": res}
        except Exception as e:
            return {"ok": False, "error": str(e)}


    def _new_card(self, actor: str) -> dict:
        return {
            "actor": actor,
            "plane": None,
            "channel": None,
            "actor_version": None,
            "lore": "",
            "blueprint": {"sha": None, "purpose": None, "mantra": None, "lore": None},
            "health": {"status": "unknown", "message": "", "recent": []},
            "checks": {"worst": "ok", "last": []},
            "evolution": {"ticks": 0},
            # NEW: home for the directive ring + subsystem states
            "character_sheet": None,
            "tabs": [
                {"id": "overview", "title": "Overview"},
                {"id": "health",   "title": "Health"},
                {"id": "checks",   "title": "Checks"},
                {"id": "blueprint","title": "Blueprint"},
            ],
            "ts": time.time(),
        }


    def _merge_observation(self, actor: str, obs: dict):
        """
        Merge a normalized observation into:
        • the rich Akashic card model (self._cards)
        • the lightweight organ directory (self._orgs)

        This is called both from telemetry ingestion (_on_ingest) and from any
        future scribe-style summaries.
        """
        # ----- 1) Akashic card path (what the right-hand "Akashic Card" view uses) -----
        card = (self._cards.get(actor) or {}).get("card") or self._new_card(actor)

        if obs.get("kind") == "forensic.card" and obs.get("card"):
            # Update our stored card + sha from the observation
            self._cards[actor] = {
                "card": obs["card"],
                "sha": obs.get("sha"),
            }
            # Refresh local working reference so downstream logic sees the new card
            card = self._cards[actor]["card"]

            # IMPORTANT:
            # Do NOT schedule a GUI update or return here.
            # The caller (_on_ingest) will call intent_emit_gui_if_changed({})
            # once per observation, and that call is already change-gated
            # via the GUI frame signature.

        # identity (idempotent)
        card["actor"]         = actor
        card["plane"]         = obs.get("plane") or card.get("plane")
        card["channel"]       = obs.get("channel") or card.get("channel")
        card["actor_version"] = (
            obs.get("actor_version")
            or obs.get("fairy_version")
            or card.get("actor_version")
        )
        card["lore"]          = card.get("lore") or obs.get("lore") or ""

        # health
        st  = (obs.get("status") or (obs.get("details") or {}).get("mood") or "").lower()
        msg = (obs.get("message") or (obs.get("details") or {}).get("message") or "")
        if st:
            card["health"]["status"] = st
        if msg:
            card["health"]["message"] = msg[:240]
        tail = card["health"].setdefault("recent", [])
        tail.append({
            "ts": obs.get("ts") or time.time(),
            "status": st,
            "msg": msg[:120],
        })
        if len(tail) > 20:
            del tail[:-20]

        # blueprint echoes
        if "blueprint" in (obs.get("kind", "") or "") or "blueprint" in (obs.get("details") or {}):
            bp = (
                obs.get("blueprint")
                or (obs.get("details") or {}).get("blueprint")
                or {}
            )
            if bp:
                card["blueprint"] = {
                    "sha": (
                        obs.get("sha")
                        or (obs.get("details") or {}).get("sha")
                        or bp.get("sha")
                        or card["blueprint"].get("sha")
                    ),
                    "purpose": bp.get("purpose") or card["blueprint"].get("purpose"),
                    "mantra":  bp.get("mantra")  or card["blueprint"].get("mantra"),
                    "lore":    bp.get("lore")    or card["blueprint"].get("lore"),
                }
                    # --- character sheet integration (from fairy_status_sheet / STATUS_EVENT) ---
        cs = None

        # 1) modern path: top-level character_sheet on the observation
        if "character_sheet" in obs:
            cs = obs.get("character_sheet")

        # 2) event path: nested under details.character_sheet (or legacy details.character)
        if cs is None:
            details = obs.get("details") or {}
            cs = details.get("character_sheet") or details.get("character")

        if isinstance(cs, dict):
            existing = card.get("character_sheet")
            if not isinstance(existing, dict):
                existing = {}
            # shallow merge is fine; the ring + subsystems are nested dicts already
            existing.update(cs)
            card["character_sheet"] = existing

        # tests/checks
        tests = None

        # 1) modern path: tests at top level
        if "tests" in obs:
            tests = obs.get("tests")

        # 2) template path: tests nested under details.tests
        if tests is None:
            details = obs.get("details") or {}
            if isinstance(details, dict) and "tests" in details:
                tests = details.get("tests")

        if tests:
            # normalize to a list so we can slice safely
            if isinstance(tests, dict):
                tests_list = list(tests.values())
            else:
                tests_list = list(tests)

            card["checks"]["last"] = tests_list[:50]

            worst = "ok"
            for t in card["checks"]["last"]:
                s = (t.get("status") or "ok").lower()
                if s == "error":
                    worst = "error"
                    break
                if s == "warn" and worst == "ok":
                    worst = "warn"
            card["checks"]["worst"] = worst

        # evolution tick
        if "evolution" in (obs.get("kind", "") or "") or "evolution" in (obs.get("opcode", "") or ""):
            card["evolution"]["ticks"] = 1 + int(card["evolution"].get("ticks", 0))

        # coalesced emit for this actor
        self._schedule_emit(actor, card)

        # ----- 2) Directory path (what the Status GUI left pane uses) -----
        # This is intentionally much lighter weight.
        rec = self._orgs.get(actor, {
            "name": actor,
            "plane": None,
            "channel": None,
            "version": None,
            "status": "unknown",
            "last_seen": None,
            "role": None,
            "purpose": None,
            "bugs": [],
            "counters": {},
        })

        plane   = obs.get("plane")   or card.get("plane")   or rec.get("plane")
        channel = obs.get("channel") or card.get("channel") or rec.get("channel")
        status  = (obs.get("status") or rec.get("status") or "unknown").lower()
        if status not in {"ok", "warn", "error", "info"}:
            status = "unknown"

        rec["plane"]   = plane
        rec["channel"] = channel
        rec["version"] = (
            obs.get("actor_version")
            or obs.get("fairy_version")
            or rec.get("version")
        )
        rec["status"]    = status
        rec["last_seen"] = self._now_iso()
        # opportunistically capture purpose/role if provided
        rec["purpose"] = rec.get("purpose") or obs.get("purpose")
        rec["role"]    = rec.get("role")    or obs.get("role")

        # basic bug feed when card health is non-ok
        if status in {"warn", "error"}:
            bug = {
                "when": rec["last_seen"],
                "from": actor,
                "event": obs.get("kind") or obs.get("event"),
                "status": status,
                "details": {
                    k: v for k, v in (obs.get("details") or {}).items()
                    if k not in {"ts", "time", "nonce"}
                },
            }
            rec.setdefault("bugs", []).append(bug)
            self._push_bug(bug)

        self._orgs[actor] = rec


    def _card_sig(self, card: dict) -> Optional[str]:
        # share the same normalizer used by _stable_sig / GUI frames: ignore volatile fields
        dropped = {"ts", "time", "nonce", "_seq"}
        def _norm(x):
            if isinstance(x, dict):
                return {k: _norm(v) for k, v in x.items() if k not in dropped}
            if isinstance(x, list):
                return [_norm(v) for v in x]
            return x
        try:
            raw = json.dumps(_norm(card), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            return hashlib.sha256(raw).hexdigest()
        except Exception:
            return None

    # --- [ADD: throttle + coalesced emit] ---
    def _schedule_emit(self, actor: str, card: dict):
        with self._emit_lock:
            now = time.time()
            due = self._throttle_due.get(actor, 0.0)
            rec = self._cards.setdefault(actor, {})
            rec["card"] = card
            if now >= due:
                self._throttle_due[actor] = now + self._throttle_sec
                # prefer a timer; if threading not available, fall back to immediate
                try:
                    t = threading.Timer(self._throttle_sec, lambda: self._emit_if_changed(actor))
                    t.daemon = True
                    t.start()
                except Exception:
                    self._emit_if_changed(actor)

    def _emit_if_changed(self, actor: str):
        with self._emit_lock:
            rec = self._cards.get(actor) or {}
            card = rec.get("card") or rec
            if not card:
                return
            card["ts"] = time.time()
            sha = self._card_sig(card)
            if not sha:
                return
            if rec.get("sha") == sha:
                return  # no change
            rec["sha"] = sha
            self._cards[actor] = rec

        pkt = {"opcode": "AKASHIC_CARD_UPSERT", "payload": {"actor": actor, "sha": sha, "card": card}}

        # Primary: Librarian's channel per 0.0.7 (e.g., "Akashic_Records")
        try:
            self.post.route(self.ACTOR_CHANNEL, pkt)
        except Exception:
            pass

        # Optional: directory echo for registry UIs
        try:
            if hasattr(self.post, "to_DIRECTORY"):
                self.post.to_DIRECTORY({"opcode": "AKASHIC_CARD_UPSERT", "payload": {"actor": actor, "sha": sha}})
        except Exception:
            pass

        # Mirror to telemetry so dashboards without the custom lane still see it
        try:
            self.post.to_TELEMETRY(pkt)
        except Exception:
            pass

        # NEW: notify local listeners (GUI, tools) without polling
        try:
            self._signal("CARD_CHANGED", {"actor": actor, "card": card, "sha": sha})
        except Exception:
            pass

        # OPTIONAL: if you want the GUI frame to update whenever a card changes, nudge it here.
        # (It will still only emit if the GUI frame's normalized signature changed.)
        try:
            self.intent_emit_gui_if_changed({})
        except Exception:
            pass


    # --- [ADD: explicit test intents] ---
    def intent_card_upsert(self, payload: dict):
        a = (payload or {}).get("actor"); patch = (payload or {}).get("patch") or {}
        if not a: return {"ok": False, "error": "actor required"}
        card = (self._cards.get(a) or {}).get("card") or self._new_card(a)
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(card.get(k), dict):
                card[k].update(v)
            else:
                card[k] = v
        self._schedule_emit(a, card)
        return {"ok": True}

    def intent_card_remove(self, payload: dict):
        a = (payload or {}).get("actor")
        if not a: return {"ok": False, "error": "actor required"}
        self._cards.pop(a, None)
        pkt = {"opcode": "AKASHIC_CARD_REMOVE", "payload": {"actor": a}}
        try: self.post.route(self.ACTOR_CHANNEL, pkt)
        except Exception: pass
        try: self.post.to_TELEMETRY(pkt)
        except Exception: pass
        return {"ok": True}

    def _bootstrap_orgs_from_directory(self) -> None:
        """
        Fallback seeding for _orgs.

        If no organs have been seen via telemetry yet, pull the current
        Directory registry and synthesize lightweight status records so
        the GUI/status views have something to render immediately.
        """
        # Do nothing if we already have any actors.
        if self._orgs:
            return

        try:
            use_intent = getattr(self.post, "use_intent", None)
            if not callable(use_intent):
                return

            # OUTER: post hub result wrapper from DirectoryOrganFairy.Socks
            outer = use_intent("DirectoryOrganFairy.Socks", "registry", {})
        except Exception:
            return

        if not isinstance(outer, dict) or not outer.get("ok"):
            return

        # INNER: actual Directory response
        inner = outer.get("result") or {}
        if not isinstance(inner, dict) or not inner.get("ok"):
            return

        registry = inner.get("registry") or {}
        if not isinstance(registry, dict):
            return

        now_iso = self._now_iso()

        for actor, contract in registry.items():
            if not isinstance(contract, dict):
                continue

            rec = self._orgs.get(actor, {
                "name": actor,
                "plane": None,
                "channel": None,
                "version": None,
                "status": "unknown",
                "last_seen": None,
                "role": None,
                "purpose": None,
                "bugs": [],
                "counters": {},
            })

            rec["plane"]   = contract.get("plane")   or rec.get("plane")   or "unknown"
            rec["channel"] = contract.get("channel") or rec.get("channel") or "unknown"
            rec["version"] = contract.get("actor_version") or rec.get("version")
            rec["role"]    = ", ".join(contract.get("roles") or []) or rec.get("role")
            rec["purpose"] = contract.get("purpose") or rec.get("purpose")

            # give actors at least one heartbeat if they've never been seen
            rec["last_seen"] = rec.get("last_seen") or now_iso

            self._orgs[actor] = rec
            cc = (contract.get("contract_check") or {})
            cstate = (cc.get("state") or "").lower()

            # Only overwrite status if the contract check is meaningful
            if cstate in {"ok", "warn", "error", "info"}:
                rec["status"] = cstate
            # give actors at least one heartbeat if they've never been seen
            rec["last_seen"] = rec.get("last_seen") or now_iso
            self._orgs[actor] = rec

    def _bootstrap_orgs_from_citizens(self) -> None:
        """
        Fallback seeding for _orgs using the organ template's in-process
        citizen registry (_CITIZEN_OBJECTS).

        This runs only when _orgs is empty, so once telemetry / scribe
        packets start enriching state, we don't stomp on that.
        """
        # if we already have anything, don't touch it
        if getattr(self, "_orgs", None):
            if len(self._orgs) > 0:
                return

        # reach into the shared template's citizen registry
        try:
            citizens = getattr(_template, "_CITIZEN_OBJECTS", {})
        except Exception:
            return

        if not isinstance(citizens, dict) or not citizens:
            return

        now_iso = self._now_iso()

        for actor_name, fairy in citizens.items():
            # skip weird entries
            if not isinstance(actor_name, str):
                continue
            if fairy is None:
                continue

            # base record
            rec = self._orgs.get(actor_name, {
                "name": getattr(fairy, "ACTOR_NAME", actor_name),
                "plane": getattr(fairy, "ACTOR_PLANE", "unknown"),
                "channel": getattr(fairy, "ACTOR_CHANNEL", "unknown"),
                "version": getattr(fairy, "ACTOR_VERSION", ""),
                "status": "ok",          # we at least know it's alive
                "last_seen": now_iso,    # first heartbeat
                "role": getattr(fairy, "ROLE", None),
                "purpose": getattr(fairy, "PURPOSE", None),
                "bugs": [],
                "counters": {},
            })

            # gently merge any existing fields (if telemetry later added some)
            if "plane" not in rec or not rec["plane"]:
                rec["plane"] = getattr(fairy, "ACTOR_PLANE", "unknown")
            if "channel" not in rec or not rec["channel"]:
                rec["channel"] = getattr(fairy, "ACTOR_CHANNEL", "unknown")
            if "version" not in rec or not rec["version"]:
                rec["version"] = getattr(fairy, "ACTOR_VERSION", "")

            self._orgs[actor_name] = rec

    def intent_ak_library_feed(self, payload: dict) -> dict:
        """
        Akashic Library Feed:
        1) Refresh our local directory view from Directory.
        2) Identify actors that need forensic attention (e.g. contract errors).
        3) Task the Forensic Scribe to gather focused telemetry / cards.
        """
        # 1) Make sure _orgs is in sync with Directory (and citizens fallback)
        self._bootstrap_orgs_from_directory()
        self._bootstrap_orgs_from_citizens()

        # 2) Choose which actors to send to the Scribe
        want_states = set((payload or {}).get("states") or ["error", "warn"])
        max_actors  = int((payload or {}).get("max_actors") or 32)

        targets: list[str] = []
        for actor, rec in sorted(self._orgs.items()):
            st = (rec.get("status") or "unknown").lower()
            if st in want_states:
                targets.append(actor)
            if len(targets) >= max_actors:
                break

        if not targets:
            return {
                "ok": True,
                "actors": [],
                "note": "no actors matched states filter",
            }

        # 3) Task the Forensic Scribe (you can tweak organ / intent names)
        try:
            use_intent = getattr(self.post, "use_intent", None)
            if not callable(use_intent):
                return {"ok": False, "error": "no_use_intent", "actors": targets}

            scribe_payload = {
                "actors": targets,
                "time_window_sec": int((payload or {}).get("time_window_sec") or 3600),
                "reason": "ak_library_feed",
            }

            # This assumes your scribe implements intent_task_audit
            res = use_intent("ForensicScribeFairy", "task_audit", scribe_payload)

            print(f"[LIBRARIAN:AK_FEED] tasked scribe for {len(targets)} actors; states={list(want_states)}")

            return {
                "ok": True,
                "actors": targets,
                "scribe_ack": res,
            }

        except Exception as e:
            return {"ok": False, "error": str(e), "actors": targets}


    def intent_status_directory(self, payload: dict) -> dict:
        """
        Return a plane → directory mapping summarizing known actors.

        This is intentionally lightweight: one row per actor with basic
        identity + status, suitable for building a plane/roster view.
        """
        # 1) Seed from Directory registry if we know nothing yet
        self._bootstrap_orgs_from_directory()
        # 2) Fallback: if Directory isn't available, seed from citizen registry
        self._bootstrap_orgs_from_citizens()

        # ⭐ DEBUG: how many actors the Librarian knows about
        print(f"[LIBRARIAN] status_directory called; _orgs has {len(self._orgs)} actors")

        try:
            plane_filter  = (payload or {}).get("plane")
            status_filter = (payload or {}).get("status")

            planes: dict[str, dict] = {}

            # _orgs is maintained by intent_ingest_scribe_packet / _merge_observation
            for actor, rec in sorted(self._orgs.items()):
                plane = rec.get("plane") or "unknown"
                if plane_filter and plane != plane_filter:
                    continue

                status = (rec.get("status") or "unknown").lower()
                if status not in {"ok", "warn", "error", "info"}:
                    status = "unknown"
                if status_filter and status != status_filter:
                    continue

                entry = {
                    "actor": actor,
                    "name": rec.get("name") or actor,
                    "plane": plane,
                    "channel": rec.get("channel") or "unknown",
                    "status": status,
                    "role": rec.get("role") or rec.get("purpose") or "organ",
                    "version": rec.get("version") or "",
                    "last_seen": rec.get("last_seen"),
                    "bugs": len(rec.get("bugs") or []),
                    "counters": rec.get("counters") or {},
                    "has_card": actor in self._cards,
                }

                bucket = planes.setdefault(plane, {"directory": [], "summary": {}})
                bucket["directory"].append(entry)

            # plane-level summaries (how many ok/warn/error/etc.)
            for plane, pdata in planes.items():
                counts = {"ok": 0, "warn": 0, "error": 0, "info": 0, "unknown": 0}
                for ent in pdata["directory"]:
                    st = ent["status"]
                    if st not in counts:
                        st = "unknown"
                    counts[st] += 1

                # "worst" status wins: error > warn > ok > info > unknown
                worst = "unknown"
                for candidate in ("error", "warn", "ok", "info"):
                    if counts[candidate] > 0:
                        worst = candidate
                        break

                pdata["summary"] = {
                    "count": len(pdata["directory"]),
                    "status": worst,
                    "states": counts,
                }

            return {
                "ok": True,
                "ts": self._now_iso(),
                "planes": planes,
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}


    def intent_status_card(self, payload: dict) -> dict:
        """
        Return the full Akashic card for one actor.

        This pulls the card as built by Forensic/Librarian ingestion, falls
        back to a skeleton if needed, and adds a compact `audit` summary
        derived from forensic `checks` when available.

        Option 1 extension:
        - If no character_sheet is present yet, ask the actor itself via
          the shared Organ Template intent: "status_sheet".
        """
        actor = (payload or {}).get("actor")
        if not actor:
            return {"ok": False, "error": "missing_actor"}

        try:
            # directory observation record (may be None)
            obs = self._orgs.get(actor) or {}

            # cards are usually stored as {"card": {...}, "sha": "..."}
            rec = self._cards.get(actor) or {}
            if isinstance(rec, dict) and ("card" in rec or "sha" in rec):
                card = rec.get("card") or {}
            else:
                # support legacy shape where the card itself was stored directly
                card = rec if isinstance(rec, dict) else {}

            # If there is no card built yet, make a skeleton from directory obs
            if not card:
                card = {
                    "actor": actor,
                    "plane":   obs.get("plane", "unknown"),
                    "channel": obs.get("channel", "unknown"),
                    "status":  obs.get("status", "unknown"),
                    "identity": {
                        "purpose": obs.get("purpose", ""),
                        "mantra":  obs.get("mantra",  ""),
                        "lore":    obs.get("lore",    ""),
                    },
                    "blueprint": {
                        # directory record uses "version"; fall back to that
                        "version":          obs.get("version", ""),
                        "template_version": obs.get("template_version", ""),
                    },
                    "checks": {
                        "worst": obs.get("status", "unknown"),
                        "last": [],
                    },
                    "shadow_tests": {},
                    "activity": {},
                    "lore": obs.get("lore", ""),
                }
            else:
                # Make sure some basic identity fields are present even when
                # the card came purely from Forensic/other sources.
                card.setdefault("actor", actor)
                card.setdefault("plane",   obs.get("plane",   card.get("plane",   "unknown")))
                card.setdefault("channel", obs.get("channel", card.get("channel", "unknown")))
                card.setdefault("status",  obs.get("status",  card.get("status",  "unknown")))
                ident = card.setdefault("identity", {})
                ident.setdefault("purpose", obs.get("purpose", ident.get("purpose", "")))
                ident.setdefault("mantra",  obs.get("mantra",  ident.get("mantra",  "")))
                ident.setdefault("lore",    obs.get("lore",    ident.get("lore",    "")))

            # ------------------------------------------------------------------
            # Lazy character_sheet fetch (Option 1)
            # If we don't yet have a character_sheet, ask the actor itself via
            # the Organ Template's "status_sheet" intent. This uses the shared
            # build_status_sheet() / fairy_status_sheet logic under the hood.
            # ------------------------------------------------------------------
            cs = card.get("character_sheet")
            if not isinstance(cs, dict):
                print(f"[LIBRARIAN] status_card: requesting status_sheet from {actor!r}")
                try:
                    res = self.post.use_intent(
                        actor,
                        "status_sheet",
                        {"source": "AkashicRecordsLibrarianFairy"},
                    )
                except Exception as e:
                    print(f"[LIBRARIAN] status_card: status_sheet call to {actor!r} raised: {e!r}")
                    res = None

                print(f"[LIBRARIAN] status_card: status_sheet response for {actor!r}: {res!r}")

                if isinstance(res, dict) and res.get("ok"):
                    # sheet can be either:
                    #   {"ok": True, "sheet": {...}}
                    # or:
                    #   {"ok": True, "result": {"ok": True, "sheet": {...}}}
                    # or:
                    #   {"ok": True, "result": {"ok": True, "character_sheet": {...}}}
                    sheet = None

                    # direct form
                    if isinstance(res.get("sheet"), dict):
                        sheet = res.get("sheet")
                    else:
                        inner = res.get("result")
                        if isinstance(inner, dict):
                            if isinstance(inner.get("sheet"), dict):
                                sheet = inner.get("sheet")
                            elif isinstance(inner.get("character_sheet"), dict):
                                sheet = inner.get("character_sheet")

                    if isinstance(sheet, dict):
                        card["character_sheet"] = sheet
                        print(f"[LIBRARIAN] status_card: character_sheet attached for {actor!r}")
                            # --- Bridge: character_sheet.shadow.tests -> card.checks ---------
                    shadow_panel = (sheet.get("shadow") or {}) if isinstance(sheet, dict) else {}
                    sheet_tests = shadow_panel.get("tests") or []

                    if sheet_tests:
                        checks = card.setdefault("checks", {})
                        existing = list(checks.get("last") or [])

                        # If we had no checks yet, just take the sheet tests;
                        # otherwise extend and keep the most recent 50.
                        if not existing:
                            existing = list(sheet_tests)
                        else:
                            existing.extend(sheet_tests)

                        checks["last"] = existing[-50:]

                        # Compute worst with a simple severity ladder
                        severity = {"ok": 0, "info": 0, "warn": 1, "warning": 1, "error": 2, "fail": 2}
                        worst = checks.get("worst") or "ok"
                        for t in sheet_tests:
                            s = str(
                                t.get("status")
                                or t.get("state")
                                or ("ok" if t.get("ok", True) else "error")
                            ).lower()
                            if s == "warning":
                                s = "warn"
                            if s == "fail":
                                s = "error"
                            if severity.get(s, 0) > severity.get(worst, 0):
                                worst = s

                        checks["worst"] = worst
                        card["checks"] = checks

                        # Also keep a mirror in shadow_tests for the GUI
                        shadow_tests_panel = card.setdefault("shadow_tests", {})
                        shadow_tests_panel["tests"] = sheet_tests
                        shadow_tests_panel["worst"] = worst
                        shadow_tests_panel["non_ok"] = [
                            t for t in sheet_tests
                            if str(t.get("status", "ok")).lower() not in ("ok", "info")
                        ]

                        # Cache back into _cards so future calls don't need
                        # another round-trip to the organ.
                        try:
                            rec = self._cards.get(actor)
                            if isinstance(rec, dict):
                                rec_card = rec.get("card")
                                if isinstance(rec_card, dict):
                                    rec["card"] = card
                                else:
                                    rec["card"] = card
                            else:
                                self._cards[actor] = {"card": card}
                        except Exception as cache_err:
                            print(f"[LIBRARIAN] status_card: cache update failed for {actor!r}: {cache_err!r}")
            # ------------------------------------------------------------------

            # ---- Add a compact audit summary from forensic checks, if present ----
            # ensure we are mutating the card's checks dict, not a throwaway copy
            checks = card.setdefault("checks", {})
            tests_list = list(checks.get("last") or [])
            worst = (checks.get("worst") or "").lower() or None

            # If worst wasn't computed (older cards), derive it from the tests list
            if tests_list and not worst:
                w = "ok"
                for t in tests_list:
                    s = str((t.get("status") or "ok")).lower()
                    if s == "error":
                        w = "error"
                        break
                    if s == "warn" and w == "ok":
                        w = "warn"
                worst = w
                checks["worst"] = worst

            # Mirror into a shadow_tests panel for GUI readers
            if tests_list:
                shadow = card.setdefault("shadow_tests", {})
                shadow["tests"] = tests_list
                shadow["non_ok"] = [
                    t for t in tests_list
                    if str((t.get("status") or "ok")).lower() not in ("ok", "info")
                ]
                shadow["worst"] = worst or "ok"

            if worst:
                audit = card.setdefault("audit", {})
                audit["status"] = worst
                if tests_list:
                    last = tests_list[-1]
                    audit["last_event"] = last
                    audit["hint"] = f"{last.get('event', '?')} ({worst}) at ts={last.get('ts')}"

            return {"ok": True, "card": card}

        except Exception as e:
            print(f"[LIBRARIAN] status_card: unexpected error for {actor!r}: {e!r}")
            return {"ok": False, "error": str(e)}


    def intent_fairy_autobiographies(self, payload: dict) -> dict:
        """
        Return autobiography history for one or all fairies.

        Args:
            payload: {
                "actor": str (optional) - specific fairy name, or None for all
                "limit": int (optional) - max entries per fairy (default 10)
            }

        Returns:
            {
                "ok": True,
                "autobiographies": {
                    "FairyName": [
                        {"ts": float, "sheet": {...}},
                        ...
                    ],
                    ...
                }
            }
        """
        actor = (payload or {}).get("actor")
        limit = (payload or {}).get("limit", 10)

        # Ensure _autobiographies exists
        if not hasattr(self, "_autobiographies"):
            self._autobiographies = {}

        try:
            if actor:
                # Return history for one fairy
                history = self._autobiographies.get(actor, [])
                return {
                    "ok": True,
                    "autobiographies": {
                        actor: history[-limit:] if limit else history
                    }
                }
            else:
                # Return history for all fairies
                result = {}
                for fairy_name, history in self._autobiographies.items():
                    result[fairy_name] = history[-limit:] if limit else history
                return {
                    "ok": True,
                    "autobiographies": result,
                    "fairy_count": len(result),
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _intent_fairy_autobiographies(self, payload: dict) -> dict:
        """Cross-organ shim for intent_fairy_autobiographies."""
        return self.intent_fairy_autobiographies(payload or {})



    # --- Cross-organ intent shims for Directory/GUI ------------------------
    # These allow central nervous `post.use_intent(actor, intent, payload)`
    # to reach our richer status intents without changing the template's
    # MyOrganFairy.use_intent contract.

    def _intent_status_directory(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-organ shim → intent_status_directory."""
        return self.intent_status_directory(payload or {})

    def _intent_status_card(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-organ shim → intent_status_card."""
        return self.intent_status_card(payload or {})

# ====================== end Akashic Records Librarian ======================

    def _on_heartbeat_pulse(self, msg):
        """Handle heartbeat pulse."""
        pass  # Placeholder for tick logic
