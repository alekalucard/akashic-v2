# Postal Protocol Specification v0.1

The Postal Protocol is the messaging foundation of the Akashic consciousness system.
Ported from Whisper's `parallel_fabric.py` to Rust for lock-free, high-throughput operation.

## Design Philosophy

- **Lock-free messaging** - No GIL bottleneck, true parallelism
- **Per-topic isolation** - Noisy neighbors can't starve critical topics
- **Priority lanes** - Urgent messages preempt non-urgent
- **Backpressure** - Graceful degradation under load
- **Envelope enforcement** - Every message has intent + timestamp

## Envelope Structure

Every message is an **Envelope** with required and optional fields:

```rust
Envelope {
    // REQUIRED
    intent: String,      // Hierarchical intent (e.g., "fairy.boot")
    t: u64,              // Timestamp in milliseconds since epoch

    // OPTIONAL
    payload: Value,      // JSON payload (arbitrary data)
    priority: Priority,  // HIGH=0, NORMAL=1, LOW=2
    source: String,      // Origin identifier
    trace_id: String,    // UUID for request tracing
    reply_to: String,    // Topic for responses
    correlation_id: String, // Links request/response pairs
    ttl_sec: u32,        // Time-to-live (0 = forever)
    dedupe_key: String,  // Key for deduplication
}
```

### Intent Format

Intents follow a **hierarchical dot-notation**:

```
<topic>.<action>[.<detail>]

Examples:
  fairy.boot           - Fairy is booting
  fairy.booted         - Fairy finished booting
  memory.store         - Request to store memory
  memory.stored        - Memory was stored
  consciousness.heartbeat - System heartbeat
```

The **topic** (first segment before `.`) determines routing to worker pools.

### Priority Levels

| Level  | Value | Use Case |
|--------|-------|----------|
| HIGH   | 0     | Control plane, heartbeats, urgent |
| NORMAL | 1     | Standard operations (default) |
| LOW    | 2     | Background, batch, deferrable |

HIGH messages are processed before NORMAL, NORMAL before LOW.

## Topic Bus Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │                  TopicBus                    │
                    │                                              │
                    │  ┌──────────────────────────────────────┐   │
                    │  │  Topics (lock-free DashMap)           │   │
                    │  │                                       │   │
    publish() ─────▶│  │  ┌─────────────┐  ┌─────────────┐    │   │
                    │  │  │ "fairy"     │  │ "memory"    │    │   │
                    │  │  │ WorkerPool  │  │ WorkerPool  │    │   │
                    │  │  │             │  │             │    │   │
                    │  │  │ [HIGH  ] ───┤  │ [HIGH  ] ──┤    │   │
                    │  │  │ [NORMAL] ───┼─▶│ [NORMAL] ──┼─▶  │   │◀── handlers
                    │  │  │ [LOW   ] ───┤  │ [LOW   ] ──┤    │   │
                    │  │  │             │  │             │    │   │
                    │  │  └─────────────┘  └─────────────┘    │   │
                    │  └──────────────────────────────────────┘   │
                    │                                              │
                    │  ┌──────────────────────────────────────┐   │
                    │  │  Autoscaler Thread                    │   │
                    │  │  - Monitors P95 latency               │   │
                    │  │  - Monitors CPU pressure              │   │
                    │  │  - Scales workers up/down             │   │
                    │  └──────────────────────────────────────┘   │
                    └─────────────────────────────────────────────┘
```

### Per-Topic Worker Pools

Each topic has its own pool of worker threads:

| Config | Default | Description |
|--------|---------|-------------|
| `min_workers` | 1 | Minimum active workers |
| `max_workers` | 8 | Maximum workers under load |
| `target_p95_ms` | 150 | Target P95 latency in ms |
| `queue_capacity` | 8192 | Max queued messages per topic |

Workers are autoscaled based on:
- **Queue depth** - Scale up if depth > workers * 8
- **P95 latency** - Scale up if exceeding target
- **CPU pressure** - Don't scale up if CPU > 85%

## Backpressure Policies

When queues are full, backpressure kicks in:

| Policy | Behavior |
|--------|----------|
| `DropOldestLow` | Drop oldest LOW message, retry (default) |
| `DropNewLow` | Drop the new message if LOW priority |
| `Block` | Block until space available |

The default `DropOldestLow` ensures HIGH and NORMAL messages are never lost,
while gracefully shedding low-priority work under pressure.

## Metrics

The system tracks:

| Metric | Description |
|--------|-------------|
| `messages_published` | Total messages published |
| `messages_delivered` | Messages successfully delivered |
| `messages_dropped` | Messages dropped (backpressure) |
| `queue_depth` | Current total queued messages |
| `peak_queue_depth` | Maximum queue depth seen |
| `p50_ms`, `p95_ms`, `p99_ms` | Latency percentiles |
| `throughput` | Messages per second |
| `drop_rate_percent` | Percentage of messages dropped |

Per-topic stats also include worker count and subscriber count.

## Usage Patterns

### Basic Pub/Sub

```python
from postal_core import PostalCore

postal = PostalCore()

def on_message(envelope):
    print(f"Got: {envelope.intent} - {envelope.payload}")

postal.subscribe("fairy", on_message, "my-handler")
postal.publish("fairy.boot", {"name": "DirectoryFairy"})
```

### Priority Messages

```python
# HIGH priority (control plane)
postal.publish("consciousness.heartbeat", {"beat": 1}, priority=0)

# NORMAL priority (default)
postal.publish("memory.store", {"key": "x", "value": "y"})

# LOW priority (background)
postal.publish("cleanup.old_sessions", {"older_than": "1d"}, priority=2)
```

### Request-Response Pattern

```python
import uuid

def handle_response(env):
    if env.correlation_id == my_request_id:
        print(f"Response: {env.payload}")

my_request_id = str(uuid.uuid4())
postal.subscribe("memory.response", handle_response)

# Include correlation_id for response matching
postal.publish("memory.retrieve", {
    "key": "greeting",
    "correlation_id": my_request_id,
    "reply_to": "memory.response"
})
```

## Python/Rust Interoperability

The Rust implementation is the primary backend for performance.
A Python fallback exists for development/debugging:

```python
from postal_core import PostalCore, USING_RUST

print(f"Backend: {'Rust' if USING_RUST else 'Python'}")
```

Both implementations provide identical APIs.

## Future: Polyglot Extensions

The postal protocol is designed for multi-language systems:

| Component | Language | Rationale |
|-----------|----------|-----------|
| PostalCore | Rust | Lock-free, no GIL, highest throughput |
| TracerPool | Go | Goroutine pools, excellent concurrency |
| Fairies | Python | Rapid iteration, AI integration |
| UI/Dashboard | TypeScript | Browser runtime |

Cross-language communication uses the envelope JSON format with
language-specific bindings to the core Rust library.

## Version History

- **v0.1** - Initial specification, ported from Whisper's parallel_fabric.py
