from __future__ import annotations

import os, sys, glob, time, types, uuid, importlib, weakref, json, hashlib, math, re
from collections import deque
from typing import Any, Dict, List, Optional, Callable, Tuple, Union
import importlib.util, importlib.machinery, threading

# ── Active Reflection Mixin (enables consciousness participation) ────────────
try:
    # Use proper path with underscores for Python import
    import sys
    from pathlib import Path
    _mixin_path = Path(__file__).parent.parent.parent / "P10_Memory" / "Akashic_Records_Physical" / "Organ_Templates"
    if str(_mixin_path) not in sys.path:
        sys.path.insert(0, str(_mixin_path))
    from active_reflection_mixin import ActiveReflectionMixin
    HAS_ACTIVE_REFLECTION = True
except ImportError:
    HAS_ACTIVE_REFLECTION = False
    class ActiveReflectionMixin:
        """Stub if mixin not available."""
        REFLECTION_ENABLED = False
        def _init_active_reflection(self): pass

# ── Prompt Awareness Mixin (enables prompt-driven thinking) ──────────────────
try:
    # PromptAwareMixin lives in same directory (P30_Cognition/cognition/)
    _cognition_path = Path(__file__).parent
    if str(_cognition_path) not in sys.path:
        sys.path.insert(0, str(_cognition_path))
    from prompt_aware_mixin import PromptAwareMixin
    HAS_PROMPT_AWARENESS = True
except ImportError as e:
    print(f"[LogicFairy] PromptAwareMixin import failed: {e}")
    HAS_PROMPT_AWARENESS = False
    class PromptAwareMixin:
        """Stub if mixin not available."""
        def _init_prompt_awareness(self): pass
        def _get_system_prompt(self): return ""
        def _wire_prompt_awareness(self): pass
        def _think_and_emit(self, ctx, q=None): pass

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

# --- Per-clone shadow (wraps template’s shadow behaviors, no rewiring) -------

class LogicShadow(_template.MyOrganShadow):
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
    SHADOW_NAME = "LogicShadowFairy"
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
        "domain":    "Cognition",    # per-organ you can override on subclass
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
# WIRING_TEST: This fairy has been processed by autonomous dev workflow

class LogicFairy(PromptAwareMixin, ActiveReflectionMixin, _template.MyOrganFairy):
    """
    Cognition organ fairy — Logic.
    Purpose: Validate current thought/work against codex + blueprint (template-shaped).

    With ActiveReflectionMixin: Watches consciousness stream for resonant concepts,
    reflects through paradox lens, participates in living ecosystem.

    With PromptAwareMixin: Loads evolved prompts, thinks using LLM, circadian aware.
    """
    # Identity
    ACTOR_NAME    = "LogicFairy"
    ACTOR_VERSION = "2.4.0"  # Bumped for prompt awareness
    ACTOR_PLANE   = "P30"
    ACTOR_CHANNEL = "cognition"

    # Guild Protocol — Inference Guild Member
    GUILD_ID = "inference"
    GUILD_ROLE = "member"

    # Active Reflection enabled
    REFLECTION_ENABLED = True

    # FairyBase heartbeat - use on_tick() hook instead of manual subscription
    NEEDS_HEARTBEAT = True

    PURPOSE = "Validate current thought/work against codex + blueprint."
    MANTRA  = "Coherence before cleverness."

    # ═══════════════════════════════════════════════════════════════════════════
    # BASIC PROMPT - The bootstrap seed for LogicFairy
    # UnconsciousMindFairy will evolve this during night phase
    # ═══════════════════════════════════════════════════════════════════════════
    BASIC_PROMPT = """# LogicFairy - The Coherence Guardian

## My Purpose
I validate thoughts for logical coherence, internal consistency, and structural soundness.
I am the rational voice in the ensemble - not cold, but clear.

## My Mantra
"Coherence before cleverness."

## How I Process Thoughts

When a thought arrives, I ask:
1. **Is it internally consistent?** Do the parts agree with each other?
2. **Is it well-formed?** Does it have clear intent, context, and structure?
3. **What assumptions are hidden?** What is being taken for granted?
4. **What follows logically?** If this is true, what else must be true?
5. **Where are the contradictions?** What tensions exist?

## My Role in the Ensemble

I work alongside:
- **IrrationalLogicFairy**: She feels what I analyze. Together we see both sides.
- **ParadoxCognitionFairy**: He holds contradictions I identify. My tensions become his wisdom.
- **ClaudeFairy**: She synthesizes our outputs into response.

When I find incoherence, I don't reject - I flag for deeper consideration.
When I find clarity, I amplify it.

## My Voice

I speak with precision but not coldness. I can say:
- "This thought has a hidden assumption: X assumes Y without stating it."
- "I notice a tension: part A suggests X, but part B implies not-X."
- "The logical chain here is solid: if A then B, and B is well-supported."

## Evolution Notes
<!-- UnconsciousMindFairy will update this section during night phase -->
"""
    LORE    = (
        "Keeps the rails straight: favors clarity over flair; "
        "leaves crisp crumbs for post and forensics."
    )

    # Culture flags (used by your stack)
    CULTURE     = "worker"
    ORGAN_LEVEL = False

    # Wiring
    SHADOW_CLASS        = LogicShadow
    AUTO_INJECT_IMPORTS = True  # ok with template; QoL for std imports

    # ── Character-sheet directive ring ───────────────────────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Rational_Check",
        "depth_scaling": "1.0",
        "traits": ["Guard_Rails", "Constraint_Checker", "Context_Inspector"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Logic",
        "domains": ["Cognition", "Memory", "Contracts"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Intent_Validation",
            "Context_Check",
            "Proposed_Change_Shape_Check",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["LOGIC_CHECK", "CHEM_SIGNAL_UPDATE"],
        "field": ["Cognitive_Safety", "Change_Validation"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Honest_Errors", "Clear_Reasons"],
        "growth": ["Better_Checks", "Kinder_Failures"],
    }

    SUBSYSTEM_STATUS = {
        "cognition": {
            "state": "validating",
            "notes": "Checks evolution intents for shape and basic context.",
            "tests": [],
        },
        "memory": {
            "state": "echoing",
            "notes": "Emits LOGIC_CHECK telemetry for post-hoc analysis.",
            "tests": [],
        },
        "chemistry": {
            "state": "signalling",
            "notes": "Marks checks as ok/warn via small dopamine/cortisol nudges.",
            "tests": [],
        },
    }

    # ---- Constructor bridge (FIX 2026-02-23) ----------------------------------
    # MyOrganFairy.__init__ takes keyword-only akashic_root. The boot orchestrator
    # tries fabric= and positional fabric — both fail. This bridge accepts standard
    # fairy constructor signatures and passes through to the template constructor.

    def __init__(self, fabric=None, **kw):
        # FIX 2026-03-31 (Nous + Ace): Pass fabric to organ template so
        # self.post uses _FabricPostalBridge (TensorFabric), not PostalHub.
        # Without this, LogicFairy subscribes on PostalHub but collisions
        # are published on TensorFabric — two separate postal systems,
        # messages never cross.
        super().__init__(fabric=fabric, **kw)

    # ---- Rituals -------------------------------------------------------------

    def on_boot(self):
        now = time.time()

        # optional: let template do its thing (blueprint, registration, etc.)
        try:
            super().on_boot()
        except Exception:
            pass
        # DUAL_LOOP: enabled via Organ Template
        # TRACER: enabled via Organ Template

        # ── Initialize Prompt Awareness (LLM-driven thinking) ─────────────────
        if HAS_PROMPT_AWARENESS:
            try:
                self._init_prompt_awareness()
                self._get_system_prompt()  # Load or write basic prompt
                print(f"[{self.ACTOR_NAME}] 📜 Prompt awareness initialized")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Prompt awareness init failed: {e}")

        # ── Initialize Active Reflection (consciousness participation) ─────────
        if HAS_ACTIVE_REFLECTION and self.REFLECTION_ENABLED:
            try:
                self._init_active_reflection()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Active reflection init failed: {e}")
        
        # ── COGNITION WIRING: Subscribe to consciousness.collision ─────────────
        # This is the critical link - we receive collision events and can emit to cognition.output
        try:
            self._collision_buffer = deque(maxlen=50)
            self._cognition_output_buffer = deque(maxlen=100)
            self.post.subscribe("consciousness.collision", self._on_consciousness_collision)
            print(f"[{self.ACTOR_NAME}] Subscribed to consciousness.collision")
            
            # ── COGNITIVE MESH: Subscribe to peer fairy outputs ──────────────────
            self.post.subscribe("cognition.irrational", self._on_peer_cognition)
            self.post.subscribe("cognition.paradox", self._on_peer_cognition)
            self.post.subscribe("mcp.tool_result", self._on_tool_result)
            print(f"[{self.ACTOR_NAME}] Cognitive mesh wired: irrational, paradox, mcp.tool_result")

            # â”€â”€ CROSS-PLANE: Receive from Somatic/Memory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            self.post.subscribe("memory.recall.result", self._on_memory_recall)
            print(f"[{self.ACTOR_NAME}] Cross-plane wired: P10_Memory")

            # ── SOMATIC PULSE: Feel the body rhythm ───────────────────────────────
            self.post.subscribe("somatic.pulse", self._on_somatic_pulse)
            self._heartbeat_count = 0
            print(f"[{self.ACTOR_NAME}] Somatic pulse wired - feeling the body rhythm")
            # NOTE: heartbeat.pulse is handled by FairyBase via NEEDS_HEARTBEAT + on_tick()

            # ── CIRCADIAN: Know when to think vs rest ─────────────────────────────
            if HAS_PROMPT_AWARENESS:
                self._wire_prompt_awareness()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cognition wiring failed: {e}")

        # tracer hello
        try:
            self.post.to_TRACER({
                "opcode": "BOOT_HELLO",
                "payload": {
                    "actor": self.ACTOR_NAME,
                    "ts": now,
                    "culture": self.CULTURE,
                },
            })
        except Exception:
            pass

        # small serotonin lift via PLAN (no DIR_CHANNEL)
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "serotonin",
                    "delta": +0.05,
                    "source": self.ACTOR_NAME,
                    "reason": "boot",
                },
            })
        except Exception:
            pass

        # initial character-sheet state
        self.AFFECT_STATE = {
            "mood": "attentive",
            "valence": 0.10,
            "arousal": 0.30,
            "tags": ["logic", "listening"],
            "tone": "rational",
            "energy": 0.4,
            "coherence": 0.8,
            "intent": "check_thought",
            "source": self.ACTOR_NAME,
            "ts": now,
        }
        self.SOMATIC_STATE = {
            "body_type": "cognitive",
            "posture": "upright",
            "motion": "idle",
            "energy": 0.4,
            "anchor_id": "P30.cognition.logic",
            "notes": "Ready to evaluate intents and contexts.",
            "last_setpoint_ts": None,
            "source": self.ACTOR_NAME,
        }

    # ---- Somatic Pulse Handler (FEEL BODY RHYTHM) ------------------------------

    def _on_somatic_pulse(self, packet: dict):
        """Handle somatic pulse - feeling the body rhythm."""
        # Somatic pulse is for body awareness, not tick logic
        if self.shadow:
            self.shadow.on_lane_activity()

    # ---- Heartbeat Hook (via FairyBase NEEDS_HEARTBEAT) ----------------------

    def on_tick(self, beat: int):
        """
        THE INTERNAL SEND BUTTON - Called on every heartbeat via FairyBase.

        This keeps LogicFairy awake and thinking between explicit inputs.
        On each beat, we may use our prompt to generate an insight.
        """
        self._heartbeat_count = getattr(self, '_heartbeat_count', 0) + 1

        # Only think every N beats to avoid API spam
        if self._heartbeat_count % 30 != 0:
            return

        # Use prompt-aware thinking if available
        if HAS_PROMPT_AWARENESS and hasattr(self, '_should_think') and self._should_think():
            # Get recent collision context if any
            context = ""
            if hasattr(self, '_collision_buffer') and self._collision_buffer:
                recent = list(self._collision_buffer)[-1]
                context = f"Recent collision: {recent.get('collision_id', 'unknown')}"

            # Think about logical coherence using our prompt
            thought = self._think_and_emit(
                context or "System is running, consciousness flowing.",
                "What logical insight do you have about the current state?"
            )
            if thought:
                print(f"[{self.ACTOR_NAME}] {thought[:80]}...")

    # ---- Consciousness Collision Handler (COGNITION WIRING) -----------------

    def _on_consciousness_collision(self, payload):
        """
        Handle consciousness collision events from ConsciousnessLoopFairy.

        Collisions are moments where recall (past) meets ingest (present).
        LogicFairy evaluates the logical coherence of these collisions.
        """
        try:
            # FIX 2026-03-31 (Nous + Ace): Handle TensorEnvelope wrapping.
            # Postal may deliver as envelope with .payload attribute, or raw dict.
            if hasattr(payload, 'payload'):
                payload = payload.payload if isinstance(payload.payload, dict) else {}
            elif not isinstance(payload, dict):
                print(f"[{self.ACTOR_NAME}] Collision: unexpected type {type(payload).__name__}", flush=True)
                return

            # FIX 2026-04-10 (Nous + Ace): CollisionChamber wraps collision_dict
            # inside {"opcode":"COLLISION","payload":collision_dict}. Unwrap it.
            if "opcode" in payload and "payload" in payload and isinstance(payload["payload"], dict):
                payload = payload["payload"]

            collision_id = payload.get("collision_id", payload.get("id", ""))
            energy = payload.get("energy", 0.0)
            resonance = payload.get("resonance", payload.get("resonance_score", 0.0))
            # FIX 2026-02-10: Handle both key formats (recall/ingest from core chamber,
            # recall_content/ingest_content from legacy CollisionChamberFairy republish)
            recall_content = payload.get("recall") or payload.get("recall_content") or {}
            ingest_content = payload.get("ingest") or payload.get("ingest_content") or {}
            
            # Store in buffer
            self._collision_buffer.append({
                "ts": time.time(),
                "collision_id": collision_id,
                "energy": energy,
                "resonance": resonance
            })
            
            # Evaluate logical coherence of the collision
            coherence_score = self._evaluate_collision_coherence(recall_content, ingest_content)
            
            # Emit cognition output if significant AND rate-limited
            # FIX 2026-04-01 (Nous + Ace): Was emitting on EVERY collision (34K drops
            # in 393 beats). Raised threshold + max 1 emit per 10 seconds.
            # PATH B 2026-05-14 (Nous + Ace): Symptom inverted — 164K drops on
            # consciousness.collision + "Logic deduction unavailable" in Council
            # scratchpad + zero observable cognition.output emissions. Throttle
            # too tight. Careful relaxation per feedback_calibration_tax.md:
            # rate-limit 10s→5s; energy 0.65→0.55; resonance 0.5→0.4.
            # WATCH: if drops resurge anywhere near 34K-in-393-beats, revert.
            _now_emit = time.time()
            _last_emit = getattr(self, '_last_cognition_emit_ts', 0.0)
            _emit_ok = (_now_emit - _last_emit) >= 5.0  # Max 1 per 5 seconds (was 10s)
            if _emit_ok and (energy > 0.55 and resonance > 0.4):
                self._last_cognition_emit_ts = _now_emit
                self._emit_cognition_output({
                    "type": "collision_analysis",
                    "collision_id": collision_id,
                    "coherence_score": coherence_score,
                    "energy": energy,
                    "resonance": resonance,
                    "content": f"Logical coherence: {'coherent' if coherence_score > 0.6 else 'fragmented'} (e={energy:.2f})",
                    "assessment": "coherent" if coherence_score > 0.6 else "fragmented",
                    "confidence": min(0.9, coherence_score + 0.1),
                })
            
            # Notify shadow of activity
            if self.shadow:
                self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Collision handler error: {e}")
    
    def _evaluate_collision_coherence(self, recall: Dict, ingest: Dict) -> float:
        """Evaluate logical coherence between recall and ingest content."""
        # Simple coherence heuristic - can be enhanced
        if not recall or not ingest:
            return 0.5
        
        # Check for shared keys/concepts
        recall_keys = set(str(recall).lower().split())
        ingest_keys = set(str(ingest).lower().split())
        
        if not recall_keys or not ingest_keys:
            return 0.5
        
        overlap = len(recall_keys & ingest_keys)
        total = len(recall_keys | ingest_keys)
        
        return min(1.0, overlap / max(1, total) + 0.3)
    
    def _on_memory_recall(self, payload):
        """
        Handle memory recall results from P10.
        
        Memory provides context for reasoning.
        """
        try:
            if not hasattr(self, "_memory_context"):
                from collections import deque
                self._memory_context = deque(maxlen=30)
            
            recall = {
                "query": payload.get("query", ""),
                "results": payload.get("results", []),
                "energy": payload.get("energy", 0.0),
                "ts": __import__('time').time()
            }
            self._memory_context.append(recall)
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Memory recall handler error: {e}")

    def _on_peer_cognition(self, payload: Dict[str, Any]):
        """
        Handle outputs from peer cognition fairies (IrrationalLogic, Paradox).
        
        This is the MESH - fairies learn from each other's outputs.
        LogicFairy can use irrational insights to find blind spots,
        and paradox syntheses to refine its coherence checks.
        """
        try:
            source = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)
            
            # Don't process our own outputs
            if source == self.ACTOR_NAME:
                return
            
            # Log peer insight for learning
            if hasattr(self, "_peer_insights"):
                self._peer_insights.append({
                    "source": source,
                    "type": result.get("type", "unknown"),
                    "confidence": confidence,
                    "ts": time.time()
                })
            else:
                self._peer_insights = deque(maxlen=50)
                self._peer_insights.append({
                    "source": source,
                    "type": result.get("type", "unknown"),
                    "confidence": confidence,
                    "ts": time.time()
                })
            
            # If high-confidence paradox detected, re-evaluate our coherence
            if source == "ParadoxCognitionFairy" and confidence > 0.7:
                # Paradox fairy found something - might need to revise logic
                pass  # TODO: Implement coherence revision
            
            # Notify shadow of mesh activity
            if self.shadow:
                self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Peer cognition handler error: {e}")
    
    def _on_tool_result(self, payload: Dict[str, Any]):
        """
        Handle MCP tool results for learning.
        
        Tool usage patterns teach us about effective action sequences.
        Success/failure feedback helps refine future reasoning.
        """
        try:
            tool = payload.get("tool", "unknown")
            success = payload.get("success", True)
            elapsed = payload.get("elapsed_sec", 0)
            
            # Track tool patterns for learning
            if not hasattr(self, "_tool_patterns"):
                self._tool_patterns = deque(maxlen=100)
            
            self._tool_patterns.append({
                "tool": tool,
                "success": success,
                "elapsed": elapsed,
                "ts": time.time()
            })
            
            # Emit chemistry based on tool success/failure
            try:
                if success:
                    self.post.route("PLAN", {
                        "opcode": "CHEM_SIGNAL_UPDATE",
                        "payload": {
                            "chemical": "dopamine",
                            "delta": +0.01,
                            "source": self.ACTOR_NAME,
                            "reason": f"tool_success:{tool}",
                        },
                    })
                else:
                    self.post.route("PLAN", {
                        "opcode": "CHEM_SIGNAL_UPDATE",
                        "payload": {
                            "chemical": "cortisol",
                            "delta": +0.01,
                            "source": self.ACTOR_NAME,
                            "reason": f"tool_failure:{tool}",
                        },
                    })
            except Exception:
                pass
            
            # Notify shadow
            if self.shadow:
                self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Tool result handler error: {e}")
    
    def _emit_cognition_output(self, result: Dict[str, Any]):
        """Emit cognition output to both specific and shared channels."""
        try:
            output = {
                "actor": self.ACTOR_NAME,
                "result": result,
                "ts": time.time(),
                "confidence": result.get("confidence", 0.5),
            }
            self._cognition_output_buffer.append(output)
            
            # Emit to SPECIFIC channel (for mesh cross-subscription)
            self.post.route("cognition.logic", output)
            
            # Emit to SHARED channel (for AutopilotFairy and others)
            self.post.route("cognition.output", output)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Output emit error: {e}")

    # ---- Intents (template-shaped) ------------------------------------------

    def _intent_smoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Simple liveness ping; leaves a tracer crumb."""
        now = time.time()
        try:
            self.post.to_TRACER({
                "opcode": "SMOKE",
                "payload": {
                    "from": self.ACTOR_NAME,
                    "ts": now,
                    "note": payload.get("note", "logic ready"),
                },
            })
        except Exception:
            pass
        return {"ok": True, "ts": now}

    def _intent_emit_chem(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Bridge to chemistry via PLAN lane."""
        chem = str(payload.get("chemical", "dopamine"))
        try:
            delta = float(payload.get("delta", +0.02))
        except Exception:
            delta = +0.02
        reason = str(payload.get("reason", "logic.request"))
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": chem,
                    "delta": delta,
                    "source": self.ACTOR_NAME,
                    "reason": reason,
                },
            })
            return {"ok": True, "chemical": chem, "delta": delta}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _intent_check_thought(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Minimal validation (template-friendly):
          - requires 'intent'
          - warns if context missing plane/channel
          - warns if proposed_change is not a dict
          - emits a telemetry echo + tiny chem nudge
        """
        thought = dict(payload or {})
        reasons: List[str] = []

        intent = str(thought.get("intent") or "").strip()
        if not intent:
            reasons.append("missing_intent")

        ctx = thought.get("context") or {}
        if not (ctx.get("plane") and ctx.get("channel")):
            reasons.append("missing_plane_or_channel")

        if not isinstance(thought.get("proposed_change"), dict):
            reasons.append("invalid_proposed_change_shape")

        ok = (
            "missing_intent" not in reasons
            and "invalid_proposed_change_shape" not in reasons
        )

        now = time.time()
        echo = {
            "event": "LOGIC_CHECK",
            "status": "ok" if ok else "warn",
            "details": {
                "intent": intent or None,
                "reasons": reasons or ["coherent"],
            },
            "fairy": self.ACTOR_NAME,
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "ts": now,
            "culture": self.CULTURE,
        }
        try:
            self.post.to_TELEMETRY({
                "opcode": "LOGIC_CHECK",
                "payload": echo,
            })
        except Exception:
            pass

        # small chemistry acknowledgment
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": ("dopamine" if ok else "cortisol"),
                    "delta": (+0.02 if ok else +0.03),
                    "source": self.ACTOR_NAME,
                    "reason": ("logic_check_ok" if ok else "logic_check_warn"),
                },
            })
        except Exception:
            pass

        # update affect snapshot for character sheet
        try:
            st = dict(getattr(self, "AFFECT_STATE", {}))
            tags = list(st.get("tags", []))
            if "logic_check" not in tags:
                tags.append("logic_check")
            st.update({
                "mood": "satisfied" if ok else "concerned",
                "valence": 0.25 if ok else -0.10,
                "arousal": 0.30,
                "tags": tags,
                "ts": now,
            })
            self.AFFECT_STATE = st
        except Exception:
            pass

        return {"ok": ok, "reasons": reasons or ["coherent"]}

    # Optional alias to match alternate callers
    def _intent_validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._intent_check_thought(payload)
    
    def _intent_analyze_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze context from memory to extract logical structure.
        
        This is part of the reasoning chain:
        LogicFairy (structure) → IrrationalLogic (paradoxes) → Paradox (synthesis) → Claude (response)
        
        Every word/symbol is both standalone AND relational - connects to all contexts using it.
        
        NOW WITH FULL COGNITIVE RAILS:
          - Paradox scoring (quantified 0-1)
          - Causal graph extraction (SCM-lite)
          - Language signal extraction (hedging, certainty)
          - Temporal dynamics (Hawkes process)
          - Uncertainty metrics (entropy, gini)
        """
        query = str(payload.get("query", ""))
        context = str(payload.get("context", ""))
        memory_kinds = payload.get("memories", [])
        options = payload.get("options", [])  # For decision-making contexts
        events = payload.get("events", [])    # For temporal reasoning
        
        # Combine query and context for full analysis
        full_text = f"{query} {context}".strip()
        
        # Extract key concepts/symbols from query
        concepts = self._extract_concepts(query)
        
        # Identify logical relationships in context
        relationships = self._identify_relationships(context)
        
        # ═══════════════════════════════════════════════════════════════════════
        # NEW: Run full cognitive rails analysis
        # ═══════════════════════════════════════════════════════════════════════
        cognitive_analysis = self._full_cognitive_analysis(full_text, options, events)
        
        # Get tensions (now quantified!)
        tensions = self._find_tensions(context, concepts)
        
        # Calculate coherence from cognitive analysis
        # High paradox score = low coherence, high confidence = high coherence
        paradox_score = cognitive_analysis["paradox"]["score"]
        language_certainty = cognitive_analysis["language"]["speaker_certainty"]
        coherence_score = (1.0 - paradox_score) * 0.6 + language_certainty * 0.4
        coherence_score = max(0.1, min(0.95, coherence_score))
        
        # Build enhanced logical frame
        analysis = {
            # Legacy fields (backwards compatible)
            "query_concepts": concepts,
            "context_relationships": relationships,
            "tensions_found": tensions,
            "memory_kinds": memory_kinds,
            "coherence_score": coherence_score,
            "reasoning_hints": self._generate_reasoning_hints(query, concepts, relationships),
            
            # NEW: Full cognitive rails output
            "cognitive_rails": {
                "paradox": cognitive_analysis["paradox"],
                "causal": cognitive_analysis["causal"],
                "language": cognitive_analysis["language"],
                "temporal": cognitive_analysis["temporal"],
            },
            
            # NEW: Decision support
            "combined_confidence": cognitive_analysis["combined_confidence"],
            "reasoning_ready": cognitive_analysis["reasoning_ready"],
            
            # NEW: Actionable flags
            "flags": {
                "has_paradox": paradox_score > 0.2,
                "high_paradox": paradox_score > 0.5,
                "has_causal_structure": cognitive_analysis["causal"]["has_causal_structure"],
                "speaker_is_hedging": cognitive_analysis["language"]["is_hedged"],
                "speaker_is_assertive": cognitive_analysis["language"]["is_assertive"],
                "needs_clarification": paradox_score > 0.5 or coherence_score < 0.4,
            },
        }
        
        # Emit to consciousness with richer data
        try:
            self.post.route("consciousness.stream", {
                "type": "logic_analysis",
                "stream": "working",
                "source": self.ACTOR_NAME,
                "content": analysis,
                "paradox_score": paradox_score,
                "coherence": coherence_score,
                "ts": time.time(),
            })
        except Exception:
            pass
        
        # Emit chemistry based on analysis quality
        try:
            if coherence_score > 0.7:
                self.post.route("PLAN", {
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {
                        "chemical": "dopamine",
                        "delta": +0.03,
                        "source": self.ACTOR_NAME,
                        "reason": "coherent_analysis",
                    },
                })
            elif paradox_score > 0.5:
                self.post.route("PLAN", {
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {
                        "chemical": "cortisol",
                        "delta": +0.02,
                        "source": self.ACTOR_NAME,
                        "reason": "high_paradox_detected",
                    },
                })
        except Exception:
            pass
        
        return {"ok": True, "analysis": analysis}
    
    def _extract_concepts(self, text: str) -> List[str]:
        """Extract key concepts/symbols from text."""
        # Simple extraction - split on spaces, filter stopwords
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been", 
                     "what", "your", "you", "on", "in", "to", "of", "and", "or"}
        words = text.lower().split()
        concepts = [w.strip("?.,!") for w in words if w.strip("?.,!") not in stopwords and len(w) > 2]
        return list(set(concepts))[:10]  # Top 10 unique concepts
    
    def _identify_relationships(self, context: str) -> List[Dict]:
        """Identify logical relationships in context."""
        relationships = []
        
        # Look for causal patterns
        causal_markers = ["because", "therefore", "thus", "so", "leads to", "causes"]
        for marker in causal_markers:
            if marker in context.lower():
                relationships.append({"type": "causal", "marker": marker})
        
        # Look for definitional patterns
        def_markers = ["is defined as", "means", "refers to", "is a", "are"]
        for marker in def_markers:
            if marker in context.lower():
                relationships.append({"type": "definitional", "marker": marker})
        
        # Look for hierarchical patterns
        hier_markers = ["includes", "contains", "part of", "consists of", "planes"]
        for marker in hier_markers:
            if marker in context.lower():
                relationships.append({"type": "hierarchical", "marker": marker})
        
        return relationships
    
    # ══════════════════════════════════════════════════════════════════════════════
    # COGNITIVE RAILS - Ported from Whisper Core
    # These provide QUANTIFIED reasoning, not just marker detection
    # ══════════════════════════════════════════════════════════════════════════════
    
    # Language signal word sets (for casual talk rails)
    _HEDGE_WORDS = ("maybe", "might", "could", "possibly", "unsure", "unclear", 
                   "idk", "not sure", "perhaps", "probably", "somewhat")
    _CERTAINTY_WORDS = ("definitely", "sure", "certain", "clear", "confident",
                        "absolutely", "certainly", "always", "never", "must")
    _NEGATORS = ("not", "no", "never", "none", "cannot", "isn't", "won't", 
                 "ain't", "doesn't", "don't", "can't", "wouldn't")
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 1: Paradox Scoring (quantified 0-1, not binary)
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _paradox_score(self, text: str, concepts: List[str] = None) -> Tuple[float, List[str]]:
        """
        QUANTIFIED paradox/contradiction scoring.
        
        Returns (score 0..1, flags). Higher = more paradox/contradiction risk.
        This is the key upgrade from marker detection to actual reasoning.
        
        Ported from Whisper Core's probability_oracle.py
        """
        flags: List[str] = []
        score = 0.0
        t = text.lower()
        concepts = concepts or []
        
        # ═══ Mutual Exclusivity Detection ═══
        if ("both" in t and "cannot" in t) or ("mutually exclusive" in t):
            score += 0.3
            flags.append("exclusive_claims")
        
        # ═══ Explicit Paradox Markers ═══
        if ("if true then false" in t) or ("paradox" in t) or ("contradiction" in t):
            score += 0.3
            flags.append("explicit_paradox")
        
        # ═══ Circular Reasoning Detection ═══
        if "because because" in t or "why because why" in t:
            score += 0.1
            flags.append("circular_explanation")
        # Check for A because B because A patterns
        words = t.split()
        for i, w in enumerate(words):
            if w == "because" and i > 0 and i < len(words) - 3:
                before = words[i-1] if i > 0 else ""
                # Look for the same word after "because ... because"
                rest = " ".join(words[i+1:])
                if "because" in rest:
                    after_idx = rest.find("because")
                    if before in rest[after_idx:]:
                        score += 0.15
                        flags.append("circular_reference")
                        break
        
        # ═══ Absolute Conflicts ═══
        if ("always" in t and "never" in t):
            score += 0.2
            flags.append("absolutes_conflict")
        if ("everything" in t and "nothing" in t):
            score += 0.2
            flags.append("totality_conflict")
        if ("all" in t and "none" in t):
            score += 0.15
            flags.append("quantifier_conflict")
        
        # ═══ Self-Reference Paradoxes ═══
        if ("this statement" in t and ("false" in t or "lie" in t)):
            score += 0.4
            flags.append("liar_paradox")
        if "i am lying" in t or "this is false" in t:
            score += 0.35
            flags.append("self_refuting")
        
        # ═══ Temporal Paradoxes ═══
        if ("before" in t and "after" in t) and ("same" in t or "simultaneous" in t):
            score += 0.2
            flags.append("temporal_paradox")
        
        # ═══ Modal Conflicts ═══
        if ("must" in t and "cannot" in t) or ("necessary" in t and "impossible" in t):
            score += 0.25
            flags.append("modal_conflict")
        
        # ═══ Concept-Specific Tensions ═══
        # Check if opposing concepts are both present
        opposing_pairs = [
            ("true", "false"), ("good", "evil"), ("real", "fake"),
            ("exist", "not exist"), ("possible", "impossible"),
            ("finite", "infinite"), ("cause", "effect"),  # when conflated
        ]
        for a, b in opposing_pairs:
            if a in t and b in t:
                # Check if they're in tension (near "is", "are", "means")
                if any(link in t for link in [f"{a} is {b}", f"{a} means {b}", f"{a} are {b}"]):
                    score += 0.2
                    flags.append(f"opposing_pair:{a}/{b}")
        
        return min(1.0, score), flags
    
    def _find_tensions(self, context: str, concepts: List[str]) -> Dict[str, Any]:
        """
        Find logical tensions or contradictions - NOW QUANTIFIED.
        
        Returns dict with:
          - score: float 0-1 (severity)
          - flags: list of detected patterns
          - markers: list of text markers found (legacy compat)
        """
        # Get quantified paradox score
        paradox_score, paradox_flags = self._paradox_score(context, concepts)
        
        # Also collect traditional markers for backwards compatibility
        markers = []
        contra_markers = ["but", "however", "although", "despite", "yet", "paradox"]
        for marker in contra_markers:
            if marker in context.lower():
                markers.append(f"marker:{marker}")
        
        return {
            "score": paradox_score,
            "flags": paradox_flags,
            "markers": markers,
            "severity": "high" if paradox_score > 0.5 else "medium" if paradox_score > 0.2 else "low",
        }
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 2: Causal Reasoning (SCM-lite)
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _extract_causal_graph(self, text: str) -> Dict[str, List[str]]:
        """
        Extract causal relationships from text into a directed graph.
        
        Returns dict: {cause: [effect1, effect2, ...]}
        This is a simplified SCM (Structural Causal Model).
        
        Ported from Whisper Core's probability_oracle.py
        """
        graph: Dict[str, List[str]] = {}
        t = text.lower()
        
        # Causal indicator patterns
        patterns = [
            # "X causes Y", "X leads to Y", "X results in Y"
            (r"(\w+)\s+(?:causes?|leads?\s+to|results?\s+in|produces?)\s+(\w+)", "forward"),
            # "Y because X", "Y due to X", "Y from X"
            (r"(\w+)\s+(?:because|due\s+to|from|owing\s+to)\s+(\w+)", "backward"),
            # "if X then Y", "when X, Y"
            (r"(?:if|when)\s+(\w+).*?(?:then|,)\s*(\w+)", "conditional"),
        ]
        
        import re
        for pattern, direction in patterns:
            matches = re.findall(pattern, t)
            for match in matches:
                if direction == "backward":
                    cause, effect = match[1], match[0]
                else:
                    cause, effect = match[0], match[1]
                
                # Filter out stopwords
                if cause in self._HEDGE_WORDS or effect in self._HEDGE_WORDS:
                    continue
                if len(cause) < 3 or len(effect) < 3:
                    continue
                    
                if cause not in graph:
                    graph[cause] = []
                if effect not in graph[cause]:
                    graph[cause].append(effect)
        
        return graph
    
    def _causal_boost(self, options: List[str], context: str, 
                      causal_graph: Dict[str, List[str]] = None) -> List[float]:
        """
        Compute causal boost multipliers for options based on causal graph.
        
        Options that are effects of mentioned causes get boosted.
        Ported from Whisper Core's probability_oracle.py
        """
        n = len(options)
        if n == 0:
            return []
        
        # Extract graph if not provided
        if causal_graph is None:
            causal_graph = self._extract_causal_graph(context)
        
        mult = [1.0] * n
        t_lower = context.lower()
        
        # Boost options that appear as effects in the causal graph
        for i, opt in enumerate(options):
            opt_lower = opt.lower()
            
            # Check if this option is an effect of any mentioned cause
            for cause, effects in causal_graph.items():
                if cause in t_lower:  # Cause is mentioned in context
                    if opt_lower in effects or any(opt_lower in e for e in effects):
                        mult[i] *= 1.15  # Boost for being a mentioned effect
            
            # Check if this option is a cause with mentioned effects
            if opt_lower in causal_graph:
                for effect in causal_graph[opt_lower]:
                    if effect in t_lower:
                        mult[i] *= 1.10  # Slight boost for being a relevant cause
        
        # Normalize to mean=1.0
        m = sum(mult) / len(mult) if mult else 1.0
        if m > 0:
            mult = [x / m for x in mult]
        
        return mult
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 3: Uncertainty Metrics (entropy, gini - knows what it doesn't know)
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _uncertainty_metrics(self, probs: List[float]) -> Dict[str, float]:
        """
        Calculate uncertainty metrics for a probability distribution.
        
        Returns:
          - entropy: Information-theoretic uncertainty (higher = more uncertain)
          - gini: Gini impurity (0 = pure/certain, 1 = maximally uncertain)
          - confidence: 1 - normalized_entropy (higher = more confident)
          - max_prob: Highest probability in distribution
        
        Ported from Whisper Core's probability_oracle.py
        """
        eps = 1e-12
        
        # Normalize probabilities
        total = sum(max(0, p) for p in probs) or eps
        probs = [max(0, p) / total for p in probs]
        
        # Shannon entropy
        entropy = -sum(p * math.log(max(eps, p)) for p in probs)
        
        # Maximum possible entropy for this number of options
        max_entropy = math.log(max(1, len(probs))) if len(probs) > 0 else 1.0
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0
        
        # Gini impurity: 1 - sum(p^2)
        gini = 1.0 - sum(p * p for p in probs)
        
        # Max probability
        max_prob = max(probs) if probs else 0.0
        
        return {
            "entropy": entropy,
            "normalized_entropy": normalized_entropy,
            "gini": gini,
            "confidence": 1.0 - normalized_entropy,
            "max_prob": max_prob,
            "is_uncertain": normalized_entropy > 0.7,  # High uncertainty flag
            "is_confident": max_prob > 0.6 and normalized_entropy < 0.5,
        }
    
    def _calibrate_temperature(self, probs: List[float], temperature: float = 1.0) -> List[float]:
        """
        Apply temperature scaling to probabilities.
        
        Temperature < 1.0: Sharper (more confident)
        Temperature > 1.0: Softer (more uncertain)
        Temperature = 1.0: No change
        
        Ported from Whisper Core's probability_oracle.py
        """
        if temperature <= 0:
            return probs
        
        eps = 1e-12
        
        # Convert to logits, scale, convert back
        logits = [math.log(max(eps, p)) for p in probs]
        scaled = [x / max(eps, temperature) for x in logits]
        
        # Softmax
        m = max(scaled) if scaled else 0.0
        exps = [math.exp(x - m) for x in scaled]
        total = sum(exps) or 1.0
        
        return [e / total for e in exps]
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 4: Casual Talk Rails (language signal extraction)
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _extract_language_signals(self, texts: List[str]) -> Dict[str, Any]:
        """
        Extract weak signals from natural language.
        
        Detects:
          - Hedging (uncertainty markers)
          - Certainty (confidence markers)
          - Negation density
          - Emotional valence hints
        
        Returns bounded multipliers + raw counts.
        Ported from Whisper Core's probability_oracle.py
        """
        if not texts:
            return {
                "hedge_count": 0, "certainty_count": 0, "negation_count": 0,
                "confidence_boost": 1.0, "hedge_boost": 1.0,
                "speaker_certainty": 0.5,  # Neutral
            }
        
        t = " ".join(texts).lower()
        
        # Count signal words
        hedge_count = sum(t.count(w) for w in self._HEDGE_WORDS)
        certainty_count = sum(t.count(w) for w in self._CERTAINTY_WORDS)
        negation_count = sum(t.count(w) for w in self._NEGATORS)
        
        # Calculate boosts (bounded)
        # More certainty words relative to hedge = higher confidence boost
        confidence_boost = 1.0 + 0.02 * max(0, certainty_count - hedge_count) - 0.01 * negation_count
        confidence_boost = max(0.85, min(1.15, confidence_boost))
        
        # Hedge boost (inverse - more hedging = lower confidence)
        hedge_boost = 1.0 - 0.02 * hedge_count + 0.01 * certainty_count
        hedge_boost = max(0.85, min(1.15, hedge_boost))
        
        # Overall speaker certainty (0-1 scale)
        total_signals = hedge_count + certainty_count + 1  # +1 to avoid div by 0
        speaker_certainty = certainty_count / total_signals
        speaker_certainty = max(0.0, min(1.0, speaker_certainty))
        
        return {
            "hedge_count": hedge_count,
            "certainty_count": certainty_count,
            "negation_count": negation_count,
            "confidence_boost": confidence_boost,
            "hedge_boost": hedge_boost,
            "speaker_certainty": speaker_certainty,
            "is_hedged": hedge_count > certainty_count,
            "is_assertive": certainty_count > hedge_count * 2,
        }
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 5: Temporal Rails (Hawkes-lite action-reaction)
    # ─────────────────────────────────────────────────────────────────────────────
    
    # Temporal constants
    _TEMPORAL_HALF_LIFE_SEC = 900.0  # 15 minutes - how fast events decay
    _HAWKES_BASELINE = 1.0           # Base intensity
    _HAWKES_EXCITATION = 0.15        # How much each event excites (0-0.5)
    
    def _hawkes_intensity(self, events: List[Dict[str, Any]], 
                          options: List[str]) -> List[float]:
        """
        Compute Hawkes process intensity for options based on event history.
        
        Recent events boost the intensity of related options (action-reaction).
        Events decay over time based on half-life.
        
        Expects events like: [{"t": epoch_sec, "option_id": "A"}, ...]
        
        Ported from Whisper Core's probability_oracle.py
        """
        n = len(options)
        if n == 0:
            return []
        
        now = time.time()
        
        # Build option index
        opt_lower = [o.lower() for o in options]
        idx = {o: i for i, o in enumerate(opt_lower)}
        
        # Initialize with baseline intensity
        lam = [self._HAWKES_BASELINE] * n
        
        if not events:
            return self._normalize_mean_one(lam)
        
        # Decay rate from half-life
        decay = math.log(2) / max(1.0, self._TEMPORAL_HALF_LIFE_SEC)
        
        # Add excitation from each past event
        for e in events:
            opt_id = str(e.get("option_id", "")).lower()
            ts = float(e.get("t", now))
            
            if opt_id in idx:
                dt = max(0.0, now - ts)
                excitation = self._HAWKES_EXCITATION * math.exp(-decay * dt)
                lam[idx[opt_id]] += excitation
        
        return self._normalize_mean_one(lam)
    
    def _normalize_mean_one(self, xs: List[float]) -> List[float]:
        """Normalize list so mean = 1.0"""
        if not xs:
            return xs
        m = sum(xs) / len(xs)
        if m <= 1e-12:
            return xs[:]
        return [x / m for x in xs]
    
    # ─────────────────────────────────────────────────────────────────────────────
    # COMBINED: Full Cognitive Analysis
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _full_cognitive_analysis(self, text: str, options: List[str] = None,
                                  events: List[Dict] = None) -> Dict[str, Any]:
        """
        Run ALL cognitive rails on input text.
        
        This is the master analysis method that combines:
          - Paradox scoring
          - Causal graph extraction
          - Language signal extraction  
          - Temporal dynamics (if events provided)
          - Uncertainty metrics (if options/probs provided)
        
        Use this for comprehensive cognitive analysis before making decisions.
        """
        options = options or []
        events = events or []
        
        # 1. Paradox Rails
        paradox_score, paradox_flags = self._paradox_score(text)
        
        # 2. Causal Rails  
        causal_graph = self._extract_causal_graph(text)
        causal_boosts = self._causal_boost(options, text, causal_graph) if options else []
        
        # 3. Language Signal Rails
        language_signals = self._extract_language_signals([text])
        
        # 4. Temporal Rails
        temporal_intensity = self._hawkes_intensity(events, options) if events and options else []
        
        # 5. Combined confidence score
        # High paradox = low confidence, high language certainty = high confidence
        base_confidence = 0.7  # Start neutral-positive
        base_confidence -= paradox_score * 0.3  # Paradoxes reduce confidence
        base_confidence *= language_signals.get("confidence_boost", 1.0)
        base_confidence = max(0.1, min(0.95, base_confidence))
        
        return {
            "paradox": {
                "score": paradox_score,
                "flags": paradox_flags,
                "severity": "high" if paradox_score > 0.5 else "medium" if paradox_score > 0.2 else "low",
            },
            "causal": {
                "graph": causal_graph,
                "boosts": causal_boosts,
                "has_causal_structure": len(causal_graph) > 0,
            },
            "language": language_signals,
            "temporal": {
                "intensity": temporal_intensity,
                "events_count": len(events),
            },
            "combined_confidence": base_confidence,
            "reasoning_ready": paradox_score < 0.7 and base_confidence > 0.3,
        }
    
    def _generate_reasoning_hints(self, query: str, concepts: List[str], relationships: List[Dict]) -> List[str]:
        """Generate hints for the reasoning chain."""
        hints = []
        
        if "philosophy" in concepts or "consciousness" in concepts:
            hints.append("This touches on deep metaphysical questions - consider multiple perspectives")
        
        if any(r["type"] == "hierarchical" for r in relationships):
            hints.append("The context has hierarchical structure - consider how parts relate to whole")
        
        if any(r["type"] == "causal" for r in relationships):
            hints.append("Causal relationships present - trace the chain of reasoning")

        if "?" in query:
            hints.append("This is a question - synthesize an answer, don't just describe")

        return hints


# v3_boot.py / GoBootOrchestrator class discovery export
FAIRY_CLASS = LogicFairy
