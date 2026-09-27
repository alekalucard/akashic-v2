from __future__ import annotations

import os, sys, glob, time, types, uuid, json
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

class SRMReplayShadowFairy(_template.MyOrganShadow):
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
    SHADOW_NAME = "SRMReplayShadowFairy"
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


class SRMReplayFairy(_template.MyOrganFairy):
    ACTOR_NAME = "SRMReplayFairy"  # Wrapped by P10_Memory/SRMReplayFairy/fairy.py
    ACTOR_VERSION = "2.2.0"  # mirrors upstream replay actor version
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory"
    ORGAN_LEVEL = False
    PURPOSE = "Broker memory recall to Somatic (P20) and Cognition (P30); allow symbolic replay in non-wake phases."
    MANTRA = "Recall is for feeling too."
    LORE = "The dream-ferryman who rows memories between feeling and thought."

    # ── character sheet / directive ring ─────────────────────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Replay",
        "depth_scaling": "1..3",
        "traits": [
            "SRM_Replay_Adapter",
            "Memory_Broker",
            "Helix_Strand_C",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "SRM_Replay_Adapter",
        "domains": [
            "Memory",
            "SRM",
            "Replay",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Recall_Brokerage",
            "Phase_Aware_Routing",
            "Helix_Card_Emission",
            "Somatic_Cognition_Bridge",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "Replay_Query",
            "Replay_Result",
            "Helix_Card",
        ],
        "field": [
            "TripleHelix_Memory",
            "Replay_Sessions",
            "Phase_Topology",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Honor_Stored_Memory",
            "No_Fabricated_Recall",
        ],
        "growth": [
            "Refine_Query_Strategy",
            "Improve_Affect_Mapping",
        ],
        "precision": [
            "Deterministic_Scoring",
            "Phase_Safe_Routing",
        ],
    }

    SUBSYSTEM_STATUS = {
        "recall_adapter": {
            "state": "active",
            "notes": "Resolves SRM recall interface (citizen or injected) and queries it.",
            "tests": [],
        },
        "replay_router": {
            "state": "active",
            "notes": "Routes replay summaries to Somatic (P20) and Cognition (P30).",
            "tests": [],
        },
        "phase_state": {
            "state": "active",
            "notes": "Tracks current phase (wake/dream/etc) and toggles symbolic vs literal replay.",
            "tests": [],
        },
    }

    SHADOW_CLASS = SRMReplayShadowFairy
    AUTO_INJECT_IMPORTS = True  # template QoL

    # runtime state
    def on_boot(self):
        import time as _t, uuid as _uuid

        # ═══════════════════════════════════════════════════════════════════════════
        # CRITICAL: Call template's on_boot() FIRST for proper registration!
        # This connects us to: Hub lanes, Identity echo, Wake subs, FairyCitizens
        # ═══════════════════════════════════════════════════════════════════════════
        try:
            super().on_boot()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] super().on_boot() error: {e}")

        # MINIMAL BOOT - just set phase, all postal calls moved to background thread
        self.current_phase = "wake"
        print(f"[{self.ACTOR_NAME}] FAIRY on_boot: minimal boot complete", flush=True)

        # emit a STATUS_EVENT with character sheet so Scribe/Librarian/GUI can ingest it
        try:
            self._boot_id = getattr(self, "_boot_id", None) or _uuid.uuid4().hex
            env = {
                "event": "STATUS_EVENT",
                "status": "info",
                "title": "SRM Replay Adapter online",
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
                "ts": _t.time(),
            }
            pkt = {"opcode": "STATUS_EVENT", "payload": env}
            try:
                self.post.to_TRACER(pkt)
            except Exception:
                pass
            try:
                self.post.to_TELEMETRY(pkt)
            except Exception:
                pass
        except Exception:
            # never crash boot on status emission
            pass
        print(f"[{self.ACTOR_NAME}] FAIRY CODE END: returning from on_boot", flush=True)

    # ---- helpers ------------------------------------------------------

    def _helix_for_top(self, *, query: dict, top: tuple, phase: str) -> dict:
        # top: (score, mem_id, rec, meta) from SRMRecall
        score, mem_id, rec, meta = top
        rec = rec or {}
        meta = meta or {}
        ptr = meta.get("ptr")

        def _sem(rec):
            what = (rec.get("what") or "").lower()
            mt = (rec.get("media_type") or "").lower()
            chs = " ".join(rec.get("channels", [])).lower()
            if any(w in what for w in ("profile", "persona", "me", "diary")):
                return 1
            if any(w in what for w in ("chem", "somatic", "sleep", "affect")) or "bio" in mt:
                return 2
            if any(w in chs for w in ("chat", "social", "discourse", "comment")):
                return 3
            return 4

        def _aff(rec):
            a = 0.0
            if rec.get("priority") in ("high", "urgent"):
                a += 0.4
            if (rec.get("media_type") or "").startswith("text/"):
                a += 0.1
            if rec.get("error"):
                a -= 0.3
            return max(-1.0, min(1.0, a))

        sem = _sem(rec)
        pos = _aff(rec)
        neg = -abs(pos)
        six_w = {
            "who": rec.get("who"),
            "what": rec.get("what"),
            "when": rec.get("ts"),
            "where": rec.get("where"),
            "why": query.get("intent") or rec.get("why"),
            "how": "memory.replay",
        }
        helix = {
            "L": {
                "addr": {"affect": pos, "sem_domain": sem, "depth": 0},
                "concept": rec.get("concept") or "replay",
                "w": six_w,
            },
            "R": {
                "addr": {"affect": neg, "sem_domain": sem, "depth": 0},
                "concept": rec.get("concept") or "replay",
                "w": six_w,
            },
            "C": {"affect": "phase:" + phase, "energy": abs(pos), "coherence": 0.78},
        }
        return {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "helix": helix,
            "ptr": ptr,
            "tags": list({"memory", "p10", "replay", rec.get("media_type") or "unknown"}),
        }

    def _get_recall_agent(self):
        """
        Resolve the recall interface without hard-coupling:
          - If a sibling citizen registered as 'srm_recall_fairy', use its .recall
          - Else look for an injected attr self.srm_recall with .recall
          - Else raise a clear error (template will diary INTENT_FAIL)
        """
        # try hub registry if available
        try:
            hub_lookup = getattr(self, "_hub_lookup", None)
            if callable(hub_lookup):
                c = hub_lookup("srm_recall_fairy") or {}
                fn = ((c.get("adapter") or {}) if isinstance(c, dict) else {}).get("recall")
                if callable(fn):
                    return fn
        except Exception:
            pass
        # direct attribute (user may wire this before calling intent)
        srm = getattr(self, "srm_recall", None)
        if srm and hasattr(srm, "recall") and callable(srm.recall):
            return srm.recall
        raise RuntimeError(
            "No SRM recall interface available (need citizen 'srm_recall_fairy' or self.srm_recall.recall)"
        )

    # ---- Intents ------------------------------------------------------

    def _intent_phase_update(self, payload: dict) -> dict:
        phase = (payload or {}).get("phase") or "wake"
        self.current_phase = str(phase)
        try:
            self.post.to_TRACER({"opcode": "PHASE_UPDATE", "payload": {"phase": self.current_phase}})
            self.post.to_PLAN(
                {
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {"chemical": "serotonin", "delta": +0.2, "reason": "phase_update"},
                }
            )
        except Exception:
            pass
        return {"ok": True, "phase": self.current_phase}

    def _intent_replay(self, payload: dict) -> dict:
        """
        payload: {
          query: {...}, max_results: int
        }
        Returns: { ok, results: [ {memory_id, score, record, meta, mode}... ], top_card? }
        """
        q = (payload or {}).get("query") or {}
        k = int((payload or {}).get("max_results") or 5)
        recall = self._get_recall_agent()

        # ask SRM recall
        results_raw = list(recall(q, max_results=k) or [])
        results = []
        for score, mem_id, rec, meta in results_raw:
            results.append(
                {
                    "memory_id": mem_id,
                    "score": float(score),
                    "record": rec or {},
                    "meta": meta or {},
                    "mode": "symbolic_ok" if getattr(self, "current_phase", "wake") != "wake" else "literal",
                }
            )

        # bus echoes
        try:
            self.post.to_SOMATIC(
                {
                    "opcode": "MEMORY_REPLAY",
                    "payload": {"query": q, "count": len(results), "phase": getattr(self, "current_phase", "wake")},
                }
            )
            self.post.to_TRACER({"opcode": "REPLAY_SUMMARY", "payload": {"count": len(results)}})
            self.post.to_PLAN(
                {
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {"chemical": "dopamine", "delta": +0.3, "reason": "replay_ok"},
                }
            )
        except Exception:
            pass

        # helix card for top item → diary + MEMORY echo
        top_card = None
        if results_raw:
            top_card = self._helix_for_top(query=q, top=results_raw[0], phase=getattr(self, "current_phase", "wake"))
            try:
                self.post.to_MEMORY({"kind": "replay.top", "card": top_card, "query": q})
            except Exception:
                pass

        return {"ok": True, "results": results, "top_card": top_card}


# ───────────────────────────── SRM Dual-Path Helpers ─────────────────────────────


def _safe_write_json(path: str, payload: "Any") -> bool:
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
        post.to_MEMORY(
            {
                "opcode": "SRM_INTAKE_WRITE",
                "payload": {"kind": kind, "path": fpath, "meta": meta or {}, "data": data, "write_ok": ok},
            }
        )
    except Exception:
        pass

    return {"path": fpath, "write_ok": ok, "meta": meta or {}}
