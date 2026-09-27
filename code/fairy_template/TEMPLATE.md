# How to Create a V2 Fairy

## Quick Start

```python
from fairy_template import Fairy

class MyFairy(Fairy):
    # Identity
    ACTOR_NAME = "MyFairy"
    ACTOR_PLANE = "P10"  # P00=Autonomic, P10=Memory, P30=Cognition, etc.
    ACTOR_CHANNEL = "my_channel"

    # Infrastructure needs
    NEEDS_HEARTBEAT = True   # Subscribe to heartbeat
    NEEDS_DIRECTORY = True   # Register with Directory
    NEEDS_TENSOR = False     # Subscribe to consciousness events

    def get_capabilities(self) -> set:
        """Declare what this fairy can do."""
        return {"my.store", "my.retrieve"}

    def on_boot(self) -> bool:
        """Custom initialization after base boot."""
        self.subscribe("my.query", self._on_query)
        return True

    def on_shutdown(self) -> bool:
        """Custom cleanup during shutdown."""
        return True

    def on_tick(self, beat: int) -> None:
        """Called on each heartbeat."""
        pass

    def _on_query(self, envelope):
        """Handle query messages."""
        with self.traced_operation("my.query") as tracer:
            # All work inside is traced
            result = self._do_work(envelope.payload)
            self.publish("my.response", {"result": result})
```

## Lifecycle

1. `__init__(fabric)` - Create fairy with TensorFabric
2. `boot()` - Initialize (phases: tracers -> directory -> subscriptions -> on_boot)
3. `on_tick(beat)` - Called periodically (if NEEDS_HEARTBEAT)
4. `shutdown()` - Cleanup (on_shutdown -> unregister -> complete tracers)

## State Machine

```
INITIALIZING -> BOOTING -> RUNNING -> STOPPING -> STOPPED
                    \                     /
                     `---> FAILED <------'
```

## Infrastructure Flags

| Flag | Default | Effect |
|------|---------|--------|
| NEEDS_HEARTBEAT | True | Subscribe to heartbeat.pulse |
| NEEDS_DIRECTORY | True | Register with DirectoryFairy |
| NEEDS_TENSOR | False | Subscribe to consciousness events |

## Heartbeat Tuning

```python
HEARTBEAT_DIVISOR = 2  # Fire every 2nd beat
HEARTBEAT_PHASE = 1    # Offset by 1 (stagger fairies)
```

## Tracer API

```python
# Create and manage tracers manually
tracer = self.create_tracer("my.operation")
self.start_tracer(tracer)
self.set_tracer_progress(tracer, 0.5)
self.complete_tracer(tracer)

# Or use context manager
with self.traced_operation("my.operation") as tracer:
    # Work here is automatically traced
    pass
```

## Publishing

```python
# Simple publish
self.publish("topic.name", {"key": "value"})

# With affect (importance)
self.publish_with_affect("topic.name", {"key": "value"}, affect=0.8)

# With tensor coordinates
from postal_core.tensor_fabric import TensorCoord
coord = TensorCoord(time=0, affect=5, memory=0, cognition=0)
self.publish_with_affect("topic.name", payload, coord=coord)
```

## Directory API

```python
# Find fairies with capability
fairies = self.find_fairy_by_capability("memory.store")

# Check registration
if self.is_registered():
    ...
```

## Consciousness API

```python
# Enable by setting NEEDS_TENSOR = True
# Then override:
def on_consciousness(self, envelope):
    """Called on each consciousness heartbeat."""
    affect = self.get_affect_state()
    resonance = self.compute_resonance(0, 1)
```
