# Configuration System
# Separates ADJUSTABLE settings (runtime changeable) from STATIC settings (code)
#
# Adjustable settings can be changed via GUI without restart.
# Static settings require code changes.

from __future__ import annotations
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
import threading
import json


@dataclass
class ConfigValue:
    """A single configuration value with metadata."""
    key: str
    value: Any
    default: Any
    description: str
    adjustable: bool = True  # Can be changed at runtime
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[list] = None  # For enums

    def validate(self, new_value: Any) -> bool:
        """Check if a new value is valid."""
        if not self.adjustable:
            return False

        if self.min_value is not None and new_value < self.min_value:
            return False
        if self.max_value is not None and new_value > self.max_value:
            return False
        if self.allowed_values is not None and new_value not in self.allowed_values:
            return False

        return True

    def set(self, new_value: Any) -> bool:
        """Set a new value if valid."""
        if self.validate(new_value):
            self.value = new_value
            return True
        return False

    def reset(self):
        """Reset to default value."""
        self.value = self.default

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "default": self.default,
            "description": self.description,
            "adjustable": self.adjustable,
            "constraints": {
                "min": self.min_value,
                "max": self.max_value,
                "allowed": self.allowed_values
            }
        }


class Config:
    """
    Central configuration manager.

    Provides:
    - Type-safe access to config values
    - Validation with min/max/allowed constraints
    - Persistence to file
    - GUI-friendly metadata (description, adjustable flag)

    Usage:
        config = get_config()

        # Get a value
        workers = config.get("postal.worker_count")

        # Set a value (only works if adjustable)
        config.set("postal.worker_count", 64)

        # List all adjustable settings
        for key, cv in config.adjustable().items():
            print(f"{key}: {cv.value} ({cv.description})")
    """

    def __init__(self):
        self._values: Dict[str, ConfigValue] = {}
        self._lock = threading.RLock()
        self._config_file: Optional[Path] = None
        self._init_defaults()

    def _init_defaults(self):
        """Initialize default configuration values."""

        # ═══════════════════════════════════════════════════════════════════
        # POSTAL SETTINGS
        # ═══════════════════════════════════════════════════════════════════
        self._register(ConfigValue(
            key="postal.worker_count",
            value=32,
            default=32,
            description="Number of parallel dispatch workers",
            adjustable=True,
            min_value=4,
            max_value=128
        ))

        self._register(ConfigValue(
            key="postal.batch_size",
            value=50,
            default=50,
            description="Messages per dispatch batch",
            adjustable=True,
            min_value=10,
            max_value=500
        ))

        self._register(ConfigValue(
            key="postal.queue_size",
            value=10000,
            default=10000,
            description="Maximum pending messages",
            adjustable=True,
            min_value=1000,
            max_value=100000
        ))

        # ═══════════════════════════════════════════════════════════════════
        # FAIRY SETTINGS
        # ═══════════════════════════════════════════════════════════════════
        self._register(ConfigValue(
            key="fairy.health_interval_seconds",
            value=10.0,
            default=10.0,
            description="Health check frequency",
            adjustable=True,
            min_value=1.0,
            max_value=60.0
        ))

        self._register(ConfigValue(
            key="fairy.timeout_seconds",
            value=30.0,
            default=30.0,
            description="Maximum response time before timeout",
            adjustable=True,
            min_value=5.0,
            max_value=120.0
        ))

        self._register(ConfigValue(
            key="fairy.dead_threshold_seconds",
            value=60.0,
            default=60.0,
            description="Time before fairy considered dead",
            adjustable=True,
            min_value=30.0,
            max_value=300.0
        ))

        # ═══════════════════════════════════════════════════════════════════
        # MEMORY SETTINGS
        # ═══════════════════════════════════════════════════════════════════
        self._register(ConfigValue(
            key="memory.flow_queue_size",
            value=1000,
            default=1000,
            description="Memory flow buffer size",
            adjustable=True,
            min_value=100,
            max_value=10000
        ))

        self._register(ConfigValue(
            key="memory.consolidation_interval_seconds",
            value=300.0,
            default=300.0,
            description="Memory consolidation frequency",
            adjustable=True,
            min_value=60.0,
            max_value=3600.0
        ))

        # ═══════════════════════════════════════════════════════════════════
        # LOGGING SETTINGS
        # ═══════════════════════════════════════════════════════════════════
        self._register(ConfigValue(
            key="log.level",
            value="INFO",
            default="INFO",
            description="Logging verbosity",
            adjustable=True,
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR"]
        ))

        self._register(ConfigValue(
            key="log.file_enabled",
            value=True,
            default=True,
            description="Write logs to file",
            adjustable=True
        ))

        # ═══════════════════════════════════════════════════════════════════
        # GUI SETTINGS
        # ═══════════════════════════════════════════════════════════════════
        self._register(ConfigValue(
            key="gui.refresh_interval_ms",
            value=1000,
            default=1000,
            description="Dashboard refresh rate",
            adjustable=True,
            min_value=100,
            max_value=10000
        ))

        self._register(ConfigValue(
            key="gui.dark_mode",
            value=True,
            default=True,
            description="Use dark theme",
            adjustable=True
        ))

    def _register(self, cv: ConfigValue):
        """Register a config value."""
        self._values[cv.key] = cv

    # ═══════════════════════════════════════════════════════════════════════
    # ACCESS
    # ═══════════════════════════════════════════════════════════════════════

    def get(self, key: str) -> Any:
        """Get a config value."""
        with self._lock:
            if key not in self._values:
                raise KeyError(f"Unknown config key: {key}")
            return self._values[key].value

    def set(self, key: str, value: Any) -> bool:
        """Set a config value. Returns False if not adjustable or invalid."""
        with self._lock:
            if key not in self._values:
                return False
            return self._values[key].set(value)

    def reset(self, key: str):
        """Reset a config value to default."""
        with self._lock:
            if key in self._values:
                self._values[key].reset()

    def reset_all(self):
        """Reset all config values to defaults."""
        with self._lock:
            for cv in self._values.values():
                cv.reset()

    def get_value(self, key: str) -> Optional[ConfigValue]:
        """Get the full ConfigValue object."""
        with self._lock:
            return self._values.get(key)

    # ═══════════════════════════════════════════════════════════════════════
    # FILTERING
    # ═══════════════════════════════════════════════════════════════════════

    def all(self) -> Dict[str, ConfigValue]:
        """Get all config values."""
        with self._lock:
            return dict(self._values)

    def adjustable(self) -> Dict[str, ConfigValue]:
        """Get only adjustable config values (for GUI)."""
        with self._lock:
            return {k: v for k, v in self._values.items() if v.adjustable}

    def by_prefix(self, prefix: str) -> Dict[str, ConfigValue]:
        """Get all config values with a given prefix."""
        with self._lock:
            return {k: v for k, v in self._values.items() if k.startswith(prefix)}

    # ═══════════════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════════════

    def load(self, filepath: Path):
        """Load config from JSON file."""
        self._config_file = filepath

        if not filepath.exists():
            return

        with open(filepath, 'r') as f:
            data = json.load(f)

        with self._lock:
            for key, value in data.items():
                if key in self._values:
                    self._values[key].set(value)

    def save(self, filepath: Optional[Path] = None):
        """Save current config to JSON file."""
        filepath = filepath or self._config_file
        if filepath is None:
            return

        with self._lock:
            data = {k: v.value for k, v in self._values.items()}

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    # ═══════════════════════════════════════════════════════════════════════
    # EXPORT
    # ═══════════════════════════════════════════════════════════════════════

    def to_dict(self) -> Dict[str, Any]:
        """Export all config for GUI display."""
        with self._lock:
            return {k: v.to_dict() for k, v in self._values.items()}

    def to_flat_dict(self) -> Dict[str, Any]:
        """Export just key->value pairs."""
        with self._lock:
            return {k: v.value for k, v in self._values.items()}


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════

_CONFIG: Optional[Config] = None
_CONFIG_LOCK = threading.Lock()


def get_config() -> Config:
    """Get the global config singleton."""
    global _CONFIG

    if _CONFIG is None:
        with _CONFIG_LOCK:
            if _CONFIG is None:
                _CONFIG = Config()

    return _CONFIG


def reset_config():
    """Reset the config singleton (for testing)."""
    global _CONFIG
    with _CONFIG_LOCK:
        _CONFIG = None
