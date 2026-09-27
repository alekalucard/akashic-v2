"""
Test that helix coordinates are passed to cortex during ingest.
This is the critical integration point that was missing!
"""
import sys
from pathlib import Path

# Add both path styles needed
ROOT = Path(__file__).parent.parent.parent.parent
FAIRIES = ROOT / "fairies"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FAIRIES))

from unittest.mock import MagicMock, patch


def test_ingest_passes_helix_to_cortex():
    """ingest_to_helix should pass helix_coord to cortex._intent_bind."""

    # Import the class fresh
    from fairies.P10_Memory.triple_helix_srm_memory.helix_integration_wiring import HelixIntegrationWiring

    # Create wiring instance with mocked dependencies
    wiring = HelixIntegrationWiring()

    # Mock the cortex
    mock_cortex = MagicMock()
    mock_cortex._intent_bind = MagicMock()
    wiring._cortex = mock_cortex

    # Mock the coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.create_card = MagicMock(return_value="card-123")
    wiring._coordinator = mock_coordinator

    # Call ingest_to_helix - this should create a real HelixCoordinate
    # and pass it to the cortex
    wiring.ingest_to_helix(
        content="test content about neural networks",
        owner_mind="nous",
        keywords=["neural", "networks"],
        affect_state={"DOP": 0.7, "SER": 0.6},
    )

    # Verify cortex._intent_bind was called
    mock_cortex._intent_bind.assert_called_once()

    # Get the call arguments
    call_args = mock_cortex._intent_bind.call_args[0][0]

    # THE KEY ASSERTION: helix_coord must be present!
    assert "helix_coord" in call_args, (
        f"Should pass helix_coord to cortex!\n"
        f"Got keys: {list(call_args.keys())}\n"
        f"Full call_args: {call_args}"
    )

    # Verify the structure of helix_coord
    helix_coord = call_args["helix_coord"]
    assert helix_coord is not None, "helix_coord should not be None"
    assert "affect" in helix_coord, f"helix_coord should have 'affect': {helix_coord}"
    assert "semantic" in helix_coord, f"helix_coord should have 'semantic': {helix_coord}"
    assert "temporal" in helix_coord, f"helix_coord should have 'temporal': {helix_coord}"

    # Verify affect has proper structure
    affect = helix_coord["affect"]
    assert "domain" in affect, f"affect should have 'domain': {affect}"
    assert "intensity" in affect, f"affect should have 'intensity': {affect}"

    # Verify semantic has proper structure
    semantic = helix_coord["semantic"]
    assert "domain" in semantic, f"semantic should have 'domain': {semantic}"
    assert "specificity" in semantic, f"semantic should have 'specificity': {semantic}"

    # Verify temporal has proper structure
    temporal = helix_coord["temporal"]
    assert "scale" in temporal, f"temporal should have 'scale': {temporal}"
    assert "position" in temporal, f"temporal should have 'position': {temporal}"

    print(f"SUCCESS! helix_coord passed to cortex: {helix_coord}")


if __name__ == "__main__":
    test_ingest_passes_helix_to_cortex()
    print("\nAll tests passed!")
