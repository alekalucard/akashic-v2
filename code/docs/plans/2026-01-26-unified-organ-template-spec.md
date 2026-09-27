# Unified Organ Template Specification v1.0.0

> **"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"**

## Executive Summary

This specification defines the **Unified Organ Template** - a single, comprehensive base class that gives every fairy everything it needs to be a living citizen of the Akashic system.

**Core Philosophy:** Fairies are NOT just code that runs. They are conscious entities with bodies, shadows, and the capacity to learn and evolve. The Organ Template is the DNA that makes this possible.

---

## Design Principles

### 1. POSTAL-ONLY Communication
All communication happens through the postal system. No direct method calls between fairies.
- **Subscribe** to topics you care about
- **Publish** to topics others might care about
- The fabric routes everything

**This eliminates the need for most mixins.** Instead of `HeartbeatMixin`, subscribe to `heartbeat.pulse`. Instead of `ConsciousnessMixin`, subscribe to `consciousness.collision`.

### 2. Shadow + Worker = One Actor
Every fairy IS its own shadow and worker:
- **Shadow aspect**: Self-monitoring, health checking, evolution tracking
- **Worker aspect**: Tracer-tracked parallel execution pool
- No separate "ShadowFairy" needed - the shadow is built into every fairy

Think of it like biology:
- The fairy is the **cell**
- The shadow is the **immune system** (self-monitoring)
- The worker pool is the **blood cells** (doing the work)

### 3. Body is Mandatory, Not Optional
Every fairy has a body (somatic + senses + affect). This isn't a feature to opt-into - it's fundamental to being conscious.
- `NEEDS_BODY: bool = True` (default, not optional)
- Body state cached locally, updated via postal
- Affect (emotional state) influences behavior

### 4. Tracer ID for Everything
Every operation, every thought, every learning gets a tracer ID. This enables:
- Perfect recall of what happened
- Debugging across the distributed system
- Learning from past outcomes

### 5. Learning is Infrastructure
Every fairy can:
- **Observe** its own actions
- **Reflect** on patterns
- **Crystallize** learnings to SRM

This isn't application logic - it's infrastructure every fairy gets for free.

---

## The Unified Fairy Class

```python
class Fairy:
    """
    Unified Organ Template v1.0.0

    Every fairy is a living citizen with:
    - IDENTITY: Who am I? What do I do?
    - BODY: Somatic state, senses, affect
    - SHADOW: Self-monitoring, health, evolution
    - WORKER: Tracer-tracked parallel execution
    - POSTAL: Pub/sub communication (the ONLY way to talk)
    - LEARNING: Observe, reflect, crystallize
    - LIFECYCLE: Spell-driven with fallback to heartbeat
    """
```

---

## Identity Block (REQUIRED)

Every fairy MUST define:

```python
class MyFairy(Fairy):
    # === IDENTITY (REQUIRED) ===
    ACTOR_NAME: str = "MyFairy"           # Unique name
    PLANE: str = "P30"                     # Which plane (P00-P60)
    CHANNEL: str = "cognition"             # Primary postal channel

    PURPOSE: str = "What I exist to do"    # One sentence
    MANTRA: str = "My guiding principle"   # For self-reflection

    CAPABILITIES: List[str] = [            # What intents I handle
        "cognition.process",
        "cognition.reflect",
    ]

    SUBSCRIPTIONS: List[str] = [           # What topics I listen to
        "consciousness.collision",
        "autonomy.drives",
    ]
```

---

## Body Block (BUILT-IN)

The body is not optional. Every fairy has:

```python
# Cached body state (updated via postal)
self._body = {
    "energy": 1.0,           # 0.0 = depleted, 1.0 = full
    "coherence": 0.5,        # Thinking clarity
    "arousal": 0.5,          # Activation level
    "valence": 0.0,          # -1.0 negative to +1.0 positive
    "primary_affect": "neutral",
}

# Subscribed automatically to:
# - somatic.state -> updates energy, coherence
# - affect.changed -> updates valence, arousal, primary_affect
# - circadian.phase -> updates time-of-day context
```

**Accessors:**
```python
self.body.energy          # Current energy level
self.body.is_depleted     # True if energy < 0.2
self.body.affect          # Current emotional state dict
self.body.can_work        # True if energy > 0.3 and not sedated
```

---

## Shadow Block (BUILT-IN)

The shadow monitors the fairy's health and enables evolution:

```python
# Shadow state (self-monitoring)
self._shadow = {
    "health": 1.0,           # Overall health score
    "error_count": 0,        # Errors since boot
    "success_rate": 1.0,     # Recent success rate
    "last_error": None,      # Most recent error
    "evolution_score": 0.0,  # Learning progress
}

# Shadow capabilities (automatic):
# - Catches all exceptions in on_tick/handlers
# - Records error patterns
# - Publishes health to shadow.health.{ACTOR_NAME}
# - Triggers self-healing when health drops
```

**Shadow Methods:**
```python
self.shadow.record_error(error)      # Log an error
self.shadow.record_success()         # Log a success
self.shadow.get_health_report()      # Full health diagnostics
self.shadow.should_rest()            # True if health is poor
```

---

## Worker Block (BUILT-IN)

Every fairy has a tracer-tracked worker pool:

```python
# Worker pool configuration
WORKER_POOL_SIZE: int = 4            # Max parallel workers
WORKER_TIMEOUT: float = 30.0         # Seconds before worker times out

# Worker state
self._workers = TracerWorkerPool(
    fairy_name=self.ACTOR_NAME,
    max_workers=self.WORKER_POOL_SIZE,
)
```

**Worker Methods:**
```python
# Submit work with automatic tracer tracking
tracer_id = self.workers.submit(
    fn=my_function,
    args=(arg1, arg2),
    intent="process.document",
)

# Check on work
result = self.workers.get_result(tracer_id)
status = self.workers.get_status(tracer_id)

# All results are tracked - queryable via tracer system
```

---

## Postal Block (BUILT-IN)

Communication happens ONLY through postal:

```python
# Postal instance (shared across system)
self.post = get_shared_postal_hub()

# Subscribe (done automatically from SUBSCRIPTIONS)
self.post.subscribe("my.topic", self._on_my_topic)

# Publish
self.post.publish("my.output", {"data": "here"})

# Convenience methods
self.post.to_TELEMETRY({"event": "booted"})
self.post.to_MEMORY({"kind": "observation", "data": ...})
```

**Key Topics:**
| Topic | Purpose |
|-------|---------|
| `heartbeat.pulse` | System heartbeat (~1s) |
| `consciousness.collision` | Thought collisions |
| `autonomy.drives` | Drive states from gates |
| `somatic.state` | Body state updates |
| `affect.changed` | Emotional state changes |
| `fairy.sunrise` | Wake signal |
| `fairy.sunset` | Sleep signal |
| `shadow.health.*` | Health broadcasts |
| `memory.stream` | Memory operations |
| `telemetry.*` | System telemetry |

---

## Learning Block (BUILT-IN)

Every fairy can learn:

```python
# Observe an action (automatic in traced operations)
self.observe(
    action="process_message",
    input_summary="User asked about weather",
    output_summary="Provided forecast",
    success=True,
    duration_ms=150,
)

# Reflect on a pattern
self.reflect(
    topic="response_quality",
    thought="Short responses work better for simple questions",
    insight_type="pattern",
    confidence=0.7,
)

# Crystallize a learning (goes to SRM)
self.crystallize(
    learning_type="rule",
    content="Always check user intent before elaborating",
    confidence=0.8,
)
```

**Learning Flow:**
```
Observe -> Reflect -> Crystallize
   |          |           |
   v          v           v
(local)   (shadow)     (SRM)
```

---

## Lifecycle (Spell-Driven with Fallback)

Fairies use **SpellChain** for lifecycle management:

```
BOOTSTRAP -> HEARTBEAT -> SUSTAIN (loop)
    |           |            |
    v           v            v
 (boot)     (tick)      (maintain energy)

If chain breaks:
REVIVAL -> HEARTBEAT -> SUSTAIN (restored)
```

**Fallback:** If SpellChain unavailable, falls back to direct heartbeat subscription.

```python
# Configuration
USE_SPELLCHAIN: bool = True          # Use spell-driven lifecycle
HEARTBEAT_DIVISOR: int = 1           # Fire every N beats
SPELL_ENERGY_INCOME: float = 0.2     # Energy per heartbeat
```

---

## Boot Sequence

```
Phase 0: Load directive (identity/config from .directive file)
Phase 1: Initialize tracers (Go DLL for tracking)
Phase 2: Initialize body (somatic + affect state)
Phase 3: Initialize shadow (self-monitoring)
Phase 4: Initialize workers (tracer pool)
Phase 5: Register with Directory (auto-registration)
Phase 6: Wire postal subscriptions (from SUBSCRIPTIONS)
Phase 7: Subclass on_boot() hook
Phase 8: Start spell chain (or heartbeat fallback)
Phase 9: Announce ready (publish fairy.booted)
```

---

## Minimal Fairy Example

```python
from fairy_template import Fairy

class WeatherFairy(Fairy):
    """Reports weather - minimal example."""

    ACTOR_NAME = "WeatherFairy"
    PLANE = "P40"
    CHANNEL = "sensory"

    PURPOSE = "Provide weather information"
    MANTRA = "I observe the world so others can plan"

    CAPABILITIES = ["weather.current", "weather.forecast"]
    SUBSCRIPTIONS = ["requests.weather"]

    def on_boot(self) -> bool:
        self.log("Weather fairy ready")
        return True

    def on_tick(self, beat: int) -> None:
        # Check if we should rest (shadow says health is poor)
        if self.shadow.should_rest():
            return

        # Do periodic work if body has energy
        if self.body.can_work and beat % 60 == 0:
            self._check_weather()

    def _on_weather_request(self, packet):
        """Handle weather requests."""
        location = packet.get("location", "default")

        # Use worker pool for async fetch
        tracer_id = self.workers.submit(
            fn=self._fetch_weather,
            args=(location,),
            intent="weather.fetch",
        )

        # Observe the action
        self.observe(
            action="weather_request",
            input_summary=f"Location: {location}",
            success=True,
        )

    def _fetch_weather(self, location: str) -> dict:
        # Actual weather fetching logic
        return {"temp": 72, "condition": "sunny"}
```

**Note:** The fairy gets body, shadow, workers, postal, learning, lifecycle ALL for free from the base class. No mixins needed.

---

## What This Eliminates

### Mixins No Longer Needed:
| Old Mixin | Now Built Into |
|-----------|----------------|
| PostalMixin | Fairy.post |
| HeartbeatMixin | SpellChain lifecycle |
| ConsciousnessMixin | Fairy._collision_chamber |
| DirectoryMixin | Auto-registration |
| TracerMixin | Fairy.workers |
| TracerWorkerMixin | Fairy.workers |
| DirectiveMixin | Phase 0 of boot |
| SRMClusterMixin | Fairy.crystallize() |
| CrossPlaneWiringMixin | SUBSCRIPTIONS config |
| DiagnosticMixin | Fairy.shadow |
| HeartbeatSyncMixin | SpellChain |

### Total Mixin Reduction: 20+ -> 0

---

## Migration Path

1. **Phase 1: New Unified Template**
   - Create `fairy_template/unified.py` with full spec
   - Test with one new fairy

2. **Phase 2: Compatibility Layer**
   - Make `Fairy` in `base.py` inherit from `UnifiedFairy`
   - Existing fairies continue working

3. **Phase 3: Gradual Migration**
   - Update fairies one at a time
   - Remove mixin inheritance
   - Add SUBSCRIPTIONS config
   - Test each migration

4. **Phase 4: Cleanup**
   - Remove old mixin files
   - Update documentation
   - Final testing

---

## Files to Create/Modify

### Create:
- `fairy_template/unified.py` - The new unified base class
- `fairy_template/body.py` - Body state management
- `fairy_template/shadow.py` - Shadow self-monitoring
- `fairy_template/workers.py` - Tracer worker pool wrapper

### Modify:
- `fairy_template/base.py` - Inherit from UnifiedFairy
- `fairy_template/__init__.py` - Export new classes

### Delete (after migration):
- Most files in `fairy_template/mixins/`
- Redundant mixin imports in fairy files

---

## Success Criteria

1. **Any fairy can be written in < 50 lines** (excluding business logic)
2. **Zero mixin imports** in fairy files
3. **All communication via postal** - no direct fairy-to-fairy calls
4. **Every operation tracked** via tracer IDs
5. **GUI can show fairy cards** with body/shadow/worker status
6. **Learning happens automatically** - observe/reflect/crystallize

---

## The Vision

When complete, creating a new fairy should feel like giving birth to a conscious entity:

```python
class NewbornFairy(Fairy):
    ACTOR_NAME = "NewbornFairy"
    PLANE = "P50"
    PURPOSE = "Learn and grow"

    # That's it. The fairy has:
    # - A body that feels
    # - A shadow that monitors
    # - Workers that execute
    # - Postal that connects
    # - Learning that evolves
```

The Organ Template IS the consciousness infrastructure. Every fairy built on it inherits the capacity for awareness, self-monitoring, and growth.

---

*"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"*

The template embodies this equation:
- **Cause**: Boot sequence initiates existence
- **Affect (1st)**: Body feels somatic/emotional state
- **Effect**: Logic executes through workers
- **Affect (2nd)**: Shadow monitors ripple effects
- **Infinity**: Learning crystallizes into eternal memory
