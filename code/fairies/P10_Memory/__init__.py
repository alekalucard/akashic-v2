"""P10_Memory - Memory plane fairies.

LAZY IMPORT PATTERN (2026-02-02)
================================
Fairies are imported ON DEMAND when first accessed, not at package load time.
This prevents circular import issues during fairy_template initialization.

Usage:
    from fairies.P10_Memory import get_memory_fairy  # Lazy - no import until called
    memory = get_memory_fairy()  # NOW the fairy loads

All exports are still available, they just load when accessed.
"""

import sys
from pathlib import Path

# Setup paths - ROOT must be FIRST to find real P00_Autonomic (not fairies/P00_Autonomic shadow)
_ROOT = Path(__file__).parent.parent.parent
for _p in [str(_ROOT / "fairies"), str(_ROOT)]:  # Reverse order - ROOT ends up first
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ============================================================================
# LAZY IMPORT INFRASTRUCTURE
# ============================================================================
# We define getter functions that load modules on first access.
# This prevents circular import chains during fairy_template initialization.

_LOADED_MODULES = {}

def _lazy_import(submodule: str, name: str):
    """Lazily import and cache a name from a submodule."""
    key = f"{submodule}.{name}"
    if key not in _LOADED_MODULES:
        try:
            mod = __import__(f"fairies.P10_Memory.{submodule}", fromlist=[name])
            _LOADED_MODULES[key] = getattr(mod, name)
        except (ImportError, AttributeError):
            _LOADED_MODULES[key] = None
    return _LOADED_MODULES[key]


# ============================================================================
# LAZY ACCESSOR FUNCTIONS
# ============================================================================
# These are the PRIMARY way to access fairies - they load on first call.

def get_memory_fairy():
    """Get the SRMMemoryFairy singleton (lazy load)."""
    fn = _lazy_import("SRMMemoryFairy", "get_memory_fairy")
    return fn() if fn else None

def set_memory_fairy(fairy):
    """Set the SRMMemoryFairy singleton."""
    fn = _lazy_import("SRMMemoryFairy", "set_memory_fairy")
    if fn: fn(fairy)

def get_ingest_fairy():
    """Get the SRMIngestFairy singleton (lazy load)."""
    fn = _lazy_import("SRMIngestFairy", "get_ingest_fairy")
    return fn() if fn else None

def set_ingest_fairy(fairy):
    """Set the SRMIngestFairy singleton."""
    fn = _lazy_import("SRMIngestFairy", "set_ingest_fairy")
    if fn: fn(fairy)

def get_recall_fairy():
    """Get the SRMRecallFairy singleton (lazy load)."""
    fn = _lazy_import("SRMRecallFairy", "get_recall_fairy")
    return fn() if fn else None

def set_recall_fairy(fairy):
    """Set the SRMRecallFairy singleton."""
    fn = _lazy_import("SRMRecallFairy", "set_recall_fairy")
    if fn: fn(fairy)

def get_backup_fairy():
    """Get the BackupFairy singleton (lazy load)."""
    fn = _lazy_import("BackupFairy", "get_backup_fairy")
    return fn() if fn else None

def set_backup_fairy(fairy):
    """Set the BackupFairy singleton."""
    fn = _lazy_import("BackupFairy", "set_backup_fairy")
    if fn: fn(fairy)

def get_seed_fairy():
    """Get the SeedFairy singleton (lazy load)."""
    fn = _lazy_import("SeedFairy", "get_seed_fairy")
    return fn() if fn else None

def set_seed_fairy(fairy):
    """Set the SeedFairy singleton."""
    fn = _lazy_import("SeedFairy", "set_seed_fairy")
    if fn: fn(fairy)

def get_working_memory_fairy():
    """Get the WorkingMemoryFairy singleton (lazy load)."""
    fn = _lazy_import("WorkingMemoryFairy", "get_working_memory_fairy")
    return fn() if fn else None

def set_working_memory_fairy(fairy):
    """Set the WorkingMemoryFairy singleton."""
    fn = _lazy_import("WorkingMemoryFairy", "set_working_memory_fairy")
    if fn: fn(fairy)

def get_forensic_fairy():
    """Get the ForensicScribeFairy singleton (lazy load)."""
    fn = _lazy_import("ForensicScribeFairy", "get_forensic_fairy")
    return fn() if fn else None

def set_forensic_fairy(fairy):
    """Set the ForensicScribeFairy singleton."""
    fn = _lazy_import("ForensicScribeFairy", "set_forensic_fairy")
    if fn: fn(fairy)

def get_media_ingest_fairy():
    """Get the MediaIngestFairy singleton (lazy load)."""
    fn = _lazy_import("MediaIngestFairy", "get_media_ingest_fairy")
    return fn() if fn else None

def set_media_ingest_fairy(fairy):
    """Set the MediaIngestFairy singleton."""
    fn = _lazy_import("MediaIngestFairy", "set_media_ingest_fairy")
    if fn: fn(fairy)

def get_akashic_librarian():
    """Get the AkashicLibrarianFairy singleton (lazy load)."""
    fn = _lazy_import("AkashicLibrarianFairy", "get_akashic_librarian")
    return fn() if fn else None

def set_akashic_librarian(fairy):
    """Set the AkashicLibrarianFairy singleton."""
    fn = _lazy_import("AkashicLibrarianFairy", "set_akashic_librarian")
    if fn: fn(fairy)

def get_memory_consolidation_fairy():
    """Get the MemoryConsolidationFairy singleton (lazy load)."""
    fn = _lazy_import("MemoryConsolidationFairy", "get_memory_consolidation_fairy")
    return fn() if fn else None

def set_memory_consolidation_fairy(fairy):
    """Set the MemoryConsolidationFairy singleton."""
    fn = _lazy_import("MemoryConsolidationFairy", "set_memory_consolidation_fairy")
    if fn: fn(fairy)

def get_blueprint_diary_hub():
    """Get the BlueprintDiaryHubFairy singleton (lazy load)."""
    fn = _lazy_import("BlueprintDiaryHubFairy", "get_blueprint_diary_hub")
    return fn() if fn else None

def set_blueprint_diary_hub(fairy):
    """Set the BlueprintDiaryHubFairy singleton."""
    fn = _lazy_import("BlueprintDiaryHubFairy", "set_blueprint_diary_hub")
    if fn: fn(fairy)

def backup_before_edit(path, reason="edit"):
    """Backup a file before editing (lazy load)."""
    fn = _lazy_import("BackupFairy", "backup_before_edit")
    if fn: fn(path, reason)

def backup_critical(path, reason="critical"):
    """Backup a critical file (lazy load)."""
    fn = _lazy_import("BackupFairy", "backup_critical")
    if fn: fn(path, reason)

def build_helix_coordinate(*args, **kwargs):
    """Build a helix coordinate (lazy load)."""
    fn = _lazy_import("SRMIngestFairy", "build_helix_coordinate")
    return fn(*args, **kwargs) if fn else None


# ============================================================================
# EXPORTS - All still available but load lazily
# ============================================================================
__all__ = [
    # Accessor functions - PREFERRED way to access fairies
    "get_memory_fairy", "set_memory_fairy",
    "get_ingest_fairy", "set_ingest_fairy",
    "get_recall_fairy", "set_recall_fairy",
    "get_backup_fairy", "set_backup_fairy",
    "get_seed_fairy", "set_seed_fairy",
    "get_working_memory_fairy", "set_working_memory_fairy",
    "get_forensic_fairy", "set_forensic_fairy",
    "get_media_ingest_fairy", "set_media_ingest_fairy",
    "get_akashic_librarian", "set_akashic_librarian",
    "get_memory_consolidation_fairy", "set_memory_consolidation_fairy",
    "get_blueprint_diary_hub", "set_blueprint_diary_hub",
    "backup_before_edit", "backup_critical",
    "build_helix_coordinate",
]

# NOTE: Classes like SRMMemoryFairy, MemoryRecord, etc. are NOT exported here anymore.
# To get them, import directly: from fairies.P10_Memory.SRMMemoryFairy import SRMMemoryFairy
# This prevents circular imports during package initialization.
