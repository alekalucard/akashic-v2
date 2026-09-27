#!/usr/bin/env python3
"""
Cardinal WoW Backport System - CLI Interface
=============================================

Main entry point for the Cardinal WoW backporting system.
Provides commands for:
- Analyzing spells
- Generating backport code
- Managing learned knowledge
- Batch processing

Usage:
    python cardinal_backport_cli.py analyze 116        # Analyze spell ID 116
    python cardinal_backport_cli.py backport 116      # Generate backport for spell 116
    python cardinal_backport_cli.py search "frostbolt" # Search spells by name
    python cardinal_backport_cli.py learn             # Show learned patterns
    python cardinal_backport_cli.py stats             # Show knowledge stats

Designed to run on Alienware at 192.168.1.24 alongside the WoW server.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

# Add parent paths for imports
ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P60_Executive.CardinalFairy.wow_backport.spell_analyzer import (
    SpellAnalyzer,
    VersionComparison,
)
from fairies.P60_Executive.CardinalFairy.wow_backport.knowledge_manager import (
    KnowledgeManager,
    KnowledgeCategory,
)
from fairies.P60_Executive.CardinalFairy.wow_backport.backport_generator import (
    BackportGenerator,
    BackportResult,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default paths - adjust for Alienware deployment
DEFAULT_DBC_PATH = Path("C:/AzerothCore/data/dbc")
DEFAULT_OUTPUT_PATH = Path("C:/Akashic_Cardinal_Sandbox/backports")
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "mistral"


# =============================================================================
# CLI COMMANDS
# =============================================================================

async def cmd_analyze(args):
    """Analyze a spell for backportability."""
    print(f"=== Cardinal Spell Analysis ===")
    print(f"Spell ID: {args.spell_id}")
    print()

    analyzer = SpellAnalyzer(
        dbc_path=args.dbc_path,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
    )

    # Load DBC if path provided
    if args.dbc_path and args.dbc_path.exists():
        print("Loading 3.3.5a DBC files...")
        if analyzer.load_dbc():
            print(f"  Loaded {len(analyzer.wotlk_spells)} spells from Spell.dbc")
        else:
            print("  Warning: Could not load DBC files")
    print()

    print("Analyzing spell...")
    comparison = await analyzer.compare_spell(args.spell_id)

    # Display results
    print()
    print(f"Spell Name: {comparison.spell_name}")
    print(f"Exists in 3.3.5a: {'Yes' if comparison.exists_in_wotlk else 'No'}")
    print(f"Can Backport: {'Yes' if comparison.can_backport else 'No'}")
    print(f"Difficulty: {comparison.backport_difficulty}")
    print()

    if comparison.retail_data:
        print("Retail Data:")
        print(f"  Effects: {len(comparison.retail_data.effects)}")
        for eff in comparison.retail_data.effects:
            print(f"    - Effect {eff.index}: {eff.effect_type_name or f'Type {eff.effect_type}'}")

    if comparison.missing_mechanics:
        print()
        print("Missing Mechanics (cannot replicate):")
        for mech in comparison.missing_mechanics:
            print(f"  - {mech}")

    if comparison.engine_limitations:
        print()
        print("Engine Limitations Hit:")
        for lim in comparison.engine_limitations:
            print(f"  - {lim}")

    if comparison.suggested_workarounds:
        print()
        print("Suggested Workarounds:")
        for wa in comparison.suggested_workarounds:
            print(f"  - {wa}")

    # Save to knowledge base
    km = KnowledgeManager()
    if comparison.retail_data:
        km.store_spell_knowledge(
            spell_id=args.spell_id,
            name=comparison.spell_name,
            version="retail",
            data=comparison.retail_data.to_dict(),
            analysis={
                "can_backport": comparison.can_backport,
                "backport_difficulty": comparison.backport_difficulty,
                "missing_mechanics": comparison.missing_mechanics,
            },
        )
        print()
        print("Knowledge saved to SRM.")

    return comparison


async def cmd_backport(args):
    """Generate backport code for a spell."""
    print(f"=== Cardinal Backport Generator ===")
    print(f"Spell ID: {args.spell_id}")
    print()

    # First analyze
    analyzer = SpellAnalyzer(
        dbc_path=args.dbc_path,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
    )

    if args.dbc_path and args.dbc_path.exists():
        analyzer.load_dbc()

    print("Analyzing spell...")
    comparison = await analyzer.compare_spell(args.spell_id)
    print(f"  Can backport: {comparison.can_backport}")
    print(f"  Difficulty: {comparison.backport_difficulty}")
    print()

    if not comparison.can_backport and comparison.backport_difficulty == "impossible":
        print("ERROR: This spell cannot be backported.")
        print("Reasons:")
        for lim in comparison.engine_limitations:
            print(f"  - {lim}")
        return None

    # Generate backport
    km = KnowledgeManager()
    generator = BackportGenerator(
        knowledge_manager=km,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
        output_path=args.output_path,
    )

    options = {
        "include_npc": args.include_npc,
    }
    if args.custom_id:
        options["custom_spell_id"] = args.custom_id

    print("Generating backport code...")
    result = await generator.generate_backport(comparison, options)

    print()
    print(f"Status: {result.status.upper()}")
    print(f"Generated {len(result.eluna_scripts)} Lua script(s)")
    print(f"Generated {len(result.sql_entries)} SQL file(s)")
    print(f"DBC instructions: {len(result.dbc_instructions)}")

    if result.patterns_used:
        print()
        print("Patterns Used:")
        for p in result.patterns_used:
            print(f"  - {p}")

    if result.warnings:
        print()
        print("Warnings:")
        for w in result.warnings:
            print(f"  - {w}")

    # Output location
    spell_dir = args.output_path / f"spell_{result.spell_id}_{result.spell_name.lower().replace(' ', '_')}"
    print()
    print(f"Output saved to: {spell_dir}")

    return result


async def cmd_search(args):
    """Search for spells by name."""
    print(f"=== Cardinal Spell Search ===")
    print(f"Query: {args.query}")
    print()

    km = KnowledgeManager()

    # Search knowledge base first
    print("Searching knowledge base...")
    results = km.find_similar_spells(args.query)

    if results:
        print(f"Found {len(results)} result(s) in knowledge base:")
        for entry in results:
            print(f"  - {entry.name} (confidence: {entry.confidence:.1f})")
    else:
        print("No results in knowledge base.")

    # Search Wowhead
    if args.online:
        print()
        print("Searching Wowhead...")
        analyzer = SpellAnalyzer()
        wowhead_results = await analyzer.wowhead.search_spells(args.query, args.version)
        if wowhead_results:
            print(f"Found {len(wowhead_results)} result(s) on Wowhead:")
            for r in wowhead_results[:10]:
                print(f"  - Spell ID: {r['id']}")
        else:
            print("No results on Wowhead.")


async def cmd_learn(args):
    """Show learned patterns."""
    print("=== Cardinal Learned Patterns ===")
    print()

    km = KnowledgeManager()
    patterns = km.srm.get_patterns()

    if not patterns:
        print("No patterns learned yet.")
        print()
        print("Patterns are learned automatically when backports succeed.")
        print("Run 'backport' commands to build the pattern library.")
        return

    print(f"Total patterns: {len(patterns)}")
    print()

    for pattern in patterns:
        print(f"Pattern: {pattern.name}")
        print(f"  Mechanic: {pattern.retail_mechanic} -> {pattern.wotlk_equivalent}")
        print(f"  Type: {pattern.implementation_type}")
        print(f"  Success/Fail: {pattern.success_count}/{pattern.failure_count}")
        print(f"  Examples: {pattern.examples[:5]}")
        print()


async def cmd_stats(args):
    """Show knowledge base statistics."""
    print("=== Cardinal Knowledge Statistics ===")
    print()

    km = KnowledgeManager()
    stats = km.get_stats()

    print(f"Total entries: {stats['total_entries']}")
    print()

    print("By category:")
    for cat, count in stats["categories"].items():
        print(f"  {cat}: {count}")
    print()

    print(f"Patterns: {stats['patterns']['count']}")
    if stats["patterns"]["by_mechanic"]:
        print("  By mechanic:")
        for mech, count in stats["patterns"]["by_mechanic"].items():
            print(f"    {mech}: {count}")


async def cmd_query(args):
    """Query knowledge base with natural language."""
    print("=== Cardinal Knowledge Query ===")
    print(f"Question: {args.question}")
    print()

    km = KnowledgeManager(
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
    )

    result = await km.query_knowledge(args.question)

    print(f"Sources consulted: {result['source_count']}")
    print()
    print("Answer:")
    print("-" * 50)
    print(result["answer"])
    print("-" * 50)


async def cmd_batch(args):
    """Batch process multiple spell IDs."""
    print("=== Cardinal Batch Processing ===")
    print(f"Spell IDs: {args.spell_ids}")
    print()

    spell_ids = [int(sid.strip()) for sid in args.spell_ids.split(",")]

    analyzer = SpellAnalyzer(
        dbc_path=args.dbc_path,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
    )

    if args.dbc_path and args.dbc_path.exists():
        analyzer.load_dbc()

    km = KnowledgeManager()
    generator = BackportGenerator(
        knowledge_manager=km,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
        output_path=args.output_path,
    )

    results = []
    for i, spell_id in enumerate(spell_ids, 1):
        print(f"[{i}/{len(spell_ids)}] Processing spell {spell_id}...")

        comparison = await analyzer.compare_spell(spell_id)
        result = await generator.generate_backport(comparison)
        results.append(result)

        print(f"  Status: {result.status}")
        await asyncio.sleep(1)  # Rate limiting

    print()
    print("=== Batch Summary ===")
    success = sum(1 for r in results if r.status == "success")
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "failed")
    print(f"Success: {success}")
    print(f"Partial: {partial}")
    print(f"Failed: {failed}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Cardinal WoW Backport System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze a spell
    python cardinal_backport_cli.py analyze 116

    # Generate backport for Frostbolt
    python cardinal_backport_cli.py backport 116

    # Search for frost spells
    python cardinal_backport_cli.py search "frostbolt" --online

    # Ask a question
    python cardinal_backport_cli.py query "How do I backport a damage over time spell?"

    # Batch process
    python cardinal_backport_cli.py batch "116,133,172,403"
        """,
    )

    # Global arguments
    parser.add_argument(
        "--dbc-path",
        type=Path,
        default=DEFAULT_DBC_PATH,
        help="Path to 3.3.5a DBC files",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output path for generated files",
    )
    parser.add_argument(
        "--ollama-url",
        default=DEFAULT_OLLAMA_URL,
        help="Ollama server URL",
    )
    parser.add_argument(
        "--ollama-model",
        default=DEFAULT_OLLAMA_MODEL,
        help="Ollama model to use",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a spell")
    analyze_parser.add_argument("spell_id", type=int, help="Spell ID to analyze")

    # Backport command
    backport_parser = subparsers.add_parser("backport", help="Generate backport")
    backport_parser.add_argument("spell_id", type=int, help="Spell ID to backport")
    backport_parser.add_argument(
        "--custom-id",
        type=int,
        help="Custom spell ID for the backport (avoid conflicts)",
    )
    backport_parser.add_argument(
        "--include-npc",
        action="store_true",
        help="Generate trainer NPC SQL",
    )

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for spells")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--online",
        action="store_true",
        help="Also search Wowhead",
    )
    search_parser.add_argument(
        "--version",
        choices=["retail", "3.3.5a"],
        default="retail",
        help="Version to search",
    )

    # Learn command
    subparsers.add_parser("learn", help="Show learned patterns")

    # Stats command
    subparsers.add_parser("stats", help="Show knowledge stats")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query knowledge base")
    query_parser.add_argument("question", help="Natural language question")

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Batch process spells")
    batch_parser.add_argument("spell_ids", help="Comma-separated spell IDs")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Run the appropriate command
    commands = {
        "analyze": cmd_analyze,
        "backport": cmd_backport,
        "search": cmd_search,
        "learn": cmd_learn,
        "stats": cmd_stats,
        "query": cmd_query,
        "batch": cmd_batch,
    }

    asyncio.run(commands[args.command](args))


if __name__ == "__main__":
    main()
