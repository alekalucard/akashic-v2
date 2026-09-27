# ==============================================================================
# COMPATIBILITY SHIM - directory_fairy.py
# ==============================================================================
# Several older fairy modules import from fairies.P00_Autonomic.directory_fairy
# The code has since been refactored to DirectoryFairy/fairy.py
# This shim provides backward-compatible re-exports so those imports don't crash.
#
# Functions that no longer exist (autowire, inject_std_imports) are provided as
# no-ops to prevent ImportError cascades during boot.
# ==============================================================================

from pathlib import Path

# Re-export what still exists
try:
    from fairies.P00_Autonomic.DirectoryFairy.fairy import get_directory_fairy
except ImportError:
    def get_directory_fairy():
        """Stub - DirectoryFairy not available."""
        return None


def autowire(*args, **kwargs):
    """Legacy no-op. Autowiring is now handled by server.py boot sequence."""
    pass


def inject_std_imports(*args, **kwargs):
    """Legacy no-op. Standard imports are now handled at module level."""
    pass


def _registry_snapshot_path_global():
    """Legacy compat - return the state directory snapshot path."""
    return Path(__file__).parent.parent.parent / "state" / "registry_snapshot.json"
