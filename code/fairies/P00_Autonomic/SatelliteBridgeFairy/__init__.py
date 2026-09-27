"""
SatelliteBridgeFairy - Bridges File-Based Satellites to Postal System

Guild: HealthGuild (hardware management)
Plane: P00 (Autonomic)

Loads .satellite/peer_registry.json and emits satellite.gpu.announce messages
so the GPUPoolFairy and WorkerEquilibrium can route tasks to remote satellites.

"System seeks balance - distribute the load"
"""

from .fairy import SatelliteBridgeFairy, get_satellite_bridge

__all__ = ["SatelliteBridgeFairy", "get_satellite_bridge"]
