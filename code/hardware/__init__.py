"""
Hardware Module - CPU/GPU/RAM sensing, network discovery, and worker pool management.

Provides:
- HardwareFairy: CPU/GPU/RAM monitoring and worker recommendations
- NetworkExplorerFairy: Active learning network discovery
- Orbi driver: Router integration for presence detection

The Dream: Jarvis-style control of everything on your network.
"""

from .sensors import (
    HardwareSensors,
    HardwareSnapshot,
    CPUReading,
    GPUReading,
    RAMReading,
    HAS_CUDA,
    CUDA_DEVICE_COUNT,
)
from .fairy import HardwareFairy, WorkerPoolConfig

# Network explorer (may not be available if dependencies missing)
try:
    from .network_explorer_fairy import (
        NetworkExplorerFairy,
        NetworkDevice,
        NetworkScan,
        get_network_explorer,
    )
    HAS_NETWORK_EXPLORER = True
except ImportError:
    HAS_NETWORK_EXPLORER = False
    NetworkExplorerFairy = None
    NetworkDevice = None
    NetworkScan = None
    get_network_explorer = None

# Orbi driver
try:
    from .drivers.orbi import OrbiDriver, auto_detect_orbi
    HAS_ORBI_DRIVER = True
except ImportError:
    HAS_ORBI_DRIVER = False
    OrbiDriver = None
    auto_detect_orbi = None


__all__ = [
    # Hardware Fairy
    "HardwareFairy",
    "WorkerPoolConfig",
    # Sensors
    "HardwareSensors",
    "HardwareSnapshot",
    "CPUReading",
    "GPUReading",
    "RAMReading",
    # Network Explorer
    "NetworkExplorerFairy",
    "NetworkDevice",
    "NetworkScan",
    "get_network_explorer",
    # Orbi
    "OrbiDriver",
    "auto_detect_orbi",
    # Constants
    "HAS_CUDA",
    "CUDA_DEVICE_COUNT",
    "HAS_NETWORK_EXPLORER",
    "HAS_ORBI_DRIVER",
]
