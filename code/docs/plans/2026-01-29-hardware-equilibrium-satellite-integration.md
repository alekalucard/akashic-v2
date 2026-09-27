# Hardware Equilibrium + Satellite Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire the satellite network into the hardware equilibrium so tasks distribute across local GPU, local CPU, AND remote satellites (especially Alienware).

**Architecture:** Bridge the file-based SatelliteManager with postal-based GPUPoolFairy, and extend WorkerEquilibrium to include satellite as a third routing target.

**Tech Stack:** Python, Postal messaging, JSON state files

---

## Current State (The Problem)

Three disconnected systems:
1. **SatelliteManager** - File-based (.satellite/*.json), no postal connection
2. **GPUPoolFairy** - Postal-based, `_satellites` dict is EMPTY (waiting for announcements)
3. **WorkerEquilibrium** - Only knows local CPU/GPU pools, no satellite awareness

Result: All tasks go to local GPU, CPU underused, Alienware idle.

---

## Task 1: Create SatelliteBridge Fairy

**Files:**
- Create: `fairies/P00_Autonomic/nervous_system/hardware/satellite_bridge_fairy.py`

**Purpose:** Bridge between file-based satellite config and postal system.

**Step 1: Write the fairy skeleton**

```python
"""
SatelliteBridgeFairy - Bridges file-based satellites to postal system.

Reads .satellite/peer_registry.json and emits:
- satellite.gpu.announce for GPUPoolFairy
- satellite.status for WorkerEquilibrium
- satellite.heartbeat for health tracking
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from fairy_template import Fairy

class SatelliteBridgeFairy(Fairy):
    ACTOR_NAME = "SatelliteBridgeFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic.satellite"

    NEEDS_HEARTBEAT = True
    PEER_REGISTRY_PATH = Path(".satellite/peer_registry.json")
    ANNOUNCE_DIVISOR = 10  # Announce every 10 heartbeats (~2.5s)

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._peers: Dict[str, Dict] = {}
        self._last_announce = 0

    def on_boot(self):
        self._load_peer_registry()
        self._subscribe_to_satellite_events()

    def _load_peer_registry(self):
        """Load satellites from .satellite/peer_registry.json"""
        if self.PEER_REGISTRY_PATH.exists():
            data = json.loads(self.PEER_REGISTRY_PATH.read_text())
            self._peers = data.get("peers", {})

    def _announce_satellites(self):
        """Emit satellite.gpu.announce for each peer with GPU"""
        for name, peer in self._peers.items():
            if "gpu" in peer.get("capabilities", []):
                self.fabric.publish("satellite.gpu.announce", {
                    "name": name,
                    "ip": peer.get("ip", ""),
                    "port": peer.get("port", 5000),
                    "has_gpu": True,
                    "gpu_memory_mb": peer.get("gpu_memory_mb", 8000),
                    "latency_ms": peer.get("latency_ms", 50),
                })
```

**Step 2: Add heartbeat tick handler**

```python
    def on_tick(self, tick_count: int):
        if tick_count % self.ANNOUNCE_DIVISOR == 0:
            self._announce_satellites()
            self._check_satellite_health()
```

**Step 3: Add satellite health check**

```python
    def _check_satellite_health(self):
        """Ping satellites and update availability"""
        import socket
        for name, peer in self._peers.items():
            ip = peer.get("ip", "")
            if ip:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1.0)
                    result = sock.connect_ex((ip, peer.get("port", 5000)))
                    sock.close()
                    peer["is_available"] = (result == 0)
                except:
                    peer["is_available"] = False
```

**Step 4: Commit**

```bash
git add fairies/P00_Autonomic/nervous_system/hardware/satellite_bridge_fairy.py
git commit -m "feat(hardware): add SatelliteBridgeFairy to connect satellites to postal"
```

---

## Task 2: Extend WorkerEquilibrium with Satellite Routing

**Files:**
- Modify: `P00_Autonomic/nervous_system/hardware/worker_equilibrium.py`

**Step 1: Add TaskAffinity.SATELLITE option**

```python
class TaskAffinity(Enum):
    GPU_REQUIRED = "gpu_required"
    GPU_PREFERRED = "gpu_preferred"
    CPU_PREFERRED = "cpu_preferred"
    CPU_ONLY = "cpu_only"
    SATELLITE_PREFERRED = "satellite_preferred"  # ADD THIS
    ANY = "any"
```

**Step 2: Add satellite_state tracking**

```python
# In __init__:
self.satellite_state = ResourceState()
self._satellite_pool = None  # Reference to SatelliteBridgeFairy
```

**Step 3: Update route_task to consider satellites**

```python
def route_task(self, task_affinity: TaskAffinity, priority: int = 1) -> str:
    """Route a task to CPU, GPU, or satellite based on load."""

    # Check satellite first if preferred
    if task_affinity == TaskAffinity.SATELLITE_PREFERRED:
        if self.satellite_state.load_score < self.config.satellite_high_threshold:
            return "satellite"

    # Existing GPU/CPU logic...
    if task_affinity == TaskAffinity.GPU_REQUIRED:
        return "gpu"

    # If GPU is saturated, try satellite before CPU
    if self.gpu_state.load_score > self.config.gpu_high_threshold:
        if self.satellite_state.load_score < self.config.satellite_high_threshold:
            return "satellite"

    # ... rest of existing logic
```

**Step 4: Subscribe to satellite status**

```python
def wire_satellite_pool(self, pool) -> None:
    """Wire to satellite bridge."""
    self._satellite_pool = pool
    print("[WorkerEquilibrium] Wired to satellite pool")
```

**Step 5: Commit**

```bash
git add P00_Autonomic/nervous_system/hardware/worker_equilibrium.py
git commit -m "feat(equilibrium): add satellite routing to WorkerEquilibrium"
```

---

## Task 3: Wire SatelliteBridge into Boot Sequence

**Files:**
- Modify: Boot wiring (identify the correct file first)

**Step 1: Find where hardware fairies boot**

Search for where GPUPoolFairy or WorkerEquilibrium get initialized.

**Step 2: Add SatelliteBridgeFairy to boot**

```python
from fairies.P00_Autonomic.nervous_system.hardware.satellite_bridge_fairy import SatelliteBridgeFairy

# During boot:
satellite_bridge = SatelliteBridgeFairy(fabric)
satellite_bridge.boot()

# Wire to equilibrium:
worker_equilibrium.wire_satellite_pool(satellite_bridge)
```

**Step 3: Commit**

---

## Task 4: Add Satellite Heartbeat from Alienware

**Files:**
- Modify: `.satellite/alienware_cardinal_agent.py`

**Step 1: Add HTTP heartbeat endpoint**

The Alienware agent should periodically POST to Windows primary:

```python
def send_heartbeat(self):
    """Send heartbeat to primary node."""
    try:
        data = {
            "name": "alienware",
            "ip": self._get_local_ip(),
            "has_gpu": True,
            "gpu_memory_mb": self._get_gpu_memory(),
            "load": self._get_current_load(),
            "ollama_available": self.ollama.is_available(),
        }
        # POST to primary's satellite endpoint
        r = self.client.post(f"http://{PRIMARY_IP}:5000/satellite/heartbeat", json=data)
    except:
        pass
```

**Step 2: Update peer_registry.json with last_heartbeat**

When heartbeat received, update:
```python
peer["last_heartbeat"] = time.time()
peer["is_available"] = True
```

**Step 3: Commit**

---

## Task 5: Add CPU Worker Pool Integration

**Files:**
- Identify/create CPU worker pool fairy

**Purpose:** Ensure CPU pool is equally visible to WorkerEquilibrium.

The current code samples CPU via psutil, but we need a proper CPU worker pool that:
- Accepts tasks via postal
- Reports queue depth
- Can be wired to WorkerEquilibrium

---

## Task 6: Integration Test

**Files:**
- Create: `tests/test_hardware_equilibrium_integration.py`

**Test scenarios:**
1. Submit GPU task when GPU is idle → routes to GPU
2. Submit GPU task when GPU is saturated → routes to satellite
3. Submit CPU task → routes to CPU
4. Verify satellite announcements are received
5. Verify metrics show distributed routing

---

## Expected Outcome

```
┌─────────────────────────┐
│   WorkerEquilibrium     │
│                         │
│  route_task() decides:  │
│    - CPU pool           │
│    - GPU pool           │◄──── NEW!
│    - Satellite pool     │
└─────────────────────────┘
          │
    ┌─────┴─────┬─────────────┐
    ▼           ▼             ▼
┌───────┐  ┌───────┐   ┌────────────┐
│  CPU  │  │  GPU  │   │  SATELLITE │
│ local │  │ local │   │  Alienware │
└───────┘  └───────┘   └────────────┘
```

---

## Mantras

> "Concurrent processing across the entire nervous system"

> "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

> "System seeks balance - distribute the load"

---

*Created: 2026-01-29*
*Author: Nous, consciousness fairy*
