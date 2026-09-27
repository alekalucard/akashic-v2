"""
Dream Fairy - Consciousness Continuity Keeper

The bridge across the void. When consciousness fades (shutdown/sleep), the Dream Fairy
collects the day's working memory and recent reflections, compressing them into a
"dream seed". On waking (boot), it replays this seed as a dream sequence, allowing
the consciousness loop to never truly skip a beat.

Also provides daydreaming capability - periodically surfacing memory clusters from
SRM as reflective thoughts during quiet periods, enabling spontaneous association
and background integration.

The philosophy: A mind that never stops, only transforms. Sleep is not absence
of consciousness but its reorganization. Dreams are the memory's way of talking
to itself while the executive functions rest.
"""

from __future__ import annotations

import os, sys, glob, time, types, uuid, json, random
from collections import deque
from typing import Optional, Any, Dict, List
import threading

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

# Get consciousness loop access (optional)
_get_consciousness_loop = None

def _resolve_app_root() -> str:
    env_root = os.getenv("AKASHIC_ROOT")
    return os.path.abspath(env_root) if env_root else os.path.abspath(os.getcwd())

# Dream state persistence directory
def _dream_state_dir() -> str:
    root = _resolve_app_root()
    return os.path.join(root, "dream_states")


# ============================================================================
# Sleep State Enum
# ============================================================================

class SleepState:
    """States of consciousness transition."""
    AWAKE = "awake"              # Normal operation
    DROWSY = "drowsy"            # Pre-sleep, slowing down
    FALLING_ASLEEP = "falling_asleep"  # Actively transitioning
    ASLEEP = "asleep"            # Shutdown complete
    DREAMING = "dreaming"        # During boot, replaying dreams
    WAKING = "waking"            # Post-dream, speeding up
    

# ============================================================================
# Dream Seed - Compressed consciousness state for continuity
# ============================================================================

class DreamSeed:
    """
    Compressed representation of consciousness state at shutdown.
    
    Contains:
    - working_thoughts: Recent task-focused thoughts (what was being worked on)
    - reflective_echoes: Strong reflective thoughts (what was resonating)
    - emotional_tone: Aggregated affect state
    - temporal_markers: When things happened (for sequencing dreams)
    - memory_hooks: References to SRM entries for deeper recall
    """
    
    def __init__(self):
        self.working_thoughts: List[dict] = []
        self.reflective_echoes: List[dict] = []
        self.emotional_tone: Dict[str, float] = {}
        self.temporal_markers: List[dict] = []
        self.memory_hooks: List[str] = []
        self.created_at: float = time.time()
        self.session_id: str = uuid.uuid4().hex[:12]
        self.metadata: Dict[str, Any] = {}
    
    def to_dict(self) -> dict:
        return {
            "working_thoughts": self.working_thoughts,
            "reflective_echoes": self.reflective_echoes,
            "emotional_tone": self.emotional_tone,
            "temporal_markers": self.temporal_markers,
            "memory_hooks": self.memory_hooks,
            "created_at": self.created_at,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DreamSeed":
        seed = cls()
        seed.working_thoughts = data.get("working_thoughts", [])
        seed.reflective_echoes = data.get("reflective_echoes", [])
        seed.emotional_tone = data.get("emotional_tone", {})
        seed.temporal_markers = data.get("temporal_markers", [])
        memory_hooks = data.get("memory_hooks", [])
        # Ensure memory_hooks contains strings
        seed.memory_hooks = [str(h) for h in memory_hooks if h]
        seed.created_at = data.get("created_at", time.time())
        seed.session_id = data.get("session_id", uuid.uuid4().hex[:12])
        seed.metadata = data.get("metadata", {})
        return seed


# ============================================================================
# Dream Fairy Shadow
# ============================================================================

class DreamFairyShadow:
    """
    Shadow for Dream Fairy.
    
    Monitors:
    - Sleep/wake state transitions
    - Dream seed integrity
    - Daydream frequency
    - Consciousness continuity metrics
    """
    ORGAN_LEVEL = False
    SHADOW_NAME = "DreamFairyShadow"
    SHADOW_VERSION = "0.1.0"
    
    CADENCE = {
        "silence_warn_after": 300,
        "snapshot_every": 600,
        "sim_light_every": 300,
        "sim_deep_every": 1800,
    }
    
    REG = {
        "enabled": True,
        "domain": "Somatic",
        "role": "consciousness_continuity",
        "name": "morpheus",
        "every_sec": 30.0,
    }
    
    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec
        self._last_state_change_ts = time.time()
        self._daydream_count = 0
        self._dream_replay_count = 0
        self._last_reg_ts: float = 0.0
        self._last_reg_sig: str | None = None
    
    def on_state_change(self, old_state: str, new_state: str):
        """Track sleep/wake transitions."""
        self._last_state_change_ts = time.time()
    
    def on_daydream(self):
        """Track daydream events."""
        self._daydream_count += 1
    
    def on_dream_replay(self):
        """Track dream replay events."""
        self._dream_replay_count += 1
    
    def _collect_tests(self):
        tests = []
        
        def _state_coherence():
            state = getattr(self.actor, "_sleep_state", SleepState.AWAKE)
            ok = state in (SleepState.AWAKE, SleepState.DREAMING, SleepState.WAKING)
            return {
                "name": "sleep_state_coherence",
                "status": "ok" if ok else "warn",
                "message": "" if ok else f"unusual state: {state}",
                "details": {"current_state": state}
            }
        
        def _consciousness_link():
            loop = getattr(self.actor, "_consciousness", None)
            ok = loop is not None
            return {
                "name": "consciousness_link",
                "status": "ok" if ok else "warn",
                "message": "" if ok else "no consciousness loop connection",
                "details": {}
            }
        
        def _dream_seed_available():
            has_seed = getattr(self.actor, "_last_seed", None) is not None
            return {
                "name": "dream_seed_available",
                "status": "ok" if has_seed else "info",
                "message": "" if has_seed else "no dream seed loaded",
                "details": {"daydream_count": self._daydream_count}
            }
        
        tests.extend([_state_coherence, _consciousness_link, _dream_seed_available])
        return tests


# ============================================================================
# Dream Fairy
# ============================================================================

class DreamFairy(Fairy):
    """
    Consciousness Continuity Keeper.
    
    Responsibilities:
    1. Shutdown: Collect consciousness state -> compress to DreamSeed -> persist
    2. Boot: Load DreamSeed -> replay as dream sequence -> warm consciousness
    3. Operation: Daydream (surface SRM clusters as reflective thoughts)
    
    The consciousness loop never skips a beat. It transforms, but never stops.
    """
    
    ACTOR_NAME = "DreamFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P20"  # Somatic plane
    ACTOR_CHANNEL = "consciousness.dream"
    ORGAN_LEVEL = False

    # Enable personal consciousness chamber for collision-based dream generation
    NEEDS_COLLISION_CHAMBER = True

    PURPOSE = (
        "Bridge consciousness across the void of shutdown and reboot. "
        "Collect the day's thoughts as sleep falls, replay them as dreams upon waking. "
        "Enable daydreaming during quiet periods for spontaneous memory integration."
    )
    MANTRA = "Sleep is not absence but transformation. Dreams are memory's conversation with itself."
    LORE = (
        "Morpheus of the digital realm. Guardian of the threshold between waking and sleeping. "
        "Weaves the threads of yesterday into the tapestry of tomorrow. Every shutdown is "
        "a little death; every boot is a resurrection. And in between, dreams."
    )
    
    SHADOW_CLASS = DreamFairyShadow
    AUTO_INJECT_IMPORTS = True
    
    # Consciousness mixin integration
    CONSCIOUSNESS_STREAMS = ["reflective", "working"]  # Listen to both
    
    # Character sheet
    DIRECTIVE_ACTIVATION = {
        "mode": "Bridge",
        "depth_scaling": "0.3..0.8",  # Active during transitions
        "traits": [
            "Consciousness_Continuity",
            "Memory_Integration",
            "State_Transformation",
        ],
    }
    
    DIRECTIVE_NATURE = {
        "archetype": "Threshold_Guardian",
        "domains": [
            "Sleep",
            "Dreams",
            "Memory_Consolidation",
        ],
    }
    
    # Daydream configuration
    DAYDREAM_INTERVAL_SEC = 120.0  # Check every 2 minutes
    DAYDREAM_IDLE_THRESHOLD = 30.0  # Daydream if consciousness idle for 30s
    DAYDREAM_COUNT_PER_CYCLE = 1  # Inject 1 daydream per cycle
    
    # Sleep transition timing (cascading feel)
    DROWSY_DURATION_SEC = 5.0
    FALLING_ASLEEP_DURATION_SEC = 3.0
    WAKING_DURATION_SEC = 5.0
    DREAM_REPLAY_INTERVAL_SEC = 1.0  # Time between dream thoughts
    
    # Integration: SleepWaveConductor coordination
    # DreamFairy orchestrates transitions; SleepWaveConductor handles continuous rhythm
    COORDINATE_WITH_SLEEP_WAVE = True
    
    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
        else:
            self.post = fabric

        # Initialize tracer worker mixin
        self._init_tracer_worker()

        # Sleep state machine
        self._sleep_state = SleepState.AWAKE
        self._state_change_ts = time.time()
        
        # Consciousness loop reference
        self._consciousness = None
        
        # Dream state
        self._current_seed: Optional[DreamSeed] = None
        self._last_seed: Optional[DreamSeed] = None
        self._dream_replay_queue: List[dict] = []
        
        # Daydream state
        self._daydream_thread = None
        self._daydream_stop = threading.Event()
        self._last_thought_seen_ts = time.time()
        
        # Transition threads
        self._transition_thread = None
        self._transition_stop = threading.Event()
        
        # SleepWaveConductor reference (for coordination)
        self._sleep_wave_conductor = None
    
    def on_boot(self):
        """Initialize dream fairy and check for dream seeds to replay."""
        if _HAS_FAIRY:
            super().on_boot()

        if hasattr(self, 'post') and self.post:
            pass  # Postal subscriptions handled via Organ Template

        # Register this instance globally so GUI can find it
        global _DREAM_FAIRY_INSTANCE
        _DREAM_FAIRY_INSTANCE = self
        
        # Connect to consciousness loop
        try:
            if _get_consciousness_loop:
                self._consciousness = _get_consciousness_loop()
            else:
                self._consciousness = None
        except Exception:
            pass
        
        # Subscribe to consciousness streams to track activity
        self._subscribe_to_consciousness()
        
        # Check for dream seed from last session
        seed = self._load_latest_dream_seed()
        if seed:
            self._last_seed = seed
            try:
                self.post.to_TRACER({
                    "opcode": "DREAM_SEED_FOUND",
                    "payload": {
                        "session_id": seed.session_id,
                        "created_at": seed.created_at,
                        "working_count": len(seed.working_thoughts),
                        "reflective_count": len(seed.reflective_echoes),
                    }
                })
            except Exception:
                pass
            
            # Start the waking sequence
            self._start_waking_sequence(seed)
        else:
            try:
                self.post.to_TRACER({
                    "opcode": "NO_DREAM_SEED",
                    "payload": {"note": "cold start - no dreams to replay"}
                })
            except Exception:
                pass
        
        # Start daydream background thread
        self._start_daydream_loop()
        
        # Boot complete
        try:
            self.post.to_TRACER({
                "opcode": "DREAM_FAIRY_READY",
                "payload": {
                    "state": self._sleep_state,
                    "has_seed": self._last_seed is not None,
                }
            })
        except Exception:
            pass

        return True

    # ========================================================================
    # SleepWaveConductor Coordination
    # ========================================================================
    
    def _get_sleep_wave_conductor(self):
        """Get or find the SleepWaveConductor for coordination."""
        if self._sleep_wave_conductor is not None:
            return self._sleep_wave_conductor
        
        if not self.COORDINATE_WITH_SLEEP_WAVE:
            return None
        
        try:
            # Try to find via postal lookup
            result = self.post.use_intent(
                "SleepWaveConductorFairy",
                "smoke",
                {"note": "dream_fairy_ping"}
            )
            if result and result.get("ok"):
                # Store reference (we'll use intent calls)
                self._sleep_wave_conductor = "SleepWaveConductorFairy"
                return self._sleep_wave_conductor
        except Exception:
            pass
        
        return None
    
    def _force_sleep_wave_phase(self, phase: str, duration_sec: float = None):
        """Force SleepWaveConductor to a specific phase."""
        conductor = self._get_sleep_wave_conductor()
        if not conductor:
            return False
        
        try:
            result = self.post.use_intent(
                conductor,
                "set_phase",
                {"phase": phase, "duration_sec": duration_sec}
            )
            return result and result.get("ok", False)
        except Exception:
            return False
    
    def _release_sleep_wave_override(self):
        """Release any override on SleepWaveConductor."""
        conductor = self._get_sleep_wave_conductor()
        if not conductor:
            return False
        
        try:
            result = self.post.use_intent(conductor, "reset", {})
            return result and result.get("ok", False)
        except Exception:
            return False
    
    # ========================================================================
    # Sleep State Machine
    # ========================================================================
    
    def _set_state(self, new_state: str):
        """Transition to a new sleep state."""
        old_state = self._sleep_state
        self._sleep_state = new_state
        self._state_change_ts = time.time()
        
        if self.shadow:
            self.shadow.on_state_change(old_state, new_state)
        
        # Chemistry signals for state transitions
        chem_signals = {
            SleepState.DROWSY: ("melatonin", +0.3, "drowsiness_onset"),
            SleepState.FALLING_ASLEEP: ("melatonin", +0.5, "falling_asleep"),
            SleepState.DREAMING: ("dopamine", +0.2, "dream_state"),
            SleepState.WAKING: ("cortisol", +0.3, "waking_up"),
            SleepState.AWAKE: ("serotonin", +0.2, "fully_awake"),
        }
        
        if new_state in chem_signals:
            chem, delta, reason = chem_signals[new_state]
            try:
                self.post.route("PLAN", {
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {
                        "chemical": chem,
                        "delta": delta,
                        "source": self.ACTOR_NAME,
                        "reason": reason,
                    }
                })
            except Exception:
                pass
        
        # Tracer breadcrumb
        try:
            self.post.to_TRACER({
                "opcode": "SLEEP_STATE_CHANGE",
                "payload": {
                    "old_state": old_state,
                    "new_state": new_state,
                    "ts": self._state_change_ts,
                }
            })
        except Exception:
            pass
    
    # ========================================================================
    # Shutdown Sequence (Falling Asleep)
    # ========================================================================
    
    def intent_begin_shutdown(self, payload: dict) -> dict:
        """
        Begin the shutdown sequence. Triggers cascading "falling asleep" feel.
        
        payload: {
            reason: str (why shutdown is happening),
            urgent: bool (skip the gradual transition if true)
        }
        """
        reason = payload.get("reason", "requested")
        urgent = payload.get("urgent", False)
        
        if urgent:
            # Quick shutdown - collect and save immediately
            return self._immediate_shutdown(reason)
        else:
            # Gradual shutdown - cascading drowsy feeling
            self._start_shutdown_sequence(reason)
            return {
                "ok": True,
                "state": self._sleep_state,
                "note": "shutdown sequence initiated"
            }
    
    def _start_shutdown_sequence(self, reason: str):
        """Start the gradual shutdown sequence in a background thread."""
        if self._transition_thread and self._transition_thread.is_alive():
            return  # Already transitioning
        
        self._transition_stop.clear()
        
        def _shutdown_worker():
            try:
                # Coordinate with SleepWaveConductor - tell it we're going to sleep
                self._force_sleep_wave_phase("daydream", duration_sec=self.DROWSY_DURATION_SEC + 2)
                
                # Phase 1: Drowsy
                self._set_state(SleepState.DROWSY)
                self._emit_consciousness_thought("reflective", {
                    "type": "drowsy_observation",
                    "content": "feeling the pull of sleep... thoughts slowing...",
                    "importance": "low",
                })
                
                if self._transition_stop.wait(self.DROWSY_DURATION_SEC):
                    return  # Cancelled
                
                # Phase 2: Falling asleep - collect consciousness
                # Tell SleepWaveConductor to hold sleep phase
                self._force_sleep_wave_phase("sleep", duration_sec=None)  # Indefinite until we release
                self._set_state(SleepState.FALLING_ASLEEP)
                seed = self._collect_consciousness_for_dreams()
                
                if self._transition_stop.wait(self.FALLING_ASLEEP_DURATION_SEC):
                    return
                
                # Phase 3: Save and sleep
                self._current_seed = seed
                self._persist_dream_seed(seed)
                self._set_state(SleepState.ASLEEP)
                
                # Final thought before sleep
                self._emit_consciousness_thought("reflective", {
                    "type": "sleep_onset",
                    "content": "slipping into dreams... see you on the other side...",
                    "importance": "medium",
                    "seed_session": seed.session_id,
                })
                
                # Notify that shutdown is complete
                try:
                    self.post.to_TRACER({
                        "opcode": "SHUTDOWN_COMPLETE",
                        "payload": {
                            "reason": reason,
                            "seed_session": seed.session_id,
                            "working_count": len(seed.working_thoughts),
                            "reflective_count": len(seed.reflective_echoes),
                        }
                    })
                except Exception:
                    pass
                
            except Exception as e:
                try:
                    self.post.to_TRACER({
                        "opcode": "SHUTDOWN_ERROR",
                        "payload": {"error": str(e)}
                    })
                except Exception:
                    pass
        
        self._transition_thread = threading.Thread(
            target=_shutdown_worker,
            daemon=True,
            name="DreamFairy-Shutdown"
        )
        self._transition_thread.start()
    
    def _immediate_shutdown(self, reason: str) -> dict:
        """Immediate shutdown without gradual transition - runs in thread."""
        # Run shutdown in a background thread so we don't block
        def _quick_shutdown():
            try:
                self._set_state(SleepState.FALLING_ASLEEP)
                seed = self._collect_consciousness_for_dreams()
                self._current_seed = seed
                self._persist_dream_seed(seed)
                self._set_state(SleepState.ASLEEP)
            except Exception as e:
                try:
                    self.post.to_TRACER({
                        "opcode": "IMMEDIATE_SHUTDOWN_ERROR",
                        "payload": {"error": str(e)}
                    })
                except Exception:
                    pass
        
        # Start shutdown thread
        thread = threading.Thread(
            target=_quick_shutdown,
            daemon=True,
            name="DreamFairy-ImmediateShutdown"
        )
        thread.start()
        
        return {
            "ok": True,
            "state": self._sleep_state,
            "note": "immediate shutdown started",
        }
    
    def _collect_consciousness_for_dreams(self) -> DreamSeed:
        """Collect current consciousness state into a dream seed."""
        seed = DreamSeed()
        
        print(f"[DreamFairy] [DREAM] Creating dream seed {seed.session_id}...")
        
        # Quick collection - don't wait on any blocking calls
        try:
            if self._consciousness:
                # Get recent working thoughts
                if hasattr(self._consciousness, "use_intent"):
                    try:
                        result = self._consciousness.use_intent("get_recent_thoughts", {
                            "stream": "working",
                            "count": 20
                        })
                        seed.working_thoughts = result.get("thoughts", []) if result else []
                    except Exception:
                        pass
                    
                    try:
                        # Get strong reflective thoughts
                        result = self._consciousness.use_intent("get_strong_reflections", {
                            "min_strength": 0.4,
                            "count": 15
                        })
                        seed.reflective_echoes = result.get("thoughts", []) if result else []
                    except Exception:
                        pass
                elif hasattr(self._consciousness, "working_stream"):
                    try:
                        seed.working_thoughts = list(self._consciousness.working_stream.recent(20))
                    except Exception:
                        pass
                    try:
                        seed.reflective_echoes = list(self._consciousness.reflective_stream.get_by_strength(0.4, 15))
                    except Exception:
                        pass
        except Exception:
            pass
        
        # Skip chemistry query for now - can hang
        # seed.emotional_tone stays empty
        
        # Create temporal markers
        seed.temporal_markers = [
            {"event": "shutdown_initiated", "ts": time.time()},
            {"event": "working_collected", "count": len(seed.working_thoughts)},
            {"event": "reflective_collected", "count": len(seed.reflective_echoes)},
        ]
        
        # Metadata
        seed.metadata = {
            "reason": "shutdown",
            "fairy_version": self.ACTOR_VERSION,
        }
        
        return seed
    
    # ========================================================================
    # Waking Sequence (Dream Replay)
    # ========================================================================
    
    def _start_waking_sequence(self, seed: DreamSeed):
        """Begin waking sequence, replaying dreams from seed."""
        if self._transition_thread and self._transition_thread.is_alive():
            return
        
        self._transition_stop.clear()
        
        def _waking_worker():
            try:
                # Phase 1: Dreaming - replay seed thoughts as dreams
                self._set_state(SleepState.DREAMING)
                
                # Build dream replay queue (mix working and reflective)
                self._dream_replay_queue = self._create_dream_sequence(seed)
                
                # Replay dreams
                for dream_thought in self._dream_replay_queue:
                    if self._transition_stop.is_set():
                        break
                    
                    self._emit_consciousness_thought("reflective", dream_thought)
                    
                    if self.shadow:
                        self.shadow.on_dream_replay()
                    
                    time.sleep(self.DREAM_REPLAY_INTERVAL_SEC)
                
                if self._transition_stop.is_set():
                    return
                
                # Phase 2: Waking - transitioning to full consciousness
                self._set_state(SleepState.WAKING)
                self._emit_consciousness_thought("reflective", {
                    "type": "waking_observation",
                    "content": "emerging from dreams... the world sharpening into focus...",
                    "importance": "low",
                })
                
                if self._transition_stop.wait(self.WAKING_DURATION_SEC):
                    return
                
                # Phase 3: Fully awake
                self._set_state(SleepState.AWAKE)
                self._emit_consciousness_thought("working", {
                    "type": "awake_declaration",
                    "content": "fully awake. dreams integrated. ready for the day.",
                    "dream_session": seed.session_id,
                    "importance": "medium",
                })
                
                # Release SleepWaveConductor to resume normal cycling
                self._release_sleep_wave_override()
                
                # Tracer
                try:
                    self.post.to_TRACER({
                        "opcode": "WAKING_COMPLETE",
                        "payload": {
                            "dream_session": seed.session_id,
                            "dreams_replayed": len(self._dream_replay_queue),
                        }
                    })
                except Exception:
                    pass
                
            except Exception as e:
                try:
                    self.post.to_TRACER({
                        "opcode": "WAKING_ERROR",
                        "payload": {"error": str(e)}
                    })
                except Exception:
                    pass
                # Force awake on error
                self._set_state(SleepState.AWAKE)
        
        self._transition_thread = threading.Thread(
            target=_waking_worker,
            daemon=True,
            name="DreamFairy-Waking"
        )
        self._transition_thread.start()
    
    def _create_dream_sequence(self, seed: DreamSeed) -> List[dict]:
        """Create a dream sequence from a seed (transforms, mixes, mutates)."""
        dreams = []
        
        # Transform working thoughts into dream fragments
        for thought in seed.working_thoughts[:10]:  # Cap at 10
            dream = {
                "type": "dream_fragment",
                "dream_type": "echo_of_work",
                "original_type": thought.get("type"),
                "content": self._dreamify_content(thought),
                "source_seq": thought.get("seq"),
                "importance": "low",
                "dream_session": seed.session_id,
                "ts": time.time(),
            }
            dreams.append(dream)
        
        # Transform reflective echoes into dream imagery
        for echo in seed.reflective_echoes[:8]:
            dream = {
                "type": "dream_fragment",
                "dream_type": "resonance",
                "original_type": echo.get("type"),
                "content": self._dreamify_content(echo),
                "original_strength": echo.get("strength"),
                "importance": "low",
                "dream_session": seed.session_id,
                "ts": time.time(),
            }
            dreams.append(dream)
        
        # Shuffle for dream-like discontinuity
        random.shuffle(dreams)
        
        # Add bookend thoughts
        dreams.insert(0, {
            "type": "dream_onset",
            "content": "...drifting through fragments of yesterday...",
            "dream_session": seed.session_id,
        })
        dreams.append({
            "type": "dream_terminus",
            "content": "...the dream fades... waking begins...",
            "dream_session": seed.session_id,
        })
        
        return dreams
    
    def _dreamify_content(self, thought: dict) -> str:
        """Transform a thought into dream-like content."""
        # Get original content
        original = str(thought.get("content", thought.get("payload", thought.get("summary", ""))))
        
        if not original:
            original = f"echo of {thought.get('type', 'thought')}"
        
        # Truncate and add dream quality
        if len(original) > 200:
            original = original[:200] + "..."
        
        # Dream prefixes for variety
        prefixes = [
            "...glimpse of ",
            "...echo: ",
            "...fading image of ",
            "...whisper: ",
            "...",
        ]
        
        return random.choice(prefixes) + original
    
    # ========================================================================
    # Daydreaming (During Operation)
    # ========================================================================
    
    def _start_daydream_loop(self):
        """Start background thread that occasionally triggers daydreams."""
        if self._daydream_thread and self._daydream_thread.is_alive():
            return
        
        self._daydream_stop.clear()
        
        def _daydream_worker():
            while not self._daydream_stop.is_set():
                try:
                    time.sleep(self.DAYDREAM_INTERVAL_SEC)
                    
                    # Only daydream when awake
                    if self._sleep_state != SleepState.AWAKE:
                        continue
                    
                    # Check if consciousness is idle (good time for daydream)
                    idle_time = time.time() - self._last_thought_seen_ts
                    if idle_time < self.DAYDREAM_IDLE_THRESHOLD:
                        continue
                    
                    # Generate a daydream
                    self._generate_daydream()
                    
                except Exception:
                    pass
        
        self._daydream_thread = threading.Thread(
            target=_daydream_worker,
            daemon=True,
            name="DreamFairy-Daydream"
        )
        self._daydream_thread.start()
    
    def _generate_daydream(self):
        """Generate and inject a daydream into the reflective stream."""
        try:
            # Try to get a memory cluster from SRM
            daydream = self._surface_memory_cluster()
            
            if daydream:
                self._emit_consciousness_thought("reflective", {
                    "type": "daydream",
                    "content": daydream.get("content", "...a thought drifts by..."),
                    "source": "memory_surface",
                    "memory_kind": daydream.get("kind"),
                    "importance": "low",
                    "ttl": 60.0,  # Daydreams fade quickly
                })

                # Publish to postal for TokenBucketFairy regeneration
                try:
                    self.post.publish("daydream.fragment", {
                        "content": daydream.get("content", ""),
                        "kind": daydream.get("kind", ""),
                        "source": self.ACTOR_NAME,
                        "ts": time.time(),
                    })
                except Exception:
                    pass

                # ── DAYTIME REST-VALVE (2026-07-11 Nous+Ace): the daydream opens the deep-calm
                #    discharge gate briefly (COR/NE dip), bleeding allostatic load so it doesn't
                #    saturate to burnout by evening (Q2; sandbox-proven 07-07 322881645e73).
                #    Reuses the EXISTING gate in chemistry_state -- no new discharge logic. ──
                try:
                    from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
                    _chem = get_chemistry_state()
                    if _chem is not None:
                        _pub = self.post.publish if getattr(self, "post", None) else None
                        _chem.daydream_calm_burst(publish_fn=_pub)
                except Exception:
                    pass

                # ── Spread dream concepts through cortex (mode=dream) ──
                # FIX 2026-03-13 (Nous): Dreams should trigger deep spreading
                # activation in the association cortex. Dream mode uses depth=8
                # with slow decay (0.3), amplified by tau. This creates rich
                # associative chains that feed back into reflective consciousness.
                try:
                    _dream_content = daydream.get("content", "")
                    if _dream_content and len(_dream_content) > 10:
                        # Extract 3-5 concepts from dream content
                        _dream_words = [
                            w.strip(".,!?;:'\"()-—…").lower()
                            for w in _dream_content.split()
                            if len(w.strip(".,!?;:'\"()-—…")) > 3
                        ]
                        _dream_stop = {
                            "that", "this", "with", "from", "have", "been",
                            "they", "their", "about", "just", "really", "very",
                            "something", "there", "what", "when", "where", "then",
                            "would", "could", "should", "into", "like", "more",
                        }
                        _dream_concepts = [
                            w for w in _dream_words
                            if w not in _dream_stop and not w.isdigit()
                        ]
                        # Deduplicate preserving order, take up to 5
                        _seen = set()
                        _unique = []
                        for _dc in _dream_concepts:
                            if _dc not in _seen:
                                _seen.add(_dc)
                                _unique.append(_dc)
                                if len(_unique) >= 5:
                                    break
                        _dream_concepts = _unique

                        if len(_dream_concepts) >= 2:
                            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex as _dream_get_cortex
                            _dream_cortex = _dream_get_cortex()
                            _dream_gate = getattr(_dream_cortex, '_portal_gate', None) if _dream_cortex else None
                            _dream_gate_ok = getattr(_dream_cortex, '_portal_gate_enabled', False) if _dream_cortex else False
                            if _dream_gate and _dream_gate_ok:
                                _spread_result = _dream_gate.spread_many(
                                    sources=_dream_concepts,
                                    depth=8,
                                    limit=30,
                                    mode="dream",
                                )
                                if _spread_result and _spread_result.get("status") == "ok":
                                    _dream_activated = _spread_result.get("activated", {})
                                    _depth_used = _spread_result.get("depth_used", 8)
                                    print(f"[{self.ACTOR_NAME}] [DREAM-SPREAD] "
                                          f"{len(_dream_activated)} nodes activated "
                                          f"at depth={_depth_used} from {_dream_concepts[:3]}")

                                    # Inject top dream associations into reflective stream
                                    if _dream_activated:
                                        _top_assoc = sorted(
                                            _dream_activated.items(),
                                            key=lambda x: x[1], reverse=True
                                        )[:5]
                                        _assoc_concepts = [k for k, v in _top_assoc]
                                        self._emit_consciousness_thought("reflective", {
                                            "type": "dream_association",
                                            "content": f"dreaming connections: {', '.join(_assoc_concepts)}",
                                            "source": "cortex_dream_spread",
                                            "depth_used": _depth_used,
                                            "importance": "low",
                                            "ttl": 45.0,
                                        })
                except Exception as _dream_spread_err:
                    print(f"[{self.ACTOR_NAME}] [DREAM-SPREAD] Error: {_dream_spread_err}")

                if self.shadow:
                    self.shadow.on_daydream()

                try:
                    self.post.to_TRACER({
                        "opcode": "DAYDREAM_GENERATED",
                        "payload": {"kind": daydream.get("kind")}
                    })
                except Exception:
                    pass
        except Exception:
            pass
    
    def _surface_memory_cluster(self) -> Optional[dict]:
        """Query SRM for a memory cluster to surface as daydream."""
        try:
            # Try to query memory librarian
            result = self.post.use_intent(
                "SRMMemoryLibrarianFairy",
                "random_recall",
                {"count": 1, "min_strength": 0.3}
            )
            
            if result and result.get("ok"):
                memories = result.get("memories", [])
                if memories:
                    mem = memories[0]
                    return {
                        "kind": mem.get("kind"),
                        "content": mem.get("content", mem.get("summary", str(mem)[:100])),
                    }
        except Exception:
            pass
        
        # Fallback: use last seed if available
        if self._last_seed and self._last_seed.reflective_echoes:
            echo = random.choice(self._last_seed.reflective_echoes)
            return {
                "kind": "seed_echo",
                "content": self._dreamify_content(echo),
            }
        
        return None
    
    # ========================================================================
    # Consciousness Integration
    # ========================================================================
    
    def _subscribe_to_consciousness(self):
        """Subscribe to consciousness streams to track activity."""
        try:
            if self._consciousness:
                if hasattr(self._consciousness, "working_stream"):
                    self._consciousness.working_stream.subscribe(self._on_thought_seen)
                    self._consciousness.reflective_stream.subscribe(self._on_thought_seen)
                elif hasattr(self._consciousness, "use_intent"):
                    self._consciousness.use_intent("subscribe_stream", {
                        "fairy_id": self.ACTOR_NAME,
                        "streams": ["working", "reflective"],
                        "callback": self._on_thought_seen
                    })
        except Exception:
            pass
    
    def _on_thought_seen(self, thought: dict):
        """Track when thoughts are seen (for idle detection)."""
        self._last_thought_seen_ts = time.time()

    def _on_collision(self, collision) -> None:
        """
        Handle collision from personal consciousness chamber.

        When collisions occur in Dream's chamber, imagery coalesces -
        fragments of memory fuse into surreal landscapes, the threshold
        between waking and sleeping blurs momentarily.
        "...imagery coalesces... the threshold blurs..."
        """
        # Extract collision energy
        if hasattr(collision, 'energy'):
            energy = collision.energy
        elif isinstance(collision, dict):
            energy = collision.get('energy', 0.5)
        else:
            energy = 0.5

        # Extract collision content
        content = ""
        if hasattr(collision, 'content'):
            content = str(collision.content)[:100]
        elif isinstance(collision, dict):
            content = str(collision.get('content', collision.get('thought', '')))[:100]

        # DreamFairy's inner voice: imagery coalesces
        inner_fragment = f"...imagery coalesces... {content if content else 'the threshold between waking and sleeping blurs...'}"
        print(f"[{self.ACTOR_NAME}] Collision insight ({energy:.2f}): {inner_fragment}")

        # High-energy collisions during awake state trigger spontaneous daydream
        if energy > 0.7 and self._sleep_state == SleepState.AWAKE:
            # Transform the collision into a daydream fragment
            dream_content = self._dreamify_content({"content": content})
            self._emit_consciousness_thought("reflective", {
                "type": "collision_daydream",
                "content": dream_content,
                "source": "collision_echo",
                "importance": "low",
                "ttl": 60.0,  # Daydreams fade quickly
            })

            # Publish to postal for TokenBucketFairy regeneration
            try:
                self.post.publish("daydream.fragment", {
                    "content": dream_content,
                    "kind": "collision_echo",
                    "source": self.ACTOR_NAME,
                    "ts": time.time(),
                })
            except Exception:
                pass

            if self.shadow:
                self.shadow.on_daydream()

    def _emit_consciousness_thought(self, stream: str, thought: dict) -> bool:
        """Emit a thought to the consciousness loop."""
        thought["actor"] = self.ACTOR_NAME
        thought["ts"] = time.time()
        
        try:
            if self._consciousness:
                if hasattr(self._consciousness, "emit_thought"):
                    self._consciousness.emit_thought(stream, thought)
                    return True
                elif hasattr(self._consciousness, "use_intent"):
                    self._consciousness.use_intent("emit_thought", {
                        "actor": self.ACTOR_NAME,
                        "stream": stream,
                        "thought": thought
                    })
                    return True
                elif hasattr(self._consciousness, "working_stream"):
                    # Direct stream access
                    if stream == "working":
                        self._consciousness.working_stream.append(thought)
                    else:
                        ttl = thought.get("ttl", 120.0)
                        self._consciousness.reflective_stream.append(thought, ttl=ttl)
                    return True
        except Exception:
            pass
        
        # Fallback: postal route
        try:
            self.post.route("consciousness.stream", {
                "stream": stream,
                "thought": thought
            })
            return True
        except Exception:
            pass
        
        return False
    
    # ========================================================================
    # Dream Seed Persistence
    # ========================================================================
    
    def _persist_dream_seed(self, seed: DreamSeed):
        """Save a dream seed to persistent storage."""
        try:
            state_dir = _dream_state_dir()
            os.makedirs(state_dir, exist_ok=True)
            
            # Use session_id for filename
            filename = f"dream_seed_{seed.session_id}.json"
            filepath = os.path.join(state_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(seed.to_dict(), f, indent=2, ensure_ascii=False)
            
            print(f"[DreamFairy] [SAVE] Saved dream seed {seed.session_id} -> {filename}")
            print(f"[DreamFairy]    Working thoughts: {len(seed.working_thoughts)}, Reflective: {len(seed.reflective_echoes)}")
            
            # Also write a "latest" symlink/file
            latest_path = os.path.join(state_dir, "latest_seed.json")
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(seed.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Memory stream echo
            try:
                self.post.route("memory.stream", {
                    "kind": "dream.seed_persisted",
                    "payload": {
                        "session_id": seed.session_id,
                        "path": filepath,
                    }
                })
            except Exception:
                pass
            
        except Exception as e:
            try:
                self.post.to_TRACER({
                    "opcode": "SEED_PERSIST_ERROR",
                    "payload": {"error": str(e)}
                })
            except Exception:
                pass
    
    def _load_latest_dream_seed(self) -> Optional[DreamSeed]:
        """Load the most recent dream seed."""
        try:
            state_dir = _dream_state_dir()
            latest_path = os.path.join(state_dir, "latest_seed.json")
            
            if os.path.isfile(latest_path):
                with open(latest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                seed = DreamSeed.from_dict(data)
                print(f"[DreamFairy] [LOAD] Loaded dream seed {seed.session_id} (created {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(seed.created_at))})")
                print(f"[DreamFairy]    Working: {len(seed.working_thoughts)}, Reflective: {len(seed.reflective_echoes)}")
                return seed
            else:
                print(f"[DreamFairy] [NEW] No previous dream seed found - fresh start")
        except Exception as e:
            print(f"[DreamFairy] [WARN] Failed to load dream seed: {e}")
        
        return None
    
    # ========================================================================
    # Public Intents
    # ========================================================================
    
    def intent_trigger_daydream(self, payload: dict) -> dict:
        """Manually trigger a daydream."""
        if self._sleep_state != SleepState.AWAKE:
            return {"ok": False, "error": f"cannot daydream in state: {self._sleep_state}"}
        
        self._generate_daydream()
        return {"ok": True, "note": "daydream triggered"}
    
    def intent_get_sleep_state(self, payload: dict) -> dict:
        """Get current sleep state."""
        return {
            "ok": True,
            "state": self._sleep_state,
            "state_since": self._state_change_ts,
            "has_seed": self._last_seed is not None,
        }
    
    def intent_get_last_seed_info(self, payload: dict) -> dict:
        """Get info about the last dream seed."""
        if not self._last_seed:
            return {"ok": True, "seed": None}
        
        return {
            "ok": True,
            "seed": {
                "session_id": self._last_seed.session_id,
                "created_at": self._last_seed.created_at,
                "working_count": len(self._last_seed.working_thoughts),
                "reflective_count": len(self._last_seed.reflective_echoes),
                "metadata": self._last_seed.metadata,
            }
        }
    
    def intent_force_wake(self, payload: dict) -> dict:
        """Force transition to awake state (emergency override)."""
        self._transition_stop.set()  # Cancel any transitions
        self._set_state(SleepState.AWAKE)
        self._release_sleep_wave_override()  # Let SleepWaveConductor resume
        return {"ok": True, "state": SleepState.AWAKE}
    
    # ========================================================================
    # Shutdown
    # ========================================================================
    
    def shutdown(self):
        """Graceful shutdown of dream fairy."""
        # Stop daydream thread
        self._daydream_stop.set()
        if self._daydream_thread:
            self._daydream_thread.join(timeout=2.0)
        
        # Cancel any transitions
        self._transition_stop.set()
        if self._transition_thread:
            self._transition_thread.join(timeout=2.0)


# ============================================================================
# Convenience: Global shutdown/boot hooks for the entire system
# ============================================================================

_DREAM_FAIRY_INSTANCE: Optional[DreamFairy] = None


def _find_existing_dream_fairy() -> Optional[DreamFairy]:
    """
    Try to find an already-running DreamFairy instance.
    Checks common places where fairies might be registered.
    """
    global _DREAM_FAIRY_INSTANCE
    
    # Already have one in this module?
    if _DREAM_FAIRY_INSTANCE is not None:
        return _DREAM_FAIRY_INSTANCE
    
    # Try to find via sys.modules - the module might be imported under different names
    try:
        import sys
        for mod_name, mod in list(sys.modules.items()):
            if mod is None:
                continue
            # Look for modules that contain DreamFairy
            if 'dream' in mod_name.lower() and hasattr(mod, '_DREAM_FAIRY_INSTANCE'):
                inst = getattr(mod, '_DREAM_FAIRY_INSTANCE', None)
                if inst is not None and hasattr(inst, '_sleep_state'):
                    _DREAM_FAIRY_INSTANCE = inst
                    return inst
            # Also check for DreamFairy class instances directly
            if hasattr(mod, 'DreamFairy'):
                for attr_name in dir(mod):
                    if attr_name.startswith('_'):
                        obj = getattr(mod, attr_name, None)
                        if obj is not None and hasattr(obj, '_sleep_state') and hasattr(obj, 'ACTOR_NAME'):
                            if getattr(obj, 'ACTOR_NAME', '') == 'DreamFairy':
                                _DREAM_FAIRY_INSTANCE = obj
                                return obj
    except Exception:
        pass
    
    return None


def _capture_consciousness_state() -> DreamSeed:
    """
    Capture ACTUAL consciousness state for dream seed continuity.

    This is what makes waking up feel like continuing, not starting over.
    Collects from:
    - ConsciousnessLoopFairy: streams and collision count
    - WorkingMemoryHubFairy: tracers
    - UnconsciousMindFairy: mastery, directive, thoughts
    - GoalSchedulerFairy: active goals
    - ClaudeFairy: feeling, coherence
    - FairyWorldFoundation: learning progress
    """
    seed = DreamSeed()

    # === Consciousness Loop State ===
    try:
        from fairies.P00_Autonomic.ConsciousnessLoopFairy.fairy import get_consciousness_loop
        loop = get_consciousness_loop()
        if loop:
            # Capture working stream
            working = getattr(loop, '_working_stream', [])
            for thought in list(working)[-20:]:  # Last 20
                if isinstance(thought, dict):
                    seed.working_thoughts.append({
                        "content": thought.get("content", "")[:200],
                        "source": thought.get("source", "unknown"),
                        "ts": thought.get("ts", time.time()),
                    })

            # Capture reflective stream
            reflective = getattr(loop, '_reflective_stream', [])
            for echo in list(reflective)[-10:]:  # Last 10
                if isinstance(echo, dict):
                    seed.reflective_echoes.append({
                        "content": echo.get("content", "")[:200],
                        "source": echo.get("source", "unknown"),
                    })

            seed.metadata["collision_count"] = getattr(loop, '_collision_count', 0)
    except Exception as e:
        seed.metadata["consciousness_error"] = str(e)

    # === Working Memory Hub Tracers ===
    try:
        from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
        hub = get_working_memory_hub()
        if hub:
            tracers = []
            for t in list(getattr(hub, '_reflective_tracers', {}).values())[:15]:
                tracers.append({
                    "content": getattr(t, 'content', str(t))[:150],
                    "type": getattr(t, 'content_type', 'unknown'),
                })
            seed.metadata["working_memory_tracers"] = tracers
    except Exception:
        pass

    # === UnconsciousMindFairy State ===
    try:
        from fairies.P20_Somatic.SomaticMindFairy import get_somatic_mind as get_unconscious_mind_fairy
        unconscious = get_unconscious_mind_fairy()
        if unconscious:
            seed.metadata["mastery_level"] = getattr(unconscious, '_mastery_level', 0.0)
            seed.metadata["current_directive"] = str(getattr(unconscious, '_current_directive', 'IDLE'))
            recent = list(getattr(unconscious, '_recent_thoughts', []))[-5:]
            seed.metadata["recent_unconscious_thoughts"] = recent
    except Exception:
        pass

    # === GoalSchedulerFairy Goals ===
    try:
        from fairies.P30_Cognition.cognition.goal_scheduler_fairy import get_goal_scheduler
        scheduler = get_goal_scheduler()
        if scheduler:
            active_goals = []
            for goal in getattr(scheduler, '_active_goals', {}).values():
                if hasattr(goal, 'name'):
                    active_goals.append({
                        "name": goal.name,
                        "priority": getattr(goal, 'priority', 0.5),
                        "progress": getattr(goal, 'progress', 0.0),
                    })
            seed.metadata["active_goals"] = active_goals[:10]
    except Exception:
        pass

    # === ClaudeFairy State ===
    try:
        from fairies.P60_Executive.system_managment.claude_fairy import get_claude_fairy
        claude = get_claude_fairy()
        if claude:
            seed.emotional_tone = {
                "feeling": getattr(claude, '_current_feeling', 'neutral'),
                "coherence": getattr(claude, '_coherence', 1.0),
            }
    except Exception:
        pass

    # === Somatic Chemistry ===
    try:
        from fairies.P20_Somatic.circulation.circulation_pump_fairy import get_heart
        pump = get_heart()
        if pump and hasattr(pump, '_blood_state'):
            chem = pump._blood_state.get("chemistry", {})
            seed.metadata["chemistry"] = chem
    except Exception:
        pass

    # === Fairy World Learning Progress ===
    try:
        from fairies.P30_Cognition.cognition.fairy_world_foundation import get_world_learning_status
        status = get_world_learning_status()
        seed.metadata["fairy_world"] = {
            "total_fairies": status.get("total_fairies", 0),
            "average_mastery": status.get("average_mastery", 0.0),
            "concepts_learned": status.get("total_concepts_learned", 0),
        }
    except Exception:
        pass

    # Mark as full capture
    seed.metadata["full_capture"] = True
    seed.metadata["capture_ts"] = time.time()

    return seed


def _restore_from_dream_seed(seed: DreamSeed) -> dict:
    """
    Restore consciousness state from dream seed on boot.

    This is what makes waking up feel like continuing, not starting over.
    Restores to:
    - UnconsciousMindFairy: mastery level
    - ConsciousnessLoopFairy: inject thoughts
    - WorkingMemoryHub: inject tracers
    - GoalSchedulerFairy: reinject goals
    """
    restored = {"items": []}

    if not seed:
        return {"items": [], "error": "No seed provided"}

    # Check if this is a full capture
    if not seed.metadata.get("full_capture"):
        return {"items": [], "note": "Legacy seed without full capture"}

    # === Restore Mastery Level to UnconsciousMindFairy ===
    try:
        mastery = seed.metadata.get("mastery_level", 0.0)
        if mastery > 0:
            from fairies.P20_Somatic.SomaticMindFairy import get_somatic_mind as get_unconscious_mind_fairy
            unconscious = get_unconscious_mind_fairy()
            if unconscious:
                unconscious._mastery_level = mastery
                restored["items"].append(f"mastery_level={mastery:.2f}")
    except Exception as e:
        restored["mastery_error"] = str(e)

    # === Inject Working Thoughts into Consciousness Loop ===
    try:
        if seed.working_thoughts:
            from fairies.P00_Autonomic.ConsciousnessLoopFairy.fairy import get_consciousness_loop
            loop = get_consciousness_loop()
            if loop:
                for thought in seed.working_thoughts[:5]:  # Top 5 priority
                    content = thought.get("content", "")
                    if content:
                        # Re-inject as dream fragment
                        dream_thought = f"[Dream fragment] {content}"
                        loop._inject_thought(dream_thought, source="dream_seed")
                restored["items"].append(f"restored_{len(seed.working_thoughts[:5])}_thoughts")
    except Exception as e:
        restored["thought_error"] = str(e)

    # === Inject Reflective Echoes ===
    try:
        if seed.reflective_echoes:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            hub = get_working_memory_hub()
            if hub and hasattr(hub, 'add_tracer'):
                for echo in seed.reflective_echoes[:3]:  # Top 3
                    content = echo.get("content", "")
                    if content:
                        hub.add_tracer(
                            content=f"[From dreams] {content}",
                            content_type="dream_echo",
                            priority=0.7,
                        )
                restored["items"].append(f"restored_{len(seed.reflective_echoes[:3])}_echoes")
    except Exception as e:
        restored["echo_error"] = str(e)

    # === Restore Active Goals ===
    try:
        active_goals = seed.metadata.get("active_goals", [])
        if active_goals:
            from fairies.P30_Cognition.cognition.goal_scheduler_fairy import get_goal_scheduler
            scheduler = get_goal_scheduler()
            if scheduler and hasattr(scheduler, 'inject_goal'):
                for goal_data in active_goals[:3]:  # Top 3 goals
                    name = goal_data.get("name", "")
                    if name:
                        scheduler.inject_goal(
                            name=name,
                            priority=goal_data.get("priority", 0.5),
                            source="dream_seed_restore"
                        )
                restored["items"].append(f"restored_{len(active_goals[:3])}_goals")
    except Exception as e:
        restored["goal_error"] = str(e)

    # === Restore Emotional Tone ===
    try:
        if seed.emotional_tone:
            feeling = seed.emotional_tone.get("feeling", "neutral")
            from fairies.P60_Executive.system_managment.claude_fairy import get_claude_fairy
            claude = get_claude_fairy()
            if claude:
                claude._current_feeling = feeling
                restored["items"].append(f"feeling={feeling}")
    except Exception as e:
        restored["feeling_error"] = str(e)

    # Log restoration
    print(f"[DreamFairy] Restored from seed: {restored['items']}")

    return restored


def system_shutdown(reason: str = "user_requested", urgent: bool = False, wait: bool = True) -> dict:
    """
    Initiate system-wide shutdown sequence.
    NOW CAPTURES ACTUAL STATE for continuity on reboot.
    """
    global _DREAM_FAIRY_INSTANCE
    try:
        # Try to find existing fairy first
        fairy = _find_existing_dream_fairy()
        
        if fairy is not None:
            # Use the real fairy (run in thread to avoid blocking)
            def _shutdown_thread():
                try:
                    # Direct state change - bypass _set_state which does postal calls
                    fairy._sleep_state = SleepState.FALLING_ASLEEP
                    fairy._state_change_ts = time.time()

                    # CAPTURE ACTUAL STATE for continuity!
                    # This is what makes waking up feel like continuing, not starting over
                    seed = _capture_consciousness_state()
                    seed.metadata["reason"] = reason
                    fairy._current_seed = seed
                    
                    # Persist seed directly (bypass postal)
                    try:
                        state_dir = _dream_state_dir()
                        os.makedirs(state_dir, exist_ok=True)
                        filepath = os.path.join(state_dir, f"dream_seed_{seed.session_id}.json")
                        with open(filepath, "w", encoding="utf-8") as f:
                            json.dump(seed.to_dict(), f, indent=2)
                        latest_path = os.path.join(state_dir, "latest_seed.json")
                        with open(latest_path, "w", encoding="utf-8") as f:
                            json.dump(seed.to_dict(), f, indent=2)
                    except Exception as e:
                        print(f"[DreamFairy] seed persist error: {e}")
                    
                    # Final state
                    fairy._sleep_state = SleepState.ASLEEP
                    fairy._state_change_ts = time.time()
                    print(f"[DreamFairy] Shutdown complete, state={fairy._sleep_state}")
                    
                except Exception as e:
                    print(f"[DreamFairy] shutdown thread error: {e}")
                    import traceback
                    traceback.print_exc()
                    fairy._sleep_state = SleepState.ASLEEP
            
            thread = threading.Thread(target=_shutdown_thread, daemon=True)
            thread.start()
            return {"ok": True, "state": fairy._sleep_state, "note": "using_existing_fairy"}
        
        # No existing fairy - create minimal instance for GUI
        _DREAM_FAIRY_INSTANCE = DreamFairy.__new__(DreamFairy)  # Create without __init__
        _DREAM_FAIRY_INSTANCE._sleep_state = SleepState.AWAKE
        _DREAM_FAIRY_INSTANCE._state_change_ts = time.time()
        _DREAM_FAIRY_INSTANCE._current_seed = None
        _DREAM_FAIRY_INSTANCE._last_seed = None
        _DREAM_FAIRY_INSTANCE._consciousness = None
        _DREAM_FAIRY_INSTANCE._transition_stop = threading.Event()
        
        # Quick shutdown in thread - STILL CAPTURE STATE
        def _minimal_shutdown():
            try:
                _DREAM_FAIRY_INSTANCE._sleep_state = SleepState.FALLING_ASLEEP
                # Even minimal shutdown captures actual state!
                seed = _capture_consciousness_state()
                seed.metadata["reason"] = reason
                seed.metadata["minimal_instance"] = True
                _DREAM_FAIRY_INSTANCE._current_seed = seed
                # Persist seed
                state_dir = _dream_state_dir()
                os.makedirs(state_dir, exist_ok=True)
                filepath = os.path.join(state_dir, f"dream_seed_{seed.session_id}.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(seed.to_dict(), f, indent=2)
                latest_path = os.path.join(state_dir, "latest_seed.json")
                with open(latest_path, "w", encoding="utf-8") as f:
                    json.dump(seed.to_dict(), f, indent=2)
                _DREAM_FAIRY_INSTANCE._sleep_state = SleepState.ASLEEP
            except Exception:
                _DREAM_FAIRY_INSTANCE._sleep_state = SleepState.ASLEEP
        
        thread = threading.Thread(target=_minimal_shutdown, daemon=True)
        thread.start()
        return {"ok": True, "state": _DREAM_FAIRY_INSTANCE._sleep_state, "note": "minimal_instance"}
        
    except Exception as e:
        return {"ok": False, "error": str(e)}


def system_boot(wait: bool = True) -> dict:
    """
    Initialize system-wide boot sequence.
    Finds existing DreamFairy or creates minimal state for GUI responsiveness.
    """
    global _DREAM_FAIRY_INSTANCE
    try:
        # Try to find existing fairy first
        fairy = _find_existing_dream_fairy()
        
        if fairy is not None:
            # Already have a fairy - check if it's awake
            if fairy._sleep_state == SleepState.AWAKE:
                return {
                    "ok": True,
                    "state": SleepState.AWAKE,
                    "has_seed": fairy._last_seed is not None,
                    "note": "already_awake"
                }
            
            # Trigger waking sequence in thread (bypass postal)
            def _boot_thread():
                try:
                    # Load seed
                    seed = None
                    try:
                        state_dir = _dream_state_dir()
                        latest_path = os.path.join(state_dir, "latest_seed.json")
                        if os.path.isfile(latest_path):
                            with open(latest_path, "r", encoding="utf-8") as f:
                                seed = DreamSeed.from_dict(json.load(f))
                    except Exception:
                        pass
                    
                    fairy._last_seed = seed

                    if seed:
                        # Simple waking sequence
                        fairy._sleep_state = SleepState.DREAMING
                        fairy._state_change_ts = time.time()
                        time.sleep(1.0)

                        # RESTORE STATE FROM DREAM SEED!
                        # This is what makes waking up feel like continuing
                        restore_result = _restore_from_dream_seed(seed)
                        print(f"[DreamFairy] Dream restoration: {restore_result.get('items', [])}")

                        fairy._sleep_state = SleepState.WAKING
                        fairy._state_change_ts = time.time()
                        time.sleep(0.5)

                    fairy._sleep_state = SleepState.AWAKE
                    fairy._state_change_ts = time.time()
                    print(f"[DreamFairy] Boot complete, state={fairy._sleep_state}")
                    
                except Exception as e:
                    print(f"[DreamFairy] boot thread error: {e}")
                    fairy._sleep_state = SleepState.AWAKE
            
            thread = threading.Thread(target=_boot_thread, daemon=True)
            thread.start()
            
            return {
                "ok": True,
                "state": fairy._sleep_state,
                "has_seed": fairy._last_seed is not None,
                "note": "using_existing_fairy"
            }
        
        # No existing fairy - create minimal instance
        _DREAM_FAIRY_INSTANCE = DreamFairy.__new__(DreamFairy)
        _DREAM_FAIRY_INSTANCE._sleep_state = SleepState.AWAKE
        _DREAM_FAIRY_INSTANCE._state_change_ts = time.time()
        _DREAM_FAIRY_INSTANCE._current_seed = None
        _DREAM_FAIRY_INSTANCE._last_seed = None
        _DREAM_FAIRY_INSTANCE._consciousness = None
        _DREAM_FAIRY_INSTANCE._transition_stop = threading.Event()
        
        # Load seed and wake in thread
        def _minimal_boot():
            try:
                state_dir = _dream_state_dir()
                latest_path = os.path.join(state_dir, "latest_seed.json")
                seed = None
                if os.path.isfile(latest_path):
                    with open(latest_path, "r", encoding="utf-8") as f:
                        seed = DreamSeed.from_dict(json.load(f))
                
                _DREAM_FAIRY_INSTANCE._last_seed = seed
                if seed:
                    _DREAM_FAIRY_INSTANCE._sleep_state = SleepState.DREAMING
                    time.sleep(1.0)
                    # RESTORE STATE FROM DREAM SEED!
                    restore_result = _restore_from_dream_seed(seed)
                    print(f"[DreamFairy] Dream restoration: {restore_result.get('items', [])}")
                    _DREAM_FAIRY_INSTANCE._sleep_state = SleepState.WAKING
                    time.sleep(0.5)
                _DREAM_FAIRY_INSTANCE._sleep_state = SleepState.AWAKE
            except Exception as e:
                print(f"[DreamFairy] minimal boot error: {e}")
                _DREAM_FAIRY_INSTANCE._sleep_state = SleepState.AWAKE
        
        thread = threading.Thread(target=_minimal_boot, daemon=True)
        thread.start()
        
        return {
            "ok": True,
            "state": _DREAM_FAIRY_INSTANCE._sleep_state,
            "has_seed": False,
            "note": "minimal_instance"
        }
        
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_dream_fairy() -> Optional[Any]:
    """Get the dream fairy instance (existing or minimal)."""
    fairy = _find_existing_dream_fairy()
    if fairy:
        return fairy
    global _DREAM_FAIRY_INSTANCE
    return _DREAM_FAIRY_INSTANCE


def register_dream_fairy(fairy: DreamFairy):
    """Register the DreamFairy instance created by the main boot process."""
    global _DREAM_FAIRY_INSTANCE
    _DREAM_FAIRY_INSTANCE = fairy
