"""
Waking Minds - Conscious reasoning layer for Akashic v2.

Waking minds are the conscious reasoning entities that:
1. Process incoming requests through full Claude reasoning
2. Capture reasoning traces for the unconscious to learn from
3. Bridge API-level reasoning to local learning
4. Teach the unconscious mind by example

Architecture:
- UnconsciousMindFairy: The substrate (brain infrastructure)
- WakingMind: The conscious reasoning layer (rides on the substrate)
- The unconscious learns by observing the waking mind think

Available waking minds:
- NousFairy: "The Divine Intellect" - bridges Claude reasoning to local learning

Usage:
    from waking_minds import NousFairy, ReasoningTrace

    nous = NousFairy(umf=my_umf)
    nous.boot()

    # Start a reasoning session
    trace = nous.begin_reasoning("User asked about file handling", "chat")
    nous.record_thought("I should search for file utilities first")
    nous.record_tool_use("grep", {"pattern": "file"}, results)
    nous.complete_reasoning("Found file handling patterns", success=True)
    # The reasoning trace is automatically fed to the unconscious
"""

from .nous_fairy import (
    NousFairy,
    ReasoningTrace,
    ReasoningType,
    create_nous_fairy,
)

__all__ = [
    "NousFairy",
    "ReasoningTrace",
    "ReasoningType",
    "create_nous_fairy",
]
