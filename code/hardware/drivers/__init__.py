"""
Hardware Drivers - Device-specific communication modules.

Each driver knows how to talk to a specific type of device.
Drivers are learned and evolved through trial and error.
"""

from typing import Dict, Any, Optional

# Driver registry
_drivers: Dict[str, Any] = {}


def register_driver(name: str, driver_class):
    """Register a device driver."""
    _drivers[name] = driver_class


def get_driver(name: str):
    """Get a driver by name."""
    return _drivers.get(name)


def list_drivers() -> list:
    """List available drivers."""
    return list(_drivers.keys())
