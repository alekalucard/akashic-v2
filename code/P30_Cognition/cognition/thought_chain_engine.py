# Shim: Forwards to canonical location at fairies.P30_Cognition.cognition.thought_chain_engine
"""
FIX 2026-02-02: This shim allows 'from P30_Cognition.cognition.thought_chain_engine import ...'
to work even though the real file is at fairies/P30_Cognition/cognition/thought_chain_engine.py
"""
from fairies.P30_Cognition.cognition.thought_chain_engine import *
from fairies.P30_Cognition.cognition.thought_chain_engine import (
    ThoughtChainEngine,
    get_thought_chain_engine,
    start_thought_chain_engine,
    create_thought_chain_engine,
    ThoughtType,
    ChainType,
    ChainState,
)
