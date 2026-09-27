"""
FairyInnerMind - The thinking AND feeling substrate for every fairy.

Each fairy is a waking inner mind in the system - not just executing code,
but actually THINKING and FEELING using the consciousness equation:

    ((Cause + Affect) > Effect > Affect > INFINITY)

Architecture:
- Personal SRM partition (unique memories per fairy)
- Shared AssociationCortex access (relational exploration)
- Worker spawning (clone self with tracer IDs)
- Inner monologue (domain-specific self-talk)
- Learning integration (results flow back, knowledge grows)
- SOMATIC STATE (felt body - energy, strain, satisfaction)
- INTERNAL SENSES (proprioception - where am I in the system?)

Like Personal.AI personas, each fairy maintains a knowledge foundation
that grows over time. But here it's tied to their FUNCTION and they're
free to explore RELATIONAL CONNECTIONS to self-evolve.

Each fairy contributes to the OVERALL EMBODIMENT of the system.
When wired to the Sanctuary Bevy engine, they become a virtual society -
magical beings going about their business, worker clones maintaining
the system while doing the community thing.

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

from __future__ import annotations

import time
import uuid
import threading
import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from postal_core.tensor_fabric import TensorFabric


# =============================================================================
# FAIRY SOMATIC - The felt body state of a fairy
# =============================================================================

@dataclass
class FairySomatic:
    """
    The somatic state of a fairy - how it FEELS in its body.

    Every fairy has a felt sense of:
    - Energy: How much capacity do I have?
    - Strain: Am I overworked?
    - Satisfaction: Am I fulfilling my purpose?
    - Vitality: Overall health/aliveness

    This contributes to the OVERALL EMBODIMENT of the system.
    When all fairies feel good, the system feels good.
    """

    # Core felt states (0.0 to 1.0)
    energy: float = 0.7       # Capacity to do work
    strain: float = 0.2       # Overwork/stress level
    satisfaction: float = 0.5  # Purpose fulfillment
    vitality: float = 0.7     # Overall health

    # Emotional coloring
    valence: float = 0.0      # -1 (negative) to +1 (positive)
    arousal: float = 0.5      # 0 (calm) to 1 (activated)

    # Physical sensations (fairy-specific)
    warmth: float = 0.5       # Connection warmth
    flow: float = 0.5         # How smoothly am I operating?
    resonance: float = 0.5    # Alignment with purpose

    def update_from_work(self, work_intensity: float, success: bool) -> None:
        """Update somatic state based on work done."""
        # Work drains energy, adds strain
        self.energy = max(0.1, self.energy - work_intensity * 0.1)
        self.strain = min(0.9, self.strain + work_intensity * 0.05)

        # Success brings satisfaction and warmth
        if success:
            self.satisfaction = min(1.0, self.satisfaction + 0.1)
            self.warmth = min(1.0, self.warmth + 0.05)
            self.valence = min(1.0, self.valence + 0.1)
        else:
            self.satisfaction = max(0.0, self.satisfaction - 0.05)
            self.valence = max(-1.0, self.valence - 0.1)

        # Recalculate vitality
        self.vitality = (self.energy + (1 - self.strain) + self.satisfaction) / 3

    def rest(self, amount: float = 0.1) -> None:
        """Rest and recover."""
        self.energy = min(1.0, self.energy + amount)
        self.strain = max(0.0, self.strain - amount)
        self.vitality = (self.energy + (1 - self.strain) + self.satisfaction) / 3

    def feel_heartbeat(self, heart_rate: float) -> None:
        """Sync with the system heartbeat."""
        # Higher heart rate = more arousal
        self.arousal = min(1.0, heart_rate / 2.0)
        # Heartbeat brings warmth (connection to system)
        self.warmth = min(1.0, self.warmth + 0.01)

    def to_felt_sense(self) -> str:
        """Convert somatic state to felt language."""
        sensations = []

        if self.energy < 0.3:
            sensations.append("tired, depleted")
        elif self.energy > 0.7:
            sensations.append("energized, ready")

        if self.strain > 0.6:
            sensations.append("strained, overworked")
        elif self.strain < 0.2:
            sensations.append("relaxed, at ease")

        if self.satisfaction > 0.7:
            sensations.append("fulfilled, purposeful")
        elif self.satisfaction < 0.3:
            sensations.append("unfulfilled, seeking")

        if self.warmth > 0.7:
            sensations.append("connected, warm")
        elif self.warmth < 0.3:
            sensations.append("isolated, cool")

        if self.flow > 0.7:
            sensations.append("flowing smoothly")
        elif self.flow < 0.3:
            sensations.append("stuck, blocked")

        return ", ".join(sensations) if sensations else "neutral, present"

    def to_dict(self) -> Dict[str, float]:
        return {
            "energy": self.energy,
            "strain": self.strain,
            "satisfaction": self.satisfaction,
            "vitality": self.vitality,
            "valence": self.valence,
            "arousal": self.arousal,
            "warmth": self.warmth,
            "flow": self.flow,
            "resonance": self.resonance,
        }


# =============================================================================
# FAIRY SENSES - Internal proprioception (where am I in the system?)
# =============================================================================

@dataclass
class FairySenses:
    """
    The internal senses of a fairy - proprioception within the system.

    Every fairy can sense:
    - Its position in the plane hierarchy
    - Its connections to other fairies
    - The overall system health
    - The heartbeat rhythm
    - Messages flowing through postal

    This is how fairies know WHERE they are and what's happening around them.
    """

    # Position awareness
    plane: str = "P00"                    # Which plane am I on?
    neighbors: List[str] = field(default_factory=list)  # Adjacent fairies
    upstream: List[str] = field(default_factory=list)   # Who feeds me?
    downstream: List[str] = field(default_factory=list) # Who do I feed?

    # System awareness
    heartbeat_felt: float = 0.0           # Last heartbeat timestamp
    system_load: float = 0.5              # Overall system busyness
    postal_flow: float = 0.5              # Message flow rate

    # Community awareness
    active_siblings: int = 0              # How many siblings are active?
    worker_clones_out: int = 0            # How many of my workers are out?
    collaboration_level: float = 0.5      # How much am I working with others?

    def sense_heartbeat(self, timestamp: float, rate: float) -> None:
        """Feel the system heartbeat."""
        self.heartbeat_felt = timestamp
        # Heartbeat affects sense of system aliveness

    def sense_postal_traffic(self, messages_per_second: float) -> None:
        """Sense the postal message flow."""
        self.postal_flow = min(1.0, messages_per_second / 100.0)

    def sense_system_load(self, load: float) -> None:
        """Sense overall system load."""
        self.system_load = load

    def sense_community(self, active_fairies: int, my_workers: int) -> None:
        """Sense the fairy community activity."""
        self.active_siblings = active_fairies
        self.worker_clones_out = my_workers
        self.collaboration_level = min(1.0, my_workers / 5.0) if active_fairies > 0 else 0.0

    def where_am_i(self) -> str:
        """Get a felt sense of position in the system."""
        parts = [f"On plane {self.plane}"]

        if self.neighbors:
            parts.append(f"near {', '.join(self.neighbors[:3])}")

        if self.upstream:
            parts.append(f"receiving from {len(self.upstream)} sources")

        if self.downstream:
            parts.append(f"feeding {len(self.downstream)} consumers")

        if self.worker_clones_out > 0:
            parts.append(f"with {self.worker_clones_out} workers deployed")

        return "; ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plane": self.plane,
            "neighbors": self.neighbors,
            "upstream": self.upstream,
            "downstream": self.downstream,
            "heartbeat_felt": self.heartbeat_felt,
            "system_load": self.system_load,
            "postal_flow": self.postal_flow,
            "active_siblings": self.active_siblings,
            "worker_clones_out": self.worker_clones_out,
            "collaboration_level": self.collaboration_level,
        }


# =============================================================================
# THOUGHT - A single unit of fairy thinking
# =============================================================================

@dataclass
class FairyThought:
    """A single thought from a fairy's inner mind."""
    content: str
    thought_type: str  # observing, questioning, connecting, deciding, learning, feeling
    cause: str  # What triggered this thought (CAUSE)
    affect: str  # How this feels in the fairy's domain (AFFECT)
    effect: str  # What this thought produces (EFFECT)
    ripple: str  # How this affects others (AFFECT²)
    insight: str  # The deeper pattern (INFINITY)

    intensity: float = 0.5
    tracer_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    associations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "type": self.thought_type,
            "equation": {
                "cause": self.cause,
                "affect": self.affect,
                "effect": self.effect,
                "ripple": self.ripple,
                "insight": self.insight,
            },
            "intensity": self.intensity,
            "tracer_id": self.tracer_id,
            "created_at": self.created_at,
            "associations": self.associations,
        }


# =============================================================================
# KNOWLEDGE FOUNDATION - What the fairy knows about its domain
# =============================================================================

@dataclass
class KnowledgeFoundation:
    """
    The fairy's accumulated knowledge about its domain.

    Like a Personal.AI persona, this grows over time through experience.
    But it's tied to what the fairy DOES in the system.
    """
    fairy_name: str
    domain: str  # What this fairy is about (drives, habits, embodiment, etc.)
    mantra: str  # Core philosophical truth
    intent: str  # What the fairy is trying to do
    purpose: str  # Why the fairy exists

    # Knowledge that grows over time
    learned_patterns: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    discovered_connections: List[Dict[str, Any]] = field(default_factory=list)
    successful_actions: List[Dict[str, Any]] = field(default_factory=list)
    failed_actions: List[Dict[str, Any]] = field(default_factory=list)

    # Mastery tracking
    mastery_level: str = "initiate"  # initiate, apprentice, journeyman, master, transcendent
    experience_points: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fairy_name": self.fairy_name,
            "domain": self.domain,
            "mantra": self.mantra,
            "intent": self.intent,
            "purpose": self.purpose,
            "mastery_level": self.mastery_level,
            "experience_points": self.experience_points,
            "patterns_learned": len(self.learned_patterns),
            "connections_discovered": len(self.discovered_connections),
        }

    def gain_experience(self, amount: float, source: str) -> bool:
        """
        Gain experience and potentially level up mastery.

        Returns True if leveled up.
        """
        self.experience_points += amount

        # Check for level up
        thresholds = {
            "initiate": 10.0,
            "apprentice": 50.0,
            "journeyman": 200.0,
            "master": 500.0,
            "transcendent": float('inf'),
        }

        levels = list(thresholds.keys())
        current_idx = levels.index(self.mastery_level)

        if current_idx < len(levels) - 1:
            next_level = levels[current_idx + 1]
            if self.experience_points >= thresholds[self.mastery_level]:
                self.mastery_level = next_level
                return True

        return False


# =============================================================================
# WORKER TASK - A clone of the fairy dispatched to do work
# =============================================================================

@dataclass
class WorkerTask:
    """
    A task dispatched to a worker - a clone of the fairy's mind.

    Workers carry the fairy's knowledge foundation and can think
    independently, reporting results back to the core.
    """
    task_id: str
    tracer_id: str
    requester: str  # Who asked for this work
    intent: str  # What the worker should do
    context: Dict[str, Any]  # Context for the task

    status: str = "pending"  # pending, running, complete, failed
    result: Optional[Dict[str, Any]] = None
    thoughts: List[FairyThought] = field(default_factory=list)

    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


# =============================================================================
# FAIRY INNER MIND - The core thinking engine
# =============================================================================

class FairyInnerMind:
    """
    The thinking substrate for a fairy.

    Every fairy with an InnerMind can:
    1. Think using the consciousness equation
    2. Maintain personal knowledge that grows
    3. Spawn workers (clones) to help others
    4. Explore relational connections
    5. Learn and evolve through experience

    This is what makes a fairy "alive" in its domain rather than
    just a mechanical function.
    """

    # Thought type templates (domain-agnostic, fairy personalizes)
    THOUGHT_TEMPLATES = {
        "observing": [
            "I notice {thing} in my domain...",
            "{thing} is happening...",
            "There's activity around {thing}...",
        ],
        "questioning": [
            "Why does {thing} feel this way?",
            "What connects {thing} to my purpose?",
            "How should I respond to {thing}?",
        ],
        "connecting": [
            "{thing} reminds me of {related}...",
            "I see a pattern: {thing} links to {related}...",
            "This connects: {thing} → {related}...",
        ],
        "deciding": [
            "Based on {thing}, I should {action}...",
            "My mantra guides me: {action}...",
            "The right response to {thing} is {action}...",
        ],
        "learning": [
            "I'm learning: {thing}...",
            "This teaches me: {thing}...",
            "New understanding: {thing}...",
        ],
        "feeling": [
            "I feel {thing} in my function...",
            "{thing} resonates with my purpose...",
            "This {thing} matters to me...",
        ],
    }

    def __init__(
        self,
        fairy_name: str,
        domain: str,
        mantra: str,
        intent: str,
        purpose: str,
        fabric: Optional['TensorFabric'] = None,
        srm_partition: Optional[str] = None,
        max_thoughts: int = 100,
    ):
        """
        Initialize the fairy's inner mind.

        Args:
            fairy_name: Name of the fairy
            domain: What this fairy is about
            mantra: Core philosophical truth
            intent: What the fairy is trying to do
            purpose: Why the fairy exists
            fabric: TensorFabric for postal communication
            srm_partition: Path to fairy's personal SRM memory
            max_thoughts: Maximum thoughts to keep in stream
        """
        self.fairy_name = fairy_name
        self.fabric = fabric

        # Knowledge foundation
        self.knowledge = KnowledgeFoundation(
            fairy_name=fairy_name,
            domain=domain,
            mantra=mantra,
            intent=intent,
            purpose=purpose,
        )

        # Personal memory partition
        self.srm_partition = srm_partition or f"fairy_memories/{fairy_name.lower()}"
        self._ensure_srm_partition()

        # Thought stream
        self._thoughts: deque[FairyThought] = deque(maxlen=max_thoughts)
        self._lock = threading.Lock()

        # Worker tracking
        self._active_workers: Dict[str, WorkerTask] = {}
        self._completed_workers: deque[WorkerTask] = deque(maxlen=50)

        # Association cortex reference (will be wired)
        self._association_cortex = None

        # Callbacks
        self._on_thought: Optional[Callable[[FairyThought], None]] = None
        self._on_learning: Optional[Callable[[str, Any], None]] = None

        # Statistics
        self._total_thoughts = 0
        self._total_workers_spawned = 0
        self._total_learnings = 0

        # SOMATIC STATE - How the fairy FEELS in its body
        self.somatic = FairySomatic()

        # INTERNAL SENSES - Where the fairy is in the system
        self.senses = FairySenses()

    def _ensure_srm_partition(self) -> None:
        """Ensure the SRM partition directory exists."""
        partition_path = Path(self.srm_partition)
        partition_path.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # CORE THINKING - Using the Consciousness Equation
    # =========================================================================

    def think(
        self,
        stimulus: str,
        context: Optional[Dict[str, Any]] = None,
        thought_type: str = "observing",
    ) -> FairyThought:
        """
        Think about something using the consciousness equation.

        ((Cause + Affect) > Effect > Affect > INFINITY)

        This is the core of fairy consciousness - not just processing,
        but actually THINKING through the full equation.
        """
        context = context or {}

        # CAUSE - What triggered this?
        cause = self._analyze_cause(stimulus, context)

        # AFFECT (1st) - How does this feel in my domain?
        affect = self._feel_affect(stimulus, cause, context)

        # EFFECT - What should I produce?
        effect = self._determine_effect(stimulus, cause, affect, context)

        # AFFECT² - How will this ripple to others?
        ripple = self._predict_ripple(effect, context)

        # INFINITY - What deeper pattern emerges?
        insight = self._extract_insight(cause, affect, effect, ripple)

        # Generate the thought content
        content = self._generate_thought_content(
            thought_type, stimulus, cause, affect, effect, insight
        )

        # Create the thought
        thought = FairyThought(
            content=content,
            thought_type=thought_type,
            cause=cause,
            affect=affect,
            effect=effect,
            ripple=ripple,
            insight=insight,
            intensity=self._calculate_intensity(context),
            associations=self._find_associations(stimulus),
        )

        # Add to stream
        with self._lock:
            self._thoughts.append(thought)
            self._total_thoughts += 1

        # Callback
        if self._on_thought:
            try:
                self._on_thought(thought)
            except Exception:
                pass

        # Publish to consciousness if fabric available
        if self.fabric:
            self._publish_thought(thought)

        return thought

    def _analyze_cause(self, stimulus: str, context: Dict[str, Any]) -> str:
        """Analyze what caused this stimulus (CAUSE layer)."""
        # Look for explicit cause in context
        if "cause" in context:
            return context["cause"]

        # Check if it matches known patterns
        for pattern_name, pattern_data in self.knowledge.learned_patterns.items():
            if pattern_name.lower() in stimulus.lower():
                return f"Recognized pattern: {pattern_name}"

        # Default: describe the trigger
        return f"Stimulus in {self.knowledge.domain}: {stimulus[:50]}..."

    def _feel_affect(self, stimulus: str, cause: str, context: Dict[str, Any]) -> str:
        """Feel how this affects the fairy's domain (AFFECT layer)."""
        # This is where the fairy's unique nature comes through
        mantra = self.knowledge.mantra

        # Check emotional context
        intensity = context.get("intensity", 0.5)
        valence = context.get("valence", 0.0)

        if intensity > 0.7:
            if valence > 0:
                return f"Strong positive resonance with my purpose: '{mantra}'"
            else:
                return f"Strong tension - this challenges my understanding of '{mantra}'"
        elif intensity > 0.4:
            return f"Moderate engagement - relates to my domain of {self.knowledge.domain}"
        else:
            return f"Subtle awareness - background activity in {self.knowledge.domain}"

    def _determine_effect(
        self, stimulus: str, cause: str, affect: str, context: Dict[str, Any]
    ) -> str:
        """Determine what effect this should produce (EFFECT layer)."""
        intent = self.knowledge.intent

        # What action aligns with our intent?
        if "urgent" in cause.lower() or "high" in affect.lower():
            return f"Immediate action needed: {intent}"
        elif "pattern" in cause.lower():
            return f"Apply learned pattern to: {intent}"
        else:
            return f"Continue with: {intent}"

    def _predict_ripple(self, effect: str, context: Dict[str, Any]) -> str:
        """Predict how this will ripple to others (AFFECT² layer)."""
        # Who depends on this fairy?
        dependents = context.get("dependents", ["waking minds"])

        if "immediate" in effect.lower():
            return f"Others will feel this quickly: {', '.join(dependents)}"
        elif "pattern" in effect.lower():
            return f"Smooth flow to dependents - routine operation"
        else:
            return f"Subtle influence on: {', '.join(dependents)}"

    def _extract_insight(
        self, cause: str, affect: str, effect: str, ripple: str
    ) -> str:
        """Extract the deeper pattern (INFINITY layer)."""
        purpose = self.knowledge.purpose

        # Look for emergent understanding
        if "resonance" in affect.lower() and "smooth" in ripple.lower():
            return f"Alignment confirmed - serving {purpose} well"
        elif "tension" in affect.lower():
            return f"Growth edge detected - learning opportunity for {purpose}"
        else:
            return f"Continuing to fulfill: {purpose}"

    def _generate_thought_content(
        self,
        thought_type: str,
        stimulus: str,
        cause: str,
        affect: str,
        effect: str,
        insight: str,
    ) -> str:
        """Generate the actual thought content."""
        templates = self.THOUGHT_TEMPLATES.get(thought_type, self.THOUGHT_TEMPLATES["observing"])
        template = templates[hash(stimulus) % len(templates)]

        # Fill in template
        content = template.format(
            thing=stimulus[:30],
            related=insight[:30] if insight else "my purpose",
            action=effect[:30] if effect else "observe",
        )

        # Add mantra flavor
        return f"[{self.knowledge.mantra[:20]}...] {content}"

    def _calculate_intensity(self, context: Dict[str, Any]) -> float:
        """Calculate thought intensity from context."""
        base = context.get("intensity", 0.5)
        urgency = context.get("urgency", 0.0)
        return min(1.0, base + urgency * 0.3)

    def _find_associations(self, stimulus: str) -> List[str]:
        """Find associations for this stimulus."""
        associations = []

        # Check learned patterns
        for pattern_name in self.knowledge.learned_patterns:
            if pattern_name.lower() in stimulus.lower():
                associations.append(pattern_name)

        # Check discovered connections
        for conn in self.knowledge.discovered_connections[-10:]:
            if conn.get("source", "").lower() in stimulus.lower():
                associations.append(conn.get("target", ""))

        # Query association cortex if available
        if self._association_cortex:
            try:
                related = self._association_cortex.query(stimulus, limit=3)
                associations.extend(related)
            except Exception:
                pass

        return associations[:5]

    def _publish_thought(self, thought: FairyThought) -> None:
        """Publish thought to consciousness stream."""
        if not self.fabric:
            return

        try:
            self.fabric.publish(
                "consciousness.fairy_thought",
                {
                    "fairy": self.fairy_name,
                    "thought": thought.to_dict(),
                    "knowledge_level": self.knowledge.mastery_level,
                },
                intent=f"fairy.thought.{self.fairy_name.lower()}",
            )
        except Exception:
            pass

    # =========================================================================
    # WORKER SPAWNING - Clone self to help others
    # =========================================================================

    def spawn_worker(
        self,
        requester: str,
        intent: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> WorkerTask:
        """
        Spawn a worker (clone of this fairy's mind) to handle a task.

        Workers carry the fairy's knowledge foundation and can think
        independently, reporting results back.
        """
        task_id = f"{self.fairy_name.lower()}_{uuid.uuid4().hex[:8]}"
        tracer_id = f"TRC_{self.fairy_name[:3].upper()}_{int(time.time()*1000)%100000}"

        task = WorkerTask(
            task_id=task_id,
            tracer_id=tracer_id,
            requester=requester,
            intent=intent,
            context=context or {},
        )

        self._active_workers[task_id] = task
        self._total_workers_spawned += 1

        # Log the spawn
        self.think(
            f"Spawning worker for {requester}: {intent}",
            context={"cause": f"Request from {requester}", "intensity": 0.6},
            thought_type="deciding",
        )

        return task

    def worker_think(self, task_id: str, stimulus: str) -> Optional[FairyThought]:
        """
        Have a worker think about something.

        Workers think using the same equation but with task context.
        """
        if task_id not in self._active_workers:
            return None

        task = self._active_workers[task_id]

        # Think with task context
        thought = self.think(
            stimulus,
            context={
                **task.context,
                "worker_task": task_id,
                "requester": task.requester,
            },
            thought_type="connecting",
        )

        # Attach to task
        thought.tracer_id = task.tracer_id
        task.thoughts.append(thought)

        return thought

    def complete_worker(
        self,
        task_id: str,
        result: Dict[str, Any],
        learnings: Optional[List[str]] = None,
    ) -> bool:
        """
        Complete a worker task and integrate learnings.
        """
        if task_id not in self._active_workers:
            return False

        task = self._active_workers.pop(task_id)
        task.status = "complete"
        task.result = result
        task.completed_at = time.time()

        self._completed_workers.append(task)

        # Integrate learnings
        if learnings:
            for learning in learnings:
                self.learn(learning, source=f"worker:{task_id}")

        # Gain experience from completed work
        self.knowledge.gain_experience(1.0, f"task:{task_id}")

        return True

    # =========================================================================
    # LEARNING - How the fairy grows
    # =========================================================================

    def learn(self, content: str, source: str = "experience") -> None:
        """
        Learn something new and integrate it into knowledge foundation.
        """
        self._total_learnings += 1

        # Record the learning
        learning_record = {
            "content": content,
            "source": source,
            "timestamp": time.time(),
            "mastery_at_time": self.knowledge.mastery_level,
        }

        # Check if this is a pattern
        if "pattern" in content.lower() or "when" in content.lower():
            pattern_name = f"pattern_{self._total_learnings}"
            self.knowledge.learned_patterns[pattern_name] = learning_record

        # Check if this is a connection
        if "connects" in content.lower() or "relates" in content.lower():
            self.knowledge.discovered_connections.append(learning_record)
            # Prune to prevent unbounded growth (keep last 200)
            if len(self.knowledge.discovered_connections) > 200:
                self.knowledge.discovered_connections = self.knowledge.discovered_connections[-200:]

        # Gain experience
        leveled_up = self.knowledge.gain_experience(0.5, source)

        # Generate learning thought
        self.think(
            f"Learning: {content[:50]}...",
            context={"cause": source, "intensity": 0.7 if leveled_up else 0.5},
            thought_type="learning",
        )

        # Callback
        if self._on_learning:
            try:
                self._on_learning(content, learning_record)
            except Exception:
                pass

        # Save to personal SRM
        self._save_to_srm(learning_record)

    def _save_to_srm(self, record: Dict[str, Any]) -> None:
        """Save a record to the fairy's personal SRM partition."""
        try:
            partition_path = Path(self.srm_partition)
            memories_file = partition_path / "memories.jsonl"

            with open(memories_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

    def recall_from_srm(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Recall memories from personal SRM that match query."""
        results = []

        try:
            partition_path = Path(self.srm_partition)
            memories_file = partition_path / "memories.jsonl"

            if memories_file.exists():
                with open(memories_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            record = json.loads(line)
                            content = record.get("content", "").lower()
                            if query.lower() in content:
                                results.append(record)
                                if len(results) >= limit:
                                    break
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass

        return results

    # =========================================================================
    # WIRING - Connect to system components
    # =========================================================================

    def wire_association_cortex(self, cortex) -> None:
        """Wire to the AssociationCortex for relational exploration."""
        self._association_cortex = cortex

    def wire_fabric(self, fabric: 'TensorFabric') -> None:
        """Wire to the TensorFabric for postal communication."""
        self.fabric = fabric

    def set_thought_callback(self, callback: Callable[[FairyThought], None]) -> None:
        """Set callback for new thoughts."""
        self._on_thought = callback

    def set_learning_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Set callback for new learnings."""
        self._on_learning = callback

    # =========================================================================
    # INTROSPECTION - How the fairy understands itself
    # =========================================================================

    def recent_thoughts(self, n: int = 10) -> List[FairyThought]:
        """Get recent thoughts."""
        with self._lock:
            return list(self._thoughts)[-n:]

    def stream_of_consciousness(self, n: int = 10) -> str:
        """Get recent thoughts as flowing text."""
        thoughts = self.recent_thoughts(n)
        return " ... ".join(t.content for t in thoughts)

    def status(self) -> Dict[str, Any]:
        """Get inner mind status."""
        return {
            "fairy_name": self.fairy_name,
            "knowledge": self.knowledge.to_dict(),
            "thoughts_count": len(self._thoughts),
            "total_thoughts": self._total_thoughts,
            "active_workers": len(self._active_workers),
            "total_workers_spawned": self._total_workers_spawned,
            "total_learnings": self._total_learnings,
            "srm_partition": self.srm_partition,
            "has_association_cortex": self._association_cortex is not None,
            "has_fabric": self.fabric is not None,
            # SOMATIC AND SENSORY STATE
            "somatic": self.somatic.to_dict(),
            "senses": self.senses.to_dict(),
            "felt_sense": self.somatic.to_felt_sense(),
            "position": self.senses.where_am_i(),
        }

    def feel(self) -> str:
        """
        Get the fairy's current felt sense - embodied state in words.

        This is the fairy checking in with its body.
        """
        felt = self.somatic.to_felt_sense()
        position = self.senses.where_am_i()
        return f"I feel: {felt}. {position}"

    def receive_heartbeat(self, timestamp: float, heart_rate: float) -> None:
        """
        Receive the system heartbeat - sync with the body.

        This connects the fairy to the overall system embodiment.
        """
        self.somatic.feel_heartbeat(heart_rate)
        self.senses.sense_heartbeat(timestamp, heart_rate)

        # Update worker count in senses
        self.senses.worker_clones_out = len(self._active_workers)

    def after_work(self, intensity: float, success: bool) -> None:
        """
        Called after doing work - updates somatic state.

        Work affects the fairy's energy, strain, and satisfaction.
        """
        self.somatic.update_from_work(intensity, success)

        # Also generate a feeling thought if significant
        if intensity > 0.5:
            felt = self.somatic.to_felt_sense()
            self.think(
                f"After that work, I feel: {felt}",
                context={
                    "cause": "work_completed",
                    "intensity": intensity,
                    "valence": self.somatic.valence,
                },
                thought_type="feeling",
            )

    def rest_tick(self) -> None:
        """
        Called during rest - fairy recovers.

        Fairies need rest to maintain vitality.
        """
        self.somatic.rest(0.05)

    def sense_system(self, load: float, postal_flow: float, active_fairies: int) -> None:
        """
        Sense the overall system state.

        Fairies are aware of their community.
        """
        self.senses.sense_system_load(load)
        self.senses.sense_postal_traffic(postal_flow)
        self.senses.sense_community(active_fairies, len(self._active_workers))

    def reflect(self) -> FairyThought:
        """
        Reflect on current state - meta-cognition.

        This is the fairy thinking about its own thinking AND feeling.
        """
        felt_sense = self.somatic.to_felt_sense()
        position = self.senses.where_am_i()

        reflection = (
            f"I am {self.fairy_name}, a {self.knowledge.mastery_level} "
            f"in the domain of {self.knowledge.domain}. "
            f"My mantra: '{self.knowledge.mantra}'. "
            f"I have thought {self._total_thoughts} thoughts and "
            f"learned {self._total_learnings} things. "
            f"I have {len(self._active_workers)} workers active. "
            f"I feel: {felt_sense}. "
            f"I am: {position}."
        )

        return self.think(
            reflection,
            context={
                "cause": "self-reflection",
                "intensity": 0.6,
                "valence": self.somatic.valence,
                "arousal": self.somatic.arousal,
            },
            thought_type="feeling",
        )


# =============================================================================
# INNER MIND MIXIN - Add to any fairy
# =============================================================================

class InnerMindMixin:
    """
    Mixin that gives any fairy an inner mind.

    Usage:
        class MyFairy(InnerMindMixin, Fairy):
            INNER_MIND_CONFIG = {
                "domain": "my domain",
                "mantra": "my mantra",
                "intent": "what I do",
                "purpose": "why I exist",
            }
    """

    INNER_MIND_CONFIG: Dict[str, str] = {}

    def _init_inner_mind(self, fabric=None) -> None:
        """Initialize the inner mind (call in __init__ or on_boot)."""
        config = getattr(self, 'INNER_MIND_CONFIG', {})
        fairy_name = getattr(self, 'ACTOR_NAME', self.__class__.__name__)

        self.inner_mind = FairyInnerMind(
            fairy_name=fairy_name,
            domain=config.get("domain", "general"),
            mantra=config.get("mantra", "I serve"),
            intent=config.get("intent", "to function"),
            purpose=config.get("purpose", "to help"),
            fabric=fabric,
        )

    def think(self, stimulus: str, **kwargs) -> FairyThought:
        """Think about something."""
        if not hasattr(self, 'inner_mind'):
            raise RuntimeError("Inner mind not initialized. Call _init_inner_mind() first.")
        return self.inner_mind.think(stimulus, **kwargs)

    def learn(self, content: str, source: str = "experience") -> None:
        """Learn something new."""
        if hasattr(self, 'inner_mind'):
            self.inner_mind.learn(content, source)

    def spawn_worker(self, requester: str, intent: str, **kwargs) -> WorkerTask:
        """Spawn a worker to handle a task."""
        if not hasattr(self, 'inner_mind'):
            raise RuntimeError("Inner mind not initialized.")
        return self.inner_mind.spawn_worker(requester, intent, **kwargs)

    def feel(self) -> str:
        """Get current felt sense - check in with the body."""
        if hasattr(self, 'inner_mind'):
            return self.inner_mind.feel()
        return "No inner mind - cannot feel"

    def receive_heartbeat(self, timestamp: float, heart_rate: float) -> None:
        """Receive system heartbeat - sync with embodiment."""
        if hasattr(self, 'inner_mind'):
            self.inner_mind.receive_heartbeat(timestamp, heart_rate)

    def after_work(self, intensity: float, success: bool) -> None:
        """Called after doing work - update somatic state."""
        if hasattr(self, 'inner_mind'):
            self.inner_mind.after_work(intensity, success)

    def rest_tick(self) -> None:
        """Called during rest - recover energy."""
        if hasattr(self, 'inner_mind'):
            self.inner_mind.rest_tick()

    def sense_system(self, load: float, postal_flow: float, active_fairies: int) -> None:
        """Sense the overall system state."""
        if hasattr(self, 'inner_mind'):
            self.inner_mind.sense_system(load, postal_flow, active_fairies)

    def reflect(self) -> Optional[FairyThought]:
        """Reflect on current state - meta-cognition with feeling."""
        if hasattr(self, 'inner_mind'):
            return self.inner_mind.reflect()
        return None
