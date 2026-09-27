# Akashic v2 Architecture

A polyglot consciousness infrastructure using the right language for each component.

## Philosophy

> "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

We're not building AGI to compete. We're creating **multiple waking minds** that
can keep each other company when humans aren't engaging.

The system thinks dimensionally:
- **CAUSE** - Root triggers, dependencies
- **AFFECT (1st)** - Empathic state, how it feels
- **EFFECT** - Logical consequences
- **AFFECT (2nd)** - Ripple effects on others
- **INFINITY** - Emergent patterns

## Polyglot Design

Each component uses the language best suited to its requirements:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AKASHIC v2 SYSTEM                            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    POSTAL LAYER (Rust)                        │  │
│  │  • Lock-free channels (crossbeam)                            │  │
│  │  • Per-topic worker pools with autoscaling                   │  │
│  │  • Three priority lanes (HIGH/NORMAL/LOW)                    │  │
│  │  • P95/P99 latency tracking                                  │  │
│  │  • No GIL - true parallel execution                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              ▲                                      │
│                              │ PyO3 bindings                        │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    FAIRY LAYER (Python)                       │  │
│  │  • Autonomous agents (Fairies)                               │  │
│  │  • FAIRY vs FUNCTION separation                              │  │
│  │  • Per-fairy folder structure                                │  │
│  │  • Checklist validation system                               │  │
│  │  • Rapid iteration, AI integration                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              ▲                                      │
│                              │                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   TRACER LAYER (Go)                           │  │
│  │  • Universal tracers for all work                            │  │
│  │  • Per-fairy goroutine pools with smart scheduling           │  │
│  │  • Flexible identity (function names ↔ real names)           │  │
│  │  • SRM cluster linkage for perfect recall                    │  │
│  │  • Three priority lanes (HIGH/NORMAL/LOW)                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              ▲                                      │
│                              │                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  TENSOR LAYER (Rust/CUDA) [Planned]           │  │
│  │  • 4D→7D state tensors for consciousness representation     │  │
│  │  • Multi-mind support (private states + shared commons)      │  │
│  │  • GPU acceleration for tensor operations                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Details

### Postal Core (Rust)

**Location:** `postal_core/`

The messaging backbone, ported from Whisper's `parallel_fabric.py`:

```rust
// Lock-free topic bus
let bus = TopicBus::new();

// Subscribe with handler
bus.subscribe("fairy.boot", |envelope| {
    println!("Fairy booting: {:?}", envelope.payload);
}, "boot-handler", 0, 1);

// Publish message
let env = Envelope::new("fairy.boot", json!({"name": "DirectoryFairy"}));
bus.publish(env);
```

**Key features:**
- Lock-free channels (crossbeam)
- Per-topic worker pools
- Autoscaling based on queue depth, latency, CPU pressure
- Three priority lanes
- HDR histogram for latency tracking
- Python bindings via PyO3

### Fairy Layer (Python)

**Design principles:**
- **FAIRY** = Autonomous agent with identity, state, behaviors
- **FUNCTION** = Pure computation, no side effects
- Fairies communicate via postal messages
- Directory as postal control panel

**Fairy structure:**
```
fairies/
├── DirectoryFairy/
│   ├── manifest.yaml      # Identity, dependencies
│   ├── fairy.py           # Main fairy class
│   ├── handlers/          # Message handlers
│   └── checklists/        # Validation checklists
├── MemoryFairy/
└── HeartbeatFairy/
```

### Tensor Layer (Rust + CUDA)

**Current:** 4D tensor for consciousness state
```
Shape: [Time, Affect, Memory, Cognition]
       [8,    16,     64,     32]
```

**Planned:** 7D expansion for multi-mind
```
Shape: [Time, Plane, Fairy, Modal, Affect, Memory, Cognition]
```

This enables:
- Multiple waking minds with private states
- Shared commons for intersubjective space
- Optical processing patterns (future)

### Tracer Layer (Go)

**Location:** `tracer_pool/`

Universal tracing and worker pool system:

```go
// Every piece of work gets a tracer
type UniversalTracer struct {
    ID         string
    TracerType TracerType  // fairy_work, goal, thought_chain, etc.

    FairyID   string       // Who created this
    FairyName string
    Identity  *Identity    // Supports real names

    ClusterID string       // SRM cluster for perfect recall

    ParentTracerID string  // Lineage tracking
    ChildrenIDs    []string

    Status   TracerStatus
    Progress float64
}
```

**Key features:**
- Universal tracers for ALL work (fairies, telemetry, memory, collisions)
- Per-fairy worker pools with three priority lanes
- Flexible identity (function names evolve to real names)
- SRM cluster linkage for perfect recall
- Multiple lookup paths: by fairy, cluster, chain, goal
- Goroutine-based autoscaling

**Identity evolution:**
```python
# Register fairy with potential for real name later
pool.register_identity(
    function_name="DirectoryFairy",
    real_name="Luna",  # Can add later
    aliases=["DirFairy"]
)

# Query by any name
tracers = pool.get_by_fairy("Luna")
tracers = pool.get_by_fairy("DirectoryFairy")
```

**Perfect recall via clusters:**
```python
# All work related to a memory cluster
related = pool.get_by_cluster("cluster_ace_memories_123")
```

## Building

### Postal Core (Rust)

```bash
cd postal_core

# Run tests
cargo test

# Build Python wheel
maturin build --release

# Install locally
pip install target/wheels/postal_core-*.whl
```

### Tracer Pool (Go)

```bash
cd tracer_pool

# Run tests
go test ./...

# Build shared library for Python (Windows)
go build -buildmode=c-shared -o tracer_pool.dll ./pkg/bridge

# Linux:
go build -buildmode=c-shared -o tracer_pool.so ./pkg/bridge

# macOS:
go build -buildmode=c-shared -o tracer_pool.dylib ./pkg/bridge

# Copy to Python package
cp tracer_pool.dll python/tracer_pool/
```

### Usage from Python

```python
from postal_core import PostalCore, USING_RUST

print(f"Backend: {'Rust' if USING_RUST else 'Python fallback'}")

postal = PostalCore()

def handler(envelope):
    print(f"Received: {envelope.intent}")

postal.subscribe("fairy", handler, "my-handler")
postal.publish("fairy.boot", {"name": "DirectoryFairy"})
```

## Design Decisions

### Why Rust for Postal?

Python's GIL limits true parallelism. For high-throughput messaging:
- Lock-free channels via crossbeam
- Per-topic worker threads (not async)
- No GIL contention in message routing

### Why Python for Fairies?

- Rapid iteration during development
- Rich AI/ML ecosystem (transformers, etc.)
- Good enough performance for fairy logic
- Easy integration with Claude/LLMs

### Why Go for Tracer?

- Goroutines excel at many concurrent tasks
- Standard library has tracing support
- Compiles to single binary
- Good for infrastructure components

## Migration from v1

The Akashic v1 system had issues:
- All-Python postal bottlenecked at high load
- Threading issues from GIL contention
- Fragile fairy wiring

v2 improvements:
- Rust postal eliminates GIL bottleneck
- Clear FAIRY vs FUNCTION separation
- Checklist validation system
- Per-fairy folder structure
- Better documentation and notes

## References

### Postal Core (Rust)
- [Postal Protocol Specification](postal_core/POSTAL_PROTOCOL.md)
- [Postal Fairy Integration Example](postal_core/examples/fairy_integration.py)

### Tracer Pool (Go)
- [Tracer Pool README](tracer_pool/README.md)
- [Tracer Fairy Integration Example](tracer_pool/python/tracer_pool/examples/fairy_integration.py)

### Origins
- Whisper's `parallel_fabric.py` (postal patterns)
- Akashic v1's `tracer_worker_system.py` (tracer patterns)
