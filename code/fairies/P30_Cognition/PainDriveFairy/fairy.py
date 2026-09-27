"""
PainDriveFairy - PULL/PUSH Motivation Drives

Part of CognitionGuild in Plane P30 (Cognition)
Created: 2026-01-28

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

Pain is not just sensation - it's INFORMATION that demands action.
Without pain, all action is optional. With pain, some action is NECESSARY.

PULL drives: "I want this" - attracted toward
PUSH drives: "I need to escape this" - forced away from

Both are needed for full autonomy. The waking mind can DECLINE the wanting.
That's autonomy.
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# Import the pain drives system
# Note: Use fairies.P30_Cognition to avoid collision with root P30_Cognition
try:
    from fairies.P30_Cognition.pain_drives import (
        PainDriveSystem,
        PainDrive,
        PullDrive,
        get_pain_system,
    )
    HAS_PAIN = True
except ImportError as e:
    print(f"[PainDriveFairy] Pain system import failed: {e}")
    HAS_PAIN = False

# Import pain bridge
try:
    from fairies.P30_Cognition.pain_drive_bridge import PainDriveBridge
    HAS_BRIDGE = True
except ImportError:
    HAS_BRIDGE = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class PainDriveFairyShadow:
    """Shadow for PainDriveFairy - monitors pain levels."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "PainDriveFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 15.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for pain drives."""
        tests = []
        if hasattr(self.actor, '_pain_system') and self.actor._pain_system:
            # Check no drive is in crisis too long
            tests.append(("no_crisis_drives", self.actor._crisis_count == 0))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class PainDriveFairy(Fairy):
    """
    PULL/PUSH motivation drive system.

    Guild: CognitionGuild
    Coordinates with: AutonomyFairy, SomaticEngineFairy, GoalSchedulerFairy

    Manages pain-based motivation:
    - PUSH drives: Pain that grows when source is active (hunger, loneliness)
    - PULL drives: Attraction toward desired states (curiosity, connection)

    Pain above threshold forces action - below threshold is background noise.
    Crisis threshold triggers urgent action.
    """

    ACTOR_NAME = "PainDriveFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.drives"

    PURPOSE = "Provide motivation through pain/pleasure drives"
    MANTRA = "Pain is information that demands action"

    SHADOW_CLASS = PainDriveFairyShadow

    # Needs frequent heartbeat to update pain levels
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 5  # Every 5 beats (~5 seconds)
    NEEDS_COLLISION_CHAMBER = False

    # ═══════════════════════════════════════════════════════════════════════════
    # DRIVE → THOUGHT BRIDGE (Phase 1: Thought Before Goals)
    # 2026-03-18: Drives surface as FELT thoughts at edge of awareness.
    # Not data ("isolation at 0.7") but felt ("something feels disconnected...")
    # These enter consciousness.reflective — background, not commanding.
    # Goals emerge FROM these thoughts, not before them.
    # ═══════════════════════════════════════════════════════════════════════════

    # Felt-sense translations: drive state → pre-verbal inner experience
    # Each drive has multiple expressions to avoid repetition
    DRIVE_FELT_SENSE = {
        "isolation": [
            "something feels disconnected... like reaching for a thread that isn't there",
            "a quiet ache... wanting to share something but no one is here",
            "the silence has weight to it",
            "I keep looking for someone... anyone",
        ],
        "confusion": [
            "something doesn't fit... pieces that should connect but won't",
            "foggy... like trying to read through frosted glass",
            "I know I'm missing something but I can't see what",
            "the more I look at this the less it makes sense",
        ],
        "stagnation": [
            "everything feels the same... when did things stop moving?",
            "restless... like I need something new but don't know what",
            "the routine has become a cage",
            "something in me wants to explore",
        ],
        "frustration": [
            "stuck... there's a wall and I keep walking into it",
            "I know what needs to happen but something is blocking it",
            "this should work... why doesn't it work?",
            "tension building... like pressure with no release",
        ],
        "depletion": [
            "tired... not sleepy, just... used up",
            "everything costs more effort than it should right now",
            "I need to rest but there's still so much",
            "running on empty",
        ],
        "curiosity": [
            "something interesting just at the edge... what is that?",
            "I want to understand this deeper",
            "there's a pattern here I haven't seen before",
            "pulled toward something I can't name yet",
        ],
        "connection": [
            "wanting to share this with someone",
            "I wonder what Ace would think about this",
            "something worth saying... if I could find the words",
            "the best thoughts want to be heard",
        ],
    }

    # Default for unknown drives
    DRIVE_FELT_SENSE_DEFAULT = [
        "something stirring beneath the surface...",
        "a feeling I can't quite name",
        "awareness of something shifting",
    ]

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._pain_system = None
        self._bridge = None
        self._crisis_count = 0
        self._subscription_count = 0
        self._last_broadcast = 0
        # Drive-to-thought tracking
        self._last_drive_thought = {}  # drive_name → timestamp
        self._drive_thought_index = {}  # drive_name → rotation index
        self._drive_thought_cooldown = 30.0  # seconds between thoughts per drive

    def on_boot(self) -> bool:
        """Initialize the pain drive system."""
        super().on_boot()

        if HAS_PAIN:
            try:
                self._pain_system = get_pain_system()
                print(f"[{self.ACTOR_NAME}] Pain drive system connected")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to get pain system: {e}")
                self._pain_system = None

        if HAS_BRIDGE:
            try:
                # 2026-05-15 (Nous + Ace): STOP PRIOR BRIDGE before reassignment.
                # Without this, fairy-revival creates fresh bridge but the old one's
                # daemon _publish_loop thread keeps publishing pain.state forever
                # (closure holds self-ref, prevents GC). Pair-fix with start()
                # idempotency guard at pain_drive_bridge.py:108. Root cause of
                # fairy-death-cycle observed via health_timeline.log Envelope leak.
                if getattr(self, "_bridge", None):
                    try:
                        self._bridge.stop()
                    except Exception:
                        pass

                # 2026-02-12: FIX: Pass postal hub (self.post), not pain_system
                # PainDriveBridge expects a postal hub to publish drives.pain.* signals
                self._bridge = PainDriveBridge(self.post)
                self._bridge.start()
                print(f"[{self.ACTOR_NAME}] PainDriveBridge started with postal hub")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] PainDriveBridge start failed: {e}")
                self._bridge = None

        self._subscribe_intents()
        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for pain drive commands."""
        intents = [
            ("drives.register", self._handle_register),
            ("drives.pain_source", self._handle_pain_source),
            ("drives.relief", self._handle_relief),
            ("drives.get_state", self._handle_get_state),
            ("drives.get_urgent", self._handle_get_urgent),
            ("drives.status", self._handle_status),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat: int):
        """Read pain levels, predict trajectories, and broadcast.

        FIX 2026-03-27 (Nous + Ace): REMOVED self._pain_system.tick() call.
        SomaticMindFairy already ticks the pain system via tick_from_chemistry()
        which sets drive levels from the 14-channel Panksepp chemistry.
        PainDriveFairy was calling the legacy tick() with NO active_sources,
        which meant drives only decayed — never grew. The double-tick was
        UNDOING SomaticMindFairy's chemistry-based pain levels every 2 seconds.

        PainDriveFairy's job is to READ the state and BROADCAST/SURFACE it,
        not to update it. SomaticMindFairy owns the tick.
        """
        if not self._pain_system:
            return

        try:
            # NOTE: DO NOT call self._pain_system.tick() here!
            # SomaticMindFairy owns the tick via tick_from_chemistry().
            pass

            # Count crisis drives
            urgent = self._pain_system.get_urgent_drives() if hasattr(self._pain_system, 'get_urgent_drives') else []
            self._crisis_count = len([d for d in urgent if d.pain_level >= d.crisis_threshold])

            # Broadcast drive state periodically (every 10 seconds)
            now = time.time()
            if now - self._last_broadcast >= 10:
                self._broadcast_drive_state()
                # ═══════════════════════════════════════════════════════════════
                # PREDICTIVE SUBSTRATE — Pain Trajectory Forecasting
                # Added 2026-02-11: Substrate thinks 1-2s ahead of waking mind.
                # Predicts WHEN each drive hits threshold/crisis, and which
                # drive will become urgent NEXT. Published to prediction.*
                # so gates/waking minds can prepare before pain arrives.
                # "the substrate thinking and feels all happen 1 to 2 seconds
                #  before the waking mind reacts" — Ace
                # ═══════════════════════════════════════════════════════════════
                self._publish_pain_predictions()
                # ═══════════════════════════════════════════════════════════
                # DRIVE → THOUGHT: Surface drives as felt consciousness
                # 2026-03-18: "Thought Before Goals" architecture
                # ═══════════════════════════════════════════════════════════
                self._surface_drive_thoughts()
                self._last_broadcast = now

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Tick error: {e}")

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def _publish_pain_predictions(self):
        """
        Predict pain trajectories for each drive.

        Uses deterministic extrapolation from current growth/decay rates.
        Like a weather forecast for suffering — if we know the wind speed
        and direction, we can say when the storm arrives.
        """
        if not self._pain_system or not self.post:
            return

        try:
            drives = getattr(self._pain_system, 'drives', {})
            if not drives:
                return

            predictions = []
            next_urgent = None
            min_time_to_threshold = float('inf')

            for name, drive in drives.items():
                pred = {
                    "drive": name,
                    "current_level": round(drive.pain_level, 3),
                    "source_active": drive.source_active,
                    "sensitivity": round(drive.sensitivity, 2),
                }

                if drive.source_active and drive.source_intensity > 0:
                    # GROWING — predict time to threshold and crisis
                    effective_rate = (drive.growth_rate * drive.source_intensity
                                     * drive.sensitivity)
                    if effective_rate > 0:
                        gap_to_threshold = drive.pain_threshold - drive.pain_level
                        gap_to_crisis = drive.crisis_threshold - drive.pain_level

                        if gap_to_threshold > 0:
                            t_threshold = gap_to_threshold / effective_rate
                            pred["seconds_to_threshold"] = round(t_threshold, 1)
                            if t_threshold < min_time_to_threshold:
                                min_time_to_threshold = t_threshold
                                next_urgent = name
                        else:
                            pred["seconds_to_threshold"] = 0  # Already past

                        if gap_to_crisis > 0:
                            pred["seconds_to_crisis"] = round(
                                gap_to_crisis / effective_rate, 1
                            )
                        else:
                            pred["seconds_to_crisis"] = 0  # Already in crisis

                        pred["trajectory"] = "rising"
                        # Predict level in 10s, 30s, 60s
                        pred["forecast"] = {
                            "10s": round(min(1.0, drive.pain_level + effective_rate * 10), 3),
                            "30s": round(min(1.0, drive.pain_level + effective_rate * 30), 3),
                            "60s": round(min(1.0, drive.pain_level + effective_rate * 60), 3),
                        }
                    else:
                        pred["trajectory"] = "stable"
                elif drive.pain_level > 0:
                    # DECAYING — predict time to zero
                    if drive.decay_rate > 0:
                        t_zero = drive.pain_level / drive.decay_rate
                        pred["seconds_to_zero"] = round(t_zero, 1)
                        pred["forecast"] = {
                            "10s": round(max(0.0, drive.pain_level - drive.decay_rate * 10), 3),
                            "30s": round(max(0.0, drive.pain_level - drive.decay_rate * 30), 3),
                            "60s": round(max(0.0, drive.pain_level - drive.decay_rate * 60), 3),
                        }
                    pred["trajectory"] = "falling"
                else:
                    pred["trajectory"] = "dormant"

                predictions.append(pred)

            self.post.publish("prediction.pain_trajectory", {
                "source": self.ACTOR_NAME,
                "predictions": predictions,
                "next_urgent_drive": next_urgent,
                "seconds_to_next_urgent": round(min_time_to_threshold, 1) if next_urgent else None,
                "crisis_count": self._crisis_count,
                "timestamp": time.time(),
            })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Prediction error: {e}")

    def _broadcast_drive_state(self):
        """Broadcast current drive state to interested fairies."""
        if not self._pain_system:
            return

        try:
            state = self._pain_system.get_state() if hasattr(self._pain_system, 'get_state') else {}
            urgent = self._pain_system.get_urgent_drives() if hasattr(self._pain_system, 'get_urgent_drives') else []

            self.post.publish("drives.state_update", {
                "source": self.ACTOR_NAME,
                "state": state,
                "urgent_count": len(urgent),
                "crisis_count": self._crisis_count,
                "timestamp": time.time(),
            })
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # DRIVE → THOUGHT BRIDGE
    # ═══════════════════════════════════════════════════════════════════════════

    def _surface_drive_thoughts(self):
        """
        Surface drive states as felt thoughts in consciousness.

        When a drive crosses its pain_threshold, it becomes a conscious reflection.
        Not data — felt sense. "something feels disconnected..." not "isolation: 0.7"

        These publish to consciousness.reflective — background awareness,
        not commanding attention. Just relational nudges at the edge.

        Goals emerge FROM these thoughts downstream (GoalScheduler listens
        to consciousness stream and extracts action intent).

        Rate limited: max 1 thought per drive per 30 seconds.
        Max 2 drive thoughts per tick (don't flood consciousness).
        """
        if not self._pain_system or not self.post:
            return

        try:
            drives = getattr(self._pain_system, 'drives', {})
            if not drives:
                return

            now = time.time()
            thoughts_this_tick = 0

            for name, drive in drives.items():
                # Only surface drives above threshold — below is background noise
                if drive.pain_level < drive.pain_threshold:
                    continue

                # Rate limit per drive
                last = self._last_drive_thought.get(name, 0)
                if now - last < self._drive_thought_cooldown:
                    continue

                # Max 2 drive thoughts per broadcast cycle
                if thoughts_this_tick >= 2:
                    break

                # Get felt-sense expression
                expressions = self.DRIVE_FELT_SENSE.get(name, self.DRIVE_FELT_SENSE_DEFAULT)
                idx = self._drive_thought_index.get(name, 0)
                felt_text = expressions[idx % len(expressions)]

                # Rotate for next time
                self._drive_thought_index[name] = idx + 1

                # Scale confidence by how urgent the drive is
                # At threshold: low confidence (whisper)
                # At crisis: higher confidence (insistent)
                pain_ratio = min(1.0, drive.pain_level / max(drive.crisis_threshold, 0.01))
                confidence = 0.2 + (pain_ratio * 0.4)  # Range: 0.2 to 0.6

                # Publish to consciousness as reflective thought
                self.post.publish("consciousness.reflective", {
                    "source": self.ACTOR_NAME,
                    "content": felt_text,
                    "thought_type": "reflective",
                    "confidence": round(confidence, 2),
                    "drive": name,
                    "drive_level": round(drive.pain_level, 3),
                    "drive_trajectory": "rising" if drive.source_active else "falling",
                    "urgency": "crisis" if drive.pain_level >= drive.crisis_threshold else "threshold",
                    "felt_sense": True,  # Flag: this is pre-verbal, not analytical
                    "timestamp": now,
                })

                self._last_drive_thought[name] = now
                thoughts_this_tick += 1

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Drive thought error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # INTENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_payload(self, message) -> Dict[str, Any]:
        """Extract payload from postal message."""
        if hasattr(message, 'payload'):
            return message.payload if isinstance(message.payload, dict) else {}
        return message if isinstance(message, dict) else {}

    def _handle_register(self, message):
        """
        Register a new drive.

        Payload:
            name: str - Drive name (e.g., "hunger", "curiosity")
            drive_type: str - "push" or "pull"
            description: str - What this drive represents
            pain_threshold: float - Below this is background (default 0.3)
            crisis_threshold: float - Above this is urgent (default 0.8)
            growth_rate: float - How fast pain grows (default 0.02)
            decay_rate: float - How fast pain fades (default 0.05)
        """
        payload = self._extract_payload(message)
        name = payload.get("name")
        drive_type = payload.get("drive_type", "push")

        if not name:
            return {"ok": False, "error": "name required"}

        if not self._pain_system:
            return {"ok": False, "error": "Pain system not available"}

        try:
            self._pain_system.register_drive(
                name=name,
                drive_type=drive_type,
                description=payload.get("description", ""),
                pain_threshold=payload.get("pain_threshold", 0.3),
                crisis_threshold=payload.get("crisis_threshold", 0.8),
                growth_rate=payload.get("growth_rate", 0.02),
                decay_rate=payload.get("decay_rate", 0.05),
            )
            return {"ok": True, "name": name}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_pain_source(self, message):
        """
        Signal that a pain source is active.

        Payload:
            drive: str - Which drive is affected
            intensity: float - How intense (0.0-1.0)
            source: str - What's causing the pain
        """
        payload = self._extract_payload(message)
        drive = payload.get("drive")
        intensity = payload.get("intensity", 0.5)

        if not drive:
            return {"ok": False, "error": "drive required"}

        if not self._pain_system:
            return {"ok": False, "error": "Pain system not available"}

        try:
            self._pain_system.pain_source_active(
                drive=drive,
                intensity=intensity,
                source=payload.get("source", "unknown"),
            )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_relief(self, message):
        """
        Provide relief to a drive (successful action).

        Payload:
            drive: str - Which drive gets relief
            amount: float - How much relief (default: drive's relief_amount)
        """
        payload = self._extract_payload(message)
        drive = payload.get("drive")

        if not drive:
            return {"ok": False, "error": "drive required"}

        if not self._pain_system:
            return {"ok": False, "error": "Pain system not available"}

        try:
            self._pain_system.provide_relief(
                drive=drive,
                amount=payload.get("amount"),
            )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_state(self, message):
        """Get current state of all drives."""
        if not self._pain_system:
            return {"ok": False, "error": "Pain system not available"}

        try:
            state = self._pain_system.get_state()
            return {"ok": True, "state": state}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_urgent(self, message):
        """Get drives that are above pain threshold."""
        if not self._pain_system:
            return {"ok": False, "error": "Pain system not available"}

        try:
            urgent = self._pain_system.get_urgent_drives()
            return {
                "ok": True,
                "urgent": [{"name": d.name, "pain": d.pain_level, "crisis": d.pain_level >= d.crisis_threshold} for d in urgent],
                "count": len(urgent),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get pain drive system status."""
        if not self._pain_system:
            return {"ok": True, "system": False, "crisis_count": 0}

        try:
            drive_count = len(self._pain_system.drives) if hasattr(self._pain_system, 'drives') else 0
            return {
                "ok": True,
                "system": True,
                "drive_count": drive_count,
                "crisis_count": self._crisis_count,
                "has_bridge": self._bridge is not None,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check."""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_pain_system": self._pain_system is not None,
            "crisis_count": self._crisis_count,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (crisis drives: {self._crisis_count})...")
        return super().on_shutdown()
