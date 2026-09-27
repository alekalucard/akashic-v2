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
    
def _r3(x: float) -> float:
    """Round safely to 3 decimals."""
    try:
        return round(float(x), 3)
    except Exception:
        return 0.0

def _round3(t):
    """Round a 3-item PAD tuple/list to 3 decimals each."""
    try:
        return [round(float(v), 3) for v in t]
    except Exception:
        return [0.0, 0.0, 0.0]

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

class SomaticAnchorResolverShadowFairy(Fairy):
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
    SHADOW_NAME = "SomaticAnchorResolverShadowFairy"
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
# APPEND-ONLY WORKER — P20 Somatic Anchor Resolver (template-safe)
# Philosophy: “Feel once, share many. Decay with grace.”
# Purpose: Fuse competing somatic influences into one resolved setpoint.
# ─────────────────────────────────────────────────────────────────────────────

class SomaticAnchorResolverFairy(Fairy):
    ACTOR_NAME    = "SomaticAnchorResolverFairy"
    ACTOR_VERSION = "0.2.0"
    ACTOR_PLANE   = "P20"
    ACTOR_CHANNEL = "somatic.resolver"
    ORGAN_LEVEL = False

    PURPOSE = (
        "Resolve multiple somatic influences—affect, chemistry hints, sleep phase, "
        "and explicit candidates—into a coherent SOMATIC_SETPOINT for the P20 bus."
    )
    MANTRA  = "Hold steady; blend kindly."
    LORE    = (
        "A soft arbiter between moods, chemical weather, and dream-cadence. "
        "She listens to everyone, then hums one chord."
    )

    SHADOW_CLASS = SomaticAnchorResolverShadowFairy  # keep the template shadow unchanged

    # ── Character-sheet directive ring (for fairy_status_sheet) ──────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Resonance",
        "depth_scaling": "1.0",
        "traits": ["Somatic_Resolver", "Blended_Setpoint", "Windowed_Sensing"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Somatic_Resolver",
        "domains": ["Somatic", "Chemistry", "Affect", "Sleep_Phase"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Windowed_Influence_Tracking",
            "PAD_Blend_Resolution",
            "Body_Budget_Heuristics",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["SOMATIC_RESOLVER_NOTE", "SOMATIC_SETPOINT"],
        "field": ["Body_State_Modulation"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Honest_Blend", "Explainable_Choice"],
        "growth": ["Better_Weights", "Gentler_Resets"],
    }

    SUBSYSTEM_STATUS = {
        "somatic": {
            "state": "resolving",
            "notes": "Blends multiple somatic influences into a single setpoint for P20.",
            "tests": [],
        },
        "chemistry": {
            "state": "hinting",
            "notes": "Uses chemistry field as soft bias for arousal/valence.",
            "tests": [],
        },
        "affect": {
            "state": "listening",
            "notes": "Consumes affect/bridge events as gentle PAD nudges.",
            "tests": [],
        },
        "sleep": {
            "state": "phase_aware",
            "notes": "Respects SleepWave phases (wake/daydream/sleep) in PAD blending.",
            "tests": [],
        },
    }

    # tunables (exposed via intent_set_weights / intent_set_params)
    WINDOW_SEC          = 20.0   # how long to consider recent influences
    EMIT_PERIOD_SEC     = 3.0    # cadence for publishing resolved setpoint
    BASELINE_PAD        = (0.33, 0.33, 0.34)  # (Pleasure, Arousal, Dominance) neutral-ish
    CHEM_TONES          = {"serotonin": +0.10, "dopamine": +0.12, "cortisol": -0.15, "adrenaline": +0.18}
    PHASE_TONES         = {"wake": (0.05, 0.10, 0.05), "daydream": (0.08, 0.06, -0.02), "sleep": (0.02, -0.10, -0.05)}
    DEFAULT_WEIGHTS     = {"affect": 0.45, "candidate": 0.35, "chemistry": 0.12, "phase": 0.08}

    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
            # self.post is set by parent Fairy.__init__
        else:
            # Fallback when fairy_template import failed
            self.post = fabric
            self.post = fabric

    def on_boot(self):
        # IMPORTANT: Call super() to trigger HeartbeatMixin auto-start
        if _HAS_FAIRY:
            super().on_boot()

        self._buf: list[dict] = []      # rolling events window
        self._last_emit = 0.0
        self._weights = dict(self.DEFAULT_WEIGHTS)
        self._phase = "wake"
        self._chem_cache: dict[str, float] = {}  # last seen field

        # hello + identity crumbs
        self.post.to_TELEMETRY({
            "opcode": "RESOLVER_READY",
            "payload": {
                "window_sec": self.WINDOW_SEC,
                "emit_period_sec": self.EMIT_PERIOD_SEC,
                "weights": self._weights,
                "baseline_PAD": self.BASELINE_PAD,
            },
        })
        # small harmony nudge (consistent with other workers)
        self.post.to_PLAN({
            "opcode": "CHEM_SIGNAL_UPDATE",
            "payload": {
                "chemical": "serotonin",
                "delta": +0.02,
                "source": self.ACTOR_NAME,
                "reason": "boot",
            },
        })

        # ── initial character-sheet state (neutral baseline) ────────────────
        now = time.time()
        self.AFFECT_STATE = {
            "mood": "neutral",
            "valence": float(self.BASELINE_PAD[0]),
            "arousal": float(self.BASELINE_PAD[1]),
            "tags": ["resolver", "baseline"],
            "tone": "somatic_resolver",
            "energy": 0.5,
            "coherence": 0.7,
            "chem_preset": "baseline",
            "intent": "resolve",
            "ts": now,
            "source": self.ACTOR_NAME,
        }
        self.SOMATIC_STATE = {
            "body_type": "field",
            "posture": "neutral",
            "motion": "idle",
            "energy": 0.5,
            "anchor_id": "P20.somatic.resolver",
            "notes": "resolver baseline before any influences",
            "last_setpoint_ts": None,
            "source": self.ACTOR_NAME,
        }
        return True

    # ——— inbox ———
    def on_message(self, msg: dict):
        ch = msg.get("channel")
        op = msg.get("opcode")
        ev = msg.get("event")
        pl = _extract_payload(msg)

        now = time.time()

        def _push(kind, payload):
            self._buf.append({"ts": now, "kind": kind, "payload": payload})

        # Affect / emotion events (from affect_bridge or others)
        if ev == "AFFECT_EVENT" or (ch in ("affect", "affect_bridge") and op in ("EMOTION", "AFFECT_EVENT")):
            tone = str((pl.get("tone") or "neutral")).lower()
            energy = float(pl.get("energy", 0.5))
            tone_map = {
                "soothing": (-0.05, -0.05, +0.02),
                "calm":     (-0.03, -0.04, +0.02),
                "neutral":  (0.0,   0.0,   0.0),
                "alert":    (+0.02, +0.05, +0.01),
                "stressed": (-0.06, +0.10, -0.04),
            }
            pad = tone_map.get(tone, (0.0, 0.0, 0.0))
            _push("affect", {"pad": pad, "energy": energy, "tone": tone})
            return

        # Somatic candidate setpoints
        if ev == "SOMATIC_SETPOINT" or (ch in ("somatic", "control") and op == "SOMATIC_SETPOINT"):
            PAD = pl.get("PAD")
            if not PAD:
                tone = str(pl.get("tone", "neutral")).lower()
                energy = float(pl.get("energy", 0.5))
                base = list(self.BASELINE_PAD)
                if tone == "soothing":
                    base[0] += +0.05
                    base[1] += -0.08
                elif energy > 0.7:
                    base[1] += +0.12
                PAD = base
            _push("candidate", {"PAD": [float(x) for x in PAD][:3]})
            return

        # Chemistry field updates
        if ev == "CHEM_FIELD_UPDATE" or (ch == "chemistry" and op == "CHEM_FIELD_UPDATE"):
            field = dict(pl)
            self._chem_cache.update({k: float(field.get(k, 0.0)) for k in self.CHEM_TONES})
            _push("chemistry", {"field": dict(self._chem_cache)})
            return

        # Phase from sleep_wave_conductor
        if (ev == "SOMATIC_PHASE") or (ch == "somatic" and op == "SOMATIC_PHASE"):
            phase = str((pl.get("phase") or self._phase)).lower()
            if phase in self.PHASES():
                self._phase = phase
                _push("phase", {"phase": phase})
            return

        # Repair hooks
        if op == "REPAIR_REQUEST":
            self.post.to_TELEMETRY({"opcode": "REPAIR_ACK", "payload": pl})
            self.post.to_PLAN({
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "adrenaline",
                    "delta": +0.03,
                    "source": self.ACTOR_NAME,
                    "reason": "repair_request",
                },
            })
            return

        if op == "PLAN_EXPRESSION":
            self.post.to_TELEMETRY({"opcode": "PLAN_EXPRESSION_ACK", "payload": pl})
            return
    
    # ——— cadence ———
    def on_tick(self, dt: float | None = None):
        now = time.time()
        cutoff = now - float(self.WINDOW_SEC)
        self._buf = [e for e in self._buf if e["ts"] >= cutoff]

        if now - self._last_emit >= float(self.EMIT_PERIOD_SEC):
            self._last_emit = now
            pad, budget, hints = self._resolve_now()
            payload = {
                "PAD": pad,
                "emotions": {},
                "body_budget": budget,
                "hints": hints,
                "source": self.ACTOR_NAME,
                "ts": now,
            }

            # ── keep character-sheet state in sync with resolved setpoint ───
            stress = float(budget.get("stress", 0.0))
            energy = float(budget.get("energy", 0.5))
            mood = "stressed" if stress > 0.6 else "neutral"

            self.AFFECT_STATE = {
                "mood": mood,
                "valence": float(pad[0]),
                "arousal": float(pad[1]),
                "tags": ["resolver"],
                "tone": "somatic_resolver",
                "energy": energy,
                "coherence": 0.7,
                "chem_preset": "dynamic",
                "intent": "resolve",
                "ts": now,
                "source": self.ACTOR_NAME,
            }
            self.SOMATIC_STATE = {
                "body_type": "field",
                "posture": "neutral",
                "motion": "idle",
                "energy": energy,
                "anchor_id": "P20.somatic.resolver",
                "notes": "latest resolved setpoint",
                "last_setpoint_ts": now,
                "source": self.ACTOR_NAME,
            }

            # Publish as setpoint for the bus
            self.post.to_SOMATIC({"opcode": "SOMATIC_SETPOINT", "payload": payload})

            # Memory breadcrumb
            self.post.to_MEMORY({
                "opcode": "SOMATIC_RESOLVER_NOTE",
                "payload": {"pad": pad, "hints": hints, "window": len(self._buf)},
            })

            # serotonin reward if calm; cortisol if stressed
            if stress <= 0.35:
                self.post.to_PLAN({
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {
                        "chemical": "serotonin",
                        "delta": +0.03,
                        "source": self.ACTOR_NAME,
                        "reason": "resolve_serene",
                    },
                })
            else:
                self.post.to_PLAN({
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {
                        "chemical": "cortisol",
                        "delta": +0.04,
                        "source": self.ACTOR_NAME,
                        "reason": "resolve_tense",
                    },
                })

    # ——— core resolver ———
    def _resolve_now(self) -> tuple[list[float], dict, dict]:
        p, a, d = self.BASELINE_PAD
        explain = {"terms": []}

        cands = [e["payload"]["PAD"] for e in self._buf if e["kind"] == "candidate" and "PAD" in e["payload"]]
        if cands:
            cpad = [sum(v)/len(cands) for v in zip(*cands)]
            w = self._weights["candidate"]
            p += w * (cpad[0] - p)
            a += w * (cpad[1] - a)
            d += w * (cpad[2] - d)
            explain["terms"].append({"kind": "candidate.avg", "w": w, "pad": _round3(cpad)})

        affects = [e["payload"]["pad"] for e in self._buf if e["kind"] == "affect" and "pad" in e["payload"]]
        if affects:
            apad = [sum(v)/len(affects) for v in zip(*affects)]
            w = self._weights["affect"]
            p += w * apad[0]
            a += w * apad[1]
            d += w * apad[2]
            explain["terms"].append({"kind": "affect.mean", "w": w, "pad": _round3(apad)})

        if self._chem_cache:
            dv = 0.0
            da = 0.0
            for chem, gain in self.CHEM_TONES.items():
                val = float(self._chem_cache.get(chem, 0.0))
                if chem in ("dopamine", "serotonin"):
                    dv += gain * val
                else:
                    da += gain * val
            w = self._weights["chemistry"]
            p += w * dv
            a += w * da
            explain["terms"].append({"kind": "chemistry.bias", "w": w, "dv": _r3(dv), "da": _r3(da)})

        phase = self._phase
        if phase in self.PHASES():
            pr, ar, dr = self.PHASE_TONES.get(phase, (0.0, 0.0, 0.0))
            w = self._weights["phase"]
            p += w * pr
            a += w * ar
            d += w * dr
            explain["terms"].append({"kind": "phase", "phase": phase, "w": w, "pad": _round3((pr, ar, dr))})

        p = min(max(p, 0.0), 1.0)
        a = min(max(a, 0.0), 1.0)
        d = min(max(d, 0.0), 1.0)

        stress = max(0.0, min(1.0, 0.6 * a - 0.2 * p + (0.08 if self._phase == "sleep" else 0.0)))
        energy = max(0.0, min(1.0, 0.5 + 0.4 * a - (0.2 if self._phase == "sleep" else 0.0)))

        budget = {"stress": _r3(stress), "energy": _r3(energy)}
        hints = {"phase": phase, "explain": explain}
        return [_r3(p), _r3(a), _r3(d)], budget, hints

    # ——— intents ———
    def _intent_set_weights(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            payload = {}
        for k, v in (payload.get("weights") or {}).items():
            if k in self._weights:
                try:
                    self._weights[k] = float(v)
                except Exception:
                    pass
        self.post.to_TELEMETRY({"opcode": "WEIGHTS_SET", "payload": {"weights": self._weights}})
        return {"ok": True, "weights": dict(self._weights)}

    def _intent_set_params(self, payload: dict) -> dict:
        p = payload or {}
        if "window_sec" in p:
            try:
                self.WINDOW_SEC = max(2.0, float(p["window_sec"]))
            except Exception:
                pass
        if "emit_period_sec" in p:
            try:
                self.EMIT_PERIOD_SEC = max(0.5, float(p["emit_period_sec"]))
            except Exception:
                pass
        return {"ok": True, "window_sec": self.WINDOW_SEC, "emit_period_sec": self.EMIT_PERIOD_SEC}

    def _intent_smoke(self, payload: dict) -> dict:
        self.post.to_TRACER({"opcode": "SMOKE", "payload": {"note": "resolver hello"}})
        return {"ok": True}

    @staticmethod
    def PHASES():
        return ("wake", "daydream", "sleep")


