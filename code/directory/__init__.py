"""
Directory - The control center of Akashic v2.

The Directory manages fairy registration, system health, and coordination.
It integrates with:
- PostalCore (Rust): Lock-free messaging
- TracerPool (Go): Universal tracing for perfect recall
- TensorFabric: 4D tensor state representation

Sleep States (for plug-and-play migration):
- SLEEPING: Dormant, minimal activity
- WAKING: Transitioning to awake
- DROWSY: Low activity, can sleep soon
- DREAMING: Background processing only
"""

from .fairy import DirectoryFairy, get_directory, set_directory
from .registry import FairyRegistry, FairyRecord
from .capability_index import CapabilityIndex
from .health import SystemHealth
from .migration import MigrationManager, FairyScanner, create_migration_manager
from .capability_checklist import (
    CapabilityChecklist,
    CapabilityCategory,
    get_capability_checklist,
    get_sourpatches_checklist,
    get_preset_capabilities,
    list_all_capabilities,
    list_capabilities_by_category,
    determine_fairy_preset,
    PRESETS,
    CAPABILITIES_REGISTRY,
)

__all__ = [
    # Main class
    "DirectoryFairy",
    "get_directory",
    "set_directory",
    # Components
    "FairyRegistry",
    "FairyRecord",
    "CapabilityIndex",
    "SystemHealth",
    # Migration
    "MigrationManager",
    "FairyScanner",
    "create_migration_manager",
    # Capability Checklist
    "CapabilityChecklist",
    "CapabilityCategory",
    "get_capability_checklist",
    "get_sourpatches_checklist",
    "get_preset_capabilities",
    "list_all_capabilities",
    "list_capabilities_by_category",
    "determine_fairy_preset",
    "PRESETS",
    "CAPABILITIES_REGISTRY",
]
