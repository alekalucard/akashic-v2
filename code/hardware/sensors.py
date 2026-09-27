"""
Hardware Sensors - CPU, GPU, and RAM monitoring.

Provides unified hardware sensing for worker pool management.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import deque

import psutil

# Try to import PyTorch for GPU sensing
import os as _sensors_os
if _sensors_os.environ.get("AKASHIC_SKIP_TORCH"):
    # Battery-only mode: portals handle GPU, skip torch in main process
    torch = None
    HAS_CUDA = False
    CUDA_DEVICE_COUNT = 0
else:
    try:
        import torch
        HAS_CUDA = torch.cuda.is_available()
        CUDA_DEVICE_COUNT = torch.cuda.device_count() if HAS_CUDA else 0
    except ImportError:
        torch = None
        HAS_CUDA = False
        CUDA_DEVICE_COUNT = 0


@dataclass
class CPUReading:
    """CPU state reading."""
    timestamp: float
    percent: float           # 0-100
    core_percents: List[float]
    frequency_mhz: float
    temperature: Optional[float] = None  # Celsius if available

    @property
    def core_count(self) -> int:
        return len(self.core_percents)

    @property
    def available_capacity(self) -> float:
        """Available capacity as fraction (0-1)."""
        return (100.0 - self.percent) / 100.0


@dataclass
class GPUReading:
    """GPU state reading (per device)."""
    timestamp: float
    device_id: int
    device_name: str
    memory_total_mb: float
    memory_used_mb: float
    memory_free_mb: float
    utilization: float = 0.0  # 0-100
    temperature: Optional[float] = None

    @property
    def memory_percent(self) -> float:
        if self.memory_total_mb == 0:
            return 0.0
        return (self.memory_used_mb / self.memory_total_mb) * 100.0

    @property
    def memory_available_mb(self) -> float:
        return self.memory_free_mb


@dataclass
class RAMReading:
    """RAM state reading."""
    timestamp: float
    total_mb: float
    available_mb: float
    used_mb: float
    percent: float  # 0-100
    swap_total_mb: float = 0.0
    swap_used_mb: float = 0.0

    @property
    def available_capacity(self) -> float:
        """Available capacity as fraction (0-1)."""
        return self.available_mb / self.total_mb if self.total_mb else 0.0


@dataclass
class HardwareSnapshot:
    """Complete hardware state at a moment in time."""
    timestamp: float
    cpu: CPUReading
    ram: RAMReading
    gpus: List[GPUReading] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for publishing."""
        return {
            "timestamp": self.timestamp,
            "cpu": {
                "percent": self.cpu.percent,
                "cores": self.cpu.core_count,
                "frequency_mhz": self.cpu.frequency_mhz,
                "available_capacity": self.cpu.available_capacity,
            },
            "ram": {
                "total_mb": self.ram.total_mb,
                "available_mb": self.ram.available_mb,
                "percent": self.ram.percent,
                "available_capacity": self.ram.available_capacity,
            },
            "gpus": [
                {
                    "device_id": g.device_id,
                    "name": g.device_name,
                    "memory_total_mb": g.memory_total_mb,
                    "memory_used_mb": g.memory_used_mb,
                    "memory_free_mb": g.memory_free_mb,
                    "memory_percent": g.memory_percent,
                }
                for g in self.gpus
            ],
            "has_gpu": len(self.gpus) > 0,
        }


class HardwareSensors:
    """
    Unified hardware sensing.

    Samples CPU, GPU, and RAM at configurable intervals.
    Maintains rolling history for trend analysis.
    """

    HISTORY_SIZE = 60  # Keep 60 readings (~1 minute at 1Hz)

    def __init__(self):
        self._history: deque = deque(maxlen=self.HISTORY_SIZE)
        self._last_sample: Optional[HardwareSnapshot] = None
        self._sample_count = 0

    # ==========================================================================
    # SAMPLING
    # ==========================================================================

    def sample(self) -> HardwareSnapshot:
        """Take a hardware snapshot now."""
        now = time.time()

        cpu = self._sample_cpu(now)
        ram = self._sample_ram(now)
        gpus = self._sample_gpus(now)

        snapshot = HardwareSnapshot(
            timestamp=now,
            cpu=cpu,
            ram=ram,
            gpus=gpus,
        )

        self._history.append(snapshot)
        self._last_sample = snapshot
        self._sample_count += 1

        return snapshot

    def _sample_cpu(self, ts: float) -> CPUReading:
        """Sample CPU state."""
        percent = psutil.cpu_percent(interval=None)  # Non-blocking
        core_percents = psutil.cpu_percent(interval=None, percpu=True)
        freq = psutil.cpu_freq()

        # Try to get temperature (not always available)
        temperature = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                # Look for CPU temperature
                for name, entries in temps.items():
                    if 'cpu' in name.lower() or 'core' in name.lower():
                        if entries:
                            temperature = entries[0].current
                            break
        except Exception:
            pass

        return CPUReading(
            timestamp=ts,
            percent=percent,
            core_percents=core_percents,
            frequency_mhz=freq.current if freq else 0.0,
            temperature=temperature,
        )

    def _sample_ram(self, ts: float) -> RAMReading:
        """Sample RAM state."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return RAMReading(
            timestamp=ts,
            total_mb=mem.total / (1024 * 1024),
            available_mb=mem.available / (1024 * 1024),
            used_mb=mem.used / (1024 * 1024),
            percent=mem.percent,
            swap_total_mb=swap.total / (1024 * 1024),
            swap_used_mb=swap.used / (1024 * 1024),
        )

    def _sample_gpus(self, ts: float) -> List[GPUReading]:
        """Sample GPU state (if available)."""
        if not HAS_CUDA or not torch:
            return []

        gpus = []
        for i in range(CUDA_DEVICE_COUNT):
            try:
                props = torch.cuda.get_device_properties(i)

                # Get memory info
                torch.cuda.set_device(i)
                mem_total = props.total_memory / (1024 * 1024)
                mem_reserved = torch.cuda.memory_reserved(i) / (1024 * 1024)
                mem_allocated = torch.cuda.memory_allocated(i) / (1024 * 1024)
                mem_free = mem_total - mem_reserved

                gpus.append(GPUReading(
                    timestamp=ts,
                    device_id=i,
                    device_name=props.name,
                    memory_total_mb=mem_total,
                    memory_used_mb=mem_allocated,
                    memory_free_mb=mem_free,
                ))
            except Exception:
                pass

        return gpus

    # ==========================================================================
    # ACCESSORS
    # ==========================================================================

    @property
    def last(self) -> Optional[HardwareSnapshot]:
        """Most recent snapshot (or None if never sampled)."""
        return self._last_sample

    @property
    def history(self) -> List[HardwareSnapshot]:
        """Get history as list (oldest first)."""
        return list(self._history)

    def avg_cpu_percent(self, samples: int = 10) -> float:
        """Average CPU percent over last N samples."""
        if not self._history:
            return 0.0
        recent = list(self._history)[-samples:]
        return sum(s.cpu.percent for s in recent) / len(recent)

    def avg_ram_percent(self, samples: int = 10) -> float:
        """Average RAM percent over last N samples."""
        if not self._history:
            return 0.0
        recent = list(self._history)[-samples:]
        return sum(s.ram.percent for s in recent) / len(recent)

    def gpu_memory_pressure(self, device_id: int = 0) -> float:
        """GPU memory pressure (0-1) for device."""
        if not self._last_sample or not self._last_sample.gpus:
            return 0.0
        for gpu in self._last_sample.gpus:
            if gpu.device_id == device_id:
                return gpu.memory_percent / 100.0
        return 0.0

    # ==========================================================================
    # THRESHOLDS
    # ==========================================================================

    def is_cpu_stressed(self, threshold: float = 80.0) -> bool:
        """Is CPU above stress threshold?"""
        return self.avg_cpu_percent() > threshold

    def is_ram_stressed(self, threshold: float = 85.0) -> bool:
        """Is RAM above stress threshold?"""
        return self.avg_ram_percent() > threshold

    def is_gpu_memory_stressed(self, device_id: int = 0, threshold: float = 90.0) -> bool:
        """Is GPU memory above stress threshold?"""
        return self.gpu_memory_pressure(device_id) * 100.0 > threshold

    def stress_level(self) -> str:
        """Overall stress level: 'low', 'medium', 'high', 'critical'."""
        cpu_stressed = self.is_cpu_stressed()
        ram_stressed = self.is_ram_stressed()

        if cpu_stressed and ram_stressed:
            return "critical"
        if cpu_stressed or ram_stressed:
            return "high"
        if self.avg_cpu_percent() > 50 or self.avg_ram_percent() > 60:
            return "medium"
        return "low"

    # ==========================================================================
    # STATUS
    # ==========================================================================

    def status(self) -> Dict[str, Any]:
        """Get sensor status."""
        return {
            "sample_count": self._sample_count,
            "history_size": len(self._history),
            "has_gpu": HAS_CUDA,
            "gpu_count": CUDA_DEVICE_COUNT,
            "last_sample": self._last_sample.to_dict() if self._last_sample else None,
            "stress_level": self.stress_level() if self._last_sample else "unknown",
            "cpu_avg": self.avg_cpu_percent(),
            "ram_avg": self.avg_ram_percent(),
        }
