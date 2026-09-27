"""
Tests for FairyBody - Somatic and Affect State Management

TDD: These tests are written FIRST, before implementation.
Run with: python -m pytest tests/test_fairy_template/test_body.py -v
"""

import sys
import threading
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest


class TestFairyBodyBasics:
    """Test FairyBody creation and basic state fields."""

    def test_creation_with_name(self):
        """FairyBody requires a fairy_name."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        assert body.fairy_name == "TestFairy"

    def test_default_energy(self):
        """Energy defaults to 1.0 (full)."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        assert body.energy == 1.0

    def test_default_coherence(self):
        """Coherence defaults to 0.5 (neutral clarity)."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        assert body.coherence == 0.5

    def test_default_valence(self):
        """Valence defaults to 0.0 (neutral emotion)."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        assert body.valence == 0.0

    def test_default_arousal(self):
        """Arousal defaults to 0.5 (mid activation)."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        assert body.arousal == 0.5

    def test_default_primary_affect(self):
        """Primary affect defaults to 'neutral'."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        assert body.primary_affect == "neutral"

    def test_default_circadian_phase(self):
        """Circadian phase defaults to 'unknown'."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        assert body.circadian_phase == "unknown"

    def test_default_sedation_level(self):
        """Sedation level defaults to 0.0 (awake)."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        assert body.sedation_level == 0.0


class TestFairyBodyProperties:
    """Test FairyBody computed properties."""

    def test_is_depleted_when_low_energy(self):
        """is_depleted is True when energy < 0.2."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 0.1})
        assert body.is_depleted is True

    def test_is_not_depleted_when_normal_energy(self):
        """is_depleted is False when energy >= 0.2."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 0.5})
        assert body.is_depleted is False

    def test_is_depleted_boundary(self):
        """is_depleted boundary at exactly 0.2."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 0.2})
        assert body.is_depleted is False  # 0.2 is NOT depleted

        body.update_somatic({"energy": 0.19})
        assert body.is_depleted is True  # Below 0.2 IS depleted

    def test_can_work_when_healthy(self):
        """can_work is True when energy > 0.3 AND sedation < 0.7."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 0.5})
        body.update_sedation(0.3)
        assert body.can_work is True

    def test_cannot_work_when_low_energy(self):
        """can_work is False when energy <= 0.3."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 0.3})
        body.update_sedation(0.0)
        assert body.can_work is False

    def test_cannot_work_when_sedated(self):
        """can_work is False when sedation >= 0.7."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 1.0})
        body.update_sedation(0.7)
        assert body.can_work is False

    def test_affect_property_returns_dict(self):
        """affect property returns {valence, arousal, primary}."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_affect({"valence": 0.5, "arousal": 0.8, "primary": "joy"})

        affect = body.affect
        assert isinstance(affect, dict)
        assert affect["valence"] == 0.5
        assert affect["arousal"] == 0.8
        assert affect["primary"] == "joy"


class TestFairyBodyUpdates:
    """Test FairyBody update methods."""

    def test_update_somatic_energy(self):
        """update_somatic updates energy."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 0.7})
        assert body.energy == 0.7

    def test_update_somatic_coherence(self):
        """update_somatic updates coherence."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"coherence": 0.9})
        assert body.coherence == 0.9

    def test_update_somatic_both(self):
        """update_somatic can update both energy and coherence."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 0.6, "coherence": 0.8})
        assert body.energy == 0.6
        assert body.coherence == 0.8

    def test_update_somatic_clamps_energy_low(self):
        """update_somatic clamps energy to 0.0 minimum."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": -0.5})
        assert body.energy == 0.0

    def test_update_somatic_clamps_energy_high(self):
        """update_somatic clamps energy to 1.0 maximum."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 1.5})
        assert body.energy == 1.0

    def test_update_somatic_clamps_coherence(self):
        """update_somatic clamps coherence to [0.0, 1.0]."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"coherence": -0.1})
        assert body.coherence == 0.0

        body.update_somatic({"coherence": 1.5})
        assert body.coherence == 1.0

    def test_update_affect_valence(self):
        """update_affect updates valence."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_affect({"valence": 0.7})
        assert body.valence == 0.7

    def test_update_affect_arousal(self):
        """update_affect updates arousal."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_affect({"arousal": 0.9})
        assert body.arousal == 0.9

    def test_update_affect_primary(self):
        """update_affect updates primary affect."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_affect({"primary": "excitement"})
        assert body.primary_affect == "excitement"

    def test_update_affect_clamps_valence(self):
        """update_affect clamps valence to [-1.0, 1.0]."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_affect({"valence": -2.0})
        assert body.valence == -1.0

        body.update_affect({"valence": 2.0})
        assert body.valence == 1.0

    def test_update_affect_clamps_arousal(self):
        """update_affect clamps arousal to [0.0, 1.0]."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_affect({"arousal": -0.5})
        assert body.arousal == 0.0

        body.update_affect({"arousal": 1.5})
        assert body.arousal == 1.0

    def test_update_circadian(self):
        """update_circadian updates circadian_phase."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_circadian("morning")
        assert body.circadian_phase == "morning"

    def test_update_sedation(self):
        """update_sedation updates sedation_level."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_sedation(0.5)
        assert body.sedation_level == 0.5

    def test_update_sedation_clamps(self):
        """update_sedation clamps to [0.0, 1.0]."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_sedation(-0.5)
        assert body.sedation_level == 0.0

        body.update_sedation(1.5)
        assert body.sedation_level == 1.0


class TestFairyBodySerialization:
    """Test FairyBody serialization."""

    def test_to_dict_contains_all_fields(self):
        """to_dict returns all state fields."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 0.8, "coherence": 0.7})
        body.update_affect({"valence": 0.3, "arousal": 0.6, "primary": "curiosity"})
        body.update_circadian("afternoon")
        body.update_sedation(0.1)

        d = body.to_dict()

        assert d["fairy_name"] == "TestFairy"
        assert d["energy"] == 0.8
        assert d["coherence"] == 0.7
        assert d["valence"] == 0.3
        assert d["arousal"] == 0.6
        assert d["primary_affect"] == "curiosity"
        assert d["circadian_phase"] == "afternoon"
        assert d["sedation_level"] == 0.1

    def test_to_dict_is_copy(self):
        """to_dict returns a copy, not the internal state."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        d = body.to_dict()
        d["energy"] = 0.0

        assert body.energy == 1.0  # Original unchanged


class TestFairyBodyThreadSafety:
    """Test FairyBody thread safety."""

    def test_concurrent_updates_no_corruption(self):
        """Concurrent updates don't corrupt state."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        errors = []

        def update_somatic():
            try:
                for i in range(100):
                    body.update_somatic({"energy": i / 100})
            except Exception as e:
                errors.append(e)

        def update_affect():
            try:
                for i in range(100):
                    body.update_affect({"valence": (i - 50) / 50})
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=update_somatic)
        t2 = threading.Thread(target=update_affect)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors
        # State should be valid after concurrent updates
        assert 0.0 <= body.energy <= 1.0
        assert -1.0 <= body.valence <= 1.0

    def test_to_dict_during_updates(self):
        """to_dict returns consistent state during updates."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        snapshots = []
        errors = []

        def update_loop():
            try:
                for i in range(50):
                    body.update_somatic({"energy": 0.5})
                    body.update_affect({"valence": 0.5})
            except Exception as e:
                errors.append(e)

        def snapshot_loop():
            try:
                for i in range(50):
                    d = body.to_dict()
                    snapshots.append(d)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=update_loop)
        t2 = threading.Thread(target=snapshot_loop)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors
        # All snapshots should have valid structure
        for snap in snapshots:
            assert "fairy_name" in snap
            assert "energy" in snap
            assert "valence" in snap


class TestFairyBodyEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_somatic_update(self):
        """Empty dict update doesn't change state."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        original_energy = body.energy
        body.update_somatic({})
        assert body.energy == original_energy

    def test_empty_affect_update(self):
        """Empty dict update doesn't change state."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        original_valence = body.valence
        body.update_affect({})
        assert body.valence == original_valence

    def test_unknown_keys_ignored(self):
        """Unknown keys in update dicts are ignored."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 0.5, "unknown_key": "value"})
        assert body.energy == 0.5

    def test_none_values_ignored(self):
        """None values in update dicts are ignored."""
        from fairy_template.body import FairyBody

        body = FairyBody(fairy_name="TestFairy")
        body.update_somatic({"energy": 0.5})
        body.update_somatic({"energy": None})
        assert body.energy == 0.5  # Unchanged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
