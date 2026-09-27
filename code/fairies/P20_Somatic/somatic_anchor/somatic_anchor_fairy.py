from __future__ import annotations

import os, sys, glob, time, types, uuid, json
import importlib.util
from collections import deque
from typing import Optional, Any, Dict

# Import V2 Fairy base class
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    _HAS_FAIRY = True
except ImportError:
    _HAS_FAIRY = False
    Fairy = object

def _resolve_app_root() -> str:
    env_root = os.getenv("AKASHIC_ROOT")
    return os.path.abspath(env_root) if env_root else os.path.abspath(os.getcwd())

def resolve_root(preferred: Optional[str] = None, *, akashic_app: Optional[str] = None) -> str:
    if preferred:
        return os.path.abspath(preferred)
    return _resolve_app_root()

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

class SomaticAnchorShadowFairy:
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
    SHADOW_NAME = "SomaticAnchorShadowFairy"
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

    def __init__(self, actor, interval_sec: float = 30.0):
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
        tests = []

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

        # 4) registration heartbeat removed (V2 Fairy handles registration)

    # helpers to track deep cadence
    def _last_deep_ts(self):
        return getattr(self, "__deep_ts", 0.0)

    def _touch_deep(self, t: float):
        setattr(self, "__deep_ts", t)

    # --- evolution sim (self-contained) ----------
    def _evolution_sim_tick(self, kind: str = "light", n: int = 1):
        """
        Send synthetic evolution observations via postal.
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

class SomaticAnchorFairy(Fairy):
    # Identity
    ACTOR_NAME    = "SomaticAnchorFairy"
    ACTOR_VERSION = "0.4.0"   # worker-on-template edition (parity with lineage)
    ACTOR_PLANE   = "P20"
    ACTOR_CHANNEL = "somatic.anchor"
    ORGAN_LEVEL = False
    
    PURPOSE = "Central affect/soma state for all P20 fairies, with chemistry-style regulation."
    MANTRA  = "Feel once, share many. Decay with grace."
    LORE    = (
        "Holds a shared somatic image from affect frames or setpoints. "
        "Takes regular snapshots for GUI/memory/bus, and nudges chemistry when stressed or tired."
    )

    DIRECTIVE_ACTIVATION = {
        "mode": "Resonance",
        "depth_scaling": "1.0",
        "traits": ["Somatic_Field", "Central_Anchor"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Somatic_Anchor",
        "domains": ["Somatic", "Chemistry", "Memory"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "FF77_Frame_Ingestion",
            "Somatic_Snapshot_Field",
            "Auto_Chem_Guardrails",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["SOMATIC_NOTE", "SOMATIC_HEALTH"],
        "field": ["Body_State_Modulation"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Grounded_Sensing", "Gentle_Truth"],
        "growth": ["Regulation_Skill", "Embodied_Learning"],
    }

    SUBSYSTEM_STATUS = {
        "somatic": {
            "state": "central",
            "notes": "Holds shared PAD/emotion/body_budget frame for P20.",
            "tests": [],
        },
        "chemistry": {
            "state": "guardrails",
            "notes": "Requests floods + signals when stress/energy thresholds are crossed.",
            "tests": [],
        },
        "memory": {
            "state": "logging",
            "notes": "Writes SOMATIC_NOTE + SOMATIC_HEALTH for downstream analysis.",
            "tests": [],
        },
    }
    # Use the template's shadow unchanged
    SHADOW_CLASS = SomaticAnchorShadowFairy

    # Tunables (can be adjusted via intent_set_params)
    SNAPSHOT_DECAY    = 0.95
    SNAPSHOT_INTERVAL = 5.0
    MAX_SNAPSHOTS     = 24
    HEALTH_TICK_SEC   = 15.0

    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
        else:
            self.post = fabric

    # ───────────────────────── lifecycle ─────────────────────────
    def on_boot(self):
        if _HAS_FAIRY:
            super().on_boot()

        # === STANDARD IGNITION WIRING ===
        try:
            self.post.subscribe("system.ignition", self._on_system_ignition)
            self.post.subscribe("somatic.pulse", self._on_somatic_pulse)
        except Exception:
            pass
        print(f"[{self.ACTOR_NAME}] on_boot START", flush=True)

        # runtime state
        self._boot_ts          = time.time()
        self._last_snapshot_ts = 0.0
        self._last_health_ts   = 0.0
        self._snapshots: list[dict] = []
        self._state: dict | None = None   # {"PAD":[p,a,d], "emotions":{}, "body_budget":{}}

        # FF77 processing is now handled internally by SomaticEngineFairy
        # No external whisper module dependencies needed
        self._affect_ref = None
        self._chem_ref = None
        self._freq_ref = None

        # soft hello
        try:
            self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                     "payload": {"chemical": "serotonin", "delta": +1.0,
                                                 "source": self.ACTOR_NAME, "reason": "boot"}})
        except Exception:
            pass

        # codex/postal readiness echoes
        try:
            ver = str((globals().get("codex") or {}).get("version", "")) or "unknown"
            if ver != "unknown":
                try:
                    self.post.to_TELEMETRY({"opcode": "CODEX_LOAD_OK", "payload": {"codex_version": ver}})
                except Exception:
                    pass
            else:
                try:
                    self.post.to_TELEMETRY({"opcode": "CODEX_VERSION_MISMATCH", "payload": {"found": ver}})
                except Exception:
                    pass
        except Exception:
            pass
        
        try:
            self.post.to_TELEMETRY({"opcode": "POSTAL_READY", "payload": {"status": "ok"}})
        except Exception:
            pass
        
        # -- COGNITION->SOMATIC: Mind triggers Body --
        # P30_Cognition.output -> P20_Somatic -> chemistry
        try:
            self.post.subscribe("cognition.output", self._on_cognition_anchor)
            print(f"[{self.ACTOR_NAME}] Mind->Body wire ACTIVE")
        except Exception:
            pass
        
        # directory beacon
        try:
            self.post.to_DIRECTORY({
                "opcode": "CONTRACT_UPSERT",
                "payload": {
                    "actor": self.ACTOR_NAME,
                    "plane": self.ACTOR_PLANE,
                    "channel": self.ACTOR_CHANNEL,
                    "version": self.ACTOR_VERSION,
                    "purpose": self.PURPOSE,
                    "mantra": self.MANTRA,
                }
            })
        except Exception:
            pass
        now = self._boot_ts

        self.AFFECT_STATE = {
            "mood": "neutral",
            "valence": 0.0,
            "arousal": 0.0,
            "tags": ["anchor", "baseline"],
            "tone": "neutral",
            "energy": 0.5,
            "coherence": 0.7,
            "chem_preset": "baseline",
            "intent": "anchor",
            "ts": now,
            "source": self.ACTOR_NAME,
        }

        self.SOMATIC_STATE = {
            "body_type": "field",
            "posture": "neutral",
            "motion": "idle",
            "energy": 0.5,
            "anchor_id": "P20.somatic.anchor",
            "notes": "central somatic field baseline",
            "last_setpoint_ts": None,
            "source": self.ACTOR_NAME,
        }

        # warm-up: if any prior somatic snapshots exist in memory lanes, we leave it to consumers;
        # we'll self-start with a baseline frame if needed in on_tick.

        return True

    # ───────────────────────── inbox (bus) ─────────────────────────
    def on_message(self, msg: dict):
        ch = msg.get("channel")
        op = msg.get("opcode")
        ev = msg.get("event")
        pl = _extract_payload(msg)

        # 77-dim affect frame (Project Whisper)
        if (ch in ("somatic", "affect") and op == "AFFECT_FF77_FRAME") or ev == "AFFECT_FF77_FRAME":
            frame = pl.get("frame") or []
            self._ingest_ff77_frame(frame, {"src": msg.get("src_organ"), "msg_id": msg.get("id")})
            return

        # explicit setpoint override
        if (ch in ("somatic", "control") and op == "SOMATIC_SETPOINT") or ev == "SOMATIC_SETPOINT":
            self._state = {
                "PAD": pl.get("PAD", [0.0, 0.0, 0.0]),
                "emotions": pl.get("emotions", {}),
                "body_budget": pl.get("body_budget", {}),
            }
            self.post.to_TELEMETRY({"opcode": "SOMATIC_OVERRIDE", "payload": {"src": msg.get("src_organ")}})
            return

        # repair hooks
        if op == "REPAIR_REQUEST":
            self.post.to_TELEMETRY({"opcode": "REPAIR_ACK", "payload": pl})
            # urgent nudge
            self._chem_signal("adrenaline", +1.0, reason="repair_request")
            # simple plan echo
            self.post.to_ORACLE({"opcode": "PLAN_EXPRESSION",
                                 "payload": {"action": "re-express-somatic", "notes": "restart snapshot loop"}})
            return

        if op == "PLAN_EXPRESSION":
            self.post.to_TELEMETRY({"opcode": "PLAN_EXPRESSION_ACK", "payload": pl})
            return

    # ───────────────────────── tick / cadence ─────────────────────────
    def on_tick(self, dt: float | None = None):
        now = time.time()

        # 1) maybe autogen baseline if we have no state
        if self._state is None:
            self._maybe_autogen_frame()

        # 2) snapshot cadence
        if now - self._last_snapshot_ts >= self.SNAPSHOT_INTERVAL and self._state is not None:
            self._last_snapshot_ts = now
            self._emit_snapshot(now)

        # 3) auto-chem based on last snapshot’s body budget
        self._maybe_auto_chem()

        # 4) lightweight health tick (template shadow handles full tests)
        if now - self._last_health_ts >= self.HEALTH_TICK_SEC:
            self._last_health_ts = now
            self.post.to_TELEMETRY({
                "opcode": "HEALTH_TICK",
                "payload": {
                    "snapshots": len(self._snapshots),
                    "has_affect_ref": bool(self._affect_ref),
                    "has_freq_ref": bool(self._freq_ref),
                    "has_chem_ref": bool(self._chem_ref),
                },
            })

    # ───────────────────────── core behavior ─────────────────────────
    def _ingest_ff77_frame(self, frame: list[float], ctx: dict):
        if not frame:
            return
        state = None
        if self._affect_ref and hasattr(self._affect_ref, "ingest_frame"):
            try:
                state = self._affect_ref.ingest_frame(frame, time.time(), 0.1)
            except Exception as e:
                self.post.to_TELEMETRY({"opcode": "FF77_INGEST_ERROR", "payload": {"error": str(e)}})
        if state is None:
            # tolerant fallback
            pad = frame[:3] if len(frame) >= 3 else [0.0, 0.0, 0.0]
            state = {"PAD": pad, "emotions": {}, "body_budget": {}}
        self._state = state
        self.post.to_TELEMETRY({"opcode": "FF77_INGEST", "payload": {"dim": len(frame), "ctx": ctx}})
        self._chem_signal("dopamine", +1.0, reason="ff77_ingest")

    def _maybe_autogen_frame(self):
        if self._freq_ref and hasattr(self._freq_ref, "generate_baseline_frame"):
            try:
                frame = self._freq_ref.generate_baseline_frame()
                self._ingest_ff77_frame(frame, {"src": "somatic.self"})
            except Exception:
                pass

    def _on_cognition_anchor(self, payload):
        """Allow thoughts to trigger somatic anchors."""
        try:
            confidence = payload.get("confidence", 0.5)
            result = payload.get("result", {})
            
            if confidence < 0.7:
                return
            
            text = str(result).lower()
            anchor_triggers = {
                "calm": "relaxation_anchor",
                "safe": "safety_anchor",
                "focus": "attention_anchor",
            }
            
            for keyword, anchor in anchor_triggers.items():
                if keyword in text:
                    self.post.route("somatic.anchor_trigger", {
                        "anchor": anchor,
                        "source": "cognition",
                        "confidence": confidence,
                    })
                    break
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cognition anchor error: {e}")

    def _emit_snapshot(self, now_ts: float):
        PAD = (getattr(self._state, "PAD", None)
               or (self._state.get("PAD") if isinstance(self._state, dict) else [0.0, 0.0, 0.0]))
        emotions = (getattr(self._state, "emotions", None)
                    or (self._state.get("emotions") if isinstance(self._state, dict) else {}))
        body_budget = (getattr(self._state, "body_budget", None)
                       or (self._state.get("body_budget") if isinstance(self._state, dict) else {}))

        snap = {
            "id": uuid.uuid4().hex,
            "ts": now_ts,
            "organ": self.ACTOR_NAME,
            "plane": self.ACTOR_PLANE,
            "state": {"PAD": PAD, "emotions": emotions, "body_budget": body_budget},
            "decay": 1.0,
        }
        self._snapshots.append(snap)
        if len(self._snapshots) > self.MAX_SNAPSHOTS:
            self._snapshots = self._snapshots[-self.MAX_SNAPSHOTS:]

                # keep a simple affect snapshot for the character sheet
        # interpret PAD as (valence, arousal, dominance)
        valence, arousal, _dom = (PAD + [0.0, 0.0, 0.0])[:3]
        self.AFFECT_STATE = {
            "mood": "stressed" if body_budget.get("stress", 0.0) > 0.6 else "neutral",
            "valence": float(valence),
            "arousal": float(arousal),
            "tags": ["anchor"],
            "tone": "somatic_field",
            "energy": float(body_budget.get("energy", 0.5)),
            "coherence": 0.7,
            "chem_preset": "dynamic",
            "intent": "anchor",
            "ts": now_ts,
            "source": self.ACTOR_NAME,
        }

        self.SOMATIC_STATE = {
            "body_type": "field",
            "posture": "neutral",
            "motion": "idle",
            "energy": float(body_budget.get("energy", 0.5)),
            "anchor_id": "P20.somatic.anchor",
            "notes": "latest somatic snapshot",
            "last_setpoint_ts": now_ts,
            "source": self.ACTOR_NAME,
        }

        # → GUI
        self.post.route("GUI", {"opcode": "SOMATIC_SNAPSHOT", "payload": snap})
        # → Memory
        self.post.to_MEMORY({"opcode": "SOMATIC_NOTE", "payload": snap})
        # → Somatic bus broadcast
        self.post.to_SOMATIC({"opcode": "SOMATIC_STATE", "payload": snap})
        # → Telemetry
        self.post.to_TELEMETRY({"opcode": "SNAPSHOT_EMIT", "payload": {"id": snap["id"]}})

        # decay + trim
        for s in self._snapshots:
            s["decay"] *= self.SNAPSHOT_DECAY
        self._snapshots = [s for s in self._snapshots if s["decay"] >= 0.05]

        # harmony nudge on steady loop
        self._chem_signal("serotonin", +1.0, reason="snapshot_loop")

    def _maybe_auto_chem(self):
        if not self._snapshots:
            return
        last = self._snapshots[-1]
        body = (last.get("state") or {}).get("body_budget", {}) or {}
        stress = float(body.get("stress", 0.0))
        energy = float(body.get("energy", 0.5))
        if stress > 0.6 or energy < 0.3:
            intent = "soothe" if stress > 0.6 else "energize"
            # → affect/plan for chem modulation
            self.post.route("PLAN", {"opcode": "CHEM_FLOOD_REQ",
                                     "payload": {"intent": intent,
                                                 "neuromods": {"OXY": 0.3 if stress > 0.6 else 0.05,
                                                               "END": 0.2 if energy < 0.3 else 0.0},
                                                 "source": self.ACTOR_NAME}})
            # forensic breadcrumb
            self.post.to_MEMORY({"opcode": "SOMATIC_HEALTH",
                                 "payload": {"stress": stress, "energy": energy, "auto_chem": intent}})
            # stress/urgent signals
            if stress > 0.6:
                self._chem_signal("cortisol", +1.0, reason="stress_high")
            if energy < 0.3:
                self._chem_signal("adrenaline", +1.0, reason="energy_low")

    # ───────────────────────── intents (public surface) ─────────────────────────
    def intent_register(self, payload: dict | None = None) -> dict:
        self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "payload": {
            "actor": self.ACTOR_NAME, "plane": self.ACTOR_PLANE, "channel": self.ACTOR_CHANNEL,
            "version": self.ACTOR_VERSION, "purpose": self.PURPOSE, "mantra": self.MANTRA}})
        self.post.to_TRACER({"opcode": "REGISTERED", "payload": {"actor": self.ACTOR_NAME}})
        return {"ok": True}

    def intent_set_params(self, payload: dict | None = None) -> dict:
        p = payload or {}
        if "snapshot_interval" in p:
            try: self.SNAPSHOT_INTERVAL = max(0.5, float(p["snapshot_interval"]))
            except Exception: pass
        if "snapshot_decay" in p:
            try: self.SNAPSHOT_DECAY = float(p["snapshot_decay"])
            except Exception: pass
        if "max_snapshots" in p:
            try: self.MAX_SNAPSHOTS = max(1, int(p["max_snapshots"]))
            except Exception: pass
        self.post.to_TELEMETRY({"opcode": "PARAMS_SET",
                                "payload": {"interval": self.SNAPSHOT_INTERVAL,
                                            "decay": self.SNAPSHOT_DECAY,
                                            "max": self.MAX_SNAPSHOTS}})
        return {"ok": True, "interval": self.SNAPSHOT_INTERVAL,
                "decay": self.SNAPSHOT_DECAY, "max": self.MAX_SNAPSHOTS}

    def intent_ingest_ff77(self, payload: dict) -> dict:
        frame = payload.get("frame") or []
        self._ingest_ff77_frame(frame, {"src": "intent"})
        return {"ok": True, "dim": len(frame)}

    def intent_somatic_setpoint(self, payload: dict) -> dict:
        self._state = {
            "PAD": payload.get("PAD", [0.0, 0.0, 0.0]),
            "emotions": payload.get("emotions", {}),
            "body_budget": payload.get("body_budget", {}),
        }
        self.post.to_TELEMETRY({"opcode": "SOMATIC_OVERRIDE", "payload": {"via": "intent"}})
        return {"ok": True}

    def intent_force_snapshot(self, payload: dict | None = None) -> dict:
        self._emit_snapshot(time.time()) if self._state is not None else None
        return {"ok": bool(self._state)}

    def intent_smoke(self, payload: dict | None = None) -> dict:
        self.post.to_TRACER({"opcode": "SMOKE", "payload": {"note": (payload or {}).get("note", "somatic hello")}})
        return {"ok": True}

    # ───────────────────────── tiny helpers ─────────────────────────
    def _chem_signal(self, chemical: str, delta: float, *, reason: str):
        self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                 "payload": {"chemical": chemical, "delta": float(delta),
                                             "source": self.ACTOR_NAME, "reason": reason}})

