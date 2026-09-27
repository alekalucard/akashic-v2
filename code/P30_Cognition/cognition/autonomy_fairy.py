"""Autonomy Fairy - Compatibility stub for akashic_v2"""


class AutonomyFairyStub:
    """Stub autonomy fairy for compatibility."""

    def get_status(self):
        return {"status": "v2_stub"}

    def on_motion(self, magnitude: float):
        """Handle motion callback."""
        pass


_fairy = None


def get_autonomy_fairy():
    """Get the autonomy fairy singleton."""
    global _fairy
    if _fairy is None:
        _fairy = AutonomyFairyStub()
    return _fairy
