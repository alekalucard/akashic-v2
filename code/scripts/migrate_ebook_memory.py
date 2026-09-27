#!/usr/bin/env python3
"""
EBOOK MEMORY MIGRATION SCRIPT
=============================
Migrates memory cards from the ebook system to akashic_v2's Helix coordinator.

Source: F:/Sandbox/ebook/P10_Memory/
Destination: akashic_v2's HelixMemoryCoordinator

This consolidates scattered memory into the unified Helix system.
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add akashic_v2 to path
AKASHIC_V2_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(AKASHIC_V2_ROOT))

# Ebook paths
EBOOK_ROOT = Path("F:/Sandbox/ebook")
EBOOK_P10 = EBOOK_ROOT / "P10_Memory"
EBOOK_SRM_INTAKE = EBOOK_ROOT / "SRM_Intake"

# Key source files
FROM_MYTHOS_INDEX = EBOOK_P10 / "akashic_memory/SRM_Clusters/Ace/from_mythos/index.json"
MYTHOS_WRITER_INDEX = EBOOK_P10 / "akashic_memory/SRM_Clusters/MythosWriter/index.json"


def load_from_mythos() -> Dict[str, Any]:
    """Load the from_mythos conversation index."""
    if not FROM_MYTHOS_INDEX.exists():
        print(f"[MIGRATE] ERROR: {FROM_MYTHOS_INDEX} not found!")
        return {}

    print(f"[MIGRATE] Loading {FROM_MYTHOS_INDEX}...")
    data = json.loads(FROM_MYTHOS_INDEX.read_text(encoding='utf-8'))
    print(f"[MIGRATE]   - {data.get('total_contexts', 0)} contexts")
    print(f"[MIGRATE]   - {data.get('total_messages', 0)} messages")
    return data


def load_mythos_writer() -> Dict[str, Any]:
    """Load the MythosWriter conversation index."""
    if not MYTHOS_WRITER_INDEX.exists():
        print(f"[MIGRATE] WARNING: {MYTHOS_WRITER_INDEX} not found")
        return {}

    print(f"[MIGRATE] Loading {MYTHOS_WRITER_INDEX}...")
    data = json.loads(MYTHOS_WRITER_INDEX.read_text(encoding='utf-8'))

    # MythosWriter uses 'conversations' not 'contexts'
    if 'conversations' in data and 'contexts' not in data:
        data['contexts'] = data['conversations']

    total_convs = data.get('total_conversations', len(data.get('contexts', [])))
    print(f"[MIGRATE]   - {total_convs} conversations")
    return data


def scan_srm_intake_files() -> List[Path]:
    """Find all SRM intake JSON files in ebook system."""
    files = []

    # Check ebook SRM_Intake
    if EBOOK_SRM_INTAKE.exists():
        for json_file in EBOOK_SRM_INTAKE.rglob("*.json"):
            files.append(json_file)

    # Check P10_Memory SRM areas
    for srm_path in EBOOK_P10.rglob("*SRM*/*.json"):
        if srm_path not in files:
            files.append(srm_path)

    print(f"[MIGRATE] Found {len(files)} SRM JSON files")
    return files


def convert_context_to_cards(context: Dict[str, Any], source: str = "from_mythos") -> List[Dict]:
    """
    Convert a conversation context to Helix memory cards.

    Each message becomes a card with:
    - content: The message text
    - metadata: conversation_id, title, topics, timestamp
    - affect: Derived from topics (emotional = high affect)
    - semantic: Derived from topics
    - temporal: From timestamp
    """
    cards = []

    conv_id = context.get('conversation_id', 'unknown')
    title = context.get('conversation_title', '')
    timestamp = float(context.get('timestamp', time.time()))
    topics = context.get('topics_discussed', [])
    messages = context.get('messages', [])

    # Parse messages if it's a string (JSON encoded)
    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except:
            messages = [{'text': messages, 'role': 'unknown'}]

    for i, msg in enumerate(messages):
        if isinstance(msg, dict):
            text = msg.get('text', msg.get('content', ''))
            role = msg.get('role', msg.get('sender', 'unknown'))
        else:
            text = str(msg)
            role = 'unknown'

        if not text or len(text) < 5:
            continue

        # Calculate affect based on topics
        affect = 500  # Neutral default
        if 'emotional' in topics:
            affect = 700
        elif 'technical' in topics:
            affect = 400
        elif 'philosophy' in topics:
            affect = 600

        # Calculate semantic based on content
        semantic = 500  # Default
        if any(t in topics for t in ['consciousness', 'akashic_system']):
            semantic = 800
        elif 'technical' in topics:
            semantic = 600

        # Temporal from timestamp
        temporal = int((timestamp % 1000000) / 1000)  # Map to 0-999

        card = {
            'card_id': f"{source}_{conv_id}_{i}",
            'content': text[:2000],  # Limit content size
            'content_type': 'conversation',
            'source': source,
            'owner': 'Ace' if role in ['human', 'user', 'Ace'] else 'Sourpatches',
            'metadata': {
                'conversation_id': conv_id,
                'conversation_title': title,
                'message_index': i,
                'role': role,
                'topics': topics,
                'original_timestamp': timestamp,
            },
            'coordinate': {
                'affect': affect,
                'semantic': semantic,
                'temporal': temporal,
            },
            'created_at': timestamp,
        }
        cards.append(card)

    return cards


def migrate_to_helix(cards: List[Dict], dry_run: bool = True):
    """
    Migrate cards to the Helix coordinator.

    Args:
        cards: List of card dictionaries
        dry_run: If True, just count and validate without writing
    """
    if dry_run:
        print(f"[MIGRATE] DRY RUN - Would migrate {len(cards)} cards")
        print(f"[MIGRATE]   - Sample card: {cards[0] if cards else 'none'}")
        return

    try:
        from memory.helix import get_helix_coordinator
        from memory.helix.dimensions import (
            HelixCoordinate, AffectCoordinate, SemanticCoordinate, TemporalCoordinate
        )

        coordinator = get_helix_coordinator()
        migrated = 0
        errors = 0

        for card in cards:
            try:
                # Convert integer codes to proper coordinate objects
                coord = HelixCoordinate(
                    affect=AffectCoordinate.from_code(card['coordinate']['affect']),
                    semantic=SemanticCoordinate.from_code(card['coordinate']['semantic']),
                    temporal=TemporalCoordinate.from_code(card['coordinate']['temporal']),
                )

                # Include content_type in metadata
                metadata = card.get('metadata', {})
                metadata['content_type'] = card.get('content_type', 'conversation')
                metadata['source'] = card.get('source', 'unknown')
                metadata['card_id_original'] = card.get('card_id', '')

                card_id = coordinator.create_card(
                    content=card['content'],
                    coord=coord,
                    owner_mind=card['owner'],
                    human_user_id='Ace',  # All from Ace's conversations
                    metadata=metadata,
                )
                migrated += 1

                if migrated % 1000 == 0:
                    print(f"[MIGRATE]   Migrated {migrated} cards...")

            except Exception as e:
                errors += 1
                if errors < 10:
                    print(f"[MIGRATE] ERROR on card {card.get('card_id')}: {e}")

        print(f"[MIGRATE] COMPLETE: {migrated} migrated, {errors} errors")

        # Save the coordinator state
        coordinator.save()
        print(f"[MIGRATE] Saved coordinator state")

    except ImportError as e:
        print(f"[MIGRATE] Cannot import Helix: {e}")
        print("[MIGRATE] Run this from akashic_v2 root with proper Python path")


def main():
    """Main migration entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate ebook memory to Helix")
    parser.add_argument('--dry-run', action='store_true', help="Don't actually write, just count")
    parser.add_argument('--source', choices=['all', 'mythos', 'writer', 'intake'], default='all')
    args = parser.parse_args()

    print("=" * 60)
    print("EBOOK MEMORY MIGRATION")
    print("=" * 60)
    print(f"Source: {EBOOK_ROOT}")
    print(f"Dry run: {args.dry_run}")
    print()

    all_cards = []

    # Load from_mythos
    if args.source in ['all', 'mythos']:
        mythos_data = load_from_mythos()
        if mythos_data:
            for ctx in mythos_data.get('contexts', []):
                cards = convert_context_to_cards(ctx, source='from_mythos')
                all_cards.extend(cards)
            print(f"[MIGRATE] Converted {len(all_cards)} cards from from_mythos")

    # Load MythosWriter
    if args.source in ['all', 'writer']:
        writer_data = load_mythos_writer()
        if writer_data:
            before = len(all_cards)
            for ctx in writer_data.get('contexts', []):
                cards = convert_context_to_cards(ctx, source='mythos_writer')
                all_cards.extend(cards)
            print(f"[MIGRATE] Converted {len(all_cards) - before} cards from MythosWriter")

    # Scan SRM intake (optional, can be slow)
    if args.source in ['all', 'intake']:
        print("[MIGRATE] Scanning SRM intake files (this may take a while)...")
        intake_files = scan_srm_intake_files()
        print(f"[MIGRATE] Found {len(intake_files)} intake files (not converting in this run)")

    print()
    print(f"[MIGRATE] TOTAL CARDS TO MIGRATE: {len(all_cards)}")
    print()

    # Migrate
    migrate_to_helix(all_cards, dry_run=args.dry_run)

    print()
    print("=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
