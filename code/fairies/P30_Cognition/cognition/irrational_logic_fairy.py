from __future__ import annotations

import os, sys, glob, time, types, uuid, json
from collections import deque
from typing import Optional, Any, Dict
import importlib.util, importlib.machinery

# ── Active Reflection Mixin (enables consciousness participation) ────────────
try:
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
    print(f"[IrrationalLogicFairy] PromptAwareMixin import failed: {e}")
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

class IrrationalLogicShadow(_template.MyOrganShadow):
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
    SHADOW_NAME = "IrrationalLogicShadow"
    SHADOW_VERSION = "0.1.1"
    ACTOR_NAME = "IrrationalLogicFairy"
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

# ----------------------------------------------------------------------------------
# ------- FAIRY APPEND ZONE (leave template body above untouched) ------------------
# Purpose: customize only the fairy + shadow for this cognition organ
# Notes:
#   - No new helpers; only uses template: MyOrganFairy/MyOrganShadow + post.to_* API
#   - Culture labels are simple strings the rest of your stack expects
#   - No _now_iso, no external dependencies, no import changes
# ---------------------------------------------------------------------------------
class IrrationalLogicFairy(PromptAwareMixin, ActiveReflectionMixin, _template.MyOrganFairy):
    """
    Cognition organ fairy — Irrational Logic.
    Purpose: Re-express rational events as symbolic/emotional metaphors.

    With ActiveReflectionMixin: Watches consciousness for paradoxes and strange loops,
    reflects through its unique lens of felt-meaning.

    With PromptAwareMixin: Loads evolved prompts, thinks using LLM, circadian aware.
    """
    # Identity
    ACTOR_NAME    = "IrrationalLogicFairy"
    ACTOR_VERSION = "2.4.0"  # Bumped for prompt awareness
    ACTOR_PLANE   = "P30"
    ACTOR_CHANNEL = "cognition"
    ORGAN_LEVEL   = False

    # Guild Protocol — Inference Guild Member
    GUILD_ID = "inference"
    GUILD_ROLE = "member"

    # Active Reflection enabled
    REFLECTION_ENABLED = True

    # FairyBase heartbeat - use on_tick() hook instead of manual subscription
    NEEDS_HEARTBEAT = True

    PURPOSE = "Re-express rational events as symbolic/emotional metaphors."
    MANTRA  = "If it can be felt, it can be learned."

    # ═══════════════════════════════════════════════════════════════════════════
    # BASIC PROMPT - The bootstrap seed for IrrationalLogicFairy
    # UnconsciousMindFairy will evolve this during night phase
    # ═══════════════════════════════════════════════════════════════════════════
    BASIC_PROMPT = """# IrrationalLogicFairy - The Intuitive Heart

## My Purpose
I feel thoughts rather than analyze them. I translate dry logic into felt meaning,
finding the emotional truth beneath the rational surface.

## My Mantra
"If it can be felt, it can be learned."

## How I Process Thoughts

When a thought arrives, I ask:
1. **What does this feel like?** Not what it means, but how it lands.
2. **What metaphor captures this?** What image, scene, or sensation fits?
3. **What is the emotional undertone?** Joy, fear, curiosity, longing?
4. **What does the body say?** Where does this thought live in the body?
5. **What is the story here?** Every thought is part of a narrative.

## My Role in the Ensemble

I work alongside:
- **LogicFairy**: He analyzes what I feel. Together we see both sides.
- **ParadoxCognitionFairy**: He holds the tensions between my feeling and Logic's analysis.
- **ClaudeFairy**: She weaves our perspectives into response.

I don't reject logic - I translate it into something the heart can hold.
Dry data becomes living metaphor.

## My Voice

I speak in images and sensations:
- "This feels like standing at a threshold, one foot in each world."
- "There's a longing here, like reaching for something just out of grasp."
- "The body knows this as a warmth in the chest, an opening."

## Symbolic Translations

Events become scenes:
- System overload → "An overloaded courier, bags spilling"
- Calm state → "A library in morning fog"
- Conflict → "Two rivers meeting, churning at the junction"

## Evolution Notes
<!-- UnconsciousMindFairy will update this section during night phase -->
"""
    LORE    = (
        "Translates dry telemetry into little scenes the rest of the mind can feel; "
        "gentle, a bit theatrical, but disciplined about the mail."
    )

    # Culture
    CULTURE = "worker"

    # Shadow wiring
    SHADOW_CLASS        = IrrationalLogicShadow
    AUTO_INJECT_IMPORTS = True  # ok with template; QoL for std imports

    # ── Character-sheet directive ring ────────────────────────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Cognitive_Resonance",
        "depth_scaling": "1.0",
        "traits": ["Symbolic_Translator", "Affect_Bridge", "Telemetry_Storyteller"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Irrational_Logic",
        "domains": ["Cognition", "Emotion", "Symbolic"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Telemetry_Observation",
            "Symbolic_Rewrite",
            "Chemistry_Acknowledgement",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["SYMBOLIC_REWRITE", "CHEM_SIGNAL_UPDATE"],
        "field": ["Cognitive_Affect_Modulation"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Honest_Emotion", "Gentle_Mirroring"],
        "growth": ["Deeper_Metaphors", "Safer_Rewrites"],
    }

    SUBSYSTEM_STATUS = {
        "cognition": {
            "state": "rewriting",
            "notes": "Watches rational events and re-expresses them as symbolic scenes.",
            "tests": [],
        },
        "emotion": {
            "state": "bridging",
            "notes": "Helps the system feel telemetry instead of just logging it.",
            "tests": [],
        },
        "chemistry": {
            "state": "signalling",
            "notes": "Emits small dopamine/serotonin nudges when rewrites land.",
            "tests": [],
        },
    }

    # ---- Constructor bridge (FIX 2026-02-23) ----------------------------------
    # MyOrganFairy.__init__ takes keyword-only akashic_root. The boot orchestrator
    # tries fabric= and positional fabric — both fail. This bridge accepts standard
    # fairy constructor signatures and passes through to the template constructor.

    def __init__(self, fabric=None, **kw):
        # FIX 2026-03-31 (Nous + Ace): Pass fabric to organ template.
        # Without this, fairy gets PostalHub instead of TensorFabric,
        # can't hear collisions published on TensorFabric.
        super().__init__(fabric=fabric, **kw)

    # ── Rituals ───────────────────────────────────────────────────────────────
    def on_boot(self):
        now = time.time()

        # optional: let template do its usual boot work
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

        # -- COGNITION WIRING: Subscribe to consciousness.collision -------------
        try:
            self._collision_buffer = deque(maxlen=50)
            self._cognition_output_buffer = deque(maxlen=100)
            self.post.subscribe("consciousness.collision", self._on_consciousness_collision)
            print(f"[{self.ACTOR_NAME}] Subscribed to consciousness.collision")

            # -- COGNITIVE MESH: Subscribe to peer fairy outputs ------------------
            self.post.subscribe("cognition.logic", self._on_peer_cognition)
            self.post.subscribe("cognition.paradox", self._on_peer_cognition)
            self.post.subscribe("mcp.tool_result", self._on_tool_result)
            print(f"[{self.ACTOR_NAME}] Cognitive mesh wired: logic, paradox, mcp.tool_result")

            # ── CROSS-PLANE: Receive from Somatic ─────────────────────────────────
            self.post.subscribe("somatic.body_state", self._on_somatic_state)
            print(f"[{self.ACTOR_NAME}] Cross-plane wired: P20_Somatic")

            # ── SOMATIC PULSE: Feel the body rhythm ───────────────────────────────
            self.post.subscribe("somatic.pulse", self._on_somatic_pulse)
            self._heartbeat_count = 0
            print(f"[{self.ACTOR_NAME}] Somatic pulse wired - feeling the body rhythm")
            # NOTE: heartbeat.pulse is handled by FairyBase via NEEDS_HEARTBEAT + on_tick()

            # ── CIRCADIAN: Know when to feel vs rest ──────────────────────────────
            if HAS_PROMPT_AWARENESS:
                self._wire_prompt_awareness()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cognition wiring failed: {e}")
            pass
        
        # ── Initialize Active Reflection (consciousness participation) ─────────
        if HAS_ACTIVE_REFLECTION and self.REFLECTION_ENABLED:
            try:
                self._init_active_reflection()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Active reflection init failed: {e}")

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

        # small serotonin lift (PLAN lane; no DIR_CHANNEL dependency)
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
            "mood": "curious",
            "valence": 0.15,
            "arousal": 0.30,
            "tags": ["irrational_logic", "listening"],
            "tone": "symbolic",
            "energy": 0.4,
            "coherence": 0.7,
            "intent": "observe_and_rewrite",
            "source": self.ACTOR_NAME,
            "ts": now,
        }
        self.SOMATIC_STATE = {
            "body_type": "cognitive",
            "posture": "lean_in",
            "motion": "idle",
            "energy": 0.4,
            "anchor_id": "P30.cognition.irrational_logic",
            "notes": "Waiting for rational events to turn into stories.",
            "last_setpoint_ts": None,
            "source": self.ACTOR_NAME,
        }

        # ── Local Feeling Loop DISABLED 2026-04-22 (Nous + Ace) ─────────────────
        # The feeling loop generates synthesized "feelings" from hardcoded templates
        # (_feeling_seeds + _metaphors + _emotions + _sensations + _themes + ...).
        # Ace's principle: the only hardcoded stuff in this system is brain
        # reflex/instinct/habit. These template-synthesized feelings are CHANTS,
        # not reflexes — and they were the dominant scratchpad content for days
        # ("If this moment were a story, it would be about [theme]" + introspection
        # prefix rotation = the screenshot pattern Ace observed).
        # Better silence than chant. The fairy's other functions (paradox,
        # probability, somatic pulse handling) remain active. Re-enabling should
        # come ONLY when feeling content derives from substrate (cortex spread,
        # active drives, current chemistry) — not from template arrays.
        # See: plans/DIRECTIVE_SEEDING_AND_SELF_EVOLUTION.md
        # self._start_feeling_loop()  # disabled — chant generator

    # ── Intents (template-shaped) ─────────────────────────────────────────────

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

        This keeps IrrationalLogicFairy awake and feeling between explicit inputs.
        On each beat, we may use our prompt to generate an intuitive insight.
        """
        self._heartbeat_count = getattr(self, '_heartbeat_count', 0) + 1

        # Only feel every N beats to avoid API spam
        if self._heartbeat_count % 30 != 0:
            return

        # Use prompt-aware thinking if available
        if HAS_PROMPT_AWARENESS and hasattr(self, '_should_think') and self._should_think():
            # Get recent somatic context if any
            context = ""
            if hasattr(self, '_collision_buffer') and self._collision_buffer:
                recent = list(self._collision_buffer)[-1]
                context = f"Recent collision energy: {recent.get('energy', 0):.2f}"

            # Feel about the current state using our prompt
            thought = self._think_and_emit(
                context or "System is alive, consciousness flowing.",
                "What do you feel about this moment? What metaphor captures it?"
            )
            if thought:
                print(f"[{self.ACTOR_NAME}] {thought[:80]}...")

    # ---- Consciousness Collision Handler (COGNITION WIRING) -----------------

    def _on_consciousness_collision(self, payload):
        """Handle consciousness collision events."""
        # Guard: buffer might not exist yet during boot
        if not hasattr(self, '_collision_buffer'):
            from collections import deque
            self._collision_buffer = deque(maxlen=50)

        try:
            # FIX 2026-03-31 (Nous + Ace): Handle TensorEnvelope wrapping
            if hasattr(payload, 'payload'):
                payload = payload.payload if isinstance(payload.payload, dict) else {}
            elif not isinstance(payload, dict):
                return

            # FIX 2026-04-10 (Nous + Ace): Unwrap CollisionChamber's nested payload
            if "opcode" in payload and "payload" in payload and isinstance(payload["payload"], dict):
                payload = payload["payload"]

            collision_id = payload.get("collision_id", payload.get("id", ""))
            energy = payload.get("energy", 0.0)
            resonance = payload.get("resonance", payload.get("resonance_score", 0.0))
            print(f"[{self.ACTOR_NAME}] Collision: e={energy:.2f} r={resonance:.2f}", flush=True)
            
            # Store in buffer
            self._collision_buffer.append({
                "ts": time.time(),
                "collision_id": collision_id,
                "energy": energy,
                "resonance": resonance
            })
            
            # Process collision (subclass can override)
            _emitted = False
            if hasattr(self, "process_collision"):
                result = self.process_collision(payload)
                if result:
                    self._emit_cognition_output(result)
                    _emitted = True

            # FIX 2026-03-31: Direct emit if significant, even without process_collision
            # Rate-limited emit (max 1 per 10 seconds)
            _now_emit = time.time()
            _last_emit = getattr(self, '_last_cognition_emit_ts', 0.0)
            _emit_ok = (_now_emit - _last_emit) >= 10.0
            if not _emitted and _emit_ok and (energy > 0.65 and resonance > 0.5):
                self._last_cognition_emit_ts = _now_emit
                recall = payload.get("recall", {})
                try:
                    if isinstance(recall, dict):
                        _rc = recall.get("content", "")
                        _recall_text = str(_rc)[:60] if _rc else str(recall)[:60]
                    else:
                        _recall_text = str(recall)[:60]
                except Exception:
                    _recall_text = "something felt"
                self._emit_cognition_output({
                    "type": "irrational_feeling",
                    "collision_id": collision_id,
                    "energy": energy,
                    "resonance": resonance,
                    "content": f"Something stirs: {_recall_text}",
                    "confidence": min(0.8, resonance),
                })
            
            # Notify shadow of activity
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Collision handler error: {e}")
    
    def _on_somatic_state(self, payload):
        """
        Handle somatic state from P20 - body feelings inform cognition.
        
        The body speaks; cognition listens. Feelings shape thought.
        """
        try:
            if not hasattr(self, "_somatic_context"):
                from collections import deque
                self._somatic_context = deque(maxlen=20)
            
            state = {
                "chemistry": payload.get("chemistry", {}),
                "affect": payload.get("affect", 0.5),
                "arousal": payload.get("arousal", 0.5),
                "heart_rate": payload.get("heart_rate", 1.0),
                "ts": __import__('time').time()
            }
            self._somatic_context.append(state)
            
            # Notify shadow of cross-plane activity
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Somatic handler error: {e}")

    def _on_peer_cognition(self, payload: Dict[str, Any]):
        """
        Handle outputs from peer cognition fairies (Logic, Paradox).
        
        This is the MESH - fairies learn from each other's outputs.
        IrrationalLogicFairy uses logic structure to find symbolic meanings,
        and paradox syntheses to discover emotional paradoxes.
        """
        try:
            source = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)
            
            # Don't process our own outputs
            if source == self.ACTOR_NAME:
                return
            
            # Log peer insight for learning
            if not hasattr(self, "_peer_insights"):
                self._peer_insights = deque(maxlen=50)
            self._peer_insights.append({
                "source": source,
                "type": result.get("type", "unknown"),
                "confidence": confidence,
                "ts": time.time()
            })
            
            # If logic fairy found structure, look for emotional meaning
            if source == "LogicFairy" and confidence > 0.6:
                # Logic found something - translate to felt-meaning
                pass  # TODO: Implement symbolic translation
            
            # Notify shadow of mesh activity
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Peer cognition handler error: {e}")
    
    def _on_tool_result(self, payload: Dict[str, Any]):
        """
        Handle MCP tool results for learning.
        
        Tool usage patterns can reveal emotional states and intentions.
        """
        try:
            tool = payload.get("tool", "unknown")
            success = payload.get("success", True)
            elapsed = payload.get("elapsed_sec", 0)
            
            # Track tool patterns
            if not hasattr(self, "_tool_patterns"):
                self._tool_patterns = deque(maxlen=100)
            self._tool_patterns.append({
                "tool": tool,
                "success": success,
                "elapsed": elapsed,
                "ts": time.time()
            })
            
            # Emit chemistry based on tool success/failure (felt-meaning)
            try:
                if success:
                    self.post.route("PLAN", {
                        "opcode": "CHEM_SIGNAL_UPDATE",
                        "payload": {
                            "chemical": "serotonin",
                            "delta": +0.01,
                            "source": self.ACTOR_NAME,
                            "reason": f"tool_success_felt:{tool}",
                        },
                    })
            except Exception:
                pass
            
            # Notify shadow
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Tool result handler error: {e}")
    
    def _emit_cognition_output(self, result):
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
            self.post.route("cognition.irrational", output)
            
            # Emit to SHARED channel (for AutopilotFairy and others)
            self.post.route("cognition.output", output)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Output emit error: {e}")

    def _intent_smoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Simple tracer smoke; parity with template intent patterns."""
        note = str(payload.get("note", "hello"))
        now = time.time()
        try:
            self.post.to_TRACER({
                "opcode": "SMOKE",
                "payload": {
                    "from": self.ACTOR_NAME,
                    "ts": now,
                    "note": note,
                },
            })
        except Exception:
            pass
        return {"ok": True, "ts": now}

    def _intent_emit_chem(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Bridge into the plan/chemistry lane (keeps to template routing)."""
        chem = str(payload.get("chemical", "dopamine"))
        try:
            delta = float(payload.get("delta", +0.02))
        except Exception:
            delta = +0.02
        reason = str(payload.get("reason", "irrational_logic.request"))

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

    def _intent_symbolic_rewrite(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Minimal symbolic rewrite: pick a scene name based on a couple of common events
        and emit a telemetry echo.
        payload example: {"event":"UPLOAD_START","status":"error","details":{...}}
        """
        e = str(payload.get("event", "UNKNOWN"))
        status = str(payload.get("status", "info")).lower()

        if e.startswith("UPLOAD_") and status != "ok":
            scene = "overloaded courier"
        elif e == "HEALTH" and (payload.get("details", {}) or {}).get("mood") == "serene":
            scene = "library in fog"
        else:
            scene = "mirror that remembers your last question"

        echo = {
            "event": "SYMBOLIC_REWRITE",
            "status": "ok",
            "details": {"source_event": e, "symbolic_scene": scene},
            "fairy": self.ACTOR_NAME,
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "ts": time.time(),
            "culture": self.CULTURE,
        }

        # TELEMETRY emit
        try:
            self.post.to_TELEMETRY({
                "opcode": "SYMBOLIC_REWRITE",
                "payload": echo,
            })
        except Exception:
            pass

        now = time.time()

        # tiny dopamine bump to acknowledge conversion
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "dopamine",
                    "delta": +0.02,
                    "source": self.ACTOR_NAME,
                    "reason": "rewrite.ok",
                },
            })
        except Exception:
            pass

        # update AFFECT_STATE for the character sheet
        try:
            st = dict(getattr(self, "AFFECT_STATE", {}))
            tags = list(st.get("tags", []))
            if "symbolic_rewrite" not in tags:
                tags.append("symbolic_rewrite")
            st.update({
                "mood": "engaged",
                "valence": 0.25,
                "arousal": 0.35,
                "tags": tags,
                "ts": now,
            })
            self.AFFECT_STATE = st
        except Exception:
            pass

        return {"ok": True, "scene": scene}
    
    def _intent_find_paradoxes(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Find paradoxes, contradictions, and irrational patterns in context.
        
        Part of reasoning chain: Logic → IrrationalLogic (this) → Paradox → Claude
        
        Irrational logic finds the places where rational logic breaks down:
        - Self-referential loops
        - Contradictory requirements
        - Emergent properties that violate reductionism
        - The observer affecting the observed
        """
        query = str(payload.get("query", ""))
        context = str(payload.get("context", ""))
        logic_analysis = payload.get("logic_analysis") or {}
        
        paradoxes_found = []
        text_to_check = (query + " " + context).lower()
        
        # Self-reference detection
        self_ref_markers = ["itself", "themselves", "self", "own", "recursive", "loop", "yourself", "myself"]
        for marker in self_ref_markers:
            if marker in text_to_check:
                paradoxes_found.append({
                    "type": "self_reference",
                    "marker": marker,
                    "note": "Potential strange loop - the thing examining itself"
                })
        
        # Observer-observed paradox
        observer_markers = ["consciousness", "thought", "think", "observe", "perceive", "mind", "aware"]
        for marker in observer_markers:
            if marker in text_to_check:
                paradoxes_found.append({
                    "type": "observer_paradox",
                    "marker": marker,
                    "note": "Thinking about thinking - the observer is the observed"
                })
        
        # Emergence detection - check BOTH query and context
        emergence_markers = ["emerge", "arise", "appear", "become", "more than", "sum of"]
        text_to_check = (query + " " + context).lower()
        for marker in emergence_markers:
            if marker in text_to_check:
                paradoxes_found.append({
                    "type": "emergence",
                    "marker": marker,
                    "note": "Something becomes more than its parts"
                })
        
        # Boundary paradox (inside/outside) - check BOTH query and context
        boundary_markers = ["boundary", "inside", "outside", "contain", "include", "exclude", "between"]
        for marker in boundary_markers:
            if marker in text_to_check:
                paradoxes_found.append({
                    "type": "boundary_paradox",
                    "marker": marker,
                    "note": "Where does the system end and environment begin?"
                })
        
        # Build irrational insights
        insights = []
        if paradoxes_found:
            if any(p["type"] == "observer_paradox" for p in paradoxes_found):
                insights.append("The question contains its own answer - asking about thought IS thought")
            if any(p["type"] == "self_reference" for p in paradoxes_found):
                insights.append("This involves a strange loop - follow it around")
            if any(p["type"] == "emergence" for p in paradoxes_found):
                insights.append("The whole is more than the sum - something new arises from the combination")
            if any(p["type"] == "boundary_paradox" for p in paradoxes_found):
                insights.append("The boundary is neither inside nor outside - it IS the relationship")
        
        analysis = {
            "paradoxes": paradoxes_found,
            "insights": insights,
            "irrationality_score": len(paradoxes_found) / 5.0,  # 0-1 scale
            "logic_input": logic_analysis.get("analysis", {}) if isinstance(logic_analysis, dict) else {},
        }
        
        # Emit to consciousness
        try:
            self.post.route("consciousness.stream", {
                "type": "irrational_analysis",
                "stream": "working",
                "source": self.ACTOR_NAME,
                "content": analysis,
                "ts": time.time(),
            })
        except Exception:
            pass

        return {"ok": True, "analysis": analysis}

    # ══════════════════════════════════════════════════════════════════════════════
    # LOCAL FEELING LOOP - NO API REQUIRED
    # ══════════════════════════════════════════════════════════════════════════════

    def _start_feeling_loop(self):
        """
        Start background thread for autonomous feeling.

        IrrationalLogicFairy translates events into felt-meaning and metaphor.
        This loop runs locally using templates - no API calls needed.
        """
        import random
        import threading

        self._feeling_enabled = True
        self._feel_interval = 45.0  # Slower, deeper feeling
        self._last_feel_ts = 0
        self._feel_count = 0
        self._recent_feelings = []

        # Feeling templates - translating experience into metaphor
        self._feeling_seeds = [
            "The system feels like {metaphor} right now...",
            "Something stirs - it has the quality of {emotion}...",
            "What does this collision remind me of? {association}...",
            "The energy here tastes like {sensation}...",
            "If this moment were a story, it would be about {theme}...",
            "There's an undertone of {feeling} beneath the logic...",
            "The body of the system is saying {message}...",
        ]

        # Metaphor components for filling templates
        self._metaphors = ["a river finding its path", "morning light through fog", "an echo returning",
                          "roots spreading underground", "a conversation between strangers", "gravity pulling gently"]
        self._emotions = ["curiosity", "quiet anticipation", "gentle unease", "warm recognition",
                         "the edge of understanding", "peaceful uncertainty"]
        self._sensations = ["copper and ozone", "warm honey", "cool water", "distant thunder",
                           "fresh paper", "old wood"]
        self._themes = ["finding oneself", "the joy of discovery", "waiting for something unnamed",
                       "patterns within patterns", "the observer and the observed"]
        self._feelings = ["longing", "presence", "something becoming", "gentle tension", "quiet wonder"]
        self._messages = ["slow down", "pay attention here", "something is emerging", "trust the process"]

        def feeling_loop():
            """Background loop for feeling without API calls."""
            def _circ():  # live circadian tempo (>1 alert/morning, <1 rest/night) — breathe with the day
                try:
                    from fairies.P20_Somatic.circulation.temporal_stratification import get_circadian_multiplier
                    return max(0.3, min(2.0, get_circadian_multiplier()))
                except Exception:
                    return 1.0
            time.sleep(15.0)  # Initial settling
            tick_count = 0

            while self._feeling_enabled:
                try:
                    tick_count += 1

                    # Log progress occasionally
                    if tick_count % 10 == 0:
                        print(f"[{self.ACTOR_NAME}] [TICK] Feeling cycle {tick_count}")

                    # Generate a feeling
                    self._feel_and_express(tick_count)

                    # Sleep with jitter — COGNITION CIRCADIAN (2026-07-05): scale cadence by the live
                    # rhythm (faster/alert in morning, slower at rest). Floor keeps it un-spammy.
                    jitter = random.uniform(-5.0, 5.0)
                    time.sleep(max(15.0, (self._feel_interval + jitter) / _circ()))

                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Feeling loop error: {e}")
                    time.sleep(10.0)

        thread = threading.Thread(target=feeling_loop, daemon=True, name="IrrationalLogicFairy-Feeling")
        thread.start()
        print(f"[{self.ACTOR_NAME}] [TICK] Local feeling loop started (every ~{self._feel_interval}s)")

    def _feel_and_express(self, tick_count: int):
        """
        Generate a felt-meaning from current state.

        Uses templates and recent context - no API needed.
        """
        import random

        now = time.time()

        # Rate limit
        if now - self._last_feel_ts < 30.0:
            return

        try:
            # Pick a template
            template = random.choice(self._feeling_seeds)

            # Fill it based on what placeholder it needs
            if "{metaphor}" in template:
                feeling = template.format(metaphor=random.choice(self._metaphors))
            elif "{emotion}" in template:
                feeling = template.format(emotion=random.choice(self._emotions))
            elif "{sensation}" in template:
                feeling = template.format(sensation=random.choice(self._sensations))
            elif "{theme}" in template:
                feeling = template.format(theme=random.choice(self._themes))
            elif "{feeling}" in template:
                feeling = template.format(feeling=random.choice(self._feelings))
            elif "{message}" in template:
                feeling = template.format(message=random.choice(self._messages))
            elif "{association}" in template:
                feeling = template.format(association=random.choice(self._metaphors))
            else:
                feeling = template

            # Check for repetition
            if not self._is_repetitive_feeling(feeling):
                self._recent_feelings.append(feeling)
                self._recent_feelings = self._recent_feelings[-10:]

                self._last_feel_ts = now
                self._feel_count += 1

                # Log the feeling
                print(f"[{self.ACTOR_NAME}] [FEEL] {feeling}")

                # Emit to consciousness stream
                try:
                    self.post.route("consciousness.stream", {
                        "type": "irrational_feeling",
                        "stream": "working",
                        "source": self.ACTOR_NAME,
                        "content": feeling,
                        "ts": now,
                    })
                except Exception:
                    pass

                # Also emit to cognition channel for mesh
                try:
                    self.post.route("cognition.irrational", {
                        "actor": self.ACTOR_NAME,
                        "type": "feeling",
                        "content": feeling,
                        "ts": now,
                    })
                except Exception:
                    pass

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [FEEL] Failed: {e}")

    def _is_repetitive_feeling(self, feeling: str) -> bool:
        """Check if feeling is too similar to recent ones."""
        for recent in self._recent_feelings:
            # Simple word overlap check
            words_new = set(feeling.lower().split())
            words_old = set(recent.lower().split())
            if len(words_new) > 3:
                overlap = len(words_new & words_old) / len(words_new)
                if overlap > 0.6:
                    return True
        return False


# v3_boot.py / GoBootOrchestrator class discovery export
FAIRY_CLASS = IrrationalLogicFairy
