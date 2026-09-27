"""
Somatic Mind Fairy - The embodied felt-sense controller.

RENAMED from UnconsciousMindFairy (2026-02-03)
Now lives in P20_Somatic where it belongs - the felt body plane.

The first fairy to wake. Orchestrates boot, monitors system health,
mentors child fairies, and thinks autonomously.

Usage:
    from fairies.P20_Somatic.SomaticMindFairy import SomaticMindFairy, create_somatic_mind

    fairy = SomaticMindFairy(fabric)
    fairy.boot()
    fairy.start_boot_sequence()
"""

from .fairy import (
    # New names (preferred)
    SomaticMindFairy,
    create_somatic_mind,
    get_somatic_mind,
    set_somatic_mind,
    # Backward compatibility aliases (deprecated)
    create_unconscious_mind,
    get_umf,
    get_unconscious_mind,
    get_unconscious_mind_fairy,
    set_umf_instance,
)
from .mixins import DiagnosticMixin, MentorMixin, ProfileMixin, ChildState, FairyProfile, CardinalMixin
from .mixins.cardinal import CardinalMode, Observation, FairySnapshot, ProposedFix
from .drives import PainSystem, PainDrive, SkillTracker, Skill
from .boot import BootOrchestrator
from .timing import (
    CircadianClock,
    fib_decay,
    golden_split,
    golden_weights,
    allocate_attention,
    fib_intervals,
    should_act_at_count,
    PHI,
)
from .interest_generator import (
    InterestGenerator,
    Interest,
    InterestType,
    create_interest_generator,
)
from .admin_tasks import (
    AdminTaskQueue,
    AdminTask,
    TaskPriority,
    TaskCategory,
    create_admin_task_queue,
)
from .thought_chains import (
    ThoughtChainEngine,
    ThoughtChain,
    ChainedThought,
    ChainType,
    create_thought_chain_engine,
)

# Backward compatibility alias
UnconsciousMindFairy = SomaticMindFairy

__all__ = [
    # Main class (new name)
    "SomaticMindFairy",
    "create_somatic_mind",
    "get_somatic_mind",
    "set_somatic_mind",
    # Backward compatibility (deprecated - will be removed)
    "UnconsciousMindFairy",
    "create_unconscious_mind",
    "get_umf",
    "get_unconscious_mind",
    "get_unconscious_mind_fairy",
    "set_umf_instance",
    # Mixins
    "DiagnosticMixin",
    "MentorMixin",
    "ProfileMixin",
    "ChildState",
    "FairyProfile",
    "CardinalMixin",
    # Cardinal types
    "CardinalMode",
    "Observation",
    "FairySnapshot",
    "ProposedFix",
    # Drives
    "PainSystem",
    "PainDrive",
    "SkillTracker",
    "Skill",
    # Boot
    "BootOrchestrator",
    # Timing / Circadian
    "CircadianClock",
    "fib_decay",
    "golden_split",
    "golden_weights",
    "allocate_attention",
    "fib_intervals",
    "should_act_at_count",
    "PHI",
    # Interest Generator
    "InterestGenerator",
    "Interest",
    "InterestType",
    "create_interest_generator",
    # Admin Task Queue
    "AdminTaskQueue",
    "AdminTask",
    "TaskPriority",
    "TaskCategory",
    "create_admin_task_queue",
    # Thought Chains
    "ThoughtChainEngine",
    "ThoughtChain",
    "ChainedThought",
    "ChainType",
    "create_thought_chain_engine",
]
