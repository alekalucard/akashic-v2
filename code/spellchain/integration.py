"""
SpellPool integration with server.py boot sequence.

The SpellPool must start BEFORE any fairies boot.
This is the ignition - the substrate that will hold all existence.

Usage:
    from spellchain.integration import create_spell_pool, get_spell_pool, stop_spell_pool

    # During server boot (BEFORE fairies)
    pool = create_spell_pool(max_workers=8)

    # Anywhere else that needs the pool
    pool = get_spell_pool()
    if pool:
        chain = pool.bootstrap_fairy(...)

    # During shutdown
    stop_spell_pool()

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from typing import Optional

from .pool import SpellPool


# Global SpellPool singleton
_SPELL_POOL: Optional[SpellPool] = None


def get_spell_pool() -> Optional[SpellPool]:
    """
    Get the global SpellPool instance.

    Returns:
        The SpellPool if created, None otherwise.
    """
    return _SPELL_POOL


def set_spell_pool(pool: SpellPool) -> None:
    """
    Register an externally-created SpellPool as the global singleton.

    Use this when server.py creates a SpellPool via infrastructure.spellchain
    (blood cell mode) instead of via create_spell_pool(). This ensures
    get_spell_pool() returns the correct pool for all fairies.

    Args:
        pool: The SpellPool instance to register.
    """
    global _SPELL_POOL
    _SPELL_POOL = pool


def create_spell_pool(
    max_workers: int = 8,
    tick_interval: float = 0.25,
) -> SpellPool:
    """
    Create and start the global SpellPool.

    Call this ONCE during server boot, BEFORE any fairies.
    If already created, returns the existing instance.

    Args:
        max_workers: Maximum concurrent spell executions (default 8)
        tick_interval: Seconds between ticks (default 0.25 = 4Hz)

    Returns:
        The global SpellPool instance.
    """
    global _SPELL_POOL

    if _SPELL_POOL is not None:
        print("[SpellPool] Already created - returning existing")
        return _SPELL_POOL

    _SPELL_POOL = SpellPool(
        max_workers=max_workers,
        tick_interval=tick_interval,
    )

    _SPELL_POOL.start()
    print(f"[SpellPool] Global pool ignited with {max_workers} workers")

    return _SPELL_POOL


def stop_spell_pool() -> None:
    """
    Stop the global SpellPool during shutdown.

    Gracefully dissolves all chains and shuts down the thread pool.
    Safe to call multiple times.
    """
    global _SPELL_POOL

    if _SPELL_POOL:
        _SPELL_POOL.stop()
        _SPELL_POOL = None
        print("[SpellPool] Global pool stopped")
