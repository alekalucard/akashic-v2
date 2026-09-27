"""
Forensic Module - Session tracking and institutional memory.

This module provides the ForensicSessionFairy which watches debugging
sessions and maintains knowledge that survives context compaction.
"""

from .forensic_session_fairy import (
    ForensicSessionFairy,
    get_forensic_fairy,
    # Convenience API
    start_session,
    tried,
    learned,
    question,
    next_step,
    end_session,
    context,
    what_tried,
    what_learned,
)

__all__ = [
    "ForensicSessionFairy",
    "get_forensic_fairy",
    "start_session",
    "tried",
    "learned",
    "question",
    "next_step",
    "end_session",
    "context",
    "what_tried",
    "what_learned",
]
