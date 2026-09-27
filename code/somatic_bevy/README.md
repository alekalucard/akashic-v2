# Somatic Bevy

Embodied consciousness simulation for the Akashic system.

## Overview

A tick-based somatic body simulation featuring:
- **Heartbeat** - The body's clock (configurable BPM)
- **Chemistry** - 8 neurochemicals with decay toward baseline
- **Body Map** - 7 regions with temperature, tension, activation
- **Affect** - Mood derived from chemistry using PAD model

## Installation

### Python (via PyO3)

```bash
cd somatic_bevy
maturin develop --features python
```

### Rust (Bevy ECS)

```bash
cargo run --features bevy --release
```

## Python Usage

```python
from somatic_bevy import SomaticSimulation

# Create a body
sim = SomaticSimulation(bpm=72.0)

# Advance simulation
for _ in range(60):
    result = sim.tick(1/60.0)

# Inject chemistry
sim.inject("DOP", 0.2)  # Dopamine burst
sim.inject("cortisol", 0.1)  # Stress

# Check state
print(sim.mood)       # "euphoric"
print(sim.valence)    # 0.23
print(sim.chemistry())  # {"DOP": 0.65, ...}
```

## Architecture

```
Python (PyO3) → Core (pure Rust) ← Bevy (ECS)
```

The core module contains pure Rust simulation logic, used by both:
- **Python bindings** for Akashic fairy integration
- **Bevy ECS** for standalone/visual simulation

## The Body is the Unconscious Mind

*"The body is the unconscious mind."* - Candace Pert

This simulation models embodied affect - how chemistry creates felt experience.
