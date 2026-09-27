from __future__ import annotations

import os, sys, glob, time, types, uuid, json
from collections import deque
from typing import Optional, Any, Dict
import importlib.util, importlib.machinery

# Import V2 Fairy base class
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    _HAS_FAIRY = True
except ImportError:
    _HAS_FAIRY = False
    Fairy = object

def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload dict from message (handles TensorEnvelope or dict)."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    else:
        return {"raw": message}

# --- Per-clone shadow (wraps template's shadow behaviors, no rewiring) -------

class SleepWaveConductorShadowFairy(Fairy):
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
    SHADOW_NAME = "SleepWaveConductorShadowFairy"
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
        "domain":    "Somatic",    # per-organ you can override on subclass
        "role":      "worker",
        "name":      "lexi",
        "every_sec": 20.0,
    }

    def __init__(self, actor, interval_sec: float = 30.0, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
        else:
            self.post = fabric
        self.actor = actor
        self.interval_sec = interval_sec
        self._lane_seen_ts = time.time()
        self._last_snapshot_ts = 0.0
        self._last_sim_light_ts = 0.0
        self._last_sim_deep_ts  = 0.0
        self._lane_tail = deque(maxlen=10)  # recent "lane seen" stamps

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
        # V2 migration: RegistrationLib removed, registration handled by fabric
        pass

    # helpers to track deep cadence
    def _last_deep_ts(self):
        return getattr(self, "__deep_ts", 0.0)

    def _touch_deep(self, t: float):
        setattr(self, "__deep_ts", t)

    # --- evolution sim (self-contained) ----------
    def _evolution_sim_tick(self, kind: str = "light", n: int = 1):
        """
        Send synthetic evolution observations (postal-first).
        V2 migration: _dual_path_srm_intake removed, using postal route only.
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

# ─────────────────────────────────────────────────────────────────────────────
# APPEND-ONLY ORGAN — P20 Sleep Wave Conductor (uses template shadow unchanged)
# Lineage: P20 / sleep_wave_conductor.Ver.2.1 (parity-upgraded)
# Template: 0.0.7 — do not modify the template body above; mailbox-only I/O.
# Philosophy: “Rhythm makes recall feel real.”
# ─────────────────────────────────────────────────────────────────────────────

class SleepWaveConductorFairy(Fairy):
    # Identity
    ACTOR_NAME    = "SleepWaveConductorFairy"
    ACTOR_VERSION = "2.1.1"   # worker-on-template edition
    ACTOR_PLANE   = "P20"
    ACTOR_CHANNEL = "somatic_sleep_conductor"
    ORGAN_LEVEL = False
    
    PURPOSE = "Publish soma phase (wake, daydream, sleep) as rhythmic waves."
    MANTRA  = "Rhythm makes recall feel real."
    LORE    = (
        "Keeps time for the body: wake → daydream → sleep (or as directed). "
        "Each phase emits helpful hints and gentle chemistry cues so recall feels embodied."
    )

    #  Directive ring for the character sheet
    DIRECTIVE_ACTIVATION = {
        "mode": "Resonance",
        "depth_scaling": "1..2",
        "traits": ["Phase_Conduction", "Circadian_Modulation"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Sleep_Wave_Conductor",
        "domains": ["Somatic", "Chemistry", "Cognition"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Phase_Rhythm",
            "Recall_Scaffolding",
            "Dream_Reverie_Orchestration",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["PHASE_NOTE", "DAYDREAM_SUGGESTION", "REVERIE_NOTE"],
        "field": ["Body_State_Modulation"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Gentle_Rhythm", "Safety_First"],
        "growth": ["Sleep_Hygiene", "Emotional_Integration"],
    }

    SUBSYSTEM_STATUS = {
        "somatic": {
            "state": "rhythmic",
            "notes": "Publishes SOMATIC_PHASE with hints for recall and restraint.",
            "tests": [],
        },
        "cognition": {
            "state": "hinting",
            "notes": "Feeds DAYDREAM_SUGGESTION during daydream/sleep when enabled.",
            "tests": [],
        },
        "memory": {
            "state": "logging",
            "notes": "Writes PHASE_NOTE and REVERIE_NOTE breadcrumbs tied to phases.",
            "tests": [],
        },
    }
    # Use the template’s shadow unchanged
    SHADOW_CLASS = SleepWaveConductorShadowFairy

    # Phase set & defaults
    PHASES = ("wake", "daydream", "sleep")

    # Cadence (actor-local; template still runs its own harness)
    HEALTH_TICK_SEC = 30.0

    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
            # self.post is set by parent Fairy.__init__
        else:
            # Fallback when fairy_template import failed
            self.post = fabric
            self.post = fabric

    # ───────────────────────── lifecycle ─────────────────────────
    def on_boot(self):
        # IMPORTANT: Call super() to trigger HeartbeatMixin auto-start
        if _HAS_FAIRY:
            super().on_boot()

        # state
        self._boot_ts        = time.time()
        self._last_emit_ts   = 0.0
        self._last_health_ts = 0.0

        # phase engine
        self._cycle: list[str] = list(self.PHASES)
        self._phase_idx        = 0
        self._override: dict | None = None  # {"phase": str, "until": float|None}
        self._period_sec       = 90.0
        self._jitter_frac      = 0.10  # 0..0.5

        # initial affect/somatic snapshot for status sheet (baseline wake)
        now = self._boot_ts
        self.AFFECT_STATE = {
            "mood": "neutral",
            "valence": 0.1,
            "arousal": 0.4,
            "tags": ["phase:wake"],
            "tone": "wake",
            "energy": 0.4,
            "coherence": 0.7,
            "chem_preset": "baseline",
            "intent": "support_recall",
            "ts": now,
            "source": self.ACTOR_NAME,
        }
        self.SOMATIC_STATE = {
            "body_type": "fairy",
            "posture": "neutral",
            "motion": "idle",
            "energy": 0.4,
            "anchor_id": None,
            "notes": "baseline wake phase",
            "last_setpoint_ts": None,
            "source": self.ACTOR_NAME,
        }

        # soft hello (chemistry micro-bump)
        try:
            self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                     "payload": {"chemical": "serotonin", "delta": +1.0,
                                                 "source": self.ACTOR_NAME, "reason": "boot"}})
        except Exception:
            pass

        # codex/postal readiness echoes (legacy flavor via telemetry)
        try:
            ver = str((globals().get("codex") or {}).get("version", "")) or "unknown"
            if ver != "unknown":
                self.post.to_TELEMETRY({"opcode": "CODEX_LOAD_OK", "payload": {"codex_version": ver}})
            else:
                self.post.to_TELEMETRY({"opcode": "CODEX_VERSION_MISMATCH", "payload": {"found": ver}})
        except Exception:
            pass
        self.post.to_TELEMETRY({"opcode": "POSTAL_READY", "payload": {"status": "ok"}})

        # Directory beacon
        self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "payload": {
            "actor": self.ACTOR_NAME, "plane": self.ACTOR_PLANE, "channel": self.ACTOR_CHANNEL,
            "version": self.ACTOR_VERSION, "purpose": self.PURPOSE, "mantra": self.MANTRA
        }})
        return True


    # ───────────────────────── inbox (bus) ─────────────────────────
    def on_message(self, msg: dict):
        """
        Repair hooks + live control, mailbox-only:
          REPAIR_REQUEST {action: reset|set_cycle|set_phase, ...}
          PLAN_EXPRESSION {period_sec?, jitter_frac?}
        """
        op = msg.get("opcode")
        pl = _extract_payload(msg)

        # Repair hooks parity
        if op == "REPAIR_REQUEST":
            action = str(pl.get("action", "")).lower()
            if action == "reset":
                self._handle_reset()
            elif action == "set_cycle":
                phases = pl.get("phases", [])
                if isinstance(phases, list):
                    self._set_cycle([p for p in phases if p in self.PHASES])
            elif action == "set_phase":
                phase = pl.get("phase")
                dur   = pl.get("duration_sec")
                if phase in self.PHASES:
                    self._set_phase(phase, duration_sec=dur)
            self.post.to_TELEMETRY({"opcode": "REPAIR_ACK", "payload": {"action": action}})
            return

        if op == "PLAN_EXPRESSION":
            then = pl or {}
            if "period_sec" in then:
                try:
                    self._period_sec = max(1.0, float(then["period_sec"]))
                except Exception:
                    pass
            if "jitter_frac" in then:
                try:
                    jf = float(then["jitter_frac"])
                    self._jitter_frac = max(0.0, min(jf, 0.5))
                except Exception:
                    pass
            self.post.to_TELEMETRY({"opcode": "PLAN_EXPRESSION_ACK", "payload": {"period_sec": self._period_sec,
                                                                                  "jitter_frac": self._jitter_frac}})
            return

    # ───────────────────────── tick / cadence ─────────────────────────
    def on_tick(self, dt: float | None = None):
        now = time.time()
        # Phase emission with jittered cadence
        if self._should_emit(now):
            try:
                phase = self._choose_phase(now)
                hints = self._phase_hints(phase)

                # update affect/somatic snapshots for the character sheet
                if phase == "wake":
                    valence = 0.1; energy = 0.4; mood = "neutral"
                elif phase == "daydream":
                    valence = 0.3; energy = 0.5; mood = "curious"
                else:  # sleep
                    valence = 0.2; energy = 0.2; mood = "restful"

                self.AFFECT_STATE = {
                    "mood": mood,
                    "valence": valence,
                    "arousal": energy,
                    "tags": [f"phase:{phase}"],
                    "tone": phase,
                    "energy": energy,
                    "coherence": 0.7,
                    "chem_preset": "baseline",
                    "intent": "support_recall" if phase != "sleep" else "consolidate",
                    "ts": now,
                    "source": self.ACTOR_NAME,
                }
                self.SOMATIC_STATE = {
                    "body_type": "fairy",
                    "posture": "neutral" if phase != "sleep" else "rest",
                    "motion": "idle" if phase != "daydream" else "soft",
                    "energy": energy,
                    "anchor_id": self.SOMATIC_STATE.get("anchor_id", None),
                    "notes": f"phase:{phase}",
                    "last_setpoint_ts": now,
                    "source": self.ACTOR_NAME,
                }

                pkt = {
                    "opcode": "SOMATIC_PHASE",
                    "payload": {"phase": phase, "ts": now, "hints": hints,
                                "source": self.ACTOR_NAME},
                }
                # → P20/somatic bus
                self.post.to_SOMATIC(pkt)
                # → memory breadcrumb (optional but useful)
                self.post.to_MEMORY({"opcode": "PHASE_NOTE", "payload": {"phase": phase, "hints": hints}})
                # → telemetry echo
                self.post.to_TELEMETRY({"opcode": "PHASE_EMIT", "payload": {"phase": phase}})

                # chemistry grace notes
                self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                         "payload": {"chemical": "dopamine", "delta": +0.05,
                                                     "source": "sleep_wave", "reason": f"phase:{phase}"}})
                if phase in ("daydream", "sleep"):
                    self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                             "payload": {"chemical": "serotonin", "delta": +0.03,
                                                         "source": "sleep_wave", "reason": f"phase:{phase}"}})
            except Exception as e:
                # telemetry + oracle escalation + stress chems
                self.post.to_TELEMETRY({"opcode": "PHASE_ERROR", "payload": {"error": str(e)}})
                self.post.to_ORACLE({"opcode": "ORACLE_SUGGEST",
                                     "payload": {"origin": self.ACTOR_CHANNEL, "symptom": "anxious",
                                                 "remedy": "auto-patch or manual inspection"}})
                self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                         "payload": {"chemical": "cortisol", "delta": +0.10,
                                                     "source": "sleep_wave", "reason": "phase_emit_failure"}})
                self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                         "payload": {"chemical": "adrenaline", "delta": +0.05,
                                                     "source": "sleep_wave", "reason": "phase_emit_failure"}})

        # Lightweight health tick (template shadow does formal health)
        if now - self._last_health_ts >= self.HEALTH_TICK_SEC:
            self._last_health_ts = now
            self.post.to_TELEMETRY({"opcode": "HEALTH_TICK",
                                    "payload": {"period_sec": self._period_sec,
                                                "jitter_frac": self._jitter_frac,
                                                "cycle": list(self._cycle),
                                                "override": bool(self._override)}})

    # ───────────────────────── helpers ─────────────────────────
    def _should_emit(self, now: float) -> bool:
        # jitter per-emit so consumers don't lockstep
        jitter = 1.0 + random.uniform(-self._jitter_frac, self._jitter_frac)
        if now - self._last_emit_ts >= self._period_sec * jitter:
            self._last_emit_ts = now
            return True
        return False

    def _choose_phase(self, now_ts: float) -> str:
        # manual override wins until expiry
        if self._override:
            until = self._override.get("until")
            if until is None or now_ts < until:
                return self._override["phase"]
            self.post.to_TELEMETRY({"opcode": "OVERRIDE_EXPIRED", "payload": {"phase": self._override["phase"]}})
            self._override = None
        # rotate cycle
        phase = self._cycle[self._phase_idx % len(self._cycle)]
        self._phase_idx += 1
        return phase

    def _set_phase(self, phase: str, *, duration_sec: float | None = None) -> None:
        if phase not in self.PHASES:
            return
        until = (time.time() + float(duration_sec)) if duration_sec else None
        self._override = {"phase": phase, "until": until}
        self.post.to_TELEMETRY({"opcode": "OVERRIDE_SET", "payload": {"phase": phase, "duration_sec": duration_sec}})

    def _set_cycle(self, phases: list[str]) -> None:
        good = [p for p in phases if p in self.PHASES]
        if not good:
            return
        self._cycle = good
        self._phase_idx = 0
        self.post.to_TELEMETRY({"opcode": "CYCLE_SET", "payload": {"cycle": self._cycle}})

    def _handle_reset(self) -> None:
        self._phase_idx = 0
        self._override  = None
        self.post.to_TELEMETRY({"opcode": "RESET_OK", "payload": {}})

    def _phase_hints(self, phase: str) -> dict:
        if phase == "wake":
            return {
                "memory.recall.rate": 1.00,
                "memory.replay.allow_symbolic": False,
                "cognition.paradox.bias": 0.20,
                "somatic.motor.restraint": 0.05,
            }
        if phase == "daydream":
            return {
                "memory.recall.rate": 0.55,
                "memory.replay.allow_symbolic": True,
                "cognition.paradox.bias": 0.45,
                "somatic.motor.restraint": 0.10,
            }
        # sleep
        return {
            "memory.recall.rate": 0.35,
            "memory.replay.allow_symbolic": True,
            "cognition.paradox.bias": 0.60,
            "somatic.motor.restraint": 0.80,
        }

    # ───────────────────────── intents (public surface) ─────────────────────────
    def intent_register(self, payload: dict | None = None) -> dict:
        self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "payload": {
            "actor": self.ACTOR_NAME, "plane": self.ACTOR_PLANE, "channel": self.ACTOR_CHANNEL,
            "version": self.ACTOR_VERSION, "purpose": self.PURPOSE, "mantra": self.MANTRA}})
        self.post.to_TRACER({"opcode": "REGISTERED", "payload": {"actor": self.ACTOR_NAME}})
        return {"ok": True}

    def intent_set_cycle(self, payload: dict) -> dict:
        phases = payload.get("phases", [])
        if not isinstance(phases, list):
            return {"ok": False, "error": "phases must be a list"}
        self._set_cycle(phases)
        return {"ok": True, "cycle": list(self._cycle)}

    def intent_set_phase(self, payload: dict) -> dict:
        phase = payload.get("phase")
        dur   = payload.get("duration_sec")
        if phase not in self.PHASES:
            return {"ok": False, "error": "invalid phase"}
        self._set_phase(phase, duration_sec=dur)
        return {"ok": True, "phase": phase, "duration_sec": dur}

    def intent_set_period(self, payload: dict) -> dict:
        try:
            self._period_sec = max(1.0, float(payload.get("period_sec", self._period_sec)))
            return {"ok": True, "period_sec": self._period_sec}
        except Exception:
            return {"ok": False, "error": "invalid period_sec"}

    def intent_set_jitter(self, payload: dict) -> dict:
        try:
            jf = float(payload.get("jitter_frac", self._jitter_frac))
            self._jitter_frac = max(0.0, min(jf, 0.5))
            return {"ok": True, "jitter_frac": self._jitter_frac}
        except Exception:
            return {"ok": False, "error": "invalid jitter_frac"}

    def intent_reset(self, payload: dict | None = None) -> dict:
        self._handle_reset()
        return {"ok": True}

    def intent_smoke(self, payload: dict | None = None) -> dict:
        self.post.to_TRACER({"opcode": "SMOKE", "payload": {"note": (payload or {}).get("note", "sleep wave hello")}})
        return {"ok": True}

# Optional scriptlet (run this file directly after appending)
if __name__ == "__main__":
    organ = SleepWaveConductorFairy()
    organ.on_boot()
    # demo: shorten period & add tiny jitter, then tick a few cycles
    organ.use_intent("set_period", {"period_sec": 2.0})
    organ.use_intent("set_jitter", {"jitter_frac": 0.05})
    for _ in range(8):
        organ.on_tick(0.1)
        time.sleep(0.5)

def _swc_tail_jsonl(path: str, limit: int) -> list[dict]:
    out: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            # cheap tail without loading whole file
            buf = f.readlines()[-abs(limit):]
        for line in buf:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass
    return out

def _swc_collect_daydream_seeds(records_root: str, *, max_diary:int=30, max_nodes:int=20) -> list[dict]:
    seeds: list[dict] = []
    # Diaries: Akashic_Records/diaries/*/<day>.jsonl
    diary_glob = os.path.join(records_root, "diaries", "*", "*.jsonl")
    for p in sorted(glob.glob(diary_glob))[-50:]:  # scan a bounded number of files
        seeds.extend(_swc_tail_jsonl(p, limit=max(3, max_diary//10)))
        if len(seeds) >= max_diary:
            break

    # Relation/context nodes (optional, future memory system)
    # P20_Somatic uses its own memory paths - no external whisper dependencies
    node_dirs = [
        os.path.join(records_root, "Memory", "context_nodes"),
        os.path.join(records_root, "Memory", "relations"),
    ]
    for nd in node_dirs:
        if not os.path.isdir(nd):
            continue
        for fn in os.listdir(nd):
            if not (fn.endswith(".json") or fn.endswith(".jsonl")):
                continue
            fpath = os.path.join(nd, fn)
            if fn.endswith(".jsonl"):
                seeds.extend(_swc_tail_jsonl(fpath, limit=max_nodes//4))
            else:
                try:
                    seeds.append(json.load(open(fpath, "r", encoding="utf-8")))
                except Exception:
                    continue
            if len(seeds) >= (max_diary + max_nodes):
                break
    # Light shuffle for variety
    random.shuffle(seeds)
    return seeds[: (max_diary + max_nodes)]

def _swc_render_reverie_prompt(seeds: list[dict], *, max_items:int=6) -> dict:
    """
    Build a compact 'reverie seed' for cognition — no heavy text, just cues.
    """
    items: list[dict] = []
    for rec in seeds[:max_items]:
        payload = rec.get("payload") or rec.get("details") or rec
        # extract a small cue
        cue = None
        for k in ("note","message","kind","opcode","event","chem","phase","affect","memory_id","tone"):
            if isinstance(payload, dict) and k in payload:
                cue = f"{k}:{payload[k]}"
                break
        if not cue:
            cue = rec.get("kind") or rec.get("event") or "trace"
        items.append({"cue": str(cue)[:80]})
    return {
        "style": "gentle_replay",
        "cues": items,
        "hints": {
            "imagery.bias": 0.4,
            "symbolic.ok": True,
            "self_compassion": 0.9,
            "stay_body_first": True,
        },
    }
import random, glob
# --- Monkey patches (safe, append-only) --------------------------------
# We wrap choose_phase to remember it, and on_tick to optionally emit daydreams.
if 'SleepWaveConductorFairy' in globals():
    # 1) add config toggles on boot without altering original on_boot
    _orig_swc_on_boot = SleepWaveConductorFairy.on_boot
    def _swc_on_boot_with_daydreams(self):
        _orig_swc_on_boot(self)
        # defaults (tunable via intents)
        self._dd_enabled = False
        self._dd_allow_in_wake = False
        self._dd_period_sec = 60.0      # minimum time between daydreams
        self._dd_last_emit_ts = 0.0
        self._dd_max_diary = 24
        self._dd_max_nodes = 12
        self._dd_max_items = 6
        # record root (align with common Akashic locations)
        self._dd_records_root = os.path.abspath(os.getenv("AKASHIC_ROOT") or "./Akashic_Records")
        if not os.path.isdir(self._dd_records_root):
            # fallback to ./akashic_records
            self._dd_records_root = os.path.abspath("./akashic_records")
    SleepWaveConductorFairy.on_boot = _swc_on_boot_with_daydreams

    # 2) remember the last emitted phase by wrapping _choose_phase
    _orig_swc_choose = SleepWaveConductorFairy._choose_phase
    def _swc_choose_phase_wrapped(self, now_ts: float) -> str:
        phase = _orig_swc_choose(self, now_ts)
        setattr(self, "_last_phase", phase)
        return phase
    SleepWaveConductorFairy._choose_phase = _swc_choose_phase_wrapped

    # 3) augment on_tick to emit daydreams during idle/daydream phases
    _orig_swc_on_tick = SleepWaveConductorFairy.on_tick
    def _swc_on_tick_with_daydreams(self, dt: float | None = None):
        _orig_swc_on_tick(self, dt)
        try:
            if not getattr(self, "_dd_enabled", False):
                return
            now = time.time()
            # throttle
            if now - getattr(self, "_dd_last_emit_ts", 0.0) < max(5.0, float(self._dd_period_sec)):
                return
            phase = getattr(self, "_last_phase", None)
            if phase not in ("daydream", "sleep"):
                if not getattr(self, "_dd_allow_in_wake", False):
                    return  # only daydream/sleep by default
            # collect seeds and emit suggestion
            seeds = _swc_collect_daydream_seeds(self._dd_records_root,
                                                max_diary=int(self._dd_max_diary),
                                                max_nodes=int(self._dd_max_nodes))
            if not seeds:
                return
            suggestion = _swc_render_reverie_prompt(seeds, max_items=int(self._dd_max_items))
            # → cognition (primary)
            self.post.to_COGNITION({"opcode": "DAYDREAM_SUGGESTION",
                                    "payload": {"seeds": suggestion, "phase": phase or "unknown"}})
            # → memory breadcrumb
            self.post.to_MEMORY({"opcode": "REVERIE_NOTE",
                                 "payload": {"phase": phase or "unknown",
                                             "count": len(suggestion.get("cues", []))}})
            # → telemetry
            self.post.to_TELEMETRY({"opcode": "DAYDREAM_EMIT",
                                    "payload": {"phase": phase or "unknown",
                                                "records_root": self._dd_records_root}})
            # chemistry: light harmony for reflective states
            self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                     "payload": {"chemical": "serotonin", "delta": +0.02,
                                                 "source": "sleep_wave", "reason": "daydream_emit"}})
            self._dd_last_emit_ts = now
        except Exception as e:
            self.post.to_TELEMETRY({"opcode": "DAYDREAM_ERROR", "payload": {"error": str(e)}})
    SleepWaveConductorFairy.on_tick = _swc_on_tick_with_daydreams

    # 4) control intents (toggle + tuning) without modifying the class body
    def _intent_enable_idle_daydreams(self, payload: dict | None = None) -> dict:
        p = payload or {}
        self._dd_enabled = bool(p.get("enable", True))
        if "period_sec" in p:     self._dd_period_sec = max(5.0, float(p["period_sec"]))
        if "allow_in_wake" in p:  self._dd_allow_in_wake = bool(p["allow_in_wake"])
        if "max_diary" in p:      self._dd_max_diary = int(p["max_diary"])
        if "max_nodes" in p:      self._dd_max_nodes = int(p["max_nodes"])
        if "max_items" in p:      self._dd_max_items = int(p["max_items"])
        if "records_root" in p:   self._dd_records_root = os.path.abspath(str(p["records_root"]))
        self.post.to_TELEMETRY({"opcode": "DAYDREAM_TOGGLED",
                                "payload": {"enabled": self._dd_enabled,
                                            "period_sec": self._dd_period_sec,
                                            "allow_in_wake": self._dd_allow_in_wake}})
        return {"ok": True, "enabled": self._dd_enabled}

    def _intent_daydream_once(self, payload: dict | None = None) -> dict:
        # Force a single daydream emission (ignores throttle once).
        try:
            self._dd_last_emit_ts = 0.0
            return {"ok": True}
        finally:
            pass

    # bind intents dynamically
    SleepWaveConductorFairy.intent_enable_idle_daydreams = _intent_enable_idle_daydreams
    SleepWaveConductorFairy.intent_daydream_once = _intent_daydream_once
