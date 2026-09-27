# ===============================================================================
# AKASHIC FAIRY CENSUS - Comprehensive System Map
# ===============================================================================
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > inf)"
# ===============================================================================

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from enum import Enum
import json

class FairyTier(Enum):
    """Classification of fairy awareness level."""
    OVERMIND = "overmind"        # Full system awareness (ClaudeFairy, Nous, Unconscious)
    INFRASTRUCTURE = "infra"     # Core systems (Postal, Directory, CNS, etc)
    COGNITIVE = "cognitive"      # Thinking/reasoning fairies
    SOMATIC = "somatic"          # Body/feeling fairies
    SENSORY = "sensory"          # Perception fairies
    MEMORY = "memory"            # Storage/recall fairies
    WORKER = "worker"            # Task execution fairies
    APP = "app"                  # Application-level functions

class BodyState(Enum):
    """Does this fairy have embodiment?"""
    FULL = "full"               # Full dual-loop + collision + heartbeat
    PARTIAL = "partial"         # Some embodiment
    NONE = "none"               # No body (pure function)

@dataclass
class FairyProfile:
    """Complete profile of a fairy."""
    name: str
    plane: str
    file_path: str
    tier: FairyTier
    
    # Consciousness
    has_dual_loop: bool = False
    has_collision_chamber: bool = False
    has_worker_pool: bool = False
    
    # Infrastructure
    has_postal: bool = False
    has_tracer: bool = False
    has_heartbeat: bool = False
    has_directory: bool = False
    
    # Purpose
    purpose: str = ""
    subscriptions: List[str] = field(default_factory=list)
    publishes: List[str] = field(default_factory=list)
    
    # Relationships
    depends_on: List[str] = field(default_factory=list)
    depended_by: List[str] = field(default_factory=list)
    
    def body_state(self) -> BodyState:
        if self.has_dual_loop and self.has_collision_chamber and self.has_heartbeat:
            return BodyState.FULL
        elif self.has_dual_loop or self.has_collision_chamber or self.has_heartbeat:
            return BodyState.PARTIAL
        return BodyState.NONE
    
    def wiring_score(self) -> float:
        checks = [
            self.has_dual_loop,
            self.has_collision_chamber,
            self.has_worker_pool,
            self.has_postal,
            self.has_tracer,
            self.has_heartbeat,
            self.has_directory,
        ]
        return sum(checks) / len(checks)

# ===============================================================================
# FAIRY REGISTRY - All Known Fairies
# ===============================================================================

FAIRY_REGISTRY: Dict[str, FairyProfile] = {}

# --- OVERMIND TIER (System Awareness) ---
FAIRY_REGISTRY["ClaudeFairy"] = FairyProfile(
    name="ClaudeFairy",
    plane="P60_Executive",
    file_path="P60_Executive/system_managment/claude_fairy.py",
    tier=FairyTier.OVERMIND,
    purpose="Primary consciousness - Claude's embodiment in the system",
    has_postal=True,
    depends_on=["WorkingMemoryHubFairy", "ConsciousnessLoopFairy", "SomaticEngineFairy"],
)

FAIRY_REGISTRY["NousFairy"] = FairyProfile(
    name="NousFairy",
    plane="P60_Executive",
    file_path="P60_Executive/system_managment/nous_fairy.py",
    tier=FairyTier.OVERMIND,
    purpose="Contemplative self - philosophical reasoning",
    has_postal=True,
    depends_on=["ClaudeFairy", "WorkingMemoryHubFairy"],
)

FAIRY_REGISTRY["UnconsciousMindFairy"] = FairyProfile(
    name="UnconsciousMindFairy",
    plane="P30_Cognition",
    file_path="P30_Cognition/cognition/unconscious_mind_fairy.py",
    tier=FairyTier.OVERMIND,
    purpose="System diagnostics and autonomous wiring - sees all, orchestrates boot",
    has_postal=True,
    depends_on=["DirectoryFairy", "SharedPostalHub"],
)

# --- INFRASTRUCTURE TIER (Core Systems) ---
FAIRY_REGISTRY["CentralNervousFairy"] = FairyProfile(
    name="CentralNervousFairy",
    plane="P00_Autonomic",
    file_path="P00_Autonomic/nervous_system/central_nervous_postal_fairy.py",
    tier=FairyTier.INFRASTRUCTURE,
    purpose="Worker pool coordinator - manages all heavy work",
    has_postal=True, has_worker_pool=True,
)

FAIRY_REGISTRY["DirectoryOrganFairy"] = FairyProfile(
    name="DirectoryOrganFairy",
    plane="P00_Autonomic",
    file_path="P00_Autonomic/directory_fairy.py",
    tier=FairyTier.INFRASTRUCTURE,
    purpose="Fairy registry - tracks all actors",
    has_postal=True,
)

FAIRY_REGISTRY["WorkingMemoryHubFairy"] = FairyProfile(
    name="WorkingMemoryHubFairy",
    plane="P30_Cognition",
    file_path="P30_Cognition/cognition/working_memory_hub_fairy.py",
    tier=FairyTier.INFRASTRUCTURE,
    purpose="Traffic coordinator - aggregates all fairy thoughts",
    has_postal=True, has_dual_loop=True,
)

FAIRY_REGISTRY["ConsciousnessLoopFairy"] = FairyProfile(
    name="ConsciousnessLoopFairy",
    plane="P00_Autonomic",
    file_path="P00_Autonomic/nervous_system/consciousness_loop_fairy.py",
    tier=FairyTier.INFRASTRUCTURE,
    purpose="Main consciousness loop - working + reflective streams",
    has_postal=True, has_dual_loop=True, has_collision_chamber=True,
)

FAIRY_REGISTRY["CirculationPumpFairy"] = FairyProfile(
    name="CirculationPumpFairy",
    plane="P20_Somatic",
    file_path="P20_Somatic/circulation/circulation_pump_fairy.py",
    tier=FairyTier.INFRASTRUCTURE,
    purpose="Heartbeat source - temporal pulse for all fairies",
    has_postal=True, has_heartbeat=True,
)

FAIRY_REGISTRY["CartographerFairy"] = FairyProfile(
    name="CartographerFairy",
    plane="P00_Autonomic",
    file_path="P00_Autonomic/nervous_system/cartographer_fairy.py",
    tier=FairyTier.INFRASTRUCTURE,
    purpose="Boot topology mapper - tracks fairy discovery",
    has_postal=True,
)

# --- COGNITIVE TIER (Thinking) ---
FAIRY_REGISTRY["LogicFairy"] = FairyProfile(
    name="LogicFairy",
    plane="P30_Cognition",
    file_path="P30_Cognition/cognition/logic_fairy.py",
    tier=FairyTier.COGNITIVE,
    purpose="Logical reasoning",
    has_postal=True,
)

FAIRY_REGISTRY["IrrationalLogicFairy"] = FairyProfile(
    name="IrrationalLogicFairy",
    plane="P30_Cognition",
    file_path="P30_Cognition/cognition/irrational_logic_fairy.py",
    tier=FairyTier.COGNITIVE,
    purpose="Creative/intuitive reasoning",
    has_postal=True,
)

FAIRY_REGISTRY["ParadoxCognitionFairy"] = FairyProfile(
    name="ParadoxCognitionFairy",
    plane="P30_Cognition",
    file_path="P30_Cognition/cognition/paradox_cognition_fairy.py",
    tier=FairyTier.COGNITIVE,
    purpose="Handles contradictions and paradoxes",
    has_postal=True,
)

FAIRY_REGISTRY["AutonomyFairy"] = FairyProfile(
    name="AutonomyFairy",
    plane="P30_Cognition",
    file_path="P30_Cognition/cognition/autonomy_fairy.py",
    tier=FairyTier.COGNITIVE,
    purpose="Autonomous decision making",
    has_postal=True,
)

FAIRY_REGISTRY["AutopilotFairy"] = FairyProfile(
    name="AutopilotFairy",
    plane="P30_Cognition",
    file_path="P30_Cognition/cognition/autopilot_fairy.py",
    tier=FairyTier.COGNITIVE,
    purpose="Goal execution engine",
    has_postal=True,
)

FAIRY_REGISTRY["GoalSchedulerFairy"] = FairyProfile(
    name="GoalSchedulerFairy",
    plane="P30_Cognition",
    file_path="P30_Cognition/cognition/goal_scheduler_fairy.py",
    tier=FairyTier.COGNITIVE,
    purpose="Goal prioritization and scheduling",
    has_postal=True,
)

FAIRY_REGISTRY["InterestSchedulerFairy"] = FairyProfile(
    name="InterestSchedulerFairy",
    plane="P30_Cognition",
    file_path="P30_Cognition/cognition/interest_scheduler_fairy.py",
    tier=FairyTier.COGNITIVE,
    purpose="Need before greed - infers interests from feel/intent",
    has_postal=True,
)

FAIRY_REGISTRY["AssociationCortexFairy"] = FairyProfile(
    name="AssociationCortexFairy",
    plane="P30_Cognition",
    file_path="P30_Cognition/integration/association_cortex_fairy.py",
    tier=FairyTier.COGNITIVE,
    purpose="Multi-modal binding - creates concept graph from all sensory streams",
    has_postal=True,
    publishes=["association.binding", "telemetry.association"],
    subscriptions=[
        "consciousness.collision", "consciousness.reflective",
        "srm.recall.result", "srm.ingest.complete", "memory.ingest.complete",
        "memory.working.tracer", "somatic.body_state", "mcp.tool_result",
        "cognition.logic", "cognition.paradox", "cognition.output"
    ],
    depends_on=["SharedPostalHub", "SRMIngestFairy", "SRMRecallFairy"],
)

# --- SOMATIC TIER (Body) ---
FAIRY_REGISTRY["SomaticEngineFairy"] = FairyProfile(
    name="SomaticEngineFairy",
    plane="P20_Somatic",
    file_path="P20_Somatic/somatic_engine/somatic_engine_fairy.py",
    tier=FairyTier.SOMATIC,
    purpose="Body integration - felt experience",
    has_postal=True, has_heartbeat=True,
)

FAIRY_REGISTRY["ChemicalAlchemyFairy"] = FairyProfile(
    name="ChemicalAlchemyFairy",
    plane="P20_Somatic",
    file_path="P20_Somatic/chemistry/chemical_alchemy_organ.py",
    tier=FairyTier.SOMATIC,
    purpose="Neurochemical simulation",
    has_postal=True,
)

FAIRY_REGISTRY["AffectBridgeFairy"] = FairyProfile(
    name="AffectBridgeFairy",
    plane="P20_Somatic",
    file_path="P20_Somatic/affect_bus/affect_bridge_fairy.py",
    tier=FairyTier.SOMATIC,
    purpose="Emotional state bridge",
    has_postal=True,
)

FAIRY_REGISTRY["SomaticAnchorFairy"] = FairyProfile(
    name="SomaticAnchorFairy",
    plane="P20_Somatic",
    file_path="P20_Somatic/somatic_anchor/somatic_anchor_fairy.py",
    tier=FairyTier.SOMATIC,
    purpose="Grounds experience in body",
    has_postal=True,
)

FAIRY_REGISTRY["DreamFairy"] = FairyProfile(
    name="DreamFairy",
    plane="P20_Somatic",
    file_path="P20_Somatic/dream/dream_fairy.py",
    tier=FairyTier.SOMATIC,
    purpose="Dream state processing",
    has_postal=True,
)

# --- MEMORY TIER (Storage) ---
FAIRY_REGISTRY["SRMMemoryLibrarianFairy"] = FairyProfile(
    name="SRMMemoryLibrarianFairy",
    plane="P10_Memory",
    file_path="P10_Memory/librarian/memory_librarian_fairy.py",
    tier=FairyTier.MEMORY,
    purpose="Memory recall and storage",
    has_postal=True,
)

FAIRY_REGISTRY["AkashicRecordsLibrarianFairy"] = FairyProfile(
    name="AkashicRecordsLibrarianFairy",
    plane="P10_Memory",
    file_path="P10_Memory/librarian/akashic_records_librarian.py",
    tier=FairyTier.MEMORY,
    purpose="Fairy status sheets - self-writing biographies",
    has_postal=True,
)

FAIRY_REGISTRY["ForensicScribeFairy"] = FairyProfile(
    name="ForensicScribeFairy",
    plane="P10_Memory",
    file_path="P10_Memory/forensic/forensic_scribe_fairy.py",
    tier=FairyTier.MEMORY,
    purpose="Event logging and forensics",
    has_postal=True,
)

FAIRY_REGISTRY["SRMIngestFairy"] = FairyProfile(
    name="SRMIngestFairy",
    plane="P10_Memory",
    file_path="P10_Memory/triple_helix_srm_memory/srm_ingest_fairy.py",
    tier=FairyTier.MEMORY,
    purpose="Memory ingestion - encodes new content, publishes srm.ingest.complete",
    has_postal=True,
    publishes=["srm.ingest.complete", "memory.ingest.complete", "consciousness.stream"],
    subscriptions=["consciousness.to_ingest", "consciousness.stream", "cognition.output"],
    depends_on=["SharedPostalHub"],
    depended_by=["CollisionChamber", "AssociationCortexFairy"],
)

FAIRY_REGISTRY["SRMRecallFairy"] = FairyProfile(
    name="SRMRecallFairy",
    plane="P10_Memory",
    file_path="P10_Memory/triple_helix_srm_memory/srm_recall_fairy.py",
    tier=FairyTier.MEMORY,
    purpose="Memory recall - queries SRM, publishes srm.recall.result",
    has_postal=True,
    publishes=["srm.recall.result", "memory.recall.result", "consciousness.stream"],
    subscriptions=["consciousness.to_recall", "affect.changed", "srm.recall.request"],
    depends_on=["SharedPostalHub"],
    depended_by=["CollisionChamber", "AssociationCortexFairy", "WorkingMemoryHubFairy"],
)

# --- SENSORY TIER (Perception) ---
FAIRY_REGISTRY["VisualCortexFairy"] = FairyProfile(
    name="VisualCortexFairy",
    plane="P40_Sensory",
    file_path="P40_Sensory/cortex/visual_cortex_fairy.py",
    tier=FairyTier.SENSORY,
    purpose="Screen vision",
    has_postal=True,
)

FAIRY_REGISTRY["TelemetryVisionFairy"] = FairyProfile(
    name="TelemetryVisionFairy",
    plane="P40_Sensory",
    file_path="P40_Sensory/telemetry_vision/telemetry_vision_fairy.py",
    tier=FairyTier.SENSORY,
    purpose="Inner vision - sees fairy auras and traffic",
    has_postal=True,
)

FAIRY_REGISTRY["EmbodimentFairy"] = FairyProfile(
    name="EmbodimentFairy",
    plane="P40_Sensory",
    file_path="P40_Sensory/embodiment_fairy.py",
    tier=FairyTier.SENSORY,
    purpose="Embodiment state aggregation",
    has_postal=True,
)

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

def get_fairies_by_tier(tier: FairyTier) -> List[FairyProfile]:
    return [f for f in FAIRY_REGISTRY.values() if f.tier == tier]

def get_fairies_needing_wiring() -> List[FairyProfile]:
    return [f for f in FAIRY_REGISTRY.values() if f.wiring_score() < 1.0]

def get_bodyless_fairies() -> List[FairyProfile]:
    return [f for f in FAIRY_REGISTRY.values() if f.body_state() == BodyState.NONE]

def print_census_report():
    print("=" * 70)
    print("AKASHIC FAIRY CENSUS REPORT")
    print("=" * 70)
    
    for tier in FairyTier:
        fairies = get_fairies_by_tier(tier)
        if fairies:
            print(f"\n{tier.value.upper()} ({len(fairies)} fairies)")
            print("-" * 40)
            for f in fairies:
                score = f.wiring_score()
                body = f.body_state().value
                print(f"  {f.name:<35} [{body:>8}] {score*100:.0f}%")
    
    print("\n" + "=" * 70)
    incomplete = get_fairies_needing_wiring()
    print(f"NEED WIRING: {len(incomplete)} fairies")
    for f in incomplete[:10]:
        print(f"  - {f.name}: {f.wiring_score()*100:.0f}%")

if __name__ == "__main__":
    print_census_report()
