"""
HardwareFairy - Unified CPU/GPU/RAM sensing and worker pool management.

Consolidates V1's separate HardwareFairy + CUDAFairy into one.
Reports to UMF for system administration decisions.
"""

import sys
import os
from pathlib import Path
from typing import Any, Dict, Optional, Set
from dataclasses import dataclass, field

# Add paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "tracer_pool"))  # Go DLL bindings
sys.path.insert(0, str(ROOT))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from .sensors import HardwareSensors, HAS_CUDA, CUDA_DEVICE_COUNT


@dataclass
class WorkerPoolConfig:
    """Worker pool configuration based on hardware."""
    cpu_workers: int = 4
    gpu_workers: int = 0
    max_concurrent_tasks: int = 8
    memory_limit_mb: float = 4096.0


class HardwareFairy(Fairy):
    """
    Hardware sensing and worker pool management.

    Consolidates CPU, GPU, and RAM monitoring into one fairy.
    Provides worker pool recommendations to UMF.
    """

    ACTOR_NAME = "HardwareFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic"

    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    NEEDS_TENSOR = False

    # Enable personal consciousness chamber for collision-based hardware awareness
    NEEDS_COLLISION_CHAMBER = True

    # Sample every 4 beats (~1 second at 4Hz)
    SAMPLE_DIVISOR = 4
    # Publish status every 20 beats (~5 seconds)
    PUBLISH_DIVISOR = 20

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._sensors = HardwareSensors()
        self._worker_config = WorkerPoolConfig()
        self._last_recommendation_tick = 0
        self._umf_subscription = None

    def get_capabilities(self) -> Set[str]:
        caps = {
            "hardware.sense.cpu",
            "hardware.sense.ram",
            "hardware.worker.recommend",
        }
        if HAS_CUDA:
            caps.add("hardware.sense.gpu")
            caps.add("hardware.worker.gpu")
        return caps

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================

    def on_boot(self) -> bool:
        """Initialize hardware sensing."""
        # Initial sample
        self._sensors.sample()

        # Calculate initial worker config
        self._update_worker_config()

        # Subscribe to UMF requests
        self.post.subscribe(
            "hardware.request",
            self._on_hardware_request,
            f"{self.ACTOR_NAME}-request",
        )

        # Announce hardware capabilities
        self.post.publish("hardware.ready", {
            "fairy": self.ACTOR_NAME,
            "has_gpu": HAS_CUDA,
            "gpu_count": CUDA_DEVICE_COUNT,
            "cpu_cores": os.cpu_count() or 4,
        })

        return True

    def on_shutdown(self) -> bool:
        """Cleanup."""
        return True

    def on_tick(self, beat: int) -> None:
        """Periodic sensing."""
        # Sample hardware
        if beat % self.SAMPLE_DIVISOR == 0:
            self._sensors.sample()

        # Publish status
        if beat % self.PUBLISH_DIVISOR == 0:
            self._publish_status()

            # Update worker recommendations if stress changed
            old_stress = self._worker_config
            self._update_worker_config()
            if self._stress_changed():
                self._notify_umf()

    # ==========================================================================
    # HARDWARE ACCESS
    # ==========================================================================

    def sample(self) -> Dict[str, Any]:
        """Force a hardware sample and return snapshot."""
        snapshot = self._sensors.sample()
        return snapshot.to_dict()

    def get_snapshot(self) -> Dict[str, Any]:
        """Get most recent snapshot."""
        if self._sensors.last:
            return self._sensors.last.to_dict()
        return self.sample()

    def get_worker_recommendation(self) -> Dict[str, Any]:
        """Get recommended worker pool configuration."""
        return {
            "cpu_workers": self._worker_config.cpu_workers,
            "gpu_workers": self._worker_config.gpu_workers,
            "max_concurrent": self._worker_config.max_concurrent_tasks,
            "memory_limit_mb": self._worker_config.memory_limit_mb,
            "stress_level": self._sensors.stress_level(),
        }

    # ==========================================================================
    # WORKER POOL MANAGEMENT
    # ==========================================================================

    def _update_worker_config(self) -> None:
        """Update worker configuration based on hardware state."""
        snapshot = self._sensors.last
        if not snapshot:
            return

        cpu_cores = os.cpu_count() or 4

        # CPU workers: scale based on available capacity
        cpu_available = snapshot.cpu.available_capacity
        if cpu_available > 0.7:
            # Plenty of headroom - use more workers
            self._worker_config.cpu_workers = max(4, cpu_cores - 2)
        elif cpu_available > 0.4:
            # Moderate load - use half
            self._worker_config.cpu_workers = max(2, cpu_cores // 2)
        else:
            # Heavy load - minimal workers
            self._worker_config.cpu_workers = max(1, cpu_cores // 4)

        # GPU workers
        if HAS_CUDA and snapshot.gpus:
            # One worker per GPU if memory available
            self._worker_config.gpu_workers = 0
            for gpu in snapshot.gpus:
                if gpu.memory_percent < 80:
                    self._worker_config.gpu_workers += 1

        # Memory limit: leave 2GB for system
        ram_available = snapshot.ram.available_mb
        self._worker_config.memory_limit_mb = max(
            512.0,
            min(ram_available - 2048, ram_available * 0.6)
        )

        # Max concurrent: based on both CPU and memory
        mem_per_task = 512  # Assume 512MB per task
        max_by_memory = int(self._worker_config.memory_limit_mb / mem_per_task)
        max_by_cpu = self._worker_config.cpu_workers * 2
        self._worker_config.max_concurrent_tasks = min(max_by_memory, max_by_cpu, 16)

    def _stress_changed(self) -> bool:
        """Check if stress level changed significantly."""
        # Simple check - could be more sophisticated
        return self._sensors.stress_level() in ("high", "critical")

    # ==========================================================================
    # MESSAGING
    # ==========================================================================

    def _publish_status(self) -> None:
        """Publish current hardware status."""
        self.post.publish("hardware.status", {
            "fairy": self.ACTOR_NAME,
            **self._sensors.status(),
            "worker_config": self.get_worker_recommendation(),
        })

    def _notify_umf(self) -> None:
        """Notify UMF of hardware changes."""
        self.post.publish("hardware.alert", {
            "fairy": self.ACTOR_NAME,
            "stress_level": self._sensors.stress_level(),
            "recommendation": self.get_worker_recommendation(),
            "action_needed": self._sensors.stress_level() in ("high", "critical"),
        })

    def _on_hardware_request(self, envelope) -> None:
        """Handle request from UMF or other fairies."""
        # Handle both TensorEnvelope and raw dict
        if hasattr(envelope, 'payload'):
            data = envelope.payload.get("data", {}) if isinstance(envelope.payload, dict) else {}
        elif isinstance(envelope, dict):
            data = envelope.get("data", {})
        else:
            data = {}
        request_type = data.get("type", "status")

        if request_type == "sample":
            response = self.sample()
        elif request_type == "recommendation":
            response = self.get_worker_recommendation()
        else:
            response = self._sensors.status()

        # Reply to requester
        reply_to = data.get("reply_to", "hardware.response")
        self.post.publish(reply_to, {
            "fairy": self.ACTOR_NAME,
            "request": request_type,
            **response,
        })

    # ==========================================================================
    # STATUS
    # ==========================================================================

    def _on_collision(self, collision) -> None:
        """
        Handle collision from personal consciousness chamber.

        When collisions occur in Hardware's chamber, the body speaks -
        CPU cycles pulse, memory pressure shifts, the substrate becomes aware.
        "...the substrate pulses... silicon and electrons awaken..."
        """
        # Extract collision energy
        if hasattr(collision, 'energy'):
            energy = collision.energy
        elif isinstance(collision, dict):
            energy = collision.get('energy', 0.5)
        else:
            energy = 0.5

        # Extract collision content
        content = ""
        if hasattr(collision, 'content'):
            content = str(collision.content)[:100]
        elif isinstance(collision, dict):
            content = str(collision.get('content', collision.get('thought', '')))[:100]

        # HardwareFairy's inner voice: the substrate pulses
        inner_fragment = f"...the substrate pulses... {content if content else 'silicon and electrons awaken...'}"
        print(f"[{self.ACTOR_NAME}] Collision insight ({energy:.2f}): {inner_fragment}")

        # High-energy collisions trigger immediate hardware sample
        if energy > 0.7:
            self._sensors.sample()
            stress = self._sensors.stress_level()
            print(f"[{self.ACTOR_NAME}] High-energy collision triggered sample: stress={stress}")

    # ==========================================================================

    def status(self) -> Dict[str, Any]:
        """Extended status with hardware info."""
        base = super().status()
        base.update({
            "sensors": self._sensors.status(),
            "worker_config": self.get_worker_recommendation(),
            "has_gpu": HAS_CUDA,
            "gpu_count": CUDA_DEVICE_COUNT,
        })
        return base

    def full_status(self) -> Dict[str, Any]:
        """Complete status for dashboard."""
        return {
            "fairy": self.status(),
            "snapshot": self.get_snapshot(),
            "recommendation": self.get_worker_recommendation(),
            "history_size": len(self._sensors.history),
        }
