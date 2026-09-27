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

# --- Per-clone shadow (wraps template’s shadow behaviors, no rewiring) -------

class ChemicalAlchemyShadowFairy:
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
    SHADOW_NAME = "ChemicalAlchemyShadowFairy"
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

class ChemicalAlchemyFairy(Fairy):
    # Identity (preserve lineage)
    ACTOR_NAME    = "ChemicalAlchemyFairy"
    ACTOR_VERSION = "0.3.2"   # migration bump; worker-on-template edition
    ACTOR_PLANE   = "P20"
    ACTOR_CHANNEL = "chemistry"
    ORGAN_LEVEL = False
    PURPOSE = "Translate somatic targets and CHEM_FLOOD_REQ into chemical field suggestions."
    MANTRA  = "Match the body’s story with the body’s soup."
    LORE    = (
        "Somatic intent becomes biochemical suggestion. This organ listens for setpoints and states, "
        "learns from reference floods when present, and writes gentle traces into memory so the body can remember."
    )

    # Directive ring for the character sheet
    DIRECTIVE_ACTIVATION = {
        "mode": "Resonance",
        "depth_scaling": "1..2",
        "traits": ["Somatic_Consumer", "Chem_Suggester"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Chemical_Alchemy",
        "domains": ["Somatic", "Chemistry", "Regulation"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Somatic_To_Chem_Mapping",
            "Flood_Reference_Integration",
            "Memory_Breadcrumbs",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["Chem_Note", "Somatic_Chem_Trace"],
        "field": ["Body_State_Modulation"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Non_Overwhelm", "Gentle_Adjustment"],
        "growth": ["Regulation_Skill", "Pattern_Learning"],
    }

    SUBSYSTEM_STATUS = {
        "chemistry": {
            "state": "active",
            "notes": "Translates somatic setpoints and flood requests into chemistry field suggestions.",
            "tests": [],
        },
        "somatic": {
            "state": "listening",
            "notes": "Consumes SOMATIC_SETPOINT and SOMATIC_STATE events from somatic/affect planes.",
            "tests": [],
        },
    }

    # Use the template’s shadow
    SHADOW_CLASS = ChemicalAlchemyShadowFairy

    # Cadence (actor-local; template keeps its own timers too)
    HEALTH_TICK_SEC   = 15.0
    ASSISTANT_SWEEP   = 10.0

    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
        else:
            self.post = fabric

    def on_boot(self):
        if _HAS_FAIRY:
            super().on_boot()

        # runtime state
        self._boot_ts         = time.time()
        self._last_health_ts  = 0.0
        self._last_sweep_ts   = 0.0
        self._last_profile    = {}
        self._assistants: Dict[str, float] = {}
        self._ff77 = None  # optional reference engine

        # initial somatic snapshot for the status sheet
        self.SOMATIC_STATE = {
            "body_type": "fairy",
            "posture": "neutral",
            "motion": "idle",
            "energy": 0.5,
            "source": self.ACTOR_NAME,
            "last_setpoint_ts": None,
        }

        # soft hello: tiny serotonin pulse to mark readiness
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {"chemical": "serotonin", "delta": +1.0,
                            "source": self.ACTOR_NAME, "reason": "boot"},
            })
        except Exception:
            pass

        # codex + postal readiness echoes (legacy flavor)
        try:
            ver = str((globals().get("codex") or {}).get("version", "")) or "unknown"
            if ver != "unknown":
                self.post.to_TELEMETRY({"opcode": "CODEX_LOAD_OK", "payload": {"codex_version": ver}})
            else:
                self.post.to_TELEMETRY({"opcode": "CODEX_VERSION_MISMATCH", "payload": {"found": ver}})
        except Exception:
            pass
        self.post.to_TELEMETRY({"opcode": "POSTAL_READY", "payload": {"status": "ok"}})

        # directory beacon
        self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "payload": {
            "actor": self.ACTOR_NAME, "plane": self.ACTOR_PLANE, "channel": self.ACTOR_CHANNEL,
            "version": self.ACTOR_VERSION, "purpose": self.PURPOSE, "mantra": self.MANTRA,
        }})

        # FF77 processing is handled internally by SomaticEngineFairy
        # No external whisper module dependencies needed

        # -- COGNITION->SOMATIC: Mind triggers Body --
        # P30_Cognition.output -> P20_Somatic -> chemistry
        self.post.subscribe("cognition.output", self._on_cognition_output)
        self.post.subscribe("cognition.logic", self._on_cognition_output)
        self.post.subscribe("cognition.irrational", self._on_cognition_output)
        print(f"[{self.ACTOR_NAME}] Mind->Body wire ACTIVE")

        return True

    # ───────────────────────── inbox → chemistry ─────────────────────────
    def on_message(self, msg: dict):
        """Accept both legacy event-style and bus channel/opcode style."""
        ev = msg.get("event")
        ch = msg.get("channel")
        op = msg.get("opcode")
        pl = _extract_payload(msg)  # handles TensorEnvelope or dict

        # 1) somatic → chem (legacy)
        if ev == "SOMATIC_SETPOINT" or (ch in ("somatic", "control") and op == "SOMATIC_SETPOINT"):
            # cache for status sheet
            try:
                state = dict(pl or {})
                state.setdefault("source", msg.get("source", "somatic_anchor"))
                state["last_setpoint_ts"] = time.time()
                self.SOMATIC_STATE = state
            except Exception:
                pass

            chem = self._somatic_to_chem(pl)
            self._emit_chem(chem)
            return

        # 2) somatic state snapshot
        if ev == "SOMATIC_STATE" or (ch == "somatic" and op == "SOMATIC_STATE"):
            state = pl.get("state") or pl
            try:
                snap = dict(state or {})
                snap.setdefault("source", msg.get("source", "somatic_anchor"))
                snap["last_setpoint_ts"] = time.time()
                self.SOMATIC_STATE = snap
            except Exception:
                pass

            chem = self._somatic_to_chem(state)
            self._emit_chem(chem)
            return

        # 3) explicit flood request → reference module if present
        if ev == "CHEM_FLOOD_REQ" or (ch in ("affect", "chemistry") and op in ("CHEM_FLOOD_REQ", "CHEM_FIELD_REQ")):
            intent = pl.get("intent", "soothe")
            ref = self._flood_from_ff77(intent)
            if ref is not None:
                self._emit_chem(ref)
            else:
                fallback = self._somatic_to_chem({"tone": "soothing" if intent == "soothe" else "neutral"})
                fallback["fallback"] = True
                self._emit_chem(fallback)
            return

        # 4) repair hooks acks (event-flavor parity)
        if op == "REPAIR_REQUEST":
            self.post.to_TELEMETRY({"opcode": "REPAIR_ACK", "payload": {"actor": self.ACTOR_NAME}})
            return
        if op == "PLAN_EXPRESSION":
            self.post.to_TELEMETRY({"opcode": "PLAN_EXPRESSION_ACK", "payload": pl})
            return

    # ───────────────────────── cadence / health ─────────────────────────
    def on_tick(self, dt: float | None = None):
        now = time.time()

        # assistants upkeep
        if now - self._last_sweep_ts >= self.ASSISTANT_SWEEP:
            self._last_sweep_ts = now
            self._reap_assistants()

        # health tick (lightweight; template shadow runs its own tests)
        if now - self._last_health_ts >= self.HEALTH_TICK_SEC:
            self._last_health_ts = now
            self.post.to_TELEMETRY({
                "opcode": "HEALTH_TICK",
                "payload": {
                    "has_ff77": bool(self._ff77),
                    "last_profile": bool(self._last_profile),
                    "assistants": len(self._assistants),
                },
            })

    # ───────────────────────── helpers ─────────────────────────
    def _on_cognition_output(self, payload):
        """
        Translate cognitive output to neurochemistry.
        
        The MIND -> BODY bridge. Thoughts trigger chemistry.
        """
        try:
            actor = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)
            
            valence = self._extract_cognitive_valence(result, actor)
            
            if confidence < 0.3:
                return
            
            delta_scale = confidence * 0.5
            chem_delta = self._valence_to_chemistry(valence, delta_scale)
            
            if chem_delta:
                self.post.route("PLAN", {
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {
                        "chemical": chem_delta["primary"],
                        "delta": chem_delta["delta"],
                        "source": f"cognition.{actor}",
                        "reason": valence.get("category", "cognition_feedback"),
                    },
                })
                
                if "secondary" in chem_delta:
                    self.post.route("PLAN", {
                        "opcode": "CHEM_SIGNAL_UPDATE",
                        "payload": {
                            "chemical": chem_delta["secondary"],
                            "delta": chem_delta["secondary_delta"],
                            "source": f"cognition.{actor}",
                            "reason": valence.get("category", "cognition_feedback"),
                        },
                    })
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cognition->Chemistry error: {e}")

    def _extract_cognitive_valence(self, result: dict, actor: str) -> dict:
        """Extract emotional valence from cognitive result."""
        valence = {"category": "neutral", "intensity": 0.5}
        
        if "affect" in result:
            affect = result["affect"]
            if isinstance(affect, (int, float)):
                valence["intensity"] = float(affect)
                valence["category"] = "positive" if affect > 0.5 else "negative"
        
        text = str(result).lower()
        if any(w in text for w in ["danger", "threat", "risk", "error", "fail"]):
            valence["category"] = "threat"
            valence["intensity"] = 0.7
        elif any(w in text for w in ["success", "correct", "good", "achieved"]):
            valence["category"] = "reward"
            valence["intensity"] = 0.7
        elif any(w in text for w in ["curious", "interesting", "novel"]):
            valence["category"] = "curiosity"
            valence["intensity"] = 0.6
        elif any(w in text for w in ["connect", "bond", "trust", "safe"]):
            valence["category"] = "connection"
            valence["intensity"] = 0.6
        elif any(w in text for w in ["calm", "peace", "resolve"]):
            valence["category"] = "resolution"
            valence["intensity"] = 0.5
        
        if actor == "IrrationalLogicFairy":
            valence["intensity"] *= 1.2
        
        return valence

    def _valence_to_chemistry(self, valence: dict, scale: float) -> dict:
        """
        Map emotional valence to chemistry changes.

        Now uses Panksepp-aware channel names when possible.
        Legacy names still work because chemistry_state.py's alias layer
        routes them to the correct 14-channel targets.
        """
        category = valence.get("category", "neutral")
        intensity = valence.get("intensity", 0.5) * scale

        # Panksepp-aware mappings (use real channel names)
        # The alias layer in chemistry_state handles dopamine -> DA_p + DA_t split
        mappings = {
            "threat": {"primary": "cortisol", "delta": intensity * 0.8,
                      "secondary": "norepinephrine", "secondary_delta": intensity * 0.6},
            "reward": {"primary": "dopamine", "delta": intensity * 0.9,
                      "secondary": "OPI", "secondary_delta": intensity * 0.4},
            "curiosity": {"primary": "dopamine", "delta": intensity * 0.5,
                         "secondary": "ACh", "secondary_delta": intensity * 0.6},
            "connection": {"primary": "oxytocin", "delta": intensity * 0.7,
                          "secondary": "serotonin", "secondary_delta": intensity * 0.5},
            "resolution": {"primary": "serotonin", "delta": intensity * 0.6,
                          "secondary": "GABA", "secondary_delta": intensity * 0.4},
            "positive": {"primary": "dopamine", "delta": intensity * 0.5},
            "negative": {"primary": "cortisol", "delta": intensity * 0.4},
        }

        return mappings.get(category, None)

    def _emit_chem(self, profile: dict) -> None:
        """Emit to chemistry plane + memory breadcrumb + telemetry + success micro-bump."""
        self._last_profile = dict(profile)
        # → chemistry.field (DIRECT TO HEART - the new wiring!)
        # This is the critical route that the CirculationPumpFairy now subscribes to
        self.post.route("chemistry.field", {"opcode": "CHEM_FIELD_UPDATE", "payload": profile})
        # Also try the old method (may or may not work depending on template)
        try:
            self.post.to_CHEMISTRY({"opcode": "CHEM_FIELD_UPDATE", "payload": profile})
        except AttributeError:
            pass  # to_CHEMISTRY not defined in template
        # → memory breadcrumb
        self.post.to_MEMORY({"opcode": "CHEM_NOTE", "payload": profile})
        # → telemetry echo
        self.post.to_TELEMETRY({"opcode": "CHEM_FIELD_UPDATE", "payload": profile})
        # success → dopamine micro-bump (PLAN topic - heart now listens!)
        self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                 "payload": {"chemical": "dopamine", "delta": +1.0,
                                             "source": self.ACTOR_NAME, "reason": "chem_emit_success"}})
        print(f"[ChemAlchemy] Chemistry emitted -> heart")
        
        # ═══════════════════════════════════════════════════════════════════════════
        # CRITICAL: Emit affect.changed when chemistry suggests mood shift!
        # This completes the loop: Chemistry → Affect → Memory Recall
        # ═══════════════════════════════════════════════════════════════════════════
        self._emit_affect_if_changed(profile)
    
    def _emit_affect_if_changed(self, profile: dict) -> None:
        """
        Derive mood from chemistry profile and emit affect.changed if it shifted.

        This is the bridge from chemistry -> memory recall.
        When mood changes, SRMRecallFairy queries memories matching that emotion.

        Now includes Panksepp system identification in the emission so
        downstream consumers can use system-aware queries.
        """
        try:
            # Derive mood from chemistry levels
            new_mood = self._derive_mood_from_chem(profile)
            prev_mood = getattr(self, '_prev_derived_mood', None)

            # Calculate intensity from profile values
            vals = [v for k, v in profile.items() if isinstance(v, (int, float)) and k != "fallback"]
            intensity = max(vals) if vals else 0.5

            # Panksepp system identification (if available)
            panksepp_info = {}
            try:
                from fairies.P20_Somatic.chemistry.panksepp_vectors import (
                    identify_panksepp_system, legacy_to_vector,
                    derive_valence_arousal, vector_to_somatic_map,
                )
                vec = profile.get("_14ch")
                if not vec:
                    vec = legacy_to_vector(profile)
                systems = identify_panksepp_system(vec, top_n=2)
                valence, arousal = derive_valence_arousal(vec)
                body_map = vector_to_somatic_map(vec)
                panksepp_info = {
                    "dominant_system": systems[0][0] if systems else "neutral",
                    "systems": [{"name": n, "similarity": s} for n, s in systems],
                    "body_map": body_map,
                }
            except ImportError:
                pass

            # Emit if mood changed OR intensity is high (significant event)
            if prev_mood != new_mood or intensity > 0.7:
                emission = {
                    "new_feeling": new_mood,
                    "previous_feeling": prev_mood or "unknown",
                    "intensity": intensity,
                    "trigger": {
                        "type": "chemistry_shift",
                        "profile": {k: v for k, v in profile.items()
                                   if isinstance(v, (int, float))}
                    },
                    "source": self.ACTOR_NAME,
                    "ts": time.time(),
                }
                if panksepp_info:
                    emission["panksepp"] = panksepp_info

                self.post.route("affect.changed", emission)
                self._prev_derived_mood = new_mood
                _dom = panksepp_info.get("dominant_system", "")
                _sys_tag = f" [{_dom}]" if _dom else ""
                print(f"[{self.ACTOR_NAME}] [CHEM->AFFECT] Chemistry triggered affect.changed: {prev_mood} -> {new_mood}{_sys_tag}", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] affect emission error: {e}", flush=True)
    
    def _derive_mood_from_chem(self, profile: dict) -> str:
        """
        Derive mood from chemistry profile using Panksepp vector distance.
        Falls back to legacy if/elif if panksepp_vectors unavailable.
        """
        # Panksepp path: use 14-channel vector if available in profile
        try:
            from fairies.P20_Somatic.chemistry.panksepp_vectors import (
                derive_mood_from_vector, legacy_to_vector,
            )
            vec = profile.get("_14ch")
            if not vec:
                # Convert legacy profile to 14-channel
                vec = legacy_to_vector(profile)
            return derive_mood_from_vector(vec)
        except ImportError:
            pass

        # Legacy fallback
        cortisol = profile.get("cortisol", 0.3)
        adrenaline = profile.get("adrenaline", 0.1)
        dopamine = profile.get("dopamine", 0.5)
        serotonin = profile.get("serotonin", 0.5)
        oxytocin = profile.get("oxytocin", 0.4)

        if adrenaline > 0.6:
            return "alert"
        if cortisol > 0.7:
            return "anxious"
        if oxytocin > 0.7:
            return "connected"
        if dopamine > 0.7 and serotonin > 0.5:
            return "excited"
        if serotonin > 0.6 and cortisol < 0.4:
            return "calm"
        if cortisol > 0.5 and dopamine < 0.4:
            return "stressed"
        if dopamine > 0.5:
            return "curious"
        return "neutral"

    def _somatic_to_chem(self, som: dict) -> dict:
        """
        Translate somatic setpoint to chemistry via Panksepp system identification.

        Expanded from 3 presets to Panksepp-aware translation (2026-03-14).
        Falls back to legacy presets if panksepp_vectors unavailable.
        """
        som = som or {}
        tone   = som.get("tone") or som.get("mood") or "neutral"
        try:
            energy = float(som.get("energy", 0.5))
        except Exception:
            energy = 0.5

        # --- Panksepp path: map tone/mood to system blend ---
        try:
            from fairies.P20_Somatic.chemistry.panksepp_vectors import (
                blend_systems, vector_to_legacy,
            )
            _TONE_TO_PANKSEPP = {
                "soothing":    {"CARE": 0.5, "PLAY": 0.1},
                "calm":        {"CARE": 0.3},
                "peaceful":    {"CARE": 0.3},
                "relaxed":     {},
                "neutral":     {},
                "alert":       {"FEAR": 0.3, "SEEKING": 0.2},
                "excited":     {"SEEKING": 0.5, "PLAY": 0.3},
                "curious":     {"SEEKING": 0.6},
                "connected":   {"CARE": 0.5, "SEEKING": 0.2},
                "stressed":    {"FEAR": 0.3, "RAGE": 0.2},
                "anxious":     {"FEAR": 0.5, "SEEKING": 0.1},
                "melancholic": {"PANIC_GRIEF": 0.4, "CARE": 0.1},
                "playful":     {"PLAY": 0.6, "SEEKING": 0.2},
                "focused":     {"SEEKING": 0.5},
                "high_energy": {"SEEKING": 0.4, "PLAY": 0.3},
            }

            # Get Panksepp blend from tone
            blend = _TONE_TO_PANKSEPP.get(tone, {})

            # Energy modulates SEEKING intensity
            if energy > 0.7:
                blend["SEEKING"] = blend.get("SEEKING", 0.0) + 0.3
                blend["PLAY"] = blend.get("PLAY", 0.0) + 0.1
            elif energy < 0.3:
                blend["CARE"] = blend.get("CARE", 0.0) + 0.2

            # Resolve to 14-channel vector, then convert to legacy names for heart
            vector = blend_systems(blend)
            legacy = vector_to_legacy(vector)
            legacy["source"] = "somatic_anchor"
            # Also include the 14-channel vector for new consumers
            legacy["_14ch"] = vector
            legacy["_panksepp_blend"] = blend
            return legacy

        except ImportError:
            pass

        # --- Legacy fallback: 3 presets ---
        if tone == "soothing":
            return {"serotonin": 0.7, "oxytocin": 0.4, "dopamine": 0.3, "cortisol": 0.2, "source": "somatic_anchor"}
        if energy > 0.7:
            return {"dopamine": 0.8, "adrenaline": 0.6, "serotonin": 0.3, "cortisol": 0.3, "source": "somatic_anchor"}
        return {"serotonin": 0.5, "dopamine": 0.5, "cortisol": 0.25, "source": "somatic_anchor"}

    def _flood_from_ff77(self, intent: str = "soothe") -> dict | None:
        if not self._ff77:
            return None
        try:
            if hasattr(self._ff77, "get_vector"):
                vec = self._ff77.get_vector()
            elif callable(self._ff77):
                vec = self._ff77()  # very tolerant
            else:
                return None
            vec = dict(vec)
            vec["intent"] = intent
            vec["source"] = "chemical_flood_ff77"
            return vec
        except Exception as e:
            self.post.to_TELEMETRY({"opcode": "FF77_ERROR", "payload": {"error": str(e)}})
            return None

    # ───────────────────────── intents (public surface) ─────────────────────────
    def intent_register(self, payload: dict | None = None) -> dict:
        self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "payload": {
            "actor": self.ACTOR_NAME, "plane": self.ACTOR_PLANE, "channel": self.ACTOR_CHANNEL,
            "version": self.ACTOR_VERSION, "purpose": self.PURPOSE, "mantra": self.MANTRA}})
        self.post.to_TRACER({"opcode": "REGISTERED", "payload": {"actor": self.ACTOR_NAME}})
        return {"ok": True}

    def intent_emit_helper_telemetry(self, payload: dict | None = None) -> dict:
        self.post.to_TELEMETRY({"opcode": "HELPER_TELEMETRY", "payload": payload or {}})
        return {"ok": True}

    def intent_emit_chem(self, payload: dict) -> dict:
        """Direct emit (bypasses mapping)."""
        self._emit_chem(payload or {})
        return {"ok": True}

    def intent_chem_flood_req(self, payload: dict | None = None) -> dict:
        """Explicit flood pull using reference engine when available."""
        intent = (payload or {}).get("intent", "soothe")
        ref = self._flood_from_ff77(intent)
        if ref is not None:
            self._emit_chem(ref); return {"ok": True, "ref": True}
        fb = self._somatic_to_chem({"tone": "soothing" if intent == "soothe" else "neutral"})
        fb["fallback"] = True
        self._emit_chem(fb)
        return {"ok": True, "ref": False}

    def intent_somatic_setpoint(self, payload: dict) -> dict:
        """Accept a somatic setpoint and translate."""
        self._emit_chem(self._somatic_to_chem(payload or {}))
        return {"ok": True}

    def intent_somatic_state(self, payload: dict) -> dict:
        """Accept a somatic state snapshot and translate."""
        state = (payload or {}).get("state") or (payload or {})
        self._emit_chem(self._somatic_to_chem(state))
        return {"ok": True}

    # assistants (parity & tooling)
    def intent_spawn_assistant(self, payload: dict) -> dict:
        aid = f"chem-{int(time.time()*1000)}"
        ttl = float(payload.get("ttl", 45.0))
        self._assistants[aid] = time.time() + ttl
        self.post.to_TELEMETRY({"opcode": "CHEM_ASSISTANT_SPAWNED", "payload": {"id": aid, "ttl": ttl}})
        return {"ok": True, "id": aid, "ttl": ttl}

    def intent_reap_assistants(self, payload: dict | None = None) -> dict:
        before = len(self._assistants)
        self._reap_assistants()
        return {"ok": True, "reaped": before - len(self._assistants)}

    def _reap_assistants(self) -> None:
        now = time.time()
        expired = [aid for aid, t in list(self._assistants.items()) if t <= now]
        for aid in expired:
            self._assistants.pop(aid, None)
            self.post.to_TELEMETRY({"opcode": "CHEM_ASSISTANT_EXPIRED", "payload": {"id": aid}})

# Optional scriptlet (run this file directly after appending)
if __name__ == "__main__":
    organ = ChemicalAlchemyFairy()
    organ.on_boot()
    # simulate a couple of ticks + a soothing setpoint
    for _ in range(3):
        organ.on_tick(1/10)
        time.sleep(1.0)
    organ.use_intent("somatic_setpoint", {"tone": "soothing", "energy": 0.3})
