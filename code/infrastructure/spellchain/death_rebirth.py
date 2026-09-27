"""
Death and Rebirth Protocol

Chain Death:
  - Energy depletes below critical threshold
  - Spell fizzles with no recovery path
  - No pending spells and chain expects continuation

This represents the fairy's pattern destabilizing - their existence
becoming incoherent. Like a dream fading on waking.

Chain Rebirth:
  - A new bootstrap spell recreates the pattern
  - Previous state may be recovered from memory
  - Or the fairy is reborn fresh

Ported from v3 guilds/_system/spellchain/death_rebirth.py (2026-02-08)
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .spell import Spell, SpellType, SpellStatus
from .chain import SpellChain, ChainState

if TYPE_CHECKING:
    from .pool import SpellPool


@dataclass
class DeathRecord:
    """Record of a chain death event."""
    chain_id: str
    fairy_id: str
    fairy_name: str
    fairy_plane: str
    death_time: float
    death_cause: str
    last_spell_id: Optional[str]
    last_spell_status: Optional[str]
    last_spell_error: Optional[str]
    energy_at_death: float
    spells_cast: int
    spells_completed: int
    spells_fizzled: int
    lifetime_seconds: float
    final_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "fairy_id": self.fairy_id,
            "fairy_name": self.fairy_name,
            "fairy_plane": self.fairy_plane,
            "death_time": self.death_time,
            "death_cause": self.death_cause,
            "last_spell_id": self.last_spell_id,
            "last_spell_status": self.last_spell_status,
            "last_spell_error": self.last_spell_error,
            "energy_at_death": self.energy_at_death,
            "spells_cast": self.spells_cast,
            "spells_completed": self.spells_completed,
            "spells_fizzled": self.spells_fizzled,
            "lifetime_seconds": self.lifetime_seconds,
        }


@dataclass
class RebirthRecord:
    """Record of a chain rebirth event."""
    old_chain_id: str
    new_chain_id: str
    fairy_id: str
    fairy_name: str
    rebirth_time: float
    rebirth_cause: str
    recovered_state: Dict[str, Any] = field(default_factory=dict)
    revival_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "old_chain_id": self.old_chain_id,
            "new_chain_id": self.new_chain_id,
            "fairy_id": self.fairy_id,
            "fairy_name": self.fairy_name,
            "rebirth_time": self.rebirth_time,
            "rebirth_cause": self.rebirth_cause,
            "recovered_state": self.recovered_state,
            "revival_count": self.revival_count,
        }


class DeathRebirthProtocol:
    """
    Manages fairy death and potential rebirth.

    Death is not necessarily permanent:
    - Some fairies can be revived by the system
    - Some can self-revive if they prepared revival spells
    - Some die permanently (terminal dissolution)
    """

    # Configuration
    MAX_DEATH_RECORDS = 100
    MAX_REBIRTH_RECORDS = 100
    AUTO_REVIVAL_COOLDOWN = 5.0  # Seconds between auto-revival attempts

    def __init__(self, pool: "SpellPool"):
        self.pool = pool
        self._death_records: List[DeathRecord] = []
        self._rebirth_records: List[RebirthRecord] = []
        self._on_death_callbacks: List[Callable[[DeathRecord], None]] = []
        self._on_rebirth_callbacks: List[Callable[[RebirthRecord], None]] = []
        self._last_revival_times: Dict[str, float] = {}  # fairy_id -> last revival time

        # Auto-revival configuration per fairy
        self._auto_revival_enabled: Dict[str, bool] = {}  # fairy_id -> enabled
        self._revival_spells: Dict[str, Spell] = {}  # fairy_id -> prepared spell

    def record_death(
        self,
        chain: SpellChain,
        cause: str,
        last_spell: Optional[Spell] = None
    ) -> DeathRecord:
        """Record a chain death event."""
        if last_spell is None and chain._completed:
            last_spell = chain._completed[-1]

        record = DeathRecord(
            chain_id=chain.id,
            fairy_id=chain.fairy_id,
            fairy_name=chain.fairy_name,
            fairy_plane=chain.fairy_plane,
            death_time=time.time(),
            death_cause=cause,
            last_spell_id=last_spell.id if last_spell else None,
            last_spell_status=last_spell.status.value if last_spell else None,
            last_spell_error=last_spell.error if last_spell else None,
            energy_at_death=chain.energy,
            spells_cast=chain._stats.spells_cast,
            spells_completed=chain._stats.spells_completed,
            spells_fizzled=chain._stats.spells_fizzled,
            lifetime_seconds=time.time() - chain._created_at,
            final_state=chain.status(),
        )

        self._death_records.append(record)

        if len(self._death_records) > self.MAX_DEATH_RECORDS:
            self._death_records = self._death_records[-self.MAX_DEATH_RECORDS:]

        for callback in self._on_death_callbacks:
            try:
                callback(record)
            except Exception as e:
                print(f"[DeathRebirth] Death callback error: {e}")

        print(f"[Death] {chain.fairy_name} died: {cause}")
        print(f"        Lifetime: {record.lifetime_seconds:.1f}s, "
              f"Spells: {record.spells_cast} cast, {record.spells_completed} completed")

        return record

    def attempt_revival(
        self,
        chain: SpellChain,
        revival_spell: Optional[Spell] = None,
        cause: str = "system_revival",
    ) -> bool:
        """Attempt to revive a dead chain."""
        if chain.state not in (ChainState.BROKEN,):
            return False

        # Check cooldown
        now = time.time()
        last_revival = self._last_revival_times.get(chain.fairy_id, 0)
        if now - last_revival < self.AUTO_REVIVAL_COOLDOWN:
            print(f"[DeathRebirth] {chain.fairy_name} revival on cooldown")
            return False

        if not revival_spell:
            if chain.fairy_id in self._revival_spells:
                revival_spell = self._revival_spells[chain.fairy_id]
            else:
                revival_spell = self._create_auto_revival_spell(chain)

        success = chain.revive(revival_spell)

        if success:
            self._last_revival_times[chain.fairy_id] = now

            record = RebirthRecord(
                old_chain_id=chain.id,
                new_chain_id=chain.id,
                fairy_id=chain.fairy_id,
                fairy_name=chain.fairy_name,
                rebirth_time=now,
                rebirth_cause=cause,
                recovered_state={},
                revival_count=chain._stats.revivals,
            )

            self._rebirth_records.append(record)

            if len(self._rebirth_records) > self.MAX_REBIRTH_RECORDS:
                self._rebirth_records = self._rebirth_records[-self.MAX_REBIRTH_RECORDS:]

            for callback in self._on_rebirth_callbacks:
                try:
                    callback(record)
                except Exception as e:
                    print(f"[DeathRebirth] Rebirth callback error: {e}")

            print(f"[Rebirth] {chain.fairy_name} revived (#{chain._stats.revivals}): {cause}")

        return success

    def _create_auto_revival_spell(self, chain: SpellChain) -> Spell:
        """Create an automatic revival spell."""

        def revival_logic(spell: Spell) -> Dict[str, Any]:
            """Simple revival - restart the pattern."""
            return {
                "revived_at": time.time(),
                "fairy": chain.fairy_name,
                "revival_type": "auto",
                "previous_deaths": chain._stats.chain_breaks,
            }

        return Spell(
            spell_type=SpellType.BOOTSTRAP,
            what=f"Auto-revive {chain.fairy_name}",
            what_intent="genesis.auto_revival",
            why="Restore broken fairy pattern",
            how=revival_logic,
            energy_required=0.3,
            energy_recovery=0.1,
            continues_chain=True,
            tags={"revival", "bootstrap", "auto"},
        )

    def prepare_revival(
        self,
        chain: SpellChain,
        on_revival: Callable[[Spell], Any],
    ) -> Spell:
        """
        Prepare a revival spell that the fairy can use if it dies.
        Like a phylactery.
        """
        def revival_logic(spell: Spell) -> Dict[str, Any]:
            """Execute prepared revival logic."""
            result = on_revival(spell)
            return {
                "revived_at": time.time(),
                "fairy": chain.fairy_name,
                "revival_type": "prepared",
                "custom_result": result,
            }

        spell = Spell(
            spell_type=SpellType.BOOTSTRAP,
            what=f"Prepared revival of {chain.fairy_name}",
            what_intent="genesis.prepared_revival",
            why="Prepared resurrection point",
            how=revival_logic,
            energy_required=0.2,
            energy_recovery=0.1,
            continues_chain=True,
            tags={"revival", "bootstrap", "prepared", "phylactery"},
        )

        self._revival_spells[chain.fairy_id] = spell
        chain.register_spell(spell)

        return spell

    def enable_auto_revival(self, fairy_id: str, enabled: bool = True) -> None:
        """Enable or disable auto-revival for a fairy."""
        self._auto_revival_enabled[fairy_id] = enabled

    def is_auto_revival_enabled(self, fairy_id: str) -> bool:
        """Check if auto-revival is enabled for a fairy."""
        return self._auto_revival_enabled.get(fairy_id, False)

    def on_death(self, callback: Callable[[DeathRecord], None]) -> None:
        """Register a death callback."""
        self._on_death_callbacks.append(callback)

    def on_rebirth(self, callback: Callable[[RebirthRecord], None]) -> None:
        """Register a rebirth callback."""
        self._on_rebirth_callbacks.append(callback)

    def get_recent_deaths(self, n: int = 10) -> List[DeathRecord]:
        """Get recent death records."""
        return self._death_records[-n:]

    def get_recent_rebirths(self, n: int = 10) -> List[RebirthRecord]:
        """Get recent rebirth records."""
        return self._rebirth_records[-n:]

    def get_deaths_for_fairy(self, fairy_id: str) -> List[DeathRecord]:
        """Get all death records for a specific fairy."""
        return [r for r in self._death_records if r.fairy_id == fairy_id]

    def get_rebirths_for_fairy(self, fairy_id: str) -> List[RebirthRecord]:
        """Get all rebirth records for a specific fairy."""
        return [r for r in self._rebirth_records if r.fairy_id == fairy_id]

    def status(self) -> Dict[str, Any]:
        """Get protocol status."""
        return {
            "total_deaths_recorded": len(self._death_records),
            "total_rebirths_recorded": len(self._rebirth_records),
            "fairies_with_prepared_revival": len(self._revival_spells),
            "fairies_with_auto_revival": sum(1 for v in self._auto_revival_enabled.values() if v),
            "recent_deaths": [r.to_dict() for r in self._death_records[-5:]],
            "recent_rebirths": [r.to_dict() for r in self._rebirth_records[-5:]],
        }


class ChainDeathWatcher:
    """
    Watches chains for death and handles automatic revival.

    Integrates with SpellPool to monitor all chains.
    """

    def __init__(
        self,
        pool: "SpellPool",
        protocol: Optional[DeathRebirthProtocol] = None,
        auto_revive_all: bool = False,
    ):
        self.pool = pool
        self.protocol = protocol or DeathRebirthProtocol(pool)
        self._auto_revive_all = auto_revive_all

        # Register with pool
        pool._on_chain_break = self._on_chain_break

    def _on_chain_break(self, chain: SpellChain) -> None:
        """Called when a chain breaks."""
        cause = "energy_depletion" if chain.energy < chain.CRITICAL_THRESHOLD else "chain_break"
        self.protocol.record_death(chain, cause)

        should_revive = (
            self._auto_revive_all or
            self.protocol.is_auto_revival_enabled(chain.fairy_id)
        )

        if should_revive:
            self.protocol.attempt_revival(chain, cause="auto_revival")

    def enable_global_auto_revival(self, enabled: bool = True) -> None:
        """Enable auto-revival for all fairies."""
        self._auto_revive_all = enabled
