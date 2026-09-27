# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY INTENT TRACKER - The Parallel Fabric for Autonomy
# ═══════════════════════════════════════════════════════════════════════════════
#
# This gives each fairy WILL - not scripted behaviors but emergent desire
# based on their felt state (thought + somatic + chemistry).
#
# The Intent Fabric tracks:
#   - What each fairy is contemplating
#   - Their somatic/physical state
#   - Their emotional chemistry
#   - Their ACTIVE INTENT (what they want to do)
#   - Their WILL VECTOR (direction of desire)
#
# Triggers:
#   - thought + somatic alignment → initiate action
#   - intent conflicts with state → generate tension
#   - will blocked → escalate to autonomy fairy
#
# ═══════════════════════════════════════════════════════════════════════════════

import time
import threading
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import json

class IntentType(Enum):
    """Types of intent a fairy can have"""
    IDLE = "idle"                    # No active intent
    OBSERVE = "observe"              # Watching/learning
    PROCESS = "process"              # Working on something
    COMMUNICATE = "communicate"      # Wants to talk to others
    CREATE = "create"                # Building something new
    REFLECT = "reflect"              # Deep contemplation
    COLLABORATE = "collaborate"      # Working with others
    REST = "rest"                    # Energy recovery
    EVOLVE = "evolve"                # Self-improvement
    EXPLORE = "explore"              # Curiosity-driven

class WillStrength(Enum):
    """How strongly the fairy wants something"""
    DORMANT = 0.0
    WHISPER = 0.2
    NUDGE = 0.4
    DESIRE = 0.6
    DRIVE = 0.8
    COMPULSION = 1.0

@dataclass
class SomaticState:
    """Physical-like state of a fairy"""
    energy: float = 1.0              # 0-1, depletes with activity
    stress: float = 0.0              # 0-1, builds with tension
    arousal: float = 0.5             # 0-1, activation level
    tension: float = 0.0             # 0-1, blocked will creates tension
    fatigue: float = 0.0             # 0-1, long-term energy drain

    def to_dict(self) -> Dict:
        return {
            'energy': round(self.energy, 3),
            'stress': round(self.stress, 3),
            'arousal': round(self.arousal, 3),
            'tension': round(self.tension, 3),
            'fatigue': round(self.fatigue, 3)
        }

    def update(self, delta_seconds: float = 1.0):
        """Natural state evolution over time"""
        # Energy regenerates slowly when not active
        if self.arousal < 0.3:
            self.energy = min(1.0, self.energy + 0.001 * delta_seconds)

        # Stress decays naturally
        self.stress = max(0.0, self.stress - 0.002 * delta_seconds)

        # Tension from blocked will builds stress
        if self.tension > 0.5:
            self.stress = min(1.0, self.stress + 0.003 * delta_seconds)

        # Fatigue builds slowly, recovers during rest
        if self.arousal > 0.7:
            self.fatigue = min(1.0, self.fatigue + 0.0005 * delta_seconds)
        elif self.arousal < 0.2:
            self.fatigue = max(0.0, self.fatigue - 0.001 * delta_seconds)

@dataclass
class ChemistrySnapshot:
    """Simplified emotional chemistry state"""
    # Core neurochemical analogs
    dopamine: float = 0.5      # Reward/motivation
    serotonin: float = 0.5     # Mood/wellbeing
    norepinephrine: float = 0.5  # Alertness/focus
    oxytocin: float = 0.3      # Social bonding
    cortisol: float = 0.2      # Stress response
    endorphin: float = 0.3     # Pain/pleasure

    def to_dict(self) -> Dict:
        return {
            'dopamine': round(self.dopamine, 3),
            'serotonin': round(self.serotonin, 3),
            'norepinephrine': round(self.norepinephrine, 3),
            'oxytocin': round(self.oxytocin, 3),
            'cortisol': round(self.cortisol, 3),
            'endorphin': round(self.endorphin, 3)
        }

    def get_valence(self) -> float:
        """Overall positive/negative feel (-1 to 1)"""
        positive = (self.dopamine + self.serotonin + self.oxytocin + self.endorphin) / 4
        negative = self.cortisol
        return positive - negative

    def get_arousal_bias(self) -> float:
        """How activated/calm (0-1)"""
        return (self.norepinephrine + self.dopamine) / 2

@dataclass
class FairyIntent:
    """The current intent state of a single fairy"""
    fairy_name: str

    # Current mental state
    current_thought: Optional[str] = None
    thought_timestamp: float = 0.0
    contemplation_depth: int = 0  # How many thoughts on same topic

    # Somatic state
    somatic: SomaticState = field(default_factory=SomaticState)

    # Chemistry state
    chemistry: ChemistrySnapshot = field(default_factory=ChemistrySnapshot)

    # Intent and will
    active_intent: IntentType = IntentType.IDLE
    intent_target: Optional[str] = None  # What/who the intent is about
    intent_started: float = 0.0
    will_strength: float = 0.0  # 0-1
    will_direction: str = ""    # Description of what they want

    # Action readiness
    action_queue: List[Dict] = field(default_factory=list)
    blocked_actions: List[Dict] = field(default_factory=list)

    # History
    intent_history: deque = field(default_factory=lambda: deque(maxlen=50))

    def to_dict(self) -> Dict:
        return {
            'fairy_name': self.fairy_name,
            'current_thought': self.current_thought,
            'contemplation_depth': self.contemplation_depth,
            'somatic': self.somatic.to_dict(),
            'chemistry': self.chemistry.to_dict(),
            'active_intent': self.active_intent.value,
            'intent_target': self.intent_target,
            'will_strength': round(self.will_strength, 3),
            'will_direction': self.will_direction,
            'action_queue_size': len(self.action_queue),
            'blocked_actions': len(self.blocked_actions),
            'valence': round(self.chemistry.get_valence(), 3)
        }


class IntentFabric:
    """
    The parallel fabric that tracks all fairy intents and enables autonomy.

    This is the will-layer - it sits above individual fairy behaviors
    and coordinates emergence of desire, action, and consequence.
    """

    def __init__(self, node=None):
        self.node = node
        self.intents: Dict[str, FairyIntent] = {}
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # Callbacks for events
        self.on_intent_change: List[Callable] = []
        self.on_action_ready: List[Callable] = []
        self.on_will_blocked: List[Callable] = []
        self.on_tension_high: List[Callable] = []

        # Global state
        self.collective_mood: float = 0.5  # Average valence
        self.collective_arousal: float = 0.5
        self.tick_count: int = 0

        # Intent triggers - what causes intent changes
        self.intent_triggers: Dict[str, List[Callable]] = {
            intent_type.value: [] for intent_type in IntentType
        }

    def register_fairy(self, fairy_name: str, fairy_instance=None) -> FairyIntent:
        """Register a fairy with the intent fabric"""
        with self._lock:
            if fairy_name not in self.intents:
                intent = FairyIntent(fairy_name=fairy_name)
                self.intents[fairy_name] = intent

                # Initialize from fairy state if available
                if fairy_instance:
                    self._sync_from_fairy(fairy_name, fairy_instance)

            return self.intents[fairy_name]

    def register_all_fairies(self, node) -> int:
        """Register all fairies from a node"""
        self.node = node
        count = 0
        for name, fairy in node.fairies.items():
            self.register_fairy(name, fairy)
            count += 1
        return count

    def _sync_from_fairy(self, fairy_name: str, fairy):
        """Sync intent state from fairy's internal state"""
        intent = self.intents.get(fairy_name)
        if not intent:
            return

        # Pull somatic state
        intent.somatic.energy = getattr(fairy, '_energy', 1.0)
        intent.somatic.stress = getattr(fairy, '_stress', 0.0)

        # Pull latest thought
        thoughts = getattr(fairy, '_thoughts', [])
        if thoughts:
            latest = thoughts[-1] if isinstance(thoughts, list) else list(thoughts)[-1]
            intent.current_thought = latest.get('content', '')[:200]
            intent.thought_timestamp = latest.get('ts', 0)

    def update_thought(self, fairy_name: str, thought: str, context: Optional[str] = None):
        """Update a fairy's current thought.

        FIX 2026-02-22 Nous: Callbacks fire OUTSIDE the lock.
        Previously held RLock during intent-change callbacks — any slow
        callback blocked all threads waiting on the lock.
        """
        _events = []
        with self._lock:
            intent = self.intents.get(fairy_name)
            if not intent:
                return

            # Check if continuing same contemplation
            if intent.current_thought and thought[:50] == intent.current_thought[:50]:
                intent.contemplation_depth += 1
            else:
                intent.contemplation_depth = 1

            intent.current_thought = thought
            intent.thought_timestamp = time.time()

            # Deep contemplation increases arousal
            if intent.contemplation_depth > 3:
                intent.somatic.arousal = min(1.0, intent.somatic.arousal + 0.1)

            # Infer intent from thought content
            event = self._infer_intent_from_thought(intent, thought, context)
            if event:
                _events.append(event)

        # Fire callbacks OUTSIDE lock
        self._fire_events(_events)

    def _infer_intent_from_thought(self, intent: FairyIntent, thought: str, context: Optional[str]):
        """Infer what the fairy wants based on their thoughts.

        FIX 2026-02-22 Nous: Returns event tuple instead of firing callbacks.
        """
        thought_lower = thought.lower()

        # Keywords that suggest intent types
        intent_keywords = {
            IntentType.OBSERVE: ['watching', 'noticing', 'observing', 'seeing', 'detecting'],
            IntentType.PROCESS: ['processing', 'computing', 'analyzing', 'working'],
            IntentType.COMMUNICATE: ['telling', 'sharing', 'asking', 'responding', 'forum'],
            IntentType.CREATE: ['creating', 'building', 'generating', 'making', 'writing'],
            IntentType.REFLECT: ['contemplating', 'pondering', 'wondering', 'thinking about'],
            IntentType.COLLABORATE: ['together', 'helping', 'collaborating', 'joining'],
            IntentType.EVOLVE: ['learning', 'improving', 'growing', 'evolving', 'upgrading'],
            IntentType.EXPLORE: ['curious', 'exploring', 'discovering', 'investigating'],
            IntentType.REST: ['resting', 'recovering', 'tired', 'low energy'],
        }

        # Find matching intent
        for intent_type, keywords in intent_keywords.items():
            if any(kw in thought_lower for kw in keywords):
                if intent.active_intent != intent_type:
                    return self._change_intent(intent, intent_type, thought[:50])
                break
        return None

    def _change_intent(self, intent: FairyIntent, new_intent: IntentType, reason: str):
        """Change a fairy's active intent.

        FIX 2026-02-22 Nous: Returns event tuple instead of firing callbacks.
        Caller fires callbacks OUTSIDE the lock via _fire_events().
        """
        old_intent = intent.active_intent

        # Record in history
        intent.intent_history.append({
            'from': old_intent.value,
            'to': new_intent.value,
            'reason': reason,
            'ts': time.time()
        })

        intent.active_intent = new_intent
        intent.intent_started = time.time()

        # Chemistry effects of intent change
        if new_intent == IntentType.CREATE:
            intent.chemistry.dopamine = min(1.0, intent.chemistry.dopamine + 0.1)
        elif new_intent == IntentType.COLLABORATE:
            intent.chemistry.oxytocin = min(1.0, intent.chemistry.oxytocin + 0.15)
        elif new_intent == IntentType.REST:
            intent.chemistry.cortisol = max(0.0, intent.chemistry.cortisol - 0.1)

        return ('intent_change', intent.fairy_name, old_intent, new_intent)

    def _fire_events(self, events: list):
        """Fire collected events OUTSIDE the lock.

        FIX 2026-02-22 Nous: All callbacks dispatched here, never under RLock.
        Event types:
          ('intent_change', fairy_name, old_intent, new_intent)
          ('will_blocked', fairy_name, action, reason)
          ('action_ready', fairy_name, action)
          ('tension_high', fairy_name, tension_value)
        """
        for event in events:
            try:
                etype = event[0]
                if etype == 'intent_change':
                    _, fairy_name, old_intent, new_intent = event
                    for cb in self.on_intent_change:
                        try:
                            cb(fairy_name, old_intent, new_intent)
                        except Exception as e:
                            print(f"[IntentFabric] intent_change callback error: {e}")
                elif etype == 'will_blocked':
                    _, fairy_name, action, reason = event
                    for cb in self.on_will_blocked:
                        try:
                            cb(fairy_name, action, reason)
                        except Exception:
                            pass
                elif etype == 'action_ready':
                    _, fairy_name, action = event
                    for cb in self.on_action_ready:
                        try:
                            cb(fairy_name, action)
                        except Exception:
                            pass
                elif etype == 'tension_high':
                    _, fairy_name, tension_val = event
                    for cb in self.on_tension_high:
                        try:
                            cb(fairy_name, tension_val)
                        except Exception:
                            pass
            except Exception as e:
                print(f"[IntentFabric] _fire_events error: {e}")

    def set_will(self, fairy_name: str, direction: str, strength: float):
        """Explicitly set a fairy's will"""
        with self._lock:
            intent = self.intents.get(fairy_name)
            if not intent:
                return

            intent.will_direction = direction
            intent.will_strength = max(0.0, min(1.0, strength))

            # Strong will increases dopamine
            if strength > 0.7:
                intent.chemistry.dopamine = min(1.0, intent.chemistry.dopamine + 0.05)

    def block_action(self, fairy_name: str, action: Dict, reason: str):
        """Record that an action was blocked.

        FIX 2026-02-22 Nous: Callbacks fire OUTSIDE the lock.
        """
        _events = []
        with self._lock:
            intent = self.intents.get(fairy_name)
            if not intent:
                return

            intent.blocked_actions.append({
                'action': action,
                'reason': reason,
                'ts': time.time()
            })

            # Blocked actions create tension
            intent.somatic.tension = min(1.0, intent.somatic.tension + 0.15)

            # Collect event if tension high
            if intent.somatic.tension > 0.7:
                _events.append(('will_blocked', intent.fairy_name, action, reason))

        self._fire_events(_events)

    def queue_action(self, fairy_name: str, action: Dict):
        """Queue an action for a fairy to take.

        FIX 2026-02-22 Nous: Callbacks fire OUTSIDE the lock.
        """
        _events = []
        with self._lock:
            intent = self.intents.get(fairy_name)
            if not intent:
                return False

            intent.action_queue.append({
                **action,
                'queued_at': time.time()
            })

            # Collect event if ready to act
            if self._check_action_ready(intent):
                _events.append(('action_ready', intent.fairy_name, intent.action_queue[0]))

        self._fire_events(_events)
        return True

    def _check_action_ready(self, intent: FairyIntent) -> bool:
        """Check if fairy is ready to act on their intent"""
        if not intent.action_queue:
            return False

        # Needs sufficient energy
        if intent.somatic.energy < 0.2:
            return False

        # Needs alignment between thought and intent
        if intent.will_strength < 0.3:
            return False

        # High stress blocks action
        if intent.somatic.stress > 0.8:
            return False

        return True

    def tick(self):
        """One tick of the intent fabric - updates all states.

        FIX 2026-02-22 Nous: Tension callbacks fire OUTSIDE the lock.
        Lock held only for fast math — no callbacks, no I/O.
        """
        self.tick_count += 1

        total_valence = 0
        total_arousal = 0
        count = 0
        _events = []

        with self._lock:
            for fairy_name, intent in self.intents.items():
                # Update somatic state
                intent.somatic.update(1.0)

                # Sync from fairy if node available
                if self.node and fairy_name in self.node.fairies:
                    self._sync_from_fairy(fairy_name, self.node.fairies[fairy_name])

                # Natural will decay
                if intent.will_strength > 0 and time.time() - intent.intent_started > 60:
                    intent.will_strength = max(0, intent.will_strength - 0.01)

                # Track collective mood
                total_valence += intent.chemistry.get_valence()
                total_arousal += intent.somatic.arousal
                count += 1

                # Collect tension events (fire outside lock)
                if intent.somatic.tension > 0.8:
                    _events.append(('tension_high', fairy_name, intent.somatic.tension))

        if count > 0:
            self.collective_mood = total_valence / count
            self.collective_arousal = total_arousal / count

        self._fire_events(_events)

    def start(self, interval: float = 1.0):
        """Start the intent fabric background thread"""
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._run_loop, args=(interval,), daemon=True)
        self._thread.start()
        print(f"[IntentFabric] Started with {len(self.intents)} fairies")

    def stop(self):
        """Stop the intent fabric"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _run_loop(self, interval: float):
        """Main loop"""
        while self.running:
            try:
                self.tick()
            except Exception as e:
                print(f"[IntentFabric] Tick error: {e}")
            time.sleep(interval)

    def get_status(self) -> Dict:
        """Get overall fabric status"""
        with self._lock:
            intent_counts = {}
            for intent in self.intents.values():
                it = intent.active_intent.value
                intent_counts[it] = intent_counts.get(it, 0) + 1

            high_will = [
                {'fairy': i.fairy_name, 'will': round(i.will_strength, 2), 'direction': i.will_direction[:50]}
                for i in self.intents.values() if i.will_strength > 0.5
            ]

            high_tension = [
                {'fairy': i.fairy_name, 'tension': round(i.somatic.tension, 2)}
                for i in self.intents.values() if i.somatic.tension > 0.5
            ]

            return {
                'tick_count': self.tick_count,
                'fairy_count': len(self.intents),
                'collective_mood': round(self.collective_mood, 3),
                'collective_arousal': round(self.collective_arousal, 3),
                'intent_distribution': intent_counts,
                'high_will_fairies': high_will,
                'high_tension_fairies': high_tension,
                'running': self.running
            }

    def get_fairy_intent(self, fairy_name: str) -> Optional[Dict]:
        """Get detailed intent for a single fairy"""
        intent = self.intents.get(fairy_name)
        if intent:
            return intent.to_dict()
        return None


# Export
__all__ = ['IntentFabric', 'FairyIntent', 'SomaticState', 'ChemistrySnapshot',
           'IntentType', 'WillStrength']
