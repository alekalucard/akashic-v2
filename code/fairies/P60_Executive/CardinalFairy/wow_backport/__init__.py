"""
Cardinal WoW Backport System
============================

A comprehensive system for analyzing and backporting WoW retail features
to AzerothCore 3.3.5a using Cardinal (Mistral via Ollama).

Modules:
- spell_analyzer: Parse and compare spell data between versions
- knowledge_manager: Interface with SRM for persistent learning
- backport_generator: Generate Eluna Lua, SQL, and DBC code

Designed to run on the Alienware node at 192.168.1.24.
"""

from .spell_analyzer import SpellAnalyzer, SpellData, SpellEffect, VersionComparison
from .knowledge_manager import KnowledgeManager, KnowledgeCategory
from .backport_generator import BackportGenerator, BackportResult

__all__ = [
    "SpellAnalyzer",
    "SpellData",
    "SpellEffect",
    "VersionComparison",
    "KnowledgeManager",
    "KnowledgeCategory",
    "BackportGenerator",
    "BackportResult",
]
