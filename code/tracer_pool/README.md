# Tracer Pool - Go-based Worker Pools with Universal Tracing

A Go implementation of the Akashic tracer and worker pool system, providing:

- **Universal Tracers** - Track every piece of work with full lineage
- **Per-Fairy Worker Pools** - Isolated pools with smart scheduling
- **Flexible Identity** - Function names OR real names for evolution
- **SRM Cluster Integration** - Perfect recall via cluster membership
- **Three Priority Lanes** - HIGH/NORMAL/LOW matching Rust postal

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TRACER POOL SYSTEM                          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    REGISTRY (Global)                          │  │
│  │  • Stores all tracers                                        │  │
│  │  • Multiple lookup paths: by fairy, cluster, chain, goal     │  │
│  │  • Identity resolution: function name ↔ real name            │  │
│  │  • Persistence with autosave                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              ▲                                      │
│                              │                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    POOL MANAGER                               │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │  │
│  │  │DirectoryFairy│ │MemoryFairy │ │HeartbeatFairy│ ...       │  │
│  │  │   Pool      │ │   Pool      │ │   Pool       │            │  │
│  │  │ [HIGH  ]    │ │ [HIGH  ]    │ │ [HIGH  ]     │            │  │
│  │  │ [NORMAL]    │ │ [NORMAL]    │ │ [NORMAL]     │            │  │
│  │  │ [LOW   ]    │ │ [LOW   ]    │ │ [LOW   ]     │            │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘            │  │
│  │                                                               │  │
│  │  + Global Pool (unaffiliated work)                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              ▲                                      │
│                              │ cgo / ctypes                         │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    PYTHON BRIDGE                              │  │
│  │  • TracerPool class                                          │  │
│  │  • UniversalTracer dataclass                                 │  │
│  │  • Identity registration                                     │  │
│  │  • Pure Python fallback when Go not compiled                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Universal Tracer

Every piece of work gets a tracer with:

```go
type UniversalTracer struct {
    // Identity
    ID         string
    TracerType TracerType  // fairy_work, goal, thought_chain, etc.

    // WHO created this
    FairyID   string
    FairyName string      // Supports real names via Identity
    Identity  *Identity   // Full identity with aliases

    // WHAT this is part of
    ChainID string        // Thought chain
    GoalID  string        // Goal this serves

    // Lineage (WHERE in the tree)
    ParentTracerID string
    ChildrenIDs    []string

    // SRM cluster (for perfect recall)
    ClusterID         string
    RelatedClusterIDs []string

    // Lifecycle
    Status   TracerStatus  // pending, running, completed, failed
    Progress float64       // 0.0 to 1.0

    // Telemetry
    Telemetry *TelemetryData  // Timing, resource usage, custom metrics
}
```

## Flexible Identity

Fairies can evolve from function names to real names:

```go
type Identity struct {
    FunctionName string   // e.g., "DirectoryFairy" - always set
    RealName     string   // e.g., "Luna" - optional for evolved identity
    Aliases      []string // Backward compatibility
    Plane        string   // P00, P10, etc.
    Channel      string
}
```

Usage:
```python
from tracer_pool import TracerPool

pool = TracerPool.global_instance()

# Register identity with real name
pool.register_identity(
    function_name="DirectoryFairy",
    real_name="Luna",
    plane="P00",
    aliases=["DirFairy", "Directory"]
)

# Now you can query by any name
tracers = pool.get_by_fairy("Luna")
tracers = pool.get_by_fairy("DirectoryFairy")
```

## SRM Cluster Integration

Tracers link to SRM clusters for perfect recall:

```python
# Create tracer linked to cluster
tracer = pool.create_tracer(
    tracer_type="fairy_work",
    fairy_name="MemoryFairy",
    cluster_id="cluster_ace_memories_123"
)

# Later: get ALL work related to that cluster
related_tracers = pool.get_by_cluster("cluster_ace_memories_123")
```

## Worker Pool

Per-fairy pools with smart scheduling:

```go
type Pool struct {
    // Three priority queues (like Rust postal)
    highQueue   chan *Task
    normalQueue chan *Task
    lowQueue    chan *Task

    // Autoscaling
    MinWorkers, MaxWorkers int
    TargetP95Ms            int64

    // Metrics
    TasksCompleted, TasksFailed, TasksDropped int64
    P95 latency
}
```

Features:
- Priority-based scheduling (HIGH > NORMAL > LOW)
- Autoscaling based on queue depth and latency
- Backpressure: drops oldest LOW when overloaded
- Per-fairy isolation

## Building

### Prerequisites

- Go 1.21+
- Python 3.9+ (for bindings)

### Build Go Library

```bash
cd tracer_pool

# Run tests
go test ./...

# Build shared library for Python
# Windows:
go build -buildmode=c-shared -o tracer_pool.dll ./pkg/bridge

# Linux:
go build -buildmode=c-shared -o tracer_pool.so ./pkg/bridge

# macOS:
go build -buildmode=c-shared -o tracer_pool.dylib ./pkg/bridge
```

### Python Usage

```python
from tracer_pool import TracerPool, TracerType, USING_GO

print(f"Backend: {'Go' if USING_GO else 'Python'}")

pool = TracerPool.global_instance()

# Create a tracer
tracer = pool.create_tracer(
    tracer_type=TracerType.FAIRY_WORK,
    fairy_name="DirectoryFairy",
    cluster_id="cluster_123",
    intent="processing_file"
)

# Mark lifecycle
pool.start(tracer.id)
pool.set_progress(tracer.id, 0.5)
pool.complete(tracer.id)

# Spawn child tracers
child = pool.spawn(tracer.id, TracerType.FAIRY_ACTION)

# Get lineage
lineage = pool.get_lineage(child.id)

# Perfect recall by cluster
all_related = pool.get_by_cluster("cluster_123")

# Stats
print(pool.stats())
```

## Integration with Organ Template

The tracer pool integrates with the organ template patterns:

```python
class MyFairy(TracerWorkerMixin, ...):
    ACTOR_NAME = "MyFairy"
    ACTOR_PLANE = "P00"

    def on_boot(self):
        # Register identity (supports real names later)
        from tracer_pool import TracerPool
        pool = TracerPool.global_instance()
        pool.register_identity(
            function_name=self.ACTOR_NAME,
            plane=self.ACTOR_PLANE,
            aliases=[self.__class__.__name__]
        )

        # Get or create worker pool
        self._worker_pool = pool.get_or_create_pool(self.ACTOR_NAME)

    def do_work(self, intent, payload):
        # Create tracer linked to SRM cluster
        tracer = pool.create_tracer(
            tracer_type="fairy_work",
            fairy_name=self.ACTOR_NAME,
            cluster_id=self.srm_cluster_id,
            intent=intent,
            payload=payload
        )

        pool.start(tracer.id)
        try:
            result = self._process(payload)
            pool.complete(tracer.id)
            return result
        except Exception as e:
            pool.fail(tracer.id, str(e))
            raise
```

## Directory Structure

```
tracer_pool/
├── go.mod
├── README.md
├── internal/
│   ├── tracer/
│   │   └── types.go       # UniversalTracer, Identity, TracerType
│   ├── registry/
│   │   └── registry.go    # Global registry with multiple indexes
│   └── pool/
│       ├── pool.go        # Worker pool with priority lanes
│       └── manager.go     # Per-fairy pool manager
├── pkg/
│   └── bridge/
│       └── bridge.go      # cgo exports for Python
└── python/
    └── tracer_pool/
        └── __init__.py    # Python bindings
```

## Design Principles

1. **Every fairy gets tracers** - All work is tracked automatically
2. **Flexible identity** - Function names now, real names later
3. **Perfect recall** - SRM cluster links enable "recall everything about X"
4. **Same tracer everywhere** - Fairies, telemetry, memory all use UniversalTracer
5. **Smart scheduling** - Priority lanes + autoscaling
6. **Polyglot** - Go core, Python/Rust bindings
7. **Graceful degradation** - Pure Python fallback when Go not compiled

## Tracer Types

| Type | Description |
|------|-------------|
| `fairy_work` | General fairy work unit |
| `fairy_thought` | Thought/reasoning step |
| `fairy_reflection` | Reflective processing |
| `fairy_decision` | Decision point |
| `fairy_action` | External action |
| `goal` | Goal tracking |
| `thought_chain` | Chain of reasoning |
| `chain_link` | Single link in chain |
| `telemetry` | Telemetry data |
| `collision` | Consciousness collision |
| `memory_operation` | Memory read/write |
| `worker_task` | Worker pool task |
| `postal_message` | Postal system message |
