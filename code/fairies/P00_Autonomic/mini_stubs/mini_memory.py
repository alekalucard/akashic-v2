"""
MiniMemory - Bootstrap Memory Stub

Just enough to read bootstrap cards from disk.
Full memory system lives in P10_Memory.

Capabilities:
- Read card clusters from disk
- Parse basic card format
- Pass cards to P10 for full processing

Does NOT:
- Build SRM infrastructure
- Run Association Cortex
- Handle complex memory operations
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BootstrapCard:
    """Minimal card representation for bootstrap."""
    card_id: str
    card_type: str  # 'identity', 'config', 'seed'
    content: Dict[str, Any]
    priority: int = 0
    loaded_at: datetime = field(default_factory=datetime.now)


class MiniMemory:
    """
    Minimal memory system for P00 bootstrap.

    Only reads bootstrap cards - no complex memory operations.
    Full SRM/AssociationCortex lives in P10_Memory.
    """

    # Default bootstrap card locations
    BOOTSTRAP_PATHS = [
        "bootstrap/",
        "P10_Memory/Akashic_Records_Physical/bootstrap/",
        "state/bootstrap_cards/",
    ]

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize with optional base path override."""
        self.base_path = base_path or self._find_base_path()
        self._bootstrap_cards: Dict[str, BootstrapCard] = {}
        self._loaded = False

    def _find_base_path(self) -> Path:
        """Find the akashic_v2 root directory."""
        # Try to find from current location
        current = Path(__file__).resolve()

        # Walk up looking for akashic_v2 marker
        for parent in current.parents:
            if (parent / "fairies").exists() and (parent / "P10_Memory").exists():
                return parent

        # Fallback to relative path
        return Path(__file__).parent.parent.parent.parent

    def read_bootstrap_cards(self, card_dir: Optional[str] = None) -> List[BootstrapCard]:
        """
        Read bootstrap cards from disk.

        Args:
            card_dir: Specific directory to read from, or None to check defaults

        Returns:
            List of bootstrap cards, sorted by priority
        """
        cards = []

        # Determine paths to check
        if card_dir:
            paths_to_check = [self.base_path / card_dir]
        else:
            paths_to_check = [self.base_path / p for p in self.BOOTSTRAP_PATHS]

        for card_path in paths_to_check:
            if card_path.exists() and card_path.is_dir():
                cards.extend(self._read_cards_from_dir(card_path))

        # Sort by priority (higher first)
        cards.sort(key=lambda c: c.priority, reverse=True)

        # Cache them
        for card in cards:
            self._bootstrap_cards[card.card_id] = card

        self._loaded = True
        return cards

    def _read_cards_from_dir(self, directory: Path) -> List[BootstrapCard]:
        """Read all card files from a directory."""
        cards = []

        for file_path in directory.glob("*.json"):
            try:
                card = self._parse_card_file(file_path)
                if card:
                    cards.append(card)
            except Exception as e:
                # Bootstrap is critical - log but continue
                print(f"[MiniMemory] Warning: Failed to read {file_path}: {e}")

        # Also check for .card files (legacy format)
        for file_path in directory.glob("*.card"):
            try:
                card = self._parse_card_file(file_path)
                if card:
                    cards.append(card)
            except Exception as e:
                print(f"[MiniMemory] Warning: Failed to read {file_path}: {e}")

        return cards

    def _parse_card_file(self, file_path: Path) -> Optional[BootstrapCard]:
        """Parse a single card file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract card metadata
            card_id = data.get('id', file_path.stem)
            card_type = data.get('type', self._infer_card_type(file_path.name))
            priority = data.get('priority', 0)
            content = data.get('content', data)

            return BootstrapCard(
                card_id=card_id,
                card_type=card_type,
                content=content,
                priority=priority
            )

        except json.JSONDecodeError:
            # Try reading as plain text card
            return self._parse_text_card(file_path)

    def _parse_text_card(self, file_path: Path) -> Optional[BootstrapCard]:
        """Parse a plain text card file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            return BootstrapCard(
                card_id=file_path.stem,
                card_type=self._infer_card_type(file_path.name),
                content={'text': content},
                priority=0
            )
        except Exception:
            return None

    def _infer_card_type(self, filename: str) -> str:
        """Infer card type from filename."""
        name_lower = filename.lower()

        if 'identity' in name_lower:
            return 'identity'
        elif 'config' in name_lower:
            return 'config'
        elif 'seed' in name_lower:
            return 'seed'
        elif 'bootstrap' in name_lower:
            return 'bootstrap'
        else:
            return 'generic'

    def get_card(self, card_id: str) -> Optional[BootstrapCard]:
        """Get a specific bootstrap card by ID."""
        return self._bootstrap_cards.get(card_id)

    def get_cards_by_type(self, card_type: str) -> List[BootstrapCard]:
        """Get all cards of a specific type."""
        return [c for c in self._bootstrap_cards.values() if c.card_type == card_type]

    def get_identity_cards(self) -> List[BootstrapCard]:
        """Get identity cards needed for waking up."""
        return self.get_cards_by_type('identity')

    def get_config_cards(self) -> List[BootstrapCard]:
        """Get configuration cards."""
        return self.get_cards_by_type('config')

    def is_loaded(self) -> bool:
        """Check if bootstrap cards have been loaded."""
        return self._loaded

    def card_count(self) -> int:
        """Get number of loaded bootstrap cards."""
        return len(self._bootstrap_cards)

    def prepare_for_p10(self) -> Dict[str, Any]:
        """
        Package bootstrap cards for handoff to P10_Memory.

        Returns a dict that P10 can use to initialize the full memory system.
        """
        return {
            'bootstrap_cards': [
                {
                    'id': c.card_id,
                    'type': c.card_type,
                    'content': c.content,
                    'priority': c.priority,
                }
                for c in self._bootstrap_cards.values()
            ],
            'card_count': len(self._bootstrap_cards),
            'loaded_at': datetime.now().isoformat(),
            'source': 'mini_memory_bootstrap',
        }


# Singleton instance for bootstrap
_mini_memory_instance: Optional[MiniMemory] = None


def get_mini_memory() -> MiniMemory:
    """Get the singleton MiniMemory instance."""
    global _mini_memory_instance
    if _mini_memory_instance is None:
        _mini_memory_instance = MiniMemory()
    return _mini_memory_instance
