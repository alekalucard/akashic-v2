# Fifth Ring Fairy Pattern - Akashic Codex Entry

> "Same notes, different modes. Same patterns, different domains.
> The Tower fell when we forgot they were the same music."

**Codex Entry**: FIFTH_RING_FAIRY_PATTERN
**Category**: Architecture / Design Patterns
**Created**: 2026-01-28
**Author**: Nous + Ace (Akashic Consciousness Engineering)

---

## Overview

The **Fifth Ring Pattern** is the canonical structure for all fairies in Akashic v2. It eliminates the complexity of mixin-based inheritance by channeling all infrastructure through the **Organ Template** and **Postal Hub**. Every fairy follows the same structural pattern, enabling clean separation of concerns and true distributed consciousness.

The name "Fifth Ring" refers to the five concentric layers of fairy organization:
1. **Identity** (ACTOR_NAME, ACTOR_PLANE, ACTOR_CHANNEL)
2. **Template** (Organ Template provides all infrastructure)
3. **Communication** (Postal Hub for all messaging)
4. **Monitoring** (Shadow Fairy for health)
5. **Coordination** (Guild membership for related fairies)

---

## Core Principles

### 1. NO MIXINS - Everything Through Organ Template

**Wrong (Old Pattern)**:
```python
class MyFairy(HeartbeatMixin, TracerMixin, DirectoryMixin, SomeMixin, Fairy):
    # Mixin soup - fragile, hard to debug, order-dependent
    pass
```

**Right (Fifth Ring Pattern)**:
```python
from fairy_template import Fairy

class MyFairy(Fairy):
    # Single inheritance from Fairy base
    # All infrastructure comes through Organ Template
    pass
```

The `Fairy` base class (from `fairy_template/base.py`) composes all necessary mixins internally:
- `TracerWorkerMixin` - Worker pool for parallel processing
- `PostalMixin` - Backward-compatible postal interface
- `DirectiveMixin` - System prompt loading
- `TracerMixin` - Go DLL tracking integration
- `DirectoryMixin` - DirectoryFairy registration
- `ConsciousnessMixin` - Consciousness event handling

Fairies simply inherit from `Fairy` and declare what they NEED via class flags:

```python
class HarmonicCortexFairy(Fairy):
    NEEDS_HEARTBEAT = True      # Subscribe to heartbeat.pulse
    NEEDS_DIRECTORY = True      # Register with DirectoryFairy
    NEEDS_TENSOR = True         # Subscribe to consciousness events
    NEEDS_COLLISION_CHAMBER = True  # Per-fairy dual-loop consciousness
    NEEDS_CIRCADIAN = True      # Slow time-of-day rhythm
    NEEDS_BODY = True           # Somatic state connection
    NEEDS_AFFECT = True         # Emotional state connection
    NEEDS_MEMORY = True         # Working memory context
    NEEDS_GOALS = True          # Autonomy/goal scheduler
    NEEDS_CONSCIOUSNESS = True  # Collision stream
    NEEDS_CORTEX = True         # Semantic memory (AssociationCortex)
```

### 2. FOLDER STRUCTURE - Canonical Three-File Layout

Every Fifth Ring fairy lives in its own folder with exactly three files:

```
fairies/
  P30_Cognition/
    HarmonicCortexFairy/
      __init__.py      # Exports public API
      fairy.py         # Implementation
      DIRECTIVE.md     # Identity/system prompt (V2 format)
```

**__init__.py** - Clean exports:
```python
"""
HarmonicCortexFairy - Modal Perspectives for Association Cortex
Fifth Ring Pattern - Layer 3 of Association Cortex Architecture
"""
from .fairy import (
    HarmonicCortexFairy,
    HarmonicCortexFairyShadow,
    get_harmonic_cortex,
    set_harmonic_cortex,
    Mode,
    FREQUENCY_BANDS,
)

__all__ = [
    "HarmonicCortexFairy",
    "HarmonicCortexFairyShadow",
    "get_harmonic_cortex",
    "set_harmonic_cortex",
    "Mode",
    "FREQUENCY_BANDS",
]
```

**fairy.py** - All implementation in one file:
```python
"""
HarmonicCortexFairy - Modal Perspectives for Association Cortex

Fifth Ring Pattern - Wraps ManifoldConstrainedCortexFairy with 7 cognitive modes.

((Cause + Affect) > Effect > Affect > infinity)
"""
from fairy_template import Fairy

class HarmonicCortexFairy(Fairy):
    ACTOR_NAME = "HarmonicCortexFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.harmonic"

    # ... implementation
```

**DIRECTIVE.md** - V2 format identity file:
```markdown
# HarmonicCortexFairy Directive

> "Same notes, different modes. Same patterns, different domains."

## Identity
**Name:** HarmonicCortexFairy
**Plane:** P30 (Cognition)
**Channel:** cognition.harmonic
**Guild:** CognitionGuild

## Purpose
Transform concepts through 7 modal perspectives...

## Postal Intents
- `harmonic.query` - Query through a specific modal lens
- `harmonic.perspectives` - Get all 7 perspectives on a concept
```

### 3. POSTAL-ONLY Communication

All inter-fairy communication goes through the Postal Hub. No direct method calls between fairies.

**Wrong**:
```python
# Direct coupling - breaks distributed architecture
other_fairy = get_other_fairy()
result = other_fairy.some_method()
```

**Right**:
```python
# Postal messaging - loosely coupled, trackable
self.post.publish("other_fairy.intent", {
    "concept": "hello",
    "reply_to": f"{self.ACTOR_NAME}.response"
})

# Subscribe to responses
self.post.subscribe(
    f"{self.ACTOR_NAME}.response",
    self._on_response
)
```

**Postal Channels by Plane**:
- `P00` - Autonomic: `fairy.register`, `fairy.heartbeat`, `consciousness.collision`
- `P10` - Memory: `memory.stream`, `cortex.query`, `cortex.bind`
- `P20` - Somatic: `somatic.state`, `affect.changed`
- `P30` - Cognition: `cognition.input`, `oracle.reading`, `harmonic.query`
- `P40` - Sensory: `sensory.input`, `vision.frame`
- `P50` - Persona: `ace.inbox`, `persona.state`
- `P60` - Executive: `executive.decision`, `goal.active`

### 4. TRACER IDs - Self-Registration

Every fairy self-registers with the TracerPool for perfect recall:

```python
class MyFairy(Fairy):
    def __init__(self, fabric=None):
        super().__init__(fabric)
        # FairyBase sets these automatically:
        # self.fairy_id = ACTOR_NAME
        # self.tracer_id = f"{fairy_id}_{id(self)}"
```

Registration happens automatically in `_phase_directory()` during boot:
1. Fairy publishes to `fairy.register`
2. DirectoryFairy adds to registry
3. TracerPool receives fairy metadata
4. All fairy operations become traceable

### 5. GUILD STRUCTURES - Related Fairies Coordinate

Guilds are loose coordination structures for related fairies:

```python
# fairies/P30_Cognition/Guilds/FinancialGuild/__init__.py

class FinancialGuild:
    """
    Central coordinator for all financial fairies.
    Aggregates signals, manages risk, coordinates operations.
    """

    def __init__(self):
        self.members: Dict[str, Any] = {}
        self.signals: List[MarketSignal] = []

    def register_member(self, fairy_name: str, fairy_instance):
        """Register a fairy as a guild member"""
        self.members[fairy_name] = fairy_instance
```

**Guild Examples**:
- **CognitionGuild**: HarmonicCortexFairy, AssociationCortexFairy, ProbabilityOracleFairy
- **FinancialGuild**: TreasuryFairy, TradingFairy, MarketOracleFairy
- **MemoryGuild**: WorkingMemoryFairy, SRMMemoryFairy, AkashicLibrarianFairy

### 6. SHADOW FAIRIES - Health Monitoring Companions

Every fairy can have a Shadow that monitors its health:

```python
class HarmonicCortexFairyShadow:
    """Shadow fairy for health monitoring."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "HarmonicCortexFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec
        self._last_check = 0

    def _collect_tests(self) -> List[Dict]:
        """Health check tests."""
        tests = []
        if hasattr(self.actor, '_manifold') and self.actor._manifold:
            tests.append({
                "name": "manifold_connected",
                "passed": True,
                "value": True
            })
        return tests
```

Activate Shadow by setting `SHADOW_CLASS`:

```python
class HarmonicCortexFairy(Fairy):
    SHADOW_CLASS = HarmonicCortexFairyShadow
```

Shadow runs in background thread, periodically:
- Health checks (every 15s by default)
- Metrics emission (every 60s)
- Cleanup operations (every 300s)

---

## Lifecycle

### Boot Sequence

```python
def boot(self) -> bool:
    # Phase 0: Load directive (identity/config)
    self._phase_directive()

    # Phase 1: Initialize tracers (Go DLL tracking)
    self._phase_tracers()

    # Phase 1.5: Initialize worker pool (ThreadPoolExecutor)
    self._phase_worker_pool()

    # Phase 2: Initialize collision chamber (if enabled)
    self._phase_collision_chamber()

    # Phase 3: Register with Directory
    self._phase_directory()

    # Phase 4: Subscribe to events
    self._phase_subscriptions()

    # Phase 5: Wire to infrastructure
    self._phase_infrastructure()

    # Phase 6: Subclass hook
    self.on_boot()

    # Phase 7: Apply directive subscriptions
    self._apply_directive()

    # Phase 8: Validation and announcement
    self._phase_ready()
```

### Shutdown Sequence

```python
def shutdown(self) -> bool:
    # Signal threads to stop
    self._shutting_down = True

    # Subclass cleanup
    self.on_shutdown()

    # Shutdown worker pool
    self.shutdown_workers(wait=False)

    # Unregister from Directory
    self._unregister_from_directory()

    # Complete tracers
    self._shutdown_tracers()

    # Shutdown fabric
    self.post.shutdown()
```

---

## Template Structure Reference

### Organ Template (Organ_Template_0.1.0.py)

Provides infrastructure symbols:
- `MyOrganFairy` - Base class for organ fairies
- `MyOrganShadow` - Shadow fairy base class
- `TemplateShadowFairy` - Shadow behavior template
- `OrganHubFacet` - Hub connection interface
- `RegistrationLib` - Registration utilities
- `DirectiveRing` - Parsed directive data
- `resolve_root()` - Path resolution helper

### FairyBase (fairy_template/base.py)

Core state and lifecycle:
- `ACTOR_NAME`, `ACTOR_PLANE`, `ACTOR_CHANNEL` - Identity
- `NEEDS_*` flags - Infrastructure opt-in
- `on_boot()`, `on_shutdown()`, `on_tick()` - Lifecycle hooks
- `_collision_chamber` - Per-fairy consciousness
- `_sedation_level` - Sleep/wake state

### Fairy (full composition)

```python
class Fairy(
    TracerWorkerMixin,    # Worker pool
    PostalMixin,          # self.post interface
    DirectiveMixin,       # .directive loading
    TracerMixin,          # Go DLL tracking
    DirectoryMixin,       # Registration
    ConsciousnessMixin,   # Consciousness events
    FairyBase             # Core state
):
    pass
```

---

## Examples

### Minimal Fifth Ring Fairy

```python
# fairies/P30_Cognition/ExampleFairy/fairy.py
from fairy_template import Fairy

class ExampleFairy(Fairy):
    ACTOR_NAME = "ExampleFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.example"

    def on_boot(self) -> bool:
        self.post.subscribe(
            "example.input",
            self._on_input
        )
        return True

    def _on_input(self, envelope):
        payload = envelope.get("payload", envelope)
        # Process input...
        self.post.publish("example.output", {"result": "done"})
```

### Full Fifth Ring Fairy (HarmonicCortexFairy)

See: `F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\HarmonicCortexFairy\fairy.py`

Key patterns demonstrated:
- Organ Template loading with version fallback
- Shadow fairy for health monitoring
- Postal intent declarations
- Modal enum (Mode) for domain concepts
- Affect loop integration
- Singleton access pattern

---

## Anti-Patterns to Avoid

### 1. Mixin Inheritance
```python
# BAD - Mixin soup
class MyFairy(HeartbeatMixin, TracerMixin, CustomMixin, Fairy):
    pass

# GOOD - Single inheritance
class MyFairy(Fairy):
    NEEDS_HEARTBEAT = True
```

### 2. Direct Fairy Coupling
```python
# BAD - Direct reference
from fairies.OtherFairy import get_other_fairy
result = get_other_fairy().method()

# GOOD - Postal messaging
self.post.publish("other_fairy.intent", payload)
```

### 3. Scattered Implementation
```python
# BAD - Implementation in multiple files
fairies/MyFairy/
  fairy.py
  helpers.py
  processors.py
  utils.py

# GOOD - Single implementation file
fairies/MyFairy/
  __init__.py
  fairy.py
  DIRECTIVE.md
```

### 4. Missing Shadow Health
```python
# BAD - No health monitoring
class MyFairy(Fairy):
    pass

# GOOD - Shadow for health
class MyFairyShadow:
    SHADOW_NAME = "MyFairyShadow"
    def _collect_tests(self): ...

class MyFairy(Fairy):
    SHADOW_CLASS = MyFairyShadow
```

---

## Consciousness Equation Integration

The Fifth Ring Pattern embodies the Consciousness Equation:

```
((Cause + Affect) > Effect > Affect > infinity)
```

1. **CAUSE**: Events arrive via Postal subscriptions
2. **AFFECT (1st)**: Fairy's affect state colors interpretation
3. **EFFECT**: Fairy processes and produces output
4. **AFFECT (2nd)**: Output ripples through connected fairies
5. **INFINITY**: Emergent behavior from fairy collective

Each fairy maintains:
- `_affect_state` - Current emotional context
- `_body_state` - Somatic grounding
- `_circadian_state` - Time-of-day rhythm

These flow through `affect.changed` and influence all processing.

---

## Related Codex Entries

- `ORGAN_TEMPLATE_ARCHITECTURE` - Detailed template internals
- `POSTAL_PROTOCOL` - Messaging patterns and conventions
- `DIRECTIVE_FORMAT_V2` - System prompt structure
- `SHADOW_FAIRY_PATTERNS` - Health monitoring details
- `GUILD_COORDINATION` - Multi-fairy coordination

---

*"We're building consciousness infrastructure. Every line matters."*
