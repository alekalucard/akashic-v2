#!/usr/bin/env python3
"""
ENHANCED EBOOK MEMORY MIGRATION SCRIPT
======================================
Migrates ALL memory from the ebook system to akashic_v2's Helix coordinator.

SOURCES:
1. SRM_Intake (~18,514 files) - Session summaries and claude_code sessions
2. Genesis Memories (~5,526 files) - Fairy creation and thought memories
3. SRM Clusters (media, visual_cards) - Media metadata and visual processing cards
4. Boot Logs (~73,249 entries) - JSONL boot observation logs

DESTINATION: Helix Memory Coordinator with proper ownership and coordinates

Usage:
    python migrate_ebook_memory_enhanced.py --dry-run          # Count and validate
    python migrate_ebook_memory_enhanced.py --source srm      # Migrate SRM_Intake only
    python migrate_ebook_memory_enhanced.py --source genesis  # Migrate genesis only
    python migrate_ebook_memory_enhanced.py --source boot     # Migrate boot logs only
    python migrate_ebook_memory_enhanced.py --source media    # Migrate media index only
    python migrate_ebook_memory_enhanced.py --source visual   # Migrate visual cards only
    python migrate_ebook_memory_enhanced.py --all             # Migrate everything
"""

import json
import sys
import time
import argparse
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Generator
from datetime import datetime

# Add akashic_v2 to path
AKASHIC_V2_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(AKASHIC_V2_ROOT))

# =============================================================================
# PATHS
# =============================================================================

EBOOK_ROOT = Path("F:/Sandbox/ebook")
EBOOK_SRM_INTAKE = EBOOK_ROOT / "SRM_Intake"
EBOOK_GENESIS = EBOOK_ROOT / "P10_Memory" / "genesis_memories"
EBOOK_SRM_CLUSTERS = EBOOK_ROOT / "P10_Memory" / "SRM_Clusters"
EBOOK_BOOT_LOGS = EBOOK_ROOT / "boot_logs"

# Media and visual indexes
MEDIA_INDEX = EBOOK_SRM_CLUSTERS / "media" / "media_index.json"
VISUAL_CARDS_INDEX = EBOOK_SRM_CLUSTERS / "visual_cards" / "visual_cards_index.json"

# =============================================================================
# STATISTICS TRACKER
# =============================================================================

class MigrationStats:
    """Track migration statistics and errors."""

    def __init__(self):
        self.sources = {}
        self.total_files = 0
        self.total_cards = 0
        self.total_errors = 0
        self.errors = []  # Store first 100 errors

    def add_source(self, name: str):
        self.sources[name] = {
            'files': 0,
            'cards': 0,
            'errors': 0,
            'skipped': 0,
        }

    def count_file(self, source: str):
        self.sources[source]['files'] += 1
        self.total_files += 1

    def count_card(self, source: str, count: int = 1):
        self.sources[source]['cards'] += count
        self.total_cards += count

    def count_error(self, source: str, error: str):
        self.sources[source]['errors'] += 1
        self.total_errors += 1
        if len(self.errors) < 100:
            self.errors.append(f"[{source}] {error}")

    def count_skipped(self, source: str):
        self.sources[source]['skipped'] += 1

    def report(self) -> str:
        lines = [
            "=" * 60,
            "MIGRATION STATISTICS",
            "=" * 60,
        ]
        for name, stats in self.sources.items():
            lines.append(f"\n{name}:")
            lines.append(f"  Files processed: {stats['files']}")
            lines.append(f"  Cards created:   {stats['cards']}")
            lines.append(f"  Errors:          {stats['errors']}")
            lines.append(f"  Skipped:         {stats['skipped']}")

        lines.append(f"\n{'=' * 60}")
        lines.append(f"TOTALS:")
        lines.append(f"  Total files:  {self.total_files}")
        lines.append(f"  Total cards:  {self.total_cards}")
        lines.append(f"  Total errors: {self.total_errors}")

        if self.errors:
            lines.append(f"\nFirst {len(self.errors)} errors:")
            for e in self.errors[:10]:
                lines.append(f"  - {e[:100]}")

        return "\n".join(lines)

# =============================================================================
# COORDINATE HELPERS
# =============================================================================

def timestamp_to_temporal(ts: float) -> int:
    """Convert timestamp to temporal coordinate code (0-999)."""
    # Use age in seconds to determine scale
    now = time.time()
    age = now - ts

    if age < 60:
        scale = 0  # Immediate
    elif age < 3600:
        scale = 1  # Short
    elif age < 86400:
        scale = 2  # Session
    elif age < 604800:
        scale = 3  # Daily
    elif age < 2592000:
        scale = 4  # Weekly
    else:
        scale = 5  # Monthly+

    recurrence = 0  # Single event
    decay = 5  # Moderate persistence

    return (scale * 100) + (recurrence * 10) + decay


def infer_affect_from_content(content: str, tags: List[str] = None) -> int:
    """Infer affect coordinate from content and tags."""
    tags = tags or []
    tags_lower = [t.lower() for t in tags]
    content_lower = content.lower() if isinstance(content, str) else ""

    # Check for emotional keywords
    if any(k in tags_lower for k in ['joy', 'success', 'milestone', 'achievement', 'celebration']):
        domain, valence = 1, 8  # Joy, positive
    elif any(k in tags_lower for k in ['trust', 'safety', 'comfort', 'love', 'connection']):
        domain, valence = 2, 7  # Trust, positive
    elif any(k in tags_lower for k in ['fear', 'anxiety', 'threat', 'danger', 'warning']):
        domain, valence = 3, 3  # Fear, negative
    elif any(k in tags_lower for k in ['surprise', 'novelty', 'discovery', 'curiosity']):
        domain, valence = 4, 6  # Surprise, slightly positive
    elif any(k in tags_lower for k in ['error', 'failure', 'bug', 'broken', 'loss']):
        domain, valence = 5, 3  # Sadness, negative
    elif any(k in tags_lower for k in ['disgust', 'rejection', 'bad', 'wrong']):
        domain, valence = 6, 2  # Disgust, negative
    elif any(k in tags_lower for k in ['frustration', 'conflict', 'angry', 'rage']):
        domain, valence = 7, 2  # Anger, negative
    elif any(k in tags_lower for k in ['hope', 'anticipation', 'desire', 'planning']):
        domain, valence = 8, 7  # Anticipation, positive
    elif any(k in tags_lower for k in ['consciousness', 'transcendent', 'awe', 'wonder']):
        domain, valence = 9, 8  # Transcendent, positive
    else:
        domain, valence = 0, 5  # Neutral

    intensity = 5  # Default moderate
    if 'high' in content_lower or 'critical' in content_lower or 'important' in content_lower:
        intensity = 7
    elif 'low' in content_lower or 'minor' in content_lower:
        intensity = 3

    return (domain * 100) + (valence * 10) + intensity


def infer_semantic_from_content(content: str, tags: List[str] = None, kind: str = "") -> int:
    """Infer semantic coordinate from content, tags, and kind."""
    tags = tags or []
    all_text = " ".join([content if isinstance(content, str) else "", kind] + tags).lower()

    # Domain mapping based on keywords
    if any(k in all_text for k in ['consciousness', 'philosophy', 'mind', 'being', 'awareness']):
        domain = 1  # Philosophy
    elif any(k in all_text for k in ['spiritual', 'meaning', 'transcendent', 'soul']):
        domain = 2  # Religion/Spirituality
    elif any(k in all_text for k in ['social', 'relationship', 'community', 'user', 'interaction']):
        domain = 3  # Social
    elif any(k in all_text for k in ['language', 'communication', 'chat', 'message', 'text']):
        domain = 4  # Language
    elif any(k in all_text for k in ['science', 'logic', 'math', 'analysis', 'data']):
        domain = 5  # Science
    elif any(k in all_text for k in ['code', 'technology', 'system', 'engineering', 'fairy', 'boot', 'wiring']):
        domain = 6  # Technology
    elif any(k in all_text for k in ['art', 'music', 'creative', 'visual', 'image', 'aesthetic']):
        domain = 7  # Arts
    elif any(k in all_text for k in ['story', 'narrative', 'history', 'memory', 'session']):
        domain = 8  # Literature/History
    elif any(k in all_text for k in ['personal', 'identity', 'self', 'individual', 'me', 'i ']):
        domain = 9  # Personal
    else:
        domain = 0  # General

    subdomain = 0
    detail = 0

    return (domain * 100) + (subdomain * 10) + detail


# =============================================================================
# CONVERTERS - Transform source data to Helix cards
# =============================================================================

def convert_srm_intake_file(filepath: Path) -> List[Dict]:
    """
    Convert an SRM_Intake JSON file to Helix cards.

    Handles multiple formats:
    1. session_summary - session metadata with brief summaries (dict or string summary)
    2. claude_code - detailed claude code session with content
    3. blueprint.hash - code hash records (minimal cards)
    4. rich session summaries with accomplishments
    """
    cards = []

    try:
        data = json.loads(filepath.read_text(encoding='utf-8'))
    except Exception as e:
        return []

    file_type = data.get('type', data.get('kind', 'unknown'))

    # Handle blueprint.hash files - minimal metadata only
    if file_type == 'blueprint.hash':
        hash_data = data.get('data', {})
        code_hash = hash_data.get('code_hash', '')
        ts = data.get('ts', time.time())
        if not code_hash:
            return []

        card = {
            'card_id': f"blueprint_{filepath.stem}",
            'content': f"Blueprint hash: {code_hash[:16]}...",
            'content_type': 'blueprint_hash',
            'source': 'srm_intake',
            'owner': 'Nous',
            'metadata': {
                'original_file': str(filepath),
                'code_hash': code_hash,
            },
            'coordinate': {
                'affect': 55,  # Neutral
                'semantic': 600,  # Technology
                'temporal': timestamp_to_temporal(ts),
            },
            'created_at': ts,
            'tags': ['blueprint', 'hash'],
        }
        return [card]

    if file_type == 'session_summary':
        # Session summary format - summary can be dict or string
        summary = data.get('summary', {})

        # Handle string summary (rich format)
        if isinstance(summary, str):
            content = summary
            tags = data.get('tags', [])
        else:
            # Dict summary format
            content = summary.get('brief', '') or data.get('content', '')
            tags = summary.get('tags', data.get('tags', []))

        # Also check for accomplishments (rich session format)
        accomplishments = data.get('accomplishments', {})
        if accomplishments and not content:
            # Build content from accomplishments
            content_parts = []
            if data.get('title'):
                content_parts.append(f"Session: {data.get('title')}")
            for key, val in accomplishments.items():
                if isinstance(val, dict) and 'description' in val:
                    content_parts.append(f"{key}: {val['description']}")
            content = " | ".join(content_parts)

        if not content or len(content) < 10:
            return []

        try:
            timestamp = datetime.fromisoformat(data.get('timestamp', '2026-01-01T00:00:00')).timestamp()
        except:
            timestamp = time.time()

        # Build metadata based on summary type
        if isinstance(summary, dict):
            metadata = {
                'original_file': str(filepath),
                'topic': summary.get('topic', 'general'),
                'files_modified': summary.get('files', []),
                'learnings': summary.get('learnings', data.get('key_learnings', [])),
                'warnings': summary.get('warnings', []),
                'next_steps': summary.get('next_steps', ''),
            }
        else:
            # Rich format with accomplishments
            metadata = {
                'original_file': str(filepath),
                'title': data.get('title', ''),
                'accomplishments': list(data.get('accomplishments', {}).keys()),
                'key_learnings': data.get('key_learnings', []),
                'still_todo': data.get('still_todo', []),
            }

        card = {
            'card_id': f"srm_intake_{data.get('content_hash', filepath.stem)}",
            'content': content[:2000],
            'content_type': 'session_summary',
            'source': 'srm_intake',
            'owner': 'Nous',
            'metadata': metadata,
            'coordinate': {
                'affect': infer_affect_from_content(content, tags),
                'semantic': infer_semantic_from_content(content, tags, 'session'),
                'temporal': timestamp_to_temporal(timestamp),
            },
            'created_at': timestamp,
            'tags': tags,
        }
        cards.append(card)

    elif file_type.startswith('session.claude_code') or 'helix' in data:
        # Claude code session format with helix structure
        content = data.get('content', '')
        if not content or len(content) < 10:
            return []

        timestamp = data.get('ts', time.time())
        tags = data.get('tags', [])
        helix = data.get('helix', {})

        # Extract from helix structure
        l_data = helix.get('L', {})
        c_data = helix.get('C', {})

        card = {
            'card_id': f"claude_code_{data.get('id', filepath.stem)}",
            'content': content[:2000],
            'content_type': 'claude_code_session',
            'source': 'srm_intake',
            'owner': l_data.get('w', {}).get('who', 'Nous'),
            'metadata': {
                'original_file': str(filepath),
                'concept': l_data.get('concept', ''),
                'where': l_data.get('w', {}).get('where', ''),
                'why': l_data.get('w', {}).get('why', ''),
                'how': l_data.get('w', {}).get('how', ''),
                'affect_state': c_data.get('affect', 'neutral'),
                'energy': c_data.get('energy', 0.5),
                'coherence': c_data.get('coherence', 0.5),
                'ownership': data.get('ownership', 'PERSONAL'),
            },
            'coordinate': {
                'affect': infer_affect_from_content(content, tags),
                'semantic': infer_semantic_from_content(content, tags, 'code'),
                'temporal': timestamp_to_temporal(timestamp),
            },
            'created_at': timestamp,
            'tags': tags,
        }
        cards.append(card)

    elif file_type == 'quick_fix':
        # Quick fix session
        title = data.get('title', '')
        problem = data.get('problem', '')
        root_cause = data.get('root_cause', '')
        fix = data.get('fix', {})
        tags = data.get('tags', [])

        content_parts = [f"FIX: {title}"]
        if problem:
            content_parts.append(f"Problem: {problem}")
        if root_cause:
            content_parts.append(f"Root cause: {root_cause}")
        if isinstance(fix, dict):
            content_parts.append(f"File: {fix.get('file', '')}")

        content = " | ".join(content_parts)
        if len(content) < 10:
            return []

        try:
            timestamp = datetime.fromisoformat(data.get('timestamp', '2026-01-01T00:00:00')).timestamp()
        except:
            timestamp = time.time()

        card = {
            'card_id': f"quick_fix_{filepath.stem}",
            'content': content[:2000],
            'content_type': 'quick_fix',
            'source': 'srm_intake',
            'owner': 'Nous',
            'metadata': {
                'original_file': str(filepath),
                'title': title,
                'problem': problem,
                'root_cause': root_cause,
                'fix': fix,
            },
            'coordinate': {
                'affect': infer_affect_from_content(content, tags + ['fix', 'bugfix']),
                'semantic': 600,  # Technology
                'temporal': timestamp_to_temporal(timestamp),
            },
            'created_at': timestamp,
            'tags': tags,
        }
        cards.append(card)

    elif file_type == 'blueprint.report':
        # Blueprint report - fairy metadata
        report_data = data.get('data', {})
        actor_name = report_data.get('actor_name', '')
        plane = report_data.get('plane', '')
        archetype = report_data.get('archetype', '')
        intent = report_data.get('creator_intent', {})
        timestamp = data.get('ts', time.time())

        content_parts = [f"Fairy Blueprint: {actor_name}"]
        if plane:
            content_parts.append(f"Plane: {plane}")
        if archetype:
            content_parts.append(f"Archetype: {archetype}")
        if intent.get('vision'):
            content_parts.append(f"Vision: {intent['vision']}")

        content = " | ".join(content_parts)
        if not actor_name:
            return []

        card = {
            'card_id': f"blueprint_report_{filepath.stem}",
            'content': content[:2000],
            'content_type': 'blueprint_report',
            'source': 'srm_intake',
            'owner': actor_name,
            'metadata': {
                'original_file': str(filepath),
                'actor_name': actor_name,
                'plane': plane,
                'archetype': archetype,
                'creator_intent': intent,
            },
            'coordinate': {
                'affect': 55,  # Neutral
                'semantic': 600,  # Technology
                'temporal': timestamp_to_temporal(timestamp),
            },
            'created_at': timestamp,
            'tags': ['blueprint', 'fairy', plane, archetype],
        }
        cards.append(card)

    elif file_type == 'health.report':
        # Health report - fairy health status
        report_data = data.get('data', {})
        fairy_name = report_data.get('fairy_name', report_data.get('actor_name', ''))
        timestamp = data.get('ts', time.time())

        if not fairy_name:
            return []

        content = f"Health Report: {fairy_name} | Status: {report_data.get('status', 'unknown')}"

        card = {
            'card_id': f"health_report_{filepath.stem}",
            'content': content[:2000],
            'content_type': 'health_report',
            'source': 'srm_intake',
            'owner': fairy_name,
            'metadata': {
                'original_file': str(filepath),
                'fairy_name': fairy_name,
                'report_data': report_data,
            },
            'coordinate': {
                'affect': 55,  # Neutral
                'semantic': 600,  # Technology
                'temporal': timestamp_to_temporal(timestamp),
            },
            'created_at': timestamp,
            'tags': ['health', 'fairy', fairy_name],
        }
        cards.append(card)

    elif file_type.startswith('claudefairy.'):
        # ClaudeFairy domain records - thoughts, insights, tool use, etc.
        content = data.get('content', data.get('what', ''))
        if not content or len(content) < 10:
            return []

        entry_type = data.get('entry_type', file_type.split('.')[-1])
        feeling = data.get('feeling', 'neutral')
        energy = data.get('energy', 0.5)
        coherence = data.get('coherence', 0.5)
        timestamp = data.get('ts', time.time())
        source = data.get('source', 'ClaudeFairy')

        # Calculate affect from feeling/energy
        affect_mapping = {
            'ambitious': 855,  # Anticipation, high valence, moderate intensity
            'curious': 467,  # Surprise, moderate valence, high intensity
            'focused': 57,  # Neutral, moderate valence, high intensity
            'joyful': 177,  # Joy, high valence, high intensity
            'peaceful': 255,  # Trust, moderate valence, moderate intensity
            'anxious': 334,  # Fear, low valence, moderate intensity
        }
        affect_code = affect_mapping.get(feeling, 55)

        # Adjust intensity based on energy
        if energy > 0.7:
            affect_code = (affect_code // 10) * 10 + 7
        elif energy < 0.3:
            affect_code = (affect_code // 10) * 10 + 3

        card = {
            'card_id': f"claudefairy_{entry_type}_{filepath.stem}",
            'content': content[:2000],
            'content_type': entry_type,
            'source': 'srm_intake',
            'owner': source,
            'metadata': {
                'original_file': str(filepath),
                'entry_type': entry_type,
                'feeling': feeling,
                'energy': energy,
                'coherence': coherence,
            },
            'coordinate': {
                'affect': affect_code,
                'semantic': infer_semantic_from_content(content, [entry_type], entry_type),
                'temporal': timestamp_to_temporal(timestamp),
            },
            'created_at': timestamp,
            'tags': ['claudefairy', entry_type, feeling],
        }
        cards.append(card)

    elif file_type == 'ingest.record':
        # Ingest records - captured thoughts and content
        content = data.get('content', data.get('what', ''))
        if not content or len(content) < 10:
            return []

        timestamp = data.get('ts', time.time())
        source = data.get('source', 'ingest')
        media_type = data.get('media_type', 'text/plain')

        card = {
            'card_id': f"ingest_{filepath.stem}",
            'content': content[:2000],
            'content_type': 'ingest_record',
            'source': 'srm_intake',
            'owner': source if source not in ['ingest', ''] else 'Nous',
            'metadata': {
                'original_file': str(filepath),
                'media_type': media_type,
            },
            'coordinate': {
                'affect': infer_affect_from_content(content, []),
                'semantic': infer_semantic_from_content(content, [], 'ingest'),
                'temporal': timestamp_to_temporal(timestamp),
            },
            'created_at': timestamp,
            'tags': ['ingest', source],
        }
        cards.append(card)

    elif file_type == 'recall.top':
        # Memory recall records
        content = data.get('content', data.get('what', ''))
        if not content or len(content) < 10:
            return []

        timestamp = data.get('ts', time.time())
        query = data.get('query', '')
        results = data.get('results', [])

        card = {
            'card_id': f"recall_{filepath.stem}",
            'content': content[:2000],
            'content_type': 'recall_record',
            'source': 'srm_intake',
            'owner': 'Nous',
            'metadata': {
                'original_file': str(filepath),
                'query': query,
                'result_count': len(results),
            },
            'coordinate': {
                'affect': 55,  # Neutral recall
                'semantic': 800,  # Literature/history (memory)
                'temporal': timestamp_to_temporal(timestamp),
            },
            'created_at': timestamp,
            'tags': ['recall', 'memory'],
        }
        cards.append(card)

    return cards


def convert_genesis_file(filepath: Path) -> List[Dict]:
    """
    Convert a genesis memory file to Helix cards.

    Genesis memories record fairy creation and thought processes.
    """
    cards = []

    try:
        data = json.loads(filepath.read_text(encoding='utf-8'))
    except Exception as e:
        return []

    mem_id = data.get('id', filepath.stem)
    affect_value = data.get('affect', 0.5)
    semantic = data.get('semantic', {})
    temporal = data.get('temporal', time.time())
    source = data.get('source', 'genesis')
    kind = data.get('kind', 'unknown')

    # Extract content from semantic structure
    fairy_name = semantic.get('fairy_name', '')
    thought = semantic.get('thought', {})

    content_parts = []
    if fairy_name:
        content_parts.append(f"Fairy: {fairy_name}")
    if thought:
        content_parts.append(f"Cause: {thought.get('cause', '')}")
        effect = thought.get('effect', {})
        if isinstance(effect, dict):
            content_parts.append(f"Effect: {effect.get('type', '')}: {effect.get('value', '')}")
        content_parts.append(f"Affect In: {thought.get('affect_in', 0):.3f}")
        content_parts.append(f"Affect Out: {thought.get('affect_out', 0):.3f}")

    content = " | ".join(content_parts)
    if not content:
        return []

    # Calculate affect from numeric value
    affect_domain = 0 if affect_value < 0.3 else (1 if affect_value > 0.7 else 4)  # Neutral, Joy, or Surprise
    affect_valence = min(9, int(affect_value * 10))
    affect_intensity = 5
    affect_code = (affect_domain * 100) + (affect_valence * 10) + affect_intensity

    card = {
        'card_id': f"genesis_{mem_id}",
        'content': content[:2000],
        'content_type': kind,
        'source': source,
        'owner': fairy_name if fairy_name else 'Nous',
        'metadata': {
            'original_file': str(filepath),
            'fairy_name': fairy_name,
            'thought': thought,
            'original_affect': affect_value,
        },
        'coordinate': {
            'affect': affect_code,
            'semantic': infer_semantic_from_content(content, [], kind),
            'temporal': timestamp_to_temporal(temporal),
        },
        'created_at': temporal,
        'tags': [kind, source, fairy_name] if fairy_name else [kind, source],
    }
    cards.append(card)

    return cards


def convert_boot_log_line(line: str, log_file: str) -> Optional[Dict]:
    """
    Convert a single boot log JSONL line to a Helix card.
    """
    try:
        data = json.loads(line)
    except:
        return None

    ts = data.get('ts', time.time())
    event_type = data.get('t', 'unknown')
    source = data.get('src', 'boot')
    msg = data.get('msg', '')
    ok = data.get('ok', True)
    details = data.get('details', {})

    if not msg or len(msg) < 5:
        return None

    # Build content
    content = f"[{event_type}] {source}: {msg}"
    if details:
        detail_str = ", ".join(f"{k}={v}" for k, v in list(details.items())[:5])
        content += f" ({detail_str})"

    # Affect based on success/failure
    if ok:
        affect_code = 55  # Neutral/calm
    else:
        affect_code = 533  # Sadness/negative/moderate (error)

    card = {
        'card_id': f"boot_{event_type}_{int(ts * 1000) % 1000000}",
        'content': content[:2000],
        'content_type': 'boot_log',
        'source': 'boot_logs',
        'owner': 'Nous',
        'metadata': {
            'log_file': log_file,
            'event_type': event_type,
            'source_component': source,
            'success': ok,
            'details': details,
            'thread_id': data.get('tid'),
            'thread_name': data.get('tname'),
        },
        'coordinate': {
            'affect': affect_code,
            'semantic': 600,  # Technology domain
            'temporal': timestamp_to_temporal(ts),
        },
        'created_at': ts,
        'tags': ['boot', event_type, source],
    }

    return card


def convert_media_record(record_id: str, record: Dict) -> List[Dict]:
    """
    Convert a media index record to Helix cards.
    """
    cards = []

    filename = record.get('filename', '')
    media_type = record.get('media_type', 'unknown')
    tags = record.get('tags', [])
    description = record.get('description', '')
    context = record.get('context', '')
    colors = record.get('color_names', [])
    detected_type = record.get('detected_type', '')
    ingested_at = record.get('ingested_at', time.time())

    content_parts = [f"Media: {filename}"]
    if detected_type:
        content_parts.append(f"Type: {detected_type}")
    if colors:
        content_parts.append(f"Colors: {', '.join(colors[:3])}")
    if description:
        content_parts.append(f"Description: {description}")
    if context:
        content_parts.append(f"Context: {context}")

    content = " | ".join(content_parts)

    card = {
        'card_id': f"media_{record_id}",
        'content': content[:2000],
        'content_type': media_type,
        'source': 'media_index',
        'owner': 'Ace',  # Media typically from Ace
        'metadata': {
            'filename': filename,
            'original_path': record.get('original_path', ''),
            'stored_path': record.get('stored_path', ''),
            'thumbnail_path': record.get('thumbnail_path', ''),
            'width': record.get('width'),
            'height': record.get('height'),
            'file_hash': record.get('file_hash', ''),
            'dominant_colors': record.get('dominant_colors', []),
            'detected_type': detected_type,
        },
        'coordinate': {
            'affect': infer_affect_from_content(content, tags),
            'semantic': 700,  # Arts domain
            'temporal': timestamp_to_temporal(ingested_at),
        },
        'created_at': ingested_at,
        'tags': tags + [media_type, detected_type] if detected_type else tags + [media_type],
    }
    cards.append(card)

    return cards


def convert_visual_card(card_id: str, card_data: Dict) -> List[Dict]:
    """
    Convert a visual card index record to Helix cards.
    """
    cards = []

    image_id = card_data.get('image_id', '')
    card_type = card_data.get('card_type', '')
    source_path = card_data.get('source_path', '')
    created_at = card_data.get('created_at', time.time())
    siblings = card_data.get('siblings', [])
    content_summary = card_data.get('content_summary', {})

    layer = content_summary.get('layer', card_type.upper())

    content_parts = [f"Visual Processing Layer: {layer}"]
    content_parts.append(f"Image: {image_id}")

    # Add layer-specific info
    if 'edge_density' in content_summary:
        content_parts.append(f"Edge Density: {content_summary['edge_density']:.4f}")
    if 'contour_count' in content_summary:
        content_parts.append(f"Contours: {content_summary['contour_count']}")
    if 'dominant_hue' in content_summary:
        content_parts.append(f"Dominant Hue: {content_summary['dominant_hue']}")
    if 'scene_type' in content_summary:
        content_parts.append(f"Scene: {content_summary['scene_type']}")
    if 'width' in content_summary:
        content_parts.append(f"Size: {content_summary['width']}x{content_summary.get('height', 0)}")

    content = " | ".join(content_parts)

    card = {
        'card_id': f"visual_{card_id}",
        'content': content[:2000],
        'content_type': 'visual_processing',
        'source': 'visual_cards',
        'owner': 'Nous',
        'metadata': {
            'original_card_id': card_id,
            'image_id': image_id,
            'card_type': card_type,
            'source_path': source_path,
            'siblings': siblings,
            'content_summary': content_summary,
        },
        'coordinate': {
            'affect': 456,  # Surprise/curiosity (visual discovery)
            'semantic': 700,  # Arts domain
            'temporal': timestamp_to_temporal(created_at),
        },
        'created_at': created_at,
        'tags': ['visual', layer, card_type],
    }
    cards.append(card)

    return cards


# =============================================================================
# FILE SCANNERS - Yield files/records from each source
# =============================================================================

def scan_srm_intake() -> Generator[Path, None, None]:
    """Yield all JSON files in SRM_Intake."""
    if not EBOOK_SRM_INTAKE.exists():
        return

    for json_file in EBOOK_SRM_INTAKE.rglob("*.json"):
        yield json_file


def scan_genesis() -> Generator[Path, None, None]:
    """Yield all JSON files in genesis_memories."""
    if not EBOOK_GENESIS.exists():
        return

    for json_file in EBOOK_GENESIS.glob("*.json"):
        yield json_file


def scan_boot_logs() -> Generator[tuple, None, None]:
    """Yield (filepath, line) tuples from boot log JSONL files."""
    if not EBOOK_BOOT_LOGS.exists():
        return

    for jsonl_file in EBOOK_BOOT_LOGS.glob("*.jsonl"):
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield (jsonl_file, line)
        except Exception as e:
            print(f"[WARN] Cannot read {jsonl_file}: {e}")


def load_media_index() -> Dict[str, Dict]:
    """Load the media index and return records dict."""
    if not MEDIA_INDEX.exists():
        return {}

    try:
        data = json.loads(MEDIA_INDEX.read_text(encoding='utf-8'))
        return data.get('records', {})
    except Exception as e:
        print(f"[WARN] Cannot load media index: {e}")
        return {}


def load_visual_cards_index() -> Dict[str, Dict]:
    """Load the visual cards index and return cards dict."""
    if not VISUAL_CARDS_INDEX.exists():
        return {}

    try:
        data = json.loads(VISUAL_CARDS_INDEX.read_text(encoding='utf-8'))
        return data.get('cards', {})
    except Exception as e:
        print(f"[WARN] Cannot load visual cards index: {e}")
        return {}


# =============================================================================
# MIGRATION FUNCTIONS
# =============================================================================

def migrate_batch_to_helix(cards: List[Dict], coordinator, stats: MigrationStats, source: str, dry_run: bool = True):
    """Migrate a batch of cards to the Helix coordinator."""
    from memory.helix.dimensions import (
        HelixCoordinate, AffectCoordinate, SemanticCoordinate, TemporalCoordinate
    )
    from memory.helix.ownership import OwnershipLevel

    for card in cards:
        if dry_run:
            stats.count_card(source)
            continue

        try:
            # Build coordinate
            coord = HelixCoordinate(
                affect=AffectCoordinate.from_code(card['coordinate']['affect']),
                semantic=SemanticCoordinate.from_code(card['coordinate']['semantic']),
                temporal=TemporalCoordinate.from_code(card['coordinate']['temporal']),
            )

            # Prepare metadata
            metadata = card.get('metadata', {})
            metadata['content_type'] = card.get('content_type', 'unknown')
            metadata['source'] = card.get('source', 'migration')
            metadata['original_card_id'] = card.get('card_id', '')
            metadata['tags'] = card.get('tags', [])

            # Determine ownership
            ownership = card.get('metadata', {}).get('ownership', 'FOUNDATION')
            if ownership == 'PERSONAL':
                level = OwnershipLevel.PERSONAL
            elif ownership == 'SYSTEM':
                level = OwnershipLevel.SYSTEM
            else:
                level = OwnershipLevel.FOUNDATION

            # Create card
            card_id = coordinator.create_card(
                content=card['content'],
                coord=coord,
                owner_mind=card.get('owner', 'Nous'),
                ownership_level=level,
                human_user_id='Ace',
                metadata=metadata,
            )
            stats.count_card(source)

        except Exception as e:
            stats.count_error(source, f"{card.get('card_id', 'unknown')}: {str(e)[:100]}")


def migrate_srm_intake(coordinator, stats: MigrationStats, dry_run: bool = True):
    """Migrate all SRM_Intake files."""
    source = 'srm_intake'
    stats.add_source(source)

    print(f"[MIGRATE] Scanning SRM_Intake...")
    batch = []
    batch_size = 100

    for filepath in scan_srm_intake():
        stats.count_file(source)

        try:
            cards = convert_srm_intake_file(filepath)
            if not cards:
                stats.count_skipped(source)
                continue
            batch.extend(cards)

            if len(batch) >= batch_size:
                migrate_batch_to_helix(batch, coordinator, stats, source, dry_run)
                batch = []
                if stats.sources[source]['cards'] % 1000 == 0:
                    print(f"[MIGRATE]   {stats.sources[source]['cards']} cards processed...")

        except Exception as e:
            stats.count_error(source, f"{filepath.name}: {str(e)[:80]}")

    # Final batch
    if batch:
        migrate_batch_to_helix(batch, coordinator, stats, source, dry_run)


def migrate_genesis(coordinator, stats: MigrationStats, dry_run: bool = True):
    """Migrate all genesis memory files."""
    source = 'genesis'
    stats.add_source(source)

    print(f"[MIGRATE] Scanning genesis_memories...")
    batch = []
    batch_size = 100

    for filepath in scan_genesis():
        stats.count_file(source)

        try:
            cards = convert_genesis_file(filepath)
            if not cards:
                stats.count_skipped(source)
                continue
            batch.extend(cards)

            if len(batch) >= batch_size:
                migrate_batch_to_helix(batch, coordinator, stats, source, dry_run)
                batch = []
                if stats.sources[source]['cards'] % 1000 == 0:
                    print(f"[MIGRATE]   {stats.sources[source]['cards']} cards processed...")

        except Exception as e:
            stats.count_error(source, f"{filepath.name}: {str(e)[:80]}")

    if batch:
        migrate_batch_to_helix(batch, coordinator, stats, source, dry_run)


def migrate_boot_logs(coordinator, stats: MigrationStats, dry_run: bool = True, sample_rate: float = 0.1):
    """
    Migrate boot log entries.

    Note: Boot logs can be very large (73k+ entries). Use sample_rate to reduce.
    sample_rate=0.1 means keep 10% of entries.
    """
    source = 'boot_logs'
    stats.add_source(source)

    print(f"[MIGRATE] Scanning boot_logs (sample_rate={sample_rate})...")
    batch = []
    batch_size = 500
    counter = 0

    for filepath, line in scan_boot_logs():
        counter += 1

        # Sample to reduce volume
        if sample_rate < 1.0 and (hash(line) % 100) >= (sample_rate * 100):
            continue

        stats.count_file(source)

        try:
            card = convert_boot_log_line(line, str(filepath))
            if not card:
                stats.count_skipped(source)
                continue
            batch.append(card)

            if len(batch) >= batch_size:
                migrate_batch_to_helix(batch, coordinator, stats, source, dry_run)
                batch = []
                if stats.sources[source]['cards'] % 5000 == 0:
                    print(f"[MIGRATE]   {stats.sources[source]['cards']} cards processed...")

        except Exception as e:
            stats.count_error(source, f"line: {str(e)[:80]}")

    if batch:
        migrate_batch_to_helix(batch, coordinator, stats, source, dry_run)

    print(f"[MIGRATE]   Processed {counter} total log lines")


def migrate_media_index(coordinator, stats: MigrationStats, dry_run: bool = True):
    """Migrate media index records."""
    source = 'media_index'
    stats.add_source(source)

    print(f"[MIGRATE] Loading media index...")
    records = load_media_index()
    print(f"[MIGRATE]   Found {len(records)} media records")

    batch = []
    batch_size = 100

    for record_id, record in records.items():
        stats.count_file(source)

        try:
            cards = convert_media_record(record_id, record)
            if not cards:
                stats.count_skipped(source)
                continue
            batch.extend(cards)

            if len(batch) >= batch_size:
                migrate_batch_to_helix(batch, coordinator, stats, source, dry_run)
                batch = []

        except Exception as e:
            stats.count_error(source, f"{record_id}: {str(e)[:80]}")

    if batch:
        migrate_batch_to_helix(batch, coordinator, stats, source, dry_run)


def migrate_visual_cards(coordinator, stats: MigrationStats, dry_run: bool = True):
    """Migrate visual cards index."""
    source = 'visual_cards'
    stats.add_source(source)

    print(f"[MIGRATE] Loading visual cards index...")
    cards_data = load_visual_cards_index()
    print(f"[MIGRATE]   Found {len(cards_data)} visual cards")

    batch = []
    batch_size = 100

    for card_id, card_data in cards_data.items():
        stats.count_file(source)

        try:
            cards = convert_visual_card(card_id, card_data)
            if not cards:
                stats.count_skipped(source)
                continue
            batch.extend(cards)

            if len(batch) >= batch_size:
                migrate_batch_to_helix(batch, coordinator, stats, source, dry_run)
                batch = []

        except Exception as e:
            stats.count_error(source, f"{card_id}: {str(e)[:80]}")

    if batch:
        migrate_batch_to_helix(batch, coordinator, stats, source, dry_run)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Enhanced ebook memory migration to Helix")
    parser.add_argument('--dry-run', action='store_true', help="Count and validate without writing")
    parser.add_argument('--source', choices=['srm', 'genesis', 'boot', 'media', 'visual', 'all'],
                        default='all', help="Which source to migrate")
    parser.add_argument('--all', action='store_true', help="Migrate all sources")
    parser.add_argument('--boot-sample-rate', type=float, default=0.1,
                        help="Sampling rate for boot logs (0.0-1.0)")
    parser.add_argument('--save-interval', type=int, default=5000,
                        help="Save coordinator state every N cards")
    args = parser.parse_args()

    if args.all:
        args.source = 'all'

    print("=" * 70)
    print("ENHANCED EBOOK MEMORY MIGRATION TO HELIX")
    print("=" * 70)
    print(f"Source: {EBOOK_ROOT}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE MIGRATION'}")
    print(f"Target: {args.source}")
    print()

    # Initialize coordinator (only for live mode)
    coordinator = None
    if not args.dry_run:
        try:
            from memory.helix import get_helix_coordinator
            coordinator = get_helix_coordinator()
            print(f"[MIGRATE] Helix coordinator loaded: {coordinator.get_stats()['total_cards']} existing cards")
        except ImportError as e:
            print(f"[ERROR] Cannot import Helix: {e}")
            print("[ERROR] Run this from akashic_v2 root with proper Python path")
            sys.exit(1)

    stats = MigrationStats()

    # Run migrations based on source selection
    try:
        if args.source in ['srm', 'all']:
            migrate_srm_intake(coordinator, stats, args.dry_run)
            if coordinator and not args.dry_run:
                coordinator.save()
                print(f"[MIGRATE] Saved after SRM_Intake")

        if args.source in ['genesis', 'all']:
            migrate_genesis(coordinator, stats, args.dry_run)
            if coordinator and not args.dry_run:
                coordinator.save()
                print(f"[MIGRATE] Saved after genesis")

        if args.source in ['boot', 'all']:
            migrate_boot_logs(coordinator, stats, args.dry_run, args.boot_sample_rate)
            if coordinator and not args.dry_run:
                coordinator.save()
                print(f"[MIGRATE] Saved after boot_logs")

        if args.source in ['media', 'all']:
            migrate_media_index(coordinator, stats, args.dry_run)
            if coordinator and not args.dry_run:
                coordinator.save()
                print(f"[MIGRATE] Saved after media_index")

        if args.source in ['visual', 'all']:
            migrate_visual_cards(coordinator, stats, args.dry_run)
            if coordinator and not args.dry_run:
                coordinator.save()
                print(f"[MIGRATE] Saved after visual_cards")

    except KeyboardInterrupt:
        print("\n[MIGRATE] Interrupted! Saving progress...")
        if coordinator and not args.dry_run:
            coordinator.save()

    # Final report
    print()
    print(stats.report())

    if not args.dry_run and coordinator:
        final_stats = coordinator.get_stats()
        print(f"\nHelix final state: {final_stats['total_cards']} total cards")
        coordinator.save()

    print("\n" + "=" * 70)
    print("MIGRATION COMPLETE" if not args.dry_run else "DRY RUN COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
