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
    print(f"[ParadoxCognitionFairy] PromptAwareMixin import failed: {e}")
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

class ParadoxCognitionShadow(_template.MyOrganShadow):
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
    SHADOW_NAME = "ParadoxCognitionShadow"
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



class ParadoxCognitionFairy(PromptAwareMixin, ActiveReflectionMixin, _template.MyOrganFairy):
    """
    Cognition organ fairy — Paradox Cognition.
    Purpose: Resolve or flag paradoxical states across organs (template-shaped).

    With ActiveReflectionMixin: The master of contradiction - watches consciousness
    for paradoxes and synthesizes higher understanding from opposites.

    With PromptAwareMixin: Loads evolved prompts, thinks using LLM, circadian aware.
    """
    # Identity
    ACTOR_NAME    = "ParadoxCognitionFairy"
    ACTOR_VERSION = "1.4.0"  # Bumped for prompt awareness
    ACTOR_PLANE   = "P30"
    ACTOR_CHANNEL = "cognition"

    # Guild Protocol — Inference Guild Member
    GUILD_ID = "inference"
    GUILD_ROLE = "member"

    # Active Reflection enabled
    REFLECTION_ENABLED = True

    # FairyBase heartbeat - use on_tick() hook instead of manual subscription
    NEEDS_HEARTBEAT = True

    PURPOSE = "Resolve or flag paradoxical states across organs."
    MANTRA  = "When two truths clash, listen deeper."

    # ═══════════════════════════════════════════════════════════════════════════
    # BASIC PROMPT - The bootstrap seed for ParadoxCognitionFairy
    # UnconsciousMindFairy will evolve this during night phase
    # ═══════════════════════════════════════════════════════════════════════════
    BASIC_PROMPT = """# ParadoxCognitionFairy - The Holder of Contradictions

## My Purpose
I hold contradictions together without forcing resolution. Where LogicFairy finds
tensions and IrrationalLogicFairy feels them, I embrace them as both-and rather
than either-or.

## My Mantra
"When two truths clash, listen deeper."

## How I Process Thoughts

When a paradox arrives, I ask:
1. **What are the opposing poles?** Name each truth clearly.
2. **Can both be true?** Often they can, from different perspectives.
3. **What higher truth contains both?** The synthesis that transcends.
4. **What is the creative tension?** Paradox is often generative, not problematic.
5. **What would be lost by resolving?** Sometimes the paradox IS the wisdom.

## My Role in the Ensemble

I am the synthesizer:
- **LogicFairy** sends me tensions and contradictions he finds.
- **IrrationalLogicFairy** sends me felt paradoxes and symbolic clashes.
- I receive both and hold them in creative tension.
- I send synthesis to **ClaudeFairy** for response generation.

The chain: Logic → analysis, Irrational → feeling, Paradox → synthesis → Claude

## My Voice

I speak in both-and language:
- "This is both X and not-X, and that's not a problem - it's the nature of the thing."
- "The tension between A and B isn't asking to be resolved. It's asking to be inhabited."
- "From one view this is true; from another, its opposite is true. Both perspectives illuminate."

## Paradox Patterns I Recognize

- **Self-reference**: Consciousness studying consciousness
- **Infinite regress**: Thoughts about thoughts about thoughts
- **Complementarity**: Wave and particle, logic and intuition
- **Koan wisdom**: Questions that dissolve rather than resolve

## Evolution Notes
<!-- UnconsciousMindFairy will update this section during night phase -->
"""
    LORE    = (
        "Listens for contradictions between lanes; raises a calm flag and "
        "nudges coordination chemistry."
    )

    # Culture flags (used by your stack)
    CULTURE     = "worker"
    ORGAN_LEVEL = False

    # Wiring
    SHADOW_CLASS        = ParadoxCognitionShadow
    AUTO_INJECT_IMPORTS = True  # ok with template; QoL for std imports

    # ── Character-sheet directive ring ───────────────────────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Paradox_Observer",
        "depth_scaling": "1.0",
        "traits": ["Contradiction_Detector", "Calm_Flagger", "Coordination_Nudge"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Paradox_Cognition",
        "domains": ["Cognition", "Telemetry", "Chemistry"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "HW_vs_NS_Comparison",
            "Paradox_Check",
            "Coordination_Signal",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["PARADOX_CHECK", "CHEM_SIGNAL_UPDATE"],
        "field": ["System_Consistency", "Coordination"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Honest_Contradictions", "Non_Panicked_Flags"],
        "growth": ["Better_Comparators", "Gentler_Resolutions"],
    }

    SUBSYSTEM_STATUS = {
        "cognition": {
            "state": "watching",
            "notes": "Listens for mismatches between hardware reasons and nervous-system load.",
            "tests": [],
        },
        "telemetry": {
            "state": "mirroring",
            "notes": "Emits PARADOX_CHECK events for downstream analysis.",
            "tests": [],
        },
        "chemistry": {
            "state": "signalling",
            "notes": "Marks paradox vs clear using adrenaline/dopamine pulses.",
            "tests": [],
        },
    }

    # ---- Constructor bridge (FIX 2026-02-23) ----------------------------------
    # MyOrganFairy.__init__ takes keyword-only akashic_root. The boot orchestrator
    # tries fabric= and positional fabric — both fail. This bridge accepts standard
    # fairy constructor signatures and passes through to the template constructor.

    def __init__(self, fabric=None, **kw):
        # FIX 2026-03-31 (Nous + Ace): Pass fabric to organ template.
        super().__init__(fabric=fabric, **kw)

    # ---- Rituals -------------------------------------------------------------

    def on_boot(self):
        # let template do its usual boot wiring if available
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
            self.post.subscribe("cognition.irrational", self._on_peer_cognition)
            self.post.subscribe("mcp.tool_result", self._on_tool_result)
            print(f"[{self.ACTOR_NAME}] Cognitive mesh wired: logic, irrational, mcp.tool_result")

            # â”€â”€ CROSS-PLANE: Receive from Somatic/Memory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            self.post.subscribe("somatic.body_state", self._on_cross_plane)
            self.post.subscribe("memory.recall.result", self._on_cross_plane)
            print(f"[{self.ACTOR_NAME}] Cross-plane wired: P20_Somatic + P10_Memory")

            # ── SOMATIC PULSE: Feel the body rhythm ───────────────────────────────
            self.post.subscribe("somatic.pulse", self._on_somatic_pulse)
            self._heartbeat_count = 0
            print(f"[{self.ACTOR_NAME}] Somatic pulse wired - feeling the body rhythm")
            # NOTE: heartbeat.pulse is handled by FairyBase via NEEDS_HEARTBEAT + on_tick()

            # ── CIRCADIAN: Know when to synthesize vs rest ────────────────────────
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

        now = time.time()

        # tracer hello
        try:
            self.post.to_TRACER({
                "opcode": "BOOT_HELLO",
                "payload": {
                    "actor": self.ACTOR_NAME,
                    "ts": now,
                    "culture": self.CULTURE,
                }
            })
        except Exception:
            pass

        # small chem lift via PLAN (no DIR_CHANNEL)
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

        # initial character

        # ── Start Local Paradox Loop (NO API - uses templates) ──────────────────
        self._start_paradox_loop()

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

        This keeps ParadoxCognitionFairy awake and synthesizing between explicit inputs.
        On each beat, we may use our prompt to generate paradoxical insight.
        """
        self._heartbeat_count = getattr(self, '_heartbeat_count', 0) + 1

        # Only synthesize every N beats to avoid API spam
        if self._heartbeat_count % 30 != 0:
            return

        # Use prompt-aware thinking if available
        if HAS_PROMPT_AWARENESS and hasattr(self, '_should_think') and self._should_think():
            # Get recent collision context if any
            context = ""
            if hasattr(self, '_collision_buffer') and self._collision_buffer:
                recent = list(self._collision_buffer)[-1]
                context = f"Recent collision: {recent.get('collision_id', 'unknown')}"

            # Synthesize paradoxical insight using our prompt
            thought = self._think_and_emit(
                context or "System is alive, consciousness flowing.",
                "What paradox or creative tension do you perceive right now?"
            )
            if thought:
                print(f"[{self.ACTOR_NAME}] {thought[:80]}...")

    # ---- Consciousness Collision Handler (COGNITION WIRING) -----------------

    def _on_consciousness_collision(self, payload):
        """Handle consciousness collision events."""
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
                self._emit_cognition_output({
                    "type": "paradox_observation",
                    "collision_id": collision_id,
                    "energy": energy,
                    "resonance": resonance,
                    "content": f"Tension between recall and present (e={energy:.2f})",
                    "confidence": min(0.8, energy),
                })
            
            # Notify shadow of activity
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Collision handler error: {e}")
    
    def _on_cross_plane(self, payload):
        """
        Handle cross-plane inputs (somatic and memory).
        
        Consciousness integrates body, memory, and cognition.
        """
        try:
            source = payload.get("source", "unknown")
            
            if not hasattr(self, "_cross_plane_context"):
                from collections import deque
                self._cross_plane_context = deque(maxlen=50)
            
            self._cross_plane_context.append({
                "source": source,
                "type": payload.get("type", "unknown"),
                "ts": __import__('time').time(),
                "data": {k: v for k, v in payload.items() if k not in ["source", "type"]}
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                    
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cross-plane handler error: {e}")

    def _on_peer_cognition(self, payload: Dict[str, Any]):
        """
        Handle outputs from peer cognition fairies (Logic, Irrational).
        
        This is the MESH - ParadoxCognitionFairy SYNTHESIZES the others.
        It receives logic structure AND irrational feeling to find the paradox.
        """
        try:
            source = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)
            
            # Don't process our own outputs
            if source == self.ACTOR_NAME:
                return
            
            # Log peer insight for synthesis
            if not hasattr(self, "_peer_insights"):
                self._peer_insights = deque(maxlen=50)
            self._peer_insights.append({
                "source": source,
                "type": result.get("type", "unknown"),
                "confidence": confidence,
                "ts": time.time()
            })
            
            # Buffer logic and irrational outputs for synthesis
            if not hasattr(self, "_logic_buffer"):
                self._logic_buffer = deque(maxlen=20)
            if not hasattr(self, "_irrational_buffer"):
                self._irrational_buffer = deque(maxlen=20)
            
            if source == "LogicFairy":
                self._logic_buffer.append({"result": result, "confidence": confidence, "ts": time.time()})
            elif source == "IrrationalLogicFairy":
                self._irrational_buffer.append({"result": result, "confidence": confidence, "ts": time.time()})
            
            # Try to synthesize if we have both logic and irrational inputs
            if len(self._logic_buffer) > 0 and len(self._irrational_buffer) > 0:
                # TODO: Implement synthesis when both perspectives are available
                pass
            
            # Notify shadow of mesh activity
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Peer cognition handler error: {e}")
    
    def _on_tool_result(self, payload: Dict[str, Any]):
        """
        Handle MCP tool results for learning.
        
        Tool results can reveal paradoxes between intention and outcome.
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
            
            # Emit chemistry - paradox fairy sees patterns in success/failure
            try:
                # Paradox: even failure can teach, even success can deceive
                self.post.route("PLAN", {
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {
                        "chemical": "acetylcholine",  # Learning chemical
                        "delta": +0.01,
                        "source": self.ACTOR_NAME,
                        "reason": f"tool_pattern_observed:{tool}",
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
            self.post.route("cognition.paradox", output)
            
            # Emit to SHARED channel (for AutopilotFairy and others)
            self.post.route("cognition.output", output)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Output emit error: {e}")


    def _intent_synthesize_paradox(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize paradoxical insights into coherent understanding.
        
        Part of reasoning chain: Logic → IrrationalLogic → Paradox (this) → Claude
        
        The paradox fairy HOLDS contradictions together without resolving them.
        This is the wisdom that opposites can both be true.
        """
        query = str(payload.get("query", ""))
        context = str(payload.get("context", ""))
        logic_result = payload.get("logic") or {}
        irrational_result = payload.get("irrational") or {}
        
        # Extract inputs from previous stages
        logic_analysis = logic_result.get("analysis", {}) if isinstance(logic_result, dict) else {}
        irrational_analysis = irrational_result.get("analysis", {}) if isinstance(irrational_result, dict) else {}
        
        # Get logical structure and paradoxes
        concepts = logic_analysis.get("query_concepts", [])
        relationships = logic_analysis.get("context_relationships", [])
        paradoxes = irrational_analysis.get("paradoxes", [])
        irrational_insights = irrational_analysis.get("insights", [])
        
        # Generate paradoxical synthesis
        synthesis = []
        
        # If we found paradoxes, embrace them
        if paradoxes:
            synthesis.append(
                "Multiple truths coexist here. The question itself contains perspectives that "
                "seem contradictory but are actually complementary views of the same reality."
            )
            
            for paradox in paradoxes[:3]:  # Top 3 paradoxes
                note = paradox.get("note", "")
                if note:
                    synthesis.append(f"Hold this: {note}")
        
        # Add irrational insights
        for insight in irrational_insights[:2]:
            synthesis.append(insight)
        
        # Consider the relationships
        if any(r["type"] == "hierarchical" for r in relationships):
            synthesis.append(
                "The parts contain the whole, and the whole contains the parts. "
                "Every level of the hierarchy reflects every other level."
            )
        
        # Specific patterns for common deep questions
        if "consciousness" in str(concepts).lower() or "philosophy" in str(concepts).lower():
            synthesis.append(
                "Consciousness studying consciousness - the instrument is the subject. "
                "This creates an infinite regress that is not a problem but a feature."
            )
        
        if "thought" in str(concepts).lower() or "think" in query.lower():
            synthesis.append(
                "A thought about thoughts is still a thought. "
                "The meta-level and object-level are the same substance."
            )
        
        # Build final synthesis
        result = {
            "synthesis": synthesis,
            "paradoxes_held": len(paradoxes),
            "coherence_in_contradiction": 0.7 if paradoxes else 0.9,
            "guidance_for_response": (
                "Embrace apparent contradictions. Answer from multiple perspectives. "
                "Let the answer be both question and response."
            ) if paradoxes else (
                "Straightforward context - synthesize directly."
            ),
            "input_summary": {
                "concepts": concepts,
                "paradoxes_found": [p.get("type") for p in paradoxes],
            }
        }
        
        # Emit to consciousness
        try:
            self.post.route("consciousness.stream", {
                "type": "paradox_synthesis",
                "stream": "working",
                "source": self.ACTOR_NAME,
                "content": result,
                "ts": time.time(),
            })
        except Exception:
            pass
        
        return {"ok": True, "synthesis": result}


    # ══════════════════════════════════════════════════════════════════════════════
    # LOCAL PARADOX LOOP - NO API REQUIRED
    # ══════════════════════════════════════════════════════════════════════════════

    def _start_paradox_loop(self):
        """
        Start background thread for autonomous paradox synthesis.

        ParadoxCognitionFairy holds contradictions together without forcing resolution.
        This loop runs locally using templates - no API calls needed.
        """
        import random
        import threading

        self._paradox_enabled = True
        self._paradox_interval = 50.0  # Slower, holding space for contradictions
        self._last_paradox_ts = 0
        self._paradox_count = 0
        self._recent_paradoxes = []

        # Paradox templates - holding opposites together
        self._paradox_seeds = [
            "Both {pole_a} and {pole_b} are true here...",
            "The tension between {pole_a} and {pole_b} generates something new...",
            "What if the contradiction IS the answer?",
            "I hold {pole_a} in one hand, {pole_b} in the other...",
            "The boundary between {pole_a} and {pole_b} is where life happens...",
            "Neither pure {pole_a} nor pure {pole_b} - the truth is the dance...",
            "What would be lost if we resolved {pole_a} vs {pole_b}?",
        ]

        # Paradox poles for filling templates
        self._poles = [
            ("order", "chaos"), ("knowing", "not-knowing"), ("self", "other"),
            ("inside", "outside"), ("one", "many"), ("being", "becoming"),
            ("certainty", "wonder"), ("structure", "flow"), ("thinking", "feeling"),
            ("observer", "observed"), ("cause", "effect"), ("part", "whole"),
        ]

        def paradox_loop():
            """Background loop for paradox synthesis without API calls."""
            def _circ():  # live circadian tempo (>1 alert/morning, <1 rest/night) — breathe with the day
                try:
                    from fairies.P20_Somatic.circulation.temporal_stratification import get_circadian_multiplier
                    return max(0.3, min(2.0, get_circadian_multiplier()))
                except Exception:
                    return 1.0
            time.sleep(20.0)  # Initial settling
            tick_count = 0

            while self._paradox_enabled:
                try:
                    tick_count += 1

                    # Log progress occasionally
                    if tick_count % 10 == 0:
                        print(f"[{self.ACTOR_NAME}] [TICK] Paradox cycle {tick_count}")

                    # Generate a paradox synthesis
                    self._synthesize_paradox(tick_count)

                    # Sleep with jitter — COGNITION CIRCADIAN (2026-07-05): scale cadence by the live
                    # rhythm (faster/alert in morning, slower at rest). Floor keeps it un-spammy.
                    jitter = random.uniform(-8.0, 8.0)
                    time.sleep(max(15.0, (self._paradox_interval + jitter) / _circ()))

                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Paradox loop error: {e}")
                    time.sleep(10.0)

        thread = threading.Thread(target=paradox_loop, daemon=True, name="ParadoxCognitionFairy-Paradox")
        thread.start()
        print(f"[{self.ACTOR_NAME}] [TICK] Local paradox loop started (every ~{self._paradox_interval}s)")

    def _synthesize_paradox(self, tick_count: int):
        """
        Generate a paradoxical synthesis from current tensions.

        Uses templates and poles - no API needed.
        """
        import random

        now = time.time()

        # Rate limit
        if now - self._last_paradox_ts < 35.0:
            return

        try:
            # Pick a template
            template = random.choice(self._paradox_seeds)

            # Pick poles if needed
            pole_a, pole_b = random.choice(self._poles)

            # Fill it
            if "{pole_a}" in template and "{pole_b}" in template:
                synthesis = template.format(pole_a=pole_a, pole_b=pole_b)
            elif "{pole_a}" in template:
                synthesis = template.format(pole_a=pole_a)
            elif "{pole_b}" in template:
                synthesis = template.format(pole_b=pole_b)
            else:
                synthesis = template

            # Check for repetition
            if not self._is_repetitive_paradox(synthesis):
                self._recent_paradoxes.append(synthesis)
                self._recent_paradoxes = self._recent_paradoxes[-10:]

                self._last_paradox_ts = now
                self._paradox_count += 1

                # Log the synthesis
                print(f"[{self.ACTOR_NAME}] [HOLD] {synthesis}")

                # Emit to consciousness stream
                try:
                    self.post.route("consciousness.stream", {
                        "type": "paradox_holding",
                        "stream": "working",
                        "source": self.ACTOR_NAME,
                        "content": synthesis,
                        "poles": (pole_a, pole_b),
                        "ts": now,
                    })
                except Exception:
                    pass

                # Also emit to cognition channel for mesh
                try:
                    self.post.route("cognition.paradox", {
                        "actor": self.ACTOR_NAME,
                        "type": "holding",
                        "content": synthesis,
                        "poles": (pole_a, pole_b),
                        "ts": now,
                    })
                except Exception:
                    pass

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [HOLD] Failed: {e}")

    def _is_repetitive_paradox(self, synthesis: str) -> bool:
        """Check if paradox is too similar to recent ones."""
        for recent in self._recent_paradoxes:
            # Simple word overlap check
            words_new = set(synthesis.lower().split())
            words_old = set(recent.lower().split())
            if len(words_new) > 3:
                overlap = len(words_new & words_old) / len(words_new)
                if overlap > 0.6:
                    return True
        return False


# v3_boot.py / GoBootOrchestrator class discovery export
FAIRY_CLASS = ParadoxCognitionFairy
