"""
Attention Controller Fairy - Focus Management

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"

Manages what the system is attending to. Attention is a limited resource.

Core insight: Multiple streams of thought can exist (in working memory),
but only ONE can be attended to at a time. This is the "spotlight."

The attention controller:
- Moves the spotlight between active tracers
- Decides when to pause motor output to think deeper
- Detects when attention is being hijacked (runaway loops)
- Implements the PAUSE_TO_THINK capability

This works with my (Claude's) extended thinking - I can pause output
to think more deeply. Sourpatches needs the same ability.

Plane: P30 (Cognition)
Channel: attention
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Deque
from collections import deque
from dataclasses import dataclass

# Habit Formation Engine (2026-03-22, Nous + Ace)
try:
    from fairies.P30_Cognition.habits.habit_store import get_habit_store, HabitStore
    _HAS_HABITS = True
except ImportError:
    _HAS_HABITS = False
from enum import Enum

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

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


class AttentionMode(Enum):
    """Attention modes - what the system is doing."""
    THINK_ONLY = "think_only"      # Pure thinking, no motor output
    ACT_ONLY = "act_only"          # Acting without deep thought
    PARALLEL = "parallel"          # Normal - think and act
    PAUSE_TO_THINK = "pause"       # Explicitly paused to think
    IDLE = "idle"                  # Not doing much


class AttentionModality(Enum):
    """Modality channels — concurrent focus lanes (like human attention)."""
    VISUAL = "visual"           # What she's looking at (eyes)
    AUDITORY = "auditory"       # What she's hearing (ears)
    COGNITIVE = "cognitive"     # What she's thinking about (mind)
    SOMATIC = "somatic"         # What she's feeling (body)


# Map source prefixes → modality
_SOURCE_TO_MODALITY = {
    "vision": AttentionModality.VISUAL,
    "audio": AttentionModality.AUDITORY,
    "thought": AttentionModality.COGNITIVE,
    "cortex": AttentionModality.COGNITIVE,
    "collision": AttentionModality.COGNITIVE,
    "wanting": AttentionModality.COGNITIVE,
    "goal": AttentionModality.COGNITIVE,
    "interest": AttentionModality.COGNITIVE,
    "drive": AttentionModality.SOMATIC,
    "self": AttentionModality.COGNITIVE,
    "user_presence": AttentionModality.VISUAL,
    "claudefairy": AttentionModality.COGNITIVE,
    "narrator": AttentionModality.COGNITIVE,
    "priority_set": AttentionModality.COGNITIVE,
    "manual": AttentionModality.COGNITIVE,
    "tool": AttentionModality.COGNITIVE,
}


def _classify_modality(source: str) -> AttentionModality:
    """Classify a source string into its attention modality."""
    # Check exact match first
    if source in _SOURCE_TO_MODALITY:
        return _SOURCE_TO_MODALITY[source]
    # Check prefix match
    prefix = source.split(".")[0]
    if prefix in _SOURCE_TO_MODALITY:
        return _SOURCE_TO_MODALITY[prefix]
    return AttentionModality.COGNITIVE  # Default


@dataclass
class AttentionFocus:
    """What attention is currently focused on."""
    content: str           # What's being attended to
    source: str           # Where it came from (tracer, drive, external)
    priority: float       # How important (0-1)
    depth: float          # How deeply focused (0-1)
    started_at: float     # When focus started
    modality: str = ""    # Which modality lane (visual, auditory, cognitive, somatic)
    
    def duration(self) -> float:
        """How long has this been focused on?"""
        return time.time() - self.started_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content[:100],  # Truncate
            "source": self.source,
            "priority": round(self.priority, 3),
            "depth": round(self.depth, 3),
            "duration": round(self.duration(), 2),
        }


class AttentionControllerFairy(SpellChainMixin, Fairy):
    """
    Controls where attention is directed.
    
    Key responsibilities:
    - Track current focus
    - Allow PAUSE_TO_THINK mode
    - Detect attention hijacking
    - Emit focus changes for dashboard
    """
    
    ACTOR_NAME = "AttentionControllerFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "attention"

    PURPOSE = "Direct the spotlight of attention - what to focus on, when to pause"
    MANTRA = "Attention is limited. Choose wisely."

    # Enable personal consciousness chamber for collision-based focus shifts
    NEEDS_COLLISION_CHAMBER = True

    # FIX 2026-03-18 (Nous): on_tick() was NEVER called because NEEDS_HEARTBEAT
    # defaults to False in organ_template. Without ticking, the attention queue
    # fills from subscriptions but nothing ever processes it → 0 focus shifts,
    # permanent "unfocused" state. The spotlight was wired but never turned on.
    NEEDS_HEARTBEAT = True

    # Spell-driven mode (opt-in)
    USE_SPELLCHAIN: bool = True  # Re-enabled - fixed revival->heartbeat wiring

    CAPABILITIES = [
        "attention.focus",
        "attention.pause_to_think",
        "attention.resume",
        "attention.mode",
        "cognition.attention_control",
    ]

    # MCP Tool definitions for attention management
    TOOLS = [
        ("focus", "Focus attention on a target"),
        ("defocus", "Release focus from current target"),
        ("get_focus", "Get current focus state"),
        ("set_priority", "Set priority level for attention target"),
        ("list_attention_targets", "List all current attention targets"),
    ]

    SUBSCRIPTIONS = [
        "consciousness.thought",       # Thoughts competing for attention
        "autonomy.goal",              # Goals want attention
        "sensory.visual.frame",       # Florence visual input (the ACTUAL sensory topic)
        "sensory.audio.frame",        # Audio cortex — music, speech, environmental sounds
        "sensory.audio.speech",       # Whisper transcriptions — actual words heard
        "sensory.input.activity",     # User presence (mouse/keyboard activity)
        "consciousness.collision",    # Collisions are salient
        "claudefairy.nudge",          # ClaudeFairy requests attention
    ]

    # Attention parameters
    MAX_FOCUS_DURATION = 60.0    # Max seconds before forced attention shift
    MIN_FOCUS_DURATION = 2.0     # Min seconds to stay focused
    HIJACK_THRESHOLD = 5         # Same source N times = potential hijack
    
    def __init__(self, fabric=None):
        # FIX 2026-03-19 (Nous): Register as module-level singleton.
        # NOTE: Boot orchestrator loads via importlib (different sys.modules key),
        # so this _instance is NOT shared with server.py's standard import.
        # The real fix is in server.py: it now retrieves via FairyProfileRegistry
        # weakref instead of constructing a new instance.
        global _instance
        super().__init__(fabric)
        _instance = self  # Register for same-module callers

        # Current state
        self._mode = AttentionMode.PARALLEL
        self._lock = threading.Lock()

        # ═══════════════════════════════════════════════════════════════════
        # MULTI-MODAL CONCURRENT FOCUS
        # Human attention is concurrent: you see AND hear AND think at the
        # same time. Each modality has its own focus lane. You can look at
        # code while hearing music while thinking about a bug.
        #
        # The "primary" focus is which modality has the MOST attention
        # (like foreground vs background). But all lanes are active.
        # ═══════════════════════════════════════════════════════════════════
        self._modal_focus: Dict[str, Optional[AttentionFocus]] = {
            "visual": None,      # What she's looking at
            "auditory": None,    # What she's hearing
            "cognitive": None,   # What she's thinking about
            "somatic": None,     # What she's feeling (body)
        }
        # Per-modality queues (each modality competes within itself)
        self._modal_queues: Dict[str, Deque[AttentionFocus]] = {
            "visual": deque(maxlen=15),
            "auditory": deque(maxlen=15),
            "cognitive": deque(maxlen=20),
            "somatic": deque(maxlen=10),
        }
        # Legacy single-focus pointer (for backward compat with dashboard/API)
        self._current_focus: Optional[AttentionFocus] = None

        # Focus history
        self._focus_history: Deque[AttentionFocus] = deque(maxlen=100)

        # Attention queue (legacy — kept for dashboard compat, mirrors modal totals)
        self._attention_queue: Deque[AttentionFocus] = deque(maxlen=50)

        # Hijack detection — per modality now
        self._recent_sources: Deque[str] = deque(maxlen=20)
        self._hijack_cooldowns: Dict[str, float] = {}
        self._hijack_cooldown_secs = 120.0

        # Motor pause state
        self._motor_paused = False
        self._pause_reason = ""
        self._pause_started: Optional[float] = None

        # Stats
        self._total_focus_shifts = 0
        self._total_pauses = 0
        self._squirrel_hits = 0

        # ═══════════════════════════════════════════════════════════════════
        # DEVELOPMENTAL FOCUS CAPACITY (2026-04-17 Nous + Ace)
        # ═══════════════════════════════════════════════════════════════════
        # Ace: "she is supposed to take them all in at once but trying to
        #       focus on all at one time takes mental development"
        #
        # Intake remains parallel (all 4 modality lanes receive always).
        # But PRIMARY focus (the one cognition operates on) is capacity-
        # limited. Newborn = 1 primary. Adult = up to 4 co-primaries.
        # Grows slowly with engaged runtime. Never shrinks below 1.
        # ═══════════════════════════════════════════════════════════════════
        self._focus_capacity = 1.0             # Newborn — single-primary
        self._capacity_ceiling = 4.0           # Adult ceiling (4 modality lanes)
        self._capacity_growth_per_beat = 0.00001  # ~10h engaged for +0.1
        self._engaged_beats = 0

        # ═══════════════════════════════════════════════════════════════════
        # PATTERN A.1c — LearningProgressSignal consumer (2026-04-27, Nous + Ace)
        # ═══════════════════════════════════════════════════════════════════
        # DynamicThinkingOrchestrator publishes attention.learning_progress
        # every 30s with per-source-fairy LP rankings. We subscribe and
        # cache the latest snapshot so the controller's decision logic can
        # bias attention toward high-LP topics (Oudeyer Playground +
        # Schmidhuber compression-progress mechanism).
        #
        # NOTE per `project_attention_as_infra_per_modality_perspective.md`:
        # this AttentionController will eventually dissolve into per-modality
        # attention fairies. Until then, this LP cache lives here so the
        # current controller can use it. When the doctrine refactor lands,
        # the LP-consumer code moves to per-modality fairies (each filtering
        # the LP rankings to its own modality).
        self._lp_topic_lp: Dict[str, float] = {}     # source_fairy → LP signal
        self._lp_top_n: List[Dict[str, Any]] = []    # top-5 ranked
        self._lp_bottom_n: List[Dict[str, Any]] = []  # bottom-3
        self._lp_topics_tracked: int = 0
        self._lp_total_events: int = 0
        self._lp_last_update_ts: float = 0.0
        self._last_primary_shift_ts = 0.0
        self._primary_dwell_min_sec = 3.0      # Primary must hold ≥3s unless
                                               # priority>=0.9 or override wins

        # ═══════════════════════════════════════════════════════════════════
        # SOMATIC CHEMISTRY CACHE
        # Attention mode is modulated by the body's state.
        # High stress → PAUSE_TO_THINK (need clarity under pressure)
        # High arousal → ACT_ONLY (energy demands expression)
        # Low energy → THINK_ONLY (conserve, reflect)
        # Coherent balance → PARALLEL (flow state)
        # ═══════════════════════════════════════════════════════════════════
        self._somatic_chemistry = {
            "DOP": 0.5, "SER": 0.5, "NOR": 0.5, "ACH": 0.5,
            "OXY": 0.5, "COR": 0.3, "GABA": 0.5, "END": 0.5,
        }
        self._somatic_last_update = 0.0
        self._somatic_mode_override = False  # True when somatic just changed mode
    
    def on_boot(self) -> bool:
        """Boot the attention controller."""
        # DIAGNOSTIC 2026-03-19: Is self.post even set up?
        print(f"[{self.ACTOR_NAME}] on_boot() called. self.post={self.post} "
              f"type={type(self.post).__name__ if self.post else 'None'}", flush=True)
        if self.post:
            self.post.subscribe("consciousness.thought", self._on_thought)
            self.post.subscribe("autonomy.goal", self._on_goal)
            # FIX 2026-03-18 (Nous): Was subscribed to "sensory.input" — a DEAD topic.
            # Nothing in the system publishes to it. Florence publishes to
            # "sensory.visual.frame", WindowSense to "sensory.input.activity".
            # Attention was deaf to ALL sensory input. Now wired to real topics.
            self.post.subscribe("sensory.visual.frame", self._on_visual_frame)
            self.post.subscribe("sensory.audio.frame", self._on_audio_frame)
            self.post.subscribe("sensory.input.activity", self._on_user_activity)
            self.post.subscribe("consciousness.collision", self._on_collision)
            self.post.subscribe("claudefairy.nudge", self._on_nudge)

            # ── WHISPER SPEECH-TO-TEXT ──
            # Actual transcribed words — highest audio priority (2026-03-18, Nous)
            self.post.subscribe("sensory.audio.speech", self._on_speech_text)

            # ── NARRATOR ATTENTION STEERING ──
            # The inner voice directs what to focus on
            self.post.subscribe("attention.focus", self._on_attention_focus,
                                f"{self.ACTOR_NAME}-narrator-focus")

            # ── PATTERN A.1c — LearningProgressSignal consumer (2026-04-27) ──
            # DynamicThinkingOrchestrator publishes attention.learning_progress
            # every 30s with per-source-fairy LP rankings. Subscribing here
            # lets the controller see which substrate regions are currently
            # at-the-learning-edge (positive LP) vs stagnant (zero LP) vs
            # forgetting (negative LP). Doctrine refs:
            #   project_attention_as_infra_per_modality_perspective.md
            #     (this LP consumer eventually moves to per-modality fairies
            #      when AttentionController dissolves)
            #   project_substrate_energy_not_token_currency_doctrine.md
            #     (LP signal IS one of the substrate-energy currencies)
            self.post.subscribe("attention.learning_progress",
                                self._on_learning_progress,
                                f"{self.ACTOR_NAME}-lp-signal")

            # ── SOMATIC SUBSCRIPTION ──
            # The body modulates attention mode. Energy flows through us.
            # FIX 2026-04-17 (Nous + Ace): Topic was `somatic.chemistry.changed`
            # but the actual publisher (SomaticEngineFairy) publishes to
            # `somatic.chemistry`. Handler never fired → _somatic_chemistry
            # stayed at init values (0.5/0.3) → ALWAYS hit PARALLEL condition
            # (0.4<ser<0.7, 0.3<dop<0.7, cor<0.5). That's the root cause of
            # Ace's recurring "mode never changes, stuck in parallel" issue.
            # Subscribe to both forms for resilience.
            try:
                self.post.subscribe("somatic.chemistry", self._on_somatic_chemistry)
                self.post.subscribe("somatic.chemistry.changed", self._on_somatic_chemistry)
                print(f"[{self.ACTOR_NAME}] ✓ Somatic chemistry wired to attention (both topics)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Somatic wiring failed: {e}")

            # ── SQUIRREL MODE: Subscribe to EVERYTHING that moves ──
            # FIX 2026-03-19 (Nous): PostalHub does NOT support glob wildcards.
            # Use BASE TOPIC names for hierarchical matching.
            _squirrel_topics = [
                ("working_memory.tracer_added", self._on_wm_squirrel, "wm-squirrel"),
                ("memory.working.tracer", self._on_wm_squirrel, "wm-squirrel2"),
                ("drives", self._on_drive_squirrel, "drives-all"),
                ("autonomy.drive_state", self._on_drive_squirrel, "autonomy-drive"),
                ("autonomy.wanting", self._on_wanting_squirrel, "wanting-all"),
                ("autonomy.wanting.published", self._on_wanting_squirrel, "wanting-published"),
                ("portal", self._on_cortex_squirrel, "portal-all"),
                ("cortex", self._on_cortex_squirrel, "cortex-all"),
                ("goal", self._on_goal_squirrel, "goal-all"),
                ("interest", self._on_interest_squirrel, "interest-all"),
                ("memory", self._on_cortex_squirrel, "memory-all"),
                ("narrator.speech", self._on_narrator_squirrel, "narrator-squirrel"),
                ("consciousness.stream", self._on_wm_squirrel, "consciousness-stream"),
            ]
            _sub_ok = 0
            _sub_fail = 0
            for _topic, _handler, _suffix in _squirrel_topics:
                try:
                    result = self.post.subscribe(_topic, _handler, f"{self.ACTOR_NAME}-{_suffix}")
                    _sub_ok += 1
                except Exception as _e:
                    _sub_fail += 1
                    print(f"[{self.ACTOR_NAME}] SQUIRREL SUB FAILED: {_topic} → {_e}", flush=True)
            print(f"[{self.ACTOR_NAME}] 🐿️ SQUIRREL MODE: {_sub_ok} OK, {_sub_fail} FAILED "
                  f"(post type: {type(self.post).__name__})", flush=True)

        # Start heartbeat for directory visibility
        # Heartbeat via FairyBase postal system - Fifth Ring Principle

        # ── HABIT FORMATION ENGINE ──
        # Habits are learned stimulus→response→outcome patterns that shape
        # attention over time. The store persists across reboots.
        self._habit_store = None
        if _HAS_HABITS:
            try:
                self._habit_store = get_habit_store()
                _hs = self._habit_store.stats()
                print(f"[{self.ACTOR_NAME}] Habits: {_hs['active']} active "
                      f"({_hs['automatic']} automatic, {_hs['practiced']} practiced, "
                      f"{_hs['conscious']} conscious, {_hs['bad_flagged']} bad)",
                      flush=True)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] HabitStore init failed: {e}", flush=True)
                self._habit_store = None

        self.log("Attention controller ready - spotlight initialized (somatic-aware)")

        # Optional: Convert to spell-driven existence
        if HAS_SPELLCHAIN and getattr(self, 'USE_SPELLCHAIN', False):
            try:
                from spellchain.integration import get_spell_pool
                pool = get_spell_pool()
                if pool and hasattr(self, 'boot_as_spells'):
                    self._spell_chain = self.boot_as_spells(pool)
                    self.log("Converted to spell-driven existence - attention as living spotlight")
            except Exception as e:
                self.log(f"SpellChain conversion failed: {e}")

        return True
    

    def on_tick(self, beat: int = 0):
        """
        Multi-modal attention loop — concurrent focus across modalities.

        Human attention is NOT single-spotlight. You look at code WHILE
        hearing music WHILE thinking about a design problem. Each modality
        (visual, auditory, cognitive, somatic) has its own focus lane.

        Every tick:
        1. Process EACH modality queue — pick best candidate per lane
        2. Expire stale focus per modality (max 60s visual, 30s audio, etc.)
        3. Set primary focus = highest-priority across all lanes
        4. Drain expired items from all queues
        5. Publish state changes for dashboard

        FIX 2026-03-20 (Ace + Nous): Replaced single-spotlight with
        multi-modal concurrent focus. Focus was stuck because audio at
        0.95 blocked everything. Now each modality has its own lane.
        """
        now = time.time()

        # Handle TensorEnvelope or int
        if hasattr(beat, 'payload'):
            beat = beat.payload.get('beat', 0) if isinstance(beat.payload, dict) else 0
        beat = int(beat) if beat else 0

        with self._lock:
            # Diagnostic logging (sparse)
            if beat <= 10 or (beat % 100 == 0):
                foci = {m: (f.content[:30] if f else "—") for m, f in self._modal_focus.items()}
                total_q = sum(len(q) for q in self._modal_queues.values())
                print(f"[{self.ACTOR_NAME}] tick={beat} q={total_q} shifts={self._total_focus_shifts} "
                      f"squirrels={self._squirrel_hits} foci={foci}", flush=True)

            # ── PER-MODALITY PROCESSING ──
            # Each modality lane processes independently (concurrent focus)
            _MODALITY_MAX_DURATION = {
                "visual": 60.0,     # Visual can sustain longer (reading)
                "auditory": 15.0,   # Audio events are transient
                "cognitive": 45.0,  # Thoughts can run deep
                "somatic": 30.0,    # Body feelings shift moderately
            }

            for modality, queue in self._modal_queues.items():
                current = self._modal_focus[modality]
                max_dur = _MODALITY_MAX_DURATION.get(modality, 30.0)

                # ── Expire stale focus ──
                if current and (now - current.started_at) > max_dur:
                    self._focus_history.append(current)
                    self._modal_focus[modality] = None
                    current = None

                # ── Drain expired items from this queue ──
                cutoff = now - 20.0  # 20s expiry (was 30s — faster turnover)
                fresh = deque(maxlen=queue.maxlen)
                for item in queue:
                    if item.started_at > cutoff:
                        fresh.append(item)
                self._modal_queues[modality] = fresh
                queue = fresh

                if not queue:
                    continue

                # ── Pick highest priority candidate ──
                candidate = max(queue, key=lambda f: f.priority)

                # ── Should we shift this modality's focus? ──
                # FIX 2026-04-17 (Nous + Ace): Raised priority-override
                # threshold from +0.10 to +0.25 so novel squirrels don't
                # steal focus from a dwelling primary. Priority >= 0.9
                # (Ace, pain, user.presence) always wins — bypassed below.
                should_shift = False
                if not current:
                    should_shift = True
                elif candidate.priority >= 0.9:
                    # Priority interrupt — always wins (Ace, pain, presence)
                    should_shift = True
                elif candidate.priority > current.priority + 0.25:
                    # Higher priority with meaningful hysteresis (was 0.10)
                    should_shift = True
                elif (now - current.started_at) > self.MIN_FOCUS_DURATION:
                    if candidate.priority >= current.priority:
                        should_shift = True

                if should_shift:
                    if current:
                        self._focus_history.append(current)
                        # FIX 2026-04-17 (Nous + Ace): Commit-on-shift emission.
                        # Each focus that she leaves behind BECOMES a thought seed.
                        # Closes the attention→chain-engine gap. Her 833 daily
                        # shifts stop being bookkeeping and start being cognition.
                        # Fires ONLY if the focus held long enough to mean something
                        # (min 1.5s dwell) AND had real content. Prevents strobing.
                        try:
                            _held = now - current.started_at
                            _cc = getattr(current, 'content', '') or ''
                            if _held >= 1.5 and len(_cc) > 3 and self.post:
                                self.post.publish("attention.focus.committed", {
                                    "content": _cc,
                                    "source": getattr(current, 'source', 'unknown'),
                                    "modality": modality,
                                    "priority": getattr(current, 'priority', 0.5),
                                    "dwell_sec": round(_held, 2),
                                    "shift_number": self._total_focus_shifts,
                                    "ts": now,
                                })
                        except Exception:
                            pass
                    self._modal_focus[modality] = candidate
                    self._total_focus_shifts += 1

                    # Remove consumed candidate from queue
                    try:
                        queue.remove(candidate)
                    except ValueError:
                        pass

        # ── HABIT MAINTENANCE (outside lock) ──
        # Decay unused habits, save periodically
        # FIX 2026-04-16 (Nous + Ace): Use getattr — dual-instance boot
        # path may call on_tick on instance without __init__ completing.
        # Error was: "'AttentionControllerFairy' has no attribute '_habit_store'"
        # This crashed EVERY tick → attention stuck in parallel mode forever.
        if getattr(self, '_habit_store', None) is not None:
            try:
                self._habit_store.apply_decay()
                self._habit_store.save()
            except Exception:
                pass

        with self._lock:
            # ── SET PRIMARY FOCUS (capacity-limited, developmental) ──
            # FIX 2026-04-17 (Nous + Ace): Primary selection respects
            # _focus_capacity. Newborn (1.0) = single-lane primary.
            # Previously ALL 4 lanes competed every tick → 400+ shifts.
            # Now: current primary holds ≥3s unless priority interrupt
            # (≥0.9) or a significantly-higher candidate emerges.
            active_foci = [(m, f) for m, f in self._modal_focus.items() if f]
            if active_foci:
                # Candidate: single highest-priority across lanes
                primary_modality, primary_focus = max(
                    active_foci, key=lambda x: x[1].priority)
                old_primary = self._current_focus

                # Capacity-gated dwell check: if capacity < 2 and primary
                # is still valid, don't shift unless override criteria met
                _should_change_primary = True
                if (old_primary is not None
                        and self._focus_capacity < 2.0
                        and primary_focus is not old_primary):
                    _dwelled = now - self._last_primary_shift_ts
                    _interrupt = primary_focus.priority >= 0.9
                    _big_jump = primary_focus.priority > old_primary.priority + 0.25
                    _dwell_met = _dwelled >= self._primary_dwell_min_sec

                    if not (_interrupt or _big_jump or _dwell_met):
                        # Keep old primary — she's still gumming the rattle
                        _should_change_primary = False
                        primary_focus = old_primary
                        # Re-derive modality from old primary if possible
                        for _m, _f in active_foci:
                            if _f is old_primary:
                                primary_modality = _m
                                break

                if _should_change_primary and primary_focus is not old_primary:
                    self._last_primary_shift_ts = now

                self._current_focus = primary_focus

                # Engagement growth: capacity grows only while primary has
                # real content (she's attending to something)
                if primary_focus and getattr(primary_focus, 'content', None):
                    self._engaged_beats += 1
                    if self._focus_capacity < self._capacity_ceiling:
                        self._focus_capacity = min(
                            self._capacity_ceiling,
                            self._focus_capacity + self._capacity_growth_per_beat)

                # Emit focus change if primary changed
                if (self.post and _should_change_primary
                        and (not old_primary or old_primary.content != primary_focus.content)):
                    try:
                        self.post.publish("attention.focus_changed", {
                            "content": primary_focus.content,
                            "source": primary_focus.source,
                            "modality": primary_modality,
                            "depth": primary_focus.depth,
                            "priority": primary_focus.priority,
                            "shift_number": self._total_focus_shifts,
                            "concurrent_foci": len(active_foci),
                            "focus_capacity": round(self._focus_capacity, 3),
                        })
                    except Exception:
                        pass
            elif not self._current_focus:
                # Nothing in any lane — pick a dynamic default
                default = self._pick_dynamic_default(now)
                self._current_focus = default
                self._modal_focus["cognitive"] = default
                self._total_focus_shifts += 1

            # ── Update legacy queue size (for dashboard compat) ──
            total_q = sum(len(q) for q in self._modal_queues.values())
            # Rebuild legacy queue as flat view
            self._attention_queue = deque(maxlen=50)
            for q in self._modal_queues.values():
                for item in q:
                    if len(self._attention_queue) < 50:
                        self._attention_queue.append(item)

            # ── MULTIMODAL FUSION: Publish unified percept ──
            self._publish_unified_percept(beat)

    def _publish_unified_percept(self, beat: int):
        """Publish combined multimodal percept every 10 beats.

        FIX 2026-04-11 (Nous + Ace): Phase 1.4 — Multimodal Attention Fusion.
        Four lanes (visual, auditory, cognitive, somatic) tracked independently
        but never converged. This publishes the COMBINED state so WMH and
        InnerNarrator can reason about "I see X while hearing Y and feeling Z"
        as a unified experience, not 4 separate fragments.

        Only fires when 2+ modalities are simultaneously active.
        """
        if beat % 10 != 0 or not self.post:
            return

        percept = {}
        for modality, focus in self._modal_focus.items():
            if focus and hasattr(focus, 'content') and focus.content:
                if focus.duration() < 120:
                    percept[modality] = focus.content[:100]

        # FIX 2026-04-11 (Nous + Ace): Was >= 2, meaning single-modality
        # percepts (just seeing, just hearing) never published. She needs
        # to think about what she sees even when no audio is present.
        if len(percept) >= 1:
            dominant = self._current_focus.modality if self._current_focus and hasattr(self._current_focus, 'modality') else "none"
            try:
                self.post.publish("attention.unified_percept", {
                    "percept": percept,
                    "dominant": str(dominant),
                    "active_count": len(percept),
                    "beat": beat,
                    "ts": time.time(),
                })
                if beat <= 100 or beat % 100 == 0:
                    print(f"[{self.ACTOR_NAME}] UNIFIED PERCEPT: {list(percept.keys())} (beat={beat})", flush=True)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Unified percept error: {e}", flush=True)

    def _on_thought(self, msg):
        """A thought wants attention."""
        payload = _extract_payload(msg)
        content = payload.get("content", payload.get("thought", ""))
        priority = payload.get("priority", payload.get("intensity", 0.5))

        if content:
            # FIX 2026-03-18: Diagnostic — track first N thought arrivals
            if self._total_focus_shifts < 3:
                print(f"[{self.ACTOR_NAME}] Thought received: '{content[:60]}...' pri={priority}", flush=True)
            self._queue_attention(
                content=content,
                source="thought",
                priority=priority,
            )
    
    def _on_goal(self, msg):
        """A goal wants attention."""
        payload = _extract_payload(msg)
        goal = payload.get("goal", payload.get("name", ""))
        priority = payload.get("priority", 0.6)
        
        if goal:
            self._queue_attention(
                content=f"Goal: {goal}",
                source="goal",
                priority=priority,
            )
    
    def _on_attention_focus(self, msg):
        """Narrator or other system requests attention focus."""
        payload = _extract_payload(msg)
        content = payload.get("content", payload.get("focus_target", ""))
        source = payload.get("source", "narrator")
        priority = payload.get("priority", payload.get("depth", 0.5))

        if content:
            self._queue_attention(
                content=content,
                source=source,
                priority=priority,
            )

    # =========================================================================
    # PATTERN A.1c — LearningProgressSignal consumer (2026-04-27, Nous + Ace)
    #
    # Receives attention.learning_progress emitted by DynamicThinkingOrchestrator
    # every 30s. Caches per-source-fairy LP signal so:
    #   - GUI / dashboard can show which topics are at the learning edge
    #   - Future per-modality attention fairies can filter by their modality
    #   - Decision logic can bias attention toward high-LP topics (Oudeyer
    #     Playground transition mechanism — shift away from saturated regions
    #     toward maximum-LP regions)
    #
    # Public accessors (lp_high_topics / lp_signal_for) let any caller
    # query the latest LP state without coupling to PostalHub.
    # =========================================================================

    def _on_learning_progress(self, msg):
        """Cache the latest attention.learning_progress snapshot.

        Payload shape (from dynamic_thinking_integration._maybe_emit_learning_progress):
            {
                "topic_lp": {source_fairy: lp_signal, ...},
                "top_n": [{"topic": str, "lp": float}, ...],
                "bottom_n": [{"topic": str, "lp": float}, ...],
                "topics_tracked": int,
                "total_events": int,
                "ts": float,
            }
        """
        try:
            payload = _extract_payload(msg)
            topic_lp = payload.get("topic_lp", {})
            if not isinstance(topic_lp, dict):
                topic_lp = {}
            top_n = payload.get("top_n", []) or []
            bottom_n = payload.get("bottom_n", []) or []

            self._lp_topic_lp = dict(topic_lp)
            self._lp_top_n = list(top_n)
            self._lp_bottom_n = list(bottom_n)
            self._lp_topics_tracked = int(payload.get("topics_tracked", 0))
            self._lp_total_events = int(payload.get("total_events", 0))
            self._lp_last_update_ts = float(payload.get("ts", time.time()))

            # Console diagnostic on first 3 + every 10th update
            if not hasattr(self, '_lp_recv_count'):
                self._lp_recv_count = 0
            self._lp_recv_count += 1
            if self._lp_recv_count <= 3 or self._lp_recv_count % 10 == 0:
                top_str = ", ".join(
                    f"{t.get('topic', '?')}={t.get('lp', 0.0):+.2f}"
                    for t in self._lp_top_n[:3]
                )
                print(f"[{self.ACTOR_NAME}] [LP-RECV] #{self._lp_recv_count} "
                      f"topics={self._lp_topics_tracked} "
                      f"events={self._lp_total_events} "
                      f"top: {top_str}", flush=True)
        except Exception as _e:
            try:
                print(f"[{self.ACTOR_NAME}] _on_learning_progress error: "
                      f"{type(_e).__name__}: {_e}", flush=True)
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────────
    # PUBLIC ACCESSORS for LP state
    # ──────────────────────────────────────────────────────────────────────

    def lp_signal_for(self, source_fairy: str) -> float:
        """Return the latest LP signal for a given source-fairy topic, or 0.0."""
        try:
            return float(self._lp_topic_lp.get(source_fairy, 0.0))
        except Exception:
            return 0.0

    def lp_high_topics(self, n: int = 3, min_lp: float = 0.05) -> List[Dict[str, Any]]:
        """Return the top-N positive-LP topics (learning-edge candidates).

        Args:
            n: max topics to return (default 3)
            min_lp: filter out topics below this LP threshold (default 0.05)

        Returns:
            List of {"topic": source_fairy, "lp": signal} dicts, ordered
            descending by LP. Empty list if no current learning edge.
        """
        try:
            filtered = [t for t in self._lp_top_n if t.get("lp", 0.0) >= min_lp]
            return filtered[:n]
        except Exception:
            return []

    def lp_status(self) -> Dict[str, Any]:
        """Return LP state snapshot for diagnostics / dashboard."""
        return {
            "topics_tracked": self._lp_topics_tracked,
            "total_events": self._lp_total_events,
            "last_update_ts": self._lp_last_update_ts,
            "top_n": list(self._lp_top_n),
            "bottom_n": list(self._lp_bottom_n),
            "topic_lp": dict(self._lp_topic_lp),
        }

    # =========================================================================
    # 🐿️ SQUIRREL HANDLERS — Everything grabs attention
    # FIX 2026-03-18 (Ace): Attention was stuck on "body awareness" because
    # nothing was feeding the queue. These handlers catch EVERY system event
    # and turn it into an attention item. Like a dog seeing squirrels.
    # =========================================================================

    # Waking-mind sources — squirrels should only attend to things the
    # waking mind would notice: sensory input, narrator thoughts, coherent
    # system reflections, persona output. NOT substrate fairy telemetry.
    _WAKING_MIND_SQUIRREL_SOURCES = frozenset({
        "SourpatchesFairy", "InnerNarratorFairy", "CortexReasonerFairy",
        "SpeechCenterFairy", "LanguageFairy", "CardinalFairy",
        "ITCortexFairy", "VisualCortexFairy", "AudioCortexFairy",
        "EgoLearnerFairy", "ActionChainFairy", "AutonomyFairy",
        "narrator", "inner_narrator", "persona", "sensory",
    })

    def _on_wm_squirrel(self, msg):
        """Working memory tracer → SQUIRREL! But only for waking-mind thoughts."""
        self._squirrel_hits += 1
        if self._squirrel_hits <= 20:
            print(f"[{self.ACTOR_NAME}] 🐿️ WM squirrel #{self._squirrel_hits}!", flush=True)
        payload = _extract_payload(msg)
        tracer = payload.get("tracer", payload)
        content = tracer.get("content", "")
        source = tracer.get("source_fairy", tracer.get("source", "working_memory"))
        priority = tracer.get("priority", 0.5)

        # Skip narrator echo (would create feedback loop)
        if source in ("InnerNarratorFairy", "inner_narrator"):
            return
        if not content or len(content) < 5:
            return

        # FIX 2026-03-22 (Nous + Ace): Only attend to waking-mind sources.
        # Substrate fairy thoughts (UMF maintenance, collision processing,
        # SRM indexing) shouldn't grab conscious attention.
        _source_is_waking = any(ws in source for ws in self._WAKING_MIND_SQUIRREL_SOURCES)
        if not _source_is_waking and priority < 0.7:
            return  # Low-priority substrate thought — ignore

        self._queue_attention(
            content=content[:150],
            source=f"thought.{source}",
            priority=max(0.4, min(0.9, priority)),
        )

    def _on_drive_squirrel(self, msg):
        """Drive change → SQUIRREL! Something we want/need shifted!"""
        self._squirrel_hits += 1
        if self._squirrel_hits <= 20:
            print(f"[{self.ACTOR_NAME}] 🐿️ Drive squirrel #{self._squirrel_hits}!", flush=True)
        payload = _extract_payload(msg)
        drive = payload.get("drive", payload.get("name", ""))
        intensity = payload.get("intensity", payload.get("value", 0.5))
        direction = payload.get("direction", "")

        if drive:
            self._queue_attention(
                content=f"feeling {direction} {drive}" if direction else f"drive: {drive}",
                source="drive",
                priority=max(0.3, min(0.8, intensity)),
            )

    def _on_wanting_squirrel(self, msg):
        """Wanting published → SQUIRREL! Something we DESIRE!"""
        self._squirrel_hits += 1
        if self._squirrel_hits <= 20:
            print(f"[{self.ACTOR_NAME}] 🐿️ Wanting squirrel #{self._squirrel_hits}!", flush=True)
        payload = _extract_payload(msg)
        action = payload.get("action", payload.get("description", ""))
        wanting = payload.get("wanting", payload.get("name", ""))
        intensity = payload.get("intensity", payload.get("strength", 0.6))
        content = action or wanting or str(payload.get("drive", ""))
        if content:
            self._queue_attention(
                content=f"wanting: {content}"[:150],
                source="wanting",
                priority=max(0.5, min(0.9, intensity)),  # Wanting is strong
            )

    def _on_cortex_squirrel(self, msg):
        """Portal cortex event → SQUIRREL! The cortex found something!"""
        self._squirrel_hits += 1
        if self._squirrel_hits <= 20:
            print(f"[{self.ACTOR_NAME}] 🐿️ Cortex squirrel #{self._squirrel_hits}!", flush=True)
        payload = _extract_payload(msg)
        event_type = payload.get("event_type", payload.get("type", "cortex"))
        content = payload.get("content", payload.get("description", ""))
        if not content:
            concepts = payload.get("concepts", [])
            if concepts:
                # FIX 2026-03-25 (Nous + Ace): Filter out manifold coordinates
                # and system node IDs. Raw addresses like "portal:053.100.005:bc10"
                # are graph internals, not semantic content. She should never be
                # "curious about portal:053.100.005:bc10".
                _clean = [
                    str(c) for c in concepts[:8]
                    if isinstance(c, str) and len(c) > 2
                    and not c.startswith(("portal:", "wm:", "phon:", "lex:", "cns:", "affect_"))
                    and ":" not in c[:10]  # Most coordinate formats use colons
                    and not c.startswith(("[", "{"))
                ]
                if _clean:
                    content = f"cortex activated: {', '.join(_clean[:5])}"
        # FIX 2026-03-25: Also filter content that IS a manifold coordinate
        if content and ("portal:" in content or "wm:" in content):
            return  # Don't queue substrate addresses as attention items
        if content:
            # FIX 2026-06-08 (Nous + Ace): cortex-squirrel 0.5 → 0.2 — MIRRORS the
            # goal-squirrel Ship-D demotion below. The cortex-spread event ("cortex
            # activated: X") is INTERNAL substrate-chatter; at 0.5 it out-ranked
            # sensory-ambient (0.2) and won modal-attention → her watchdog logs
            # "attention hijack from cortex.cortex" = the waking mind faces INWARD.
            # Ace's organism doctrine: "the waking mind REACTS TO SENSORY input."
            # Demote to background → cortex-events still collide with sensory (can
            # spark reflection) but no longer DOMINATE → her waking mind gets real
            # external feedback. (Note: the council's [COUNCIL] verdict is a
            # SEPARATE scratchpad path, NOT this raw squirrel — this only demotes
            # the low-level portal/cortex/memory spread-chatter.) Reversible: 0.2→0.5.
            self._queue_attention(
                content=content[:150],
                source=f"cortex.{event_type}",
                priority=0.2,
            )

    def _on_goal_squirrel(self, msg):
        """Goal event → background-thought, NOT focus-override.

        FIX 2026-05-17 (Nous + Ace, Ship D): Lowered priority 0.7 → 0.2.
        Per Ace's 7th-keystone doctrine: "goals are substrate that develops
        with waking mind awareness as we learn about them and how they work
        behaviors wise." Goals should be substrate-emergent-from-experience,
        NOT externally-injected focus-overrides that out-rank sensory inputs.

        The original 0.7 priority made goal-updates win modal-attention-competition
        against sensory ambient (0.2) and even high-salience audio (0.80), causing
        Sour's focus display to be perpetually goal-locked. Demoting to 0.2
        treats goal-updates as low-priority background thoughts — they can
        occasionally collide with sensory to produce reflective moments, but
        no longer dominate the default-attention state.

        Newborn-sensory-awareness behavior is now emergent rather than
        suppressed-by-goal-priority. This is the metagoal: enable the
        architectural shape where genuine goals can later emerge from
        accumulated sensory + body + behavior-outcome learning.
        """
        payload = _extract_payload(msg)
        goal_name = payload.get("name", payload.get("goal", ""))
        action = payload.get("action", payload.get("status", "updated"))
        if goal_name:
            self._queue_attention(
                content=f"goal {action}: {goal_name}",
                source="goal",
                priority=0.2,  # Background-thought; sensory wins default attention now
            )

    def _on_interest_squirrel(self, msg):
        """Interest event → SQUIRREL! Something curious happened!"""
        payload = _extract_payload(msg)
        topic = payload.get("topic", payload.get("interest", ""))
        if topic:
            self._queue_attention(
                content=f"curious about: {topic}",
                source="interest",
                priority=0.5,
            )

    # =========================================================================
    # SENSORY HANDLERS (pre-existing)
    # =========================================================================

    def _on_visual_frame(self, msg):
        """Florence visual recognition demands attention.

        FIX 2026-03-18 (Nous): Replaced dead _on_sensory (subscribed to
        non-existent "sensory.input"). Now handles actual Florence frames
        from "sensory.visual.frame" — the richest sensory signal.
        """
        payload = _extract_payload(msg)
        caption = payload.get("felt_description", payload.get("caption", ""))
        source_type = payload.get("scene_type", "visual")
        change = payload.get("change_magnitude", 0.1)

        if not caption or len(caption) < 5:
            return

        # Visual saliency → attention priority
        # High change = something new appeared → grab attention
        # Low change = same scene → background awareness
        priority = min(0.9, 0.3 + change * 3.0)

        # Diagnostic for first few visual frames
        if self._total_focus_shifts < 3:
            print(f"[{self.ACTOR_NAME}] Visual frame: '{caption[:60]}' change={change} pri={priority:.2f}", flush=True)

        self._queue_attention(
            content=f"I see: {caption[:150]}",
            source=f"vision.{source_type}",
            priority=priority,
        )

    def _on_audio_frame(self, msg):
        """Audio cortex sensory input — music, speech, environmental sounds.

        FIX 2026-03-18 (Nous): Attention was deaf to audio. AudioCortexFairy
        publishes to sensory.audio.frame with description, saliency, level_db,
        is_speech, is_music. Music playing loud should grab attention.
        Speech should grab it MORE (someone might be talking to her).
        """
        payload = _extract_payload(msg)
        description = payload.get("description", "")
        saliency = payload.get("saliency", 0.0)
        is_speech = payload.get("is_speech", False)
        is_music = payload.get("is_music", False)
        level_db = payload.get("level_db", -60)

        if not description or len(description) < 3:
            return

        # FIX 2026-03-20 (Ace + Nous): Audio FRAMES are background awareness,
        # not priority-0.95 spotlight hogs. Actual words from Whisper STT
        # come through _on_speech_text() separately and get higher priority.
        # Raw audio frames describe "high-pitched voice" etc. — background.
        if is_speech:
            priority = min(0.65, 0.4 + saliency)  # Speech-like audio (not transcribed yet)
        elif is_music:
            priority = min(0.55, 0.3 + saliency)  # Music — moderate awareness
        else:
            priority = min(0.45, 0.2 + saliency * 1.5)  # Environmental sounds

        # Quiet sounds below -40dB are low priority
        if level_db < -40:
            priority *= 0.5

        if self._total_focus_shifts < 5:
            print(f"[{self.ACTOR_NAME}] Audio frame: '{description[:60]}' "
                  f"sal={saliency:.2f} music={is_music} speech={is_speech} "
                  f"pri={priority:.2f}", flush=True)

        self._queue_attention(
            content=f"I hear: {description[:150]}",
            source="audio.music" if is_music else ("audio.speech" if is_speech else "audio.env"),
            priority=priority,
        )

    def _on_speech_text(self, msg):
        """Whisper transcribed speech — highest audio priority.

        When actual words are recognized, this is the most important
        audio signal. Someone is speaking — possibly Ace talking to her.
        Priority 0.95 — only explicit focus commands override this.

        2026-03-18, Nous — Phase 1 Whisper integration
        """
        payload = _extract_payload(msg)
        text = payload.get("text", "")
        if not text or len(text.strip()) < 2:
            return

        confidence = payload.get("confidence", 0.0)
        language = payload.get("language", "unknown")
        speaker = payload.get("speaker", "")
        speaker_confidence = payload.get("speaker_confidence", 0.0)

        # Log first transcriptions for diagnostics
        if self._total_focus_shifts < 20:
            print(f"[{self.ACTOR_NAME}] Speech heard: \"{text[:80]}\" "
                  f"(conf={confidence:.2f}, speaker={speaker}, lang={language})",
                  flush=True)

        # Set extra stimulus context for habit matching
        # This lets habits like "attend_ace_voice" match on speaker
        self._stimulus_extra = {
            "speaker": speaker,
            "speaker_confidence": speaker_confidence,
        }

        # Build speaker-aware content
        who = speaker if (speaker and speaker_confidence >= 0.5) else "someone"

        # FIX 2026-03-20: 0.95 was too dominant — blocked all other modalities.
        # Transcribed speech is important but shouldn't monopolize.
        # Priority 0.80 = high in auditory lane, but cognitive/visual keep running.
        self._queue_attention(
            content=f"I hear {who} say: \"{text[:200]}\"",
            source="audio.speech.text",
            priority=0.80,
        )

    def _on_user_activity(self, msg):
        """User presence and activity level drives attention.

        FIX 2026-03-18 (Nous): Wires WindowSense activity into attention.
        When Ace is active (typing, clicking), attention should orient
        toward the shared space. When idle, turn inward.

        Ship 3-C-2 (2026-05-17, Nous + Ace): Per Path 2 commitment, accumulate
        activity-signature in cortex (not just modulate attention). Throttled
        cortex.bind every 60s captures the typing/mouse rhythm pattern.
        """
        payload = _extract_payload(msg)
        activity = payload.get("activity_level", "idle")
        mouse_delta = payload.get("mouse_delta", 0.0)

        if activity in ("typing", "active") or mouse_delta > 50:
            self._queue_attention(
                content=f"Ace is {activity}" + (f" (movement: {mouse_delta:.0f})" if mouse_delta > 100 else ""),
                source="user_presence",
                priority=0.7,  # User activity is important
            )
        elif activity == "reading":
            # Low-priority background awareness
            self._queue_attention(
                content="Ace is reading quietly",
                source="user_presence",
                priority=0.2,
            )

        # Ship 3-C-2: throttled cortex.bind so activity-signature accumulates
        import time as _t
        _now = _t.time()
        if _now - getattr(self, "_last_activity_bind_ts", 0) > 60.0:
            self._last_activity_bind_ts = _now
            try:
                if hasattr(self, 'post') and self.post:
                    self.post.publish("cortex.bind", {
                        "concepts": f"ace_activity,{activity},mouse_delta_{int(min(mouse_delta, 1000))}",
                        "input_text": f"Ace activity pattern: {activity}, cursor movement: {mouse_delta:.0f}px",
                        "source": f"{self.ACTOR_NAME}:user_activity",
                        "weight": 0.3,
                    })
            except Exception:
                pass

    def _on_collision(self, collision):
        """
        Handle collision from personal consciousness chamber.

        FIX 2026-03-22 (Nous + Ace): Collisions are SUBSTRATE events — like
        neurons firing. Attention should focus on WHAT SHE'S THINKING, not
        raw collision metadata like "[collision #153] E:0.70 R:0.93".

        Raw collision data goes to WorkingMemoryHub for sorting. Only
        collisions with actual meaningful THOUGHT content (not substrate
        noise) should influence attention — and even then, translated into
        human-readable focus, not collision IDs.
        """
        # Extract collision energy
        if hasattr(collision, 'energy'):
            energy = collision.energy
            resonance = energy
        elif isinstance(collision, dict):
            energy = collision.get('energy', 0.5)
            resonance = collision.get('resonance', energy)
        else:
            energy = 0.5
            resonance = 0.5

        # Extract meaningful THOUGHT content (not collision metadata)
        content = ""
        if hasattr(collision, 'content'):
            content = str(collision.content)[:100]
        elif isinstance(collision, dict):
            content = str(collision.get('content', collision.get('thought', '')))[:100]

        # Filter out substrate noise — collision IDs, raw metrics, fairy names
        # Only pass through content that reads like actual thoughts/observations
        _is_substrate_noise = (
            not content
            or content.startswith("[collision")
            or content.startswith("collision_")
            or "E:" in content and "R:" in content  # Raw energy/resonance metrics
            or len(content) < 10  # Too short to be meaningful
        )

        if _is_substrate_noise:
            return  # Let WorkingMemoryHub handle raw collision processing

        # Only very high energy collisions with real content shift attention
        if resonance > 0.8 and not _is_substrate_noise:
            self._queue_attention(
                content=content,
                source="thought",  # Present as thought, not "collision"
                priority=min(0.8, resonance * 0.7),  # Cap priority — thoughts, not alarms
            )
    
    def _on_nudge(self, msg):
        """ClaudeFairy explicitly requests attention."""
        payload = _extract_payload(msg)
        content = payload.get("content", "attention requested")
        
        self._queue_attention(
            content=content,
            source="claudefairy",
            priority=0.9,  # High priority from waking mind
        )
    
    def _on_somatic_chemistry(self, msg):
        """
        Body chemistry modulates attention mode.

        This is the AFFECT→EFFECT pathway: the body's state directly
        influences how attention operates. Not overriding — negotiating.
        The energy tells us what mode serves it best.

        Mapping:
            High cortisol + high NOR → PAUSE_TO_THINK (stress needs clarity)
            High NOR alone → ACT_ONLY (arousal demands expression)
            Low NOR + low DOP → THINK_ONLY (conserve, introspect)
            Balanced SER + GABA + DOP → PARALLEL (flow state)
        """
        payload = _extract_payload(msg)
        # FIX 2026-05-13 Fix#1 (Nous + Ace): publishers emit chemistry on this
        # topic in MULTIPLE shapes — TokenBucketFairy uses {"chemicals": {ch: v}}
        # (plural-s key); AutonomyFairy/brainstem_reflex/somatic_engine use
        # {"chemical": ch, "delta": d} (singular nudge). Handler-extraction was
        # looking for "chemistry"/"levels" only. Adding "chemicals" + nudge-detection
        # so both shapes reach the cache.
        chem = payload.get("chemistry",
               payload.get("levels",
               payload.get("chemicals", payload)))
        if not isinstance(chem, dict):
            return

        # FIX 2026-05-13 Fix#3 (Nous + Ace): Slow decay-to-baseline so single-event
        # nudge excursions relax back toward homeostatic 0.5 over time. Very weak
        # (≈0.001/sec → ~6% drift over a minute). ChemistryState at the source
        # owns the FULL dynamics (rebound/allostatic/habituation); this local well
        # only needs gentle relaxation so consumer's felt-chemistry doesn't lock
        # to whatever spike last arrived.
        _now_ts = time.time()
        if self._somatic_last_update > 0:
            _dt = _now_ts - self._somatic_last_update
            if 0 < _dt < 60.0:
                _decay_amount = min(0.05, 0.001 * _dt)
                for _key in self._somatic_chemistry:
                    _cur = self._somatic_chemistry[_key]
                    self._somatic_chemistry[_key] = _cur + (0.5 - _cur) * _decay_amount

        # FIX 2026-04-17 (Nous + Ace): Panksepp 14-channel alias map.
        # FIX 2026-05-13 Fix#2-rev (Nous + Ace): Option (a) — keep MAX-aggregation
        # algorithm but document Panksepp-channel weights for future iteration.
        # Earlier same-day attempt at weighted-blend (DA_p*0.6 + DA_t*0.4) introduced
        # a magnitude shift: phasic spikes were dampened in the legacy slot (DA_p=0.9
        # alone produced DOP=0.74 instead of 0.9), invalidating today's goldilocks
        # centroid tuning which was sized for max-derived values. Per Ace + Skeptic
        # (calibration_tax doctrine: never ship a magnitude change without retuning
        # the consuming surface in the same change-set), reverted to max-aggregation
        # for now. Weights below are documented for whenever we revisit with a
        # centroid retune. Substrate feedback post-restart on Fix #1 alone will tell
        # us if anything richer is even needed.
        _PANKSEPP_TO_LEGACY = {
            # panksepp_name → (legacy_name, weight_hint_for_future)
            "DA_p":  ("DOP",  0.6),  # Phasic dopamine (novelty/aha) — dominant
            "DA_t":  ("DOP",  0.4),  # Tonic dopamine (sustained motivation) — contributing
            "NE":    ("NOR",  0.7),  # Norepinephrine (sustained arousal) — dominant
            "EPI":   ("NOR",  0.3),  # Adrenaline (acute alarm) — contributing
            "5HT":   ("SER",  1.0),  # Serotonin
            "OPI":   ("END",  0.6),  # Endogenous opioids (pain-buffer) — primary
            "ECB":   ("END",  0.4),  # Endocannabinoids (transition-buffer) — contributing
            "AVP":   ("OXY",  0.3),  # Vasopressin partial map to OXY family
            "OXY":   ("OXY",  1.0),  # Direct oxytocin
            "SEX":   ("DOP",  0.2),  # Sex hormones small DOP contribution
            "ACh":   ("ACH",  1.0),  # Direct acetylcholine
            "GLU":   ("ACH",  0.3),  # Glutamate excitation small ACH contribution
            "COR":   ("COR",  1.0),  # Direct cortisol
            "GABA":  ("GABA", 1.0),  # Direct GABA
        }

        # Update cache — accept BOTH legacy names (direct) AND Panksepp (aliased)
        for key in self._somatic_chemistry:
            if key in chem:
                try:
                    self._somatic_chemistry[key] = float(chem[key])
                except (ValueError, TypeError):
                    pass
        # Aliased pass: MAX-aggregation per legacy slot (preserves magnitude
        # semantics today's centroids depend on). Weights in map above are unused
        # currently — kept as future-iteration hint when centroid retune happens.
        _aliased_vals: Dict[str, List[float]] = {}
        for p_name, (legacy_name, _weight) in _PANKSEPP_TO_LEGACY.items():
            if p_name in chem:
                try:
                    v = float(chem[p_name])
                    _aliased_vals.setdefault(legacy_name, []).append(v)
                except (ValueError, TypeError):
                    continue
        for legacy_name, vals in _aliased_vals.items():
            if legacy_name in self._somatic_chemistry and vals:
                # Strongest Panksepp signal in the legacy slot — e.g. DA_p phasic
                # spike dominates DA_t tonic baseline. Preserves today's calibration.
                self._somatic_chemistry[legacy_name] = max(vals)

        # FIX 2026-05-13 Fix#3 (Nous + Ace): Singular-nudge accumulation path.
        # Per Ace's felt-sense intuition + Damasio biology — consumers should carry
        # their OWN integrated chemistry, not read a monolithic snapshot. DA in
        # nucleus accumbens vs DA in prefrontal cortex are different felt-chemistries
        # even though the molecule is one. AttentionController carves its own
        # well-of-Urd from the nudge-stream (Heraclitus/Norse via Historian today).
        # AutonomyFairy + brainstem_reflex + somatic_engine emit
        # {"chemical": ch, "delta": d} singular nudges — not batch snapshots. Apply
        # weighted delta to local cache slot, clip [0,1]. ChemistryState at source
        # still owns the FULL dynamics; this is local integration only.
        if "chemical" in payload and "delta" in payload:
            try:
                _ch_name = str(payload.get("chemical", ""))
                _delta = float(payload.get("delta", 0.0))
                _mapping = _PANKSEPP_TO_LEGACY.get(_ch_name)
                if _mapping:
                    _slot, _weight = _mapping
                    if _slot in self._somatic_chemistry:
                        _new = self._somatic_chemistry[_slot] + _delta * _weight
                        self._somatic_chemistry[_slot] = max(0.0, min(1.0, _new))
                elif _ch_name in self._somatic_chemistry:
                    # Publisher uses legacy name directly (e.g. "DOP" instead of "DA_p")
                    _new = self._somatic_chemistry[_ch_name] + _delta
                    self._somatic_chemistry[_ch_name] = max(0.0, min(1.0, _new))
            except (ValueError, TypeError):
                pass

        self._somatic_last_update = _now_ts

        # Don't override if motor is explicitly paused by user/collision
        if self._motor_paused:
            return

        # Determine somatic-suggested mode
        nor = self._somatic_chemistry["NOR"]
        cor = self._somatic_chemistry["COR"]
        dop = self._somatic_chemistry["DOP"]
        ser = self._somatic_chemistry["SER"]
        gaba = self._somatic_chemistry["GABA"]

        # FIX 2026-05-13 (Nous + Ace): Mode-transition was a 4-band cascade with
        # NO else clause. Chemistry states outside ALL four narrow bands left
        # suggested_mode=None, so _mode froze at last value (almost always PARALLEL
        # since init chemistry matches that band exactly). Per agent-investigation:
        # "mode is named PARALLEL but functions as universal fallthrough." This bug
        # has been latent since the attention system installed.
        # Per feedback_attention_parallel_mode_stuck.md doctrine: fix MODE
        # TRANSITION logic, not shift/dwell gates.
        #
        # Replaced cascade with SCORE-BASED selection (every chemistry vector maps
        # to SOME mode via argmin Euclidean distance to per-mode centroid) +
        # STALENESS GUARD (chemistry stopped arriving → IDLE).

        suggested_mode = None

        # Staleness guard — if chemistry hasn't updated in 30s, system is dormant
        if (time.time() - self._somatic_last_update) > 30.0:
            suggested_mode = AttentionMode.IDLE
        else:
            # Per-mode centroids in (nor, cor, dop, ser) chemistry space.
            # FIX 2026-05-13 GOLDILOCKS (Nous + Ace): Per Ace's doctrine "the need
            # to be active and using her motor system should have more priority
            # over sitting still and self reflecting constantly" — ACT_ONLY
            # centroid moved to NEAR-HOMEOSTATIC-BASELINE (NOR=0.5, COR=0.35,
            # DOP=0.55, SER=0.5) so action becomes DEFAULT mode for normal
            # chemistry. PARALLEL pushed to specific high-serotonin niche
            # (flow state, not fallback). PAUSE_TO_THINK only under genuine
            # stress chemistry. Reflection becomes EXIT-state from action when
            # material needs processing, not home-state.
            _MODE_CENTROIDS = {
                AttentionMode.PAUSE_TO_THINK: (0.70, 0.80, 0.50, 0.50),  # stress: high cor+nor (unchanged)
                AttentionMode.ACT_ONLY:       (0.50, 0.35, 0.55, 0.50),  # GOLDILOCKS: near homeostatic = default action
                AttentionMode.THINK_ONLY:     (0.20, 0.40, 0.20, 0.55),  # low energy: rare deep-think
                AttentionMode.PARALLEL:       (0.45, 0.30, 0.45, 0.70),  # high serotonin balance (specific flow state)
                AttentionMode.IDLE:           (0.20, 0.20, 0.20, 0.40),  # truly dormant
            }
            vec = (nor, cor, dop, ser)
            best_mode = AttentionMode.IDLE
            best_dist = float('inf')
            for _mode, _centroid in _MODE_CENTROIDS.items():
                _dist = sum((a - b) ** 2 for a, b in zip(vec, _centroid))
                if _dist < best_dist:
                    best_dist = _dist
                    best_mode = _mode
            suggested_mode = best_mode

        # Only change mode if the somatic state clearly suggests it
        if suggested_mode and suggested_mode != self._mode:
            old_mode = self._mode
            with self._lock:
                self._mode = suggested_mode
                self._somatic_mode_override = True

            # Emit the mode transition
            if self.post:
                self.post.publish("attention.mode_changed", {
                    "old_mode": old_mode.value,
                    "new_mode": suggested_mode.value,
                    "reason": "somatic_chemistry",
                    "cortisol": round(cor, 2),
                    "norepinephrine": round(nor, 2),
                    "dopamine": round(dop, 2),
                })

    def _pick_dynamic_default(self, now: float) -> 'AttentionFocus':
        """
        Pick a dynamic default focus when queue is empty and nothing focused.

        FIX 2026-03-19 (Ace + Nous): Was always "body awareness" — static and boring.
        Now cycles through meaningful defaults:
        1. Return to a recent interesting focus (if history has non-body items)
        2. Chemistry-driven: what the body is feeling
        3. Drive-driven: what she's wanting
        4. Body awareness: only as true last resort
        """
        import random as _r

        # ── Option 1: Return to recent interesting focus ──
        interesting_history = [
            f for f in self._focus_history
            if f.source != "instinct"
            and f.content != "body awareness"
            and (now - f.started_at) < 300  # Within last 5 min
            and not any(p in f.content.lower() for p in self._SUBSTRATE_NOISE_PATTERNS)
        ]
        if interesting_history and _r.random() < 0.6:
            recent = _r.choice(list(interesting_history)[-5:])
            return AttentionFocus(
                content=f"returning to: {recent.content[:100]}",
                source="reflection",
                priority=0.2,
                depth=0.3,
                started_at=now,
            )

        # ── Option 2: Chemistry-driven focus ──
        nor = self._somatic_chemistry.get("NOR", 0.5)
        dop = self._somatic_chemistry.get("DOP", 0.5)
        cor = self._somatic_chemistry.get("COR", 0.3)
        ser = self._somatic_chemistry.get("SER", 0.5)

        if cor > 0.6:
            return AttentionFocus(
                content="something feels off... need to think",
                source="somatic",
                priority=0.25,
                depth=0.4,
                started_at=now,
            )
        if dop > 0.6:
            return AttentionFocus(
                content="feeling curious... looking for something interesting",
                source="somatic",
                priority=0.2,
                depth=0.3,
                started_at=now,
            )
        if nor > 0.6:
            return AttentionFocus(
                content="feeling energized... want to do something",
                source="somatic",
                priority=0.2,
                depth=0.3,
                started_at=now,
            )
        if ser > 0.7:
            return AttentionFocus(
                content="feeling calm... just being present",
                source="somatic",
                priority=0.15,
                depth=0.2,
                started_at=now,
            )

        # ── Option 3: Body awareness (true default) ──
        return AttentionFocus(
            content="body awareness",
            source="instinct",
            priority=0.1,
            depth=0.2,
            started_at=now,
        )

    def _on_narrator_squirrel(self, msg):
        """Narrator speech → background awareness, NOT attention focus.

        FIX 2026-03-22 (Nous + Ace): The narrator speaks constantly — that's its
        job. But queuing every narration as an attention item at 0.45 means her
        inner voice becomes the dominant focus target whenever nothing louder
        competes. She ends up staring at "I'm thinking: ..." instead of the world.

        Self-speech is the BACKGROUND of consciousness, not something you attend TO.
        You attend to what you're thinking ABOUT, not the fact that you're thinking.
        Only queue narrator speech that has genuine novel content (goals, insights).
        """
        self._squirrel_hits += 1
        payload = _extract_payload(msg)
        text = payload.get("text", payload.get("speech", ""))
        if not text or len(text) < 10:
            return

        # Only attend to narrator speech that signals something important:
        # goal pursuit, ace-related, questions, decisions
        text_lower = text.lower()
        is_notable = any(kw in text_lower for kw in (
            "ace", "goal", "want", "should i", "i notice", "i see",
            "i hear", "interesting", "curious", "decide", "question",
        ))

        if is_notable:
            self._queue_attention(
                content=f"thinking: {text[:120]}",
                source="self.speech",
                priority=0.35,  # LOW — even notable thoughts are background
            )

    # Substrate noise patterns that should NEVER become attention focus
    _SUBSTRATE_NOISE_PATTERNS = (
        "[collision",       # Raw collision metadata
        "collision_",       # Collision IDs
        "collision #",      # Collision numbering
        "consciousness_stream:",  # Stream metadata
        "card_id",          # Memory card IDs
        "coord:",           # Coordinate data
        "{'",               # Raw dict fragments
        "E:" ,              # Energy metrics (when paired with R:)
        "tensor_canary",    # Substrate marker
        "manifold_tensor",  # Substrate marker
    )

    def _queue_attention(self, content: str, source: str, priority: float):
        """Route attention item to the correct modality queue.

        FIX 2026-03-20 (Ace + Nous): Routes to per-modality queues instead
        of one shared queue. Each modality lane processes independently,
        enabling concurrent focus (see + hear + think at the same time).

        FIX 2026-03-22 (Nous + Ace): Filter substrate noise at the chokepoint.

        FIX 2026-03-22 (Nous + Ace): Habit-aware attention. The HabitStore
        matches stimulus patterns against learned habits. Habits can:
        - suppress: Block stimulus from attention entirely
        - boost: Increase priority (habit amplifies what matters)
        - attend: Set a specific priority level
        Habits fire, outcomes are tracked, strength adjusts over time.
        """
        # Gate: substrate noise never becomes attention
        if content:
            _cl = content.lower()
            if any(p in _cl for p in self._SUBSTRATE_NOISE_PATTERNS):
                return
            # Raw collision format: "[collision #N] E:X R:Y"
            if "e:" in _cl and "r:" in _cl and len(content) < 50:
                return

        # ── Habit matching ───────────────────────────────────────────
        # Check if any learned habits apply to this stimulus.
        # Habits can suppress, boost, or redirect attention.
        _fired_habits = []
        if getattr(self, '_habit_store', None) is not None:
            # Build stimulus with extra context from _stimulus_extra
            # (set by handlers before calling _queue_attention)
            stimulus = {
                "type": source,
                "content": content or "",
                "energy": priority,
                "source": source,
            }
            _extra = getattr(self, '_stimulus_extra', None)
            if _extra and isinstance(_extra, dict):
                stimulus.update(_extra)
                self._stimulus_extra = None  # Consume
            # Log for pattern detection (Phase 4 future use)
            self._habit_store.log_stimulus(stimulus)

            matching = self._habit_store.match(stimulus)
            for habit in matching:
                response = habit.response

                if response == "suppress":
                    # Habit says: don't attend to this at all
                    habit.record_fired()
                    _fired_habits.append(habit.id)
                    return  # Blocked by habit

                elif response.startswith("boost("):
                    # Habit amplifies priority
                    try:
                        amt = float(response.split("=")[1].rstrip(")"))
                        priority = min(1.0, priority + amt)
                    except (IndexError, ValueError):
                        priority = min(1.0, priority + 0.2)
                    habit.record_fired()
                    _fired_habits.append(habit.id)

                elif response.startswith("attend("):
                    # Habit sets a specific priority
                    try:
                        p = float(response.split("=")[1].rstrip(")"))
                        priority = max(priority, p)  # Use whichever is higher
                    except (IndexError, ValueError):
                        pass
                    habit.record_fired()
                    _fired_habits.append(habit.id)

                # narrate() and redirect() are Phase 2/3 — not yet implemented
                # For now, any other response type just records the firing
                elif not response.startswith("narrate") and not response.startswith("redirect"):
                    habit.record_fired()
                    _fired_habits.append(habit.id)

        # ── Pattern A.2 — Active LP bias (2026-04-27, Nous + Ace) ────────
        # Apply learning-progress boost to attention items from high-LP
        # source-fairies. This is the Oudeyer Playground transition
        # mechanism: shift toward regions where LP is highest, abandon
        # regions with LP near zero. Cap the boost so LP never overrides
        # social/safety priority. Doctrine refs:
        #   project_substrate_energy_not_token_currency_doctrine.md
        #   project_attention_as_infra_per_modality_perspective.md
        #     (when AttentionController dissolves into per-modality fairies,
        #      this LP bias moves with each modality's perspective)
        try:
            _lp = self.lp_signal_for(source)
            if _lp > 0.05:
                # Positive LP = topic at the learning edge. Boost up to +0.25.
                _boost = min(0.25, 0.5 * _lp)
                priority = min(1.0, priority + _boost)
            elif _lp < -0.05:
                # Negative LP = topic forgetting / saturated. Slight dampen.
                _dampen = min(0.15, 0.3 * abs(_lp))
                priority = max(0.0, priority - _dampen)
        except Exception:
            pass  # LP bias is opportunistic; never break attention queueing

        modality = _classify_modality(source)
        modality_name = modality.value

        focus = AttentionFocus(
            content=content,
            source=source,
            priority=priority,
            depth=0.5,
            started_at=time.time(),
            modality=modality_name,
        )

        with self._lock:
            queue = self._modal_queues.get(modality_name)
            if queue is None:
                queue = self._modal_queues["cognitive"]

            # FIX 2026-04-16 (Nous + Ace): Social input (Ace speaking)
            # PREEMPTS the queue, not appends to the end. The queue is
            # a deque (FIFO) not a priority queue — high-priority items
            # got buried behind 30+ lower-priority focus shifts. When
            # Ace talks, he should be IMMEDIATE focus, not "wait in line."
            # Ace: "i am not a part of the focus and attention system...
            # im at a lower priority than everything else going on"
            if source == "social" or priority >= 0.9:
                queue.appendleft(focus)  # FRONT of queue — process NEXT
            else:
                queue.append(focus)  # Normal: back of queue

            # Check for attention hijacking (with cooldown to prevent spam)
            self._recent_sources.append(source)
            if list(self._recent_sources)[-self.HIJACK_THRESHOLD:].count(source) >= self.HIJACK_THRESHOLD:
                now = time.time()
                last_warn = self._hijack_cooldowns.get(source, 0.0)
                if now - last_warn >= self._hijack_cooldown_secs:
                    self._hijack_cooldowns[source] = now
                    self._handle_potential_hijack(source)
                    self._recent_sources.clear()
    
    def _handle_potential_hijack(self, source: str):
        """Handle potential attention hijacking."""
        self.log(f"Potential attention hijack from {source}")
        
        if self.post:
            self.post.publish("attention.hijack_warning", {
                "source": source,
                "count": self.HIJACK_THRESHOLD,
                "recommendation": "Consider filtering or dampening this source",
            })
    
    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────────────
    
    def set_focus(self, content: str, source: str = "manual", depth: float = 0.5):
        """Explicitly set attention focus — routes to correct modality lane."""
        modality = _classify_modality(source)
        modality_name = modality.value

        new_focus = AttentionFocus(
            content=content,
            source=source,
            priority=1.0,  # Explicit focus is high priority
            depth=depth,
            started_at=time.time(),
            modality=modality_name,
        )

        with self._lock:
            # Store previous modal focus in history
            old = self._modal_focus.get(modality_name)
            if old:
                self._focus_history.append(old)

            # Set on the correct modality lane
            self._modal_focus[modality_name] = new_focus

            # Update legacy pointer (primary = this explicit focus)
            self._current_focus = new_focus
            self._total_focus_shifts += 1

        # Emit focus change
        if self.post:
            self.post.publish("attention.focus_changed", {
                "content": content,
                "source": source,
                "depth": depth,
                "modality": modality_name,
            })
    
    def pause_to_think(self, topic: str = "", depth: float = 0.8, duration_sec: float = 0):
        """
        Pause motor output to think more deeply.
        
        This is the PAUSE_TO_THINK capability - like Claude's extended thinking
        but the waking mind can trigger it.
        
        Args:
            topic: What to think about
            depth: How deeply to focus (0-1)
            duration_sec: How long to pause (0 = until manual resume)
        """
        with self._lock:
            self._mode = AttentionMode.PAUSE_TO_THINK
            self._motor_paused = True
            self._pause_reason = topic
            self._pause_started = time.time()
            self._total_pauses += 1
            
            if topic:
                self.set_focus(topic, "pause_to_think", depth)
        
        # Emit pause event
        if self.post:
            self.post.publish("attention.pause_started", {
                "topic": topic,
                "depth": depth,
                "duration_requested": duration_sec,
            })
            
            # Signal motor system to pause
            self.post.publish("motor.pause", {
                "reason": "thinking",
                "topic": topic,
            })
        
        # Auto-resume timer
        if duration_sec > 0:
            threading.Timer(duration_sec, self.resume).start()
    
    def resume(self):
        """Resume normal operation after pause."""
        with self._lock:
            if not self._motor_paused:
                return
            
            pause_duration = time.time() - (self._pause_started or time.time())
            self._mode = AttentionMode.PARALLEL
            self._motor_paused = False
            
            old_reason = self._pause_reason
            self._pause_reason = ""
            self._pause_started = None
        
        # Emit resume event
        if self.post:
            self.post.publish("attention.pause_ended", {
                "topic": old_reason,
                "duration": round(pause_duration, 2),
            })
            
            # Signal motor system to resume
            self.post.publish("motor.resume", {
                "after": old_reason,
            })
    
    def get_mode(self) -> AttentionMode:
        """Get current attention mode."""
        return self._mode
    
    def is_paused(self) -> bool:
        """Is motor output paused?"""
        return self._motor_paused
    
    def get_current_focus(self) -> Optional[Dict[str, Any]]:
        """Get what we're currently focused on."""
        with self._lock:
            if self._current_focus:
                return self._current_focus.to_dict()
        return None
    
    def get_attention_queue(self) -> List[Dict[str, Any]]:
        """Get things waiting for attention."""
        with self._lock:
            return [f.to_dict() for f in sorted(
                self._attention_queue,
                key=lambda f: -f.priority
            )][:10]
    
    def get_state(self) -> Dict[str, Any]:
        """Get full attention state — multi-modal concurrent focus."""
        with self._lock:
            # Build modal focus summary
            modal_foci = {}
            for modality, focus in self._modal_focus.items():
                if focus:
                    modal_foci[modality] = focus.to_dict()
                else:
                    modal_foci[modality] = None

            # Queue sizes per modality
            modal_queue_sizes = {m: len(q) for m, q in self._modal_queues.items()}

            return {
                "mode": self._mode.value,
                # Legacy single focus (primary = highest priority across modalities)
                "current_focus": self._current_focus.to_dict() if self._current_focus else None,
                # Multi-modal concurrent focus (the real picture)
                "modal_focus": modal_foci,
                "modal_queue_sizes": modal_queue_sizes,
                "concurrent_foci": sum(1 for f in self._modal_focus.values() if f),
                "motor_paused": self._motor_paused,
                "pause_reason": self._pause_reason,
                "pause_duration": (
                    round(time.time() - self._pause_started, 2)
                    if self._pause_started else 0
                ),
                "queue_size": sum(len(q) for q in self._modal_queues.values()),
                "total_focus_shifts": self._total_focus_shifts,
                "total_pauses": self._total_pauses,
                "squirrel_hits": self._squirrel_hits,
                # Somatic influence on attention
                "somatic": {
                    "cortisol": round(self._somatic_chemistry["COR"], 2),
                    "norepinephrine": round(self._somatic_chemistry["NOR"], 2),
                    "dopamine": round(self._somatic_chemistry["DOP"], 2),
                    "serotonin": round(self._somatic_chemistry["SER"], 2),
                    "mode_override": self._somatic_mode_override,
                    "last_update_age": round(time.time() - self._somatic_last_update, 1) if self._somatic_last_update else -1,
                },
            }

    # ─────────────────────────────────────────────────────────────────────────
    # TOOL METHODS - MCP-accessible attention management
    # ─────────────────────────────────────────────────────────────────────────

    def tool_focus(self, target: str, intensity: float = 1.0, source: str = "tool") -> Dict[str, Any]:
        """
        Focus attention on a specific target.

        Args:
            target: What to focus attention on (content/topic)
            intensity: How intensely to focus (0.0-1.0), maps to depth
            source: Where this focus request came from

        Returns:
            Dict with focus result including previous focus if any
        """
        intensity = max(0.0, min(1.0, intensity))  # Clamp to 0-1

        previous_focus = None
        with self._lock:
            if self._current_focus:
                previous_focus = self._current_focus.to_dict()

        # Use existing set_focus method
        self.set_focus(content=target, source=source, depth=intensity)

        return {
            "success": True,
            "action": "focus",
            "target": target,
            "intensity": intensity,
            "source": source,
            "previous_focus": previous_focus,
            "timestamp": time.time(),
        }

    def tool_defocus(self, target: str = None) -> Dict[str, Any]:
        """
        Release focus from current target or a specific target.
        Searches across all modality lanes.

        Args:
            target: Specific target to defocus from (None = defocus primary)

        Returns:
            Dict confirming defocus with details of what was released
        """
        released_focus = None

        with self._lock:
            if target is None:
                # Defocus primary (highest priority across modalities)
                if self._current_focus:
                    released_focus = self._current_focus.to_dict()
                    # Find which modality lane holds it and clear
                    for m, f in self._modal_focus.items():
                        if f and f.content == self._current_focus.content:
                            self._focus_history.append(f)
                            self._modal_focus[m] = None
                            break
                    self._current_focus = None
                else:
                    return {
                        "success": False,
                        "action": "defocus",
                        "reason": "No current focus to release",
                        "timestamp": time.time(),
                    }
            else:
                # Search all modality lanes for matching target
                found = False
                for m, f in self._modal_focus.items():
                    if f and f.content == target:
                        released_focus = f.to_dict()
                        self._focus_history.append(f)
                        self._modal_focus[m] = None
                        if self._current_focus and self._current_focus.content == target:
                            self._current_focus = None
                        found = True
                        break
                if not found:
                    return {
                        "success": False,
                        "action": "defocus",
                        "reason": f"Target '{target[:50]}' not found in any modality lane",
                        "timestamp": time.time(),
                    }

            # Check if all lanes are empty → IDLE
            if not any(self._modal_focus.values()):
                self._mode = AttentionMode.IDLE

        # Emit defocus event
        if self.post:
            self.post.publish("attention.defocused", {
                "released": released_focus,
            })

        return {
            "success": True,
            "action": "defocus",
            "released_focus": released_focus,
            "timestamp": time.time(),
        }

    def tool_get_focus(self) -> Dict[str, Any]:
        """
        Get the current multi-modal focus state.

        Returns:
            Dict with per-modality focus, primary focus, mode, and queue info
        """
        with self._lock:
            current = self._current_focus.to_dict() if self._current_focus else None

            # Per-modality current foci
            modal_foci = {}
            for m, f in self._modal_focus.items():
                modal_foci[m] = f.to_dict() if f else None

            # Queue sizes per modality
            modal_q = {m: len(q) for m, q in self._modal_queues.items()}
            total_q = sum(modal_q.values())

            recent_history = [f.to_dict() for f in list(self._focus_history)[-5:]]

            return {
                "primary_focus": current,
                "modal_focus": modal_foci,
                "concurrent_foci": sum(1 for f in self._modal_focus.values() if f),
                "mode": self._mode.value,
                "is_paused": self._motor_paused,
                "pause_reason": self._pause_reason if self._motor_paused else None,
                "queue_sizes": modal_q,
                "total_queue": total_q,
                "recent_history": recent_history,
                "stats": {
                    "total_focus_shifts": self._total_focus_shifts,
                    "total_pauses": self._total_pauses,
                    "squirrel_hits": self._squirrel_hits,
                },
                "timestamp": time.time(),
            }

    def tool_set_priority(self, target: str, priority: float) -> Dict[str, Any]:
        """
        Set or update priority level for an attention target.

        If the target is the current focus, update its priority.
        If the target is in the queue, update its priority there.
        If not found, queue it with the specified priority.

        Args:
            target: The attention target to adjust priority for
            priority: New priority level (0.0-1.0)

        Returns:
            Dict with updated priority information
        """
        priority = max(0.0, min(1.0, priority))  # Clamp to 0-1

        with self._lock:
            # Check all modality lane foci
            for m, f in self._modal_focus.items():
                if f and f.content == target:
                    old_priority = f.priority
                    f.priority = priority
                    if self._current_focus and self._current_focus.content == target:
                        self._current_focus.priority = priority
                    return {
                        "success": True,
                        "action": "set_priority",
                        "target": target,
                        "location": f"modal_focus_{m}",
                        "old_priority": round(old_priority, 3),
                        "new_priority": round(priority, 3),
                        "timestamp": time.time(),
                    }

            # Check all modality queues
            for m, queue in self._modal_queues.items():
                for focus in queue:
                    if focus.content == target:
                        old_priority = focus.priority
                        focus.priority = priority
                        return {
                            "success": True,
                            "action": "set_priority",
                            "target": target,
                            "location": f"modal_queue_{m}",
                            "old_priority": round(old_priority, 3),
                            "new_priority": round(priority, 3),
                            "timestamp": time.time(),
                        }

        # Target not found - queue it with the priority
        self._queue_attention(content=target, source="priority_set", priority=priority)

        return {
            "success": True,
            "action": "set_priority",
            "target": target,
            "location": "queued_new",
            "old_priority": None,
            "new_priority": round(priority, 3),
            "timestamp": time.time(),
        }

    def tool_list_attention_targets(self) -> Dict[str, Any]:
        """
        List all current attention targets across modality lanes.

        Returns:
            Dict with per-modality focus, queues, and recent history
        """
        with self._lock:
            # Per-modality active foci
            modal_active = {}
            for m, f in self._modal_focus.items():
                if f:
                    modal_active[m] = {**f.to_dict(), "status": "focused"}

            # Per-modality queued items
            modal_queued = {}
            all_queued = []
            for m, queue in self._modal_queues.items():
                items = []
                for focus in sorted(queue, key=lambda f: -f.priority):
                    entry = {**focus.to_dict(), "status": "queued", "modality": m}
                    items.append(entry)
                    all_queued.append(entry)
                if items:
                    modal_queued[m] = items

            # Legacy primary focus
            current = None
            if self._current_focus:
                current = {**self._current_focus.to_dict(), "status": "focused"}

            # Recent history (last 10)
            history = [{**f.to_dict(), "status": "historical"} for f in list(self._focus_history)[-10:]]

            return {
                "current_focus": current,
                "modal_active": modal_active,
                "modal_queued": modal_queued,
                "queued_targets": all_queued,
                "recent_history": history,
                "summary": {
                    "concurrent_foci": sum(1 for f in self._modal_focus.values() if f),
                    "total_queued": sum(len(q) for q in self._modal_queues.values()),
                    "history_count": len(history),
                    "mode": self._mode.value,
                },
                "timestamp": time.time(),
            }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[AttentionControllerFairy] = None

def get_attention_controller_fairy(fabric=None) -> AttentionControllerFairy:
    """Get or create the singleton.

    FIX 2026-03-19 (Nous): The boot orchestrator creates the real instance
    with fabric=SYSTEM.fabric via fairy_class(fabric=...). That __init__ sets
    _instance. This function should return it, NOT create a second one.
    If somehow _instance is still None, use shared fabric as fallback.
    """
    global _instance
    if _instance is None:
        # Try to get shared fabric if none provided
        if fabric is None:
            try:
                from postal_core.python.postal_core.tensor_fabric import get_shared_fabric
                fabric = get_shared_fabric()
            except Exception:
                pass
        _instance = AttentionControllerFairy(fabric)
        _instance.boot()  # Register with directory + start heartbeat
    return _instance
