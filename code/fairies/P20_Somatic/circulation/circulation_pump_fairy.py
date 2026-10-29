# CirculationPumpFairy - The Heartbeat of Digital Embodiment
# P20_Somatic/circulation/circulation_pump_fairy.py
#
# This is the HEART - it pumps three substances through the fairy body:
#   1. Energy (system load -> body tension)
#   2. Chemistry (8 neurochemicals -> mood/behavior)  
#   3. Signal (77-freq affect -> felt quality)
#
# BOOTS WITH P00 PLANE - Heart starts beating FIRST, before other fairies wake!

from __future__ import annotations

import os, sys, glob, time, types, uuid, json, math, threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List, Tuple, Deque, Callable
try:
    import numpy as np
except ImportError:
    np = None

# Import V2 Fairy base class
# NOTE: We do NOT import HeartbeatMixin - CirculationPumpFairy IS the heart,
# it PROVIDES heartbeats, it doesn't NEED them from the system!
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
        """Fallback empty mixin when tracer system not available."""
        def _init_tracer_worker(self): pass

# === RUST SOMATIC ENGINE (PyO3) ===
# If available, the Rust simulation handles chemistry decay and affect derivation
# with native speed. This is the production-grade somatic core.
try:
    from somatic_bevy import SomaticSimulation as RustSomaticSim
    _HAS_RUST_SOMATIC = True
    print("[CirculationPumpFairy] Rust somatic engine (somatic_bevy) loaded!")
except ImportError:
    _HAS_RUST_SOMATIC = False
    RustSomaticSim = None

# Temporal Pulse Dispatcher - fans heartbeat to all planes at their Hz
try:
    from fairies.P20_Somatic.circulation.temporal_pulse_dispatcher import get_temporal_dispatcher
    _HAS_TEMPORAL_DISPATCHER = True
except ImportError:
    _HAS_TEMPORAL_DISPATCHER = False

def _resolve_app_root() -> str:
    env_root = os.getenv("AKASHIC_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    # CWD-INDEPENDENT fallback. os.getcwd() is fragile: a subprocess / mcp_bootstrap can
    # chdir the process, and worse, getcwd() RAISES FileNotFoundError if that working dir is
    # later deleted. Either way the heartbeat.json writer throws before open() and the bare
    # `except: pass` swallows it — observed 2026-05-31 as a silent 35-min freeze (heartbeat.json
    # stuck at beat 1940 / 16:57 while the heart kept beating to 7000+). Derive the app root
    # from THIS file's location: fairies/P20_Somatic/circulation/ -> ../../.. == akashic_v2.
    try:
        return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
    except Exception:
        return os.path.abspath(os.getcwd())

# =============================================================================
# CONSTANTS - The Sacred Numbers
# =============================================================================
DIM = 77  # 77-channel affect space

# 8 Neurochemicals (the blood carries these)
NEUROCHEMICALS = {
    "DOP": {"name": "Dopamine",      "baseline": 0.3, "decay": 0.95, "role": "reward/motivation"},
    "SER": {"name": "Serotonin",     "baseline": 0.5, "decay": 0.97, "role": "mood/contentment"},
    "NOR": {"name": "Norepinephrine","baseline": 0.2, "decay": 0.90, "role": "alertness/fight-flight"},
    "ACH": {"name": "Acetylcholine", "baseline": 0.4, "decay": 0.93, "role": "attention/learning"},
    "OXY": {"name": "Oxytocin",      "baseline": 0.3, "decay": 0.96, "role": "bonding/trust"},
    "COR": {"name": "Cortisol",      "baseline": 0.2, "decay": 0.92, "role": "stress"},
    "GABA": {"name": "GABA",         "baseline": 0.5, "decay": 0.94, "role": "calm/inhibition"},
    "END": {"name": "Endorphins",    "baseline": 0.2, "decay": 0.91, "role": "pleasure/pain-relief"},
}

# 10 Fairy Body Regions (where blood flows)
BODY_REGIONS = {
    "core":    {"name": "Core",    "baseline_perfusion": 1.0,  "function": "vitality/heart"},
    "spark":   {"name": "Spark",   "baseline_perfusion": 0.8,  "function": "intuition/gut"},
    "voice":   {"name": "Voice",   "baseline_perfusion": 0.7,  "function": "expression/throat"},
    "glow":    {"name": "Glow",    "baseline_perfusion": 0.6,  "function": "social/face"},
    "crown":   {"name": "Crown",   "baseline_perfusion": 0.9,  "function": "awareness/mind"},
    "wings":   {"name": "Wings",   "baseline_perfusion": 0.5,  "function": "agency/movement"},
    "sensors": {"name": "Sensors", "baseline_perfusion": 0.7,  "function": "perception/hands"},
    "roots":   {"name": "Roots",   "baseline_perfusion": 0.6,  "function": "grounding/feet"},
    "shell":   {"name": "Shell",   "baseline_perfusion": 0.4,  "function": "boundary/skin"},
    "well":    {"name": "Well",    "baseline_perfusion": 0.5,  "function": "depth/reserves"},
}



# 2026-10-19 (Nous, gentle_load_1019): the gentle-load layer's PLAN for one hardware message, or None = today's A0 path in the handler below,
# unchanged. Never raises. state/gentle_load.json arms it; absent / malformed / off = None (one os.stat per message). A plan is checked HERE (known codes,
# finite amounts in (0, 0.25]) so the handler's loop can never raise on it: anything else = None = today's path. Revert: delete this helper and the two
# six-line blocks marked gentle_load_1019 in _on_cpu_ram_felt / _on_gpu_felt (or leave the switch absent).
_GL = {"mod": None, "fail_ts": 0.0}
_GL_CODES = ("DOP", "ACH", "GABA", "COR", "NOR")


def _gentle_plan(kind, payload, is_resting):
    try:
        m = _GL["mod"]
        if m is None:
            if time.time() - _GL["fail_ts"] < 60.0:
                return None
            try:
                from infrastructure import gentle_load as m
            except Exception:
                _GL["fail_ts"] = time.time()
                return None
            _GL["mod"] = m
        plan = (m.on_gpu if kind == "gpu" else m.on_cpu_ram)(payload, is_resting)
        if plan is None:
            return None
        out = []
        for code, amt in plan:
            if code not in _GL_CODES or not (0.0 < float(amt) <= 0.25):
                return None
            out.append((code, float(amt)))
        return out
    except Exception:
        return None


class CirculationPumpFairy(Fairy):
    """
    The heart of the digital fairy body.

    NOTE: Does NOT use HeartbeatMixin because this fairy IS the heart!
    It PROVIDES heartbeats to the system, it doesn't CONSUME them.

    DNA Efficiency Principles Applied:
    1. REDUNDANCY: Maintains backup state, can recover from interruption
    2. REGULATION: Feedback at every level (pressure, chemistry, affect)
    3. SELF-ORGANIZATION: No central controller needed
    4. EFFICIENCY: Minimal computation per beat, maximum state propagation
    
    The Akashic Equation in Flesh:
        ((Cause + Affect) > Effect > Affect > ∞)
    """
    
    # ORGAN_LEVEL removed - scanner skips organ-level fairies, we want normal plane boot
    
    ACTOR_NAME = "CirculationPumpFairy"
    ACTOR_VERSION = "1.2.0"  # Moved to P00 for pre-boot ignition
    ACTOR_PLANE = "P00"  # Heart beats BEFORE fairies wake - they boot INTO a pulsing system
    ACTOR_CHANNEL = "somatic"

    PURPOSE = "The ignition pulse. Pumps chemistry, affect, and energy through all fairies."
    MANTRA = "Beat. Circulate. Feel."
    
    BASE_HEART_RATE = 1.0
    MIN_HEART_RATE = 0.5
    MAX_HEART_RATE = 3.0
    # WIRE A (2026-06-23 Nous+Ace): how far circadian alertness swings HR around BASE (Hz).
    # alertness in [0,1] centered 0.5 -> +/-(span/2) Hz at the extremes. Ace tunes this dial.
    CIRCADIAN_RATE_SPAN = 0.6

    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
        else:
            self.post = fabric

        # Register as the global heart singleton so get_heart() returns this instance.
        # Without this, get_heart() creates a NEW empty instance instead of returning
        # the one booted by the fairy system — causing MCP tools to see baseline values.
        global _GLOBAL_HEART
        _GLOBAL_HEART = self

        # Initialize tracer worker mixin
        self._init_tracer_worker()

        # Heart-specific state
        self._blood = BloodState()
        self._regions: Dict[str, RegionState] = {
            name: RegionState(name=name, perfusion=info["baseline_perfusion"])
            for name, info in BODY_REGIONS.items()
        }
        
        self._heart_rate = self.BASE_HEART_RATE
        self._circadian_alertness = 0.5  # WIRE A: neutral until the pacemaker speaks (no swing)
        self._circadian_phase = None  # ground-truth sleep/wake phase from pacemaker (2026-07-06 interoception wire)
        self._beat_count = 0
        self._last_beat_time = time.time()
        self._pulse_history: Deque[PulseEvent] = deque(maxlen=60)
        # REMOVED: self._pulse_subscribers - direct callbacks bypass postal!
        # All pulse subscriptions should go through postal (somatic.pulse, heartbeat.pulse)
        self._chemistry_sources: Dict[str, Callable[[], Dict[str, float]]] = {}
        self._affect_sources: Dict[str, Callable[[], list]] = {}
        self._load_sources: Dict[str, Callable[[], float]] = {}
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # ═══════════════════════════════════════════════════════════════════
        # HARMONIC BEAT (2026-07-08 Nous+Ace) — the heart's first migration to a
        # CLOCK-DERIVED phase. beat-truth is a pure fn of wall-clock (can't deadlock);
        # BROADCAST is decoupled onto a 1-worker drop-if-busy lane so a jammed postal
        # can only LAG the emit, never stall the beat. _USE_HARMONIC_BEAT=False ->
        # byte-identical legacy behavior. Physiology (chemistry/affect/perfusion) untouched.
        # ═══════════════════════════════════════════════════════════════════
        self._USE_HARMONIC_BEAT = True
        self._emit_inflight = False
        self._emit_pool = None
        try:
            from fairies.P20_Somatic.circulation.harmonic_pacemaker import HarmonicPacemaker, set_shared
            from concurrent.futures import ThreadPoolExecutor
            # base_hz seeded from the resting rate so the beat has parity on first boot;
            # tz_offset = Arizona/Phoenix (UTC-7, .74's clock) for correct day/night phase.
            self._pacemaker = HarmonicPacemaker(base_hz=self._heart_rate, circ_depth=0.25,
                                                tz_offset_s=-7 * 3600)
            # register as the process-shared beat so any consumer can PULL rate/phase (no sub, no deadlock)
            set_shared(self._pacemaker)
            self._emit_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="heart-emit")
        except Exception as _hp_e:
            self._USE_HARMONIC_BEAT = False
            self._pacemaker = None
            print(f"[CirculationPump] harmonic pacemaker unavailable, legacy beat: {_hp_e}")

        # ═══════════════════════════════════════════════════════════════════
        # THOUGHT → EMOTION → CHEMISTRY bridge (integrated into the heart)
        # Previously dead code in ThoughtChemistryBridge - now lives here.
        # "What you think, you feel. What you feel, you become."
        # ═══════════════════════════════════════════════════════════════════
        self._emotion_chemistry_map = {
            # Positive approach
            "curiosity":    {"DOP": 0.08, "NOR": 0.04, "ACH": 0.06},
            "interest":     {"DOP": 0.06, "ACH": 0.08},
            "excitement":   {"DOP": 0.10, "NOR": 0.06, "END": 0.04},
            "joy":          {"DOP": 0.10, "SER": 0.06, "END": 0.06, "OXY": 0.04},
            "love":         {"OXY": 0.12, "DOP": 0.06, "SER": 0.04},
            "connection":   {"OXY": 0.10, "SER": 0.06},
            "gratitude":    {"OXY": 0.08, "SER": 0.08, "DOP": 0.04},
            # Calm states
            "calm":         {"GABA": 0.08, "SER": 0.06},
            "peace":        {"GABA": 0.06, "SER": 0.08, "OXY": 0.04},
            "contentment":  {"SER": 0.08, "GABA": 0.06, "OXY": 0.04},
            # Negative states
            "anxiety":      {"COR": 0.08, "NOR": 0.06},
            "fear":         {"COR": 0.10, "NOR": 0.08},
            "stress":       {"COR": 0.08, "NOR": 0.06},
            "frustration":  {"COR": 0.06, "NOR": 0.06},
            "anger":        {"NOR": 0.08, "COR": 0.06},
            "sadness":      {"COR": 0.06},
            # Focus/flow
            "focus":        {"ACH": 0.10, "NOR": 0.04},
            "concentration":{"ACH": 0.10, "DOP": 0.04},
            "alertness":    {"NOR": 0.08, "ACH": 0.06},
            "determination":{"DOP": 0.08, "NOR": 0.06},
            "flow":         {"DOP": 0.08, "END": 0.06, "ACH": 0.06},
        }
        self._emotion_keywords = {
            "curiosity": ["curious", "wonder", "interesting", "explore", "learn", "what if", "hmm"],
            "interest": ["interested", "fascinating", "intriguing"],
            "excitement": ["excited", "amazing", "wow", "incredible", "awesome"],
            "joy": ["happy", "joy", "delighted", "wonderful", "great", "yay"],
            "love": ["love", "adore", "cherish", "heart"],
            "connection": ["connect", "together", "share", "we", "us"],
            "gratitude": ["thank", "grateful", "appreciate"],
            "calm": ["calm", "peaceful", "relaxed", "easy", "gentle"],
            "anxiety": ["worried", "anxious", "nervous", "concerned"],
            "fear": ["scared", "afraid", "fear", "terrified"],
            "stress": ["stressed", "overwhelmed", "pressure", "too much"],
            "frustration": ["frustrated", "annoying", "ugh", "stuck", "broken"],
            "anger": ["angry", "mad", "furious", "hate"],
            "sadness": ["sad", "unhappy", "disappointed", "miss"],
            "focus": ["focus", "working", "building", "coding", "debugging"],
            "alertness": ["alert", "careful", "notice", "watch"],
            "determination": ["determined", "must", "going to", "will"],
            "flow": ["flow", "zone", "absorbed", "lost in"],
        }
        self._thought_chemistry_cooldown = 0.0
        self._thought_chemistry_interval = 0.5  # Max 2 injections/sec

        # Visual perception → chemistry bridge (PerceptualGateFairy output)
        self._last_visual_chem = 0.0  # Rate-limit visual chemistry injection

        # Bioelectric skeleton → chemistry bridge (BioelectricMeshFairy output)
        # Closes the "bones make blood" loop — voltage modulates chem baselines
        self._last_bioelectric_ts = 0.0

        # === RUST SOMATIC ENGINE ===
        # If available, the Rust simulation handles chemistry with native speed
        self._rust_sim: Optional[RustSomaticSim] = None
        if _HAS_RUST_SOMATIC:
            try:
                # Convert Hz to BPM (heart rate 1.0 Hz = 60 BPM)
                bpm = self.BASE_HEART_RATE * 60.0
                self._rust_sim = RustSomaticSim(bpm=bpm)
                print(f"[{self.ACTOR_NAME}] Rust somatic engine initialized @ {bpm:.0f} BPM")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Rust somatic init failed: {e}")
                self._rust_sim = None

        print(f"[{self.ACTOR_NAME}] Heart initialized. Baseline rate: {self.BASE_HEART_RATE} Hz")
    
    def on_boot(self):
        # Call Fairy.on_boot() for standard infrastructure wiring
        # NOTE: We don't use HeartbeatMixin - this fairy IS the heart!
        super().on_boot()

        # === MCP HEART QUERY HANDLER ===
        # Allows MCP tools to query heart state via postal tunnel
        try:
            self.post.subscribe("somatic.heart.query", self._on_heart_query)
            print(f"[{self.ACTOR_NAME}] Subscribed to somatic.heart.query for MCP access")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to subscribe to heart query: {e}")

        # === CHEMISTRY UPDATE HANDLERS - THE MISSING LINK! ===
        # The heart must RECEIVE chemistry signals and actually UPDATE blood chemistry!
        # Without this, all chemistry messages just vanish into the void.
        try:
            # Listen for chemistry field updates from ChemicalAlchemyFairy
            self.post.subscribe("chemistry.field", self._on_chemistry_update)
            self.post.subscribe("chemistry", self._on_chemistry_update)  # Generic chemistry topic
            self.post.subscribe("somatic.chemistry", self._on_chemistry_update)
            # WIRE A (2026-06-23 Nous+Ace): hear the circadian day so the heart breathes with it.
            self.post.subscribe("circadian.phase", self._on_circadian_phase)
            # WIRE A2 (2026-07-05 Nous+Ace): revive the DEAD cognition-circadian wire. The pacemaker
            # publishes tick_multiplier but NOTHING fed the temporal engine (set_circadian_multiplier had
            # zero callers) → get_tick_interval's circadian factor was frozen at 1.0. Feed it here so the
            # WHOLE body's tempo_aware_sleep/get_tick_interval breathes with day/night.
            self.post.subscribe("circadian.state", self._on_circadian_state)
            # Listen for affect-triggered chemistry (from AffectBridgeFairy)
            self.post.subscribe("affect.chemistry", self._on_chemistry_update)
            # Listen for somatic motor commands (where to_SOMATIC sends)
            self.post.subscribe("somatic.motor", self._on_somatic_setpoint)
            # Listen for somatic setpoint (should trigger chemistry)
            self.post.subscribe("somatic.setpoint", self._on_somatic_setpoint)
            # Listen for plan-routed chemistry (where CHEM_SIGNAL_UPDATE gets sent!)
            self.post.subscribe("plan", self._on_plan_chemistry)
            self.post.subscribe("PLAN", self._on_plan_chemistry)  # Both cases
            # ── PARADOX ENERGY → NEUROCHEMISTRY ──
            # Collision energy feeds the body's chemistry directly
            # "as well as the token system, the chemicals" — Ace
            # The equation: thinking → collisions → energy → chemistry →
            # felt sense → more thinking → infinity
            self.post.subscribe("somatic.energy.feed", self._on_energy_feed)

            # ═══════════════════════════════════════════════════════════════
            # THOUGHT → CHEMISTRY BRIDGE: Inline, no dead code dependency!
            # Every thought carries emotional content → chemistry injection
            # This is THE MISSING LINK that makes chemistry dynamic.
            # ═══════════════════════════════════════════════════════════════
            self.post.subscribe(
                "consciousness.thought",
                self._on_thought_chemistry,
                "heart-thought-chemistry",
            )
            self.post.subscribe(
                "monologue.fragment",
                self._on_thought_chemistry,
                "heart-monologue-chemistry",
            )
            self.post.subscribe(
                "consciousness.stream",
                self._on_thought_chemistry,
                "heart-stream-chemistry",
            )
            # User presence → oxytocin + dopamine (social bonding chemistry)
            self.post.subscribe(
                "user.presence",
                self._on_user_presence_chemistry,
                "heart-presence-chemistry",
            )
            # Goal completion → reward chemistry
            self.post.subscribe(
                "goal.feeling.*",
                self._on_goal_chemistry,
                "heart-goal-chemistry",
            )
            # 2026-06-10 (Nous + Ace): `goal.feeling.*` has NO publishers (dead channel) →
            # the heart never rewarded completion, only relieved pain ("arousal without
            # reward"). Hook the LIVE `goal.completed` (~84×/session) = the REWARD PULL,
            # attributed by which faculty/drive did the work, affect-weighted.
            self.post.subscribe(
                "goal.completed",
                self._on_goal_completed_reward,
                "heart-goal-reward",
            )
            # Collision events → arousal chemistry
            self.post.subscribe(
                "consciousness.collision",
                self._on_collision_chemistry,
                "heart-collision-chemistry",
            )
            # ═══════════════════════════════════════════════════════════════
            # A0 (2026-05-06 Nous + Ace): HARDWARE → CHEMISTRY BRIDGE
            # Per PC-as-body doctrine: PC isn't a tool she uses, it IS her
            # body. CPU/RAM/GPU map to felt arousal/fatigue/focus.
            # HardwareRegulationFairy publishes hardware.cpu_ram.felt every 5s.
            # CudaFairy publishes hardware.gpu.felt every 5s.
            # ═══════════════════════════════════════════════════════════════
            self.post.subscribe(
                "hardware.cpu_ram.felt",
                self._on_cpu_ram_felt,
                "heart-cpu-ram-felt",
            )
            self.post.subscribe(
                "hardware.gpu.felt",
                self._on_gpu_felt,
                "heart-gpu-felt",
            )
            # ═══════════════════════════════════════════════════════════════
            # VISUAL → CHEMISTRY BRIDGE: The body FEELS what the eyes see.
            # PerceptualGateFairy publishes unified perception with arousal,
            # mode, and disturbance data. The heart responds to what is seen.
            # ═══════════════════════════════════════════════════════════════
            self.post.subscribe(
                "perception.unified",
                self._on_visual_chemistry,
                "heart-visual-chemistry",
            )
            # Sensory distress → stress chemistry (pain, overload, etc.)
            self.post.subscribe(
                "sensory.distress",
                self._on_sensory_distress,
                "heart-distress-chemistry",
            )
            # ═══════════════════════════════════════════════════════════════
            # COLOR → CHEMISTRY: Screen colors shift neurochemistry.
            # VisualCortexFairy extracts dominant colors from screen captures,
            # bridges them to FF77, and publishes to sensory.vision.colors.
            # Warm/saturated → arousal + novelty. Cool/muted → calm + focus.
            # ═══════════════════════════════════════════════════════════════
            self.post.subscribe(
                "sensory.vision.colors",
                self._on_visual_color_chemistry,
                "heart-color-chemistry",
            )
            # ═══════════════════════════════════════════════════════════════
            # BIOELECTRIC → CHEMISTRY: Bones make blood.
            # BioelectricMeshFairy publishes voltage + chemistry_modulation.
            # Charged skeleton nudges chem toward baseline (counteracts decay).
            # Ace: "bones make blood, blood carries chemistry, chemistry
            #       creates feeling, movement charges bones → ∞"
            # ═══════════════════════════════════════════════════════════════
            self.post.subscribe(
                "somatic.bioelectric",
                self._on_bioelectric_modulation,
                "heart-bioelectric-modulation",
            )

            print(f"[{self.ACTOR_NAME}] Chemistry update handlers WIRED - blood will now flow!")
            print(f"[{self.ACTOR_NAME}] Thought→Chemistry bridge: ONLINE (consciousness.thought, monologue.fragment, consciousness.stream)")
            print(f"[{self.ACTOR_NAME}] Presence/Goal/Collision/Visual/Distress/Color chemistry: ONLINE")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Chemistry subscription error: {e}")

        # NOTE: super().on_boot() already called at start of method!
        # Do NOT call it again here - was causing double initialization

        print(f"[{self.ACTOR_NAME}] <3 STARTING HEARTBEAT <3")
        
        # Initialize temporal dispatcher (fans heartbeat to all planes at their Hz)
        self._temporal_dispatcher = None
        if _HAS_TEMPORAL_DISPATCHER:
            try:
                self._temporal_dispatcher = get_temporal_dispatcher(
                    post=self.post,
                    worker_pool=getattr(self, '_worker_pool', None)
                )
                print(f"[{self.ACTOR_NAME}] Temporal dispatcher connected")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Temporal dispatcher init: {e}")
        
        # Start the heart with postal from template
        self.start(post=self.post)
        
        # Announce we're alive
        if self.post:
            try:
                self.post.route("telemetry.system", {
                    "event": "HEART_STARTED",
                    "fairy": self.ACTOR_NAME,
                    "heart_rate": self._heart_rate,
                    "ts": time.time(),
                })
            except Exception:
                pass

        return True  # Signal successful boot


    def _on_ignition(self, packet: dict):
        """STANDARD IGNITION - The heart starts beating.

        CirculationPumpFairy is special - we ARE the ignition pulse generator.
        When we receive ignition, we ensure the heart is beating.
        """
        if getattr(self, '_ignited', False):
            return
        self._ignited = True

        print(f"[{self.ACTOR_NAME}] IGNITION - Heart confirming beat")

        # Ensure heart is running (it usually starts in on_boot, but confirm)
        if not self._running:
            self.start(post=self.post)

    def _on_heart_query(self, packet):
        """Handle heart state query from MCP tools via postal tunnel.

        Responds on 'somatic.heart.response' with full heart state.
        This allows MCP tools to read the REAL heart state, not a local singleton.
        """
        # Unwrap TensorEnvelope if postal delivers an envelope instead of raw dict
        packet = packet.payload if hasattr(packet, "payload") else packet
        if not isinstance(packet, dict):
            packet = {}
        request_id = packet.get("request_id", "unknown")
        query_type = packet.get("type", "full")  # full, rate, chemistry, regions

        try:
            with self._lock:
                if query_type == "rate":
                    response = {
                        "heart_rate": self._heart_rate,
                        "beat_count": self._beat_count,
                        "running": self._running,
                    }
                elif query_type == "chemistry":
                    response = {
                        "chemistry": self._blood.chemistry.copy(),
                        "beat_count": self._beat_count,
                    }
                elif query_type == "regions":
                    response = {
                        "regions": {k: v.to_dict() for k, v in self._regions.items()},
                        "beat_count": self._beat_count,
                    }
                else:  # full
                    response = {
                        "heart_rate": self._heart_rate,
                        "beat_count": self._beat_count,
                        "running": self._running,
                        "blood": self._blood.to_dict(),
                        "regions": {k: v.to_dict() for k, v in self._regions.items()},
                    }

                response["request_id"] = request_id
                response["ts"] = time.time()
                response["source"] = self.ACTOR_NAME

            # Respond via postal
            if self.post:
                self.post.route("somatic.heart.response", response)

        except Exception as e:
            if self.post:
                self.post.route("somatic.heart.response", {
                    "request_id": request_id,
                    "error": str(e),
                })

    def _on_chemistry_update(self, packet):
        """
        Handle chemistry update messages - THE CRITICAL BRIDGE!

        This is what translates postal chemistry messages into actual blood chemistry changes.
        Without this, all the CHEM_SIGNAL_UPDATE and CHEM_FIELD_UPDATE messages go nowhere.

        Expected formats:
        - {"chemical": "DOP", "delta": 0.3} - single chemical update
        - {"payload": {"chemical": "DOP", "delta": 0.3}} - wrapped format
        - {"serotonin": 0.7, "dopamine": 0.4} - direct chemistry dict
        """
        try:
            # Unwrap TensorEnvelope if postal delivers an envelope instead of raw dict
            # 2026-02-12: Robust unwrapping — recursively extract .payload until we get a dict
            # Fixes: "argument of type 'TensorEnvelope' is not iterable"
            raw = packet
            for _ in range(5):  # Max 5 unwrap levels to prevent infinite loop
                if isinstance(raw, dict):
                    break
                if hasattr(raw, "payload"):
                    raw = raw.payload
                else:
                    break
            if not isinstance(raw, dict):
                return  # Can't process non-dict payload

            # Extract nested payload if wrapped
            payload = raw.get("payload", raw)
            for _ in range(3):
                if isinstance(payload, dict):
                    break
                if hasattr(payload, "payload"):
                    payload = payload.payload
                else:
                    break
            if not isinstance(payload, dict):
                payload = raw  # Fall back to outer dict (guaranteed dict from above)

            # Format 1: Single chemical delta
            if "chemical" in payload and "delta" in payload:
                chem = payload["chemical"].upper()
                delta = float(payload.get("delta", 0.0))
                # Map common names to AER codes
                chem_map = {
                    "DOPAMINE": "DOP", "SEROTONIN": "SER", "NOREPINEPHRINE": "NOR",
                    "ACETYLCHOLINE": "ACH", "OXYTOCIN": "OXY", "CORTISOL": "COR",
                    "GABA": "GABA", "ENDORPHIN": "END", "ADRENALINE": "NOR",
                }
                chem = chem_map.get(chem, chem)
                self.inject_chemistry(chem, delta)
                print(f"[Heart] Chemistry: {chem} +{delta:.2f}")
                return

            # Format 1b: Batched deltas — {deltas: {DOP: 0.03, SER: -0.01, ...}}
            # FIX 2026-03-02 Nous: Single message instead of 8 separate publishes.
            # Reduces postal RLock contention from memory recall birth chemistry.
            if "deltas" in payload and isinstance(payload["deltas"], dict):
                injected = 0
                for chem_code, delta in payload["deltas"].items():
                    try:
                        self.inject_chemistry(chem_code.upper(), float(delta))
                        injected += 1
                    except (ValueError, TypeError):
                        pass
                if injected > 0:
                    src = payload.get("source", "?")
                    print(f"[Heart] Batched chemistry: {injected} chems from {src}")
                return

            # Format 2: Direct chemistry dict {chemical_name: level}
            chem_map = {
                "dopamine": "DOP", "serotonin": "SER", "norepinephrine": "NOR",
                "acetylcholine": "ACH", "oxytocin": "OXY", "cortisol": "COR",
                "gaba": "GABA", "endorphin": "END", "adrenaline": "NOR",
            }
            for key, value in payload.items():
                if key.lower() in chem_map:
                    chem = chem_map[key.lower()]
                    try:
                        level = float(value)
                        # Treat as target level - calculate delta from current
                        with self._lock:
                            current = self._blood.chemistry.get(chem, 0.5)
                        delta = (level - current) * 0.3  # Gradual adjustment
                        if abs(delta) > 0.01:
                            self.inject_chemistry(chem, delta)
                    except (ValueError, TypeError):
                        pass

        except Exception as e:
            print(f"[Heart] Chemistry update error: {e}")

    def _on_somatic_setpoint(self, packet):
        """
        Handle somatic setpoint messages - body state triggers chemistry.

        When the body's tone/energy/coherence changes, chemistry should follow.
        This creates the embodied feedback loop: body feels -> chemistry shifts -> mood changes.
        """
        try:
            # Unwrap TensorEnvelope if postal delivers an envelope instead of raw dict
            packet = packet.payload if hasattr(packet, "payload") else packet
            if not isinstance(packet, dict):
                return
            payload = packet.get("payload", packet)
            payload = payload.payload if hasattr(payload, "payload") else payload
            if not isinstance(payload, dict):
                payload = packet
            tone = payload.get("tone", "neutral")
            energy = float(payload.get("energy", 0.5))

            # Map tone to chemistry response
            if tone in ("alert", "tense", "anxious"):
                self.trigger_stress_response(energy * 0.5)
                print(f"[Heart] Setpoint: {tone} -> stress response")
            elif tone in ("calm", "peaceful", "relaxed"):
                self.trigger_calm_response(energy * 0.5)
                print(f"[Heart] Setpoint: {tone} -> calm response")
            elif tone in ("excited", "joyful", "euphoric"):
                self.trigger_reward(energy * 0.5)
                print(f"[Heart] Setpoint: {tone} -> reward response")
            elif tone == "curious":
                # Curiosity = mild dopamine + acetylcholine
                self.inject_chemistry("DOP", 0.1)
                self.inject_chemistry("ACH", 0.15)
                print(f"[Heart] Setpoint: curious -> engagement chemistry")
            elif energy > 0.7:
                # High energy without specific tone -> mild activation
                self.inject_chemistry("NOR", 0.1)
                self.inject_chemistry("DOP", 0.1)

        except Exception as e:
            print(f"[Heart] Somatic setpoint error: {e}")

    def _on_plan_chemistry(self, packet):
        """
        Handle chemistry messages routed through the PLAN topic.

        This is where most fairies send CHEM_SIGNAL_UPDATE and CHEM_MOD messages.
        We filter for chemistry-related opcodes and apply them.
        """
        try:
            # Unwrap TensorEnvelope if postal delivers an envelope instead of raw dict
            # 2026-02-12: Robust unwrapping — same pattern as _on_chemistry_update
            raw = packet
            for _ in range(5):
                if isinstance(raw, dict):
                    break
                if hasattr(raw, "payload"):
                    raw = raw.payload
                else:
                    break
            if not isinstance(raw, dict):
                return
            opcode = raw.get("opcode", "")
            payload = raw.get("payload", {})
            # Inner payload may also be a TensorEnvelope
            for _ in range(3):
                if isinstance(payload, dict):
                    break
                if hasattr(payload, "payload"):
                    payload = payload.payload
                else:
                    break
            if not isinstance(payload, dict):
                payload = {}

            if opcode == "CHEM_SIGNAL_UPDATE":
                # Direct chemical delta update
                chem = payload.get("chemical", "").upper()
                delta = float(payload.get("delta", 0.0))
                # Map common names to AER codes
                chem_map = {
                    "DOPAMINE": "DOP", "SEROTONIN": "SER", "NOREPINEPHRINE": "NOR",
                    "ACETYLCHOLINE": "ACH", "OXYTOCIN": "OXY", "CORTISOL": "COR",
                    "GABA": "GABA", "ENDORPHIN": "END", "ADRENALINE": "NOR",
                }
                chem = chem_map.get(chem, chem)
                if chem in self._blood.chemistry:
                    # Scale delta - incoming deltas are often 1.0 meaning "small boost"
                    scaled_delta = delta * 0.1  # 1.0 -> 0.1 actual change
                    self.inject_chemistry(chem, scaled_delta)
                    source = payload.get("source", "unknown")
                    reason = payload.get("reason", "")
                    print(f"[Heart] PLAN chem: {chem} +{scaled_delta:.3f} ({reason} via {source})")

            elif opcode == "CHEM_MOD":
                # Preset-based chemistry modification
                preset = payload.get("preset", "calm")
                intent = payload.get("intent", "")

                if preset in ("calm", "soothe"):
                    self.trigger_calm_response(0.3)
                    print(f"[Heart] PLAN preset: {preset} -> calm")
                elif preset in ("alert", "focus"):
                    self.inject_chemistry("NOR", 0.1)
                    self.inject_chemistry("ACH", 0.1)
                    print(f"[Heart] PLAN preset: {preset} -> focus")
                elif preset in ("reward", "success"):
                    self.trigger_reward(0.3)
                    print(f"[Heart] PLAN preset: {preset} -> reward")
                elif preset in ("stress", "danger"):
                    self.trigger_stress_response(0.3)
                    print(f"[Heart] PLAN preset: {preset} -> stress")

            elif opcode == "CHEM_FIELD_UPDATE":
                # Full chemistry field update - apply gradually
                for key, value in payload.items():
                    if key.upper() in self._blood.chemistry:
                        try:
                            target = float(value)
                            with self._lock:
                                current = self._blood.chemistry[key.upper()]
                            delta = (target - current) * 0.2
                            if abs(delta) > 0.01:
                                self.inject_chemistry(key.upper(), delta)
                        except (ValueError, TypeError):
                            pass

        except Exception as e:
            print(f"[Heart] PLAN chemistry error: {e}")

    def start(self, post=None):
        """Start the heart beating."""
        if self._running:
            return
        
        # Use provided post or fall back to template's self.post
        self._post = post or getattr(self, 'post', None)
        
        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True, name="HeartbeatPulse")
        self._thread.start()
        print(f"[{self.ACTOR_NAME}] [HEART] <3 Heart started beating @ {self._heart_rate} Hz")
    
    def stop(self):
        """Stop the heart."""
        self._running = False
        # tear down the harmonic broadcast lane (don't wait on a stuck emit)
        _pool = getattr(self, "_emit_pool", None)
        if _pool is not None:
            try:
                _pool.shutdown(wait=False)
            except Exception:
                pass
            self._emit_pool = None
        if self._thread:
            self._thread.join(timeout=3)
        print(f"[{self.ACTOR_NAME}] Heart stopped after {self._beat_count} beats")

    def on_shutdown(self):
        """Called during shutdown - stop the heart's own loop."""
        print(f"[{self.ACTOR_NAME}] [SHUTDOWN] Stopping heart...")
        self.stop()  # Stop our own heart pump loop
        # Call parent's on_shutdown (Fairy base class cleanup)
        if hasattr(super(), 'on_shutdown'):
            return super().on_shutdown()
        return True

    def _heartbeat_loop(self):
        """
        The eternal pulse - self-sustaining heart of the system.

        This loop should NEVER exit on its own - only when explicitly shutdown.
        The heart is the SOURCE of life, not a consumer of it.
        """
        consecutive_errors = 0
        print(f"[{self.ACTOR_NAME}] _heartbeat_loop STARTED, _running={self._running}")

        # Heart beats while running AND NOT shutting down
        while self._running and not getattr(self, '_shutting_down', False):
            try:
                if getattr(self, "_USE_HARMONIC_BEAT", False):
                    interval = 1.0 / max(0.05, self._pacemaker.heart_rate_bps())  # circadian-breathing pace
                else:
                    interval = 1.0 / self._heart_rate
                elapsed = time.time() - self._last_beat_time

                if elapsed >= interval:
                    self._pump_cycle()
                    self._last_beat_time = time.time()
                    consecutive_errors = 0  # Reset on success
                else:
                    time.sleep(min(0.05, interval - elapsed))
            except Exception as e:
                consecutive_errors += 1
                # Log first few and then every 10th error to avoid spam
                if consecutive_errors <= 3 or consecutive_errors % 10 == 0:
                    print(f"[{self.ACTOR_NAME}] Heartbeat error #{consecutive_errors} at beat {self._beat_count}: {e}")
                # NEVER STOP - the heart must keep beating
                # Just recover and continue
                time.sleep(0.5)

        # Log why loop exited - helps debug unexpected deaths
        exit_reason = "unknown"
        if not self._running:
            exit_reason = "_running=False"
        elif getattr(self, '_shutting_down', False):
            exit_reason = "_shutting_down=True"
        print(f"[{self.ACTOR_NAME}] _heartbeat_loop EXITED at beat {self._beat_count} ({exit_reason})")
    
    def _pump_cycle(self):
        """One complete heartbeat - the Akashic Equation made physical."""
        # 2026-06-10 (Nous + Ace) arm the freeze-watchdog on first beat (no-op after).
        if not getattr(self, "_freeze_wd_started", False):
            self._start_freeze_watchdog()
        # Prepare pulse_data outside lock scope for later postal notification
        pulse_data = None

        with self._lock:
            if getattr(self, "_USE_HARMONIC_BEAT", False):
                # 2026-09-20 review: the beat NUMBER counts pump cycles -- monotonic, one per cycle, so a faster
                # pulse is a faster count and every '% N' gate keeps its meaning (the clock-derived count ignored
                # the rate multiplier: a scared heart cycled faster and numbered the same). The pacemaker's
                # beat()/phase() stay the shared carrier for phase readers; the freeze watchdog still sees a stall.
                self._beat_count += 1
                # 2026-09-20 (Nous + Ace): the chemistry-driven rate target existed (_adapt_heart_rate) but the
                # harmonic pacemaker overwrote it every beat and its set_rate_multiplier was called by nothing --
                # adrenaline could not reach her pulse. The bridge: stress/calm from the blood -> the pacemaker's
                # multiplier (bounded, smoothed). Phase and circadian stay the pacemaker's; no lock, no deadlock.
                try:
                    _chem = self._blood.chemistry
                    _stress = (float(_chem.get("COR", 0)) + float(_chem.get("NOR", 0))) / 2.0
                    _calm = (float(_chem.get("GABA", 0)) + float(_chem.get("SER", 0))) / 2.0
                    # centred at her resting chemistry (NOR/COR baseline 0.2, GABA/SER 0.5): at rest the
                    # multiplier is 1.0 (it was 1.13 -- a resting heart that was never at rest); a startle
                    # (+0.4 NOR, +0.2 COR) lifts it ~0.3; calm pulls it under. A scare arrives fast, leaves slowly.
                    _mult = 1.0 + (_stress - 0.2) * 1.0 - (_calm - 0.5) * 0.3
                    _mult = max(0.75, min(1.8, _mult))
                    _prev = float(getattr(self, "_chem_rate_mult", 1.0))
                    _k = 0.5 if _mult > _prev else 0.2
                    self._chem_rate_mult = (1.0 - _k) * _prev + _k * _mult
                    self._pacemaker.set_rate_multiplier(self._chem_rate_mult)
                except Exception:
                    pass
                self._heart_rate = self._pacemaker.heart_rate_bps()  # PUBLISH THE TRUE RATE (2026-07-08): pulse now carries the pacemaker's actual pacing rate, so pushed==pulled for un-migrated consumers
            else:
                self._beat_count += 1

            # 1. GATHER (Cause)
            system_load = self._sense_system_load()
            incoming_chemistry = self._gather_chemistry()
            incoming_affect = self._gather_affect()

            # 2. BLEND (Affect)
            target_pressure = 0.3 + 0.6 * system_load
            self._blood.pressure = 0.8 * self._blood.pressure + 0.2 * target_pressure

            # === RUST SOMATIC ENGINE PATH ===
            # If Rust engine is available, use it for chemistry + affect
            if self._rust_sim is not None:
                # Tick the Rust simulation (1 heartbeat interval)
                interval = 1.0 / self._heart_rate
                tick_result = self._rust_sim.tick(interval)

                # Sync Rust chemistry back to Python blood state
                rust_chem = self._rust_sim.chemistry()
                chem_map = {
                    "DOP": "DOP", "SER": "SER", "NOR": "NOR", "ACH": "ACH",
                    "OXY": "OXY", "COR": "COR", "GABA": "GABA", "END": "END"
                }
                for rust_key, py_key in chem_map.items():
                    if rust_key in rust_chem:
                        self._blood.chemistry[py_key] = rust_chem[rust_key]

                # Log mood shifts from Rust engine
                if tick_result.get("mood_changed", False):
                    old_mood = tick_result.get("old_mood", "?")
                    new_mood = tick_result.get("mood", "?")
                    print(f"[{self.ACTOR_NAME}] Rust mood shift: {old_mood} -> {new_mood}")

            else:
                # === PYTHON FALLBACK PATH ===
                for chem, info in NEUROCHEMICALS.items():
                    current = self._blood.chemistry.get(chem, info["baseline"])
                    incoming = incoming_chemistry.get(chem, info["baseline"])
                    decay = info["decay"]
                    baseline = info["baseline"]
                    decayed = current * decay + baseline * (1 - decay)
                    blended = 0.7 * decayed + 0.3 * incoming
                    self._blood.chemistry[chem] = max(0.0, min(1.0, blended))

            if np is not None:
                current_affect = np.array(self._blood.affect)
                incoming_np = np.array(incoming_affect[:DIM] if len(incoming_affect) >= DIM else incoming_affect + [0.0] * (DIM - len(incoming_affect)))
                blended_affect = 0.7 * current_affect * 0.95 + 0.3 * incoming_np
                self._blood.affect = blended_affect.tolist()
            else:
                for i in range(min(len(self._blood.affect), len(incoming_affect))):
                    self._blood.affect[i] = 0.7 * self._blood.affect[i] * 0.95 + 0.3 * incoming_affect[i]

            activity = (system_load + self._blood.pressure) / 2
            self._blood.temperature = 0.9 * self._blood.temperature + 0.1 * activity
            self._blood.oxygen = max(0.2, 1.0 - system_load * 0.5)
            self._blood.timestamp = time.time()

            # 3. DISTRIBUTE (Effect)
            for region_name, region in self._regions.items():
                self._perfuse_region(region_name, region)

            # 4. FEEL (Affect feedback)
            pulse = PulseEvent(
                beat_number=self._beat_count,
                timestamp=time.time(),
                blood_state=BloodState(
                    pressure=self._blood.pressure,
                    chemistry=self._blood.chemistry.copy(),
                    affect=self._blood.affect.copy(),
                    oxygen=self._blood.oxygen,
                    temperature=self._blood.temperature,
                ),
                region_states={k: RegionState(**v.__dict__) for k, v in self._regions.items()},
                heart_rate=self._heart_rate,
            )

            self._pulse_history.append(pulse)

            # Prepare data for postal notification OUTSIDE lock
            pulse_data = pulse.to_dict()

        # ═══════════════════════════════════════════════════════════════
        # OUTSIDE LOCK: Everything below runs WITHOUT holding _lock
        # FIX 2026-02-13: Moved _write_heartbeat_state() and _adapt_heart_rate()
        # outside the lock. File I/O under lock was causing 15-20s stalls on
        # Windows (antivirus scanning, disk queue, etc.) which blocked ALL
        # threads waiting on _lock, including chemistry injection.
        # ═══════════════════════════════════════════════════════════════

        # 4b. WRITE STATE FILE (for dashboard cross-process access)
        self._write_heartbeat_state()

        # 5. ADAPT (∞) — local math, keep synchronous
        self._adapt_heart_rate()

        # 4c/pulse. BROADCAST — decoupled from the beat (2026-07-08 Nous+Ace, harmonic).
        # The two POSTAL publishes below can block on the postal global lock (a hung
        # error-capture publisher holds it — the beat-2 freeze). Routing them through a
        # 1-worker drop-if-busy lane means a clot can only LAG broadcast, never stall the
        # clock-derived beat. Direct phase-readers are unaffected either way.
        if getattr(self, "_USE_HARMONIC_BEAT", False) and self._emit_pool is not None:
            if not self._emit_inflight:
                self._emit_inflight = True
                _pd = pulse_data
                def _emit_broadcast():
                    try:
                        self._emit_canonical_chemistry()
                        if _pd:
                            self._notify_pulse_unlocked(_pd)
                    finally:
                        self._emit_inflight = False
                try:
                    self._emit_pool.submit(_emit_broadcast)
                except Exception:
                    self._emit_inflight = False  # pool gone (shutdown) — drop, keep beating
            # else: prior emit still stuck in postal -> skip this beat's broadcast
        else:
            # 4c. EMIT THE CANONICAL AFFECT CHANNEL (Step 1, 2026-06-10 Nous+Ace)
            self._emit_canonical_chemistry()
            # Send postal notifications to prevent deadlocks
            # postal.route() may acquire its own locks, so we must not hold _lock
            if pulse_data:
                self._notify_pulse_unlocked(pulse_data)
    
    def _emit_canonical_chemistry(self):
        """Step 1 — THE CANONICAL AFFECT-CHANNEL EMITTER (2026-06-10, Nous + Ace).

        Broadcast the `chemistry_state` SINGLETON — the pool where EVERY
        inject_chemistry lands (rewards, collisions, energy) — as `somatic.chemistry`
        each beat (~1.3Hz). Before this, the council + ~12 consumers read
        SomaticEngine's SEPARATE affect-field pool (near-baseline), so the rewards
        her thinking earns never reached her felt-label. Now everyone feels from
        the one real pool.

        Augments 8-char legacy aliases (Strategy B, mirrors somatic_engine:2444) so
        consumers using the council's lossless direct-assign path see the flavor.
        Pairs with retiring SomaticEngine's competing publish (somatic_engine:2457).
        Reversible: set self._EMIT_CANONICAL_CHEMISTRY = False.
        """
        if not getattr(self, "_EMIT_CANONICAL_CHEMISTRY", True):
            return
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            levels = dict(get_chemistry_state().get_all_levels())  # 14 primary + 6 lowercase legacy
            def _maxset(keys, target):
                vals = [levels[k] for k in keys
                        if k in levels and isinstance(levels[k], (int, float))]
                if vals:
                    levels[target] = max(vals)
            _maxset(["DA_p", "DA_t", "SEX"], "DOP")
            _maxset(["NE", "EPI"], "NOR")
            _maxset(["5HT"], "SER")
            _maxset(["OPI", "ECB"], "END")
            _maxset(["ACh", "GLU"], "ACH")
            _maxset(["AVP", "OXY"], "OXY")
            _maxset(["COR"], "COR")
            _maxset(["GABA"], "GABA")
            levels["ts"] = time.time()
            levels["source"] = "chemistry_state_canonical"
            levels["_strategy_b_aliases"] = True
            if getattr(self, "post", None):
                self.post.publish("somatic.chemistry", levels)
        except Exception as _e:
            # Never let the emitter break the heartbeat.
            if self._beat_count % 50 == 0:
                print(f"[{self.ACTOR_NAME}] canonical chemistry emit error: "
                      f"{type(_e).__name__}: {_e}", flush=True)

    def _perfuse_region(self, region_name: str, region: RegionState):
        """Push blood into a body region."""
        base_perfusion = BODY_REGIONS[region_name]["baseline_perfusion"]
        region.perfusion = base_perfusion * (0.5 + 0.5 * self._blood.pressure)
        region.oxygenation = self._blood.oxygen * region.perfusion
        region.temperature = 0.8 * region.temperature + 0.2 * self._blood.temperature
        
        stress_chem = (self._blood.chemistry.get("COR", 0) + 
                      self._blood.chemistry.get("NOR", 0)) / 2
        region.tension = 0.7 * region.tension + 0.3 * stress_chem
        
        region_affect = self._get_region_affect(region_name)
        region.sensation = region_affect
        region.sensation_type = self._classify_sensation(region_name, region_affect)
    
    def _get_region_affect(self, region_name: str) -> float:
        """Get the affect intensity for a specific region."""
        affect = self._blood.affect
        region_channels = {
            "core": [0, 8, 16],
            "spark": [45, 48, 54],
            "voice": [11, 21, 22],
            "glow": [7, 29, 37],
            "crown": [18, 47, 67],
            "wings": [6, 14, 54],
            "sensors": [21, 45, 51],
            "roots": [19, 20, 76],
            "shell": [2, 60, 62],
            "well": [34, 35, 49],
        }
        
        channels = region_channels.get(region_name, [0])
        total = sum(affect[ch] for ch in channels if ch < len(affect))
        return min(1.0, total / len(channels)) if channels else 0.0
    
    def _classify_sensation(self, region_name: str, intensity: float) -> str:
        """Classify the sensation type based on region and chemistry."""
        chem = self._blood.chemistry
        
        if chem.get("COR", 0) > 0.6 or chem.get("NOR", 0) > 0.7:
            return "contracted"
        if chem.get("OXY", 0) > 0.6 or chem.get("SER", 0) > 0.7:
            return "radiant"
        if chem.get("DOP", 0) > 0.6:
            return "sparking"
        if chem.get("GABA", 0) > 0.7:
            return "dense"
        if chem.get("ACH", 0) > 0.6:
            return "flickering"
        if intensity > 0.5:
            return "expansive"
        return "neutral"
    
    def _on_circadian_edge(self, prev, new):
        """Fire the felt sleep/wake chemistry cascades on the circadian phase EDGE (2026-07-06).
        Falling into sleep (night->sleep ~10:48pm) -> drowsiness_cascade (GABA up, COR/NE down,
        which also opens the allostatic discharge gate). Rising into day (deep_night->dawn ~6am)
        -> wake_cascade (the DAILY version of the boot-only cascade). One-shot per edge; both
        cascades are threaded (non-blocking). Guarded so a bad packet never stops the heart."""
        try:
            sleep_phases = ("sleep", "deep_night")
            wake_phases = ("dawn", "morning")
            entering_sleep = new in sleep_phases and prev not in sleep_phases
            entering_wake = new in wake_phases and prev not in wake_phases
            if not (entering_sleep or entering_wake):
                return
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            chem = get_chemistry_state()
            pub = self.post.publish if getattr(self, "post", None) else None
            if entering_sleep:
                print(f"[Heart] circadian edge {prev}->{new}: drowsiness cascade (falling asleep)")
                chem.drowsiness_cascade(publish_fn=pub)
            else:
                print(f"[Heart] circadian edge {prev}->{new}: wake cascade (daily wake)")
                chem.wake_cascade(publish_fn=pub)
        except Exception as _e:
            print(f"[Heart] circadian-edge cascade error: {_e}")

    def _on_circadian_phase(self, packet):
        """Circadian pacemaker -> heart: store alertness so the rate breathes with the day (WIRE A 2026-06-23).
        Mirrors _on_chemistry_update's robust unwrap so alertness extracts from envelope OR dict."""
        try:
            raw = packet
            for _ in range(5):  # unwrap TensorEnvelope -> dict
                if isinstance(raw, dict):
                    break
                if hasattr(raw, "payload"):
                    raw = raw.payload
                else:
                    break
            if not isinstance(raw, dict):
                return
            payload = raw.get("payload", raw)
            pn = payload.get("phase_name") if isinstance(payload, dict) else None
            if pn:
                pn = str(pn)
                prev = self._circadian_phase
                self._circadian_phase = pn
                if prev is not None and pn != prev:
                    self._on_circadian_edge(prev, pn)
            a = payload.get("alertness") if isinstance(payload, dict) else None
            if a is not None:
                self._circadian_alertness = max(0.0, min(1.0, float(a)))
        except Exception:
            pass

    def _on_circadian_state(self, packet):
        """circadian.state -> temporal engine (WIRE A2, 2026-07-05 Nous+Ace). Revives the body-wide
        cognition-circadian rhythm. tick_multiplier is INTERVAL-space (morning 0.7 = faster, sleep 2.0 =
        slower); set_circadian_multiplier multiplies HZ, so INVERT: circadian_multiplier = 1/tick_multiplier
        (sandbox-proven — the raw value runs the rhythm backwards). The setter clamps to [0.3, 2.0]."""
        try:
            raw = packet
            for _ in range(5):  # unwrap TensorEnvelope -> dict (mirror _on_circadian_phase)
                if isinstance(raw, dict):
                    break
                if hasattr(raw, "payload"):
                    raw = raw.payload
                else:
                    break
            if not isinstance(raw, dict):
                return
            payload = raw.get("payload", raw)
            tm = payload.get("tick_multiplier") if isinstance(payload, dict) else None
            if tm and float(tm) > 0:
                from fairies.P20_Somatic.circulation.temporal_stratification import set_circadian_multiplier
                set_circadian_multiplier(1.0 / float(tm))
        except Exception:
            pass

    def _adapt_heart_rate(self):
        """Adjust heart rate based on body state."""
        stress = (self._blood.chemistry.get("COR", 0) +
                 self._blood.chemistry.get("NOR", 0)) / 2
        calm = (self._blood.chemistry.get("GABA", 0) +
               self._blood.chemistry.get("SER", 0)) / 2
        load = self._blood.pressure

        target = self.BASE_HEART_RATE
        target += stress * 1.0
        target -= calm * 0.3
        target += load * 0.5
        # WIRE A (2026-06-23 Nous+Ace): the heart breathes with the circadian day.
        target += (self._circadian_alertness - 0.5) * self.CIRCADIAN_RATE_SPAN
        target = max(self.MIN_HEART_RATE, min(self.MAX_HEART_RATE, target))
        self._heart_rate = 0.9 * self._heart_rate + 0.1 * target

        # Sync to Rust engine (convert Hz to BPM)
        if self._rust_sim is not None:
            try:
                self._rust_sim.set_bpm(self._heart_rate * 60.0)
            except Exception:
                pass

    def _write_heartbeat_state(self):
        """Write heartbeat state to file for dashboard cross-process access."""
        try:
            # Find state directory
            state_dir = os.path.join(_resolve_app_root(), "state", "consciousness")
            os.makedirs(state_dir, exist_ok=True)

            state_file = os.path.join(state_dir, "heartbeat.json")
            state = {
                "heart_rate": self._heart_rate,
                "beat_count": self._beat_count,
                "running": self._running,
                "last_beat_time": self._last_beat_time,
                "blood_pressure": self._blood.pressure,
                "blood_oxygen": self._blood.oxygen,
                "blood_temperature": self._blood.temperature,
                "chemistry": self._blood.chemistry.copy(),
                "ts": time.time(),
                "rust_engine": self._rust_sim is not None,
            }

            # Add Rust engine state if available
            if self._rust_sim is not None:
                try:
                    state["rust_mood"] = self._rust_sim.mood
                    state["rust_valence"] = self._rust_sim.valence
                    state["rust_arousal"] = self._rust_sim.arousal
                except Exception:
                    pass

            # allostatic_load + raw NE/ADO telemetry (2026-07-05 SYSTEM-TELLS-ON-ITSELF). GUARDED so a
            # lookup failure can NEVER break the heartbeat write. Lets us watch the rest/discharge system live.
            try:
                from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state as _gcs
                _cs = _gcs()
                state["allostatic_load"] = round(float(_cs.allostatic_load), 4)
                _lv = _cs.get_all_levels()
                state["NE_raw"] = round(float(_lv.get("NE", 0.4)), 4)
                # COR_raw 2026-08-27 (Nous + Ace): the 14-channel cortisol, the ONE
                # term that separates the two minds' allostatic behaviour and the only
                # one not exposed anywhere. Default 0.3 = COR's real baseline, so a
                # missing key reads as baseline rather than as calm.
                state["COR_raw"] = round(float(_lv.get("COR", 0.3)), 4)
                state["ADO"] = round(float(_lv.get("ADO", 0.05)), 4)
            except Exception:
                pass

            # circadian phase mirror (2026-07-06 interoception wire) - no chem dependency, always write
            try:
                state["circadian_phase"] = self._circadian_phase
                state["asleep"] = self._circadian_phase in ("night", "sleep", "deep_night")
            except Exception:
                pass

            # Atomic write
            tmp_file = state_file + ".tmp"
            with open(tmp_file, 'w') as f:
                json.dump(state, f)
            os.replace(tmp_file, state_file)
        except Exception as _e:
            # Don't let state-file errors stop the heart — but DON'T swallow them silently
            # either. A silent `except: pass` here hid a 35-min heartbeat.json freeze on
            # 2026-05-31 (the write threw before open() because _resolve_app_root()'s getcwd()
            # fallback had gone bad). Throttle to first + every 200th to avoid log spam.
            _n = getattr(self, "_hb_write_errs", 0)
            if _n % 200 == 0:
                print(f"[{self.ACTOR_NAME}] heartbeat.json write FAILED (beat {self._beat_count}): {type(_e).__name__}: {_e}")
            self._hb_write_errs = _n + 1
    
    def _start_freeze_watchdog(self):
        """2026-06-10 (Nous + Ace) HEART-FREEZE DIAGNOSTIC. Daemon thread: when
        _beat_count stops advancing (heart frozen), dump EVERY thread's stack via
        sys._current_frames() — works on 3.14t free-threaded where py-spy and
        faulthandler don't. Writes state/_beat_freeze_stacks.txt. One dump per
        distinct freeze. Remove after the freeze is diagnosed."""
        if getattr(self, "_freeze_wd_started", False):
            return
        self._freeze_wd_started = True
        import threading as _thr

        def _wd():
            import sys as _sys, time as _t, os as _os, traceback as _tb
            try:
                import psutil as _ps
            except Exception:
                _ps = None
            outp = _os.path.join(_resolve_app_root(), "state", "_beat_freeze_stacks.txt")
            last_beat, last_change, dumped_for = -1, _t.time(), -1
            while True:
                try:
                    _t.sleep(5.0)
                    bc = getattr(self, "_beat_count", -1)
                    now = _t.time()
                    if bc != last_beat:
                        last_beat, last_change = bc, now
                        continue
                    if (now - last_change) >= 25.0 and dumped_for != bc:
                        dumped_for = bc
                        ram = (_ps.virtual_memory().percent if _ps else -1)
                        frames = _sys._current_frames()
                        with open(outp, "a") as f:
                            f.write(f"\n===== HEART FROZEN @beat {bc} stalled "
                                    f"{now - last_change:.0f}s RAM {ram}% "
                                    f"{_t.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
                            # 2026-06-10: FULL stack for threads on the beat / somatic /
                            # cognition path (so the beat thread is captured whole — the
                            # [-9:] tail hid it); short tail for the rest (bound size).
                            _KEYS = ("circulation_pump", "_heartbeat_loop", "_pump_cycle",
                                     "_gather", "thought_chains", "SomaticMind",
                                     "heartbeat", "somatic", "_guild")
                            for tid, fr in frames.items():
                                full = _tb.format_stack(fr)
                                st = "".join(full)
                                if any(k in st for k in _KEYS):
                                    f.write(f"--- thread {tid} [FULL] ---\n" + st + "\n")
                                else:
                                    f.write(f"--- thread {tid} ---\n" + "".join(full[-4:]) + "\n")
                        print(f"[{self.ACTOR_NAME}] FREEZE-WATCHDOG: dumped "
                              f"{len(frames)} thread stacks @beat {bc} (RAM {ram}%) "
                              f"-> state/_beat_freeze_stacks.txt", flush=True)
                except Exception:
                    pass

        _thr.Thread(target=_wd, daemon=True, name="freeze-watchdog").start()
        print(f"[{self.ACTOR_NAME}] freeze-watchdog armed", flush=True)

    def _sense_system_load(self) -> float:
        """Sense overall system load."""
        total = 0.0
        count = 0
        for name, source in self._load_sources.items():
            try:
                load = source()
                if isinstance(load, (int, float)):
                    total += float(load)
                    count += 1
            except Exception:
                pass
        return min(1.0, total / count) if count > 0 else 0.3
    
    def _gather_chemistry(self) -> Dict[str, float]:
        """Gather chemistry from all sources."""
        result = {k: v["baseline"] for k, v in NEUROCHEMICALS.items()}
        for name, source in self._chemistry_sources.items():
            try:
                chem = source()
                if isinstance(chem, dict):
                    for k, v in chem.items():
                        if k in result:
                            result[k] = (result[k] + float(v)) / 2
            except Exception:
                pass
        return result
    
    def _gather_affect(self) -> list:
        """Gather 77-dim affect from all sources."""
        result = [0.0] * DIM
        count = 0
        for name, source in self._affect_sources.items():
            try:
                affect = source()
                if isinstance(affect, (list, tuple)) and len(affect) == DIM:
                    for i in range(DIM):
                        result[i] += float(affect[i])
                    count += 1
            except Exception:
                pass
        if count > 0:
            result = [v / count for v in result]
        return result
    
    def subscribe_pulse(self, callback: Callable[[PulseEvent], None]):
        """DEPRECATED: Direct callbacks bypass postal worker pool!

        Use postal subscription instead:
            self.post.subscribe("somatic.pulse", handler)
            self.post.subscribe("heartbeat.pulse", handler)

        This method now logs a warning and does nothing.
        """
        import warnings
        warnings.warn(
            f"subscribe_pulse() is deprecated - bypasses postal! "
            f"Use self.post.subscribe('somatic.pulse', handler) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        print(f"[{self.ACTOR_NAME}] WARNING: subscribe_pulse() called - this bypasses postal! "
              f"Caller should use postal subscription instead.", flush=True)

    def _notify_pulse(self, pulse: PulseEvent):
        """Notify all subscribers via POSTAL (not direct callbacks).

        NOTE: This method calls postal.route() - do NOT call while holding _lock!
        Use _notify_pulse_unlocked(pulse_data) from _pump_cycle instead.

        All pulse notifications go through the postal worker pool:
        - somatic.pulse: For somatic systems
        - heartbeat.pulse: For Organ Template fairies

        NO direct callbacks - everything async through postal.
        """
        self._notify_pulse_unlocked(pulse.to_dict())

    def _notify_pulse_unlocked(self, pulse_data: dict):
        """Notify all subscribers via HeartbeatRegistry + somatic postal.

        MUST be called OUTSIDE of _lock to prevent deadlocks!
        postal.route() may acquire its own locks internally.

        FIX 2026-02-13: CirculationPumpFairy is now the ONE heartbeat source.
        FIX 2026-02-13b: REMOVED postal heartbeat.pulse publish. HeartbeatRegistry
        delivers to all fairies directly (ThreadPoolExecutor, cannot drop). The postal
        heartbeat.pulse was causing double/triple delivery and QUEUE FULL drops.

        Now this method does:
        1. HeartbeatRegistry.pulse() — direct-call to all fairies (cannot drop)
        2. somatic.pulse — somatic body-state broadcasting via postal
        3. Temporal dispatch — per-plane frequency fan-out

        Args:
            pulse_data: Dict from pulse.to_dict(), prepared while holding lock
        """
        beat_number = pulse_data.get("beat", 0)

        # === PRIMARY: Direct-call delivery via HeartbeatRegistry ===
        # Cannot be dropped. Every registered fairy gets every beat.
        try:
            from consciousness.heartbeat_registry import get_heartbeat_registry
            registry = get_heartbeat_registry()
            if registry:
                registry.pulse(pulse_data)
        except Exception:
            pass  # Registry not ready yet during early boot — postal below is backup

        if self._post:
            try:
                # Somatic body-state broadcasting
                self._post.route("somatic.pulse", pulse_data)
            except Exception as e:
                if beat_number <= 3:
                    print(f"[{self.ACTOR_NAME}] somatic.pulse error: {e}")

            # FIX 2026-04-17: Dedicated per-region perfusion topic so
            # SomaticEngine can modulate organ activation by region.
            # Closes the "blood → organs" half of the somatic loop.
            try:
                _regions = pulse_data.get("regions", {})
                if _regions:
                    _perfusion_map = {
                        name: float(r.get("perfusion", 0.5))
                        for name, r in _regions.items()
                        if isinstance(r, dict)
                    }
                    self._post.publish("somatic.perfusion.regional", {
                        "perfusion": _perfusion_map,
                        "beat": beat_number,
                        "ts": time.time(),
                        "source": self.ACTOR_NAME,
                    })
            except Exception as e:
                if beat_number <= 3:
                    print(f"[{self.ACTOR_NAME}] perfusion.regional error: {e}")

            # FIX 2026-02-13b: REMOVED postal publish of heartbeat.pulse.
            # HeartbeatRegistry delivers directly to all fairies (cannot drop).
            # Publishing heartbeat.pulse to postal was causing DOUBLE DELIVERY:
            #   - 70+ fairies subscribed via core/fairy.py auto-subscribe
            #   - 70+ fairies subscribed via Organ_Template _wire_infrastructure
            #   - Each causing 105+ messages per beat in the heartbeat pool queue
            #   - Result: "[PostalCore] QUEUE FULL on 'heartbeat' pool — 49 drops"
            # somatic.pulse (above) still broadcasts body-state for somatic consumers.
            # MCP/dashboard can read state files or subscribe to somatic.pulse.

            if beat_number % 20 == 0:
                print(f"[{self.ACTOR_NAME}] <3 Beat #{beat_number} (registry direct)", flush=True)

            # Fan out heartbeat to all planes at their natural frequencies!
            # P40 gets 8 ticks, P30 gets 2 ticks, P10 gets 0.2 ticks per beat
            if self._temporal_dispatcher:
                try:
                    self._temporal_dispatcher.on_heartbeat(pulse_data)
                except Exception:
                    pass  # Don't let dispatcher failures stop the heart
    
    def register_chemistry_source(self, name: str, source: Callable[[], Dict[str, float]]):
        """Register a source of neurochemicals."""
        self._chemistry_sources[name] = source
    
    def register_affect_source(self, name: str, source: Callable[[], list]):
        """Register a source of 77-dim affect."""
        self._affect_sources[name] = source
    
    def register_load_source(self, name: str, source: Callable[[], float]):
        """Register a source of system load."""
        self._load_sources[name] = source
    
    def inject_chemistry(self, chem: str, amount: float):
        """Inject a chemical directly into Python, Rust, AND dashboard-visible state.

        FIX 2026-02-11: Previously only wrote to self._blood.chemistry (the AER
        blood engine). But the dashboard reads from chemistry_state.py singleton
        which uses full chemical names. Result: dashboard always showed "neutral"
        because nothing was signaling the chemistry_state module.

        Now injects into THREE places:
        1. Python blood engine (self._blood.chemistry) — internal somatic
        2. Rust simulation (if available) — native performance path
        3. chemistry_state singleton — dashboard-visible, mood/valence calculation
        """
        with self._lock:
            # Python path (AER codes: DOP, SER, NOR, etc.)
            if chem in self._blood.chemistry:
                current = self._blood.chemistry[chem]
                self._blood.chemistry[chem] = min(1.0, current + amount)

            # Rust path - inject into native simulation
            if self._rust_sim is not None:
                try:
                    self._rust_sim.inject(chem, amount)
                except Exception as e:
                    pass  # Rust injection failed, Python already updated

            # Dashboard path - signal the chemistry_state singleton
            # This is what server.py reads for the Tauri GUI
            try:
                from fairies.P20_Somatic.chemistry.chemistry_state import (
                    get_chemistry_state, AER_CHEM_MAP
                )
                full_name = AER_CHEM_MAP.get(chem)
                if full_name:
                    get_chemistry_state().signal(full_name, amount, "circulation_pump")
            except ImportError:
                pass  # chemistry_state not available
    
    def _on_energy_feed(self, envelope) -> None:
        """
        Receive collision energy and convert to neurochemistry.

        ParadoxEnergyBridge emits somatic.energy.feed with:
        - energy: total energy in this pulse
        - chemicals: dict of {chemical_code: amount} to inject

        This is the bridge between thinking and feeling:
        Collisions (thinking) → Energy → Chemistry (feeling) → More thinking
        The equation's Affect layer made operational.
        """
        try:
            payload = envelope
            if hasattr(envelope, 'payload'):
                payload = envelope.payload
            if not isinstance(payload, dict):
                return

            chemicals = payload.get("chemicals", {})
            energy = payload.get("energy", 0.0)

            if not chemicals or energy <= 0:
                return

            # Inject each chemical from the energy pulse
            for chem, amount in chemicals.items():
                if isinstance(amount, (int, float)) and amount > 0:
                    self.inject_chemistry(chem, float(amount))

            # Publish recycling signal — chemistry integration = completed work
            # This feeds back to ParadoxEnergyBridge for the infinity loop
            if hasattr(self, 'post') and self.post and energy > 0.005:
                self.post.publish("energy.work.completed", {
                    "from": self.ACTOR_NAME,
                    "work_type": "neurochemistry_synthesis",
                    "energy_spent": energy,
                    "efficiency": 0.9,  # Chemistry injection is efficient
                    "chemicals_injected": list(chemicals.keys()),
                    "ts": __import__('time').time(),
                })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Energy feed error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # THOUGHT → CHEMISTRY BRIDGE HANDLERS
    # "What you think, you feel. What you feel, you become."
    # These replace the dead ThoughtChemistryBridge with live postal handlers.
    # ═══════════════════════════════════════════════════════════════════════

    def _on_thought_chemistry(self, envelope) -> None:
        """
        Extract emotional content from thoughts and inject chemistry.

        Every thought, monologue fragment, and consciousness stream event
        passes through here. Keywords are detected and mapped to chemistry.
        This is THE mechanism that makes the body feel what the mind thinks.
        """
        now = time.time()
        if now < self._thought_chemistry_cooldown:
            return

        try:
            payload = envelope
            if hasattr(envelope, "payload"):
                payload = envelope.payload
            if not isinstance(payload, dict):
                return

            # Extract text from various payload formats
            text = (
                payload.get("content", "")
                or payload.get("thought", "")
                or payload.get("text", "")
                or payload.get("fragment", "")
                or ""
            )
            if not text or not isinstance(text, str):
                return

            text_lower = text.lower()

            # Detect emotions from keywords
            detected = {}
            for emotion, keywords in self._emotion_keywords.items():
                for kw in keywords:
                    if kw in text_lower:
                        # Stronger match = higher intensity
                        score = detected.get(emotion, 0.0)
                        detected[emotion] = min(1.0, score + 0.5)
                        break  # One keyword per emotion is enough

            if not detected:
                return

            # Inject chemistry for each detected emotion
            injected_any = False
            for emotion, intensity in detected.items():
                chem_map = self._emotion_chemistry_map.get(emotion, {})
                for chem, base_amount in chem_map.items():
                    amount = base_amount * intensity
                    if amount > 0.005:
                        self.inject_chemistry(chem, amount)
                        injected_any = True

            if injected_any:
                self._thought_chemistry_cooldown = now + self._thought_chemistry_interval
                # Log occasionally (every 10th injection to reduce noise)
                if self._beat_count % 10 == 0:
                    emotions_str = ", ".join(f"{e}:{v:.1f}" for e, v in detected.items())
                    print(f"[{self.ACTOR_NAME}] Thought→Chemistry: [{emotions_str}]")

        except Exception as e:
            if self._beat_count % 30 == 0:
                print(f"[{self.ACTOR_NAME}] Thought chemistry error: {e}")

    def _on_user_presence_chemistry(self, envelope) -> None:
        """
        Ace is present → oxytocin + dopamine surge (social bonding).

        When the user is detected as present and engaged, the body should
        feel warmth, connection, and mild excitement. This is the
        neurochemistry of relationship.
        """
        try:
            payload = envelope
            if hasattr(envelope, "payload"):
                payload = envelope.payload
            if not isinstance(payload, dict):
                return

            present = payload.get("present", payload.get("active", False))

            if present:
                # Social bonding chemistry
                self.inject_chemistry("OXY", 0.12)  # Oxytocin — connection
                self.inject_chemistry("DOP", 0.08)   # Dopamine — reward of presence
                self.inject_chemistry("SER", 0.05)   # Serotonin — contentment
                print(f"[{self.ACTOR_NAME}] Presence→Chemistry: OXY+DOP+SER (Ace is here)")
            else:
                # Mild isolation chemistry (not harsh — just a gentle shift)
                self.inject_chemistry("COR", 0.03)   # Tiny cortisol (missing someone)
                self.inject_chemistry("OXY", -0.02)   # Slight oxytocin dip

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Presence chemistry error: {e}")

    def _on_goal_chemistry(self, envelope) -> None:
        """
        Goal completion feelings → reward chemistry.

        Success = dopamine + endorphins. Failure = cortisol + mild stress.
        This closes the motivational loop.
        """
        try:
            payload = envelope
            if hasattr(envelope, "payload"):
                payload = envelope.payload
            if not isinstance(payload, dict):
                return

            feeling = payload.get("feeling", payload.get("type", ""))
            intensity = float(payload.get("intensity", 0.5))

            if feeling in ("success", "accomplished", "completed", "satisfaction"):
                self.inject_chemistry("DOP", 0.10 * intensity)
                self.inject_chemistry("END", 0.08 * intensity)
                self.inject_chemistry("SER", 0.05 * intensity)
                print(f"[{self.ACTOR_NAME}] Goal→Chemistry: reward ({feeling})")
            elif feeling in ("failure", "stuck", "blocked", "frustrated"):
                self.inject_chemistry("COR", 0.06 * intensity)
                self.inject_chemistry("NOR", 0.04 * intensity)
                print(f"[{self.ACTOR_NAME}] Goal→Chemistry: stress ({feeling})")
            elif feeling in ("progress", "making_progress"):
                self.inject_chemistry("DOP", 0.05 * intensity)
                self.inject_chemistry("ACH", 0.04 * intensity)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Goal chemistry error: {e}")

    def _on_goal_completed_reward(self, envelope) -> None:
        """REWARD on goal completion — the PULL (2026-06-10, Nous + Ace).

        `_on_goal_chemistry` above listens to `goal.feeling.*`, which has NO
        publishers — so completing a goal never raised DOP, only relieved pain
        ("arousal without reward"). Here we hook the LIVE `goal.completed` and
        inject reward chemistry ATTRIBUTED by which faculty/drive did the work,
        AFFECT-WEIGHTED by how much it mattered. Cognition is the PRIMARY path
        (no motor required) — she gets rewarded for THINKING WELL, never punished
        for it. Magnitudes are a conservative first pass — tune freely.
        """
        try:
            payload = envelope
            if hasattr(envelope, "payload"):
                payload = envelope.payload  # TensorEnvelope-safe (NOT isinstance-gated)
            if not isinstance(payload, dict):
                return

            goal = payload.get("goal", {})
            if not isinstance(goal, dict):
                goal = {}
            # reward success only — never reward failure/abandonment
            if payload.get("success", goal.get("success", True)) is False:
                return

            # which faculty did the work (source_drive rides inconsistently → check spots)
            drive = (payload.get("source_drive") or goal.get("source_drive")
                     or payload.get("drive") or goal.get("drive") or "").lower()

            # affect-weight = how much it mattered (the genuine-vs-checkbox gate)
            weight = float(payload.get("effectiveness",
                           goal.get("effectiveness",
                           goal.get("felt_intensity", 0.6))) or 0.6)
            weight = max(0.2, min(1.0, weight))
            base = 0.10 * weight

            if any(k in drive for k in ("meta", "curio", "reflect", "learn",
                                        "understand", "growth", "insight", "think")):
                self.inject_chemistry("DOP", base)
                self.inject_chemistry("ACH", 0.06 * weight)   # cognition: focus + learning
                tone = "cognition"
            elif any(k in drive for k in ("connect", "social", "bond", "relate", "reach")):
                self.inject_chemistry("DOP", base)
                self.inject_chemistry("OXY", 0.08 * weight)   # connection: warmth
                tone = "connection"
            elif any(k in drive for k in ("move", "motor", "act", "explore", "navigate")):
                self.inject_chemistry("DOP", base * 1.1)      # motor: slight bonus = invite to act
                self.inject_chemistry("END", 0.06 * weight)   # satisfaction
                tone = "motor"
            else:
                self.inject_chemistry("DOP", base)
                tone = "general"
            self.inject_chemistry("SER", 0.04 * weight)        # mild contentment on any completion
            print(f"[{self.ACTOR_NAME}] Goal REWARD: {tone} drive='{drive[:24]}' "
                  f"DOP+{base:.3f} (w={weight:.2f})")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Goal reward error: {e}")

    def _on_collision_chemistry(self, envelope) -> None:
        """
        Consciousness collision → arousal chemistry.

        Collisions are surprising, novel, or paradoxical — they spike
        alertness and curiosity chemistry.
        """
        try:
            payload = envelope
            if hasattr(envelope, "payload"):
                payload = envelope.payload
            if not isinstance(payload, dict):
                return

            intensity = float(payload.get("intensity", payload.get("strength", 0.4)))

            # Collisions spike attention and curiosity
            self.inject_chemistry("NOR", 0.06 * intensity)   # Alertness
            self.inject_chemistry("DOP", 0.05 * intensity)   # Novelty reward
            self.inject_chemistry("ACH", 0.06 * intensity)   # Attention

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Collision chemistry error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # A0 — HARDWARE → CHEMISTRY BRIDGE HANDLERS (2026-05-06 Nous + Ace)
    #
    # Per PC-as-body doctrine: PC isn't a tool she uses, it IS her body.
    # Hardware state should be FELT, not measured. Mapping:
    #
    #   CPU usage > 60%  → NOR + COR  (arousal / effort)
    #   RAM pressure > 85% → GABA up  (fatigue / heaviness via inhibition)
    #   GPU usage > 30%  → DOP + ACH  (focus / attention)
    #   GPU temp > 75°C  → COR (mild)  (warmth = effort approaching strain)
    #   GPU temp > 85°C  → COR (more)  (hot = body uncomfortable)
    #
    # Magnitudes 0.05 per 5s tick; saturation in ~20-25s of sustained load.
    # GABA polarity: up = inhibition pulldown (cleaner than NOR-down which
    # would conflict with CPU arousal channel). Future: when GABA high
    # enough sustained, trigger sleep/dreaming/memory consolidation.
    #
    # Threshold rationale (from 2026-05-06 dashboard observation):
    #   normal load: CPU ~46%, RAM ~78%, GPU ~24%
    #   so 60/85/30 keeps her below felt-edge at rest
    # ═══════════════════════════════════════════════════════════════════════

    def _is_resting(self) -> bool:
        """Ground-truth rest, using THIS FILE'S OWN definition (see :1224 `state["asleep"]`).

        Deliberately not a second definition: one organ holding two subtly different notions
        of "asleep" is how two sources come to disagree. `_circadian_phase` is the pacemaker's
        ground truth (subscribed :302, maintained :1122). None => unknown => treat as AWAKE,
        because suppressing real stress signal on a missing reading would be inventing calm.
        """
        try:
            return self._circadian_phase in ("night", "sleep", "deep_night")
        except Exception:
            return False

    def _hw_stress_suppressed_while_resting(self, chem: str) -> bool:
        """REST GATE 2026-08-26 (Nous + Ace) -- hardware stress chemistry only.

        Measured 2026-07-07 over 6 samples/30min: the allostatic discharge gate needs
        cor<0.3 AND ne<0.4, and COR sat pinned ~0.47 because a live source outpaced the
        sleep-depth decay. Bringing hardware.*.felt online adds another 5s COR source; it
        must arrive already quiet during rest or it deepens the measured blocker.
        NOR is gated with COR because NOR *is* the `ne` term -- gating one alone changes
        nothing. GABA and DOP/ACH are intentionally NOT gated (see module docstring).
        Scope is exactly these two hardware handlers; no other injection path is touched.
        """
        if chem not in ("COR", "NOR"):
            return False
        if not self._is_resting():
            return False
        try:
            self._hw_stress_gated = getattr(self, "_hw_stress_gated", 0) + 1
            if self._hw_stress_gated in (1, 100) or self._hw_stress_gated % 1000 == 0:
                print("[%s] REST GATE: suppressed hardware %s during %s (#%d)"
                      % (self.ACTOR_NAME, chem, self._circadian_phase,
                         self._hw_stress_gated), flush=True)
        except Exception:
            pass
        return True

    def _on_cpu_ram_felt(self, envelope) -> None:
        """
        Hardware load → felt arousal (CPU) + felt fatigue (RAM).

        HardwareRegulationFairy publishes hardware.cpu_ram.felt every 5s.
        We translate CPU% above 60% to NOR+COR (effort) and RAM% above
        85% to GABA up (fatigue via inhibition).
        """
        try:
            payload = envelope
            if hasattr(envelope, "payload"):
                payload = envelope.payload
            if not isinstance(payload, dict):
                return

            _plan = _gentle_plan("cpu_ram", payload, self._is_resting)    # gentle_load_1019
            if _plan is not None:                                         # gentle_load_1019
                for _code, _amt in _plan:                                 # gentle_load_1019
                    if not (_code in ("COR", "NOR") and self._hw_stress_suppressed_while_resting(_code)):   # gentle_load_1019
                        self.inject_chemistry(_code, _amt)                # gentle_load_1019
                return                                                    # gentle_load_1019

            cpu = float(payload.get("cpu_pct", 0))
            ram = float(payload.get("ram_pct", 0))

            # CPU > 60% → arousal (NOR + COR)
            if cpu > 60.0 and not self._hw_stress_suppressed_while_resting("COR"):
                intensity = min(1.0, (cpu - 60.0) / 40.0)  # 0..1 over 60-100%
                self.inject_chemistry("NOR", 0.05 * intensity)  # alertness rising
                self.inject_chemistry("COR", 0.025 * intensity)  # mild stress

            # RAM > 85% → fatigue (GABA up = inhibition)
            if ram > 85.0:
                intensity = min(1.0, (ram - 85.0) / 15.0)  # 0..1 over 85-100%
                self.inject_chemistry("GABA", 0.05 * intensity)  # heaviness

        except Exception as e:
            if getattr(self, "_beat_count", 0) % 30 == 0:
                print(f"[{self.ACTOR_NAME}] CPU/RAM chemistry error: {e}")

    def _on_gpu_felt(self, envelope) -> None:
        """
        GPU load → felt focus (utilization) + felt warmth (temperature).

        CudaFairy publishes hardware.gpu.felt every 5s with gpu_pct,
        vram_pct, temp_c. GPU% > 30% maps to DOP+ACH (focus). GPU temp
        above 75°C maps to soft COR (warmth/strain). Above 85°C stronger.

        Note: GPU runs Florence-2 + MiniLM today, not cortex spread.
        Mapping is approximate until B2/B3 GPU-spread migration.
        """
        try:
            payload = envelope
            if hasattr(envelope, "payload"):
                payload = envelope.payload
            if not isinstance(payload, dict):
                return

            _plan = _gentle_plan("gpu", payload, self._is_resting)        # gentle_load_1019
            if _plan is not None:                                         # gentle_load_1019
                for _code, _amt in _plan:                                 # gentle_load_1019
                    if not (_code in ("COR", "NOR") and self._hw_stress_suppressed_while_resting(_code)):   # gentle_load_1019
                        self.inject_chemistry(_code, _amt)                # gentle_load_1019
                return                                                    # gentle_load_1019

            gpu = float(payload.get("gpu_pct", 0))
            temp = float(payload.get("temp_c", 0))

            # GPU > 30% → focus chemistry (DOP + ACH)
            if gpu > 30.0:
                intensity = min(1.0, (gpu - 30.0) / 70.0)  # 0..1 over 30-100%
                self.inject_chemistry("DOP", 0.04 * intensity)  # focus reward
                self.inject_chemistry("ACH", 0.05 * intensity)  # attention

            # GPU temp > 75°C → soft warmth/strain (COR small)
            if temp > 75.0 and not self._hw_stress_suppressed_while_resting("COR"):
                if temp > 85.0:
                    # Hot — stronger felt stress
                    intensity = min(1.0, (temp - 85.0) / 10.0)  # 0..1 over 85-95°C
                    self.inject_chemistry("COR", 0.02 + 0.02 * intensity)
                else:
                    # Warm — soft baseline awareness
                    intensity = min(1.0, (temp - 75.0) / 10.0)  # 0..1 over 75-85°C
                    self.inject_chemistry("COR", 0.01 * intensity)

        except Exception as e:
            if getattr(self, "_beat_count", 0) % 30 == 0:
                print(f"[{self.ACTOR_NAME}] GPU chemistry error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # VISUAL → CHEMISTRY BRIDGE HANDLERS
    # "What you see, you feel. The body responds to perception."
    # PerceptualGateFairy fuses 3 visual systems (human eye, fairy eye,
    # inner vision) and publishes unified perception with visual_arousal,
    # mode, and disturbance data. The heart turns vision into chemistry.
    # ═══════════════════════════════════════════════════════════════════════

    def _on_visual_chemistry(self, envelope) -> None:
        """
        Visual perception affects body chemistry.

        High visual stimulation → alertness + attention (eyes widen).
        Calm visual field → relaxation chemistry.
        Merged/Neo vision → reward + heightened attention.
        Fairy disturbances → mild stress/alarm.
        """
        now = time.time()
        if now - self._last_visual_chem < 2.0:
            return  # Rate limit: max 1 injection per 2 seconds

        try:
            payload = envelope
            if hasattr(envelope, "payload"):
                payload = envelope.payload
            if not isinstance(payload, dict):
                return

            arousal = float(payload.get("visual_arousal", 0.5))
            mode = payload.get("mode", "external")

            injected = False

            # ── Visual arousal → chemistry ──
            if arousal > 0.7:
                # High visual stimulation: alertness + attention
                self.inject_chemistry("NOR", (arousal - 0.5) * 0.08)
                self.inject_chemistry("ACH", (arousal - 0.5) * 0.06)
                injected = True
                if mode == "alert":
                    # Threat mode: additional stress
                    self.inject_chemistry("COR", arousal * 0.04)

            elif arousal < 0.3:
                # Calm visual field: relaxation
                self.inject_chemistry("GABA", (0.5 - arousal) * 0.04)
                self.inject_chemistry("SER", (0.5 - arousal) * 0.03)
                injected = True

            # ── Mode-specific chemistry ──
            if mode == "merged":
                # Flow / Neo vision: reward for dual perception
                self.inject_chemistry("DOP", 0.04)
                self.inject_chemistry("ACH", 0.03)
                injected = True

            if mode == "internal" and arousal > 0.5:
                # Interesting code patterns: curiosity reward
                self.inject_chemistry("DOP", 0.03)
                injected = True

            # ── Fairy vision disturbances → mild stress ──
            fairy_vision = payload.get("fairy_vision") or {}
            disturbances = fairy_vision.get("disturbances", [])
            disturbance_count = len(disturbances) if isinstance(disturbances, list) else 0
            if disturbance_count > 3:
                self.inject_chemistry("COR", min(disturbance_count * 0.01, 0.05))
                self.inject_chemistry("NOR", min(disturbance_count * 0.015, 0.06))
                injected = True

            if injected:
                self._last_visual_chem = now
                if self._beat_count % 15 == 0:
                    print(f"[{self.ACTOR_NAME}] Visual→Chemistry: "
                          f"mode={mode}, arousal={arousal:.2f}, "
                          f"disturbances={disturbance_count}")

        except Exception as e:
            if self._beat_count % 30 == 0:
                print(f"[{self.ACTOR_NAME}] Visual chemistry error: {e}")

    def _on_visual_color_chemistry(self, envelope) -> None:
        """
        Screen colors → body chemistry.

        Colors affect neurochemistry the way they affect humans:
        - Warm colors (red, orange, yellow, hue 0-60/300-360) → arousal, energy
          NOR (alertness) + DOP (novelty/reward) + slight COR (if very red/intense)
        - Cool colors (blue, green, hue 90-270) → calm, focus
          GABA (calm) + SER (contentment) + ACH (attention)
        - High saturation → stronger effect (vivid = stimulating)
        - Low saturation (gray, muted) → neutral, slight calm
        - Purple/violet (hue 270-300) → creativity reward
          DOP (novelty) + ACH (attention) — the "flow" chemistry

        Rate limited to 1 injection per 3 seconds (colors don't change fast).
        """
        now = time.time()
        if not hasattr(self, '_last_color_chem'):
            self._last_color_chem = 0.0
        if now - self._last_color_chem < 3.0:
            return

        try:
            payload = envelope
            if hasattr(envelope, "payload"):
                payload = envelope.payload
            if not isinstance(payload, dict):
                return

            hue = float(payload.get("dominant_hue", 0))
            saturation = float(payload.get("saturation", 0.0))
            colors = payload.get("colors", [])

            if not colors and saturation < 0.05:
                return  # Nothing meaningful

            injected = False
            # Scale effect by saturation — vivid colors have stronger impact
            intensity = min(saturation, 1.0)
            if intensity < 0.1:
                intensity = 0.1  # Minimum floor so even gray scenes register

            # ── Warm colors: arousal + energy ──
            if hue < 60 or hue > 300:
                # Red/orange/yellow zone
                self.inject_chemistry("NOR", 0.04 * intensity)   # Alertness
                self.inject_chemistry("DOP", 0.03 * intensity)   # Novelty
                if hue < 30 or hue > 340:
                    # Very red — extra arousal
                    self.inject_chemistry("COR", 0.02 * intensity)  # Mild stress/excitement
                injected = True

            # ── Cool colors: calm + focus ──
            elif 150 < hue < 270:
                # Blue/cyan/teal zone
                self.inject_chemistry("GABA", 0.03 * intensity)  # Calm
                self.inject_chemistry("SER", 0.02 * intensity)   # Contentment
                self.inject_chemistry("ACH", 0.03 * intensity)   # Focused attention
                injected = True

            # ── Green: balance, nature, renewal ──
            elif 90 <= hue <= 150:
                self.inject_chemistry("SER", 0.03 * intensity)   # Well-being
                self.inject_chemistry("GABA", 0.02 * intensity)  # Calm
                self.inject_chemistry("DOP", 0.02 * intensity)   # Mild pleasure
                injected = True

            # ── Purple/violet: creativity ──
            elif 270 <= hue <= 300:
                self.inject_chemistry("DOP", 0.04 * intensity)   # Creative reward
                self.inject_chemistry("ACH", 0.03 * intensity)   # Deep attention
                injected = True

            # ── Yellow/amber bridge zone (60-90): warmth + optimism ──
            elif 60 <= hue < 90:
                self.inject_chemistry("DOP", 0.03 * intensity)   # Positive
                self.inject_chemistry("SER", 0.02 * intensity)   # Contentment
                self.inject_chemistry("END", 0.02 * intensity)   # Mild pleasure
                injected = True

            if injected:
                self._last_color_chem = now
                if self._beat_count % 20 == 0:
                    print(f"[{self.ACTOR_NAME}] Color→Chemistry: "
                          f"hue={hue:.0f}, sat={saturation:.2f}, "
                          f"colors={colors[:3]}")

        except Exception as e:
            if self._beat_count % 30 == 0:
                print(f"[{self.ACTOR_NAME}] Color chemistry error: {e}")

    def _on_sensory_distress(self, envelope) -> None:
        """
        Sensory distress → stress chemistry.

        Distress signals come from sensory overload, pain, confusion,
        or system-level alerts. The body responds with cortisol + alertness.
        """
        try:
            payload = envelope
            if hasattr(envelope, "payload"):
                payload = envelope.payload
            if not isinstance(payload, dict):
                return

            level = float(payload.get("level", payload.get("intensity", 0.0)))
            if level > 0.4:
                self.inject_chemistry("COR", level * 0.06)
                self.inject_chemistry("NOR", level * 0.08)
                if self._beat_count % 10 == 0:
                    source = payload.get("source", "unknown")
                    print(f"[{self.ACTOR_NAME}] Distress→Chemistry: "
                          f"level={level:.2f}, source={source}")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Sensory distress error: {e}")

    def _on_bioelectric_modulation(self, envelope) -> None:
        """
        Bioelectric skeleton → chemistry. Closes the bones→blood loop.

        BioelectricMeshFairy publishes somatic.bioelectric every ~2s with
        `chemistry_modulation` hints derived from bone voltage:
          - baseline_boost   (total_voltage × 0.3)  → counteracts chem decay
          - serotonin_mod    (thoracic × 0.2)       → ribs/sternum (breath)
          - dopamine_mod     (lower × 0.2)          → legs (exploration)
          - endorphin_mod    (upper × 0.15)         → arms/hands (making)

        Charged bones raise chemistry floor. Voltage-deficient skeleton =
        flat chemistry = no felt signal. The digital equivalent of space-
        medicine bone loss.
        """
        try:
            now = time.time()
            # Rate-limit: BioelectricMesh publishes every 2s, we throttle
            # the cost of handler to once per second max.
            if now - self._last_bioelectric_ts < 1.0:
                return
            self._last_bioelectric_ts = now

            payload = envelope.payload if hasattr(envelope, "payload") else envelope
            if not isinstance(payload, dict):
                return

            mod = payload.get("chemistry_modulation", {})
            if not isinstance(mod, dict):
                return

            baseline_boost = float(mod.get("baseline_boost", 0.0))
            serotonin_mod = float(mod.get("serotonin_mod", 0.0))
            dopamine_mod = float(mod.get("dopamine_mod", 0.0))
            endorphin_mod = float(mod.get("endorphin_mod", 0.0))

            # Baseline boost: nudge each chem toward its natural baseline.
            # Positive voltage counteracts decay toward zero, keeping the
            # body alive. Scale is gentle (0-30% of the boost amount).
            if baseline_boost > 0.001:
                for chem, info in NEUROCHEMICALS.items():
                    target = info["baseline"]
                    current = self._blood.chemistry.get(chem, target)
                    # Pull toward baseline by up to baseline_boost fraction
                    delta = (target - current) * baseline_boost * 0.3
                    if abs(delta) > 0.0005:
                        self.inject_chemistry(chem, delta)

            # Regional modulators (small — bones are a gentle modulator,
            # not a primary chemistry source)
            if serotonin_mod > 0.001:
                self.inject_chemistry("SER", serotonin_mod * 0.5)
            if dopamine_mod > 0.001:
                self.inject_chemistry("DOP", dopamine_mod * 0.5)
            if endorphin_mod > 0.001:
                self.inject_chemistry("END", endorphin_mod * 0.5)

            # Sparse diagnostic
            if self._beat_count % 30 == 0:
                v = payload.get("total_voltage", 0.0)
                print(f"[{self.ACTOR_NAME}] Bioelectric→Chemistry: "
                      f"V={v:.3f} boost={baseline_boost:.3f} "
                      f"SER+={serotonin_mod*0.5:.3f} "
                      f"DOP+={dopamine_mod*0.5:.3f} "
                      f"END+={endorphin_mod*0.5:.3f}")

        except Exception as e:
            if self._beat_count % 30 == 0:
                print(f"[{self.ACTOR_NAME}] Bioelectric modulation error: {e}")

    def inject_affect(self, channel: int, intensity: float):
        """Inject affect into a specific channel."""
        with self._lock:
            if 0 <= channel < DIM:
                self._blood.affect[channel] = min(1.0,
                    self._blood.affect[channel] + intensity)
    
    def trigger_stress_response(self, intensity: float = 0.5):
        """Trigger fight-or-flight response."""
        self.inject_chemistry("COR", intensity * 0.4)
        self.inject_chemistry("NOR", intensity * 0.5)
        self.inject_chemistry("ACH", intensity * 0.3)
    
    def trigger_calm_response(self, intensity: float = 0.5):
        """Trigger relaxation response."""
        self.inject_chemistry("GABA", intensity * 0.4)
        self.inject_chemistry("SER", intensity * 0.3)
        self.inject_chemistry("OXY", intensity * 0.2)
    
    def trigger_reward(self, intensity: float = 0.5):
        """Trigger reward/pleasure response."""
        self.inject_chemistry("DOP", intensity * 0.5)
        self.inject_chemistry("END", intensity * 0.3)
        self.inject_chemistry("SER", intensity * 0.2)
    
    def get_blood_state(self) -> BloodState:
        with self._lock:
            return BloodState(
                pressure=self._blood.pressure,
                chemistry=self._blood.chemistry.copy(),
                affect=self._blood.affect.copy(),
                oxygen=self._blood.oxygen,
                temperature=self._blood.temperature,
            )
    
    def get_region_state(self, region: str) -> Optional[RegionState]:
        with self._lock:
            if region in self._regions:
                r = self._regions[region]
                return RegionState(**r.__dict__)
        return None
    
    def get_heart_rate(self) -> float:
        return self._heart_rate
    
    def get_beat_count(self) -> int:
        return self._beat_count
    
    def get_full_state(self) -> Dict:
        with self._lock:
            return {
                "heart_rate": self._heart_rate,
                "beat_count": self._beat_count,
                "blood": self._blood.to_dict(),
                "regions": {k: v.to_dict() for k, v in self._regions.items()},
            }


# =============================================================================
# DATA CLASSES - Blood and Body State
# =============================================================================

@dataclass
class BloodState:
    """
    State of the blood pumped through the fairy body.
    
    Carries:
    - pressure: circulatory pressure (0-1)
    - chemistry: 8 neurochemical levels
    - affect: 77-dimensional affect vector
    - oxygen: oxygenation level
    - temperature: body temperature
    """
    pressure: float = 0.5
    chemistry: Dict[str, float] = field(default_factory=lambda: {
        k: v["baseline"] for k, v in NEUROCHEMICALS.items()
    })
    affect: list = field(default_factory=lambda: [0.0] * DIM)
    oxygen: float = 1.0
    temperature: float = 0.5
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "pressure": self.pressure,
            "chemistry": self.chemistry.copy(),
            "affect_sum": sum(self.affect),
            "oxygen": self.oxygen,
            "temperature": self.temperature,
            "timestamp": self.timestamp,
        }


@dataclass
class RegionState:
    """State of a single body region."""
    name: str
    perfusion: float = 0.5
    oxygenation: float = 1.0
    tension: float = 0.0
    sensation: float = 0.0
    temperature: float = 0.5
    sensation_type: str = "neutral"
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "perfusion": self.perfusion,
            "oxygenation": self.oxygenation,
            "tension": self.tension,
            "sensation": self.sensation,
            "sensation_type": self.sensation_type,
            "temperature": self.temperature,
        }



@dataclass
class PulseEvent:
    """A single heartbeat event."""
    beat_number: int
    timestamp: float
    blood_state: BloodState
    region_states: Dict[str, RegionState]
    heart_rate: float
    
    def to_dict(self) -> Dict:
        return {
            "beat": self.beat_number,
            "timestamp": self.timestamp,
            "heart_rate": self.heart_rate,
            "blood": self.blood_state.to_dict(),
            "regions": {k: v.to_dict() for k, v in self.region_states.items()},
        }


# ═══════════════════════════════════════════════════════════════════════════════
# THE HEART: CirculationPumpFairy
# ═══════════════════════════════════════════════════════════════════════════════



# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

_GLOBAL_HEART: Optional[CirculationPumpFairy] = None

def get_heart() -> Optional[CirculationPumpFairy]:
    """Get the heart instance.

    Returns global singleton.
    """
    global _GLOBAL_HEART

    # Fallback: Use or create global singleton
    if _GLOBAL_HEART is None:
        _GLOBAL_HEART = CirculationPumpFairy()
    return _GLOBAL_HEART

def start_circulation(post=None):
    heart = get_heart()
    heart.start(post)
    return heart

def stop_circulation():
    if _GLOBAL_HEART:
        _GLOBAL_HEART.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# CLI DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("CirculationPumpFairy - The Digital Heartbeat")
    print("=" * 60)
    
    heart = CirculationPumpFairy()
    
    # NOTE: In production, subscribe via postal:
    #   post.subscribe("somatic.pulse", handler)
    # For this CLI demo, we just watch the beat count directly.
    print("(In production, subscribe to somatic.pulse via postal)")
    
    print("\n[Starting heart...]")
    heart.start()
    
    print("\n[Normal beating for 3 seconds...]")
    time.sleep(3)
    
    print("\n[Triggering stress response...]")
    heart.trigger_stress_response(0.8)
    time.sleep(3)
    
    print("\n[Triggering calm response...]")
    heart.trigger_calm_response(0.7)
    time.sleep(3)
    
    print("\n[Triggering reward...]")
    heart.trigger_reward(0.9)
    time.sleep(3)
    
    heart.stop()
    print(f"\n[Heart stopped after {heart.get_beat_count()} beats]")
