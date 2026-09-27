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

class EmotionalHiveProcessorShadowFairy(Fairy):
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
    SHADOW_NAME = "EmotionalHiveProcessorShadowFairy"
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
# APPEND-ONLY ORGAN — P20 Emotional Hive Processor (uses template shadow unchanged)
# Lineage: P20 / emotional_hive_processor.Ver.2.1 (parity-upgraded)
# Template: 0.0.7 — do not modify the template body above; mailbox-only I/O.
# Philosophy: “Feel it fully, return with grace.”
# ─────────────────────────────────────────────────────────────────────────────

class EmotionalHiveProcessorFairy(Fairy):
    # Identity (preserve lineage)
    ACTOR_NAME    = "EmotionalHiveProcessorFairy"
    ACTOR_VERSION = "2.1.1"  # worker-on-template edition
    ACTOR_PLANE   = "P20"
    ACTOR_CHANNEL = "somatic.hive"
    ORGAN_LEVEL = False
    
    PURPOSE = "Recreate and gently resolve the 'emotional pose' of a recalled memory."
    MANTRA  = "Feel it fully, return with grace."
    LORE    = (
        "On recall, reconstitute the felt pose (affect→chems), hold it briefly, then return to baseline "
        "through a smooth, proportional decay. Leave breadcrumbs so the body remembers how it learned to soften."
    )

    # Directive ring for the status/character sheet
    DIRECTIVE_ACTIVATION = {
        "mode": "Resonance",
        "depth_scaling": "1..2",
        "traits": ["Recall_Pose_Recreation", "Chem_Decay_Orchestration"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Emotional_Hive",
        "domains": ["Somatic", "Chemistry", "Memory"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Memory_Recall_Pose",
            "Chem_Delta_Application",
            "Guided_Decay",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["RECALL_STATE", "CHEM_NOTE", "DECAY_TRACE"],
        "field": ["Body_State_Modulation"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Felt_Truth", "Gentle_Resolution"],
        "growth": ["Regulation_Skill", "Emotional_Learning"],
    }

    SUBSYSTEM_STATUS = {
        "somatic": {
            "state": "reactive",
            "notes": "Listens for RECALL_STATE and reconstructs felt pose.",
            "tests": [],
        },
        "chemistry": {
            "state": "active",
            "notes": "Applies and decays chem deltas mapped from recalled affect.",
            "tests": [],
        },
        "memory": {
            "state": "bound",
            "notes": "Ties chem traces to memory_id; emits breadcrumbs.",
            "tests": [],
        },
    }

    # Use the template’s shadow unchanged
    SHADOW_CLASS = EmotionalHiveProcessorShadowFairy

    # Cadence (actor-local; template runs its own harness too)
    HEALTH_TICK_SEC = 15.0
    DECAY_TICK_SEC  = 0.5  # fine-grained, gentle decay rhythm

    # Default timing (can be adjusted via intent_set_params)
    DEFAULT_HOLD_MS  = 1500
    DEFAULT_DECAY_MS = 2000

    # Built-in affect → chemistry deltas (can be extended via intents)
    _AFFECT_REGISTRY: dict[str, dict[str, float]] = {
        "stress":    {"cortisol": +0.20, "adrenaline": +0.10},
        "curiosity": {"dopamine": +0.15, "serotonin": +0.05},
        "neutral":   {"serotonin": +0.02},
    }

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
        self._boot_ts          = time.time()
        self._last_health_ts   = 0.0
        self._last_decay_tick  = 0.0
        self._upgrade_ack_sent = False

        # recall state container
        self._hold_ms  = self.DEFAULT_HOLD_MS
        self._decay_ms = self.DEFAULT_DECAY_MS
        self._current: dict | None = None  # {"affect": str, "applied_at": float, "chems": {...}, "last": {...}}

        # initial affect/somatic snapshot for status sheet
        now = self._boot_ts
        self.AFFECT_STATE = {
            "mood": "neutral",
            "valence": 0.0,
            "arousal": 0.0,
            "tags": ["idle"],
            "tone": "neutral",
            "energy": 0.3,
            "coherence": 0.5,
            "chem_preset": "baseline",
            "intent": "recall",
            "ts": now,
            "source": self.ACTOR_NAME,
        }
        self.SOMATIC_STATE = {
            "body_type": "fairy",
            "posture": "neutral",
            "motion": "idle",
            "energy": 0.3,
            "anchor_id": None,
            "notes": "baseline pose before recall",
            "last_setpoint_ts": None,
            "source": self.ACTOR_NAME,
        }

        # soft hello
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {"chemical": "serotonin", "delta": +1.0,
                            "source": self.ACTOR_NAME, "reason": "boot"},
            })
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


        # -- COGNITION->SOMATIC: Mind triggers Body --
        # P30_Cognition.output -> P20_Somatic -> chemistry
        self.post.subscribe("cognition.output", self._on_cognition_affect)
        self.post.subscribe("cognition.irrational", self._on_cognition_affect)
        print(f"[{self.ACTOR_NAME}] Mind->Body wire ACTIVE")

        # -- FF77->CHEMISTRY: Visual frequency field triggers body chemistry --
        # Visual perception → FF77 bands → chemistry (dopamine on novelty, cortisol on edge)
        self.post.subscribe("telemetry.frequency", self._on_ff77_frequency)
        print(f"[{self.ACTOR_NAME}] FF77->Chemistry wire ACTIVE")
        # Directory beacon
        self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "payload": {
            "actor": self.ACTOR_NAME, "plane": self.ACTOR_PLANE, "channel": self.ACTOR_CHANNEL,
            "version": self.ACTOR_VERSION, "purpose": self.PURPOSE, "mantra": self.MANTRA,
        }})
        return True

    # ───────────────────────── inbox (bus) ─────────────────────────
    def on_message(self, msg: dict):
        """
        Accepts both styles:
         - event-based:  msg['event'] == 'RECALL_STATE'
         - bus style:    msg['channel']=='somatic' and msg['opcode']=='RECALL_STATE'
        Payload shape:
         { intent:'recall.state', memory_id:'...', somatic:{...}, affect:'curiosity'|'stress'|None, ts:... }
        """
        ev = msg.get("event")
        ch = msg.get("channel")
        op = msg.get("opcode")
        pl = _extract_payload(msg)

        # Recall → pose recreation
        if ev == "RECALL_STATE" or (ch == "somatic" and op == "RECALL_STATE"):
            self._handle_recall_state(pl)
            return

        # Repair hooks parity echoes
        if op == "REPAIR_REQUEST":
            self.post.to_TELEMETRY({"opcode": "REPAIR_ACK", "payload": {"actor": self.ACTOR_NAME}})
            # also let the shadow run promptly
            self.request_immediate_selfcheck()
            return
        if op == "PLAN_EXPRESSION":
            self.post.to_TELEMETRY({"opcode": "PLAN_EXPRESSION_ACK", "payload": pl})
            return

    # ───────────────────────── tick / cadence ─────────────────────────
    def on_tick(self, dt: float | None = None):
        now = time.time()

        # Work cadence: hold → decay
        if self._current is not None and (now - self._last_decay_tick) >= self.DECAY_TICK_SEC:
            self._last_decay_tick = now
            self._decay_step()

        # Health tick (lightweight; formal health handled by template shadow)
        if now - self._last_health_ts >= self.HEALTH_TICK_SEC:
            self._last_health_ts = now
            self.post.to_TELEMETRY({
                "opcode": "HEALTH_TICK",
                "payload": {
                    "active": bool(self._current),
                    "hold_ms": self._hold_ms,
                    "decay_ms": self._decay_ms,
                },
            })

    # ───────────────────────── core behavior ─────────────────────────
    def _affect_to_chems(self, affect: str) -> dict[str, float]:
        return dict(self._AFFECT_REGISTRY.get(affect.lower(), self._AFFECT_REGISTRY["neutral"]))

    def _on_cognition_affect(self, payload):
        """Integrate cognitive output into emotional processing."""
        try:
            actor = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)
            
            if not hasattr(self, "_cognitive_affect_context"):
                from collections import deque
                self._cognitive_affect_context = deque(maxlen=30)
            
            affect = result.get("affect", 0.5)
            if isinstance(affect, str):
                affect = 0.7 if affect in ["positive", "good"] else 0.3
            
            self._cognitive_affect_context.append({
                "actor": actor,
                "affect": affect,
                "confidence": confidence,
                "ts": __import__('time').time(),
            })
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cognition affect error: {e}")

    def _on_ff77_frequency(self, msg):
        """
        Process FF77 frequency field telemetry → chemistry deltas.
        Rate-limited and lightweight to avoid blocking.
        """
        try:
            # Rate limit: max 2Hz
            now = __import__('time').time()
            if now - getattr(self, '_last_ff77_ts', 0) < 0.5:
                return
            self._last_ff77_ts = now

            payload = _extract_payload(msg)
            vec77 = payload.get("vec", [])
            
            if not vec77 or len(vec77) != 77:
                return
            
            # Quick band energy extraction
            v1_energy = sum(vec77[0:20]) / 20
            v4_energy = sum(vec77[40:60]) / 20
            it_energy = sum(vec77[60:70]) / 10
            meta_energy = sum(vec77[70:77]) / 7
            
            # Only emit deltas if significant (reduces postal traffic)
            if v1_energy > 0.6:
                self._emit_chem_delta("norepinephrine", (v1_energy - 0.5) * 0.3, "visual_edge")
            if v4_energy > 0.5:
                self._emit_chem_delta("dopamine", (v4_energy - 0.4) * 0.25, "visual_color")
            if it_energy > 0.55:
                self._emit_chem_delta("dopamine", (it_energy - 0.45) * 0.2, "visual_novelty")
            if meta_energy > 0.6:
                self._emit_chem_delta("serotonin", (meta_energy - 0.5) * 0.2, "visual_engage")
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] FF77 frequency error: {e}")

    def _emit_chem_delta(self, chem: str, delta: float, reason: str):
        """Chem delta → chemistry plane + memory breadcrumb + telemetry echo."""
        # → chemistry vectorized as individual deltas
        # FIX 2026-04-04 (Nous): to_CHEMISTRY doesn't exist on _FabricPostalBridge.
        # Route through publish() to somatic.chemistry topic instead.
        try:
            if hasattr(self.post, 'to_CHEMISTRY'):
                self.post.to_CHEMISTRY({"opcode": "CHEM_FIELD_UPDATE", "payload": {chem: float(delta), "source": self.ACTOR_NAME}})
            else:
                self.post.publish("somatic.chemistry", {"opcode": "CHEM_FIELD_UPDATE", "payload": {chem: float(delta), "source": self.ACTOR_NAME}})
        except Exception:
            pass
        # → memory breadcrumb
        self.post.to_MEMORY({"opcode": "CHEM_NOTE", "payload": {"chem": chem, "delta": float(delta), "reason": reason}})
        # → telemetry echo
        self.post.to_TELEMETRY({"opcode": "CHEM_FIELD_UPDATE", "payload": {"chem": chem, "delta": float(delta), "reason": reason}})

    def _chem_signal(self, chemical: str, delta: float, reason: str):
        self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                 "payload": {"chemical": chemical, "delta": float(delta),
                                             "source": self.ACTOR_NAME, "reason": reason}})

    def _handle_recall_state(self, evt: dict):
        # Validate intent (tolerant)
        if (evt.get("intent") or "").lower() not in ("recall.state", "recall_state", ""):
            self.post.to_TELEMETRY({"opcode": "RECALL_IGNORED", "payload": {"intent": evt.get("intent")}})
            return

        target_affect = (evt.get("affect") or "neutral").lower()
        deltas = self._affect_to_chems(target_affect)

        # Apply initial pose
        for chem, delta in deltas.items():
            try:
                self._emit_chem_delta(chem, float(delta), reason=f"recall:{evt.get('memory_id')}")
            except Exception:
                self._emit_chem_delta(chem, float(delta), reason="recall:apply")

            # parity: dopamine/serotonin bumps for successful apply
            if chem in ("dopamine", "serotonin"):
                self._chem_signal(chem, +1.0, "recall_apply")

        now = time.time()
        self._current = {
            "affect": target_affect,
            "applied_at": now,
            "chems": deltas,
            "last": {k: v for k, v in deltas.items()},
        }

        # affect + somatic snapshots for status sheet
        # simple valence/energy guess based on affect
        if target_affect == "stress":
            valence = -0.6
            energy = 0.8
        elif target_affect == "curiosity":
            valence = 0.4
            energy = 0.6
        else:
            valence = 0.0
            energy = 0.4

        tags = ["recall", f"memory:{evt.get('memory_id') or 'unknown'}", target_affect]

        self.AFFECT_STATE = {
            "mood": target_affect,
            "valence": valence,
            "arousal": energy,
            "tags": tags,
            "tone": target_affect,
            "energy": energy,
            "coherence": 0.6,
            "chem_preset": "baseline",
            "intent": "recall_replay",
            "ts": now,
            "source": self.ACTOR_NAME,
        }

        som = evt.get("somatic") or {}
        self.SOMATIC_STATE = {
            "body_type": som.get("body_type", "fairy"),
            "posture": som.get("posture", "neutral"),
            "motion": som.get("motion", "idle"),
            "energy": som.get("energy", energy),
            "anchor_id": som.get("anchor_id"),
            "notes": "recalled pose from memory",
            "last_setpoint_ts": now,
            "source": self.ACTOR_NAME,
        }

        self.post.to_TELEMETRY({"opcode": "RECALL_APPLY",
                                "payload": {"memory_id": evt.get("memory_id"), "affect": target_affect, "chems": deltas}})

    def _decay_step(self):
        if not self._current:
            return
        try:
            now = time.time()
            elapsed_ms = int((now - self._current["applied_at"]) * 1000)

            # hold phase
            if elapsed_ms < self._hold_ms:
                return

            # decay phase (linear ramp to zero over decay_ms)
            progress = min(1.0, (elapsed_ms - self._hold_ms) / max(1.0, self._decay_ms))
            chems = self._current.get("chems", {})
            for chem, initial_delta in chems.items():
                current_target = initial_delta * (1.0 - progress)
                last_emitted   = self._current["last"].get(chem, initial_delta)
                step = current_target - last_emitted
                if abs(step) > 1e-6:
                    self._emit_chem_delta(chem, float(step), reason="hive.decay")
                    self._current["last"][chem] = current_target
                    if step < 0:
                        # small serotonin bump for smooth decay
                        self._chem_signal("serotonin", +1.0, "decay_step")

            self.post.to_TELEMETRY({"opcode": "DECAY_PROGRESS",
                                    "payload": {"progress": round(progress, 3), "chems": list(chems.keys())}})

            if progress >= 1.0:
                self.post.to_TELEMETRY({"opcode": "DECAY_END", "payload": {"affect": self._current["affect"]}})
                # reset affect/somatic snapshots to baseline calm
                self.AFFECT_STATE = {
                    "mood": "neutral",
                    "valence": 0.0,
                    "arousal": 0.0,
                    "tags": ["post_recall"],
                    "tone": "neutral",
                    "energy": 0.3,
                    "coherence": 0.7,
                    "chem_preset": "baseline",
                    "intent": "return_to_baseline",
                    "ts": now,
                    "source": self.ACTOR_NAME,
                }
                self.SOMATIC_STATE = {
                    "body_type": self.SOMATIC_STATE.get("body_type", "fairy"),
                    "posture": "neutral",
                    "motion": "idle",
                    "energy": 0.3,
                    "anchor_id": self.SOMATIC_STATE.get("anchor_id"),
                    "notes": "returned to baseline after recall",
                    "last_setpoint_ts": now,
                    "source": self.ACTOR_NAME,
                }
                self._current = None
        except Exception as e:
            self.post.to_TELEMETRY({"opcode": "DECAY_ERROR", "payload": {"error": str(e)}})
            self._chem_signal("cortisol", +1.0, "decay_error")

    # ───────────────────────── intents (public surface) ─────────────────────────
    def intent_register(self, payload: dict | None = None) -> dict:
        self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "payload": {
            "actor": self.ACTOR_NAME, "plane": self.ACTOR_PLANE, "channel": self.ACTOR_CHANNEL,
            "version": self.ACTOR_VERSION, "purpose": self.PURPOSE, "mantra": self.MANTRA}})
        self.post.to_TRACER({"opcode": "REGISTERED", "payload": {"actor": self.ACTOR_NAME}})
        return {"ok": True}

    def intent_set_params(self, payload: dict | None = None) -> dict:
        """Adjust hold/decay windows in milliseconds."""
        p = payload or {}
        if "hold_ms" in p:  self._hold_ms  = max(0, int(p["hold_ms"]))
        if "decay_ms" in p: self._decay_ms = max(1, int(p["decay_ms"]))
        self.post.to_TELEMETRY({"opcode": "PARAMS_SET", "payload": {"hold_ms": self._hold_ms, "decay_ms": self._decay_ms}})
        return {"ok": True, "hold_ms": self._hold_ms, "decay_ms": self._decay_ms}

    def intent_register_affect(self, payload: dict) -> dict:
        """Extend affect registry at runtime."""
        name = str(payload.get("name") or "").strip().lower()
        deltas = payload.get("deltas") or {}
        if not name or not isinstance(deltas, dict):
            return {"ok": False, "error": "invalid payload"}
        # ensure floats
        self._AFFECT_REGISTRY[name] = {k: float(v) for k, v in deltas.items()}
        self.post.to_TELEMETRY({"opcode": "AFFECT_REGISTERED", "payload": {"name": name, "deltas": self._AFFECT_REGISTRY[name]}})
        return {"ok": True, "name": name}

    def intent_list_affects(self, payload: dict | None = None) -> dict:
        return {"ok": True, "affects": {k: dict(v) for k, v in self._AFFECT_REGISTRY.items()}}

    def intent_recall_state(self, payload: dict) -> dict:
        """Manual recall trigger (same as RECALL_STATE message)."""
        self._handle_recall_state(payload or {})
        return {"ok": True}

    def intent_smoke(self, payload: dict | None = None) -> dict:
        self.post.to_TRACER({"opcode": "SMOKE", "payload": {"note": (payload or {}).get("note", "hive hello")}})
        return {"ok": True}

# Optional scriptlet (run this file directly after appending)
if __name__ == "__main__":
    organ = EmotionalHiveProcessorFairy()
    organ.on_boot()
    # quick demo: set params, trigger recall, and tick through decay
    organ.use_intent("set_params", {"hold_ms": 800, "decay_ms": 1500})
    organ.use_intent("recall_state", {"memory_id": "demo-001", "affect": "curiosity"})
    for _ in range(10):
        organ.on_tick(0.1)
        time.sleep(0.25)
