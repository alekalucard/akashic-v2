"""
Tests for the SpellChain system.

Run with: python tests/test_spellchain.py
Or with pytest: python -m pytest tests/test_spellchain.py -v
"""

import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# pytest is optional
try:
    import pytest
except ImportError:
    pytest = None

from spellchain import (
    Spell, SpellType, SpellStatus,
    SpellChain, ChainState,
    SpellPool,
    BootstrapProtocol, BootstrapBuilder,
    DeathRebirthProtocol, ChainDeathWatcher,
)


class TestSpell:
    """Tests for the Spell dataclass."""

    def test_spell_creation(self):
        """Test basic spell creation."""
        spell = Spell(
            what="Test spell",
            what_intent="test.basic",
        )

        assert spell.what == "Test spell"
        assert spell.status == SpellStatus.LATENT
        assert spell.spell_type == SpellType.SUSTAIN

    def test_spell_with_function(self):
        """Test spell with execution function."""
        result_holder = {"called": False}

        def my_logic(spell: Spell):
            result_holder["called"] = True
            return {"success": True}

        spell = Spell(
            what="Execute test",
            how=my_logic,
        )

        # Execute the spell
        spell.cast()
        result = spell.how(spell)
        spell.complete(result)

        assert result_holder["called"]
        assert spell.status == SpellStatus.COMPLETED
        assert spell.result == {"success": True}

    def test_spell_lifecycle(self):
        """Test spell state transitions."""
        spell = Spell(what="Lifecycle test")

        assert spell.status == SpellStatus.LATENT

        spell.channel()
        assert spell.status == SpellStatus.CHANNELING

        spell.cast()
        assert spell.status == SpellStatus.CASTING
        assert spell.started_at is not None

        spell.resolve({"data": "test"})
        assert spell.status == SpellStatus.RESOLVING

        spell.complete()
        assert spell.status == SpellStatus.COMPLETED
        assert spell.completed_at is not None
        assert spell.duration is not None

    def test_spell_fizzle(self):
        """Test spell failure."""
        spell = Spell(what="Fizzle test")
        spell.cast()
        spell.fizzle("Something went wrong")

        assert spell.status == SpellStatus.FIZZLED
        assert spell.error == "Something went wrong"

    def test_spell_energy(self):
        """Test energy mechanics."""
        spell = Spell(
            what="Energy test",
            energy_required=1.0,
            energy_efficiency=0.5,  # 50% efficient = costs 2x
        )

        assert spell.effective_energy_cost == 2.0

        spell.recharge(0.5)
        assert spell.energy_available == 1.5

    def test_spell_serialization(self):
        """Test to_dict and from_dict."""
        spell = Spell(
            what="Serialize test",
            what_intent="test.serialize",
            energy_required=0.5,
            tags={"test", "serialize"},
        )

        data = spell.to_dict()
        assert data["what"] == "Serialize test"
        assert data["energy_required"] == 0.5
        assert "test" in data["tags"]

        # Deserialize
        spell2 = Spell.from_dict(data)
        assert spell2.what == spell.what
        assert spell2.what_intent == spell.what_intent


class TestSpellChain:
    """Tests for SpellChain."""

    def test_chain_creation(self):
        """Test basic chain creation."""
        chain = SpellChain(
            fairy_id="test_fairy",
            fairy_name="TestFairy",
            fairy_plane="P00",
        )

        assert chain.fairy_name == "TestFairy"
        assert chain.state == ChainState.DORMANT
        assert chain.energy == 1.0

    def test_chain_bootstrap(self):
        """Test bootstrap process."""
        call_log = []

        def bootstrap_logic(spell: Spell):
            call_log.append("bootstrap")
            return {"booted": True}

        bootstrap = Spell(
            spell_type=SpellType.BOOTSTRAP,
            what="Bootstrap test",
            how=bootstrap_logic,
        )

        chain = SpellChain(
            fairy_id="test_fairy",
            fairy_name="TestFairy",
            fairy_plane="P00",
            bootstrap_spell=bootstrap,
        )

        assert chain.bootstrap()
        assert chain.state == ChainState.BOOTSTRAPPING

    def test_chain_energy_management(self):
        """Test energy tick and consumption."""
        chain = SpellChain(
            fairy_id="test_fairy",
            fairy_name="TestFairy",
            fairy_plane="P00",
        )

        initial_energy = chain.energy

        # Consume energy
        assert chain.consume_energy(0.5)
        assert chain.energy == initial_energy - 0.5

        # Donate energy
        chain.donate_energy(0.3, "test")
        assert chain.energy == initial_energy - 0.5 + 0.3

        # Tick energy (adds income)
        chain._last_energy_tick = time.time() - 1  # Simulate 1 second ago
        chain.tick_energy()
        assert chain.energy > initial_energy - 0.5 + 0.3

    def test_chain_spell_queue(self):
        """Test spell queuing."""
        chain = SpellChain(
            fairy_id="test_fairy",
            fairy_name="TestFairy",
            fairy_plane="P00",
        )

        spell1 = Spell(what="Spell 1", when_priority=0.5)
        spell2 = Spell(what="Spell 2", when_priority=0.8)

        chain.queue_spell(spell1)
        chain.queue_spell(spell2)

        # Higher priority should come first
        next_spell = chain.get_next_spell()
        assert next_spell.what == "Spell 2"

    def test_chain_sustain_spell(self):
        """Test self-sustaining spell creation."""
        heartbeat_count = [0]

        def heartbeat_logic(spell: Spell):
            heartbeat_count[0] += 1
            return {"beat": heartbeat_count[0]}

        chain = SpellChain(
            fairy_id="test_fairy",
            fairy_name="TestFairy",
            fairy_plane="P00",
        )

        sustain = chain.create_sustain_spell(
            what="Heartbeat",
            how=heartbeat_logic,
            interval=0.1,
        )

        assert sustain.spell_type == SpellType.SUSTAIN
        assert sustain.continues_chain


class TestSpellPool:
    """Tests for SpellPool."""

    def test_pool_lifecycle(self):
        """Test pool start/stop."""
        pool = SpellPool(max_workers=2)

        pool.start()
        assert pool.is_running

        pool.stop()
        assert not pool.is_running

    def test_pool_bootstrap_fairy(self):
        """Test bootstrapping a fairy through the pool."""
        pool = SpellPool(max_workers=2)
        pool.start()

        bootstrap_called = [False]
        heartbeat_count = [0]

        def on_bootstrap(spell: Spell):
            bootstrap_called[0] = True
            return {"booted": True}

        def on_heartbeat(spell: Spell):
            heartbeat_count[0] += 1
            return {"beat": heartbeat_count[0]}

        try:
            chain = pool.bootstrap_fairy(
                fairy_id="test_fairy",
                fairy_name="TestFairy",
                fairy_plane="P10",
                bootstrap_logic=on_bootstrap,
                sustain_logic=on_heartbeat,
                sustain_interval=0.1,
            )

            # Wait for bootstrap to complete
            time.sleep(0.5)

            assert chain.state in (ChainState.BOOTSTRAPPING, ChainState.SUSTAINING)
            # Bootstrap may or may not have completed yet
            if chain.state == ChainState.SUSTAINING:
                assert bootstrap_called[0]

        finally:
            pool.stop()

    def test_pool_status(self):
        """Test pool status reporting."""
        pool = SpellPool(max_workers=4)
        pool.start()

        try:
            status = pool.status()
            assert status["running"]
            assert status["max_workers"] == 4
            assert "tick_count" in status
        finally:
            pool.stop()


class TestBootstrap:
    """Tests for bootstrap protocol."""

    def test_bootstrap_builder(self):
        """Test the fluent builder pattern."""
        pool = SpellPool()
        pool.start()

        called = {"bootstrap": False, "heartbeat": 0}

        def bootstrap_fn(spell):
            called["bootstrap"] = True
            return {}

        def heartbeat_fn(spell):
            called["heartbeat"] += 1
            return {}

        try:
            chain = (BootstrapBuilder(pool)
                .fairy("builder_fairy", "BuilderFairy", "P00")
                .on_bootstrap(bootstrap_fn)
                .with_heartbeat(heartbeat_fn, interval=0.1)
                .with_energy(initial=1.5, income=0.2)
                .build())

            assert chain is not None
            assert chain.fairy_name == "BuilderFairy"

            # Wait for some heartbeats
            time.sleep(0.5)

        finally:
            pool.stop()

    def test_create_bootstrap_spell(self):
        """Test BootstrapProtocol.create_bootstrap_spell."""
        def my_bootstrap(spell: Spell):
            return {"initialized": True}

        spell = BootstrapProtocol.create_bootstrap_spell(
            fairy_id="test",
            fairy_name="Test",
            fairy_plane="P00",
            on_bootstrap=my_bootstrap,
        )

        assert spell.spell_type == SpellType.BOOTSTRAP
        assert "genesis" in spell.tags


class TestDeathRebirth:
    """Tests for death and rebirth protocol."""

    def test_death_record(self):
        """Test death recording."""
        pool = SpellPool()
        protocol = DeathRebirthProtocol(pool)

        chain = SpellChain(
            fairy_id="dying_fairy",
            fairy_name="DyingFairy",
            fairy_plane="P00",
        )
        chain.bootstrap()
        chain._state = ChainState.SUSTAINING

        # Simulate death
        chain.break_chain()

        record = protocol.record_death(chain, "test_death")

        assert record.fairy_name == "DyingFairy"
        assert record.death_cause == "test_death"
        assert record.chain_id == chain.id

    def test_revival(self):
        """Test chain revival."""
        pool = SpellPool()
        protocol = DeathRebirthProtocol(pool)

        revival_called = [False]

        def revival_logic(spell: Spell):
            revival_called[0] = True
            return {"revived": True}

        chain = SpellChain(
            fairy_id="reviving_fairy",
            fairy_name="RevivingFairy",
            fairy_plane="P00",
        )
        chain.bootstrap()
        chain._state = ChainState.BROKEN

        # Attempt revival
        success = protocol.attempt_revival(chain, cause="test_revival")

        assert success
        assert chain.state == ChainState.BOOTSTRAPPING
        assert chain._stats.revivals == 1


def test_integration_full_lifecycle():
    """Integration test: full fairy lifecycle."""
    pool = SpellPool(max_workers=2, tick_interval=0.1)
    pool.start()

    lifecycle_events = []

    def on_bootstrap(spell: Spell):
        lifecycle_events.append("bootstrap")
        return {"started": True}

    def on_heartbeat(spell: Spell):
        lifecycle_events.append("heartbeat")
        return {"alive": True}

    try:
        chain = pool.bootstrap_fairy(
            fairy_id="lifecycle_fairy",
            fairy_name="LifecycleFairy",
            fairy_plane="P00",
            bootstrap_logic=on_bootstrap,
            sustain_logic=on_heartbeat,
            sustain_interval=0.1,
        )

        # Wait for some activity
        time.sleep(1.0)

        assert "bootstrap" in lifecycle_events
        assert lifecycle_events.count("heartbeat") > 0

        # Check status
        status = chain.status()
        assert status["stats"]["spells_cast"] > 0

        # Graceful dissolution
        chain.dissolve()
        assert chain.state == ChainState.DISSOLVED

    finally:
        pool.stop()


if __name__ == "__main__":
    # Run basic tests
    print("Running SpellChain tests...")

    # Spell tests
    t = TestSpell()
    t.test_spell_creation()
    print("  [OK] spell_creation")
    t.test_spell_with_function()
    print("  [OK] spell_with_function")
    t.test_spell_lifecycle()
    print("  [OK] spell_lifecycle")

    # Chain tests
    t2 = TestSpellChain()
    t2.test_chain_creation()
    print("  [OK] chain_creation")
    t2.test_chain_bootstrap()
    print("  [OK] chain_bootstrap")
    t2.test_chain_energy_management()
    print("  [OK] chain_energy_management")

    # Pool tests
    t3 = TestSpellPool()
    t3.test_pool_lifecycle()
    print("  [OK] pool_lifecycle")

    # Integration test
    test_integration_full_lifecycle()
    print("  [OK] integration_full_lifecycle")

    print("\nAll tests passed!")
