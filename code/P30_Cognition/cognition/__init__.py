# Cognition module for akashic_v2
"""
P30_Cognition - Cognitive processing fairies.

This module contains the cognition fairies that provide:
- Logical analysis and paradox detection (LogicFairy)
- Intuitive/irrational processing (IrrationalLogicFairy)
- Paradox synthesis (ParadoxCognitionFairy)
- NousFairy access (divine intellect, reasoning traces)
- WorkingMemoryHub access (limited capacity workspace)
- DynamicThinkingOrchestrator (autonomous thought generation)

The fairies work as an ensemble, each providing a unique perspective
on incoming thoughts. They wire into the consciousness stream and
emit to cognition.output for downstream processing.

Chain: Logic -> IrrationalLogic -> Paradox -> Claude

FIX 2026-02-02: This shim re-exports from fairies.P30_Cognition.cognition
so imports like 'from P30_Cognition.cognition.thought_chain_engine import ...'
work correctly.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# RE-EXPORT FROM fairies.P30_Cognition.cognition (canonical location)
# ═══════════════════════════════════════════════════════════════════════════════
# First try to import everything from the canonical fairies location
try:
    from fairies.P30_Cognition.cognition import *
    from fairies.P30_Cognition.cognition import __all__ as _fairy_cognition_all
    _HAS_FAIRY_COGNITION = True
except ImportError:
    _fairy_cognition_all = []
    _HAS_FAIRY_COGNITION = False

# ═══════════════════════════════════════════════════════════════════════════════
# LOCAL IMPORTS (fallback for anything not in fairies/)
# ═══════════════════════════════════════════════════════════════════════════════
from .prompt_aware_mixin import PromptAwareMixin
from .logic_fairy import LogicFairy
from .irrational_logic_fairy import IrrationalLogicFairy
from .paradox_cognition_fairy import ParadoxCognitionFairy
from .nous_fairy import get_nous_fairy, set_nous_fairy, NousFairy
from .working_memory_hub_fairy import (
    WorkingMemoryHubFairy,
    WorkingMemoryHubStub,  # Legacy alias for backward compatibility
    get_working_memory_hub,
    set_working_memory_hub,
)
from .dynamic_thinking_orchestrator import (
    DynamicThinkingOrchestrator,
    get_dynamic_thinking_orchestrator,
    start_dynamic_thinking,
    create_dynamic_thinking_for_fairy,
)

__all__ = [
    "PromptAwareMixin",
    "LogicFairy",
    "IrrationalLogicFairy",
    "ParadoxCognitionFairy",
    "get_nous_fairy",
    "set_nous_fairy",
    "NousFairy",
    # Working Memory Hub (real implementation)
    "WorkingMemoryHubFairy",
    "WorkingMemoryHubStub",  # Legacy alias
    "get_working_memory_hub",
    "set_working_memory_hub",
    # Dynamic Thinking
    "DynamicThinkingOrchestrator",
    "get_dynamic_thinking_orchestrator",
    "start_dynamic_thinking",
    "create_dynamic_thinking_for_fairy",
]
