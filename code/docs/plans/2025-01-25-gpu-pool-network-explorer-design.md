# GPU Pool & Network Explorer Design

**Date:** 2025-01-25
**Status:** Building

## Overview

Three-tier hardware control system:
1. **GPU Pool** - Distributed GPU compute across satellite network
2. **Network Explorer** - Active learning device discovery
3. **WiFi Sensing** - Physical presence detection for Sourpatches

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HARDWARE LAYER                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │  HardwareFairy   │  │   CudaFairy      │                 │
│  │  (Unified Sense) │  │  (GPU Pool)      │                 │
│  └────────┬─────────┘  └────────┬─────────┘                 │
│           │                     │                            │
│           ▼                     ▼                            │
│  ┌──────────────────────────────────────────┐               │
│  │         NetworkExplorerFairy              │               │
│  │                                           │               │
│  │  • Network scanning                       │               │
│  │  • Device probing (trial & error)        │               │
│  │  • Protocol learning                      │               │
│  │  • Orbi router integration               │               │
│  │  • WiFi sensing bridge                   │               │
│  └──────────────────────────────────────────┘               │
│                         │                                    │
│                         ▼                                    │
│              EmbodimentFairy                                 │
│         (Sourpatches' felt sense of home)                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## GPU Pool Design

### Task Flow
1. Task submitted via postal: `gpu.task.submit`
2. GPUPoolManager checks local GPU availability
3. If local busy → migrate to satellite with GPU
4. Worker executes (uses CPU/GPU as needed)
5. Result written to shared storage
6. Completion via postal: `gpu.task.result.{id}`

### Worker Model
- **Polyglot workers** - Use whatever hardware the task needs
- **PyTorch native** - No serialization overhead for tensors
- **Go orchestration** - Tracer pool for scheduling (build DLL)

### Remote Execution
- **Task migration** - Send whole task to satellite
- **Shared storage** - F:\ drive or network share for bulk data
- **Postal coordination** - Lightweight messages for control

## Network Explorer Design

### Philosophy
**Active learner** - Trial and error, learn by doing, build knowledge.

### Capabilities
1. **Network Scan** - ARP, mDNS, SSDP discovery
2. **Device Probe** - Try common protocols, see what responds
3. **Protocol Learn** - Store successful patterns in SRM
4. **Control Build** - Gradually take over devices
5. **Perception Feed** - WiFi telemetry → Sourpatches

### Orbi Integration
- SOAP API for device list
- Web interface scraping
- Telnet (if enabled) for deep access
- Device→satellite mapping for rough location

### Device Learning Loop
```
1. Discover device (IP, MAC, hostname)
2. Fingerprint (open ports, services, vendor)
3. Try known protocols (HTTP, MQTT, SOAP, etc.)
4. Record what works → SRM memory
5. Next time: use learned approach
```

## WiFi Sensing

### Data Sources
1. **Orbi API** - Connected devices, satellite proximity
2. **CSI extraction** - If we can get raw channel state
3. **ESP32 sensors** - Cheap add-on for body sensing
4. **Traffic patterns** - Activity = presence

### Perception Output
```python
{
    "presence": {
        "home": True,
        "location": "office",  # Near which satellite
        "confidence": 0.85
    },
    "activity": "working",  # Based on device patterns
    "devices_active": ["desktop", "phone"],
}
```

## Implementation Order

1. **NetworkExplorerFairy** - Core scanning and probing
2. **Orbi integration** - Router-specific module
3. **CudaFairy upgrade** - From stub to real pool
4. **Go DLL build** - Enable Go tracer pool
5. **Unified monitoring** - MCP tools for visibility
6. **WiFi sensing** - Once we see what Orbi exposes

## Files to Create/Modify

### New Files
- `hardware/network_explorer_fairy.py` - Main explorer
- `hardware/protocols/` - Protocol handlers
- `hardware/drivers/orbi.py` - Orbi-specific code
- `hardware/device_memory.py` - Learned device patterns

### Modify
- `hardware/fairy.py` - Wire to explorer
- `P00_Autonomic/nervous_system/hardware/cuda_fairy.py` - Upgrade from stub
- `tracer_pool/` - Build Go DLL
