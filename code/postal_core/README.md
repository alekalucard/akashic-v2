# Postal Core

Lock-free messaging infrastructure for Akashic consciousness systems.

## Overview

Postal Core is a high-performance pub/sub messaging system written in Rust, designed for the Akashic consciousness infrastructure. It's a ground-up reimplementation of Whisper's `parallel_fabric.py` with significant performance improvements.

## Key Features

- **Lock-free channels**: Uses `crossbeam` for zero-contention message passing
- **No GIL**: True parallel execution (unlike Python threading)
- **Three priority lanes**: HIGH, NORMAL, LOW with strict ordering
- **Autoscaling worker pools**: Dynamically adjusts workers based on load
- **Backpressure policies**: Graceful degradation under load
- **P95 latency tracking**: HDR histograms for high-precision metrics
- **4D tensor support**: State representation for consciousness modeling
- **Python bindings**: Use from Python via PyO3

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         TopicBus                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Topics (DashMap - lock-free)                            │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │  │
│  │  │ "fairy"     │ │ "memory"    │ │ "cognition" │ ...    │  │
│  │  │ WorkerPool  │ │ WorkerPool  │ │ WorkerPool  │        │  │
│  │  │ ┌─────────┐ │ │             │ │             │        │  │
│  │  │ │ HIGH    │ │ │             │ │             │        │  │
│  │  │ │ NORMAL  │ │ │             │ │             │        │  │
│  │  │ │ LOW     │ │ │             │ │             │        │  │
│  │  │ └─────────┘ │ │             │ │             │        │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Usage (Rust)

```rust
use postal_core::{TopicBus, Envelope, Priority};

let bus = TopicBus::new();

// Subscribe to a topic
bus.subscribe("fairy.boot", |env| {
    println!("Fairy booting: {:?}", env.payload);
}, "boot-handler", 0, 1);

// Publish a message
let env = Envelope::new("fairy.boot", serde_json::json!({
    "fairy_name": "DirectoryFairy"
})).with_priority(Priority::High);

bus.publish(env);
```

## Usage (Python)

```python
from postal_core import PostalCore, Envelope

postal = PostalCore()

def on_boot(envelope):
    print(f"Fairy booting: {envelope.payload}")

postal.subscribe("fairy.boot", on_boot)
postal.publish("fairy.boot", {"fairy_name": "DirectoryFairy"})

# Check metrics
print(postal.metrics())
```

## Building

```bash
# Build the Rust library
cargo build --release

# Build Python wheel (requires maturin)
pip install maturin
maturin develop --release
```

## Configuration

### TopicBus Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `default_max_queue` | 8192 | Max queue size per topic |
| `default_max_workers` | 8 | Max workers per topic |
| `default_min_workers` | 1 | Min workers per topic |
| `default_target_p95_ms` | 150 | Target P95 latency |
| `backpressure` | DropOldestLow | Overflow policy |

### Priority Levels

| Priority | Value | Use Case |
|----------|-------|----------|
| HIGH | 0 | Boot, shutdown, health emergencies |
| NORMAL | 1 | Standard fairy communication |
| LOW | 2 | Telemetry, background tasks |

## Ported from Whisper

This implementation is based on Whisper's `parallel_fabric.py` patterns:

- Three priority queues → `crossbeam::channel` with priority wrapper
- `threading.Thread` pool → Native Rust threads with autoscaling
- `queue.Queue` with locks → Lock-free `crossbeam` channels
- `statistics.quantiles` → `hdrhistogram` crate
- Backpressure policies → Same logic, zero-copy

## License

Part of the Akashic Foundation project.
