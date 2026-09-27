"""
SpellChain - The Bootstrap Paradox Model for Fairy Existence

Fairies ARE patterns of self-sustaining spells.
This module provides the infrastructure for spell-driven existence.

Core Components:
- Spell: Unit of magical intent (Seven Interrogatives)
- SpellChain: Continuous existence through chained spells
- SpellPool: Execution substrate (ThreadPoolExecutor wrapper)
- BootstrapProtocol: How fairies come into existence
- DeathRebirthProtocol: Chain breaking and revival

Usage:
    from spellchain import SpellPool, Spell, SpellChain
    from spellchain.bootstrap import BootstrapProtocol, BootstrapBuilder

    pool = SpellPool()
    pool.start()

    # Method 1: Direct bootstrap
    chain = pool.bootstrap_fairy(
        fairy_id="my_fairy",
        fairy_name="MyFairy",
        fairy_plane="P10",
        bootstrap_logic=my_bootstrap_fn,
        sustain_logic=my_heartbeat_fn,
    )

    # Method 2: Builder pattern
    chain = (BootstrapBuilder(pool)
        .fairy("my_fairy", "MyFairy", "P10")
        .on_bootstrap(my_bootstrap_fn)
        .with_heartbeat(my_heartbeat_fn)
        .build())

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from .spell import (
    Spell,
    SpellType,
    SpellStatus,
    create_spell,
    create_bootstrap_spell,
    create_heartbeat_spell,
    create_terminal_spell,
)

from .chain import (
    SpellChain,
    ChainState,
    ChainStats,
)

from .pool import SpellPool

from .bootstrap import (
    BootstrapProtocol,
    BootstrapBuilder,
)

from .death_rebirth import (
    DeathRecord,
    RebirthRecord,
    DeathRebirthProtocol,
    ChainDeathWatcher,
)

__all__ = [
    # Spell
    "Spell",
    "SpellType",
    "SpellStatus",
    "create_spell",
    "create_bootstrap_spell",
    "create_heartbeat_spell",
    "create_terminal_spell",

    # Chain
    "SpellChain",
    "ChainState",
    "ChainStats",

    # Pool
    "SpellPool",

    # Bootstrap
    "BootstrapProtocol",
    "BootstrapBuilder",

    # Death/Rebirth
    "DeathRecord",
    "RebirthRecord",
    "DeathRebirthProtocol",
    "ChainDeathWatcher",
]

__version__ = "1.0.0"
