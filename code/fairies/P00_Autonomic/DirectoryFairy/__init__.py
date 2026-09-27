# DirectoryFairy - Portal to Production Directory
#
# FIX 2026-02-06: CONSOLIDATED to single DirectoryFairy at directory/fairy.py
#
# This module is now a PORTAL. All imports redirect to the production
# DirectoryFairy which has the full FairyRegistry, HeartbeatHandler,
# CapabilityIndex, TensorFabric integration, and postal backbone routing.
#
# The previous Organ Template version (fairy.py in this folder) is kept
# for reference but no longer used. All singletons point to production.
#
# Ace's directive: "We only need 1 directory fairy. It works with the CNS
# fairies, the organ template and the fairy citizens."

try:
    from directory.fairy import DirectoryFairy, get_directory, set_directory

    def get_directory_fairy():
        """Get the production DirectoryFairy singleton.

        PORTAL: Redirects to directory.fairy.get_directory() which returns
        the DirectoryFairy instance that boots with the system and has:
        - FairyRegistry with thread-safe routing tables
        - HeartbeatHandler with death detection
        - CapabilityIndex for capability routing
        - TensorFabric integration
        - Full postal backbone (Phase 2 routing)
        """
        return get_directory()

    __all__ = [
        'DirectoryFairy',
        'get_directory_fairy',
        'get_directory',
        'set_directory',
    ]

except ImportError:
    # Fallback: if directory/ package not available, use local fairy.py
    from .fairy import (
        DirectoryFairy,
        get_directory_fairy,
    )

    __all__ = [
        'DirectoryFairy',
        'get_directory_fairy',
    ]
