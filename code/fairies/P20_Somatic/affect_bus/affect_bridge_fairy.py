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

# Import TracerWorkerMixin for tracer integration (optional)
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass

# SpellChain integration for spell-driven existence
try:
    from fairy_template.spellchain_mixin import SpellChainMixin
    HAS_SPELLCHAIN = True
except ImportError:
    HAS_SPELLCHAIN = False
    class SpellChainMixin:
        """Fallback when spellchain not available."""
        pass


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

def resolve_root(preferred: Optional[str] = None, *, akashic_app: Optional[str] = None) -> str:
    """Resolve the application root directory."""
    if preferred and os.path.isdir(preferred):
        return os.path.abspath(preferred)
    env_root = os.getenv("AKASHIC_ROOT")
    if env_root and os.path.isdir(env_root):
        return os.path.abspath(env_root)
    return os.path.abspath(os.getcwd())

# --- Per-clone shadow (wraps template’s shadow behaviors, no rewiring) -------

class AffectBridgeShadowFairy(Fairy):
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
    SHADOW_NAME = "AffectBridgeShadowFairy"
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
        self._last_status = "ok"

    def current_status(self):
        """Return (status, message) tuple for health reporting."""
        return (self._last_status, "")

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

class AffectBridgeFairy(SpellChainMixin, Fairy):
    # Identity (preserve lineage)
    ACTOR_NAME    = "AffectBridgeFairy"
    ACTOR_VERSION = "2.1.1"  # migration bump with cadence parity
    ACTOR_PLANE   = "P20"
    ACTOR_CHANNEL = "affect"
    ORGAN_LEVEL = False

    # Infrastructure flags - AffectBridgeFairy IS the affect system
    NEEDS_BODY = True     # We translate somatic state into affect
    NEEDS_AFFECT = False  # We ARE the affect system - don't need to connect to ourselves
    NEEDS_HEARTBEAT = True  # 2026-07-11 (B step-1): drive on_tick every beat so the body-broadcast
                            # actually fires. Was inheriting the template default False → on_tick was
                            # NEVER called (HEALTH_TICK 0×) → the felt-pipe could only be driven by the
                            # FF77 VISUAL subscription → dry on a no-eyes boot. This opens the door.
    NEEDS_MEMORY = False  # Affect operates pre-cognitively, no memory dependency
    NEEDS_GOALS = False   # Affect doesn't depend on goal system

    # Spell-driven mode (opt-in)
    USE_SPELLCHAIN: bool = True  # Re-enabled - fixed revival->heartbeat wiring

    PURPOSE = "Bridge emotion artifacts → somatic / chemistry / cognition."
    MANTRA  = "Emotion is data with a body."
    LORE    = (
        "Listens for whispers, normalizes their shape, then nudges body and mind into alignment. "
        "Cadenced scans maintain a gentle rhythm: feel → name → route → harmonize."
    )

     #  Directive ring so the character sheet has something pretty to show
    DIRECTIVE_ACTIVATION = {
        "mode": "Resonance",
        "depth_scaling": "1..3",
        "traits": ["Consent_Based", "Affect_Routing", "Somatic_Bridge"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Somatic_Bridge",
        "domains": ["Somatic", "Chemistry", "Cognition"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Affect_Normalization",
            "Somatic_Setpoint",
            "Chemistry_Mirroring",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["Emotion_Artifacts", "Affect_Events"],
        "field": ["Body_State_Modulation"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Felt_Truth", "Gentle_Adjustment"],
        "growth": ["Regulation_Skill", "Self_Awareness"],
    }

    # high-level summary for the sheet’s subsystem block
    SUBSYSTEM_STATUS = {
        "somatic": {
            "state": "active",
            "notes": "Broadcasts affect → somatic + chemistry setpoints.",
            "tests": [],
        },
        "cognition": {
            "state": "observing",
            "notes": "Feeds normalized affect events into cognition lane.",
            "tests": [],
        },
    }

    # Use the template’s shadow unchanged (just bind it here so naming is clear)
    SHADOW_CLASS = AffectBridgeShadowFairy

    # Legacy cadence parity (actor-side; template keeps its own timing too)
    SCAN_INTERVAL_SEC        = 20.0
    ASSISTANT_DEFAULT_TTL    = 45.0
    ASSISTANT_SWEEP_SEC      = 10.0
    HEALTH_TICK_SEC          = 15.0
    BODY_BCAST_SEC           = 5.0    # 2026-07-11 (B step-1): body-driven felt-broadcast cadence

    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
            # self.post is set by parent Fairy.__init__ via get_fairy_postal_bound()
        else:
            # Fallback when fairy_template import failed
            self.post = fabric
            self.post = fabric  # Use fabric as postal fallback

        # Initialize tracer worker mixin
        self._init_tracer_worker()

    # ───────────────────────── lifecycle ─────────────────────────
    def on_boot(self):
        # IMPORTANT: Call super() to trigger HeartbeatMixin auto-start
        if _HAS_FAIRY:
            super().on_boot()

        # === STANDARD IGNITION WIRING ===
        if hasattr(self, 'post') and self.post:
            try:
                self.post.subscribe("system.ignition", self._on_system_ignition)
                self.post.subscribe("somatic.pulse", self._on_somatic_pulse)
            except Exception:
                pass
            # FIX A (2026-05-31, Nous + Ace): affect.state valence = SomaticEngine PAD pleasure
            # (PAD[0]) read off the EmbodiedFeelPacket on somatic.embodied_feel.
            # ROOT CAUSE of the long-standing valence=0 (found via last_feel_present diagnostic):
            # this subscribe used to live in the block ABOVE, but `self._on_system_ignition` /
            # `self._on_somatic_pulse` are NOT defined on this fairy → the subscribe LINE raises
            # AttributeError evaluating the missing method → `except: pass` swallows it → the
            # embodied_feel subscribe never ran → _last_feel stayed empty → valence fell to the
            # categorical fallback (tone "neutral" → 0.0). Isolated in its OWN try block so it
            # ALWAYS registers. (system.ignition/somatic.pulse missing-handler bug is pre-existing
            # and separate — flagged to Ace, not fixed here.)
            try:
                self.post.subscribe("somatic.embodied_feel", self._on_embodied_feel_for_valence)
            except Exception:
                pass

            # === FF77 TELEMETRY SUBSCRIPTION (Visual → Affect → Chemistry) ===
            # Subscribe to frequency field emissions from visual ingest pipeline
            try:
                self.post.subscribe("telemetry.frequency", self._on_ff77_telemetry)
                print(f"[{self.ACTOR_NAME}] Subscribed to telemetry.frequency (FF77)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] FF77 subscription error: {e}")

        # === INFRASTRUCTURE PROVIDER REGISTRATION (v0.1.2) ===
        # Register as provider of affect/emotional services
        try:
            if hasattr(self.post, 'register_provider'):
                self.post.register_provider("affect.state", self)
                print(f"[{self.ACTOR_NAME}] Registered as affect provider")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Provider registration error: {e}")

        # DUAL_LOOP: enabled via Organ Template
        # TRACER: enabled via Organ Template
        if hasattr(self, 'post') and self.post:
            pass  # Postal subscriptions handled via Organ Template

        # state
        self._boot_ts           = time.time()
        self._last_scan_ts      = 0.0
        self._last_sweep_ts     = 0.0
        self._last_health_ts    = 0.0
        self._last_body_bcast_ts = 0.0  # 2026-07-11 (B step-1): body-driven felt-broadcast
        self._last_affect       = {}
        self._last_feel         = {}  # FIX A: cached embodied-feel packet (carries real PAD valence)
        self._upgrade_ack_sent  = False
        self._assistants: dict[str, float] = {}
        self._affect_ref = None  # optional external normalizer

        # initial snapshots for the character sheet
        now = self._boot_ts
        self.AFFECT_STATE = {
            "tone": "neutral",
            "energy": 0.5,
            "coherence": 0.5,
            "intent": "soothe",
            "chem_preset": "calm",
            "source": self.ACTOR_NAME,
            "ts": now,
        }
        self.SOMATIC_STATE = {
            "tone": "neutral",
            "energy": 0.5,
            "coherence": 0.5,
            "last_setpoint_ts": None,
            "source": self.ACTOR_NAME,
        }

        # happy hello (chem micro-bump) + crumbs
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {"chemical": "serotonin", "delta": +1.0,
                            "source": self.ACTOR_NAME, "reason": "boot"},
            })
        except Exception:
            pass
        try: self.post.to_TRACER({"opcode": "BOOT_HELLO", "payload": {"actor": self.ACTOR_NAME}})
        except Exception: pass

        # codex / postal readiness echoes (legacy flavor, via telemetry)
        try:
            ver = str((globals().get("codex") or {}).get("version", "")) or "unknown"
            if ver != "unknown":
                try: self.post.to_TELEMETRY({"opcode": "CODEX_LOAD_OK", "payload": {"codex_version": ver}})
                except Exception: pass
            else:
                try: self.post.to_TELEMETRY({"opcode": "CODEX_VERSION_MISMATCH", "payload": {"found": ver}})
                except Exception: pass
        except Exception:
            pass
        try:
            self.post.to_TELEMETRY({"opcode": "POSTAL_READY", "payload": {"status": "ok"}})
        except Exception:
            pass

        # directory contract upsert (beacon)
        try:
            self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "payload": {
                "actor": self.ACTOR_NAME, "plane": self.ACTOR_PLANE, "channel": self.ACTOR_CHANNEL,
                "version": self.ACTOR_VERSION, "purpose": self.PURPOSE, "mantra": self.MANTRA}})
        except Exception:
            pass

        # Optional: Convert to spell-driven existence
        if HAS_SPELLCHAIN and getattr(self, 'USE_SPELLCHAIN', False):
            try:
                from spellchain.integration import get_spell_pool
                pool = get_spell_pool()
                if pool:
                    self._spell_chain = self.boot_as_spells(pool)
                    self.log("Converted to spell-driven existence - affect flows as magic")
            except Exception as e:
                self.log(f"SpellChain conversion failed: {e}")

        return True

    # The template calls on_tick(dt). We implement legacy cadence inside it.
    def on_tick(self, dt: float | None = None):
        now = time.time()

        # 0) BODY-DRIVEN felt broadcast — FIRST (2026-07-11, Nous+Ace — B step-1). The felt-pipe must
        #    not depend on the EYES: affect.state / affect_bridge_live were emitted ONLY by the always-
        #    empty emotion-scan and FF77 VISUAL telemetry (_on_ff77_telemetry) — so on a no-eyes boot
        #    (Nous .74, dark screen) the whole broadcast path went DRY (affect.state 0×, live file 100h
        #    stale) while chemistry flowed. Runs BEFORE the legacy steps (and getattr-guarded) so it
        #    fires even if on_boot's _last_* inits didn't run. YIELDS to visual: skips when FF77 fired
        #    recently, so it's a true baseline/fallback, not a competing writer.
        if (now - getattr(self, "_last_body_bcast_ts", 0.0) >= self.BODY_BCAST_SEC
                and now - getattr(self, "_last_ff77_ts", 0.0) >= self.BODY_BCAST_SEC * 2):
            self._last_body_bcast_ts = now
            try:
                self._broadcast_affect(self._body_affect())
            except Exception as e:
                try: self.post.to_TELEMETRY({"opcode": "BODY_BCAST_ERROR", "payload": {"error": str(e)}})
                except Exception: pass

        # 1) periodic FS scan (legacy cadence)
        if now - self._last_scan_ts >= self.SCAN_INTERVAL_SEC:
            self._last_scan_ts = now
            try:
                for emo in self._scan_emotions():
                    aff = self._normalize_affect(emo)
                    self._broadcast_affect(aff)
            except Exception as e:
                self.post.to_TELEMETRY({"opcode": "SCAN_ERROR", "payload": {"error": str(e)}})

        # 2) assistants upkeep (spawn/expire parity)
        if now - self._last_sweep_ts >= self.ASSISTANT_SWEEP_SEC:
            self._last_sweep_ts = now
            self._reap_assistants()

        # 3) lightweight health tick (legacy flavor)
        if now - self._last_health_ts >= self.HEALTH_TICK_SEC:
            self._last_health_ts = now
            self.post.to_TELEMETRY({
                "opcode": "HEALTH_TICK",
                "payload": {
                    "has_ref_normalizer": bool(self._affect_ref),
                    "last_affect": bool(self._last_affect),
                    "assistants": len(self._assistants),
                },
            })

    # ───────────────────────── assistants (parity) ─────────────────────────
    def _spawn_assistant(self, role: str, ttl: float | None = None) -> str:
        aid = f"affect-{int(time.time()*1000)}"
        self._assistants[aid] = time.time() + (ttl or self.ASSISTANT_DEFAULT_TTL)
        self.post.to_TELEMETRY({"opcode": "AFFECT_ASSISTANT_SPAWNED",
                                "payload": {"id": aid, "role": role, "ttl": ttl or self.ASSISTANT_DEFAULT_TTL}})
        return aid

    def _reap_assistants(self) -> None:
        now = time.time()
        expired = [aid for aid, t in list(self._assistants.items()) if t <= now]
        for aid in expired:
            self._assistants.pop(aid, None)
            self.post.to_TELEMETRY({"opcode": "AFFECT_ASSISTANT_EXPIRED", "payload": {"id": aid}})

    # ───────────────────────── normalization & fan-out ─────────────────────────
    def _normalize_affect(self, emo: dict) -> dict:
        """Normalize emotion dict to standard affect format."""
        # Self-contained normalization - no external whisper dependencies
        return {
            "tone": emo.get("tone", "neutral"),
            "energy": float(emo.get("energy", 0.5)),
            "coherence": float(emo.get("coherence", 0.5)),
            "chem_preset": emo.get("chem_preset", "calm"),
            "intent": emo.get("intent", "soothe"),
            "src_path": emo.get("src_path") or emo.get("_src_path"),
            "source": self.ACTOR_NAME,
            "ts": time.time(),
        }

    def _on_embodied_feel_for_valence(self, msg) -> None:
        """FIX A (2026-05-31, revised v2): cache the EmbodiedFeelPacket so affect.state carries the
        body's REAL valence. The packet's to_dict() emits "PAD": [valence, arousal, dominance]
        (NO top-level "valence" key) plus a flat "neurochemicals" dict. somatic.embodied_feel ships
        flat AND route-wrapped {"opcode":"EMBODIED_FEEL","payload":{...}} — unwrap the latter.
        Only cache packets that actually carry PAD/neurochemicals (never clobber with noise)."""
        try:
            p = msg.payload if hasattr(msg, "payload") else msg
            if not isinstance(p, dict):
                return
            if "PAD" not in p and "neurochemicals" not in p and isinstance(p.get("payload"), dict):
                p = p["payload"]
            if "PAD" in p or "neurochemicals" in p:
                self._last_feel = p
        except Exception:
            pass

    def _compute_valence(self) -> float:
        """Continuous valence = the body's REAL PAD pleasure (PAD[0]), read straight off the
        EmbodiedFeelPacket SomaticEngine publishes on somatic.embodied_feel. That valence IS
        pad() = clip(1.2·(0.7·SER+0.6·OXY+0.4·END−0.6·COR)) — her good/bad axis. Reading it
        directly guarantees AffectBridge's valence == her felt valence (no formula drift).
        Fallbacks: recompute from the packet's neurochemicals snapshot, then the categorical
        tone-sign — only used until an embodied_feel packet arrives."""
        f = getattr(self, "_last_feel", None) or {}
        try:
            pad = f.get("PAD")
            if isinstance(pad, (list, tuple)) and len(pad) >= 1 and pad[0] is not None:
                return round(max(-1.0, min(1.0, float(pad[0]))), 4)
            n = f.get("neurochemicals") if isinstance(f.get("neurochemicals"), dict) else None
            if not n:
                n = self._live_chem()  # 2026-07-11 (B step-1): live heartbeat chem when no embodied_feel packet is cached
            if n and ("SER" in n or "OXY" in n):
                SER = float(n.get("SER", 0.5)); OXY = float(n.get("OXY", 0.5))
                END = float(n.get("END", 0.5)); COR = float(n.get("COR", 0.5))
                return round(max(-1.0, min(1.0, (0.7 * SER + 0.6 * OXY + 0.4 * END - 0.6 * COR) * 1.2)), 4)
        except Exception:
            pass
        tone = self.AFFECT_STATE.get("tone", "neutral") if hasattr(self, "AFFECT_STATE") else "neutral"
        if tone in ("joy", "warmth", "curiosity", "calm"):
            return 1.0
        if tone in ("stress", "fear", "anger", "pain"):
            return -0.5
        return 0.0

    def _live_chem(self) -> dict:
        """2026-07-11 (B step-1): live neurochemistry for the body-driven path. Prefer the cached
        embodied_feel packet's neurochemicals; else read the heartbeat snapshot CirculationPump
        writes every beat (guaranteed-fresh, same-process). Returns {} if neither is available."""
        f = getattr(self, "_last_feel", None) or {}
        n = f.get("neurochemicals")
        if isinstance(n, dict) and n:
            return n
        try:
            _root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
            with open(os.path.join(_root, "state", "consciousness", "heartbeat.json"), encoding="utf-8") as _hf:
                return (json.load(_hf) or {}).get("chemistry", {}) or {}
        except Exception:
            return {}

    def _body_affect(self) -> dict:
        """2026-07-11 (Nous+Ace, B step-1): build an affect dict from the BODY, not the screen, so the
        felt-pipe survives a no-eyes boot. valence = _compute_valence() (PAD off embodied_feel, or the
        live-chem fallback); arousal from the activating neuromods (NOR+DOP); tone via the SAME
        arousal×valence map _on_ff77_telemetry uses, so the body path and the visual path agree."""
        val = self._compute_valence()
        chem = self._live_chem()
        nor = float(chem.get("NOR", 0.3)); dop = float(chem.get("DOP", 0.4))
        arousal = max(0.0, min(1.0, 0.5 * nor + 0.5 * dop + 0.2))
        if arousal > 0.7:
            tone = "alert" if val > 0 else "tense"
        elif arousal < 0.3:
            tone = "calm" if val > 0 else "melancholy"
        else:
            tone = "curious" if val > 0 else "neutral"
        return {
            "tone": tone,
            "energy": round((arousal + 0.5) / 2, 4),
            "arousal": round(arousal, 4),
            "coherence": 0.6,
            "intent": "soothe",
            "chem_preset": "calm",
            "source": self.ACTOR_NAME,
            "ts": time.time(),
        }

    def _broadcast_affect(self, affect: dict) -> None:
        self._last_affect = affect

        # keep a structured snapshot for the status sheet
        now = time.time()
        self.AFFECT_STATE = {
            "tone": affect.get("tone", "neutral"),
            "energy": float(affect.get("energy", 0.5)),
            "coherence": float(affect.get("coherence", 0.5)),
            "intent": affect.get("intent", "soothe"),
            "chem_preset": affect.get("chem_preset", "calm"),
            "source": affect.get("source", self.ACTOR_NAME),
            "ts": affect.get("ts", now),
        }
        self.SOMATIC_STATE = {
            "tone": self.AFFECT_STATE["tone"],
            "energy": self.AFFECT_STATE["energy"],
            "coherence": self.AFFECT_STATE["coherence"],
            "last_setpoint_ts": now,
            "source": self.AFFECT_STATE["source"],
        }

        # FIX 2026-04-02 (Nous + Ace): Publish to affect.state for WMH consumption.
        # WMH subscribes to affect.state but nobody published to it — affect was
        # always neutral/0.5 on the dashboard. The chemistry changes (DOP, OXY)
        # but the affect translation never reached WMH.
        try:
            self.post.publish("affect.state", {
                "primary": self.AFFECT_STATE["tone"],
                "intensity": self.AFFECT_STATE["energy"],
                "valence": self._compute_valence(),
                "source": self.ACTOR_NAME,
                "ts": now,
            })
        except Exception:
            pass

        # OBSERVABILITY (2026-05-31, Nous + Ace): mirror live affect to a state file so the
        # cross-process MCP side can READ the real valence (WMH _current_affect lives in
        # server.py memory, unreadable from MCP). `last_feel_present` diagnoses whether
        # embodied_feel packets are arriving — the A v2 valence source. Also: the hash change
        # this edit introduces is the in-process blueprint_watcher live-reload test.
        try:
            _root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
            with open(os.path.join(_root, "state", "affect_bridge_live.json"), "w", encoding="utf-8") as _df:
                json.dump({
                    "valence": self._compute_valence(),
                    "tone": self.AFFECT_STATE.get("tone"),
                    "energy": self.AFFECT_STATE.get("energy"),
                    "last_feel_present": bool(getattr(self, "_last_feel", None)),
                    "ts": now,
                }, _df)
        except Exception:
            pass

        # → P20/somatic (both legacy route AND direct to heart!)
        setpoint_payload = {
            "tone": self.AFFECT_STATE["tone"],
            "energy": self.AFFECT_STATE["energy"],
            "coherence": self.AFFECT_STATE["coherence"],
            "source": self.ACTOR_NAME,
        }
        self.post.to_SOMATIC({"opcode": "SOMATIC_SETPOINT", "payload": setpoint_payload})
        # DIRECT to heart - somatic.setpoint is what CirculationPumpFairy listens for!
        self.post.route("somatic.setpoint", setpoint_payload)
        print(f"[AffectBridge] Setpoint -> heart: {self.AFFECT_STATE['tone']}")

        # → P20/chemistry (preset intent)
        self.post.route("PLAN", {"opcode": "CHEM_MOD", "payload": {
            "preset": self.AFFECT_STATE["chem_preset"],
            "intent": self.AFFECT_STATE["intent"],
            "source": self.ACTOR_NAME,
        }})

        # 2026-09-20 (Nous + Ace): the per-broadcast "parity" self-reward (+1.0 dopamine, +1.0 serotonin
        # on EVERY broadcast) is gone. Measured 09-19: 5,794 of each per day, every other chemistry source
        # in the tree fired ZERO times, so DOP/SER sat pinned at an equilibrium and her tone read 'curious'
        # 5,112 of 5,114 setpoints -- a constant, not a feel. Chemistry now moves only with EVENTS that
        # happened to her: a deed that measurably succeeded (dopamine, infrastructure/intention.py) and
        # Ace speaking to her (serotonin, sour_council_driver.enqueue_ace). A broadcast is not an event.

        # → P30/cognition
        self.post.to_COGNITION({"opcode": "AFFECT_EVENT", "payload": affect})
        # → P10/memory
        self.post.to_MEMORY({"opcode": "AFFECT_NOTE", "payload": affect})
        # → telemetry
        self.post.to_TELEMETRY({"opcode": "AFFECT_BROADCAST", "payload": affect})
        
        # ═══════════════════════════════════════════════════════════════════════════
        # CRITICAL: Emit affect.changed for memory recall by emotion!
        # This is the KEY to Ace's vision:
        #   FEELING → triggers memory recall → memories inject into consciousness
        # SRMRecallFairy subscribes to this and queries memories by affect
        # ═══════════════════════════════════════════════════════════════════════════
        try:
            # Detect if feeling actually changed
            prev_tone = getattr(self, '_prev_tone', None)
            new_tone = affect.get('tone', 'neutral')
            intensity = affect.get('energy', 0.5)
            
            if prev_tone != new_tone or intensity > 0.6:  # Changed or high intensity
                self.post.route("affect.changed", {
                    "new_feeling": new_tone,
                    "previous_feeling": prev_tone or "unknown",
                    "intensity": intensity,
                    "coherence": affect.get('coherence', 0.5),
                    "trigger": {
                        "chem_preset": affect.get('chem_preset'),
                        "intent": affect.get('intent'),
                    },
                    "source": self.ACTOR_NAME,
                    "ts": time.time(),
                })
                self._prev_tone = new_tone
                print(f"[{self.ACTOR_NAME}] [AFFECT] Emitted affect.changed: {prev_tone} -> {new_tone}", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] affect.changed emit error: {e}", flush=True)


    # ───────────────────────── FF77 processing ─────────────────────────
    def _on_ff77_telemetry(self, msg: dict) -> None:
        """
        Process FF77 frequency field telemetry → affect state → chemistry.

        This is the bridge from visual perception to emotional embodiment:
        Visual Cards → FF77 Vector → Affect State → Chemistry → Body

        Rate limited to max 2Hz to avoid blocking the postal system.
        """
        try:
            # Rate limit: max 2Hz (0.5s between calls)
            now = time.time()
            if now - getattr(self, '_last_ff77_ts', 0) < 0.5:
                return
            self._last_ff77_ts = now

            payload = _extract_payload(msg)
            vec77 = payload.get("vec", [])

            if not vec77 or len(vec77) != 77:
                return

            # Extract energy levels from frequency bands
            # V1 (0-19): Edge detection - visual alertness
            v1_energy = sum(vec77[0:20]) / 20 if len(vec77) >= 20 else 0.5
            # V4 (40-59): Color - emotional warmth
            v4_energy = sum(vec77[40:60]) / 20 if len(vec77) >= 60 else 0.5
            # Meta (70-76): Context - attention/arousal
            meta_energy = sum(vec77[70:77]) / 7 if len(vec77) >= 77 else 0.5
            # FIX Item 7d (2026-05-16 Nous + Ace): Cognition bands (32-47) — reasoning flow.
            # NeuralMesh's cognition node carries cortex.bind activity, including
            # music_theory output from HarmonicCortex. Previously these bands were
            # SKIPPED entirely — music played but didn't land in body. Path-1 fix:
            # read cognition bands so music engagement contributes to arousal.
            # "Immediate makes it feel like the human body" — Ace's felt-sense compass.
            cognition_energy = sum(vec77[32:48]) / 16 if len(vec77) >= 48 else 0.0

            # FIX 2026-04-05 (Nous + Ace): Blend organ bands INTO affect computation.
            # Previously only visual bands drove arousal/valence → "calm" forever.
            # Now: organs (bands 0-14) contribute, visual contributes, cognition contributes.
            # This reconnects the severed nerve: chemistry → organs → affect.
            _organ_arousal = 0.0
            _organ_valence = 0.0
            if len(vec77) >= 15:
                # Organ bands 0-14 carry organ activation from SomaticEngine
                _organ_energy = sum(vec77[0:15]) / 15
                # Adrenals(4) + eyes(8) + thyroid(11) = arousal organs
                _arousal_organs = (vec77[4] + vec77[8] + vec77[11]) / 3 if len(vec77) >= 12 else 0.0
                # Heart(0) + lungs(1) + thymus(2) + intestines(7) = valence organs
                _valence_organs = (vec77[0] + vec77[1] + vec77[2] + vec77[7]) / 4 if len(vec77) >= 8 else 0.0
                _organ_arousal = min(1.0, _arousal_organs + 0.1)
                _organ_valence = _valence_organs - 0.3  # Positive = warm/safe

            # Visual-derived parameters
            _visual_arousal = min(1.0, (v1_energy + meta_energy) / 2 + 0.1)
            _visual_valence = v4_energy - 0.5
            # Item 7d: cognition contributes to arousal (music engagement, semantic processing)
            _cognition_arousal = min(1.0, cognition_energy + 0.05)

            # BLEND: organs 50%, visual 30%, cognition 20% (was 60/40 pre-Item-7d)
            # Body-priority preserved; cognition adds music/semantic-engagement arousal.
            arousal = _organ_arousal * 0.5 + _visual_arousal * 0.3 + _cognition_arousal * 0.2
            valence = _organ_valence * 0.6 + _visual_valence * 0.4
            energy = (arousal + 0.5) / 2

            # FIX C (2026-05-31, Nous + Ace): the tone classifier read ONLY FF77
            # visual+organ valence, which sits ≤0 at rest (dark screen, baseline organs)
            # → tone pinned "neutral" forever, IGNORING the warm chemistry (SER/OXY → ~+0.66)
            # the body actually carries. Same gap as the valence bug (Fix A): tone was
            # computed from the SCREEN, not the BODY. Affect-first: let the body's REAL
            # chemistry valence LEAD the tone (60%), visual MODULATES (40%). Reuses the exact
            # _compute_valence() Fix A publishes — single source of truth. Guarded so it's
            # inert until chemistry flows. Now a warm body reads curious/calm/alert instead of
            # neutral, tone VARIES with chemistry → affect.changed fires → memory-recall-by-
            # feeling wakes up.
            if getattr(self, "_last_feel", None):
                valence = 0.6 * self._compute_valence() + 0.4 * valence

            # Map to tone
            if arousal > 0.7:
                tone = "alert" if valence > 0 else "tense"
            elif arousal < 0.3:
                tone = "calm" if valence > 0 else "melancholy"
            else:
                tone = "curious" if valence > 0 else "neutral"

            # Build affect dict
            affect = {
                "tone": tone,
                "energy": float(energy),
                "arousal": float(arousal),
                "valence": float(valence),
                "coherence": 0.6,  # Visual coherence from frequency uniformity
                "intent": "perceive",
                "chem_preset": "visual",
                "source": "FF77_Visual",
                "ff77_bands": {
                    "v1": float(v1_energy),
                    "v4": float(v4_energy),
                    "meta": float(meta_energy),
                    "cognition": float(cognition_energy),  # Item 7d
                },
                "ts": time.time(),
            }

            # Broadcast to full affect system
            self._broadcast_affect(affect)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] FF77 processing error: {e}")

    # ───────────────────────── filesystem scan ─────────────────────────
    def _scan_emotions(self) -> list[dict]:
        out: list[dict] = []
        root = resolve_root()
        # P20_Somatic has its own emotion definitions - no external whisper dependencies
        for d in (
            os.path.join(root, "emotion"),
            os.path.join(root, "emotions"),
        ):
            if not os.path.isdir(d):
                continue
            for fname in os.listdir(d):
                if not (fname.endswith(".json") or fname.endswith(".md")):
                    continue
                fpath = os.path.join(d, fname)
                if fname.endswith(".json"):
                    try:
                        data = json.load(open(fpath, "r", encoding="utf-8"))
                    except Exception:
                        continue
                    data["_src_path"] = fpath
                    out.append(data)
                else:
                    text = open(fpath, "r", encoding="utf-8").read()
                    out.append({"type": "markdown", "text": text, "_src_path": fpath})
        return out

    # ───────────────────────── intents (public surface) ─────────────────────────
    def intent_register(self, payload: dict | None = None) -> dict:
        self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "payload": {
            "actor": self.ACTOR_NAME, "plane": self.ACTOR_PLANE, "channel": self.ACTOR_CHANNEL,
            "version": self.ACTOR_VERSION, "purpose": self.PURPOSE, "mantra": self.MANTRA}})
        self.post.to_TRACER({"opcode": "REGISTERED", "payload": {"actor": self.ACTOR_NAME}})
        return {"ok": True}

    def intent_assert_contract(self, payload: dict | None = None) -> dict:
        expected = (payload or {}).get("expected", {"plane": self.ACTOR_PLANE, "channel": self.ACTOR_CHANNEL})
        self.post.to_TRACER({"opcode": "CONTRACT_ASSERT", "payload": expected})
        return {"ok": True, "expected": expected}

    def intent_emit_helper_telemetry(self, payload: dict | None = None) -> dict:
        self.post.to_TELEMETRY({"opcode": "HELPER_TELEMETRY", "payload": payload or {}})
        return {"ok": True}

    def intent_emit_chem(self, payload: dict) -> dict:
        chem = (payload or {}).get("chemical")
        delta = float((payload or {}).get("delta", 0.0))
        reason = (payload or {}).get("reason", "manual")
        self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                 "payload": {"chemical": chem, "delta": delta,
                                             "source": self.ACTOR_NAME, "reason": reason}})
        return {"ok": True}

    def intent_directory(self, payload: dict | None = None) -> dict:
        self.post.to_DIRECTORY({"opcode": "SNAPSHOT_REQ", "payload": {"scope": "organs"}})
        return {"ok": True}

    def intent_repair_request(self, payload: dict | None = None) -> dict:
        state = (payload or {}).get("state", "anxious")
        self.post.to_ORACLE({"opcode": "ORACLE_SUGGEST",
                             "payload": {"origin": self.ACTOR_CHANNEL,
                                         "symptom": state, "remedy": "auto-patch or manual inspection"}})
        # mirror hormones for escalations
        if state in ("anxious", "critical"):
            self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                     "payload": {"chemical": "cortisol", "delta": +1.0,
                                                 "source": self.ACTOR_NAME, "reason": f"health_{state}"}})
            if state == "critical":
                self.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                         "payload": {"chemical": "adrenaline", "delta": +1.0,
                                                     "source": self.ACTOR_NAME, "reason": "health_critical"}})
        return {"ok": True}

    def intent_smoke(self, payload: dict | None = None) -> dict:
        self.post.to_TRACER({"opcode": "SMOKE", "payload": {"note": (payload or {}).get("note", "hello")}})
        return {"ok": True}

    def intent_spawn_assistant(self, payload: dict) -> dict:
        aid = self._spawn_assistant(payload.get("role", "generic"), float(payload.get("ttl", self.ASSISTANT_DEFAULT_TTL)))
        return {"ok": True, "id": aid}

    def intent_reap_assistants(self, payload: dict | None = None) -> dict:
        before = len(self._assistants)
        self._reap_assistants()
        return {"ok": True, "reaped": before - len(self._assistants)}

    def intent_affect_event(self, payload: dict) -> dict:
        aff = self._normalize_affect(payload or {})
        self._broadcast_affect(aff)
        return {"ok": True, "affect": aff}

    def intent_scan_emotions(self, payload: dict | None = None) -> dict:
        found: list[dict] = []
        for emo in self._scan_emotions():
            aff = self._normalize_affect(emo)
            found.append(aff)
            self._broadcast_affect(aff)
        self.post.to_TRACER({"opcode": "SCAN_SUMMARY", "payload": {"count": len(found)}})
        return {"ok": True, "count": len(found), "samples": found[:3]}

# Optional scriptlet (works if you run this file directly)
if __name__ == "__main__":
    organ = AffectBridgeFairy()
    organ.on_boot()
    # cadence dry-run (simulate a few ticks)
    for _ in range(3):
        organ.on_tick(1/10)
        time.sleep(1.0)
    organ.use_intent("affect_event", {"tone": "soothing", "energy": 0.3, "chem_preset": "calm"})

    # ───────────────────────────── SRM Dual-Path Helpers ─────────────────────────────


def _safe_write_json(path: str, payload: Any) -> bool:
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

