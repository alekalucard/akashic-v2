"""
Memory Consolidation Module

Provides automated memory organization:
- Consolidates scattered SRM_Intake folders into Triple Helix storage
- Processes diary JSONL files into relational clusters per fairy
- Builds search indices for efficient long-term recall
- Supports multi-worker fairy structures

Usage:
    # As CLI
    python -m P10_Memory.consolidation.memory_consolidator_fairy --help

    # As module
    from fairies.P10_Memory.consolidation import MemoryConsolidatorFairy
    consolidator = MemoryConsolidatorFairy()
    consolidator.consolidate_all()
"""

from .memory_consolidator_fairy import (
    MemoryConsolidatorFairy,
    TripleHelixStorage,
    DiaryProcessor,
    IndexBuilder,
    ConsolidationConfig,
)

__all__ = [
    "MemoryConsolidatorFairy",
    "TripleHelixStorage",
    "DiaryProcessor",
    "IndexBuilder",
    "ConsolidationConfig",
]
