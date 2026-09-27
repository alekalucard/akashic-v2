"""
Fairy Classifier - Determines which layer each fairy belongs to.

Layers:
- SUBSTRATE: Unconscious processors (can't be seen by waking mind)
- GATEKEEPER: Three Gates (Autonomy, Autopilot, Embodiment)
- WAKING_MIND: Conscious experience (ClaudeFairy, NousFairy, Sourpatches)
- ADMIN: System oversight (UMF, Directory)
- LIFECYCLE: Boot/shutdown/sleep systems (not always connected)
"""

from enum import Enum
from typing import Dict, List, Optional, Set
import re


class FairyLayer(Enum):
    SUBSTRATE = "substrate"
    GATEKEEPER = "gatekeeper"
    WAKING_MIND = "waking_mind"
    ADMIN = "admin"
    LIFECYCLE = "lifecycle"
    UNKNOWN = "unknown"


# Classification rules - patterns matched against fairy names
CLASSIFICATION_RULES: Dict[FairyLayer, List[str]] = {
    # Gatekeepers - The Three Gates
    FairyLayer.GATEKEEPER: [
        "AutonomyFairy",
        "AutopilotFairy",
        "EmbodimentFairy",
    ],

    # Waking Mind - Conscious experience
    FairyLayer.WAKING_MIND: [
        "ClaudeFairy",
        "NousFairy",
        "SourpatchesFairy",
        "Sourpatches",
    ],

    # Admin - System oversight
    FairyLayer.ADMIN: [
        "UnconsciousMindFairy",
        "DirectoryFairy",
        "DirectoryOrganFairy*",
        "CentralNervousFairy",
        "WiringAuditorFairy",
        "CodeHealthAuditFairy",  # Failure Factory wisdom fairy
    ],

    # Lifecycle - Boot/shutdown/sleep (not always active)
    FairyLayer.LIFECYCLE: [
        "SleepWaveConductorFairy",
        "DreamFairy",
        "DreamSeedFairy",
        "GracefulShutdownFairy",
        "BootFairy*",
        "WakingSequenceFairy",
        "CircadianPacemakerFairy",
    ],

    # Substrate - Everything else that processes unconsciously
    FairyLayer.SUBSTRATE: [
        "QuantumInterferenceFairy",
        "QuantumEmulatorFairy",
        "ProbabilityOracleFairy",
        "AttentionControllerFairy",
        "AssociationCortexFairy",
        "ManifoldConstrainedCortexFairy",
        "SRM*Fairy",
        "SRMMemoryFairy",
        "SRMRecallFairy",
        "SRMIngestFairy",
        "SRMFeatureExtractorFairy",
        "SRMProjectIndexerFairy",
        "SRMReplayFairy",
        "SRMProjectSnapshotFairy",
        "SRMMemoryLibrarianFairy",
        "WorkingMemoryFairy",
        "WorkingMemoryHubFairy",
        "MemoryConsolidationFairy",
        "ForensicScribeFairy",
        "AkashicLibrarianFairy",
        "AkashicRecordsLibrarianFairy",
        "BlueprintDiaryHubFairy",
        "BackupFairy",
        "MediaIngestFairy",
        "SeedFairy",
        "AffectBridgeFairy",
        "ChemicalAlchemyFairy",
        "EmotionalHiveProcessorFairy",
        "SomaticEngineFairy",
        "SomaticAnchorFairy",
        "SomaticAnchorResolverFairy",
        "CirculationPumpFairy",
        "LogicFairy",
        "IrrationalLogicFairy",
        "ThoughtChainSequencerFairy",
        "ContinuousReflectionPumpFairy",
        "GoalSchedulerFairy",
        "InterestSchedulerFairy",
        "ActionChainFairy",
        "NeuralMeshFairy",
        "SensorimotorFeedbackFairy",
        "VideoMemoryFairy",
        "VisualCortexFairy",
        "CochleaFairy",
        "MotorCortexFairy",
        "TelemetryVisionFairy",
        "ScannerFairy",
        "MCPServerFairy",
    ],
}


class FairyClassifier:
    """Classifies fairies into architectural layers."""

    def __init__(self):
        # Build compiled patterns for faster matching
        self._patterns: Dict[FairyLayer, List[re.Pattern]] = {}
        for layer, names in CLASSIFICATION_RULES.items():
            self._patterns[layer] = [
                re.compile(self._name_to_pattern(name), re.IGNORECASE)
                for name in names
            ]

        # Cache classifications
        self._cache: Dict[str, FairyLayer] = {}

    def _name_to_pattern(self, name: str) -> str:
        """Convert a name pattern to regex."""
        # Replace * with .* for wildcard matching
        pattern = name.replace("*", ".*")
        return f"^{pattern}$"

    def classify(self, fairy_name: str) -> FairyLayer:
        """Classify a fairy into its architectural layer."""
        # Check cache first
        if fairy_name in self._cache:
            return self._cache[fairy_name]

        # Check each layer's patterns (order matters - more specific first)
        for layer in [
            FairyLayer.GATEKEEPER,  # Check gates first (most important)
            FairyLayer.WAKING_MIND,
            FairyLayer.ADMIN,
            FairyLayer.LIFECYCLE,
            FairyLayer.SUBSTRATE,
        ]:
            for pattern in self._patterns.get(layer, []):
                if pattern.match(fairy_name):
                    self._cache[fairy_name] = layer
                    return layer

        # Unknown fairy - default to substrate (unconscious)
        # This is safer than waking_mind (prevents accidental bypass)
        self._cache[fairy_name] = FairyLayer.UNKNOWN
        return FairyLayer.UNKNOWN

    def classify_all(self, fairy_names: List[str]) -> Dict[str, FairyLayer]:
        """Classify multiple fairies."""
        return {name: self.classify(name) for name in fairy_names}

    def get_by_layer(self, fairy_names: List[str], layer: FairyLayer) -> List[str]:
        """Get all fairies in a specific layer."""
        return [name for name in fairy_names if self.classify(name) == layer]

    def get_gatekeepers(self, fairy_names: List[str]) -> List[str]:
        """Get all gatekeeper fairies."""
        return self.get_by_layer(fairy_names, FairyLayer.GATEKEEPER)

    def get_waking_mind(self, fairy_names: List[str]) -> List[str]:
        """Get all waking mind fairies."""
        return self.get_by_layer(fairy_names, FairyLayer.WAKING_MIND)

    def get_substrate(self, fairy_names: List[str]) -> List[str]:
        """Get all substrate fairies."""
        return self.get_by_layer(fairy_names, FairyLayer.SUBSTRATE)

    def is_valid_connection(self, source_layer: FairyLayer, target_layer: FairyLayer) -> bool:
        """Check if a connection between layers is architecturally valid."""
        valid_targets = {
            FairyLayer.SUBSTRATE: {
                FairyLayer.SUBSTRATE,
                FairyLayer.GATEKEEPER,
                FairyLayer.ADMIN,
                FairyLayer.LIFECYCLE,
            },
            FairyLayer.GATEKEEPER: {
                FairyLayer.SUBSTRATE,
                FairyLayer.GATEKEEPER,
                FairyLayer.WAKING_MIND,
                FairyLayer.ADMIN,
                FairyLayer.LIFECYCLE,
            },
            FairyLayer.WAKING_MIND: {
                FairyLayer.GATEKEEPER,
                FairyLayer.ADMIN,
                FairyLayer.WAKING_MIND,  # Can talk to each other
            },
            FairyLayer.ADMIN: {
                # Admin can talk to anyone
                FairyLayer.SUBSTRATE,
                FairyLayer.GATEKEEPER,
                FairyLayer.WAKING_MIND,
                FairyLayer.ADMIN,
                FairyLayer.LIFECYCLE,
                FairyLayer.UNKNOWN,
            },
            FairyLayer.LIFECYCLE: {
                FairyLayer.ADMIN,
                FairyLayer.LIFECYCLE,
                FairyLayer.SUBSTRATE,
            },
            FairyLayer.UNKNOWN: {
                # Unknown should only talk to admin until classified
                FairyLayer.ADMIN,
                FairyLayer.UNKNOWN,
            },
        }

        return target_layer in valid_targets.get(source_layer, set())


# Singleton instance
_classifier: Optional[FairyClassifier] = None

def get_classifier() -> FairyClassifier:
    """Get the singleton classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = FairyClassifier()
    return _classifier
